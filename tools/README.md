# Realism tools

These check that the game sim produces real-NFL-like stats. They were built
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
- `free_agency_check.py` - contracts, the cap and free agency vs the real NFL (`free_agency_report.txt`), incl. the
  "fair price" check against FOF8's cheap-star exploit: do good free agents sign far below their worth while teams
  have room (real yardstick: `docs/research/fair_price.py`)? `--leagues 101,102,103 --seasons 4` (~5 min)
- `draft_check.py` - the draft vs the real NFL (`draft_report.txt`), incl. sections 14-15, the tight end checks
  against FOF8's "elite TEs fall past pick 8" exploit (rookie draft by true grade, public board and hindsight;
  startup draft vs real contract ranks; real data: `docs/research/te_draft.py`). ~10 min; `--startup-only` ~20 s
- `trade_check.py` - player trades vs the real NFL (`trade_report.txt`; real data: `docs/research/trade_research.py` -> `real_trades.json`): trades a league year and by phase, the deadline rush, deals per team, who's traded (position, age, contract size, stars), what comes back, how far out the picks are, legality; and the exploit checks (asks by position, quantity for quality, dumping bad contracts, buy low / sell high, lowballs). Made-up results, the game's own offseason. `--leagues 101,102,103,104,105,106 --seasons 3` (~4 min); `--calls 0` for a no-trades baseline
