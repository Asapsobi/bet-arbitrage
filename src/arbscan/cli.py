"""arbscan: scan a moment, replay a recording, score the gates. Read-only; never places orders."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import gates, replay
from .engine import Limits, scan
from .store import Store


def _limits(a, min_roi):
    return Limits(max_age=a.max_age, max_skew=a.max_skew if a.max_skew is not None else a.max_age,
                  min_roi=min_roi if a.min_roi is None else a.min_roi, palp_roi=a.palp)


def _table(rows, header):
    rows = [header] + [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    for i, r in enumerate(rows):
        print('  '.join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        if i == 0:
            print('  '.join('-' * w for w in widths))


def _hms(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%H:%M:%S')


def _money(x):
    return '-' if x is None else f'${x:,.0f}'


def cmd_scan(a):
    snaps = replay.read(a.file)
    books, now = replay.books_at(snaps, None if a.at is None else replay.parse_ts(a.at))
    limits = _limits(a, -1.0)
    markets = sorted({replay.to_offers(s)[2] for s in snaps}, key=str)
    rows = []
    for m in markets:
        for o in scan(m, books.offers(m), now, limits)[:a.top]:
            stakes = ' / '.join(f'{w * a.bankroll:.2f}' for w in o.weights)
            rows.append([m, ' + '.join(map(str, o.legs)), f'{o.roi_per_leg:+.2%}', f'{o.roi:+.2%}', stakes,
                         _money(o.max_bankroll), ','.join(sorted(o.flags))])
    print(f'books at {_hms(now)} UTC, quotes up to {a.max_age:g} s old\n')
    _table(rows, ['market', 'legs', 'roi per-leg', 'roi', f'stakes of {a.bankroll:g}', 'max bankroll', 'flags'])


def cmd_replay(a):
    store = Store(a.db)
    if store.has_data():
        if not a.reset:
            sys.exit(f'{a.db} already holds snapshots; pass --reset to clear it first')
        store.reset()
    eps = replay.run(replay.read(a.file), _limits(a, 0.0), store=store)
    store.close()
    rows = [[e.market, ' + '.join(e.legs), _hms(e.first_seen), f'{e.lifetime_min:.0f}',
             '-' if e.lifetime_max is None else f'{e.lifetime_max:.0f}', e.n_obs, f'{e.roi_first:+.2%}',
             f'{e.roi_max:+.2%}', _money(e.bankroll_first), ','.join(sorted(e.flags))] for e in eps]
    print(f'{len(eps)} arb episodes written to {a.db}\n')
    if rows:
        _table(rows, ['market', 'legs', 'first seen', 'alive s', 'at most s', 'looks', 'roi first', 'roi max',
                      'bankroll', 'flags'])


def cmd_gates(a):
    store = Store(a.db)
    res = gates.evaluate(store.episodes(), store.window(), store.poll_gaps(), min_roi=a.min_roi,
                         fixed_cost=a.fixed_cost, cap=a.cap, latency=a.latency,
                         require_verified_rules=a.verified_only)
    store.close()
    _table([[g.gate, g.metric, g.value, g.go_if, g.verdict, g.note] for g in res],
           ['gate', 'metric', 'value', 'go if', 'verdict', 'note'])


def main(argv=None):
    p = argparse.ArgumentParser(prog='arbscan', description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)

    def limit_args(sp):
        sp.add_argument('--max-age', type=float, default=30.0, help='ignore quotes older than this, seconds')
        sp.add_argument('--max-skew', type=float, help='max seconds between leg quotes (default: --max-age)')
        sp.add_argument('--min-roi', type=float, help='keep combinations above this return, e.g. 0.002')
        sp.add_argument('--palp', type=float, default=0.03, help='flag returns above this as error prices')

    s = sub.add_parser('scan', help='every combination at one moment, near misses included')
    s.add_argument('file')
    s.add_argument('--at', help='ISO time or unix seconds (default: last snapshot)')
    s.add_argument('--top', type=int, default=5, help='combinations per market')
    s.add_argument('--bankroll', type=float, default=1000.0)
    limit_args(s)
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser('replay', help='replay a recording into the store and list arb episodes')
    r.add_argument('file')
    r.add_argument('--db', default='scan.db')
    r.add_argument('--reset', action='store_true', help='clear the store first')
    limit_args(r)
    r.set_defaults(func=cmd_replay)

    g = sub.add_parser('gates', help='score G1-G6 on the store')
    g.add_argument('--db', default='scan.db')
    g.add_argument('--min-roi', type=float, default=0.005, help='net return an arb needs to count for G2')
    g.add_argument('--fixed-cost', type=float, default=100.0, help='monthly data + server cost, USD')
    g.add_argument('--cap', type=float, help='planned max bankroll per arb, USD')
    g.add_argument('--latency', type=float, default=2.0, help='your detect-to-fill time, seconds')
    g.add_argument('--verified-only', action='store_true', help='count only arbs whose settlement rules are checked')
    g.set_defaults(func=cmd_gates)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == '__main__':
    main()
