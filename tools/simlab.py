# tools/simlab.py
# Shared helpers for the realism tools: load or generate a league, play a
# full 17-week season with injuries carried week to week, and collect every
# player's season stats in the same format the real benchmarks use.
# Nothing here changes or saves a league.

import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.database import load_league          # noqa: E402
from engine.injury_report import InjuryReport    # noqa: E402
from engine.league import create_league          # noqa: E402
from engine.sim.game import Game                 # noqa: E402
from engine.sim.norms import build_norms         # noqa: E402

# Sim roster positions -> position groups used by the benchmarks.
GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
         "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB",
         "K": "K", "P": "P"}
# The fixed test league the realism tools call "saved": a copy of Blake's first saved
# league (saves/league.db, Oct 19), kept here since Oct 24 when he cleared his saves,
# so the reports stay comparable with earlier ones. Never changed by the tools.
SAVE_FILE = ROOT / "tools" / "data" / "realism_league.db"


def get_league(name, camp=True):
    """'saved' = the fixed test league (tools/data/realism_league.db, never changed);
    a number = a brand-new generated league from that seed (not saved).
    camp: a new league starts at training camp with 90-man rosters, as in
    the game (play_season makes the final cuts before week 1); camp=False
    for tools that play games without a preseason (53s + practice squads)."""
    if name == "saved":
        if not SAVE_FILE.exists():
            raise SystemExit(f"No test league found at {SAVE_FILE}")
        return load_league(SAVE_FILE)
    return create_league(seed=int(name), camp=camp)


def round_robin_weeks(team_ids, weeks, rng):
    """Every team plays a different opponent each week (circle method)."""
    ids = list(team_ids)
    rng.shuffle(ids)
    n = len(ids)
    schedule = []
    for w in range(weeks):
        games = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            games.append((a, b) if (w + i) % 2 == 0 else (b, a))
        schedule.append(games)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return schedule


ROSTER_STATE = ("rosters", "practice", "reserve", "waivers", "transactions", "ir_returns", "elevations",
                "elevated", "depth_charts", "user_team_id",
                # final cuts (Oct 23) also change money, captains and the free-agent pool
                "contracts", "cap_charges", "cap_carry", "contract_log", "june1_used", "fa", "captains",
                "staff_requests")


def _snapshot(league):
    import copy
    state = {k: copy.deepcopy(getattr(league, k, None)) for k in ROSTER_STATE}
    return state, len(league.players), [p.retired for p in league.players]


def _restore(league, snap):
    state, n_players, retired = snap
    for k, v in state.items():
        setattr(league, k, v)
    del league.players[n_players:]           # made-up street free agents signed during the season
    for p, r in zip(league.players, retired):
        p.retired = r                        # players nobody signed at final cuts left the league
    league.__dict__.pop("_index", None)
    league.__dict__.pop("_fa_table", None)


def play_season(league, seed, norms=None, weeks=17, moves=True):
    """Play a season. Returns a dict:
       players: list of player-season dicts (stats + pid, pos, grp, team; gp = games
                played on offense)
       team_tot: summed team box-score totals over all team-games
       team_games: number of team-games
       missed_by_team: {team id: player-games missed to injury}
    moves: the season loop's roster rules (engine/transactions.py): training
    camp and preseason injuries before week 1, final cuts, injured reserve,
    signings, practice squads, elevations. The league's rosters are put back
    as they were afterward, so every season starts from the same rosters.
    Each replay (seed) gets its own hidden season form (gameteam.hidden_form).
    """
    from engine.sim import gameteam
    gameteam.SEASON_KEY = seed
    from engine import transactions as TR
    norms = norms or build_norms(league)
    rng = random.Random(seed)
    schedule = round_robin_weeks([t.id for t in league.teams], weeks, rng)
    # The same injury rules as the season loop: statuses, playing hurt,
    # aggravation and flare-ups by injury (engine/injury_report.py).
    report = InjuryReport({}, {}, lambda cal, pid, what: random.Random(f"{seed}-{what}-{cal}-{pid}"))
    snap = _snapshot(league) if moves else None
    if moves:
        TR.ensure(league)
        league.user_team_id = None            # every team makes AI moves here (your saved team too)
        mrng = random.Random(f"{seed}-moves")
        TR.lab_preseason(league, report, mrng)
    season = defaultdict(lambda: defaultdict(float))
    team_of = {}
    team_tot = defaultdict(float)
    team_games = 0
    missed = defaultdict(int)
    for week, games in enumerate(schedule, start=1):
        for home, away in games:
            unavailable = {tid: report.unavailable(tid, week) for tid in (home, away)}
            hurt = {tid: report.playing_hurt(tid, week) for tid in (home, away)}
            extra = TR.lab_elevations(league, report, (home, away), unavailable) if moves else {}
            for tid in (home, away):
                missed[tid] += len(unavailable[tid])
            g = Game(league, home, away, seed=rng.random(), week=week, norms=norms,
                     unavailable=unavailable, hurt=hurt, extra=extra).run()
            if moves:
                TR.count_reserve_games(league, (home, away))
            for pid, line in g.box.players.items():
                team_of[pid] = g.teams[g.box.owner[pid]].id
                for k, v in line.items():
                    if k.endswith("_long"):
                        season[pid][k] = max(season[pid][k], v)
                    else:
                        season[pid][k] += v
                if line.get("off_snaps"):
                    season[pid]["gp"] += 1          # games he played on offense (as the real stats count games)
            for idx in (0, 1):
                team_games += 1
                team_tot["points"] += g.state.score[idx]
                for k, v in g.box.team[idx].items():
                    team_tot[k] += v
            report.after_game((home, away), week, set(g.box.players), g.injuries())
        report.end_week(week)
        if moves:
            TR.weekly(league, report.injuries, report.recovering, week, f"Week {week}", mrng)
    by_id = {p.id: p for p in league.players}
    if moves:
        _restore(league, snap)
    players = []
    for pid, s in season.items():
        p = by_id[pid]
        grp = GROUP.get(p.position)
        if grp is None:
            continue
        d = dict(s)
        d.update(pid=pid, pos=p.position, grp=grp, team=team_of[pid],
                 tackles=s.get("tkl", 0) + s.get("ast", 0))
        players.append(d)
    return {"players": players, "team_tot": dict(team_tot), "team_games": team_games,
            "missed_by_team": dict(missed)}


def league_averages(team_tot, n):
    """Per team per game, defined the same way as the real NFL numbers."""
    t = defaultdict(float, team_tot)
    att = max(1, t["pass_att"] - t["spikes"])
    return {
        "points": t["points"] / n,
        "total_yds": (t["rush_yds"] + t["pass_yds"] - t["sacked_yds"]) / n,
        "plays": t["plays"] / n,
        "pass_att": t["pass_att"] / n,
        "cmp_pct": 100 * t["pass_cmp"] / att,
        "pass_yds": t["pass_yds"] / n,
        "ypa": t["pass_yds"] / att,
        "pass_td": t["pass_td"] / n,
        "int_thrown": t["int_thrown"] / n,
        "sacked": t["sacked"] / n,
        "rush_att": (t["rush_att"] - t["kneels"]) / n,
        "rush_yds": t["rush_yds"] / n,
        "ypc": (t["rush_yds"] + t["kneels"]) / max(1, t["rush_att"] - t["kneels"]),
        "rush_td": t["rush_td"] / n,
        "fd": (t["fd_rush"] + t["fd_pass"] + t["fd_pen"]) / n,
        "third_pct": 100 * t["third_conv"] / max(1, t["third_att"]),
        "fum_lost": t["fum_lost"] / n,
        "penalties": t["penalties"] / n,
        "penalty_yds": t["penalty_yds"] / n,
        "punts": t["punts"] / n,
        "fga": t["fga"] / n,
        "fg_pct": 100 * t["fgm"] / max(1, t["fga"]),
        "xp_pct": 100 * t["xpm"] / max(1, t["xpa"]),
    }
