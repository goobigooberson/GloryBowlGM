# Current state (summary of docs/build-log.md, as of Oct 26, 2026)

Read this, then search `docs/build-log.md` for your topic (section 6). Where the log reversed itself, only the latest call is given. Numbers are copied from the log; "game / real" = game vs real NFL. Each system's open choices are also in `docs/draft-design.md`, `free-agency-design.md`, `staff-design.md` (GMs: section 10), `trade-design.md`, `news-design.md`, `development-review.md`, `layout-research.md`.

## 1. Overview

**Glory Bowl GM** (name chosen Oct 22; folder and code comments keep the old name): Blake's single-player football GM sim, successor to FOF8. You run one of 32 fictional teams (2 conferences, 8 divisions); 31 are AI. Python 3.13 + NiceGUI 3.18; `python app.py` opens a pywebview window (`--browser`, `--no-show`, `--saves-dir=`, `--port=` for testing). Rules in `engine/`, screens in `screens/`. Saves: one SQLite `.db` per game in `saves/` (temp file swapped in), plus `<save>.history.db` for past box scores; many systems are JSON keys in `league_info`; older saves get new fields on load. Saving is manual only (no autosave, no recovery copy; Oct 24). Packaged: `tools/build_exe.ps1` -> one-file `GloryBowlGM.exe`, saves in `Documents\Glory Bowl GM\saves` (or an existing `Documents\Front Office Football\saves`). Git since Oct 23; the main session merges branches. Latest commit `5f06216` (scoreboard baseline after AI commitment + finances).

## 2. Systems

**Game sim** - built Oct 19, tuned through Oct 26. `engine/sim/` (game, plays, coach, gameteam, penalties, stats, text, weather, norms, data = real tables, tuning = every knob, playcalling). Plays come from individual matchups tilting real 2023-25 distributions (log-odds); ratings read as z vs the league's average starter, soft cap `Z_CAP` 2.3 (Generational 2.7); `tuning.CENTER` re-measured by `tools/recenter.py`; 2025 kickoff/OT rules. Mechanisms worth knowing: load-the-box, coverage rolled to hot receivers, `CB_SIDE_SWAP` 0.35, `HOT_RUSHER_CLEANUP` 0.20, `CLEANUP_WEIGHT` DE 0.4 / DT 0.25, star TE pull `TE_FEATURE_K` 0.25, 3rd-down back 0.85 of passing snaps, RB blowout rest, hidden QB knack + season form (`KNACK_SD` 3.5, `SEASON_FORM_SD` 4.5, QBs only), out-of-position penalties outside the per-play caps (`UNTRAINED_K`, `depth.RELATED`), down-and-distance set ON (Oct 25), real screens (Oct 26), run/pass tables at 1% points (`tools/run_tables.py`). Latest realism check (Oct 26, 16 seasons): **21 of 303 outside the real range** (normal band ~19-26); points 22.6 / 22.6, completion 65.0 / 64.4%, INT 0.74 / 0.73. Gaps: 10+ TFL seasons 66 / 53; backs score too often near the goal line (needs fewer red-zone trips and more QB sneaks first; a stronger `RUN_FIELD` raised FG tries, not kept); punt returns 1.3-1.9 yards long (rebuild return tables; kr/pr centers deliberately NOT written); 27 / 33 defenders used a season (no defensive blowout rest); tempo spread 2.72 s / 1.44 and pass lean unrelated to team quality (Blake's call); 4,500-yard passers ~2 / 3.8 a season.

**Injuries** - built. `injuries.py`, `injury_report.py` (one rulebook for the season and all tools): ~820 game-costing injuries a season (`INJURY_RATE` 0.0112), ~60 types, Q / D / Out / IR / concussion protocol, per-body-part playing hurt and flare-ups, camp injuries (`CAMP_INJURIES_PER_TEAM` 4.0), PUP carryover, career effects (`CAREER_SIZE_SCALE` 3.0, `POSITION_RISK`), full injury history.

**Players, ratings, development, aging** - built. `player.py`, `positions.py` (scarcity), `development.py`, `scale.py`, `evaluation.py`, `combine_data.py` (real combine shapes), `name_data.py` (real-roster names; `names.elder` for coaches/GMs). Development: two potential layers, no yes/no switch, ~88-90% move 0-3 a year (`LONG_SD` 1.05, `SWING_SD` 1.3). Aging (Oct 24): `DECLINE_BASE` 3.0 / `DECLINE_GROWTH` 1.0, `PEAK_SEASONS` one season earlier than the Oct 21 table for RB/FB/OL/DL/LB/DB, QB decline at half speed, QB `RETIRE_AGE` 40, per-player aging profile; retirement weighs money owed (`RETIRE_MONEY_K` 0.02). New leagues start settled (`NEW_LEAGUE_READY` 0.84 / 0.905 / 0.95 / 0.975). Display: engine keeps internal ratings; screens show `scale.shown` (median 50; 80+ from internal 88, 90+ from 93, 95+ from 96; K/P/LS own curve; `legacy_shown` only for award "film" and news cutoffs) through **your staff's evaluation** (`scale.seen`, since Oct 24). New leagues: ~18-22 players 80+, ~3 at 90+. `career_mix_check.py`: 9+ year veterans 10.7% / 8.0%. Gaps: rookies 13.8% / 16.5% of week-1 rosters; rookies ~0.5 yr young at OL/TE/QB/DL/LB; 34+ leave too often.

**Depth charts, game day** - built. `depth.py`, `roster_rules.py`: a list per spot (incl. RB3, KR/PR), AI auto-fill, `spot_fit`, OL sides, voted captains; 48 active (47 without 8 OL) + emergency 3rd QB, minimum 44. Gaps: AI charts start 202 of 2,976 starters out of position; picking your own inactives not built.

**Roster moves** - built. `transactions.py`: 53 + 16 practice squad, IR (8 returns), PUP, waivers, elevations, 90-man camp and one cut to 53 (`final_cuts`), staff check-in before cutting important players, practice-squad toggle (default you; staff mode adds injury cover). AI teams at the cap may play up to 2 short (`SHORT_AT_CAP`), never over the cap (`cap_squeeze`): short of 53 4.2% / 4.6% of team-weeks. Gaps: nobody signs your practice squad players; AI squads 15.9 / ~15.2; too many players change teams (32.9% / 20.5%).

**Contracts, cap, void years** - built. `contracts.py` (real CBA: 2026 cap $301.2M, minimums, proration, June 1, rookie scale, tags, tenders, 2020-CBA option levels, top-51 until week 1), `cap_market.py` (real pay ladders), `league_money.py` (cap after 2026: TV-deal eras, labor deals, shocks, buzz; next year's cap fixed a year ahead; `league.tv`). Void years (Oct 26): max 5 bonus seasons incl. voids; AI use all-in 90% / normal 35% / rebuild 0, `VOID_BRAKE` 20%; void restructures are every AI team's last escape. Your controls are on the Contracts tab. Check (`free_agency_check.py`, scoreboard `fa.*`): dead money over the league year 17.6-18.4% / 17.6% (Spotrac; the older "5-10%" target was a guess); deals voiding ~52 / 73 a year; cap must-be-zero numbers 0. Gaps: cash paid to players spreads ~2.5x real; rookie bonuses maybe ~2x (unchecked); a claimed waived player leaves all guarantees as your dead money; Pro Bowl option levels unused; option-year deals still labeled "Rookie".

**Free agency** - built. `free_agency.py`: 7 waves, `WAVE_ROUNDS` 3, summer price drops, make-room cuts, approaches (`set_approaches`: all in / normal / rebuild), cap plans (`spend_level`, `plan_keep`, `plan_next`), `LATER_COVER` all-in 0.5, `RFA_TENDER_MIN_VALUE` 1.0, bids moved by staff misjudgment. Results (12 leagues x 8 seasons): under 2% of the cap after wave 1 4.5-5.2 / 5.8 teams; 24th team 3.9-4.1% / 3.7; median 7.4-7.6 / 8.0. Gaps: new-team market deals ~100 / 148, re-signings 122 / 102; good FAs under 60% of value 48.6% / 34.6%; near-broke teams not tied enough to winning (correlation -0.17 / -0.28; next: weight record more in `set_approaches`); signed veterans play 59% / 43-47% of snaps; profits don't move AI owners' spending (held back).

**Draft, scouting, startup draft** - built. `draft.py` (real position mix, `POOL` 2.5, `CLASS_PER_PICK` 1.4, `LEVEL_SHIFT` -7, `PROSPECT_READY_MEAN` 0.82 / SD 0.08; AI boards with real error, crushes, speed pricing, `AGE_VALUE` -0.60, GM trade habits, next-year picks; no QB over a good young starter), `draft_day.py` (live from pick 1, speed control), `scouting.py` (20 interviews, 15 visits, 150 film hours; honest ranges; impressions; two scouts; Developed % from `DEVELOPED_RAW` 0.75), `screens/draft_page.py` (FOF8-style board, cloud bars, skill web, no numbers on prospect grades). Startup draft is New game's default (`STARTUP_POS_WEIGHT`, RB 1.53; `STARTUP_QB_EAGER`). `draft_check.py` (6 x 22): picks 1-5 start 3+ seasons 90-95% / 93, R1 83-85% / 78, rookies 8% of starters / 8, draft-day trades 21.6 / 21.1. Gaps: K/P drafted 1.6 / 3.9, WRs 25.7 / 28.6; startup RB shape, tackles and TE/C depth late; first TE median pick 28 / 21 (watch); no conditional picks; double-click opens two report copies.

**Offseason flow** - built. `offseason.py`, `season.begin_offseason` / `advance_offseason`, phase saved in `league.offseason`, Next button: season end (owner review, news freeze, history archive) -> GM changes, coaching carousel -> league year (re-sign, tags, options due by the draft) -> FA waves 1-4 (class announced, scouting) -> live draft -> waves 5-7 -> camp (90-man, development, captains, schedule) -> preseason (Hall of Fame Game + 4 weeks) -> final cuts -> 18 weeks -> 14-team playoffs -> Pro Bowl week -> Glory Bowl. Tools: `run_offseason`, `lab.py`.

**Coaches, staff, GMs, play calling** - built. `staff.py` (HC, OC, DC, asst HC, strength coach, college scouting director, pro personnel director, head trainer; budgets; carousel; `MARKET_K` 0.8; HC changes 6.78 / 6.6 a year), `evaluation.py` (own players ~1.5 points off, others by tape 8 / 5 / 3, rookies 4.9), `gm.py` (AI GMs with habits, 4.52 / 4.54 changes a year; `owner_review`), play calling (`sim/playcalling.py`, `game_page.py`: "Take over play calling", tendency reading, 3 games of film `READ_FILM_W` 0.4, `SCHEME_FIT_K` 0.20). `playcall_check.py`: sensible strategies +0.5 to +0.75 a game pooled; spamming costs 3-13. Gaps: trainer/strength effects, benching, AI in-season firings (`staff.ai_in_season` not hooked), Coach of the Year, high coach reputations, 7 teams over budget after the carousel, GM money habits ~0.3 / 0.5 (`GM_CAP_HELL` switches most money pushers off), no "retire" choice when fired.

**Trades** - built. `trades.py`, `news_trades.py`, `screens/trade_page.py`: per-player value through each staff's eyes, Jimmy Johnson chart, picks up to 3 drafts out, phone-call answers, lowball patience, window league year to the deadline after week 9. `trade_check.py`: 52.1 / 59.8 a league year, 0 of 937 illegal, exploit checks pass. Gap: star (10%+) trades 0.5 / 1.8 a year.

**News, Bitter, awards** - built. `news.py` (from records only; finished seasons frozen in `league.news_archive`), `news_words.py`, `storylines.py`, `bitter.py` / `bitter_words.py` (PG-13, ~80 bits a week in For you, accounts remember), `news_*.py`; `awards.py` (Players of the Week/Month, 50-voter season awards, All-Pro, Pro Bowl vote and tackle game, Glory Bowl MVP). `bitter_check.py`: 0 word-for-word repeats; `awards_check.py`: MVP QB 94% / 85. Gaps: RB MVPs rare; Pro Bowl replacements ~28 / 40+; same beat writer per team in every save; news archive writes a set in hash order (fix: sort in `news._enc`).

**History, Hall of Fame** - built Oct 25. `history.py`, `hall_of_fame.py`, `news_history.py`, `screens/history_page.py`. 5-season wait, 40 of 50 votes, 5 a class max, 25 seasons on the ballot. `hof_check.py`: odds by honors match; 3.9 / 4.5-5 inductees a year; DBs 11% / 19%, RBs 20% / 13% (DB All-Pros rarely repeat).

**Finances** - built Oct 26; stadium projects are next. `finances.py` (markets, real stadium mix, hidden franchise pull, two ticket prices a year, every team's books, owner money factor; profits drift only the staff budget), `news_finances.py`, `screens/finances_page.py`. `finance_check.py`: revenue 2.63x cap / 2.59, profit 0.48x / 0.45-0.50, ticket $160 / $161, crowd 67,963 / 69,376. Gaps: top team 1.42x average / 1.86x; 4.8% of team-seasons lose money / none.

**Screens, UI, windows** - built; UI overhaul with Gemini in progress. `main_page.py` (team-colored bar, page strip with badges), `nav.SECTIONS` (Home; Team: Roster, Depth chart, Position counts, Contracts, Trades, Staff, Finances; Schedule: Schedule, Watch a game, Playoffs; League: Standings, Stats, Awards, History, Records, Hall of Fame, League finances; Draft (offseason only); Bitter), `home_page.py`, `theme.py` (`DESKTOP_CSS`, `TOPBAR_CSS`, `STEP2_CSS`, `STEP3_HOME_CSS`, `TEAM_COLORS`), `popups.py`, `windows.py` (OS windows at fixed sizes). Gemini Steps 1-3 merged; Step 4 (game screen) package in `docs/for-gemini-step4/`, awaiting Gemini. Gaps: no postgame screen; windows don't remember position; harmless Quasar "Anchor" warnings.

**Check tools** (`tools/README.md`) - `scoreboard.py` (~10 min; suites fa, sim, determinism, rookies (8 leagues), integration, speed; ~380 numbers with noise bands; `--set`, `--save-baseline`), `lab.py`, `same_results.py`, `sweep.py`, `make_test_saves.py` + `screens_check.py` (last: 1,620 steps, 0 problems), `integration_check.py` (last: 0 problems), plus the per-system checks above. The fixed "saved" test league is `tools/data/realism_league.db`. Same seed = same league and results; New game is unseeded, so every new game differs.

## 3. Blake's decisions in force (beyond CLAUDE.md)

- Ratings shown are the staff's evaluation everywhere, no label; top ratings FOF8-rare; median shown player 50 (Oct 24-25).
- Rust dropped (Oct 23). Class "vintages" / talent eras not built, Blake declined (Oct 24). Startup pool "leave it honest" (Oct 24).
- You run your contracts; staff steps in only if you can't field a team; routine deals stay automatic (Oct 23).
- Practice squad: you by default, a toggle hands it plus injury cover to staff; your 53 is only touched to field a legal team (Oct 22).
- Preseason: Hall of Fame Game + 4 games each, classic starter playing time, never counts in stats; schedule set before the season; watch or sim your game (Oct 20).
- Modern camp: 90 men, one cut to 53 after the last preseason game (Oct 23).
- Scouting offseason only; Draft section hidden otherwise; prospect grades as clouds, no numbers; Developed % from raw; draft watched live (Oct 22-25).
- Owner can fire you: off by default; AI GMs hired and fired; GMs' "Known for" shown (Oct 23).
- Pro Bowl is a tackle game, its injuries never carry over; official awards exist (Oct 23).
- Bitter: ~80 bits a week, current snark, accounts remember (Oct 24); finished seasons' news frozen (Oct 22).
- Cap: TV-deal eras, "mostly market, some buzz"; AI cap room matches the real NFL (Oct 24). Void-year rules approved (Oct 26).
- Play calling: one "Take over play calling" box, toggle any time, coordinator picks personnel, no play clock, "They're keying on" kept (Oct 25-26).
- Contracts and Roster keep side panels (Oct 22). Captains voted by players; leadership generated the same at every position (Oct 20). `league.ORG_STRENGTH` stays 0.0.

## 4. Provisional, awaiting Blake

- Development numbers were "NOT locked" (Oct 20-21) and never explicitly locked; serious-injury rule (12+ weeks, 60%), `POSITION_RISK`.
- Aging (Oct 24): fitted `PEAK_SEASONS`, QBs' half decline and ~40 retirement, classes 3 points stronger, ~11% 9+ veterans accepted. New-league readiness and rookie ceiling shift (Oct 25).
- Developed %: a fifth of drafted players under 10% (a 0.72 raw point would soften it); rounds 6-7 show ~18-20.
- Sim: clean-up sack weights, star TE pull.
- PROVISIONAL items in the design docs (news, draft section 13, free agency, staff incl. GM style sizes, trades: patience, AI premium, ~6-7 calls a season).
- Awards: personality boost (~1-2 of 88 picks), Pro Bowl skip rate 15%+, names "Pro Bowl"/"All-Pro".
- Extensions: 1-2 years left, ~27% refuse, 3 low offers, undrafted extendable after 2 seasons.
- Draft room: speeds, opens paused, marked-player pause, FOF8 combine colors, Value column; average staff's best prospect QB ceiling ~73 (target was mid-70s to mid-80s).
- Hall of Fame: 25-season ballot, 5 a year, no pre-league careers, vote counts shown.
- FA commitment (Oct 26): all-in teams count half their later restructure room, its guard, 0.1% minimum restructure.
- Finances: the Oct 26 list (demand sensitivity, prices reset yearly, owner factor, seats/suites, value multiple, fan support).
- Looks: title screen, yellow main buttons, green headers, `DESKTOP_CSS`, 25 team color pairs, section name "Draft", Position counts as its own page.

## 5. Open threads, roughly by importance

1. Blake's open questions: coordinators' pass lean following team quality (fixes the pass-happy end and tempo spread)? Tune punt returns? How Developed % feels?
2. Free agency mid-market shortfall and near-broke teams not being winners.
3. Contract money pacing (cash spread, rookie bonuses), which also skews finances.
4. Sim: red-zone rebalance, 10+ TFL seasons, return tables, defensive blowout rest and DB rotation.
5. Stadium projects (next finances piece); profits -> AI owners' spending.
6. Coaching: benching, trainer/strength effects, in-season AI firings, Coach of the Year.
7. Draft gaps, HOF position mix, 9+ veteran share.
8. Gemini Step 4, a postgame screen, remembered window positions.
9. Approved for later: legacy rosters, instant history, choosing inactives, college stats/positions, arm length/hand size, pro days, a college-season hub.
10. CLAUDE.md's "Planned next" is out of date: main menu, new game, save slots, the 16/17-game setting and player development are all built.

## 6. Where to look in build-log.md

Top-level headings (search the exact start): `## Tech stack`, `## File layout` (old, incomplete), `## Decisions` (ratings, scarcity, roster rules, depth charts, captains, parity, name), `## Player development (design agreed Oct 19`, `## Game sim (Step 6`, `## Planned game flow`, `## Later ideas Blake approved`, `## Progress` (Oct 19-21 sim tuning), `## Step 7 plan` (every later `###` entry sits under it). Main `###` entries by topic (search these heading starts):

- Season: Piece 1: save slots / Piece 2: schedule / Piece 3: season stats / Piece 4a: career stats / Piece 4c: player development.
- Players: Ratings scale, real peak years / Does talent feel like a quota? / Aging and decline fitted / New leagues start settled / Careers: aging player by player / Combine results with real shapes.
- Injuries: Injuries rebuilt from real NFL data / Injury history.
- Rosters: In-season roster moves / Game day: 48 actives / Training camp, 90-man rosters / AI teams never over the cap in season.
- Sim: Overnight Oct 22-23 / Receivers and tight ends rotate / Playtest fixes: non-quarterbacks at QB / Single-game extremes / QBs: the top end / Out of position everywhere / Pass rush and tight ends retuned / Measured realism gaps / Running QBs and pass-happy teams / The follow-ups: return centers / Early-down run yardage / Tackles for loss after.
- Money: Step-by-step offseason and the Contracts tab / Your contract controls finished / Salary cap research / Every league its own dice / Multi-year cap plans / Standing checks against FOF8's / Void years / How hard AI teams commit money / Team finances.
- Draft: Draft screens: your own picks / Scouting you can see / The Draft tab as a real draft board / Scouting ranges made honest / Smarter AI front offices / Startup draft position values / The draft plays out live / Draft prospects rawer / Developed % counted from raw.
- Staff, GMs, trades, play calling: Coaching staff, staff-rated / AI teams decide through their own staff's eyes / AI general managers / The owner can fire you / Player trades / Calling plays while you watch / Play calling: scheme fit.
- News, history: Awards and the Pro Bowl / Bitter rehaul / Finished seasons' news / League history, the record book.
- Screens: Pop-ups like FOF8 / More pop-ups / Pop-out windows / Slim bar, sections and the Home page / The rest of the screens spruced up / Gemini's Phase 1 CSS (then Step 1-4 entries) / Blake's playtest notes, Oct 24.
- Tools, process: Git and the full integration pass / The league lab and the scoreboard / Several sessions at once / Standard test saves / Faster lab and offseason / The knob sweep / Overnight summary for Blake / A packaged copy.

All headings: `grep -n "^##" docs/build-log.md`. Several entries dated "Oct 22" sit after Oct 24-25 entries and describe later work; trust file order and content over the date label.
