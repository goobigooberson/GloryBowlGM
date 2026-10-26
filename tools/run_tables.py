# tools/run_tables.py
# Rebuilds engine/sim/data.py's designed-run (Oct 25) and passing (Oct 26) yards tables from real NFL regular seasons
# 2023-2025 (nflverse play-by-play), at fine quantile points (data.Q_FINE_STEPS: every 1%, plus
# the rare ends). The other tables use 27 points, and straight lines between them blur whole-yard
# outcomes: between the 85th percentile of open runs (8 yards) and the 90th (11 yards) they spread
# the mass evenly, so 9-yard runs came up 1.2% of the time on 1st & 10 vs real 3.5%, and 2nd & 1
# and 3rd & 1 too rarely.
#   Q_RUN_OPEN           backs' (any non-QB) designed runs, outside the 20, not 1-2 to go
#   Q_RUN_SHORT_YARDAGE  the same with 1-2 to go
#   Q_QB_RUN             designed QB runs (keepers, read options, draws) outside the 20, not sneaks
#                        (1 to go up the middle: the sim's own play)
# Inside the 20 the sim shortens runs itself (tuning.RUN_FIELD). Botched snaps and handoffs
# ("aborted" plays) are left out: the sim plays those separately (tuning.FUMBLE_EXCHANGE).
# The passing tables too (Oct 26, from the tackles-for-loss check: the coarse tables put too many
# throws behind the line, receivers 9.6% of targets 3+ yards behind vs real 6.3%, and too few at
# 1-4 yards, 14.4% vs 17.5%, so catches dropped for a loss ran 0.67 a team game vs real 0.41):
#   Q_AIR_WR / Q_AIR_TE / Q_AIR_RB   targeted air yards by position on routes that aren't screens
#                                    (FTN charting marks screens), the whole field. Until Oct 26 these
#                                    were all targets, screens included, so regular routes went behind
#                                    the line 3x as often as real (receivers 8.5% vs 2.5%) and the
#                                    screen play added its own on top.
#   Q_SCREEN_AIR_RB / _WR            air yards on real screens: to backs / to receivers and tight ends
#   Q_YAC_SCREEN                     yards after the catch on real screens (blockers set up), outside the 20
#   Q_YAC_BEHIND / _SHORT / _INTER   yards after the catch by air yards (0 or less / 1-9 / 10-19) on
#                                    other passes, outside the 20. Until Oct 26 screens were in
#                                    Q_YAC_BEHIND. Q_YAC_DEEP stays as it is.
#
#   python tools/run_tables.py          # prints the tables
#   python tools/run_tables.py --write  # writes them into engine/sim/data.py
#
# Reads only the real data (and, with --write, data.py).

import csv
import gzip
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data" / "nflverse"
DATA_PY = ROOT / "engine" / "sim" / "data.py"
YEARS = (2023, 2024, 2025)
OPEN_FROM = 20                # yards from the goal line
STEPS = [0.001, 0.005] + [round(0.01 * i, 2) for i in range(1, 100)] + [0.995, 0.999]


def runs():
    out = {"Q_RUN_OPEN": [], "Q_RUN_SHORT_YARDAGE": [], "Q_QB_RUN": []}
    for yr in YEARS:
        with gzip.open(DATA / "stats_player" / f"stats_player_reg_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            pos = {r["player_id"]: r["position"] for r in csv.DictReader(f)}
        with gzip.open(DATA / "pbp" / f"play_by_play_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["season_type"] != "REG" or r["play_type"] != "run" or r["qb_scramble"] == "1":
                    continue
                if r.get("aborted_play") == "1" or float(r["yardline_100"] or 50) <= OPEN_FROM:
                    continue
                togo = float(r["ydstogo"] or 10)
                y = float(r["rushing_yards"] or 0)
                if pos.get(r["rusher_player_id"]) == "QB":
                    if togo <= 1 and r["run_location"] == "middle":
                        continue      # sneak
                    out["Q_QB_RUN"].append(y)
                else:
                    out["Q_RUN_SHORT_YARDAGE" if togo <= 2 else "Q_RUN_OPEN"].append(y)
    return out


def screens(yr):
    """FTN charting: {(nflverse game id, play id): is it a screen pass}."""
    with gzip.open(DATA / "ftn_charting" / f"ftn_charting_{yr}.csv.gz", "rt", encoding="utf-8") as f:
        return {(r["nflverse_game_id"], r["nflverse_play_id"]): r["is_screen_pass"].lower() in ("true", "1")
                for r in csv.DictReader(f)}


def passes():
    out = {k: [] for k in ("Q_AIR_WR", "Q_AIR_TE", "Q_AIR_RB", "Q_SCREEN_AIR_RB", "Q_SCREEN_AIR_WR",
                           "Q_YAC_SCREEN", "Q_YAC_BEHIND", "Q_YAC_SHORT", "Q_YAC_INTER")}
    for yr in YEARS:
        with gzip.open(DATA / "stats_player" / f"stats_player_reg_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            pos = {r["player_id"]: r["position"] for r in csv.DictReader(f)}
        scr = screens(yr)
        with gzip.open(DATA / "pbp" / f"play_by_play_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["season_type"] != "REG" or r["play_type"] != "pass" or not r["air_yards"] or not r["receiver_player_id"]:
                    continue
                air = float(r["air_yards"])
                p = {"FB": "RB"}.get(pos.get(r["receiver_player_id"]), pos.get(r["receiver_player_id"]))
                screen = scr.get((r["game_id"], str(int(float(r["play_id"])))))
                if p in ("WR", "TE", "RB") and screen is not None:
                    if screen:
                        out["Q_SCREEN_AIR_RB" if p == "RB" else "Q_SCREEN_AIR_WR"].append(air)
                    else:
                        out["Q_AIR_" + p].append(air)
                if r["complete_pass"] == "1" and float(r["yardline_100"] or 50) > OPEN_FROM and air <= 19                         and screen is not None:
                    k = "Q_YAC_SCREEN" if screen else (
                        "Q_YAC_BEHIND" if air <= 0 else ("Q_YAC_SHORT" if air <= 9 else "Q_YAC_INTER"))
                    out[k].append(float(r["yards_after_catch"] or 0))
    return out


def table(v):
    v = sorted(v)
    n = len(v)
    out = []
    for p in STEPS:
        x = p * (n - 1)
        i = int(x)
        out.append(round(v[i] + (v[min(n - 1, i + 1)] - v[i]) * (x - i), 2))
    return out


def main():
    lines = {"Q_FINE_STEPS": f"Q_FINE_STEPS = {STEPS}"}
    for name, v in list(runs().items()) + list(passes().items()):
        lines[name] = f"{name} = {table(v)}"
        print(f"# {name}: {len(v)} plays, {sum(v) / len(v):.2f} yards each")
    for s in lines.values():
        print(s)
    if "--write" in sys.argv:
        src = DATA_PY.read_bytes().decode("utf-8")
        for name, s in lines.items():
            src, k = re.subn(rf"^{name} = \[.*\]$", s, src, flags=re.M)
            if k != 1:
                raise SystemExit(f"{name}: expected one line in data.py, found {k}")
        DATA_PY.write_bytes(src.encode("utf-8"))
        print(f"written to {DATA_PY}")


if __name__ == "__main__":
    main()
