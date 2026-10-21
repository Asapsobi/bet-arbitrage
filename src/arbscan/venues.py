"""Venue fee models and the conversion from a quoted level to an Offer."""
from __future__ import annotations

from dataclasses import dataclass

from . import odds
from .markets import covers
from .model import Offer


@dataclass(frozen=True)
class Venue:
    name: str
    commission: float = 0.0        # exchange commission on net market winnings
    taker_fee: float = 0.0         # prediction-market fee rate r: fee per share = r * p * (1 - p)
    currency: str = 'USD'
    price: str = 'decimal'         # how levels are quoted: 'decimal', 'bp' (basis points of probability) or 'prob'

    @property
    def exchange(self):
        return self.price != 'prob'


# Rates from docs/02 and docs/08 as of 2026-10-21. Betfair UK/IE: 5% Rewards, 2% Basic, 8% Rewards+.
VENUES = {
    'betfair': Venue('betfair', commission=0.05, currency='GBP'),
    'smarkets': Venue('smarkets', commission=0.02, currency='GBP', price='bp'),
    'matchbook': Venue('matchbook', commission=0.02, currency='GBP'),
    'polymarket': Venue('polymarket', taker_fee=0.05, currency='USDC', price='prob'),
}

# Placeholder rates, used only to compare depth across venues (ROI never uses them). Set from your treasury.
FX_TO_USD = {'USD': 1.0, 'USDC': 1.0, 'GBP': 1.30, 'EUR': 1.15}


def offer(venue, market, selection, side, price, size, ts, rule='unknown', fx=FX_TO_USD):
    """Turn one quoted level into an Offer.

    Exchange levels: side 'back' at price o, size = backer stake you can back;
    side 'lay' at price L, size = backer stake you can lay (your liability is
    size * (L - 1)). On Smarkets, back at the offer price and lay at the bid.
    Prediction-market levels: side 'yes' or 'no' at the ask price p, size in
    shares. With only a YES book, NO ask = 1 - YES bid at the bid's size.
    """
    cov = covers(market, selection, side)
    rate = fx[venue.currency]
    if venue.exchange:
        if side not in ('back', 'lay'):
            raise ValueError(f'{venue.name} quotes back/lay, not {side!r}')
        o = odds.from_bp(price) if venue.price == 'bp' else price
        if o <= 1:
            raise ValueError(f'decimal odds must be above 1, got {o}')
        if side == 'back':
            gross, net, at_risk = o, odds.back(o, venue.commission), size
        else:
            gross, net = odds.lay_gross(o), odds.lay(o, venue.commission)
            at_risk = None if size is None else size * (o - 1)
        return Offer(venue=venue.name, market=market, selection=selection, side=side, covers=cov,
                     gross_odds=gross, net_odds=net, max_stake=None if at_risk is None else at_risk * rate,
                     ts=ts, rule=rule, commission=venue.commission, group=f'{venue.name}:{market}', price=o)
    if side not in ('yes', 'no'):
        raise ValueError(f'{venue.name} quotes yes/no, not {side!r}')
    if not 0 < price < 1:
        raise ValueError(f'share price must be in (0, 1), got {price}')
    cost = odds.share_cost(price, venue.taker_fee)
    return Offer(venue=venue.name, market=market, selection=selection, side=side, covers=cov,
                 gross_odds=1 / price, net_odds=1 / cost, max_stake=None if size is None else size * cost * rate,
                 ts=ts, rule=rule, price=price)


def polymarket_levels(yes_book, no_book=None):
    """(side, ask price, ask size) for buying YES and NO from CLOB /book responses.

    A book looks like {'bids': [{'price': '0.47', 'size': '120'}], 'asks': [...]};
    level order in the response is not relied on.
    """
    def best(levels, pick):
        levels = [(float(lv['price']), float(lv['size'])) for lv in levels or []]
        return pick(levels, key=lambda lv: lv[0]) if levels else None

    out = []
    ask = best(yes_book.get('asks'), min)
    if ask:
        out.append(('yes', *ask))
    if no_book is not None:
        no_ask = best(no_book.get('asks'), min)
    else:
        bid = best(yes_book.get('bids'), max)
        no_ask = (round(1 - bid[0], 6), bid[1]) if bid else None
    if no_ask:
        out.append(('no', *no_ask))
    return out
