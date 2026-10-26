# tuning.py
# The knobs that decide how much player ratings matter in the game sim.
#
# The baseline for every play comes from the real NFL (data.py). These knobs
# control how far a play's result moves away from that baseline when the
# players involved are better or worse than an average NFL starter.
#
# Ratings are compared as "z-scores": 0 = an average starter at that
# position, +1 = clearly better than average (about the 84th percentile),
# -1 = clearly worse. A knob of 0.30 means "one z-score of advantage moves the
# result 0.30 of a step", where the step size depends on what's being moved.
#
# These were set by calibration: simulating thousands of games and full
# seasons and comparing the stats to the real NFL (2023-2025). Change one
# knob at a time and re-check with step6_season_test.py.

# ---- Pass rush and protection ---------------------------------------------
RUSH_WIN_BASE = -1.59        # logit: an average rusher vs an average blocker
RUSH_WIN_K = 0.27            # how much each z of rusher-vs-blocker edge matters
FREE_RUSHER_WIN = 0.42       # an unblocked blitzer gets home this often
CHIP_EDGE = 0.8              # a rusher winning his matchup by this much draws a chip from a back or TE
RUSH_EDGE_CAP = 1.4          # z: how far below average a pass blocker can drag the matchup (diminishing returns; keeps team sack totals in the real 14-70 range)
RUSH_INTERIOR = -1.55        # logit: inside rushers face guards, the center's help and a QB who can step up
                             # (real NFL: defensive tackles get about 20-25% of sacks, edge rushers most of the rest)
SACK_GIVEN_PRESSURE = -1.55  # logit: share of pressures that become sacks
SACK_SENSE_RUSH_K = 0.24     # QBs who feel pressure take fewer sacks
SACK_SCRAMBLE_K = 0.10       # mobile QBs escape more often
HIT_ON_HURRIED_THROW = 0.42
CLEANUP_WEIGHT = {"DE": 0.4, "DT": 0.25}  # who finishes a clean-up sack (blitzers and other spots 1.0)
                             # (Oct 25: was DE 0.7, DT 0.35. Half the clean-ups went to the other end, so
                             # too many second ends reached 10 sacks: 23.5 10+ sack seasons and 12.6 12+
                             # vs real 18.8 / 9.8 on settled leagues; team #2 sacker 7.4 vs real 6.8;
                             # sacks from players with under 3 just 20% vs real 26%.)
SACK_CLEANUP = 0.45          # share of sacks finished by someone other than the man who won first
                             # (Oct 19: 0.55 -> 0.45; sacks were spread too evenly: leader 17.3 vs real 20.1, too many 10-12 sack rushers)

# ---- Scrambles -----------------------------------------------------------
SCRAMBLE_UNPRESSURED = 0.019 # base: QB tucks it when nobody is open
SCRAMBLE_PRESSURED = 0.17    # base share of escaped pressures that become runs
SCRAMBLE_SKILL_K = 0.50      # logit per z of the QB's scrambling rating
                             # (Oct 25: 0.85 -> 0.50. The best scramblers scrambled far too often: top QBs
                             # 81/64/55/38/21 scrambles a season (#1/#3/#5/#10/#20) vs real 63/49/44/32/19,
                             # 500+ scramble-yard seasons 2.9 a season vs real 0.6; nflverse 2021-25)
SCRAMBLE_YARDS_K = 0.35      # tilt per z of scrambling on how far he gets

# ---- Coverage and target choice ------------------------------------------
SEPARATION_NOISE = 0.95      # random play-to-play noise in getting open
TARGET_SEP_WEIGHT = 0.20     # QBs favor open receivers...
TARGET_READ_K = 0.30         # ...and good readers find them more reliably
TARGET_TALENT_WEIGHT = 0.15  # QBs feed their best receivers
FED_COVER_FROM = 8           # after this many targets in a game... (Oct 23: 6 -> 8 and TARGET_SATURATION
                             # 10 -> 13: 12+ catch games ran 3.5 a season vs real 15.8, tools/game_extremes_check.py)
FED_COVER_K = 0.14           # ...each extra one tightens his coverage this much (z)
TARGET_EDGE_CAP = 0.55       # most openness + talent can pull the ball toward one receiver (logit)
TARGET_SATURATION = 13       # targets in a game before the ball starts spreading around
TARGET_SATURATION_K = 0.10   # logit per extra target
TARGET_ROLE_BIAS = {         # extra pull toward each player's role (shapes target shares)
    "WR1": 0.48, "WR2": 0.34, "WR3": 0.16, "WR4": 0.05,
    "TE1": -0.08, "TE2": 0.24, "TE3": -0.30,
    "RB": -0.26, "FB": -1.20,
    "WR_BACKUP": -0.15,     # a receiver with no starting role, filling in while a starter rests
}
# (Oct 23: WR1 0.38 -> 0.48, WR2 0.28 -> 0.34, WR3 0.14 -> 0.16 and WR_BACKUP added once receivers
# rotate like real ones and the pull follows the player: the rotation took ~11% of the top
# receivers' snaps and their targets went to backups, cutting the league's top receiver from
# ~1,810 yards to ~1,590; real stars keep their share of throws. TE1 -0.22 -> -0.08 with it, or the
# receivers' boost took the tight ends' share: TE #3/#5 in receiving yards fell to 809/717 vs real 966/825.)
TE_FEATURE_FROM = 0.8        # a starting tight end this far above the average starter (talent z)...
TE_FEATURE_K = 0.25          # ...gets this much more pull toward him per z beyond it (gameteam: featured star TE)
                             # (Oct 25, real 2021-25 TE targets by rank #1/#2/#3/#5/#10/#20: 154/131/119/106/88/68;
                             # before 134/119/111/100/84/64, after 144/128/118/105/86/65 over 48 seasons)
ROUTE_DEPTH_TILT = 0.20      # overall push on route depths (matches the real aDOT)
POSITION_DEPTH = {"WR": -0.10, "TE": -0.35}  # route depth by position group (real aDOT: WR 10.8, TE 6.3)
RB_CATCH_BONUS = 0.20        # logit: backs catch checkdowns more often than the depth alone says
RB_YAC_BONUS = 0.15          # tilt: backs run after the catch in space
RZ_SPREAD = 0.40             # inside the 10, talent and separation matter this much less in who gets the ball
                             # (tight windows: real touchdown catches are spread around more than yards are)
RED_ZONE_ROLE = {"TE": 0.35, "WR": 0.0, "RB": -0.15}  # target lean inside the 10 (real: TEs get 27%)
# Defenses roll extra coverage (a safety over the top, a bracket) to the
# other team's best receiver, more when he's far better than the rest. This
# is what keeps a star on a weak supporting cast from going for 2,000 yards.
SHADE_RATE = 0.40            # base share of passing downs with a shade (team style varies it)
SHADE_GAP_K = 0.9            # more likely when the star is far better than receiver #2
SHADE_COVER = 1.10           # coverage boost on the shaded receiver (z units)
SHADE_OTHERS = 0.10          # everyone else is a little more open
SHADE_HOT_K = 0.012          # per receiving yard over 40 in this game: the defense adjusts to a hot receiver
DEEP_SPEED_K = 0.03          # per sd of speed: fast receivers run deeper routes
WR_ROUTE_SCALE = 1.00        # receivers' route skill vs coverage (keeps elite receivers' efficiency in the real range)
TE_ROUTE_SCALE = 0.70        # tight ends' route skill vs coverage, relative to receivers'
THROWAWAY_RATE = 0.021       # throwaways per clean-pocket attempt with average coverage
THROWAWAY_HURRIED = 7.0      # ...multiplied this much under pressure
THROWAWAY_SEP_K = 0.9        # fewer throwaways when someone is open
GROUNDING_SHARE = 0.16       # pressured throwaways flagged for intentional grounding
DEEP_ARM_K = 0.012           # per yard per z: strong arms look deeper

# ---- Completion, interception, yards after catch -------------------------
COMP_ACCURACY_K = 0.15       # logit per z of QB accuracy for that depth (0.28 before Oct 23: the best QBs completed
                             # too many passes; part of a QB's results now comes from his hidden knack, KNACK_SD)
                             # (Oct 21: 0.19 -> 0.28; completion % barely depended on the QB: top passers
                             # 64.3% vs worst starters 64.7%, real 68.2% vs 63.9%)
COMP_SEPARATION_K = 0.16     # logit per unit of separation (open vs covered)
COMP_HANDS_K = 0.22          # logit per z of receiver hands
COMP_DEFENDER_K = 0.10       # logit per z of the covering defender's ball skills
COMP_HURRIED = -0.55         # logit when the throw is hurried by pressure
COMP_SCALE = 0.18            # logit: overall completion level (fine-tunes the league rate)
COMP_CAP = 0.55              # most one pass's matchups can move its completion odds (logit)
YAC_CAP = 0.40               # most one catch's matchups can tilt yards after catch
RUN_CAP = 0.55               # most one run's matchups can tilt it (stacked edges have diminishing returns)
INT_SKILL_K = 0.15           # interception odds per z of QB decision-making (0.27 before Oct 23, as COMP_ACCURACY_K)
INT_DEFENDER_K = 0.22        # per z of the defender's ball skills
INT_HURRIED = 0.55           # pressure makes interceptions more likely
INT_SEPARATION_K = 0.30      # throws into tight coverage get picked more
INT_SCALE = 1.035            # overall multiplier (1.00 before Oct 23; after INT_SKILL_K 0.27 -> 0.15 and recentering,
                             # league interceptions ran ~6% under real)
YAC_K = 0.08                 # tilt per z of receiver run-after-catch vs tacklers
YAC_SEP_K = 0.04             # wide-open receivers gain more after the catch
YAC_SCALE = 0.08             # tilt: overall yards after catch (fine-tunes league YPA)
DROP_RATE = 0.035            # share of catchable balls dropped by an average receiver
DROP_HANDS_K = 0.45          # per z of hands

# ---- Runs ---------------------------------------------------------------
RUN_SCALE = 0.02            # tilt: overall level of designed runs (fine-tunes league YPC)
RUN_BLOCK_K = 0.20           # tilt per z of blockers vs defenders at the hole
RUN_BACK_K = 0.13            # tilt per z of the ball carrier vs second level
RUN_BREAKAWAY_K = 0.17       # extra tilt on long runs: speed vs safeties
RUN_BOX_LIGHT = 0.22         # tilt vs a nickel/dime box (fewer defenders)
RUN_BOX_HEAVY = -0.10        # tilt vs a base 4-3 box
# Loading the box (Oct 20, Blake): against a dangerous running back the
# defense walks a safety down into an 8-man box. Runs gain less; the passing
# game gets lighter coverage, play action most of all, and fewer rolled
# coverages to a receiver. More often the better the back, the hotter he is
# today and the more his team runs. (Before this, star backs ran as freely as
# anyone: 1,600-yard seasons were about 3x as common as real.)
LOAD_BOX_RATE = 0.25        # share of early-down snaps with a loaded box vs a back rated +1 z
LOAD_BOX_MIN = 0.3           # backs below this talent z don't draw it
LOAD_BOX_THREAT_K = 0.8      # more against a better back (log-odds per z)
LOAD_BOX_HOT_K = 0.003       # per rushing yard over 50 in this game (Oct 20: 0.008 -> 0.003 so a back
                             # having a monster day keeps running; 0.008 left no 2,000-yard seasons in 16)
LOAD_BOX_LEAN_K = 1.0        # run-heavy offenses see it more (per unit of run lean)
LOAD_BOX_MAX = 0.65
LOAD_BOX_RUN = -0.35         # tilt on a run into a loaded box (about 0.4 yards per carry)
LOAD_BOX_PASS = 0.12         # separation for every receiver (one fewer man in coverage)
LOAD_BOX_PA = 0.15           # extra separation on play action vs a loaded box
LOAD_BOX_SHADE = 0.5         # rolled coverage to a receiver this much less likely (the safety is in the box)
# Near the goal line the field shrinks (yard line, tilt): fewer yards per
# carry and the real NFL's touchdown rates from each spot.
RUN_FIELD = ((1, -1.15), (2, -0.88), (3, -0.74), (5, -0.60), (10, -0.48), (15, -0.30), (20, -0.12),
             (30, -0.05), (40, 0.0))
PASS_FIELD = ((3, -0.50), (5, -0.50), (10, -0.42), (15, -0.20), (20, -0.06), (25, 0.0))
# Room to run after the catch (yards from the catch point to the goal line, tilt)
YAC_FIELD = ((0, -0.8), (10, -0.6), (20, -0.3), (35, 0.0))
WR_RUN_SHARE = 0.022          # designed runs that are jet sweeps / end-arounds to a receiver
QB_GOAL_LINE_RUN = 0.8       # logit: QB keepers and pushes are more common at the 1-3 (real: QBs score ~20% of rushing TDs)
QB_RUN_SHARE = 0.026         # base share of designed runs that are QB keepers
QB_RUN_MOBILITY_K = 1.5      # logit per z of QB scrambling
                             # (Oct 25: 0.035 / 0.75 -> 0.026 / 1.5. Real offenses build designed runs around a
                             # truly mobile QB: real top QBs 86/64/44/23/13 designed carries a season
                             # (#1/#3/#5/#10/#20, sneaks included) vs the game's 55/38/34/25/17, so the game's
                             # 600-yard rushers got there almost all on scrambles. League QB runs unchanged.)
QB_KEEP_SKILL_K = 3.2        # how much the QB's mobility (scrambling) moves a designed QB run, vs 1.0 for a back's skills
                             # (Oct 25: was 0.8, built into plays.run_play. Real defenses have to respect a running
                             # QB on a keeper: the most mobile QBs gain 6.2 yards a keeper in the open field vs 4.7
                             # for the rest (nflverse 2021-25); the game gave them ~4.5 vs ~4.1.)
SNEAK_SUCCESS = 0.80         # QB sneak converts this often vs an average line

# ---- Turnovers on carries -------------------------------------------------
# Who fumbles, matched to the real split (Oct 22; nflverse weekly player stats 2021-25, per team
# game): QBs 0.53 (0.30 on sacks, 51% lost; 0.24 on runs, scrambles and fumbled snaps/handoffs,
# ~30% lost), backs/receivers on carries 0.17 (0.74% of carries, 60% lost), on catches 0.22
# (1.03% of catches, 53% lost). Before, ball carriers fumbled ~3x too often (2.05% of designed
# runs) and QBs ~2.5x too rarely, with one 49% recovery share: the league total was right,
# the split wasn't.
FUMBLE_RUN = 0.0056          # fumbles per designed run by a back or receiver (average carrier; the hit and
                             # ball-security factors average ~1.2x, giving about the real 0.74%)
FUMBLE_QB_RUN = 0.015        # per QB carry (designed run, scramble, sneak)
FUMBLE_EXCHANGE = 0.0072     # per designed run: the snap or handoff is fumbled (credited to the QB)
FUMBLE_CATCH = 0.0090        # fumbles per reception (x the same factors: about the real 1.03%)
FORCED_SHARE = 0.56          # share of run/catch fumbles credited as 'forced' to a defender (real: about 2 in 3;
                             # the rest are bad exchanges, slips and balls that just come out)
FUMBLE_SACK = 0.115          # strip-sack share of sacks (real ~12%)
FUMBLE_LOST_BY_KIND = {"sack": 0.51, "qb": 0.30, "run": 0.60, "catch": 0.53}  # defense recovers (real)
FUMBLE_SKILL_K = 0.55        # per z of the hidden fumble-avoidance rating
TACKLE_SKILL_K = 0.20        # better tacklers get in on more stops
                             # (Oct 23, tried 0.26 with the middle linebacker's weight 7% lower: 12+ tackle games
                             # ~7 fewer a season, but 80+ tackle players 113 -> 121 (real 102) and 80+ tackle DBs
                             # 57 -> 64 (real 46): it piles stops on starters. Kept 0.20.)
TACKLE_ASSIST = {"short": 0.42, "mid": 0.32, "long": 0.17, "break": 0.10}  # share of tackles made by two players
                             # (Oct 23, tried 0.35/0.27/0.14/0.08: assists run 30.4 a team game vs real 25.4 and
                             # 12+ tackle games 1.8x real, but fewer assists pushed the season leaders below real
                             # while mid-pack totals stayed high: the gap is game-to-game spread, not volume. Kept.)
                             # (in traffic near the line more; in the open field mostly one man: real DBs make more solo tackles)
# Who makes the tackle, by how far the ball carrier got (relative weight per player on the field).
# Set so each position group's share of tackles and the leaderboards match the real NFL (2021-25):
# middle linebackers lead the league, defensive linemen spread their tackles over a rotation.
TACKLE_POOL = {
    "short": {"MLB": 2.85, "WLB": 2.46, "SLB": 2.04, "DE": 1.9, "DT": 2.38, "SS": 1.12, "FS": 0.47, "NB": 0.56, "CB": 0.56, "DB": 0.59},
    "mid": {"MLB": 2.7, "WLB": 2.26, "SLB": 1.7, "DE": 0.6, "DT": 0.75, "SS": 1.9, "FS": 1.62, "NB": 0.82, "CB": 0.82, "DB": 0.81},
    "long": {"MLB": 1.15, "WLB": 0.9, "SLB": 0.51, "DE": 0.15, "DT": 0.19, "SS": 2.24, "FS": 2.2, "NB": 1.07, "CB": 1.28, "DB": 1.15},
    "break": {"MLB": 0.3, "WLB": 0.23, "SLB": 0.0, "DE": 0.0, "DT": 0.0, "SS": 3.36, "FS": 3.52, "NB": 1.2, "CB": 1.65, "DB": 1.35},
}
# (Oct 23: matched to real tackles per game by ROLE at the same share of defensive snaps (real 2023-25
# snap counts joined to weekly stats; real 3-4 edge rushers listed as LB counted with the line):
# full-time corners 4.6 a game (game had 5.5), full-time safeties 6.0 (5.2), linebackers playing 60-85%
# of snaps 6.2 (weak-side LBs 7.5), defensive tackles at 60-85% 3.2 (2.7). Was WLB 3.15/2.9/1.15/0.3,
# SLB 2.4/2.0/0.6, DE and DT one "DL" 1.9/0.6/0.15, SS 1.0/1.7/2.0/3.0, FS 0.43/1.47/2.0/3.2,
# CB and NB 0.74/1.09/1.7(NB 1.42)/2.2(NB 1.6), DB 0.66/0.9/1.28/1.5. Corners and weak-side LBs piled up
# tackles: 12+ tackle games ran 180-188 a season vs real 151 (tools/game_extremes_check.py).)
TFL_POA_SHARE = 0.30         # runs stopped behind the line: share made by the men at the point of attack
PD_RATE = 0.37               # incompletions broken up by the covering defender (plus ball skills)
CB_SIDE_SWAP = 0.35          # share of pass plays the top receiver lines up across from the #2 corner
                             # (corners mostly play sides; tuned to each team's #1 in passes defensed)
BATTED_RATE = 0.085          # incompletions batted down or tipped at the line by a pass rusher
ST_ASSIST = 0.25             # kick and punt return tackles made by two players
ST_OFFENSE_SHARE = 0.32      # coverage tackles made by backups from the offense (RB, WR, TE)
FUMBLE_LOST_SHARE = 0.49     # share of fumbles the defense recovers (anything without a kind)
# Return fumbles (real play-by-play 2023-25): kick returns fumbled 1.7% of the time (52% lost to the
# kicking team); punts with a returner: 0.105 fumbles/muffs a team game, 0.039 lost (37%).
KR_FUMBLE = 0.017
KR_FUMBLE_LOST = 0.52
PR_MUFF = 0.035              # per punt the returner handles (fair catches are separate)
PR_MUFF_LOST = 0.37
SAFETY_ESCAPE = 0.72         # backed up: losses that would be a safety stop at the 1 this often

# ---- Special teams ------------------------------------------------------
FG_ACCURACY_K = 0.26         # logit per z of kicker accuracy
FG_POWER_K = 0.03            # extra per z of power per yard beyond 40
FG_SCALE = 0.15             # logit: overall field goal accuracy (real: 85% on 20+ attempt kickers)
FG_KICK_NOW_SECONDS = 8      # end of a half, 1st-3rd down, a timeout left: keep running plays (get closer, then
                             # use the timeout) until this many seconds are left, then kick. Oct 23: real 2023-25
                             # (pbp) early-down field goals come with 0-8 s left (~110 a season), almost never 9-24 s
                             # (~4); the game kicked at up to 16-24 s and tried 60+ yarders 27.7 times a season
                             # (real 13.6, range 9-22; 2023-25 15.3). With 8: 15.5, points per game unchanged.
PUNT_SCALE = 1.0            # yards: overall punt distance (real: 47.1 gross for 40+ punt punters)
PUNT_POWER_K = 2.6           # yards per z of punting power
RETURN_K = 0.30              # tilt per z of returner vs coverage

# ---- Penalties ------------------------------------------------------------
PENALTY_SCALE = 1.07         # overall multiplier on real penalty rates

# ---- Calling your own plays (engine/sim/playcalling.py) ---------------------
# Only for a team whose plays you've called (from the first call that isn't the coordinator's):
# AI teams' games never use these. The other side reads your calls against your coordinator's
# film: a call you make more than he would, beyond what chance explains, gets worse; one you
# make less gets a little better. "Over-use" = (your share - his share) of that kind of play,
# shrunk toward 0 early in the game (READ_N0) and minus READ_CHANCE_Z chance spreads.
# Real yardstick (nflverse 2021-25, quarters 1-4 outside the 2-minute drill, win chance 10-90%):
# a team running ~20% more than its own season mix in a game gains ~0.3 yards a run less than
# usual; passing ~20% more, ~0.3 yards a pass play less; the under-used kind gains little.
READ_N0_GAME = 8.0           # plays of shrinkage for the whole game's tendencies
READ_N0_SITUATION = 6.0      # ... and for this down-and-distance's tendencies
READ_CHANCE_Z = 0.5          # deviation within half a chance spread doesn't count (his own mix reads ~0)
READ_ALLOW = 1.0             # ... nor the first extra call: one surprise deep shot isn't a tendency
READ_DECAY = 0.98            # each snap, older calls count a little less (half-life ~35 snaps)
READ_GROUP_W = 1.0           # weight of run vs pass (offense) / blitz vs not (defense)
READ_KIND_W = 0.5            # weight of the exact call (deep pass, screen, man blitz...). Oct 25: at 1.0
                             # spamming one call was counted about twice over (always deep: -11.5 points a game)
READ_UNDERUSED = 0.35        # an under-used call's bonus, as a share of the same over-use penalty
READ_PASS_SEP = 1.6          # receivers' separation per 1.0 of over-use (pass plays). Measured
                             # (tools/playcall_check.py probe, Oct 25): at 1.0, a read of -0.2 on every
                             # pass cost 0.19 net yards a dropback; real ~0.3
READ_RUN_TILT = 0.8          # run tilt per 1.0 of over-use. At 1.4, -0.2 cost 0.57 yards a carry; real ~0.3
READ_SNEAK_LOGIT = 1.0       # sneak success log-odds per 1.0 of over-use
READ_DEF_K = 0.5             # your defense's over-use, in the same units, as an edge for the offense. At 1.0
                             # always zone cost 6.3 points a game, though zone-heavy defenses are a real style
SCHEME_FIT_K = 0.08          # scheme fit: over-use units per 1.0 of fit above the coordinator's own mix

# ---- Game-to-game form, home field, fatigue --------------------------------
# Coordinator style (persistent for a team all season; placeholder for coaches)
STYLE_PASS_SD = 0.26         # logit: run-heavy vs pass-heavy offenses
PASS_BIAS_MAX = 0.50         # limit on a team's pass/run lean (logit). Oct 21 (Blake): 0.36 -> 0.50; at 0.36
                             # a quarter of teams sat at the limit and the most pass-heavy teams threw less than real
STRENGTH_PASS_K = 0.14       # teams with a better passing game than running game throw more
PASS_SCALE = 0.00            # logit: overall run/pass balance (real: about 61% dropbacks)
STYLE_RB_SPLIT_SD = 0.40     # staff style: some ride one back, some split it
RB_ENDURANCE_SPLIT_K = 0.6   # a back with high endurance gets more of the work (bell cow)
RB_GAP_SPLIT_K = 0.2         # ...and so does one clearly better than his backup
RB_SPLIT_MIN = 0.18          # even a bell cow comes off for a series now and then
SHORT_YARDAGE_RB_ROTATION = 0.40  # share of the usual RB rotation kept on short yardage / goal line (goal-line backs)
RB_CARRIES_SOFT = 16         # carries in a game before the staff starts spreading the work...
RB_CARRIES_ENDURANCE = 6     # ...later for a high-endurance back (+6 at 100), sooner for a low one
RB_CARRIES_STEP = 0.03       # backup share added per carry beyond that
                             # (Oct 23: 0.10 -> 0.03. The steep brake flattened every back's day to ~16-22
                             # carries: 25+ carry games 12.5 a season vs real 31.8, 30+ 0.2 vs 6.2, 150-yard
                             # games 11.5 vs 16, 200-yard 1.2 vs 2.2; real 2021-25 weekly stats.
                             # Real backs ride a game script: 20+ carries 111 a season, 25+ 32.)
THIRD_DOWN_BACK_SHARE = 0.85 # passing situations (3rd/4th and 4+, 2nd and long, two-minute drill, down 9+ late) the 3rd-down back plays
THIRD_DOWN_BACK_2ND_TOGO = 8 # 2nd down counts as a passing situation from this many yards to go
                             # (Oct 21, Blake: a depth chart spot, rated mainly on pass blocking and receiving)
# Decided games (Oct 20, Blake): a staff with a big lead late protects its
# lead back and gives the backup the clock-killing carries.
# (from this quarter on, lead of at least, share of RB snaps the backup takes)
RB_BLOWOUT_REST = ((4, 24, 0.85), (4, 17, 0.60), (3, 28, 0.50))
    # workhorse back vs committee
STYLE_ROLE_SD = {"WR": 0.10, "TE": 0.32, "RB": 0.16, "FB": 0.2}  # who the passing game features
Z_CAP_GENERATIONAL = 2.7     # Generational players get a little more headroom at the top (Blake)
Z_CAP = 2.3                  # soft ceiling on how far above/below average a player can play
Z_FLOOR_OUT_OF_POSITION = -6.0  # out of position, no soft floor (a DT at QB is worse than any real QB), just this
UNTRAINED_PASSER_K = 0.30    # completion logit per z a passer's accuracy is below every real QB's (only a non-QB is)
UNTRAINED_K = 1.0            # everywhere else: the part of a matchup that's below every real player's level at
                             # that spot (only a player out of position can be) counts this much, OUTSIDE the
                             # per-play caps (RUSH_EDGE_CAP, TARGET_EDGE_CAP, COMP_CAP, YAC_CAP, RUN_CAP), which
                             # soften real players' extremes. 1.0 = the matchup's normal slope (Oct 24)
UNTRAINED_QB_RUN_K = 0.8     # pass-rate logit per z a non-quarterback at QB passes below every real QB: coaches
                             # run the ball. Real: 2020 Broncos with WR Kendall Hinton at QB, 11 dropbacks and 33
                             # runs (25%). With 0.8 a WR at QB ~16 dropbacks, 45 runs (26%); a DT or G ~13, 45.
                             # Before, the offense still threw ~30 times a game.
FORM_SD = 2.6                # rating points: an average player's game-to-game swing
# A hidden, career-long knack (Blake, Oct 23: "I remember in FOF8 a really highly rated quarterback
# would just suck sometimes ... they just played bad their whole career despite being high rated";
# he chose "QBs mostly"): rating points added to everything a player does, fixed for his career,
# never shown (gameteam.hidden_form). Plus a season form: a good or bad year (rating points, new
# each season). Sized so a QB's passer rating carries over from one season to the next about as
# much as real QBs' (correlation ~0.40, nflverse 2006-24) while ratings explain less of it.
KNACK_SD = {"QB": 3.5}       # by position; everyone else KNACK_SD_OTHER
KNACK_SD_OTHER = 0.0
SEASON_FORM_SD = {"QB": 4.5}  # by position; everyone else SEASON_FORM_SD_OTHER
# Fitted Oct 23 (16-season realism runs, variants A-G): with these and the two QB levers above, passer
# rating leaders #1/#3/#5/#10 113.5/106.4/103.4/98.0 (real 2021-25: 112.7/105.0/102.2/98.4; before
# 117.4/109.5/106.1/99.5), completion #1 71.6% (71.1; before 73.1); a QB's overall vs his passer
# rating correlation 0.47 (before 0.73: ratings decided more); frozen-ratings replays: typical
# season-to-season passer rating change 6.3 (before 6.4; real 8.1, real players also age and move).
SEASON_FORM_SD_OTHER = 0.0
HOME_EDGE = 0.09             # z added to the home team's players (crowd, comfort)
AWAY_FALSE_START = 1.25      # crowd noise: away offense false starts more
FATIGUE_PER_SNAP = {"QB": 0.5, "RB": 2.8, "FB": 3.0, "WR": 2.6, "TE": 3.0, "T": 1.6,
                    "G": 1.6, "C": 1.6, "DE": 5.0, "DT": 5.8, "OLB": 3.4, "ILB": 2.6,
                    "CB": 2.4, "S": 2.0, "K": 0, "P": 0, "LS": 0}
# Planned rotation: share of snaps the backup takes at an even talent level.
# (Oct 20: RB 0.30 -> 0.26 and RB_3 0.04 -> 0.025; backup and third backs had too many carries, real
# 2021-25 per team: RB1 216 / RB2 99 / RB3 35 carries median vs sim 198 / 103 / 38)
# (Oct 23, Blake OK'd: receivers and tight ends rotate like real ones. Share of snaps in the
# games he played, real 2023-25 snap counts vs sim: WR1 0.81 vs 0.92, WR2 0.71 vs 0.83, WR5 0.33
# vs 0.21, TE1 0.71 vs 0.85, TE3 0.28 vs 0.11; scratchpad snapshare_pg.py. Before: WR1 0.05,
# WR2 0.07, TE1 0.08, no _3. The "_3" share goes to the second backup, spreading the snaps.)
ROTATION = {"RB": 0.26, "RB_3": 0.025, "WR1": 0.11, "WR1_3": 0.23, "WR2": 0.10, "WR2_3": 0.20,
            "WR3": 0.22, "TE1": 0.18, "TE1_3": 0.12, "TE2": 0.10,
            "LE": 0.40, "RE": 0.40, "LDT": 0.42, "RDT": 0.42, "WLB": 0.08, "SLB": 0.10, "NB": 0.06,
            "MLB": 0.05, "LE_3": 0.06, "RE_3": 0.06, "LDT_3": 0.10, "RDT_3": 0.10}
HOT_RUSHER_CLEANUP = 0.10    # and per sack he already has, this much more chance the next sack is a clean-up
                             # by someone else (the protection is sliding his way)
HOT_RUSHER_K = 0.60         # per sack (half per QB hit) a rusher has in this game: how much more the offense
                             # treats him as the threat to slide to and chip (plays.protection). Real
                             # 2021-25 per season: 16 games of 3+ sacks by one player, 2 of 4+; before
                             # this the game had 32 and 6.5 (tools/game_extremes_check.py)
ROTATION_GAP_K = 0.20       # bigger talent gap -> fewer snaps for the backup
ROTATION_GAP_K_WR = 0.50     # receivers: a star rotates much less than an ordinary #1 (real elite receivers play
                             # 90%+ of snaps; the average #1 81%). With the flat 0.20 the league's top receiver
                             # lost ~200 yards a season to rotation (1,612 vs real 1,811).
FATIGUE_RECOVERY = 7.0       # per snap spent on the sideline
FATIGUE_SUB_AT = 26.0        # starters rotate out around here (endurance shifts it)
FATIGUE_EFFECT = 0.06        # rating points lost per point of fatigue over the limit

# ---- Pace ---------------------------------------------------------------
STYLE_PACE_SD = 3.0          # seconds: team-to-team spread in offensive tempo (real: about 26-33s per play)
RUNOFF_NORMAL = 33.0         # seconds between plays when the clock keeps running
RUNOFF_HURRY = 12.0
RUNOFF_MILK = 39.0
RUNOFF_AFTER_OOB = 29.0      # clock restarts on the ready signal (outside late-game)

# ---- In-game injuries -------------------------------------------------------
INJURY_RATE = 0.0112         # chance each player in on contact gets hurt. Oct 21: lengths now come from
                             # real data (engine/injuries.py) and the rate is set so a regular season has
                             # the real ~820 injuries that cost games and ~90 player-games lost per team
                             # (2022-25 reports + snap counts; earlier years link fewer players, undercount).
                             # 0.0118 hit ~820 before flare-ups existed; flare-ups of earlier injuries
                             # (injuries.RECOVERY, ~90 a season, about half new report entries) -> 0.0112.
INJURY_SHAKEN_SHARE = 0.45   # share of injuries that cost no games (back in a few snaps)
PLAYING_HURT = 4.0           # rating points off for a player who plays listed Questionable, when the injury
                             # isn't known (the season loop passes the amount by injury: injuries.RECOVERY).
                             # Real overall (play-by-play 2016-25 vs the same player's other games): QBs -4%
                             # yards per dropback, receivers -4.5% per target; 3.3 points matched QBs in the sim.
INJURY_RANDOM_CONTACT = 1.00 # one more player on each side (often a lineman) is in the pile this often
INJURY_CARRIER_MULT = {"RB": 0.35, "other": 0.55}  # per touch for ball carriers and receivers (they touch it often; real backs miss ~2-4 games a year)
DURABILITY_K = 0.35          # injury odds per 15 points of hidden durability (iron man ~half the rate, fragile ~double)
DURABILITY_SEVERITY = 0.05   # durable players more often shake injuries off or miss less time
FATIGUE_INJURY_K = 0.03      # per point of fatigue over his limit: worn-down players get hurt more
INJURY_QB_MULT = 0.65        # rules protect quarterbacks

# ---- Centering (set by calibration) -----------------------------------------
# The league-wide average of each matchup adjustment. Subtracting it means an
# average matchup gives exactly the real NFL baseline; better players move the
# result up, worse players move it down. These need re-measuring (by Claude)
# if player ratings or the knobs above change a lot.
# Measured Oct 19, 2026 over 1,500 games in three different leagues.
# Oct 25: only "scramble" and "qb_run" re-measured (tools/recenter.py) after the scramble and
# designed QB run retune changed which QBs carry the ball; the rest left as they were.
CENTER = {
    "breakaway": 0.011,
    "comp0": 0.061,
    "comp1": 0.05,
    "comp2": 0.046,
    "comp3": -0.063,
    "int0": -0.112,
    "int1": -0.017,
    "int2": 0.045,
    "int3": 0.259,
    "kr": -0.058,
    "pr": -0.041,
    "qb_run": 0.576,
    "run": 0.1,
    "scramble": 0.157,
    "sneak": 0.011,
    "throwaway": -1.195,
    "yac0": 0.043,
    "yac1": 0.046,
    "yac2": 0.051,
    "yac3": 0.017,
}
