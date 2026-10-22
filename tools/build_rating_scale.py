# tools/build_rating_scale.py
# Rebuilds the table in engine/scale.py that turns the engine's internal
# ratings into the ratings shown on screen (Blake, Oct 21: "median NFL
# player = 50").
#
# How: generate several fresh leagues, pool every rostered player's internal
# overall rating (all positions together), and map each internal value to
#     shown = 50 + 16 x (how many standard deviations above the median it sits)
# using the pooled distribution. So the typical NFL player shows 50, about 1
# in 30 shows 80+, and about 1 in 160 shows 90+. One curve for every position,
# so positions keep their differences (QBs scarcest, most kickers good).
#
# Kickers, punters and long snappers get their own curve (SPECIALIST): a
# starting specialist at a given rank among starting specialists shows what
# a starter at that rank among all other starters shows. Their ratings run
# much higher than other positions', so on the main curve they took about a
# third of the 80+ spots.
#
# Only needed if player generation changes. Run from the project folder:
#     python tools/build_rating_scale.py
# then paste the printed tables into engine/scale.py (_MIDDLE from SHOWN's
# 45..92 entries, and _SPECIALIST).

import sys
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.league import create_league  # noqa: E402

LEAGUES = 8
MIDPOINT, SPREAD = 50, 16


SPECIALISTS = ("K", "P", "LS")
STARTERS = {"QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 1, "T": 2, "G": 2, "C": 1, "DE": 2, "DT": 2, "OLB": 2,
            "ILB": 1, "CB": 2, "S": 2}


def specialist_table(leagues, shown_main):
    """Kickers, punters and snappers (Blake, Oct 21: rated among their own
    kind): a starting specialist at a given rank among starting specialists
    shows what a starter at that rank among all other starters shows."""
    starters, specs, spec_backups = [], [], []
    for lg in leagues:
        for t in lg.teams:
            for position, n in STARTERS.items():
                g = sorted((p.overall() for p in lg.team_players(t.id) if p.position == position), reverse=True)
                starters += [shown_main[v] for v in g[:n]]
            for position in SPECIALISTS:
                g = sorted((p.overall() for p in lg.team_players(t.id) if p.position == position), reverse=True)
                specs += g[:1]
                spec_backups += g[1:]
    starters.sort()
    n_st, n_sp = len(starters), len(specs)
    counts = [0] * 101
    for v in specs:
        counts[v] += 1
    table, below = {}, 0
    for v in range(101):
        if counts[v] >= 3:
            q = (below + counts[v] / 2) / n_sp
            table[v] = starters[min(n_st - 1, int(q * n_st))]
        below += counts[v]
    known = sorted(table)
    lo, hi = known[0], known[-1]
    out = []
    for v in range(101):
        if v < lo:
            x = table[lo] - 1.5 * (lo - v)          # backups and worse: a steady slope down
        elif v > hi:
            x = table[hi] + 1.5 * (v - hi)
        elif v in table:
            x = table[v]
        else:
            a = max(k for k in known if k < v)
            b = min(k for k in known if k > v)
            x = table[a] + (table[b] - table[a]) * (v - a) / (b - a)
        out.append(max(1.0, min(99.0, round(x, 1))))
    for i in range(1, 101):
        out[i] = max(out[i], out[i - 1])
    return out


def main():
    values = []
    leagues = []
    for seed in range(901, 901 + LEAGUES):
        lg = create_league(season=2026, seed=seed, camp=False)
        leagues.append(lg)
        # The main curve: every position but kickers, punters and snappers (they have their own).
        values += [p.overall() for p in lg.players if p.id in lg.rosters and p.position not in SPECIALISTS]
    n = len(values)
    counts = [0] * 101
    for v in values:
        counts[v] += 1
    nd = NormalDist()
    table = {}
    below = 0
    for v in range(101):
        if counts[v] >= 5:      # enough players at this value to place it reliably
            mid_rank = (below + counts[v] / 2) / n
            table[v] = MIDPOINT + SPREAD * nd.inv_cdf(mid_rank)
        below += counts[v]
    known = sorted(table)
    lo, hi = known[0], known[-1]
    # Beyond the data, continue with the slope of the nearest 10 points.
    slope_lo = (table[lo + 10] - table[lo]) / 10
    slope_hi = (table[hi] - table[hi - 10]) / 10
    shown = []
    for v in range(101):
        if v < lo:
            x = table[lo] - slope_lo * (lo - v)
        elif v > hi:
            x = table[hi] + slope_hi * (v - hi)
        elif v in table:
            x = table[v]
        else:                    # a gap inside the data: straight line between neighbors
            a = max(k for k in known if k < v)
            b = min(k for k in known if k > v)
            x = table[a] + (table[b] - table[a]) * (v - a) / (b - a)
        shown.append(round(x, 1))
    for i in range(1, 101):      # always rising
        shown[i] = max(shown[i], shown[i - 1] + 0.1)
    print(f"# from {LEAGUES} leagues, {n} rostered players; internal 0..100 -> shown")
    print("SHOWN = [")
    for i in range(0, 101, 10):
        print("    " + ", ".join(f"{x:.1f}" for x in shown[i:i + 10]) + ",")
    print("]")
    # The specialist curve, against the main scale as engine/scale.py uses it.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from engine.scale import shown as main_shown
    spec = specialist_table(leagues, [main_shown(v, None) for v in range(101)])
    print("SPECIALIST = [")
    for i in range(0, 101, 10):
        print("    " + ", ".join(f"{x:.1f}" for x in spec[i:i + 10]) + ",")
    print("]")


if __name__ == "__main__":
    main()
