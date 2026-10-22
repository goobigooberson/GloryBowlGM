# awards.py
# The league's official awards and the Pro Bowl (Blake, Oct 23: "absolutely
# there should be a player of the week, mvp, all pro team, and a fan voted pro
# bowl ... and a pro bowl game"). Rules only: screens and news read from here.
#
# What's handed out, and when (the real NFL's calendar):
#   - Players of the Week, after every regular-season week: Offensive,
#     Defensive and Special Teams, one each per conference (the NFL's set).
#   - Players of the Month: the same three per conference, plus an Offensive
#     and a Defensive Rookie of the Month league-wide. September, October,
#     November, and December (with any January games), as the NFL does it.
#   - MVP watch: the media's top five every other week from Week 6.
#   - Pro Bowl rosters, announced before the last regular-season week: fans,
#     players and coaches each count for a third of the vote (the NFL's way),
#     44 players per conference at the real Pro Bowl's position counts.
#   - All-Pro first and second teams, announced at the start of the playoffs
#     (the AP's positions: left and right tackles and guards, three edge
#     rushers, a slot corner, an all-purpose player, return men...).
#   - Pro Bowl replacements once the Glory Bowl teams are known (Glory Bowl
#     players, injured players and players who choose not to play), then the
#     Pro Bowl game in the week off before the Glory Bowl. It never counts in
#     any stats, and injuries in it don't carry over (Blake, Oct 23: a tackle
#     game, and its injuries never count).
#   - Season awards (MVP, Offensive and Defensive Player of the Year,
#     Offensive and Defensive Rookie of the Year, Comeback Player of the Year),
#     voted after the regular season and announced the week of the Glory Bowl,
#     like the NFL Honors. No Coach of the Year: the game has no coaches yet.
#   - Glory Bowl MVP, right after the game.
#
# How the voting works (so winners look like real ones; tools/awards_check.py
# compares them with the real NFL's 2000-2025 winners):
#   - A media panel of 50 voters. Season awards: each voter ranks five
#     players, 10-5-3-2-1 points (the AP's ballot since 2022). All-Pro: each
#     voter picks a first and a second team at every position.
#   - What voters see: the season's stats (turned into one number per player,
#     compared with what a great season at his position looks like), how his
#     team did (MVP leans heavily on QBs of winning teams), games missed, and
#     "film": his current overall rating, a stand-in for what watching him
#     shows (most of the story for linemen, who have no stats). Every voter
#     sees it a little differently, and each player's season has its own
#     story (media narrative), so close races can go either way.
#   - Never used: hidden ratings (consistency, durability, interception or
#     fumble avoidance, Generational status).
#
# Feel choices are marked PROVISIONAL for Blake (docs/build-log.md).

import math
import random
from collections import defaultdict

from . import playoffs as po
from . import schedule as sched
from .scale import legacy_shown

VOTERS = 50                       # media panel for season awards and All-Pro
BALLOT_POINTS = (10, 5, 3, 2, 1)  # points for 1st..5th on a season-award ballot

SEASON_AWARDS = [
    ("mvp", "Most Valuable Player", "MVP"),
    ("opoy", "Offensive Player of the Year", "Offensive Player of the Year"),
    ("dpoy", "Defensive Player of the Year", "Defensive Player of the Year"),
    ("oroy", "Offensive Rookie of the Year", "Offensive Rookie of the Year"),
    ("droy", "Defensive Rookie of the Year", "Defensive Rookie of the Year"),
    ("cpoy", "Comeback Player of the Year", "Comeback Player of the Year"),
]
AWARD_NAME = {k: name for k, name, _s in SEASON_AWARDS}
WEEKLY_KINDS = {"off": "Offensive", "def": "Defensive", "st": "Special Teams"}
MONTHS = ["September", "October", "November", "December"]

# Position groups (how voters compare players).
GROUP = {"QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
         "DE": "EDGE", "DT": "DT", "OLB": "LB", "ILB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P", "LS": "LS"}
OFFENSE_GROUPS = ("QB", "RB", "FB", "WR", "TE")
DEFENSE_GROUPS = ("EDGE", "DT", "LB", "CB", "S")

# ---- Season awards: knobs (tuned with tools/awards_check.py) -------------------
# What a great season looks like for each group, per 17 team games, in the
# value units below (offense: yards plus 20 a touchdown, minus 45 a turnover;
# defense: sacks, takeaways, tackles... see def_value). Roughly the league's
# best season at the position in a typical year, measured in the game's own
# seasons (tools/awards_check.py, 8 leagues: the average #1 at each position).
# The game's corners make more tackles than real ones, so their reference is
# higher than real numbers would suggest.
REF = {"QB": 5500, "RB": 2350, "FB": 880, "WR": 1930, "TE": 1360,
       "EDGE": 178, "DT": 140, "LB": 136, "CB": 128, "S": 112}
QB_RUSH_VOTE = 0.35
QB_TD_VOTE = 8                        # extra a touchdown pass, in voters' eyes                   # voters count a quarterback's rushing yards a bit less than passing
# How much each group's best seasons count for each award (voters' view of
# positional value: an MVP is a quarterback unless a back has a historic year).
WEIGHT = {
    "mvp": {"QB": 1.00, "RB": 0.93, "WR": 0.66, "TE": 0.60, "EDGE": 0.62, "DT": 0.62, "LB": 0.50,
            "CB": 0.50, "S": 0.50},
    "opoy": {"QB": 0.90, "RB": 0.97, "WR": 0.95, "TE": 0.60},
    "dpoy": {"EDGE": 1.06, "DT": 1.00, "LB": 0.95, "CB": 1.03, "S": 0.98},
    "oroy": {"QB": 1.00, "RB": 0.97, "WR": 1.00, "TE": 0.80},
    "droy": {"EDGE": 1.04, "DT": 1.02, "LB": 1.02, "CB": 0.97, "S": 0.80},
    "cpoy": {"QB": 1.00, "RB": 0.90, "WR": 0.90, "TE": 0.90, "EDGE": 0.85, "DT": 0.85, "LB": 0.85,
             "CB": 0.85, "S": 0.85},
}
# Team success: score += TEAM_K * (win% - .500), plus playoff bonuses.
TEAM_K = {"mvp": 0.70, "opoy": 0.35, "dpoy": 0.45, "oroy": 0.12, "droy": 0.08, "cpoy": 0.30}
PLAYOFF_BONUS = {"mvp": 0.05, "opoy": 0.02, "dpoy": 0.02, "oroy": 0.02, "droy": 0.0, "cpoy": 0.03}
TOP_SEED_BONUS = {"mvp": 0.04}
MISSED_PLAYOFFS = {"mvp": -0.10, "opoy": -0.02}
MISSED_GAME = {"mvp": -0.025, "opoy": -0.01, "dpoy": -0.01}   # per game missed beyond the first
REPEAT = {"mvp": -0.03}               # voter fatigue: last year's winner
MVP_SPLIT = 0.02                      # OPOY voters lean away from the MVP (real since 2016: 20% overlap)
NARRATIVE_SD = 0.06                   # each player's season story, shared by every voter
VOTER_SD = 0.07                       # each voter's own view
COMEBACK_K = 0.35                     # how much the size of the comeback counts
# Comeback: an injury comeback missed at least this share of last season...
COMEBACK_INJURY_MISSED = 0.45
# ...a revival had less than this share of a great season last year and at least
# COMEBACK_REVIVAL_NOW this year.
COMEBACK_REVIVAL_PREV = 0.35
COMEBACK_REVIVAL_PROVEN = 0.55             # ...and had a good season (this share or more) before that
COMEBACK_REVIVAL_NOW = 0.55

# ---- All-Pro (the AP's positions) ------------------------------------------------
# (spot, label, how many, pool)
ALL_PRO_SPOTS = [
    ("QB", "Quarterback", 1, "QB"), ("RB", "Running back", 1, "RB"), ("FB", "Fullback", 1, "FB"),
    ("WR", "Wide receiver", 3, "WR"), ("TE", "Tight end", 1, "TE"), ("AP", "All-purpose", 1, "AP"),
    ("LT", "Left tackle", 1, "LT"), ("LG", "Left guard", 1, "LG"), ("C", "Center", 1, "C"),
    ("RG", "Right guard", 1, "RG"), ("RT", "Right tackle", 1, "RT"),
    ("EDGE", "Edge rusher", 3, "DE"), ("DT", "Interior lineman", 2, "DT"), ("LB", "Linebacker", 2, "LB"),
    ("CB", "Cornerback", 2, "CB"), ("NB", "Slot cornerback", 1, "NB"), ("S", "Safety", 2, "S"),
    ("K", "Kicker", 1, "K"), ("P", "Punter", 1, "P"), ("KR", "Kick returner", 1, "KR"),
    ("PR", "Punt returner", 1, "PR"), ("ST", "Special teamer", 1, "ST"), ("LS", "Long snapper", 1, "LS"),
]
ALL_PRO_LABEL = {s: label for s, label, _n, _p in ALL_PRO_SPOTS}
ALL_PRO_NOISE = 0.30                  # each voter's view, in z units
ALL_PRO_STORY = 0.12                  # each player's season story, shared by every voter
# At quarterback the panel votes the way it votes for MVP (the same voters, the same
# case: stats and winning), so the MVP is almost always the All-Pro quarterback.
# Their MVP case is turned into the All-Pro scale by this (case points per z).
ALL_PRO_QB_SCALE = 0.08

# ---- Pro Bowl ----------------------------------------------------------------------
# Per conference (the real Pro Bowl's 44): (spot, label, players, starters, pool)
PRO_BOWL_SPOTS = [
    ("QB", "Quarterbacks", 3, 1, "QB"), ("RB", "Running backs", 3, 1, "RB"), ("FB", "Fullback", 1, 1, "FB"),
    ("WR", "Wide receivers", 4, 2, "WR"), ("TE", "Tight ends", 2, 1, "TE"), ("T", "Tackles", 3, 2, "T"),
    ("G", "Guards", 3, 2, "G"), ("C", "Centers", 2, 1, "C"), ("DE", "Defensive ends", 3, 2, "DE"),
    ("DT", "Defensive tackles", 3, 2, "DT"), ("OLB", "Outside linebackers", 3, 2, "OLB"),
    ("ILB", "Inside linebackers", 2, 1, "ILB"), ("CB", "Cornerbacks", 4, 2, "CB"), ("S", "Safeties", 3, 2, "S"),
    ("K", "Kicker", 1, 1, "K"), ("P", "Punter", 1, 1, "P"), ("LS", "Long snapper", 1, 1, "LS"),
    ("RS", "Return specialist", 1, 1, "RS"), ("ST", "Special teamer", 1, 1, "ST"),
]
PRO_BOWL_LABEL = {s: label for s, label, _n, _st, _p in PRO_BOWL_SPOTS}
ALTERNATES = 4                        # alternates kept per spot, in order
VOTE_TEMP = 0.45                      # how lopsided each group's vote is (lower = more lopsided)
# Fans (PROVISIONAL): fame counts, and (Blake) a slight boost for strong
# personalities who play well. Nobody gets in without playing (snap share)
# and playing well (above the typical regular at his position).
FAN_FAME_K = 0.35                     # per 25 points of popularity above 50
FAN_PERSONALITY_K = 0.50              # x his performance (z, if above 0) x personality strength (0-1)
FAN_TEAM_K = 0.60                     # x (win% - .500)
PRO_BOWL_MIN_SHARE = 0.45             # share of his team's snaps
MIN_SHARE = {"FB": 0.2}               # a regular at his position (fullbacks play about a third of the snaps)
PRO_BOWL_MIN_GAMES = 0.5              # share of his team's games
PRO_BOWL_MIN_PERF = 0.0               # performance z (0 = the typical regular at his position)
# Players who choose not to play (PROVISIONAL; the real NFL often replaces
# half its original picks, counting Super Bowl players and injuries).
DECLINE_BASE = 0.15
DECLINE_PER_SEASON = 0.015            # more for veterans past 5 seasons
DECLINE_MAX = 0.40
PRO_BOWL_SITES = ["LVG", "MIA", "PHX", "SDG", "TAM", "LAS", "HOU", "NOR"]
PRO_BOWL_TEAM_IDS = (901, 902)

# How much "film" (his current overall rating) counts next to his stats, by position.
FILM = {"QB": 0.2, "RB": 0.2, "FB": 0.7, "WR": 0.2, "TE": 0.3, "T": 1.0, "G": 1.0, "C": 1.0,
        "DE": 0.25, "DT": 0.35, "OLB": 0.3, "ILB": 0.3, "CB": 0.45, "S": 0.35, "K": 0.1, "P": 0.1, "LS": 1.0}
REP_K = 0.08                          # per earlier All-Pro or Pro Bowl (up to 3): voters remember


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

KEYS = ("weekly", "monthly", "mvp_watch", "pro_bowl", "pro_bowl_games", "all_pro", "season", "gb_mvp", "notes")


def ensure(league):
    """league.awards: lists of records, each with its season (saved as JSON;
    older saves start with none)."""
    a = getattr(league, "awards", None)
    if not isinstance(a, dict):
        a = {}
        league.awards = a
    for k in KEYS:
        if not isinstance(a.get(k), list):
            a[k] = []
    return a


def records(league, kind, season=None):
    ensure(league)
    return [r for r in league.awards[kind] if season is None or r["season"] == season]


def _done(league, kind, **match):
    return any(all(r.get(k) == v for k, v in match.items()) for r in league.awards[kind])


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _f(s, k):
    return (s or {}).get(k, 0) or 0


def _rng(league, *key):
    return random.Random("awards-" + "-".join(str(k) for k in (league.settings.get("salt", ""),) + key))


def _n_weeks(league):
    return league.settings.get("season_games", 17) + 1


def _player(league, pid):
    try:
        return league.player(int(pid))
    except (KeyError, ValueError, TypeError):
        return None


def conferences(league):
    return sorted({t.conference for t in league.teams})


def conf_of(league, tid):
    t = next((x for x in league.teams if x.id == tid), None)
    return t.conference if t else None


def group_of(position):
    return GROUP.get(position)


def off_value(s):
    """Offense in yards: yards from scrimmage and passing (sacks taken off),
    20 a touchdown, minus 45 a turnover (like adjusted net yards)."""
    return (_f(s, "pass_yds") - _f(s, "sacked_yds") + 20 * _f(s, "pass_td") - 45 * _f(s, "pass_int")
            + _f(s, "rush_yds") + 20 * _f(s, "rush_td") + _f(s, "rec_yds") + 20 * _f(s, "rec_td")
            - 45 * _f(s, "fum_lost"))


def def_value(s):
    """Defense in points: sacks and takeaways count most, then tackles for
    loss, pass breakups, QB hits and tackles (special teams tackles left out)."""
    tackles = _f(s, "tkl") + _f(s, "ast") - _f(s, "st_tkl")
    return (5 * _f(s, "sacks") + 0.6 * _f(s, "qb_hits") + 1.2 * _f(s, "tfl") + 0.35 * tackles
            + 6 * _f(s, "def_int") + 1.6 * _f(s, "pd") + 3 * _f(s, "ff") + 2 * _f(s, "fr")
            + 6 * _f(s, "def_td") + 3 * _f(s, "safeties"))


def kick_value(s):
    made, att = _f(s, "fgm"), _f(s, "fga")
    return (3 * made - 3.5 * (att - made) + 2 * _f(s, "fgm_50") + 0.5 * _f(s, "xpm")
            - 2 * (_f(s, "xpa") - _f(s, "xpm")))


def punt_value(s):
    n = _f(s, "punts")
    if not n:
        return 0.0
    net = (_f(s, "punt_yds") - _f(s, "punt_ret_yds") - 20 * _f(s, "punt_tb")) / n
    return n * (net - 40) * 0.3 + _f(s, "punt_in20")


def return_value(s, kind="both"):
    kr = _f(s, "kr_yds") / 15 + 15 * _f(s, "kr_td")
    pr = _f(s, "pr_yds") / 8 + 15 * _f(s, "pr_td")
    return {"kr": kr, "pr": pr}.get(kind, kr + pr) - 10 * _f(s, "fum_lost") * (1 if kind != "both" else 0)


def season_value(position, s):
    g = group_of(position)
    if g in OFFENSE_GROUPS:
        return off_value(s)
    if g in DEFENSE_GROUPS:
        return def_value(s)
    return 0.0


def vote_group(position, s):
    """The group voters compare him with: a linebacker who mostly rushes the
    passer is judged as an edge rusher (like the NFL's 3-4 outside linebackers)."""
    g = group_of(position)
    if g == "LB" and 5 * _f(s, "sacks") > 0.45 * max(1.0, def_value(s)):
        return "EDGE"
    return g


def vote_value(position, s):
    """His season as award voters see it (compared with REF[vote_group])."""
    v = season_value(position, s)
    if group_of(position) == "QB":
        # Touchdown passes make headlines; rushing yards count for less.
        v += QB_TD_VOTE * _f(s, "pass_td") - (1 - QB_RUSH_VOTE) * _f(s, "rush_yds")
    return v


def film(p):
    # The Oct 22 scale the voters were tuned on (tools/awards_check.py), not the
    # rarer top ratings screens show since Oct 24.
    return legacy_shown(p.overall(), p.position)


# ---------------------------------------------------------------------------
# A stretch of the regular season: every player's totals and every team's
# games, snaps and record (weeks first..last).
# ---------------------------------------------------------------------------

_cache = {}


def stretch(league, first=1, last=None):
    last = last or _n_weeks(league)
    games = [g for g in league.schedule if g["played"] and first <= g["week"] <= last and g["id"] in league.boxes]
    key = (id(league), league.season, first, last, len(games))
    if key in _cache:
        return _cache[key]
    players = defaultdict(lambda: defaultdict(float))
    teams = defaultdict(lambda: {"g": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "off_plays": 0, "def_plays": 0})
    for g in sorted(games, key=lambda g: g["week"]):
        box = league.boxes[g["id"]]
        for idx, tid, opp, pf, pa in ((0, g["home"], g["away"], g["home_score"], g["away_score"]),
                                      (1, g["away"], g["home"], g["away_score"], g["home_score"])):
            t = teams[tid]
            t["g"] += 1
            t["pf"] += pf
            t["pa"] += pa
            t["w" if pf > pa else "l" if pf < pa else "t"] += 1
            t["off_plays"] += box["team"][idx].get("plays", 0)
            t["def_plays"] += box["team"][1 - idx].get("plays", 0)
        for pid_s, line in box["players"].items():
            s = players[int(pid_s)]
            s["team"] = line["team"]
            s["gp"] += 1
            for k, v in line.items():
                if k == "team" or not isinstance(v, (int, float)):
                    continue
                s[k] = max(s[k], v) if k.endswith("_long") else s[k] + v
    for t in teams.values():
        t["pct"] = (t["w"] + 0.5 * t["t"]) / t["g"] if t["g"] else 0.5
    out = ({pid: dict(s) for pid, s in players.items()}, dict(teams))
    _cache.clear()
    _cache[key] = out
    return out


def snap_share(s, team):
    if not team:
        return 0.0
    off = _f(s, "off_snaps") / team["off_plays"] if team["off_plays"] else 0.0
    de = _f(s, "def_snaps") / team["def_plays"] if team["def_plays"] else 0.0
    return min(1.0, max(off, de))


def _team_now(league, pid, fallback=None):
    from . import transactions
    return transactions.team_of(league, pid)[0] or fallback


def _reputation(league, pid, season):
    """Earlier All-Pro and Pro Bowl nods (voters remember), up to 3."""
    n = sum(1 for r in league.awards["all_pro"] if r["pid"] == pid and r["season"] < season and r["team_no"] == 1)
    n += sum(1 for r in league.awards["pro_bowl"] if r["pid"] == pid and r["season"] < season and played_pro_bowl(r))
    return min(3, n)


def played_pro_bowl(r):
    """A Pro Bowl selection that counts (the NFL counts alternates who were added)."""
    return r.get("role") == "selected" or r.get("added")


# ---------------------------------------------------------------------------
# Performance at a position, compared with the league's regulars there
# ---------------------------------------------------------------------------

def _depth_spot(league, pid, tid):
    """The spot he starts at on his team's depth chart (LT, NB...), or None."""
    chart = league.depth_charts.get(tid) or {}
    for slot, ids in chart.items():
        if ids and ids[0] == pid:
            return slot
    return None


def _pool_of(league, p, tid):
    """Which All-Pro / Pro Bowl pools a player belongs to."""
    pos = p.position
    pools = {pos}
    if pos in ("OLB", "ILB"):
        pools.add("LB")
    if pos == "T" or pos == "G":
        spot = _depth_spot(league, p.id, tid)
        side = {"LT": "L", "RT": "R", "LG": "L", "RG": "R"}.get(spot) or ("R" if p.side == "R" else "L")
        pools.add(("L" if side == "L" else "R") + pos)
    if pos in ("CB", "S") and _depth_spot(league, p.id, tid) == "NB":
        pools.add("NB")
    if pos in ("RB", "WR", "TE"):
        pools.add("AP")
    return pools


def candidates(league, first=1, last=None):
    """Every player who played in the stretch, with how he compares with the
    regulars at his position: {pid: info}. info: p, team, conf, s (totals),
    share (snaps), gp_share, stat, film, perf (z: 0 = the typical regular)."""
    totals, teams = stretch(league, first, last)
    out = {}
    for pid, s in totals.items():
        p = _player(league, pid)
        if p is None or p.position not in GROUP:
            continue
        tid = s["team"]
        team = teams.get(tid)
        share = snap_share(s, team)
        gp_share = s["gp"] / team["g"] if team and team["g"] else 0.0
        stat = {"K": kick_value, "P": punt_value}.get(p.position, lambda x: vote_value(p.position, x))(s)
        out[pid] = {"pid": pid, "p": p, "team": tid, "conf": conf_of(league, tid), "s": s, "share": share,
                    "gp_share": gp_share, "stat": stat, "film": film(p), "pools": _pool_of(league, p, tid),
                    "regular": _regular(p, s, share, gp_share, team)}
    # Long snappers have no stats line of their own: each team's snapper.
    for t in league.teams:
        chart = league.depth_charts.get(t.id) or {}
        for pid in (chart.get("LS") or [])[:1]:
            p = _player(league, pid)
            if p and pid not in out and t.id in teams:
                out[pid] = {"pid": pid, "p": p, "team": t.id, "conf": t.conference, "s": {"team": t.id},
                            "share": 0.0, "gp_share": 1.0, "stat": 0.0, "film": film(p), "pools": {p.position},
                            "regular": True}
    # z-scores against the regulars at each position (league-wide).
    by_pos = defaultdict(list)
    for c in out.values():
        if c["regular"]:
            by_pos[c["p"].position].append(c)
    norms = {}
    for pos, cs in by_pos.items():
        norms[pos] = (_mean_sd([c["stat"] for c in cs]), _mean_sd([c["film"] for c in cs]))
    for c in out.values():
        pos = c["p"].position
        (sm, ss), (fm, fs) = norms.get(pos, ((0, 1), (50, 10)))
        c["stat_z"] = (c["stat"] - sm) / ss
        c["film_z"] = (c["film"] - fm) / fs
        f = FILM.get(pos, 0.3)
        c["perf"] = (1 - f) * c["stat_z"] + f * c["film_z"]
    return out, teams


def _regular(p, s, share, gp_share, team):
    if p.position == "K":
        return _f(s, "fga") + _f(s, "xpa") >= 2 * (team or {}).get("g", 1) * 0.5
    if p.position == "P":
        return _f(s, "punts") >= 2 * (team or {}).get("g", 1) * 0.5
    if p.position == "LS":
        return True
    return share >= MIN_SHARE.get(p.position, 0.5) and gp_share >= 0.5


def _mean_sd(xs):
    if len(xs) < 2:
        return (xs[0] if xs else 0.0), 1.0
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
    return m, sd or 1.0


def _special(cands, kind):
    """Return men and core special teams players (z among those who did it)."""
    rows = []
    for c in cands.values():
        s = c["s"]
        if kind == "KR" and _f(s, "kr") >= max(10, 0.6 * c.get("team_g", 10)):
            rows.append((c, return_value(s, "kr")))
        elif kind == "PR" and _f(s, "pr") >= 8:
            rows.append((c, return_value(s, "pr")))
        elif kind == "RS" and _f(s, "kr") + _f(s, "pr") >= 12:
            rows.append((c, return_value(s)))
        elif kind == "ST" and c["p"].position not in ("K", "P", "LS") and _f(s, "st_tkl") >= 3 and c["share"] < 0.5:
            rows.append((c, 3 * _f(s, "st_tkl") + 6 * _f(s, "ret_td")))
    if not rows:
        return []
    m, sd = _mean_sd([v for _c, v in rows])
    return [dict(c, perf=(v - m) / sd, stat=v) for c, v in rows]


def _all_purpose(cands):
    rows = []
    for c in cands.values():
        if "AP" not in c["pools"] or not c["regular"]:
            continue
        s = c["s"]
        ap = (_f(s, "rush_yds") + _f(s, "rec_yds") + 0.5 * (_f(s, "kr_yds") + _f(s, "pr_yds"))
              + 20 * (_f(s, "rush_td") + _f(s, "rec_td") + _f(s, "kr_td") + _f(s, "pr_td")))
        rows.append((c, ap))
    if not rows:
        return []
    m, sd = _mean_sd([v for _c, v in rows])
    return [dict(c, perf=(v - m) / sd, stat=v) for c, v in rows]


def pool(cands, name):
    """Players in an All-Pro / Pro Bowl pool, best first."""
    if name in ("KR", "PR", "RS", "ST"):
        rows = _special(cands, name)
    elif name == "AP":
        rows = _all_purpose(cands)
    else:
        rows = [c for c in cands.values() if name in c["pools"] and c["regular"]]
        if name in ("LT", "RT", "LG", "RG", "C"):
            # Starters only: a backup who filled in is no All-Pro lineman.
            rows = [c for c in rows if c["share"] >= 0.6]
    return sorted(rows, key=lambda c: -c["perf"])


# ---------------------------------------------------------------------------
# Players of the Week
# ---------------------------------------------------------------------------

# One game's offense counts in yards (off_value); quarterbacks pile up more, so
# their games are scaled down to compete fairly with backs and receivers.
GAME_OFF_WEIGHT = {"QB": 0.53, "RB": 1.0, "FB": 1.0, "WR": 1.0, "TE": 1.05}
WIN_BONUS = 1.15                      # the league office likes a winner
GAME_NOISE = 0.06                     # close calls go either way


def st_game_value(s):
    v = 1.3 * kick_value(s) + (2 if _f(s, "fg_long") >= 55 else 0)
    v += (_f(s, "kr_yds") + _f(s, "pr_yds")) / 16 + 12 * (_f(s, "kr_td") + _f(s, "pr_td"))
    if _f(s, "punts") >= 3:
        v += max(0.0, punt_value(s)) * 0.8
    return v


def _week_scores(league, week):
    """[(score, kind, conf, pid, line, game)] for every notable game line of a week."""
    out = []
    for g in league.schedule:
        if g["week"] != week or not g["played"] or g["id"] not in league.boxes:
            continue
        box = league.boxes[g["id"]]
        for pid_s, line in box["players"].items():
            p = _player(league, pid_s)
            if p is None:
                continue
            tid = line["team"]
            pf, pa = (g["home_score"], g["away_score"]) if tid == g["home"] else (g["away_score"], g["home_score"])
            mult = WIN_BONUS if pf > pa else (1.05 if pf == pa else 1.0)
            grp = group_of(p.position)
            conf = conf_of(league, tid)
            if grp in GAME_OFF_WEIGHT:
                out.append((off_value(line) * GAME_OFF_WEIGHT[grp] * mult, "off", conf, p.id, line, g))
            if grp in DEFENSE_GROUPS:
                out.append((def_value(line) * mult, "def", conf, p.id, line, g))
            st = st_game_value(line)
            if st > 0:
                out.append((st * mult * (1.15 if pf > pa else 1.0), "st", conf, p.id, line, g))
    return out


def _compact_line(line):
    return {k: (round(v, 1) if isinstance(v, float) else v) for k, v in line.items()
            if v and not k.endswith("_snaps")}


def players_of_the_week(league, week):
    if _done(league, "weekly", season=league.season, week=week):
        return
    rng = _rng(league, league.season, "pow", week)
    best = {}
    for score, kind, conf, pid, line, g in _week_scores(league, week):
        score *= 1 + rng.gauss(0, GAME_NOISE)
        key = (conf, kind)
        if key not in best or score > best[key][0]:
            best[key] = (score, pid, line, g)
    for conf in conferences(league):
        for kind in WEEKLY_KINDS:
            if (conf, kind) not in best:
                continue
            score, pid, line, g = best[(conf, kind)]
            tid = line["team"]
            home = g["home"] == tid
            league.awards["weekly"].append({
                "season": league.season, "week": week, "conf": conf, "kind": kind, "pid": pid, "team": tid,
                "opp": g["away"] if home else g["home"], "home": home,
                "pf": g["home_score"] if home else g["away_score"], "pa": g["away_score"] if home else g["home_score"],
                "gid": g["id"], "line": _compact_line(line)})


# ---------------------------------------------------------------------------
# Players of the Month
# ---------------------------------------------------------------------------

def month_of_week(league, week):
    d = sched.week_sunday(league.season, week)
    if d.month == 9:
        return "September"
    if d.month == 10:
        return "October"
    if d.month == 11:
        return "November"
    return "December"                 # December and January together, as the NFL does


def month_weeks(league, month):
    return [w for w in range(1, _n_weeks(league) + 1) if month_of_week(league, w) == month]


def players_of_the_month(league, month):
    if _done(league, "monthly", season=league.season, month=month):
        return
    weeks = month_weeks(league, month)
    if not weeks:
        return
    cands, teams = candidates(league, weeks[0], weeks[-1])
    rng = _rng(league, league.season, "month", month)
    picks = []
    for conf in conferences(league):
        for kind, award in (("off", "opoy"), ("def", "dpoy")):
            scored = _award_scores(league, award, cands, teams, rng, rookies=None, conf=conf)
            if scored:
                picks.append((conf, kind, scored[0][0]))
        st = []
        for c in cands.values():
            if c["conf"] != conf:
                continue
            v = kick_value(c["s"]) + 0.8 * return_value(c["s"]) + 0.8 * max(0.0, punt_value(c["s"]))
            if v > 0:
                st.append((v * (1 + rng.gauss(0, GAME_NOISE)), c["pid"]))
        if st:
            picks.append((conf, "st", max(st)[1]))
    for kind, award in (("orook", "oroy"), ("drook", "droy")):
        scored = _award_scores(league, award, cands, teams, rng, rookies=True)
        if scored:
            picks.append((None, kind, scored[0][0]))
    for conf, kind, pid in picks:
        c = cands[pid]
        league.awards["monthly"].append({"season": league.season, "month": month, "conf": conf, "kind": kind,
                                         "pid": pid, "team": c["team"], "weeks": [weeks[0], weeks[-1]],
                                         "line": _compact_line(c["s"]), "w": teams[c["team"]]["w"],
                                         "l": teams[c["team"]]["l"], "t": teams[c["team"]]["t"]})


# ---------------------------------------------------------------------------
# Season awards: the media vote
# ---------------------------------------------------------------------------

def _award_scores(league, award, cands, teams, rng, rookies=None, conf=None, seeds=None, prev_winner=None,
                  mvp_pid=None, comeback=None):
    """[(pid, score)] best first: how strong each player's case is before the
    voters' own views. comeback: {pid: (kind, size)} for the comeback award."""
    weights = WEIGHT[award]
    out = []
    for pid, c in cands.items():
        p = c["p"]
        grp = vote_group(p.position, c["s"])
        w = weights.get(grp)
        if not w or (conf and c["conf"] != conf):
            continue
        if rookies is True and p.experience != 0:
            continue
        if award == "cpoy" and pid not in (comeback or {}):
            continue
        team = teams.get(c["team"])
        if not team:
            continue
        tg = team["g"]
        ratio = vote_value(p.position, c["s"]) / (REF[grp] * tg / 17)
        score = w * ratio
        score += TEAM_K.get(award, 0) * (team["pct"] - 0.5)
        if seeds is not None:
            seed = seeds.get(c["team"])
            if seed:
                score += PLAYOFF_BONUS.get(award, 0) + (TOP_SEED_BONUS.get(award, 0) if seed == 1 else 0)
            else:
                score += MISSED_PLAYOFFS.get(award, 0)
        score += MISSED_GAME.get(award, 0) * max(0, tg - c["s"].get("gp", 0) - 1)
        if prev_winner == pid:
            score += REPEAT.get(award, 0)
        if award == "opoy" and pid == mvp_pid:
            score -= MVP_SPLIT
        if award == "cpoy":
            score += COMEBACK_K * comeback[pid][1]
        out.append((pid, score))
    out.sort(key=lambda x: -x[1])
    return out


def _vote(league, award, scored, rng):
    """50 voters each rank five (10-5-3-2-1). [[pid, firsts, points]] best first."""
    top = scored[:15]
    if not top:
        return []
    story = {pid: rng.gauss(0, NARRATIVE_SD) for pid, _s in top}
    points = defaultdict(int)
    firsts = defaultdict(int)
    for _v in range(VOTERS):
        seen = sorted(top, key=lambda x: -(x[1] + story[x[0]] + rng.gauss(0, VOTER_SD)))
        for place, (pid, _s) in enumerate(seen[:len(BALLOT_POINTS)]):
            points[pid] += BALLOT_POINTS[place]
            if place == 0:
                firsts[pid] += 1
    order = sorted(points, key=lambda pid: (-points[pid], -firsts[pid]))
    return [[pid, firsts[pid], points[pid]] for pid in order]


def comeback_cases(league):
    """{pid: (kind, size)}: players coming back from an injury-shortened season
    ('injury') or from a season as a backup or worse ('revival'), judged on
    last season's records. None in the league's first season (no records)."""
    season = league.season
    if season <= league.settings.get("first_season", season):
        return {}
    prev = defaultdict(lambda: defaultdict(float))
    for r in league.career:
        if r["season"] == season - 1 and r["phase"] == "regular":
            for k, v in r["stats"].items():
                if isinstance(v, (int, float)):
                    prev[r["pid"]][k] += v
    hurt = defaultdict(int)
    for r in league.injury_history:
        if r["season"] == season - 1:
            hurt[r["pid"]] = max(hurt[r["pid"]], r.get("weeks") or 0)
    # His best season before last (regular season, vs a great season at his position):
    # a revival is a player who was good before, fell off, and came back.
    by_season = defaultdict(lambda: defaultdict(float))
    for r in league.career:
        if r["season"] < season - 1 and r["phase"] == "regular":
            for k, v in r["stats"].items():
                if isinstance(v, (int, float)):
                    by_season[(r["pid"], r["season"])][k] += v
    best_before = defaultdict(float)
    for (pid, _s), st in by_season.items():
        p = _player(league, pid)
        if p and vote_group(p.position, st) in REF:
            best_before[pid] = max(best_before[pid], vote_value(p.position, st) / REF[vote_group(p.position, st)])
    season_games = league.settings.get("season_games", 17)
    cands, teams = candidates(league)
    out = {}
    for pid, c in cands.items():
        p = c["p"]
        grp = vote_group(p.position, c["s"])
        if grp not in WEIGHT["cpoy"] or p.experience == 0 or c["gp_share"] < 0.7:
            continue
        tg = teams[c["team"]]["g"]
        now = vote_value(p.position, c["s"]) / (REF[grp] * tg / 17)
        last = prev.get(pid, {})
        gp = last.get("gp", 0)
        missed = 1 - gp / season_games
        if hurt.get(pid, 0) >= 4 and missed >= COMEBACK_INJURY_MISSED and now >= 0.45:
            out[pid] = ("injury", missed)
            continue
        if best_before.get(pid, 0.0) < COMEBACK_REVIVAL_PROVEN:
            continue                  # never good on record: a breakout, not a comeback
        before = vote_value(p.position, last) / REF[grp] if last else 0.0
        if before < COMEBACK_REVIVAL_PREV and now >= COMEBACK_REVIVAL_NOW:
            out[pid] = ("revival", min(1.0, now - before))
    return out


def season_awards(league):
    """The media's season awards (regular season only), announced the week of
    the Glory Bowl."""
    if _done(league, "season", season=league.season):
        return
    cands, teams = candidates(league)
    seeds = {}
    for ids in (league.playoff_seeds or {}).values():
        for i, tid in enumerate(ids, start=1):
            seeds[tid] = i
    last = {r["award"]: r["pid"] for r in league.awards["season"] if r["season"] == league.season - 1}
    comeback = comeback_cases(league)
    mvp_pid = None
    for award, _name, _short in SEASON_AWARDS:
        rng = _rng(league, league.season, award)
        if award == "cpoy" and not comeback:
            league.awards["notes"].append({"season": league.season, "award": award,
                                           "text": "No Comeback Player of the Year: it needs a season on record "
                                                   "to come back from (the league's first season has none)."
                                           if league.season <= league.settings.get("first_season", league.season)
                                           else "No Comeback Player of the Year: no player qualified."})
            continue
        scored = _award_scores(league, award, cands, teams, rng, rookies=True if award in ("oroy", "droy") else None,
                               seeds=seeds, prev_winner=last.get(award), mvp_pid=mvp_pid, comeback=comeback)
        votes = _vote(league, award, scored, rng)
        if not votes:
            continue
        pid = votes[0][0]
        if award == "mvp":
            mvp_pid = pid
        rec = {"season": league.season, "award": award, "pid": pid, "team": cands[pid]["team"],
               "votes": [[v[0], cands[v[0]]["team"], v[1], v[2]] for v in votes[:5]],
               "line": _compact_line(cands[pid]["s"])}
        if award == "cpoy":
            rec["kind"] = comeback[pid][0]
        league.awards["season"].append(rec)


def mvp_watch(league, week):
    """The media's MVP top five after a week (every other week from Week 6)."""
    if week < 6 or week % 2 or week >= _n_weeks(league) - 1:
        return
    if _done(league, "mvp_watch", season=league.season, week=week):
        return
    cands, teams = candidates(league, 1, week)
    rng = _rng(league, league.season, "watch", week)
    scored = _award_scores(league, "mvp", cands, teams, rng)
    story = {pid: rng.gauss(0, NARRATIVE_SD) for pid, _s in scored[:12]}
    top = sorted(scored[:12], key=lambda x: -(x[1] + story[x[0]]))[:5]
    def rec(tid):
        t = teams.get(tid, {})
        return [t.get("w", 0), t.get("l", 0), t.get("t", 0)]
    league.awards["mvp_watch"].append({"season": league.season, "week": week,
                                       "top": [[pid, cands[pid]["team"], _compact_line(cands[pid]["s"]),
                                                rec(cands[pid]["team"])] for pid, _s in top]})


# ---------------------------------------------------------------------------
# All-Pro
# ---------------------------------------------------------------------------

def all_pro(league):
    if _done(league, "all_pro", season=league.season):
        return
    cands, teams = candidates(league)
    rng = _rng(league, league.season, "allpro")
    taken = set()
    for spot, _label, n, pool_name in ALL_PRO_SPOTS:
        rows = [c for c in pool(cands, pool_name) if c["pid"] not in taken][:12]
        if not rows:
            continue
        base = {}
        mvp_case = dict(_award_scores(league, "mvp", cands, teams, rng)) if spot == "QB" else {}
        for c in rows:
            team = teams.get(c["team"], {})
            if c["pid"] in mvp_case:
                base[c["pid"]] = mvp_case[c["pid"]] / ALL_PRO_QB_SCALE
            else:
                base[c["pid"]] = c["perf"] + 0.5 * (team.get("pct", 0.5) - 0.5)
            base[c["pid"]] += REP_K * _reputation(league, c["pid"], league.season)
        story = {pid: rng.gauss(0, ALL_PRO_STORY) for pid in base}
        first = defaultdict(int)
        second = defaultdict(int)
        for _v in range(VOTERS):
            seen = sorted(base, key=lambda pid: -(base[pid] + story[pid] + rng.gauss(0, ALL_PRO_NOISE)))
            for pid in seen[:n]:
                first[pid] += 1
            for pid in seen[n:2 * n]:
                second[pid] += 1
        order1 = sorted(base, key=lambda pid: (-first[pid], -(3 * first[pid] + second[pid])))
        team1 = order1[:n]
        rest = [pid for pid in base if pid not in team1]
        team2 = sorted(rest, key=lambda pid: -(3 * first[pid] + second[pid]))[:n]
        taken.update(team1 + team2)           # one All-Pro spot per player
        for team_no, ids in ((1, team1), (2, team2)):
            for pid in ids:
                c = cands[pid]
                league.awards["all_pro"].append({"season": league.season, "team_no": team_no, "spot": spot,
                                                 "pid": pid, "team": c["team"], "firsts": first[pid],
                                                 "line": _compact_line(c["s"])})


# ---------------------------------------------------------------------------
# The Pro Bowl vote
# ---------------------------------------------------------------------------

def personality_strength(p):
    """How big a personality fans see (0-1): fame and leadership (PROVISIONAL)."""
    v = 0.7 * (p.popularity or 0) + 0.3 * (p.leadership or 0)
    return max(0.0, min(1.0, (v - 45) / 50))


def _shares(scores):
    if not scores:
        return {}
    top = max(scores.values())
    ex = {pid: math.exp((v - top) / VOTE_TEMP) for pid, v in scores.items()}
    tot = sum(ex.values())
    return {pid: v / tot for pid, v in ex.items()}


def _eligible(c, pool_name):
    if pool_name in ("K", "P", "LS", "RS", "ST"):
        return c["perf"] >= PRO_BOWL_MIN_PERF - (0.5 if pool_name in ("RS", "ST") else 0)
    return (c["share"] >= min(PRO_BOWL_MIN_SHARE, MIN_SHARE.get(c["p"].position, 1))
            and c["gp_share"] >= PRO_BOWL_MIN_GAMES and c["perf"] >= PRO_BOWL_MIN_PERF)


def pro_bowl_vote(league, last_week):
    """Fans, players and coaches vote (a third each): the rosters, starters
    and alternates for each conference."""
    if _done(league, "pro_bowl", season=league.season):
        return
    cands, teams = candidates(league, 1, last_week)
    rng = _rng(league, league.season, "probowl")
    for conf in conferences(league):
        conf_c = {pid: c for pid, c in cands.items() if c["conf"] == conf}
        taken = set()
        for spot, _label, n, starters, pool_name in PRO_BOWL_SPOTS:
            rows = [c for c in pool(conf_c, pool_name) if c["pid"] not in taken and _eligible(c, pool_name)]
            if len(rows) < n:
                # Too few qualify (a thin position, e.g. fullbacks who split the job):
                # the best of the rest who played most of the season.
                more = [c for c in conf_c.values() if pool_name in c["pools"] and c["pid"] not in taken
                        and c["gp_share"] >= PRO_BOWL_MIN_GAMES and c not in rows]
                rows += sorted(more, key=lambda c: -c["perf"])[:n - len(rows) + ALTERNATES]
            if not rows:
                continue
            special = pool_name in ("RS", "ST")
            fans, players, coaches = {}, {}, {}
            for c in rows[:20]:
                p = c["p"]
                team = teams.get(c["team"], {})
                wp = team.get("pct", 0.5) - 0.5
                rep = REP_K * _reputation(league, c["pid"], league.season)
                # Fans go by the numbers more; coaches by what they see on film.
                stat_z = c["perf"] if special else c["stat_z"]
                film_z = 0.0 if special else c["film_z"]
                f = FILM.get(p.position, 0.3)
                fan_perf = c["perf"] if f >= 1 or special else 0.85 * stat_z + 0.15 * film_z
                coach_perf = c["perf"] if f >= 1 or special else 0.45 * stat_z + 0.55 * film_z
                fame = FAN_FAME_K * ((p.popularity or 0) - 50) / 25
                boost = FAN_PERSONALITY_K * max(0.0, c["perf"]) * personality_strength(p)
                fans[c["pid"]] = fan_perf + fame + boost + FAN_TEAM_K * wp + rng.gauss(0, 0.25)
                players[c["pid"]] = c["perf"] + 2 * rep + 0.2 * wp + rng.gauss(0, 0.2)
                coaches[c["pid"]] = coach_perf + 2 * rep + 0.3 * wp + rng.gauss(0, 0.2)
            fs, ps, cs = _shares(fans), _shares(players), _shares(coaches)
            total = {pid: (fs[pid] + ps[pid] + cs[pid]) / 3 for pid in fans}
            order = sorted(total, key=lambda pid: -total[pid])
            fan_rank = {pid: i + 1 for i, pid in enumerate(sorted(fs, key=lambda pid: -fs[pid]))}
            for rank, pid in enumerate(order[:n + ALTERNATES], start=1):
                c = cands[pid]
                selected = rank <= n
                if selected:
                    taken.add(pid)
                league.awards["pro_bowl"].append({
                    "season": league.season, "conf": conf, "spot": spot, "pid": pid, "team": c["team"],
                    "rank": rank, "role": "selected" if selected else "alternate", "starter": rank <= starters,
                    "fan_share": round(fs[pid], 4), "player_share": round(ps[pid], 4),
                    "coach_share": round(cs[pid], 4), "fan_rank": fan_rank[pid], "case": round(c["perf"], 2),
                    "out": None, "added": False,
                    "replaces": None, "line": _compact_line(c["s"])})


def _unavailable(league, pid):
    from . import season as S
    if pid in getattr(league, "reserve", {}):
        return True
    p = _player(league, pid)
    if p is None or p.retired is not None:
        return True
    return S.injury_status(league, pid) in ("Out", "Doubtful", "Injured reserve", "Concussion protocol")


def pro_bowl_replacements(league):
    """Once the Glory Bowl teams are known: Glory Bowl players, injured
    players and players who choose not to play are replaced by alternates."""
    if _done(league, "notes", season=league.season, award="pb_replaced"):
        return
    rows = [r for r in league.awards["pro_bowl"] if r["season"] == league.season]
    if not rows:
        return
    glory = {po.winner(g) for g in league.playoffs if g["week"] == 3 and g["played"]}
    playing = {r["pid"] for r in rows if r["role"] == "selected"}

    def why_out(r):
        if _team_now(league, r["pid"], r["team"]) in glory or r["team"] in glory:
            return "glory_bowl"
        if _unavailable(league, r["pid"]):
            return "injured"
        p = _player(league, r["pid"])
        chance = min(DECLINE_MAX, DECLINE_BASE + DECLINE_PER_SEASON * max(0, p.experience - 5)
                     + (0.05 if p.position == "QB" else 0))
        if _rng(league, league.season, "decline", r["pid"]).random() < chance:
            return "declined"
        return None

    for conf in conferences(league):
        for spot, *_rest in PRO_BOWL_SPOTS:
            group = sorted((r for r in rows if r["conf"] == conf and r["spot"] == spot), key=lambda r: r["rank"])
            alts = [r for r in group if r["role"] == "alternate"]
            for r in [x for x in group if x["role"] == "selected"]:
                r["out"] = why_out(r)
                if not r["out"]:
                    continue
                while alts:
                    a = alts.pop(0)
                    if a["pid"] in playing:           # already going at another spot
                        continue
                    a_out = why_out(a)
                    if a_out:
                        a["out"] = a_out
                        continue
                    playing.add(a["pid"])
                    a["added"] = True
                    a["replaces"] = r["pid"]
                    a["starter"] = r["starter"]
                    break
                else:
                    # Out of alternates: the league goes further down the vote.
                    extra = _next_in_line(league, conf, spot, playing | {x["pid"] for x in group}, why_out)
                    if extra:
                        playing.add(extra["pid"])
                        group.append(extra)
                        league.awards["pro_bowl"].append(dict(extra, rank=max(x["rank"] for x in group) + 1,
                                                              replaces=r["pid"], starter=r["starter"]))
    league.awards["notes"].append({"season": league.season, "award": "pb_replaced", "text": ""})


def _next_in_line(league, conf, spot, skip, why_out):
    """The best player at a Pro Bowl spot who wasn't on the ballot's list:
    a record ready to add, or None."""
    pool_name = next(p for s, _l, _n, _st, p in PRO_BOWL_SPOTS if s == spot)
    cands, _teams = candidates(league, 1, _n_weeks(league) - 1)
    conf_c = {pid: c for pid, c in cands.items() if c["conf"] == conf}
    for c in pool(conf_c, pool_name) or sorted((c for c in conf_c.values() if pool_name in c["pools"]),
                                              key=lambda c: -c["perf"]):
        if c["pid"] in skip or c["gp_share"] < PRO_BOWL_MIN_GAMES:
            continue
        rec = {"season": league.season, "conf": conf, "spot": spot, "pid": c["pid"], "team": c["team"],
               "rank": 0, "role": "alternate", "starter": False, "fan_share": 0.0, "player_share": 0.0,
               "coach_share": 0.0, "fan_rank": 0, "case": round(c["perf"], 2), "out": None, "added": True,
               "replaces": None, "line": _compact_line(c["s"])}
        if not why_out(rec):
            return rec
    return None


def pro_bowl_roster(league, season=None):
    """{conference: [records of players who play in the Pro Bowl]}."""
    season = season or league.season
    out = defaultdict(list)
    for r in league.awards["pro_bowl"]:
        if r["season"] == season and ((r["role"] == "selected" and not r["out"]) or r["added"]):
            out[r["conf"]].append(r)
    return dict(out)


# ---------------------------------------------------------------------------
# The Pro Bowl game (never counts in any stats)
# ---------------------------------------------------------------------------

class _AllStars:
    """Just enough of a league for the game sim to play the two Pro Bowl teams."""

    def __init__(self, league, rosters):
        from .teams import Team
        self.season = league.season
        self.settings = league.settings
        self.teams = []
        for tid, conf in rosters:
            self.teams.append(Team(tid, conf, "Pro Bowl", conf[:4].upper(), conf, ""))
        self._rosters = {tid: players for (tid, _c), players in rosters.items()}
        self.players = [p for ps in self._rosters.values() for p in ps]
        self.depth_charts = {}
        self.captains = {}

    def team(self, tid):
        return next(t for t in self.teams if t.id == tid)

    def team_players(self, tid):
        return list(self._rosters[tid])


def play_pro_bowl(league):
    if _done(league, "pro_bowl_games", season=league.season):
        return
    roster = pro_bowl_roster(league)
    confs = conferences(league)
    if len(confs) != 2 or not all(roster.get(c) for c in confs):
        return
    from .sim.game import Game
    from .sim.norms import build_norms
    from .sim import weather as weather_mod
    ids = dict(zip(confs, PRO_BOWL_TEAM_IDS))
    teams = {(ids[c], c): [_player(league, r["pid"]) for r in roster[c]] for c in confs}
    teams = {k: [p for p in v if p is not None] for k, v in teams.items()}
    proxy = _AllStars(league, teams)
    rng = _rng(league, league.season, "pb-game")
    gb_site = po.glory_bowl_site(league)
    site = rng.choice([s for s in PRO_BOWL_SITES if s != gb_site])
    week = _n_weeks(league) + 4
    home, away = (ids[confs[0]], ids[confs[1]]) if league.season % 2 else (ids[confs[1]], ids[confs[0]])
    game = Game(proxy, home, away, seed=f"probowl-{league.settings.get('salt', '')}-{league.season}", week=week,
                norms=build_norms(league), weather=weather_mod.generate(site, league.season, week, rng),
                preseason={home: 3, away: 3}, neutral=True).run()
    # Injuries in the Pro Bowl never carry over (Blake, Oct 23): nothing from
    # game.injuries() is recorded.
    conf_of_id = {v: k for k, v in ids.items()}
    box = game.box
    idx_conf = [conf_of_id[home], conf_of_id[away]]
    players = {}
    for pid, line in box.players.items():
        if pid in box.owner:
            players[str(pid)] = {"conf": idx_conf[box.owner[pid]], **_compact_line(line)}
    score = {idx_conf[0]: game.state.score[0], idx_conf[1]: game.state.score[1]}
    winner = max(score, key=score.get) if score[confs[0]] != score[confs[1]] else None
    site_team = next((t for t in league.teams if t.abbrev == site), None)
    rec = {"season": league.season, "site": site_team.city if site_team else site, "home": idx_conf[0],
           "away": idx_conf[1], "score": score, "winner": winner, "overtime": bool(game.overtime),
           "weather": game.weather.text(), "players": players,
           "team": [_compact_line(box.team[0]), _compact_line(box.team[1])],
           "quarters": box.quarter_points,
           "scoring": [{"conf": idx_conf[s["team"]], "qtr": s["qtr"], "clock": s["clock"], "text": s["text"],
                        "score": list(s["score"])} for s in box.scoring]}
    # Game MVPs (offense and defense), usually from the winning side.
    best = {}
    for pid_s, line in players.items():
        p = _player(league, pid_s)
        if p is None:
            continue
        mult = 1.3 if line["conf"] == winner else 1.0
        grp = group_of(p.position)
        if grp in GAME_OFF_WEIGHT:
            v = off_value(line) * GAME_OFF_WEIGHT[grp] * mult
            if v > best.get("off", (0, None))[0]:
                best["off"] = (v, p.id)
        if grp in DEFENSE_GROUPS:
            v = def_value(line) * mult
            if v > best.get("def", (0, None))[0]:
                best["def"] = (v, p.id)
    rec["mvp_off"] = best.get("off", (0, None))[1]
    rec["mvp_def"] = best.get("def", (0, None))[1]
    league.awards["pro_bowl_games"].append(rec)


# ---------------------------------------------------------------------------
# Glory Bowl MVP
# ---------------------------------------------------------------------------

def glory_bowl_mvp(league):
    if _done(league, "gb_mvp", season=league.season):
        return
    g = next((x for x in league.playoffs if x["week"] == 5 and x["played"]), None)
    if g is None or g["id"] not in league.boxes:
        return
    win = po.winner(g)
    rng = _rng(league, league.season, "gbmvp")
    best = None
    for pid_s, line in league.boxes[g["id"]]["players"].items():
        p = _player(league, pid_s)
        if p is None:
            continue
        grp = group_of(p.position)
        v = 0.0
        if grp in GAME_OFF_WEIGHT:
            v = off_value(line) * (0.75 if grp == "QB" else 1.0)
        if grp in DEFENSE_GROUPS:
            v = max(v, def_value(line) * 2.2)
        v += kick_value(line) * 2 if p.position == "K" else 0
        v *= (1.6 if line["team"] == win else 0.6) * (1 + rng.gauss(0, 0.05))
        if best is None or v > best[0]:
            best = (v, p.id, line)
    if best:
        league.awards["gb_mvp"].append({"season": league.season, "pid": best[1], "team": best[2]["team"],
                                        "gid": g["id"], "line": _compact_line(best[2])})


# ---------------------------------------------------------------------------
# The calendar: called once at the end of every week (season.awards_week)
# ---------------------------------------------------------------------------

def _last_full_week(league):
    played = defaultdict(lambda: [0, 0])
    for g in league.schedule:
        played[g["week"]][0] += 1
        played[g["week"]][1] += bool(g["played"])
    done = [w for w, (n, p) in played.items() if n and n == p]
    w = 0
    while w + 1 in done:
        w += 1
    return w


def after_week(league):
    """Everything that's due after the week just played (and anything an
    older save missed): Players of the Week and Month, the MVP watch, the Pro
    Bowl vote, All-Pro, Pro Bowl replacements and game, the season awards and
    the Glory Bowl MVP."""
    from . import season as S
    ensure(league)
    if S.in_preseason(league):
        return
    n = _n_weeks(league)
    last = _last_full_week(league)
    for w in range(1, last + 1):
        players_of_the_week(league, w)
        mvp_watch(league, w)
        m = month_of_week(league, w)
        if w == n or month_of_week(league, w + 1) != m:
            players_of_the_month(league, m)
    if last >= n - 1:
        pro_bowl_vote(league, n - 1)
    if last >= n:
        all_pro(league)
    if S.in_playoffs(league) or S.season_over(league):
        conf_done = any(g["week"] == 3 and g["played"] for g in league.playoffs)
        if conf_done:
            pro_bowl_replacements(league)
        if conf_done and (league.playoff_round >= 4 or S.season_over(league)):
            play_pro_bowl(league)
            season_awards(league)
        glory_bowl_mvp(league)


# ---------------------------------------------------------------------------
# For screens and news
# ---------------------------------------------------------------------------

def seasons(league):
    ensure(league)
    return sorted({r["season"] for k in KEYS if k != "notes" for r in league.awards[k]}, reverse=True)


def winners(league, season):
    """{award: record} for one season's media awards."""
    return {r["award"]: r for r in records(league, "season", season)}


def player_honors(league, pid):
    """Every honor a player has won, newest first: [(season, sort, text)]."""
    ensure(league)
    a = league.awards
    out = []
    names = {k: name for k, name, _s in SEASON_AWARDS}
    first = league.settings.get("first_season", league.season)
    for r in a["season"]:
        if r["pid"] == pid:
            out.append((r["season"], 0, names[r["award"]]))
    for r in a["gb_mvp"]:
        if r["pid"] == pid:
            out.append((r["season"], 1, f"{po.CHAMPIONSHIP} {po.roman(r['season'] - first + 1)} MVP"))
    for r in a["all_pro"]:
        if r["pid"] == pid:
            out.append((r["season"], 2 + r["team_no"], f"All-Pro, {'first' if r['team_no'] == 1 else 'second'} "
                                                        f"team ({ALL_PRO_LABEL[r['spot']].lower()})"))
    for r in a["pro_bowl"]:
        if r["pid"] == pid and played_pro_bowl(r):
            extra = " (named as a replacement)" if r.get("added") else ""
            if r.get("out") == "glory_bowl":
                extra = f" (played in the {po.CHAMPIONSHIP} instead)"
            out.append((r["season"], 5, f"Pro Bowl{extra}"))
    for g in a["pro_bowl_games"]:
        for k, label in (("mvp_off", "Pro Bowl Offensive MVP"), ("mvp_def", "Pro Bowl Defensive MVP")):
            if g.get(k) == pid:
                out.append((g["season"], 6, label))
    months = defaultdict(list)
    for r in a["monthly"]:
        if r["pid"] == pid:
            kind = {"orook": "Offensive Rookie", "drook": "Defensive Rookie"}.get(r["kind"])
            label = (f"{kind} of the Month" if kind else
                     f"{r['conf']} Conference {WEEKLY_KINDS[r['kind']]} Player of the Month")
            months[(r["season"], label)].append(r["month"])
    for (season, label), ms in months.items():
        out.append((season, 7, f"{label} ({', '.join(ms)})"))
    weeks = defaultdict(list)
    for r in a["weekly"]:
        if r["pid"] == pid:
            weeks[(r["season"], f"{r['conf']} Conference {WEEKLY_KINDS[r['kind']]} Player of the Week")].append(r["week"])
    for (season, label), ws in weeks.items():
        out.append((season, 8, f"{label} (Week{'s' if len(ws) > 1 else ''} {', '.join(str(w) for w in ws)})"))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out


def honors_summary(league, pid):
    """'MVP (2027) · 2x All-Pro · 3x Pro Bowl · 4x Player of the Week', or ''."""
    ensure(league)
    a = league.awards
    bits = []
    for award, name, short in SEASON_AWARDS:
        yrs = [r["season"] for r in a["season"] if r["pid"] == pid and r["award"] == award]
        if yrs:
            bits.append(f"{short} ({', '.join(str(y) for y in sorted(yrs))})")
    gb = [r["season"] for r in a["gb_mvp"] if r["pid"] == pid]
    if gb:
        bits.append(f"{po.CHAMPIONSHIP} MVP ({', '.join(str(y) for y in gb)})")
    ap1 = sum(1 for r in a["all_pro"] if r["pid"] == pid and r["team_no"] == 1)
    ap2 = sum(1 for r in a["all_pro"] if r["pid"] == pid and r["team_no"] == 2)
    if ap1:
        bits.append(f"{ap1}x first-team All-Pro" if ap1 > 1 else "First-team All-Pro")
    if ap2:
        bits.append(f"{ap2}x second-team All-Pro" if ap2 > 1 else "Second-team All-Pro")
    pb = sum(1 for r in a["pro_bowl"] if r["pid"] == pid and played_pro_bowl(r))
    if pb:
        bits.append(f"{pb}x Pro Bowl" if pb > 1 else "Pro Bowl")
    pow_ = sum(1 for r in a["weekly"] if r["pid"] == pid)
    if pow_:
        bits.append(f"{pow_}x Player of the Week")
    return " · ".join(bits)
