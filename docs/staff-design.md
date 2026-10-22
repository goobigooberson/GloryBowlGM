# Coaching staff and staff-rated players: design (started Oct 24, 2026)

Status: **design agreed Oct 24** (Blake's answers in section 3); building in pieces
(section 9). Each choice marked PROVISIONAL is Claude's judgment call for Blake to review.

What Blake decided before this doc (Oct 24):
1. You are the GM and you hire the whole coaching staff; AI teams hire theirs.
2. Coaches develop players: a position coach's skill at his position changes how much of
   his ceiling a player reaches and whether the ceiling grows or shrinks. (Blake: in FOF8 a
   startup draft's best QB potential was sometimes only ~75, "which made it feel special when
   you got a 80+ one. but i think part of that was having to have a coaching staff that could
   really maximize that specific players potential by being specialized in their position".)
3. Every rating you see is your staff's evaluation, everywhere (your roster, other teams,
   free agents, prospects, the startup draft), shown as plain ratings, no "how your staff sees
   it" label (Blake: "i just want their ratings to be whatever the staff evaluates it to be").
   Your own players are judged closely; everyone else less so; better staff = closer to the
   truth. True ratings stay inside the engine. Stats and game results never change.
4. Coaches replace the random coordinator styles in the game sim and should bench players
   who play badly (Blake: benching is a later piece of its own).

---------------------------------------------------------------------------------------

## 1. What real NFL staffs look like (research)

**Size.** Real staffs run about 22-29 coaches in 2024 (Vikings 27, Cowboys 28, Patriots 29,
Browns 28 under Monken), counting quality-control assistants. The core every team has:
head coach; offensive, defensive and special teams coordinators; position coaches for
QB, RB, WR, TE, OL, DL, LB and DB (most split DB into CB and S, and add assistant OL/DL
coaches); a head strength and conditioning coach. Many add a passing or run game
coordinator, an assistant head coach and 3-6 quality-control coaches (young assistants who
break down film). Separately the front office has the GM (you), a director of college
scouting with ~10-15 area scouts, a director of pro personnel (other teams' players and
free agents), and the medical staff (head athletic trainer, team doctors).

**Head coach turnover (measured from nflverse's game files, 1999-2026, the coach of each
team in each game):**
- Teams with a new head coach at the start of a season: **6.6 a year** (spread 1.8;
  fewest 3 in 2005 and 2010, most 10 in 2006 and 2022). Recent: 2023 5, 2024 7, 2025 7,
  2026 7.
- In-season changes (an interim coach takes over): **1.5 a year**.
- Completed tenures: average **4.1 seasons, median 3**; 1 season 15%, 2 seasons 20%,
  3 seasons 22%, 4 seasons 17%, 5-9 seasons 22%, 10+ about 4% (Belichick, Reid, Tomlin,
  Carroll, Payton, McCarthy...).
- About 30% of new head coaches have been a head coach before ("retreads"); the rest are
  first-timers, mostly coordinators.
- What gets a coach changed after a season (includes retirements and resignations):

  | Wins (per 17 games) | Coach's 1st-2nd season | 3rd season or later | All |
  |---|---|---|---|
  | 0-4 | 35% | 71% | 49% |
  | 5-6 | 17% | 45% | 30% |
  | 7-8 | 2% | 21% | 12% |
  | 9-10 | 15% | 15% | 15% (retirements, resignations, the odd firing) |
  | 11+ | 1% | 5% | 4% |

  Playoff teams change coaches 4% of the time, non-playoff teams 27%. New coaches get
  time (a 0-4 season in year 1-2 costs the job about a third of the time; later, 7 in 10).

**Coordinators** turn over much faster: by reporters' counts about half the league changes
at least one coordinator each year (for 2026, 21 of 32 teams have a new offensive
coordinator and 14 a new defensive coordinator, much of it new head coaches bringing their
own staffs). Coordinators who succeed leave for head coaching jobs (Detroit lost both
coordinators to head jobs in one offseason; Tampa Bay lost its offensive coordinator two
years running). Sources: Pro Football Rumors' coordinator tracker, CBS Sports, AP.

**How hiring works for real (Claude's summary, well documented):** firings come the day
after the regular season ("Black Monday") or as soon as a team is eliminated; head coach
interviews run through January (a coordinator on a playoff team can't have an in-person
second interview until his team is out); a team can't block its assistant from
interviewing for a head coaching job, but can block a lateral move (coordinator to
coordinator) while he's under contract; the Rooney Rule requires diverse interviews; a new
head coach hires most of his staff, usually within weeks; the market for assistants runs
through February. Contracts: head coaches usually 4-6 years (5 is common), coordinators 2-3,
position coaches 1-3. A fired coach is owed the rest of his contract (reduced by what he
earns at his next job). **Coaches' pay doesn't count against the salary cap.**

**Pay** (rough: coaches' contracts aren't published; these are reported ranges): head coaches
about $5-12M a year, the best paid $15-20M (Sean Payton ~$18M); coordinators $1-3M, the
best $4M+; position coaches $0.3-1M (QB coaches toward $1M); quality control $0.1-0.25M.

**Do coaches make players better? (measured, real data).** This is where the real NFL is
humbling, and Blake should know it when choosing how strong coaching is (his answer is in section 3):
- *Quarterbacks under different head coaches* (nflverse 1999-2025, 658 cases of a QB with
  200+ dropbacks in two straight seasons): after allowing for the usual pull toward average
  and for changing teams, the head coach in the second season explains **none of the
  measurable year-to-year change** in EPA per dropback. The data can rule out an effect
  bigger than about 0.025 EPA per dropback per season for one spread of coach quality
  (about a fifth of the gap between an average and a good starting QB season).
- *Drafted players under the same head coach for their first three seasons* (2000-2018
  drafts, 4,841 players, value earned for the drafting team versus what that draft slot
  usually earns): the coach-to-coach spread is about **1 point of career value** (players
  average 12, spread 15.4) and can't be told apart from luck; at most about 2 points
  (about 15% of an average pick's value) for one spread of coach quality. This mixes
  drafting and development, so the coaching part alone is smaller still.
- *Published research:* Pitts and Evans (2018, Managerial and Decision Economics) found
  that offensive coordinators' characteristics (age, experience, playing career) barely
  matter for QB performance, but **individual coordinators do**: the elite and the poor
  ones measurably change their QBs' production. No study I found isolates position
  coaches (no public data on who coached each position room).
- Reading: in the real NFL, great coaches matter, but for development the effect is
  modest and the noise is huge. A great QB coach helps; he doesn't turn a 70 into a 90.
  Head coaches are a proxy here; position coaches may matter more than these numbers show,
  and real teams clearly believe they do (they pay QB coaches the most).

## 2. How FOF8 did staff (design reference; Blake's priorities override)

From the design reference (verified from FOF8's manual unless marked):
- Staff was added in FOF7: "hiring coaches and scouts who affect development and
  evaluation". Each staff member has a **scouting rating**, which sets how accurate your
  scouting reports are (prospect ranges narrow with better scouts).
- "Coaches develop players, with a boost when the head or assistant coach specializes in
  the player's position group. The strength coordinator speeds injury recovery and helps
  prevent injuries."
- Staff retention: each coach's salary and years left; only staff with one year left can be
  extended. Then the **staff draft**: 5 rounds, one per staff job, from a long list of
  coaches with a specialty, a style ("West Coast", "43 Over") and a rating; order by profit
  rank. **Blake dislikes the staff draft** and wants hiring done another way.
- Profits cap the bonus money you can offer players and staff.
- [Unverified, from memory, Blake to correct] FOF8's five jobs were head coach, offensive
  coordinator, defensive coordinator, assistant coach and strength coordinator, with ratings
  along the lines of player development, motivation, discipline, scouting and play-calling
  style.

## 3. Blake's answers (Oct 24)

1. **Jobs: FOF8-sized, 5 coaches** (head coach, offensive coordinator, defensive
   coordinator, assistant head coach, strength and conditioning coach). Position specialty
   comes from each coach's background (the position group he coached), so which rooms your
   staff covers is a real trade-off.
2. **Front office and support: all three** (director of college scouting, director of pro
   personnel, head athletic trainer). So 8 jobs in all.
3. **Money: an owner's staff budget** (some owners spend, some are cheap); candidates weigh
   money, the job's level, your team's outlook and their ties to your head coach.
4. **Development effect: in between, ~+4-5** points of potential for a young player with a
   top-3 staff at his position over 4 years, versus an average staff (the real data's upper
   bound is ~+3; Blake chose a little more).
5. **Coach ratings: reputation + track record.** True skill is hidden; you see a reputation
   (which can be off, and sharpens with a longer record) and his record (teams, results,
   how players developed under him).
6. **AI teams judge players through their own staff's eyes** (their mistakes decide their
   signings, cuts and depth charts).
7. **In games: style only** (same spreads as today's random styles). **Benching struggling
   players: later, its own piece.**
8. **Hiring: a carousel in rounds** right after the season; you make offers, candidates
   choose; other teams can poach your coordinators for head jobs. **You can fire any coach
   during the season** (an interim fills in until the carousel).
9. **Startup pools: "Leave it honest"** (Blake, Oct 24, via the main session). A staff's
   number is its best estimate, pulled toward average in proportion to its uncertainty, so
   proven veterans read about what they've shown: an average staff's best QB ceiling in a
   startup pool shows 87-93 (the truth 88-97), while draft classes' best QB ceilings show
   ~70-75 (one class 88). The FOF8 mystery stays on prospects, young players and free agents;
   other teams' established players are not judged less surely to make 80+ rarer.

## 4. The staff (PROVISIONAL details)

| Job | What he does |
|---|---|
| Head coach | Develops everyone a little and his background group a lot; reads players (all groups a little); 4th-down aggression and game style. |
| Offensive coordinator | Develops the offense a little and his background group a lot; reads offensive players; offensive style (pass/run lean, tempo, personnel, RB committee or bell cow, who the passing game features). |
| Defensive coordinator | Same for the defense; defensive style (man/zone, blitz rate, rolling coverage to a star). |
| Assistant head coach | Develops his background group a lot (any group, including special teams: K/P/LS); reads that group. The flexible hire: cover the room your other coaches don't. |
| Strength and conditioning | Fewer injuries (small, centered on today's real injury rates); helps physical skills develop a little. |
| Director of college scouting | Draft prospects: how close your grades start (takes the place of today's hidden front-office scouting skill). |
| Director of pro personnel | Other teams' players and free agents: how close your read is. |
| Head athletic trainer | Faster recovery from injuries (small, centered on today's real recovery times). |

Background groups: QB, RB (and FB), WR, TE, OL, DL, LB, DB, ST (K, P, LS, returners).
Offensive coordinators come from QB/RB/WR/TE/OL rooms, defensive coordinators from
DL/LB/DB, head coaches from either side (about 55% offense, as in the real NFL's recent
hires; PROVISIONAL) or rarely special teams.

**Every coach is a person with a career:** age, background, true ratings (hidden),
reputation (shown), style, contract (years and salary), his record (job by job, team
results, how his players developed), mentor (his coaching tree), ambition (wants a
promotion) and loyalty. Coaches improve with experience into their 50s, slow down later,
retire (mostly 60-72), climb the ladder and get fired. New coaches come in each year from
outside the modeled jobs (position coaches and college coaches), less proven.

**Reputation** (what you see): starts as a rough read of his true skill (off by about 10
points for a newcomer) and moves toward what his record shows each season (players
developing above or below expectation under him; drafts that hit or miss; his teams'
injury luck), so a coach with a long record is known fairly well, while one great or awful
year can fool everyone a little. Shown FOF8-style as word-plus-number.

**Money** (PROVISIONAL, coaches' real pay isn't published; from reported ranges): head
coaches about $4-20M a year (typical ~$8M), coordinators $1-4.5M, assistant head coach
$0.7-2M, strength coach $0.3-0.9M, the two scouting directors $0.3-0.8M, head trainer
$0.2-0.5M. Each owner's yearly budget for the 8 jobs is about $15M on average, from about
$11M (frugal) to $21M (big spender), growing with the salary cap. Outside the player cap.
A fired coach is still paid the rest of his contract, and that counts against the budget
(real NFL: owners pay fired coaches; less what he earns at his next job).

## 5. Development, in detail (PROVISIONAL)

`engine/development.py` today, per player per camp: a long-term step (lean by career stage
+ heavy-tailed dice), a fading season swing, aging, injuries, then current ratings close a
share of the gap to potential. Coaching adds a **coaching score** for each player, from:
- the **specialist**: the best of his staff's coaches whose background is his group
  (head coach, coordinators, assistant head coach), weighted most;
- his side's **coordinator** and the **head coach**, a little each (general teaching);
- for physical skills, the **strength coach**, a little.

The score is measured against the league's average staff each season (like the sim
measures players against the league's average starter) and turned into spreads, so a
league of average staffs develops exactly as today. Three effects, each scaled by career
stage (strongest before his peak, small for veterans):
1. Ceiling lean: up for good coaching, down for bad, every year.
2. Reaching the ceiling: growth toward potential a bit faster or slower.
3. Softer (or harder) falls: the downside of the yearly dice is softened by good coaching
   and sharpened by bad (Blake's "makes collapses less likely").

Size (Blake: in between): about **+4 to +5 points of potential** after 4 years for a young
player whose staff is about the league's best 2-3 at his group, and about the same down for
the worst. Checked over 22 seasons with `tools/draft_check.py` before and after (league
level, Blake's 88-90% moving 0-3 points a year, stars 80+/90+), plus sample careers.

## 6. Every rating is a staff's evaluation (PROVISIONAL)

- One place decides what a team sees: `engine/evaluation.py` gives, for a viewing team and
  a player, his skills (now and ceiling) as that staff sees them; `scale.shown` turns them
  into screen numbers as today. Every screen asks for the user's staff's view. Hidden
  ratings stay hidden.
- How far off (internal points, one spread; truth inside about 2 times in 3):
  - **Your own players:** about 1.5 for an average staff (best ~0.75, worst ~2.5): your
    coaches see them every day; the coach whose background is his group counts most. A new
    arrival starts at the "other team" level and narrows over his first weeks with you.
  - **Other teams' players and free agents:** by how much tape there is (his share of his
    team's snaps over his last two seasons): about 8 for a player who barely played, 5 for a
    part-timer (45%), 3 for a full-time starter (80%+); other teams' rookies 4.9 (Oct 22,
    sized to real data; was a flat 3.5). Better or worse pro personnel directors scale it
    (best about half, worst about 1.6 times). Part of it is shared across the league
    (everyone overrates the same player a little).
  - **Draft prospects:** the draft's existing model (`scouting.py`), with the college
    scouting director's skill taking the place of the hidden front-office skill.
  - **The startup draft:** veterans at the "other team" level from the pro personnel
    director, rookies at the prospect level from the college director.
  - Potential is a projection, so its mistake is about 1.5 times bigger than current ability's.
- **Mistakes don't flicker:** each is a fixed draw for that staff and player, narrowed as
  the staff learns and redrawn only when the evaluator changes (a new pro personnel
  director sees the league with fresh eyes).
- **Staged reveals** (decided Oct 19): the change happens at camp; your staff sees about a
  third of it after camp, most of it by the end of the preseason, the rest during the
  season. Other teams' players: slower (a third by the end of the preseason, all of it by
  the end of the season).
- **Stats never change.** The sim uses true ratings; production can tell you your staff is
  wrong, like a real GM (and FOF8).
- **AI teams use their own staff's view** (Blake) for their roster decisions: free agency,
  re-signing, cuts, depth charts, the startup draft. Your staff's suggestions (its depth
  chart, "would cut" tags, draft picks) use your staff's view.
  - Built (Oct 24): depth charts (`League.auto_depth_chart`), cuts (`offseason.keep_value`,
    `free_agency.cut_down`), in-season moves (`transactions.value` / `camp_value` with the
    team: waivers, practice squads, injury cover, upgrades, elevations), draft scouting skill
    (`draft.team_skill` = the college scouting director). Free agency bids keep the market's
    price (the league's consensus) and move it by the team's **misjudgment**
    (`evaluation.misjudgment`: its view minus what an equally unsure staff would see with no
    mistake), x e^(0.04 per point), 0.80-1.25. A first version compared the team's view
    with the league's public view directly; views of different sureness are pulled toward
    average by different amounts, so teams overpaid their own stars and 3 AI teams ended
    over the cap at week 1 in `free_agency_check` (101,102,103 x 4); with misjudgment, 0.
  - Built (Oct 22, AI-eyes session): free agency's roles and upgrade size ("is he better than
    our starter, by how much": `free_agency.team_score`, the league's market score moved by
    the team's misjudgment, now and ceiling, for the free agent and its own players alike),
    fifth-year option / extension / re-sign role checks, `set_approaches` (its window from
    its own view of its roster), `draft.team_needs` / `qb_situation` / `sign_undrafted`'s
    weakest player, game-day actives' tiebreak and the emergency QB (`roster_rules`, rating
    from `gameteam`). The tape behind the other-team mistake is each season's snap shares
    (`evaluation.record_tape`, at the end of the season; a league with none on record reads
    it from the depth charts).
  - Still on true ratings or its own model: `cap_market` (the price, deliberately the
    consensus), the startup room's AI boards (`draft.StartupRoom`, its own scouting model;
    your screen's numbers there come from `evaluation.py`), cap cuts' "worth" (the price).

## 7. The coaching carousel (PROVISIONAL)

- **When:** the first offseason phase, "Coaching changes", right after the Glory Bowl
  (real: Black Monday into February), before re-signing and free agency.
- **Firings:** AI teams change head coaches by the real table in section 1 (wins, his
  tenure, playoffs; about 6.6 a year, plus about 1.5 in-season). New head coaches usually
  replace the coordinators; coordinators also leave when promoted, when their unit is bad,
  or retire (target: about a third of coordinators change a year). You decide yours (and
  you can fire anyone mid-season; an interim fills in).
- **Rounds** (Next button between them, like free agency): (1) head coaches, (2) offensive
  and defensive coordinators and assistant head coaches, (3) strength coaches, scouting
  directors, trainers. In each round you make offers to candidates; then everyone's offers
  are settled: each candidate takes the best for him (salary against his market value, the
  job's level, your team's outlook, staff stability, ties to your head coach or his mentor,
  loyalty to his current team). Unfilled jobs carry to a second pass in the same round.
  Any of your jobs still empty at the end are filled by your staff's default pick.
- **Candidates:** coaches out of work, other teams' coaches one level down (their teams
  can't block a promotion: real rule), and new coaches from outside (position coaches and
  college coaches, generated). Lateral moves of coaches under contract don't happen.
- **Poaching:** your coordinators and assistant can be hired away as head coaches.
- **Your staff page** (Team section, "Staff"): your 8 jobs (name, age, background,
  reputation ratings, style, contract, salary), owner's budget used / left, the selected
  coach's record in a side panel, Fire / Extend; the carousel's candidate list as a pop-up.
  Every column labeled.

## 8. Coaches in the game sim (PROVISIONAL)

`engine/sim/gameteam._build_tendencies` takes its style draws from the team's coaches
instead of a random draw by season and team: the offensive coordinator's (pass/run lean,
tempo, personnel, RB usage, passing-game roles), the defensive coordinator's (man/zone,
blitz, rolling coverage) and the head coach's (4th-down aggression). Each coach's style
numbers are drawn once, from exactly today's spreads, so league stats can't drift; the
difference is that a team keeps its identity while the coordinator stays, and the style
moves with him. Checked with `tools/realism_check.py` (and the team sport test) before and
after.

## 9. Build order (each piece testable; nothing committed)

1. `engine/staff.py`: coaches, staffs for every team (new and older saves), saving, careers,
   AI firing and hiring, the carousel engine; checked against the real turnover numbers.
2. Development wired in; `tools/draft_check.py` before/after (22 seasons); sample careers.
3. `engine/evaluation.py`; screens switched to it (coordinated with the sessions that own
   them); AI decisions switched to their staff's view; `tools/free_agency_check.py`.
4. The Staff page and carousel screens; in-season firing; tested in the app.
5. Coordinator styles in the sim; realism check.
6. Strength coach and trainer effects on injuries (centered); realism check.
