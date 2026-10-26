# plays.py
# Resolving a single play from the players on the field.
#
# Every play is built from matchups: each pass rusher against the man
# blocking him, each receiver against the defender covering him, the
# blockers at the hole against the defenders there, the ball carrier
# against the second level. Those matchups tilt the odds; the real NFL
# distributions in data.py supply the randomness. Nothing is decided ahead
# of time: a great offense usually wins the play, but not always.

import math
from bisect import bisect_right

from . import data
from . import tuning as T
from .coach import sigmoid, logit

Q = data.Q_STEPS


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def tilt(u, m):
    """Shift a random point u (0-1) up (m > 0) or down (m < 0) the distribution.
    The shift is in log-odds, so an edge of m multiplies the chance of a big
    play (top 1%) by about e^m: a +0.3 edge makes a 30-yard run about 35% more
    likely, not three times as likely."""
    if m == 0:
        return u
    u = min(max(u, 1e-9), 1.0 - 1e-9)
    x = math.log(u / (1.0 - u)) + m
    if x > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


# Calibration support: when RECORD is a dict, every matchup adjustment is
# logged by site so a calibration run can measure its league-wide average. Each site
# is then centered on that average (tuning.CENTER), so an average matchup
# reproduces the real NFL baseline and only the differences between players
# move results.
RECORD = None


def soft_cap(cap, x):
    """Diminishing returns: small edges count fully, huge stacked edges
    (a great QB throwing to a great receiver against a weak corner) can't
    push one play beyond about +/-cap."""
    return cap * math.tanh(x / cap)


def centered(site, m):
    if RECORD is not None:
        RECORD.setdefault(site, []).append(m)
    return m - T.CENTER.get(site, 0.0)


def qvalue(table, u, rng=None, tail=0.0):
    """Value at random point u in a real-NFL quantile table. Beyond the last
    point, extend with an exponential tail (for the rare very long play)."""
    if u <= Q[0]:
        return table[0]
    if u >= Q[-1]:
        if tail and rng is not None:
            return table[-1] + rng.expovariate(1.0 / tail)
        return table[-1]
    i = bisect_right(Q, u) - 1
    lo, hi = Q[i], Q[i + 1]
    f = (u - lo) / (hi - lo)
    return table[i] + f * (table[i + 1] - table[i])


_AIR_MID = []
_AIR_COMP = []
_AIR_INT = []
for lo, hi, share, comp, intr, yac in data.AIR_YARDS_TABLE:
    mid = -4.0 if lo < -50 else (45.0 if hi > 90 else (lo + hi) / 2 + 0.5)
    _AIR_MID.append(mid)
    _AIR_COMP.append(comp)
    _AIR_INT.append(intr)


def _interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x) - 1
    f = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + f * (ys[i + 1] - ys[i])


def field_squeeze(table, yl):
    """Near the goal line the field shrinks: defenders have less ground to
    cover. Returns the adjustment for this yard line from a tuning table of
    (yard line, adjustment) points."""
    if yl >= table[-1][0]:
        return table[-1][1]
    if yl <= table[0][0]:
        return table[0][1]
    for (y0, a0), (y1, a1) in zip(table, table[1:]):
        if y0 <= yl <= y1:
            return a0 + (a1 - a0) * (yl - y0) / (y1 - y0)
    return 0.0


def pass_down(st, hurry=False, cover=False):
    """How sure the defense is that a pass is coming (0 = it must respect the run, 1 = an
    obvious passing down), minus the league's average over dropbacks, so it moves passing
    between downs without moving it overall. Real NFL (nflverse 2023-25, neutral score):
    sacks 4.8% of dropbacks on 1st & 10 but 9-11% on 3rd & 3+; completions 69% vs 57-59%.
    cover: the coverage's level, which eases off on 3rd and very long (it gives up the
    underneath throw: real completions 66% on 3rd & 11+, while the rush still comes)."""
    if st.down >= 3:
        lvl = 1.0 if st.togo >= 3 else T.PASS_DOWN_SHORT
        if cover and st.togo >= 11:
            lvl = T.PASS_DOWN_LONG_COVER
    else:
        lvl = 0.0
    if hurry or (st.qtr >= 4 and st.score[1 - st.poss] - st.score[st.poss] >= 9):
        lvl = max(lvl, T.PASS_DOWN_CATCHUP)
    return lvl - (T.PASS_DOWN_CENTER_COVER if cover else T.PASS_DOWN_CENTER)


def marked_short(st, res, rng):
    """Defenders defend the line to gain: a run or catch that just reaches it is often marked a
    yard short. Real NFL (nflverse 2023-25): runs with 4-6 to go end 1 yard short 15.3% of the
    time, exactly at the sticks 3.7%, 1 past 7.1%; catches with 7-9 to go 10.4 / 3.3 / 7.4%.
    The sim's yards didn't know where the sticks were (10.8 / 8.2 / 6.1 and 5.9 / 5.6 / 5.9),
    so 2nd and 3rd & 1 came up too rarely (3rd & 1: 7.8% of 3rd downs vs real 12.1%)."""
    if not T.STICKS_SHORT or res.td or res.fumble or res.safety or res.yards != st.togo or st.togo >= st.yl:
        return
    if not (res.kind in ("run", "scramble") or (res.kind == "pass" and res.complete)):
        return
    if rng.random() < T.STICKS_SHORT:
        res.yards -= 1
        if res.kind == "pass":
            if res.yac >= 1:
                res.yac -= 1
            elif res.air_yards is not None:
                res.air_yards -= 1


def base_completion(air):
    return _interp(_AIR_MID, _AIR_COMP, air)


def base_interception(air):
    return _interp(_AIR_MID, _AIR_INT, air)


def pick(rng, items, weights=None):
    if not items:
        return None
    if weights is None:
        return items[int(rng.random() * len(items))]
    total = sum(weights)
    if total <= 0:
        return items[int(rng.random() * len(items))]
    r = rng.random() * total
    for item, w in zip(items, weights):
        r -= w
        if r <= 0:
            return item
    return items[-1]


# ---------------------------------------------------------------------------
# The result of one play
# ---------------------------------------------------------------------------

class PlayResult:
    def __init__(self, kind):
        self.kind = kind            # run, pass, sack, scramble, sneak, kneel, spike, punt, fg, xp,
                                    # two_point, kickoff, onside, penalty
        self.yards = 0
        self.passer = self.receiver = self.rusher = None
        self.target_slot = None
        self.tacklers = []          # (player) primary first
        self.assist = None
        self.sackers = []
        self.qb_hit_by = None
        self.tfl = False
        self.interceptor = None
        self.pd_by = None
        self.batted = False         # pass knocked down at the line
        self.forced_by = None
        self.recovered_by = None
        self.kicker = self.punter = self.returner = self.snapper = self.holder = None
        self.complete = False
        self.interception = False
        self.td = False
        self.def_td = False         # defense (or return team) scores
        self.safety = False
        self.fumble = False
        self.fumble_lost = False
        self.oob = False
        self.throwaway = False
        self.dropped = False
        self.hurried = False
        self.air_yards = None
        self.yac = 0
        self.direction = ""         # left, middle, right
        self.depth_word = ""        # short, deep
        self.gap = ""
        self.return_yards = 0
        self.kick_distance = 0
        self.made = False
        self.blocked = False
        self.touchback = False
        self.fair_catch = False
        self.downed = False
        self.muffed = False
        self.new_yl = None          # field position for the team that has the ball next (kicks, turnovers)
        self.change_poss = False
        self.penalty = None         # Penalty object from penalties.py
        self.no_play = False
        self.elapsed = 5
        self.desc = ""
        self.note = ""              # short "why" for the play-by-play
        self.injuries = []          # (team, player, description)
        self.on_field_off = set()
        self.on_field_def = set()
        self.two_point_good = False
        self.first_down = False
        # For the play-by-play detail line ("what happened on the field")
        self.pressure_by = None     # rusher who got pressure
        self.beat = None            # blocker he beat (None = came free)
        self.cover_def = None       # defender covering the target
        self.sep = None             # how open the target was (z units)
        self.block_edge = None      # run: blockers vs defenders at the hole
        self.bracket = None         # receiver the defense rolled extra coverage to

    def contact_players(self, rng):
        out = []
        for p in (self.rusher, self.receiver):
            if p is not None:
                out.append(p)
        out.extend(self.tacklers)
        if self.assist:
            out.append(self.assist)
        # Quarterbacks get hurt when they're sacked or hit as they throw.
        if self.passer is not None and self.kind == "sack":
            out.append(self.passer)
            out.extend(self.sackers)
        elif self.passer is not None and self.qb_hit_by is not None and rng.random() < 0.4:
            out.append(self.passer)
        return out


# ---------------------------------------------------------------------------
# Matchup tables (position vs position adjustments, in z units)
# ---------------------------------------------------------------------------

# Coverage: how a defender of one position matches up against a receiver of
# another. A linebacker on a wide receiver is a mismatch; a safety on a tight
# end is fine.
COVER_CLASS = {
    ("CB", "WR"): 0.0, ("CB", "TE"): 0.15, ("CB", "RB"): 0.30, ("CB", "FB"): 0.4,
    ("S", "WR"): -0.35, ("S", "TE"): 0.10, ("S", "RB"): 0.20, ("S", "FB"): 0.3,
    ("OLB", "WR"): -1.00, ("OLB", "TE"): -0.25, ("OLB", "RB"): -0.10, ("OLB", "FB"): 0.2,
    ("ILB", "WR"): -1.05, ("ILB", "TE"): -0.30, ("ILB", "RB"): -0.10, ("ILB", "FB"): 0.2,
}

# Pass rush: rusher position vs blocker position.
RUSH_CLASS = {
    ("DE", "TE"): 0.55, ("DE", "RB"): 0.85, ("DE", "FB"): 0.6,
    ("DT", "TE"): 0.6, ("DT", "RB"): 0.9,
    ("OLB", "RB"): 0.35, ("OLB", "TE"): 0.25, ("OLB", "FB"): 0.2,
    ("ILB", "RB"): 0.20, ("ILB", "TE"): 0.15, ("ILB", "FB"): 0.1,
    ("S", "RB"): 0.0, ("CB", "RB"): -0.1, ("S", "TE"): -0.1, ("CB", "TE"): -0.2,
}

COVER_PRIORITY = {
    "WR1": ["CB1", "CB2", "NB", "DB", "FS", "SS"],
    "WR2": ["CB2", "CB1", "NB", "DB", "SS", "FS"],
    "WR3": ["NB", "DB", "SS", "WLB", "SLB", "MLB", "FS", "CB2"],
    "WR4": ["DB", "NB", "SS", "FS", "WLB", "MLB", "SLB"],
    "TE1": ["SS", "SLB", "MLB", "WLB", "FS", "NB", "DB"],
    "TE2": ["SLB", "MLB", "WLB", "SS", "FS"],
    "TE3": ["MLB", "WLB", "SLB", "SS", "FS"],
    "RB": ["WLB", "MLB", "SLB", "SS", "NB", "DB"],
    "FB": ["MLB", "SLB", "WLB", "SS"],
}

ZONE_POOL = {
    "WR1": (["CB1", "NB", "WLB"], ["CB1", "SS", "WLB", "MLB"], ["CB1", "FS"]),
    "WR2": (["CB2", "NB", "SLB"], ["CB2", "SS", "SLB", "MLB"], ["CB2", "FS"]),
    "WR3": (["NB", "WLB", "SLB", "MLB", "DB"], ["NB", "SS", "MLB", "DB"], ["FS", "SS"]),
    "WR4": (["DB", "NB", "MLB", "WLB"], ["DB", "SS", "MLB"], ["FS", "SS"]),
    "TE": (["MLB", "SLB", "WLB", "SS"], ["SS", "MLB", "SLB"], ["FS", "SS"]),
    "RB": (["WLB", "MLB", "SLB"], ["MLB", "WLB", "SS"], ["FS", "SS"]),
}

RECEIVER_SLOTS = ("WR1", "WR2", "WR3", "WR4", "TE1", "TE2", "TE3", "RB", "FB")

# Which side of the field each receiver usually works (offense's view).
_DIRECTION = {
    "WR1": (("left", .82), ("middle", .18)),
    "WR2": (("right", .82), ("middle", .18)),
    "WR3": (("middle", .40), ("right", .34), ("left", .26)),
    "WR4": (("left", .45), ("middle", .25), ("right", .30)),
    "TE1": (("middle", .38), ("right", .40), ("left", .22)),
    "TE2": (("left", .45), ("middle", .30), ("right", .25)),
    "TE3": (("middle", .5), ("left", .25), ("right", .25)),
    "RB": (("left", .40), ("right", .40), ("middle", .20)),
    "FB": (("left", .35), ("right", .35), ("middle", .30)),
}


def natural(slot):
    from ..depth import SLOTS
    return SLOTS[slot][1]


# ---------------------------------------------------------------------------
# Pass plays
# ---------------------------------------------------------------------------

DL_SLOTS = ("LE", "LDT", "RDT", "RE")
# Which offensive blocker each defensive lineman faces (offense's left tackle
# faces the defense's right end, and so on).
DL_MATCH = {"RE": "LT", "LE": "RT", "RDT": "LG", "LDT": "RG"}


def _rush_score(team, p, slot):
    if slot in DL_SLOTS:
        return team.zmix(p, slot, {"rush_tech": .55, "rush_power": .45})
    return team.zmix(p, slot, {"rush_tech": .45, "pursuit": .35, "hitting": .20})


def _block_weights(slot):
    if slot in ("LT", "LG", "C", "RG", "RT"):
        return {"pass_block": .55, "footwork": .30, "block_aware": .15}
    return {"pass_block": 1.0}


def _block_score(team, p, slot):
    return team.zmix(p, slot, _block_weights(slot))


def _block_below(team, p, slot):
    """The part of his pass blocking below every real blocker's level (out of position only)."""
    return team.untrained(p, slot, _block_weights(slot))


def protection(g, off, deff, call, dcall, rng):
    """Who wins up front. Returns (pressured, winners, rush list) where winners
    are (rusher_slot, rusher, blocker, win_prob) for rushers who beat their man."""
    lo, ld = call.lineup, dcall.lineup
    timing = {"screen": 0.35, "quick": 0.55, "dropback": 1.0, "play_action": 1.15,
              "deep": 1.35, "hail_mary": 1.6}.get(call.concept, 1.0)
    qb = lo.get("QB")
    if qb is not None:
        timing *= math.exp(-0.10 * off.z(qb, "QB", "timing"))
    # Obvious passing downs: rushers pin their ears back and the QB waits for routes past the sticks.
    timing *= math.exp(T.PASS_DOWN_RUSH * pass_down(g.state, call.tempo == "hurry"))

    extra_blockers = []
    blitz = bool(dcall.blitzers)
    if call.concept not in ("screen", "quick"):
        if lo.get("RB") is not None and rng.random() < (0.60 if blitz else 0.20):
            extra_blockers.append(("RB", lo["RB"]))
        if lo.get("TE1") is not None and rng.random() < (0.25 if blitz else 0.12):
            extra_blockers.append(("TE1", lo["TE1"]))

    duels = []      # (rusher_slot, rusher, blocker_slot, blocker, helper)
    used_blockers = set()
    for rs in DL_SLOTS:
        r = ld.get(rs)
        if r is None:
            continue
        bs = DL_MATCH[rs]
        b = lo.get(bs)
        duels.append([rs, r, bs, b, None])
        used_blockers.add(bs)
    center = lo.get("C")
    # The center helps whichever guard has the tougher matchup (a double team),
    # unless a blitzer comes through the middle.
    blitzers = [(s, ld[s]) for s in dcall.blitzers if ld.get(s) is not None]
    free = []
    for i, (bs_slot, bl) in enumerate(blitzers):
        if extra_blockers:
            es, ep = extra_blockers.pop(0)
            duels.append([bs_slot, bl, es, ep, None])
        elif center is not None and "C" not in used_blockers:
            duels.append([bs_slot, bl, "C", center, None])
            used_blockers.add("C")
        else:
            free.append((bs_slot, bl))
    # Protection slides toward the biggest threat: the center doubles the
    # inside rusher with the biggest edge, and a back or tight end who stays in
    # chips whoever is winning his matchup most clearly (often a star edge
    # rusher), the way real offenses scheme against great pass rushers.
    box = getattr(g, "box", None)

    def hot(r):
        # A rusher who's already getting home today draws the help (real offenses slide
        # protection and chip a hot rusher; without this, 3-sack games ran 2x real).
        line = box.players.get(r.id) if box is not None else None
        return (line.get("sacks", 0) + 0.5 * line.get("qb_hits", 0)) if line else 0.0

    def threat(d):
        return (_rush_score(deff, d[1], d[0]) - (_block_score(off, d[3], d[2]) if d[3] is not None else -2.0)
                + T.HOT_RUSHER_K * hot(d[1]))
    if center is not None and "C" not in used_blockers:
        inner = [d for d in duels if d[0] in ("LDT", "RDT") and d[3] is not None]
        if inner:
            max(inner, key=threat)[4] = center
    for es, ep in extra_blockers:
        open_duels = [d for d in duels if d[4] is None and d[3] is not None]
        if open_duels:
            max(open_duels, key=threat)[4] = ep
    # Game plan against a star rusher: when one man clearly wins his matchup,
    # the offense usually sends a back or tight end to chip him.
    if call.concept not in ("screen", "quick"):
        open_duels = [d for d in duels if d[4] is None and d[3] is not None]
        if open_duels:
            worst = max(open_duels, key=threat)
            edge = threat(worst)
            if edge > T.CHIP_EDGE and rng.random() < min(0.8, 0.35 + 0.4 * (edge - T.CHIP_EDGE)):
                used = {id(d[4]) for d in duels if d[4] is not None}
                for hs in ("RB", "TE1"):
                    hp = lo.get(hs)
                    if hp is not None and id(hp) not in used:
                        worst[4] = hp
                        break

    winners = []
    for rs, r, bs, b, helper in duels:
        rz = _rush_score(deff, r, rs)
        if b is None:
            w = T.FREE_RUSHER_WIN
        else:
            bz = _block_score(off, b, bs)
            below = _block_below(off, b, bs)
            if helper is not None:
                hs = "C" if helper is center else ("RB" if helper is lo.get("RB") else "TE1")
                hz = _block_score(off, helper, hs)
                if hz > bz:
                    below = 0.0         # the helper takes the man
                bz = max(bz, hz) + 0.45
            cls = RUSH_CLASS.get((natural(rs), natural(bs)), 0.0)
            inside = T.RUSH_INTERIOR if rs in ("LDT", "RDT") else 0.0
            # A terrible blocker can only be so much worse: diminishing returns on the blocker's side keeps
            # a rusher's own talent fully counted but stops team sack totals running past the real extremes.
            # A player blocking out of position below every real blocker's level isn't softened (T.UNTRAINED_K).
            w = sigmoid(T.RUSH_WIN_BASE + inside + T.RUSH_WIN_K * (rz - soft_cap(T.RUSH_EDGE_CAP, bz)
                                                                   - T.UNTRAINED_K * below + cls))
        w = min(0.95, w * timing)
        if rng.random() < w:
            winners.append((rs, r, b, w, bs))
    for rs, r in free:
        w = min(0.95, T.FREE_RUSHER_WIN * timing)
        if rng.random() < w:
            winners.append((rs, r, None, w, None))
    return (len(winners) > 0), winners


# How each pass concept shifts route depths (log-odds tilt on the real
# distribution of targeted air yards for that position).
CONCEPT_DEPTH = {"screen": -0.5, "quick": -1.2, "dropback": 0.25, "play_action": 0.6, "deep": 1.4}
SLOT_DEPTH = {"WR1": 0.02, "WR2": 0.12, "WR3": -0.22}


def _route_depth(rng, slot, concept, yl, player=None):
    if concept == "hail_mary":
        return int(min(yl + 9, yl + rng.random() * 6))
    m = (CONCEPT_DEPTH.get(concept, 0.0) + SLOT_DEPTH.get(slot, 0.0) + T.ROUTE_DEPTH_TILT
         + T.POSITION_DEPTH.get(slot[:2], 0.0))
    if player is not None and slot not in ("RB", "FB"):
        # Fast receivers run deeper routes; possession receivers work underneath.
        m += T.DEEP_SPEED_K * (player.athletic.get("speed", 57.5) - 57.5) / 13.0
    u = tilt(rng.random(), m)
    if slot.startswith("WR"):
        d = qvalue(data.Q_AIR_WR, u)
    elif slot.startswith("TE"):
        d = qvalue(data.Q_AIR_TE, u)
    else:
        d = qvalue(data.Q_AIR_RB, u)
    d = int(round(d + rng.random() - 0.5))
    # Near the goal line routes get squeezed: nothing deeper than the back of the end zone.
    return max(-8, min(d, yl + 9))


def _depth_key(depth):
    """Depth classes for centering: behind the line, short, intermediate,
    deep (where a safety can help over the top)."""
    if depth <= 0:
        return "0"
    if depth <= 9:
        return "1"
    if depth <= 15:
        return "2"
    return "3"


def _depth_class(d):
    if d <= 6:
        return 0
    if d <= 15:
        return 1
    return 2


def _route_weights(slot, depth):
    """(scale, skill weights) for how well a receiver gets open on this route."""
    if slot in ("RB", "FB"):
        return 1.0, ({"route_running": .55, "hands": .25, "elusiveness": .20} if slot == "RB"
                     else {"route_running": .7, "hands": .3})
    if slot.startswith("TE"):
        # Tight ends are measured against other tight ends, whose receiving
        # skills sit well below receivers'; scale so a great TE gets open like
        # a good receiver, not like a great one.
        return T.TE_ROUTE_SCALE, {"route_running": .5, "getting_open": .4, "after_catch": .1}
    k = T.WR_ROUTE_SCALE
    if depth <= 6:
        return k, {"route_running": .55, "getting_open": .45}
    if depth <= 15:
        return k, {"route_running": .5, "getting_open": .5}
    if slot.startswith("WR"):
        return k, {"route_running": .3, "getting_open": .3, "breakaway": .4}
    return k, {"route_running": .45, "getting_open": .45, "after_catch": .10}


def _receiver_route_score(team, p, slot, depth):
    k, w = _route_weights(slot, depth)
    return k * team.zmix(p, slot, w)


def _cover_weights(dslot, coverage, depth):
    if coverage == "man":
        if depth >= 16:
            return {"man_cover": .6, "pursuit": .4}
        return {"man_cover": .65, "bump_run": .20, "pursuit": .15}
    if dslot in ("WLB", "MLB", "SLB"):
        return {"zone_cover": .7, "diagnosis": .3}
    return {"zone_cover": .75, "ball_skills": .25}


def _cover_score(team, d, dslot, coverage, depth):
    return team.zmix(d, dslot, _cover_weights(dslot, coverage, depth))


def _sep_below(off, p, slot, deff, d, dslot, coverage, depth):
    """The part of a receiver's separation that comes from a player out of position below every
    real player's level at his spot (a hopeless receiver, a hopeless cover man). It's already in
    the separation; the completion and target caps count it outside the cap (T.UNTRAINED_K)."""
    k, w = _route_weights(slot, depth)
    below = k * off.untrained(p, slot, w)
    if d is not None:
        below -= deff.untrained(d, dslot, _cover_weights(dslot, coverage, depth))
    return below


def _assign_coverage(rng, routes, dcall, rushing_slots):
    """Match each route to the defender covering it."""
    ld = dcall.lineup
    available = [s for s in ld if ld[s] is not None and s not in rushing_slots and s not in DL_SLOTS]
    assignment = {}
    # Corners mostly play a side of the field and the top receiver moves around, so he
    # isn't always across from the top corner (T.CB_SIDE_SWAP; Oct 22: with a permanent
    # shadow the top corner's passes defensed ran ~12% high and 15+ PD seasons 16 vs real 10).
    swap = rng.random() < T.CB_SIDE_SWAP
    side = {"WR1": "WR2", "WR2": "WR1"} if swap else {}
    if dcall.coverage == "man":
        taken = set()
        for r in routes:
            for s in COVER_PRIORITY.get(side.get(r["slot"], r["slot"]), []):
                if s in available and s not in taken:
                    assignment[r["slot"]] = s
                    taken.add(s)
                    break
        helper = "FS" if "FS" in available and "FS" not in taken else None
        return assignment, helper
    for r in routes:
        key = r["slot"] if r["slot"].startswith("WR") else ("TE" if r["slot"].startswith("TE") else "RB")
        key = side.get(key, key)
        pool = [s for s in ZONE_POOL[key][_depth_class(r["depth"])] if s in available]
        if not pool:
            pool = available
        if pool:
            weights = [3.0 / (i + 1) for i in range(len(pool))]
            assignment[r["slot"]] = pick(rng, pool, weights)
    return assignment, None


def _threat(off, p, slot):
    """How dangerous a receiver is, as the defense sees it."""
    t = off.talent_z(p, slot)
    if slot.startswith("TE"):
        return 0.8 * t
    if slot in ("RB", "FB"):
        return 0.5 * t - 0.5
    return t


def _shade(off, deff, routes, dcall, st, rng, assignment=None, box=None):
    """Does the defense roll extra coverage to the most dangerous receiver on
    the field - the best player, or the worst mismatch (a great slot receiver
    on a weak nickel back)? More likely when he's far more dangerous than
    everyone else, on obvious passing downs, near the goal line, and by the
    defensive coordinator's style. Returns the route or None."""
    if dcall.prevent or len(routes) < 2:
        return None
    ld = dcall.lineup

    def danger(r):
        t = _threat(off, r["p"], r["slot"])
        dslot = (assignment or {}).get(r["slot"])
        if dslot and ld.get(dslot) is not None:
            mismatch = (_receiver_route_score(off, r["p"], r["slot"], 10)
                        - _cover_score(deff, ld[dslot], dslot, dcall.coverage, 10)
                        - COVER_CLASS.get((natural(dslot), natural(r["slot"])), 0.0))
            t = 0.5 * t + 0.5 * mismatch
        return t
    scored = sorted(((danger(r), r) for r in routes), key=lambda x: -x[0])
    t1, top = scored[0]
    t2 = scored[1][0]
    if t1 < 0.3:
        return None
    p = deff.shade_rate * math.exp(T.SHADE_GAP_K * (t1 - t2) + 0.35 * (t1 - 1.0))
    if st.down >= 3 and st.togo >= 5:
        p *= 1.25
    if st.yl <= 20:
        p *= 1.3
    if box is not None:
        hot = box.players.get(top["p"].id, {}).get("rec_yds", 0) if top["p"].id in box.players else 0
        p *= math.exp(T.SHADE_HOT_K * max(0.0, hot - 40))
    if dcall.loaded:
        p *= T.LOAD_BOX_SHADE       # the safety who'd roll over is in the box
    if rng.random() < min(0.9, p):
        return top
    return None


def _unused_shade_tail():
    return None


def pass_play(g, off, deff, call, dcall, rng):
    st = g.state
    lo, ld = call.lineup, dcall.lineup
    qb = lo["QB"]
    res = PlayResult("pass")
    res.passer = qb
    w = g.weather
    hurry_mode = call.tempo == "hurry"

    pressured, winners = protection(g, off, deff, call, dcall, rng)
    # A list, not a set: the order must be the same every run so a seed always
    # picks the same sacker and QB hitter.
    rushing = list(DL_SLOTS) + [s for s in dict.fromkeys(dcall.blitzers) if s not in DL_SLOTS]
    sense = off.z(qb, "QB", "sense_rush")
    scr = off.z(qb, "QB", "scrambling")
    if pressured:
        # Whoever gets there first: more likely the rusher who won more clearly.
        first = pick(rng, winners, [w[3] for w in winners])
        winners.remove(first)
        winners.insert(0, first)
        rs, rusher, blocker, wprob, bslot = winners[0]
        edge = 0.0
        if blocker is not None:
            edge = (_rush_score(deff, rusher, rs) - soft_cap(T.RUSH_EDGE_CAP, _block_score(off, blocker, bslot))
                    - T.UNTRAINED_K * _block_below(off, blocker, bslot))
        free = blocker is None
        conc = {"quick": -0.5, "screen": -0.9, "deep": 0.25, "play_action": 0.1, "hail_mary": 0.3}.get(call.concept, 0.0)
        p_sack = sigmoid(T.SACK_GIVEN_PRESSURE + 0.30 * edge - T.SACK_SENSE_RUSH_K * sense
                         - T.SACK_SCRAMBLE_K * scr + (0.35 if free else 0.0) + conc
                         + T.PASS_DOWN_SACK * pass_down(st, hurry_mode))
        if rng.random() < p_sack:
            return _sack(g, off, deff, qb, winners, res, rng, [ld[s] for s in rushing if ld.get(s) is not None])
        p_scramble = sigmoid(logit(T.SCRAMBLE_PRESSURED) + T.SCRAMBLE_SKILL_K * scr)
        if call.concept not in ("screen", "hail_mary") and rng.random() < p_scramble:
            return _scramble(g, off, deff, qb, call, dcall, res, rng)
        res.hurried = True
        res.pressure_by, res.beat = rusher, blocker
        if rng.random() < T.HIT_ON_HURRIED_THROW:
            res.qb_hit_by = rusher
            # Often it's a second man arriving who actually hits him.
            others = [ld[s] for s in rushing if ld.get(s) is not None and ld[s] is not rusher]
            if others and rng.random() < 0.45:
                res.qb_hit_by = pick(rng, others, [T.CLEANUP_WEIGHT.get(p.position, 1.0) for p in others])

    # Routes
    routes = []
    stay_home = set()
    for slot in RECEIVER_SLOTS:
        p = lo.get(slot)
        if p is None:
            continue
        routes.append({"slot": slot, "p": p, "depth": _route_depth(rng, slot, call.concept, st.yl, p)})
    if call.concept == "screen":
        screen_slot = "RB" if (lo.get("RB") and rng.random() < 0.6) else ("WR3" if lo.get("WR3") else "WR1")
        for r in routes:
            if r["slot"] == screen_slot:
                r["depth"] = min(r["depth"], -1 - int(rng.random() * 4))
    else:
        screen_slot = None
    assignment, helper = _assign_coverage(rng, routes, dcall, rushing)
    shaded = _shade(off, deff, routes, dcall, st, rng, assignment, getattr(g, "box", None))
    res.bracket = shaded["p"] if shaded else None
    blitz = bool(dcall.blitzers)
    read = off.zmix(qb, "QB", {"read_defense": .7, "timing": .3})
    arm = off.zmix(qb, "QB", {"deep_pass": .6, "long_pass": .4})
    best_sep = -9.0
    for r in routes:
        p, slot, depth = r["p"], r["slot"], r["depth"]
        rec = _receiver_route_score(off, p, slot, depth)
        dslot = assignment.get(slot)
        if dslot is None:
            cover, cls, d = -1.2, 0.0, None
        else:
            d = ld[dslot]
            cover = _cover_score(deff, d, dslot, dcall.coverage, depth)
            cls = COVER_CLASS.get((natural(dslot), natural(slot)), 0.0)
            if helper and depth >= 16 and ld.get(helper) is not None:
                cover += 0.25 + 0.15 * deff.z(ld[helper], helper, "zone_cover")
        sep = rec - cover - cls + rng.gauss(0, T.SEPARATION_NOISE)
        if shaded is not None:
            sep += -T.SHADE_COVER if r is shaded else T.SHADE_OTHERS
        # A receiver who's been fed all game draws tighter coverage.
        bx = getattr(g, "box", None)
        if bx is not None and r["p"].id in bx.players:
            fed = bx.players[r["p"].id].get("targets", 0)
            if fed > T.FED_COVER_FROM:
                sep -= T.FED_COVER_K * (fed - T.FED_COVER_FROM)
        if call.concept == "play_action":
            sep += 0.25
        if dcall.loaded:
            # One fewer man in coverage, and play action fakes the extra man up.
            sep += T.LOAD_BOX_PASS + (T.LOAD_BOX_PA if call.concept == "play_action" else 0.0)
        if blitz:
            sep += 0.30
        if dcall.prevent:
            sep += 0.6 if depth < 12 else -0.6
        if slot == screen_slot:
            sep += 0.8
        r["sep"], r["dslot"], r["def"] = sep, dslot, d
        r["below"] = _sep_below(off, p, slot, deff, d, dslot, dcall.coverage, depth)
        best_sep = max(best_sep, sep)

    # Unpressured scramble: nobody open and the QB can run.
    if not res.hurried and call.concept not in ("screen", "hail_mary"):
        p = T.SCRAMBLE_UNPRESSURED * math.exp(T.SCRAMBLE_SKILL_K * scr) * (1.0 if best_sep < -0.2 else 0.25)
        if rng.random() < p:
            return _scramble(g, off, deff, qb, call, dcall, res, rng)

    # Throwaway: nobody open, more often with a rusher in his face.
    if call.concept not in ("screen", "hail_mary"):
        p_ta = (T.THROWAWAY_RATE * (T.THROWAWAY_HURRIED if res.hurried else 1.0)
                * math.exp(centered("throwaway", -T.THROWAWAY_SEP_K * best_sep)))
        if rng.random() < p_ta:
            res.throwaway = True
            res.elapsed = 5
            # Intentional grounding if he's still in the pocket with nobody near.
            if res.hurried and rng.random() < T.GROUNDING_SHARE:
                from .penalties import make_grounding
                res.penalty = make_grounding(off, qb)
            return res

    # Choose the target.
    scores = []
    for r in routes:
        depth = r["depth"]
        rz = T.RZ_SPREAD if st.yl <= 10 else 1.0
        # How open he is and how good he is, with diminishing returns: the
        # play design still sends the ball to the other receivers.
        sep_w = T.TARGET_SEP_WEIGHT * (1 + T.TARGET_READ_K * read)
        edge = sep_w * r["sep"] + T.TARGET_TALENT_WEIGHT * off.talent_z(r["p"], r["slot"])
        # A cover man out of position and hopeless gets picked on: that part isn't capped.
        s = rz * (soft_cap(T.TARGET_EDGE_CAP, edge) + T.UNTRAINED_K * sep_w * r["below"])
        roles = getattr(off, "role_bias", T.TARGET_ROLE_BIAS)
        role = r["slot"]
        if role[:2] in ("WR", "TE"):
            # His own role on the depth chart (a backup: the deepest role there).
            role = getattr(off, "target_role", {}).get(r["p"].id) or ("WR_BACKUP" if role[:2] == "WR" else "TE3")
        s += roles.get(role, 0.0)
        if st.yl <= 10:
            s += T.RED_ZONE_ROLE.get(r["slot"][:2], 0.0)
        # The more one man has been fed today, the more the defense (and the
        # QB's progression) spreads it around.
        box = getattr(g, "box", None)
        if box is not None and r["p"].id in box.players:
            fed = box.players[r["p"].id].get("targets", 0)
            if fed > T.TARGET_SATURATION:
                s -= T.TARGET_SATURATION_K * (fed - T.TARGET_SATURATION)
        s += T.DEEP_ARM_K * depth * arm
        if res.hurried:
            s -= 0.05 * depth
        if st.down >= 3:
            pull = 1.0 if st.togo <= T.STICKS_TARGET_MAX else T.STICKS_LONG_SCALE
            s += pull * (T.STICKS_TARGET_K if depth >= st.togo else (-T.SHORT_OF_STICKS_K if depth < st.togo - 2 else 0.0))
        if hurry_mode and depth >= 8:
            s += 0.15
        if r["slot"] == screen_slot:
            s += 2.0
        scores.append(s)
    mx = max(scores)
    weights = [math.exp(s - mx) for s in scores]
    target = pick(rng, routes, weights)
    rec = target["p"]
    slot = target["slot"]
    depth = target["depth"]
    sep = target["sep"]
    d = target["def"]
    dslot = target["dslot"]
    res.receiver = rec
    res.target_slot = slot
    res.cover_def, res.sep = d, sep
    res.air_yards = depth
    res.depth_word = "deep" if depth >= 15 else "short"
    res.direction = pick(rng, [x[0] for x in _DIRECTION[slot]], [x[1] for x in _DIRECTION[slot]])

    # Completion, interception or incompletion.
    if depth <= 0:
        dskill = "screen_pass"
    elif depth <= 9:
        dskill = "short_pass"
    elif depth <= 19:
        dskill = "medium_pass"
    elif depth <= 29:
        dskill = "long_pass"
    else:
        dskill = "deep_pass"
    acc = off.zmix(qb, "QB", {"accuracy": .55, dskill: .45})
    if st.down == 3:
        acc = 0.75 * acc + 0.25 * off.z(qb, "QB", "third_down")
    if hurry_mode:
        acc = 0.75 * acc + 0.25 * off.z(qb, "QB", "two_minute")
    hands = off.zmix(rec, slot, {"hands": .7, "traffic": .3} if sep < 0 else {"hands": 1.0})
    dball = deff.z(d, dslot, "ball_skills") if d is not None else -1.0
    base = base_completion(depth)
    dec = off.zmix(qb, "QB", {"int_avoid": .6, "read_defense": .4})
    if call.concept == "hail_mary":
        p_comp = sigmoid(logit(0.06) + 0.2 * acc)
        p_int = 0.12
    else:
        dk = _depth_key(depth)
        x = logit(base) + T.COMP_SCALE + soft_cap(T.COMP_CAP, centered(
            "comp" + dk, T.COMP_ACCURACY_K * acc + T.COMP_SEPARATION_K * sep + T.COMP_HANDS_K * hands
            - T.COMP_DEFENDER_K * dball + (T.COMP_HURRIED if res.hurried else 0.0) + w.pass_logit(depth)))
        x += field_squeeze(T.PASS_FIELD, st.yl)
        # Coverage that knows a pass is coming sits on the sticks; on early downs it must respect the run.
        pdl = pass_down(st, hurry_mode, cover=True)
        x -= T.PASS_DOWN_COVER * pdl
        # A non-quarterback throwing (only he can be below every real QB's level, since a
        # real QB's accuracy has a soft floor at -Z_CAP): the part below it isn't capped.
        x += T.UNTRAINED_PASSER_K * min(0.0, acc + T.Z_CAP)
        # Likewise a hopeless cover man or receiver out of position (T.UNTRAINED_K).
        x += T.UNTRAINED_K * (T.COMP_SEPARATION_K * target.get("below", 0.0)
                              + T.COMP_HANDS_K * off.untrained(rec, slot, {"hands": 1.0}))
        if slot == "RB":
            x += T.RB_CATCH_BONUS
        p_comp = sigmoid(x)
        p_int = (base_interception(depth) * T.INT_SCALE
                 * math.exp(centered("int" + dk, -T.INT_SKILL_K * dec + T.INT_DEFENDER_K * dball
                                     + (T.INT_HURRIED if res.hurried else 0.0) - T.INT_SEPARATION_K * sep))
                 * math.exp(T.PASS_DOWN_INT * pdl))
    p_int = min(p_int, 0.6 * (1 - p_comp))
    u = rng.random()
    res.elapsed = 6
    if u < p_comp:
        res.complete = True
        return _completion(g, off, deff, call, dcall, res, rec, slot, depth, sep, d, dslot, rng)
    if u < p_comp + p_int:
        return _interception(g, off, deff, res, rec, depth, d, dslot, dcall, rng)
    # Incomplete
    res.elapsed = 5
    if sep > -0.3 and rng.random() < 0.10 * math.exp(-T.DROP_HANDS_K * off.z(rec, slot, "hands")):
        res.dropped = True
    elif depth <= 12 and rng.random() < T.BATTED_RATE * (1.5 if res.hurried else 1.0):
        # Batted down or tipped at the line by a pass rusher.
        line = [ld[s] for s in DL_SLOTS if ld.get(s) is not None]
        if line:
            res.pd_by = pick(rng, line, [math.exp(0.3 * deff.z(p, _slot_of(ld, p), "rush_tech")) for p in line])
            res.batted = True
    elif d is not None and rng.random() < min(0.65, T.PD_RATE + 0.03 * dball):
        res.pd_by = d
    return res


def _completion(g, off, deff, call, dcall, res, rec, slot, depth, sep, d, dslot, rng):
    st = g.state
    if depth <= 0:
        table = data.Q_YAC_BEHIND
    elif depth <= 9:
        table = data.Q_YAC_SHORT
    elif depth <= 19:
        table = data.Q_YAC_INTER
    else:
        table = data.Q_YAC_DEEP
    if slot == "RB":
        yw = {"elusiveness": .5, "breakaway": .3, "vision": .2}
    elif slot == "FB":
        yw = {"power_run": .6, "vision": .4}
    elif slot.startswith("WR"):
        yw = {"after_catch": .65, "breakaway": .35}
    else:
        yw = {"after_catch": 1.0}
    yskill = off.zmix(rec, slot, yw)
    below = off.untrained(rec, slot, yw)
    if d is not None:
        tackle = deff.zmix(d, dslot, {"hitting": .5, "pursuit": .5})
        below -= deff.untrained(d, dslot, {"hitting": .5, "pursuit": .5})
    else:
        tackle = -0.5
    m = soft_cap(T.YAC_CAP, centered("yac" + _depth_key(depth), T.YAC_K * (yskill - tackle) + T.YAC_SEP_K * sep))
    m += T.UNTRAINED_K * T.YAC_K * below
    m += field_squeeze(T.YAC_FIELD, st.yl - depth) + T.YAC_SCALE
    if slot == "RB":
        m += T.RB_YAC_BONUS
    if dcall.prevent:
        m -= 0.1
    yac = int(round(qvalue(table, tilt(rng.random(), m), rng, tail=12)))
    if depth + yac > st.yl:
        yac = st.yl - depth
    gain = depth + yac
    if st.yl - gain >= 100:
        gain = st.yl - 99
    res.yac = yac
    res.yards = gain
    if gain >= st.yl:
        res.td = True
        res.yards = st.yl
        res.elapsed = 6 + abs(yac) // 8
        return res
    res.elapsed = 6 + max(0, yac) // 8
    _tackle(res, deff, dcall.lineup, gain, rng, primary=d if yac < 6 else None)
    # Fumble after the catch
    fa = off.z(rec, slot, "fumble_avoid")
    hit = deff.z(res.tacklers[0], _slot_of(dcall.lineup, res.tacklers[0]), "hitting") if res.tacklers else 0.0
    if rng.random() < T.FUMBLE_CATCH * math.exp(-T.FUMBLE_SKILL_K * fa + 0.25 * hit) * g.weather.fumble_mult():
        _fumble(g, res, deff, dcall.lineup, st.yl - gain, rng, kind="catch")
        return res
    hurry = call.tempo == "hurry"
    p_oob = (0.30 if hurry else 0.20) * (0.6 if depth <= 0 else 1.0)
    if rng.random() < p_oob:
        res.oob = True
    return res


def _interception(g, off, deff, res, rec, depth, d, dslot, dcall, rng):
    st = g.state
    res.interception = True
    res.change_poss = True
    ld = dcall.lineup
    if d is None or rng.random() < 0.28:
        # Tipped balls, overthrows to a safety, a linebacker undercutting a route.
        cands = [ld[s] for s in ("FS", "SS", "CB1", "CB2", "NB", "DB", "MLB", "WLB") if ld.get(s) is not None]
        d = pick(rng, cands) if cands else d
    res.interceptor = d
    spot = st.yl - depth                       # offense's yards from goal at the catch point
    res.elapsed = 7
    if spot <= 0 and rng.random() < 0.75:
        res.touchback = True
        res.new_yl = 80
        return res
    spot_def = 100 - max(spot, 0)              # interceptor's distance to the end zone he's running at
    ret = int(round(qvalue(data.Q_INT_RETURN, rng.random(), rng, tail=15)))
    ret = max(0, ret)
    res.return_yards = ret
    if ret >= spot_def:
        res.return_yards = spot_def
        res.def_td = True
        res.new_yl = None
        return res
    res.new_yl = spot_def - ret
    res.elapsed += ret // 8
    return res


def _sack(g, off, deff, qb, winners, res, rng, rushers=()):
    st = g.state
    res.kind = "sack"
    res.passer = qb
    loss = int(round(qvalue(data.Q_SACK_LOSS, rng.random())))
    loss = max(0, loss)
    res.yards = -loss
    primary = winners[0]
    # Coverage sacks and clean-up sacks: often it's not the man who won first
    # who finishes the play, but whoever closes in as the QB holds the ball.
    res.pressure_by, res.beat = primary[1], primary[2]
    others = [p for p in rushers if p is not primary[1]]
    box = getattr(g, "box", None)
    line = box.players.get(primary[1].id) if box is not None else None
    hot = min(0.4, T.HOT_RUSHER_CLEANUP * line.get("sacks", 0)) if line else 0.0
    if others and rng.random() < T.SACK_CLEANUP + hot:
        res.sackers = [pick(rng, others, [T.CLEANUP_WEIGHT.get(p.position, 1.0) for p in others])]
    else:
        res.sackers = [primary[1]]
        if len(winners) > 1 and rng.random() < 0.18:
            res.sackers.append(winners[1][1])
    res.qb_hit_by = res.sackers[0]
    res.elapsed = 6
    if st.yl + loss >= 100:
        # Backed up, QBs fight to get back to the line; most are dragged down
        # just short of the end zone.
        if rng.random() < T.SAFETY_ESCAPE:
            loss = max(0, 99 - st.yl)
            res.yards = -loss
        else:
            res.safety = True
            res.yards = -(100 - st.yl)
            return res
    sense = off.z(qb, "QB", "sense_rush")
    power = deff.z(primary[1], primary[0], "rush_power")
    if rng.random() < T.FUMBLE_SACK * math.exp(-0.25 * sense + 0.25 * power) * g.weather.fumble_mult():
        res.forced_by = primary[1]
        _fumble(g, res, deff, None, st.yl + loss, rng, forced=primary[1], kind="sack")
    return res


def _scramble(g, off, deff, qb, call, dcall, res, rng):
    st = g.state
    res.kind = "scramble"
    res.rusher = qb
    scr = off.z(qb, "QB", "scrambling")
    m = centered("scramble", T.SCRAMBLE_YARDS_K * scr)
    y = int(round(qvalue(data.Q_SCRAMBLE, tilt(rng.random(), m), rng, tail=12)))
    y = min(y, st.yl)
    res.yards = y
    res.elapsed = 7
    if y >= st.yl:
        res.td = True
        return res
    if rng.random() < (0.30 if call.tempo == "hurry" else 0.22):
        res.oob = True
    if not res.oob:
        _tackle(res, deff, dcall.lineup, y, rng)
    if rng.random() < T.FUMBLE_QB_RUN * g.weather.fumble_mult():
        _fumble(g, res, deff, dcall.lineup, st.yl - y, rng, kind="qb")
    return res


# ---------------------------------------------------------------------------
# Run plays
# ---------------------------------------------------------------------------

# Blockers and defenders at the point of attack (offense's view of left/right).
RUN_MAP = {
    ("left", "end"): (["LT", "LG", "TE2", "FB"], ["RE", "WLB", "CB2", "SS"]),
    ("left", "tackle"): (["LT", "LG", "TE2", "FB"], ["RE", "RDT", "WLB", "MLB"]),
    ("left", "guard"): (["LG", "C", "LT", "FB"], ["RDT", "MLB", "WLB"]),
    ("middle", "guard"): (["C", "LG", "RG", "FB"], ["RDT", "LDT", "MLB"]),
    ("right", "guard"): (["RG", "C", "RT", "FB"], ["LDT", "MLB", "SLB"]),
    ("right", "tackle"): (["RT", "RG", "TE1", "FB"], ["LE", "LDT", "SLB", "MLB"]),
    ("right", "end"): (["RT", "TE1", "TE3", "FB"], ["LE", "SLB", "CB1", "SS"]),
}
# If a listed defender isn't on the field (nickel/dime), the next one fills in.
DEF_FILL = {"SLB": ["NB", "SS", "DB"], "WLB": ["NB", "MLB", "DB"], "MLB": ["WLB", "SLB", "DB", "SS"],
            "SS": ["FS"], "CB1": ["NB"], "CB2": ["NB"]}


def _run_block_weights(slot):
    if slot in ("LT", "LG", "C", "RG", "RT"):
        return {"run_block": .60, "block_aware": .25, "footwork": .15}
    return {"run_block": 1.0}


def _run_block_score(team, p, slot):
    return team.zmix(p, slot, _run_block_weights(slot))


def _run_def_weights(slot):
    nat = natural(slot)
    if nat in ("DE", "DT"):
        return {"run_defense": .45, "shed": .35, "rush_power": .20}
    if nat in ("OLB", "ILB"):
        return {"run_defense": .40, "diagnosis": .30, "pursuit": .30}
    return {"run_defense": .55, "hitting": .45}


def _run_def_score(team, p, slot):
    return team.zmix(p, slot, _run_def_weights(slot)) - (0.35 if natural(slot) not in ("DE", "DT", "OLB", "ILB") else 0.0)


def _run_below(off, blockers, deff, defenders):
    """Blockers' minus defenders' run play below every real player's level at their spots
    (out of position only), averaged like the scores; counted outside T.RUN_CAP."""
    b = sum(off.untrained(p, s, _run_block_weights(s)) for s, p in blockers) / max(1, len(blockers))
    d = sum(deff.untrained(p, s, _run_def_weights(s)) for s, p in defenders) / max(1, len(defenders))
    return b - d


def run_play(g, off, deff, call, dcall, rng):
    st = g.state
    lo, ld = call.lineup, dcall.lineup
    res = PlayResult("run")
    carrier = lo.get(call.carrier) or lo.get("RB") or lo.get("QB")
    cslot = call.carrier if lo.get(call.carrier) is not None else ("RB" if lo.get("RB") else "QB")
    res.rusher = carrier
    res.direction = call.location
    res.gap = call.gap
    qb = lo.get("QB")
    if qb is not None and cslot != "QB" and rng.random() < T.FUMBLE_EXCHANGE * g.weather.fumble_mult():
        # The snap or the handoff is fumbled (credited to the quarterback, as the NFL records it).
        res.rusher = qb
        res.yards = max(-rng.randint(0, 3), -(99 - st.yl))
        res.elapsed = 5
        _fumble(g, res, deff, ld, st.yl - res.yards, rng, kind="qb")
        return res
    blk_slots, def_slots = RUN_MAP[(call.location, call.gap)]
    blockers = [(s, lo[s]) for s in blk_slots if lo.get(s) is not None]
    defenders = []
    seen = set()
    for s in def_slots:
        if ld.get(s) is not None and s not in seen:
            defenders.append((s, ld[s]))
            seen.add(s)
        else:
            for alt in DEF_FILL.get(s, []):
                if ld.get(alt) is not None and alt not in seen:
                    defenders.append((alt, ld[alt]))
                    seen.add(alt)
                    break
    b = sum(_run_block_score(off, p, s) for s, p in blockers[:3]) / max(1, min(3, len(blockers)))
    extra = len(blockers) - 3
    dz = [(_run_def_score(deff, p, s), s, p) for s, p in defenders]
    dscore = sum(x[0] for x in dz[:3]) / max(1, min(3, len(dz)))
    block_edge = b - dscore + 0.15 * max(0, extra)
    res.block_edge = block_edge

    if cslot == "QB":
        rk, rw = T.QB_KEEP_SKILL_K, {"scrambling": 1.0}
    elif cslot.startswith("WR"):
        rk, rw = 0.8, {"after_catch": .5, "breakaway": .5}
    elif call.gap == "end":
        rk, rw = 1.0, {"vision": .35, "elusiveness": .35, "breakaway": .30}
    else:
        rk, rw = 1.0, {"vision": .40, "power_run": .35, "elusiveness": .25}
    rb_z = rk * off.zmix(carrier, cslot, rw)
    below = (T.RUN_BLOCK_K * _run_below(off, blockers[:3], deff, defenders[:3])
             + T.RUN_BACK_K * rk * off.untrained(carrier, cslot, rw))
    lvl2 = [ld[s] for s in ("MLB", "WLB", "SLB") if ld.get(s) is not None]
    if lvl2:
        l2w = {"pursuit": .4, "hitting": .3, "diagnosis": .3}
        l2 = sum(deff.zmix(p, _slot_of(ld, p), l2w) for p in lvl2) / len(lvl2)
        below -= T.RUN_BACK_K * sum(deff.untrained(p, _slot_of(ld, p), l2w) for p in lvl2) / len(lvl2)
    else:
        l2 = -0.6
    box = {"Base 4-3": T.RUN_BOX_HEAVY, "Nickel": T.RUN_BOX_LIGHT * 0.6, "Dime": T.RUN_BOX_LIGHT}.get(dcall.package, 0.0)
    if dcall.loaded:
        box += T.LOAD_BOX_RUN       # a safety walked down: 8 in the box
    m = T.RUN_BLOCK_K * block_edge + T.RUN_BACK_K * (rb_z - l2) + box
    if dcall.blitzers:
        m += 0.05
    if g.weather.precip == "snow" and not g.weather.indoors:
        m -= 0.05
    m = soft_cap(T.RUN_CAP, centered("qb_run" if cslot == "QB" else "run", m))
    m += T.UNTRAINED_K * below      # players out of position below every real player's level: not capped
    if cslot == "QB":
        table = data.Q_QB_RUN
    elif st.togo <= 2 and st.yl > 3:
        table = data.Q_RUN_SHORT_YARDAGE
    else:
        table = data.Q_RUN_OPEN
    m += field_squeeze(T.RUN_FIELD, st.yl) * (T.QB_RUN_FIELD_SCALE if cslot == "QB" else 1.0) + T.RUN_SCALE
    u = tilt(rng.random(), m)
    if u > 0.85:
        safeties = [ld[s] for s in ("FS", "SS") if ld.get(s) is not None]
        sz = (sum(deff.z(p, _slot_of(ld, p), "pursuit") for p in safeties) / len(safeties)) if safeties else -0.5
        speed = off.z(carrier, cslot, "breakaway") if cslot != "QB" else off.z(carrier, "QB", "scrambling")
        u = tilt(u, centered("breakaway", T.RUN_BREAKAWAY_K * (speed - sz)))
    y = int(round(qvalue(table, u, rng, tail=15)))
    y = min(y, st.yl)
    if st.yl - y >= 100:
        if rng.random() < T.SAFETY_ESCAPE:
            y = st.yl - 99
        else:
            res.safety = True
            y = st.yl - 100
    res.yards = y
    res.elapsed = 5 + max(0, y) // 10
    if y >= st.yl:
        res.td = True
        res.yards = st.yl
        return res
    if res.safety:
        _tackle(res, deff, ld, y, rng, poa=dz)
        return res
    hurry = call.tempo == "hurry"
    p_oob = (0.106 if hurry else 0.076) * (1.8 if call.gap == "end" else 0.7)
    if y >= 3 and rng.random() < p_oob:
        res.oob = True
    _tackle(res, deff, ld, y, rng, poa=dz)
    if y < 0:
        res.tfl = True
    fa = off.z(carrier, cslot, "fumble_avoid") if cslot != "QB" else 0.0
    hit = deff.z(res.tacklers[0], _slot_of(ld, res.tacklers[0]), "hitting") if res.tacklers else 0.0
    base = T.FUMBLE_QB_RUN if cslot == "QB" else T.FUMBLE_RUN
    if rng.random() < base * math.exp(-T.FUMBLE_SKILL_K * fa + 0.25 * hit) * g.weather.fumble_mult():
        _fumble(g, res, deff, ld, st.yl - y, rng, kind="qb" if cslot == "QB" else "run")
    return res


def sneak_play(g, off, deff, call, dcall, rng):
    st = g.state
    lo, ld = call.lineup, dcall.lineup
    res = PlayResult("run")
    res.kind = "sneak"
    qb = lo["QB"]
    res.rusher = qb
    res.direction = "middle"
    res.gap = "guard"
    inner_o = [(s, lo[s]) for s in ("C", "LG", "RG") if lo.get(s) is not None]
    inner_d = [(s, ld[s]) for s in ("LDT", "RDT", "MLB") if ld.get(s) is not None]
    bo = sum(_run_block_score(off, p, s) for s, p in inner_o) / max(1, len(inner_o))
    bd = sum(_run_def_score(deff, p, s) for s, p in inner_d) / max(1, len(inner_d))
    p = sigmoid(logit(T.SNEAK_SUCCESS) + centered("sneak", 0.45 * (bo - bd)) - (0.25 if st.togo >= 2 else 0.0))
    if rng.random() < p:
        y = st.togo + (1 if rng.random() < 0.3 else 0)
    else:
        y = 0 if rng.random() < 0.7 else -1
    y = min(y, st.yl)
    res.yards = y
    res.elapsed = 4
    if y >= st.yl:
        res.td = True
        return res
    _tackle(res, deff, ld, y, rng, poa=[(_run_def_score(deff, p2, s), s, p2) for s, p2 in inner_d])
    return res


# ---------------------------------------------------------------------------
# Tackles and fumbles
# ---------------------------------------------------------------------------

def _slot_of(lineup, player):
    for s, p in lineup.items():
        if p is player:
            return s
    return "MLB"


def _pool_key(slot):
    if slot in DL_SLOTS:
        return "DT" if slot in ("LDT", "RDT") else "DE"
    if slot in ("CB1", "CB2"):
        return "CB"
    return slot


def _tackle(res, deff, ld, gain, rng, primary=None, poa=None):
    """Credit the tackle to a defender who'd realistically be there; sure
    tacklers who read plays fast get there more often. How far the runner got
    decides who is around him (tuning.TACKLE_POOL)."""
    bucket = "short" if gain <= 4 else ("mid" if gain <= 9 else ("long" if gain <= 19 else "break"))
    weights = T.TACKLE_POOL[bucket]
    on_field = [(s, p) for s, p in ld.items() if p is not None]

    def pick_from(exclude=None):
        cands, w = [], []
        for s, p in on_field:
            base = weights.get(_pool_key(s), 0.0)
            if base <= 0 or p is exclude:
                continue
            cands.append(p)
            w.append(base * math.exp(T.TACKLE_SKILL_K * deff.zmix(p, s, {"pursuit": .4, "hitting": .3, "diagnosis": .3})))
        return pick(rng, cands, w) if cands else None

    if primary is None:
        if gain <= 0 and poa and rng.random() < T.TFL_POA_SHARE:
            cands = [x[2] for x in poa]
            primary = pick(rng, cands, [math.exp(0.6 * x[0]) for x in poa])
        else:
            primary = pick_from()
    if primary is None:
        return
    res.tacklers = [primary]
    if rng.random() < T.TACKLE_ASSIST[bucket]:
        res.assist = pick_from(exclude=primary)


def _fumble(g, res, deff, ld, spot_off, rng, forced=None, kind=None):
    """A fumble at spot_off (offense's yards from the goal it's attacking).
    kind (sack / qb / run / catch): how often the defense recovers it
    (T.FUMBLE_LOST_BY_KIND, real rates)."""
    res.fumble = True
    if forced is None and res.tacklers and rng.random() < T.FORCED_SHARE:
        forced = res.tacklers[0]
    res.forced_by = forced
    if rng.random() < T.FUMBLE_LOST_BY_KIND.get(kind, T.FUMBLE_LOST_SHARE):
        res.fumble_lost = True
        res.change_poss = True
        if ld:
            cands = [p for p in ld.values() if p is not None]
            res.recovered_by = pick(rng, cands)
        else:
            res.recovered_by = forced
        spot_def = 100 - spot_off
        ret = 0
        r = rng.random()
        if r < 0.065:
            ret = spot_def          # scoop and score
        elif r < 0.35:
            ret = int(rng.random() * 12)
        if ret >= spot_def:
            res.def_td = True
            res.return_yards = spot_def
            res.new_yl = None
        else:
            res.return_yards = ret
            res.new_yl = max(1, spot_def - ret)


# ---------------------------------------------------------------------------
# Special teams
# ---------------------------------------------------------------------------

def coverage_z(team, unit_slots=("WLB", "SLB", "SS", "NB", "DB", "FS")):
    """Kick coverage quality: backups at linebacker and safety run down kicks."""
    vals = []
    for slot in unit_slots:
        ids = [pid for pid in team.chart.get(slot, []) if team.available(pid)]
        if len(ids) > 1:
            p = team.by_id[ids[1]]
            vals.append(team.zmix(p, slot, {"pursuit": .6, "hitting": .4}))
    return sum(vals) / len(vals) if vals else 0.0


def kickoff(g, kick, recv, rng, onside=False, free_kick=False):
    res = PlayResult("kickoff")
    kicker = kick.special("K")
    res.kicker = kicker
    if onside:
        res.kind = "onside"
        res.elapsed = 4
        if rng.random() < 0.10:
            res.recovered_by = kick.special("SS") or kicker
            res.change_poss = False
            res.new_yl = 54            # kicking team keeps it at the receiving team's 46
        else:
            res.change_poss = True
            res.recovered_by = recv.special("WR1")
            res.new_yl = 46            # receiving team at the kicking team's 46
        return res
    res.change_poss = True
    kz = kick.z(kicker, "K", "kickoff") if kicker else -1.0
    r = rng.random()
    tb_rate = 0.21 + 0.035 * kz
    if free_kick:
        tb_rate = 0.02
    if r < 0.025:
        res.kick_distance = 40
        res.new_yl = 60                 # short of the landing zone / out of bounds: ball at the 40
        res.note = "out of bounds"
        res.elapsed = 0
        return res
    if r < 0.025 + tb_rate:
        res.touchback = True
        res.kick_distance = 65 + int(rng.random() * 8)
        res.new_yl = 65
        res.elapsed = 0
        return res
    returner = recv.special("KR")
    res.returner = returner
    catch = -3 + rng.random() * 13 - 1.2 * kz      # yards from his own goal line where he fields it
    if free_kick:
        catch = 20 + rng.random() * 15
    res.kick_distance = int(round(65 - catch)) if not free_kick else int(round(80 - catch))
    rz = recv.z(returner, "KR", "kick_return") if returner else -1.0
    m = centered("kr", T.RETURN_K * (rz - coverage_z(kick)))
    ret = qvalue(data.Q_KR_2025, tilt(rng.random(), m), rng, tail=20)
    start = catch + ret
    res.return_yards = int(round(ret))
    res.elapsed = 6
    if start >= 100:
        res.def_td = True               # return touchdown (scored by the receiving team)
        res.return_yards = int(round(100 - catch))
        res.new_yl = None
        return res
    start = max(1, int(round(start)))
    res.new_yl = 100 - start
    _cover_tackle(res, kick, rng)
    if rng.random() < T.KR_FUMBLE:
        res.fumble = True
        res.forced_by = res.tacklers[0] if res.tacklers else None
        if rng.random() < T.KR_FUMBLE_LOST:
            res.fumble_lost = True
            res.change_poss = False
            res.recovered_by = _cov_player(kick, rng)
            res.new_yl = start          # kicking team ball at the spot
    return res


def _cov_player(team, rng, exclude=None, offense=False):
    """A kick coverage player: mostly backup linebackers and defensive backs,
    sometimes a backup running back, receiver or tight end."""
    cands = []
    slots = (("RB", 1), ("WR3", 1), ("WR4", 1), ("TE2", 1), ("FB", 0)) if offense else \
        (("WLB", 1), ("SLB", 1), ("MLB", 1), ("SS", 1), ("FS", 1), ("NB", 1), ("DB", 1), ("CB2", 2))
    for slot, k in slots:
        ids = [pid for pid in team.chart.get(slot, []) if team.available(pid)]
        if len(ids) > k:
            p = team.by_id[ids[k]]
            if p is not exclude and p not in cands:
                cands.append(p)
    if not cands:
        return None
    return pick(rng, cands)


def _cover_tackle(res, kick, rng):
    """Credit a kick or punt return tackle to the coverage team."""
    first = _cov_player(kick, rng, offense=rng.random() < T.ST_OFFENSE_SHARE) or _cov_player(kick, rng)
    res.tacklers = [first] if first else []
    if first and rng.random() < T.ST_ASSIST:
        res.assist = _cov_player(kick, rng, exclude=first, offense=rng.random() < T.ST_OFFENSE_SHARE)


def punt(g, kick, recv, rng):
    st = g.state
    res = PlayResult("punt")
    punter = kick.special("P")
    res.punter = punter
    res.snapper = kick.special("LS")
    res.change_poss = True
    res.elapsed = 9
    snap = kick.z(res.snapper, "LS", "long_snap") if res.snapper else -1.5
    if rng.random() < 0.0015 * math.exp(-0.7 * snap):
        res.note = "bad snap"
        res.blocked = True
        loss = 8 + int(rng.random() * 10)
        spot = st.yl + loss
        if spot >= 100:
            res.safety = True
            res.new_yl = None
            return res
        res.new_yl = 100 - spot
        return res
    if rng.random() < 0.0043:
        res.blocked = True
        res.tacklers = []
        if rng.random() < 0.25:
            res.def_td = True
            res.new_yl = None
            return res
        spot = min(99, st.yl + 8)
        res.new_yl = 100 - spot
        return res
    yl = st.yl
    if yl <= 45:
        table = data.Q_PUNT_0_45
    elif yl <= 55:
        table = data.Q_PUNT_46_55
    elif yl <= 65:
        table = data.Q_PUNT_56_65
    else:
        table = data.Q_PUNT_66_100
    pz = kick.zmix(punter, "P", {"punt_power": .65, "hang_time": .35}) if punter else -1.0
    gross = qvalue(table, rng.random()) + T.PUNT_SCALE + T.PUNT_POWER_K * pz + g.weather.punt_yards()
    gross = int(round(max(20, gross)))
    land = yl - gross                    # receiving team's yards from its own goal line at the landing spot
    res.kick_distance = gross
    hang = kick.z(punter, "P", "hang_time") if punter else -1.0
    aim = kick.z(punter, "P", "directional") if punter else -1.0
    if land <= 0:
        if yl <= 55 and rng.random() < 0.35 + 0.08 * aim:
            res.downed = True
            res.new_yl = 100 - (2 + int(rng.random() * 8))
            res.kick_distance = yl - (100 - res.new_yl)
            return res
        res.touchback = True
        res.kick_distance = yl
        res.new_yl = 80
        return res
    r = rng.random()
    short_field = land <= 15
    p_fc = (0.42 if short_field else 0.24) + 0.05 * hang
    p_oob = 0.10 + (0.04 * aim if short_field else 0.0)
    p_down = (0.30 if short_field else 0.06) + (0.04 * aim if short_field else 0.0)
    if r < p_fc:
        res.fair_catch = True
        res.returner = recv.special("PR")
        res.new_yl = 100 - land
        return res
    if r < p_fc + p_oob:
        res.oob = True
        res.new_yl = 100 - land
        return res
    if r < p_fc + p_oob + p_down:
        res.downed = True
        res.new_yl = 100 - land
        return res
    returner = recv.special("PR")
    res.returner = returner
    if rng.random() < T.PR_MUFF:
        res.muffed = True
        if rng.random() < T.PR_MUFF_LOST:
            res.change_poss = False
            res.fumble_lost = True
            res.recovered_by = _cov_player(kick, rng)
            res.new_yl = land               # punting team ball at the spot (their yards to goal)
            return res
    rz = recv.z(returner, "PR", "punt_return") if returner else -1.0
    m = centered("pr", T.RETURN_K * (rz - coverage_z(kick)) - 0.12 * hang)
    ret = int(round(qvalue(data.Q_PR, tilt(rng.random(), m), rng, tail=15)))
    res.return_yards = ret
    res.elapsed = 12
    start = land + ret
    if start >= 100:
        res.def_td = True
        res.return_yards = 100 - land
        res.new_yl = None
        return res
    res.new_yl = 100 - max(1, start)
    _cover_tackle(res, kick, rng)
    return res


def field_goal(g, kick, deff, rng, distance=None):
    st = g.state
    res = PlayResult("fg")
    kicker = kick.special("K")
    res.kicker = kicker
    res.holder = kick.special("P")
    res.snapper = kick.special("LS")
    dist = distance if distance is not None else st.yl + 17
    res.kick_distance = dist
    res.elapsed = 5
    acc = kick.z(kicker, "K", "kick_accuracy") if kicker else -1.5
    power = kick.z(kicker, "K", "kick_power") if kicker else -1.5
    base = _interp([20, 32, 37, 42, 47, 52, 57, 64, 70],
                   [0.985, 0.972, 0.909, 0.842, 0.764, 0.74, 0.637, 0.457, 0.25], dist)
    rng_limit = 56 + 5 * power - g.weather.fg_range_loss()
    x = logit(base) + T.FG_SCALE + T.FG_ACCURACY_K * acc + T.FG_POWER_K * max(0, dist - 40) * power + g.weather.fg_logit(dist)
    if dist > rng_limit:
        x -= 0.25 * (dist - rng_limit)
    snap = kick.z(res.snapper, "LS", "long_snap") if res.snapper else -1.5
    if rng.random() < 0.0015 * math.exp(-0.7 * snap):
        x -= 2.0
        res.note = "bad snap"
    block = 0.012 + 0.0008 * max(0, dist - 40)
    if rng.random() < block:
        res.blocked = True
        res.change_poss = True
        spot = st.yl + 7
        if rng.random() < 0.08:
            res.def_td = True
            res.new_yl = None
        else:
            res.new_yl = 100 - min(99, spot + 5)
        return res
    if rng.random() < sigmoid(x):
        res.made = True
        return res
    res.change_poss = True
    spot = st.yl + 7
    res.new_yl = 100 - max(spot, 20)
    if st.yl <= 13:
        res.new_yl = 80
    return res


def extra_point(g, kick, rng):
    res = PlayResult("xp")
    kicker = kick.special("K")
    res.kicker = kicker
    res.holder = kick.special("P")
    res.snapper = kick.special("LS")
    acc = kick.z(kicker, "K", "kick_accuracy") if kicker else -1.5
    r = rng.random()
    p_good = sigmoid(logit(data.XP_RATES["good"]) + 0.25 + T.FG_ACCURACY_K * acc + g.weather.fg_logit(33))
    if r < data.XP_RATES["blocked"]:
        res.blocked = True
    elif rng.random() < p_good:
        res.made = True
    res.elapsed = 0
    return res
