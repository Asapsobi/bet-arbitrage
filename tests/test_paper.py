import pytest

from arbscan import odds, replay
from arbscan.gates import paper_gate
from arbscan.markets import MarketKey
from arbscan.paper import Attempt, Execution, simulate

ARB = 3571                                    # Smarkets Under at 2.80: +0.65% net against Over at 0.62
PM_LEG, SMK_LEG = 'polymarket:yes:over', 'smarkets:back:under'


def smk(ts, size=150):
    return {'ts': ts, 'venue': 'smarkets', 'event': 'e', 'market': 'ou', 'line': 2.5, 'rule': 'ft90',
            'levels': [{'selection': 'under', 'side': 'back', 'price': ARB, 'size': size}]}


def pm(ts, price=0.62, size=400):
    return {'ts': ts, 'venue': 'polymarket', 'event': 'e', 'market': 'ou', 'line': 2.5, 'rule': 'ft90',
            'levels': [{'selection': 'over', 'side': 'yes', 'price': price, 'size': size}]}


# The plan at detection: Polymarket's 400 shares bind the bankroll.
N_U, N_O = odds.back(odds.from_bp(ARB), 0.02), odds.share(0.62, 0.05)
S = 1 / N_U + 1 / N_O
W_U, W_O = (1 / N_U) / S, (1 / N_O) / S
B = min(150 * 1.30 / W_U, 400 * odds.share_cost(0.62, 0.05) / W_O)
STAKE_U = W_U * B


def one(snaps, **kw):
    [a] = simulate(snaps, ex=Execution(**kw))
    return a, dict(zip(a.legs, a.reasons))


def test_complete_fill_books_the_plan():
    a, why = one([pm(0), smk(1), pm(3), smk(5)])
    assert a.status == 'filled' and a.fills == pytest.approx((1, 1))
    assert a.bankroll == pytest.approx(B) and a.pnl == pytest.approx(B * (1 / S - 1))


def test_moved_leg_is_hedged_at_the_later_price():
    a, why = one([pm(0), smk(1), pm(3, 0.64), smk(5), pm(8, 0.63, size=1000)])
    assert why == {PM_LEG: 'price_moved', SMK_LEG: 'filled'}
    payout = STAKE_U * N_U
    hedge = payout / odds.share(0.63, 0.05)
    assert a.status == 'partial' and not a.open
    assert a.hedge == pytest.approx(hedge)
    assert a.pnl == pytest.approx(payout - STAKE_U - hedge)
    assert a.pnl < 0 < a.planned_pnl


def test_sequential_sends_thinnest_leg_first_and_aborts():
    a, why = one([pm(0), smk(1), pm(3, 0.64), smk(5), pm(8, 0.63, size=1000)], sequential=True)
    assert a.status == 'aborted' and a.pnl == 0
    assert why == {PM_LEG: 'price_moved', SMK_LEG: 'not_sent'}


def test_no_quote_after_arrival_is_a_miss():
    a, why = one([pm(0), smk(1)])
    assert a.status == 'missed' and a.pnl == 0 and set(why.values()) == {'no_quote'}


def test_thin_book_partial_fill_topped_up_at_same_price():
    a, why = one([pm(0), smk(1), pm(3, size=200), smk(5), pm(8, size=1000)])
    assert why == {PM_LEG: 'partial', SMK_LEG: 'filled'}
    assert dict(zip(a.legs, a.fills))[PM_LEG] == pytest.approx(200 / 400)
    assert a.status == 'partial' and a.pnl == pytest.approx(a.planned_pnl)


def test_unhedgeable_gap_stays_open_at_worst_outcome():
    a, _ = one([pm(0), smk(1), pm(3, 0.64), smk(5)])
    assert a.open and a.pnl == pytest.approx(-STAKE_U)
    assert a.pnl_best == pytest.approx(STAKE_U * N_U - STAKE_U)


def test_one_attempt_per_new_arb(fixtures):
    # The demo shows two overlapping arbs on one market for 18-20 s: only the better one is traded, once.
    [a] = simulate(replay.read(fixtures / 'synthetic_ou_demo.jsonl'))
    assert a.status == 'filled' and set(a.legs) == {PM_LEG, SMK_LEG}
    assert a.roi == pytest.approx(0.0074, abs=5e-5)


def att(status, pnl, reasons=('filled', 'filled')):
    return Attempt(MarketKey('e', 'ou', 2.5), (PM_LEG, SMK_LEG), 0.0, 100.0, 0.01, status,
                   (1.0, 1.0), reasons, 0.0, pnl, pnl, False)


def test_paper_gate():
    assert paper_gate(None).verdict == 'N/A'
    assert paper_gate([att('filled', 2.0)] * 9 + [att('partial', -1.0)]).verdict == 'GO'
    assert paper_gate([att('filled', 1.0)] * 8 + [att('partial', -3.0)] * 2).verdict == 'GREY'      # 80% filled
    nq = paper_gate([att('filled', 1.0)] * 7 + [att('missed', 0.0, ('no_quote', 'no_quote'))] * 3)
    assert nq.verdict == 'NO-GO' and 'poll faster' in nq.note
    assert paper_gate([att('filled', 1.0)] * 9 + [att('partial', -5.0)]).verdict == 'GREY'         # loss 56% of gross
