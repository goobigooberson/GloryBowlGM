# step6_season_test.py
# Step 6 test: plays a full 17-game regular season with the game sim and
# compares the league's stats to the real NFL.
# Run it from the terminal (in the project folder) with:
#     python step6_season_test.py
#
# It uses your saved league (saves/league.db) if there is one, but it does
# NOT change it: nothing is saved. Injuries carry over from week to week
# during the test season, like they will in the real season later.
# The report is printed and also written to step6_season_report.txt.
#
# Real NFL numbers: team averages are 2023-2025; leaderboards and "how
# common" counts are 2021-2025 (the 17-game seasons). Tackles for loss use
# 2024-2025 only, because the NFL started recording far more of them in 2024.

import random
import time
from collections import defaultdict
from pathlib import Path

from engine.database import load_league
from engine.league import create_league
from engine.sim.game import Game
from engine.injury_report import InjuryReport
from engine import transactions
from engine.sim.norms import build_norms
from engine.sim.stats import passer_rating

SAVE_FILE = Path("saves/league.db")
REPORT_FILE = Path("step6_season_report.txt")

# Real NFL, per team per game, 2023-2025 regular seasons.
REAL = [
    ("Points", "points", 22.6),
    ("Total yards", "total_yds", 333),
    ("Offensive plays", "plays", 62.4),
    ("Pass attempts", "pass_att", 33.0),
    ("Completion %", "cmp_pct", 64.4),
    ("Passing yards (gross)", "pass_yds", 231.6),
    ("Yards per attempt", "ypa", 7.02),
    ("Passing TDs", "pass_td", 1.45),
    ("Interceptions thrown", "int_thrown", 0.73),
    ("Sacks allowed", "sacked", 2.46),
    ("Rushes (incl. scrambles)", "rush_att", 26.2),
    ("Rushing yards", "rush_yds", 117),
    ("Yards per carry", "ypc", 4.48),
    ("Rushing TDs", "rush_td", 0.91),
    ("First downs", "fd", 19.2),
    ("3rd down conversion %", "third_pct", 39.3),
    ("Fumbles lost", "fum_lost", 0.50),
    ("Penalties", "penalties", 6.17),
    ("Penalty yards", "penalty_yds", 50.1),
    ("Punts", "punts", 3.8),
    ("Field goal attempts", "fga", 2.0),
    ("Field goal %", "fg_pct", 85.2),
    ("Extra point %", "xp_pct", 95.9),
]

# How many players reach each mark in a real season (2021-25): average, lowest, highest.
# (label, stat, minimum, positions or None for everyone, real average, real low, real high)
COMMON = [
    ("4,000+ passing yards", "pass_yds", 4000, None, 8.2, 6, 10),
    ("4,500+ passing yards", "pass_yds", 4500, None, 3.8, 3, 6),
    ("30+ passing TDs", "pass_td", 30, None, 5.2, 4, 9),
    ("15+ interceptions thrown", "pass_int", 15, None, 3.0, 2, 5),
    ("1,000+ rushing yards", "rush_yds", 1000, None, 13.6, 7, 17),
    ("1,500+ rushing yards", "rush_yds", 1500, None, 1.8, 0, 3),
    ("250+ carries", "rush_att", 250, None, 8.2, 4, 12),
    ("10+ rushing TDs", "rush_td", 10, None, 10.0, 8, 13),
    ("1,000+ receiving yards", "rec_yds", 1000, None, 24.0, 20, 28),
    ("1,400+ receiving yards", "rec_yds", 1400, None, 4.4, 2, 5),
    ("100+ receptions", "rec", 100, None, 9.6, 7, 12),
    ("10+ receiving TDs", "rec_td", 10, None, 7.0, 5, 8),
    ("Tight ends with 1,000+ receiving yards", "rec_yds", 1000, ("TE",), 1.8, 1, 3),
    ("Running backs with 60+ receptions", "rec", 60, ("RB", "FB"), 4.6, 3, 6),
    ("120+ tackles", "tackles", 120, None, 27.0, 20, 30),
    ("140+ tackles", "tackles", 140, None, 11.8, 10, 13),
    ("10+ sacks", "sacks", 10, None, 18.8, 17, 24),
    ("15+ sacks", "sacks", 15, None, 3.6, 1, 5),
    ("5+ interceptions", "def_int", 5, None, 8.6, 6, 11),
    ("15+ passes defensed", "pd", 15, None, 9.8, 8, 11),
    ("4+ forced fumbles", "ff", 4, None, 8.4, 5, 12),
    ("15+ tackles for loss (2024-25)", "tfl", 15, None, 12.5, 10, 15),
]


def round_robin_weeks(team_ids, weeks, rng):
    """Circle-method round robin: every team plays a different opponent each
    week. Home and away alternate so most teams get 8 or 9 home games."""
    ids = list(team_ids)
    rng.shuffle(ids)
    n = len(ids)
    schedule = []
    for w in range(weeks):
        games = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            games.append((a, b) if (w + i) % 2 == 0 else (b, a))
        schedule.append(games)
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    return schedule


def main():
    started = time.time()
    if SAVE_FILE.exists():
        league = load_league(SAVE_FILE)
        source = "your saved league (not changed)"
    else:
        league = create_league(season=2026)
        source = "a brand-new league (not saved)"
    norms = build_norms(league)
    rng = random.Random()
    schedule = round_robin_weeks([t.id for t in league.teams], 17, rng)

    # The same injury rules as the season loop (engine/injury_report.py).
    salt = rng.random()
    report = InjuryReport({}, {}, lambda cal, pid, what: random.Random(f"{what}-{cal}-{pid}-{salt}"))
    # The season loop's roster moves too (engine/transactions.py): training camp
    # and preseason injuries, final cuts, then injured reserve, signings and
    # practice squads every week. Every team makes AI moves.
    league.user_team_id = None
    moves_rng = random.Random(salt)
    transactions.lab_preseason(league, report, moves_rng)
    record = defaultdict(lambda: [0, 0, 0, 0, 0])   # W, L, T, PF, PA
    season = defaultdict(lambda: defaultdict(float))  # player id -> stat -> total
    games_played = defaultdict(int)
    team_tot = defaultdict(float)
    team_games = 0
    injuries = 0
    games_missed = 0
    missed_by_team = defaultdict(int)
    owner = {}

    for week, games in enumerate(schedule, start=1):
        for home, away in games:
            unavailable = {tid: report.unavailable(tid, week) for tid in (home, away)}
            hurt = {tid: report.playing_hurt(tid, week) for tid in (home, away)}
            games_missed += len(unavailable[home]) + len(unavailable[away])
            for tid in (home, away):
                missed_by_team[tid] += len(unavailable[tid])
            extra = transactions.lab_elevations(league, report, (home, away), unavailable)
            g = Game(league, home, away, seed=rng.random(), week=week, norms=norms,
                     unavailable=unavailable, hurt=hurt, extra=extra).run()
            transactions.count_reserve_games(league, (home, away))
            hs, as_ = g.state.score
            for tid, pf, pa in ((home, hs, as_), (away, as_, hs)):
                r = record[tid]
                r[0 if pf > pa else (1 if pf < pa else 2)] += 1
                r[3] += pf
                r[4] += pa
            for pid, line in g.box.players.items():
                idx = g.box.owner[pid]
                owner[pid] = g.teams[idx].id
                games_played[pid] += 1
                for k, v in line.items():
                    if k.endswith("_long"):
                        season[pid][k] = max(season[pid][k], v)
                    else:
                        season[pid][k] += v
            for idx in (0, 1):
                t = g.box.team[idx]
                team_games += 1
                team_tot["points"] += g.state.score[idx]
                for k, v in t.items():
                    team_tot[k] += v
            # Injuries: this game's, plus aggravations and flare-ups.
            injuries += len(report.after_game((home, away), week, set(g.box.players), g.injuries()))
        report.end_week(week)
        transactions.weekly(league, report.injuries, report.recovering, week, f"Week {week}", moves_rng)

    elapsed = time.time() - started
    players = {p.id: p for p in league.players}
    for pid in season:
        season[pid]["tackles"] = season[pid]["tkl"] + season[pid]["ast"]
    lines = []
    say = lines.append

    say("=" * 78)
    say(f"  STEP 6 TEST SEASON: 17 weeks, 272 games, using {source}")
    say(f"  Simulated in {elapsed:.1f} seconds ({elapsed / 272 * 1000:.0f} ms per game)")
    say("=" * 78)

    # ---- League averages vs the real NFL ---------------------------------
    n = team_games
    avg = {k: v / n for k, v in team_tot.items()}
    avg["cmp_pct"] = 100 * team_tot["pass_cmp"] / max(1, team_tot["pass_att"] - team_tot["spikes"])
    avg["ypa"] = team_tot["pass_yds"] / max(1, team_tot["pass_att"] - team_tot["spikes"])
    avg["ypc"] = (team_tot["rush_yds"] + team_tot["kneels"]) / max(1, team_tot["rush_att"] - team_tot["kneels"])
    avg["rush_att"] = (team_tot["rush_att"] - team_tot["kneels"]) / n
    avg["total_yds"] = (team_tot["rush_yds"] + team_tot["pass_yds"] - team_tot["sacked_yds"]) / n
    avg["fd"] = (team_tot["fd_rush"] + team_tot["fd_pass"] + team_tot["fd_pen"]) / n
    avg["third_pct"] = 100 * team_tot["third_conv"] / max(1, team_tot["third_att"])
    avg["fg_pct"] = 100 * team_tot["fgm"] / max(1, team_tot["fga"])
    avg["xp_pct"] = 100 * team_tot["xpm"] / max(1, team_tot["xpa"])
    say("")
    say("  LEAGUE AVERAGES PER TEAM PER GAME        This season    Real NFL")
    say("  " + "-" * 64)
    for label, key, real in REAL:
        say(f"  {label:38} {avg.get(key, 0):>10.1f} {real:>11.1f}")

    # ---- Standings --------------------------------------------------------
    say("")
    say("  STANDINGS")
    by_div = defaultdict(list)
    for t in league.teams:
        by_div[(t.conference, t.division)].append(t)
    for (conf, div), teams in sorted(by_div.items()):
        say(f"  {conf} - {div}")
        teams.sort(key=lambda t: (record[t.id][0] + 0.5 * record[t.id][2], record[t.id][3] - record[t.id][4]),
                   reverse=True)
        for t in teams:
            w, l, ti, pf, pa = record[t.id]
            rec = f"{w}-{l}" + (f"-{ti}" if ti else "")
            star = "  <- your team" if t.id == league.user_team_id else ""
            say(f"     {t.name:28} {rec:>7}   PF {pf:>4}  PA {pa:>4}  ({pf - pa:+d}){star}")

    # ---- How common are big seasons? ---------------------------------------
    say("")
    say("  HOW COMMON ARE BIG SEASONS?            This season   Real NFL average (range)")
    say("  " + "-" * 76)
    for label, key, mark, positions, r_avg, r_lo, r_hi in COMMON:
        count = sum(1 for pid, s in season.items()
                    if s.get(key, 0) >= mark and (positions is None or players[pid].position in positions))
        say(f"  {label:40} {count:>6}        {r_avg:>5.1f}  ({r_lo}-{r_hi})")

    # ---- Leaders ----------------------------------------------------------
    def who(pid):
        p = players[pid]
        team = league.team(owner[pid]).abbrev if pid in owner else ""
        return f"{p.first_name[0]}. {p.last_name} ({p.position}, {team})"

    def leaders(title, key, extra, k=5, filt=None):
        rows = sorted((pid for pid in season if (filt is None or filt(pid))),
                      key=lambda pid: season[pid][key], reverse=True)[:k]
        say("")
        say(f"  {title}")
        for i, pid in enumerate(rows, 1):
            say(f"    {i}. {who(pid):34} {extra(season[pid])}")

    leaders("PASSING YARDS (real: leader ~4,950; 10th best ~3,900)", "pass_yds",
            lambda s: (f"{s['pass_yds']:,.0f} yds  {s['pass_cmp']:.0f}/{s['pass_att']:.0f} "
                       f"({100 * s['pass_cmp'] / max(1, s['pass_att']):.1f}%)  {s['pass_td']:.0f} TD  "
                       f"{s['pass_int']:.0f} INT  rating "
                       f"{passer_rating(s['pass_att'], s['pass_cmp'], s['pass_yds'], s['pass_td'], s['pass_int']):.1f}"))
    leaders("RUSHING YARDS (real: leader ~1,700; 10th ~1,065)", "rush_yds",
            lambda s: f"{s['rush_yds']:,.0f} yds  {s['rush_att']:.0f} car  "
                      f"{s['rush_yds'] / max(1, s['rush_att']):.1f} avg  {s['rush_td']:.0f} TD")
    leaders("RECEIVING YARDS (real: leader ~1,800; 10th ~1,175)", "rec_yds",
            lambda s: f"{s['rec_yds']:,.0f} yds  {s['rec']:.0f} rec  {s['targets']:.0f} tgt  {s['rec_td']:.0f} TD")
    leaders("RECEPTIONS (real: leader ~133)", "rec", lambda s: f"{s['rec']:.0f} rec  {s['rec_yds']:,.0f} yds")
    leaders("TIGHT END RECEPTIONS (real: leader ~114)", "rec",
            lambda s: f"{s['rec']:.0f} rec  {s['rec_yds']:,.0f} yds  {s['rec_td']:.0f} TD", k=3,
            filt=lambda pid: players[pid].position == "TE")
    leaders("RUNNING BACK RECEPTIONS (real: leader ~87)", "rec",
            lambda s: f"{s['rec']:.0f} rec  {s['rec_yds']:,.0f} yds", k=3,
            filt=lambda pid: players[pid].position in ("RB", "FB"))
    leaders("TACKLES (real: leader ~183; 10th ~145)", "tackles",
            lambda s: f"{s['tackles']:.0f} tackles ({s['tkl']:.0f} solo, {s['ast']:.0f} assisted)")
    leaders("SACKS (real: leader ~20; 10th ~12)", "sacks", lambda s: f"{s['sacks']:.1f} sacks  {s['qb_hits']:.0f} QB hits")
    leaders("TACKLES FOR LOSS (real 2024-25: leader ~27)", "tfl", lambda s: f"{s['tfl']:.0f} TFL", k=3)
    leaders("INTERCEPTIONS (real: leader ~8)", "def_int", lambda s: f"{s['def_int']:.0f} INT  {s['pd']:.0f} passes defensed")
    leaders("PASSES DEFENSED (real: leader ~21)", "pd", lambda s: f"{s['pd']:.0f} PD  {s['def_int']:.0f} INT", k=3)
    leaders("FORCED FUMBLES (real: leader ~6)", "ff", lambda s: f"{s['ff']:.0f} FF", k=3)
    leaders("FIELD GOALS MADE (real: leader ~40)", "fgm", lambda s: f"{s['fgm']:.0f}/{s['fga']:.0f}  long {s['fg_long']:.0f}")

    say("")
    say(f"  Injuries that cost at least one game: {injuries} (about {injuries / 32:.1f} per team)")
    healthiest = min(missed_by_team.values()) if missed_by_team else 0
    most = max(missed_by_team.values()) if missed_by_team else 0
    say(f"  Player-games missed to injury: about {games_missed / 32:.0f} per team on average; "
        f"healthiest team {healthiest}, most injured {most}")
    say("     (real NFL 2024: healthiest team 95, most injured 254. Both include players hurt in")
    say("      training camp and the preseason, and players on injured reserve.)")
    say("")
    text = "\n".join(lines)
    print(text)
    REPORT_FILE.write_text(text, encoding="utf-8")
    print(f"  (Report also saved to {REPORT_FILE})")


if __name__ == "__main__":
    main()
