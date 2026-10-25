# scale.py
# The rating scale players see (Blake, Oct 21: "median NFL player = 50").
#
# The engine keeps its own internal ratings: the game sim, development, the
# draft and every tuning number were calibrated on them, and the sim only
# compares players to the league's average starter, so those internal
# numbers never need to change. Screens show every rating (skills, overall,
# potential, ratings history, depth chart fit) through shown() below, so:
#   - the typical NFL player shows about 50 (internal ~57; Oct 25: ~50 in a new
#     league, ~53 in one that has run many seasons, was ~56)
#   - an average starter shows about 62, backups high 30s to low 40s
#   - top ratings are rare (Oct 24, "FOF8-rare", see _TOP): the league's top
#     ~15-25 players show 80+, a few show 90+, 95+ is almost never seen
#     (measured Oct 25: 80+ about 20-22 a league, 90+ about 3-4)
# One curve for every position, so positions keep their differences
# (QBs are the scarcest; most kickers still read "Good").
#
# The middle of the curve (internal 45-92) comes from the real spread of
# rostered players' overall ratings in 8 generated leagues (every position but
# K/P/LS, which have their own curve below)
# (tools/build_rating_scale.py); below 45 it continues one point per point
# (weak individual skills still read "Very Bad", not negative), and above 92
# it runs straight to 99 so the very best skills don't all pile up at 99.

# Shown value for internal ratings 45..92, from tools/build_rating_scale.py.
# Rebuilt Oct 22 after veterans in new leagues started out aged (player.py,
# development.pre_age): the typical rostered player was internal ~54 (was ~57).
# Rebuilt Oct 25 after new leagues' young players were made as developed as drafted
# ones (player.NEW_LEAGUE_READY): a new league now looks like one that has run for
# years (before, the shown median drifted from ~50 to ~55-57 over the first seasons),
# and the typical rostered player is internal ~57 in both.
_MIDDLE = {
    45: 23.2, 46: 26.9, 47: 30.1, 48: 33.0, 49: 35.5, 50: 37.8, 51: 39.9, 52: 42.0, 53: 44.0, 54: 45.7,
    55: 47.4, 56: 49.0, 57: 50.4, 58: 51.8, 59: 53.0, 60: 54.2, 61: 55.4, 62: 56.4, 63: 57.4, 64: 58.4,
    65: 59.4, 66: 60.3, 67: 61.3, 68: 62.2, 69: 63.1, 70: 64.0, 71: 64.9, 72: 65.8, 73: 66.6, 74: 67.5,
    75: 68.4, 76: 69.4, 77: 70.4, 78: 71.3, 79: 72.3, 80: 73.3, 81: 74.4, 82: 75.7, 83: 77.2, 84: 78.7,
    85: 80.3, 86: 82.0, 87: 83.8, 88: 85.5, 89: 87.4, 90: 89.9, 91: 92.3, 92: 94.2,
}
_LOW, _HIGH = 45, 92
# The Oct 22 middle, kept for legacy_shown() (hidden judgments tuned on it).
_LEGACY_MIDDLE = {
    45: 31.4, 46: 33.9, 47: 36.3, 48: 38.6, 49: 40.7, 50: 42.7, 51: 44.5, 52: 46.2, 53: 47.9, 54: 49.5,
    55: 51.0, 56: 52.4, 57: 53.7, 58: 55.0, 59: 56.2, 60: 57.4, 61: 58.5, 62: 59.7, 63: 60.8, 64: 61.7,
    65: 62.7, 66: 63.6, 67: 64.6, 68: 65.5, 69: 66.5, 70: 67.3, 71: 68.1, 72: 69.0, 73: 69.8, 74: 70.5,
    75: 71.4, 76: 72.4, 77: 73.3, 78: 74.2, 79: 75.2, 80: 76.2, 81: 77.4, 82: 78.5, 83: 79.6, 84: 81.0,
    85: 82.4, 86: 84.1, 87: 86.0, 88: 87.8, 89: 89.6, 90: 91.7, 91: 94.1, 92: 96.7,
}


def _base_exact(internal, middle=_MIDDLE):
    """The middle curve (internal -> shown, unrounded), before the top is
    stretched. legacy_shown() uses the Oct 22 middle."""
    v = float(internal)
    if v <= _LOW:
        x = middle[_LOW] - (_LOW - v)
    elif v >= _HIGH:
        x = middle[_HIGH] + (v - _HIGH) * (99 - middle[_HIGH]) / (99 - _HIGH)
    else:
        a = int(v)
        x = middle[a] + (middle[a + 1] - middle[a]) * (v - a) if a < _HIGH else middle[a]
    return max(1.0, min(99.0, x))


# ---- Top ratings rare, FOF8-style (Blake, Oct 24: "i want higher ratings to feel
# more rare and special and much less common. in fof8 it is extremely rare to have a
# 90+qb"; he picked "FOF8-rare"). Display only, like the rest of this file: below 70
# nothing changes (the median player stays 50); above it the Oct 22 curve's values
# are stretched through these points (Oct 22 shown -> shown now). Measured Oct 24
# on 6 leagues (fresh and 1-5 seasons in; scratchpad rating_ranks.py), every
# rostered player: before, ~50 showed 80+, ~11-15 showed 90+, and a new league could
# open with four QBs at 96-97 (the top of the old curve packed internal 92-95 into
# 96.7-97.7). Now 80+ is internal 88 and up (the league's top ~15-25), 90+ is 93 and
# up (about 0-5 a league, ~2 on average), 95+ needs internal 96, higher than any
# player measured (only a generational player at his best could get there).
# (Oct 25: the middle was rebuilt, so these points were moved to the same internal
# ratings as before: 80+ still starts at internal 88, 90+ at 93, 95+ at 96. Oct 24's
# points on the Oct 22 curve were (69.8, 69.8), (87.8, 80.0), (96.7, 88.0), (97.0, 90.0),
# (97.4, 92.0), (97.7, 94.0), (98.0, 95.5), (99.0, 99.0).)
_TOP = [(66.6, 66.6), (85.5, 80.0), (94.2, 88.0), (94.83, 90.0), (95.66, 92.0), (96.29, 94.0),
        (96.91, 95.5), (99.0, 99.0)]


def _stretch(x):
    if x <= _TOP[0][0]:
        return x
    for (a, fa), (b, fb) in zip(_TOP, _TOP[1:]):
        if x <= b:
            return fa + (fb - fa) * (x - a) / (b - a)
    return _TOP[-1][1]


def shown_exact(internal):
    """Internal rating (any number) -> shown rating, unrounded."""
    return _stretch(_base_exact(internal))


# Lookup for whole numbers (what the screens use almost always).
_TABLE = [round(shown_exact(v)) for v in range(101)]
_BASE_TABLE = [round(_base_exact(v, _LEGACY_MIDDLE)) for v in range(101)]

# Kickers, punters and long snappers (Blake, Oct 21): rated among their own
# kind. A starting specialist at a given rank among starting specialists shows
# what a starter at that rank among all other starters shows (a typical
# starting kicker ~61, the league's best few 80+). On the main curve their
# much higher internal numbers took about a third of the 80+ spots.
# From tools/build_rating_scale.py (internal 0..100 -> shown; rebuilt Oct 25 with the main curve).
SPECIALISTS = ("K", "P", "LS")
_SPECIALIST = [
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 4.0, 5.5, 7.0,
    8.5, 10.0, 11.5, 13.0, 14.5, 16.0, 17.5, 19.0, 20.5, 22.0,
    23.5, 25.0, 26.5, 28.0, 29.5, 31.0, 32.5, 34.0, 35.5, 37.0,
    38.5, 40.0, 44.0, 46.0, 49.0, 49.0, 50.0, 52.0, 53.0, 54.0,
    55.0, 56.0, 57.0, 58.0, 59.0, 59.0, 60.0, 61.0, 62.0, 62.0,
    63.0, 64.0, 65.0, 66.0, 67.0, 67.0, 68.0, 69.0, 70.0, 71.0,
    72.0, 74.0, 75.0, 78.0, 79.0, 82.0, 84.0, 88.0, 89.5, 91.0,
    92.5,
]
# The Oct 22 specialist curve, kept for legacy_shown().
_LEGACY_SPECIALIST = [
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    1.0, 1.0, 1.0, 1.0, 2.5, 4.0, 5.5, 7.0, 8.5, 10.0,
    11.5, 13.0, 14.5, 16.0, 17.5, 19.0, 20.5, 22.0, 23.5, 25.0,
    26.5, 28.0, 29.5, 31.0, 39.0, 41.0, 43.0, 43.0, 44.5, 46.0,
    48.0, 50.0, 50.0, 51.0, 51.0, 52.0, 54.0, 55.0, 56.0, 57.0,
    57.0, 58.0, 60.0, 61.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0,
    66.0, 66.0, 66.0, 67.0, 68.0, 69.0, 70.0, 70.0, 72.0, 73.0,
    75.0, 77.0, 80.0, 82.0, 84.0, 88.0, 92.0, 94.5, 97.0, 98.5,
    99.0,
]


def _special(internal, table=None):
    table = table or _SPECIALIST
    v = max(0.0, min(100.0, float(internal)))
    a = int(v)
    if a >= 100:
        return table[100]
    return table[a] + (table[a + 1] - table[a]) * (v - a)


def shown(internal, position=None):
    """Internal rating -> the whole-number rating shown on screen (1-99).
    position: the player's position (or the spot's), so kickers, punters and
    snappers use their own curve."""
    if position in SPECIALISTS and _SPECIALIST is not None:
        return max(1, min(99, round(_stretch(_special(internal)))))
    if isinstance(internal, int) and 0 <= internal <= 100:
        return _TABLE[internal]
    return round(shown_exact(internal))


def legacy_shown(internal, position=None):
    """The Oct 22 scale, before top ratings were made rarer. Never shown on a
    screen: only for hidden judgments tuned on it (award voters' "film", which
    players the news treats as notable or stars), so they behave as tuned."""
    if position in SPECIALISTS and _SPECIALIST is not None:
        return max(1, min(99, round(_special(internal, _LEGACY_SPECIALIST))))
    if isinstance(internal, int) and 0 <= internal <= 100:
        return _BASE_TABLE[internal]
    return round(_base_exact(internal, _LEGACY_MIDDLE))


def seen(league, p, which="current", skill=None, viewer="user"):
    """The rating a screen shows for a player: his overall (or one skill),
    current or potential ("potential"), as YOUR staff evaluates him (Blake,
    Oct 24: every rating you see is your staff's evaluation; evaluation.py).
    viewer: a team id, "user" (your team) or None (the public view: what the
    league as a whole believes, used before you have a team)."""
    from . import evaluation
    tid = league.user_team_id if viewer == "user" else viewer
    if tid is None:
        skills = evaluation.public_skills(league, p)
    else:
        skills = evaluation.seen_skills(league, tid, p)
    index = 0 if which == "current" else 1
    if skill is not None:
        return shown(skills[skill][index], p.position)
    from . import positions as pos
    total = wsum = 0.0
    for s, w in pos.POSITIONS[p.position][1]:
        if w > 0:
            total += skills[s][index] * w
            wsum += w
    return shown(total / wsum if wsum else 0.0, p.position)


def internal(shown_value):
    """The lowest internal rating that shows as at least this value (for
    turning a shown-scale cutoff, e.g. 'shows 80+', into the engine's)."""
    for v in range(101):
        if _TABLE[v] >= shown_value:
            return v
    return 101
