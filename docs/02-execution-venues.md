# Execution venues with APIs

Only a handful of venues let you place bets by API. Pinnacle, the anchor sharp book, closed its public API in July 2025, so it is now reached through brokers or as read-only data.

| Venue | Type | Betting API | How you get access | Cost to you | Crypto |
| --- | --- | --- | --- | --- | --- |
| [Betfair Exchange](https://support.developer.betfair.com/hc/en-us/articles/115003864651-How-do-I-get-started) | Exchange | Yes: REST + Stream API | Free delayed key for dev; live key on application | £499 one-off live key; UK/IE commission 5% (Rewards), 2% (Basic) or 8% (Rewards+) on net winnings | No |
| [Smarkets](https://sportsapis.dev/betting-exchange-api) | Exchange | Yes | Public v3 read endpoints work without auth; trading via request form and explicit approval | 2% commission on net winnings | No |
| [Matchbook](https://github.com/xanadunf/matchbook) | Exchange | Yes: REST, session token | Verified account | Commission on winnings | No |
| Betdaq | Exchange | Yes | Account + API terms | Commission on winnings | No |
| [Cloudbet](https://pkg.go.dev/github.com/cloudbet/docs) | Crypto sportsbook | Yes: Feed, Trading, Account APIs | API key from account; test funds (PLAY_EUR) for validation | Book margin ~3.5–5% | Yes, 28+ coins |
| [BetInAsia](https://www.vip-grinders.com/best-bookmakers-2022/betinasia-review) | Broker | Yes (BLACK platform + betting API) | Broker account | ~3% on OrbitX winnings | Yes: BTC, ETH, USDT |
| Pinnacle / PS3838 | Sharp book | No public API since July 2025 | Via brokers (PS3838 through BetInAsia) | Low margin, ~2–3% | Yes: BTC (direct) |
| [Stake](https://sharpapi.io/sportsbooks/stake-odds-api) | Crypto sportsbook | No public API (undocumented internal only) | Manual or browser automation (ToS risk) | Book margin | Yes: BTC, ETH, USDT, more |
| [Polymarket](https://skills.cat/skills/axwelbrand-byte/arbibot/polymarket-prediction-market) | Prediction market | Yes: CLOB + Gamma APIs | Wallet-based; public reads need no auth | Sports taker fee = 0.05 × p × (1 − p) per share; makers pay 0 ([fees](https://docs.polymarket.com/trading/fees?via=xp)). Iran blocked; UK, US, FR, DE close-only ([geoblock](https://docs.polymarket.com/api-reference/geoblock.md)) | Yes: USDC on Polygon |
| Sportmarket | Broker | Sportmarket Pro (Molly) platform; API to confirm | Broker account | Free broker, no limits on winners | To confirm |

## Notes

- **Betfair** rate-limits `listMarketBook` at 5 requests/second per app key and can charge for heavy polling, so use the Exchange Stream API ([source](https://github.com/ChainBench/OpenChainBench/pull/1702/files)).
- **Cloudbet** is mid-rebuild of its API; check which sports and markets the Trading API currently covers before relying on it ([GitHub discussion](https://github.com/cloudbet/docs/discussions/186)).
- **BetInAsia** has recent user complaints about slower, fee-bearing deposits and high minimums on crypto transfers ([Trustpilot](https://jp.trustpilot.com/review/betinasia.com)). Start small.
- **Polymarket** endpoints: CLOB `https://clob.polymarket.com`, Gamma `https://gamma-api.polymarket.com`.
