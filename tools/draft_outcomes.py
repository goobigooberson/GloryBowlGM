# tools/draft_outcomes.py
# Turns draft_lab runs into the same career measures as the real NFL draft
# research (docs/research/real_draft.json, real_draft_summary.md): for each
# pick band, round and position x round, how many became starters for 3+
# seasons, 5+ seasons, made a Pro Bowl, never started, and how often they
# started in their 1st-4th seasons (real: tools' snap counts, starter = 50%+
# of his team's snaps; sim: a starter on the depth chart).

from collections import defaultdict

BANDS = [(1, 5), (6, 10), (11, 20), (21, 32), (33, 48), (49, 64), (65, 100), (101, 140), (141, 180),
         (181, 220), (221, 262)]
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
         "DE": "DE", "DT": "DT", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB", "K": "K/P", "P": "K/P",
         "LS": "K/P"}

# Real rookie-to-year-4 starter rates by pick band (nflverse snap counts 2013-25, drafts 2013-22;
# starter = played 50%+ of his team's offensive or defensive snaps that season). K/P/LS left out.
REAL_START_BY_YEAR = {
    "1-5": (0.82, 0.80, 0.80, 0.68), "6-10": (0.72, 0.82, 0.82, 0.68), "11-20": (0.67, 0.67, 0.68, 0.63),
    "21-32": (0.47, 0.60, 0.54, 0.52), "33-48": (0.46, 0.54, 0.52, 0.53), "49-64": (0.38, 0.53, 0.48, 0.43),
    "65-100": (0.22, 0.34, 0.34, 0.34), "101-140": (0.10, 0.21, 0.22, 0.24), "141-180": (0.09, 0.20, 0.18, 0.16),
    "181-220": (0.05, 0.08, 0.10, 0.11), "221-262": (0.02, 0.07, 0.05, 0.06)}
REAL_ROOKIE_SHARE_OF_STARTERS = 0.083   # drafted rookies among 50%-snap players (2013-25 average)


def band_of(pick):
    for a, b in BANDS:
        if a <= pick <= b:
            return f"{a}-{b}"
    return None


def careers(runs, min_seasons=8, skip_first=3):
    """Per drafted player: dict with band, round, group, starts (by season
    number 1..), pro bowls. Only classes with at least min_seasons seasons
    observed after the draft, and not the first skip_first classes (the
    league is still settling from its made-up start)."""
    out = []
    for r in runs:
        seasons = r["seasons"]
        last = max(seasons)
        first = min(seasons)
        league = r["league"]
        for pk in r["picks"]:
            yr = pk["season"]
            if yr - first < skip_first or last - yr + 1 < min_seasons:
                continue
            p = league.player(pk["pid"])
            starts, pb, on = [], 0, 0
            for s in range(yr, last + 1):
                snap = seasons.get(s, {}).get(p.id)
                started = bool(snap and snap[1])
                starts.append(started)
                if snap:
                    on += 1
                    pb += snap[3]
            out.append({"pid": pk["pid"], "season": yr, "team": pk["team"],
                        "band": band_of(pk["pick"]), "round": pk["round"], "pick": pk["pick"],
                        "group": GROUP[p.position], "pos": p.position, "starts": starts,
                        "pro_bowls": pb, "seasons_on_roster": on})
    return out


def summarize(cs, key):
    acc = defaultdict(list)
    for c in cs:
        acc[c[key]].append(c)
    res = {}
    for k, group in acc.items():
        n = len(group)
        s3 = sum(sum(c["starts"]) >= 3 for c in group) / n
        s5 = sum(sum(c["starts"]) >= 5 for c in group) / n
        pb = sum(c["pro_bowls"] > 0 for c in group) / n
        never = sum(sum(c["starts"]) == 0 for c in group) / n
        by_year = []
        for y in range(4):
            v = [c["starts"][y] for c in group if len(c["starts"]) > y and c["group"] != "K/P"]
            by_year.append(sum(v) / len(v) if v else 0)
        res[k] = {"n": n, "starter_3plus_seasons": s3, "starter_5plus_seasons": s5, "pro_bowl": pb,
                  "never_started": never, "start_by_year": by_year,
                  "seasons_on_roster": sum(c["seasons_on_roster"] for c in group) / n}
    return res


def rookie_share_of_starters(runs, skip_first=3):
    """Share of (non-specialist) starters who are drafted rookies, by season."""
    vals = []
    for r in runs:
        league = r["league"]
        rookies = defaultdict(set)
        for pk in r["picks"]:
            rookies[pk["season"]].add(pk["pid"])
        first = min(r["seasons"])
        for s, snap in r["seasons"].items():
            if s - first < skip_first:
                continue
            st = [pid for pid, v in snap.items() if v[1] and league.player(pid).position not in ("K", "P", "LS")]
            if st:
                vals.append(sum(pid in rookies[s] for pid in st) / len(st))
    return sum(vals) / len(vals) if vals else 0.0


def veteran_share(runs, skip_first=3, years=9):
    """Share of rostered players with `years`+ seasons of experience (real ~9%)."""
    vals = []
    for r in runs:
        first = min(r["seasons"])
        for s, snap in r["seasons"].items():
            if s - first < skip_first:
                continue
            vals.append(sum(v[4] >= years for v in snap.values()) / len(snap))
    return sum(vals) / len(vals) if vals else 0.0
