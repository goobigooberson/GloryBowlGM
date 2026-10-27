# gm.py
# General managers for the AI teams (Blake, Oct 22: "wouldnt a gm affect alot
# more than just the draft trade habits?"; he chose all four jobs below and
# visible GMs). Rules only, no screens. Design and real data:
# docs/staff-design.md section 10, docs/research/real_gm.json.
#
# You are your own team's GM. Every AI team has one, a person with a name, an
# age, a record (his teams' seasons) and a reputation (what everyone believes he
# is as a team builder: it follows his teams' results, as real GMs' do). What he
# does:
#   1. Draft-day trades: his habit of trading up or down (draft.trade_style).
#   2. Free agency and re-signing: how much he spends on other teams' players,
#      and how readily he pays his own (free_agency.py).
#   3. The cap: whether he pushes money into later years (restructures,
#      back-loaded deals) or keeps the books clean (free_agency.py).
#   4. Hiring coaches: he picks the staff, and GMs differ in how well they see
#      through a coach's reputation to what he really is (staff._ai_value). This
#      skill is hidden, like coaches' true ratings.
# Each habit is mostly his and partly the organization's (the owner, the
# building's culture): real habits change when the GM does, but not all the way
# (gm_research.py: draft-day trades, same GM odd vs even years 0.52, the same
# team before vs after a GM change 0.20).
#
# Hiring and firing: after each season, before the coaching carousel (real: the
# GM is usually let go first, on Black Monday, and the new one is hired in
# January), owners fire GMs by the real odds (record and tenure, measured from
# Wikipedia's GM lists 2002-2026), and hire a new one right away: a GM out of
# work, another team's scouting director (a promotion: his team can't block it),
# or an assistant GM from outside. A new GM often brings his own head coach
# (staff.carousel_start), and a coach he inherited is on thinner ice for a
# couple of years. Player trades wait until trades exist (hook: style "trade"
# is draft-day only for now).
#
# State: league.staff["gm"] (saved with the staff). Saves from before Oct 22 get
# GMs on load, seeded by the save's salt, so the same save always gets the same GMs.

import math
import random

from . import names

STYLES = ("trade", "fa", "resign", "cap")
STYLE_NAMES = {"trade": "Draft day", "fa": "Free agency", "resign": "His own players", "cap": "The salary cap"}
# What each end of a style looks like (screens show only a clear lean).
STYLE_WORDS = {"trade": ("Trades down for more picks", "Trades up for his man"),
               "fa": ("Builds through the draft", "Big free-agent spender"),
               "resign": ("Lets players walk", "Pays his own stars early"),
               "cap": ("Keeps the books clean", "Pushes money into later years")}

# ---- Knobs (PROVISIONAL unless a source is given) -------------------------------
# Share of each habit's spread that belongs to the organization, not the GM. Real (2002-26,
# gm_research.py), the same team's habit after a GM change vs the same GM's own steadiness:
# draft trades 0.20 vs 0.52, outside free-agent money 0.30 vs 0.49, own players' share
# 0.10 vs 0.43, dead money 0.20 vs 0.48. Part of what carries over is the situation (cap
# room, contracts), which the game makes on its own, so these sit a little under the ratios.
ORG_SHARE = {"trade": 0.20, "fa": 0.35, "resign": 0.20, "cap": 0.20}
# GM changes after a season, by wins (per 17 games) and his tenure (seasons as this team's GM).
# Real 2003-26 (Wikipedia GM lists; who ran each draft), after his 1st season: 0-4 wins 13%,
# 5-6 17%, 7-8 13%, 9-10 15%, 11+ 0% (11% overall: owners give a new GM time); after his 2nd:
# 28 / 13 / 15 / 12 / 6%; later: 47-55 / 16-26 / 12-21 / 6-15 / 2-6%; playoff teams 4.3%,
# others 20.5%. Smoothed so more wins never raise the odds; retirements by age.
# Rows: wins up to 4.5 / 6.5 / 8.5 / 10.5 / more.
FIRE_GM = {1: (0.12, 0.11, 0.09, 0.07, 0.01),
           2: (0.26, 0.14, 0.13, 0.09, 0.04),
           "settled": (0.45, 0.21, 0.15, 0.10, 0.03)}
FIRE_PLAYOFF_MULT = 0.5
FIRE_LIFT = 1.07              # odds multiplier (calibrated: real 4.5 GM changes a year)
# A new GM and the head coach he inherits. Real: 57% of GM changes come with a new head coach
# the same offseason; a new GM who kept the coach replaced him within 2 seasons 55% of the time.
NEW_GM_OWN_COACH = 0.55       # a new GM brings in his own head coach (on top of the usual odds)
INHERITED_MULT = 1.4          # later: the usual odds x this for a coach he didn't hire
# People.
AGE = (49, 7, 34, 68)         # a GM's age when first made (mean, spread, lowest, highest)
JUDGE_MEAN, JUDGE_SD = 50, 12  # how well he judges coaches (hidden), 1-99
# How much of a coach's reputation error he sees through when hiring: this share at an average
# judge, plus this much per spread above, within these limits (worst ~0, best ~0.7).
SEE_MEAN, SEE_PER_SD, SEE_RANGE = 0.30, 0.20, (0.0, 0.75)
# Reputation (shown): what everyone believes he is as a team builder. Starts as a rough read,
# then moves each season toward what his teams did (wins, playoffs), as real GMs' do.
REP_NEW_SD = 8
REP_MOVE = 0.25               # share of the way toward the season's showing
REP_NOISE = 2.0
RETIRE_AGE = 70               # retirement odds about 50% a year at this age (in a job)...
RETIRE_SPREAD = 2.5
OUT_OF_WORK_LIMIT = 3         # seasons out of work before he's gone from the league for good
NEWCOMERS = 5                 # assistant GMs / personnel directors from outside each year
# Owners' choice: reputation + their own read. Owners are wary of a GM who was let go
# elsewhere (real: 14% of new GMs 2003-26 had been a GM before).
OWNER_NOISE = 6.0
EXPERIENCE_BONUS = -7.0
DIRECTOR_REP = (41, 8)        # a scouting director's reputation as a GM candidate (mean, spread)
NEWCOMER_REP = (43, 8)
# In-season: none yet (the game has no in-season head coach firings for AI teams yet either).
# You (Blake, Oct 23: "gm firing should by default be off, but can be enabled in settings. i always
# had it off in fof8"): with league.settings["owner_can_fire"] on, your owner judges you after each
# season by the same real odds as the AI GMs (record, tenure, playoffs). FOF8 weighed finances as
# much as wins; this game has no team finances yet, so results decide, as they mostly do for real GMs.
# If you're fired, teams with an open GM job that want you make offers and you pick your next team.
YOU_OFFERS = 3                # at most this many offers
YOU_SHORTLIST = 3             # an owner offers you the job if you're among his top this many candidates
YOU_PRIOR_GAMES = 3           # in-season job security: the record so far, with this many .500 games mixed in
SECURITY_WORDS = ((0.05, "Secure"), (0.12, "Safe for now"), (0.25, "Uneasy"), (0.45, "Hot seat"),
                  (9.9, "On the way out"))
# ---------------------------------------------------------------------------------


def _clip(v, lo=1, hi=99):
    return max(lo, min(hi, v))


def _salt(league):
    return league.settings.get("salt", "")


def _rng(league, name):
    return random.Random(f"gm-{_salt(league)}-{league.season}-{name}")


def ensure(league):
    """league.staff["gm"], made for a new league or an older save (seeded by the
    save's salt). Your team never has an AI GM (you are its GM). Returns it, or
    None for a league without staffs."""
    st = getattr(league, "staff", None)
    if not st:
        return None
    g = st.get("gm")
    if not g:
        rng = random.Random(f"gm-new-{_salt(league)}-{league.settings.get('first_season', league.season)}")
        g = {"people": {}, "jobs": {}, "next_id": 1, "org": {}, "log": [], "season": league.season}
        st["gm"] = g
        for t in league.teams:
            o = random.Random(f"gm-org-{_salt(league)}-{t.id}")
            g["org"][str(t.id)] = {k: round(o.gauss(0, 1), 3) for k in STYLES}
            g["jobs"][str(t.id)] = None
            if t.id == league.user_team_id:
                continue
            p = _new_person(league, rng)
            done = min(18, int(rng.expovariate(1 / 4.5)))           # seasons already in the job
            if done > league.season - p["born"] - 30:
                done = max(0, league.season - p["born"] - 30)
            p["exp"] = done + (rng.randint(2, 6) if rng.random() < 0.14 else 0)
            p["rep"] = round(_clip(p["judge"] * 0.3 + 35 + rng.gauss(0, 7)), 1)
            _seat(league, p, t.id, league.season - done)
        # A few GMs out of work (fired in recent years).
        for _ in range(6):
            p = _new_person(league, rng)
            p["exp"] = rng.randint(2, 8)
            p["rep"] = round(_clip(rng.gauss(42, 7)), 1)
            p["out_since"] = league.season - rng.choice((0, 1, 1, 2))
    # You are your team's GM: if you took over a team that had one, he's out of work.
    user = league.user_team_id
    y = g.setdefault("you", {"team": user, "since": league.settings.get("first_season", league.season),
                             "record": [], "rep": 50.0, "jobs": []})
    if user is not None and y.get("team") != user:
        if y.get("team") is not None:
            y["jobs"].append({"team": y["team"], "from": y["since"], "to": league.season - 1})
        y["team"], y["since"] = user, league.season
    if user is not None:
        cur = g["jobs"].get(str(user))
        if cur is not None:
            p = g["people"][str(cur)]
            _unseat(league, p)
            _log(league, user, p, "left", "the team's new owner runs the front office")
            g["log"][-1]["quiet"] = True
    return g


def _new_person(league, rng, age=None):
    g = league.staff["gm"]
    gid = g["next_id"]
    g["next_id"] += 1
    if age is None:
        age = int(_clip(round(rng.gauss(AGE[0], AGE[1])), AGE[2], AGE[3]))
    p = {"id": gid, "name": " ".join(names.elder(rng)),
         "born": league.season - age, "judge": round(_clip(rng.gauss(JUDGE_MEAN, JUDGE_SD)), 1),
         "rep": None, "style": {k: round(rng.gauss(0, 1), 3) for k in STYLES},
         "team": None, "since": None, "exp": 0, "record": [], "from": None, "out_since": None,
         "retired": None, "interim": False, "inherited_hc": None}
    p["rep"] = round(_clip(p["judge"] * 0.3 + 35 + rng.gauss(0, REP_NEW_SD)), 1)
    g["people"][str(gid)] = p
    return p


def _seat(league, p, tid, since):
    p.update({"team": tid, "since": since, "out_since": None, "interim": False})
    league.staff["gm"]["jobs"][str(tid)] = p["id"]


def _unseat(league, p):
    jobs = league.staff["gm"]["jobs"]
    if jobs.get(str(p["team"])) == p["id"]:
        jobs[str(p["team"])] = None
    p.update({"team": None, "since": None, "out_since": league.season, "inherited_hc": None})


def _log(league, tid, p, move, note=""):
    league.staff["gm"]["log"].append({"season": league.season, "team": tid, "gid": p["id"], "name": p["name"],
                                      "move": move, "note": note})


# ---------------------------------------------------------------------------
# Looking things up
# ---------------------------------------------------------------------------

def gm_of(league, tid):
    """A team's GM (None for your team, or a league without staffs)."""
    st = getattr(league, "staff", None)
    g = st.get("gm") if st else None
    if not g or tid is None:
        return None
    gid = g["jobs"].get(str(tid))
    return g["people"].get(str(gid)) if gid is not None else None


def person(league, gid):
    st = getattr(league, "staff", None)
    g = st.get("gm") if st else None
    return g["people"].get(str(gid)) if g and gid is not None else None


def age(league, p):
    return league.season - p["born"]


def style(league, tid, key):
    """A team's habit (about -2.5 .. +2.5, average 0; + = the second of
    STYLE_WORDS[key]): mostly its GM's, partly the organization's. 0 for your
    team (you decide) and for a league without GMs."""
    if tid is None or tid == league.user_team_id:
        return 0.0
    st = getattr(league, "staff", None)
    g = st.get("gm") if st else None
    if not g:
        return 0.0
    org = g["org"].get(str(tid), {}).get(key, 0.0)
    p = gm_of(league, tid)
    mine = p["style"][key] if p else 0.0
    w = ORG_SHARE[key]
    return max(-2.5, min(2.5, math.sqrt(w) * org + math.sqrt(1 - w) * mine))


def judge_seen(league, tid):
    """Share of a coach's reputation error this team's GM sees through when
    hiring (0 for your team: you see reputations, like everyone)."""
    p = gm_of(league, tid)
    if not p:
        return 0.0
    v = SEE_MEAN + SEE_PER_SD * (p["judge"] - JUDGE_MEAN) / JUDGE_SD
    return max(SEE_RANGE[0], min(SEE_RANGE[1], v))


def reputation(p):
    return int(round(_clip(p["rep"])))


def new_this_offseason(league, tid):
    """The team's GM was hired this offseason."""
    p = gm_of(league, tid)
    return bool(p and p["since"] == league.season and not p.get("interim"))


def inherited_coach(league, tid, hc):
    """The head coach was there before this GM (he didn't hire him)."""
    p = gm_of(league, tid)
    if not p or not hc:
        return False
    return (hc.get("since") or 0) < (p["since"] or 0)


# ---------------------------------------------------------------------------
# After the season: records, careers, firings, hiring
# ---------------------------------------------------------------------------

def _wins17(r):
    g = (r.get("w", 0) + r.get("l", 0) + r.get("t", 0)) or 17
    return (r.get("w", 0) + 0.5 * r.get("t", 0)) * 17 / g


def fire_chance(wins17, tenure, playoffs):
    """Chance an AI owner changes GMs after a season (real table, smoothed)."""
    row = FIRE_GM[tenure if tenure <= 2 else "settled"]
    i = 0 if wins17 < 4.5 else 1 if wins17 < 6.5 else 2 if wins17 < 8.5 else 3 if wins17 < 10.5 else 4
    return row[i] * (FIRE_PLAYOFF_MULT if playoffs else 1.0)


def _showing(r):
    """What a season shows of a GM (reputation points): wins and playoffs."""
    res = (r.get("result") or "").lower()
    v = 50 + 5 * (_wins17(r) - 8.5) / 1.5
    if r.get("seed"):
        v += 5
    if res.startswith("won"):
        v += 8
    return v


def record_season(league, lines):
    g = league.staff["gm"]
    rng = _rng(league, "rep")
    y = g.get("you")
    for r in lines:
        if y is not None and r["team"] == league.user_team_id:
            y["record"].append({"season": r["season"], "team": r["team"], "w": r.get("w", 0), "l": r.get("l", 0),
                                "t": r.get("t", 0), "result": r.get("result", ""), "seed": r.get("seed")})
            y["rep"] = round(_clip(y["rep"] + REP_MOVE * (_showing(r) - y["rep"])), 1)
        p = gm_of(league, r["team"])
        if not p:
            continue
        p["record"].append({"season": r["season"], "team": r["team"], "w": r.get("w", 0), "l": r.get("l", 0),
                            "t": r.get("t", 0), "result": r.get("result", ""), "seed": r.get("seed"),
                            "interim": bool(p.get("interim"))})
        p["exp"] += 1
        p["rep"] = round(_clip(p["rep"] + REP_MOVE * (_showing(r) - p["rep"]) + rng.gauss(0, REP_NOISE)), 1)
    g["last_lines"] = [{k: r.get(k) for k in ("team", "season", "w", "l", "t", "result", "seed")} for r in lines]


def _retire_chance(league, p):
    return 1 / (1 + math.exp(-(age(league, p) - RETIRE_AGE) / RETIRE_SPREAD))


def _age_year(league, rng):
    for p in list(league.staff["gm"]["people"].values()):
        if p["retired"] is not None:
            continue
        chance = _retire_chance(league, p)
        if p["team"] is None:
            chance = min(1.0, 2 * chance)
            if p["out_since"] is not None and league.season - p["out_since"] > OUT_OF_WORK_LIMIT:
                chance = 1.0
        if rng.random() < chance:
            if p["team"] is not None:
                tid = p["team"]
                _log(league, tid, p, "retired", f"after {len([r for r in p['record'] if r['team'] == tid])} seasons")
                _unseat(league, p)
            p["retired"] = league.season


def fire(league, tid, why="fired"):
    p = gm_of(league, tid)
    if not p:
        return None
    seasons = len([r for r in p["record"] if r["team"] == tid])
    _log(league, tid, p, why, f"after {seasons} season{'s' if seasons != 1 else ''}")
    _unseat(league, p)
    return p


def candidates(league, tid):
    """Who could become this team's GM: GMs out of work, other teams' scouting
    directors (a promotion: his team can't block it) and this year's newcomers."""
    from . import staff as S
    out = []
    for p in league.staff["gm"]["people"].values():
        if p["retired"] is None and p["team"] is None and p["id"] not in _not_again(league, tid):
            out.append(("gm", p))
    for c in league.staff["coaches"].values():
        if c["retired"] is None and c["track"] == "scout" and c["team"] is not None and c["team"] != tid \
                and c["job"] in ("CS", "PP") and not c.get("interim") and S.age(league, c) <= 62:
            out.append(("director", c))
    return out


def _not_again(league, tid):
    """GMs this team fired or lost (it doesn't rehire them)."""
    return {e["gid"] for e in league.staff["gm"]["log"] if e["team"] == tid and e["move"] in ("fired", "left")}


def _director_rep(league, c):
    """A scouting director's standing as a GM candidate: his scouting reputation,
    squeezed toward a newcomer's level (he hasn't run a team)."""
    from . import staff as S
    rep = S.reputation(c, "eval") or 50
    return DIRECTOR_REP[0] + 0.4 * (rep - 55) + random.Random(f"gm-dir-{league.settings.get('salt', '')}-{c['id']}").gauss(0, DIRECTOR_REP[1] * 0.6)


def _owner_view(league, tid, kind, x):
    noise = random.Random(f"gm-owner-{_salt(league)}-{league.season}-{tid}-{kind}-{x['id']}").gauss(0, OWNER_NOISE)
    if kind == "gm":
        return x["rep"] + noise + (EXPERIENCE_BONUS if x["exp"] > 0 else 0.0)
    return _director_rep(league, x) + noise


def _promote(league, c, tid, rng):
    """Another team's scouting director becomes a GM: he leaves his staff job."""
    from . import staff as S
    old_team, old_job = c["team"], c["job"]
    p = _new_person(league, rng, age=S.age(league, c))
    p["name"] = c["name"]
    p["born"] = c["born"]
    # He's judged players for years; his eye for coaches is his own.
    p["judge"] = round(_clip(rng.gauss(JUDGE_MEAN + 0.15 * (c["true"].get("eval", 50) - 50), JUDGE_SD)), 1)
    p["rep"] = round(_clip(_director_rep(league, c)), 1)
    p["from"] = f"{S.JOB_NAMES[old_job]}, {league.team(old_team).name}"
    p["from_job"] = S.JOB_NAMES[old_job]
    p["from_team"] = old_team
    S._log(league, old_team, c, old_job, "left", "hired as general manager")
    S._unseat(league, c)
    c["retired"] = league.season       # leaves the coaching and scouting pool
    c["became_gm"] = p["id"]
    return p


def _hire(league, tid, rng):
    pool = candidates(league, tid)
    pool.sort(key=lambda kx: -_owner_view(league, tid, *kx))
    kind, x = pool[0]
    p = _promote(league, x, tid, rng) if kind == "director" else x
    was = p.get("from")
    retread = kind == "gm" and p["exp"] > 0
    p.pop("new", None)
    p["out_since"] = None
    hc = None
    from . import staff as S
    hc_c = S.staff_of(league, tid)["HC"]
    if hc_c:
        hc = hc_c["id"]
    _seat(league, p, tid, league.season)
    p["inherited_hc"] = hc
    note = (f"former GM" if retread else was or "")
    _log(league, tid, p, "hired", note)
    # Newcomers nobody hired stay in the pool for a year or two.
    return p


def offseason_start(league, lines, rng=None):
    """The season is over (league.season already the new one): records, a year
    older, AI owners' GM changes, new GMs hired. Runs before the new league year
    (the new GM makes its decisions) and before the coaching carousel (he
    picks the head coach). Returns [(team, old GM or None, new GM)]."""
    if not ensure(league):
        return []
    g = league.staff["gm"]
    rng = rng or _rng(league, "offseason")
    record_season(league, lines)
    # Your owner's verdict, made when you started the offseason (owner_review): if you were
    # fired and took another job, you move now (its GM was let go to make room for you).
    review = g.get("review")
    decided = None
    if review and review.get("season") == league.season - 1 and review.get("fired"):
        decided = set(review.get("ai_fired", ()))
        old, new = review["team"], review.get("new_team")
        _log_you(league, old, "fired", review.get("note", ""))
        if new is not None:
            if gm_of(league, new):
                fire(league, new)
            decided.discard(new)
            league.user_team_id = new
            _log_you(league, new, "hired", f"after the {league.team(old).name} let you go")
            ensure(league)
        review["done"] = True
    _age_year(league, rng)
    by_team = {r["team"]: r for r in lines}
    user = league.user_team_id
    ai = [t.id for t in league.teams if t.id != user]
    rng.shuffle(ai)
    changes = []
    for tid in ai:
        p = gm_of(league, tid)
        if p is None:
            changes.append((tid, None))
            continue
        r = by_team.get(tid, {})
        tenure = max(1, league.season - (p["since"] or league.season))
        chance = min(0.95, fire_chance(_wins17(r), tenure, bool(r.get("seed"))) * FIRE_LIFT)
        roll = rng.random()
        fired = (tid in decided) if decided is not None else roll < chance
        if p.get("interim") or fired:
            changes.append((tid, fire(league, tid)))
    out = []
    if changes:
        # This year's outside candidates (assistant GMs, personnel directors elsewhere): the
        # ones nobody hires stay in their jobs, out of the game's view.
        for _ in range(NEWCOMERS):
            p = _new_person(league, rng, age=int(_clip(round(rng.gauss(43, 5)), 33, 58)))
            p["rep"] = round(_clip(rng.gauss(*NEWCOMER_REP)), 1)
            p["from"] = rng.choice(("Assistant general manager", "Assistant general manager",
                                    "Director of player personnel", "Vice president of player personnel"))
            p["new"] = league.season
    for tid, old in changes:
        new = _hire(league, tid, rng)
        out.append((tid, old["id"] if old else None, new["id"]))
    for k in [k for k, p in g["people"].items() if p.get("new") == league.season]:
        del g["people"][k]
    g["season"] = league.season
    return out


# ---------------------------------------------------------------------------
# You: your owner's patience (off unless league.settings["owner_can_fire"])
# ---------------------------------------------------------------------------

def can_be_fired(league):
    return bool(league.settings.get("owner_can_fire", False))


def set_can_be_fired(league, on):
    league.settings["owner_can_fire"] = bool(on)


def you(league):
    st = getattr(league, "staff", None)
    g = st.get("gm") if st else None
    if not g:
        return None
    if "you" not in g:
        ensure(league)
    return g.get("you")


def _log_you(league, tid, move, note=""):
    league.staff["gm"]["log"].append({"season": league.season, "team": tid, "gid": None, "name": "you",
                                      "move": move, "note": note, "you": True})


def _your_tenure(league, finished):
    """Seasons you've run your current team (the one just played counts once it's over)."""
    y = you(league)
    since = y.get("since", league.season) if y else league.season
    return max(1, league.season - since + (1 if finished else 0))


def job_security(league):
    """How your owner sees you right now: {"chance" (that he'd let you go if the season
    ended today), "word", "on" (the setting), "tenure", "basis" (plain words)}. In the
    offseason it's last season's verdict-to-be; during the season, the record so far
    (with a few .500 games mixed in early on, so one bad week isn't the hot seat)."""
    tid = league.user_team_id
    if tid is None or not getattr(league, "staff", None):
        return None
    from . import season as SE
    from . import playoffs as po
    y = you(league) or {}
    if (SE.in_offseason(league) or SE.in_preseason(league)) and y.get("since") == league.season:
        # You just took this job: the owner hasn't seen a season of yours yet.
        p = min(0.95, fire_chance(8.5, 1, False) * FIRE_LIFT)
        return {"chance": p, "word": "New in the job", "on": can_be_fired(league), "tenure": 1,
                "basis": "you just took over; your first season decides the owner's view"}
    if SE.in_offseason(league) or SE.in_preseason(league):
        last = next((r for r in reversed(league.team_history) if r["team"] == tid
                     and r["season"] == league.season - 1), None)
        w17 = _wins17(last) if last else 8.5
        playoffs = bool(last and last.get("seed"))
        tenure = _your_tenure(league, False)
        basis = (f"last season {last['w']}-{last['l']}" + (f"-{last['t']}" if last['t'] else "") if last
                 else "no season played yet")
    else:
        r = SE.records(league).get(tid, {"w": 0, "l": 0, "t": 0})
        g = r["w"] + r["l"] + r["t"]
        w = r["w"] + 0.5 * r["t"]
        w17 = 17 * (w + 0.5 * YOU_PRIOR_GAMES) / (g + YOU_PRIOR_GAMES)
        over = SE.season_over(league)
        playoffs = bool(po.seed_of(league, tid)) if (over or SE.in_playoffs(league)) else False
        tenure = _your_tenure(league, True)
        basis = f"this season {r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
    money, money_word = _money(league, tid)
    p = min(0.95, fire_chance(w17, tenure, playoffs) * FIRE_LIFT * money)
    word = next(wd for lim, wd in SECURITY_WORDS if p < lim)
    return {"chance": p, "word": word, "on": can_be_fired(league), "tenure": tenure,
            "basis": f"{basis}, your {_ordinal(tenure)} season in charge" + (", playoffs" if playoffs else "")
                     + (f"; {money_word}" if money_word else "")}


def _money(league, tid):
    """The money part of your owner's view (finances.owner_money_factor; Blake, Oct 26:
    winning first, money only at the edges): (factor on the chance, words or None)."""
    if not getattr(league, "finances", None):
        return 1.0, None
    from . import finances
    return finances.owner_money_factor(league, tid)


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _ai_firings(league, lines, rng):
    """Which AI owners change GMs this offseason (decided early when you're fired, so
    the jobs that open can be offered to you; offseason_start then uses these)."""
    by_team = {r["team"]: r for r in lines}
    out = []
    for t in league.teams:
        if t.id == league.user_team_id:
            continue
        p = gm_of(league, t.id)
        if p is None:
            out.append(t.id)
            continue
        r = by_team.get(t.id, {})
        tenure = max(1, league.season + 1 - (p["since"] or league.season + 1))
        chance = min(0.95, fire_chance(_wins17(r), tenure, bool(r.get("seed"))) * FIRE_LIFT)
        if rng.random() < chance:
            out.append(t.id)
    return out


def owner_review(league):
    """The season is over and you're starting the offseason: if your owner can fire
    you, he decides (once a season, kept in the save). Returns the review:
    {"season", "fired", "chance", "team", "offers": [team ids], "new_team"}, or None
    when the setting is off (or there's no team of yours)."""
    tid = league.user_team_id
    if tid is None or not can_be_fired(league) or not ensure(league):
        return None
    g = league.staff["gm"]
    S = league.season
    rv = g.get("review")
    if rv and rv.get("season") == S:
        return rv
    from . import season as SE
    if not SE.season_over(league):
        return None
    lines = SE.team_season_summary(league)
    mine = next(r for r in lines if r["team"] == tid)
    tenure = _your_tenure(league, True)
    money, _w = _money(league, tid)
    chance = min(0.95, fire_chance(_wins17(mine), tenure, bool(mine.get("seed"))) * FIRE_LIFT * money)
    rng = random.Random(f"gm-you-{_salt(league)}-{S}")
    fired = rng.random() < chance
    rv = {"season": S, "fired": fired, "chance": round(chance, 3), "team": tid, "offers": [], "new_team": None,
          "record": [mine["w"], mine["l"], mine["t"]], "tenure": tenure}
    if fired:
        ai_fired = _ai_firings(league, lines, rng)
        rv["ai_fired"] = ai_fired
        rv["offers"] = _offers(league, ai_fired, rng)
        if not rv["offers"]:
            # Nobody's job is open: the owner most ready for a change makes one now that you're
            # available (owners do move when a GM they like comes free).
            by_team = {r["team"]: r for r in lines}
            hot = max((t.id for t in league.teams if t.id != tid and gm_of(league, t.id)),
                      key=lambda k: fire_chance(_wins17(by_team.get(k, {})),
                                                max(1, S + 1 - (gm_of(league, k)["since"] or S)),
                                                bool(by_team.get(k, {}).get("seed"))))
            rv["ai_fired"].append(hot)
            rv["offers"] = [hot]
        w, l_, t_ = rv["record"]
        rv["note"] = f"after {tenure} season{'s' if tenure != 1 else ''} in charge"
    g["review"] = rv
    return rv


def _your_view(league, tid, rng_key):
    """An owner's read of you as a candidate (your record's reputation, his own read,
    and that you were just let go elsewhere)."""
    y = you(league)
    noise = random.Random(f"gm-owner-you-{_salt(league)}-{league.season}-{tid}-{rng_key}").gauss(0, OWNER_NOISE)
    return y["rep"] + noise + EXPERIENCE_BONUS


def _offers(league, open_teams, rng):
    """Teams (of those opening their GM job) whose owners would offer it to you: you're
    among each one's top candidates. At most YOU_OFFERS, the keenest first."""
    out = []
    for tid in open_teams:
        mine = _your_view(league, tid, "offer")
        pool = candidates(league, tid)
        better = sum(1 for kind, x in pool if _owner_view(league, tid, kind, x) > mine)
        out.append((better, tid))
    out.sort()
    return [tid for better, tid in out if better < YOU_SHORTLIST][:YOU_OFFERS]


def take_job(league, tid):
    """You accept an offer (after being fired). You move when the offseason starts."""
    rv = (league.staff.get("gm") or {}).get("review")
    if not rv or not rv.get("fired") or tid not in rv.get("offers", ()):
        return False, "That job isn't offered to you."
    rv["new_team"] = tid
    return True, f"You're the new general manager of the {league.team(tid).name}."


def your_view(league):
    """Your own GM record for the screens: reputation, seasons, teams, playoff trips."""
    y = you(league)
    if not y:
        return None
    rec = y["record"]
    return {"reputation": int(round(_clip(y["rep"]))), "seasons": len(rec),
            "record": (sum(r["w"] for r in rec), sum(r["l"] for r in rec), sum(r["t"] for r in rec)),
            "playoffs": sum(1 for r in rec if r.get("seed")),
            "titles": sum(1 for r in rec if (r.get("result") or "").startswith("Won")),
            "since": y.get("since"), "jobs": list(y.get("jobs", ())), "history": list(rec)}


# ---------------------------------------------------------------------------
# For the screens and the news
# ---------------------------------------------------------------------------

KNOWN_FOR = 1.0               # a lean this clear (spreads) is what a GM is known for (about 1 in 3 per habit)


def style_words(league, p):
    """His clear leans, in words (for the screens): [(area, words)]. Styles are
    known around the league (they show in what he does); only clear ones are
    named."""
    leans = sorted(((abs(p["style"][k]), k) for k in STYLES if abs(p["style"][k]) >= KNOWN_FOR), reverse=True)
    return [(STYLE_NAMES[k], STYLE_WORDS[k][1 if p["style"][k] > 0 else 0]) for _v, k in leans[:2]]


def view(league, p):
    """Everything a screen may show about a GM (never his judging skill)."""
    rec = [r for r in p["record"] if not r.get("interim")]
    w = sum(r["w"] for r in rec)
    l_ = sum(r["l"] for r in rec)
    t_ = sum(r["t"] for r in rec)
    here = [r for r in rec if r["team"] == p["team"]]
    return {"id": p["id"], "name": p["name"], "age": age(league, p), "team": p["team"], "since": p["since"],
            "reputation": reputation(p), "record": (w, l_, t_), "seasons": len(rec),
            "here": (sum(r["w"] for r in here), sum(r["l"] for r in here), sum(r["t"] for r in here)),
            "playoffs": sum(1 for r in rec if r.get("seed")), "titles": sum(1 for r in rec if (r.get("result") or "").startswith("Won")),
            "teams": sorted({r["team"] for r in rec}), "from": p.get("from"), "styles": style_words(league, p),
            "history": list(rec), "interim": p.get("interim", False), "exp": p["exp"]}


def log(league, season=None):
    st = getattr(league, "staff", None)
    g = st.get("gm") if st else None
    if not g:
        return []
    return [e for e in g["log"] if season is None or e["season"] == season]
