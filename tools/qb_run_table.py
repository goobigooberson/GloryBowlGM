# tools/qb_run_table.py
# Rebuilds engine/sim/data.py's Q_QB_RUN (Oct 25): yards on a designed QB run (keepers, read
# options, QB draws), real NFL regular seasons 2023-2025 (nflverse play-by-play), at the sim's
# quantile points (data.Q_STEPS). Sneaks (1 to go, up the middle) have their own play in the
# sim and are left out, as before. Two things changed from the old table:
#   - Open field only (outside the 20), like the running backs' table: the sim shortens runs near
#     the goal line itself (tuning.RUN_FIELD), so the old whole-field table shortened red-zone
#     keepers twice and diluted the rest (game keepers ran 0.6-1.5 yards short in every zone,
#     backs' runs matched real in every zone).
#   - Botched snaps and handoffs ("aborted" plays, ~16% of QB runs) are left out. The sim plays
#     those separately (tuning.FUMBLE_EXCHANGE, credited to the QB as a run of 0 to -3 yards, as
#     the NFL scores them), so they counted twice.
#
#   python tools/qb_run_table.py        # prints the table; paste it into engine/sim/data.py
#
# Reads only the real data; changes nothing.

import csv
import gzip
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.sim import data  # noqa: E402

DATA = HERE / "data" / "nflverse"
YEARS = (2023, 2024, 2025)
OPEN_FROM = 20                # yards from the goal line


def qb_runs():
    out = []
    for yr in YEARS:
        with gzip.open(DATA / "stats_player" / f"stats_player_reg_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            pos = {r["player_id"]: r["position"] for r in csv.DictReader(f)}
        with gzip.open(DATA / "pbp" / f"play_by_play_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["season_type"] != "REG" or r["play_type"] != "run" or r["qb_scramble"] == "1":
                    continue
                if pos.get(r["rusher_player_id"]) != "QB" or r.get("aborted_play") == "1":
                    continue
                if float(r["ydstogo"] or 10) <= 1 and r["run_location"] == "middle":
                    continue          # sneak
                if float(r["yardline_100"] or 50) <= OPEN_FROM:
                    continue          # red zone: the sim's field squeeze handles it
                out.append(float(r["rushing_yards"] or 0))
    return out


def table(v):
    v = sorted(v)
    n = len(v)
    out = []
    for p in data.Q_STEPS:
        x = p * (n - 1)
        i = int(x)
        out.append(round(v[i] + (v[min(n - 1, i + 1)] - v[i]) * (x - i), 2))
    return out


if __name__ == "__main__":
    v = qb_runs()
    print(f"{len(v)} designed QB runs, {sum(v) / len(v):.2f} yards each")
    print("Q_QB_RUN =", table(v))
