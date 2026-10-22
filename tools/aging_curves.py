# tools/aging_curves.py
# How real NFL players rise, peak and decline, by position and pro season
# (season 1 = rookie year). Used to set development.PEAK_SEASONS.
#
# Data (tools/data, from nflverse): season rosters 1999-2025 (birth date,
# rookie year, ids), snap counts 2013-2025, season stats 1999-2025.
#
# Method ("delta method", the standard way to measure aging in sports
# analytics): for every player who played in two straight seasons, take the
# change in a measure from season n to n+1, and average those changes by n.
# Adding the changes up gives the typical career curve. Comparing the same
# player with himself avoids the trap of simple averages, where the players
# still around at season 12 are the great ones, so old players look better
# than they are. Players who leave the league aren't counted after they
# leave (the game handles retirements separately).
#
# Measures:
#   share   share of his team's offensive or defensive snaps in the games he
#           played (6+ games; every position but K, P, LS): how much teams
#           trust him, the broadest measure. Per game played, because per
#           team game an every-down starter can only lose share (missed games,
#           the 100% ceiling), which made declines look ~2 seasons early.
#   eff     an efficiency stat where one exists (QB: EPA per dropback;
#           RB: rushing EPA per carry; WR/TE: receiving EPA per target;
#           edge rushers: sacks + QB hits per defensive snap; K: field goal
#           accuracy compared with the league at each kick's distance band;
#           P: gross yards per punt). Only seasons with enough plays count.
#
# Run from the project folder:  python tools/aging_curves.py

import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

DATA = Path(__file__).resolve().parent / "data"
SHOW_PAIRS = "--pairs" in sys.argv     # also print how many players each step rests on (± = 95% range)
PER_GAME = True                        # snap share per game played (see snap_seasons)
YEARS = range(2013, 2026)

GROUP = {"QB": "QB", "RB": "RB", "HB": "RB", "FB": "FB", "WR": "WR", "TE": "TE",
         "T": "T", "OT": "T", "LT": "T", "RT": "T", "G": "G", "OG": "G", "LG": "G", "RG": "G", "C": "C",
         "DE": "DE", "DT": "DT", "NT": "DT", "OLB": "OLB", "ILB": "ILB", "MLB": "ILB", "LB": "LB",
         "CB": "CB", "S": "S", "FS": "S", "SS": "S", "SAF": "S", "K": "K", "P": "P", "LS": "LS"}
OFFENSE = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C"}


def rows(name):
    path = DATA / name
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def load_people():
    """pfr id / gsis id / (name, season) -> {rookie_year, finer position}."""
    by_pfr, by_gsis, by_name = {}, {}, {}
    for year in range(1999, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            rookie = r.get("rookie_year") or r.get("entry_year")
            if not rookie:
                continue
            info = {"rookie": int(float(rookie)), "depth_pos": r.get("depth_chart_position") or ""}
            if r.get("pfr_id"):
                by_pfr.setdefault(r["pfr_id"], info)
            if r.get("gsis_id"):
                by_gsis.setdefault(r["gsis_id"], info)
            by_name[(r["full_name"], year)] = info
    return by_pfr, by_gsis, by_name


def snap_seasons(by_pfr, by_name):
    """{(pfr id, season): (group, season number, share)}"""
    out = {}
    for year in YEARS:
        team_games = defaultdict(set)
        player = defaultdict(lambda: {"pct": 0.0, "pos": None, "name": None})
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            team_games[r["team"]].add(r["game_id"])
            grp = GROUP.get(r["position"])
            if grp is None:
                continue
            pct = num(r["offense_pct"]) if grp in OFFENSE else num(r["defense_pct"])
            d = player[r["pfr_player_id"]]
            d["pct"] += pct
            d["games"] = d.get("games", 0) + (pct > 0)
            d["pos"], d["name"] = grp, r["player"]
        games = max(len(g) for g in team_games.values())
        for pid, d in player.items():
            info = by_pfr.get(pid) or by_name.get((d["name"], year))
            if not info or d["pos"] in ("K", "P", "LS"):
                continue
            if PER_GAME:
                # Share of snaps in the games he played (6+), so missed games and
                # the 100% ceiling of an every-down starter don't read as decline.
                if d.get("games", 0) < 6:
                    continue
                share = d["pct"] / d["games"]
            else:
                share = d["pct"] / games
            grp = d["pos"]
            if grp == "LB":                       # split linebackers where the roster says which
                grp = {"OLB": "OLB", "ILB": "ILB", "MLB": "ILB"}.get(info["depth_pos"], "LB")
            n = year - info["rookie"] + 1
            if 1 <= n <= 20:
                out[(pid, year)] = (grp, n, share)
    return out


def stat_seasons(by_gsis):
    """{(gsis id, season): (group, season number, efficiency)} where there's enough volume."""
    out = {}
    fg_rate = {}                                  # league FG% by distance band, per season
    seasons = {}
    for year in range(1999, 2026):
        rs = rows(f"stats_player_reg_{year}.csv.gz")
        seasons[year] = rs
        made = defaultdict(float)
        att = defaultdict(float)
        for r in rs:
            for band in ("0_19", "20_29", "30_39", "40_49", "50_59", "60_"):
                m, x = num(r.get(f"fg_made_{band}")), num(r.get(f"fg_missed_{band}"))
                made[band] += m
                att[band] += m + x
        fg_rate[year] = {b: made[b] / att[b] for b in att if att[b]}
    for year, rs in seasons.items():
        for r in rs:
            info = by_gsis.get(r["player_id"])
            if not info:
                continue
            grp = GROUP.get(r["position"])
            n = year - info["rookie"] + 1
            if grp is None or not 1 <= n <= 22:
                continue
            eff = None
            if grp == "QB":
                plays = num(r["attempts"]) + num(r["sacks_suffered"]) + num(r["carries"])
                if plays >= 150:
                    eff = (num(r["passing_epa"]) + num(r["rushing_epa"])) / plays
            elif grp == "RB":
                if num(r["carries"]) >= 60:
                    eff = num(r["rushing_epa"]) / num(r["carries"])
            elif grp in ("WR", "TE"):
                if num(r["targets"]) >= 30:
                    eff = num(r["receiving_epa"]) / num(r["targets"])
            elif grp == "K":
                over = tries = 0.0
                for band, rate in fg_rate[year].items():
                    m, x = num(r.get(f"fg_made_{band}")), num(r.get(f"fg_missed_{band}"))
                    over += m - rate * (m + x)
                    tries += m + x
                if tries >= 15:
                    eff = over / tries
            elif grp == "P":
                if num(r["pt_att"]) >= 30:
                    eff = num(r["pt_yards"]) / num(r["pt_att"])
            if eff is not None:
                out[(r["player_id"], year)] = (grp, n, eff)
    return out


def curve(seasons, min_pairs=25, exits_as_zero=False):
    """Average change from season n to n+1, by group: {group: {n: (mean change, pairs, standard error)}}.
    exits_as_zero: a player missing the next season counts as dropping to 0
    (the other side of the survivor question; the truth sits between)."""
    deltas = defaultdict(lambda: defaultdict(list))
    last = max(year for _pid, year in seasons)
    for (pid, year), (grp, n, v) in seasons.items():
        nxt = seasons.get((pid, year + 1))
        if nxt and nxt[0] == grp:
            deltas[grp][n].append(nxt[2] - v)
        elif exits_as_zero and not nxt and year < last:
            deltas[grp][n].append(-v)
    return {g: {n: (mean(v), len(v), pstdev(v) / len(v) ** 0.5) for n, v in sorted(d.items()) if len(v) >= min_pairs}
            for g, d in deltas.items()}


def show(title, c, scale, unit):
    print(f"\n{title}")
    print("  cumulative change from season 1 (each column = start of that pro season); * = biggest")
    for grp in ["QB", "RB", "FB", "WR", "TE", "T", "G", "C", "DE", "DT", "OLB", "ILB", "LB", "CB", "S", "K", "P"]:
        if grp not in c:
            continue
        total, line, best, best_n = 0.0, {1: 0.0}, 0.0, 1
        for n, (d, k, se) in c[grp].items():
            total += d
            line[n + 1] = total
            if total > best:
                best, best_n = total, n + 1
        cells = " ".join(f"{n}:{v * scale:+.0f}{'*' if n == best_n else ''}" for n, v in line.items())
        print(f"  {grp:4} {cells}  ({unit})")
        if SHOW_PAIRS:
            print("       pairs: " + " ".join(f"{n}>{n + 1}:{k}(±{2 * se * scale:.1f})" for n, (_d, k, se) in c[grp].items()))


def main():
    by_pfr, by_gsis, by_name = load_people()
    snaps = snap_seasons(by_pfr, by_name)
    print(f"snap seasons linked: {len(snaps)}")
    show("SHARE OF TEAM SNAPS (percentage points)", curve(snaps), 100, "pct pts")
    if not PER_GAME:     # (per game, any season under 6 games reads as an exit, so this only works per team game)
        show("SHARE OF TEAM SNAPS, players who leave the league count as 0", curve(snaps, exits_as_zero=True), 100,
             "pct pts")
    eff = stat_seasons(by_gsis)
    print(f"\nstat seasons with enough volume: {len(eff)}")
    show("EFFICIENCY (QB/RB/WR/TE: EPA per play x100; K: FG% vs league x100; P: gross yards x1)",
         {g: v for g, v in curve(eff, 15).items() if g in ("QB", "RB", "WR", "TE")}, 100, "EPA x100")
    c = curve(eff, 10)
    show("KICKERS (FG% above league, pct pts)", {g: v for g, v in c.items() if g == "K"}, 100, "pct pts")
    show("PUNTERS (gross yards per punt)", {g: v for g, v in c.items() if g == "P"}, 1, "yards")


if __name__ == "__main__":
    main()
