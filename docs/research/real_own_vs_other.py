# docs/research/real_own_vs_other.py
# Real data for tools/ai_views_check.py: run  python docs/research/real_own_vs_other.py
# How well do real teams know pros? Own re-signs vs players signed from other teams.
# Price (APY share of cap, ranked within position and year) vs what he gave the
# signing team: his share of that team's snaps in the next season(s).
import csv, gzip, math, os, random, statistics, sys
from collections import defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NV = os.path.join(ROOT, "tools", "data", "nflverse")

TEAM = {"Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
        "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN",
        "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
        "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC", "Rams": "LA", "Dolphins": "MIA",
        "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
        "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Seahawks": "SEA", "Buccaneers": "TB",
        "Titans": "TEN", "Commanders": "WAS"}
ALIAS = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS"}
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "LT": "OT", "RT": "OT",
         "LG": "IOL", "RG": "IOL", "C": "IOL", "ED": "EDGE", "IDL": "IDL", "LB": "LB",
         "CB": "CB", "S": "S"}
DEF = {"EDGE", "IDL", "LB", "CB", "S"}


def rd(path):
    return csv.DictReader(gzip.open(path, "rt", encoding="utf-8"))


otc2pfr = {}
for r in rd(os.path.join(NV, "players", "players.csv.gz")):
    if r["otc_id"] and r["pfr_id"]:
        otc2pfr[r["otc_id"]] = r["pfr_id"]

# Per season: team snaps in each game, each player's snaps by team, his last team of the season.
snaps = defaultdict(float)            # (season, pfr, team, side) -> snaps
team_tot = defaultdict(float)         # (season, team, side) -> snaps (sum of each game's max)
last_team = {}                        # (season, pfr) -> team in his last game
for season in range(2013, 2024):
    game_max = defaultdict(float)
    last = {}
    for r in rd(os.path.join(NV, "snap_counts", f"snap_counts_{season}.csv.gz")):
        if r["game_type"] != "REG":
            continue
        t = ALIAS.get(r["team"], r["team"])
        wk = int(r["week"])
        for side, col, pct in (("off", "offense_snaps", "offense_pct"), ("def", "defense_snaps", "defense_pct")):
            s = float(r[col] or 0)
            p = float(r[pct] or 0)
            if s > 0:
                snaps[(season, r["pfr_player_id"], t, side)] += s
                if p > 0:
                    game_max[(r["game_id"], t, side)] = max(game_max[(r["game_id"], t, side)], s / p)
        if r["pfr_player_id"] not in last or wk >= last[r["pfr_player_id"]][0]:
            last[r["pfr_player_id"]] = (wk, t)
    for (g, t, side), v in game_max.items():
        team_tot[(season, t, side)] += v
    for pid, (wk, t) in last.items():
        last_team[(season, pid)] = t


def share(season, pid, t, side):
    tot = team_tot.get((season, t, side))
    return snaps.get((season, pid, t, side), 0.0) / tot if tot else None


rows = []
for r in rd(os.path.join(NV, "contracts", "historical_contracts.csv.gz")):
    g = GROUP.get(r["position"])
    t = TEAM.get(r["team"])
    if not g or not t:
        continue
    y = int(r["year_signed"] or 0)
    if not 2014 <= y <= 2021:
        continue
    if r["draft_year"] not in ("", "NA") and int(r["draft_year"]) == y:
        continue                     # his rookie deal
    pct = float(r["apy_cap_pct"] or 0)
    if pct < 0.01:
        continue                     # minimum-level churn
    pid = otc2pfr.get(r["otc_id"])
    if not pid:
        continue
    prev = last_team.get((y - 1, pid))
    if prev is None:
        continue                     # didn't play the year before: unknown to everyone
    side = "def" if g in DEF else "off"
    own = prev == t
    out1 = share(y, pid, t, side)
    out2 = share(y + 1, pid, t, side)
    before = share(y - 1, pid, prev, side)
    if out1 is None or out2 is None or before is None:
        continue
    rows.append(dict(g=g, y=y, pct=pct, own=own, out1=out1, out2=out2, before=before,
                     years=int(r["years"] or 1), name=r["player"]))

print("contracts used:", len(rows), " own:", sum(r["own"] for r in rows), " other:", sum(not r["own"] for r in rows))


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    rk = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[order[k]] = (i + j) / 2
        i = j + 1
    return rk


def pearson(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


# Price percentile within position group and year (all market deals together, own and other),
# so "price" means the same thing in both groups.
by = defaultdict(list)
for r in rows:
    by[(r["g"], r["y"])].append(r)
for grp in by.values():
    rk = ranks([r["pct"] for r in grp])
    n = len(grp)
    for r, k in zip(grp, rk):
        r["pp"] = (k + 0.5) / n if n > 1 else 0.5


def z(x):
    # normal score of a percentile
    from statistics import NormalDist
    return NormalDist().inv_cdf(min(0.999, max(0.001, x)))


def report(label, sel, key):
    a = [z(r["pp"]) for r in sel]
    b = [r[key] for r in sel]
    print(f"  {label:<26} n={len(sel):5d}  corr(price, snap share)={pearson(a, b):.3f}"
          f"  spearman={pearson(ranks(a), ranks(b)):.3f}  mean share={statistics.fmean(b):.3f}")


def boot(sel_own, sel_other, key, n=400):
    rng = random.Random(1)
    diffs = []
    for _ in range(n):
        o = [rng.choice(sel_own) for _ in sel_own]
        t = [rng.choice(sel_other) for _ in sel_other]
        diffs.append(pearson([z(r["pp"]) for r in o], [r[key] for r in o])
                     - pearson([z(r["pp"]) for r in t], [r[key] for r in t]))
    diffs.sort()
    return diffs[int(0.05 * n)], diffs[int(0.95 * n)]


for key, lab in (("out1", "first season"), ("out2", "second season")):
    print(f"\n== Price vs share of the signing team's snaps, {lab} ==")
    own = [r for r in rows if r["own"]]
    oth = [r for r in rows if not r["own"]]
    report("own (re-sign/extension)", own, key)
    report("other (from another team)", oth, key)
    lo, hi = boot(own, oth, key)
    print(f"  own - other corr difference, 90% range: {lo:+.3f} .. {hi:+.3f}")
    for g in ("QB", "RB", "WR", "TE", "OT", "IOL", "EDGE", "IDL", "LB", "CB", "S"):
        o = [r for r in own if r["g"] == g]
        t = [r for r in oth if r["g"] == g]
        if len(o) > 20 and len(t) > 20:
            print(f"    {g:<5} own {pearson([z(r['pp']) for r in o], [r[key] for r in o]):.2f} (n={len(o)})"
                  f"   other {pearson([z(r['pp']) for r in t], [r[key] for r in t]):.2f} (n={len(t)})")

# "Busts": paid like a starter (top 40% of price at his position) but gave the team under 25% of
# its snaps in the first season (benched, cut or hurt).
print("\n== Paid like a starter (top 40% price), gave under 25% of snaps in season 1 ==")
for lab, sel in (("own", [r for r in rows if r["own"]]), ("other", [r for r in rows if not r["own"]])):
    top = [r for r in sel if r["pp"] >= 0.6]
    bust1 = sum(r["out1"] < 0.25 for r in top) / len(top)
    bust2 = sum(r["out2"] < 0.25 for r in top) / len(top)
    print(f"  {lab:<6} n={len(top):4d}  season 1: {bust1:.1%}   season 2: {bust2:.1%}")

# How much does what he did last year (on his old team) explain? Partial view: price vs share,
# with last season's share held about equal (players who were full-time starters last year).
print("\n== Full-time last season (60%+ of his old team's snaps) ==")
for key in ("out1", "out2"):
    own = [r for r in rows if r["own"] and r["before"] >= 0.6]
    oth = [r for r in rows if not r["own"] and r["before"] >= 0.6]
    report(f"own {key}", own, key)
    report(f"other {key}", oth, key)

print("\n== By how much tape there is: last season's share of his old team's snaps ==")
for lo, hi in ((0.0, 0.3), (0.3, 0.6), (0.6, 1.1)):
    for key in ("out1",):
        own = [r for r in rows if r["own"] and lo <= r["before"] < hi]
        oth = [r for r in rows if not r["own"] and lo <= r["before"] < hi]
        report(f"own  {lo:.1f}-{hi:.1f} {key}", own, key)
        report(f"other {lo:.1f}-{hi:.1f} {key}", oth, key)
        top_o = [r for r in own if r["pp"] >= 0.6]
        top_t = [r for r in oth if r["pp"] >= 0.6]
        if top_o and top_t:
            print(f"     paid like a starter, <25% snaps: own {sum(r['out1'] < 0.25 for r in top_o) / len(top_o):.1%} (n={len(top_o)})"
                  f"  other {sum(r['out1'] < 0.25 for r in top_t) / len(top_t):.1%} (n={len(top_t)})")
