# tools/lab.py
# The league lab: plays leagues through the game's own code, season after
# season, for every check tool. A lab league is made the way New Game makes
# one (engine.league.create_league + season.start_season: contracts, coaching
# staffs, training camp at 90), with no team of yours (every team is run by
# the AI). Each season goes through season.play_week week by week (preseason,
# final cuts, regular season, playoffs: injuries, roster moves, waivers,
# trades, awards, money every week), then the offseason phase by phase
# through season.begin_offseason / advance_offseason, exactly as the Next
# button plays it, ending in training camp and the new season's schedule.
#
# Two ways to play the games:
#   real  the game sim (engine/sim), as in the game. About 25-35 s a season.
#   fast  a made-up result instead of each game (FakeGame below): scores from
#         the teams' strength, injuries at the real rate, snaps by depth chart
#         role. Everything around the games still runs for real. For checks of
#         the season loop, money, rosters, the offseason and careers, not of
#         game stats.
#
# Checks attach to moments with lab.on(event, fn); fn(lab, **info):
#   "season_start"       the league is set (new league, or the new season's
#                        schedule after training camp); the preseason is next
#   "week_end"           after each play_week (info: label = the week played)
#   "regular_season"     the preseason is over: final cuts done, week 1 is next
#   "season_end"         the playoffs are over, before the offseason starts
#   "offseason_start"    after season.begin_offseason (retirements, the draft
#                        class, GM changes, the new league year)
#   "phase_before"       before each offseason phase plays (info: phase, wave)
#   "phase_after"        after it (info: phase, wave = the phase just played)
#
#   from lab import Lab
#   lab = Lab(101)                      # fast games
#   lab.on("phase_after", lambda lab, phase, wave: ...)
#   lab.run(seasons=3)                  # 3 x (season, offseason)
#
# Nothing is saved; your saves are never touched. A given seed is always the
# same league and plays out the same (engine dice are keyed by the league).

import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import depth, injuries                   # noqa: E402
from engine import season as SEASON                  # noqa: E402
from engine.league import create_league              # noqa: E402

# ---- Fast games --------------------------------------------------------------
GAME_COSTING_PER_TEAM_GAME = 1.5   # real: about 820 game-costing injuries a regular season (injuries.py),
                                   # over 544 team-games
KNOCKS_PER_TEAM_GAME = 1.0         # knocks that cost no games (listed Questionable now and then)
STARTER_INJURY_WEIGHT = 1.6        # starters play more snaps, so get hurt more (tools/draft_lab.py)
HOME_EDGE_PTS = 1.5
STRENGTH_PTS = 4.0                 # points of expected margin per spread of team strength (real teams' strength
                                   # spreads about 6 points a game, 1 sd: CLAUDE.md, Step 7)
MARGIN_SD = 13.0                   # real NFL game margins scatter about 13-14 points around expectation
TOTAL_MEAN, TOTAL_SD = 45.0, 10.0
PLAYS = 62                         # offensive plays a team-game (real 62.4)
SNAP_SHARE = {"starter": 0.9, "backup": 0.3, "other": 0.05}


class _Box:
    def __init__(self):
        self.players, self.owner = {}, {}
        self.team = [{"plays": PLAYS}, {"plays": PLAYS}]
        self.quarter_points = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.scoring, self.drives = [], []


class _State:
    def __init__(self, score):
        self.score = score


class _Weather:
    def text(self):
        return "Clear"


class _Side:
    def __init__(self, tid):
        self.id = tid
        self.injuries = []


def _strength(league, tid, players):
    """A team's strength: its starters' ratings against the league's starters
    (z), the quarterback counted four times (tools/draft_lab.py)."""
    stat = league.__dict__.get("_lab_strength_stats")
    if stat is None or stat[0] != (league.season, league.stage, league.week):
        by = defaultdict(list)
        for t in league.teams:
            for pid in depth.starter_ids(league.depth_charts.get(t.id, {})):
                if pid in league.rosters:
                    p = league.player(pid)
                    by[p.position].append(p.overall())
        ms = {}
        for pos, v in by.items():
            m = sum(v) / len(v)
            ms[pos] = (m, math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)) or 1.0)
        stat = ((league.season, league.stage, league.week), ms)
        league.__dict__["_lab_strength_stats"] = stat
    ms = stat[1]
    chart = league.depth_charts.get(tid, {})
    ids = {p.id for p in players}
    zs = []
    for pid in depth.starter_ids(chart):
        if pid in ids:
            p = league.player(pid)
            m, sd = ms.get(p.position, (65.0, 8.0))
            zs += [(p.overall() - m) / sd] * (4 if p.position == "QB" else 1)
    return sum(zs) / max(1, len(zs)) if zs else -1.0


class FakeGame:
    """Stands in for engine.sim.game.Game in fast mode: the same constructor
    and what season.record_game reads (teams, state.score, box, injuries...)."""

    def __init__(self, league, home_id, away_id, seed=None, unavailable=None, extra=None, **_kw):
        self.league = league
        self.ids = (home_id, away_id)
        self.rng = random.Random(f"lab-game-{seed}")
        self.unavailable = unavailable or {}
        self.extra = extra or {}
        self.teams = (_Side(home_id), _Side(away_id))
        self.box = _Box()
        self.overtime = False
        self.weather = _Weather()
        self.state = None

    def run(self):
        lg, rng = self.league, self.rng
        dressed = []
        for idx, tid in enumerate(self.ids):
            out = {getattr(x, "id", x) for x in self.unavailable.get(tid, ())}
            players = [p for p in lg.team_players(tid) if p.id not in out] + list(self.extra.get(tid, ()))
            dressed.append(players)
        s = [_strength(lg, tid, ps) for tid, ps in zip(self.ids, dressed)]
        margin = HOME_EDGE_PTS + STRENGTH_PTS * (s[0] - s[1]) + rng.gauss(0, MARGIN_SD)
        total = max(6.0, rng.gauss(TOTAL_MEAN, TOTAL_SD))
        home = max(0, round((total + margin) / 2))
        away = max(0, round((total - margin) / 2))
        if home == away:
            home += 3 if rng.random() < 0.55 else 0
            away += 0 if home != away else 3
        self.state = _State([home, away])
        for idx, (tid, players) in enumerate(zip(self.ids, dressed)):
            chart = lg.depth_charts.get(tid, {})
            starters = depth.starter_ids(chart)
            backups = {ids[1] for ids in chart.values() if len(ids) > 1}
            weights = []
            for p in players:
                role = "starter" if p.id in starters else "backup" if p.id in backups else "other"
                snaps = round(PLAYS * SNAP_SHARE[role])
                unit = depth.unit_of_position(p.position)
                self.box.players[p.id] = {"off_snaps" if unit == "Offense" else "def_snaps": snaps} \
                    if unit != "Special teams" else {"st_snaps": snaps}
                self.box.owner[p.id] = idx
                weights.append(STARTER_INJURY_WEIGHT if role == "starter" else 1.0 if role == "backup" else 0.3)
            side = self.teams[idx]
            n_costly = _poisson(rng, GAME_COSTING_PER_TEAM_GAME)
            n_knock = _poisson(rng, KNOCKS_PER_TEAM_GAME)
            hurt = set()
            for k in range(n_costly + n_knock):
                if not players:
                    break
                p = rng.choices(players, weights=weights)[0]
                if p.id in hurt:
                    continue
                hurt.add(p.id)
                if k < n_costly:
                    grp, lo, hi = injuries.length_group(rng.random())
                    weeks = lo + int(rng.random() * (hi - lo + 1))
                    side.injuries.append((p.id, weeks, injuries.pick_kind(grp, rng.random())))
                else:
                    side.injuries.append((p.id, 0, injuries.pick_kind("shaken", rng.random())))
        return self

    def injuries(self):
        return {t.id: list(t.injuries) for t in self.teams}


def _poisson(rng, lam):
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


# ---- The lab -----------------------------------------------------------------

class Lab:
    """One league played through the game's own season and offseason (see the
    top of this file). games: "fast" or "real"."""

    def __init__(self, seed, games="fast", league=None):
        assert games in ("fast", "real")
        self.seed = seed
        self.games = games
        self.hooks = defaultdict(list)
        if league is None:
            league = create_league(seed=seed)
            league.name = f"league {seed}"
            league.user_team_id = None
            SEASON.start_season(league)
        self.league = league
        self.seasons_played = 0
        self._started = False

    def on(self, event, fn):
        self.hooks[event].append(fn)
        return self

    def emit(self, event, **info):
        for fn in self.hooks[event]:
            fn(self, **info)

    def _patch(self):
        """Fast games: FakeGame stands in for the sim inside season.new_game."""
        if self.games != "fast":
            return None
        saved = (SEASON.Game, SEASON.build_norms)
        SEASON.Game = FakeGame
        SEASON.build_norms = lambda league: None
        return saved

    def _unpatch(self, saved):
        if saved is not None:
            SEASON.Game, SEASON.build_norms = saved

    def play_season(self, until=None):
        """The preseason (camp, final cuts), regular season and playoffs.
        until="week1": stop when the preseason is over (a later call carries on)."""
        lg = self.league
        if not self._started:
            self._started = True
            self.emit("season_start")
        saved = self._patch()
        try:
            while not SEASON.season_over(lg):
                pre = SEASON.in_preseason(lg)
                label = SEASON.week_label(lg)
                SEASON.play_week(lg)
                self.emit("week_end", label=label)
                if pre and SEASON.in_regular_season(lg):
                    self.emit("regular_season")
                    if until == "week1":
                        return
        finally:
            self._unpatch(saved)
        self.emit("season_end")

    def play_offseason(self):
        """The offseason phase by phase, then training camp and the new schedule."""
        lg = self.league
        SEASON.begin_offseason(lg)
        self.emit("offseason_start")
        while SEASON.in_offseason(lg):
            st = lg.offseason or {}
            phase, wave = st.get("phase"), st.get("wave")
            self.emit("phase_before", phase=phase, wave=wave)
            SEASON.advance_offseason(lg)
            self.emit("phase_after", phase=phase, wave=wave)
        self.seasons_played += 1
        self.emit("season_start")

    def run(self, seasons=1, offseason_last=True):
        """seasons x (season, offseason); offseason_last=False stops after the last season."""
        for k in range(seasons):
            self.play_season()
            if offseason_last or k < seasons - 1:
                self.play_offseason()
        return self


def fingerprint(league):
    """A short code for the league's state (rosters, contracts, ratings): the same
    code means the same league (determinism checks)."""
    import hashlib
    state = (sorted(league.rosters.items()), sorted(getattr(league, "practice", {}).items()),
             sorted((pid, c["team"], c["apy"]) for pid, c in (getattr(league, "contracts", {}) or {}).items()),
             [(p.id, p.overall(), p.retired) for p in league.players])
    return hashlib.md5(repr(state).encode()).hexdigest()[:12]


if __name__ == "__main__":
    import time
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 101
    games = sys.argv[2] if len(sys.argv) > 2 else "fast"
    t0 = time.time()
    lab = Lab(seed, games)
    lab.on("regular_season", lambda lab: print(f"  week 1 of {lab.league.season}: "
                                               f"{len(lab.league.rosters)} on 53s ({time.time() - t0:.0f}s)"))
    lab.on("phase_after", lambda lab, phase, wave: print(f"    {phase} {wave if phase == 'fa' else ''} "
                                                         f"({time.time() - t0:.0f}s)"))
    lab.run(seasons=int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    print(f"done in {time.time() - t0:.0f}s; fingerprint {fingerprint(lab.league)}")
