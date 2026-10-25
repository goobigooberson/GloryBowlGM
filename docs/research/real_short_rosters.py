"""How often real NFL teams carry fewer than 53, and how big their practice squads run
(nflverse weekly rosters, regular season). Oct 25, 2026: the target for AI teams that play
short at the cap (transactions.SHORT_AT_CAP, tools/scoreboard.py fa.short_*).

The 53: players listed ACT or INA in a game week. Elevated practice squad players are listed
ACT that week, so a player ACT this week and DEV (practice squad) the week before and after
is counted as an elevation and left out.

    python docs/research/real_short_rosters.py

Result (Oct 25): 2022-25, team-weeks with 52 or fewer 5.5 / 4.2 / 4.6 / 3.9% (avg 4.6%),
51 or fewer 0.9 / 0.2 / 0.6 / 0.4% (0.5%), 50 or fewer never (the fewest: 51). 2020-21, with
COVID reserve lists: 11-20% under 53, as few as 41. Practice squads (DEV): average 15.0-15.4,
a full 16 in 20-27% of team-weeks, 14-15 in about half.
"""
import collections
import csv
import gzip
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent / "tools" / "data" / "nflverse" / "weekly_rosters"


def season(year):
    rows = [r for r in csv.DictReader(gzip.open(BASE / f"roster_weekly_{year}.csv.gz", "rt", encoding="utf-8"))
            if r["game_type"] == "REG"]
    status = {(r["team"], int(r["week"]), r["gsis_id"]): r["status"] for r in rows}
    weeks = collections.defaultdict(list)
    for (t, w, pid), s in status.items():
        weeks[(t, w)].append((pid, s))
    on53, ps = collections.Counter(), collections.Counter()
    for (t, w), players in weeks.items():
        on = [pid for pid, s in players if s in ("ACT", "INA")]
        elevated = [pid for pid in on if status.get((t, w - 1, pid)) == "DEV" and status.get((t, w + 1, pid)) == "DEV"]
        on53[len(on) - len(elevated)] += 1
        ps[sum(1 for _pid, s in players if s == "DEV")] += 1
    return on53, ps


def main():
    for year in range(2018, 2026):
        on53, ps = season(year)
        n = sum(on53.values())

        def share(f):
            return 100 * sum(c for k, c in on53.items() if f(k)) / n
        avg_ps = sum(k * c for k, c in ps.items()) / sum(ps.values())
        print(f"{year}: {n} team-weeks; 52 or fewer {share(lambda k: k < 53):.1f}%, 51 or fewer "
              f"{share(lambda k: k <= 51):.1f}%, 50 or fewer {share(lambda k: k <= 50):.1f}% (fewest {min(on53)}); "
              f"practice squad average {avg_ps:.1f}")


if __name__ == "__main__":
    main()
