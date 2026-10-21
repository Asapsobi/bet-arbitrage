"""The engine must reproduce the Bayern-Arsenal figures in docs/08 (net-of-fee table and case A)."""
import pytest

from arbscan import odds, replay
from arbscan.engine import Limits, scan
from arbscan.markets import MarketKey

EV = '2026-10-21:bayern-munich-v-arsenal'
X12, OU = MarketKey(EV, '1x2'), MarketKey(EV, 'ou', 2.5)
WIDE = Limits(max_age=120, max_skew=120, min_roi=-1)     # the two venues were read a minute apart


def combos(fixtures, market, limits=WIDE):
    books, now = replay.books_at(replay.read(fixtures / 'bayern_arsenal_2026-10-21.jsonl'))
    return {frozenset(o.id for o in opp.legs): opp for opp in scan(market, books.offers(market), now, limits)}


def stakes(opp, bankroll=1000):
    return {o.id: round(w * bankroll, 2) for o, w in zip(opp.legs, opp.weights)}


def test_formulas():
    assert odds.from_bp(4587) == pytest.approx(2.180, abs=1e-3)
    assert odds.back(2.10, 0.05) == pytest.approx(2.045)
    S = 1 / odds.back(odds.from_bp(4587), 0.02) + 1 / odds.share(0.53, 0.05)
    assert S == pytest.approx(1.0062, abs=1e-4)
    assert 1000 * (1 / S - 1) == pytest.approx(-6.14, abs=0.01)
    assert (odds.share_cost(0.25, 0.05) - 0.25) / 0.25 == pytest.approx(0.0375)   # fee: 3.75% of stake at 0.25


def test_combination_b(fixtures):
    b = combos(fixtures, X12)[frozenset({'smarkets:back:home', 'polymarket:no:home'})]
    assert b.roi == pytest.approx(-0.0061, abs=5e-5)
    assert b.roi_per_leg == pytest.approx(b.roi)
    assert stakes(b) == {'smarkets:back:home': 460.87, 'polymarket:no:home': 539.13}


def test_combination_b2(fixtures):
    b2 = combos(fixtures, X12)[frozenset({'polymarket:yes:away', 'smarkets:lay:away'})]
    assert b2.roi == pytest.approx(-0.0103, abs=5e-5)
    assert stakes(b2) == {'polymarket:yes:away': 297.21, 'smarkets:lay:away': 702.79}


def test_combination_a_market_level_commission(fixtures):
    a = combos(fixtures, X12)[frozenset({'smarkets:back:home', 'smarkets:back:draw', 'polymarket:yes:away'})]
    assert a.roi_per_leg == pytest.approx(-0.0175, abs=5e-5)
    assert a.roi == pytest.approx(-0.0130, abs=5e-5)
    assert {k: round(v, 1) for k, v in stakes(a).items()} == {
        'smarkets:back:home': 455.4, 'smarkets:back:draw': 248.2, 'polymarket:yes:away': 296.4}


def test_combination_c(fixtures):
    c = combos(fixtures, OU)[frozenset({'smarkets:back:under', 'polymarket:yes:over'})]
    assert c.roi == pytest.approx(-0.0151, abs=5e-5)
    assert stakes(c) == {'smarkets:back:under': 377.77, 'polymarket:yes:over': 622.23}


def test_market_level_never_worse_than_per_leg(fixtures):
    for opp in [*combos(fixtures, X12).values(), *combos(fixtures, OU).values()]:
        assert opp.roi >= opp.roi_per_leg - 1e-12


def test_no_arb_after_fees(fixtures):
    assert combos(fixtures, X12, Limits(max_age=120, max_skew=120)) == {}
    assert combos(fixtures, OU, Limits(max_age=120, max_skew=120)) == {}


def test_back_and_lay_of_one_selection_never_paired(fixtures):
    for ids in combos(fixtures, X12):
        picks = [i.split(':')[0] + ':' + i.split(':')[2] for i in ids]
        assert len(set(picks)) == len(picks)


def test_stale_venue_dropped(fixtures):
    # At 09:07 the 09:06 Smarkets quotes are 60 s old; with a 30 s limit only Polymarket-only combos remain.
    c = combos(fixtures, X12, Limits(max_age=30, min_roi=-1))
    assert c and all(opp.venues == ('polymarket',) for opp in c.values())
    a3 = c[frozenset({'polymarket:yes:home', 'polymarket:yes:draw', 'polymarket:yes:away'})]
    assert a3.roi == pytest.approx(-0.0496, abs=5e-5)
