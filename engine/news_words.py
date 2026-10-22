# news_words.py
# The words the News tab writes with (engine/news.py decides WHAT to say; this
# file holds the many ways to SAY it), and the Writer that puts sentences
# together.
#
# How it works, in plain terms:
#   - BANK maps a name ("lead_star", "fan_win"...) to a list of ways to say
#     it. {name} is a fact filled in by news.py (a team, a score, a stat
#     line). #name# drops in a pick from another list, so sentences are built
#     from interchangeable pieces.
#   - An entry can be a plain string, or (string, "needs"): it's only used
#     when those facts are true ("bigstar", "!tie"...), and when it fits it's
#     favored over the plain ones, so the unusual angle wins when it exists.
#   - The Writer remembers, across the whole season, which ways it used
#     lately for each name, and doesn't reuse them until most of the others
#     have had a turn. That's what keeps a season of game stories from
#     sounding the same.
#   - Every fact comes from the game's records. Lines here never add a fact
#     of their own (no "his career high" unless news.py checked it).
#
# Adding wording: add strings to a list. Use only the {facts} the list's
# other entries use. tools/news_check.py flags unfilled {gaps}.

import re
from collections import defaultdict

_TOKEN = re.compile(r"#(\w+)#")


class Writer:
    def __init__(self, bank=None):
        self.bank = bank or BANK
        self.recent = defaultdict(list)
        self.errors = []

    @staticmethod
    def _ok(opt, facts):
        if isinstance(opt, str):
            return True
        for need in opt[1].split():
            neg = need.startswith("!")
            if bool(facts.get(need.lstrip("!"))) == neg:
                return False
        return True

    def pick(self, name, rng, facts, favor=3):
        """One way to say `name` that fits the facts and hasn't been used lately."""
        opts = self.bank[name]
        ok = [i for i, o in enumerate(opts) if self._ok(o, facts)]
        if not ok:
            return None
        recent = self.recent[name]
        window = (len(ok) * 2) // 3
        blocked = set(recent[-window:]) if window else set()
        fresh = [i for i in ok if i not in blocked] or ok
        weights = [1 if isinstance(opts[i], str) else favor for i in fresh]
        i = rng.choices(fresh, weights)[0]
        recent.append(i)
        del recent[:-80]
        o = opts[i]
        return o if isinstance(o, str) else o[0]

    def expand(self, text, rng, facts):
        for _ in range(6):
            new = _TOKEN.sub(lambda m: self.pick(m.group(1), rng, facts) or "", text)
            if new == text:
                break
            text = new
        return text

    def fill(self, text, rng, facts):
        try:
            out = self.expand(text, rng, facts).format(**facts)
        except (KeyError, IndexError, ValueError) as e:
            self.errors.append(f"{e!r} in {text!r}")
            return ""
        out = re.sub(r"\s+([,.;:])", r"\1", re.sub(r"  +", " ", out)).strip()
        # A sentence that starts with a spelled-out number ("five sacks") gets its capital.
        out = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
        return out[:1].upper() + out[1:]

    def say(self, name, rng, facts, favor=3):
        """A finished sentence (or headline) for `name`, or '' if nothing fits."""
        t = self.pick(name, rng, facts, favor)
        return self.fill(t, rng, facts) if t is not None else ""


# ---------------------------------------------------------------------------
# The bank. Facts used in game stories (news.py, _game_facts):
#   W L: full team names; Wc Lc: cities; Wn Ln: nicknames; Wc_poss Lc_poss
#   score "27-24"; when " in Week 7"; where " at home" / " on the road" / "";
#   ot " in overtime"; ot_s " in OT"; v_s v_p v_past: the verb (present after a
#   city, present after a plural, past)
#   star star_last star_poss star_h (headline name) star_does ("threw for 312
#   yards...") star_got ("312 passing yards and three touchdowns");
#   lstar lstar_last lstar_poss lstar_h lstar_does lstar_got (the loser's best)
#   wrec lrec (records after), wrec_b lrec_b (before), n_w n_l (streak words)
# ---------------------------------------------------------------------------

BANK = {
    # ---- Game headlines (regular season) ------------------------------------
    "head": [
        "{Wc} {v_s} {Lc} {score}{ot_s}",
        "{Wc} {v_s} {Lc}, {score}{ot_s}",
        "{Wc} {v_s} {Lc} {score}{ot_s}{where_h}",
        ("{star_h}, {Wn} {v_p} {Ln} {score}{ot_s}", "bigstar"),
        ("{star_h} leads {Wc} past {Lc}, {score}", "bigstar plainwin"),
        ("{star_h} carries {Wc} past {Lc}", "bigstar plainwin"),
        ("{Wc} rides {star_h} past {Lc}, {score}", "bigstar plainwin"),
        ("{star_h} powers {Wc} to {score} win over {Lc}", "bigstar plainwin"),
        ("{Wc} improves to {wrec} with {score} win over {Lc}", "midseason"),
        ("{Wc} moves to {wrec}, {v_s} {Lc}", "midseason"),
        ("{Wc} {v_s} {Lc} for {w_ord} straight win", "wstreak"),
        ("{Wc} makes it {n_w} straight, {score} over {Lc}", "wstreak"),
        ("{Wc} keeps rolling: {n_w} straight after {score} win", "wstreak"),
        ("{Lc} drops {l_ord} straight, {score} to {Wc}", "lstreak"),
        ("{Lc} skid reaches {n_l} with {score} loss to {Wc}", "lstreak"),
        ("{Wc} earns first win of season, {score} over {Lc}", "first_win"),
        ("Finally: {Wc} gets first win, {v_s} {Lc}", "first_win"),
        ("{Wc} snaps {snap_w}-game skid with {score} win over {Lc}", "snap_w"),
        ("{Wc} ends losing streak at {snap_w}, {v_s} {Lc}", "snap_w"),
        ("{Wc} ends {Lc_poss} winning streak at {snap_l}", "snap_l"),
        ("{Lc_poss} {snap_l}-game win streak ends in {score} loss to {Wc}", "snap_l"),
        ("{Wc} stays unbeaten with {score} win over {Lc}", "unbeaten"),
        ("{Wc} improves to {wrec}, still perfect", "unbeaten"),
        ("{Wc} takes over first place in the {wdiv}", "took_first"),
        ("{Wc} {v_s} {Lc}, grabs {wdiv} lead", "took_first"),
        ("{Wc} avenges earlier loss, {v_s} {Lc} {score}", "avenge"),
        ("{Wc} gets even with {Lc}, {score}", "avenge"),
        ("{Wc} sweeps season series with {Lc}", "sweep"),
        ("{star_h} stays hot as {Wc} {v_s} {Lc}", "star_streak"),
        ("Another big day for {star_h} in {Wc} win", "star_streak"),
        ("{Lc} still winless after {score} loss to {Wc}", "winless"),
        ("Shootout goes to {Wc}, {score} over {Lc}", "shootout"),
        ("{Wc} outlasts {Lc} in {score} shootout", "shootout"),
        ("Defense rules as {Wc} {v_s} {Lc} {score}", "lowscore"),
        ("{Wc} grinds out {score} win over {Lc}", "lowscore"),
        ("{Wc} survives {lstar_h} and {Lc}, {score}", "lstar_big"),
        ("{lstar_h} not enough as {Lc} falls to {Wc}", "lstar_big"),
        ("{Wc} wins in {wx} conditions, {score} over {Lc}", "weather_h"),
        ("{Wc} spoils {cp_h} return, {v_s} {Lc}", "cp_lost"),
        ("{cp_h} returns, {Wc} {v_s} {Lc}", "cp_won"),
    ],
    "head_tie": [
        "{Wc} and {Lc} play to {score} tie",
        "No winner: {Wc}, {Lc} tie {score}",
        "{Wc}, {Lc} settle for {score} tie",
    ],
    "head_preseason": [
        "Preseason: {Wc} {v_s} {Lc} {score}",
        "Preseason: {Wc} {v_s} {Lc}, {score}",
        ("Preseason: {star_h} shines as {Wc} {v_s} {Lc}", "bigstar"),
    ],
    "head_hof": [
        "Hall of Fame Game: {Wc} {v_s} {Lc} {score}",
        "{Wc} wins the Hall of Fame Game, {score} over {Lc}",
    ],
    "head_wildcard": [
        "{Wc} {v_s} {Lc} {score}{ot_s}, advances to divisional round",
        "{Wc} moves on with {score} win over {Lc}{ot_s}",
        "{Lc_poss} season ends in {score} loss to {Wc}",
        ("{star_h} leads {Wc} past {Lc} in Wild Card round", "bigstar"),
    ],
    "head_divisional": [
        "{Wc} {v_s} {Lc} {score}{ot_s}, reaches conference championship",
        "{Wc} one win from {champ} after {score} win over {Lc}",
        "{Lc_poss} season ends in divisional round, {score} to {Wc}",
        ("{star_h} sends {Wc} to the conference championship", "bigstar"),
    ],
    "head_conference": [
        "{Wc} {v_s} {Lc} {score}{ot_s}, heads to {champ}",
        "{Wc} wins {wconf} Conference title, {score} over {Lc}",
        "{Wc} is going to {champ} after {score} win over {Lc}",
        ("{star_h} and {Wc} punch ticket to {champ}", "bigstar"),
    ],
    "head_final": [
        "{Wc} wins {champ}",
        "Champions: {Wc} {v_s} {Lc} {score} in {champ}",
        "{Wc} {v_s} {Lc} {score}{ot_s} to win {champ}",
        ("{star_h} leads {Wc} to {champ} title", "bigstar"),
        ("{Wc} wins its first title, {score} over {Lc} in {champ}", "first_title"),
    ],

    # ---- Leads --------------------------------------------------------------
    "lead_star": [
        "{star} {star_does}{when}, leading the {W} past the {L} {score}{ot}.",
        "It was {star_poss} day{when}: he {star_does} in a {score} win over the {L}{ot}.",
        "The {L} had no answer for {star}, who {star_does} in a {score} {Wc} win{ot}{when}.",
        "{star} led the way with {star_got} as the {W} {v_past} the {L} {score}{ot}{where}{when}.",
        "{star} {star_does} as the {W} {v_past} the {L} {score}{ot}{where}{when}.",
        "{star} {star_does}, and the {W} {v_past} the {L} {score}{ot}{when}.",
        "Behind {star_poss} {star_got}, the {W} {v_past} the {L} {score}{ot}{where}{when}.",
        "The {W} rode {star_poss} {star_got} to a {score} win over the {L}{ot}{when}.",
        "{star} had {star_got}{when}, and the {W} {v_past} the {L} {score}{ot}{where}.",
        "The {W} got {star_got} from {star} and {v_past} the {L} {score}{ot}{when}.",
        "{star_poss} {star_got} carried the {W} past the {L} {score}{ot}{when}.",
        "On a day when {star} {star_does}, the {W} {v_past} the {L} {score}{ot}{when}.",
    ],
    "lead_plain": [
       "Final{when}: {W} {ws}, {L} {ls}{ot}.",
        "The {W} handed the {L} a {score} loss{ot}{where}{when}.",
        "The {W} {v_past} the {L} {score}{ot}{where}{when}.",
        "{Wc} {v_past} {Lc} {score}{ot}{where}{when}.",
        "The {Wn} {v_past} the {Ln} {score}{ot}{when}{where}.",
        "It finished {score}{ot}{when}: the {W} over the {L}.",
        "The {W} came away with a {score} win over the {L}{ot}{where}{when}.",
    ],
    "lead_comeback": [
        "Down by {max_def}, the {W} came back to beat the {L} {score}{ot}{when}.",
        "The {W} erased a {max_def}-point deficit and beat the {L} {score}{ot}{when}.",
        "{Wc} trailed {Lc} by {max_def} points and won anyway, {score}{ot}{when}.",
        "The {W} dug out of a {max_def}-point hole to beat the {L} {score}{ot}{where}{when}.",
    ],
    "lead_shutout": [
        "The {W} shut out the {L} {score}{where}{when}.",
        "{Lc} never scored: the {W} won {score}{where}{when}.",
        "The {W} blanked the {L} {score}{when}.",
    ],
    "lead_blowout": [
        "The {W} ran away from the {L}, {score}{where}{when}.",
        "It was never close: the {W} beat the {L} {score}{when}.",
        "The {W} routed the {L} {score}{where}{when}.",
        "The {W} rolled over the {L} {score}{when}.",
    ],
    "lead_upset": [
        "The {W} ({wrec_b}) stunned the {L} ({lrec_b}) {score}{ot}{where}{when}.",
        "{Wc} came in at {wrec_b} and {Lc} at {lrec_b}. {Wc} won anyway, {score}{ot}{when}.",
        "The {W} knocked off the {L} {score}{ot}{when}, beating a team that came in {lrec_b}.",
    ],
    "lead_defense": [
        "{star} {star_does}, and the {W} defense carried a {score} win over the {L}{when}.",
        "The {W} won with defense, beating the {L} {score}{when}. {star} {star_does}.",
        "{star} {star_does} as the {W} held off the {L} {score}{when}.",
    ],
    "lead_tie": [
        "The {W} and the {L} played to a {score} tie{when}.",
        "Neither team could win it{when}: the {W} and the {L} tied {score}.",
    ],

    # ---- The winner's star, when the lead didn't name him ------------------
    "star_extra": [
        "{star} carried the load. He {star_does}.",
        "The {Ln} couldn't contain {star}, who {star_does}.",
        "{star} {star_does}, the best line of the day for the {Wn}.",
        "Much of it ran through {star}: he {star_does}.",
        "{star} {star_does}.",
        "{star} led the way. He {star_does}.",
        "{star} did the damage: he {star_does}.",
        "{star} {star_does} for the {Wn}.",
        "The {Wn} leaned on {star}, who {star_does}.",
        "{star} was the difference. He {star_does}.",
        "No one was better than {star}, who {star_does}.",
        "{star_poss} {star_got} set the tone.",
    ],

    # ---- How it was won -------------------------------------------------------
    "how_late": [
        "{goahead} with {clock} left put the {Wn} ahead for good.",
        "{goahead}, with {clock} to play, proved to be the winner.",
        "{Wc} went ahead for good on {goahead} with {clock} left.",
        "The deciding score was {goahead} with {clock} remaining.",
    ],
    "how_late_plain": [
        "The {Wn} took the lead for good with {clock} left in the fourth quarter.",
        "{Wc} went ahead to stay with {clock} remaining.",
    ],
    "how_ot": [
        "{goahead} won it in overtime.",
        "{goahead} ended it in overtime.",
        "Overtime ended on {goahead}.",
    ],
    "how_ot_plain": [
        "The winning points came in overtime.",
        "{Wc} won it in the extra period.",
    ],
    "how_comeback": [
        "The {Wn} trailed by {max_def} points before coming back.",
        "{Wc} erased a {max_def}-point deficit.",
        "{Wc} was down {max_def} at one point and still won.",
    ],
    "how_half_lead": [
        "{Wc} took a {hw}-{hl} lead into halftime.",
        "By halftime it was {hw}-{hl} {Wc}.",
       "{Wc} built a {hw}-{hl} halftime lead.",
        "It was {hw}-{hl} at the break.",
        "{Wc} was up {hw}-{hl} by halftime.",
        "The game was all but decided by the half, with {Wc} up {hw}-{hl}.",
    ],
    "how_half_trail": [
        "{Lc} took a {hl}-{hw} lead into the locker room before {Wc} rallied.",
        "Down {hl}-{hw} at halftime, {Wc} came back.",
        "{Lc} led {hl}-{hw} at halftime before {Wc} took over.",
        "{Wc} trailed {hl}-{hw} at the half.",
        "The {Wn} turned a {hl}-{hw} halftime deficit into a win.",
        "{Wc} was behind {hl}-{hw} at the break and came back.",
    ],
    "how_shutout": [
        "The {Wn} defense held {Lc} scoreless.",
        "{Lc} never got on the board.",
        "{Lc} didn't score a point.",
    ],
    # ---- Team-stat angles (from the box score) ---------------------------------
    "angle_yards": [
        "{Wc} outgained {Lc} {yw}-{yl}.",
        "The {Wn} piled up {yw} total yards to {Lc_poss} {yl}.",
        "{Wc} had {yw} yards of offense; {Lc} managed {yl}.",
    ],
    "angle_yards_lost": [
        "{Lc} outgained {Wc} {yl}-{yw} and lost anyway.",
        "{Lc} had more yards, {yl} to {yw}, but not more points.",
    ],
    "angle_turnovers": [
        "{Wc} won the turnover battle {tw}-{tl}.",
        ("The {Wn} forced {takeaways_w} and gave the ball away {giveaways_w_t}.", "gw"),
        ("The {Wn} forced {takeaways_w} without giving the ball away.", "!gw"),
        "{Lc} turned it over {giveaways_l_t} in the loss.",
        "Turnovers told the story: {Lc} {gl_n}, {Wc} {gw_n}.",
    ],
    "angle_rush": [
        "{Wc} ran for {rw} yards as a team.",
        "The {Wn} pounded out {rw} yards on the ground.",
        "{Wc} had {rw} rushing yards.",
    ],
    "angle_sacks": [
        "The {Wn} sacked {lqb} {sacks_w_t}.",
        "{Wc} got to {lqb} {sacks_w_t}.",
        "{lqb} was sacked {sacks_w_t}.",
    ],
    "angle_penalties": [
        "{Lc} hurt itself with {pen_l} penalties for {peny_l} yards.",
        "{Lc} was flagged {pen_l} times for {peny_l} yards.",
    ],
    # ---- The loser's best player ---------------------------------------------
    "loser_line": [
        "{Lc} leaned on {lstar}, who {lstar_does}.",
        "{lstar} {lstar_does} for the {Ln} in a losing effort.",
        "On the other side, {lstar} {lstar_does}.",
        "{lstar} {lstar_does} for the {Ln}.",
        "For the {Ln}, {lstar} {lstar_does}.",
        "{lstar} {lstar_does} in the loss.",
        "{lstar_poss} {lstar_got} wasn't enough for {Lc}.",
        "{lstar} {lstar_does}, but it wasn't enough.",
        "{Lc} got {lstar_got} from {lstar} in defeat.",
    ],
    "tie_star": [
        "{lstar} {lstar_does} for the {Ln}.",
        "{star} {star_does} for the {Wn}.",
    ],
    # ---- Storylines inside a game story ----------------------------------------
    "star_streak": [
        "It was {star_last_poss} {streak_ord} straight {streak_what}.",
        "That makes {streak_n} straight {streak_whats} for {star_last}.",
        "{star_last} has now had {streak_n} {streak_whats} in a row.",
        "{star_last} keeps rolling: that's {streak_n} straight {streak_whats}.",
    ],
    "since_injury": [
        "{inj_team} is {since_rec} since losing {inj_player} to {inj_what} in Week {inj_week}.",
        "Since {inj_player} went down in Week {inj_week}, {inj_team} has gone {since_rec}.",
        "{inj_team} has gone {since_rec} without {inj_player}, lost to {inj_what} in Week {inj_week}.",
    ],
    "comeback_player": [
        "In his first game back from {cp_what}, {cp} {cp_does}.",
        "{cp}, back from {cp_what}, {cp_does}.",
        "{cp} returned from {cp_what} and {cp_does}.",
        "Back from {cp_what}, {cp} {cp_does}.",
    ],
    "comeback_player_plain": [
        "{cp} returned from {cp_what}.",
        "{cp} was back in the lineup after {cp_what}.",
        "{cp} played for the first time since {cp_what}.",
    ],
    "series_avenge": [
        "{Wc} avenged a {prev_score} loss to {Lc} in Week {prev_week}.",
        "It was payback for {Lc_poss} {prev_score} win in Week {prev_week}.",
        "{Lc} had won the first meeting, {prev_score} in Week {prev_week}.",
    ],
    "series_sweep": [
        "{Wc} swept the season series, after a {prev_score} win in Week {prev_week}.",
        "{Wc} beat {Lc} for the second time this season; the first was {prev_score} in Week {prev_week}.",
        "That's two wins over {Lc} this season for {Wc}.",
    ],
    "rec_plain": [
        "{Wc} is now {wrec}. {Lc} is {lrec}.",
        "{Wc} sits at {wrec} after the win; {Lc} is {lrec}.",
        "Records: {Wc} {wrec}, {Lc} {lrec}.",
        "The {Wn} improved to {wrec}; the {Ln} fell to {lrec}.",
        "{Wc} is {wrec}, {Lc} {lrec}.",
        "The win put {Wc} at {wrec}. {Lc} dropped to {lrec}.",
        "{Wc} moved to {wrec}, while {Lc} slipped to {lrec}.",
        "With the loss, {Lc} fell to {lrec}; {Wc} is {wrec}.",
        "{Lc} is now {lrec} after the loss. {Wc} is {wrec}.",
        ("{Wc} ({wrec}) has won {w_last4} of its last four.", "w_last4"),
    ],
    "rec_wstreak": [
        "{Wc} ({wrec}) has won {n_w} straight.",
        "That's {n_w} wins in a row for {Wc}, now {wrec}.",
        "{Wc} has won {n_w} straight and sits at {wrec}.",
        "The win streak is at {n_w} for {Wc} ({wrec}).",
    ],
    "rec_lstreak": [
        "{Lc} ({lrec}) has lost {n_l} in a row.",
        "The skid is at {n_l} for {Lc}, now {lrec}.",
        "{Lc} has dropped {n_l} straight and is {lrec}.",
        "Losers of {n_l} straight, {Lc} is {lrec}.",
    ],
    "rec_snap_w": [
        "The win snapped a {snap_w}-game losing streak for {Wc}, now {wrec}.",
        "{Wc} ({wrec}) ended a {snap_w}-game skid.",
        "It was {Wc_poss} first win since {last_win}.",
    ],
    "rec_snap_l": [
        "The loss ended {Lc_poss} {snap_l}-game winning streak.",
        "{Lc} ({lrec}) had won {snap_l} straight.",
        "{Lc_poss} streak ended at {snap_l}.",
    ],
    "rec_first_win": [
        "It was {Wc_poss} first win of the season. {Wc} is {wrec}.",
        "{Wc} is in the win column at last, at {wrec}.",
        "{Wc} ({wrec}) has its first win.",
    ],
    "rec_winless": [
        "{Lc} is still looking for its first win, at {lrec}.",
        "{Lc} fell to {lrec}, still winless.",
    ],
    "rec_unbeaten": [
        ("{Wc} is the league's last unbeaten team, at {wrec}.", "last_unbeaten"),
        ("{Wc} is still unbeaten at {wrec}.", "!last_unbeaten"),
        ("{Wc} improved to {wrec}, one of {unbeaten_n} unbeaten teams left.", "!last_unbeaten"),
    ],
    "div_took_first": [
        "The win moved {Wc} into first place in the {wdiv} Division.",
        "{Wc} now leads the {wdiv} Division.",
        "{Wc} took over first place in the {wdiv}.",
    ],
    "div_alone": [
        "{Wc} leads the {wdiv} Division by {gb}.",
        "{Wc} has a {gb_adj} lead in the {wdiv}.",
    ],
    "div_tied": [
        "{Wc} and {div_mate} share first place in the {wdiv}.",
        "{Wc} is tied with {div_mate} atop the {wdiv}.",
    ],
    "div_behind": [
        "{Wc} is {gb} behind {div_leader} in the {wdiv}.",
        "{Wc} sits {gb} back of {div_leader} in the {wdiv}.",
    ],
    "weather": [
        ("The game was played in the rain.", "rain"),
        ("Rain fell in {wx_city}.", "rain"),
        ("It was a wet one in {wx_city}.", "rain"),
        ("Snow fell in {wx_city}.", "snow"),
        ("The game was played in the snow.", "snow"),
        ("Winds of {wind} mph swirled through the stadium.", "windy"),
        ("The game was played in {wind} mph winds.", "windy"),
        ("It was {temp} degrees at kickoff.", "frigid"),
    ],

    # ---- Big performances -----------------------------------------------------------
    "perf_lead": [
        "{Tc} {pos_word} {name} {does} in {result}{when}.",
        "{name} {does} in {Tc_poss} {result_short}{when}.",
        "{name} of the {T} {does} in {result}{when}.",
        "{Tc} got {got} from {pos_word} {name} in {result}{when}.",
    ],
    "perf_best": [
        "No one has had more {stat_words} in a game this season.",
        "That's the most {stat_words} by any player in a game this season.",
        "It's the league's best single-game total this season.",
    ],
    "perf_rank": [
        "He has {season_amount} this season, {rank}.",
        "That gives him {season_amount} on the season, {rank}.",
        "He's up to {season_amount} for the season, {rank}.",
    ],
    "perf_total": [
        "He has {season_amount} this season.",
        "That gives him {season_amount} on the season.",
        "He's up to {season_amount} for the season.",
    ],
    "perf_streak": [
        "It's his {streak_ord} straight {streak_what}.",
        "That's {streak_n} straight {streak_whats}.",
        "He has {streak_n} {streak_whats} in a row.",
    ],

    # ---- Storyline features -----------------------------------------------------
    "streak_head": [
        "{last} stays hot: {streak_n} straight {streak_whats}",
        "{streak_n} straight {streak_whats} for {Tc_poss} {last}",
        "{last} can't be stopped: {streak_ord} straight {streak_what}",
        "Streak watch: {last} keeps it going",
    ],
    "streak_body": [
        "{name} of the {T} has had {streak_n} straight {streak_whats}, the latest {in_game}.",
        "{Tc} {pos_word} {name} put together his {streak_ord} straight {streak_what} {in_game}.",
        "{name} keeps producing. {in_game_cap}, he {does}, his {streak_ord} straight {streak_what}.",
    ],
    "streak_season": [
        "He has {season_amount} through {gp_t} this season.",
        "For the season he has {season_amount} in {gp_t}.",
    ],
    "breakout_head": [
        "Breakout: {last} is turning heads in {Tc}",
        ("Who is {name}? {Tc} is finding out", "late_pick"),
        ("Diamond in the rough: {last} is producing for {Tc}", "late_pick"),
        ("{last} is living up to the hype", "!late_pick"),
        "{last} is for real",
        "{Tc_poss} {last} keeps delivering",
    ],
    "breakout_body": [
        "{name} came into the league as {origin} and is now a weekly factor for the {T}.",
        ("Not many saw this coming from {name}, who came into the league as {origin}.", "late_pick"),
        "{name}, who came into the league as {origin}, has been one of {Tc_poss} best players.",
    ],
    "breakout_recent": [
        "Over his last three games he has {recent_got}.",
        "In his last three games: {recent_got}.",
        "He has {recent_got} over the last three weeks.",
    ],
    "slump_head": [
        "{last} in a slump",
        "Rough stretch for {Tc} QB {last}",
        "{last} searching for answers",
        "What's wrong with {last}?",
    ],
    "slump_body": [
        "{name} has a passer rating of {rating} over his last three games, with {ints_t} and {tds_t}.",
        "Over his last three starts, {Tc} quarterback {name} has completed {pct} percent of his passes with {tds_t} and {ints_t}.",
        "{name} has struggled for three straight weeks: a {rating} passer rating, {tds_t}, {ints_t}.",
    ],
    "slump_team": [
        "{Tc} is {last3_rec} in those games.",
        "The {Tn} went {last3_rec} in that stretch.",
    ],
    "turnaround_head": [
        "From {start_rec} to {rec}: {Tc} has turned it around",
        "{Tc} climbs back after {start_rec} start",
        "{Tc} is back in it",
        "{Tc} has won {n_t} straight after rough start",
    ],
    "turnaround_body": [
        "{Tc} started {start_rec}. It has won {n_t} straight since and is {rec}.",
        "After a {start_rec} start, {Tc} has won {n_t} in a row to get to {rec}.",
        "Remember when {Tc} was {start_rec}? It's {rec} now, after {n_t} straight wins.",
    ],
    "collapse_head": [
        "{Tc} in free fall after {start_rec} start",
        "What happened to {Tc}?",
        "{Tc} has lost {n_t} straight since {start_rec} start",
    ],
    "collapse_body": [
        "{Tc} started {start_rec}. It has lost {n_t} straight since and is {rec}.",
        "{Tc} was {start_rec}. Now it's {rec}, after {n_t} losses in a row.",
        "After a {start_rec} start, {Tc} has dropped {n_t} straight to fall to {rec}.",
    ],
    "fallout_head": [
        "{Tc} is {since_rec} without {inj_last}",
        "Life without {inj_last}: {Tc} {since_rec} since injury",
        ("{Tc} struggling since losing {inj_last}", "bad"),
        ("{Tc} hasn't missed a beat without {inj_last}", "good"),
        ("{Tc} keeps winning without {inj_last}", "good"),
        ("Losing {inj_last} has hit {Tc} hard", "bad"),
    ],
    "fallout_body": [
        "{Tc} lost {pos_word} {inj_player} to {inj_what} in Week {inj_week}. Since then it is {since_rec}.",
        "Since {inj_player} went down with {inj_what} in Week {inj_week}, {Tc} has gone {since_rec}.",
        "{Tc} was {before_rec} when {inj_player} was hurt in Week {inj_week}. It has gone {since_rec} since.",
    ],
    "fallout_scoring": [
        "{Tc} is scoring {ppg_after} points a game without him, down from {ppg_before}.",
        "{Tc} averaged {ppg_before} points a game before the injury and {ppg_after} since.",
    ],
    "fallout_scoring_up": [
        "{Tc} is actually scoring more without him: {ppg_after} points a game, up from {ppg_before}.",
    ],
    "comeback_head": [
        "{last} returns for {Tc}",
        "{last} is back",
        "{Tc_poss} {last} back from {cp_short}",
    ],
    "comeback_body": [
        "{name} played for the first time since {cp_what} kept him out {out_t}. {in_game_cap}, he {does}.",
        "{Tc} got {pos_word} {name} back {in_game} after {out_t} out with {cp_what}. He {does}.",
        "Back after {out_t} out with {cp_what}, {name} {does} {in_game}.",
    ],
    "comeback_body_plain": [
        "{name} returned {in_game} after missing {out_t} with {cp_what}.",
        "{Tc} had {pos_word} {name} back {in_game}. He had missed {out_t} with {cp_what}.",
        "After {out_t} out with {cp_what}, {name} was back on the field {in_game}.",
    ],
    "pace_head": [
        "{last} on pace for {pace_mark} {stat_words}",
        "{pace_mark} {stat_words}? {last} is on pace",
        ("Chasing history: {last} on record pace", "record_pace"),
        ("{last} chasing the league record for {stat_words}", "record_pace"),
    ],
    "pace_body": [
        "{name} of the {T} has {season_amount} through Week {week}, on pace for about {pace_val} over {games} games.",
        "Through Week {week}, {Tc} {pos_word} {name} has {season_amount}. That's a pace of about {pace_val} over {games} games.",
    ],
    "pace_record": [
        "The league record is {rec_val}, set by {rec_holder} in {rec_season}.",
        "The most in a season since the league began is {rec_val} ({rec_holder}, {rec_season}).",
    ],
    "race_head": [
        ("Race for the {div}: {lead_team} and {chase_team} separated by {gap}", "!tied"),
        ("{lead_team} and {chase_team} tied atop the {div}", "tied"),
        ("{chase_team} within {gap} of {lead_team} in the {div}", "!tied"),
        "{div} Division race tightens",
        "Down the stretch in the {div}",
    ],
    "race_body": [
        "{lines} {games_left_t} left.",
    ],
    "pick_head": [
        "Race for the No. 1 pick: {worst_team} at the bottom",
        "Who picks first? {worst_team} leads the race for the top pick",
        "The bottom of the standings after Week {week}",
    ],
    "pick_body": [
        "The worst record picks first in the draft. The bottom of the standings after Week {week}: {lines}.",
        "The teams with the worst records after Week {week}, the front-runners for the top pick: {lines}.",
    ],
    "rank_head": [
        "Power rankings after Week {week}: {top} on top",
        "Week {week} power rankings: {top} holds No. 1",
        "Power rankings: {top} is No. 1 after Week {week}",
        ("Power rankings, Week {week}: {mover} makes the biggest jump", "mover"),
        ("Power rankings: {mover} climbs, {top} stays on top", "mover same_top"),
        ("New No. 1 in our power rankings: {top}", "new_top"),
    ],
    "rank_intro": [
        "Our ranking of all 32 teams, by record, point differential and recent form.",
        "How we rank the league after Week {week}: record, point differential, recent form.",
    ],
    "preview_head": [
        "Week {week} preview: {top_game}",
        "Games to watch in Week {week}",
        "Week {week} preview: the matchups that matter",
        "Circle these Week {week} games",
    ],
    "mvp_head": [
        "MVP watch after Week {week}: {top}",
        "{top} leads our MVP watch",
        "MVP watch: {top} on top after Week {week}",
    ],
    "mvp_intro": [
        "Our picks for the league's most valuable player so far: production, and what it means for a winning team.",
        "Who's having the season? Our MVP watch after Week {week}, weighing numbers and team success.",
    ],
    "rookie_head": [
        "Rookie watch after Week {week}: {top}",
        "{top} leads our rookie watch",
        "The best rookies so far: {top} on top",
    ],
    "rookie_intro": [
        "The first-year players making the biggest impact so far.",
        "Our ranking of this season's rookies after Week {week}.",
    ],

    # ---- Social ----------------------------------------------------------------------
    "fan_win": [
        "LET'S GO {NICK}!!! {rec}", "That's how you do it. {rec}.", "W. On to next week.",
        "{city} football is fun again", "Good win. Don't get comfortable.", "Love this team. {rec}.",
        "Never a doubt. (There were many doubts.)", "Big win. BIG win.", "That's what I'm talking about",
        "We take those. {rec}.", "Feels good to be a {nick} fan today", "Another W. Keep stacking.",
        ("{star} is HIM.", "star"), ("Give {star} whatever he wants", "star"), ("{star} cooked today", "star"),
    ],
    "fan_win_close": [
        "I can breathe again. {score}.", "Ugly win but I'll take it.", "My heart can't take these games",
        "Survive and advance. {rec}.", "Aged 10 years watching that", "A win's a win",
        "Why do we always make it this hard",
    ],
    "fan_win_big": [
        "Somebody check on {opp} fans", "{score}. Not even close.", "Statement game. {rec}.",
        "Put that one on the highlight reel", "That was a beatdown", "Total domination",
    ],
    "fan_loss": [
        "Tough one. We'll get 'em next week.", "That fourth quarter was hard to watch", "Can't win like that",
        "Not good enough. {rec}.", "Who is calling these plays", "This one stings. {score}.",
        "Season's not over. Breathe.", "I'm not even mad, just disappointed. {rec}.", "Same old {nick}",
        "We'll be fine. Probably.", "Bad day. Moving on.", "Tackling was optional today apparently",
    ],
    "fan_loss_big": [
        "Embarrassing. {score}.", "Turned it off at halftime", "Fire everybody",
        "Worst game I've watched in years", "I want my Sunday back", "Not one positive thing to say",
    ],
    "fan_streak_win": ["{n} straight. Don't wake me up.", "This team is rolling. {rec}.",
                       "{n} in a row. Is this real?", "Nobody wants to play us right now"],
    "fan_streak_loss": ["{n} straight losses. I need a break from this team", "Wake me up when it's draft season",
                        "{n} in a row. Rock bottom has a basement", "At least the draft pick is getting better"],
    "fan_tie": ["A tie?? What am I supposed to do with a tie", "Nobody wins. Story of my life.",
                "Kissing your sister. Ugh."],
    "fan_playoff_win": ["ON TO THE NEXT ROUND", "{NICK} PLAYOFF FOOTBALL IS THE BEST FOOTBALL", "Still alive!!",
                        "One step closer", "January football hits different"],
    "fan_playoff_loss": ["What a season though. Proud of this team.", "It hurts. Thanks for the ride, {NICK}.",
                         "Offseason starts now. Ugh.", "So close. Next year."],
    "fan_champ": ["CHAMPIONS!!!!!!", "I've waited my whole life for this. {NICK} WIN IT ALL", "WORLD CHAMPION {NICK}!!!",
                  "Parade. Downtown. Let's go."],
    "fan_preseason": ["Preseason, but I liked what I saw", "Can't read too much into the preseason. Still fun.",
                      "Looking at the backups like they're the future", "Football is back"],
    "fan_rank_up": ["#{rank} in the power rankings. Respect.", "Finally getting some respect. #{rank}.",
                    "Up to #{rank}. Climbing."],
    "fan_rank_down": ["#{rank}?? Disrespect.", "They have us at #{rank}. Fair, honestly.", "Down to #{rank}. Deserved."],
    "fan_rank_top": ["NUMBER ONE. Say it louder.", "#1 in the power rankings. As it should be."],
    "stat_streak": [
        "{name} ({abbr}): {streak_n} straight {streak_whats}.",
        "{name} has {streak_n} consecutive {streak_whats}. {season_amount} on the year.",
    ],
    "insider_fallout": [
        "{Tc} is {since_rec} since losing {inj_player}.",
    ],
    "fan_breakout": ["Where did {last} come from??", "{last} is the steal of the draft", "Put {last} in the lineup forever",
                     "Somebody tell me how {last} was available where we got him", "{last} is the real deal"],
    "fan_mvp": ["{last} for MVP. Not even a debate.", "MVP chants for {last}", "Put {last} at number one and leave it there",
                "Our guy {last} is the best player in this league"],
    "fan_slump": ["Bench {last}. I'm serious.", "What happened to {last}??", "{last} has to be hurt or something",
                  "I've seen enough from {last}"],
    "fan_turnaround": ["Told y'all not to panic", "From {start_rec} to {rec}. Believe.", "We are SO back"],
    "fan_collapse": ["How did we blow a {start_rec} start", "This collapse is historic. Not in a good way.",
                     "From {start_rec} to {rec}. Unreal."],
    "player_streak": ["Stay locked in.", "Just doing my job. Credit to my guys.", "Keep stacking.",
                      "We not done."],
    "player_comeback": ["Felt good to be back out there.", "Thankful. Back where I belong.",
                        "Day by day got me here. Back to work."],
    "player_win": ["Team win. Proud of my guys.", "Blessed. On to the next one.", "We eat together.",
                   "Credit to the big fellas up front.", "God is good. Back to work Monday.", "Locked in."],
    "player_loss": ["Doesn't mean a thing without the W. Back to work.", "Numbers don't matter. We lost.",
                    "On me. We'll be better."],
}
