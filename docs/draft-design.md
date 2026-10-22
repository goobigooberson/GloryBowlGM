# The draft (Step 8): design, test results, and decisions for Blake

Built overnight Oct 21-22 while you slept. You said: "i want the draft to just feel
absolutely accurate and real." Everything below was checked against real NFL draft data
(nflverse, in `docs/research/`) with a new tool, `tools/draft_check.py`.

**Anything marked PROVISIONAL is a feel or design choice I made so the work could go on.
It's yours to change.** Each one lists the options and my recommendation. The full list
is in section 9.

Plain-language terms used below:
- **Grade**: how good a prospect is compared with the league's starters at his position.
  0 means as good as an average starter, +1 means one "spread" better (about the gap
  between an average starter and a Pro Bowl-level one).
- **Board**: a team's ranked list of prospects. Every team has its own.
- **Consensus**: what the league's scouts think as a group (like the public big boards on
  ESPN), before each team adds its own opinion.

---

## 1. What's built

| File | What it does |
|---|---|
| `engine/draft.py` | The draft class, every team's board, the AI's picks, draft-day trades, signing undrafted rookies, the "draft capital" depth-chart nudge, made-up street free agents at a realistic level, and a first version of the startup draft. |
| `engine/scouting.py` | What *your* staff knows about each prospect: grades shown as ranges that tighten as you scout, combine interviews, top-30 visits, red flags. |
| `tools/draft_lab.py` | A fast test harness. It runs the real offseason and training camp year after year but skips the games, so 22 seasons in 6 leagues take about 3 minutes. |
| `tools/draft_outcomes.py` | Follows every pick's career: seasons as a starter, Pro Bowls, never started, starts in years 1-4. |
| `tools/draft_check.py` | Prints the sim next to the real NFL for every draft benchmark and writes `tools/draft_report.txt`. Run it with `python tools/draft_check.py`. |

The main session wired the draft into the game's offseason on Oct 22 (section 11). **Since
Oct 23 the draft screens exist** (section 13): you scout the class during free agency,
draft live in the Draft tab (with trades and save/load mid-draft), and can start a new
league with a startup draft where you make your own picks.

---

## 2. How a draft class is made

1. **Who's in it.** For each position the game makes a big pool of college prospects
   (2.5 for every spot in the class) and the best of them make the class. Each position's
   share of the class follows the real NFL's mix of new players: real draft picks there
   (2014-26) plus the undrafted players who make it, so most kickers, snappers and
   fullbacks arrive undrafted, as in the real NFL. A position gets a few more prospects
   when the league is short of players there, a few fewer when it's long. QB classes are
   a bit smaller than the real share, because QBs last longer in this game. (Until Oct 23
   classes were sized by roster openings at draft time. With 90-man camps that made WR
   classes too small: 19.7 WRs drafted a draft vs real 28.6.) The class also carries a
   "fringe" of long shots (40% more) who usually go undrafted. They sign to camp rosters and
   practice squads, like the ~500 undrafted rookies real teams sign each year.
2. **Level.** The class is set 10 rating points below the pool it came from, with less
   taken off the very top prospects. This keeps the league's overall level steady over
   the decades instead of creeping up. Each position has its own small adjustment, so no
   position slowly gets better or worse than the others. Measured over 22 seasons (Oct 23,
   with free agency and 90-man camps): every position's starters stay within about 2
   points of where they began.
3. **Age.** Real ages at the draft: the best prospects are often 21-year-old juniors,
   late-rounders 22-23. Sim by round: R1 21.9, R7 22.6 (real 21.8 and 22.8).
4. **Readiness.** This is how much of his ceiling a prospect already has, about 88% on
   average, a bit more for older prospects. This is the big change from the placeholder,
   which made every rookie 70% developed and 8 points weaker, so rookies almost never
   started. Real NFL rookies are mostly finished products: about 8 in 10 top-5 picks
   start right away.
5. **Combine.** Results come from the player's hidden athletic traits, as before. The
   gaps between early and late picks match real ones (e.g. the 40 for early vs late DBs:
   sim 4.44 vs 4.48, real 4.46 vs 4.51). That makes the combine a weak hint, like the real
   one: teams draft on tape.
6. **Red flags.** About 5% of prospects carry one. Medical flags are real: the player's
   hidden durability really is low. Character flags only drop him on boards for now,
   because the game has no off-field system yet (see decision D8). The public big boards
   don't know about flags, so flagged players "fall": about 3-4 falls of 60+ picks per
   draft.
7. **Generational players** appear about once every 2-3 drafts, following the existing
   rules, including the limits on Generational K/P/LS/FB.

## 3. How the AI teams draft

- **Their boards** are the consensus plus each team's own opinion. The consensus is close
  to the truth for the obvious top prospects and fuzzier lower down. Its misses are
  limited in size, so a nobody never looks like a top-10 talent. Better front offices see
  through part of the consensus's mistakes.
- **Front-office skill persists.** Every team has a hidden scouting skill, kept for the
  whole save. Real NFL: how well a team drafts in odd years predicts its even years
  (correlation 0.53). Sim: 0.60.
- **Position value.** A franchise QB goes early, a merely good QB prospect waits, kickers
  go late, and backs are discounted unless they're special. This was tuned so each
  round's mix of positions matches real 2014-26 drafts.
- **Need.** A team leans toward positions where a prospect would replace its weakest
  starter. It is much less keen on a position where it took a high pick in the last 3
  drafts. This is strongest at one-man positions (QB, TE, RB) and weak at OL and DB,
  exactly the real pattern. It also avoids taking a third WR in the same draft.
- **QB rule (FOF8 exploit).** A team with a young, good starting QB never takes a QB in
  rounds 1-2. That's a hard rule, matching the real 0 of 58. The other QB situations
  match the real rates (see the results).
- **Age.** Older prospects have less growing left and shorter careers. Real teams only
  partly price that in, the best front offices more.
- **Draft-day trades.** A team that badly wants a player still on the board trades up
  4-24 spots. It pays by the Jimmy Johnson chart, which is what real teams use (real
  deals average 0.98-1.01 of chart value). **Trades with you always have to be at least
  full chart value** for the AI, which blocks pick-farming. When you're on the clock, AI
  teams call you with offers.
- **Draft capital.** Real staffs give high picks a chance to start (they invested a high
  pick). Without this, 15% of the sim's top-5 picks never started a game (real 2%).
  AI depth charts give a young high pick a small nudge: a 1st-rounder +2.5 rating points
  in year 1, a top-10 pick +6, fading over 3 years. It applies only when the AI sets a
  depth chart, never in games and never on your chart.
- **Undrafted signings** use each team's scouting opinion, not the player's true ratings.
  The placeholder let teams see through every undrafted rookie.

## 4. Test results vs the real NFL

From `tools/draft_report.txt`: 6 generated leagues x 22 seasons, 132 drafts, about 17,500
careers followed for 8-19 seasons. "Starter" in the sim = a starter on his team's depth
chart at camp and not out 9+ games. Real = PFR's seasons as a starter.

**What a pick slot gets you** (sim | real 2000-18 classes)

| Picks | Starter 3+ seasons | Starter 5+ | Pro Bowl | Never started | Starts as a rookie (real: 50%+ of snaps) |
|---|---|---|---|---|---|
| 1-5 | 90% / 93% | 84% / 77% | 68% / 62% | 2% / 2% | 83% / 82% |
| 6-10 | 88 / 82 | 77 / 67 | 56 / 50 | 5 / 4 | 78 / 72 |
| 11-20 | 83 / 86 | 76 / 66 | 48 / 48 | 6 / 6 | 70 / 67 |
| 21-32 | 80 / 64 | 66 / 49 | 36 / 33 | 10 / 10 | 61 / 47 |
| 33-48 | 62 / 67 | 50 / 46 | 21 / 24 | 22 / 14 | 47 / 46 |
| 49-64 | 58 / 49 | 45 / 34 | 16 / 19 | 26 / 26 | 42 / 38 |
| 65-100 | 36 / 38 | 25 / 25 | 7 / 11 | 47 / 38 | 21 / 22 |
| 101-140 | 20 / 24 | 13 / 15 | 3 / 7 | 65 / 50 | 9 / 10 |
| 141-180 | 12 / 19 | 7 / 10 | 1 / 6 | 77 / 65 | 4 / 9 |
| 181-220 | 8 / 11 | 5 / 6 | 1 / 3 | 83 / 74 | 2 / 5 |

By round, starter 3+ / Pro Bowl: R1 84/48 (real 78/45), R2 60/18 (58/21), R3 38/7
(38/11), R4 23/4 (25/7), R5 14/2 (20/7), R6 9/1 (12/4), R7 7/1 (9/2).

**The AI's behavior** (sim | real)

| Benchmark | Sim | Real |
|---|---|---|
| Drafted rookies among starters | 8% | 8% |
| Rookies on 53-man rosters | 15% | 12% |
| Typical gap between big-board rank and actual pick: ranked 1-10 / 11-32 / 33-64 / 65-100 | 2 / 7 / 13 / 19 | 3 / 5 / 14 / 22 |
| Board-pick correlation | 0.85 | 0.88 |
| Takes the position in R1-2 normally / after a recent 1st-rounder there: QB | 12% / 4% | 15% / 6% |
| ... TE | 8% / 2% | 10% / 3% |
| ... WR | 30% / 14% | 32% / 16% |
| ... DB | 45% / 35% | 37% / 34% |
| QB in round 1: young good starter / young not good / older good / older not good | 0 / 3 / 2 / 12% | 0 / 5 / 3 / 17% |
| Draft-day trades per draft | 19.6 | 18.4 (21.1 per 257 picks) |
| Trade price (Jimmy Johnson chart ratio), by top pick 1-10 / 11-32 / 33-64 / 65-128 / 129+ | 1.08 / 1.05 / 1.03 / 1.06 / 1.18 | 0.99 / 1.01 / 1.00 / 0.98 / 1.12 |
| Front-office drafting skill, odd vs even years | 0.60 | 0.53 |
| Age at the draft, R1 / R7 | 21.9 / 22.6 | 21.8 / 22.8 |
| Career value vs slot, age 21 or younger / 22 / 23 / 24+ | 1.12 / 1.04 / 0.88 / 0.70 | 1.22 / 1.25 / 1.03 / 0.88 |
| First pick at each position (median): QB / DE / WR / OL / DB / LB / RB / DT / TE | 3 / 6 / 6 / 4 / 5 / 12 / 18 / 7 / 23 | 1 / 3 / 5 / 6 / 6 / 8 / 10 / 12 / 19 |
| Pro Bowlers per class / selections each / only once | 26 / 3.2 / 37% | 31 / 3.0 / 38% |

**The league over 22 seasons:** shown median rating 52 at the start, 54-55 later.
Starters' internal average 68 to 69. 80+ players 62-78 at the start, 49-62 later. 90+
players 10-20 throughout. Every position's starters stay within about 3 points.

**What matches well:** top-pick outcomes, round-by-round starter and Pro Bowl rates for
rounds 1-3, how soon picks start (years 1-4), rookies' share of starters (8% vs 8%),
draft-day trade prices, the QB rules, need effects, scatter of picks around the public
board, front-office skill persisting, and every position's level staying steady over 22
seasons.

**Known gaps (honest list):**
- Rounds 4-7 become starters a little less often than real (R5: about 15% vs 20%).
  Undrafted players become starters far less often than real (about 4% of starters vs
  13%). Real teams churn more: they cut expensive veterans and keep giving young
  long shots a look. The new free agency system already closed part of this gap
  (veterans staying on a roster next season: sim 72-78% vs real 69-75%). Players with
  9+ seasons are still 13% of rosters vs real 9%. That's the main session's area
  (cuts, contracts).
- Older prospects (24+) turn out worse than real for their draft slot (0.70 vs 0.88).
- Team drafting skill is a little more lasting than real (0.60 vs 0.53).
- Kickers and punters: only about 1.4 a draft are drafted (real about 4); most good ones come in undrafted. Knob: their POS_SHIFT.
- Pro Bowl in the sim is a stand-in: each season, the best players at each position by
  rating plus "voting luck", as many as the real Pro Bowl names including alternates. The
  luck was tuned so players make it about 3 times each, like real Pro Bowlers.
- These checks skip the games (the fast harness fakes who plays and who gets hurt). A
  real-game check is a good follow-up once everything is wired in.
- The real NFL has about 257 picks a year (with compensatory picks); this draft has 224
  (7 x 32). See decision D6.

## 5. FOF8 exploits and how the AI resists them

| Exploit | What the AI does now | Result |
|---|---|---|
| TEs falling late | TEs are valued like the real NFL values them. A first-round TE talent goes in round 1-2. | The class's best TE goes around pick 30 (real first TE: pick 19). He lasts past round 3 in about 1 draft in 7. Good TEs come from rounds 1-4 like real. |
| Drafting a QB over a good young starter | A hard rule: never in rounds 1-2 with a young, good starter. | 0% (real 0%). |
| Easy trades / pick farming | AI teams price by the Jimmy Johnson chart and never accept less than chart value from you. | You can still profit by trading down, as smart real teams do: the chart overvalues top picks by about 30-50% vs real outcomes. That's an honest edge, not an exploit. |
| Underrated youth / combine | Real teams under-price youth a little and the AI does too, the best front offices less. The combine is a weak signal. | A sharp GM who drafts younger prospects gains a little, as in the real NFL. |

## 6. Your draft day (PROVISIONAL, for Blake's review)

The engine (`draft.DraftRoom`) already supports all of this. The screens aren't built.

- **D1. How the draft runs.** Options:
  (a) pick by pick, with buttons for "Sim to my pick" and "Sim the rest of the draft"
  (FOF8-like);
  (b) a live ticker with a clock per pick;
  (c) the staff drafts for you entirely.
  **Recommendation: (a)**, with (c) available as "Let my staff pick for me" on any pick
  or for the rest of the draft.
- **D2. When you're on the clock.** The screen shows your staff's board (your scouting,
  with ranges), your needs by position, and up to 3 trade offers from teams behind you
  (with the picks they offer and the chart value). You can make your own offer to any
  team; it's accepted if it's at least full chart value. Recommendation: as described.
- **D3. Future picks in trades.** The research only covered same-year pick-for-pick
  deals. Options: (a) same-year picks only for now; (b) allow next year's picks, valued
  one round lower (a common real rule of thumb). **Recommendation: (a) now, (b) with
  the trade system.**
- **D4. Draft order.** The current order is unchanged: non-playoff teams worst first,
  then playoff teams by round of elimination. Real ties are broken by strength of
  schedule (the game uses a coin flip). Recommendation: switch to strength of schedule.
  It's small, and it's the main session's code.

## 7. Scouting (Version 1: interview-based; PROVISIONAL, for Blake's review)

*(Oct 23: Blake decided timing, budget, interviews and combine display; the numbers below
are the first draft. What's built is in section 13.)*

`engine/scouting.py`. Everyone sees the public part: age, school, size, combine,
intelligence test, position drill, the media's big board rank, and medical red flags
(real combine medicals are shared with every team). Your staff's grade of each prospect
is a **range** (e.g. "Good (61-68)") that tightens as you spend time on him:

| Step | Cost | What it does |
|---|---|---|
| Film study | 3 of your 300 hours | Removes the biggest part of the staff's mistake. |
| Cross-check (second scout) | 6 hours, after film | Removes more. |
| Top-30 visit | 1 of 30 (the real NFL limit) | Sharpens the grade the most. |
| Combine interview | 1 of 45 (the real NFL limit) | Shows a read on leadership, loyalty, wanting to win and how steady he is, and turns up a character flag 85% of the time if he has one. |

Your grade never becomes perfect: some mistake always remains. Each step moves the
estimate toward the truth without re-rolling it, so scouting a player twice doesn't
change him at random. Your staff's own skill (the same front-office skill AI teams have)
sets how big its mistakes are to begin with. Hidden ratings (consistency, durability,
interception/fumble avoidance, Generational) are never shown.

- **D5. Scouting budget and timing.** Options: (a) as above, spent in a pre-draft stage
  of the offseason; (b) FOF8-style: scout during the season, with the class visible all
  year. That one is more fun and closer to real (scouts watch college games), but it needs
  the class saved for the whole season. (c) Scouting staff as hired people with ratings
  (comes with coaches/staff). **Recommendation: (a) now, (b) when the season screens
  are reworked, (c) with the staff system.** The hours (300) and sizes are first
  guesses to tune by feel.

## 8. The startup draft (your main way to start a league; PROVISIONAL)

`draft.startup_draft(league, rng)`, first version, built and tested. Every player goes
into one pool and the 32 teams draft full 53-man rosters, each position to its roster
count. AI teams draft from their own boards, mostly on what a player is now, less for
his ceiling, and less for players past their prime. Starters come first, then backups.
Better front offices judge players better. Tested on 4 generated leagues:

- Every roster is legal (53, every position at its count), about 3 seconds per draft.
- Team strength spreads out 1.3-1.6x compared with today's random generated leagues.
  The real NFL vs today's random leagues is about 1.33x (about 6 vs 4.5 points per game).
- How good a team's scouting is decides how strong it starts (correlation 0.64-0.87
  between front-office skill and team strength). So teams that draft well start strong,
  as you wanted.
- The first picks are mostly QBs, then tackles, edge rushers and WRs, as you'd expect.

Decisions:
- **D9. Draft order.** (a) snake (order reverses every round, fairest over 53 rounds);
  (b) the same order every round (the team picking 1st gets a big edge); (c) random
  order each round. **Recommendation: (a)** (built).
- **D10. Your picks.** You pick yourself, or let your staff auto-draft any pick or the
  rest. Not built yet: your team is auto-drafted for now. Recommendation: same screen as
  the yearly draft (D1), with position counts showing what you still need.
- **D11. How much scouting skill should matter.** Bigger gaps between front offices
  mean a more uneven league. Now: spread 1.3-1.6x. Recommendation: keep it, then check
  with real games (CLAUDE.md: rerun the realism tools on drafted leagues).

## 9. All open decisions (PROVISIONAL, for Blake's review)

| # | Decision | My recommendation |
|---|---|---|
| D1 | How draft day runs | Pick by pick with "Sim to my pick" / "Let my staff pick" |
| D2 | On the clock: board, needs, up to 3 trade offers, make your own | As described |
| D3 | Future picks in trades | Same-year only for now |
| D4 | Draft-order ties | Strength of schedule, like the NFL |
| D5 | Scouting budget/timing | Pre-draft stage now; in-season scouting later |
| D6 | Compensatory picks (real ~32 extra a year at the ends of rounds 3-7) | Add them once free agency losses can be counted; until then 224 picks |
| D7 | Draft capital: high picks get a depth-chart nudge from AI staffs | Keep (it's what real staffs do); your own chart is never touched |
| D8 | Character red flags: only a board drop now | Later tie them to suspensions or off-field events once those exist |
| D9 | Startup draft order | Snake |
| D10 | Startup draft: your picks | Same screen as the yearly draft |
| D11 | Startup draft: how much scouting skill matters | Keep 1.3-1.6x spread, check with real games |
| D12 | Rookie readiness ~88% of ceiling (top picks start right away) | Keep; it matches real starting rates |
| D13 | The shown development % for rookies is the staff's estimate (your Oct 21 decision) | Built in scouting ranges |

## 10. What the AI does each pick, in one paragraph

The team on the clock first listens to trade offers from teams behind it. If someone
badly wants a player still on the board and the team on the clock doesn't lose much by
moving down, they deal at chart value. Then the team takes the best player on its own
board, adjusted for need, position value, recent high picks and the QB rule. Its board
is the league's consensus plus its own scouting opinion, which is better or worse
depending on its front office.

---

## 11. Integration steps (for the main session)

**Status (Oct 22, morning): steps 1-5 are done by the main session**, and the rerun of
`tools/draft_check.py` on the wired-in game matches section 4 within run-to-run noise
(e.g. picks 1-5 start 3+ seasons 91% vs real 93%, rookies 8% of starters vs 8%, 19.9
trades per draft vs real 18.4). The harness now just watches the game's own offseason;
it no longer swaps any functions in. Steps 6-8 are what's left, for when the draft
screens are built.

1. **Done: `engine/offseason.py`, `run_offseason`** calls `D.make_class`, `D.run_draft` and
   `D.sign_undrafted`. It drops `league.__dict__["_last_draft"]` and calls `D.finish(rookies)`
   at the end, and puts `room.trades` in the report as `"draft_trades"`. The old
   placeholder `rookie_class`, `_set_draft_board`, `run_draft`, `sign_undrafted` and
   `ROOKIE_POOL` / `ROOKIE_LEVEL_SHIFT` / `SHIFT_TAPER_*` in offseason.py are no longer
   used and can be deleted. Picks keep the format free agency reads (`season, round,
   pick, team, pid`, plus `from` and `board_rank`, which it ignores).
2. **Done: street free agents** (transactions.py and `fill_short_positions` call
   `draft.street_free_agent`; don't rename it).
3. **Done: draft capital** (`depth.auto_depth_chart(players, pick_of)`, passed by
   `League.auto_depth_chart` from the last 1,000 picks).
4. **Keep:** `cut_to_53`'s `DRAFT_KEEP` values (R1 16 ... R7 4, `UDFA_KEEP` 2). The class
   was calibrated with them. `draft.UDFA_PER_TEAM` is 8 (camp signings); the cut decides
   who sticks.
5. **Done: the free agency 53-man bug** (`run_offseason` refills after
   `final_compliance`, up to 4 passes).6. **Saving:** `league.settings["draft_skill"]` (team front-office skill) and
   `league.settings["scouting"]` (your scouting this year) are plain JSON in settings and
   save already. For an interactive draft (D1) the class must survive between offseason
   stages:
   - keep the prospects' pids in a saved list (e.g. `league.prospects`), and make
     `League.free_agents()` skip them until the draft is over;
   - save `D.save_notes(prospects)` and `room.to_dict()` (both plain JSON); restore with
     `D.load_notes(...)` and `D.DraftRoom.from_dict(league, prospects, d, rng)`.
7. **Your team drafting (D1/D2):**
   `room = D.DraftRoom(league, prospects, order, rng, humans={league.user_team_id},
   boards_override={league.user_team_id: scouting.staff_board(league, uid, prospects)})`.
   `room.run()` stops at your pick (returns the slot). Then `room.offers_to(uid)` (AI
   trade-up offers), `room.accept(buyer, uid, offer["gives"], [offer["for_pick"]])`,
   `room.offer(uid, other, give, get)` / `room.accept(...)` for your own offers,
   `room.make_pick(pid)` or `room.staff_pick()`, then `room.run()` again.
   `room.picks` and `room.trades` hold the results.
8. **Startup draft:** `D.startup_draft(league, rng)` on a freshly created league (it
   pools every rostered and practice squad player and redrafts them, then sets depth
   charts, captains and practice squads). For the New game screen's "Startup draft"
   option. After it, run the realism tools on drafted leagues (CLAUDE.md).
9. **Checks:** `python tools/draft_check.py` (3 minutes) should print about
   the same numbers as section 4. Run the usual realism check afterward. The draft
   changes who's on rosters, not how ratings become results, so no recenter is needed.

## 13. The draft screens (built Oct 23; Draft tab, `engine/draft_day.py`, `screens/draft_page.py`)

Steps 6-8 of section 11 are done.

**Blake's scouting choices (Oct 23):** scout in the offseason, before the draft (not all
season); "fewer, harder choices" (20 interviews, 15 top-30 visits, 150 film hours, about
half the real NFL limits, for a class of ~440); an interview reads the person (leadership,
loyalty, wanting to win, how steady he is, a character flag 85% of the time) and his football
mind (it sharpens the grade a little); combine results in real units with where each ranks
at his position in this class ("4.52 sec (8th of 24 DEs)").

**How it plays:**
- The class is announced before the league year starts (the real combine is late February),
  so it's there all through free agency waves 1-4. Prospects are in the save but aren't free
  agents (`league.draft["pool"]`).
- Draft tab, **Prospects**: every prospect with your staff's grade as ranges ("Good (66-73)"
  now, and a ceiling), your board rank, the media's rank, 40 time, what you've scouted, red
  flags you know about. Click one for his report: the grade, the scouting buttons, bio, every
  skill as a range, the combine with ranks, the interview.
- Your staff's view starts as good as an average NFL staff's: it shares the league's common
  mistake (the consensus miss) and has its own. Film study clears half the shared mistake,
  the cross-check a quarter more, the visit 10% more (15% always stays), and each step clears
  one of your staff's own mistakes; "never" stays. Ranges are +/- 1 spread of what's still
  unknown: the truth is inside about 2 times in 3. (At first I used 0.67, a 50% range; a fully
  scouted top prospect then showed a 1-2 point range, which read as knowing the truth.)
  Unscouted top prospects show ranges about 12-20 points wide, deep ones up to ~30; fully
  scouted about 4-6.
- **Next: start the draft** ends scouting; the AI picks until you're on the clock and the
  offseason phase becomes "drafting". **Draft room**: who's on the clock and who your staff
  would take; Draft selected player / Let my staff pick when it's you; Next pick (one pick, so
  you can stop and make an offer for that pick) / Sim to my pick otherwise; Staff finishes the
  draft (= Next in the bar). Side panel: Prospect, Trades (up to 3 offers when you're on the
  clock, at least full chart value; your own offers: picks this draft only, at most 4 a side,
  full Jimmy Johnson value, and a team on the clock or within 5 picks of it that loves a player
  on the board won't move down, the same rule AI teams use with each other), Needs, Picks.
- **Results**: every pick (team, the team the pick came from, media rank) and the trades;
  earlier drafts by season.
- Saved mid-draft: the room's state (slots, picks, trades, who's left) in `league.draft["room"]`;
  every team's board is rebuilt the same way on load (same dice), and your staff's board from
  your saved scouting.
- **Startup draft** (New game, "How teams are built", now the default as Blake's main way):
  the league's players are generated, the round-1 order drawn by lot (snake after), you pick
  your team seeing its slots, then the AI picks until you're on the clock. Same room: your
  board (your staff's view of veterans, by their shown ratings), "Only positions I still need",
  your roster by position against its 53-man count (you can't draft past it). Saves mid-draft.
  When it's over: depth charts, captains, practice squads, fresh contracts for the drafted
  rosters, 90-man camps and the first season's schedule. Team strength spread after it: starter
  average SD 2.5-2.9 rating points vs 1.6-1.8 in a random league (1.5-1.8x).
  **Revised the same day (QBs were undervalued):** teams now value a pick by what it adds over the
  starter they'd be stuck with by waiting, times position importance (QB 3.0, LT 1.3, most 1.0,
  K 0.3, P 0.25, LS 0.1); backups count a quarter and don't take starter-caliber players from teams
  that need one; every team has its QB by round 4 (`STARTUP_POS_WEIGHT`, `STARTUP_WAIT_DEPTH`,
  `STARTUP_QB_BY`, `STARTUP_BACKUP_SHARE`). Spread after it: SD ~2.5 (about 1.5x random rosters).

**Fixed on the way:** a prospect's college was re-drawn when he was drafted (by the round he
went in); now it's set once, by where the media expects him to go. Prospects were counted in
the free-agent pay ladders (`cap_market.active_players`).

**Making the class earlier needed one correction** (`draft.CLASS_EARLY`, used only by the
game's early class): at the start of the league year the roster openings that size each
position's class differ from draft day (practice squads are on rosters, expiring deals haven't
left): K/P/LS/FB classes came out ~25% bigger and QB/TE/CB 7-14% smaller, and over 22 seasons
K/P/LS starters crept up 3-4 points while QB starters slipped 2. The factors bring the early
class back to the draft-day mix on average. AI boards are also re-measured on draft day
against the rosters then (`draft.regrade`: same scouting opinions, no new dice).

**PROVISIONAL (for Blake):** what each scouting step clears and how wide the ranges are; the
trade rules for your offers (4 picks a side; the on-the-clock refusal); the startup draft
being the New game default; your board order (talent, position value and age, as AI boards).

## 12. Where the knobs are

Every number is at the top of `engine/draft.py` and `engine/scouting.py`, with a comment
saying what it does and, where it was tuned, the measurement. The most important ones:
`LEVEL_SHIFT` / `SHIFT_TAPER` / `POS_LEVEL` (class level), `READY_MEAN` (readiness),
`CONSENSUS_MISS*` / `TEAM_MISS*` / `TEAM_INSIGHT` (how well teams scout), `POS_SHIFT` /
`POS_STAR` (position value), `NEED_K` / `RECENT_PICK` (need), `QB_*` (QB rules),
`TRADE_*` (trades), `DRAFT_CAPITAL` (draft capital), `STARTUP_*` (startup draft).
