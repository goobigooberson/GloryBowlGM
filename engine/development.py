# development.py
# Player development (Step 7 piece 4c), as designed with Blake on Oct 19:
#
# - Not Madden-style steady climbs. The drama is in POTENTIAL shifting;
#   current ratings grow fairly steadily toward potential.
# - Once a year, at training camp, every player's potential is re-checked.
#   No fixed percentages: each player's odds come from his own make-up
#   (volatility the most, then age, playing time, serious injuries,
#   Generational status), and league-wide rates come out of that. Target: in
#   a typical year ~88-90% of players barely move (0-3 points); big swings
#   are rare.
# - Two layers of potential, both moving a little every year (no yes/no
#   switch deciding "for good" or "comes back"):
#     long_term: a ceiling that drifts by small amounts and now and then
#       takes a bigger, lasting step (heavy-tailed randomness, not a switch)
#     swing: a season-to-season swing on top that fades gradually: part of
#       it carries into next year, part wears off, how much is random
#   So outcomes cover a spectrum: full bounce-back, partial recovery, stays
#   down, keeps sliding, occasionally comes back better.
# - Aging is separate: past his position's peak years a player's potential
#   (and with it his current ratings) declines, physical skills faster than
#   mental ones, faster the further past the peak.
# - Current ratings move a steady share of the way toward potential each
#   year with a little noise. If potential falls below current, current
#   falls too, though not point for point.
# - Coaches (later) will tilt shifts upward at their specialty; staged
#   reveals (what the staff can see) and rust come with training camp.
#
# Each player keeps his development state in Player.dev:
#   {"base": {skill: potential before the layers}, "long": float, "swing": float}
# and a year-by-year ratings history is kept in League.rating_history.

import math
import random

from . import injuries
from . import positions as pos

# ---- Knobs (judgment calls; Blake reviews player histories before these are locked) ----
LONG_SD = 1.05            # long-term drift per year, in rating points, for an average player
SWING_SD = 1.3            # new season swing per year
                          # (Blake's target: 88-90% of players move 0-3 points of potential a year.
                          # With the real-data peak years (Oct 21) more veterans decline each year,
                          # which is movement too, so the random part is smaller than before
                          # (was 1.15/1.6): ~90% in real-game leagues. More randomness (1.15/1.45)
                          # didn't make more stars; faster growth for young players did, see
                          # GROWTH_SHARE.)
# Long-term lean by career stage at his position (points per year), see PEAK_SEASONS.
LEAN_BY_STAGE = {"before peak": 0.30, "early peak": 0.10, "peak": -0.10, "past peak": -0.30}
PLAYING_TIME_LEAN = 0.15  # starters (half the snaps or more) lean up this much; seldom-used players down
SWING_CARRY = (0.25, 0.75)  # share of last year's swing that carries over (random in this range)
LONG_PULL = 0.10          # share of the long-term shift that fades each year (half-life ~7 seasons)
SPECIALIST_SCALE = 0.6    # K/P/LS development movement (their ratings rest on few skills and careers are
                          # long; at 1.0 kickers' and punters' spread grew ~4 points over 16 seasons)
TAIL_DF = 4               # heavy tails: mostly small moves, now and then a big one
                          # (3 gave 30-point one-year flukes; 5 with limit 3.5 felt tame: biggest jump +14)
TAIL_LIMIT = 4.0          # the most extreme single-year draw, in spreads (Blake: raise for more drama)
SKILL_SD = 0.55           # each skill also wanders a little on its own
# Share of the gap to potential closed each year, by age. Raised Oct 21 (was 0.38 at 21 down to
# 0.24 at 27): real players reach their prime by about season 2-4 (tools/aging_curves.py), and with
# the slower growth, aged leagues ran short of stars (players topped out just under 90, then aged).
GROWTH_SHARE = {21: 0.46, 22: 0.44, 23: 0.42, 24: 0.40, 25: 0.37, 26: 0.33, 27: 0.29}
GROWTH_SHARE_OLD = 0.20   # share of the gap to potential closed per year, older players
GROWTH_NOISE = 0.8
DROP_SHARE = 0.75         # potential falls below current: current falls this share of the gap
# Peak years by position: (first, last) pro season of his prime (a rookie's first season
# is 1); decline starts the season after. Measured from real NFL players (Blake, Oct 21:
# "make it extremely accurate"; tools/aging_curves.py, nflverse data): each player compared
# with himself from one season to the next ("delta method"), 1999-2025 stats for QB/RB/WR/
# TE/K/P efficiency, 2013-2025 snap shares in games played for everyone else.
#   QB  efficiency jumps from year 1 to 2, flat through 8, slides from 9-10    -> 2-9
#   RB  most efficient as a rookie; playing time peaks 2-5, falls from 7       -> 2-6
#   WR  playing time flat 2-6, falls from 7; efficiency peaks 3, slides from 5 -> 2-6
#   TE  rises to 4, flat to 7-8, falls from 9 (both measures)                  -> 3-8
#   T   keeps rising to 7, still near the top at 10                            -> 3-10
#   G   flat 4-7, falls from 8-9                                               -> 3-8
#   C   rising through 8 (no data past 8; set like T)                          -> 3-10
#   DE  flat 4-9, falls from 10                                                -> 3-9
#   DT  flat 3-6, slow slide from 7                                            -> 3-8
#   LB  rises to 5, flat to 7, falls from 8 (OLB/ILB alone are too few)        -> 2-8
#   CB  peaks 4, flat 2-7, falls from 8                                        -> 2-7
#   S   flat 3-8, falls from 9                                                 -> 3-8
#   K   accuracy flat 1-6, slow slide from 7, faster after 10                  -> 1-9
#   P   distance flat into season 14                                           -> 1-14
#   LS, FB: no usable data (LS set like P; FB like RB, a little longer).
# The FOF8 design doc's examples were QB 5-13, RB 3-9, K 1-16: real players peak earlier.
PEAK_SEASONS = {"QB": (2, 9), "RB": (2, 6), "FB": (2, 7), "WR": (2, 6), "TE": (3, 8),
                "T": (3, 10), "G": (3, 8), "C": (3, 10), "DE": (3, 9), "DT": (3, 8),
                "OLB": (2, 8), "ILB": (2, 8), "CB": (2, 7), "S": (3, 8),
                "K": (1, 9), "P": (1, 14), "LS": (1, 14)}
DECLINE_BASE = 1.2        # rating points lost the first year past the peak...
DECLINE_GROWTH = 0.45     # ...and this much more each further year
# How fast each position declines once past its peak (1.0 = the rates above). Real kickers
# lose accuracy slowly (about half a point of FG% a year at first) and punters barely lose
# distance at all; the other positions' slides look alike within the data's noise.
DECLINE_SCALE = {"K": 0.5, "P": 0.35, "LS": 0.35}
# Everyone ages differently (Blake, Oct 21: not "27 hits and the same predictable drop-off").
# Each player has his own aging profile, fixed for his career (seeded by his id):
AGING_PEAK_SD = 2.5       # his prime ends this many seasons earlier/later than his position's (spread)
AGING_PEAK_LIMIT = 4      # ...at most this many either way
AGING_RATE_SD = 0.35      # how fast he declines once past it (spread of a multiplier around 1)
AGING_YEAR_NOISE = 0.5    # and each year's decline varies by up to this share either way (bumpy, not smooth)
# Tuned so a sim league's "still in the league next season" by pro season matches the
# real NFL's (tools/retention_check.py).
PHYSICAL_TRAITS = ("speed", "agility", "explosion", "strength")
# Injuries (Oct 21, Blake: specific injuries, permanent and temporary step backs): each
# injury's odds and sizes are in injuries.py. (Before: any 12+ week injury cut the ceiling
# 60% of the time; before that, any 8+ week one, every time: ~210 hits a season.)
INJURY_MENTAL_SHARE = 0.3   # how much of an injury hit lands on non-physical skills (vs 1.0 = all equal)
COMEBACK_SHARE = (0.7, 1.0)  # share of a temporary step back he gets back at the next camp
# ------------------------------------------------------------------------------------------


def _t(rng, df=TAIL_DF):
    """Heavy-tailed noise, scaled so its spread is about 1: mostly small
    moves, now and then a big one. The most extreme draws are limited to
    TAIL_LIMIT spreads: with no limit, a few very volatile backups jumped
    30+ points of potential for one year and fell back the next (55 -> 91
    -> 71), which doesn't read like a real breakout. This shapes the dice
    for development only; no game stat is capped."""
    z = rng.gauss(0, 1)
    chi = sum(rng.gauss(0, 1) ** 2 for _ in range(df))
    v = z / math.sqrt(chi / df) / math.sqrt(df / (df - 2))
    return max(-TAIL_LIMIT, min(TAIL_LIMIT, v))


def ensure_state(p):
    """Players made before development existed: start from today's potentials."""
    if not getattr(p, "dev", None):
        p.dev = {"base": {s: float(v[1]) for s, v in p.skills.items()}, "long": 0.0, "swing": 0.0}
    return p.dev


def aging_profile(p):
    """His own aging: (seasons his prime ends later (+) or earlier (-) than
    his position's, decline speed multiplier). Fixed for his career."""
    rng = random.Random(f"aging-{p.id}")
    shift = max(-AGING_PEAK_LIMIT, min(AGING_PEAK_LIMIT, round(rng.gauss(0, AGING_PEAK_SD))))
    rate = math.exp(rng.gauss(0, AGING_RATE_SD))
    return shift, rate


def peak_seasons(p):
    """His prime, in pro seasons: his position's, moved by his own aging profile."""
    start, end = PEAK_SEASONS.get(p.position, (3, 10))
    shift, _rate = aging_profile(p)
    return start, max(start + 1, end + shift)


def _physical_share(skill):
    _label, traits = pos.SKILLS[skill]
    return sum(w for t, w in traits.items() if t in PHYSICAL_TRAITS) / max(1e-9, sum(traits.values()) or 1)


def _scale(p, age):
    """How much this player's potential tends to move: volatility the most,
    then age (young players swing more)."""
    vol = 0.45 + 1.1 * (p.volatility / 100)          # 0.45 (very steady) .. 1.55 (very volatile)
    if age <= 23:
        a = 1.30
    elif age <= 26:
        a = 1.05
    elif age <= 29:
        a = 0.85
    else:
        a = 0.70
    s = vol * a
    if p.generational:
        s *= 0.5
    if p.position in ("K", "P", "LS"):
        s *= SPECIALIST_SCALE
    return s


def _lean(p, age, share_played):
    """Which way the long-term ceiling tends to drift (points per year):
    young players lean up, veterans lean down; playing time nudges it.
    Balanced so the league as a whole doesn't drift up or down over the
    years (the first version leaned up on average and the league's talent
    crept up ~1 point a year: QB starters 70 -> 75 in four seasons)."""
    # By career stage at his position, not raw age: a 30-year-old QB is in his
    # prime, a 30-year-old running back is past it. (Raw-age leans made QBs,
    # with their long careers, slide for years: starters 71 -> 66 over 13 seasons.)
    start, end = peak_seasons(p)
    seasons = season_number(p)
    if seasons < start:
        lean = LEAN_BY_STAGE["before peak"]
    elif seasons <= start + 2:
        lean = LEAN_BY_STAGE["early peak"]
    elif seasons <= end:
        lean = LEAN_BY_STAGE["peak"]
    else:
        lean = LEAN_BY_STAGE["past peak"]
    # Kickers, punters and snappers aren't judged by scrimmage snaps (they have
    # none, so they used to lean down every year as if they never played).
    if share_played is not None and p.position not in ("K", "P", "LS"):
        if share_played >= 0.5:
            lean += PLAYING_TIME_LEAN
        elif share_played < 0.1:
            lean -= PLAYING_TIME_LEAN
    return lean


def season_number(p):
    """Which pro season he's about to play (training camp runs after the
    offseason has added last season to his experience): a second-year
    player has experience 1 and is about to play season 2."""
    return p.experience + 1


def aging(p, rng=None):
    """Points of potential lost to age this year (0 inside his prime). His
    own profile sets when it starts and how fast; each year varies a bit."""
    _start, end = peak_seasons(p)
    past = season_number(p) - end
    if past <= 0:
        return 0.0
    _shift, rate = aging_profile(p)
    year = 1 + (rng.uniform(-AGING_YEAR_NOISE, AGING_YEAR_NOISE) if rng else 0)
    return (DECLINE_BASE + DECLINE_GROWTH * (past - 1)) * DECLINE_SCALE.get(p.position, 1.0) * rate * year


def pre_age(p, rng):
    """A veteran made for a new league (or signed later as a made-up
    veteran) is created at his peak ability; take off the aging he'd have
    had at the camps already past his prime, by the same rules as aging()
    (his own profile, bumpy years, physical skills faster). A new league
    has no camp before its first season, so a player about to play pro
    season N has had the camps for every season up to N."""
    _start, end = peak_seasons(p)
    past = season_number(p) - end
    if past <= 0:
        return 0.0
    _shift, rate = aging_profile(p)
    total = sum((DECLINE_BASE + DECLINE_GROWTH * (k - 1)) * (1 + rng.uniform(-AGING_YEAR_NOISE, AGING_YEAR_NOISE))
                for k in range(1, past + 1)) * DECLINE_SCALE.get(p.position, 1.0) * rate
    skills = {}
    for skill, (cur, pot) in p.skills.items():
        loss = total * (0.5 + 1.0 * _physical_share(skill))
        new_pot = max(1, round(pot - loss))
        skills[skill] = (max(1, min(new_pot, round(cur - loss))), new_pot)
    p.skills = skills
    return total


def _injury_effects(rng, season_injuries, position=None):
    """Last season's injuries -> (temporary step back, permanent loss), in
    rating points for an average skill (injuries.py has each injury's odds,
    adjusted for his position)."""
    temp = perm = 0.0
    for kind, _weeks in season_injuries or ():
        inj = injuries.get(kind, position)
        if inj.temp_chance and rng.random() < inj.temp_chance:
            temp += abs(rng.gauss(inj.temp_size, 0.4 * inj.temp_size))
        if inj.perm_chance and rng.random() < inj.perm_chance:
            perm += abs(rng.gauss(inj.perm_size, 0.4 * inj.perm_size))
    return temp, perm


def develop(p, age, rng, share_played=None, season_injuries=()):
    """One year of development for one player (at training camp). Changes
    p.skills in place. season_injuries: [[injury kind, weeks], ...] from
    last season (injuries.py). Returns (overall before, overall after,
    potential before, potential after)."""
    d = ensure_state(p)
    ovr0, pot0 = p.overall(), p.overall("potential")
    s = _scale(p, age)
    # Layer 1: the long-term ceiling.
    step = _lean(p, age, share_played) + LONG_SD * s * _t(rng)
    if p.generational:
        step = max(step, -1.5)                    # Generational players almost never collapse
    # A lasting shift fades very slowly (LONG_PULL a year), so a breakout
    # or collapse still shapes most of a career, but talent within a
    # position can't keep spreading out forever (without the pull, 15
    # seasons widened the spread among starters by ~30%, most for long
    # careers like kickers, and stats drifted away from the real NFL).
    d["long"] = (1 - LONG_PULL) * d["long"] + step
    # Layer 2: this season's swing, fading from last year's.
    carry = rng.uniform(*SWING_CARRY)
    shock = SWING_SD * s * _t(rng)
    if p.generational:
        shock = max(shock, -1.5)
    d["swing"] = carry * d["swing"] + shock
    # Aging past his peak years (physical skills fade faster).
    decline = aging(p, rng)
    growth = GROWTH_SHARE.get(age, GROWTH_SHARE_OLD if age > 27 else 0.38)
    # Injuries. Permanent: a lower ceiling. Temporary: he comes to camp below
    # where he'd be (not all the way back yet) and gets most of it back at the
    # next camp. Both hit physical skills hardest (an Achilles costs burst,
    # not football sense).
    temp, perm = _injury_effects(rng, season_injuries, p.position)
    comeback = d.get("comeback", 0.0)            # owed back from last year's step back
    hit_weight = {k: INJURY_MENTAL_SHARE + (1 - INJURY_MENTAL_SHARE) * 2 * _physical_share(k) for k in p.skills}
    norm = sum(hit_weight.values()) / len(hit_weight) if hit_weight else 1.0
    new_skills = {}
    for skill, (cur, _pot) in p.skills.items():
        if skill not in d["base"]:
            d["base"][skill] = float(_pot)
        d["base"][skill] += SKILL_SD * s * rng.gauss(0, 1)
        if decline:
            d["base"][skill] -= decline * (0.5 + 1.0 * _physical_share(skill))
        w = hit_weight[skill] / norm
        if perm:
            d["base"][skill] -= perm * w
        pot = max(1, min(99, round(d["base"][skill] + d["long"] + d["swing"])))
        if pot >= cur:
            new_cur = cur + growth * (pot - cur) + rng.gauss(0, GROWTH_NOISE)
        else:
            new_cur = cur - DROP_SHARE * (cur - pot) + rng.gauss(0, GROWTH_NOISE * 0.5)
        new_cur += (comeback - temp) * w
        new_cur = max(1, min(pot, round(new_cur)))
        new_skills[skill] = (new_cur, pot)
    p.skills = new_skills
    d["comeback"] = round(temp * rng.uniform(*COMEBACK_SHARE), 2) if temp else 0.0
    return ovr0, p.overall(), pot0, p.overall("potential")


def training_camp(league, played_share=None, serious=None, rng=None):
    """Every active player's yearly development, at training camp.
    played_share: {player id: share of his team's snaps last season};
    serious: {player id: [[injury kind, weeks], ...] last season} (injuries
    that can mark a career; see injuries.py).
    Records everyone's new ratings in league.rating_history."""
    from datetime import date
    rng = rng or random.Random(f"camp-{league.settings.get('salt', '')}-{league.season}")
    changes = {}
    for p in league.players:
        if p.retired is not None:
            continue
        age = p.age(date(league.season, 9, 1))
        if p.experience == 0 and p.draft_year == league.season:
            ensure_state(p)               # rookies: their first camp sets them up; growth starts next year
        else:
            changes[p.id] = develop(p, age, rng, (played_share or {}).get(p.id),
                                    (serious or {}).get(p.id, ()))
        league.rating_history.append({"pid": p.id, "season": league.season, "ovr": p.overall(),
                                      "pot": p.overall("potential")})
    return changes
