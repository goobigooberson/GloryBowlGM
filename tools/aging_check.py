# tools/aging_check.py
# How long players stay good, real vs simulated, on the same yardstick:
# a player who's a regular this season (half or more of his side's snaps in
# the games he played, 8+ games), what's his chance he's still a regular next
# season, by position group and pro season? That curve shows both WHEN
# players fade and how unevenly (if everyone dropped on schedule, it would
# fall off a cliff at one season instead of sliding).
# Also: among regulars, how much his share moves from one season to the next
# (the spread), by career stage.
#   python tools/aging_check.py real
#   python tools/aging_check.py sim <file.jsonl> [more...]   (from tools/injury_careers_sim.py)

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import pstdev

sys.path.insert(0, str(Path(__file__).resolve().parent))

BANDS = [(1, 2, "1-2"), (3, 4, "3-4"), (5, 6, "5-6"), (7, 8, "7-8"), (9, 10, "9-10"), (11, 99, "11+")]
GROUPS = ["QB", "RB", "WR/TE", "OL", "DL", "LB", "DB"]


def curves(rows):
    """rows: {(key, season): (group, season number, share, games)}."""
    stay = defaultdict(lambda: [0, 0])
    moves = defaultdict(list)
    for (pid, y), (pg, sn, sh, g) in rows.items():
        if sh < 0.5 or g < 8:
            continue
        nxt = rows.get((pid, y + 1))
        band = next(lbl for lo, hi, lbl in BANDS if lo <= sn <= hi)
        s = stay[(pg, band)]
        s[0] += 1
        if nxt and nxt[2] >= 0.5 and nxt[3] >= 8:
            s[1] += 1
        if nxt and nxt[3] >= 4:
            moves[(pg, band)].append(nxt[2] - sh)
    return stay, moves


def show(title, stay, moves):
    print(title)
    print("  Still a regular next season (regulars this season), by pro season:")
    print(f"  {'pos':7}" + "".join(f"{lbl:>10}" for _lo, _hi, lbl in BANDS))
    for pg in GROUPS:
        cells = []
        for _lo, _hi, lbl in BANDS:
            n, k = stay.get((pg, lbl), (0, 0))
            cells.append(f"{100 * k / n:5.0f}%({n:3})" if n >= 15 else f"{'-':>10}")
        print(f"  {pg:7}" + "".join(f"{c:>10}" for c in cells))
    print("  Spread of the change in snap share, season to season (regulars who played again), pts:")
    for pg in GROUPS:
        cells = []
        for _lo, _hi, lbl in BANDS:
            m = moves.get((pg, lbl), [])
            cells.append(f"{100 * pstdev(m):9.1f}" if len(m) >= 15 else f"{'-':>9}")
        print(f"  {pg:7}" + "".join(f"{c:>10}" for c in cells))


def main():
    if sys.argv[1] == "real":
        from injury_careers_real import season_shares
        rows = {(pid, y): v for (pid, y), v in season_shares().items() if y not in (2020, 2021)}
        # Next season 2020/2021 (COVID opt-outs, reserve lists): leave those transitions out.
        rows_next = {k: v for k, v in rows.items()}
        for (pid, y) in list(rows_next):
            if y in (2019,):
                rows_next.pop((pid, y))
        show("REAL NFL 2013-2025", *curves(rows_next))
    else:
        rows = {}
        for fn in sys.argv[2:]:
            tag = Path(fn).stem
            for line in open(fn):
                r = json.loads(line)
                rows[(tag + str(r["pid"]), r["season"])] = (r["pg"], r["sn"], r["share"], r["games"])
        show("SIM", *curves(rows))


if __name__ == "__main__":
    main()
