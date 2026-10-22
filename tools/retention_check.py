# tools/retention_check.py
# Real vs simulated: of the players who contributed this season (25%+ of his
# side's snaps in the games he played, 6+ games), how many play again next
# season, by position group and pro season. Too-short sim careers show here.
#   python tools/retention_check.py <sim1.jsonl> [more...]   (from tools/injury_careers_sim.py)

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
BANDS = [(1, 2, "1-2"), (3, 4, "3-4"), (5, 6, "5-6"), (7, 8, "7-8"), (9, 10, "9-10"), (11, 13, "11-13"),
         (14, 99, "14+")]
GROUPS = ["QB", "RB", "WR/TE", "OL", "DL", "LB", "DB"]


def table(rows, skip_next=()):
    out = defaultdict(lambda: [0, 0])
    for (pid, y), (pg, sn, sh, g) in rows.items():
        if sh < 0.25 or g < 6 or y in skip_next:
            continue
        band = next(lbl for lo, hi, lbl in BANDS if lo <= sn <= hi)
        for key in ((pg, band), (pg, "all")):
            out[key][0] += 1
            out[key][1] += (pid, y + 1) in rows
    return out


def show(title, t):
    print(title)
    print(f"  {'pos':7}" + "".join(f"{lbl:>11}" for _lo, _hi, lbl in BANDS) + f"{'all':>11}")
    for pg in GROUPS:
        cells = []
        for lbl in [b[2] for b in BANDS] + ["all"]:
            n, k = t.get((pg, lbl), (0, 0))
            cells.append(f"{100 * k / n:5.0f}%({n:4})" if n >= 15 else "-")
        print(f"  {pg:7}" + "".join(f"{c:>11}" for c in cells))


def main():
    from injury_careers_real import season_shares
    real = season_shares()
    last = max(y for _p, y in real)
    show("REAL NFL (played again next season)", table(real, skip_next=(2019, 2020, last)))
    rows = {}
    lasts = {}
    for fn in sys.argv[1:]:
        tag = Path(fn).stem
        for line in open(fn):
            r = json.loads(line)
            rows[(tag + "-" + str(r["pid"]), r["season"])] = (r["pg"], r["sn"], r["share"], r["games"])
            lasts[tag] = max(lasts.get(tag, 0), r["season"])
    rows_ok = {k: v for k, v in rows.items() if k[1] < lasts[k[0].split("-")[0]]}
    t = table({**rows_ok, **{k: v for k, v in rows.items() if k not in rows_ok}},
              skip_next=())
    # only count transitions whose next season exists in the file
    t2 = defaultdict(lambda: [0, 0])
    for (pid, y), (pg, sn, sh, g) in rows_ok.items():
        if sh < 0.25 or g < 6:
            continue
        band = next(lbl for lo, hi, lbl in BANDS if lo <= sn <= hi)
        for key in ((pg, band), (pg, "all")):
            t2[key][0] += 1
            t2[key][1] += (pid, y + 1) in rows
    show("SIM (played again next season)", t2)


if __name__ == "__main__":
    main()
