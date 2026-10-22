# menu_page.py
# The screens around a game: the main menu (Continue, New game, Load game,
# Settings, Quit), the Load game list (load, rename, copy, delete saves) and
# Settings. The New game screen has its own file (new_game_page.py).

from datetime import datetime

from nicegui import app, ui

from engine import saves
from engine.league import ROSTER_METHODS
from . import theme
from .state import open_save


def when(iso):
    """'Oct 19, 2026, 10:52 PM' (or 'Today, 10:52 PM')."""
    if not iso:
        return "unknown"
    t = datetime.fromisoformat(iso)
    clock = t.strftime("%I:%M %p").lstrip("0")
    if t.date() == datetime.now().date():
        return f"Today, {clock}"
    return f"{t:%b} {t.day}, {t.year}, {clock}"


def save_details(s):
    """One line about a save: team, season, games, when saved."""
    parts = []
    if s.get("team"):
        parts.append(s["team"])
    if s.get("season"):
        if s.get("stage") == "regular_season_done":
            parts.append(f"{s['season']} regular season complete")
        elif s.get("stage") == "playoffs":
            parts.append(f"{s['season']} playoffs")
        elif s.get("stage") == "season_complete":
            parts.append(f"{s['season']} season complete")
        elif s.get("stage") == "startup_draft":
            parts.append(f"{s['season']} startup draft")
        elif s.get("stage") == "offseason":
            parts.append(f"{s['season']} offseason")
        elif s.get("stage") == "preseason":
            pw = s.get("pre_week", 1)
            parts.append(f"{s['season']} preseason, " + ("Hall of Fame Game week" if pw == 1 else f"week {pw - 1}"))
        else:
            parts.append(f"{s['season']} season, week {s.get('week', 1)}")
    games = s.get("settings", {}).get("season_games")
    if games:
        parts.append(f"{games}-game season")
    parts.append(f"saved {when(s.get('saved_at'))}")
    return "   ·   ".join(parts)


def _page_start(title, subtitle=None, back=None):
    ui.add_head_html(theme.HEAD_HTML)
    ui.query("body").style(f"background:{theme.CHALK}")
    with ui.element("div").classes("field-band w-full px-10 pt-8 pb-8"):
        with ui.row().classes("w-full items-end justify-between"):
            with ui.column().classes("gap-1"):
                ui.label(title).classes("menu-title")
                if subtitle:
                    ui.label(subtitle).classes("menu-sub")
            if back:
                ui.button(back[0], on_click=lambda: ui.navigate.to(back[1])) \
                    .props("outline color=white no-caps")


def _open_and_play(path):
    try:
        open_save(path)
    except Exception:
        ui.notify("That save couldn't be opened. It may be from an older version of the game.",
                  type="negative")
        return
    ui.navigate.to("/game")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def build_main_menu():
    _page_start("Front Office Football", "You're the general manager. Build a winner.")
    all_saves = saves.list_saves()
    last = saves.last_played()

    with ui.column().classes("px-10 py-8 gap-4").style("width: 640px; max-width: 100%"):
        with ui.column().classes("menu-panel p-5 gap-3 w-full"):
            if last:
                with ui.button(on_click=lambda: _open_and_play(last["path"])) \
                        .props("no-caps unelevated color=green-10 size=lg").classes("menu-button"):
                    with ui.column().classes("gap-0 items-start"):
                        ui.label(f"Continue: {last['name']}").classes("condensed text-2xl")
                        ui.label(save_details(last)).classes("text-sm opacity-80")
            ui.button("New game", on_click=lambda: ui.navigate.to("/new")) \
                .props(f"no-caps size=lg {'outline color=green-10' if last else 'unelevated color=green-10'}") \
                .classes("menu-button")
            ui.button(f"Load game ({len(all_saves)} saved)" if all_saves else "Load game",
                      on_click=lambda: ui.navigate.to("/load")) \
                .props(f"no-caps size=lg outline color=green-10 {'' if all_saves else 'disable'}") \
                .classes("menu-button")
            ui.button("Settings", on_click=lambda: ui.navigate.to("/settings")) \
                .props("no-caps size=lg outline color=green-10").classes("menu-button")
            ui.button("Quit game", on_click=app.shutdown) \
                .props("no-caps size=lg flat color=grey-8").classes("menu-button")

        if not all_saves:
            ui.label("No saved games yet. Start with New game.").classes("legend")


# ---------------------------------------------------------------------------
# Load game
# ---------------------------------------------------------------------------

def build_load_page():
    _page_start("Load game", "Your saved games, most recent first.", back=("Main menu", "/"))
    selected = {"save": None}

    @ui.refreshable
    def save_list():
        all_saves = saves.list_saves()
        if not all_saves:
            ui.label("No saved games yet.").classes("legend")
            ui.button("New game", on_click=lambda: ui.navigate.to("/new")).props("no-caps color=green-10")
            return
        with ui.column().classes("menu-panel w-full gap-0"):
            for s in all_saves:
                with ui.element("div").classes("save-row"):
                    ui.label(s.get("team_abbrev") or "?").classes("save-abbrev")
                    with ui.column().classes("gap-0"):
                        ui.label(s["name"]).classes("save-name")
                        if s["problem"]:
                            ui.label(s["problem"]).classes("problem")
                        else:
                            method = ROSTER_METHODS.get(s["settings"].get("roster_method"), "")
                            ui.label(save_details(s)).classes("legend")
                            ui.label(f"{method}   ·   started {when(s.get('created'))}"
                                     if s.get("created") else method).classes("legend")
                    with ui.row().classes("gap-1 no-wrap"):
                        if not s["problem"]:
                            ui.button("Load", on_click=lambda s=s: _open_and_play(s["path"])) \
                                .props("no-caps unelevated color=green-10")
                            ui.button("Rename", on_click=lambda s=s: ask("rename", s)).props("no-caps flat color=grey-9")
                            ui.button("Make a copy", on_click=lambda s=s: ask("copy", s)).props("no-caps flat color=grey-9")
                        ui.button("Delete", on_click=lambda s=s: ask("delete", s)).props("no-caps flat color=red-9")

    with ui.column().classes("px-10 py-8 gap-4").style("width: 1000px; max-width: 100%"):
        save_list()

    # One small dialog for rename / copy / delete.
    with ui.dialog() as dialog, ui.card().classes("p-6").style("min-width:440px"):
        title = ui.label().classes("condensed text-2xl")
        message = ui.label().classes("legend")
        name_input = ui.input("Name").props("outlined dense").classes("w-full mt-2")
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
            ok = ui.button("OK", on_click=lambda: confirm()).props("no-caps color=green-10")

    def ask(action, s):
        selected["save"], selected["action"] = s, action
        name_input.visible = action in ("rename", "copy")
        if action == "rename":
            title.text, message.text, ok.text = "Rename save", f'Current name: "{s["name"]}"', "Rename"
            name_input.value = s["name"]
            ok.props("color=green-10")
        elif action == "copy":
            title.text, ok.text = "Make a copy", "Make copy"
            message.text = "A separate save that starts exactly where this one is now."
            name_input.value = f"{s['name']} (copy)"
            ok.props("color=green-10")
        else:
            title.text, ok.text = "Delete this save?", "Delete forever"
            message.text = f'"{s["name"]}" will be deleted. This can\'t be undone.'
            ok.props("color=red-9")
        dialog.open()

    def confirm():
        s, action = selected["save"], selected["action"]
        name = (name_input.value or "").strip()
        if action in ("rename", "copy"):
            if not name:
                ui.notify("Type a name first.")
                return
            if saves.name_taken(name, except_path=s["path"] if action == "rename" else None):
                ui.notify("There's already a save with that name. Pick another.")
                return
            if action == "rename":
                saves.rename(s["path"], name)
                ui.notify(f'Renamed to "{name}".', type="positive")
            else:
                saves.copy_save(s["path"], name)
                ui.notify(f'Made a copy called "{name}".', type="positive")
        else:
            saves.delete_save(s["path"])
            ui.notify(f'Deleted "{s["name"]}".')
        dialog.close()
        save_list.refresh()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def build_settings_page():
    _page_start("Settings", "These apply to every save.", back=("Main menu", "/"))
    with ui.column().classes("px-10 py-8 gap-4").style("width: 760px; max-width: 100%"):
        with ui.column().classes("menu-panel p-6 gap-1 w-full"):
            ui.label("Saving").classes("menu-heading")
            ui.label("The game saves only when you press Save (or Ctrl+S). Changes stay unsaved until "
                     "then: go back to the main menu or close the window without saving and they're "
                     "gone, and the save is as you last left it. Use \"Save a copy\" for a backup to "
                     "go back to.").classes("legend")
