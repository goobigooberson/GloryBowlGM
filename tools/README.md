# Realism tools

## Start here: the scoreboard and the league lab (Oct 25)

- `scoreboard.py`: one command runs the checks side by side (free agency on the lab, the
  sim's stats with QB season styles, determinism, drafted rookies' playing time, the
  whole-game test, speed; `--full` adds the draft), boils them down to about 380
  headline numbers next to the real NFL, and compares them with the saved baseline
  (`scoreboard/baseline.json`). It flags only changes bigger than the numbers' normal
  run-to-run swing (3x), as IMPROVED / REGRESSED (toward / away from the real NFL) or
  CHANGED; must-be-zero numbers (cap legality, determinism) as BROKEN; speed (CPU time)
  past 25%. The same build always gives the same numbers.

  ```
  python tools/scoreboard.py                       # before and after a change (~9 min)
  python tools/scoreboard.py --save-baseline       # after a change you're keeping
  python tools/scoreboard.py --suites fa --set free_agency.WAVE_ROUNDS=1   # try a knob, no code edit
  python tools/scoreboard.py --report-only --all   # re-read the last run, every measure
  ```
  Writes `scoreboard/latest.json` and `scoreboard/report.txt`.
- `lab.py`: the league lab every new check should build on. A league made the way New Game
  makes one, played through the game's own code: `season.play_week` week by week (camp,
  final cuts, injuries, roster moves, waivers, trades, awards, money), then the offseason
  phase by phase through `season.begin_offseason` / `advance_offseason`, exactly as the Next
  button plays it. `games="fast"` swaps each game for a quick made-up result (everything
  around the games is real; about 40 seconds a season + offseason since Oct 25); `games="real"`
  plays the sim. Checks attach to moments with `lab.on(event, fn)`: season_start, week_end,
  regular_season (week 1, after final cuts), season_end, offseason_start, phase_before /
  phase_after (each offseason phase or free agency wave). `python tools/lab.py 101 fast 2`
  plays one league two seasons and prints its progress. `free_agency_check.py` runs on it.
  `lab.fingerprint(league)` is a short code for the league's whole state (every League field,
  every player with his hidden values, the shared dice); `lab.fingerprint_parts` gives one
  code per field, to see what differs.
  (Older harnesses: `simlab.py` plays games from fixed rosters for the sim's stats;
  `draft_lab.py` runs the draft's 22-season careers without contracts.)
- `same_results.py`: proves a change plays out exactly as before (speed work, clean-ups). It
  plays the same lab leagues on an earlier commit (`--ref`, default main) and on this folder
  side by side, compares the whole league at every checkpoint (creation, week 1, season's
  end, every offseason phase) and prints each side's CPU time.

  ```
  python tools/same_results.py                                   # seeds 101 202 303, 1 season, fast games
  python tools/same_results.py --ref 8e2eea9 --seasons 3
  python tools/same_results.py --games real --seeds 101 --seasons 2
  python tools/same_results.py --ignore history awards           # leave out League fields main doesn't have yet
  ```

- Checks the scoreboard also runs, each usable alone (Oct 25):
  - `rookie_check.py`: drafted rookies' playing time by round vs real (regulars as
    rookies, late bloomers, ever regular; nflverse snap counts, 2013-2021 classes) and the
    draft board's Developed %. `python tools/rookie_check.py real` rebuilds
    `real_rookie_bloom.json`.
  - `qb_style_check.py`: efficient low-volume passers, running QBs and pass attempts per
    game vs real (2021-2025, games played, each season's attempts centered before
    pooling; until Oct 25 it was 2010-2024). `python tools/qb_style_check.py real` rebuilds
    `real_qb_styles.json`.
  - `integration_check.py`: the whole game with a team of yours, start to finish (startup
    draft, seasons, every offseason phase, save/load at each stage); prints the problems
    found (must be 0). `python tools/integration_check.py --seasons 6` before big commits.

## Calling your own plays: the balance check (Oct 25)

- `playcall_check.py`: is "Take over play calling" balanced? A bot calls one team's plays in
  every regular-season game of lab leagues (real games), with a fixed strategy: always run,
  always throw deep, always play action, random, pass more on early downs, a plausible human,
  the coordinator's best-fit play every time, going for it on 4th and short, and on defense
  always blitz, always man, always prevent, always stop the run, random; plus one call of its
  own each game and then always "Coach's call" (being read must cost it nothing), and one call
  spammed every snap but a different one each week (film of your last 3 games must make that
  no cheaper than spamming without film: `--set READ_FILM_W=0` for the comparison). The bot's side
  alternates home/away; its point margin a game is compared with "coach" (the staff's own
  calls: exactly the games nobody calls plays in). `probe:X` gives every offensive play of the
  bot's side a fixed read X, to see what a read is worth in yards (for the `READ_*` knobs in
  `engine/sim/tuning.py`).

  ```
  python tools/playcall_check.py                                  # every strategy, 6 leagues (~20 min)
  python tools/playcall_check.py --strategies coach,always_deep,probe:-0.2 --leagues 4
  python tools/playcall_check.py --set READ_PASS_SEP=1.5          # try a knob without editing code
  ```
  Writes `tools/playcall_report.txt` and `.json`.

## Tuning: the knob sweep (Oct 25)

- `sweep.py`: tries several values of engine settings side by side on the scoreboard's
  suites and ranks them against the real NFL. Every combination of the `--try` values (or
  `--variant` lists of knobs set together) plus the code as it is ("current"), all in one
  pool. Score = the average gap to real over the target measures, in noise units (lower is
  closer; under ~1 apart is luck). It also lists side effects: other measures that moved
  from current beyond 3x the noise. It never writes a setting into the code.

  ```
  python tools/sweep.py --suites rookies --try "draft.PROSPECT_READY_MEAN=0.80,0.82,0.85" --try "draft.PROSPECT_READY_SD=0.05,0.08"
  python tools/sweep.py --suites rookies --variant "draft.PROSPECT_READY_MEAN=0.88;draft.PROSPECT_READY_SD=0.05" --leagues 8
  python tools/sweep.py --suites sim --try "sim.tuning.SOME_K=0.9,1.1" --targets sim.common.edge_sacks>=10
  ```
  Writes `sweep/last_sweep.txt` and `.json` (git-ignored). Time: 3 variants x 8 rookie
  leagues took ~11 minutes. A knob another module copied with `from x import NAME` isn't
  reached; set it in the module that reads it.

## Screens: the standard test saves and the every-screen check (Oct 25)

- `make_test_saves.py`: rebuilds 19 saves, one at each moment of a game's year, through the
  same engine calls the screens make (New game's startup draft, Sim week, Start the
  offseason, the offseason's Next, the Contracts tab's franchise tag and free agency offers,
  the draft room). Your team (PIT by default) is a human team, as in a real game. The moments:
  startup draft (you on the clock), new game (camp open), preseason, week 8, trade deadline
  week, regular season over, playoffs, season complete, coaching carousel, re-sign, after
  your franchise tag, free agency waves 1 and 2 (an offer of yours out), the draft is next,
  draft day (pick 1 on the clock), the draft with you on the clock, after the draft, camp
  next, camp open (next preseason, 90-man rosters). The same seed makes the same saves
  (`index.json` lists each save with a fingerprint of its rosters, contracts and ratings).
  The first season plays the real game sim, because nearly every screen shows its stats;
  `--games fast` swaps in the lab's made-up results. Writes `data/test_saves/` (git-ignored,
  wiped each time); never touches `saves/`.
- `screens_check.py`: opens the game in browser mode (`app.py --browser --saves-dir=...`)
  on copies of the test saves and clicks through the main menu screens, every section and
  page of the green bar (`screens/nav.SECTIONS`), every view toggle and tab on them, the
  pop-ups (player card, team window, game summary, offseason report) and their tabs, the
  team picker (another team, the free agent pool), the draft room's views, and the Contracts
  tab's Re-sign and Free agency lists with a player picked. It never presses Sim, Next or
  Save. It reports every server error (a Python traceback in the game's log, a "500 Server
  error" page), every browser console error and anything it couldn't click, with the save
  and page, and saves a 1600x900 screenshot of every step (the Gemini package's size).
  Exit code 1 on any problem. Writes `data/screens/` (git-ignored): a folder of screenshots
  per save, `report.txt` (with full tracebacks), `report.json`, and the game's log.
  The driver is Playwright with Microsoft Edge, which every Windows PC has, so there's no
  browser to download. Playwright is a development tool only (`requirements-dev.txt`); the
  game never imports it, so it isn't in the .exe.

  ```
  python -m pip install -r requirements-dev.txt     # once
  python tools/make_test_saves.py                   # ~1.5 min; again after engine changes
  python tools/screens_check.py                     # ~4 min: every save, 3 game copies side by side
  python tools/screens_check.py --saves 12,15       # just saves 12 and 15
  python tools/screens_check.py --no-shots          # errors only, faster
  ```
  One browser message is known to be harmless and isn't counted (the report gives how many):
  Quasar's `Anchor: target "#c123" not found`, printed when a tooltip outlives the element
  it was on after part of the page is redrawn (e.g. the green bar after picking another team).

The tools below check that the game sim produces real-NFL-like stats. They were built
during Step 6 calibration (Oct 19, 2026) and are what the sim was tuned with.
None of them change or save your league. Run them from the project folder.

| Tool | What it answers | Time |
|---|---|---|
| `realism_check.py` | Do league averages, leaderboards and "how common" every kind of season is match the real NFL? Also how stats are shared within teams, defense volume, solo vs assisted tackles, receivers, workhorse backs, injuries | ~30-60 s per season |
| `team_sport_test.py` | Is it a team sport? Same QB/RB with a stacked vs average vs weak supporting cast; great QBs on a bad roster | several minutes |
| `consistency_test.py` | Does it feel random and real, not like a formula? Same rosters replayed: how much players' numbers move season to season vs the real NFL; does the best-rated player always lead (he shouldn't) | ~30-60 s per season |
| `recenter.py` | Re-measures `tuning.CENTER` (the average of each matchup adjustment) after big changes to how ratings are read | 10-20 min |
| `build_benchmarks.py` | Rebuilds `real_nfl_benchmarks.json` from the real data in `data/` (only if the data changes) | seconds |

Examples:

```
python tools/realism_check.py                                  # your saved league + 3 generated leagues, 2 seasons each
python tools/realism_check.py --leagues saved,101,102,103 --seasons 4   # 16 seasons: what calibration used
python tools/team_sport_test.py --league 101 --games 160
python tools/consistency_test.py --league saved --seasons 4
python tools/recenter.py              # look first
python tools/recenter.py --write      # then write the new centers into engine/sim/tuning.py
```

## How to read the results

- Use at least 8 seasons (16 is better) before judging a leaderboard number;
  2 seasons is mostly noise.
- `HIGH` / `low` means the sim's average is outside the real five-season range
  (2021-2025). Measures marked `*` can't match for a known reason (listed at
  the bottom of the report: kicker/punter churn, position labels in the real
  data).
- Expected until Step 7 adds signings/cuts: mid-pack tackle counts run a bit
  high (real teams use ~46 defenders a season, sim teams ~28).
- Expected until coaches can bench players: the occasional bad QB throws 20+
  interceptions.
- Injuries: real totals include training camp and preseason injuries, which
  the test seasons don't have yet.

## Workflow after changing the sim

1. If the change affects how ratings turn into matchup edges (any `*_K` knob,
   how a skill is read in `plays.py`, norms, player generation): run
   `recenter.py`, then `recenter.py --write`.
2. Run `realism_check.py --seasons 4` (16 seasons) and compare to the last
   report (`realism_report.txt`).
3. If anything about teams, targeting, usage or injuries changed, also run
   `team_sport_test.py` and `consistency_test.py`.
4. Guard rails Blake cares about: no 2,000-yard receivers except as a true
   once-in-decades freak (real record 1,964); tackle leaders in the real
   173-192 range (200+ very rare); a below-average QB with a stacked cast puts
   up good numbers; great QBs make bad rosters competitive; bell-cow backs
   exist but 300+ carry seasons stay around 3 a year. Judge records by
   per-game pace (Blake, Oct 20): most were set in 16-game seasons or
   shorter, so in 17 games an occasional season slightly past the old total
   is fine (receiving 1,964 in 16 games ~ 2,090 over 17; rushing 2,105 in
   16 ~ 2,240). Several in 16 sim seasons is not.
5. The "real range" in the report is from 5 real seasons. With 16 sim seasons,
   even a perfect sim puts about 1 in 6 seasons above the best real season of
   those 5 (2-3 of 16) just by chance. Count how many sim seasons pass the real
   max rather than reacting to the single highest one.

## Files

- `measures.py` - the shared definition of every measure (used for real and sim data)
- `awards_check.py` - plays whole seasons through the real season loop and compares the award
  winners (MVP, Offensive/Defensive Player and Rookie of the Year, Comeback) with the real
  2000-2025 winners: positions, team records, stats; plus All-Pro, the Pro Bowl vote (who gets in,
  the fan personality boost, replacements) and Players of the Week. Seasons are cached in
  your temp folder (`fof_awards_cache`, safe to delete); `--report-only --rescore` re-votes them with the current knobs
  in `engine/awards.py`. Writes `awards_report.txt`.
- `hof_check.py` - the Hall of Fame (`engine/hall_of_fame.py`) against the real one. `real`
  rebuilds `real_hof.json` from nflverse `draft_picks` (1980-2005 classes, careers over by 2015:
  who got in by first-team All-Pros, Pro Bowls and position, and the logistic fit of what voters
  weigh, which is where `hall_of_fame.CASE_*` come from). `run --leagues 4 --seasons 22` plays lab
  leagues with the real sim (about an hour, in parallel) and keeps each as
  `data/hof/<seed>.db` (a save file) and `.json`; `report` re-reads them: each whole-career retiree's odds of
  getting in someday (played through the Hall's vote) by All-Pros, Pro Bowls and position vs real,
  inductees a year, first-ballot share, and the leagues' own classes.
- `real_awards.py` - the real AP award winners 2000-2025 with their stats and team records (from
  the nflverse files in `data/`); run it alone to print the real profiles
- `game_extremes_check.py` - how often one-game spikes happen per season (400-yard and 5-TD passing
  games, 200-yard rushing/receiving games, 12+ catches, 3+ sacks, 10+/12+/15+ tackles, 2+ INTs, 4+
  field goals, 25+/30+ carries), plus season totals of long field goals (50+, 55+, 60+ tries and
  makes), game vs real (nflverse weekly stats 2021-25). The realism check covers season totals; this
  covers the single games the news and Players of the Week are built from.
  `--leagues 101,102,103 --seasons 2` (6 seasons, ~5 min; the counts move a few each run).
  Real combined tackles = solo + "with assist" + assists (all three nflverse columns).
- `big_games_real.py` - how often each kind of big single game happens a week in the real NFL
  (2015-25); the news uses it for its "big game" and "dominant game" bars
- `news_check.py` - builds a league, plays some weeks and prints sample news stories and social
  posts with automatic checks (no unfilled text, no hidden-rating words, no repeated headlines);
  `--weeks 18`, `--full` (a whole season, the offseason and 3 more weeks), `--cache file.pkl`
- `simlab.py` - loads/generates leagues and plays full seasons with injuries and (since Oct 22) the
  season loop's roster moves (`engine/transactions.py`): training camp and preseason injuries before
  week 1, final cuts, injured reserve, signings, practice squads, game-day elevations, every team
  run by the AI. Rosters are put back afterward, so each season starts from the same rosters.
  `play_season(..., moves=False)` plays the old way (frozen 53s), for comparisons. Reports from
  before Oct 22 had no roster moves: tackle, sack and kicker counts read differently since.
- `real_nfl_benchmarks.json` - the real NFL targets
- `data/` - nflverse player season stats 2015-2025 and snap counts 2023-2025
  (https://github.com/nflverse/nflverse-data)
- `realism_report.txt` - written by the last `realism_check.py` run
- `free_agency_check.py` - contracts, the cap and free agency vs the real NFL (`free_agency_report.txt`), playing the
  game's own offseason phase by phase (as the Next button does), then camp and the cut to 53; incl. the
  "fair price" check against FOF8's cheap-star exploit: do good free agents sign far below their worth while teams
  have room (real yardstick: `docs/research/fair_price.py`)? `--leagues 101,102,103 --seasons 4` (~5 min)
- `draft_check.py` - the draft vs the real NFL (`draft_report.txt`), incl. sections 14-15, the tight end checks
  against FOF8's "elite TEs fall past pick 8" exploit (rookie draft by true grade, public board and hindsight;
  startup draft vs real contract ranks; real data: `docs/research/te_draft.py`). ~10 min; `--startup-only` ~20 s
- `trade_check.py` - player trades vs the real NFL (`trade_report.txt`; real data: `docs/research/trade_research.py` -> `real_trades.json`): trades a league year and by phase, the deadline rush, deals per team, who's traded (position, age, contract size, stars), what comes back, how far out the picks are, legality; and the exploit checks (asks by position, quantity for quality, dumping bad contracts, buy low / sell high, lowballs). Made-up results, the game's own offseason. `--leagues 101,102,103,104,105,106 --seasons 3` (~4 min); `--calls 0` for a no-trades baseline
- `career_mix_check.py` - aging and careers vs the real NFL (Oct 24): week-1 rosters by experience and age, the share
  of 9+ year veterans, starters' age and experience, leaving the league by experience and age, career length,
  age at the last season, and (game only) starters' average overall by season and the rating curve by pro season.
  Real: nflverse weekly rosters 2013-26 and snap counts. Game: `injury_careers_sim.py run <seed> <seasons> <out.jsonl>`
  (about a minute a season; it also writes `<out>.w1.jsonl` and `<out>.players.jsonl`), then
  `python tools/career_mix_check.py <out1.jsonl> ... [--skip 6]` (leaves out each league's first 6 seasons, which still
  carry the made-up starting rosters). Use with `aging_check.py sim` and `retention_check.py` on the same files.
