# tools/injury_data.py
# How real NFL injuries play out, from nflverse weekly injury reports
# (2013-2025, joined to snap counts by player and week):
#   1. Games missed per injury, by body part: an injury "episode" starts the
#      first week a player who played recently is listed with that injury;
#      games missed = the team's games he sits out until he plays again
#      (seasons that end first are counted as "rest of season").
#   2. Game-day status: how often a player listed Questionable or Doubtful
#      actually plays, and how much (share of his usual snaps).
# Note: players hurt in a game and put on injured reserve right away often
# never appear on a weekly report, so the longest injuries are undercounted
# here; published studies fill those in (see engine/injuries.py).
#
# Run from the project folder:  python tools/injury_data.py

import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aging_curves import rows, num  # noqa: E402

PARTS = {"rib": "ribs", "ankles": "ankle", "knees": "knee", "quadricep": "quad", "quadriceps": "quad",
         "hamstrings": "hamstring", "heel": "foot", "toe": "toe", "toes": "toe", "thumb": "hand", "finger": "hand",
         "fingers": "hand", "wrist": "hand", "fibula": "lower leg", "shin": "lower leg", "tibia": "lower leg",
         "abdomen": "core", "oblique": "core", "core": "core", "pectoral": "chest", "biceps": "arm",
         "tricep": "arm", "triceps": "arm", "forearm": "arm", "elbow": "elbow", "head": "concussion",
         "thigh": "quad"}
SKIP = {"", "illness", "not injury related", "personal", "rest", "resting", "not injury related - resting player"}


def part_of(text):
    t = (text or "").strip().lower()
    for side in ("right ", "left ", "r ", "l "):
        if t.startswith(side):
            t = t[len(side):]
    t = t.split(",")[0].split("/")[0].strip()
    if t in SKIP:
        return None
    return PARTS.get(t, t)


def main():
    gsis_to_pfr = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("gsis_id") and r.get("pfr_id"):
                gsis_to_pfr[r["gsis_id"]] = r["pfr_id"]
    episodes = defaultdict(list)          # part -> [games missed (or 99 = rest of season)]
    status_play = defaultdict(lambda: [0, 0, []])  # status -> [listed, played, snap share vs usual]
    by_status_part = defaultdict(lambda: [0, 0])
    for year in range(2013, 2026):
        played = defaultdict(dict)         # pfr id -> {week: share of his side's snaps}
        team_weeks = defaultdict(set)
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            wk = int(r["week"])
            team_weeks[r["team"]].add(wk)
            share = max(num(r["offense_pct"]), num(r["defense_pct"]), num(r["st_pct"]) * 0.3)
            if share > 0:
                played[r["pfr_player_id"]][wk] = max(played[r["pfr_player_id"]].get(wk, 0), share)
        reports = defaultdict(dict)        # pfr id -> {week: (status, part, team)}
        for r in rows(f"injuries_{year}.csv.gz"):
            if r["game_type"] != "REG" or not r["report_status"]:
                continue
            pid = gsis_to_pfr.get(r["gsis_id"])
            part = part_of(r["report_primary_injury"])
            if pid is None or part is None:
                continue
            reports[pid][int(r["week"])] = (r["report_status"], part, r["team"])
        for pid, rep in reports.items():
            games = played.get(pid, {})
            weeks = sorted(rep)
            usual = sorted(games.values())
            usual = usual[len(usual) // 2] if usual else 0
            # Game-day status: did he play that week, and how much vs his usual.
            for wk in weeks:
                status, part, _team = rep[wk]
                s = status_play[status]
                s[0] += 1
                bp = by_status_part[(status, part)]
                bp[0] += 1
                if wk in games:
                    s[1] += 1
                    bp[1] += 1
                    if usual >= 0.5:
                        s[2].append(games[wk] / usual)
            # Episodes: first week listed with a part after having played in the 2 weeks before.
            seen = set()
            for wk in weeks:
                status, part, team = rep[wk]
                if (part, wk - 1) in seen or (part, wk - 2) in seen:
                    seen.add((part, wk))
                    continue
                seen.add((part, wk))
                if not any(w in games for w in (wk - 1, wk - 2, wk - 3)):
                    continue
                schedule = sorted(w for w in team_weeks.get(team, ()) if w >= wk)
                missed, back = 0, False
                for w in schedule:
                    if w in games:
                        back = True
                        break
                    missed += 1
                episodes[part].append(missed if back else 99)
    print("GAMES MISSED PER INJURY (real NFL 2013-2025, from weekly injury reports)")
    print(f"{'injury':14}{'n':>6}{'0':>6}{'1':>6}{'2-3':>6}{'4-7':>6}{'8+':>6}{'rest of szn':>12}{'median':>8}")
    for part, lst in sorted(episodes.items(), key=lambda kv: -len(kv[1])):
        n = len(lst)
        if n < 40:
            continue
        b = [sum(1 for x in lst if x == 0), sum(1 for x in lst if x == 1), sum(1 for x in lst if 2 <= x <= 3),
             sum(1 for x in lst if 4 <= x <= 7), sum(1 for x in lst if 8 <= x < 99), sum(1 for x in lst if x == 99)]
        print(f"{part:14}{n:6}" + "".join(f"{100 * v / n:5.0f}%" for v in b[:5]) + f"{100 * b[5] / n:11.0f}%"
              + f"{median(lst):8.0f}")
    print("\nGAME-DAY STATUS: share who played, and snaps vs his usual when he did")
    for status in ("Questionable", "Doubtful", "Out"):
        n, p, shares = status_play[status]
        if n:
            print(f"  {status:13} listed {n:6}  played {100 * p / n:5.1f}%"
                  + (f"  snaps vs usual: median {100 * median(shares):.0f}%" if shares else ""))
    print("\nQUESTIONABLE, share who played, by injury")
    for (status, part), (n, p) in sorted(by_status_part.items(), key=lambda kv: -kv[1][0]):
        if status == "Questionable" and n >= 150:
            print(f"  {part:14} {n:6}  played {100 * p / n:5.1f}%")


def ir_stints():
    """Injured-reserve stints from weekly rosters (status RES), 2013-2025: a
    player who was active and playing goes on reserve during the season.
    Linked to his last injury-report entry (if any) in the two weeks before.
    Returns [(season, part or 'not on a report', games missed or 99)]."""
    gsis_to_pfr = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("gsis_id") and r.get("pfr_id"):
                gsis_to_pfr[r["gsis_id"]] = r["pfr_id"]
    out = []
    for year in range(2013, 2026):
        if year in (2020, 2021):
            continue                              # the reserve list also held COVID cases those years
        played = defaultdict(set)
        team_weeks = defaultdict(set)
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            team_weeks[r["team"]].add(int(r["week"]))
            if max(num(r["offense_pct"]), num(r["defense_pct"]), num(r["st_pct"])) > 0:
                played[r["pfr_player_id"]].add(int(r["week"]))
        last_report = defaultdict(dict)
        for r in rows(f"injuries_{year}.csv.gz"):
            if r["game_type"] == "REG" and r["report_status"]:
                part = part_of(r["report_primary_injury"])
                if part:
                    last_report[r["gsis_id"]][int(r["week"])] = part
        status = defaultdict(dict)
        path = Path(__file__).resolve().parent / "data" / "nflverse" / "weekly_rosters" / f"roster_weekly_{year}.csv.gz"
        if not path.exists():
            continue
        import csv
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["game_type"] == "REG" and r["week"]:
                    status[r["gsis_id"]][int(r["week"])] = (r["status"], r["team"])
        for gsis, weeks in status.items():
            pid = gsis_to_pfr.get(gsis)
            if pid is None:
                continue
            wk_sorted = sorted(weeks)
            for i, wk in enumerate(wk_sorted):
                st, team = weeks[wk]
                prev = weeks.get(wk - 1, ("", ""))[0]
                if st != "RES" or prev == "RES":
                    continue
                if not any(w in played[pid] for w in (wk - 1, wk - 2, wk - 3)):
                    continue                      # wasn't playing before: not a fresh in-season injury
                rep = last_report.get(gsis, {})
                part = next((rep[w] for w in (wk, wk - 1, wk - 2) if w in rep), "not on a report")
                games = sorted(w for w in team_weeks.get(team, ()) if w >= wk)
                missed, back = 0, False
                for w in games:
                    if w in played[pid]:
                        back = True
                        break
                    missed += 1
                out.append((year, part, missed if back else 99))
    return out


def ir_report():
    stints = ir_stints()
    seasons = len({s for s, _p, _m in stints})
    print(f"\nINJURED RESERVE (in season, players who had been playing), {seasons} seasons: "
          f"{len(stints) / seasons:.0f} a season")
    by = defaultdict(list)
    for _s, part, m in stints:
        by[part].append(m)
    print(f"{'injury':16}{'per season':>11}{'back same season':>18}{'games missed if back (median)':>32}")
    for part, lst in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(lst) < 15:
            continue
        back = [m for m in lst if m < 99]
        print(f"{part:16}{len(lst) / seasons:11.1f}{100 * len(back) / len(lst):17.0f}%"
              + (f"{median(back):32.0f}" if back else f"{'-':>32}"))


def episodes_all(with_ids=False):
    """Every real injury that cost a contributor at least one game, 2013-2025
    (not 2020-21): weekly-report episodes, plus injured-reserve stints that
    never appeared on a report. [(season, week hurt, part, games missed or
    None if it ran past the season's end, games left in his season)]."""
    gsis_to_pfr = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("gsis_id") and r.get("pfr_id"):
                gsis_to_pfr[r["gsis_id"]] = r["pfr_id"]
    import csv
    import gzip
    out = []
    for year in range(2013, 2026):
        if year in (2020, 2021):
            continue
        played = defaultdict(set)
        team_weeks = defaultdict(set)
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            team_weeks[r["team"]].add(int(r["week"]))
            if max(num(r["offense_pct"]), num(r["defense_pct"]), num(r["st_pct"])) > 0:
                played[r["pfr_player_id"]].add(int(r["week"]))
        rep = defaultdict(dict)
        for r in rows(f"injuries_{year}.csv.gz"):
            if r["game_type"] == "REG" and r["report_status"]:
                part = part_of(r["report_primary_injury"])
                if part:
                    rep[r["gsis_id"]][int(r["week"])] = (part, r["team"])
        res = defaultdict(dict)
        path = Path(__file__).resolve().parent / "data" / "nflverse" / "weekly_rosters" / f"roster_weekly_{year}.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["game_type"] == "REG" and r["week"]:
                    res[r["gsis_id"]][int(r["week"])] = (r["status"], r["team"])
        for gsis in set(rep) | set(res):
            pid = gsis_to_pfr.get(gsis)
            if pid is None:
                continue
            g = played[pid]
            starts = []
            for wk, (part, team) in sorted(rep.get(gsis, {}).items()):
                if any(w in g for w in (wk - 1, wk - 2, wk - 3)) and not any(
                        rep[gsis].get(w, ("",))[0] == part for w in (wk - 1, wk - 2)):
                    starts.append((wk, part, team))
            covered = {s[0] for s in starts} | {s[0] + 1 for s in starts}
            for wk, (st, team) in sorted(res.get(gsis, {}).items()):
                if st == "RES" and res[gsis].get(wk - 1, ("",))[0] != "RES" and wk not in covered \
                        and any(w in g for w in (wk - 1, wk - 2, wk - 3)):
                    starts.append((wk, "not on a report", team))
            for wk, part, team in starts:
                sched = sorted(w for w in team_weeks.get(team, ()) if w >= wk)
                missed, back = 0, False
                for w in sched:
                    if w in g:
                        back = True
                        break
                    missed += 1
                if missed == 0:
                    continue                       # listed but played: not a missed-game injury
                out.append((year, wk, part, missed if back else None, len(sched)) + ((pid,) if with_ids else ()))
    return out


def season_buckets():
    eps = episodes_all()
    seasons = len({e[0] for e in eps})
    b = defaultdict(int)
    for _y, _wk, _p, m, _left in eps:
        k = ("rest of season" if m is None else "1" if m == 1 else "2-3" if m <= 3 else "4-7" if m <= 7
             else "8+")
        b[k] += 1
    print(f"\nREAL INJURIES THAT COST GAMES, per season ({seasons} seasons, contributors only):")
    print("  " + ", ".join(f"{k}: {b[k] / seasons:.0f}" for k in ("1", "2-3", "4-7", "8+", "rest of season"))
          + f"; total {sum(b.values()) / seasons:.0f}")
    # Injuries early in the season (weeks 1-6) show how long injuries really are,
    # before the season's end cuts them short.
    early = [(p, m) for _y, wk, p, m, _l in eps if wk <= 6]
    b2 = defaultdict(int)
    for _p, m in early:
        k = ("past season end" if m is None else "1" if m == 1 else "2-3" if m <= 3 else "4-7" if m <= 7
             else "8-11" if m <= 11 else "12+")
        b2[k] += 1
    n = len(early)
    print("  Hurt in weeks 1-6 (length less cut off by the season's end): "
          + ", ".join(f"{k}: {100 * b2[k] / n:.0f}%" for k in ("1", "2-3", "4-7", "8-11", "12+",
                                                               "past season end")))
    return eps


if __name__ == "__main__":
    main()
    ir_report()
    season_buckets()
