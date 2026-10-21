"""Paper trading: what each detected arb would have filled, given latency and the books that followed.

When an arb is first seen, every leg goes out as a limit order at the detected
price. A leg is judged against the first snapshot of its venue after it would
arrive, never the one it was detected on (docs/08: the quotes after your
delay). Gaps left by legs that miss are topped up at the best price available
a little later; whatever cannot be covered stays open and is booked at its
worst outcome. Detection uses only the past; fills use what came next.

Not modelled: queue position, and our own fills taking liquidity from later
snapshots. Partial outcomes charge commission per leg, which is conservative.
"""
from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

from .books import Books
from .engine import Limits, scan
from .lifecycle import Tracker
from .markets import MarketKey
from .replay import parse_ts, to_offers
from .venues import VENUES

FULL = 1 - 1e-6        # a leg that fills this share of its stake counts as filled


@dataclass(frozen=True)
class Execution:
    latency: float = 1.0           # seconds from decision to a venue
    venue_latency: dict = field(default_factory=dict)   # per-venue override, e.g. {'polymarket': 2.0}
    timeout: float = 10.0          # a leg that sees no venue snapshot this long after arriving is missed
    hedge_delay: float = 2.0       # seconds after the last fill before topping up gaps
    cap: float = 1000.0            # max bankroll per arb, USD
    size_fraction: float = 1.0     # share of the quoted fillable bankroll to use
    sequential: bool = False       # send the thinnest leg first, the rest only once it fills
    tolerance: float = 0.0         # accept net odds this much worse than detected, relative
    cooldown: float = 30.0         # at most one attempt per market in this many seconds
    min_roi: float = 0.005         # trade arbs at or above this net return

    def lat(self, venue):
        return self.venue_latency.get(venue, self.latency)


@dataclass(frozen=True)
class Attempt:
    market: MarketKey
    legs: tuple[str, ...]
    t0: float                      # detection time
    bankroll: float                # planned
    roi: float                     # planned
    status: str                    # 'filled', 'partial', 'missed' or 'aborted'
    fills: tuple[float, ...]       # share of each leg's planned stake that filled
    reasons: tuple[str, ...]       # per leg: filled, partial, price_moved, no_quote, not_sent
    hedge: float                   # stake spent topping up gaps
    pnl: float                     # realized; the worst outcome when exposure is left open
    pnl_best: float
    open: bool                     # exposure could not be fully hedged

    @property
    def planned_pnl(self):
        return self.bankroll * self.roi


class Tape:
    """Every venue snapshot per market, in time order, to look up what a leg meets on arrival."""

    def __init__(self):
        self._ts, self._offers = {}, {}

    def add(self, venue, market, ts, offers):
        self._ts.setdefault((venue, market), []).append(ts)
        self._offers.setdefault((venue, market), []).append(offers)

    def venues(self, market):
        return sorted(v for v, m in self._ts if m == market)

    def first_after(self, venue, market, t, timeout):
        ts = self._ts.get((venue, market), [])
        i = bisect_left(ts, t)
        if i < len(ts) and ts[i] <= t + timeout:
            return ts[i], self._offers[(venue, market)][i]
        return None


def _fill(leg, stake, arrive, tape, ex):
    """(filled stake, snapshot time, reason) for a limit order at the leg's detected price."""
    snap = tape.first_after(leg.venue, leg.market, arrive, ex.timeout)
    if snap is None:
        return 0.0, None, 'no_quote'
    ts, offers = snap
    match = [o for o in offers if o.selection == leg.selection and o.side == leg.side
             and o.net_odds >= leg.net_odds * (1 - ex.tolerance)]
    avail = math.inf if any(o.max_stake is None for o in match) else sum(o.max_stake for o in match)
    filled = min(stake, avail)
    if filled <= 0:
        return 0.0, ts, 'price_moved'
    return filled, ts, 'filled' if filled >= stake * FULL else 'partial'


def execute(opp, t0, tape, ex):
    k, legs = len(opp.legs), opp.legs
    bankroll = ex.cap if opp.max_bankroll is None else min(ex.cap, opp.max_bankroll * ex.size_fraction)
    plan = [w * bankroll for w in opp.weights]
    stakes, fills, times, reasons = list(plan), [0.0] * k, [None] * k, ['not_sent'] * k

    def attempt(status, pnl=0.0, pnl_best=None, hedge=0.0, open_=False):
        return Attempt(opp.market, tuple(o.id for o in legs), t0, bankroll, opp.roi, status,
                       tuple(f / p for f, p in zip(fills, plan)), tuple(reasons), hedge, pnl,
                       pnl if pnl_best is None else pnl_best, open_)

    send = [(i, t0) for i in range(k)]
    if ex.sequential:
        first = min(range(k), key=lambda i: 0.0 if legs[i].max_stake is None else legs[i].max_stake / plan[i])
        fills[first], times[first], reasons[first] = _fill(legs[first], plan[first],
                                                           t0 + ex.lat(legs[first].venue), tape, ex)
        if fills[first] == 0:
            return attempt('aborted')
        stakes = [s * fills[first] / plan[first] for s in plan]
        send = [(i, times[first]) for i in range(k) if i != first]
    for i, t in send:
        fills[i], times[i], reasons[i] = _fill(legs[i], stakes[i], t + ex.lat(legs[i].venue), tape, ex)

    share = [f / p for f, p in zip(fills, plan)]
    if sum(fills) == 0:
        return attempt('missed')
    if min(share) > 0 and max(share) - min(share) < 1e-6:     # balanced, maybe smaller than planned: no leg risk
        return attempt('filled', sum(fills) * opp.roi)

    # Leg i alone pays on its block; top every block up to the best-covered one.
    payout = [f * o.net_odds for f, o in zip(fills, legs)]
    cost, hedge, target = sum(fills), 0.0, max(payout)
    t_h = max(t for t in times if t is not None) + ex.hedge_delay
    for b, leg in enumerate(legs):
        need = target - payout[b]
        if need <= 1e-9:
            continue
        offers = []
        for venue in tape.venues(opp.market):
            snap = tape.first_after(venue, opp.market, t_h, ex.timeout)
            if snap:
                offers += [o for o in snap[1] if o.covers == leg.covers]
        for o in sorted(offers, key=lambda o: -o.net_odds):
            take = min(need / o.net_odds, math.inf if o.max_stake is None else o.max_stake)
            payout[b] += take * o.net_odds
            cost, hedge, need = cost + take, hedge + take, need - take * o.net_odds
            if need <= 1e-9:
                break
    pnls = [p - cost for p in payout]
    return attempt('partial', min(pnls), max(pnls), hedge, max(pnls) - min(pnls) > 0.01)


def simulate(snapshots, limits=Limits(), ex=Execution(), venues=VENUES):
    """One attempt per new arb (best first, per-market cooldown), judged on the snapshots that followed."""
    parsed = [to_offers(s, venues) for s in sorted(snapshots, key=lambda s: parse_ts(s['ts']))]
    tape = Tape()
    for ts, venue, market, _, offers in parsed:
        tape.add(venue, market, ts, offers)
    books, tracker, last, out = Books(), Tracker(), {}, []
    for ts, venue, market, _, offers in parsed:
        books.update(venue, market, ts, offers)
        opps = scan(market, books.offers(market), ts, limits)
        live = tracker.open.get(market, {})
        new = [o for o in opps if o.key not in live and o.roi >= ex.min_roi and 'palp' not in o.flags]
        tracker.observe(market, ts, opps, books.fresh_venues(market, ts, limits.max_age))
        if new and ts - last.get(market, -math.inf) >= ex.cooldown:
            last[market] = ts
            out.append(execute(new[0], ts, tape, ex))
    return out
