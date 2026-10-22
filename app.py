# app.py
# Starts the game. Run it from the terminal (in the project folder) with:
#     python app.py
# The game opens in its own window at the main menu. To quit, use Quit game
# on the main menu or close the window.
# (If the window add-on "pywebview" isn't installed, or you run
# "python app.py --browser", the game opens in your web browser instead.)

import multiprocessing
import sys

# The packaged game (the .exe built by tools/build_exe.ps1) has no console, so
# give its log output somewhere harmless to go.
if getattr(sys, "frozen", False):
    import io
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

from fastapi.responses import RedirectResponse
from nicegui import app, native, ui

from screens import main_page, menu_page, new_game_page, offseason_page, player_card_page
from screens.state import state

from engine import saves

# Testing only: "--saves-dir=<folder>" uses another saves folder, so tests
# never touch your real saves.
for arg in sys.argv:
    if arg.startswith("--saves-dir="):
        from pathlib import Path
        saves.SAVES_DIR = Path(arg.split("=", 1)[1])
        saves.SETTINGS_FILE = saves.SAVES_DIR / "settings.json"

def webview2_installed():
    """True if Microsoft's WebView2 (what draws the game window) is on this PC.
    It's in Windows 11 and up-to-date Windows 10, but some PCs lack it."""
    import winreg
    client = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    places = [(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + client),
              (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + client),
              (winreg.HKEY_CURRENT_USER, "Software\\" + client)]
    for root, path in places:
        try:
            with winreg.OpenKey(root, path) as key:
                version = winreg.QueryValueEx(key, "pv")[0]
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            pass
    return False


try:
    import webview  # noqa: F401  (the pywebview add-on that draws the window)
    HAS_WINDOW = "--browser" not in sys.argv
except ImportError:
    HAS_WINDOW = False

# The packaged game on a PC without WebView2: open in the web browser instead.
if HAS_WINDOW and getattr(sys, "frozen", False) and not webview2_installed():
    HAS_WINDOW = False


@ui.page("/")
def main_menu():
    if state.league is not None:
        # A game is open (e.g. the page was refreshed): go back to it.
        return RedirectResponse("/game")
    menu_page.build_main_menu()


@ui.page("/new")
def new_game():
    new_game_page.build_new_game_page()


@ui.page("/load")
def load_game():
    menu_page.build_load_page()


@ui.page("/settings")
def settings():
    menu_page.build_settings_page()


@ui.page("/game")
def game():
    if state.league is None:
        return RedirectResponse("/")
    main_page.build_page()


@ui.page("/offseason")
def offseason_report():
    if state.league is None:
        return RedirectResponse("/")
    offseason_page.build_offseason_page()


@ui.page("/player/{pid}")
def player_card(pid: int):
    if state.league is None:
        return RedirectResponse("/")
    player_card_page.build_player_card(pid)


# Closing the window with unsaved changes throws them away: the game only saves when
# you press Save (Blake, Oct 24: "if i close the game without saving i dont want it to
# still save cause then whats the point of saving"). Until then a recovery copy was kept.


if __name__ in {"__main__", "__mp_main__"}:
    multiprocessing.freeze_support()  # needed for the game window in the packaged .exe
    if HAS_WINDOW:
        # find_open_port: use any free port, so another program on the PC can't block the game.
        port = native.find_open_port()
        if getattr(sys, "frozen", False) and multiprocessing.current_process().name == "MainProcess":
            # Packaged game: if no game screen has connected in 30 seconds (the
            # window failed on a friend's PC), open the game in the web browser
            # instead. (A window can appear but stay blank, so this waits for the
            # screen itself, not the window.)
            import threading
            import webbrowser
            screen_connected = threading.Event()
            app.on_connect(lambda: screen_connected.set())

            def browser_if_no_window():
                if not screen_connected.wait(30):
                    webbrowser.open(f"http://127.0.0.1:{port}")

            threading.Thread(target=browser_if_no_window, daemon=True).start()
        ui.run(title="Glory Bowl GM", native=True, window_size=(1600, 950),
               reload=False, port=port)
    else:
        print("Opening in your browser.")
        if "--browser" not in sys.argv:
            print("For a game window instead, run:")
            print("    python -m pip install pywebview")
        # --no-show: don't open a browser tab (used for testing in Claude's browser pane)
        # --port=<n>: another port, so two test copies can run side by side.
        port = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--port=")), 8085)
        if getattr(sys, "frozen", False) and not any(a.startswith("--port=") for a in sys.argv):
            port = native.find_open_port()  # packaged game: any free port
        ui.run(title="Glory Bowl GM", favicon="🏈", reload=False,
               show="--no-show" not in sys.argv, port=port)
