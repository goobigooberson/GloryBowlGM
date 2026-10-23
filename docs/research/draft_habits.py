# Real NFL draft-day habits, for the draft AI's front offices (Oct 22, draft session).
# All local nflverse data (trades, draft picks). Writes real_draft_habits.json.
#   python docs/research/draft_habits.py
# - Draft-time trades 2010-26 (April/May trades that move a pick in that year's draft; future
#   picks and players can be in the deal): how many, who moves up for which position, and
#   whether a team's habit (trading down or up) lasts (odd vs even years).
# - Does a trade-down habit go with drafting better? (career value vs a typical player at the
#   same pick, 2010-18 classes)
import csv, gzip, json, statistics as st
from collections import defaultdict, Counter
from pathlib import Path

N = Path("tools/data/nflverse")
OUT = Path(__file__).parent / "real_draft_habits.json"
GRP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL", "OL": "OL",
       "OT": "OL", "DE": "EDGE", "OLB": "EDGE", "DT": "DT", "NT": "DT", "DL": "DT", "LB": "LB", "ILB": "LB",
       "CB": "DB", "S": "DB", "DB": "DB", "SAF": "DB", "FS": "DB", "K": "K/P", "P": "K/P", "LS": "K/P"}
ALIAS = {"OAK": "LV", "LVR": "LV", "SDG": "LAC", "SD": "LAC", "STL": "LA", "LAR": "LA", "RAM": "LA", "GNB": "GB",
         "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF", "TAM": "TB"}


def rows(p):
    return list(csv.DictReader(gzip.open(N / p, "rt", encoding="utf-8")))


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


trades = rows("trades/trades.csv.gz")
picks = {(int(r["season"]), int(r["pick"])): r for r in rows("draft_picks/draft_picks.csv.gz")}
by_id = defaultdict(list)
for t in trades:
    by_id[t["trade_id"]].append(t)
ups = []
for ts in by_id.values():
    s = int(ts[0]["season"])
    if s < 2010 or ts[0]["trade_date"][5:7] not in ("04", "05"):
        continue
    cur = [t for t in ts if t["pick_season"] == ts[0]["season"] and t["pick_number"] not in ("", "NA")]
    teams = sorted(set(ALIAS.get(t["gave"], t["gave"]) for t in ts))
    if not cur or len(teams) != 2:
        continue
    side = {tm: [int(t["pick_number"]) for t in cur if ALIAS.get(t["gave"], t["gave"]) == tm] for tm in teams}
    a, b = teams
    best = {tm: min(side[tm]) if side[tm] else 999 for tm in teams}
    up, down = (a, b) if best[a] > best[b] else (b, a)
    ups.append((s, up, down, best[down]))
out = {"note": "draft-time trades 2010-26: April/May trades moving a pick in that year's draft (future picks and "
               "players may be included); 'up' = the team that got the best current-year pick in the deal",
       "trades_per_draft": round(len(ups) / 17, 1)}
# Who teams move up for
bands = {}
for lo, hi in ((1, 10), (11, 32), (33, 64), (65, 262)):
    got = Counter(GRP.get(picks[(s, p)]["position"], "?") for s, u, d, p in ups if lo <= p <= hi and (s, p) in picks)
    base = Counter(GRP.get(r["position"], "?") for (s, p), r in picks.items() if 2010 <= s <= 2026 and lo <= p <= hi)
    n, m = sum(got.values()), sum(base.values())
    bands[f"{lo}-{hi}"] = {"n": n, "qb_share_of_trade_ups": round(got["QB"] / n, 3),
                           "qb_share_of_all_picks": round(base["QB"] / m, 3),
                           "wr_share_of_trade_ups": round(got["WR"] / n, 3),
                           "wr_share_of_all_picks": round(base["WR"] / m, 3)}
out["trade_up_targets"] = bands
# Habits: net trade-downs per draft (downs - ups) for each team, odd vs even years
net = defaultdict(lambda: defaultdict(int))
for s, u, d, p in ups:
    net[u][s] -= 1
    net[d][s] += 1
teams = sorted(net)
odd = [st.mean(net[t][s] for s in range(2010, 2027) if s % 2) for t in teams]
even = [st.mean(net[t][s] for s in range(2010, 2027) if not s % 2) for t in teams]
mean_net = {t: sum(net[t].values()) / 17 for t in teams}
out["habit"] = {"net_trade_downs_odd_vs_even_corr": round(corr(odd, even), 2),
                "team_net_per_draft_sd": round(st.pstdev(mean_net.values()), 2),
                "most_trade_downs": sorted(((round(v, 2), t) for t, v in mean_net.items()), reverse=True)[:5],
                "most_trade_ups": sorted((round(v, 2), t) for t, v in mean_net.items())[:5],
                "deals_per_team_draft": round(2 * len(ups) / 17 / 32, 2)}
# Does the habit go with drafting better? (weighted AV vs a typical player at the pick, 2010-18 classes)
by_pick = defaultdict(list)
for (s, p), r in picks.items():
    if 2000 <= s <= 2018 and r["w_av"] not in ("", "NA"):
        by_pick[p].append(float(r["w_av"]))
exp = {k: st.mean(v) for k in range(1, 263) if (v := [x for j in range(max(1, k - 6), k + 7) for x in by_pick.get(j, [])])}
val = defaultdict(lambda: [0.0, 0.0])
for (s, p), r in picks.items():
    if 2010 <= s <= 2018 and r["w_av"] not in ("", "NA") and p in exp:
        t = ALIAS.get(r["team"], r["team"])
        val[t][0] += float(r["w_av"])
        val[t][1] += exp[p]
common = [t for t in teams if t in val]
out["habit"]["trade_down_habit_vs_drafting_value_corr"] = round(
    corr([mean_net[t] for t in common], [val[t][0] / val[t][1] for t in common]), 2)
# Big reaches (ESPN 2023 big board, top 100, from real_draft_ai.json): picked 20+ spots before his rank
ai = json.load(open(Path(__file__).parent / "real_draft_ai.json"))
reaches = [r for r in ai["board_vs_pick_2023"]["biggest_reaches"] if r[0] - r[1] >= 20]
out["reaches_2023"] = {"note": "top-100 ranked players picked 20+ spots before their rank, of 89 matched (one draft)",
                       "count": len(reaches), "biggest": max(r[0] - r[1] for r in reaches), "list": reaches}
json.dump(out, open(OUT, "w"), indent=1)
print(json.dumps(out, indent=1))
