# How real NFL teams draft (benchmarks for the Step 8 draft AI)

Blake: "i want the draft to just feel absolutely accurate and real." These are measured targets
the draft AI can be checked against, the same way the sim was calibrated.
Data: local nflverse files. Full numbers: `real_draft_ai.json`; script: `draft_ai.py`.
Companion: `real_draft_summary.md` (pick value, hit rates by slot/position/round, composition, combine).

## 1. Teams follow the consensus board closely, with real scatter
ESPN final big board vs actual picks, 2023 (the only year in the file; 89 top-100 players
matched by name, so treat it as a rough guide):
- Rank and pick correlate 0.88 (log scale).
- How far players land from their rank (median absolute gap): **top 10: 3 picks; ranks 11-32:
  5; ranks 33-64: 14; ranks 65-100: 22.** 80% ranges: ranks 11-32 went 13 picks earlier to 18
  later; ranks 65-100 went 28 earlier to 95 later.
- Falls are bigger than reaches: big reaches are ~15-30 picks (Gibbs ranked 28 → pick 12, Jack
  Campbell 51 → 18, LaPorta 55 → 34), while falls can be 70-120 picks (A.T. Perry 74 → 195,
  Antonio Johnson 61 → 160), usually medical or off-field reasons the board ignored.
- So the AI board should be each team's own noisy view of a shared "true" ranking: very tight at
  the top, widening fast after round 1, with occasional big falls (medicals, character) and
  smaller reaches (a team's scheme fit or need).

## 2. Need matters, but less than you'd think (except QB and TE)
Chance a team takes the position in rounds 1-2, normally vs when it used a 1st-rounder there in
the previous 3 drafts (2003-26):

| Pos | Normally | After a recent R1 there | Effect |
|---|---|---|---|
| QB | 15% | 6% | strong |
| TE | 10% | 3% | strong |
| RB | 15% | 7% | strong |
| WR | 32% | 16% | strong |
| DT | 20% | 11% | moderate |
| LB | 24% | 17% | moderate |
| DE | 22% | 17% | weak |
| OL | 36% | 29% | weak (5 starters to fill) |
| DB | 37% | 34% | none (4-5 starters, always needed) |

Positions with one starter (QB, TE, RB) are strongly need-driven; OL and DB are drafted almost
regardless of recent picks.

## 3. QBs: never over a good young starter (the FOF8 exploit)
Team's main passer last season (most attempts), and how often the team took a QB in round 1:
- **Young (drafted R1-2 within 4 years) and good (350+ attempts, EPA/attempt ≥ 0.10): 0 of 58
  team-drafts took a QB in rounds 1-2.**
- Young but not good: 5.4% R1 QB (7.2% R1-2).
- Older and good: 3.0% R1 (5.5% R1-2): the successor pick for an aging star.
- Older and not good: **17.2% R1 (21.2% R1-2)**: this is where QBs go.
Rule for the AI: a good young starter blocks an early QB pick almost completely.

## 4. Draft-day trades happen at the Jimmy Johnson chart
Same-year pick-for-pick trades 2010-26 (no players or future picks): **358, about 21 per draft**.
The team moving up gave (by Johnson chart value) / what it got:

| Top pick in the deal | Trades | Johnson ratio | Real-outcome ratio | Spots moved |
|---|---|---|---|---|
| 1-10 | 13 | 0.99 | 1.38 | 5 |
| 11-32 | 46 | 1.01 | 1.40 | 5 |
| 33-64 | 95 | 1.00 | 1.32 | 7 |
| 65-128 | 106 | 0.98 | 1.42 | 10 |
| 129+ | 98 | 1.12 | 1.51 | 12 |

Real teams still price trades almost exactly on the Johnson chart, even though by real career
outcomes the team moving up overpays by ~30-50%. Median deal: 2 picks for 1, moving up 5-12 spots.
For the AI: price trades with the Johnson chart (that's what real teams do), and let a smart user
profit a little by trading down, as smart real teams (e.g. analytics-leaning ones) do. AI teams
shouldn't accept less than chart value; that blocks pick-farming.

## 5. Age at draft: younger prospects beat their slot
Career AV relative to a typical player at the same pick (2000-18 classes; compare across rows):
21 or younger 1.22 · 22: 1.25 · 23: 1.03 · **24+: 0.88**. Players 23 and older underperform their
slot, so real teams underrate age. A good AI should value youth a bit more than real teams do
(since prospects' ages are visible, a sharp user would exploit an AI that ignores it).

## 6. Combine: mostly priced in, except a few drills
Correlation of each drill (+ = better result) with beating your draft slot, 2000-18:
- **RB: 40 time +0.25, 3-cone +0.22, weight −0.21** (lighter, faster backs beat their slot).
- **TE: 40 time +0.23, vertical +0.17.**
- LB: shuttle +0.19, 3-cone +0.17, 40 +0.15. QB: broad jump +0.18. OL: shuttle +0.15.
- WR, DB, DE: ≈0 (teams already price their athleticism in).
These are small effects: the combine should nudge the AI's view a little, never override tape.

## 7. Some teams really are better drafters
Each team's average career AV relative to slot, odd-numbered vs even-numbered drafts 2000-18:
correlation **0.53**, so drafting skill persists. Spread: best team 1.58, worst 0.74, middle half
0.96-1.16. (Part of this is team quality: good teams give rookies more snaps and starts.) For the
AI: give each AI front office its own scouting accuracy, so some teams draft consistently better.
That connects naturally to coaches/GMs and to interview-based scouting.
