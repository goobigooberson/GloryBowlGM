# season.py
# The season, week by week: the preseason (Hall of Fame Game + 4 weeks),
# the regular season, then the playoffs and the Glory Bowl. Make the
# schedules, play a week's games, record every result and box score, carry
# injuries from week to week, and work out the standings. Screens call
# these; they never play games themselves.
#
# Preseason games don't count in the standings or in any stats (Blake).
# Injuries from them do carry into the regular season.
#
# Injuries: a player hurt in week 5 who will miss 2 weeks sits out weeks 6
# and 7 and is back for week 8. Healing goes by calendar weeks (the five
# preseason weeks, the regular-season weeks, then the playoff weeks), so a
# bye week counts as a week of healing (as in the real NFL).
#
# Every game gets its own seed (season + game number), so a game you watch
# snap by snap is the same game the "Sim week" button would have played.

import random

from . import injuries
from . import transactions
from .injury_report import InjuryReport
from . import playoffs as po
from . import schedule as sched
from .sim.game import Game
from .sim.norms import build_norms
from .sim import weather as weather_mod

PRESEASON = "preseason"
REGULAR_SEASON = "regular_season"
PLAYOFFS = "playoffs"
SEASON_COMPLETE = "season_complete"
OLD_SEASON_DONE = "regular_season_done"   # saves from before the playoffs existed
STARTUP_DRAFT = "startup_draft"           # a new league drafting its rosters (draft_day.py), before camp
PRESEASON_WEEKS = sched.PRESEASON_WEEKS
PLAYOFF_KINDS = ("wildcard", "divisional", "conference", "glory_bowl")


def n_weeks(league):
    return league.settings.get("season_games", 17) + 1


def start_season(league, rng=None, carryover=None):
    """Make the whole schedule for league.season, preseason and regular
    season, all at once before the Hall of Fame Game; reset the weeks,
    results and injuries. carryover: last season's long injuries that keep
    players out of the start of this one [(pid, team, kind, games)].
    Then the first week of training camp (practice injuries)."""
    # The league's own dice for the year's schedule (Oct 25: it was unseeded, so a league never played out the
    # same twice and the check tools couldn't compare runs; every save still gets its own schedules).
    rng = rng or random.Random(f"schedule-{league.settings.get('salt', '')}-{league.season}")
    ranks = league.division_ranks or sched.random_division_ranks(league, rng)
    league.schedule = sched.build_schedule(league, league.season, ranks,
                                           league.settings.get("season_games", 17), rng)
    league.preseason = sched.build_preseason(league, league.season, league.schedule, rng)
    league.playoffs = []
    league.playoff_seeds = None
    league.playoff_round = 0
    league.pre_week = 1
    league.week = 1
    league.stage = PRESEASON
    league.injuries = {}
    league.recovering = {}
    league.season_injuries = {}
    league.long_injuries = {}
    league.boxes = {}
    league.settings.setdefault("first_season", league.season)
    if "salt" not in league.settings:
        # This league's own dice for the offseason and training camp, so two
        # leagues don't get the same draws in the same year.
        league.settings["salt"] = rng.randrange(1 << 30)
    from .offseason import talent_targets
    talent_targets(league)        # the first season sets each position's talent level for good
    if not any(r["season"] == league.season for r in league.rating_history):
        # The league's first season: everyone's starting ratings.
        for p in league.players:
            if p.retired is None:
                league.rating_history.append({"pid": p.id, "season": league.season, "ovr": p.overall(),
                                              "pot": p.overall("potential")})
    transactions.ensure(league)
    league.ir_returns, league.elevations, league.elevated, league.waivers = {}, {}, {}, []
    # Last season's long injuries that aren't healed yet (injuries.not_ready_games):
    # out through the preseason and the first games of this one.
    for pid, team, kind, games in carryover or ():
        weeks = PRESEASON_WEEKS + games
        league.injuries[pid] = {"team": team, "weeks": weeks, "part": injuries.name(kind), "week": 0,
                                "kind": kind, "initial": weeks, "carryover": True, "status": "Out"}
    # Training camp opens: its first week of practices.
    practice_week(league, 0)


def practice_week(league, cal):
    """A week of practices in training camp or the preseason (cal 0 = camp
    before the Hall of Fame Game): game-costing practice injuries for the
    90-man camp rosters (older saves: the 53s and practice squads;
    injuries.CAMP_INJURIES_PER_TEAM)."""
    teams = {t.id: league.team_players(t.id) + transactions.practice_players(league, t.id) for t in league.teams}
    rep = report(league)
    rep.on_injury = lambda pid, team, kind, weeks, how: league.injury_history.append(
        {"pid": pid, "season": league.season, "game": "Training camp", "team": team, "kind": kind,
         "weeks": weeks, "how": how})
    for pid, kind, weeks in rep.practice_injuries(teams, cal, injuries.CAMP_INJURIES_PER_TEAM / injuries.CAMP_WEEKS):
        if injuries.lasting(kind):
            league.season_injuries.setdefault(pid, []).append([kind, weeks])
        note_long_injury(league, pid, kind, weeks, cal, league.injuries[pid]["team"])


def carryover_injuries(league):
    """At the end of a season: players whose season-ending injury will keep
    them out of the start of next season (real return patterns,
    injuries.not_ready_games). [(pid, team, kind, games to miss)]."""
    out = []
    for pid, inj in league.long_injuries.items():
        hurt_week = max(0, inj["week"] - PRESEASON_WEEKS)
        rng = random.Random(f"carry-{league.settings.get('salt', '')}-{league.season}-{pid}")
        games = injuries.not_ready_games(inj.get("kind"), hurt_week, rng)
        if games:
            out.append((pid, inj["team"], inj.get("kind"), games))
    return out


def note_long_injury(league, pid, kind, weeks, cal, team):
    """Season-ending injuries this season (for next season's carryover)."""
    if weeks >= injuries.SEASON_ENDING_WEEKS:
        league.long_injuries[pid] = {"kind": kind, "week": cal, "team": team}


def add_preseason(league, rng=None):
    """For a save made before the preseason existed, at regular-season week 1
    with nothing played: add this year's preseason in front of it."""
    league.preseason = sched.build_preseason(league, league.season, league.schedule, rng or random.Random(
        f"preseason-{league.settings.get('salt', '')}-{league.season}"))
    league.pre_week = 1
    league.stage = PRESEASON


def bring_up_to_date(league):
    """Older saves: a regular season that finished before the playoffs
    existed goes straight to the playoffs."""
    league.settings.setdefault("first_season", league.season)
    if league.stage == STARTUP_DRAFT:
        return                  # a new league's startup draft: rosters are being drafted (draft_day.py)
    if league.stage == OLD_SEASON_DONE:
        start_playoffs(league)
    # Saves from before the Oct 22 fix: injuries from regular-season conference
    # games were dated after the regular season (counted as playoff games), so
    # they never counted. Date them to last week so they count and heal.
    now = calendar(league)
    for inj in league.injuries.values():
        if inj["week"] > now:
            inj["week"] = now - 1
    # Saves from before roster moves (Oct 22): every team gets its practice squad.
    transactions.ensure(league)
    if not league.practice and league.stage not in (SEASON_COMPLETE, PRESEASON, "offseason"):
        transactions.form_practice_squads(league, league.injuries, league.recovering,
                                          rng=random.Random(f"ps-{league.settings.get('salt', '')}-{league.season}"))
        league.added_practice_squads = True
    # Saves from before contracts (Oct 23): everyone on a team gets a realistic contract.
    from . import free_agency
    free_agency.ensure(league)
    if not league.contracts:
        free_agency.initial_contracts(league)
        league.added_contracts = True


# ---------------------------------------------------------------------------
# Looking things up
# ---------------------------------------------------------------------------

def in_preseason(league):
    return league.stage == PRESEASON


def in_regular_season(league):
    return league.stage == REGULAR_SEASON


def in_playoffs(league):
    return league.stage == PLAYOFFS


def season_over(league):
    """No games left this season (the Glory Bowl has been played)."""
    return league.stage == SEASON_COMPLETE


def calendar(league):
    """Weeks since the preseason began: preseason weeks 1-5, then the
    regular-season weeks, then the playoff rounds. Injuries heal by this count."""
    if in_preseason(league):
        return league.pre_week
    if in_regular_season(league):
        return PRESEASON_WEEKS + league.week
    if in_playoffs(league):
        return PRESEASON_WEEKS + n_weeks(league) + league.playoff_round
    return PRESEASON_WEEKS + n_weeks(league) + 6


def game_calendar(league, g):
    if is_preseason_game(g):
        return g["week"]
    if is_playoff_game(g):
        return PRESEASON_WEEKS + n_weeks(league) + g["week"]
    return PRESEASON_WEEKS + g["week"]


def is_preseason_game(g):
    return g.get("kind") in ("hof", "preseason")


def is_playoff_game(g):
    # By id, not kind: regular-season games against conference opponents are
    # also kind "conference" (the schedule's name for them), and until Oct 22
    # this check counted them as playoff games (playoff overtime, January
    # weather, and their injuries dated after the regular season, so injured
    # players kept playing and didn't heal on schedule).
    return g.get("id", 0) >= po.PLAYOFF_ID_START and g.get("kind") in PLAYOFF_KINDS


def week_games(league, week=None):
    """Regular-season games of a week."""
    week = league.week if week is None else week
    return [g for g in league.schedule if g["week"] == week]


def preseason_games(league, week=None):
    week = league.pre_week if week is None else week
    return [g for g in league.preseason if g["week"] == week]


def playoff_games(league, rnd=None):
    rnd = league.playoff_round if rnd is None else rnd
    return [g for g in league.playoffs if g["week"] == rnd]


def current_games(league):
    """This week's games: preseason, regular season or playoffs."""
    if in_preseason(league):
        return preseason_games(league)
    if in_regular_season(league):
        return week_games(league)
    if in_playoffs(league):
        return playoff_games(league)
    return []


def team_game(league, team_id, week=None):
    """This team's regular-season game in a week, or None if it's their bye."""
    return next((g for g in week_games(league, week) if team_id in (g["home"], g["away"])), None)


def team_current_game(league, team_id):
    """This team's game this week (any part of the season), or None."""
    return next((g for g in current_games(league) if team_id in (g["home"], g["away"])), None)


def games_left(league, team_id=None):
    """Weeks left in this season from now, preseason through the last playoff
    round (an injury at least this long ends his season)."""
    return PRESEASON_WEEKS + n_weeks(league) + 5 - calendar(league) + 1


def team_schedule(league, team_id):
    return sorted((g for g in league.schedule if team_id in (g["home"], g["away"])), key=lambda g: g["week"])


def team_preseason(league, team_id):
    return sorted((g for g in league.preseason if team_id in (g["home"], g["away"])), key=lambda g: g["week"])


def all_games(league):
    return league.preseason + league.schedule + league.playoffs


def last_team_game(league, team_id):
    """This team's most recent played game (any part of the season), or None."""
    played = [g for g in all_games(league) if g["played"] and team_id in (g["home"], g["away"])]
    return max(played, key=lambda g: game_calendar(league, g)) if played else None


def bye_week(league, team_id):
    played = {g["week"] for g in team_schedule(league, team_id)}
    return next((w for w in range(1, n_weeks(league) + 1) if w not in played), None)


def unavailable(league, team_id, cal=None):
    """Players who can't play this week because of an injury from an earlier week."""
    return report(league).unavailable(team_id, calendar(league) if cal is None else cal)


def week_label(league):
    """'Hall of Fame Game week', 'Preseason week 2', 'Week 7', 'Wild Card round'."""
    if league.stage == "offseason":
        ph = offseason_phase(league)
        return ph[1] if ph else "Offseason"
    if in_preseason(league):
        return preseason_week_name(league.pre_week)
    if in_regular_season(league):
        return f"Week {league.week}"
    if in_playoffs(league):
        if league.playoff_round == 5:
            return po.championship_name(league)
        return po.ROUND_NAMES[league.playoff_round]
    return "Season complete"


def preseason_week_name(week):
    return "Hall of Fame Game week" if week == 1 else f"Preseason week {week - 1}"


# ---------------------------------------------------------------------------
# Playing games
# ---------------------------------------------------------------------------

def _preseason_game_numbers(league, g):
    """Each team's preseason game number (1-4) for this game."""
    out = {}
    for tid in (g["home"], g["away"]):
        out[tid] = 1 + sum(1 for x in league.preseason
                           if x["week"] < g["week"] and tid in (x["home"], x["away"]))
    return out


def new_game(league, g, norms=None):
    """A Game object for a scheduled game, ready to play (or to watch)."""
    cal = game_calendar(league, g)
    # The league's own dice (its salt) go into every game's seed: before Oct 23 the seed was only
    # the season and game id, so every save drew the same dice (and the same weather) for the
    # same game slot. Within one save a game still plays out the same if it's replayed.
    seed = f"{league.settings.get('salt', '')}-{league.season}-{g['id']}"
    kw = {}
    if is_preseason_game(g):
        # Preseason weeks are in August: the weather looks up "week 0 and earlier".
        kw["week"] = g["week"] - PRESEASON_WEEKS
        kw["preseason"] = _preseason_game_numbers(league, g)
        if g.get("neutral"):
            kw["neutral"] = True
            # Canton, Ohio has Cleveland's weather.
            kw["weather"] = weather_mod.generate("CLE", league.season, kw["week"], random.Random(seed + "-weather"))
    elif is_playoff_game(g):
        kw["week"] = n_weeks(league) + g["week"]          # January / February weather
        kw["playoff"] = True
        if g.get("neutral"):
            kw["neutral"] = True
            kw["weather"] = weather_mod.generate(po.glory_bowl_site(league), league.season, kw["week"],
                                                 random.Random(seed + "-weather"))
    else:
        kw["week"] = g["week"]
    out = {tid: unavailable(league, tid, cal) for tid in (g["home"], g["away"])}
    transactions.ensure(league)
    extra = {}
    for tid in (g["home"], g["away"]):
        if is_preseason_game(g):
            # Practice squad players are still on the camp roster in the preseason: they play.
            extra[tid] = transactions.practice_players(league, tid)
            continue
        if tid not in league.elevated:
            # AI teams elevate practice squad players when they're short, and now and then for
            # depth (transactions.py). Your team, if you haven't picked anyone yourself: your
            # staff does the same in staff mode, and only the short-handed call-ups otherwise.
            mine = tid == league.user_team_id
            routine = not mine or transactions.staff_runs_practice_squad(league)
            league.elevated[tid] = [p.id for p in transactions.elevations_for_game(league, league.injuries, tid,
                                                                                    out[tid], routine)]
        extra[tid] = [league.player(pid) for pid in league.elevated.get(tid, [])]
    return Game(league, g["home"], g["away"], seed=seed, norms=norms or build_norms(league),
                unavailable=out, hurt={tid: playing_hurt(league, tid, cal) for tid in (g["home"], g["away"])},
                extra=extra, **kw)


def playing_hurt(league, team_id, cal=None):
    """{player id: rating points off} for players listed Questionable this week
    who will play (by injury; engine/injury_report.py)."""
    return report(league).playing_hurt(team_id, calendar(league) if cal is None else cal)


def _compact(d):
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items() if v}


def site_text(league, g):
    """Where a neutral-site game was played."""
    if g.get("kind") == "hof":
        return sched.HOF_SITE
    if g.get("kind") == "glory_bowl":
        site = po.glory_bowl_site(league)
        team = next((t for t in league.teams if t.abbrev == site), None)
        return team.city if team else site
    return ""


def record_game(league, g, game):
    """Store a finished game: score, box score and the injuries it caused."""
    if g["played"]:
        return
    home, away = game.teams
    g["played"] = True
    g["home_score"], g["away_score"] = game.state.score[0], game.state.score[1]
    g["overtime"] = bool(game.overtime)
    box = game.box
    ids = (home.id, away.id)
    site = site_text(league, g) if g.get("neutral") else ""
    league.boxes[g["id"]] = {
        "players": {str(pid): {"team": ids[box.owner[pid]], **_compact(line)}
                    for pid, line in box.players.items() if pid in box.owner},
        "team": [_compact(box.team[0]), _compact(box.team[1])],
        "quarters": box.quarter_points,
        "scoring": [{"team": ids[s["team"]], "qtr": s["qtr"], "clock": s["clock"], "text": s["text"],
                     "score": list(s["score"])} for s in box.scoring],
        "drives": [{"team": ids[d["team"]], "qtr": d["qtr"], "clock": d["clock"], "start_yl": d["start_yl"],
                    "plays": d["plays"], "yards": d["yards"], "time": d["time"], "result": d["result"]}
                   for d in box.drives],
        "weather": (site + ". " if site else "") + game.weather.text(),
    }
    if getattr(game, "books", None) or getattr(league, "playcall_film", None):
        # Plays you called go on film for your next opponents (engine/sim/playcalling.py).
        from .sim import playcalling
        playcalling.save_film(league, game)
    cal = game_calendar(league, g)
    played_ids = {int(k) for k in league.boxes[g["id"]]["players"]}
    label = game_label(league, g)

    def log_injury(pid, team, kind, weeks, how):
        # Every injury, kept for good: the player's injury history (player report, player card).
        league.injury_history.append({"pid": pid, "season": league.season, "game": label, "team": team,
                                      "kind": kind, "weeks": weeks, "how": how})
    rep = report(league)
    rep.on_injury = log_injury
    for pid, kind, weeks_out in rep.after_game(ids, cal, played_ids, game.injuries()):
        # Injuries that can mark a career (step back, lower ceiling, retirement),
        # applied at next training camp (development.py, offseason.py).
        if injuries.lasting(kind):
            league.season_injuries.setdefault(pid, []).append([kind, weeks_out])
        note_long_injury(league, pid, kind, weeks_out, cal, league.injuries[pid]["team"])
    # Reserve lists: one more game missed; elevated players go back to the practice squad.
    if not is_preseason_game(g):
        transactions.count_reserve_games(league, ids)
        for tid in ids:
            transactions.record_elevations(league, tid, [league.player(pid) for pid in league.elevated.get(tid, [])],
                                           label)
            if getattr(league, "contracts", None) and league.elevated.get(tid):
                from . import free_agency
                free_agency.elevation_pay(league, tid, list(league.elevated[tid]))   # a game check at the minimum
            league.elevated.pop(tid, None)


def game_label(league, g):
    """'Week 7', 'Preseason week 2', 'Hall of Fame Game', 'Wild Card round', 'Glory Bowl I'."""
    if is_preseason_game(g):
        return "Hall of Fame Game" if g.get("kind") == "hof" else preseason_week_name(g["week"])
    if is_playoff_game(g):
        return po.championship_name(league) if g["week"] == 5 else po.ROUND_NAMES[g["week"]]
    return f"Week {g['week']}"


def injury_history(league, pid):
    """His injuries, most recent first: [{season, game, team, kind, weeks, how}]."""
    return [r for r in reversed(league.injury_history) if r["pid"] == pid]


def report(league):
    """The league's injury report (engine/injury_report.py), with dice seeded
    by league, season, week and player (the same every time a week is
    replayed or reloaded)."""
    return InjuryReport(league.injuries, league.recovering,
                        lambda cal, pid, what: random.Random(
                            f"{what}-{league.settings.get('salt', '')}-{league.season}-{cal}-{pid}"))


def injury_status(league, pid):
    """His status for the next game: 'Out', 'Doubtful', 'Questionable',
    'Injured reserve', 'Concussion protocol', or None (healthy)."""
    return report(league).status(pid)


def user_moves_open(league):
    """Can you make roster moves right now? (Not once the season is over:
    the offseason sorts rosters out.)"""
    return not season_over(league)


def _user_has_game(league):
    g = team_current_game(league, league.user_team_id) if league.user_team_id else None
    return bool(g and not g["played"] and not is_preseason_game(g))


def user_options(league, pid):
    """Your possible moves with a player: [(action, label, tooltip)]."""
    if league.user_team_id is None or not user_moves_open(league):
        return []
    return transactions.user_options(league, league.injuries, pid, league.user_team_id, _user_has_game(league))


def user_move(league, action, pid):
    """Make one of your roster moves (transactions.py). (done, message)."""
    if not user_moves_open(league):
        return False, "The season is over: rosters are set in the offseason."
    return transactions.user_move(league, league.injuries, league.recovering, action, pid, league.user_team_id,
                                  calendar(league), week_label(league), _user_has_game(league))


def staff_requests(league):
    """Moves your staff wants to make but asks you about first: [{why, ...}]."""
    return getattr(league, "staff_requests", None) or []


def answer_staff_request(league, index, approve):
    """Approve or decline one of your staff's requests. (done, message)."""
    reqs = staff_requests(league)
    if 0 <= index < len(reqs) and "cap" in reqs[index].get("then", {}):
        from . import free_agency
        return free_agency.answer_cap_request(league, index, approve)
    return transactions.answer_request(league, league.injuries, league.recovering, index, approve,
                                       calendar(league), week_label(league),
                                       random.Random(f"ask-{league.settings.get('salt', '')}-{league.season}-"
                                                     f"{calendar(league)}"))


class CapHold(Exception):
    """You're over the salary cap at one of the NFL's deadlines (see cap_hold)."""


def cap_hold(league):
    """Is your team over the salary cap at a deadline? The real NFL's cap is
    hard: every team must be under it when the new league year starts (before
    free agency opens; the top-51 rule applies then) and when the regular
    season starts (every contract counts from week 1). AI teams always are;
    you can't move on until you are (Blake, Oct 24). Returns None, or {"when",
    "short" ($K over)}; your staff's suggested moves are on the Roster tab."""
    tid = league.user_team_id
    if tid is None or not getattr(league, "contracts", None):
        return None
    from . import contracts as C
    from . import free_agency as FA
    when = None
    if in_offseason(league) and offseason_phase(league)[0] == "resign":
        when = "the new league year starts (Next opens free agency)"
    elif in_regular_season(league) and league.week == 1:
        g = team_current_game(league, tid)
        if g and not g["played"]:
            when = "the regular season starts (every contract counts from week 1)"
    if when is None:
        return None
    room = C.cap_room(league, tid)
    if room >= 0:
        return None
    FA.request_cap_moves(league, tid)       # your staff's suggestions (restructures first, then cuts)
    return {"when": when, "short": -room}


def _check_cap_hold(league):
    hold = cap_hold(league)
    if hold:
        from .contracts import fmt_money
        raise CapHold(f"You're {fmt_money(hold['short'])} over the salary cap. Every team must be under it "
                      f"when {hold['when']}.")


def play_week(league):
    """Play every game this week that hasn't been played (yours too, unless
    you already watched it), then move on to the next week."""
    if season_over(league):
        return []
    _check_cap_hold(league)
    transactions.ensure(league)
    league.staff_moves = []
    if league.user_team_id is not None and not in_preseason(league):
        g = team_current_game(league, league.user_team_id)
        if g and not g["played"]:
            # Simming ahead: if your team can't legally take the field, your staff
            # makes the smallest moves that fix it (you see them on the Roster screen).
            league.staff_moves = transactions.staff_minimum(
                league, league.injuries, league.recovering, league.user_team_id, calendar(league),
                week_label(league), random.Random(f"staff-{league.settings.get('salt', '')}-{league.season}-"
                                                  f"{calendar(league)}"))
    norms = build_norms(league)
    played = []
    for g in current_games(league):
        if not g["played"]:
            game = new_game(league, g, norms).run()
            record_game(league, g, game)
            played.append(g)
    league.week_played = True         # contracts.pay_week: this week's check is paid now
    try:
        end_week(league)
    finally:
        league.week_played = False
    return played


def start_playoffs(league):
    """The regular season is over: seed the playoffs, set the Wild Card
    games, and record each team's division finish for next season's
    schedule."""
    league.playoff_seeds = po.seeds(league)
    league.division_ranks = po.division_ranks(league)
    league.playoffs = []
    league.playoff_round = 1
    league.stage = PLAYOFFS
    po.make_round(league, 1)


def playoff_result(league, tid):
    """How a team's season ended: 'Won Glory Bowl I', 'Lost in the divisional round'..."""
    if po.seed_of(league, tid) is None:
        return "Missed the playoffs"
    if po.champion(league) == tid:
        return f"Won {po.championship_name(league)}"
    lost = next((g for g in league.playoffs if g["played"] and po.loser(g) == tid), None)
    if lost is None:
        return "Playoffs"
    return {1: "Lost in the Wild Card round", 2: "Lost in the divisional round",
            3: "Lost in the conference championship",
            5: f"Lost {po.championship_name(league)}"}[lost["week"]]


def team_season_summary(league):
    """One line per team for the season just finished (kept for good)."""
    rec = records(league)
    ranks = po.division_ranks(league)
    out = []
    for t in league.teams:
        r = rec[t.id]
        out.append({"team": t.id, "season": league.season, "w": r["w"], "l": r["l"], "t": r["t"],
                    "pf": r["pf"], "pa": r["pa"], "div_rank": ranks.get(t.id, 0) + 1,
                    "seed": po.seed_of(league, t.id), "result": playoff_result(league, t.id)})
    return out


def snap_shares(league):
    """{player id: share of his team's snaps this regular season} (offense or
    defense, whichever he played more of)."""
    from . import stats
    team = stats.team_totals(league, stats.REGULAR)
    out = {}
    for pid, s in stats.player_totals(league, stats.REGULAR).items():
        t = team.get(s["team"])
        if not t:
            continue
        off_plays = t["off"].get("plays", 0) or 1
        def_plays = t["def"].get("plays", 0) or 1
        out[pid] = max(s.get("off_snaps", 0) / off_plays, s.get("def_snaps", 0) / def_plays)
    return out


OFFSEASON = "offseason"
OFFSEASON_PHASES = {
    "coaching": ("Coaching changes",
                 "The coaching carousel: fire or extend your coaches, then make offers to candidates. Each "
                 "Next settles one round (head coaches; coordinators and assistant head coaches; the rest). "
                 "Jobs still open after the last round get your staff's pick."),
    "resign": ("Start of the league year",
               "Re-sign or tag your expiring players, or let them go. Other teams have made their "
               "decisions. Anyone you haven't re-signed becomes a free agent when the market opens."),
    "fa": ("Free agency", "Make offers to free agents. When you press Next, the wave plays out: every "
                          "player picks the offer he likes best, yours or another team's."),
    "draft": ("The draft is next", "Last chance to scout (Draft tab). Next starts the draft: scouting ends, "
                                   "and pick 1 goes on the clock in the draft room."),
    "drafting": ("The draft", "Watch it pick by pick in the draft room at the speed you choose and make "
                              "your picks there. Next lets your staff make the rest of your picks and "
                              "finishes the draft."),
    "camp": ("Free agency is over", "Next opens training camp: every team fills its roster to 90 (your "
                                    "staff adds cheap camp bodies at your thinnest spots), players develop, "
                                    "and the preseason schedule is set."),
}


def in_offseason(league):
    return league.stage == OFFSEASON


def offseason_phase(league):
    """(phase key, title, explanation) of where the offseason is, or None."""
    if not in_offseason(league):
        return None
    st = getattr(league, "offseason", None) or {}
    key = st.get("phase", "resign")
    title, text = OFFSEASON_PHASES.get(key, ("Offseason", ""))
    if key == "fa":
        from .free_agency import WAVES
        title = f"Free agency, wave {st.get('wave')}: {WAVES.get(st.get('wave'), '')}"
    elif key == "coaching":
        from .staff import ROUND_NAMES
        rnd = ((getattr(league, "staff", None) or {}).get("carousel") or {}).get("round", 1)
        title = f"Coaching changes, round {rnd} of 3: {ROUND_NAMES.get(rnd, '')}"
    return key, title, text


def begin_offseason(league, rng=None):
    """The season is complete: keep its records for good and start the new
    league year (offseason.offseason_start). The offseason then goes phase by
    phase (advance_offseason). Returns the finished games (with their box
    scores) so the screens can store them in the save's history file before
    they're cleared from the season in progress."""
    from . import offseason, stats
    if not season_over(league):
        raise ValueError("The season isn't over yet.")
    played_share = snap_shares(league)
    from . import evaluation
    evaluation.record_tape(league, played_share, league.season)    # the tape other teams' staffs have seen
    serious = dict(league.season_injuries)
    # 1. Keep everything from this season for good.
    lines = stats.season_lines(league)
    league.career.extend(lines)
    from . import league_money
    league_money.record_buzz(league, lines)    # how the season played with the TV audience
    summary = team_season_summary(league)
    league.team_history.extend(summary)
    champ = po.champion(league)
    if champ:
        league.champions[league.season] = champ
    from . import history
    history.archive_season(league)     # the record book's best single games, before the box scores go
    finished = [{"season": league.season, "phase": phase, "game": dict(g), "box": league.boxes.get(g["id"])}
                for phase, games in (("preseason", league.preseason), ("regular", league.schedule),
                                     ("playoffs", league.playoffs))
                for g in games if g["played"]]
    # Long injuries that will keep players out of the start of next season.
    carry = carryover_injuries(league)
    # 2. A new year. Reserve lists clear and practice squads sign "future"
    #    deals: everyone is on the offseason roster until the cuts.
    transactions.end_of_season(league)
    # The season's news is written one last time and kept as it is (news.freeze_season;
    # Blake, Oct 22: old stories stop changing once a season is over).
    from . import news
    news.freeze_season(league)
    for p in league.players:
        if p.id in league.rosters:
            p.experience += 1
    league.season += 1
    # Last season's games are in the history now; the new season has none yet.
    league.schedule, league.preseason, league.playoffs, league.boxes = [], [], [], {}
    league.playoff_seeds, league.playoff_round = None, 0
    offseason.offseason_start(league, summary, rng)
    league.offseason.update({"share": {str(k): v for k, v in played_share.items()},
                             "serious": {str(k): v for k, v in serious.items()},
                             "carry": [list(c) for c in carry]})
    return finished


def advance_offseason(league, rng=None):
    """Your Next button: play the current offseason phase (offseason.offseason_next).
    After the last one, training camp opens: every player's yearly development,
    AI depth charts, captains, and the new season's schedules. Returns the
    phase key now (None once the preseason has started)."""
    from . import development, offseason
    if not in_offseason(league):
        return None
    _check_cap_hold(league)
    if offseason.offseason_next(league, rng) != "done":
        return league.offseason["phase"]
    st = league.offseason
    played_share = {int(k): v for k, v in st.get("share", {}).items()}
    serious = {int(k): v for k, v in st.get("serious", {}).items()}
    # Training camp: every player's yearly development, then AI teams reset
    # their depth charts for the new ratings (yours stays as you set it).
    development.training_camp(league, played_share, serious)
    for t in league.teams:
        if t.id != league.user_team_id:
            league.auto_depth_chart(t.id)
    for t in league.teams:
        league.vote_captains(t.id, rng=random.Random(f"captains-{league.settings.get('salt', '')}-{league.season}-{t.id}"))
    # Next season's schedules (same-place games from last season's finish).
    teams_now = {p.id: transactions.team_of(league, p.id)[0] for p in league.players if p.retired is None}
    carry = [(pid, teams_now.get(pid), kind, games) for pid, _t, kind, games in st.get("carry", ())
             if teams_now.get(pid)]
    league.offseason = None
    start_season(league, rng, carry)
    return None


def start_next_season(league, rng=None):
    """The whole offseason at once (tools; your decisions left to their
    defaults), then the new season's camp and preseason. Returns the
    finished games, as begin_offseason does."""
    finished = begin_offseason(league, rng)
    while in_offseason(league):
        advance_offseason(league, rng)
    return finished


def money_week(league, label):
    """After the week's roster moves (free_agency.py): every signing gets its
    contract, every release its cap charge, and AI teams get under the cap
    (your staff asks you if you're over). Called after league.week has
    advanced: contracts.pay_week counts the weeks already paid."""
    from . import free_agency
    if not getattr(league, "contracts", None):
        return
    free_agency.sync(league, label)
    free_agency.final_compliance(league)
    free_agency.sync(league, label)


def awards_week(league):
    """Awards and the Pro Bowl (engine/awards.py, added Oct 23): whatever is
    due after the week just played (Players of the Week and Month, the Pro
    Bowl vote, All-Pro, the Pro Bowl game in the week off, the season awards,
    the Glory Bowl MVP). Runs before the week counter moves on."""
    from . import awards
    awards.after_week(league)
    from . import hall_of_fame
    hall_of_fame.after_week(league)    # the Hall of Fame vote, once the season awards are out (Oct 25)


def end_week(league):
    """Heal injuries by a week and move to the next week (preseason ->
    regular season -> playoffs -> season complete)."""
    awards_week(league)
    cal = calendar(league)
    label = week_label(league)
    report(league).end_week(cal)
    rng = random.Random(f"moves-{league.settings.get('salt', '')}-{league.season}-{cal}")
    if in_preseason(league):
        # This week's practices, then (after the last preseason game) final cuts:
        # AI teams move long injuries to injured reserve / PUP and fill the 53.
        practice_week(league, cal)
        final = league.pre_week >= PRESEASON_WEEKS
        if final:
            # The real calendar has about two weeks from the last preseason game to
            # week 1 (final cuts in between): one more week of healing.
            report(league).end_week(cal + 0.5)
            if transactions.in_camp(league):
                # The cut from 90 to 53, waiver claims, practice squads (Oct 23).
                league.final_cuts = transactions.final_cuts(league, league.injuries, league.recovering, cal, rng)
        transactions.weekly(league, league.injuries, league.recovering, cal,
                            "Final cuts" if final else label, rng, preseason=not final)
        from . import trades           # player trades (trades.py, Oct 23): camp and cut-down day
        trades.step(league)
        league.pre_week += 1
        if league.pre_week > PRESEASON_WEEKS:
            league.stage = REGULAR_SEASON
            league.week = 1
        money_week(league, "Final cuts" if final else label)
        return
    if in_regular_season(league):
        transactions.weekly(league, league.injuries, league.recovering, cal, label, rng,
                            records=records(league) if league.week >= 3 else None)   # waivers: from week 4
        league.week += 1
        league.week_played = False    # the new week's games aren't played yet (contracts.pay_week)
        money_week(league, label)
        from . import trades           # player trades (trades.py, Oct 23): up to the deadline
        trades.step(league)
        if league.week > n_weeks(league):
            start_playoffs(league)
        return
    if in_playoffs(league) and league.playoff_round < 5:
        alive = ({tid for ids in (league.playoff_seeds or {}).values() for tid in ids}
                 - {po.loser(g) for g in league.playoffs if g["played"]})
        transactions.weekly(league, league.injuries, league.recovering, cal, label, rng,
                            teams=[t for t in league.teams if t.id in alive])
        money_week(league, label)
    if in_playoffs(league):
        r = league.playoff_round
        if r == 5:
            league.stage = SEASON_COMPLETE
            return
        league.playoff_round = r + 1
        if league.playoff_round in (2, 3, 5):
            po.make_round(league, league.playoff_round)


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def _blank_record():
    return {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "home": [0, 0, 0], "away": [0, 0, 0],
            "div": [0, 0, 0], "conf": [0, 0, 0], "results": [], "vs": {}}


def pct(w, l, t):
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def records(league):
    """Every team's record so far: wins, losses, ties, points, home/away,
    division and conference records, streak, and results vs each opponent."""
    teams = {t.id: t for t in league.teams}
    rec = {tid: _blank_record() for tid in teams}
    for g in sorted(league.schedule, key=lambda g: g["week"]):
        if not g["played"]:
            continue
        h, a, hs, as_ = g["home"], g["away"], g["home_score"], g["away_score"]
        same_div = teams[h].conference == teams[a].conference and teams[h].division == teams[a].division
        same_conf = teams[h].conference == teams[a].conference
        for tid, opp, pf, pa, where in ((h, a, hs, as_, "home"), (a, h, as_, hs, "away")):
            r = rec[tid]
            k = 0 if pf > pa else (1 if pf < pa else 2)
            r[("w", "l", "t")[k]] += 1
            r["pf"] += pf
            r["pa"] += pa
            r[where][k] += 1
            if same_div:
                r["div"][k] += 1
            if same_conf:
                r["conf"][k] += 1
            r["results"].append("WLT"[k])
            r["vs"].setdefault(opp, [0, 0, 0])[k] += 1
    for r in rec.values():
        r["pct"] = pct(r["w"], r["l"], r["t"])
        res = r["results"]
        if res:
            n = 1
            while n < len(res) and res[-n - 1] == res[-1]:
                n += 1
            r["streak"] = f"{res[-1]}{n}"
        else:
            r["streak"] = "-"
    return rec


def division_standings(league, rec=None):
    """{conference: {division: [team ids, first place first]}}, with ties
    broken by the NFL's division tiebreakers (see playoffs.py)."""
    return po.division_order(league)


def record_text(r):
    return f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
