# news_check.py
# Build a league, sim some weeks, and print sample news and social posts so
# the wording can be judged (engine/news.py). Also runs a few automatic
# checks: no unfilled template gaps, no "None", no hidden ratings mentioned,
# no headline repeated word for word in the same week.
#
# Run from the project folder:
#   python tools/news_check.py                 (preseason + 6 regular-season weeks)
#   python tools/news_check.py --weeks 18      (the whole regular season)
#   python tools/news_check.py --full          (a whole season with playoffs, the
#                                               offseason, then 3 weeks of the next)
#   python tools/news_check.py --cache league.pkl   (reuse the simmed league next time)
# The full output is also written to tools/news_check_report.txt.

import argparse
import os
import pickle
import random
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import news, season as S                     # noqa: E402
from engine.league import create_league                  # noqa: E402

HIDDEN_WORDS = ["consisten", "durab", "generational", "volatil", "adaptab", "potential", "hidden"]


def sim(args):
    """(league, past games): past games are the finished season's games, the
    way the save's history file keeps them (the News tab reads them from there)."""
    if args.cache and os.path.exists(args.cache):
        with open(args.cache, "rb") as f:
            print(f"Loaded the simmed league from {args.cache}")
            data = pickle.load(f)
            return data if isinstance(data, tuple) else (data, [])
    t0 = time.time()
    league = create_league(seed=args.seed)
    league.name = "News check"
    S.start_season(league, rng=random.Random(args.seed))
    past = []
    if args.full:
        while not S.season_over(league):
            S.play_week(league)
            print(f"  played {S.week_label(league)}", end="\r")
        past = S.start_next_season(league, rng=random.Random(args.seed + 1))
        target = S.PRESEASON_WEEKS + 3
    else:
        target = S.PRESEASON_WEEKS + args.weeks
    while not S.season_over(league) and S.calendar(league) <= target:
        S.play_week(league)
        print(f"  played through {S.week_label(league)}      ", end="\r")
    print(f"\nSimmed in {time.time() - t0:.0f}s. Now: {league.season} {S.week_label(league)}")
    if args.cache:
        with open(args.cache, "wb") as f:
            pickle.dump((league, past), f)
    return league, past


def show_story(x, out):
    out.append(f"[{x['season']} {x['when']}] ({news.TYPES[x['kind']]}, importance {x['importance']})")
    out.append(f"  {x['headline']}")
    for line in x["body"].split("\n"):
        out.append(f"    {line}")


def show_post(x, out):
    out.append(f"[{x['season']} {x['when']}] {x['name']} {x['handle']} ({x['role']}): {x['text']}")


def checks(items, posts, out, errors=()):
    problems = [f"wording error: {e}" for e in sorted(set(errors))]
    for x in items:
        text = x["headline"] + " " + x["body"]
        if re.search(r"[{}]", text) or "None" in text:
            problems.append(f"unfilled text: {x['headline']}")
        low = text.lower()
        for w in HIDDEN_WORDS:
            if w in low:
                problems.append(f"mentions '{w}': {x['headline']}")
    for x in posts:
        if re.search(r"[{}]", x["text"]) or "None" in x["text"]:
            problems.append(f"unfilled post: {x['text']}")
        for w in HIDDEN_WORDS:
            if w in x["text"].lower():
                problems.append(f"post mentions '{w}': {x['text']}")
    same = Counter((x["season"], x["cal"], x["headline"]) for x in items)
    for (s, c, h), n in same.items():
        if n > 1:
            problems.append(f"headline used {n} times in one week: {h}")
    # How varied are the game headlines? Strip names and numbers to see their shape.
    games = [x for x in items if x["kind"] == "game"]
    shapes = Counter(re.sub(r"\d+", "#", re.sub(r"[A-Z][a-z.']+", "X", x["headline"])) for x in games)
    out.append(f"Game headlines: {len(games)}, {len(shapes)} different shapes; most used: "
               + "; ".join(f"{s!r} x{n}" for s, n in shapes.most_common(4)))
    out.append("Automatic checks: " + ("all passed" if not problems else f"{len(problems)} problems"))
    for p in problems[:40]:
        out.append("  PROBLEM: " + p)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--weeks", type=int, default=6, help="regular-season weeks to play after the preseason")
    ap.add_argument("--full", action="store_true", help="a whole season, the offseason, then 3 weeks")
    ap.add_argument("--cache", help="pickle file: load the simmed league from it, or save it there")
    ap.add_argument("--team", type=int, default=None, help="team id for the team view (default: team 1)")
    ap.add_argument("--n", type=int, default=25, help="stories to print per section")
    args = ap.parse_args()

    league, past = sim(args)
    past = past or None
    t0 = time.time()
    data = news.build(league, past)
    items, posts = data["items"], data["posts"]
    out = [f"Built {len(items)} stories and {len(posts)} posts in {time.time() - t0:.1f}s."]
    by_kind = Counter(x["kind"] for x in items)
    out.append("Stories by type: " + ", ".join(f"{news.TYPES[k]} {n}" for k, n in by_kind.most_common()))
    league_view = news.stories(league, past_games=past)
    out.append(f"League view (importance {news.LEAGUE_VIEW_MIN}+): {len(league_view)} stories")
    checks(items, posts, out, data.get("errors", ()))

    out.append("\n==== LEAGUE VIEW (newest first) ====")
    for x in league_view[:args.n]:
        show_story(x, out)
    tid = args.team or league.teams[0].id
    out.append(f"\n==== TEAM VIEW: {league.team(tid).name} ====")
    for x in news.stories(league, team_id=tid, past_games=past)[:args.n]:
        show_story(x, out)
    # One of each kind, so every template family gets a look.
    out.append("\n==== ONE OF EACH TYPE ====")
    for kind in news.TYPES:
        pick = [x for x in items if x["kind"] == kind]
        if pick:
            rng = random.Random(kind)
            for x in rng.sample(pick, min(3, len(pick))):
                show_story(x, out)
    # The player with the most stories that aren't transaction lists.
    players = Counter(pid for x in items if x["kind"] != "moves" for pid in x["players"])
    if players:
        pid = players.most_common(1)[0][0]
        out.append(f"\n==== PLAYER VIEW: {league.player(pid).name} ({players[pid]} stories) ====")
        for x in news.stories(league, player_id=pid, past_games=past)[:10]:
            show_story(x, out)
    out.append("\n==== SOCIAL (league view) ====")
    for x in news.posts(league, past_games=past)[:args.n]:
        show_post(x, out)
    out.append(f"\n==== SOCIAL ({league.team(tid).name}) ====")
    for x in news.posts(league, team_id=tid, past_games=past)[:args.n]:
        show_post(x, out)

    text = "\n".join(out)
    print(text)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_check_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n(Written to {path})")


if __name__ == "__main__":
    main()
