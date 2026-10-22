# big_games_real.py
# What counts as a "big game" at each position, from real NFL games (nflverse
# weekly player stats, regular seasons 2015-2025, in tools/data). For each
# rule it prints how many players a week league-wide have a game like that, and
# what share of the position's regular players do. engine/news.py's big-game
# rules (BIG_GAMES) were set from this (Blake, Oct 23: "a dominant performance
# for all positions, not just QB").
#
#   python tools/big_games_real.py

import csv
import gzip
import os
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nflverse", "stats_player")
SEASONS = range(2015, 2026)


def f(row, k):
    try:
        return float(row.get(k) or 0)
    except ValueError:
        return 0.0


def stats(row):
    s = {k: f(row, k) for k in ("attempts", "passing_yards", "passing_tds", "passing_interceptions", "carries",
                                 "rushing_yards", "rushing_tds", "receptions", "receiving_yards", "receiving_tds",
                                 "targets", "def_sacks", "def_interceptions", "def_tds", "def_fumbles_forced",
                                 "def_tackles_solo", "def_tackle_assists", "def_tackles_for_loss", "def_pass_defended",
                                 "fg_made", "fg_long", "gwfg_made", "gwfg_distance", "special_teams_tds")}
    s["tackles"] = s["def_tackles_solo"] + s["def_tackle_assists"]
    s["scrim"] = s["rushing_yards"] + s["receiving_yards"]
    s["tds"] = s["rushing_tds"] + s["receiving_tds"]
    return s


# Who counts as a regular at the position in that game (the denominator).
REGULAR = {
    "QB": lambda s: s["attempts"] >= 15,
    "RB": lambda s: s["carries"] >= 10,
    "WR": lambda s: s["targets"] >= 5,
    "TE": lambda s: s["targets"] >= 3,
    "DL": lambda s: s["tackles"] >= 2 or s["def_sacks"] > 0,
    "LB": lambda s: s["tackles"] >= 4,
    "DB": lambda s: s["tackles"] >= 3 or s["def_pass_defended"] > 0,
    "K": lambda s: s["fg_made"] + 0 >= 0,
}

RULES = {
    "QB": [
        ("Blake: 300+ yards or 3+ TD passes, 0-1 INT",
         lambda s: (s["passing_yards"] >= 300 or s["passing_tds"] >= 3) and s["passing_interceptions"] <= 1),
        ("350+ yards or 3+ TD passes, 0-1 INT",
         lambda s: (s["passing_yards"] >= 350 or s["passing_tds"] >= 3) and s["passing_interceptions"] <= 1),
        ("300+ yards and 3+ TD passes, 0-1 INT",
         lambda s: s["passing_yards"] >= 300 and s["passing_tds"] >= 3 and s["passing_interceptions"] <= 1),
        ("400+ yards (any INT) or 4+ TD passes",
         lambda s: s["passing_yards"] >= 400 or s["passing_tds"] >= 4),
        ("QB rushing: 100+ rushing yards", lambda s: s["rushing_yards"] >= 100),
    ],
    "RB": [
        ("100+ rushing yards and a TD", lambda s: s["rushing_yards"] >= 100 and s["tds"] >= 1),
        ("150+ yards from scrimmage", lambda s: s["scrim"] >= 150),
        ("3+ touchdowns", lambda s: s["tds"] >= 3),
        ("any of the three", lambda s: (s["rushing_yards"] >= 100 and s["tds"] >= 1) or s["scrim"] >= 150
         or s["tds"] >= 3),
    ],
    "WR": [
        ("100+ receiving yards and a TD", lambda s: s["receiving_yards"] >= 100 and s["receiving_tds"] >= 1),
        ("150+ receiving yards", lambda s: s["receiving_yards"] >= 150),
        ("3+ TD catches", lambda s: s["receiving_tds"] >= 3),
        ("10+ catches and 120+ yards", lambda s: s["receptions"] >= 10 and s["receiving_yards"] >= 120),
        ("any of the four", lambda s: (s["receiving_yards"] >= 100 and s["receiving_tds"] >= 1)
         or s["receiving_yards"] >= 150 or s["receiving_tds"] >= 3
         or (s["receptions"] >= 10 and s["receiving_yards"] >= 120)),
    ],
    "TE": [
        ("100+ receiving yards", lambda s: s["receiving_yards"] >= 100),
        ("2+ TD catches", lambda s: s["receiving_tds"] >= 2),
        ("either", lambda s: s["receiving_yards"] >= 100 or s["receiving_tds"] >= 2),
    ],
    "DL": [
        ("2+ sacks", lambda s: s["def_sacks"] >= 2),
        ("3+ sacks", lambda s: s["def_sacks"] >= 3),
        ("a sack and a forced fumble", lambda s: s["def_sacks"] >= 1 and s["def_fumbles_forced"] >= 1),
        ("3+ tackles for loss", lambda s: s["def_tackles_for_loss"] >= 3),
    ],
    "LB": [
        ("2+ sacks", lambda s: s["def_sacks"] >= 2),
        ("15+ tackles", lambda s: s["tackles"] >= 15),
        ("an interception or a defensive TD", lambda s: s["def_interceptions"] >= 1 or s["def_tds"] >= 1),
        ("12+ tackles and a sack or TFL", lambda s: s["tackles"] >= 12 and (s["def_sacks"] >= 1
                                                                           or s["def_tackles_for_loss"] >= 1)),
    ],
    "DB": [
        ("2+ interceptions", lambda s: s["def_interceptions"] >= 2),
        ("a defensive TD", lambda s: s["def_tds"] >= 1),
        ("an interception and 3+ passes defensed", lambda s: s["def_interceptions"] >= 1
         and s["def_pass_defended"] >= 3),
        ("a sack and an interception", lambda s: s["def_sacks"] >= 1 and s["def_interceptions"] >= 1),
    ],
    "K": [
        ("5+ field goals", lambda s: s["fg_made"] >= 5),
        ("4+ field goals", lambda s: s["fg_made"] >= 4),
        ("a 55+ yard field goal", lambda s: s["fg_long"] >= 55),
        ("a game-winning field goal", lambda s: s["gwfg_made"] >= 1),
    ],
}

GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL",
         "OLB": "LB", "ILB": "LB", "MLB": "LB", "LB": "LB", "CB": "DB", "S": "DB", "FS": "DB", "SS": "DB", "DB": "DB",
         "K": "K", "PK": "K"}


def main():
    regulars = defaultdict(int)
    hits = defaultdict(int)
    team_games = 0
    for season in SEASONS:
        path = os.path.join(DATA, f"stats_player_week_{season}.csv.gz")
        if not os.path.exists(path):
            continue
        games = set()
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("season_type") != "REG":
                    continue
                games.add((row["week"], row["team"]))
                g = GROUP.get(row.get("position") or "")
                if not g:
                    continue
                s = stats(row)
                if not REGULAR[g](s):
                    continue
                regulars[g] += 1
                for i, (_name, rule) in enumerate(RULES[g]):
                    if rule(s):
                        hits[(g, i)] += 1
        team_games += len(games)
    weeks = team_games / 32          # league weeks (32 teams' games)
    print(f"Real NFL regular seasons {SEASONS.start}-{SEASONS.stop - 1}: {team_games} team games "
          f"({weeks:.0f} league weeks).\n")
    for g, rules in RULES.items():
        print(f"{g}: {regulars[g] / weeks:.0f} regulars a week")
        for i, (name, _rule) in enumerate(rules):
            n = hits[(g, i)]
            print(f"   {name:<52} {n / weeks:5.1f} a week   ({100 * n / max(1, regulars[g]):4.1f}% of regulars)")
        print()


if __name__ == "__main__":
    main()
