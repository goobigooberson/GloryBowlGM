# Real NFL trades, for the player trade system (Oct 23, trades session).
# All local nflverse data (trades, players, OverTheCap contracts, draft picks).
# Writes real_trades.json next to this file.
#   python docs/research/trade_research.py
# What it measures, league years 2013-2025 (the first full years of the 2011 CBA's rules
# and its deadline; 2026 is cut off in April):
# - trades a league year, split by phase (league year start to the draft, draft days,
#   after the draft to camp, camp and preseason, the season up to the deadline) and by week
#   of the season (the deadline rush)
# - what's in them: picks only, players for picks, players for players, both
# - who gets traded: position (vs his share of rosters), age, contract size (share of the
#   cap a year, OverTheCap), "stars" (a top contract at his position, or a recent 1st-rounder)
# - what comes back: for players traded for picks only, the best pick returned by his
#   contract size and age, and the Jimmy Johnson chart value of the whole return
# - how far out traded future picks are (1, 2 or 3 drafts away)
# - how many teams trade, and how many deals a team makes a year (spread)
import csv, gzip, json, statistics as st
from collections import defaultdict, Counter
from datetime import date, timedelta
from pathlib import Path

N = Path("tools/data/nflverse")
OUT = Path(__file__).parent / "real_trades.json"
ALIAS = {"OAK": "LV", "LVR": "LV", "SDG": "LAC", "SD": "LAC", "STL": "LA", "LAR": "LA", "RAM": "LA", "GNB": "GB",
         "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF", "TAM": "TB"}
GRP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "OT": "OL", "G": "OL", "OG": "OL",
       "C": "OL", "OL": "OL", "DE": "EDGE", "OLB": "LB", "DT": "DL", "NT": "DL", "DL": "DL", "LB": "LB",
       "ILB": "LB", "MLB": "LB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB", "SAF": "DB",
       "K": "K/P/LS", "P": "K/P/LS", "LS": "K/P/LS"}
# Key dates (real): new league year, draft (first day; 3 days), week 1 kickoff, trade deadline.
DATES = {
    2013: ("2013-03-12", "2013-04-25", "2013-09-05", "2013-10-29"),
    2014: ("2014-03-11", "2014-05-08", "2014-09-04", "2014-10-28"),
    2015: ("2015-03-10", "2015-04-30", "2015-09-10", "2015-11-03"),
    2016: ("2016-03-09", "2016-04-28", "2016-09-08", "2016-11-01"),
    2017: ("2017-03-09", "2017-04-27", "2017-09-07", "2017-10-31"),
    2018: ("2018-03-14", "2018-04-26", "2018-09-06", "2018-10-30"),
    2019: ("2019-03-13", "2019-04-25", "2019-09-05", "2019-10-29"),
    2020: ("2020-03-18", "2020-04-23", "2020-09-10", "2020-11-03"),
    2021: ("2021-03-17", "2021-04-29", "2021-09-09", "2021-11-02"),
    2022: ("2022-03-16", "2022-04-28", "2022-09-08", "2022-11-01"),
    2023: ("2023-03-15", "2023-04-27", "2023-09-07", "2023-10-31"),
    2024: ("2024-03-13", "2024-04-25", "2024-09-05", "2024-11-05"),
    2025: ("2025-03-12", "2025-04-24", "2025-09-04", "2025-11-04"),
    2026: ("2026-03-11", "2026-04-23", "2026-09-10", "2026-11-03"),
}
YEARS = range(2013, 2026)
CAMP_OPENS = (7, 22)     # month, day: veterans report about then
JJ = [(1, 3000), (2, 2600), (3, 2200), (4, 1800), (5, 1700), (6, 1600), (7, 1500), (8, 1400), (9, 1350),
      (10, 1300), (16, 1000), (20, 850), (32, 590), (33, 580), (48, 420), (60, 300), (64, 270), (96, 116),
      (100, 100), (128, 43), (160, 27.4), (192, 15.2), (224, 3.6), (262, 1.0)]


def jj(pick):
    for (x0, y0), (x1, y1) in zip(JJ, JJ[1:]):
        if x0 <= pick <= x1:
            return y0 + (y1 - y0) * (pick - x0) / (x1 - x0)
    return 1.0


def round_value(rnd, years_out):
    """Chart value of a pick known only by round: the middle of the round, a future pick
    valued as the middle of its round (no discount here; the game's discount is its own)."""
    mid = (int(rnd) - 1) * 32 + 16
    return jj(mid)


def d(s):
    return date.fromisoformat(s)


def rows(p):
    return list(csv.DictReader(gzip.open(N / p, "rt", encoding="utf-8")))


def league_year(day):
    """The league year a date falls in (from its new league year to the next)."""
    for y in sorted(DATES, reverse=True):
        if day >= d(DATES[y][0]):
            return y
    return None


def phase(day, y):
    ly, draft, kick, dead = (d(x) for x in DATES[y])
    if day < draft:
        return "1 league year to draft"
    if day <= draft + timedelta(days=3):
        return "2 draft"
    if day < date(y, *CAMP_OPENS):
        return "3 after draft to camp"
    if day < kick:
        return "4 camp and preseason"
    if day <= dead:
        return "5 season to deadline"
    return "6 after deadline"


trades = rows("trades/trades.csv.gz")
players = {r["pfr_id"]: r for r in rows("players/players.csv.gz") if r["pfr_id"]}
by_otc = defaultdict(list)
for c in rows("contracts/historical_contracts.csv.gz"):
    if c["year_signed"] not in ("", "NA") and c["apy_cap_pct"] not in ("", "NA"):
        by_otc[c["otc_id"]].append(c)
picks = {(int(r["season"]), int(r["pick"])): r for r in rows("draft_picks/draft_picks.csv.gz")}


def contract_at(pl, y):
    """(share of the cap a year, years left) of the deal he was on in league year y, or None."""
    if not pl or not pl.get("otc_id"):
        return None
    best = None
    for c in by_otc.get(pl["otc_id"], ()):
        s, n = int(c["year_signed"]), int(float(c["years"])) if c["years"] not in ("", "NA") else 1
        if s <= y < s + max(1, n) and (best is None or s > int(best["year_signed"])):
            best = c
    if not best:
        return None
    return float(best["apy_cap_pct"]), int(best["year_signed"]) + (int(float(best["years"])) if best["years"] not in ("", "NA") else 1) - y


def age_at(pl, day):
    b = pl.get("birth_date") if pl else None
    if not b or b == "NA":
        return None
    b = d(b)
    return day.year - b.year - ((day.month, day.day) < (b.month, b.day))


deals = defaultdict(list)
for t in trades:
    deals[t["trade_id"]].append(t)

per_year = defaultdict(Counter)
phase_count = defaultdict(Counter)
week_count = defaultdict(Counter)
kinds = defaultdict(Counter)
pos_traded = Counter()
age_traded = []
pos_age = defaultdict(list)
shares = []
stars = defaultdict(int)
first_rounders = defaultdict(int)
team_deals = defaultdict(Counter)
years_out = Counter()
returns = []          # (cap share, age, best pick round, chart value of the return, phase)
players_per_deal = []
multi_team = 0
for tid, ts in deals.items():
    day = d(ts[0]["trade_date"])
    y = league_year(day)
    if y not in YEARS:
        continue
    teams = sorted(set(ALIAS.get(t["gave"], t["gave"]) for t in ts) | set(ALIAS.get(t["received"], t["received"]) for t in ts))
    if len(teams) > 2:
        multi_team += 1
    ph = phase(day, y)
    # A pick row also names the player later drafted with it (pfr_id): only rows without a pick are players.
    pl_rows = [t for t in ts if t["pfr_id"] and t["pick_season"] in ("", "NA")]
    pk_rows = [t for t in ts if t["pick_season"] not in ("", "NA")]
    # Only real players (some deals list "future considerations" etc. as nothing)
    side_players = defaultdict(list)
    side_picks = defaultdict(list)
    for t in pl_rows:
        side_players[ALIAS.get(t["gave"], t["gave"])].append(t)
    for t in pk_rows:
        side_picks[ALIAS.get(t["gave"], t["gave"])].append(t)
        yo = int(t["pick_season"]) - (y if day < d(DATES[y][1]) + timedelta(days=3) else y + 1)
        years_out[yo] += 1
    if not pl_rows and not pk_rows:
        continue
    if not pl_rows:
        kind = "picks only"
    elif not pk_rows:
        kind = "players for players" if len(side_players) >= 2 else "player for nothing"
    else:
        both = [tm for tm in teams if side_players.get(tm)]
        if len(both) >= 2:
            kind = "players both ways (+ picks)"
        else:
            kind = "players for picks"
    kinds[y][kind] += 1
    per_year[y]["all"] += 1
    if pl_rows:
        per_year[y]["with players"] += 1
        phase_count[y][ph] += 1
        players_per_deal.append(len(pl_rows))
        for tm in teams:
            team_deals[y][tm] += 1
    if ph.startswith("5"):
        kick = d(DATES[y][2])
        wk = (day - kick).days // 7 + 1
        week_count[y][max(0, wk)] += 1 if pl_rows else 0
    for t in pl_rows:
        pl = players.get(t["pfr_id"])
        g = GRP.get((pl or {}).get("position", ""), "?")
        pos_traded[g] += 1
        a = age_at(pl, day)
        if a:
            age_traded.append(a)
            pos_age[g].append(a)
        c = contract_at(pl, y)
        if c:
            shares.append(c[0])
            if c[0] >= 0.08:
                stars[y] += 1
        if pl and pl.get("draft_round") == "1" and pl.get("draft_year") not in ("", "NA") \
                and y - int(pl["draft_year"]) <= 4:
            first_rounders[y] += 1
    # Returns: exactly one player one way, only picks the other way.
    if len(pl_rows) == 1 and len(side_players) == 1:
        giver = ALIAS.get(pl_rows[0]["gave"], pl_rows[0]["gave"])
        known = [t for t in pk_rows if t["pick_round"].isdigit()]
        back = [t for t in known if ALIAS.get(t["gave"], t["gave"]) != giver]
        sent = [t for t in known if ALIAS.get(t["gave"], t["gave"]) == giver]
        if back:
            pl = players.get(pl_rows[0]["pfr_id"])
            c = contract_at(pl, y)
            a = age_at(pl, day)
            val = sum(round_value(t["pick_round"], 0) for t in back) - sum(round_value(t["pick_round"], 0) for t in sent)
            best = min(int(t["pick_round"]) for t in back)
            returns.append({"share": c[0] if c else None, "age": a, "best_round": best, "chart": round(val),
                            "pos": GRP.get((pl or {}).get("position", ""), "?"), "phase": ph,
                            "swap": bool(sent)})

ny = len(YEARS)
out = {"note": "nflverse trades, league years 2013-2025 (March to March). A deal = one trade_id. 'with players' "
               "= at least one player moved. Phases by real dates (league year, draft, camp ~Jul 22, kickoff, "
               "deadline).",
       "years": [min(YEARS), max(YEARS)]}
out["deals_per_year"] = {k: round(sum(per_year[y][k] for y in YEARS) / ny, 1) for k in ("all", "with players")}
out["deals_with_players_by_year"] = {y: per_year[y]["with players"] for y in YEARS}
out["deals_with_players_sd"] = round(st.pstdev([per_year[y]["with players"] for y in YEARS]), 1)
phases = sorted({p for y in YEARS for p in phase_count[y]})
out["player_deals_by_phase"] = {p: round(sum(phase_count[y][p] for y in YEARS) / ny, 1) for p in phases}
recent = range(2021, 2026)
out["player_deals_by_phase_2021_25"] = {p: round(sum(phase_count[y][p] for y in recent) / len(recent), 1)
                                        for p in phases}
weeks = sorted({w for y in YEARS for w in week_count[y]})
out["player_deals_by_week_of_season_2021_25"] = {w: round(sum(week_count[y][w] for y in recent) / len(recent), 1)
                                                for w in weeks}
kk = sorted({k for y in YEARS for k in kinds[y]})
out["deal_kinds_per_year"] = {k: round(sum(kinds[y][k] for y in YEARS) / ny, 1) for k in kk}
tot = sum(pos_traded.values())
out["players_traded_per_year"] = round(tot / ny, 1)
out["position_share_of_players_traded"] = {g: round(n / tot, 3) for g, n in pos_traded.most_common()}
out["age_traded"] = {"mean": round(st.mean(age_traded), 1), "median": st.median(age_traded),
                     "share_by_age": {a: round(n / len(age_traded), 3) for a, n in sorted(Counter(
                         min(33, max(22, a)) for a in age_traded).items())}}
out["age_by_position"] = {g: round(st.mean(v), 1) for g, v in pos_age.items() if len(v) > 20}
qs = sorted(shares)
out["contract_share_of_cap"] = {"n_with_contract": len(qs), "median": round(st.median(qs), 4),
                                "p75": round(qs[int(0.75 * len(qs))], 4), "p90": round(qs[int(0.9 * len(qs))], 4),
                                "p97": round(qs[int(0.97 * len(qs))], 4),
                                "share_under_1pct": round(sum(1 for s in qs if s < 0.01) / len(qs), 3)}
out["stars_traded_per_year"] = {"contract_8pct_plus": round(sum(stars[y] for y in YEARS) / ny, 1),
                                "by_year": {y: stars[y] for y in YEARS},
                                "recent_first_rounders_(<=4_seasons)": round(sum(first_rounders[y] for y in YEARS) / ny, 1)}
counts = [team_deals[y].get(tm, 0) for y in YEARS for tm in set().union(*[team_deals[x] for x in YEARS])]
out["player_deals_per_team_year"] = {"mean": round(st.mean(counts), 2), "sd": round(st.pstdev(counts), 2),
                                     "share_zero": round(sum(1 for c in counts if c == 0) / len(counts), 3),
                                     "max": max(counts)}
out["players_per_deal"] = round(st.mean(players_per_deal), 2)
out["future_pick_years_out"] = {k: years_out[k] for k in sorted(years_out)}
out["three_team_deals"] = multi_team


def summarize(rs):
    if not rs:
        return None
    return {"n": len(rs), "best_round": dict(sorted(Counter(r["best_round"] for r in rs).items())),
            "chart_median": st.median(r["chart"] for r in rs),
            "chart_p25": sorted(r["chart"] for r in rs)[len(rs) // 4],
            "chart_p75": sorted(r["chart"] for r in rs)[3 * len(rs) // 4]}


band = lambda s: ("unknown" if s is None else "under 2%" if s < 0.02 else "2-5%" if s < 0.05 else
                  "5-10%" if s < 0.10 else "10%+")
out["returns_player_for_picks"] = {b: summarize([r for r in returns if band(r["share"]) == b])
                                   for b in ("under 2%", "2-5%", "5-10%", "10%+", "unknown")}
out["returns_by_age"] = {a: summarize([r for r in returns if r["age"] and lo <= r["age"] <= hi])
                         for a, (lo, hi) in {"22-25": (22, 25), "26-28": (26, 28), "29-31": (29, 31),
                                             "32+": (32, 45)}.items()}
out["returns_deadline_vs_offseason"] = {
    "season": summarize([r for r in returns if r["phase"].startswith("5")]),
    "offseason": summarize([r for r in returns if not r["phase"].startswith("5")])}
# Future picks, priced by the market: draft-time pick-only deals where one side's return is
# current-year picks (numbers known) plus exactly one next-year pick, the other side only
# current-year picks. The future pick's implied chart value = what the other side gave minus
# the current picks that came with it, against the middle of its round (Jimmy Johnson chart).
implied = defaultdict(list)
for tid, ts in deals.items():
    day = d(ts[0]["trade_date"])
    y = league_year(day)
    if y not in YEARS or phase(day, y) != "2 draft" or any(t["pfr_id"] and t["pick_season"] in ("", "NA") for t in ts):
        continue
    side = defaultdict(list)
    for t in ts:
        if t["pick_season"] not in ("", "NA"):
            side[ALIAS.get(t["gave"], t["gave"])].append(t)
    if len(side) != 2:
        continue
    (a, ra), (b, rb) = side.items()
    for giver, rows_, other in ((a, ra, rb), (b, rb, ra)):
        fut = [t for t in rows_ if int(t["pick_season"]) == y + 1]
        cur = [t for t in rows_ if int(t["pick_season"]) == y]
        if len(fut) != 1 or len(cur) + 1 != len(rows_) or not fut[0]["pick_round"].isdigit():
            continue
        if any(int(t["pick_season"]) != y or t["pick_number"] in ("", "NA") for t in other):
            continue
        if any(t["pick_number"] in ("", "NA") for t in cur):
            continue
        got = sum(jj(int(t["pick_number"])) for t in other)
        gave_now = sum(jj(int(t["pick_number"])) for t in cur)
        mid = round_value(fut[0]["pick_round"], 1)
        implied[int(fut[0]["pick_round"])].append((got - gave_now) / mid)
out["future_pick_implied_share_of_mid_round"] = {
    r: {"n": len(v), "median": round(st.median(v), 2), "p25": round(sorted(v)[len(v) // 4], 2),
        "p75": round(sorted(v)[3 * len(v) // 4], 2)} for r, v in sorted(implied.items()) if len(v) >= 3}
# In-season deals by week before the deadline (0 = the deadline's own week: the 7 days up to it).
before = defaultdict(Counter)
for tid, ts in deals.items():
    day = d(ts[0]["trade_date"])
    y = league_year(day)
    if y not in YEARS or phase(day, y) != "5 season to deadline":
        continue
    if not any(t["pfr_id"] and t["pick_season"] in ("", "NA") for t in ts):
        continue
    before[y][(d(DATES[y][3]) - day).days // 7] += 1
out["player_deals_by_weeks_before_deadline"] = {
    "2013_25": {w: round(sum(before[y][w] for y in YEARS) / ny, 2) for w in range(0, 10)},
    "2021_25": {w: round(sum(before[y][w] for y in recent) / len(recent), 2) for w in range(0, 10)}}
OUT.write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
