# scouting_words.py
# What your scouts say about a prospect, in football language (scouting.py picks the
# lines; Blake, Oct 22: scout's notes, two scouts who can disagree, round projections,
# and the staff's impression in scout slang). Everything here is wording only: which
# line shows is decided from your staff's view of the player, so a line can be wrong
# when your staff is.

# ---- Your staff's impression of him vs his buzz (where the media has him) ------------
# key: (word, color, what it means). Shown once your scouts have watched his film.
IMPRESSIONS = {
    "gem": ("Hidden gem", "#1F6FB2", "Your staff thinks he's much better than players at his spot on the big "
                                     "boards usually turn out: a steal where he's expected to go."),
    "sleeper": ("Sleeper", "#2E8B47", "Your staff thinks he's better than his buzz."),
    "fair": ("Fair value", "#6B6B6B", "Your staff sees him about where the big boards have him."),
    "wild": ("Wild card", "#8A5CB8", "Raw: what he is now and what he could become are far apart, and your "
                                     "staff can't say which way he'll go yet. A top-30 visit is your best look."),
    "hyped": ("Overhyped", "#C9822B", "Your staff thinks he's worse than his buzz."),
    "fools": ("Fool's gold", "#A3321F", "Your staff thinks he's much worse than players at his spot on the big "
                                        "boards usually turn out: a bust waiting to happen where he's expected "
                                        "to go."),
}

# ---- Two scouts before the cross-check ---------------------------------------------------
SCOUTS = ("Area scout", "National scout")

# ---- Film notes: what he does best and worst, per skill ---------------------------------
# Two ways to say each, picked by the prospect's own dice so his report reads the same
# every time you open it.
STRENGTH = {
    "screen_pass": ["Gets the ball out quick on screens and touch throws", "Throws a soft, catchable screen ball"],
    "short_pass": ["Lethal underneath: quick, accurate, on time", "Picks defenses apart in the short game"],
    "medium_pass": ["Drives the ball between the levels with velocity", "Attacks the intermediate middle with confidence"],
    "long_pass": ["Big arm: drives it outside the numbers", "Makes the deep out look easy"],
    "deep_pass": ["Can throw it 60 yards with a flick", "Drops it in the bucket deep"],
    "third_down": ["Clutch on third down: moves the chains", "At his best when the chains are on the line"],
    "accuracy": ["Pinpoint ball placement", "Puts it where only his man can get it"],
    "timing": ["Throws with anticipation, before the break", "Rhythm passer: ball out on time, every time"],
    "sense_rush": ["Feels pressure and slides away from it", "Calm in a collapsing pocket"],
    "read_defense": ["Reads the whole field, doesn't lock on", "Diagnoses coverage before the snap"],
    "two_minute": ["Cool in the two-minute drill", "Runs the hurry-up like a veteran"],
    "scrambling": ["Dangerous when he breaks the pocket", "Extends plays and picks up chunks with his legs"],
    "vision": ["Patient runner with great vision", "Sees the cutback before it opens"],
    "power_run": ["Runs through arm tackles", "Falls forward every time: a short-yardage hammer"],
    "elusiveness": ["Makes the first man miss in a phone booth", "Slippery: tacklers grab air"],
    "breakaway": ["Home-run speed: gone if he gets a crease", "Nobody catches him from behind"],
    "hands": ["Natural hands: plucks it away from his body", "Rarely drops one"],
    "route_running": ["Crisp, sudden route runner", "Sets up defenders and snaps off his breaks"],
    "getting_open": ["Always seems to find the soft spot", "Separates late and often"],
    "traffic": ["Strong hands in traffic: wins the contested catch", "Takes the hit and holds on over the middle"],
    "after_catch": ["Electric with the ball in his hands", "Turns a 5-yard catch into 25"],
    "kick_return": ["Explosive kick returner", "One cut and up the field on kickoffs"],
    "punt_return": ["Fearless, shifty punt returner", "Can flip a game on a punt return"],
    "run_block": ["Mauler in the run game: moves people", "Finishes blocks into the ground"],
    "pass_block": ["Anchors well in pass protection", "Hard to beat in pass pro"],
    "footwork": ["Light, quick feet for his size", "Mirrors speed rushers with clean footwork"],
    "block_aware": ["Smart: picks up stunts and blitzes", "Rarely blocks the wrong man"],
    "snapping": ["Clean, consistent snaps", "Never a bad exchange"],
    "endurance": ["Motor runs all game: no drop-off late", "Can handle a full load of snaps"],
    "run_defense": ["Stout at the point of attack against the run", "Sets the edge with authority"],
    "diagnosis": ["Instinctive: reads plays before they develop", "Quick to diagnose run or pass"],
    "hitting": ["Heavy hitter: ball carriers feel him", "Violent, wrap-up tackler"],
    "rush_tech": ["Polished pass rusher with a plan and counters", "Bends the edge with real technique"],
    "rush_power": ["Bull rush walks tackles back into the QB", "Power rusher who collapses the pocket"],
    "shed": ["Sheds blocks quickly with violent hands", "Gets off blocks and makes the play"],
    "pursuit": ["Sideline-to-sideline range", "Chases plays down from the backside"],
    "man_cover": ["Sticky in man coverage", "Can shadow a top receiver"],
    "zone_cover": ["Smart zone defender who reads the QB", "Always in the right spot in zone"],
    "bump_run": ["Physical at the line: jams receivers off their routes", "Wins early in press coverage"],
    "ball_skills": ["Ball hawk: high-points it like a receiver", "Turns pass breakups into interceptions"],
    "kick_power": ["Big leg: range past 55 yards", "Kicks it a mile"],
    "kick_accuracy": ["Automatic from inside 45", "Accurate, repeatable stroke"],
    "kickoff": ["Booms kickoffs deep", "Puts kickoffs where he wants them"],
    "punt_power": ["Big leg: flips the field", "Booms it 50-plus regularly"],
    "hang_time": ["Great hang time: coverage gets there", "Punts hang forever"],
    "directional": ["Pins returners against the sideline", "Drops it inside the 10 on command"],
    "long_snap": ["Laser-accurate long snaps", "Snaps right on the holder's hands every time"],
    "snap_speed": ["Fast, tight spiral on long snaps", "Gets the ball back in a hurry"],
    "coverage": ["Covers kicks like a linebacker", "Gets downfield and makes tackles on punts"],
}
WEAKNESS = {
    "screen_pass": ["Floats screens and touch throws", "Struggles to take speed off the ball"],
    "short_pass": ["Erratic in the short game", "Misses easy throws underneath"],
    "medium_pass": ["Lacks zip in the intermediate range", "Hesitant over the middle"],
    "long_pass": ["Arm strength is a question on outside throws", "Outs and comebacks die in the air"],
    "deep_pass": ["Can't consistently push it deep", "Deep ball floats and gets undercut"],
    "third_down": ["Shrinks on third down", "Inconsistent when the chains are on the line"],
    "accuracy": ["Scattershot ball placement", "Accuracy comes and goes"],
    "timing": ["Waits for receivers to come open", "Late with the ball: throws people into hits"],
    "sense_rush": ["Doesn't feel pressure: takes too many sacks", "Drifts into the rush"],
    "read_defense": ["Locks onto his first read", "Gets fooled by disguised coverages"],
    "two_minute": ["Rushed and sloppy in the two-minute drill", "Struggles to run the hurry-up"],
    "scrambling": ["Statue in the pocket", "Not a threat with his legs"],
    "vision": ["Runs into his own blockers", "Misses the cutback lanes"],
    "power_run": ["Goes down on first contact", "Not a short-yardage back"],
    "elusiveness": ["Stiff hips: tacklers square him up", "Rarely makes anyone miss"],
    "breakaway": ["Gets caught from behind", "Lacks a second gear"],
    "hands": ["Body catcher with concentration drops", "Hands are a question"],
    "route_running": ["Rounds off his routes", "Limited route tree"],
    "getting_open": ["Has trouble separating", "Lives in tight windows"],
    "traffic": ["Shies away from contact over the middle", "Loses too many 50-50 balls"],
    "after_catch": ["Goes down right after the catch", "Not much after the catch"],
    "kick_return": ["Indecisive on kick returns", "Not a return option"],
    "punt_return": ["Shaky fielding punts", "Not a punt returner"],
    "run_block": ["Doesn't move people in the run game", "Gets stalemated at the point of attack"],
    "pass_block": ["Gets walked back in pass protection", "Liability in pass pro"],
    "footwork": ["Heavy feet: speed rushers get around him", "Sloppy footwork, gets overextended"],
    "block_aware": ["Loses track of stunts and blitzes", "Blocks the wrong man too often"],
    "snapping": ["Inconsistent snaps", "Shotgun snaps wander"],
    "endurance": ["Fades late in games", "Needs to come off the field a lot"],
    "run_defense": ["Gets pushed around against the run", "Washed out at the point of attack"],
    "diagnosis": ["Slow to read plays: bites on play action", "Late to diagnose"],
    "hitting": ["Grabby, arm tackler", "Doesn't bring much pop"],
    "rush_tech": ["No plan as a pass rusher", "One move: no counters"],
    "rush_power": ["Can't collapse the pocket with power", "Gets stoned on the bull rush"],
    "shed": ["Gets stuck on blocks", "Struggles to disengage"],
    "pursuit": ["Limited range", "Doesn't chase from the backside"],
    "man_cover": ["Struggles to stay with receivers in man", "Gets lost in man coverage"],
    "zone_cover": ["Busts in zone: loses his landmarks", "Eyes in the backfield, man behind him"],
    "bump_run": ["Gets beat off the line in press", "Doesn't jam: receivers release clean"],
    "ball_skills": ["Hands of stone: drops the interceptions", "Doesn't find the ball in the air"],
    "kick_power": ["Limited range", "Short leg: 50-plus is a stretch"],
    "kick_accuracy": ["Spray kicker: misses short ones", "Inconsistent stroke"],
    "kickoff": ["Kickoffs land short", "Gives up returnable kickoffs"],
    "punt_power": ["Short leg on punts", "Shanks too many"],
    "hang_time": ["Line-drive punts: outkicks his coverage", "Low hang time"],
    "directional": ["Can't place punts", "Kicks it into the end zone too often"],
    "long_snap": ["Erratic long snaps", "Snaps sail on him"],
    "snap_speed": ["Slow snaps", "Takes too long to get the ball back"],
    "coverage": ["Liability covering kicks", "Doesn't get downfield"],
}

# Blocking said the way scouts say it about receivers, tight ends and backs.
BY_POSITION = {
    ("strength", "run_block", "WR"): ["Willing, physical blocker on the perimeter", "Sustains blocks downfield"],
    ("strength", "run_block", "RB"): ["Lead-blocks with a purpose", "Doesn't shy from contact as a blocker"],
    ("strength", "pass_block", "RB"): ["Stands up blitzers in pass protection", "Trusted on third down: picks up the blitz"],
    ("weakness", "pass_block", "RB"): ["Whiffs on blitz pickups", "Can't be trusted to pick up the blitz"],
    ("weakness", "run_block", "WR"): ["Doesn't want to block", "Gets pushed around blocking on the edge"],
    ("strength", "pass_block", "TE"): ["Can stay in and help in pass pro", "Holds up against edge rushers"],
    ("strength", "run_block", "TE"): ["Moves people as an in-line blocker", "Seals the edge in the run game"],
}


def phrases(table, skill, position):
    """The lines for a skill (STRENGTH or WEAKNESS), worded for his position where it matters."""
    kind = "strength" if table is STRENGTH else "weakness"
    group = {"FB": "RB", "TE": "TE", "WR": "WR", "RB": "RB"}.get(position)
    return BY_POSITION.get((kind, skill, group)) or table[skill]


# ---- Tape vs stopwatch -------------------------------------------------------------------
PLAYS_FASTER = ["Plays faster than he timed", "Faster on tape than on the stopwatch"]
TIMED_FASTER = ["Timed fast, plays slower", "Workout warrior: the speed doesn't show on tape"]

# ---- The person (from the interview) -----------------------------------------------------
PERSON = {
    ("leadership", "high"): ["Natural leader: teammates follow him", "Commands the room"],
    ("leadership", "low"): ["Quiet: not a vocal leader", "Leads by example, if at all"],
    ("volatility", "high"): ["Emotional: needs the right locker room", "Runs hot and cold"],
    ("volatility", "low"): ["Even-keeled: nothing rattles him", "Same guy every day"],
    ("wants_winner", "high"): ["Hates losing", "Ultra-competitive"],
    ("wants_winner", "low"): ["Laid back about winning and losing", "Competitive fire is a question"],
    ("loyalty", "high"): ["Loyal: wants to stay in one place", "All about his team"],
    ("loyalty", "low"): ["Will chase the money", "About his own future first"],
}
CHARACTER = "Off-field concerns came up in his background check"
CLEAN = "Background check came back clean"

# ---- Wild card ---------------------------------------------------------------------------
WILD = ["Flashes of everything, consistency of nothing", "Our scouts are split on what he'll become",
        "Raw: the tape shows a different player every week"]
