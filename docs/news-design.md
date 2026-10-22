# News and social media hub: design (built Oct 22, 2026, overnight)

Part of the Version 1 scope ("a news or social media hub"). Blake was asleep when this was
built, so **every choice about how it feels is marked PROVISIONAL, for Blake's review**.
Technical choices are explained but not marked.

## What it is, in plain terms

A **News** tab. In the middle: news stories, newest first, like a sports website.
On the right: a social media feed, with posts from league insiders, each team's beat
writer, a stats account, players and fans. On the left: checkboxes for which kinds of
stories to show. Across the top: whose news (the whole league, your team, any team, or
one player) and which season.

Everything is **built from what the game already records**: box scores, career stats,
the injury history, the transactions log, the draft history, retirements, team history,
captains, awards. Nothing new is saved, so old saves get news right away, and the news is
always in step with the actual results.

**Fresh but stable wording.** Each league has its own random "dice" (set when the league
starts), so two leagues tell the same kind of story in different words, and a story never
changes once written (reloading gives the same text). Blake's call (Oct 22): stories must
feel fresh, never repeated, and react to storylines as they form.

## Bitter: the league's social media site (built Oct 23, Blake's idea)

Blake: make it "organized as if it's a social media page. Let's call it Bitter instead of
Twitter", with reporters, fans, celebrities and others posting "bits" that "give it more flavor
and personality in the story of the league rather than just generic statements."

Decided with Blake (Oct 23): **tone is PG-13** (trash talk, roasts, hot takes, sarcasm, memes;
no swearing or slurs, so a Steam rating isn't a problem); **news stories are posted as bits** by
outlet accounts, with an article card you open to read the full story. **Weekly power
rankings: keep weekly** (Blake).

The page (`screens/news_page.py`, still the News tab until the parent session renames it): a
Bitter header with the filters (For you / Your team / A team / A player, season); on the left,
which kinds of accounts to show; in the middle the timeline (avatar, name, gold check for
verified accounts, handle, the bit, quote-bits, article cards, replies, likes and rebits); on the
right "What's happening" (trending hashtags, players and teams) and "Who to follow".

The cast (all invented, PROVISIONAL, for Blake's review), in `engine/bitter.py`:
- **League Wire** and **Gridiron Daily**: every news story, as a bit with an article card.
- **Insiders** (Dana Kessler, Marcus Okafor, Tori Vance) break injuries and moves; the
  **League Stat Desk** posts numbers; one **beat writer** per team posts finals.
- **Team accounts** for all 32 teams: finals (with fans replying), clinches, draft picks,
  signings, players back from injury, thank-yous to retiring players. Each team has a hashtag
  (#HoistTheSails, #BringTheStorm...).
- **Rex Harmon**, a TV host who makes hot takes ("Dallas is DONE"). The game remembers them:
  **Football Receipts** quote-bits him when he's proven wrong ("Rex, buddy. Baltimore is 0-3
  since you said this."), and Rex takes a victory lap when he's right.
- **Walt Brennan**, a grumpy old-school columnist (loves a 13-9 game, hates shootouts).
- **Fantasy Freddie** (big fantasy days, busts, injuries), **Big T Holloway**, a former
  lineman who watches film (sacks allowed, rushing days, defenders who lived in the backfield),
  **Gridiron Memes** (shutouts, blowouts, blown leads, game-winning kicks, long losing streaks).
- **Ten fictional celebrities**, each rooting for one team (picked per league): a rapper, a pop
  star, a country singer, an actress, a comedian, a basketball star, a chef, a wrestler, a DJ,
  a talk show host. They celebrate big wins in their own voice and sulk after losses.
- **Fans**: three per team, a homer, a worrier and a trash talker who dunks on division
  rivals when they lose.
- **Players** post after big games, injuries, promotions, awards and retirement.

Likes, rebits, replies and follower counts are invented flavor (players' followings follow
their popularity), the same every time for a league. Every opinion is the account's; every
fact comes from the league's records.

### Blake's answers on the open choices (Oct 23)

- **Celebrities**: "please, for my health" belongs after a nail-biting win, not a loss (Blake;
  done: close wins and overtime wins get their own celebrity lines).
- **Player posts (#4)**: mostly generic, but some players are wild: bold, weird or cryptic
  like real players. Built: each player has a personality picked at random per league (never
  from his ratings): about 1 in 10 bold (trash talk after wins, "that ain't happening twice"
  after losses, and sometimes a public guarantee before a game: if his team loses, Football
  Receipts quote-bits it; if it wins, he posts "Told y'all" quoting himself), about 1 in 17
  cryptic ("👀", "Loyalty is rare these days", "Patience."), about 1 in 25 weird ("Cereal is a
  soup. I will die on this hill."). The rest post the usual things.
- **How much news (#5)**: "as much news as will make it feel real." The "For you" feed shows
  articles and insiders at importance 25+, and opinion accounts, players, celebrities and fans
  at a lower bar so there's plenty of personality (`bitter.FOR_YOU_BARS`): about 200 bits a
  week in a test season. A team's or a player's view shows everything.
- **Big games (#6)**: Blake's QB rule (300+ yards or 3+ TD passes with 0-1 INT, flexible for a
  huge day like 450 yards, 4 TDs, 2 INTs) and "a dominant performance for all positions."
  Built from real NFL games 2015-2025 (`tools/big_games_real.py`) as two levels (`news.big_game`):
  a **big game** is celebrated on Bitter (fantasy guy, fans, the player); a **dominant game**
  also gets its own story and a stat desk bit.

  | Position | Big game | Dominant game |
  |---|---|---|
  | QB | 300+ yds or 3+ TD with 0-1 INT, or a huge day like 450/4/2 | 300+ yds and 3+ TD with 0-1 INT, 400+ yds, 4+ TD, or 100+ rushing yds |
  | RB | 100+ rushing yds and a TD, or 150+ from scrimmage | 200+ from scrimmage, 3+ TD, 150+ rushing and a TD, 175+ scrimmage and a TD |
  | WR | 100+ yds and a TD, or 10+ catches for 120+ | 150+ yds, 3+ TD catches, 125+ yds and 2 TD |
  | TE | 100+ yds or 2 TD catches | 125+ yds, 3 TD, or 100+ yds and 2 TD |
  | DL | 2+ sacks, a sack and a forced fumble, 3+ TFL, an interception | 3+ sacks, 2 sacks and a forced fumble, a defensive TD |
  | LB | 2+ sacks, 15+ tackles, an INT, 12+ tackles with a sack or TFL | 3+ sacks, 18+ tackles, a defensive TD, 2 INT, an INT and a sack |
  | DB | an INT and 3+ passes defensed | 2+ INT, a defensive TD, an INT and a sack |
  | K | 4+ FG or a 55+ yarder | 5+ FG or a 58+ yarder |
  | Returner | | a kick or punt return TD |

  Real NFL a week: about 8 QBs, 5 RBs, 6 WRs, 2 TEs have big games. In a test season the sim
  gave about 16 dominant-game stories a week. Two sim differences showed up (for the realism
  tools, not the news): linebackers get 15+ tackle games about 4 times a week (real NFL: under
  1), and long field goals are more common than in the real NFL.
- **Milestones** (asked what this meant): season marks like reaching 1,000 rushing or
  receiving yards, 4,000 passing yards, 100 catches or 10 sacks, and career marks like 10,000
  passing yards or 50 sacks (only for players whose whole career is in the league's records).
- **#8 no ratings in news**: OK (Blake). **#9 weekly power rankings**: keep weekly (Blake).
- **#10 storyline thresholds**: Blake left it to me. Decided: a streak story at 3 straight
  100-yard rushing or receiving or 300-yard passing games (then 5, 7...), 3 straight games with
  an interception, 5 straight with a sack, a touchdown, or 2+ TD passes; a turnaround when a
  team that started 1-4 or worse (at least 3 games) wins 3 straight and gets back to .500; a
  collapse when a team that started 3-1 or better (at least 4 games, .750+) loses 3 straight;
  a breakout for an undrafted, Round 4-7 or first/second-year player with three straight strong
  games; a QB slump at a passer rating under 62 over three games. These match how often real
  streaks make news; easy to change in `engine/storylines.py`.

## Storylines and the phrase library (built Oct 22-23, after Blake's feedback)

Blake: "I want fresh new generated stories... they should legit feel like a reaction to
the league... every single time if storylines are starting to form." Decided: no online
AI and nothing that needs a strong PC (he may sell the game on Steam someday), so the
built-in writer had to get much better on its own. An optional local-AI writer could be
added later; see "Later".

Three pieces:
- `engine/storylines.py` follows each season week by week: every player's game-by-game
  lines, team results, streaks, division standings, who's been lost to injury and how the
  team has done since, players coming back from injury, quarterback form. A story about
  Week 7 only knows what was true after Week 7.
- `engine/news_words.py` is the phrase library: about 117 kinds of sentences and 480 ways
  to say them, built from interchangeable pieces. Its Writer remembers, across the whole
  season, which wordings it used lately and doesn't reuse one until most of the others have
  had a turn. Lines that only fit certain facts (a streak, a comeback, a sweep) are used only
  then, and are favored when they fit, so the unusual angle wins.
- `engine/news.py` decides what's news and which facts each story gets.

What game stories now pick up from the season so far: win and losing streaks (and when one
is snapped), a team's first win, still-unbeaten and still-winless teams, taking over first
place, how far behind the division leader a team sits, avenging an earlier loss or sweeping
the season series, a player's ongoing streak, a player back from a long injury, a team's
record since losing its quarterback or a star, plus box-score angles (turnover battle,
yardage, team rushing, sacks, penalties), halftime scores, late go-ahead scores and weather.

New stories that follow the season (PROVISIONAL, for Blake's review):

| Story | When |
|---|---|
| Streaks | 100-yard rushing or receiving games and 300-yard passing games (at 3, then 5, 7...), multi-TD passing games, touchdown, sack and interception streaks (at 5) |
| Breakouts | an undrafted player, a Round 4-7 pick or a first/second-year player with three strong games in a row (once a season each) |
| Slumps | a quarterback with a passer rating under 62 over his last three games |
| Turnarounds and collapses | a team that started 1-4 (or worse) and won three straight back to .500; a team that started 4-1 (or better) and lost three straight |
| Life without a star | a team's record (and scoring) 3 and 6 games after losing its QB or a star |
| Comebacks | a notable player's first game after missing three or more games |
| Record paces | weeks 8, 11 and 14: on pace for 2,000 rushing yards, 5,000 passing yards, 20 sacks and similar, and for the league record |
| Division races | from Week 12, every other week, when the top two are within a game |
| Race for the No. 1 pick | weeks 10, 13, 16 |
| Power rankings | every week from Week 2: all 32 teams with movement and a one-line reason each (last result, streak, a key injury, a hot player). Our opinion, weighted by record, then point differential and recent form |
| Previews | before every week: the three most interesting games and why (first place on the line, a rematch, streaks, an unbeaten team, a hot player) |
| Rookie watch | weeks 5, 8, 11, 14, 17 |

The MVP race comes from the league's awards (`engine/news_awards.py`, built by the awards
session), so there's only one.

Measured on a full test season (272 regular-season game stories): no two stories are the
same, and the most repeated sentence shape appears in about 19 stories (it was 55 before).
There are about 170 different headline shapes.

## Rules it follows

- **Never invents facts.** Every number, injury, signing, record and result in a story
  comes from the game's records. Opinions are allowed only where they're clearly
  opinions: fans' posts ("Fire everybody"), and plain color ("a rough day").
  No made-up quotes about real decisions, no made-up events.
- **Never mentions hidden ratings** (consistency, durability, interception or fumble
  avoidance, Generational status). Ratings are never printed in news at all. They only
  decide who is newsworthy, on the shown scale (`engine.scale.shown`): a player rated
  62+ (NOTABLE) or a starter counts as notable; 72+ (STAR) as a star.
- **Varied wording.** Each kind of story has many ways to say it, and the Writer spreads
  them across the whole season (see "Storylines and the phrase library"). A player whose last name
  matches a teammate's, or a city or team name ("Washington"), gets his full name in
  headlines. The check tool flags any headline repeated word for word in a week
  (currently none in a full season plus offseason).
- Newspaper style: AP-style numbers (one to nine in words), full name on first mention
  and last name after, winning score first ("a 27-24 loss to").

## Story types (the left-hand checkboxes)

| Type | What triggers it |
|---|---|
| Game stories | Every played game: preseason (short), regular season, playoffs. The headline and lead fit how the game went: comeback (trailed by 14+), overtime, upset (winner's record at least .300 worse, Week 4+), shutout, blowout (21+), close (3 or less). Plus the top player on each side, the go-ahead score when it came late ("Devon Washington's 38-yard field goal with 0:08 left in the fourth quarter put the Liberty ahead for good"), the halftime score, rain/snow/strong wind, records and streaks. |
| Big performances | One game worth its own story: 400+ passing yards, 5+ TD passes, 175+ rushing or receiving yards, 3+ rushing or receiving TDs, 14+ catches, 3+ sacks, 2+ interceptions, a defensive or return TD, 5+ field goals, a 57+ yard field goal, and 4+ interceptions thrown (the bad kind). Adds "No one has had more ... in a game this season" (Week 3 on) and his season total with his league rank. Also the outlet's **weekly standouts** (best offensive and defensive games). |
| Milestones and records | Season marks (4,000 passing yards, 1,000 rushing/receiving yards, 100 catches, 10/15/20 sacks...), with a pace projection until the last three weeks. League single-season records (the most in a season since the league began). Career marks (10,000 passing yards, 100 TD passes, 50 sacks...) only for players whose whole career is in the league's records (see Known gaps). |
| Injuries | Every injury that costs games: what it is, against whom, and how long ("expected to miss about three weeks", "out for the season", "expected to miss the rest of the regular season"), aggravations and re-injuries, repeat injuries ("hurt again"), two injuries in one game merged into one story. Plus this week's **injury report** for each team (Out / Concussion protocol / Doubtful / Questionable) and a league-wide "Key players out" list. |
| Roster moves | Each team's weekly transactions list, plus stories for notable releases, signings (including who released him), activations from injured reserve, and practice squad promotions. Cut-downs and camp (final cuts, training camp, preseason, offseason) log hundreds of moves at once, so they get one league-wide roll-up each ("Final cuts: the notable names let go"); only a star's release gets its own story, and a team's list on a big day shows counts plus the known names. |
| Playoff race | "If the season ended today" (from Week 11), clinching a playoff spot / division / No. 1 seed, elimination, and the playoff field. |
| Draft | The No. 1 pick (with the record that earned it and any standout combine result), the first round, every team's class, Mr. Irrelevant. |
| Retirements | Notable veterans: seasons played, teams, career numbers, titles won. |
| Season and team news | The season in review (champion, best record, league leaders) and each team's captains. |

**Clinching math is careful on purpose:** it only announces a clinch or an elimination
that is certain, counting any possible tie against the team. So it never announces one
too early, but it can be a week later than the real NFL's tiebreaker-aware announcements.

## How much news (PROVISIONAL, for Blake's review)

Each story gets an importance from 0 to 100. The league-wide view shows 25 and up
(`news.LEAGUE_VIEW_MIN`); your team, another team or a player shows everything. The
"Include minor items" checkbox shows everything league-wide too.

In a full test season the league-wide view had about 40-50 stories a week: ~15 game
stories, ~12 injuries (notable players out 4+ weeks, season-ending, or any star), ~12-18
big performances and milestones, and a few moves. A team's own view adds every injury,
every transaction and its captains.

| Knob in `engine/news.py` | Now | What it does |
|---|---|---|
| `LEAGUE_VIEW_MIN` | 25 | league-wide story cutoff |
| `POST_LEAGUE_VIEW_MIN` | 30 | league-wide social cutoff |
| `NOTABLE` / `STAR` | 62 / 72 (shown scale) | who is newsworthy / a star |
| `FEATS` | see table above | what makes a big game |
| `SEASON_MARKS`, `CAREER_MARKS` | see file | milestones |
| `STANDOUTS` | on | the outlet's weekly standouts |

## Choices waiting for Blake (all PROVISIONAL)

1. **Weekly standouts**: the league now has official Players of the Week (awards
   session), so the outlet's own "Week N standouts" only appear for weeks without them
   (older saves).
2. **Social personas are invented**: three insiders (Dana Kessler, Marcus Okafor, Tori
   Vance), a League Stat Desk, one beat writer per team (names drawn from the game's name
   lists), three fan accounts per team, and players posting on their own accounts. None
   imitate real reporters.
3. **Fan tone**: fans celebrate, complain and overreact ("Fire everybody", "Mock draft
   season it is"). Is that the feel Blake wants?
4. **Player posts** are short and generic ("Team win. Proud of my guys.", "I'll be back
   stronger"). No made-up quotes about contracts, coaches or teammates.
5. **How much news league-wide** (the importance cutoffs above).
6. **What counts as a big game** (`FEATS`) and the milestones.
7. **Captains** are reported as "players voted X the offensive captain", which is what
   the game does.
8. No ratings ever appear in news, not even shown-scale ones. A real outlet would say
   "Pro Bowl-caliber", but that risks reading as a hidden judgment. Easy to add later.
9. **Power rankings, previews and the rookie watch** are the outlet's opinion, worked out
   from records, point differential and recent form. Is weekly too often for power
   rankings?
10. **Which storylines become stories**, and at what thresholds (the table in "Storylines
    and the phrase library").

## What's different from FOF8, and why

FOF8's news is mostly a list of results and transactions. This adds written game
stories, injury reports with game-day status, milestones and records, playoff-race
math, and a social feed, because Blake wants the league to feel like the real NFL.
Everything is generated from real game data, never scripted, so it can't drift from
what happened.

## Later

- **Optional local-AI writer** (discussed with Blake Oct 22). A small AI model running on
  the player's own PC could write story text from the same fact sheets, with a checker
  that rejects any story whose names or numbers aren't in the facts (falling back to the
  built-in writer). It must stay optional (an Off / Small / Large setting) so the game
  runs on ordinary PCs, and any model shipped must have a license that allows selling the
  game. Only worth adding if a small model clearly beats the built-in writer in testing.

## Known gaps

- **Earlier seasons' game stories** come from the save's history file (box scores move
  there when a new season starts). The tab loads one season's file when you pick that
  season. "All seasons" shows earlier seasons' other news (draft, retirements, injuries,
  moves, playoff field, season review) but not their game stories, to keep it fast.
- **Career milestones** only count players whose whole career is in the league's
  records (drafted in or after the league's first season). Veterans who were already in
  the league when it began have earlier seasons the game never recorded, so "career"
  numbers for them would be wrong. Retirement stories say "in N seasons since 2026" for them.
- **Practice injuries during the preseason** are recorded by the season as "Training
  camp", so news dates them to camp.
- No trade news (trades don't exist yet). Free agency and the new draft engine are being
  built in other sessions: their moves will appear in the weekly transactions lists right
  away (any unknown move type is listed as written). Dedicated free-agency stories ("X
  signs a 3-year deal") should be added once contracts exist.
- League single-season records start counting from the league's first season, and the
  first season has none (no prior season to beat).
- News is rebuilt from the records each time, not stored. If the wording code changes,
  old stories are reworded too (the facts don't change).

## Sim observations noticed while testing (for the realism tools, not news bugs)

- **Long field goals look too common.** In a 10-week test, several weeks had three
  field goals of 57+ yards, including 59, 60, 62, 63 and 65 yards. The real NFL has only
  a handful of 60+ yarders a season. Worth a look with `tools/realism_check.py`.
- One defensive end had 12 sacks through six games (real record pace is rare but
  possible). One sample season had a 20-TD receiver, a 1,978-yard receiver and a
  4,990-yard passer. These may be within normal outlier range; the realism tools are the
  place to judge.

## Testing

- `python tools/news_check.py` builds a league, plays the preseason and 6 regular-season
  weeks, and prints sample stories and posts (league view, a team view, one of each
  story type, a player view, social). `--weeks 18` plays the whole regular season;
  `--full` plays a whole season with playoffs, the offseason (draft, retirements) and 3
  weeks of the next season; `--cache file.pkl` reuses the simmed league next time.
  Output also goes to `tools/news_check_report.txt`.
- Automatic checks in that tool: no unfilled template gaps, no "None", no hidden-rating
  words, no headline repeated in a week. A full season plus offseason (4,253 stories,
  2,903 posts, built in 0.6 seconds) passes all of them.
- The tab itself was tested in the browser with a stand-alone harness (the game screen
  doesn't have it wired yet): filters, player search, player links, the Game summary
  button, picking an earlier season (history file), no console errors.

**What Blake should see once it's wired:** a News tab. Sim a week, open it, and the
top stories are that week's games, big performances and injuries; the right side has
the social feed. Click "Your team" for everything about your team, including its injury
report for the coming game. Click a player's name to open his card.

---

## Integration steps (for the session that owns `screens/main_page.py`)

No new saved fields, no database changes, no changes to any engine file. Only
`screens/main_page.py` needs editing:

1. Import, with the other tab imports:
   ```python
   from .news_page import build_news_tab
   ```
2. Add the tab in the `with ui.tabs(...) as tabs:` block (suggested between
   "Playoffs" and "Game"):
   ```python
   news_tab = ui.tab("News")
   ```
3. Add its panel in the `with ui.tab_panels(...)` block, in the same position:
   ```python
   with ui.tab_panel(news_tab).classes("p-0"):
       refresh_news = build_news_tab(on_open_summary=lambda gid: open_summary(gid))
   ```
   (`open_summary` is defined later in `build_page`; the lambda looks it up when
   clicked, the same as the Playoffs tab does.)
4. In `after_games(follow_week)`, add:
   ```python
   refresh_news()
   ```
   Optionally also call it in `change_team` and after roster moves, so the "Your team"
   view picks up moves made on the Roster tab right away (it already refreshes whenever
   the tab is rebuilt).

The storyline update (Oct 23) needs no more wiring: it adds two engine files that
`engine/news.py` uses on its own, and two story-type colors in `screens/news_page.py`.

Bitter (Oct 23): the page keeps the same `build_news_tab(on_open_summary=...)` entry point, so
the existing wiring still works. One change for `screens/main_page.py`: rename the tab label
from `ui.tab("News")` to `ui.tab("Bitter")` (Blake's name for it). New engine files:
`engine/bitter.py` (the accounts, their reactions, the timeline) and `engine/bitter_words.py`
(what they sound like).

Housekeeping for the same session (files I wasn't allowed to edit tonight):
- `CLAUDE.md` "Files": add `engine/news.py` (news and social posts, built from the
  league's records), `engine/storylines.py` (what's building over a season: streaks,
  form, races, injuries' fallout), `engine/news_words.py` (the phrase library and the
  Writer that spreads wording across a season), `engine/bitter.py` and
  `engine/bitter_words.py` (Bitter, the social media site), `screens/news_page.py` (the
  Bitter page), `tools/news_check.py`.
- `tools/README.md`: one line for `news_check.py`.
- `docs/build-log.md`: a Progress entry pointing to this file, with the PROVISIONAL list
  above for Blake.
