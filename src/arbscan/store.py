"""SQLite store for raw snapshots, closed episodes and paper trades. The schema ports to Postgres as is."""
from __future__ import annotations

import json
import sqlite3

from .lifecycle import Episode
from .markets import MarketKey
from .paper import Attempt

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
CREATE TABLE IF NOT EXISTS paper_trades (
    event TEXT NOT NULL, market TEXT NOT NULL, line REAL, legs TEXT NOT NULL, t0 REAL NOT NULL,
    bankroll REAL NOT NULL, roi REAL NOT NULL, status TEXT NOT NULL, fills TEXT NOT NULL, reasons TEXT NOT NULL,
    hedge REAL NOT NULL, pnl REAL NOT NULL, pnl_best REAL NOT NULL, open INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def has_data(self):
        return self.db.execute('SELECT EXISTS (SELECT 1 FROM snapshots)').fetchone()[0] == 1

    def reset(self):
        self.db.executescript('DELETE FROM snapshots; DELETE FROM episodes; DELETE FROM paper_trades;')

    def add_snapshot(self, ts, venue, market, rule, levels):
        self.db.execute('INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (ts, venue, market.event, market.market, market.line, rule, json.dumps(levels)))

    def snapshots(self):
        """Stored snapshots in the replay format, in time order."""
        rows = self.db.execute('SELECT ts, venue, event, market, line, rule, levels FROM snapshots ORDER BY ts, rowid')
        return [{'ts': r[0], 'venue': r[1], 'event': r[2], 'market': r[3], 'line': r[4], 'rule': r[5],
                 'levels': json.loads(r[6])} for r in rows]

    def set_attempts(self, attempts):
        """Replace the paper trades with a new simulation run."""
        self.db.execute('DELETE FROM paper_trades')
        self.db.executemany(
            'INSERT INTO paper_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [(a.market.event, a.market.market, a.market.line, json.dumps(a.legs), a.t0, a.bankroll, a.roi,
              a.status, json.dumps(a.fills), json.dumps(a.reasons), a.hedge, a.pnl, a.pnl_best, int(a.open))
             for a in attempts])
        self.db.commit()

    def attempts(self):
        """Paper trades of the last simulation run, or None if it never ran."""
        rows = self.db.execute(
            'SELECT event, market, line, legs, t0, bankroll, roi, status, fills, reasons, hedge, pnl, pnl_best, open '
            'FROM paper_trades ORDER BY t0').fetchall()
        if not rows:
            return None
        return [Attempt(MarketKey(r[0], r[1], r[2]), tuple(json.loads(r[3])), r[4], r[5], r[6], r[7],
                        tuple(json.loads(r[8])), tuple(json.loads(r[9])), r[10], r[11], r[12], bool(r[13]))
                for r in rows]

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
