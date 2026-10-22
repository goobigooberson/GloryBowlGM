# tools/injury_careers_sim.py
# The same measurement as tools/injury_careers_real.py, on simulated leagues
# (real games, full offseasons and development): players with a season-ending
# injury vs matched uninjured players. Writes one JSON line per player-season
# so several leagues can be pooled:
#   python tools/injury_careers_sim.py run <seed> <seasons> <out.jsonl>
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


def run(seed, seasons, out):
    from engine.league import create_league
    from engine import season as S, injuries as I
    lg = create_league(season=2026, seed=seed)
    lg.user_team_id = 1
    S.start_season(lg, random.Random(seed))
    with open(out, "w") as f:
        for yr in range(seasons):
            while not S.season_over(lg):
                S.play_week(lg)
            # Each player's share of his side's snaps per game played (regular season).
            share = defaultdict(list)
            for g in lg.schedule:
                box = lg.boxes.get(g["id"])
                if not box:
                    continue
                plays = [box["team"][0].get("plays", 0), box["team"][1].get("plays", 0)]
                tids = [g["home"], g["away"]]
                for pid_s, line in box["players"].items():
                    i = tids.index(line["team"])
                    off, deff = line.get("off_snaps", 0), line.get("def_snaps", 0)
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
                                    "ending": ending.get(p.id)}) + "\n")
            f.flush()
            S.start_next_season(lg, random.Random(yr))
            print(f"season {yr + 1} done", flush=True)


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
