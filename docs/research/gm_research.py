# Real NFL general managers, for the AI GMs (Oct 22, GM side session). Writes real_gm.json.
#   python docs/research/gm_research.py
# Sources:
# - Who ran each team's draft, 2002-2026: Wikipedia's "<team> general managers" navboxes
#   (fetched Oct 22, 2026), turned into draft years below. A GM hired after the draft (or an
#   interim who never ran one) doesn't count until the next draft. Teams without a GM title
#   count their real decision maker (Cincinnati: Mike Brown; Dallas: Jerry Jones; New England
#   2000-23: Belichick).
# - Head coaches: nflverse games (the week-1 coach of each season).
# - Draft-day trades: nflverse trades (same rules as draft_habits.py).
# - Contracts: OverTheCap via nflverse (CSV snapshot May 2022): outside signings vs own players.
# - Dead money and cap left: Spotrac's team cap tables 2013-2025 (scratchpad copy, see
#   SPOTRAC below; saved into real_gm.json so the script runs without it).
# - Restructures: OverTheCap, "Looking at Restructuring NFL Contracts" (June 10, 2021).
import csv, gzip, json, os, statistics as st
from collections import defaultdict, Counter
from pathlib import Path

N = Path("tools/data/nflverse")
OUT = Path(__file__).parent / "real_gm.json"
ALIAS = {"OAK": "LV", "LVR": "LV", "SDG": "LAC", "SD": "LAC", "STL": "LA", "LAR": "LA", "RAM": "LA", "GNB": "GB",
         "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF", "TAM": "TB"}

# (name, first draft run, last draft run). 2026 = still in the job for the 2026 draft.
GMS = {
    "ARI": [("Bob Ferguson", 2002, 2002), ("Rod Graves", 2003, 2012), ("Steve Keim", 2013, 2022), ("Monti Ossenfort", 2023, 2026)],
    "ATL": [("Harold Richardson", 2002, 2002), ("Rich McKay", 2003, 2007), ("Thomas Dimitroff", 2008, 2020), ("Terry Fontenot", 2021, 2025),
            ("Ian Cunningham", 2026, 2026)],
    "BAL": [("Ozzie Newsome", 2002, 2018), ("Eric DeCosta", 2019, 2026)],
    "BUF": [("Tom Donahoe", 2002, 2005), ("Marv Levy", 2006, 2007), ("Russ Brandon", 2008, 2009),
            ("Buddy Nix", 2010, 2012), ("Doug Whaley", 2013, 2016), ("Brandon Beane", 2017, 2026)],
    "CAR": [("Marty Hurney", 2002, 2012), ("Dave Gettleman", 2013, 2017), ("Marty Hurney", 2018, 2020),
            ("Scott Fitterer", 2021, 2023), ("Dan Morgan", 2024, 2026)],
    "CHI": [("Jerry Angelo", 2002, 2011), ("Phil Emery", 2012, 2014), ("Ryan Pace", 2015, 2021),
            ("Ryan Poles", 2022, 2026)],
    "CIN": [("Mike Brown", 2002, 2026)],
    "CLE": [("Butch Davis", 2002, 2004), ("Phil Savage", 2005, 2008), ("George Kokinis", 2009, 2009),
            ("Tom Heckert Jr.", 2010, 2012), ("Michael Lombardi", 2013, 2013), ("Ray Farmer", 2014, 2015),
            ("Sashi Brown", 2016, 2017), ("John Dorsey", 2018, 2019), ("Andrew Berry", 2020, 2026)],
    "DAL": [("Jerry Jones", 2002, 2026)],
    "DEN": [("Ted Sundquist", 2002, 2007), ("Jim Goodman", 2008, 2008), ("Brian Xanders", 2009, 2010),
            ("John Elway", 2011, 2020), ("George Paton", 2021, 2026)],
    "DET": [("Matt Millen", 2002, 2008), ("Martin Mayhew", 2009, 2015), ("Bob Quinn", 2016, 2020),
            ("Brad Holmes", 2021, 2026)],
    "GB": [("Mike Sherman", 2002, 2004), ("Ted Thompson", 2005, 2017), ("Brian Gutekunst", 2018, 2026)],
    "HOU": [("Charley Casserly", 2002, 2005), ("Rick Smith", 2006, 2017), ("Brian Gaine", 2018, 2019),
            ("Bill O'Brien", 2020, 2020), ("Nick Caserio", 2021, 2026)],
    "IND": [("Bill Polian", 2002, 2008), ("Chris Polian", 2009, 2011), ("Ryan Grigson", 2012, 2016),
            ("Chris Ballard", 2017, 2026)],
    "JAX": [("Tom Coughlin", 2002, 2002), ("James Harris", 2003, 2008), ("Gene Smith", 2009, 2012),
            ("David Caldwell", 2013, 2020), ("Trent Baalke", 2021, 2024), ("James Gladstone", 2025, 2026)],
    "KC": [("Carl Peterson", 2002, 2008), ("Scott Pioli", 2009, 2012), ("John Dorsey", 2013, 2016),
           ("Brett Veach", 2017, 2026)],
    "LA": [("Charley Armey", 2002, 2005), ("Jay Zygmunt", 2006, 2008), ("Billy Devaney", 2009, 2011),
           ("Les Snead", 2012, 2026)],
    "LAC": [("John Butler", 2002, 2002), ("A. J. Smith", 2003, 2012), ("Tom Telesco", 2013, 2023),
            ("Joe Hortiz", 2024, 2026)],
    "LV": [("Al Davis", 2002, 2011), ("Reggie McKenzie", 2012, 2018), ("Mike Mayock", 2019, 2021),
           ("Dave Ziegler", 2022, 2023), ("Tom Telesco", 2024, 2024), ("John Spytek", 2025, 2026)],
    "MIA": [("Rick Spielman", 2004, 2004), ("Randy Mueller", 2005, 2007), ("Jeff Ireland", 2008, 2013),
            ("Dennis Hickey", 2014, 2015), ("Chris Grier", 2016, 2025), ("Jon-Eric Sullivan", 2026, 2026)],
    "MIN": [("Rob Brzezinski", 2002, 2005), ("Fran Foley", 2006, 2006), ("Rick Spielman", 2007, 2021),
            ("Kwesi Adofo-Mensah", 2022, 2025), ("Nolan Teasley", 2026, 2026)],
    "NE": [("Bill Belichick", 2002, 2023), ("Eliot Wolf", 2024, 2026)],
    "NO": [("Randy Mueller", 2002, 2002), ("Mickey Loomis", 2003, 2026)],
    "NYG": [("Ernie Accorsi", 2002, 2006), ("Jerry Reese", 2007, 2017), ("Dave Gettleman", 2018, 2021),
            ("Joe Schoen", 2022, 2026)],
    "NYJ": [("Terry Bradway", 2002, 2005), ("Mike Tannenbaum", 2006, 2012), ("John Idzik Jr.", 2013, 2014),
            ("Mike Maccagnan", 2015, 2019), ("Joe Douglas", 2020, 2024), ("Darren Mougey", 2025, 2026)],
    "PHI": [("Andy Reid", 2002, 2005), ("Tom Heckert Jr.", 2006, 2009), ("Howie Roseman", 2010, 2014),
            ("Chip Kelly", 2015, 2015), ("Howie Roseman", 2016, 2026)],
    "PIT": [("Kevin Colbert", 2002, 2021), ("Omar Khan", 2022, 2026)],
    "SEA": [("Mike Holmgren", 2002, 2002), ("Bob Ferguson", 2003, 2004), ("Tim Ruskell", 2005, 2009),
            ("John Schneider", 2010, 2026)],
    "SF": [("Terry Donahue", 2002, 2004), ("Mike Nolan", 2005, 2007), ("Scot McCloughan", 2008, 2009),
           ("Trent Baalke", 2010, 2016), ("John Lynch", 2017, 2026)],
    "TB": [("Rich McKay", 2002, 2003), ("Bruce Allen", 2004, 2008), ("Mark Dominik", 2009, 2013),
           ("Jason Licht", 2014, 2026)],
    "TEN": [("Floyd Reese", 2002, 2006), ("Mike Reinfeldt", 2007, 2011), ("Ruston Webster", 2012, 2015),
            ("Jon Robinson", 2016, 2022), ("Ran Carthon", 2023, 2024), ("Mike Borgonzi", 2025, 2026)],
    "WAS": [("Vinny Cerrato", 2002, 2009), ("Bruce Allen", 2010, 2014), ("Scot McCloughan", 2015, 2016),
            ("Bruce Allen", 2017, 2019), ("Ron Rivera", 2020, 2020), ("Martin Mayhew", 2021, 2023),
            ("Adam Peters", 2024, 2026)],
}
# Miami 2002-03: Rick Spielman ran personnel under Dave Wannstedt (GM title Eddie Jones/Wannstedt).
GMS["MIA"].insert(0, ("Dave Wannstedt", 2002, 2003))
Y0, Y1 = 2002, 2026


def rows(p):
    return list(csv.DictReader(gzip.open(N / p, "rt", encoding="utf-8")))


def corr(a, b):
    if len(a) < 3:
        return float("nan")
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def r2(x):
    return None if x != x else round(x, 2)


# ---- Who ran each draft, and each team's tenures ---------------------------------------------
gm_of = {}            # (team, year) -> tenure id
tenures = []          # dicts: team, name, first, last
for t, lst in GMS.items():
    for name, a, b in lst:
        tid = len(tenures)
        tenures.append({"team": t, "name": name, "first": a, "last": b})
        for y in range(a, b + 1):
            assert (t, y) not in gm_of, (t, y)
            gm_of[(t, y)] = tid
for t in GMS:
    for y in range(Y0, Y1 + 1):
        assert (t, y) in gm_of, (t, y)
out = {"note": "GM = who ran that year's draft (hired after the draft counts from the next one)."}

# ---- Head coaches and records -----------------------------------------------------------------
games = rows("schedules/games.csv.gz")
hc = {}
wins = defaultdict(float)
gp = defaultdict(int)
playoff = set()
for g in games:
    s = int(g["season"])
    for side, opp in (("home", "away"), ("away", "home")):
        t = ALIAS.get(g[f"{side}_team"], g[f"{side}_team"])
        if g["game_type"] == "REG":
            if g["week"] == "1" or (t, s) not in hc:
                hc.setdefault((t, s), g[f"{side}_coach"])
            if g["result"] not in ("", "NA"):
                pts, opts = float(g[f"{side}_score"]), float(g[f"{opp}_score"])
                gp[(t, s)] += 1
                wins[(t, s)] += 1 if pts > opts else 0.5 if pts == opts else 0
        elif g["game_type"] in ("WC", "DIV", "CON", "SB"):
            playoff.add((t, s))

# ---- Turnover ------------------------------------------------------------------------------------
gm_changes, hc_changes, both, gm_only, hc_only = [], [], 0, 0, 0
per_year = {}
firing = defaultdict(lambda: [0, 0])          # (win band, tenure band) -> [changes, chances]
with_hc = [0, 0]                              # GM changes that came with an HC change
hc_with_gm = [0, 0]
first_year_hc = [0, 0]                        # a new GM keeps the head coach he inherits?
for y in range(Y0 + 1, Y1 + 1):
    g = h = 0
    for t in GMS:
        gch = gm_of[(t, y)] != gm_of[(t, y - 1)]
        hch = hc.get((t, y)) != hc.get((t, y - 1))
        g += gch
        h += hch
        both += gch and hch
        with_hc[0] += gch and hch
        with_hc[1] += gch
        hc_with_gm[0] += gch and hch
        hc_with_gm[1] += hch
        # odds of a GM change by last season's wins (per 17) and his tenure before it
        ten = y - tenures[gm_of[(t, y - 1)]]["first"]          # drafts run before this offseason
        w17 = wins[(t, y - 1)] * 17 / max(1, gp[(t, y - 1)])
        wb = "0-4" if w17 < 4.5 else "5-6" if w17 < 6.5 else "7-8" if w17 < 8.5 else "9-10" if w17 < 10.5 else "11+"
        tb = "1-2" if ten <= 2 else "3-5" if ten <= 5 else "6+"
        firing[(wb, tb)][0] += gch
        firing[(wb, tb)][1] += 1
        firing[(wb, "all")][0] += gch
        firing[(wb, "all")][1] += 1
        firing[("playoffs" if (t, y - 1) in playoff else "no playoffs", "all")][0] += gch
        firing[("playoffs" if (t, y - 1) in playoff else "no playoffs", "all")][1] += 1
    per_year[y] = {"gm": g, "hc": h}
    gm_changes.append(g)
    hc_changes.append(h)
# a GM who arrives without an HC change: does he replace the coach within 2 seasons?
keep = [0, 0]
for t in GMS:
    for y in range(Y0 + 1, Y1 - 1):
        if gm_of[(t, y)] != gm_of[(t, y - 1)] and hc.get((t, y)) == hc.get((t, y - 1)):
            keep[1] += 1
            keep[0] += hc.get((t, y + 1)) != hc.get((t, y)) or hc.get((t, y + 2)) != hc.get((t, y + 1))
done = [tt for tt in tenures if tt["last"] < Y1 and tt["first"] > Y0]
lens = sorted(tt["last"] - tt["first"] + 1 for tt in done)
names = Counter((tt["name"]) for tt in tenures)
new = [tt for tt in tenures if tt["first"] > Y0]
retread = sum(1 for tt in new if any(o["name"] == tt["name"] and o["first"] < tt["first"] for o in tenures))
out["turnover"] = {
    "years": f"{Y0 + 1}-{Y1} offseasons",
    "gm_changes_per_year": round(st.mean(gm_changes), 2), "gm_changes_sd": round(st.stdev(gm_changes), 2),
    "gm_changes_min_max": [min(gm_changes), max(gm_changes)],
    "hc_changes_per_year": round(st.mean(hc_changes), 2), "hc_changes_sd": round(st.stdev(hc_changes), 2),
    "both_same_offseason_per_year": round(both / len(gm_changes), 2),
    "share_of_gm_changes_with_new_hc": round(with_hc[0] / with_hc[1], 3),
    "share_of_hc_changes_with_new_gm": round(hc_with_gm[0] / hc_with_gm[1], 3),
    "new_gm_kept_coach_then_replaced_within_2_seasons": round(keep[0] / max(1, keep[1]), 3), "n_kept": keep[1],
    "completed_tenures": len(lens), "tenure_mean": round(st.mean(lens), 2), "tenure_median": st.median(lens),
    "tenure_share": {k: round(sum(1 for x in lens if lo <= x <= hi) / len(lens), 3)
                     for k, (lo, hi) in {"1": (1, 1), "2": (2, 2), "3": (3, 3), "4": (4, 4), "5-9": (5, 9),
                                         "10+": (10, 99)}.items()},
    "retread_share_of_new_gms": round(retread / len(new), 3),
    "per_year": per_year,
}
out["gm_change_odds"] = {f"{a} | {b}": [round(c / n, 3), n] for (a, b), (c, n) in sorted(firing.items())}

# ---- Habits: does it stay with the team, or with the GM? -----------------------------------------
def habit_report(val, years, label):
    """val[(team, year)] -> number. Persistence three ways:
    - team odd vs even years (all years, like draft_habits.py),
    - same GM, his odd vs even years (tenures with 4+ years in range),
    - the same team, the GM before vs the GM after a change (each side 3+ years),
    - the same GM at two teams (his years at each, 2+ years each)."""
    rep = {}
    teams = sorted(GMS)
    o = [st.mean(val.get((t, y), 0) for y in years if y % 2) for t in teams]
    e = [st.mean(val.get((t, y), 0) for y in years if not y % 2) for t in teams]
    rep["team_odd_even_corr"] = r2(corr(o, e))
    sd_team = st.pstdev([st.mean(val.get((t, y), 0) for y in years) for t in teams])
    rep["team_mean_sd"] = round(sd_team, 3)
    yrs = defaultdict(list)
    for (t, y), v in val.items():
        if y in years:
            yrs[gm_of[(t, y)]].append((y, v))
    a, b = [], []
    for tid, lst in yrs.items():
        if len(lst) >= 4:
            a.append(st.mean(v for y, v in lst if y % 2))
            b.append(st.mean(v for y, v in lst if not y % 2))
    rep["same_gm_odd_even_corr"] = r2(corr(a, b))
    rep["n_gms"] = len(a)
    # same team, different GMs
    a, b = [], []
    for t in teams:
        ts = [tid for tid in sorted(set(gm_of[(t, y)] for y in years)) if len(yrs[tid]) >= 3]
        ts.sort(key=lambda k: tenures[k]["first"])
        for k1, k2 in zip(ts, ts[1:]):
            a.append(st.mean(v for y, v in yrs[k1]))
            b.append(st.mean(v for y, v in yrs[k2]))
    rep["same_team_next_gm_corr"] = r2(corr(a, b))
    rep["n_pairs"] = len(a)
    # same GM, different teams
    by_name = defaultdict(list)
    for tid, lst in yrs.items():
        if len(lst) >= 2:
            by_name[tenures[tid]["name"]].append((tenures[tid]["team"], st.mean(v for y, v in lst)))
    a, b, who = [], [], []
    for nm, lst in by_name.items():
        tms = {}
        for tm, v in lst:
            tms.setdefault(tm, []).append(v)
        if len(tms) >= 2:
            vs = [st.mean(v) for v in tms.values()]
            a.append(vs[0])
            b.append(vs[1])
            who.append(nm)
    rep["same_gm_two_teams_corr"] = r2(corr(a, b))
    rep["movers"] = who
    # One-year-apart persistence, same GM vs a new GM (one season's value is noisy, both shrink)
    s1, s2, d1, d2 = [], [], [], []
    for t in teams:
        for y in years:
            if y - 1 in years and (t, y) in val and (t, y - 1) in val:
                (s1 if gm_of[(t, y)] == gm_of[(t, y - 1)] else d1).append(val[(t, y - 1)])
                (s2 if gm_of[(t, y)] == gm_of[(t, y - 1)] else d2).append(val[(t, y)])
    rep["next_year_corr_same_gm"] = r2(corr(s1, s2))
    rep["next_year_corr_new_gm"] = r2(corr(d1, d2))
    rep["n_new_gm_years"] = len(d1)
    return rep


# draft-day trades (draft_habits.py's rules)
trades = rows("trades/trades.csv.gz")
by_id = defaultdict(list)
for tr in trades:
    by_id[tr["trade_id"]].append(tr)
net = defaultdict(float)
for ts in by_id.values():
    s = int(ts[0]["season"])
    if s < 2010 or ts[0]["trade_date"][5:7] not in ("04", "05"):
        continue
    cur = [x for x in ts if x["pick_season"] == ts[0]["season"] and x["pick_number"] not in ("", "NA")]
    tms = sorted(set(ALIAS.get(x["gave"], x["gave"]) for x in ts))
    if not cur or len(tms) != 2:
        continue
    side = {tm: [int(x["pick_number"]) for x in cur if ALIAS.get(x["gave"], x["gave"]) == tm] for tm in tms}
    best = {tm: min(side[tm]) if side[tm] else 999 for tm in tms}
    up, down = (tms[0], tms[1]) if best[tms[0]] > best[tms[1]] else (tms[1], tms[0])
    net[(up, s)] -= 1
    net[(down, s)] += 1
yrs_trade = range(2010, 2027)
for t in GMS:
    for y in yrs_trade:
        net.setdefault((t, y), 0.0)
out["trade_habit"] = habit_report(net, yrs_trade, "net trade-downs per draft")

# free agency spending and re-signing (OverTheCap contracts, % of cap, market deals 1%+)
NICK = {"Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR", "Bears": "CHI",
        "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
        "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC",
        "Rams": "LA", "Dolphins": "MIA", "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG",
        "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Seahawks": "SEA", "Buccaneers": "TB",
        "Titans": "TEN", "Commanders": "WAS", "Football Team": "WAS", "Redskins": "WAS", "Washington": "WAS"}
con = rows("contracts/historical_contracts.csv.gz")
by_player = defaultdict(list)
for c in con:
    if c["year_signed"] in ("", "NA", "0") or c["team"] not in NICK:
        continue
    by_player[c["otc_id"] or c["player"]].append(c)
outside, own = defaultdict(float), defaultdict(float)
n_out = defaultdict(int)
for lst in by_player.values():
    lst.sort(key=lambda c: (int(c["year_signed"]), -float(c["apy"] or 0)))
    for prev, c in zip(lst, lst[1:]):
        y = int(c["year_signed"])
        pct = float(c["apy_cap_pct"] or 0)
        if not (2011 <= y <= 2021) or pct < 0.01:
            continue
        t = NICK[c["team"]]
        if NICK.get(prev["team"]) == t:
            own[(t, y)] += pct
        else:
            outside[(t, y)] += pct
            n_out[(t, y)] += 1
yrs_fa = range(2011, 2022)
for t in GMS:
    for y in yrs_fa:
        outside.setdefault((t, y), 0.0)
        own.setdefault((t, y), 0.0)
share = {k: own[k] / (own[k] + outside[k]) if own[k] + outside[k] else 0.5 for k in own}
out["fa_spending"] = habit_report(outside, yrs_fa, "outside signings, sum of APY % of cap (1%+ deals)")
out["fa_spending"]["mean_pct_of_cap"] = round(st.mean(outside.values()) * 100, 1)
out["fa_spending"]["team_year_sd_pct"] = round(st.pstdev(outside.values()) * 100, 1)
out["fa_spending"]["team_mean_sd_pct"] = round(out["fa_spending"]["team_mean_sd"] * 100, 1)
out["resign_share"] = habit_report(share, yrs_fa, "own players' share of market money (re-signs + extensions)")
out["resign_share"]["mean"] = round(st.mean(share.values()), 3)
out["own_spending"] = habit_report(own, yrs_fa, "own players: re-signs + extensions, APY % of cap")

# dead money and cap left (Spotrac), % of that year's total allocations
SPOTRAC = Path(os.environ.get("SPOTRAC_JSON", "spotrac_cap.json"))
cache = out.get("spotrac")
if SPOTRAC.exists():
    raw = json.load(open(SPOTRAC))
    sp = {}
    for y, tb in raw.items():
        for r in tb["rows"]:
            if not r[1].split():
                continue
            t = ALIAS.get(r[1].split()[0], r[1].split()[0])
            if t not in GMS:
                continue
            money = lambda s: float(s.replace("$", "").replace(",", "") or 0)
            sp[f"{t}-{y}"] = [money(r[5]), money(r[6]), money(r[9])]
    out["spotrac_raw"] = sp
elif OUT.exists():
    out["spotrac_raw"] = json.load(open(OUT)).get("spotrac_raw", {})
sp = out.get("spotrac_raw", {})
if sp:
    dead, room = {}, {}
    for k, (tot, space, d) in sp.items():
        t, y = k.split("-")
        dead[(t, int(y))] = d / (tot + space)
        room[(t, int(y))] = space / (tot + space)
    yrs_sp = range(2013, 2026)
    out["dead_money"] = habit_report(dead, yrs_sp, "dead money, share of the cap")
    out["dead_money"]["mean"] = round(st.mean(dead.values()), 3)
    out["dead_money"]["sd_team_year"] = round(st.pstdev(dead.values()), 3)
    out["cap_left"] = habit_report(room, yrs_sp, "cap space left at the season's end, share of the cap")
    out["cap_left"]["mean"] = round(st.mean(room.values()), 3)
out["restructures_otc_2021"] = {
    "source": "OverTheCap, Looking at Restructuring NFL Contracts (June 10, 2021), 2013-2020 adjusted to a $182M cap",
    "share_teams_any_restructure_a_year": 0.55, "share_major_over_6_5M": 0.37, "share_15M_plus": 0.20,
    "by_prior_wins_any": {"8+": 0.60, "5-8": 0.50, "0-5": 0.40},
    "2021_teams_over_15M": 17, "usual_teams_over_15M": "6-8 (prior high 11)",
    "2021_no_restructure": ["LAC", "IND", "NYJ", "NE", "TB", "JAX", "SEA"],
    "note": "share of teams that restructured at all rose from 42% (2017-19) to ~73% (2020-21)"}
json.dump(out, open(OUT, "w"), indent=1)
show = {k: v for k, v in out.items() if k != "spotrac_raw"}
print(json.dumps(show, indent=1))
