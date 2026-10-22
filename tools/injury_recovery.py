# tools/injury_recovery.py
# How each kind of injury behaves while a player plays through it or comes
# back from it (Blake, Oct 21: hamstrings and high ankle sprains re-aggravate,
# bruises are pain tolerance; the tags only say where he is in recovery).
# Real data, 2018-2025 regular seasons: weekly injury reports (body part,
# status) joined to snap counts (who played, how much) and play-by-play.
#
# For each body part:
#   listed-and-played games: he's on the report with it and plays anyway
#     snaps     his snap share that game vs his usual
#     aggravate he then misses the next game with the same body part
#   comeback games: his first 4 games back after missing games with it
#     reinjury  per game, he's listed with the same body part again and misses
#               the following game (the injury flared up)
#   baseline: a healthy regular's chance per game of a NEW injury to that same
#     body part that costs the next game (so the excess is the injury's own risk)
#   per-play results while listed (QB/RB/WR/TE): EPA per play vs his own other
#     games (small samples for some parts; see the n column)
#
# Run from the project folder:  python tools/injury_recovery.py

import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aging_curves import rows, num  # noqa: E402
from injury_data import part_of  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
YEARS = range(2018, 2026)
COMEBACK_GAMES = 4


def main(with_epa=True):
    gsis_to_pfr = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("gsis_id") and r.get("pfr_id"):
                gsis_to_pfr[r["gsis_id"]] = r["pfr_id"]
    S = defaultdict(lambda: {"played": 0, "snap_ratio": [], "aggr": 0, "cb_games": 0, "cb_re": 0})
    base_games = 0
    base_new = defaultdict(int)
    epa = defaultdict(list)            # part -> [(diff, n plays)]
    for year in YEARS:
        played = defaultdict(dict)
        team_weeks = defaultdict(set)
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            team_weeks[r["team"]].add(int(r["week"]))
            s = max(num(r["offense_pct"]), num(r["defense_pct"]))
            if s > 0:
                played[r["pfr_player_id"]][int(r["week"])] = (s, r["team"])
        rep = defaultdict(dict)
        for r in rows(f"injuries_{year}.csv.gz"):
            if r["game_type"] == "REG" and r["report_status"]:
                p = part_of(r["report_primary_injury"])
                if p:
                    rep[r["gsis_id"]][int(r["week"])] = (r["report_status"], p)
        q_weeks = defaultdict(dict)    # gsis -> week -> part (listed and played), for the EPA pass
        for gsis, pid in gsis_to_pfr.items():
            games = played.get(pid)
            if not games:
                continue
            shares = sorted(s for s, _t in games.values())
            if len(shares) < 6 or shares[len(shares) // 2] < 0.4:
                continue                                  # regulars only
            usual = shares[len(shares) // 2]
            team = next(iter(games.values()))[1]
            sched = sorted(team_weeks[team])
            r = rep.get(gsis, {})
            for i, w in enumerate(sched):
                nxt = sched[i + 1] if i + 1 < len(sched) else None
                st, part = r.get(w, ("", None))
                if w in games and nxt is not None:
                    if not st:
                        base_games += 1
                        nst, npart = r.get(nxt, ("", None))
                        if nst and nxt not in games and npart:
                            base_new[npart] += 1
                    else:
                        a = S[part]
                        a["played"] += 1
                        a["snap_ratio"].append(games[w][0] / usual)
                        q_weeks[gsis][w] = part
                        nst, npart = r.get(nxt, ("", None))
                        if nxt not in games and nst and npart == part:
                            a["aggr"] += 1
                # comeback: he missed the game before with this part, plays now
                if i > 0 and w in games and sched[i - 1] not in games:
                    pst, ppart = r.get(sched[i - 1], ("", None))
                    if ppart:
                        for j in range(i, min(i + COMEBACK_GAMES, len(sched) - 1)):
                            g, ng = sched[j], sched[j + 1]
                            if g not in games:
                                break
                            S[ppart]["cb_games"] += 1
                            nst, npart = r.get(ng, ("", None))
                            if ng not in games and nst and npart == ppart:
                                S[ppart]["cb_re"] += 1
                                break
        if with_epa:
            path = DATA / "nflverse" / "pbp" / f"play_by_play_{year}.csv.gz"
            per = defaultdict(lambda: defaultdict(list))
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("season_type") != "REG":
                        continue
                    e = num(row.get("epa"))
                    if not row.get("epa"):
                        continue
                    wk = int(row["week"])
                    for col in ("passer_player_id", "rusher_player_id", "receiver_player_id"):
                        pid = row.get(col)
                        if pid:
                            per[pid][wk].append(e)
            for gsis, weeks in per.items():
                qw = q_weeks.get(gsis, {})
                if not qw:
                    continue
                other = [e for w, es in weeks.items() if w not in qw for e in es]
                if len(other) < 60:
                    continue
                by_part = defaultdict(list)
                for w, part in qw.items():
                    by_part[part] += weeks.get(w, [])
                for part, es in by_part.items():
                    if len(es) >= 8:
                        epa[part].append((mean(es) - mean(other), len(es)))
        print(f"{year} done", flush=True)
    print(f"\nHealthy regulars: {base_games} games. Per body part below, n = games.")
    print(f"{'injury':12}{'played listed':>14}{'snaps vs usual':>15}{'aggravated':>11}{'baseline':>9}"
          f"{'comeback g':>11}{'flare-up/g':>11}{'EPA/play':>10}{'plays':>7}")
    for part, a in sorted(S.items(), key=lambda kv: -kv[1]["played"]):
        if a["played"] < 80:
            continue
        b = base_new[part] / base_games
        e = epa.get(part, [])
        ew = sum(n for _d, n in e)
        ediff = sum(d * n for d, n in e) / ew if ew else 0
        print(f"{part:12}{a['played']:14}{100 * median(a['snap_ratio']):14.0f}%{100 * a['aggr'] / a['played']:10.1f}%"
              f"{100 * b:8.2f}%{a['cb_games']:11}{100 * a['cb_re'] / max(1, a['cb_games']):10.1f}%"
              f"{ediff:+10.3f}{ew:7}")


if __name__ == "__main__":
    main(with_epa="--no-epa" not in sys.argv)
