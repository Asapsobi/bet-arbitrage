"""Independent recount of `arbscan history` for Pinnacle vs Betfair Exchange.

Shares no code with arbscan. It reads football-data.co.uk files with the csv module, takes the best
net price per outcome across Pinnacle and Betfair Exchange, and computes the return two ways:
commission on each exchange leg's winnings, and commission once on the exchange market's net
result (Betfair's rule, which arbscan uses). With --arbscan-csv it also compares every
match-market's return against arbscan's per-match output.

Usage:
    uv run arbscan fetch --seasons 2024-2024
    uv run arbscan history data/football-data --since 2024-07-01 --until 2025-06-30 --csv data/h.csv
    python analysis/crosscheck_history.py data/football-data --since 2024-07-01 --until 2025-06-30 \
        --arbscan-csv data/h.csv

Result on 2024/25 (checked 2026-10-22): 36,831 match-markets; 41 arbs >= 0.5% with commission per
leg and 48 with commission per market. 8 cross 0.5% only under the cheaper rule and 1 is pushed past
the 3% palp cut; arbscan's 48 are the same matches.
"""
import argparse
import csv
import sys
from itertools import product
from pathlib import Path


def num(row, col):
    try:
        x = float(row.get(col) or '')
    except ValueError:
        return None
    return x if x > 1 else None


def iso_date(s):
    try:
        d, m, y = s.strip().split('/')
        return f'{int(y) + (2000 if len(y) == 2 else 0)}-{int(m):02d}-{int(d):02d}'
    except ValueError:
        return None


def markets(row):
    """(snapshot, market, line, pinnacle prices, betfair prices) with both venues complete."""
    for snap, c in (('pre', ''), ('close', 'C')):
        ps = 'PS' if num(row, f'PS{c}H') else 'P'           # newer files PS, older P
        found = [('1x2', None, [num(row, f'{ps}{c}{s}') for s in 'HDA'], [num(row, f'BFE{c}{s}') for s in 'HDA']),
                 ('ou', 2.5, [num(row, f'P{c}>2.5'), num(row, f'P{c}<2.5')],
                  [num(row, f'BFE{c}>2.5'), num(row, f'BFE{c}<2.5')])]
        try:
            line = float(row.get('AHCh' if c else 'AHh') or '')
            if (line * 4) % 2 == 0:                          # quarter lines are not a clean 2-way market
                found.append(('ah', line, [num(row, f'P{c}AHH'), num(row, f'P{c}AHA')],
                              [num(row, f'BFE{c}AHH'), num(row, f'BFE{c}AHA')]))
        except ValueError:
            pass
        for market, line, pin, bfe in found:
            if all(pin) and all(bfe):
                yield snap, market, line, pin, bfe


def gauss(a, b):
    n = len(b)
    m = [list(row) + [v] for row, v in zip(a, b)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-14:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def market_level(odds, on_exchange, c):
    """Equal-payout return when leg i alone pays on outcome i and every exchange leg shares one market.

    Outcome k won by an exchange leg: market net = x_k (o_k - 1) - sum of the other exchange stakes,
    commission c only if that net is positive. Outcome k won elsewhere: the exchange market loses, no
    commission. Each sign assumption is solved as a linear system and kept only if it holds.
    """
    n = len(odds)
    ex = [i for i in range(n) if on_exchange[i]]

    def coeffs(k, positive):
        row = [0.0] * n
        if on_exchange[k]:
            f = (1 - c) if positive else 1.0
            for j in ex:
                row[j] += f * ((odds[k] - 1) if j == k else -1.0)
            for j in range(n):
                if not on_exchange[j]:
                    row[j] -= 1.0
        else:
            for j in range(n):
                row[j] = (odds[k] - 1) if j == k else -1.0
        return row

    for signs in product((True, False), repeat=len(ex)):
        pos = dict(zip(ex, signs))
        rows = [coeffs(k, pos.get(k, False)) for k in range(n)]
        a = [[x - y for x, y in zip(rows[k], rows[0])] for k in range(1, n)] + [[1.0] * n]
        x = gauss(a, [0.0] * (n - 1) + [1.0])
        if x is None or min(x) <= 0:
            continue
        nets = {k: x[k] * (odds[k] - 1) - sum(x[j] for j in ex if j != k) for k in ex}
        if all((nets[k] > 0) == pos[k] for k in ex):
            return sum(v * w for v, w in zip(rows[0], x))
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('data')
    p.add_argument('--since', default='0000-00-00')
    p.add_argument('--until', default='9999-99-99')
    p.add_argument('--commission', type=float, default=0.05)
    p.add_argument('--min-roi', type=float, default=0.005)
    p.add_argument('--palp', type=float, default=0.03)
    p.add_argument('--arbscan-csv', help='per-match CSV from arbscan history, to compare every return')
    p.add_argument('--arbscan-pool', default='pinnacle+exchange')
    a = p.parse_args()
    c, ours = a.commission, {}
    for f in sorted(Path(a.data).rglob('*.csv')):
        for row in csv.DictReader(f.read_bytes().decode('utf-8-sig', errors='replace').splitlines()):
            day = iso_date(row.get('Date', ''))
            if day is None or not a.since <= day <= a.until:
                continue
            for snap, market, line, pin, bfe in markets(row):
                net_bfe = [1 + (o - 1) * (1 - c) for o in bfe]
                on_ex = [nb >= pp for nb, pp in zip(net_bfe, pin)]   # ties go to the exchange, as in arbscan
                best = [nb if e else pp for nb, pp, e in zip(net_bfe, pin, on_ex)]
                leg = 1 / sum(1 / x for x in best) - 1
                gross = [o if e else pp for o, pp, e in zip(bfe, pin, on_ex)]
                exact = market_level(gross, on_ex, c) if sum(on_ex) > 1 else leg
                key = (day, row.get('HomeTeam') or row.get('Home'), snap, market, '' if line is None else str(line))
                ours[key] = (leg, exact if exact is not None else leg)

    hit = lambda r: a.min_roi <= r <= a.palp
    per_leg = {k for k, (lg, _) in ours.items() if hit(lg)}
    per_mkt = {k for k, (_, ex) in ours.items() if hit(ex)}
    print(f'match-markets compared: {len(ours):,}')
    print(f'arbs {a.min_roi:.1%}-{a.palp:.0%}: {len(per_leg)} with commission per leg, '
          f'{len(per_mkt)} with commission per market')
    print(f'  only with per-market commission (two exchange legs): {len(per_mkt - per_leg)}')
    print(f'  pushed past the {a.palp:.0%} palp cut by per-market commission: '
          f'{sum(1 for k in per_leg - per_mkt if ours[k][1] > a.palp)}')
    if not a.arbscan_csv:
        return 0
    theirs = {}
    for r in csv.DictReader(open(a.arbscan_csv)):
        if r['pool'] == a.arbscan_pool and a.since <= r['date'] <= a.until:
            theirs[(r['date'], r['home'], r['snapshot'], r['market'], r['line'])] = float(r['roi'])
    common = ours.keys() & theirs.keys()
    worst = max((abs(ours[k][1] - theirs[k]), k) for k in common) if common else (0.0, None)
    their_arbs = {k for k, v in theirs.items() if hit(v)}
    print(f'\narbscan rows in pool {a.arbscan_pool}: {len(theirs):,}; in both: {len(common):,}; '
          f'only here: {len(ours.keys() - theirs.keys())}; only in arbscan: {len(theirs.keys() - ours.keys())}')
    print(f'largest return difference on shared rows: {worst[0]:.2e}' + (f' at {worst[1]}' if worst[0] > 1e-9 else ''))
    same = their_arbs == per_mkt
    print('arb sets: identical' if same else f'arb sets differ: only here {sorted(per_mkt - their_arbs)}, '
                                             f'only in arbscan {sorted(their_arbs - per_mkt)}')
    return 0 if same and worst[0] <= 1e-9 and ours.keys() == theirs.keys() else 1


if __name__ == '__main__':
    sys.exit(main())
