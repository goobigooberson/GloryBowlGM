# step2_players.py
# Step 2 test: generates fictional players and prints them.
# Run it from the terminal (in the project folder) with:   python step2_players.py
#
# Each run makes brand-new players, so run it several times.
# This is a temporary text "screen". The real screens come later and will
# read the same player data.

from datetime import date
from statistics import mean

from engine import positions as pos
from engine import formatting as fmt
from engine.player import generate_player

SEASON = 2026
SEASON_START = date(SEASON, 9, 1)


def print_card(p):
    """Print one player the way a player screen would show him."""
    pos_name = pos.POSITIONS[p.position][0]
    print()
    print("=" * 74)
    print(f"  {p.name}  |  {pos_name} ({p.position})")
    print("=" * 74)
    exp = "Rookie" if p.experience == 0 else f"{p.experience} yrs"
    print(f"  Size:       {fmt.size(p.height, p.weight)}")
    print(f"  Age:        {p.age(SEASON_START)}   (born {p.birth_date:%b %d, %Y})")
    print(f"  Experience: {exp}")
    print(f"  College:    {p.college}")
    print(f"  Drafted:    {p.draft_text}")
    print(f"  Hometown:   {p.hometown}")
    print()
    print("  COMBINE")
    for drill in pos.COMBINE_DRILLS:
        label = fmt.DRILL_LABELS[drill][0]
        print(f"    {label:<24}{fmt.drill(drill, p.combine[drill])}")
    print(f"    {'Intelligence test':<24}{p.intel_test} out of 50")
    print(f"    {'Position drill':<24}{p.position_drill}")
    print()
    print("  PERSONALITY")
    for label, value in [("Loyalty", p.loyalty), ("Wants a winner", p.wants_winner),
                         ("Leadership", p.leadership), ("Volatility", p.volatility),
                         ("Popularity", p.popularity)]:
        print(f"    {label:<24}{fmt.trait(value)}")
    print()
    print("  RATINGS                   now / potential      (# = now, + = room to grow)")
    for skill, weight in pos.POSITIONS[p.position][1]:
        label = pos.SKILLS[skill][0]
        cur, potn = p.skills[skill]
        if skill in pos.HIDDEN_SKILLS:
            # Shown here only so you can check the generator. Scouts will never see it.
            label += " *"
        print(f"    {label:<26}{fmt.bar(cur, potn)}  {fmt.skill(cur):<16} / {potn}")
    ovr, ovr_pot = p.overall(), p.overall("potential")
    print(f"    {'OVERALL':<26}{fmt.bar(ovr, ovr_pot)}  {fmt.skill(ovr):<16} / {ovr_pot}"
          f"   ({p.developed_pct}% developed)")
    print("    * hidden rating: scouts will never see this; shown for testing only")


def _avg(values, places=0):
    """Average of the results that exist (skipped drills are left out)."""
    values = [v for v in values if v is not None]
    if not values:
        return "-"
    return f"{mean(values):.{places}f}"


def print_position_summary(players):
    """Averages by position, to compare against real combine data."""
    print()
    print("=" * 94)
    print(f"  POSITION AVERAGES ({len(players)} random players; skipped drills left out)")
    print("=" * 94)
    print(f"  {'Pos':<5}{'Count':>6}{'Height':>8}{'Weight':>8}{'40-yd':>8}{'Bench':>7}"
          f"{'Vert':>7}{'Broad':>12}{'3-cone':>8}{'Shuttle':>9}{'Overall':>9}")
    for code in pos.POSITIONS:
        group = [p for p in players if p.position == code]
        if not group:
            continue
        broad = [p.combine["broad"] for p in group if p.combine["broad"] is not None]
        broad_txt = fmt.jump(round(mean(broad))) if broad else "-"
        print(f"  {code:<5}{len(group):>6}"
              f"{fmt.height(round(mean(p.height for p in group))):>8}"
              f"{round(mean(p.weight for p in group)):>8}"
              f"{_avg([p.combine['forty'] for p in group], 2):>8}"
              f"{_avg([p.combine['bench'] for p in group]):>7}"
              f"{_avg([p.combine['vertical'] for p in group], 1):>7}"
              f"{broad_txt:>12}"
              f"{_avg([p.combine['cone'] for p in group], 2):>8}"
              f"{_avg([p.combine['shuttle'] for p in group], 2):>9}"
              f"{round(mean(p.overall() for p in group)):>9}")


if __name__ == "__main__":
    # Three example players: a rookie QB, a veteran WR, and one random player.
    print_card(generate_player("QB", experience=0, season_year=SEASON))
    print_card(generate_player("WR", experience=6, season_year=SEASON))
    print_card(generate_player(season_year=SEASON))

    # A big batch to check that the numbers look realistic overall.
    batch = [generate_player(season_year=SEASON) for _ in range(2000)]
    print_position_summary(batch)
    print()
