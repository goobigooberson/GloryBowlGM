# roster_rules.py
# How a roster has to be built, so no team (yours or the AI's) ends up with
# a strange mix, like two quarterbacks and nine receivers.
#
#   - Up to 53 players on the roster.
#   - Real NFL rules (since 2020; Blake, Oct 22: "switch game day to the real
#     NFL's 48 actives"): 48 are "active" on game day if at least 8 of them are
#     offensive linemen, otherwise 47 (real teams dress 48 nearly every week:
#     nflverse 2022-25, 48.0 active, 6.3 inactive a team-week). Elevated
#     practice squad players count toward it.
#   - Emergency third quarterback (since 2023): a team may also name a third
#     QB from its inactive players; he can come in only if both active QBs
#     are out for the game (emergency_qb below; the game sim applies it).
#   - The actives must include a minimum at each position and position
#     group (below), so a team can always field every package and survive
#     an injury or two during a game.
#
# These minimums are this game's own, based on how NFL teams typically
# dress for games. Change them here.

from . import depth

ROSTER_LIMIT = 53
# Training camp (Blake, Oct 23: "late free agency, then training camp, then preseason, then
# the cuts"; the modern NFL): from the end of the offseason until final cuts, teams carry up
# to 90 players. Since 2023 there's one cut-down, to 53, after the last preseason game.
CAMP_LIMIT = 90
# A 90-man camp roster by position (judgment call from typical real camp rosters: about 1.7x
# the 53-man counts, more at positions where camp battles are common, one long snapper).
# Teams fill toward this shape; nothing forces it.
CAMP_TEMPLATE = {"QB": 4, "RB": 5, "FB": 2, "TE": 5, "WR": 12, "T": 7, "G": 6, "C": 3,
                 "DE": 8, "DT": 7, "OLB": 6, "ILB": 5, "CB": 10, "S": 6, "K": 2, "P": 1, "LS": 1}
ACTIVE_LIMIT = 48              # with 8+ offensive linemen active
ACTIVE_LIMIT_FEW_OL = 47        # otherwise
OL_FOR_FULL_LIMIT = 8
_OL = ("C", "G", "T")

# Rows of the position counts table, in order. Each row:
#   (label, positions it counts, minimum active on game day, is it a group?)
ROWS = [
    ("Quarterbacks",            ["QB"],                         2, False),
    ("Running backs",           ["RB"],                         2, False),
    ("Fullbacks",               ["FB"],                         0, False),
    ("Backfield (RB/FB)",       ["RB", "FB"],                   3, True),
    ("Tight ends",              ["TE"],                         2, False),
    ("Wide receivers",          ["WR"],                         4, False),
    ("Skill positions (RB/FB/TE/WR)", ["RB", "FB", "TE", "WR"], 10, True),
    ("Centers",                 ["C"],                          1, False),
    ("Guards",                  ["G"],                          2, False),
    ("Tackles",                 ["T"],                          2, False),
    ("Offensive line (C/G/T)",  ["C", "G", "T"],                7, True),
    ("Defensive ends",          ["DE"],                         3, False),
    ("Defensive tackles",       ["DT"],                         2, False),
    ("Defensive line (DE/DT)",  ["DE", "DT"],                   6, True),
    ("Outside linebackers",     ["OLB"],                        2, False),
    ("Inside linebackers",      ["ILB"],                        1, False),
    ("Linebackers (OLB/ILB)",   ["OLB", "ILB"],                 4, True),
    ("Defensive front (DL/LB)", ["DE", "DT", "OLB", "ILB"],     11, True),
    ("Cornerbacks",             ["CB"],                         4, False),
    ("Safeties",                ["S"],                          2, False),
    ("Secondary (CB/S)",        ["CB", "S"],                    7, True),
    ("Kickers",                 ["K"],                          1, False),
    ("Punters",                 ["P"],                          1, False),
    ("Long snappers",           ["LS"],                         1, False),
]


def count(players, positions):
    return sum(p.position in positions for p in players)


def distribution(roster, active_ids):
    """The position counts table: a list of dicts with label, active,
    required, on_roster, is_group and short (True if below the minimum)."""
    active = [p for p in roster if p.id in active_ids]
    table = []
    for label, positions, required, is_group in ROWS:
        n_active = count(active, positions)
        table.append({"label": label, "positions": positions, "active": n_active,
                      "required": required, "on_roster": count(roster, positions),
                      "is_group": is_group, "short": n_active < required})
    limit = active_limit(active)
    table.append({"label": "Total", "positions": [], "active": len(active),
                  "required": limit, "on_roster": len(roster), "is_group": True,
                  "short": len(active) < limit})
    return table


def active_limit(players):
    """48 on game day with 8+ offensive linemen among them, else 47."""
    return ACTIVE_LIMIT if count(players, _OL) >= OL_FOR_FULL_LIMIT else ACTIVE_LIMIT_FEW_OL


def meets_minimums(players):
    return all(count(players, positions) >= required for _l, positions, required, _g in ROWS)


def game_day_actives(roster, chart, unavailable=frozenset(), rating=None):
    """Pick who dresses on game day: 48 with 8 offensive linemen among them
    (when 8 are healthy), else 47. Everyone healthy starts active; then the
    least-needed players are made inactive one at a time, never breaking a
    position minimum or leaving a starting spot empty (and keeping 8 linemen
    when there are 8). (Later you'll be able to set your own inactives;
    injured players are always inactive.) rating: how the team's staff rates
    a player (evaluation.overall; default his own overall), for ties."""
    rating = rating or (lambda p: p.overall())
    healthy = [p for p in roster if p.id not in unavailable]
    starters = depth.starter_ids(chart)
    keep_ol = count(healthy, _OL) >= OL_FOR_FULL_LIMIT
    limit = ACTIVE_LIMIT if keep_ol else ACTIVE_LIMIT_FEW_OL

    def need(p):
        """Higher = more needed on game day."""
        best_rank = min((ids.index(p.id) for ids in chart.values() if p.id in ids), default=9)
        return (p.id in starters, -best_rank, rating(p))

    active = list(healthy)
    for p in sorted(healthy, key=need):
        if len(active) <= limit:
            break
        if p.id in starters:
            continue
        trial = [x for x in active if x.id != p.id]
        if meets_minimums(trial) and (not keep_ol or count(trial, _OL) >= OL_FOR_FULL_LIMIT):
            active = trial
    return {p.id for p in active}


def emergency_qb(roster, actives, unavailable=frozenset(), rating=None):
    """The emergency third quarterback: the best healthy QB who isn't active
    (he can come in only if both active QBs are out for the game), or None.
    rating: as in game_day_actives."""
    rating = rating or (lambda p: p.overall())
    qbs = [p for p in roster if p.position == "QB" and p.id not in actives and p.id not in unavailable]
    return max(qbs, key=rating).id if qbs else None


def roster_problems(roster, active_ids, limit=ROSTER_LIMIT):
    """Plain-language problems with a roster, for screens and AI checks
    (limit: CAMP_LIMIT during training camp and the preseason)."""
    notes = []
    if len(roster) > limit:
        notes.append(f"Roster has {len(roster)} players; the limit is {limit}.")
    for row in distribution(roster, active_ids):
        if row["short"] and row["label"] != "Total":
            notes.append(f"{row['label']}: {row['active']} active, at least {row['required']} required.")
    active = [p for p in roster if p.id in active_ids]
    limit = active_limit(active)
    if len(active_ids) < limit and len(roster) >= limit:
        notes.append(f"Only {len(active_ids)} active players; teams dress {limit}.")
    return notes
