# tools/rookie_check.py
# How ready drafted rookies are, real vs the game (Oct 25; Blake: "i dont think most
# players in the draft should be like 70-80% plus developed"). The real NFL has no
# ratings, so the yardstick is playing time: of each draft round,
#   - rookie regulars: the share who play half or more of their side's snaps (over
#     the team's games) as rookies,
#   - regulars in years 2-5, ever regular (years 1-5),
#   - of the eventual regulars, the share who already were as rookies (the rest are
#     late bloomers: most real mid-round starters break out in year 2-4).
# Real: nflverse snap counts, 2013-2021 draft classes' first 5 seasons (K/P/LS left
# out). Game: lab leagues (tools/lab.py, fast games: snaps follow the depth chart),
# the classes drafted after the league's first season. Also the draft board's
# Developed % (each prospect's true value on the screen scale, before your scouts'
# error): the share of drafted players at 70%+ and 80%+.
#
#   python tools/rookie_check.py real              # rebuild tools/real_rookie_bloom.json from the data
#   python tools/rookie_check.py                   # 4 lab leagues x 9 seasons (~10 minutes in parallel)
#   python tools/rookie_check.py --leagues 2 --seasons 7
#
# tools/scoreboard.py runs the same measures (suite "rookies"). Changes and saves nothing.

import argparse
import csv
import gzip
import json
import statistics as st
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

REAL_FILE = HERE / "real_rookie_bloom.json"
DATA = HERE / "data" / "nflverse"
BUCKETS = [("1", {1}), ("2", {2}), ("3", {3}), ("4-5", {4, 5}), ("6-7", {6, 7})]
REGULAR = 0.5                 # half or more of his side's snaps over the team's games
FOLLOW = 5                    # seasons followed (rookie year + 4)
SPECIALISTS = ("K", "P", "LS")
OFFENSE = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OT", "OG", "OL", "LT", "RT", "LG", "RG", "HB"}


# ---- Shared: shares by round -> measures -------------------------------------------------

def summarize(players):
    """players: [(round, [share in seasons 1..5])] -> {bucket: {...}} (fractions)."""
    out = {}
    for name, rounds in BUCKETS:
        g = [s for r, s in players if r in rounds]
        n = len(g)
        acc = defaultdict(float)
        for s in g:
            later = max(s[1:]) >= REGULAR
            ever = max(s) >= REGULAR
            acc["rookie_regular"] += s[0] >= REGULAR
            acc["regular_later"] += later
            acc["ever"] += ever
            acc["ever_and_rookie"] += ever and s[0] >= REGULAR
        o = {k: v / max(1, n) for k, v in acc.items() if k != "ever_and_rookie"}
        o["started_as_rookie"] = acc["ever_and_rookie"] / max(1, acc["ever"])
        o["n"], o["n_ever"] = n, acc["ever"]
        out[name] = o
    return out


# ---- Real --------------------------------------------------------------------------------

def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_real():
    share = defaultdict(float)
    for y in range(2013, 2026):
        games, tot = defaultdict(set), defaultdict(float)
        for r in _rows(DATA / "snap_counts" / f"snap_counts_{y}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            games[r["team"]].add(r["game_id"])
            try:
                pct = float(r["offense_pct"] or 0) if r["position"] in OFFENSE else float(r["defense_pct"] or 0)
            except ValueError:
                pct = 0.0
            tot[r["pfr_player_id"]] += pct
        n = max(len(v) for v in games.values())
        for pid, t in tot.items():
            share[(pid, y)] = t / n
    players = []
    for r in _rows(DATA / "draft_picks" / "draft_picks.csv.gz"):
        y = int(r["season"])
        if 2013 <= y <= 2021 and r["position"] not in SPECIALISTS and r["pfr_player_id"]:
            players.append((int(r["round"]), [share.get((r["pfr_player_id"], y + k), 0.0) for k in range(FOLLOW)]))
    out = {"source": "nflverse snap counts and draft picks, 2013-2021 classes, first 5 seasons (K/P/LS out)",
           "by_round": summarize(players)}
    REAL_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def real():
    return json.loads(REAL_FILE.read_text(encoding="utf-8"))["by_round"]


# ---- Game --------------------------------------------------------------------------------

def run_league(job):
    """One lab league (seed, seasons). Returns {"players": [(round, shares)], "devl": [%...]}."""
    seed, seasons = job
    from lab import Lab
    from engine import draft_day, season as S
    from engine.player import developed_share
    recs = {}
    devl = []

    def season_end(lab):
        lg = lab.league
        tot, games = defaultdict(float), defaultdict(int)
        for g in lg.schedule:
            if S.is_preseason_game(g) or S.is_playoff_game(g):
                continue
            box = lg.boxes.get(g["id"])
            if not box:
                continue
            plays = {g["home"]: box["team"][0].get("plays", 0), g["away"]: box["team"][1].get("plays", 0)}
            for t in (g["home"], g["away"]):
                games[t] += 1
            for pid, line in box["players"].items():
                t = line["team"]
                o = g["away"] if t == g["home"] else g["home"]
                off, de = line.get("off_snaps", 0), line.get("def_snaps", 0)
                if off >= de and plays[t]:
                    tot[int(pid)] += off / plays[t]
                elif plays[o]:
                    tot[int(pid)] += de / plays[o]
        n = max(games.values())
        first = lab.seed_first_season
        for p in lg.players:
            if p.draft_year and p.draft_year > first and p.draft_round and p.position not in SPECIALISTS:
                r = recs.setdefault(p.id, {"round": p.draft_round, "year": p.draft_year, "share": {}})
                r["share"][lg.season] = tot.get(p.id, 0.0) / n

    def offseason_start(lab):
        lg = lab.league
        pros = sorted(draft_day.prospects(lg), key=lambda p: getattr(p, "_media", 0.0), reverse=True)
        for p in pros[:7 * len(lg.teams)]:
            devl.append(developed_share(p.overall(), p.overall("potential")))

    lab = Lab(seed, games="fast")
    lab.seed_first_season = lab.league.season
    lab.on("season_end", season_end)
    lab.on("offseason_start", offseason_start)
    lab.run(seasons=seasons, offseason_last=False)
    last = lab.league.season
    players = [(r["round"], [r["share"].get(r["year"] + k, 0.0) for k in range(FOLLOW)])
               for r in recs.values() if r["year"] + FOLLOW - 1 <= last]
    return {"players": players, "devl": devl}


def devl_shares(devl):
    v = sorted(devl)
    if not v:
        return {}
    return {"devl_70plus": sum(x >= 70 for x in v) / len(v), "devl_80plus": sum(x >= 80 for x in v) / len(v),
            "devl_median": st.median(v)}


def report(results, say=print):
    rl = real()
    players = [x for r in results for x in r["players"]]
    game = summarize(players)
    keys = [("rookie_regular", "rookie regulars"), ("regular_later", "regular yr 2-5"), ("ever", "ever regular"),
            ("started_as_rookie", "eventual regulars who started as rookies")]
    say("Drafted players' playing time by round, game / real (regular = half his side's snaps or more)")
    say("round      n | " + " | ".join(lbl for _k, lbl in keys))
    for b, _r in BUCKETS:
        g, r = game[b], rl[b]
        say(f"{b:5} {g['n']:6} | " + " | ".join(f"{100 * g[k]:4.0f}% / {100 * r[k]:3.0f}%".center(len(lbl))
                                               for k, lbl in keys))
    d = devl_shares([x for r in results for x in r["devl"]])
    if d:
        say(f"Draft board Developed % (drafted players, true value): 70%+ {100 * d['devl_70plus']:.0f}%, "
            f"80%+ {100 * d['devl_80plus']:.0f}%, median {d['devl_median']:.0f}%  (Oct 25 yardstick from raw, lab league 101: 70%+ about 12%, median about 32)")
    return game


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="game", choices=["game", "real"])
    ap.add_argument("--leagues", type=int, default=4)
    ap.add_argument("--seasons", type=int, default=9)
    a = ap.parse_args()
    if a.mode == "real":
        out = build_real()
        print(json.dumps(out["by_round"], indent=1))
        return
    jobs = [(301 + i, a.seasons) for i in range(a.leagues)]
    with Pool(len(jobs), maxtasksperchild=1) as pool:
        results = pool.map(run_league, jobs)
    report(results)


if __name__ == "__main__":
    main()
