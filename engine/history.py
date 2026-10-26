# history.py
# League history and the record book (Oct 25; FOF8's "reward loop": record
# books, franchise histories, the Hall of Fame in hall_of_fame.py). Rules
# only: the History, Records and Hall of Fame pages and the team window's
# History tab read from here.
#
# Built on what the save already keeps for good:
#   - league.career: every player's season lines (stats.season_lines);
#   - league.team_history: every team's season (record, finish, seed, result);
#   - league.champions, league.awards (awards.py), league.draft_history;
#   - the season in progress (stats.player_totals, league.boxes).
# The one new thing kept: the best single-game performances (league.history
# ["game_bests"]), because a finished season's box scores leave the save for
# its history file (database.write_history). They're added when a season ends
# (archive_season, from season.begin_offseason). An older save fills them in
# once from its history file (backfill_games), and a save without a history
# file simply starts its single-game records from the seasons it has.
#
# Records follow the NFL's record book: regular season and playoffs apart
# (FOF8 keeps playoff records too), counting stats with no minimum, rate stats
# with the NFL's minimums (season: per team game, as the Stats tab's leaders;
# career: 1,500 pass attempts, 750 carries, 100 field goal tries).

from collections import defaultdict

from . import awards as A
from . import playoffs as po
from . import stats as ST

GAME_BESTS_KEPT = 25          # best single games kept per stat and phase (the screens show 10)

# (key, label, how to show it, per-team-game minimum for a season, career minimum, what the minimum counts,
#  game minimum)
RECORD_STATS = {
    "Passing": [
        ("pass_yds", "Passing yards", "int", None, None, None, None),
        ("pass_td", "Passing touchdowns", "int", None, None, None, None),
        ("pass_cmp", "Completions", "int", None, None, None, None),
        ("att", "Pass attempts", "int", None, None, None, None),
        ("rating", "Passer rating", "1f", 14, 1500, "att", 20),
        ("cmp_pct", "Completion %", "1f", 14, 1500, "att", 20),
        ("pass_int", "Interceptions thrown", "int", None, None, None, None),
        ("pass_long", "Longest pass", "int", None, None, None, None),
    ],
    "Rushing": [
        ("rush_yds", "Rushing yards", "int", None, None, None, None),
        ("rush_td", "Rushing touchdowns", "int", None, None, None, None),
        ("rush_att", "Carries", "int", None, None, None, None),
        ("ypc", "Yards per carry", "2f", 6.25, 750, "rush_att", 10),
        ("rush_long", "Longest run", "int", None, None, None, None),
    ],
    "Receiving": [
        ("rec", "Receptions", "int", None, None, None, None),
        ("rec_yds", "Receiving yards", "int", None, None, None, None),
        ("rec_td", "Receiving touchdowns", "int", None, None, None, None),
        ("rec_long", "Longest catch", "int", None, None, None, None),
    ],
    "Scoring": [
        ("scrim_yds", "Yards from scrimmage", "int", None, None, None, None),
        ("total_td", "Total touchdowns", "int", None, None, None, None),
        ("points", "Points", "int", None, None, None, None),
    ],
    "Defense": [
        ("sacks", "Sacks", "1f", None, None, None, None),
        ("def_int", "Interceptions", "int", None, None, None, None),
        ("tackles", "Tackles", "int", None, None, None, None),
        ("tfl", "Tackles for loss", "1f", None, None, None, None),
        ("ff", "Forced fumbles", "int", None, None, None, None),
        ("pd", "Passes defensed", "int", None, None, None, None),
        ("def_td", "Defensive touchdowns", "int", None, None, None, None),
    ],
    "Kicking": [
        ("fgm", "Field goals made", "int", None, None, None, None),
        ("fg_pct", "Field goal %", "1f", 1, 100, "fga", None),
        ("fg_long", "Longest field goal", "int", None, None, None, None),
        ("xpm", "Extra points made", "int", None, None, None, None),
        ("punt_avg", "Punting average", "1f", 2.5, 250, "punts", None),
        ("kr_yds", "Kick return yards", "int", None, None, None, None),
        ("pr_yds", "Punt return yards", "int", None, None, None, None),
        ("ret_td", "Return touchdowns", "int", None, None, None, None),
    ],
}
STAT_INFO = {k: (label, how, sm, cm, of, gm, cat)
             for cat, rows in RECORD_STATS.items() for k, label, how, sm, cm, of, gm in rows}
LONGEST = {"pass_long", "rush_long", "rec_long", "fg_long"}   # a play, not a total: single game only
GAME_STATS = [k for k in STAT_INFO if k not in ("fg_pct", "punt_avg")]   # a game is too few kicks to rank
SCOPES = {"game": "Single game", "season": "Single season", "career": "Career"}
PHASES = {ST.REGULAR: "Regular season", ST.PLAYOFFS: "Playoffs"}

# Team records (from team_history and the box scores).
TEAM_SEASON_STATS = [("w", "Most wins", True), ("l", "Most losses", True), ("pf", "Most points scored", True),
                     ("pa", "Fewest points allowed", False), ("diff", "Best point differential", True)]

_cache = {}


def ensure(league):
    """league.history: {"game_bests": {phase: {stat: [[value, pid, team, opp, season, week, game id], ...]}},
    "team_game_bests": {phase: {stat: [...]}}, "seasons": [seasons whose games are in]}. Saved as JSON."""
    h = getattr(league, "history", None)
    if not isinstance(h, dict):
        h = {}
        league.history = h
    h.setdefault("game_bests", {})
    h.setdefault("team_game_bests", {})
    h.setdefault("seasons", [])
    return h


def value(s, key):
    if key == "att":
        return ST.pass_att(s)
    return ST.value(s, key)


# ---------------------------------------------------------------------------
# Single games: kept when a season ends (and backfilled for older saves)
# ---------------------------------------------------------------------------

def _game_rows(season, phase, g, box):
    """(player rows, team rows) for one played game: [(stat, value, pid, team, opp)]."""
    prow, trow = [], []
    if not box:
        return prow, trow
    for pid_s, line in box.get("players", {}).items():
        tid = line.get("team")
        opp = g["away"] if tid == g["home"] else g["home"]
        for k in GAME_STATS:
            v = value(line, k)
            if not v:
                continue
            gm, of = STAT_INFO[k][5], STAT_INFO[k][4]
            if gm and value(line, of) < gm:
                continue
            prow.append((k, v, int(pid_s), tid, opp))
    for tid, opp, pf, pa in ((g["home"], g["away"], g["home_score"], g["away_score"]),
                             (g["away"], g["home"], g["away_score"], g["home_score"])):
        trow.append(("pts", pf, None, tid, opp))
        trow.append(("margin", pf - pa, None, tid, opp))
    return prow, trow


def _merge(bests, rows, season, week, gid, keep=GAME_BESTS_KEPT):
    """Add rows to a {stat: [[value, pid, team, opp, season, week, gid]]} table, keeping the best."""
    touched = set()
    for k, v, pid, tid, opp in rows:
        bests.setdefault(k, []).append([round(v, 2) if isinstance(v, float) else v, pid, tid, opp, season, week, gid])
        touched.add(k)
    for k in touched:
        bests[k].sort(key=lambda r: (-r[0], r[4], r[5]))
        del bests[k][keep:]


def add_games(league, games):
    """games: [(season, phase, g, box)] of played regular-season and playoff games."""
    h = ensure(league)
    for season, phase, g, box in games:
        if phase not in (ST.REGULAR, ST.PLAYOFFS) or not box:
            continue
        prow, trow = _game_rows(season, phase, g, box)
        _merge(h["game_bests"].setdefault(phase, {}), prow, season, g["week"], g["id"])
        _merge(h["team_game_bests"].setdefault(phase, {}), trow, season, g["week"], g["id"])
    _cache.clear()


def archive_season(league):
    """season.begin_offseason, before the season's box scores leave the save: keep its best games."""
    h = ensure(league)
    if league.season in h["seasons"]:
        return
    games = [(league.season, ST.REGULAR, g, league.boxes.get(g["id"])) for g in league.schedule if g["played"]]
    games += [(league.season, ST.PLAYOFFS, g, league.boxes.get(g["id"])) for g in league.playoffs if g["played"]]
    add_games(league, games)
    h["seasons"].append(league.season)


def missing_seasons(league):
    """Finished seasons whose single games aren't in the record book yet (an older save)."""
    h = ensure(league)
    done = {h_["season"] for h_ in league.team_history}
    return sorted(done - set(h["seasons"]))


def backfill_games(league, past_games):
    """An older save: fill in its finished seasons' single games from the history file
    (database.read_history). Seasons with no games there are marked done anyway."""
    h = ensure(league)
    need = set(missing_seasons(league))
    rows = [(r["season"], r["phase"], r["game"], r["box"]) for r in past_games or () if r["season"] in need]
    add_games(league, rows)
    h["seasons"] = sorted(set(h["seasons"]) | need)


# ---------------------------------------------------------------------------
# Season and career totals (archived lines plus the season in progress)
# ---------------------------------------------------------------------------

def _key(league, phase, extra=()):
    return (id(league), league.season, len(league.career), phase,
            sum(1 for g in ST._games(league, phase)), extra)


def season_totals(league, phase=ST.REGULAR, team=None):
    """{(pid, season): {"stats": totals, "teams": [team ids], "current": bool}}. team: lines with that team only."""
    key = _key(league, phase, ("season", team))
    if key in _cache:
        return _cache[key]
    out = {}
    for r in league.career:
        if r["phase"] != phase or (team is not None and r["team"] != team):
            continue
        k = (r["pid"], r["season"])
        e = out.get(k)
        if e is None:
            out[k] = {"lines": [r["stats"]], "teams": [r["team"]], "current": False}
        else:
            e["lines"].append(r["stats"])
            if r["team"] not in e["teams"]:
                e["teams"].append(r["team"])
    for (pid, tid), s in ST.player_team_totals(league, phase).items():
        if team is not None and tid != team:
            continue
        e = out.setdefault((pid, league.season), {"lines": [], "teams": [], "current": True})
        e["lines"].append(s)
        e["current"] = True
        if tid not in e["teams"]:
            e["teams"].append(tid)
    for e in out.values():
        e["stats"] = e["lines"][0] if len(e["lines"]) == 1 else ST.add_up(e["lines"])
        del e["lines"]
    _cache[key] = out
    return out


def career_totals(league, phase=ST.REGULAR, team=None):
    """{pid: {"stats", "teams": [ids, most games first], "first", "last", "seasons", "current"}}."""
    key = _key(league, phase, ("career", team))
    if key in _cache:
        return _cache[key]
    lines = defaultdict(list)
    games = defaultdict(lambda: defaultdict(float))
    years = defaultdict(set)
    current = set()
    for (pid, season), e in season_totals(league, phase, team).items():
        lines[pid].append(e["stats"])
        years[pid].add(season)
        if e["current"]:
            current.add(pid)
        for tid in e["teams"]:
            games[pid][tid] += e["stats"].get("gp", 0) / max(1, len(e["teams"]))
    out = {}
    for pid, ls in lines.items():
        out[pid] = {"stats": ST.add_up(ls), "teams": sorted(games[pid], key=lambda t: -games[pid][t]),
                    "first": min(years[pid]), "last": max(years[pid]), "seasons": len(years[pid]),
                    "current": pid in current}
    _cache[key] = out
    return out


def _passes_min(league, s, key, scope, phase=ST.REGULAR):
    """Rate stats need enough tries: the NFL's minimums in the regular season; in the
    playoffs two games' worth for one postseason and a tenth of the career minimum."""
    _label, _how, per_game, career_min, of, _gm, _cat = STAT_INFO[key]
    if of is None:
        return True
    have = value(s, of)
    if scope == "career":
        return have >= (career_min if phase == ST.REGULAR else career_min / 10)
    games = league.settings.get("season_games", 17) if phase == ST.REGULAR else 2
    return have >= max(1, (per_game or 1) * games)


# ---------------------------------------------------------------------------
# The record book
# ---------------------------------------------------------------------------

def records(league, key, scope="season", phase=ST.REGULAR, n=10, team=None, players=None):
    """The top n for one stat: [{"value", "pid", "teams", "season", "current", "game": {...} or None}].
    scope: game / season / career. team: that franchise's records only. players: only these ids
    (career leaders' filters)."""
    rows = []
    if scope == "game":
        if key not in GAME_STATS:
            return []
        h = ensure(league)
        kept = list(h["game_bests"].get(phase, {}).get(key, []))
        done = set(h["seasons"])
        if league.season not in done:
            pool = league.schedule if phase == ST.REGULAR else league.playoffs
            live = []
            for g in pool:
                if g["played"] and g["id"] in league.boxes:
                    prow, _t = _game_rows(league.season, phase, g, league.boxes[g["id"]])
                    live += [[v, pid, tid, opp, league.season, g["week"], g["id"]]
                             for k, v, pid, tid, opp in prow if k == key]
            kept += live
        for v, pid, tid, opp, season, week, gid in kept:
            if team is not None and tid != team:
                continue
            if players is not None and pid not in players:
                continue
            rows.append({"value": v, "pid": pid, "teams": [tid], "season": season, "current": season == league.season
                         and league.season not in done,
                         "game": {"opp": opp, "week": week, "id": gid, "phase": phase}})
        rows.sort(key=lambda r: (-r["value"], r["season"], r["game"]["week"]))
        return rows[:n]
    if key in LONGEST:
        return []
    if scope == "season":
        for (pid, season), e in season_totals(league, phase, team).items():
            if players is not None and pid not in players:
                continue
            s = e["stats"]
            v = value(s, key)
            if not v:
                continue
            if not _passes_min(league, s, key, "season", phase):
                continue
            rows.append({"value": v, "pid": pid, "teams": e["teams"], "season": season, "current": e["current"],
                         "game": None})
    else:
        for pid, e in career_totals(league, phase, team).items():
            if players is not None and pid not in players:
                continue
            s = e["stats"]
            v = value(s, key)
            if not v:
                continue
            if not _passes_min(league, s, key, "career", phase):
                continue
            rows.append({"value": v, "pid": pid, "teams": e["teams"], "season": (e["first"], e["last"]),
                         "current": e["current"], "game": None})
    rows.sort(key=lambda r: (-r["value"], r["season"] if scope == "season" else r["season"][0]))
    return rows[:n]


def record_holder(league, key, scope="season", phase=ST.REGULAR, team=None):
    top = records(league, key, scope, phase, n=1, team=team)
    return top[0] if top else None


def team_season_records(league, n=5, team=None):
    """{stat: [team season lines best first]} (finished seasons; per-game numbers for 16/17-game fairness
    aren't needed: the league plays one schedule length)."""
    hist = [h for h in league.team_history if team is None or h["team"] == team]
    out = {}
    for key, _label, high in TEAM_SEASON_STATS:
        val = (lambda h: h["pf"] - h["pa"]) if key == "diff" else (lambda h, k=key: h[k])
        out[key] = sorted(hist, key=lambda h: (-val(h) if high else val(h), h["season"]))[:n]
    return out


def team_game_records(league, n=5, team=None, phase=ST.REGULAR):
    """{"pts": [...], "margin": [...]} best single games by a team: [value, None, team, opp, season, week, gid]."""
    h = ensure(league)
    out = {}
    for key in ("pts", "margin"):
        rows = list(h["team_game_bests"].get(phase, {}).get(key, []))
        if league.season not in h["seasons"]:
            pool = league.schedule if phase == ST.REGULAR else league.playoffs
            for g in pool:
                if g["played"]:
                    _p, trow = _game_rows(league.season, phase, g, league.boxes.get(g["id"]) or {"players": {}})
                    rows += [[v, None, tid, opp, league.season, g["week"], g["id"]] for k, v, _x, tid, opp in trow
                             if k == key]
        rows = [r for r in rows if team is None or r[2] == team]
        rows.sort(key=lambda r: (-r[0], r[4], r[5]))
        out[key] = rows[:n]
    return out


# ---------------------------------------------------------------------------
# Season by season
# ---------------------------------------------------------------------------

def seasons(league):
    """Finished seasons, newest first."""
    return sorted({h["season"] for h in league.team_history}, reverse=True)


def championship_name(league, season):
    first = league.settings.get("first_season", season)
    return f"{po.CHAMPIONSHIP} {po.roman(season - first + 1)}"


def season_summary(league, season):
    """One finished season: {"champion", "runner_up", "teams": [lines by finish], "awards", "leaders"}."""
    lines = [h for h in league.team_history if h["season"] == season]
    champ = league.champions.get(season)
    runner = next((h["team"] for h in lines if h.get("result", "").startswith(f"Lost {po.CHAMPIONSHIP}")), None)
    order = {"Won": 0, f"Lost {po.CHAMPIONSHIP}": 1, "Lost in the conference": 2, "Lost in the divisional": 3,
             "Lost in the Wild Card": 4}

    def depth_of(h):
        r = h.get("result") or ""
        return next((v for k, v in order.items() if r.startswith(k)), 5)
    teams = sorted(lines, key=lambda h: (depth_of(h), -(h["w"] + 0.5 * h["t"]), -(h["pf"] - h["pa"])))
    leaders = {}
    tot = season_totals(league, ST.REGULAR)
    for key in ("pass_yds", "pass_td", "rush_yds", "rec", "rec_yds", "sacks", "def_int", "tackles", "fgm"):
        best = None
        for (pid, s), e in tot.items():
            if s != season:
                continue
            v = value(e["stats"], key)
            if v and (best is None or v > best[0]):
                best = (v, pid, e["teams"])
        if best:
            leaders[key] = best
    return {"season": season, "name": championship_name(league, season), "champion": champ, "runner_up": runner,
            "teams": teams, "awards": A.winners(league, season), "leaders": leaders,
            "gb_mvp": next(iter(A.records(league, "gb_mvp", season)), None)}


# ---------------------------------------------------------------------------
# Franchises
# ---------------------------------------------------------------------------

FRANCHISE_LEADER_STATS = ["pass_yds", "pass_td", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td", "sacks",
                          "def_int", "tackles", "fgm", "points"]


def franchise(league, tid):
    """A team's history: year by year, totals, playoff results, titles, best players."""
    years = sorted((h for h in league.team_history if h["team"] == tid), key=lambda h: -h["season"])
    tot = {"seasons": len(years), "w": sum(h["w"] for h in years), "l": sum(h["l"] for h in years),
           "t": sum(h["t"] for h in years), "playoffs": sum(1 for h in years if h.get("seed")),
           "titles": [h["season"] for h in years if league.champions.get(h["season"]) == tid],
           "division_titles": sum(1 for h in years if h.get("div_rank") == 1),
           "finals": [h["season"] for h in years if (h.get("result") or "").startswith(f"Lost {po.CHAMPIONSHIP}")]}
    pw = pl = 0
    for h in years:
        r = h.get("result") or ""
        if not h.get("seed") or r == "Playoffs":
            continue
        # Playoff games won, from how far they went (the 1 seed skips the Wild Card round).
        reached = (4 if r.startswith("Won") else 3 if r.startswith(f"Lost {po.CHAMPIONSHIP}") else
                   2 if "conference" in r else 1 if "divisional" in r else 0)
        pw += max(0, reached - (1 if h["seed"] == 1 else 0))
        pl += 0 if r.startswith("Won") else 1
    tot["playoff_w"], tot["playoff_l"] = pw, pl
    honors = defaultdict(lambda: {"ap1": 0, "ap2": 0, "pb": 0, "awards": []})
    A.ensure(league)
    for r in league.awards["all_pro"]:
        if r["team"] == tid:
            honors[r["pid"]]["ap1" if r["team_no"] == 1 else "ap2"] += 1
    for r in league.awards["pro_bowl"]:
        if r.get("team") == tid and A.played_pro_bowl(r):
            honors[r["pid"]]["pb"] += 1
    for r in league.awards["season"]:
        if r["team"] == tid:
            honors[r["pid"]]["awards"].append((r["season"], A.AWARD_NAME[r["award"]]))
    careers = career_totals(league, ST.REGULAR, tid)

    def score(pid):
        h = honors[pid]
        return 5 * len(h["awards"]) + 4 * h["ap1"] + 2 * h["ap2"] + h["pb"] + careers.get(pid, {}).get("seasons", 0) / 10
    best = sorted((pid for pid in set(honors) | set(careers) if pid in honors), key=lambda pid: -score(pid))[:15]
    return {"years": years, "totals": tot, "best": [(pid, honors[pid], careers.get(pid)) for pid in best]}
