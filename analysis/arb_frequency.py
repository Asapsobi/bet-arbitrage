"""Historical pre-match arbitrage frequency in football (1X2 and O/U 2.5).

Reproduces the "Measured" historical figures in docs/08-research-report-fa.md.

Data: football-data.co.uk odds via the GitHub mirror
https://github.com/xgabora/Club-Football-Match-Data-2000-2025 (data/Matches.csv).
MaxHome/MaxDraw/MaxAway and MaxOver25/MaxUnder25 are market-maximum odds from a
single pre-match snapshot (Friday/Tuesday afternoon), so the result is an upper
bound on *displayed* arbs, not executable ones.

Usage:
    git clone --depth 1 https://github.com/xgabora/Club-Football-Match-Data-2000-2025 cfmd
    python analysis/arb_frequency.py cfmd/data/Matches.csv
"""
import sys

import pandas as pd

EXTRA = ['ARG', 'AUT', 'BRA', 'CHN', 'DEN', 'FIN', 'IRL', 'JAP', 'MEX', 'NOR',
         'POL', 'ROM', 'RUS', 'SUI', 'SWE', 'USA']  # different source file family
TIERS = {
    **{d: '1 Top-5' for d in ['E0', 'D1', 'I1', 'SP1', 'F1']},
    **{d: '2 Top-5 second tiers' for d in ['E1', 'D2', 'I2', 'SP2', 'F2']},
    **{d: '3 Other EU top flights' for d in ['N1', 'P1', 'B1', 'T1', 'G1', 'SC0']},
    **{d: '4 Lower tiers Eng/Sco' for d in ['E2', 'E3', 'EC', 'SC1', 'SC2', 'SC3']},
    **{d: '5 Extra leagues' for d in EXTRA},
}


def load(path):
    df = pd.read_csv(path, low_memory=False)
    df['MatchDate'] = pd.to_datetime(df['MatchDate'])
    df['Season'] = df.MatchDate.dt.year.where(df.MatchDate.dt.month >= 7, df.MatchDate.dt.year - 1)
    df['tier'] = df.Division.map(TIERS)
    return df


def with_arb(df, cols):
    x = df.dropna(subset=cols).copy()
    x = x[(x[cols] > 1).all(axis=1)]
    x['S'] = sum(1 / x[c] for c in cols)          # implied probability sum of best prices
    x['ROI'] = 1 / x.S - 1
    x['arb'] = x.S < 1
    return x


def summary(x):
    return pd.Series({
        'matches': len(x),
        'arb_pct': x.arb.mean() * 100,
        'roi_ge_1pct_pct': (x.ROI >= 0.01).mean() * 100,
        'roi_ge_2pct_pct': (x.ROI >= 0.02).mean() * 100,
        'median_roi_of_arbs_pct': x.loc[x.arb, 'ROI'].median() * 100,
    })


def main(path):
    df = load(path)
    x12 = with_arb(df, ['MaxHome', 'MaxDraw', 'MaxAway'])
    xou = with_arb(df, ['MaxOver25', 'MaxUnder25'])
    main_ = x12[~x12.Division.isin(EXTRA)]

    by_season = main_[main_.Season.between(2005, 2025)].groupby('Season').apply(summary)
    by_season.index = [f'{s}/{str(s + 1)[2:]}' for s in by_season.index]
    print('== 1X2, 22 main European divisions, by season')
    print(by_season.round(2).to_string())

    recent = [2022, 2023]
    print('\n== 1X2 by tier, 2022/23-2023/24')
    print(x12[x12.Season.isin(recent)].groupby('tier').apply(summary).round(2).to_string())
    print('\n== O/U 2.5 by tier, 2022/23-2023/24')
    print(xou[xou.Season.isin(recent)].groupby('tier').apply(summary).round(2).to_string())
    print('\n== 1X2, main divisions, 2022/23-2023/24')
    print(summary(main_[main_.Season.isin(recent)]).round(2).to_string())


if __name__ == '__main__':
    main(sys.argv[1])
