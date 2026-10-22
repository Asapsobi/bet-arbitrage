# Historical check: Pinnacle vs Betfair Exchange

How often a net arb appeared in real pre-match odds, after Betfair's commission, across 22 European leagues. Measured with `arbscan history` on football-data.co.uk files ([how](09-scanner.md#historical-odds-football-datacouk)).

_Measured 2026-10-21._

## Answer

Between Pinnacle and Betfair Exchange, the two venues in this data that don't limit winners, arbs of 0.5% or more after 5% commission came up **48 times in the whole 2024/25 season**: about 0.15 a day across all 22 leagues. Gate G2 asks for at least 3 a day, and about 11 once G6 is counted ($200 per arb at 0.5% net, $160 a month fixed cost). Adding every soft bookmaker raises it to 1.24 a day, still short, and those books have no betting API and limit winners.

## 2024/25, 22 leagues, 7,680 matches

| Market | Moment | Pinnacle + exchange: net arb | ≥ 0.5% | All books: net arb | ≥ 0.5% |
| --- | --- | --- | --- | --- | --- |
| 1X2 | Friday/Tuesday before | 0.1% | 0.0% | 2.0% | 0.8% |
| 1X2 | Kickoff | 0.3% | 0.2% | 6.7% | 3.7% |
| O/U 2.5 | Friday/Tuesday before | 0.0% | 0.0% | 0.1% | 0.0% |
| O/U 2.5 | Kickoff | 0.4% | 0.2% | 0.4% | 0.3% |
| Asian handicap | Friday/Tuesday before | 0.1% | 0.1% | 0.1% | 0.1% |
| Asian handicap | Kickoff | 0.7% | 0.2% | 0.9% | 0.4% |

Share of match-markets; arbs above 3% are left out as probable error prices (at most 0.9% of matches). Asian handicap covers 3,600 matches whose line was a half or whole goal.

| Count of ≥ 0.5% arbs, 311-day season | Before | Kickoff | Total | Per day |
| --- | --- | --- | --- | --- |
| Pinnacle + exchange | 8 | 40 | 48 | 0.15 |
| All books | 66 | 320 | 386 | 1.24 |

## League tiers

With the venue set held fixed, Top-5 leagues are no richer than the rest: Pinnacle vs exchange at kickoff, 1X2 arbs were 0.3% in the Top-5 and 0.2–0.3% in every other tier. The report's Top-5 figure (28.4% displayed arbs against 2.9–5.1% in lower tiers) came from the `Max` column, which takes the best of however many bookmakers quote a league; Top-5 leagues have more of them.

## Data caveats

- **Two snapshots per match.** Arbs that open and close between Friday afternoon and kickoff are missed, so continuous scanning would find more. Those short-lived ones are also the hardest to fill.
- **Kickoff prices may not be simultaneous.** Pinnacle and Betfair closing prices can come from different sources a little apart, which can create gaps that never existed together.
- **August–October 2025 is left out.** Kickoff arbs jump from 0–0.6% a month to about 10% in exactly those months and drop back in November; the exchange prices themselves look normal, so this is a source change, not the market. Exchange columns stop after January 2026, and exist only from 2024/25.
- **Back prices only.** No Betfair lay prices, no stake sizes, no Smarkets, Matchbook or Polymarket.
- **Pinnacle** has had no public betting API since July 2025; it is reachable through brokers.

## Reproduce

```bash
uv run arbscan fetch --seasons 2019-2025
uv run arbscan history data/football-data --since 2024-07-01 --until 2025-06-30
uv run arbscan history data/football-data --by month,snapshot --market 1x2 --pool 'pe=pinnacle,betfair_exchange'
```

## Independent check

`analysis/crosscheck_history.py` recounts this without any `arbscan` code and compares every match-market's return with `arbscan`'s per-match CSV:

```bash
uv run arbscan history data/football-data --since 2024-07-01 --until 2025-06-30 --csv data/h.csv
python analysis/crosscheck_history.py data/football-data --since 2024-07-01 --until 2025-06-30 --arbscan-csv data/h.csv
```

On 2024/25 all 36,831 returns agree to 3×10⁻¹⁶, and on every season fetched (51,207) the same. Charging commission on each exchange leg instead of once per market gives 41 arbs instead of 48: 8 need two legs in one Betfair market to clear 0.5%, and 1 (Brest, March 2025) is pushed past the 3% palp cut.
