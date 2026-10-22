# tools/realism_check.py
# The main realism check. Plays several full seasons (schedule + injuries)
# in several leagues and compares everything to the real NFL:
#   - league averages per team per game
#   - "how common" every kind of season is (leaderboard ranks and how many
#     players pass each mark) for every stat and position group
#   - how each team's stats are shared among its players
#   - defensive volume, solo vs assisted tackles, receivers, workhorse backs
#   - injuries
# Changes and saves nothing.
#
# Run from the project folder (takes roughly 30-60 seconds per season):
#     python tools/realism_check.py
#     python tools/realism_check.py --leagues saved,101,102,103 --seasons 3
#
# --leagues: comma list; "saved" = your saved league, a number = a generated
#            league from that seed. Default: saved (if it exists) + 101,102,103.
# --seasons: seasons per league (default 2). More seasons = steadier averages;
#            16 total is what calibration used.
# The report is printed and saved to tools/realism_report.txt.
# Flags: HIGH / low = the sim average is outside the real five-season range.
# Measures marked * have a known reason they can't match (listed at the end).

import argparse
import json
import time
from pathlib import Path

import measures as M
import simlab

HERE = Path(__file__).resolve().parent
BENCH = json.loads((HERE / "real_nfl_benchmarks.json").read_text(encoding="utf-8"))

LEAGUE_LABELS = [
    ("Points", "points"), ("Total yards", "total_yds"), ("Offensive plays", "plays"),
    ("Pass attempts", "pass_att"), ("Completion %", "cmp_pct"), ("Passing yards (gross)", "pass_yds"),
    ("Yards per attempt", "ypa"), ("Passing TDs", "pass_td"), ("Interceptions thrown", "int_thrown"),
    ("Sacks allowed", "sacked"), ("Rushes (incl. scrambles)", "rush_att"), ("Rushing yards", "rush_yds"),
    ("Yards per carry", "ypc"), ("Rushing TDs", "rush_td"), ("First downs", "fd"),
    ("3rd down conversion %", "third_pct"), ("Fumbles lost", "fum_lost"), ("Penalties", "penalties"),
    ("Penalty yards", "penalty_yds"), ("Punts", "punts"), ("Field goal attempts", "fga"),
    ("Field goal %", "fg_pct"), ("Extra point %", "xp_pct"),
]


def main():
    ap = argparse.ArgumentParser()
    default = ("saved," if simlab.SAVE_FILE.exists() else "") + "101,102,103"
    ap.add_argument("--leagues", default=default)
    ap.add_argument("--seasons", type=int, default=2)
    args = ap.parse_args()

    seasons = []
    started = time.time()
    for name in args.leagues.split(","):
        league = simlab.get_league(name.strip())
        norms = simlab.build_norms(league)
        for i in range(args.seasons):
            t0 = time.time()
            seasons.append(simlab.play_season(league, seed=f"{name}-{i}", norms=norms))
            print(f"  league {name}, season {i + 1}: {time.time() - t0:.0f}s", flush=True)
    n_seasons = len(seasons)

    lines = []
    say = lines.append
    say("=" * 86)
    say(f"  REALISM CHECK: {n_seasons} sim seasons ({args.leagues}; {args.seasons} each) "
        f"in {time.time() - started:.0f}s")
    say("  Real NFL: team averages 2023-25; everything else 2021-25 average (range) unless noted")
    say("=" * 86)

    # 1. League averages
    team_tot, team_games = {}, 0
    for s in seasons:
        for k, v in s["team_tot"].items():
            team_tot[k] = team_tot.get(k, 0) + v
        team_games += s["team_games"]
    avg = simlab.league_averages(team_tot, team_games)
    real = BENCH["league_per_team_game"]
    say("")
    say("  LEAGUE AVERAGES PER TEAM PER GAME           Sim     Real    diff")
    for label, key in LEAGUE_LABELS:
        diff = 100 * (avg[key] - real[key]) / real[key]
        mark = "  <<" if abs(diff) > 6 else ""
        say(f"  {label:38} {avg[key]:7.1f} {real[key]:7.1f} {diff:+6.1f}%{mark}")

    # 2. How common is each stat line
    per = [M.measure(s["players"]) for s in seasons]
    say("")
    say("  HOW COMMON IS EACH STAT LINE (per season)")
    say(f"  {'measure':22}{'sim':>8}{'sim sd':>8}{'real':>8}{'real range':>14}")
    flagged = []
    for key in per[0]:
        vals = [p[key] for p in per]
        mu = M.mean(vals)
        sd = M.stdev(vals)
        r = BENCH["common"][key]
        flag = ""
        if mu > r["max"] * 1.03 + 0.5:
            flag = "HIGH"
        elif mu < r["min"] * 0.97 - 0.5:
            flag = "low"
        star = "*" if key.split("#")[0].split(">=")[0] in M.CAVEATS else " "
        if flag:
            flagged.append((key, star))
        rng_txt = "[%.0f-%.0f]" % (r["min"], r["max"])
        say(f"  {key:21}{star}{mu:8.1f}{sd:8.1f}{r['mean']:8.1f}{rng_txt:>14}  {flag}")

    # 3. Defense volume and solo share
    all_players = [p for s in seasons for p in s["players"]]
    say("")
    say("  DEFENSE PER TEAM PER GAME                    Sim     Real")
    real_d = BENCH["per_team_game_defense"]
    for key in ("tackles", "tkl", "ast", "sacks", "tfl", "qb_hits", "ff", "pd", "def_int"):
        sim_v = sum(p.get(key, 0) for p in all_players) / team_games
        label = {"tkl": "solo tackles", "ast": "assisted tackles", "tfl": "tackles for loss (real 2024-25)",
                 "def_int": "interceptions", "pd": "passes defensed", "ff": "forced fumbles"}.get(key, key)
        say(f"  {label:42} {sim_v:6.2f} {real_d[key]:7.2f}")
    defense = [p for p in all_players if p["grp"] in ("DL", "LB", "DB")]

    def solo_share(ps):
        tot = sum(p.get("tackles", 0) for p in ps)
        return sum(p.get("tkl", 0) for p in ps) / tot if tot else 0
    rs = BENCH["solo_tackle_share"]
    say(f"  Solo share of tackles: all {100*solo_share(defense):.0f}% (real {100*rs['all']:.0f}%), "
        + ", ".join(f"{g} {100*solo_share([p for p in defense if p['grp'] == g]):.0f}% ({100*rs[g]:.0f}%)"
                    for g in ("DL", "LB", "DB")))

    # 4. Team rank profiles
    say("")
    say("  HOW EACH TEAM'S STATS ARE SHARED (team's #1, #2 ... #8 player, season totals)")
    for label, key, groups in (("tackles", "tackles", None), ("tackles_DL", "tackles", ("DL",)),
                               ("tackles_LB", "tackles", ("LB",)), ("tackles_DB", "tackles", ("DB",)),
                               ("sacks", "sacks", None), ("qb_hits", "qb_hits", None),
                               ("pd", "pd", None), ("tfl", "tfl", None), ("ff", "ff", None)):
        rows = [M.team_rank_profile(s["players"], key, groups) for s in seasons]
        simp = [M.mean(r[i] for r in rows) for i in range(8)]
        say(f"  {label:11} real " + " ".join(f"{v:6.1f}" for v in BENCH["team_rank_profiles"][label]))
        say(f"  {'':11} sim  " + " ".join(f"{v:6.1f}" for v in simp))

    # 5. Receivers and backs
    say("")
    shares = [M.target_share_profile(s["players"]) for s in seasons]
    ts = BENCH["target_share"]
    say("  TEAM TARGET SHARE BY RANK  real " + " ".join(f"{v:.3f}" for v in ts["by_rank"])
        + f" | #1 p90 {ts['top_p90']:.3f} max {ts['top_max']:.3f}")
    say("                             sim  " + " ".join(f"{M.mean(s[0][i] for s in shares):.3f}" for i in range(6))
        + f" | #1 p90 {M.mean(s[1] for s in shares):.3f} max {max(s[2] for s in shares):.3f}")
    hv = [p for p in all_players if p.get("targets", 0) >= 140]
    ypt = [p["rec_yds"] / p["targets"] for p in hv]
    rh = BENCH["high_volume_receivers"]
    say(f"  140+ target receivers: {len(hv)/n_seasons:.1f} per season (real {rh['per_season']:.1f}); yards per target "
        f"avg {M.mean(ypt):.2f} (real {rh['ypt_mean']:.2f}), top 10% {M.quantile(ypt, .9):.2f} ({rh['ypt_p90']:.2f}), "
        f"best {max(ypt) if ypt else 0:.2f} ({rh['ypt_max']:.2f})")
    wh = [p for p in all_players if p["grp"] == "RB" and p.get("rush_att", 0) >= 200]
    ypc = [p["rush_yds"] / p["rush_att"] for p in wh]
    rw = BENCH["workhorse_backs"]
    say(f"  200+ carry backs: {len(wh)/n_seasons:.1f} per season (real {rw['per_season']:.1f}); YPC avg {M.mean(ypc):.2f} "
        f"(real {rw['ypc_mean']:.2f}), spread {M.stdev(ypc):.2f} ({rw['ypc_sd']:.2f}), best {max(ypc) if ypc else 0:.2f} "
        f"({rw['ypc_max']:.2f}); TD per carry {100*M.mean(p.get('rush_td', 0)/p['rush_att'] for p in wh):.1f}% "
        f"({100*rw['td_per_carry']:.1f}%)")

    say("")
    say("  SEASON LEADERS (every sim season, lowest to highest) vs real 2021-25 range")
    for label, key, groups in (("Passing yards", "pass_yds", ("QB",)), ("Rushing yards", "rush_yds", None),
                               ("Receiving yards", "rec_yds", None), ("Receptions", "rec", None),
                               ("Tackles", "tackles", None), ("Sacks", "sacks", None)):
        lead = sorted(max((p.get(key, 0) for p in s["players"] if groups is None or p["grp"] in groups), default=0)
                      for s in seasons)
        mkey = {"Passing yards": "pass_yds#1", "Rushing yards": "rush_yds#1", "Receiving yards": "rec_yds#1",
                "Receptions": "rec#1", "Tackles": "tackles#1", "Sacks": "sacks#1"}[label]
        r = BENCH["common"][mkey]
        say(f"  {label:16} {', '.join(f'{v:.0f}' for v in lead)}   (real {r['min']:.0f}-{r['max']:.0f})")

    # 6. Injuries
    say("")
    missed = [s["missed_by_team"] for s in seasons]
    inj = BENCH["injury_games_missed_2024"]
    say("  INJURIES: player-games missed per team, by season (average; healthiest-most injured)")
    say("   " + "  ".join(f"{M.mean(m.values()):.0f} ({min(m.values())}-{max(m.values())})" for m in missed))
    say(f"   Real NFL 2024: healthiest team {inj['healthiest_team']}, most injured {inj['most_injured_team']}"
        " (real totals include camp/preseason injuries)")

    # Summary
    say("")
    say(f"  OUTSIDE THE REAL RANGE: {len(flagged)} of {len(per[0])} measures")
    if flagged:
        say("   " + ", ".join(k + s.strip() for k, s in flagged))
    say("  * Known reasons a measure can't match:")
    for k, why in M.CAVEATS.items():
        say(f"     {k}: {why}")
    say("  Also expected until rosters change during seasons (Step 7 signings/cuts): mid-pack tackle counts")
    say("  run a bit high (real teams use ~46 defenders a season, sim teams ~28).")
    text = "\n".join(lines)
    print(text)
    (HERE / "realism_report.txt").write_text(text, encoding="utf-8")
    print("\n  (Saved to tools/realism_report.txt)")


if __name__ == "__main__":
    main()
