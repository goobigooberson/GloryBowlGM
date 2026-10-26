# hall_of_fame.py
# The Hall of Fame (Oct 25; FOF8: "eligible 5 years after retiring; needs 80%
# of the vote"). Rules only: the Hall of Fame page, the player card and the
# news read from here.
#
# How it works (the real Pro Football Hall of Fame's way, which FOF8 copied):
#   - A player is eligible 5 seasons after his last one: a player who retires
#     after the 2030 season is first on the ballot the week of the 2035
#     season's Glory Bowl, as the "Class of 2036" (the real Hall votes the
#     week of the Super Bowl and names the class for the new year).
#   - The vote: the same 50-member media panel as the MVP (awards.VOTERS).
#     Each voter says yes or no; 80% (40 votes) puts a player in.
#   - At most 5 a year (the real Hall's limit on modern-era players); if more
#     reach 80%, the 5 with the most votes go in and the rest wait a year.
#   - A player stays on the ballot until 25 seasons after retiring (the real
#     Hall's modern-era window), so borderline players can get in after a wait,
#     and support tends to grow the longer a good player waits (as it does).
#     PROVISIONAL (Blake): FOF8 gave one shot only.
#
# What voters weigh: only the record. First-team All-Pros (each weighted by how common that
# All-Pro spot was in the real data: SPOT_WEIGHT), Pro Bowls and
# career production at his position, with the weights real voters have
# shown: a logistic fit on every drafted player whose career ended by 2015
# (nflverse draft_picks, 1980-2005 classes, `hof` column; tools/hof_check.py
# prints the fit). Each player's case is also seen through the panel's own
# view of his career (his "standing": the part of real voting the record
# doesn't explain, a fixed draw for each player), and each year's vote has
# its own small swing. Never used: hidden ratings, Generational status.
# Careers count only from the league's first season (a generated league's
# veterans have no record from before it; FOF8 imported real careers instead).

import math
import random
from collections import defaultdict

from . import awards as A
from . import stats as ST

WAIT = 5                      # seasons after his last one before he's on the ballot
LAST_BALLOT = 25              # last ballot: this many seasons after his last one
VOTERS = A.VOTERS             # the media panel (50)
NEEDED = 0.80                 # share of the vote that puts a player in
CLASS_LIMIT = 5               # most players inducted in one year
FINALISTS = 15                # the real Hall's modern-era finalists: shown with their votes
ON_BALLOT = 0.004             # a career this unlikely to make it isn't on the ballot at all (saves time)

# ---- The case: real voters' weights (logit; tools/hof_check.py --fit) -----------
CASE_BASE = -9.54             # the tuned knob: how many get in a year (real: ~4.5-5 for 32 teams). The real
                              # fit's -9.79 gave 3.6 a year in 4 lab leagues of 22 seasons, a little low at
                              # every All-Pro count too; +0.25 (tools/hof_check.py)
CASE_AP1 = 1.285              # each first-team All-Pro
CASE_PB = 0.785               # each Pro Bowl
CASE_PROD = 0.509             # each "great season" of production at his position (PROD_REF)
CASE_POS = {"QB": 0.12, "RB": 0.39, "WR": -0.42, "TE": -0.64, "OL": 0.98, "DL": -0.20, "LB": -0.36,
            "DB": -0.13, "K": 0.26, "P": -0.01, "LS": -6.0}
SPECIALIST_SPOTS = {"KR", "PR", "ST", "LS"}   # these All-Pro spots count half (voters rarely induct
SPECIALIST_WEIGHT = 0.5                       # return men: Hester in 2024 was the first)
# The weights above were fitted on 1980-2005 careers, when the AP's first team had 2 wide
# receivers, 2 defensive ends, about 3 linebackers and no slot corner; the game's All-Pro team is
# today's (3 receivers, 3 edge rushers, 2 linebackers, a slot corner). So each first-team All-Pro
# counts by how common that honor was in the real data: that era's spots over the game's.
SPOT_WEIGHT = {"WR": 2 / 3, "EDGE": 2 / 3, "LB": 3 / 2, "NB": 0.5}
HOF_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
             "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB", "K": "K", "P": "P",
             "LS": "LS"}
# A great season at each position (the average of the top 5 each real season, 1999-2015,
# 16 games; scaled to the league's season length).
PROD_REF = {"QB": (4400, 32), "RB": 1900, "WR": 1450, "TE": 900, "DL": 15, "LB": 15, "DB": 7.5}

# ---- How the vote plays out (tuned with tools/hof_check.py) ----------------------
VOTE_SLOPE = 1.6              # how sharply the panel's support follows his standing
FIRST_BALLOT_BAR = 4.0        # standing above this gets in on the first ballot (real: about a third of
                              # modern-era inductees go in first time; with no class limit this gives 43%
                              # on real careers, and the limit of 5 a year holds some back)
WAIT_GAIN = FIRST_BALLOT_BAR / (LAST_BALLOT - WAIT)   # support grows with each year he waits: a standing
                                                      # just above 0 gets in on the last ballot
YEAR_SWING = 0.2              # each year's vote has its own mood


def ensure(league):
    """league.awards["hall_of_fame"]: {"members": [...], "votes": [...]}, saved with the awards."""
    A.ensure(league)
    h = league.awards.get("hall_of_fame")
    if not isinstance(h, dict):
        h = {"members": [], "votes": []}
        league.awards["hall_of_fame"] = h
    h.setdefault("members", [])
    h.setdefault("votes", [])
    return h


def _sig(x):
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))


# ---------------------------------------------------------------------------
# A career on the record
# ---------------------------------------------------------------------------

def _career_lines(league, pids):
    by = defaultdict(list)
    for r in league.career:
        if r["pid"] in pids:
            by[r["pid"]].append(r)
    return by


def resume(league, pid, lines=None, honors=None):
    """What the voters see: {"ap1", "ap2", "pb", "awards": [(season, name)], "titles": [seasons],
    "seasons", "games", "stats" (regular season), "teams": [ids, most games first], "first", "last",
    "prod"}."""
    p = league.player(pid)
    if lines is None:
        lines = [r for r in league.career if r["pid"] == pid]
    reg = [r for r in lines if r["phase"] == ST.REGULAR]
    stats = ST.add_up([r["stats"] for r in reg])
    games = defaultdict(float)
    for r in reg:
        games[r["team"]] += r["stats"].get("gp", 0)
    titles = sorted({r["season"] for r in lines if r["phase"] == ST.PLAYOFFS
                     and league.champions.get(r["season"]) == r["team"]})
    h = honors if honors is not None else _honors(league).get(pid, {})
    years = {r["season"] for r in reg}
    return {"ap1": h.get("ap1", 0), "ap1_spec": h.get("ap1_spec", 0), "ap1_w": h.get("ap1_w", 0.0),
            "ap2": h.get("ap2", 0),
            "pb": h.get("pb", 0), "awards": sorted(h.get("awards", [])), "titles": titles,
            "seasons": len(years), "games": int(stats.get("gp", 0)), "stats": stats,
            "teams": sorted(games, key=lambda t: -games[t]),
            "first": min(years) if years else None, "last": max(years) if years else None,
            "prod": production(league, p.position, stats)}


def _honors(league):
    """{pid: {"ap1", "ap1_spec", "ap2", "pb", "awards"}} from the award records."""
    A.ensure(league)
    out = defaultdict(lambda: {"ap1": 0, "ap1_spec": 0, "ap1_w": 0.0, "ap2": 0, "pb": 0, "awards": []})
    for r in league.awards["all_pro"]:
        if r["team_no"] == 1:
            out[r["pid"]]["ap1_spec" if r["spot"] in SPECIALIST_SPOTS else "ap1"] += 1
            out[r["pid"]]["ap1_w"] += SPECIALIST_WEIGHT if r["spot"] in SPECIALIST_SPOTS else                 SPOT_WEIGHT.get(r["spot"], 1.0)
        else:
            out[r["pid"]]["ap2"] += 1
    for r in league.awards["pro_bowl"]:
        if A.played_pro_bowl(r):
            out[r["pid"]]["pb"] += 1
    for r in league.awards["season"]:
        out[r["pid"]]["awards"].append((r["season"], A.AWARD_NAME[r["award"]]))
    return out


def production(league, position, s):
    """Career production in great seasons at his position (PROD_REF)."""
    g = HOF_GROUP.get(position)
    scale = league.settings.get("season_games", 17) / 16
    f = lambda k: (s or {}).get(k, 0) or 0
    if g == "QB":
        yds, td = PROD_REF["QB"]
        return (f("pass_yds") / yds + f("pass_td") / td) / 2 / scale
    if g == "RB":
        return (f("rush_yds") + f("rec_yds")) / PROD_REF["RB"] / scale
    if g in ("WR", "TE"):
        return f("rec_yds") / PROD_REF[g] / scale
    if g in ("DL", "LB"):
        return f("sacks") / PROD_REF[g] / scale
    if g == "DB":
        return f("def_int") / PROD_REF["DB"] / scale
    return 0.0


def case(position, r):
    """His Hall of Fame case in real voters' weights (logit: 0 = even odds of getting in someday)."""
    ap1 = r["ap1_w"] if "ap1_w" in r else r["ap1"] + SPECIALIST_WEIGHT * r.get("ap1_spec", 0)
    return (CASE_BASE + CASE_AP1 * ap1 + CASE_PB * r["pb"]
            + CASE_PROD * r["prod"] + CASE_POS.get(HOF_GROUP.get(position), 0.0))


def chance(position, r):
    """How likely a career like this is to get in someday (the real fit's odds)."""
    return _sig(case(position, r))


def standing(league, pid):
    """The panel's own view of his career beyond the record: a fixed draw for each player
    (logistic, so a case's odds of ever getting in are the real fit's odds)."""
    u = random.Random(f"hof-standing-{league.settings.get('salt', '')}-{pid}").random()
    u = min(max(u, 1e-9), 1 - 1e-9)
    return math.log(u / (1 - u))


def ballot_support(c, stand, ballot_no, swing):
    """The share of voters for him on his ballot_no-th ballot (1 = first)."""
    x = c + stand - FIRST_BALLOT_BAR + WAIT_GAIN * (ballot_no - 1) + swing
    return _sig(math.log(NEEDED / (1 - NEEDED)) + VOTE_SLOPE * x)


# ---------------------------------------------------------------------------
# The yearly vote (the week of the Glory Bowl, after the season awards)
# ---------------------------------------------------------------------------

def members(league):
    return ensure(league)["members"]


def member(league, pid):
    """His Hall of Fame record ({pid, season, class_of, votes, ballot, team, position}) or None."""
    return next((m for m in members(league) if m["pid"] == pid), None)


def candidates(league, season=None):
    """Retired players on this year's ballot: [(player, ballot number, resume, case)]."""
    season = league.season if season is None else season
    inducted = {m["pid"] for m in members(league)}
    pool = [p for p in league.players if p.retired is not None and p.id not in inducted
            and WAIT <= season - p.retired <= LAST_BALLOT]
    if not pool:
        return []
    lines = _career_lines(league, {p.id for p in pool})
    honors = _honors(league)
    out = []
    for p in pool:
        if not lines.get(p.id):
            continue
        r = resume(league, p.id, lines[p.id], honors.get(p.id, {}))
        c = case(p.position, r)
        if _sig(c) < ON_BALLOT:
            continue
        out.append((p, season - p.retired - WAIT + 1, r, c))
    return out


def vote(league):
    """Hold this season's vote (once). Returns the new members."""
    h = ensure(league)
    season = league.season
    if any(v["season"] == season for v in h["votes"]):
        return []
    rng = random.Random(f"hof-vote-{league.settings.get('salt', '')}-{season}")
    rows = []
    for p, ballot_no, r, c in sorted(candidates(league, season), key=lambda x: x[0].id):
        share = ballot_support(c, standing(league, p.id), ballot_no, rng.gauss(0, YEAR_SWING))
        yes = sum(1 for _v in range(VOTERS) if rng.random() < share)
        rows.append({"pid": p.id, "votes": yes, "ballot": ballot_no, "team": r["teams"][0] if r["teams"] else None,
                     "position": p.position, "x": c})
    rows.sort(key=lambda x: (-x["votes"], -x["x"]))
    need = math.ceil(NEEDED * VOTERS - 1e-9)
    elected = [x for x in rows if x["votes"] >= need][:CLASS_LIMIT]
    elected_ids = {x["pid"] for x in elected}
    finalists = rows[:max(FINALISTS, len(elected))]
    h["votes"].append({"season": season, "class_of": season + 1,
                       "ballot": [[x["pid"], x["votes"], x["ballot"], x["pid"] in elected_ids] for x in finalists],
                       "considered": len(rows), "held_over": sum(1 for x in rows if x["votes"] >= need) - len(elected)})
    new = []
    for x in elected:
        m = {"pid": x["pid"], "season": season, "class_of": season + 1, "votes": x["votes"], "ballot": x["ballot"],
             "team": x["team"], "position": x["position"]}
        h["members"].append(m)
        new.append(m)
    return new


def after_week(league):
    """season.awards_week: the vote is held once the season awards are announced."""
    if A.winners(league, league.season):
        vote(league)


# ---------------------------------------------------------------------------
# For the screens and the news
# ---------------------------------------------------------------------------

def classes(league):
    """{class year: [member records]} newest first."""
    out = defaultdict(list)
    for m in members(league):
        out[m["class_of"]].append(m)
    return dict(sorted(out.items(), reverse=True))


def ballot(league, season):
    """That year's vote record, or None."""
    return next((v for v in ensure(league)["votes"] if v["season"] == season), None)


def eligible_next(league, n=10):
    """The strongest careers first eligible at next year's vote (on the record only)."""
    season = league.season + 1
    pool = [p for p in league.players if p.retired is not None and season - p.retired == WAIT]
    if not pool:
        return []
    lines = _career_lines(league, {p.id for p in pool})
    honors = _honors(league)
    rows = []
    for p in pool:
        if lines.get(p.id):
            r = resume(league, p.id, lines[p.id], honors.get(p.id, {}))
            c = case(p.position, r)
            if _sig(c) >= ON_BALLOT:
                rows.append((p, r, c))
    rows.sort(key=lambda x: -x[2])
    return [(p, r) for p, r, _c in rows[:n]]


def summary_text(league, pid):
    """'Hall of Fame, Class of 2036 (first ballot)' or ''."""
    m = member(league, pid)
    if not m:
        return ""
    return f"Hall of Fame, Class of {m['class_of']}" + (" (first ballot)" if m["ballot"] == 1 else "")
