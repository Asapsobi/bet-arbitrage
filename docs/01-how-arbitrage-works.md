# How football arbitrage works

An arb exists when the best prices for every outcome, taken across venues, have implied probabilities summing below 100%. Football 1X2 is a 3-way market, so you need three legs; Asian handicap, totals and draw-no-bet give cheaper 2-way arbs.

## Formula

For decimal odds `o_i` on each outcome `i` and total bankroll `B`:

```
S        = Σ (1 / o_i)          # arb exists if S < 1
stake_i  = B · (1 / o_i) / S
profit   = B · (1 / S − 1)
```

## Worked example (B = 1,000 USDT)

| Outcome | Best odds | Venue | Implied | Stake (USDT) | Payout (USDT) |
| --- | --- | --- | --- | --- | --- |
| Home | 2.10 | Book A | 47.6% | 480 | 1,008 |
| Draw | 3.60 | Book B | 27.8% | 280 | 1,008 |
| Away | 4.20 | Book C | 23.8% | 240 | 1,008 |
| **Total** | | | **99.2%** | **1,000** | **+8 (0.8%)** |

## Exchange commission

On an exchange, adjust each price for commission `c` on winnings before summing:

```
effective_odds = 1 + (o − 1) · (1 − c)
```

At Betfair's ~5% base rate, a 2.10 back becomes about 2.05, which can erase a sub-1% arb on its own. The scanner must always work on net-of-fee odds.

## Why arbs exist

- Books update at different speeds.
- Books hold different risk views / liabilities.
- Boosted odds and promotions create artificial arbs.

## The catch

Recreational (soft) books spot systematic arbers within days to weeks and restrict them. Sharps (Pinnacle) and exchanges (Betfair, Smarkets) do not restrict winners. This is the main design constraint for the product — see [Risks](06-risks.md).
