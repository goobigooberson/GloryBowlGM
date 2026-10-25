# gameteam.py
# One team on game day: who's active, who is on the field each snap, how tired
# players are, how sharp each player is today (form), and how to read a
# player's ratings during a play.

import math
import random
from collections import defaultdict

from .. import depth
from .. import positions as pos
from .. import roster_rules
from . import tuning as T

UNIT_OF_SLOT = {slot: info[2] for slot, info in depth.SLOTS.items()}
NATURAL = {slot: info[1] for slot, info in depth.SLOTS.items()}


_OFFENSE_SLOTS = {"QB", "RB", "FB", "WR1", "WR2", "WR3", "WR4", "TE1", "TE2", "TE3", "LT", "LG", "C", "RG", "RT"}
_DEFENSE_SLOTS = {"LE", "LDT", "RDT", "RE", "WLB", "MLB", "SLB", "CB1", "CB2", "NB", "DB", "FS", "SS"}
_OFFENSE_POS = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C"}
_DEFENSE_POS = {"DE", "DT", "OLB", "ILB", "CB", "S"}
_BACKS = {"RB", "FB"}


# Preseason playing time (Blake: the classic NFL pattern). Position families:
# a resting starter is replaced by a healthy player from the same family.
FAMILY = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
          "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB"}
PRESEASON_STARTERS_SECS = {1: 450, 2: 900, 3: 1800, 4: 0}   # game number -> seconds starters play
PRESEASON_SECOND_STRING_UNTIL = 2700                          # the 3rd string plays the 4th quarter


class _StyleDice:
    """The team's coaches' style (engine/staff.py) handed out in the order
    _build_tendencies asks for it, as gauss(0, spread) = spread x the coach's
    own number. Falsy when the team has no staff (then the old random draw)."""

    def __new__(cls, league, team_id):
        from .. import staff
        st = staff.style(league, team_id) if league is not None and getattr(league, "staff", None) else None
        if not st:
            return None
        obj = super().__new__(cls)
        obj.z = iter([st["pass"], st["aggr"], st["man"], st["blitz"], st["heavy"], st["fb"], st["rb_split"]]
                     + [st["roles"].get(slot, 0.0) for slot in T.TARGET_ROLE_BIAS]
                     + [st["shade"], st["pace"]])
        return obj

    def __init__(self, league, team_id):
        pass

    def gauss(self, mu, sigma):
        return mu + sigma * next(self.z)


_HIDDEN = {}
SEASON_KEY = None    # the test tools' replays set this (simlab.play_season): each replay its own season form


def hidden_form(p, salt, season):
    """Rating points a player plays above (or below) his ratings, never shown: his career-long
    knack (fixed for his career) plus this season's form (tuning.KNACK_SD, SEASON_FORM_SD).
    Drawn from his own dice (league salt and player id), not the game's, so it's the same
    every game and changes nothing else."""
    k = T.KNACK_SD.get(p.position, T.KNACK_SD_OTHER)
    s = T.SEASON_FORM_SD.get(p.position, T.SEASON_FORM_SD_OTHER)
    if not (k or s):
        return 0.0
    if SEASON_KEY is not None:
        season = SEASON_KEY
    key = (salt, p.id, season)
    v = _HIDDEN.get(key)
    if v is None:
        if len(_HIDDEN) > 50000:
            _HIDDEN.clear()
        knack = random.Random(f"knack-{salt}-{p.id}").gauss(0, 1)
        year = random.Random(f"season-form-{salt}-{p.id}-{season}").gauss(0, 1)
        v = _HIDDEN[key] = (knack, year)
    return k * v[0] + s * v[1]


class GameTeam:
    def __init__(self, league, team_id, norms, rng, is_home, unavailable=(), neutral=False,
                 preseason_game=None, hurt=(), extra=()):
        """preseason_game: this team's preseason game number (1-4), or None
        for a regular-season game. neutral: no home field (Hall of Fame Game).
        hurt: players listed Questionable who play anyway (a bit below
        themselves, tuning.PLAYING_HURT). extra: players beyond the 53 for
        this game (elevated from the practice squad), listed last on the
        depth chart at their position's spots."""
        self.league = league
        self.team = league.team(team_id)
        self.id = team_id
        self.abbrev = self.team.abbrev
        self.name = self.team.name
        self.rng = rng
        self.norms = norms
        self.is_home = is_home
        self.roster = league.team_players(team_id)
        extra = [p for p in extra if p.id not in {x.id for x in self.roster}]
        chart = league.depth_charts.get(team_id)
        if not chart:
            chart = depth.auto_depth_chart(self.roster)
        if not chart.get("RB3"):
            # A chart saved before the 3rd-down back spot existed: the staff picks one
            # for this game (the saved chart itself isn't changed).
            chart = depth.fill_missing_spots(dict(chart), self.roster)
        if extra:
            # Elevated players: at the end of the list at their position's spots (this game only).
            chart = {slot: list(ids) for slot, ids in chart.items()}
            for p in sorted(extra, key=lambda p: -p.overall()):
                for slot, (_label, natural, _unit) in depth.SLOTS.items():
                    if natural == p.position and slot in chart:
                        chart[slot].append(p.id)
            self.roster = self.roster + list(extra)
        self.by_id = {p.id: p for p in self.roster}
        if any(pid not in self.by_id for ids in chart.values() for pid in ids):
            # Someone listed has left the roster (released, injured reserve): skip him.
            chart = {slot: [pid for pid in ids if pid in self.by_id] for slot, ids in chart.items()}
        self.chart = chart
        unavailable = set(unavailable)
        self.preseason_game = preseason_game
        if preseason_game:
            # Everyone healthy dresses in the preseason (no 48-man game-day limit).
            self.actives = {p.id for p in self.roster if p.id not in unavailable}
        else:
            # Who dresses is the staff's call: ties go by how its staff rates them (evaluation.py).
            from .. import evaluation
            staff_rating = lambda p: evaluation.overall(league, team_id, p)     # noqa: E731
            self.actives = roster_rules.game_day_actives(self.roster, chart, unavailable, rating=staff_rating)
        self.out = {p.id for p in self.roster if p.id not in self.actives}
        # The emergency third QB (real rule since 2023): inactive, but he can come in
        # if both active quarterbacks are out for the game (available() below).
        self.emergency_qb = (None if preseason_game else
                             roster_rules.emergency_qb(self.roster, self.actives, unavailable, rating=staff_rating))
        self._active_qbs = [p.id for p in self.roster if p.position == "QB" and p.id in self.actives]
        # Preseason: who sits as the game goes on (see preseason_clock).
        self.resting = set()
        self._first_string = set()
        self._second_string = set()
        if preseason_game:
            for slot, ids in chart.items():
                if slot in _OFFENSE_SLOTS or slot in _DEFENSE_SLOTS:
                    if ids:
                        self._first_string.add(ids[0])
            for slot, ids in chart.items():
                if slot in _OFFENSE_SLOTS or slot in _DEFENSE_SLOTS:
                    for pid in ids[1:2]:
                        if pid not in self._first_string:
                            self._second_string.add(pid)
        self.injured = {}            # pid -> plays until he can return (None = done for the day)
        self.injuries = []           # (pid, weeks_out, description) for the season loop
        self.fatigue = defaultdict(float)
        self.carries = defaultdict(int)   # this game, for the backfield workload
        self.form = {}
        salt = league.settings.get("salt", "")
        for p in self.roster:
            consistency = getattr(p, "consistency", 50)
            sd = T.FORM_SD * (1.35 - consistency / 100 * 0.7)
            self.form[p.id] = rng.gauss(0, sd) + hidden_form(p, salt, league.season)
        # Playing hurt: {player id: rating points off} (by injury; engine/injuries.py RECOVERY).
        for pid, pts in (hurt.items() if isinstance(hurt, dict) else ((p, T.PLAYING_HURT) for p in hurt)):
            if pid in self.form:
                self.form[pid] -= pts
        self.edge = T.HOME_EDGE if is_home and not neutral else 0.0
        caps = league.captains.get(team_id, {})
        self.captain_z = {}
        for unit in ("Offense", "Defense"):
            p = self.by_id.get(caps.get(unit))
            boost = depth.captain_boost(p.leadership) if p else 0.0
            self.captain_z[unit] = boost / 9.0      # rating points -> about z units
        self.captain_ids = set(caps.values())
        self._val = {}
        self._pen = {}
        self._fit = {}
        self.timeouts = 3
        self._build_tendencies()

    # ------------------------------------------------------------------
    # Ratings
    # ------------------------------------------------------------------
    def raw(self, p, skill, position=None):
        """His current rating in a skill (estimated if he never trained it; playing a
        related position, some of that position's craft carries over: depth.RELATED)."""
        key = (p.id, skill, position)
        v = self._val.get(key)
        if v is None:
            if skill in p.skills:
                v = p.skills[skill][0]
            else:
                v = depth._skill_value(p, skill, 0, position)
            self._val[key] = v
        return v

    def slot_penalty(self, p, slot):
        """Rating points lost playing this spot (new position, other side of the line)."""
        key = (p.id, slot)
        v = self._pen.get(key)
        if v is None:
            natural = NATURAL[slot]
            if natural in ("KR", "PR"):
                v = 0.0
            else:
                fit = depth.rating_at(p, slot)          # = spot_fit(...)["now"], faster
                if natural == p.position:
                    base = p.overall()
                else:
                    total = wsum = 0.0
                    for s, w in pos.POSITIONS[natural][1]:
                        if w > 0:
                            total += depth._skill_value(p, s, 0, natural) * w
                            wsum += w
                    base = total / wsum
                v = min(0.0, fit - base)
            self._pen[key] = v
        return v

    def z(self, p, slot, skill):
        """How player p compares to an average starter at this spot, in this skill,
        today. 0 = average starter, +1 = clearly better, -1 = clearly worse."""
        natural = NATURAL.get(slot, p.position)
        value = self.raw(p, skill, natural) + self.slot_penalty(p, slot) + self.form[p.id]
        f = self.fatigue[p.id]
        limit = self.fatigue_limit(p)
        if f > limit:
            value -= (f - limit) * T.FATIGUE_EFFECT * 10
        if natural in ("KR", "PR"):
            m, sd = self.norms.get(natural, skill)
        else:
            m, sd = self.norms.get(natural, skill)
        z = (value - m) / sd
        # Diminishing returns at the extremes: great players are great, but a
        # single player can't take over every snap.
        cap = T.Z_CAP_GENERATIONAL if p.generational else T.Z_CAP
        if z < 0 and natural not in ("KR", "PR") and natural != p.position:
            # Out of position, the soft floor doesn't apply: a defensive tackle at
            # quarterback is far worse than the worst real quarterback. (Before Oct 23
            # the floor made him merely a bad QB: a playtest DT threw for 333 yards.)
            z = max(T.Z_FLOOR_OUT_OF_POSITION, z) + self.edge
        else:
            z = cap * math.tanh(z / cap) + self.edge
        unit = UNIT_OF_SLOT.get(slot)
        if unit in self.captain_z:
            z += self.captain_z[unit]
        return z

    def zmix(self, p, slot, weights):
        """Weighted blend of z-scores, e.g. {"pass_block": .55, "footwork": .3}."""
        return sum(w * self.z(p, slot, s) for s, w in weights.items())

    def untrained(self, p, slot, weights):
        """How far below the worst real player at this spot he plays (z units, 0 or less).
        Only a player out of position can be (at his own position z has a soft floor), so
        this is 0 in normal play. The plays add it outside their per-play caps, which exist
        to soften real players' extremes, not to hide a receiver at left tackle (Oct 24)."""
        natural = NATURAL.get(slot, p.position)
        if natural == p.position or natural in ("KR", "PR"):
            return 0.0
        floor = T.Z_CAP_GENERATIONAL if p.generational else T.Z_CAP
        return min(0.0, self.zmix(p, slot, weights) + floor)

    def untrained_qb_lean(self):
        """Run/pass logit nudge when the man at quarterback isn't a quarterback (0 otherwise):
        coaches stop asking him to throw (tuning.UNTRAINED_QB_RUN_K)."""
        qb = next((self.by_id[pid] for pid in self.chart.get("QB", []) if self.available(pid)), None)
        if qb is None or qb.position == "QB":
            return 0.0
        key = ("qb_lean", qb.id)
        v = self._pen.get(key)
        if v is None:
            v = self._pen[key] = T.UNTRAINED_QB_RUN_K * self.untrained(qb, "QB", {"accuracy": .55, "short_pass": .45})
        return v

    def talent_z(self, p, slot=None):
        """How good he is overall, in z vs average starters. With slot: at that spot (a player
        away from his own position is judged by his rating there, not his own position's
        overall: a good fullback behind the running back isn't an equal back, Oct 24)."""
        natural = NATURAL.get(slot, p.position) if slot else p.position
        if natural != p.position and natural not in ("KR", "PR"):
            m, sd = self.norms.overall_of(natural)
            z = (self.rating_at(p, slot) + self.form[p.id] - m) / sd
        else:
            m, sd = self.norms.overall_of(p.position)
            z = (p.overall() + self.form[p.id] - m) / sd
        cap = T.Z_CAP_GENERATIONAL if p.generational else T.Z_CAP
        return cap * math.tanh(z / cap)

    # ------------------------------------------------------------------
    # Who is on the field
    # ------------------------------------------------------------------
    def available(self, pid):
        if pid in self.injured:
            return False
        if pid in self.out:
            # The emergency QB only once both active quarterbacks are out for the game.
            return (pid == self.emergency_qb and len(self._active_qbs) >= 2
                    and all(self.injured.get(q, 0) is None for q in self._active_qbs))
        return True

    def preseason_clock(self, elapsed):
        """Preseason only: who rests at this point of the game (elapsed game
        seconds). Starters play their share (a series or two in game 1, about
        a quarter in game 2, the first half in the 'dress rehearsal' game 3,
        none in game 4); the second string plays until the 4th quarter; then
        the third string. Where a position has no healthy backup left, the
        starter stays in (a 53-man roster isn't a 90-man camp roster)."""
        if not self.preseason_game:
            return
        resting = set()
        if elapsed >= PRESEASON_STARTERS_SECS.get(self.preseason_game, 0):
            resting |= self._first_string
        if elapsed >= PRESEASON_SECOND_STRING_UNTIL:
            resting |= self._second_string
        self.resting = resting

    def _fresh_first(self, slot, ids, used):
        """Preseason: put players who aren't resting first, from the same
        position family, including healthy players not listed at this spot."""
        natural = NATURAL.get(slot)
        fam = FAMILY.get(natural)
        if fam is None:                    # returners: anyone not resting
            fresh = [pid for pid in ids if pid not in self.resting]
            return fresh + [pid for pid in ids if pid in self.resting]
        def same(pid):
            return FAMILY.get(self.by_id[pid].position) == fam
        fresh = [pid for pid in ids if pid not in self.resting and same(pid)]
        if not fresh:
            extra = [p for p in self.roster if self.available(p.id) and p.id not in used
                     and p.id not in self.resting and p.id not in ids and FAMILY.get(p.position) == fam]
            extra.sort(key=lambda p: self.rating_at(p, slot), reverse=True)
            fresh = [p.id for p in extra[:1]]
        # No fresh player left here: the second string comes back before the starters.
        rest = [pid for pid in ids if pid not in fresh]
        rest.sort(key=lambda pid: 1 if pid in self._first_string else 0)
        if not fresh and not any(pid in self._second_string for pid in rest):
            # Nobody from the second string listed here: the best unlisted one from
            # this family, before a starter.
            second = [p for p in self.roster if p.id in self._second_string and self.available(p.id)
                      and p.id not in used and p.id not in ids and FAMILY.get(p.position) == fam]
            second.sort(key=lambda p: self.rating_at(p, slot), reverse=True)
            rest = [p.id for p in second[:1]] + rest
        return fresh + rest

    def fatigue_limit(self, p):
        if "endurance" in p.skills:
            endurance = p.skills["endurance"][0]
        else:
            endurance = 50 + 0.3 * (p.athletic.get("strength", 50) - 50)
        return T.FATIGUE_SUB_AT * (0.7 + endurance / 100 * 0.6)

    def lineup(self, package, short=False, passing=False):
        """{slot: player} for a package, walking each spot's depth list past
        players who are out, injured, already on the field, or worn out.
        short=True (goal line, 3rd/4th and 1): starters stay in more.
        passing=True (3rd/4th and 5+, two-minute drill): the 3rd-down back
        usually plays running back."""
        used = set()
        result = {}
        self._short = short
        self._passing = passing
        for slot in depth.PACKAGES[package]:
            result[slot] = self._fill(slot, used)
        self._short = False
        self._passing = False
        return result

    def special(self, slot, used=None):
        return self._fill(slot, used if used is not None else set())

    def _fill(self, slot, used):
        # Obvious passing down: the 3rd-down back usually plays running back
        # (his list is used instead of the running back list for this snap).
        # When the starting back is his own 3rd-down back, nothing changes (the
        # usual rotation still gives the backup his series).
        src = slot
        if slot == "RB" and getattr(self, "_passing", False) and self.chart.get("RB3") \
                and self.chart["RB3"][0] != (self.chart.get("RB") or [None])[0] \
                and self.rng.random() < T.THIRD_DOWN_BACK_SHARE:
            src = "RB3"
        ids = [pid for pid in self.chart.get(src, []) if self.available(pid) and pid not in used]
        if src != slot and not ids:
            src = slot
            ids = [pid for pid in self.chart.get(src, []) if self.available(pid) and pid not in used]
        # Backups from the other side of the ball (a linebacker listed as the
        # third tight end) only go in when no one from that side is left.
        side = _OFFENSE_POS if slot in _OFFENSE_SLOTS else (_DEFENSE_POS if slot in _DEFENSE_SLOTS else None)
        if side is not None and len(ids) > 1:
            listed = self.chart.get(src, [])
            starter = listed[0] if listed else None
            ids = sorted(ids, key=lambda pid: 0 if (pid == starter or getattr(self.by_id.get(pid), "position", None) in side) else 1)
        if side is not None and ids and ids[0] != (self.chart.get(src) or [None])[0] \
                and getattr(self.by_id.get(ids[0]), "position", None) not in side:
            # Everyone listed from this side is out: a healthy player from this
            # side who isn't listed here (a running back at receiver, a
            # receiver at tight end) goes in before a two-way emergency.
            alt = self._emergency(slot, used)
            if alt and self.by_id[alt[0]].position in side:
                ids = alt + ids
        if not ids:
            ids = self._emergency(slot, used)
            if not ids:
                return None
        if self.resting:
            ids = self._fresh_first(slot, ids, used)
        first = self.by_id[ids[0]]
        pick = first
        # Planned rotation: backups get series at running back, receiver and
        # on the defensive line, more often when they're close in talent.
        base = T.ROTATION.get(slot)
        if src == "RB3":
            base = 0.0      # the 3rd-down back plays the down (no planned series swap)
        elif slot == "RB" and hasattr(self, "rb_split"):
            base = self.rb_split
            # Workload: once the lead back has had his share of carries today,
            # the staff gets the backup more involved (sooner for a back with
            # low endurance). Real backs rarely top 25-30 carries.
            ids0 = [pid for pid in self.chart.get(slot, []) if self.available(pid) and pid not in used]
            if ids0:
                lead = self.by_id[ids0[0]]
                end = lead.skills.get("endurance", (50, 50))[0]
                soft = T.RB_CARRIES_SOFT + T.RB_CARRIES_ENDURANCE * (end - 50) / 50
                over = self.carries[lead.id] - soft
                if over > 0:
                    base = min(0.85, base + T.RB_CARRIES_STEP * over)
        if base and getattr(self, "_short", False):
            # Short yardage / goal line: starters stay in, though many staffs
            # have a goal-line back.
            base *= T.SHORT_YARDAGE_RB_ROTATION if slot == "RB" else 0.10
        # Planned rotation and fatigue subs only bring in players from this
        # side of the ball.
        subs = [pid for pid in ids[1:] if side is None or getattr(self.by_id.get(pid), "position", None) in side]
        if self.resting:
            subs = [pid for pid in subs if pid not in self.resting]     # resting players stay on the bench
        if side is not None and not subs and (base or T.FATIGUE_PER_SNAP.get(first.position, 0) > 0):
            # Nobody listed behind him from this side (the listed backups are
            # hurt, or the chart lists two-way players): rotate in the best
            # healthy player from this side who isn't on the field.
            alt = self._emergency(slot, set(used) | {first.id})
            if alt and self.by_id[alt[0]].position in side:
                subs = alt
        if slot == "RB" and first.position in _BACKS:
            # Rotation, rest and fatigue swaps at running back bring in another
            # back (a fullback if he's all that's left), not the receiver listed
            # last on the chart: with the other backs hurt, the healthy starter
            # carries the load. A receiver plays there only when no back is left.
            backs = [pid for pid in subs if self.by_id[pid].position in _BACKS]
            if not backs:
                spare = [p for p in self.roster if p.position in _BACKS and p.id != first.id
                         and p.id in self.actives and self.available(p.id) and p.id not in used
                         and p.id not in self.resting]
                spare.sort(key=lambda p: self.rating_at(p, slot), reverse=True)
                backs = [p.id for p in spare[:1]]
            subs = backs
        if slot == "RB" and subs and not self.preseason_game:
            # Game decided: protect the lead back, the backup runs out the clock.
            qtr, lead = getattr(self, "game_lead", (1, 0))
            rest = next((share for q, margin, share in T.RB_BLOWOUT_REST if qtr >= q and lead >= margin), 0.0)
            if rest and self.rng.random() < rest:
                second = self.by_id[subs[0]]
                used.add(second.id)
                return second
        if base and subs and slot in ("TE1", "TE2", "TE3"):
            # Tight end rotation brings in another tight end (the chart may list the fullback
            # ahead of the 3rd TE, a blocking fit, but staffs rotate their tight ends).
            subs = sorted(subs, key=lambda pid: 0 if self.by_id[pid].position == "TE" else 1)
        if base and subs:
            second = self.by_id[subs[0]]
            gap = max(0.0, self.talent_z(first, slot) - self.talent_z(second, slot))
            gap_k = T.ROTATION_GAP_K_WR if slot[:2] == "WR" else T.ROTATION_GAP_K
            r = self.rng.random()
            if r < base * math.exp(-gap_k * gap):
                used.add(second.id)
                return second
            third_base = T.ROTATION.get(slot + "_3")
            if third_base and len(subs) > 1:
                third = self.by_id[subs[1]]
                gap3 = max(0.0, self.talent_z(first, slot) - self.talent_z(third, slot))
                if self.rng.random() < third_base * math.exp(-gap_k * gap3):
                    used.add(third.id)
                    return third
        if subs and T.FATIGUE_PER_SNAP.get(first.position, 0) > 0:
            over = self.fatigue[first.id] - self.fatigue_limit(first)
            if over > 0:
                backup = self.by_id[subs[0]]
                chance = min(0.85, over / 14.0)
                if self.rng.random() < chance and self.fatigue[backup.id] < self.fatigue[first.id]:
                    pick = backup
        used.add(pick.id)
        return pick

    def rating_at(self, p, slot):
        """depth.rating_at, remembered for the game (ratings don't change during one).
        Preseason games with 90-man rosters asked it ~1 million times a week (17 of a
        preseason week's 23 seconds) when looking for a fresh player at a spot."""
        key = (p.id, slot)
        v = self._fit.get(key)
        if v is None:
            v = self._fit[key] = depth.rating_at(p, slot)
        return v

    def _emergency(self, slot, used):
        """Nobody listed is available: use the best healthy active player for it."""
        cands = [p for p in self.roster if self.available(p.id) and p.id not in used]
        if not cands:
            return []
        # Stay on the same side of the ball: a backup running back or tight end
        # fills in at receiver before a linebacker would.
        side = _OFFENSE_POS if slot in _OFFENSE_SLOTS else (_DEFENSE_POS if slot in _DEFENSE_SLOTS else None)
        if side is not None:
            same = [p for p in cands if p.position in side]
            if same:
                cands = same
        cands.sort(key=lambda p: self.rating_at(p, slot), reverse=True)
        return [cands[0].id]

    def after_play(self, on_field_ids, between_drives=False):
        for p in self.roster:
            if p.id in on_field_ids:
                self.fatigue[p.id] += T.FATIGUE_PER_SNAP.get(p.position, 2.0)
            else:
                rec = T.FATIGUE_RECOVERY * (3 if between_drives else 1)
                if self.fatigue[p.id] > 0:
                    self.fatigue[p.id] = max(0.0, self.fatigue[p.id] - rec)
        # minor injuries heal as plays go by
        for pid in list(self.injured):
            left = self.injured[pid]
            if left is not None:
                if left <= 1:
                    del self.injured[pid]
                else:
                    self.injured[pid] = left - 1

    def rest(self, amount):
        for pid in list(self.fatigue):
            self.fatigue[pid] = max(0.0, self.fatigue[pid] - amount)

    # ------------------------------------------------------------------
    # Coaching tendencies (until coaches exist, they come from the roster)
    # ------------------------------------------------------------------
    def starter(self, slot):
        ids = [pid for pid in self.chart.get(slot, []) if pid in self.actives]
        return self.by_id[ids[0]] if ids else None

    def _second(self, slot):
        ids = [pid for pid in self.chart.get(slot, []) if pid in self.actives]
        return self.by_id[ids[1]] if len(ids) > 1 else None

    def _build_tendencies(self):
        # The coordinators' style (Oct 24: the team's real coaches, engine/staff.py:
        # the offensive coordinator's offense, the defensive coordinator's defense,
        # the head coach's 4th-down aggression; each coach's style numbers were
        # drawn once from exactly the spreads below, so league stats are as before,
        # but a team keeps its identity while its coordinator stays and the style
        # moves with him). A league without staffs draws it from the team and season
        # as before. The roster still shapes it each game.
        style = _StyleDice(self.league, self.id) or random.Random(
            f"style-{self.league.settings.get('salt', '')}-{self.league.season}-{self.id}-{self.abbrev}")

        def tz(slot):
            p = self.starter(slot)
            return self.talent_z(p, slot) if p else -1.0

        pass_strength = 0.6 * tz("QB") + 0.25 * (tz("WR1") + tz("WR2")) / 2 + 0.15 * tz("TE1")
        run_strength = 0.6 * tz("RB") + 0.4 * sum(tz(s) for s in ("LT", "LG", "C", "RG", "RT")) / 5
        # Logit nudge to the pass rate: teams lean on what they're good at, plus
        # the coordinator's own style.
        self.pass_bias = max(-T.PASS_BIAS_MAX, min(T.PASS_BIAS_MAX, T.STRENGTH_PASS_K * (pass_strength - run_strength)
                                        + style.gauss(0, T.STYLE_PASS_SD)))
        self.aggression = style.gauss(0, 0.35)       # 4th down go-for-it lean
        cb = [self.starter(s) for s in ("CB1", "CB2")]
        man_edge = sum(self.zmix(p, "CB1", {"man_cover": 1.0}) - self.zmix(p, "CB1", {"zone_cover": 1.0})
                       for p in cb if p) / 2
        self.man_rate = min(0.55, max(0.15, 0.31 + 0.06 * man_edge + style.gauss(0, 0.06)))
        rush = [self.starter(s) for s in ("LE", "RE", "LDT", "RDT")]
        rush_z = sum(self.zmix(p, "LE", {"rush_tech": .6, "rush_power": .4}) for p in rush if p) / 4
        self.blitz_rate = min(0.42, max(0.14, 0.26 - 0.03 * rush_z + style.gauss(0, 0.06)))
        rb = self.starter("RB")
        if rb:
            power = self.zmix(rb, "RB", {"power_run": 1.0})
            speed = self.zmix(rb, "RB", {"elusiveness": .5, "breakaway": .5})
            self.outside_lean = 0.12 * (speed - power)
        else:
            self.outside_lean = 0.0
        te2 = self.starter("TE2")
        fb = self.starter("FB")
        self.heavy_lean = 0.25 * (self.talent_z(te2, "TE2") if te2 else -1) + style.gauss(0, 0.25)
        self.fb_lean = 0.25 * (self.talent_z(fb, "FB") if fb else -2) + style.gauss(0, 0.25)
        qb = self.starter("QB")
        self.qb_mobility = self.zmix(qb, "QB", {"scrambling": 1.0}) if qb else -1.0
        # Running back usage: some staffs ride one workhorse, others split carries.
        # Bell cow or committee: a back with the endurance to carry the load,
        # clearly better than his backup, gets most of the work; two similar
        # backs or a starter who wears down means a committee. The staff's
        # own style adds some variety.
        rb1, rb2 = self.starter("RB"), self._second("RB")
        endurance_z = ((rb1.skills.get("endurance", (50, 50))[0] - 50) / 15) if rb1 else 0.0
        gap = max(0.0, self.talent_z(rb1, "RB") - self.talent_z(rb2, "RB")) if (rb1 and rb2) else 1.0
        self.rb_split = min(0.55, max(T.RB_SPLIT_MIN, 0.04 + T.ROTATION["RB"]
                                      * math.exp(style.gauss(0, T.STYLE_RB_SPLIT_SD)
                                                 - T.RB_ENDURANCE_SPLIT_K * endurance_z
                                                 - T.RB_GAP_SPLIT_K * gap)))
        # Who the passing game is built around: some feature their tight end,
        # some throw to the backs, some spread it out.
        self.role_bias = {slot: b + style.gauss(0, T.STYLE_ROLE_SD.get(slot[:2], 0.12))
                          for slot, b in T.TARGET_ROLE_BIAS.items()}
        # A star tight end is a featured part of the passing game, whoever the coordinator
        # is (Oct 25: the pull above didn't follow his talent, so the league's best tight
        # ends drew ~17% of their teams' targets vs real ~20-27%, and the top TE caught 92-99
        # passes a season vs real 107-126; tuning.TE_FEATURE_K).
        te = self.starter("TE1")
        if te is not None:
            self.role_bias["TE1"] += T.TE_FEATURE_K * max(0.0, self.talent_z(te, "TE1") - T.TE_FEATURE_FROM)
        # Receivers' and tight ends' pull follows the player, not the spot (Oct 23): a backup
        # filling the top receiver's spot while he rests doesn't inherit his share of throws
        # (real teams keep feeding their best receivers; once they rotate like real ones, the
        # spot-based pull cut the league's top receiver from ~1,810 yards to ~1,560).
        self.target_role = {}
        for slot in ("WR1", "WR2", "WR3", "WR4", "TE1", "TE2", "TE3"):
            ids = self.chart.get(slot) or []
            if ids and ids[0] not in self.target_role:
                self.target_role[ids[0]] = slot
        # How often this defense rolls extra coverage to the other team's best receiver.
        self.shade_rate = min(0.8, max(0.1, T.SHADE_RATE + style.gauss(0, 0.10)))
        # Offensive pace: seconds faster (-) or slower (+) than average between
        # plays. Fast-paced offenses run more plays and give the opponent more too.
        self.pace = max(-2.2 * T.STYLE_PACE_SD, min(2.2 * T.STYLE_PACE_SD, style.gauss(0, T.STYLE_PACE_SD)))
