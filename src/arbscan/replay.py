"""Replay recorded snapshots through the scanner.

Input is JSON lines, one snapshot of one venue's book for one market per line:

    {"ts": "2026-10-21T09:06:00Z", "venue": "smarkets", "event": "2026-10-21:bayern-munich-v-arsenal",
     "market": "1x2", "line": null, "rule": "ft90",
     "levels": [{"selection": "home", "side": "back", "price": 4587, "size": null}, ...]}

Prices are as the venue quotes them (see venues.offer for sides and sizes).
Live collectors write the same format, so a recorded day replays exactly.
"""
from __future__ import annotations

import json
from datetime import datetime

from .books import Books
from .engine import Limits, scan
from .lifecycle import Tracker
from .markets import MarketKey
from .venues import VENUES, offer


def parse_ts(v):
    if isinstance(v, (int, float)):
        return float(v)
    return datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp()


def read(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def to_offers(snap, venues=VENUES):
    """(ts, venue name, market, rule, offers) for one snapshot."""
    ts, venue = parse_ts(snap['ts']), venues[snap['venue']]
    market = MarketKey(snap['event'], snap['market'], snap.get('line'))
    rule = snap.get('rule', 'unknown')
    offers = [offer(venue, market, lv['selection'], lv['side'], lv['price'], lv.get('size'), ts, rule)
              for lv in snap['levels']]
    return ts, venue.name, market, rule, offers


def books_at(snapshots, at=None, venues=VENUES):
    """Books as they stood at time `at` (default: the last snapshot), and that time."""
    books, now = Books(), None
    for snap in sorted(snapshots, key=lambda s: parse_ts(s['ts'])):
        ts, venue, market, _, offers = to_offers(snap, venues)
        if at is not None and ts > at:
            break
        books.update(venue, market, ts, offers)
        now = ts
    return books, now if at is None else at


def run(snapshots, limits=Limits(), venues=VENUES, store=None):
    """Scan after every snapshot and return every episode, closed or still open at the end."""
    books, tracker, episodes = Books(), Tracker(), []
    for n, snap in enumerate(sorted(snapshots, key=lambda s: parse_ts(s['ts']))):
        try:
            ts, venue, market, rule, offers = to_offers(snap, venues)
        except (KeyError, ValueError) as e:
            raise ValueError(f'snapshot {n} ({snap.get("venue")} {snap.get("event")}): {e}') from e
        books.update(venue, market, ts, offers)
        if store:
            store.add_snapshot(ts, venue, market, rule, snap['levels'])
        opps = scan(market, books.offers(market), ts, limits)
        episodes += tracker.observe(market, ts, opps, books.fresh_venues(market, ts, limits.max_age))
    episodes += tracker.flush()
    if store:
        for ep in episodes:
            store.add_episode(ep)
        store.commit()
    return episodes
