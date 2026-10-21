import pytest

from arbscan import replay
from arbscan.engine import Limits

EV = 'e'


def smk(ts, under_bp):
    return {'ts': ts, 'venue': 'smarkets', 'event': EV, 'market': 'ou', 'line': 2.5, 'rule': 'ft90',
            'levels': [{'selection': 'under', 'side': 'back', 'price': under_bp, 'size': 150}]}


def pm(ts):
    return {'ts': ts, 'venue': 'polymarket', 'event': EV, 'market': 'ou', 'line': 2.5, 'rule': 'ft90',
            'levels': [{'selection': 'over', 'side': 'yes', 'price': 0.62, 'size': 400}]}


ARB, NONE = 3571, 3788      # under at 2.80 makes a +0.65% net arb with Over at 0.62; 2.64 does not


def test_synthetic_demo(fixtures):
    # Over at 0.60 on Polymarket arbs against both Smarkets back Under (+0.74%) and lay Over (+0.44%).
    eps = {ep.legs: ep for ep in replay.run(replay.read(fixtures / 'synthetic_ou_demo.jsonl'))}
    assert set(eps) == {('polymarket:yes:over', 'smarkets:back:under'), ('polymarket:yes:over', 'smarkets:lay:over')}
    assert eps[('polymarket:yes:over', 'smarkets:lay:over')].roi_first == pytest.approx(0.0044, abs=5e-5)
    ep = eps[('polymarket:yes:over', 'smarkets:back:under')]
    t0 = replay.parse_ts('2026-10-24T18:00:00Z')
    assert (ep.first_seen - t0, ep.last_seen - t0, ep.closed_at - t0) == (22, 40, 42)
    assert (ep.lifetime_min, ep.lifetime_max, ep.n_obs) == (18, 20, 8)
    assert ep.roi_first == pytest.approx(0.0074, abs=5e-5)
    assert ep.bankroll_first == pytest.approx(397.1, abs=0.1)     # Polymarket's 400 shares bind first


def test_outage_does_not_close():
    # Polymarket goes quiet after t=5; Smarkets moves away at t=40 while Polymarket is stale.
    [ep] = replay.run([pm(0), smk(1, ARB), pm(5), smk(40, NONE), pm(45)], Limits(max_age=30))
    assert (ep.first_seen, ep.last_seen, ep.closed_at) == (1, 5, 45)


def test_open_at_end_is_censored():
    [ep] = replay.run([pm(0), smk(1, ARB), pm(5)])
    assert ep.closed_at is None and ep.lifetime_max is None and ep.lifetime_min == 4
