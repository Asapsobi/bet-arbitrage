# Crypto payment support

Five venues take crypto directly; the exchanges with the best APIs do not. Plan treasury around USDT, with BTC as the fallback where USDT is not offered.

| Venue | Coins | Fees / limits seen | Watch out for |
| --- | --- | --- | --- |
| [Cloudbet](https://www.deucescracked.com/sports-betting/cloudbet-review) | 28+ incl. BTC (Lightning), ETH, USDT | ~$1 minimum; withdrawals instant to 24 h | API coverage during rebuild |
| [Stake](https://dappradar.com/?p=27427) | BTC, ETH, USDT, LTC, DOGE, BNB, TRX | Fast crypto rails | No API; UK site is fiat-only |
| [Pinnacle](https://www.vip-grinders.com/best-bookmakers/pinnacle-sports-review) | BTC (users also report USDT) | Deposit free, $5–50,000; withdrawal ~$15 | Rollover required before withdrawal, or a fee ([rg.org](https://rg.org/en-ca/sportsbooks/review/pinnacle/pinnacle-user-reviews)) |
| [BetInAsia](https://www.oddschecker.com/ke/betting-sites/bet-in-asia) | BTC, ETH, USDT | 0% on deposit and first withdrawal | Recent complaints on deposit delays and crypto minimums |
| Polymarket | USDC on Polygon | Gas + market spread | Bridging USDT → USDC adds a step |
| Betfair, Smarkets, Matchbook, Betdaq | None | — | Fiat only: needs a bank card or e-wallet |

Always match the network to the deposit address (TRC-20 vs ERC-20 vs BEP-20); a mismatch can lose the funds ([CryptoDaily](https://cryptodaily.co.uk/2026/07/how-to-fund-a-crypto-sportsbook-with-stablecoins)).
