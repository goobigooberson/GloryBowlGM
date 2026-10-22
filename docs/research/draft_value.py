# Real NFL draft value: pick slot -> career outcome, by position and round
# (nflverse draft_picks.csv: PFR career data incl. weighted career AV), plus
# draft composition (how many of each position go in each round) and
# combine results in real units. Run from the project folder:
#   python -I <scratchpad>/draft_value.py
import csv, gzip, json, math, sys
from collections import defaultdict
from pathlib import Path

D = Path("tools/data/nflverse/draft_picks/draft_picks.csv.gz")
C = Path("tools/data/nflverse/combine/combine.csv.gz")
OUT = Path(__file__).with_name("real_draft.json")

GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
         "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL", "OL": "OL",
         "DE": "DE", "DT": "DT", "NT": "DT", "DL": "DT",
         "LB": "LB", "OLB": "LB", "ILB": "LB",
         "DB": "DB", "CB": "DB", "S": "DB", "SAF": "DB", "FS": "DB",
         "K": "K/P", "P": "K/P", "LS": "K/P"}
MATURE = range(2000, 2019)       # classes with full careers mostly played out (8+ seasons)
RECENT = range(2014, 2027)       # draft composition: the modern draft


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def mean(v):
    return sum(v) / len(v) if v else None


def r(x, n=2):
    return None if x is None else round(x, n)


picks = [p for p in csv.DictReader(gzip.open(D, "rt", encoding="utf-8")) if p["position"] in GROUP]
for p in picks:
    p["g"] = GROUP[p["position"]]
    p["yr"], p["rd"], p["pk"] = int(p["season"]), int(p["round"]), int(p["pick"])
    for k in ("w_av", "dr_av", "seasons_started", "probowls", "allpro", "games"):
        p[k] = f(p[k])

mature = [p for p in picks if p["yr"] in MATURE and p["pk"] <= 256]


def outcome(ps):
    n = len(ps)
    if not n:
        return None
    return {"n": n,
            "career_av": r(mean([p["w_av"] for p in ps]), 1),
            "av_with_drafting_team": r(mean([p["dr_av"] for p in ps]), 1),
            "seasons_started": r(mean([p["seasons_started"] for p in ps]), 2),
            "starter_3plus_seasons": r(sum(p["seasons_started"] >= 3 for p in ps) / n, 3),
            "starter_5plus_seasons": r(sum(p["seasons_started"] >= 5 for p in ps) / n, 3),
            "pro_bowl": r(sum(p["probowls"] >= 1 for p in ps) / n, 3),
            "all_pro": r(sum(p["allpro"] >= 1 for p in ps) / n, 3),
            "bust_under_16_games": r(sum(p["games"] < 16 for p in ps) / n, 3),
            "never_started": r(sum(p["seasons_started"] == 0 for p in ps) / n, 3)}


out = {"source": "nflverse draft_picks.csv (PFR). Outcomes from the 2000-2018 classes (picks 1-256); "
                 "career_av = PFR weighted career Approximate Value; composition from 2014-2026 drafts.",
       "groups": "OL = T/G/C; DT includes NT and generic DL; LB = all linebackers (OLB edge rushers in 3-4 "
                 "teams are listed as LB by PFR in many years); DB = CB+S; K/P includes LS"}

# 1. Value by pick: smoothed career AV per slot -> a chart with pick 1 = 3000
by_pick = defaultdict(list)
for p in mature:
    by_pick[p["pk"]].append(p["w_av"])
raw = {k: mean(v) for k, v in by_pick.items()}
smooth = {}
for k in range(1, 257):
    # local log-linear fit over a window that widens later in the draft
    w = max(2, int(k * 0.15))
    xs = [j for j in range(max(1, k - w), min(256, k + w) + 1) if j in raw]
    if not xs:
        continue
    lx = [math.log(j) for j in xs]
    ly = [math.log(max(raw[j], 0.5)) for j in xs]
    mx, my = mean(lx), mean(ly)
    sxx = sum((a - mx) ** 2 for a in lx)
    b = sum((a - mx) * (c - my) for a, c in zip(lx, ly)) / sxx if sxx else 0
    smooth[k] = math.exp(my + b * (math.log(k) - mx))
# force non-increasing
prev = float("inf")
for k in sorted(smooth):
    smooth[k] = min(smooth[k], prev)
    prev = smooth[k]
scale = 3000 / smooth[1]
out["pick_value_chart"] = {
    "note": "career-AV based (like Chase Stuart's chart), scaled so pick 1 = 3000 to compare with the "
            "Jimmy Johnson chart. Johnson overvalues the top of round 1 versus real outcomes: real "
            "AV says the 1st pick is worth about 2 late firsts, Johnson says about 5.",
    "career_av_smoothed": {str(k): r(v, 1) for k, v in smooth.items()},
    "points": {str(k): round(v * scale) for k, v in smooth.items()},
    "jimmy_johnson_reference": {"1": 3000, "2": 2600, "3": 2200, "5": 1700, "10": 1300, "16": 1000,
                                "20": 850, "32": 590, "33": 580, "48": 420, "64": 270, "96": 116,
                                "128": 43, "160": 27.4, "192": 15.2, "224": 3.6}}

# 2. Outcomes by round and by pick band (all positions)
out["by_round"] = {str(rd): outcome([p for p in mature if p["rd"] == rd]) for rd in range(1, 8)}
bands = [(1, 5), (6, 10), (11, 20), (21, 32), (33, 48), (49, 64), (65, 100), (101, 140), (141, 180),
         (181, 220), (221, 256)]
out["by_pick_band"] = {f"{a}-{b}": outcome([p for p in mature if a <= p["pk"] <= b]) for a, b in bands}

# 3. Outcomes by position x round
out["by_position_round"] = {}
for g in sorted(set(GROUP.values())):
    out["by_position_round"][g] = {str(rd): outcome([p for p in mature if p["g"] == g and p["rd"] == rd])
                                   for rd in range(1, 8)}
    out["by_position_round"][g]["all"] = outcome([p for p in mature if p["g"] == g])

# 4. Draft composition: picks per draft by position and round (modern drafts)
recent = [p for p in picks if p["yr"] in RECENT]
years = len(set(p["yr"] for p in recent))
comp = defaultdict(lambda: defaultdict(int))
for p in recent:
    comp[p["g"]][p["rd"]] += 1
out["picks_per_draft_by_position_round"] = {
    g: {str(rd): r(comp[g][rd] / years, 2) for rd in range(1, 8)} | {"total": r(sum(comp[g].values()) / years, 1)}
    for g in sorted(comp)}
# first pick at each position each year (how early the first TE, QB... goes)
first = defaultdict(list)
for yr in RECENT:
    for g in set(GROUP.values()):
        ps = [p["pk"] for p in recent if p["yr"] == yr and p["g"] == g]
        if ps:
            first[g].append(min(ps))
out["first_pick_at_position_median"] = {g: sorted(v)[len(v) // 2] for g, v in first.items()}
# age at draft by round
ages = defaultdict(list)
for p in recent:
    if p["age"] not in ("", "NA"):
        ages[p["rd"]].append(f(p["age"]))
out["age_at_draft_by_round"] = {str(k): r(mean(v), 1) for k, v in sorted(ages.items())}

# 5. TE focus: when do the good TEs come from
te = [p for p in mature if p["g"] == "TE"]
good = [p for p in te if p["seasons_started"] >= 5 or p["probowls"] >= 1]
out["te_focus"] = {"te_drafted_2000_18": len(te), "good_te (5+ seasons started or a Pro Bowl)": len(good),
                   "good_te_by_round": {str(rd): sum(1 for p in good if p["rd"] == rd) for rd in range(1, 8)},
                   "pro_bowl_te_by_round": {str(rd): sum(1 for p in te if p["probowls"] >= 1 and p["rd"] == rd)
                                            for rd in range(1, 8)}}

# 6. Combine in real units by position (2000-2026 combine invites)
cmb = defaultdict(lambda: defaultdict(list))
drafted_cmb = defaultdict(lambda: defaultdict(list))
for row in csv.DictReader(gzip.open(C, "rt", encoding="utf-8")):
    g = GROUP.get(row["pos"]) or {"EDGE": "DE", "OG": "OL"}.get(row["pos"])
    if not g:
        continue
    ht = row["ht"]
    if ht and "-" in ht:
        a, b = ht.split("-")
        row["ht_in"] = int(a) * 12 + int(b)
    for k in ("ht_in", "wt", "forty", "bench", "vertical", "broad_jump", "cone", "shuttle"):
        v = f(row.get(k))
        if v:
            cmb[g][k].append(v)
            if row["draft_round"] not in ("", "NA"):
                drafted_cmb[(g, int(f(row["draft_round"])) <= 2)][k].append(v)


def dist(v):
    v = sorted(v)
    m = mean(v)
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / len(v))
    q = lambda p: v[int(p * (len(v) - 1))]
    return {"n": len(v), "mean": r(m), "sd": r(sd, 3), "p10": q(.1), "p50": q(.5), "p90": q(.9),
            "min": v[0], "max": v[-1]}


out["combine_by_position"] = {g: {k: dist(v) for k, v in ks.items() if len(v) >= 30} for g, ks in cmb.items()}
out["combine_rounds_1_2_vs_later_means"] = {
    g: {k: [r(mean(drafted_cmb[(g, True)][k])), r(mean(drafted_cmb[(g, False)][k]))]
        for k in ("forty", "vertical", "broad_jump", "cone", "bench", "wt")
        if drafted_cmb[(g, True)][k] and drafted_cmb[(g, False)][k]}
    for g in sorted(set(GROUP.values()))}

OUT.write_text(json.dumps(out, indent=1))
print("wrote", OUT)
pv = out["pick_value_chart"]["points"]
print("chart:", {k: pv[k] for k in ("1", "2", "3", "5", "10", "16", "20", "32", "33", "48", "64", "96", "128", "160", "192", "224", "256") if k in pv})
for k, v in out["by_pick_band"].items():
    print(k, v)
print("position x round: career AV / starter3+ / pro bowl")
for g, d in out["by_position_round"].items():
    print(f"{g:4}", " | ".join(f"R{rd} {d[rd]['n']:3} {d[rd]['career_av']:5} {d[rd]['starter_3plus_seasons']:.2f} {d[rd]['pro_bowl']:.2f}"
                               for rd in map(str, range(1, 8)) if d[rd]))
print("per draft:", out["picks_per_draft_by_position_round"])
print("first pick median:", out["first_pick_at_position_median"])
print("age:", out["age_at_draft_by_round"])
print("TE:", out["te_focus"])
print("combine R1-2 vs later:", out["combine_rounds_1_2_vs_later_means"])
