"""SQLite store for raw snapshots and closed episodes. The schema ports to Postgres as is."""
from __future__ import annotations

import json
import sqlite3

from .lifecycle import Episode
from .markets import MarketKey

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ts REAL NOT NULL, venue TEXT NOT NULL, event TEXT NOT NULL, market TEXT NOT NULL, line REAL,
    rule TEXT NOT NULL, levels TEXT NOT NULL            -- JSON list of quoted levels as received
);
CREATE INDEX IF NOT EXISTS snapshots_by_market ON snapshots (event, market, line, venue, ts);
CREATE TABLE IF NOT EXISTS episodes (
    key TEXT NOT NULL, event TEXT NOT NULL, market TEXT NOT NULL, line REAL,
    legs TEXT NOT NULL, venues TEXT NOT NULL,
    first_seen REAL NOT NULL, last_seen REAL NOT NULL, closed_at REAL, n_obs INTEGER NOT NULL,
    roi_first REAL NOT NULL, roi_max REAL NOT NULL, roi_min REAL NOT NULL,
    bankroll_first REAL, bankroll_max REAL, flags TEXT NOT NULL,
    PRIMARY KEY (key, first_seen)
);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def has_data(self):
        return self.db.execute('SELECT EXISTS (SELECT 1 FROM snapshots)').fetchone()[0] == 1

    def reset(self):
        self.db.executescript('DELETE FROM snapshots; DELETE FROM episodes;')

    def add_snapshot(self, ts, venue, market, rule, levels):
        self.db.execute('INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (ts, venue, market.event, market.market, market.line, rule, json.dumps(levels)))

    def add_episode(self, ep):
        m = ep.market
        self.db.execute(
            'INSERT OR REPLACE INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (ep.key, m.event, m.market, m.line, json.dumps(ep.legs), json.dumps(ep.venues),
             ep.first_seen, ep.last_seen, ep.closed_at, ep.n_obs, ep.roi_first, ep.roi_max, ep.roi_min,
             ep.bankroll_first, ep.bankroll_max, json.dumps(sorted(ep.flags))))

    def episodes(self):
        rows = self.db.execute(
            'SELECT key, event, market, line, legs, venues, first_seen, last_seen, roi_first, roi_max, roi_min, '
            'bankroll_first, bankroll_max, flags, n_obs, closed_at FROM episodes ORDER BY first_seen')
        return [Episode(r[0], MarketKey(r[1], r[2], r[3]), tuple(json.loads(r[4])), tuple(json.loads(r[5])),
                        *r[6:13], frozenset(json.loads(r[13])), r[14], r[15]) for r in rows]

    def window(self):
        """(first, last) snapshot time, or None when empty."""
        lo, hi = self.db.execute('SELECT MIN(ts), MAX(ts) FROM snapshots').fetchone()
        return None if lo is None else (lo, hi)

    def poll_gaps(self):
        """Seconds between consecutive snapshots of each venue's book for each market."""
        rows = self.db.execute(
            'SELECT gap FROM (SELECT ts - LAG(ts) OVER (PARTITION BY venue, event, market, line ORDER BY ts) AS gap '
            'FROM snapshots) WHERE gap IS NOT NULL')
        return [r[0] for r in rows]

    def commit(self):
        self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()
