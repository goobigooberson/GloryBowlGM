# game.py
# Runs a whole game, play by play: downs, the clock, possessions, scoring,
# halftime, overtime, and late-game clock management.
#
#   game = Game(league, home_id, away_id)
#   for event in game.events():      # step through plays (the live game screen)
#       ...
#   result = game.run()              # or simulate straight to the final

import math
import random
from dataclasses import dataclass, field

from .. import injuries
from . import coach
from . import plays as P
from . import penalties as PEN
from . import text
from . import tuning as T
from .gameteam import GameTeam
from .norms import build_norms
from .stats import BoxScore
from .weather import generate as generate_weather

OL = ("LT", "LG", "C", "RG", "RT")


@dataclass
class GameState:
    qtr: int = 1
    clock: float = 900.0
    poss: int = 0              # index of the team with the ball (0 = home, 1 = away)
    down: int = 1
    togo: int = 10
    yl: int = 75               # yards from the offense to the opponent's goal line
    score: list = field(default_factory=lambda: [0, 0])
    clock_running: bool = False
    ready_restart: bool = False     # clock restarts on the ready signal (out of bounds, early game)
    warned: set = field(default_factory=set)

    def copy(self):
        s = GameState(self.qtr, self.clock, self.poss, self.down, self.togo, self.yl, list(self.score),
                      self.clock_running, self.ready_restart, set(self.warned))
        return s


@dataclass
class Event:
    """One line of the game: a play, a score, a timeout, the end of a quarter."""
    kind: str                  # play, kickoff, punt, fg, xp, two_point, penalty, timeout, note, quarter, final
    text: str
    qtr: int
    clock: float               # game clock when the play started
    poss: int                  # team with the ball (index)
    down: int = 0
    togo: int = 0
    yl: int = 0
    score: tuple = (0, 0)      # after the play
    scoring: bool = False
    drive: int = 0
    after: object = None       # GameState after the play
    yards: int = 0
    big: bool = False          # highlight-worthy (score, turnover, long gain)
    detail: str = ""           # what happened on the field (formation, matchups)


class Game:
    def __init__(self, league, home_id, away_id, seed=None, week=1, season=None,
                 unavailable=None, norms=None, weather=None, preseason=None, neutral=False,
                 playoff=False, hurt=None, extra=None):
        """preseason: {team id: that team's preseason game number 1-4} for a
        preseason game (playing time follows the preseason plan), else None.
        neutral: no home-field edge (the Hall of Fame Game, the Glory Bowl).
        playoff: playoff overtime rules (15-minute periods until someone wins).
        week: the regular-season week (preseason games use 0 and below, so
        the weather is August's; playoff weeks run past the last week).
        extra: {team id: [players]} beyond the 53 for this game: practice
        squad players elevated for it (or, in the preseason, the whole
        practice squad, who are still on the camp roster)."""
        self.rng = random.Random(seed)
        rng = self.rng
        self.league = league
        self.season = season or league.season
        self.week = week
        self.preseason = preseason
        self.playoff = playoff
        norms = norms or build_norms(league)
        unavailable = unavailable or {}
        pre = preseason or {}
        hurt = hurt or {}
        extra = extra or {}
        self.teams = [GameTeam(league, home_id, norms, rng, True, unavailable.get(home_id, ()),
                               neutral=neutral, preseason_game=pre.get(home_id), hurt=hurt.get(home_id, ()),
                               extra=extra.get(home_id, ())),
                      GameTeam(league, away_id, norms, rng, False, unavailable.get(away_id, ()),
                               neutral=neutral, preseason_game=pre.get(away_id), hurt=hurt.get(away_id, ()),
                               extra=extra.get(away_id, ()))]
        self.weather = weather or generate_weather(self.teams[0].abbrev, self.season, week, rng)
        self.state = GameState()
        self.box = BoxScore(self)
        self.log = []
        self.finished = False
        self.overtime = False
        self.drive_no = 0
        self._drive = None
        self._need_kickoff = True
        self._kicking = 0
        self._need_pat = False
        self._safety_kick = False
        self._first_receiver = 0
        self._ot_poss = []          # team indices whose overtime possessions have ended
        self._ot_first = None
        self._last_play_inbounds = False
        self._detail = ""

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def run(self):
        for _ in self.events():
            pass
        return self

    def events(self):
        """Generator: yields Event objects in order until the game ends."""
        st = self.state
        rng = self.rng
        toss = 0 if rng.random() < 0.5 else 1
        receiver = 1 - toss                 # the toss winner defers to the second half
        self._first_receiver = receiver
        self._kicking = toss
        yield self._note(f"{self.teams[toss].abbrev} wins the toss and defers. "
                         f"{self.teams[receiver].abbrev} will receive. Weather: {self.weather.text()}.")
        while not self.finished:
            for idx, t in enumerate(self.teams):
                t.game_lead = (st.qtr, st.score[idx] - st.score[1 - idx])
            if self.preseason:
                elapsed = (min(st.qtr, 4) - 1) * 900 + (900 - st.clock) if st.qtr <= 4 else 3600
                for t in self.teams:
                    t.preseason_clock(elapsed)
            if self._need_kickoff:
                yield from self._kickoff()
            elif self._need_pat:
                yield from self._pat()
            else:
                yield from self._snap()
            yield from self._check_clock()
        self._close_drive("End of game")

    # ------------------------------------------------------------------
    # Clock and quarters
    # ------------------------------------------------------------------
    def _check_clock(self):
        st = self.state
        if self.finished:
            return
        # Two-minute warning (after the play that crossed 2:00).
        if st.qtr in (2, 4) and st.qtr not in st.warned and 0 < st.clock <= 120 and not self._need_kickoff:
            st.warned.add(st.qtr)
            st.clock_running = False
            st.ready_restart = False
            yield self._note("Two-minute warning.", kind="quarter")
        if st.clock > 0 or self._need_pat:
            return
        yield from self._end_quarter()

    def _end_quarter(self):
        st = self.state
        q = st.qtr
        if q in (1, 3):
            yield self._note(f"END OF {'1ST' if q == 1 else '3RD'} QUARTER", kind="quarter")
            st.qtr += 1
            st.clock = 900.0
            st.clock_running = False
            st.ready_restart = False
            for t in self.teams:
                t.rest(10)
            return
        if q == 2:
            yield self._note("END OF 2ND QUARTER", kind="quarter")
            self._close_drive("End of half")
            st.qtr = 3
            st.clock = 900.0
            st.clock_running = False
            st.ready_restart = False
            for t in self.teams:
                t.timeouts = 3
                t.rest(100)
            self._need_kickoff = True
            self._kicking = self._first_receiver
            return
        if q == 4:
            if st.score[0] == st.score[1]:
                yield self._note("END OF REGULATION. Overtime!", kind="quarter")
                self._close_drive("End of regulation")
                self.overtime = True
                st.qtr = 5
                # Playoffs: 15-minute periods, 3 timeouts (as in a half);
                # regular season: one 10-minute period, 2 timeouts.
                st.clock = 900.0 if self.playoff else 600.0
                st.clock_running = False
                st.ready_restart = False
                for t in self.teams:
                    t.timeouts = 3 if self.playoff else 2
                    t.rest(60)
                toss = 0 if self.rng.random() < 0.5 else 1
                self._kicking = 1 - toss
                self._ot_first = toss
                self._need_kickoff = True
                yield self._note(f"{self.teams[toss].abbrev} wins the overtime toss and will receive.")
                return
            yield from self._final()
            return
        # End of an overtime period. Regular season: the game ends (a tie
        # stands). Playoffs: someone has to win, so play another 15-minute
        # period (the clock just keeps going, like a new quarter; timeouts
        # reset every two periods, as at halftime).
        if self.playoff and not self.finished:
            yield self._note(f"END OF OVERTIME PERIOD {q - 4}. The game continues.", kind="quarter")
            st.qtr += 1
            st.clock = 900.0
            st.clock_running = False
            st.ready_restart = False
            for t in self.teams:
                t.rest(10)
                if (st.qtr - 5) % 2 == 0:
                    t.timeouts = 3
            return
        yield from self._final()

    def _final(self):
        st = self.state
        self.finished = True
        self._close_drive("End of game")
        h, a = self.teams
        tie = st.score[0] == st.score[1]
        txt = (f"FINAL{' (OT)' if self.overtime else ''}: {a.abbrev} {st.score[1]}, {h.abbrev} {st.score[0]}"
               + (" - TIE" if tie else ""))
        yield self._note(txt, kind="final")

    def _runoff(self, tempo, off_idx):
        """Time that comes off before the snap."""
        st = self.state
        if not st.clock_running and not st.ready_restart:
            return 0.0
        rng = self.rng
        pace = getattr(self.teams[off_idx], "pace", 0.0)
        if st.ready_restart:
            secs = T.RUNOFF_AFTER_OOB + pace + rng.gauss(0, 4)
        elif tempo == "hurry":
            secs = T.RUNOFF_HURRY + rng.gauss(0, 3)
        elif tempo == "milk":
            secs = T.RUNOFF_MILK + rng.gauss(0, 1.5)
        else:
            secs = T.RUNOFF_NORMAL + pace + rng.gauss(0, 4.5)
        return max(3.0, secs)

    def _late_window(self):
        """Last 2:00 of the first half or last 5:00 of the game: the clock stays
        stopped after out-of-bounds plays until the next snap."""
        st = self.state
        return (st.qtr == 2 and st.clock <= 120) or (st.qtr >= 4 and st.clock <= 300)

    def _tick(self, elapsed, off_idx):
        st = self.state
        used = min(st.clock, elapsed)
        st.clock = max(0.0, st.clock - elapsed)
        self.box.team[off_idx]["top"] += used
        if self._drive is not None:
            self._drive["time"] += used

    # ------------------------------------------------------------------
    # Drives
    # ------------------------------------------------------------------
    def _open_drive(self, team_idx, how):
        self._close_drive(None)
        self.drive_no += 1
        st = self.state
        self._drive = {"no": self.drive_no, "team": team_idx, "qtr": st.qtr, "clock": st.clock,
                       "start_yl": st.yl, "plays": 0, "yards": 0, "time": 0.0, "result": None,
                       "how": how, "red_zone": False}

    def _close_drive(self, result):
        d = self._drive
        if d is None:
            return
        if result is None and d["result"] is None:
            d["result"] = "Unknown"
        elif result is not None and d["result"] is None:
            d["result"] = result
        self.box.drives.append(d)
        if d["red_zone"]:
            self.box.team[d["team"]]["rz_trips"] += 1
            if d["result"] == "Touchdown":
                self.box.team[d["team"]]["rz_td"] += 1
        self._drive = None

    def _set_result(self, result):
        if self._drive is not None and self._drive["result"] is None:
            self._drive["result"] = result

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _note(self, msg, kind="note"):
        st = self.state
        ev = Event(kind=kind, text=msg, qtr=st.qtr, clock=st.clock, poss=st.poss,
                   score=tuple(st.score), drive=self.drive_no, after=st.copy())
        self.log.append(ev)
        return ev

    def _event(self, kind, msg, before, yards=0, scoring=False, big=False):
        st = self.state
        scrimmage = kind in ("play", "penalty", "punt", "fg")
        ev = Event(kind=kind, text=msg, qtr=before.qtr, clock=before.clock, poss=before.poss,
                   down=before.down if scrimmage else 0, togo=before.togo, yl=before.yl, score=tuple(st.score),
                   scoring=scoring, drive=self.drive_no, after=st.copy(), yards=yards, big=big,
                   detail=self._detail if kind in ("play", "penalty", "two_point") else "")
        self.log.append(ev)
        return ev

    def _score(self, team_idx, pts, label, before_clock=None, merge=False):
        """Add points. merge=True attaches the try after a touchdown to the
        touchdown's line in the scoring summary, the way real summaries read:
        'J.Smith 12 yd pass from K.Jones (M.Brown kick)'."""
        st = self.state
        st.score[team_idx] += pts
        if pts:
            self.box.points(team_idx, st.qtr, pts)
        if merge and self.box.scoring and self.box.scoring[-1]["team"] == team_idx:
            last = self.box.scoring[-1]
            last["text"] += f" ({label})"
            last["score"] = (st.score[1], st.score[0])
            return
        self.box.scoring.append({"qtr": st.qtr, "clock": st.clock if before_clock is None else before_clock,
                                 "team": team_idx, "text": label,
                                 "score": (st.score[1], st.score[0])})

    # ------------------------------------------------------------------
    # Kickoffs and tries
    # ------------------------------------------------------------------
    def _kickoff(self):
        st = self.state
        rng = self.rng
        kick_idx = self._kicking
        recv_idx = 1 - kick_idx
        kick, recv = self.teams[kick_idx], self.teams[recv_idx]
        before = st.copy()
        before.poss = kick_idx
        self._need_kickoff = False
        free_kick = self._safety_kick
        self._safety_kick = False
        onside = (not free_kick) and coach.wants_onside(st, kick_idx)
        res = P.kickoff(self, kick, recv, rng, onside=onside, free_kick=free_kick)
        from_yl = 80 if free_kick else 65
        msg = text.describe_kickoff(res, kick, recv, from_yl=from_yl)
        if free_kick:
            msg = msg.replace("kicks", "free kicks", 1)
        # Return-team penalty (holding / illegal block) on returns.
        pen = None
        if res.returner is not None and not res.touchback and not res.def_td and res.change_poss:
            pen = PEN.return_foul(rng, recv) or PEN.coverage_foul(rng, kick)
        self._tick(res.elapsed, recv_idx)
        st.clock_running = False
        st.ready_restart = False
        self.box.credit_kick(res, kick_idx)
        if res.def_td:
            st.poss = recv_idx
            self._open_drive(recv_idx, "Kickoff")
            self._set_result("Touchdown")
            self._score(recv_idx, 6, f"{text.short_name(res.returner)} {res.return_yards} yd kickoff return")
            self._ot_possession_ended(recv_idx)
            yield self._event("kickoff", msg, before, scoring=True, big=True)
            self._need_pat = True
            return
        if res.change_poss:
            new_yl = res.new_yl
            if pen is not None:
                new_yl, msg = self._return_penalty(pen, new_yl, msg, kick_idx, recv_idx)
            st.poss = recv_idx
            st.yl = new_yl
            st.down, st.togo = 1, min(10, st.yl)
            self._open_drive(recv_idx, "Kickoff")
            ev = self._event("kickoff", msg, before, big=res.fumble)
            yield ev
            return
        # Kicking team keeps it (onside recovery or a fumbled return).
        st.poss = kick_idx
        st.yl = res.new_yl
        st.down, st.togo = 1, min(10, st.yl)
        self._open_drive(kick_idx, "Onside kick" if res.kind == "onside" else "Fumble")
        yield self._event("kickoff", msg, before, big=True)

    def _pat(self):
        st = self.state
        rng = self.rng
        self._need_pat = False
        off_idx = st.poss
        off, deff = self.teams[off_idx], self.teams[1 - off_idx]
        before = st.copy()
        if self.overtime and self._ot_over() and st.score[off_idx] > st.score[1 - off_idx]:
            yield from self._final()          # the touchdown already won it: no try
            return
        if coach.go_for_two(rng, st, off_idx):
            st.yl, st.down, st.togo = 2, 1, 2
            try_state = st.copy()
            call = coach.call_offense(rng, st, off_idx, off, deff)
            if call.kind in ("kneel", "spike", "sneak"):
                call.kind = "pass"
                call.concept = "quick"
            call.package = "11 personnel" if call.kind == "pass" else "12 personnel"
            dcall = coach.call_defense(rng, st, 1 - off_idx, deff, call)
            call.lineup = off.lineup(call.package)
            dcall.lineup = deff.lineup(dcall.package)
            if call.kind == "pass":
                res = P.pass_play(self, off, deff, call, dcall, rng)
            else:
                res = P.run_play(self, off, deff, call, dcall, rng)
            good = res.td or (res.kind in ("run", "pass", "scramble", "sneak") and res.yards >= 2
                              and not res.interception and not res.fumble_lost)
            desc = text.describe_two_point(res, off, deff)
            self._score(off_idx, 2 if good else 0,
                        f"two-point {'pass' if res.kind == 'pass' else 'run'} {'good' if good else 'failed'}",
                        merge=True)
            msg = f"TWO-POINT CONVERSION ATTEMPT. {desc}. ATTEMPT {'SUCCEEDS' if good else 'FAILS'}."
            self._detail = text.detail(res, call, dcall)
            yield self._event("two_point", msg, try_state, scoring=good)
            self._detail = ""
        else:
            res = P.extra_point(self, off, rng)
            self.box.credit_kick(res, off_idx)
            kicker = text.short_name(res.kicker)
            self._score(off_idx, 1 if res.made else 0,
                        f"{kicker} kick" if res.made else ("kick blocked" if res.blocked else "kick failed"),
                        merge=True)
            yield self._event("xp", text.describe_xp(res), before, scoring=res.made)
        self._kicking = off_idx
        self._need_kickoff = True
        if self.overtime and self._ot_over():
            yield from self._final()

    # ------------------------------------------------------------------
    # Overtime
    # ------------------------------------------------------------------
    def _ot_possession_ended(self, team_idx):
        if self.overtime:
            self._ot_poss.append(team_idx)

    def _ot_over(self):
        """Regular-season overtime (2025 rules): both teams get a possession;
        after that, the next score wins. A tie stands if time runs out."""
        st = self.state
        if not self.overtime:
            return False
        both = len(set(self._ot_poss)) >= 2
        if both and st.score[0] != st.score[1]:
            return True
        return False

    # ------------------------------------------------------------------
    # Scrimmage plays
    # ------------------------------------------------------------------
    def _snap(self):
        st = self.state
        rng = self.rng
        off_idx = st.poss
        def_idx = 1 - off_idx
        off, deff = self.teams[off_idx], self.teams[def_idx]
        tempo = coach.tempo_for(st, off_idx)

        # Defense uses a timeout to save time when it's behind late.
        if self._defense_timeout(off_idx, def_idx):
            deff.timeouts -= 1
            st.clock_running = False
            st.ready_restart = False
            yield self._note(f"Timeout #{3 - deff.timeouts if st.qtr < 5 else 2 - deff.timeouts} by "
                             f"{deff.abbrev} at {text.clock_text(st.clock)}.", kind="timeout")
            return
        # Offense timeout in a two-minute drill.
        if self._offense_timeout(off_idx):
            off.timeouts -= 1
            st.clock_running = False
            st.ready_restart = False
            yield self._note(f"Timeout #{3 - off.timeouts if st.qtr < 5 else 2 - off.timeouts} by "
                             f"{off.abbrev} at {text.clock_text(st.clock)}.", kind="timeout")
            return

        runoff = self._runoff(tempo, off_idx)
        urgent_kick = self._kick_now(off_idx, off) == "urgent"
        if urgent_kick and runoff > 0 and st.clock > 3:
            # Field goal unit sprints on with the clock running.
            runoff = min(runoff, 6.0 + self.rng.random() * 6.0, st.clock - 1.0)
        if runoff > 0:
            if st.qtr in (2, 4) and st.qtr not in st.warned and st.clock > 120 and st.clock - runoff <= 120:
                self._tick(st.clock - 120, off_idx)
                st.warned.add(st.qtr)
                st.clock_running = False
                st.ready_restart = False
                yield self._note("Two-minute warning.", kind="quarter")
                return
            if runoff >= st.clock:
                self._tick(st.clock, off_idx)
                return
            self._tick(runoff, off_idx)
        st.ready_restart = False

        # What are we doing on this snap?
        decision = self._special_decision(off_idx, off, deff)
        if decision == "punt":
            yield from self._punt(off_idx)
            return
        if decision == "field_goal":
            yield from self._field_goal(off_idx)
            return

        if decision == "kneel":
            call = coach.OffCall(kind="kneel", package="11 personnel", tempo="milk")
        elif decision == "spike":
            call = coach.OffCall(kind="spike", package="11 personnel", tempo="hurry")
        elif decision == "hail_mary":
            call = coach.OffCall(kind="pass", package="10 personnel", concept="hail_mary", tempo="hurry")
        else:
            call = coach.call_offense(rng, st, off_idx, off, deff)
        dcall = coach.call_defense(rng, st, def_idx, deff, call)
        short = st.yl <= 3 or (st.togo <= 1 and st.down >= 3)
        # Passing situations bring in the 3rd-down back (the situation, not the
        # play call: the offense doesn't tip its hand by personnel): 3rd/4th and
        # 4+, 2nd and long, the two-minute drill, two scores down late.
        lead = st.score[off_idx] - st.score[def_idx]
        passing = ((st.down >= 3 and st.togo >= 4) or (st.down == 2 and st.togo >= T.THIRD_DOWN_BACK_2ND_TOGO)
                   or call.tempo == "hurry" or (st.qtr >= 4 and lead <= -9))
        call.lineup = off.lineup(call.package, short, passing)
        dcall.lineup = deff.lineup(dcall.package, short)
        if call.lineup.get("QB") is None:
            call.lineup["QB"] = off.special("QB", set(p.id for p in call.lineup.values() if p))
        dcall.loaded = coach.load_box(rng, st, off, call, dcall, getattr(self, "box", None))
        before = st.copy()
        if self._drive is None:
            self._open_drive(off_idx, "Start")
        shotgun = call.kind == "pass" and call.concept != "play_action" and rng.random() < 0.85

        # Pre-snap penalties
        if call.kind not in ("kneel", "spike"):
            pen = PEN.pre_snap(self, off, deff, call.lineup, dcall.lineup, rng)
            if pen is not None:
                yield from self._apply_presnap(pen, off_idx, before)
                return

        res = self._resolve(call, dcall, off, deff)
        P.marked_short(st, res, rng)
        res.on_field_off = {p.id for p in call.lineup.values() if p}
        res.on_field_def = {p.id for p in dcall.lineup.values() if p}
        live = None
        if call.kind not in ("kneel", "spike"):
            live = res.penalty or PEN.live(self, off, deff, res, call, dcall, rng)
        self._detail = text.detail(res, call, dcall, shotgun)
        yield from self._apply_play(res, live, off_idx, before, call, shotgun)
        self._detail = ""

    def _resolve(self, call, dcall, off, deff):
        rng = self.rng
        st = self.state
        if call.kind == "kneel":
            r = P.PlayResult("kneel")
            r.rusher = call.lineup["QB"]
            r.yards = -1 if st.yl < 99 else 0
            r.elapsed = 2
            return r
        if call.kind == "spike":
            r = P.PlayResult("spike")
            r.passer = call.lineup["QB"]
            r.elapsed = 1
            return r
        if call.kind == "sneak":
            return P.sneak_play(self, off, deff, call, dcall, rng)
        if call.kind == "pass":
            return P.pass_play(self, off, deff, call, dcall, rng)
        return P.run_play(self, off, deff, call, dcall, rng)

    # ------------------------------------------------------------------
    def _special_decision(self, off_idx, off, deff):
        """Kneel, spike, punt, field goal, Hail Mary, or a normal play (None)."""
        st = self.state
        rng = self.rng
        diff = coach.score_diff(st, off_idx)
        hs = coach.half_seconds(st)
        kicker = off.special("K")
        max_fg = coach.fg_range(off, kicker, self.weather)

        # Victory formation / run out the half.
        if diff > 0 and st.qtr >= 4 and self._can_kneel_out(off_idx):
            return "kneel"
        if (st.qtr == 2 and hs <= 30 and st.yl >= 60 and diff >= -3 and st.clock_running
                and (deff.timeouts == 0 or hs <= 20)):
            return "kneel"
        if st.qtr == 4 and diff == 0 and hs <= 25 and st.yl >= 70 and st.clock_running:
            return "kneel"

        # Time running out and a field goal ties, wins or ends the half.
        if self._kick_now(off_idx, off, max_fg):
            return "field_goal"
        # Last seconds of a half.
        if st.qtr in (2, 4, 5) and hs <= 6:
            fg_dist = st.yl + 17
            need_td = st.qtr != 2 and diff < -3
            if not need_td and fg_dist <= min(67, max_fg + (4 if st.qtr == 2 else 2)) and not (st.qtr >= 4 and diff > 0):
                return "field_goal"
            if st.yl <= 62:
                return "hail_mary"
            if st.qtr == 2:
                return "kneel" if (st.down < 4 or hs <= 2) else "punt"
        # Spike to stop the clock.
        if (st.clock_running and st.down < 4 and coach.tempo_for(st, off_idx) == "hurry" and hs <= 40
                and off.timeouts == 0 and self._last_play_inbounds and st.down <= 3 and rng.random() < 0.65):
            return "spike"
        if st.down == 4:
            return coach.fourth_down(rng, st, off_idx, off, max_fg)
        return None

    def _kick_now(self, off_idx, off, max_fg=None):
        """End of a half (or a tied/close game late): kick the field goal now
        rather than risk the clock running out. Returns "urgent" when the
        clock is running with no timeouts left, True to kick, False otherwise."""
        st = self.state
        if st.qtr not in (2, 4, 5):
            return False
        hs = coach.half_seconds(st)
        if hs > 24:
            return False
        diff = coach.score_diff(st, off_idx)
        if st.qtr >= 4 and not (-3 <= diff <= 0):
            return False
        if max_fg is None:
            max_fg = coach.fg_range(off, off.special("K"), self.weather)
        if st.yl + 17 > min(67, max_fg + (4 if st.qtr == 2 else 2)):
            return False
        if st.clock_running and off.timeouts == 0 and hs <= 22:
            return "urgent"
        if st.down < 4 and off.timeouts > 0 and hs > T.FG_KICK_NOW_SECONDS:
            return False         # a timeout left: run another play to get closer, then stop the clock and kick
        if not st.clock_running and hs <= 16:
            return True
        return False

    def _can_kneel_out(self, off_idx):
        """Can the offense kneel until the clock hits zero? Each kneel takes
        about 2 seconds; between kneels about 40 seconds run off, unless the
        defense stops the clock with a timeout (or the two-minute warning)."""
        st = self.state
        if st.qtr < 4:
            return False
        opp_to = self.teams[1 - off_idx].timeouts
        if st.qtr == 4 and 4 not in st.warned and st.clock > 120:
            opp_to += 1
        kneels = 5 - st.down
        runoffs = max(0, (4 - st.down) - opp_to)
        burn = 2.0 * kneels + 39.0 * runoffs
        return st.clock <= burn

    def _defense_timeout(self, off_idx, def_idx):
        st = self.state
        deff = self.teams[def_idx]
        if deff.timeouts <= 0:
            return False
        rng = self.rng
        if not st.clock_running:
            # Occasional timeout to avoid a bad matchup or get a call in.
            if st.down >= 3 and rng.random() < 0.006:
                return True
            return False
        diff_def = coach.score_diff(st, def_idx)
        if st.qtr >= 4 and st.clock > 3:
            if -8 <= diff_def < 0 and st.clock <= 170:
                return True
            if -16 <= diff_def < -8 and st.clock <= 300:
                return True
            if diff_def == 0 and st.clock <= 60 and st.yl > 40:
                return True
        # Before halftime: stop the clock to get the ball back with time left.
        if st.qtr == 2 and 20 < st.clock <= 125 and st.yl >= 45 and coach.tempo_for(st, off_idx) != "hurry":
            return rng.random() < 0.5
        if rng.random() < 0.004:
            return True
        return False

    def _offense_timeout(self, off_idx):
        st = self.state
        off = self.teams[off_idx]
        if off.timeouts <= 0:
            return False
        rng = self.rng
        diff = coach.score_diff(st, off_idx)
        hs = coach.half_seconds(st)
        late = (st.qtr == 2 and hs <= 120) or (st.qtr >= 4 and hs <= 300)
        if not late and rng.random() < 0.017:
            return True          # play clock running down / a bad look
        if not st.clock_running:
            return False
        max_fg = coach.fg_range(off, off.special("K"), self.weather)
        in_range = st.yl + 17 <= max_fg
        if st.qtr == 2 and hs <= 120 and coach.tempo_for(st, off_idx) == "hurry" and st.yl <= 70:
            if in_range and hs <= 24:
                return True
            if hs <= 60 and st.yl <= 60:
                return True
            return off.timeouts > 1 and rng.random() < 0.3
        if st.qtr >= 4 and diff <= 0 and hs <= 120 and coach.tempo_for(st, off_idx) == "hurry":
            if in_range and diff >= -3 and hs <= 24:
                return True              # stop the clock to set up the kick
            keep = 1 if in_range else 0
            return off.timeouts > keep
        return False

    # ------------------------------------------------------------------
    def _apply_presnap(self, pen, off_idx, before):
        st = self.state
        off, deff = self.teams[off_idx], self.teams[1 - off_idx]
        yards = pen.yards
        if pen.side == "off":
            yards = min(yards, (100 - st.yl) // 2) if st.yl + yards >= 100 else yards
            st.yl += yards
            st.togo += yards
            self.box.credit_penalty(pen, off_idx)
        else:
            yards = min(yards, max(1, st.yl // 2)) if st.yl - yards <= 0 else yards
            st.yl -= yards
            st.togo -= yards
            self.box.credit_penalty(pen, 1 - off_idx)
            if st.togo <= 0:
                st.down, st.togo = 1, min(10, st.yl)
                self.box.team[off_idx]["fd_pen"] += 1
        st.togo = max(1, min(st.togo, st.yl))
        pen.yards = yards
        st.clock_running = False
        st.ready_restart = not self._late_window()
        msg = text.describe_penalty(pen, before, off, deff)
        yield self._event("penalty", msg, before)

    def _apply_play(self, res, pen, off_idx, before, call, shotgun):
        st = self.state
        rng = self.rng
        off, deff = self.teams[off_idx], self.teams[1 - off_idx]
        def_idx = 1 - off_idx

        # --- Should the penalty be accepted? ---
        accepted = False
        if pen is not None:
            accepted = self._accept(pen, res, before, off_idx)
        self._tick(res.elapsed, off_idx)
        if self._drive is not None:
            self._drive["plays"] += 1

        if pen is not None and accepted and pen.timing in ("prev", "spot", "down"):
            yield from self._enforce_erasing(pen, res, before, off_idx)
            self._after_snap(res, off_idx)
            return

        # The play stands.
        play_desc = text.describe(res, before, off, deff, shotgun=shotgun)
        gained = res.yards
        new_yl = st.yl - gained
        scoring = False
        big = False
        msg_extra = ""
        self.box.snaps(res.on_field_off, off_idx, "off_snaps")
        self.box.snaps(res.on_field_def, def_idx, "def_snaps")

        if res.td:
            res.first_down = True
        elif not res.change_poss and not res.safety and res.kind not in ("spike",):
            if gained >= st.togo:
                res.first_down = True

        self.box.credit(res, off_idx, before)
        if self._drive is not None and res.kind not in ("spike", "kneel"):
            self._drive["yards"] += gained
        if res.kind in ("pass", "scramble", "run", "sneak") and gained >= 20:
            big = True

        # Penalty that stands with the play (enforced from the end of the play)
        end_pen = pen is not None and accepted and pen.timing == "end"
        if pen is not None and not accepted:
            msg_extra = " " + text.describe_penalty(pen, before, off, deff, declined=True)

        # --- Outcomes ---
        if res.td:
            self._set_result("Touchdown")
            who = res.receiver if res.kind == "pass" else res.rusher
            if res.kind == "pass":
                label = f"{text.short_name(who)} {res.yards} yd pass from {text.short_name(res.passer)}"
            else:
                label = f"{text.short_name(who)} {res.yards} yd run"
            self._score(off_idx, 6, label, before.clock)
            self._ot_possession_ended(off_idx)
            scoring = big = True
            self._need_pat = True
            st.clock_running = False
            yield self._event("play", play_desc + msg_extra, before, gained, scoring, big)
            self._after_snap(res, off_idx)
            return
        if res.safety:
            self._set_result("Safety")
            self._score(def_idx, 2, f"Safety, {text.short_name(res.passer if res.kind == 'sack' else res.rusher)} tackled in the end zone", before.clock)
            yield self._event("play", play_desc + msg_extra, before, gained, True, True)
            self._ot_possession_ended(off_idx)
            self._safety_kick = True
            self._kicking = off_idx
            self._need_kickoff = True
            st.clock_running = False
            self._after_snap(res, off_idx)
            if self.overtime:
                yield from self._final()
            return
        if res.change_poss:
            self._ot_possession_ended(off_idx)
            if res.def_td:
                self._set_result("Turnover")
                kind = "interception" if res.interception else "fumble"
                scorer = res.interceptor if res.interception else res.recovered_by
                self._score(def_idx, 6, f"{text.short_name(scorer)} {res.return_yards} yd {kind} return", before.clock)
                self._ot_possession_ended(def_idx)     # a defensive score counts as their possession
                st.poss = def_idx
                st.clock_running = False
                yield self._event("play", play_desc + msg_extra, before, gained, True, True)
                self._open_drive(def_idx, "Turnover")
                self._set_result("Touchdown")
                self._need_pat = True
                self._after_snap(res, off_idx)
                if self.overtime and self._ot_over():
                    yield from self._final()
                return
            self._set_result("Turnover")
            st.poss = def_idx
            st.yl = res.new_yl
            st.down, st.togo = 1, min(10, st.yl)
            st.clock_running = False
            yield self._event("play", play_desc + msg_extra, before, gained, False, True)
            self._open_drive(def_idx, "Turnover")
            self._after_snap(res, off_idx)
            if self.overtime and self._ot_over():
                yield from self._final()
            return

        # Normal down advance
        st.yl = new_yl
        off_end_yards = 0
        if end_pen and pen.side == "def":
            yds = pen.yards if st.yl - pen.yards > 0 else max(1, st.yl // 2)
            pen.yards = yds
            st.yl -= yds
            self.box.credit_penalty(pen, def_idx)
            msg_extra = " " + text.describe_penalty(pen, before, off, deff)
            if not res.first_down:
                self.box.team[off_idx]["fd_pen"] += 1
            res.first_down = True
        elif end_pen:
            yds = pen.yards if st.yl + pen.yards < 100 else (100 - st.yl) // 2
            pen.yards = yds
            off_end_yards = yds
            self.box.credit_penalty(pen, off_idx)
            msg_extra = " " + text.describe_penalty(pen, before, off, deff)
        if res.first_down:
            st.down = 1
            st.togo = min(10, st.yl)
        else:
            st.down += 1
            st.togo = max(1, st.togo - gained)
            if st.togo > st.yl:
                st.togo = st.yl
        if off_end_yards:
            st.yl += off_end_yards
            st.togo += off_end_yards
        if self._drive is not None and st.yl <= 20:
            self._drive["red_zone"] = True
        if st.down > 4:
            # Turnover on downs
            self._set_result("Downs")
            self._ot_possession_ended(off_idx)
            st.poss = def_idx
            st.yl = 100 - st.yl
            st.down, st.togo = 1, min(10, st.yl)
            st.clock_running = False
            yield self._event("play", play_desc + msg_extra + " Turnover on downs.", before, gained, False, True)
            self._open_drive(def_idx, "Downs")
            self._after_snap(res, off_idx)
            if self.overtime and self._ot_over():
                yield from self._final()
            return
        # Clock status for the next snap
        if res.kind in ("spike",) or (res.kind == "pass" and not res.complete):
            st.clock_running = False
            st.ready_restart = False
        elif res.oob:
            st.clock_running = False
            st.ready_restart = not self._late_window()
        elif end_pen:
            st.clock_running = False
            st.ready_restart = not self._late_window()
        else:
            st.clock_running = True
        self._last_play_inbounds = st.clock_running
        yield self._event("play", play_desc + msg_extra, before, gained, False, big or res.fumble)
        self._after_snap(res, off_idx)

    def _after_snap(self, res, off_idx):
        """Fatigue, injuries."""
        off, deff = self.teams[off_idx], self.teams[1 - off_idx]
        on_o = res.on_field_off
        on_d = res.on_field_def
        if res.rusher is not None and res.kind in ("run", "sneak"):
            off.carries[res.rusher.id] += 1
        off.after_play(on_o)
        deff.after_play(on_d)
        self._injuries(res, off, deff)

    def _injuries(self, res, off, deff):
        rng = self.rng
        if res.kind in ("kneel", "spike"):
            return
        contact = []
        for p in res.contact_players(rng):
            contact.append(p)
        for team, pool in ((off, res.on_field_off), (deff, res.on_field_def)):
            ids = [pid for pid in pool if team.by_id.get(pid) is not None]
            if ids and rng.random() < T.INJURY_RANDOM_CONTACT:
                contact.append(team.by_id[ids[int(rng.random() * len(ids))]])
        carriers = {id(x) for x in (res.rusher, res.receiver) if x is not None}
        for p in contact:
            rate = T.INJURY_RATE
            if p.position == "QB":
                rate *= T.INJURY_QB_MULT
            elif id(p) in carriers:
                rate *= T.INJURY_CARRIER_MULT["RB" if p.position in ("RB", "FB") else "other"]
            # His body: durable players get hurt less often; worn-down players more.
            rate *= math.exp(-T.DURABILITY_K * ((p.durability if p.durability is not None else 50) - 50) / 15)
            team_ = off if p.id in off.by_id else deff
            over = team_.fatigue[p.id] - team_.fatigue_limit(p)
            if over > 0:
                rate *= 1 + T.FATIGUE_INJURY_K * over
            if rng.random() < rate:
                team = off if p.id in off.by_id else deff
                if p.id in team.injured or p.id in team.out:
                    continue
                self._injure(team, p)

    def _injure(self, team, p):
        rng = self.rng
        # Durable players more often shake it off or miss less time.
        dur = p.durability if p.durability is not None else 50
        r = min(0.999, max(0.0, rng.random() - T.DURABILITY_SEVERITY * (dur - 50) / 15))
        u_kind = rng.random()       # which injury (engine/injuries.py)
        if r < T.INJURY_SHAKEN_SHARE:
            team.injured[p.id] = 3 + int(rng.random() * 10)
            weeks = 0
            kind = injuries.pick_kind("shaken", u_kind)
        else:
            # How long, then which injury: both from real NFL injury data (injuries.py).
            team.injured[p.id] = None
            grp, lo, hi = injuries.length_group((r - T.INJURY_SHAKEN_SHARE) / (1 - T.INJURY_SHAKEN_SHARE))
            weeks = lo + int(rng.random() * (hi - lo + 1))
            kind = injuries.pick_kind(grp, u_kind)
        what = injuries.name(kind)
        if weeks == 0:
            msg = f"{team.abbrev}-{text.short_name(p)} was shaken up on the play ({what}) and will miss a few snaps."
        else:
            msg = f"{team.abbrev}-{text.short_name(p)} was injured on the play ({what}) and is out for the game."
        team.injuries.append((p.id, weeks, kind))
        self.log.append(Event(kind="injury", text=msg, qtr=self.state.qtr, clock=self.state.clock,
                              poss=self.state.poss, score=tuple(self.state.score), drive=self.drive_no,
                              after=self.state.copy()))

    # ------------------------------------------------------------------
    def _accept(self, pen, res, before, off_idx):
        """Does the team that was fouled accept the penalty?"""
        st = before
        if pen.timing == "end":
            return True             # added on after the play: no reason to decline
        ep = PEN.expected_points
        # Value of the play as it happened (offense's view)
        if res.td:
            play_val = 6.95
        elif res.safety:
            play_val = -2.0
        elif res.change_poss:
            if res.def_td:
                play_val = -6.95
            else:
                play_val = -ep(1, 10, res.new_yl if res.new_yl is not None else 75)
        else:
            new_yl = st.yl - res.yards
            if res.yards >= st.togo:
                play_val = ep(1, min(10, new_yl), new_yl)
            elif st.down >= 4:
                play_val = -ep(1, 10, 100 - new_yl)
            else:
                play_val = ep(st.down + 1, st.togo - res.yards, new_yl)
        # Value with the penalty
        if pen.side == "off":
            if pen.timing == "down":
                y = st.yl + pen.yards
                pen_val = ep(st.down + 1, st.togo + pen.yards, y) if st.down < 4 else -ep(1, 10, 100 - y)
            else:
                yards = min(pen.yards, (100 - st.yl) // 2) if st.yl + pen.yards >= 100 else pen.yards
                pen_val = ep(st.down, st.togo + yards, st.yl + yards)
            return pen_val < play_val        # defense accepts if it hurts the offense more
        # Defensive foul: offense decides
        if pen.timing == "spot":
            y = max(1, st.yl - pen.yards)
        else:
            y = st.yl - (min(pen.yards, max(1, st.yl // 2)) if st.yl - pen.yards <= 0 else pen.yards)
        pen_val = ep(1, min(10, y), y) if pen.auto_first else ep(st.down, max(1, st.togo - pen.yards), y)
        return pen_val > play_val

    def _enforce_erasing(self, pen, res, before, off_idx):
        """Penalty accepted: the play doesn't count; move the ball."""
        st = self.state
        off, deff = self.teams[off_idx], self.teams[1 - off_idx]
        st.yl, st.down, st.togo = before.yl, before.down, before.togo
        if pen.side == "off":
            yards = pen.yards
            if st.yl + yards >= 100:
                yards = (100 - st.yl) // 2
            pen.yards = yards
            st.yl += yards
            st.togo += yards
            if pen.timing == "down":
                st.down += 1
            self.box.credit_penalty(pen, off_idx)
        else:
            if pen.timing == "spot":
                yards = min(pen.yards, st.yl - 1)
                if before.yl - pen.yards <= 0:
                    yards = st.yl - 1
            else:
                yards = pen.yards if st.yl - pen.yards > 0 else max(1, st.yl // 2)
            pen.yards = yards
            st.yl -= yards
            self.box.credit_penalty(pen, 1 - off_idx)
            if pen.auto_first or yards >= st.togo:
                st.down, st.togo = 1, min(10, st.yl)
                self.box.team[off_idx]["fd_pen"] += 1
            else:
                st.togo -= yards
        st.togo = max(1, min(st.togo, st.yl))
        msg = text.describe_penalty(pen, before, off, deff)
        st.clock_running = False
        st.ready_restart = not self._late_window()
        if st.down > 4:
            self._set_result("Downs")
            self._ot_possession_ended(off_idx)
            st.poss = 1 - off_idx
            st.yl = 100 - st.yl
            st.down, st.togo = 1, min(10, st.yl)
            msg += " Turnover on downs."
            self._open_drive(1 - off_idx, "Downs")
        if st.yl >= 100:
            # Foul in the end zone: safety
            self._set_result("Safety")
            self._score(1 - off_idx, 2, "Safety, penalty in the end zone")
            self._safety_kick = True
            self._kicking = off_idx
            self._need_kickoff = True
        yield self._event("penalty", msg, before)

    # ------------------------------------------------------------------
    def _punt(self, off_idx):
        st = self.state
        rng = self.rng
        kick, recv = self.teams[off_idx], self.teams[1 - off_idx]
        before = st.copy()
        if self._drive is not None:
            self._drive["plays"] += 1
        res = P.punt(self, kick, recv, rng)
        self._tick(res.elapsed, off_idx)
        msg = text.describe_punt(res, before, kick, recv)
        self.box.credit_kick(res, off_idx)
        st.clock_running = False
        st.ready_restart = False
        self._set_result("Punt")
        self._ot_possession_ended(off_idx)
        if res.safety:
            self._score(1 - off_idx, 2, "Safety, bad snap through the end zone")
            self._safety_kick = True
            self._kicking = off_idx
            self._need_kickoff = True
            yield self._event("punt", msg, before, scoring=True, big=True)
            return
        if res.def_td:
            st.poss = 1 - off_idx
            self._open_drive(1 - off_idx, "Punt")
            self._set_result("Touchdown")
            label = "blocked punt return" if res.blocked else "punt return"
            who = res.returner if not res.blocked else None
            self._score(1 - off_idx, 6, f"{text.short_name(who) + ' ' if who else ''}{res.return_yards} yd {label}" if who else label)
            self._ot_possession_ended(1 - off_idx)
            self._need_pat = True
            yield self._event("punt", msg, before, scoring=True, big=True)
            return
        pen = None
        if res.returner is not None and res.return_yards and res.change_poss:
            pen = PEN.return_foul(rng, recv) or PEN.coverage_foul(rng, kick)
        if not res.change_poss:
            # Muffed punt recovered by the kicking team
            st.yl = res.new_yl
            st.down, st.togo = 1, min(10, st.yl)
            self._open_drive(off_idx, "Muffed punt")
            yield self._event("punt", msg, before, big=True)
            return
        st.poss = 1 - off_idx
        st.yl = res.new_yl
        if pen is not None:
            st.yl, msg = self._return_penalty(pen, st.yl, msg, off_idx, 1 - off_idx)
        st.down, st.togo = 1, min(10, st.yl)
        self._open_drive(1 - off_idx, "Punt")
        yield self._event("punt", msg, before, big=res.blocked)
        if self.overtime and self._ot_over():
            yield from self._final()

    def _return_penalty(self, pen, new_yl, msg, kick_idx, recv_idx):
        """Enforce a foul during a kick return. new_yl is the receiving team's
        distance to the goal it now attacks."""
        if pen.side == "ret":
            yards = pen.yards if new_yl + pen.yards < 100 else (100 - new_yl) // 2
            pen.yards = yards
            new_yl += yards
            team, idx = self.teams[recv_idx], recv_idx
        else:
            yards = pen.yards if new_yl - pen.yards > 0 else max(1, new_yl // 2)
            pen.yards = yards
            new_yl -= yards
            team, idx = self.teams[kick_idx], kick_idx
        self.box.credit_penalty(pen, idx)
        who = f"{team.abbrev}-{text.short_name(pen.player)}" if pen.player is not None else team.abbrev
        msg += f" PENALTY on {who}, {pen.name}, {yards} yards."
        return new_yl, msg

    def _field_goal(self, off_idx):
        st = self.state
        rng = self.rng
        kick, deff = self.teams[off_idx], self.teams[1 - off_idx]
        before = st.copy()
        if self._drive is not None:
            self._drive["plays"] += 1
        res = P.field_goal(self, kick, deff, rng)
        self._tick(res.elapsed, off_idx)
        msg = text.describe_fg(res, kick)
        self.box.credit_kick(res, off_idx)
        st.clock_running = False
        st.ready_restart = False
        if res.made:
            self._set_result("Field goal")
            self._score(off_idx, 3, f"{text.short_name(res.kicker)} {res.kick_distance} yd field goal",
                        before.clock)
            self._ot_possession_ended(off_idx)
            yield self._event("fg", msg, before, scoring=True, big=True)
            self._kicking = off_idx
            self._need_kickoff = True
            if self.overtime and self._ot_over():
                yield from self._final()
            return
        self._set_result("Missed FG" if not res.blocked else "Blocked FG")
        self._ot_possession_ended(off_idx)
        if res.def_td:
            st.poss = 1 - off_idx
            self._score(1 - off_idx, 6, "Blocked field goal return")
            self._ot_possession_ended(1 - off_idx)
            self._open_drive(1 - off_idx, "Blocked FG")
            self._set_result("Touchdown")
            self._need_pat = True
            yield self._event("fg", msg, before, scoring=True, big=True)
            return
        st.poss = 1 - off_idx
        st.yl = res.new_yl
        st.down, st.togo = 1, min(10, st.yl)
        self._open_drive(1 - off_idx, "Missed FG")
        yield self._event("fg", msg, before, big=True)
        if self.overtime and self._ot_over():
            yield from self._final()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    @property
    def home(self):
        return self.teams[0]

    @property
    def away(self):
        return self.teams[1]

    def injuries(self):
        """{team id: [(player id, weeks out, description)]} from this game."""
        return {t.id: list(t.injuries) for t in self.teams}


def simulate_game(league, home_id, away_id, seed=None, **kw):
    """Simulate a game to the final whistle and return the finished Game."""
    return Game(league, home_id, away_id, seed=seed, **kw).run()
