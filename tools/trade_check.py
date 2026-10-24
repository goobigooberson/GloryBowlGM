# tools/trade_check.py
# Player trades vs the real NFL (Oct 23; engine/trades.py).
#
# Runs generated leagues through several years: a regular season with made-up results
# (from team strength, no game sim) and made-up injuries at the real rate, the game's own
# offseason (every phase, so the trade steps fire as they do in the game: the league year,
# free agency waves, before and after the draft) and training camp with the preseason
# steps (camp, the preseason weeks, cut-down day). Then it measures what
# docs/research/trade_research.py measured for the real NFL (real_trades.json):
#   - trades with players a league year, by phase, by week before the deadline
#   - deals per team a year (spread, teams with none)
#   - what's in them: players for picks, players for players, both
#   - who's traded: position, age, contract size (share of the cap), stars (8%+ of the cap),
#     recent first-rounders
#   - what comes back for a player traded for picks, by his contract size
#   - how far out the future picks traded are
#   - cap legality and roster limits after every step
# And the exploit checks (your team = the first team, at a few points in each league):
#   - position: what an AI team asks for its best players, by position (no cheap TEs)
#   - quantity for quality: three of your average starters for one of its stars
#   - dumping a bad contract for nothing
#   - buy low, sell high: the AI's asking price vs the best another AI team pays
#   - lowballs: a GM who's insulted often enough stops taking your calls
#   - parity: does trading move talent toward the strong teams? (same leagues, trades off)
#
#   python tools/trade_check.py                         (leagues 101-104, 4 seasons each)
#   python tools/trade_check.py --leagues 101,102 --seasons 3
#   python tools/trade_check.py --calls 1.2             (try another CALLS_K)
# Writes tools/trade_report.txt. Nothing is saved; your saves are never touched.

import argparse
import json
import math
import os
import random
import statistics as st
import sys
import time
from collections import defaultdict, Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REAL = json.loads((ROOT / "docs" / "research" / "real_trades.json").read_text())
PHASE_GROUP = {"league_year": "1 league year to draft", "fa_early": "1 league year to draft",
               "pre_draft": "1 league year to draft", "draft": "2 draft", "fa_late": "3 after draft to camp",
               "camp": "4 camp and preseason", "preseason": "4 camp and preseason", "cuts": "4 camp and preseason",
               "season": "5 season to deadline", "deadline": "5 season to deadline"}
GRP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
       "DE": "EDGE", "OLB": "LB", "ILB": "LB", "DT": "DL", "CB": "DB", "S": "DB", "K": "K/P/LS", "P": "K/P/LS",
       "LS": "K/P/LS"}
INJURIES_PER_WEEK = 48          # game-costing injuries a regular-season week, league-wide (real ~820 a season)


def _strength(league):
    """Each team's strength (its starters' overall, QB counted 4 times), as z-scores."""
    from tools import draft_lab
    from engine import depth
    starters = {t.id: depth.starter_ids(league.depth_charts.get(t.id, {})) for t in league.teams}
    pool = [league.player(pid) for s in starters.values() for pid in s if pid in league.rosters]
    stat = draft_lab._z_by_position(pool)
    out = {}
    for t in league.teams:
        zs = []
        for pid in starters[t.id]:
            if pid in league.rosters and pid not in league.injuries:
                p = league.player(pid)
                m, sd = stat[p.position]
                zs += [(p.overall() - m) / sd] * (4 if p.position == "QB" else 1)
        out[t.id] = sum(zs) / max(1, len(zs))
    return out


def _fake_week(league, rng):
    """This week's games with made-up scores (better teams win more), and injuries."""
    from engine import season as S
    z = _strength(league)
    for g in league.schedule:
        if g["week"] != league.week or g["played"]:
            continue
        d = 0.9 * (z[g["home"]] - z[g["away"]]) + 0.15
        p_home = 1 / (1 + math.exp(-1.2 * d))
        hs, as_ = rng.randint(10, 34), rng.randint(10, 34)
        if (rng.random() < p_home) != (hs > as_):
            hs, as_ = as_, hs
        if hs == as_:
            hs += 3
        g.update(played=True, home_score=hs, away_score=as_, overtime=False)
    # injuries heal a week; new ones at the real rate
    for pid in list(league.injuries):
        inj = league.injuries[pid]
        inj["weeks"] -= 1
        if inj["weeks"] <= 0:
            league.injuries.pop(pid)
    rostered = list(league.rosters)
    for pid in rng.sample(rostered, INJURIES_PER_WEEK):
        weeks = rng.choice([1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 10, 17])
        league.injuries[pid] = {"team": league.rosters[pid], "weeks": weeks, "part": "knee", "week": league.week,
                                "kind": "knee_sprain", "initial": weeks, "status": "Out"}


def _season_lines(league, rng):
    from engine import season as S
    rec = S.records(league)
    lines = []
    for t in league.teams:
        r = rec[t.id]
        lines.append({"team": t.id, "season": league.season, "w": r["w"], "l": r["l"], "t": r["t"],
                      "conf": t.conference})
    for conf in ("Eastern", "Western"):
        group = sorted((r for r in lines if r["conf"] == conf), key=lambda r: (r["w"], rng.random()), reverse=True)
        for i, r in enumerate(group):
            r["seed"] = i + 1 if i < 7 else None
    for r in lines:
        r["result"] = "Missed the playoffs"
    alive = sorted((r for r in lines if r["seed"]), key=lambda r: (r["seed"], rng.random()))
    for stage in ("Lost in the Wild Card round", "Lost in the divisional round",
                  "Lost in the conference championship", "Lost the final"):
        alive.sort(key=lambda r: r["seed"] + rng.gauss(0, 3))
        keep = 8 if stage == "Lost in the Wild Card round" else (len(alive) // 2 if len(alive) > 2 else 1)
        for r in alive[keep:]:
            r["result"] = stage
        alive = alive[:keep]
    alive[0]["result"] = "Won the final"
    share = {}
    from engine import depth
    for t in league.teams:
        chart = league.depth_charts.get(t.id, {})
        starters = depth.starter_ids(chart)
        backups = {ids[1] for ids in chart.values() if len(ids) > 1}
        for p in league.team_players(t.id):
            share[p.id] = 0.85 if p.id in starters else (0.3 if p.id in backups else 0.05)
    return lines, share


def _audit(league, out):
    from engine import contracts as C, transactions as TR
    # (Cap: only outside the regular season here. In-season AI teams drift over the cap with or
    # without trades, an existing money quirk; each trade's own legality is checked as it's made.)
    over = [tid for tid in (t.id for t in league.teams) if C.cap_room(league, tid) < 0
            and league.stage != "regular_season"]
    limit = TR.roster_limit(league)
    big = [t.id for t in league.teams if sum(1 for x in league.rosters.values() if x == t.id) > limit]
    if over:
        where = (league.stage, (league.offseason or {}).get("phase") if league.stage == "offseason" else
                 league.pre_week if league.stage == "preseason" else league.week)
        out.setdefault("where", Counter())[str(where)] += len(over)
    out["cap_over"] += len(over)
    out["roster_over"] += len(big)
    if big:
        where = (league.stage, (league.offseason or {}).get("phase") if league.stage == "offseason" else
                 league.pre_week if league.stage == "preseason" else league.week)
        out.setdefault("where_roster", Counter())[str(where)] += len(big)
    out["checks"] += 1


def _true_delta(league, tid, gets_players, gives_players, gets_picks, gives_picks):
    """The AI team's gain with no scouting mistakes (true ratings), chart points."""
    from engine import trades as T, evaluation as E
    plain = E.misjudgment
    E.misjudgment = lambda *a, **k: 0.0
    league.__dict__.pop("_trade_ctx", None)
    try:
        return T.deal_delta(league, tid, gets_players=gets_players, gives_players=gives_players,
                            gets_picks=gets_picks, gives_picks=gives_picks)
    finally:
        E.misjudgment = plain
        league.__dict__.pop("_trade_ctx", None)


def _exploits(league, rng):
    """Your-team checks at this point (the first team plays you)."""
    from engine import trades as T, cap_market as M, contracts as C
    uid = league.teams[0].id
    league.user_team_id = uid
    league.__dict__.pop("_trade_ctx", None)
    res = defaultdict(list)
    ctx = T._ctx(league)
    cap = C.cap_for(league, league.season)
    # 1. What AI teams ask for their best players, by position (and what they'd pay for yours).
    for pos in ("QB", "RB", "WR", "TE", "T", "G", "DE", "DT", "OLB", "CB", "S"):
        group = sorted((p for p in league.players if league.rosters.get(p.id) not in (None, uid)
                        and p.position == pos), key=lambda p: -p.overall())[:5]
        for p in group:
            tid = league.rosters[p.id]
            loss = T.player_value(league, tid, p)
            ask = loss + T.USER_MARGIN[0] + T.USER_MARGIN[1] * max(0.0, loss)
            price = ctx.table[p.id]["price"]
            res[f"ask_{pos}"].append((ask, price))
    # 2. Quantity for quality: three of your average starters for an AI star.
    from engine import depth
    mine = [league.player(pid) for pid in depth.starter_ids(league.depth_charts.get(uid, {}))
            if pid in league.rosters and league.rosters[pid] == uid]
    mine.sort(key=lambda p: p.overall())
    middle = mine[len(mine) // 3: 2 * len(mine) // 3]
    stars = sorted((p for p in league.players if league.rosters.get(p.id) not in (None, uid)),
                   key=lambda p: -T.player_value(league, league.rosters[p.id], p))[:12]
    for star in stars:
        tid = league.rosters[star.id]
        same = [p for p in middle if p.position == star.position][:1]
        offer = (same + [p for p in middle if p not in same])[:3]
        ans = T.answer(league, tid, {"players": [p.id for p in offer], "picks": []},
                       {"players": [star.id], "picks": []}, rng)
        res["qty_for_quality"].append(ans["kind"] if ans["kind"] != "illegal" else "illegal")
        if ans["kind"] == "accept":
            res["qty_true"].append(_true_delta(league, tid, [p.id for p in offer], [star.id], [], []))
    league.trades["mood"] = {}
    # 3. Your worst contract for an AI team's 7th-round pick (dumping it).
    worst = []
    for pid, t in league.rosters.items():
        if t != uid:
            continue
        v = -T.deal_delta(league, uid, gives_players=[pid])
        worst.append((v, pid))
    worst.sort()
    for v, pid in worst[:4]:
        c = league.contracts[pid]
        if c["apy"] / cap < 0.03:
            continue
        for o in [t.id for t in league.teams if t.id != uid][:8]:
            sevenths = [k for k in T.team_picks(league, o) if T.parse_key(k)[1] == 7][:1]
            if not sevenths:
                continue
            ans = T.answer(league, o, {"players": [pid], "picks": []}, {"players": [], "picks": sevenths}, rng)
            res["dump"].append(ans["kind"] if ans["kind"] != "illegal" else "illegal")
            if ans["kind"] == "accept":
                res["dump_true"].append(_true_delta(league, o, [pid], [], [], sevenths))
    league.trades["mood"] = {}
    # 4. Buy low, sell high: an AI team's ask for a player vs the most another AI team would pay you.
    sample = rng.sample([p for p in league.players if league.rosters.get(p.id) not in (None, uid)], 60)
    for p in sample:
        tid = league.rosters[p.id]
        loss = T.player_value(league, tid, p)
        ask = loss + T._need(league, tid, {"players": [p.id], "picks": []}, max(0.0, loss))
        best = max(T.deal_delta(league, o.id, gets_players=[p]) for o in league.teams if o.id not in (tid, uid))
        pay = best - T.USER_MARGIN[0] - T.USER_MARGIN[1] * max(0.0, best)
        res["flip"].append((pay - ask, ask))
    # 5. Lowballs: a 7th-round pick for an AI team's best player, again and again.
    o = league.teams[1].id
    star = max((p for p in league.players if league.rosters.get(p.id) == o),
               key=lambda p: T.player_value(league, o, p))
    seventh = [k for k in T.team_picks(league, uid) if T.parse_key(k)[1] == 7][:1]
    kinds = []
    for _ in range(6):
        ans = T.answer(league, o, {"players": [], "picks": seventh}, {"players": [star.id], "picks": []}, rng)
        kinds.append(ans["kind"] if ans["kind"] != "illegal" else "illegal: " + ans["words"][-30:])
    res["lowball"].append(kinds)
    league.trades["mood"] = {}
    league.user_team_id = None
    league.__dict__.pop("_trade_ctx", None)
    return dict(res)


def _worker(args):
    seed, seasons, calls, exploits = args
    from engine import trades as T
    if calls is not None:
        T.CALLS_K = calls
    from engine import contracts as C, schedule as sched, season as S, transactions as TR, development
    from engine import offseason, evaluation
    from engine.league import create_league
    plain_execute = T.execute
    bad = []

    def checked(lg, a, b, deal, user=False, note=""):
        before = {t: C.cap_room(lg, t) for t in (a, b)}
        e = plain_execute(lg, a, b, deal, user, note)
        for t in (a, b):
            after = C.cap_room(lg, t)
            if after < 0 and after < before[t]:
                bad.append(("cap", lg.season, e["when"], t, after))
            if sum(1 for x in lg.rosters.values() if x == t) > TR.roster_limit(lg):
                bad.append(("roster", lg.season, e["when"], t))
        return e
    T.execute = checked
    from engine import draft_day as DD
    plain_finish = DD.finish
    draft_trades = []

    def finish(lg, *a, **k):
        room = plain_finish(lg, *a, **k)
        if room is not None:
            draft_trades.extend(dict(t) for t in room.trades)
        return room
    DD.finish = finish
    random.seed(f"trade-lab-{seed}")
    league = create_league(seed=seed, camp=False)
    league.settings["salt"] = f"tlab{seed}"
    rng = random.Random(f"trade-lab-run-{seed}")
    T.ensure(league)
    audit = {"cap_over": 0, "roster_over": 0, "checks": 0}
    parity = []
    snaps = []
    exploit = []
    first = league.season
    t0 = time.time()
    starts = []
    for i in range(seasons):
        starts.append(league.trades["step"])
        # ---- the regular season (made-up results), with trade steps up to the deadline ----
        ranks = league.division_ranks or sched.random_division_ranks(league, rng)
        league.schedule = sched.build_schedule(league, league.season, ranks, 17, rng)
        league.preseason, league.playoffs, league.boxes = [], [], {}
        league.stage, league.week = "regular_season", 1
        league.injuries = {}
        from engine import free_agency as FA
        league.recovering = {}
        for w in range(1, 19):
            _fake_week(league, rng)
            # The AI teams' weekly roster moves, as in the game (injured reserve, signings, waivers).
            TR.weekly(league, league.injuries, league.recovering, 5 + w, f"Week {w}", rng,
                      records=S.records(league) if w >= 3 else None)
            league.week += 1
            FA.sync(league, f"Week {w}")             # the game's money_week
            FA.final_compliance(league)
            FA.sync(league, f"Week {w}")
            T.step(league)
            _audit(league, audit)
        if exploits and i in (0, seasons - 1):
            league.week = 5
            exploit.append(dict(_exploits(league, random.Random(f"x-{seed}-{i}")), when="in-season"))
            league.week = 19
        z = _strength(league)
        parity.append(st.pstdev(z.values()))
        lines, share = _season_lines(league, rng)
        league.injuries = {}
        # ---- the offseason (the game's own; its steps fire the trade steps) ----
        serious = {}
        evaluation.record_tape(league, share, league.season)
        league.team_history.extend({k: v for k, v in r.items() if k != "conf"} for r in lines)
        TR.end_of_season(league)
        for p in league.players:
            if p.id in league.rosters:
                p.experience += 1
        league.season += 1
        league.schedule = []
        offseason.offseason_start(league, lines, random.Random(rng.random()))
        while league.offseason["phase"] != "done":
            offseason.offseason_next(league, random.Random(rng.random()))
            _audit(league, audit)
            st_ = league.offseason
            if exploits and i in (0, seasons - 1) and st_["phase"] == "fa" and st_.get("wave") == 1:
                exploit.append(dict(_exploits(league, random.Random(f"xo-{seed}-{i}")), when="league year"))
        development.training_camp(league, share, serious, rng=random.Random(rng.random()))
        for t in league.teams:
            league.auto_depth_chart(t.id)
        league.offseason = None
        # ---- camp and the preseason (no games), cut-down day ----
        league.stage = "preseason"
        for pw in range(1, 6):
            league.pre_week = pw
            if pw == 5:
                TR.final_cuts(league, {}, {}, 5, random.Random(rng.random()))
                from engine import free_agency as FA
                FA.sync(league, "Final cuts")
                FA.final_compliance(league)
                FA.sync(league, "Final cuts")
            T.step(league)
            _audit(league, audit)
    log = []
    cap_of = {s: C.cap_for(league, s) for s in range(first, league.season + 2)}
    for e in league.trades["log"]:
        players = []
        for side in ("a", "b"):
            for pid in e["gave"][side]["players"]:
                inf = e["info"][str(pid)]
                p = league.player(pid)
                players.append({"side": side, "pos": inf["pos"], "age": inf["age"], "cap": inf["cap"],
                                "rnd": p.draft_round, "dy": p.draft_year, "exp": inf["exp"]})
        picks = {side: [T.parse_key(k) for k in e["gave"][side]["picks"]] for side in ("a", "b")}
        year = max([i for i, s0 in enumerate(starts) if e["step"] > s0] or [0])
        log.append({"season": e["season"], "phase": e["phase"], "step": e["step"], "teams": e["teams"],
                    "when": e["when"], "players": players, "picks": picks, "year": year})
    roster_share = Counter(GRP[league.player(pid).position] for pid in league.rosters)
    audit["trades_illegal"] = len(bad)
    return {"seed": seed, "first": first, "seasons": seasons, "log": log, "audit": audit, "parity": parity,
            "draft_trades": draft_trades,
            "exploit": exploit, "roster_share": dict(roster_share), "secs": time.time() - t0,
            "teams": [t.id for t in league.teams]}


def jj_mid(rnd):
    from engine.draft import jj_value
    return jj_value((rnd - 1) * 32 + 16)


def report(results, label=""):
    out = []
    say = out.append
    n_years = sum(r["seasons"] for r in results)
    deals = [e for r in results for e in r["log"]]
    real_ph = REAL["player_deals_by_phase_2021_25"]
    real_ph = {k: v for k, v in real_ph.items()}
    real_ph["1 league year to draft"] = round(real_ph["1 league year to draft"] + real_ph.pop("6 after deadline", 0), 1)
    say(f"PLAYER TRADES vs the real NFL {label}")
    say(f"{len(results)} leagues x {results[0]['seasons']} league years (made-up results; the game's own offseason)."
        f" Real: nflverse trades, 2021-25 unless noted (2013-25 in brackets where given).")
    say("")
    with_players = [e for e in deals if e["players"]]
    say(f"Trades with players a league year: {len(with_players) / n_years:.1f}   real 2021-25 "
        f"{st.mean(REAL['deals_with_players_by_year'][str(y)] for y in range(2021, 2026)):.1f} "
        f"(range 41-67) [2013-25 {REAL['deals_per_year']['with players']}]")
    by = Counter(PHASE_GROUP.get(e["phase"], "?") for e in with_players)
    say("By phase (a league year):")
    for k in sorted(set(real_ph) | set(by)):
        say(f"  {k:28} {by.get(k, 0) / n_years:5.1f}   real {real_ph.get(k, 0):5.1f}")
    say("  (real 'league year to draft' includes deals agreed after the deadline and made official when the "
        "league year opens)")
    # Draft-day pick deals (the draft room) that include a next-year pick (real 2013-25: 23%)
    dd = [t for r in results for t in r.get("draft_trades", [])]
    if dd:
        fut = sum(1 for t in dd if t.get("gave_future") or t.get("got_future"))
        say(f"Draft-day pick deals (the draft room): {len(dd) / n_years:.1f} a draft (real ~30), with a next-year "
            f"pick {fut / len(dd):.0%} (real 23%)")
    wk = Counter()
    for e in with_players:
        if e["phase"] in ("season", "deadline"):
            played = int(e["when"].split()[-1]) - 1 if e["when"].startswith("Week") else 9
            wk[9 - played] += 1
    real_wk = REAL["player_deals_by_weeks_before_deadline"]["2021_25"]
    say("In-season by weeks before the deadline (0 = deadline week):  sim | real")
    say("  " + "  ".join(f"{w}: {wk.get(w, 0) / n_years:.1f}|{real_wk[str(w)]}" for w in range(0, 9)))
    per_team = []
    for r in results:
        cnt = Counter()
        for e in r["log"]:
            if e["players"]:
                for t in e["teams"]:
                    cnt[(t, e["year"])] += 1
        for y in range(r["seasons"]):
            for t in r["teams"]:
                per_team.append(cnt.get((t, y), 0))
    rp = REAL["player_deals_per_team_year"]
    say(f"Deals with players per team a year: mean {st.mean(per_team):.2f} (real {rp['mean']}), sd "
        f"{st.pstdev(per_team):.2f} ({rp['sd']}), teams with none {sum(1 for x in per_team if x == 0) / len(per_team):.0%} "
        f"({rp['share_zero']:.0%}), most {max(per_team)} ({rp['max']})  [real: 2013-25]")
    kinds = Counter()
    for e in deals:
        sides = {s for s in ("a", "b") if any(p["side"] == s for p in e["players"])}
        pk = any(e["picks"][s] for s in ("a", "b"))
        kinds["players both ways (+ picks)" if len(sides) == 2 else "players for picks" if sides and pk else
              "player for nothing" if sides else "picks only"] += 1
    say("What's in them (a year):  " + ", ".join(f"{k} {v / n_years:.1f}" for k, v in sorted(kinds.items()))
        + "   real [2013-25]: " + ", ".join(f"{k} {v}" for k, v in REAL["deal_kinds_per_year"].items()
                                           if k != "picks only") + " (picks-only deals are the draft room's)")
    players = [p for e in deals for p in e["players"]]
    say(f"Players traded a year: {len(players) / n_years:.1f}   real [2013-25] {REAL['players_traded_per_year']}; "
        f"players per deal with players {len(players) / max(1, len(with_players)):.2f} (real {REAL['players_per_deal']})")
    pos = Counter(GRP[p["pos"]] for p in players)
    rs = Counter()
    for r in results:
        for k, v in r["roster_share"].items():
            rs[k] += v
    tot_r = sum(rs.values())
    say("Who's traded, by position: share of players traded (share of roster spots) | real [2013-25]:")
    say("  " + "  ".join(f"{g} {pos.get(g, 0) / max(1, len(players)):.0%} ({rs.get(g, 0) / tot_r:.0%}) | "
                         f"{REAL['position_share_of_players_traded'].get(g, 0):.0%}"
                         for g in ("QB", "RB", "WR", "TE", "OL", "EDGE", "DL", "LB", "DB", "K/P/LS")))
    ages = [p["age"] for p in players]
    ra = REAL["age_traded"]
    if ages:
        say(f"Age when traded: mean {st.mean(ages):.1f} (real {ra['mean']}), median {st.median(ages)} ({ra['median']}); "
            f"by age sim|real: " + " ".join(
                f"{a}:{sum(1 for x in ages if min(33, max(22, x)) == a) / len(ages):.0%}|{ra['share_by_age'][str(a)]:.0%}"
                for a in range(22, 34)))
    caps = sorted(p["cap"] for p in players)
    rc = REAL["contract_share_of_cap"]
    if caps:
        say(f"Contract size (share of the cap a year): median {st.median(caps):.1%} (real {rc['median']:.1%}), "
            f"75th {caps[int(.75 * len(caps))]:.1%} ({rc['p75']:.1%}), 90th {caps[int(.9 * len(caps))]:.1%} "
            f"({rc['p90']:.1%}), under 1% {sum(1 for c in caps if c < 0.01) / len(caps):.0%} ({rc['share_under_1pct']:.0%})")
    stars = sum(1 for p in players if p["cap"] >= 0.08)
    firsts = sum(1 for e in deals for p in e["players"] if p["rnd"] == 1 and e["season"] - p["dy"] <= 4)
    say(f"Stars (deals of 8%+ of the cap) a year: {stars / n_years:.1f} (real {REAL['stars_traded_per_year']['contract_8pct_plus']},"
        f" range 1-10); first-rounders in their first 4 seasons {firsts / n_years:.1f} "
        f"(real {REAL['stars_traded_per_year']['recent_first_rounders_(<=4_seasons)']})")
    # Returns for one player traded for picks only
    def band(c):
        return "under 2%" if c < 0.02 else "2-5%" if c < 0.05 else "5-10%" if c < 0.10 else "10%+"
    ret = defaultdict(list)
    for e in deals:
        if len(e["players"]) != 1:
            continue
        p = e["players"][0]
        other = "b" if p["side"] == "a" else "a"
        back = e["picks"][other]
        sent = e["picks"][p["side"]]
        if not back:
            continue
        val = sum(jj_mid(r) for _s, r, _o in back) - sum(jj_mid(r) for _s, r, _o in sent)
        ret[band(p["cap"])].append((min(r for _s, r, _o in back), val))
    say("What comes back for one player traded for picks (best pick's round; chart value of the picks at the middle of"
        " each round):  sim | real [2013-25]")
    for b in ("under 2%", "2-5%", "5-10%", "10%+"):
        rows = ret.get(b, [])
        rr = REAL["returns_player_for_picks"].get(b) or {}
        if rows:
            vals = sorted(v for _r, v in rows)
            rounds = Counter(r for r, _v in rows)
            say(f"  {b:8} n {len(rows) / n_years:4.1f}/yr  rounds " + " ".join(
                f"{k}:{rounds.get(k, 0) / len(rows):.0%}" for k in range(1, 8))
                + f"  value median {vals[len(vals) // 2]:.0f} (25th {vals[len(vals) // 4]:.0f}, 75th "
                  f"{vals[3 * len(vals) // 4]:.0f})")
        if rr:
            n = rr["n"]
            say(f"  {'':8} real {n / 13:4.1f}/yr  rounds " + " ".join(
                f"{k}:{rr['best_round'].get(str(k), 0) / n:.0%}" for k in range(1, 8))
                + f"  value median {rr['chart_median']:.0f} (25th {rr['chart_p25']}, 75th {rr['chart_p75']})")
    yrs = Counter()
    for e in deals:
        for s in ("a", "b"):
            for season, _r, _o in e["picks"][s]:
                after_draft = e["phase"] not in ("league_year", "fa_early", "pre_draft")
                yrs[season - e["season"] - (1 if after_draft else 0)] += 1
    tot = sum(yrs.values()) or 1
    ry = REAL["future_pick_years_out"]
    rtot = sum(v for k, v in ry.items() if int(k) >= 0)
    say("Picks traded, by drafts away (0 = the next draft):  " + "  ".join(
        f"{k}: {yrs.get(k, 0) / tot:.0%} (real {ry.get(str(k), 0) / rtot:.0%})" for k in range(0, 3)))
    a = defaultdict(int)
    where = Counter()
    for r in results:
        for k, v in r["audit"].items():
            if k == "where":
                where.update(v)
            elif k == "where_roster":
                where.update({"roster " + kk: vv for kk, vv in v.items()})
            else:
                a[k] += v
    say(f"Legality: trades that left a team over the cap or its roster limit: {a['trades_illegal']} (of "
        f"{len(deals)}). Outside the regular season, team-steps over the cap: {a['cap_over']}; over the roster limit: "
        f"{a['roster_over']} ({a['checks']} steps checked)" + (f"; where: {dict(where)}" if where else ""))
    par = [x for r in results for x in r["parity"]]
    say(f"Team strength spread (starters, z) by season: {st.mean(par):.3f}")
    say(f"({sum(r['secs'] for r in results):.0f} s of work)")
    # Exploit checks
    ex = [x for r in results for x in r["exploit"]]
    if ex:
        say("")
        say("EXPLOIT CHECKS (your team = the first team; at the start and end of each league)")
        say("1. What an AI team asks for one of its 5 best players at each position (chart points; and per 1% of"
            " the cap his market price is):")
        line = []
        for pos in ("QB", "RB", "WR", "TE", "T", "G", "DE", "DT", "OLB", "CB", "S"):
            rows = [v for x in ex for v in x.get(f"ask_{pos}", [])]
            if rows:
                asks = sorted(a for a, _p in rows)
                per = sorted(a / max(0.5, p * 100) for a, p in rows)
                line.append(f"{pos} {asks[len(asks) // 2]:.0f} ({per[len(per) // 2]:.0f}/1%)")
        say("   " + "  ".join(line))
        q = Counter(k for x in ex for k in x.get("qty_for_quality", []))
        qt = [v for x in ex for v in x.get("qty_true", [])]
        say(f"2. Three of your average starters for one of their 12 most valuable players: " +
            ", ".join(f"{k} {v}" for k, v in q.most_common())
            + (f"; the accepted ones, judged with true ratings: good for the AI team in {sum(1 for v in qt if v > 0)} of "
               f"{len(qt)} (median {st.median(qt):+.0f} points)" if qt else ""))
        d = Counter(k for x in ex for k in x.get("dump", []))
        dt = [v for x in ex for v in x.get("dump_true", [])]
        say(f"3. Your worst contracts (3%+ of the cap) for a 7th-round pick: " + ", ".join(f"{k} {v}" for k, v in d.most_common())
            + (f"; the accepted ones with true ratings: good for the AI team in {sum(1 for v in dt if v > 0)} of {len(dt)} "
               f"(median {st.median(dt):+.0f} points)" if dt else ""))
        f = [x2 for x in ex for x2 in x.get("flip", [])]
        if f:
            gains = sorted(g for g, _a in f)
            say(f"4. Buy from one AI team at its ask, sell to the keenest other: profitable {sum(1 for g in gains if g > 0) / len(gains):.0%}"
                f" of {len(gains)}; median {gains[len(gains) // 2]:.0f}, 90th {gains[int(.9 * len(gains))]:.0f} chart points"
                f" (median ask {st.median(a for _g, a in f):.0f})")
        lb = [x2 for x in ex for x2 in x.get("lowball", [])]
        say("5. A 7th for their best player, six calls in a row: " + " | ".join(", ".join(k) for k in lb[:4]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102,103,104")
    ap.add_argument("--seasons", type=int, default=4)
    ap.add_argument("--calls", type=float, default=None, help="CALLS_K for this run")
    ap.add_argument("--no-exploits", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "tools" / "trade_report.txt"))
    a = ap.parse_args()
    seeds = [int(s) for s in a.leagues.split(",")]
    t0 = time.time()
    with Pool(min(len(seeds), 6)) as pool:
        results = pool.map(_worker, [(s, a.seasons, a.calls, not a.no_exploits) for s in seeds])
    text = report(results, f"(CALLS_K {a.calls})" if a.calls is not None else "")
    text += f"\n({time.time() - t0:.0f} s)"
    print(text)
    Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
