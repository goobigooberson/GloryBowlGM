# state.py
# What the screens are currently looking at, plus opening, creating and
# saving games. Shared by every screen.
#
# Saving (Blake): manual by default. Changes stay in memory and the header
# shows "Unsaved changes" until you press Save (or Ctrl+S). With autosave
# turned on in Settings, every change is saved right away instead.

from engine import depth
from engine import saves
from engine import season
from engine.database import load_league, save_league, write_history
from engine.league import create_league

FREE_AGENTS = 0          # "team id" used in the team picker for the free agent pool


class GameState:
    league = None
    save_path = None     # the save file this game lives in
    dirty = False        # changes not yet written to the save
    team_id = 1
    unit = "All"
    position = "All positions"
    selected_id = None   # player shown in the roster report
    depth_slot = "QB"    # spot being edited on the depth chart
    depth_unit = "Offense"
    packages = {"Offense": "11 personnel", "Defense": "Base 4-3"}
    pending_league = None    # New game: league generated, team not picked yet
    on_save_status = None    # screen callback: redraw the save status in the header


state = GameState()


def _reset_view():
    state.unit = "All"
    state.position = "All positions"
    state.selected_id = None
    state.depth_slot = "QB"
    state.depth_unit = "Offense"


def _opened(league, path):
    state.league = league
    state.save_path = path
    state.dirty = False
    state.team_id = league.user_team_id or min(t.id for t in league.teams)
    _reset_view()
    saves.set_app_setting("last_opened", path.name)


def open_save(path):
    """Load a save and make it the current game."""
    league = load_league(path)
    if not league.name:
        # Saves from before save names existed: name it after the file, as Load game shows it.
        league.name = path.stem.replace("-", " ").replace("_", " ").title()
    season.bring_up_to_date(league)       # e.g. a finished regular season goes on to the playoffs
    # (no games in the offseason, nor during a new league's startup draft)
    new_schedule = not league.schedule and league.stage not in (season.OFFSEASON, season.STARTUP_DRAFT)
    if new_schedule:
        # Saves from before the season existed: make this season's schedule now.
        season.start_season(league)
    elif (not league.preseason and league.stage == season.REGULAR_SEASON and league.week == 1
          and not any(g["played"] for g in league.schedule)):
        # Saves from before the preseason existed, not started yet: add it.
        season.add_preseason(league)
        new_schedule = True
    _opened(league, path)
    if new_schedule or getattr(league, "filled_on_load", False):
        # (filled_on_load: a depth chart spot that didn't exist when it was saved got the AI's pick)
        state.dirty = True


def generate_league(year, settings):
    """New game, step 1: build a league and its whole first-season schedule
    (not saved until you pick a team). With "Startup draft" the players are
    generated and the draft order drawn; the schedule comes after the draft."""
    if settings.get("roster_method") == "startup_draft":
        from engine import draft_day
        league = draft_day.startup_league(year, settings)
        state.pending_league = league
        return league
    league = create_league(season=year)
    # update, not replace: create_league set this league's own dice ("salt"); replacing the
    # settings threw it away, so every new league got the same draws (draft session, Oct 23)
    league.settings.update(settings)
    season.start_season(league)
    state.pending_league = league
    return league


def start_new_game(league, name, user_team_id):
    """New game, step 2: you picked your team. Saves it as a new save slot
    right away (even with manual saving, so it shows up in Load game). A
    startup draft starts now: the AI picks until you're on the clock."""
    league.name = name
    league.user_team_id = user_team_id
    from engine import draft_day
    if draft_day.in_startup(league):
        draft_day.startup_begin(league)
    path = saves.new_save_path(name)
    save_league(league, path)
    state.pending_league = None
    _opened(league, path)


def close_game():
    state.league = None
    state.save_path = None
    state.dirty = False
    state.on_save_status = None


def mark_changed():
    """Call after anything that changes the league (depth chart edit, signing,
    simmed week...). Saves right away if autosave is on."""
    state.dirty = True
    if saves.load_app_settings()["autosave"]:
        save_now()
    elif state.on_save_status:
        state.on_save_status()


def save_now():
    if state.league is None or state.save_path is None:
        return
    save_league(state.league, state.save_path)
    saves.discard_recovery(state.save_path)
    state.dirty = False
    if state.on_save_status:
        state.on_save_status()


def save_copy(name):
    """Write the game as it is right now to a new save. You keep playing the
    current one (its unsaved changes, if any, stay unsaved)."""
    path = saves.new_save_path(name)
    original = state.league.name
    try:
        state.league.name = name
        save_league(state.league, path, created=None)
    finally:
        state.league.name = original
    saves.copy_history(state.save_path, path)
    return path


def start_next_season():
    """The season is over: archive it for good and set up next season.
    Past box scores go to the save's history file right away (adding to it
    is safe even if you later leave without saving: the same games are just
    written again next time)."""
    finished = season.begin_offseason(state.league)     # the offseason then goes phase by phase
    write_history(saves.history_path(state.save_path), finished)
    mark_changed()


def advance_offseason():
    """Your Next button in the offseason. Returns the phase now (None once
    training camp has opened and the preseason is set)."""
    out = season.advance_offseason(state.league)
    mark_changed()
    return out


def finish_startup():
    """The startup draft is over (your staff makes any picks left): contracts,
    practice squads, training camp and the first season's schedule."""
    from engine import draft_day
    draft_day.startup_finish(state.league)
    mark_changed()


def write_recovery():
    """The window is closing. If there are unsaved changes, keep them in a
    recovery copy so the main menu can offer them back next time."""
    if state.dirty and state.league is not None and state.save_path is not None:
        save_league(state.league, saves.recovery_path(state.save_path))


INJURY_TAGS = {"Questionable": "Q", "Doubtful": "D", "Out": "OUT", "Injured reserve": "IR",
               "Concussion protocol": "CONC", "Physically unable to perform": "PUP"}
RESERVE_NAMES = {"IR": "Injured reserve", "PUP": "Physically unable to perform",
                 "PSIR": "Practice squad injured list"}


def reserve_status(pid):
    """'Injured reserve' / 'Physically unable to perform' / 'Practice squad
    injured list' for a player on a reserve list, else None."""
    league = state.league
    r = getattr(league, "reserve", {}).get(pid) if league is not None else None
    return RESERVE_NAMES.get(r["list"]) if r else None


def injury_text(pid):
    """His injury and game-day status, e.g. 'Questionable: hamstring strain',
    'Out: high ankle sprain (about 3 more weeks)', 'Injured reserve: torn ACL
    (out for the season)'; None if healthy."""
    league = state.league
    inj = league.injuries.get(pid) if league is not None else None
    status = season.injury_status(league, pid) if inj else None
    res = reserve_status(pid)
    if res and (not inj or inj["weeks"] <= 0):
        from engine import transactions
        ready = transactions.can_return(league, league.injuries, pid)
        return f"{res}: healthy" + (" (can be activated)" if ready and res != RESERVE_NAMES["PSIR"] else
                                    " (must miss at least 4 games)" if res != RESERVE_NAMES["PSIR"] else "")
    if res:
        status = res
    if not status:
        return None
    if status in ("Questionable", "Doubtful"):
        return f"{status}: {inj['part']}"
    if status == "Concussion protocol":
        return "In the concussion protocol: can't play until he's cleared"
    n = inj["weeks"]
    left = season.games_left(league, inj["team"])
    if n >= left:
        when = "out for the season"
    else:
        when = f"about {n} more week{'s' if n != 1 else ''}"
    return f"{status}: {inj['part']} ({when})"


def injury_code(pid):
    """'Q', 'D', 'OUT', 'IR' or '' for the roster and depth chart tags."""
    league = state.league
    status = season.injury_status(league, pid) if league is not None else None
    res = reserve_status(pid)
    if res:
        return "PUP" if res == RESERVE_NAMES["PUP"] else "IR"
    return INJURY_TAGS.get(status, "")


def injury_tag(pid):
    """A small colored status tag (HTML) for an injured player, or ''."""
    code = injury_code(pid)
    if not code:
        return ""
    return f' <span class="inj-tag inj-{code.lower()}" title="{injury_text(pid)}">{code}</span>'


def is_user_team(team_id):
    return state.league is not None and team_id == state.league.user_team_id


def team_starter_ids(team_id):
    """Starters according to the team's depth chart."""
    if team_id == FREE_AGENTS or state.league is None:
        return set()
    return depth.starter_ids(state.league.depth_charts.get(team_id, {}))
