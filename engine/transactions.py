# transactions.py
# Roster moves during the season (Step 7 piece 6, Oct 22): practice squads,
# injured reserve, signings, releases, waivers and game-day elevations, by
# the real NFL's rules (Blake: "real NFL rules"). AI teams make their moves
# every week; your team's moves are yours (Blake: "you decide, the game warns
# you"), except that when you sim ahead with a team that can't legally take
# the field, your staff makes the smallest move that fixes it.
#
# Where a player is:
#   league.rosters   {pid: team}  the 53-man roster (the only players who can play)
#   league.practice  {pid: team}  the practice squad (16)
#   league.reserve   {pid: {...}} reserve lists: injured reserve ("IR") or
#                                 physically unable to perform ("PUP")
#   none of these and not retired: a free agent
#
# Real NFL in-season movement, per team per regular season (2022-25, nflverse
# weekly rosters; scratchpad real_moves.py), which the AI is tuned to match:
#   72 different players spend time on the 53 (53 at a time)
#   24 added to the 53 after week 1: 11.6 promoted from their own practice
#      squad, 5.6 back from a reserve list, 6.6 from outside
#   11.8 moved from the 53 to a reserve list; 17.7 released or sent to the
#   practice squad; 16.4 practice squad signings from outside; 6 game-day
#   elevations that went back to the practice squad right after
#   7.5 on reserve lists in week 1 (4.8 IR, 0.7 IR designated to return,
#   0.9 PUP, 0.3 NFI; 4.0 of them new since last season)
#   71 players take a snap

import random
from collections import defaultdict

from . import depth
from . import injuries as I
from . import roster_rules
from . import evaluation as _evaluation   # (imported once here: Oct 25, for speed)
from .teams import ROSTER_TEMPLATE, ROSTER_SIZE


def street_free_agent(*args, **kwargs):
    """A made-up street free agent at undrafted-rookie level (draft.py)."""
    from .draft import street_free_agent as make
    return make(*args, **kwargs)

# ---- Real NFL rules (2024-25) ----------------------------------------------
PRACTICE_SQUAD_SIZE = 16
PRACTICE_SQUAD_VETERANS = 6      # up to 6 may have any experience...
PRACTICE_SQUAD_MAX_EXPERIENCE = 2  # ...the rest have played 2 seasons or fewer
IR_MIN_GAMES = 4                 # a player placed on injured reserve misses at least 4 games
IR_RETURNS = 8                   # each team can bring back 8 players from IR a season (playoffs included)
PUP_MIN_GAMES = 4                # PUP to start the season: misses at least the first 4 games
ELEVATIONS_PER_GAME = 2          # practice squad players a team may elevate for a game...
ELEVATIONS_PER_PLAYER = 3        # ...each at most 3 times a season (then he must be signed to the 53)
SHORT_AT_CAP = 2                 # a team with no cap room left for even a minimum deal may leave up to
                                 # this many 53-man spots open in-season (real teams often carry an open
                                 # spot; game-day minimums are met with elevations). Oct 23, judgment.
WAIVER_EXPERIENCE = 4            # released players with fewer than 4 seasons go on waivers (others are free)

# ---- How AI teams behave (judgment calls, tuned to the real counts above) ---
IR_AT_WEEKS = 4                  # expected out this many games or more: on injured reserve
OWN_PS_BONUS = 2.5               # a team prefers its own practice squad player (knows the system), in
                                 # value points (in-season value: 0.75 now + 0.25 ceiling)
UPGRADE_MARGIN = 4.0             # sign a free agent over his worst at a position only if this much better
UPGRADE_CHANCE = 0.5             # a team looks to upgrade a given week (front offices don't churn every week)
PS_UPGRADE_MARGIN = 4.0          # the same for the practice squad
PS_UPGRADE_CHANCE = 0.2
COVER_EXTRA = 1                  # short-term cover: healthy players wanted at a position beyond game-day minimums
COVER_PER_WEEK = 2               # at most this many cover signings a team a week
ELEVATE_ROUTINE = 0.3            # chance a team elevates one player for depth in a game it isn't short for
CLAIM_MARGIN = 9.0               # claim a waived player only if this much better than your worst there
                                 # (at most one claim a team a week; real NFL: ~1.4 direct moves from one
                                 # team's 53 to another's per team-season, claims and trades together)
# Practice squads by position: real squads, 2018-25 (research session, docs/research/
# real_movement_summary.md), per squad: WR 2.6, CB 1.5 (+0.3 DB), DT 1.35, T 1.35, TE 1.2,
# RB 1.1, DE 1.0, G 0.95, S 0.9, ILB 0.9, OLB 0.7, QB 0.6, C 0.5, K 0.13 (avg 15.2 players).
# Rounded to 16; PS_POSITION_FLEX lets a squad skip a QB or C, as about half of real ones do.
PS_TEMPLATE = {"QB": 1, "RB": 1, "TE": 1, "WR": 3, "T": 1, "G": 1, "C": 1,
               "DE": 1, "DT": 1, "OLB": 1, "ILB": 1, "CB": 2, "S": 1}
PS_POSITION_FLEX = 1             # a squad may run this many over or under at a position


def value(p, league=None, tid=None):
    """How a team rates a player for a move during the season: mostly what he
    can do now, some for his upside. With league and team: as that team's
    staff sees him (Oct 24, Blake: AI teams judge players through their own
    staff's eyes; evaluation.py)."""
    if tid is not None and getattr(league, "staff", None):
        overall = _evaluation.overall
        return 0.75 * overall(league, tid, p) + 0.25 * overall(league, tid, p, "potential")
    return 0.75 * p.overall() + 0.25 * p.overall("potential")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def ensure(league):
    """Leagues and saves from before roster moves: add the new lists."""
    for key, default in (("practice", dict), ("reserve", dict), ("waivers", list), ("transactions", list),
                         ("ir_returns", dict), ("elevations", dict), ("elevated", dict), ("staff_requests", list)):
        if getattr(league, key, None) is None:
            setattr(league, key, default())


def team_of(league, pid):
    """(team id, where) for a player: where is 'roster', 'practice', 'reserve' or None."""
    if pid in league.rosters:
        return league.rosters[pid], "roster"
    if pid in league.practice:
        return league.practice[pid], "practice"
    if pid in league.reserve:
        return league.reserve[pid]["team"], "reserve"
    return None, None


def _on_53(league, tid):
    """The team's 53 in the order of league.players: what a scan of every player for
    league.rosters.get(p.id) == tid gives, from the roster lists instead (Oct 25, for
    speed: the scan reads every player ever, retired ones too). (tid None keeps the scan:
    it matches everyone who isn't on a 53.)"""
    if tid is None:
        return [p for p in league.players if league.rosters.get(p.id) is None]
    return league.team_players(tid)


def practice_players(league, tid):
    return league.in_order(pid for pid, t in league.practice.items() if t == tid)


def reserve_players(league, tid):
    return league.in_order(pid for pid, r in league.reserve.items() if r["team"] == tid)


def ps_eligible(p, squad):
    """Can he join this practice squad (real rules: 2 or fewer seasons, or one
    of up to 6 veterans)?"""
    if p.experience <= PRACTICE_SQUAD_MAX_EXPERIENCE:
        return True
    vets = sum(1 for x in squad if x.experience > PRACTICE_SQUAD_MAX_EXPERIENCE)
    return vets < PRACTICE_SQUAD_VETERANS


def injured_weeks(league, injuries, pid):
    inj = injuries.get(pid)
    return inj["weeks"] if inj and inj["weeks"] > 0 else 0


# ---------------------------------------------------------------------------
# Moves (each one logged)
# ---------------------------------------------------------------------------

def log(league, cal_label, tid, pid, move, note=""):
    league.transactions.append({"season": league.season, "when": cal_label, "team": tid, "pid": pid,
                                "move": move, "note": note})


def _set_team(league, injuries, recovering, pid, tid):
    """An injured or recovering player who changes teams takes it with him."""
    if pid in injuries:
        injuries[pid]["team"] = tid
    if pid in recovering:
        recovering[pid]["team"] = tid


def place_on_reserve(league, injuries, pid, cal, label, lst="IR", tid=None):
    """53 -> injured reserve (or PUP). He misses at least 4 games."""
    tid = tid if tid is not None else league.rosters.get(pid)
    league.rosters.pop(pid, None)
    league.reserve[pid] = {"team": tid, "list": lst, "since": cal, "games": 0}
    inj = injuries.get(pid)
    if inj:
        inj["reserve"] = lst
        inj["status"] = "Injured reserve" if lst == "IR" else "Physically unable to perform"
    log(league, label, tid, pid, "Placed on injured reserve" if lst == "IR" else "Placed on PUP",
        I.name(inj["kind"]) if inj and inj.get("kind") else "")


def can_return(league, injuries, pid):
    """Off IR / PUP: healthy, has missed the 4 games, and (IR) the team has a
    return left this season."""
    r = league.reserve.get(pid)
    if not r or injured_weeks(league, injuries, pid) > 0 or r.get("season"):
        return False      # ("season": placed on IR in training camp, out for the year)
    if r["games"] < (IR_MIN_GAMES if r["list"] == "IR" else PUP_MIN_GAMES):
        return False
    if r["list"] == "IR" and league.ir_returns.get(r["team"], 0) >= IR_RETURNS:
        return False
    return True


def activate(league, injuries, pid, label):
    """Reserve -> 53 (the caller makes room first)."""
    r = league.reserve.pop(pid)
    league.rosters[pid] = r["team"]
    if r["list"] == "IR":
        league.ir_returns[r["team"]] = league.ir_returns.get(r["team"], 0) + 1
    if pid in injuries:
        injuries[pid].pop("reserve", None)
    log(league, label, r["team"], pid, "Activated from injured reserve" if r["list"] == "IR" else "Activated from PUP")


def release(league, pid, cal, label, note=""):
    """53 or practice squad -> waivers (fewer than 4 seasons) or free agency."""
    tid, where = team_of(league, pid)
    league.rosters.pop(pid, None)
    league.practice.pop(pid, None)
    p = league.player(pid)
    if where == "practice":
        log(league, label, tid, pid, "Released from practice squad", note)
    elif p.experience < WAIVER_EXPERIENCE:
        league.waivers.append({"pid": pid, "team": tid, "cal": cal})
        log(league, label, tid, pid, "Waived", note)
    else:
        log(league, label, tid, pid, "Released", note)


def sign(league, injuries, recovering, pid, tid, label, to="roster", note=""):
    """A free agent (or a waiver claim) -> 53 or practice squad."""
    (league.rosters if to == "roster" else league.practice)[pid] = tid
    _set_team(league, injuries, recovering, pid, tid)
    log(league, label, tid, pid, "Signed" if to == "roster" else "Signed to practice squad", note)


def promote(league, pid, label):
    """Practice squad -> 53."""
    tid = league.practice.pop(pid)
    league.rosters[pid] = tid
    log(league, label, tid, pid, "Promoted from practice squad")


# ---------------------------------------------------------------------------
# Helpers for choosing
# ---------------------------------------------------------------------------

def _healthy(league, injuries, players):
    return [p for p in players if injured_weeks(league, injuries, p.id) == 0]


def _counts(players):
    c = defaultdict(int)
    for p in players:
        c[p.position] += 1
    return c


def neediest_position(league, injuries, tid):
    """The position where the 53 is shortest of its roster count, healthy
    players counted first (ties: the scarcer position on game day)."""
    roster = _on_53(league, tid)
    healthy = _counts(_healthy(league, injuries, roster))
    total = _counts(roster)
    return max(ROSTER_TEMPLATE, key=lambda pos_: (ROSTER_TEMPLATE[pos_] - total[pos_],
                                                  ROSTER_TEMPLATE[pos_] - healthy[pos_], ROSTER_TEMPLATE[pos_]))


def release_candidate(league, injuries, tid, protect=(), avoid=None, guard=True):
    """Who a team lets go to make room: the least valuable healthy player at a
    position where it has players to spare (healthy ones beyond the game-day
    minimum plus one, and at least its roster count), never a starter or this
    year's high draft pick. avoid: a position not to cut from."""
    protect = set(protect) | _just_added(league, tid)
    if tid == league.user_team_id and guard:
        # Your staff never cuts an important player on its own (Blake: no FOF8-style
        # bold cuts); it asks you instead (staff_requests).
        protect |= {p.id for p in _on_53(league, tid)
                    if important_reason(league, tid, p)}
    roster = [p for p in _on_53(league, tid) if p.id not in protect]
    chart = league.depth_charts.get(tid, {})
    starters = depth.starter_ids(chart) if chart else set()
    total = _counts(_on_53(league, tid))
    healthy = _counts(_healthy(league, injuries, _on_53(league, tid)))
    options = [p for p in _healthy(league, injuries, roster)
               if p.id not in starters and p.position != avoid
               and total[p.position] >= ROSTER_TEMPLATE.get(p.position, 0)
               and healthy[p.position] > GAME_DAY_MIN.get(p.position, 0) + 1
               and not (p.draft_year == league.season and 1 <= p.draft_round <= 3)]
    if not options:
        options = [p for p in _healthy(league, injuries, roster) if p.id not in starters and p.position != avoid
                   and healthy[p.position] > GAME_DAY_MIN.get(p.position, 0)]
    return min(options, key=lambda q: value(q, league, tid)) if options else None


# Your staff checks in with you before a bigger-than-normal move (Blake, Oct 22:
# FOF8's staff sometimes cut a really good player mid-season; here it asks first).
# An important player: a starter or the first backup at his position, one of the
# team's best players overall, a captain, or a recent high draft pick.
IMPORTANT_TOP_ROSTER = 25       # among the team's 25 most valuable players
IMPORTANT_RECENT_PICK = (3, 3)  # drafted in rounds 1-3, within his first 3 seasons
STARTER_COUNT = {"QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 1, "T": 2, "G": 2, "C": 1, "DE": 2, "DT": 2,
                 "OLB": 2, "ILB": 1, "CB": 2, "S": 2, "K": 1, "P": 1, "LS": 1}


def important_reason(league, tid, p):
    """Why letting this player go would be a big decision ('' if it wouldn't)."""
    roster = _on_53(league, tid)
    def val(q):
        return value(q, league, tid)
    same = sorted((x for x in roster if x.position == p.position), key=val, reverse=True)
    if p in same[:STARTER_COUNT.get(p.position, 1) + 1]:
        return "a starter or first backup at his position"
    if p in sorted(roster, key=val, reverse=True)[:IMPORTANT_TOP_ROSTER]:
        return "one of the team's best players"
    if p.id in league.captains.get(tid, {}).values():
        return "a team captain"
    rnd, seasons = IMPORTANT_RECENT_PICK
    if 1 <= p.draft_round <= rnd and league.season - p.draft_year < seasons:
        return f"a round {p.draft_round} pick from {p.draft_year}"
    return ""


ADDED_MOVES = ("Signed", "Promoted from practice squad", "Claimed off waivers", "Activated from injured reserve",
               "Activated from PUP")


def _just_added(league, tid):
    """Players this team added to its 53 in its latest round of moves (a team
    doesn't cut a player it just signed)."""
    if not league.transactions:
        return set()
    last = league.transactions[-1]
    out = set()
    for t in reversed(league.transactions):
        if t["season"] != last["season"] or t["when"] != last["when"]:
            break
        if t["team"] == tid and t["move"] in ADDED_MOVES:
            out.add(t["pid"])
    return out


def can_afford(league, tid, pid):
    """With contracts (free_agency.py): can this team pay him and stay under
    the cap? (Leagues without contracts: always.)"""
    if tid is None or not getattr(league, "contracts", None):
        return True
    from . import free_agency
    return free_agency.affordable(league, tid, pid)


def free_agent_pool(league, injuries, position=None, ps_only=False, tid=None):
    """Healthy free agents not on waivers (at a position); with tid, only
    the ones that team can afford."""
    waived = {w["pid"] for w in league.waivers}
    fas = [p for p in league.free_agents() if p.id not in league.practice and p.id not in league.reserve
           and injured_weeks(league, injuries, p.id) == 0 and p.id not in waived]
    if position:
        fas = [p for p in fas if p.position == position]
    if tid is not None and getattr(league, "contracts", None):
        from .free_agency import AffordCheck
        money = AffordCheck(league)          # = can_afford, the team's cap worked out once
        fas = [p for p in fas if money.ok(tid, p.id)]
    return fas


# ---------------------------------------------------------------------------
# Practice squads
# ---------------------------------------------------------------------------

def fill_practice_squad(league, injuries, recovering, tid, label, prefer=(), log_it=True, rng=None, fas=None,
                        money=None):
    """Bring a practice squad up to 16: positions short of the squad's mix
    first, best available (his own released players first, then free agents).
    fas / money: the free agents and an AffordCheck shared across teams (final
    cuts fill 32 squads: rebuilding the pool for every pick took ~9 seconds)."""
    squad = practice_players(league, tid)
    if fas is None:
        fas = free_agent_pool(league, injuries)
    if money is None and getattr(league, "contracts", None):
        from .free_agency import AffordCheck
        money = AffordCheck(league)
    by_pos = defaultdict(list)
    for p in fas:
        by_pos[p.position].append(p)
    while len(squad) < PRACTICE_SQUAD_SIZE:
        have = _counts(squad)
        short = sorted(PS_TEMPLATE, key=lambda x: have[x] - PS_TEMPLATE[x])
        pick = None
        for position in short:
            if have[position] >= PS_TEMPLATE[position] + PS_POSITION_FLEX:
                continue
            pool = [p for p in prefer if p.position == position and p.id not in league.rosters
                    and p.id not in league.practice and p.retired is None and ps_eligible(p, squad)]
            pool += [p for p in by_pos.get(position, ()) if team_of(league, p.id)[0] is None
                     and ps_eligible(p, squad) and (money is None or money.ok(tid, p.id))]
            if pool:
                pick = max(pool, key=lambda p: camp_value(p, league, tid))
                break
        if pick is None:
            # Nobody suitable left: a made-up young player (a street free agent, at
            # undrafted-rookie level; draft.street_free_agent).
            position = short[0]
            pick = street_free_agent(position, experience=(rng or random).choice([0, 0, 1, 2]),
                                     season_year=league.season)
            league.players.append(pick)
        league.practice[pick.id] = tid
        _set_team(league, injuries, recovering, pick.id, tid)
        if log_it:
            log(league, label, tid, pick.id, "Signed to practice squad")
        squad.append(pick)
        if money is not None:
            money.invalidate(tid)


def form_practice_squads(league, injuries, recovering, released=(), rng=None, log_it=False):
    """Every team builds its practice squad (a new league, after final cuts).
    released: {team: [players it just cut]} - teams keep their own first."""
    order = list(league.teams)
    (rng or random).shuffle(order)
    released = dict(released or {})
    fas = free_agent_pool(league, injuries)
    money = None
    if getattr(league, "contracts", None):
        from .free_agency import AffordCheck
        money = AffordCheck(league)
    for t in order:
        fill_practice_squad(league, injuries, recovering, t.id, "Final cuts",
                            prefer=released.get(t.id, ()), log_it=log_it, rng=rng, fas=fas, money=money)


# ---------------------------------------------------------------------------
# Training camp, the preseason and final cuts (Oct 23)
# ---------------------------------------------------------------------------
# Blake: "late free agency, then training camp, then pre season, then the cuts". The modern
# NFL: teams carry up to 90 players through camp and the preseason, make small moves every
# week (injured players out, new bodies in, a better free agent now and then), and cut to 53
# once, after the last preseason game (the 75/85/80-man cut-downs ended in 2023); waiver
# claims follow, then practice squads are signed. During camp league.rosters holds the whole
# camp roster and there are no practice squads yet.
CAMP_SWAP_CHANCE = 0.4      # chance a team swaps its worst camp body for a better free agent in a week...
CAMP_SWAP_MARGIN = 3.0      # ...if the free agent is this much better (camp value: half now, half upside).
                            # (Judgment calls: real teams make a few such moves a week in camp.)
CAMP_CLAIM_MARGIN = 4.0     # in camp, claim a waived player who'd beat the team's 53rd-man level at
                            # his position by this much (claims compare to the 53, not the 90)
CAMP_BODY_SHIFT = 20        # a made-up camp body (when no real free agent is left) is a long shot: his
                            # ceiling this many rating points below a street free agent's. Real camp
                            # bodies are mostly the draft class's undrafted tail and released veterans
                            # (those come first). At the plain street level (~390 made up a year) they
                            # were 25% of all starters after 12 seasons and the league's talent crept
                            # up ~4 points; real starters who went undrafted: 8-11% (nflverse 2023-25,
                            # 50%+ snaps, not K/P/LS). At 20: 10.4%, and the level holds (scratchpad
                            # camp_inflation.py, 2 leagues x 12 offseasons).


def in_camp(league):
    """Training camp and the preseason, before final cuts (no practice
    squads yet; a save from before Oct 23 in its preseason has practice squads
    and plays the old way, with 53-man rosters)."""
    return getattr(league, "stage", "") in ("offseason", "preseason") and not getattr(league, "practice", None)


def roster_limit(league):
    return roster_rules.CAMP_LIMIT if in_camp(league) else ROSTER_SIZE


def camp_value(p, league=None, tid=None):
    if tid is not None and getattr(league, "staff", None):
        from .evaluation import overall
        return 0.5 * overall(league, tid, p) + 0.5 * overall(league, tid, p, "potential")
    return 0.5 * p.overall() + 0.5 * p.overall("potential")


def camp_pool(league, injuries):
    """{position: [free agents a team would bring to camp, best first]}:
    healthy, not on waivers, and (with contracts) asking about the minimum by
    now (a starter-caliber free agent doesn't come to camp for the minimum).
    Oct 23: by what he asks once camp opens, not his spring price; before, a
    veteran priced a little over the minimum who went unsigned through free
    agency was never invited (teams made up street free agents instead) and
    often left the league: 3-4 year players were out of the league at week 1
    twice as often as real ones (20% vs 9%)."""
    cheap = None
    if getattr(league, "contracts", None):
        from . import cap_market as M
        from . import free_agency as FA
        table = M.market_table(league)
        camp_wave = FA.POST_DRAFT_WAVES[-1]
        cheap = lambda p: p.id in table and FA.ask_share(table[p.id], camp_wave) <= M.MINIMUM_LINE   # noqa: E731
    pool = defaultdict(list)
    for p in free_agent_pool(league, injuries):
        if cheap is None or cheap(p):
            pool[p.position].append(p)
    for lst in pool.values():
        lst.sort(key=camp_value, reverse=True)
    return pool


def _camp_body(league, pool, position, rng):
    """The best free agent left in the pool at a position, else a made-up
    long shot (a street free agent with a lower ceiling: CAMP_BODY_SHIFT)."""
    lst = pool.get(position) or []
    while lst:
        p = lst.pop(0)
        if team_of(league, p.id)[0] is None and p.retired is None:
            return p
    p = street_free_agent(position, experience=rng.choice([0, 0, 1, 2]), season_year=league.season)
    p.skills = {s: (max(1, round(cur * max(1, pot - CAMP_BODY_SHIFT) / max(1, pot))), max(1, pot - CAMP_BODY_SHIFT))
                for s, (cur, pot) in p.skills.items()}
    league.players.append(p)
    return p


def fill_camp(league, injuries, recovering, tid, label, rng, pool, log_it=True, note="camp roster"):
    """Bring a camp roster up to 90: the position furthest below its camp
    count first (roster_rules.CAMP_TEMPLATE). Returns the players signed."""
    roster = _on_53(league, tid)
    have = _counts(roster)
    n = len(roster)
    signed = []
    tmpl = roster_rules.CAMP_TEMPLATE
    while n < roster_rules.CAMP_LIMIT:
        position = max(tmpl, key=lambda x: (tmpl[x] - have[x], tmpl[x]))
        p = _camp_body(league, pool, position, rng)
        league.rosters[p.id] = tid
        _set_team(league, injuries, recovering, p.id, tid)
        if log_it:
            log(league, label, tid, p.id, "Signed", note)
        have[position] += 1
        n += 1
        signed.append(p)
    return signed


def fill_camp_rosters(league, rng, label="Training camp"):
    """The end of the offseason: every team fills its camp roster to 90
    (yours by your staff: cheap young players at your thinnest positions;
    cut whoever you like before final cuts). Returns [(pid, team)]."""
    ensure(league)
    # Over 90 (last season's 53, practice squad and reserve lists, plus the draft class and
    # undrafted signings): the real limit applies, so the team lets its least valuable
    # players go (never this year's draft picks; for your team, never an important player).
    from . import offseason as OS
    for t in league.teams:
        roster = _on_53(league, t.id)
        over = len(roster) - roster_rules.CAMP_LIMIT
        if over <= 0:
            continue
        mine = t.id == league.user_team_id
        cands = [p for p in roster if not (p.draft_year == league.season and p.draft_round >= 1)
                 and not (mine and important_reason(league, t.id, p))]
        for p in sorted(cands, key=lambda p: OS.keep_value(league, p, t.id))[:over]:
            release(league, p.id, 0, label, "90-man limit" + ("; staff move" if mine else ""))
    pool = camp_pool(league, league.injuries)
    out = []
    for t in sorted(league.teams, key=lambda _t: rng.random()):
        note = "camp roster; staff move" if t.id == league.user_team_id else "camp roster"
        for p in fill_camp(league, league.injuries, league.recovering, t.id, label, rng, pool, note=note):
            out.append((p.id, t.id))
    return out


def open_camp(league, rng):
    """A new league (league.create_league): its practice squads join the camp
    rosters and every team fills to 90, so the first season has training camp
    and final cuts too."""
    for pid, tid in list(league.practice.items()):
        league.rosters[pid] = tid
    league.practice = {}
    pool = camp_pool(league, league.injuries)
    for t in league.teams:
        fill_camp(league, league.injuries, league.recovering, t.id, "Training camp", rng, pool, log_it=False)


def camp_week(league, injuries, recovering, tid, cal, label, rng, pool, fill=True, swaps=True):
    """One team's moves in a week of camp or the preseason: a player out
    for the season goes on injured reserve (real rule: placed on IR before
    the final cut, he can't come back that year; other injured players are
    carried to final cuts), open spots are filled, and now and then the
    worst camp body is swapped for a clearly better free agent. Returns True
    if the roster changed."""
    changed = False
    roster = _on_53(league, tid)
    for p in roster:
        inj = injuries.get(p.id)
        if inj and inj["weeks"] > 0 and inj.get("initial", 0) >= I.SEASON_ENDING_WEEKS and not inj.get("carryover"):
            place_on_reserve(league, injuries, p.id, cal, label, "IR", tid)
            league.reserve[p.id]["season"] = True
            changed = True
    if fill and len([1 for x in league.rosters.values() if x == tid]) < roster_rules.CAMP_LIMIT:
        changed |= bool(fill_camp(league, injuries, recovering, tid, label, rng, pool))
    if swaps and rng.random() < CAMP_SWAP_CHANCE:
        roster = _healthy(league, injuries, _on_53(league, tid))
        by_pos = defaultdict(list)
        for p in roster:
            by_pos[p.position].append(p)
        bodies = []
        for position, group in by_pos.items():
            group.sort(key=lambda q: value(q, league, tid), reverse=True)
            # Players outside the team's best 53-man count at the position, and not
            # one of this year's draft picks: camp bodies.
            bodies += [p for p in group[ROSTER_TEMPLATE.get(position, 0):]
                       if not (p.draft_year == league.season and p.draft_round >= 1)]
        if bodies:
            worst = min(bodies, key=lambda q: camp_value(q, league, tid))
            lst = [p for p in pool.get(worst.position, []) if team_of(league, p.id)[0] is None]
            if lst and camp_value(lst[0], league, tid) > camp_value(worst, league, tid) + CAMP_SWAP_MARGIN:
                best = lst[0]
                pool[worst.position].remove(best)
                release(league, worst.id, cal, label, "camp roster move")
                sign(league, injuries, recovering, best.id, tid, label, note="camp roster")
                changed = True
    return changed


def staff_cut_list(league, injuries, tid):
    """Who your staff would cut to get your camp roster to 53 (the Roster
    screen shows it during the preseason; at final cuts the staff makes
    whatever cuts you haven't): the AI's rule, each position down to its
    roster count, the players it least wants to keep first, except that your
    important players stay while anyone else can go (Blake: no FOF8-style
    bold cuts). Players out 4+ weeks go on injured reserve instead (back
    after 4 games) and don't need a spot. Returns players, first to go first."""
    from . import offseason as OS
    roster = _on_53(league, tid)
    pool = [p for p in roster if injured_weeks(league, injuries, p.id) < IR_AT_WEEKS]
    n_cut = len(pool) - ROSTER_SIZE
    if n_cut <= 0:
        return []
    kv = {p.id: OS.keep_value(league, p, tid) for p in pool}
    important = {p.id for p in pool if important_reason(league, tid, p)}
    if tid == league.user_team_id:
        important |= camp_keeps(league)          # players you marked "Keep at final cuts"
    template = OS.template_cuts(league, tid, pool)
    picked = sorted((p for p in template if p.id not in important), key=lambda p: kv[p.id])[:n_cut]
    if len(picked) < n_cut:
        # You've already cut more than the usual count somewhere: the rest by lowest
        # value, keeping the game-day minimums plus one, important players last.
        have = _counts(pool)
        for p in picked:
            have[p.position] -= 1
        chosen = {p.id for p in picked}
        rest = sorted((p for p in pool if p.id not in chosen),
                      key=lambda p: (p.id in important, kv[p.id]))
        for p in rest:
            if len(picked) >= n_cut:
                break
            if have[p.position] > GAME_DAY_MIN.get(p.position, 0) + 1 or p.position == "FB":
                picked.append(p)
                have[p.position] -= 1
        for p in rest:
            if len(picked) >= n_cut:
                break
            if p not in picked:
                picked.append(p)
    return picked


def camp_keeps(league):
    """Players you've marked 'Keep at final cuts' (your staff won't cut them)."""
    return set(league.settings.get("camp_keep", []))


def final_cuts(league, injuries, recovering, cal, rng, label="Final cuts"):
    """After the last preseason game: every team gets to 53 (long injuries
    to injured reserve or PUP, then the cuts; your team: whatever you
    haven't cut, by your staff), AI teams claim the cut players who'd
    clearly help, then every practice squad is signed (each team's own cuts
    first; yours by your staff unless you've already signed some), short
    positions are filled, and everyone gets under the cap with every
    contract counting. Returns {'cuts': n, 'claims': n}."""
    from . import offseason as OS
    ensure(league)
    released = defaultdict(list)
    user = league.user_team_id
    start = len(league.transactions)
    n_cuts = 0
    for t in league.teams:
        tid = t.id
        mark = len(league.transactions)
        roster = _on_53(league, tid)
        if len(roster) > ROSTER_SIZE:
            for p in roster:
                if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS:
                    lst = "PUP" if injuries[p.id].get("carryover") else "IR"
                    place_on_reserve(league, injuries, p.id, cal, label, lst, tid)
        if tid == user:
            cuts = staff_cut_list(league, injuries, tid)
        else:
            cuts = OS.template_cuts(league, tid)
        for p in cuts:
            release(league, p.id, cal, label, "final cuts")
            released[tid].append(p)
            n_cuts += 1
        if tid == user:
            for tx in league.transactions[mark:]:
                tx["note"] = (tx["note"] + "; " if tx["note"] else "") + "staff move"
    league.settings.pop("camp_keep", None)
    # Waiver claims come the day after the cuts.
    n_tx = len(league.transactions)
    process_waivers(league, injuries, recovering, cal + 0.25, label, rng=rng, camp=False, same_spot=True)
    claims = sum(1 for tx in league.transactions[n_tx:] if tx["move"] == "Claimed off waivers")
    mark = len(league.transactions)
    form_practice_squads(league, injuries, recovering, released, rng=rng, log_it=True)
    for tx in league.transactions[mark:]:
        if tx["team"] == user:
            tx["note"] = (tx["note"] + "; " if tx["note"] else "") + "staff move"
    ai = [t for t in league.teams if t.id != user]
    for pid, tid in OS.fill_short_positions(league, rng, teams=ai):
        log(league, label, tid, pid, "Signed", "roster spot needed")
    if getattr(league, "contracts", None):
        from . import free_agency as FA
        FA.sync(league, label)
        for _ in range(4):
            FA.final_compliance(league, full=True)
            FA.sync(league, label)
            if all(len([1 for x in league.rosters.values() if x == t.id]) >= ROSTER_SIZE for t in ai):
                break
            for pid, tid in OS.fill_short_positions(league, rng, teams=ai):
                log(league, label, tid, pid, "Signed", "roster spot needed")
            FA.sync(league, label)
    # Players nobody signed: the free-agent pool keeps the best (as each offseason).
    from .league import roster_value
    fas = sorted(league.free_agents(), key=roster_value, reverse=True)
    for p in fas[OS.FA_POOL_MAX:]:
        if p.id not in injuries:
            p.retired = league.season - 1
    # Depth charts; a team whose captain was cut votes again.
    for t in league.teams:
        if t.id == user:
            refresh_user_chart(league, t.id)
        else:
            league.auto_depth_chart(t.id)
        if any(league.rosters.get(pid) != t.id for pid in league.captains.get(t.id, {}).values()):
            league.vote_captains(t.id, rng=random.Random(f"captains-{league.settings.get('salt', '')}-{league.season}-{t.id}-cuts"))
    for t in ai:
        n = len([1 for x in league.rosters.values() if x == t.id])
        assert n == ROSTER_SIZE, (t.abbrev, n)
    return {"cuts": n_cuts, "claims": claims, "moves": len(league.transactions) - start}


# ---------------------------------------------------------------------------
# The weekly AI pass
# ---------------------------------------------------------------------------

def waiver_order(league, records=None):
    """Real rule: from week 4 on, worst current record first (records); until
    then, the draft order: last season's worst team first (a new league's
    first weeks: the team list's order)."""
    if records is not None:
        return sorted(league.teams, key=lambda t: (records[t.id]["w"] + 0.5 * records[t.id]["t"]
                                                   - records[t.id]["l"], t.id))
    last = {r["team"]: r for r in league.team_history if r["season"] == league.season - 1}
    if not last:
        return list(league.teams)
    return sorted(league.teams, key=lambda t: (last[t.id]["w"] + 0.5 * last[t.id]["t"] - last[t.id]["l"]
                                               if t.id in last else 0, t.id))


def process_waivers(league, injuries, recovering, cal, label, records=None, rng=None, camp=None, same_spot=False):
    """Last week's waived players: AI teams in waiver order claim the ones who'd
    clearly help them; the rest become free agents (and the team that cut
    him may sign him to its practice squad). In camp a claim is judged
    against the team's 53-man level at the position (not its 90th man), and
    a team under 90 needn't cut anyone. same_spot (final cuts): the claiming
    team lets go of the worst player at that position, keeping its 53's mix."""
    camp = in_camp(league) if camp is None else camp
    pending = [w for w in league.waivers if w["cal"] < cal]
    league.waivers = [w for w in league.waivers if w["cal"] >= cal]
    if not pending:
        return
    order = waiver_order(league, records)
    claimed_by = set()
    # Each team's players by position, built once (rebuilt for a team after it claims):
    # final cuts send ~1,100 players through waivers, and scanning the whole league for
    # every player-team pair took ~11 of final cuts' 15 seconds.
    groups = defaultdict(list)

    def build(tid=None):
        for key in [k for k in groups if tid is None or k[0] == tid]:
            del groups[key]
        for pid, team in league.rosters.items():
            if tid is None or team == tid:
                groups[(team, league.player(pid).position)].append(league.player(pid))
    build()
    money = None
    if getattr(league, "contracts", None):
        from .free_agency import AffordCheck
        money = AffordCheck(league)
    for w in pending:
        p = league.player(w["pid"])
        if p.retired is not None or team_of(league, p.id)[0] is not None:
            continue
        for t in order:
            if t.id == w["team"] or t.id == league.user_team_id or t.id in claimed_by:
                continue
            vp = value(p, league, t.id)
            same = list(groups.get((t.id, p.position), ()))
            margin = CLAIM_MARGIN
            if camp:
                same = sorted(same, key=lambda q, t=t: value(q, league, t.id), reverse=True)[:ROSTER_TEMPLATE.get(p.position, 1)]
                margin = CAMP_CLAIM_MARGIN
            worst = min(same, key=lambda q, t=t: value(q, league, t.id)) if same else None
            if worst is not None and vp > value(worst, league, t.id) + margin and (money is None or money.ok(t.id, p.id)):
                if camp and len([1 for x in league.rosters.values() if x == t.id]) < roster_rules.CAMP_LIMIT:
                    out = None
                else:
                    if same_spot:
                        spare = [x for x in _healthy(league, injuries, same) if x.id not in _just_added(league, t.id)]
                        out = min(spare, key=lambda q, t=t: value(q, league, t.id)) if spare else None
                    else:
                        out = release_candidate(league, injuries, t.id)
                    if out is None:
                        continue
                if out is not None:
                    release(league, out.id, cal, label, "to make room")
                sign(league, injuries, recovering, p.id, t.id, label, note=f"from {league.team(w['team']).abbrev}")
                league.transactions[-1]["move"] = "Claimed off waivers"
                claimed_by.add(t.id)
                build(t.id)
                if money is not None:
                    money.invalidate(t.id)
                break
        else:
            # Cleared waivers: his old team may bring him back on the practice squad.
            if w["team"] != league.user_team_id:
                squad = practice_players(league, w["team"])
                if ps_eligible(p, squad) and squad:
                    worst = min(squad, key=lambda q: value(q, league, w["team"]))
                    if len(squad) < PRACTICE_SQUAD_SIZE or (value(p, league, w["team"]) >
                                                            value(worst, league, w["team"]) + PS_UPGRADE_MARGIN):
                        if len(squad) >= PRACTICE_SQUAD_SIZE:
                            release(league, worst.id, cal, label)
                        sign(league, injuries, recovering, p.id, w["team"], label, to="practice")


GAME_DAY_MIN = {"QB": 2, "RB": 2, "TE": 2, "WR": 4, "C": 1, "G": 2, "T": 2, "DE": 3, "DT": 2, "OLB": 2,
                "ILB": 1, "CB": 4, "S": 2, "K": 1, "P": 1, "LS": 1}   # roster_rules' position minimums


def _thin_position(league, injuries, tid):
    """The position most short of healthy players (game-day minimum plus
    COVER_EXTRA) because of injuries, or None."""
    roster = _on_53(league, tid)
    healthy = _counts(_healthy(league, injuries, roster))
    hurt = _counts(p for p in roster if injured_weeks(league, injuries, p.id) > 0)
    worst, gap = None, 0
    for position, need in GAME_DAY_MIN.items():
        want = need + (COVER_EXTRA if need > 1 else 0)
        g = want - healthy[position]
        if hurt[position] and g > gap:
            worst, gap = position, g
    return worst


def fill_roster_spot(league, injuries, recovering, tid, label, rng, position=None):
    """An open spot on the 53: the best healthy player at the neediest position,
    from the team's own practice squad (preferred) or free agency."""
    position = position or neediest_position(league, injuries, tid)
    own = [p for p in practice_players(league, tid) if p.position == position
           and injured_weeks(league, injuries, p.id) == 0 and can_afford(league, tid, p.id)]
    outside = free_agent_pool(league, injuries, position, tid=tid)
    best_own = max(own, key=lambda q: value(q, league, tid)) if own else None
    best_out = max(outside, key=lambda q: value(q, league, tid)) if outside else None
    if best_own and (best_out is None or value(best_own, league, tid) + OWN_PS_BONUS >= value(best_out, league, tid)):
        promote(league, best_own.id, label)
        return best_own
    street = best_out is None
    if street:
        best_out = street_free_agent(position, experience=rng.choice([0, 1, 2]), season_year=league.season)
        league.players.append(best_out)
    sign(league, injuries, recovering, best_out.id, tid, label)
    if street and getattr(league, "contracts", None):
        # A street free agent signs for the minimum (Oct 23: the week's contract writer priced
        # him like any free agent, up to several million, with no check that the team, which
        # had no one affordable to sign, could pay it).
        from . import contracts as C
        C.sign(league, C.minimum_contract(league, best_out.id, tid, years=1, week=C.pay_week(league)),
               phase=f"signed {label}".strip(), new_team=True)
    return best_out


def staff_runs_practice_squad(league):
    """Your practice squad (Blake, Oct 22): you run it unless you switch it to
    your staff. Staff mode: your staff manages it like an AI team (fills it,
    swaps in better young players now and then, uses its injured list,
    elevates players for games when you haven't) and makes short-term injury
    signings on your 53 like an AI team (injury_cover). Your mode: your choices
    are never overridden, but whatever you leave undone the staff finishes
    when the week is simmed (empty spots filled, injured players to the
    injured list, call-ups when you're short on game day); no upgrades."""
    return league.settings.get("ps_staff", False)


def practice_squad_week(league, injuries, recovering, tid, cal, label, rng, preseason=False, upgrades=True):
    """The practice squad part of a team's week (AI teams, and your team:
    with upgrades=False only the unfinished business, see
    staff_runs_practice_squad)."""
    if not preseason:
        for p in practice_players(league, tid):
            if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS:
                league.practice.pop(p.id)
                league.reserve[p.id] = {"team": tid, "list": "PSIR", "since": cal, "games": 0}
                log(league, label, tid, p.id, "Placed on practice squad injured list",
                    I.name(injuries[p.id]["kind"]) if injuries[p.id].get("kind") else "")
    for pid in [pid for pid, r in league.reserve.items() if r["team"] == tid and r["list"] == "PSIR"]:
        if injured_weeks(league, injuries, pid) == 0:
            del league.reserve[pid]
            squad = practice_players(league, tid)
            p = league.player(pid)
            if len(squad) < PRACTICE_SQUAD_SIZE and ps_eligible(p, squad):
                league.practice[pid] = tid
                log(league, label, tid, pid, "Back to practice squad")
            else:
                log(league, label, tid, pid, "Released", "injury settlement")
    squad = practice_players(league, tid)
    if len(squad) < PRACTICE_SQUAD_SIZE:
        fill_practice_squad(league, injuries, recovering, tid, label, rng=rng)
    elif upgrades and not preseason and rng.random() < PS_UPGRADE_CHANCE:
        worst = min(squad, key=lambda q: value(q, league, tid))
        pool = [p for p in free_agent_pool(league, injuries, worst.position)
                if ps_eligible(p, [x for x in squad if x.id != worst.id])]
        best = max(pool, key=lambda q: value(q, league, tid)) if pool else None
        if best and value(best, league, tid) > value(worst, league, tid) + PS_UPGRADE_MARGIN:
            release(league, worst.id, cal, label)
            sign(league, injuries, recovering, best.id, tid, label, to="practice")


def injury_cover(league, injuries, recovering, tid, cal, label, rng, preseason=False):
    """Open spots on the 53 filled; then short-term cover: a position left
    thin by injuries (fewer healthy than game day needs, plus COVER_EXTRA)
    gets a player for now, and someone at a position with players to spare
    is let go. AI teams every week; your team in staff mode (Blake, Oct 22:
    "let the staff also make short-term injury signings on my 53, like AI
    teams do"). Returns True if the 53 changed."""
    changed = False
    while (n := sum(1 for x in league.rosters.values() if x == tid)) < ROSTER_SIZE:
        if (n >= ROSTER_SIZE - SHORT_AT_CAP and getattr(league, "stage", "") == "regular_season"
                and not _room_for_minimum(league, tid)):
            break               # at the cap: an open spot or two, game-day elevations instead
        if getattr(league, "stage", "") == "regular_season" and tid != league.user_team_id:
            _make_room_for_minimum(league, tid)
        fill_roster_spot(league, injuries, recovering, tid, label, rng)
        changed = True
    if not preseason:
        for _ in range(COVER_PER_WEEK):
            position = _thin_position(league, injuries, tid)
            if position is None:
                break
            if not _room_for_minimum(league, tid):
                break       # at the cap: no swap (a cut veteran is still paid); game-day elevations instead
            out = release_candidate(league, injuries, tid, avoid=position)
            if out is None:
                _ask_instead(league, injuries, tid, label, {"cover": position},
                             f"to sign a {position} while injuries leave the position thin", avoid=position)
                break
            release(league, out.id, cal, label, "roster spot needed")
            fill_roster_spot(league, injuries, recovering, tid, label, rng, position=position)
            changed = True
    return changed


def injured_reserve_week(league, injuries, tid, cal, label, preseason=False):
    """Long injuries (4+ weeks) to injured reserve (PUP for last season's at
    final cuts; not during the preseason: teams carry them to final cuts),
    and healed players back from IR / PUP, letting the least valuable spare
    player go. AI teams every week; your team in staff mode. Returns True if
    the 53 changed."""
    changed = False
    if not preseason:
        for p in _on_53(league, tid):
            if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS:
                lst = "PUP" if injuries[p.id].get("carryover") and cal <= _first_regular_cal() else "IR"
                place_on_reserve(league, injuries, p.id, cal, label, lst, tid)
                changed = True
    for pid in [pid for pid, r in league.reserve.items() if r["team"] == tid and r["list"] != "PSIR"]:
        if can_return(league, injuries, pid):
            out = release_candidate(league, injuries, tid)
            if len([1 for x in league.rosters.values() if x == tid]) >= ROSTER_SIZE:
                if out is None:
                    p = league.player(pid)
                    _ask_instead(league, injuries, tid, label, {"activate": pid},
                                 f"to bring {p.position} {p.first_name} {p.last_name} back from injured reserve")
                    continue
                release(league, out.id, cal, label, "to make room")
            activate(league, injuries, pid, label)
            changed = True
    return changed


def _ask_instead(league, injuries, tid, label, then, purpose, avoid=None):
    """Your team only: the move needs a cut, and the only players to spare are
    important ones: the staff asks you about the one it would let go."""
    if tid != league.user_team_id:
        return
    cand = release_candidate(league, injuries, tid, avoid=avoid, guard=False)
    if cand is None:
        return
    reqs = league.__dict__.setdefault("staff_requests", [])
    if any(r["pid"] == cand.id for r in reqs):
        return
    reqs.append({"pid": cand.id, "then": then, "when": label, "team": tid,
                 "why": f"Release {cand.position} {cand.first_name} {cand.last_name} "
                        f"({important_reason(league, tid, cand)}) {purpose}?"})


def answer_request(league, injuries, recovering, index, approve, cal, label, rng):
    """You approved or declined a staff request. (done, message)."""
    reqs = league.__dict__.get("staff_requests", [])
    if not 0 <= index < len(reqs):
        return False, "That request is gone."
    r = reqs.pop(index)
    if not approve:
        return True, "Declined: nothing changed."
    tid = r["team"]
    if league.rosters.get(r["pid"]) != tid:
        return False, "He's no longer on your 53: nothing changed."
    then = r["then"]
    if "activate" in then and not can_return(league, injuries, then["activate"]):
        return False, "He can't come off injured reserve right now: nothing changed."
    release(league, r["pid"], cal, label, "you approved your staff's request")
    if "activate" in then:
        activate(league, injuries, then["activate"], label)
    else:
        fill_roster_spot(league, injuries, recovering, tid, label, rng, position=then["cover"])
    refresh_user_chart(league, tid)
    return True, "Done."


def ai_week(league, injuries, recovering, tid, cal, label, rng, preseason=False):
    """One AI team's moves for the week. Returns True if its roster changed."""
    # 1-2. Injured reserve for long injuries; players ready to come back.
    changed = injured_reserve_week(league, injuries, tid, cal, label, preseason)
    # 3. Open spots and short-term injury cover.
    changed |= injury_cover(league, injuries, recovering, tid, cal, label, rng, preseason)
    # 4. Now and then, an upgrade: a clearly better free agent (or practice
    #    squad player) over the worst healthy player at a position.
    if not preseason and rng.random() < UPGRADE_CHANCE:
        changed |= _upgrade(league, injuries, recovering, tid, cal, label)
    # 5. Practice squad: injured players to its injured list (and back), refill,
    #    and swap in a clearly better young player now and then.
    practice_squad_week(league, injuries, recovering, tid, cal, label, rng, preseason)
    return changed


def _upgrade(league, injuries, recovering, tid, cal, label):
    roster = league.team_players(tid)
    chart = league.depth_charts.get(tid, {})
    starters = depth.starter_ids(chart) if chart else set()
    fresh = _just_added(league, tid)
    best_gain, move = 0.0, None
    # Nothing changes until the move is made, so the healthy players, the free agents
    # he can afford and his practice squad are worked out once (Oct 22, for speed).
    healthy = _healthy(league, injuries, roster)
    outside = free_agent_pool(league, injuries, tid=tid)
    squad = [p for p in practice_players(league, tid) if injured_weeks(league, injuries, p.id) == 0]
    if squad and getattr(league, "contracts", None):
        from .free_agency import AffordCheck
        money = AffordCheck(league)
        squad = [p for p in squad if money.ok(tid, p.id)]
    for position in ROSTER_TEMPLATE:
        mine = [p for p in healthy if p.position == position and p.id not in starters
                and p.id not in fresh
                and not (p.draft_year == league.season and 1 <= p.draft_round <= 3)]
        if not mine:
            continue
        worst = min(mine, key=lambda q: value(q, league, tid))
        cands = [(value(p, league, tid), p, "fa") for p in outside if p.position == position]
        cands += [(value(p, league, tid) + OWN_PS_BONUS, p, "ps") for p in squad if p.position == position]
        if not cands:
            continue
        v, best, src = max(cands, key=lambda c: c[0])
        gain = v - value(worst, league, tid)
        if gain > UPGRADE_MARGIN and gain > best_gain:
            best_gain, move = gain, (worst, best, src)
    if not move:
        return False
    worst, best, src = move
    release(league, worst.id, cal, label, "replaced")
    if src == "ps":
        promote(league, best.id, label)
    else:
        sign(league, injuries, recovering, best.id, tid, label)
    return True


def _first_regular_cal():
    from .schedule import PRESEASON_WEEKS
    return PRESEASON_WEEKS + 1


def weekly(league, injuries, recovering, cal, label, rng, records=None, preseason=False, teams=None):
    """The league's moves for the week, after its games (AI teams; your team's
    moves are yours). Returns the ids of teams whose roster changed."""
    ensure(league)
    before = defaultdict(set)
    for pid, tid in league.rosters.items():
        before[tid].add(pid)
    process_waivers(league, injuries, recovering, cal, label, records, rng)
    camp = in_camp(league)
    pool = camp_pool(league, injuries) if camp else None
    for t in (teams or league.teams):
        if camp:
            # Training camp (90-man rosters, no practice squads yet). Your camp roster is
            # yours; in staff mode your staff fills open spots and moves players out for
            # the season to injured reserve, as AI teams do (no swaps: who stays is your call).
            mine = t.id == league.user_team_id
            if mine:
                league.staff_requests = [r for r in league.staff_requests if "cap" in r.get("then", {})]
                if staff_runs_practice_squad(league):
                    start = len(league.transactions)
                    camp_week(league, injuries, recovering, t.id, cal, label, rng, pool, swaps=False)
                    for tx in league.transactions[start:]:
                        tx["note"] = (tx["note"] + "; " if tx["note"] else "") + "staff move"
            else:
                camp_week(league, injuries, recovering, t.id, cal, label, rng, pool)
            continue
        if t.id == league.user_team_id:
            # Your practice squad: run by your staff, or by you with the staff
            # finishing what you left undone (your 53 stays yours either way).
            # Last week's unanswered staff requests are dropped (asked again if still needed;
            # cap requests stay until you answer them, see free_agency.request_cap_moves).
            league.staff_requests = [r for r in league.staff_requests if "cap" in r.get("then", {})]
            start = len(league.transactions)
            if staff_runs_practice_squad(league):
                injured_reserve_week(league, injuries, t.id, cal, label, preseason)
                injury_cover(league, injuries, recovering, t.id, cal, label, rng, preseason)
            practice_squad_week(league, injuries, recovering, t.id, cal, label, rng, preseason,
                                upgrades=staff_runs_practice_squad(league))
            for tx in league.transactions[start:]:
                tx["note"] = (tx["note"] + "; " if tx["note"] else "") + "staff move"
            continue
        ai_week(league, injuries, recovering, t.id, cal, label, rng, preseason)
    after = defaultdict(set)
    for pid, tid in league.rosters.items():
        after[tid].add(pid)
    changed = {t.id for t in league.teams if before[t.id] != after[t.id]}
    for tid in changed:
        if tid == league.user_team_id:
            refresh_user_chart(league, tid)
        else:
            league.auto_depth_chart(tid)
    return changed


def refresh_user_chart(league, tid):
    """Your depth chart after a roster move: players who left come off; where
    your starter at a spot left, the best fit there moves in, your other
    choices stay in your order (offseason.update_depth_charts, one team)."""
    roster = league.team_players(tid)
    roster_ids = {p.id for p in roster}
    auto = depth.auto_depth_chart(roster)
    chart = league.depth_charts.get(tid, {})
    for slot, ids in auto.items():
        old = chart.get(slot, [])
        kept = [pid for pid in old if pid in roster_ids]
        if not old or old[0] not in roster_ids:
            kept = ids[:1] + [pid for pid in kept if pid not in ids[:1]]
        fill = [pid for pid in ids if pid not in kept]
        chart[slot] = (kept + fill)[:max(len(old), len(ids))]
    league.depth_charts[tid] = chart


def count_reserve_games(league, team_ids):
    """After a game: each reserve-list player of these teams has missed one more game."""
    for r in league.reserve.values():
        if r["team"] in team_ids:
            r["games"] += 1


# ---------------------------------------------------------------------------
# Game day
# ---------------------------------------------------------------------------

def elevations_for_game(league, injuries, tid, unavailable, routine=True):
    """Practice squad players a team elevates for this game: when its healthy
    53 can't meet the game-day position minimums, up to 2 at the short
    positions (each player at most 3 times a season); with routine, now and
    then one more for depth."""
    roster = [p for p in _on_53(league, tid) if p.id not in unavailable]
    squad = [p for p in practice_players(league, tid) if injured_weeks(league, injuries, p.id) == 0
             and league.elevations.get(p.id, 0) < ELEVATIONS_PER_PLAYER]
    picked = []
    for _ in range(ELEVATIONS_PER_GAME):
        if roster_rules.meets_minimums(roster) and len(roster) >= roster_rules.active_limit(roster):
            break
        short = _short_positions(roster)
        options = [p for p in squad if p not in picked and (p.position in short or not short)]
        if not options or not _room_for_game_check(league, tid, len(picked) + 1):
            break           # (no room for his game check: the team plays a body short, Oct 23)
        p = max(options, key=lambda q: value(q, league, tid))
        picked.append(p)
        roster.append(p)
    if routine and not picked and squad and _room_for_game_check(league, tid):
        # Routine depth: now and then a team dresses one more at its thinnest
        # position (special teams, a banged-up group), if it has the cap room for
        # his game check (Oct 23: teams at the cap went over on routine elevations).
        rng = random.Random(f"elev-{league.settings.get('salt', '')}-{league.season}-{tid}-{len(league.transactions)}")
        if rng.random() < ELEVATE_ROUTINE:
            have = _counts(roster)
            thin = min(ROSTER_TEMPLATE, key=lambda x: (have[x] - ROSTER_TEMPLATE[x], -ROSTER_TEMPLATE[x]))
            options = [p for p in squad if p.position == thin] or squad
            picked.append(max(options, key=lambda q: value(q, league, tid)))
    return picked


def _room_for_minimum(league, tid):
    """Room under the cap (counting this week's unwritten signings) for one more player at
    the minimum for the rest of the season; always True in leagues without contracts."""
    if not getattr(league, "contracts", None):
        return True
    from . import contracts as C
    from .free_agency import pending_hits
    rest = (C.PAY_WEEKS - C.pay_week(league)) / C.PAY_WEEKS
    return C.cap_room(league, tid, top51=False) - pending_hits(league, tid) >= C.min_salary(league, 10) * rest


def _make_room_for_minimum(league, tid):
    """AI, regular season, more open spots than it can carry: if one more minimum player
    doesn't fit under the cap, restructure (then cut) first, as real teams do, instead of
    signing him and going over (Oct 25: a team at the cap three or four short after
    injuries signed them all and stayed up to ~$3.7M over for the rest of the season;
    the week's cap clean-up can't win that back late in the year)."""
    if not getattr(league, "contracts", None) or _room_for_minimum(league, tid):
        return
    from . import contracts as C
    from .free_agency import _comply, pending_hits
    rest = (C.PAY_WEEKS - C.pay_week(league)) / C.PAY_WEEKS
    need = C.min_salary(league, 10) * rest + pending_hits(league, tid)
    cap = C.cap_for(league, league.season)
    rng = random.Random(f"room-{league.settings.get('salt', '')}-{league.season}-{tid}-{len(league.transactions)}")
    _comply(league, tid, rng, target=need / cap, top51=False)


def _room_for_game_check(league, tid, n=1):
    """Room under the cap for n elevated players' game checks (the highest, a veteran's
    minimum for a week); always True in leagues without contracts."""
    if not getattr(league, "contracts", None):
        return True
    from . import contracts as C
    return C.cap_room(league, tid, top51=False) >= n * C.min_salary(league, 10) / C.PAY_WEEKS


def _short_positions(players):
    short = set()
    for _label, positions, required, _g in roster_rules.ROWS:
        if roster_rules.count(players, positions) < required:
            short.update(positions)
    return short


def record_elevations(league, tid, players, label):
    for p in players:
        league.elevations[p.id] = league.elevations.get(p.id, 0) + 1
        log(league, label, tid, p.id, "Elevated for the game")


def roster_warnings(league, injuries, tid):
    """Plain-language notes for your team's roster (the Roster screen)."""
    ensure(league)
    roster = _on_53(league, tid)
    notes = []
    n = len(roster)
    if in_camp(league):
        cuts = len(staff_cut_list(league, injuries, tid))
        notes.append(f"Training camp: {n} of {roster_rules.CAMP_LIMIT} on your camp roster. Final cuts come after "
                     f"the last preseason game: {ROSTER_SIZE} make the team. "
                     + (f"{cuts} more cut{'s' if cuts != 1 else ''} to make; whatever you haven't cut by then, "
                        f"your staff cuts (the players marked CUT; mark anyone you want to keep)." if cuts else
                        "You're down to 53 (players out 4+ weeks go on injured reserve at final cuts)."))
        long_out = [p for p in roster if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS]
        for p in long_out:
            if injuries[p.id].get("initial", 0) >= I.SEASON_ENDING_WEEKS and not injuries[p.id].get("carryover"):
                notes.append(f"{p.position} {p.first_name} {p.last_name} is out for the season: injured reserve "
                             f"frees his camp spot.")
        return notes
    if n < ROSTER_SIZE:
        notes.append(f"{ROSTER_SIZE - n} open spot{'s' if ROSTER_SIZE - n != 1 else ''} on the 53-man roster.")
    long_out = [p for p in roster if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS]
    for p in long_out:
        notes.append(f"{p.position} {p.first_name} {p.last_name} is out about {injuries[p.id]['weeks']} more "
                     f"weeks: injured reserve would free his spot (he'd miss at least {IR_MIN_GAMES} games).")
    healthy = _healthy(league, injuries, roster)
    for row in roster_rules.distribution(healthy, {p.id for p in healthy}):
        if row["short"] and row["label"] != "Total":
            notes.append(f"Only {row['active']} healthy {row['label'].lower()} (game day needs {row['required']}).")
    for p in reserve_players(league, tid):
        if can_return(league, injuries, p.id):
            notes.append(f"{p.position} {p.first_name} {p.last_name} is healthy and can come off "
                         f"{'injured reserve' if league.reserve[p.id]['list'] == 'IR' else 'PUP'}.")
    return notes


def staff_minimum(league, injuries, recovering, tid, cal, label, rng):
    """You simmed ahead and your team can't legally take the field: your
    staff makes the smallest moves that fix it (long injuries to IR to open
    spots, then the best healthy player at each short position from your
    practice squad or free agency). Returns the moves' descriptions."""
    before = len(league.transactions)
    for _ in range(8):
        roster = _on_53(league, tid)
        short = _short_positions(_healthy(league, injuries, roster))
        if not short:
            break
        if len(roster) >= ROSTER_SIZE:
            # Open a spot: the longest injury (4+ weeks) to injured reserve, one at a
            # short position first. With nobody to place there, the staff stops
            # (it never cuts one of your players).
            hurt = [p for p in roster if injured_weeks(league, injuries, p.id) >= IR_AT_WEEKS]
            if not hurt:
                break
            p = max(hurt, key=lambda p: (p.position in short, injured_weeks(league, injuries, p.id)))
            place_on_reserve(league, injuries, p.id, cal, label, "IR", tid)
            continue
        # Exact positions first (the QB minimum before the "skill positions" group).
        exact = {pos_ for pos_, need in GAME_DAY_MIN.items()
                 if sum(1 for x in _healthy(league, injuries, roster) if x.position == pos_) < need}
        pick = _best_for(league, injuries, tid, exact or short)
        if pick is None:
            break
        p2, src = pick
        if src == "ps":
            promote(league, p2.id, label)
        else:
            sign(league, injuries, recovering, p2.id, tid, label)
    for t in league.transactions[before:]:
        t["note"] = (t["note"] + "; " if t["note"] else "") + "staff move (you simmed ahead)"
    if len(league.transactions) > before:
        refresh_user_chart(league, tid)
    return league.transactions[before:]


def _best_for(league, injuries, tid, positions):
    cands = [(value(p, league, tid) + OWN_PS_BONUS, p, "ps") for p in practice_players(league, tid)
             if p.position in positions and injured_weeks(league, injuries, p.id) == 0
             and can_afford(league, tid, p.id)]
    cands += [(value(p, league, tid), p, "fa") for p in free_agent_pool(league, injuries, tid=tid)
              if p.position in positions]
    if not cands:
        return None
    _v, p, src = max(cands, key=lambda c: c[0])
    return p, src


# ---------------------------------------------------------------------------
# Your moves (the Roster screen calls these through season.user_move).
# Each returns (done, message); nothing changes when done is False.
# ---------------------------------------------------------------------------

def _roster_count(league, tid):
    return sum(1 for x in league.rosters.values() if x == tid)


def user_options(league, injuries, pid, tid, has_game):
    """The moves you can make with this player right now: [(action, label, tooltip)]."""
    team, where = team_of(league, pid)
    p = league.player(pid)
    out = []
    hurt = injured_weeks(league, injuries, pid) > 0
    if in_camp(league):
        # Training camp: a 90-man roster, no practice squad until final cuts.
        if team == tid and where == "roster":
            if hurt:
                out.append(("ir", "Place on injured reserve",
                            "Out for the season: a player placed on injured reserve in training camp can't come "
                            "back this year (real rule). Players out 4+ weeks go on injured reserve at final "
                            "cuts instead (back after 4 games), so you can wait."))
            out.append(("release", "Release",
                        "Off your camp roster. Waived if he has fewer than 4 seasons (other teams can claim "
                        "him), else a free agent." + (" Injured: an injury settlement." if hurt else "")))
            if pid in camp_keeps(league):
                out.append(("unkeep", "Remove keep mark", "Your staff may cut him at final cuts again."))
            else:
                out.append(("keep", "Keep at final cuts",
                            "Your staff won't cut him at final cuts (it cuts someone else instead). "
                            "Players marked CUT are the ones it would let go."))
        elif team is None and p.retired is None and not any(w["pid"] == pid for w in league.waivers) \
                and getattr(league, "stage", "") != "offseason":
            # (In the offseason free agents sign through negotiation: the Contracts tab's
            # free agency board.)
            out.append(("sign", "Sign to the camp roster",
                        f"Up to {roster_rules.CAMP_LIMIT} players in training camp, at what he's asking now. "
                        f"Final cuts to {ROSTER_SIZE} come after the last preseason game."))
        return out
    if team == tid and where == "roster":
        if hurt:
            out.append(("ir", "Place on injured reserve",
                        f"Frees his roster spot. He must miss at least {IR_MIN_GAMES} games; you can bring "
                        f"back {IR_RETURNS} players from IR a season ({league.ir_returns.get(tid, 0)} used)."))
        else:
            out.append(("release", "Release",
                        "Waived if he has fewer than 4 seasons (other teams can claim him), else a free agent."))
    elif team == tid and where == "practice":
        out.append(("promote", "Promote to the 53", "Signs him to your 53-man roster (needs an open spot)."))
        if has_game:
            if pid in league.elevated.get(tid, []):
                out.append(("unelevate", "Cancel elevation", "He stays on the practice squad for this game."))
            else:
                n = league.elevations.get(pid, 0)
                out.append(("elevate", "Elevate for this week's game",
                            f"Up to {ELEVATIONS_PER_GAME} a game; each player up to {ELEVATIONS_PER_PLAYER} times "
                            f"a season ({n} used). He returns to the practice squad after the game."))
        out.append(("release", "Release", "Off the practice squad (a free agent)."))
    elif team == tid and where == "reserve" and league.reserve[pid]["list"] != "PSIR":
        out.append(("activate", "Activate",
                    "Back to the 53 (needs an open spot)." if league.reserve[pid]["list"] == "PUP"
                    else f"Back to the 53 (needs an open spot). Uses one of your {IR_RETURNS} IR returns "
                         f"({league.ir_returns.get(tid, 0)} used)."))
    elif team is None and p.retired is None and not any(w["pid"] == pid for w in league.waivers):
        out.append(("sign", "Sign to the 53", "Needs an open spot on your 53-man roster."))
        out.append(("sign_ps", "Sign to practice squad",
                    f"{PRACTICE_SQUAD_SIZE} spots; players with {PRACTICE_SQUAD_MAX_EXPERIENCE} or fewer seasons, "
                    f"plus up to {PRACTICE_SQUAD_VETERANS} veterans."))
    return out


def user_move(league, injuries, recovering, action, pid, tid, cal, label, has_game):
    """Make one of your moves. (done, message)."""
    ensure(league)
    p = league.player(pid)
    team, where = team_of(league, pid)
    name = f"{p.position} {p.first_name} {p.last_name}"
    hurt = injured_weeks(league, injuries, pid) > 0
    camp = in_camp(league)
    if camp and action in ("keep", "unkeep"):
        if team != tid or where != "roster":
            return False, "He isn't on your camp roster."
        keeps = camp_keeps(league)
        (keeps.add if action == "keep" else keeps.discard)(pid)
        league.settings["camp_keep"] = sorted(keeps)
        return True, (f"{name} stays at final cuts." if action == "keep"
                      else f"{name} can be cut at final cuts again.")
    if camp and action not in ("ir", "release", "sign"):
        return False, "Practice squads are signed at final cuts, after the last preseason game."
    if action in ("sign", "sign_ps") and getattr(league, "stage", "") == "offseason":
        return False, "In the offseason, make him an offer on the Contracts tab's free agency board."
    if action == "ir":
        if team != tid or where != "roster" or not hurt:
            return False, "Only an injured player on your roster can go on injured reserve."
        place_on_reserve(league, injuries, pid, cal, label, "IR", tid)
        if camp:
            league.reserve[pid]["season"] = True
            msg = f"{name} placed on injured reserve: out for the season."
        else:
            msg = f"{name} placed on injured reserve: he misses at least {IR_MIN_GAMES} games."
    elif action == "activate":
        if team != tid or where != "reserve":
            return False, "He isn't on your reserve list."
        if not can_return(league, injuries, pid):
            r = league.reserve[pid]
            if hurt:
                return False, f"{name} isn't healthy yet."
            if r["games"] < IR_MIN_GAMES:
                return False, f"{name} has missed {r['games']} games; he must miss at least {IR_MIN_GAMES}."
            return False, f"You've used all {IR_RETURNS} returns from injured reserve this season."
        if _roster_count(league, tid) >= ROSTER_SIZE:
            return False, "Your 53-man roster is full: release someone first."
        activate(league, injuries, pid, label)
        msg = f"{name} activated."
    elif action == "release":
        if team != tid or where not in ("roster", "practice"):
            return False, "He isn't on your roster or practice squad."
        if where == "roster" and hurt and not camp:
            return False, f"{name} is injured: place him on injured reserve instead."
        waived = where == "roster" and p.experience < WAIVER_EXPERIENCE
        if pid in league.elevated.get(tid, []):
            league.elevated[tid].remove(pid)
        release(league, pid, cal, label)
        msg = f"{name} {'waived (other teams can claim him this week)' if waived else 'released'}."
    elif action in ("sign", "sign_ps"):
        if team is not None or p.retired is not None or any(w["pid"] == pid for w in league.waivers):
            return False, "He isn't a free agent right now."
        if hurt:
            return False, f"{name} is injured: no team signs him until he's healthy."
        if action == "sign":
            if _roster_count(league, tid) >= roster_limit(league):
                return False, (f"Your camp roster is full ({roster_rules.CAMP_LIMIT}): release someone first."
                               if camp else "Your 53-man roster is full: release someone first.")
            if not can_afford(league, tid, pid):
                return False, f"Signing {name} would put you over the salary cap."
            sign(league, injuries, recovering, pid, tid, label)
            msg = f"{name} signed to your {'camp roster' if camp else '53-man roster'}."
        else:
            squad = practice_players(league, tid)
            if len(squad) >= PRACTICE_SQUAD_SIZE:
                return False, f"Your practice squad is full ({PRACTICE_SQUAD_SIZE})."
            if not ps_eligible(p, squad):
                return False, (f"He has {p.experience} seasons and you already have {PRACTICE_SQUAD_VETERANS} "
                               f"veterans on the practice squad.")
            sign(league, injuries, recovering, pid, tid, label, to="practice")
            msg = f"{name} signed to your practice squad."
    elif action == "promote":
        if team != tid or where != "practice":
            return False, "He isn't on your practice squad."
        if _roster_count(league, tid) >= ROSTER_SIZE:
            return False, "Your 53-man roster is full: release someone first."
        if not can_afford(league, tid, pid):
            return False, f"Promoting {name} would put you over the salary cap."
        if pid in league.elevated.get(tid, []):
            league.elevated[tid].remove(pid)
        promote(league, pid, label)
        msg = f"{name} promoted to the 53."
    elif action in ("elevate", "unelevate"):
        if team != tid or where != "practice":
            return False, "Only practice squad players can be elevated."
        if not has_game:
            return False, "Your team has no game left to play this week."
        chosen = league.elevated.setdefault(tid, [])
        if action == "unelevate":
            if pid in chosen:
                chosen.remove(pid)
            return True, f"{name} stays on the practice squad this week."
        if hurt:
            return False, f"{name} is injured."
        if len(chosen) >= ELEVATIONS_PER_GAME:
            return False, f"You've already elevated {ELEVATIONS_PER_GAME} players for this game."
        if league.elevations.get(pid, 0) >= ELEVATIONS_PER_PLAYER:
            return False, (f"{name} has been elevated {ELEVATIONS_PER_PLAYER} times this season: "
                           f"promote him to the 53 to use him again.")
        chosen.append(pid)
        return True, f"{name} elevated for this week's game."
    else:
        return False, "Unknown move."
    if getattr(league, "contracts", None):
        from . import free_agency
        free_agency.sync(league, label)      # the move's money right away (signing, release charges)
    refresh_user_chart(league, tid)
    return True, msg


# ---------------------------------------------------------------------------
# For tools that play a season without a preseason (tools/simlab.py,
# step6_season_test.py): the same camp, preseason injuries and final cuts
# ---------------------------------------------------------------------------
# Injuries in preseason games, per team (measured in real-game seasons, Oct 22:
# ~6.2 game-costing injuries a team over its preseason games, 19% of them to
# depth-chart starters, who are 36% of the 53 + practice squad: they barely play).
PRESEASON_GAME_INJURIES = 6.2
PRESEASON_STARTER_SHARE = 0.19


def lab_preseason(league, report, rng):
    """Training camp and the preseason before week 1 of a tool season
    (calendar weeks -5..0, week 1 = 1): practice injuries every week, what
    the preseason games would cause in their weeks, the extra week of healing
    before week 1, then final cuts. Every team makes AI moves."""
    ensure(league)
    camp = in_camp(league)
    if not league.practice and not camp:
        form_practice_squads(league, report.injuries, report.recovering, rng=rng)
    starters = set()
    for t in league.teams:
        starters |= depth.starter_ids(league.depth_charts.get(t.id, {}))
    teams = {t.id: league.team_players(t.id) + practice_players(league, t.id) for t in league.teams}
    n_all = sum(len(v) for v in teams.values())
    share = sum(1 for v in teams.values() for p in v if p.id in starters) / max(1, n_all)
    game_weight = {p.id: (PRESEASON_STARTER_SHARE / share if p.id in starters
                          else (1 - PRESEASON_STARTER_SHARE) / (1 - share))
                   for v in teams.values() for p in v}
    for cal in range(-5, 1):
        report.practice_injuries(teams, cal, I.CAMP_INJURIES_PER_TEAM / I.CAMP_WEEKS)
        if cal >= -3:
            report.practice_injuries(teams, cal, PRESEASON_GAME_INJURIES / 4, weight=game_weight, key="pregame")
        if camp and cal < 0:
            weekly(league, report.injuries, report.recovering, cal, f"Camp week {cal + 6}", rng, preseason=True)
        report.end_week(cal + 1 if cal < 0 else 0.5)
    if camp:
        final_cuts(league, report.injuries, report.recovering, 0, rng)
    weekly(league, report.injuries, report.recovering, 0, "Final cuts", rng)


def lab_elevations(league, report, team_ids, unavailable):
    """Game-day elevations for a tool game: {team id: [players]}."""
    extra = {}
    for tid in team_ids:
        extra[tid] = elevations_for_game(league, report.injuries, tid, unavailable[tid])
        for p in extra[tid]:
            league.elevations[p.id] = league.elevations.get(p.id, 0) + 1
    return extra


# ---------------------------------------------------------------------------
# Season boundaries
# ---------------------------------------------------------------------------

def end_of_season(league):
    """The league year ends: reserve lists clear and practice squad players
    sign "reserve/future" deals with their teams (the 90-man offseason
    roster), so the offseason sorts everyone out (cuts to 53, a new practice
    squad from the players cut)."""
    ensure(league)
    # Who ended the season on a 53 or injured reserve (the offseason's cut to 53 favors them).
    league.last_53 = {**{pid: r["team"] for pid, r in league.reserve.items() if r["list"] != "PSIR"},
                      **league.rosters}
    for pid, r in list(league.reserve.items()):
        league.rosters[pid] = r["team"]
    league.reserve = {}
    for pid, tid in list(league.practice.items()):
        league.rosters[pid] = tid
    league.practice = {}
    league.waivers = []
    league.ir_returns = {}
    league.elevations = {}
