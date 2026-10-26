# trades.py
# Player trades (Oct 23; trades session). Blake's decisions:
#   - AI teams call with offers themselves, at real NFL rates (a few calls a season, more
#     near the deadline and around the draft), mostly about players you have to spare or
#     that a team needs.
#   - Future draft picks up to 3 drafts out. An AI team values a future pick by how good it
#     expects that team to be, discounted for the wait (the real market's discount).
#   - The AI answers in words, like a phone call: "not interested", "close, add a little",
#     or a counter-offer. No value meter, no numbers. A GM you keep insulting stops
#     listening for a while (FOF8).
#   - The real NFL window: from the new league year to the deadline (Tuesday after week 9
#     in a 17-game season), then closed until the next league year.
#
# The core, from FOF8's lesson (its AI traded by a fixed value per position and by "team
# strength before vs after" through one league-wide scouting view, so elite TEs and some
# positions were easy to pry loose): every team values the PLAYER, through its own staff's
# eyes, the way it values everything else in this game:
#   - what he adds to ITS position group over who would play otherwise (group_value: its
#     starters, first backup and depth, from the real pay ladders, with a premium for the
#     scarce top of each position: a top-5 player can't be bought in free agency);
#   - minus what he costs it: the base salaries he brings (his signing bonus stays with the
#     team that paid it, the real rule), year by year;
#   - his age and development curve (cap_market.project), year by year while he's under
#     contract, plus the rights to re-sign a young player (and a first-rounder's option);
#   - weighed by the team's timeline: all in (this season counts most), normal, rebuilding
#     (the future counts most, picks are worth more), and in-season its playoff chances.
# All values are in draft-chart points (the Jimmy Johnson chart draft.py prices draft-day
# trades with), so picks and players are on one scale.
#
# Real data (docs/research/trade_research.py -> real_trades.json; nflverse trades 2013-25):
#   about 60 trades with players a league year lately (2021-25; 47 in 2013-25), mostly one
#   player for a mid or late pick; stars (8%+ of the cap) about 4.5 a year; ~1 in 7 teams
#   makes no player trade in a year; future picks traded are almost all next year's.
#
# Where things live: league.trades (saved as a league_info key, plain JSON):
#   {"picks": {"2027-1-5": 12}  traded picks only: "season-round-original team" -> owner
#    "log": [every trade: {"id", "season", "when", "phase", "step", "teams": [a, b],
#            "gave": {"a": {"players", "picks"}, "b": {...}}, "user", "info": {pid: what he
#            was when traded}, "dead": {team: $K}}]
#    "mood": {team: {"insults", "until", "backout"}}  GMs tired of lowball offers
#    "inbox": [AI teams' offers to you, each good until the next step]
#    "shopped": {pid: step}  players you've shopped around (rumors)
#    "step": decision points so far (each offseason phase, preseason and regular-season week)}
# Screens read this module; nothing here draws anything.

import math
import random
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta

from . import cap_market as M
from . import contracts as C
from . import draft as D

# ---- Real rules -----------------------------------------------------------------
PICK_YEARS = 3                # picks in the next three drafts can be traded (real rule)
DEADLINE_WEEK = {17: 9, 16: 8}   # the deadline: Tuesday after week 9 (17 games, since 2024), week 8 before
MAX_SIDE = 5                  # most players + picks one side of a deal (FOF8's limit; real deals: 1-4)
ROUNDS = D.ROUNDS
STARTERS = {"QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 1, "T": 2, "G": 2, "C": 1, "DE": 2, "DT": 2,
            "OLB": 2, "ILB": 1, "CB": 2, "S": 2, "K": 1, "P": 1, "LS": 1}

# ---- How a team values a player (PROVISIONAL; sized by tools/trade_check.py) ----
POINTS_PER_CAP = 4000         # chart points per season of surplus worth a whole cap (40 per 1% of the cap)
STAR_K = 0.5                  # premium on the scarce top of a position: x (1 + this x how far above the
                              # starter line he ranks); the best at a position is worth 1.5x his pay rung
BACKUP_SHARE = 0.25           # a first backup is worth this share of what he'd add as a starter (starters
                              # miss ~3 of 17 games, plus rotation snaps)
DEPTH_SHARE = 0.05            # ...and the second backup this share
RIGHTS_SHARE = 0.5            # the rights to re-sign a young player (29 or younger when his deal ends):
RIGHTS_AGE = 29               # this share of a season of his worth over his market price
TRADE_SURE = 0.5              # a team acts on this share of its staff's misjudgment of ANOTHER team's player
                              # (the team that has him knows him better; acting on the full read made every
                              # call land on the player its staff overrated most: the winner's curse)
DEAD_TIMING_K = 0.15          # the team trading him: future bonus money speeding onto this year's cap costs
                              # this share of it (it was owed anyway; only the timing changes)
# The team's timeline: (weight of this season, each later season's weight vs the one before).
TIMELINE = {"all_in": (1.25, 0.75), "normal": (1.0, 0.85), "rebuild": (0.65, 0.92)}
RACE = (0.6, 1.3)             # in-season: this season's weight for a team out of the race / in it
# ---- Picks ----
# Real market (draft-time deals 2013-25 with one next-year pick): the team taking a next-year
# pick counts it at 0.36-0.48 of its round's middle (median ~0.44; "one round lower", as the
# saying goes). Here: x this per year until that draft (continuous), on the pick's expected
# chart value from where that team is likely to pick.
PICK_DISCOUNT = {"all_in": 0.42, "normal": 0.50, "rebuild": 0.60}
PICK_TEAM = {"all_in": 0.90, "normal": 1.0, "rebuild": 1.15}   # and rebuilding teams want picks more
PICK_STYLE_K = 0.10           # a GM who trades down for picks values them x e^(-k x his draft-day style)
SLOT_SD_LATER = 9.0           # where a team will pick in a later draft: its likely slot +/- this
SLOT_REGRESS = 0.5            # each draft further out, its likely slot moves this share back to the middle
# ---- Deals ----
CAMP_BUFFER = 0.015           # camp trades: room kept for week 1 (the 52nd/53rd men, practice squad, reserve lists)
AI_MARGIN = (1.0, 0.03)       # between AI teams each side wants to gain at least this (points, share)
USER_MARGIN = (15.0, 0.08)    # from you an AI team wants a bit more (they lean conservative, FOF8)
FAR_PENALTY = 0.5            # building a package: a pick a draft further out counts as this share of the price
                              # more (real: 82% of traded picks are in the next draft, 16% the one after, 2% later)
FAR_MIN = 30.0                # (at least this many points, so small deals use next year's picks too)
EXTRA_ITEM = 10.0             # ...each extra pick in it this many points (simpler deals first)
PLAYER_ITEM = 70.0           # ...a player in it this many (real: 15% of player trades have players both ways)
STAR_AUCTION_CAP = 0.10       # players paid this share of the cap or more go by auction (above)
AUCTION = 0.85               # a team shopping a player gets this share of the second-best bid at least
PRICE_SPLIT = 0.15             # AI deals: the price lands this share of the way from the seller's floor
                              # to the buyer's ceiling (buyers have other numbers to call)
STARTER_PREMIUM = 0.2        # a team selling one of its starters wants this much over what losing him costs
YOUNG_PREMIUM = 0.35          # ...and this much more for a young one (25 or younger: the core it's building)
REBUILD_SELL_AGE = 28         # (a rebuilding team asks no premium for its veterans this old or older)
CLOSE_SHARE = 0.15            # short by this share of what they need (or CLOSE_POINTS): "close, add a little"
CLOSE_POINTS = 25.0
INSULT_SHARE = 0.5            # offering less than this share of what they'd need is a lowball
PATIENCE = (2, 4)             # lowballs a GM puts up with (each GM his own number in this range)...
COOL_OFF = 10                 # ...then he stops taking your calls for this many steps (about 4 months)
BACKOUT_COUNTS = 1            # agreeing to a deal and backing out counts like this many lowballs
MARKET_SHARE = 0.95           # an AI team selling you a player wants at least this share of the most another
                              # AI team would give for him (it knows the market: no buying low to flip him)
STAR_LOCK = 900               # a player worth this much to his team (about a top-10 pick)...
STAR_LOCK_RATIO = 0.75        # ...isn't available for less than this share of what they'd need (unless rebuilding)
# ---- How often AI teams call (league-wide expected calls per step; tools/trade_check.py sizes the
# multiplier to the real counts by phase, 2021-25: league year to the draft 19.0 trades a year
# (incl. the deals agreed before the league year), draft 1.4, after the draft to camp 2.8, camp and
# the preseason 19.4, the season to the deadline 17.2 (deadline week 9.2, the week before 3.2)).
CALLS = {"league_year": 17.0, "fa_early": 5.0, "pre_draft": 5.0, "draft": 3.2, "fa_late": 1.6, "camp": 12.0,
         "preseason": 8.0, "cuts": 17.0, "season": 3.2, "deadline": 48.0}
SEASON_RAMP = {1: 0.4, 2: 0.5, 3: 0.6, 4: 0.8, 5: 1.0, 6: 1.3, 7: 1.6}   # weeks before the last two
CALLS_K = 1.0                 # overall multiplier (sized by trade_check)
GM_ACTIVE_K = 1.0             # a GM with a strong draft-day habit (either way) deals more: calls x e^(k x |habit|)
                              # (real teams differ: deals per team a year spread 2.4, 14% of teams make none)
import os as _os
if _os.environ.get("TRADES_OFF"):  # the check tools' "before" runs: no AI trades (the game as it was)
    CALLS_K = 0.0
CANDIDATES = 6                # players a calling team looks at per call...
STARTER_LOOK = 0.3            # ...each of them this likely another team's starter (the rest: its spare players)
NEED_POINTS = 8.0             # rating points short of a typical player in the role that make a need of 1
STARTER_HOLE = 0.5            # a starter need counts once he's this far short (4 rating points)
BACKUP_NEED = 1.0             # a hole behind the starter counts this much next to a hole in the lineup
SPECIALIST_NEED = 0.3         # kickers, punters, snappers, fullbacks: this much
# How often a hole at each position is filled by trade rather than free agency or the draft (x the
# need), sized so the share of traded players by position matches the real NFL's 2013-25 (traded share
# / roster share: QB 1.7, WR 1.45, DB 1.05, OL 0.95, RB/LB/EDGE 0.9, TE 0.8, DL 0.6, K/P/LS 0.4):
# QBs and receivers move by trade more than their roster share, defensive tackles less.
POSITION_MARKET = {"QB": 1.1, "WR": 2.0, "CB": 1.3, "S": 1.3, "T": 0.85, "G": 0.85, "C": 0.85, "TE": 0.7,
                   "DT": 0.9, "DE": 1.3, "OLB": 1.0, "ILB": 1.0, "RB": 1.0}
# ---- Calls to you (Blake: "a few calls a season, more near the deadline and around the draft")
USER_CALLS = {"league_year": 0.9, "fa_early": 0.25, "pre_draft": 0.8, "draft": 0.3, "fa_late": 0.15, "camp": 0.4,
              "preseason": 0.25, "cuts": 0.8, "season": 0.12, "deadline": 1.6}
OFFER_SWEETEN = (0.03, 0.15)  # an AI team calling you offers this much over what it thinks you'd lose


# ---------------------------------------------------------------------------
# State and the calendar
# ---------------------------------------------------------------------------

def ensure(league):
    t = getattr(league, "trades", None)
    if not isinstance(t, dict):
        t = {}
        league.trades = t
    for k, v in (("picks", {}), ("log", []), ("mood", {}), ("inbox", []), ("shopped", {}), ("step", 0)):
        t.setdefault(k, v)
    return t


def _salt(league):
    return league.settings.get("salt", "")


def deadline_week(league):
    return DEADLINE_WEEK.get(league.settings.get("season_games", 17), 9)


def deadline_date(league):
    """The real deadline: the Tuesday after the deadline week's Sunday (4 pm ET; real
    2024-25: Nov 5 and Nov 4, the Tuesday after week 9)."""
    from .schedule import week_sunday
    return week_sunday(league.season, deadline_week(league)) + timedelta(days=2)


def deadline_words(league):
    """Where the deadline stands, in words that agree with the week shown in the header.
    The game moves from one week's games to the next; "Week 10" is the stretch after
    week 9's games and before week 10's, which holds the real deadline (Tuesday), so trades
    are still open then and close once week 10 is played."""
    from .schedule import week_sunday
    dw = deadline_week(league)
    dl = deadline_date(league)
    day = f"{dl:%A}, {dl:%B} {dl.day}"
    stage = getattr(league, "stage", "")
    if stage == "regular_season" and league.week == dw + 1:
        nxt = week_sunday(league.season, dw + 1)
        return (f"Deadline week: trades close at the deadline, {day}, between week {dw}'s games and week "
                f"{dw + 1}'s ({nxt:%a}, {nxt:%b} {nxt.day}). Once you play week {dw + 1}, trades are closed "
                f"until the new league year.")
    if stage == "regular_season" and league.week > dw + 1:
        return f"The deadline was {day}, after week {dw}'s games. Trades reopen when the new league year starts."
    return (f"The trade deadline is {day}, the Tuesday after week {dw}'s games; after it, trades reopen when "
            f"the new league year starts.")


def window(league):
    """(open?, why) for trades right now. Real rule: from the new league year to the
    deadline, then closed until the next league year. Here also closed while the draft
    is on (trade picks in the draft room) and before the league year (the coaching
    carousel)."""
    stage = getattr(league, "stage", "")
    if getattr(league, "contracts", None) is None or not league.contracts:
        return False, "Trades need contracts."
    if stage == "offseason":
        phase = (league.offseason or {}).get("phase", "resign")
        if phase == "coaching":
            return False, "Trades open when the new league year starts (after the coaching changes)."
        if phase == "drafting":
            return True, ("The draft is on: this draft's picks are traded in the draft room; players and "
                          "later picks here.")
        return True, ""
    if stage == "preseason":
        return True, ""
    if stage == "regular_season":
        dw = deadline_week(league)
        if league.week <= dw:
            return True, ""
        if league.week == dw + 1:
            return True, f"Deadline week: last chance to trade before week {dw + 1}'s games."
        dl = deadline_date(league)
        return False, (f"The trade deadline passed on {dl:%A}, {dl:%B} {dl.day}, after week {dw}'s games. "
                       f"Trades reopen when the new league year starts.")
    if stage == "startup_draft":
        return False, "The startup draft is on."
    return False, "Trades reopen when the new league year starts."


def phase_key(league):
    """Which part of the trading year this is (sets how often AI teams call)."""
    stage = getattr(league, "stage", "")
    if stage == "offseason":
        st = league.offseason or {}
        phase = st.get("phase")
        if phase == "resign":
            return "league_year"
        if phase == "fa":
            return "fa_early" if (st.get("wave") or 1) <= 4 else "fa_late"
        if phase == "draft":
            return "pre_draft"
        if phase == "camp":
            return "fa_late"
        return None
    if stage == "preseason":
        return "cuts" if league.pre_week >= 5 else ("camp" if league.pre_week <= 1 else "preseason")
    if stage == "regular_season":
        # (steps run after a week's games, once the week counter has moved on)
        return "deadline" if league.week - 1 >= deadline_week(league) else "season"
    return None


def when_label(league):
    stage = getattr(league, "stage", "")
    if stage == "offseason":
        from .season import offseason_phase
        ph = offseason_phase(league)
        st = league.offseason or {}
        if st.get("phase") == "fa":
            return f"Free agency, wave {st.get('wave')}"
        return ph[1] if ph else "Offseason"
    from .season import week_label
    lbl = week_label(league)
    if stage == "regular_season" and league.week == deadline_week(league) + 1:
        return "Trade deadline"
    return lbl


def _years_to_draft(league, season):
    """Years until the draft of `season` (late April), from where the league is now."""
    stage = getattr(league, "stage", "")
    if stage == "offseason":
        now = date(league.season, 3, 15)
        st = league.offseason or {}
        wave = st.get("wave") or 1
        if st.get("phase") == "fa" and wave >= 5 or st.get("phase") == "camp":
            now = date(league.season, 6, 1)
        elif st.get("phase") == "draft":
            now = date(league.season, 4, 20)
    elif stage == "preseason":
        now = date(league.season, 8, 10) + timedelta(days=7 * max(0, league.pre_week - 1))
    elif stage == "regular_season":
        now = date(league.season, 9, 10) + timedelta(days=7 * max(0, league.week - 1))
    else:
        now = date(league.season + 1, 1, 20)
    return max(0.0, (date(season, 4, 25) - now).days / 365.0)


# ---------------------------------------------------------------------------
# Draft picks: who owns them, what they're worth
# ---------------------------------------------------------------------------

def draft_done(league):
    """Has this league year's draft been held?"""
    if getattr(league, "stage", "") != "offseason":
        return True
    return any(d["season"] == league.season for d in league.draft_history[-300:])


def pick_seasons(league):
    """The drafts whose picks can be traded here now (the next three not yet held;
    while the draft is on, its own picks are traded in the draft room)."""
    first = league.season + (1 if draft_done(league) else 0)
    out = list(range(first, first + PICK_YEARS))
    if getattr(league, "stage", "") == "offseason" and (league.offseason or {}).get("phase") == "drafting":
        out = [s for s in out if s != league.season]
    return out


def pick_key(season, rnd, orig):
    return f"{season}-{rnd}-{orig}"


def parse_key(key):
    s, r, o = key.split("-")
    return int(s), int(r), int(o)


def owner(league, key):
    t = ensure(league)
    if key in t["picks"]:
        return t["picks"][key]
    return parse_key(key)[2]


def team_picks(league, tid):
    """Keys of every tradable pick this team owns, earliest draft and round first."""
    ensure(league)
    out = []
    teams = [t.id for t in league.teams]
    for s in pick_seasons(league):
        for rnd in range(1, ROUNDS + 1):
            for o in teams:
                k = pick_key(s, rnd, o)
                if owner(league, k) == tid:
                    out.append(k)
    return out


def pick_owners(league, season):
    """{(round, original team): owner} for a draft's traded picks (the draft room uses it)."""
    out = {}
    for k, v in ensure(league)["picks"].items():
        s, r, o = parse_key(k)
        if s == season and v != o:
            out[(r, o)] = v
    return out


def _order(league, season):
    """This draft's order (team ids, first pick first) if it's set, else None."""
    if season == league.season and getattr(league, "stage", "") == "offseason":
        return (league.offseason or {}).get("order")
    return None


def _strength(league):
    """{team: expected win share next} from last season, this season so far and the
    roster (a rough public view; cached for the step)."""
    memo = league.__dict__.setdefault("_trade_strength", {})
    key = _cache_key(league)
    if memo.get("key") == key:
        return memo["v"]
    from . import free_agency as FA
    last = FA.team_quality(league)
    rec = {}
    if getattr(league, "stage", "") in ("regular_season", "playoffs", "season_complete"):
        from .season import records
        rec = records(league)
    out = {}
    for t in league.teams:
        q = last.get(t.id, 0.5)
        r = rec.get(t.id)
        g = (r["w"] + r["l"] + r["t"]) if r else 0
        if g:
            now = (r["w"] + 0.5 * r["t"]) / g
            q = (now * g + q * 6) / (g + 6)       # a few games of last season's showing as a prior
        out[t.id] = q
    memo["key"], memo["v"] = key, out
    return out


def _slot_odds(league, season, orig):
    """[(slot 1-32, chance)] where this team's pick lands in a round of that draft."""
    order = _order(league, season)
    n = len(league.teams)
    if order:
        return [(order.index(orig) + 1, 1.0)]
    q = _strength(league)
    ranked = sorted(q, key=lambda t: q[t])
    mean = ranked.index(orig) + 1
    games = 0
    if getattr(league, "stage", "") == "regular_season":
        games = league.week - 1
    ahead = season - (league.season + (1 if draft_done(league) else 0))   # drafts after the next one
    sd = 3.0 + 8.0 * (1 - games / 17.0)
    if ahead >= 1:
        mean = (n + 1) / 2 + (mean - (n + 1) / 2) * SLOT_REGRESS ** ahead
        sd = SLOT_SD_LATER
    w = [math.exp(-0.5 * ((s - mean) / sd) ** 2) for s in range(1, n + 1)]
    tot = sum(w)
    return [(s, x / tot) for s, x in zip(range(1, n + 1), w)]


def pick_number(league, key):
    """The overall pick number if this draft's order is set, else None."""
    s, r, o = parse_key(key)
    order = _order(league, s)
    if not order:
        return None
    return (r - 1) * len(order) + order.index(o) + 1


def expected_points(league, key):
    """The pick's expected chart value where its team is likely to pick (no discount)."""
    s, r, o = parse_key(key)
    n = len(league.teams)
    return sum(ch * D.jj_value((r - 1) * n + slot) for slot, ch in _slot_odds(league, s, o))


def pick_value(league, tid, key):
    """What this team thinks the pick is worth now (chart points)."""
    s, _r, _o = parse_key(key)
    way = _approach(league, tid)
    base = expected_points(league, key)
    t = _years_to_draft(league, s)
    v = base * PICK_DISCOUNT[way] ** t * PICK_TEAM[way]
    if tid != league.user_team_id and getattr(league, "staff", None):
        from . import gm as G
        v *= math.exp(-PICK_STYLE_K * G.style(league, tid, "trade"))
    return v


def pick_label(league, key, short=False):
    """'2027 1st round (DAL)' or with the pick number when the order is set."""
    s, r, o = parse_key(key)
    ords = {1: "1st", 2: "2nd", 3: "3rd"}
    rn = ords.get(r, f"{r}th")
    num = pick_number(league, key)
    abbr = league.team(o).abbrev
    if short:
        return f"{s} {rn}" + (f" (#{num})" if num else "") + f" {abbr}"
    return f"{s} {rn}-round pick" + (f" (#{num} overall)" if num else "") + f", {abbr}'s"


def pick_words(league, key):
    """How a pick looks: 'likely early', 'mid', 'late' in its round (no numbers)."""
    s, r, o = parse_key(key)
    num = pick_number(league, key)
    if num:
        slot = num - (r - 1) * len(league.teams)
    else:
        odds = _slot_odds(league, s, o)
        slot = sum(sl * ch for sl, ch in odds)
    return "early" if slot <= 10 else ("late" if slot >= 23 else "middle")


# ---------------------------------------------------------------------------
# Player values
# ---------------------------------------------------------------------------

def _cache_key(league):
    from .evaluation import _clock
    t = ensure(league)
    return (league.season, _clock(league), len(league.contract_log), len(league.transactions), len(t["log"]),
            len(league.rosters), getattr(league, "week", 0))


def _approach(league, tid):
    if tid == league.user_team_id:
        return "normal"
    from . import free_agency as FA
    return FA.approach(league, tid)


class _Ctx:
    """Everything a step's valuations share: the market table, price curves, each team's
    position groups as its staff sees them."""

    def __init__(self, league):
        from . import free_agency as FA
        self.league = league
        self.S = league.season
        self.cap = C.cap_for(league, self.S)
        self.table = M.market_table(league)
        self.minimum = C.min_salary(league, 2) / self.cap
        self.week = C.pay_week(league)
        self.in_season = getattr(league, "stage", "") == "regular_season"
        # Price curve per position: market scores (desc) and their ladder ranks.
        by = defaultdict(list)
        for pid, d in self.table.items():
            by[d["position"]].append((d["score"], d["rank"]))
        self.curve = {}
        for pos, rows in by.items():
            rows.sort(key=lambda x: -x[0])
            self.curve[pos] = ([-s for s, _r in rows], [r for _s, r in rows])
        self._scores = {}
        self.groups = {}
        self._on_53 = None
        self.FA = FA
        self.injuries = getattr(league, "injuries", {}) or {}
        self._seasons_left = None

    # ---- the market's curve ----
    def rank_of(self, pos, score):
        neg, ranks = self.curve.get(pos, ([], []))
        if not neg:
            return 999.0
        i = bisect_left(neg, -score)
        if i <= 0:
            return max(0.5, ranks[0] - (score + neg[0]) * 0.3)
        if i >= len(neg):
            return ranks[-1] + 1
        s0, s1 = -neg[i - 1], -neg[i]
        r0, r1 = ranks[i - 1], ranks[i]
        if s0 == s1:
            return r0
        return r0 + (r1 - r0) * (s0 - score) / (s0 - s1)

    def price(self, pos, score):
        ladder, mult = M.LADDER_OF[pos]
        r = self.rank_of(pos, score)
        return max(self.minimum, M.ladder_price(ladder, max(0.5, r)))

    def worth(self, pos, score):
        """W: what a season of his play is worth (share of the cap): his pay rung, with
        a premium for the scarce top of the position."""
        ladder, mult = M.LADDER_OF[pos]
        r = self.rank_of(pos, score)
        line = 32 * STARTERS.get(pos, 1) * mult
        prem = 1 + STAR_K * max(0.0, 1 - r / line)
        return max(self.minimum, M.ladder_price(ladder, max(0.5, r))) * prem

    # ---- how a team sees a player ----
    def score(self, tid, p):
        k = (tid, p.id)
        if k not in self._scores:
            info = self.table.get(p.id)
            self._scores[k] = (self.FA.team_score(self.league, tid, p, info) if info else 0.0)
        return self._scores[k]

    def proj(self, tid, p, n):
        """His rating for each of the next n seasons as this team sees him (this
        season first; once camp has opened, this season is what he is now)."""
        k = ("proj", tid, p.id, n)
        if k not in self._scores:
            from . import evaluation as E
            d_now = E.misjudgment(self.league, tid, p) if tid is not None else 0.0
            d_pot = E.misjudgment(self.league, tid, p, "potential") if tid is not None else 0.0
            if tid is not None and E.team_of(self.league, p.id) != tid:
                d_now *= TRADE_SURE
                d_pot *= TRADE_SURE
            cur, pot = p.overall() + d_now, p.overall("potential") + d_pot
            if self.season_started():
                out = [cur] + M.project(p, self.S + 1, max(0, n - 1), cur, pot)
            else:
                out = M.project(p, self.S, n, cur, pot)
            self._scores[k] = out[:n]
        return self._scores[k]

    def season_started(self):
        return getattr(self.league, "stage", "") in ("regular_season", "preseason", "playoffs", "season_complete")

    def out_weeks(self, pid):
        inj = self.injuries.get(pid)
        return inj["weeks"] if inj and inj.get("weeks", 0) > 0 else 0

    def group(self, tid, pos):
        """[(score, pid)] of the team's players at a position, best first (the 53 and,
        in the offseason, its offseason roster; long injuries left out in-season)."""
        k = (tid, pos)
        if k not in self.groups:
            # Every team's players by position, in the order of league.rosters, listed once for
            # this context (Oct 25, for speed: one pass instead of one per team and position).
            # The rosters can't change while a context lives: every roster move changes its key
            # (_cache_key), and _dry_run_room puts back what it tries.
            on_53 = self._on_53
            if on_53 is None:
                on_53 = self._on_53 = defaultdict(list)
                for pid, t in self.league.rosters.items():
                    on_53[(t, self.league.player(pid).position)].append(pid)
            rows = []
            for pid in on_53.get((tid, pos), ()):
                p = self.league.player(pid)
                if self.in_season and self.out_weeks(pid) >= 4:
                    continue
                rows.append((self.proj(tid, p, 1)[0], pid))
            rows.sort(reverse=True)
            self.groups[k] = rows
        return self.groups[k]

    def group_value(self, pos, scores):
        """A season of a position group's worth (share of the cap): starters, first
        backup and second backup; missing players count as street free agents."""
        n = STARTERS.get(pos, 1)
        s = sorted(scores, reverse=True)
        floor = self.floor_score(pos)
        while len(s) < n + 2:
            s.append(floor)
        v = sum(self.worth(pos, x) for x in s[:n])
        v += BACKUP_SHARE * self.worth(pos, s[n]) + DEPTH_SHARE * self.worth(pos, s[n + 1])
        return v

    def floor_score(self, pos):
        """A street free agent at the position (about the 5th-best player at the position
        nobody rosters)."""
        k = ("floor", pos)
        if k not in self._scores:
            neg, _r = self.curve.get(pos, ([], []))
            n = len(neg)
            per_team = STARTERS.get(pos, 1) * 2 + 1
            i = min(n - 1, 32 * per_team + 5) if n else 0
            self._scores[k] = -neg[i] if n else 40.0
        return self._scores[k]

    def weights(self, tid, n):
        """This season's weight and the later seasons' for a team's timeline."""
        way = _approach(self.league, tid)
        now, per = TIMELINE[way]
        if self.in_season:
            left = max(0.0, (C.PAY_WEEKS - self.week) / C.PAY_WEEKS)
            now *= left * race_factor(self.league, tid)
        elif getattr(self.league, "stage", "") in ("playoffs", "season_complete"):
            now = 0.0
        return [now] + [per ** t for t in range(1, n)]


def _ctx(league):
    key = _cache_key(league)
    c = league.__dict__.get("_trade_ctx")
    if c is None or c[0] != key:
        c = (key, _Ctx(league))
        league.__dict__["_trade_ctx"] = c
    return c[1]


def race_factor(league, tid):
    """In-season: how much this season still matters to the team (its playoff chances)."""
    from .season import records
    if getattr(league, "stage", "") != "regular_season" or league.week <= 3:
        return 1.0
    r = records(league).get(tid)
    if not r:
        return 1.0
    g = r["w"] + r["l"] + r["t"]
    pct = (r["w"] + 0.5 * r["t"]) / g if g else 0.5
    z = (pct - 0.5) * math.sqrt(g) / 0.5        # how clear the record is
    x = 1 / (1 + math.exp(-1.3 * z))            # rough playoff odds
    return RACE[0] + (RACE[1] - RACE[0]) * x


def _contract_years(league, c, S):
    """[(season, base, bonus)] of the contract from this season on."""
    return [(y["season"], y["base"], y["bonus"]) for y in c["years"] if y["season"] >= S]


def _base_left(ctx, c, season, base):
    """Base salary still to be paid in that season above the minimum (share of the cap):
    the roster spot would be paid the minimum whoever filled it."""
    base = max(0.0, base - C.min_salary(ctx.league, 1, season))
    if season == ctx.S and ctx.week:
        start = c["week"] if c["signed"] == ctx.S else 0
        base = base * (C.PAY_WEEKS - max(ctx.week, start)) / max(1, C.PAY_WEEKS - start)
    return base / ctx.cap


def _seasons(ctx, c):
    """Seasons the deal still runs from now (in-season the current one counts)."""
    if getattr(ctx.league, "stage", "") in ("playoffs", "season_complete"):
        return [s for s, _b, _x in _contract_years(ctx.league, c, ctx.S + 1)]
    return [s for s, _b, _x in _contract_years(ctx.league, c, ctx.S)]


def deal_delta(league, tid, gets_players=(), gives_players=(), gets_picks=(), gives_picks=(), detail=False):
    """How much better (chart points) this team thinks it is after the deal: the
    position groups it changes, season by season while the traded players are under
    contract, net of their base salaries, plus the rights to re-sign, plus picks."""
    ctx = _ctx(league)
    gets_players = [league.player(p) if isinstance(p, int) else p for p in gets_players]
    gives_players = [league.player(p) if isinstance(p, int) else p for p in gives_players]
    moved = gets_players + gives_players
    horizon = 1
    seasons_of = {}
    for p in moved:
        c = league.contracts.get(p.id)
        ss = _seasons(ctx, c) if c else []
        seasons_of[p.id] = ss
        horizon = max(horizon, len(ss) + 1)
    first = ctx.S if getattr(league, "stage", "") not in ("playoffs", "season_complete") else ctx.S + 1
    w = ctx.weights(tid, horizon + 1)
    if first != ctx.S:
        w = [TIMELINE[_approach(league, tid)][1] ** t for t in range(horizon + 1)]
    proj = {p.id: ctx.proj(tid, p, horizon + 1) for p in moved}
    out_ids = {p.id for p in gives_players}
    total = 0.0
    parts = defaultdict(float)
    for pos in sorted({p.position for p in moved}):
        base = [(s, pid) for s, pid in ctx.group(tid, pos)]
        for t in range(horizon):
            season = first + t
            before = []
            after = []
            for s, pid in base:
                if pid in proj:
                    if season not in seasons_of.get(pid, ()):
                        continue                          # his deal has run out by then
                    s = proj[pid][t]
                elif t:
                    s = ctx.proj(tid, league.player(pid), horizon + 1)[t]
                before.append(s)
                if pid not in out_ids:
                    after.append(s)
            for p in gets_players:
                if p.position == pos and season in seasons_of.get(p.id, ()):
                    s = proj[p.id][t]
                    if t == 0 and ctx.in_season and ctx.out_weeks(p.id):
                        # hurt now: he helps only for the weeks he's back
                        s = s if ctx.out_weeks(p.id) < 4 else ctx.floor_score(pos)
                    after.append(s)
            d = ctx.group_value(pos, after) - ctx.group_value(pos, before)
            total += w[t] * d
            parts["group"] += w[t] * d
    # Money: base salaries in, out (bonus money stays with the team that paid it).
    for sign, players in ((-1, gets_players), (1, gives_players)):
        for p in players:
            c = league.contracts.get(p.id)
            if not c:
                continue
            for t, (season, base, bonus) in enumerate(
                    [y for y in _contract_years(league, c, first)]):
                if t >= horizon:
                    break
                v = _base_left(ctx, c, season, base)
                total += sign * w[t] * v
                parts["money"] += sign * w[t] * v
            if sign == 1:
                fut = sum(b for s, _x, b in _contract_years(league, c, ctx.S + 1)) / ctx.cap
                total -= DEAD_TIMING_K * fut
                parts["dead"] -= DEAD_TIMING_K * fut
    # Rights to re-sign young players (and a first-rounder's fifth-year option).
    for sign, players in ((1, gets_players), (-1, gives_players)):
        for p in players:
            c = league.contracts.get(p.id)
            ss = seasons_of.get(p.id, [])
            if not c or not ss:
                continue
            t_end = len(ss)
            age_then = M.age_on(p, first + t_end)
            if age_then > RIGHTS_AGE:
                continue
            s_then = proj[p.id][min(t_end, len(proj[p.id]) - 1)]
            prem = ctx.worth(p.position, s_then) - ctx.price(p.position, s_then)
            share = RIGHTS_SHARE
            if c["kind"] == "rookie" and p.draft_round == 1 and not c.get("option") and t_end <= 2:
                share = 1.0 + RIGHTS_SHARE * 0.5          # the option year, then the usual rights
            wt = w[min(t_end, len(w) - 1)]
            v = sign * wt * share * max(0.0, prem)
            total += v
            parts["rights"] += v
    total *= POINTS_PER_CAP
    for k in parts:
        parts[k] *= POINTS_PER_CAP
    pk_in = sum(pick_value(league, tid, k) for k in gets_picks)
    pk_out = sum(pick_value(league, tid, k) for k in gives_picks)
    total += pk_in - pk_out
    parts["picks"] = pk_in - pk_out
    if detail:
        return total, dict(parts)
    return total


def player_value(league, tid, p):
    """What a player on another team would add to this team (chart points), or for its
    own player, what losing him would cost (positive = he's an asset)."""
    from .evaluation import team_of
    if team_of(league, p.id) == tid:
        return -deal_delta(league, tid, gives_players=[p])
    return deal_delta(league, tid, gets_players=[p])


# ---------------------------------------------------------------------------
# Who can be traded; a deal's legality
# ---------------------------------------------------------------------------

def tradable(league, pid, tid=None):
    """(yes?, why not): on a team's roster (not a practice squad or reserve list) with a
    contract running this season."""
    if pid not in league.rosters:
        if pid in getattr(league, "practice", {}):
            return False, "Practice squad players can't be traded."
        if pid in getattr(league, "reserve", {}):
            return False, "Players on a reserve list can't be traded."
        return False, "He isn't on a roster."
    if tid is not None and league.rosters[pid] != tid:
        return False, "He's not on that team."
    c = league.contracts.get(pid)
    if not c or C.last_season(c) < league.season:
        return False, "He isn't under contract."
    if c["kind"] == "practice":
        return False, "Practice squad players can't be traded."
    return True, ""


def _side(d):
    return {"players": [int(x) for x in d.get("players", ())], "picks": list(d.get("picks", ()))}


def trade_charges(league, c):
    """{season: $K} the trading team keeps on its cap: the bonus money not yet counted
    (it all speeds onto this season's cap; after June 1 and during the season the
    later years' part goes onto next season's), and salary already paid this season."""
    S = league.season
    week = C.pay_week(league)
    cur = C._year(c, S)
    now = cur["bonus"] if cur else 0
    if cur and week:
        start = c["week"] if c["signed"] == S else 0
        now += C.base_counted(league, c, cur) * max(0, week - start) / C.PAY_WEEKS
    later = sum(y["bonus"] for y in c["years"] if y["season"] > S) + C.void_bonus(c)   # (void years too)
    if week > 0 or C.after_june1(league):
        out = {S: int(round(now))}
        if later:
            out[S + 1] = int(round(later))
    else:
        out = {S: int(round(now + later))}
    return {s: v for s, v in out.items() if v}


def _acquired_contract(league, c, tid):
    """The contract as the new team takes it over: the base salaries from now on (the
    bonus money stays behind)."""
    S = league.season
    week = C.pay_week(league)
    new = dict(c)
    years = [dict(y, bonus=0) for y in c["years"] if y["season"] >= S]
    new["years"] = years
    new["void"] = []           # (its void-year money stayed behind with the bonus)
    new["team"] = tid
    new["signed"] = S
    new["week"] = week if week else 0
    value = sum(y["base"] for y in years)
    new["value"] = value
    new["apy"] = int(round(value / max(1, len(years))))
    new["guaranteed"] = sum(y["gtd"] for y in years)
    new["signing_bonus"] = 0
    new["note"] = "acquired by trade"
    new["traded"] = True
    return new


def cap_effect(league, a, b, deal):
    """{team: {"room_before", "room_after", "dead"}} ($K, this season) for a deal where
    deal = {"a": side a gives, "b": side b gives}."""
    S = league.season
    out = {}
    # In camp and the preseason the top-51 rule still applies, but from week 1 the whole 53, the
    # practice squad and the reserve lists count: a team keeps CAMP_BUFFER of room for that.
    camp = getattr(league, "stage", "") == "preseason"
    for tid, give, get in ((a, deal["a"], deal["b"]), (b, deal["b"], deal["a"])):
        before = C.cap_room(league, tid) - (int(CAMP_BUFFER * C.cap_for(league, S)) if camp else 0)
        hits_out = sum(C.cap_hit(league, league.contracts[pid], S) for pid in give["players"]
                       if pid in league.contracts)
        dead = sum(trade_charges(league, league.contracts[pid]).get(S, 0) for pid in give["players"]
                   if pid in league.contracts)
        hits_in = 0
        for pid in get["players"]:
            c = league.contracts.get(pid)
            if c:
                hits_in += C.cap_hit(league, _acquired_contract(league, c, tid), S)
        out[tid] = {"room_before": before, "room_after": before + hits_out - dead - hits_in, "dead": dead,
                    "in": hits_in, "out": hits_out}
    return out


def _dry_run_room(league, a, b, deal):
    """Each team's cap room right after the trade, worked out exactly (the offseason's
    top-51 rule included) by making the money moves and undoing them."""
    S = league.season
    moved = deal["a"]["players"] + deal["b"]["players"]
    saved_c = {pid: league.contracts.get(pid) for pid in moved}
    saved_r = {pid: league.rosters.get(pid) for pid in moved}
    saved_ch = {tid: dict(league.cap_charges.get(tid, {})) for tid in (a, b)}
    camp = getattr(league, "stage", "") == "preseason"
    try:
        for give_tid, get_tid, side in ((a, b, deal["a"]), (b, a, deal["b"])):
            for pid in side["players"]:
                c = league.contracts.get(pid)
                if c is None:
                    continue
                for season, amount in trade_charges(league, c).items():
                    C.add_charge(league, give_tid, season, amount)
                league.contracts[pid] = _acquired_contract(league, c, get_tid)
                league.rosters[pid] = get_tid
        out = {tid: C.cap_room(league, tid) - (int(CAMP_BUFFER * C.cap_for(league, S)) if camp else 0)
               for tid in (a, b)}
    finally:
        for pid in moved:
            if saved_c[pid] is None:
                league.contracts.pop(pid, None)
            else:
                league.contracts[pid] = saved_c[pid]
            if saved_r[pid] is None:
                league.rosters.pop(pid, None)
            else:
                league.rosters[pid] = saved_r[pid]
        for tid in (a, b):
            league.cap_charges[tid] = saved_ch[tid]
    return out


def room_needed(league, give, get):
    """How many of your players you'd have to release for this deal to fit your roster."""
    from . import transactions as TR
    uid = league.user_team_id
    n = roster_after(league, uid, len(get["players"]), len(give["players"]))
    return max(0, n - TR.roster_limit(league)) if len(get["players"]) > len(give["players"]) else 0


def roster_after(league, tid, n_in, n_out):
    return sum(1 for t in league.rosters.values() if t == tid) + n_in - n_out


def check_deal(league, a, b, deal, ai_fix=True, release=()):
    """(legal?, why not) for a trade between teams a and b. ai_fix: an AI team over the
    roster limit cuts its least valuable player (you must make room first)."""
    from . import transactions as TR
    ok, why = window(league)
    if not ok:
        return False, why
    if a == b:
        return False, "Pick another team."
    ga, gb = deal["a"], deal["b"]
    if not (ga["players"] or ga["picks"]) or not (gb["players"] or gb["picks"]):
        return False, "Each side has to give something."
    for side, tid in ((ga, a), (gb, b)):
        if len(side["players"]) + len(side["picks"]) > MAX_SIDE:
            return False, f"At most {MAX_SIDE} players and picks on a side."
        for pid in side["players"]:
            ok, why = tradable(league, pid, tid)
            if not ok:
                return False, f"{league.player(pid).name}: {why}"
        seasons = pick_seasons(league)
        for k in side["picks"]:
            s, _r, _o = parse_key(k)
            if s not in seasons:
                return False, f"The {pick_label(league, k)} can't be traded now."
            if owner(league, k) != tid:
                return False, f"{league.team(tid).abbrev} doesn't own the {pick_label(league, k)}."
    cap = cap_effect(league, a, b, deal)
    exact = _dry_run_room(league, a, b, deal)
    for tid in (a, b):
        after = min(cap[tid]["room_after"], exact[tid])
        if after < 0 and _ai(league, tid):
            # An all-in AI team (or a money-pushing GM's) restructures to fit him, with void years
            # if it leans on them (Oct 26; real deadline deals: the Bills, the Dolphins).
            from . import free_agency as FA
            after += FA._restructure_left(league, tid)
        if after < 0 and after < cap[tid]["room_before"]:
            who = "You" if tid == league.user_team_id else league.team(tid).name
            return False, (f"{who} would be {C.fmt_money(-after)} over the salary cap "
                           f"after this trade.")
    limit = TR.roster_limit(league)
    for tid, n_in, n_out in ((a, len(gb["players"]), len(ga["players"])), (b, len(ga["players"]), len(gb["players"]))):
        n = roster_after(league, tid, n_in, n_out)
        if tid == league.user_team_id:
            n -= len([pid for pid in release if league.rosters.get(pid) == tid])
        if n > limit and n_in > n_out:
            if tid == league.user_team_id or not ai_fix:
                return False, (f"You'd have {n} players on a {limit}-man roster: release "
                               f"{plural(n - limit, 'player')} (pick who below, or on the Roster tab).")
    return True, ""


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


# ---------------------------------------------------------------------------
# Making a trade
# ---------------------------------------------------------------------------

def execute(league, a, b, deal, user=False, note=""):
    """Make the trade (check_deal first). Returns the log entry."""
    from . import transactions as TR
    t = ensure(league)
    S = league.season
    label = when_label(league)
    info = {}
    dead = {}
    for give_tid, get_tid, side in ((a, b, deal["a"]), (b, a, deal["b"])):
        for pid in side["players"]:
            p = league.player(pid)
            c = league.contracts[pid]
            info[str(pid)] = {"pos": p.position, "age": M.age_on(p, S), "exp": p.experience, "from": give_tid,
                              "apy": c["apy"], "years": C.years_left(c, S), "kind": c["kind"],
                              "cap": round(c["apy"] / C.cap_for(league, S), 4)}
            for season, amount in trade_charges(league, c).items():
                C.add_charge(league, give_tid, season, amount)
                if season == S:
                    dead[give_tid] = dead.get(give_tid, 0) + amount
            league.contracts[pid] = _acquired_contract(league, c, get_tid)
            league.rosters[pid] = get_tid
            if pid in league.injuries:
                league.injuries[pid]["team"] = get_tid
            if pid in getattr(league, "recovering", {}):
                league.recovering[pid]["team"] = get_tid
            TR.log(league, label, give_tid, pid, "Traded", f"to {league.team(get_tid).name}")
            TR.log(league, label, get_tid, pid, "Acquired in trade", f"from {league.team(give_tid).name}")
        for k in side["picks"]:
            t["picks"][k] = get_tid
    entry = {"id": len(t["log"]) + 1, "season": S, "when": label,
             "phase": (league.__dict__.get("_trade_phase") or phase_key(league)
                       or ("draft" if (league.offseason or {}).get("phase") == "drafting" else None)),
             "step": t["step"],
             "teams": [a, b], "gave": {"a": _side(deal["a"]), "b": _side(deal["b"])}, "user": bool(user),
             "info": info, "dead": {str(k): v for k, v in dead.items()}, "note": note,
             "picks": {k: {"num": pick_number(league, k), "label": pick_label(league, k)}
                       for k in deal["a"]["picks"] + deal["b"]["picks"]}}
    t["log"].append(entry)
    for tid in (a, b):
        if _ai(league, tid) and C.cap_room(league, tid) < 0:
            # (the restructure check_deal counted on: Oct 26)
            from . import free_agency as FA
            rng = random.Random(f"trade-room-{_salt(league)}-{S}-{t['step']}-{tid}")
            if not FA._make_room(league, tid, 0, rng):
                FA._comply(league, tid, rng, target=0.0, allow_cuts=False)    # (a little short: any restructure)
    _after(league, a, b, deal)
    room = (league.__dict__.get("_draft_day") or {}).get("room")
    if room is not None:
        room.needs = {}
    league.__dict__.pop("_trade_ctx", None)
    league.__dict__.pop("_trade_strength", None)
    return entry


def _after(league, a, b, deal):
    """Rosters and depth charts after a trade: an AI team over the limit cuts its least
    valuable player; captains who left are replaced by a new vote."""
    from . import transactions as TR
    label = when_label(league)
    limit = TR.roster_limit(league)
    for tid in (a, b):
        if tid != league.user_team_id:
            while sum(1 for x in league.rosters.values() if x == tid) > limit:
                incoming = set(deal["b"]["players"] if tid == a else deal["a"]["players"])
                cand = TR.release_candidate(league, league.injuries, tid, protect=incoming)
                if cand is None:
                    # (no one spare by the usual rules: the least valuable player who didn't just arrive)
                    pool = [league.player(x) for x, t2 in league.rosters.items() if t2 == tid and x not in incoming]
                    cand = min(pool, key=lambda q: TR.value(q, league, tid)) if pool else None
                if cand is None:
                    break
                _release_ai(league, tid, cand, label, "roster spot after a trade")
        moved = set(deal["a"]["players"] + deal["b"]["players"])
        caps = league.captains.get(tid, {})
        if any(v in moved for v in caps.values()):
            league.vote_captains(tid, rng=random.Random(f"captains-trade-{league.season}-{tid}-{len(ensure(league)['log'])}"))
        if tid == league.user_team_id:
            TR.refresh_user_chart(league, tid)
        else:
            league.auto_depth_chart(tid)


def _release_ai(league, tid, q, label, why):
    """An AI team lets a player go to make room: in the offseason as the spring's other
    cuts (free_agency._cap_cuts), during camp and the season through waivers."""
    from . import transactions as TR
    from . import free_agency as FA
    C.release(league, q.id)
    if getattr(league, "stage", "") == "offseason":
        FA._let_go(league, q.id, tid, "UFA" if q.experience >= C.RFA + 1 else FA._status(q), f"released ({why})")
        TR.log(league, label, tid, q.id, "Released", why)
    else:
        TR.release(league, q.id, _cal(league), label, why)


def _trim_rosters(league):
    """AI teams over the offseason's 90 (extra draft picks, from trades) cut their least
    valuable players, as real teams do when they sign their rookies."""
    from . import transactions as TR
    if getattr(league, "stage", "") != "offseason" or not TR.in_camp(league):
        return
    limit = TR.roster_limit(league)
    label = when_label(league)
    cut = False
    for team in league.teams:
        tid = team.id
        if tid == league.user_team_id:
            continue
        while sum(1 for x in league.rosters.values() if x == tid) > limit:
            pool = [league.player(x) for x, t2 in league.rosters.items() if t2 == tid]
            q = min(pool, key=lambda q: TR.value(q, league, tid))
            _release_ai(league, tid, q, label, "roster limit")
            cut = True
    if cut:
        league.__dict__.pop("_trade_ctx", None)


def _cal(league):
    from .season import calendar
    try:
        return calendar(league)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# AI teams trading with each other
# ---------------------------------------------------------------------------

def _need_list(league, ctx, tid):
    """[(need, position, kind)] this team's holes, biggest first: kind "starter" (its
    worst starter there falls short of a typical starter) or "backup" (its first backup
    falls short of a typical first backup). need: the shortfall as a share of what a
    typical player in that role is worth, so a hole at any position counts."""
    out = []
    for pos, n in STARTERS.items():
        g = ctx.group(tid, pos)
        floor = ctx.floor_score(pos)
        worst = g[n - 1][0] if len(g) >= n else floor
        backup = g[n][0] if len(g) > n else floor
        spec = (SPECIALIST_NEED if pos in ("K", "P", "LS", "FB") else 1.0) * POSITION_MARKET.get(pos, 1.0)
        # In rating points (a hole at any position counts; pay can't show it: backups all earn
        # about the minimum), NEED_POINTS short of a typical player in the role = a need of 1.
        need = (_typical(ctx, pos) - worst) / NEED_POINTS
        if need > STARTER_HOLE:
            out.append((need * spec, pos, "starter"))
        need_b = (_typical_backup(ctx, pos) - backup) / NEED_POINTS
        if need_b > 0.25 and pos not in ("K", "P", "LS"):
            out.append((BACKUP_NEED * need_b * spec, pos, "backup"))
    out.sort(reverse=True)
    return out


def _typical_backup(ctx, pos):
    k = ("typical_b", pos)
    if k not in ctx._scores:
        neg, _r = ctx.curve.get(pos, ([], []))
        n = len(neg)
        i = min(n - 1, int(32 * STARTERS.get(pos, 1) + 16)) if n else 0
        ctx._scores[k] = -neg[i] if n else 45.0
    return ctx._scores[k]


def _typical(ctx, pos):
    k = ("typical", pos)
    if k not in ctx._scores:
        neg, _r = ctx.curve.get(pos, ([], []))
        n = len(neg)
        i = min(n - 1, int(32 * STARTERS.get(pos, 1) * 0.5)) if n else 0
        ctx._scores[k] = -neg[i] if n else 50.0
    return ctx._scores[k]


def _ai(league, tid):
    return tid is not None and tid != league.user_team_id


def just_traded(league, pid):
    """Did he change teams by trade this league year? (AI teams don't flip a player they
    just traded for.)"""
    memo = league.__dict__.setdefault("_trade_recent", {})
    t = ensure(league)
    key = (league.season, len(t["log"]))
    if memo.get("key") != key:
        memo["key"] = key
        memo["ids"] = {pid_ for e in t["log"] if e["season"] == league.season
                       for side in ("a", "b") for pid_ in e["gave"][side]["players"]}
    return pid in memo["ids"]


def _package(league, buyer, seller, target_s, ceiling_b, exclude_players=(), players_ok=True):
    """The buyer's assets that give the seller at least target_s (seller's value)
    without costing the buyer more than ceiling_b (buyer's value): picks (fewest, the
    nearest drafts, closest to the target), or one of the buyer's players the seller
    wants, alone or with a pick. Returns (picks, players) or None."""
    from itertools import combinations
    picks = team_picks(league, buyer)
    if not picks:
        return None
    vs = {k: pick_value(league, seller, k) for k in picks}
    vb = {k: pick_value(league, buyer, k) for k in picks}
    first = min(parse_key(k)[0] for k in picks)
    far = {k: parse_key(k)[0] - first for k in picks}
    if target_s <= 0:
        # Nothing really owed: his latest pick in the next draft (the usual "for a 7th").
        near = [k for k in picks if far[k] == 0] or picks
        k = min(near, key=lambda k: vb[k])
        return ([k], []) if vb[k] <= max(ceiling_b, 5.0) else None
    options = []
    cands = sorted(picks, key=lambda k: vs[k])
    for n in (1, 2, 3):
        pool = cands if n == 1 else cands[-14:]
        for combo in combinations(pool, n):
            s_val = sum(vs[k] for k in combo)
            b_val = sum(vb[k] for k in combo)
            if s_val >= target_s and b_val <= ceiling_b:
                cost = ((s_val - target_s) + FAR_PENALTY * sum(far[k] for k in combo) * max(target_s, FAR_MIN)
                        + EXTRA_ITEM * (n - 1))
                options.append((cost, list(combo), []))
        if options and n >= 2:
            break
    if players_ok:
        ctx = _ctx(league)
        wants = {x[1] for x in _need_list(league, ctx, seller)[:6]}
        mine = [pid for pid, t in league.rosters.items() if t == buyer and pid not in exclude_players
                and league.player(pid).position in wants and tradable(league, pid, buyer)[0]
                and not (_ai(league, buyer) and just_traded(league, pid))]
        scored = []
        for pid in mine:
            sv = deal_delta(league, seller, gets_players=[pid])
            if sv > 10:
                scored.append((sv, pid))
        scored.sort(reverse=True)
        for sv, pid in scored[:4]:
            bv = -deal_delta(league, buyer, gives_players=[pid])
            if sv >= target_s and bv <= ceiling_b:
                options.append(((sv - target_s) + PLAYER_ITEM, [], [pid]))
                continue
            for k in cands:
                if sv + vs[k] >= target_s and bv + vb[k] <= ceiling_b:
                    options.append(((sv + vs[k] - target_s) + PLAYER_ITEM + EXTRA_ITEM
                                    + FAR_PENALTY * far[k] * max(target_s, FAR_MIN), [k], [pid]))
                    break
    if not options:
        return None
    options.sort(key=lambda o: o[0])
    return options[0][1], options[0][2]


def _try(league, buyer, seller, pid, margin=AI_MARGIN, rng=None, at_least=0.0):
    """Would AI teams `buyer` and `seller` make a deal for this player, and at what
    price? Returns the deal ({"a": seller gives, "b": buyer gives}) or None."""
    p = league.player(pid)
    gain = deal_delta(league, buyer, gets_players=[p])
    loss = -deal_delta(league, seller, gives_players=[p])
    if gain <= margin[0]:
        return None
    loss *= 1 + seller_premium(league, seller, p, loss)
    floor = loss + margin[0] + margin[1] * max(0.0, loss)
    c = league.contracts.get(pid)
    if c and c["apy"] >= STAR_AUCTION_CAP * C.cap_for(league, league.season) and not at_least:
        # A player on a big deal draws calls from several teams: the seller gets about what the
        # next-keenest would have paid (real: 46% of players on 10%+ deals traded for picks bring
        # back a 1st; before this the game's went mostly as salary dumps for late picks).
        others = [t.id for t in league.teams if _ai(league, t.id) and t.id not in (buyer, seller)]
        r2 = random.Random(f"auction-{_salt(league)}-{ensure(league)['step']}-{pid}")
        bids = sorted([gain] + [deal_delta(league, o, gets_players=[p]) for o in r2.sample(others, min(8, len(others)))],
                      reverse=True)
        if len(bids) > 1:
            at_least = AUCTION * bids[1]          # about what the second-keenest team would pay
    ceiling = gain - margin[0] - margin[1] * max(0.0, gain)
    if ceiling < floor:
        return None
    target = max(floor + PRICE_SPLIT * (ceiling - floor), min(at_least, ceiling))
    # (a seller glad to move him still gets part of what he's worth to the buyer; with nothing
    # owed at all, the buyer's latest pick: "for a 7th")
    pkg = _package(league, buyer, seller, target if target > 0 else floor, ceiling)
    if pkg is None and floor > 0:
        pkg = _package(league, buyer, seller, floor, ceiling)
    if pkg is None:
        return None
    picks, players = pkg
    deal = {"a": {"players": [pid], "picks": []}, "b": {"players": players, "picks": picks}}
    ok, _why = check_deal(league, seller, buyer, deal)
    if not ok:
        return None
    return deal


def seller_premium(league, seller, p, loss):
    """Share over what losing him costs that a team wants before it trades one of its
    starters (more for a young one); none for a rebuilding team's veterans or a player
    it would be glad to move."""
    if loss <= 0:
        return 0.0
    ctx = _ctx(league)
    g = ctx.group(seller, p.position)
    n = STARTERS.get(p.position, 1)
    if p.id not in [pid for _s, pid in g[:n]]:
        return 0.0
    age = M.age_on(p, league.season)
    if _approach(league, seller) == "rebuild" and age >= REBUILD_SELL_AGE:
        return 0.0
    return STARTER_PREMIUM + (YOUNG_PREMIUM if age <= 25 else 0.0)


def _callers(league, ctx, phase, rng, n_calls):
    """Teams that pick up the phone this step: needy teams more, trading GMs more,
    contenders buying and sellers selling in-season."""
    teams = [t.id for t in league.teams if _ai(league, t.id)]
    w = []
    for tid in teams:
        needs = _need_list(league, ctx, tid)
        need = needs[0][0] if needs else 0.0
        x = 0.3 + min(3.0, need)
        if getattr(league, "staff", None):
            from . import gm as G
            x *= math.exp(GM_ACTIVE_K * abs(G.style(league, tid, "trade")))
        w.append(x)
    calls = []
    for _ in range(n_calls):
        calls.append(rng.choices(teams, weights=w)[0])
    return calls


def _sellers_for(league, ctx, tid, rng):
    """A team shopping its own players: rebuilding teams their veterans; any team its
    surplus (a third good QB, depth it can't keep)."""
    out = []
    way = _approach(league, tid)
    for pid, t in league.rosters.items():
        if t != tid:
            continue
        p = league.player(pid)
        c = league.contracts.get(pid)
        if not c or c["kind"] == "practice" or just_traded(league, pid):
            continue
        age = M.age_on(p, league.season)
        if way == "rebuild" and age >= 28 and ctx.score(tid, p) >= _typical(ctx, p.position) - 4:
            out.append(pid)
    return out


def ai_step(league, rng=None, report=None, phase=None):
    """AI teams call each other this step: a team with a hole looks at players on other
    AI teams who'd fill it (or a rebuilding team shops a veteran) and they deal when
    both come out ahead in their own eyes. Returns the trades made."""
    ok, _why = window(league)
    if not ok:
        return []
    phase = phase or phase_key(league)
    if phase is None:
        return []
    rng = rng or random.Random(f"trades-{_salt(league)}-{league.season}-{ensure(league)['step']}")
    base = CALLS.get(phase, 0.0)
    if phase == "season":
        weeks_before = deadline_week(league) - (league.week - 1)
        base *= SEASON_RAMP.get(weeks_before, 1.0) if weeks_before >= 1 else 1.0
        if weeks_before == 1:
            base = CALLS["deadline"] * 0.35
    lam = base * CALLS_K
    n_calls = _poisson(rng, lam)
    made = []
    if n_calls == 0:
        return made
    ctx = _ctx(league)
    for buyer in _callers(league, ctx, phase, rng, n_calls):
        ctx = _ctx(league)
        deal = None
        seller = None
        why = ""
        if _approach(league, buyer) == "rebuild" and rng.random() < 0.4:
            # A seller's call: shop a veteran to the teams he'd help most.
            mine = _sellers_for(league, ctx, buyer, rng)
            if mine:
                pid = rng.choice(mine)
                pos = league.player(pid).position
                buyers = [t.id for t in league.teams if _ai(league, t.id) and t.id != buyer]
                rng.shuffle(buyers)
                # He takes calls from several teams: the keenest buyer pays about what the
                # next-keenest would have (a real seller's auction).
                bids = sorted(((deal_delta(league, b, gets_players=[pid]), b) for b in buyers[:10]), reverse=True)
                if bids and bids[0][0] > AI_MARGIN[0]:
                    second = bids[1][0] if len(bids) > 1 else 0.0
                    d = _try(league, bids[0][1], buyer, pid, rng=rng, at_least=AUCTION * second)
                    if d is not None:
                        deal = d
                        seller, buyer = buyer, bids[0][1]
                        why = "selling a veteran"
        if deal is None:
            needs = _need_list(league, ctx, buyer)
            if not needs:
                continue
            _n, pos, kind = rng.choices(needs[:5], weights=[x[0] for x in needs[:5]])[0]
            g = ctx.group(buyer, pos)
            n = STARTERS[pos]
            worst = g[n - 1][0] if len(g) >= n else ctx.floor_score(pos)
            backup = g[n][0] if len(g) > n else ctx.floor_score(pos)
            lo, hi = (worst + 1.0, 999) if kind == "starter" else (backup + 1.0, worst + 3.0)
            cands = []
            for pid, t in league.rosters.items():
                if t == buyer or not _ai(league, t):
                    continue
                p = league.player(pid)
                if p.position != pos or not tradable(league, pid, t)[0] or just_traded(league, pid):
                    continue
                s = ctx.proj(buyer, p, 1)[0]
                if lo < s < hi:
                    starts = pid in [q for _x, q in ctx.group(t, pos)[:STARTERS[pos]]]
                    cands.append((s - lo + rng.gauss(0, 2.0), pid, t, starts))
            cands.sort(reverse=True)
            # Look at a few of the better fits, not always the very best (calls are spread around),
            # mostly players who don't start for their team (another team's spare player is what a
            # buyer usually gets; real trades are mostly depth for late picks).
            spare = [c for c in cands[:CANDIDATES * 4] if not c[3]]
            start = [c for c in cands[:CANDIDATES * 4] if c[3]]
            rng.shuffle(spare)
            rng.shuffle(start)
            n_start = sum(1 for _ in range(CANDIDATES) if rng.random() < STARTER_LOOK)
            tried = sorted(start[:n_start] + spare[:CANDIDATES - n_start], reverse=True)
            tried = [(x, pid, t) for x, pid, t, _st in tried]
            options = []
            for _s, pid, t in tried:
                d = _try(league, buyer, t, pid, rng=rng)
                if d is not None:
                    paid = sum(pick_value(league, buyer, k) for k in d["b"]["picks"])
                    if d["b"]["players"]:
                        paid -= deal_delta(league, buyer, gives_players=d["b"]["players"])
                    options.append((paid, t, d))
            if options:
                # The cheapest deal that fills the hole (GMs shop for value, not headlines).
                options.sort(key=lambda o: o[0])
                _paid, seller, deal = options[0]
                why = f"{kind} at {pos}"
        if deal is None:
            continue
        entry = execute(league, seller, buyer, deal, note=why)
        made.append(entry)
        if report is not None:
            report.append(entry)
    return made


def _poisson(rng, lam):
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


# ---------------------------------------------------------------------------
# Your calls: the AI answers in words
# ---------------------------------------------------------------------------

def _gm_name(league, tid):
    from . import gm as G
    p = G.gm_of(league, tid)
    return p["name"] if p else f"The {league.team(tid).nickname} GM"


def _patience(league, tid):
    from . import gm as G
    p = G.gm_of(league, tid)
    key = p["id"] if p else tid
    r = random.Random(f"trade-patience-{_salt(league)}-{key}")
    return r.randint(*PATIENCE)


def listening(league, tid):
    """(listening?, words): a GM you've insulted too often won't take your calls for a while."""
    t = ensure(league)
    m = t["mood"].get(str(tid))
    if m and m.get("until", -1) > t["step"]:
        return False, f"{_gm_name(league, tid)} isn't taking your calls right now."
    return True, ""


def _insult(league, tid, n=1):
    t = ensure(league)
    m = t["mood"].setdefault(str(tid), {"insults": 0, "until": -1})
    m["insults"] = m.get("insults", 0) + n
    if m["insults"] >= _patience(league, tid):
        m["until"] = t["step"] + COOL_OFF
        m["insults"] = 0
        return True
    return False


def mood_words(league, tid):
    """How the GM feels about your calls, in words (for the trade screen)."""
    t = ensure(league)
    ok, words = listening(league, tid)
    if not ok:
        return words
    m = t["mood"].get(str(tid)) or {}
    n = m.get("insults", 0)
    if n == 0:
        return "Open to talking."
    if n >= _patience(league, tid) - 1:
        return "Losing patience with your offers."
    return "A little wary after your last offer."


def _say(league, tid, kind, rng):
    gm = _gm_name(league, tid).split()[-1]
    lines = {
        "accept": ["You've got a deal.", "That works for us. Let's do it.", "Done. Send it in.",
                   "We can live with that. Deal.", "Yeah, we'll do that one."],
        "close": ["We're close. Add a little something and we can get it done.",
                  "Not quite there. A little more and it's a deal.",
                  "You're in the neighborhood. Sweeten it a bit.",
                  "Close. Give us a little more and we'll talk."],
        "counter": ["Not like that. Here's what we'd do:", "We'd need more. How about this:",
                    "Can't do it as is. This one works for us:", "Here's where we'd be:"],
        "no": ["We're not interested.", "I'll pass.", "That doesn't work for us.", "No thanks.",
               "We're going to say no to that one."],
        "lowball": ["Come on. That's not a real offer.", "Is this a joke?", "You'll have to do a lot better than that.",
                    "I'm not even going to take that to the owner."],
        "last": ["Call me back when you're serious.", "I'm done with these offers for a while.",
                 "We're not going to keep doing this. Lose my number for a bit."],
        "gone": ["He's not taking your calls right now."],
        "unavailable": ["He's not available.", "We're not moving him.", "He's not going anywhere."],
    }[kind]
    return rng.choice(lines)


def answer(league, other, give, get, rng=None, release=()):
    """You offer `give` (your players and picks) for `get` (theirs). The other team's
    GM answers like a phone call:
      {"kind": "accept" | "close" | "counter" | "no" | "lowball" | "gone" | "illegal",
       "words": what he says, "counter": a deal he'd make instead (or None),
       "gm": his name}
    No numbers: you hear what a real GM would tell you."""
    uid = league.user_team_id
    give, get = _side(give), _side(get)
    rng = rng or random.Random(f"answer-{_salt(league)}-{ensure(league)['step']}-{other}-"
                               f"{sorted(give['players'])}-{sorted(give['picks'])}-{sorted(get['players'])}-"
                               f"{sorted(get['picks'])}")
    gm = _gm_name(league, other)
    ok, words = listening(league, other)
    if not ok:
        return {"kind": "gone", "words": words, "counter": None, "gm": gm}
    deal = {"a": give, "b": get}
    ok, why = check_deal(league, uid, other, deal, release=release)
    if not ok:
        return {"kind": "illegal", "words": why, "counter": None, "gm": gm}
    delta = deal_delta(league, other, gets_players=give["players"], gives_players=get["players"],
                       gets_picks=give["picks"], gives_picks=get["picks"])
    gives_val = max(0.0, -deal_delta(league, other, gives_players=get["players"], gives_picks=get["picks"]))
    need = _need(league, other, get, gives_val)
    if delta >= need:
        return {"kind": "accept", "words": _say(league, other, "accept", rng), "counter": None, "gm": gm,
                "deal": deal}
    short = need - delta
    received = delta + gives_val             # what your side is worth to them
    ratio = received / max(1.0, gives_val + need)
    # A core player it won't move for what you've put on the table.
    core = max((-deal_delta(league, other, gives_players=[pid]) for pid in get["players"]), default=0.0)
    if ratio < INSULT_SHARE and gives_val > 30:
        stopped = _insult(league, other)
        return {"kind": "lowball", "words": _say(league, other, "last" if stopped else "lowball", rng),
                "counter": None, "gm": gm}
    if core >= STAR_LOCK and ratio < STAR_LOCK_RATIO and _approach(league, other) != "rebuild":
        return {"kind": "no", "words": _say(league, other, "unavailable", rng), "counter": None, "gm": gm}
    if short <= max(CLOSE_POINTS, CLOSE_SHARE * max(need, gives_val)):
        counter = counter_offer(league, other, give, get, short)
        return {"kind": "close", "words": _say(league, other, "close", rng), "counter": counter, "gm": gm}
    counter = counter_offer(league, other, give, get, short)
    if counter:
        return {"kind": "counter", "words": _say(league, other, "counter", rng), "counter": counter, "gm": gm}
    return {"kind": "no", "words": _say(league, other, "no", rng), "counter": None, "gm": gm}


def counter_offer(league, other, give, get, short):
    """A deal the AI team would take: your offer plus the smallest of your picks (or a
    player of yours it likes) that makes up what's missing; failing that, your offer for
    less of theirs. None if nothing works."""
    uid = league.user_team_id
    need_extra = short
    # 1. Add one of your picks (or two).
    mine = [k for k in team_picks(league, uid) if k not in give["picks"]]
    vals = sorted(((pick_value(league, other, k), k) for k in mine))
    for v, k in vals:
        if v >= need_extra:
            cand = {"players": list(give["players"]), "picks": give["picks"] + [k]}
            if _accepts(league, other, cand, get):
                return {"a": cand, "b": get}
            break
    for i, (v1, k1) in enumerate(vals):
        for v2, k2 in vals[i + 1:]:
            if v1 + v2 >= need_extra and len(give["players"]) + len(give["picks"]) + 2 <= MAX_SIDE:
                cand = {"players": list(give["players"]), "picks": give["picks"] + [k1, k2]}
                if _accepts(league, other, cand, get):
                    return {"a": cand, "b": get}
                break
    # 2. One of your players it would want (a fit for its needs), cheapest that works.
    ctx = _ctx(league)
    needs = {x[1] for x in _need_list(league, ctx, other)[:6]}
    yours = [pid for pid, t in league.rosters.items() if t == uid and pid not in give["players"]
             and tradable(league, pid, uid)[0] and league.player(pid).position in needs]
    scored = []
    for pid in yours:
        v = deal_delta(league, other, gets_players=[pid])
        if v > 0:
            scored.append((v, pid))
    scored.sort()
    for v, pid in scored:
        if v >= need_extra:
            cand = {"players": give["players"] + [pid], "picks": list(give["picks"])}
            if _accepts(league, other, cand, get):
                return {"a": cand, "b": get}
    # 3. Less of theirs: drop one of their picks or players.
    for k in sorted(get["picks"], key=lambda k: -pick_value(league, other, k)):
        cand_get = {"players": list(get["players"]), "picks": [x for x in get["picks"] if x != k]}
        if (cand_get["players"] or cand_get["picks"]) and _accepts(league, other, give, cand_get):
            return {"a": give, "b": cand_get}
    for pid in get["players"]:
        cand_get = {"players": [x for x in get["players"] if x != pid], "picks": list(get["picks"])}
        if (cand_get["players"] or cand_get["picks"]) and _accepts(league, other, give, cand_get):
            return {"a": give, "b": cand_get}
    return None


def _market_floor(league, other, players):
    """Extra an AI team wants from you for its players beyond its own loss: up to what the
    keenest other AI team would pay for each (MARKET_SHARE of it)."""
    uid = league.user_team_id
    extra = 0.0
    for pid in players:
        loss = -deal_delta(league, other, gives_players=[pid])
        best = max((deal_delta(league, o.id, gets_players=[pid]) for o in league.teams if o.id not in (uid, other)),
                   default=0.0)
        extra += max(0.0, MARKET_SHARE * best - max(0.0, loss))
    return extra


def _need(league, other, get, gives_val):
    """What the AI team needs to come out ahead by (points) on a deal with you."""
    return USER_MARGIN[0] + USER_MARGIN[1] * gives_val + _market_floor(league, other, get["players"])


def _accepts(league, other, give, get, release=()):
    deal = {"a": give, "b": get}
    if not check_deal(league, league.user_team_id, other, deal, release=release)[0]:
        return False
    delta = deal_delta(league, other, gets_players=give["players"], gives_players=get["players"],
                       gets_picks=give["picks"], gives_picks=get["picks"])
    gives_val = max(0.0, -deal_delta(league, other, gives_players=get["players"], gives_picks=get["picks"]))
    return delta >= _need(league, other, get, gives_val)


def make_user_trade(league, other, give, get, release=()):
    """You and the AI team agreed (answer() said accept, or you took its counter or
    offer): make it. release: players of yours to cut right after, to make room on a
    full roster (they can't be in the trade). (done?, message, log entry)."""
    from . import free_agency as FA
    uid = league.user_team_id
    give, get = _side(give), _side(get)
    release = [int(pid) for pid in release if int(pid) not in give["players"]]
    for pid in release:
        why = FA.release_block(league, pid)
        if league.rosters.get(pid) != uid or why:
            return False, f"{league.player(pid).name} can't be released: {why or 'not on your roster'}", None
    if not _accepts(league, other, give, get, release):
        return False, "They won't do that deal.", None
    deal = {"a": give, "b": get}
    ok, why = check_deal(league, uid, other, deal, release=release)
    if not ok:
        return False, why, None
    entry = execute(league, uid, other, deal, user=True)
    FA.sync(league, when_label(league))
    msg = describe(league, entry)
    for pid in release:
        done, m = FA.your_release(league, pid)
        msg += " " + m
    return True, msg, entry


def back_out(league, other):
    """You agreed and then walked away: GMs don't like that (FOF8)."""
    _insult(league, other, BACKOUT_COUNTS)


# ---------------------------------------------------------------------------
# AI teams calling you; shopping your players
# ---------------------------------------------------------------------------

def _user_view_loss(league, other, pid):
    """What the AI team thinks you'd lose (it sees your roster through its own eyes,
    your timeline as normal)."""
    uid = league.user_team_id
    ctx = _ctx(league)
    p = league.player(pid)
    # Your group as the caller sees it.
    pos = p.position
    rows = sorted(((ctx.score(other, league.player(q)), q) for q, t in league.rosters.items()
                   if t == uid and league.player(q).position == pos), reverse=True)
    before = [s for s, _q in rows]
    after = [s for s, q in rows if q != pid]
    w = ctx.weights(uid, 4)
    c = league.contracts.get(pid)
    seasons = _seasons(ctx, c) if c else []
    proj = ctx.proj(other, p, max(1, len(seasons)))
    total = 0.0
    for t, season in enumerate(seasons[:4]):
        b = [s if q != pid else proj[t] for s, q in rows]
        total += w[t] * (ctx.group_value(pos, b) - ctx.group_value(pos, after))
        base = next((y["base"] for y in c["years"] if y["season"] == season), 0)
        total -= w[t] * _base_left(ctx, c, season, base)
    return total * POINTS_PER_CAP


def _offer_for(league, other, pid, rng, sweeten=None):
    """The AI team's offer for your player: what it would give (picks, or one of its
    players you might want), or None."""
    uid = league.user_team_id
    gain = deal_delta(league, other, gets_players=[pid])
    loss_est = _user_view_loss(league, other, pid)
    ceiling = gain - USER_MARGIN[0] - USER_MARGIN[1] * max(0.0, gain)
    lo, hi = OFFER_SWEETEN
    s = sweeten if sweeten is not None else rng.uniform(lo, hi)
    target = max(0.0, loss_est) * (1 + s) + 5.0
    if ceiling <= 0 or ceiling < target * 0.85:
        return None
    pkg = _package(league, other, uid, min(target, ceiling), ceiling)
    if pkg is None:
        return None
    picks, players = pkg
    deal = {"a": {"players": [pid], "picks": []}, "b": {"players": players, "picks": picks}}
    if not check_deal(league, uid, other, deal)[0]:
        return None
    return deal


def interest_words(ratio):
    return ("Very interested" if ratio >= 1.6 else "Interested" if ratio >= 1.15 else
            "Some interest" if ratio >= 0.9 else "Little interest")


def shop(league, pid, rng=None):
    """You shop one of your players around: every AI team that wants him, how keen
    it is (in words) and its best offer. [{"team", "gm", "interest", "deal"}], keenest
    first. The league hears about it (a rumor on Bitter)."""
    uid = league.user_team_id
    t = ensure(league)
    ok, why = window(league)
    if not ok:
        return []
    ok, why = tradable(league, pid, uid)
    if not ok:
        return []
    rng = rng or random.Random(f"shop-{_salt(league)}-{t['step']}-{pid}")
    out = []
    for team in league.teams:
        o = team.id
        if o == uid or not listening(league, o)[0]:
            continue
        gain = deal_delta(league, o, gets_players=[pid])
        if gain <= 10:
            continue
        deal = _offer_for(league, o, pid, rng, sweeten=0.0)
        if deal is None:
            continue
        loss_est = max(1.0, _user_view_loss(league, o, pid))
        out.append({"team": o, "gm": _gm_name(league, o), "interest": interest_words(gain / (loss_est + 20)),
                    "deal": deal, "keen": gain})
    out.sort(key=lambda r: -r["keen"])
    for r in out:
        r.pop("keen")
    t["shopped"][str(pid)] = {"step": t["step"], "season": league.season, "when": when_label(league), "team": uid}
    return out


def user_calls(league, rng=None, phase=None):
    """AI teams call you this step with offers (each good until the next step):
    a team with a hole at a position where you have a player it likes, often one you
    have to spare. Returns the new offers."""
    uid = league.user_team_id
    t = ensure(league)
    if uid is None or not window(league)[0]:
        return []
    phase = phase or phase_key(league)
    if phase is None:
        return []
    rng = rng or random.Random(f"calls-{_salt(league)}-{league.season}-{t['step']}")
    lam = USER_CALLS.get(phase, 0.0)
    if phase == "season":
        weeks_before = deadline_week(league) - (league.week - 1)
        lam *= SEASON_RAMP.get(weeks_before, 1.0) if weeks_before >= 1 else 1.0
    n = _poisson(rng, lam)
    made = []
    if not n:
        return made
    ctx = _ctx(league)
    teams = [x.id for x in league.teams if _ai(league, x.id)]
    rng.shuffle(teams)
    for o in teams:
        if len(made) >= n:
            break
        needs = _need_list(league, ctx, o)[:5]
        if not needs:
            continue
        want = {x[1] for x in needs}
        mine = []
        for pid, tt in league.rosters.items():
            if tt != uid or league.player(pid).position not in want or not tradable(league, pid, uid)[0]:
                continue
            gain = deal_delta(league, o, gets_players=[pid])
            if gain > 15:
                # players you have to spare first: what you'd lose (as they see it) is small next to what they'd gain
                spare = gain - max(0.0, _user_view_loss(league, o, pid))
                mine.append((spare + rng.gauss(0, 15), pid))
        if not mine:
            continue
        mine.sort(reverse=True)
        for _s, pid in mine[:3]:
            deal = _offer_for(league, o, pid, rng)
            if deal is not None and not any(x["team"] == o and x.get("status") in (None, "open") for x in t["inbox"]):
                # As you'll see it: you give "a", they give "b".
                offer = {"id": f"{league.season}-{t['step']}-{o}-{pid}", "team": o, "gm": _gm_name(league, o),
                         "step": t["step"], "when": when_label(league), "give": deal["a"], "get": deal["b"],
                         "note": _call_note(league, o, pid, rng)}
                t["inbox"].append(offer)
                made.append(offer)
                break
    return made


def _call_note(league, o, pid, rng):
    p = league.player(pid)
    from .news import POS_WORD
    pw = POS_WORD.get(p.position, p.position)
    return rng.choice([
        f"We're looking for help at {pw}, and we like {p.name}. Here's what we can do.",
        f"Got a minute? We'd like to talk about {p.name}.",
        f"We've had our eye on {p.name} for a while. Would this get it done?",
        f"You've got {p.name} and we've got a need. Take a look at this.",
        f"Our staff likes {p.name}. Here's our offer.",
    ])


def inbox(league):
    """AI teams' offers to you that are still good (newest first)."""
    t = ensure(league)
    return [o for o in reversed(t["inbox"]) if o.get("status") in (None, "open")]


def take_offer(league, offer_id, release=()):
    """You accept one of the AI offers in your inbox. (done?, message)."""
    t = ensure(league)
    o = next((x for x in t["inbox"] if x["id"] == offer_id and x.get("status") in (None, "open")), None)
    if o is None:
        return False, "That offer isn't there anymore."
    ok, msg, _e = make_user_trade(league, o["team"], o["give"], o["get"], release=release)
    o["status"] = "taken" if ok else o.get("status")
    if ok:
        for x in t["inbox"]:
            if x is not o and x.get("status") in (None, "open") and (
                    set(x["give"]["players"]) & set(o["give"]["players"])
                    or set(x["give"]["picks"]) & set(o["give"]["picks"])):
                x["status"] = "gone"
    return ok, msg


def decline_offer(league, offer_id):
    t = ensure(league)
    for x in t["inbox"]:
        if x["id"] == offer_id:
            x["status"] = "declined"
    return True


def _expire(league):
    t = ensure(league)
    for x in t["inbox"]:
        if x.get("status") in (None, "open") and x["step"] < t["step"]:
            x["status"] = "expired"
    t["inbox"] = [x for x in t["inbox"] if x["step"] >= t["step"] - 30]


# ---------------------------------------------------------------------------
# The steps (called from the season and the offseason)
# ---------------------------------------------------------------------------

def step(league, rng=None, phase=None):
    """One decision point: offers to you expire, AI teams trade with each other, and
    some call you. Called after each offseason phase and each preseason and
    regular-season week (season.end_week, offseason.offseason_next), and as the draft
    opens (phase "draft": real teams make 1-2 trades with players a draft)."""
    t = ensure(league)
    if not getattr(league, "contracts", None):
        return []
    t["step"] += 1
    _expire(league)
    _trim_rosters(league)
    if not window(league)[0]:
        return []
    r = rng or random.Random(f"trade-step-{_salt(league)}-{league.season}-{t['step']}")
    league.__dict__["_trade_phase"] = phase
    try:
        made = ai_step(league, random.Random(r.random()), phase=phase)
        if league.user_team_id is not None:
            user_calls(league, random.Random(r.random()), phase=phase)
    finally:
        league.__dict__.pop("_trade_phase", None)
    if made:
        from . import free_agency as FA
        FA.sync(league, when_label(league))
    return made


# ---------------------------------------------------------------------------
# Words for screens and news
# ---------------------------------------------------------------------------

def side_text(league, side, short=False):
    bits = []
    for pid in side["players"]:
        p = league.player(pid)
        bits.append(f"{p.position} {p.name}")
    for k in side["picks"]:
        bits.append(pick_label(league, k, short=short))
    return ", ".join(bits) if bits else "nothing"


def describe(league, entry):
    a, b = entry["teams"]
    ga, gb = entry["gave"]["a"], entry["gave"]["b"]
    return (f"Trade: {league.team(a).name} send {side_text(league, ga)} to the {league.team(b).name} for "
            f"{side_text(league, gb)}.")


def log(league, season=None, team=None):
    t = ensure(league)
    return [e for e in t["log"] if (season is None or e["season"] == season)
            and (team is None or team in e["teams"])]
