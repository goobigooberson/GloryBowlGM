# menu_page.py
# The screens around a game: the main menu (Continue, New game, Load game,
# Settings, Quit), the Load game list (load, rename, copy, delete saves) and
# Settings. The New game screen has its own file (new_game_page.py).

from datetime import datetime
from html import escape

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

# The title screen (Oct 22; Blake: "spruce up the rest of the ui"): a football field at
# night behind the game's name, big menu buttons, and your latest saves as cards.
TITLE_CSS = f"""
<style>
  .title-screen {{ min-height: 100vh; width: 100%; color: white; position: relative; overflow: hidden;
    background-color: #173A29;
    background-image:
      linear-gradient(180deg, rgba(5, 18, 11, .55) 0%, rgba(5, 18, 11, .15) 45%, rgba(5, 18, 11, .7) 100%),
      repeating-linear-gradient(90deg, rgba(255,255,255,.16) 0 3px, transparent 3px 10vw),
      repeating-linear-gradient(90deg, rgba(0,0,0,.07) 0 5vw, transparent 5vw 10vw); }}
  .title-screen .yard {{ position: absolute; bottom: 4vh; font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700; font-size: 9vh; color: rgba(255,255,255,.10); letter-spacing: .05em; user-select: none; }}
  .title-wrap {{ position: relative; z-index: 1; display: flex; gap: 48px; flex-wrap: wrap; align-items: flex-start;
    padding: 9vh 7vw 6vh; }}
  .title-kicker {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 20px;
    letter-spacing: .32em; color: {theme.FLAG}; }}
  .title-name {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 96px; line-height: .9;
    letter-spacing: .01em; text-shadow: 0 4px 24px rgba(0,0,0,.35); }}
  .title-tag {{ font-size: 17px; opacity: .85; margin-top: 10px; }}
  .title-menu {{ display: flex; flex-direction: column; gap: 10px; width: 400px; max-width: 86vw; margin-top: 34px; }}
  .title-menu .q-btn {{ justify-content: flex-start; min-height: 54px; border-radius: 4px; padding: 0 20px;
    font-family: 'Barlow Condensed', sans-serif; font-size: 23px; font-weight: 600; text-align: left;
    background: rgba(8, 24, 15, .55); color: white; box-shadow: inset 0 0 0 1px rgba(255,255,255,.22);
    backdrop-filter: blur(2px); }}
  .title-menu .q-btn .q-btn__content {{ justify-content: flex-start; text-align: left; }}
  .title-menu .q-btn:hover {{ background: rgba(255,255,255,.12); }}
  .title-menu .q-btn.go {{ background: {theme.FLAG}; color: {theme.INK}; box-shadow: none; min-height: 72px; }}
  .title-menu .q-btn.go:hover {{ background: #FFD43B; }}
  .title-menu .q-btn.quiet {{ background: transparent; box-shadow: none; font-size: 19px; min-height: 40px;
    opacity: .75; }}
  .title-menu .go .sub {{ display: block; font-family: 'Barlow', sans-serif; font-size: 13.5px; font-weight: 500;
    opacity: .8; line-height: 1.2; }}
  .title-saves {{ flex: 1 1 380px; max-width: 560px; margin-top: 8px; }}
  .title-saves h3 {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 18px;
    letter-spacing: .14em; text-transform: uppercase; opacity: .8; margin: 0 0 10px; }}
  .save-card {{ display: flex; align-items: center; gap: 16px; padding: 12px 16px; margin-bottom: 8px; cursor: pointer;
    background: rgba(255,255,255,.94); color: {theme.INK}; border-radius: 4px; border-left: 5px solid var(--turf);
    box-shadow: 0 6px 18px rgba(0,0,0,.25); }}
  .save-card:hover {{ border-left-color: {theme.FLAG}; background: white; }}
  .save-card .ab {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 34px; color: var(--turf);
    width: 64px; text-align: center; line-height: 1; }}
  .save-card .nm {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 21px; line-height: 1.1; }}
  .save-card .dt {{ font-size: 12.5px; color: {theme.INK_SOFT}; line-height: 1.3; }}
  .save-card .bad {{ font-size: 12.5px; color: #A3321F; }}
</style>
"""


def build_main_menu():
    ui.add_head_html(theme.HEAD_HTML)
    ui.add_head_html(TITLE_CSS)
    ui.query("body").style("background:#173A29")
    all_saves = saves.list_saves()
    last = saves.last_played()

    with ui.element("div").classes("title-screen"):
        for i, yard in enumerate(("10", "20", "30", "40", "50", "40", "30", "20", "10")):
            ui.html(f'<span class="yard" style="left:calc({(i + 1) * 10}vw - 3.2vh)">{yard}</span>',
                    sanitize=False)
        with ui.element("div").classes("title-wrap"):
            with ui.column().classes("gap-0"):
                ui.label("GLORY BOWL").classes("title-kicker")
                ui.label("GM").classes("title-name")
                ui.label("You're the general manager. Build a winner.").classes("title-tag")
                with ui.element("div").classes("title-menu"):
                    if last:
                        with ui.button(on_click=lambda: _open_and_play(last["path"]), color=None) \
                                .props("no-caps unelevated").classes("go"):
                            ui.html(f'<span>Continue: {escape(last["name"])}<span class="sub">'
                                    f'{escape(save_details(last))}</span></span>', sanitize=False)
                    ui.button("New game", on_click=lambda: ui.navigate.to("/new"), color=None) \
                        .props("no-caps unelevated").classes("" if last else "go")
                    ui.button(f"Load game ({len(all_saves)} saved)" if all_saves else "Load game",
                              on_click=lambda: ui.navigate.to("/load"), color=None) \
                        .props(f"no-caps unelevated {'' if all_saves else 'disable'}")
                    ui.button("Settings", on_click=lambda: ui.navigate.to("/settings"), color=None) \
                        .props("no-caps unelevated")
                    ui.button("Quit game", on_click=app.shutdown, color=None) \
                        .props("no-caps unelevated").classes("quiet")
                if not all_saves:
                    ui.label("No saved games yet. Start with New game.").classes("title-tag")
            recent = [s for s in all_saves if not last or s["path"] != last["path"]][:4]
            if recent:
                with ui.element("div").classes("title-saves"):
                    ui.html("<h3>Your other saves</h3>", sanitize=False)
                    for s in recent:
                        card = ui.element("div").classes("save-card") \
                            .tooltip("Click to load this game" if not s["problem"] else s["problem"])
                        if not s["problem"]:
                            card.on("click", lambda s=s: _open_and_play(s["path"]))
                        with card:
                            ui.html(f'<span class="ab">{escape(s.get("team_abbrev") or "?")}</span>'
                                    f'<span><div class="nm">{escape(s["name"])}</div>'
                                    + (f'<div class="bad">{escape(s["problem"])}</div>' if s["problem"] else
                                       f'<div class="dt">{escape(save_details(s))}</div>')
                                    + '</span>', sanitize=False).style("display:flex;align-items:center;gap:16px")
                    if len(all_saves) > len(recent) + (1 if last else 0):
                        ui.button("All saves (Load game)", on_click=lambda: ui.navigate.to("/load")) \
                            .props("flat no-caps color=white")


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
        with ui.column().classes("menu-panel p-6 gap-1 w-full"):
            ui.label("Windows").classes("menu-heading")
            popouts = ui.switch("Open player cards, teams and game summaries in their own windows",
                                value=saves.load_app_settings().get("popout_windows", True),
                                on_change=lambda e: saves.set_app_setting("popout_windows", bool(e.value)))
            popouts.props("color=green-10")
            ui.label("Like Front Office Football: each one is a window of its own that you can drag "
                     "anywhere, even onto another monitor, and keep several open; they update as "
                     "the season goes on. Off: they open inside the game window instead. (In the "
                     "web browser they always open inside the page.)").classes("legend")
