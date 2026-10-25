# schedule.py
# Builds a season's schedule the way the NFL does (Blake: real NFL formula).
# The whole schedule is made at once, before the season, so every team
# knows all its games in advance (Blake). For now that happens when a new
# league starts; once the offseason exists it happens before training camp
# (the real NFL releases its schedule in mid-May).
#
# Who plays whom (17 games):
#   6  division games: each division rival twice, home and away
#   4  every team in one other division of your conference (rotates, 3 years)
#   4  every team in one division of the other conference (rotates, 4 years)
#   2  the teams that finished in the same place last season in the other two
#      divisions of your conference
#   1  (17-game seasons only) the same-place team in a division of the other
#      conference you aren't otherwise playing (rotates); the home conference
#      alternates by year
# That gives every team 8 or 9 home games.
#
# When (weeks): one bye per team, in weeks 5-14 (5-13 in a 16-game season),
# no more than 6 teams off in any week; the final week is all division
# games; no team plays three road games in a row or three home games in a
# row (a bye breaks a streak); the two games against a division rival are
# never in back-to-back weeks.
#
# "Finished in the same place" needs last season's standings. A league's
# first season has none, so the order inside each division is drawn at random.
#
# How the weeks get filled (a standard sports-scheduling method):
#   1. Put every game in a week so no team plays twice in a week. When a game
#      won't fit, a "chain swap" makes room: two weeks trade a linked chain of
#      games (A's week-3 game becomes week 7, so his week-7 opponent's week-7
#      game becomes week 3, and so on), which never double-books anyone.
#   2. Keep making chain swaps that move byes into weeks 5-14 and break up
#      three-game home or road runs, until every rule holds.

import math
import random
from datetime import date, timedelta

# Intra-conference division pairings, one per year of the 3-year cycle
# (division indexes 0-3 inside a conference).
INTRA_ROTATION = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
MAX_BYES_PER_WEEK = 6
SEARCH_STEPS = 100000     # chain swaps tried per attempt in step 2 (usually done in 1-2 seconds)
MAX_ATTEMPTS = 10


def divisions(league):
    """{conference: [[team ids of division 0], [division 1], ...]} in a fixed order."""
    out = {}
    for conf in sorted({t.conference for t in league.teams}):
        names = sorted({t.division for t in league.teams if t.conference == conf})
        out[conf] = [[t.id for t in league.teams if t.conference == conf and t.division == d] for d in names]
    return out


def random_division_ranks(league, rng):
    """First season: a random 'last season' finishing order in each division."""
    ranks = {}
    for divs in divisions(league).values():
        for div in divs:
            order = list(div)
            rng.shuffle(order)
            for r, tid in enumerate(order):
                ranks[tid] = r
    return ranks


def matchups(league, year, ranks, season_games=17):
    """Every game of the season as (home id, away id, kind), kind being
    'division', 'conference', 'interconference', 'place' or 'extra'."""
    divs = divisions(league)
    confs = sorted(divs)
    games = []

    def by_rank(div):
        return sorted(div, key=lambda tid: ranks[tid])

    def full_set(div_a, div_b, kind, cycle_len):
        # Every team in A plays every team in B; 2 home, 2 away each. Who
        # hosts flips each time the rotation brings these divisions back
        # together (every 3 or 4 years), so over two cycles every team plays
        # at every other team's stadium, as in the NFL.
        # A fixed team order (not last season's finish, which changes every
        # year) so the flip works out.
        a, b = sorted(div_a), sorted(div_b)
        turn = year // cycle_len
        for i, ta in enumerate(a):
            for j, tb in enumerate(b):
                games.append((ta, tb, kind) if (i + j + turn) % 2 == 0 else (tb, ta, kind))

    for conf in confs:
        for div in divs[conf]:
            for i, ta in enumerate(div):
                for tb in div[i + 1:]:
                    games.append((ta, tb, "division"))
                    games.append((tb, ta, "division"))
        pairs = INTRA_ROTATION[year % 3]
        for a, b in pairs:
            full_set(divs[conf][a], divs[conf][b], "conference", 3)
        # Same-place games against the two divisions not paired with yours.
        # Hosting goes around a cycle so every team gets one home, one away.
        (a, b), (c, d) = pairs
        cycle = [a, c, b, d] if year % 2 == 0 else [a, d, b, c]
        for k in range(4):
            host_div, visit_div = divs[conf][cycle[k]], divs[conf][cycle[(k + 1) % 4]]
            for h, v in zip(by_rank(host_div), by_rank(visit_div)):
                games.append((h, v, "place"))

    east, west = confs[0], confs[1]
    for i in range(4):
        full_set(divs[east][i], divs[west][(i + year) % 4], "interconference", 4)
    if season_games >= 17:
        host_conf = east if year % 2 == 0 else west
        for i in range(4):
            e_div, w_div = divs[east][i], divs[west][(i + year + 2) % 4]
            for te, tw in zip(by_rank(e_div), by_rank(w_div)):
                games.append((te, tw, "extra") if host_conf == east else (tw, te, "extra"))
    return games


def _final_week(league, games, rng):
    """One division game for every team: in each division, a random pairing
    and a random home team for each pair. Returns the chosen game indexes."""
    chosen = []
    for divs in divisions(league).values():
        for div in divs:
            t = list(div)
            rng.shuffle(t)
            for x, y in ((t[0], t[1]), (t[2], t[3])):
                options = [gi for gi, (h, a, k) in enumerate(games) if k == "division" and {h, a} == {x, y}]
                chosen.append(rng.choice(options))
    return chosen


class _Weeks:
    """Which game each team plays in each week, with no team ever booked
    twice in a week. The final week is set first and never changes."""

    def __init__(self, games, team_ids, n_weeks, rng):
        self.games, self.teams, self.W, self.rng = games, team_ids, n_weeks, rng
        self.week = {}                                        # game index -> week
        self.at = {t: [None] * (n_weeks + 1) for t in team_ids}   # team -> week -> game index

    def put(self, gi, w):
        h, a, _k = self.games[gi]
        self.week[gi] = w
        self.at[h][w] = gi
        self.at[a][w] = gi

    def other(self, gi, t):
        h, a, _k = self.games[gi]
        return a if h == t else h

    def chain(self, t, w1, w2):
        """Every game linked to team t through weeks w1 and w2."""
        seen_t, out, stack = {t}, set(), [t]
        while stack:
            u = stack.pop()
            for w in (w1, w2):
                gi = self.at[u][w]
                if gi is not None and gi not in out:
                    out.add(gi)
                    o = self.other(gi, u)
                    if o not in seen_t:
                        seen_t.add(o)
                        stack.append(o)
        return out, seen_t

    def swap(self, gis, w1, w2):
        """Trade the chain's games between weeks w1 and w2."""
        for gi in gis:
            h, a, _k = self.games[gi]
            self.at[h][self.week[gi]] = None
            self.at[a][self.week[gi]] = None
        for gi in gis:
            self.put(gi, w2 if self.week[gi] == w1 else w1)

    # ---- step 1: one game per team per week --------------------------------
    def insert(self, gi):
        """Place one game without double-booking anyone. Returns False if it
        can't be done right now."""
        rng = self.rng
        h, a, _k = self.games[gi]
        weeks = list(range(1, self.W))
        rng.shuffle(weeks)
        for w in weeks:
            if self.at[h][w] is None and self.at[a][w] is None:
                self.put(gi, w)
                return True
        free_h = [w for w in weeks if self.at[h][w] is None]
        free_a = [w for w in weeks if self.at[a][w] is None]
        for alpha in free_h:            # week open for h
            for beta in free_a:          # week open for a
                # Swap a's chain on (alpha, beta): a's alpha game moves to
                # beta, which frees alpha for a, unless the chain reaches h.
                gis, members = self.chain(a, alpha, beta)
                if h in members:
                    continue
                self.swap(gis, alpha, beta)
                self.put(gi, alpha)
                return True
        return False

    # ---- step 2: byes and home/road runs ------------------------------------
    @property
    def bye_lo(self):
        return 5

    @property
    def bye_hi(self):
        return self.W - 4

    def _run_weeks(self, t):
        """Weeks (before the final week) inside a run of 3+ home or road games."""
        out, last, run, weeks = [], None, 0, []
        for w in range(1, self.W + 1):
            gi = self.at[t][w]
            if gi is None:
                last, run, weeks = None, 0, []
                continue
            side = "H" if self.games[gi][0] == t else "A"
            if side == last:
                run += 1
                weeks.append(w)
            else:
                last, run, weeks = side, 1, [w]
            if run >= 3:
                out.extend(x for x in weeks if x < self.W)
        return out

    def team_cost(self, t):
        # (Oct 25, for speed: the search asks this ~1.5 million times a schedule; one pass
        # over the weeks with the lookups done once. The same count as before.)
        bye_lo, bye_hi = self.bye_lo, self.bye_hi
        at, games, W = self.at[t], self.games, self.W
        bad_bye = 0
        streak, last, run = 0, None, 0
        prev_opp, rematch = None, 0
        for w in range(1, W + 1):
            gi = at[w]
            if gi is None:
                if w < W and not (bye_lo <= w <= bye_hi):
                    bad_bye += 1
                last, run, prev_opp = None, 0, None
                continue
            h, a, _k = games[gi]
            home = h == t
            run = run + 1 if home is last else 1
            last = home
            if run >= 3:
                streak += 1
            # Division rival twice in back-to-back weeks: the NFL spaces these out.
            opp = a if home else h
            if opp == prev_opp:
                rematch += 1
            prev_opp = opp
        return 3 * bad_bye + 2 * streak + 2 * rematch

    def bye_over(self, w):
        byes = sum(1 for t in self.teams if self.at[t][w] is None)
        return 3 * max(0, byes - MAX_BYES_PER_WEEK)

    def polish(self, steps):
        rng = self.rng
        tcost = {t: self.team_cost(t) for t in self.teams}
        over = {w: self.bye_over(w) for w in range(1, self.W)}
        cost = sum(tcost.values()) + sum(over.values())
        for step in range(steps):
            if cost == 0:
                return True
            bad = [t for t in self.teams if tcost[t] > 0]
            busy_weeks = [w for w, v in over.items() if v > 0]
            if bad and (not busy_weeks or rng.random() < 0.8):
                t = rng.choice(bad)
                bye = next(w for w in range(1, self.W) if self.at[t][w] is None)
                if not (self.bye_lo <= bye <= self.bye_hi):
                    # A bye in the wrong week: trade it toward weeks 5-14.
                    w1, w2 = bye, rng.randint(self.bye_lo, self.bye_hi)
                else:
                    # A three-game home or road run: move one of its games.
                    # Often the best move is trading weeks with the rematch
                    # against the same division rival, which flips home and
                    # road for both teams in those two weeks and nothing else.
                    w1 = rng.choice(self._run_weeks(t) or [rng.randrange(1, self.W)])
                    w2 = rng.randrange(1, self.W)
                    gi = self.at[t][w1]
                    if gi is not None and self.games[gi][2] == "division" and rng.random() < 0.5:
                        o = self.other(gi, t)
                        rematch = [w for w in range(1, self.W)
                                   if w != w1 and self.at[t][w] is not None and self.other(self.at[t][w], t) == o]
                        if rematch:
                            w2 = rematch[0]
            else:
                w1 = rng.choice(busy_weeks)
                t = rng.choice([x for x in self.teams if self.at[x][w1] is None])
                w2 = rng.randrange(1, self.W)
            if w2 == w1:
                continue
            gis, members = self.chain(t, w1, w2)
            if not gis:
                continue
            before = sum(tcost[m] for m in members) + over[w1] + over[w2]
            self.swap(gis, w1, w2)
            new_t = {m: self.team_cost(m) for m in members}
            new_o = {w1: self.bye_over(w1), w2: self.bye_over(w2)}
            delta = sum(new_t.values()) + sum(new_o.values()) - before
            # Annealing: early on, worse moves are often taken (to escape dead
            # ends); toward the end almost never.
            temp = 3.0 * (1 - step / steps) + 0.05
            if delta <= 0 or rng.random() < math.exp(-delta / temp):
                tcost.update(new_t)
                over.update(new_o)
                cost += delta
            else:
                self.swap(gis, w1, w2)       # undo
        return cost == 0


def _try_once(league, games, team_ids, n_weeks, rng):
    weeks = _Weeks(games, team_ids, n_weeks, rng)
    final = _final_week(league, games, rng)
    for gi in final:
        weeks.put(gi, n_weeks)
    rest = [gi for gi in range(len(games)) if gi not in set(final)]
    rng.shuffle(rest)
    for gi in rest:
        if not weeks.insert(gi):
            return None
    if not weeks.polish(SEARCH_STEPS):
        return None
    return weeks


def build_schedule(league, year, ranks, season_games=17, rng=None):
    """The full season, built all at once: a list of games, each a dict with
    id, week, home, away, kind, played (False) and scores (None)."""
    rng = rng or random.Random()
    games = matchups(league, year, ranks, season_games)
    team_ids = [t.id for t in league.teams]
    n_weeks = season_games + 1
    for _ in range(MAX_ATTEMPTS):
        weeks = _try_once(league, games, team_ids, n_weeks, rng)
        if weeks is not None:
            break
    else:
        raise RuntimeError("Couldn't build a schedule (this shouldn't happen; please report it).")
    placed = sorted((weeks.week[gi], games[gi][0], games[gi][1], games[gi][2]) for gi in range(len(games)))
    return [{"id": i, "week": w, "home": h, "away": a, "kind": k,
             "played": False, "home_score": None, "away_score": None, "overtime": False}
            for i, (w, h, a, k) in enumerate(placed, start=1)]


# ---------------------------------------------------------------------------
# Preseason (Blake): 5 weeks, set in advance like the NFL's.
#   Week 1: the Hall of Fame Game only: one Eastern vs one Western team at a
#           neutral site (Canton, Ohio). Those two teams get a bye in one of
#           the other preseason weeks, so every team plays 4 preseason games.
#   Weeks 2-5: everyone else plays every week. 2 home and 2 away each (the
#           Hall of Fame teams: their Canton game plus 3 more). Opponents are
#           mostly nearby teams, as in the real NFL; never a division rival,
#           never your week-1 regular-season opponent, nobody twice.
# Preseason games don't count in the standings.
# ---------------------------------------------------------------------------

PRESEASON_WEEKS = 5
PRESEASON_ID_START = 1001       # preseason game ids (regular season games are 1-272)
HOF_SITE = "Canton, Ohio"

# Rough map position of each team's city (latitude, longitude), for regional matchups.
CITY_COORDS = {
    "BOS": (42.4, -71.1), "NYK": (40.8, -74.1), "PHI": (39.9, -75.2), "BUF": (42.9, -78.9),
    "BAL": (39.3, -76.6), "WAS": (38.9, -77.0), "PIT": (40.4, -80.0), "CIN": (39.1, -84.5),
    "CLE": (41.5, -81.7), "DET": (42.3, -83.0), "CHI": (41.9, -87.6), "IND": (39.8, -86.2),
    "CHA": (35.2, -80.8), "ATL": (33.8, -84.4), "MIA": (25.8, -80.2), "TAM": (28.0, -82.5),
    "MIN": (45.0, -93.3), "KCY": (39.1, -94.6), "STL": (38.6, -90.2), "NSH": (36.2, -86.8),
    "HOU": (29.8, -95.4), "DAL": (32.8, -96.8), "SAN": (29.4, -98.5), "NOR": (30.0, -90.1),
    "SEA": (47.6, -122.3), "POR": (45.5, -122.7), "SFO": (37.8, -122.4), "DEN": (39.7, -105.0),
    "LAS": (34.1, -118.3), "SDG": (32.7, -117.2), "LVG": (36.2, -115.1), "PHX": (33.4, -112.1),
}


def _miles(a, b):
    (la1, lo1), (la2, lo2) = CITY_COORDS.get(a, (39, -95)), CITY_COORDS.get(b, (39, -95))
    p1, p2 = math.radians(la1), math.radians(la2)
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 3959 * 2 * math.asin(math.sqrt(d))


def build_preseason(league, year, regular_schedule, rng=None):
    """The whole preseason, built at once. Each game is a dict like a
    regular-season game, with kind 'hof' or 'preseason' and neutral True for
    the Hall of Fame Game. Week numbers are preseason weeks 1-5."""
    rng = rng or random.Random()
    teams = {t.id: t for t in league.teams}
    abbrev = {t.id: t.abbrev for t in league.teams}
    week1_opp = {}
    for g in regular_schedule:
        if g["week"] == 1:
            week1_opp[g["home"]], week1_opp[g["away"]] = g["away"], g["home"]

    def allowed(a, b, met):
        ta, tb = teams[a], teams[b]
        if ta.conference == tb.conference and ta.division == tb.division:
            return False
        return frozenset((a, b)) not in met and week1_opp.get(a) != b

    for _attempt in range(500):
        east = [t.id for t in league.teams if t.conference == sorted({x.conference for x in league.teams})[0]]
        west = [t.id for t in league.teams if t.id not in east]
        hof = [rng.choice(east), rng.choice(west)]
        rng.shuffle(hof)
        hof_bye = rng.randint(2, PRESEASON_WEEKS)
        met = {frozenset(hof)}
        home_n = {t: 0 for t in teams}
        away_n = {t: 0 for t in teams}
        games = [(1, hof[0], hof[1], "hof")]
        ok = True
        for week in range(2, PRESEASON_WEEKS + 1):
            avail = [t for t in teams if not (t in hof and week == hof_bye)]
            pairs = _preseason_week(avail, allowed, met, home_n, away_n, abbrev, rng)
            if pairs is None:
                ok = False
                break
            for h, a in pairs:
                met.add(frozenset((h, a)))
                home_n[h] += 1
                away_n[a] += 1
                games.append((week, h, a, "preseason"))
        if ok:
            break
    else:
        raise RuntimeError("Couldn't build a preseason schedule (this shouldn't happen; please report it).")
    return [{"id": PRESEASON_ID_START + i, "week": w, "home": h, "away": a, "kind": k, "neutral": k == "hof",
             "played": False, "home_score": None, "away_score": None, "overtime": False}
            for i, (w, h, a, k) in enumerate(games)]


def _preseason_week(avail, allowed, met, home_n, away_n, abbrev, rng):
    """Pair up every available team for one preseason week, nearby teams
    first (with some randomness). Returns [(home, away)] or None."""
    def can(a, b):
        # Someone has to be able to host and the other to travel (2 and 2).
        return allowed(a, b, met) and ((home_n[a] < 2 and away_n[b] < 2) or (home_n[b] < 2 and away_n[a] < 2))

    order = list(avail)
    rng.shuffle(order)
    pairs = []
    used = set()
    budget = [3000]       # give up on this try after this many steps (the caller starts over)

    def solve():
        free = [t for t in order if t not in used]
        if not free:
            return True
        budget[0] -= 1
        if budget[0] <= 0:
            return False
        t = min(free, key=lambda x: sum(1 for o in free if o != x and can(x, o)))
        opts = [o for o in free if o != t and can(t, o)]
        # Nearby first: distance with a random stretch, so matchups vary year to year.
        opts.sort(key=lambda o: _miles(abbrev[t], abbrev[o]) * rng.uniform(0.6, 1.6))
        for o in opts[:5]:
            used.update((t, o))
            pairs.append((t, o))
            if solve():
                return True
            pairs.pop()
            used.difference_update((t, o))
        return False

    if not solve():
        return None
    out = []
    for a, b in pairs:
        a_hosts = home_n[a] < 2 and away_n[b] < 2
        b_hosts = home_n[b] < 2 and away_n[a] < 2
        if a_hosts and b_hosts:
            # The team with fewer home games so far hosts (coin flip if even).
            a_hosts = (home_n[a], rng.random()) < (home_n[b], rng.random())
        out.append((a, b) if a_hosts else (b, a))
    return out


def preseason_date(year, week):
    """Preseason games: the Hall of Fame Game is a Thursday in early August;
    the last preseason week is the Thursday before Labor Day."""
    last = week_sunday(year, 1) - timedelta(days=10)          # Thursday before Labor Day
    return last - timedelta(days=7 * (PRESEASON_WEEKS - week))


def week_sunday(year, week):
    """The Sunday of a regular-season week. The season opens the weekend
    after Labor Day (the first Monday of September)."""
    sept1 = date(year, 9, 1)
    labor_day = sept1 + timedelta(days=(0 - sept1.weekday()) % 7)
    return labor_day + timedelta(days=6 + 7 * (week - 1))
