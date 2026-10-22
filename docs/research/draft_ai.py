# Real NFL draft behaviour, for the draft AI (Step 8). All local nflverse data.
#   python -I <scratchpad>/draft_ai.py
import csv, gzip, json, math, statistics as st
from collections import defaultdict, Counter
from pathlib import Path

N = Path("tools/data/nflverse")
HERE = Path(__file__).parent
OUT = HERE / "real_draft_ai.json"
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "OT": "OL", "G": "OL", "OG": "OL",
         "C": "OL", "OL": "OL", "DE": "DE", "EDGE": "DE", "DT": "DT", "NT": "DT", "DL": "DT", "LB": "LB",
         "OLB": "LB", "ILB": "LB", "DB": "DB", "CB": "DB", "S": "DB", "SAF": "DB", "FS": "DB", "K": "K/P",
         "P": "K/P", "LS": "K/P"}


def rows(p):
    return list(csv.DictReader(gzip.open(N / p, "rt", encoding="utf-8")))


def f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def pct(v, q):
    v = sorted(v)
    return v[int(q * (len(v) - 1))] if v else None


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else 0


out = {}
picks = [p for p in rows("draft_picks/draft_picks.csv.gz") if p["position"] in GROUP]
for p in picks:
    p["g"], p["yr"], p["rd"], p["pk"] = GROUP[p["position"]], int(p["season"]), int(p["round"]), int(p["pick"])
    p["av"] = f(p["w_av"])
    p["age_f"] = f(p["age"], None)
real_draft = json.loads((HERE / "real_draft.json").read_text())
AVPICK = {int(k): v for k, v in real_draft["pick_value_chart"]["career_av_smoothed"].items()}
JJ = None

# ---------------------------------------------------------------------------
# 1. Consensus board vs where players actually went (ESPN 2023 final big board rank)
# ---------------------------------------------------------------------------
espn = rows("misc/espn_draft_player_probs.csv.gz")
rank = {}
for e in espn:
    if e["type"] == "final" and e["rank"] not in ("", "NA"):
        rank[e["player"].lower()] = (int(f(e["rank"])), e["pos"])
d23 = [p for p in picks if p["yr"] == 2023]
pairs = []
for p in d23:
    k = p["pfr_player_name"].lower()
    if k in rank:
        pairs.append((rank[k][0], p["pk"], p["g"], p["pfr_player_name"]))
undrafted_ranked = sorted(r for name, (r, _pos) in rank.items()
                          if name not in {p["pfr_player_name"].lower() for p in d23})
diffs = defaultdict(list)
for rk, pk, g, _n in pairs:
    band = "1-10" if rk <= 10 else "11-32" if rk <= 32 else "33-64" if rk <= 64 else "65-100" if rk <= 100 else "101+"
    diffs[band].append(pk - rk)
out["board_vs_pick_2023"] = {
    "note": "ESPN final big board rank vs actual pick, 2023 draft (the only year in the file). "
            "positive = went later than ranked",
    "matched": len(pairs),
    "rank_pick_correlation": round(corr([math.log(a) for a, *_ in pairs], [math.log(b) for _, b, *_ in pairs]), 3),
    "by_rank_band": {b: {"n": len(v), "median_pick_minus_rank": pct(v, .5), "p10": pct(v, .1), "p90": pct(v, .9),
                         "abs_median": pct([abs(x) for x in v], .5)} for b, v in diffs.items()},
    "ranked_top100_undrafted": [r for r in undrafted_ranked if r <= 100],
    "biggest_reaches": sorted(pairs, key=lambda t: t[1] - t[0])[:8],
    "biggest_falls": sorted(pairs, key=lambda t: t[0] - t[1])[:8]}
# by position: do some positions go earlier than the board (positional value)?
pos_d = defaultdict(list)
for rk, pk, g, _n in pairs:
    if rk <= 100:
        pos_d[g].append(math.log(pk) - math.log(rk))
out["board_vs_pick_2023"]["position_log_ratio_top100"] = {
    g: {"n": len(v), "mean_log_pick_over_rank": round(st.mean(v), 2)} for g, v in sorted(pos_d.items())}

# ---------------------------------------------------------------------------
# 2. Team need: does a recent high pick at a position stop a team taking another?
# ---------------------------------------------------------------------------
by_team_yr = defaultdict(list)
for p in picks:
    by_team_yr[(p["team"], p["yr"])].append(p)
years = range(2003, 2027)
need = {}
for g in ("QB", "RB", "WR", "TE", "OL", "DE", "DT", "LB", "DB"):
    base_n = base_hit = inv_n = inv_hit = 0
    for (team, yr), ps in by_team_yr.items():
        if yr not in years:
            continue
        took = any(p["g"] == g and p["rd"] <= 2 for p in ps)
        invested = any(q["g"] == g and q["rd"] == 1
                       for y in (yr - 1, yr - 2, yr - 3) for q in by_team_yr.get((team, y), []))
        if invested:
            inv_n += 1
            inv_hit += took
        else:
            base_n += 1
            base_hit += took
    need[g] = {"p_take_r1_r2": round(base_hit / base_n, 3),
               "p_take_r1_r2_after_r1_pick_there_in_last_3_drafts": round(inv_hit / inv_n, 3) if inv_n else None,
               "team_drafts_with_recent_r1": inv_n}
out["need_recent_first_rounder"] = need

# QB focus: team's main passer last season (most attempts) - young & good -> drafts a QB early?
qbs = {}
for yr in range(2002, 2026):
    path = N / f"stats_player/stats_player_reg_{yr}.csv.gz"
    if not path.exists():
        continue
    best = {}
    for r in rows(f"stats_player/stats_player_reg_{yr}.csv.gz"):
        if r["position"] != "QB":
            continue
        a = f(r["attempts"])
        t = r["recent_team"]
        if a > best.get(t, (0,))[0]:
            best[t] = (a, r)
    qbs[yr] = best
dp_by_id = {p["gsis_id"]: p for p in picks if p["gsis_id"] not in ("", "NA")}
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}
cases = Counter()
for (team, yr), ps in by_team_yr.items():
    prev = qbs.get(yr - 1)
    if not prev:
        continue
    t2 = {"LVR": "LV", "OAK": "LV", "SDG": "LAC", "STL": "LA", "RAM": "LA", "GNB": "GB", "KAN": "KC", "NWE": "NE",
          "NOR": "NO", "SFO": "SF", "TAM": "TB", "JAX": "JAX", "LAR": "LA"}.get(team, team)
    q = prev.get(t2) or prev.get(TEAM_FIX.get(t2, t2))
    if not q:
        continue
    a, r = q
    dp = dp_by_id.get(r["player_id"])
    young = dp is not None and yr - dp["yr"] <= 4 and dp["rd"] <= 2
    good = a >= 350 and f(r["passing_epa"]) / max(a, 1) >= 0.10
    took = any(p["g"] == "QB" and p["rd"] <= 2 for p in ps)
    took1 = any(p["g"] == "QB" and p["rd"] == 1 for p in ps)
    key = ("young_R1-2_starter" if young else "other_starter") + ("_good" if good else "_not_good")
    cases[key + "_n"] += 1
    cases[key + "_took_qb_r1_r2"] += took
    cases[key + "_took_qb_r1"] += took1
qb_out = {}
for k in ("young_R1-2_starter_good", "young_R1-2_starter_not_good", "other_starter_good", "other_starter_not_good"):
    n = cases[k + "_n"]
    qb_out[k] = {"team_drafts": n, "p_qb_r1_r2": round(cases[k + "_took_qb_r1_r2"] / n, 3) if n else None,
                 "p_qb_r1": round(cases[k + "_took_qb_r1"] / n, 3) if n else None}
out["qb_need"] = {"note": "last season's main passer (most attempts). young = drafted R1-2 within 4 years; "
                          "good = 350+ attempts and EPA/attempt >= 0.10", **qb_out}

# ---------------------------------------------------------------------------
# 3. Draft-day trades: what moving up costs
# ---------------------------------------------------------------------------
JJ_PTS = {1: 3000, 2: 2600, 3: 2200, 4: 1800, 5: 1700, 6: 1600, 7: 1500, 8: 1400, 9: 1350, 10: 1300, 11: 1250,
          12: 1200, 13: 1150, 14: 1100, 15: 1050, 16: 1000, 17: 950, 18: 900, 19: 875, 20: 850, 21: 800, 22: 780,
          23: 760, 24: 740, 25: 720, 26: 700, 27: 680, 28: 660, 29: 640, 30: 620, 31: 600, 32: 590}


def jj(n):
    if n in JJ_PTS:
        return JJ_PTS[n]
    if n <= 64:
        return 580 - (n - 33) * (580 - 270) / 31
    if n <= 96:
        return 270 - (n - 64) * (270 - 116) / 32
    if n <= 128:
        return 116 - (n - 96) * (116 - 43) / 32
    if n <= 160:
        return 43 - (n - 128) * (43 - 27.4) / 32
    if n <= 192:
        return 27.4 - (n - 160) * (27.4 - 15.2) / 32
    return max(15.2 - (n - 192) * (15.2 - 2) / 64, 1)


trades = rows("trades/trades.csv.gz")
by_id = defaultdict(list)
for t in trades:
    by_id[t["trade_id"]].append(t)
deals = []
for tid, ts in by_id.items():
    season = ts[0]["season"]
    if any(t["pfr_id"] not in ("", "NA") and not t["pick_season"] for t in ts):
        continue                                    # players involved
    if not all(t["pick_season"] == season and t["pick_number"] not in ("", "NA") for t in ts):
        continue                                    # future or unnumbered picks: skip
    teams = sorted(set(t["gave"] for t in ts))
    if len(teams) != 2:
        continue
    side = {tm: [int(t["pick_number"]) for t in ts if t["gave"] == tm] for tm in teams}
    # 'gave' = the team that gave this pick away
    a, b = teams
    if not side[a] or not side[b]:
        continue
    up, down = (a, b) if min(side[a]) > min(side[b]) else (b, a)   # 'up' gave the later picks, got the top one
    got = side[down]
    gave = side[up]
    deals.append({"season": int(season), "top_pick": min(got), "gave": sorted(gave), "got": sorted(got),
                  "jj_ratio": sum(jj(x) for x in gave) / sum(jj(x) for x in got),
                  "av_ratio": sum(AVPICK.get(x, 6) for x in gave) / sum(AVPICK.get(x, 6) for x in got)})
deals = [d for d in deals if d["season"] >= 2010]
bands = [(1, 10), (11, 32), (33, 64), (65, 128), (129, 262)]
out["draft_trades"] = {"note": "same-year pick-for-pick trades 2010-2026 (no players, no future picks). "
                               "ratio = value the team moving up gave / value it got; 1.0 = fair",
                       "n": len(deals), "per_draft": round(len(deals) / 17, 1),
                       "by_top_pick": {}}
for a, b in bands:
    ds = [d for d in deals if a <= d["top_pick"] <= b]
    if ds:
        out["draft_trades"]["by_top_pick"][f"{a}-{b}"] = {
            "n": len(ds), "jimmy_johnson_ratio_median": round(pct([d["jj_ratio"] for d in ds], .5), 2),
            "av_chart_ratio_median": round(pct([d["av_ratio"] for d in ds], .5), 2),
            "picks_given_median": pct([len(d["gave"]) for d in ds], .5),
            "spots_moved_median": pct([min(d["gave"]) - d["top_pick"] for d in ds], .5)}
out["draft_trades"]["examples"] = sorted(deals, key=lambda d: d["top_pick"])[:6]

# ---------------------------------------------------------------------------
# 4. Signals beyond draft slot: age and combine (2000-2018 classes)
# ---------------------------------------------------------------------------
mature = [p for p in picks if 2000 <= p["yr"] <= 2018 and p["pk"] <= 256]
for p in mature:
    exp = AVPICK.get(p["pk"], 6)
    p["resid"] = p["av"] / exp if exp else 1      # career AV vs a typical player at that slot
age_out = {}
for a, b, lab in ((0, 21.49, "21 or younger"), (21.5, 22.49, "22"), (22.5, 23.49, "23"), (23.5, 99, "24+")):
    ps = [p for p in mature if p["age_f"] and a <= p["age_f"] <= b]
    if ps:
        age_out[lab] = {"n": len(ps), "career_av_vs_slot": round(st.mean(p["resid"] for p in ps), 2),
                        "median_pick": pct([p["pk"] for p in ps], .5)}
out["age_effect"] = {"note": "career AV divided by the typical career AV at that pick (1.00 = as expected)",
                     **age_out}
cmb = {}
for c in rows("combine/combine.csv.gz"):
    if c["pfr_id"]:
        cmb[c["pfr_id"]] = c
combine_out = {}
for g in ("QB", "RB", "WR", "TE", "OL", "DE", "DT", "LB", "DB"):
    ps = [p for p in mature if p["g"] == g and p["pfr_player_id"] in cmb]
    res = {}
    for k in ("forty", "vertical", "broad_jump", "cone", "shuttle", "bench", "wt"):
        xs, ys = [], []
        for p in ps:
            v = f(cmb[p["pfr_player_id"]].get(k), None)
            if v:
                xs.append(v)
                ys.append(math.log(max(p["resid"], 0.05)))
        if len(xs) >= 60:
            # sign: positive = better drill (faster time / higher jump) goes with beating your slot
            sgn = -1 if k in ("forty", "cone", "shuttle") else 1
            res[k] = {"n": len(xs), "corr_with_beating_slot": round(sgn * corr(xs, ys), 3)}
    combine_out[g] = res
out["combine_signal_beyond_slot"] = {"note": "correlation of each drill (oriented so + = better result) with "
                                             "career AV relative to draft slot; ~0 = teams already priced it in",
                                     **combine_out}

# ---------------------------------------------------------------------------
# 5. Is drafting skill persistent? team AV-over-slot, odd vs even years 2000-2018
# ---------------------------------------------------------------------------
team_res = defaultdict(lambda: defaultdict(list))
for p in mature:
    team_res[p["team"]][p["yr"] % 2].append(p["resid"])
tm = [t for t in team_res if team_res[t][0] and team_res[t][1]]
odd = [st.mean(team_res[t][1]) for t in tm]
even = [st.mean(team_res[t][0]) for t in tm]
spread = sorted(st.mean(team_res[t][0] + team_res[t][1]) for t in tm)
out["team_drafting_skill"] = {"teams": len(tm), "odd_vs_even_year_correlation": round(corr(odd, even), 3),
                              "team_av_vs_slot_best": round(spread[-1], 2), "worst": round(spread[0], 2),
                              "p25": round(pct(spread, .25), 2), "p75": round(pct(spread, .75), 2)}

OUT.write_text(json.dumps(out, indent=1, default=str))
print(json.dumps(out, indent=1, default=str))
