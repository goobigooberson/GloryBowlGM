# storylines.py
# What's building over the weeks of a season, for the News tab: player
# streaks, team form, turnarounds and collapses, how a team has done since
# losing a key player, players back from injury, breakouts and slumps,
# record paces, division races, the race for the No. 1 pick, power rankings,
# previews, MVP and rookie watches.
#
# Everything is worked out from one season's played games (box scores) and
# the league's records, "as of" a given week, so a story written about Week 7
# only knows what was true after Week 7. engine/news.py turns these facts into
# words (engine/news_words.py). Nothing here changes the league.

from collections import defaultdict

from . import injuries as I
from .sim.stats import passer_rating

# Streaks worth a story: (key, test on one game line, singular, plural, story at this many,
# also mention inside game stories from this many).
STREAKS = [
    ("rush100", lambda s: s.get("rush_yds", 0) >= 100, "100-yard rushing game", "100-yard rushing games", 3),
    ("rec100", lambda s: s.get("rec_yds", 0) >= 100, "100-yard receiving game", "100-yard receiving games", 3),
    ("pass300", lambda s: s.get("pass_yds", 0) >= 300, "300-yard passing game", "300-yard passing games", 3),
    ("pass2td", lambda s: s.get("pass_td", 0) >= 2, "game with at least two touchdown passes",
     "games with at least two touchdown passes", 5),
    ("td", lambda s: s.get("rush_td", 0) + s.get("rec_td", 0) >= 1, "game with a touchdown",
     "games with a touchdown", 5),
    ("sack", lambda s: s.get("sacks", 0) >= 1, "game with a sack", "games with a sack", 5),
    ("int", lambda s: s.get("def_int", 0) >= 1, "game with an interception", "games with an interception", 3),
]

# Season paces worth a story (stat, mark), from Week 8 on.
PACE_MARKS = {"rush_yds": 2000, "pass_yds": 5000, "rec_yds": 1800, "sacks": 20, "pass_td": 45, "rush_td": 20,
              "rec_td": 17, "def_int": 11}

# Power rankings: how much each part counts.
RANK_PCT, RANK_DIFF, RANK_FORM = 100, 0.8, 10


def rec_of(results):
    """(w, l, t) from a list of 'W'/'L'/'T'."""
    return (results.count("W"), results.count("L"), results.count("T"))


def rec_text(r):
    return f"{r[0]}-{r[1]}" + (f"-{r[2]}" if r[2] else "")


def pct(r):
    g = r[0] + r[1] + r[2]
    return (r[0] + 0.5 * r[2]) / g if g else 0.0


class SeasonTrack:
    """One season's played regular-season games, searchable by player, team and week."""

    def __init__(self, ctx, season, games):
        self.ctx = ctx
        self.season = season
        self.schedule = [g for ph, g, _b in games if ph == "regular"]
        self.player_games = defaultdict(list)    # pid -> [(week, game, team, line)]
        self.team_games = defaultdict(list)      # tid -> [(week, game, opp, pf, pa, box index)]
        self.boxes = {}
        played = sorted(((g, b) for ph, g, b in games if ph == "regular" and g.get("played") and b),
                        key=lambda x: (x[0]["week"], x[0]["id"]))
        for g, b in played:
            self.boxes[g["id"]] = b
            for idx, tid, opp, pf, pa in ((0, g["home"], g["away"], g["home_score"], g["away_score"]),
                                          (1, g["away"], g["home"], g["away_score"], g["home_score"])):
                self.team_games[tid].append((g["week"], g, opp, pf, pa, idx))
            for pid_s, line in b.get("players", {}).items():
                self.player_games[int(pid_s)].append((g["week"], g, line.get("team"), line))
        self.weeks = sorted({g["week"] for g, _b in played})
        self._injuries = None

    # ---- players ----
    def games_of(self, pid, upto):
        return [x for x in self.player_games.get(pid, ()) if x[0] <= upto]

    def totals(self, pid, upto):
        t = defaultdict(float)
        for _w, _g, _tid, s in self.games_of(pid, upto):
            for k, v in s.items():
                if k != "team" and isinstance(v, (int, float)):
                    t[k] = max(t[k], v) if k.endswith("_long") else t[k] + v
        return t

    def streak(self, pid, upto, test):
        """Consecutive games he played, ending with his game in week `upto`, that pass the test."""
        gs = self.games_of(pid, upto)
        if not gs or gs[-1][0] != upto:
            return 0
        n = 0
        for _w, _g, _tid, s in reversed(gs):
            if not test(s):
                break
            n += 1
        return n

    def streaks_for(self, pid, upto):
        """[(key, n, singular, plural, story_at)] streaks alive after his game in week `upto`."""
        out = []
        for key, test, one, many, at in STREAKS:
            n = self.streak(pid, upto, test)
            if n >= 2:
                out.append((key, n, one, many, at))
        return out

    # ---- teams ----
    def results(self, tid, upto, since=0):
        out = []
        for w, g, _opp, pf, pa, _i in self.team_games.get(tid, ()):
            if since < w <= upto:
                out.append("W" if pf > pa else "L" if pf < pa else "T")
        return out

    def record(self, tid, upto, since=0):
        return rec_of(self.results(tid, upto, since))

    def points(self, tid, upto, since=0):
        pf = pa = n = 0
        for w, _g, _opp, f, a, _i in self.team_games.get(tid, ()):
            if since < w <= upto:
                pf, pa, n = pf + f, pa + a, n + 1
        return pf, pa, n

    def last_game(self, tid, upto):
        gs = [x for x in self.team_games.get(tid, ()) if x[0] <= upto]
        return gs[-1] if gs else None

    def streak_of(self, tid, upto):
        res = self.results(tid, upto)
        if not res:
            return "", 0
        n = 1
        while n < len(res) and res[-n - 1] == res[-1]:
            n += 1
        return res[-1], n

    def meetings(self, a, b, before_week):
        return [x for x in self.team_games.get(a, ()) if x[2] == b and x[0] < before_week]

    def games_left(self, tid, after_week):
        return sum(1 for g in self.schedule if g["week"] > after_week and tid in (g["home"], g["away"]))

    def division_table(self, upto):
        """{(conf, div): [(tid, rec), ...] best first} (by win percentage, then point differential)."""
        out = defaultdict(list)
        for t in self.ctx.teams.values():
            r = self.record(t.id, upto)
            pf, pa, _n = self.points(t.id, upto)
            out[(t.conference, t.division)].append((t.id, r, pf - pa))
        for k in out:
            out[k].sort(key=lambda x: (-pct(x[1]), -x[2]))
        return out

    # ---- injuries that cost a team a key player ----
    def key_injuries(self):
        """[(tid, pid, injury week, weeks out, kind)]: notable players lost for 4+ weeks
        during the regular season, after playing in at least two of the team's games."""
        if self._injuries is not None:
            return self._injuries
        out = []
        ctx = self.ctx
        for e in ctx.league.injury_history:
            if e["season"] != self.season or (e.get("weeks") or 0) < 4:
                continue
            cal = ctx.label_cal(e.get("game"))
            if not (6 <= cal < 6 + ctx.n_weeks):
                continue
            week = int(cal) - 5
            p = ctx.player(e["pid"])
            tid = e.get("team")
            if p is None or tid not in ctx.teams or not ctx.notable(p, tid):
                continue
            before = [x for x in self.games_of(p.id, week) if x[2] == tid]
            if len(before) < 2:
                continue
            if p.position == "QB" and sum(x[3].get("pass_att", 0) for x in before) / len(before) < 15:
                continue
            out.append((tid, p.id, week, e["weeks"], e.get("kind")))
        self._injuries = out
        return out

    def fallout(self, tid, upto):
        """The team's most telling stretch without a key player, as of week `upto`:
        (pid, injury week, kind, record before, record since, points before, points since) or None."""
        best = None
        for t, pid, week, weeks, kind in self.key_injuries():
            if t != tid or week >= upto:
                continue
            back = week + weeks          # he's out through this week
            # He has played for this team again: the stretch without him is over.
            if any(x[0] > week and x[2] == tid for x in self.games_of(pid, upto)):
                continue
            end = min(upto, back)
            since = self.record(tid, end, since=week)
            if sum(since) < 2:
                continue
            before = self.record(tid, week)
            p_before = self.points(tid, week)
            p_since = self.points(tid, end, since=week)
            cand = (pid, week, kind, before, since, p_before, p_since)
            score = self.ctx.caliber(self.ctx.player(pid)) + (15 if self.ctx.player(pid).position == "QB" else 0)
            if best is None or score > best[0]:
                best = (score, cand)
        return best[1] if best else None

    def comebacks(self, week):
        """Players back this week from a 4+ week injury: [(pid, tid, kind, weeks missed, line, game)]."""
        ctx = self.ctx
        out = []
        for e in ctx.league.injury_history:
            if e["season"] != self.season or (e.get("weeks") or 0) < 4:
                continue
            cal = ctx.label_cal(e.get("game"))
            if cal < 0:
                continue
            p = ctx.player(e["pid"])
            if p is None or not ctx.notable(p, e.get("team")):
                continue
            later = [x for x in self.player_games.get(p.id, ()) if 5 + x[0] > cal]
            if later and later[0][0] == week:
                w, g, tid, line = later[0]
                missed = sum(1 for x in self.team_games.get(tid, ()) if cal < 5 + x[0] < 5 + week)
                if missed >= 3:
                    out.append((p.id, tid, e.get("kind"), missed, line, g))
        # One per player (the latest injury he's back from).
        seen = {}
        for c in out:
            seen[c[0]] = c
        return list(seen.values())

    # ---- quarterbacks ----
    def qb_recent(self, pid, upto, n=3):
        gs = [x for x in self.games_of(pid, upto) if x[3].get("pass_att", 0) >= 10][-n:]
        if len(gs) < n or gs[-1][0] != upto:
            return None
        att = sum(x[3].get("pass_att", 0) - x[3].get("spikes", 0) for x in gs)
        cmp_ = sum(x[3].get("pass_cmp", 0) for x in gs)
        y = sum(x[3].get("pass_yds", 0) for x in gs)
        td = sum(x[3].get("pass_td", 0) for x in gs)
        it = sum(x[3].get("pass_int", 0) for x in gs)
        return {"att": att, "cmp": cmp_, "yds": y, "td": td, "int": it,
                "rating": passer_rating(att, cmp_, y, td, it), "games": gs}


def power_scores(track, upto):
    """{tid: score}: record, point differential per game and the last three games."""
    out = {}
    for tid in track.ctx.teams:
        r = track.record(tid, upto)
        pf, pa, n = track.points(tid, upto)
        last3 = track.results(tid, upto)[-3:]
        form = pct(rec_of(last3)) if last3 else 0.5
        out[tid] = RANK_PCT * pct(r) + RANK_DIFF * ((pf - pa) / n if n else 0) + RANK_FORM * form
    return out


def rank_order(track, upto):
    scores = power_scores(track, upto)
    return sorted(scores, key=lambda t: (-scores[t], t))


def injury_word(kind):
    return I.name(kind).partition(" (")[0] if kind else "an injury"
