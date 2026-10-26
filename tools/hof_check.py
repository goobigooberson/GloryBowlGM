# tools/hof_check.py
# The Hall of Fame against the real one (engine/hall_of_fame.py).
#
#   python tools/hof_check.py real                    # the real numbers -> tools/real_hof.json (~1 min)
#   python tools/hof_check.py run --leagues 4 --seasons 24   # lab leagues, real games (~30-40 min, in parallel)
#   python tools/hof_check.py report                  # re-read the last run's leagues
#   python tools/hof_check.py revote                  # their votes again with the current knobs, then report
#
# Real: nflverse draft_picks (every drafted player since 1980 with his first-team
# All-Pros, Pro Bowls, career stats and a `hof` column). Careers from the 1980-2005
# draft classes that ended by 2015 (so most have had their 10+ ballots): who got in,
# by All-Pro count, Pro Bowl count and position, and a logistic fit of what voters
# weigh (the weights in hall_of_fame.CASE_*). Undrafted Hall of Famers (Moon, Warner,
# Gates...) aren't in this file: about 6% of modern-era players.
#
# Game: lab leagues (tools/lab.py) played with the real sim for many seasons; every
# retired player whose whole career was in the league (drafted after its first season)
# is run through the Hall's vote many times (a fresh "standing" each time), which gives
# his odds of getting in someday. Compared with real: those odds by All-Pro count, Pro
# Bowl count and position; inductees a year; first-ballot share. The leagues' own votes
# (classes, finalists) are listed too, and each league is kept as a save file
# (tools/data/hof/<seed>.db, a save file) for looking at the history screens.

import argparse
import csv
import gzip
import json
import math
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import hall_of_fame as HOF          # noqa: E402

DATA = ROOT / "tools" / "data"
OUT = DATA / "hof"
REAL = ROOT / "tools" / "real_hof.json"
POS = ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K", "P")
REAL_FIRST_BALLOT = 0.32       # NFL.com (2018): 16 first-ballot modern-era inductees in the 10 classes 2009-2018,
                               # about 50 modern-era players inducted
REAL_PER_YEAR = (4.5, 5.0)     # drafted inductees a draft class 1980-1999 (4.15, ~28.8 teams) scaled to 32 teams,
                               # plus ~6% undrafted; the real Hall's limit is 5 modern-era players a year


# ---------------------------------------------------------------------------
# Real
# ---------------------------------------------------------------------------

def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _real_prod(x):
    c, f = x["category"], lambda k: _num(x[k])
    if c == "QB":
        return (f("pass_yards") / 4400 + f("pass_tds") / 32) / 2
    if c == "RB":
        return (f("rush_yards") + f("rec_yards")) / 1900
    if c == "WR":
        return f("rec_yards") / 1450
    if c == "TE":
        return f("rec_yards") / 900
    if c in ("DL", "LB"):
        return f("def_sacks") / 15
    if c == "DB":
        return f("def_ints") / 7.5
    return 0.0


def _solve(A, b):
    n = len(b)
    M = [A[k][:] + [b[k]] for k in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda k: abs(M[k][c]))
        M[c], M[p] = M[p], M[c]
        for k in range(n):
            if k != c:
                f = M[k][c] / M[c][c]
                for j in range(c, n + 1):
                    M[k][j] -= f * M[c][j]
    return [M[k][n] / M[k][k] for k in range(n)]


def _fit(X, y, ridge_pos=2.0):
    """Logistic regression by damped Newton steps; ridge on the position terms (small groups)."""
    d = len(X[0])
    w = [0.0] * d
    w[0] = -6.0
    for _it in range(60):
        H = [[0.0] * d for _ in range(d)]
        g = [0.0] * d
        for xi, yi in zip(X, y):
            p = 1 / (1 + math.exp(-max(-35, min(35, sum(a * b for a, b in zip(w, xi))))))
            s = p * (1 - p)
            for a in range(d):
                g[a] += (yi - p) * xi[a]
                for b in range(d):
                    H[a][b] += s * xi[a] * xi[b]
        for a in range(1, d):
            r = ridge_pos if a >= 4 else 0.05
            H[a][a] += r
            g[a] -= r * w[a]
        step = _solve(H, g)
        m = max(abs(a) for a in step)
        sc = min(1.0, 1.0 / m) if m else 1.0
        w = [a + sc * b for a, b in zip(w, step)]
    return w


def real():
    rows = list(csv.DictReader(gzip.open(DATA / "nflverse" / "draft_picks" / "draft_picks.csv.gz", "rt",
                                         encoding="utf8")))
    car = [x for x in rows if 1980 <= int(x["season"]) <= 2005 and x["to"] and int(x["to"]) <= 2015
           and x["category"] in POS]
    X = [[1.0, _num(x["allpro"]), _num(x["probowls"]), _real_prod(x)] + [1.0 if x["category"] == g else 0.0
                                                                        for g in POS] for x in car]
    y = [1.0 if x["hof"] == "TRUE" else 0.0 for x in car]
    w = _fit(X, y)
    out = {"source": "nflverse draft_picks; 1980-2005 draft classes, careers ended by 2015",
           "players": len(car), "inducted": int(sum(y)),
           "fit": {"base": w[0], "ap1": w[1], "pb": w[2], "prod": w[3], "pos": dict(zip(POS, w[4:]))}}

    def table(f):
        c = defaultdict(lambda: [0, 0])
        for x, yi in zip(car, y):
            k = f(x)
            if k is None:
                continue
            c[k][0] += 1
            c[k][1] += yi
        return {str(k): [n, int(h), h / n] for k, (n, h) in sorted(c.items())}
    out["by_ap1"] = table(lambda x: str(min(int(_num(x["allpro"])), 4)))
    out["by_pb"] = table(lambda x: _pb_bin(int(_num(x["probowls"]))))
    out["by_pos_ap1"] = table(lambda x: x["category"] if _num(x["allpro"]) >= 1 else None)
    out["by_pos_pb3"] = table(lambda x: x["category"] if _num(x["probowls"]) >= 3 else None)
    hof = [x for x, yi in zip(car, y) if yi]
    out["inductee_positions"] = {g: sum(1 for x in hof if x["category"] == g) / len(hof) for g in POS}
    out["inductee_seasons_median"] = sorted(int(x["to"]) - int(x["season"]) + 1 for x in hof)[len(hof) // 2]
    out["inductee_pb_median"] = sorted(int(_num(x["probowls"])) for x in hof)[len(hof) // 2]
    out["inductee_ap1_median"] = sorted(int(_num(x["allpro"])) for x in hof)[len(hof) // 2]
    early = [x for x in rows if 1980 <= int(x["season"]) <= 1999]
    out["drafted_inductees_per_class_1980_1999"] = sum(1 for x in early if x["hof"] == "TRUE") / 20
    out["first_ballot_share"] = REAL_FIRST_BALLOT
    out["per_year"] = REAL_PER_YEAR
    REAL.write_text(json.dumps(out, indent=1))
    print(f"wrote {REAL.name}: {len(car)} careers, {int(sum(y))} Hall of Famers")
    print("fit:", {k: (round(v, 3) if isinstance(v, float) else {a: round(b, 2) for a, b in v.items()})
                   for k, v in out["fit"].items()})


def _pb_bin(n):
    return "0-3" if n <= 3 else str(n) if n <= 7 else "8-9" if n <= 9 else "10+"


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

def odds(c, sims=400, rng=None):
    """Chance a case gets in someday, playing his ballots through the Hall's vote (no class limit),
    and the chance he goes in on the first ballot."""
    rng = rng or random.Random(1)
    need = math.ceil(HOF.NEEDED * HOF.VOTERS - 1e-9)
    hit = first = 0
    for _ in range(sims):
        u = min(max(rng.random(), 1e-9), 1 - 1e-9)
        stand = math.log(u / (1 - u))
        for b in range(1, HOF.LAST_BALLOT - HOF.WAIT + 2):
            share = HOF.ballot_support(c, stand, b, rng.gauss(0, HOF.YEAR_SWING))
            if sum(1 for _v in range(HOF.VOTERS) if rng.random() < share) >= need:
                hit += 1
                first += b == 1
                break
    return hit / sims, first / sims


def _play(args):
    seed, seasons = args
    from tools.lab import Lab
    t0 = time.time()
    lab = Lab(seed, "real")
    lab.run(seasons=seasons)
    lg = lab.league
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{seed}.json").write_text(json.dumps(dump(lg)))      # the results first
    keep(lg, seed)
    return seed, time.time() - t0


def keep(lg, seed):
    """The league as a save file (tools/data/hof/<seed>.db): for revote and for looking at the
    history screens (load it with a team picked)."""
    from engine.database import save_league
    try:
        save_league(lg, OUT / f"{seed}.db")
    except Exception as e:                       # never lose the results over the copy
        print(f"league {seed}: couldn't keep the save ({e})", flush=True)


def dump(lg):
    """Every retired player's record (as the voters see it) and the league's own votes."""
    first = lg.settings.get("first_season", lg.season)
    retired = [p for p in lg.players if p.retired is not None]
    lines = HOF._career_lines(lg, {p.id for p in retired})
    honors = HOF._honors(lg)
    players = []
    for p in retired:
        if not lines.get(p.id):
            continue
        r = HOF.resume(lg, p.id, lines[p.id], honors.get(p.id, {}))
        players.append({"pid": p.id, "pos": p.position, "group": HOF.HOF_GROUP.get(p.position), "retired": p.retired,
                        "full": (p.draft_year or 0) > first, "ap1": r["ap1"], "ap1_spec": r["ap1_spec"],
                        "pb": r["pb"], "prod": round(r["prod"], 3), "seasons": r["seasons"],
                        "case": round(HOF.case(p.position, r), 4)})
    h = HOF.ensure(lg)
    return {"first": first, "last": lg.season - 1, "players": players, "members": h["members"], "votes": h["votes"]}


def run(leagues, seasons, seeds=None):
    seeds = seeds or [101 + 101 * k for k in range(leagues)]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=len(seeds)) as ex:
        for seed, secs in ex.map(_play, [(s, seasons) for s in seeds]):
            print(f"league {seed}: {seasons} seasons in {secs / 60:.1f} min", flush=True)
    print(f"all done in {(time.time() - t0) / 60:.1f} min")
    report()


def revote():
    """Play every lab league's Hall of Fame votes again with the current knobs (from the kept
    save files): each season's vote in order, as it would have gone."""
    from engine.database import load_league
    for path in sorted(OUT.glob("*.db")):
        lg = load_league(path)
        HOF.ensure(lg)
        lg.awards["hall_of_fame"] = {"members": [], "votes": []}
        now = lg.season
        first = lg.settings.get("first_season", now)
        for s in range(first, now):
            lg.season = s
            HOF.vote(lg)
        lg.season = now
        (OUT / f"{path.stem}.json").write_text(json.dumps(dump(lg)))
        print(f"re-voted {path.stem}")


def report():
    real_ = json.loads(REAL.read_text())
    dumps = sorted(OUT.glob("*.json"))
    if not dumps:
        print("No lab leagues yet: python tools/hof_check.py run")
        return
    rng = random.Random(7)
    rows, per_year, members, firsts, held = [], [], [], [], 0
    for path in dumps:
        d = json.loads(path.read_text())
        late = d["last"] - 14          # retirement seasons where nearly every retiree's whole career was in the league
        cohort = defaultdict(float)
        for x in d["players"]:
            x["p_in"], x["p_first"] = (odds(x["case"], rng=rng) if HOF._sig(x["case"]) >= HOF.ON_BALLOT
                                       else (0.0, 0.0))
            if x["full"]:
                rows.append(x)
            if x["retired"] >= d["first"] + 14:
                cohort[x["retired"]] += x["p_in"]
        per_year += [v for s, v in cohort.items() if s <= d["last"]]
        members += d["members"]
        for v in d["votes"]:
            held += v.get("held_over", 0)
        print(f"{path.stem}: seasons {d['first']}-{d['last']}, {len(d['players'])} retired, "
              f"{len(d['members'])} in the Hall; classes " +
              " ".join(f"{v['class_of']}:{sum(1 for b in v['ballot'] if b[3])}" for v in d["votes"]))
    print()
    print(f"Game: {len(rows)} retired players with whole careers in the league "
          f"(retirement seasons {min(x['retired'] for x in rows)}-{max(x['retired'] for x in rows)})")

    def line(title, key, real_tab):
        c = defaultdict(lambda: [0, 0.0])
        for x in rows:
            k = key(x)
            if k is None:
                continue
            c[k][0] += 1
            c[k][1] += x["p_in"]
        print(f"\n{title}")
        print(f"  {'':8}{'game n':>8}{'game %':>9}{'real n':>9}{'real %':>9}")
        for k in sorted(set(c) | set(real_tab), key=lambda k: (len(k), k)):
            n, s = c.get(k, (0, 0.0))
            rn, _rh, rp = real_tab.get(k, (0, 0, 0.0))
            print(f"  {k:8}{n:>8}{(100 * s / n if n else 0):>8.1f}%{rn:>9}{100 * rp:>8.1f}%")
    line("Chance of the Hall by first-team All-Pros (4 = 4 or more)",
         lambda x: str(min(int(x["ap1"]), 4)), real_["by_ap1"])
    line("By Pro Bowls", lambda x: _pb_bin(x["pb"]), real_["by_pb"])
    line("By position, players with a first-team All-Pro", lambda x: x["group"] if x["ap1"] >= 1 else None,
         real_["by_pos_ap1"])
    line("By position, players with 3+ Pro Bowls", lambda x: x["group"] if x["pb"] >= 3 else None,
         real_["by_pos_pb3"])
    exp = sum(x["p_in"] for x in rows) or 1
    print("\nInductees by position (share; game expected from whole careers vs real)")
    for g in POS:
        print(f"  {g:4}{100 * sum(x['p_in'] for x in rows if x['group'] == g) / exp:>7.1f}%"
              f"{100 * real_['inductee_positions'].get(g, 0):>8.1f}%")
    fb = sum(x["p_first"] for x in rows) / exp
    print(f"\nFirst-ballot share of inductees: game {fb:.2f}, real about {real_['first_ballot_share']:.2f}")
    if per_year:
        print(f"Inductees a year (expected, from retirement seasons with whole careers in the league): "
              f"game {sum(per_year) / len(per_year):.2f} (from {len(per_year)} seasons), "
              f"real {real_['per_year'][0]}-{real_['per_year'][1]}")
    print(f"Players reaching 80% but held over by the limit of {HOF.CLASS_LIMIT}: {held}")
    if members:
        fbm = sum(1 for m in members if m["ballot"] == 1) / len(members)
        print(f"The leagues' own votes: {len(members)} inducted, {100 * fbm:.0f}% on the first ballot "
              "(early classes are small: careers count only from the league's first season)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["real", "run", "report", "revote"])
    ap.add_argument("--leagues", type=int, default=4)
    ap.add_argument("--seasons", type=int, default=24)
    ap.add_argument("--seeds", type=int, nargs="*")
    a = ap.parse_args()
    if a.mode == "real":
        real()
    elif a.mode == "run":
        run(a.leagues, a.seasons, a.seeds)
    elif a.mode == "revote":
        revote()
        report()
    else:
        report()


if __name__ == "__main__":
    main()
