# stats.py
# Season stats, built from the box score of every played game: each
# player's season totals, each team's totals, and league leaders.
#
# Regular season and playoffs are kept separate, as in the NFL. Preseason
# games never count (Blake). Career totals will add up these season lines
# once seasons are archived in the offseason (Step 7 piece 4).
#
# Leaders for rate stats (passer rating, yards per carry...) need a minimum
# amount of play, using the NFL's own rules scaled to games played:
#   passing: 14 attempts per team game; rushing: 6.25 carries per team game;
#   receiving: 1.875 catches per team game; field goals: 1 attempt per team
#   game; punting: 2.5 punts per team game (rounded the NFL way);
#   returns: 1 per team game.

from collections import defaultdict

from .sim.stats import passer_rating

REGULAR = "regular"
PLAYOFFS = "playoffs"

_cache = {}


def _games(league, phase):
    pool = league.schedule if phase == REGULAR else getattr(league, "playoffs", [])
    return [g for g in pool if g["played"] and g["id"] in league.boxes]


def player_totals(league, phase=REGULAR):
    """{player id: {"team": team id (latest), "gp": games, stat: total, ...}}."""
    games = _games(league, phase)
    key = (id(league), league.season, phase, len(games))
    if key in _cache:
        return _cache[key]
    out = defaultdict(lambda: defaultdict(float))
    for g in sorted(games, key=lambda g: g["week"]):
        for pid_s, line in league.boxes[g["id"]]["players"].items():
            t = out[int(pid_s)]
            t["team"] = line["team"]
            t["gp"] += 1
            for k, v in line.items():
                if k == "team":
                    continue
                if k.endswith("_long"):
                    t[k] = max(t[k], v)
                else:
                    t[k] += v
    result = {pid: dict(t) for pid, t in out.items()}
    _cache.clear()
    _cache[key] = result
    return result


def player_team_totals(league, phase=REGULAR):
    """Like player_totals, but split by team: {(player id, team id): totals}.
    A player traded mid-season gets one line per team (as on FOF8's cards)."""
    out = defaultdict(lambda: defaultdict(float))
    for g in _games(league, phase):
        for pid_s, line in league.boxes[g["id"]]["players"].items():
            t = out[(int(pid_s), line["team"])]
            t["gp"] += 1
            for k, v in line.items():
                if k == "team":
                    continue
                if k.endswith("_long"):
                    t[k] = max(t[k], v)
                else:
                    t[k] += v
    return {key: dict(t) for key, t in out.items()}


def season_lines(league):
    """Every player's lines for the season just played, ready to archive
    for good: [{"pid", "season", "phase", "team", "stats": {...}}]."""
    rows = []
    for phase in (REGULAR, PLAYOFFS):
        for (pid, tid), s in player_team_totals(league, phase).items():
            rows.append({"pid": pid, "season": league.season, "phase": phase, "team": tid,
                         "stats": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items() if v}})
    return rows


def add_up(lines):
    """Career (or multi-team) totals from several lines: counts added,
    longest plays kept as the best."""
    t = defaultdict(float)
    for s in lines:
        for k, v in s.items():
            if k.endswith("_long"):
                t[k] = max(t[k], v)
            else:
                t[k] += v
    return dict(t)


def career_lines(league, pid, phase=REGULAR):
    """A player's season-by-season lines, oldest first: archived seasons plus
    the season in progress: [{"season", "team", "stats", "current"}]."""
    rows = [{"season": r["season"], "team": r["team"], "stats": r["stats"], "current": False}
            for r in league.career if r["pid"] == pid and r["phase"] == phase]
    for (p, tid), s in player_team_totals(league, phase).items():
        if p == pid:
            rows.append({"season": league.season, "team": tid, "stats": s, "current": True})
    rows.sort(key=lambda r: (r["season"], r["current"]))
    return rows


def team_games(league, phase=REGULAR):
    """{team id: games played}."""
    n = defaultdict(int)
    for g in _games(league, phase):
        n[g["home"]] += 1
        n[g["away"]] += 1
    return n


def team_totals(league, phase=REGULAR):
    """{team id: {"g": games, "pf", "pa", "off": {stat: total}, "def": {stat: total allowed}}}."""
    out = {t.id: {"g": 0, "pf": 0, "pa": 0, "off": defaultdict(float), "def": defaultdict(float)}
           for t in league.teams}
    for g in _games(league, phase):
        box = league.boxes[g["id"]]
        for idx, tid, opp, pf, pa in ((0, g["home"], g["away"], g["home_score"], g["away_score"]),
                                      (1, g["away"], g["home"], g["away_score"], g["home_score"])):
            r = out[tid]
            r["g"] += 1
            r["pf"] += pf
            r["pa"] += pa
            for k, v in box["team"][idx].items():
                r["off"][k] += v
            for k, v in box["team"][1 - idx].items():
                r["def"][k] += v
    return out


# ---------------------------------------------------------------------------
# Team summary (Blake, Oct 21: one page with a team's record, results, team
# and opponent stats with league ranks, and every player's stats, like
# FOF8's Team Summary)
# ---------------------------------------------------------------------------

# (key, label, how to read it, higher is better for the offense)
TEAM_SUMMARY_STATS = [
    ("pts", "Points per game", "1f", True),
    ("yds", "Total yards per game", "1f", True),
    ("rush_g", "Rushes per game", "1f", True),
    ("rush_yds_g", "Rushing yards per game", "1f", True),
    ("ypc", "Yards per carry", "2f", True),
    ("att_g", "Pass attempts per game", "1f", True),
    ("cmp_g", "Completions per game", "1f", True),
    ("cmp_pct", "Completion %", "1f", True),
    ("pass_yds_g", "Passing yards per game", "1f", True),
    ("ypa", "Yards per pass attempt", "2f", True),
    ("ypr", "Yards per catch", "2f", True),
    ("sacked", "Sacks", "int", False),
    ("third", "3rd down conversion %", "1f", True),
    ("giveaways", "Turnovers", "int", False),
]


def _side_numbers(o, g, pts):
    """Per-game and rate numbers for one side of the ball (a team's offense,
    or what it allowed)."""
    att = o.get("pass_att", 0) - o.get("spikes", 0)
    return {
        "pts": pts / g, "yds": (o.get("rush_yds", 0) + o.get("pass_yds", 0) - o.get("sacked_yds", 0)) / g,
        "rush_g": o.get("rush_att", 0) / g, "rush_yds_g": o.get("rush_yds", 0) / g,
        "ypc": o.get("rush_yds", 0) / o["rush_att"] if o.get("rush_att") else 0.0,
        "att_g": att / g, "cmp_g": o.get("pass_cmp", 0) / g,
        "cmp_pct": 100 * o.get("pass_cmp", 0) / att if att else 0.0,
        "pass_yds_g": (o.get("pass_yds", 0) - o.get("sacked_yds", 0)) / g,
        "ypa": o.get("pass_yds", 0) / att if att else 0.0,
        "ypr": o.get("pass_yds", 0) / o["pass_cmp"] if o.get("pass_cmp") else 0.0,
        "sacked": o.get("sacked", 0),
        "third": 100 * o.get("third_conv", 0) / o["third_att"] if o.get("third_att") else 0.0,
        "giveaways": o.get("int_thrown", 0) + o.get("fum_lost", 0),
    }


def _ranks(values, higher_better):
    """{team id: (rank, tied?)}: 1 = best in the league."""
    out = {}
    for tid, v in values.items():
        better = sum(1 for w in values.values() if (w > v if higher_better else w < v) and abs(w - v) > 1e-9)
        tied = sum(1 for w in values.values() if abs(w - v) <= 1e-9) > 1
        out[tid] = (better + 1, tied)
    return out


def team_player_totals(league, team_id, phase=REGULAR):
    """{player id: his totals for this team only} (a player who changed
    teams counts only his games here)."""
    return {pid: s for (pid, tid), s in player_team_totals(league, phase).items() if tid == team_id}


def team_summary(league, team_id, phase=REGULAR):
    """Everything on the Team summary page for one team."""
    from . import playoffs as po, season as se
    tt = team_totals(league, phase)
    played = {tid: r for tid, r in tt.items() if r["g"]}
    offense = {tid: _side_numbers(r["off"], r["g"], r["pf"]) for tid, r in played.items()}
    defense = {tid: _side_numbers(r["def"], r["g"], r["pa"]) for tid, r in played.items()}
    margin = {tid: (r["def"].get("int_thrown", 0) + r["def"].get("fum_lost", 0)
                    - r["off"].get("int_thrown", 0) - r["off"].get("fum_lost", 0)) for tid, r in played.items()}
    lines_off, lines_def = [], []
    if team_id in played:
        for key, label, how, higher in TEAM_SUMMARY_STATS:
            r_off = _ranks({t: v[key] for t, v in offense.items()}, higher)[team_id]
            # A defense is better when the opponent's number is lower (sacks: higher).
            r_def = _ranks({t: v[key] for t, v in defense.items()}, not higher)[team_id]
            lines_off.append((label, offense[team_id][key], how, r_off))
            lines_def.append((label if key != "giveaways" else "Takeaways", defense[team_id][key], how, r_def))
        lines_off.append(("Turnover margin", margin[team_id], "+int", _ranks(margin, True)[team_id]))

    rec = se.records(league)[team_id]
    games = []
    for g in sorted(league.schedule, key=lambda g: g["week"]):
        if team_id in (g["home"], g["away"]):
            games.append(("regular", g))
    for g in sorted(getattr(league, "playoffs", []), key=lambda g: g["week"]):
        if team_id in (g["home"], g["away"]):
            games.append(("playoffs", g))
    log = []
    for kind, g in games:
        home = g["home"] == team_id
        opp = g["away"] if home else g["home"]
        row = {"kind": kind, "week": g["week"], "opp": opp, "home": home, "neutral": bool(g.get("neutral")),
               "played": g["played"], "id": g["id"]}
        if g["played"]:
            pf, pa = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
            row.update(pf=pf, pa=pa, result="W" if pf > pa else "L" if pf < pa else "T", ot=bool(g.get("overtime")))
        log.append(row)

    past = [h for h in league.team_history if h["team"] == team_id]
    history = {"seasons": len(past), "w": sum(h["w"] for h in past), "l": sum(h["l"] for h in past),
               "t": sum(h["t"] for h in past), "playoffs": sum(1 for h in past if h.get("seed")),
               "titles": sum(1 for s, tid in league.champions.items() if tid == team_id and s != league.season)}
    return {
        "record": rec, "games_played": played.get(team_id, {}).get("g", 0),
        "seed": po.seed_of(league, team_id) if getattr(league, "playoff_seeds", None) else None,
        "playoff_result": se.playoff_result(league, team_id) if getattr(league, "playoffs", None) else None,
        "offense": lines_off, "defense": lines_def, "log": log, "history": history,
        "players": team_player_totals(league, team_id, phase),
    }


# ---------------------------------------------------------------------------
# Derived numbers (the way the NFL computes them)
# ---------------------------------------------------------------------------

def pass_att(s):
    """Pass attempts, not counting spikes."""
    return s.get("pass_att", 0) - s.get("spikes", 0)


def derived(s):
    """Rates and combined stats for one player's totals."""
    att = pass_att(s)
    d = {
        "tackles": s.get("tkl", 0) + s.get("ast", 0),
        "cmp_pct": 100 * s.get("pass_cmp", 0) / att if att else 0.0,
        "ypa": s.get("pass_yds", 0) / att if att else 0.0,
        "rating": passer_rating(att, s.get("pass_cmp", 0), s.get("pass_yds", 0), s.get("pass_td", 0),
                                s.get("pass_int", 0)) if att else 0.0,
        "ypc": s.get("rush_yds", 0) / s["rush_att"] if s.get("rush_att") else 0.0,
        "ypr": s.get("rec_yds", 0) / s["rec"] if s.get("rec") else 0.0,
        "fg_pct": 100 * s.get("fgm", 0) / s["fga"] if s.get("fga") else 0.0,
        "punt_avg": s.get("punt_yds", 0) / s["punts"] if s.get("punts") else 0.0,
        "kr_avg": s.get("kr_yds", 0) / s["kr"] if s.get("kr") else 0.0,
        "pr_avg": s.get("pr_yds", 0) / s["pr"] if s.get("pr") else 0.0,
        "scrim_yds": s.get("rush_yds", 0) + s.get("rec_yds", 0),
        "total_td": s.get("rush_td", 0) + s.get("rec_td", 0) + s.get("ret_td", 0) + s.get("def_td", 0),
    }
    d["points"] = 6 * d["total_td"] + 3 * s.get("fgm", 0) + s.get("xpm", 0)
    return d


# ---------------------------------------------------------------------------
# League leaders
# ---------------------------------------------------------------------------

# (key, label, how to read it, minimum per team game for rate stats, what the minimum counts, higher is better)
LEADER_CATEGORIES = {
    "Passing": [
        ("pass_yds", "Passing yards", "int", None, None, True),
        ("pass_td", "Passing TDs", "int", None, None, True),
        ("rating", "Passer rating", "1f", 14, "att", True),
        ("cmp_pct", "Completion %", "1f", 14, "att", True),
        ("ypa", "Yards per attempt", "2f", 14, "att", True),
        ("pass_int", "Interceptions thrown", "int", None, None, True),
    ],
    "Rushing": [
        ("rush_yds", "Rushing yards", "int", None, None, True),
        ("rush_td", "Rushing TDs", "int", None, None, True),
        ("ypc", "Yards per carry", "2f", 6.25, "rush_att", True),
        ("rush_att", "Carries", "int", None, None, True),
    ],
    "Receiving": [
        ("rec_yds", "Receiving yards", "int", None, None, True),
        ("rec", "Receptions", "int", None, None, True),
        ("rec_td", "Receiving TDs", "int", None, None, True),
        ("ypr", "Yards per catch", "1f", 1.875, "rec", True),
    ],
    "Defense": [
        ("tackles", "Tackles", "int", None, None, True),
        ("sacks", "Sacks", "1f", None, None, True),
        ("def_int", "Interceptions", "int", None, None, True),
        ("tfl", "Tackles for loss", "1f", None, None, True),
        ("ff", "Forced fumbles", "int", None, None, True),
        ("pd", "Passes defensed", "int", None, None, True),
    ],
    "Kicking": [
        ("fgm", "Field goals made", "int", None, None, True),
        ("fg_pct", "Field goal %", "1f", 1, "fga", True),
        ("points", "Points", "int", None, None, True),
        ("punt_avg", "Punting average", "1f", 2.5, "punts", True),
    ],
    "Returns": [
        ("kr_avg", "Kick return average", "1f", 1, "kr", True),
        ("pr_avg", "Punt return average", "1f", 0.5, "pr", True),
        ("scrim_yds", "Yards from scrimmage", "int", None, None, True),
        ("total_td", "Total touchdowns", "int", None, None, True),
    ],
}


def value(s, key):
    if key in s:
        return s[key]
    return derived(s).get(key, 0)


def leaders(league, key, phase=REGULAR, n=10, per_game_min=None, min_of=None):
    """Top n players for one stat: [(player, team id, value)]."""
    totals = player_totals(league, phase)
    games = team_games(league, phase)
    by_id = {p.id: p for p in league.players}
    rows = []
    for pid, s in totals.items():
        p = by_id.get(pid)
        if p is None:
            continue
        if per_game_min:
            need = per_game_min * games.get(s["team"], 0)
            have = pass_att(s) if min_of == "att" else s.get(min_of, 0)
            if have < max(1, need):
                continue
        v = value(s, key)
        if v:
            rows.append((p, s["team"], v))
    rows.sort(key=lambda r: -r[2])
    return rows[:n]


def fmt_value(v, how):
    if how == "int":
        return f"{int(round(v)):,}"
    if how == "1f":
        return f"{v:.1f}"
    return f"{v:.2f}"
