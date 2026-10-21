# Getting started

Start data-only and prove arbs exist on venues you can actually execute on, before putting money in.

1. **Weeks 1–2 — Data and scanner.** Get free keys: OddsPapi, pinnapi, Betfair delayed key, Cloudbet API key. Build event / market mapping across books, then the arb scanner with net-of-commission odds. Log every arb with its size, venues and lifespan.
2. **Weeks 3–4 — Measure.** From the log, count arbs per day that involve only executable venues (Betfair, Cloudbet, BetInAsia books, Polymarket). Median lifespan tells you whether REST polling is enough or you need WebSocket.
3. **Weeks 5–6 — Small live test.** Activate the Betfair live key (£299), fund Cloudbet and BetInAsia with small USDT amounts, run two-way arbs (Asian handicap, totals) with tight stake caps and auto-hedge.
4. **After that — Scale.** Upgrade the odds feed to streaming, add Polymarket and more broker books, and add treasury rebalancing across venues.

## Open questions

- [ ] Is sports betting legal for you, and do Betfair, Cloudbet and BetInAsia accept customers from your country?
- [ ] Does Cloudbet's Trading API currently cover the football markets you need?
- [ ] Does Sportmarket offer an API and crypto funding?
- [ ] Which OddsPapi plan includes WebSocket?
