# bitter_check.py
# Does Bitter (the league's social media site) ever say the same thing twice?
# Blake, Oct 24: "the tweets that are visible feel completely new and in reaction
# to whats happening... there should not be word for word repeats of tweets
# especially not in the same page/week/year honestly".
#
# Counts two kinds of repeats among every bit on Bitter (news outlets' article
# bits, team accounts, insiders, analysts, players, celebrities, fans, replies):
#   - exact: the same text, word for word;
#   - same shape: the same text once names and numbers are swapped out
#     ("If you started Smith this week..." and "If you started Jones this
#     week..."), the kind of repeat a reader notices as a template.
# Each is counted within a week, within a season and across seasons, and the
# worst offenders are printed with examples. Also times how long the feed takes
# to build (the Bitter tab rebuilds it after every week).
#
# The targets (Oct 24) are written into TARGETS below; the tool exits with an
# error if any is missed, so repeats can't creep back unnoticed.
#
# Run from the project folder:
#   python tools/bitter_check.py --cache league.pkl     (a pickled (league, past games))
#   python tools/bitter_check.py --seasons 3             (sims a league first: slow)
# The pickle is what tools/news_check.py --cache writes, or (league, past) from
# any script that keeps season.begin_offseason's finished games.

import argparse
import os
import pickle
import random
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import bitter, news, season as S              # noqa: E402

# What counts as passing (Oct 24):
#   - word-for-word repeats: none in a week or a season, among all bits;
#   - same shape: never twice in a week and at most SHAPE_SEASON_MAX times a
#     season among the accounts' own bits (everything but the outlets' article
#     bits, which share news stories and are counted separately), and never twice
#     in a week in the For you view (what you see league-wide, articles included).
# Across seasons, word-for-word repeats are reported (the target is "ideally none":
# each season is worded on its own so that looking at an earlier season's games
# never rewords this one, and a few short lines like a cryptic player's "Patience."
# can come back in a later season).
TARGETS = {"exact_week": 0, "exact_season": 0, "voice_shape_week": 0, "voice_shape_over": 0,
           "foryou_shape_week": 0}
SHAPE_SEASON_MAX = 3

NUMBER_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                "fifteen sixteen seventeen eighteen nineteen twenty first second third fourth fifth sixth "
                "seventh eighth ninth tenth").split()


class Shaper:
    """Turns a bit into its shape: names, teams, hashtags, handles and numbers swapped for placeholders."""

    def __init__(self, league):
        names = set()
        for p in league.players:
            for n in (p.name, p.first_name, p.last_name):
                if n and len(n) > 2:
                    names.add(n)
        teams = set()
        for t in league.teams:
            for n in (t.name, t.city, t.nickname, t.abbrev):
                if n:
                    teams.add(n)
        alt = lambda words: "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
        self.team_re = re.compile(r"\b(" + alt(teams) + r")\b", re.I)
        self.name_re = re.compile(r"\b(" + alt(names - teams) + r")\b")
        self.num_re = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.I)

    def shape(self, text):
        s = re.sub(r"[#@]\w+", "#", text).replace("Hall of Fame", "HOF")
        s = self.team_re.sub("T", s)
        s = self.name_re.sub("N", s)
        s = re.sub(r"\d[\d,.]*(st|nd|rd|th)?", "9", s)
        s = self.num_re.sub("9", s)
        s = re.sub(r"\b(N|T)( (N|T))+\b", r"\1", s)
        return re.sub(r"\s+", " ", s).strip().lower()


def all_bits(league, past):
    """Every bit on Bitter, top-level and replies (what the team and player views can show)."""
    data = bitter.timeline(league, past, min_importance=0)
    out = []
    for b in data["bits"]:
        out.append(b)
        out.extend(b["replies"])
    return out


def count(bits, key, shaper):
    """Repeats of `key` (exact text or shape) by week, season and across the save.
    Returns {scope: (repeat count, {value: [bits]})}."""
    groups = {"week": defaultdict(list), "season": defaultdict(list), "save": defaultdict(list)}
    for b in bits:
        v = b["text"] if key == "exact" else shaper.shape(b["text"])
        groups["week"][(b["season"], int(b["cal"]), v)].append(b)
        groups["season"][(b["season"], v)].append(b)
        groups["save"][v].append(b)
    out = {}
    for scope, g in groups.items():
        rep = {k: v for k, v in g.items() if len(v) > 1}
        out[scope] = (sum(len(v) - 1 for v in rep.values()), rep)
    return out


def show(b):
    return f"{b['season']} {b['when']}: {b['name']} ({b['role']}): {b['text']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", help="pickle of (league, past games); simmed and saved there if missing")
    ap.add_argument("--seasons", type=int, default=3, help="seasons to sim when there's no cache")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--n", type=int, default=12, help="offenders to print per list")
    args = ap.parse_args()
    if args.cache and os.path.exists(args.cache):
        with open(args.cache, "rb") as f:
            league, past = pickle.load(f)
    else:
        from engine.league import create_league
        league = create_league(seed=args.seed)
        S.start_season(league, rng=random.Random(args.seed))
        past = []
        for i in range(args.seasons):
            while not S.season_over(league):
                S.play_week(league)
            past += S.start_next_season(league, rng=random.Random(args.seed + i + 1))
        for _ in range(S.PRESEASON_WEEKS + 6):
            S.play_week(league)
        if args.cache:
            with open(args.cache, "wb") as f:
                pickle.dump((league, past), f)
    out = []
    # Speed: the current season alone (what the Bitter tab builds after a week), then every season.
    news._cache.clear()
    t0 = time.time()
    bitter.timeline(league, None)
    t_now = time.time() - t0
    news._cache.clear()
    t0 = time.time()
    bits = all_bits(league, past or None)
    t_all = time.time() - t0
    seasons = sorted({b["season"] for b in bits})
    out.append(f"League: {league.name}, now {league.season} {S.week_label(league)}; seasons with bits: {seasons}")
    out.append(f"Build time: this season's feed {t_now:.2f}s; every season with its games {t_all:.2f}s")
    per_season = Counter(b["season"] for b in bits)
    weeks = Counter((b["season"], int(b["cal"])) for b in bits if 6 <= b["cal"] < 6 + 18)
    fy = bitter.timeline(league, past or None)["bits"]           # For you: top-level bits
    fy_weeks = Counter((b["season"], int(b["cal"])) for b in fy if 6 <= b["cal"] < 6 + 18)
    out.append("Bits per season: " + ", ".join(f"{s}: {per_season[s]}" for s in seasons)
               + f"; regular-season week average: {sum(weeks.values()) / max(1, len(weeks)):.0f} in all, "
               f"{sum(fy_weeks.values()) / max(1, len(fy_weeks)):.0f} top-level in For you")
    shaper = Shaper(league)
    results = {}
    voices = [b for b in bits if b["cat"] != "headlines"]
    articles = [b for b in bits if b["cat"] == "headlines"]
    for label, key, group, name in (
            ("Word-for-word repeats, every bit", "exact", bits, "exact"),
            ("Same shape (names and numbers swapped), the accounts' own bits", "shape", voices, "voice_shape"),
            ("Same shape, the outlets' article bits (for information)", "shape", articles, "article_shape"),
            ("Same shape in the For you view", "shape", fy, "foryou_shape")):
        res = count(group, key, shaper)
        for scope in ("week", "season", "save"):
            results[f"{name}_{scope}"] = res[scope][0]
        over = sum(1 for g in res["season"][1].values() if len(g) > SHAPE_SEASON_MAX)
        results[f"{name}_over"] = over
        out.append(f"\n{label}: in a week {res['week'][0]}, in a season {res['season'][0]}, "
                   f"across the save {res['save'][0]} (extra copies among {len(group)} bits)"
                   + (f"; shapes used more than {SHAPE_SEASON_MAX} times in a season: {over}" if key == "shape" else ""))
        worst = sorted(res["season"][1].items(), key=lambda kv: -len(kv[1]))[:args.n]
        for (season, v), g in worst:
            out.append(f"  x{len(g)} in {season}: {g[0]['text'][:110]}")
            for b in g[:2]:
                out.append(f"       {show(b)[:150]}")
        if key == "exact":
            worst = sorted(res["save"][1].items(), key=lambda kv: -len(kv[1]))[:args.n]
            out.append("  Across seasons:")
            for v, g in worst:
                out.append(f"  x{len(g)}: {g[0]['text'][:100]} ({', '.join(str(b['season']) for b in g[:4])})")
    # Which accounts repeat themselves most (shape, within a season).
    by_role = Counter()
    for (season, v), group in count(voices, "shape", shaper)["season"][1].items():
        for b in group[1:]:
            by_role[bitter.category(b["role"])] += 1
    out.append("\nSame-shape repeats in a season by kind of account: "
               + ", ".join(f"{bitter.CATS[c]} {n}" for c, n in by_role.most_common()))
    # Pass or fail.
    fails = [f"{k} = {results[k]} (target {v})" for k, v in TARGETS.items() if results[k] > v]
    out.append("\nTARGETS: " + ("all met" if not fails else "MISSED: " + "; ".join(fails)))
    text = "\n".join(out)
    print(text)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitter_check_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n(Written to {path})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
