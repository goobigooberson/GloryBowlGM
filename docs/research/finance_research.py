# Real NFL team finances, for engine/finances.py (Oct 26, team-finances side session).
# Writes real_finance.json (measured here) and keeps the published numbers in one place.
#   python docs/research/finance_research.py          (downloads ESPN attendance once, ~1 min)
#
# MEASURED HERE (data):
# - Home attendance by team, 2008-2025 (ESPN's attendance pages, which use the tickets each
#   team reports; 2020 had no fans and is left out, 2021 is kept). Joined with each team's
#   record and home stadium from nflverse games (tools/data/nflverse/schedules/games.csv.gz).
#   From these: the league average and the spread across teams each year; how much a team's
#   crowd moves from one year to the next; how it follows this season's and last season's
#   record and playoffs; what a new stadium does in its first ten years.
#
# PUBLISHED NUMBERS (data, copied with their sources; see PUBLISHED below):
# - Revenue by team, the 2024 season (Forbes 2025 list, via Wikipedia's table, fetched Oct 26).
# - Where an average team's revenue comes from, the 2025 season (Sportico, "How NFL Teams and
#   Owners Made $23.5 Billion Last Year", 2026).
# - The Packers' reports (the only team whose books are public), fiscal years to March.
# - Ticket prices: Team Marketing Report's Fan Cost Index (2023 by team, 2024 averages).
# - Gate receipts by team (Sportico, 2021, 2022, 2024 seasons).
# - TV households by market (Nielsen DMA estimates 2024-25), for the game's market sizes.

import csv
import gzip
import html
import json
import os
import re
import statistics
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(HERE, "real_attendance.json")
OUT = os.path.join(HERE, "real_finance.json")
YEARS = list(range(2008, 2026))   # ESPN's pages before 2008 are missing teams

# ESPN's link names and nflverse's abbreviations, by franchise (moves keep the franchise).
ESPN = {"lar": "RAMS", "stl": "RAMS", "lac": "CHARGERS", "sd": "CHARGERS", "lv": "RAIDERS", "oak": "RAIDERS",
        "wsh": "WAS"}
NFLV = {"LA": "RAMS", "STL": "RAMS", "LAC": "CHARGERS", "SD": "CHARGERS", "LV": "RAIDERS", "OAK": "RAIDERS"}

PUBLISHED = {
    # Forbes 2025 list (2024 season), $M: revenue, operating income. Via Wikipedia's
    # "Forbes list of the most valuable NFL teams" (fetched Oct 26, 2026).
    "forbes_2024": {
        "DAL": (1234, 629), "LA": (764, 244), "NYG": (707, 181), "NE": (762, 222), "SF": (723, 115),
        "PHI": (688, 117), "CHI": (629, 80), "NYJ": (663, 180), "LV": (832, 179), "WAS": (644, 116),
        "MIA": (656, 63), "HOU": (687, 156), "DEN": (645, 103), "SEA": (624, 143), "GB": (719, 83),
        "TB": (629, 130), "PIT": (619, 137), "CLE": (685, 90), "ATL": (612, 37), "TEN": (582, 93),
        "MIN": (609, 70), "KC": (610, 66), "BAL": (621, 115), "LAC": (593, 105), "BUF": (585, 104),
        "IND": (593, 109), "CAR": (588, 36), "JAX": (552, 106), "ARI": (571, 62), "DET": (585, 21),
        "NO": (607, 115), "CIN": (573, 50)},
    # Sportico 2026 (the 2025 season): all 32 teams $23.5B; national $14.5B (62%, about $453M a
    # team); tickets and suites $4.35B (19%, including about $29M a team of visiting teams'
    # share); team sponsorship $2.6B (about 11%; naming rights about a tenth of it);
    # concessions, parking, team stores and non-NFL events $1.7B (7%); local media under 2%.
    # Profit (EBITDA) $127M a team on average, Broncos about $51M to Cowboys about $510M.
    # Player costs: cap $279M + benefits $74M = $353M a team. Only the Cowboys and Rams have
    # more local than national revenue. Cowboys suites about $135M, sponsorship $300M.
    "sportico_2025": {"total_b": 23.5, "national": 0.62, "tickets_suites": 0.19, "sponsorship": 0.11,
                      "concessions_parking_events": 0.07, "local_media": 0.02, "vts_per_team_m": 29,
                      "profit_avg_m": 127, "profit_low_m": 51, "profit_high_m": 510,
                      "cap_m": 279, "benefits_m": 74},
    # Packers (fiscal years end March 31; FY2025 = the 2024 season). $M.
    # total, national, local, operating profit. Sources: Packers.com and AP each July.
    "packers": {
        2020: (507, 296, 211, 70), 2021: (371, 309, 62, -39), 2022: (579, 347, 232, 78),
        2023: (610, 375, 235, 69), 2024: (654, 402, 252, 60), 2025: (719, 433, 286, 84),
        2026: (753, 453, 300, -1)},
    # Fan Cost Index (Team Marketing Report): league average ticket (non-premium, weighted).
    # 2019 $102.35, 2023 $120.94, 2024 $136.38 (all 32 over $100 for the first time; lowest
    # Chargers $100.78). Family of four (4 tickets, 4 sodas, 4 hot dogs, 2 beers, 2 caps,
    # parking): 2019 $540.52, 2023 $631.63, 2024 $691.41 (lowest Atlanta $557.62, Green Bay
    # $938.09). No 2025 edition.
    "fci_avg_ticket": {2019: 102.35, 2023: 120.94, 2024: 136.38},
    "fci_family": {2019: 540.52, 2023: 631.63, 2024: 691.41},
    # 2023 by team (general ticket, premium ticket); TMR via DolphinsTalk/LVSportsBiz.
    "fci_2023": {
        "LV": (168.83, 370.28), "SF": (161.33, 491.68), "NE": (142.74, 439.57), "GB": (141.48, 354.57),
        "PHI": (139.01, 409.65), "DEN": (131.91, 488.56), "KC": (131.81, 290.06), "CHI": (130.29, 357.36),
        "SEA": (127.71, 297.81), "PIT": (127.04, 295.93), "NYG": (126.74, 459.08), "WAS": (124.80, 396.00),
        "TB": (124.43, 294.34), "MIN": (123.37, 367.08), "CLE": (122.18, 306.10), "BAL": (120.27, 312.93),
        "HOU": (117.45, 376.47), "DAL": (116.69, 408.93), "CAR": (115.45, 353.05), "NYJ": (112.56, 393.09),
        "NO": (111.97, 288.80), "ATL": (111.54, 430.61), "TEN": (107.37, 250.11), "DET": (107.31, 256.85),
        "ARI": (98.54, None), "BUF": (101.64, None), "CIN": (101.78, None), "JAX": (102.22, None),
        "LA": (103.90, None)},
    # Yearly change in the average ticket, 2023 (TMR, the 24 teams listed with a change), %.
    "fci_2023_change": [10, 11.4, 8.6, 4.9, 9.4, 10.2, 14.5, 0, 3.8, 5.8, 4.1, 20, 1.6, 5.6, 8.9, 0, 0, 8.2,
                        10.4, 14.6, 2.2, 0.8, 6.7, 16.8],
    # Cash paid to players, 2026 season to date (OverTheCap "Cash Spending", fetched Oct 26,
    # 2026; cap $301.2M): mean $330.8M (1.10 x cap), spread $32.6M, $245.7M to $391.5M.
    "otc_cash_2026": {"mean_m": 330.8, "sd_m": 32.6, "min_m": 245.7, "max_m": 391.5, "cap_m": 301.2},
    # Net gate receipts (general and club seats, after local taxes, before the visitors'
    # share; suites not included), $M. Sportico.
    "gate": {"2021": {"high": ("LV", 119), "low": ("DET", 51)},
             "2022": {"high": ("SF", 136), "low": ("ARI", 58)},
             "2024": {"SF": 176, "DAL": 136, "PHI": 130, "DEN": 129, "MIA": 127, "LA_low": None,
                      "TEN": 81, "IND": 83.3, "ARI": 83.4}},
    # Playoff games: the league keeps the ticket money (pays the home team's costs); the home
    # team keeps its concessions and parking, roughly $1-2M a game (CNBC; Huddle Up).
    # New stadiums: US studies find the attendance boost gone within about 5-10 years
    # (Bradbury 2019; Szymanski 2023, as reviewed by van Ours 2024).
    # TV households (millions), Nielsen 2024-25 estimates, for the game's 32 markets.
    "tv_homes_m": {
        "New York": 7.49, "Los Angeles": 5.84, "Chicago": 3.65, "Dallas": 3.26, "Philadelphia": 3.15,
        "Houston": 2.80, "Atlanta": 2.76, "Washington": 2.63, "Boston": 2.58, "San Francisco": 2.54,
        "Phoenix": 2.21, "Seattle": 2.10, "Tampa": 2.10, "Detroit": 1.90, "Minneapolis": 1.86,
        "Denver": 1.83, "Miami": 1.73, "Charlotte": 1.48, "Portland": 1.30, "Cleveland": 1.47,
        "St. Louis": 1.23, "Indianapolis": 1.18, "Nashville": 1.20, "Baltimore": 1.15, "San Diego": 1.12,
        "Pittsburgh": 1.13, "San Antonio": 1.04, "Kansas City": 1.03, "Cincinnati": 0.93,
        "Las Vegas": 0.84, "New Orleans": 0.63, "Buffalo": 0.64, "Green Bay": 0.45},
}


def fetch_attendance():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    out = {}
    for y in YEARS:
        req = urllib.request.Request(f"https://www.espn.com/nfl/attendance/_/year/{y}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
        rows = {}
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
            m = re.search(r"/name/([a-z]+)/", r)
            cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            if not m or len(cells) < 11 or not cells[4].replace(",", "").isdigit():
                continue
            ab = m.group(1)
            rows[ESPN.get(ab, ab.upper())] = {"home_g": int(cells[2]), "home_avg": int(cells[4].replace(",", ""))}
        out[str(y)] = rows
        print(y, len(rows))
        time.sleep(1)
    with open(CACHE, "w") as f:
        json.dump(out, f, indent=0)
    return out


def team_seasons():
    """(franchise, season) -> {"w", "g", "playoffs", "stadium"} from nflverse games."""
    path = os.path.join(ROOT, "tools", "data", "nflverse", "schedules", "games.csv.gz")
    out = defaultdict(lambda: {"w": 0.0, "g": 0, "playoffs": False, "st": defaultdict(int)})
    with gzip.open(path, "rt") as f:
        for g in csv.DictReader(f):
            if not g["home_score"]:
                continue
            s = int(g["season"])
            hs, as_ = int(g["home_score"]), int(g["away_score"])
            for side, mine, theirs in (("home_team", hs, as_), ("away_team", as_, hs)):
                t = NFLV.get(g[side], g[side])
                if g["game_type"] == "REG":
                    d = out[(t, s)]
                    d["g"] += 1
                    d["w"] += 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0
                    if side == "home_team" and g["location"] == "Home":
                        d["st"][g["stadium_id"]] += 1
                else:
                    out[(t, s)]["playoffs"] = True
    for d in out.values():
        d["stadium"] = max(d["st"], key=d["st"].get) if d["st"] else None
        d["wp"] = d["w"] / d["g"] if d["g"] else 0.5
    return out


def ols(X, y):
    """Least squares with an intercept: coefficients [b0, b1, ...] and R^2 (no numpy)."""
    n, k = len(y), len(X[0]) + 1
    A = [[1.0] + list(r) for r in X]
    AtA = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Aty = [sum(A[i][a] * y[i] for i in range(n)) for a in range(k)]
    M = [row[:] + [v] for row, v in zip(AtA, Aty)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(k):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    beta = [M[i][k] / M[i][i] for i in range(k)]
    pred = [sum(b * a for b, a in zip(beta, row)) for row in A]
    my = statistics.mean(y)
    ss = sum((v - my) ** 2 for v in y)
    return beta, 1 - sum((v - p) ** 2 for v, p in zip(y, pred)) / ss


def main():
    att = fetch_attendance()
    ts = team_seasons()
    out = {"source": "ESPN attendance 2008-2025 (2020 left out) + nflverse games", "years": {}}
    # League average and spread across teams, by year.
    for y in YEARS:
        if y == 2020:
            continue
        v = [r["home_avg"] for r in att[str(y)].values()]
        out["years"][y] = {"avg": round(statistics.mean(v)), "sd": round(statistics.pstdev(v)),
                           "min": min(v), "max": max(v)}

    # Each team-season's crowd against the same team's average in the same stadium
    # ("era"), as a share: 1.03 = 3% above its usual crowd there.
    eras = defaultdict(list)
    rows = []
    for y in YEARS:
        if y == 2020:
            continue
        for t, r in att[str(y)].items():
            d = ts.get((t, y))
            if not d or not d["stadium"]:
                continue
            rows.append({"t": t, "y": y, "avg": r["home_avg"], "st": d["stadium"], "wp": d["wp"],
                         "po": d["playoffs"]})
            eras[(t, d["stadium"])].append(r["home_avg"])
    by = {(r["t"], r["y"]): r for r in rows}
    for r in rows:
        e = eras[(r["t"], r["st"])]
        r["rel"] = r["avg"] / statistics.mean(e)
        r["rel_peak"] = r["avg"] / max(e)
        r["era_n"] = len(e)

    # Year-to-year change of a team's crowd in the same stadium (and not across 2020).
    ch = []
    for r in rows:
        p = by.get((r["t"], r["y"] - 1)) or (by.get((r["t"], r["y"] - 2)) if r["y"] == 2021 else None)
        if p and p["st"] == r["st"]:
            ch.append(r["avg"] / p["avg"] - 1)
    ch.sort()
    out["yoy_change"] = {"n": len(ch), "sd": round(statistics.pstdev(ch), 4),
                         "median_abs": round(statistics.median(abs(c) for c in ch), 4),
                         "p05": round(ch[len(ch) // 20], 4), "p95": round(ch[-len(ch) // 20], 4)}
    rp = sorted(r["rel_peak"] for r in rows if r["era_n"] >= 5)
    out["below_era_peak"] = {"median": round(statistics.median(rp), 4), "p10": round(rp[len(rp) // 10], 4),
                             "p25": round(rp[len(rp) // 4], 4)}

    # How the crowd follows winning: rel ~ this season's win% + last season's + playoffs last
    # season (stadiums with 5+ seasons, the stadium's first two years left out).
    X, Y = [], []
    for r in rows:
        p = by.get((r["t"], r["y"] - 1)) or (by.get((r["t"], r["y"] - 2)) if r["y"] == 2021 else None)
        if not p or r["era_n"] < 5:
            continue
        first = min(q["y"] for q in rows if q["t"] == r["t"] and q["st"] == r["st"])
        if r["y"] - first < 2:
            continue
        p2 = by.get((r["t"], r["y"] - 2))
        X.append((r["wp"] - 0.5, p["wp"] - 0.5, (p2["wp"] - 0.5) if p2 else 0.0, 1.0 if p["po"] else 0.0))
        Y.append(r["rel"] - 1)
    beta, r2 = ols(X, Y)
    # The same without odd years (moves, tarps, games abroad: crowd more than 10% off the
    # stadium's usual), which hide the winning effect.
    keep = [i for i, v in enumerate(Y) if abs(v) <= 0.10]
    tb, tr2 = ols([X[i] for i in keep], [Y[i] for i in keep])
    out["winning_trimmed"] = {"n": len(keep), "beta": [round(b, 4) for b in tb], "r2": round(tr2, 3),
                              "resid_sd": round(statistics.pstdev(
                                  [Y[i] - tb[0] - sum(b * x for b, x in zip(tb[1:], X[i])) for i in keep]), 4)}
    out["winning"] = {"n": len(Y), "terms": ["const", "win% this season - .5", "win% last season - .5",
                                             "win% 2 seasons ago - .5", "playoffs last season"],
                      "beta": [round(b, 4) for b in beta], "r2": round(r2, 3),
                      "note": "rel = crowd / the team's average in that stadium, minus 1"}

    # New stadiums: crowd in years 1-10 against the old stadium's last 3 years (same team).
    opens = []
    for (t, st), e in eras.items():
        ys = sorted(r["y"] for r in rows if r["t"] == t and r["st"] == st)
        first = ys[0]
        old = [by[(t, y)] for y in range(first - 4, first) if (t, y) in by and by[(t, y)]["st"] != st]
        if first <= YEARS[0] + 1 or len(old) < 2:
            continue
        base = statistics.mean(o["avg"] for o in old[-3:])
        path = {y - first + 1: round(by[(t, y)]["avg"] / base, 3) for y in ys if y - first < 10}
        opens.append({"team": t, "opened": first, "stadium": st, "vs_old": path,
                      "era_rel": {y - first + 1: round(by[(t, y)]["rel"], 3) for y in ys if y - first < 10}})
    out["new_stadiums"] = opens
    curve = defaultdict(list)
    for o in opens:
        for k, v in o["era_rel"].items():
            curve[k].append(v)
    out["new_stadium_curve"] = {k: round(statistics.mean(v), 3) for k, v in sorted(curve.items()) if len(v) >= 3}
    out["published"] = PUBLISHED

    f24 = PUBLISHED["forbes_2024"]
    rev = sorted(v[0] for v in f24.values())
    out["forbes_2024_summary"] = {"mean": round(statistics.mean(rev)), "sd": round(statistics.pstdev(rev)),
                                  "median": statistics.median(rev), "min": rev[0], "max": rev[-1],
                                  "mean_without_dal": round(statistics.mean(rev[:-1])),
                                  "sd_without_dal": round(statistics.pstdev(rev[:-1])),
                                  "op_income_mean": round(statistics.mean(v[1] for v in f24.values())),
                                  "op_income_median": statistics.median(v[1] for v in f24.values())}
    fci = [v[0] for v in PUBLISHED["fci_2023"].values()]
    out["fci_2023_summary"] = {"n": len(fci), "mean": round(statistics.mean(fci), 2),
                               "sd": round(statistics.pstdev(fci), 2), "min": min(fci), "max": max(fci)}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)

    print("League average home crowd by year:", {y: v["avg"] for y, v in out["years"].items()})
    print("Spread across teams (sd):", {y: v["sd"] for y, v in out["years"].items()})
    print("Year-to-year change, same stadium:", out["yoy_change"])
    print("Below the stadium's best year:", out["below_era_peak"])
    print("Winning:", out["winning"])
    print("Winning (odd years out):", out["winning_trimmed"])
    print("New stadium (crowd vs its own average there), by year:", out["new_stadium_curve"])
    for o in opens:
        print("  ", o["team"], o["opened"], o["vs_old"])
    print("Forbes 2024 revenue:", out["forbes_2024_summary"])
    print("FCI 2023 ticket:", out["fci_2023_summary"])


if __name__ == "__main__":
    main()
