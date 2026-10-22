# tools/nfl_retention.py
# How often a real NFL player is still in the league the next season, by
# position and age. Injury studies report "return to play" rates that mix
# the injury's effect with normal turnover (many careers end every year);
# this gives the normal rate to compare against.
#
# Data: tools/data rosters (1999-2025, season rosters with birth dates) and
# snap counts (2013-2025). A player counts in season n if he played 25%+ of
# his team's snaps in the games he played (6+ games): a real contributor, like
# the players in the injury studies. "Back" = he plays a regular-season snap
# the next season (snap counts 2013-2025).
#
# Run from the project folder:  python tools/nfl_retention.py

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aging_curves import rows, num, GROUP, OFFENSE, load_people  # noqa: E402

BANDS = [(0, 25, "under 25"), (25, 28, "25-27"), (28, 31, "28-30"), (31, 99, "31+")]


def main():
    by_pfr, _by_gsis, by_name = load_people()
    birth = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("pfr_id") and r.get("birth_date"):
                birth[r["pfr_id"]] = int(r["birth_date"][:4])
    played = defaultdict(dict)      # season -> {pfr id: (group, share per game played, games)}
    for year in range(2013, 2026):
        acc = defaultdict(lambda: [0.0, 0, None])
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            grp = GROUP.get(r["position"])
            if grp is None:
                continue
            pct = num(r["offense_pct"]) if grp in OFFENSE else num(r["defense_pct"])
            if grp in ("K", "P", "LS"):
                pct = 1.0 if num(r["st_snaps"]) > 0 else 0.0
            a = acc[r["pfr_player_id"]]
            if pct > 0:
                a[0] += pct
                a[1] += 1
            a[2] = grp
        for pid, (tot, games, grp) in acc.items():
            played[year][pid] = (grp, tot / games if games else 0.0, games)
    stats = defaultdict(lambda: [0, 0])
    for year in range(2013, 2025):
        nxt = played[year + 1]
        for pid, (grp, share, games) in played[year].items():
            if games < 6 or share < 0.25 or pid not in birth:
                continue
            age = year - birth[pid]
            band = next(lbl for lo, hi, lbl in BANDS if lo <= age < hi)
            g = {"OLB": "LB", "ILB": "LB", "FB": "RB", "NT": "DT"}.get(grp, grp)
            s = stats[(g, band)]
            s[0] += 1
            s[1] += pid in nxt and nxt[pid][2] > 0
            s2 = stats[(g, "all")]
            s2[0] += 1
            s2[1] += pid in nxt and nxt[pid][2] > 0
    print("Real NFL: share of contributors (25%+ of snaps, 6+ games) who play again the next season")
    print(f"{'pos':5}" + "".join(f"{lbl:>12}" for _lo, _hi, lbl in BANDS) + f"{'all':>12}")
    for g in ["QB", "RB", "WR", "TE", "T", "G", "C", "DE", "DT", "LB", "CB", "S", "K", "P"]:
        cells = []
        for _lo, _hi, lbl in BANDS + [(0, 0, "all")]:
            n, back = stats.get((g, lbl), (0, 0))
            cells.append(f"{100 * back / n:5.0f}% ({n:4})" if n >= 20 else f"{'-':>12}")
        print(f"{g:5}" + "".join(f"{c:>12}" for c in cells))


if __name__ == "__main__":
    main()
