"""football-data.co.uk odds files as scanner input.

Each row prices one match at two moments: 'pre' (collected the Friday or
Tuesday afternoon before) and 'close' (kickoff). Betfair Exchange columns are
back prices and pay exchange commission like any back. One snapshot per
moment and no stake sizes, so this measures how often net arbs appear (G2),
not depth, lifetime or fills.

Every quote is a back on one outcome, so taking the best net price per
outcome is the best combination; no search over combinations is needed.
"""
from __future__ import annotations

import csv
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from .markets import MarketKey, outcomes
from .payoff import equal_payout
from .venues import Venue, offer

BASE_URL = 'https://www.football-data.co.uk'

# Column prefix -> venue. 'PS' and 'P' are both Pinnacle; PS wins when a row has both.
BOOKS = {
    '1XB': '1xbet', 'B365': 'bet365', 'BF': 'betfair_sportsbook', 'BFD': 'betfred', 'BFE': 'betfair_exchange',
    'BMGM': 'betmgm', 'BS': 'bluesquare', 'BV': 'betvictor', 'BW': 'bwin', 'CL': 'coral', 'GB': 'gamebookers',
    'IW': 'interwetten', 'LB': 'ladbrokes', 'PP': 'paddypower', 'PS': 'pinnacle', 'P': 'pinnacle', 'SK': 'skybet',
    'SO': 'sportingodds', 'SB': 'sportingbet', 'SJ': 'stanjames', 'SY': 'stanleybet', 'VC': 'vcbet',
    'WH': 'williamhill',
}
EXCHANGE, SHARP = 'betfair_exchange', 'pinnacle'
SNAPSHOTS = {'pre': '', 'close': 'C'}

MAIN = ['E0', 'E1', 'E2', 'E3', 'EC', 'SC0', 'SC1', 'SC2', 'SC3', 'D1', 'D2', 'I1', 'I2', 'SP1', 'SP2',
        'F1', 'F2', 'N1', 'B1', 'P1', 'T1', 'G1']
EXTRA = ['ARG', 'AUT', 'BRA', 'CHN', 'DEN', 'FIN', 'IRL', 'JAP', 'MEX', 'NOR', 'POL', 'ROM', 'RUS', 'SUI',
         'SWE', 'USA']                # one file per league, closing odds only
TIERS = {                             # same grouping as analysis/arb_frequency.py
    **{d: '1 Top-5' for d in ['E0', 'D1', 'I1', 'SP1', 'F1']},
    **{d: '2 Top-5 second tiers' for d in ['E1', 'D2', 'I2', 'SP2', 'F2']},
    **{d: '3 Other EU top flights' for d in ['N1', 'P1', 'B1', 'T1', 'G1', 'SC0']},
    **{d: '4 Lower tiers Eng/Sco' for d in ['E2', 'E3', 'EC', 'SC1', 'SC2', 'SC3']},
    **{d: '5 Extra leagues' for d in EXTRA},
}
# Pools of venues an arb may use. 'all' is every bookmaker in the row, so its make-up varies by league and
# season; the named pools need every member quoting, which keeps comparisons across leagues fair.
POOLS = {
    'all': None,
    'bet365+pinnacle+exchange': ('bet365', SHARP, EXCHANGE),
    'pinnacle+exchange': (SHARP, EXCHANGE),
}


def venues(commission=0.05):
    """Fee model per venue: only the exchange charges commission (5% is Betfair's UK Rewards rate)."""
    return {v: Venue(v, commission=commission if v == EXCHANGE else 0.0, currency='GBP')
            for v in set(BOOKS.values())}


@dataclass(frozen=True)
class Result:
    div: str
    tier: str
    season: str
    date: str
    home: str
    away: str
    snapshot: str
    market: str
    line: float | None
    pool: str
    n_venues: int
    roi: float
    legs: tuple[str, ...]              # venue per outcome, in outcome order

    @property
    def uses_exchange(self):
        return EXCHANGE in self.legs

    @property
    def month(self):
        return self.date[:7]


def _odds(row, col):
    try:
        x = float(row.get(col) or '')
    except ValueError:
        return None
    return x if x > 1 else None


def _line(row, prefix, c):
    for col in ((f'{prefix}AH', 'AHh') if not c else ('AHCh',)):
        try:
            return float(row.get(col) or '')
        except ValueError:
            continue
    return None


def quotes(row):
    """(snapshot, market, line, venue, {selection: decimal odds}) for every complete quote in a row."""
    out, seen = [], set()
    for snap, c in SNAPSHOTS.items():
        for prefix, venue in BOOKS.items():
            found = [('1x2', None, dict(zip(('home', 'draw', 'away'),
                                            (_odds(row, f'{prefix}{c}{s}') for s in 'HDA')))),
                     ('ou', 2.5, {'over': _odds(row, f'{prefix}{c}>2.5'), 'under': _odds(row, f'{prefix}{c}<2.5')})]
            line = _line(row, prefix, c)
            if line is not None:
                found.append(('ah', line, {'home': _odds(row, f'{prefix}{c}AHH'), 'away': _odds(row, f'{prefix}{c}AHA')}))
            for market, ln, prices in found:
                if all(prices.values()) and (snap, market, ln, venue) not in seen:
                    seen.add((snap, market, ln, venue))
                    out.append((snap, market, ln, venue, prices))
    return out


def _date(s):
    for fmt in ('%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def scan_row(row, div, pools=POOLS, fee=None):
    """Best net combination per (snapshot, market, line, pool) for one match."""
    fee = fee or venues()
    day = _date(row.get('Date', ''))
    home, away = row.get('HomeTeam') or row.get('Home'), row.get('AwayTeam') or row.get('Away')
    if day is None or not home or not away:
        return []
    start = day.year if day.month >= 7 else day.year - 1
    season = f'{start}/{(start + 1) % 100:02d}'
    event = f'{div}:{day:%Y-%m-%d}:{_slug(home)}-v-{_slug(away)}'
    groups = {}
    for snap, market, line, venue, prices in quotes(row):
        groups.setdefault((snap, market, line), {})[venue] = prices
    out = []
    for (snap, market, line), books in groups.items():
        key = MarketKey(event, market, line)
        try:
            outs = outcomes(key)
        except ValueError:            # quarter-line handicaps are not a clean 2-way market
            continue
        offers = {v: [offer(fee[v], key, sel, 'back', p[sel], None, day.timestamp()) for sel in outs]
                  for v, p in books.items()}
        for pool, members in pools.items():
            use = [v for v in offers if members is None or v in members]
            if len(use) < 2 or (members is not None and len(use) < len(members)):
                continue
            legs = [max((offers[v][i] for v in use), key=lambda o: o.net_odds) for i in range(len(outs))]
            S = sum(1 / o.net_odds for o in legs)
            solved = equal_payout(legs) if len({o.group for o in legs}) < len(legs) else None
            roi = solved[1] if solved else 1 / S - 1
            out.append(Result(div, TIERS.get(div, div), season, f'{day:%Y-%m-%d}', home, away, snap, market,
                              line, pool, len(use), roi, tuple(o.venue for o in legs)))
    return out


def read(path):
    """Rows of one football-data CSV (BOM and Latin-1 tolerant)."""
    raw = Path(path).read_bytes()
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.DictReader(text.splitlines()))


def files(paths):
    out = []
    for p in map(Path, paths):
        out += sorted(p.rglob('*.csv')) if p.is_dir() else [p]
    return out


def scan_files(paths, pools=POOLS, commission=0.05):
    fee, results = venues(commission), []
    for f in files(paths):
        for row in read(f):
            div = row.get('Div') or f.stem
            results += scan_row(row, div, pools, fee)
    return results


@dataclass(frozen=True)
class Summary:
    group: tuple
    matches: int
    arb: float                 # share with a net arb (palp excluded)
    roi_min: float             # share at or above min_roi
    roi_1pct: float
    median_roi: float | None   # of the arbs
    palp: float                # share above the palp threshold, left out of the rest
    via_exchange: float | None  # share of arbs that use the exchange


def summarize(results, by=('market', 'snapshot', 'pool'), min_roi=0.005, palp=0.03):
    groups = {}
    for r in results:
        groups.setdefault(tuple(getattr(r, k) for k in by), []).append(r)
    out = []
    for key in sorted(groups, key=lambda k: tuple(str(x) for x in k)):
        rs = groups[key]
        ok = [r for r in rs if r.roi <= palp]
        arbs = [r for r in ok if r.roi > 0]
        n = len(rs)
        out.append(Summary(key, n, len(arbs) / n, sum(r.roi >= min_roi for r in ok) / n,
                           sum(r.roi >= 0.01 for r in ok) / n, median(r.roi for r in arbs) if arbs else None,
                           (n - len(ok)) / n, sum(r.uses_exchange for r in arbs) / len(arbs) if arbs else None))
    return out


def url(div, season=None):
    """Download URL: main leagues by season code ('2526' = 2025/26), extra leagues one file each."""
    return f'{BASE_URL}/new/{div}.csv' if div in EXTRA else f'{BASE_URL}/mmz4281/{season}/{div}.csv'


def fetch(divs, seasons, out_dir, refresh=False, timeout=30):
    """Download files into out_dir/<season>/<div>.csv (extra leagues: out_dir/extra/<div>.csv)."""
    done, missing = [], []
    jobs = [(d, None) for d in divs if d in EXTRA] + [(d, s) for s in seasons for d in divs if d not in EXTRA]
    for div, season in jobs:
        dest = Path(out_dir) / (season or 'extra') / f'{div}.csv'
        if dest.exists() and not refresh:
            done.append(dest)
            continue
        try:
            with urllib.request.urlopen(url(div, season), timeout=timeout) as resp:
                data = resp.read()
        except urllib.error.URLError as e:
            missing.append(f'{div} {season or ""}: {e}'.strip())
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        done.append(dest)
    return done, missing
