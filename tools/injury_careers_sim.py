# tools/injury_careers_sim.py
# The same measurement as tools/injury_careers_real.py, on simulated leagues
# (real games, full offseasons and development): players with a season-ending
# injury vs matched uninjured players. Writes one JSON line per player-season
# so several leagues can be pooled:
#   python tools/injury_careers_sim.py run <seed> <seasons> <out.jsonl> [module.NAME=value ...]
# Each line also carries his position, age, team, ratings and snaps (for
# tools/career_mix_check.py); <out>.w1.jsonl lists every week-1 roster (the
# 53s plus injured reserve / PUP, with depth-chart starters) and
# <out>.players.jsonl every player's birth date and retirement.
#   python tools/injury_careers_sim.py report <file1.jsonl> [file2 ...]

import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR/TE", "TE": "WR/TE", "T": "OL", "G": "OL", "C": "OL",
             "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB"}
KIND_GROUP = {"knee": "knee", "achilles": "achilles", "foot": "foot", "shoulder": "shoulder"}
SEASON_ENDING_MIN = 12


def _week1(lg, season):
    """Every player on a week-1 roster: the 53s plus injured reserve / PUP."""
    from datetime import date
    from engine import depth
    starters = set()
    for t in lg.teams:
        starters |= depth.starter_ids(lg.depth_charts.get(t.id, {}))
    where = {pid: (tid, "53") for pid, tid in lg.rosters.items()}
    where.update({pid: (r["team"], r["list"]) for pid, r in lg.reserve.items() if r["list"] != "PSIR"})
    out = []
    for pid, (tid, lst) in where.items():
        p = lg.player(pid)
        out.append({"pid": pid, "season": season, "pos": p.position, "age": p.age(date(season, 9, 1)),
                    "exp": p.experience, "team": tid, "list": lst, "ovr": p.overall(),
                    "pot": p.overall("potential"), "start": pid in starters})
    return out


def run(seed, seasons, out):
    from datetime import date
    from engine.league import create_league
    from engine import season as S, injuries as I
    lg = create_league(season=2026, seed=seed)
    lg.user_team_id = 1
    S.start_season(lg, random.Random(seed))
    stem = str(Path(out).with_suffix(""))
    with open(out, "w") as f, open(stem + ".w1.jsonl", "w") as w1f:
        for yr in range(seasons):
            w1_done = False
            while not S.season_over(lg):
                S.play_week(lg)
                if not w1_done and S.in_regular_season(lg) and lg.week == 1:
                    for r in _week1(lg, lg.season):
                        w1f.write(json.dumps(r) + "\n")
                    w1f.flush()
                    w1_done = True
            # Each player's share of his side's snaps per game played (regular season).
            share = defaultdict(list)
            snaps = defaultdict(lambda: [0, 0, None])     # pid -> [offense snaps, defense snaps, team]
            for g in lg.schedule:
                box = lg.boxes.get(g["id"])
                if not box:
                    continue
                plays = [box["team"][0].get("plays", 0), box["team"][1].get("plays", 0)]
                tids = [g["home"], g["away"]]
                for pid_s, line in box["players"].items():
                    i = tids.index(line["team"])
                    off, deff = line.get("off_snaps", 0), line.get("def_snaps", 0)
                    sn = snaps[int(pid_s)]
                    sn[0], sn[1], sn[2] = sn[0] + off, sn[1] + deff, line["team"]
                    if off >= deff and plays[i]:
                        share[int(pid_s)].append(off / plays[i])
                    elif plays[1 - i]:
                        share[int(pid_s)].append(deff / plays[1 - i])
            ending = {}
            for pid, lst in lg.season_injuries.items():
                for kind, weeks in lst:
                    if weeks >= SEASON_ENDING_MIN:
                        ending[pid] = KIND_GROUP.get(I.PART.get(kind), "other")
            for p in lg.players:
                if p.id not in share or p.position not in POS_GROUP:
                    continue
                s = share[p.id]
                f.write(json.dumps({"pid": p.id, "season": lg.season, "pg": POS_GROUP[p.position],
                                    "sn": p.experience + 1, "share": round(sum(s) / len(s), 3), "games": len(s),
                                    "ending": ending.get(p.id), "pos": p.position,
                                    "age": p.age(date(lg.season, 9, 1)), "team": snaps[p.id][2],
                                    "off": snaps[p.id][0], "def": snaps[p.id][1],
                                    "ovr": p.overall(), "pot": p.overall("potential")}) + "\n")
            f.flush()
            S.start_next_season(lg, random.Random(yr))
            print(f"season {yr + 1} done", flush=True)
    with open(stem + ".players.jsonl", "w") as pf:
        for p in lg.players:
            pf.write(json.dumps({"pid": p.id, "pos": p.position, "birth": str(p.birth_date), "exp": p.experience,
                                 "retired": p.retired, "draft_year": p.draft_year,
                                 "generational": bool(p.generational)}) + "\n")


def report(files):
    rows = {}
    for fn in files:
        tag = Path(fn).stem
        for line in open(fn):
            r = json.loads(line)
            rows[(tag, r["pid"], r["season"])] = r

    def bucket(sn, sh):
        return (min(sn, 10) // 2, round(sh * 4) / 4)
    ctrl = defaultdict(lambda: [0, 0, [], []])
    for (tag, pid, y), r in rows.items():
        if r["ending"] or r["share"] < 0.3 or r["games"] < 6:
            continue
        c = ctrl[(r["pg"],) + bucket(r["sn"], r["share"])]
        nxt = rows.get((tag, pid, y + 1))
        c[0] += 1
        if nxt:
            c[1] += 1
            c[2].append(nxt["share"] - r["share"])
            nx2 = rows.get((tag, pid, y + 2))
            if nx2:
                c[3].append(nx2["share"] - r["share"])
    res = defaultdict(lambda: {"n": 0, "back": 0, "exp": 0.0, "d1": [], "e1": [], "d2": [], "e2": []})
    last = {tag: max(y for t, _p, y in rows if t == tag) for tag in {k[0] for k in rows}}
    for (tag, pid, y), r in rows.items():
        if not r["ending"] or r["share"] < 0.3 or y >= last[tag]:
            continue
        c = ctrl.get((r["pg"],) + bucket(r["sn"], r["share"]))
        if not c or c[0] < 15:
            continue
        for key in ((r["ending"], r["pg"]), (r["ending"], "all"), ("all season-ending", r["pg"])):
            x = res[key]
            x["n"] += 1
            x["exp"] += c[1] / c[0]
            nxt = rows.get((tag, pid, y + 1))
            if nxt:
                x["back"] += 1
                x["d1"].append(nxt["share"] - r["share"])
                x["e1"].append(mean(c[2]) if c[2] else 0)
                nx2 = rows.get((tag, pid, y + 2))
                if nx2:
                    x["d2"].append(nx2["share"] - r["share"])
                    x["e2"].append(mean(c[3]) if c[3] else 0)
    print("SIM season-ending injuries vs matched uninjured players (share = snaps per game played)")
    print(f"{'injury':20}{'pos':7}{'n':>5}{'back':>7}{'matched':>9}{'share +1':>10}{'share +2':>10}")
    for ig in ["all season-ending", "knee", "achilles", "foot", "shoulder", "other"]:
        for pg in ["all", "QB", "RB", "WR/TE", "OL", "DL", "LB", "DB"]:
            x = res.get((ig, pg))
            if not x or x["n"] < 12:
                continue
            d1 = mean(a - b for a, b in zip(x["d1"], x["e1"])) if x["d1"] else 0
            d2 = mean(a - b for a, b in zip(x["d2"], x["e2"])) if x["d2"] else 0
            print(f"{ig:20}{pg:7}{x['n']:5}{100 * x['back'] / x['n']:6.0f}%{100 * x['exp'] / x['n']:8.0f}%"
                  f"{100 * d1:+9.1f}pt{100 * d2:+9.1f}pt")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        import importlib
        for arg in sys.argv[5:]:            # optional knob overrides: module.NAME=value
            name, value = arg.split("=", 1)
            mod, attr = name.split(".")
            setattr(importlib.import_module(f"engine.{mod}"), attr, eval(value))
        run(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    else:
        report(sys.argv[2:])
