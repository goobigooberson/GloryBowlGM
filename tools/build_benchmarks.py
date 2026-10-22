# tools/build_benchmarks.py
# Rebuilds tools/real_nfl_benchmarks.json from the real NFL player stats in
# tools/data (nflverse season stats, 2015-2025). You only need this if the
# data files change (for example, adding a new season). Plain Python.
#
# Run from the project folder:
#     python tools/build_benchmarks.py
#
# Most comparisons use 2021-2025 (the 17-game seasons). Tackles for loss use
# 2024-2025 only, because the NFL started recording far more of them in 2024.
# 2015-2020 seasons are scaled up by 17/16 where they're used at all.

import csv
import gzip
import json
from pathlib import Path

import measures as M

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "real_nfl_benchmarks.json"

GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
         "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL",
         "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
         "CB": "DB", "SAF": "DB", "S": "DB", "FS": "DB", "SS": "DB", "DB": "DB",
         "K": "K", "P": "P"}
RECENT = range(2021, 2026)


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def load_year(year):
    scale = 17 / 16 if year <= 2020 else 1.0
    players = []
    with gzip.open(DATA / f"stats_player_reg_{year}.csv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            grp = GROUP.get(r["position"])
            if grp is None:
                continue
            ast = num(r, "def_tackles_with_assist") + num(r, "def_tackle_assists")
            solo = num(r, "def_tackles_solo")
            p = {"id": r["player_id"], "grp": grp, "pos": r["position"], "team": r["recent_team"],
                 "games": num(r, "games"),
                 "pass_att": num(r, "attempts"), "pass_yds": num(r, "passing_yards"),
                 "pass_td": num(r, "passing_tds"), "pass_int": num(r, "passing_interceptions"),
                 "rush_att": num(r, "carries"), "rush_yds": num(r, "rushing_yards"), "rush_td": num(r, "rushing_tds"),
                 "rec": num(r, "receptions"), "targets": num(r, "targets"),
                 "rec_yds": num(r, "receiving_yards"), "rec_td": num(r, "receiving_tds"),
                 "tackles": solo + ast, "tkl": solo, "ast": ast,
                 "sacks": num(r, "def_sacks"), "def_int": num(r, "def_interceptions"),
                 "pd": num(r, "def_pass_defended"), "ff": num(r, "def_fumbles_forced"),
                 "tfl": num(r, "def_tackles_for_loss"), "qb_hits": num(r, "def_qb_hits"),
                 "fgm": num(r, "fg_made"), "fga": num(r, "fg_att"), "punts": num(r, "pt_att")}
            if scale != 1.0:
                for k, v in list(p.items()):
                    if isinstance(v, float) and k != "games":
                        p[k] = v * scale
            players.append(p)
    return players


def main():
    seasons = {y: load_year(y) for y in range(2015, 2026)}
    per_year = {y: M.measure(ps) for y, ps in seasons.items()}
    common = {}
    for k in per_year[2021]:
        years = range(2024, 2026) if k.startswith("tfl") else RECENT
        vals = [per_year[y][k] for y in years]
        common[k] = {"mean": M.mean(vals), "min": min(vals), "max": max(vals),
                     "max_2015_2025": max(per_year[y][k] for y in per_year)}

    recent = [p for y in RECENT for p in seasons[y]]
    team_games = 32 * 17 * len(RECENT)
    defense = [p for p in recent if p["grp"] in ("DL", "LB", "DB")]
    per_team_game = {k: sum(p[k] for p in recent) / team_games
                     for k in ("tackles", "tkl", "ast", "sacks", "qb_hits", "ff", "pd", "def_int")}
    per_team_game["tfl"] = sum(p["tfl"] for y in (2024, 2025) for p in seasons[y]) / (32 * 17 * 2)

    def solo_share(ps):
        tot = sum(p["tackles"] for p in ps)
        return sum(p["tkl"] for p in ps) / tot if tot else 0
    solo = {"all": solo_share(defense)}
    for g in ("DL", "LB", "DB"):
        solo[g] = solo_share([p for p in defense if p["grp"] == g])
    big = [p for p in defense if p["tackles"] >= 120]
    solo["120_plus_tacklers"] = solo_share(big)

    profiles = {}
    for label, key, groups, years in (
            ("tackles", "tackles", None, RECENT), ("tackles_DL", "tackles", ("DL",), RECENT),
            ("tackles_LB", "tackles", ("LB",), RECENT), ("tackles_DB", "tackles", ("DB",), RECENT),
            ("sacks", "sacks", None, RECENT), ("qb_hits", "qb_hits", None, RECENT),
            ("pd", "pd", None, RECENT), ("ff", "ff", None, RECENT), ("tfl", "tfl", None, (2024, 2025))):
        rows = [M.team_rank_profile(seasons[y], key, groups) for y in years]
        profiles[label] = [M.mean(r[i] for r in rows) for i in range(8)]

    shares = [M.target_share_profile(seasons[y]) for y in RECENT]
    target_share = {"by_rank": [M.mean(s[0][i] for s in shares) for i in range(6)],
                    "top_p90": M.mean(s[1] for s in shares), "top_max": max(s[2] for s in shares)}

    hv = [p for p in recent if p["targets"] >= 140]
    ypt = [p["rec_yds"] / p["targets"] for p in hv]
    high_volume_receivers = {"per_season": len(hv) / len(RECENT), "ypt_mean": M.mean(ypt),
                             "ypt_p90": M.quantile(ypt, 0.9), "ypt_max": max(ypt)}
    wh = [p for p in recent if p["grp"] == "RB" and p["rush_att"] >= 200]
    ypc = [p["rush_yds"] / p["rush_att"] for p in wh]
    workhorse_backs = {"per_season": len(wh) / len(RECENT), "ypc_mean": M.mean(ypc), "ypc_sd": M.stdev(ypc),
                       "ypc_p90": M.quantile(ypc, 0.9), "ypc_max": max(ypc),
                       "td_per_carry": M.mean(p["rush_td"] / p["rush_att"] for p in wh)}

    # Season-to-season change for established full-time players (median).
    def change(stat, groups, minimum, games, pct=True, both=False):
        out = []
        for y in range(2021, 2025):
            nxt = {p["id"]: p for p in seasons[y + 1] if p["games"] >= games}
            for p in seasons[y]:
                if (p["grp"] in groups or p["pos"] in groups) and p["games"] >= games and p[stat] >= minimum and p["id"] in nxt:
                    q = nxt[p["id"]]
                    if both and q[stat] < minimum:
                        continue
                    out.append(abs(q[stat] - p[stat]) / p[stat] if pct else abs(q[stat] - p[stat]))
        return M.median(out)
    for p in recent:
        p["ypc"] = p["rush_yds"] / p["rush_att"] if p["rush_att"] else 0
        p["ypa"] = p["pass_yds"] / p["pass_att"] if p["pass_att"] else 0
        p["ypt"] = p["rec_yds"] / p["targets"] if p["targets"] else 0
    for y in range(2015, 2021):
        for p in seasons[y]:
            p["ypc"] = p["ypa"] = p["ypt"] = 0
    consistency = {
        "wr_targets_pct": change("targets", ("WR",), 90, 15),
        "wr_rec_yds_pct": change("rec_yds", ("WR",), 800, 15),
        "rb_carries_pct": change("rush_att", ("RB",), 180, 15),
        "qb_pass_yds_pct": change("pass_yds", ("QB",), 3000, 16),
        "edge_sacks_pct": change("sacks", ("DE", "OLB", "LB"), 7, 15),
        "tackles_pct": change("tackles", ("DL", "LB", "DB"), 90, 15),
    }
    # Efficiency stats: typical absolute change (players with enough volume both years).
    for key, stat, groups, vol, minimum in (("rb_ypc_abs", "ypc", ("RB",), "rush_att", 150),
                                            ("qb_ypa_abs", "ypa", ("QB",), "pass_att", 350),
                                            ("wr_ypt_abs", "ypt", ("WR",), "targets", 80)):
        out = []
        for y in range(2021, 2025):
            nxt = {p["id"]: p for p in seasons[y + 1] if p[vol] >= minimum}
            for p in seasons[y]:
                if p["grp"] in groups and p[vol] >= minimum and p["id"] in nxt:
                    out.append(abs(nxt[p["id"]][stat] - p[stat]))
        consistency[key] = M.median(out)

    bench = {
        "about": "Real NFL benchmarks built from nflverse player season stats (tools/data). "
                 "Leaderboards/counts: 2021-2025 average and range (tackles for loss: 2024-2025).",
        "common": common,
        "per_team_game_defense": per_team_game,
        "solo_tackle_share": solo,
        "team_rank_profiles": profiles,
        "target_share": target_share,
        "high_volume_receivers": high_volume_receivers,
        "workhorse_backs": workhorse_backs,
        "consistency": consistency,
        # Team averages per game, 2023-2025 regular seasons (from nflverse play-by-play).
        "league_per_team_game": {
            "points": 22.6, "total_yds": 333, "plays": 62.4, "pass_att": 33.0, "cmp_pct": 64.4,
            "pass_yds": 231.6, "ypa": 7.02, "pass_td": 1.45, "int_thrown": 0.73, "sacked": 2.46,
            "rush_att": 26.2, "rush_yds": 117, "ypc": 4.48, "rush_td": 0.91, "fd": 19.2,
            "third_pct": 39.3, "fum_lost": 0.50, "penalties": 6.17, "penalty_yds": 50.1,
            "punts": 3.8, "fga": 2.0, "fg_pct": 85.2, "xp_pct": 95.9},
        # Real 2024 player-games missed to injury, per team (Pro Football Reference via RotoWire):
        # healthiest team 95, most injured 254. Includes camp/preseason injuries.
        "injury_games_missed_2024": {"healthiest_team": 95, "most_injured_team": 254},
    }
    OUT.write_text(json.dumps(bench, indent=1), encoding="utf-8")
    print(f"Wrote {OUT} ({len(common)} leaderboard measures)")


if __name__ == "__main__":
    main()
