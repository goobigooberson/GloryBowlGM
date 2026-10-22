# scouting.py
# What YOUR staff knows about this year's draft prospects (Step 8, Version 1:
# interview-based scouting). The AI teams have their own boards in draft.py;
# this is the view your screens show and your staff drafts from.
#
# How it works, in plain terms:
#   - The class is announced at the start of the league year (the combine) and
#     you scout it during the free agency waves before the draft. Scouting ends
#     when the draft starts (Blake, Oct 23: "Offseason, before draft").
#   - Everyone sees the public part: age, school, height, weight, combine
#     results (with where each ranks at his position in this class), the
#     intelligence test, the position drill, where the media's big board ranks
#     him, and medical red flags (real combine medicals are shared with every
#     team).
#   - Your staff's grade of each prospect starts out about as good as an
#     average NFL staff's: it shares the league's common mistakes (what the
#     media and the combine say) plus its own. Each step clears part of the
#     mistake, so the grade moves toward the truth as you learn (it never
#     re-rolls, and it never becomes perfect):
#       film study (3 hours)       clears most of the league's shared mistake
#       cross-check (6 hours)      a second scout: clears more of both kinds
#       top-30 visit (1 of 15)     sharpens the grade the most of your own mistakes
#       interview (1 of 20)        your staff's read on the person (leadership,
#                                  loyalty, wanting to win, how steady he is), a
#                                  character red flag if he has one (85%), and
#                                  his football mind (sharpens the grade a little)
#   - Your staff's own scouting skill (the same front-office skill AI teams
#     have, draft.team_skill) sets how big its mistakes are to begin with.
# Ratings are shown as ranges on the screen scale (engine/scale.py), e.g.
# "Good (66-73)". Hidden ratings (consistency, durability, interception and
# fumble avoidance, Generational) are never shown.
#
# Budget (Blake, Oct 23: "Fewer, harder choices"): 150 hours, 20 interviews,
# 15 visits, about half the real NFL's limits (45 interviews, 30 visits), for a
# class of about 440. What each step clears is PROVISIONAL (docs/draft-design.md).

import math
import random
from datetime import date

from . import positions as pos
from . import scale
from .draft import (team_skill, starter_stats, TEAM_INSIGHT, INSIGHT_RANGE, POT_WEIGHT, AGE_VALUE, AGE_SEEN,
                    AGE_SEEN_SKILL, CONSENSUS_MISS, CONSENSUS_MISS_DEPTH, board_grade)

# ---- Knobs (budget: Blake; what each step clears: PROVISIONAL) ----------------
SCOUT_HOURS = 150            # your scouting department's hours for one draft year
FILM_HOURS = 3               # film study on one prospect
CROSS_CHECK_HOURS = 6        # a second scout's cross-check (after film study)
INTERVIEWS = 20              # formal combine interviews (real NFL limit 45)
VISITS = 15                  # top-30 pre-draft visits (real NFL limit 30)
# The league's shared mistake (draft.py's consensus miss, p._cerr): how much of it
# your staff still has. An average staff starts with all of it (a better one sees
# through part, like AI teams); each step clears this share of the whole.
SHARED_CLEARED = {"film": 0.50, "cross": 0.25, "visit": 0.10}   # never below 15%
# Your staff's own mistakes (grade units), one fixed draw per part, cleared by the
# step named; "never" stays. Sized like an AI team's own error (draft.TEAM_MISS 0.40,
# plus up to 0.50 more lower in the class): times (1 + OWN_DEPTH x how deep he is).
OWN_PARTS = {"film": 0.20, "cross": 0.15, "visit": 0.20, "interview": 0.10, "never": 0.25}
OWN_DEPTH = 1.25
PERSONALITY_MISS = 7         # interview: your staff's read of each personality trait is off by about this
CHARACTER_FOUND = 0.85       # chance an interview turns up a character red flag he has
RANGE_WIDTH = 1.0            # ranges shown = estimate +/- this many spreads of what's still unknown: the
                             # truth is inside about 2 times in 3 (with 0.67, a 50% range, a fully scouted
                             # top prospect showed a 1-2 point range: it looked like knowing the truth)
# ------------------------------------------------------------------------------

STEPS = ("film", "cross", "visit", "interview")
STEP_NAMES = {"film": "Film study", "cross": "Cross-check", "visit": "Top-30 visit", "interview": "Interview"}
PERSONALITY = ("leadership", "loyalty", "wants_winner", "volatility")
PERSONALITY_NAMES = {"leadership": "Leadership", "loyalty": "Loyalty", "wants_winner": "Wants a winner",
                     "volatility": "Volatility"}
LOW_IS_FAST = {"forty", "cone", "shuttle"}     # combine drills where a lower number is better


def state(league):
    """Your scouting this year: {pid: {"film", "cross", "visit", "interview"}} plus
    hours and slots used. Kept in league.settings so it saves with the game."""
    s = league.settings.setdefault("scouting", {})
    if s.get("season") != league.season:
        s.clear()
        s.update({"season": league.season, "hours_used": 0, "interviews_used": 0, "visits_used": 0,
                  "prospects": {}})
    return s


def budget(league):
    """What's left: {"hours": (left, of), "interviews": (left, of), "visits": (left, of)}."""
    s = state(league)
    return {"hours": (SCOUT_HOURS - s["hours_used"], SCOUT_HOURS),
            "interviews": (INTERVIEWS - s["interviews_used"], INTERVIEWS),
            "visits": (VISITS - s["visits_used"], VISITS)}


def _entry(league, pid):
    return state(league)["prospects"].get(str(pid)) or {"film": False, "cross": False, "visit": False,
                                                        "interview": False}


def done_steps(league, pid):
    """The steps your staff has done on him, in order."""
    e = _entry(league, pid)
    return [k for k in STEPS if e.get(k)]


def can_do(league, pid, what, open_=True):
    """(allowed?, why not) for 'film', 'cross', 'interview' or 'visit'.
    open_: is scouting still open (it ends when the draft starts)."""
    if not open_:
        return False, "Scouting is over: the draft has started."
    s = state(league)
    e = _entry(league, pid)
    if e.get(what):
        return False, "Already done."
    if what == "film" and s["hours_used"] + FILM_HOURS > SCOUT_HOURS:
        return False, f"Not enough scouting hours left ({SCOUT_HOURS - s['hours_used']} of {SCOUT_HOURS})."
    if what == "cross":
        if not e["film"]:
            return False, "A cross-check comes after film study."
        if s["hours_used"] + CROSS_CHECK_HOURS > SCOUT_HOURS:
            return False, f"Not enough scouting hours left ({SCOUT_HOURS - s['hours_used']} of {SCOUT_HOURS})."
    if what == "interview" and s["interviews_used"] >= INTERVIEWS:
        return False, f"All {INTERVIEWS} interviews are used."
    if what == "visit" and s["visits_used"] >= VISITS:
        return False, f"All {VISITS} top-30 visits are used."
    return True, ""


def do(league, pid, what, open_=True):
    """Spend time on a prospect. Returns (done?, message)."""
    ok, why = can_do(league, pid, what, open_)
    if not ok:
        return False, why
    s = state(league)
    e = s["prospects"].setdefault(str(pid), {"film": False, "cross": False, "visit": False, "interview": False})
    e[what] = True
    if what == "film":
        s["hours_used"] += FILM_HOURS
    elif what == "cross":
        s["hours_used"] += CROSS_CHECK_HOURS
    elif what == "interview":
        s["interviews_used"] += 1
    elif what == "visit":
        s["visits_used"] += 1
    return True, {"film": "Film study done.", "cross": "Cross-check done.", "interview": "Interview done.",
                  "visit": "Top-30 visit done."}[what]


def _draws(league, team_id, p):
    """Your staff's fixed mistakes about this prospect (one per part), so
    looking again never re-rolls them."""
    r = random.Random(f"scout-{league.settings.get('salt', '')}-{team_id}-{p.id}")
    own = {k: r.gauss(0, 1) for k in OWN_PARTS}
    return own, [r.gauss(0, 1) for _ in PERSONALITY], r.random()


def _skill_scale(league, team_id):
    """Better front offices start with smaller mistakes (draft.py's team skill)."""
    skill = team_skill(league, team_id)
    return max(INSIGHT_RANGE[0], min(INSIGHT_RANGE[1], 1 - TEAM_INSIGHT * skill))


def remaining_miss(league, team_id, p):
    """(this staff's current mistake about him in grade units, the spread of
    what it still doesn't know)."""
    e = _entry(league, p.id)
    own, _pz, _u = _draws(league, team_id, p)
    k = _skill_scale(league, team_id)
    depth = p.__dict__.get("_depth", 0.5)
    shared_left = max(0.15, 1.0 - sum(c for step, c in SHARED_CLEARED.items() if e.get(step)))
    cerr = p.__dict__.get("_cerr", 0.0)
    cerr_sd = CONSENSUS_MISS + CONSENSUS_MISS_DEPTH * depth
    size = 1.0 + OWN_DEPTH * depth
    left = [part for part in OWN_PARTS if part == "never" or not e.get(part)]
    miss = k * shared_left * cerr + sum(k * OWN_PARTS[part] * size * own[part] for part in left)
    spread = math.sqrt((k * shared_left * cerr_sd) ** 2 + sum((k * OWN_PARTS[part] * size) ** 2 for part in left))
    return miss, spread


def _true_grade(p, stats):
    g = p.__dict__.get("_grade")
    if g is not None:
        return g
    m, sd = stats.get(p.position, (65.0, 8.0))
    return POT_WEIGHT * (p.overall("potential") - m) / sd + (1 - POT_WEIGHT) * (p.overall() - m) / sd


def _character_known(league, team_id, p):
    _own, _pz, u = _draws(league, team_id, p)
    return _entry(league, p.id)["interview"] and u < CHARACTER_FOUND


def known_flag(league, team_id, p):
    """The red flag this staff knows about: "medical" (everyone sees the combine
    medicals), "character" (only if its interview turned it up) or None."""
    flag = p.__dict__.get("_flag")
    if flag == "medical" or (flag == "character" and _character_known(league, team_id, p)):
        return flag
    return None


def staff_grade(league, team_id, p, stats=None):
    """Your staff's grade of a prospect (grade units), for its board: its view
    of his ability, what it allows for his age (like an AI front office of
    the same skill), and any red flag it knows about."""
    stats = stats or starter_stats(league)
    miss, _spread = remaining_miss(league, team_id, p)
    flag = p.__dict__.get("_flag")
    known = flag == "medical" or (flag == "character" and _character_known(league, team_id, p))
    drop = p.__dict__.get("_flag_drop", 0.0) if known else 0.0
    skill = team_skill(league, team_id)
    age_k = AGE_VALUE * max(0.0, min(1.0, AGE_SEEN + AGE_SEEN_SKILL * skill))
    return _true_grade(p, stats) + miss + age_k * p.__dict__.get("_age_gap", 0.0) - drop


def staff_board(league, team_id, prospects):
    """{pid: board grade} from your staff's current view (what your staff
    drafts from; draft.DraftRoom takes it for your team)."""
    stats = starter_stats(league)
    return {p.id: board_grade(p, staff_grade(league, team_id, p, stats)) for p in prospects}


def combine_ranks(prospects):
    """{pid: {drill: (rank, of)}}: where each result ranks at his position in
    this class (1 = best), among those who did the drill; also "intel" (the
    intelligence test) and "drill" (the position drill)."""
    by_pos = {}
    for p in prospects:
        by_pos.setdefault(p.position, []).append(p)
    out = {p.id: {} for p in prospects}
    for group in by_pos.values():
        tests = {d: (lambda p, d=d: p.combine.get(d)) for d in pos.COMBINE_DRILLS}
        tests["intel"] = lambda p: p.intel_test
        tests["drill"] = lambda p: p.position_drill
        for name, get in tests.items():
            did = [p for p in group if get(p) is not None]
            did.sort(key=get, reverse=name not in LOW_IS_FAST)
            for i, p in enumerate(did):
                # ties share the better rank
                rank = i + 1
                if i and get(did[i - 1]) == get(p):
                    rank = out[did[i - 1].id][name][0]
                out[p.id][name] = (rank, len(did))
    return out


def grade_ranges(league, team_id, p, stats=None):
    """Your staff's grade of him as ranges on the screen scale: ((now low,
    high), (ceiling low, high)). stats: draft.starter_stats(league), when
    you already have it (it takes a moment to work out)."""
    stats = stats or starter_stats(league)
    _m, sd = stats.get(p.position, (65.0, 8.0))
    miss, spread = remaining_miss(league, team_id, p)
    half = RANGE_WIDTH * spread * sd
    return tuple((scale.shown(v + miss * sd - half, p.position), scale.shown(v + miss * sd + half, p.position))
                 for v in (p.overall(), p.overall("potential")))


def report(league, team_id, p, media_rank=None, stats=None):
    """Everything your screens may show about a prospect, in shown units:
    {"public": ..., "staff": {"now": (lo, hi), "ceiling": (lo, hi), "skills": {skill: {"now", "ceiling"}},
    "scouted": [steps done]}, "interview": None or {trait: shown read, "character_flag": bool}}."""
    stats = stats or starter_stats(league)
    _m, sd = stats.get(p.position, (65.0, 8.0))
    miss, spread = remaining_miss(league, team_id, p)
    e = _entry(league, p.id)
    half = RANGE_WIDTH * spread * sd

    def rng_(v):
        return scale.shown(v - half, p.position), scale.shown(v + half, p.position)
    out = {
        "public": {"age": round((date(league.season, 4, 25) - p.birth_date).days / 365.25, 1),
                   "college": p.college, "height": p.height, "weight": p.weight, "combine": dict(p.combine),
                   "intel_test": p.intel_test, "position_drill": p.position_drill, "media_rank": media_rank,
                   "medical_flag": p.__dict__.get("_flag") == "medical"},
        "staff": {"now": rng_(p.overall() + miss * sd), "ceiling": rng_(p.overall("potential") + miss * sd),
                  "skills": {}, "scouted": [k for k in STEPS if e.get(k)]},
        "interview": None,
    }
    for skill, (cur, pot_s) in p.skills.items():
        if skill in pos.HIDDEN_SKILLS:
            continue                              # hidden ratings are never shown
        out["staff"]["skills"][skill] = {"now": rng_(cur + miss * sd), "ceiling": rng_(pot_s + miss * sd)}
    if e["interview"]:
        _own, pz, _u = _draws(league, team_id, p)
        notes = {}
        for trait, zi in zip(PERSONALITY, pz):
            notes[trait] = max(1, min(99, round(getattr(p, trait) + PERSONALITY_MISS * zi)))
        notes["character_flag"] = p.__dict__.get("_flag") == "character" and _character_known(league, team_id, p)
        out["interview"] = notes
    return out
