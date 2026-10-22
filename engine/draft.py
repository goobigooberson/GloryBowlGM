# draft.py
# The NFL draft (Step 8): each year's draft class and how the 31 AI teams
# (and your staff, when you let it pick) draft it. Built to match the real
# NFL, measured from nflverse draft data (docs/research/real_draft_*.md) and
# checked with tools/draft_check.py. Design and open decisions for Blake:
# docs/draft-design.md.
#
# How it works, in plain terms:
#   1. The class. For each position, a pool of college prospects is made and
#      the best of it enter the draft (the same filter that built the
#      starting league), set a little lower so the league's talent level
#      holds steady over the years. Each prospect gets a real age at the
#      draft (top prospects are often 21-year-old juniors) and a readiness:
#      how much of his ceiling he already has (older prospects are more
#      finished, younger ones have more growing to do).
#   2. What everyone thinks of him. The league's scouts share a "consensus"
#      view that is close to the truth at the top of the class and gets
#      fuzzier further down (a real big board). A few prospects carry a red
#      flag (medical or character) that drops them down boards.
#   3. Each team's own board: the consensus plus its own scouting error.
#      Some front offices scout better than others, every year (real NFL:
#      team drafting skill persists).
#   4. Each pick: the team takes the best player on its board, nudged by
#      need (a team with a good young starter at a one-man position, like
#      QB or TE, rarely spends a high pick there). A team with a good young
#      QB never takes a QB in rounds 1-2.
#   5. Draft-day trades: a team that badly wants a player still on the board
#      trades up, paying by the Jimmy Johnson chart (what real teams do).
#
# Nothing here touches the screens. offseason.py calls make_class() and
# run_draft() (see the integration steps at the end of docs/draft-design.md).

import math
import random
from collections import defaultdict
from datetime import date, timedelta

from . import colleges
from .league import roster_value, GENERATIONAL_RATE
from .player import generate_player
from .teams import ROSTER_TEMPLATE, ROSTER_SIZE

# ---- The class ---------------------------------------------------------------
ROUNDS = 7
CLASS_PER_PICK = 1.4         # prospects in the class per draft pick (plus the fringe below)
# Each position's share of a class: the real NFL's yearly new players there, i.e. real
# draft picks per draft (2014-26, nflverse; generic OL/DB/LB/DL split by the real
# position mix and this game's roster template) divided by the share of that
# position's players who were drafted at all (colleges.DRAFT_BY_POSITION), so the
# undrafted ones are counted too (most kickers, snappers and fullbacks).
# (Oct 23: classes used to be sized by each position's openings on the rosters at
# draft time. With 90-man camps, rosters then hold last year's practice squads and
# pre-draft free agents, so a WR room looked full and the class had 12-17 WRs:
# 19.7 drafted a draft vs real 28.6, while DE/LB classes ballooned.)
REAL_PICKS = {"QB": 11.6, "RB": 20.3, "FB": 1.1, "TE": 14.8, "WR": 32.9, "T": 21.8, "G": 14.7, "C": 7.6,
              "DE": 20.8, "DT": 24.6, "OLB": 17.0, "ILB": 12.8, "CB": 31.1, "S": 21.0, "K": 1.9, "P": 1.9,
              "LS": 0.7}
# QBs last longer in this game than the real mix allows for: with the real share
# (17 a class) QB starters climbed 8 points over 22 seasons. Class size factor by position.
POS_CLASS = {"QB": 0.65}
OPENINGS_K = 1.0             # and a little more (less) where the league is short (long) of players:
OPENINGS_RANGE = (0.75, 1.35)  # x e^(this x share of the position's roster spots open), within these limits
# The game announces the class at the start of the league year (so you can scout it,
# draft_day.py), when rosters still hold last year's practice squads and expiring deals,
# not after four waves of free agency as when the class plan above was tuned. Measured
# (3 leagues x 6 offseasons, scratchpad plan_timing.py): the openings then make K/P/LS/FB
# classes ~25% bigger and QB/TE/CB ~7-14% smaller than on draft day, and over 22 seasons
# K/P/LS starters crept up 3-4 points and QB starters slipped 2. Class size factors that
# bring the early plan back to the draft-day mix on average (each year's class still
# follows that year's shortages).
CLASS_EARLY = {"QB": 1.14, "RB": 1.06, "FB": 0.73, "TE": 1.09, "WR": 0.98, "T": 1.03, "C": 0.96,
               "DE": 1.02, "DT": 0.98, "ILB": 1.03, "CB": 1.07, "K": 0.73, "P": 0.80, "LS": 0.79}
POOL = 2.5                   # prospects made per class spot; the class is the best of them
CLASS_FRINGE = 0.4           # plus this share more from the next tier down (undrafted long shots)
LEVEL_SHIFT = -10            # rating points the class is set below the pool (league level steady)
SHIFT_TAPER = (86, 96)       # full shift up to this potential, none from this one (top prospects)
# Positions whose classes sit higher or lower than that (rating points), so each
# position's picks turn out like the real ones (QB: real first-round QBs start 3+
# seasons 76% of the time and half make a Pro Bowl).
# Set so every position's starters hold their level over 22 seasons (6 leagues,
# with free agency and 90-man camps, Oct 23; a point here moves a position's
# starters about a point in the long run).
POS_LEVEL = {"QB": 0, "WR": -2, "TE": -3, "T": -3, "G": -2, "C": -2, "FB": -4, "DE": -2, "DT": -2,
             "OLB": -2, "ILB": -2, "S": -2, "CB": -3, "P": -1, "LS": 2}
GENERATIONAL_CAREER = 10     # new Generational players a year = GENERATIONAL_RATE x spots / this
# Readiness: share of his ceiling a prospect has already reached (each skill),
# at the average draft age; older prospects are a little more finished.
READY_MEAN = 0.88
READY_PER_YEAR = 0.01        # per year of age above/below the average
READY_SD = 0.05
READY_SKILL_SD = 0.03
READY_RANGE = (0.62, 0.98)
# Age at the draft (real 2000-2018: round 1 averages 21.8, round 7 22.8;
# 11% are 21 or younger, 37% 22, 41% 23, 11% 24+ by PFR's count).
AGE_MEAN = 22.35
AGE_TALENT = 0.45            # years younger for the class's best (early entrants)
AGE_SD = 0.75
AGE_RANGE = (20.6, 25.8)
DRAFT_DAY = (4, 25)          # month, day

# ---- What the league thinks of him -------------------------------------------
# Everything below is in "grade" units: spreads of the league's starters at his
# position (a grade of +1 = as good as a starter one spread above average).
POT_WEIGHT = 0.7             # how much teams grade the ceiling vs what he is now
CONSENSUS_MISS = 0.60        # how far the shared view can be from the truth for the obvious top prospects...
CONSENSUS_MISS_DEPTH = 1.00  # ...plus up to this much more for prospects lower in the class
CONSENSUS_CAP = 1.8          # but never more than this (grade): scouts can be well off on a mid-round
                             # prospect, not so far off that a nobody looks like a top-10 talent (an
                             # uncapped spread put busts with true grades of -1.5 in the top 10)
TEAM_MISS = 0.40             # each team's own error on top of the shared view...
TEAM_MISS_DEPTH = 0.50       # ...plus up to this much more lower in the class
TEAM_INSIGHT = 0.35          # better front offices see through part of the shared mistake:
                             # a team with skill +1 keeps 55% of it, -1 145% (skill ~ N(0, 1))
INSIGHT_RANGE = (0.25, 1.75)
# Age: an older prospect has less growing left and a shorter career, worth about
# AGE_VALUE grade per year older than the average. Real teams only see part of it
# (real 24+ year-olds return 0.88 of their slot, 21-22 year-olds 1.22-1.25), the
# best front offices more of it.
AGE_VALUE = -0.28
AGE_SEEN = 0.85              # share an average front office allows for...
AGE_SEEN_SKILL = 0.2         # ...plus this much per point of skill
RED_FLAG_RATE = 0.05         # share of prospects with a medical or character red flag
RED_FLAG_DROP = (0.8, 2.6)   # how far a flag drops him on boards (grade); the public big boards
                             # don't know about it, so he "falls"
RED_FLAG_TEAM = (0.4, 1.3)   # teams weigh a flag differently (share of the drop on their board)
MEDICAL_DURABILITY = (12, 32)  # a medical flag is real: his durability is set in this range
# Position value: grade points added on every board, so positions go in the
# rounds they really go in (real 2014-26: QB 3.2 in round 1, TE 1.0, K/P never).
POS_SHIFT = {"QB": 0.45, "RB": -0.45, "FB": -2.6, "WR": 0.10, "TE": -0.15, "T": 0.45, "G": -0.10,
             "C": -0.25, "DE": 0.10, "DT": 0.30, "OLB": -0.45, "ILB": -0.55, "CB": -0.20, "S": -0.35,
             "K": -3.0, "P": -3.1, "LS": -3.6}
# Stars at a few positions are worth more than their grade says: a franchise QB
# goes first (real: the first QB taken is the 1st pick, median), a feature back
# in the top 10, but a merely good QB prospect waits (real: 3.2 QBs in round 1,
# 0.7 in round 2). Grade added per grade point above STAR_GRADE.
STAR_GRADE = 0.6
POS_STAR = {"QB": 0.8, "RB": 0.3}

# ---- Each pick ---------------------------------------------------------------
NEED_K = 0.40                # grade added per spread a prospect would improve the team's weakest starter
NEED_RANGE = (-1.6, 1.2)     # limits on that upgrade (spreads)
DEPTH_SHORT = 0.20           # grade added when the team is short of bodies at the position
STARTERS_FOR_NEED = {"QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 1, "T": 2, "G": 2, "C": 1, "DE": 2,
                     "DT": 2, "OLB": 2, "ILB": 1, "CB": 3, "S": 2, "K": 1, "P": 1, "LS": 1}
# A recent high pick at the position (rounds 1-2 in the last 3 drafts, still on the
# team) makes another one there much less likely, most at one-man positions (real:
# after a 1st-rounder there, QB 15% -> 6%, TE 10 -> 3, RB 15 -> 7, WR 32 -> 16,
# but OL 36 -> 29 and DB 37 -> 34). Grade taken off per such player.
SAME_DRAFT = 0.5             # grade off per player already taken at the position in this draft
                             # (divided by its starters: a second WR is fine, a second QB rare)
RECENT_PICK = {"QB": 0.6, "RB": 0.6, "FB": 0.9, "TE": 0.7, "WR": 0.35, "T": 0.15, "G": 0.15, "C": 0.3,
               "DE": 0.05, "DT": 0.3, "OLB": 0.25, "ILB": 0.35, "CB": 0.05, "S": 0.1, "K": 2.0, "P": 2.0,
               "LS": 2.0}
# QB rule (real 2003-26: 0 of 58 teams with a young, good starting QB took a QB in
# rounds 1-2). Young = his first 4 seasons, drafted in rounds 1-2. Good = graded at
# least this many spreads above the league's average starter.
QB_GOOD = 0.30
QB_BLOCK = -6.0              # grade on that team's board for QBs in rounds 1-2 (never)
# The other QB situations (real chance of a 1st-round QB: young not good 5%, older
# and good 3%, older and not good 17%): grade added to QBs on the team's board.
QB_SITUATION = {"young": -0.10, "good": -0.30, "other": 0.50}
QB_OLD_AGE = 33              # a team whose good starter is this old leans toward a successor
QB_SUCCESSOR = 0.35

# ---- Draft-day trades ----------------------------------------------------------
TRADE_WINDOW = (4, 24)       # a team trades up this many spots (fewest, most)...
TRADE_WINDOW_LATE = 6        # ...at least this many from round 3 on (real median 10-12)
TRADE_URGE = (0.40, 0.18, 0.25)           # grade a team must gain (its man now vs at its own pick) to trade up
TRADE_DOWN_COST = 0.45       # most grade the team on the clock will give up to move down
# Of the deals that make sense, the share that actually get made, by pick (real per draft:
# picks 1-10 0.8 trades, 11-32 2.7, 33-64 5.6, 65-128 6.2, 129+ 5.8).
TRADE_CHANCE = [(10, 0.75), (32, 0.55), (64, 0.55), (128, 0.75), (999, 0.6)]
TRADE_PREMIUM = (-0.05, 0.03)  # between AI teams the price is chart value x (1 + this), as close as the
                               # picks allow (real median 0.98-1.01). Deals with you: never below the chart.

# Jimmy Johnson trade chart (1990s, still how real teams price draft-day deals:
# 2010-26 same-year pick trades were 0.98-1.12 by this chart). Points between
# the anchors are filled in a straight line.
JJ_ANCHORS = [(1, 3000), (2, 2600), (3, 2200), (4, 1800), (5, 1700), (6, 1600), (7, 1500), (8, 1400),
              (9, 1350), (10, 1300), (16, 1000), (20, 850), (32, 590), (33, 580), (48, 420), (60, 300),
              (64, 270), (96, 116), (100, 100), (128, 43), (160, 27.4), (192, 15.2), (224, 3.6), (262, 1.0)]
# What picks really turn into (career AV of real picks 2000-18, pick 1 = 3000). Much flatter
# than the Johnson chart: real teams moving up overpay by ~30-50% by this measure.
OUTCOME_ANCHORS = [(1, 3000), (2, 2452), (3, 2298), (5, 2098), (10, 1856), (16, 1729), (20, 1472),
                   (32, 1386), (48, 1054), (64, 962), (96, 648), (128, 519), (160, 358), (192, 279),
                   (224, 237), (262, 222)]


def _interp(anchors, x):
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return anchors[-1][1]


def jj_value(pick):
    """Jimmy Johnson chart points for an overall pick number."""
    return _interp(JJ_ANCHORS, pick)


def outcome_value(pick):
    """What a pick is really worth, on the same scale (real career outcomes)."""
    return _interp(OUTCOME_ANCHORS, pick)


# ---------------------------------------------------------------------------
# League yardsticks
# ---------------------------------------------------------------------------

def starter_stats(league):
    """{position: (average, spread)} of the overall ratings of each team's
    starters there (its top players by the starter count), the yardstick a
    prospect is graded against."""
    out = {}
    for position, n in STARTERS_FOR_NEED.items():
        vals = []
        for t in league.teams:
            group = sorted((p.overall() for p in league.team_players(t.id) if p.position == position),
                           reverse=True)
            vals += group[:n]
        if len(vals) >= 2:
            m = sum(vals) / len(vals)
            sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))
            out[position] = (m, max(sd, 3.0))
        else:
            out[position] = (65.0, 8.0)
    return out


def team_skill(league, team_id):
    """A front office's scouting skill (about -2 .. +2, average 0). Since Oct 24
    it's the team's director of college scouting (staff.py: his evaluation
    skill against the league's), so it changes when he does; a league without
    staffs keeps a fixed skill per team for the whole save (real: a team's
    drafting in odd years predicts its even years, correlation 0.53)."""
    if getattr(league, "staff", None):
        from .evaluation import _eval_z
        return round(max(-2.5, min(2.5, _eval_z(league, team_id, "college"))), 3)
    skills = league.settings.setdefault("draft_skill", {})
    key = str(team_id)
    if key not in skills:
        rng = random.Random(f"draft-skill-{league.settings.get('salt', '')}-{team_id}")
        skills[key] = round(rng.gauss(0, 1), 3)
    return skills[key]


# ---------------------------------------------------------------------------
# 1. The class
# ---------------------------------------------------------------------------

def _age_at_draft(p, season):
    d = date(season, *DRAFT_DAY)
    return (d - p.birth_date).days / 365.25


def _class_plan(league, early=False):
    """{position: class size}: the real NFL's mix of new players by position
    (REAL_PICKS / drafted share), nudged up where the league's rosters are
    short at a position and down where they're long. early: the class is
    made at the start of the league year (the game: draft_day.py), not on
    draft day (CLASS_EARLY)."""
    n_teams = len(league.teams)
    counts = defaultdict(int)
    for pid in league.rosters:
        counts[league.player(pid).position] += 1
    weight = {}
    for position, per_team in ROSTER_TEMPLATE.items():
        entrants = REAL_PICKS[position] / colleges.DRAFT_BY_POSITION[position][0]
        spots = per_team * n_teams
        open_share = (spots - counts[position]) / spots
        nudge = max(OPENINGS_RANGE[0], min(OPENINGS_RANGE[1], math.exp(OPENINGS_K * open_share)))
        weight[position] = (entrants * nudge * POS_CLASS.get(position, 1.0)
                            * (CLASS_EARLY.get(position, 1.0) if early else 1.0))
    total = CLASS_PER_PICK * ROUNDS * n_teams
    scale = total / sum(weight.values())
    return {position: max(2, round(w * scale)) for position, w in weight.items()}


def make_class(league, rng, early=False):
    """This year's draft class: a list of Player objects (not yet in
    league.players). Each carries hidden draft info in p.__dict__ (removed
    by finish()): "_grade" (the truth, in grade units), "_consensus" (what
    the league's scouts think), "_flag" (None, "medical" or "character").
    early: made at the start of the league year (draft_day.new_class)."""
    plan = _class_plan(league, early)
    n_teams = len(league.teams)
    per_year = GENERATIONAL_RATE * ROSTER_SIZE * n_teams / GENERATIONAL_CAREER
    gen_odds = per_year / sum(POOL * n for n in plan.values())
    stats = starter_stats(league)
    state = random.getstate()
    random.seed(rng.random())          # player generation uses Python's shared dice
    prospects = []
    try:
        for position, size in plan.items():
            pool = []
            for _ in range(round(size * POOL)):
                generational = rng.random() < gen_odds and league.generational_allowed(position)
                pool.append(generate_player(position, experience=0, season_year=league.season,
                                            generational=generational))
            pool.sort(key=roster_value, reverse=True)
            # The class, plus the next tier of the pool: the long shots who sign as
            # undrafted free agents and fill practice squads (real teams sign ~500
            # undrafted rookies a year to fill 90-man camp rosters).
            chosen = pool[:size + round(size * CLASS_FRINGE)]
            for rank, p in enumerate(chosen):
                _shape_prospect(p, position, min(1.0, rank / max(1, size - 1)), league.season, rng)
            prospects.extend(chosen)
    finally:
        random.setstate(state)
    for p in prospects:
        p.draft_year = league.season
        p.draft_round = 0
        _grade(p, stats, league.season, rng)
    # Schools, by the round the media expects him to go in (real first-rounders come
    # mostly from big programs). Set once here: you scout him at his school, so it
    # can't change on draft day (it used to be drawn by the round he went in).
    picks = ROUNDS * n_teams
    for rank, p in enumerate(sorted(prospects, key=lambda p: p._media, reverse=True)):
        p.college = colleges.pick_college(rank // n_teams + 1 if rank < picks else 0)
    return prospects


def _shape_prospect(p, position, pct, season, rng):
    """Level, age and readiness for one prospect. pct: 0 = the best of his
    position's class, 1 = the last one in."""
    # Level: the class sits a little below the pool it came from, the top
    # prospects less so (see offseason.py's history of this setting: it keeps
    # the league's level and spread steady over many seasons).
    shift = 0 if p.generational else LEVEL_SHIFT
    if shift and SHIFT_TAPER and position not in ("K", "P", "LS"):
        lo, hi = SHIFT_TAPER
        shift = shift * max(0.0, min(1.0, (hi - p.overall("potential")) / (hi - lo)))
    shift = round(shift + (0 if p.generational else POS_LEVEL.get(position, 0)))
    # Age: the best prospects tend to be early entrants.
    z = 1.0 - 2.0 * pct                          # +1 best .. -1 last in
    age = AGE_MEAN - AGE_TALENT * z + rng.gauss(0, AGE_SD)
    age = max(AGE_RANGE[0], min(AGE_RANGE[1], age))
    p.birth_date = date(season, *DRAFT_DAY) - timedelta(days=round(age * 365.25))
    # Readiness: how much of his ceiling he already has.
    ready = READY_MEAN + READY_PER_YEAR * (age - AGE_MEAN) + rng.gauss(0, READY_SD)
    skills = {}
    for skill, (cur, pot) in p.skills.items():
        if position == "RB" and skill == "endurance":
            skills[skill] = (cur, pot)
            continue
        pot2 = max(1, min(99, pot + shift))
        r = max(READY_RANGE[0], min(READY_RANGE[1], ready + rng.gauss(0, READY_SKILL_SD)))
        skills[skill] = (max(1, min(pot2, round(pot2 * r))), pot2)
    p.skills = skills
    p.position_drill = max(1, min(99, round(p.overall() + rng.gauss(0, 7))))


def _grade(p, stats, season, rng):
    """The truth about him (p._grade) and what the league's scouts think
    (p._consensus), in grade units (see the knobs above)."""
    m, sd = stats.get(p.position, (65.0, 8.0))
    pot_z = (p.overall("potential") - m) / sd
    cur_z = (p.overall() - m) / sd
    age = _age_at_draft(p, season)
    true = POT_WEIGHT * pot_z + (1 - POT_WEIGHT) * cur_z
    p._grade = true
    # The shared view: tighter for the obvious top prospects (they've been
    # watched for years), fuzzier further down. Real teams also give older
    # prospects a little too much credit (AGE_BIAS: real 24+ year-olds
    # return 0.88 of their slot, 21-22 year-olds 1.22-1.25).
    depth = max(0.0, min(1.0, (1.5 - true) / 3.0))
    p._depth = depth
    p._cerr = _capped(rng, CONSENSUS_MISS + CONSENSUS_MISS_DEPTH * depth, CONSENSUS_CAP)
    p._age_bias = AGE_VALUE * AGE_SEEN * (age - AGE_MEAN)
    p._age_gap = age - AGE_MEAN
    p._flag = None
    p._flag_drop = 0.0
    if rng.random() < RED_FLAG_RATE:
        p._flag = "medical" if rng.random() < 0.6 else "character"
        p._flag_drop = rng.uniform(*RED_FLAG_DROP)
        if p._flag == "medical":
            p.durability = rng.randint(*MEDICAL_DURABILITY)
    p._consensus = board_grade(p, true + p._cerr + p._age_bias - p._flag_drop)
    # The public big board (media): the same view, but it doesn't know about red flags.
    p._media = board_grade(p, true + p._cerr + p._age_bias)


def regrade(prospects, stats):
    """On draft day, measure the class against the league as it is then (the
    class is announced before the league year, and free agency moves players
    around in between): the same scouting misses and red flags, today's
    yardsticks. stats: starter_stats(league)."""
    for p in prospects:
        m, sd = stats.get(p.position, (65.0, 8.0))
        true = POT_WEIGHT * (p.overall("potential") - m) / sd + (1 - POT_WEIGHT) * (p.overall() - m) / sd
        p._grade = true
        p._consensus = board_grade(p, true + p._cerr + p._age_bias - p._flag_drop)
        p._media = board_grade(p, true + p._cerr + p._age_bias)


def _capped(rng, sd, cap):
    """A random miss with this spread, redrawn until it's inside +/- cap."""
    while True:
        x = rng.gauss(0, sd)
        if abs(x) <= cap:
            return x


def board_grade(p, view):
    """A view of a prospect (grade units) -> where he goes on a board: his
    position's value, and the star premium at QB and RB."""
    g = view + POS_SHIFT.get(p.position, 0.0)
    star = POS_STAR.get(p.position)
    if star and view > STAR_GRADE:
        g += star * (view - STAR_GRADE)
    return g


# ---------------------------------------------------------------------------
# 2. Team boards and needs
# ---------------------------------------------------------------------------

def team_boards(league, prospects, rng, misses=None):
    """{team id: {pid: grade on that team's board}}. Each team's view is the
    consensus plus its own error (smaller for better front offices).
    misses: a dict to fill with {team id: {pid: how far its view of his
    ability is off, in grade units}} (used after the draft, for signing
    undrafted rookies by what the team thinks of them)."""
    boards = {}
    for t in league.teams:
        skill = team_skill(league, t.id)
        keep = max(INSIGHT_RANGE[0], min(INSIGHT_RANGE[1], 1 - TEAM_INSIGHT * skill))
        age_k = AGE_VALUE * max(0.0, min(1.0, AGE_SEEN + AGE_SEEN_SKILL * skill))
        r = random.Random(f"board-{league.settings.get('salt', '')}-{league.season}-{t.id}")
        board = {}
        miss = {}
        for p in prospects:
            noise = r.gauss(0, TEAM_MISS + TEAM_MISS_DEPTH * p._depth)
            flag = p._flag_drop * r.uniform(*RED_FLAG_TEAM)
            view = p._grade + keep * p._cerr + age_k * p._age_gap - flag + noise
            board[p.id] = board_grade(p, view)
            miss[p.id] = keep * p._cerr + noise - flag
        boards[t.id] = board
        if misses is not None:
            misses[t.id] = miss
    return boards


def _future(p, season):
    """About what he'll be in a season or two: young players grow toward
    their ceiling, veterans past their prime slip."""
    from .development import peak_seasons, season_number
    cur, pot = p.overall(), p.overall("potential")
    if p.experience <= 3:
        return cur + 0.5 * (pot - cur)
    _start, end = peak_seasons(p)
    past = season_number(p) - end
    return cur - (1.5 * past if past > 0 else 0)


def team_needs(league, team_id, stats):
    """{position: (weakest starter's rating in a season or two, bodies on the
    roster)} for one team, and its QB situation, as its staff sees its players."""
    from .evaluation import seen
    by_pos = defaultdict(list)
    for p in league.team_players(team_id):
        by_pos[p.position].append(seen(league, team_id, p))
    # Recent high picks still on the team, by position.
    recent = defaultdict(int)
    for d in league.draft_history:
        if (d["team"] == team_id and d["round"] <= 2 and league.season - 3 <= d["season"] < league.season
                and league.rosters.get(d["pid"]) == team_id):
            recent[league.player(d["pid"]).position] += 1
    need = {}
    for position, n in STARTERS_FOR_NEED.items():
        futs = sorted((_future(p, league.season) for p in by_pos[position]), reverse=True)
        weakest = futs[n - 1] if len(futs) >= n else (stats[position][0] - 2 * stats[position][1])
        need[position] = (weakest, len(by_pos[position]), recent[position])
    qb = qb_situation(league, team_id, stats)
    return need, qb


def qb_situation(league, team_id, stats):
    """'young_good', 'young', 'good', 'other' (the real-data groups), as the
    team's staff sees its quarterback."""
    from .evaluation import overall
    chart = league.depth_charts.get(team_id, {})
    ids = [pid for pid in chart.get("QB", []) if league.rosters.get(pid) == team_id]
    if not ids:
        qbs = [p for p in league.team_players(team_id) if p.position == "QB"]
        if not qbs:
            return "other", None
        qb = max(qbs, key=lambda p: overall(league, team_id, p))
    else:
        qb = league.player(ids[0])
    m, sd = stats["QB"]
    good = (overall(league, team_id, qb) - m) / sd >= QB_GOOD
    young = qb.experience <= 3 and qb.draft_round in (1, 2)
    if young:
        return ("young_good" if good else "young"), qb
    return ("good" if good else "other"), qb


def soon(p):
    """About what a prospect will be in a season or two."""
    return 0.4 * p.overall() + 0.6 * p.overall("potential")


def pick_score(p, board_grade, need, qb, rnd, stats, season, mine=None):
    """How much this team wants this prospect right now (grade units)."""
    position = p.position
    m, sd = stats[position]
    weakest, bodies, recent = need[position]
    mine = soon(p) if mine is None else mine
    upgrade = max(NEED_RANGE[0], min(NEED_RANGE[1], (mine - weakest) / sd))
    score = board_grade + NEED_K * upgrade
    if bodies < ROSTER_TEMPLATE[position]:
        score += DEPTH_SHORT
    if recent:
        score -= RECENT_PICK.get(position, 0.3) * recent
    if position == "QB":
        kind, starter = qb
        if kind == "young_good":
            if rnd <= 2:
                score += QB_BLOCK
        else:
            score += QB_SITUATION.get(kind, 0.0)
            if kind == "good" and starter is not None and starter.age(date(season, 9, 1)) >= QB_OLD_AGE:
                score += QB_SUCCESSOR
    return score


# ---------------------------------------------------------------------------
# 3. The draft
# ---------------------------------------------------------------------------

def pick_slots(order, rounds=ROUNDS):
    """Every pick of the draft: [{"pick": overall number, "round", "team": owner,
    "from": original team}], in order."""
    slots = []
    n = 0
    for rnd in range(1, rounds + 1):
        for tid in order:
            n += 1
            slots.append({"pick": n, "round": rnd, "team": tid, "from": tid})
    return slots


class DraftRoom:
    """One year's draft, pick by pick. The AI makes every pick unless a team
    is listed in `humans` (your team when you draft yourself): then the
    draft stops at that pick (on_clock() returns the slot) until you call
    make_pick(). State is plain data (to_dict / from_dict) so a draft can be
    saved halfway through."""

    def __init__(self, league, prospects, order, rng, humans=(), boards_override=None):
        self.league = league
        self.season = league.season
        self.prospects = {p.id: p for p in prospects}
        self.available = [p.id for p in prospects]
        self.slots = pick_slots(order)
        self.next = 0                       # index into slots
        self.picks = []                     # made picks
        self.trades = []                    # draft-day trades
        self.humans = set(humans)
        self.rng = rng
        self.stats = starter_stats(league)
        self.misses = {}
        self.boards = team_boards(league, prospects, rng, self.misses)
        # Your team's board comes from your own scouting (scouting.staff_board),
        # so your staff's auto-picks use what you've learned, not the truth.
        for tid, board in (boards_override or {}).items():
            self.boards[tid] = dict(board)
        self.needs = {}
        self._prep()

    def _prep(self):
        self.notes = {}
        self.qb_before = {t.id: qb_situation(self.league, t.id, self.stats)[0] for t in self.league.teams}
        self.soon = {pid: soon(p) for pid, p in self.prospects.items()}
        ranked = sorted(self.prospects.values(), key=lambda p: getattr(p, "_media", 0.0), reverse=True)
        self.board_rank = {p.id: i + 1 for i, p in enumerate(ranked)}

    # ---- helpers ----
    def _need(self, tid):
        if tid not in self.needs:
            self.needs[tid] = team_needs(self.league, tid, self.stats)
        return self.needs[tid]

    def scores(self, tid, rnd):
        """[(score, pid)] best first, this team's view of who's left."""
        need, qb = self._need(tid)
        board = self.boards[tid]
        # Already took one (or more) at this position in this draft: less keen on another.
        taken = defaultdict(int)
        for pk in self.picks:
            if pk["team"] == tid:
                taken[self.prospects[pk["pid"]].position] += 1
        out = [(pick_score(self.prospects[pid], board[pid], need, qb, rnd, self.stats, self.season,
                           self.soon[pid])
                - SAME_DRAFT * taken[self.prospects[pid].position] / STARTERS_FOR_NEED[self.prospects[pid].position],
                pid)
               for pid in self.available]
        out.sort(reverse=True)
        return out

    def on_clock(self):
        """The slot that's up next, or None when the draft is over."""
        return self.slots[self.next] if self.next < len(self.slots) else None

    def make_pick(self, pid):
        slot = self.on_clock()
        p = self.prospects[pid]
        self.available.remove(pid)
        p.draft_round = slot["round"]
        self.league.rosters[pid] = slot["team"]
        self.needs.pop(slot["team"], None)
        self.picks.append({"season": self.season, "round": slot["round"], "pick": slot["pick"],
                           "team": slot["team"], "pid": pid, "from": slot["from"],
                           "board_rank": self.board_rank.get(pid)})
        # Hidden notes for the check tools (not saved with the draft history).
        self.notes[pid] = {"grade": getattr(p, "_grade", None), "flag": getattr(p, "_flag", None),
                           "age": round(_age_at_draft(p, self.season), 2), "pos": p.position,
                           "qb": self.qb_before.get(slot["team"])}
        self.next += 1
        return self.picks[-1]

    def ai_pick(self):
        slot = self.on_clock()
        best = self.scores(slot["team"], slot["round"])
        return self.make_pick(best[0][1])

    def run(self, until_human=True):
        """Make AI picks (and trades) until a human team is on the clock or the
        draft ends. Returns the slot that's waiting, or None."""
        while self.on_clock() is not None:
            slot = self.on_clock()
            if slot["team"] in self.humans and until_human:
                return slot
            self.try_trade_up()
            slot = self.on_clock()
            if slot["team"] in self.humans and until_human:
                return slot
            self.ai_pick()
        return None

    # ---- trades ----
    def _later_slots(self, tid, start):
        return [i for i in range(start, len(self.slots)) if self.slots[i]["team"] == tid]

    def _package(self, buyer, j, price):
        """The buyer's pick j plus the fewest, closest-to-fair later picks of
        his (at most 3 in all) worth at least `price` chart points, or None."""
        from itertools import combinations
        base = jj_value(self.slots[j]["pick"])
        extra = self._later_slots(buyer, j + 1)
        best = None
        for n in (0, 1, 2):
            for combo in combinations(extra, n):
                v = base + sum(jj_value(self.slots[k]["pick"]) for k in combo)
                if v >= price and (best is None or v < best[0]):
                    best = (v, [j, *combo])
            if best is not None:
                return best[1]
        return None

    def try_trade_up(self):
        """Before the team on the clock picks: does someone a few spots back
        want a player here badly enough to trade up, and will the team on the
        clock move down? Both sides price it by the Jimmy Johnson chart."""
        i = self.next
        slot = self.slots[i]
        owner = slot["team"]
        if owner in self.humans:
            return None
        rnd = slot["round"]
        mine = self.scores(owner, rnd)
        if len(mine) < 3:
            return None
        offers = []
        seen = set()
        fewest = TRADE_WINDOW[0] if rnd <= 2 else TRADE_WINDOW_LATE
        for j in range(i + fewest, min(len(self.slots), i + 1 + TRADE_WINDOW[1])):
            buyer = self.slots[j]["team"]
            if buyer == owner or buyer in seen or buyer in self.humans:
                continue
            seen.add(buyer)
            theirs = self.scores(buyer, self.slots[j]["round"])
            gap = j - i                     # players likely gone before the buyer's own pick
            if len(theirs) <= gap:
                continue
            urge = theirs[0][0] - theirs[gap][0]
            if urge < TRADE_URGE[min(rnd, 3) - 1]:
                continue
            # The team on the clock: what it loses by picking at j instead.
            cost = mine[0][0] - mine[min(gap, len(mine) - 1)][0]
            if cost > TRADE_DOWN_COST:
                continue
            offers.append((urge, j, buyer))
        if not offers or self.rng.random() > next(ch for top, ch in TRADE_CHANCE if slot["pick"] <= top):
            return None
        # The team on the clock takes calls from everyone interested; the
        # keenest are likelier to get the deal done.
        _urge, j, buyer = self.rng.choices(offers, weights=[u * (j - i) ** 2 for u, j, _b in offers])[0]
        price = jj_value(slot["pick"]) * (1 + self.rng.uniform(*TRADE_PREMIUM))
        give = self._package(buyer, j, price)
        if give is None:
            return None
        value = sum(jj_value(self.slots[k]["pick"]) for k in give)
        for k in give:
            self.slots[k]["team"] = owner
        self.slots[i]["team"] = buyer
        self.needs.pop(owner, None)
        self.needs.pop(buyer, None)
        deal = {"season": self.season, "up": buyer, "down": owner, "got": [slot["pick"]],
                "gave": [self.slots[k]["pick"] for k in give], "jj_ratio": round(value / jj_value(slot["pick"]), 3)}
        self.trades.append(deal)
        return deal

    def offers_to(self, team_id, most=3):
        """When your team is on the clock: AI teams behind you that want to
        trade up into your pick, each with the package it offers (its picks,
        by the Jimmy Johnson chart, at least full value). [{"team", "gives":
        [overall picks], "chart_points", "for_pick"}], keenest first."""
        i = self.next
        slot = self.slots[i]
        if slot["team"] != team_id:
            return []
        rnd = slot["round"]
        out = []
        seen = set()
        fewest = TRADE_WINDOW[0] if rnd <= 2 else TRADE_WINDOW_LATE
        for j in range(i + fewest, min(len(self.slots), i + 1 + TRADE_WINDOW[1])):
            buyer = self.slots[j]["team"]
            if buyer == team_id or buyer in seen or buyer in self.humans:
                continue
            seen.add(buyer)
            theirs = self.scores(buyer, self.slots[j]["round"])
            gap = j - i
            if len(theirs) <= gap or theirs[0][0] - theirs[gap][0] < TRADE_URGE[min(rnd, 3) - 1]:
                continue
            give = self._package(buyer, j, jj_value(slot["pick"]))
            if give:
                out.append({"team": buyer, "gives": [self.slots[k]["pick"] for k in give],
                            "chart_points": round(sum(jj_value(self.slots[k]["pick"]) for k in give)),
                            "for_pick": slot["pick"], "urge": theirs[0][0] - theirs[gap][0]})
        out.sort(key=lambda o: o["urge"], reverse=True)
        return out[:most]

    def staff_pick(self):
        """Your staff picks for you (the best on your board, with your needs)."""
        return self.ai_pick()

    def offer(self, from_team, to_team, give_picks, get_picks):
        """Would the AI team to_team accept this deal (overall pick numbers of
        this draft)? It accepts when it gets at least chart value."""
        owned = {s["pick"]: s["team"] for s in self.slots[self.next:]}
        if any(owned.get(k) != from_team for k in give_picks) or any(owned.get(k) != to_team for k in get_picks):
            return False, "Those picks aren't theirs to trade (or have been used)."
        give = sum(jj_value(k) for k in give_picks)
        get = sum(jj_value(k) for k in get_picks)
        if give < get:
            return False, f"Not enough: {give:.0f} chart points for {get:.0f}."
        return True, f"{give:.0f} chart points for {get:.0f}."

    def accept(self, from_team, to_team, give_picks, get_picks):
        ok, why = self.offer(from_team, to_team, give_picks, get_picks)
        if not ok:
            return False, why
        for s in self.slots[self.next:]:
            if s["pick"] in give_picks:
                s["team"] = to_team
            elif s["pick"] in get_picks:
                s["team"] = from_team
        self.needs.pop(from_team, None)
        self.needs.pop(to_team, None)
        self.trades.append({"season": self.season, "up": from_team, "down": to_team, "got": list(get_picks),
                            "gave": list(give_picks),
                            "jj_ratio": round(sum(map(jj_value, give_picks)) / sum(map(jj_value, get_picks)), 3)})
        return True, why

    # ---- saving ----
    def to_dict(self):
        return {"season": self.season, "available": list(self.available), "slots": [dict(s) for s in self.slots],
                "next": self.next, "picks": list(self.picks), "trades": list(self.trades),
                "humans": sorted(self.humans), "boards": {str(t): b for t, b in self.boards.items()}}

    @classmethod
    def from_dict(cls, league, prospects, d, rng):
        room = cls.__new__(cls)
        room.league = league
        room.season = d["season"]
        room.prospects = {p.id: p for p in prospects}
        room.available = list(d["available"])
        room.slots = [dict(s) for s in d["slots"]]
        room.next = d["next"]
        room.picks = list(d["picks"])
        room.trades = list(d["trades"])
        room.humans = set(d["humans"])
        room.rng = rng
        room.stats = starter_stats(league)
        room.boards = {int(t): {int(k): v for k, v in b.items()} for t, b in d["boards"].items()}
        room.needs = {}
        room.misses = {}
        room._prep()
        return room


def run_draft(league, prospects, order, rng, humans=()):
    """The whole draft, AI picking for everyone (offseason.py's drop-in for
    its placeholder). Returns (picks, undrafted prospects). Trades made are
    kept in league.settings["draft_trades"] (last few years)."""
    room = DraftRoom(league, prospects, order, rng, humans=())
    room.run(until_human=False)
    picked = {pk["pid"] for pk in room.picks}
    undrafted = [p for p in prospects if p.id not in picked]
    league.__dict__["_last_draft"] = room
    return room.picks, undrafted


STREET_SHIFT = -1            # a made-up street free agent: this much below an undrafted rookie's level


def street_free_agent(position=None, experience=None, season_year=2026, generational=False, rng_seed=None):
    """A made-up young street free agent (for when no real free agent is
    left: practice squads, emergency signings). Same arguments as
    player.generate_player, but he's at the level of an undrafted rookie
    who didn't stick, not the starting league's. (transactions.py and
    offseason.py made these with generate_player, at full starting-league
    level: ~60 a year in the draft harness, and after 15 seasons 16.5% of all
    starters were these players, an outside source of talent that pushed
    the league's level up.)"""
    p = generate_player(position, experience=experience, season_year=season_year, generational=False,
                        rng_seed=rng_seed)
    exp = p.experience
    ready = min(READY_RANGE[1], READY_MEAN + 0.04 * exp + random.gauss(0, READY_SD))
    skills = {}
    for skill, (cur, pot) in p.skills.items():
        if p.position == "RB" and skill == "endurance":
            skills[skill] = (cur, pot)
            continue
        pot2 = max(1, min(99, pot + LEVEL_SHIFT + STREET_SHIFT))
        r = max(READY_RANGE[0], min(READY_RANGE[1], ready + random.gauss(0, READY_SKILL_SD)))
        skills[skill] = (max(1, min(pot2, round(pot2 * r))), pot2)
    p.skills = skills
    p.draft_round = 0
    p.college = colleges.pick_college(0)
    return p


UDFA_PER_TEAM = 8            # undrafted rookies a team signs to camp (real teams sign ~15 to fill a
                             # 90-man camp roster; the cut to 53 keeps the ones who earn it)


def sign_undrafted(league, undrafted, rng):
    """After the draft each team signs a few undrafted rookies who look
    better than its weakest player at the position: by what its scouts think
    of them (the draft boards), not by their true ratings. (offseason.py's
    placeholder signs by true ratings, so teams saw through every undrafted
    prospect: 19% of starters were undrafted, real 13%, and late-round picks
    started too rarely.) Its own weakest player there is judged by its staff
    too (evaluation.py). Returns ([(pid, team id)], the unsigned)."""
    from . import evaluation as E
    room = league.__dict__.get("_last_draft")
    stats = room.stats if room else starter_stats(league)
    misses = room.misses if room else {}
    signed = []
    pool = list(undrafted)
    for t in sorted(league.teams, key=lambda t: rng.random()):
        miss = misses.get(t.id, {})

        def seen(p):
            sd = stats.get(p.position, (65.0, 8.0))[1]
            return roster_value(p) + miss.get(p.id, 0.0) * sd
        roster = league.team_players(t.id)
        own = {x.id: roster_value(E.seen(league, t.id, x)) for x in roster}
        n = 0
        for p in sorted(pool, key=seen, reverse=True):
            if n >= UDFA_PER_TEAM:
                break
            same = [x for x in roster if x.position == p.position]
            worst = min(same, key=lambda x: own[x.id]) if same else None
            if worst is None or seen(p) > own[worst.id] + 1:
                league.rosters[p.id] = t.id
                pool.remove(p)
                roster.append(p)
                own[p.id] = seen(p)
                signed.append((p.id, t.id))
                n += 1
    return signed, pool


_NOTE_KEYS = ("_grade", "_consensus", "_media", "_flag", "_cerr", "_depth", "_age_bias", "_age_gap", "_flag_drop")


def save_notes(prospects):
    """The class's hidden draft notes as plain data, for saving a class
    between offseason stages (the database saves players, not these):
    {pid: {key: value}}."""
    return {str(p.id): {k: p.__dict__.get(k) for k in _NOTE_KEYS} for p in prospects}


def load_notes(prospects, notes):
    """Put saved notes back on the prospects (see save_notes)."""
    for p in prospects:
        for k, v in (notes.get(str(p.id)) or {}).items():
            p.__dict__[k] = v


def finish(prospects):
    """Remove the hidden draft-day notes from the prospects once the draft is done."""
    for p in prospects:
        for k in _NOTE_KEYS:
            p.__dict__.pop(k, None)


# ---------------------------------------------------------------------------
# Draft capital: staffs give their high picks a real chance
# ---------------------------------------------------------------------------
# Real teams start their high picks more than the players' play alone would
# earn (they invested a high pick and want to see what they have; NFL studies
# of playing time vs draft slot find the same "sunk cost" effect). Without it,
# 15% of the sim's top-5 picks never started a game (real 2%). Rating points
# added to a young drafted player when an AI staff sets its depth chart (not
# in games, and never on a depth chart you set yourself), by round, for his
# 1st, 2nd and 3rd seasons. PROVISIONAL (Blake): docs/draft-design.md.
DRAFT_CAPITAL = {1: (2.5, 1.5, 0.5), 2: (3.0, 2.0, 1.0), 3: (1.5, 1.0, 0.5), 4: (0.75, 0.5, 0.0)}
TOP_PICK_EXTRA = (3.5, 2.5, 1.5)   # and more for top-10 picks


def draft_capital(p, overall_pick=None):
    """Depth chart nudge (rating points) for a young drafted player."""
    if not p.draft_round or p.experience > 2:
        return 0.0
    by_year = DRAFT_CAPITAL.get(p.draft_round)
    if not by_year:
        return 0.0
    bonus = by_year[p.experience]
    if overall_pick is not None and overall_pick <= 10:
        bonus += TOP_PICK_EXTRA[p.experience]
    return bonus


# ---------------------------------------------------------------------------
# The startup draft: a new league's teams draft every player (Blake's main way
# to start a league). PROVISIONAL: docs/draft-design.md, "Startup draft".
# ---------------------------------------------------------------------------
STARTUP_SNAKE = True          # the order reverses every round (fairest for 53 rounds)
STARTUP_NOW_WEIGHT = 0.6      # veterans are graded more on what they are now than on their ceiling
STARTUP_PAST_PRIME = 0.15     # spreads of his position off per season past his prime (fewer good years left)
STARTUP_MISS = 0.60           # each team's error on a veteran (he has pro tape)...
STARTUP_MISS_YOUNG = 0.90     # ...and on a player with 0-1 seasons
# How a team values a pick (Oct 23; the first version graded each player only against
# his own position, so a team saw a good guard and a good QB alike and waited on QB:
# in 6 test leagues 112 of 192 teams took their first QB after round 5, some in round
# 25, and 8 started a QB rated under 45). Now, like real team-building: what he adds over
# the starter the team would be stuck with if it waited (the worst starter-level player
# still left at his position, counting every team's open starting spots), times how much
# the position matters (the depth chart's spot importance: QB 3.0, LT 1.3, most 1.0).
# Results: see docs/build-log.md, "Startup draft QB fix".
STARTUP_POS_WEIGHT = {"QB": 3.0, "RB": 1.0, "FB": 0.4, "WR": 1.1, "TE": 1.0, "T": 1.2, "G": 1.0, "C": 1.1,
                      "DE": 1.2, "DT": 1.0, "OLB": 0.95, "ILB": 1.1, "CB": 1.03, "S": 1.03,
                      "K": 0.3, "P": 0.25, "LS": 0.1}
# (Specialists: the depth chart gives them 1.0, but their ratings spread wider and a rating
# point there moves games far less; at 1.0 kickers, punters and snappers went in rounds 1-2.
# With these, each team's first K goes around round 22, P 23, LS 38; none in rounds 1-3.)
STARTUP_WAIT_DEPTH = 8        # a team never counts on getting better than the 8th best player left at a
                              # position by waiting (others take players too)
STARTUP_QB_EAGER = 0.05       # a team still without a QB gets this much keener on one each round after
STARTUP_QB_EAGER_FROM = 3     # this one, but only for a QB better than what it would find later (Blake,
                              # Oct 22: no reaching for the best of a bad bunch; a round-12 QB is fine
                              # when that's what makes sense. Replaced a hard 'QB by round 4' rule.)
STARTUP_BACKUP_SHARE = 0.25   # a backup is worth this share of a starter (insurance), measured against
                              # the worst player who'll make a roster there, and half again for each more


class StartupRoom:
    """The startup draft, pick by pick (so you can make your own picks and
    save halfway; draft_day.py runs it for the game). Every rostered and
    practice squad player goes back in the pool and the teams draft full
    53-man rosters (each position to its roster count), snake order. AI teams
    (and your staff, when it picks for you) take the best player on their own
    board for a spot they still have open, starters first; better front
    offices judge players better (team_skill). State is plain data (to_dict /
    from_dict): the boards are rebuilt the same way from the league's dice."""

    def __init__(self, league, humans=(), order=None, pool_ids=None):
        from .development import peak_seasons, season_number
        self.league = league
        if pool_ids is None:
            pool = [p for p in league.players
                    if p.retired is None and (p.id in league.rosters or p.id in league.practice)]
            for p in pool:
                league.rosters.pop(p.id, None)
                league.practice.pop(p.id, None)
        else:
            pool = [league.player(pid) for pid in pool_ids]
        self.pool = pool
        self.humans = set(humans)
        self.order = list(order or [t.id for t in league.teams])
        stats = starter_stats_from(pool)
        # Each team's view of each player, in rating points: what he is now and a bit of
        # his ceiling, less for seasons past his prime, plus its own scouting error
        # (smaller for better front offices).
        self.views = {}
        for t in league.teams:
            skill = team_skill(league, t.id)
            keep = max(INSIGHT_RANGE[0], min(INSIGHT_RANGE[1], 1 - TEAM_INSIGHT * skill))
            r = random.Random(f"startup-{league.settings.get('salt', '')}-{t.id}")
            v = {}
            for p in pool:
                _m, sd = stats.get(p.position, (65.0, 8.0))
                g = (STARTUP_NOW_WEIGHT * p.overall() + (1 - STARTUP_NOW_WEIGHT) * p.overall("potential"))
                _start, end = peak_seasons(p)
                g -= STARTUP_PAST_PRIME * sd * max(0, season_number(p) - end)
                miss = STARTUP_MISS_YOUNG if p.experience <= 1 else STARTUP_MISS
                v[p.id] = g + keep * sd * r.gauss(0, miss)
            self.views[t.id] = v
        # Each team's best remaining player at each position, by its own view.
        by_pos = defaultdict(list)
        for p in pool:
            by_pos[p.position].append(p)
        self.lists = {t.id: {pos_: sorted(g, key=lambda p, tid=t.id: self.views[tid][p.id], reverse=True)
                             for pos_, g in by_pos.items()} for t in league.teams}
        self.taken = set()
        self.have = {t.id: defaultdict(int) for t in league.teams}
        self.picks = []
        n = len(league.teams)
        # Open spots league-wide: starting spots, and all roster spots, by position.
        self.open_start = {pos_: n * STARTERS_FOR_NEED.get(pos_, 1) for pos_ in ROSTER_TEMPLATE}
        self.open_all = {pos_: n * k for pos_, k in ROSTER_TEMPLATE.items()}

    def _filled(self, tid, position):
        """Bookkeeping when a team adds a player at a position."""
        have = self.have[tid][position]
        if have < STARTERS_FOR_NEED.get(position, 1):
            self.open_start[position] -= 1
        if have < ROSTER_TEMPLATE.get(position, 0):
            self.open_all[position] -= 1
        self.have[tid][position] = have + 1

    def _kth(self, tid, position, k):
        """This team's view of the k-th best player still left at a position
        (the worst of them if fewer are left)."""
        last = None
        for p in self.lists[tid][position]:
            if p.id in self.taken:
                continue
            last = self.views[tid][p.id]
            k -= 1
            if k <= 0:
                break
        return last

    def on_clock(self):
        """{"pick", "round", "team"} that's up next, or None when it's over."""
        n = len(self.picks)
        per = len(self.order)
        if n >= ROSTER_SIZE * per:
            return None
        rnd = n // per + 1
        this = self.order if (not STARTUP_SNAKE or rnd % 2 == 1) else list(reversed(self.order))
        return {"pick": n + 1, "round": rnd, "team": this[n % per]}

    def open_spots(self, tid):
        """{position: spots still open on this team's roster}."""
        return {pos_: ROSTER_TEMPLATE[pos_] - self.have[tid][pos_] for pos_ in ROSTER_TEMPLATE
                if self.have[tid][pos_] < ROSTER_TEMPLATE[pos_]}

    def score(self, tid, p, _repl=None):
        """How much this team wants him now: what he adds over the player it would
        be stuck with at his position if it waited, times how much the position
        matters (STARTUP_POS_WEIGHT); a backup much less (STARTUP_BACKUP_SHARE)."""
        position = p.position
        backups = self.have[tid][position] - STARTERS_FOR_NEED.get(position, 1)
        if backups < 0:            # a starting spot: against the worst starter-level player left
            k, share = max(STARTUP_WAIT_DEPTH, self.open_start[position]), 1.0
        else:                      # a backup: against the worst player left who'll make a roster
            k, share = max(1, self.open_all[position]), STARTUP_BACKUP_SHARE * 0.5 ** backups
        repl = _repl if _repl is not None else self._kth(tid, position, k)
        value = share * STARTUP_POS_WEIGHT.get(position, 1.0) * (self.views[tid][p.id] - repl)
        if position == "QB" and backups < 0 and value > 0:
            # No QB yet: a little keener each round, only for one worth more than waiting.
            n = len(self.picks) // len(self.order) + 1
            value *= 1 + STARTUP_QB_EAGER * max(0, n - STARTUP_QB_EAGER_FROM)
        return value

    def scores(self, tid, players):
        """{pid: score(tid, p)} for many players at once (the screens' board)."""
        repl = {}
        out = {}
        for p in players:
            key = (p.position, self.have[tid][p.position] >= STARTERS_FOR_NEED.get(p.position, 1))
            if key not in repl:
                backups = self.have[tid][p.position] - STARTERS_FOR_NEED.get(p.position, 1)
                k = (max(STARTUP_WAIT_DEPTH, self.open_start[p.position]) if backups < 0
                     else max(1, self.open_all[p.position]))
                repl[key] = self._kth(tid, p.position, k)
            out[p.id] = self.score(tid, p, repl[key])
        return out

    def best(self, tid):
        """The player this team takes now: the best on its board for a spot it
        still has open (starters first)."""
        best = None
        for pos_, lst in self.lists[tid].items():
            if self.have[tid][pos_] >= ROSTER_TEMPLATE.get(pos_, 0):
                continue
            while lst and lst[0].id in self.taken:
                lst.pop(0)
            if not lst:
                continue
            cand = lst[0]
            if self.have[tid][pos_] >= STARTERS_FOR_NEED.get(pos_, 1):
                # A backup: not one good enough to start for a team that still needs a
                # starter here (no team hoards a second starting QB while others have none).
                cand = self._nth_left(tid, pos_, self.open_start[pos_] + 1)
                if cand is None:
                    continue
            score = self.score(tid, cand)
            if best is None or score > best[0]:
                best = (score, cand)
        return best[1]

    def _nth_left(self, tid, position, n):
        """The n-th best player left at a position by this team's view (or the
        last one left), or None."""
        last = None
        for p in self.lists[tid][position]:
            if p.id in self.taken:
                continue
            last = p
            n -= 1
            if n <= 0:
                break
        return last

    def available(self):
        return [p for p in self.pool if p.id not in self.taken]

    def make_pick(self, pid):
        slot = self.on_clock()
        tid = slot["team"]
        p = self.league.player(pid)
        if pid in self.taken:
            raise ValueError("He's already been drafted.")
        if self.have[tid][p.position] >= ROSTER_TEMPLATE.get(p.position, 0):
            raise ValueError(f"The roster is already full at {p.position}.")
        self.taken.add(pid)
        self._filled(tid, p.position)
        self.league.rosters[pid] = tid
        self.picks.append({"round": slot["round"], "pick": slot["pick"], "team": tid, "pid": pid})
        return self.picks[-1]

    def ai_pick(self):
        return self.make_pick(self.best(self.on_clock()["team"]).id)

    def run(self, until_human=True):
        """AI picks until a human team is on the clock (returns its slot) or the
        draft is over (returns None)."""
        while (slot := self.on_clock()) is not None:
            if slot["team"] in self.humans and until_human:
                return slot
            self.ai_pick()
        return None

    def finish(self, rng):
        """Depth charts, captains and practice squads for the new rosters."""
        from . import transactions
        league = self.league
        for t in league.teams:
            league.auto_depth_chart(t.id)
            league.vote_captains(t.id, rng=random.Random(f"captains-{league.season}-{t.id}"))
        transactions.form_practice_squads(league, league.injuries, league.recovering, rng=rng)

    def to_dict(self):
        return {"pool": [p.id for p in self.pool], "order": list(self.order), "picks": list(self.picks),
                "humans": sorted(self.humans)}

    @classmethod
    def from_dict(cls, league, d):
        room = cls(league, humans=d["humans"], order=d["order"], pool_ids=d["pool"])
        for pk in d["picks"]:
            room.taken.add(pk["pid"])
            room._filled(pk["team"], league.player(pk["pid"]).position)
            room.picks.append(dict(pk))
        return room


def startup_draft(league, rng, humans=(), order=None):
    """The whole startup draft at once (tools, and a league whose GM lets his
    staff draft): see StartupRoom. Returns the picks [{round, pick, team, pid}]."""
    room = StartupRoom(league, order=order)
    room.run(until_human=False)
    room.finish(rng)
    return room.picks


def starter_stats_from(players):
    """starter_stats() for a pool with no teams yet: the league's top players
    at each position, as many as 32 teams would start."""
    out = {}
    by_pos = defaultdict(list)
    for p in players:
        by_pos[p.position].append(p.overall())
    for pos_, vals in by_pos.items():
        vals.sort(reverse=True)
        top = vals[:32 * STARTERS_FOR_NEED.get(pos_, 1)]
        m = sum(top) / len(top)
        sd = math.sqrt(sum((x - m) ** 2 for x in top) / max(1, len(top) - 1))
        out[pos_] = (m, max(sd, 3.0))
    return out


# ---------------------------------------------------------------------------
# Drop-ins for offseason.py (same names and arguments as its placeholder)
# ---------------------------------------------------------------------------

def rookie_class(league, rng):
    return make_class(league, rng)
