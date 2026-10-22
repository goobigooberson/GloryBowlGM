# positions.py
# Everything that makes one position different from another:
#   - which skill ratings a position has, and how much each counts toward overall
#   - typical height and weight
#   - typical combine results
#
# This file is pure data. To rebalance positions later, edit the numbers here.

# ---------------------------------------------------------------------------
# Athletic traits
# Every player has five hidden athletic traits from 0 to 100. Speed, strength,
# agility and explosion are measured RELATIVE TO HIS POSITION: a guard with
# speed 80 is fast for a guard, not fast like a cornerback. Intelligence is
# the same scale for everyone.
# Combine results come from these traits (plus some luck), which is why the
# combine predicts ratings well but not perfectly.
# ---------------------------------------------------------------------------
ATHLETIC_TRAITS = ["speed", "strength", "agility", "explosion", "intelligence"]

# ---------------------------------------------------------------------------
# Skills
# key: (label shown to the player, {athletic trait: how much it feeds this skill})
# Whatever weight is left over (1.0 minus the trait weights) comes from the
# player's football ability: technique, instincts, things a stopwatch can't see.
# ---------------------------------------------------------------------------
SKILLS = {
    # Quarterback
    "screen_pass":    ("Screen Passing",       {"intelligence": 0.10}),
    "short_pass":     ("Short Passing",        {"intelligence": 0.10}),
    "medium_pass":    ("Medium Passing",       {"strength": 0.05}),
    "long_pass":      ("Long Passing",         {"strength": 0.15}),
    "deep_pass":      ("Deep Passing",         {"strength": 0.25}),
    "third_down":     ("Third-Down Passing",   {"intelligence": 0.15}),
    "accuracy":       ("Accuracy",             {}),
    "timing":         ("Timing",               {"intelligence": 0.10}),
    "sense_rush":     ("Sense Rush",           {"agility": 0.15}),
    "read_defense":   ("Read Defense",         {"intelligence": 0.30}),
    "two_minute":     ("Two-Minute Offense",   {"intelligence": 0.20}),
    "scrambling":     ("Scrambling",           {"speed": 0.35, "agility": 0.25}),
    "int_avoid":      ("Interception Avoidance", {"intelligence": 0.15}),

    # Ball carriers and receivers
    "vision":         ("Rushing Vision",       {"intelligence": 0.15}),
    "power_run":      ("Power Running",        {"strength": 0.40, "explosion": 0.15}),
    "elusiveness":    ("Elusiveness",          {"agility": 0.45, "speed": 0.10}),
    "breakaway":      ("Breakaway Speed",      {"speed": 0.65, "explosion": 0.10}),
    "hands":          ("Hands",                {}),
    "route_running":  ("Route Running",        {"agility": 0.25}),
    "getting_open":   ("Getting Open",         {"speed": 0.20, "agility": 0.15}),
    "traffic":        ("Catching in Traffic",  {"strength": 0.15}),
    "after_catch":    ("Run After Catch",      {"agility": 0.20, "speed": 0.20}),
    "fumble_avoid":   ("Fumble Avoidance",     {"strength": 0.15}),
    "kick_return":    ("Kick Returns",         {"speed": 0.40, "agility": 0.15}),
    "punt_return":    ("Punt Returns",         {"agility": 0.40, "speed": 0.15}),

    # Blocking
    "run_block":      ("Run Blocking",         {"strength": 0.35, "explosion": 0.10}),
    "pass_block":     ("Pass Blocking",        {"agility": 0.20, "strength": 0.20}),
    "footwork":       ("Footwork",             {"agility": 0.45}),
    "block_aware":    ("Blocking Awareness",   {"intelligence": 0.35}),
    "snapping":       ("Snapping",             {}),

    # Every defender
    "endurance":      ("Endurance",            {}),
    "run_defense":    ("Run Defense",          {"strength": 0.30}),
    "diagnosis":      ("Diagnosis",            {"intelligence": 0.35}),
    "hitting":        ("Hitting",              {"strength": 0.25, "explosion": 0.20}),

    # Front seven
    "rush_tech":      ("Pass Rush Technique",  {"agility": 0.25}),
    "rush_power":     ("Pass Rush Power",      {"strength": 0.45, "explosion": 0.15}),
    "shed":           ("Block Shedding",       {"strength": 0.30}),
    "pursuit":        ("Pursuit",              {"speed": 0.40}),

    # Coverage
    "man_cover":      ("Man Coverage",         {"speed": 0.25, "agility": 0.20}),
    "zone_cover":     ("Zone Coverage",        {"intelligence": 0.25}),
    "bump_run":       ("Bump-and-Run",         {"strength": 0.20, "agility": 0.15}),
    "ball_skills":    ("Ball Skills",          {"explosion": 0.15}),

    # Kickers and punters
    "kick_power":     ("Kicking Power",        {"strength": 0.30}),
    "kick_accuracy":  ("Kicking Accuracy",     {}),
    "kickoff":        ("Kickoff Distance",     {"strength": 0.30}),
    "punt_power":     ("Punting Power",        {"strength": 0.30}),
    "hang_time":      ("Hang Time",            {}),
    "directional":    ("Directional Punting",  {}),

    # Long snappers
    "long_snap":      ("Snap Accuracy",        {}),
    "snap_speed":     ("Snap Velocity",        {"strength": 0.20, "explosion": 0.10}),
    "coverage":       ("Coverage Tackling",    {"speed": 0.30, "strength": 0.10}),
}

# Ratings scouts can never see. You judge these from stats only.
HIDDEN_SKILLS = {"int_avoid", "fumble_avoid"}

# ---------------------------------------------------------------------------
# Positions
# For each position: full name, and its skills with the weight each one
# carries in the overall rating. Weight 0 means the skill is shown but does
# not count toward overall (return skills, for example).
# ---------------------------------------------------------------------------
_DEFENDER = [("endurance", 1), ("run_defense", 3), ("diagnosis", 2), ("hitting", 2)]
_RETURNS = [("kick_return", 0), ("punt_return", 0)]

POSITIONS = {
    "QB":  ("Quarterback", [
        ("screen_pass", 1), ("short_pass", 3), ("medium_pass", 3), ("long_pass", 2),
        ("deep_pass", 2), ("third_down", 2), ("accuracy", 4), ("timing", 2),
        ("sense_rush", 2), ("read_defense", 3), ("two_minute", 1), ("scrambling", 1),
        ("int_avoid", 0)]),
    "RB":  ("Running Back", [
        ("vision", 3), ("power_run", 2), ("elusiveness", 3), ("breakaway", 2),
        ("hands", 1), ("route_running", 1), ("pass_block", 1),
        ("fumble_avoid", 0), ("endurance", 0)] + _RETURNS),
    "FB":  ("Fullback", [
        ("run_block", 4), ("pass_block", 2), ("power_run", 2), ("vision", 1),
        ("hands", 1), ("route_running", 1), ("fumble_avoid", 0)]),
    "TE":  ("Tight End", [
        ("hands", 3), ("route_running", 2), ("getting_open", 2), ("traffic", 2),
        ("after_catch", 1), ("run_block", 3), ("pass_block", 1), ("fumble_avoid", 0)]),
    "WR":  ("Wide Receiver", [
        ("hands", 3), ("route_running", 3), ("getting_open", 3), ("traffic", 2),
        ("after_catch", 2), ("breakaway", 2), ("run_block", 1),
        ("fumble_avoid", 0)] + _RETURNS),
    "T":   ("Tackle", [
        ("pass_block", 4), ("run_block", 3), ("footwork", 3), ("block_aware", 2)]),
    "G":   ("Guard", [
        ("run_block", 4), ("pass_block", 3), ("footwork", 2), ("block_aware", 2)]),
    "C":   ("Center", [
        ("run_block", 3), ("pass_block", 3), ("footwork", 2), ("block_aware", 3),
        ("snapping", 1)]),
    "DE":  ("Defensive End", _DEFENDER + [
        ("rush_tech", 4), ("rush_power", 3), ("shed", 2), ("pursuit", 2)]),
    "DT":  ("Defensive Tackle", _DEFENDER + [
        ("rush_tech", 2), ("rush_power", 3), ("shed", 4), ("pursuit", 1)]),
    "OLB": ("Outside Linebacker", _DEFENDER + [
        ("rush_tech", 2), ("rush_power", 1), ("shed", 1), ("pursuit", 3),
        ("man_cover", 1), ("zone_cover", 2), ("bump_run", 1)]),
    "ILB": ("Inside Linebacker", _DEFENDER + [
        ("shed", 2), ("pursuit", 3), ("man_cover", 1), ("zone_cover", 2),
        ("rush_tech", 1)]),
    "CB":  ("Cornerback", _DEFENDER + [
        ("man_cover", 4), ("zone_cover", 3), ("bump_run", 2), ("ball_skills", 2),
        ("pursuit", 1)] + _RETURNS),
    "S":   ("Safety", _DEFENDER + [
        ("zone_cover", 4), ("man_cover", 2), ("bump_run", 1), ("ball_skills", 2),
        ("pursuit", 2)]),
    "K":   ("Kicker", [
        ("kick_power", 3), ("kick_accuracy", 4), ("kickoff", 2)]),
    "LS":  ("Long Snapper", [
        ("long_snap", 4), ("snap_speed", 2), ("coverage", 1)]),
    "P":   ("Punter", [
        ("punt_power", 3), ("hang_time", 3), ("directional", 2)]),
}

# ---------------------------------------------------------------------------
# REAL-WORLD DATA
# The numbers below come from actual NFL Scouting Combine results, 2010-2026,
# for players who were drafted (source: the nflverse open combine dataset,
# github.com/nflverse/nflverse-data). "Spread" is the standard deviation:
# about two-thirds of players land within one spread of the average.
# Kicker and punter drill numbers marked (est.) are estimates: so few of them
# do those drills that there isn't enough real data. Long snapper numbers come
# from only 32 combine invitees (2006-2023), so they're rougher than others.
# ---------------------------------------------------------------------------

# Body size: (average height in inches, spread, average weight in lbs, spread)
# Taller players also come out heavier (about 5 lbs per inch).
BODY = {
    "QB":  (74.9, 1.75, 222, 10),
    "RB":  (70.5, 1.7,  213, 12),
    "FB":  (72.7, 1.6,  243, 7),
    "TE":  (76.5, 1.35, 251, 8.5),
    "WR":  (72.5, 2.3,  201, 15),
    "T":   (77.7, 1.15, 315, 11.5),
    "G":   (76.2, 1.15, 315, 10.5),
    "C":   (75.7, 1.1,  306, 7.5),
    "DE":  (75.9, 1.35, 264, 14.5),
    "DT":  (75.2, 1.45, 309, 16),
    "OLB": (74.0, 1.4,  243, 10.5),
    "ILB": (73.3, 1.3,  241, 7),
    "CB":  (71.6, 1.55, 194, 8.5),
    "S":   (72.3, 1.5,  207, 9),
    "K":   (72.0, 2.2,  196, 15),
    "P":   (74.3, 1.85, 211, 11.5),
    "LS":  (74.2, 1.9,  242, 12),
}

# Combine drills: (average, spread, share of players who do the drill)
# Units: forty, cone, shuttle in seconds; bench in reps of 225 lbs;
# vertical and broad jump in inches.
# Many players skip drills (QBs almost never bench), and the skipped
# results show as "Did not test", just like a real combine.
COMBINE_DRILLS = ["forty", "bench", "vertical", "broad", "cone", "shuttle"]

COMBINE = {
    "QB":  {"forty": (4.80, .18, .68), "bench": (17, 3.0, .01), "vertical": (31.7, 3.1, .69),
            "broad": (113, 6.7, .67), "cone": (7.08, .19, .59), "shuttle": (4.32, .15, .61)},
    "RB":  {"forty": (4.52, .10, .83), "bench": (19, 4.6, .61), "vertical": (34.9, 3.3, .83),
            "broad": (121, 5.2, .79), "cone": (7.02, .19, .36), "shuttle": (4.26, .14, .43)},
    "FB":  {"forty": (4.75, .14, .83), "bench": (24, 5.9, .78), "vertical": (34.4, 2.8, .72),
            "broad": (115, 5.2, .72), "cone": (7.16, .18, .67), "shuttle": (4.31, .13, .67)},
    "TE":  {"forty": (4.71, .12, .76), "bench": (20, 4.3, .57), "vertical": (33.9, 3.0, .72),
            "broad": (118, 5.8, .70), "cone": (7.12, .19, .51), "shuttle": (4.36, .13, .55)},
    "WR":  {"forty": (4.47, .09, .85), "bench": (15, 4.1, .53), "vertical": (36.1, 2.9, .84),
            "broad": (123, 5.8, .82), "cone": (6.93, .19, .50), "shuttle": (4.22, .14, .53)},
    "T":   {"forty": (5.18, .17, .79), "bench": (24, 4.7, .44), "vertical": (28.7, 3.1, .76),
            "broad": (105, 6.7, .74), "cone": (7.77, .27, .53), "shuttle": (4.73, .17, .55)},
    "G":   {"forty": (5.23, .16, .83), "bench": (27, 5.6, .37), "vertical": (27.7, 2.9, .82),
            "broad": (103, 6.3, .82), "cone": (7.78, .27, .62), "shuttle": (4.74, .18, .65)},
    "C":   {"forty": (5.21, .15, .71), "bench": (26, 5.2, .34), "vertical": (28.3, 3.1, .68),
            "broad": (103, 6.3, .67), "cone": (7.64, .23, .49), "shuttle": (4.65, .17, .54)},
    "DE":  {"forty": (4.75, .15, .75), "bench": (24, 4.6, .59), "vertical": (33.9, 3.0, .74),
            "broad": (118, 6.2, .73), "cone": (7.20, .21, .43), "shuttle": (4.40, .16, .45)},
    "DT":  {"forty": (5.06, .17, .74), "bench": (28, 5.5, .51), "vertical": (29.3, 3.1, .74),
            "broad": (106, 6.4, .69), "cone": (7.64, .28, .48), "shuttle": (4.65, .17, .52)},
    "OLB": {"forty": (4.67, .10, .99), "bench": (23, 4.7, .74), "vertical": (34.6, 3.2, .82),
            "broad": (119, 6.3, .82), "cone": (7.10, .22, .62), "shuttle": (4.31, .14, .63)},
    "ILB": {"forty": (4.72, .11, .84), "bench": (22, 3.9, .84), "vertical": (33.8, 2.7, .80),
            "broad": (117, 4.8, .78), "cone": (7.08, .20, .52), "shuttle": (4.29, .14, .61)},
    "CB":  {"forty": (4.47, .08, .84), "bench": (15, 4.0, .54), "vertical": (36.3, 2.7, .72),
            "broad": (124, 5.8, .70), "cone": (6.89, .19, .38), "shuttle": (4.16, .13, .40)},
    "S":   {"forty": (4.53, .09, .78), "bench": (17, 4.0, .59), "vertical": (36.0, 3.0, .76),
            "broad": (123, 6.2, .74), "cone": (6.94, .21, .36), "shuttle": (4.20, .13, .39)},
    "K":   {"forty": (4.90, .14, .24), "bench": (13, 4.0, .04),          # bench onward: est.
            "vertical": (30.0, 3.0, .02), "broad": (110, 6.0, .02),
            "cone": (7.30, .25, .02), "shuttle": (4.45, .18, .02)},
    "LS":  {"forty": (5.03, .16, .94), "bench": (17, 4.9, .53), "vertical": (29.3, 2.8, .53),
            "broad": (109, 6.9, .56), "cone": (7.44, .25, .41), "shuttle": (4.53, .19, .44)},
    "P":   {"forty": (4.85, .16, .48), "bench": (16, 5.0, .07), "vertical": (31.6, 2.5, .18),
            "broad": (115, 5.0, .15), "cone": (7.30, .25, .03),          # cone, shuttle: est.
            "shuttle": (4.45, .18, .05)},
}

# ---------------------------------------------------------------------------
# POSITIONAL SCARCITY
# Two settings per position, tuned so each position has a realistic number
# of good players (see the table below). Applies to every player ever made
# at that position: starting rosters, free agents and all future draft
# classes.
#
# TALENT_SHIFT: how much talent the position has overall, in talent points
#   (all players average 50, spread about 17).
# TALENT_SPREAD_MULT: how far apart the best and worst are (1.0 = normal).
#   Below 1.0 = "replaceable": backups and free agents aren't far behind the
#   starters (running backs, linebackers, kickers). Above 1.0 = a few stars
#   and a steep drop-off (tackles, edge rushers).
#
# Targets per league (before Generational players, who add 3-7 more elites):
#   pos  Elite 90+  rated 80+  starter avg  best free agent   why
#   QB       2          6          70            43        the scarcest position in football
#   RB       1          6          72            55        replaceable: decent backs are easy to find
#   FB       0          2          62            54        a dying position; cheap and available
#   TE       1          4          68            47        true two-way TEs are rare
#   WR       4         18          70            50        deepest skill position in today's game
#   T        2         10          68            46        good tackles, especially LTs, are scarce
#   G        1          8          67            52        solid guards are findable
#   C        1          4          68            50
#   DE       2         10          70            46        elite pass rushers are scarce
#   DT       1-2        8          68            48
#   OLB      1-2        8          68            49
#   ILB      1          5          70            52        replaceable
#   CB       2         10          70            47        shutdown corners are scarce
#   S        1-2        9          68            50
#   K        4         14          76            65        most kickers are good; easy to replace
#   P        3         12          74            65        same as kickers
#   LS       3         12          74            65        same: most snappers are reliable
# These targets are judgment calls about the real league, not measured
# data. Change them by adjusting the two settings below.
# Measured result: 80+ counts, starter averages and best free agents land
# on target. Elite (90+) tackles, edge rushers and corners come out a bit
# under target (about 1 per league each); Generational players add more.
# ---------------------------------------------------------------------------
TALENT_SHIFT = {
    "QB": -9,
    "RB": +11,
    "FB": +7,
    "TE": -5,
    "WR": +1,
    "T": -9,
    "G": +5,
    "C": +0,
    "DE": -6,
    "DT": -4,
    "OLB": -2,
    "ILB": +5,
    "CB": -4,
    "S": -1,
    "K": +11,
    "P": +12,
    "LS": +13,
}

TALENT_SPREAD_MULT = {
    "QB": 0.8,
    "RB": 0.6,
    "FB": 0.6,
    "TE": 0.7,
    "WR": 0.9,
    "T": 1.3,
    "G": 1.0,
    "C": 0.9,
    "DE": 1.0,
    "DT": 1.0,
    "OLB": 1.0,
    "ILB": 0.6,
    "CB": 0.8,
    "S": 0.9,
    "K": 1.2,
    "P": 0.9,
    "LS": 1.0,
}

# Positions that tend to score higher on the intelligence test.
INTELLIGENCE_BONUS = {"QB": 10, "C": 6, "S": 3, "ILB": 3, "T": 2, "G": 2}
