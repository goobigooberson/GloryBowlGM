# Contracts, salary cap and free agency: design (built overnight Oct 22-23, 2026)

Status: the engine is built and checked against real NFL data, but **not wired into the
game yet** (no save columns, no screens, the offseason doesn't call it). Integration steps
for the main session are at the end. Everything marked **PROVISIONAL** is a judgment call
for Blake to review.

## Files

| File | What it does |
|---|---|
| `engine/contracts.py` | The rules and the accounting: the cap by year, minimum salaries, contract structure (base, bonus, guarantees), cap hits, top-51 rule, dead money, June 1 cuts, restructures, rookie scale, franchise tag, RFA tenders, fifth-year options, carryover. Money is in whole $K so cap math is exact. |
| `engine/cap_market.py` | The market's price for a player (share of the cap), and the shape of a deal (years, guarantees). |
| `engine/free_agency.py` | The AI: a new league's contracts, the start of the league year (re-signings, tags, tenders, extensions, options, cap cuts, getting under the cap), the free agency market in waves, rookie deals, money-aware cut-down, a `sync()` safety net that keeps contracts in step with any roster move, and the engine side of your negotiations. |
| `tools/free_agency_check.py` | Builds generated leagues, runs offseasons in the real order and prints sim vs real for every benchmark. Writes `tools/free_agency_report.txt`. |

Run it: `python tools/free_agency_check.py` (2 leagues x 3 offseasons, ~15 s), or
`python tools/free_agency_check.py --leagues 101,102,103 --seasons 4 --games` (plays one
real season per league first, ~2 min). Nothing is saved.

## Real rules modeled (2020 CBA, which runs through 2030)

- **The cap**: real figures 1994-2026 ($301.2M in 2026); later years come from each league's
  own TV-deal eras (`engine/league_money.py`, Blake Oct 24): steady ~7% a year inside an era,
  a jump when new TV money arrives (deals of 7-11 years, signed 1-2 years ahead; the size is
  mostly market luck plus some league buzz), labor deals every 10 years (a hard one keeps the
  cap flat for a few years), a rare revenue shock (a drop, paid back over the next two years).
  Next year's cap is projected a year ahead, as the real NFL does, and teams plan with it.
  Unused cap room carries over to next season (real rule).
- **AI teams' approach each league year** (Blake Oct 24, "match the real NFL"): the most
  promising ~10 go all in (restructure to keep and sign starters, back-load new deals, keep
  less room), the least promising ~7 rebuild (pay older players less, cut overpaid veterans,
  keep extra room that carries over). Target: cap room when free agency opens spread like the
  real NFL's (median ~13-14% of the cap, the most ~40%, several teams at almost nothing).
- **Minimum salaries** by credited season, the 2020 CBA table for 2020-2030 (2026: $885K
  for a rookie up to $1.3M for 7+ seasons); scaled with the cap outside those years.
- **Contract structure**: base salary by year (rising ~6% a year: real deals are
  back-loaded), signing bonus spread evenly over at most 5 seasons, guaranteed money =
  the bonus plus the earliest base salaries.
- **Cap hit** = this year's base + this year's bonus share. **Top 51**: from the start of
  the league year until the first game only a team's 51 biggest cap hits count; after
  that, everyone (53, practice squad, reserve lists).
- **Weekly pay**: base salary is paid in 18 regular-season checks. A player signed in week
  10 counts only the weeks he's paid; a player cut mid-season counts what he was paid.
- **Cuts and dead money**: remaining bonus money speeds onto this year's cap plus any
  guaranteed salary still owed. After June 1 (and all in-season cuts) the bonus money for
  future years moves to next year instead. Teams may name **2 post-June 1 cuts** a spring.
- **Vested veterans** (4+ seasons) on the week-1 roster cut during the season are owed the
  rest of that season's salary (termination pay).
- **Veteran salary benefit**: a 4+ season veteran on a 1-year minimum deal counts on the
  cap like a 2-season player.
- **Retirement**: remaining bonus money speeds onto his team's cap; no salary owed.
- **Waiver claims**: the claiming team takes over the base salaries; bonus money stays on
  the old team's cap.
- **Restructures**: base salary turned into bonus spread over the remaining years (max 5).
- **Rookie scale** by overall pick (4 years; round 1 fully guaranteed for picks 1-24, round
  2 partly); **fifth-year option** for first-rounders (playing-time levels of the 2020 CBA:
  a regular starter's option is the top-10 average at his position, otherwise the 3rd-25th
  average; the Pro Bowl levels wait for a Pro Bowl). **Undrafted**: 3 years at the minimum
  plus a small bonus.
- **Free agent status** by accrued seasons: 2 or fewer = exclusive rights (team keeps him at
  the minimum if it wants), 3 = restricted (tenders: right of first refusal / 2nd-round /
  1st-round, or 110% of last salary), 4+ = unrestricted.
- **Franchise tag**: real 2024 tag levels as a share of the cap (QB 15.0% ... K/P 2.3%; OL
  share one tag, so a guard tagged gets the tackle-heavy number, as in the real NFL), moved
  by how this league's top salaries compare with real ones; at least 120% of his last cap
  hit; second tag 120% of the first, third 144%. One a team a year.
- **Practice squad pay**: 2026 $13,750 a week (2 or fewer seasons), $18,350-$22,850 for
  veterans; counts from week 1. **Elevations** pay a week at the minimum.
- **Reserve/future deals**: last season's practice squad players re-sign 1-2 year minimum
  deals when the season ends.

Not modeled (deliberate, small): void years, incentives (likely/unlikely to be earned),
offset language, the 89% cash-spending floor over multi-year periods, the transition tag
and RFA offer sheets with draft-pick compensation (no draft-pick trading in the game yet),
compensatory picks.

## What a player costs: the market price (`cap_market.py`)

1. **How teams rate him**: his overall projected over the next 3 seasons (weights 50/30/20):
   young players grow toward their potential at the normal rate for their age, veterans
   past their position's prime decline at the normal rate (development.py's real-data
   tables). Teams don't see his hidden personal aging, durability or Generational status;
   they do see an injury carrying into next season and his recent injury record (discounts).
2. **His rank**: among veterans at his position on that projection.
3. **His price**: that rank read off the **real pay ladder** for his position (Nth best-paid
   player as a share of the cap, every active contract, OverTheCap 2022; QB #1 24.1%, #10
   17.0%, #32 2.6%; RB #10 3.4%; ...). The real ladder counts rookie deals too, so a
   veteran's rung is his rank among veterans plus the rookie deals that pay more than that
   rung. Linebackers: the game's OLBs take 2/3 and ILBs 1/3 of the off-ball linebacker
   ladder; DEs use the edge ladder.
4. Below the ladder's last rung the price slides to his minimum salary.

This is the anti-exploit core (CLAUDE.md "underpriced free agents"): a top-10 player at a
position costs a top-10 salary from whoever signs him, you included.

## How AI teams act (`free_agency.py`)

**Willingness to pay**: a team pays up to his price to start him (a bit more, up to +6%,
for a big upgrade), but never a starter's salary for a backup: for a backup or camp body,
the most it pays is what the league's best player in that role earns. Each front office has
a hidden spending style (+/-4%) and judges each player a little differently each year
(+/-5%, scouting misjudgment). It always keeps cap room for: in-season moves (3.5% of the
cap), what starts counting at week 1 (2.5%), filling its open roster spots at the minimum,
and (before the draft) its draft class at its draft slots.

**Start of the league year**, in order:
1. Reserve/future deals for practice squad players (85% kept).
2. Fifth-year options (exercised if he's worth 80% of the option).
3. **Extensions**: a starter worth 2%+ of the cap, 29 or younger (QB 33, K 34, P/LS 35),
   entering his last contract year: 45% a year. This season's money stays; new years and a
   new bonus are added.
4. **Expiring contracts**, best players first: the team decides if it wants him (would he
   start, back up, or fill a camp spot; depth players kept 55% of the time, teams churn
   depth). He asks his price +2.5-7.5% (less if loyal). They agree if the team's figure is
   within 10% (they meet in between). A player worth 1%+ of the cap **tests the market**
   ~55% of the time at average loyalty (more if disloyal, more if his team was bad and he
   wants to win); depth veterans 30%. A starter who won't re-sign may get the **franchise
   tag** if he's worth 95% of it; ~45% of tagged players then sign long-term before the
   season. Exclusive rights players are kept at the minimum; restricted ones tendered.
5. **Cap cuts**: veterans paid 30%+ (and 1%+ of the cap) over their price, where cutting
   saves 0.75%+ of the cap this season and leaves dead money under 60% of his cap hit,
   never a deal signed last year: cut 60% of the time (post-June 1 if that saves more
   without pushing more into next year than it saves).
6. **Getting under the cap**: restructures first (biggest savings), then the cuts that save
   the most for the least value lost.

**Free agency**, 7 waves (4 before the draft, 3 after): each team bids on the free agents it
wants (up to 3-10 a wave, one per position a wave, within its room). Prices behave like a
real auction: the top bidder pays about what the second team would. A player picks by money
first, then winning (if he wants to), loyalty to his old team (or away from it), and
starting. His ask starts at 108% of his price and falls each wave (100, 93, 86, 74, 50,
30%); a starter-caliber player won't go below 50% (40% once camp opens): he'd rather wait
for the season's injuries. During the season a market-level free agent still asks 50% of
his price (no signing a good player for the minimum).

**Never over the cap**: every AI signing is checked against the cap first. Checkpoints in
the check tool: start of league year, after free agency, after the draft, week 1, and every
week of a played season.

## Results vs the real NFL

`python tools/free_agency_check.py --leagues 101,102,103 --seasons 4 --games` (12
offseasons; one real season per league). Real numbers in brackets.

- **Cap legality**: AI teams over the cap at any checkpoint: **0**; players on a team
  without a contract at week 1: **0**. In-season (weekly checks, 3 played seasons): 0 in the
  final run; an earlier run had 4 team-weeks slightly over (largest $3.2M), from practice
  squad promotions and IR activations in transactions.py, which don't check money yet
  (integration step 6 fixes that).
- **Veteran deals in a league year**: at about the minimum (<= 0.65% of the cap) **81%**
  [76-87%]; one-year **76%** [75-80%].
- **Market deals (1%+ of the cap)**: **268 a season** [352]; length 1y 38 / 2y 22 / 3y 20 /
  4y 13 / 5y 6% [42 / 23 / 19 / 10 / 5]; guaranteed share by position within a few points
  (QB 70% [67]); age 26-27 38% [41], 28-29 21% [21], 30-31 11% [12], 32+ 10% [13].
- **Big deals (5%+)**: 95 a season [80]; lengths 3y 32% [27], 4y 27% [28], 5y 12% [14].
- **Pay ladder at week 1**: within ~10% at most rungs (QB #1 25.0 [24.1], #10 17.8 [17.0],
  #32 2.4 [2.6]; WR #1 15.5 [14.4], #32 5.9 [4.8]; EDGE #1 16.5 [15.3]; RB #10 4.3 [3.4];
  K #1 2.8 [2.7]). A little high in the middle for WR/T/S/LB (#16-#32).
- **Positional spending** (share of all cap dollars): WR 13.1 [12.7], EDGE 11.3 [11.7], CB 9.4
  [10.5], QB 11.4 [10.3], T 10.9 [9.8], DT 9.0 [9.5], LB 7.7 [6.7], S 6.7 [6.5], G 5.6 [5.9],
  TE 4.5 [5.4], RB 4.1 [4.9], C 3.0 [2.9], K 1.4 [1.4], P 0.8 [0.8].
- **Rookie scale** by round: R1 1.92% [1.90], R2 0.83 [0.85], R3 0.58 [0.60], R4 0.49 [0.50],
  R5-7 0.39-0.43 [0.40].
- **Payrolls at week 1**: 96.7% of the cap used on average (10th-90th percentile 95.6-98.9%);
  dead money 4.7% of the cap a team [roughly 5-10%].
- **Franchise tags**: 11 a season [6-14, usually 7-9]. Extensions 55, options 20, cap cuts 10.
- **Where last season's players are at week 1**: same team **62.6%** [65.7], new team
  **21.1%** [23.8], out of the league 16.3% [10.5]. By experience: 0-2 seasons 82/9/9
  [81/14/5]; 3-4 51/31/18 [54/37/9]; 5-7 55/26/19 [54/32/14]; 8+ 42/27/31 [47/25/28]. By
  position, QB 63/32/5 [59/32/8], WR 62/29/9 [65/26/9], OL 63/22/15 [67/22/10] match well.
  (Before contracts and free agency existed, the game kept far more of its own players.)

## Known gaps (and what I think causes them)

1. **Too many players leave the league** (16% vs 10.5%). About 9 points of it is
   retirements of rostered players (~150 a season, including ~50 with 0-4 seasons), which
   come from `offseason.retirements`, not free agency; the rest are unsigned free agents.
   Worth a look in the retirement model (young-player retirements especially) with this
   tool.
2. **Defensive linemen and linebackers rarely change teams** (DL 10% new team vs 25%, LB
   18% vs 24%) and go unsigned instead. Their unsigned veterans lose their roster spots to
   rookies: real teams carry and rotate more DL than the 9-spot template, and the cut-down
   (by roster value, with potential at 50%) and the rookie class sizing favor young
   linemen. This is roster construction in offseason.py rather than the market.
3. **Too few mid-priced market deals** (268 vs 352 a season; median market deal 4-6% of the
   cap at WR/EDGE/T vs real 2.2-2.8%). Real teams sign many 1-2.5% role players (backup QBs,
   rotational linemen, TE2s); here many of those players take minimum deals. A role-player
   premium for the 2nd-3rd backup would help; left for after Blake's review.
4. **Market deals with a new team: 39%** (real roughly 50-57%, but that real number comes
   from OverTheCap's team field and is rough).
5. Kickers and punters sign slightly short deals (2.1 years vs 2.4-2.9).
6. Data: the contract numbers are from OverTheCap's May 2022 snapshot (the newer nflverse
   file is parquet only). Shares of the cap age well; QB tops have drifted down ~2 points
   since and WR/edge tops up ~1-2.

## Your team (PROVISIONAL, for Blake's review)

What you'd see and do. Engine pieces exist for the starred items; screens are not built.

**The Contracts view** (a tab, one main view with side panels):
- Payroll table for your team: every player's cap hit this season and the next 4,
  guaranteed money, years left, dead money if cut now / as a June 1 cut (*
  `contracts.release_preview`, `cap_hit`), cap room now and next year (* `team_cap`,
  `commitments`), dead money list, carryover. Top-51 line shown in the offseason.

**Start of the league year**:
- Your expiring players listed with your staff's recommendation (re-sign at about $X, let
  go, tag), what he's asking (* `asking_terms`: per year, years, guaranteed) and hints about
  him (loyal / wants a winner, never the hidden numbers).
- Re-signing is a negotiation (* `respond`, `accept_offer`): you offer per year, years,
  guaranteed money. He **accepts** at or above his ask (guarantees count extra; older players
  value years more), **counters** with his ask within 10%, and **rejects** lower offers;
  three lowball offers and he stops talking to you until the next wave. Loyal players give
  their own team a little slack. Anyone you haven't re-signed when the market opens becomes a
  free agent (* `open_market`).
- Franchise tag, tenders, fifth-year options: buttons with the cost shown (* `tag_amount`,
  `rfa_tender`, `option_salary`).
- Restructure and cut buttons with the cap effect shown before you confirm (*
  `restructure`, `release` with June 1 choice).

**Free agency**: a board of free agents (position, age, rating, asking price, "other teams
interested: several / a few / none", never the exact bids). You place offers during a wave;
at the end of the wave each player chooses among all his offers, yours and the AI's (*
`league.fa["user_offers"]` is read by `market`). The game won't let an offer put you over
the cap.

**Your staff checks in (Blake's rule)**: nothing bigger than routine happens to your team
without you. Routine and automatic: reserve/future deals for your practice squad players.
Everything else waits for you. If you're over the cap when the league year starts or before
week 1, your staff proposes the moves (restructures first, then cuts, cheapest value lost
first) as requests in the existing "Your staff wants to check with you first" box, each
saying what it saves and what dead money it leaves, and flagging important players (a
starter or first backup, top-25 player, captain, recent high pick) (*
`request_cap_moves`, `answer_cap_request`). Nothing happens until you approve. The game
can't start the regular season while you're over the cap (real rule: always under).

**Decided (Blake, Oct 23) and built:** you run your own contracts (your staff only steps in when
you're short of players); the offseason goes in phases with a Next button (start of the league
year / your exclusive window, free agency waves 1-4, the draft, waves 5-7, training camp);
negotiation is offer / counter / patience as described above; you see rough interest from other
teams ("several / a few / no other teams"), never their offers; routine only is automatic (draft
picks' rookie deals, practice squad reserve/future deals). Screens: the Contracts tab
(`screens/contracts_page.py`). Engine for it: `free_agency.expiring_for_you`, `resign_offer`,
`tag_or_tender`, `place_offer`, `withdraw_offer`, `interest`; phases in `offseason.py`
(`offseason_start`, `offseason_next`) and `season.begin_offseason` / `advance_offseason`.

**Still open for Blake** (from the list below): 5 (tune the role-player and DL/LB market gaps now or
after playing), 6 (startup-draft contracts), 7 (trades, later). Not built yet: extensions for your
players during the season, fifth-year option decisions for your first-rounders (AI teams decide
theirs), June 1 designations and restructures from the screen (your staff proposes them when
you're over the cap).

**Open decisions for Blake** (as first written):
1. Is the negotiation flow right (accept / counter / reject with a patience limit), or do you
   want FOF8-style "interest" levels and multi-day haggling?
2. Should your staff be allowed to make routine cheap moves on its own in a "staff runs
   contracts" mode (like the practice squad switch), e.g. re-sign minimum depth players?
3. Should rookies' deals and reserve/future deals be automatic for your team (they are now)?
4. How much should you see of other teams' bids: "several / a few / none" (proposed), exact
   offers (FOF8 hid them), or nothing?
5. The 2 known market gaps (role-player deals, DL/LB movement): tune now, or after you've
   played with it?
6. Startup draft leagues will need starting contracts too: real-ish contracts like a
   generated league (proposed), or everyone on fresh deals priced at the draft?
7. Trades (later) will use these contracts and prices; the "easy trades" exploit should be
   handled there by pricing players with this same market value.

## Integration steps (for the main session)

Contracts are kept on the league object, set up by `contracts.ensure(league)` /
`free_agency.ensure(league)`; nothing in the existing engine depends on them yet.

1. **New League fields** (add to the `League` dataclass in league.py so they're explicit):
   `contracts: dict` {pid: contract}, `cap_history: dict` {season: $K}, `cap_carry: dict`
   {team: {season: $K}}, `cap_charges: dict` {team: {season: $K}}, `contract_log: list`,
   `june1_used: dict` {team: {season: n}}, `fa: dict` (this league year's free agency state:
   former teams, statuses, your pending re-signings, tags, user_offers, report).
   `league.__dict__["_fa_table"]` is a per-season cache: don't save it.
2. **Save/load** (database.py): a `contracts` table (pid, team, kind, signed, week, apy,
   value, guaranteed, signing_bonus, vsb, tags, option JSON, years JSON, extra JSON for
   new_years/new_apy/pick/restructured), a `contract_log` table (season, pid, team, kind,
   phase, pos, age, exp, years, apy, apy_share, guaranteed, value, new_team, pick), and
   league_info JSON for cap_history, cap_carry, cap_charges, june1_used, fa. Note JSON turns
   int keys into strings: convert season/team keys back to int on load. **Older saves**: if
   no contracts on load, call `free_agency.initial_contracts(league)` once (it sets the
   past caps and gives every player on a team a realistic contract).
3. **New leagues** (`league.create_league`, at the end, after practice squads):
   `free_agency.initial_contracts(league)` (needs `settings["salt"]` set first for its dice;
   the New game flow sets it, or set it in create_league).
4. **The offseason** (`offseason.run_offseason`, called after `season += 1` and
   `transactions.end_of_season`). New order (real NFL order):
   ```
   retired = retirements(...); for each: contracts.retire(league, pid); retire(league, pid)
   order = draft_order(league, season_lines)
   free_agency.league_year_start(league, rng, draft_order=order)   # cap, re-signs, tags, cuts
   free_agency.market(league, free_agency.PRE_DRAFT_WAVES, rng)
   rookies = rookie_class(...); run_draft(...) ; free_agency.sign_draft_picks(league, picks)
   udfa, unsigned = sign_undrafted(...); free_agency.sign_undrafted(league, udfa)
   free_agency.market(league, free_agency.POST_DRAFT_WAVES, rng)
   free_agency.tagged_long_term(league, rng)
   cuts = cut_to_53(league)            # see step 5
   free_agency.sync(league, "cut-down")  # dead money for the cuts
   filled = fill_short_positions(league, rng); free_agency.sync(league)
   transactions.form_practice_squads(...); free_agency.sync(league, "practice squads")
   free_agency.final_compliance(league); free_agency.sync(league)
   trim_free_agents(...); update_depth_charts(...)
   ```
   With your team: `league_year_start` leaves your expiring players in
   `league.fa["pending"]` (still on your roster, no contract) until `market` opens; the
   screens should pause there so you can re-sign (the market call is the "Open free agency"
   button). Until the screens exist, the offseason can call `market` straight away (your
   unsigned players then just leave) or let the staff re-sign them (decision 2 above).
   The offseason report can list `league.fa["left"]`, the contract_log for the season
   (signings with team, years, money) and `league.fa["report"]` counts.
5. **Cut-down**: in `offseason.cut_to_53`, replace
   `v -= VET_COST_K * max(0, p.experience - VET_COST_FROM)` with
   `v += free_agency.cut_money_value(league, p)` (keeps players whose cut would leave dead
   money, lets go of players whose cut saves real money; this is the real cost the stand-in
   was approximating). Then `VET_COST_K` / `VET_COST_FROM` can go. Rerun your fast harness:
   the young-player churn numbers will move.
6. **In-season moves** (`transactions.py`):
   - In `season.end_week`, right AFTER `league.week += 1` (regular season) and after the
     final-cuts branch has switched to `stage = REGULAR_SEASON, week = 1`, and in the
     playoffs after their weekly moves: `free_agency.sync(league, label)` then
     `free_agency.final_compliance(league)` then `sync` again. (Timing matters:
     `contracts.pay_week` = `league.week - 1` = weeks already paid, so syncing before the
     increment would date every move a week early. The realism tools' `lab_preseason` needs
     the same calls after its final cuts.) `sync` prices every signing (minimum, or 50% of a market-level player's
     price, prorated by week), charges every release (earned pay, termination pay, dead
     money), handles promotions (2-year minimum for young players), demotions, waiver claims
     (contract taken over) and retirements.
   - When an AI team picks a free agent (`free_agent_pool` callers: `fill_roster_spot`,
     `_upgrade`, `injury_cover`, `fill_practice_squad`, `process_waivers`), skip players it
     can't afford: `free_agency.affordable(league, tid, pid)`. (The check tool emulates this
     by wrapping those functions; with it in place, in-season over-the-cap weeks went from
     418 to 0-4 a run.) Also check before promotions and IR activations (cost: minimum minus
     practice squad pay, or his contract) and prefer a cheaper move if over.
   - Elevations: `free_agency.elevation_pay(league, tid, pids)` when elevations are made.
   - Your team's signing buttons: show the cost (`in_season_terms`) and refuse if
     `affordable` is False ("That would put you over the cap").
   - `transactions.answer_request`: route requests whose `then` has a `"cap"` key to
     `free_agency.answer_cap_request(league, index, approve)`.
7. **Season rollover** (`season.start_next_season`): nothing extra beyond step 4 (contracts
   expire inside `league_year_start`; carryover is computed there). `contracts.pay_week`
   reads `league.stage`/`league.week`, so the stages need no change.
8. **Realism checks after wiring** (CLAUDE.md): contracts don't touch the game sim, but they
   change who's on rosters, so rerun `tools/realism_check.py --seasons 4` and your fast
   offseason harness; rerun `tools/free_agency_check.py` and compare with
   `tools/free_agency_report.txt` from tonight.
9. **Build log**: record the decisions above as PROVISIONAL with Blake's open questions.
