# Real offseason movement and practice squad makeup from nflverse weekly rosters.
# Offseason: each player's team in the last regular-season week he appears (season Y)
# vs his team in week 1 of season Y+1. Run from the project folder:
#   python -I <scratchpad>/real_movement.py
import csv, gzip, json
from collections import defaultdict, Counter
from pathlib import Path

W = Path("tools/data/nflverse/weekly_rosters")
OUT = Path(__file__).with_name("real_movement.json")
POS = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL", "OL": "OL",
       "OT": "OL", "OG": "OL", "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "LB": "LB", "OLB": "LB", "ILB": "LB",
       "MLB": "LB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB", "SAF": "DB", "K": "K", "P": "P",
       "LS": "LS"}
DCP = {"LT": "T", "RT": "T", "T": "T", "LG": "G", "RG": "G", "G": "G", "C": "C", "DE": "DE", "LDE": "DE",
       "RDE": "DE", "EDGE": "DE", "DT": "DT", "NT": "DT", "LDT": "DT", "RDT": "DT", "OLB": "OLB", "LOLB": "OLB",
       "ROLB": "OLB", "ILB": "ILB", "MLB": "ILB", "LILB": "ILB", "RILB": "ILB", "WLB": "OLB", "SLB": "OLB",
       "LB": "ILB", "CB": "CB", "LCB": "CB", "RCB": "CB", "NB": "CB", "S": "S", "FS": "S", "SS": "S",
       "QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "K": "K", "P": "P", "LS": "LS"}


def load(yr):
    p = W / f"roster_weekly_{yr}.csv.gz"
    return list(csv.DictReader(gzip.open(p, "rt", encoding="utf-8"))) if p.exists() else []


out = {"source": "nflverse weekly rosters", "offseason": {}, "practice_squad": {}}
moves_all = defaultdict(lambda: Counter())
age_all = defaultdict(lambda: Counter())
for yr in range(2018, 2025):
    a, b = load(yr), load(yr + 1)
    a = [r for r in a if r["game_type"] == "REG" and r["gsis_id"]]
    b = [r for r in b if r["game_type"] == "REG" and r["gsis_id"]]
    last = {}
    for r in a:
        w = int(r["week"])
        if r["gsis_id"] not in last or w >= last[r["gsis_id"]][0]:
            last[r["gsis_id"]] = (w, r)
    wk1 = min(int(r["week"]) for r in b)
    nxt = {r["gsis_id"]: r for r in b if int(r["week"]) == wk1}
    for pid, (_w, r) in last.items():
        if r["status"] not in ("ACT", "RES", "INA"):
            continue                   # count only players on a 53 / reserve at season's end
        g = POS.get(r["position"])
        if not g:
            continue
        exp = int(r["years_exp"] or 0)
        n = nxt.get(pid)
        if n is None:
            res = "gone"               # not on any week-1 roster/PS next year (retired, unsigned, cut)
        elif n["team"] == r["team"]:
            res = "same"
        else:
            res = "new_team"
        moves_all[g][res] += 1
        band = "0-2" if exp <= 2 else "3-4" if exp <= 4 else "5-7" if exp <= 7 else "8+"
        age_all[band][res] += 1
seasons = 2024 - 2018 + 1


def shares(c):
    n = sum(c.values())
    return {"n_per_season": round(n / seasons, 1), **{k: round(c[k] / n, 3) for k in ("same", "new_team", "gone")}}


out["offseason"]["by_position"] = {g: shares(c) for g, c in sorted(moves_all.items())}
out["offseason"]["by_experience_end_of_season"] = {b: shares(age_all[b]) for b in ("0-2", "3-4", "5-7", "8+")}
tot = Counter()
for c in moves_all.values():
    tot.update(c)
out["offseason"]["all"] = shares(tot)
out["offseason"]["note"] = ("players on a 53 or reserve list in their last regular-season week of season Y; "
                            "'new_team' = on a different team's week-1 roster/PS/reserve in Y+1 (free agency, "
                            "trades, cuts and claims); 'gone' = on no team in week 1 (retired, unsigned, or "
                            "back later in the season)")

# Practice squad makeup (status DEV), regular season weeks 2022-25
ps_pos, ps_exp, team_weeks = Counter(), Counter(), set()
for yr in range(2022, 2026):
    for r in load(yr):
        if r["game_type"] != "REG" or r["status"] != "DEV":
            continue
        team_weeks.add((yr, r["team"], r["week"]))
        d = DCP.get(r["depth_chart_position"]) or DCP.get(r["position"]) or r["position"]
        ps_pos[d] += 1
        e = int(r["years_exp"] or 0)
        ps_exp["0" if e == 0 else "1" if e == 1 else "2" if e == 2 else "3+"] += 1
tw = len(team_weeks)
out["practice_squad"] = {"team_weeks": tw, "players_per_team_week": round(sum(ps_pos.values()) / tw, 2),
                         "by_position_per_squad": {k: round(v / tw, 2) for k, v in ps_pos.most_common()},
                         "by_experience_share": {k: round(v / sum(ps_exp.values()), 3) for k, v in sorted(ps_exp.items())}}
OUT.write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
