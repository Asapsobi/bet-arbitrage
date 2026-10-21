"""Go/no-go gates G1-G6 from docs/08-research-report-fa.md, scored on logged episodes.

Episodes are per leg combination. Overlapping episodes on the same market are
one chance to trade, so G2-G4 and G6 count clusters of them, not combinations.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median


@dataclass(frozen=True)
class Gate:
    gate: str
    metric: str
    value: str
    go_if: str
    verdict: str                  # GO, NO-GO, GREY, MANUAL or N/A
    note: str = ''


@dataclass
class Cluster:
    market: object
    start: float
    last: float
    closed: float | None
    roi: float
    depth: float | None


def clusters(episodes, min_roi=0.005, require_verified_rules=False):
    """Merge qualifying episodes that overlap in time on the same market."""
    keep = [e for e in episodes if e.roi_first >= min_roi and 'palp' not in e.flags
            and not (require_verified_rules and 'rules_unverified' in e.flags)]
    out = []
    for market in sorted({e.market for e in keep}, key=str):
        cur = None
        for e in sorted((e for e in keep if e.market == market), key=lambda e: e.first_seen):
            if cur and e.first_seen <= cur.last:
                cur.last = max(cur.last, e.last_seen)
                cur.closed = None if cur.closed is None or e.closed_at is None else max(cur.closed, e.closed_at)
                cur.roi = max(cur.roi, e.roi_first)
                if e.bankroll_first is not None:
                    cur.depth = max(cur.depth or 0.0, e.bankroll_first)
                continue
            cur = Cluster(market, e.first_seen, e.last_seen, e.closed_at, e.roi_first, e.bankroll_first)
            out.append(cur)
    return out


def _day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date()


def paper_gate(attempts):
    """Paper-trading gate: share of arbs filled in full, and what the incomplete ones cost against the rest."""
    go_if = '>= 90% filled, incomplete loss < 25% of gross'
    if not attempts:
        return Gate('G5 simulated fills', 'complete fills / attempts', '-', go_if, 'N/A',
                    'run arbscan paper first' if attempts is None else 'no arbs to trade')
    full = [a for a in attempts if a.status == 'filled']
    rate = len(full) / len(attempts)
    gross = sum(a.pnl for a in full)
    loss = -sum(a.pnl for a in attempts if a.status != 'filled')
    ratio = loss / gross if gross > 0 else math.inf if loss > 0 else 0.0
    no_quote = sum(r == 'no_quote' for a in attempts for r in a.reasons)
    left_open = sum(a.open for a in attempts)
    notes = [f'{len(attempts)} attempts']
    if no_quote:
        notes.append(f'{no_quote} legs saw no quote within the timeout: poll faster or stream')
    if left_open:
        notes.append(f'{left_open} left open, booked at their worst outcome')
    shown = 'no gross profit' if ratio == math.inf else f'{ratio:.0%} of gross'
    return Gate('G5 simulated fills', 'complete fills / attempts; incomplete loss', f'{rate:.0%}; {shown}', go_if,
                'GO' if rate >= 0.9 and ratio < 0.25 else 'NO-GO' if rate < 0.75 else 'GREY', '; '.join(notes))


def g6_needs(fixed_cost, bankroll, roi):
    """Arbs a day for G6 (twice the fixed cost) at this bankroll per arb and net ROI: 2C / (30 B r)."""
    return 2 * fixed_cost / (30 * bankroll * roi)


def evaluate(episodes, window, poll_gaps, *, attempts=None, min_roi=0.005, fixed_cost=160.0, cap=None,
             latency=2.0, require_verified_rules=False):
    g1 = Gate('G1 legal', 'written sign-off for every venue in the operator\'s country', '-',
              'all venues in the strategy allowed', 'MANUAL', 'not computable; one missing venue is a stop')
    g5 = paper_gate(attempts)
    if window is None:
        def na(name):
            return Gate(name, '-', '-', '-', 'N/A', 'no snapshots')
        return [g1, na('G2 frequency'), na('G3 depth'), na('G4 lifetime'), g5, na('G6 economics')]

    cl = clusters(episodes, min_roi, require_verified_rules)
    lo, hi = window
    span_days = (hi - lo) / 86400
    thin = span_days < 1           # too little data to say anything per day or per month
    span = f'{span_days * 1440:.0f} min' if span_days < 1 / 24 else f'{span_days * 24:.1f} h'
    short = f'only {span} of data; the gate wants 30 days' if span_days < 7 else ''

    days = [_day(lo) + timedelta(d) for d in range((_day(hi) - _day(lo)).days + 1)]
    per_day = {d: 0 for d in days}
    for c in cl:
        per_day[_day(c.start)] += 1
    freq = median(per_day.values())
    depths = [c.depth for c in cl if c.depth is not None]
    # G2 must be enough for G6 at the measured depth and return, not just 3 a day (docs/08, gates).
    need, why = 3.0, 'G6 floor unknown without depth'
    if depths:
        b = median(d if cap is None else min(d, cap) for d in depths)
        r = median(c.roi for c in cl if c.depth is not None)
        need = max(3.0, g6_needs(fixed_cost, b, r))
        why = f'G6 needs {g6_needs(fixed_cost, b, r):.1f}/day at ${b:,.0f} and {r:.2%}'
    g2 = Gate('G2 frequency', f'arbs/day with net ROI >= {min_roi:.2%}, median', f'{freq:g}', f'>= {need:.1f}/day',
              'N/A' if thin else 'GO' if freq >= need else 'NO-GO' if freq < 1 else 'GREY',
              '; '.join(n for n in (short, why if cl else '') if n))

    if depths:
        d = median(depths)
        g3 = Gate('G3 depth', 'bankroll fillable at quoted prices, median', f'${d:,.0f}', '>= $200',
                  'GO' if d >= 200 else 'NO-GO' if d < 50 else 'GREY',
                  f'{len(cl) - len(depths)} of {len(cl)} arbs without depth' if len(depths) < len(cl) else '')
    else:
        g3 = Gate('G3 depth', 'bankroll fillable at quoted prices, median', '-', '>= $200', 'N/A',
                  'feeds gave no sizes' if cl else 'no qualifying arbs')

    poll = median(poll_gaps) if poll_gaps else None
    if cl:
        lower = median(c.last - c.start for c in cl)
        uppers = [c.closed - c.start for c in cl if c.closed is not None]
        upper = median(uppers) if uppers else None
        need = 2.0 if poll is not None and poll <= 1 else 10.0
        verdict = ('GO' if lower >= need else 'NO-GO' if upper is not None and upper < latency else 'GREY')
        notes = []
        if upper is not None and poll is not None and upper <= poll:
            notes.append('most arbs were gone by the next poll, so lifetimes are not resolved: poll faster or stream')
        if poll is not None:
            notes.append(f'median poll gap {poll:.1f} s')
        g4 = Gate('G4 lifetime', 'seconds alive, median (certain / at most)',
                  f'{lower:.1f} / {"-" if upper is None else f"{upper:.1f}"}', f'>= {need:g} s', verdict,
                  '; '.join(notes))
    else:
        g4 = Gate('G4 lifetime', 'seconds alive, median', '-', '>= 10 s', 'N/A', 'no qualifying arbs')

    if thin:
        g6 = Gate('G6 economics', 'projected net profit per month', '-', f'>= ${2 * fixed_cost:,.0f}', 'N/A',
                  short + '; no monthly projection from under a day')
    else:
        profit = sum(c.roi * (c.depth if cap is None else min(c.depth, cap)) for c in cl if c.depth is not None)
        monthly = profit / span_days * 30
        g6 = Gate('G6 economics', 'projected net profit per month', f'${monthly:,.0f}',
                  f'>= ${2 * fixed_cost:,.0f} (2x fixed cost)',
                  'GO' if monthly >= 2 * fixed_cost else 'NO-GO' if monthly < fixed_cost else 'GREY',
                  '; '.join(n for n in (short, 'arbs without depth count as zero' if len(depths) < len(cl) else '')
                            if n))
    return [g1, g2, g3, g4, g5, g6]
