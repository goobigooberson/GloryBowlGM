# Real NFL contract market (for the free agency step)

Data: OverTheCap via nflverse `tools/data/nflverse/contracts/historical_contracts.csv.gz`.
Full numbers: `real_contracts.json` (same folder); script: `contracts_market.py`.

**Big caveat: the local CSV is a May 2022 snapshot.** nflverse stopped updating the CSV; the
current file (updated Oct 20, 2026) is parquet only, which needs `pip install pyarrow` and a
re-download (Blake's call). Everything below is in **% of that year's cap**, which ages much
better than dollars. Dollar figures use the 2026 cap ($301.2M).
"Veteran deal" = any contract that isn't the player's rookie deal (includes extensions, tags,
re-signings, futures/minimum deals). OTC's `years` = new years added (for extensions).
Age = at signing (birth date where known, else draft year + 22).

## Salary cap history ($M)
2017 167.0 · 2018 177.2 · 2019 188.2 · 2020 198.2 · 2021 182.5 (COVID dip) · 2022 208.2 ·
2023 224.8 · 2024 255.4 · 2025 279.2 · 2026 301.2 (+$77.6M benefits per club).
Typical growth ~7-10% a year (2023-26: +8.0%, +13.6%, +9.3%, +7.9%).

## The market ladder: Nth best-paid player at each position (active deals, 2022)
APY as % of cap (→ $M at the 2026 cap).

| Pos | #1 | #5 | #10 | #32 |
|---|---|---|---|---|
| QB | 24.1% ($72.6M) | 21.9% | 17.0% | 2.6% |
| EDGE | 15.3% | 11.3% | 8.8% | 4.8% |
| WR | 14.4% | 11.5% | 9.9% | 4.8% |
| DT | 12.7% | 9.9% | 7.7% | 3.4% |
| T | 12.6% | 10.1% | 9.3% | 3.4% |
| LB (off-ball) | 10.8% | 7.2% | 5.6% | 1.7% |
| CB | 10.6% | 9.7% | 7.9% | 3.5% |
| S | 9.6% | 7.4% | 6.2% | 1.9% |
| G | 8.8% | 7.8% | 5.1% | 2.0% |
| RB | 8.1% | 6.6% | 3.4% | 1.2% |
| TE | 7.8% | 6.8% | 5.3% | 1.7% |
| C | 7.4% | 6.2% | 3.4% | 0.7% |
| K | 2.7% | 2.4% | 2.2% | 0.4% |
| P | 2.0% | 1.5% | 1.2% | 0.4% |
| FB | 3.0% | 1.5% | 0.7% | - |
| LS | 0.8% | 0.6% | 0.6% | 0.4% |

Since 2022 the QB top has drifted down as a share (2025: ~$55-60M on a $279M cap = ~20-21.5%),
and WR/EDGE tops have risen (~14-16%). Treat the shape as right, the exact top as ±2 points.

## How the market is built (veteran deals 2017-22)
- **Most deals are minimums.** 76-87% of veteran deals at every position are ≤0.65% of the cap
  (veteran-minimum level), and ~75-80% are 1-year deals. The median veteran deal is 0.3-0.4% of
  the cap at every position. Free agency AI should fill most of a roster this way.
- **Market deals (1%+ of the cap) per season, league-wide:** WR 41, DT 37, CB 36, EDGE 36, LB 30,
  S 27, T 27, G 24, QB 22, TE 22, RB 19, C 13, K 11, P 7, FB 3. Median 1.8-2.8% of the cap.
  Average new years 2.0-2.3 (lots of 1-2 year "prove it" deals); guaranteed share ~46-53% of
  total value (QB 67%).
- **Big deals (5%+ of the cap), 2019-22: 321 deals; years 4: 90, 3: 86, 1: 61, 5: 46, 2: 32, 6+: 6.**
  Almost all the 1-year big deals are **franchise / transition tags**. So the real top of free
  agency is 3-5 years, with the tag as the 1-year alternative.
- **Age:** market deals peak at **26-27** (34-50% of each position's market deals), then
  28-29 (15-27%), 30-31 (6-14%), 32+ (7-13%, except QB 34% and K/P 31-35%: long careers).
  RBs skew young (29% of market deals at ≤25, i.e. second contracts right after rookie deals),
  and money falls off after 28 (median market RB deal 2.3% at 26-27 vs 1.3% at 28-29).
  Contract length falls with age: 32+ market deals average 1.3-1.8 years vs 2.0-2.8 at ≤27.
- **Top-10% deals by position:** average 2.0 years (RB) to 3.0 (T), guarantees ~50% (QB 75%,
  EDGE 62%), median age 27 (QB 29, K 31, LS 32).
- **Where the money goes (share of all active cap dollars, 2022):** WR 12.7%, EDGE 11.7%,
  CB 10.5%, QB 10.3%, T 9.8%, DT 9.5%, LB 6.7%, S 6.5%, G 5.9%, TE 5.4%, RB 4.9%, C 2.9%,
  K 1.4%, P 0.8%, LS 0.5%, FB 0.4%.

## Rookie wage scale (median APY as % of cap, by round, 2017-22)
R1 1.9% (top picks ~4-5%) · R2 0.85% · R3 0.6% · R4 0.5% · R5-7 0.4% (≈ minimum).

## Practice squad pay (2026)
$13,750/week for 2 or fewer accrued seasons; veterans $18,350-$22,850/week; 18 weeks, no bonuses
(≈ $0.25-0.41M a season). Counts against the cap.

## Ideas for the FA AI (anti-exploit, per CLAUDE.md "underpriced free agents")
- Price from the position ladder: a player's asking APY ≈ the ladder value at his rank among
  the league's players at his position, times an age factor, with the 1%-cap line splitting
  "market" from "minimum" players. Never let a top-10 player at a position sign near the minimum.
- 26-28-year-old starters get 3-5 years; 30+ get 1-2 years; RBs lose value fastest after 28.
- Good players rarely reach free agency: teams tag or extend their best (61 of 321 big deals were
  one-year tags). The open market is mostly mid-tier players plus minimum depth.
- Guarantees ~50% of value overall; ~65-75% for QBs and top EDGE.

## Not covered (data limits)
- Free agency signings vs extensions vs re-signings aren't marked in this file. Separating them
  needs the newer OTC data (`season_history`/team changes) or the nflverse `trades`/weekly rosters
  (team change between seasons ⇒ FA move).
- Contract structure (signing bonus proration, cap hit by year, dead money) isn't in this file.
