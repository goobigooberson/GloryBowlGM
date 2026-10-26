# tools/qb_style_check.py
# Different kinds of good quarterback seasons, real vs the game (Oct 25; Blake: "is it
# currently possible in the game for a very highly rated qb to not pass for a lot of
# yards but still play well and have a high rating. Maybe cause they run alot, or are
# on a heavy run first team" ... "and i mean for this to happen naturally"). Nothing in
# the game scripts it: coordinators' run/pass styles, rosters (a strong run game means
# fewer throws), game script (leading teams run) and mobile QBs (designed runs and
# scrambles) make it. Per season, starting QBs (13+ games, 300+ attempts):
#   - efficient on low volume: passer rating 100+ on under a 3,600-yard pace (per 17 games)
#   - running QBs: 600+ rushing yards (any starter)
#   - pass attempts per game: the low, middle and high teams' QBs (10th / 50th / 90th percentile)
# Real: nflverse season stats, regular seasons 2021-2025, the era the sim is calibrated to
# (every other sim benchmark uses it too). Until Oct 25 this used 2010-2024, which mixed in
# the 2012-2016 passing peak (more attempts) and years with few running QBs: 600-yard QB
# seasons were about 1 a season in 2010-2017 and 2.8 in 2021-25 (Lamar Jackson, Jalen Hurts,
# Josh Allen, Justin Fields, Jayden Daniels...).
# Games: games played on both sides (the game: games with an offensive snap). Attempts per
# game percentiles: each season is centered on its own league average first, then pooled,
# because real league-wide passing drifts from year to year (34.4 attempts a team game in
# 2021, 32.1 in 2025) and the game's seasons don't.
# Game: tools/simlab.py seasons (real games).
#
#   python tools/qb_style_check.py real        # rebuild tools/real_qb_styles.json from the data
#   python tools/qb_style_check.py             # leagues 101-103 x 4 seasons (~5 minutes in parallel)
#
# tools/scoreboard.py reports the same measures in its sim suite. Changes and saves nothing.

import argparse
import csv
import gzip
import json
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

REAL_FILE = HERE / "real_qb_styles.json"
DATA = HERE / "data" / "nflverse"
REAL_YEARS = range(2021, 2026)
MIN_GAMES, MIN_ATT = 13, 300
EFFICIENT, LOW_PACE, RUNNER = 100.0, 3600, 600
LABELS = {
    "qb_efficient_low_volume": "QB seasons with a 100+ passer rating on under a 3,600-yard pace",
    "qb_600_rush": "QB seasons with 600+ rushing yards",
    "qb_att_pg_p10": "starting QBs' pass attempts per game: low (10th percentile)",
    "qb_att_pg_p50": "...middle (median)",
    "qb_att_pg_p90": "...high (90th percentile)",
}


def passer_rating(c, a, y, t, i):
    f = lambda v: max(0.0, min(2.375, v))  # noqa: E731
    return 100 * (f((c / a - .3) * 5) + f((y / a - 3) * .25) + f(t / a * 20) + f(2.375 - i / a * 25)) / 6


def season_measures(qbs):
    """qbs: one season's [(games, att, cmp, yds, td, int, rush_yds)] -> counts, plus attempts per game list."""
    eff = run = 0
    att_pg = []
    for g, a, c, y, t, i, ry in qbs:
        if g >= 6 and ry >= RUNNER:
            run += 1
        if g < MIN_GAMES or a < MIN_ATT:
            continue
        att_pg.append(a / g)
        eff += passer_rating(c, a, y, t, i) >= EFFICIENT and y / g * 17 < LOW_PACE
    return {"qb_efficient_low_volume": eff, "qb_600_rush": run}, att_pg


def percentiles(seasons):
    """seasons: one list of attempts per game per season. Each season is centered on its own
    average, then all are pooled around the overall average (see the top of the file)."""
    seasons = [x for x in seasons if x]
    if not seasons:
        return {}
    allv = [a for x in seasons for a in x]
    mean = sum(allv) / len(allv)
    v = sorted(a - sum(x) / len(x) + mean for x in seasons for a in x)
    return {"qb_att_pg_p10": v[len(v) // 10], "qb_att_pg_p50": v[len(v) // 2], "qb_att_pg_p90": v[9 * len(v) // 10]}


def game_qbs(players, plays_per_game):
    """simlab players (one season) -> season_measures input. Games: games played (gp); older
    simlab output without it falls back to his snaps / his team's plays per game."""
    out = []
    for p in players:
        if p.get("pos") != "QB" or not p.get("pass_att"):
            continue
        g = p["gp"] if "gp" in p else p.get("off_snaps", 0) / max(1.0, plays_per_game)
        out.append((g, p["pass_att"], p.get("pass_cmp", 0), p.get("pass_yds", 0), p.get("pass_td", 0),
                    p.get("pass_int", 0), p.get("rush_yds", 0)))
    return out


def build_real():
    per_season, att = [], []
    for yr in REAL_YEARS:
        qbs = []
        with gzip.open(DATA / "stats_player" / f"stats_player_reg_{yr}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("position") != "QB" or not float(r.get("attempts") or 0):
                    continue
                qbs.append(tuple(float(r.get(k) or 0) for k in ("games", "attempts", "completions", "passing_yards",
                                                                 "passing_tds", "passing_interceptions", "rushing_yards")))
        m, a = season_measures(qbs)
        per_season.append(m)
        att.append(a)
    out = {"source": f"nflverse season stats, regular seasons {REAL_YEARS[0]}-{REAL_YEARS[-1]}",
           "seasons": len(per_season)}
    for k in ("qb_efficient_low_volume", "qb_600_rush"):
        v = [m[k] for m in per_season]
        out[k] = {"mean": sum(v) / len(v), "min": min(v), "max": max(v)}
    for k, v in percentiles(att).items():
        out[k] = {"mean": v}
    REAL_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    return out


def real():
    return json.loads(REAL_FILE.read_text(encoding="utf-8"))


def _season(job):
    import simlab
    seed, i = job
    lg = simlab.get_league(str(seed))
    res = simlab.play_season(lg, seed=f"qbstyle-{seed}-{i}", norms=simlab.build_norms(lg))
    plays = res["team_tot"].get("plays", 0) / max(1, res["team_games"])
    return season_measures(game_qbs(res["players"], plays))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="game", choices=["game", "real"])
    ap.add_argument("--seasons", type=int, default=4)
    a = ap.parse_args()
    if a.mode == "real":
        print(json.dumps(build_real(), indent=1))
        return
    jobs = [(s, i) for s in (101, 102, 103) for i in range(a.seasons)]
    with Pool(len(jobs), maxtasksperchild=1) as pool:
        res = pool.map(_season, jobs)
    rl = real()
    att = [a_ for _m, a_ in res]
    game = {k: sum(m[k] for m, _a in res) / len(res) for k in ("qb_efficient_low_volume", "qb_600_rush")}
    game.update(percentiles(att))
    print(f"QB season styles, game ({len(res)} seasons) / real ({rl['source']})")
    for k, lbl in LABELS.items():
        r = rl[k]
        rng = f"  (real seasons {r['min']}-{r['max']})" if "min" in r else ""
        print(f"  {lbl:70} {game.get(k, 0):5.1f} / {r['mean']:5.1f}{rng}")


if __name__ == "__main__":
    main()
