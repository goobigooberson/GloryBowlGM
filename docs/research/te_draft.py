# docs/research/te_draft.py
# Real data for the tight end section of tools/draft_check.py:
#   python docs/research/te_draft.py
# Writes docs/research/real_te_draft.json.
#
# FOF8's AI valued tight ends among the lowest of all positions, so elite TE
# prospects fell past pick 8. Real teams don't do that with the TEs they
# believe in, but real TEs are hard to judge and many great ones went late.
# What's measured (nflverse draft picks, PFR career fields as of 2026):
#   - the first TE taken in each draft (2000-2026);
#   - TEs taken in round 1 and the top 10, per draft;
#   - in hindsight (classes 2000-2018, 8+ seasons to judge): where each
#     class's best TE went, and where TEs among each class's best careers went
#     compared with other positions. Career value = seasons as a starter + 1.5
#     per Pro Bowl + 0.25 per season in the league (the same yardstick
#     tools/draft_check.py uses for the game's careers);
#   - how first-round TEs turned out;
#   - the one year of public big-board ranks in the data (ESPN 2023): the TEs'
#     ranks vs where they went.
import csv
import gzip
import json
import os
import statistics as st
import sys
from collections import defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NV = os.path.join(ROOT, "tools", "data", "nflverse")
OUT = os.path.join(ROOT, "docs", "research", "real_te_draft.json")
HINDSIGHT = range(2000, 2019)


def rd(path):
    return csv.DictReader(gzip.open(path, "rt", encoding="utf-8"))


def num(x, d=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return d


def value(r):
    s = num(r["season"])
    on = num(r["to"]) - s + 1 if num(r["to"]) >= s else 0
    return num(r["seasons_started"]) + 1.5 * num(r["probowls"]) + 0.25 * on


rows = [r for r in rd(os.path.join(NV, "draft_picks", "draft_picks.csv.gz")) if num(r["season"]) >= 2000]
by_year = defaultdict(list)
for r in rows:
    by_year[num(r["season"])].append(r)

first_te = {}
r1_te, top10_te = [], []
for y, rs in sorted(by_year.items()):
    tes = sorted(num(r["pick"]) for r in rs if r["position"] == "TE")
    if tes:
        first_te[y] = tes[0]
    r1_te.append(sum(1 for p in tes if p <= 32))
    top10_te.append(sum(1 for p in tes if p <= 10))
fp = list(first_te.values())

best_te, top8, top32 = [], defaultdict(list), defaultdict(list)
r1_out = []
for y in HINDSIGHT:
    rs = sorted(by_year[y], key=value, reverse=True)
    tes = [r for r in rs if r["position"] == "TE"]
    if tes:
        best_te.append({"year": y, "pick": num(tes[0]["pick"]), "name": tes[0]["pfr_player_name"],
                        "value": value(tes[0])})
    for i, r in enumerate(rs[:32]):
        key = "TE" if r["position"] == "TE" else "other"
        top32[key].append(num(r["pick"]))
        if i < 8:
            top8[key].append(num(r["pick"]))
    for r in tes:
        if num(r["pick"]) <= 32:
            r1_out.append(r)
bp = [b["pick"] for b in best_te]

# ESPN's final 2023 big board: the TEs.
espn = []
for r in rd(os.path.join(NV, "misc", "espn_draft_player_probs.csv.gz")):
    if r["type"] == "final" and r["pos"] == "TE" and r["rank"] not in ("", "NA"):
        espn.append((num(r["rank"]), r["player"]))
espn = sorted(set(espn))[:8]
picks23 = {r["pfr_player_name"]: num(r["pick"]) for r in by_year[2023]}

out = {"source": "nflverse draft_picks.csv (PFR career fields as of 2026); ESPN 2023 final big board "
                 "(nflverse misc/espn_draft_player_probs). Script: docs/research/te_draft.py",
       "first_te_pick": {"years": f"{min(first_te)}-{max(first_te)}", "median": st.median(fp),
                         "top10_share": round(sum(p <= 10 for p in fp) / len(fp), 3),
                         "round1_share": round(sum(p <= 32 for p in fp) / len(fp), 3),
                         "after_50_share": round(sum(p > 50 for p in fp) / len(fp), 3),
                         "by_year": first_te},
       "te_per_draft": {"round1": round(st.mean(r1_te), 2), "top10": round(st.mean(top10_te), 2)},
       "best_te_hindsight": {"years": f"{HINDSIGHT[0]}-{HINDSIGHT[-1]}", "median_pick": st.median(bp),
                             "round1_share": round(sum(p <= 32 for p in bp) / len(bp), 3),
                             "top10_share": round(sum(p <= 10 for p in bp) / len(bp), 3),
                             "after_round3_share": round(sum(p > 100 for p in bp) / len(bp), 3),
                             "classes": best_te},
       "class_top8_careers": {"te_per_class": round(len(top8["TE"]) / len(HINDSIGHT), 2),
                              "te_median_pick": st.median(top8["TE"]) if top8["TE"] else None,
                              "other_median_pick": st.median(top8["other"])},
       "class_top32_careers": {"te_per_class": round(len(top32["TE"]) / len(HINDSIGHT), 2),
                               "te_median_pick": st.median(top32["TE"]) if top32["TE"] else None,
                               "other_median_pick": st.median(top32["other"])},
       "round1_te_outcomes": {"n": len(r1_out),
                              "starter_3plus": round(sum(num(r["seasons_started"]) >= 3 for r in r1_out) / len(r1_out), 3),
                              "starter_5plus": round(sum(num(r["seasons_started"]) >= 5 for r in r1_out) / len(r1_out), 3),
                              "pro_bowl": round(sum(num(r["probowls"]) > 0 for r in r1_out) / len(r1_out), 3),
                              "never_started": round(sum(num(r["seasons_started"]) == 0 for r in r1_out) / len(r1_out), 3)},
       "espn_2023_te": [{"rank": k, "player": n, "pick": picks23.get(n)} for k, n in espn]}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("first_te_pick", "best_te_hindsight")}, indent=1))
print({k: v for k, v in out["first_te_pick"].items() if k != "by_year"})
print({k: v for k, v in out["best_te_hindsight"].items() if k != "classes"})
print([(b["year"], b["pick"], b["name"]) for b in best_te])
