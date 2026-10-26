# Void years and restructures: the real rules and how teams use them

Oct 26, 2026, for the game's void years (`engine/contracts.py`, `engine/free_agency.py` VOID_*).
Numbers the checks use: `real_void_years.json` (built by `void_years.py`, which lists every source).

## The rules (2020 CBA and how OverTheCap and team reporters describe them)

- **A void year** is a placeholder season added after a contract's real ones. It is never played:
  the contract voids automatically on a set date (often a few days after the Super Bowl, at the
  latest the start of the new league year) on a trivial condition, such as being on the roster.
  Its only purpose is accounting.
- **Proration:** a signing bonus (and any salary converted into a bonus) counts against the cap
  spread evenly over the contract's seasons, **at most 5**, and void years count as seasons. So a
  1-year deal with 4 void years spreads its bonus over 5 seasons. The most void years a deal can
  use is 5 minus its real seasons left.
- **When it voids**, every share of bonus sitting in void years speeds onto the cap of the league
  year that's starting: dead money, all at once (Kirk Cousins' $28.5M on the 2024 Vikings).
- **Extended first** (before the void date), the shares stay in their seasons on the new deal.
  OverTheCap books the void charge in advance because voiding happens "over 80% of the time".
- **Cut, traded or retired before then:** the void-year shares are bonus money still to come, so
  they speed up like any other (all this season before June 1; split this season / next after
  June 1 or a post-June 1 designation; a traded player's stays with the old team).
- **Restructures:** a team turns part of this season's base salary (above the minimum) into a
  bonus, spread over the seasons left, at most 5. A "maximum" restructure adds void years to
  spread it further; with void years even a player in his last season can be restructured
  (Cousins, March 2023; Mike Evans, 2024). Restructures can happen any time in the league year;
  during the season only the salary not yet paid can be converted (the weekly checks already paid
  are paid). Real teams also restructure right before trade deadlines to fit a player in.
- **Limits:** the 5-season proration limit; rookie contracts follow the rookie rules; a franchise
  tag is all base salary. In 2025 the commissioner talked about "looking into" void years, but no
  rule changed (Draft Network, May 2025).

## How teams use them (data)

- **Deals voiding a year:** 73 contracts were set to void in 2024 (OverTheCap, Jan 2024). 23 of
  32 teams had at least one; 9 had none (Bears, Colts, Chargers, Steelers, Broncos, Jaguars,
  Bengals, Cardinals, Rams).
- **Void money by team** (OverTheCap, April 2023, a year or more ahead, so it understates the
  final figures): 2024: 63 players at 22 teams, $274M (3.4% of the cap a team on average); the
  Saints 23.0% of their cap, the Vikings 18.2%, everyone else 8.6% or less. 2025: 67 players at 19
  teams, $406M (4.5%); the Eagles 21.1%, Cowboys 20.5%, Buccaneers 19.3%, Rams 14.7%, Saints 11.9%.
  The 2023 Buccaneers carried about $53M from voided deals (23.4% of the cap). So use is lumpy:
  a few teams lean on void years hard in a given year, about a third barely or never.
- **Restructures** (OverTheCap, 2013-20, money scaled to a $182M cap): 45% of team-years without
  one, 18% up to 3.6% of the cap, 17% 3.6-8.2%, 20% over 8.2%. Contenders do more: after 10+ win
  seasons 37.5% do none and 21.6% do 8.2%+; after 0-5 wins 59% none and 10.3% 8.2%+. Use rose
  sharply with the 2021 cap drop (73% of teams in 2020-21; 17 teams over $15M by June 2021,
  usually 6-8).
- **Dead money over the league year** (Spotrac team cap tables, already in `real_gm.json`):
  2013-20 about 9-12% of the cap a team on average, 2021 14.7%, **2022-25 16.8-18.6%** (the void
  year era), 90th percentile team 28-30%, 9-15 teams a year at 20%+, the most 34-44%.
  Caveat: Spotrac's dead cap may count a mid-season cut's already-paid salary differently from
  the game's charges, and the game's charges include practice squad elevation pay (about 1% of
  the cap), so compare the shape more than the last point.
- **In-season restructures:** no league-wide count found; only team reports (Cowboys, Dolphins,
  Bills before trade deadlines). The game's in-season use is judgment.

## What's data and what's judgment in the game

- Data: the rules above; deals voiding a year (73), teams with one (23), the void-money spread
  (about 4% a team, a few teams at 10-23%), the restructure spread by bucket, dead money levels.
- Judgment: how a team decides to lean on void years in a given year (its approach and its GM's
  cap style; `VOID_USE`, `VOID_CAP_K`), that a void deal's guarantee goes in as bonus
  (`VOID_BONUS`), the escape (every AI team restructures with void years when nothing else gets
  it under the cap), and in-season restructures to fit a traded player.

Sources: OverTheCap, "Creating Cap Space by Extending Players with Void Years" (Jan 29, 2024);
"Examining the Pros and Cons of Void Years for Salary Cap Relief" (Apr 19, 2023); "Looking at
Restructuring NFL Contracts" (June 10, 2021); "The Voidable Year and the Salary Cap"; Sumer
Sports, "Void Years Explained"; The Draft Network (May 29, 2025); Spotrac team cap tables 2013-25.
