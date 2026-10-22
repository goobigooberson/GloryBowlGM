# Making the game addictive, fun and never predetermined

Blake, Oct 22: "Do a very intense look into figuring out ways to make this game extremely
addicting, fun, and not pre determined. Anything that will improve the game." Research,
measurements and ideas, checked against what the game already has. Nothing here is built
yet; each idea is for Blake to pick, and its design calls are his.

## What the research says

- **The core pull of Football Manager is finding and growing unknown talent**: spotting a player
  "nobody's ever heard of" and building him up, more than signing stars (FM Projects). Its
  makers chose text over graphics so players imagine the game themselves (Game Developer).
- **Out of the Park Baseball's pull is the long dynasty with stakes**: careers you follow for
  decades, a GM who can be promoted or fired, and since OOTP 13 interactive storylines: a star
  goes to the media during a slump and you fine him, ignore him or cut him, with effects on
  morale, chemistry, fan interest and the owner (OOTP 13 previews). "You can do everything
  correctly and still lose."
- **FOF8's own pillars** (Blake's design reference): the player is judged on four things, not just
  wins: on-field results, roster building, finances, owner and fan satisfaction. Decisions over
  dexterity; stats are the reward; long careers; every layer can be delegated.
- **What fans hate** (Madden franchise criticism): staleness, shallow coaching (only the head
  coach matters), and scripted stories that limit what you can change. They want decisions
  with real effects and deeper roster and league management, not cinematics.
- **FOF and OOTP**: OOTP Developments brought FOF's creator Jim Gindin on in May 2018 to rebuild
  FOF on OOTP's interface, then shelved it in June 2020 (GM Games). This game is, in a sense,
  that cancelled collaboration's goal: FOF's depth with a modern interface.

## Measured today: is the league predetermined?

| Check | Game | Real NFL | Verdict |
|---|---|---|---|
| New playoff teams each year | 6.2 (startup league, 4 transitions); 5.7 (15-season save) | 5.85 since 1990, 6-7 since the 14-team field | Good |
| Distinct champions | 4 of 5 seasons; 11 of 15 | | Good |
| Last season's wins predicting this season's (correlation) | **0.16** (startup league, 5 seasons); 0.32 (15-season random-roster save, older code) | **0.33** (2002-2026), **0.37** (2012-2026), nflverse games | **Too random in startup leagues** |

The last row matters most for fun: if team quality doesn't carry over, building well doesn't
pay off, and results feel like dice. Real NFL teams are about twice as consistent as our
startup leagues. Likely causes to check (one at a time, measured): startup-draft rosters and
their contracts (every deal fresh and even), AI cap approaches (all in / rebuild swings),
development swings, injuries. **This should be fixed before anything else.**

## Ideas, by what makes it fun

Size: S = a day or less, M = a few days, L = a big system. Status: has / in progress / new.

### 1. Stakes: you're judged, and you can lose your job (FOF8 pillar, currently missing)
- **Owner with goals and patience** (new, M). Each owner has a personality (patient, win-now,
  frugal, meddling) and yearly goals (make the playoffs, develop the young QB, cut payroll,
  sell tickets). Progress shows on Home. Goals come from the team's real situation, not a script.
- **Job security and getting fired** (new, M). A hot seat that heats up with losing, missed
  goals and fan anger, cools with wins and good drafts. Fired = your save goes on: you get
  interviews with other teams (worse teams first, like real GMs), so the career continues.
  Real basis: NFL GM tenure and firing rates (measure from real GM changes, as the staff
  session did for head coaches: 6.6 HC changes a year).
- **Fans and finances** (new, L). Attendance, merchandise and fan mood from winning, stars and
  hope (a top pick QB sells tickets); revenue feeds the owner's budget (staff, later stadiums,
  already on Blake's "later" list). Keep it light: a few numbers that move for clear reasons.
- **GM report card each season** (new, S once the above exist). FOF8's four pillars graded with
  real comparisons: results, roster building (your draft and signings' value vs the league's),
  finances, owner and fans. A legacy score that adds up over a career.

### 2. "Find a gem" (FM's core loop)
- **Staff-estimated ratings and scouting fog** (in progress: coaching staff session).
  Unproven players read modestly until they prove it; a late-round pick who breaks out is yours.
- **Breakouts, late bloomers and busts at real rates** (has development; S to check). Measure
  how often real late-round picks and undrafted players become starters (nflverse draft picks,
  seasons_started by round; real undrafted starters 8-11%) and make sure the game produces
  the same surprises, both ways.
- **Hidden gems you can actually find** (new, S-M). Signals for a careful GM: a backup who
  played well in garbage time, a practice squad player with standout practice reports,
  college stats that don't match his draft grade (Blake's college stats idea). Information
  that rewards attention, never the truth handed out.
- **Position switches that unlock players** (Blake's college positions idea; out-of-position
  realism in progress): a college WR who could be a CB, a TE who could block at T.

### 3. A living league that tells its own stories
- **Interactive storylines, OOTP-style** (new, L). Events from the league's real state, each a
  decision with real effects: a star in a contract year wants an extension; a veteran
  benched for a rookie asks to be released; a player wants more touches after a big game;
  a rookie arrives out of shape; a locker-room fight after a losing streak; a holdout in camp.
  PG-13. Effects on morale, loyalty, performance (small and real), and Bitter's reactions.
  Rare enough to stay special.
- **Personalities that matter** (has the traits: loyalty, wants a winner, leadership, volatility;
  new uses, M). Leaders who steady young players, volatile players who press in big games
  (only where real data supports it: real "clutch" mostly isn't measurable, so keep effects
  tiny or skip), loyal players who give a hometown discount (has), mentors who speed up a
  rookie's development at their position (fits the staff system).
- **Rivalries** (new, S-M). Division rivals, teams that knocked you out of the playoffs, a former
  player who signed elsewhere, a coach who left you. Bitter and the news remember them;
  the game day preview shows the history.
- **AI GMs with personalities and memory** (new, M). Some trade often, some hoard picks, some
  overpay veterans, some never deal with a division rival. They remember a lopsided trade.
  Makes the league feel run by people, and resists exploits naturally.
- **League history** (new, M). Record book (single game, season, career, franchise), Hall of
  Fame voting for retired players (real voting rules: 5 years retired), all-time leaders,
  franchise pages with every season, retired numbers, a history of every Glory Bowl. Long
  saves (FOF8's 50 seasons) are where this pays off. Milestone chases on Home ("needs 312
  yards for the franchise record").

### 4. A decision every week (decisions over dexterity)
- **Inbox, FM-style** (new, M). One place each week: staff requests (has), contract talks,
  storyline decisions, injury choices (play a Questionable star in a big game or rest him:
  real injury-risk numbers), trade calls from AI teams, owner notes. A short list, so each
  week has something to decide without becoming a chore.
- **Weekly game plan** (new, M; the sim session's coaches work fits here). A few real levers:
  run/pass lean, aggressiveness on 4th down and 2-point tries (real analytics give the
  trade-offs), blitz rate, who to feature, protect a lead or keep attacking. Stays inside the
  calibrated sim (it already has coach tendencies to drive).
- **Playing time choices** (new, S-M). Give a rookie snaps to develop vs win now; rest starters
  late in a decided season.

### 5. The market (FOF8's exploits are here, so it has to be smart)
- **Trades** (new, L, the biggest missing piece). Players and picks, during the season (a real
  trade deadline) and offseason; AI valuations from contracts, age, need, their own staff's
  eyes, and pick value charts; no fixed position values (FOF8's exploit). AI teams also call
  you with offers.
- **Real contract drama** (some has; S-M each). Restricted free agent offer sheets (real rule),
  compensatory picks for lost free agents (real formula), holdouts, the franchise tag fights.

### 6. Feedback and rewards ("stats are the reward")
- **Records and milestones as they happen** (news has many; S). A banner when a record falls in
  your game.
- **Season recap** (S). One page at season's end: your season in numbers, best moments, report
  card, what's next.
- **Optional challenge starts** (new, S). Worst roster, cap hell, no first-round picks, a small
  market with a frugal owner. Replayability without changing the rules.

### What not to do
- No rubber-banding or scripted outcomes (Madden's scripted modes are a top complaint; Blake's
  "never pre-determined"). Every swing should come from a football reason the game can show.
- No fake drama: storylines must come from what really happened in the league.
- No stat caps to make things look right (CLAUDE.md sim rule).

## Recommended order

1. **Team persistence fix** (measured gap above; makes building matter). Check the causes one
   at a time against the real 0.33-0.37, and add the check to the realism tools so it stays
   right.
2. **Stakes: owner, hot seat, report card** (FOF8's own pillar; gives every season a purpose).
3. **Trades with AI GM personalities** (the biggest missing system; FOF8's exploits).
4. **Inbox with interactive storylines** (the weekly "one more week" pull; OOTP's best idea).
5. **League history: record book, Hall of Fame, milestone chases** (pays off long saves).

Then weekly game plans, fans and finances, and the gem signals (college stats).

## Sources
- [FM Projects: Why Football Manager is so addicting](https://fmprojects.substack.com/p/why-football-manager-is-so-addicting)
- [Game Developer: the ingredient that turned Football Manager into a massive hit](https://www.gamedeveloper.com/design/the-ingredient-that-turned-i-football-manager-i-into-a-massive-hit)
- [OSFTW: OOTP 13 new features (interactive storylines)](https://www.osftw.com/previews/146/out-of-the-park-baseball-13-new-features)
- [SI: interview with the creator of OOTP](https://www.si.com/extra-mustard/2014/08/08/interview-creator-out-park-baseball)
- [Giant Bomb: Out of the Park Baseball](https://giantbomb.com/wiki/Franchises/Out_of_the_Park_Baseball)
- [SportsGamersOnline: Madden franchise mode through the community's eyes](https://www.sportsgamersonline.com/featured/an-in-depth-look-at-madden-nfls-franchise-mode-failure/amp/)
- [PhillyVoice: how Madden can fix franchise mode](https://www.phillyvoice.com/madden-21-ea-sports-fix-franchise-mode-release-date-update-features-training-camps-scouting-team-relocation/amp)
- [GM Games: OOTP Developments and Solecismic Software part ways](https://gmgames.org/2020/06/11/ootp-developments-and-solecismic-software-part-ways/)
- [theScore: how many new playoff teams](https://thescore.com/news/3060635) and [Sharp Football Analysis](https://www.sharpfootballanalysis.com/betting/t-a-s-2019-nfl-season-predictions/)
- Real year-to-year wins correlation: nflverse schedules (`tools/data/nflverse/schedules/games.csv.gz`), computed Oct 22.
