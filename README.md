# Bet Arbitrage — Football

Research and design notes for an automated football (soccer) betting-arbitrage product: which venues have APIs, which odds feeds to build on, which accept crypto, and how the system fits together.

_As of 2026-10-21._

## TL;DR

The buildable stack today is an aggregated odds feed for detection, plus three or four venues you can actually bet on by API. Soft bookmakers create the arbs but have no APIs and limit winners fast, so the product is built around venues that tolerate winners.

Price gaps that look like arbs are common; arbs that survive fees on those venues are rare and thin. In the [report](docs/08-research-report-fa.md)'s live Smarkets–Polymarket check, the best one went from +1.14% to −0.61% after fees. So the plan is a 30-day read-only scanner first, and real money only once all six go/no-go gates pass, starting with the legal one ([getting started](docs/07-getting-started.md)).

| Layer | Start with | Why |
| --- | --- | --- |
| Odds data | The Odds API | Cheapest feed covering Pinnacle, Betfair Exchange, Matchbook, Smarkets, Polymarket and Kalshi in one schema; Pinnacle doubles as the fair-price reference |
| Depth and timing | The exchanges' own APIs: Betfair Stream, Smarkets v3, Polymarket CLOB | Aggregated feeds don't show order-book depth |
| Exchange leg | Betfair, Smarkets, Matchbook | Real API, lay side, do not limit winners |
| Prediction market | Polymarket CLOB API | Soccer markets, USDC on Polygon, full order book |
| Sharp / Asian books | Later: BetInAsia broker (BLACK, PS3838, OrbitX) | Ranked 2nd in the report; only once API access and legality are confirmed |
| Crypto book leg | Later: Cloudbet Trading API | Ranked 3rd; only once its football coverage and your country's access are confirmed |

Crypto-funded venues: **Cloudbet, Stake, Pinnacle, BetInAsia, Polymarket**. Betfair and the UK exchanges are fiat-only.

## Docs

| # | Doc | What's in it |
| --- | --- | --- |
| 1 | [How football arbitrage works](docs/01-how-arbitrage-works.md) | 3-way / 2-way math, stake sizing, commission, why arbs exist |
| 2 | [Execution venues with APIs](docs/02-execution-venues.md) | Exchanges, sharp books, crypto books, brokers — API, access, cost |
| 3 | [Odds data feeds](docs/03-odds-data-feeds.md) | Aggregators and arb scanners — coverage, pricing, streaming |
| 4 | [Crypto payment support](docs/04-crypto-payments.md) | Coins, fees and gotchas per venue |
| 5 | [System architecture](docs/05-architecture.md) | Pipeline from feeds to execution router, hedge and treasury |
| 6 | [Risks and gotchas](docs/06-risks.md) | Limits, leg risk, voids, fees, counterparty, legal |
| 7 | [Getting started](docs/07-getting-started.md) | 30-day read-only plan, go/no-go gates, what happens after a go, open questions |
| 8 | [Research report (Persian)](docs/08-research-report-fa.md) | Measured arb frequency in 211k historical matches, a live net-of-fee check, venue/API database, ranking, capital, 30-day plan and go/no-go gates |
| 9 | [Scanner](docs/09-scanner.md) | Read-only `arbscan` package: net-of-fee engine, arb lifetime and depth log, gate scoring |
| — | [Sources](docs/sources.md) | Pages the research is based on |

Analysis code behind the report's measured figures is in [`analysis/`](analysis/): `arb_frequency.py` (historical frequency) and `live_example.py` (Bayern–Arsenal net-of-fee check); install its dependencies with `uv sync --extra analysis`. The scanner is in [`src/arbscan/`](src/arbscan/); see [docs/09](docs/09-scanner.md).

> Pricing, API availability and venue policies change often. Re-check each venue's own docs before building on it.
