# finances.py
# The business side of every team (Blake, Oct 26): ticket prices, attendance, the
# stadium, and the owner's profit and loss. FOF8 had it; this game's version, with
# Blake's calls (all PROVISIONAL until he plays it, docs/build-log.md):
#   - you set two prices a year (regular seats and premium club seats; suites follow
#     the club price), with your staff's recommended price and attendance as feedback;
#     concessions, parking, sponsors and local media run on their own;
#   - every team has a stadium (capacity, club seats, suites, age); a new one earns
#     more and the edge fades; building and renovating are the next step, not here;
#   - the owner judges you mostly on winning; money counts only at the edges
#     (owner_money_factor), and profits slowly move his staff budget;
#   - all 32 teams run real books and price their own tickets, shown on the League
#     finances page.
#
# Rules only (screens read from here). League money stays in league_money.py: the
# national revenue every team gets is a fixed share of the cap, so a TV boom lifts
# every team's books with the cap; team revenue sits beside it and the cap is still
# set league-wide.
#
# Real data behind the knobs (docs/research/finance_research.py -> real_finance.json):
#   revenue by source (Sportico, 2025 season): an average team $734M at a $279.2M cap
#   (2.63 x the cap): national 62%, tickets and suites 19% (incl. ~$29M visiting share),
#   team sponsors 11%, concessions/parking/stores/stadium events 7%, local media 2%;
#   profit (EBITDA) $127M a team. Forbes 2024 (all 32): revenue $552M-$1.23B, mean
#   $662M; local revenue (revenue minus the $433M national share) barely follows market
#   size (R^2 0.04) but a stadium in its first 5 years adds ~$80M and each franchise's
#   own pull (Patriots, Packers vs Chargers, Cardinals) spreads it ~$57M either way.
#   Ticket prices (Team Marketing Report 2023): mean $122.50, spread $16.70 ($99-$169),
#   yearly change +7% on average (0% to +20%; none cut). Attendance (ESPN 2008-2025):
#   about 69,000 a game; a team's crowd changes ~1% a year (median) and follows winning
#   only a little (this season's win% +0.02-0.03, last season's +0.015-0.04 of the
#   crowd per 1.0 of win%), because real teams sell out and winning shows in prices.
#   New stadiums: no lasting rise in the crowd itself (they sell out either way), the
#   gain is in prices, premium seats and sponsors. Playoff games: the league keeps the
#   tickets; the home team keeps ~$1-2M of concessions and parking.
#
# Saved on the league as league.finances (database MONEY_INFO key "finances"):
#   {"teams": {tid: {"market", "income", "brand", "opex", "budget_mult", "stadium": {...}}},
#    "prices": {season: {tid: {"general", "club", "set_by"}}},
#    "games": {season: {gid: {"home", "att", "club", "general_cap", "club_cap", "gate",
#                              "club_gate", "conc", "kind"}}},
#    "books": {season: {tid: {line: $K, ...}}}   (closed seasons)}

import math
import random
import statistics

# ---- Markets (the game's teams play in real cities) -----------------------------
# TV households (millions; Nielsen 2024-25 estimates). One team per city here, so New
# York's and Los Angeles's teams have their whole market to themselves.
TV_HOMES = {
    "New York": 7.49, "Los Angeles": 5.84, "Chicago": 3.65, "Dallas": 3.26, "Philadelphia": 3.15,
    "Houston": 2.80, "Atlanta": 2.76, "Washington": 2.63, "Boston": 2.58, "San Francisco": 2.54,
    "Phoenix": 2.21, "Seattle": 2.10, "Tampa": 2.10, "Detroit": 1.90, "Minneapolis": 1.86,
    "Denver": 1.83, "Miami": 1.73, "Charlotte": 1.48, "Portland": 1.30, "Cleveland": 1.47,
    "St. Louis": 1.23, "Indianapolis": 1.18, "Nashville": 1.20, "Baltimore": 1.15, "San Diego": 1.12,
    "Pittsburgh": 1.13, "San Antonio": 1.04, "Kansas City": 1.03, "Cincinnati": 0.93,
    "Las Vegas": 0.84, "New Orleans": 0.63, "Buffalo": 0.64}
# Median household income by metro ($K; Census ACS 2023, rounded; approximate).
INCOME = {
    "New York": 98, "Los Angeles": 98, "Chicago": 90, "Dallas": 87, "Philadelphia": 90, "Houston": 81,
    "Atlanta": 87, "Washington": 123, "Boston": 112, "San Francisco": 136, "Phoenix": 84, "Seattle": 111,
    "Tampa": 74, "Detroit": 75, "Minneapolis": 96, "Denver": 102, "Miami": 77, "Charlotte": 80,
    "Portland": 95, "Cleveland": 69, "St. Louis": 78, "Indianapolis": 78, "Nashville": 84, "Baltimore": 96,
    "San Diego": 103, "Pittsburgh": 75, "San Antonio": 74, "Kansas City": 82, "Cincinnati": 80,
    "Las Vegas": 76, "New Orleans": 64, "Buffalo": 70}
MARKET_MID = 1.5                # TV households (M) of a middle market
INCOME_MID = 85                 # $K

# ---- Stadiums ---------------------------------------------------------------------
# The real 32 (year opened or last rebuilt, capacity; Wikipedia, 2025-26), dealt out at
# random to the game's teams so the league has the real mix of new and old.
REAL_STADIUMS = [
    (2006, 63400), (2017, 71000), (1998, 71008), (2026, 62000), (1996, 74867), (2003, 61500),
    (2000, 65515), (1999, 67431), (2009, 80000), (2001, 76125), (2002, 65000), (2003, 81441),
    (2002, 72220), (2008, 67000), (1995, 67814), (2010, 76416), (2020, 65000), (2020, 70240),
    (2016, 65326), (2016, 66655), (2002, 65878), (2011, 73208), (2010, 82500), (2003, 69796),
    (2001, 68400), (2014, 68500), (2002, 68740), (1998, 65618), (1999, 69143), (1997, 62000),
    (2020, 70240), (2010, 82500)]
CLUB_SHARE = (0.11, 0.02)       # club seats as a share of capacity (real ~6,000-13,000; newer = more)
SUITES = (140, 35)              # luxury suites (real ~60-340; Dallas over 300)
SUITE_SEATS = 18                # seats in a suite (FOF8: ~25 people a box; real 12-24)
# Invented naming-rights sponsors (older stadiums usually have a plain name).
SPONSORS = ["Keystone Mutual", "Orion Bank", "Summit Health", "Pioneer Energy", "Atlas Freight",
            "Northstar Wireless", "Beacon Insurance", "Granite Financial", "Liberty Air", "Cardinal Foods",
            "Vista Motors", "Harbor Trust", "Evergreen Credit", "Meridian Tech", "Ridgeline Bank",
            "Frontier Mobile", "Crescent Health", "Ironwood Capital", "Lakeshore Mutual", "Bluewater Energy"]
PLAIN = ["{city} Memorial Stadium", "{nick} Stadium", "{city} Field", "Municipal Stadium"]
NAMING_FROM = 1997              # stadiums opened since this year carry a sponsor's name

# ---- Prices and demand ------------------------------------------------------------
# All money in $K and prices in $ at the 2026 cap; everything grows with the cap
# (real: the average ticket rose 33% 2019-24 while the cap rose 36%).
TICKET_2026 = 158.0             # average regular seat a game (TMR 2024 $136.38 x 301.2/255.4 = $161)
CLUB_MULT = 3.0                 # a club seat costs ~3x a regular seat (TMR premium avg ~$370 vs $122)
SUITE_MULT = 1.3                # a suite seat over a season costs this much more than a club seat
# The price a team could charge and still just sell out ("sellout price") is the
# middle price x these effects (log units). Real prices spread 14% around the
# average (TMR 2023), from the franchise's pull, local incomes, a new stadium, and
# recent winning.
BRAND_W = 0.06                  # per spread of the franchise's own pull
INCOME_W = 0.30                 # per log of local income vs the middle (richer cities pay more)
MARKET_W = 0.03                 # per log of market size (bigger cities, a bit more)
NEW_W = (0.15, 7.0)             # a new stadium: this much more, fading with this time constant (years)
STAR_W = 0.03                   # per 10 points of the team's three most popular players above the middle
# Winning (judgment, checked against real price changes, +7% a year, 0% to +20%, and
# the small real effect on crowds): last three seasons' win% (minus .500), playoffs
# and a title last season.
HYPE_LAGS = (0.15, 0.07, 0.03)
HYPE_PLAYOFFS = 0.025
HYPE_TITLE = 0.03
PRICE_K = 1.5                   # demand falls this fast above the sellout price: 10% over sells ~86%
                                # (k > 1, so pricing past the sellout point always loses money)
SEASON_NOISE = 0.025            # how far a season's true demand lands from what teams can foresee
GAME_NOISE = 0.02               # game-to-game luck in single-game sales
# In-season (each home game): the record so far (from the 4th game on) and the
# opponent's draw. Real: this season's win% moves the crowd ~+0.02-0.03 per 1.0.
FORM_K = 0.10
RIVAL_K = 0.02                  # division games draw a little more
OPP_BRAND_K = 0.015             # so do teams with big followings
COLD_LOSER = 0.03               # December cold and a losing team: more empty seats outdoors
PRESEASON_DEMAND = 0.90         # preseason games (in the season-ticket package at full price)
CLUB_CORP_K = 0.10              # club seats and suites follow the local business base (market size)
CLUB_BRAND_K = 0.10             # and the franchise's pull
# How teams set prices (each league year): the staff's guess of the sellout price
# (off by about this much), the owner's habit (a bit under the sellout point keeps
# fans happy and full; some owners squeeze), and real stickiness: teams almost never
# cut prices (TMR 2023: 0 of 29 did) and rarely raise more than ~20%.
ESTIMATE_SD = 0.03
OWNER_PRICE = (0.985, 0.04)
PRICE_STEP = (-0.03, 0.20)

# ---- Revenue (shares of the cap; Sportico 2025 an average team / $279.2M cap) -------
NATIONAL_PER_CAP = 1.62         # national revenue each team gets ($453M / $279.2M)
VTS_SHARE = 0.30                # share of regular seats' and club seats' face value that goes to the
                                # league pool for visiting teams, split 32 ways (real rule: 34% of the
                                # gate less allowances; 0.30 gives Sportico's ~$29M a team)
SPONSOR_PER_CAP = 0.29          # team sponsorship ($81M), spread by:
SPONSOR_BRAND, SPONSOR_MARKET, SPONSOR_NEW, SPONSOR_HYPE = 0.65, 0.10, 0.80, 0.8
MEDIA_PER_CAP = 0.053           # local radio and preseason TV ($15M)
PER_FAN_2026 = 52.0             # concessions and parking a fan, the team's net share ($)
STORE_PER_FAN_2026 = 9.0        # team store ($)
EVENTS_PER_CAP = (0.05, 0.4)    # non-NFL stadium events (concerts, college games): average, spread
PLAYOFF_GAME_PER_CAP = 0.005    # a home playoff game: concessions and parking only (~$1.5M)
# ---- Expenses -------------------------------------------------------------------
BENEFITS_PER_CAP = 0.265        # player benefits ($74M / $279.2M; Sportico)
OPEX_FIXED = 0.30               # running the team and stadium, fixed part (x cap), times the team's
OPEX_SD = 0.10                  #   own cost level (stadium leases vary a lot)
OPEX_VAR = 0.46                 # and this share of local revenue (game-day costs, rent shares, sales
                                # costs: real profit rises ~$0.54 per $1 of revenue, Forbes 2024)
DEAD_CASH = 0.3                 # share of dead money that is cash still owed (the rest was paid up front)
# ---- Franchise value ------------------------------------------------------------
VALUE_MULT = 10.7               # Forbes 2025: average value $7.1B on $662M revenue
VALUE_MARKET = 0.08             # a bigger market sells for a bit more per dollar of revenue (log)
# ---- The owner ------------------------------------------------------------------
BUDGET_DRIFT = 0.15             # each season his staff budget moves this share of the way toward
BUDGET_PROFIT_K = 0.06          #   his own level x exp(this x profit vs expected, in spreads)
BUDGET_MULT = (0.85, 1.15)      #   never more than this far from his own level
MONEY_HEAT = (0.20, 0.10)       # owner can fire you: chance x (1 + this x bad money, - this x good money)
PROFIT_SPREAD = 0.20            # a spread of profit (x cap; Forbes 2024 without Dallas: $52M / $255M)

LINES_REVENUE = [("national", "National revenue (TV, league deals)"),
                 ("gate", "Tickets: regular seats"), ("club", "Tickets: club seats"), ("suites", "Luxury suites"),
                 ("vts_in", "Visiting teams' share (league pool)"), ("vts_out", "Visiting teams' share (paid in)"),
                 ("sponsors", "Sponsors and naming rights"), ("concessions", "Concessions and parking"),
                 ("store", "Team store"), ("events", "Other stadium events"), ("media", "Local radio and TV"),
                 ("playoffs", "Playoff games (concessions)")]
LINES_EXPENSE = [("players", "Player pay (cash this season)"), ("benefits", "Player benefits"),
                 ("staff", "Coaches and scouts"), ("operations", "Team and stadium operations")]


def _salt(league):
    return league.settings.get("salt", "")


def _rng(league, *parts):
    return random.Random("fin-" + "-".join(str(x) for x in (_salt(league),) + parts))


def cap_k(league, season=None):
    from . import contracts as C
    if getattr(league, "contracts", None) is None:
        return 301_200
    return C.cap_for(league, league.season if season is None else season)


def ratio(league, season=None):
    """Prices and money grow with the cap."""
    return cap_k(league, season) / 301_200


# ---------------------------------------------------------------------------
# Setting up: markets, franchises, stadiums (new leagues and older saves)
# ---------------------------------------------------------------------------

def ensure(league):
    """league.finances, made for a new league or an older save (the same save always
    gets the same markets and stadiums: seeded by its salt). Fills in this season's
    prices and any games already played. Returns it."""
    fin = getattr(league, "finances", None) or {}
    league.finances = fin
    for key in ("teams", "prices", "games", "books", "bonus"):
        fin.setdefault(key, {})
    if not fin["teams"]:
        _new_teams(league)
        if league.season not in fin["bonus"]:
            _backfill_bonuses(league)
    if league.season not in fin["prices"]:
        set_prices(league)
    games = fin["games"].setdefault(league.season, {})
    for g in _season_games(league):
        if g.get("played") and g["id"] not in games:
            game_played(league, g)
    return fin


def _backfill_bonuses(league):
    """A save from before team finances: this league year's signing bonuses already paid,
    from its signings (contract_log) whose deals are still on the books."""
    S = league.season
    led = league.finances["bonus"].setdefault(S, {})
    seen = set()
    for e in getattr(league, "contract_log", ()):
        c = (getattr(league, "contracts", None) or {}).get(e.get("pid"))
        if e.get("season") != S or not c or e["pid"] in seen or c.get("signed") != S or c["team"] != e["team"]:
            continue
        seen.add(e["pid"])
        led[c["team"]] = led.get(c["team"], 0) + c.get("signing_bonus", 0)


def note_bonus(league, tid, amount):
    """A signing bonus just paid (contracts.sign): cash out this league year."""
    fin = getattr(league, "finances", None)
    if fin is None:
        fin = league.finances = {}
    led = fin.setdefault("bonus", {}).setdefault(league.season, {})
    led[tid] = led.get(tid, 0) + int(amount)


def _fin(league):
    """league.finances, set up if it isn't yet (helpers use this; ensure() also fills in
    prices and games already played)."""
    fin = getattr(league, "finances", None)
    return fin if fin and fin.get("teams") else ensure(league)


def _new_teams(league):
    fin = league.finances
    rng = _rng(league, "teams")
    pool = list(REAL_STADIUMS)
    rng.shuffle(pool)
    sponsors = list(SPONSORS)
    rng.shuffle(sponsors)
    from .sim.weather import STADIUMS
    first = league.settings.get("first_season", league.season)
    for i, t in enumerate(league.teams):
        opened, capacity = pool[i % len(pool)]
        opened = min(opened, first)
        newness = math.exp(-(first - opened) / 10)
        club = int(round(capacity * max(0.05, rng.gauss(CLUB_SHARE[0], CLUB_SHARE[1]) + 0.02 * (newness - 0.5)) / 50) * 50)
        suites = max(60, int(round(rng.gauss(SUITES[0], SUITES[1]))))
        if opened >= NAMING_FROM:
            name = f"{sponsors[i % len(sponsors)]} {rng.choice(['Field', 'Stadium', 'Stadium', 'Park'])}"
        else:
            name = rng.choice(PLAIN).format(city=t.city, nick=t.nickname)
        fin["teams"][t.id] = {
            "market": TV_HOMES.get(t.city, 1.2), "income": INCOME.get(t.city, INCOME_MID),
            # The franchise's own pull: history, tradition, brand (real local revenue spreads
            # ~$57M after market and stadium; a few franchises far above the rest).
            "brand": round(rng.gauss(0, 1), 3),
            "opex": round(max(0.7, rng.gauss(1.0, OPEX_SD)), 3),
            "owner_price": round(rng.gauss(*OWNER_PRICE), 3),
            "events": round(rng.lognormvariate(0, EVENTS_PER_CAP[1]), 3),
            "stadium": {"name": name, "opened": opened, "capacity": capacity, "club": club, "suites": suites,
                        "roof": STADIUMS.get(t.abbrev, ("outdoor", {}))[0]},
        }


def team(league, tid):
    return _fin(league)["teams"][tid]


def stadium(league, tid):
    return team(league, tid)["stadium"]


def stadium_age(league, tid, season=None):
    season = league.season if season is None else season
    return max(0, season - stadium(league, tid)["opened"])


def _newness(league, tid, season=None):
    return math.exp(-stadium_age(league, tid, season) / NEW_W[1])


def seats(league, tid):
    """{'general', 'club', 'suite'} seats for a game."""
    st = stadium(league, tid)
    suite = st["suites"] * SUITE_SEATS
    return {"general": st["capacity"] - st["club"] - suite, "club": st["club"], "suite": suite}


# ---------------------------------------------------------------------------
# Demand: what fans will pay
# ---------------------------------------------------------------------------

def _wins_pct(r):
    g = r["w"] + r["l"] + r["t"]
    return (r["w"] + 0.5 * r["t"]) / g if g else 0.5


def hype(league, tid, season=None):
    """How the last three seasons lift (or sink) demand, in log units."""
    season = league.season if season is None else season
    past = {r["season"]: r for r in league.team_history if r["team"] == tid}
    h = 0.0
    for k, w in enumerate(HYPE_LAGS, start=1):
        r = past.get(season - k)
        if r:
            h += w * (_wins_pct(r) - 0.5)
    last = past.get(season - 1)
    if last and last.get("seed"):
        h += HYPE_PLAYOFFS
    if getattr(league, "champions", {}).get(season - 1) == tid:
        h += HYPE_TITLE
    return h


def star_power(league, tid):
    """The team's three most popular players, above the middle (in tens of points)."""
    pops = sorted((p.popularity for p in league.team_players(tid)), reverse=True)[:3]
    return (statistics.mean(pops) - 50) / 10 if pops else 0.0


def _foreseen(league, tid, season):
    """Log of the sellout price over the middle price: everything a team can foresee."""
    t = team(league, tid)
    return (BRAND_W * t["brand"] + INCOME_W * math.log(t["income"] / INCOME_MID)
            + MARKET_W * math.log(t["market"] / MARKET_MID) + NEW_W[0] * _newness(league, tid, season)
            + hype(league, tid, season) + STAR_W * star_power(league, tid))


def sellout_price(league, tid, season=None):
    """The true regular-seat price at which this season's games would just sell out ($)."""
    season = league.season if season is None else season
    luck = _rng(league, "demand", season, tid).gauss(0, SEASON_NOISE)
    return TICKET_2026 * ratio(league, season) * math.exp(_foreseen(league, tid, season) + luck)


def estimated_sellout(league, tid, season=None):
    """Your staff's (or an AI team's) estimate of the sellout price ($)."""
    season = league.season if season is None else season
    miss = _rng(league, "estimate", season, tid).gauss(0, ESTIMATE_SD)
    luck = _rng(league, "demand", season, tid).gauss(0, SEASON_NOISE)
    return sellout_price(league, tid, season) * math.exp(miss - luck)


def _corporate(league, tid, season):
    t = team(league, tid)
    return math.exp(CLUB_CORP_K * math.log(t["market"] / MARKET_MID) + CLUB_BRAND_K * t["brand"]
                    + 0.5 * NEW_W[0] * _newness(league, tid, season))


def demand_share(price, sellout):
    """Share of the seats that sell at this price (1.0 = sold out)."""
    if price <= sellout:
        return 1.0
    return math.exp(-PRICE_K * (price / sellout - 1))


# ---------------------------------------------------------------------------
# Ticket prices
# ---------------------------------------------------------------------------

def prices(league, tid, season=None):
    season = league.season if season is None else season
    p = _fin(league)["prices"].get(season, {}).get(tid)
    return p


def recommended(league, tid, season=None):
    """Your staff's recommendation: just under their guess of the sellout price, never
    more than a 20% raise or a 3% cut from last season ($ regular, $ club)."""
    season = league.season if season is None else season
    est = estimated_sellout(league, tid, season)
    general = est * 0.98
    last = _fin(league)["prices"].get(season - 1, {}).get(tid)
    if last:
        growth = ratio(league, season) / ratio(league, season - 1)
        lo, hi = last["general"] * (1 + PRICE_STEP[0]), last["general"] * growth * (1 + PRICE_STEP[1])
        general = max(lo, min(hi, general))
    club = general * CLUB_MULT * _corporate(league, tid, season)
    return round(general), round(club)


def _ai_price(league, tid, season):
    t = team(league, tid)
    est = estimated_sellout(league, tid, season)
    general = est * t["owner_price"]
    last = _fin(league)["prices"].get(season - 1, {}).get(tid)
    if last:
        lo = last["general"] * (1 + PRICE_STEP[0])
        hi = last["general"] * (1 + PRICE_STEP[1])
        # Real teams hold prices rather than cut them: a cut only when well over the mark.
        if general < last["general"] and general > last["general"] * 0.88:
            general = last["general"]
        general = max(lo, min(hi, general))
    club = general * CLUB_MULT * _corporate(league, tid, season)
    return round(general), round(club)


def set_prices(league, season=None):
    """Every team's prices for the season (AI teams by their owners' habits; yours at
    your staff's recommendation until you change them). Prices already set stay."""
    fin = league.finances
    season = league.season if season is None else season
    table = fin["prices"].setdefault(season, {})
    for t in league.teams:
        if t.id in table:
            continue
        if t.id == league.user_team_id:
            g, c = recommended(league, t.id, season)
            table[t.id] = {"general": g, "club": c, "set_by": "staff"}
        else:
            g, c = _ai_price(league, t.id, season)
            table[t.id] = {"general": g, "club": c, "set_by": "ai"}
    return table


def prices_open(league):
    """You can change this season's prices until its first game is played."""
    from . import season as SE
    if SE.in_offseason(league):
        return True
    return not any(g.get("played") for g in _season_games(league))


def set_your_prices(league, general, club):
    """Your two prices for this season. Returns (ok, message)."""
    tid = league.user_team_id
    if tid is None:
        return False, "You don't run a team."
    if not prices_open(league):
        return False, "Prices are set for the season once its first game is played."
    general, club = int(round(general)), int(round(club))
    if general < 10 or club < general:
        return False, "Club seats must cost at least as much as regular seats, and regular seats at least $10."
    _fin(league)["prices"].setdefault(league.season, {})[tid] = {"general": general, "club": club, "set_by": "you"}
    return True, "Ticket prices set."


def suite_price(league, tid, season=None):
    """A suite for the season ($K)."""
    p = prices(league, tid, season)
    return p["club"] * SUITE_SEATS * 10 * SUITE_MULT / 1000 if p else 0


def forecast(league, tid, general=None, club=None, season=None):
    """What your staff expects at these prices (their estimate, not the truth):
    {"fill", "club_fill", "attendance", "gate_k"} for an average regular-season game."""
    season = league.season if season is None else season
    p = prices(league, tid, season) or {}
    general = p.get("general") if general is None else general
    club = p.get("club") if club is None else club
    est = estimated_sellout(league, tid, season)
    s = seats(league, tid)
    fill = demand_share(general, est)
    club_fill = demand_share(club, est * CLUB_MULT * _corporate(league, tid, season))
    att = s["general"] * fill + s["club"] * club_fill + s["suite"] * min(1.0, club_fill + 0.05)
    return {"fill": fill, "club_fill": club_fill, "attendance": round(att),
            "gate_k": (s["general"] * fill * general + s["club"] * club_fill * club) / 1000}


def family_of_four(league, tid, season=None):
    """FOF8's (and Team Marketing Report's) family-of-four cost: 4 regular tickets, 4
    sodas, 4 hot dogs, 2 beers, 2 caps and parking ($; TMR 2024 average $691)."""
    p = prices(league, tid, season)
    if not p:
        return None
    r = ratio(league, season) * (team(league, tid)["income"] / INCOME_MID) ** 0.3
    extras = (4 * 6.5 + 4 * 7.0 + 2 * 13.0 + 2 * 30.0 + 45.0) * r
    return 4 * p["general"] + extras


# ---------------------------------------------------------------------------
# Each home game
# ---------------------------------------------------------------------------

def _season_games(league):
    return list(league.preseason) + list(league.schedule) + list(league.playoffs)


def _record_before(league, tid, g):
    """The team's record in this regular season before game g."""
    w = l_ = t_ = 0
    for x in league.schedule:
        if not x.get("played") or x["week"] >= g["week"] or tid not in (x["home"], x["away"]):
            continue
        mine, theirs = ((x["home_score"], x["away_score"]) if x["home"] == tid else (x["away_score"], x["home_score"]))
        if mine > theirs:
            w += 1
        elif mine < theirs:
            l_ += 1
        else:
            t_ += 1
    return {"w": w, "l": l_, "t": t_}


def game_played(league, g):
    """A finished game: the home team's crowd and game-day money (season.record_game
    calls this; neutral-site games earn no home gate)."""
    fin = league.finances
    if fin is None or not fin.get("teams"):
        return None
    games = fin["games"].setdefault(league.season, {})
    if g["id"] in games or g.get("neutral"):
        return games.get(g["id"])
    from . import season as SE
    tid, opp = g["home"], g["away"]
    kind = "playoffs" if SE.is_playoff_game(g) else "preseason" if SE.is_preseason_game(g) else "regular"
    s = seats(league, tid)
    p = prices(league, tid) or {"general": 0, "club": 0}
    sell = sellout_price(league, tid)
    rng = _rng(league, "game", league.season, g["id"])
    tilt = rng.gauss(0, GAME_NOISE)
    if kind == "regular":
        r = _record_before(league, tid, g)
        n = r["w"] + r["l"] + r["t"]
        if n >= 3:
            tilt += FORM_K * (_wins_pct(r) - 0.5) * min(1.0, n / 8)
        home_t, away_t = next(t for t in league.teams if t.id == tid), next(t for t in league.teams if t.id == opp)
        if home_t.division == away_t.division and home_t.conference == away_t.conference:
            tilt += RIVAL_K
        tilt += OPP_BRAND_K * team(league, opp)["brand"]
        if stadium(league, tid)["roof"] == "outdoor" and g["week"] >= 13 and n and _wins_pct(r) < 0.4:
            tilt -= COLD_LOSER
    elif kind == "preseason":
        tilt += math.log(PRESEASON_DEMAND)
    if kind == "playoffs":
        fill = club_fill = 1.0
    else:
        fill = demand_share(p["general"], sell * math.exp(tilt))
        club_fill = demand_share(p["club"], sell * math.exp(tilt) * CLUB_MULT * _corporate(league, tid, league.season))
    general = round(s["general"] * fill)
    club = round(s["club"] * club_fill)
    suite = round(s["suite"] * min(1.0, club_fill + 0.05))
    att = general + club + suite
    per_fan = (PER_FAN_2026 + STORE_PER_FAN_2026) * ratio(league) * (team(league, tid)["income"] / INCOME_MID) ** 0.3
    rec = {"home": tid, "away": opp, "kind": kind, "att": att, "capacity": stadium(league, tid)["capacity"],
           "general": general, "club": club, "suite": suite, "week": g.get("week"),
           "price": p["general"], "club_price": p["club"]}
    if kind == "playoffs":
        # The league keeps playoff ticket money; the home team keeps concessions and parking.
        rec.update({"gate": 0, "club_gate": 0, "conc": round(PLAYOFF_GAME_PER_CAP * cap_k(league))})
    else:
        rec.update({"gate": round(general * p["general"] / 1000), "club_gate": round(club * p["club"] / 1000),
                    "conc": round(att * per_fan / 1000)})
    games[g["id"]] = rec
    return rec


def home_games(league, tid, season=None):
    """This season's home games so far, in order: [record]."""
    season = league.season if season is None else season
    games = _fin(league)["games"].get(season, {})
    out = [dict(r, gid=gid) for gid, r in games.items() if r["home"] == tid]
    order = {"preseason": 0, "regular": 1, "playoffs": 2}
    return sorted(out, key=lambda r: (order[r["kind"]], r.get("week") or 0))


# ---------------------------------------------------------------------------
# The books
# ---------------------------------------------------------------------------

def _scheduled_home(league, tid):
    """Regular-season and preseason home games on this season's schedule (not neutral)."""
    reg = sum(1 for g in league.schedule if g["home"] == tid and not g.get("neutral"))
    pre = sum(1 for g in league.preseason if g["home"] == tid and not g.get("neutral"))
    return reg, pre


def player_cash(league, tid, season=None):
    """Cash paid to players this season ($K): base salaries (cap hits less bonus
    proration), signing bonuses paid this league year (note_bonus: paid up front), and
    the cash part of dead money."""
    from . import contracts as C
    season = league.season if season is None else season
    if getattr(league, "contracts", None) is None:
        return round(cap_k(league, season) * 0.97)
    total = 0
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        if not c or c["team"] != tid:
            continue
        y = C._year(c, season)
        if y:
            total += max(0, C.cap_hit(league, c, season) - y["bonus"])
    bonus = _fin(league)["bonus"].get(season, {}).get(tid, 0)
    if season == league.settings.get("first_season"):
        bonus += _starting_bonuses(league, tid, season)
    return round(total + bonus + DEAD_CASH * C.charges(league, tid, season))


def _starting_bonuses(league, tid, season):
    """A new league's first season: the bonuses of its starting contracts dated this
    year (made as if signed this spring; free_agency.initial_contracts logs none)."""
    logged = {e["pid"] for e in getattr(league, "contract_log", ()) if e.get("season") == season}
    return sum(c.get("signing_bonus", 0) for pid, c in league.contracts.items()
               if c["team"] == tid and c.get("signed") == season and pid not in logged)


def _staff_cost(league, tid, season):
    try:
        from . import staff as S
        return S.payroll(league, tid, season) + S.dead_money(league, tid, season)
    except Exception:
        return round(0.066 * cap_k(league, season))


def books(league, tid, season=None, pool=None):
    """A team's profit and loss ($K). A closed season returns its record. The season in
    progress returns {"lines": {...} for the full season (game-day money: what's been
    earned so far plus the staff's forecast for the home games left), "so_far": {...}
    game-day money earned so far, "games_left": n}."""
    fin = _fin(league)
    season = league.season if season is None else season
    closed = fin["books"].get(season, {}).get(tid)
    if closed:
        return {"lines": closed, "so_far": None, "games_left": 0, "closed": True}
    if season != league.season:
        return None
    return _live_books(league, tid, season, pool)


def _pool(league, season):
    """Every team's seats' face value this season ($K; for the visiting teams' pool)."""
    return {t.id: _face_estimate(league, t.id, season) for t in league.teams}


def _live_books(league, tid, season, pool=None):
    fin = league.finances
    cap = cap_k(league, season)
    t = team(league, tid)
    games = [r for r in fin["games"].get(season, {}).values() if r["home"] == tid]
    so_far = {"gate": sum(r["gate"] for r in games), "club": sum(r["club_gate"] for r in games),
              "concessions": sum(r["conc"] for r in games if r["kind"] != "playoffs"),
              "playoffs": sum(r["conc"] for r in games if r["kind"] == "playoffs")}
    reg, pre = _scheduled_home(league, tid)
    played_reg = sum(1 for r in games if r["kind"] == "regular")
    played_pre = sum(1 for r in games if r["kind"] == "preseason")
    left_reg, left_pre = max(0, reg - played_reg), max(0, pre - played_pre)
    f = forecast(league, tid, season=season)
    p = prices(league, tid, season) or {"general": 0, "club": 0}
    s = seats(league, tid)
    per_fan = (PER_FAN_2026 + STORE_PER_FAN_2026) * ratio(league, season) * (t["income"] / INCOME_MID) ** 0.3
    left = left_reg + left_pre * PRESEASON_DEMAND
    gate = so_far["gate"] + left * s["general"] * f["fill"] * p["general"] / 1000
    club = so_far["club"] + left * s["club"] * f["club_fill"] * p["club"] / 1000
    conc_all = so_far["concessions"] + left * f["attendance"] * per_fan / 1000
    store = conc_all * STORE_PER_FAN_2026 / (PER_FAN_2026 + STORE_PER_FAN_2026)
    conc = conc_all - store
    suites_sold = min(1.0, f["club_fill"] + 0.05) * stadium(league, tid)["suites"]
    suites = suites_sold * suite_price(league, tid, season)
    # Visiting teams' share: this team pays VTS_SHARE of its seats' face value into the
    # pool and gets 1/32 of the pool (everyone's, estimated the same way).
    face_mine = gate + club * p["general"] / max(1, p["club"])      # club seats count at a regular seat's price
    pool = dict(pool or _pool(league, season))
    pool[tid] = face_mine
    pool = sum(pool.values())
    vts_out = -VTS_SHARE * face_mine
    vts_in = VTS_SHARE * pool / len(league.teams)
    newness = _newness(league, tid, season)
    h = hype(league, tid, season)
    sponsors = SPONSOR_PER_CAP * cap * math.exp(SPONSOR_BRAND * t["brand"] + SPONSOR_MARKET * math.log(t["market"] / MARKET_MID)
                                              + SPONSOR_NEW * newness + SPONSOR_HYPE * h - 0.22)
    media = MEDIA_PER_CAP * cap * math.exp(0.15 * math.log(t["market"] / MARKET_MID) + 0.25 * t["brand"])
    events = EVENTS_PER_CAP[0] * cap * t["events"] * (0.7 + 0.6 * newness)
    lines = {"national": NATIONAL_PER_CAP * cap, "gate": gate, "club": club, "suites": suites,
             "vts_in": vts_in, "vts_out": vts_out, "sponsors": sponsors, "concessions": conc, "store": store,
             "events": events, "media": media, "playoffs": so_far["playoffs"]}
    local = sum(v for k, v in lines.items() if k != "national")
    lines.update({"players": -player_cash(league, tid, season), "benefits": -BENEFITS_PER_CAP * cap,
                  "staff": -_staff_cost(league, tid, season),
                  "operations": -(OPEX_FIXED * cap * t["opex"] + OPEX_VAR * local)})
    lines = {k: round(v) for k, v in lines.items()}
    _totals(lines)
    return {"lines": lines, "so_far": so_far, "games_left": left_reg + left_pre, "closed": False}


def _face_estimate(league, tid, season):
    """A team's regular and club seats' face value for the season ($K, for the visiting
    pool): what it has earned plus the forecast for its games left."""
    fin = league.finances
    games = [r for r in fin["games"].get(season, {}).values() if r["home"] == tid and r["kind"] != "playoffs"]
    p = prices(league, tid, season) or {"general": 0, "club": 0}
    done = sum((r["general"] + r["club"]) * r["price"] for r in games) / 1000
    reg, pre = _scheduled_home(league, tid)
    left = max(0, reg - sum(1 for r in games if r["kind"] == "regular")) + \
        PRESEASON_DEMAND * max(0, pre - sum(1 for r in games if r["kind"] == "preseason"))
    if left <= 0:
        return done
    f = forecast(league, tid, season=season)
    s = seats(league, tid)
    return done + left * (s["general"] * f["fill"] + s["club"] * f["club_fill"]) * p["general"] / 1000


def _totals(lines):
    rev = sum(lines[k] for k, _ in LINES_REVENUE if k in lines)
    exp_ = sum(lines[k] for k, _ in LINES_EXPENSE if k in lines)
    lines["revenue"] = rev
    lines["expenses"] = exp_
    lines["profit"] = rev + exp_
    lines["local"] = rev - lines.get("national", 0)


def attendance(league, tid, season=None):
    """{"avg", "fill", "games", "sellouts"} over regular-season home games."""
    season = league.season if season is None else season
    closed = _fin(league)["books"].get(season, {}).get(tid)
    if closed and "att_avg" in closed:
        return {"avg": closed["att_avg"], "fill": closed["fill"], "games": closed["home_games"],
                "sellouts": closed.get("sellouts", 0)}
    games = [r for r in home_games(league, tid, season) if r["kind"] == "regular"]
    if not games:
        return {"avg": None, "fill": None, "games": 0, "sellouts": 0}
    avg = statistics.mean(r["att"] for r in games)
    cap_ = statistics.mean(r["capacity"] for r in games)
    return {"avg": round(avg), "fill": avg / cap_, "games": len(games),
            "sellouts": sum(1 for r in games if r["att"] >= r["capacity"] * 0.995)}


def franchise_value(league, tid, season=None):
    """An estimate of what the team would sell for ($K): revenue x a multiple, a bit
    more in a big market (Forbes' method, roughly)."""
    b = books(league, tid, season)
    if not b:
        return None
    m = team(league, tid)["market"]
    return round(b["lines"]["revenue"] * VALUE_MULT * math.exp(VALUE_MARKET * math.log(m / MARKET_MID)))


def fan_support(league, tid, season=None):
    """0-100 (shown with trait words): the franchise's pull plus recent winning."""
    z = team(league, tid)["brand"] + hype(league, tid, season) / 0.06
    return max(1, min(99, round(50 + 15 * z)))


# ---------------------------------------------------------------------------
# The season ends: close the books, the owner's budget
# ---------------------------------------------------------------------------

def close_season(league):
    """The season is over (season.begin_offseason, before the new league year): every
    team's books are kept for good, and each owner's staff budget drifts with his
    profits. Returns {tid: lines}."""
    fin = _fin(league)
    S = league.season
    out = {}
    pool = _pool(league, S)
    for t in league.teams:
        b = _live_books(league, t.id, S, pool)["lines"]
        a = attendance(league, t.id, S)
        p = prices(league, t.id, S) or {}
        b.update({"att_avg": a["avg"], "fill": round(a["fill"], 4) if a["fill"] else None,
                  "home_games": a["games"], "sellouts": a["sellouts"], "price": p.get("general"),
                  "club_price": p.get("club"), "set_by": p.get("set_by")})
        out[t.id] = b
    fin["books"][S] = out
    for t in league.teams:
        out[t.id]["value"] = franchise_value(league, t.id, S)
    _owner_budgets(league, S)
    # Game-by-game detail isn't needed once a season is closed (keep the save small);
    # last season's stays for the screens.
    for key in ("games", "bonus"):
        for s in [s for s in fin[key] if s < S - 1]:
            del fin[key][s]
    return out


def _season_rows(league, season):
    """Every team's books for a season: the closed record, or (a finished season whose
    books aren't closed yet, as when your owner reviews you) the live ones."""
    fin = _fin(league)
    if season in fin["books"]:
        return fin["books"][season]
    from . import season as SE
    if season == league.season and SE.season_over(league):
        pool = _pool(league, season)
        return {t.id: _live_books(league, t.id, season, pool)["lines"] for t in league.teams}
    return {}


def expected_profit(league, tid, season, rows=None):
    """What a team in this market and stadium should make in an ordinary season ($K):
    the league's average profit plus the share of its local edge that profit keeps."""
    rows = _season_rows(league, season) if rows is None else rows
    if not rows or tid not in rows:
        return None
    avg_local = statistics.mean(r["local"] for r in rows.values())
    avg_profit = statistics.mean(r["profit"] for r in rows.values())
    return avg_profit + (1 - OPEX_VAR) * (rows[tid]["local"] - avg_local)


def profit_score(league, tid, seasons=3):
    """How this team's profit compares with what it should make, in spreads (average
    of the last few closed seasons; 0 = as expected, -1 = a spread short)."""
    fin = _fin(league)
    zs = []
    for s in sorted(set(fin["books"]) | {league.season})[-seasons:]:
        rows = _season_rows(league, s)
        row = rows.get(tid)
        exp_ = expected_profit(league, tid, s, rows)
        if row and exp_ is not None:
            zs.append((row["profit"] - exp_) / (PROFIT_SPREAD * cap_k(league, s)))
    return statistics.mean(zs) if zs else 0.0


def _owner_budgets(league, season):
    """Each owner's staff budget drifts with his profits (budget_mult, read by
    staff.budget). His free agency spending level stays his own (free_agency.spend_level
    reads only staff["owner"]): letting profits move it too made one AI team in 12
    league-offseasons end a checkpoint over the cap (scoreboard, Oct 26)."""
    for t in league.teams:
        ft = league.finances["teams"][t.id]
        target = math.exp(BUDGET_PROFIT_K * max(-2.0, min(2.0, profit_score(league, t.id))))
        cur = ft.get("budget_mult", 1.0)
        ft["budget_mult"] = round(max(BUDGET_MULT[0], min(BUDGET_MULT[1], cur + BUDGET_DRIFT * (target - cur))), 3)


def budget_mult(league, tid):
    """The owner's staff budget times this (profits; 1.0 before any season closes)."""
    fin = getattr(league, "finances", None)
    if not fin or not fin.get("teams") or tid not in fin["teams"]:
        return 1.0
    return fin["teams"][tid].get("budget_mult", 1.0)


def owner_money_factor(league, tid):
    """For 'owner can fire you': the money part of your owner's view, multiplying the
    chance he lets you go (Blake: winning first, money only at the edges). Losing money,
    or making well under what the team should, raises it; a strong money record lowers
    it a little. Returns (factor, plain words or None)."""
    fin = getattr(league, "finances", None)
    if not fin or not fin.get("teams"):
        return 1.0, None
    seasons = [s for s in sorted(set(fin["books"]) | {league.season}) if _season_rows(league, s)]
    if not seasons:
        return 1.0, None
    z = profit_score(league, tid)
    bad = max(0.0, -z - 0.75)
    # Losing money: each of the last two seasons in the red adds to it.
    bad += 0.5 * sum(1 for s in seasons[-2:] if (_season_rows(league, s).get(tid) or {}).get("profit", 0) < 0)
    good = max(0.0, z - 0.5)
    f = max(0.85, min(1.6, 1 + MONEY_HEAT[0] * bad - MONEY_HEAT[1] * min(1.5, good)))
    if f >= 1.05:
        word = "the owner is unhappy with the team's profits"
    elif f <= 0.95:
        word = "the owner likes the team's profits"
    else:
        word = None
    return f, word


# ---------------------------------------------------------------------------
# For the screens
# ---------------------------------------------------------------------------

def league_table(league, season=None):
    """One row per team for the League finances page."""
    season = league.season if season is None else season
    rows = []
    fin = _fin(league)
    pool = _pool(league, season) if season == league.season and season not in fin["books"] else None
    for t in league.teams:
        b = books(league, t.id, season, pool)
        if not b:
            continue
        a = attendance(league, t.id, season)
        p = prices(league, t.id, season) or {}
        rows.append({"team": t.id, "market": team(league, t.id)["market"], "stadium_age": stadium_age(league, t.id, season),
                     "capacity": stadium(league, t.id)["capacity"], "att": a["avg"], "fill": a["fill"],
                     "price": p.get("general"), "revenue": b["lines"]["revenue"], "local": b["lines"]["local"],
                     "profit": b["lines"]["profit"], "value": franchise_value(league, t.id, season),
                     "support": fan_support(league, t.id, season), "closed": b.get("closed", False)})
    return rows


def history(league, tid):
    """Closed seasons for this team, newest first: [{"season", lines...}]."""
    fin = _fin(league)
    return [dict(fin["books"][s][tid], season=s) for s in sorted(fin["books"], reverse=True) if tid in fin["books"][s]]


def market_word(m):
    if m >= 3.0:
        return "Very large"
    if m >= 2.0:
        return "Large"
    if m >= 1.3:
        return "Medium"
    if m >= 0.9:
        return "Small"
    return "Very small"
