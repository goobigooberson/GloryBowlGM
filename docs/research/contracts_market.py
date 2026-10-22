# Real NFL contract market from OverTheCap (nflverse historical_contracts.csv,
# snapshot May 2022). Everything is in % of that year's salary cap so it can be
# scaled to any cap. Run from the project folder:
#   python <scratchpad>/contracts_market.py
import csv, gzip, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

SRC = Path("tools/data/nflverse/contracts/historical_contracts.csv.gz")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("real_contracts.json")

# OTC position -> game position(s)
POS = {"QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "LT": "T", "RT": "T", "LG": "G", "RG": "G",
       "C": "C", "ED": "EDGE", "IDL": "DT", "LB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P", "LS": "LS"}
CAP = {2011: 120.0, 2012: 120.6, 2013: 123.0, 2014: 133.0, 2015: 143.28, 2016: 155.27, 2017: 167.0, 2018: 177.2,
       2019: 188.2, 2020: 198.2, 2021: 182.5, 2022: 208.2, 2023: 224.8, 2024: 255.4, 2025: 279.2, 2026: 301.2}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def r(x, n=4):
    return None if x is None else round(x, n)


rows = list(csv.DictReader(gzip.open(SRC, "rt", encoding="utf-8")))
deals = []
for row in rows:
    pos = POS.get(row["position"])
    yr = int(f(row["year_signed"]) or 0)
    capp = f(row["apy_cap_pct"])
    if not pos or yr < 2011 or capp is None or capp <= 0:
        continue
    dy = f(row["draft_year"])
    dob = row["date_of_birth"]
    age = None
    if dob not in ("", "NA"):
        try:
            age = yr - int(dob[:4]) - (0 if int(dob[5:7]) <= 3 else 1)   # age at March of the signing year
        except ValueError:
            age = None
    if age is None and dy:
        age = 22 + (yr - int(dy))                                        # proxy: drafted at ~22
    rookie = (dy is not None and int(dy) == yr) or (dy is None and age is not None and age <= 23)
    value, gtd = f(row["value"]), f(row["guaranteed"])
    deals.append({"pos": pos, "year": yr, "cap_pct": capp, "years": int(f(row["years"]) or 0),
                  "gtd_share": (gtd / value) if value and gtd is not None and value > 0 else None,
                  "age": age, "rookie": rookie, "active": row["is_active"] == "TRUE",
                  "round": int(f(row["draft_round"]) or 0) if dy else None})

vet = [d for d in deals if not d["rookie"] and 2017 <= d["year"] <= 2022]
out = {"source": "OverTheCap via nflverse historical_contracts.csv (snapshot 2022-05-29); amounts are APY as a "
                 "share of that year's cap; veteran = not a rookie deal; age = at signing (birth date, else draft "
                 "year + 22)",
       "salary_cap_millions": CAP,
       "notes": {"benefits_2026": "2026: $301.2M cap plus $77.6M benefits per club",
                 "vet_minimum_rule": "veteran minimums are ~0.4-0.6% of the cap; a 4+ year vet on a 1-year "
                                     "minimum deal counts only ~0.4% (veteran salary benefit)"},
       "positions": {}}

for pos in sorted(set(d["pos"] for d in deals)):
    pv = [d for d in vet if d["pos"] == pos]
    caps = [d["cap_pct"] for d in pv]
    if len(pv) < 20:
        continue
    p50, p75, p90 = pct(caps, .5), pct(caps, .75), pct(caps, .9)
    tiers = {"top10": [d for d in pv if d["cap_pct"] >= p90],
             "p75_90": [d for d in pv if p75 <= d["cap_pct"] < p90],
             "p50_75": [d for d in pv if p50 <= d["cap_pct"] < p75],
             "below50": [d for d in pv if d["cap_pct"] < p50]}
    tier_stats = {}
    for t, ds in tiers.items():
        yrs = [d["years"] for d in ds if d["years"]]
        g = [d["gtd_share"] for d in ds if d["gtd_share"] is not None]
        ages = [d["age"] for d in ds if d["age"]]
        tier_stats[t] = {"n": len(ds), "cap_pct_median": r(pct([d["cap_pct"] for d in ds], .5)),
                         "years_median": pct(yrs, .5), "years_mean": r(st.mean(yrs), 2) if yrs else None,
                         "years_dist": {str(k): round(sum(1 for y in yrs if y == k) / len(yrs), 3)
                                        for k in range(1, 7)} if yrs else {},
                         "guaranteed_share_median": r(pct(g, .5), 3),
                         "age_median": pct(ages, .5)}
    by_age = {}
    for lo, hi, lab in ((0, 25, "<=25"), (26, 27, "26-27"), (28, 29, "28-29"), (30, 31, "30-31"), (32, 99, "32+")):
        ds = [d for d in pv if d["age"] and lo <= d["age"] <= hi]
        if ds:
            c = [d["cap_pct"] for d in ds]
            yrs = [d["years"] for d in ds if d["years"]]
            by_age[lab] = {"n": len(ds), "cap_pct_median": r(pct(c, .5)), "cap_pct_p90": r(pct(c, .9)),
                           "top10_share": round(sum(1 for x in c if x >= p90) / len(c), 3),
                           "years_mean": r(st.mean(yrs), 2) if yrs else None}
    # The market ladder: what the Nth best-paid player at the position earns (active contracts, 2022)
    act = sorted((d["cap_pct"] for d in deals if d["pos"] == pos and d["active"]), reverse=True)
    ladder = {str(n): r(act[n - 1]) for n in (1, 3, 5, 10, 16, 24, 32, 48, 64, 96) if len(act) >= n}
    # Market deals: 1%+ of the cap (the real free agency / extension market, not minimums)
    mk = [d for d in pv if d["cap_pct"] >= 0.01]
    market = {"n_per_season": round(len(mk) / 6, 1)}
    if mk:
        yrs = [d["years"] for d in mk if d["years"]]
        g = [d["gtd_share"] for d in mk if d["gtd_share"] is not None]
        market.update({
            "cap_pct_p50": r(pct([d["cap_pct"] for d in mk], .5)),
            "years_mean": r(st.mean(yrs), 2), "years_dist": {str(k): round(sum(1 for y in yrs if y == k) / len(yrs), 3)
                                                             for k in range(1, 7)},
            "guaranteed_share_median": r(pct(g, .5), 3),
            "age_dist": {lab: round(sum(1 for d in mk if d["age"] and lo <= d["age"] <= hi) / len(mk), 3)
                         for lo, hi, lab in ((0, 25, "<=25"), (26, 27, "26-27"), (28, 29, "28-29"),
                                             (30, 31, "30-31"), (32, 99, "32+"))},
            "years_by_age": {lab: r(st.mean([d["years"] for d in mk if d["age"] and lo <= d["age"] <= hi
                                              and d["years"]] or [0]), 2)
                             for lo, hi, lab in ((0, 25, "<=25"), (26, 27, "26-27"), (28, 29, "28-29"),
                                                 (30, 31, "30-31"), (32, 99, "32+"))},
            "cap_pct_median_by_age": {lab: r(pct([d["cap_pct"] for d in mk if d["age"] and lo <= d["age"] <= hi], .5))
                                      for lo, hi, lab in ((0, 25, "<=25"), (26, 27, "26-27"), (28, 29, "28-29"),
                                                          (30, 31, "30-31"), (32, 99, "32+"))}})
    out["positions"][pos] = {
        "market_deals_1pct_plus": market,
        "veteran_deals_2017_22": len(pv),
        "veteran_deals_per_season": round(len(pv) / 6, 1),
        "cap_pct": {"p10": r(pct(caps, .1)), "p25": r(pct(caps, .25)), "p50": r(p50), "p75": r(p75),
                    "p90": r(p90), "p95": r(pct(caps, .95)), "p99": r(pct(caps, .99)), "max": r(max(caps))},
        "minimum_share": round(sum(1 for x in caps if x <= 0.0065) / len(caps), 3),
        "one_year_share": round(sum(1 for d in pv if d["years"] == 1) / len(pv), 3),
        "tiers": tier_stats, "by_age": by_age, "ladder_active_2022": ladder}

# Rookie deals: % of cap by draft round (the rookie wage scale)
rk = defaultdict(list)
for d in deals:
    if d["rookie"] and d["round"] and 2017 <= d["year"] <= 2022:
        rk[d["round"]].append(d["cap_pct"])
out["rookie_scale_by_round"] = {str(k): {"n": len(v), "p10": r(pct(v, .1)), "median": r(pct(v, .5)),
                                         "p90": r(pct(v, .9)), "max": r(max(v))} for k, v in sorted(rk.items())}
# Positional spending: share of all active cap dollars by position (2022 snapshot)
tot = defaultdict(float)
for d in deals:
    if d["active"]:
        tot[d["pos"]] += d["cap_pct"]
s = sum(tot.values())
out["active_cap_share_by_position"] = {k: round(v / s, 3) for k, v in sorted(tot.items(), key=lambda kv: -kv[1])}

OUT.write_text(json.dumps(out, indent=1))
print("wrote", OUT)
for pos, d in out["positions"].items():
    t = d["tiers"]
    print(f"{pos:5} n/yr {d['veteran_deals_per_season']:6} p50 {d['cap_pct']['p50']:.4f} p90 {d['cap_pct']['p90']:.4f} "
          f"max {d['cap_pct']['max']:.4f} | min {d['minimum_share']:.2f} 1yr {d['one_year_share']:.2f} | "
          f"top10 yrs {t['top10']['years_mean']} gtd {t['top10']['guaranteed_share_median']} age {t['top10']['age_median']}"
          f" | ladder #1 {d['ladder_active_2022'].get('1')} #5 {d['ladder_active_2022'].get('5')} "
          f"#10 {d['ladder_active_2022'].get('10')} #32 {d['ladder_active_2022'].get('32')}")
print("market deals (1%+ cap): n/season, median cap%, years, gtd, age dist, years by age, cap% by age")
for pos, d in out["positions"].items():
    m = d["market_deals_1pct_plus"]
    if "years_mean" in m:
        print(f"{pos:5} {m['n_per_season']:5} {m['cap_pct_p50']:.4f} yrs {m['years_mean']} gtd {m['guaranteed_share_median']}",
              m["age_dist"], m["years_by_age"], m["cap_pct_median_by_age"])
print("rookie", {k: v["median"] for k, v in out["rookie_scale_by_round"].items()})
print("cap share", out["active_cap_share_by_position"])
