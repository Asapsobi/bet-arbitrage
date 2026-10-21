# Odds data feeds

For football arbs, bookmaker breadth beats everything else: you need sharps, Asian books, crypto books and exchanges in one normalized schema. OddsPapi and Odds-API.io have the widest coverage; The Odds API is the cheapest feed that covers Pinnacle and the exchanges (Betfair, Matchbook, Smarkets) plus Polymarket and Kalshi, so the [report](08-research-report-fa.md) picks it for the first test. None of them show order-book depth; that comes from the exchanges' own APIs.

| Provider | Books | Sharps / crypto / exchanges | Free tier | Paid from | Streaming |
| --- | --- | --- | --- | --- | --- |
| [OddsPapi](https://oddspapi.io/blog/?p=144) | 350+ | Pinnacle, Singbet, SBOBet; Stake, Cloudbet; Matchbook | 250 req/month + historical | ~$49/mo | WebSocket on paid plans (some say B2B only — confirm) |
| [Odds-API.io](https://odds-api.io/blog/best-odds-apis-2026) | 415+ | Betfair Exchange, Polymarket | None (new free keys paused) | £49/mo for 2 books (to £229 for 15) | REST + WebSocket |
| [pinnapi](https://sportsapis.dev/apis/pinnapi) | Pinnacle only | Pinnacle reference line | Free while building | Tiered | REST, SSE, WebSocket |
| [SportsGameOdds](https://sportsgameodds.com/blog/comparing-odds-api-providers) | 85+ | Pinnacle, Polymarket, Kalshi | Limited, 7-day trial | $99/mo | WebSocket on enterprise |
| [The Odds API](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html) | 100+ | Pinnacle, Betfair Ex (uk/eu/au), Matchbook, Smarkets, Polymarket, Kalshi | 500 credits/month | $30/mo (to $249) | REST only |
| [OpticOdds](https://sportsgameodds.com/blog/comparing-odds-api-providers) | 200+ | Broad | No | ~$5,000/mo | SSE |
| [BetBurger](https://www.ruthlessreviews.com/featured-posts/arbitrage-betting-services-review-betburger-vs-surebet-2/) | 127+ originals, 582 clones | Arb signals already computed | Arbs ≤1%, up to 60 s delay | Subscription | API (plan-dependent) |

## Notes

- The Odds API bills credits as `markets × regions` per call, so 500 free credits is roughly 83 multi-market calls ([OddsPapi](https://oddspapi.io/blog/the-odds-api-free-tier-limits)).
- Most vendor comparisons come from competitors' own blogs. Benchmark coverage and latency yourself before paying.
- Use the Pinnacle line as the "fair price" reference for sanity checks and error-price filtering.
