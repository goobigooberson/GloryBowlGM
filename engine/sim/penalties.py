# penalties.py
# Penalties at real NFL rates (2023-2025), who commits them, and how they're
# enforced. Rates are per play; together they add up to about 6 flags for
# 50 yards per team per game, like the real league.

import math
from dataclasses import dataclass

from . import data
from . import tuning as T
from .plays import pick, natural

OL = ("LT", "LG", "C", "RG", "RT")
DL = ("LE", "LDT", "RDT", "RE")


@dataclass
class Penalty:
    name: str
    side: str            # "off" or "def" (relative to the offense on the play)
    player: object       # Player or None (team penalty)
    yards: int
    timing: str          # pre (dead ball), prev (from previous spot, play erased),
                         # spot (DPI at the spot of the foul), end (added after the play),
                         # down (loss of down at the spot: grounding)
    auto_first: bool = False
    accepted: bool = True
    team_abbrev: str = ""
    enforced_yl: int = 0


def _flag(rng, rate):
    return rng.random() < rate * T.PENALTY_SCALE


def _blocker(team, lineup, rng, weights_from="block_aware"):
    cands = [(s, lineup[s]) for s in OL if lineup.get(s) is not None]
    if not cands:
        return None
    w = [math.exp(-0.5 * team.z(p, s, weights_from)) for s, p in cands]
    return pick(rng, [p for _s, p in cands], w)


def pre_snap(g, off, deff, call_lineup, def_lineup, rng):
    away = not off.is_home
    fs_rate = 0.0168 * (T.AWAY_FALSE_START if away else 0.85)
    if _flag(rng, fs_rate):
        if rng.random() < 0.8:
            p = _blocker(off, call_lineup, rng)
        else:
            p = pick(rng, [call_lineup[s] for s in ("TE1", "WR1", "WR2", "WR3") if call_lineup.get(s)])
        return Penalty("False Start", "off", p, 5, "pre")
    if _flag(rng, 0.0041):
        return Penalty("Delay of Game", "off", None, 5, "pre")
    if _flag(rng, 0.0025):
        p = pick(rng, [call_lineup[s] for s in ("WR1", "WR2", "WR3", "TE1", "TE2") if call_lineup.get(s)])
        return Penalty("Illegal Formation", "off", p, 5, "pre")
    if _flag(rng, 0.0015):
        return Penalty("Illegal Shift", "off", None, 5, "pre")
    if _flag(rng, 0.0005):
        p = pick(rng, [call_lineup[s] for s in ("WR1", "WR2", "WR3", "TE1", "RB") if call_lineup.get(s)])
        return Penalty("Illegal Motion", "off", p, 5, "pre")
    if _flag(rng, 0.0008):
        return Penalty("Offensive Offside", "off", _blocker(off, call_lineup, rng), 5, "pre")
    if _flag(rng, 0.0039):
        p = pick(rng, [def_lineup[s] for s in DL if def_lineup.get(s)])
        return Penalty("Defensive Offside", "def", p, 5, "pre")
    if _flag(rng, 0.0030):
        p = pick(rng, [def_lineup[s] for s in DL if def_lineup.get(s)])
        return Penalty("Neutral Zone Infraction", "def", p, 5, "pre")
    if _flag(rng, 0.0011):
        p = pick(rng, [def_lineup[s] for s in DL if def_lineup.get(s)])
        return Penalty("Encroachment", "def", p, 5, "pre")
    if _flag(rng, 0.0011):
        return Penalty("Defensive Too Many Men on Field", "def", None, 5, "pre")
    return None


def make_grounding(off, qb):
    return Penalty("Intentional Grounding", "off", qb, 10, "down")


def _db(ld, rng, slots=("CB1", "CB2", "NB", "DB", "SS", "FS")):
    return pick(rng, [ld[s] for s in slots if ld.get(s)])


def live(g, off, deff, res, call, dcall, rng):
    """Maybe a flag on a live play. Returns a Penalty or None."""
    lo, ld = call.lineup, dcall.lineup
    kind = res.kind
    if kind in ("pass", "sack", "scramble"):
        rate = 0.0133 * (2.0 if (res.hurried or kind == "sack") else 1.0)
        if _flag(rng, rate):
            return Penalty("Offensive Holding", "off", _blocker(off, lo, rng), 10, "prev")
        if kind == "pass" and res.receiver is not None:
            depth = res.air_yards or 0
            if depth >= 3 and _flag(rng, 0.0055):
                return Penalty("Offensive Pass Interference", "off", res.receiver, 10, "prev")
            if _flag(rng, 0.0042):
                return Penalty("Ineligible Downfield Pass", "off", _blocker(off, lo, rng), 5, "prev")
            # Pass interference is called on throws that fall incomplete.
            if (depth >= 5 and not res.complete and not res.interception
                    and _flag(rng, 0.023 + 0.0027 * min(depth, 45))):
                d = res.pd_by or _db(ld, rng)
                return Penalty("Defensive Pass Interference", "def", d, max(1, depth), "spot", auto_first=True)
        if _flag(rng, 0.0125):
            d = _db(ld, rng, ("CB1", "CB2", "NB", "DB", "SS", "FS", "WLB"))
            return Penalty("Defensive Holding", "def", d, 5, "prev", auto_first=True)
        if kind == "pass" and _flag(rng, 0.0064):
            return Penalty("Illegal Contact", "def", _db(ld, rng, ("CB1", "CB2", "NB", "DB")), 5, "prev",
                           auto_first=True)
        if res.qb_hit_by is not None and _flag(rng, 0.030):
            return Penalty("Roughing the Passer", "def", res.qb_hit_by, 15,
                           "end" if res.complete else "prev", auto_first=True)
    elif kind in ("run", "sneak"):
        if _flag(rng, 0.0098):
            return Penalty("Offensive Holding", "off", _blocker(off, lo, rng), 10, "prev")
    if kind in ("run", "sneak", "pass", "scramble", "sack"):
        if _flag(rng, 0.0050):
            if rng.random() < 0.80:
                d = res.tacklers[0] if res.tacklers else pick(rng, [p for p in ld.values() if p])
                return Penalty("Unnecessary Roughness", "def", d, 15, "end", auto_first=True)
            return Penalty("Unnecessary Roughness", "off", pick(rng, [p for p in lo.values() if p]), 15, "end")
        if res.tacklers and _flag(rng, 0.0026):
            if rng.random() < 0.78:
                return Penalty("Face Mask", "def", res.tacklers[0], 15, "end", auto_first=True)
            return Penalty("Face Mask", "off", res.rusher or res.receiver, 15, "prev")
        if _flag(rng, 0.0025):
            if rng.random() < 0.8:
                d = pick(rng, [ld[s] for s in DL + ("CB1", "CB2") if ld.get(s)])
                return Penalty("Illegal Use of Hands", "def", d, 5, "prev", auto_first=True)
            return Penalty("Illegal Use of Hands", "off", _blocker(off, lo, rng), 10, "prev")
        if _flag(rng, 0.0010):
            if rng.random() < 0.6:
                return Penalty("Unsportsmanlike Conduct", "def", pick(rng, [p for p in ld.values() if p]), 15,
                               "end", auto_first=True)
            return Penalty("Unsportsmanlike Conduct", "off", pick(rng, [p for p in lo.values() if p]), 15, "end")
        if _flag(rng, 0.0006):
            if rng.random() < 0.55:
                return Penalty("Taunting", "def", pick(rng, [p for p in ld.values() if p]), 15, "end",
                               auto_first=True)
            return Penalty("Taunting", "off", res.rusher or res.receiver or lo.get("WR1"), 15, "end")
        if res.tacklers and kind in ("run", "pass", "scramble") and res.yards >= 5 and _flag(rng, 0.0007):
            return Penalty("Horse Collar Tackle", "def", res.tacklers[0], 15, "end", auto_first=True)
    return None


def return_foul(rng, return_team):
    """A foul by the return team on a kick or punt return."""
    if _flag(rng, 0.075):
        p = _st_player(return_team, rng)
        return Penalty("Offensive Holding", "ret", p, 10, "ret")
    if _flag(rng, 0.015):
        p = _st_player(return_team, rng)
        return Penalty("Illegal Block Above the Waist", "ret", p, 10, "ret")
    if _flag(rng, 0.006):
        p = _st_player(return_team, rng)
        return Penalty("Illegal Blindside Block", "ret", p, 15, "ret")
    return None


def coverage_foul(rng, kick_team):
    """A foul by the kicking team during a return: added to the end of the run."""
    if _flag(rng, 0.010):
        return Penalty("Face Mask", "kick", _st_player(kick_team, rng), 15, "kick")
    if _flag(rng, 0.006):
        return Penalty("Unnecessary Roughness", "kick", _st_player(kick_team, rng), 15, "kick")
    if _flag(rng, 0.008):
        return Penalty("Offensive Holding", "kick", _st_player(kick_team, rng), 10, "kick")
    return None


def _st_player(team, rng):
    cands = []
    for slot in ("WLB", "SLB", "SS", "NB", "TE2", "FB", "WR4", "RB"):
        ids = [pid for pid in team.chart.get(slot, []) if team.available(pid)]
        if len(ids) > 1:
            cands.append(team.by_id[ids[1]])
    return pick(rng, cands) if cands else None


# ---------------------------------------------------------------------------
# Expected points (for accept/decline decisions)
# ---------------------------------------------------------------------------

def expected_points(down, togo, yl):
    if yl <= 0:
        return 6.95
    if yl >= 100:
        return -2.0
    down = max(1, min(4, down))
    t = max(1, min(20, togo))
    key = (down, t, min(19, yl // 5))
    v = data.EXPECTED_POINTS.get(key)
    if v is None:
        # nearest available cell
        for dt in range(1, 20):
            for tt in (t - dt, t + dt):
                k = (down, max(1, min(20, tt)), min(19, yl // 5))
                if k in data.EXPECTED_POINTS:
                    return data.EXPECTED_POINTS[k]
        return 0.0
    return v
