# league_money.py
# Where the salary cap comes from after the last real year (2026). Blake, Oct 24:
# "TV-deal eras" and "mostly market, some buzz".
#
# How the real cap works (research in docs/build-log.md, "Salary cap research"):
# the players get a fixed share of league revenue (about 48%), split 32 ways.
# About two-thirds of the revenue is national TV money, signed in long deals
# (8-11 years). So the cap grows steadily inside a TV era (the deals' yearly
# raises plus local revenue: about 7% a year), jumps when new TV money arrives
# (1998 +26%, 2006 +19%, 2023-24), and drops only in a rare shock (2021, COVID:
# -8%, with the loss paid back over the next years) or stays flat after a hard
# labor fight (2011-13). TV ratings matter through the price of the next deal;
# what the players on the field are rated plays no part.
#
# Rules only; contracts.set_cap asks this file for each new league year's cap.
# Everything is fixed one league year ahead, as in the real NFL (teams get the
# next year's projection in December): when league year S starts, its cap is
# set and next year's projection is made, so AI teams plan with it. The real
# NFL's projection misses by a little; so does this one (PROJECTION_SD), except
# when a shock is announced.
#
# Saved on the league as league.tv (database MONEY_INFO key "tv"):
#   {"deals": [{"start", "end", "signed", "jump", "market", "buzz", "real"}, ...],
#    "labor": [{"start", "end", "signed", "kind", "real"}, ...],
#    "shocks": {season: growth that year},
#    "buzz":   {season: {"parity", "close", "drama", "stars", "score"}},
#    "proj":   {season: projected cap ($K)}}

import random
import statistics

# ---- Knobs ---------------------------------------------------------------------
# The real eras: TV deals by first and last season (the current deals can be ended
# after the 2029 season, and the league is expected to do it), labor deals (CBAs).
REAL_TV_DEALS = [(1998, 2005), (2006, 2013), (2014, 2022), (2023, 2029)]
REAL_LABOR = [(2011, 2020), (2021, 2030)]
# A normal year's growth inside a TV era: real 2000-05, 2007-09, 2015-20, 2025-26
# averaged 6.8% with a spread of about 1.2%.
BASE_GROWTH = (0.068, 0.013)
DEAL_YEARS = (7, 11)            # a new TV deal runs this many seasons (real 8, 8, 9, 7 to the opt-out)
DEAL_LEAD = (1, 2)              # signed this many league years before its first season
# The extra growth new TV money brings, on top of a normal year (average, spread,
# lowest, highest). Real: 1998 about +19 points, 2006 about +12 (with a new CBA),
# 2014 about +1, 2023-25 about +10 over three years. A deal can come in below the
# old one's pace (lowest) if the market sours.
DEAL_JUMP = (0.09, 0.07, -0.04, 0.30)
DEAL_SPLIT = (0.7, 0.3)         # the extra arrives over the deal's first two seasons, mostly in
                                # the first (real 1998 +26% then +9%, 2006 +19% then +7%)
# League buzz (Blake: "mostly market, some buzz"): the average buzz score of the
# seasons since the last deal was signed (up to BUZZ_SEASONS) moves the new deal's
# extra by this much per point. A typical buzz average spreads about +/-0.5, so
# buzz moves a deal about +/-2 points against the market's +/-6.
BUZZ_K = 0.04
BUZZ_SEASONS = 4
LABOR_YEARS = 10                # a labor deal (CBA) runs this many seasons (real 2011-20, 2021-30)
# How the next labor deal goes, and what it does to the growth of its first seasons.
# Real: 2011 (owners won a bigger share; -2.4%, +0.5%, +2.0%, about 9, 6 and 5 points
# below normal), 2006 (players' share went up; about +12 points with new TV money),
# 2020 (no change to the growth).
LABOR_ODDS = (("owners", 0.35), ("smooth", 0.45), ("players", 0.20))
LABOR_EFFECT = {"owners": (-0.08, -0.05, -0.03), "smooth": (), "players": (0.05,)}
# A shock (a pandemic, a recession): this chance a year, announced the season
# before (real: the 2021 drop was known in the summer of 2020). The cap falls by
# this much, and the lost growth comes back over the next two seasons.
SHOCK_CHANCE = 0.02             # (one real one in 32 capped years; the true rate can't be pinned down)
SHOCK_GROWTH = (-0.09, -0.04)
SHOCK_REBOUND = (0.5, 0.3)
PROJECTION_SD = 0.006           # how far the final cap lands from last year's projection
FIRST_MODEL_SEASON = 2027       # every cap before this is the real one
# The buzz score, from the season's own records (Blake: "how the ratings for the
# league are"): closer races (point differential spread across teams, lower is
# better), one-score games, close playoff games, and big individual seasons. Each
# is measured against the game's normal seasons (average, spread); the score is
# their average, scaled so a typical season spreads about +/-1. Measured Oct 24 on 12
# full seasons of generated leagues (scratchpad buzz_sample.py): point-differential
# spread 4.70 (+/-0.74; a 6-season startup-draft league ran 5.1-6.2, average 5.5, so
# the middle, 5.3, is used), one-score games 0.50 (+/-0.04), close playoff games 0.51
# (+/-0.16), big seasons 7.8 (+/-4.3, one season had 19).
BUZZ_PARTS = {"parity": (5.3, 0.7), "close": (0.49, 0.04), "drama": (0.5, 0.15), "stars": (7.5, 3.5)}
BUZZ_SCALE = 2.0
# A season that's news: 4,500 passing yards or 40 touchdown passes, 1,600 rushing
# yards, 1,500 receiving yards, 17 sacks, 9 interceptions.
STAR_SEASON = (("pass_yds", 4500), ("pass_td", 40), ("rush_yds", 1600), ("rec_yds", 1500),
               ("sacks", 17), ("def_int", 9))
# What a TV deal is worth a year, for the news: about this many times the
# league's total cap in its first season (real: the 2014 deals ~$6.4B a year at a
# $133M cap; the 2023 deals ~$10-11B a year at $224.8M: 1.5x).
TV_VALUE_PER_CAP = 1.5


def ensure(league):
    """The league's TV and labor records (leagues and saves from before Oct 24 get the
    real ones)."""
    tv = getattr(league, "tv", None)
    if not tv:
        tv = {}
        league.tv = tv
    tv.setdefault("deals", [{"start": a, "end": b, "real": True} for a, b in REAL_TV_DEALS])
    tv.setdefault("labor", [{"start": a, "end": b, "real": True} for a, b in REAL_LABOR])
    for key in ("shocks", "buzz", "proj"):
        tv.setdefault(key, {})
    return tv


def _rng(league, *parts):
    return random.Random("tv-" + "-".join(str(x) for x in (league.settings.get("salt", ""),) + parts))


# ---------------------------------------------------------------------------
# What the eras do to one season's growth
# ---------------------------------------------------------------------------

def _deal_extra(tv, season):
    for d in tv["deals"]:
        if d.get("real") or "jump" not in d:
            continue
        k = season - d["start"]
        if 0 <= k < len(DEAL_SPLIT):
            return d["jump"] * DEAL_SPLIT[k]
    return 0.0


def _labor_extra(tv, season):
    for d in tv["labor"]:
        if d.get("real"):
            continue
        k = season - d["start"]
        eff = LABOR_EFFECT.get(d["kind"], ())
        if 0 <= k < len(eff):
            return eff[k]
    return 0.0


def _shock_extra(tv, season):
    """A shock year replaces the normal growth (None if no shock); the two years after
    it get part of the lost growth back."""
    extra = 0.0
    for k, share in enumerate(SHOCK_REBOUND, start=1):
        g = tv["shocks"].get(season - k)
        if g is not None:
            extra += (BASE_GROWTH[0] - g) * share
    return tv["shocks"].get(season), extra


def growth(league, season):
    """This season's cap growth over last season's (the same for a league and season
    every time it's asked, given what has been decided)."""
    tv = ensure(league)
    shock, rebound = _shock_extra(tv, season)
    if shock is not None:
        return shock
    base = _rng(league, "base", season).gauss(*BASE_GROWTH)
    return base + _deal_extra(tv, season) + _labor_extra(tv, season) + rebound


def expected_growth(league, season):
    """Growth for planning further ahead than next year: the normal pace plus
    whatever has already been signed or announced (no luck)."""
    tv = ensure(league)
    shock, rebound = _shock_extra(tv, season)
    if shock is not None:
        return shock
    return BASE_GROWTH[0] + _deal_extra(tv, season) + _labor_extra(tv, season) + rebound


# ---------------------------------------------------------------------------
# The league year: deals signed, labor deals, shocks announced
# ---------------------------------------------------------------------------

def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def buzz_average(league, season):
    """The average buzz of the seasons since the last TV deal was signed, up to
    BUZZ_SEASONS of them, before this league year (0 when there are none yet)."""
    tv = ensure(league)
    signed = max((d.get("signed", d["start"] - 1) for d in tv["deals"]), default=0)
    seasons = sorted(s for s in tv["buzz"] if signed <= s < season)[-BUZZ_SEASONS:]
    return statistics.mean(tv["buzz"][s]["score"] for s in seasons) if seasons else 0.0


def _new_deal(league, season):
    """The next TV deal, signed in league year `season` if it's due."""
    tv = ensure(league)
    last = max(tv["deals"], key=lambda d: d["start"])
    start = last["end"] + 1
    if season >= start:
        # The signing window passed without a deal (a save from before Oct 24 that was
        # already past it): the old deals run one more season and the new ones are signed now.
        last["end"] = season
        start = season + 1
    lead = _rng(league, "lead", start).randint(*DEAL_LEAD)
    if season < start - lead:
        return None
    rng = _rng(league, "deal", start)
    market = rng.gauss(0, 1)
    buzz = buzz_average(league, season)
    mean, sd, lo, hi = DEAL_JUMP
    jump = _clip(mean + sd * market + BUZZ_K * buzz, lo, hi)
    deal = {"start": start, "end": start + rng.randint(*DEAL_YEARS) - 1, "signed": season,
            "jump": round(jump, 4), "market": round(market, 3), "buzz": round(buzz, 3)}
    tv["deals"].append(deal)
    return deal


def _new_labor_deal(league, season):
    """The next labor deal, agreed in the league year before it starts."""
    tv = ensure(league)
    last = max(tv["labor"], key=lambda d: d["start"])
    start = last["end"] + 1
    if season != start - 1:
        return None
    rng = _rng(league, "labor", start)
    r, kind = rng.random(), LABOR_ODDS[-1][0]
    for k, p in LABOR_ODDS:
        if r < p:
            kind = k
            break
        r -= p
    deal = {"start": start, "end": start + LABOR_YEARS - 1, "signed": season, "kind": kind}
    tv["labor"].append(deal)
    return deal


def league_year(league, season, prev_cap):
    """League year `season` begins: its cap ($K) from last year's (prev_cap), then
    this league year's business (a TV deal or labor deal signed, a shock announced
    for next season), then next season's projection. Called by contracts.set_cap
    once per league year, for seasons after the last real cap."""
    tv = ensure(league)
    proj = tv["proj"].get(season)
    if proj is None:
        cap = prev_cap * (1 + growth(league, season))
    else:
        cap = proj * (1 + _rng(league, "miss", season).gauss(0, PROJECTION_SD))
    cap = round(cap)
    _new_labor_deal(league, season)
    deal = _new_deal(league, season)
    if deal:
        # Its yearly value as announced (from the cap expected in its first season).
        deal["value_k"] = round(tv_value_per_year(projected(league, deal["start"], season, cap)))
    nxt = season + 1
    if nxt not in tv["shocks"] and _rng(league, "shock", nxt).random() < SHOCK_CHANCE:
        tv["shocks"][nxt] = round(_rng(league, "shock-size", nxt).uniform(*SHOCK_GROWTH), 4)
    tv["proj"][nxt] = round(cap * (1 + growth(league, nxt)))
    return cap


def projected(league, season, known_season, known_cap):
    """The cap a team can plan on for a future season, from the last one fixed
    (known_season, known_cap): next year's projection, then the expected pace."""
    tv = ensure(league)
    cap, s = known_cap, known_season
    if s + 1 in tv["proj"] and season > s:
        cap, s = tv["proj"][s + 1], s + 1
    while s < season:
        s += 1
        cap *= 1 + expected_growth(league, s)
    return round(cap)


# ---------------------------------------------------------------------------
# League buzz, recorded when a season ends
# ---------------------------------------------------------------------------

def _margin(g):
    return abs((g.get("home_score") or 0) - (g.get("away_score") or 0))


def record_buzz(league, season_lines):
    """The season just played, as the TV audience saw it (season.begin_offseason
    calls this before the season's games are cleared). season_lines: the season's
    archived player lines (stats.season_lines)."""
    tv = ensure(league)
    games = [g for g in league.schedule if g.get("played")]
    if not games:
        return None
    diff = {}
    for g in games:
        for tid, sign in ((g["home"], 1), (g["away"], -1)):
            d = diff.setdefault(tid, [0, 0])
            d[0] += sign * ((g["home_score"] or 0) - (g["away_score"] or 0))
            d[1] += 1
    per_game = [v[0] / v[1] for v in diff.values() if v[1]]
    parity = statistics.pstdev(per_game) if len(per_game) > 1 else BUZZ_PARTS["parity"][0]
    close = sum(1 for g in games if _margin(g) <= 8 or g.get("overtime")) / len(games)
    po = [g for g in league.playoffs if g.get("played")]
    drama = (sum(1 for g in po if _margin(g) <= 8 or g.get("overtime")) / len(po)) if po else BUZZ_PARTS["drama"][0]
    stars = sum(1 for r in season_lines if r["phase"] == "regular"
                and any(r["stats"].get(k, 0) >= v for k, v in STAR_SEASON))
    raw = {"parity": round(parity, 3), "close": round(close, 3), "drama": round(drama, 3), "stars": stars}
    zs = [(BUZZ_PARTS["parity"][0] - parity) / BUZZ_PARTS["parity"][1]]
    zs += [(raw[k] - BUZZ_PARTS[k][0]) / BUZZ_PARTS[k][1] for k in ("close", "drama", "stars")]
    raw["score"] = round(_clip(BUZZ_SCALE * statistics.mean(_clip(z, -2.5, 2.5) for z in zs), -3, 3), 3)
    tv["buzz"][league.season] = raw
    return raw


# ---------------------------------------------------------------------------
# For the screens and the news
# ---------------------------------------------------------------------------

def current_deal(league, season):
    tv = ensure(league)
    deals = [d for d in tv["deals"] if d["start"] <= season]
    return max(deals, key=lambda d: d["start"]) if deals else None


def outlook(league):
    """The league's money outlook for the screens: {"deal_end", "next_deal" (start,
    end) or None, "labor_end", "next_season", "next_cap", "next_change", "shock"}."""
    from . import contracts as C
    tv = ensure(league)
    s = league.season
    cur = current_deal(league, s)
    nxt = next((d for d in tv["deals"] if d["start"] > s), None)
    labor = max((d for d in tv["labor"] if d["start"] <= s), key=lambda d: d["start"], default=None)
    cap, next_cap = C.cap_for(league, s), C.cap_for(league, s + 1)
    return {"deal_end": cur["end"] if cur else None, "next_deal": (nxt["start"], nxt["end"]) if nxt else None,
            "labor_end": labor["end"] if labor else None, "next_season": s + 1, "next_cap": next_cap,
            "next_change": next_cap / cap - 1, "shock": (s + 1) in tv["shocks"]}


def tv_value_per_year(cap_k):
    """A TV deal's yearly value ($K), from the cap in its first season."""
    return TV_VALUE_PER_CAP * 32 * cap_k


def buzz_word(score):
    if score >= 1.0:
        return "booming"
    if score >= 0.35:
        return "strong"
    if score <= -1.0:
        return "slumping"
    if score <= -0.35:
        return "soft"
    return "steady"
