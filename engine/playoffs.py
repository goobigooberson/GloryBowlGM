# playoffs.py
# Tiebreakers, playoff seeding and the playoff bracket.
#
# Format (Blake: today's NFL): 7 teams per conference. The 4 division
# winners are seeds 1-4 (by record), the 3 best other teams are wild cards
# 5-7. Only the #1 seed gets a first-round bye.
#   Wild Card round: 2 v 7, 3 v 6, 4 v 5 (better seed at home)
#   Divisional round: #1 v the lowest seed left, the other two play
#     (the NFL re-seeds after every round)
#   Conference championships
#   An off week, then the Glory Bowl (Blake's name for the title game) at
#   a neutral site.
#
# Tiebreakers follow the NFL's procedure:
#   Inside a division: head-to-head, division record, record in common
#     games, conference record, strength of victory, strength of schedule,
#     net points in conference games, net points in all games, coin toss.
#   Between teams from different divisions (wild cards, seeding): only the
#     best team from each division is compared; then head-to-head (only if
#     one team beat or lost to all the others), conference record, common
#     games (at least 4), strength of victory, strength of schedule, net
#     points in conference games, net points in all games, coin toss.
#   With three or more teams tied, as soon as one team is decided the rest
#     start over at the first step (two-team rules if two are left).
# Left out (rarely decide anything): "combined ranking" in points scored and
# allowed, and net touchdowns. The coin toss is a seeded random draw.

import random
from collections import defaultdict

from . import schedule as sched

SEEDS_PER_CONF = 7
ROUND_NAMES = {1: "Wild Card round", 2: "Divisional round", 3: "Conference championships",
               4: "Pro Bowl week", 5: "Glory Bowl"}     # week 4: no playoff games, the Pro Bowl (awards.py)
ROUND_KINDS = {1: "wildcard", 2: "divisional", 3: "conference", 5: "glory_bowl"}
PLAYOFF_ID_START = 2001
CHAMPIONSHIP = "Glory Bowl"
# The Glory Bowl rotates among warm-weather and domed stadiums.
GLORY_BOWL_SITES = ["MIA", "TAM", "NOR", "LAS", "SDG", "PHX", "ATL", "DET", "MIN", "HOU", "DAL", "LVG",
                    "IND", "STL", "SAN"]


def roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def championship_name(league):
    """'Glory Bowl I' for the league's first season, II for the next..."""
    first = league.settings.get("first_season", league.season)
    return f"{CHAMPIONSHIP} {roman(league.season - first + 1)}"


# ---------------------------------------------------------------------------
# What the tiebreakers need from the regular season
# ---------------------------------------------------------------------------

class Results:
    def __init__(self, league):
        self.teams = {t.id: t for t in league.teams}
        self.games = defaultdict(list)       # team -> [(opponent, 1 / 0.5 / 0, pf, pa)]
        for g in league.schedule:
            if not g["played"]:
                continue
            h, a, hs, as_ = g["home"], g["away"], g["home_score"], g["away_score"]
            rh = 1.0 if hs > as_ else (0.5 if hs == as_ else 0.0)
            self.games[h].append((a, rh, hs, as_))
            self.games[a].append((h, 1.0 - rh, as_, hs))
        self.coin = random.Random(f"coin-{league.settings.get('salt', '')}-{league.season}")
        self.coin_order = {tid: self.coin.random() for tid in self.teams}

    def same_div(self, a, b):
        ta, tb = self.teams[a], self.teams[b]
        return ta.conference == tb.conference and ta.division == tb.division

    def same_conf(self, a, b):
        return self.teams[a].conference == self.teams[b].conference

    @staticmethod
    def _pct(results):
        return sum(r for _o, r, _f, _a in results) / len(results) if results else None

    def pct(self, t):
        return self._pct(self.games[t]) or 0.0

    def vs(self, t, opps):
        return self._pct([x for x in self.games[t] if x[0] in opps])

    def div_pct(self, t):
        return self._pct([x for x in self.games[t] if self.same_div(t, x[0])])

    def conf_pct(self, t):
        return self._pct([x for x in self.games[t] if self.same_conf(t, x[0])])

    def common_pct(self, t, group):
        common = None
        for c in group:
            opps = {o for o, *_ in self.games[c]}
            common = opps if common is None else common & opps
        common = (common or set()) - set(group)
        res = [x for x in self.games[t] if x[0] in common]
        return self._pct(res), len(res)

    def sov(self, t):
        beaten = [o for o, r, *_ in self.games[t] for _ in range(int(r * 2)) if r > 0]   # ties count half
        return sum(self.pct(o) for o in beaten) / len(beaten) if beaten else 0.0

    def sos(self, t):
        opps = [o for o, *_ in self.games[t]]
        return sum(self.pct(o) for o in opps) / len(opps) if opps else 0.0

    def net_conf(self, t):
        return sum(f - a for o, _r, f, a in self.games[t] if self.same_conf(t, o))

    def net_all(self, t):
        return sum(f - a for _o, _r, f, a in self.games[t])


# ---------------------------------------------------------------------------
# Breaking ties
# ---------------------------------------------------------------------------

def _best_of(group, res, division):
    """The team that wins a tie among `group` (all on the same win pct)."""
    group = list(group)
    while len(group) > 1:
        steps = _division_steps(group, res) if division else _wildcard_steps(group, res)
        for step in steps:
            vals = {t: step(t) for t in group}
            if any(v is None for v in vals.values()):
                continue                       # this step doesn't apply to this group
            top = max(vals.values())
            best = [t for t in group if abs(vals[t] - top) < 1e-9]
            if len(best) < len(group):
                if len(best) == 1:
                    return best[0]
                group = best                   # some dropped out: start over with the rest
                break
        else:
            return max(group, key=lambda t: res.coin_order[t])   # coin toss
    return group[0]


def _division_steps(group, res):
    others = lambda t: [o for o in group if o != t]
    return [
        lambda t: res.vs(t, others(t)),                    # head-to-head
        lambda t: res.div_pct(t),
        lambda t: res.common_pct(t, group)[0],
        lambda t: res.conf_pct(t),
        lambda t: res.sov(t),
        lambda t: res.sos(t),
        lambda t: res.net_conf(t),
        lambda t: res.net_all(t),
    ]


def _wildcard_steps(group, res):
    def results_vs(u, o):
        return [x[1] for x in res.games[u] if x[0] == o]

    def beat_all(u):
        return all(results_vs(u, o) and all(r == 1.0 for r in results_vs(u, o)) for o in group if o != u)

    def lost_to_all(u):
        return all(results_vs(u, o) and all(r == 0.0 for r in results_vs(u, o)) for o in group if o != u)

    def h2h(t):
        others = [o for o in group if o != t]
        if len(group) == 2:
            return res.vs(t, others)           # None if they didn't play
        # Three or more: only a sweep counts (one team beat all the others,
        # or one lost to all the others).
        if any(beat_all(u) for u in group):
            return 1.0 if beat_all(t) else 0.0
        if any(lost_to_all(u) for u in group):
            return 0.0 if lost_to_all(t) else 1.0
        return None

    def common(t):
        p, n = res.common_pct(t, group)
        return p if n >= 4 else None

    return [h2h, lambda t: res.conf_pct(t), common, lambda t: res.sov(t), lambda t: res.sos(t),
            lambda t: res.net_conf(t), lambda t: res.net_all(t)]


def order(teams, res, division):
    """Rank teams best first: by win percentage, ties broken by the NFL steps."""
    remaining = list(teams)
    out = []
    while remaining:
        top = max(res.pct(t) for t in remaining)
        tied = [t for t in remaining if abs(res.pct(t) - top) < 1e-9]
        if not division:
            # Only the best team from each division takes part.
            by_div = defaultdict(list)
            for t in tied:
                by_div[(res.teams[t].conference, res.teams[t].division)].append(t)
            tied = [_best_of(g, res, True) for g in by_div.values()]
        pick = _best_of(tied, res, division)
        out.append(pick)
        remaining.remove(pick)
    return out


def division_order(league, res=None):
    """{conference: {division: [team ids, first place first]}} with real tiebreakers."""
    res = res or Results(league)
    out = {}
    for conf, divs in sched.divisions(league).items():
        names = sorted({t.division for t in league.teams if t.conference == conf})
        out[conf] = {name: order(div, res, True) for name, div in zip(names, divs)}
    return out


def seeds(league):
    """{conference: [7 team ids, seed 1 first]}."""
    res = Results(league)
    divs = division_order(league, res)
    out = {}
    for conf, by_div in divs.items():
        winners = [ids[0] for ids in by_div.values()]
        rest = [t for ids in by_div.values() for t in ids[1:]]
        out[conf] = order(winners, res, False) + order(rest, res, False)[:SEEDS_PER_CONF - 4]
    return out


def division_ranks(league):
    """{team id: 0-3 place in division} for next season's schedule."""
    ranks = {}
    for by_div in division_order(league).values():
        for ids in by_div.values():
            for r, tid in enumerate(ids):
                ranks[tid] = r
    return ranks


# ---------------------------------------------------------------------------
# The bracket
# ---------------------------------------------------------------------------

def seed_of(league, tid):
    for conf, ids in (league.playoff_seeds or {}).items():
        if tid in ids:
            return ids.index(tid) + 1
    return None


def _game(league, rnd, home, away, neutral=False):
    gid = PLAYOFF_ID_START + len(league.playoffs)
    return {"id": gid, "week": rnd, "home": home, "away": away, "kind": ROUND_KINDS[rnd],
            "neutral": neutral, "played": False, "home_score": None, "away_score": None, "overtime": False}


def winner(g):
    return g["home"] if g["home_score"] > g["away_score"] else g["away"]


def loser(g):
    return g["away"] if g["home_score"] > g["away_score"] else g["home"]


def make_round(league, rnd):
    """Add the games of a playoff round to league.playoffs (rounds 1, 2, 3, 5)."""
    S = league.playoff_seeds
    confs = sorted(S)
    new = []
    if rnd == 1:
        for conf in confs:
            s = S[conf]
            for hi, lo in ((2, 7), (3, 6), (4, 5)):
                new.append(_game(league, 1, s[hi - 1], s[lo - 1]))
                league.playoffs.append(new[-1])
    elif rnd in (2, 3):
        prev = [g for g in league.playoffs if g["week"] == rnd - 1]
        for conf in confs:
            alive = [t for t in S[conf] if t in {winner(g) for g in prev}]
            if rnd == 2:
                alive = [S[conf][0]] + alive                  # the #1 seed had the bye
            alive.sort(key=lambda t: S[conf].index(t))
            # Re-seed: best seed hosts the lowest seed left.
            while alive:
                hi, lo = alive[0], alive[-1]
                g = _game(league, rnd, hi, lo)
                league.playoffs.append(g)
                new.append(g)
                alive = alive[1:-1]
    elif rnd == 5:
        champs = [winner(g) for g in league.playoffs if g["week"] == 3]
        # Neutral site; the "home" team alternates by year between conferences.
        home_first = league.season % 2 == 0
        a, b = champs[0], champs[1]
        g = _game(league, 5, a if home_first else b, b if home_first else a, neutral=True)
        league.playoffs.append(g)
        new.append(g)
    return new


def glory_bowl_site(league):
    """Host stadium (team abbreviation) for this season's Glory Bowl."""
    rng = random.Random(f"glory-bowl-{league.settings.get('salt', '')}-{league.season}")
    return rng.choice(GLORY_BOWL_SITES)


def champion(league):
    g = next((x for x in league.playoffs if x["week"] == 5 and x["played"]), None)
    return winner(g) if g else None


def round_date(league, rnd):
    """Sunday of a playoff round (the week after the last regular-season week)."""
    n_weeks = league.settings.get("season_games", 17) + 1
    return sched.week_sunday(league.season, n_weeks + rnd)
