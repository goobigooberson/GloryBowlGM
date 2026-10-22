# tools/measures.py
# One definition of "how common is each stat line", used for both the real
# NFL seasons (build_benchmarks.py) and simulated seasons (realism_check.py),
# so the two are always compared on exactly the same terms.
#
# Plain Python only (no extra packages needed).
#
# A "player-season" is a dict with these keys (missing keys count as 0):
#   grp   position group: QB RB WR TE DL LB DB K P
#   pos   roster position (QB, RB, DE, DT, OLB, ILB, CB, S...)
#   team  team id or abbreviation
#   pass_yds pass_td pass_int pass_att rush_yds rush_att rush_td
#   rec_yds rec rec_td targets tackles tkl (solo) ast sacks def_int pd ff
#   tfl qb_hits fgm fga punts

# (name, stat key, positions to include (None = everyone), leaderboard ranks, thresholds)
SPECS = [
    ("pass_yds", "pass_yds", ("QB",), [1, 3, 5, 10, 15, 20, 25, 32], [3000, 3500, 4000, 4500, 5000]),
    ("pass_td", "pass_td", ("QB",), [1, 3, 5, 10, 20, 32], [20, 25, 30, 35, 40]),
    ("pass_int", "pass_int", ("QB",), [1, 5, 10, 20], [10, 15]),
    ("rush_yds", "rush_yds", None, [1, 3, 5, 10, 15, 20, 30, 40], [500, 750, 1000, 1250, 1500]),
    ("rush_att", "rush_att", None, [1, 5, 10, 20, 30], [150, 200, 250, 300]),
    ("rush_td", "rush_td", None, [1, 3, 5, 10, 20], [5, 8, 10, 12, 15]),
    ("qb_rush_yds", "rush_yds", ("QB",), [1, 3, 5, 10], [400, 600, 800]),
    ("rec_yds", "rec_yds", None, [1, 3, 5, 10, 20, 30, 40, 50], [800, 1000, 1200, 1400, 1600]),
    ("rec", "rec", None, [1, 3, 5, 10, 20, 30, 50], [70, 80, 90, 100, 110, 120]),
    ("rec_td", "rec_td", None, [1, 3, 5, 10, 20, 30], [6, 8, 10, 12, 14]),
    ("targets", "targets", None, [1, 5, 10, 20, 40], [100, 120, 140, 160]),
    ("wr_rec_yds", "rec_yds", ("WR",), [1, 5, 10, 20, 30], [1000, 1300]),
    ("te_rec_yds", "rec_yds", ("TE",), [1, 3, 5, 10], [700, 900, 1000]),
    ("te_rec", "rec", ("TE",), [1, 3, 5, 10], [60, 80, 100]),
    ("rb_rec", "rec", ("RB",), [1, 3, 5, 10, 20], [40, 50, 60, 80]),
    ("rb_rec_yds", "rec_yds", ("RB",), [1, 3, 5, 10], [400, 600]),
    ("tackles", "tackles", None, [1, 3, 5, 10, 20, 30, 50, 75, 100], [80, 100, 120, 140]),
    ("lb_tackles", "tackles", ("LB",), [1, 5, 10, 20, 30], [100, 120]),
    ("db_tackles", "tackles", ("DB",), [1, 5, 10, 20, 30], [80, 100]),
    ("dl_tackles", "tackles", ("DL",), [1, 5, 10, 20], [50, 70]),
    ("solo", "tkl", None, [1, 5, 10, 20], [60, 80, 100]),
    ("sacks", "sacks", None, [1, 3, 5, 10, 15, 20, 30, 50], [5, 8, 10, 12, 15]),
    ("dt_sacks", "sacks", ("DT",), [1, 3, 5, 10], [6, 8, 10]),
    ("edge_sacks", "sacks", ("DE", "OLB", "EDGE"), [1, 5, 10, 20], [10, 12]),
    ("int", "def_int", None, [1, 3, 5, 10, 20, 30], [3, 4, 5, 6, 7]),
    ("pd", "pd", None, [1, 5, 10, 20, 40], [10, 15, 20]),
    ("ff", "ff", None, [1, 5, 10, 20], [3, 4, 5]),
    ("tfl", "tfl", None, [1, 5, 10, 20, 40], [10, 15, 20]),
    ("qb_hits", "qb_hits", None, [1, 5, 10, 20], [15, 20, 30]),
    ("fgm", "fgm", ("K",), [1, 5, 10, 20, 32], [30, 35, 40]),
    ("fga", "fga", ("K",), [1, 5, 10, 20, 32], [35, 40, 45]),
    ("punts", "punts", ("P",), [1, 5, 10, 20, 32], [60, 70, 80]),
]

# Measures that can't be compared fairly, with the reason (shown in reports).
CAVEATS = {
    "fgm": "real teams change kickers during a season; sim teams keep one, so ranks below #5 run high",
    "fga": "real teams change kickers during a season; sim teams keep one, so ranks below #5 run high",
    "punts": "real teams change punters during a season; sim teams keep one",
    "edge_sacks": "real data labels many 3-4 edge rushers 'LB', so the real edge numbers are undercounted",
    "dt_sacks": "real data labels some interior linemen 'DE', so real DT numbers are a bit low",
    "dl_tackles": "real data labels 3-4 edge rushers 'LB'; the game's ends play that role, so real DL numbers run low "
                  "(real line + edge LBs 2021-25: #10 66-72, 50+ tackles 38-60 a season)",
}


def value(p, key):
    return p.get(key, 0) or 0


def measure(players):
    """{measure name: value} for one season's player-seasons."""
    out = {}
    for name, key, groups, ranks, thresholds in SPECS:
        vals = sorted((value(p, key) for p in players
                       if groups is None or p.get("grp") in groups or p.get("pos") in groups), reverse=True)
        for r in ranks:
            out[f"{name}#{r}"] = float(vals[r - 1]) if len(vals) >= r else 0.0
        for t in thresholds:
            out[f"{name}>={t}"] = float(sum(1 for v in vals if v >= t))
    return out


def team_rank_profile(players, key, groups=None, n=8):
    """Average of each team's #1, #2, ... #n player in a stat (how a team's
    production is shared among its players)."""
    by_team = {}
    for p in players:
        if groups is not None and p.get("grp") not in groups:
            continue
        v = value(p, key)
        if v > 0:
            by_team.setdefault(p["team"], []).append(v)
    if not by_team:
        return [0.0] * n
    rows = []
    for vals in by_team.values():
        vals = sorted(vals, reverse=True)[:n]
        rows.append(vals + [0.0] * (n - len(vals)))
    return [sum(r[i] for r in rows) / len(rows) for i in range(n)]


def target_share_profile(players, n=6):
    """Average share of team targets for each team's #1, #2... target."""
    by_team = {}
    for p in players:
        if value(p, "targets") > 0:
            by_team.setdefault(p["team"], []).append(value(p, "targets"))
    rows, tops = [], []
    for vals in by_team.values():
        tot = sum(vals)
        vals = sorted(vals, reverse=True)
        share = [v / tot for v in vals[:n]] + [0.0] * max(0, n - len(vals))
        rows.append(share)
        tops.append(share[0])
    prof = [sum(r[i] for r in rows) / len(rows) for i in range(n)]
    tops.sort()
    return prof, tops[int(0.9 * (len(tops) - 1))], tops[-1]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def median(xs):
    xs = sorted(xs)
    if not xs:
        return 0.0
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def stdev(xs):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
