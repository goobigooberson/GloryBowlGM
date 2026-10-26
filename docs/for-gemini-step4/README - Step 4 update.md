# Front Office Football: update for Gemini before Step 4 (the game screen: scoreboard and pre-game)

Written by Claude (who puts your designs into the game) on Oct 26, 2026. This
updates the first package's `README - start here.md`. Read that first if you
no longer have it.

**In this package:**
- this brief
- `theme.py`, the current file (it has changed a lot since the first package)
- `game_page.py`, the file that draws the game screen
- `screenshots/`, the game screen today in every state (1600x900)
- `Game screen - all states.pdf`, the same screenshots with captions

## 1. What changed since you last saw the game

Steps 1-3 are in and checked on every screen:

- **Step 1:**
  - team colors for all 32 teams
  - the 58 px top bar with the team badge and uppercase section tabs
  - the docked white page strip with badges (Trades shows offers waiting, Contracts shows fifth-year options due)
- **Step 2:**
  - the white `.page-toolbar` with stat pills on Roster, Contracts and Staff
  - the Contracts cap ledger
  - Staff's "My staff | League coaching moves" switch
  - docked side panels with a header band (class `report inspector`)
- **Step 3:** the Home dashboard (team-colored card headers, a broadcast matchup card, the attention inbox, the leaders grid, streak boxes, the news wire).

A feature you haven't seen: **Take over play calling** (added Oct 25). It's a
checkbox next to the speed buttons. While it's ticked, the game stops on each of
your team's snaps, offense or defense, and shows a call menu:

- your coordinator's suggestion and a "Coach's call" button
- the plays (stars mark plays that fit your coordinator's scheme)
- a warning when the other side is "keying on" your calls

Unticking it hands play calling back to your staff. See screenshot 07.

## 2. How Claude merged your CSS, and what to keep in mind

These came up in Steps 1-3. Planning around them saves a round trip.

1. **Use the game's real class names.** Some of your rules targeted classes that mean something else here:
   - `.field-band` is the big header on the menu screens, not the top bar.
   - `.report` is on about 25 boxes across the game: the player card, draft notes, awards and pop-ups. A rule on `body .report` hits all of them.

   Section 5 lists this screen's real classes. For a new piece, name a new class
   and Claude will add it to the right element.
2. **Where CSS lives.** Your CSS goes into `theme.py` as its own plain-string block (`STEP2_CSS`, `STEP3_HOME_CSS`; Step 4 will be `STEP4_GAME_CSS`). Two page-level blocks in `game_page.py`, `TALE_CSS` (pre-game) and `CALL_CSS` (the play-call menu), load after the theme. When your rule clashes with one of those, Claude edits or removes the page rule, but tell us which you mean to replace.
3. **Team colors are CSS variables** (set for the team being viewed):
   - `--turf`: the team's primary color
   - `--turf-dark`: 18% darker
   - `--team-accent`: the second color
   - `--team-accent-ink`: readable text on the accent
   - `--team-link`: link color on the primary, readable at 4.5:1
   - `--flag`: penalty-flag yellow, which stays for selections and the main action

   White text on every primary is guaranteed readable (4.5:1 or better). An
   accent on its own primary is only guaranteed 3:1, so use it for edges,
   underlines and big text, not small text.
4. **Both teams' colors can be used on the game screen.** The page knows both teams. Claude can expose them as `--away-primary`, `--away-accent`, `--home-primary` and `--home-accent` (from `theme.team_colors(abbrev)`). Design with those names if you want each side of the scoreboard or field in its own team's colors.
5. **Tooltips in screenshots aren't page text.** A gray box over the page in a screenshot is a tooltip that showed because the mouse was over a button. Twice it was mistaken for a layout bug.
6. **What you can and can't do with the parts.**
   - Buttons are Quasar `q-btn`, view switches are `q-btn-toggle`, the checkbox is `q-checkbox`, and the side tabs are `q-tabs`.
   - You can restyle all of them freely. The text, labels and what they do stay the same unless Blake decides otherwise.
   - The game runs in a 1600x950 desktop window, and should still work at 1440 wide.

## 3. Rules that still apply

- **The screen only shows the game.** Every football decision is made by the engine. Design what we show, not how plays work.
- **Keep every control:** Pause/Resume, Next play, the four speeds (Slow, Normal, Fast, Very fast), Sim to the end, Take over play calling, and in the call menu Coach's call, the star for plays that fit the scheme, and the "keying on" warning.
- **Ratings appear as a word plus a number**, like "Good (66)". The pre-game ratings are your staff's view, not the true ratings. Hidden ratings never appear.
- **Label every button and column.** Away team on the left, home on the right, like a TV scoreboard.

## 4. The game screen today (Schedule › Watch a game)

**Before kickoff** (screenshot 01):
- a line with the week, the matchup and Watch this game
- the "tale of the tape": a dark header (away abbreviation and name on the left, home on the right, AT or VS in the middle), then rows of points per game, points allowed per game, last 5 (W/L boxes), offense starters, defense starters and starting QB
- the better side's number in each row in green

**During the game** (02-07, top to bottom):
1. **The scoreboard:** dark, not in team colors yet. Each team shows a possession ball, its abbreviation and name, its score and three timeout bars. The middle shows the quarter, the clock, down and distance with the yard line (in yellow), and the weather.
2. **The field strip:** an SVG 1200 x 80. End zones show the team abbreviations, with yard numbers, a blue line of scrimmage, a yellow first-down line, the ball, and an arrow for the direction.
3. **Controls:** Pause, Next play, Speed, Sim to the end, and the Take over play calling checkbox.
4. **The call menu** (only while you're calling plays).
5. **Two columns:**
   - Left: the play-by-play, NFL game-book style. Rows are grouped under drive headers; each row shows the time, the team, down and distance, and the play with a gray detail line (personnel, formation, coverage, who beat whom). Scoring plays are green, turnovers red and big plays yellow.
   - Right: side tabs. Team stats (line score plus team stats), the away box score, the home box score, the scoring summary, and drives.

**After the game** (08-09): the page clears to one line ("Final: Buffalo
Blizzard 9, Pittsburgh Ironmen 24") and a Game summary button that opens the
box score pop-up. **There's no postgame screen yet.**

**Data the screen can show (ask if you want more):**
- **Every snap:** score, quarter, clock, down, distance, yard line, possession, timeouts, weather, the play's text and detail line, drive starts, scoring plays, turnovers, big plays, injuries, and which plays were your calls.
- **The full box score**, line score, team stats and drives, all live.
- **Before kickoff:** both records, points for and against per game, last 5, starters' averages for offense and defense (staff-rated), and the starting QBs.
- **Available but not on screen yet:** each team's injury report (out, doubtful, questionable), key players by position, captains, the head coach and coordinators, playoff seeds, the site, preseason or Hall of Fame game status, and each side's season stat leaders.

## 5. This screen's current class names

- **Scoreboard:** `.scoreboard`, `.sb-team`, `.sb-abbrev`, `.sb-name`, `.sb-score`, `.sb-to`, `.to-dot` (`.used`), `.poss-ball` (`.off`), `.sb-mid`, `.sb-period`, `.sb-clock`, `.sb-situation`, `.sb-weather`
- **Field:** `.field-strip` (SVG), `.f-num`, `.f-ez`, `.f-arrow`
- **Play-by-play:** `.pbp-scroll`, `.pbp-row`, `.pbp-clock`, `.pbp-team`, `.pbp-dd`, `.pbp-text`, `.pbp-detail`, `.pbp-scoreline`, `.pbp-score`, `.pbp-turnover`, `.pbp-big`, `.pbp-drive`, `.pbp-note`, `.pbp-injury`, `.pbp-quarter`, `.pbp-final`, `.pbp-yourcall`
- **Side tabs and box score:** `.box-panels`, `.box-team`, `.box-title`, `.box-table`, `.line-score`, `.team-stats`
- **Pre-game:** `.tale`, `.tale-top`, `.tale-side` (`.r`, `.you`), `.tale-ab`, `.tale-nm`, `.tale-rec`, `.tale-mid`, `.tale-row`, `.edge`
- **Call menu:** `.call-panel`, `.call-head` (`.side`, `.side.def`), `.call-staff`, `.call-warn`, `.call-btn` (`.suggested`), `.call-legend`

## 6. What to send back

A `STEP4_GAME_CSS` block, plus a short description of each part's layout:

- which pieces move where
- any new pieces, such as a pregame matchup card or a postgame summary
- which existing page rules it replaces

Small HTML mockups are welcome. Claude turns them into the game's code and
checks every screen before Blake looks.
