# staff.py
# Coaching staffs and front offices (Blake, Oct 24; design and his answers:
# docs/staff-design.md). Rules only, no screens.
#
# Every team has 8 jobs (Blake: "FOF8-sized" coaching staff plus three front
# office / support jobs):
#   HC  head coach                    AHC assistant head coach
#   OC  offensive coordinator         SC  strength and conditioning coach
#   DC  defensive coordinator         CS  director of college scouting
#   AT  head athletic trainer         PP  director of pro personnel
# You hire yours (you're the GM); AI teams hire theirs.
#
# Every coach is a person with a career: age, a background (the position group
# he coached: QB, RB, WR, TE, OL, DL, LB, DB or ST for special teams), hidden
# true ratings, a reputation (what everyone, you included, can see: Blake chose
# "reputation + track record"), a style (coordinators and head coaches), a
# contract, his record job by job, a mentor (his coaching tree), ambition and
# loyalty. Coaches improve with experience into their 50s, slow down later,
# retire, climb the ladder (assistant -> coordinator -> head coach) and get
# fired.
#
# What the staff does elsewhere in the engine:
#   - player development (development.py): coaching_scores() below. The coach
#     whose background is a player's group (his "specialist") matters most,
#     like FOF8's "boost when the head or assistant coach specializes in the
#     player's position group". Measured against the league's average staff
#     each season, so a league of average staffs develops exactly as before.
#   - what each team sees of players (evaluation.py): eval_z() below.
#   - the game sim's coordinator styles (sim/gameteam.py): style() below.
#
# Money (Blake: an owner's staff budget): coaches' pay is outside the player
# cap; each owner sets a yearly budget for the 8 jobs. A fired coach is still
# owed the rest of his contract (less what his next job pays: the real NFL's
# offset), and that counts against the budget.
#
# The hiring cycle (Blake: "carousel in rounds"): the first offseason phase,
# right after the season (the real Black Monday into February): AI teams
# change coaches by the real odds (wins, tenure; measured from nflverse,
# docs/staff-design.md section 1), then three rounds of hiring: head coaches;
# coordinators and assistant head coaches; the rest. You make offers;
# candidates take the best offer for them. A team can't block its coach from
# taking a promotion (real rule).
#
# Everything in "Knobs" is a judgment call unless it says where it's from
# (PROVISIONAL, docs/staff-design.md).

import math
import random

from . import names

JOBS = ("HC", "OC", "DC", "AHC", "SC", "CS", "PP", "AT")
JOB_NAMES = {"HC": "Head coach", "OC": "Offensive coordinator", "DC": "Defensive coordinator",
             "AHC": "Assistant head coach", "SC": "Strength and conditioning coach",
             "CS": "Director of college scouting", "PP": "Director of pro personnel",
             "AT": "Head athletic trainer"}
JOB_SHORT = {"HC": "Head coach", "OC": "Off. coordinator", "DC": "Def. coordinator", "AHC": "Asst. head coach",
             "SC": "Strength coach", "CS": "College scouting", "PP": "Pro personnel", "AT": "Head trainer"}
# Career tracks: which jobs a person can hold.
TRACK = {"HC": "coach", "OC": "coach", "DC": "coach", "AHC": "coach", "SC": "strength", "CS": "scout",
         "PP": "scout", "AT": "medical"}
# Job level within a track (a coach takes another team's job only if it's a promotion).
LEVEL = {"HC": 3, "OC": 2, "DC": 2, "AHC": 1, "SC": 1, "CS": 1, "PP": 1, "AT": 1}
ROUNDS = {1: ("HC",), 2: ("OC", "DC", "AHC"), 3: ("SC", "CS", "PP", "AT")}
ROUND_NAMES = {1: "Head coaches", 2: "Coordinators and assistant head coaches",
               3: "Strength coaches, scouting directors and trainers"}
GROUPS = ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "ST")
GROUP_NAMES = {"QB": "Quarterbacks", "RB": "Running backs", "WR": "Wide receivers", "TE": "Tight ends",
               "OL": "Offensive line", "DL": "Defensive line", "LB": "Linebackers", "DB": "Defensive backs",
               "ST": "Special teams"}
OFFENSE = ("QB", "RB", "WR", "TE", "OL")
DEFENSE = ("DL", "LB", "DB")
POSITION_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
                  "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB", "K": "ST", "P": "ST",
                  "LS": "ST"}
# True ratings each track has (hidden; reputation shows them as they're believed to be).
RATINGS = {"coach": ("dev", "eval"), "strength": ("cond", "dev"), "scout": ("eval",), "medical": ("rehab",)}
RATING_NAMES = {"dev": "Player development", "eval": "Evaluating players", "cond": "Conditioning",
                "rehab": "Rehab"}
# What a job is judged on (shares of each rating).
JOB_SCORE = {"HC": {"dev": 0.6, "eval": 0.4}, "OC": {"dev": 0.7, "eval": 0.3}, "DC": {"dev": 0.7, "eval": 0.3},
             "AHC": {"dev": 0.7, "eval": 0.3}, "SC": {"cond": 0.6, "dev": 0.4}, "CS": {"eval": 1.0},
             "PP": {"eval": 1.0}, "AT": {"rehab": 1.0}}

# ---- Knobs (PROVISIONAL unless a source is given) -------------------------------
# Backgrounds. Offensive coordinators mostly come up from QB and WR rooms, defensive
# coordinators from the secondary; head coaches ~55% offense in recent hiring cycles.
OC_BACKGROUND = {"QB": 0.40, "WR": 0.20, "OL": 0.15, "TE": 0.15, "RB": 0.10}
DC_BACKGROUND = {"DB": 0.45, "LB": 0.30, "DL": 0.25}
HC_SIDE = {"O": 0.55, "D": 0.40, "S": 0.05}
AHC_BACKGROUND = {"ST": 0.20, "QB": 0.08, "RB": 0.10, "WR": 0.10, "TE": 0.08, "OL": 0.12, "DL": 0.12,
                  "LB": 0.10, "DB": 0.10}
# Ages (mean, spread, lowest, highest) by job when first made; newcomers are younger.
AGE = {"HC": (52, 7, 36, 72), "OC": (48, 7, 33, 68), "DC": (49, 7, 33, 68), "AHC": (50, 8, 32, 70),
       "SC": (45, 8, 30, 66), "CS": (47, 8, 32, 68), "PP": (47, 8, 32, 68), "AT": (46, 8, 30, 66)}
NEWCOMER_AGE = (41, 6, 29, 60)
# True ability: a talent level per person (ratings share it, each also varies on its own).
TALENT_EMPLOYED = 55          # coaches already in the 256 jobs when a league starts
TALENT_POOL = 47              # coaches out of work
TALENT_NEW = 48               # newcomers from outside each year (position and college coaches)
TALENT_SD = 12
RATING_SD = 8                 # each rating around his talent
# Reputation: true ability + a mistake that shrinks as his record grows (a newcomer is
# off by about REP_NEW; each season keeps REP_KEEP of the old mistake and adds a fresh
# REP_NOISE from what his teams' results happened to show: one great or awful year can
# fool everyone a little).
REP_NEW = 11
REP_START = 7                 # coaches already in jobs when a league starts (some record behind them)
REP_KEEP = 0.8
REP_NOISE = 3.0
# Careers: yearly change in true ability by age, and retirement odds by age.
GROWTH_BY_AGE = ((44, 0.8), (57, 0.2), (200, -0.7))   # (up to this age, average change a year)
GROWTH_SD = 1.3
RETIRE_AGE = 66               # retirement odds: about 50% a year at this age...
RETIRE_SPREAD = 3.5           # ...rising/falling by e per this many years
OUT_OF_WORK_LIMIT = 2         # seasons out of work before a coach leaves the NFL for good
# Contracts (years: weights). Real: head coaches 4-6 (5 most common), coordinators 2-3.
CONTRACT_YEARS = {"HC": {4: 0.3, 5: 0.5, 6: 0.2}, "OC": {2: 0.4, 3: 0.6}, "DC": {2: 0.4, 3: 0.6},
                  "AHC": {2: 0.5, 3: 0.5}, "SC": {2: 0.5, 3: 0.5}, "CS": {3: 0.6, 4: 0.4},
                  "PP": {3: 0.6, 4: 0.4}, "AT": {3: 1.0}}
# Pay ($K a year at the 2026 cap, scaled with the cap): (at reputation 40, per point above,
# lowest, highest). Reported ranges (real pay isn't published): head coaches ~$4-20M
# (Payton ~$18M), coordinators $1-4.5M, position coaches $0.3-1M.
PAY = {"HC": (4000, 200, 3500, 20000), "OC": (900, 60, 800, 4500), "DC": (900, 60, 800, 4500),
       "AHC": (600, 25, 500, 2000), "SC": (300, 10, 250, 900), "CS": (300, 9, 250, 800),
       "PP": (300, 9, 250, 800), "AT": (200, 6, 180, 500)}
HC_EXPERIENCE_PREMIUM = 0.15  # a former head coach asks this much more for a head job
# Fired coaches' remaining pay: this share counts against the staff budget. Real owners pay
# it out of pocket and hire a replacement anyway; at 1.0 a team that fired a head coach
# with years left (~$8M a year) couldn't afford a new one (tested: firings stalled and
# most new head coaches were last-minute minimum hires). Shown on the staff page.
DEAD_IN_BUDGET = 0.0
# Owners' yearly staff budget for the 8 jobs ($K at the 2026 cap; an average staff costs ~$16M, a
# star head coach alone ~$13-15M, so most owners make you choose): average, spread of the
# owner's factor (frugal ~0.75, big spenders up to ~1.4).
BUDGET_BASE = 20000
BUDGET_SD = 0.18
BUDGET_RANGE = (0.72, 1.40)
# Head coach changes after a season: chance by wins (per 17 games) and his tenure, from
# real 1999-2025 (nflverse game files; docs/staff-design.md), smoothed so more wins never
# raise the odds (the real 9-10 win rows include retirements, which are modeled by age
# here). Rows: wins up to 4.5 / 6.5 / 8.5 / 10.5 / more.
FIRE_HC = {"new": (0.35, 0.17, 0.05, 0.04, 0.01),   # his 1st or 2nd season
           "settled": (0.71, 0.45, 0.21, 0.12, 0.045)}
FIRE_PLAYOFF_MULT = 0.5       # reached the playoffs
# The hiring market steadies the number of changes from year to year (Blake, Oct 24: match
# the real spread, not just the average). Real 1999-2025: 6.6 head coach changes a year,
# spread 1.8, never under 3 or over 10, steadier than 32 independent coin flips would be
# (about 2.3): owners look at how many jobs are already open (the best candidates go fast
# in a busy year; in a quiet one a struggling coach looks easier to replace). Each AI team,
# in random order, has its odds x e^(-MARKET_K x (jobs opened so far - expected so far)).
MARKET_K = 0.8
MARKET_LIFT = 1.18            # odds multiplier that keeps the average at the real 6.6 (the brake trims it)
# A new head coach (AI team) keeps each of these with this chance (otherwise he brings
# his own; real: much of the coordinator turnover is new head coaches' staffs).
KEEP_UNDER_NEW_HC = {"OC": 0.20, "DC": 0.25, "AHC": 0.35, "SC": 0.50, "CS": 0.85, "PP": 0.85, "AT": 0.85}
# Coordinators fired when the head coach stays: base + this x how far his unit was in the
# bottom half of the league (points scored for the offense, allowed for the defense).
# Target with the rest (new head coaches, promotions, retirements): about 30% of
# coordinators change a year (real: about half the league changes at least one).
FIRE_COORD = (0.05, 0.25)
OTHER_TURNOVER = 0.08         # yearly chance an AI team replaces an SC / scouting director / trainer
# The carousel: newcomers from outside each year (keeps the pool of candidates steady).
NEWCOMERS = {("coach", "O"): 12, ("coach", "D"): 10, ("coach", "S"): 3, ("college", None): 2,
             ("strength", None): 4, ("scout", None): 6, ("medical", None): 3}
# A candidate's view of an offer: e^(... ) style utility.
U_MONEY = 2.5                 # x log(offer / his market value)
U_PROMOTION = 1.2             # per level up the ladder
U_OUTLOOK = 0.4               # per spread of last season's wins (good teams attract coaches)
U_TIE = 0.6                   # worked with the head coach before / the head coach is his mentor
U_NOISE = 0.35                # his own taste (fixed per coach and team)
U_ACCEPT_FREE = -0.6          # out of work: takes a job at least this good
U_ACCEPT_LAST = -1.6          # ...or, when every round is over, almost anything
AI_VIEW_NOISE = 4.0           # AI teams' taste in candidates (reputation points, fixed per team)
PASSES = 2                    # rounds of offers within each round of the carousel
# In-season firings (AI): real 1.5 a season (1999-2025), mostly bad starts.
INSEASON_WEEKS = (4, 14)
INSEASON_BASE = 0.010
INSEASON_K = 6.0              # x e^(K x (0.35 - win share so far)) while under 0.40
INSEASON_SETTLED = 1.5        # 3rd season or later
INSEASON_NEW = 0.5
# ---------------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The staff state (league.staff, saved as JSON in the save's league_info)
# ---------------------------------------------------------------------------

def _rng(league, name):
    return random.Random(f"staff-{league.settings.get('salt', '')}-{league.season}-{name}")


def ensure(league):
    """league.staff, made for a new league or an older save (the same save always
    gets the same staff: seeded by its salt). Returns it."""
    st = getattr(league, "staff", None)
    if st and st.get("coaches"):
        return st
    rng = random.Random(f"staff-new-{league.settings.get('salt', '')}-{league.settings.get('first_season', league.season)}")
    st = {"coaches": {}, "jobs": {}, "next_id": 1, "owner": {}, "dead": [], "log": [], "carousel": None,
          "season": league.season}
    league.staff = st
    for t in league.teams:
        st["owner"][str(t.id)] = round(max(BUDGET_RANGE[0], min(BUDGET_RANGE[1], rng.gauss(1.0, BUDGET_SD))), 3)
        st["jobs"][str(t.id)] = {}
        hc = None
        for job in JOBS:
            c = _new_person(league, rng, TRACK[job], job=job, talent=TALENT_EMPLOYED, rep_sd=REP_START)
            _start_tenure(league, rng, c, job)
            if job != "HC" and TRACK[job] == "coach" and hc and rng.random() < 0.4:
                c["mentor"] = hc["id"]
            _seat(league, c, t.id, job, c["since"], c["through"], c["salary"])
            if job == "HC":
                hc = c
    # Coaches out of work (former head coaches and coordinators, others).
    for track, side, n, level in (("coach", "O", 10, 2), ("coach", "D", 9, 2), ("coach", None, 8, 3),
                                  ("coach", "S", 3, 1), ("strength", None, 6, 1), ("scout", None, 8, 1),
                                  ("medical", None, 4, 1)):
        for _ in range(n):
            c = _new_person(league, rng, track, side=side, talent=TALENT_POOL, rep_sd=REP_START)
            c["out_since"] = league.season - rng.choice((0, 1))
            if level == 3:
                c["exp"]["HC"] = rng.randint(2, 7)
                c["exp"]["coord"] = rng.randint(2, 8)
            elif level == 2:
                c["exp"]["coord"] = rng.randint(1, 6)
    return st


def _new_person(league, rng, track, job=None, side=None, talent=TALENT_NEW, rep_sd=REP_NEW, age=None,
                bg=None):
    st = league.staff
    cid = st["next_id"]
    st["next_id"] += 1
    if age is None:
        a = AGE[job] if job else NEWCOMER_AGE
        age = int(max(a[2], min(a[3], round(rng.gauss(a[0], a[1])))))
    if bg is None and track == "coach":
        bg = _background(rng, job, side)
    level = rng.gauss(talent, TALENT_SD)
    true = {k: _clip(rng.gauss(level, RATING_SD)) for k in RATINGS[track]}
    err = {k: round(rng.gauss(0, rep_sd), 2) for k in true}
    years = max(1, age - 27 - abs(round(rng.gauss(0, 3))))
    c = {"id": cid, "name": f"{rng.choice(names.FIRST_NAMES)} {rng.choice(names.LAST_NAMES)}",
         "born": league.season - age, "track": track, "bg": bg, "true": true, "err": err,
         "style": _style_draw(rng), "team": None, "job": None, "since": None, "through": None, "salary": 0,
         "exp": {"years": years, "HC": 0, "coord": 0}, "record": [], "mentor": None,
         "ambition": int(_clip(rng.gauss(50, 18))), "loyalty": int(_clip(rng.gauss(50, 18))),
         "retired": None, "out_since": None, "interim": False}
    st["coaches"][str(cid)] = c
    return c


def _background(rng, job, side):
    if job == "OC" or side == "O":
        table = OC_BACKGROUND
    elif job == "DC" or side == "D":
        table = DC_BACKGROUND
    elif side == "S":
        return "ST"
    elif job == "HC":
        s = _pick(rng, HC_SIDE)
        return "ST" if s == "S" else _pick(rng, OC_BACKGROUND if s == "O" else DC_BACKGROUND)
    else:
        table = AHC_BACKGROUND
    return _pick(rng, table)


def _style_draw(rng):
    """His style as standard spreads (the sim multiplies by its own spreads,
    sim/tuning.py), drawn once for his career."""
    from .sim import tuning as T
    return {"pass": round(rng.gauss(0, 1), 3), "aggr": round(rng.gauss(0, 1), 3), "man": round(rng.gauss(0, 1), 3),
            "blitz": round(rng.gauss(0, 1), 3), "heavy": round(rng.gauss(0, 1), 3), "fb": round(rng.gauss(0, 1), 3),
            "rb_split": round(rng.gauss(0, 1), 3), "shade": round(rng.gauss(0, 1), 3),
            "pace": round(rng.gauss(0, 1), 3),
            "roles": {slot: round(rng.gauss(0, 1), 3) for slot in T.TARGET_ROLE_BIAS}}


def _start_tenure(league, rng, c, job):
    """A coach already in his job when a league starts: how long he's been there
    and how long his contract runs (head coaches: real tenure lengths)."""
    if job == "HC":
        done = min(12, int(rng.expovariate(1 / 3.0)))       # seasons already coached here (real mean ~4)
        c["exp"]["HC"] = done + (rng.randint(2, 6) if rng.random() < 0.3 else 0)
        c["exp"]["coord"] = rng.randint(2, 8)
    elif job in ("OC", "DC"):
        done = min(8, int(rng.expovariate(1 / 1.8)))
        c["exp"]["coord"] = done + rng.randint(0, 4)
    else:
        done = min(10, int(rng.expovariate(1 / 3.0)))
    c["since"] = league.season - done
    years = _pick(rng, CONTRACT_YEARS[job])
    through = c["since"] + years - 1
    while through < league.season:
        through += _pick(rng, CONTRACT_YEARS[job])       # extended along the way
    c["through"] = through
    c["salary"] = market_value(league, c, job, rng)


def _seat(league, c, tid, job, since, through, salary, interim=False):
    c.update({"team": tid, "job": job, "since": since, "through": through, "salary": int(salary),
              "out_since": None, "interim": interim})
    league.staff["jobs"][str(tid)][job] = c["id"]


def _unseat(league, c):
    jobs = league.staff["jobs"].get(str(c["team"]), {})
    if jobs.get(c["job"]) == c["id"]:
        jobs[c["job"]] = None
    c.update({"team": None, "job": None, "since": None, "through": None, "salary": 0,
              "out_since": league.season, "interim": False})


def _pick(rng, weights):
    r = rng.random() * sum(weights.values())
    for k, w in weights.items():
        r -= w
        if r <= 0:
            return k
    return k


def _clip(v, lo=1, hi=99):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Looking things up
# ---------------------------------------------------------------------------

def coach(league, cid):
    return league.staff["coaches"].get(str(cid)) if cid is not None else None


def staff_of(league, tid):
    """{job: coach or None} for a team."""
    jobs = league.staff["jobs"].get(str(tid), {})
    return {job: coach(league, jobs.get(job)) for job in JOBS}


def age(league, c):
    return league.season - c["born"]


def reputation(c, key):
    """What everyone believes a rating is (shown on screens; the true rating
    is hidden)."""
    if key not in c["true"]:
        return None
    return int(round(_clip(c["true"][key] + c["err"].get(key, 0.0))))


def reputation_score(c, job):
    """His reputation for a job (what teams hire on)."""
    w = JOB_SCORE[job]
    have = {k: reputation(c, k) for k in w if k in c["true"]}
    if not have:
        return 0.0
    tot = sum(w[k] for k in have)
    return sum(have[k] * w[k] for k in have) / tot


def _true_score(c, job):
    w = JOB_SCORE[job]
    have = {k: c["true"][k] for k in w if k in c["true"]}
    tot = sum(w[k] for k in have) or 1
    return sum(have[k] * w[k] for k in have) / tot


def side_of(c):
    bg = c.get("bg")
    return "O" if bg in OFFENSE else "D" if bg in DEFENSE else "S" if bg == "ST" else None


def can_hold(c, job):
    """Can this person do this job (track, and coordinators by side)?"""
    if TRACK[job] != c["track"]:
        return False
    if job == "OC":
        return c.get("bg") in OFFENSE
    if job == "DC":
        return c.get("bg") in DEFENSE
    if job == "HC":
        return c["exp"].get("coord", 0) > 0 or c["exp"].get("HC", 0) > 0 or c.get("college")
    return True


def cap_ratio(league, season=None):
    """Pay and budgets grow with the salary cap."""
    try:
        from . import contracts as C
        if getattr(league, "contracts", None) is None:
            return 1.0
        return C.cap_for(league, season or league.season) / C.cap_for(league, 2026)
    except Exception:
        return 1.0


def market_value(league, c, job, rng=None):
    """What he can ask for this job ($K a year)."""
    base, per, lo, hi = PAY[job]
    v = base + per * (reputation_score(c, job) - 40)
    if job == "HC" and c["exp"].get("HC", 0) > 0:
        v *= 1 + HC_EXPERIENCE_PREMIUM
    v = max(lo, min(hi, v)) * cap_ratio(league)
    if rng is not None:
        v *= rng.uniform(0.95, 1.08)
    return int(round(v / 5) * 5)


def budget(league, tid, season=None):
    """The owner's staff budget for a season ($K)."""
    f = league.staff["owner"].get(str(tid), 1.0)
    return int(BUDGET_BASE * f * cap_ratio(league, season))


def dead_money(league, tid, season=None):
    """Fired coaches still owed this season ($K, less what their new jobs pay)."""
    season = season or league.season
    total = 0
    for d in league.staff["dead"]:
        if d["team"] != tid or not (d["from"] <= season <= d["through"]):
            continue
        c = coach(league, d["cid"])
        offset = c["salary"] if c and c["team"] is not None and (c["through"] or 0) >= season else 0
        total += max(0, d["salary"] - offset)
    return total


def payroll(league, tid, season=None):
    """Staff pay this season against the budget ($K): current staff under
    contract, plus DEAD_IN_BUDGET of what fired coaches are still owed."""
    season = season or league.season
    pay = sum(c["salary"] for c in staff_of(league, tid).values()
              if c and (c["through"] or 0) >= season)
    return pay + int(DEAD_IN_BUDGET * dead_money(league, tid, season))


def room(league, tid, season=None):
    return budget(league, tid, season) - payroll(league, tid, season)


# ---------------------------------------------------------------------------
# What the staff does: development, evaluation, styles
# ---------------------------------------------------------------------------

def _league_dev_stats(league):
    vals = [coach(league, cid)["true"]["dev"] for jobs in league.staff["jobs"].values()
            for job, cid in jobs.items() if cid is not None and job in ("HC", "OC", "DC", "AHC")
            and coach(league, cid)]
    m = sum(vals) / max(1, len(vals))
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)) or 10.0
    return m, sd


NO_SPECIALIST_Z = -1.5        # no coach on the staff from his group: like a weak specialist (PROVISIONAL)
COACH_WEIGHTS = {"spec": 0.55, "coord": 0.22, "hc": 0.15, "sc": 0.08}


def raw_coaching(league, tid, position, dev_stats=None):
    """A team's raw coaching for a position (spreads of the league's coaches'
    development ratings): mostly the best coach on the staff whose background
    is the position's group (FOF8: "a boost when the head or assistant coach
    specializes in the player's position group"), plus his side's coordinator,
    the head coach and, a little, the strength coach."""
    m, sd = dev_stats or _league_dev_stats(league)
    s = staff_of(league, tid)
    group = POSITION_GROUP.get(position, "ST")

    def z(c):
        return (c["true"]["dev"] - m) / sd if c else -1.0
    spec = [c for job in ("HC", "OC", "DC", "AHC") for c in (s[job],) if c and c.get("bg") == group]
    spec_z = max(z(c) for c in spec) if spec else NO_SPECIALIST_Z
    coord = s["OC"] if group in OFFENSE else s["DC"] if group in DEFENSE else (s["AHC"] or s["HC"])
    sc = s["SC"]
    sc_z = ((sc["true"]["dev"] - 50) / 12) if sc else -1.0
    w = COACH_WEIGHTS
    return w["spec"] * spec_z + w["coord"] * z(coord) + w["hc"] * z(s["HC"]) + w["sc"] * sc_z


def coaching_scores(league):
    """{player id: coaching score} for every rostered player (camp rosters
    too): his team's raw coaching at his position, measured against the
    league's rostered players (average 0, spread 1), so a league of average
    staffs develops exactly as before the staff existed. Free agents: 0."""
    if not getattr(league, "staff", None):
        return {}
    stats = _league_dev_stats(league)
    cache = {}
    raw = {}
    for pid, tid in list(league.rosters.items()):
        p = league.player(pid)
        key = (tid, p.position)
        if key not in cache:
            cache[key] = raw_coaching(league, tid, p.position, stats)
        raw[pid] = cache[key]
    if not raw:
        return {}
    vals = list(raw.values())
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)) or 1.0
    return {pid: max(-3.0, min(3.0, (v - m) / sd)) for pid, v in raw.items()}


DEV_NOTE_SEASONS = 4          # "young players" for a coach's development record: pro seasons 1-4
REP_FROM_RESULTS = 0.15       # each camp, a coach's development reputation moves this share toward
                              # what his young players' progress made him look like (luck included)
DEV_PER_SPREAD = 0.6          # about how much more potential a year young players gain under a specialist
                              # one spread better than average (development.COACH_LEAN via the coaching score)


def note_development(league, changes):
    """After training camp (development.training_camp): every coach's record
    gets how his background group's young players moved (potential, versus
    the league's young players in that group), and his development
    reputation moves toward what that made him look like. changes: {pid:
    (overall before, after, potential before, after)}."""
    if not getattr(league, "staff", None):
        return
    from .development import season_number
    league_moves = {}
    team_moves = {}
    for pid, (_o0, _o1, p0, p1) in changes.items():
        p = league.player(pid)
        if season_number(p) > DEV_NOTE_SEASONS + 1:
            continue
        group = POSITION_GROUP.get(p.position, "ST")
        league_moves.setdefault(group, []).append(p1 - p0)
        tid = league.rosters.get(pid)
        if tid is not None:
            team_moves.setdefault((tid, group), []).append(p1 - p0)
    avg = {g: sum(v) / len(v) for g, v in league_moves.items() if v}
    m, sd = _league_dev_stats(league)
    for t in league.teams:
        for job, c in staff_of(league, t.id).items():
            if not c or job not in ("HC", "OC", "DC", "AHC") or not c.get("bg"):
                continue
            moves = team_moves.get((t.id, c["bg"]), [])
            if len(moves) < 2 or c["bg"] not in avg:
                continue
            diff = sum(moves) / len(moves) - avg[c["bg"]]
            c.setdefault("dev_notes", []).append({"season": league.season, "team": t.id, "job": job,
                                                  "group": c["bg"], "n": len(moves), "vs_league": round(diff, 2)})
            looks = m + sd * diff / DEV_PER_SPREAD
            c["err"]["dev"] = round((1 - REP_FROM_RESULTS) * c["err"].get("dev", 0.0)
                                    + REP_FROM_RESULTS * (looks - c["true"]["dev"]), 2)


def _job_z(league, job, key):
    vals = [coach(league, jobs.get(job))["true"][key] for jobs in league.staff["jobs"].values()
            if jobs.get(job) is not None and coach(league, jobs.get(job)) and key in coach(league, jobs.get(job))["true"]]
    m = sum(vals) / max(1, len(vals))
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)) or 10.0
    return m, sd


def eval_z(league, tid, kind, position=None):
    """How well a team's staff reads players, in spreads from the league's
    average staff (0 average, +1 good, -1 poor):
      "own"     its own players (the coach from his group counts most)
      "pro"     other teams' players and free agents (pro personnel director)
      "college" draft prospects (college scouting director)
    An empty job counts as a poor one."""
    if not getattr(league, "staff", None):
        return 0.0
    s = staff_of(league, tid)

    def z(c, job):
        if not c or "eval" not in c["true"]:
            return -1.0
        m, sd = _job_z(league, job, "eval")
        return (c["true"]["eval"] - m) / sd
    if kind == "college":
        return z(s["CS"], "CS")
    if kind == "pro":
        return 0.75 * z(s["PP"], "PP") + 0.25 * z(s["HC"], "HC")
    group = POSITION_GROUP.get(position, "ST")
    spec = [(c, job) for job in ("HC", "OC", "DC", "AHC") for c in (s[job],) if c and c.get("bg") == group]
    spec_z = max(z(c, job) for c, job in spec) if spec else -1.0
    coord_job = "OC" if group in OFFENSE else "DC" if group in DEFENSE else "AHC"
    return 0.5 * spec_z + 0.25 * z(s[coord_job], coord_job) + 0.25 * z(s["HC"], "HC")


def style(league, tid):
    """The team's coaching style for the game sim (standard spreads): the
    offensive coordinator's offense, the defensive coordinator's defense, the
    head coach's 4th-down aggression. None if the team has no staff."""
    if not getattr(league, "staff", None):
        return None
    s = staff_of(league, tid)
    oc = s["OC"] or s["HC"]
    dc = s["DC"] or s["HC"]
    hc = s["HC"] or oc
    if not (oc and dc and hc):
        return None
    out = {k: oc["style"][k] for k in ("pass", "pace", "heavy", "fb", "rb_split")}
    out["roles"] = dict(oc["style"]["roles"])
    out.update({k: dc["style"][k] for k in ("man", "blitz", "shade")})
    out["aggr"] = hc["style"]["aggr"]
    return out


# ---------------------------------------------------------------------------
# The season ends: records, careers
# ---------------------------------------------------------------------------

def record_season(league, lines):
    """Add last season to every employed coach's record (lines: the season's
    team lines: team, season, w, l, t, result, and pf/pa when played)."""
    st = league.staff
    for r in lines:
        for job, c in staff_of(league, r["team"]).items():
            if not c:
                continue
            c["record"].append({"season": r["season"], "team": r["team"], "job": job, "w": r.get("w", 0),
                                "l": r.get("l", 0), "t": r.get("t", 0), "result": r.get("result", ""),
                                "interim": bool(c.get("interim"))})
            c["exp"]["years"] += 1
            if job == "HC" and not c.get("interim"):
                c["exp"]["HC"] += 1
            elif job in ("OC", "DC"):
                c["exp"]["coord"] += 1
    st["last_lines"] = [{k: r.get(k) for k in ("team", "season", "w", "l", "t", "pf", "pa", "result", "seed")}
                        for r in lines]


def _age_year(league, rng):
    """A year older: ability moves with age, reputations drift toward what the
    record shows, some retire, long-unemployed coaches leave for good."""
    gone = []
    for c in league.staff["coaches"].values():
        if c["retired"] is not None:
            continue
        a = age(league, c)
        avg = next(g for lim, g in GROWTH_BY_AGE if a <= lim)
        for k in c["true"]:
            c["true"][k] = round(_clip(c["true"][k] + rng.gauss(avg, GROWTH_SD)), 2)
            c["err"][k] = round(REP_KEEP * c["err"].get(k, 0.0) + rng.gauss(0, REP_NOISE), 2)
        p_retire = _retire_chance(league, c)
        if c["team"] is None:
            p_retire = min(1.0, p_retire * 2)
            if c["out_since"] is not None and league.season - c["out_since"] > OUT_OF_WORK_LIMIT:
                p_retire = 1.0
        if rng.random() < p_retire:
            gone.append(c)
    for c in gone:
        if c["team"] is not None:
            _log(league, c["team"], c, c["job"], "retired")
            _unseat(league, c)
        c["retired"] = league.season
    # Retired coaches stay in the save (records), but the pool would grow forever: drop
    # retired people nobody's record points to after 15 years.
    keep_ids = {d["cid"] for d in league.staff["dead"]}
    for key in [k for k, c in league.staff["coaches"].items()
                if c["retired"] is not None and league.season - c["retired"] > 15 and int(k) not in keep_ids
                and not c["record"]]:
        del league.staff["coaches"][key]


def _retire_chance(league, c):
    """His chance to retire this offseason, by age (in a job)."""
    return 1 / (1 + math.exp(-(age(league, c) - RETIRE_AGE) / RETIRE_SPREAD))


def _log(league, tid, c, job, move, note=""):
    league.staff["log"].append({"season": league.season, "team": tid, "cid": c["id"], "name": c["name"],
                                "job": job, "move": move, "note": note})


def fire(league, tid, job, when=None):
    """Fire a team's coach in a job. He's still owed the rest of his contract
    (less what his next job pays). Returns the coach, or None."""
    c = staff_of(league, tid)[job]
    if not c:
        return None
    if (c["through"] or 0) >= league.season and not c.get("interim"):
        start = league.season if when != "after" else league.season + 1
        if c["through"] >= start:
            league.staff["dead"].append({"cid": c["id"], "team": tid, "from": start, "through": c["through"],
                                         "salary": c["salary"]})
    _log(league, tid, c, job, "fired")
    _unseat(league, c)
    return c


def extend(league, tid, job, years=None, rng=None):
    """Extend a coach in the last year of his contract (or just past it, during
    the coaching phase), at his market value. Returns (ok, message)."""
    c = staff_of(league, tid)[job]
    if not c:
        return False, "Nobody holds that job."
    if c.get("interim"):
        return False, "An interim coach can't be extended; hire him in the carousel instead."
    if c["through"] > league.season:
        return False, "Only a coach in the last year of his contract can be extended."
    pay = market_value(league, c, job)
    old = c["salary"] if c["through"] >= league.season else 0
    if pay - old > room(league, tid) and tid == league.user_team_id:
        return False, "Not enough room in your staff budget."
    years = years or _pick(rng or random.Random(c["id"]), CONTRACT_YEARS[job])
    start = c["through"] + 1 if c["through"] >= league.season else league.season
    c["through"] = start + years - 1
    c["salary"] = pay
    _log(league, tid, c, job, "extended", f"through {c['through']}")
    return True, f"{c['name']} extended through {c['through']} at ${pay / 1000:.2f}M a year."


# ---------------------------------------------------------------------------
# The coaching carousel (the first offseason phase)
# ---------------------------------------------------------------------------

def fire_chance(wins17, tenure, playoffs):
    """Chance an AI team changes its head coach after a season (real table)."""
    row = FIRE_HC["new" if tenure <= 2 else "settled"]
    i = 0 if wins17 < 4.5 else 1 if wins17 < 6.5 else 2 if wins17 < 8.5 else 3 if wins17 < 10.5 else 4
    p = row[i]
    return p * (FIRE_PLAYOFF_MULT if playoffs else 1.0)


def _tenure(league, c):
    """Seasons he has coached this team in this job (including the one just played)."""
    return max(1, league.season - (c["since"] or league.season))


def _wins17(r):
    g = (r.get("w", 0) + r.get("l", 0) + r.get("t", 0)) or 17
    return (r.get("w", 0) + 0.5 * r.get("t", 0)) * 17 / g


def carousel_start(league, lines, rng=None):
    """The season is over (league.season already the new one): records, a year
    older, expiring contracts, AI teams' firings, newcomers. Opens round 1."""
    ensure(league)
    rng = rng or _rng(league, "carousel")
    record_season(league, lines)
    # How many AI head coaches would retire in a typical year like this one (the hiring
    # market below counts retirements against this, so a cluster of them calms firings).
    user = league.user_team_id
    retire_expected = sum(_retire_chance(league, c) for t in league.teams if t.id != user
                          for c in (staff_of(league, t.id)["HC"],) if c and not c.get("interim"))
    _age_year(league, rng)
    by_team = {r["team"]: r for r in lines}
    # Unit ranks for coordinators (points scored / allowed) when the season was played.
    pf_rank = _rank(lines, "pf", reverse=True)
    pa_rank = _rank(lines, "pa", reverse=False)
    expiring_user = []
    # Head coaches first, team by team in random order, with the hiring market's brake.
    # Jobs already open (retirements) and interim coaches count as openings both made
    # and expected, so only the true decisions are steadied.
    ai = [t.id for t in league.teams if t.id != user]
    rng.shuffle(ai)
    opened, expected = 0.0, retire_expected
    for tid in ai:
        hc = staff_of(league, tid)["HC"]
        if not hc or hc.get("interim"):
            if hc:                            # an interim: his team was always going to choose
                fire(league, tid, "HC")
                expected += 1
            opened += 1                       # (a retirement is counted against retire_expected)
            continue
        r = by_team.get(tid, {})
        p = min(0.95, fire_chance(_wins17(r), _tenure(league, hc), bool(r.get("seed"))) * MARKET_LIFT)
        p_now = min(0.95, p * math.exp(-MARKET_K * (opened - expected)))
        expected += p
        if rng.random() < p_now:
            fire(league, tid, "HC")
            opened += 1
    for t in league.teams:
        s = staff_of(league, t.id)
        r = by_team.get(t.id, {})
        if t.id == user:
            expiring_user = [job for job, c in s.items() if c and (c["through"] or 0) < league.season]
            continue
        for job in ("OC", "DC"):
            c = s[job]
            if not c or c["team"] is None:
                continue
            rank = (pf_rank if job == "OC" else pa_rank).get(t.id)
            bad = max(0.0, (rank - 16) / 16) if rank else max(0.0, (8.5 - _wins17(r)) / 8.5)
            if c.get("interim") or rng.random() < FIRE_COORD[0] + FIRE_COORD[1] * bad:
                fire(league, t.id, job)
        for job in ("AHC", "SC", "CS", "PP", "AT"):
            c = s[job]
            if c and c["team"] is not None and (c.get("interim") or rng.random() < OTHER_TURNOVER):
                fire(league, t.id, job)
        # Expiring contracts: AI teams keep whoever they didn't let go, if the
        # owner's budget covers his new price.
        for job, c in staff_of(league, t.id).items():
            if c and (c["through"] or 0) < league.season:
                if market_value(league, c, job) <= room(league, t.id) + 0.15 * budget(league, t.id):
                    extend(league, t.id, job, rng=rng)
                else:
                    _log(league, t.id, c, job, "left", "contract ran out")
                    _unseat(league, c)
    _newcomers(league, rng)
    league.staff["carousel"] = {"round": 1, "offers": {}, "expiring": expiring_user, "results": [],
                                "season": league.season}
    return league.staff["carousel"]


def _rank(lines, key, reverse):
    have = [r for r in lines if r.get(key) is not None]
    if len(have) < len(lines) or not have:
        return {}
    order = sorted(have, key=lambda r: r[key], reverse=reverse)
    return {r["team"]: i + 1 for i, r in enumerate(order)}


def _newcomers(league, rng):
    for (track, side), n in NEWCOMERS.items():
        for _ in range(n):
            if track == "college":
                c = _new_person(league, rng, "coach", side=rng.choice("OD"), talent=TALENT_NEW + 3,
                                age=int(max(38, min(64, rng.gauss(50, 6)))))
                c["college"] = True
            else:
                c = _new_person(league, rng, track, side=side)
            c["out_since"] = league.season
            c["new"] = league.season


def in_carousel(league):
    st = getattr(league, "staff", None)
    return bool(st and st.get("carousel"))


def vacancies(league, tid, upto_round=None):
    """Jobs a team has open now (only those whose round has come, if upto_round)."""
    s = staff_of(league, tid)
    jobs = [j for j in JOBS if s[j] is None]
    if upto_round:
        allowed = {j for r in range(1, upto_round + 1) for j in ROUNDS[r]}
        jobs = [j for j in jobs if j in allowed]
    return jobs


def candidates(league, job, tid=None):
    """Everyone who could take this job now: coaches out of work, and other
    teams' coaches for whom it's a promotion (their teams can't block it)."""
    out = []
    for c in league.staff["coaches"].values():
        if c["retired"] is not None or not can_hold(c, job):
            continue
        if c["team"] is None:
            out.append(c)
        elif c["team"] != tid and LEVEL[job] > LEVEL[c["job"]] and not c.get("interim"):
            out.append(c)
        elif c["team"] == tid and LEVEL[job] > LEVEL[c["job"]]:
            out.append(c)            # an internal promotion
    return out


def _outlook(league, tid):
    r = next((x for x in league.staff.get("last_lines") or () if x["team"] == tid), None)
    if not r:
        return 0.0
    return max(-2.0, min(2.0, (_wins17(r) - 8.5) / 3.0))


def _tie(league, c, tid):
    hc = staff_of(league, tid)["HC"]
    if not hc or hc["id"] == c["id"]:
        return False
    if c.get("mentor") == hc["id"] or hc.get("mentor") == c["id"]:
        return True
    teams_c = {(r["team"], r["season"]) for r in c["record"]}
    return any((r["team"], r["season"]) in teams_c for r in hc["record"])


def utility(league, c, tid, job, salary):
    """How much a candidate likes an offer (higher is better)."""
    m = max(1, market_value(league, c, job))
    cur = LEVEL[c["job"]] if c["team"] is not None else 0
    up = max(0, LEVEL[job] - cur) if c["track"] == "coach" else (1 if c["team"] is None else 0)
    taste = random.Random(f"taste-{c['id']}-{tid}").gauss(0, U_NOISE)
    return (U_MONEY * math.log(max(1, salary) / m) + U_PROMOTION * up + U_OUTLOOK * _outlook(league, tid)
            + (U_TIE if _tie(league, c, tid) else 0.0) + taste)


def _willing(league, c, tid, job, u, last=False):
    if c["team"] is not None:
        return LEVEL[job] > LEVEL[c["job"]] and u >= 0.0
    return u >= (U_ACCEPT_LAST if last else U_ACCEPT_FREE)


def interest(league, cid, tid, job, salary):
    """Rough interest for the screens: 'Very interested' ... 'Not interested'."""
    c = coach(league, cid)
    if not c or not can_hold(c, job):
        return "Can't take this job"
    if c["team"] is not None and LEVEL[job] <= LEVEL[c["job"]]:
        return "Under contract (not a promotion)"
    u = utility(league, c, tid, job, salary)
    return ("Very interested" if u > 1.0 else "Interested" if u > 0.3 else "Lukewarm" if u > -0.4
            else "Not interested")


def make_offer(league, cid, job, salary, years):
    """Your offer to a candidate for one of your open jobs (settled at Next).
    Returns (ok, message)."""
    car = league.staff.get("carousel")
    tid = league.user_team_id
    if not car:
        return False, "The coaching carousel isn't open."
    c = coach(league, cid)
    if not c or not can_hold(c, job):
        return False, "He can't hold that job."
    if job not in vacancies(league, tid):
        return False, f"Your {JOB_NAMES[job].lower()} job isn't open."
    lo = PAY[job][2] * cap_ratio(league)
    if salary < lo:
        return False, f"The least a {JOB_NAMES[job].lower()} makes is ${lo / 1000:.2f}M."
    committed = sum(o["salary"] for k, o in car["offers"].items() if k != str(cid))
    if salary + committed > room(league, tid):
        return False, "That's more than your staff budget has left (counting your other offers)."
    if years not in CONTRACT_YEARS[job] and not (1 <= years <= 6):
        return False, "Contracts run 1 to 6 years."
    car["offers"][str(cid)] = {"job": job, "salary": int(salary), "years": int(years)}
    return True, f"Offer made to {c['name']}."


def withdraw_offer(league, cid):
    car = league.staff.get("carousel")
    if car:
        car["offers"].pop(str(cid), None)


def carousel_next(league, rng=None):
    """Settle the current round (Next). Returns True when the carousel is over."""
    car = league.staff.get("carousel")
    if not car:
        return True
    rng = rng or _rng(league, f"round{car['round']}")
    user = league.user_team_id
    if car["round"] == 1:
        # Your expiring coaches you didn't extend leave now.
        for job in car.get("expiring", ()):
            c = staff_of(league, user)[job] if user is not None else None
            if c and (c["through"] or 0) < league.season:
                _log(league, user, c, job, "left", "contract ran out")
                _unseat(league, c)
        car["expiring"] = []
    r = car["round"]
    for pss in range(PASSES):
        _settle_pass(league, r, rng, use_user_offers=(pss == 0))
    car["offers"] = {}
    if r >= 3:
        _final_fill(league, rng)
        league.staff["last_carousel"] = {"season": league.season, "results": car["results"]}
        league.staff["carousel"] = None
        return True
    car["round"] = r + 1
    return False


def _ai_value(league, c, tid, job):
    noise = random.Random(f"view-{tid}-{c['id']}").gauss(0, AI_VIEW_NOISE)
    v = reputation_score(c, job) + noise
    if job == "HC" and c["exp"].get("HC", 0) > 0:
        v += 2.0
    if _tie(league, c, tid):
        v += 3.0
    return v


def _settle_pass(league, rnd, rng, use_user_offers):
    user = league.user_team_id
    car = league.staff["carousel"]
    offers = {}          # cid -> [(tid, job, salary, years)]
    if use_user_offers and user is not None:
        for cid, o in car["offers"].items():
            if o["job"] in vacancies(league, user):
                offers.setdefault(int(cid), []).append((user, o["job"], o["salary"], o["years"]))
    teams = [t.id for t in league.teams if t.id != user]
    rng.shuffle(teams)
    targeted = {cid: len(v) for cid, v in offers.items()}     # offers each candidate has (at most 3 this pass)
    for tid in teams:
        spend = 0
        for job in vacancies(league, tid, rnd):
            pool = [c for c in candidates(league, job, tid) if targeted.get(c["id"], 0) < 3]
            pool.sort(key=lambda c: _ai_value(league, c, tid, job), reverse=True)
            for c in pool[:15]:
                pay = int(market_value(league, c, job) * rng.uniform(0.98, 1.12))
                if pay + spend > room(league, tid) and pay > PAY[job][2] * cap_ratio(league):
                    continue
                u = utility(league, c, tid, job, pay)
                if not _willing(league, c, tid, job, u):
                    continue
                offers.setdefault(c["id"], []).append((tid, job, pay, _pick(rng, CONTRACT_YEARS[job])))
                targeted[c["id"]] = targeted.get(c["id"], 0) + 1
                spend += pay
                break
    # Each candidate takes the offer he likes best (if he likes any enough).
    for cid in sorted(offers, key=lambda k: -reputation_score(coach(league, k), offers[k][0][1])):
        c = coach(league, cid)
        best = None
        for tid, job, pay, years in offers[cid]:
            if job not in vacancies(league, tid):
                continue
            u = utility(league, c, tid, job, pay)
            if _willing(league, c, tid, job, u) and (best is None or u > best[0]):
                best = (u, tid, job, pay, years)
        if best:
            _, tid, job, pay, years = best
            hire(league, c, tid, job, pay, years, rng)
            car["results"].append({"round": rnd, "team": tid, "job": job, "cid": cid, "name": c["name"],
                                   "salary": pay, "years": years})
        elif any(tid == user for tid, *_ in offers[cid]):
            car["results"].append({"round": rnd, "team": user, "job": None, "cid": cid, "name": c["name"],
                                   "declined": True})


def hire(league, c, tid, job, salary, years, rng=None, sweep=True):
    """He takes the job. If he left another job, it opens. A new head coach of
    an AI team brings his own staff (sweep; not in the final fill, which has no
    round left to replace them)."""
    old_team, old_job = c["team"], c["job"]
    if old_team is not None:
        _log(league, old_team, c, old_job, "left", f"hired as {JOB_NAMES[job].lower()}")
        _unseat(league, c)
    _seat(league, c, tid, job, league.season, league.season + years - 1, salary)
    c.pop("new", None)
    _log(league, tid, c, job, "hired", f"{years} years, ${salary / 1000:.2f}M a year")
    if job == "HC" and tid != league.user_team_id and sweep:
        r = rng or random.Random()
        for j, keep in KEEP_UNDER_NEW_HC.items():
            other = staff_of(league, tid)[j]
            if other and other["id"] != c["id"] and r.random() >= keep:
                fire(league, tid, j)


def _final_fill(league, rng):
    """After the last round: every job still open gets someone (AI teams, and
    your staff's default pick for yours), newcomers if nobody's left."""
    user = league.user_team_id
    teams = [t.id for t in league.teams if t.id != user] + ([user] if user is not None else [])
    for tid in teams:
        for job in vacancies(league, tid):
            pool = [c for c in candidates(league, job, tid) if c["team"] is None]
            pool.sort(key=lambda c: _ai_value(league, c, tid, job), reverse=True)
            chosen = None
            for c in pool[:12]:
                pay = market_value(league, c, job)
                if pay > room(league, tid) and pay > PAY[job][2] * cap_ratio(league):
                    continue
                if _willing(league, c, tid, job, utility(league, c, tid, job, pay), last=True):
                    chosen = (c, pay)
                    break
            if not chosen:
                c = _new_person(league, rng, TRACK[job], job=job,
                                side={"OC": "O", "DC": "D"}.get(job), talent=TALENT_NEW - 4)
                chosen = (c, int(PAY[job][2] * cap_ratio(league)))
            c, pay = chosen
            hire(league, c, tid, job, pay, _pick(rng, CONTRACT_YEARS[job]), rng, sweep=False)
            league.staff["carousel"]["results"].append({"round": 4, "team": tid, "job": job, "cid": c["id"],
                                                        "name": c["name"], "salary": pay, "default": True})


def run_carousel(league, lines, rng=None):
    """The whole carousel at once (tools; your jobs left to your staff's defaults)."""
    carousel_start(league, lines, rng)
    while not carousel_next(league, rng):
        pass


# ---------------------------------------------------------------------------
# During the season
# ---------------------------------------------------------------------------

def fire_in_season(league, tid, job):
    """Fire a coach during the season: someone on the staff takes over as
    interim (for the head coach: the assistant head coach, else a coordinator)
    until the carousel; another job left open gets an interim from the staff's
    assistants. Returns (fired coach, interim)."""
    rng = _rng(league, f"interim-{tid}-{job}-{league.week}")
    c = fire(league, tid, job)
    if not c:
        return None, None
    s = staff_of(league, tid)
    interim = None
    if job == "HC":
        for j in ("AHC", "DC", "OC"):
            if s[j]:
                interim = s[j]
                old = j
                _unseat(league, interim)
                _seat(league, interim, tid, "HC", league.season, league.season, interim["salary"], interim=True)
                _log(league, tid, interim, "HC", "interim")
                _fill_interim(league, rng, tid, old)
                break
    if staff_of(league, tid)[job] is None:
        interim = _fill_interim(league, rng, tid, job)
    return c, interim


def _fill_interim(league, rng, tid, job):
    side = {"OC": "O", "DC": "D"}.get(job)
    c = _new_person(league, rng, TRACK[job], job=job, side=side, talent=TALENT_NEW - 2)
    _seat(league, c, tid, job, league.season, league.season, int(PAY[job][2] * cap_ratio(league)), interim=True)
    _log(league, tid, c, job, "interim")
    return c


def ai_in_season(league, records, rng=None):
    """After a regular-season week: AI teams may fire a head coach off to a bad
    start (real: about 1.5 a season). records: {team id: (w, l, t)} so far.
    Returns [(team id, fired coach, interim)]."""
    if not getattr(league, "staff", None) or not (INSEASON_WEEKS[0] <= league.week <= INSEASON_WEEKS[1]):
        return []
    rng = rng or _rng(league, f"inseason-{league.week}")
    out = []
    for t in league.teams:
        if t.id == league.user_team_id:
            continue
        hc = staff_of(league, t.id)["HC"]
        if not hc or hc.get("interim"):
            continue
        w, l, tie = records.get(t.id, (0, 0, 0))
        g = w + l + tie
        if not g:
            continue
        share = (w + 0.5 * tie) / g
        if share >= 0.40:
            continue
        mult = INSEASON_SETTLED if _tenure(league, hc) >= 3 else INSEASON_NEW
        if rng.random() < INSEASON_BASE * mult * math.exp(INSEASON_K * (0.35 - share)):
            fired, interim = fire_in_season(league, t.id, "HC")
            out.append((t.id, fired, interim))
    return out


# ---------------------------------------------------------------------------
# For the screens
# ---------------------------------------------------------------------------

def view(league, c, tid=None, job=None):
    """Everything a screen may show about a coach (never his true ratings)."""
    job = job or c["job"]
    rec = [r for r in c["record"] if r["job"] == "HC" and not r.get("interim")]
    w = sum(r["w"] for r in rec)
    l_ = sum(r["l"] for r in rec)
    t_ = sum(r["t"] for r in rec)
    return {"id": c["id"], "name": c["name"], "age": age(league, c), "track": c["track"], "bg": c.get("bg"),
            "bg_name": GROUP_NAMES.get(c.get("bg"), ""), "job": c["job"], "team": c["team"],
            "reputation": {k: reputation(c, k) for k in c["true"]},
            "score": round(reputation_score(c, job)) if job else None,
            "through": c["through"], "salary": c["salary"], "interim": c.get("interim", False),
            "exp": dict(c["exp"]), "hc_record": (w, l_, t_), "record": list(c["record"]),
            "mentor": coach(league, c.get("mentor"))["name"] if c.get("mentor") and coach(league, c.get("mentor"))
            else None, "college": bool(c.get("college")), "new": c.get("new") is not None,
            "market": market_value(league, c, job) if job else None}
