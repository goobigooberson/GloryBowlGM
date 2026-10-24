# docs/research/fair_price.py
# Real data for the "fair price" section of tools/free_agency_check.py:
#   python docs/research/fair_price.py
# Writes docs/research/real_fair_price.json.
#
# FOF8's best-known free agency exploit: good players signing far below their
# worth while teams still had cap room. This measures how often that happens in
# the real NFL, with a yardstick the game can be held to as well:
#   - a GOOD player = a starter last season (65%+ of his team's offensive or
#     defensive snaps in the games he played, 8+ games, regular season, with the
#     team he finished with), 30 or younger on September 1 of the signing year;
#   - a FREE AGENT signing = a veteran contract (not his rookie deal) signed with
#     a different team from the one he finished last season with (re-signings
#     with his own team are left out: those mix in extensions, and the exploit
#     is about players the other 31 teams passed on);
#     (his biggest such deal of the year: later small deals that year are
#     in-season pickups after a release; practice squad pay, under 0.25% of the
#     cap, is left out);
#   - his MARKET VALUE = what real good free agents of his position group
#     signed for (the median APY, as a share of that year's cap; age bands have
#     too few deals each for a steady median).
# Then: how often a good free agent signs for under 60% (and 40%) of that, or
# at about the minimum.
# Data: OverTheCap contracts (nflverse historical_contracts.csv, May 2022
# snapshot), nflverse snap counts 2013-2021, nflverse players (ids, birth dates).
import csv
import gzip
import json
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import date

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NV = os.path.join(ROOT, "tools", "data", "nflverse")
OUT = os.path.join(ROOT, "docs", "research", "real_fair_price.json")

TEAM = {"Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
        "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN",
        "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
        "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC", "Rams": "LA", "Dolphins": "MIA",
        "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
        "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Seahawks": "SEA", "Buccaneers": "TB",
        "Titans": "TEN", "Commanders": "WAS"}
ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS"}
# OTC position -> the game's pay-ladder groups (tools/free_agency_check.py LADDER_GROUP)
GROUP = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "LT": "T", "RT": "T", "LG": "G", "RG": "G", "C": "C",
         "ED": "EDGE", "IDL": "DT", "LB": "LB", "CB": "CB", "S": "S"}
DEF = {"EDGE", "DT", "LB", "CB", "S"}
STARTER_SNAPS = 0.65
MAX_AGE = 30
AGE_BANDS = (("<=26", 0, 26), ("27-28", 27, 28), ("29-30", 29, 30))
YEARS = range(2014, 2023)          # signing years (snaps from the season before; 2022 = March-May only)
PS_LINE = 0.0025                   # under this share of the cap: practice squad pay
MINIMUM_LINE = 0.0065


def rd(path):
    return csv.DictReader(gzip.open(path, "rt", encoding="utf-8"))


def age_band(a):
    return next((b for b, lo, hi in AGE_BANDS if lo <= a <= hi), None)


otc2pfr, born = {}, {}
for r in rd(os.path.join(NV, "players", "players.csv.gz")):
    if r["otc_id"] and r["pfr_id"]:
        otc2pfr[r["otc_id"]] = r["pfr_id"]
    if r["otc_id"] and r["birth_date"] not in ("", "NA"):
        born[r["otc_id"]] = r["birth_date"]

snaps = defaultdict(float)            # (season, pfr, team, side) -> his snaps
team_in = defaultdict(float)          # (season, pfr, team, side) -> his team's snaps in the games he played
games = defaultdict(int)              # (season, pfr, team, side) -> games he played on that side
last_team = {}                        # (season, pfr) -> team in his last game
for season in range(YEARS[0] - 1, YEARS[-1]):
    last = {}
    for r in rd(os.path.join(NV, "snap_counts", f"snap_counts_{season}.csv.gz")):
        if r["game_type"] != "REG":
            continue
        t = ALIAS.get(r["team"], r["team"])
        wk = int(r["week"])
        for side, col, pc in (("off", "offense_snaps", "offense_pct"), ("def", "defense_snaps", "defense_pct")):
            s = float(r[col] or 0)
            p = float(r[pc] or 0)
            if s > 0 and p > 0:
                k = (season, r["pfr_player_id"], t, side)
                snaps[k] += s
                team_in[k] += s / p
                games[k] += 1
        if r["pfr_player_id"] not in last or wk >= last[r["pfr_player_id"]][0]:
            last[r["pfr_player_id"]] = (wk, t)
    for pid, (wk, t) in last.items():
        last_team[(season, pid)] = t

CAP = {2014: 133.0, 2015: 143.28, 2016: 155.27, 2017: 167.0, 2018: 177.2, 2019: 188.2, 2020: 198.2, 2021: 182.5,
       2022: 208.2}
best = {}
for r in rd(os.path.join(NV, "contracts", "historical_contracts.csv.gz")):
    g = GROUP.get(r["position"])
    t = TEAM.get(r["team"])
    y = int(float(r["year_signed"] or 0))
    if not g or not t or y not in YEARS:
        continue
    if r["draft_year"] not in ("", "NA") and int(r["draft_year"]) == y:
        continue                                     # his rookie deal
    pid = otc2pfr.get(r["otc_id"])
    prev = last_team.get((y - 1, pid)) if pid else None
    if prev is None or prev == t:
        continue                                     # didn't play last season, or stayed with his team
    side = "def" if g in DEF else "off"
    k = (y - 1, pid, prev, side)
    share = snaps[k] / team_in[k] if games.get(k, 0) >= 8 else 0.0
    b = born.get(r["otc_id"])
    if b:
        bd = date.fromisoformat(b[:10])
        age = y - bd.year - ((9, 1) < (bd.month, bd.day))
    elif r["draft_year"] not in ("", "NA"):
        age = 22 + y - int(r["draft_year"])
    else:
        continue
    pct = float(r["apy"] or 0) / 1e6 / CAP[y]
    if pct < PS_LINE:
        continue
    key = (r["otc_id"] or r["player"], y)
    if key not in best or pct > best[key]["pct"]:
        best[key] = {"g": g, "y": y, "pct": pct, "share": share, "age": age,
                     "name": r["player"], "years": int(float(r["years"] or 1))}
rows = list(best.values())

good = [x for x in rows if x["share"] >= STARTER_SNAPS and x["age"] <= MAX_AGE and x["pct"] > 0]
comp = defaultdict(list)
for x in good:
    comp[x["g"]].append(x["pct"])
value = {k: st.median(v) for k, v in comp.items()}
for x in good:
    x["ratio"] = x["pct"] / value[x["g"]]


def summary(sel):
    n = len(sel) or 1
    return {"n": len(sel), "n_per_season": round(len(sel) / len(YEARS), 1),
            "under_60": round(sum(x["ratio"] < 0.6 for x in sel) / n, 4),
            "under_40": round(sum(x["ratio"] < 0.4 for x in sel) / n, 4),
            "minimum_level": round(sum(x["pct"] <= MINIMUM_LINE for x in sel) / n, 4),
            "under_1pct": round(sum(x["pct"] < 0.01 for x in sel) / n, 4),
            "ratio_p25": round(sorted(x["ratio"] for x in sel)[len(sel) // 4], 3) if sel else None,
            "median_cap_pct": round(st.median(x["pct"] for x in sel), 4) if sel else None}


out = {"source": "OverTheCap via nflverse historical_contracts.csv (May 2022 snapshot), signing years "
                 f"{YEARS[0]}-{YEARS[-1]}; nflverse snap counts (regular season) for the season before; "
                 "nflverse players for ids and birth dates. Script: docs/research/fair_price.py",
       "definitions": {"good": f"{int(STARTER_SNAPS * 100)}%+ of his last team's offensive/defensive snaps last "
                               f"season, age <= {MAX_AGE} on Sept 1 of the signing year",
                       "free_agent": "veteran contract with a team other than the one he finished last season with",
                       "market_value": "median APY share of the cap of good free agents of his position group "
                                       "(pooled over the signing years)",
                       "deal": "his biggest deal of the year with a new team; under 0.25% of the cap (practice "
                               "squad pay) left out",
                       "minimum_level": f"APY <= {MINIMUM_LINE:.2%} of the cap"},
       "starter_snaps": STARTER_SNAPS, "max_age": MAX_AGE,
       "age_bands": [[b, lo, hi] for b, lo, hi in AGE_BANDS],
       "market_value": {g: round(v, 4) for g, v in sorted(value.items())},
       "market_value_n": {g: len(v) for g, v in sorted(comp.items())},
       "all": summary(good),
       "by_group": {g: summary([x for x in good if x["g"] == g]) for g in sorted({x["g"] for x in good})},
       "by_age": {b: summary([x for x in good if age_band(x["age"]) == b]) for b, _lo, _hi in AGE_BANDS},
       "full_time": summary([x for x in good if x["share"] >= 0.85]),
       "full_time_28": summary([x for x in good if x["share"] >= 0.85 and x["age"] <= 28]),
       "cheapest_examples": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()}
                             for x in sorted(good, key=lambda x: x["ratio"])[:15]]}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
print(json.dumps({k: out[k] for k in ("all", "full_time", "full_time_28", "by_age")}, indent=1))
for g, s in out["by_group"].items():
    print(f"  {g:5} n {s['n']:4}  under 60% {s['under_60']:.1%}  under 40% {s['under_40']:.1%}  "
          f"minimum {s['minimum_level']:.1%}  median {s['median_cap_pct']:.2%}")
print("market value:", out["market_value"])
print("cheapest:", [(x["name"], x["g"], x["y"], x["age"], round(x["pct"], 4), round(x["share"], 2))
                    for x in out["cheapest_examples"]])
