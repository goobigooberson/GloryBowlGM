# CLAUDE.md

You're helping Blake build his own football general manager sim, a new and
improved successor to Front Office Football 8 (FOF8). Read this whole file,
then `docs/build-log.md` (the full record of what's built and decided) before
doing anything else. For design questions, also read
`FOF8 Design Reference for AI Context.pdf` (in this folder); its "Blake's
priorities" section overrides everything else in that document.

## The project

- Personal project for Blake's own use on his Windows PC. Not for sale, no
  other platforms, single-player only.
- Not a 1:1 remake. Change, cut or reinvent any FOF8 system when it makes the
  game better, and say what you changed and why.
- Stack (decided): Python 3.13, NiceGUI 3.18 (opens in its own desktop window
  via pywebview), SQLite saves in `saves/`. Start the game with `python app.py`.
- Version 1 scope: roster, game sim, in-depth stats and player info, free
  agency, draft, interview-based scouting, depth charts, and a news or social
  media hub.

## About Blake

- Near-zero coding experience (light HTML in high school). Explain each step
  in plain language and define new terms the first time you use them.
- Knows FOF8 deeply as a player. Treat his gameplay knowledge as expert.
- Values accuracy and directness and catches errors quickly. If you're unsure,
  say so. If you made a mistake, say so plainly and fix it, without deflecting.
- He wants the game "perfect and real": stats and outcomes must feel like the
  real NFL and never pre-determined or formula-like.

## How to work

- Build one system at a time, in small pieces Blake can run and test before
  moving on. Never try to build the whole game at once.
- Give complete files, never fragments or "add this somewhere."
- After each step, tell Blake what he should see when it works and what to
  check if it doesn't.
- When he reports an error, ask for the exact message or a screenshot rather
  than guessing.
- Keep the game's rules and data (`engine/`) separate from the screens
  (`screens/`), so balance and AI can be tuned later without rewriting the
  interface. Screens read from the engine only.
- Keep `docs/build-log.md` up to date: record decisions (with Blake's
  reasoning), what was built, test results, and known gaps. It's the hand-off
  record between sessions.
- Ask Blake before design decisions that are his to make (how something should
  feel or play). Make technical calls yourself and mention them.
- Measure every engine change: `python tools/scoreboard.py` before and after
  (~9 min; flags only changes bigger than normal run-to-run luck); save a new
  baseline (`--save-baseline`) when a change is kept. New check tools build on
  `tools/lab.py` (the game's own season and offseason code). See
  `tools/README.md`.

## Several sessions at once (Oct 25)

- A session that changes `engine/` or measures with the check tools works in
  its own git worktree (a separate folder on its own branch; start it with
  `use_worktree: true`), so other sessions' unfinished edits can't leak into its
  measurements or be overwritten. In a new worktree run
  `python tools/link_data.py` once (links the 643 MB real-data folder instead
  of copying it). The main session merges finished branches.
- Sessions sharing the main folder (reading, or screens nobody else touches):
  say which files you're editing in the shared notes or to the session that
  owns them, and leave other sessions' files alone.
- Line endings are handled by `.gitattributes` (git compares text as LF); don't
  convert files between line endings.
- OneDrive: if removing a worktree leaves `.git/worktrees/<name>` that can't be
  deleted ("Permission denied"), OneDrive marked it read-only; in PowerShell:
  `Get-ChildItem -Recurse -Force .git\worktrees\<name> | % { $_.Attributes = 'Normal' }`
  then `Remove-Item -Recurse -Force .git\worktrees\<name>`.
  If the worktree folder itself is left behind, first remove its data link alone with
  `cmd /c rmdir <folder>\tools\data\nflverse` (a link to the real 643 MB data; `rmdir`
  removes only the link), check it's gone, then clear the flags and delete the folder.

## Design rules

- Show numbers the way football fans expect: heights in feet-inches (6-2),
  combine results in real units, ratings as word-plus-number like
  "Very High (87)" (see `engine/formatting.py`).
- Label every button and column. One main view is the home base: a slim green
  bar with six sections (Home, Team, Schedule, League, Draft, Bitter), page
  buttons under it, side panels on the pages (Oct 22; `screens/nav.py` sorts
  pages into sections, `screens/home_page.py` is the overview; new pages get a
  tab in `main_page.py` plus an entry in `nav.SECTIONS`); detail views (player card, team window, game summary, offseason report)
  and the draft room open as pop-ups over it, FOF8-style, and they stack (Blake,
  Oct 21-22; reverses the old "no floating pop-ups" rule). Use `screens/popups.py`
  for new ones; any `<a href="/player/ID">`, `/team/ID` or `/game/ID` link on the
  game screen opens its pop-up by itself (`popups.player_link`, `team_link`).
  In the game window, player cards, team windows and game summaries open as real
  Windows windows (drag anywhere, any monitor, several at once, kept in front of the
  game, redrawn on `state.mark_changed`): `screens/windows.py` (Blake, Oct 22;
  Settings can switch it off; browser mode keeps the in-window pop-ups).
  The look's "desktop feel" layer is `theme.DESKTOP_CSS`.
- Design AI teams to resist the FOF8 exploits: TEs falling late in the draft,
  easy trades for certain positions, underpriced free agents, and drafting a QB
  over a good young starter.
- Hidden ratings are never shown on screens: consistency, durability,
  interception avoidance, fumble avoidance, Generational status.
- How a new league's teams are formed (Blake): the main way is a league-wide
  startup draft, so teams that draft well start strong and teams that draft
  badly start weak. Historical rosters (real NFL seasons) are uneven like the
  real NFL. The "random generated rosters" option (what exists today, and what
  the test leagues use) makes fairly even teams; `league.ORG_STRENGTH` (0.0)
  only affects that option. Once the startup draft exists, rerun the realism
  tools on drafted leagues: team strength will spread out more, closer to the
  real NFL.
  In a generated league the gaps should grow over the seasons from player
  development (breakouts and fall-offs), injuries, drafting and free agency.
  Step 7 check: sim several seasons from a generated league and confirm team
  strength spreads toward the real NFL's (about 6 points per game, 1 standard
  deviation, vs about 4 at the start).

## The game sim (Step 6, done) - handle with care

The sim (`engine/sim/`) was calibrated against real NFL data on Oct 19, 2026:
league averages, every leaderboard rank and "how common" each kind of season
is, team-sport effects, season-to-season randomness, injuries. All knobs live
in `engine/sim/tuning.py` with comments. Before and after any change that
could affect stats:

- Run `python tools/realism_check.py --seasons 4` (16 seasons; see
  `tools/README.md` for how to read it). Compare with the previous report.
- If the change affects how ratings turn into matchup edges, run
  `python tools/recenter.py --write` first.
- If it touches teams, usage, targeting or injuries, also run
  `tools/team_sport_test.py` and `tools/consistency_test.py`.
- `python step6_season_test.py` is Blake's own quick one-season check (prints a
  report and writes `step6_season_report.txt`).
- Change one thing at a time; never "fix" a leaderboard by capping a stat.
  Nothing in the sim is capped and that's deliberate (5,000-yard seasons can
  happen); outliers are controlled by football mechanisms (coverage
  adjustments, workload, injuries, diminishing returns).

## Planned next (Step 7: season loop)

See "Planned game flow", "Player development" and "Progress" in the build log.
Decided items waiting to be built:
- A "Regular season games" league setting (16 or 17; default 17). The engine
  is per-play, so only the schedule and the report benchmarks change (scale
  real benchmarks by games/17).
- Player development as designed in the build log (potential shifts, two
  layers, staged reveals). Rust was dropped (Blake, Oct 23).
- Main menu, new game, save slots.
- Coaches will eventually replace the random coordinator styles in
  `gameteam._build_tendencies` and should bench players who play badly.
- Roster moves during a season: built Oct 22 (`engine/transactions.py`: practice
  squads, injured reserve/PUP, signings, waivers, elevations, real NFL rules;
  training camp injuries and next-season carryover). Since Oct 23 camp runs
  with 90-man rosters and one cut to 53 after the last preseason game
  (`transactions.final_cuts`), and contracts, free agency and the draft are in
  (`contracts.py`, `free_agency.py`, `draft.py`). The offseason plays in phases
  with a Next button (`offseason.offseason_start/next`, `season.begin_offseason/
  advance_offseason`); you run your contracts on the Contracts tab
  (`screens/contracts_page.py`) and your draft on the Draft tab
  (`engine/draft_day.py` runs it pick by pick, `engine/scouting.py` interview
  scouting, `screens/draft_page.py`; new games start with a live startup draft).

## Files

- `app.py` starts the game; `screens/` is the interface; `engine/` is the rules.
- `engine/transactions.py` roster moves (AI and yours); `engine/injury_report.py`
  week-to-week injury rules shared by the season and the tools.
- `engine/storylines.py` what's building over a season (streaks, form, races, injury
  fallout); `engine/news_words.py` the phrase library and the Writer that spreads wording
  across a season; `engine/bitter.py` / `engine/bitter_words.py` Bitter, the league's social
  media site (invented accounts, their voices; PG-13); `engine/awards.py` /
  `engine/news_awards.py` awards and the Pro Bowl (`screens/awards_page.py`).
- `engine/news.py` news stories and social posts, built from the league's records
  (nothing saved); `screens/news_page.py` the Bitter tab (the league's social media site); `tools/news_check.py`.
  Design and Blake's open choices: `docs/news-design.md`.
- `engine/awards.py` official awards and the Pro Bowl (Players of the Week/Month, MVP and season
  awards by a 50-voter media panel, All-Pro, fan/player/coach Pro Bowl vote, alternates, the Pro
  Bowl game in the week off, Glory Bowl MVP; saved as `league.awards`); `engine/news_awards.py`
  their news; `screens/awards_page.py` the Awards tab; `tools/awards_check.py` vs real winners.
- `engine/league_money.py` where the salary cap comes from after 2026: TV-deal eras, labor
  deals, rare shocks, league buzz, next year's projection (saved as `league.tv`; Blake, Oct 24);
  `engine/news_money.py` its news. AI teams' yearly approach (all in / normal / rebuild) is in
  `free_agency.set_approaches`; `tools/free_agency_check.py` compares cap room at free agency's
  opening with the real NFL's.
- `engine/finances.py` team finances (Blake, Oct 26: two ticket prices a year, every team's books,
  stadiums that age, the owner judges winning first and money at the edges): markets, stadiums,
  demand and prices, each home game's crowd and money, the profit and loss (saved as
  `league.finances`); `engine/news_finances.py` its news; `screens/finances_page.py` the Finances
  page (Team) and League finances (League); `tools/finance_check.py` vs real data
  (`docs/research/finance_research.py`). Stadium projects (new, renovations) are the next step.
- `engine/gm.py` the AI teams' general managers (Blake, Oct 22: draft-day, free agency, own-player and cap
  habits, hiring coaches; hired and fired like real GMs; `docs/staff-design.md` section 10);
  `engine/news_front_office.py` GM and head coach news; `tools/gm_check.py` vs real GM data
  (`docs/research/gm_research.py`, `real_gm.json`).
- `engine/sim/` game sim; `engine/player.py` player generation (incl.
  durability/RB endurance via `fill_new_ratings`); `engine/depth.py` depth
  charts; `engine/database.py` save/load (older saves get new fields filled on
  load).
- `tools/` realism tools and real NFL benchmark data.
- `docs/build-log.md` the project record. Blake also keeps a copy in his
  claude.ai Project; `docs/build-log.md` is the one to update from now on.
