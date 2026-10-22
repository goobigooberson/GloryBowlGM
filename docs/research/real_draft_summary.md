# Real NFL draft value (prep for Step 8: the draft)

Data: nflverse `draft_picks.csv` (PFR career data, current through the 2026 draft) and
`combine.csv`, all local. Full numbers: `real_draft.json`; script: `draft_value.py` (same folder).
Outcomes use the **2000-2018 classes** (careers mostly played out); draft composition uses
**2014-2026**. "Career AV" = PFR's weighted career Approximate Value (a rough all-position value
score; it undervalues TEs and OL a bit). "Starter 3+" = started 3+ seasons.

## Pick value chart (career-AV based, pick 1 = 3000)
| Pick | 1 | 2 | 3 | 5 | 10 | 16 | 20 | 32 | 48 | 64 | 96 | 128 | 160 | 192 | 224 | 256 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Real outcomes | 3000 | 2452 | 2298 | 2098 | 1856 | 1729 | 1472 | 1386 | 1054 | 962 | 648 | 519 | 358 | 279 | 237 | 222 |
| Jimmy Johnson | 3000 | 2600 | 2200 | 1700 | 1300 | 1000 | 850 | 590 | 420 | 270 | 116 | 43 | 27 | 15 | 4 | - |

Real outcomes fall off far more gently than the Johnson chart teams historically traded by:
the 1st pick produces ~2.2 times a 32nd pick (Johnson: 5.1 times), and a 7th-rounder still has ~7%
of the 1st pick's value (Johnson: ~0). Real trades sit in between (modern teams use Rich Hill /
Fitzgerald-Spielberger-style charts that are flatter than Johnson). For the AI: **trade with a
chart between the two, and value late picks above zero**, or the user can farm picks.

## What a pick slot gets you (all positions)
| Picks | Career AV | Starter 3+ seasons | Starter 5+ | Pro Bowl | Never started | <16 career games |
|---|---|---|---|---|---|---|
| 1-5 | 59.7 | 93% | 77% | 62% | 2% | 1% |
| 6-10 | 46.9 | 82% | 67% | 51% | 4% | 0% |
| 11-20 | 45.0 | 86% | 66% | 48% | 6% | 1% |
| 21-32 | 36.5 | 64% | 49% | 33% | 11% | 2% |
| 33-48 | 31.4 | 67% | 46% | 24% | 15% | 2% |
| 49-64 | 25.6 | 49% | 35% | 19% | 26% | 8% |
| 65-100 | 19.4 | 38% | 25% | 11% | 38% | 12% |
| 101-140 | 14.1 | 25% | 15% | 7% | 50% | 21% |
| 141-180 | 9.8 | 19% | 10% | 6% | 65% | 34% |
| 181-220 | 7.2 | 11% | 6% | 3% | 74% | 44% |
| 221-256 | 6.2 | 9% | 5% | 2.5% | 77% | 52% |

Use these as targets for the game's draft classes plus development: e.g. about 1 in 3 late
first-rounders becomes a Pro Bowler, about 1 in 10 sixth/seventh-rounders becomes a 3-year starter.

## By position and round: starter 3+ seasons / Pro Bowl rate (2000-18)
| Pos | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|---|---|---|---|---|---|---|
| QB | 76% / 51% | 35% / 20% | 20% / 12% | 19% / 12% | 0% / 0% | 9% / 9% | 5% / 3% |
| RB | 74 / 53 | 38 / 26 | 18 / 16 | 20 / 12 | 12 / 11 | 6 / 4 | 6 / 1 |
| WR | 71 / 28 | 55 / 24 | 30 / 14 | 15 / 6 | 15 / 7 | 7 / 7 | 6 / 2 |
| TE | 86 / 64 | 55 / 19 | 55 / 21 | 33 / 8 | 33 / 4 | 16 / 0 | 7 / 4 |
| OL | 91 / 48 | 76 / 23 | 58 / 14 | 29 / 5 | 22 / 6 | 21 / 3 | 16 / 2 |
| DE | 71 / 38 | 45 / 15 | 41 / 11 | 40 / 12 | 23 / 12 | 9 / 2 | 10 / 3 |
| DT | 76 / 36 | 63 / 12 | 36 / 8 | 32 / 6 | 32 / 6 | 15 / 0 | 7 / 0 |
| LB | 82 / 56 | 66 / 25 | 40 / 9 | 28 / 5 | 17 / 3 | 12 / 2 | 5 / 1 |
| DB | 77 / 47 | 61 / 18 | 31 / 5 | 21 / 6 | 19 / 5 | 13 / 4 | 9 / 2 |

QBs are boom-or-bust: R2-R4 QBs start 3+ seasons only 19-35% of the time, R5+ almost never.
OL is the safest pick at every round (91% R1, 58% R3). K/P are mostly late picks and often hit.

## Tight ends (the FOF8 "TEs fall late" exploit)
- Real drafts take **~15 TEs a year: R1 1.0, R2 2.1, R3 2.6, R4 2.4, R5 2.9, R6 1.7, R7 2.2**.
  The first TE goes at **pick 19** (median, 2014-26), vs QB 1, DE 3, WR 5, OL 6, DB 6, LB 8,
  RB 10, DT 12.
- Good TEs (5+ seasons started or a Pro Bowl), 2000-18: 67 of 282 drafted, by round
  **18 / 11 / 15 / 10 / 6 / 3 / 4**. Pro Bowl TEs by round: **14 / 6 / 9 / 3 / 2 / 0 / 2**.
  So real teams do find starting TEs in rounds 2-4, but Pro Bowl TEs after round 3 are rare
  (7 of 38). If the game's top TE prospects are lasting to round 4+ while being Pro Bowl
  talents, the AI is undervaluing them; a first-round TE talent should go in round 1-2.
- Real R1 TEs hit at the highest rate of any position (86% become 3+ year starters, 64% make a
  Pro Bowl; small sample, 22 players).

## Draft composition: picks per draft by position (2014-26 average, 257 picks)
DB 52.1 · OL 44.2 · WR 32.8 · LB 29.8 · DT 24.6 · RB 21.4 · DE 20.8 · TE 14.8 · QB 11.6 · K/P/LS 4.5.
Round 1: OL 6.5, DB 5.4, WR 4.5, LB 3.5, DT 3.2, QB 3.2, DE 3.0, RB 1.4, TE 1.0.
QBs: 3.2 in round 1, then only 0.7 in round 2 (teams take a QB early or wait).
Age at draft: R1 21.8, R2 22.1, R3 22.4, R4-5 22.5, R6 22.7, R7 22.8.
(PFR lists many 3-4 edge rushers as LB, so DE looks smaller and LB bigger than "edge" really is.)

## Combine (real units): rounds 1-2 vs rounds 3-7 averages
| Pos | 40 (s) | Vertical (in) | Broad (in) | 3-cone (s) | Bench (reps) | Weight |
|---|---|---|---|---|---|---|
| QB | 4.75 / 4.83 | 32.6 / 31.3 | 115 / 110 | 7.02 / 7.17 | - | 225 / 221 |
| RB | 4.48 / 4.57 | 36.2 / 34.2 | 122 / 118 | 6.96 / 7.10 | 21 / 20 | 218 / 218 |
| WR | 4.45 / 4.49 | 36.8 / 35.7 | 124 / 122 | 6.93 / 6.94 | 16 / 15 | 203 / 200 |
| TE | 4.67 / 4.74 | 35.0 / 33.4 | 120 / 116 | 7.09 / 7.17 | 23 / 20 | 254 / 253 |
| OL | 5.15 / 5.24 | 29.4 / 28.2 | 106 / 103 | 7.72 / 7.80 | 27 / 26 | 316 / 313 |
| DE | 4.73 / 4.80 | 34.1 / 33.7 | 118 / 116 | 7.21 / 7.30 | 25 / 24 | 267 / 265 |
| DT | 5.01 / 5.07 | 30.3 / 29.6 | 108 / 107 | 7.59 / 7.67 | 29 / 27 | 306 / 304 |
| LB | 4.62 / 4.68 | 35.5 / 34.3 | 120 / 118 | 7.08 / 7.12 | 23 / 23 | 242 / 239 |
| DB | 4.46 / 4.51 | 37.0 / 36.0 | 125 / 122 | 6.90 / 6.96 | 16 / 16 | 199 / 199 |

The gaps are small (0.04-0.09 s in the 40): real teams draft on tape far more than on the combine,
so the game's combine should be a weak signal of a prospect's ratings, not a strong one.
Full per-position distributions (mean, SD, 10th/50th/90th percentile, min, max) for height,
weight and all six drills are in `real_draft.json` under `combine_by_position`.
