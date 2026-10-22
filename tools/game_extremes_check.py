# tools/game_extremes_check.py
# How often single-game extremes happen, per 17-week season: 400-yard and 5-touchdown passing
# games, 200-yard rushing and receiving games, 3-sack and 15-tackle games... game vs real.
# The realism check covers season totals and leaderboards; this covers the one-game spikes
# the news and Players of the Week are built from (Oct 23: a test league's Week 1 had three
# 5-touchdown passing games and a 6-sack game; the news session saw ~4 LB 15-tackle games a week).
#
# Real: nflverse weekly player stats, regular season 2021-25 (17 games, 272 games a season).
# Sim: generated leagues played with tools/simlab.py (round robin, 17 weeks, 272 games).
# Also: season totals of long field goals (50+, 55+, 60+ attempts and makes).
#
#   python tools/game_extremes_check.py                 # leagues 101,102 x 2 seasons
#   python tools/game_extremes_check.py --leagues 101,102,103 --seasons 3

import argparse
import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import simlab  # noqa: E402

# (label, stat in the game's box, real column(s), threshold)
MEASURES = [
    ("pass yds 350+", "pass_yds", ["passing_yards"], 350),
    ("pass yds 400+", "pass_yds", ["passing_yards"], 400),
    ("pass TD 4+", "pass_td", ["passing_tds"], 4),
    ("pass TD 5+", "pass_td", ["passing_tds"], 5),
    ("INT thrown 4+", "pass_int", ["passing_interceptions"], 4),
    ("rush yds 150+", "rush_yds", ["rushing_yards"], 150),
    ("rush yds 200+", "rush_yds", ["rushing_yards"], 200),
    ("rush TD 3+", "rush_td", ["rushing_tds"], 3),
    ("rec yds 150+", "rec_yds", ["receiving_yards"], 150),
    ("rec yds 200+", "rec_yds", ["receiving_yards"], 200),
    ("receptions 12+", "rec", ["receptions"], 12),
    ("rec TD 3+", "rec_td", ["receiving_tds"], 3),
    ("sacks 3+", "sacks", ["def_sacks"], 3),
    ("sacks 4+", "sacks", ["def_sacks"], 4),
    # Combined tackles = solo + "with assist" + assists (Oct 23 fix: the first version left out
    # def_tackles_with_assist, ~5 a team game, and undercounted real 12+ games 99 vs 151; all three
    # add to the official total, e.g. Oluokun 2021 88 + 14 + 90 = 192, and to the realism benchmark's).
    ("tackles 10+", "tackles", ["def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists"], 10),
    ("tackles 12+", "tackles", ["def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists"], 12),
    ("tackles 15+", "tackles", ["def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists"], 15),
    ("INT 2+ (defender)", "def_int", ["def_interceptions"], 2),
    ("FG made 4+", "fgm", ["fg_made"], 4),
    ("FG att 4+", "fga", ["fg_att"], 4),
    # Oct 23 additions: what's behind the gaps (tackle spread, rushing volume vs efficiency)
    ("assisted tkl 6+", "ast", ["def_tackles_with_assist", "def_tackle_assists"], 6),
    ("carries 25+", "rush_att", ["carries"], 25),
    ("carries 30+", "rush_att", ["carries"], 30),
]
# Totals per season (not games past a line): long field goals by distance.
# Real distances come from the weekly files' made/missed/blocked lists.
FG_TOTALS = [("FG att 50+", "fga50"), ("FG made 50+", "fgm50"), ("FG att 55+", "fga55"), ("FG made 55+", "fgm55"),
             ("FG att 60+", "fga60")]


def _fg_lines(dists_made, dists_missed):
    d = {}
    for lo in (50, 55, 60):
        made = sum(1 for x in dists_made if x >= lo)
        d[f"fgm{lo}"] = made
        d[f"fga{lo}"] = made + sum(1 for x in dists_missed if x >= lo)
    return d


def _dists(s):
    return [int(x) for x in (s or "").split(";") if x.strip()]


def real_counts():
    out = defaultdict(list)
    for yr in range(2021, 2026):
        f = ROOT / "tools" / "data" / "nflverse" / "stats_player" / f"stats_player_week_{yr}.csv.gz"
        c = defaultdict(int)
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            if r["season_type"] != "REG":
                continue
            for label, _k, cols, th in MEASURES:
                v = sum(float(r.get(col) or 0) for col in cols)
                if v >= th:
                    c[label] += 1
            fg = _fg_lines(_dists(r.get("fg_made_list")),
                           _dists(r.get("fg_missed_list")) + _dists(r.get("fg_blocked_list")))
            for label, k in FG_TOTALS:
                c[label] += fg[k]
        for label in [m[0] for m in MEASURES] + [t[0] for t in FG_TOTALS]:
            out[label].append(c[label])
    return out


def sim_counts(leagues, seasons):
    from engine.sim.stats import BoxScore
    games = []
    orig = simlab.Game
    orig_kick = BoxScore.credit_kick

    class Capture(orig):
        def run(self):
            g = super().run()
            games.append(g)
            return g

    def credit_kick(box, res, kick_idx):
        # The box keeps 50+ as one band; note each kick's distance for the 55+ / 60+ totals.
        orig_kick(box, res, kick_idx)
        if res.kind == "fg" and res.kick_distance and res.kick_distance >= 50:
            for lo in (50, 55, 60):
                if res.kick_distance >= lo:
                    box.add(res.kicker, kick_idx, f"fga{lo}")
                    if res.made:
                        box.add(res.kicker, kick_idx, f"fgm{lo}")
    simlab.Game = Capture
    BoxScore.credit_kick = credit_kick
    out = defaultdict(list)
    try:
        for name in leagues:
            lg = simlab.get_league(name)
            norms = simlab.build_norms(lg)
            for i in range(seasons):
                games.clear()
                simlab.play_season(lg, seed=f"extremes-{name}-{i}", norms=norms)
                c = defaultdict(int)
                for g in games:
                    for line in g.box.players.values():
                        line = dict(line)
                        line["tackles"] = line.get("tkl", 0) + line.get("ast", 0)
                        for label, k, _cols, th in MEASURES:
                            if line.get(k, 0) >= th:
                                c[label] += 1
                        for label, k in FG_TOTALS:
                            c[label] += line.get(k, 0)
                for label in [m[0] for m in MEASURES] + [t[0] for t in FG_TOTALS]:
                    out[label].append(c[label])
                print(f"  league {name}, season {i + 1} done", flush=True)
    finally:
        simlab.Game = orig
        BoxScore.credit_kick = orig_kick
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102")
    ap.add_argument("--seasons", type=int, default=2)
    a = ap.parse_args()
    real = real_counts()
    sim = sim_counts(a.leagues.split(","), a.seasons)
    print("\nSINGLE-GAME EXTREMES PER SEASON (272 games)      sim      real   (real range 2021-25)")
    for label in [m[0] for m in MEASURES] + [None] + [t[0] for t in FG_TOTALS]:
        if label is None:
            print("  -- long field goals, season totals --")
            continue
        s = sum(sim[label]) / len(sim[label])
        r = sum(real[label]) / len(real[label])
        flag = "  <<" if (s > 1.5 * max(real[label]) + 1 or s < 0.67 * min(real[label]) - 1) else ""
        print(f"  {label:20s} {s:8.1f}  {r:8.1f}   [{min(real[label])}-{max(real[label])}]{flag}")


if __name__ == "__main__":
    main()
