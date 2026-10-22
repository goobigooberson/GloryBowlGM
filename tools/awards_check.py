# awards_check.py
# Do the game's award winners look like the real NFL's? Plays whole seasons
# through the real season loop (preseason, 17 games, playoffs, Pro Bowl,
# Glory Bowl, offseason), then compares the winners' profiles with the real
# 2000-2025 winners (tools/real_awards.py): which positions win, how good
# their teams were, their stats; plus the All-Pro teams, the Pro Bowl
# (who gets in, who doesn't, the fan vote) and Players of the Week.
# Changes nothing in your saves.
#
# Run from the project folder:
#   python tools/awards_check.py                         (3 leagues x 3 seasons, ~15 min)
#   python tools/awards_check.py --leagues 101,102 --seasons 2
#   python tools/awards_check.py --report-only           (just re-read the cached seasons)
#   python tools/awards_check.py --report-only --rescore (re-vote cached seasons with the current knobs:
#                                                          season awards, All-Pro, Pro Bowl vote)
# Each finished season is cached in your temp folder (fof_awards_cache, safe to delete) so the
# voting can be re-tuned without re-simming. The report also goes to
# tools/awards_report.txt.

import argparse
import os
import pickle
import random
import tempfile
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from engine import awards as A                      # noqa: E402
from engine import playoffs as po                   # noqa: E402
from engine import season as S                      # noqa: E402
from engine.league import create_league             # noqa: E402
import real_awards                                  # noqa: E402

# Kept in the PC's temp folder (about 6 MB a season), not the project folder, which syncs to OneDrive.
CACHE = Path(tempfile.gettempdir()) / "fof_awards_cache"
GROUP_ORDER = ["QB", "RB", "WR", "TE", "FB", "EDGE", "DT", "LB", "CB", "S"]


def sim(leagues, seasons):
    CACHE.mkdir(exist_ok=True)
    for name in leagues:
        t0 = time.time()
        league = create_league(seed=int(name))
        league.name = f"Awards check {name}"
        league.user_team_id = None
        S.start_season(league, rng=random.Random(int(name)))
        for i in range(seasons):
            while not S.season_over(league):
                S.play_week(league)
                print(f"  league {name}, {league.season}: {S.week_label(league):<28}", end="\r")
            path = CACHE / f"{name}-{league.season}.pkl"
            with open(path, "wb") as f:
                pickle.dump(league, f)
            print(f"  league {name}, {league.season} done ({time.time() - t0:.0f}s so far)        ")
            if i + 1 < seasons:
                S.start_next_season(league, rng=random.Random(f"{name}-{i}"))


def load_cached():
    out = []
    for path in sorted(CACHE.glob("*.pkl")):
        with open(path, "rb") as f:
            out.append((path.stem, pickle.load(f)))
    return out


def rescore(league):
    """Vote this season again with the current knobs."""
    A.ensure(league)
    s = league.season
    for k in ("season", "all_pro", "pro_bowl", "mvp_watch", "weekly", "monthly"):
        league.awards[k] = [r for r in league.awards[k] if r["season"] != s]
    league.awards["notes"] = [r for r in league.awards["notes"] if r["season"] != s]
    A._cache.clear()
    n = A._n_weeks(league)
    for w in range(1, n + 1):
        A.players_of_the_week(league, w)
        A.mvp_watch(league, w)
    for m in A.MONTHS:
        A.players_of_the_month(league, m)
    A.pro_bowl_vote(league, n - 1)
    A.all_pro(league)
    A.season_awards(league)


def _seed(league, tid):
    return po.seed_of(league, tid)


def winner_rows(leagues):
    """The game's season-award winners, in the same shape as real_awards.winner_lines()."""
    rows = []
    for _name, league in leagues:
        rec = S.records(league)
        n_games = league.settings.get("season_games", 17)
        for r in A.records(league, "season", league.season):
            p = league.player(r["pid"])
            s = r["line"]
            t = rec[r["team"]]
            g = t["w"] + t["l"] + t["t"]
            rows.append({"award": r["award"], "season": league.season, "name": p.name,
                         "group": A.vote_group(p.position, s) if p.position != "FB" else "RB",
                         "kind": r.get("kind"), "team": r["team"], "games": s.get("gp", 0), "team_games": g or n_games,
                         "win_pct": (t["w"] + 0.5 * t["t"]) / g if g else 0.5, "playoffs": _seed(league, r["team"]) is not None,
                         "seed": _seed(league, r["team"]),
                         "pass_yds": s.get("pass_yds", 0), "pass_td": s.get("pass_td", 0),
                         "pass_int": s.get("pass_int", 0), "rush_yds": s.get("rush_yds", 0),
                         "rush_td": s.get("rush_td", 0), "rec": s.get("rec", 0), "rec_yds": s.get("rec_yds", 0),
                         "rec_td": s.get("rec_td", 0), "sacks": s.get("sacks", 0), "def_int": s.get("def_int", 0),
                         "tackles": s.get("tkl", 0) + s.get("ast", 0), "pd": s.get("pd", 0), "ff": s.get("ff", 0),
                         "firsts": r["votes"][0][2], "points": r["votes"][0][3],
                         "margin": r["votes"][0][3] - (r["votes"][1][3] if len(r["votes"]) > 1 else 0)})
    return rows


def fmt_groups(groups):
    return ", ".join(f"{g} {groups[g]:.0%}" for g in sorted(groups, key=lambda g: -groups[g]) if groups[g] > 0)


def report(leagues, out):
    real = real_awards.profiles()
    rows = winner_rows(leagues)
    n_seasons = len(leagues)
    out.append(f"Seasons: {n_seasons} ({', '.join(n for n, _l in leagues)})")
    out.append("Real = AP winners 2000-2025 (tools/real_awards.py); stats are per 17 team games.\n")
    for award, name in real_awards.AWARD_NAMES.items():
        mine = [x for x in rows if x["award"] == award]
        out.append(f"== {name} ==  (game: {len(mine)} winners)")
        rp = real[award]
        groups = Counter(x["group"] for x in mine)
        out.append(f"  positions   game: {fmt_groups({g: c / max(1, len(mine)) for g, c in groups.items()})}")
        out.append(f"              real: {fmt_groups(rp['groups'])}")
        if mine:
            wp = sum(x["win_pct"] for x in mine) / len(mine)
            pl = sum(1 for x in mine if x["playoffs"]) / len(mine)
            gs = sum(min(1, x["games"] / x["team_games"]) for x in mine) / len(mine)
            out.append(f"  team win%   game {wp:.3f} / real {rp.get('win_pct', 0):.3f};  made playoffs game {pl:.0%} / "
                       f"real {rp.get('playoffs', 0):.0%};  played game {gs:.0%} / real {rp.get('games_share', 0):.0%}")
            if award == "mvp":
                top = sum(1 for x in mine if x["seed"] == 1) / len(mine)
                out.append(f"  MVP's team the No. 1 seed: {top:.0%}")
                ap = sum(1 for _n, l in leagues for r in A.records(l, "all_pro", l.season)
                         if r["team_no"] == 1 and any(w["award"] == "mvp" and w["pid"] == r["pid"]
                                                      for w in A.records(l, "season", l.season)))
                out.append(f"  MVP also first-team All-Pro: {ap / len(mine):.0%} (real: almost always; "
                           f"2024 was an exception, Allen MVP and Jackson All-Pro)")
            firsts = [x["firsts"] for x in mine]
            out.append(f"  winner's first-place votes (of 50): avg {sum(firsts) / len(firsts):.0f}, "
                       f"unanimous {sum(1 for f in firsts if f == 50)}, under 30: {sum(1 for f in firsts if f < 30)}")
        for grp in ("QB", "RB", "WR", "EDGE", "DT", "LB", "CB", "S"):
            gl = [x for x in mine if x["group"] == grp]
            if not gl or grp not in rp:
                continue
            stats = list(rp[grp])
            g_avg = {s: sum(x[s] * 17 / x["team_games"] for x in gl) / len(gl) for s in stats}
            out.append(f"  {grp:<4} game: " + ", ".join(f"{s} {g_avg[s]:.1f}" for s in stats) + f"  (n={len(gl)})")
            out.append(f"       real: " + ", ".join(f"{s} {rp[grp][s]:.1f}" for s in stats))
        if award == "opoy":
            mvp = {(x["season"], x["name"]) for x in rows if x["award"] == "mvp"}
            both = sum(1 for x in mine if (x["season"], x["name"]) in mvp) / max(1, len(mine))
            out.append(f"  also MVP    game {both:.0%} / real {rp['also_mvp']:.0%} (since 2016 {rp['also_mvp_since_2016']:.0%})")
        if award == "cpoy":
            kinds = Counter(x["kind"] for x in mine)
            out.append(f"  kind        game: {fmt_groups({k: c / max(1, len(mine)) for k, c in kinds.items()})}; "
                       f"real: {fmt_groups(rp['kinds'])}")
            notes = [r["text"] for _n, l in leagues for r in A.records(l, "notes", l.season) if r.get("award") == "cpoy"]
            if notes:
                out.append(f"  seasons without one: {len(notes)} ({notes[0]})")
        for x in mine:
            out.append(f"    {x['season']} {x['name']:<24} {x['group']:<4} team {x['win_pct']:.3f}"
                       f"{' #' + str(x['seed']) if x['seed'] else ' --'}  {short_line(x)}  "
                       f"({x['firsts']} first-place, {x['points']} pts, by {x['margin']})")
        out.append("")
    all_pro_report(leagues, out)
    pro_bowl_report(leagues, out)
    weekly_report(leagues, out)


def short_line(x):
    g = x["group"]
    if g == "QB":
        return f"{x['pass_yds']:.0f} yds {x['pass_td']:.0f} TD {x['pass_int']:.0f} INT, rush {x['rush_yds']:.0f}"
    if g in ("RB",):
        return f"rush {x['rush_yds']:.0f} yds {x['rush_td']:.0f} TD, rec {x['rec_yds']:.0f}"
    if g in ("WR", "TE"):
        return f"{x['rec']:.0f} rec {x['rec_yds']:.0f} yds {x['rec_td']:.0f} TD"
    return f"{x['sacks']:.1f} sk {x['def_int']:.0f} INT {x['tackles']:.0f} tkl {x['pd']:.0f} PD {x['ff']:.0f} FF"


def all_pro_report(leagues, out):
    out.append("== All-Pro ==")
    per_team = []
    wps = []
    for _name, league in leagues:
        rec = S.records(league)
        firsts = [r for r in A.records(league, "all_pro", league.season) if r["team_no"] == 1]
        c = Counter(r["team"] for r in firsts)
        per_team.append(max(c.values()) if c else 0)
        wps += [(rec[r["team"]]["w"] + 0.5 * rec[r["team"]]["t"]) / 17 for r in firsts]
        unanimous = sum(1 for r in firsts if r["firsts"] == 50)
        out.append(f"  {league.season} ({_name}): {len(firsts)} first-teamers from {len(c)} teams; most from one team "
                   f"{max(c.values()) if c else 0}; unanimous {unanimous}")
    if wps:
        out.append(f"  first-teamers' team win% avg {sum(wps) / len(wps):.3f} (real All-Pros lean to good teams; "
                   f"no clean real number on file)")
    league = leagues[-1][1]
    out.append(f"  Sample, {league.season} first team:")
    for r in A.records(league, "all_pro", league.season):
        if r["team_no"] == 1:
            p = league.player(r["pid"])
            out.append(f"    {A.ALL_PRO_LABEL[r['spot']]:<18} {p.name:<24} {p.position:<3} "
                       f"{league.team(r['team']).abbrev} ({r['firsts']} first-team votes)")
    out.append("")


def pro_bowl_report(leagues, out):
    out.append("== Pro Bowl ==")
    sel_pop, elig_pop, sel_perf, below, sel_share = [], [], [], 0, []
    reasons = Counter()
    from_playoff = []
    games = []
    boosted = []
    for _name, league in leagues:
        n = A._n_weeks(league)
        cands, teams = A.candidates(league, 1, n - 1)
        rows = A.records(league, "pro_bowl", league.season)
        seeds = {t for ids in (league.playoff_seeds or {}).values() for t in ids}
        for r in rows:
            c = cands.get(r["pid"])
            if r["role"] == "selected":
                p = league.player(r["pid"])
                sel_pop.append(p.popularity)
                from_playoff.append(r["team"] in seeds)
                if c:
                    sel_perf.append(c["perf"])
                    if r["spot"] not in ("K", "P", "LS", "RS", "ST"):
                        sel_share.append(c["share"])
                    if c["perf"] < 0 and r["spot"] not in ("RS", "ST"):
                        below += 1
                if r["out"]:
                    reasons[r["out"]] += 1
        for c in cands.values():
            if c["regular"] and c["p"].position not in ("K", "P", "LS"):
                elig_pop.append(c["p"].popularity)
        for g in A.records(league, "pro_bowl_games", league.season):
            games.append(g)
        # The personality effect: how many picks would change without the fan boost?
        boosted.append(_boost_effect(league))
    k = len(leagues)
    sizes = [len(v) for _n, l in leagues for v in A.pro_bowl_roster(l).values()]
    picks = [sum(1 for r in A.records(l, "pro_bowl", l.season) if r["role"] == "selected" and r["conf"] == c)
             for _n, l in leagues for c in A.conferences(l)]
    out.append(f"  selected per conference: {min(picks or [0])}-{max(picks or [0])} (should be 44); playing in the "
               f"game: {min(sizes or [0])}-{max(sizes or [0])}")
    out.append(f"  selected players' popularity avg {sum(sel_pop) / max(1, len(sel_pop)):.0f} "
               f"vs all regulars {sum(elig_pop) / max(1, len(elig_pop)):.0f}")
    out.append(f"  selected players' performance (z vs regulars at the position) avg "
               f"{sum(sel_perf) / max(1, len(sel_perf)):.2f}; below the typical regular: {below} (0 except thin positions, e.g. fullbacks, filled from the rest)")
    out.append(f"  selected players' snap share avg {sum(sel_share) / max(1, len(sel_share)):.0%}, lowest "
               f"{min(sel_share or [0]):.0%}")
    out.append(f"  from playoff teams {sum(from_playoff) / max(1, len(from_playoff)):.0%} (14 of 32 teams make it)")
    out.append(f"  replaced per season: " + ", ".join(f"{k_}: {v / k:.1f}" for k_, v in reasons.items())
               + f"; total {sum(reasons.values()) / k:.1f} of 88 (real: often 40+, counting the Super Bowl teams)")
    out.append(f"  picks changed by the personality boost per season: {sum(boosted) / k:.1f} of 88")
    for g in games:
        sc = g["score"]
        out.append(f"  {g['season']} Pro Bowl at {g['site']}: " + ", ".join(f"{c} {v}" for c, v in sc.items())
                   + (" (OT)" if g["overtime"] else ""))
    out.append("  (Real Pro Bowl tackle games 2010-2022 averaged about 60-70 combined points; this game plays it "
               "like a real game, so expect normal scores)")
    out.append("")


def _boost_effect(league):
    """Re-run the vote without the personality boost and count changed picks."""
    import copy
    saved = A.FAN_PERSONALITY_K
    lg = copy.copy(league)
    lg.awards = {k: list(v) for k, v in league.awards.items()}
    lg.awards["pro_bowl"] = [r for r in lg.awards["pro_bowl"] if r["season"] != league.season]
    before = {(r["conf"], r["spot"], r["pid"]) for r in league.awards["pro_bowl"]
              if r["season"] == league.season and r["role"] == "selected"}
    try:
        A.FAN_PERSONALITY_K = 0.0
        A.pro_bowl_vote(lg, A._n_weeks(league) - 1)
    finally:
        A.FAN_PERSONALITY_K = saved
    after = {(r["conf"], r["spot"], r["pid"]) for r in lg.awards["pro_bowl"]
             if r["season"] == league.season and r["role"] == "selected"}
    return len(before - after)


def weekly_report(leagues, out):
    out.append("== Players of the Week ==")
    by_kind = defaultdict(Counter)
    won = Counter()
    total = Counter()
    for _name, league in leagues:
        for r in A.records(league, "weekly", league.season):
            p = league.player(r["pid"])
            by_kind[r["kind"]][p.position] += 1
            total[r["kind"]] += 1
            won[r["kind"]] += r["pf"] > r["pa"]
    for kind, label in A.WEEKLY_KINDS.items():
        n = max(1, total[kind])
        out.append(f"  {label}: " + ", ".join(f"{pos} {c / n:.0%}" for pos, c in by_kind[kind].most_common())
                   + f";  from the winning team {won[kind] / n:.0%}")
    out.append("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102,103")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args()
    if not args.report_only:
        sim(args.leagues.split(","), args.seasons)
    leagues = load_cached()
    if not leagues:
        raise SystemExit("No cached seasons: run without --report-only first.")
    if args.rescore:
        for _n, league in leagues:
            rescore(league)
    out = []
    report(leagues, out)
    text = "\n".join(out)
    print(text)
    (ROOT / "tools" / "awards_report.txt").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
