# tools/playing_hurt.py
# Do players play worse when they play while listed Questionable? Each
# player is compared with himself: his per-play results (EPA, expected points
# added) in games he played listed Questionable vs his other games the same
# season. Real data: nflverse play-by-play 2016-2025 joined to weekly injury
# reports.
#
# Run from the project folder:  python tools/playing_hurt.py

import csv
import gzip
from collections import defaultdict
from pathlib import Path
from statistics import mean

DATA = Path(__file__).resolve().parent / "data"
import sys
METRIC = sys.argv[1] if len(sys.argv) > 1 else "epa"     # or yards_gained
ROLES = {"passer_player_id": ("QB dropbacks", "pass_attempt"), "rusher_player_id": ("RB carries", "rush_attempt"),
         "receiver_player_id": ("WR/TE targets", "pass_attempt")}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    diffs = defaultdict(list)        # role -> [(Q-game EPA per play - other games), weight]
    for year in range(2016, 2026):
        q = defaultdict(set)         # gsis id -> weeks listed Questionable
        with gzip.open(DATA / f"injuries_{year}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["game_type"] == "REG" and r["report_status"] == "Questionable":
                    q[r["gsis_id"]].add(int(r["week"]))
        per = defaultdict(lambda: defaultdict(list))   # (role, id) -> week -> [epa]
        path = DATA / "nflverse" / "pbp" / f"play_by_play_{year}.csv.gz"
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("season_type") != "REG":
                    continue
                epa = num(r.get(METRIC))
                if epa is None:
                    continue
                wk = int(r["week"])
                for col, (role, _flag) in ROLES.items():
                    pid = r.get(col)
                    if pid:
                        per[(role, pid)][wk].append(epa)
        for (role, pid), weeks in per.items():
            qw = [w for w in weeks if w in q.get(pid, ())]
            ow = [w for w in weeks if w not in q.get(pid, ())]
            qplays = [e for w in qw for e in weeks[w]]
            oplays = [e for w in ow for e in weeks[w]]
            if len(qplays) >= 10 and len(oplays) >= 60:
                diffs[role].append((mean(qplays) - mean(oplays), len(qplays)))
        print(f"{year} done", flush=True)
    print(f"\nPlaying while Questionable vs the same player's other games ({METRIC} per play):")
    for role, lst in diffs.items():
        w = sum(n for _d, n in lst)
        avg = sum(d * n for d, n in lst) / w
        print(f"  {role:14} players {len(lst):4}  Q-game plays {w:6}  difference {avg:+.3f} per play")


if __name__ == "__main__":
    main()
