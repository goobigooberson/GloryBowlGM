# docs/research/deal_kinds.py
# How real veteran market deals split: extensions (signed while his old deal
# still had years to run), re-signings with his own team as a free agent, and
# signings with a new team. For tools/free_agency_check.py.
#   python docs/research/deal_kinds.py   -> docs/research/real_deal_kinds.json
# Data: OverTheCap via nflverse historical_contracts.csv (May 2022 snapshot).
# Each player's contracts in order: a deal signed in year Y is an EXTENSION if
# his previous deal (same team) ran past Y-1 (it had years left), a RE-SIGNING
# if his previous deal ended in Y-1 with the same team, a NEW TEAM deal if it's
# with another team. Market deal = 1%+ of that year's cap. Signing years
# 2016-2021 (earlier years miss many previous deals; 2022 is only March-May).
# Caveat: OTC's team on a deal is the signing team; players traded mid-deal
# show their old team on the old deal, so a few "new team" deals are trades.
import csv
import gzip
import json
import os
import sys
from collections import defaultdict, Counter

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "tools", "data", "nflverse", "contracts", "historical_contracts.csv.gz")
OUT = os.path.join(ROOT, "docs", "research", "real_deal_kinds.json")
GROUP = {"QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "LT": "T", "RT": "T", "LG": "G", "RG": "G",
         "C": "C", "ED": "EDGE", "IDL": "DT", "LB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P", "LS": "LS"}
CAP = {2011: 120.0, 2012: 120.6, 2013: 123.0, 2014: 133.0, 2015: 143.28, 2016: 155.27, 2017: 167.0, 2018: 177.2,
       2019: 188.2, 2020: 198.2, 2021: 182.5, 2022: 208.2}
YEARS = range(2016, 2022)


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


by_player = defaultdict(list)
for r in csv.DictReader(gzip.open(SRC, "rt", encoding="utf-8")):
    y = num(r["year_signed"])
    if r["position"] not in GROUP or y not in CAP or "/" in r["team"]:
        continue
    by_player[r["otc_id"] or r["player"]].append({
        "y": y, "team": r["team"], "years": max(1, num(r["years"])), "pct": num(r["apy"]) / 1e6 / CAP[y],
        "g": GROUP[r["position"]], "rookie": r["draft_year"] not in ("", "NA") and num(r["draft_year"]) == y})

kinds = defaultdict(Counter)          # year -> kind -> market deals
by_group = defaultdict(Counter)
for deals in by_player.values():
    deals.sort(key=lambda d: (d["y"], -d["pct"]))
    seen = set()
    prev = None
    for d in deals:
        key = (d["y"], d["team"])
        if key in seen:                    # duplicate rows / restructured versions of the same deal
            continue
        seen.add(key)
        if d["rookie"] or prev is None:
            prev = d
            continue
        if d["y"] in YEARS and d["pct"] >= 0.01:
            end = prev["y"] + prev["years"] - 1
            if d["team"] != prev["team"]:
                k = "new_team"
            elif end >= d["y"]:
                k = "extension"
            else:
                k = "re_signed"
            kinds[d["y"]][k] += 1
            by_group[d["g"]][k] += 1
        prev = d

n_years = len(YEARS)
tot = Counter()
for c in kinds.values():
    tot.update(c)
out = {"source": "OverTheCap via nflverse historical_contracts.csv (May 2022 snapshot); market deals (1%+ of the cap), "
                 f"signing years {YEARS[0]}-{YEARS[-1]}; script docs/research/deal_kinds.py",
       "per_season": {k: round(v / n_years, 1) for k, v in tot.items()},
       "share": {k: round(v / sum(tot.values()), 3) for k, v in tot.items()},
       "by_year": {y: dict(c) for y, c in sorted(kinds.items())},
       "by_group_per_season": {g: {k: round(v / n_years, 1) for k, v in c.items()} for g, c in sorted(by_group.items())}}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
print(json.dumps({k: out[k] for k in ("per_season", "share", "by_year")}, indent=1))
