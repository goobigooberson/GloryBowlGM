# draft_day.py
# The draft as the game plays it, with you in it (Step 8's screens: the Draft tab).
# draft.py has the rules (the class, AI boards, picks, trades); this file runs them
# one step at a time so the draft can stop at your picks and be saved halfway.
#
# The yearly draft, in the offseason's order:
#   1. Start of the league year: this year's class is announced (new_class), like
#      the real combine. The prospects are in league.players but aren't free
#      agents (league.draft["pool"]); you scout them during free agency waves 1-4
#      (scouting.py).
#   2. The draft phase's Next starts the draft (start): scouting ends and pick 1
#      is on the clock. The draft room runs it pick by pick (step) at the speed
#      you choose and stops when you're on the clock. You pick, let your staff
#      pick, take a trade offer or make one, step one pick at a time, sim to your
#      next pick, or let your staff finish the draft.
#   3. When the last pick is in (finish): rookie deals, undrafted signings (by
#      each team's own scouting), the draft history and the offseason report.
# The startup draft (a new league's teams draft every player) works the same way:
# startup_order / startup_begin / startup_finish.
#
# Saved in league.draft (plain JSON, a league_info key in the save):
#   {"kind": "yearly", "season", "status": "scouting" | "drafting", "pool": [pids],
#    "notes": the class's hidden draft notes (draft.save_notes), "room": the draft
#    in progress (draft.DraftRoom.to_dict, without the boards: they're rebuilt the
#    same way from the league's dice), "stats": the yardsticks the draft started with}
#   {"kind": "startup", "status": "pending" | "drafting", "order": [team ids],
#    "pool": [pids], "room": draft.StartupRoom.to_dict()}
# Screens read this file and scouting.py; nothing here draws anything.

import random

from . import draft as D
from . import scouting as S
from .scale import shown
from .teams import ROSTER_TEMPLATE

YEARLY, STARTUP = "yearly", "startup"
STARTUP_STAGE = "startup_draft"   # league.stage while a new league's startup draft is on
MAX_TRADE_PICKS = 4           # most picks one side of a trade you propose can have (real deals: 1-4)
# A team on the clock that loves a player sitting there won't move down for chart value
# alone: the same rule AI teams use with each other (draft.TRADE_DOWN_COST, grade it would
# give up by picking later instead).
ON_CLOCK_KEEP = D.TRADE_DOWN_COST
ON_CLOCK_NEAR = 5             # ...and the same for a team picking within this many picks of the clock


# ---------------------------------------------------------------------------
# What exists right now
# ---------------------------------------------------------------------------

def _d(league):
    return getattr(league, "draft", None) or {}


def _cache(league):
    """Objects rebuilt from the save (prospect list, draft room), kept while
    the same draft is in memory."""
    d = _d(league)
    c = league.__dict__.get("_draft_day")
    if c is None or c.get("of") is not d:
        c = {"of": d}
        league.__dict__["_draft_day"] = c
    return c


def has_class(league):
    """Is this season's draft class out (scouting or drafting)?"""
    d = _d(league)
    return d.get("kind") == YEARLY and d.get("season") == league.season


def scouting_open(league):
    return has_class(league) and _d(league).get("status") == "scouting"


def drafting(league):
    """Is the yearly draft under way (waiting for you or between picks)?"""
    return has_class(league) and _d(league).get("status") == "drafting"


def in_startup(league):
    return _d(league).get("kind") == STARTUP


def prospects(league):
    """This year's class (Player objects), with their hidden draft notes back on."""
    if not has_class(league):
        return []
    c = _cache(league)
    if "prospects" not in c:
        pros = [league.player(pid) for pid in _d(league)["pool"]]
        if pros and "_grade" not in pros[0].__dict__:
            D.load_notes(pros, _d(league).get("notes") or {})
        c["prospects"] = pros
    return c["prospects"]


def media_ranks(league):
    """{pid: the media's big board rank} (it doesn't know about red flags)."""
    c = _cache(league)
    if "media" not in c:
        ranked = sorted(prospects(league), key=lambda p: p.__dict__.get("_media", 0.0), reverse=True)
        c["media"] = {p.id: i + 1 for i, p in enumerate(ranked)}
    return c["media"]


def combine_ranks(league):
    c = _cache(league)
    if "combine" not in c:
        c["combine"] = S.combine_ranks(prospects(league))
    return c["combine"]


def stats(league):
    """The yardsticks prospects are graded against (draft.starter_stats): the
    ones the draft started with once it's under way."""
    c = _cache(league)
    if "stats" not in c:
        saved = (_d(league).get("stats") or {})
        c["stats"] = {k: tuple(v) for k, v in saved.items()} if saved else D.starter_stats(league)
    return c["stats"]


# ---------------------------------------------------------------------------
# 1. The class is announced (start of the league year)
# ---------------------------------------------------------------------------

def new_class(league, rng):
    """This year's draft class, announced at the start of the league year
    (the real combine is in late February). Returns the prospects."""
    pros = D.make_class(league, rng, early=True)
    league.players.extend(pros)
    league.draft = {"kind": YEARLY, "season": league.season, "status": "scouting",
                    "pool": [p.id for p in pros], "notes": D.save_notes(pros), "room": None}
    _cache(league)["prospects"] = pros
    return pros


# ---------------------------------------------------------------------------
# 2. The draft
# ---------------------------------------------------------------------------

def _user(league):
    return league.user_team_id


def room(league):
    """The draft in progress (draft.DraftRoom), or None."""
    if not drafting(league):
        return None
    c = _cache(league)
    if c.get("room") is None:
        saved = dict(_d(league)["room"])
        pros = prospects(league)
        misses = {}
        saved["boards"] = D.team_boards(league, pros, None, misses)
        uid = _user(league)
        if uid is not None and uid in saved.get("humans", []):
            saved["boards"][uid] = _staff_board(league, uid, pros)
        rng = random.Random(f"draft-resume-{league.settings.get('salt', '')}-{league.season}-{saved['next']}")
        r = D.DraftRoom.from_dict(league, pros, saved, rng)
        r.misses = misses
        r.stats = stats(league)
        c["room"] = r
    return c["room"]


def _staff_board(league, tid, pros):
    """Your staff's board as scouting left it (scouting ends when the draft starts)."""
    return S.staff_board(league, tid, pros)


def _save(league):
    r = _cache(league).get("room")
    if r is None:
        return
    d = r.to_dict()
    d.pop("boards", None)                 # rebuilt the same way on load (room())
    _d(league)["room"] = d


def start(league, order, rng):
    """The draft phase begins: scouting ends and pick 1 is on the clock. Nothing
    is picked yet: you watch the draft pick by pick in the draft room (Blake,
    Oct 22: "it should start at 1st overall", at a draft speed you choose).
    Without a team of yours, or with no picks of yours in this draft, the AI
    makes every pick now. Returns True if the draft is already over (then call
    finish). Stepping (step) gives exactly the picks a straight run would: each
    step is one pass of DraftRoom.run's loop, with the same dice."""
    if not has_class(league):
        new_class(league, rng)            # (a save from before the class came out at the league year's start)
    pros = prospects(league)
    uid = _user(league)
    humans = {uid} if uid is not None else set()
    st = D.starter_stats(league)
    D.regrade(pros, st)                   # draft-day yardsticks, same scouting opinions
    league.draft["notes"] = D.save_notes(pros)
    c = _cache(league)
    c.pop("media", None)
    c["stats"] = st
    override = {uid: _staff_board(league, uid, pros)} if uid is not None else None
    r = D.DraftRoom(league, pros, order, rng, humans=humans, boards_override=override)
    r.stats = st
    league.draft["status"] = "drafting"
    league.draft["stats"] = {k: list(v) for k, v in st.items()}
    c = _cache(league)
    c["room"] = r
    c["stats"] = st
    if uid is None or not any(s["team"] == uid for s in r.slots):
        while r.run() is not None:        # (nobody to watch for: tools, or no picks of yours)
            r.staff_pick()
    _save(league)
    return r.on_clock() is None


def on_clock(league):
    """The slot that's up: {"pick", "round", "team", "from"}, or None when it's over."""
    r = room(league)
    return r.on_clock() if r else None


def user_on_clock(league):
    slot = on_clock(league)
    return slot is not None and slot["team"] == _user(league)


def step(league):
    """One pick by the team on the clock (an AI team; it may trade first).
    Returns the pick made, or None if it's your pick."""
    r = room(league)
    slot = r.on_clock()
    if slot is None or slot["team"] in r.humans:
        return None
    r.try_trade_up()
    slot = r.on_clock()
    if slot["team"] in r.humans:
        _save(league)
        return None
    made = r.ai_pick()
    _save(league)
    return made


def sim_to_user(league):
    """AI picks until you're on the clock again (or the draft ends). Returns
    your slot, or None."""
    r = room(league)
    slot = r.run()
    _save(league)
    return slot


def sim_until(league, stop=None, most=None):
    """AI picks one at a time (step) until you're on the clock, the draft ends,
    stop(made) says so after a pick (the draft room: a player you marked is
    gone), or `most` picks are made. The same picks sim_to_user would make.
    Returns the picks made."""
    made = []
    while (most is None or len(made) < most) and not user_on_clock(league) and on_clock(league) is not None:
        pk = step(league)
        if pk is None:
            break
        made.append(pk)
        if stop is not None and stop(pk):
            break
    return made


def pick(league, pid):
    """You draft him (your team must be on the clock). (done?, message)"""
    r = room(league)
    slot = r.on_clock() if r else None
    if slot is None or slot["team"] != _user(league):
        return False, "You're not on the clock."
    if pid not in r.available:
        return False, "He's already been drafted."
    p = r.prospects[pid]
    r.make_pick(pid)
    _save(league)
    return True, f"With pick {slot['pick']} (round {slot['round']}), you take {p.position} {p.name}."


def staff_pick(league):
    """Your staff makes this pick for you (the best on your board, with your needs)."""
    r = room(league)
    slot = r.on_clock() if r else None
    if slot is None or slot["team"] != _user(league):
        return False, "You're not on the clock."
    made = r.staff_pick()
    p = r.prospects[made["pid"]]
    _save(league)
    return True, f"Your staff takes {p.position} {p.name} with pick {slot['pick']}."


def sim_rest(league):
    """The rest of the draft, your staff picking for you (no trades for you)."""
    r = room(league)
    while r.run() is not None:
        r.staff_pick()
    _save(league)


def staff_choice(league):
    """Who your staff would take with your next pick if it were now: (pid,
    the next pick's slot) or (None, None)."""
    r = room(league)
    uid = _user(league)
    if r is None or uid is None:
        return None, None
    slot = next((s for s in r.slots[r.next:] if s["team"] == uid), None)
    if slot is None or not r.available:
        return None, None
    return r.scores(uid, slot["round"])[0][1], slot


def your_slots(league):
    """Your picks still to come (slots), in order."""
    r = room(league)
    uid = _user(league)
    if r is None:
        return []
    return [s for s in r.slots[r.next:] if s["team"] == uid]


def slots_left(league, team_id):
    r = room(league)
    return [s for s in r.slots[r.next:] if s["team"] == team_id] if r else []


def offers(league):
    """Trade offers for your pick while you're on the clock: AI teams behind you
    that want to move up, each paying at least full chart value. [{"team",
    "gives": [their picks], "chart_points", "for_pick", "for_points"}]"""
    if not user_on_clock(league):
        return []
    r = room(league)
    out = r.offers_to(_user(league))
    for o in out:
        o["for_points"] = round(D.jj_value(o["for_pick"]))
    return out


def accept_offer(league, offer):
    """Take one of offers(): they move up into your pick."""
    r = room(league)
    ok, why = r.accept(offer["team"], _user(league), offer["gives"], [offer["for_pick"]])
    _save(league)
    if not ok:
        return False, why
    team = league.team(offer["team"])
    return True, (f"Trade: {team.name} move up to pick {offer['for_pick']}; you get "
                  f"{pick_list(league, offer['gives'])}.")


def trade_check(league, other, give, get):
    """Would AI team `other` take this deal (your picks `give` for its picks
    `get`: overall pick numbers in this draft, or next year's pick keys like
    "2028-3-12", trades.py)? (yes?, explanation). AI teams want at least full
    Jimmy Johnson chart value from you (draft.py; next year's picks as they value
    them, about a round lower), and a team on the clock that loves a player
    sitting there won't move down."""
    r = room(league)
    uid = _user(league)
    if r is None:
        return False, "The draft isn't on."
    if not give or not get:
        return False, "Pick at least one pick on each side."
    if len(give) > MAX_TRADE_PICKS or len(get) > MAX_TRADE_PICKS:
        return False, f"At most {MAX_TRADE_PICKS} picks on a side."
    ok, why = r.offer(uid, other, list(give), list(get))
    if not ok:
        return False, why
    # A team on the clock (or about to be) that loves a player on the board won't move
    # down past where it could still get him.
    ahead = r.slots[r.next:r.next + ON_CLOCK_NEAR]
    near = [s for s in ahead if s["team"] == other and s["pick"] in get]
    if near:
        s0 = near[0]
        mine = r.scores(other, s0["round"])
        now = [k for k in give if isinstance(k, int)]
        upcoming = [s["pick"] for s in r.slots[r.next:]]
        # (only next year's picks for it: it would give up the player entirely)
        gap = upcoming.index(min(now)) if now and min(now) in upcoming else len(mine) - 1
        if len(mine) > 1 and mine[0][0] - mine[min(gap, len(mine) - 1)][0] > ON_CLOCK_KEEP:
            return False, (f"{league.team(other).name} won't move down: there's a player on the board they "
                           f"want with that pick. ({why})")
    return True, why


def propose(league, other, give, get):
    """Make the trade if they'll take it. (done?, message)"""
    ok, why = trade_check(league, other, give, get)
    if not ok:
        return False, why
    r = room(league)
    done, why = r.accept(_user(league), other, list(give), list(get))
    _save(league)
    if not done:
        return False, why
    return True, (f"Trade with {league.team(other).name}: you give {pick_list(league, give)} for "
                  f"{pick_list(league, get)} ({why}).")


def pick_list(league, picks):
    """'picks 12, 77 and a 2028 3rd-round pick, PIT's' (this draft's by number, next year's by name)."""
    from . import trades as T
    now = sorted(k for k in picks if isinstance(k, int))
    later = [T.pick_label(league, k) for k in picks if not isinstance(k, int)]
    bits = []
    if now:
        bits.append(f"pick{'s' if len(now) > 1 else ''} {', '.join(map(str, now))}")
    bits += [f"a {x}" for x in later]
    return " and ".join(bits) if bits else "nothing"


def next_year_picks(league, team_id):
    """[(key, label, chart points to the team that would get it)] a team's picks in next
    year's draft, for draft-room offers."""
    from . import trades as T
    r = room(league)
    if r is None:
        return []
    out = []
    for key in T.team_picks(league, team_id):
        if T.parse_key(key)[0] == r.season + 1:
            out.append((key, T.pick_label(league, key, short=True)))
    return out


def future_points(league, key, valued_by):
    """What a next-year pick is worth now to the team that would get it (chart points)."""
    from . import trades as T
    return round(T.pick_value(league, valued_by, key))


def chart_points(pick_no):
    return round(D.jj_value(pick_no))


# ---------------------------------------------------------------------------
# What the screens show
# ---------------------------------------------------------------------------

NEED_WORDS = [(1.0, "Big need"), (0.45, "Need"), (0.0, "Could use one"), (-99, "Set")]


def needs(league, team_id):
    """[{"pos", "need" (words), "level" (number), "weakest" (shown rating of the
    starter you'd replace, in a season or two), "typical" (a typical starter there),
    "bodies", "spots"}], biggest need first, and a note on the QB rule."""
    st = stats(league)
    need, qb = D.team_needs(league, team_id, st)
    rows = []
    for position, (weakest, bodies, _recent) in need.items():
        m, sd = st[position]
        level = (m - weakest) / sd + (0.35 if bodies < ROSTER_TEMPLATE[position] else 0.0)
        word = next(w for cut, w in NEED_WORDS if level >= cut)
        rows.append({"pos": position, "need": word, "level": round(level, 2),
                     "weakest": shown(weakest, position), "typical": shown(m, position),
                     "bodies": bodies, "spots": ROSTER_TEMPLATE[position]})
    rows.sort(key=lambda r: -r["level"])
    note = None
    if qb[0] == "young_good":
        note = ("You have a good young starting QB: your staff won't take a quarterback in rounds 1-2 "
                "(you still can).")
    return rows, note


def board(league, team_id=None):
    """Your staff's board: {pid: board grade} (what it would draft from, best
    first by value). While scouting is open it follows what you've learned."""
    tid = _user(league) if team_id is None else team_id
    r = room(league)
    if r is not None and tid in r.boards:
        return r.boards[tid]
    c = _cache(league)
    key = ("board", tid, str(S.state(league)))
    if c.get("board_key") != key:
        c["board_key"] = key
        c["board"] = _staff_board(league, tid, prospects(league))
    return c["board"]


def available(league):
    """Prospects not yet drafted."""
    r = room(league)
    if r is None:
        return list(prospects(league))
    return [r.prospects[pid] for pid in r.available]


def made_picks(league):
    r = room(league)
    return list(r.picks) if r else []


def trades(league):
    r = room(league)
    return list(r.trades) if r else []


def all_slots(league):
    """Every pick of the draft: [{"pick", "round", "team", "from", "pid" or None}]."""
    r = room(league)
    if r is None:
        return []
    made = {pk["pick"]: pk["pid"] for pk in r.picks}
    return [dict(s, pid=made.get(s["pick"])) for s in r.slots]


# ---------------------------------------------------------------------------
# 3. The draft is over
# ---------------------------------------------------------------------------

def finish(league, rng):
    """The last pick is in (your staff makes any you haven't): rookie deals,
    undrafted rookies signed by each team's own scouting, the draft history
    and the offseason report. Returns the draft room (the check tools read it)."""
    from . import free_agency as FA
    r = room(league)
    if r is None:
        return None
    sim_rest(league)
    pros = prospects(league)
    rep = league.offseason_report
    picks = r.picks
    FA.sign_draft_picks(league, picks)
    picked = {pk["pid"] for pk in picks}
    undrafted = [p for p in pros if p.id not in picked]
    league.__dict__["_last_draft"] = r            # sign_undrafted reads each team's scouting misses
    udfa, _unsigned = D.sign_undrafted(league, undrafted, rng)
    league.__dict__.pop("_last_draft", None)
    FA.sign_undrafted(league, udfa)
    league.draft_history.extend(picks)
    D.finish(pros)                                # the hidden draft-day notes go
    if rep is not None:
        rep["draft"] = picks
        rep["udfa"] = [list(x) for x in udfa]
        rep["draft_trades"] = r.trades
    league.draft = None
    league.__dict__.pop("_draft_day", None)
    return r


# ---------------------------------------------------------------------------
# The startup draft (a new league; Blake's main way to start one)
# ---------------------------------------------------------------------------

def startup_league(season, settings):
    """New game with "Startup draft": the league's players are generated as for
    any new league (their 53s and practice squads are only a way to make a
    realistic player pool), then the order is drawn. You pick your team next;
    startup_begin starts the draft."""
    from .league import create_league
    league = create_league(season=season, camp=False)
    league.settings.update(settings)
    startup_order(league, random.Random(f"startup-order-{league.settings['salt']}"))
    return league


def startup_order(league, rng):
    """A new league chooses the startup draft: its teams' order for round 1 is
    drawn by lot (snake after that). Nobody is pooled until you've picked your
    team (startup_begin)."""
    order = [t.id for t in league.teams]
    rng.shuffle(order)
    league.draft = {"kind": STARTUP, "status": "pending", "order": order, "pool": []}
    league.stage = STARTUP_STAGE
    return order


def startup_slot(league, team_id):
    """Where a team picks in round 1 of the startup draft (1-32)."""
    return _d(league)["order"].index(team_id) + 1


def startup_room(league):
    if not in_startup(league) or _d(league).get("status") != "drafting":
        return None
    c = _cache(league)
    if c.get("room") is None:
        c["room"] = D.StartupRoom.from_dict(league, _d(league)["room"])
    return c["room"]


def _startup_save(league):
    r = _cache(league).get("room")
    if r is not None:
        _d(league)["room"] = r.to_dict()


def startup_begin(league):
    """You've picked your team: every rostered and practice squad player goes in
    the pool, and pick 1 is on the clock (you watch it from there, like the
    yearly draft; without a team of yours the AI picks until it's over). (Depth
    charts and captains are set when it's over.)"""
    uid = league.user_team_id
    r = D.StartupRoom(league, humans={uid} if uid is not None else (), order=_d(league)["order"])
    league.draft.update({"status": "drafting", "pool": [p.id for p in r.pool]})
    _cache(league)["room"] = r
    if uid is None:
        r.run()
    _startup_save(league)
    return r.on_clock()


def startup_on_clock(league):
    r = startup_room(league)
    return r.on_clock() if r else None


def startup_pick(league, pid):
    r = startup_room(league)
    slot = r.on_clock() if r else None
    if slot is None or slot["team"] != league.user_team_id:
        return False, "You're not on the clock."
    p = league.player(pid)
    try:
        r.make_pick(pid)
    except ValueError as e:
        return False, str(e)
    _startup_save(league)
    return True, f"Round {slot['round']}, pick {slot['pick']}: you take {p.position} {p.name}."


def startup_staff_pick(league):
    r = startup_room(league)
    slot = r.on_clock() if r else None
    if slot is None or slot["team"] != league.user_team_id:
        return False, "You're not on the clock."
    made = r.ai_pick()
    p = league.player(made["pid"])
    _startup_save(league)
    return True, f"Your staff takes {p.position} {p.name} (round {slot['round']})."


def startup_step(league):
    """One AI pick (None if you're on the clock or it's over)."""
    r = startup_room(league)
    slot = r.on_clock() if r else None
    if slot is None or slot["team"] in r.humans:
        return None
    made = r.ai_pick()
    _startup_save(league)
    return made


def startup_sim_to_user(league):
    r = startup_room(league)
    slot = r.run()
    _startup_save(league)
    return slot


def startup_sim_until(league, stop=None, most=None):
    """startup_step until you're on the clock, it's over, stop(made) after a
    pick, or `most` picks. Returns the picks made."""
    made = []
    while most is None or len(made) < most:
        pk = startup_step(league)
        if pk is None:
            break
        made.append(pk)
        if stop is not None and stop(pk):
            break
    return made


def startup_sim_rest(league):
    r = startup_room(league)
    while r.run() is not None:
        r.ai_pick()
    _startup_save(league)


def startup_staff_choice(league):
    r = startup_room(league)
    uid = league.user_team_id
    if r is None or uid is None or r.on_clock() is None:
        return None
    return r.best(uid).id


def startup_finish(league, rng=None):
    """The startup draft is over (your staff makes any picks you haven't): depth
    charts, captains, practice squads, fresh contracts for the new rosters (the
    generated league's deals are thrown out), then training camp opens (90-man
    rosters) and the first season's schedule is made, as for any new league."""
    from . import free_agency as FA
    from . import season
    from . import transactions
    rng = rng or random.Random(f"startup-finish-{league.settings.get('salt', '')}")
    r = startup_room(league)
    startup_sim_rest(league)
    r.finish(rng)
    # Contracts for the rosters the teams drafted.
    league.contracts, league.contract_log = {}, []
    league.cap_carry, league.cap_charges, league.june1_used = {}, {}, {}
    FA.initial_contracts(league)
    # Kept for the record (not in league.draft_history: that's the college draft, which
    # the AI reads for recent high picks and draft capital).
    league.settings["startup_picks"] = [[pk["pick"], pk["team"], pk["pid"]] for pk in r.picks]
    league.draft = None
    league.__dict__.pop("_draft_day", None)
    # Training camp opens, as for a new league (league.create_league with camp=True).
    league.stage = "preseason"
    transactions.open_camp(league, random.Random(f"camp-{league.settings['salt']}"))
    FA.sync(league, "training camp")
    for t in league.teams:
        league.auto_depth_chart(t.id)
    season.start_season(league)
    return r.picks


def startup_needs(league, team_id):
    """Your roster so far in the startup draft: [{"pos", "have", "spots"}]."""
    r = startup_room(league)
    if r is None:
        return []
    return [{"pos": p, "have": r.have[team_id][p], "spots": n} for p, n in ROSTER_TEMPLATE.items()]
