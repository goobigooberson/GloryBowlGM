# startup_value.py
# How real NFL teams rank established players by position, for tuning the startup draft
# (engine/draft.py, STARTUP_POS_WEIGHT; Blake, Oct 22: re-tune the startup draft's position
# values to real contract rankings).
#
# Source: OverTheCap contracts via nflverse (tools/data/nflverse/contracts). For each season
# 2015-2022, every player's contract in force that season (the latest one signed by then
# that still runs), veteran deals only (not the rookie deal he signed the year he was
# drafted: those are set by draft slot, not by what teams think he's worth), ranked by
# share of the cap when signed. For each position, the rank of its 1st, 3rd, 5th, 10th, 20th
# and 32nd player, as the median over the 8 seasons. A startup draft is all 32 teams picking
# from every established player at once, so this is the closest real thing: what the
# market says each position's best players are worth against everyone else.
#
# Positions are grouped the game's way: edge rushers = DE, interior line = DT, off-ball
# linebackers = OLB + ILB (the game's 4-3 has two OLBs and one ILB), tackles = T, guards = G.
#
#   python docs/research/startup_value.py    (writes docs/research/real_startup_value.json)

import csv
import gzip
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "LT": "T", "RT": "T", "LG": "G",
         "RG": "G", "C": "C", "ED": "DE", "IDL": "DT", "LB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P",
         "LS": "LS"}
KS = (1, 3, 5, 10, 20, 32)
SEASONS = range(2015, 2023)


def main():
    rows = list(csv.DictReader(gzip.open(ROOT / "tools/data/nflverse/contracts/historical_contracts.csv.gz",
                                         "rt", encoding="utf-8")))
    by_player = defaultdict(list)
    for x in rows:
        if not (x["year_signed"].isdigit() and x["years"].isdigit() and x["apy_cap_pct"] not in ("", "NA")):
            continue
        by_player[x["otc_id"] or x["player"]].append(x)
    ranks = defaultdict(lambda: defaultdict(list))
    mixes = defaultdict(lambda: defaultdict(list))
    for season in SEASONS:
        pool = []
        for deals in by_player.values():
            live = [d for d in deals if int(d["year_signed"]) <= season < int(d["year_signed"]) + int(d["years"])]
            if not live:
                continue
            d = max(live, key=lambda d: int(d["year_signed"]))
            if d["draft_year"].isdigit() and d["year_signed"] == d["draft_year"]:
                continue                       # his rookie deal
            g = GROUP.get(d["position"])
            if g:
                pool.append((float(d["apy_cap_pct"]), g))
        pool.sort(reverse=True)
        seen = defaultdict(int)
        for i, (_share, g) in enumerate(pool, start=1):
            seen[g] += 1
            if seen[g] in KS:
                ranks[g][seen[g]].append(i)
        for lo, hi in ((1, 32), (33, 64), (65, 96), (97, 160), (161, 320)):
            n = hi - lo + 1
            c = defaultdict(int)
            for _s, g in pool[lo - 1:hi]:
                c[g] += 1
            for g in GROUP.values():
                mixes[f"{lo}-{hi}"][g].append(c[g] / n)
    out = {"source": "OverTheCap via nflverse, veteran contracts in force 2015-2022, ranked by cap share",
           "ranks": {g: {str(k): st.median(v) for k, v in sorted(d.items())} for g, d in ranks.items()},
           "mix": {r: {g: round(st.mean(v), 3) for g, v in d.items() if st.mean(v) > 0} for r, d in mixes.items()}}
    path = ROOT / "docs/research/real_startup_value.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print("rank of the k-th player at each position (median 2015-2022):")
    for g, d in sorted(out["ranks"].items(), key=lambda kv: kv[1].get("5", 9999)):
        print(f"  {g:3}", "  ".join(f"{k}th {d.get(str(k), '-'):>6}" for k in KS))
    for r, d in out["mix"].items():
        print(f"  picks {r}:", ", ".join(f"{g} {100 * v:.0f}%" for g, v in sorted(d.items(), key=lambda kv: -kv[1])[:10]))


if __name__ == "__main__":
    main()
