"""Turns repeated scans into episodes: first and last sighting of each arb.

Feeds the lifetime (G4) and depth (G3) gates. An episode closes only when every
venue in it has a fresh snapshot that no longer shows it, so a feed outage is
never mistaken for the arb disappearing.
"""
from __future__ import annotations

from dataclasses import dataclass

from .markets import MarketKey


@dataclass
class Episode:
    key: str
    market: MarketKey
    legs: tuple[str, ...]
    venues: tuple[str, ...]
    first_seen: float
    last_seen: float
    roi_first: float
    roi_max: float
    roi_min: float
    bankroll_first: float | None
    bankroll_max: float | None
    flags: frozenset[str]
    n_obs: int = 1
    closed_at: float | None = None     # first fresh look without it; None = still open when data ended

    @property
    def lifetime_min(self):
        """Seconds it was certainly alive: first to last sighting."""
        return self.last_seen - self.first_seen

    @property
    def lifetime_max(self):
        """Seconds it was at most alive: first sighting to the first look without it."""
        return None if self.closed_at is None else self.closed_at - self.first_seen


class Tracker:
    def __init__(self):
        self.open = {}             # MarketKey -> {opportunity key: Episode}

    def observe(self, market, now, opportunities, fresh_venues):
        """Record one scan of `market`; return the episodes it closed."""
        live = self.open.setdefault(market, {})
        seen = set()
        for opp in opportunities:
            seen.add(opp.key)
            ep = live.get(opp.key)
            if ep is None:
                live[opp.key] = Episode(
                    opp.key, market, tuple(sorted(o.id for o in opp.legs)), opp.venues, now, now,
                    opp.roi, opp.roi, opp.roi, opp.max_bankroll, opp.max_bankroll, opp.flags)
                continue
            ep.last_seen, ep.n_obs = now, ep.n_obs + 1
            ep.roi_max, ep.roi_min = max(ep.roi_max, opp.roi), min(ep.roi_min, opp.roi)
            if opp.max_bankroll is not None:
                ep.bankroll_max = max(ep.bankroll_max or 0.0, opp.max_bankroll)
            ep.flags = ep.flags | opp.flags
        closed = [ep for key, ep in live.items() if key not in seen and set(ep.venues) <= fresh_venues]
        for ep in closed:
            ep.closed_at = now
            del live[ep.key]
        return closed

    def flush(self):
        """Hand back every open episode; closed_at stays None because the data ended first."""
        out = [ep for live in self.open.values() for ep in live.values()]
        self.open = {}
        return out
