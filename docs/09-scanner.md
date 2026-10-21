# Scanner (arbscan)

A read-only scanner for the 30-day test in the [research report](08-research-report-fa.md). It finds arbs on net-of-fee odds, logs how long each one lives and how much bankroll it could take, and scores gates G1–G6. It never places orders.

_As of 2026-10-21._

## What is built

| Module | Does | Report gate |
| --- | --- | --- |
| `odds`, `venues` | Effective odds after commission and fees; quoted level → offer with fillable stake | — |
| `markets` | 1X2, O/U, AH, BTTS; which outcomes a back / lay / YES / NO pays on; rejects quarter lines | — |
| `engine` | Every leg combination covering each outcome once, same settlement rule, quotes within age and skew limits; palp flag above 3% | G2 |
| `payoff` | Equal-payout stakes when two legs share an exchange market (commission on net market winnings) | — |
| `lifecycle` | First / last sighting of each arb; closes only on a fresh look, so feed outages don't end arbs | G3, G4 |
| `store` | SQLite: every snapshot and every episode | all |
| `gates` | G2–G6 from the store; G1 is manual, G5 waits for the simulator | G1–G6 |
| `mapper` | Same match across venues; partial names and swapped home/away go to review | — |

## Run it

```bash
uv sync
uv run pytest
uv run arbscan scan fixtures/bayern_arsenal_2026-10-21.jsonl --max-age 120
uv run arbscan replay fixtures/synthetic_ou_demo.jsonl --db scan.db
uv run arbscan gates --db scan.db
```

`scan` shows every combination at one moment, near misses included; on the report's Bayern–Arsenal snapshot it reproduces the net table (B −0.61%, B2 −1.03%, A −1.30%, C −1.51%). `replay` runs a recording through the scanner and writes episodes; `gates` scores them. `synthetic_ou_demo.jsonl` is made-up data for the demo, not market quotes.

## Snapshot format

One JSON line per snapshot of one venue's book for one market. Live collectors will write the same format, so a recorded day replays exactly.

```json
{"ts": "2026-10-21T09:06:00Z", "venue": "smarkets", "event": "2026-10-21:bayern-munich-v-arsenal",
 "market": "1x2", "line": null, "rule": "ft90",
 "levels": [{"selection": "home", "side": "back", "price": 4587, "size": 120}]}
```

| Venue type | Sides | Price | Size |
| --- | --- | --- | --- |
| Exchange | `back`, `lay` | As quoted (Smarkets: basis points; back at the offer, lay at the bid) | Backer stake, venue currency |
| Prediction market | `yes`, `no` | Ask price | Shares |

## What the gate numbers mean

- **Lifetime (G4)** is reported as "certain / at most": first to last sighting, and first sighting to the first fresh look without it. If most arbs are gone by the next poll, the gate says so instead of passing; poll faster or stream.
- **Depth (G3)** is the largest bankroll every leg can fill at the quoted top-of-book price. Feeds without sizes give no depth, and those arbs count as zero in G6.
- **Frequency (G2)** and **economics (G6)** count overlapping arbs on one market as one chance, skip palp-flagged ones, and need at least a day of data.

## Not built yet, and why

- **Live collectors.** From Iran (checked 2026-10-21), Smarkets returns a Cloudflare block, Polymarket's Gamma `/events` returns a region block, and Betfair, Matchbook and OddsPapi time out. The report rules out VPNs, so collectors only make sense run from a place where the operator is allowed to use these venues (gate G1).
- **Paper-trading simulator (G5).**
- **Verified settlement rules.** Every leg is flagged `rules_unverified` until its `(venue, market, rule)` is checked against the venue's rules and added to `Limits.verified_rules`.
- **Smarkets size units** and **FX rates** (`venues.FX_TO_USD` is a placeholder) are unconfirmed.
