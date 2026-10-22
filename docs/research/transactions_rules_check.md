# Rules check: engine/transactions.py vs current NFL rules (2024-26)

Checked Oct 20, 2026 by the research session. Read-only: nothing in the project was edited.
Sources are mostly secondary (team blogs, AP, Wikipedia); the official CBA / NFL Ops pages
were not fetchable (403/404). Confidence is given per item.

## Matches (no change needed)

| Constant / rule | Code | Real | Confidence |
|---|---|---|---|
| PRACTICE_SQUAD_SIZE | 16 | 16 (+1 exempt international spot, see below) | high |
| PRACTICE_SQUAD_VETERANS | 6 any experience | 6 with no accrued-season limit (since 2022) | high |
| PRACTICE_SQUAD_MAX_EXPERIENCE | other 10: 2 seasons or fewer | other 10: 2 or fewer *accrued* seasons | high (see nuance 6) |
| ELEVATIONS_PER_GAME | 2 | 2 (revert to PS automatically, no waivers) | high |
| ELEVATIONS_PER_PLAYER | 3 | 3 per season, then must be signed to the 53 | high |
| IR_MIN_GAMES | 4 | 4 games (since 2022; 3 in 2020-21) | high |
| PUP_MIN_GAMES | 4 | reserve/PUP misses at least the first 4 games | high |
| PUP returns don't use IR returns | yes | yes (IR designations only) | medium-high |
| WAIVER_EXPERIENCE | <4 seasons -> waivers | fewer than 4 accrued seasons -> waivers; vested vets free | high (before the trade deadline, see 3) |
| Released PS player | free agent | free agent (PS players are not waived) | high |
| PS injured list ("PSIR") | yes | yes (practice squad/injured) | high |
| Reserve/future at season end | PS -> 90-man roster | yes, that's what teams do | high |

## Mismatches, most important first

1. **Game-day actives: code 46, real 48.** `roster_rules.ACTIVE_LIMIT = 46`, and elevated
   players are added to the pool but the actives stay capped at 46 (`gameteam.py:79`).
   Real rule (2020 CBA on): up to **48 active if at least 8 are offensive linemen, else 47**;
   the 2 elevations are how a team gets to 55 bodies with 48 dressed, but a team can dress
   48 from its 53 too. nflverse weekly rosters 2022-25: **48.0 ACT and 6.3 INA per team-week**
   every season. Plus the **emergency 3rd QB** (2023+): a 3rd QB from the 53 (not an elevated
   player) can be designated and doesn't count against the 48; he may play only if both other
   QBs are out (rarely used).
   *Caution:* the sim was calibrated with 46 actives. Changing this changes who plays
   (more special-teams/rotation bodies), so it's a stats-affecting change: run the realism
   tools before/after per CLAUDE.md, and ask Blake first.

2. **Waiver order before week 4.** Code: worst record first, or plain team-list order when
   `records` is None (preseason, final cuts, weeks 1-3). Real: **from the final cutdown through
   week 3, priority = that year's original draft order** (trades ignored); **from week 4,
   current-season record** (worst first), ties by strength of schedule (code ties by team id).
   With the placeholder draft (worst-to-first) the draft order is just last season's
   standings reversed, so this is easy to get.

3. **Vested veterans after the trade deadline.** Code: 4+ season players are always free
   agents when released. Real: **from the trade deadline to the end of the regular season,
   every released player goes through waivers**, vested or not (NFL Ops waiver overview;
   e.g. Nov 1 onward in 2023). Needs a trade-deadline week constant (real: Tuesday after
   week 8 or 9; e.g. Nov 5, 2024 = after week 9; Nov 4, 2025 = after week 9).

4. **IR at final cuts / before week 1.** Code places 4+ week injuries on IR at "Final cuts"
   (`lab_preseason` -> `weekly(..., 0, "Final cuts")` with preseason False) and they can come
   back after 4 games. Real: a player placed on IR **at or before the final cutdown is out for
   the season**, except that **each team may designate up to 2 players** placed on IR at the
   cutdown to return (those count against the 8). Real teams dodge this by keeping the player
   on the initial 53 and moving him to IR a day later (the "IR shuffle"), which is fully legal
   and returnable. So either (a) do IR moves for cutdown-injured players in week 1 (after
   cuts) as real teams do, or (b) model the 2 cutdown designations. Real week-1 split (your
   own measurement): 4.8 IR, 0.7 IR-designated-to-return, so most week-1 IR players never return.

5. **IR returns count: 8 including playoffs?** Code: 8 per season, playoffs included.
   Sources disagree: some say 8 in the regular season **plus 2 more for playoff teams (10)**;
   others 8 total. Since 2022 the rule I'm most confident of: 8 per season, and playoff teams
   get 2 extra. Medium confidence; worth a check against the 2026 NFL Ops roster rules page.
   Also not modeled (fine to skip): the **21-day practice window** (once a player starts
   practicing he must be activated within 21 days or he reverts to season-ending IR; the
   designation is used even if he never returns), and from 2026 PUP players may start
   practicing after week 2 (still miss 4 games).

6. **Practice squad eligibility nuance.** Code counts `experience` (seasons). Real counts
   **accrued seasons** (6+ games on full pay status: active, inactive, IR or PUP), so a player
   who spent a year mostly on a practice squad hasn't accrued it. In this game `experience`
   probably counts every season in the league, so PS-eligible young players run out a little
   early. Small; only matters if Blake wants it exact. (Older rule bits like "one accrued
   season but fewer than 9 games active" are folded into the 2-season bucket now; sources
   conflict, low importance.)

7. **International Player Pathway 17th spot.** Real: every team may carry a 17th PS player if
   he's an IPP international player (exempt; since 2024 he can be elevated up to 3 times). The
   game has no international players, so skipping it is reasonable; mention it in the
   build log as a deliberate cut.

8. **Practice squad poaching (missing mechanism).** Real: any team may sign another team's
   PS player **to its 53** at any time (not to its own PS), and must keep him on the 53 (or
   pay him) for **3 game weeks**. nflverse weekly rosters: a PS player moves straight to
   another team's 53 **0.75-1.06 times per team-season (2022-25)**. The code only promotes a
   team's own PS players; AI teams never look at other squads, and your PS players can't be
   taken. Adds realism and a reason to promote your best PS player.

9. **Waiver timing.** Code processes last week's waived players during the next week's moves
   (`w["cal"] < cal`), so a waived player sits a full week. Real: 24-hour claim period (cuts
   by 4 pm ET, awarded next day), so a claimed player can play that weekend. Minor.

10. **PS pay (for the free agency/cap step).** PS players are paid weekly for 18 weeks, no
    bonuses or guarantees: 2026 minimum $13,750/week for 2-or-fewer accrued seasons,
    veteran scale $18,350-$22,850/week. PS salaries count against the salary cap.

## Things that are judgment calls, not rule mismatches (look fine)

- AI 1 claim a week, CLAIM_MARGIN 9: real teams can claim more but rarely do; your own
  measurement (~1.4 team-to-team moves per team-season) is the right target.
- IR_AT_WEEKS 4: matches the minimum; real teams also IR some 3-week injuries when the roster
  spot matters, and keep some 4-6 week stars on the 53. Fine.
- PS_TEMPLATE: no K/P/LS on PS is close to real (a few teams carry a K or LS). Could measure
  from weekly rosters (status DEV by position) if wanted.

## Sources
- Windy City Gridiron, 2025 practice squad rules: https://www.windycitygridiron.com/chicago-bears-roster/96946/2025-nfl-practice-squad-rules-and-chicago-bears-news-and-rumor-tracker
- NBC Sports Boston, 2025 cutdown/practice squad rules: https://www.nbcsportsboston.com/news/sports/nfl/nfl-roster-cutdown-day-2025-deadline-date-practice-squad-rules/
- Wikipedia, Practice squad: https://en.wikipedia.org/wiki/Practice_squad
- FantasyNerds, PS eligibility/pay/poaching (Aug 2026): https://fantasynerds.com/news/story/2026/08/31/nfl-practice-squad-rules-eligibility-pay-and-poaching-explained-1611683
- Pride of Detroit, IR / designated to return / NFI / PUP: https://www.prideofdetroit.com/detroit-lions-analysis/140149/nfl-roster-cuts-rules-how-ir-to-return-nfi-pup-lists-work
- Arrowhead Pride, 2024 IR tweaks: https://www.arrowheadpride.com/2024/6/21/24183076/nfl-tweaks-injured-reserve-rules-for-2024-season
- AtoZ Sports, 2026 PUP practice-window change: https://atozsports.com/nfl/green-bay-packers-news/micah-parsons-should-be-salivating-nfl-rules-pup/
- CBS Sports, 2026 waiver order: https://cbssports.com/nfl/news/nfl-waiver-order-2026
- SI, waivers after the trade deadline: https://www.si.com/nfl/chargers/onsi/nfl-wavier-wire-order-new-nfl-rules-start-trade-deadline-chargers
- PFR (ProFootballRumors) 2023 calendar (all players on waivers Nov 1 on): https://profootballrumors.com/2023/06/key-dates-remaining-on-2023-nfl-calendar
- Wikipedia, Third quarterback rule: https://en.wikipedia.org/wiki/Third_quarterback_rule
- Fox Sports / AP, emergency QB usage (2025): https://www.foxsports.com/articles/nfl/nfl-teams-dont-use-gameday-roster-flexibility-with-emergency-qbs-as-often-as-one-would-think
- Data: tools/data/nflverse/weekly_rosters 2022-25 (48.0 ACT / 6.3 INA per team-week; PS-to-other-team's-53 moves).
