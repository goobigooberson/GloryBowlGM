# tools/career_mix_check.py
# Who is on NFL rosters, by age and experience, and how careers end: real vs
# simulated on the same yardsticks (Oct 24; Blake: player aging "extremely
# fine tuned and accurate").
#
#   1. Week-1 rosters (the 53 plus injured reserve / PUP) by experience
#      (pro seasons before this one) and by age, per position group; the
#      share of 9+ year veterans.
#   2. Starters (each team's 11 offensive and 11 defensive players with the
#      most regular-season snaps) by age and experience.
#   3. Leaving the league: of the players on a week-1 roster, the share on no
#      week-1 roster next season, by experience and by age.
#   4. Career length: from those yearly odds, the share of rookies still on a
#      week-1 roster N seasons later (a player who sits out a season and comes
#      back counts as having left; the same for the game).
#   5. Age at the last season (players leaving the league), by position group.
#   6. (game only) starters' average overall rating by season, to see whether
#      a league's talent drifts.
#
# Real: nflverse weekly rosters 2013-2026 (week 1; statuses ACT, INA, RES,
# PUP), birth dates; snap counts 2013-2025 for starters. Experience is
# season - rookie year, as nflverse counts it. Transitions into 2020 and 2021
# (COVID opt-outs) are left out of "leaving".
# Game: files from tools/injury_careers_sim.py run (<out>.jsonl and the
# <out>.w1.jsonl beside it). The first SKIP seasons of a generated league are
# left out (its made-up veterans start from a fitted mix, not from careers).
#
#   python tools/career_mix_check.py [sim1.jsonl ...] [--skip N]

import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

DATA = Path(__file__).resolve().parent / "data"
GROUP = {"QB": "QB", "RB": "RB", "HB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
         "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL", "OL": "OL",
         "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL",
         "OLB": "LB", "ILB": "LB", "MLB": "LB", "LB": "LB",
         "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "SAF": "DB", "DB": "DB",
         "K": "K/P", "P": "K/P", "LS": "K/P"}
GROUPS = ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K/P", "ALL"]
OFFENSE = {"QB", "RB", "WR", "TE", "OL"}
EXP_BANDS = [(0, 0, "0"), (1, 2, "1-2"), (3, 4, "3-4"), (5, 6, "5-6"), (7, 8, "7-8"), (9, 10, "9-10"),
             (11, 99, "11+")]
AGE_BANDS = [(0, 23, "-23"), (24, 25, "24-25"), (26, 27, "26-27"), (28, 29, "28-29"), (30, 31, "30-31"),
             (32, 33, "32-33"), (34, 99, "34+")]
W1_STATUS = {"ACT", "INA", "RES", "PUP"}
SKIP_NEXT = {2019, 2020}


def band(x, bands):
    return next(lbl for lo, hi, lbl in bands if lo <= x <= hi)


def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def _age(birth, season):
    y, m, d = (int(v) for v in birth[:10].split("-"))
    return season - y - ((9, 1) < (m, d))


# ---------------------------------------------------------------- real data
def real_week1(first=2013, last=2026):
    """{season: {player key: {group, age, exp}}} from the weekly rosters."""
    out = {}
    for year in range(first, last + 1):
        path = DATA / "nflverse" / "weekly_rosters" / f"roster_weekly_{year}.csv.gz"
        if not path.exists():
            continue
        cur = {}
        for r in _rows(path):
            if r["week"] != "1" or r.get("game_type", "REG") != "REG" or r["status"] not in W1_STATUS:
                continue
            g = GROUP.get(r["position"]) or GROUP.get(r.get("depth_chart_position") or "")
            key = r.get("gsis_id") or (r["full_name"], r.get("birth_date"))
            if not g or not key:
                continue
            rookie = r.get("rookie_year") or r.get("entry_year")
            exp = int(r["years_exp"]) if r.get("years_exp") not in ("", None) else (
                year - int(float(rookie)) if rookie else None)
            age = _age(r["birth_date"], year) if r.get("birth_date") else None
            cur[key] = {"g": g, "age": age, "exp": exp}
        out[year] = cur
    return out


def real_starters(first=2013, last=2025):
    """[(group, age, exp)] for each team-season's 11+11 snap leaders."""
    # Season rosters lack the pfr id of most linemen (players without stats), so
    # the league-wide player list fills those in.
    people = {}
    for r in _rows(DATA / "nflverse" / "players" / "players.csv.gz"):
        if r.get("pfr_id") and r.get("birth_date"):
            rookie = r.get("rookie_season") or r.get("draft_year")
            for year in range(first, last + 1):
                people[(r["pfr_id"], year)] = (r["birth_date"], int(float(rookie)) if rookie else None)
    for year in range(first, last + 1):
        for r in _rows(DATA / f"roster_{year}.csv.gz"):
            if r.get("pfr_id") and r.get("birth_date"):
                rookie = r.get("rookie_year") or r.get("entry_year")
                people[(r["pfr_id"], year)] = (r["birth_date"], int(float(rookie)) if rookie else None)
    out = []
    for year in range(first, last + 1):
        tot = defaultdict(lambda: [0, 0, None, None])
        for r in _rows(DATA / f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            g = GROUP.get(r["position"])
            if not g or g == "K/P":
                continue
            a = tot[(r["team"], r["pfr_player_id"])]
            a[0] += float(r["offense_snaps"] or 0)
            a[1] += float(r["defense_snaps"] or 0)
            a[2] = g
        by_team = defaultdict(list)
        for (team, pid), (off, de, g, _x) in tot.items():
            by_team[team].append((pid, off, de, g))
        for team, lst in by_team.items():
            for side, idx in (("off", 1), ("def", 2)):
                pool = [x for x in lst if (x[3] in OFFENSE) == (side == "off")]
                for pid, *_rest in sorted(pool, key=lambda x: -x[idx])[:11]:
                    who = people.get((pid, year))
                    if not who:
                        continue
                    birth, rookie = who
                    out.append((_rest[2], _age(birth, year), year - rookie if rookie else None))
    return out


# ---------------------------------------------------------------- game data
CAREERS = defaultdict(dict)          # game: (league, pid) -> {league season: (group, exp, age, overall)}


def rating_curve():
    """Game only: average change in overall from one season to the next by pro
    season (each player against himself, both seasons on a week-1 roster),
    and how uneven it is: share who improved, spread of the change."""
    steps = defaultdict(list)
    for seasons in CAREERS.values():
        for k, (g, exp, age, o) in seasons.items():
            nxt = seasons.get(k + 1)
            if nxt and g != "K/P":
                steps[("sn", g, min(exp + 1, 15))].append(nxt[3] - o)
                steps[("sn", "ALL", min(exp + 1, 15))].append(nxt[3] - o)
                steps[("age", "ALL", min(max(age, 21), 36))].append(nxt[3] - o)
    return steps


def sim_load(files, skip):
    """({season: {key: {g, age, exp, ovr, start}}}, [(group, age, exp)] starters, {season: [starter ovr]})."""
    w1, starters, ovr = {}, [], defaultdict(list)
    for fn in files:
        tag = Path(fn).stem
        w1_path = Path(fn).with_suffix("").as_posix() + ".w1.jsonl"
        first = None
        lines = [json.loads(x) for x in open(w1_path)]
        first = min(r["season"] for r in lines)
        for r in lines:
            season = r["season"]
            if r["start"]:
                ovr[season - first].append(r["ovr"])
            CAREERS[(tag, r["pid"])][season - first] = (GROUP[r["pos"]], r["exp"], r["age"], r["ovr"])
            if season - first < skip:
                continue
            w1.setdefault((tag, season - first), {})[r["pid"]] = {
                "g": GROUP[r["pos"]], "age": r["age"], "exp": r["exp"], "ovr": r["ovr"], "start": r["start"]}
        by_team = defaultdict(list)
        for line in open(fn):
            r = json.loads(line)
            if "team" not in r or r["season"] - first < skip or r["team"] is None:
                continue
            by_team[(r["season"], r["team"])].append(r)
        for lst in by_team.values():
            for side in ("off", "def"):
                pool = [x for x in lst if (GROUP[x["pos"]] in OFFENSE) == (side == "off") and GROUP[x["pos"]] != "K/P"]
                for x in sorted(pool, key=lambda x: -x[side])[:11]:
                    starters.append((GROUP[x["pos"]], x["age"], x["sn"] - 1))
    return w1, starters, ovr


# ---------------------------------------------------------------- measures
def mix(seasons, field, bands):
    c = defaultdict(Counter)
    for roster in seasons.values():
        for x in roster.values():
            if x[field] is None:
                continue
            b = band(x[field], bands)
            c[x["g"]][b] += 1
            c["ALL"][b] += 1
    return c


def mix_list(rows, idx, bands):
    c = defaultdict(Counter)
    for row in rows:
        if row[idx] is None:
            continue
        b = band(row[idx], bands)
        c[row[0]][b] += 1
        c["ALL"][b] += 1
    return c


def leaving(seasons, next_of):
    """Share on no week-1 roster next season, by exp band and age band: {(g, kind, band): [n, gone]}."""
    out = defaultdict(lambda: [0, 0])
    exits = defaultdict(list)       # g -> ages at the last season
    for key, roster in seasons.items():
        nxt = next_of(key)
        if nxt is None:
            continue
        for pid, x in roster.items():
            gone = pid not in nxt
            for g in (x["g"], "ALL"):
                if x["exp"] is not None:
                    o = out[(g, "exp", band(x["exp"], EXP_BANDS))]
                    o[0] += 1
                    o[1] += gone
                    o = out[(g, "exp1", min(x["exp"], 16))]
                    o[0] += 1
                    o[1] += gone
                if x["age"] is not None:
                    o = out[(g, "age", band(x["age"], AGE_BANDS))]
                    o[0] += 1
                    o[1] += gone
                    if gone and x["exp"] is not None and x["exp"] >= 3:
                        exits[g].append(x["age"])
    return out, exits


def survival(leave, g, upto=16):
    s, curve = 1.0, {0: 1.0}
    for e in range(upto):
        n, gone = leave.get((g, "exp1", e), (0, 0))
        if n:
            s *= 1 - gone / n
        curve[e + 1] = s
    return curve


def pct(c, b):
    n = sum(c.values())
    return 100 * c[b] / n if n else float("nan")


def show_mix(title, real, sim, bands):
    print(title)
    labels = [b[2] for b in bands]
    print(f"  {'':5}" + "".join(f"{lbl:>12}" for lbl in labels))
    for g in GROUPS:
        if g not in real:
            continue
        cells = [f"{pct(real[g], b):4.1f}/{pct(sim.get(g, Counter()), b):4.1f}" if sim else f"{pct(real[g], b):4.1f}"
                 for b in labels]
        print(f"  {g:5}" + "".join(f"{c:>12}" for c in cells))


def nine_plus(c):
    n = sum(c.values())
    return 100 * (c["9-10"] + c["11+"]) / n if n else float("nan")


def main():
    argv = sys.argv[1:]
    skip = 6
    if "--skip" in argv:
        i = argv.index("--skip")
        skip = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    args = argv
    real = real_week1()
    real_leave, real_exits = leaving({y: r for y, r in real.items() if y not in SKIP_NEXT},
                                     lambda y: real.get(y + 1))
    rs = real_starters()
    sim = sim_st = sim_leave = sim_exits = ovr = None
    if args:
        sim, sim_st, ovr = sim_load(args, skip)
        sim_leave, sim_exits = leaving(sim, lambda k: sim.get((k[0], k[1] + 1)))
    tag = "real/game" if args else "real"
    print(f"Real NFL 2013-2026 week-1 rosters vs game (seasons {skip + 1}+ of each league)" if args else "Real NFL")
    rexp, rage = mix({y: r for y, r in real.items()}, "exp", EXP_BANDS), mix(real, "age", AGE_BANDS)
    sexp = mix(sim, "exp", EXP_BANDS) if sim else {}
    sage = mix(sim, "age", AGE_BANDS) if sim else {}
    show_mix(f"\n1a. Week-1 rosters by experience, % ({tag})", rexp, sexp, EXP_BANDS)
    show_mix(f"\n1b. Week-1 rosters by age, % ({tag})", rage, sage, AGE_BANDS)
    print("\n  9+ year veterans, % of rosters: " + "  ".join(
        f"{g} {nine_plus(rexp[g]):.1f}" + (f"/{nine_plus(sexp.get(g, Counter())):.1f}" if sim else "")
        for g in GROUPS if g in rexp))
    print("  Average age: " + "  ".join(
        f"{g} {mean(x['age'] for r in real.values() for x in r.values() if x['age'] and (g == 'ALL' or x['g'] == g)):.1f}"
        + (f"/{mean(x['age'] for r in sim.values() for x in r.values() if g == 'ALL' or x['g'] == g):.1f}" if sim else "")
        for g in GROUPS))
    show_mix(f"\n2a. Starters by experience, % ({tag})", mix_list(rs, 2, EXP_BANDS),
             mix_list(sim_st, 2, EXP_BANDS) if sim else {}, EXP_BANDS)
    show_mix(f"\n2b. Starters by age, % ({tag})", mix_list(rs, 1, AGE_BANDS),
             mix_list(sim_st, 1, AGE_BANDS) if sim else {}, AGE_BANDS)
    rse, sse = mix_list(rs, 2, EXP_BANDS), mix_list(sim_st, 2, EXP_BANDS) if sim else {}
    print("\n  Starters with 9+ seasons, %: " + "  ".join(
        f"{g} {nine_plus(rse[g]):.1f}" + (f"/{nine_plus(sse.get(g, Counter())):.1f}" if sim else "")
        for g in GROUPS if g in rse))
    for kind, bands in (("exp", EXP_BANDS), ("age", AGE_BANDS)):
        print(f"\n3{'a' if kind == 'exp' else 'b'}. Gone from week-1 rosters next season, by "
              f"{'experience' if kind == 'exp' else 'age'}, % ({tag})")
        print(f"  {'':5}" + "".join(f"{b[2]:>12}" for b in bands))
        for g in GROUPS:
            cells = []
            for b in bands:
                n, k = real_leave.get((g, kind, b[2]), (0, 0))
                cell = f"{100 * k / n:4.0f}" if n >= 20 else "   -"
                if sim:
                    n2, k2 = sim_leave.get((g, kind, b[2]), (0, 0))
                    cell += f"/{100 * k2 / n2:3.0f}" if n2 >= 20 else "/  -"
                cells.append(cell)
            print(f"  {g:5}" + "".join(f"{c:>12}" for c in cells))
    print(f"\n4. Still on a week-1 roster N seasons after his rookie season, % (from 3's yearly odds; {tag})")
    marks = [1, 2, 3, 5, 8, 10, 12, 14]
    print(f"  {'':5}" + "".join(f"{m:>11}" for m in marks) + f"{'avg yrs':>11}")
    for g in GROUPS:
        rc = survival(real_leave, g)
        sc = survival(sim_leave, g) if sim else None
        cells = [f"{100 * rc[m]:4.0f}" + (f"/{100 * sc[m]:3.0f}" if sc else "") for m in marks]
        avg = f"{sum(rc.values()):4.1f}" + (f"/{sum(sc.values()):4.1f}" if sc else "")
        print(f"  {g:5}" + "".join(f"{c:>11}" for c in cells) + f"{avg:>11}")
    print(f"\n5. Age at his last season, players leaving after 3+ seasons: 10th / median / 90th percentile ({tag})")
    for g in GROUPS:
        def q(v):
            v = sorted(v)
            return (v[len(v) // 10], v[len(v) // 2], v[9 * len(v) // 10]) if len(v) >= 20 else None
        r = q(real_exits.get(g, []))
        s = q(sim_exits.get(g, [])) if sim else None
        print(f"  {g:5} real {r[0]}/{r[1]}/{r[2]} (n {len(real_exits[g])})" if r else f"  {g:5} real -", end="")
        print(f"   game {s[0]}/{s[1]}/{s[2]} (n {len(sim_exits[g])})" if s else "")
    if ovr:
        print("\n6. Game: depth-chart starters' average overall by league season: " +
              " ".join(f"{k + 1}:{mean(v):.1f}" for k, v in sorted(ovr.items())))
        steps = rating_curve()
        print("   Game: overall rating by pro season, built from each player's yearly change (season 1 = 0):")
        for g in GROUPS:
            if g == "K/P":
                continue
            tot, cells = 0.0, ["1:+0"]
            for n in range(1, 15):
                v = steps.get(("sn", g, n), [])
                if len(v) < 30:
                    break
                tot += mean(v)
                cells.append(f"{n + 1}:{tot:+.0f}")
            print(f"     {g:5}" + " ".join(cells))
        print("   Game: yearly change in overall by age (all but K/P): average / share who improved / spread")
        for a in range(22, 37):
            v = steps.get(("age", "ALL", a), [])
            if len(v) >= 30:
                print(f"     age {a}: {mean(v):+.1f} / {100 * sum(x > 0 for x in v) / len(v):.0f}% / {pstdev(v):.1f}")


if __name__ == "__main__":
    main()
