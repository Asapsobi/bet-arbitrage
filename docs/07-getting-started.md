# Getting started

Run a read-only scanner for 30 days and let the go/no-go gates decide. No money goes in until all six gates pass, and failing the legal gate (G1) alone is a stop. This follows the 30-day plan in the [research report](08-research-report-fa.md); the [scanner](09-scanner.md) does the measuring.

## 30-day read-only plan

| By | Deliverable |
| --- | --- |
| Day 7 | Country × venue matrix from each venue's official terms, plus a local lawyer's view (G1). Event mapper checked by hand on 200 sample events |
| Day 14 | Scanner running 72 hours without gaps: every quote stored with its timestamp, every arb with its first and last sighting (`arbscan replay`) |
| Day 21 | Daily table of net arbs by venue pair, market and league; fill rate from paper trading (`arbscan paper`) |
| Day 30 | Decision report with G2–G6 and a verdict per strategy (`arbscan gates`) |

First test: two-way markets (O/U, Asian handicap, draw no bet, BTTS, back/lay) in the Top-5 leagues and the Champions League, across Betfair (delayed key), Smarkets, Matchbook and Polymarket, with Pinnacle as the reference price. The Odds API gives breadth; the exchanges' own APIs give depth. The only cash cost is a data plan and a small server.

## Gates

| Gate | Go if |
| --- | --- |
| G1 legal | Written sign-off that every venue in the strategy is allowed where you operate |
| G2 frequency | Median ≥ 3 net arbs a day at ≥ 0.5% net, on executable venues |
| G3 depth | Median ≥ $200 fillable at the quoted price on every leg |
| G4 lifetime | Median ≥ 10 s with polling, or ≥ 2 s with streaming |
| G5 simulated fills | ≥ 90% filled, and losses on incomplete legs < 25% of gross profit |
| G6 economics | Projected monthly net profit ≥ 2× fixed monthly cost |

Thresholds are the report's estimates; tighten them before starting if you want.

## After a go

Only for strategies that pass every gate:

1. **Small live test.** Activate the Betfair live key (£499 one-off) and run two-way arbs with tight stake caps and auto-hedge.
2. **Add venues.** BetInAsia and Cloudbet once API access and legality are confirmed, funded with small USDT amounts.
3. **Scale.** Streaming feeds, more broker books, treasury rebalancing across venues.

## Open questions

- [ ] G1: is sports betting legal where you operate, and does each venue accept customers from there? Several venues block Iran outright ([scanner notes](09-scanner.md#not-built-yet-and-why)).
- [ ] Where will the collectors run? They need access to the venues without a VPN.
- [ ] Which settlement rules match across venues for each market (90 minutes, postponement, push)?
- [ ] Does Cloudbet's Trading API currently cover the football markets you need?
- [ ] Does BetInAsia grant betting-API access, and to customers from your country?
- [ ] Does Sportmarket offer an API and crypto funding?
