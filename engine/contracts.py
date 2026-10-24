# contracts.py
# Money: the salary cap, player contracts and how they count against the cap,
# by the real NFL's rules (the 2020 CBA, which runs through 2030). Rules and
# accounting only; who gets paid what is decided in cap_market.py (the
# market's price for a player) and free_agency.py (AI teams and players).
#
# Units: every amount is in thousands of dollars ($K) as a whole number, so
# cap math is exact (a team is either under the cap or it isn't). 885 = $885K,
# 72600 = $72.6M. fmt_money() turns them into "$72.6M" for screens.
#
# Where things live (all on the league; see ensure()):
#   league.contracts    {player id: contract}  every player under contract
#   league.cap_history  {season: $K}           each league year's salary cap
#   league.cap_carry    {team id: {season: $K}} unused cap carried into a season
#   league.cap_charges  {team id: {season: $K}} money that counts against a team's
#                       cap for players no longer on it: dead money from cuts,
#                       salary already paid to them, elevation pay
#   league.contract_log [every contract signed, for history, news and the checks]
#
# A contract:
#   {"pid", "team", "kind", "signed": league year signed, "week": pay week he
#    joined in that season (0 = from the start), "years": [{"season", "base",
#    "bonus" (this year's share of signing/restructure bonuses), "gtd" (the
#    guaranteed part of this year's base)}, ...], "apy", "value", "guaranteed",
#    "signing_bonus", "vsb" (veteran salary benefit), "tags" (franchise tags in a
#    row), "option" (a first-rounder's fifth-year option), "exp_at_signing"}
# kinds: rookie, udfa, veteran, minimum, futures, tag, tender, option,
#        practice (practice squad, paid by the week), extension
#
# Real rules used (sources in docs/free-agency-design.md):
#   - The cap: real figures 1994-2026; later years come from each league's own
#     TV-deal eras, labor deals and rare shocks (league_money.py).
#   - Minimum salaries by credited season (2020 CBA table, 2020-2030).
#   - Signing bonuses are spread evenly over the contract, at most 5 years.
#   - Base salaries are paid over 18 regular-season weeks; a player signed or
#     cut during the season counts only for the weeks he was paid.
#   - From the start of the league year to the first regular-season game only a
#     team's 51 biggest cap hits count (the "top 51" rule); then everyone does.
#   - Cuts: remaining bonus money speeds up onto this year's cap ("dead money")
#     plus any guaranteed salary still owed; after June 1 (and during the
#     season) the bonus money for future years moves to next year instead. Teams
#     may name 2 players a year as "post-June 1" cuts in the spring.
#   - A vested veteran (4+ seasons) on the week-1 roster who is cut during the
#     season is still owed the rest of that season's salary (termination pay).
#   - Veteran salary benefit: a 4+ season veteran on a 1-year minimum deal
#     counts against the cap like a 2-season player's minimum.
#   - Unused cap space carries over to next season.
#   - Rookie wage scale by draft slot; 4-year deals; first-rounders have a
#     fifth-year option. Undrafted rookies sign 3-year minimum deals.
#   - Franchise tag; restricted free agent tenders.

import math
import random

from . import league_money as LM

# ---- The salary cap ($M), real figures -----------------------------------------
# 2011-2026 from the research (docs/research/real_contracts.json, OverTheCap/NFL);
# 1994-2010 are the published caps (2010 was an uncapped year: 2009's figure is used).
CAP_HISTORY_M = {
    1994: 34.608, 1995: 37.1, 1996: 40.753, 1997: 41.454, 1998: 52.388, 1999: 57.288,
    2000: 62.172, 2001: 67.405, 2002: 71.101, 2003: 75.007, 2004: 80.582, 2005: 85.5,
    2006: 102.0, 2007: 109.0, 2008: 116.0, 2009: 123.0, 2010: 123.0,
    2011: 120.0, 2012: 120.6, 2013: 123.0, 2014: 133.0, 2015: 143.28, 2016: 155.27,
    2017: 167.0, 2018: 177.2, 2019: 188.2, 2020: 198.2, 2021: 182.5, 2022: 208.2,
    2023: 224.8, 2024: 255.4, 2025: 279.2, 2026: 301.2,
}
# Years after the last real cap: TV-deal eras, labor deals and rare shocks
# (league_money.py; Blake, Oct 24). Until then each year was a random 2-13%.
# The pace used only for years before the first real cap (1994):
CAP_GROWTH = (0.07,)

# ---- Minimum salaries ($K) by credited seasons: 0, 1, 2, 3, 4-6, 7+ (2020 CBA) --
MIN_SALARY = {
    2020: (610, 675, 750, 825, 910, 1050), 2021: (660, 780, 850, 920, 990, 1075),
    2022: (705, 825, 895, 965, 1035, 1120), 2023: (750, 870, 940, 1010, 1080, 1165),
    2024: (795, 915, 985, 1055, 1125, 1210), 2025: (840, 960, 1030, 1100, 1170, 1255),
    2026: (885, 1005, 1075, 1145, 1215, 1300), 2027: (930, 1050, 1120, 1190, 1260, 1345),
    2028: (975, 1095, 1165, 1235, 1305, 1390), 2029: (1020, 1140, 1210, 1280, 1350, 1435),
    2030: (1065, 1185, 1255, 1325, 1395, 1480),
}
# Practice squad pay per week ($K), 2026: 2 or fewer seasons / 3-4 / 5+ (research:
# docs/research/transactions_rules_check.md; the veteran split is approximate).
PS_WEEKLY_2026 = (13.75, 18.35, 22.85)
PAY_WEEKS = 18                 # base salaries are paid in 18 weekly checks in the regular season
TOP_51 = 51                    # offseason: only a team's 51 biggest cap hits count
MAX_PRORATION_YEARS = 5        # a signing bonus is spread over at most 5 seasons
JUNE1_CUTS_PER_YEAR = 2        # "post-June 1" designations a team may use in the spring
VESTED = 4                     # seasons to be a vested veteran (termination pay, no waivers)
VSB_EXPERIENCE = 4             # veteran salary benefit: 4+ seasons on a 1-year minimum deal
VSB_COUNTS_AS = 2              # ...counts like a player with this many seasons
UDFA_YEARS = 3
ROOKIE_YEARS = 4

# ---- Rookie wage scale: average per year as a share of the cap, by overall pick --
# Real 2017-22 rookie deals (docs/research/real_contracts.json, rookie_scale_by_round):
# round 1 median 1.9% (top picks 4-5%), round 2 0.85%, round 3 0.6%, round 4 0.5%,
# rounds 5-7 0.4% (about the minimum). In between, a smooth slide by pick (real
# deals fall by slot; the 2024-25 numbers: #1 ~4.4%, #32 ~1.3%, #33 ~1.0%).
ROOKIE_SCALE = [(1, 0.045), (3, 0.040), (5, 0.034), (10, 0.0245), (16, 0.0195), (24, 0.016),
                (32, 0.013), (33, 0.0098), (48, 0.0084), (64, 0.0065), (65, 0.0062), (80, 0.0058),
                (100, 0.0054), (101, 0.0050), (140, 0.0046), (141, 0.0043), (180, 0.0041),
                (181, 0.0040), (224, 0.0039), (400, 0.0039)]
UDFA_BONUS_K = (0, 60)         # undrafted signing bonus, typical range at the 2026 cap ($K; the best get more)

# ---- Franchise tag: share of the cap, by tag group -------------------------------
# Real 2024 non-exclusive franchise tags ($255.4M cap): QB $38.3M, RB $12.0M, WR $21.8M,
# TE $12.7M, OL $21.0M, DE $21.3M, DT $22.1M, LB $24.0M, CB $19.8M, S $17.1M, K/P $6.0M.
# The real LB tag includes 3-4 edge rushers; this game's linebackers are off-ball ones,
# so their tag is set from the off-ball pay ladder instead (about 0.7 of the top-5 pay,
# the ratio the other groups show). A tag is at least 120% of his previous cap hit;
# a second tag in a row is 120% of the first, a third 144% (real rules).
TAG_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
             "DE": "DE", "DT": "DT", "OLB": "LB", "ILB": "LB", "CB": "CB", "S": "S", "K": "KP", "P": "KP",
             "LS": "KP"}
TAG_SHARE = {"QB": 0.150, "RB": 0.047, "WR": 0.085, "TE": 0.050, "OL": 0.082, "DE": 0.083, "DT": 0.087,
             "LB": 0.063, "CB": 0.078, "S": 0.067, "KP": 0.023}
TRANSITION_SHARE = 0.88        # the transition tag (top-10 average) runs about this share of the franchise tag
# ---- Restricted free agent tenders (3 accrued seasons), 2025: right of first refusal
# $3.263M, second-round $5.346M, first-round $7.458M ($279.2M cap) ---------------
RFA_TENDER_SHARE = {"rofr": 0.0117, "second": 0.0191, "first": 0.0267}
ERFA = 2                       # 2 or fewer accrued seasons: exclusive rights free agent
RFA = 3                        # 3: restricted free agent; 4+: unrestricted
# ---- Fifth-year option (first-rounders), 2020 CBA: by playing time. Basic level is
# the average of the 3rd-25th highest salaries (cap numbers) at the position; a regular
# starter's the 3rd-20th. Pro Bowl levels (transition / franchise tag) need a Pro Bowl
# (not yet). See option_salary.
# -----------------------------------------------------------------------------------


def ensure(league):
    """Add the money lists to leagues and saves from before contracts."""
    for key, default in (("contracts", dict), ("cap_history", dict), ("cap_carry", dict),
                         ("cap_charges", dict), ("contract_log", list), ("june1_used", dict)):
        if getattr(league, key, None) is None:
            setattr(league, key, default())
    return league


# ---------------------------------------------------------------------------
# The cap and minimums
# ---------------------------------------------------------------------------

def _real_cap_k(season):
    return round(CAP_HISTORY_M[season] * 1000)


def cap_for(league, season):
    """The salary cap ($K) for a season: the league's own record if set, the
    real figure for past years, else a projection for planning (next year's
    announced projection, then the expected pace with every TV and labor deal
    already signed: league_money.projected)."""
    ensure(league)
    if season in league.cap_history:
        return league.cap_history[season]
    if season in CAP_HISTORY_M:
        return _real_cap_k(season)
    first = min(CAP_HISTORY_M)
    if season < first:
        return round(_real_cap_k(first) * (1 - CAP_GROWTH[0]) ** (first - season))
    base_season = max([s for s in league.cap_history if s < season] + [s for s in CAP_HISTORY_M if s < season])
    base = league.cap_history.get(base_season) or _real_cap_k(base_season)
    return LM.projected(league, season, base_season, base)


def set_cap(league, season):
    """Fix this league year's cap (called when the league year starts). Real
    years use the real cap; later years come from the league's TV-deal eras
    (league_money.py: next year's figure is projected a year ahead, the same for
    a given league and year every time)."""
    ensure(league)
    if season in league.cap_history:
        return league.cap_history[season]
    if season in CAP_HISTORY_M:
        cap = _real_cap_k(season)
    else:
        prev = cap_for(league, season - 1)
        cap = LM.league_year(league, season, prev)
    league.cap_history[season] = cap
    return cap


def adjusted_cap(league, tid, season):
    """The cap plus this team's carryover of unused space from last season."""
    return cap_for(league, season) + league.cap_carry.get(tid, {}).get(season, 0)


def _scaled_table(league, season, table_year):
    ratio = cap_for(league, season) / cap_for(league, table_year)
    return tuple(round(v * ratio) for v in MIN_SALARY[table_year])


def min_salary(league, experience, season=None):
    """Minimum base salary ($K) for a player with this many credited seasons."""
    season = league.season if season is None else season
    if season in MIN_SALARY:
        table = MIN_SALARY[season]
    else:
        table = _scaled_table(league, season, max(MIN_SALARY) if season > max(MIN_SALARY) else min(MIN_SALARY))
    e = max(0, experience)
    return table[0 if e == 0 else 1 if e == 1 else 2 if e == 2 else 3 if e == 3 else 4 if e <= 6 else 5]


def ps_weekly(league, experience, season=None):
    """Practice squad pay per week ($K)."""
    season = league.season if season is None else season
    level = PS_WEEKLY_2026[0 if experience <= 2 else 1 if experience <= 4 else 2]
    return level * cap_for(league, season) / _real_cap_k(2026)


def share(league, amount_k, season=None):
    """An amount as a share of that season's cap."""
    return amount_k / cap_for(league, league.season if season is None else season)


def fmt_money(k):
    """$K -> '$72.6M', '$885K', '-$1.2M', '$1.17B' (the cap passes $1B around 2045)."""
    sign = "-" if k < 0 else ""
    k = abs(k)
    if k >= 999_500:
        return f"{sign}${k / 1_000_000:.2f}B" if k < 99_995_000 else f"{sign}${k / 1_000_000:.0f}B"
    if k >= 1000:
        m = k / 1000
        return f"{sign}${m:.1f}M" if m < 100 else f"{sign}${m:.0f}M"
    return f"{sign}${round(k)}K"


def pay_week(league):
    """Regular-season pay weeks already paid (0 in the offseason and preseason,
    18 once the regular season is over)."""
    stage = getattr(league, "stage", "")
    if stage == "regular_season":
        return max(0, min(PAY_WEEKS, getattr(league, "week", 1) - 1))
    if stage in ("regular_season_done", "playoffs", "season_complete"):
        return PAY_WEEKS
    return 0


def after_june1(league):
    """Training camp and the preseason come after June 1 (real calendar: the league
    year opens in March, camps open in late July). Every cut from then on splits
    its dead money between this season and next on its own, with no designation
    needed; in the offseason stage (March to June) a cut speeds it all onto this
    season unless it's one of the team's 2 post-June 1 designations."""
    return getattr(league, "stage", "") == "preseason"


def top51_in_force(league):
    """The top-51 rule applies from the start of the league year until the
    first regular-season game."""
    stage = getattr(league, "stage", "")
    if stage == "regular_season":
        if pay_week(league) > 0:
            return False
        # Week 1: until its games are played. (Before Oct 23 it also covered the moves made
        # right after the week-1 games, when the week counter still said 1: AI teams signed
        # players by the top-51 count and were over the cap once every contract counted.)
        return not any(g.get("played") for g in getattr(league, "schedule", ()) if g.get("week") == 1)
    return stage not in ("regular_season_done", "playoffs", "season_complete")


# ---------------------------------------------------------------------------
# Building a contract
# ---------------------------------------------------------------------------

def _year(c, season):
    for y in c["years"]:
        if y["season"] == season:
            return y
    return None


def last_season(c):
    return c["years"][-1]["season"] if c["years"] else None


def years_left(c, season):
    """Contract seasons from this one on (this season included)."""
    return sum(1 for y in c["years"] if y["season"] >= season)


def build(league, pid, tid, kind, start, n_years, apy, guaranteed=0, signing_bonus=None, rise=0.06,
          week=0, experience=None, note="", bases=None):
    """Make a contract (not yet attached to anyone; see sign()).
    apy: average per year ($K); guaranteed: total guaranteed ($K), which is
    the signing bonus plus the earliest base salaries; signing_bonus: $K
    (default: about half the guarantee on multi-year deals); rise: how much
    base salaries climb each year (real deals are back-loaded); bases: exact
    base salaries (rookie deals)."""
    p = league.player(pid)
    exp = p.experience if experience is None else experience
    n_years = max(1, int(n_years))
    total = int(round(apy * n_years))
    guaranteed = max(0, min(total, int(round(guaranteed))))
    mins = [min_salary(league, exp + i, start + i) for i in range(n_years)]
    if bases is None:
        if signing_bonus is None:
            signing_bonus = int(round(guaranteed * (0.55 if n_years > 1 else 0.5)))
        signing_bonus = max(0, min(signing_bonus, total - sum(mins)))
        rest = total - signing_bonus
        weights = [(1 + rise) ** i for i in range(n_years)]
        bases = [rest * w / sum(weights) for w in weights]
        # Every base at least the minimum (move money from the later years if needed).
        for i in range(n_years):
            if bases[i] < mins[i]:
                short = mins[i] - bases[i]
                bases[i] = mins[i]
                for j in range(n_years - 1, i, -1):
                    take = min(short, bases[j] - mins[j])
                    bases[j] -= take
                    short -= take
                    if short <= 0:
                        break
                if short > 0:
                    signing_bonus = max(0, signing_bonus - short)
        bases = [int(round(b)) for b in bases]
    else:
        signing_bonus = max(0, total - sum(bases)) if signing_bonus is None else signing_bonus
    pro_years = min(n_years, MAX_PRORATION_YEARS)
    pro = [signing_bonus // pro_years + (1 if i < signing_bonus % pro_years else 0) if i < pro_years else 0
           for i in range(n_years)]
    gtd_base = max(0, guaranteed - signing_bonus)
    years = []
    for i in range(n_years):
        g = min(bases[i], gtd_base)
        gtd_base -= g
        years.append({"season": start + i, "base": bases[i], "bonus": pro[i], "gtd": g})
    value = sum(y["base"] + y["bonus"] for y in years)
    c = {"pid": pid, "team": tid, "kind": kind, "signed": league.season, "week": week, "years": years,
         "apy": int(round(value / n_years)), "value": value,
         "guaranteed": signing_bonus + sum(y["gtd"] for y in years),
         "signing_bonus": signing_bonus, "vsb": False, "tags": 0, "option": None,
         "exp_at_signing": exp, "note": note}
    if kind in ("minimum", "futures") and n_years == 1 and exp >= VSB_EXPERIENCE:
        c["vsb"] = True
    return c


def sign(league, c, log=True, phase="", new_team=None):
    """Attach a contract to its player (replacing any he had)."""
    ensure(league)
    old = league.contracts.get(c["pid"])
    league.contracts[c["pid"]] = c
    if log:
        p = league.player(c["pid"])
        from datetime import date
        league.contract_log.append({
            "season": league.season, "pid": c["pid"], "team": c["team"], "kind": c["kind"], "phase": phase,
            "pos": p.position, "age": p.age(date(league.season, 9, 1)), "exp": p.experience,
            "years": len(c["years"]), "apy": c["apy"], "apy_share": round(c["apy"] / cap_for(league, league.season), 5),
            "guaranteed": c["guaranteed"], "value": c["value"],
            "new_team": (new_team if new_team is not None
                         else bool(old and old["team"] != c["team"]))})
        if c.get("pick"):
            league.contract_log[-1]["pick"] = c["pick"]
    return c


# ---------------------------------------------------------------------------
# Cap hits
# ---------------------------------------------------------------------------

def base_counted(league, c, y):
    """Base salary that counts on the cap that year (veteran salary benefit)."""
    if c.get("vsb"):
        return min(y["base"], min_salary(league, VSB_COUNTS_AS, y["season"]))
    return y["base"]


def cap_hit(league, c, season=None, full=False):
    """What the contract counts against the cap in a season ($K). A player who
    joined during the season counts only the weeks he's paid (from the week he
    signed), unless full=True. Practice squad contracts count by the week."""
    season = league.season if season is None else season
    y = _year(c, season)
    if y is None:
        return 0
    base = base_counted(league, c, y)
    if c["kind"] == "practice":
        weeks = PAY_WEEKS - (c["week"] if c["signed"] == season and not full else 0)
        return int(round(y["base"] * weeks / PAY_WEEKS))
    if c["signed"] == season and c["week"] and not full:
        base = base * (PAY_WEEKS - c["week"]) / PAY_WEEKS
    return int(round(base + y["bonus"]))


def players_with_team(league, tid):
    """Player ids on a team in any form: the 53, practice squad, reserve lists."""
    out = [pid for pid, t in league.rosters.items() if t == tid]
    out += [pid for pid, t in getattr(league, "practice", {}).items() if t == tid]
    out += [pid for pid, r in getattr(league, "reserve", {}).items() if r["team"] == tid]
    return out


def charges(league, tid, season=None):
    season = league.season if season is None else season
    return league.cap_charges.get(tid, {}).get(season, 0)


def add_charge(league, tid, season, amount):
    if amount:
        t = league.cap_charges.setdefault(tid, {})
        t[season] = t.get(season, 0) + int(round(amount))


def team_cap(league, tid, season=None, top51=None):
    """{'cap', 'used', 'room', 'dead', 'contracts'} for a team ($K). In the
    offseason only the 51 biggest cap hits count (practice squad pay starts
    in week 1); during the season every contract does."""
    ensure(league)
    season = league.season if season is None else season
    top51 = top51_in_force(league) if top51 is None else top51
    practice = getattr(league, "practice", {})
    hits = []
    for pid in players_with_team(league, tid):
        c = league.contracts.get(pid)
        if c is None or c["team"] != tid:
            continue
        if top51 and pid in practice:
            continue
        hits.append(cap_hit(league, c, season))
    if top51:
        hits = sorted(hits, reverse=True)[:TOP_51]
    dead = charges(league, tid, season)
    cap = adjusted_cap(league, tid, season)
    used = sum(hits) + dead
    return {"cap": cap, "used": used, "room": cap - used, "dead": dead, "contracts": sum(hits)}


def cap_room(league, tid, season=None, top51=None):
    return team_cap(league, tid, season, top51)["room"]


def room_after(league, tid, new_hit, season=None):
    """Cap room left if a contract with this cap hit were added now (the top-51
    rule means a cheap signing in the offseason may push out a smaller hit)."""
    season = league.season if season is None else season
    if not top51_in_force(league):
        return cap_room(league, tid, season) - new_hit
    practice = getattr(league, "practice", {})
    hits = [cap_hit(league, league.contracts[pid], season) for pid in players_with_team(league, tid)
            if pid in league.contracts and league.contracts[pid]["team"] == tid and pid not in practice]
    hits = sorted(hits + [new_hit], reverse=True)[:TOP_51]
    return adjusted_cap(league, tid, season) - sum(hits) - charges(league, tid, season)


def commitments(league, tid, season):
    """Money already committed to a future season ($K): contracts running into
    it plus dead money already charged to it (for planning)."""
    total = charges(league, tid, season)
    for pid in players_with_team(league, tid):
        c = league.contracts.get(pid)
        if c and c["team"] == tid and c["kind"] != "practice":
            total += cap_hit(league, c, season, full=True)
    return total


# ---------------------------------------------------------------------------
# Releases, retirements, restructures
# ---------------------------------------------------------------------------

def release_charges(league, c, week=None, june1=False):
    """{season: $K} that would stay on the team's cap if he were cut now."""
    season = league.season
    week = pay_week(league) if week is None else week
    p = league.player(c["pid"])
    out = {}
    if c["kind"] == "practice":
        y = _year(c, season)
        if y and week:
            start = c["week"] if c["signed"] == season else 0
            out[season] = int(round(y["base"] * max(0, week - start) / PAY_WEEKS))
        return out
    rest = [y for y in c["years"] if y["season"] >= season]
    if not rest:
        return out
    cur = rest[0] if rest[0]["season"] == season else None
    future = [y for y in rest if y["season"] > season]
    now = 0
    if cur:
        now += cur["bonus"]
        base = base_counted(league, c, cur)
        if week > 0:
            start = c["week"] if c["signed"] == season else 0
            earned = base * max(0, week - start) / PAY_WEEKS
            vested = p.experience >= VESTED and start == 0 and week >= 1
            now += base if vested else max(earned, min(base, cur["gtd"]))
        else:
            now += min(base, cur["gtd"])
    later = sum(y["bonus"] + y["gtd"] for y in future)
    if week > 0 or june1 or after_june1(league):
        out[season] = int(round(now))
        if later:
            out[season + 1] = int(round(later))
    else:
        out[season] = int(round(now + later))
    return {s: v for s, v in out.items() if v}


def release_preview(league, pid, june1=False):
    """What cutting him does to this season's cap: {'dead': {season: $K},
    'savings': $K this season, 'hit': his cap hit now}."""
    c = league.contracts.get(pid)
    if c is None:
        return {"dead": {}, "savings": 0, "hit": 0}
    hit = cap_hit(league, c)
    dead = release_charges(league, c, june1=june1)
    return {"dead": dead, "savings": hit - dead.get(league.season, 0), "hit": hit}


def june1_left(league, tid):
    """Post-June 1 designations this team has left this spring (none once camp
    opens: every cut is then a post-June 1 cut anyway)."""
    if pay_week(league) > 0 or after_june1(league):
        return 0
    return JUNE1_CUTS_PER_YEAR - league.june1_used.get(tid, {}).get(league.season, 0)


def best_release(league, pid):
    """(june1?, preview) for the way of cutting him that leaves the most cap
    room this season without pushing more dead money into next season than
    it saves now (a post-June 1 designation only if one is left)."""
    c = league.contracts.get(pid)
    plain = release_preview(league, pid)
    if c is None or not june1_left(league, c["team"]):
        return False, plain
    june = release_preview(league, pid, june1=True)
    later = june["dead"].get(league.season + 1, 0)
    if june["savings"] > plain["savings"] and later <= june["savings"]:
        return True, june
    return False, plain


def release(league, pid, june1=False, week=None):
    """He's cut (or waived, or let go from the practice squad): the money that
    stays behind is charged to his team and the contract ends. Returns the
    charges {season: $K}."""
    ensure(league)
    c = league.contracts.pop(pid, None)
    if c is None:
        return {}
    if june1 and pay_week(league) == 0 and not after_june1(league):
        used = league.june1_used.setdefault(c["team"], {})
        if used.get(league.season, 0) >= JUNE1_CUTS_PER_YEAR:
            june1 = False
        else:
            used[league.season] = used.get(league.season, 0) + 1
    out = release_charges(league, c, week=week, june1=june1)
    for season, amount in out.items():
        add_charge(league, c["team"], season, amount)
    return out


def retire(league, pid):
    """A player under contract retires: his remaining bonus money speeds onto
    his team's cap (teams rarely get it back); no salary is owed. What he was
    already paid stays on the books of the season it was paid in: the season
    just finished, for a spring retirement (before Oct 23 it dropped off, so
    it came back as unused room and carried over: about $30M a team a year),
    or the weeks played, during a season."""
    c = league.contracts.pop(pid, None)
    if c is None:
        return {}
    S = league.season
    week = pay_week(league)
    if week == 0 and _year(c, S - 1) is not None:
        add_charge(league, c["team"], S - 1, cap_hit(league, c, S - 1))
    cur = _year(c, S)
    if week > 0 and cur is not None:
        start = c["week"] if c["signed"] == S else 0
        add_charge(league, c["team"], S, base_counted(league, c, cur) * max(0, week - start) / PAY_WEEKS
                   if c["kind"] != "practice" else cur["base"] * max(0, week - start) / PAY_WEEKS)
    if c["kind"] == "practice":
        return {}
    rest = sum(y["bonus"] for y in c["years"] if y["season"] >= S)
    if rest:
        add_charge(league, c["team"], S, rest)
    return {S: rest} if rest else {}


def restructure_room(league, c, season=None):
    """Most base salary ($K) that could be turned into bonus this season. During
    the season only the checks still to come can be converted (weeks already
    paid are paid); once the regular season is over there's nothing left."""
    season = league.season if season is None else season
    y = _year(c, season)
    if y is None or c["kind"] in ("practice", "rookie", "udfa", "minimum", "futures", "tag", "tender"):
        return 0
    if years_left(c, season) < 2:
        return 0
    p = league.player(c["pid"])
    unpaid = (PAY_WEEKS - pay_week(league)) / PAY_WEEKS if season == league.season else 1.0
    return max(0, int((y["base"] - min_salary(league, p.experience, season)) * unpaid))


def _apply_restructure(c, amount, season):
    """Move `amount` of this season's base into bonus spread over the remaining
    seasons (at most 5). Returns {season: bonus added}."""
    rest = [y for y in c["years"] if y["season"] >= season]
    n = min(len(rest), MAX_PRORATION_YEARS)
    rest[0]["base"] -= amount
    rest[0]["gtd"] = min(rest[0]["gtd"], rest[0]["base"])
    added = {}
    for i in range(n):
        share = amount // n + (1 if i < amount % n else 0)
        rest[i]["bonus"] += share
        added[rest[i]["season"]] = share
    c["guaranteed"] += amount
    return added


def restructure(league, pid, amount=None):
    """Turn some of this season's base salary into a bonus spread over the
    contract's remaining seasons (at most 5): the classic way teams make cap
    room now at the cost of later years. Returns this season's savings ($K)."""
    c = league.contracts.get(pid)
    if c is None:
        return 0
    season = league.season
    room = restructure_room(league, c, season)
    amount = room if amount is None else max(0, min(room, int(amount)))
    if amount <= 0:
        return 0
    added = _apply_restructure(c, amount, season)
    c["restructured"] = c.get("restructured", 0) + 1
    return amount - added[season]


def restructure_preview(league, pid, amount=None):
    """What a restructure would do, without doing it: {'max': most that can be
    converted, 'amount', 'savings': cap room this season, 'added': {later
    season: cap hit added}, 'hits': {season: (cap hit before, after)},
    'dead_before' / 'dead_after': dead money if he were cut right after
    (all seasons)}. None if he has no contract."""
    import copy
    c = league.contracts.get(pid)
    if c is None:
        return None
    season = league.season
    room = restructure_room(league, c, season)
    amount = room if amount is None else max(0, min(room, int(amount)))
    after = copy.deepcopy(c)
    added = _apply_restructure(after, amount, season) if amount > 0 else {}
    hits = {y["season"]: (cap_hit(league, c, y["season"]), cap_hit(league, after, y["season"]))
            for y in c["years"] if y["season"] >= season}
    return {"max": room, "amount": amount, "savings": amount - added.get(season, 0),
            "added": {s: v for s, v in added.items() if s != season}, "hits": hits,
            "dead_before": sum(release_charges(league, c).values()),
            "dead_after": sum(release_charges(league, after).values())}


# ---------------------------------------------------------------------------
# Kinds of contract
# ---------------------------------------------------------------------------

def _interp(knots, x):
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x <= x1:
            t = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0)) if x0 > 0 else 0
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
    return knots[-1][1]


def rookie_apy_share(overall_pick):
    """Average per year of a drafted rookie's deal, as a share of the cap."""
    return _interp(ROOKIE_SCALE, max(1, overall_pick))


def rookie_contract(league, pid, tid, overall_pick, draft_round, start=None, rng=None):
    """The rookie wage scale: 4 years, base salaries at the minimum for each
    season, the rest as a signing bonus. Round 1: fully guaranteed (picks
    25-32: the first three years); round 2: the bonus and year 1 (top half
    also year 2); later rounds: the bonus. First-rounders carry a fifth-year
    option the team decides on before year 4."""
    start = league.season if start is None else start
    apy = rookie_apy_share(overall_pick) * cap_for(league, start)
    bases = [min_salary(league, i, start + i) for i in range(ROOKIE_YEARS)]
    total = max(sum(bases), int(round(apy * ROOKIE_YEARS)))
    bonus = total - sum(bases)
    if draft_round == 1:
        gtd = total if overall_pick <= 24 else bonus + sum(bases[:3])
    elif draft_round == 2:
        gtd = bonus + bases[0] + (bases[1] if overall_pick <= 48 else 0)
    else:
        gtd = bonus
    c = build(league, pid, tid, "rookie", start, ROOKIE_YEARS, total / ROOKIE_YEARS, guaranteed=gtd,
              signing_bonus=bonus, bases=bases, experience=0, note=f"pick {overall_pick}")
    if draft_round == 1:
        c["option"] = {"season": start + ROOKIE_YEARS, "salary": None, "exercised": None}
    c["pick"] = overall_pick
    return c


def udfa_contract(league, pid, tid, start=None, rng=None, bonus=None):
    """Undrafted rookie: 3 years at the minimum, a small signing bonus."""
    start = league.season if start is None else start
    rng = rng or random
    bases = [min_salary(league, i, start + i) for i in range(UDFA_YEARS)]
    if bonus is None:
        lo, hi = UDFA_BONUS_K
        bonus = int(round(rng.uniform(lo, hi) * cap_for(league, start) / _real_cap_k(2026)))
    return build(league, pid, tid, "udfa", start, UDFA_YEARS, (sum(bases) + bonus) / UDFA_YEARS,
                 guaranteed=bonus, signing_bonus=bonus, bases=bases, experience=0)


def minimum_contract(league, pid, tid, years=1, week=0, kind="minimum", start=None):
    """A minimum-salary deal (1 year unless asked), e.g. a depth signing, an
    in-season pickup or a reserve/future deal."""
    start = league.season if start is None else start
    p = league.player(pid)
    bases = [min_salary(league, p.experience + i, start + i) for i in range(years)]
    c = build(league, pid, tid, kind, start, years, sum(bases) / years, guaranteed=0, signing_bonus=0,
              bases=bases)
    c["week"] = week
    return c


def practice_contract(league, pid, tid, week=0, start=None):
    """A practice squad deal: paid by the week, no bonus, no guarantee."""
    start = league.season if start is None else start
    p = league.player(pid)
    season_pay = int(round(ps_weekly(league, p.experience, start) * PAY_WEEKS))
    c = build(league, pid, tid, "practice", start, 1, season_pay, bases=[season_pay], signing_bonus=0)
    c["week"] = week
    return c


def tag_amount(league, position, prior_hit=0, tags=0, market_ratio=1.0):
    """The franchise tag for a position this season ($K): the tag group's real
    share of the cap (moved by how this league's top salaries there compare
    with the real ones), at least 120% of his previous cap hit; a second tag
    in a row 120% of the last, a third 144% (real rules)."""
    base = TAG_SHARE[TAG_GROUP[position]] * cap_for(league, league.season) * max(0.8, min(1.25, market_ratio))
    if tags >= 2:
        base = max(base, prior_hit * 1.44)
    elif tags >= 1:
        base = max(base, prior_hit * 1.2)
    return int(round(max(base, 1.2 * prior_hit)))


def tag_contract(league, pid, tid, amount, tags_before=0):
    """One year, fully guaranteed, all base salary."""
    c = build(league, pid, tid, "tag", league.season, 1, amount, guaranteed=amount, signing_bonus=0,
              bases=[int(amount)])
    c["tags"] = tags_before + 1
    return c


def rfa_tender(league, level, prior_base=0):
    """Restricted free agent tender ($K): the level's amount or 110% of last
    year's base salary, whichever is more."""
    return int(round(max(RFA_TENDER_SHARE[level] * cap_for(league, league.season), 1.1 * prior_base)))


def option_salary(league, position, starter):
    """Fifth-year option amount ($K), 2020 CBA levels: a player who met the
    playing-time level (here: a regular starter) gets the average of the
    3rd-20th highest salaries at his position, otherwise the 3rd-25th; the
    "salaries" are this league year's cap numbers, not contract averages.
    (One Pro Bowl would make it the transition tag, two the franchise tag:
    not used yet.) Real 2024 options, set in 2023 ($224.8M cap): QB playing
    time $23.2M (Tagovailoa, 10.3% of the cap), basic $20.3M (Love, 9.0%);
    Pro Bowl level $29.5M (Herbert, 13.1%). (Until Oct 23 this used the top-10
    average per year, about twice the real figure: a starting QB's option
    came to ~20% of the cap.)"""
    hits = sorted((cap_hit(league, c, full=True) for c in league.contracts.values()
                   if c["kind"] != "practice" and league.player(c["pid"]).position == position),
                  reverse=True)
    top = hits[2:20] if starter else hits[2:25]
    if not top:
        return int(round(TAG_SHARE[TAG_GROUP[position]] * cap_for(league, league.season) * 0.6))
    return int(round(sum(top) / len(top)))


def option_contract(league, c, salary):
    """Exercise a fifth-year option: one more year at the option salary, fully
    guaranteed (2020 CBA)."""
    season = c["option"]["season"]
    c["years"].append({"season": season, "base": int(salary), "bonus": 0, "gtd": int(salary)})
    c["value"] += int(salary)
    c["guaranteed"] += int(salary)
    c["apy"] = int(round(c["value"] / len(c["years"])))
    c["option"]["salary"] = int(salary)
    c["option"]["exercised"] = True
    return c


# ---------------------------------------------------------------------------
# New league year and audits
# ---------------------------------------------------------------------------

def start_league_year(league):
    """A new league year (league.season already advanced): set the cap, carry
    over last year's unused space, and return the contracts that ran out
    {player id: old contract} (they're removed). Practice squad deals end too."""
    ensure(league)
    season = league.season
    set_cap(league, season)
    expired = {}
    for t in league.teams:
        prev = season - 1
        if prev in league.cap_history or league.contract_log:
            room = team_cap(league, t.id, prev, top51=False)["room"]
            if room > 0:
                league.cap_carry.setdefault(t.id, {})[season] = room
    for pid, c in list(league.contracts.items()):
        if last_season(c) is None or last_season(c) < season:
            expired[pid] = league.contracts.pop(pid)
    return expired


def audit(league, season=None, top51=None):
    """Teams over the cap: [(team id, room $K)] (should always be empty for AI teams)."""
    out = []
    for t in league.teams:
        room = cap_room(league, t.id, season, top51)
        if room < 0:
            out.append((t.id, room))
    return out


def missing_contracts(league):
    """Players on a team without a contract (should be none once wired in)."""
    out = []
    for pid, tid in list(league.rosters.items()) + list(getattr(league, "practice", {}).items()):
        c = league.contracts.get(pid)
        if c is None or c["team"] != tid:
            out.append(pid)
    for pid, r in getattr(league, "reserve", {}).items():
        c = league.contracts.get(pid)
        if c is None or c["team"] != r["team"]:
            out.append(pid)
    return out
