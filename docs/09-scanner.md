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
| `paper` | Paper trading: each new arb's legs judged against the snapshots after their latency; gaps hedged later | G5 |
| `store` | SQLite: every snapshot, episode and paper trade | all |
| `gates` | G2–G6 from the store; G1 is manual | G1–G6 |
| `mapper` | Same match across venues; partial names and swapped home/away go to review | — |
| `footballdata` | football-data.co.uk odds files: download, then net-of-fee arb frequency per match by venue pool | G2 (history) |

## Run it

```bash
uv sync
uv run pytest
uv run arbscan scan fixtures/bayern_arsenal_2026-10-21.jsonl --max-age 120
uv run arbscan replay fixtures/synthetic_ou_demo.jsonl --db scan.db
uv run arbscan paper --db scan.db --latency 1 --venue-latency polymarket=2
uv run arbscan gates --db scan.db
```

`scan` shows every combination at one moment, near misses included; on the report's Bayern–Arsenal snapshot it reproduces the net table (B −0.61%, B2 −1.03%, A −1.30%, C −1.51%). `replay` runs a recording through the scanner and writes episodes; `paper` trades them on paper; `gates` scores the result. `synthetic_ou_demo.jsonl` is made-up data for the demo, not market quotes.

## Historical odds (football-data.co.uk)

football-data.co.uk is reachable from Iran, so this runs on real odds today. Results are in [docs/10](10-historical-check.md).

```bash
uv run arbscan fetch --seasons 2019-2025            # 22 main divisions into data/football-data (git-ignored)
uv run arbscan history data/football-data --since 2024-07-01 --until 2025-06-30
uv run arbscan history data/football-data --by month,snapshot --pool 'pe=pinnacle,betfair_exchange'
```

Each row prices a match at two moments: `pre` (collected Friday or Tuesday afternoon) and `close` (kickoff), for 1X2, O/U 2.5 and the row's Asian handicap line. Quarter lines are skipped. Betfair Exchange prices pay `--commission` (default 5%); legs sharing the exchange market pay it once, on the net result. Every quote is a back on one outcome, so the best net price per outcome is the best combination.

| Pool | Venues | Use |
| --- | --- | --- |
| `all` | Every bookmaker in the row | Upper bound; its make-up changes by league and season |
| `bet365+pinnacle+exchange` | Fixed three | Fair comparison across leagues and seasons |
| `pinnacle+exchange` | Fixed two that don't limit winners | Closest to the report's strategies 1–2 |

`--pool name=venue,venue` defines others; `--csv` writes per-match results. Group with `--by` (tier, div, season, month, market, snapshot, pool) and use `--by month` to spot data-source changes before trusting a number.

What it can't tell you: depth, lifetime or fills (no sizes, two snapshots per match), lay prices, or Smarkets / Matchbook / Polymarket.

`analysis/crosscheck_history.py` recounts the Pinnacle + exchange pool with no shared code and exits non-zero if any return differs; run it after changing the adapter or the solver. `tests/test_properties.py` settles thousands of random leg sets by hand and checks the solver and the engine against them.

## Paper trading

When an arb is first seen, every leg goes out as a limit order at the detected price, sized to the smaller of `--cap` and the quoted fillable bankroll.

| Step | Rule |
| --- | --- |
| Arrival | Detection time + the venue's latency (`--latency`, `--venue-latency`) |
| Fill | Against the venue's first snapshot after arrival, never the one the arb was detected on. Filled up to the size quoted at the detected price or better (`--tolerance` relaxes it) |
| Miss | `price_moved` if that snapshot has nothing at the price; `no_quote` if the venue sends no snapshot within `--timeout` |
| Order | All legs at once, or with `--sequential` the thinnest leg first and the rest only after it fills (sized down to match) |
| Hedge | `--hedge-delay` after the last fill, each short block is topped up at the best price any venue then shows. What can't be covered stays open and is booked at its worst outcome |
| Pacing | One trade per new arb, the best one first, and at most one per market per `--cooldown` |

Statuses are `filled` (every leg in proportion, maybe smaller than planned), `partial` (hedged or open), `missed` (nothing filled) and `aborted` (sequential first leg missed, no exposure). G5 is the share of `filled`, and the net loss on everything else as a share of what the filled ones made.

Not modelled: queue position, and our own fills taking liquidity out of later snapshots, both of which flatter the result. Partial outcomes charge commission per leg, which is conservative. When feeds are polled more slowly than the timeout, most legs end `no_quote`; G5 says so rather than passing.

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
- **Frequency (G2)** and **economics (G6)** count overlapping arbs on one market as one chance, skip palp-flagged ones, and need at least a day of data. G2's bar is the larger of 3 a day and what G6 needs at the measured depth and return, 2 × fixed cost ÷ (30 × bankroll × ROI); `--fixed-cost` defaults to the report's $160 a month.
- **Simulated fills (G5)** come from the last `arbscan paper` run on the same store; `replay --reset` clears them.

## Not built yet, and why

- **Live collectors.** From Iran (checked 2026-10-21), Smarkets returns a Cloudflare block, Polymarket's Gamma `/events` returns a region block, and Betfair, Matchbook and OddsPapi time out. The report rules out VPNs, so collectors only make sense run from a place where the operator is allowed to use these venues (gate G1).
- **Verified settlement rules.** Every leg is flagged `rules_unverified` until its `(venue, market, rule)` is checked against the venue's rules and added to `Limits.verified_rules`.
- **Smarkets size units** and **FX rates** (`venues.FX_TO_USD` is a placeholder) are unconfirmed.
