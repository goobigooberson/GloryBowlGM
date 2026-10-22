# Player development: review for Blake (updated Oct 21, afternoon)

Everything below is on the **new rating scale** you picked (median NFL
player = 50). Careers come from test leagues simmed 15 full seasons with real
games on the final settings. Each line is a player's **overall / potential**
at each training camp; the first number is when he entered the league (or
2026 for players already in it).

What to judge: do these read like real careers? Is there enough drama, or
too much? Every number can be turned up or down (see "Knobs" at the end).

## What changed today, from your three requests

1. **Rating scale: median NFL player = 50.** Only what's shown changed; the
   engine's internal ratings (and so every game result) are the same. On
   screen: typical player ~50, average starter 61-63, backups high 30s,
   ~40-70 players 80+ and ~8-14 at 90+ per league. One curve for every
   position, so QBs are still the scarcest and most kickers still read "Good".
   Two side effects: rookies look rough (a late-round rookie often shows
   15-25, since rookies come in about 70% developed), and emergency
   out-of-position fill-ins show 8-18.
2. **Peak years from real players** (1999-2025 NFL data, each player compared
   with himself season to season). Real players peak earlier than FOF8's
   examples:

   | Position | Prime (pro seasons) | | Position | Prime |
   |---|---|---|---|---|
   | QB | 2-9 | | DE | 3-9 |
   | RB | 2-6 | | DT | 3-8 |
   | WR | 2-6 | | OLB / ILB | 2-8 |
   | TE | 3-8 | | CB | 2-7 |
   | T, C | 3-10 | | S | 3-8 |
   | G | 3-8 | | K | 1-9 (declines at half speed) |
   | FB | 2-7 (estimate) | | P, LS | 1-14 (slow decline; LS an estimate) |

   Young players also grow into their prime faster now, as real players do
   (most reach it by season 2-4).
3. **Specific injuries with lasting effects.** About 45 injury types, from a
   high ankle sprain to a torn ACL, torn Achilles or neck surgery. Each can
   cause a temporary step back (he comes to camp below his level and gets
   70-100% of it back the next year), a permanent loss (physical skills hit
   hardest) and extra retirement odds. How long players miss is unchanged.

## How injuries play out (5 real-game seasons, every serious injury followed)

| Injury | Per season | Retired / gone right after | Overall at next camp | Two camps later |
|---|---|---|---|---|
| Torn ACL | ~41 (real NFL ~47-62 incl. preseason/practice) | 18% | -3.0 | +3.9 |
| Torn Achilles | ~12 (real ~10-25) | 22% | -10.6 | -0.6 |
| Lisfranc | ~19 | 20% | -0.9 | +3.4 |
| Major knee injury | ~16 | 20% | -1.2 | +3.5 |

(Young players keep growing through an injury, which is why ACL players are
often higher two years later. The Achilles is the career-changer, as in the
real NFL, where about a third never return and returners often lose a lot.)

Examples:
- DT Eli James, torn ACL at 25: 84/91 | 84/87 | **77/91** | 87/87 | 87/90 (a lost year, then all the way back)
- CB Jack Chambers, torn ACL at 28: 79/82 | **71/77** | 69/75 | 71/71, retired at 31 (never the same)
- G Devon Thompson, torn Achilles at 30: 67/67 | 67/68 | **48/61** | 60/61 | 56/56 (partial comeback, then fades)
- RB Quincy Payne, torn ACL at 26: 64/71 | 69/69 | **65/71** | 70/71 | 69/70 (one down year)

## League-wide (final settings, 3 leagues x 15 real-game seasons)

| Measure | Result | Target |
|---|---|---|
| Players whose potential moves 0-3 points a year | 90% | 88-90% |
| League level, start -> 15 years later | steady (within ~1 internal point) | steady |
| Players showing 90+ after 15 seasons | 3-15 (fresh league 10-15) | like a new league |
| Players showing 80+ after 15 seasons | 39-57 (fresh league 49-71) | like a new league |
| Points per team game | 22.9-23.1 | real 22.6 |
| Stat measures outside the real range, aged league | 40-45 of 282 | fresh league: 33-37 |

## Homegrown stars (drafted after the league began, not Generational)

48 players in one league reached 85+ over 15 seasons. Examples:
- WR Mason Bradley (round 1): 62/95 | 71/95 | 80/96 | 87/98 | 92/99 | 94/96 | 95/96 | 94/94 | 92/92 | 87/87 | 80/80 | 75/75 (star by year 5, gone by 33)
- DE Isaiah Harper (round 1): 67/91 | 72/91 | 80/94 | 85/94 | 84/92 | 87/92 | 91/95 | 90/96 | 94/95 (late bloomer, still rising in year 9)
- T Gabe Ramsey (round 1): 56/94 | 69/95 | 79/96 | 82/87 | 87/91 | 91/94 | 92/96 | 91/92 | 92/92 | 92/92 | 90/90 | 80/80 | 75/75 | 72/72 (long prime, tackles last)
- OLB Dean Fletcher (round 1): 68/92 | 75/94 | 84/96 | 87/95 | 90/95 | 91/95 | 91/95 | 92/95 | 90/92 | 85/85 | 82/82 | 77/77

## Breakouts, busts and comebacks

- RB Seth Carter (round 4): 23/64 | **48/66** | 57/66 | 61/65 | 62/66 | 64/68 | 65/65 | 63/63 (a fourth-rounder who becomes a starter)
- DE Austin Woods (round 5): 23/60 | 41/59 | 51/62 | 54/62 | 59/64 | 56/63 (late-round pick turned rotation player)
- DE Kendrick King (round 7): 17/48 | 23/35 | 28/39 | 33/37 | 35/43 | 37/43 | **43/51** | 43/46 | 45/49 (written off, keeps hanging on)
- S Jackson Bell (round 4, very volatile): 18/53 | 26/49 | 39/52 | 43/49 | 41/48 | **35/51** | 46/56 | 48/52 | 48/49 | 45/45 (up and down)
- G Mark Burns (undrafted): 21/41 | **35/58** | 45/54 | 48/51 (undrafted surprise)
- CB Xavier Jones (round 4): 21/51 ... 51/51 | 49/49 | 46/48 | 46/46 | 45/48 | **23/23** (collapses at 32 and retires; the test doesn't record which injury, if any)

## Generational players

- S Clay Booker: 62/92 | 70/92 | 77/92 | 84/94 | 87/94 | 90/94 | 92/94 | 92/94 | 91/92
- WR Devon Chapman: 69/96 | 76/96 | 84/98 | 87/96 | **90/95** | 87/90 | 84/85 | 79/79 | 74/74 | 70/70 (peaks at 28, fades in his early 30s, like real receivers)

## Your calls

- Do these careers read like real ones? Too much drama, too little?
- Injuries: is the Achilles harsh enough (or too harsh)? ACL about right?
- Kickers, punters and snappers take about a third of the 80+ spots on the
  new scale (your earlier "most kickers are good"). Keep, or rate them
  lower?
- Rookies showing 15-25: fine (they aren't good yet), or should rookies'
  current ratings start higher?
- Peak years for FB and LS are my estimates (no usable data).

## Knobs

`engine/development.py`: `LONG_SD` / `SWING_SD` (movement), `TAIL_DF` /
`TAIL_LIMIT` (rare big moves), `GROWTH_SHARE` (how fast young players grow),
`PEAK_SEASONS` / `DECLINE_BASE` / `DECLINE_GROWTH` / `DECLINE_SCALE` (aging),
`LEAN_BY_STAGE`, `INJURY_MENTAL_SHARE`, `COMEBACK_SHARE`.
`engine/injuries.py`: every injury's step-back, lasting-loss and retirement odds.
`engine/offseason.py`: rookie classes (`ROOKIE_POOL`, `ROOKIE_LEVEL_SHIFT`,
`SHIFT_TAPER_FULL` / `SHIFT_TAPER_TOP`), `GENERATIONAL_CAREER`.
`engine/scale.py`: the shown rating scale (rebuilt by `tools/build_rating_scale.py`).
