# player.py
# What a player is (the Player record) and how a new fictional one is made.
#
# How generation works, in plain terms:
#   1. Roll an overall talent level.
#   2. Roll hidden athletic traits (speed, strength...). Talented players
#      lean a little more athletic, but not always.
#   3. Each skill's POTENTIAL (his ceiling) mixes the athletic traits that
#      matter for that skill with his football talent.
#   4. His CURRENT rating is a share of that ceiling. Rookies have grown
#      into 60-85% of it; veterans are near 100%. Veterans past their
#      position's prime then lose what aging would have cost them
#      (development.pre_age).
#   5. Height, weight and combine results come from his traits plus luck,
#      using real NFL combine averages and spreads (see positions.py), so the
#      combine hints at ratings without giving them away.

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import positions as pos
from . import names
from . import colleges


@dataclass
class Player:
    id: int
    first_name: str
    last_name: str
    position: str
    birth_date: date
    experience: int            # pro seasons played (0 = rookie)
    height: int                # inches
    weight: int                # lbs
    college: str
    hometown: str
    draft_year: int = 0
    draft_round: int = 0       # 1-7, or 0 = undrafted

    # skill key -> (current, potential), both 0-100
    skills: dict = field(default_factory=dict)

    # hidden athletic traits, 0-100 (see positions.py)
    athletic: dict = field(default_factory=dict)

    # combine drill -> result in real units, or None if he skipped it.
    # Drills: forty, bench, vertical, broad, cone, shuttle (see positions.py)
    combine: dict = field(default_factory=dict)
    intel_test: int = 0        # out of 50 (everyone takes it)
    position_drill: int = 0    # 0-100 (everyone does it)

    # personality, 0-100
    loyalty: int = 50
    wants_winner: int = 50
    leadership: int = 50
    volatility: int = 50       # odds of sudden jumps or drops in development
    popularity: int = 0

    # Hidden. Never shown to the player; judge them from results.
    consistency: int = 50      # how reliably he plays to his ratings week to week
    generational: bool = False # a once-in-a-generation talent (very rare)
    adaptability: int = 50     # how well he holds his ceiling when moved to a new spot
    # How well his body holds up: how often he gets hurt and how long he's out.
    # Most players are near 50; a few are iron men, a few are fragile. You can
    # only learn it from his injury history. Set by fill_new_ratings().
    durability: int = None

    # Offensive linemen: the side he's used to. "L", "R", or "B" (both).
    # Empty for everyone else. Switching sides is like switching hands.
    side: str = ""

    # Reps learned at spots other than his own: {"G": 40, "side": 70, ...}.
    # 0-100. Grows with practice and games (season loop, later), shrinking the
    # penalty for playing out of position.
    learned: dict = field(default_factory=dict)

    # The year he retired (his last season), or None while he's still playing.
    # Retired players stay in the save so their careers stay viewable.
    retired: int = None

    # Development state (see development.py): {"base": {skill: potential},
    # "long": long-term ceiling shift, "swing": this season's swing}. Hidden.
    dev: dict = None

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    def age(self, on_date):
        years = on_date.year - self.birth_date.year
        if (on_date.month, on_date.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    def overall(self, which="current"):
        """Weighted average of the position's skills. which = 'current' or 'potential'."""
        index = 0 if which == "current" else 1
        total = weight_sum = 0
        for skill, w in pos.POSITIONS[self.position][1]:
            if w > 0:
                total += self.skills[skill][index] * w
                weight_sum += w
        return round(total / weight_sum)

    @property
    def build_note(self):
        """'light for a DE' / 'heavy for a DE' if he's well off the normal
        weight for his position, else ''. Size has real trade-offs (see
        SIZE_TRADEOFF); this is just a quiet label for screens."""
        avg_w, w_spread = pos.BODY[self.position][2], pos.BODY[self.position][3]
        z = (self.weight - avg_w) / w_spread
        if z <= -1.75:
            return f"light for a {self.position}"
        if z >= 1.75:
            return f"heavy for a {self.position}"
        return ""

    @property
    def draft_text(self):
        """'2021, Round 2' or 'Undrafted (2021)'"""
        if self.draft_round == 0:
            return f"Undrafted ({self.draft_year})"
        return f"{self.draft_year}, Round {self.draft_round}"

    def set_draft_history(self, draft_round):
        """Give him a draft round and a school that fits it (see colleges.py)."""
        self.draft_round = draft_round
        self.college = colleges.pick_college(draft_round)

    @property
    def developed_pct(self):
        """How far he has come from raw toward his potential, as a percent (developed_share)."""
        return round(developed_share(self.overall("current"), self.overall("potential")))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

# Spread of raw talent among all football players. Bigger = more distance
# between stars and scrubs. Tuned so a full league has a realistic mix.
TALENT_SPREAD = 17
# Extra stretch on the high end only. Real talent has a long tail: stars are
# much further above average than scrubs are below it.
TALENT_STAR_STRETCH = 9


def _clamp(value, low=1, high=99):
    return max(low, min(high, value))


def _roll(mean, spread):
    return random.gauss(mean, spread)


# How each combine drill links to the hidden traits.
# drill: (trait, link strength, does a HIGHER trait give a LOWER number?)
# Link strength 0.8 means the drill mostly reflects the trait, with some luck.
_DRILL_LINKS = {
    "forty":    ("speed",     0.80, True),
    "bench":    ("strength",  0.85, False),
    "vertical": ("explosion", 0.80, False),
    "broad":    ("explosion", 0.80, False),
    "cone":     ("agility",   0.80, True),
    "shuttle":  ("agility",   0.75, True),
}

# Trait points gained (or lost, if negative) per "spread" of extra weight for
# his position. A player 2 spreads heavier than normal: about +12 strength, -10 speed.
SIZE_TRADEOFF = {"strength": 6, "speed": -5, "agility": -4, "explosion": -1}

# How many pro seasons a made-up player has played (0 = rookie .. 15), by
# position group: odds for the pool a new league picks its players from.
# Fitted (Oct 22) so the players who make a new league's rosters match real
# NFL week-1 active rosters, 2021-26, by experience (nflverse weekly rosters),
# within about a point at every experience level. The pool leans younger
# than real rosters because teams keep the better players and veterans past
# their prime have aged (development.pre_age). Real rosters by experience,
# all positions: rookies 12%, 1-2 seasons 27%, 3-4 23%, 5-6 17%, 7-8 11%,
# 9-10 5%, 11+ 4%; QBs and kickers/punters/snappers last much longer (11+:
# QB 16%, K/P/LS 18%), running backs least (11+: 1.5%).
# (Before Oct 22: one made-up table for every position, 14, 12, 11 ... 1, and
# no aging, so new leagues had 16% 9+ year veterans vs real 9%, RBs 20% vs 5%.)
EXPERIENCE_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
                    "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB",
                    "K": "ST", "P": "ST", "LS": "ST"}
EXPERIENCE_WEIGHTS = {
    # experience: 0     1     2     3     4    5    6    7    8    9   10   11   12   13   14   15
    "QB": [9.1, 11.1, 7.1, 7.5, 6.6, 7.3, 7.3, 6.0, 5.5, 4.4, 4.0, 3.3, 2.4, 3.8, 3.9, 10.7],
    "RB": [20.3, 16.9, 14.1, 10.6, 8.6, 7.6, 5.5, 4.2, 3.3, 3.4, 1.9, 1.9, 1.1, 0.6, 0.2, 0.0],
    "WR": [17.6, 14.9, 12.6, 9.8, 8.4, 7.2, 6.3, 5.1, 4.2, 3.9, 3.2, 2.6, 2.1, 1.2, 0.6, 0.3],
    "TE": [14.6, 15.0, 13.4, 10.4, 10.0, 7.2, 5.9, 5.8, 5.1, 3.5, 1.7, 1.3, 1.1, 0.9, 0.7, 3.3],
    "OL": [15.4, 14.8, 13.7, 11.8, 9.5, 7.8, 6.8, 5.7, 4.6, 3.2, 2.0, 1.2, 1.1, 0.9, 0.4, 0.8],
    "DL": [12.6, 13.4, 11.3, 10.7, 8.6, 8.4, 7.1, 6.4, 6.0, 4.2, 3.3, 2.8, 1.6, 1.2, 0.9, 1.4],
    "LB": [18.9, 16.0, 13.8, 11.2, 9.0, 7.5, 6.4, 4.8, 4.0, 2.6, 1.7, 1.5, 1.2, 0.7, 0.6, 0.1],
    "DB": [17.5, 16.6, 14.4, 11.4, 9.1, 8.4, 6.6, 5.5, 3.8, 2.4, 1.6, 1.1, 0.9, 0.4, 0.2, 0.0],
    "ST": [12.5, 10.2, 11.1, 7.5, 6.7, 6.5, 6.8, 6.3, 4.6, 5.6, 4.7, 3.8, 3.6, 2.9, 2.1, 5.1],
}

# Young players in a NEW league (Oct 25; Blake: "make new leagues' young players as
# developed as drafted rookies"). A league that has run a few seasons has young
# players the draft made: a rookie at ~88% of his ceiling, a 2nd-year player ~93%,
# 3rd-year ~95%, 4th-year ~96.5% (internal overall; 8 simulated leagues x 14
# seasons), and rookies' and 2nd-year players' ceilings a few points lower than a
# new league's, since the draft sets each class below the pool it's drawn from
# (draft.LEVEL_SHIFT). New leagues used to make them at 71% / 78% / 85% / 91% with
# the higher ceilings, so the league's starters climbed ~5 points over its first 5
# seasons as they grew up (65 -> 70 internal; startup-draft leagues 62.5 -> 69),
# then held. Now a new league's young players match a running league's:
# (Oct 25, later: draft prospects were made rawer, draft.PROSPECT_READY_MEAN 0.88 -> 0.82, to match real
# rookies' playing time; running leagues' young players then sat at 83.8% / 90.1% / 93.7% / 95.6% (3 leagues
# x 10 real seasons, seasons 7+), so these moved down by the same amounts, from 0.89 / 0.935 / 0.965 / 0.985.)
NEW_LEAGUE_READY = {0: 0.84, 1: 0.905, 2: 0.95, 3: 0.975}    # base share of the ceiling (then the usual noise)
NEW_LEAGUE_POT_SHIFT = {0: -5.0, 1: -2.5}                     # ceiling, rating points (not Generational players)

# Developed % (Oct 25; Blake, choosing to change the yardstick and not the players: in FOF8
# "it was uncommon for someone to be 50% developed or more"). Counted from a raw starting
# point to his ceiling, not as his current rating over his ceiling: even a raw prospect
# already has most of his ceiling in rating points (drafted rookies sit at 72-93% of it,
# median 82%, set by real rookies' playing time, draft.PROSPECT_READY_*), so that ratio read
# 70-80% for nearly everyone. A player at DEVELOPED_RAW of his ceiling (internal overall)
# counts as 0%, at his ceiling 100%. Drafted rookies: median ~28%, about 1 in 4 at 50%+,
# 1 in 10 at 70%+; a 2nd-year player ~60%, 3rd-year ~75%, a veteran in his prime ~92%.
DEVELOPED_RAW = 0.75


def developed_share(current, potential):
    """Developed %, 0-100 (unrounded), from internal overall ratings."""
    if not potential:
        return 100.0
    return max(0.0, min(100.0, 100.0 * (current / potential - DEVELOPED_RAW) / (1 - DEVELOPED_RAW)))


_next_id = 1


def _combine_value(position, drill, z, plain):
    """A combine result from his standing z among players at his position, shaped like real
    combine results there (combine_data.py, every combine 2000-2026): the same order as the
    bell curve `plain` but real tails, so no one beats the real best by more than a hair
    (Oct 23; Blake had seen a 4.14 forty; the real record is 4.21)."""
    from . import combine_data as CD
    table = CD.QUANTILES.get(position, {}).get(drill)
    if not table:
        low, high = CD.RECORDS[drill]
        return min(high, max(low, plain))
    p = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    for (p0, v0), (p1, v1) in zip(table, table[1:]):
        if p <= p1:
            return v0 + (v1 - v0) * (p - p0) / (p1 - p0) if p1 > p0 else v1
    return table[-1][1]


def generate_player(position=None, experience=None, season_year=2026,
                    generational=False, rng_seed=None, new_league=False):
    """Make one fictional player.
    position:     e.g. "QB". Random if left out.
    experience:   pro seasons played. Random if left out.
    season_year:  the season he is being created for (sets his birth date).
    generational: True makes a once-in-a-generation talent. The league decides
                  how rare these are (see league.py); never set this casually.
    new_league:   he's for a new league's starting rosters: young players are made
                  as developed as drafted ones (NEW_LEAGUE_READY). Off for draft
                  prospects and street free agents (draft.py shapes those itself).
    """
    global _next_id
    if rng_seed is not None:
        random.seed(rng_seed)

    if position is None:
        position = random.choice(list(pos.POSITIONS))
    if experience is None:
        experience = random.choices(range(16), weights=EXPERIENCE_WEIGHTS[EXPERIENCE_GROUP[position]])[0]

    # 1. Talent
    z = _roll(0, 1)                 # how talented, in spreads above/below average
    if generational:
        talent = _clamp(_roll(93, 3), 88, 99)
    else:
        talent = (50 + pos.TALENT_SHIFT.get(position, 0)
                  + pos.TALENT_SPREAD_MULT.get(position, 1.0)
                  * (TALENT_SPREAD * z + (TALENT_STAR_STRETCH * z * z if z > 0 else 0)))
        talent = _clamp(talent, 5, 99)

    # Body. Some players are light or heavy for their position, and it
    # matters: see the size trade-off just below.
    avg_h, h_spread, avg_w, w_spread = pos.BODY[position]
    height = round(_roll(avg_h, h_spread))
    weight = round(_roll(avg_w, w_spread) + (height - avg_h) * 5)
    weight_z = (weight - avg_w) / w_spread   # how heavy for his position (0 = typical)

    # 2. Athletic traits (relative to his position). Average 50, spread 15.
    #    Generational players are freaks for their position, with rare exceptions.
    #    Each trait mixes: how talented he is (relative to his position),
    #    luck, and the size trade-off: heavier than normal for his position =
    #    stronger but a bit slower and less agile; lighter = the reverse.
    #    Because skills come from these traits, a heavy end is better against
    #    the run and a light end is quicker off the edge. The mix is scaled so
    #    each trait keeps a spread of 15, which keeps combine results matching
    #    real NFL data.
    athletic = {}
    # His talent in spreads above or below the average for his position,
    # including the extra stretch that makes stars stand out.
    # (Rescaled to an average of 0 and a spread of 1, so traits, and the
    # combine results built from them, keep matching real NFL data.)
    a = TALENT_STAR_STRETCH / TALENT_SPREAD
    stretch_mean = a / 2
    stretch_sd = math.sqrt(1 + 2 * a * 0.7979 + 1.5 * a * a - stretch_mean ** 2)
    talent_z = 2.5 if generational else (
        (z + (a * z * z if z > 0 else 0) - stretch_mean) / stretch_sd)
    for trait in ["speed", "strength", "agility", "explosion"]:
        size = SIZE_TRADEOFF.get(trait, 0) / 15
        mix = 0.47 * talent_z + 0.88 * _roll(0, 1) + size * weight_z
        scale = 15 / math.sqrt(0.47 ** 2 + 0.88 ** 2 + (size * 1.1) ** 2)
        if generational:
            athletic[trait] = _roll(80, 10) + SIZE_TRADEOFF.get(trait, 0) * weight_z
        else:
            athletic[trait] = 50 + scale * mix
    athletic = {t: _clamp(round(v)) for t, v in athletic.items()}
    intel_avg = 50 + pos.INTELLIGENCE_BONUS.get(position, 0) + (15 if generational else 0)
    athletic["intelligence"] = _clamp(round(_roll(intel_avg, 15)))

    # 3 and 4. Skills: potential, then current
    base = NEW_LEAGUE_READY.get(experience) if new_league else None
    if base is None:
        base = min(1.0, 0.70 + 0.07 * experience)
    developed = _clamp(base + _roll(0, 0.05), 0.55, 1.0)
    pot_shift = 0.0 if generational or not new_league else NEW_LEAGUE_POT_SHIFT.get(experience, 0.0)
    skills = {}
    skill_list = pos.POSITIONS[position][1]
    # Positions with few skills (K, P) get less random wobble per skill, so
    # their overall ratings don't swing more than other positions'.
    wobble = 7 if len(skill_list) >= 6 else 4
    for skill, _w in skill_list:
        if position == "RB" and skill == "endurance":
            continue                     # set by fill_new_ratings() below
        _label, trait_weights = pos.SKILLS[skill]
        talent_share = 1.0 - sum(trait_weights.values())
        potential = talent_share * talent
        for trait, tw in trait_weights.items():
            potential += tw * athletic[trait]
        potential = _clamp(round(potential + _roll(0, wobble) + pot_shift), 5, 99)
        if generational and _w >= 2:
            # His most important skills top out near the ceiling of the scale.
            potential = max(potential, random.randint(90, 99))
        share = min(1.0, developed + _roll(0, 0.04))
        current = _clamp(round(potential * share), 1, potential)
        skills[skill] = (current, potential)

    # Combine. Each result = position average, shifted by his trait, plus luck.
    combine = {}
    for drill in pos.COMBINE_DRILLS:
        avg, spread, takes_part = pos.COMBINE[position][drill]
        if random.random() > takes_part:
            combine[drill] = None            # skipped the drill
            continue
        trait, link, lower_is_better = _DRILL_LINKS[drill]
        trait_z = (athletic[trait] - 50) / 15
        if lower_is_better:
            trait_z = -trait_z
        z = link * trait_z + math.sqrt(1 - link ** 2) * _roll(0, 1)
        value = _combine_value(position, drill, z, avg + z * spread)
        if drill in ("forty", "cone", "shuttle"):
            combine[drill] = round(value, 2)
        elif drill == "vertical":
            combine[drill] = round(value * 2) / 2   # to the half inch, like the real combine
        else:
            combine[drill] = max(1, round(value))
    intel_test = round(_clamp(8 + athletic["intelligence"] * 0.30 + _roll(0, 3), 4, 48))

    # Age (as of Sept 1 of the season) and birth date: rookies are usually 21-23
    age = max(21, 22 + experience + random.choice([-1, 0, 0, 1]))
    birth_date = date(season_year - age - 1, 9, 2) + timedelta(days=random.randint(0, 364))

    first_name, last_name = names.person(random)
    player = Player(
        id=_next_id,
        first_name=first_name,
        last_name=last_name,
        position=position,
        birth_date=birth_date,
        experience=experience,
        height=height,
        weight=weight,
        college="",                     # set just below, to fit his draft round
        hometown=random.choice(names.HOMETOWNS),
        skills=skills,
        athletic=athletic,
        combine=combine,
        intel_test=intel_test,
        loyalty=_clamp(round(_roll(50, 18))),
        wants_winner=_clamp(round(_roll(50, 18))),
        leadership=_clamp(round(_roll(40 + experience * 2, 18))),
        # Generational players almost never bust, so their development is steady.
        volatility=_clamp(round(_roll(25, 10) if generational else _roll(50, 18))),
        popularity=_clamp(round(5 + experience * 3 + (talent - 50) * 0.4 + _roll(0, 8)), 1, 99),
        consistency=_clamp(round(_roll(92, 4) if generational else _roll(50, 15))),
        generational=generational,
        adaptability=_clamp(round(_roll(50, 18) + (athletic["intelligence"] - 50) * 0.3)),
        # Guards and tackles: 45% left side, 45% right side, 10% comfortable on both.
        side=random.choices(["L", "R", "B"], weights=[45, 45, 10])[0] if position in ("T", "G") else "",
    )
    player.position_drill = _clamp(round(player.overall() + _roll(0, 7)))

    # Draft history. A league overrides this with a ranking of all its players
    # (see league.py); this is a stand-in for players made on their own.
    player.draft_year = season_year - experience
    pct = 1 - 0.5 * (1 + math.erf((talent - 50) / TALENT_SPREAD / math.sqrt(2)))
    player.set_draft_history(colleges.round_from_percentile(_clamp(pct + _roll(0, 0.08), 0, 0.999)))
    _next_id += 1
    fill_new_ratings(player)
    # A veteran past his prime has already aged (development.py's real-data
    # aging; before Oct 22 a 12-year veteran was made at his full peak).
    from . import development
    development.pre_age(player, random)
    return player


# ---------------------------------------------------------------------------
# Durability and running back endurance (added Oct 19)
# ---------------------------------------------------------------------------
# Durability (hidden) averages 50. Size matters both ways (Blake): heavier
# than normal for his position is a small edge on average, but size also
# widens the spread, so big men are more often iron men OR fragile.
DURABILITY_SPREAD = 14         # spread for a typical-sized player
DURABILITY_SIZE_SHIFT = 3      # points per spread of extra weight
DURABILITY_SIZE_SPREAD = 3     # extra spread per spread of weight away from typical
DURABILITY_GENERATIONAL = (72, 12)   # Generational players usually hold up (not always)


def fill_new_ratings(p):
    """Give a player the ratings added after the first saves existed: hidden
    durability for everyone and endurance for running backs. Each is seeded by
    the player (his id, name and birth date: an id alone gave player #57 the same
    draw in every league, Oct 23), so it never changes and older saved leagues
    get the same values without being regenerated."""
    avg_h, h_spread, avg_w, w_spread = pos.BODY[p.position]
    weight_z = (p.weight - avg_w) / w_spread
    if getattr(p, "durability", None) is None:
        rng = random.Random(f"durability-{p.id}-{p.first_name} {p.last_name}-{p.birth_date}")
        if p.generational:
            mean, spread = DURABILITY_GENERATIONAL
        else:
            mean = 50 + DURABILITY_SIZE_SHIFT * weight_z
            spread = DURABILITY_SPREAD + DURABILITY_SIZE_SPREAD * abs(weight_z)
        p.durability = _clamp(round(rng.gauss(mean, spread)), 5, 99)
    if p.position == "RB" and "endurance" not in p.skills:
        # How big a workload he can carry in a game before he wears down.
        # Stronger, thicker backs tend to handle more; plenty of luck.
        rng = random.Random(f"endurance-{p.id}-{p.first_name} {p.last_name}-{p.birth_date}")
        value = (50 + 0.35 * (p.athletic.get("strength", 50) - 50) + 5 * weight_z
                 + (10 if p.generational else 0) + rng.gauss(0, 13))
        value = _clamp(round(value), 10, 99)
        p.skills["endurance"] = (value, value)
