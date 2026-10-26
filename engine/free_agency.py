# free_agency.py
# Who gets paid what, and who goes where: the AI side of contracts.
#
#   initial_contracts(league)   a new league's contracts, set up like a real league's
#   league_year_start(league)   the new league year: the cap, contracts that ran out,
#                               reserve/future deals, fifth-year options, extensions,
#                               re-signings (each team's exclusive window), franchise
#                               tags, restricted tenders, cap cuts, getting under the cap
#   market(league, waves)       free agency, in waves: teams bid, players choose
#   sign_draft_picks / sign_undrafted   rookie deals after the draft
#   cut_down(league)            cut to 53 (like offseason.cut_to_53, but money-aware)
#   sync(league)                safety net: anyone on a team without a contract gets the
#                               right one, anyone gone from a team has his cut charged
#
# Design (docs/free-agency-design.md): prices come from the real pay ladders
# (cap_market.py), so a good player never comes cheap; each team bids what the
# role he'd fill is worth to it; players pick by money first, then winning,
# loyalty and playing time. Every AI move checks the cap first, so AI teams
# never go over it. Your team's decisions are yours: nothing here moves your
# players except the staff's routine (reserve/future deals); anything bigger
# goes to you as a staff request.
#
# Real NFL targets this is tuned to (docs/research/): 66% of players stay with
# their team from one season to the next, 24% move, 10% leave the league (by
# experience: 0-2 seasons 81/14/5, 3-4 54/37/9, 5-7 54/32/14, 8+ 47/25/28);
# 76-87% of veteran deals at about the minimum, 75-80% for one year; ~355
# market deals (1%+ of the cap) a season; the pay ladder by position.

import math
import random
from collections import defaultdict
from datetime import date
from functools import lru_cache

from . import cap_market as M
from . import contracts as C
from . import evaluation as E   # (imported once here, not in the busy functions: Oct 25, for speed)
from . import gm as G
from .teams import ROSTER_TEMPLATE, ROSTER_SIZE
from .transactions import STARTER_COUNT

# ---- Knobs: AI teams ------------------------------------------------------------------
OFFSEASON_ROSTER_MAX = 90       # real offseason roster limit
CAMP_EXTRA_SHARE = 0.5          # bodies a team takes to camp beyond its roster count, per position (x count, at least 1)
IN_SEASON_BUFFER = 0.025        # cap room AI teams keep for in-season moves (share of the cap; about $7.5M at the
                                # 2026 cap: injured reserve players keep counting while their replacements are
                                # paid; 1.5% put teams over by week 1. Oct 22: 0.035 -> 0.025 with the spending
                                # changes below, cap room at free agency's opening toward real; legality 0)
WEEK1_EXTRA = 0.025             # ...plus, in the offseason, room for what starts counting at week 1 (all 53
                                # instead of the top 51, the practice squad's pay: about 2% of the cap)
ROOKIE_RESERVE = 0.035          # cap room kept for the draft class before the draft (if the picks aren't known)
KEEP_RESERVE_SHARE = 0.5        # after signing a free agent a team keeps this share of that reserve (and its owner's savings)
STYLE_SD = 0.04                 # front offices differ in how freely they spend (hidden, fixed per team)
EVAL_SD = 0.05                  # and in how they judge a given player (scouting misjudgment)
RESIGN_SLACK = 0.10             # re-signing: a deal happens if the team's top figure is within this share of his ask
                                # (they meet in between); otherwise he goes to the market
UPGRADE_K = 0.10               # a team pays up to this much over his price for a big upgrade at a starting job
                                # (Oct 22: 0.06 -> 0.10; real teams with room pay up, see OFFERS_PER_WAVE)
UPGRADE_FULL = 10.0             # ...reached at this many rating points over the starter he'd replace
MIN_UPGRADE = 1.5               # less of an upgrade than this: he's priced as a backup there
DEPTH_KEEP = 0.55               # chance a team keeps a cheap depth player it could keep (teams churn depth)
# ---- Knobs: each AI team's approach to the league year (Blake, Oct 24: "match the real NFL":
# contenders go all in, rebuilders sit on room). Real cap room when free agency opens
# (2024-25): median ~14% of the cap, 7-8 teams with almost none, the most 40-45%; before
# this every AI team spent the same way and none ran short (lowest tenth ~9%).
APPROACH_COUNTS = (10, 7)       # AI teams going all in / rebuilding each league year (the rest: normal)
APPROACH_NOISE = 0.6            # front offices read their window differently (spread, in team-strength units)
ALLIN_RESTRUCTURE = 0.12        # all in: turn up to this share of the cap in salary into bonus (pushing money
                                # into later years) when it needs room to sign or keep a player it wants
ALLIN_RESERVE = 0.5             # ...keep only this share of the usual room for in-season moves
ALLIN_PAY = 1.05                # ...and pay a little more for starters
ALLIN_EXTEND = 0.65             # ...and extend core players more often (EXTEND_CHANCE otherwise)
ALLIN_RISE = 0.15               # ...back-load new deals (base salary climbs this much a year, 6% otherwise:
                                # a small cap hit now, bigger ones later)
ALLIN_NEXT_MAX = 1.15           # ...and let next season's commitments run past next season's cap (it'll
                                # restructure or cut in March, as real contenders do; EXTEND_NEXT_MAX otherwise)
REBUILD_KEEP = 0.0              # rebuilding: keep this share of the cap unspent in the offseason (it carries over;
                                # Oct 22: 0.02 -> 0 with the real opening-day data, rebuilders sat on too much)
REBUILD_AGE = 29                # ...pay players this old or older less
REBUILD_OLD_PAY = 0.9           # (Oct 22: 0.8 -> 0.9)
REBUILD_CUT_CHANCE = 0.85       # ...and cut overpaid veterans more readily (CUT_CHANCE otherwise)
# ---- Knobs: each AI team's general manager (gm.py, Oct 22; Blake chose free agency /
# re-signing style and cap style as the GM's). Styles are spreads (about -2..+2, mostly the
# GM's, partly the organization's); sized so teams' habits last like real ones
# (tools/gm_check.py vs docs/research/real_gm.json). PROVISIONAL sizes.
GM_FA_PAY_K = 0.18              # a big spender's bids for other teams' players x e^(k x free-agency style)...
GM_FA_OFFERS_K = 0.8            # ...and his offers a wave x e^(k x style) (he chases more players); a GM who
                                # builds through the draft bids like anyone, up to his ceiling below...
GM_FA_HOLD = 0.0                # ...a GM who builds through the draft could keep this share of the cap per point
                                # out of the bidding (0: at 0.015-0.03 the roomiest teams sat on far more than real)...
GM_FA_BUDGET = (0.10, 0.90)     # ...and spends at most (this share of the cap + GM_FA_BUDGET_ROOM x the room it had
GM_FA_BUDGET_ROOM = 0.5         # when free agency opened) x e^(k x style) a league year on other teams' players in
                                # market deals (real: 12.3% of the cap a team a year, teams' own levels spread ~2.8%;
                                # a ceiling that mostly binds the draft builders; a flat ceiling left draft builders
                                # with lots of room spending nothing, and the roomiest teams far roomier than real;
                                # k 0.45 -> 0.9 with the cap plan below: outside money's habit 0.20 -> ~0.4-0.45, real 0.53)
GM_RESIGN_EXT_K = 1.0           # extending a core starter early: odds x e^(k x own-players style)
GM_RESIGN_PAY_K = 0.06          # his top figure for his own players x e^(k x style)
GM_CAP_RISE_K = 0.06            # cap style: base salaries climb this much more a year per point (back-loading)...
GM_CAP_BONUS_K = 0.50           # ...the signing bonus (spread over the years) x e^(k x style)...
GM_CAP_RESTRUCTURE = 0.08       # ...a team that isn't all in restructures up to this share of the cap per point
                                # (all in: ALLIN_RESTRUCTURE x e^(GM_CAP_ALLIN_K x style))...
GM_CAP_ALLIN_K = 0.3
GM_CAP_RESTRUCTURE_MAX = 0.15    # ...never more than this share of the cap a league year
GM_CAP_NEXT_K = 0.06            # ...next season's commitments may run this much further past the cap per point...
GM_CAP_HELL = 0.28              # ...until the bill comes due: once bonus money already owed next season passes this
                                # share of the cap, a pushing GM stops pushing (without it the most extreme ones
                                # restructured year after year until no move could get them under the cap)
GM_CAP_HELL_NOW = 0.30          # (or this season's bonus money and dead money pass this share)
GM_CAP_PUSH_MAX = 1.5           # (and pushes no harder than a GM 1.5 spreads out)
GM_CAP_CUT_K = 0.3              # ...and a cap cut may leave dead money up to CUT_DEAD_MAX x e^(k x style) of his hit
# ---- Knobs: each AI team's multi-year cap plan (Blake, Oct 22: "build multi year cap planning to
# close the money gap"; on holding room: "chris ballard used to get roasted for holding too much
# cap money and not spending"). A team's spending level (spend_level: about -2..+2) is mostly its
# owner's (real: cap room left at the season's end is the most lasting team habit, 0.88 odd vs even
# years, and it outlasts GM changes, 0.57 vs 0.62) and partly its GM's (free agency and cap
# styles). It sets how full the team runs its cap every year and how much of next season's cap it
# will commit now. PROVISIONAL sizes, tuned with tools/gm_check.py and free_agency_check.py.
PLAN_OWNER_SHARE = 0.7          # share of the spending level that is the owner's
PLAN_KEEP = 0.03                # a frugal team leaves this share of the cap unspent per spread below 0...
PLAN_KEEP_MAX = 0.08            # ...at most this much
PLAN_SPEND_K = 1.0              # a free-spending team keeps less for in-season moves: x e^(-k x level), never
                                # less than an all-in team does (ALLIN_RESERVE)
PLAN_ROOM_MAX = 0.25            # but every plan spends down to this much room (the real league's spending floor: teams
                                # must pay out about 89% of the cap in cash over four years; without it a frugal draft
                                # builder in a startup-draft league sat on 70-90% of its cap)
PLAN_NEXT = 0.85                # a multi-year deal for another team's player must leave next season's commitments
PLAN_NEXT_K = 0.10              # under (this + this x level) of next season's cap, within PLAN_NEXT_RANGE; past it
PLAN_NEXT_RANGE = (0.70, 1.05)  # the team offers him one year instead (real teams that hold room sign 1-year deals)
# ---- Knobs: the market ---------------------------------------------------------------
# A free agent's ask, as a share of his price, by wave: high early (the first days,
# when the best players sign), falling as the market cools; market-level players
# don't go below ASK_FLOOR in the offseason (they'd rather wait for injuries).
WAVES = {1: "Free agency opens", 2: "First week", 3: "Second week", 4: "Before the draft",
         5: "After the draft", 6: "Summer", 7: "Training camp"}
PRE_DRAFT_WAVES = (1, 2, 3, 4)
POST_DRAFT_WAVES = (5, 6, 7)
ASK_BY_WAVE = {1: 1.08, 2: 1.0, 3: 0.93, 4: 0.86, 5: 0.74, 6: 0.5, 7: 0.3}
ASK_FLOOR = 0.5                 # starter-caliber players, until camp...
ASK_FLOOR_CAMP = 0.4            # ...and once camp opens (wave 7)
IN_SEASON_ASK = 0.5             # in-season, a market-level free agent still wants this share of his price
OFFERS_PER_WAVE = {1: 5, 2: 4, 3: 4, 4: 5, 5: 6, 6: 8, 7: 10}   # Oct 22: waves 1-2 were 3 / 3. Real teams with
# room spend most of it in the first days (OverTheCap the day after each league year opened, 2022-25):
# with these and the knobs marked Oct 22, room after the first wave (3 leagues x 4 offseasons, two league
# sets) went most 37.7-38.3 -> 29.4-30.6% [real 4-yr average 26.4], 5th 22.4-23.4 -> 19.2-19.3 [16.3],
# median 10.4-11.4 -> 9.5-10.0 [8.0], 24th 5.6-6.5 -> 5.9-6.2 [3.7], teams under 2% 2.2-3.3 -> 2.0-2.5 [5.8].
# The low end needs teams that truly spend themselves into a corner (see the build log).
WAVE_ROUNDS = 3                 # Oct 23: bidding rounds in a wave. When a team's target signs elsewhere it moves
# on to its next one in the same wave, as real teams do within hours (before, it sat out until the next wave:
# 244 market-level free agents a year were on the market when it opened, 204 of them starter-level, but only
# ~37 signed in the first wave and 120 were still unsigned at camp; real teams sign 148 market-level players
# from other teams a year (OverTheCap 2016-21, docs/research/deal_kinds.py), the game 85).
MAKE_ROOM_GAIN = 5.0            # Oct 23 (Blake: "teams make room"): a team that can't afford a free agent who'd
# start for it releases a veteran at his position he's clearly better than (by this many rating points, as its
# staff sees them) when that saves money this season within the cap-cut rule (CUT_DEAD_MAX). Before, about 9
# free agents priced as stars were still unsigned at camp each year, wanted by teams with no room left, and any
# of them would sign with you for 40% of his price (FOF8's cheap-star exploit).
SUMMER_WAVES = (6, 7)           # ...and in these waves an unsigned starter-caliber player's ask drops to the best
# offer a team that would start him can actually fit (summer_asks; Blake chose both, Oct 23)
# ---- Knobs: players --------------------------------------------------------------------
WINNER_K = 0.30                 # how much a winning team counts, for a player who most wants to win
LOYALTY_K = 0.10                # how much a loyal player leans toward his old team (disloyal ones lean away)
FAMILIAR = 0.03                 # everyone likes the known a little
ROLE_K = 0.04                   # players like to start
CHOICE_SD = 0.04                # and some of it is just a feeling
RESIGN_PREMIUM = 0.05           # before the market, he asks this much over his price (less if loyal)
TEST_MARKET = 0.55              # chance a player worth 1%+ of the cap wants to test free agency (loyalty 50)
TEST_MARKET_DEPTH = 0.30        # the same for an unrestricted veteran worth less (he looks for a bigger role)
# ---- Knobs: the start of the league year ---------------------------------------------
EXTEND_CHANCE = 0.45            # a core starter entering his last year gets extended
EXTEND_MIN_PRICE = 0.02         # ...if he's worth at least this share of the cap
EXTEND_MAX_AGE = {"QB": 33, "K": 34, "P": 35, "LS": 35}   # and no older than this (others 29)
EXTEND_NEXT_MAX = 1.0           # ...and only if next season's commitments stay within next season's cap
# Retiring while under contract (retirement_contract_factor; fitted to the real reserve/retired list 2021-22):
RETIRE_UC_SCALE = 0.5           # his plain odds times this at his position's usual retiring age...
RETIRE_UC_AGE = 0.175           # ...times e^(this x years past that age), from 8 years before to 4 after
RETIRE_MONEY_K = 0.01           # ...and shrinking by e per 1% of the cap he'd give up (full weight when young)
TAG_MIN_VALUE = 0.95            # tag a player only if he's worth at least this share of the tag
RFA_TENDER_MIN_VALUE = 1.0      # tender a restricted free agent only if he's worth this share of the lowest tender
                                # (Oct 25: 0.75 -> 1.0. At 0.75 teams paid 1-year tenders a third above a player's
                                # worth: 39 tenders a year at 1%+ of the cap vs real ~19, OverTheCap 2016-21 1-year
                                # re-signings at the tender amounts; now ~27, the rest re-sign or test the market)
LONG_TERM_AFTER_TAG = 0.45      # a tagged player signs a long-term deal before the season
OPTION_MIN_VALUE = 0.8          # exercise a fifth-year option if he's worth this share of it
FUTURES_KEEP = 0.85             # practice squad players re-signed on reserve/future deals
# Cuts, tuned to real dead money (Oct 24; Blake: real numbers, not judgment). Real: OverTheCap team
# pages (Internet Archive copies, end of each season, 26-31 teams a season) with trades taken out
# (nflverse trades): 2016-20 7.5-8.4% of the cap a team, about 2.4 players worth 1%+ of the cap and
# 0.45 worth 3%+, the biggest ~2.8%; 2021-25 10.5-15% (void years, which this game doesn't have,
# drive much of the rise). Before this tuning teams cut almost no one with real money left (about 1
# player worth 1%+ a season, the biggest ~2.4%): spring cuts needed him 30% overpaid with dead money
# under 60% of his cap hit, and the cut-down protected guaranteed players at 2 points per 1% of cap.
CUT_OVERPAY_SHARE = 0.15        # cap cut: paid this share more than he's worth...
CUT_OVERPAY_MIN = 0.01          # ...and at least this share of the cap more...
CUT_SAVINGS_MIN = 0.0075        # ...and cutting him saves at least this much this season...
CUT_DEAD_MAX = 1.5              # ...and leaves no more dead money (all years) than this share of his cap hit...
CUT_CHANCE = 0.8                # ...then he's cut this often
DEAD_KEEP_PER_PCT = 0.5         # cut-down: keep value points per 1% of the cap in dead money a cut would leave...
CUT_SAVE_PER_PCT = 1.0          # ...and less keep value per 1% of the cap a cut would save (over a minimum player)
# ---- Knobs: your extensions (Oct 23; PROVISIONAL for Blake) ----------------------------
EXTEND_YEARS_LEFT = 2           # you can extend a player with this many contract seasons left (this one included)
ROOKIE_EXTEND_AFTER = 3         # real rule: a drafted rookie's deal can't be redone until after his 3rd season
UDFA_EXTEND_AFTER = 2           # undrafted rookies: after his 2nd (judgment: their 3-year deals end a year sooner)
EXT_REFUSE_K = 0.5              # a market-level player in his last year who'd test free agency refuses to talk
                                # about an extension this share as often as he tests the market at the end of
                                # his deal (about 27% at average loyalty; decided once a season)
EXT_PATIENCE = 3                # lowball extension offers before he stops talking until next league year
OFFER_ROUNDING = 12             # $K of slack when your offer is weighed against his ask: the screens show money
                                # in $10K steps, so an offer typed in at the ask shown can be a few $K under it
# ----------------------------------------------------------------------------------------


def ensure(league):
    C.ensure(league)
    if getattr(league, "fa", None) is None:
        league.fa = {}
    return league


def _salt(league):
    return league.settings.get("salt", "")


@lru_cache(maxsize=None)
def _style(salt, tid):
    r = random.Random(f"fa-style-{salt}-{tid}")
    return max(0.9, min(1.1, r.gauss(1.0, STYLE_SD)))


@lru_cache(maxsize=300000)
def _eval_draw(salt, season, tid, pid):
    r = random.Random(f"fa-eval-{salt}-{season}-{tid}-{pid}")
    return max(0.88, min(1.12, r.gauss(1.0, EVAL_SD)))


def team_style(league, tid):
    """A front office's spending style (hidden, the same every year)."""
    return _style(_salt(league), tid)


def gm_style(league, tid, key):
    """The team's general manager's habit (gm.style; 0 for your team)."""
    if tid is None or tid == league.user_team_id or not getattr(league, "staff", None):
        return 0.0
    return G.style(league, tid, key)


def cap_push(league, tid):
    """The GM's cap style as it acts this league year: a GM who pushes money into later
    years stops once next season's bonus money passes GM_CAP_HELL of the cap (the bill
    has come due; gm.py, Oct 22). Clean-books GMs are always themselves."""
    z = gm_style(league, tid, "cap")
    if z <= 0:
        return z
    z = min(z, GM_CAP_PUSH_MAX)
    S = league.season
    key = (S, len(league.contract_log))        # (worked out again after each signing)
    memo = league.__dict__.setdefault("_cap_push", {})
    if memo.get(tid, (None,))[0] == key:
        return memo[tid][1]
    owed = 0
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        y = C._year(c, S + 1) if c else None
        if y:
            owed += y["bonus"]
    owed += C.charges(league, tid, S + 1)
    now = C.charges(league, tid, S)
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        y = C._year(c, S) if c else None
        if y:
            now += y["bonus"]
    cap = C.cap_for(league, S)
    v = 0.0 if owed > GM_CAP_HELL * cap or now > GM_CAP_HELL_NOW * cap else z
    memo[tid] = (key, v)
    return v


def spend_level(league, tid):
    """A team's spending level (about -2..+2, average 0; below 0 frugal, above 0 free
    spending): mostly the owner's (staff.py's budget factor), partly its GM's free
    agency and cap styles. 0 for your team and for a league without staffs."""
    if tid is None or tid == league.user_team_id or not getattr(league, "staff", None):
        return 0.0
    from . import staff as SF
    owner = (league.staff.get("owner", {}).get(str(tid), 1.0) - 1.0) / SF.BUDGET_SD
    gm = (gm_style(league, tid, "fa") + gm_style(league, tid, "cap")) / math.sqrt(2)
    v = math.sqrt(PLAN_OWNER_SHARE) * owner + math.sqrt(1 - PLAN_OWNER_SHARE) * gm
    return max(-2.5, min(2.5, v))


def plan_keep(league, tid):
    """Extra cap room (share of the cap) a frugal team plans to leave unspent all year."""
    return min(PLAN_KEEP_MAX, PLAN_KEEP * max(0.0, -spend_level(league, tid)))


def plan_next(league, tid):
    """The most of next season's cap a team will commit now to another team's player."""
    v = PLAN_NEXT + PLAN_NEXT_K * spend_level(league, tid)
    return max(PLAN_NEXT_RANGE[0], min(PLAN_NEXT_RANGE[1], v))


def _odds_shift(p, k):
    """A chance with its odds multiplied by e^k."""
    if p <= 0 or p >= 1:
        return p
    o = p / (1 - p) * math.exp(k)
    return o / (1 + o)


# Since Oct 24 (Blake: AI teams judge players through their own staff's eyes) a team's
# judgment comes from its staff (evaluation.py): how far its staff misjudges him
# (evaluation.misjudgment: its luck, without the pull toward average every unsure estimate
# has; comparing its view with the league's directly made teams overpay their own stars
# and end up over the cap at week 1), turned into money. A one-point misjudgment in overall
# is worth about STAFF_EVAL_K of his price (PROVISIONAL: a market rank ladder is steep near
# the top), limited like the old draw.
STAFF_EVAL_K = 0.04
STAFF_EVAL_RANGE = (0.80, 1.25)


def _eval(league, tid, pid):
    """How this team's staff judges this player (fixed until its view changes)."""
    if getattr(league, "staff", None):
        diff = E.misjudgment(league, tid, league.player(pid))
        return max(STAFF_EVAL_RANGE[0], min(STAFF_EVAL_RANGE[1], math.exp(STAFF_EVAL_K * diff)))
    return _eval_draw(_salt(league), league.season, tid, pid)


def team_score(league, tid, p, info, memo=None):
    """His market score as this team's staff sees him, for its role decisions
    (is he better than our starter, by how much; Oct 24: AI teams judge players
    through their own staff's eyes): the league's score moved by the staff's
    misjudgment of him, now and ceiling (evaluation.misjudgment). Not its view
    as such: its own players, seen surely, would barely be pulled toward
    average while other teams' players would be pulled more, and a role
    decision compares the two (the same reason bids use the misjudgment).
    memo: a dict to remember answers in (a free agency wave asks the same
    questions round after round): a staff's view holds through the wave, even
    of a player it signs during it (it has known him for minutes)."""
    if memo is not None:
        key = (tid, p.id)
        if key not in memo:
            memo[key] = team_score(league, tid, p, info)
        return memo[key]
    if tid is None or not getattr(league, "staff", None):
        return info["score"]
    d_now = E.misjudgment(league, tid, p)
    d_pot = E.misjudgment(league, tid, p, "potential")
    if not d_now and not d_pot:
        return info["score"]
    cur, pot = float(p.overall()), float(p.overall("potential"))
    S = league.season
    # (M.own_score(league, p, S) = M.market_score(p, S, cur, pot), remembered: Oct 25, for speed.)
    return info["score"] + M.market_score(p, S, cur + d_now, pot + d_pot) - M.own_score(league, p, S)


def ai_teams(league):
    return [t.id for t in league.teams if t.id != league.user_team_id]


def approach(league, tid):
    """This AI team's approach this league year: 'all_in', 'rebuild' or 'normal'
    (set_approaches, at the start of the league year)."""
    return league.fa.get("approach", {}).get(tid, "normal")


def set_approaches(league, table):
    """Each AI team reads its window: last season's record and the talent on its
    roster (its best 22 players' market scores, as its staff sees them), plus its
    own judgment. The most promising go all in, the least promising rebuild."""
    quality = team_quality(league)
    strength = {}
    for tid in ai_teams(league):
        scores = sorted((team_score(league, tid, league.player(pid), table[pid])
                         for pid, t in league.rosters.items() if t == tid and pid in table), reverse=True)[:22]
        strength[tid] = sum(scores) / max(1, len(scores))
    if not strength:
        league.fa["approach"] = {}
        return
    mu_s = sum(strength.values()) / len(strength)
    sd_s = (sum((v - mu_s) ** 2 for v in strength.values()) / len(strength)) ** 0.5 or 1.0
    z = {}
    for tid in strength:
        r = random.Random(f"fa-approach-{_salt(league)}-{league.season}-{tid}")
        z[tid] = (0.5 * (quality.get(tid, 0.5) - 0.5) / 0.18 + 0.5 * (strength[tid] - mu_s) / sd_s
                  + r.gauss(0, APPROACH_NOISE))
    order = sorted(z, key=lambda t: -z[t])
    n_in, n_re = APPROACH_COUNTS
    league.fa["approach"] = {tid: ("all_in" if i < n_in else "rebuild" if i >= len(order) - n_re else "normal")
                             for i, tid in enumerate(order)}


def restructure_budget(league, tid):
    """Share of the cap an AI team will restructure this league year to sign or keep
    players it wants: all-in teams, and teams whose GM pushes money into later years
    (gm.py, Oct 22); a clean-books GM restructures less even when all in. (Getting
    under the cap, _comply, restructures whatever the style: every team must.)"""
    if tid == league.user_team_id:
        return 0.0
    z = cap_push(league, tid)
    if approach(league, tid) == "all_in":
        return min(GM_CAP_RESTRUCTURE_MAX, ALLIN_RESTRUCTURE * math.exp(GM_CAP_ALLIN_K * z))
    return min(GM_CAP_RESTRUCTURE_MAX, GM_CAP_RESTRUCTURE * max(0.0, z))


def _make_room(league, tid, need_k, rng):
    """All in (or a GM who pushes money): restructure to open `need_k` more cap room,
    within the league year's restructure_budget. True if the room is there now."""
    cap = C.cap_for(league, league.season)
    if C.cap_room(league, tid) >= need_k:
        return True
    budget = restructure_budget(league, tid)
    if budget <= 0:
        return False
    used = league.fa.setdefault("allin_used", {})
    left = budget * cap - used.get(tid, 0)
    short = need_k - C.cap_room(league, tid)
    if short > left:
        return False
    before = C.cap_room(league, tid)
    _comply(league, tid, rng, target=need_k / cap, allow_cuts=False)
    used[tid] = used.get(tid, 0) + max(0, C.cap_room(league, tid) - before)
    return C.cap_room(league, tid) >= need_k


def _restructure_left(league, tid):
    """Cap room an all-in team (or a money-pushing GM's) could still open by restructuring this league year."""
    budget = restructure_budget(league, tid)
    if budget <= 0:
        return 0
    cap = C.cap_for(league, league.season)
    left = budget * cap - league.fa.get("allin_used", {}).get(tid, 0)
    S = league.season
    possible = 0
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        if c is not None:
            r = C.restructure_room(league, c, S)
            if r > 0:
                possible += r - r // min(C.years_left(c, S), C.MAX_PRORATION_YEARS)
    return max(0, min(left, possible))


def _outside_left(league, tid, cap):
    """$K this team's GM will still spend this league year on other teams'
    market-level players (gm.py, Oct 22: GM_FA_BUDGET)."""
    z_fa = gm_style(league, tid, "fa")
    open_room = league.fa.setdefault("open_room", {}).setdefault(tid, max(0.0, C.cap_room(league, tid) / cap))
    ceiling = max((GM_FA_BUDGET[0] + GM_FA_BUDGET_ROOM * open_room) * math.exp(GM_FA_BUDGET[1] * z_fa),
                  open_room - PLAN_ROOM_MAX)
    return (ceiling - league.fa.get("outside_spent", {}).get(tid, 0.0)) * cap


def _keep_k(league, tid, pre, cap):
    """Cap room ($K) an AI team keeps after signing a free agent: half its usual
    reserve, plus all of its owner's planned savings, and never less than what
    starts counting at week 1 (an all-in team keeps less for in-season moves, and
    could otherwise be over the cap at week 1)."""
    pk = plan_keep(league, tid)
    keep = ((_reserve_share(league, tid, pre) - pk) * KEEP_RESERVE_SHARE + pk) * cap
    if C.top51_in_force(league):
        keep = max(keep, (WEEK1_EXTRA + 0.005 + _open_spots_share(league, tid)) * cap)
    return keep


def _room_cut(league, tid, p, info, table, pids=None, memo=None):
    """(player id, post-June 1?, cap savings $K) for the release that would make
    room for free agent p at this AI team: a veteran on its 53 at his position
    he's clearly better than (MAKE_ROOM_GAIN, as its staff sees them), whose
    release saves the most this season within the cap-cut rule; or None.
    pids: the team's player ids at his position, if already gathered; memo: see team_score."""
    if pids is None:
        pids = [pid for pid, t in league.rosters.items() if t == tid and league.player(pid).position == p.position]
    s = team_score(league, tid, p, info, memo)
    best = None
    for pid in pids:
        c = league.contracts.get(pid)
        if c is None or c["kind"] not in ("veteran", "extension", "minimum") or pid not in table:
            continue
        if s - team_score(league, tid, league.player(pid), table[pid], memo) < MAKE_ROOM_GAIN:
            continue
        june1, prev = C.best_release(league, pid)
        if prev["savings"] <= 0 or sum(prev["dead"].values()) > CUT_DEAD_MAX * max(1, prev["hit"]):
            continue
        if best is None or prev["savings"] > best[2]:
            best = (pid, june1, prev["savings"])
    return best


def _cut_to_fit(league, tid, p, info, table, need_k):
    """Release the player _room_cut picks if that gives this team need_k of cap
    room. True if the room is there now."""
    cut = _room_cut(league, tid, p, info, table)
    if cut is None or C.cap_room(league, tid) + cut[2] < need_k:
        return False
    pid, june1, _savings = cut
    C.release(league, pid, june1=june1)
    q = league.player(pid)
    _let_go(league, pid, tid, "UFA" if q.experience >= C.RFA + 1 else _status(q), "released (to make room)")
    from .transactions import log
    log(league, WAVES.get(league.fa.get("wave"), "Free agency"), tid, pid, "Released",
        f"to make room for {p.first_name} {p.last_name}")
    return True


def team_quality(league):
    """{team id: last season's winning share} (0.5 when there's no last season)."""
    last = {r["team"]: r for r in league.team_history if r.get("season") == league.season - 1}
    out = {}
    for t in league.teams:
        r = last.get(t.id)
        g = (r["w"] + r["l"] + r["t"]) if r else 0
        out[t.id] = (r["w"] + 0.5 * r["t"]) / g if g else 0.5
    return out


def camp_max(position):
    n = ROSTER_TEMPLATE[position]
    return n + max(1, round(CAMP_EXTRA_SHARE * n))


def on_team(league, pid):
    """Team id if he's on a 53, a reserve list or a practice squad."""
    if pid in league.rosters:
        return league.rosters[pid]
    if pid in getattr(league, "practice", {}):
        return league.practice[pid]
    r = getattr(league, "reserve", {}).get(pid)
    return r["team"] if r else None


def roster_count(league, tid):
    return sum(1 for t in league.rosters.values() if t == tid) + sum(
        1 for r in getattr(league, "reserve", {}).values() if r["team"] == tid)


def depth_lists(league, table, exclude=(), memo=None):
    """{team: {position: [market scores as its staff sees them (team_score), best
    first]}} for players on the 53 or reserve lists. memo: see team_score."""
    d = defaultdict(lambda: defaultdict(list))
    for pid, tid in league.rosters.items():
        if pid not in exclude:
            p = league.player(pid)
            d[tid][p.position].append(team_score(league, tid, p, table[pid], memo))
    for pid, r in getattr(league, "reserve", {}).items():
        if pid not in exclude:
            p = league.player(pid)
            d[r["team"]][p.position].append(team_score(league, r["team"], p, table[pid], memo))
    for tid in d:
        for lst in d[tid].values():
            lst.sort(reverse=True)
    return d


def role_price(position, slot):
    """The most the league pays a player in this role (0 = best starter at a
    position, then backups): what the best of the league's players in that
    role earns, as a share of the cap. A team won't pay a starter's salary to
    a backup, but pays a good backup like one."""
    ladder, mult = M.LADDER_OF[position]
    return M.ladder_price(ladder, (32 * slot + 1) * mult)


def starter_level(info):
    """Is he good enough to start for a typical team (his rank at his position)?"""
    ladder, mult = M.LADDER_OF[info["position"]]
    return info["rank"] <= 32 * STARTER_COUNT.get(info["position"], 1) * mult


def willingness(league, tid, p, info, depth, quality=None, score=None):
    """(most this team would pay him, as a share of the cap; his role there:
    'starter' / 'backup' / 'depth'), or (0, None). A team pays a starter about
    his price (a bit more for a big upgrade); for a backup or depth job, no
    more than that role is worth league-wide. Role and upgrade are judged by
    its staff (team_score; score: already worked out)."""
    pos = p.position
    lst = depth[tid][pos]
    count = len(lst)
    if count >= camp_max(pos):
        return 0.0, None
    s = team_score(league, tid, p, info) if score is None else score
    price = info["price"]
    starters = STARTER_COUNT.get(pos, 1)
    slot = sum(1 for x in lst if x > s)
    role = None
    w = 0.0
    if slot < starters:
        gain = UPGRADE_FULL if count < starters else s - lst[starters - 1]
        if gain >= MIN_UPGRADE:
            role = "starter"
            w = price * (1 + UPGRADE_K * max(0.0, min(1.0, gain / UPGRADE_FULL)))
        else:
            slot = starters
    if role is None:
        # Backups, and bodies for camp (offseason rosters run to 90; the cut to 53 sorts them out).
        role = "backup" if slot <= starters else "depth"
        w = min(price, role_price(pos, slot))
    way = approach(league, tid)
    if way == "all_in" and role == "starter":
        w *= ALLIN_PAY
    elif way == "rebuild" and _age(league, p) >= REBUILD_AGE:
        w *= REBUILD_OLD_PAY
    # The GM: how freely he pays other teams' players, and his own (gm.py, Oct 22).
    if tid != league.user_team_id:
        own = league.rosters.get(p.id) == tid or league.fa.get("former", {}).get(p.id) == tid
        w *= math.exp((GM_RESIGN_PAY_K * gm_style(league, tid, "resign")) if own
                      else (GM_FA_PAY_K * max(0.0, gm_style(league, tid, "fa"))))
    return max(info["minimum"], w * team_style(league, tid) * _eval(league, tid, p.id)), role


def ask_share(info, wave):
    """What he asks this wave, as a share of the cap."""
    f = ASK_BY_WAVE.get(wave, ASK_FLOOR)
    if info["price"] >= M.MARKET_LINE and starter_level(info):
        # a starter-caliber player would rather wait for the season's injuries
        f = max(f, ASK_FLOOR if wave < 7 else ASK_FLOOR_CAMP)
    ask = max(info["minimum"], info["price"] * f)
    if wave in SUMMER_WAVES and info.get("summer_ask") is not None:
        # ...unless the summer shows him what's really out there (summer_asks)
        ask = max(info["minimum"], min(ask, info["summer_ask"]))
    return ask


def summer_asks(league):
    """Oct 23 (Blake: leftover players' prices drop to fit): as the summer's waves
    open, each unsigned starter-caliber free agent lowers his ask to the best offer
    a team that would start him could actually make: what it can fit under its cap
    (after its reserve, restructures, and releasing a worse veteran at his position:
    _room_cut), within its GM's budget for other teams' players. If no team could
    fit him at all he waits. Saved in league.fa['summer_ask'] {pid: share}; the
    market table carries it (yours too: you see the same ask)."""
    league.fa["summer_ask"] = {}
    table = M.market_table(league)
    memo = {}
    depth = depth_lists(league, table, memo=memo)
    cap = C.cap_for(league, league.season)
    teams = [t for t in ai_teams(league) if roster_count(league, t) < OFFSEASON_ROSTER_MAX]
    fits = {t: C.cap_room(league, t) - _keep_k(league, t, False, cap) + _restructure_left(league, t) for t in teams}
    out = {}
    for p in free_agent_list(league):
        info = table[p.id]
        if info["price"] < M.MARKET_LINE or not starter_level(info):
            continue
        best = 0.0
        for t in teams:
            w, role = willingness(league, t, p, info, depth, score=team_score(league, t, p, info, memo))
            if role != "starter":
                continue
            room_k = fits[t]
            if room_k < w * cap:
                cut = _room_cut(league, t, p, info, table, memo=memo)
                room_k += cut[2] if cut else 0
            if league.fa.get("former", {}).get(p.id) != t:
                room_k = min(room_k, _outside_left(league, t, cap))
            best = max(best, min(w, room_k / cap))
        if best >= info["minimum"]:
            out[p.id] = best
    league.fa["summer_ask"] = out
    return out


def _age(league, p):
    return p.age(date(league.season, 9, 1))


def _kind_for(share):
    return "veteran" if share > M.MINIMUM_LINE else "minimum"


def make_deal(league, p, tid, apy_share, rng, kind=None, years=None, gtd_share=None, week=0):
    """A veteran contract at this average per year (share of the cap)."""
    cap = C.cap_for(league, league.season)
    apy_k = max(C.min_salary(league, p.experience), int(round(apy_share * cap)))
    share = apy_k / cap
    years = years or M.deal_years(share, _age(league, p), p.position, rng)
    if share <= M.MINIMUM_LINE and apy_k <= C.min_salary(league, p.experience) * 1.02:
        c = C.minimum_contract(league, p.id, tid, years=years, week=week, kind=kind or "minimum")
        return c
    gtd = (gtd_share if gtd_share is not None else M.guarantee_share(share, years, p.position, rng)) * apy_k * years
    rise = ALLIN_RISE if tid != league.user_team_id and approach(league, tid) == "all_in" else 0.06
    bonus = None
    if tid != league.user_team_id and years > 1:
        # The GM's cap style (gm.py, Oct 22): back-loaded deals with more bonus spread into
        # later years, or flatter ones with less.
        z = cap_push(league, tid)
        rise = max(0.0, min(0.25, rise + GM_CAP_RISE_K * z))
        bonus = int(round(min(gtd, gtd * 0.55 * math.exp(GM_CAP_BONUS_K * z))))
    c = C.build(league, p.id, tid, kind or _kind_for(share), league.season, years, apy_k, guaranteed=gtd, rise=rise,
                signing_bonus=bonus)
    c["week"] = week
    return c


def _sign(league, p, c, label, note, phase, new_team=None):
    from .transactions import log
    C.sign(league, c, phase=phase, new_team=new_team)
    league.rosters[p.id] = c["team"]
    log(league, label, c["team"], p.id, "Signed", note)


def _open_spots_share(league, tid):
    """Room (share of the cap) to fill out the roster at the minimum: a team
    can't spend it all on a few stars."""
    signed = sum(1 for c in league.contracts.values() if c["team"] == tid and c["kind"] != "practice")
    open_spots = max(0, (C.TOP_51 if C.top51_in_force(league) else ROSTER_SIZE) - signed)
    return open_spots * C.min_salary(league, 1) / C.cap_for(league, league.season)


def _reserve_share(league, tid, before_draft):
    """Cap room (share of the cap) an AI team keeps free: for in-season moves,
    in the offseason also for week 1's extra costs, and before the draft for
    its picks. All-in teams keep less for in-season moves; rebuilding teams keep
    extra room through the offseason."""
    way = approach(league, tid)
    f = ALLIN_RESERVE if way == "all_in" else 1.0
    if tid != league.user_team_id:
        # The team's cap plan (Oct 22): free spenders keep less for in-season moves (never less
        # than an all-in team), frugal teams leave room unspent all year.
        level = spend_level(league, tid)
        if level > 0:
            f = max(ALLIN_RESERVE, f * math.exp(-PLAN_SPEND_K * level))
    r = IN_SEASON_BUFFER * f + plan_keep(league, tid)
    top51 = C.top51_in_force(league)
    if top51:
        r += WEEK1_EXTRA
        if way == "rebuild":
            r += REBUILD_KEEP
    r += _open_spots_share(league, tid)
    if before_draft:
        picks = league.fa.get("pick_reserve", {}).get(tid)
        r += picks if picks is not None else ROOKIE_RESERVE
    return r


def _room_share(league, tid, before_draft=False):
    cap = C.cap_for(league, league.season)
    return C.cap_room(league, tid) / cap - _reserve_share(league, tid, before_draft)


def _first_hit(league, c):
    return C.cap_hit(league, c, league.season)


# ---------------------------------------------------------------------------
# A new league's contracts
# ---------------------------------------------------------------------------

def initial_contracts(league, rng=None):
    """Every player on a team gets a contract that looks like a real league's:
    rookie-scale deals for players in their first seasons, veteran deals
    signed in past seasons (some running a few more years, signed when the cap
    was smaller), minimum deals for depth, practice squad deals; then each
    team is brought under the cap the way real teams do it (restructures),
    with some dead money from past cuts."""
    ensure(league)
    rng = rng or random.Random(f"fa-initial-{_salt(league)}-{league.season}")
    S = league.season
    for s in range(S - 6, S + 1):
        C.set_cap(league, s)
    table = M.market_table(league)
    # Draft slots for players still on rookie deals: rank each draft class's round by talent.
    by_class = defaultdict(list)
    for p in league.players:
        if p.retired is None and p.draft_round > 0 and on_team(league, p.id) is not None:
            by_class[(p.draft_year, p.draft_round)].append(p)
    pick_of = {}
    for (year, rnd), group in by_class.items():
        group.sort(key=lambda p: -(0.7 * p.overall("potential") + 0.3 * p.overall() + rng.gauss(0, 6)))
        for i, p in enumerate(group):
            pick_of[p.id] = (rnd - 1) * 32 + 1 + min(31, int(i * 32 / max(1, len(group))))
    for p in league.players:
        tid = on_team(league, p.id)
        if tid is None or p.retired is not None:
            continue
        if p.id in getattr(league, "practice", {}):
            C.sign(league, C.practice_contract(league, p.id, tid), log=False)
            continue
        if M.on_rookie_deal(league, p):
            start = S - p.experience
            if p.draft_round > 0:
                c = C.rookie_contract(league, p.id, tid, pick_of.get(p.id, p.draft_round * 32 - 16),
                                      p.draft_round, start=start)
                if c["option"] and p.experience == C.ROOKIE_YEARS - 1:
                    _decide_option(league, c, table, depth_lists(league, table), rng)
            else:
                c = C.udfa_contract(league, p.id, tid, start=start, rng=rng)
            C.sign(league, c, log=False)
            continue
        info = table[p.id]
        price = info["price"] * math.exp(rng.gauss(0, 0.10))
        age = _age(league, p)
        years = M.deal_years(price, age - 1, p.position, rng)
        k = rng.randrange(years)                        # seasons since he signed
        while k > 0 and p.experience - k < 0:
            k -= 1
        start = S - k
        exp0 = p.experience - k
        cap0 = C.cap_for(league, start)
        apy = int(round(max(price * cap0, C.min_salary(league, exp0, start))))
        if price <= M.MINIMUM_LINE:
            bases = [C.min_salary(league, exp0 + i, start + i) for i in range(years)]
            c = C.build(league, p.id, tid, "minimum", start, years, sum(bases) / years, bases=bases,
                        signing_bonus=0, experience=exp0)
        else:
            gtd = M.guarantee_share(price, years, p.position, rng) * apy * years
            c = C.build(league, p.id, tid, "veteran", start, years, apy, guaranteed=gtd, experience=exp0)
        c["signed"] = start
        C.sign(league, c, log=False)
    # Under the cap, the way real teams get there; then a little dead money from past cuts.
    cap = C.cap_for(league, S)
    for t in league.teams:
        # (a new league is about to play: everyone counts, not just the top 51)
        _comply(league, t.id, rng, target=IN_SEASON_BUFFER, allow_cuts=False, top51=False)
        room = C.cap_room(league, t.id, top51=False)
        if room < IN_SEASON_BUFFER * cap:
            _shrink(league, t.id, IN_SEASON_BUFFER * cap - room + int(0.005 * cap))
        room = C.cap_room(league, t.id, top51=False)
        dead = int(max(0.0, min(room - IN_SEASON_BUFFER * cap, abs(rng.gauss(0.03, 0.02)) * cap)))
        C.add_charge(league, t.id, S, dead)
        C.add_charge(league, t.id, S + 1, int(abs(rng.gauss(0.0, 0.01)) * cap))
    return league


def _shrink(league, tid, amount):
    """New leagues only: trim this team's current-season veteran salaries
    (as if those deals had been signed a little cheaper) by about this much."""
    S = league.season
    cs = [league.contracts[pid] for pid in C.players_with_team(league, tid)
          if pid in league.contracts and league.contracts[pid]["kind"] == "veteran"]
    total = sum(C.cap_hit(league, c, S) for c in cs) or 1
    f = max(0.5, 1 - amount / total)
    for c in cs:
        for y in c["years"]:
            if y["season"] >= S:
                p = league.player(c["pid"])
                y["base"] = max(C.min_salary(league, p.experience, y["season"]), int(y["base"] * f))
                y["bonus"] = int(y["bonus"] * f)
                y["gtd"] = min(y["gtd"], y["base"])


# ---------------------------------------------------------------------------
# The start of the league year
# ---------------------------------------------------------------------------

def _status(p):
    if p.experience <= C.ERFA:
        return "ERFA"
    if p.experience == C.RFA:
        return "RFA"
    return "UFA"


def _let_go(league, pid, tid, status, why=""):
    league.rosters.pop(pid, None)
    league.fa.setdefault("former", {})[pid] = tid
    league.fa.setdefault("status", {})[pid] = status
    league.fa.setdefault("left", []).append({"pid": pid, "team": tid, "status": status, "why": why})


def _option_terms(league, c, table, depth):
    """(regular starter?, option salary $K, what he's worth next season $K) for a
    first-rounder's fifth-year option."""
    p = league.player(c["pid"])
    lst = depth[c["team"]][p.position]
    s = team_score(league, c["team"], p, table[p.id])
    starter = sum(1 for x in lst if x > s) < STARTER_COUNT.get(p.position, 1)
    salary = C.option_salary(league, p.position, starter)
    return starter, salary, table[p.id]["price"] * C.cap_for(league, league.season + 1)


def _decide_option(league, c, table, depth, rng):
    """Fifth-year option for a first-rounder about to play year 4."""
    _starter, salary, worth = _option_terms(league, c, table, depth)
    if worth >= OPTION_MIN_VALUE * salary:
        C.option_contract(league, c, salary)
        return True
    c["option"]["exercised"] = False
    return False


def league_year_start(league, rng=None, draft_order=None):
    """Run the start of the new league year (league.season already advanced,
    retirements done). AI teams decide everything; your team's expiring
    players wait for you in league.fa['pending'] until the market opens.
    draft_order: this year's order (team ids), so teams keep room for their
    picks. Returns a report dict of counts and moves."""
    ensure(league)
    rng = rng or random.Random(f"fa-year-{_salt(league)}-{league.season}")
    S = league.season
    expired = C.start_league_year(league)
    league.fa = {"season": S, "former": {}, "status": {}, "pending": [], "tags": {}, "left": [],
                 "report": defaultdict(int), "pick_reserve": {}}
    if draft_order:
        set_pick_reserve(league, draft_order)
    rep = league.fa["report"]
    user = league.user_team_id
    table = M.market_table(league)
    set_approaches(league, table)
    # 1. Reserve/future deals for last season's practice squad players (now on the offseason roster).
    pending = {}
    for pid, old in expired.items():
        p = league.player(pid)
        tid = league.rosters.get(pid)
        if p.retired is not None or tid is None:
            continue
        if old["kind"] == "practice":
            if tid == user or rng.random() < FUTURES_KEEP:
                c = C.minimum_contract(league, pid, tid, years=1 if rng.random() < 0.7 else 2, kind="futures")
                C.sign(league, c, phase="futures", new_team=False)
                rep["futures"] += 1
            else:
                _let_go(league, pid, tid, _status(p), "not kept from the practice squad")
            continue
        pending[pid] = (tid, old)
    depth = depth_lists(league, table, exclude=pending)
    # 2. Fifth-year options; 3. extensions for core players entering their last year.
    for pid, c in list(league.contracts.items()):
        if c["team"] == user or c["kind"] == "practice":
            continue
        if c.get("option") and c["option"].get("exercised") is None and C.years_left(c, S) == 1:
            rep["options"] += _decide_option(league, c, table, depth, rng)
    for pid, c in list(league.contracts.items()):
        if c["team"] == user or c["kind"] in ("practice", "minimum", "futures", "tag", "tender"):
            continue
        if C.years_left(c, S) != 1:
            continue
        p = league.player(pid)
        info = table[pid]
        age = _age(league, p)
        if info["price"] < EXTEND_MIN_PRICE or age > EXTEND_MAX_AGE.get(p.position, 29):
            continue
        s = team_score(league, c["team"], p, info)
        lst = [x for x in depth[c["team"]][p.position] if x != s]
        if sum(1 for x in lst if x > s) >= STARTER_COUNT.get(p.position, 1):
            continue
        chance = ALLIN_EXTEND if approach(league, c["team"]) == "all_in" else EXTEND_CHANCE
        chance = _odds_shift(chance, GM_RESIGN_EXT_K * gm_style(league, c["team"], "resign"))
        if rng.random() < chance:
            apy = info["price"] * (1 + RESIGN_PREMIUM * (1.5 - p.loyalty / 100)) * team_style(league, c["team"])
            ext, new = _extension_contract(league, p, c, apy, rng)
            if _extension_fits(league, c, ext):
                _sign_extension(league, ext, new)
                rep["extensions"] += 1
    # 4. Expiring contracts: best players first, so a re-signed starter counts for the next decision.
    quality = team_quality(league)
    order = sorted(pending, key=lambda pid: -table[pid]["price"])
    for pid in order:
        tid, old = pending[pid]
        p = league.player(pid)
        status = _status(p)
        if tid == user:
            league.fa["pending"].append(pid)
            league.fa["status"][pid] = status
            league.fa.setdefault("pending_old", {})[str(pid)] = old     # for his tag / tender price
            continue
        info = table[pid]
        w, role = willingness(league, tid, p, info, depth, quality)
        signed = None
        if w > 0 and (role != "depth" or rng.random() < DEPTH_KEEP):
            if status == "ERFA":
                signed = C.minimum_contract(league, pid, tid, years=1, kind="tender")
                rep["erfa"] += 1
            elif (status == "RFA" and role in ("starter", "backup")
                  and info["price"] >= RFA_TENDER_MIN_VALUE * C.RFA_TENDER_SHARE["rofr"]):
                level = ("first" if info["price"] >= C.RFA_TENDER_SHARE["first"] else
                         "second" if info["price"] >= C.RFA_TENDER_SHARE["second"] else "rofr")
                amt = C.rfa_tender(league, level, old["years"][-1]["base"])
                signed = C.build(league, pid, tid, "tender", S, 1, amt, bases=[amt], signing_bonus=0)
                rep["rfa_tenders"] += 1
            else:
                loyal = p.loyalty / 100
                ask = info["price"] * (1 + RESIGN_PREMIUM * (1.5 - loyal))
                bad_team = max(0.0, 0.5 - quality.get(tid, 0.5)) * 2 * max(0.0, (p.wants_winner - 50) / 50)
                chance = TEST_MARKET if info["price"] >= M.MARKET_LINE else TEST_MARKET_DEPTH
                test = status == "UFA" and rng.random() < chance * (1.5 - loyal) * (1 + bad_team)
                if w >= ask * (1 - RESIGN_SLACK) and not test:
                    signed = make_deal(league, p, tid, ask if w >= ask else (w + ask) / 2, rng)
                    rep["resigned"] += 1
                elif (role == "starter" and status == "UFA" and tid not in league.fa["tags"]):
                    amount = C.tag_amount(league, p.position, C.cap_hit(league, old, S - 1, full=True),
                                          old.get("tags", 0) if old["kind"] == "tag" else 0)
                    floor = ((WEEK1_EXTRA + 0.005) if approach(league, tid) != "rebuild"
                             else _reserve_share(league, tid, True))
                    if (info["price"] * C.cap_for(league, S) >= TAG_MIN_VALUE * amount
                            and C.room_after(league, tid, amount) >= floor * C.cap_for(league, S)):
                        signed = C.tag_contract(league, pid, tid, amount,
                                                old.get("tags", 0) if old["kind"] == "tag" else 0)
                        league.fa["tags"][tid] = pid
                        rep["tags"] += 1
        if signed is not None:
            # Within the cap (with room kept for the draft) or he goes to the market. Teams that
            # aren't rebuilding keep their starters and find the rookie and in-season money later
            # (restructures after the draft, at final cuts), as real teams do, keeping only what
            # week 1 adds; an all-in team restructures now if even that isn't there.
            keep = _reserve_share(league, tid, True) * C.cap_for(league, S)
            if approach(league, tid) != "rebuild" and role == "starter":
                keep = (WEEK1_EXTRA + 0.005) * C.cap_for(league, S)
            if C.room_after(league, tid, _first_hit(league, signed)) < keep and signed["kind"] not in ("tender",):
                if not (role == "starter" and _make_room(league, tid, _first_hit(league, signed) + keep, rng)):
                    signed = None
        if signed is not None:
            C.sign(league, signed, phase="re-sign", new_team=False)
            s = team_score(league, tid, p, table[pid])
            depth[tid][p.position].append(s)
            depth[tid][p.position].sort(reverse=True)
        else:
            _let_go(league, pid, tid, status, "not re-signed")
            rep["let_go"] += 1
    # 5. Cap cuts and 6. getting under the cap (AI teams); your staff asks you instead.
    for tid in ai_teams(league):
        rep["cap_cuts"] += _cap_cuts(league, tid, table, depth, rng)
        _comply(league, tid, rng, target=0.0)
    if user is not None and C.cap_room(league, user) < 0:
        request_cap_moves(league, user)
    return rep


def _extension_contract(league, p, c, apy_share, rng, years=None, apy_k=None, gtd=None):
    """The contract an extension makes (not signed): this season's money stays;
    from next season the new deal's years at the new price replace whatever was
    left of the old one (its bonus shares still count in their seasons), with a
    new signing bonus spread from this season on. years: seasons from next
    season on; apy_k / gtd: exact terms ($K) when you set them."""
    S = league.season
    cap = C.cap_for(league, S)
    years = years or max(2, M.deal_years(apy_share, _age(league, p) + 1, p.position, rng))
    apy_k = int(round(apy_share * cap)) if apy_k is None else int(apy_k)
    if gtd is None:
        gtd = M.guarantee_share(apy_share, years, p.position, rng) * apy_k * years
    new = C.build(league, p.id, c["team"], "extension", S + 1, years, apy_k, guaranteed=gtd,
                  experience=p.experience + 1)
    cur = C._year(c, S)
    bonus = new["signing_bonus"]
    # The new bonus is spread over this season and the new years (at most 5).
    n = min(1 + years, C.MAX_PRORATION_YEARS)
    for y in new["years"]:
        y["bonus"] = 0
    share_each = [bonus // n + (1 if i < bonus % n else 0) for i in range(n)]
    years_list = [dict(cur)] + new["years"]
    for i in range(n):
        years_list[i]["bonus"] += share_each[i]
    # Old bonus money already spread into later seasons keeps counting there.
    for y in c["years"]:
        if y["season"] > S and y["bonus"]:
            years_list[min(y["season"] - S, len(years_list) - 1)]["bonus"] += y["bonus"]
    ext = dict(new)
    ext["years"] = years_list
    ext["value"] = sum(y["base"] + y["bonus"] for y in years_list)
    ext["apy"] = int(round(ext["value"] / len(years_list)))
    ext["guaranteed"] = new["guaranteed"] + cur["gtd"]
    ext["signed"] = S
    ext["week"] = c["week"] if c["signed"] == S else 0    # (this season counts from when he joined)
    ext["option"] = None
    ext["new_years"] = years
    ext["new_apy"] = new["apy"]
    return ext, new


def _extension_fits(league, c, ext):
    """AI: can the team afford this extension? The new bonus's share has to fit
    this season with the room it keeps for the draft and in-season moves (as
    re-signings do), and next season's commitments can't go past next season's
    cap. (Before Oct 24 extensions never checked: a startup-draft league had a
    team pay two quarterbacks 38% of its cap, and teams piled up deals they
    then had to cut.)"""
    tid, S = c["team"], league.season
    more = C.cap_hit(league, ext) - C.cap_hit(league, c)
    if more > 0 and C.room_after(league, tid, more) < _reserve_share(league, tid, True) * C.cap_for(league, S):
        return False
    nxt = (C.commitments(league, tid, S + 1) - C.cap_hit(league, c, S + 1, full=True)
           + C.cap_hit(league, ext, S + 1, full=True))
    limit = ALLIN_NEXT_MAX if approach(league, tid) == "all_in" else EXTEND_NEXT_MAX
    limit = max(0.95, limit + GM_CAP_NEXT_K * cap_push(league, tid))
    return nxt <= limit * C.cap_for(league, S + 1)


def _sign_extension(league, ext, new):
    cap = C.cap_for(league, league.season)
    years = ext["new_years"]
    C.sign(league, ext, phase="extension", new_team=False)
    # Logged the way OverTheCap records extensions: the new years and their average.
    league.contract_log[-1].update(years=years, apy=new["apy"], apy_share=round(new["apy"] / cap, 5),
                                   value=new["value"], guaranteed=new["guaranteed"])
    return ext


def _extend(league, p, c, apy_share, rng, years=None, apy_k=None, gtd=None):
    """Extension: sign _extension_contract's deal (logged the way OverTheCap
    records extensions: the new years and their average)."""
    ext, new = _extension_contract(league, p, c, apy_share, rng, years, apy_k, gtd)
    return _sign_extension(league, ext, new)


def _cap_cuts(league, tid, table, depth, rng):
    """AI: release veterans paid well over what they're worth now when it
    saves real money (the spring's "cap casualties")."""
    S = league.season
    cap = C.cap_for(league, S)
    n = 0
    for pid in list(C.players_with_team(league, tid)):
        c = league.contracts.get(pid)
        if c is None or c["kind"] not in ("veteran", "extension"):
            continue
        if c["signed"] >= S - 1:
            continue                  # teams don't cut a deal they signed last year for cap reasons
        hit = C.cap_hit(league, c, S)
        worth = table[pid]["price"] * cap
        use_june, prev = C.best_release(league, pid)
        savings = prev["savings"]
        over = hit - worth
        dead_total = sum(prev["dead"].values())
        dead_max = CUT_DEAD_MAX * math.exp(GM_CAP_CUT_K * cap_push(league, tid))   # the GM (gm.py)
        if (over >= max(CUT_OVERPAY_MIN * cap, CUT_OVERPAY_SHARE * hit) and savings >= CUT_SAVINGS_MIN * cap
                and dead_total <= dead_max * hit):
            if rng.random() < (REBUILD_CUT_CHANCE if approach(league, tid) == "rebuild" else CUT_CHANCE):
                C.release(league, pid, june1=use_june)
                p = league.player(pid)
                _let_go(league, pid, tid, "UFA" if p.experience >= C.RFA + 1 else _status(p), "released (cap)")
                from .transactions import log
                log(league, "Start of league year", tid, pid, "Released", "cap savings")
                n += 1
    return n


def _comply(league, tid, rng, target=0.0, allow_cuts=True, top51=None):
    """AI: get at least `target` (share of the cap) of room: restructure the
    biggest contracts first, then cut the players whose release saves the
    most for the least value lost. Returns the moves made."""
    S = league.season
    cap = C.cap_for(league, S)
    moves = []
    for _ in range(60):
        room = C.cap_room(league, tid, top51=top51)
        if room >= target * cap:
            return moves
        need = target * cap - room
        best = None
        for pid in C.players_with_team(league, tid):
            c = league.contracts.get(pid)
            if c is None:
                continue
            r = C.restructure_room(league, c, S)
            if r > 0:
                n = min(C.years_left(c, S), C.MAX_PRORATION_YEARS)
                gain = r - r // n
                if best is None or gain > best[0]:
                    best = (gain, pid)
        # A restructure worth doing: at least 0.2% of the cap, or all that's needed when the team
        # is only a little over (Oct 23: a team $100K over with no restructure worth 0.2% left
        # stayed over all season; the trades session found AI teams drifting over in-season).
        if best and best[0] > min(0.002 * cap, need):
            C.restructure(league, best[1], min(C.restructure_room(league, league.contracts[best[1]], S),
                                               int(need * 1.3) + 1))
            moves.append(("restructure", best[1]))
            continue
        if not allow_cuts:
            return moves
        table = league.fa.get("_table") or M.market_table(league)
        cands = []
        # In the offseason only the top 51 count: cutting a player there lets the
        # 52nd biggest hit in; cutting one outside it saves nothing.
        t51 = C.top51_in_force(league) if top51 is None else top51
        team_ids = [x for x in C.players_with_team(league, tid) if x in league.contracts
                    and not (t51 and x in getattr(league, "practice", {}))]
        hits = sorted((C.cap_hit(league, league.contracts[x], S) for x in team_ids), reverse=True)
        line = hits[C.TOP_51 - 1] if t51 and len(hits) >= C.TOP_51 else 0
        nxt = hits[C.TOP_51] if t51 and len(hits) > C.TOP_51 else 0
        on53 = sum(1 for t in league.rosters.values() if t == tid)
        practice = getattr(league, "practice", {})
        # His replacement is paid only for the weeks left (Oct 23: a full year at the minimum
        # was counted all season, so late in a season almost no cut seemed to save anything).
        refill = C.min_salary(league, 1) * (C.PAY_WEEKS - C.pay_week(league)) / C.PAY_WEEKS
        for pid in team_ids:
            if pid in practice:
                continue        # a practice squad spot is refilled at the same pay: cutting saves nothing
            c = league.contracts[pid]
            use_june, prev = C.best_release(league, pid)
            hit = C.cap_hit(league, c, S)
            saved = prev["savings"]
            if t51:
                saved = (hit - nxt if hit >= line else 0) - prev["dead"].get(S, 0)
            if pid in league.rosters and on53 <= ROSTER_SIZE:
                # The spot has to be refilled, at about the minimum: only what's saved beyond that
                # helps. (Before Oct 23, getting under the cap at week 1 cut and refilled minimum
                # players round after round: a team over by $38M went down to 11 players.)
                saved -= refill
            if saved <= min(0.001 * cap, need / 2):     # a cut worth it (or half of a small need)
                continue
            value = table[pid]["price"] * cap
            cands.append((value / saved, pid, use_june))
        if not cands:
            return moves
        _ratio, pid, use_june = min(cands)
        p = league.player(pid)
        C.release(league, pid, june1=use_june)
        if pid in league.rosters:
            _let_go(league, pid, tid, _status(p), "released (cap)")
        else:
            getattr(league, "practice", {}).pop(pid, None)
            getattr(league, "reserve", {}).pop(pid, None)
        from .transactions import log
        log(league, "Cap", tid, pid, "Released", "to get under the cap")
        moves.append(("release", pid))
    return moves


def request_cap_moves(league, tid):
    """Your team is over the cap: your staff proposes the moves (restructures
    first, then cuts) and asks you; nothing happens until you approve
    (Blake's rule: the staff checks in before a bigger-than-normal move)."""
    from .transactions import important_reason
    S = league.season
    cap = C.cap_for(league, S)
    reqs = league.__dict__.setdefault("staff_requests", [])
    short = -C.cap_room(league, tid)
    if short <= 0:
        return []
    made = []
    for pid in sorted(C.players_with_team(league, tid), key=lambda x: -C.restructure_room(
            league, league.contracts[x], S) if x in league.contracts else 0):
        c = league.contracts.get(pid)
        r = C.restructure_room(league, c, S) if c else 0
        if r <= 0.002 * cap or short <= 0:
            continue
        p = league.player(pid)
        n = min(C.years_left(c, S), C.MAX_PRORATION_YEARS)
        save = r - r // n
        req = {"pid": pid, "then": {"cap": "restructure"}, "team": tid, "when": "Start of league year",
               "why": f"Restructure {p.position} {p.first_name} {p.last_name}'s contract (turn {C.fmt_money(r)} of "
                      f"salary into bonus) to save {C.fmt_money(save)} of cap room this season?"}
        if any(x.get("pid") == pid and x.get("then") == req["then"] for x in reqs):
            short -= save                      # already asked (still waiting for your answer)
            continue
        reqs.append(req)
        made.append(req)
        short -= save
    if short > 0:
        table = M.market_table(league)
        cands = []
        for pid in C.players_with_team(league, tid):
            _june, prev = C.best_release(league, pid)
            if prev["savings"] > 0:
                cands.append((table[pid]["price"] * cap / prev["savings"], pid, prev))
        for _r, pid, prev in sorted(cands):
            if short <= 0:
                break
            p = league.player(pid)
            why = important_reason(league, tid, p)
            req = {"pid": pid, "then": {"cap": "release"}, "team": tid, "when": "Start of league year",
                   "why": f"Release {p.position} {p.first_name} {p.last_name}" + (f" ({why})" if why else "")
                          + f" to get under the cap? Saves {C.fmt_money(prev['savings'])}, leaves "
                            f"{C.fmt_money(sum(prev['dead'].values()))} in dead money."}
            if any(x.get("pid") == pid and x.get("then") == req["then"] for x in reqs):
                short -= prev["savings"]           # already asked
                continue
            reqs.append(req)
            made.append(req)
            short -= prev["savings"]
    return made


def answer_cap_request(league, index, approve):
    """You approved or declined one of your staff's cap requests. (done, message)."""
    reqs = league.__dict__.get("staff_requests", [])
    if not 0 <= index < len(reqs) or "cap" not in reqs[index].get("then", {}):
        return False, "That request is gone."
    r = reqs.pop(index)
    if not approve:
        return True, "Declined: nothing changed."
    pid = r["pid"]
    c = league.contracts.get(pid)
    if c is None or c["team"] != r["team"]:
        return False, "He's no longer under contract with you: nothing changed."
    if r["then"]["cap"] == "restructure":
        saved = C.restructure(league, pid)
        return True, f"Done: {C.fmt_money(saved)} of cap room this season."
    use_june, _prev = C.best_release(league, pid)
    out = C.release(league, pid, june1=use_june)
    league.rosters.pop(pid, None)
    getattr(league, "practice", {}).pop(pid, None)
    getattr(league, "reserve", {}).pop(pid, None)
    from .transactions import log
    log(league, "Cap", r["team"], pid, "Released", "you approved your staff's request")
    return True, f"Released. Dead money: {C.fmt_money(sum(out.values()))}."


# ---------------------------------------------------------------------------
# The market
# ---------------------------------------------------------------------------

def staff_resign_pending(league, rng=None):
    """Until the contract screens exist (Oct 23, PROVISIONAL for Blake): your
    staff handles your expiring players before the market opens. Important
    players (a starter or first backup, top-25, captain, recent high pick;
    transactions.important_reason) are re-signed at their asking price
    whenever it fits under the cap, so no key player walks on his own;
    others the way AI teams decide (would they keep him in that role, and
    teams churn depth). Logged as staff moves. Returns the re-signed ids."""
    from .transactions import important_reason, log
    user = league.user_team_id
    pending = list(league.fa.get("pending", []))
    if user is None or not pending:
        return []
    rng = rng or random.Random(f"fa-staff-{_salt(league)}-{league.season}")
    table = M.market_table(league)
    depth = depth_lists(league, table, exclude=set(pending))
    quality = team_quality(league)
    S = league.season
    signed_ids = []
    for pid in sorted(pending, key=lambda x: -table[x]["price"]):
        p = league.player(pid)
        info = table[pid]
        ask = info["price"] * (1 + RESIGN_PREMIUM * (1.5 - p.loyalty / 100))
        key = important_reason(league, user, p)
        if not key:
            w, role = willingness(league, user, p, info, depth, quality)
            if w <= 0 or (role == "depth" and rng.random() >= DEPTH_KEEP):
                continue
        c = make_deal(league, p, user, ask, rng)
        if C.room_after(league, user, _first_hit(league, c)) < 0:
            continue
        C.sign(league, c, phase="re-sign", new_team=False)
        league.fa["pending"].remove(pid)
        depth[user][p.position].append(team_score(league, user, p, info))
        depth[user][p.position].sort(reverse=True)
        log(league, "Start of league year", user, pid, "Re-signed",
            f"{len(c['years'])} yr, {C.fmt_money(c['apy'])} a year; staff move" + (f" ({key})" if key else ""))
        signed_ids.append(pid)
    return signed_ids


def open_market(league):
    """Your expiring players you haven't re-signed become free agents."""
    for pid in league.fa.get("pending", []):
        if pid not in league.contracts and pid in league.rosters:
            _let_go(league, pid, league.rosters[pid], league.fa["status"].get(pid, "UFA"), "not re-signed")
    league.fa["pending"] = []


def free_agent_list(league):
    """Free agents who can sign now (not injured long-term)."""
    inj = getattr(league, "injuries", {})
    return [p for p in league.free_agents() if not (inj.get(p.id, {}).get("weeks", 0) > 17)]


def market(league, waves, rng=None, before_draft=None):
    """Run free agency waves. Each wave: every AI team bids on the free agents
    it wants (at most what the role is worth to it, within its cap room); the
    top bid is about what the second-highest bidder would pay (bidding wars
    push prices up); each player picks the offer he likes best (money first,
    then winning, loyalty, playing time), if it meets his ask. Unsigned
    players ask for less in later waves. Returns the signings."""
    ensure(league)
    open_market(league)
    rng = rng or random.Random(f"fa-market-{_salt(league)}-{league.season}-{waves[0]}")
    S = league.season
    cap = C.cap_for(league, S)
    quality = team_quality(league)
    signings = []
    for wave in waves:
        pre = (wave in PRE_DRAFT_WAVES) if before_draft is None else before_draft
        if wave in POST_DRAFT_WAVES:
            lapse_your_options(league)        # the option deadline (early May) has passed
        fas = free_agent_list(league)
        if not fas:
            break
        if wave in SUMMER_WAVES:
            summer_asks(league)               # leftover players see what's really out there
        table = M.market_table(league)        # prices hold through the wave (the same players are ranked)
        landed = defaultdict(int)             # signings each team has made this wave
        memo = {}                             # each staff's view of each player, for the wave
        for rnd in range(WAVE_ROUNDS):
            if rnd:
                fas = free_agent_list(league)
                if not fas:
                    break
            n_signed = len(signings)
            _bidding_round(league, wave, pre, fas, table, quality, cap, rng, signings, landed, memo)
            if len(signings) == n_signed:
                break                         # nobody signed this round: the wave is over
    return signings


def _bidding_round(league, wave, pre, fas, table, quality, cap, rng, signings, landed, memo=None):
    """One round of a wave: every AI team bids on the free agents it wants (its
    offers this wave, less the players it has already landed), then each player
    picks the offer he likes best. Adds to signings and landed. memo: see team_score."""
    S = league.season
    depth = depth_lists(league, table, memo=memo)
    bids = defaultdict(list)
    at_pos = defaultdict(list)                  # (team, position) -> player ids on its 53, for making room
    for pid, t in league.rosters.items():
        at_pos[(t, league.player(pid).position)].append(pid)
    for tid in sorted(ai_teams(league), key=lambda _t: rng.random()):
        room = C.cap_room(league, tid) - _reserve_share(league, tid, pre) * cap + _restructure_left(league, tid)
        z_fa = gm_style(league, tid, "fa")
        room -= GM_FA_HOLD * max(0.0, -z_fa) * cap      # builds through the draft
        outside_left = _outside_left(league, tid, cap)
        fits = C.cap_room(league, tid) - _keep_k(league, tid, pre, cap) + _restructure_left(league, tid)
        spots = OFFSEASON_ROSTER_MAX - roster_count(league, tid)
        cands = []
        for p in fas:
            info = table[p.id]
            if len(depth[tid][p.position]) >= camp_max(p.position):
                continue
            s = team_score(league, tid, p, info, memo)
            w, role = willingness(league, tid, p, info, depth, quality, score=s)
            if w <= 0 or w < ask_share(info, wave):
                continue
            gain = s - (depth[tid][p.position][STARTER_COUNT.get(p.position, 1) - 1]
                        if len(depth[tid][p.position]) >= STARTER_COUNT.get(p.position, 1) else 0)
            cands.append(({"starter": 0, "backup": 1, "depth": 2}[role], -gain, p, w, role))
        cands.sort(key=lambda x: (x[0], x[1]))
        used_pos = set()
        spent = 0
        made = 0
        limit = max(1, round(OFFERS_PER_WAVE.get(wave, 10) * math.exp(GM_FA_OFFERS_K * max(0.0, z_fa))))
        limit -= landed[tid]
        if limit <= 0:
            continue
        for _r, _g, p, w, role in cands:
            if made >= limit or spots - made <= 0:
                break
            if p.position in used_pos:
                continue
            est = ask_share(table[p.id], wave) * cap * 0.9
            cut_k = 0
            # (in the summer it bids with what it would keep after signing, the room summer_asks counted on)
            gate = fits if wave in SUMMER_WAVES else room
            if spent + est > gate:
                # No room: for a player who'd start, the team could release a worse veteran there.
                cut = (_room_cut(league, tid, p, table[p.id], table, at_pos[(tid, p.position)], memo)
                       if role == "starter" else None)
                if cut is None or spent + est > gate + cut[2]:
                    continue
                cut_k = cut[2]
            # It never offers more than it can fit (Oct 23: before, bids were checked at 90% of his ask but
            # the winner paid up to the next bidder's figure; when that didn't fit the deal fell through,
            # about 97 deals an offseason, and good players sat unsigned while teams still had room).
            w = min(w, (fits + cut_k - spent) / cap)
            if w < ask_share(table[p.id], wave):
                continue
            outside = league.fa["former"].get(p.id) != tid and table[p.id]["price"] >= M.MARKET_LINE
            if outside and tid != league.user_team_id and est > outside_left:
                continue                 # his GM's ceiling for other teams' players this year
            if outside:
                outside_left -= est
            used_pos.add(p.position)
            spent += est
            made += 1
            bids[p.id].append((tid, w, role))
    for pid, offer in league.fa.get("user_offers", {}).items():
        if league.player(pid).id in {p.id for p in fas}:
            bids[pid].append((offer["team"], offer["apy"] / cap, "user"))
    # Each player chooses.
    for pid in sorted(bids, key=lambda x: -table[x]["price"]):
        p = league.player(pid)
        if pid in league.rosters:
            continue
        info = table[pid]
        ask = ask_share(info, wave)
        lst = sorted(bids[pid], key=lambda b: -b[1])
        role_of = {(pid, tid): role for tid, _w, role in lst}
        second = lst[1][1] if len(lst) > 1 else ask
        offers = []
        uo = league.fa.get("user_offers", {}).get(pid)
        for i, (tid, w, role) in enumerate(lst):
            amount = max(ask, min(w, second)) if i == 0 else w
            if role == "user":
                # Your offer: what you offered, weighed with its years and guarantees (with
                # OFFER_ROUNDING of slack: the screens round money to $10K).
                amount = offer_value(league, pid, uo["apy"], uo["years"], uo["guaranteed"],
                                     asking_terms(league, pid, tid, wave, table=table)) / cap
                amount = max(amount, ask) if amount >= ask - OFFER_ROUNDING / cap else amount
            if amount < ask:
                continue
            u = amount / max(info["price"], 1e-9)
            u += WINNER_K * ((p.wants_winner - 50) / 50) * (quality.get(tid, 0.5) - 0.5)
            if tid == league.fa["former"].get(pid):
                u += FAMILIAR + LOYALTY_K * (p.loyalty - 50) / 50
            if role == "starter":
                u += ROLE_K
            u += rng.gauss(0, CHOICE_SD)
            offers.append((u, tid, amount))
        for _u, tid, amount in sorted(offers, reverse=True):
            if tid == league.user_team_id and uo is not None:
                c = C.build(league, pid, tid, "veteran" if uo["apy"] / cap > M.MINIMUM_LINE else "minimum",
                            league.season, uo["years"], uo["apy"], guaranteed=uo["guaranteed"])
                if C.room_after(league, tid, C.cap_hit(league, c)) < 0:
                    continue          # your offer can't fit under your cap any more: he looks elsewhere
            else:
                c = make_deal(league, p, tid, amount, rng)
            if tid != league.user_team_id:
                keep = _keep_k(league, tid, pre, cap)
                if C.room_after(league, tid, _first_hit(league, c)) < keep and \
                        not (role_of.get((pid, tid)) == "starter"
                             and (_make_room(league, tid, _first_hit(league, c) + keep, rng)
                                  or _cut_to_fit(league, tid, p, info, table, _first_hit(league, c) + keep))):
                    continue
                if roster_count(league, tid) >= OFFSEASON_ROSTER_MAX:
                    continue
                # The multi-year plan: another team's player on a long deal can't push next
                # season's commitments past what this team will commit now; it offers one year.
                if (league.fa["former"].get(pid) != tid and len(c["years"]) > 1
                        and C.commitments(league, tid, S + 1) + C.cap_hit(league, c, S + 1, full=True)
                        > plan_next(league, tid) * C.cap_for(league, S + 1)):
                    c = make_deal(league, p, tid, amount, rng, years=1)
                    if C.room_after(league, tid, _first_hit(league, c)) < keep:
                        continue
            former = league.fa["former"].get(pid)
            if former != tid and c["apy"] / cap >= M.MARKET_LINE:
                spent_out = league.fa.setdefault("outside_spent", {})
                spent_out[tid] = spent_out.get(tid, 0.0) + c["apy"] / cap
            _sign(league, p, c, WAVES.get(wave, "Free agency"), "free agency", f"FA wave {wave}",
                  new_team=(former is not None and former != tid) if former is not None else True)
            signings.append({"wave": wave, "pid": pid, "team": tid, "apy": c["apy"], "years": len(c["years"]),
                             "former": former})
            landed[tid] += 1
            league.fa.get("user_offers", {}).pop(pid, None)
            break


def tagged_long_term(league, rng=None):
    """Before the season, about half of tagged players sign long-term deals
    (AI teams; yours stays on the tag unless you extend him from the Payroll
    view: Blake, Oct 23, your staff doesn't sign your players for you)."""
    rng = rng or random.Random(f"fa-tagdeal-{_salt(league)}-{league.season}")
    table = M.market_table(league)
    n = 0
    for tid, pid in list(league.fa.get("tags", {}).items()):
        if tid == league.user_team_id:
            continue
        c = league.contracts.get(pid)
        if c is None or c["kind"] != "tag" or c["team"] != tid or rng.random() >= LONG_TERM_AFTER_TAG:
            continue
        p = league.player(pid)
        tags = c["tags"]
        new = make_deal(league, p, tid, table[pid]["price"], rng, kind="veteran",
                        years=max(3, M.deal_years(table[pid]["price"], _age(league, p), p.position, rng)))
        if C.room_after(league, tid, _first_hit(league, new) - C.cap_hit(league, c)) < 0:
            continue
        new["tags"] = tags
        C.sign(league, new, phase="long-term after tag", new_team=False)
        n += 1
    return n


# ---------------------------------------------------------------------------
# The draft, cut-downs, and the safety net
# ---------------------------------------------------------------------------

def set_pick_reserve(league, order):
    """Before free agency: each AI team keeps cap room for its draft class
    (one pick a round at its spot in the order)."""
    cap = C.cap_for(league, league.season)
    n = len(order)
    from .trades import pick_owners     # picks traded away or picked up (trades.py, Oct 23)
    owners = pick_owners(league, league.season)
    held = {tid: [] for tid in order}
    for i, orig in enumerate(order):
        for rnd in range(7):
            held.setdefault(owners.get((rnd + 1, orig), orig), []).append(rnd * n + i + 1)
    out = {}
    for tid in order:
        total = sum(C.rookie_apy_share(pick) * cap for pick in held.get(tid, []))
        # rookies push minimum players out of the top 51
        out[tid] = max(0.0, total / cap - len(held.get(tid, [])) * C.min_salary(league, 1) / cap)
    league.fa["pick_reserve"] = out
    return out


def sign_draft_picks(league, picks):
    """Rookie-scale deals for the draft class (picks: offseason.run_draft's)."""
    for d in picks:
        c = C.rookie_contract(league, d["pid"], d["team"], d["pick"], d["round"])
        C.sign(league, c, phase="draft", new_team=False)
    _after_rookies(league)
    lapse_your_options(league)          # the fifth-year option deadline comes right after the draft


def sign_undrafted(league, signed):
    """[(pid, team)] undrafted rookies: 3-year minimum deals."""
    rng = random.Random(f"fa-udfa-{_salt(league)}-{league.season}")
    for pid, tid in signed:
        C.sign(league, C.udfa_contract(league, pid, tid, rng=rng), phase="undrafted", new_team=False)
    _after_rookies(league)


def _after_rookies(league):
    rng = random.Random(f"fa-rookies-{_salt(league)}-{league.season}")
    league.fa["pick_reserve"] = {}
    for tid in ai_teams(league):
        if C.cap_room(league, tid) < IN_SEASON_BUFFER * C.cap_for(league, league.season):
            _comply(league, tid, rng, target=IN_SEASON_BUFFER)


def final_compliance(league, full=None):
    """After final cuts and practice squads (before week 1, when every
    contract starts to count, not just the top 51), and after each week's
    moves during the season: AI teams get under the cap (restructures first,
    as real teams do in-season; cuts only if that's not enough); your staff
    asks you if you're over. full: count every contract (None: every
    contract once the regular season has started; before that, during the
    offseason, camp and the preseason, only the top 51, so a 90-man camp
    roster isn't counted in full)."""
    if full is None:
        full = getattr(league, "stage", "") not in ("offseason", "preseason")
    t51 = None if not full else False
    rng = random.Random(f"fa-final-{_salt(league)}-{league.season}")
    moves = {}
    from . import transactions as T
    for tid in ai_teams(league):
        if C.cap_room(league, tid, top51=t51) < 0:
            moves[tid] = _comply(league, tid, rng, target=0.0, top51=t51)
            if full and C.cap_room(league, tid, top51=False) < 0:
                # Nothing left to restructure and no cut that saves money once the spot is
                # refilled: the team carries fewer players instead (Oct 25, transactions.cap_squeeze).
                moves[tid] += T.cap_squeeze(league, tid)
    user = league.user_team_id
    if user is not None and C.cap_room(league, user, top51=t51) < 0:
        request_cap_moves(league, user)
    return moves


def retirement_contract_factor(league, p, typical_age):
    """A multiplier on his chance to retire this offseason (offseason.retirements)
    when he's still under contract for the coming season. Real players under
    contract rarely retire (they're released instead, or play on), and almost
    never walk away from real money before their prime ends, while an old star
    still might (Brees, Whitworth). Players whose contract just ended keep the
    plain odds (offseason.retirement_chance, fitted to real career lengths).
    Fitted to the real rates (Oct 24; Blake: "make sure its as accurate as you
    can get it"): players on the NFL's reserve/retired list in 2021-22 (nflverse
    rosters, status RET; the list is for players who retire under contract),
    out of the players on a roster under an OverTheCap contract that season:
    1.0% a season; by age under 26 0.3%, 26-29 1.1%, 30-32 2.4%, 33+ 6.3%; none
    of the ~865 players under 30 paid 1.5%+ of the cap retired, while 10% of
    those 33+ paid 4%+ did. The game with this factor: 0.4% / 0.6% / 2.4% / 6.2%
    (before: 2.7% / 6.2% / 14.8% / 21.1%, five times the real rate overall,
    and retirees' leftover bonuses were the biggest source of dead money).
    Money he'd give up: this season's base salary plus guaranteed salary still
    to come, as a share of the cap; it counts in full until 3 years before his
    position's usual retiring age and not at all from 3 years after it."""
    c = getattr(league, "contracts", {}).get(p.id)
    if c is None or c["kind"] == "practice" or C.last_season(c) < league.season:
        return 1.0
    S = league.season
    money = sum(y["base"] if y["season"] == S else y["gtd"] for y in c["years"] if y["season"] >= S)
    share = money / C.cap_for(league, S)
    age = _age(league, p)
    youth = max(0.0, min(1.0, 1.0 - (age - (typical_age - 3)) / 6))
    scale = RETIRE_UC_SCALE * math.exp(RETIRE_UC_AGE * max(-8.0, min(4.0, age - typical_age)))
    return scale * math.exp(-share / RETIRE_MONEY_K * youth)


def cut_money_value(league, p):
    """Roster-value points the money adds to keeping him at a cut-down:
    + for the dead money cutting him would leave (it's spent either way),
    - for the cap room cutting him would free (over a minimum-salary
    replacement). Replaces offseason.cut_to_53's VET_COST_K stand-in."""
    if p.id not in getattr(league, "contracts", {}):
        return 0.0
    cap = C.cap_for(league, league.season)
    prev = C.release_preview(league, p.id)
    return (DEAD_KEEP_PER_PCT * 100 * sum(prev["dead"].values()) / cap
            - CUT_SAVE_PER_PCT * 100 * max(0, prev["savings"] - C.min_salary(league, 1)) / cap)


def cut_down(league):
    """Every team cuts to 53 with each position at its roster count, like
    offseason.cut_to_53 but money-aware: cutting a player who'd leave a lot
    of dead money is less appealing (real teams keep guaranteed players
    longer). Cuts are charged to the cap. Returns [(pid, team)]. Your team
    included, for now (the placeholder offseason picks for everyone)."""
    from .league import roster_value
    from .offseason import HIGH_PICK_KEEP
    cap = C.cap_for(league, league.season)
    cuts = []
    for t in league.teams:
        roster = league.team_players(t.id)
        by_pos = defaultdict(list)
        for p in roster:
            by_pos[p.position].append(p)
        for position, group in by_pos.items():
            want = ROSTER_TEMPLATE.get(position, 0)
            if len(group) <= want:
                continue

            def keep_value(p):
                from .evaluation import seen
                v = roster_value(seen(league, t.id, p))      # as this team's staff sees him
                if p.draft_year == league.season and 1 <= p.draft_round <= 3:
                    v += HIGH_PICK_KEEP
                return v + cut_money_value(league, p)
            group.sort(key=keep_value, reverse=True)
            for p in group[want:]:
                league.rosters.pop(p.id, None)
                C.release(league, p.id)
                cuts.append((p.id, t.id))
    return cuts


def in_season_terms(league, pid, week=None):
    """A free agent's terms during the season: 1 year, at least the minimum;
    a market-level player still wants IN_SEASON_ASK of his price (no
    signing a good player for the minimum). Paid from this week on."""
    week = C.pay_week(league) if week is None else week
    # Prices barely move during a season: one table per season (kept off the saved state).
    cached = league.__dict__.get("_fa_table")
    if not cached or cached[0] != league.season or pid not in cached[1]:
        cached = (league.season, M.market_table(league))
        league.__dict__["_fa_table"] = cached
    info = cached[1].get(pid)
    share = max(info["minimum"], info["price"] * IN_SEASON_ASK) if info else 0
    return {"apy_share": share, "week": week}


def _deal_rng(league, pid, week):
    """The dice for a free agent's in-season deal. The same for the check that the team can
    afford him (asking_hit, AffordCheck) and for the contract sync writes at the week's end, so
    the deal checked is the deal signed (Oct 25: the check used other dice, the signing bonus
    came out different, and a team at the cap could end up a few hundred $K over)."""
    return random.Random(f"sync-{_salt(league)}-{pid}-{week}")


def asking_hit(league, tid, pid, week=None):
    """This season's cap hit ($K) of the deal this free agent would sign now."""
    terms = in_season_terms(league, pid, week)
    p = league.player(pid)
    c = make_deal(league, p, tid, terms["apy_share"], _deal_rng(league, pid, terms["week"]), years=1,
                  week=terms["week"])
    return C.cap_hit(league, c)


def pending_hits(league, tid, full=False):
    """$K of this season's cap for players a team signed this week whose contracts aren't
    written yet (sync writes them at the end of the week), and for this week's releases
    (pending_release_charges). Oct 23: each in-season signing was checked as if the team's
    other new signings that week didn't exist, so two signings that each fit could together
    put a team over the cap. While only the top 51 count (offseason, camp) it's left out: a
    cheap new signing there usually isn't among the 51 biggest hits. full: counted anyway
    (checks against every contract, e.g. between final cuts and week 1)."""
    if C.top51_in_force(league) and not full:
        return 0
    total = 0
    practice = getattr(league, "practice", {})
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        if c is None or c["team"] != tid:
            if pid in practice:
                # (sync writes him a practice squad deal; before Oct 25 he was priced like a
                # free agent signed to the 53)
                total += C.ps_weekly(league, league.player(pid).experience) * (C.PAY_WEEKS - C.pay_week(league))
            else:
                total += asking_hit(league, tid, pid)
        elif c["kind"] == "practice" and pid in league.rosters:
            # Promoted to the 53 this week: sync swaps his squad deal for a minimum one (he
            # was counted at squad pay until then).
            S, week = league.season, C.pay_week(league)
            unpaid = C.cap_hit(league, c) - C.release_charges(league, c).get(S, 0)
            minimum = C.min_salary(league, league.player(pid).experience) * (C.PAY_WEEKS - week) / C.PAY_WEEKS
            total += max(0, int(minimum - unpaid))
    return total + pending_release_charges(league, tid)


def pending_release_charges(league, tid):
    """$K of this season's cap still owed for players this team let go this week: cap_room
    stops counting a released player's contract at once, but what stays on the cap (a vested
    veteran's termination pay, bonus money) is charged only when sync runs at the week's end.
    Oct 25: in between, a team at the cap that cut a vested veteran (it saves nothing in
    season) looked as if it had his whole cap hit to spend, signed his replacement, and was
    over once the charge was written."""
    S = league.season
    total = 0
    for pid, c in league.contracts.items():
        if c["team"] != tid or on_team(league, pid) == tid or C.last_season(c) < S:
            continue
        if league.player(pid).retired is not None:
            continue                     # (retire() charges only the bonus money: left out, it's small)
        total += C.release_charges(league, c).get(S, 0)
    return total


def affordable(league, tid, pid, week=None, also=0):
    """Can this team sign this free agent now and stay under the cap (also:
    $K of other signings it's making that aren't on the books yet; this week's
    unwritten signings are counted too: pending_hits)?"""
    if _all_count(league):
        left = (C.cap_room(league, tid, top51=False) - pending_hits(league, tid, full=True)
                - asking_hit(league, tid, pid, week) - also)
    else:
        left = C.room_after(league, tid, asking_hit(league, tid, pid, week) + also + pending_hits(league, tid))
    return left >= (0 if tid == league.user_team_id else 0)


def _all_count(league):
    """Between final cuts and week 1's games: the top-51 rule is still in force, but every
    contract is about to count (week 1), so checks count them all (Oct 25: a team that fit by
    the top 51 at final cuts could start the season over the cap)."""
    from .transactions import _every_contract_counts
    return C.top51_in_force(league) and _every_contract_counts(league)


class AffordCheck:
    """affordable() for many (team, player) pairs at once: each team's cap figures and
    each player's asking deal are worked out once (a final-cuts waiver run asks ~40,000
    times; that took ~8 of its 15 seconds). Same answers as affordable(). Call
    invalidate(tid) after that team's roster or money changes."""

    def __init__(self, league):
        self.league = league
        self.teams = {}
        self.hits = {}

    def hit(self, tid, pid):
        if pid not in self.hits:
            terms = in_season_terms(self.league, pid)
            c = make_deal(self.league, self.league.player(pid), tid, terms["apy_share"],
                          _deal_rng(self.league, pid, terms["week"]), years=1, week=terms["week"])
            self.hits[pid] = C.cap_hit(self.league, c)
        return self.hits[pid]

    def ok(self, tid, pid):
        L = self.league
        new = self.hit(tid, pid)
        if tid not in self.teams:
            if _all_count(L):
                self.teams[tid] = (None, None, C.cap_room(L, tid, L.season, top51=False)
                                   - pending_hits(L, tid, full=True))
            elif C.top51_in_force(L):
                practice = getattr(L, "practice", {})
                hits = sorted((C.cap_hit(L, L.contracts[x], L.season) for x in C.players_with_team(L, tid)
                               if x in L.contracts and L.contracts[x]["team"] == tid and x not in practice),
                              reverse=True)[:C.TOP_51]
                self.teams[tid] = (hits, sum(hits), C.adjusted_cap(L, tid, L.season) - C.charges(L, tid, L.season))
            else:
                self.teams[tid] = (None, None, C.cap_room(L, tid, L.season) - pending_hits(L, tid))
        hits, total, base = self.teams[tid]
        if hits is None:
            left = base - new
        elif len(hits) < C.TOP_51:
            left = base - total - new
        else:
            left = base - (total - hits[-1] + max(new, hits[-1]))
        return left >= 0

    def invalidate(self, tid):
        self.teams.pop(tid, None)


def sync(league, label=""):
    """Bring money in line with where players are (call after any roster step
    that doesn't handle contracts itself):
      - a player who left a team (released, waived, retired): his cut is charged
      - a waiver claim takes over the rest of the contract (bonus money stays behind)
      - a practice squad player promoted to the 53: a minimum deal through next season
      - a player moved to the practice squad: a practice squad deal
      - anyone else on a team without a contract: a 1-year deal (the minimum,
        or more for a market-level player during the season)
    Returns counts."""
    ensure(league)
    out = defaultdict(int)
    week = C.pay_week(league)
    practice = getattr(league, "practice", {})
    # Contracts whose player is no longer with that team.
    for pid, c in list(league.contracts.items()):
        if C.last_season(c) < league.season:
            continue              # ran out: start_league_year deals with it
        p = league.player(pid)
        tid = on_team(league, pid)
        if tid == c["team"]:
            if pid in practice and c["kind"] != "practice":
                C.release(league, pid)
                C.sign(league, C.practice_contract(league, pid, tid, week=week), phase="practice squad")
                out["to_practice"] += 1
            elif pid not in practice and c["kind"] == "practice":
                C.release(league, pid)
                # young players promoted usually sign through next season; veterans for the rest of this one
                years = 2 if week < C.PAY_WEEKS and p.experience <= 2 else 1
                C.sign(league, C.minimum_contract(league, pid, tid, years=years, week=week),
                       phase="promoted", new_team=False)
                out["promoted"] += 1
            continue
        if p.retired is not None:
            C.retire(league, pid)
            out["retired"] += 1
            continue
        if tid is not None and _claimed(league, pid, tid):
            _take_over(league, c, tid, week)
            out["claimed"] += 1
            continue
        C.release(league, pid)
        out["released"] += 1
    # Players on a team without a contract. (Not your expiring players in the exclusive
    # window: they're yours to re-sign or let go. Before Oct 23 any roster move then, a
    # release on the Roster tab say, signed all of them to minimum deals.)
    pending = set(league.fa.get("pending", []) or [])
    for pid in list(league.rosters) + list(practice) + list(getattr(league, "reserve", {})):
        tid = on_team(league, pid)
        if tid is None or pid in league.contracts or pid in pending:
            continue
        p = league.player(pid)
        if pid in practice:
            c = C.practice_contract(league, pid, tid, week=week)
        elif week > 0 or getattr(league, "stage", "") == "preseason":
            # (In camp and the preseason too: before Oct 23 a free agent signed then got the
            # minimum whoever he was, so a starter-level player could be had for the minimum.
            # Camp bodies are minimum-level players, so they still get the minimum.)
            terms = in_season_terms(league, pid, week)
            c = make_deal(league, p, tid, terms["apy_share"], _deal_rng(league, pid, week), years=1, week=week)
        else:
            c = C.minimum_contract(league, pid, tid, years=1)
        former = league.fa.get("former", {}).get(pid)
        C.sign(league, c, phase=f"signed {label}".strip(), new_team=(former != tid) if former else True)
        out["new"] += 1
    return out


def _claimed(league, pid, tid):
    for t in reversed(league.transactions[-200:]):
        if t["pid"] == pid:
            return t["team"] == tid and t["move"] == "Claimed off waivers"
    return False


def _take_over(league, c, tid, week):
    """Waiver claim: the new team takes over the base salaries from now on;
    the bonus money stays on the old team's cap."""
    S = league.season
    old_team = c["team"]
    rest_bonus = sum(y["bonus"] for y in c["years"] if y["season"] >= S)
    earned = 0
    cur = C._year(c, S)
    if cur and week:
        start = c["week"] if c["signed"] == S else 0
        earned = cur["base"] * max(0, week - start) / C.PAY_WEEKS
    C.add_charge(league, old_team, S, rest_bonus + earned)
    new = dict(c)
    new["years"] = [dict(y, bonus=0) for y in c["years"] if y["season"] >= S]
    new["team"] = tid
    new["signed"] = S
    new["week"] = week
    new["kind"] = c["kind"] if c["kind"] != "practice" else "minimum"
    league.contracts[c["pid"]] = new


def elevation_pay(league, tid, pids):
    """A practice squad player elevated for a game is paid a week at the
    minimum for his experience (counts on the cap)."""
    for pid in pids:
        p = league.player(pid)
        C.add_charge(league, tid, league.season, C.min_salary(league, p.experience) / C.PAY_WEEKS)


# ---------------------------------------------------------------------------
# Your team: asking terms and offers (the screens' engine side)
# ---------------------------------------------------------------------------

def asking_terms(league, pid, tid, wave=None, table=None):
    """What a player wants from your team: {'apy' $K, 'years', 'guaranteed' $K,
    'mood'}. Before the market (your own expiring player) he asks his price
    plus a little (less if he's loyal); in the market, the wave's ask.
    table: cap_market.market_table, if the caller has it (it's slow to build)."""
    table = table or M.market_table(league)
    info = table[pid]
    p = league.player(pid)
    rng = random.Random(f"ask-{_salt(league)}-{league.season}-{pid}")
    if wave is None:
        share = info["price"] * (1 + RESIGN_PREMIUM * (1.5 - p.loyalty / 100))
    else:
        share = ask_share(info, wave)
    share = max(share, info["minimum"])
    cap = C.cap_for(league, league.season)
    years = M.deal_years(share, _age(league, p), p.position, rng)
    gtd = M.guarantee_share(share, years, p.position, rng)
    apy = int(round(share * cap))
    return {"apy": apy, "years": years, "guaranteed": int(round(gtd * apy * years)), "gtd_share": gtd}


def offer_value(league, pid, apy, years, guaranteed, ask):
    """How a player weighs an offer against his ask: guaranteed money counts
    extra; older players value more years, young ones less."""
    p = league.player(pid)
    age = _age(league, p)
    gshare = guaranteed / max(1, apy * years)
    v = apy * (1 + 0.25 * (gshare - ask["gtd_share"]))
    v *= 1 + (0.04 if age >= 29 else 0.01) * (years - ask["years"])
    return v


def respond(league, pid, tid, apy, years, guaranteed, patience_key=None, ask=None, patience=3):
    """Your offer to a player: ('accept' | 'counter' | 'reject', message, ask).
    He accepts at or above his ask (counting guarantees and years); within 10%
    he counters with his ask; lower offers wear his patience (3 lowball offers
    and he stops talking to you until the next wave). Re-signing your own
    player: loyalty softens it; in free agency, an accepted offer is placed and
    he chooses among all his offers at the end of the wave. ask: his terms, if
    not the usual ones (an extension's)."""
    st = league.fa.setdefault("patience", {})
    key = patience_key or f"{pid}-{league.fa.get('wave', 0)}"
    if st.get(key, 0) >= patience:
        return "reject", "He's done talking with you for now.", None
    wave = league.fa.get("wave")
    ask = ask or asking_terms(league, pid, tid, wave)
    v = offer_value(league, pid, apy, years, guaranteed, ask)
    p = league.player(pid)
    tolerance = 0.0
    if league.fa.get("former", {}).get(pid, on_team(league, pid)) == tid:
        # A loyal player gives his own team a little slack. (A disloyal one already asks
        # more, RESIGN_PREMIUM; before Oct 23 he also wanted more than his own ask here, so
        # an offer at the ask he'd just named drew a counter with that same ask.)
        tolerance = max(0.0, 0.03 * (p.loyalty - 50) / 50)
    if v >= ask["apy"] * (1 - tolerance) - OFFER_ROUNDING:
        return "accept", "He accepts.", ask
    if v >= ask["apy"] * 0.9:
        yrs = f"{ask['years']} year{'s' if ask['years'] != 1 else ''}"
        return "counter", f"He'd sign for {C.fmt_money(ask['apy'])} a year over {yrs}, " \
                          f"{C.fmt_money(ask['guaranteed'])} guaranteed.", ask
    st[key] = st.get(key, 0) + 1
    return "reject", "That's well short of what he's looking for.", ask


# ---------------------------------------------------------------------------
# Your team in the offseason (the Contracts tab; Blake, Oct 23: you run your own
# contracts, phases with a Next button, offer / counter / patience, rough interest only)
# ---------------------------------------------------------------------------

def _user_cap_room_after_offers(league, tid, exclude=None):
    """Your cap room now, less what your standing free-agency offers would cost."""
    room = C.cap_room(league, tid)
    for opid, o in league.fa.get("user_offers", {}).items():
        if opid != exclude:
            room -= o["apy"]           # (roughly a first-year hit)
    return room


def expiring_for_you(league):
    """Your expiring players in the exclusive window, best first: [{pid, status,
    ask, advice, why, tag, tenders}]. advice: your staff's recommendation
    ('Re-sign', 'Tag', 'Tender', 'Let go'); tag / tenders: the cost ($K) of
    each option open to him."""
    from .transactions import important_reason
    tid = league.user_team_id
    pending = [pid for pid in league.fa.get("pending", []) if pid in league.rosters]
    if tid is None or not pending:
        return []
    table = M.market_table(league)
    depth = depth_lists(league, table, exclude=set(pending))
    quality = team_quality(league)
    S = league.season
    out = []
    for pid in sorted(pending, key=lambda x: -table[x]["price"]):
        p = league.player(pid)
        info = table[pid]
        status = league.fa["status"].get(pid, _status(p))
        ask = asking_terms(league, pid, tid, table=table)
        old = league.fa.get("pending_old", {}).get(str(pid))
        w, role = willingness(league, tid, p, info, depth, quality)
        key = important_reason(league, tid, p)
        row = {"pid": pid, "status": status, "ask": ask, "role": role, "why": key, "tag": None, "tenders": {}}
        if status == "UFA" and tid not in league.fa.get("tags", {}):
            prior = C.cap_hit(league, old, S - 1, full=True) if old else 0
            row["tag"] = C.tag_amount(league, p.position, prior, old.get("tags", 0) if old and old["kind"] == "tag" else 0)
        if status == "RFA":
            base = old["years"][-1]["base"] if old else 0
            row["tenders"] = {lvl: C.rfa_tender(league, lvl, base) for lvl in ("rofr", "second", "first")}
        if status == "ERFA":
            row["tenders"] = {"erfa": C.min_salary(league, p.experience)}
        worth = w * C.cap_for(league, S) if w > 0 else 0
        if status == "ERFA" and role in ("starter", "backup", "depth") and w > 0:
            advice = "Tender"
        elif key and worth >= ask["apy"] * (1 - RESIGN_SLACK):
            advice = "Re-sign"
        elif row["tag"] and key and role == "starter" and info["price"] * C.cap_for(league, S) >= TAG_MIN_VALUE * row["tag"]:
            advice = "Tag"
        elif w > 0 and role != "depth" and worth >= ask["apy"] * (1 - RESIGN_SLACK):
            advice = "Re-sign"
        else:
            advice = "Let go"
        row["advice"] = advice
        out.append(row)
    return out


def resign_offer(league, pid, apy, years, guaranteed):
    """Your offer to one of your own expiring players in the exclusive window:
    ('accept' | 'counter' | 'reject', message). Accepted = signed now."""
    tid = league.user_team_id
    if pid not in league.fa.get("pending", []):
        return "reject", "He isn't one of your expiring players any more."
    result, msg, _ask = respond(league, pid, tid, apy, years, guaranteed, patience_key=f"resign-{pid}")
    if result == "accept":
        done, msg = accept_offer(league, pid, tid, apy, years, guaranteed)
        if not done:
            return "reject", msg
    return result, msg


def tag_or_tender(league, pid, kind):
    """Franchise tag ('tag') or a restricted tender ('rofr' / 'second' / 'first' /
    'erfa') for one of your expiring players. (done, message)."""
    tid = league.user_team_id
    rows = {r["pid"]: r for r in expiring_for_you(league)}
    r = rows.get(pid)
    if r is None:
        return False, "He isn't one of your expiring players any more."
    S = league.season
    old = league.fa.get("pending_old", {}).get(str(pid))
    if kind == "tag":
        if not r["tag"]:
            return False, "Only an unrestricted free agent can be tagged, and one tag a year."
        c = C.tag_contract(league, pid, tid, r["tag"], old.get("tags", 0) if old and old["kind"] == "tag" else 0)
        league.fa.setdefault("tags", {})[tid] = pid
        what = f"franchise tag, {C.fmt_money(r['tag'])} for {S}"
    elif kind == "erfa":
        c = C.minimum_contract(league, pid, tid, years=1, kind="tender")
        what = "exclusive-rights tender (1 year at the minimum)"
    else:
        amt = r["tenders"].get(kind)
        if amt is None:
            return False, "That tender isn't open to him."
        c = C.build(league, pid, tid, "tender", S, 1, amt, bases=[amt], signing_bonus=0)
        what = f"{ {'rofr': 'right-of-first-refusal', 'second': 'second-round', 'first': 'first-round'}[kind]} tender, " \
               f"{C.fmt_money(amt)}"
    if C.room_after(league, tid, C.cap_hit(league, c)) < 0:
        return False, "That would put you over the cap."
    C.sign(league, c, phase="re-sign", new_team=False)
    league.fa["pending"].remove(pid)
    from .transactions import log
    log(league, "Start of league year", tid, pid, "Re-signed", what)
    return True, f"Done: {what}."


def place_offer(league, pid, apy, years, guaranteed):
    """Your free-agency offer for this wave: ('accept' | 'counter' | 'reject',
    message). 'accept' means he'd take it: the offer stands, and when the wave
    plays out he picks the offer he likes best (yours or another team's)."""
    from .roster_rules import CAMP_LIMIT
    tid = league.user_team_id
    if pid not in {p.id for p in free_agent_list(league)}:
        return "reject", "He isn't a free agent right now."
    if roster_count(league, tid) + len(league.fa.get("user_offers", {})) >= CAMP_LIMIT and \
            pid not in league.fa.get("user_offers", {}):
        return "reject", f"Your offseason roster would go over {CAMP_LIMIT}: release someone first."
    if apy > _user_cap_room_after_offers(league, tid, exclude=pid):
        return "reject", "That doesn't fit under your cap with your other offers."
    result, msg, _ask = respond(league, pid, tid, apy, years, guaranteed)
    if result == "accept":
        league.fa.setdefault("user_offers", {})[pid] = {"team": tid, "apy": int(apy), "years": int(years),
                                                       "guaranteed": int(guaranteed)}
        msg = "He likes it. Your offer stands; he decides when the wave plays out (Next)."
    return result, msg


def withdraw_offer(league, pid):
    league.fa.get("user_offers", {}).pop(pid, None)


def interest(league, pids, wave=None, table=None):
    """Rough interest from other teams this wave: {pid: 'Several teams' / 'A few teams'
    / 'No other teams'} (how many AI teams would bid at his ask; never their offers)."""
    # (before the market opens, league.fa["wave"] is None: rate interest as for wave 1. Was
    # .get("wave", 1), which passed the None on and crashed the Contracts tab's Free agency
    # view in the coaching and re-sign phases; found by tools/screens_check.py, Oct 25)
    wave = wave or league.fa.get("wave") or 1
    table = table or M.market_table(league)
    depth = depth_lists(league, table)
    quality = team_quality(league)
    cap = C.cap_for(league, league.season)
    rooms = {tid: C.cap_room(league, tid) - _reserve_share(league, tid, wave in PRE_DRAFT_WAVES) * cap
             for tid in ai_teams(league)}
    out = {}
    for pid in pids:
        p = league.player(pid)
        info = table.get(pid)
        if info is None:
            out[pid] = "No other teams"
            continue
        ask = ask_share(info, wave)
        n = sum(1 for tid, room in rooms.items() if room > ask * cap
                and willingness(league, tid, p, info, depth, quality)[0] >= ask)
        out[pid] = "Several teams" if n >= 4 else ("A few teams" if n else "No other teams")
    return out


def accept_offer(league, pid, tid, apy, years, guaranteed):
    """Sign an accepted offer (your own expiring player in the exclusive
    window, or a free agent who chose you). Refused if it would put you over
    the cap. (done, message)."""
    p = league.player(pid)
    c = C.build(league, pid, tid, "veteran" if apy / C.cap_for(league, league.season) > M.MINIMUM_LINE
                else "minimum", league.season, years, apy, guaranteed=guaranteed)
    if C.room_after(league, tid, C.cap_hit(league, c)) < 0:
        return False, "That would put you over the cap."
    former = league.fa.get("former", {}).get(pid, on_team(league, pid))
    if pid in league.fa.get("pending", []):
        league.fa["pending"].remove(pid)
    _sign(league, p, c, "Free agency", "re-signed" if former == tid else "free agency", "your offer",
          new_team=former is not None and former != tid)
    return True, f"Signed: {years} years, {C.fmt_money(c['value'])}, {C.fmt_money(c['guaranteed'])} guaranteed."


# ---------------------------------------------------------------------------
# Your team, any time: extensions, fifth-year options, restructures and cuts
# (the Contracts tab's Payroll and Re-sign views)
# ---------------------------------------------------------------------------

def _when(league):
    """The transaction log's 'when' for a move you make now."""
    from .season import week_label
    return week_label(league)


def _drop_cap_requests(league, pid):
    """You handled him yourself: your staff's open cap requests about him go."""
    reqs = league.__dict__.get("staff_requests")
    if reqs:
        league.staff_requests = [r for r in reqs if not (r.get("pid") == pid and "cap" in r.get("then", {}))]


def _yours(league, pid):
    c = league.contracts.get(pid)
    tid = league.user_team_id
    if tid is None or c is None or c["team"] != tid or on_team(league, pid) != tid:
        return None
    return c


def _will_talk(league, pid, table):
    """Will he talk about an extension this league year? A market-level player
    in his last year who'd rather test free agency won't (decided once a
    season: asking again doesn't change it)."""
    p = league.player(pid)
    c = league.contracts[pid]
    info = table.get(pid)
    if C.years_left(c, league.season) > 1 or p.experience + 1 <= C.RFA:
        return True                        # signed beyond this year, or not headed for free agency
    if info is None or info["price"] < M.MARKET_LINE:
        return True
    loyal = p.loyalty / 100
    q = team_quality(league).get(c["team"], 0.5)
    bad_team = max(0.0, 0.5 - q) * 2 * max(0.0, (p.wants_winner - 50) / 50)
    chance = EXT_REFUSE_K * TEST_MARKET * (1.5 - loyal) * (1 + bad_team)
    return random.Random(f"ext-talk-{_salt(league)}-{league.season}-{pid}").random() >= chance


def extension_check(league, pid, table=None):
    """Can you offer him an extension now? (ok, reason in words). Real rules:
    a drafted rookie's deal can't be redone until after his 3rd season; a
    tagged player can sign long-term only until training camp (the real
    deadline is mid-July). Teams extend players with a year or two left."""
    c = _yours(league, pid)
    if c is None:
        return False, "He isn't under contract with you."
    p = league.player(pid)
    S = league.season
    if c["kind"] == "practice" or pid in getattr(league, "practice", {}):
        return False, "Practice squad players sign reserve/future deals when the season ends, not extensions."
    left = C.years_left(c, S)
    wait = {"rookie": ROOKIE_EXTEND_AFTER, "udfa": UDFA_EXTEND_AFTER}.get(c["kind"], 0) - p.experience
    if left > EXTEND_YEARS_LEFT:
        first = max(C.last_season(c) - EXTEND_YEARS_LEFT + 1, S + max(0, wait))
        return False, (f"He's signed through {C.last_season(c)}. Teams extend players with a year or two "
                       f"left; you can talk to him from {first}.")
    if wait > 0:
        return False, ("A drafted rookie's contract can't be redone until after his third season (league rule)."
                       if c["kind"] == "rookie" else
                       "An undrafted rookie's contract can't be redone until after his second season.")
    if c["kind"] == "tag" and getattr(league, "stage", "") != "offseason":
        return False, ("A tagged player can sign a long-term deal only until training camp opens. "
                       "He plays this season on the tag.")
    if c["signed"] == S and c["kind"] == "extension":
        return False, f"You already extended him in the {S} league year."
    if not _will_talk(league, pid, table or M.market_table(league)):
        return False, "He wants to test free agency: he won't talk about an extension this season."
    st = league.fa.get("patience", {})
    if st.get(f"ext-{pid}-{S}", 0) >= EXT_PATIENCE:
        return False, "He's done talking about an extension until next league year (too many low offers)."
    return True, ""


def extension_ask(league, pid, table=None):
    """What he wants to extend: {'apy' $K a year for the new years, 'years'
    (seasons from next season on), 'guaranteed' $K, 'gtd_share', 'min_years'
    (the least that makes it an extension: past his current deal)}. His price
    plus the re-signing premium (less if he's loyal), as if he were re-signing."""
    table = table or M.market_table(league)
    info = table[pid]
    p = league.player(pid)
    c = league.contracts[pid]
    S = league.season
    rng = random.Random(f"ext-ask-{_salt(league)}-{S}-{pid}")
    share = max(info["minimum"], info["price"] * (1 + RESIGN_PREMIUM * (1.5 - p.loyalty / 100)))
    min_years = max(1, C.last_season(c) - S + 1)
    years = max(min_years, 2, M.deal_years(share, _age(league, p) + 1, p.position, rng))
    gtd = M.guarantee_share(share, years, p.position, rng)
    apy = int(round(share * C.cap_for(league, S)))
    return {"apy": apy, "years": years, "guaranteed": int(round(gtd * apy * years)), "gtd_share": gtd,
            "min_years": min_years}


def extension_preview(league, pid, apy, years, guaranteed):
    """What an extension on these terms looks like: {'contract', 'hit_now',
    'hit_before', 'through'} (not signed)."""
    c = league.contracts[pid]
    ext, _new = _extension_contract(league, league.player(pid), c, apy / C.cap_for(league, league.season),
                                    random.Random(0), years=years, apy_k=apy, gtd=guaranteed)
    return {"contract": ext, "hit_now": C.cap_hit(league, ext), "hit_before": C.cap_hit(league, c),
            "through": C.last_season(ext)}


def extension_offer(league, pid, apy, years, guaranteed):
    """Your extension offer: ('accept' | 'counter' | 'reject', message).
    Offer / counter / patience as with re-signing (3 low offers and he stops
    talking until next league year). Accepted = signed now, if the new
    bonus's share this season fits under your cap."""
    ok, why = extension_check(league, pid)
    if not ok:
        return "reject", why
    S = league.season
    tid = league.user_team_id
    ask = extension_ask(league, pid)
    years = int(years)
    if years < ask["min_years"]:
        return "reject", (f"He's already signed through {C.last_season(league.contracts[pid])}: an extension "
                          f"has to run at least {ask['min_years']} season{'s' if ask['min_years'] != 1 else ''} "
                          f"from next season.")
    result, msg, _ask = respond(league, pid, tid, apy, years, guaranteed, patience_key=f"ext-{pid}-{S}",
                                ask=ask, patience=EXT_PATIENCE)
    if result != "accept":
        return result, msg
    c = league.contracts[pid]
    prev = extension_preview(league, pid, apy, years, guaranteed)
    more = prev["hit_now"] - prev["hit_before"]
    if more > 0 and C.cap_room(league, tid) < more:
        return "reject", (f"He'd sign, but it doesn't fit: the new signing bonus adds {C.fmt_money(more)} to "
                          f"your cap this season and you have {C.fmt_money(max(0, C.cap_room(league, tid)))} of room.")
    p = league.player(pid)
    ext = _extend(league, p, c, apy / C.cap_for(league, S), random.Random(0), years=years, apy_k=apy,
                  gtd=guaranteed)
    from .transactions import log
    note = (f"{years} more yr through {C.last_season(ext)}, {C.fmt_money(apy)} a year, "
            f"{C.fmt_money(int(guaranteed))} guaranteed")
    log(league, _when(league), tid, pid, "Extended", note)
    _drop_cap_requests(league, pid)
    return "accept", f"Extended: {note}."


def options_for_you(league, table=None):
    """Your first-rounders whose fifth-year option is due: from the start of the
    league year until the draft (the real deadline is early May, after the
    draft). [{pid, season, salary, starter, worth, advice}]."""
    tid = league.user_team_id
    if tid is None or getattr(league, "stage", "") != "offseason":
        return []
    S = league.season
    due = [c for c in league.contracts.values()
           if c["team"] == tid and c.get("option") and c["option"].get("exercised") is None
           and C.years_left(c, S) == 1 and on_team(league, c["pid"]) == tid]
    if not due:
        return []
    table = table or M.market_table(league)
    depth = depth_lists(league, table, exclude=set(league.fa.get("pending", [])))
    out = []
    for c in sorted(due, key=lambda c: -table[c["pid"]]["price"]):
        starter, salary, worth = _option_terms(league, c, table, depth)
        out.append({"pid": c["pid"], "season": c["option"]["season"], "salary": salary, "starter": starter,
                    "worth": int(round(worth)),
                    "advice": "Exercise" if worth >= OPTION_MIN_VALUE * salary else "Decline"})
    return out


def decide_option(league, pid, exercise):
    """Exercise or decline one of your fifth-year options. (done, message)."""
    r = {x["pid"]: x for x in options_for_you(league)}.get(pid)
    if r is None:
        return False, "His fifth-year option isn't up for a decision now."
    c = league.contracts[pid]
    from .transactions import log
    if exercise:
        C.option_contract(league, c, r["salary"])
        msg = (f"Option exercised: he's signed through {r['season']} at {C.fmt_money(r['salary'])} that season, "
               f"fully guaranteed.")
        log(league, _when(league), c["team"], pid, "Fifth-year option exercised",
            f"{r['season']}: {C.fmt_money(r['salary'])}")
    else:
        c["option"]["exercised"] = False
        msg = f"Option declined: he plays out his rookie deal in {league.season}, then can become a free agent."
        log(league, _when(league), c["team"], pid, "Fifth-year option declined")
    return True, msg


def lapse_your_options(league):
    """The option deadline has passed (the draft is over): options you didn't
    exercise are declined, as in the real NFL."""
    from .transactions import log
    tid = league.user_team_id
    for c in league.contracts.values():
        if (c["team"] == tid and c.get("option") and c["option"].get("exercised") is None
                and C.years_left(c, league.season) == 1):
            c["option"]["exercised"] = False
            log(league, "After the draft", tid, c["pid"], "Fifth-year option declined", "deadline passed")


def restructure_check(league, pid):
    """Can his contract be restructured now? (ok, reason in words)."""
    c = _yours(league, pid)
    if c is None:
        return False, "He isn't under contract with you."
    S = league.season
    if c["kind"] in ("rookie", "udfa"):
        return False, "Rookie contracts aren't restructured (they're mostly minimum salaries already)."
    if c["kind"] in ("practice", "minimum", "futures", "tag", "tender"):
        return False, "Only multi-year veteran deals can be restructured (there's no later year to spread money into)."
    if C.years_left(c, S) < 2:
        return False, "This is his last contract year: there's no later season to push money into."
    if C.restructure_room(league, c) <= 0:
        if C.pay_week(league) >= C.PAY_WEEKS:
            return False, "This season's salary has all been paid."
        return False, "His salary this season is already at the minimum."
    return True, ""


def your_restructure(league, pid, amount=None):
    """Restructure one of your players' contracts: `amount` ($K, default the
    most possible) of this season's salary becomes a bonus spread over the
    remaining years (at most 5). (done, message)."""
    ok, why = restructure_check(league, pid)
    if not ok:
        return False, why
    prev = C.restructure_preview(league, pid, amount)
    if prev["amount"] <= 0:
        return False, "Nothing to restructure."
    saved = C.restructure(league, pid, prev["amount"])
    from .transactions import log
    log(league, _when(league), league.user_team_id, pid, "Contract restructured",
        f"{C.fmt_money(prev['amount'])} of salary into bonus; {C.fmt_money(saved)} of cap room this season")
    _drop_cap_requests(league, pid)
    later = ", ".join(f"{s} +{C.fmt_money(v)}" for s, v in sorted(prev["added"].items()))
    return True, f"Restructured: {C.fmt_money(saved)} of cap room this season (later cap hits: {later})."


def release_choices(league, pid):
    """What cutting him would do, each way open to you now: {'plain': preview,
    'june1': preview or None (a post-June 1 designation, if you have one left
    and it's still spring), 'june1_left': n, 'after_june1': True once camp has
    opened (every cut splits its dead money then), 'best_june1': is the
    designation the better choice (contracts.best_release)}. Previews:
    contracts.release_preview ({'dead': {season: $K}, 'savings', 'hit'})."""
    c = league.contracts.get(pid)
    tid = league.user_team_id
    plain = C.release_preview(league, pid)
    left = C.june1_left(league, tid) if c is not None and getattr(league, "stage", "") == "offseason" else 0
    june = C.release_preview(league, pid, june1=True) if left and c is not None and c["kind"] != "practice" else None
    if june is not None and june["dead"] == plain["dead"]:
        june = None                     # no bonus money in later years: the designation changes nothing
    best = C.best_release(league, pid)[0] if june is not None else False
    return {"plain": plain, "june1": june, "june1_left": left, "after_june1": C.after_june1(league),
            "best_june1": best, "blocked": release_block(league, pid)}


def release_block(league, pid):
    """Why you can't cut him right now, in words ('' if you can)."""
    from . import season as SE
    opts = {a for a, _l, _t in SE.user_options(league, pid)}
    if "release" in opts:
        return ""
    if SE.season_over(league):
        return "The season is over: cuts wait for the offseason (Start the offseason)."
    if "ir" in opts:
        return "He's injured: place him on injured reserve instead (Roster tab)."
    return "You can't release him right now."


def your_release(league, pid, june1=False):
    """Cut one of your players from the Contracts tab (the Roster tab's Release,
    with the June 1 choice). (done, message)."""
    from . import season as SE
    tid = league.user_team_id
    why = release_block(league, pid)
    if why:
        return False, why
    c = league.contracts.get(pid)
    charged = {}
    if c is not None and c["team"] == tid:
        if june1 and not release_choices(league, pid)["june1"]:
            return False, "A post-June 1 designation isn't open for him now."
        charged = C.release(league, pid, june1=june1)
    done, msg = SE.user_move(league, "release", pid)
    if done:
        for tx in reversed(league.transactions):
            if tx["pid"] == pid:
                if june1:
                    tx["note"] = (tx["note"] + "; " if tx["note"] else "") + "post-June 1 designation"
                break
        _drop_cap_requests(league, pid)
        if charged:
            msg += " Dead money: " + ", ".join(f"{s} {C.fmt_money(v)}" for s, v in sorted(charged.items())) + "."
    return done, msg
