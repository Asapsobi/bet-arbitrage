# Decision: park the product

_Decided 2026-10-22._

**Park it.** No real money, no live deployment, and no more product building from the current location. The code, data tools and research stay in this repo; the conditions that would reopen it are at the bottom.

## Why

The go/no-go gates from the [research report](08-research-report-fa.md) decide this, and two of them already fail on their own.

| Gate | Evidence | Result |
| --- | --- | --- |
| G1 legal | The operator is in Iran, where gambling is illegal. Polymarket blocks Iran outright; from Iran, Smarkets returns a Cloudflare block and Betfair, Matchbook and OddsPapi don't respond ([docs/09](09-scanner.md#not-built-yet-and-why)). The report rules out VPNs and borrowed accounts | **No-go** for real betting |
| G2 frequency | Pinnacle vs Betfair Exchange, 22 leagues, 2024/25: 48 arbs ≥ 0.5% net in the season, 0.15 a day. The bar is at least 3 a day, and about 11 once G6 is counted ([docs/10](10-historical-check.md)) | **Fails** for strategy 2, by about 70× |

The result holds when the fees are cut:

| Betfair commission | Pinnacle vs exchange, arbs ≥ 0.5% in 2024/25 | Per day |
| --- | --- | --- |
| 5% (UK Rewards) | 48 | 0.15 |
| 2% (Basic) | 111 | 0.36 |
| 0% (best case, not available) | 230 | 0.74 |

## Each strategy

| # | Strategy (report ranking) | What we know | Verdict |
| --- | --- | --- | --- |
| 1 | Two-way arbs between exchanges and Polymarket | Not measured over time. The one live check (Bayern–Arsenal, 2026-10-21) went from +1.14% gross to −0.61% after fees, and every combination was negative | Open, but blocked by G1 |
| 2 | Pinnacle or Asian books via a broker vs the exchange | 0.15 arbs a day before kickoff and at kickoff combined; still under 1 a day with zero commission | No-go |
| 3 | Cloudbet vs exchange or Pinnacle | Not measured; Cloudbet's API coverage and country rules unconfirmed | Not pursued |
| 4 | Soft bookmakers vs the exchange | The most arbs (1.24 a day with every bookmaker in 2024/25), but those books have no betting API and restrict winners within months | Not automatable |
| 5–7 | In-play, lower leagues and exotics, promos | No-go for a first version in the report; with the same venues, lower leagues show no more arbs than the Top-5 | No-go |

## What we keep

- **`arbscan`** (read-only, [docs/09](09-scanner.md)): net-of-fee engine with commission charged per market, arb lifetime and depth tracking, paper-trading simulator, gate scoring, event mapping, replay, and the football-data adapter. 43 tests, CI on Python 3.11 and 3.13.
- **Research:** the [report](08-research-report-fa.md) with its four internal fixes, the [historical check](10-historical-check.md), and the English docs aligned with both.
- **Reproducible numbers:** `arbscan fetch --seasons 2019-2025`, then the commands in [docs/10](10-historical-check.md).

## What would reopen it

1. **A legal base first.** Residency or a company in a country where these venues are allowed, with written legal sign-off for each venue (G1). Without it, nothing below matters.
2. **Then test the one open strategy.** A 30-day read-only run of strategy 1 from that location: collectors for Smarkets and Polymarket polled every few seconds, The Odds API for coverage, then `arbscan replay`, `paper` and `gates`. Go only if every gate passes.
3. **Test Polymarket as a maker in that run.** Makers pay no fee there. In the Bayern–Arsenal snapshot, combination B goes from −0.61% to +0.63% with the Polymarket leg posted as a maker at the same price, and to +1.65% one cent better. That trades fee for fill risk, and paper trading can measure both.
4. **A big drop in fees or a new data source.** Rerun `arbscan history` with the new fee (`--commission`) or new files. It takes seconds, and the result above should move by an order of magnitude before it matters.

## Loose ends, only if reopened

- Settlement rules for each venue and market are still unverified (every leg is flagged until checked).
- Smarkets size units and real FX rates are unconfirmed.
- The report's two images still list Betfair's delayed key without the caveat, and the Claude Docs copy linked from the report is out of date.
