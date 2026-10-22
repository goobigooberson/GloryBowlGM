# Real offseason movement and practice squad makeup

Data: nflverse weekly rosters (local). Full numbers: `real_movement.json`; script: `real_movement.py`.

## Offseason movement (2018-19 through 2024-25 offseasons)
Players on a 53 or a reserve list in their last regular-season week of season Y (~2,140 a
season, ~67 per team), and where they are in week 1 of Y+1:

- **Same team 66% · new team 24% · on no team 10%** (retired, unsigned, or back later in the season).
- So about **16 players per team per offseason land on a different team** (free agency, trades,
  cuts/claims together), and ~7 leave the league.

By experience at the end of season Y:
| Seasons | Players/season | Same team | New team | On no team |
|---|---|---|---|---|
| 0-2 | 990 | 81% | 14% | 5% |
| 3-4 | 473 | 54% | 37% | 9% |
| 5-7 | 441 | 54% | 32% | 14% |
| 8+ | 238 | 47% | 25% | 28% |

The big wave is players coming off rookie contracts (3-4 seasons: 37% switch teams). 8+ year
veterans mostly either stay or are done (28% on no team: retirements and unsigned vets).

By position (new team / on no team): QB 32% / 8% (backup QB carousel), WR 26% / 9%, DL 25% / 10%,
TE 24% / 11%, DB 24% / 10%, LB 24% / 12%, RB 23% / 12%, OL 22% / 10%, K 18% / 15%, P 16% / 9%,
LS 9% / 12% (long snappers stay put).

## Practice squad makeup (regular-season weeks, 2022-25)
Real squads average **15.2 players** (not always full). Per squad, by depth-chart position:

| Pos | Real | Game's PS_TEMPLATE |
|---|---|---|
| WR | 2.60 | 2 |
| CB | 1.50 (+0.34 generic DB) | 2 |
| DT | 1.35 | 1 |
| T | 1.35 | 1 |
| TE | 1.17 | 1 |
| RB | 1.13 | 1 |
| DE | 1.02 | 2 |
| G | 0.95 | 1 |
| S | 0.92 | 1 |
| ILB | 0.88 | 1 |
| OLB | 0.70 | 1 |
| QB | 0.59 | 1 |
| C | 0.48 | 1 |
| K | 0.13 | 0 |
| FB / P / LS | 0.04 / 0.02 / 0.01 | 0 |

The template is close. Real squads carry a 3rd WR more often than not, and a QB only 59% of the
time. They carry a center only about half the time. DE+OLB together is 1.7 vs the template's 3.
Experience on real squads: 0 seasons 31%, 1 season 18%, 2 seasons 15%, 3+ seasons 36% (≈5.4
veterans of the 6 allowed).
