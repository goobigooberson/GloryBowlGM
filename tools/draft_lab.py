# tools/draft_lab.py
# A fast many-season harness for checking the draft (Step 8): it runs the
# real offseason (retirements, draft, cuts, practice squads) and the real
# training camp (player development) year after year, but skips the games.
# Instead of playing games it makes up what development needs from a season:
#   - each team's record (from how good its starters are, plus luck) for the
#     draft order,
#   - who played (starters most of the snaps, first backups some, the rest
#     little),
#   - injuries at the real rate and length mix (injuries.py), for career
#     effects and retirements.
# Then it follows every drafted player's career: seasons as a starter, Pro
# Bowls (the best at each position each season, as many as the real Pro Bowl
# names incl. alternates), how long he lasts. Nothing is saved.
#
# The game sim isn't used, so this is quick (a season takes a second or two);
# real-game checks of the same thing can be done with season.py later.

import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import depth, development, evaluation, injuries, offseason, transactions   # noqa: E402
from engine.league import create_league                                     # noqa: E402

# Pro Bowl players per position per season, both conferences: the real roster
# (44 per conference since 2023: QB 3, RB 3, FB 1, WR 4, TE 2, T 3, G 3, C 2,
# DE 3, DT 3, OLB 3, ILB 2, CB 4, S 3, K 1, P 1, LS 1) x2, plus about 20% more
# for the alternates who replace injured and Super Bowl players (PFR counts
# them as Pro Bowlers; drafted players 1995-2010 made ~91 a class, plus
# undrafted ones: ~105 a season).
PRO_BOWL = {"QB": 7, "RB": 7, "FB": 2, "WR": 10, "TE": 5, "T": 7, "G": 7, "C": 5, "DE": 7, "DT": 7,
            "OLB": 7, "ILB": 5, "CB": 10, "S": 7, "K": 2, "P": 2, "LS": 2}
# Real Pro Bowl voting isn't a pure ranking of the best players: stats, team
# success and reputation all count, so the same player isn't picked every
# year (real drafted Pro Bowlers 1995-2010: 30.6 per class, 3.0 selections
# each, 38% only once). Votes here = his overall rating + this much luck
# (rating points), tuned to those real repeat rates. A pure ranking gave 14.6
# Pro Bowlers per class with 5.5 selections each.
PRO_BOWL_NOISE = 6.0
INJURIES_PER_SEASON = 820       # game-costing injuries a regular season (real, injuries.py)
STARTER_INJURY_WEIGHT = 1.6      # starters play more snaps, so get hurt more
WIN_SD_FROM_TALENT = 2.4         # wins: talent part (real wins spread ~3.1 with luck)
WIN_LUCK_SD = 1.9


def _z_by_position(players):
    by = defaultdict(list)
    for p in players:
        by[p.position].append(p.overall())
    stat = {}
    for pos_, v in by.items():
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) or 1.0
        stat[pos_] = (m, sd)
    return stat


def fake_season(league, rng):
    """Make up a season's results. Returns (team season lines for the draft
    order, {pid: share of snaps played}). Sets league.season_injuries."""
    starters = {t.id: depth.starter_ids(league.depth_charts.get(t.id, {})) for t in league.teams}
    all_starters = [league.player(pid) for s in starters.values() for pid in s if pid in league.rosters]
    stat = _z_by_position(all_starters)
    strength = {}
    for t in league.teams:
        zs = []
        for pid in starters[t.id]:
            if pid not in league.rosters:
                continue
            p = league.player(pid)
            m, sd = stat[p.position]
            w = 4.0 if p.position == "QB" else 1.0
            zs += [(p.overall() - m) / sd] * int(w)
        strength[t.id] = sum(zs) / max(1, len(zs))
    vals = list(strength.values())
    mu = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)) or 1.0
    lines = []
    for t in league.teams:
        w = 8.5 + WIN_SD_FROM_TALENT * (strength[t.id] - mu) / sd + rng.gauss(0, WIN_LUCK_SD)
        w = max(0, min(17, round(w)))
        lines.append({"team": t.id, "season": league.season, "w": w, "l": 17 - w, "t": 0, "conf": t.conference})
    for conf in ("Eastern", "Western"):
        group = sorted((r for r in lines if r["conf"] == conf), key=lambda r: (r["w"], rng.random()), reverse=True)
        for i, r in enumerate(group):
            r["seed"] = i + 1 if i < 7 else None
    playoff = [r for r in lines if r["seed"]]
    for r in lines:
        r["result"] = "Missed the playoffs"
    # A rough bracket: better seeds win more often.
    alive = sorted(playoff, key=lambda r: (r["seed"], rng.random()))
    for stage in ("Lost in the Wild Card round", "Lost in the divisional round",
                  "Lost in the conference championship", "Lost the final"):
        rng.shuffle(alive)
        alive.sort(key=lambda r: r["seed"] + rng.gauss(0, 3))
        keep = len(alive) // 2 if len(alive) > 2 else 1
        if stage == "Lost in the Wild Card round":
            keep = 8
        for r in alive[keep:]:
            r["result"] = stage
        alive = alive[:keep]
    alive[0]["result"] = "Won the final"
    # Snaps.
    share = {}
    for t in league.teams:
        chart = league.depth_charts.get(t.id, {})
        backups = set()
        for slot, ids in chart.items():
            if len(ids) > 1:
                backups.add(ids[1])
        for p in league.team_players(t.id):
            share[p.id] = 0.85 if p.id in starters[t.id] else (0.3 if p.id in backups else 0.05)
    # Injuries (only the ones that can mark a career are kept, as in the season loop).
    rostered = list(league.rosters)
    weights = [STARTER_INJURY_WEIGHT if pid in starters[league.rosters[pid]] else 1.0 for pid in rostered]
    league.season_injuries = {}
    for pid in rng.choices(rostered, weights=weights, k=INJURIES_PER_SEASON):
        grp, lo, hi = injuries.length_group(rng.random())
        kind = injuries.pick_kind(grp, rng.random())
        weeks = rng.randint(lo, hi)
        if injuries.lasting(kind):
            league.season_injuries.setdefault(pid, []).append([kind, weeks])
        if weeks >= 8:
            share[pid] = share.get(pid, 0) * 0.5
        if weeks >= 9:
            league.__dict__.setdefault("_lab_long_out", set()).add(pid)
    return lines, share


def next_season(league, lines, share, rng):
    """The offseason and training camp, as season.start_next_season does them."""
    serious = dict(league.season_injuries)
    evaluation.record_tape(league, share, league.season)     # the tape other staffs have seen (as the game does)
    league.team_history.extend({k: v for k, v in r.items() if k != "conf"} for r in lines)
    transactions.end_of_season(league)
    for p in league.players:
        if p.id in league.rosters:
            p.experience += 1
    league.season += 1
    report = offseason.run_offseason(league, lines, rng=random.Random(rng.random()))
    development.training_camp(league, share, serious, rng=random.Random(rng.random()))
    for t in league.teams:
        league.auto_depth_chart(t.id)
    # Camp rosters (90) to the 53 and practice squads, as after the preseason (no
    # preseason games or camp injuries here).
    league.stage = "preseason"
    league.pre_week = 5     # the cut comes after the last preseason game, as in the game (staffs
                            # see most of camp's changes by then: evaluation.py's staged reveals)
    transactions.final_cuts(league, {}, {}, 5, random.Random(rng.random()))
    league.season_injuries = {}
    return report


def snapshot(league):
    """This season (after camp): {pid: (team, starter?, overall, pro bowl?, experience)}."""
    out = {}
    starters = set()
    for t in league.teams:
        starters |= depth.starter_ids(league.depth_charts.get(t.id, {}))
    by_pos = defaultdict(list)
    for pid, tid in league.rosters.items():
        p = league.player(pid)
        by_pos[p.position].append(p)
    pro = set()
    rng = random.Random(f"probowl-{league.season}-{league.settings.get('salt', '')}")
    for pos_, group in by_pos.items():
        vote = {p.id: p.overall() + rng.gauss(0, PRO_BOWL_NOISE) for p in group}
        group.sort(key=lambda p: vote[p.id], reverse=True)
        pro.update(p.id for p in group[:PRO_BOWL.get(pos_, 0)])
    for pid, tid in league.rosters.items():
        p = league.player(pid)
        out[pid] = (tid, pid in starters, p.overall(), pid in pro, p.experience)
    return out


def run(seed, seasons, draft_module=None, quiet=False):
    """One league, `seasons` offseasons, with the game's own offseason (since
    Oct 23 it runs engine/draft.py: the class, the AI draft, undrafted
    signings, street free agents, and draft capital in AI depth charts).
    draft_module is accepted for older callers and ignored.
    Returns {"picks": [...], "seasons": {season: snapshot}, "league": league,
    "drafts": [each draft's room notes, trades and picks]}."""
    import time
    from engine import draft_day as DD
    random.seed(f"lab-{seed}")
    league = create_league(seed=seed, camp=False)
    league.settings["salt"] = f"lab{seed}"
    rng = random.Random(f"lab-run-{seed}")
    # Keep each draft's room for the checks (the offseason drops it afterwards).
    # (Since Oct 23 the game's draft runs through draft_day.py, which can stop at
    # your picks; these leagues have no team of yours, so it runs straight through.)
    plain_finish = DD.finish

    def finish(lg, *a, **k):
        room = plain_finish(lg, *a, **k)
        lg.__dict__["_lab_room"] = room
        return room
    DD.finish = finish
    history = {league.season: snapshot(league)}
    reports = []
    drafts = []
    t0 = time.time()
    try:
        for i in range(seasons):
            league.__dict__["_lab_long_out"] = set()
            lines, share = fake_season(league, rng)
            # A starter who missed 9+ games didn't play half the season's snaps
            # (the real measure of a starting season).
            out = league.__dict__["_lab_long_out"]
            snap = history[league.season]
            for pid in out:
                if pid in snap:
                    v = snap[pid]
                    snap[pid] = (v[0], False, v[2], v[3], v[4])
            reports.append(next_season(league, lines, share, rng))
            history[league.season] = snapshot(league)
            room = league.__dict__.pop("_lab_room", None)
            if room is not None:
                drafts.append({"season": room.season, "notes": room.notes, "trades": room.trades,
                               "picks": room.picks, "stats": room.stats,
                               "teams": getattr(room, "team_info", {}), "media": dict(room.board_rank)})
            if not quiet:
                print(f"  league {seed}: season {league.season} done ({time.time() - t0:.0f}s)", flush=True)
    finally:
        DD.finish = plain_finish
    return {"picks": list(league.draft_history), "seasons": history, "league": league, "reports": reports,
            "drafts": drafts}
