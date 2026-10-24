# Player trades: design, real data, results

Built Oct 23 (trades session). Code: `engine/trades.py` (rules), `engine/news_trades.py`
(news and Bitter), `screens/trade_page.py` (the Trades tab, Team section), `tools/trade_check.py`
(the realism and exploit check), real data from `docs/research/trade_research.py` ->
`docs/research/real_trades.json`. Everything marked PROVISIONAL is a judgment call for Blake.

## 1. Blake's decisions (Oct 23)

- **AI teams call you with offers, at real NFL rates:** a few calls a season, more near the
  deadline and around the draft, mostly about players you have to spare or that a team needs.
- **Future picks up to three drafts out.** An AI team values a future pick by how good it
  expects that team to be, discounted for the wait.
- **The AI answers in words, like a phone call:** "not interested", "close, add a little", or a
  counter-offer. No value meter, no numbers. A GM you keep insulting stops listening for a while.
- **The real trade window:** from the new league year to the deadline (Tuesday after week 9 in a
  17-game season), then closed until the next league year.

## 2. What FOF8 got wrong, and the fix

FOF8's AI traded by a fixed value per position (TEs near the bottom) and judged a deal by "team
strength before vs after" through one league-wide scouting view. So a position the AI valued low
could be pried loose cheaply, quantity could buy quality when it filled the AI's hole, and every
AI team saw players the same way. Here each team values **the player**, through **its own staff's
eyes**, in its own situation:

- **What he adds to its position group** over who would play otherwise: its starters, first
  backup and second backup (`group_value`), each season he's under contract. What a season of a
  player's play is worth comes from the real pay ladders (`cap_market.LADDER`: the Nth best-paid
  player at the position), plus a premium for the scarce top of each position (`STAR_K`: the best
  player at a position is worth 1.5x his pay rung; you can't buy a top-5 player in free agency).
  A backup counts for a quarter of what he'd add as a starter (`BACKUP_SHARE`), the second backup
  5%. So an elite TE is worth what an elite TE is worth over the TE a team would otherwise play,
  not a fixed "TE value"; a backup's worth depends on who he backs up.
- **Minus what he costs:** the base salary he brings above the minimum (the roster spot is paid
  the minimum whoever fills it), year by year. His signing bonus stays with the team that paid it
  (the real rule), so a player with big bonus money is cheaper to take on than his cap hit says.
- **His age and development:** his rating each season ahead (`cap_market.project`, the same
  growth and decline curves free agency uses), as this team's staff sees him now and his ceiling.
- **The rights to re-sign him** if he's 29 or younger when his deal ends (half a season of his
  worth over his market price), and a first-rounder's fifth-year option.
- **The team's timeline:** all in (this season counts 1.25, each later one 0.75 of the one
  before), normal (1.0, 0.85), rebuilding (0.65, 0.92: the future and picks matter more). In the
  season only the games left count, and this season counts less for a team out of the race
  (`race_factor`).
- **Picks** on the same scale: the Jimmy Johnson chart the draft room already uses.

All values are in chart points (pick 1 = 3,000, a mid 1st ~1,000, a mid 3rd ~190, a 7th ~5). A
season of surplus worth 1% of the cap is 40 points (`POINTS_PER_CAP`).

**Staff eyes, with care:** a team acts on half its staff's misjudgment of another team's player
(`TRADE_SURE` 0.5). With the full misjudgment every call landed on the player its staff overrated
most (the "winner's curse"): in the first test, young players on rookie deals moved for first-round
picks every week. The team that has him knows him better (its staff's own-player error is small).

## 3. Draft picks

- **Ownership:** `league.trades["picks"]` keeps only traded picks ("season-round-original team" ->
  owner). The draft room gives each traded pick to its owner when the draft starts
  (`draft.DraftRoom`), free agency keeps cap room for the picks a team actually holds
  (`free_agency.set_pick_reserve`).
- **In the draft room** (follow-up, Oct 23): this draft's picks and next year's can be traded, by
  you and by AI teams. AI teams value next year's pick their usual way (about a round lower); a team
  pays with this draft's picks unless next year's fits the price better (`FUTURE_PACKAGE_COST`), and
  only uses next year's picks to move up into a pick worth a mid-round price or more
  (`FUTURE_MIN_PRICE`; without it late-round trade-ups doubled). Real draft-time deals 2013-25: 23%
  include a next-year pick; the game 14-21% (14% in `trade_check`'s leagues, 21% in the integration
  league), with draft-day deals still 21 a draft as the draft session calibrated them (`draft_check`,
  real same-year deals 21.1). While the draft is on, the Trades tab trades players and later picks.
- **Which drafts:** the next three not yet held (real rule).
- **Value:** the pick's expected chart value where its team is likely to pick (this year's order
  once it's set; in-season from the record so far and last season; later drafts drift back toward
  the middle), discounted for the wait: x 0.50 per year until that draft for a normal team, 0.42
  all in, 0.60 rebuilding (`PICK_DISCOUNT`), and rebuilding teams want picks 15% more. Real data:
  in draft-time deals 2013-25 with one next-year pick, the team taking it counted it at 0.36-0.48
  of its round's middle (median about 0.44; the old "one round lower" rule of thumb). A GM who
  trades down on draft day values picks a little more.
- **On screens:** "2028 2nd PHX", where it falls in words ("likely early in the round"), or the
  pick number once the order is set.

## 4. AI teams trading with each other

At each step (each offseason phase from the league year on, each preseason week including
cut-down day, each regular-season week up to the deadline) a number of AI teams pick up the phone
(`CALLS` by phase, sized to the real counts below):

- **A team with a hole** (its worst starter 4+ rating points short of a typical starter there, or
  its first backup short of a typical backup; `NEED_POINTS` 8) looks at six players on other AI
  teams who'd fill it: mostly players who don't start for their own team (another team's spare
  player is what a buyer usually gets), sometimes a starter (`STARTER_LOOK` 0.3). It takes the
  cheapest deal that works. How often a hole at each position is filled by trade rather than free
  agency is sized to the real share of traded players by position (`POSITION_MARKET`).
- **A rebuilding team shopping a veteran** (28+) takes calls from several teams and gets about
  what the second-keenest would have paid (`AUCTION` 0.85). **Stars** (paid 10%+ of the cap) go the
  same way whoever sells them: the price is about what the second-keenest of several teams would
  pay, so a star brings back a 1st (in the first version they mostly went as salary dumps).
- **Draft-day player trades:** as the draft opens, a few AI teams call about players (real: 1.4 a
  draft in 2021-25, 2.2 in 2013-25; the game 1.3).
- **A deal happens** when both come out ahead in their own eyes: the seller wants what losing him
  costs plus a premium for one of its starters (20%, plus 35% for a young one: the core it's
  building; none for a rebuilding team's veterans), the price lands just above the seller's floor
  (`PRICE_SPLIT` 0.15), paid in picks (fewest, nearest drafts) or a player the seller needs.
- **No flipping:** an AI team doesn't re-trade a player it got in a trade this league year (the
  first version had teams buying and reselling the same player in the same week).
- **Legal every time:** both teams under the cap right after (an exact dry run of the money moves,
  the offseason top-51 rule included; in camp a team keeps 1.5% of the cap for week 1), roster
  limits (an AI team over the limit cuts its least valuable player who didn't just arrive), at
  most 5 players and picks a side, practice squad and reserve-list players can't be traded.

## 5. Your trades: the phone call

You build an offer (your players and picks for theirs) and make the call. The GM answers:

- **"You've got a deal."** You can make the trade, or hang up: backing out of an agreed deal counts
  against you like a lowball (FOF8).
- **"We're close. Add a little something..."** (you're within 15% of what they need), usually with
  what they'd do: your offer plus one of your picks or a player of yours they need, or the same
  offer for a bit less of theirs. You can take it, load it to edit, or walk away.
- **A counter-offer** when you're further off but there's a deal they'd make.
- **"We're not interested."** / **"He's not available."** (a core player, ~a top-10 pick's worth to
  them, for less than 75% of what they'd need, unless they're rebuilding).
- **A lowball** (less than half of what they'd need): "Is this a joke?" Each GM puts up with 2-4
  lowballs (his own number), then **stops taking your calls for 10 steps** (about four months).
- What they need from you: they come out ahead by 15 points plus 8% of what they give, and they
  won't sell you a player for less than 95% of the most another AI team would pay for him
  (`MARKET_SHARE`): no buying low from one team to sell high to another.

The deal box shows before you call: both sides, your cap room and theirs before and after (with
the dead money from the bonus money of players you send), your roster count, and "Not allowed"
with the reason when a rule blocks it (cap, roster limit, the window).

## 6. Calls to you, and shopping a player

- **Offers to you:** at each step some AI teams with a hole look at your roster for a player who'd
  fill it, most often one you have to spare, and offer a little more than they think you'd lose
  (`OFFER_SWEETEN` 3-15%), never more than he's worth to them. Each offer is good until the next
  week or phase. Rates by phase (`USER_CALLS`): a few a season, most at the league year, before
  the draft, on cut-down day and at the deadline. Home's "Needs your attention" lists them.
- **Shop a player:** every AI team that wants him, how keen it is ("Very interested",
  "Interested", "Some interest") and its best offer, which you can take on the spot. The league
  hears about it: an insider's rumor on Bitter.

## 7. Money rules (real)

- The team trading a player keeps his remaining signing-bonus money as dead money: all of it this
  season in the offseason (before June 1), this season's share now and the rest next season once
  camp opens and during the season; it also keeps the salary already paid this season.
- The team getting him takes over his base salaries from now on (only the weeks left this
  season), with their guarantees.
- Both teams must be under the cap right after the trade.

## 8. News and Bitter

`engine/news_trades.py`, a new "Trades" kind: a story for every trade with a player (who went
where for what; age and years left; both records in-season; the dead money left behind when it's
big), a deadline round-up of the last day's deals, and on Bitter: an insider's scoop, the new
team's welcome, the old team's thank-you, fans of both teams, sometimes the player himself, and
rumors about players you shopped. Finished seasons' news stays frozen; trades show up in the
season they happen. Trades also appear in the teams' transaction lists ("Traded", "Acquired in
trade").

## 9. Real data (nflverse trades, `docs/research/trade_research.py` -> `real_trades.json`)

League years 2013-25 (March to March); 2021-25 where noted (the recent level; trades have grown).
A pick row in the data also names the player later drafted with it, so only rows without a pick
count as players.

- **Trades with players:** 47.2 a league year 2013-25, **59.8 in 2021-25** (range 41-67).
- **By phase, 2021-25:** league year to the draft 11.6 (+7.4 dated after the deadline: agreed then,
  made official at the league year), draft days 1.4, after the draft to camp 2.8, camp and the
  preseason 19.4, the season up to the deadline 17.2. **The deadline rush:** 9.2 in the deadline's
  own week, 3.2 the week before, under 1 a week earlier.
- **What's in them (2013-25):** one player for picks 40.1 a year, players both ways 3.8, players
  for players 3.3; 1.16 players a deal. Pick-only deals (30.5) are draft-day swaps, which the draft
  room already makes.
- **Who:** median age 26 (mean 26.5); by position (share of players traded vs share of roster
  spots) QB 10% (6%), WR 16% (11%), DB 18% (17%), OL 16% (17%), LB 12%, EDGE 8%, RB 7%, DL 5%,
  TE 5%, K/P/LS 2%.
- **Contracts:** median 1.1% of the cap a year; 46% under 1% (mostly depth players); **stars (8%+
  of the cap) 4.5 a year** (range 1-10); first-rounders in their first 4 seasons 6.8 a year.
- **Deals per team a year:** 2.96, spread 2.38, 14% of teams make none (2013-25).
- **What comes back** for one player traded for picks (best pick's round; chart value of the
  picks): under 2% of the cap mostly 6th-7th rounders (median 14 points); 2-10% median 35 (a 5th);
  10%+ 46% get a 1st (median 608, a late 1st).
- **Future picks:** of picks traded, 82% are in the next draft, 16% the one after, 2% later.

## 10. Results (`tools/trade_check.py`, 6 leagues x 3 league years; `tools/trade_report.txt`)

Made-up game results, the game's own offseason, the AI teams' weekly roster moves. Sim | real:

- Trades with players a league year **51.2 | 59.8** (41-67). By phase: league year to the draft
  16.1 | 19.0, after the draft 1.9 | 2.8, camp and preseason 17.7 | 19.4, season 15.5 | 17.2;
  deadline week 8.5 | 9.2, the week before 2.3 | 3.2.
- Deals per team a year 3.20 | 2.96 (spread 2.22 | 2.38; none 7% | 14%).
- Players for picks 46.2, players both ways 4.9 | 40.1, 7.1; players a deal 1.10 | 1.16.
- Age: median 25 | 26, mean 26.1 | 26.5.
- Position: QB 13 | 10%, WR 17 | 16, DB 15 | 18, OL 16 | 16, LB 12 | 12, EDGE 10 | 8, RB 6 | 7,
  DL 4 | 5, TE 3 | 5, K/P/LS 3 | 2.
- Contracts: median 0.7% | 1.1% of the cap, under 1% 56 | 46%; stars **4.7 | 4.5** a year;
  first-rounders in their first 4 seasons 5.9 | 6.8.
- Returns, median chart points: under 2% 21 | 14; 2-5% 76 | 35; 5-10% 269 | 35; 10%+ 420 | 608
  (n small: 0.8 a year | 1.8).
- Picks by drafts away: 80/15/5% | 82/16/2%.
- **Legality: 0 of 921 trades left a team over the cap or its roster limit.**
- **Parity:** team strength spread 0.237 with trades, 0.249 with AI trades off (same leagues):
  trades don't tilt the league toward the strong teams.

**Exploit checks** (your team at the start and end of each league, in-season and at free agency):
1. **Positions (FOF8's cheap TEs):** what an AI team asks for one of its 5 best players, per 1% of
   the cap his market price is: QB 74, RB 74, WR 83, TE 70, T 72, G 70, DE 71, DT 72, OLB 67,
   CB 66, S 69. No position comes cheap; an elite TE costs about what his worth says (~530 points,
   a pick in the 20s).
2. **Quantity for quality:** three of your average starters for one of their 12 most valuable
   players: 1 accepted in ~290 tries (most were lowballs or illegal by the cap), and that one was
   good for the AI team by true ratings.
3. **Dumping a bad contract** (your worst, 3%+ of the cap) for a 7th: accepted 12 times in ~200,
   10 of them good for the AI team by true ratings (the player filled a hole: one team's surplus is
   another's need); 2 were its scouting mistakes.
4. **Buy low, sell high:** buying a player at one AI team's asking price and selling him to the
   keenest other: profitable 3% of the time, and the 90th percentile loses 25 points.
5. **Lowballs:** a 7th for a team's best player, six calls in a row: "lowball, lowball, gone..." (or
   illegal by the cap).

**Integration test** (scratchpad `integ_trades.py`: a startup-draft league, 4 seasons of real game
sims and offseasons phase by phase, your team taking ~35% of AI calls, calling teams itself,
shopping players; save/load round trips at the deadline, free agency and the draft): no crashes,
save/load keeps the trade state, trades open on deadline day and closed after, every traded pick
went to its owner in the draft room, ~50-60 trades a league year, 40-60 trade stories and 110-170
Bitter bits a season, 0 wording errors. A deadline step takes 1-2.5 s (10-15 deals), other weeks
much less.

## 11. PROVISIONAL (for Blake)

1. The look of the Trades tab (Team section): four views (Make a trade, Offers to you, Shop a
   player, Trade log); the deal box with both cap rooms.
2. The GM's words (a phrase list per answer) and his patience: 2-4 lowballs, then 10 steps
   (about four months) of not taking your calls; backing out of an agreed deal counts as a lowball.
3. What counts as "close" (within 15% of what they need) and a lowball (under half).
4. AI teams want a bit more from you than from each other (15 points + 8%), and won't sell you a
   player for less than 95% of what another AI team would pay.
5. How often AI teams call you (`USER_CALLS`): about 6-7 calls a season in the integration test.
   Offers last until the next step.
6. Shopping a player tells the league (a rumor on Bitter); no limit on how often you shop.
7. With a full roster you must release someone before taking on an extra player (the real rule):
   the deal box (and each offer) lets you pick who's cut when the trade goes through (lowest rated
   listed first), and shows your roster after it.
8. Players on reserve lists and practice squads can't be traded (simplification).
9. The value model's knobs: the star premium (1.5x for the best at a position), backup 25%, picks'
   discount (0.42 / 0.50 / 0.60 a year by timeline, from the real draft-day market), teams acting on
   half their read of other teams' players, the seller's premium for starters (20%, +35% if 25 or
   younger).
10. How often holes are filled by trade, by position (`POSITION_MARKET`): sized to the real mix.

## 12. Not built / follow-ups

- **Done Oct 23 (follow-ups):** next year's picks in the draft room (yours and the AI's), draft-day
  player trades, stars priced by an auction, picking a player to release on a full roster. No trades
  during a new league's startup draft (Blake): the window is closed, the startup room has no trade
  offers, and the integration test checks it.
- **Stars on 10%+ deals** now bring back what real ones do (67% a 1st, median ~1,000 chart points;
  real 46%, median 608) but move less often (0.5 a year vs real 1.8; all 8%+ deals 3.4 vs 4.5,
  inside the real range of 1-10 a year).
- **Conditional picks**, three-team deals, salary retention (not allowed in the NFL anyway).
- **Trading for injured players** on reserve lists (real teams sometimes do).
- AI teams' trade habits come from their GM's draft-day habit (more active either way); a separate
  "trades a lot" GM habit could be measured from real data later.
- **Found, not caused by trades (sent to the main session):** AI teams drift over the cap in the later
  regular season (also with AI trades off); 1-3 teams over the cap in camp before final cuts.
