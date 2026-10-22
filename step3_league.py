# step3_league.py
# Step 3 test: builds a new 32-team league, saves it to saves/league.db,
# loads it back from the file, and prints a summary.
# Run it from the terminal (in the project folder) with:   python step3_league.py
#
# Each run makes a NEW league and replaces the saved one.

import random
from collections import Counter
from datetime import date
from statistics import mean

from engine import formatting as fmt
from engine import positions as pos
from engine.database import save_league, load_league
from engine.league import create_league
from engine.teams import ROSTER_TEMPLATE, STARTERS

SAVE_FILE = "saves/league.db"


def depth_sorted(players, position):
    """A position group, best first (a stand-in for depth charts, which come later)."""
    return sorted([p for p in players if p.position == position],
                  key=lambda p: p.overall(), reverse=True)


def starters_of(players):
    result = []
    for position, count in STARTERS.items():
        result += depth_sorted(players, position)[:count]
    return result


def print_standings_style_table(league):
    print()
    print("=" * 84)
    print("  TEAMS  (Starter rating = average overall of the 22 starters plus K and P)")
    print("=" * 84)
    for conference in ["Eastern", "Western"]:
        divisions = []
        for t in league.teams:
            if t.conference == conference and t.division not in divisions:
                divisions.append(t.division)
        for division in divisions:
            print(f"\n  {conference} Conference - {division} Division")
            print(f"    {'Team':<28}{'Starters':>18}   {'Best player':<34}")
            for t in [t for t in league.teams if t.division == division and t.conference == conference]:
                roster = league.team_players(t.id)
                start_avg = round(mean(p.overall() for p in starters_of(roster)))
                # Kickers and punters left out: their ratings aren't comparable.
                best = max([p for p in roster if p.position not in ("K", "P")],
                           key=lambda p: p.overall())
                best_txt = f"{best.name}, {best.position} ({best.overall()})"
                print(f"    {t.name:<28}{fmt.skill(start_avg):>18}   {best_txt:<34}")


def print_roster(league, team):
    today = date(league.season, 9, 1)
    roster = league.team_players(team.id)
    print()
    print("=" * 104)
    print(f"  ROSTER: {team.name}  ({len(roster)} players)")
    print("=" * 104)
    print(f"  {'Pos':<5}{'Name':<22}{'Age':>4}{'Exp':>5}{'Size':>16}  {'Overall':<17}{'Potential':>10}  {'Draft':<7}{'College':<20}")
    for position in ROSTER_TEMPLATE:
        for i, p in enumerate(depth_sorted(roster, position)):
            starter = "*" if i < STARTERS[position] else " "
            exp = "R" if p.experience == 0 else str(p.experience)
            draft = "UDFA" if p.draft_round == 0 else f"Rd {p.draft_round}"
            print(f" {starter}{p.position:<5}{p.name:<22}{p.age(today):>4}{exp:>5}"
                  f"{fmt.size(p.height, p.weight):>16}  {fmt.skill(p.overall()):<17}"
                  f"{p.overall('potential'):>10}  {draft:<7}{p.college:<20}")
    print("  * = starter     Exp: R = rookie     Draft: round he was picked; UDFA = undrafted free agent")


def print_league_summary(league):
    signed = [p for p in league.players if p.id in league.rosters]
    today = date(league.season, 9, 1)
    print()
    print("=" * 84)
    print("  LEAGUE BALANCE CHECK")
    print("=" * 84)
    words = Counter(fmt.skill_word(p.overall()) for p in signed)
    print(f"  {len(signed)} players on rosters. Overall ratings:")
    for _floor, word in fmt.SKILL_WORDS:
        n = words.get(word, 0)
        print(f"    {word:<11}{n:>6}  ({100 * n / len(signed):4.1f}%)  {'#' * round(60 * n / len(signed))}")
    starters = [p for t in league.teams for p in starters_of(league.team_players(t.id))]
    print(f"\n  Average starter: {fmt.skill(round(mean(p.overall() for p in starters)))}")
    print(f"  Average age: {mean(p.age(today) for p in signed):.1f}     "
          f"Rookies: {sum(p.experience == 0 for p in signed)}")

    print("\n  Best player at each position:")
    for position in ROSTER_TEMPLATE:
        best = depth_sorted(signed, position)[0]
        team = league.team(league.rosters[best.id])
        print(f"    {position:<5}{best.name:<22}{team.abbrev:<6}{fmt.skill(best.overall())}")

    free = sorted(league.free_agents(), key=lambda p: p.overall(), reverse=True)
    print(f"\n  Free agents available: {len(free)}. Best five:")
    for p in free[:5]:
        print(f"    {p.position:<5}{p.name:<22}age {p.age(today):<4}{fmt.skill(p.overall())}")

    gens = [p for p in league.players if p.generational]
    print(f"\n  Generational players in this league: {len(gens)}")
    print("  (Names hidden: in the real game this is secret. Shown here for testing only.)")
    for p in sorted(gens, key=lambda p: p.position):
        exp = "rookie" if p.experience == 0 else f"{p.experience} yrs"
        draft = "undrafted" if p.draft_round == 0 else f"round {p.draft_round}"
        print(f"    {p.position:<5}{exp:<10}now {fmt.skill(p.overall()):<17} potential {p.overall('potential'):<4}"
              f"drafted {draft}, {p.college}")


if __name__ == "__main__":
    print("Building a new league...")
    new_league = create_league(season=2026)
    save_league(new_league, SAVE_FILE)
    print(f"Saved to {SAVE_FILE}. Loading it back from the file...")
    league = load_league(SAVE_FILE)

    print_standings_style_table(league)
    print_roster(league, random.choice(league.teams))
    print_league_summary(league)
    print()
