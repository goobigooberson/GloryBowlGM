# evaluation.py
# What each team's staff sees of a player (Blake, Oct 24: "i just want their
# ratings to be whatever the staff evaluates it to be"; design:
# docs/staff-design.md section 6). Rules only, no screens.
#
# Every rating on every screen is your staff's evaluation; true ratings stay
# inside the engine (the game sim, stats and development always use the truth,
# so stats never change). AI teams make their roster decisions from their own
# staff's view too.
#
# How far off a staff is (internal rating points, one spread: the truth is
# within that about 2 times in 3), PROVISIONAL:
#   your own players       OWN_SD   (your coaches see them every day; the coach
#                                    whose background is his group counts most)
#   everyone else          OTHER_SD (other teams' players, free agents: mostly the
#                                    director of pro personnel; part of the mistake
#                                    is shared by the whole league)
#   draft prospects        the draft's own model (scouting.py), cleared by scouting
# times e^(-EVAL_K x the staff's evaluation skill in spreads, staff.eval_z).
# Potential is a projection: POT_MULT times the mistake on current ability.
#
# The mistakes never flicker: each is a fixed draw for that team, player and
# evaluator(s), redrawn only when the evaluator changes. A player who joins a
# team is first seen at the "everyone else" level and becomes "own" over his
# first few weeks there (KNOW_TICKS).
#
# A staff's number is its best estimate, not the truth plus noise (main
# session, Oct 24): what it saw is pulled toward the average player at his
# position in proportion to how unsure it is (the usual "shrinkage" of an
# estimate; prior = the league's players at his position, rookies apart). So an
# unproven player's ceiling reads modest until it's proven, as in FOF8, and the
# mistakes don't make 90s more common. Your own players (small mistakes) are
# barely pulled; other teams' young players' ceilings the most.
#
# Staged reveals (decided Oct 19): development happens at training camp, but a
# staff sees the change in stages: your own players about a third after camp,
# most by the end of the preseason, all of it a few weeks into the season;
# other teams' players more slowly (REVEAL).

import copy
import math
import random

from . import positions as pos

# ---- Knobs (PROVISIONAL) -----------------------------------------------------
OWN_SD = 1.5
OTHER_SD = 3.5
ROOKIE_MULT = 1.4          # a player who hasn't played a pro season yet is harder to read
POT_MULT = 1.5
EVAL_K = 0.45              # a staff 1.5 spreads better than average halves the mistake
SHARED = 0.40              # share of the "everyone else" mistake the whole league shares
PLAYER_PART = 0.75         # how much of a mistake is about the whole player (vs one skill)
KNOW_TICKS = 6             # weeks (or offseason steps) until a new arrival is known as "own"
# How much of the change at camp a staff sees: (after camp, end of preseason, week 8,
# end of the regular season) for its own players and for everyone else's.
REVEAL = {"own": (0.35, 0.80, 1.0, 1.0), "other": (0.15, 0.35, 0.70, 1.0)}
# A ceiling is what he is now plus the growth still to come, and the growth is what nobody
# can see: the staff's mistake on it (rating points, an average staff, other teams'
# players) by pro seasons played (0 = rookie or prospect), pulled toward the typical
# growth of players that far along (so an unproven ceiling reads modest until it's proven:
# FOF8's feel). Your own coaches see their young players' growth somewhat better.
GROWTH_SD = {0: 6.0, 1: 4.5, 2: 3.5, 3: 2.5}
GROWTH_SD_VET = 1.5
GROWTH_OWN = 0.7
# ------------------------------------------------------------------------------


def _clock(league):
    """A step counter through the year (offseason phases, preseason and
    regular-season weeks, playoff rounds), for how long a player has been with
    a team."""
    stage = league.stage
    base = league.season * 100
    if stage == "offseason":
        # In the real order: coaching, the league year, free agency waves 1-4, the
        # draft, waves 5-7, camp. (The first version added the wave to the phase's
        # place in a list, so the clock ran backwards from the last waves to camp and
        # every late signing and rookie looked brand new at camp.)
        st = league.offseason or {}
        phase = st.get("phase", "resign")
        wave = st.get("wave") or 0
        if phase == "fa":
            return base + (2 + wave if wave <= 4 else 4 + wave)
        return base + {"coaching": 0, "resign": 2, "draft": 7, "drafting": 8, "camp": 12, "done": 13}.get(phase, 0)
    if stage == "preseason":
        return base + 20 + league.pre_week
    if stage == "regular_season":
        return base + 30 + league.week
    if stage == "playoffs":
        return base + 50 + league.playoff_round
    return base + 60


def _reveal(league, rel):
    """Share of this year's camp change the staff sees by now."""
    a, b, c, d = REVEAL[rel]
    stage = league.stage
    if stage == "preseason":
        return a + (b - a) * (max(1, league.pre_week) - 1) / 5
    if stage == "regular_season":
        w = league.week - 1
        return b + (c - b) * min(1.0, w / 8) if w <= 8 else c + (d - c) * min(1.0, (w - 8) / 9)
    return 1.0


def team_of(league, pid):
    t = league.rosters.get(pid)
    if t is None:
        t = league.practice.get(pid)
    if t is None:
        r = league.reserve.get(pid)
        t = r.get("team") if r else None
    return t


def _pool(league):
    """This year's draft prospects (a startup draft's pool is the league's players:
    they're judged like any other team's players)."""
    d = league.draft if isinstance(league.draft, dict) else None
    if not d or d.get("kind") == "startup":
        return set()
    return set(d.get("pool", ()))


def _known_since(league, tid, pid):
    """Clock when the player joined this team, as far as its staff knows
    (league.staff["seen"]: {pid: [team, clock]}). A player never looked at
    before counts as long known (a new league's rosters, older saves)."""
    seen = league.staff.setdefault("seen", {})
    key = str(pid)
    rec = seen.get(key)
    if rec and rec[0] == tid:
        return rec[1]
    now = _clock(league)
    start = now if rec else now - KNOW_TICKS
    seen[key] = [tid, start]
    return start


def _eval_z(league, tid, kind, position=None):
    """staff.eval_z, remembered until the clock moves or a staff changes."""
    from . import staff as S
    memo = league.__dict__.setdefault("_evalz", {})
    group = S.POSITION_GROUP.get(position, "ST") if kind == "own" else None
    key = (_clock(league), len(league.staff["log"]), tid, kind, group)
    if key not in memo:
        if len(memo) > 5000:
            memo.clear()
        memo[key] = S.eval_z(league, tid, kind, position)
    return memo[key]


def _evaluators(league, tid, p, rel):
    from . import staff as S
    s = S.staff_of(league, tid)
    if rel == "own":
        group = S.POSITION_GROUP.get(p.position, "ST")
        spec = [c["id"] for job in ("HC", "OC", "DC", "AHC") for c in (s[job],) if c and c.get("bg") == group]
        return ("own", tuple(sorted(spec)), s["HC"]["id"] if s["HC"] else 0)
    return ("pro", s["PP"]["id"] if s["PP"] else 0, s["HC"]["id"] if s["HC"] else 0)


def _draws(seed, skills):
    r = random.Random(seed)
    g_now, g_pot = r.gauss(0, 1), r.gauss(0, 1)
    out = {}
    for k in sorted(skills):
        out[k] = (g_now, r.gauss(0, 1), g_pot, r.gauss(0, 1))
    return out


def _priors(league, p):
    """{skill: (mean now, variance now, mean ceiling, variance ceiling)} of the
    players at his position (rookies against rookies, veterans against rostered
    veterans; draft prospects against this class), remembered for the season."""
    pool = _pool(league)
    kind = "pool" if p.id in pool else "rookie" if p.experience == 0 else "vet"
    memo = league.__dict__.setdefault("_eval_priors", {})
    key = (league.season, league.stage == "offseason", p.position, kind, len(pool))
    if key in memo:
        return memo[key]
    if kind == "pool":
        group = [league.player(pid) for pid in pool]
    elif kind == "rookie":
        group = [q for q in league.players if q.retired is None and q.experience == 0 and q.id not in pool]
    else:
        group = [league.player(pid) for pid in list(league.rosters) + list(league.practice)]
        group = [q for q in group if q.experience > 0]
    group = [q for q in group if q.position == p.position]
    if len(group) < 8:
        group = [q for q in league.players if q.retired is None and q.position == p.position]
    out = {}
    for k in p.skills:
        cs = [q.skills[k][0] for q in group if k in q.skills]
        ps = [q.skills[k][1] for q in group if k in q.skills]
        if len(cs) < 2:
            out[k] = None
            continue
        mc, mp = sum(cs) / len(cs), sum(ps) / len(ps)
        out[k] = (mc, sum((x - mc) ** 2 for x in cs) / (len(cs) - 1),
                  mp, sum((x - mp) ** 2 for x in ps) / (len(ps) - 1))
    if len(memo) > 400:
        memo.clear()
    memo[key] = out
    return out


def _bucket(p, league):
    return "pool" if p.id in _pool(league) else min(p.experience, 4)


def _growth_prior(league, p):
    """(mean, variance) of the growth still to come (overall ceiling - now) of
    players as far along as he is (draft prospects: this class), for the season."""
    memo = league.__dict__.setdefault("_eval_growth", {})
    b = _bucket(p, league)
    key = (league.season, league.stage == "offseason", b, len(_pool(league)))
    if key not in memo:
        pool = _pool(league)
        if b == "pool":
            group = [league.player(pid) for pid in pool]
        else:
            group = [q for q in league.players if q.retired is None and q.id not in pool
                     and min(q.experience, 4) == b]
        gs = [q.overall("potential") - q.overall() for q in group]
        if len(gs) < 2:
            memo[key] = None
        else:
            m = sum(gs) / len(gs)
            memo[key] = (m, sum((x - m) ** 2 for x in gs) / (len(gs) - 1))
    return memo[key]


def _growth_sd(p, league):
    b = _bucket(p, league)
    return GROWTH_SD[0] if b == "pool" else GROWTH_SD.get(b, GROWTH_SD_VET)


def _estimate(cur, pot, n_now, n_pot, sd_now, sd_growth, prior, gprior):
    """The staff's best estimate (now, ceiling) from what it saw. Now: the
    truth plus its mistake, pulled toward the position's average by how unsure
    it is. Ceiling: that plus the growth it expects, pulled toward the typical
    growth of players as far along by how unsure it is of his."""
    c_obs = cur + sd_now * n_now
    if prior:
        mc, vc, _mp, _vp = prior
        if vc > 0:
            c_obs = mc + vc / (vc + sd_now * sd_now) * (c_obs - mc)
    c_seen = max(1.0, min(99.0, c_obs))
    g_obs = max(0.0, pot - cur) + sd_growth * n_pot
    if gprior:
        mg, vg = gprior
        if vg > 0:
            g_obs = mg + vg / (vg + sd_growth * sd_growth) * (g_obs - mg)
    return c_seen, max(c_seen, min(99.0, c_seen + max(0.0, g_obs)))


def _true_view(league, p, rel):
    """His skills as far as anyone could know them yet (the staged reveal of
    this year's camp change)."""
    d = p.dev or {}
    pre = d.get("pre")
    if not pre or d.get("pre_season") != league.season:
        return dict(p.skills)
    f = _reveal(league, rel)
    if f >= 1.0:
        return dict(p.skills)
    out = {}
    for k, (cur, pot) in p.skills.items():
        old = pre.get(k)
        if old is None:
            out[k] = (cur, pot)
        else:
            out[k] = (old[0] + f * (cur - old[0]), old[1] + f * (pot - old[1]))
    return out


def seen_skills(league, tid, p):
    """{skill: (now, ceiling)} as this team's staff sees him (internal scale,
    unrounded). No staff at all (tools without one): the truth."""
    st = getattr(league, "staff", None)
    if tid is None or not st:
        return dict(p.skills)
    cache = league.__dict__.setdefault("_eval_cache", {})
    now = _clock(league)
    pool = p.id in _pool(league)
    rel = "own" if team_of(league, p.id) == tid else "other"
    since = _known_since(league, tid, p.id) if rel == "own" else None
    ev = _evaluators(league, tid, p, rel)
    key = (tid, p.id, now, ev, since, id(p.skills), p.position)
    hit = cache.get(key)
    if hit is not None:
        return hit
    if pool:
        out = _prospect_view(league, tid, p)
        cache[key] = out
        return out
    from . import staff as S
    base = _true_view(league, p, rel)
    rookie = p.experience == 0
    salt = league.settings.get("salt", "")
    z_pro = _eval_z(league, tid, "college" if rookie else "pro")
    sd_other = OTHER_SD * math.exp(-EVAL_K * z_pro) * (ROOKIE_MULT if rookie else 1.0)
    if rel == "own":
        z_own = _eval_z(league, tid, "own", p.position)
        sd_own = OWN_SD * math.exp(-EVAL_K * z_own) * (ROOKIE_MULT if rookie else 1.0)
        w = max(0.0, min(1.0, (now - since) / KNOW_TICKS))
        sd = sd_other * (1 - w) + sd_own * w
        team = _draws(f"eval-{salt}-{tid}-{p.id}-{ev}", base)
        shared = None
    else:
        sd = sd_other
        team = _draws(f"eval-{salt}-{tid}-{p.id}-{ev}", base)
        shared = _draws(f"eval-shared-{salt}-{p.id}-{league.season}", base)
    a = math.sqrt(SHARED)
    b = math.sqrt(1 - SHARED)
    pp = PLAYER_PART
    q = math.sqrt(1 - pp * pp)
    priors = _priors(league, p)
    gprior = _growth_prior(league, p)
    # The growth still to come: the scouting side's read (pro personnel, or college
    # scouting for a rookie); your own coaches see their young players' growth a bit better.
    sd_g = _growth_sd(p, league) * math.exp(-EVAL_K * z_pro)
    if rel == "own":
        sd_g *= (1 - w) + GROWTH_OWN * w
    out = {}
    quiet = {}          # the same staff's estimate with no mistake (misjudgment() below)
    for k, (cur, pot) in base.items():
        g1, e1, g2, e2 = team[k]
        n_now = pp * g1 + q * e1
        n_pot = 0.6 * n_now + 0.8 * (pp * g2 + q * e2)
        if shared is not None:
            s1, f1, s2, f2 = shared[k]
            sn = pp * s1 + q * f1
            sp = 0.6 * sn + 0.8 * (pp * s2 + q * f2)
            n_now = a * sn + b * n_now
            n_pot = a * sp + b * n_pot
        out[k] = _estimate(cur, pot, n_now, n_pot, sd, sd_g, priors.get(k), gprior)
        quiet[k] = _estimate(cur, pot, 0.0, 0.0, sd, sd_g, priors.get(k), gprior)
    if len(cache) > 200000:
        cache.clear()
        league.__dict__.get("_eval_quiet", {}).clear()
    cache[key] = out
    league.__dict__.setdefault("_eval_quiet", {})[key] = quiet
    return out


def _overall_of(skills, position, which="current"):
    index = 0 if which == "current" else 1
    total = wsum = 0.0
    for skill, w in pos.POSITIONS[position][1]:
        if w > 0:
            total += skills[skill][index] * w
            wsum += w
    return total / wsum if wsum else 0.0


def misjudgment(league, tid, p, which="current"):
    """How far this team's staff misjudges him (its view minus what a staff
    exactly as sure as it is would see with no mistake): its luck or bad luck,
    without the pull toward average that every unsure estimate has. Money
    decisions use this (free agency): comparing views of different sureness
    directly made teams overpay their own stars (seen surely, so barely pulled
    toward average) against the league's view of them."""
    if tid is None or not getattr(league, "staff", None) or p.id in _pool(league):
        return 0.0
    skills = seen_skills(league, tid, p)
    rel = "own" if team_of(league, p.id) == tid else "other"
    since = _known_since(league, tid, p.id) if rel == "own" else None
    key = (tid, p.id, _clock(league), _evaluators(league, tid, p, rel), since, id(p.skills), p.position)
    quiet = league.__dict__.get("_eval_quiet", {}).get(key)
    if quiet is None:
        return 0.0
    return _overall_of(skills, p.position, which) - _overall_of(quiet, p.position, which)


def public_skills(league, p):
    """What the league as a whole believes about him (the shared part of every
    staff's mistake, at an average staff's size): for screens shown before you
    have a team (choosing your team in a new game)."""
    if not getattr(league, "staff", None):
        return dict(p.skills)
    base = _true_view(league, p, "other")
    shared = _draws(f"eval-shared-{league.settings.get('salt', '')}-{p.id}-{league.season}", base)
    sd = OTHER_SD * (ROOKIE_MULT if p.experience == 0 else 1.0)
    pp = PLAYER_PART
    q = math.sqrt(1 - pp * pp)
    priors = _priors(league, p)
    gprior = _growth_prior(league, p)
    sd_g = _growth_sd(p, league)
    out = {}
    for k, (cur, pot) in base.items():
        s1, f1, s2, f2 = shared[k]
        sn = pp * s1 + q * f1
        sp = 0.6 * sn + 0.8 * (pp * s2 + q * f2)
        out[k] = _estimate(cur, pot, sn, sp, sd, sd_g, priors.get(k), gprior)
    return out


def public_overall(league, p, which="current"):
    """His overall as the league as a whole believes it (public_skills),
    remembered for the season (free agency asks this for every bid)."""
    memo = league.__dict__.setdefault("_eval_public", {})
    key = (p.id, which, _clock(league), id(p.skills))
    if key not in memo:
        if len(memo) > 100000:
            memo.clear()
        skills = public_skills(league, p)
        index = 0 if which == "current" else 1
        total = wsum = 0.0
        for skill, w in pos.POSITIONS[p.position][1]:
            if w > 0:
                total += skills[skill][index] * w
                wsum += w
        memo[key] = total / wsum if wsum else 0.0
    return memo[key]


def _prospect_view(league, tid, p):
    """Draft prospects: the draft's scouting model (scouting.py's reading of
    him: the staff's view pulled toward a typical prospect in this class by
    how unsure it still is), so the single number a screen shows is the middle
    of the range on the draft board. AI teams draft from their own boards
    (draft.py)."""
    from . import scouting
    from .draft import starter_stats
    stats = league.__dict__.get("_eval_starter_stats")
    if not stats or stats[0] != _clock(league):
        stats = (_clock(league), starter_stats(league))
        league.__dict__["_eval_starter_stats"] = stats
    (shift_now, _h1), (shift_pot, _h2) = scouting._reading(league, tid, p, stats[1])
    out = {}
    for k, (c, pt) in p.skills.items():
        c_seen = max(1.0, min(99.0, c + shift_now))
        out[k] = (c_seen, max(c_seen, min(99.0, pt + shift_pot)))
    return out


def seen(league, tid, p):
    """The player as this team's staff sees him: a copy whose skills are the
    staff's evaluation (overall(), depth chart fit and everything else that
    reads skills work on it as on the player). Never change it; it isn't the
    player."""
    if tid is None or not getattr(league, "staff", None):
        return p
    view = copy.copy(p)
    view.skills = seen_skills(league, tid, p)
    view.__dict__["_seen_by"] = tid
    return view


def overall(league, tid, p, which="current"):
    """His overall as this team's staff sees it (internal scale, unrounded)."""
    skills = seen_skills(league, tid, p)
    index = 0 if which == "current" else 1
    total = wsum = 0.0
    for skill, w in pos.POSITIONS[p.position][1]:
        if w > 0:
            total += skills[skill][index] * w
            wsum += w
    return total / wsum if wsum else 0.0


def user_view(league, p):
    """The player as YOUR staff sees him (what every screen shows)."""
    return seen(league, league.user_team_id, p)


def note_camp(league, p):
    """Training camp is about to change him: remember what he was, so staffs
    see this year's change in stages (development.training_camp calls this)."""
    if p.dev is None:
        return
    p.dev["pre"] = {k: [round(v[0], 1), round(v[1], 1)] for k, v in p.skills.items()}
    p.dev["pre_season"] = league.season
