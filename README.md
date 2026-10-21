# Bet Arbitrage — Football

Research and design notes for an automated football (soccer) betting-arbitrage product: which venues have APIs, which odds feeds to build on, which accept crypto, and how the system fits together.

_As of 2026-10-21._

## TL;DR

The buildable stack today is an aggregated odds feed for detection, plus three or four venues you can actually bet on by API. Soft bookmakers create the arbs but have no APIs and limit winners fast, so the product is built around venues that tolerate winners.

| Layer | Start with | Why |
| --- | --- | --- |
| Odds data | OddsPapi (350+ books, free tier) + a Pinnacle feed (pinnapi) | Covers sharps, crypto books and exchanges in one schema |
| Exchange leg | Betfair Exchange API (or Smarkets / Matchbook) | Real API, lay side, does not limit winners |
| Crypto book leg | Cloudbet Trading API | Only major crypto sportsbook with a public betting API |
| Sharp / Asian books | BetInAsia broker (BLACK, PS3838, OrbitX) | One crypto-funded wallet into Pinnacle and Asian books |
| Prediction market | Polymarket CLOB API | Soccer markets, USDC on Polygon, full order book |

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
| 7 | [Getting started](docs/07-getting-started.md) | Phased plan and open questions |
| 8 | [Research report (Persian)](docs/08-research-report-fa.md) | Measured arb frequency in 211k historical matches, a live net-of-fee check, venue/API database, ranking, capital, 30-day plan and go/no-go gates |
| 9 | [Scanner](docs/09-scanner.md) | Read-only `arbscan` package: net-of-fee engine, arb lifetime and depth log, gate scoring |
| — | [Sources](docs/sources.md) | Pages the research is based on |

Analysis code behind the report's measured figures is in [`analysis/`](analysis/): `arb_frequency.py` (historical frequency) and `live_example.py` (Bayern–Arsenal net-of-fee check); install its dependencies with `uv sync --extra analysis`. The scanner is in [`src/arbscan/`](src/arbscan/); see [docs/09](docs/09-scanner.md).

> Pricing, API availability and venue policies change often. Re-check each venue's own docs before building on it.
