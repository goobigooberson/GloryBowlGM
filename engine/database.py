# database.py
# Saves a league to a file and loads it back, using SQLite (a database that
# lives in a single file and comes built into Python).
#
# Each save is one file in the "saves" folder, e.g. saves/bears-2026.db
# (see saves.py for the list of saves). Simple values get their own columns,
# so later screens can search and sort them quickly. Groups of values (a
# player's skill ratings, combine results) are stored together as text in a
# format called JSON.

import json
import os
import random
import sqlite3
from datetime import date, datetime
from pathlib import Path

from . import depth
from .league import League, DEFAULT_SETTINGS
from . import player as player_module
from .player import Player, fill_new_ratings
from .teams import Team

SCHEMA = """
CREATE TABLE league_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE teams (
    id         INTEGER PRIMARY KEY,
    city       TEXT, nickname TEXT, abbrev TEXT,
    conference TEXT, division TEXT
);
CREATE TABLE players (
    id             INTEGER PRIMARY KEY,
    team_id        INTEGER,          -- empty = free agent
    first_name     TEXT, last_name TEXT, position TEXT,
    birth_date     TEXT, experience INTEGER,
    height         INTEGER, weight INTEGER,
    college        TEXT, hometown TEXT,
    draft_year     INTEGER, draft_round INTEGER,   -- round 0 = undrafted
    intel_test     INTEGER, position_drill INTEGER,
    loyalty        INTEGER, wants_winner INTEGER, leadership INTEGER,
    volatility     INTEGER, popularity INTEGER,
    consistency    INTEGER, generational INTEGER,
    adaptability   INTEGER, side TEXT,
    durability     INTEGER,          -- hidden (added Oct 19; older files get it on load)
    retired        INTEGER,          -- year he retired (his last season); empty while playing
    dev            TEXT,             -- JSON: development state (hidden; see development.py)
    learned        TEXT,             -- JSON: {position or "side": 0-100}
    skills         TEXT,             -- JSON: {skill: [current, potential]}
    athletic       TEXT,             -- JSON: {trait: value}
    combine        TEXT              -- JSON: {drill: result or null}
);
CREATE TABLE captains (
    team_id   INTEGER,
    unit      TEXT,                  -- Offense or Defense
    player_id INTEGER
);
CREATE TABLE depth_charts (
    team_id   INTEGER,
    slot      TEXT,                  -- spot on the field, e.g. LT (see depth.py)
    rank      INTEGER,               -- 0 = starter, 1 = first backup...
    player_id INTEGER
);
CREATE TABLE schedule (
    id         INTEGER PRIMARY KEY,
    week       INTEGER, home INTEGER, away INTEGER, kind TEXT,
    played     INTEGER, home_score INTEGER, away_score INTEGER, overtime INTEGER,
    box        TEXT                  -- JSON box score once played
);
CREATE TABLE preseason (
    id         INTEGER PRIMARY KEY,
    week       INTEGER, home INTEGER, away INTEGER, kind TEXT, neutral INTEGER,
    played     INTEGER, home_score INTEGER, away_score INTEGER, overtime INTEGER,
    box        TEXT
);
CREATE TABLE playoffs (
    id         INTEGER PRIMARY KEY,
    week       INTEGER,              -- round: 1 Wild Card, 2 Divisional, 3 Conference, 5 Glory Bowl
    home INTEGER, away INTEGER, kind TEXT, neutral INTEGER,
    played     INTEGER, home_score INTEGER, away_score INTEGER, overtime INTEGER,
    box        TEXT
);
CREATE TABLE rating_history (       -- every player's ratings each season, kept for good
    player_id INTEGER, season INTEGER, ovr INTEGER, pot INTEGER
);
CREATE TABLE injury_history (       -- every injury, kept for good (player report: Past injuries)
    player_id INTEGER, season INTEGER, game TEXT, team_id INTEGER, kind TEXT, weeks INTEGER, how TEXT
);
CREATE TABLE drafts (               -- every draft pick, kept for good
    season INTEGER, round INTEGER, pick INTEGER, team_id INTEGER, player_id INTEGER
);
CREATE TABLE player_seasons (       -- every player's season lines, kept for good
    player_id  INTEGER, season INTEGER, phase TEXT, team_id INTEGER,
    stats      TEXT                  -- JSON: every stat for that season with that team
);
CREATE TABLE team_seasons (         -- every team's season, kept for good
    team_id    INTEGER, season INTEGER,
    line       TEXT                  -- JSON: record, points, division finish, seed, playoff result
);
CREATE TABLE injuries (
    player_id  INTEGER PRIMARY KEY,
    team_id    INTEGER,
    weeks      INTEGER,              -- weeks still to miss
    part       TEXT,                 -- e.g. knee
    week       INTEGER               -- week he was hurt
);
CREATE TABLE transactions (         -- every roster move, kept for good (transactions.py)
    season INTEGER, happened TEXT, team_id INTEGER, player_id INTEGER, move TEXT, note TEXT
);
CREATE TABLE contracts (            -- every current contract (contracts.py)
    player_id INTEGER PRIMARY KEY, team_id INTEGER, data TEXT   -- data: the whole contract as JSON
);
CREATE TABLE contract_log (         -- every signing, kept for good
    season INTEGER, data TEXT
);
"""

# Money state kept as JSON in league_info (dicts keyed by team id / season / player id).
MONEY_INFO = ("cap_history", "cap_carry", "cap_charges", "june1_used", "fa", "tv")   # tv: league_money.py


def _int_keys(obj):
    """JSON turns int keys into strings: turn number-like keys back into ints (all levels)."""
    if isinstance(obj, dict):
        return {(int(k) if isinstance(k, str) and k.lstrip("-").isdigit() else k): _int_keys(v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_int_keys(v) for v in obj]
    return obj

PLAIN_COLUMNS = [
    "id", "first_name", "last_name", "position", "experience", "height", "weight",
    "college", "hometown", "draft_year", "draft_round", "intel_test", "position_drill", "loyalty", "wants_winner",
    "leadership", "volatility", "popularity", "consistency",
]
# Added after the first saves existed; older files get these defaults.
NEWER_COLUMNS = {"adaptability": 50, "side": "", "durability": None, "retired": None}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def save_league(league: League, path, created=None):
    """Write the whole league to a file. Replaces the file if it exists.

    It writes to a temporary file first and swaps it in at the end, so if the
    game crashes mid-save, the old save is still there and still works."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if created is None:
        created = read_save_info(path).get("created") if path.exists() else None
    tmp = path.with_suffix(".saving")
    if tmp.exists():
        tmp.unlink()
    info = {
        "season": str(league.season),
        "user_team": "" if league.user_team_id is None else str(league.user_team_id),
        "name": league.name,
        "settings": json.dumps(league.settings),
        "created": created or _now(),
        "saved_at": _now(),
        "week": str(league.week),
        "pre_week": str(league.pre_week),
        "stage": league.stage,
        "division_ranks": json.dumps(league.division_ranks),
        "playoff_round": str(league.playoff_round),
        "playoff_seeds": json.dumps(league.playoff_seeds),
        "champions": json.dumps({str(k): v for k, v in league.champions.items()}),
        "offseason_report": json.dumps(league.offseason_report),
        "season_injuries": json.dumps({str(k): v for k, v in league.season_injuries.items()}),
        # Injury type, game-day status and original length (the injuries table
        # keeps team, weeks left, name and week hurt).
        "injury_details": json.dumps({str(pid): {k: i[k] for k in ("kind", "initial", "status", "aggravated",
                                                                    "reserve", "carryover") if k in i}
                                      for pid, i in league.injuries.items()}),
        "recovering": json.dumps({str(pid): r for pid, r in league.recovering.items()}),
        # Roster moves (transactions.py).
        "practice": json.dumps({str(k): v for k, v in getattr(league, "practice", {}).items()}),
        "reserve": json.dumps({str(k): v for k, v in getattr(league, "reserve", {}).items()}),
        "waivers": json.dumps(getattr(league, "waivers", [])),
        "ir_returns": json.dumps({str(k): v for k, v in getattr(league, "ir_returns", {}).items()}),
        "elevations": json.dumps({str(k): v for k, v in getattr(league, "elevations", {}).items()}),
        "elevated": json.dumps({str(k): v for k, v in getattr(league, "elevated", {}).items()}),
        "long_injuries": json.dumps({str(k): v for k, v in getattr(league, "long_injuries", {}).items()}),
        "staff_requests": json.dumps(getattr(league, "staff_requests", [])),
        # The offseason in progress (offseason.py phases), or null during a season.
        "offseason": json.dumps(getattr(league, "offseason", None)),
        # This year's draft class (scouting notes) and a draft in progress, or a startup
        # draft (draft_day.py), or null.
        "draft": json.dumps(getattr(league, "draft", None), separators=(",", ":")),
        **{key: json.dumps(getattr(league, key, None) or {}) for key in MONEY_INFO},
        # Awards and the Pro Bowl (awards.py, Oct 23): lists of records by season.
        "awards": json.dumps(getattr(league, "awards", None) or {}, separators=(",", ":")),
        # Coaching staffs and front offices (staff.py, Oct 24).
        "staff": json.dumps(getattr(league, "staff", None) or {}, separators=(",", ":")),
        # Finished seasons' news, kept as it was (news.freeze_season, Oct 22; compressed text).
        "news_archive": json.dumps(getattr(league, "news_archive", None) or {}, separators=(",", ":")),
    }
    db = sqlite3.connect(tmp)
    try:
        with db:
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO league_info VALUES (?, ?)", list(info.items()))
            db.executemany(
                "INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?)",
                [(t.id, t.city, t.nickname, t.abbrev, t.conference, t.division) for t in league.teams])
            rows = []
            for p in league.players:
                row = {c: getattr(p, c) for c in PLAIN_COLUMNS + list(NEWER_COLUMNS)}
                row["learned"] = json.dumps(p.learned)
                row["dev"] = json.dumps(p.dev) if p.dev else None
                row["team_id"] = league.rosters.get(p.id)
                row["birth_date"] = p.birth_date.isoformat()
                row["generational"] = int(p.generational)
                row["skills"] = json.dumps(p.skills)
                row["athletic"] = json.dumps(p.athletic)
                row["combine"] = json.dumps(p.combine)
                rows.append(row)
            columns = list(rows[0].keys())
            db.executemany(
                f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(':' + c for c in columns)})",
                rows)
            _write_depth_charts(db, league)
            db.executemany(
                "INSERT INTO schedule VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(g["id"], g["week"], g["home"], g["away"], g["kind"], int(g["played"]),
                  g["home_score"], g["away_score"], int(g["overtime"]),
                  json.dumps(league.boxes[g["id"]], separators=(",", ":")) if g["id"] in league.boxes else None)
                 for g in league.schedule])
            db.executemany(
                "INSERT INTO preseason VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(g["id"], g["week"], g["home"], g["away"], g["kind"], int(g.get("neutral", False)),
                  int(g["played"]), g["home_score"], g["away_score"], int(g["overtime"]),
                  json.dumps(league.boxes[g["id"]], separators=(",", ":")) if g["id"] in league.boxes else None)
                 for g in league.preseason])
            db.executemany(
                "INSERT INTO playoffs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(g["id"], g["week"], g["home"], g["away"], g["kind"], int(g.get("neutral", False)),
                  int(g["played"]), g["home_score"], g["away_score"], int(g["overtime"]),
                  json.dumps(league.boxes[g["id"]], separators=(",", ":")) if g["id"] in league.boxes else None)
                 for g in league.playoffs])
            db.executemany(
                "INSERT INTO rating_history VALUES (?, ?, ?, ?)",
                [(r["pid"], r["season"], r["ovr"], r["pot"]) for r in league.rating_history])
            db.executemany(
                "INSERT INTO injury_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(r["pid"], r["season"], r["game"], r["team"], r["kind"], r["weeks"], r["how"])
                 for r in league.injury_history])
            db.executemany(
                "INSERT INTO drafts VALUES (?, ?, ?, ?, ?)",
                [(d["season"], d["round"], d["pick"], d["team"], d["pid"]) for d in league.draft_history])
            db.executemany(
                "INSERT INTO player_seasons VALUES (?, ?, ?, ?, ?)",
                [(r["pid"], r["season"], r["phase"], r["team"], json.dumps(r["stats"], separators=(",", ":")))
                 for r in league.career])
            db.executemany(
                "INSERT INTO team_seasons VALUES (?, ?, ?)",
                [(r["team"], r["season"], json.dumps(r, separators=(",", ":"))) for r in league.team_history])
            db.executemany(
                "INSERT INTO injuries VALUES (?, ?, ?, ?, ?)",
                [(pid, i["team"], i["weeks"], i["part"], i["week"]) for pid, i in league.injuries.items()])
            db.executemany(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)",
                [(t["season"], t["when"], t["team"], t["pid"], t["move"], t["note"])
                 for t in getattr(league, "transactions", [])])
            db.executemany(
                "INSERT INTO contracts VALUES (?, ?, ?)",
                [(pid, c.get("team"), json.dumps(c, separators=(",", ":")))
                 for pid, c in (getattr(league, "contracts", None) or {}).items()])
            db.executemany(
                "INSERT INTO contract_log VALUES (?, ?)",
                [(r.get("season"), json.dumps(r, separators=(",", ":")))
                 for r in (getattr(league, "contract_log", None) or [])])
    finally:
        db.close()
    os.replace(tmp, path)


def _write_depth_charts(db, league):
    db.execute("DELETE FROM depth_charts")
    db.execute("DELETE FROM captains")
    db.executemany(
        "INSERT INTO captains VALUES (?, ?, ?)",
        [(team_id, unit, pid) for team_id, caps in league.captains.items() for unit, pid in caps.items()])
    db.executemany(
        "INSERT INTO depth_charts VALUES (?, ?, ?, ?)",
        [(team_id, slot, rank, pid)
         for team_id, chart in league.depth_charts.items()
         for slot, ids in chart.items()
         for rank, pid in enumerate(ids)])


def read_save_info(path):
    """The quick facts about a save (for the Load game list), without loading
    every player: name, season, your team, settings, when created and saved."""
    db = sqlite3.connect(path)
    try:
        info = dict(db.execute("SELECT key, value FROM league_info").fetchall())
        out = {
            "name": info.get("name") or "",
            "season": int(info["season"]),
            "settings": {**DEFAULT_SETTINGS, **json.loads(info.get("settings") or "{}")},
            "created": info.get("created"),
            "saved_at": info.get("saved_at"),
            "week": int(info.get("week") or 1),
            "pre_week": int(info.get("pre_week") or 1),
            "stage": info.get("stage") or "regular_season",
            "team": None,
        }
        user = info.get("user_team")
        if user:
            row = db.execute("SELECT city, nickname, abbrev FROM teams WHERE id = ?", (int(user),)).fetchone()
            if row:
                out["team"] = f"{row[0]} {row[1]}"
                out["team_abbrev"] = row[2]
        return out
    finally:
        db.close()


def rename_save(path, new_name):
    """Change a save's name without loading or re-saving the league."""
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute("DELETE FROM league_info WHERE key = 'name'")
            db.execute("INSERT INTO league_info VALUES ('name', ?)", (new_name,))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# History file: past seasons' box scores, beside the save (e.g.
# saves/bears-2026.history.db). Kept out of the main save so it stays fast to
# load and save as the years pile up; nothing is ever deleted.
# ---------------------------------------------------------------------------

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    season INTEGER, phase TEXT, game_id INTEGER,
    week INTEGER, home INTEGER, away INTEGER, kind TEXT,
    home_score INTEGER, away_score INTEGER, overtime INTEGER, neutral INTEGER,
    box TEXT,
    PRIMARY KEY (season, game_id)
);
"""


def write_history(path, finished):
    """Add finished games (from season.start_next_season) to the history file."""
    db = sqlite3.connect(path)
    try:
        with db:
            db.executescript(HISTORY_SCHEMA)
            db.executemany(
                "INSERT OR REPLACE INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(f["season"], f["phase"], f["game"]["id"], f["game"]["week"], f["game"]["home"], f["game"]["away"],
                  f["game"].get("kind"), f["game"]["home_score"], f["game"]["away_score"],
                  int(f["game"]["overtime"]), int(f["game"].get("neutral", False)),
                  json.dumps(f["box"], separators=(",", ":")) if f["box"] else None)
                 for f in finished])
    finally:
        db.close()


def read_history(path, season=None):
    """Past games from the history file (all seasons, or one)."""
    if not Path(path).exists():
        return []
    db = sqlite3.connect(path)
    try:
        db.row_factory = sqlite3.Row
        q = "SELECT * FROM games" + (" WHERE season = ?" if season is not None else "") + " ORDER BY season, game_id"
        rows = db.execute(q, (season,) if season is not None else ()).fetchall()
        return [{"season": r["season"], "phase": r["phase"],
                 "game": {"id": r["game_id"], "week": r["week"], "home": r["home"], "away": r["away"],
                          "kind": r["kind"], "home_score": r["home_score"], "away_score": r["away_score"],
                          "overtime": bool(r["overtime"]), "neutral": bool(r["neutral"]), "played": True},
                 "box": json.loads(r["box"]) if r["box"] else None} for r in rows]
    finally:
        db.close()


def load_league(path):
    """Read a league back from its file."""
    db = sqlite3.connect(path)
    try:
        db.row_factory = sqlite3.Row
        info = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM league_info")}
        teams = [Team(**dict(r)) for r in db.execute("SELECT * FROM teams ORDER BY id")]
        league = League(season=int(info["season"]), teams=teams)
        league.user_team_id = int(info["user_team"]) if info.get("user_team") else None
        league.name = info.get("name") or ""
        league.settings = {**DEFAULT_SETTINGS, **json.loads(info.get("settings") or "{}")}
        for r in db.execute("SELECT * FROM players ORDER BY id"):
            keys = r.keys()
            p = Player(
                **{c: r[c] for c in PLAIN_COLUMNS},
                **{c: (r[c] if c in keys and r[c] is not None else default)
                   for c, default in NEWER_COLUMNS.items()},
                learned=json.loads(r["learned"]) if "learned" in keys and r["learned"] else {},
                dev=json.loads(r["dev"]) if "dev" in keys and r["dev"] else None,
                birth_date=date.fromisoformat(r["birth_date"]),
                generational=bool(r["generational"]),
                skills={k: tuple(v) for k, v in json.loads(r["skills"]).items()},
                athletic=json.loads(r["athletic"]),
                combine=json.loads(r["combine"]),
            )
            fill_new_ratings(p)          # durability / RB endurance for older save files
            league.players.append(p)
            if r["team_id"] is not None:
                league.rosters[p.id] = r["team_id"]
        has_depth = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='depth_charts'").fetchone()
        if has_depth:
            for r in db.execute("SELECT * FROM depth_charts ORDER BY team_id, slot, rank"):
                league.depth_charts.setdefault(r["team_id"], {}).setdefault(r["slot"], []).append(r["player_id"])
        has_captains = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='captains'").fetchone()
        if has_captains:
            for r in db.execute("SELECT * FROM captains"):
                league.captains.setdefault(r["team_id"], {})[r["unit"]] = r["player_id"]
        # The season in progress (saves from before Step 7 piece 2 have none;
        # the screens make a schedule for them).
        league.week = int(info.get("week") or 1)
        league.stage = info.get("stage") or "regular_season"
        league.division_ranks = ({int(k): v for k, v in json.loads(info["division_ranks"]).items()}
                                 if info.get("division_ranks") not in (None, "null") else None)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "schedule" in tables:
            for r in db.execute("SELECT * FROM schedule ORDER BY id"):
                league.schedule.append({"id": r["id"], "week": r["week"], "home": r["home"], "away": r["away"],
                                        "kind": r["kind"], "played": bool(r["played"]),
                                        "home_score": r["home_score"], "away_score": r["away_score"],
                                        "overtime": bool(r["overtime"])})
                if r["box"]:
                    league.boxes[r["id"]] = json.loads(r["box"])
        league.pre_week = int(info.get("pre_week") or 1)
        if "preseason" in tables:
            for r in db.execute("SELECT * FROM preseason ORDER BY id"):
                league.preseason.append({"id": r["id"], "week": r["week"], "home": r["home"], "away": r["away"],
                                         "kind": r["kind"], "neutral": bool(r["neutral"]),
                                         "played": bool(r["played"]), "home_score": r["home_score"],
                                         "away_score": r["away_score"], "overtime": bool(r["overtime"])})
                if r["box"]:
                    league.boxes[r["id"]] = json.loads(r["box"])
        league.playoff_round = int(info.get("playoff_round") or 0)
        seeds = info.get("playoff_seeds")
        league.playoff_seeds = json.loads(seeds) if seeds not in (None, "null") else None
        if "playoffs" in tables:
            for r in db.execute("SELECT * FROM playoffs ORDER BY id"):
                league.playoffs.append({"id": r["id"], "week": r["week"], "home": r["home"], "away": r["away"],
                                        "kind": r["kind"], "neutral": bool(r["neutral"]),
                                        "played": bool(r["played"]), "home_score": r["home_score"],
                                        "away_score": r["away_score"], "overtime": bool(r["overtime"])})
                if r["box"]:
                    league.boxes[r["id"]] = json.loads(r["box"])
        if "player_seasons" in tables:
            for r in db.execute("SELECT * FROM player_seasons ORDER BY season, rowid"):
                league.career.append({"pid": r["player_id"], "season": r["season"], "phase": r["phase"],
                                      "team": r["team_id"], "stats": json.loads(r["stats"])})
        if "team_seasons" in tables:
            for r in db.execute("SELECT * FROM team_seasons ORDER BY season, team_id"):
                league.team_history.append(json.loads(r["line"]))
        league.champions = {int(k): v for k, v in json.loads(info.get("champions") or "{}").items()}
        rep = info.get("offseason_report")
        league.offseason_report = json.loads(rep) if rep not in (None, "null") else None
        if "rating_history" in tables:
            for r in db.execute("SELECT * FROM rating_history ORDER BY season, player_id"):
                league.rating_history.append({"pid": r["player_id"], "season": r["season"],
                                              "ovr": r["ovr"], "pot": r["pot"]})
        if "injury_history" in tables:
            for r in db.execute("SELECT * FROM injury_history ORDER BY rowid"):
                league.injury_history.append({"pid": r["player_id"], "season": r["season"], "game": r["game"],
                                              "team": r["team_id"], "kind": r["kind"], "weeks": r["weeks"],
                                              "how": r["how"]})
        league.season_injuries = {}
        for k, v in json.loads(info.get("season_injuries") or "{}").items():
            if isinstance(v, (int, float)):
                # Saves from before injury types: only the longest injury's weeks.
                # 12+ weeks keeps the old rule (a possible lasting hit).
                v = [["serious", int(v)]] if v >= 12 else []
            if v:
                league.season_injuries[int(k)] = v
        if "drafts" in tables:
            for r in db.execute("SELECT * FROM drafts ORDER BY season, pick"):
                league.draft_history.append({"season": r["season"], "round": r["round"], "pick": r["pick"],
                                             "team": r["team_id"], "pid": r["player_id"]})
        if "injuries" in tables:
            for r in db.execute("SELECT * FROM injuries"):
                league.injuries[r["player_id"]] = {"team": r["team_id"], "weeks": r["weeks"],
                                                   "part": r["part"], "week": r["week"]}
            for pid, extra in json.loads(info.get("injury_details") or "{}").items():
                if int(pid) in league.injuries:
                    league.injuries[int(pid)].update(extra)
        league.recovering = {int(k): v for k, v in json.loads(info.get("recovering") or "{}").items()}
        # Roster moves (saves from before Oct 22 have none; season.bring_up_to_date adds practice squads).
        league.practice = {int(k): v for k, v in json.loads(info.get("practice") or "{}").items()}
        league.reserve = {int(k): v for k, v in json.loads(info.get("reserve") or "{}").items()}
        league.waivers = json.loads(info.get("waivers") or "[]")
        league.ir_returns = {int(k): v for k, v in json.loads(info.get("ir_returns") or "{}").items()}
        league.elevations = {int(k): v for k, v in json.loads(info.get("elevations") or "{}").items()}
        league.elevated = {int(k): v for k, v in json.loads(info.get("elevated") or "{}").items()}
        league.long_injuries = {int(k): v for k, v in json.loads(info.get("long_injuries") or "{}").items()}
        league.staff_requests = json.loads(info.get("staff_requests") or "[]")
        league.offseason = json.loads(info.get("offseason") or "null")
        # This year's draft class and a draft in progress, or a startup draft (draft_day.py).
        league.draft = json.loads(info.get("draft") or "null")
        # Money (saves from before Oct 23 have none: season.bring_up_to_date sets contracts up).
        for key in MONEY_INFO:
            setattr(league, key, _int_keys(json.loads(info.get(key) or "{}")))
        if isinstance(league.fa.get("report"), dict):
            from collections import defaultdict
            league.fa["report"] = defaultdict(int, league.fa["report"])
        if "contracts" in tables:
            league.contracts = {r["player_id"]: _int_keys(json.loads(r["data"]))
                                for r in db.execute("SELECT * FROM contracts")}
        if "contract_log" in tables:
            league.contract_log = [json.loads(r["data"]) for r in db.execute("SELECT * FROM contract_log ORDER BY rowid")]
        # Awards (saves from before Oct 23 have none: they start empty).
        league.awards = json.loads(info.get("awards") or "{}")
        from . import awards
        awards.ensure(league)
        # Coaching staffs (saves from before Oct 24 have none: every team gets one,
        # seeded by the save's salt so it's the same staff every time it loads).
        league.staff = json.loads(info.get("staff") or "{}") or None
        # Finished seasons' news (saves from before Oct 22 have none: news writes every season).
        league.news_archive = json.loads(info.get("news_archive") or "{}") or None
        from . import staff
        if not league.staff:
            staff.ensure(league)
            league.filled_on_load = True
        elif not league.staff.get("gm"):
            staff.ensure(league)          # saves from before Oct 22: the AI general managers (gm.py)
            league.filled_on_load = True
        if "transactions" in tables:
            for r in db.execute("SELECT * FROM transactions ORDER BY rowid"):
                league.transactions.append({"season": r["season"], "when": r["happened"], "team": r["team_id"],
                                            "pid": r["player_id"], "move": r["move"], "note": r["note"]})
    finally:
        db.close()
    # Leagues saved before depth charts existed: let the AI set them. Charts
    # saved before a spot existed (the 3rd-down back, Oct 21) get the AI's pick
    # for that spot only (league.filled_on_load tells the screens it changed).
    for team in league.teams:
        if team.id not in league.depth_charts:
            league.auto_depth_chart(team.id)
        else:
            chart = league.depth_charts[team.id]
            before = {k: list(v) for k, v in chart.items()}
            depth.fill_missing_spots(chart, league.team_players(team.id))
            if chart != before:
                league.filled_on_load = True
        if team.id not in league.captains:
            # Seeded by season and team, so an older save gets the same
            # captains every time it loads (keeps the sim reproducible).
            league.vote_captains(team.id, rng=random.Random(f"captains-{league.season}-{team.id}"))
    # A draft class's hidden notes (draft.py: the truth, the league's shared mistake...) go back
    # on its prospects, so every screen and tool sees the same grades from the moment it loads.
    notes = league.draft.get("notes") if isinstance(league.draft, dict) else None
    if notes:
        from .draft import load_notes
        by_id = {p.id: p for p in league.players}
        load_notes([by_id[int(k)] for k in notes if int(k) in by_id], notes)
    # New players made after loading (draft classes, etc.) must get fresh ids.
    if league.players:
        player_module._next_id = max(player_module._next_id, max(p.id for p in league.players) + 1)
    return league
