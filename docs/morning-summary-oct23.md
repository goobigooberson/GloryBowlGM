# Morning summary: overnight Oct 22-23

You asked me to grind while you slept. Three side sessions built new systems in their
own files; I tuned the game, wired their work in, and checked everything against the
real NFL. Nothing is committed. Full details are in `docs/build-log.md` (the "Overnight
Oct 22-23" entries).

## What's new in the game

1. **Contracts, salary cap and free agency.** Every player has a real-style contract
   (pay by year, guarantees, signing bonus, dead money). The offseason now runs in the
   real NFL order: re-signings and franchise tags, free agency before the draft, the
   draft, free agency after it, then cuts. AI teams never go over the cap. Players change
   teams at about the real rate. Your staff re-signs your important players for now (until
   the contract screens exist), and anything bigger (restructures, cap cuts) comes to you
   as an Approve/Decline request on the Roster tab. Player reports show each contract.
2. **News tab.** Written stories (games, big performances, milestones, injuries and
   weekly injury reports, roster moves, playoff race, draft, retirements) and a social
   feed, all built from what actually happened in your league.
3. **Draft engine (Step 8).** See the draft section below (status at the end of the night).

## What I tuned (all checked with the realism tools)

- **Fumbles:** QBs fumbled too rarely and ball carriers 3x too often (the total was
  right, the split wasn't). Now QB fumbles, ball-carrier fumbles and fumbles lost all match
  the real numbers, and return fumbles finally count in the stats.
- **Corners:** the top corner always covered the top receiver (like a shadow corner on
  every team), which piled passes defensed on one player. Corners now play sides of the
  field most of the time. It's closer to real and still a little high.
- **Veterans piling up over the seasons:** found the cause. Rookie classes are made
  weaker on purpose (to keep ratings from creeping up), so rookies rarely won jobs and
  nobody churned. Free agency and new cut-down rules (teams keep their draft picks, and
  money matters) fixed most of it. The draft session's realistic rookie classes should
  finish the job.
- **Checked and fine:** kick returns (the game plays 2025 rules, where real teams return
  ~3.8 a game) and long field goals (60+ yarders at the real rate).

Stat realism stayed in its normal band all night: 22 of 282 measures outside the real
range on the latest run (it moves between ~19 and 26 from run to run). League averages
haven't moved.

## Decisions waiting for you

1. **Rust:** you asked for it (FOF8 had it), but real data shows none: players play just
   as well in their first game back from injury, and week 1 isn't sloppier than later
   weeks. Skip it, or add a small one for feel?
2. **Contracts/free agency** (`docs/free-agency-design.md`, "Open decisions"): how
   negotiating should work, whether a "staff runs contracts" switch makes sense, how much
   you see of other teams' offers, and more.
3. **News** (`docs/news-design.md`, "Choices waiting for Blake"): should the league have
   official awards (Player of the Week, MVP, All-Pro)? Fan tone? How much news?
4. **Draft** (`docs/draft-design.md`): scouting and the draft screens.
5. **Receivers rotate less than real** (the top WR plays ~91% of snaps vs ~81% real).
   The stats are right, because targets are already split like the real NFL, but more
   rotation would mean re-tuning the passing game. Worth doing?

## What to test

Start a **new game** (old saves work too, and get contracts when they load), sim a week,
and look at: the News tab, a player's contract in his report, the Roster tab's moves. Then
finish a season and press next season to watch free agency and the draft happen. The
Moves view lists every signing.
