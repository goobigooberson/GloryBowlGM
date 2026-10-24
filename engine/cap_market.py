# cap_market.py
# What the market pays a player: his price as a share of the salary cap.
#
# How it works, in plain terms:
#   1. Teams judge a player by what he should give them over the next few
#      seasons, not just today: his rating projected forward (young players
#      grow toward their potential, veterans past their position's prime
#      decline), the next season counting most. (market_score)
#   2. Every player at a position is ranked on that projection against the
#      league's other veterans. Players still on rookie deals are left out of
#      the ranking (their pay is fixed by the rookie scale), which is how the
#      real pay ladder works too: the 5th-best-paid QB is the 5th-best veteran,
#      not the 5th-best QB.
#   3. His rank is read off the REAL pay ladder for his position: what the Nth
#      best-paid player there earns as a share of the cap (OverTheCap via
#      nflverse, every active contract in 2022; docs/research/real_contracts.json):
#      QB #1 24.1%, #10 17.0%, #32 2.6%; RB #10 3.4%; ...
#      So the market is never underpriced: a top-10 player at a position costs a
#      top-10 salary, whoever signs him.
#   4. Below the ladder's last rung the price slides to the veteran minimum.
# Each team then sees the price through its own eyes (need, money, scouting
# misjudgment) in free_agency.py; this module is the league's going rate.
#
# AI teams see true ratings for now (the staff-evaluation layer comes with
# scouting); they never see hidden ratings (durability, consistency,
# Generational), only what shows: ratings, age, and his injury record.

import bisect
import math
from collections import defaultdict
from datetime import date

from . import contracts as C
from . import development as D

# ---- The real pay ladders: Nth best-paid player (active contracts, 2022), share of the cap ----
LADDER = {
    "QB":   {1: .241, 3: .227, 5: .219, 10: .170, 16: .067, 24: .043, 32: .026, 48: .010, 64: .006, 96: .004},
    "RB":   {1: .081, 3: .076, 5: .066, 10: .034, 16: .029, 24: .016, 32: .012, 48: .007, 64: .006, 96: .005},
    "FB":   {1: .030, 3: .016, 5: .015, 10: .007, 16: .004},
    "WR":   {1: .144, 3: .134, 5: .115, 10: .099, 16: .086, 24: .063, 32: .048, 48: .019, 64: .015, 96: .008},
    "TE":   {1: .078, 3: .076, 5: .068, 10: .053, 16: .039, 24: .027, 32: .017, 48: .007, 64: .006, 96: .005},
    "T":    {1: .126, 3: .111, 5: .101, 10: .093, 16: .085, 24: .064, 32: .034, 48: .017, 64: .012, 96: .006},
    "G":    {1: .088, 3: .079, 5: .078, 10: .051, 16: .041, 24: .026, 32: .020, 48: .011, 64: .007, 96: .005},
    "C":    {1: .074, 3: .067, 5: .062, 10: .034, 16: .024, 24: .012, 32: .007, 48: .005, 64: .004},
    "EDGE": {1: .153, 3: .133, 5: .113, 10: .088, 16: .081, 24: .070, 32: .048, 48: .027, 64: .016, 96: .008},
    "DT":   {1: .127, 3: .106, 5: .099, 10: .077, 16: .052, 24: .043, 32: .034, 48: .022, 64: .015, 96: .006},
    "LB":   {1: .108, 3: .090, 5: .072, 10: .056, 16: .038, 24: .020, 32: .017, 48: .012, 64: .008, 96: .006},
    "CB":   {1: .106, 3: .101, 5: .097, 10: .079, 16: .065, 24: .044, 32: .035, 48: .019, 64: .014, 96: .007},
    "S":    {1: .096, 3: .084, 5: .074, 10: .062, 16: .048, 24: .026, 32: .019, 48: .011, 64: .009, 96: .005},
    "K":    {1: .027, 3: .024, 5: .024, 10: .022, 16: .018, 24: .010, 32: .004},
    "P":    {1: .020, 3: .016, 5: .015, 10: .012, 16: .006, 24: .005, 32: .004},
    "LS":   {1: .008, 3: .006, 5: .006, 10: .006, 16: .006, 24: .005, 32: .004},
}
# Game position -> (real ladder, rank multiplier). This game's linebackers are
# off-ball linebackers (the real "LB" market; edge rushers are its DEs). The game
# carries 4 OLB and 3 ILB, with 2 and 1 starters: OLBs take about 2/3 of the
# linebacker ladder and ILBs 1/3, so the best ILB is priced like the 3rd-best LB.
LADDER_OF = {"QB": ("QB", 1.0), "RB": ("RB", 1.0), "FB": ("FB", 1.0), "WR": ("WR", 1.0), "TE": ("TE", 1.0),
             "T": ("T", 1.0), "G": ("G", 1.0), "C": ("C", 1.0), "DE": ("EDGE", 1.0), "DT": ("DT", 1.0),
             "OLB": ("LB", 1.5), "ILB": ("LB", 3.0), "CB": ("CB", 1.0), "S": ("S", 1.0),
             "K": ("K", 1.0), "P": ("P", 1.0), "LS": ("LS", 1.0)}
MINIMUM_LINE = 0.0065          # deals at or under this share of the cap are "minimum-level" (research's line)
MARKET_LINE = 0.01             # 1%+ of the cap: a "market" deal (research's line)
# ---- Projection: how teams weigh the coming seasons ----
SCORE_WEIGHTS = (0.5, 0.3, 0.2)   # next season, the one after, the third
POTENTIAL_SEEN = 1.0           # share of a young player's growth teams count on (they see true potential for now)
# Injuries: a player who'll miss games next season, or who has missed a lot lately, costs less.
INJURY_OUT_DISCOUNT = 0.03     # per game he's expected to miss next season (up to 17)
INJURY_HISTORY_DISCOUNT = 0.006  # per game missed over the last two seasons...
INJURY_HISTORY_MAX = 0.15      # ...at most this much
# -----------------------------------------------------------------------------------


def age_on(p, season):
    return p.age(date(season, 9, 1))


def project(p, season, n=3, cur=None, pot=None):
    """His expected overall rating for each of the next n seasons, starting
    with the coming one (its training camp comes first). Uses the position's
    normal growth and prime (development.py's tables), not his hidden
    personal aging profile. cur / pot: his overall now and ceiling as someone
    sees them (default: his own)."""
    cur = float(p.overall()) if cur is None else float(cur)
    pot = float(p.overall("potential")) if pot is None else float(pot)
    _start, end = D.PEAK_SEASONS.get(p.position, (3, 10))
    season_no = p.experience + 1          # the pro season he's about to play
    age = age_on(p, season)
    out = []
    for t in range(n):
        share = D.GROWTH_SHARE.get(age + t, D.GROWTH_SHARE_OLD if age + t > 27 else 0.46)
        if pot > cur:
            cur += share * (pot - cur) * POTENTIAL_SEEN
        past = season_no + t - end
        if past > 0:
            loss = (D.DECLINE_BASE + D.DECLINE_GROWTH * (past - 1)) * D.DECLINE_SCALE.get(p.position, 1.0)
            pot -= loss
            cur -= loss
        out.append(cur)
    return out


def market_score(p, season, cur=None, pot=None):
    """How teams rate him for a new contract: projected overall over the next
    three seasons, the next one counting most (cur / pot: see project)."""
    proj = project(p, season, len(SCORE_WEIGHTS), cur, pot)
    return sum(w * v for w, v in zip(SCORE_WEIGHTS, proj))


def ladder_price(ladder, rank):
    """The real ladder's share at a (possibly fractional) rank: log-linear
    between the measured rungs; past the last rung it keeps falling at the
    last rungs' rate (the caller floors it at the minimum)."""
    pts = sorted(LADDER[ladder].items())
    if rank <= pts[0][0]:
        return pts[0][1]
    for (r0, v0), (r1, v1) in zip(pts, pts[1:]):
        if rank <= r1:
            t = (math.log(rank) - math.log(r0)) / (math.log(r1) - math.log(r0))
            return math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0)))
    (r0, v0), (r1, v1) = pts[-2], pts[-1]
    slope = (math.log(v1) - math.log(v0)) / (math.log(r1) - math.log(r0))
    return math.exp(math.log(v1) + slope * (math.log(rank) - math.log(r1)))


def on_rookie_deal(league, p):
    """Still on his rookie (or undrafted rookie) contract, before its last year."""
    c = getattr(league, "contracts", {}).get(p.id)
    if c is not None:
        return c["kind"] in ("rookie", "udfa")
    # Before contracts exist (a brand-new league): by experience.
    return (p.draft_round > 0 and p.experience < C.ROOKIE_YEARS) or (p.draft_round == 0 and p.experience < C.UDFA_YEARS)


def active_players(league):
    """Everyone who could be priced: players on a team in any form, and free agents
    (not this year's draft prospects before the draft: draft_day.py)."""
    pool = set((getattr(league, "draft", None) or {}).get("pool", ()))
    return [p for p in league.players if p.retired is None and (p.id not in pool or p.id in league.rosters)]


def rookie_pay(league, p):
    """A rookie-deal player's pay, as a share of the cap when he signed."""
    c = getattr(league, "contracts", {}).get(p.id)
    if c is not None:
        return c["apy"] / C.cap_for(league, c["signed"])
    if p.draft_round > 0:
        return C.rookie_apy_share(p.draft_round * 32 - 16)
    return 0.0


def market_table(league, season=None, players=None):
    """{player id: {'score', 'rank', 'price'}} for every active player: his
    market score, his rank on the real pay ladder and his price as a share
    of the cap. The real ladder counts every contract, rookie deals too, so a
    veteran's rank is his place among veterans plus the rookie deals that pay
    more than that rung (first-rounders' deals sit in the middle of most
    ladders). Rookie-deal players get a price too (what they'd earn as
    veterans: extension talks), but don't push veterans down."""
    season = league.season if season is None else season
    players = active_players(league) if players is None else players
    by_pos = defaultdict(list)
    for p in players:
        by_pos[p.position].append(p)
    out = {}
    hist = defaultdict(int)
    for h in getattr(league, "injury_history", []):
        if h.get("season", 0) >= season - 2 and isinstance(h.get("weeks"), int):
            hist[h.get("pid")] += min(17, h["weeks"])
    for position, group in by_pos.items():
        ladder, mult = LADDER_OF[position]
        scored = [(market_score(p, season), p) for p in group]
        vets = sorted((s for s, p in scored if not on_rookie_deal(league, p)), reverse=True)
        neg = [-s for s in vets]
        rookie_neg = sorted(-rookie_pay(league, p) for s, p in scored if on_rookie_deal(league, p))
        cache = {}
        for s, p in scored:
            better = bisect.bisect_left(neg, -s)      # veterans strictly better than him
            if better not in cache:
                r = better + 1
                for _ in range(4):
                    paid_more = bisect.bisect_right(rookie_neg, -ladder_price(ladder, r * mult))
                    r = better + 1 + paid_more
                cache[better] = r * mult
            rank = cache[better]
            out[p.id] = {"score": s, "rank": rank, "price": ladder_price(ladder, rank), "position": position}
    # injury worries, and the floor at his minimum salary
    cap = C.cap_for(league, season)
    for p in players:
        d = out[p.id]
        f = 1.0
        inj = getattr(league, "injuries", {}).get(p.id)
        if inj and inj.get("weeks", 0) > 0:
            f -= INJURY_OUT_DISCOUNT * min(17, inj["weeks"])
        f -= min(INJURY_HISTORY_MAX, INJURY_HISTORY_DISCOUNT * hist.get(p.id, 0))
        floor = C.min_salary(league, p.experience, season) / cap
        d["minimum"] = floor
        d["price"] = max(floor, d["price"] * max(0.3, f))
    # Leftover free agents' summer asks (free_agency.summer_asks), for free_agency.ask_share.
    for pid, share in ((getattr(league, "fa", None) or {}).get("summer_ask") or {}).items():
        pid = int(pid)                    # (a saved league brings the ids back as text)
        if pid in out:
            out[pid]["summer_ask"] = share
    return out


def price_k(league, pid, table, season=None):
    """His market price in $K a year."""
    season = league.season if season is None else season
    return int(round(table[pid]["price"] * C.cap_for(league, season)))


# ---------------------------------------------------------------------------
# The shape of a deal: years, guarantees
# ---------------------------------------------------------------------------
# Real veteran deals 2017-22 (docs/research/real_contracts.json):
#   - minimum-level deals (<= 0.65% of the cap): ~88% one year, the rest mostly two
#   - market deals (1%+): average 2.0-2.3 years, 3-5 for the top of the market,
#     shorter with age (32+: 1.3-1.8); QBs and kickers sign longer at the top
#   - guaranteed share: ~0 on minimum deals, ~25-40% at 1-2% of the cap, ~50% at
#     2-5%, ~60% at 5%+, QBs ~10 points higher
# Contract length by price (share of the cap): odds of 1..6 years. Real 2017-22: market deals
# (1%+) run 1y 42%, 2y 23%, 3y 19%, 4y 10%, 5y 5%; big deals (5%+) 3-4 years mostly (1-year
# big deals are almost all franchise tags, made separately); minimum deals ~88% one year.
YEARS_BY_PRICE = [
    (0.05, {1: 0.04, 2: 0.14, 3: 0.34, 4: 0.33, 5: 0.14, 6: 0.01}),
    (0.02, {1: 0.36, 2: 0.27, 3: 0.22, 4: 0.10, 5: 0.05}),
    (0.01, {1: 0.62, 2: 0.24, 3: 0.10, 4: 0.03, 5: 0.01}),
    (MINIMUM_LINE, {1: 0.76, 2: 0.20, 3: 0.04}),
    (0.0, {1: 0.89, 2: 0.10, 3: 0.01}),
]
# Older players sign shorter: each extra year's odds x this, by age (up to). Real market deals
# average 2.0-2.8 years at 27 and under, 1.3-1.8 at 32+.
YEARS_AGE_DECAY = ((25, 1.15), (27, 1.08), (29, 1.0), (31, 0.70), (33, 0.42), (99, 0.22))
YEARS_SPECIALIST = 2.0         # kickers/punters/snappers 33 and under sign longer (real top-10% K 3.3, P 3.6 years)
GTD_AT_MARKET_LINE = 0.28       # guaranteed share of a deal at 1% of the cap...
GTD_PER_TENFOLD = 0.32          # ...plus this per tenfold rise in price
GTD_QB = 0.10                   # QBs get more guaranteed


def deal_years(price, age, position, rng):
    """How many years a new veteran deal runs."""
    odds = next(o for line, o in YEARS_BY_PRICE if price >= line)
    decay = next(d for limit, d in YEARS_AGE_DECAY if age <= limit)
    if position in ("K", "P", "LS") and age <= 33 and price >= MINIMUM_LINE:
        decay *= YEARS_SPECIALIST
    weights = {n: w * decay ** (n - 1) for n, w in odds.items()}
    r = rng.random() * sum(weights.values())
    for n in sorted(weights):
        r -= weights[n]
        if r <= 0:
            return n
    return max(weights)


def guarantee_share(price, years, position, rng):
    """Share of the total value that's guaranteed."""
    if price < MINIMUM_LINE:
        return 0.0
    g = GTD_AT_MARKET_LINE + GTD_PER_TENFOLD * math.log10(max(price, MINIMUM_LINE) / MARKET_LINE)
    if position == "QB":
        g += GTD_QB
    if years == 1:
        g += 0.10                     # one-year deals: most of it up front
    g += rng.gauss(0, 0.08)
    return max(0.0, min(0.95, g))
