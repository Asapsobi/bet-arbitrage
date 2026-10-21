"""arbscan: scan a moment, replay a recording, score the gates. Read-only; never places orders."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime, timezone

from . import footballdata, gates, paper, replay
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


def _venue_latency(s):
    """'smarkets=0.5,polymarket=2' -> {'smarkets': 0.5, 'polymarket': 2.0}"""
    try:
        return {v: float(t) for v, t in (p.split('=') for p in s.split(',') if p)}
    except ValueError:
        raise argparse.ArgumentTypeError(f'expected venue=seconds,..., got {s!r}')


def cmd_paper(a):
    store = Store(a.db)
    snaps = store.snapshots()
    if not snaps:
        sys.exit(f'{a.db} has no snapshots; run arbscan replay first')
    ex = paper.Execution(latency=a.latency, venue_latency=a.venue_latency, timeout=a.timeout,
                         hedge_delay=a.hedge_delay, cap=a.cap, size_fraction=a.size_fraction,
                         sequential=a.sequential, tolerance=a.tolerance, cooldown=a.cooldown, min_roi=a.min_roi)
    limits = Limits(max_age=a.max_age, max_skew=a.max_skew if a.max_skew is not None else a.max_age,
                    min_roi=0.0, palp_roi=a.palp)
    res = paper.simulate(snaps, limits, ex)
    store.set_attempts(res)
    store.close()
    by = Counter(r.status for r in res)
    legs = Counter(x for r in res for x in r.reasons)
    print(f'{len(res)} paper trades from {len(snaps)} snapshots: '
          + ', '.join(f'{by[s]} {s}' for s in ('filled', 'partial', 'missed', 'aborted')))
    print('legs: ' + (', '.join(f'{n} {r}' for r, n in legs.most_common()) or '-'))
    print(f'planned P&L ${sum(r.planned_pnl for r in res):,.2f}; simulated ${sum(r.pnl for r in res):,.2f}'
          ' (open positions at their worst outcome)\n')
    if res:
        _table([[r.market, ' + '.join(r.legs), _hms(r.t0), _money(r.bankroll), f'{r.roi:+.2%}', r.status,
                 ' / '.join(f'{f:.0%}' for f in r.fills), f'{r.pnl:+.2f}', 'yes' if r.open else '']
                for r in res],
               ['market', 'legs', 'at', 'bankroll', 'roi', 'status', 'filled', 'pnl', 'open'])


def _seasons(s):
    """'2019-2025' -> ['1920', ..., '2526'] (season start years); '1920,2526' as given."""
    m = re.fullmatch(r'(\d{4})-(\d{4})', s)
    if m:
        return [f'{y % 100:02d}{(y + 1) % 100:02d}' for y in range(int(m[1]), int(m[2]) + 1)]
    return [x for x in s.split(',') if x]


def _pool(s):
    name, _, members = s.partition('=')
    return name, (tuple(v for v in members.split(',') if v) or None) if members else None


def cmd_fetch(a):
    divs = a.divs.split(',') + (footballdata.EXTRA if a.extra else [])
    done, missing = footballdata.fetch(divs, _seasons(a.seasons), a.dir, a.refresh)
    print(f'{len(done)} files in {a.dir}' + (f'; {len(missing)} not available:' if missing else ''))
    for m in missing:
        print(f'  {m}')


def cmd_history(a):
    pools = dict(a.pool) if a.pool else footballdata.POOLS
    res = [r for r in footballdata.scan_files(a.paths, pools, a.commission)
           if r.market in a.market.split(',') and r.snapshot in a.snapshot.split(',')
           and (a.since is None or r.date >= a.since) and (a.until is None or r.date <= a.until)]
    if not res:
        sys.exit('no matches with at least two complete quotes in those files')
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow([*footballdata.Result.__dataclass_fields__, 'uses_exchange'])
            w.writerows([*(getattr(r, k) for k in footballdata.Result.__dataclass_fields__), r.uses_exchange]
                        for r in res)
    by = tuple(a.by.split(','))
    pct = lambda x: '-' if x is None else f'{x:.1%}'
    rows = [[*s.group, s.matches, pct(s.arb), pct(s.roi_min), pct(s.roi_1pct), pct(s.median_roi), pct(s.palp),
             pct(s.via_exchange)] for s in footballdata.summarize(res, by, a.min_roi, a.palp)]
    print(f'{len({(r.div, r.date, r.home) for r in res}):,} matches; Betfair Exchange commission {a.commission:.0%}; '
          f'arbs above {a.palp:.0%} counted as palp and left out\n')
    _table(rows, [*by, 'matches', 'net arb', f'>= {a.min_roi:.1%}', '>= 1%', 'median arb', 'palp', 'via exchange'])
    if a.csv:
        print(f'\nper-match results written to {a.csv}')


def cmd_gates(a):
    store = Store(a.db)
    res = gates.evaluate(store.episodes(), store.window(), store.poll_gaps(), attempts=store.attempts(),
                         min_roi=a.min_roi, fixed_cost=a.fixed_cost, cap=a.cap, latency=a.latency,
                         require_verified_rules=a.verified_only)
    store.close()
    _table([[g.gate, g.metric, g.value, g.go_if, g.verdict, g.note] for g in res],
           ['gate', 'metric', 'value', 'go if', 'verdict', 'note'])


def main(argv=None):
    p = argparse.ArgumentParser(prog='arbscan', description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)

    def limit_args(sp, min_roi=True):
        sp.add_argument('--max-age', type=float, default=30.0, help='ignore quotes older than this, seconds')
        sp.add_argument('--max-skew', type=float, help='max seconds between leg quotes (default: --max-age)')
        if min_roi:
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

    pp = sub.add_parser('paper', help='paper-trade every new arb in the store against the books that followed')
    pp.add_argument('--db', default='scan.db')
    pp.add_argument('--latency', type=float, default=1.0, help='seconds from decision to a venue')
    pp.add_argument('--venue-latency', type=_venue_latency, default={}, help='per venue, e.g. polymarket=2,smarkets=0.5')
    pp.add_argument('--timeout', type=float, default=10.0, help='a leg with no venue snapshot this long after arrival is missed')
    pp.add_argument('--hedge-delay', type=float, default=2.0, help='seconds after the last fill before topping up gaps')
    pp.add_argument('--cap', type=float, default=1000.0, help='max bankroll per arb, USD')
    pp.add_argument('--size-fraction', type=float, default=1.0, help='share of the quoted fillable bankroll to use')
    pp.add_argument('--sequential', action='store_true', help='send the thinnest leg first, the rest once it fills')
    pp.add_argument('--tolerance', type=float, default=0.0, help='accept net odds this much worse, relative')
    pp.add_argument('--cooldown', type=float, default=30.0, help='at most one attempt per market in this many seconds')
    pp.add_argument('--min-roi', type=float, default=0.005, help='trade arbs at or above this net return')
    limit_args(pp, min_roi=False)
    pp.set_defaults(func=cmd_paper)

    fe = sub.add_parser('fetch', help='download football-data.co.uk odds files')
    fe.add_argument('--divs', default=','.join(footballdata.MAIN), help='division codes, e.g. E0,D1')
    fe.add_argument('--seasons', default='2019-2025', help='start years 2019-2025, or codes 1920,2526')
    fe.add_argument('--extra', action='store_true', help='also the extra leagues (ARG, BRA, USA, ...)')
    fe.add_argument('--dir', default='data/football-data')
    fe.add_argument('--refresh', action='store_true', help='download again even if the file exists')
    fe.set_defaults(func=cmd_fetch)

    h = sub.add_parser('history', help='net-of-fee arb frequency in football-data.co.uk files')
    h.add_argument('paths', nargs='+', help='CSV files or folders')
    h.add_argument('--by', default='market,snapshot,pool',
                   help='group by any of: tier, div, season, month, market, snapshot, pool')
    h.add_argument('--since', help='first match date, YYYY-MM-DD')
    h.add_argument('--until', help='last match date, YYYY-MM-DD')
    h.add_argument('--pool', type=_pool, action='append',
                   help='venue pool, e.g. tolerant=pinnacle,betfair_exchange or all (repeatable)')
    h.add_argument('--market', default='1x2,ou,ah')
    h.add_argument('--snapshot', default='pre,close')
    h.add_argument('--commission', type=float, default=0.05, help='Betfair Exchange commission')
    h.add_argument('--min-roi', type=float, default=0.005)
    h.add_argument('--palp', type=float, default=0.03, help='leave out arbs above this as probable error prices')
    h.add_argument('--csv', help='write per-match results here')
    h.set_defaults(func=cmd_history)

    g = sub.add_parser('gates', help='score G1-G6 on the store')
    g.add_argument('--db', default='scan.db')
    g.add_argument('--min-roi', type=float, default=0.005, help='net return an arb needs to count for G2')
    g.add_argument('--fixed-cost', type=float, default=160.0, help='monthly data + server cost, USD (docs/08: about 160)')
    g.add_argument('--cap', type=float, help='planned max bankroll per arb, USD')
    g.add_argument('--latency', type=float, default=2.0, help='your detect-to-fill time, seconds')
    g.add_argument('--verified-only', action='store_true', help='count only arbs whose settlement rules are checked')
    g.set_defaults(func=cmd_gates)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == '__main__':
    main()
