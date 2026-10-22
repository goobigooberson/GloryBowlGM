# saves.py
# Save slots: every game you start is its own file in the "saves" folder,
# so you can keep several leagues going at once. This file lists them,
# names new ones, copies and deletes them, and keeps the game's own settings
# (saves/settings.json), such as which save you played last.
#
# Saving is manual only (Blake, Oct 24): closing the window with unsaved
# changes throws them away. Until then the game kept a "recovery copy" next to
# the save (e.g. bears-2026.recovery.db); the functions below still clean up
# any that are left (deleting a save deletes its copy; saving discards it).

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import sys

from .database import read_save_info, rename_save

def _documents_folder():
    """The player's Documents folder (wherever Windows keeps it, e.g. in OneDrive)."""
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:   # 5 = My Documents
        return Path(buf.value)
    return Path.home() / "Documents"


# In the packaged game (the .exe), saves go in Documents\Glory Bowl GM\saves,
# so they're kept even if the .exe was run straight from inside its zip.
if getattr(sys, "frozen", False):
    SAVES_DIR = _documents_folder() / "Glory Bowl GM" / "saves"
    _OLD_DIR = _documents_folder() / "Front Office Football" / "saves"   # before the rename (Oct 22)
    if _OLD_DIR.exists() and not SAVES_DIR.exists():
        SAVES_DIR = _OLD_DIR
else:
    SAVES_DIR = Path(__file__).resolve().parent.parent / "saves"
SETTINGS_FILE = SAVES_DIR / "settings.json"
RECOVERY = ".recovery.db"
HISTORY = ".history.db"      # past seasons' box scores, beside each save (database.write_history)

DEFAULT_APP_SETTINGS = {
    "last_opened": None,   # file name of the save you played last (for Continue)
}                          # (no autosave: Blake, Oct 24, saving is manual only)


# ---- Game settings (not part of any one save) -----------------------------

def load_app_settings():
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULT_APP_SETTINGS, **data}


def save_app_settings(settings):
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def set_app_setting(key, value):
    s = load_app_settings()
    s[key] = value
    save_app_settings(s)


# ---- The list of saves ------------------------------------------------------

def _is_save_file(path):
    return path.suffix == ".db" and not path.name.endswith(RECOVERY) and not path.name.endswith(HISTORY)


def history_path(path):
    path = Path(path)
    return path.with_name(path.stem + HISTORY)


def copy_history(src, dst):
    """Give a copied save its own copy of the history file."""
    if history_path(src).exists():
        shutil.copyfile(history_path(src), history_path(dst))


def list_saves():
    """Every save in the saves folder, most recently saved first. Each is a
    dict: path, name, season, team, settings, created, saved_at, has_recovery,
    and problem (set if the file can't be read, e.g. made by a much older
    version of the game)."""
    out = []
    if not SAVES_DIR.exists():
        return out
    for path in SAVES_DIR.glob("*.db"):
        if not _is_save_file(path):
            continue
        try:
            info = read_save_info(path)
            info["problem"] = None
        except Exception:
            info = {"name": "", "season": None, "team": None, "settings": {},
                    "created": None, "saved_at": None,
                    "problem": "This save can't be read (it may be from an older version of the game)."}
        info["path"] = path
        if not info["name"]:
            info["name"] = path.stem.replace("-", " ").replace("_", " ").title()
        if not info.get("saved_at"):
            # Saves from before save times were stored: use the file's own date.
            info["saved_at"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        info["has_recovery"] = recovery_path(path).exists()
        out.append(info)
    out.sort(key=lambda s: s["saved_at"] or "", reverse=True)
    return out


def last_played():
    """The save to offer under Continue: the last one opened, else the most
    recently saved one. None if there are no saves."""
    saves = [s for s in list_saves() if not s["problem"]]
    if not saves:
        return None
    last = load_app_settings().get("last_opened")
    for s in saves:
        if s["path"].name == last:
            return s
    return saves[0]


def name_taken(name, except_path=None):
    return any(s["name"].strip().lower() == name.strip().lower() and s["path"] != except_path
               for s in list_saves())


def new_save_path(name):
    """A new, unused file name for a save called `name`."""
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "league"
    slug = slug[:50]
    path = SAVES_DIR / f"{slug}.db"
    n = 2
    while path.exists() or recovery_path(path).exists() or history_path(path).exists():
        path = SAVES_DIR / f"{slug}-{n}.db"
        n += 1
    return path


def rename(path, new_name):
    rename_save(path, new_name)


def copy_save(path, new_name):
    """Make a copy of a save under a new name (e.g. a backup before a big
    decision). Returns the copy's path."""
    new_path = new_save_path(new_name)
    shutil.copyfile(path, new_path)
    copy_history(path, new_path)
    rename_save(new_path, new_name)
    return new_path


def delete_save(path):
    """Delete a save file (with its recovery copy and history file). Can't be undone."""
    path = Path(path)
    for p in (path, recovery_path(path), history_path(path)):
        if p.exists():
            p.unlink()
    if load_app_settings().get("last_opened") == path.name:
        set_app_setting("last_opened", None)


# ---- Recovery copies --------------------------------------------------------

def recovery_path(path):
    path = Path(path)
    return path.with_name(path.stem + RECOVERY)


def discard_recovery(path):
    rp = recovery_path(path)
    if rp.exists():
        rp.unlink()


def restore_recovery(path):
    """Replace the save with its recovery copy (keeps the save's name)."""
    rp = recovery_path(path)
    shutil.copyfile(rp, path)
    rp.unlink()
