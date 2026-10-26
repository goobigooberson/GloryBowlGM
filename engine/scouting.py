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
from . import scouting_words as W
from .draft import (team_skill, starter_stats, insight_keep, speed_term, POT_WEIGHT, AGE_VALUE, AGE_SEEN,
                    AGE_SEEN_SKILL, AGE_MEAN, CONSENSUS_MISS, CONSENSUS_MISS_DEPTH, board_grade, load_notes)

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
SHARED_TYPICAL = 0.6        # the range's league-wide part is sized this far toward a typical prospect's
                             # (measured Oct 22: with 0 the unscouted top 32 of your board had the truth
                             # inside 54% of the time, with 1.0 77%, with 0.6 about 2 in 3)
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
    return insight_keep(team_skill(league, team_id))


def _ensure_notes(league, p):
    """The class's hidden notes on this prospect (draft.py: the truth, the league's shared
    mistake, how deep in the class he is). Without them the grade would quietly use
    defaults and differ from the board's, so they're put back if they're missing."""
    if "_depth" in p.__dict__:
        return
    d = getattr(league, "draft", None)
    notes = d.get("notes") if isinstance(d, dict) else None
    if notes and str(p.id) in notes:
        load_notes([p], notes)


def _depth_of(grade):
    """How deep in the class a grade puts a prospect, 0 (top) to 1 (draft.py's _depth)."""
    return max(0.0, min(1.0, (1.5 - grade) / 3.0))


def remaining_miss(league, team_id, p, seen_grade=None, shared_grade=None):
    """(this staff's current mistake about him in grade units, the spread of
    what it still doesn't know). The spread goes by how deep in the class the
    staff THINKS he is, never his true depth (a wide range would otherwise
    quietly say he's truly worse): seen_grade is the grade it's read at
    (default: the staff's raw view of him), shared_grade the grade the
    league-wide part is read at (default: seen_grade)."""
    _ensure_notes(league, p)
    e = _entry(league, p.id)
    own, _pz, _u = _draws(league, team_id, p)
    k = _skill_scale(league, team_id)
    depth = p.__dict__.get("_depth", 0.5)
    shared_left = max(0.15, 1.0 - sum(c for step, c in SHARED_CLEARED.items() if e.get(step)))
    cerr = p.__dict__.get("_cerr", 0.0)
    size = 1.0 + OWN_DEPTH * depth
    left = [part for part in OWN_PARTS if part == "never" or not e.get(part)]
    miss = k * shared_left * cerr + sum(k * OWN_PARTS[part] * size * own[part] for part in left)
    grade = p.__dict__.get("_grade")
    if seen_grade is None and grade is not None:
        seen_grade = grade + miss
    seen = _depth_of(seen_grade) if seen_grade is not None else depth
    shared_seen = _depth_of(shared_grade) if shared_grade is not None else seen
    cerr_sd = CONSENSUS_MISS + CONSENSUS_MISS_DEPTH * shared_seen
    seen_size = 1.0 + OWN_DEPTH * seen
    spread = math.sqrt((k * shared_left * cerr_sd) ** 2
                       + sum((k * OWN_PARTS[part] * seen_size) ** 2 for part in left))
    return miss, spread


def class_prior(league, stats):
    """What a staff knows about a typical prospect in this class: (mean, spread) of
    the class's ability now, its ceiling and its draft grade, in grade units (how far from a typical
    starter at his position), all positions together. Used to read a grade the way
    a good staff does: the prospects it rates highest are, more often than not, the
    ones it overrates (the board's top is full of them)."""
    d = getattr(league, "draft", None) or {}
    pool = d.get("pool") or []
    key = (league.season, len(pool), pool[:1] and pool[0], tuple(sorted(stats.items())))
    c = league.__dict__.get("_scout_prior")
    if c and c[0] == key:
        return c[1]
    by_id = {p.id: p for p in league.players}
    zs = ([], [], [])
    for pid in pool:
        p = by_id.get(pid)
        if p is None:
            continue
        m, sd = stats.get(p.position, (65.0, 8.0))
        zs[0].append((p.overall() - m) / sd)
        zs[1].append((p.overall("potential") - m) / sd)
        zs[2].append(POT_WEIGHT * zs[1][-1] + (1 - POT_WEIGHT) * zs[0][-1])

    def ms(v):
        if len(v) < 2:
            return 0.0, 1.0
        mean = sum(v) / len(v)
        return mean, max(0.3, math.sqrt(sum((x - mean) ** 2 for x in v) / (len(v) - 1)))
    prior = (ms(zs[0]), ms(zs[1]), ms(zs[2]))
    league.__dict__["_scout_prior"] = (key, prior)
    return prior


def _reading(league, team_id, p, stats):
    """Your staff's reading of him: for his ability now and his ceiling, (the shift from
    his true rating to the middle of the range, half the range's width), in rating
    units. The staff's raw view (truth + its mistake) is pulled toward a typical
    prospect by how unsure it still is, and the width is how unsure it is after
    that, so the truth lands inside about 2 times in 3 for every kind of prospect,
    the ones it rates highest included (tools: scratchpad coverage.py of the Oct 22
    draft board session; results in the build log)."""
    m, sd = stats.get(p.position, (65.0, 8.0))
    miss, spread = remaining_miss(league, team_id, p)
    wide = spread
    grade = p.__dict__.get("_grade")
    if grade is not None:
        # How deep in the class he is, read from the pulled-in view.
        mu_g, tau_g = class_prior(league, stats)[2]
        seen = mu_g + tau_g ** 2 / (tau_g ** 2 + spread ** 2) * (grade + miss - mu_g)
        spread = remaining_miss(league, team_id, p, seen_grade=seen)[1]
        # The league-wide part of the width is read closer to a typical prospect: the
        # prospects a staff rates highest are partly ones the whole league overrates,
        # who really come from deeper in the class, where those misses are bigger.
        wide = remaining_miss(league, team_id, p, seen_grade=seen,
                              shared_grade=SHARED_TYPICAL * mu_g + (1 - SHARED_TYPICAL) * seen)[1]
    out = []
    for value, (mu, tau) in zip((p.overall(), p.overall("potential")), class_prior(league, stats)[:2]):
        z_view = (value - m) / sd + miss
        w = tau ** 2 / (tau ** 2 + spread ** 2)
        z_mid = mu + w * (z_view - mu)
        out.append(((z_mid - (value - m) / sd) * sd, RANGE_WIDTH * wide * math.sqrt(w) * sd))
    return out


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
    return (_true_grade(p, stats) + miss + age_k * p.__dict__.get("_age_gap", 0.0) + speed_term(p, skill)
            - drop)


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
    return tuple((scale.shown(v + shift - half, p.position), scale.shown(v + shift + half, p.position))
                 for v, (shift, half) in zip((p.overall(), p.overall("potential")),
                                             _reading(league, team_id, p, stats)))


def report(league, team_id, p, media_rank=None, stats=None):
    """Everything your screens may show about a prospect, in shown units:
    {"public": ..., "staff": {"now": (lo, hi), "ceiling": (lo, hi), "skills": {skill: {"now", "ceiling"}},
    "scouted": [steps done]}, "interview": None or {trait: shown read, "character_flag": bool}}."""
    stats = stats or starter_stats(league)
    (shift_now, half_now), (shift_pot, half_pot) = _reading(league, team_id, p, stats)
    e = _entry(league, p.id)

    def rng_(v, shift, half):
        return scale.shown(v + shift - half, p.position), scale.shown(v + shift + half, p.position)
    out = {
        "public": {"age": round((date(league.season, 4, 25) - p.birth_date).days / 365.25, 1),
                   "college": p.college, "height": p.height, "weight": p.weight, "combine": dict(p.combine),
                   "intel_test": p.intel_test, "position_drill": p.position_drill, "media_rank": media_rank,
                   "medical_flag": p.__dict__.get("_flag") == "medical"},
        "staff": {"now": rng_(p.overall(), shift_now, half_now),
                  "ceiling": rng_(p.overall("potential"), shift_pot, half_pot),
                  "skills": {}, "scouted": [k for k in STEPS if e.get(k)]},
        "interview": None,
    }
    for skill, (cur, pot_s) in p.skills.items():
        if skill in pos.HIDDEN_SKILLS:
            continue                              # hidden ratings are never shown
        out["staff"]["skills"][skill] = {"now": rng_(cur, shift_now, half_now),
                                         "ceiling": rng_(pot_s, shift_pot, half_pot)}
    if e["interview"]:
        _own, pz, _u = _draws(league, team_id, p)
        notes = {}
        for trait, zi in zip(PERSONALITY, pz):
            notes[trait] = max(1, min(99, round(getattr(p, trait) + PERSONALITY_MISS * zi)))
        notes["character_flag"] = p.__dict__.get("_flag") == "character" and _character_known(league, team_id, p)
        out["interview"] = notes
    return out


# ---------------------------------------------------------------------------
# What your staff says about him (Blake, Oct 22: FOF8's "underrated / overrated"
# idea in scout slang, scout's notes, two scouts who can disagree until a
# cross-check, round projections). All of it comes from your staff's view, so it
# can be wrong; better staffs (draft.team_skill) are wrong less. Wording:
# scouting_words.py.
# ---------------------------------------------------------------------------
IMPRESSION_SPLIT = (0.55, 1.15)  # board-grade gap between your staff's view and what a player at his media
                                 # rank usually turns out to be: Sleeper / Overhyped from the first, Hidden
                                 # gem / Fool's gold from the second (Oct 22: about 15% and 10% each, whole
                                 # class scouted)
RAW_WILD = 0.85                  # a Wild card: his ceiling this many spreads above what he is now (raw;
RAW_WILD_YOUNG = 0.65            # this much if he's 21.5 or younger), until a top-30 visit sorts him out
SCOUT_SPLIT = 1.0                # the two scouts sit this many of the cross-check part's spreads apart
NOTE_MISREAD = {"film": 0.5, "cross": 0.25, "visit": 0.1}  # per-skill misread in the notes, by how far
                                 # your scouting has gone (film, then a cross-check, then a visit)
NOTE_STRONG = 0.5                # a skill this many spreads above (below) a typical prospect at his
                                 # position in this class is a strength (weakness) worth a note


def _board_view(league, team_id, p, stats):
    return board_grade(p, staff_grade(league, team_id, p, stats))


def _media_grades(league):
    """The class's media board grades, best first (for turning a grade into a pick)."""
    d = getattr(league, "draft", None) or {}
    pool = d.get("pool") or []
    key = (league.season, len(pool), pool[:1] and pool[0])
    c = league.__dict__.get("_scout_media")
    if c and c[0] == key:
        return c[1]
    by_id = {p.id: p for p in league.players}
    grades = []
    for pid in pool:
        p = by_id.get(pid)
        if p is None:
            continue
        _ensure_notes(league, p)
        grades.append(p.__dict__.get("_media", -9.0))
    grades.sort(reverse=True)
    league.__dict__["_scout_media"] = (key, grades)
    return grades


def media_worth(league, p):
    """What a player at his place on the media's big board usually turns out to be
    (board-grade units): big boards regress to the mean (their top prospects are, more
    often than not, ones the media overrates), and every front office knows it from
    years of drafts. Measured on the class: the straight-line fit of true draft value
    on the media's grade."""
    d = getattr(league, "draft", None) or {}
    pool = d.get("pool") or []
    key = (league.season, len(pool), pool[:1] and pool[0])
    c = league.__dict__.get("_scout_worth")
    if not (c and c[0] == key):
        by_id = {q.id: q for q in league.players}
        xs, ys = [], []
        for pid in pool:
            q = by_id.get(pid)
            if q is None:
                continue
            _ensure_notes(league, q)
            if "_media" in q.__dict__:
                xs.append(q._media)
                ys.append(board_grade(q, q._grade + AGE_VALUE * q._age_gap))
        if len(xs) > 2:
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            var = sum((x - mx) ** 2 for x in xs)
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else 1.0
            fit = (my - slope * mx, slope)
        else:
            fit = (0.0, 1.0)
        c = (key, fit)
        league.__dict__["_scout_worth"] = c
    a, b = c[1]
    return a + b * p.__dict__.get("_media", 0.0)


def projected_pick(league, grade):
    """Where a board grade would go in this draft: 1 + the prospects the media ranks above it."""
    grades = _media_grades(league)
    lo, hi = 0, len(grades)
    while lo < hi:                      # grades are best first
        mid = (lo + hi) // 2
        if grades[mid] > grade:
            lo = mid + 1
        else:
            hi = mid
    return lo + 1


def ordinal_word(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


def round_text(pick, n_teams=32, rounds=7):
    """A pick number in scout language: 'Top-5 talent', 'Late 1st', 'Mid 3rd',
    'Undrafted free agent'..."""
    if pick <= 5:
        return "Top-5 talent"
    if pick <= 15:
        return "Top-half 1st"
    if pick <= n_teams:
        return "Late 1st"
    rnd = (pick - 1) // n_teams + 1
    if rnd > rounds:
        return "Undrafted free agent" if pick <= rounds * n_teams * 1.35 else "Camp body"
    third = ("Early", "Mid", "Late")[min(2, ((pick - 1) % n_teams) * 3 // n_teams)]
    return f"{third} {ordinal_word(rnd)}"


def impression(league, team_id, p, stats=None):
    """Your staff's impression of him vs his buzz, once its scouts have watched his
    film: {"key", "word", "color", "tip"} (scouting_words.IMPRESSIONS), or None."""
    if not _entry(league, p.id).get("film"):
        return None
    stats = stats or starter_stats(league)
    m, sd = stats.get(p.position, (65.0, 8.0))
    raw = (p.overall("potential") - p.overall()) / sd
    age = p.__dict__.get("_age_gap", 0.0) + AGE_MEAN
    if not _entry(league, p.id).get("visit") and (raw >= RAW_WILD or (raw >= RAW_WILD_YOUNG and age <= 21.5)):
        key = "wild"
    else:
        gap = _board_view(league, team_id, p, stats) - media_worth(league, p)
        small, big = IMPRESSION_SPLIT
        key = ("gem" if gap >= big else "sleeper" if gap >= small else "fools" if gap <= -big
               else "hyped" if gap <= -small else "fair")
    word, color, tip = W.IMPRESSIONS[key]
    return {"key": key, "word": word, "color": color, "tip": tip}


def projections(league, team_id, p, stats=None, media_rank=None):
    """Where he'd go, in scout language: {"media": the media's projection,
    "staff": your staff's (None before film study), "scouts": [(scout, projection),
    (scout, projection)] while your two scouts still disagree (after film study,
    before the cross-check), else None}."""
    stats = stats or starter_stats(league)
    out = {"media": round_text(media_rank) if media_rank else None, "staff": None, "scouts": None}
    e = _entry(league, p.id)
    if not e.get("film"):
        return out
    g = _board_view(league, team_id, p, stats)
    out["staff"] = round_text(projected_pick(league, g))
    if not e.get("cross"):
        r = random.Random(f"scouts-{league.settings.get('salt', '')}-{team_id}-{p.id}")
        depth = p.__dict__.get("_depth", 0.5)
        d = (abs(r.gauss(0, 1)) * SCOUT_SPLIT * _skill_scale(league, team_id) * OWN_PARTS["cross"]
             * (1.0 + OWN_DEPTH * depth))
        sign = 1 if r.random() < 0.5 else -1
        out["scouts"] = [(W.SCOUTS[0], round_text(projected_pick(league, g + sign * d))),
                         (W.SCOUTS[1], round_text(projected_pick(league, g - sign * d)))]
    return out


def _class_skills(league, position):
    """{skill: (mean, spread)} of this class's prospects at a position (ability now)."""
    d = getattr(league, "draft", None) or {}
    pool = d.get("pool") or []
    key = (league.season, len(pool), position)
    cache = league.__dict__.setdefault("_scout_skills", {})
    if key in cache:
        return cache[key]
    by_id = {p.id: p for p in league.players}
    vals = {}
    for pid in pool:
        p = by_id.get(pid)
        if p is not None and p.position == position:
            for s, (cur, _pot) in p.skills.items():
                vals.setdefault(s, []).append(cur)
    out = {}
    for s, v in vals.items():
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1))
        out[s] = (m, max(2.0, sd))
    cache[key] = out
    return out


def report_interview(league, team_id, p):
    """Your staff's interview reads ({trait: shown read, "character_flag": bool}), or None."""
    if not _entry(league, p.id).get("interview"):
        return None
    _own, pz, _u = _draws(league, team_id, p)
    reads = {trait: max(1, min(99, round(getattr(p, trait) + PERSONALITY_MISS * zi)))
             for trait, zi in zip(PERSONALITY, pz)}
    reads["character_flag"] = p.__dict__.get("_flag") == "character" and _character_known(league, team_id, p)
    return reads


def notes(league, team_id, p, stats=None, combine=None):
    """Your scouts' notes on him: [{"kind": "film" | "person", "text"}]. Film notes
    (his best and worst, tape vs stopwatch) once they've watched his film; notes on
    the person once he's interviewed. combine: his combine ranks ({drill: (rank, of)})."""
    stats = stats or starter_stats(league)
    e = _entry(league, p.id)
    out = []
    if e.get("film"):
        (shift, _half), _pot = _reading(league, team_id, p, stats)
        r = random.Random(f"notes-{league.settings.get('salt', '')}-{team_id}-{p.id}")
        level = "visit" if e.get("visit") else "cross" if e.get("cross") else "film"
        misread = NOTE_MISREAD[level]
        typical = _class_skills(league, p.position)
        zs = {}
        for s, _w in pos.POSITIONS[p.position][1]:
            if s in pos.HIDDEN_SKILLS or s not in typical or s in ("kick_return", "punt_return", "endurance"):
                continue
            m, sd = typical[s]
            zs[s] = (p.skills[s][0] + shift - m) / sd + r.gauss(0, misread)
        ranked = sorted(zs.items(), key=lambda kv: kv[1], reverse=True)
        for s, z in ranked[:2]:
            if z >= NOTE_STRONG:
                out.append({"kind": "film", "text": r.choice(W.phrases(W.STRENGTH, s, p.position))})
        if ranked and ranked[-1][1] <= -NOTE_STRONG:
            out.append({"kind": "film", "text": r.choice(W.phrases(W.WEAKNESS, ranked[-1][0], p.position))})
        # Tape vs stopwatch: the skills that run on speed, against his 40 time.
        fast = [zs[s] for s in zs if pos.SKILLS[s][1].get("speed", 0) >= 0.3]
        forty = (combine or {}).get("forty")
        if fast and forty:
            play = sum(fast) / len(fast)
            pct = forty[0] / forty[1]                # near 0 = fastest at his position in the class
            if play >= 0.6 and pct >= 0.6:
                out.append({"kind": "film", "text": r.choice(W.PLAYS_FASTER)})
            elif play <= -0.4 and pct <= 0.25:
                out.append({"kind": "film", "text": r.choice(W.TIMED_FASTER)})
        imp = impression(league, team_id, p, stats)
        if imp and imp["key"] == "wild":
            out.append({"kind": "film", "text": r.choice(W.WILD)})
    reads = report_interview(league, team_id, p)
    if reads:
        r = random.Random(f"person-{league.settings.get('salt', '')}-{team_id}-{p.id}")
        extremes = []
        for trait in PERSONALITY:
            v = reads[trait]
            if v >= 75:
                extremes.append((v - 50, (trait, "high")))
            elif v <= 30:
                extremes.append((50 - v, (trait, "low")))
        for _d, k in sorted(extremes, reverse=True)[:2]:
            out.append({"kind": "person", "text": r.choice(W.PERSON[k])})
        out.append({"kind": "person", "text": W.CHARACTER if reads["character_flag"] else W.CLEAN})
    return out


# ---------------------------------------------------------------------------
# Developed % (Blake, Oct 22: the bars shrink toward your staff's view of his potential;
# "the developed % will determine what they come into the league with their current
# rating at", like FOF8). Your staff's estimate of how much of his potential he already
# has, with a fixed mistake that shrinks as you scout (better staffs err less).
# ---------------------------------------------------------------------------
# Oct 25: Developed % is now counted from a raw starting point (player.developed_share), which
# spreads a class about twice as wide (drafted rookies' spread ~27 points, was ~13), so the
# staff's mistake is twice as many points: the same share of the spread as before.
DEVELOPED_MISS = {"none": 12.0, "film": 8.0, "cross": 6.0, "visit": 4.0}   # percentage points (1 spread)


def developed(league, team_id, p):
    """Your staff's estimate of his Developed % (how far he has come from raw toward his
    potential: player.developed_share), a whole number."""
    from .player import developed_share
    true = developed_share(p.overall(), p.overall("potential"))
    e = _entry(league, p.id)
    level = "visit" if e.get("visit") else "cross" if e.get("cross") else "film" if e.get("film") else "none"
    z = random.Random(f"devl-{league.settings.get('salt', '')}-{team_id}-{p.id}").gauss(0, 1)
    # Never 100: a scouting guess doesn't say a prospect has nothing left to grow.
    return max(1, min(99, round(true + z * DEVELOPED_MISS[level] * _skill_scale(league, team_id))))
