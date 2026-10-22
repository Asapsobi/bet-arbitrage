"""Randomized checks of the stake solver and the engine against payouts computed from first principles.

Each case draws random prices, venues and commission rates (fixed seeds, so failures reproduce) and
checks the result by settling every outcome by hand: exchange commission on each market's net win,
prediction-market fees already in the price.
"""
import random
from collections import defaultdict

import pytest

from arbscan import odds
from arbscan.engine import Limits, scan
from arbscan.markets import MarketKey, covers, outcomes, partitions
from arbscan.model import Offer
from arbscan.payoff import equal_payout
from arbscan.venues import Venue, offer

M3, M2 = MarketKey('e', '1x2'), MarketKey('e', 'ou', 2.5)


def settle(legs, stakes, outcome):
    """Profit if `outcome` happens: commission on each exchange market's net win, fees in prediction prices."""
    total, markets = 0.0, defaultdict(float)
    for o, s in zip(legs, stakes):
        if o.group:
            markets[(o.group, o.commission)] += s * (o.gross_odds - 1) if outcome in o.covers else -s
        else:
            total += s * (o.net_odds - 1) if outcome in o.covers else -s
    return total + sum(net - c * max(0.0, net) for (_, c), net in markets.items())


def random_legs(rng, market):
    """One leg per block of a random partition, each on a random venue: two exchanges or a prediction market."""
    venues = {'exA': rng.uniform(0, 0.08), 'exB': rng.uniform(0, 0.08), 'pm': rng.uniform(0, 0.1)}
    legs = []
    for block in rng.choice(partitions(outcomes(market))):
        v = rng.choice(list(venues))
        if v == 'pm':
            p = rng.uniform(0.03, 0.97)
            legs.append(Offer(v, market, '-', 'yes', block, 1 / p, 1 / odds.share_cost(p, venues[v]), None, 0.0))
        else:
            gross = rng.uniform(1.02, 15.0)
            legs.append(Offer(v, market, '-', 'back', block, gross, odds.back(gross, venues[v]), None, 0.0,
                              commission=venues[v], group=f'{v}:{market}'))
    return legs


@pytest.mark.parametrize('seed', range(5))
def test_solver_pays_the_same_in_every_outcome(seed):
    rng, solved = random.Random(seed), 0
    for _ in range(2000):
        market = rng.choice((M3, M2))
        legs = random_legs(rng, market)
        per_leg = 1 / sum(1 / o.net_odds for o in legs) - 1
        res = equal_payout(legs)
        if res is None:
            # the engine then falls back to per-leg stakes, which must never pay less than the per-leg return
            S = sum(1 / o.net_odds for o in legs)
            stakes = [(1 / o.net_odds) / S for o in legs]
            assert all(settle(legs, stakes, out) >= per_leg - 1e-12 for out in outcomes(market))
            continue
        solved += 1
        stakes, roi = res
        assert min(stakes) > 0 and sum(stakes) == pytest.approx(1)
        for out in outcomes(market):
            assert settle(legs, stakes, out) == pytest.approx(roi, abs=1e-9)
        assert roi >= per_leg - 1e-12                      # commission once per market is never dearer
        if len({o.group for o in legs if o.group}) == sum(1 for o in legs if o.group):
            assert roi == pytest.approx(per_leg, abs=1e-12)   # no shared market: both rules agree
    assert solved > 1900                                   # the fallback stays rare


@pytest.mark.parametrize('seed', range(3))
def test_engine_weights_settle_to_the_reported_roi(seed):
    rng = random.Random(100 + seed)
    venues = {'smarkets': Venue('smarkets', commission=0.02), 'betfair': Venue('betfair', commission=0.05),
              'polymarket': Venue('polymarket', taker_fee=0.05, price='prob')}
    checked = 0
    for _ in range(150):
        market = rng.choice((M3, M2))
        outs = outcomes(market)
        fair = [rng.uniform(0.5, 3.0) for _ in outs]
        fair = [x / sum(fair) for x in fair]
        offers = []
        for name, v in venues.items():
            for sel, p in zip(outs, fair):
                q = min(0.97, max(0.03, p * rng.uniform(0.95, 1.08)))       # noisy, sometimes generous
                if v.exchange:
                    offers += [offer(v, market, sel, 'back', 1 / q, rng.uniform(10, 500), 0.0),
                               offer(v, market, sel, 'lay', 1 / (q * rng.uniform(0.9, 0.99)), rng.uniform(10, 500), 0.0)]
                else:
                    offers += [offer(v, market, sel, 'yes', round(q, 2), rng.uniform(10, 500), 0.0),
                               offer(v, market, sel, 'no', round(min(0.97, 1 - q * rng.uniform(0.9, 0.99)), 2),
                                     rng.uniform(10, 500), 0.0)]
        for opp in scan(market, offers, 0.0, Limits(min_roi=-1.0, palp_roi=1.0)):
            checked += 1
            assert sorted(o for leg in opp.legs for o in leg.covers) == sorted(outs)   # each outcome exactly once
            for out in outs:
                assert settle(opp.legs, opp.weights, out) == pytest.approx(opp.roi, abs=1e-9)
            if opp.max_bankroll is not None:                 # the binding leg is filled exactly, none overfilled
                fills = [w * opp.max_bankroll / o.max_stake for o, w in zip(opp.legs, opp.weights)]
                assert max(fills) == pytest.approx(1.0)
    assert checked > 1000


def test_covers_are_complements():
    for market in (M3, M2):
        for sel in outcomes(market):
            assert covers(market, sel, 'back') | covers(market, sel, 'lay') == set(outcomes(market))
            assert not covers(market, sel, 'yes') & covers(market, sel, 'no')
