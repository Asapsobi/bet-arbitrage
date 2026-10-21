import pytest

from arbscan.markets import MarketKey, covers, outcomes, partitions
from arbscan.venues import VENUES, offer, polymarket_levels

M = MarketKey('e', '1x2')


def test_partitions():
    assert len(partitions(('home', 'draw', 'away'))) == 4
    assert partitions(('over', 'under')) == [(frozenset({'over'}), frozenset({'under'}))]


def test_covers():
    assert covers(M, 'home', 'lay') == {'draw', 'away'}
    assert covers(M, 'home', 'no') == {'draw', 'away'}
    assert covers(M, 'draw', 'back') == {'draw'}


def test_lines():
    assert outcomes(MarketKey('e', 'ou', 2.5)) == ('over', 'under')
    assert outcomes(MarketKey('e', 'ah', -1)) == ('home', 'away')
    with pytest.raises(ValueError, match='quarter'):
        outcomes(MarketKey('e', 'ah', -0.25))
    with pytest.raises(ValueError, match='needs a line'):
        outcomes(MarketKey('e', 'ou'))


def test_exchange_lay_depth_is_liability():
    o = offer(VENUES['smarkets'], M, 'away', 'lay', 2941, 100, 0.0)    # lay 100 GBP of backer stake at 3.40
    assert o.covers == {'home', 'draw'}
    assert o.max_stake == pytest.approx(100 * (10000 / 2941 - 1) * 1.30)   # liability, in USD


def test_prediction_market_depth_includes_fee():
    o = offer(VENUES['polymarket'], M, 'home', 'yes', 0.5, 100, 0.0)
    assert o.max_stake == pytest.approx(100 * (0.5 + 0.05 * 0.25))


def test_wrong_side_for_venue():
    with pytest.raises(ValueError):
        offer(VENUES['smarkets'], M, 'home', 'yes', 4587, None, 0.0)
    with pytest.raises(ValueError):
        offer(VENUES['polymarket'], M, 'home', 'back', 0.48, None, 0.0)


def test_polymarket_levels_ignore_level_order():
    yes = {'bids': [{'price': '0.45', 'size': '10'}, {'price': '0.47', 'size': '120'}],
           'asks': [{'price': '0.50', 'size': '5'}, {'price': '0.48', 'size': '80'}]}
    assert polymarket_levels(yes) == [('yes', 0.48, 80.0), ('no', 0.53, 120.0)]
    no = {'asks': [{'price': '0.54', 'size': '9'}]}
    assert polymarket_levels(yes, no) == [('yes', 0.48, 80.0), ('no', 0.54, 9.0)]
