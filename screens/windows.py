# windows.py
# Pop-out windows (Blake, Oct 22: "player cards, team windows and game summaries as real
# windows I can drag anywhere, even onto my second monitor, with several open at once";
# that's how Front Office Football did it).
#
# In the game window (not browser mode) a player card, a team window or a game summary
# opens as its own Windows window: drag it anywhere, onto another monitor, resize it,
# keep several open. Each one is a page of its own (/w/player/12, /w/team/3, /w/game/57)
# drawn by the same code as the in-window pop-ups (popups.py), and every open one is
# redrawn when the league changes (a simmed week, a signing...: state.mark_changed), so
# none goes out of date. Links inside one open another window. In browser mode (and if
# the game window can't open more windows) the in-window pop-ups are used as before.
#
# How it works: the game window is drawn by a second process (NiceGUI's native mode,
# pywebview). app.py calls install_in_window_process() in that process, which gives the
# game window a command, fof_open_window, that opens another window; pop_out() here sends
# that command down the same queue NiceGUI uses for its own window commands.
# pop_out() is what popups.open_player / open_team / open_game try first.

import multiprocessing

from nicegui import app, context, ui

from .state import state

# Window sizes (logical pixels; FOF8-like compact windows so a few fit beside the game).
SIZES = {"player": (1240, 860), "team": (1300, 900), "game": (940, 900)}
TITLES = {"player": "Player card", "team": "Team", "game": "Game summary"}
CASCADE = 30                      # each new window opens this far down and right of the last

_open_pages = {}                  # client id -> redraw function, for every open pop-out window


# ---------------------------------------------------------------------------
# The game's side
# ---------------------------------------------------------------------------

def enabled():
    """True when pop-ups should open as their own windows (the game window is up)."""
    if not getattr(app, "native", None):
        return False
    try:
        from nicegui.native import native
    except ImportError:
        return False
    if native.method_queue is None:
        return False
    from engine import saves
    return saves.load_app_settings().get("popout_windows", True)


def pop_out(kind, ident):
    """Open a pop-out window for a player, team or game. False if it can't (then the
    caller opens an in-window pop-up instead)."""
    if kind not in SIZES or not enabled():
        return False
    try:
        client = context.client
    except RuntimeError:          # not from a screen (a background task): no page is drawing
        client = None
    if client is not None and getattr(client, "fof_window_drawing", False):
        return False              # this window's own page is drawing itself
    from nicegui.native import native
    width, height = SIZES[kind]
    try:
        native.method_queue.put(("fof_open_window", (f"/w/{kind}/{ident}", _title(kind, ident), width, height), {}))
    except Exception:
        return False
    return True


def _title(kind, ident):
    """The window's title bar (and taskbar) text: who or what it is, so several open
    windows are easy to tell apart."""
    league = state.league
    try:
        if kind == "player":
            p = league.player(ident)
            return f"{p.name} ({p.position}) · Player card"
        if kind == "team":
            return f"{league.team(ident).name} · Team"
        if kind == "game":
            from engine import season as S
            g = next(x for x in S.all_games(league) if x["id"] == ident)
            home, away = league.team(g["home"]), league.team(g["away"])
            return f"{away.abbrev} {g['away_score']}, {home.abbrev} {g['home_score']} · Game summary"
    except Exception:
        pass
    return TITLES[kind]


def close_all():
    """Close every pop-out window (another league loaded, back to the main menu)."""
    _open_pages.clear()
    if not enabled():
        return
    from nicegui.native import native
    try:
        native.method_queue.put(("fof_close_windows", (), {}))
    except Exception:
        pass


def refresh_all():
    """Redraw every open pop-out window (the league changed)."""
    for cid, redraw in list(_open_pages.items()):
        try:
            redraw()
        except Exception:
            _open_pages.pop(cid, None)


@ui.page("/w/{kind}/{ident}")
def popout_page(kind: str, ident: int):
    """One pop-out window's page."""
    from . import nav, popups, theme
    from .main_page import HOME_CSS
    ui.add_head_html(theme.HEAD_HTML)
    ui.add_head_html(nav.CSS)
    ui.add_head_html(HOME_CSS)
    ui.add_head_html("<style>.fof-window .fof-popup-body { overflow: visible; }"
                     " .fof-window .fof-popup-head { cursor: default; }</style>")
    popups.install()              # links in it open more windows
    ui.query("body").style(f"background:{theme.CHALK}")
    client = context.client

    @ui.refreshable
    def content():
        if state.league is None:
            ui.label("No game is open.").classes("p-8")
            return
        page = _WindowTarget()
        client.fof_window = page
        client.fof_window_drawing = True
        try:
            if kind == "player":
                popups.open_player(ident)
            elif kind == "team":
                popups.open_team(ident)
            elif kind == "game":
                popups.open_game(ident)
        finally:
            client.fof_window_drawing = False
            client.fof_window = None
    content()
    _open_pages[client.id] = content.refresh
    client.on_disconnect(lambda: _open_pages.pop(client.id, None))


class _WindowTarget:
    """What popups._popup draws into on a pop-out window's page (instead of a dialog):
    the window's own header band and body."""

    fof_window = True

    def __init__(self):
        with ui.element("div").classes("fof-popup fof-window w-full").style("min-height:100vh"):
            self.head = ui.element("div").classes("field-band fof-popup-head w-full px-6 pt-3 pb-4")
            self.body = ui.element("div").classes("fof-popup-body w-full")
        self.dialog = self

    def close(self):
        """The window closes with its own title bar's X."""
        return None


# ---------------------------------------------------------------------------
# The game window's process (pywebview)
# ---------------------------------------------------------------------------

def install_in_window_process():
    """In the process that draws the game window: give the game window the commands
    to open and close pop-out windows (pop_out() and close_all() send them)."""
    if multiprocessing.current_process().name == "MainProcess":
        return
    try:
        import webview
    except ImportError:
        return
    original = webview.create_window
    popouts = []

    def create_window(*args, **kwargs):
        window = original(*args, **kwargs)
        if window is None or getattr(create_window, "main", None) is not None:
            return window
        create_window.main = window
        base = kwargs.get("url") or (args[1] if len(args) > 1 else "")
        base = base.rstrip("/")

        def fof_open_window(path, title, width, height):
            alive = [w for w in popouts if w in webview.windows]
            popouts[:] = alive
            step = CASCADE * (len(alive) % 10)
            try:
                x0, y0 = int(window.x or 0), int(window.y or 0)
            except Exception:
                x0 = y0 = 0
            w = original(title, base + path, width=width, height=height,
                         x=x0 + 120 + step, y=y0 + 90 + step, min_size=(560, 420),
                         background_color="#ECEFEA", text_select=True)
            popouts.append(w)

            def owned():
                # Owned by the game window (Windows' "owner"): it stays in front of the
                # game, like FOF8's windows, instead of vanishing behind it when you click
                # the game; it can still go anywhere, any monitor, and isn't on top of
                # other programs.
                try:
                    import ctypes
                    from ctypes import wintypes
                    set_long = ctypes.windll.user32.SetWindowLongPtrW
                    set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
                    set_long.restype = ctypes.c_void_p
                    hw = int(w.native.Handle.ToInt64())
                    owner = int(window.native.Handle.ToInt64())
                    set_long(hw, -8, owner)          # GWLP_HWNDPARENT: the owner window
                except Exception:
                    pass
            w.events.shown += owned

        def fof_close_windows():
            for w in list(popouts):
                try:
                    w.destroy()
                except Exception:
                    pass
            popouts.clear()

        window.fof_open_window = fof_open_window
        window.fof_close_windows = fof_close_windows
        window.events.closed += fof_close_windows     # closing the game closes its pop-outs too
        return window

    create_window.main = None
    webview.create_window = create_window
