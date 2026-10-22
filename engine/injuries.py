# injuries.py
# Real NFL injuries: what they are, how long they keep a player out, how
# teams list them on game day, and what they do to a career.
# (Blake, Oct 21: injury types and lengths must be realistic and data-backed;
# a Questionable / Doubtful / Out system; specific injuries hit specific
# positions harder.)
#
# WHERE THE NUMBERS COME FROM
#   tools/injury_data.py and the scripts beside it, from nflverse data:
#   weekly NFL injury reports 2013-2025 joined to snap counts (who played each
#   game) and weekly rosters (injured reserve), regular season, players who
#   had been playing (2020-21 left out of reserve counts: COVID used the same
#   list). Published studies for the career effects of the big injuries.
#
#   How long injuries last (injuries in weeks 1-6, so the season's end
#   doesn't cut them short), among injuries that cost at least a game:
#     1 game 32%, 2-3 games 28-30%, 4-7 games 17-19%, 8-11 games 4%, 12+ / rest of
#     season 17%. About 820 such injuries a season league-wide (2022-25, the most
#     complete years; ~90 player-games lost per team).
#   Which injuries make up each length: LENGTH_MIX below (body parts from the
#   reports; the 12+ group from reports plus the real counts of torn ACLs, ~21-33
#   in regular-season games a year, and torn Achilles, ~4-10 historically, more
#   lately; most season-ending injuries go straight to injured reserve and never
#   appear on a report, so their body part isn't in the reports).
#   Game-day status (STATUS_*): see below.
#
# The game sim still decides that an injury happens (sim/tuning.py INJURY_RATE)
# and how severe (durable players shake more off); this file turns that into a
# specific injury and length.

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Injury:
    name: str             # what screens and play-by-play say
    temp_chance: float = 0.0
    temp_size: float = 0.0
    perm_chance: float = 0.0
    perm_size: float = 0.0
    retire: float = 0.0   # extra retirement chance that offseason
    area: str = ""        # "lower" (legs, feet), "upper" (shoulder, chest, arm), "spine", "head"


# Career effects. retire = extra chance his career ends that offseason, set from real
# players (tools/injury_careers_real.py: season-ending injuries vs matched uninjured
# players at the same position, career stage and role, 2013-24): about 11 points fewer
# play again the next season on average, knees ~25 (62% vs 87%), shoulders ~11, feet
# ~10; torn Achilles from the studies (57-81% return; 68% higher chance the career ends
# vs matched players). temp / perm sizes are scaled together by CAREER_SIZE_SCALE, tuned
# so a sim league's injured players lose the real amount of playing time the next two
# seasons (tools/injury_careers_sim.py vs the real -8 / -5 points for knees).
CATALOG = {
    # Shaken up: back in a few snaps (often listed Questionable that week)
    "ankle": Injury("ankle"), "knee": Injury("knee"), "shoulder": Injury("shoulder"),
    "hand": Injury("hand"), "hip": Injury("hip"), "back": Injury("back"), "ribs": Injury("ribs"),
    "stinger": Injury("stinger"), "calf": Injury("calf"), "hamstring_tight": Injury("hamstring"),
    "head": Injury("head (cleared)"), "groin_tight": Injury("groin"),
    # Short: 1-3 games
    "ankle_sprain": Injury("ankle sprain"), "hamstring": Injury("hamstring strain"),
    "concussion": Injury("concussion"), "knee_sprain": Injury("knee sprain"),
    "shoulder_sprain": Injury("shoulder sprain"), "groin": Injury("groin strain"),
    "quad": Injury("quad strain"), "calf_strain": Injury("calf strain"), "back_strain": Injury("back strain"),
    "rib_bruise": Injury("rib injury"), "hand_injury": Injury("hand injury"), "turf_toe": Injury("turf toe"),
    "hip_injury": Injury("hip injury"), "foot_sprain": Injury("foot sprain"), "neck_strain": Injury("neck strain"),
    "elbow": Injury("elbow injury"), "chest": Injury("chest injury"), "abdominal": Injury("abdominal strain"),
    # Medium: 4-7 games
    "high_ankle": Injury("high ankle sprain"),
    "mcl_sprain": Injury("MCL sprain"),
    "hamstring_bad": Injury("hamstring strain (severe)"),
    "broken_hand": Injury("broken hand"),
    "concussion_long": Injury("concussion (lingering)", 0.08, 1.0, retire=0.02, area="head"),
    "ac_joint": Injury("separated shoulder"),
    "rib_fracture": Injury("broken ribs"),
    # Long: 8-11 games
    "mcl_tear": Injury("torn MCL", 0.20, 1.5, 0.05, 1.5, area="lower"),
    "high_ankle_bad": Injury("high ankle sprain (severe)", 0.15, 1.0, area="lower"),
    "broken_arm": Injury("broken arm", 0.10, 1.0, area="upper"),
    "fractured_ankle": Injury("fractured ankle", 0.30, 1.5, 0.06, 1.5, 0.05, area="lower"),
    "jones_fracture": Injury("broken foot", 0.20, 1.5, 0.06, 1.0, 0.05, area="lower"),
    "neck_stinger": Injury("neck injury", 0.20, 1.5, 0.06, 1.5, 0.05, area="spine"),
    "core_surgery": Injury("core muscle surgery", 0.15, 1.0, area="lower"),
    "hip_bad": Injury("hip injury (serious)", 0.30, 1.5, 0.08, 1.5, 0.06, area="lower"),
    "torn_quad": Injury("torn quad", 0.40, 2.0, 0.10, 1.5, 0.08, area="lower"),
    "torn_calf": Injury("torn calf", 0.30, 1.5, 0.06, 1.0, area="lower"),
    "elbow_bad": Injury("elbow injury (serious)", 0.15, 1.0, area="upper"),
    "turf_toe_bad": Injury("turf toe (surgery)", 0.30, 1.5, 0.06, 1.0, area="lower"),
    # Season-ending (12+ games)
    "acl": Injury("torn ACL", 0.60, 3.5, 0.20, 2.5, 0.22, area="lower"),
    "achilles": Injury("torn Achilles", 0.90, 5.5, 0.60, 6.0, 0.25, area="lower"),
    "knee_major": Injury("major knee injury", 0.55, 3.0, 0.25, 3.0, 0.22, area="lower"),
    "broken_leg": Injury("broken leg", 0.35, 2.0, 0.08, 1.5, 0.06, area="lower"),
    "lisfranc": Injury("Lisfranc injury", 0.50, 3.0, 0.20, 2.5, 0.08, area="lower"),
    "labrum": Injury("torn labrum", 0.30, 1.5, 0.10, 1.5, 0.10, area="upper"),
    "pectoral": Injury("torn pectoral", 0.30, 1.5, 0.06, 1.0, 0.06, area="upper"),
    "disc": Injury("neck/back surgery", 0.50, 2.5, 0.25, 2.5, 0.18, area="spine"),
    "muscle_tear": Injury("torn hamstring", 0.30, 1.5, 0.08, 1.5, 0.05, area="lower"),
    "concussion_season": Injury("concussion (season-ending)", 0.20, 1.5, 0.05, 1.0, 0.10, area="head"),
    # Saves from before injury types existed: a long injury, the old rule
    "serious": Injury("serious injury", 0.0, 0.0, 0.60, 2.5),
}

# Position multipliers on career effects. Lower body: from the real gap in "plays again
# next season" after a season-ending injury, by position group, relative to the average
# (RB 17 points, WR/TE 13, LB 11, DL 7, DB 6; QB from the studies, which find QBs come
# back best; OL from the studies, ~69% return after an ACL vs ~50% for all players).
# Upper body and spine: no usable real split yet (kept small).
POSITION_RISK = {
    "lower": {"RB": 1.55, "FB": 1.2, "WR": 1.2, "TE": 1.2, "OLB": 1.0, "ILB": 1.0, "QB": 0.8, "T": 0.8, "G": 0.8,
              "C": 0.8, "DE": 0.65, "DT": 0.65, "CB": 0.55, "S": 0.55, "K": 0.5, "P": 0.5, "LS": 0.5},
    "upper": {"QB": 1.5, "T": 1.3, "G": 1.3, "C": 1.3, "DT": 1.3, "DE": 1.2, "TE": 1.1, "ILB": 1.1,
              "RB": 0.9, "WR": 0.9, "CB": 0.9, "S": 0.9, "K": 0.6, "P": 0.6, "LS": 0.6},
    "spine": {"T": 1.15, "G": 1.15, "C": 1.15, "DT": 1.15, "RB": 1.1, "ILB": 1.1},
}

# ---- How long: share of game-costing injuries by length (real, see top) ----
# (length group, first week, last week, share). Season-ending injuries are
# given 20 weeks: out for the rest of the season and the playoffs.
LENGTHS = [("1", 1, 1, 0.32), ("2-3", 2, 3, 0.30), ("4-7", 4, 7, 0.17), ("8-11", 8, 11, 0.04),
           ("season", 20, 20, 0.17)]
SEASON_ENDING_WEEKS = 20
# Not every 12+ week injury ends the season (Oct 22): of real players moved to
# injured reserve in weeks 1-6 (2018-25, scratchpad real_ir_len.py), 4.3% came
# back after 12-16 weeks and 43% didn't come back that season, so about 1 in 11
# "season" injuries lasts 12-16 weeks (back late in the year if there's time).
SEASON_GROUP_RETURNS = 0.09
SEASON_GROUP_RETURN_WEEKS = (12, 16)

# ---- Next season: still not ready? (Oct 22) ---------------------------------
# Real players who ended a season on injured reserve and played again the next
# season (2019-25, scratchpad real_camp.py): about a quarter weren't ready for
# week 1, by when they were hurt (weeks 1-6: 23%, 7-12: 26%, 13-18: 26%); of
# those, about half missed 1-5 games and half 6 or more (most of those were
# back by about week 7-10; on PUP, they must miss at least 4). Knees were
# slower (32% not ready after a late-season knee), ankles a bit quicker (23%),
# concussions rarely carried over (8%).
NOT_READY = ((6, 0.23), (12, 0.26), (99, 0.26))      # (hurt in regular-season week <= this, share)
NOT_READY_BY_PART = {"knee": 1.25, "ankle": 0.9, "concussion": 0.3}
NOT_READY_ACHILLES = 1.25                            # no real split (too few); set like knees
NOT_READY_LONG = 0.55                                # share of the not-ready who miss 6+ games
NOT_READY_SHORT_GAMES = (1, 5)
NOT_READY_LONG_GAMES = (6, 10)

# ---- Training camp and preseason practices (Oct 22) -------------------------
# Real teams open week 1 with about 4.0 players newly on reserve lists (hurt
# in the offseason, camp or preseason: IR 3.2, IR designated to return 0.3,
# PUP 0.3, non-football 0.2) and about 1.0 more newly Out or Doubtful
# (2019-25, scratchpad real_camp.py), ~5.0 new game-costing injuries a team.
# Preseason games make some of those; practices make the rest: this many
# game-costing practice injuries per team over camp and the preseason (about
# 6 weeks), tuned so week 1 matches. Same length and injury mix as games.
CAMP_INJURIES_PER_TEAM = 4.0
CAMP_WEEKS = 6

# ---- Which injury, within each length group (real mix; see top) -------------
# Body-part shares from the reports (percent), each turned into the injury a
# player with that body part and that long an absence most likely has.
LENGTH_MIX = {
    "shaken": {"hamstring_tight": 17, "head": 6, "knee": 12, "ankle": 13, "shoulder": 9, "groin_tight": 6,
               "back": 5, "hip": 5, "hand": 6, "calf": 4, "ribs": 3, "stinger": 3},
    "1": {"hamstring": 17, "concussion": 16, "knee_sprain": 12, "ankle_sprain": 9, "shoulder_sprain": 7,
          "groin": 6, "back_strain": 4, "hip_injury": 4, "foot_sprain": 4, "quad": 3, "calf_strain": 3,
          "hand_injury": 3, "rib_bruise": 2, "neck_strain": 2, "elbow": 2, "chest": 1},
    "2-3": {"hamstring": 24, "ankle_sprain": 16, "knee_sprain": 14, "concussion": 7, "shoulder_sprain": 6,
            "groin": 5, "quad": 5, "hand_injury": 3, "calf_strain": 3, "hip_injury": 3, "foot_sprain": 3,
            "rib_bruise": 2, "chest": 2, "back_strain": 1, "abdominal": 1, "elbow": 1},
    "4-7": {"high_ankle": 21, "hamstring_bad": 18, "mcl_sprain": 17, "broken_hand": 7, "jones_fracture": 6,
            "ac_joint": 4, "groin": 4, "quad": 4, "concussion_long": 3, "turf_toe": 3, "calf_strain": 3,
            "hip_injury": 2, "chest": 2, "broken_arm": 1, "rib_fracture": 1, "neck_strain": 1},
    "8-11": {"mcl_tear": 30, "high_ankle_bad": 9, "fractured_ankle": 6, "muscle_tear": 13, "core_surgery": 9,
             "hip_bad": 4, "labrum": 4, "concussion_long": 4, "torn_calf": 4, "broken_hand": 4,
             "jones_fracture": 2, "disc": 2, "turf_toe_bad": 2, "pectoral": 2},
    # About 140 season-enders a regular season (17% of ~820): torn ACL ~28 a year
    # (regular-season counts run 21-33), torn Achilles ~9, the rest by body part
    # from the reports.
    "season": {"acl": 22, "achilles": 7, "knee_major": 8, "lisfranc": 5, "jones_fracture": 4,
               "fractured_ankle": 5, "broken_leg": 3, "labrum": 7, "muscle_tear": 6, "concussion_season": 5,
               "neck_stinger": 3, "disc": 4, "hip_bad": 2, "elbow_bad": 2, "core_surgery": 2, "broken_arm": 2,
               "torn_quad": 2, "pectoral": 2, "torn_calf": 2},
}


def length_group(u):
    """A length group for an injury that costs games, from u in [0, 1)."""
    x = u
    for grp, lo, hi, share in LENGTHS:
        if x < share:
            return grp, lo, hi
        x -= share
    grp, lo, hi, _s = LENGTHS[-1]
    return grp, lo, hi


def not_ready_games(kind, hurt_week, rng):
    """A season-ending injury from last season (hurt in regular-season week
    hurt_week; 0 = camp/preseason): games he misses at the start of this
    season (0 = ready for week 1), from the real return patterns above."""
    share = next(s for w, s in NOT_READY if hurt_week <= w)
    part = PART.get(kind)
    share *= NOT_READY_ACHILLES if kind == "achilles" else NOT_READY_BY_PART.get(part, 1.0)
    if rng.random() >= share:
        return 0
    lo, hi = NOT_READY_LONG_GAMES if rng.random() < NOT_READY_LONG else NOT_READY_SHORT_GAMES
    return rng.randint(lo, hi)


def pick_kind(group, u):
    """The specific injury within a length group ("shaken" for a knock that
    costs no games), from u in [0, 1)."""
    table = LENGTH_MIX[group]
    x = u * sum(table.values())
    for key, w in table.items():
        x -= w
        if x < 0:
            return key
    return key


# ---- Game-day status (real, weekly injury reports 2013-2025) ---------------
# Real reports list ~1,300-1,750 Questionable a season (2016-25; about two-thirds
# play), ~150-220 Doubtful (1% play) and ~1,000 Out. Before a player's last missed game he's listed Out 48%,
# Questionable 39%, Doubtful 13%; earlier missed games Out 69%, Questionable
# 22%, Doubtful 9%; in his first game back he's still listed Questionable 35%
# of the time. Players on injured reserve (long injuries) aren't listed.
STATUS_LAST_MISSED = (("Out", 0.48), ("Questionable", 0.39), ("Doubtful", 0.13))
STATUS_STILL_OUT = (("Out", 0.69), ("Questionable", 0.22), ("Doubtful", 0.09))
RETURN_QUESTIONABLE = 0.35
MINOR_QUESTIONABLE = 1.0      # shaken up last game: listed Questionable this week (then plays). Real
                              # teams also list knocks from practice (not modeled), so every in-game
                              # knock is listed: still ~10% fewer Questionable listings than real.
INJURED_RESERVE_WEEKS = 8     # expected to miss this many or more: on injured reserve, not listed
# When it's aggravated or flares up: he misses 1-3 more games (the short end of
# real injury lengths). Odds by injury: RECOVERY below.
AGGRAVATE_WEEKS = (1, 3)


# ---- Playing through it and coming back, by body part (real) ---------------
# tools/injury_recovery.py, 2018-25 regular seasons, regular players:
#   hurt      rating points below himself in a game he plays while listed. From
#             his per-play results (EPA) vs his own other games, blended toward
#             the all-injury average (-0.06 EPA) by sample size (1,000 plays of
#             weight on the average), at ~65 points per EPA (the sim matched
#             the real -4% yards for QBs at 3.3 points). Bruise-type injuries
#             (hand, ribs, hip) barely matter; hamstrings and concussions most.
#   aggravate chance per game played while listed that he misses the next game
#             with the same injury, minus a healthy player's chance of a new
#             injury there (hamstring 12.0% vs 0.5% ... back 1.9% vs 0.1%).
#   flare     per game, in his first 4 games back, chance it flares up and he
#             misses the next game, minus the healthy-player rate.
RECOVERY = {
    #            hurt  aggravate flare
    "hamstring": (5.6, 0.115, 0.034),
    "concussion": (5.7, 0.000, 0.007),
    "back":      (4.8, 0.018, 0.021),
    "ankle":     (4.3, 0.055, 0.023),
    "calf":      (4.0, 0.076, 0.034),
    "shoulder":  (3.8, 0.041, 0.017),
    "foot":      (3.8, 0.075, 0.030),
    "quad":      (3.3, 0.022, 0.012),
    "knee":      (3.3, 0.057, 0.020),
    "ribs":      (2.6, 0.057, 0.023),
    "groin":     (2.1, 0.077, 0.026),
    "hip":       (1.8, 0.043, 0.025),
    "hand":      (0.8, 0.049, 0.017),
}
RECOVERY_DEFAULT = (3.9, 0.050, 0.020)   # body parts with too few real cases: the all-injury averages
COMEBACK_GAMES = 4
# Which body part each injury is (for RECOVERY).
PART = {
    "ankle": "ankle", "ankle_sprain": "ankle", "high_ankle": "ankle", "high_ankle_bad": "ankle",
    "fractured_ankle": "ankle", "knee": "knee", "knee_sprain": "knee", "mcl_sprain": "knee", "mcl_tear": "knee",
    "acl": "knee", "knee_major": "knee", "hamstring_tight": "hamstring", "hamstring": "hamstring",
    "hamstring_bad": "hamstring", "muscle_tear": "hamstring", "head": "concussion", "concussion": "concussion",
    "concussion_long": "concussion", "concussion_season": "concussion", "shoulder": "shoulder",
    "shoulder_sprain": "shoulder", "ac_joint": "shoulder", "labrum": "shoulder", "groin_tight": "groin",
    "groin": "groin", "core_surgery": "groin", "abdominal": "groin", "back": "back", "back_strain": "back",
    "disc": "back", "hip": "hip", "hip_injury": "hip", "hip_bad": "hip", "hand": "hand", "hand_injury": "hand",
    "broken_hand": "hand", "ribs": "ribs", "rib_bruise": "ribs", "rib_fracture": "ribs", "calf": "calf",
    "calf_strain": "calf", "torn_calf": "calf", "quad": "quad", "torn_quad": "quad", "foot_sprain": "foot",
    "jones_fracture": "foot", "lisfranc": "foot", "turf_toe": "foot", "turf_toe_bad": "foot",
}


def recovery(kind):
    """(rating points off while playing listed, aggravation chance per game
    played listed, flare-up chance per game in his first games back)."""
    return RECOVERY.get(PART.get(kind), RECOVERY_DEFAULT)


def is_concussion(kind):
    return PART.get(kind) == "concussion" and kind != "head"


def pick_status(table, u):
    x = u
    for st, share in table:
        if x < share:
            return st
        x -= share
    return table[-1][0]


CAREER_SIZE_SCALE = 3.0      # all temporary and lasting rating losses. Tuned in simulated leagues (6 x 8
                             # seasons, real games): at 3.0 injured players' return rates match the real ones
                             # (season-ending: QB 78% vs 79%, WR/TE 73/73, DL 75/75, DB 76/79; knees 69 vs 62
                             # before the knee retire bump); at 1.0 injuries barely changed careers.
CAREER_RETIRE_SCALE = 1.0    # all retirement pushes


def get(key, position=None):
    """The injury's effects, adjusted for the player's position (POSITION_RISK)."""
    inj = CATALOG.get(key) or CATALOG["serious"]
    m = POSITION_RISK.get(inj.area, {}).get(position, 1.0) if position else 1.0
    inj = replace(inj, temp_size=inj.temp_size * CAREER_SIZE_SCALE, perm_size=inj.perm_size * CAREER_SIZE_SCALE,
                  retire=inj.retire * CAREER_RETIRE_SCALE)
    if m == 1.0:
        return inj
    return replace(inj, temp_chance=min(0.95, inj.temp_chance * m), perm_chance=min(0.95, inj.perm_chance * m),
                   temp_size=inj.temp_size * (0.5 + 0.5 * m), perm_size=inj.perm_size * (0.5 + 0.5 * m),
                   retire=min(0.9, inj.retire * m))


def name(key):
    """Display name; older saves stored a body part, shown as is."""
    return CATALOG[key].name if key in CATALOG else str(key)


def lasting(key):
    """Can this injury affect his career (step back, ceiling, retirement)?"""
    i = get(key)
    return bool(i.temp_chance or i.perm_chance or i.retire)
