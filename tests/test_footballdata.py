import csv
import urllib.error

import pytest

from arbscan import footballdata as fd
from arbscan import odds
from arbscan.cli import _seasons, main

HEADER = ['Div', 'Date', 'Time', 'HomeTeam', 'AwayTeam',
          'B365H', 'B365D', 'B365A', 'PSH', 'PSD', 'PSA', 'PH', 'PD', 'PA', 'BFDH', 'BFDD', 'BFDA',
          'BFH', 'BFD', 'BFA', 'BFEH', 'BFED', 'BFEA', 'MaxH', 'MaxD', 'MaxA',
          'B365>2.5', 'B365<2.5', 'P>2.5', 'P<2.5', 'BFE>2.5', 'BFE<2.5',
          'AHh', 'B365AHH', 'B365AHA', 'PAHH', 'PAHA',
          'PSCH', 'PSCD', 'PSCA', 'BFECH', 'BFECD', 'BFECA', 'AHCh', 'PCAHH', 'PCAHA']


def row(**kw):
    base = {'Div': 'E0', 'Date': '15/08/2025', 'Time': '20:00', 'HomeTeam': 'Liverpool', 'AwayTeam': 'Bournemouth',
            'B365H': '2.0', 'B365D': '3.4', 'B365A': '3.8', 'PSH': '2.05', 'PSD': '3.5', 'PSA': '3.9',
            'PH': '9', 'PD': '9', 'PA': '9',            # older Pinnacle columns; PS must win
            'BFDH': '1.9', 'BFDD': '3.3', 'BFDA': '3.7', 'BFH': '1.95', 'BFD': '3.3', 'BFA': '3.6',
            'BFEH': '2.3', 'BFED': '3.6', 'BFEA': '4.0', 'MaxH': '50', 'MaxD': '50', 'MaxA': '50',
            'B365>2.5': '1.9', 'B365<2.5': '1.95', 'P>2.5': '1.95', 'P<2.5': '1.97', 'BFE>2.5': '2.0', 'BFE<2.5': '',
            'AHh': '-0.5', 'B365AHH': '2.0', 'B365AHA': '1.9', 'PAHH': '2.02', 'PAHA': '1.92',
            'PSCH': '2.1', 'PSCD': '3.5', 'PSCA': '3.8', 'BFECH': '2.08', 'BFECD': '3.6', 'BFECA': '3.9',
            'AHCh': '-0.75', 'PCAHH': '1.95', 'PCAHA': '1.95'}
    base.update(kw)
    return base


def by(results, **kw):
    return [r for r in results if all(getattr(r, k) == v for k, v in kw.items())]


def test_quotes_pick_the_right_columns():
    q = {(s, m, ln, v): p for s, m, ln, v, p in fd.quotes(row())}
    assert q[('pre', '1x2', None, 'pinnacle')] == {'home': 2.05, 'draw': 3.5, 'away': 3.9}     # PS, not P
    assert q[('pre', '1x2', None, 'betfred')]['home'] == 1.9
    assert q[('pre', '1x2', None, 'betfair_sportsbook')]['home'] == 1.95
    assert not any(v == 'Max' or p.get('home') == 50 for (_, _, _, v), p in q.items())       # Max is not a venue
    assert ('pre', 'ou', 2.5, 'betfair_exchange') not in q                                      # Under missing
    assert q[('pre', 'ah', -0.5, 'pinnacle')] == {'home': 2.02, 'away': 1.92}


def test_season_event_and_quarter_lines():
    res = fd.scan_row(row(Date='10/05/26'), 'E0')
    assert {r.season for r in res} == {'2025/26'} and res[0].date == '2026-05-10'
    assert not by(res, market='ah', snapshot='close')                                          # -0.75 skipped


def test_best_net_price_per_outcome_with_exchange_commission():
    [r] = by(fd.scan_row(row(), 'E0'), market='1x2', snapshot='pre', pool='all')
    assert r.legs == ('betfair_exchange', 'pinnacle', 'pinnacle')
    S = 1 / odds.back(2.3, 0.05) + 1 / 3.5 + 1 / 3.9
    assert r.roi == pytest.approx(1 / S - 1)
    # with Betfair Basic's 2% the exchange wins every leg (net draw 3.548 beats Pinnacle's 3.5)
    [r2] = by(fd.scan_row(row(), 'E0', fee=fd.venues(0.02)), market='1x2', snapshot='pre', pool='all')
    assert r2.legs == ('betfair_exchange',) * 3


def test_legs_in_one_exchange_market_pay_commission_once():
    [r] = by(fd.scan_row(row(), 'E0', fee=fd.venues(0.02)), market='1x2', snapshot='pre', pool='all')
    gross = 1 / (1 / 2.3 + 1 / 3.6 + 1 / 4.0) - 1
    per_leg = 1 / (1 / odds.back(2.3, 0.02) + 1 / odds.back(3.6, 0.02) + 1 / odds.back(4.0, 0.02)) - 1
    assert r.roi == pytest.approx(gross * 0.98) and r.roi > per_leg     # commission on the net market win only


def test_named_pools_need_every_member():
    res = fd.scan_row(row(BFEH='', BFED='', BFEA=''), 'E0')
    assert not by(res, market='1x2', snapshot='pre', pool='pinnacle+exchange')
    assert by(res, market='1x2', snapshot='pre', pool='all')


def test_summarize_leaves_out_palp():
    R = lambda roi, legs=('bet365', 'pinnacle'): fd.Result('E0', '1 Top-5', '2025/26', 'd', 'h', 'a', 'pre', 'ou',
                                                          2.5, 'all', 2, roi, legs)
    [s] = fd.summarize([R(-0.02), R(0.004), R(0.012, ('betfair_exchange', 'pinnacle')), R(0.08)])
    assert (s.matches, s.arb, s.roi_min, s.roi_1pct, s.palp) == (4, 0.5, 0.25, 0.25, 0.25)
    assert s.median_roi == pytest.approx(0.008) and s.via_exchange == 0.5


def test_urls_and_season_codes():
    assert fd.url('E0', '2526') == 'https://www.football-data.co.uk/mmz4281/2526/E0.csv'
    assert fd.url('ARG') == 'https://www.football-data.co.uk/new/ARG.csv'
    assert _seasons('2019-2021') == ['1920', '2021', '2122'] and _seasons('1920,2526') == ['1920', '2526']


def test_fetch_skips_existing_and_reports_missing(tmp_path, monkeypatch):
    (tmp_path / '2526').mkdir()
    (tmp_path / '2526' / 'E0.csv').write_text('Div\n')

    def fail(*a, **k):
        raise urllib.error.URLError('404')
    monkeypatch.setattr(fd.urllib.request, 'urlopen', fail)
    done, missing = fd.fetch(['E0', 'D1'], ['2526'], tmp_path)
    assert done == [tmp_path / '2526' / 'E0.csv'] and missing == ['D1 2526: <urlopen error 404>']


def test_cli_history(tmp_path, capsys):
    f = tmp_path / 'E0.csv'
    with open(f, 'w', newline='', encoding='utf-8-sig') as fh:           # files start with a BOM
        w = csv.DictWriter(fh, HEADER)
        w.writeheader()
        w.writerows([row(), row(HomeTeam='Arsenal', AwayTeam='Chelsea', BFEH='2.0')])
    out_csv = tmp_path / 'out.csv'
    main(['history', str(tmp_path), '--by', 'market,snapshot', '--pool', 'all', '--csv', str(out_csv)])
    out = capsys.readouterr().out
    assert out.startswith('2 matches') and '1x2' in out and 'ou' in out
    assert sum(1 for _ in open(out_csv)) > 2
    main(['history', str(f), '--by', 'month', '--until', '2025-08-31'])
    assert '2025-08' in capsys.readouterr().out
    with pytest.raises(SystemExit, match='no matches'):
        main(['history', str(f), '--since', '2025-09-01'])
