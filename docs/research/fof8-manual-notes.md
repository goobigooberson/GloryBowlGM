# FOF8 manual notes: how its systems work, what to learn from them

Written overnight Oct 23, 2026 by a side session for Blake, from Front Office Football 8's
own help files on disk (`frfoot8.chm`, `DraftFile.chm`, `PlayerFile.chm`, the `datafile`
text lists). Nothing was launched or clicked. Everything is paraphrased; nothing is copied.

How to read the labels:
- **Manual:** what FOF8's manual says, with its numbers.
- **My judgment:** my opinion, measured against "Blake's priorities" in
  `FOF8 Design Reference for AI Context.pdf` (keep the season/offseason loop, realistic
  but varied stats, strong balance; fix exploits, the staff draft and dumb AI roster moves;
  avoid janky visuals and odd number formats).
- The manual is a help file, not a design document. It says *what* each screen does and
  often gives rules and numbers, but it rarely explains the formulas under the hood. Where
  it is silent, I say so rather than guess.

---

## Top 10 takeaways

1. **The manual explains Blake's exploits.** FOF8's AI drafts and trades by a *fixed value
   per position* (the manual's own table puts TEs among the least valued) and judges trades
   by "team strength before vs after" using one league scouting view. That's why elite TEs
   fell late and some positions were easy to pry loose by trade. The cure is to value the
   *player* (surplus over replacement, contract, age, team timeline), which Blake's game is
   partly doing already with staff-eyes AI and real-contract position values.
2. **Player trades are the biggest missing system**, and the place where FOF8's lessons
   matter most. Build them on surplus value, add AI-initiated offers and "shop a player,"
   and keep FOF8's "GMs stop listening if you insult them."
3. **Free agency's "best perceived offer" in stages** is what made FOF8 feel alive, but
   pre-decided signing stages are a likely source of the cheap-star exploit. Add a
   "fair price" check to `tools/free_agency_check.py`.
4. **The X-factor is FOF8's anti-memorization rule:** each new career re-rolls ratings
   (up to 50% for unproven players, 10% for proven ones). Blake's planned real-NFL rosters
   will need the same idea.
5. **FOF8's staff draft is as odd as Blake felt:** order by last year's profit, salary by
   draft slot, no candidate choice. Blake's carousel already fixes it. Still worth taking
   from FOF8's staff: head coach *motivation* and *discipline* (penalties), a separate
   *interviewing* rating, and the DC's front tied to the man you hire.
6. **Head coach game settings** (4th-down aggression, FG range, clock rules, play-hurt
   threshold, QB patience, CB shadowing) are a cheap, real layer between "no control" and
   FOF8's full scripted playbook.
7. **Continuity and the locker room:** unit cohesion (groups that stay together play and
   learn better), mentors, and playing-time attitude make "keep the old lineman or not" a
   real choice. Small effects, good stories.
8. **History is FOF8's reward loop:** record books (7 kinds), a Hall of Fame (5-year wait,
   80% vote), QB Coterie, playoff odds, point spreads, Create History. Blake's game has
   stats and awards but none of these yet.
9. **FOF8 grades you mostly on money** (over half the grade is franchise and stadium
   value). If Blake adds owners and stadiums, keep money as something that feeds football,
   not the score.
10. **FOF8's sim philosophy matches Blake's:** real play-by-play averages *and spreads*,
    weight vs ideal weight per play, offense position-locked and defense flexible,
    technique that doesn't age while strength does, and opponents who adapt to anything
    overused. Blake's game already calibrates more broadly; "skills age differently" and
    "anti-repetition" are the two ideas worth borrowing.

---

## Part 1 and 2: FOF8's systems, and how well they work

### 1. The year's calendar (the loop Blake loves)

**Manual:** the year runs in fixed stages, each with its own buttons:

| Stage | Length | What happens |
|---|---|---|
| Staff retention | 1 stage | extend coaches with 1 year left; propose a stadium project; change teams |
| Staff draft | 5 rounds | hire head coach, OC, DC, assistant, strength coach |
| Pre-free agency | 1 stage | set ticket prices; franchise designations happen before this |
| Free agency | 12 stages | main free agency; draft pool is visible; 12 interviews |
| Pre-draft | 1 stage | set draft preferences |
| Amateur draft | 7 rounds | |
| Late free agency | 5 stages | leftovers, undrafted |
| Training camp | 1 stage | build the playbook; weight training happens just before |
| Preseason | 5 weeks | |
| Regular season | 17 weeks | (my inference: 16 games and a bye, the 2016 NFL) |
| Playoffs | 4 weeks | |
| End season | 1 stage | retirements, awards, aging |

A league-wide Email window carries time-limited messages (trade offers from AI GMs, the
yearly cap/minimum salary announcement, stadium vote results, suspensions). Email is not
archived: move to the next stage and it's gone.

**My judgment:** this is the "satisfying loop" in its purest form: every stage has one job
and one button, so the offseason feels like a sequence of decisions rather than a menu.
Blake's game already follows the same shape (phases with a Next button). Two things worth
noticing: (1) FOF8 puts staff hiring *first*, so you know your coaches (and their
scheme/front) before you shop and draft; (2) scouting interviews happen during free agency,
so the two compete for your attention. The disappearing Email is a nice pressure device
but a bad archive: Blake's news/Bitter hub keeps history, which is better.

### 2. League setup and the startup draft

**Manual:**
- Three ways to start: **Complete Draft** (you pick, 53 rounds, snake order, random order
  for round 1, a speed selector, "Have Scout Finish Draft" button), **Preference Draft**
  (you fill in a preference sheet and 53 rounds are picked for you), or **No Draft** (start
  with the player file's rosters).
- The Preference Draft sheet: position-group emphasis sliders (balanced against how an
  average team values positions, so "kicker 55, QB 50" won't take a kicker before a top QB),
  plus trait sliders: Reserves vs Starters (depth vs a strong top line), Potential vs
  Experience, Loyalty, Run vs Pass defense, Run vs Pass blocking, Fan popularity.
- **The X-factor:** each new career re-rolls the core ratings of the player file. A player
  with lots of pro starts (X-factor 100, about a third of the league) varies by up to 10%;
  a player with no pro record varies by up to 50%. So the same file plays out differently
  each time, and you can't "know" who the steals are.
- Options at new game: team chemistry on/off; GM firing on/off (finances count as much
  as wins); a "level economic playing field" (same economies, identical stadiums); track a
  ratings history; a reduced X-factor for files with real ratings.
- No weight training in the first camp.

**My judgment:** works well. The X-factor is the key idea: it stops memorized "known
steals" (the manual itself names the exploit of trading for an undervalued star every new
game). Blake's legacy-rosters plan (real NFL seasons with estimated ratings) will need an
X-factor-style re-roll for exactly this reason. The Preference Draft is a nice
"I don't want to draft 53 rounds" option that's more personal than "auto-draft".

### 3. Roster limits

**Manual:**
- 60 players until the end of the preseason; 53 in the regular season.
- 46 active on game day (inactives don't count); a long snapper is required on the actives
  even though it isn't a primary position.
- Each position has a minimum active count (Position Distribution screen; red if short).
- Injured reserve is for the season: once placed, a player can't come back until next year.
- Suspended players don't count against the 46.
- "Out" players can't be made active.
- Restricted/unsigned players: with too little service to be a free agent, you keep the
  rights; if still unsigned at training camp he becomes a free agent.

**My judgment:** this is the 2016 NFL, simplified (no practice squad, no IR-return, no
waivers in the manual). Blake's game is already past it: real 90-man camps, one cut to
53, practice squads, IR/PUP with returns, waivers, 48 actives plus the emergency third QB.
Nothing to take here except the "required long snapper" idea, which Blake's game already
has in its roster rules.

### 4. Contracts and the salary cap

**Manual:**
- Contracts are never guaranteed, so players value **bonus** money far above salary, and
  value salary beyond year 1 much less.
- Cap hit each year = salary + (bonus / contract length). Release or trade a player and
  the bonus left becomes "lost cap room" (dead money): this year's leftover counts this
  year, the rest next year. A team acquiring a player by trade takes none of his bonus.
- **The cap counts only your 51 most expensive players** plus lost cap room (so camp
  bodies are free).
- **Veteran minimum rule:** a player with 4+ years at his experience minimum, with a tiny
  bonus (about 0.039% of the cap a year), counts only as a 3rd-year minimum.
- Not a hard cap: you can start a year over it if old contracts push you there, but you
  **lose draft picks** and can't sign or trade until you're under. AI teams may sit over
  the cap for a few seasons early in a career.
- **Cap Out:** for a player with 2+ years left, turn this year's salary into bonus (salary
  drops to the minimum), spreading the cap hit. Allowed even in season (renegotiations are
  not).
- Offers: you can't go below the minimum in any year or above $300M; the player shows his
  request (most accept a bit less unless their attitude toward you is bad); confirm or
  your reneging hurts his attitude; lowball far below and his attitude drops too.
- Releasing injured players: only in their last contract year, with a settlement fee on
  next year's cap. Injured players signed past this year can't be released.
- Cap increases come with new TV contracts; the commissioner sets the range (0 to $9.9M).
- Agents: rated for charisma (how many clients they get); an agent who already represents
  several of your players makes signing his other clients easier; a stubborn agent's
  clients hold out more.

**My judgment:** the bones are right (bonus proration, dead money, minimum-salary rule),
and the 51-man cap is a neat simplification. Weaknesses against Blake's "perfect and
real" bar: no guaranteed money, no void years, no rookie wage scale in the manual,
a very small TV-deal-only cap growth. Blake's game already goes further (real rookie
scale, fifth-year options, June 1 cuts, restructures, RFA tenders, cap eras with labor
deals and shocks). **Worth taking:** the agent relationship (an agent who represents
several of your players gives a small edge) is a cheap, flavorful layer Blake's game
doesn't have. The over-the-cap penalty (losing picks) is softer than the real NFL's
"you must be compliant" rule; I'd keep Blake's real rule.

### 5. Free agency

**Manual:**
- 12 stages of main free agency, then 5 stages of late free agency after the draft.
- Stage 1: only renegotiations with your own players and your own restricted free agents
  (4 or fewer years of experience).
- In each stage, players with offers consider the one they **perceive** as best (not
  necessarily the highest). Many of the best free agents decide **in advance** which stage
  they'll sign in, and usually stick to it; lesser players wait until later. Players
  usually sign oldest to youngest within a stage.
- You see each player's offers so far, and can wait for the market to set a price or bid
  early to beat a quick signing.
- Offer options: "withdraw my other offers at this position if he signs" and "withdraw
  all my other offers if he signs" (since you can't control signing order within a stage).
- Statuses: Signed, Pending, Withdrew, Over Cap (every bidder had to pull out).
- What players weigh (from the player screen): **loyalty** (staying with his team),
  **wants a winner** (playoff chances), **attitude toward your team** (built by how you've
  negotiated and how ruthlessly you've cut veterans), **playing-time happiness**, the
  **agent** link, and **distance from his home town** ("important to some free agents").
- Your profits cap the bonus money you can offer.
- Staff can auto-sign depth for you (never major free agents).
- The "Grey Sheet" ranks the top 88 free agents and shows where they signed and for what.

**My judgment:** the stage system and "best perceived offer" are what made FOF8 free
agency feel alive. But this is exactly where Blake's exploit lives: **good free agents
signing for very little.** The manual hints at why: players who pre-decide a stage
sign with whatever is on the table then, and AI teams bid from scouting reports, so a
player whose ratings are under-scouted (or whose stage arrives after AI teams spent their
room) can fall through. My judgment: the fix is (a) AI teams bid on *performance as well as
scouting*, (b) a player's asking price never collapses below what his last season says he's
worth while teams still have room, and (c) AI teams keep some room for late bargains.
Blake's game already uses waves, staff-eyes judging and real cap-room data; it should
add a check that "good recent stats + good ratings" players don't sign under a floor
(the tool `tools/free_agency_check.py` is the natural place).

### 6. Re-signing and the franchise tag

**Manual:**
- One franchise player a team a year; only for an unrestricted free agent; set after the
  season and before free agency. If he isn't signed by camp, he gets a one-year deal at the
  higher of **the average of the top 5 salaries at his position** or **120% of last
  year's salary**.
- For DL and LB, the tag's position is where "the majority of the league's staffs" think
  he belongs (his "Identifies As"), not where he plays.
- Renegotiations happen before free agency (stage 1 is reserved for them) and are mostly
  about lowering cap value for a bonus. No renegotiation in season (except Cap Out).
- Playing-time attitude: an unhappy player (not starting) may refuse to re-sign until he
  starts. Loyalty makes re-signing easier.
- Coaches/coordinators can only be extended with one year left, in the staff stage.

**My judgment:** simple and works. The "Identifies As" rule for DL/LB tags is a real NFL
fight (edge vs linebacker tags) and a nice touch. Blake's game already has the tag and
RFA tenders; the playing-time attitude is worth taking (see section 9).

### 7. The draft and scouting

**Manual:**
- 7 rounds, reverse standings; ties broken by reverse strength of schedule; playoff teams
  below non-playoff teams with the same record; Bowl runner-up picks 31st, winner last.
  Teams with the same record **rotate** their order round to round.
- Over-the-cap teams forfeit picks.
- Picks (this year's and next year's) can be traded, including during the draft.
- The draft pool appears when free agency starts (view-only until the draft).
- **League scouting pool grades:** a "Grade" from 1.0 to 9.9 (raw ability, from skills and
  the combine) and an "Adjusted Grade" (by position, for draft slot).
- **"Fit" position:** splits OT into left/right, and DL/LB into eleven scheme spots (3-4
  DE, 3-4 NT, 4-3 DE, 1-tech DT, 3-tech DT, 3-4 SLB/ILB/WLB, 4-3 SLB/MLB/OLB).
- **Combine:** 40, bench (weight varies by position), agility/cone, a Solecismic
  intelligence test, broad jump, and position drills. The manual lists exactly which
  ratings each test reflects for each position (for example: the bench press reflects a
  QB's long/deep arm, a WR's courage over the middle and a DB's bump-and-run; the broad
  jump reflects a WR/DB's return ability and a lineman's endurance). Comparisons are only
  valid **within** a position. "Developed" (how finished he is) is called "very important,
  more developed = much safer."
- Combine accuracy is a league setting (0-100; 50 already "quite accurate").
- **Interviews:** 12 per year, during early free agency. An interview reveals personality
  details and the staff's impression (**underrated / overrated** vs the report), and the
  player's potential range turns orange. The **head coach** drives the overall impression;
  the other coaches the skill details.
- Rookies' scouting bars show only a range of potential (blue; narrower with better
  scouts; orange if interviewed). Veterans show current (red) and future (green).
- Real data the manual quotes (2013 study): QBs go top-3 14.7x more than their share,
  first round 28.4x; level of play per pick correlates 0.40 for QBs vs 0.66 for tackles,
  0.64 ILB, 0.57 TE/HB/OLB/S. Kickers, centers, guards and TEs were valued least.
- Draft grades: analysts grade each team's draft right after it ("Post-Draft Analysis").
- "Green Page": the league's best young players.

**My judgment:** what works: ranges instead of numbers for rookies, interviews that
shrink uncertainty, the "developed" rating, and the scheme-specific Fit. What doesn't:
**the TE exploit** comes straight from the AI's position values. The manual's own table
puts TEs among the least-valued positions (0 top-3 picks, 6.7 first-round rate), and AI
teams draft by those values, so a great TE falls. My judgment: the cure is to value the
*player* (how far above his position's replacement level he projects), not a fixed
position weight, plus some teams that rate TEs highly. Blake's game already fits position
values to real contract rankings and has staff-eyes AI boards; the draft check should
include "where do top-rated TEs go" as a standing test.

### 8. Player ratings

**Manual:**
- Every skill has a **current** (red bar) and **future** (green bar), as seen by *your*
  staff; staff members are rated for scouting, and better scouts mean more accurate bars.
- Position skill lists (QB: screen/short/medium/long/deep passes, third-down passing,
  accuracy, timing, scramble frequency, sensing the rush, two-minute offense, reading the
  defense; RB: power inside, speed outside, third-down running, hole finding, elusiveness,
  blitz pickup, hands, catch frequency, third-down catching, endurance, breakaway; and so
  on for every position).
- **Hidden:** fumble avoidance (skill players) and interception avoidance (QBs); you can
  only judge them from stats.
- **Experience at each position** shown 0-9 (offense tracks it per position; defense gains
  general experience).
- Personality: **leadership, intelligence** (mentors, fewer penalties, fewer suspensions),
  **loyalty, wants a winner, personality strength** (bigger affinities and conflicts),
  **fan popularity** (can lift attendance).
- **Volatility:** the chance of a sudden jump or drop in skills as he develops.
- **Developed:** how close to fully developed.
- **Seasonal rust:** players need game reps to reach full strength; usually gone after the
  preseason.
- "Ideal front fit" and "Identifies as" for DL/LB.
- Optional ratings history (re-scouted before camp and after preseason week 2, through the
  eyes of an unemployed veteran scout, so it's a neutral view).

**My judgment:** the strengths are the ones Blake already copied (hidden turnover
ratings, current vs future, staff-dependent accuracy). The *very specific* skill lists
(e.g. QB third-down passing, two-minute offense) are part of why FOF8 stats vary
realistically: different QBs fail in different situations. (Checked: Blake's game already
has these; `engine/positions.py` lists third-down passing, two-minute, timing, read
defense and the rest, nearly one for one, plus a few FOF8 lacks, like shedding blocks and
pursuit.) The neutral-scout ratings history is a clever way to show "how a player developed" without
leaking true ratings.

### 9. Player development, aging, retirement, attitude

**Manual:**
- Coaches develop players; each coach has "develop players" and "develop young players"
  ratings and a **reputation per position group**. A head coach or assistant whose
  specialty matches the player's group can give a **development boost**.
- Volatility drives sudden jumps or drops. Ratings are re-scouted after preseason week 2,
  when a recovering player can turn out to have **lost ability** after a serious injury.
- **Weight training** (just before camp, **once per career**): bulk up or trim down toward
  the ideal weight for his position (ideal weight = better performance) or toward another
  position for a later switch.
- **Mentors:** smart, high-leadership veterans help young players develop (Attitude
  Advisory shows mentors and red-flag "clubhouse disrupters").
- **Retirement:** the designer's research by position: QB matures in season 5, peaks to
  season 13 (average career 5.5 years, 37 starts); RB 3rd to 9th (4.1 years); receivers
  2nd to 10th; OL 2nd to 12th; P 2nd to 14th; K 1st to 16th; DL 3rd to 10th; LB 3rd to
  10th; DB 4th to 11th. Stars don't retire "at the average"; fringe players simply fall out
  of the league because nobody pays them. Established players retire from career-ending
  injury, being unwanted, or the twilight of their curve.
- **Playing-time attitude:** a player unhappy about his snaps stays unhappy until he
  starts and may refuse to re-sign.

**My judgment:** works well and matches Blake's own development design (peaks by position
from real data, staged reveals). Two things worth taking: **(1) mentors** (a cheap, real
locker-room effect that also makes old backups worth keeping), and **(2) once-per-career
weight training** (a small, meaningful decision each camp; Blake's game already models
light/heavy for a position, so the hook exists). The "retire because nobody wants you"
rule is how Blake's game should keep fringe players' careers short: let the market end
them.

### 10. Team chemistry and unit cohesion

**Manual:**
- **Chemistry** (optional): five leadership groups (backfield, receivers, offensive line,
  defensive front, secondary), each with a leader. Players form **affinities or conflicts**
  with their group's leader; leaders form them with the quarterbacks. The total helps or
  hurts on the field. Newcomers count only after a few starts (except recent high picks).
  Before the draft you see a rough "disposition" (mellow / sociable / cheerful); an
  interview reveals more. The Recommend screen flags free agents who'd click (green) or
  clash (blue) with your leaders.
- **Cohesion:** passing (QB + receivers), OL (+ RBs), defensive front, secondary. Mostly
  how long the group has been together. It affects play on the field **and how fast the
  team learns plays in camp**. The stated purpose: make "pay the aging lineman or replace
  him with a cheaper young one" a harder call.

**My judgment:** cohesion is a smart *anti-churn* rule: it gives continuity a real value,
which is also an anti-exploit (you can't rebuild a line from bargain free agents every
year without a cost). It must stay small and data-backed (real research on OL continuity
shows a small but real effect). Chemistry is fun flavor but is the kind of hidden dice
roll Blake dislikes if it swings games. My judgment: take cohesion (small), consider
chemistry only as a news/Bitter storyline source, not a big on-field modifier.

### 11. Injuries

**Manual (says little):**
- A league injury frequency setting: 0 (off) to 400; 100 default; "over 200 is suggested
  for greatest accuracy" (i.e., the default under-injures).
- Statuses: Good, Probable, Possible/Questionable, Doubtful, Out; "Recovering" from a
  serious injury, with possible lost ability found after preseason week 2.
- Injury history with "(x)" marking an aggravation that lengthened the recovery.
- Strength coordinator: "strength training" speeds recovery; "conditioning" mostly helps
  avoid injuries.
- Stadium turf quality lowers the injury rate.
- Coach's "Use of injured players" setting (0-9; at 5 a player plays a competitive regular
  season game at 85% health or better).
- Released injured players: settlement fees.

**My judgment:** FOF8's own manual admits the default is unrealistic. Blake's game is far
ahead here (real injury types and times, Q/D/Out, careers changed by serious injuries,
injury history). **Worth taking:** (1) the coach's "play hurt" setting, (2) aggravation
when a not-fully-healed player plays (the "(x)"), and (3) turf as a stadium choice (fits
Blake's planned stadiums).

### 12. Depth charts and game plans

**Manual:**
- **Offensive depth:** QB and OL are full-timers; a passing-down halfback comes in on
  3rd-and-3+; the rest is set **per personnel group** (who plays in 11, 12, 21, ...).
  An Analyze button warns when a player is over his endurance; tired players get subbed
  play by play; force a player to stay on and he "economizes" (plays worse). HBs have the
  lowest endurance; on defense DTs, then DEs, LBs, CBs, safeties.
- **Defensive depth:** six personnel sections keyed to the offense's number of WRs, with
  forced changes on 3rd-and-long and goal line. Kick and punt returners set here.
- **Special teams** "encouraged/discouraged" per player.
- **Playbook:** built in training camp, 100-200 offensive plays (at least 40 pass, 25
  run); the AI builds one by your OC's style and your QB's strengths if you don't. Up to 12
  new plays a week in season. Each play has a "best fit" style; the OC's style gives a small
  bonus to matching plays.
- **Offensive game plan:** scripted lists by situation (first play of a drive, first down
  after earning one, red zone, inside the 2, backed up inside your 5, two-minute drill,
  down and distance). Each time the situation comes up, the next play in that list runs.
  Up to 150 entries; the OC limits how many **unique** plays you can install each week.
  Automatic "hot plays" cover odd situations (run up the middle, kneel, short pass, spike,
  Hail Mary). The AI generator samples its own percentage chart, so each generated plan
  differs.
- **Defensive game plan:** choose 12 defensive calls (coverage, number of blitzers,
  safety in the box, spy on a running QB); 64 sections (by offensive personnel, down and
  distance, red zone); up to 78 entries. Personnel is automatic by the offense's WR count.
  The DC's front (3-4 or 4-3) is fixed for the season: **change the front only by changing
  the DC.** Blitz weights per defender (1-9); "the offense adapts if one player blitzes too
  often."
- **Game plan details:** 4th-down go-for-it % by score and field position (capped at 30%
  before the 4th quarter, scaled down sharply beyond 1 yard to go); field goal max
  distance (setting + 17 yards); when to hurry up or run out the clock; use of injured
  players; fake kick rate; how strictly to keep players at their own positions (offense
  matters more than defense); how quickly to pull a struggling QB (often in preseason,
  almost never in playoffs); "top CB shadows top WR."
- **Film room:** each opponent's tendencies by down/distance and personnel, and blitz,
  coverage, double-teams, spies and box safeties on defense.
- **Play-calling:** you can call every play yourself from the scoreboard; it doesn't change
  how the sim works.

**My judgment:** this is FOF8's deepest layer and its most "FOF" feature, but it is
also a heavy-time sink most players hand to the AI (the coach-sets-depth and coach-sets-plan
options default to ON). For Blake's goals (realism, anti-exploit), the parts worth taking
are the **settings that a real GM/head coach decides**: 4th-down aggression, FG range,
hurry-up/clock rules, play-hurt threshold, pull-the-QB patience, CB shadowing, the
DC's front fixed by who you hire. A full scripted playbook is *my judgment* a later,
optional layer: big build cost, and a scripted list can be gamed (find a play the AI can't
stop and repeat it). The "a blitzer used too often becomes predictable" rule is a good
anti-exploit idea for any play-calling Blake adds.

### 13. Coaching staff

**Manual:**
- Five jobs: head coach, offensive coordinator, defensive coordinator, assistant coach,
  strength coordinator. Each has an **area of expertise** (a position group). OCs must
  specialize on offense, DCs on defense; head and assistant coaches anywhere but strength.
- Ratings: develop players, develop young players, **motivation** (head coach, in
  games), **discipline** (head coach, penalties), **play calling** (coordinators),
  **interviewing** (accuracy of interviews), **scouting** (accuracy of scouting); a
  development **reputation per position group**; strength coaches rate strength training
  (recovery) and conditioning (avoid injury).
- OCs: an **offensive style** (plays matching it are learned a little better) and a
  **playbook limit** (unique plays per week). DCs: a **favored front** that your team uses.
- Everyone but the strength coach develops and scouts players; OC leans offense, DC
  defense, assistant special teams.
- **Hiring = the staff draft:** 5 rounds (HC, OC, DC, assistant, strength), order by
  **last season's profit**. Anyone unhired is available; you may promote (assistant to
  coordinator or HC; coordinator to HC) from any team, and "poach" a same-level coach from
  a team picking at least 4 slots later if he's in his last year. Salary is set by the role
  and **how early he's picked**. You can skip to keep your coach. Suitability 0-99, with a
  bonus for DCs whose front matches yours.
- Extensions only in the retention stage, only with 1 year left; they ask for a raise;
  let one expire and you must redraft him.

**My judgment:** the *jobs and ratings* are good (Blake's design kept the 5 jobs and
added 3 front-office jobs). The *hiring* is what Blake dislikes, and the manual shows why
it feels wrong: order by profit is unrelated to football; salary set by draft slot means
the coach has no say; there's no interview, no candidate choosing you, no coaching tree.
Blake already replaced it with a carousel where candidates choose. Things still worth
taking from FOF8's staff: **motivation** and **discipline** (penalties) as head-coach
effects, the **interviewing** rating (separate from scouting), and the DC's front being
tied to the man you hire.

### 14. Owner, finances, stadium, cities

**Manual:**
- The GM is graded each year by "Herb the Referee" on four parts: **wins** (big bonus for
  reaching the Bowl), **roster value** (scouts' value of players under contract),
  **profit** vs other teams, and **franchise value** vs other teams, scaled by a
  difficulty factor per franchise. "Pleased with anything over 50." The financial essay
  says over half the grade is franchise and stadium value.
- Owner is "mostly invisible" but fires you if finances go badly (if firing is on).
- Profits limit the bonus money you can offer players and the salaries for staff.
- **Tickets:** set once a year before free agency; luxury boxes priced per season (~25
  people each), other seats per game; attendance tells you if you priced it wrong; a
  Recommend button; a "family of four" price comparison (tickets, parking, concessions,
  local cost of living).
- **Stadium:** proposals at the start of the year; public vote after the draft; your
  contribution % raises approval (requests can't exceed half the cost); a high-quality
  builder costs more but earns more for longer; renovations of turf (fewer injuries) and
  parking (more revenue, fewer no-shows). A new stadium's earnings fade over time. After
  a rejected vote you may **relocate** the next year.
- **Cities:** population, income, growth, poverty, entertainment competition, "trendiness,"
  desire for a team, weather (affects play and extreme attendance), nearby teams.
- Franchise value = roster value + local fan support + local economy + stadium.
- Other money signals: popular players lift attendance; a QB controversy on "sports
  radio" (fans want the young backup) can lower popularity and attendance; the "Sweat
  Socks" training-camp TV show boosts featured teams' popularity.
- You can switch teams before free agency (to a less prestigious team; harder in the first
  20 seasons).

**My judgment:** this is FOF8's most "GM" feature and one Blake's game barely has yet
(cap eras exist; stadiums are an approved "eventually"). What works: one yearly
decision (ticket prices), one big multi-year decision (stadium), and visible feedback
(attendance). What doesn't: by the manual's own words, **more than half your grade is
money**, which pulls the game away from football; and a franchise-value race between AI
teams makes little sense in a single-player game. My judgment: if Blake adds finances,
keep them as a *budget that feeds football* (staff budget, facilities that help
development/injuries, fan mood) rather than a score you chase, and make relocation an
option, not a goal.

### 15. Trades

**Manual:**
- AI GMs judge a trade by **team strength before vs after**, with traded-away players
  replaced by **replacement-level talent from leftover free agents**. You can't trade a
  player the free agent pool could replace with someone better.
- Each **position has a value**; QBs far above everyone, kickers almost nothing; so both
  are rarely traded. AI GMs lean conservative (won't trade an All-Pro QB for a pile of
  decent players).
- Up to 5 players/picks per side; next season's picks tradable; no cash; can't go over
  the cap; trades during the draft allowed ("your pick may be worth much more to them").
- AI GMs email offers (one-time, gone next stage; often better than what you could build).
- GM attitude: accept-then-back-out or absurd offers sour a GM; enough of it and he stops
  listening for about a year.
- "Shop player": see which teams want a player; limited uses per season.
- Scout's "Cap/Needs" list for all 32 teams.

**My judgment:** the design is sensible on paper, and the manual tells us *exactly* why
Blake found it exploitable: (1) **fixed position values** (a position the AI values low
can be pried away cheaply, and one it values high can be sold dear), (2) value measured by
**the AI's scouting, not performance**, and (3) "before vs after" team strength rewards
filling *their* hole even with a weaker player. The fix, in my judgment: AI values players
by **surplus value** (production and projected ratings over replacement, minus contract
cost, by age), adds its **own needs and timeline** (contender vs rebuild, which Blake's
game already has as yearly approaches), and refuses lopsided offers even when the
"strength" math says yes. Blake's game has draft-day trades priced at the real trade
chart; full player trades are still to build, and this is where the FOF8 lessons matter
most.

### 16. The season and playoffs

**Manual:**
- 5 preseason weeks, 17 regular season weeks, 4 playoff weeks ending in the Front Office
  Bowl. The manual mentions division leaders, wild cards and byes but never says how many
  teams make it (my guess: 12, the 2016 NFL format).
- Standings color codes (leading division, clinched division, in line for playoffs,
  clinched wild card, eliminated).
- **Power ratings ("System 304"):** every team vs every other by score, with diminishing
  returns for big margins and heavy strength-of-schedule weight; point spreads come from
  these.
- **Playoff probabilities** from week 6: simulate the rest of the season (10,000+ times)
  using the point spreads; odds for each seed, byes and wild cards.
- Game previews; option to hide results (for watching your game); "Solevision"
  play-by-play viewer for any week in history; detailed logs can grade whether each player
  did his job on each play.
- Suspensions for off-field conduct (intelligence lowers the risk).
- Weather affects play.

**My judgment:** power ratings, point spreads and playoff odds are cheap to add and make
the season feel covered by a real media. Blake's game has standings, playoffs and a news
hub; **worth taking:** power rankings, point spreads in previews, and playoff odds (all
pure math on results, no effect on the sim). The "did he do his job on this play" log is
a great idea for a later game-detail view.

### 17. Stats, records and history

**Manual:**
- Season and career player stats; team stats (182 kinds per the design PDF); team
  summary; team history and graphs; team vs team all-time records.
- Records: career, single season, single game, playoff game; team single season, single
  game, playoff game. Players' honors list includes their rank on each team's all-time
  lists.
- Awards: offensive/defensive player of the year, offensive/defensive rookie of the year,
  MVP, Bowl MVP, 1st and 2nd team all-league, player of the week, coach of the year,
  skill competition winners, "Legend of the Game."
- **Hall of Fame:** eligible 5 years after retiring; needs 80% of the vote; no limit per
  year; **one shot only** (fail once, never again); players get credit for pre-sim careers.
- Draft history, first picks, how each team acquired its players, average roster age,
  "native snap %" (snaps by players a team drafted).
- **QB Coterie:** every QB season with 8+ starts scored (100 = perfect), grouped by years
  of experience, to compare rookies across eras. "QB comparison" vs top retired QBs.
- GM records and performance history.
- "Create History": sim up to 50 years at the start.
- Strongest, fastest, most athletic players lists; "Sage of the Gridiron" weekly top-10s.
- Export to CSV and HTML pages.

**My judgment:** this is where FOF8 shines and where "stats are the reward" lives. Blake's
game has season/career stats, leaders, awards, Pro Bowl and news. **Worth taking:** the
record books (all seven kinds), the Hall of Fame with one-shot voting, team all-time
lists in a player's honors, native snap %, how-acquired chart, the QB Coterie, and "Create
History" (needs a fast sim; Blake's sim is now faster).

### 18. Everything else in the manual

- **Media flavor:** Quote of the Day (365 quotes), Sports Radio QB controversies (they
  have a money effect), Sweat Socks camp TV show (popularity), Sage of the Gridiron lists,
  Green Page (best young players), Grey Sheet (top 88 free agents), "Strongest/Fastest/Most
  Athletic Man". Blake's Bitter covers this space better; Sports Radio's idea (fan anger
  at a QB choice that *does* something) is the one worth stealing.
- **Herb's grade** (yearly GM report card); GM firing optional; change teams.
- **Multi-player** leagues (a big part of the manual): skipped, since Blake's game is
  single-player.
- **Data export:** CSV/HTML of everything (for spreadsheets and league websites).
- **The College Years** (a separate product) could create draft classes with college
  stats. Imported rookies then show their last college season's key stats.
- Easter eggs ("Secret Convention", "Secret Tournament").

### 19. How FOF8's sim "thinks" (from its two strategy essays and the data files)

**Manual:**
- **Real play-by-play behind the run game.** The designer built run results from real
  play-by-play (starting with every 1997 run, later 18 seasons): average and spread of
  gains by direction (all runs 4.16 yards, spread 6.27; end runs 5.02 and 7.19; up the
  middle 3.73 and 5.47; on 3rd-and-1-2, about a yard less everywhere). Line and defender
  run ratings were graded on whether runs in their direction beat the median (2 yards
  inside, 3 at the ends); linebackers on the mean; the secondary on stopping long runs. His
  advice: about 30% of runs up the middle, 10% around each end, because end runs boom and
  bust.
- **Weight matters most.** A player's performance drops with the gap between his weight
  and the ideal weight for the spot he is playing *on that play*. Height matters for QBs
  (seeing over the line; a QB's weight doesn't matter), receivers (contested balls), DBs
  (coverage) and two-gap 3-4 linemen.
- **Offense is position-locked, defense isn't.** Offensive experience is tracked per
  position (0-9), with slower gains at related spots (any OL spot, RB/FB, X/Z); offensive
  players always play best at their primary position. Defenders can switch spots with
  little or no penalty and gain general experience.
- **Four fronts:** True 3-4 (two-gap linemen), 3-4 Eagle, 4-3 Under, 4-3 Over; each spot's
  technique and gap is spelled out. Personnel follows the offense's WR count (nickel,
  dime); goal line and prevent are automatic.
- **Nine coverages:** man, Cover-1, Press-1, Tampa-2, Cover-2, Press-2, Cover-3 Sky,
  Cover-3 Cloud (rotated to the best WR), Cover-4. More deep defenders = better against the
  pass, worse against the run. One receiver can be doubled (the staff's #1 or #2).
- **Anti-repetition:** reuse a play many times in a game and the opponent "learns" it; a
  player who blitzes too often gets picked up more; too many counters/reverses stop
  working.
- **Aging detail:** pass rush *technique* does not decline with age; pass rush *strength*
  does. Hard hitters cause more injuries.
- **Ratings scale:** internal ratings are 0-1000, rolled partly at random from the file's
  guideline at each new career; skills sit on a logarithmic curve (except QB scramble rate).
- **Talent pyramid of the default player file** (about 1,750 players): rare superstar 0.3%,
  superstar 0.4%, near superstar 0.6%, elite starter 1.1%, excellent starter 1.5%, very
  good-plus 2.6%, very good 3.9%, good starter 12.2%, replacement-level starter 23.9%,
  roster filler 53.4%. About 1,700 players active league-wide.
- **Player file fields:** max contract 5 years; 7 minimum-salary tiers (rookie, 1, 2, 3,
  4-6, 7-9, 10+ years); "participation % last year" (snap share); **Hall of Fame points**
  per season (a QB needs about 6,000, a defensive lineman about 3,000 "but harder to
  earn"); **volatility** 0-100 (small-college players and very highly rated college players
  should be more volatile); **injury propensity** 0-10 (0-2 for never-injured; over 5 only
  for fragile players). Draft files need at least 800 prospects; DL/LB and OL get exact
  spots at random on import and can switch freely after the draft.

**My judgment:** the run-game approach (real averages *and spreads* by direction and
situation) is exactly Blake's "spread, not just averages" rule, and his sim already
calibrates this way, more broadly. Two ideas stand out as worth borrowing: **(1)
anti-repetition** (an opponent adapts to what you overuse; it makes any future
play-calling layer exploit-proof), and **(2) skills that age differently** (technique holds,
strength fades), which gives aging pass rushers a realistic shape. The talent pyramid is
a useful cross-check for Blake's "talent feels like a quota" question: FOF8's file has
about 2.4% of players at "elite starter" or better and over half as filler. The "small
school = more volatile" rule is a nice touch for scouting uncertainty.

---

## Part 3: FOF8 vs Blake's game (Glory Bowl GM)

Based on `CLAUDE.md`, the build log's headings and decisions, `docs/staff-design.md`, and a
quick search of `engine/` and `screens/` (Oct 23). If I've missed something that's built,
it's because I skimmed; say so and I'll correct it.

### What FOF8 has that Blake's game doesn't yet

Football side:
1. **Player-for-player trades with AI GMs** (your offers, AI-initiated offers, "shop a
   player," GM attitude toward you). Blake's game has draft-day pick trades only.
2. **Weekly game plans, playbook, play-calling** (scripted situations, 12 defensive
   calls, blitz weights, film room). Blake's sim uses coordinator styles instead.
3. **Game-plan "details" a head coach sets:** 4th-down aggression, FG range, hurry-up and
   clock-killing rules, play-hurt threshold, pull-the-QB patience, CB shadows the top WR,
   fake-kick rate.
4. **Defensive fronts as a staff choice** (the DC's 3-4/4-3 front, fixed for the season)
   and scheme-specific "Fit" positions for DL/LB.
5. **Unit cohesion** (continuity bonus) and **team chemistry** (leaders, affinities,
   conflicts).
6. **Mentors** among players (in Blake's code "mentor" means a coaching tree);
   **playing-time attitude** (unhappy backups who won't re-sign); **holdouts**;
   **suspensions**.
7. **Agents** (charisma, client lists, stubborn agents, a signing edge with an agent you
   already work with).
8. **Weight training** once per career.
9. **Seasonal rust** (needs preseason reps). The build log lists rust as still to do.

League and history side:
10. **Record books** (career, season, game, playoff; team versions). Blake's news tracks
    single-season league records; there's no record-book screen.
11. **Hall of Fame** (5-year wait, 80% vote, one shot). Not built (only the Hall of Fame
    *Game*).
12. **Playoff probabilities**, **point spreads**, a math-based **power rating**. Blake's game
    has power rankings as news text.
13. **QB Coterie**, native snap %, how-acquired chart, average age by unit, team-vs-team
    all-time records, GM records.
14. **Create History** (sim up to 50 years at the start).
15. **Scheme-aware franchise tag** ("Identifies As" for DL/LB).
16. **CSV/HTML export** of the league.

Business side:
17. **Owner, finances, tickets, stadium, relocation, cities** (Blake's stadiums are an
    approved "eventually"). Blake has a staff budget and cap eras, but no revenue or ticket
    model.
18. **The yearly GM grade** (Herb's report card) and **GM firing** for you.
19. **Changing teams** as GM.

### Where Blake's game already goes further

- **Realism checked against real data.** FOF8 calibrated runs from play-by-play; Blake's
  game is calibrated across every stat, leaderboard, "how common" season and team effect
  against recent real NFL data, with tools to re-check after every change.
- **Roster rules:** 90-man camps, one cut to 53, practice squads, IR/PUP with returns,
  waivers, 48 actives plus the emergency QB (FOF8: 60/53/46, IR is for the season).
- **Contracts:** rookie scale, fifth-year options, June 1 cuts, restructures, RFA tenders,
  real pay ladders (`cap_market.py`). FOF8 has bonus/salary, Cap Out and the tag.
- **The cap's future:** TV-deal eras, labor deals and shocks from real history (FOF8: a
  TV contract bump in a commissioner-set range).
- **Injuries:** real injury types and recovery times, game-status tiers, careers changed
  by serious injuries, an injury history (FOF8's own manual says its default injury rate
  is too low).
- **Coaching staff hiring:** a carousel where candidates choose you, owners' budgets,
  reputations that sharpen with a record, coaching trees, poaching, front-office jobs
  (scouting directors, head trainer). This is the fix Blake wanted for the staff draft.
- **AI general managers** with their own habits, hired and fired; AI teams judge players
  through their own staff's eyes, with mistakes sized from real data. FOF8's AI used one
  league-wide scouting view plus fixed position values (the root of Blake's exploits).
- **Scouting presentation:** cloud bars, staff impressions in words, two scouts, a skill
  web, honest ranges.
- **The draft room:** live pick by pick with a draft speed, AI draft-day trades priced at
  the real chart.
- **Media:** Bitter (social media with invented accounts), storylines that build across a
  season, awards voted by a media panel, a fan/player/coach Pro Bowl vote and Pro Bowl
  game. FOF8's equivalents are short lists (Sage, Sports Radio, Quote of the Day).
- **Player cards and pop-out windows** that can be dragged to another monitor (FOF8's
  pop-up feel, with better visuals and football-style number formats).
- **Ratings:** the same situational skills FOF8 has, plus a few it lacks (shedding blocks,
  pursuit), and size trade-offs shown plainly (light/heavy for a position).

### Ideas worth taking (my judgment, ranked by value for effort)

1. **Trades built on surplus value, not position value** (the biggest gap, and FOF8's
   biggest exploit). AI values a player by production and projected ratings over
   replacement, minus contract cost, by age and *its own* timeline (all-in/normal/rebuild,
   which already exists). Keep FOF8's good parts: AI GMs offer trades themselves, a
   "shop this player" list, and GMs who stop listening if you spam lopsided offers.
2. **A free-agency "fair price" check.** Add to `tools/free_agency_check.py`: players with
   good recent stats *and* good ratings never sign far below their market while teams
   still have room (Blake's FOF8 exploit).
3. **A standing draft check on tight ends** (where top-rated TEs go vs real), so the FOF8
   "TEs fall past pick 8" exploit can't creep back.
4. **Head coach game settings** (4th-down aggression, FG range, clock rules, play-hurt,
   QB patience): a small screen with real effects; AI coaches get their own values from
   real data (for example, real 4th-down rates by coach).
5. **Record books and a Hall of Fame** (with FOF8's sensible rules: 5-year wait, a vote
   threshold, no limit per year; my judgment: allow several tries rather than one shot,
   since the real Hall allows 20 years of eligibility).
6. **Playoff odds and point spreads** from a power rating (pure math on results; no effect
   on the sim; makes news and previews richer).
7. **Mentors and playing-time attitude.** A smart, high-leadership veteran helps a young
   player at his position develop a little; an unhappy backup is harder to re-sign. Both
   create real roster trade-offs and good Bitter/news stories.
8. **Unit cohesion (small).** A small, data-backed edge for OL and QB-WR groups that have
   played together, so continuity has value.
9. **Weight training once per career** (Blake's size trade-offs already model light/heavy,
   so the hook exists).
10. **Agents** (light version): an agent who represents several of your players gives a
    small signing edge; stubborn agents mean more holdouts.
11. **Skills that age differently** (technique holds, strength fades), if the development
    model doesn't already do this.
12. **Owner and money** (later, with stadiums): one yearly decision (ticket prices), one
    big multi-year decision (stadium), visible feedback (attendance). My judgment: make it
    feed football (budget, facilities, fans), not a score that's half of your grade as in
    FOF8.
13. **Create History** (sim 10-50 years before you start), now that the sim is faster.
14. **QB Coterie and other history views** (native snap %, how acquired).

Things I'd *not* take (my judgment): the staff draft (Blake already replaced it); the
over-the-cap "lose your picks" softness (Blake's real rule is better); disappearing email
(Blake's news archive is better); franchise value as a GM score; chemistry as a big
on-field swing; a full 200-play scripted playbook unless Blake wants it as an optional
layer (big cost, and scripts can be gamed).

---

## Where this stopped

Everything in the task was covered. Read in full: every single-player topic of the manual
that describes a system (about 110 of 197 topics), both strategy essays, the Draft File
and Player File help, and the data field lists. Skipped on purpose: the ~25 multi-player
topics, most individual stats-screen column lists, the color chooser, and the
play-creation screen's controls. The budget stayed under Blake's limit.

