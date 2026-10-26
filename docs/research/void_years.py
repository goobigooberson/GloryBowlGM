"""Real NFL void years, restructures and dead money: the targets for the game's void years
(Oct 26, 2026; engine/contracts.py, engine/free_agency.py VOID_*; tools/free_agency_check.py and
tools/scoreboard.py read real_void_years.json). Write-up: void_years.md.

Two kinds of source:
  - Spotrac team cap tables 2013-25 (already fetched for the GM research: real_gm.json
    "spotrac_raw", [total allocations, cap space, dead cap] per team-year): dead money over the
    whole league year as a share of the team's cap. Computed here.
  - OverTheCap articles (read Oct 26, 2026; figures copied by hand, below):
      * "Creating Cap Space by Extending Players with Void Years" (Jan 29, 2024): 73 contracts set
        to void in 2024; OTC books the void charge because it happens "over 80% of the time" (the
        rest are extended first); teams with no automatic voids in 2024: Bears, Colts, Chargers,
        Steelers, Broncos, Jaguars, Bengals, Cardinals, Rams (9), so 23 teams had at least one.
      * "Examining the Pros and Cons of Void Years for Salary Cap Relief" (Apr 19, 2023): void money
        already set to land in 2024 / 2025 / 2026, by team (a snapshot a year or more ahead, so it
        understates the final years: more void deals are added every year). 2024: 63 players at 22
        teams, $274.4M; Saints 23.0% of the cap, Vikings 18.2%, then 8.6% and below. 2025: 67
        players at 19 teams, $406.5M; Eagles 21.1%, Cowboys 20.5%, Buccaneers 19.3%, Rams 14.7%,
        Saints 11.9%. The 2023 Buccaneers: about $53M of dead money from deals voiding (23.4%).
      * "Looking at Restructuring NFL Contracts" (June 10, 2021), 2013-20 adjusted to a $182M cap:
        55% of teams restructure at all in a year (42% in 2017-19, ~73% in 2020-21), 37% more than
        $6.5M (3.6% of the cap), 20% $15M or more (8.2%). By the prior season's wins, none / up to
        3.6% / 3.6-8.2% / 8.2%+: 10+ wins 37.5 / 19.3 / 21.6 / 21.6%; 0-5 wins 59.0 / 15.4 / 15.4 /
        10.3%. In 2021, 17 teams were already over $15M by June (usually 6-8, prior high 11).
No league-wide count of in-season restructures exists that I could find (team reports only:
Cowboys, Dolphins, Bills before trade deadlines), so that part of the game is judgment.

    python docs/research/void_years.py
"""
import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent

sp = json.loads((HERE / "real_gm.json").read_text())["spotrac_raw"]
by_year = {}
for key, (total, space, dead) in sp.items():
    _team, year = key.split("-")
    by_year.setdefault(int(year), []).append(dead / (total + space))
dead_years = {}
for y, v in sorted(by_year.items()):
    v = sorted(v)
    n = len(v)
    dead_years[y] = {"mean": round(st.mean(v), 4), "median": round(v[n // 2], 4), "p90": round(v[int(0.9 * n)], 4),
                     "max": round(v[-1], 4), "teams_20pct": sum(x >= 0.20 for x in v)}
ERA = (2022, 2023, 2024, 2025)          # the void-year era (after the 2021 COVID cap drop made them common)


def era(k):
    return round(st.mean(dead_years[y][k] for y in ERA), 4)


targets = {
    # dead money over the league year (Spotrac), 2022-25 average; 2013-25 for reference in the notes
    "dead_end_mean": {"real": era("mean"), "note": "Spotrac 2022-25 average of team dead money / cap "
                      f"(2013-25: {round(st.mean(x for v in by_year.values() for x in v), 4)})"},
    "dead_end_p90": {"real": era("p90"), "note": "Spotrac 2022-25, 90th percentile team"},
    "dead_end_20": {"real": era("teams_20pct"), "note": "Spotrac 2022-25: teams at 20%+ (9, 13, 15, 13)"},
    # restructures (OTC 2013-20)
    "restr_none": {"real": 0.45, "note": "OTC 2013-20: 45% of team-years without a restructure (2017-19 58%, 2020-21 ~27%)"},
    "restr_mid": {"real": 0.17, "note": "OTC 2013-20: 3.6-8.2% of the cap"},
    "restr_big": {"real": 0.20, "note": "OTC 2013-20: 8.2%+ of the cap (2021: 53% by June)"},
    # void years (OTC)
    "voided": {"real": 73, "note": "OTC Jan 2024: 73 deals set to void in 2024 (over 80% do; the rest are extended)"},
    "voided_teams": {"real": 23, "note": "OTC Jan 2024: 9 teams had none"},
    "void_dead_mean": {"real": 0.04, "note": "OTC Apr 2023 snapshots: 2024 3.4%, 2025 4.5% of the cap a team on "
                       "average, a year or more ahead (more get added): about 4%, judgment from snapshots"},
    "void_dead_max": {"real": 0.22, "note": "OTC Apr 2023: the most 23.0% (2024), 21.1% (2025)"},
    "void_dead_10": {"real": 3.5, "note": "OTC Apr 2023: teams at 10%+ 2 (2024), 5 (2025)"},
}
out = {"source": __doc__.split("\n\n")[0], "dead_by_year": dead_years, "targets": targets,
       "restructures_by_prior_wins": {"10+": [0.375, 0.193, 0.216, 0.216], "8-10": [0.408, 0.163, 0.204, 0.224],
                                      "5-8": [0.475, 0.200, 0.138, 0.188], "0-5": [0.590, 0.154, 0.154, 0.103],
                                      "buckets": "none / up to 3.6% / 3.6-8.2% / 8.2%+ of the cap"}}
(HERE / "real_void_years.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
for y, d in dead_years.items():
    print(y, d)
print({k: v["real"] for k, v in targets.items()})
