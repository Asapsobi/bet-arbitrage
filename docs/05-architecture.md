# System architecture

The product is a pipeline much like a market-making stack: normalized feeds in, a scanner, risk checks, and one router that owns every order.

The 30-day test runs only the read-only half: feeds, normalizer, scanner and risk checks, writing to a log and the paper trader ([scanner](09-scanner.md)). The execution router, hedge loop and treasury are built only after a go on every gate ([getting started](07-getting-started.md)).

```mermaid
flowchart TD
    F1["Aggregated odds feed<br/><small>The Odds API</small>"]
    F2["Pinnacle reference line<br/><small>from the odds feed, or pinnapi</small>"]
    F3["Venue order books<br/><small>Betfair Stream, Polymarket WS</small>"]

    N["Normalizer<br/><small>map events and markets; odds net of commission</small>"]
    S["Arb scanner<br/><small>sum of 1/odds below 1; stake per leg</small>"]
    R["Risk checks<br/><small>stake caps, venue exposure, error-price filter</small>"]
    X["Execution router<br/><small>fill the slow leg first, then the rest</small>"]

    V1["Betfair exchanges<br/><small>REST + Stream API</small>"]
    V2["Cloudbet<br/><small>Trading API, crypto</small>"]
    V3["BetInAsia broker<br/><small>BLACK, PS3838, OrbitX</small>"]
    V4["Polymarket<br/><small>CLOB API, USDC</small>"]

    H["Fill monitor and hedge<br/><small>rejected leg: auto-hedge on an exchange</small>"]
    T["Treasury and ledger<br/><small>USDT and BTC balances per venue; rebalancing</small>"]

    F1 --> N
    F2 --> N
    F3 --> N
    N --> S --> R --> X
    X --> V1 & V2 & V3 & V4
    V1 & V2 & V3 & V4 --> H
    V1 & V2 & V3 & V4 --> T

    style X stroke-width:3px
```

## Components

| Component | Responsibility |
| --- | --- |
| Feeds | Aggregated odds for detection; Pinnacle as fair-price anchor; venue order books for live depth |
| Normalizer | Map the same match / market / selection across venues; convert to decimal odds net of commission |
| Arb scanner | Compute `Σ 1/o_i`, flag `< 1`, size each leg |
| Risk checks | Per-arb stake caps, per-venue exposure limits, reject suspicious (error) prices |
| Execution router | Places legs; fills the leg most likely to move or reject first |
| Fill monitor and hedge | Watches fills; if a leg fails, hedges the open position on an exchange |
| Treasury and ledger | Tracks USDT / BTC balances per venue, P&L, and rebalancing |

The router is where profit is won or lost: it fills the leg most likely to move or reject first, and the hedge loop covers any leg that fails.
