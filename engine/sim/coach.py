# coach.py
# Coaching decisions during a game: what to call, which personnel, how the
# defense lines up, when to go for it on 4th down, two-point tries, tempo.
#
# Run-vs-pass and 4th-down choices come straight from how real NFL teams
# behaved in 2023-2025 (data.py), nudged by each team's own tendencies.

import math
from dataclasses import dataclass, field

from . import data
from . import tuning as T


def sigmoid(x):
    if x < -30:
        return 0.0
    if x > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


@dataclass
class OffCall:
    kind: str                       # run, pass, sneak, kneel, spike, hail_mary
    package: str = "11 personnel"
    concept: str = "dropback"       # pass: screen, quick, dropback, play_action, deep
    carrier: str = "RB"             # run: RB, QB, FB
    location: str = "middle"        # left, middle, right
    gap: str = "guard"              # guard, tackle, end
    tempo: str = "normal"           # normal, hurry, milk
    lineup: dict = field(default_factory=dict)
    read: float = 0.0               # called plays only (playcalling.py): the offense's edge from how
                                    # each side's calls are read, plus scheme fit; 0 for the staffs' calls


@dataclass
class DefCall:
    package: str = "Nickel"
    coverage: str = "zone"          # man or zone
    blitzers: list = field(default_factory=list)
    prevent: bool = False
    loaded: bool = False            # a safety walked down: 8 in the box
    lineup: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Situation helpers
# ---------------------------------------------------------------------------

def half_seconds(state):
    """Seconds left in the current half (or overtime)."""
    if state.qtr in (1, 3):
        return state.clock + 900
    return state.clock


def score_diff(state, team_idx):
    return state.score[team_idx] - state.score[1 - team_idx]


def is_late(state):
    return (state.qtr >= 4 and half_seconds(state) <= 300) or state.qtr >= 5


def tempo_for(state, off_idx):
    diff = score_diff(state, off_idx)
    hs = half_seconds(state)
    if state.qtr == 2 and hs <= 120 and (state.yl <= 75 or hs >= 45):
        return "hurry"
    if state.qtr >= 4:
        if diff < 0 and hs <= 300:
            return "hurry"
        if diff <= -9 and hs <= 600:
            return "hurry"
        if diff == 0 and hs <= 120 and (state.yl <= 75 or hs >= 60):
            return "hurry"           # tied late: play to win
        if diff > 0 and hs <= 720:
            return "milk"
    if state.qtr >= 3 and diff >= 17:
        return "milk"
    return "normal"


def _dist_bucket(togo):
    if togo <= 1:
        return "1"
    if togo <= 3:
        return "2-3"
    if togo <= 6:
        return "4-6"
    if togo <= 9:
        return "7-9"
    if togo == 10:
        return "10"
    if togo <= 15:
        return "11-15"
    return "16+"


def _state_key(state, off_idx):
    hs = half_seconds(state)
    if state.qtr == 2 and hs <= 120:
        return "twomin_half"
    sd = score_diff(state, off_idx)
    if -3 <= sd <= 3:
        s = "tied"
    elif 4 <= sd <= 8:
        s = "up4_8"
    elif 9 <= sd <= 16:
        s = "up9_16"
    elif sd >= 17:
        s = "up17"
    elif -8 <= sd <= -4:
        s = "dn4_8"
    elif -16 <= sd <= -9:
        s = "dn9_16"
    else:
        s = "dn17"
    if state.qtr >= 4 and hs <= 300:
        return "late_" + s
    if state.qtr >= 4:
        return "q4_" + s
    return "early_" + s


def pass_probability(state, off_idx, off_team):
    down = min(4, state.down)
    dkey = f"db_{down}&{_dist_bucket(state.togo)}"
    if state.yl <= 5:
        fz = "fz_goal5"
    elif state.yl <= 20:
        fz = "fz_red"
    elif state.yl >= 90:
        fz = "fz_own10"
    else:
        fz = "fz_open"
    skey = "st_" + _state_key(state, off_idx)
    m = data.PASS_MODEL
    x = m.get(dkey, 0.0) + m.get(fz, 0.0) + m.get(skey, 0.0) + off_team.pass_bias + T.PASS_SCALE
    lean = getattr(off_team, "untrained_qb_lean", None)
    if lean is not None:
        x += lean()          # a non-quarterback at QB: run the ball (0 with a real QB)
    return sigmoid(x)


# ---------------------------------------------------------------------------
# Offensive play call
# ---------------------------------------------------------------------------

def _weighted(rng, options):
    total = sum(w for _k, w in options)
    r = rng.random() * total
    for k, w in options:
        r -= w
        if r <= 0:
            return k
    return options[-1][0]


def choose_personnel(rng, state, is_pass, team, tempo):
    # Real 2023-25 personnel in each of these situations, defined exactly as the game defines
    # them (hurry = this file's tempo_for rules: 17.1% of real plays, the game's 18.5%; nflverse
    # participation + pbp, scratchpad real_personnel2.py; Oct 23). Groupings the game doesn't
    # have are folded into the nearest one (6 linemen into the same back/TE count; 0 backs into
    # 10 or 11). Before, short yardage used 2 backs or 3 TEs about half the time (real: 11
    # personnel 42-61%) and hurry-up offenses went 3- or 4-wide 91% of the time (real 85%).
    short = state.togo <= 2 or state.yl <= 3
    long_ = state.down >= 3 and state.togo >= 7
    if tempo == "hurry":
        opts = [("11 personnel", .84), ("12 personnel", .11), ("21 personnel", .015), ("13 personnel", .012),
                ("10 personnel", .013), ("22 personnel", .007)]
    elif short:
        opts = ([("11 personnel", .61), ("12 personnel", .215), ("13 personnel", .065), ("21 personnel", .05),
                 ("22 personnel", .04), ("10 personnel", .007)] if is_pass
                else [("11 personnel", .42), ("12 personnel", .30), ("13 personnel", .10), ("21 personnel", .09),
                      ("22 personnel", .08), ("10 personnel", .005)])
    elif long_ and is_pass:
        opts = [("11 personnel", .89), ("12 personnel", .07), ("10 personnel", .03), ("21 personnel", .01)]
    elif is_pass:
        opts = [("11 personnel", .62), ("12 personnel", .24), ("21 personnel", .078), ("13 personnel", .035),
                ("22 personnel", .011), ("10 personnel", .014)]
    else:
        opts = [("11 personnel", .49), ("12 personnel", .295), ("21 personnel", .114), ("13 personnel", .058),
                ("22 personnel", .029), ("10 personnel", .01)]
    adj = []
    for k, w in opts:
        if k in ("12 personnel", "13 personnel"):
            w *= math.exp(team.heavy_lean)
        if k in ("21 personnel", "22 personnel"):
            w *= math.exp(team.fb_lean * 1.5)
        adj.append((k, w))
    return _weighted(rng, adj)


def pass_concepts(state, tempo):
    """The coordinator's mix of pass concepts in this situation. Screens as often as real ones
    (FTN charting 2023-25, share of dropbacks): 11-12% on early downs and 2nd and long, 8% on
    3rd and 6+, 3% on 3rd and short, 5% in the hurry-up (Oct 26; were 7 / 7 / 5 / 4%)."""
    if tempo == "hurry":
        return [("dropback", .60), ("quick", .27), ("deep", .09), ("screen", .052)]
    if state.down >= 3 and state.togo >= 6:
        return [("dropback", .58), ("quick", .20), ("deep", .11), ("screen", .083), ("play_action", .04)]
    if state.down >= 3:
        return [("quick", .45), ("dropback", .40), ("screen", .028), ("play_action", .07), ("deep", .03)]
    return [("dropback", .36), ("quick", .27), ("play_action", .24), ("screen", .12), ("deep", .06)]


def must_pass(state, off_idx):
    """Must-have yardage with the clock running out: the coordinator all but always throws."""
    diff = score_diff(state, off_idx)
    hs = half_seconds(state)
    return (((state.qtr >= 4 and diff < 0 and hs <= 150) or (state.qtr == 2 and hs <= 40))
            and state.down >= 3 and state.togo >= 4)


def call_offense(rng, state, off_idx, off_team, def_team):
    tempo = tempo_for(state, off_idx)
    p_pass = pass_probability(state, off_idx, off_team)
    if must_pass(state, off_idx):
        p_pass = max(p_pass, 0.985)
    is_pass = rng.random() < p_pass
    package = choose_personnel(rng, state, is_pass, off_team, tempo)
    call = OffCall(kind="pass" if is_pass else "run", package=package, tempo=tempo)
    if is_pass:
        call.concept = _weighted(rng, pass_concepts(state, tempo))
    else:
        sneak_spot = state.togo <= 1 and (state.down >= 3 or (state.down == 2 and rng.random() < 0.25))
        if sneak_spot and rng.random() < 0.42:
            call.kind = "sneak"
            call.carrier = "QB"
            call.location = "middle"
            return call
        qb_share = sigmoid(logit(T.QB_RUN_SHARE) + T.QB_RUN_MOBILITY_K * (off_team.qb_mobility - 0.3)
                           + (T.QB_GOAL_LINE_RUN if state.yl <= 3 else 0.0))
        if rng.random() < qb_share:
            call.carrier = "QB"
        elif package in ("21 personnel", "22 personnel") and rng.random() < 0.07:
            call.carrier = "FB"
        elif state.yl > 5 and rng.random() < T.WR_RUN_SHARE:
            # Jet sweep / end-around to a receiver.
            call.carrier = "WR3" if rng.random() < 0.55 else "WR1"
            call.location = "left" if rng.random() < 0.5 else "right"
            call.gap = "end"
            return call
        else:
            call.carrier = "RB"
        call.location = _weighted(rng, [("left", .38), ("middle", .255), ("right", .365)])
        if call.location == "middle":
            call.gap = "guard"
        else:
            lean = off_team.outside_lean
            call.gap = _weighted(rng, [("guard", .36 - lean / 2), ("tackle", .33), ("end", .31 + lean / 2)])
    return call


# ---------------------------------------------------------------------------
# Calling your own plays (the Watch a game page; tools/playcall_check.py)
# ---------------------------------------------------------------------------
# The menu, in the words a fan would use, and the sim's call behind each one. You pick the
# kind of play; the coordinator fills in the rest exactly as he would for his own call of
# that kind (personnel, who carries it, which side), so a called play is the same play an AI
# coordinator would run.

PLAY_MENU = {
    "run_inside": "Inside run",
    "run_outside": "Outside run",
    "sneak": "QB sneak",
    "pass_short": "Short pass",
    "pass_medium": "Medium pass",
    "pass_long": "Deep pass",
    "screen": "Screen",
    "play_action": "Play action",
}
PASS_CHOICES = {"pass_short": "quick", "pass_medium": "dropback", "pass_long": "deep",
                "screen": "screen", "play_action": "play_action"}
RUN_CHOICES = ("run_inside", "run_outside", "sneak")


def choice_of(call):
    """The menu entry a coach's call falls under (None for kneels, spikes, Hail Marys)."""
    if call.kind == "sneak":
        return "sneak"
    if call.kind == "run":
        return "run_inside" if call.gap == "guard" else "run_outside"
    if call.kind == "pass":
        for k, concept in PASS_CHOICES.items():
            if concept == call.concept:
                return k
    return None


def _sweep_share(lean):
    """Of the coach's own outside runs by a back or receiver, the share that are jet sweeps."""
    outside = (.38 + .365) * (.33 + .31 + lean / 2)
    w = T.WR_RUN_SHARE
    return w / (w + (1 - w) * outside)


def call_for_choice(rng, state, off_idx, off_team, choice):
    """The coordinator's call of the kind you picked: everything you didn't pick (personnel,
    ball carrier, side, gap) is drawn from his own habits for that kind of play."""
    tempo = tempo_for(state, off_idx)
    if choice in PASS_CHOICES:
        package = choose_personnel(rng, state, True, off_team, tempo)
        return OffCall(kind="pass", package=package, concept=PASS_CHOICES[choice], tempo=tempo)
    package = choose_personnel(rng, state, False, off_team, tempo)
    call = OffCall(kind="run", package=package, tempo=tempo)
    if choice == "sneak":
        call.kind, call.carrier, call.location = "sneak", "QB", "middle"
        return call
    qb_share = sigmoid(logit(T.QB_RUN_SHARE) + T.QB_RUN_MOBILITY_K * (off_team.qb_mobility - 0.3)
                       + (T.QB_GOAL_LINE_RUN if state.yl <= 3 else 0.0))
    if rng.random() < qb_share:
        call.carrier = "QB"
    elif package in ("21 personnel", "22 personnel") and rng.random() < 0.07:
        call.carrier = "FB"
    elif choice == "run_outside" and state.yl > 5 and rng.random() < _sweep_share(off_team.outside_lean):
        # Jet sweep / end-around (the coach's share of his outside runs).
        call.carrier = "WR3" if rng.random() < 0.55 else "WR1"
        call.location = "left" if rng.random() < 0.5 else "right"
        call.gap = "end"
        return call
    else:
        call.carrier = "RB"
    lean = off_team.outside_lean
    if choice == "run_inside":
        # The coach's inside runs: up the middle, or off either guard.
        call.location = _weighted(rng, [("left", .38 * (.36 - lean / 2)), ("middle", .255),
                                        ("right", .365 * (.36 - lean / 2))])
        call.gap = "guard"
    else:
        call.location = _weighted(rng, [("left", .38), ("right", .365)])
        call.gap = _weighted(rng, [("tackle", .33), ("end", .31 + lean / 2)])
    return call


# The defensive menu. Personnel stays the coordinator's (it follows the offense's personnel).
DEF_MENU = {
    "zone": "Zone",
    "man": "Man",
    "zone_blitz": "Zone blitz",
    "man_blitz": "Man blitz",
    "all_out": "All-out blitz",
    "run_stop": "Stop the run",
    "prevent": "Prevent",
}
BLITZ_CHOICES = ("zone_blitz", "man_blitz", "all_out")


def def_choice_of(dcall):
    """The menu entry a defensive call falls under."""
    if dcall.prevent:
        return "prevent"
    if dcall.loaded:
        return "run_stop"
    if not dcall.blitzers:
        return dcall.coverage
    if dcall.coverage == "zone":
        return "zone_blitz"
    return "all_out" if len(dcall.blitzers) >= 2 else "man_blitz"


def _blitz_pool(package):
    # Slot corners and safeties blitz often in the modern NFL (real: about 8% of sacks come from DBs).
    return {"Base 4-3": ["WLB", "SLB", "MLB", "SS", "SS"], "Nickel": ["WLB", "MLB", "NB", "NB", "SS", "SS"],
            "Dime": ["MLB", "DB", "NB", "NB", "SS"]}[package]


def apply_def_choice(rng, dcall, choice):
    """Change the coordinator's call to the one you picked (same personnel on the field)."""
    dcall.prevent = choice == "prevent"
    dcall.loaded = choice == "run_stop" and dcall.lineup.get("SS") is not None
    if choice in ("zone", "man"):
        dcall.coverage = choice
    elif choice in ("zone_blitz", "prevent"):
        dcall.coverage = "zone"
    elif choice in ("man_blitz", "all_out"):
        dcall.coverage = "man"
    n = {"zone_blitz": 1, "man_blitz": 1, "all_out": 2}.get(choice, 0)
    blitzers = list(dcall.blitzers[:n])
    pool = _blitz_pool(dcall.package)
    while len(blitzers) < n:
        s = pool[int(rng.random() * len(pool))]
        if s not in blitzers:
            blitzers.append(s)
    dcall.blitzers = blitzers
    return dcall


# ---------------------------------------------------------------------------
# Defensive call
# ---------------------------------------------------------------------------

def call_defense(rng, state, def_idx, def_team, off_call):
    diff = score_diff(state, def_idx)
    hs = half_seconds(state)
    prevent = (diff >= 4 and ((state.qtr >= 4 and hs <= 120) or (state.qtr == 2 and hs <= 40))
               and off_call.tempo == "hurry")
    pkg = off_call.package
    long_ = state.down >= 3 and state.togo >= 7
    if off_call.tempo == "hurry" or prevent:
        opts = [("Nickel", .55), ("Dime", .45)]
    elif pkg in ("13 personnel", "22 personnel"):
        opts = [("Base 4-3", 1.0)]
    elif pkg == "21 personnel":
        opts = [("Base 4-3", .70), ("Nickel", .30)]
    elif pkg == "12 personnel":
        opts = [("Base 4-3", .50), ("Nickel", .50)]
    elif pkg == "10 personnel":
        opts = [("Dime", .60), ("Nickel", .40)]
    elif long_:
        opts = [("Nickel", .55), ("Dime", .45)]
    else:
        opts = [("Nickel", .78), ("Base 4-3", .12), ("Dime", .10)]
    package = _weighted(rng, opts)
    call = DefCall(package=package, prevent=prevent)
    call.coverage = "zone" if prevent else ("man" if rng.random() < def_team.man_rate else "zone")
    rate = def_team.blitz_rate
    if state.down >= 3 and state.togo >= 4:
        rate *= 1.3
    if prevent or off_call.tempo == "hurry":
        rate *= 0.55
    if state.yl <= 10:
        rate *= 0.9
    if rng.random() < rate:
        # Slot corners and safeties blitz often in the modern NFL (real: about 8% of sacks come from DBs).
        pool = {"Base 4-3": ["WLB", "SLB", "MLB", "SS", "SS"], "Nickel": ["WLB", "MLB", "NB", "NB", "SS", "SS"],
                "Dime": ["MLB", "DB", "NB", "NB", "SS"]}[package]
        n = 2 if rng.random() < 0.2 else 1
        call.blitzers = []
        while len(call.blitzers) < n:
            s = pool[int(rng.random() * len(pool))]
            if s not in call.blitzers:
                call.blitzers.append(s)
    return call


def load_box(rng, state, off_team, off_call, dcall, box=None):
    """Does the defense walk a safety down for an 8-man box? Decided once the
    defense sees who's in the backfield, before it knows run or pass: more
    likely against a better back, one who's hot today, and a run-heavy
    offense. Not on obvious passing downs, in the hurry-up or in dime."""
    if (off_call.kind not in ("run", "pass") or off_call.concept == "hail_mary" or off_call.tempo == "hurry"
            or dcall.prevent or dcall.package == "Dime" or dcall.lineup.get("SS") is None):
        return False
    if state.down >= 3 and state.togo >= 7:
        return False
    rb = off_call.lineup.get("RB")
    if rb is None:
        return False
    t = off_team.talent_z(rb, "RB")
    if t < T.LOAD_BOX_MIN:
        return False
    hot = box.players.get(rb.id, {}).get("rush_yds", 0) if box is not None else 0
    lean = -getattr(off_team, "pass_bias", 0.0)
    p = T.LOAD_BOX_RATE * math.exp(T.LOAD_BOX_THREAT_K * (t - 1.0) + T.LOAD_BOX_HOT_K * max(0.0, hot - 50)
                                   + T.LOAD_BOX_LEAN_K * lean)
    return rng.random() < min(T.LOAD_BOX_MAX, p)


# ---------------------------------------------------------------------------
# 4th down, field goal range, two-point tries
# ---------------------------------------------------------------------------

def fg_range(kicker_team, kicker, weather):
    """Longest field goal (yards) the coach will try in normal situations."""
    if kicker is None:
        return 35
    power = kicker_team.z(kicker, "K", "kick_power")
    # Even the strongest legs rarely try one longer than 64 in a normal spot.
    return min(64.0, 59.0 + 4.5 * power - weather.fg_range_loss())


def _zone(yl):
    for lo, hi, name in ((1, 9, "opp1-9"), (10, 19, "opp10-19"), (20, 29, "opp20-29"), (30, 34, "opp30-34"),
                         (35, 39, "opp35-39"), (40, 49, "opp40-49"), (50, 59, "mid50-59"),
                         (60, 69, "own31-40"), (70, 100, "own1-30")):
        if lo <= yl <= hi:
            return name
    return "own1-30"


def _dist4(togo):
    if togo <= 1:
        return "1"
    if togo <= 2:
        return "2"
    if togo <= 4:
        return "3-4"
    if togo <= 7:
        return "5-7"
    return "8+"


def fourth_down(rng, state, off_idx, off_team, max_fg):
    """Return 'go', 'punt' or 'field_goal'."""
    fg_dist = state.yl + 17
    in_range = fg_dist <= max_fg
    diff = score_diff(state, off_idx)
    hs = half_seconds(state)
    late = is_late(state)

    # End of half / game: kick if it's the last chance and in range.
    if state.qtr in (2, 4, 5) and hs <= 8:
        if in_range and (state.qtr == 2 or -3 <= diff <= 0 or (state.qtr == 5 and diff == 0)):
            return "field_goal"
        if state.qtr == 2:
            return "field_goal" if fg_dist <= min(67, max_fg + 4) else "go"
        return "go" if diff < 0 else ("field_goal" if in_range else "punt")

    table = data.FOURTH_DOWN.get(f"{_zone(state.yl)}|{_dist4(state.togo)}", {"punt": 1.0})
    go = table.get("go", 0.0)
    punt = table.get("punt", 0.0)
    fg = table.get("field_goal", 0.0)
    # The table reflects real kickers' range; adjust for this kicker.
    if not in_range:
        punt += fg if state.yl >= 33 else 0
        go += fg if state.yl < 33 else 0
        fg = 0.0
    elif fg_dist <= max_fg - 8 and state.yl >= 30:
        fg += punt * 0.6
        punt *= 0.4
    # Team aggression nudges the go share.
    if go > 0:
        odds = go / max(1e-6, 1 - go) * math.exp(off_team.aggression)
        new_go = odds / (1 + odds)
        scale = (1 - new_go) / max(1e-6, (1 - go))
        punt *= scale
        fg *= scale
        go = new_go
    if late:
        if diff < -3 or (diff < 0 and not in_range):
            # Need a touchdown (or no kick is available): keep the drive alive,
            # unless there's time to punt, use timeouts and get it back.
            to = off_team.timeouts
            if hs <= 120 or diff < -8:
                go_p = 0.90
            elif state.yl >= 50 and state.togo >= 5:
                go_p = 0.25 if to >= 2 else 0.50
            else:
                go_p = 0.70
            if rng.random() < go_p:
                return "go"
            return "field_goal" if (in_range and diff >= -8) else "punt"
        if -3 <= diff <= 0 and in_range:
            return "field_goal" if rng.random() < 0.78 else "go"
        if diff > 0:
            go *= 0.7
    total = go + punt + fg
    if total <= 0:
        return "punt"
    r = rng.random() * total
    if r < go:
        return "go"
    if r < go + fg:
        return "field_goal"
    return "punt"


# Two-point try rates after a touchdown, by score difference after the TD
# (offense's view) and phase of the game. Measured from 2023-2025.
_TWO_PT = {
    -2: (.27, .85, 1.0), -5: (.06, .75, 1.0), 1: (.60, .43, 1.0), 5: (.24, .64, 1.0),
    -1: (.02, .02, .15), -8: (0.0, .14, .42), -9: (0.0, .14, .42), -10: (.07, .18, .49),
    -11: (.07, .18, .49), -12: (.07, .18, .49), -13: (.07, .18, .49), -14: (.07, .18, .49), -15: (.07, .18, .49),
    2: (.04, .02, .02), -3: (.01, .04, .03), -4: (.01, .04, .03), 3: (.02, .02, .07), 4: (.02, .02, .07),
    0: (0.0, 0.0, 0.0), 6: (0.0, 0.0, .02), -6: (0.0, 0.0, 0.0), -7: (0.0, 0.0, 0.0),
}


def go_for_two(rng, state, off_idx):
    diff = score_diff(state, off_idx)          # after the touchdown
    phase = 0 if state.qtr <= 2 else (1 if state.qtr == 3 else 2)
    if diff in _TWO_PT:
        p = _TWO_PT[diff][phase]
    elif diff <= -16:
        p = (.07, .37, .35)[phase]
    else:
        p = (.03, .04, .07)[phase]
    if state.qtr >= 4 and half_seconds(state) <= 600 and diff in (-2, -5, 1, 5, -10, -9):
        p = max(p, 0.85)
    return rng.random() < p


def wants_onside(state, kick_idx):
    diff = score_diff(state, kick_idx)
    hs = half_seconds(state)
    if state.qtr < 4 or diff >= 0:
        return False
    if diff >= -16 and hs <= 150:
        return True
    if diff <= -9 and diff >= -16 and hs <= 300:
        return True
    return False
