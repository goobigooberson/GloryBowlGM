# depth.py
# Depth charts: who plays where, and who is on the field in each package.
#
# How it works, in plain terms:
#   - Every team has a list for each spot on the field (LT, WR1, RE, ...):
#     the starter first, then backups in order.
#   - A "package" is a group of spots used together. 11 personnel uses one
#     RB, one TE and three WRs; nickel defense swaps a linebacker for a
#     third cornerback. Packages pull players from the spot lists.
#   - If a player is already on the field (or injured, later), the game
#     moves down that spot's list to the next player.
#   - Any player can be put at any spot, but he plays worse away from his
#     own position (see rating_at).

from . import positions as pos

# ---------------------------------------------------------------------------
# Spots on the field
# spot: (label, natural position, unit)
# ---------------------------------------------------------------------------
SLOTS = {
    # Offense
    "QB":  ("Quarterback", "QB", "Offense"),
    "RB":  ("Running back", "RB", "Offense"),
    "RB3": ("3rd-down back", "RB", "Offense"),
    "FB":  ("Fullback", "FB", "Offense"),
    "WR1": ("Wide receiver 1", "WR", "Offense"),
    "WR2": ("Wide receiver 2", "WR", "Offense"),
    "WR3": ("Slot receiver", "WR", "Offense"),
    "WR4": ("Wide receiver 4", "WR", "Offense"),
    "TE1": ("Tight end 1", "TE", "Offense"),
    "TE2": ("Tight end 2", "TE", "Offense"),
    "TE3": ("Tight end 3", "TE", "Offense"),
    "LT":  ("Left tackle", "T", "Offense"),
    "LG":  ("Left guard", "G", "Offense"),
    "C":   ("Center", "C", "Offense"),
    "RG":  ("Right guard", "G", "Offense"),
    "RT":  ("Right tackle", "T", "Offense"),
    # Defense (base 4-3)
    "LE":  ("Left end", "DE", "Defense"),
    "LDT": ("Left tackle", "DT", "Defense"),
    "RDT": ("Right tackle", "DT", "Defense"),
    "RE":  ("Right end", "DE", "Defense"),
    "WLB": ("Weakside linebacker", "OLB", "Defense"),
    "MLB": ("Middle linebacker", "ILB", "Defense"),
    "SLB": ("Strongside linebacker", "OLB", "Defense"),
    "CB1": ("Cornerback 1", "CB", "Defense"),
    "CB2": ("Cornerback 2", "CB", "Defense"),
    "NB":  ("Nickel back", "CB", "Defense"),
    "DB":  ("Dime back", "CB", "Defense"),
    "FS":  ("Free safety", "S", "Defense"),
    "SS":  ("Strong safety", "S", "Defense"),
    # Special teams
    "K":   ("Kicker", "K", "Special teams"),
    "P":   ("Punter", "P", "Special teams"),
    "LS":  ("Long snapper", "LS", "Special teams"),
    "KR":  ("Kick returner", "KR", "Special teams"),
    "PR":  ("Punt returner", "PR", "Special teams"),
}

DEPTH_SIZE = 4          # starter + 3 backups per spot

# ---------------------------------------------------------------------------
# Packages: which spots are on the field together.
# Offensive personnel is named the standard way: first digit = running backs
# (RB + FB), second digit = tight ends. "11" = 1 back, 1 tight end, 3 WRs.
# ---------------------------------------------------------------------------
_OL = ["LT", "LG", "C", "RG", "RT"]
PACKAGES = {
    "11 personnel": ["QB", "RB", "TE1", "WR1", "WR2", "WR3"] + _OL,
    "12 personnel": ["QB", "RB", "TE1", "TE2", "WR1", "WR2"] + _OL,
    "21 personnel": ["QB", "RB", "FB", "TE1", "WR1", "WR2"] + _OL,
    "13 personnel": ["QB", "RB", "TE1", "TE2", "TE3", "WR1"] + _OL,
    "22 personnel": ["QB", "RB", "FB", "TE1", "TE2", "WR1"] + _OL,
    "10 personnel": ["QB", "RB", "WR1", "WR2", "WR3", "WR4"] + _OL,
    "Base 4-3":     ["LE", "LDT", "RDT", "RE", "WLB", "MLB", "SLB", "CB1", "CB2", "FS", "SS"],
    "Nickel":       ["LE", "LDT", "RDT", "RE", "WLB", "MLB", "CB1", "CB2", "NB", "FS", "SS"],
    "Dime":         ["LE", "LDT", "RDT", "RE", "MLB", "CB1", "CB2", "NB", "DB", "FS", "SS"],
}

# The spots that count as "starters" for roster screens.
STARTING_SPOTS = PACKAGES["11 personnel"] + PACKAGES["Base 4-3"] + ["K", "P", "LS"]

# Order the AI fills starting spots: most important first, so the best
# players land where they matter most (blind-side tackle, edge rusher...).
FILL_ORDER = [
    "QB", "LT", "RE", "CB1", "WR1", "LE", "C", "RT", "MLB", "FS", "RB", "TE1",
    "CB2", "WR2", "LDT", "RDT", "SS", "WLB", "SLB", "LG", "RG", "WR3", "NB",
    "TE2", "FB", "WR4", "DB", "TE3", "K", "P", "LS", "KR", "PR", "RB3",
]
assert set(FILL_ORDER) == set(SLOTS)

# Role spots: a list for a job, not a separate spot on the field. The 3rd-down
# back plays the running back spot on obvious passing downs (3rd or 4th and 5+,
# the two-minute drill). He can be the starting back himself, so the AI picks
# him after the starters instead of making him a different player.
ROLE_SPOTS = ("RB3",)

# A role spot is rated on the skills that job needs, not the position's
# overall. 3rd-down back (Blake): blocking and receiving drive it; picking up
# the blitz first, then catching the ball and running routes out of the
# backfield, plus making the first man miss in space.
SPOT_SKILLS = {
    "RB3": (("pass_block", 3), ("hands", 3), ("route_running", 3), ("elusiveness", 1)),
}

# AI: staffs like to keep their lead back fresh, so the best backup takes
# 3rd downs if he's at most this many points worse at the job than the
# starter (and of course if he's better). Set so the AI uses a different back
# on about a quarter of teams; injuries and rotation add more, toward the real
# NFL's third (2021-25: on 33% of teams the leading receiver among the backs
# wasn't the leading rusher).
THIRD_DOWN_BACKUP_WITHIN = 4

# ---------------------------------------------------------------------------
# How good a player is at a spot
# ---------------------------------------------------------------------------
# Penalties for playing away from what a player knows. "Now" penalties hit
# his current rating and shrink as he learns the spot (practice and games,
# later). "Ceiling" penalties are permanent and depend on his hidden
# adaptability: some players never fully get it back.
NEW_POSITION_NOW = 6          # a position he hasn't played
NEW_POSITION_CEILING = 4      # most a new position can cost his ceiling
SIDE_SWITCH_NOW = 5           # an offensive lineman flipping sides (like switching hands)
SIDE_SWITCH_CEILING = 2
UNTRAINED_TECHNIQUE = 12      # technique level, right now, for a skill he's never practiced
                              # (Oct 24: 25 -> 12. Real anchor: 2020 Broncos, WR Kendall Hinton at QB went 1 for 9;
                              # at 25 a receiver or back at QB still completed 47-48% for 4.6 a throw, now ~39% for 3.5)
LEARNABLE_TECHNIQUE = 0.75    # share of his usual ceiling he could reach in a new skill

# How much of a new position's craft a player brings from his own (Oct 24; Blake: "obviously not
# for like corner to safety but like DT to qb there should be a very noticeable fall off"): 0 = nothing
# in common (a receiver at tackle), 1 = the same job. It shrinks the size penalty (his skills already
# carry his size) and lets skills the related position partly shares start above UNTRAINED_TECHNIQUE.
# Tiers follow how often real players switch between the two (nflverse rosters 2010-25, switches per
# 1,000 player-seasons): ILB-OLB 97, C-G 80, DE-DT 78, G-T 70, DE-OLB 45 (real 3-4 OLBs are edge
# rushers; this game's OLB is an off-ball linebacker, so lower here), CB-S 20 (plus many more listed
# only as "DB"), RB-FB 15; then TE-WR 5, FB-TE 4, RB-TE 4, S-LB 3, RB-WR 3; DL-OL 2, DB-WR 1.6,
# QB-anything under 2. The numbers themselves are judgment.
RELATED = {
    frozenset(("CB", "S")): 0.7, frozenset(("G", "T")): 0.7, frozenset(("C", "G")): 0.7,
    frozenset(("ILB", "OLB")): 0.7, frozenset(("DE", "DT")): 0.7,
    frozenset(("C", "T")): 0.55, frozenset(("RB", "FB")): 0.5,
    frozenset(("DE", "OLB")): 0.35, frozenset(("TE", "FB")): 0.35, frozenset(("TE", "WR")): 0.35,
    frozenset(("S", "ILB")): 0.35, frozenset(("S", "OLB")): 0.35,
    frozenset(("RB", "WR")): 0.25, frozenset(("RB", "TE")): 0.25,
}


def related(a, b):
    """0-1: how much of position b's craft a player from position a already has."""
    return 1.0 if a == b else RELATED.get(frozenset((a, b)), 0.0)

# Which side of the line each offensive line spot is on.
SLOT_SIDE = {"LT": "L", "LG": "L", "RG": "R", "RT": "R"}


def _skill_value(p, skill, which, position=None):
    """His rating in a skill, now (which=0) or at his ceiling (which=1).
    If his position never trains it, estimate from raw athletic ability:
    very little technique now, more at his ceiling if he learns it. Playing a
    related position (position), some of the craft carries over (RELATED)."""
    if skill in p.skills:
        return p.skills[skill][which]
    _label, trait_weights = pos.SKILLS[skill]
    # Only a NEW position's craft carries over. At his own position an untrained skill (a
    # linebacker's ball skills, a safety's pass rush) stays untrained: related(own, own) is 1.0,
    # which briefly gave every linebacker in coverage his overall level as ball skills (Oct 24 bug:
    # league interceptions +8%).
    r = related(p.position, position) if position and position != p.position else 0.0
    own_now = [cur for cur, _pot in p.skills.values()]
    technique = UNTRAINED_TECHNIQUE + r * max(0.0, sum(own_now) / len(own_now) - UNTRAINED_TECHNIQUE)
    if which == 1:
        own = [pot for _cur, pot in p.skills.values()]
        technique = max(technique, LEARNABLE_TECHNIQUE * (sum(own) / len(own)))
    value = (1 - sum(trait_weights.values())) * technique
    for trait, w in trait_weights.items():
        value += w * p.athletic.get(trait, 50)
    return value


def spot_fit(p, slot):
    """How player p fits a spot: {"now": 1-99, "ceiling": 1-99, "notes": [...]}.
    notes explain any penalty in plain words."""
    position = SLOTS[slot][1]
    notes = []
    if position in ("KR", "PR"):
        skill = "kick_return" if position == "KR" else "punt_return"
        if skill in p.skills:
            cur, pot = p.skills[skill]
            return {"now": cur, "ceiling": pot, "notes": notes, "size": ""}
        return {"now": 15, "ceiling": 15, "notes": ["Not a return man"], "size": ""}

    now = ceiling = None
    if position == p.position and slot not in SPOT_SKILLS:
        now, ceiling = p.overall(), p.overall("potential")
    else:
        weights = SPOT_SKILLS.get(slot) or pos.POSITIONS[position][1]
        totals = [0.0, 0.0]
        weight_sum = 0
        for skill, w in weights:
            if w > 0:
                totals[0] += _skill_value(p, skill, 0, position) * w
                totals[1] += _skill_value(p, skill, 1, position) * w
                weight_sum += w
        now, ceiling = totals[0] / weight_sum, totals[1] / weight_sum
    close = related(p.position, position)
    if position != p.position:
        learned = p.learned.get(position, 0) / 100
        # (The same for every move. Oct 24, tried shrinking it for related positions: with CB-S or G-T
        # nearly free, AI depth charts started 408-634 of 2,976 starters out of position, vs 169.)
        now -= NEW_POSITION_NOW * (1 - learned)
        ceiling -= NEW_POSITION_CEILING * (1 - p.adaptability / 100)
        notes.append(f"Out of position (a {p.position} playing {position})")

    # Offensive line: playing the other side.
    spot_side = SLOT_SIDE.get(slot)
    if spot_side and p.side in ("L", "R") and p.side != spot_side:
        learned = p.learned.get("side", 0) / 100
        now -= SIDE_SWITCH_NOW * (1 - learned)
        ceiling -= SIDE_SWITCH_CEILING * (1 - p.adaptability / 100)
        notes.append("Switching sides of the line")

    # Too light or too heavy for a NEW position. (At his own position, his
    # size is already built into his ratings: see SIZE_TRADEOFF in player.py.)
    _h, _hs, avg_w, w_spread = pos.BODY[position]
    off_size = abs(p.weight - avg_w) / w_spread
    size_note = ""
    if position != p.position and off_size > 1.5:
        # (At a related position his skills already carry his size: a light corner's run
        # defense and hitting are already lower, so the extra charge shrinks with RELATED.)
        cost = (off_size - 1.5) * 6 * (1 - close)
        now -= cost
        ceiling -= cost
        size_note = f"light for a {position}" if p.weight < avg_w else f"heavy for a {position}"
    elif position == p.position:
        size_note = p.build_note       # just a label: his ratings already include it

    now = max(1, min(99, round(now)))
    ceiling = max(now, min(99, round(ceiling)))
    return {"now": now, "ceiling": ceiling, "notes": notes, "size": size_note}


def rating_at(p, slot):
    """How well player p would play this spot right now, 1-99: spot_fit's "now",
    worked out on its own (Oct 22, for speed: AI depth charts ask this ~1,900
    times a team, and the ceiling half and the notes were thrown away). Same
    arithmetic in the same order as spot_fit, so the result is identical."""
    position = SLOTS[slot][1]
    if position in ("KR", "PR"):
        skill = "kick_return" if position == "KR" else "punt_return"
        return p.skills[skill][0] if skill in p.skills else 15
    if position == p.position and slot not in SPOT_SKILLS:
        now = p.overall()
    else:
        weights = SPOT_SKILLS.get(slot) or pos.POSITIONS[position][1]
        r = related(p.position, position) if position != p.position else 0.0
        own_now = [cur for cur, _pot in p.skills.values()]
        technique = UNTRAINED_TECHNIQUE + r * max(0.0, sum(own_now) / len(own_now) - UNTRAINED_TECHNIQUE)
        total = 0.0
        weight_sum = 0
        for skill, w in weights:
            if w > 0:
                if skill in p.skills:
                    value = p.skills[skill][0]
                else:                                   # as _skill_value(p, skill, 0, position)
                    _label, trait_weights = pos.SKILLS[skill]
                    value = (1 - sum(trait_weights.values())) * technique
                    for trait, tw in trait_weights.items():
                        value += tw * p.athletic.get(trait, 50)
                total += value * w
                weight_sum += w
        now = total / weight_sum
    close = related(p.position, position)
    if position != p.position:
        learned = p.learned.get(position, 0) / 100
        now -= NEW_POSITION_NOW * (1 - learned)
    spot_side = SLOT_SIDE.get(slot)
    if spot_side and p.side in ("L", "R") and p.side != spot_side:
        learned = p.learned.get("side", 0) / 100
        now -= SIDE_SWITCH_NOW * (1 - learned)
    _h, _hs, avg_w, w_spread = pos.BODY[position]
    off_size = abs(p.weight - avg_w) / w_spread
    if position != p.position and off_size > 1.5:
        now -= (off_size - 1.5) * 6 * (1 - close)
    return max(1, min(99, round(now)))


# ---------------------------------------------------------------------------
# AI: build a depth chart
# ---------------------------------------------------------------------------

# How much each starting spot matters when the AI arranges a unit. Higher =
# the AI works harder to put a strong player there (the blind-side tackle
# and the right end, who usually faces the QB's blind side, matter most).
SLOT_IMPORTANCE = {
    "QB": 3.0, "RB": 1.0, "FB": 0.4, "WR1": 1.2, "WR2": 1.1, "WR3": 1.0, "WR4": 0.4,
    "TE1": 1.0, "TE2": 0.6, "TE3": 0.2,
    "LT": 1.3, "LG": 1.0, "C": 1.1, "RG": 1.0, "RT": 1.1,
    "LE": 1.1, "LDT": 1.0, "RDT": 1.0, "RE": 1.3,
    "WLB": 1.0, "MLB": 1.1, "SLB": 0.9,
    "CB1": 1.2, "CB2": 1.1, "NB": 0.8, "DB": 0.4, "FS": 1.05, "SS": 1.0,
    "K": 1.0, "P": 1.0, "LS": 1.0,
}


def _arrange_unit(slots, players, rating):
    """Pick starters for a unit's spots so the unit as a whole is as strong
    as possible: start with the obvious choices, then keep trying swaps
    (between spots, or with a bench player) while the unit gets better."""
    assigned = {}
    used = set()
    for slot in slots:                      # first pass: best available, in order
        options = [p for p in players if p.id not in used]
        if not options:
            break
        best = max(options, key=lambda p: rating(p, slot))
        assigned[slot] = best
        used.add(best.id)

    def gain(slot, old, new):
        return SLOT_IMPORTANCE[slot] * (rating(new, slot) - rating(old, slot))

    improved = True
    while improved:
        improved = False
        filled = list(assigned)
        # Swap two spots' starters.
        for i, a in enumerate(filled):
            for b in filled[i + 1:]:
                pa, pb = assigned[a], assigned[b]
                if gain(a, pa, pb) + gain(b, pb, pa) > 0.01:
                    assigned[a], assigned[b] = pb, pa
                    improved = True
        # Replace a starter with a bench player.
        for slot in filled:
            current = assigned[slot]
            for p in players:
                if p.id in used:
                    continue
                if gain(slot, current, p) > 0.01:
                    used.discard(current.id)
                    used.add(p.id)
                    assigned[slot] = current = p
                    improved = True
    return {slot: p.id for slot, p in assigned.items()}


def auto_depth_chart(players, pick_of=None):
    """The AI's depth chart for a roster: {spot: [player ids, starter first]}.
    pick_of: {player id: overall draft pick} for AI teams' charts: staffs give
    their recent high picks a real chance (draft.draft_capital; without it 15%
    of top-5 picks never started, real 2%). None (your chart): no nudge."""
    cache = {}
    if pick_of is not None:
        from .draft import draft_capital

    def rating(p, slot):
        key = (p.id, slot)
        if key not in cache:
            cache[key] = rating_at(p, slot) + (draft_capital(p, pick_of.get(p.id)) if pick_of is not None else 0.0)
        return cache[key]

    starting_in = {}           # player id -> unit he starts for (in the base packages)
    chart = {slot: [] for slot in SLOTS}
    base = set(STARTING_SPOTS)

    # Starters, arranged unit by unit (returners are chosen afterwards).
    for unit in ("Offense", "Defense", "Special teams"):
        slots = [s for s in FILL_ORDER if SLOTS[s][2] == unit and s not in ("KR", "PR") and s not in ROLE_SPOTS]
        for slot, pid in _arrange_unit(slots, players, rating).items():
            chart[slot] = [pid]
            # Only base-package starters (11 personnel, base 4-3, K/P/LS) are kept off other
            # spots' backup lists. Situational starters (2nd and 3rd TE, 4th WR, fullback,
            # nickel and dime backs) back up the base spots too: before Oct 23 they didn't, so
            # when the top TE needed a breather a running back or receiver came in (TE spots
            # were 15% non-TEs; real teams' TE2 plays 39% of snaps, the game's 27%).
            if slot in base:
                starting_in[pid] = unit

    # Returners: teams avoid risking key starters, so prefer non-starters.
    for slot in ("KR", "PR"):
        bench = [p for p in players if p.id not in starting_in]
        pool = bench if bench and max(rating(p, slot) for p in bench) >= 45 else players
        best = max(pool, key=lambda p: rating(p, slot))
        chart[slot] = [best.id]

    # Backups: the best remaining players for each spot, skipping that
    # unit's other starters so backups are real bench players.
    for slot in FILL_ORDER:
        if slot in ROLE_SPOTS:
            continue
        unit = SLOTS[slot][2]
        taken = set(chart[slot])
        bench = [p for p in players
                 if p.id not in taken and (starting_in.get(p.id) != unit or unit == "Special teams")]
        # Offensive spots are backed up by offensive players and defensive spots
        # by defensive players (NFL teams almost never play two ways).
        if unit in ("Offense", "Defense"):
            same = [p for p in bench if unit_of_position(p.position) == unit]
            if same:
                bench = same
        bench.sort(key=lambda p: rating(p, slot), reverse=True)
        chart[slot] += [p.id for p in bench[:DEPTH_SIZE - 1]]
    chart["RB3"] = third_down_backs(players, chart, rating)
    return chart


def third_down_backs(players, chart, rating=None):
    """The AI's 3rd-down back list: the best backup at the job takes it if he's
    within THIRD_DOWN_BACKUP_WITHIN points of the starting back (staffs keep
    the lead back fresh), otherwise the starter keeps it; then the other
    backs, best first. Only backs (RB/FB): a staff doesn't plan to put a
    receiver there, though you can."""
    rating = rating or rating_at
    backs = [p for p in players if p.position in ("RB", "FB")]
    if not backs:
        return []
    backs.sort(key=lambda p: rating(p, "RB3"), reverse=True)
    by_id = {p.id: p for p in players}
    starter = by_id.get((chart.get("RB") or [None])[0])
    first = backs[0]
    if starter is not None and starter.position in ("RB", "FB"):
        others = [p for p in backs if p.id != starter.id]
        first = starter
        if others and rating(others[0], "RB3") >= rating(starter, "RB3") - THIRD_DOWN_BACKUP_WITHIN:
            first = others[0]
    return [first.id] + [p.id for p in backs if p.id != first.id][:DEPTH_SIZE - 1]


def fill_missing_spots(chart, players):
    """Charts saved before a spot existed (the 3rd-down back, Oct 21): the
    AI's pick fills it. Changes nothing that's already set."""
    if not chart.get("RB3"):
        chart["RB3"] = third_down_backs(players, chart)
    return chart


# ---------------------------------------------------------------------------
# Who is on the field
# ---------------------------------------------------------------------------

def on_field(chart, package, unavailable=frozenset()):
    """{spot: player id} for a package. Walks down each spot's list past
    players who are already on the field or unavailable (injured, later).
    A spot is None if nobody on its list can play it."""
    used = set()
    result = {}
    for slot in PACKAGES[package]:
        result[slot] = None
        for pid in chart.get(slot, []):
            if pid not in used and pid not in unavailable:
                result[slot] = pid
                used.add(pid)
                break
    return result


def unit_of_position(position):
    """Offense, Defense or Special teams for a roster position (QB, DE, K...)."""
    for _slot, (_label, natural, unit) in SLOTS.items():
        if natural == position:
            return unit
    return "Offense"


# ---------------------------------------------------------------------------
# Captains
# ---------------------------------------------------------------------------
CAPTAIN_MAX_BOOST = 1.0   # most a captain adds to his unit, in rating points


def captain_boost(leadership):
    """A very small lift a captain gives his unit in games: nothing for an
    average leader (50 or below), up to +1 rating point for the best."""
    return max(0.0, (leadership - 50) / 50) * CAPTAIN_MAX_BOOST


def starter_ids(chart):
    """Players who start in the base packages (11 personnel, base 4-3, K, P, LS)."""
    ids = set()
    ids.update(v for v in on_field(chart, "11 personnel").values() if v)
    ids.update(v for v in on_field(chart, "Base 4-3").values() if v)
    for slot in ("K", "P", "LS"):
        if chart.get(slot):
            ids.add(chart[slot][0])
    return ids


def problems(chart, players):
    """Plain-language warnings about a depth chart."""
    by_id = {p.id: p for p in players}
    notes = []
    for package in PACKAGES:
        empty = [s for s, pid in on_field(chart, package).items() if pid is None]
        if empty:
            notes.append(f"{package}: no one available at {', '.join(empty)}.")
    first_listed = {}
    for slot in SLOTS:
        ids = chart.get(slot, [])
        unit = SLOTS[slot][2]
        if ids and unit != "Special teams" and slot in STARTING_SPOTS:
            first_listed.setdefault((unit, ids[0]), []).append(slot)
    for (unit, pid), slots in first_listed.items():
        if len(slots) > 1 and pid in by_id:
            notes.append(f"{by_id[pid].name} is listed as the starter at {' and '.join(slots)}. "
                         f"In games he plays {slots[0]}, and the next man down fills the other spot.")
    for slot in ("K", "P", "LS"):
        if not chart.get(slot):
            notes.append(f"No {SLOTS[slot][0].lower()} listed.")
    gone = sorted({pid for ids in chart.values() for pid in ids if pid not in by_id})
    if gone:
        notes.append(f"{len(gone)} listed player(s) are no longer on the roster.")
    return notes
