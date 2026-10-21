"""Arb detection on net-of-fee odds for one market."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .markets import outcomes, partitions
from .model import Opportunity
from .payoff import equal_payout


@dataclass(frozen=True)
class Limits:
    max_age: float = 30.0          # seconds; older quotes are ignored
    max_skew: float = 30.0         # seconds between the oldest and newest leg quote
    min_roi: float = 0.0           # keep combinations returning more than this (-1 shows near misses)
    palp_roi: float = 0.03         # flag anything above as a probable error price (report: 3-5%)
    verified_rules: frozenset[tuple[str, str, str]] = frozenset()   # (venue, market, rule) checked by hand


def _valid(legs, limits):
    ts = [o.ts for o in legs]
    if max(ts) - min(ts) > limits.max_skew:
        return False
    picks = [(o.venue, o.selection) for o in legs]
    return len(set(picks)) == len(picks)     # back and lay of one selection on one venue only pays the spread


def scan(market, offers, now, limits=Limits()):
    """Every combination with roi above limits.min_roi, best first.

    Legs must share a settlement rule and cover each outcome exactly once.
    Each combination is returned on its own so its lifetime can be tracked
    even while another venue briefly has the better price for one block.
    """
    fresh = [o for o in offers if o.market == market and now - o.ts <= limits.max_age]
    found = []
    for rule in sorted({o.rule for o in fresh}):
        pool = [o for o in fresh if o.rule == rule]
        for part in partitions(outcomes(market)):
            choices = [[o for o in pool if o.covers == block] for block in part]
            for legs in product(*choices):
                if not _valid(legs, limits):
                    continue
                S = sum(1 / o.net_odds for o in legs)
                # Per-leg commission is never cheaper than per-market, so it is the safe fallback.
                weights, roi = equal_payout(legs) or ([(1 / o.net_odds) / S for o in legs], 1 / S - 1)
                if roi <= limits.min_roi:
                    continue
                depth = [o.max_stake / w for o, w in zip(legs, weights) if o.max_stake is not None]
                flags = set()
                if roi > limits.palp_roi:
                    flags.add('palp')
                if any((o.venue, market.market, o.rule) not in limits.verified_rules for o in legs):
                    flags.add('rules_unverified')
                if len(depth) < len(legs):
                    flags.add('depth_unknown')
                ts = [o.ts for o in legs]
                found.append(Opportunity(market, legs, tuple(weights), roi, 1 / S - 1,
                                         min(depth) if len(depth) == len(legs) else None,
                                         now, max(ts) - min(ts), frozenset(flags)))
    return sorted(found, key=lambda o: -o.roi)
