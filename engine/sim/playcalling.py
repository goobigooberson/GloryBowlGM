# playcalling.py
# Calling your own plays (Watch a game, "Take over play calling"): how the
# other side reads your calls, and how your coordinators' schemes fit them.
#
# Balance (Blake, Oct 25: "making sure its implemented in a balanced way"):
#   - A call you make is the same play an AI coordinator's call of that kind
#     is (coach.call_for_choice / apply_def_choice): no bonus for being yours.
#   - The other side has your coordinator's film: it expects his normal mix
#     for the situation (odds_offense / odds_defense, the same numbers the AI
#     coordinators call from). Call something more often than he would, beyond
#     what chance explains, and they start to expect it: it works worse; what
#     you've been avoiding works a little better (Tendencies). The coordinators'
#     own calls follow their mix, so AI teams are never read this way, and a
#     team is only read once you've made a call that isn't the coordinator's.
#   - Scheme fit: calls that suit your coordinator's style work a little better,
#     the rest a little worse, evened out over his own mix (fit_*).
# Real yardstick and every knob: tuning.py, "Calling your own plays".
# Measured with tools/playcall_check.py (bots calling plays in lab leagues).

import math
from collections import defaultdict

from . import coach
from . import tuning as T

OFF_GROUP = {"run_inside": "run", "run_outside": "run", "sneak": "run", "pass_short": "pass",
             "pass_medium": "pass", "pass_long": "pass", "screen": "pass", "play_action": "pass"}
DEF_GROUP = {"zone": "base", "man": "base", "run_stop": "base", "prevent": "base",
             "zone_blitz": "blitz", "man_blitz": "blitz", "all_out": "blitz"}
_CONCEPT_KEY = {v: k for k, v in coach.PASS_CHOICES.items()}


def situation(state):
    """Down-and-distance bucket the other side keeps a separate book on."""
    d = "1" if state.down == 1 else ("2" if state.down == 2 else "3")
    t = "short" if state.togo <= 3 else ("mid" if state.togo <= 7 else "long")
    return d + t


# ---------------------------------------------------------------------------
# The coordinators' normal mix (their film)
# ---------------------------------------------------------------------------

def odds_offense(state, off_idx, off_team):
    """How often the offensive coordinator calls each menu play here (the same model he calls from)."""
    p = coach.pass_probability(state, off_idx, off_team)
    if coach.must_pass(state, off_idx):
        p = max(p, 0.985)
    out = {}
    for concept, w in coach.pass_concepts(state, coach.tempo_for(state, off_idx)):
        out[_CONCEPT_KEY[concept]] = p * w
    run = 1.0 - p
    sneak_spot = 1.0 if (state.togo <= 1 and state.down >= 3) else (0.25 if (state.togo <= 1 and state.down == 2) else 0.0)
    sneak = sneak_spot * 0.42
    lean = off_team.outside_lean
    qb = coach.sigmoid(coach.logit(T.QB_RUN_SHARE) + T.QB_RUN_MOBILITY_K * (off_team.qb_mobility - 0.3)
                       + (T.QB_GOAL_LINE_RUN if state.yl <= 3 else 0.0))
    sweep = (1 - qb) * T.WR_RUN_SHARE if state.yl > 5 else 0.0
    inside = (1 - sweep) * (.255 + (.38 + .365) * (.36 - lean / 2))
    out["sneak"] = run * sneak
    out["run_inside"] = run * (1 - sneak) * inside
    out["run_outside"] = run * (1 - sneak) * (1 - inside)
    for k in coach.PLAY_MENU:
        out.setdefault(k, 0.0)
    return out


def odds_defense(state, def_idx, def_team, off_call, dcall, off_team, box=None):
    """How often the defensive coordinator makes each menu call here."""
    out = {k: 0.0 for k in coach.DEF_MENU}
    if dcall.prevent:
        out["prevent"] = 1.0
        return out
    loaded = load_box_odds(state, off_team, off_call, dcall, box)
    m = def_team.man_rate
    r = def_team.blitz_rate
    if state.down >= 3 and state.togo >= 4:
        r *= 1.3
    if off_call.tempo == "hurry":
        r *= 0.55
    if state.yl <= 10:
        r *= 0.9
    r = min(1.0, r)
    rest = 1.0 - loaded
    out["run_stop"] = loaded
    out["zone"] = rest * (1 - m) * (1 - r)
    out["man"] = rest * m * (1 - r)
    out["zone_blitz"] = rest * (1 - m) * r
    out["man_blitz"] = rest * m * r * 0.8
    out["all_out"] = rest * m * r * 0.2
    return out


def load_box_odds(state, off_team, off_call, dcall, box=None):
    """coach.load_box's chance, without the dice."""
    if (off_call.kind not in ("run", "pass") or off_call.concept == "hail_mary" or off_call.tempo == "hurry"
            or dcall.package == "Dime" or dcall.lineup.get("SS") is None):
        return 0.0
    if state.down >= 3 and state.togo >= 7:
        return 0.0
    rb = off_call.lineup.get("RB")
    if rb is None:
        return 0.0
    t = off_team.talent_z(rb, "RB")
    if t < T.LOAD_BOX_MIN:
        return 0.0
    hot = box.players.get(rb.id, {}).get("rush_yds", 0) if box is not None else 0
    lean = -getattr(off_team, "pass_bias", 0.0)
    p = T.LOAD_BOX_RATE * math.exp(T.LOAD_BOX_THREAT_K * (t - 1.0) + T.LOAD_BOX_HOT_K * max(0.0, hot - 50)
                                   + T.LOAD_BOX_LEAN_K * lean)
    return min(T.LOAD_BOX_MAX, p)


# ---------------------------------------------------------------------------
# Reading tendencies
# ---------------------------------------------------------------------------

class Tendencies:
    """One side's calls this game, against its coordinator's film. read() is how much the
    call is over-used (+) or under-used (-) beyond chance, in share units."""

    def __init__(self, groups):
        self.groups = groups
        self.dev = defaultdict(float)      # (scope, key): sum of (called - expected)
        self.var = defaultdict(float)      # (scope, key): sum of chance variance
        self.n = defaultdict(float)        # scope: snaps
        self.game = {"dev": defaultdict(float), "var": defaultdict(float), "n": defaultdict(float)}
                                           # this game's calls alone, not faded: what goes on film

    def add_film(self, snap, weight):
        """Start from an earlier game's film (snapshot()), counted at `weight` per snap."""
        for name, book in (("dev", self.dev), ("var", self.var)):
            for k, v in snap.get(name, {}).items():
                scope, key = k.split("|")
                book[(scope, key)] += weight * v
        for scope, v in snap.get("n", {}).items():
            self.n[scope] += weight * v

    def snapshot(self):
        """This game's calls, for the film (JSON-ready)."""
        g = self.game
        return {"dev": {f"{s}|{k}": round(v, 3) for (s, k), v in g["dev"].items()},
                "var": {f"{s}|{k}": round(v, 3) for (s, k), v in g["var"].items()},
                "n": {s: v for s, v in g["n"].items()}}

    def read(self, sit, choice):
        total = self.part(sit, self.groups[choice], T.READ_GROUP_W) + self.part(sit, choice, T.READ_KIND_W)
        return total if total >= 0 else total * T.READ_UNDERUSED

    def part(self, sit, key, w):
        """Over-use of one key (a call, or a group such as "pass"), both books together."""
        total = 0.0
        for scope, n0 in (("game", T.READ_N0_GAME), (sit, T.READ_N0_SITUATION)):
            n = self.n[scope]
            if n <= 0:
                continue
            d = self.dev[(scope, key)]
            beyond = max(0.0, abs(d) - T.READ_CHANCE_Z * math.sqrt(self.var[(scope, key)]) - T.READ_ALLOW)
            total += w * math.copysign(beyond, d) / (n + n0)
        return total

    def record(self, sit, odds, choice):
        for scope in ("game", sit):
            for k in list(self.dev):
                if k[0] == scope:
                    self.dev[k] *= T.READ_DECAY
                    self.var[k] *= T.READ_DECAY
            self.n[scope] = self.n[scope] * T.READ_DECAY + 1.0
            self.game["n"][scope] += 1.0
            group_odds = defaultdict(float)
            for k, q in odds.items():
                group_odds[self.groups[k]] += q
            for k, q in list(odds.items()) + list(group_odds.items()):
                hit = 1.0 if (k == choice or k == self.groups[choice]) else 0.0
                self.dev[(scope, k)] += hit - q
                self.var[(scope, k)] += q * (1 - q)
                self.game["dev"][(scope, k)] += hit - q
                self.game["var"][(scope, k)] += q * (1 - q)


# ---------------------------------------------------------------------------
# Scheme fit
# ---------------------------------------------------------------------------

def _style(game_team):
    from .. import staff
    lg = game_team.league
    st = staff.style(lg, game_team.id) if getattr(lg, "staff", None) else None
    return st or {}


def fit_offense(game_team):
    """How well each menu play suits the offensive coordinator's style (0 = neutral)."""
    s = _style(game_team)
    if not s:
        return {}
    pas, heavy, fb, pace = s.get("pass", 0.0), s.get("heavy", 0.0), s.get("fb", 0.0), s.get("pace", 0.0)
    rb_role = s.get("roles", {}).get("RB", 0.0)
    return {"run_inside": -0.5 * pas + 0.3 * fb + 0.2 * heavy,
            "run_outside": -0.5 * pas + 0.2 * heavy - 0.2 * fb,
            "sneak": 0.0,
            "pass_short": 0.3 * pas - 0.3 * pace,          # pace < 0 = a fast, up-tempo offense
            "pass_medium": 0.5 * pas,
            "pass_long": 0.6 * pas - 0.2 * heavy,
            "screen": 0.2 * pas + 0.5 * rb_role,
            "play_action": 0.5 * heavy + 0.3 * fb - 0.2 * pas}


def fit_defense(game_team):
    """How well each defensive call suits the defensive coordinator's style."""
    s = _style(game_team)
    if not s:
        return {}
    man, blitz = s.get("man", 0.0), s.get("blitz", 0.0)
    return {"zone": -0.5 * man - 0.3 * blitz, "man": 0.5 * man - 0.3 * blitz,
            "zone_blitz": 0.7 * blitz - 0.4 * man, "man_blitz": 0.7 * blitz + 0.4 * man,
            "all_out": 1.0 * blitz + 0.4 * man, "run_stop": 0.0, "prevent": -0.5 * blitz}


def fit_edge(fit, odds, choice):
    """The call's fit above the coordinator's own mix here (his mix comes out 0 on average)."""
    if not fit:
        return 0.0
    total = sum(odds.values()) or 1.0
    mix = sum(q * fit.get(k, 0.0) for k, q in odds.items()) / total
    return T.SCHEME_FIT_K * (fit.get(choice, 0.0) - mix)


# ---------------------------------------------------------------------------
# What the Watch a game page shows while the game waits for your call
# ---------------------------------------------------------------------------

KEYING_FROM = 0.06      # over-use at which your coordinator warns you the other side is onto it
FITS_FROM = 0.4         # scheme fit (style units above his mix) worth a "fits his scheme" mark
FG_LONGEST = 70         # field goal tries offered on the menu up to this distance (the NFL record is 66)


def _keying(tend, sit, group_words, options):
    """What the other side is onto, in words: a whole group ("the pass") and the calls beyond it."""
    out = [word for g, word in group_words.items() if tend.part(sit, g, T.READ_GROUP_W) >= KEYING_FROM]
    out += [label for k, label in options if tend.part(sit, k, T.READ_KIND_W) >= KEYING_FROM]
    return out


def prompt(game):
    """The call the game is waiting for (game.awaiting), ready for a screen: who's asking,
    the staff's suggestion, the menu, what the other side is keying on, what fits the scheme."""
    from .. import staff
    a = game.awaiting
    if not a:
        return None
    st = game.state
    idx, kind = a["team"], a["kind"]
    team = game.teams[idx]
    lg = game.league
    crew = staff.staff_of(lg, team.id) if getattr(lg, "staff", None) else {}
    job = {"offense": "OC", "fourth": "HC", "pat": "HC", "defense": "DC"}[kind]
    who = crew.get(job) or crew.get("HC")
    title = {"OC": "Offensive coordinator", "DC": "Defensive coordinator", "HC": "Head coach"}[job if crew.get(job) else "HC"]
    plays = [k for k in coach.PLAY_MENU if k != "sneak" or st.togo <= 2]
    if kind == "defense":
        options = [(k, coach.DEF_MENU[k]) for k in coach.DEF_MENU]
    elif kind == "pat":
        options = [("kick", "Kick the extra point"), ("two_point", "Go for two (coach's play)")]
        options += [(k, "Two: " + coach.PLAY_MENU[k]) for k in plays if k != "sneak"]
    else:
        options = [(k, coach.PLAY_MENU[k]) for k in plays]
        if kind == "fourth":
            kicks = [("punt", "Punt")]
            if st.yl + 17 <= FG_LONGEST or a["suggested"] == "field_goal":
                kicks.append(("field_goal", f"Field goal ({st.yl + 17} yds)"))
            options = kicks + options
    book = game.books.get(idx)
    keying, fits = [], []
    sit = situation(st)
    # Before your first call of the game, what they'd bring from film of your last games.
    film = None
    if (getattr(lg, "playcall_film", None) or {}).get(str(team.id)):
        film = Book(team)
    if kind in ("offense", "fourth"):
        src = book.offense if (book is not None and book.active_off) else (film.offense if film else None)
        if src is not None:
            keying = _keying(src, sit, {"run": "the run", "pass": "the pass"},
                             [(k, coach.PLAY_MENU[k]) for k in plays])
        fit = book.fit_off if book is not None else fit_offense(team)
        if fit:
            odds = odds_offense(st, idx, team)
            mix = sum(q * fit.get(k, 0.0) for k, q in odds.items()) / (sum(odds.values()) or 1.0)
            fits = [k for k in plays if fit.get(k, 0.0) - mix >= FITS_FROM]
    elif kind == "defense":
        src = book.defense if (book is not None and book.active_def) else (film.defense if film else None)
        if src is not None:
            keying = _keying(src, sit, {"blitz": "the blitz"}, list(coach.DEF_MENU.items()))
        fit = book.fit_def if book is not None else fit_defense(team)
        if fit:
            vals = sorted(fit.values())
            mid = vals[len(vals) // 2]
            fits = [k for k in coach.DEF_MENU if fit.get(k, 0.0) - mid >= FITS_FROM]
    labels = dict(options)
    return {"kind": kind, "team": idx, "suggested": a["suggested"],
            "suggested_label": labels.get(a["suggested"], coach.PLAY_MENU.get(a["suggested"], a["suggested"])),
            "options": options, "staff_title": title, "staff_name": who["name"] if who else None,
            "keying": keying, "fits": fits}


class Book:
    """Everything the game keeps about one team's called plays (both sides of the ball).
    Made the first time that team's call isn't its coordinator's. The other side starts from
    the film of your last few games (league.playcall_film): your called plays there count as
    lighter evidence than this game's, older games lighter still."""

    def __init__(self, game_team):
        self.offense = Tendencies(OFF_GROUP)
        self.defense = Tendencies(DEF_GROUP)
        film = (getattr(game_team.league, "playcall_film", None) or {}).get(str(game_team.id), [])
        for age, entry in enumerate(film[:T.READ_FILM_GAMES]):
            w = T.READ_FILM_W * T.READ_FILM_FADE ** age
            for side, tend in (("off", self.offense), ("def", self.defense)):
                if entry.get(side):
                    tend.add_film(entry[side], w)
                else:
                    tend.n["game"] += w * entry.get("n_" + side, 0)    # a game the staff called: all normal
        self.fit_off = fit_offense(game_team)
        self.fit_def = fit_defense(game_team)
        self.active_off = False
        self.active_def = False

    def offense_edge(self, state, odds, choice):
        """The offense's edge on this snap (+ good for your offense), then the call goes in the book."""
        sit = situation(state)
        e = -self.offense.read(sit, choice) + fit_edge(self.fit_off, odds, choice)
        self.offense.record(sit, odds, choice)
        return e

    def defense_edge(self, state, odds, choice):
        """The OFFENSE's edge on this snap from your defensive call (+ = bad for your defense)."""
        sit = situation(state)
        e = T.READ_DEF_K * self.defense.read(sit, choice) - fit_edge(self.fit_def, odds, choice)
        self.defense.record(sit, odds, choice)
        return e


def save_film(league, game):
    """After a game: put each team's called plays on film (league.playcall_film, newest first,
    the last READ_FILM_GAMES games). A team only has film once you've called its plays; its
    games where the staff called everything go on film as normal games, and a team whose film
    is all normal games drops off (it's back to being untouched)."""
    film = getattr(league, "playcall_film", None)
    for idx, team in enumerate(game.teams):
        key = str(team.id)
        book = game.books.get(idx) if getattr(game, "books", None) else None
        if book is None and not (film and key in film):
            continue
        if film is None:
            film = league.playcall_film = {}
        bx = game.box.team
        entry = {"n_off": bx[idx]["plays"], "n_def": bx[1 - idx]["plays"],
                 "off": book.offense.snapshot() if book is not None and book.active_off else None,
                 "def": book.defense.snapshot() if book is not None and book.active_def else None}
        games = [entry] + film.get(key, [])
        games = games[:T.READ_FILM_GAMES]
        if any(e["off"] or e["def"] for e in games):
            film[key] = games
        else:
            film.pop(key, None)
