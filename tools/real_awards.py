# tools/real_awards.py
# The real NFL's season awards, 2000-2025 (AP awards; the 2025 winners were
# announced Feb 5, 2026), so the game's award winners can be compared with
# real ones (tools/awards_check.py). Each winner's season stats and his team's
# record come from the nflverse data already in tools/data.
#
# Groups (how the game's positions line up): QB, RB, WR, TE; EDGE (4-3 ends
# and 3-4 pass-rushing outside linebackers), DT (interior line), LB (off-ball
# linebackers), CB, S.
#
# Run on its own to print the real profiles:
#   python tools/real_awards.py

import csv
import gzip
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# (season, name, group). Co-winners are both listed.
WINNERS = {
    "mvp": [
        (2000, "Marshall Faulk", "RB"), (2001, "Kurt Warner", "QB"), (2002, "Rich Gannon", "QB"),
        (2003, "Peyton Manning", "QB"), (2003, "Steve McNair", "QB"), (2004, "Peyton Manning", "QB"),
        (2005, "Shaun Alexander", "RB"), (2006, "LaDainian Tomlinson", "RB"), (2007, "Tom Brady", "QB"),
        (2008, "Peyton Manning", "QB"), (2009, "Peyton Manning", "QB"), (2010, "Tom Brady", "QB"),
        (2011, "Aaron Rodgers", "QB"), (2012, "Adrian Peterson", "RB"), (2013, "Peyton Manning", "QB"),
        (2014, "Aaron Rodgers", "QB"), (2015, "Cam Newton", "QB"), (2016, "Matt Ryan", "QB"),
        (2017, "Tom Brady", "QB"), (2018, "Patrick Mahomes", "QB"), (2019, "Lamar Jackson", "QB"),
        (2020, "Aaron Rodgers", "QB"), (2021, "Aaron Rodgers", "QB"), (2022, "Patrick Mahomes", "QB"),
        (2023, "Lamar Jackson", "QB"), (2024, "Josh Allen", "QB"), (2025, "Matthew Stafford", "QB"),
    ],
    "opoy": [
        (2000, "Marshall Faulk", "RB"), (2001, "Marshall Faulk", "RB"), (2002, "Priest Holmes", "RB"),
        (2003, "Jamal Lewis", "RB"), (2004, "Peyton Manning", "QB"), (2005, "Shaun Alexander", "RB"),
        (2006, "LaDainian Tomlinson", "RB"), (2007, "Tom Brady", "QB"), (2008, "Drew Brees", "QB"),
        (2009, "Chris Johnson", "RB"), (2010, "Tom Brady", "QB"), (2011, "Drew Brees", "QB"),
        (2012, "Adrian Peterson", "RB"), (2013, "Peyton Manning", "QB"), (2014, "DeMarco Murray", "RB"),
        (2015, "Cam Newton", "QB"), (2016, "Matt Ryan", "QB"), (2017, "Todd Gurley", "RB"),
        (2018, "Patrick Mahomes", "QB"), (2019, "Michael Thomas", "WR"), (2020, "Derrick Henry", "RB"),
        (2021, "Cooper Kupp", "WR"), (2022, "Justin Jefferson", "WR"), (2023, "Christian McCaffrey", "RB"),
        (2024, "Saquon Barkley", "RB"), (2025, "Jaxon Smith-Njigba", "WR"),
    ],
    "dpoy": [
        (2000, "Ray Lewis", "LB"), (2001, "Michael Strahan", "EDGE"), (2002, "Derrick Brooks", "LB"),
        (2003, "Ray Lewis", "LB"), (2004, "Ed Reed", "S"), (2005, "Brian Urlacher", "LB"),
        (2006, "Jason Taylor", "EDGE"), (2007, "Bob Sanders", "S"), (2008, "James Harrison", "EDGE"),
        (2009, "Charles Woodson", "CB"), (2010, "Troy Polamalu", "S"), (2011, "Terrell Suggs", "EDGE"),
        (2012, "J.J. Watt", "EDGE"), (2013, "Luke Kuechly", "LB"), (2014, "J.J. Watt", "EDGE"),
        (2015, "J.J. Watt", "EDGE"), (2016, "Khalil Mack", "EDGE"), (2017, "Aaron Donald", "DT"),
        (2018, "Aaron Donald", "DT"), (2019, "Stephon Gilmore", "CB"), (2020, "Aaron Donald", "DT"),
        (2021, "T.J. Watt", "EDGE"), (2022, "Nick Bosa", "EDGE"), (2023, "Myles Garrett", "EDGE"),
        (2024, "Patrick Surtain", "CB"), (2025, "Myles Garrett", "EDGE"),
    ],
    "oroy": [
        (2000, "Mike Anderson", "RB"), (2001, "Anthony Thomas", "RB"), (2002, "Clinton Portis", "RB"),
        (2003, "Anquan Boldin", "WR"), (2004, "Ben Roethlisberger", "QB"), (2005, "Cadillac Williams", "RB"),
        (2006, "Vince Young", "QB"), (2007, "Adrian Peterson", "RB"), (2008, "Matt Ryan", "QB"),
        (2009, "Percy Harvin", "WR"), (2010, "Sam Bradford", "QB"), (2011, "Cam Newton", "QB"),
        (2012, "Robert Griffin", "QB"), (2013, "Eddie Lacy", "RB"), (2014, "Odell Beckham", "WR"),
        (2015, "Todd Gurley", "RB"), (2016, "Dak Prescott", "QB"), (2017, "Alvin Kamara", "RB"),
        (2018, "Saquon Barkley", "RB"), (2019, "Kyler Murray", "QB"), (2020, "Justin Herbert", "QB"),
        (2021, "Ja'Marr Chase", "WR"), (2022, "Garrett Wilson", "WR"), (2023, "C.J. Stroud", "QB"),
        (2024, "Jayden Daniels", "QB"), (2025, "Tetairoa McMillan", "WR"),
    ],
    "droy": [
        (2000, "Brian Urlacher", "LB"), (2001, "Kendrell Bell", "LB"), (2002, "Julius Peppers", "EDGE"),
        (2003, "Terrell Suggs", "EDGE"), (2004, "Jonathan Vilma", "LB"), (2005, "Shawne Merriman", "EDGE"),
        (2006, "DeMeco Ryans", "LB"), (2007, "Patrick Willis", "LB"), (2008, "Jerod Mayo", "LB"),
        (2009, "Brian Cushing", "LB"), (2010, "Ndamukong Suh", "DT"), (2011, "Von Miller", "EDGE"),
        (2012, "Luke Kuechly", "LB"), (2013, "Sheldon Richardson", "DT"), (2014, "Aaron Donald", "DT"),
        (2015, "Marcus Peters", "CB"), (2016, "Joey Bosa", "EDGE"), (2017, "Marshon Lattimore", "CB"),
        (2018, "Darius Leonard", "LB"), (2019, "Nick Bosa", "EDGE"), (2020, "Chase Young", "EDGE"),
        (2021, "Micah Parsons", "LB"), (2022, "Sauce Gardner", "CB"), (2023, "Will Anderson", "EDGE"),
        (2024, "Jared Verse", "EDGE"), (2025, "Carson Schwesinger", "LB"),
    ],
    # Comeback: "injury" = missed most of the season before (or played hurt
    # through it); "revival" = healthy but benched, cut, a backup or out of the league.
    "cpoy": [
        (2000, "Joe Johnson", "EDGE", "injury"), (2001, "Garrison Hearst", "RB", "injury"),
        (2002, "Tommy Maddox", "QB", "revival"), (2003, "Jon Kitna", "QB", "revival"),
        (2004, "Drew Brees", "QB", "revival"), (2005, "Tedy Bruschi", "LB", "injury"),
        (2005, "Steve Smith", "WR", "injury"), (2006, "Chad Pennington", "QB", "injury"),
        (2007, "Greg Ellis", "EDGE", "injury"), (2008, "Chad Pennington", "QB", "revival"),
        (2009, "Tom Brady", "QB", "injury"), (2010, "Michael Vick", "QB", "revival"),
        (2011, "Matthew Stafford", "QB", "injury"), (2012, "Peyton Manning", "QB", "injury"),
        (2013, "Philip Rivers", "QB", "revival"), (2014, "Rob Gronkowski", "TE", "injury"),
        (2015, "Eric Berry", "S", "injury"), (2016, "Jordy Nelson", "WR", "injury"),
        (2017, "Keenan Allen", "WR", "injury"), (2018, "Andrew Luck", "QB", "injury"),
        (2019, "Ryan Tannehill", "QB", "revival"), (2020, "Alex Smith", "QB", "injury"),
        (2021, "Joe Burrow", "QB", "injury"), (2022, "Geno Smith", "QB", "revival"),
        (2023, "Joe Flacco", "QB", "revival"), (2024, "Joe Burrow", "QB", "injury"),
        (2025, "Christian McCaffrey", "RB", "injury"),
    ],
}

AWARD_NAMES = {"mvp": "MVP", "opoy": "Offensive Player of the Year", "dpoy": "Defensive Player of the Year",
               "oroy": "Offensive Rookie of the Year", "droy": "Defensive Rookie of the Year",
               "cpoy": "Comeback Player of the Year"}


# Names as the nflverse files spell them.
ALIASES = {"Michael Vick": "Mike Vick", "Darius Leonard": "Shaquille Leonard", "Patrick Surtain": "Pat Surtain"}


def _norm(name):
    name = ALIASES.get(name, name)
    name = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", name.lower())
    return re.sub(r"[^a-z]", "", name)


def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def _num(r, k):
    try:
        return float(r.get(k) or 0)
    except ValueError:
        return 0.0


def team_records():
    """{(season, team): {"w","l","t","g","playoffs"}} from the real schedules."""
    out = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "g": 0, "playoffs": False})
    for r in _rows(DATA / "nflverse" / "schedules" / "games.csv.gz"):
        if not r["home_score"]:
            continue
        s = int(r["season"])
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        for team, pf, pa in ((r["home_team"], hs, as_), (r["away_team"], as_, hs)):
            rec = out[(s, team)]
            if r["game_type"] != "REG":
                rec["playoffs"] = True
                continue
            rec["g"] += 1
            rec["w" if pf > pa else "l" if pf < pa else "t"] += 1
    return out


def winner_lines():
    """[{award, season, name, group, kind, team, games, stats..., team record}]."""
    want = defaultdict(list)
    for award, rows in WINNERS.items():
        for row in rows:
            season, name, group = row[:3]
            want[season].append((award, name, group, row[3] if len(row) > 3 else None))
    recs = team_records()
    out = []
    for season in sorted(want):
        found = {}
        prev = {}
        for path, store in ((DATA / f"stats_player_reg_{season}.csv.gz", found),
                            (DATA / f"stats_player_reg_{season - 1}.csv.gz", prev)):
            if not path.exists():
                continue
            names = {_norm(n) for _a, n, _g, _k in want[season]}
            for r in _rows(path):
                key = _norm(r["player_display_name"])
                if key in names and (key not in store or _num(r, "games") > _num(store[key], "games")):
                    store[key] = r
        for award, name, group, kind in want[season]:
            r = found.get(_norm(name))
            line = {"award": award, "season": season, "name": name, "group": group, "kind": kind}
            if r is None:
                line["missing"] = True
                out.append(line)
                continue
            team = r["recent_team"]
            rec = recs.get((season, team), {})
            g = rec.get("g") or 16
            line.update(team=team, games=_num(r, "games"), team_games=g,
                        win_pct=(rec.get("w", 0) + 0.5 * rec.get("t", 0)) / g if rec else None,
                        playoffs=rec.get("playoffs"),
                        pass_yds=_num(r, "passing_yards"), pass_td=_num(r, "passing_tds"),
                        pass_int=_num(r, "passing_interceptions"), rush_yds=_num(r, "rushing_yards"),
                        rush_td=_num(r, "rushing_tds"), rec=_num(r, "receptions"),
                        rec_yds=_num(r, "receiving_yards"), rec_td=_num(r, "receiving_tds"),
                        sacks=_num(r, "def_sacks"), def_int=_num(r, "def_interceptions"),
                        tackles=_num(r, "def_tackles_solo") + _num(r, "def_tackle_assists"),
                        pd=_num(r, "def_pass_defended"), ff=_num(r, "def_fumbles_forced"))
            p = prev.get(_norm(name))
            line["prev_games"] = _num(p, "games") if p else 0.0
            out.append(line)
    return out


def profiles(lines=None):
    """Summary per award: group shares and averages (stats per 17 team games)."""
    lines = lines or winner_lines()
    out = {}
    for award in WINNERS:
        rows = [x for x in lines if x["award"] == award]
        n = len(rows)
        groups = Counter(x["group"] for x in rows)
        prof = {"n": n, "groups": {g: c / n for g, c in groups.items()}}
        ok = [x for x in rows if not x.get("missing") and x.get("win_pct") is not None]
        if ok:
            prof["win_pct"] = sum(x["win_pct"] for x in ok) / len(ok)
            prof["playoffs"] = sum(1 for x in ok if x["playoffs"]) / len(ok)
            prof["games_share"] = sum(min(1, x["games"] / x["team_games"]) for x in ok) / len(ok)
            for grp, stats in (("QB", ("pass_yds", "pass_td", "pass_int", "rush_yds")),
                               ("RB", ("rush_yds", "rush_td", "rec_yds")),
                               ("WR", ("rec", "rec_yds", "rec_td")),
                               ("EDGE", ("sacks", "ff", "tackles")), ("DT", ("sacks", "tackles")),
                               ("LB", ("tackles", "sacks", "def_int")), ("CB", ("def_int", "pd")),
                               ("S", ("def_int", "pd", "tackles"))):
                gl = [x for x in ok if x["group"] == grp]
                if gl:
                    prof[grp] = {s: sum(x[s] * 17 / x["team_games"] for x in gl) / len(gl) for s in stats}
        if award == "cpoy":
            prof["kinds"] = {k: c / n for k, c in Counter(x["kind"] for x in rows).items()}
        out[award] = prof
    # How often the MVP also won Offensive Player of the Year.
    mvp = {(x["season"], x["name"]) for x in lines if x["award"] == "mvp"}
    opoy = [(x["season"], x["name"]) for x in lines if x["award"] == "opoy"]
    out["opoy"]["also_mvp"] = sum(1 for k in opoy if k in mvp) / len(opoy)
    recent = [k for k in opoy if k[0] >= 2016]
    out["opoy"]["also_mvp_since_2016"] = sum(1 for k in recent if k in mvp) / len(recent)
    return out


def main():
    lines = winner_lines()
    missing = [f"{x['season']} {x['name']}" for x in lines if x.get("missing")]
    for award, prof in profiles(lines).items():
        print(f"{AWARD_NAMES[award]} ({prof['n']} winners)")
        print("  groups: " + ", ".join(f"{g} {v:.0%}" for g, v in sorted(prof["groups"].items(), key=lambda kv: -kv[1])))
        if "win_pct" in prof:
            print(f"  team win% {prof['win_pct']:.3f}, made playoffs {prof['playoffs']:.0%}, "
                  f"played {prof['games_share']:.0%} of games")
        for grp in ("QB", "RB", "WR", "EDGE", "DT", "LB", "CB", "S"):
            if grp in prof:
                print(f"  {grp}: " + ", ".join(f"{k} {v:.1f}" for k, v in prof[grp].items()))
        if "kinds" in prof:
            print("  kinds: " + ", ".join(f"{k} {v:.0%}" for k, v in prof["kinds"].items()))
        if "also_mvp" in prof:
            print(f"  also MVP: {prof['also_mvp']:.0%} (since 2016: {prof['also_mvp_since_2016']:.0%})")
    if missing:
        print("Not found in the stats files:", ", ".join(missing))


if __name__ == "__main__":
    sys.exit(main())
