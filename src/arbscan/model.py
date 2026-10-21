"""Offers (positions available now) and opportunities (arbs built from them)."""
from __future__ import annotations

from dataclasses import dataclass

from .markets import MarketKey


@dataclass(frozen=True)
class Offer:
    """A position you could take now, normalized to a back on `covers`.

    gross_odds and net_odds are decimal payout per unit at risk when the
    position wins, before and after the venue's fee. max_stake is the at-risk
    amount fillable at this price in the base currency; None when the feed
    does not say.
    """
    venue: str
    market: MarketKey
    selection: str
    side: str
    covers: frozenset[str]
    gross_odds: float
    net_odds: float
    max_stake: float | None
    ts: float
    rule: str = 'unknown'          # settlement rule key, e.g. 'ft90'
    commission: float = 0.0        # charged on the net winnings of `group`
    group: str | None = None       # venue market whose net winnings carry the commission
    price: float | None = None     # as quoted, for display: decimal odds, or share price on prediction markets

    @property
    def id(self):
        return f'{self.venue}:{self.side}:{self.selection}'

    def __str__(self):
        return f'{self.venue} {self.side} {self.selection} @{self.price:.4g}'


@dataclass(frozen=True)
class Opportunity:
    market: MarketKey
    legs: tuple[Offer, ...]
    weights: tuple[float, ...]     # share of bankroll per leg, equal payout in every outcome
    roi: float                     # return on bankroll; commission charged per market where legs share one
    roi_per_leg: float             # 1/S - 1 with commission charged per leg (never higher than roi)
    max_bankroll: float | None     # largest bankroll fillable at these prices; None if any leg's depth is unknown
    ts: float
    skew: float                    # seconds between the oldest and newest leg quote
    flags: frozenset[str] = frozenset()

    @property
    def key(self):
        return f'{self.market}|' + ';'.join(sorted(o.id for o in self.legs))

    @property
    def venues(self):
        return tuple(sorted({o.venue for o in self.legs}))
