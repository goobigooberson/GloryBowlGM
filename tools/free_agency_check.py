# tools/free_agency_check.py
# Contracts, the salary cap and free agency vs the real NFL.
#
# Builds generated leagues (engine.league.create_league), gives them contracts
# (free_agency.initial_contracts), then runs the game's own offseasons
#   (offseason.py, phase by phase as the Next button plays them: retirements,
#   coaching and GM changes, the new league year with re-signings, tags,
#   extensions and cap cuts, free agency's 4 waves, the draft and undrafted
#   signings, 3 more waves, trades, camp), training camp (development) and
#   the cut from 90 to 53 after the preseason (transactions.final_cuts)
# and prints the sim next to the real numbers for every benchmark:
#   where players go (same team / new team / out of the league), the deals
#   signed (minimum share, one-year share, market deals by position, lengths,
#   guarantees, ages), the pay ladder by position, team payrolls, positional
#   spending, rookie scale, tags/extensions, and cap legality; and the "fair
#   price" check: do good players sign far below their worth while teams still
#   have room (FOF8's cheap-star exploit; real yardstick from
#   docs/research/fair_price.py)?
# Seasons between offseasons are not played (fast): records are made up from
# team strength. --games plays one real season per league first (slow) to
# count in-season signings too.
#
#   python tools/free_agency_check.py                 (leagues 101,102; 3 offseasons each)
#   python tools/free_agency_check.py --leagues 101,102,103 --seasons 4
#   python tools/free_agency_check.py --games
# Writes tools/free_agency_report.txt. Nothing is saved; your saves are never touched.

import argparse
import copy
import json
import random
import statistics as st
import sys
import time
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import contracts as C                     # noqa: E402
from engine import cap_market as M                    # noqa: E402
from engine import free_agency as FA                  # noqa: E402
from engine import offseason as OS                    # noqa: E402
from engine import transactions as TR                 # noqa: E402
from engine import development                        # noqa: E402
from engine import depth as DEPTH                     # noqa: E402
from engine.league import create_league               # noqa: E402

RESEARCH = ROOT / "docs" / "research"
REAL_C = json.loads((RESEARCH / "real_contracts.json").read_text())
REAL_M = json.loads((RESEARCH / "real_movement.json").read_text())
REAL_FP = json.loads((RESEARCH / "real_fair_price.json").read_text())
# Big deals (5%+ of the cap), 2019-22: 321 deals by length (real_contracts_summary.md)
REAL_BIG_YEARS = {1: 61, 2: 32, 3: 86, 4: 90, 5: 46, 6: 6}
# Franchise tags per year (real 2019-24, public tag trackers): about 6-14, usually ~7-9.
REAL_TAGS = (6, 14)
GROUP_MOVE = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
              "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB", "K": "K", "P": "P", "LS": "LS"}
LADDER_GROUP = {"QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "T": "T", "G": "G", "C": "C",
                "DE": "EDGE", "DT": "DT", "OLB": "LB", "ILB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P",
                "LS": "LS"}
EXP_GROUPS = (("0-2", 0, 2), ("3-4", 3, 4), ("5-7", 5, 7), ("8+", 8, 99))
# Cap room when free agency opened, March 2, 2024 (OverTheCap via CBS Sports; $255.4M cap; $M).
# Teams over the cap had to get under it by the start of the league year (March 13), so they
# count as 0 here. 2025 (CBS, March 5; tiers only): 5 teams over, 6 at $0-20M, 5 at $20-40M,
# 9 at $40-60M, 6 at $60-100M, New England $127M ($279.2M cap): a median of about 14%.
REAL_FA_OPEN_2024 = [101.8, 91.5, 78.7, 75.7, 70.1, 69.7, 56.8, 52.5, 48.6, 42.0, 41.9, 40.9, 37.6, 37.6, 35.0,
                     34.8, 32.6, 29.2, 20.7, 13.6, 12.5, 12.2, 8.0, 6.8, 3.5, 0, 0, 0, 0, 0, 0, 0]
REAL_CAP_2024 = 255.4
# Cap room just after each new league year opened, after the first day or two of signings
# (OverTheCap's "Cap Space" via the Internet Archive: March 19, 2021, March 17, 2022, March 17,
# 2023, March 14, 2024, March 13, 2025; $M). The game's match is right after free agency's
# first wave. The target is the average without 2021 (the COVID year, when the cap fell).
REAL_FA_DAY1_TARGET_YEARS = (2022, 2023, 2024, 2025)
REAL_FA_DAY1 = {
    2021: (182.5, [43.6, 37.6, 34.1, 32.4, 29.1, 28.0, 21.2, 15.7, 15.1, 14.1, 12.5, 12.5, 11.7, 10.7, 10.6, 9.0,
                   8.7, 7.1, 5.5, 4.0, 3.0, 2.7, 1.5, 1.3, 0.6, 0.4, -1.3, -2.3, -3.6, -7.6, -12.0, -18.7]),
    2022: (208.2, [44.3, 39.7, 37.3, 34.6, 32.1, 29.4, 26.6, 24.8, 22.7, 21.0, 19.8, 17.4, 16.3, 15.7, 14.0, 14.0,
                   13.3, 13.1, 13.0, 12.0, 12.0, 9.2, 8.3, 6.6, 0.9, 0.8, 0.7, -3.6, -8.2, -9.4, -9.6, -10.7]),
    2023: (224.8, [44.9, 33.6, 23.8, 23.2, 22.8, 22.7, 21.4, 21.3, 21.0, 20.3, 19.8, 19.3, 18.7, 17.5, 17.4, 17.3,
                   15.5, 15.1, 14.7, 14.1, 12.3, 11.9, 10.6, 9.3, 8.5, 8.4, 7.9, 5.8, 5.3, 3.3, -1.4, -2.5]),
    2024: (255.4, [72.1, 68.0, 57.2, 56.3, 45.7, 40.6, 40.0, 34.2, 31.9, 29.2, 26.8, 26.0, 21.0, 18.9, 17.8, 17.3,
                   15.3, 15.1, 12.9, 11.9, 10.8, 9.8, 4.7, 3.6, 3.4, 3.0, 2.2, 1.2, 1.1, -1.8, -2.2, -7.8]),
    2025: (279.2, [100.9, 83.0, 70.2, 66.1, 60.8, 55.3, 53.6, 48.2, 47.5, 47.3, 46.4, 43.7, 35.1, 34.5, 33.8, 32.8,
                   32.2, 32.1, 28.4, 27.5, 26.1, 23.9, 22.6, 16.5, 13.8, 11.8, 9.9, 6.9, 6.3, 6.2, 0.8, -10.3]),
}

out_lines = []


def say(s=""):
    print(s)
    out_lines.append(s)


def pct(x):
    return f"{100 * x:5.1f}%"


# ---------------------------------------------------------------------------
# A fast season: made-up records from team strength
# ---------------------------------------------------------------------------

def fake_season_lines(lg, rng):
    strength = {}
    for t in lg.teams:
        players = lg.team_players(t.id)
        strength[t.id] = sum(sorted((p.overall() for p in players), reverse=True)[:24]) / 24
    mu = st.mean(strength.values())
    sd = st.pstdev(strength.values()) or 1
    lines = []
    for t in lg.teams:
        p = max(0.05, min(0.95, 0.5 + 0.12 * (strength[t.id] - mu) / sd + rng.gauss(0, 0.13)))
        w = sum(rng.random() < p for _ in range(17))
        lines.append({"team": t.id, "season": lg.season, "w": w, "l": 17 - w, "t": 0, "pf": 0, "pa": 0,
                      "div_rank": 1, "seed": None, "result": "Missed the playoffs"})
    lines.sort(key=lambda r: -r["w"])
    for i, r in enumerate(lines[:14]):
        r["result"] = "Won the Glory Bowl" if i == 0 else "Lost in the Wild Card round"
    return lines


def play_real_season(lg, seed, counts):
    """One real season (tools/simlab.py: games, injuries, roster moves) with
    contracts kept in step every week; counts the in-season deals. The
    league's rosters and contracts are put back afterward."""
    sys.path.insert(0, str(ROOT / "tools"))
    import simlab
    saved = {k: copy.deepcopy(getattr(lg, k)) for k in ("contracts", "cap_charges", "contract_log", "fa")}
    n_log = len(lg.contract_log)
    orig = TR.weekly
    # Integration step 6 of docs/free-agency-design.md, emulated here: when a team picks a
    # free agent during the season it only looks at players it can afford.
    current = [None]
    wrapped = {}
    for name in ("fill_roster_spot", "_upgrade", "fill_practice_squad", "injury_cover", "practice_squad_week"):
        fn = getattr(TR, name)

        def make(fn):
            def w(league, injuries, recovering, tid, *a, **k):
                prev, current[0] = current[0], tid
                try:
                    return fn(league, injuries, recovering, tid, *a, **k)
                finally:
                    current[0] = prev
            return w
        wrapped[name] = fn
        setattr(TR, name, make(fn))
    orig_pool = TR.free_agent_pool

    def pool(league, injuries, position=None, ps_only=False):
        fas = orig_pool(league, injuries, position, ps_only)
        if current[0] is None or not getattr(league, "contracts", None) or C.pay_week(league) == 0:
            return fas
        return [p for p in fas if FA.affordable(league, current[0], p.id)]
    TR.free_agent_pool = pool

    orig_pre = TR.lab_preseason

    def preseason(league, report, rng):
        r = orig_pre(league, report, rng)
        league.stage = "preseason"
        FA.sync(league, "final cuts")
        FA.final_compliance(league)
        FA.sync(league, "final cuts")
        return r
    TR.lab_preseason = preseason
    wrapped["lab_preseason"] = orig_pre

    def weekly(league, injuries, recovering, cal, label, rng, *a, **k):
        league.stage, league.week = "regular_season", cal + 1     # this week's game is played and paid
        r = orig(league, injuries, recovering, cal, label, rng, *a, **k)
        league.stage, league.week = "regular_season", cal + 1
        FA.sync(league, label)
        FA.final_compliance(league)          # integration step 6: AI teams stay under the cap
        FA.sync(league, label)
        over =[(t, room) for t, room in C.audit(league) if t != league.user_team_id]
        counts["over_in_season"] += len(over)
        counts["over_amounts"] = counts.get("over_amounts", []) + [room for _t, room in over]
        return r
    TR.weekly = weekly
    try:
        lg.stage, lg.week = "preseason", 1
        simlab.play_season(lg, seed)
    finally:
        TR.weekly = orig
        TR.free_agent_pool = orig_pool
        for name, fn in wrapped.items():
            setattr(TR, name, fn)
    new = lg.contract_log[n_log:]
    for k, v in saved.items():
        setattr(lg, k, v)
    lg.stage, lg.week = "season_complete", 18
    return new


# ---------------------------------------------------------------------------
# Fair price: free agency wave by wave, with what each player was worth and
# what room every AI team had when the wave opened
# ---------------------------------------------------------------------------

FAIR_LINE = 0.6            # "far below his worth": under this share of his market value


def wave_context(lg, w):
    """What every free agent is worth and the room every AI team has, as wave w opens."""
    cap = C.cap_for(lg, lg.season)
    pre = w in FA.PRE_DRAFT_WAVES
    room = {tid: (C.cap_room(lg, tid) - FA._reserve_share(lg, tid, pre) * cap + FA._restructure_left(lg, tid)) / cap
            for tid in FA.ai_teams(lg)}
    return M.market_table(lg), room


def record_wave(lg, w, table, room, signed, stats, before, starters):
    """For each signing of the wave: the player's market price, his ask, whether
    he was a starter last season, and the room every other AI team had."""
    cap = C.cap_for(lg, lg.season)
    for s_ in signed:
        p = lg.player(s_["pid"])
        info = table[p.id]
        stats["fair"].append({
            "pid": p.id, "pos": p.position, "group": LADDER_GROUP[p.position], "age": FA._age(lg, p),
            "ovr": p.overall(), "wave": w, "share": s_["apy"] / cap, "price": info["price"],
            "ask": FA.ask_share(info, w), "good_rating": info["price"] >= M.MARKET_LINE and FA.starter_level(info),
            "starter": p.id in starters, "last_team": before.get(p.id), "team": s_["team"],
            "rooms": sorted(r for t, r in room.items() if t != s_["team"]),
            "name": f"{p.first_name} {p.last_name}", "season": lg.season, "league": lg.name})


def cut_to_53(lg, salt):
    """After the (skipped) preseason: the game's final cuts from 90 to 53, waiver
    claims, practice squads, everyone under the cap (transactions.final_cuts)."""
    lg.stage, lg.week, lg.pre_week = "preseason", 1, 5
    r = TR.final_cuts(lg, {}, {}, 5, random.Random(f"fa-check-cuts-{salt}-{lg.season}"))
    lg.stage, lg.week = "regular_season", 1
    return r


# ---------------------------------------------------------------------------
# One offseason: the game's own (offseason.py, phase by phase, as your Next
# button plays it), then training camp and the cut to 53 after the preseason
# ---------------------------------------------------------------------------

def offseason(lg, rng, stats, lines):
    S0 = lg.season
    before = {pid: tid for pid, tid in lg.rosters.items()}
    for pid, r in lg.reserve.items():
        before[pid] = r["team"]
    exp_before = {pid: lg.player(pid).experience for pid in before}
    starters = set()                 # last season's starters (the base packages of each depth chart)
    for t in lg.teams:
        starters |= DEPTH.starter_ids(lg.depth_charts.get(t.id, {}))
    TR.end_of_season(lg)
    for p in lg.players:
        if p.id in lg.rosters:
            p.experience += 1
    lg.season += 1
    S = lg.season
    # Retirements, the draft class, GM changes, the new league year (the game's own dice).
    OS.offseason_start(lg, lines)
    retired = {pid for pid, _t in lg.offseason_report["retired"]}
    rep = lg.offseason_report.get("free_agency") or {}
    stats["legal"].append(("league year", [t for t, _ in C.audit(lg)]))
    # Cap room the day free agency opens (after re-signings, tags, cap cuts; top 51 counts).
    cap = C.cap_for(lg, S)
    stats["fa_open"].append(sorted((C.cap_room(lg, t.id) / cap for t in lg.teams if t.id != lg.user_team_id),
                                   reverse=True))
    sign1, sign2 = [], []
    n_signed = 0
    long_term = []
    plain_long_term = FA.tagged_long_term

    def counted_long_term(*a, **k):
        n = plain_long_term(*a, **k)
        long_term.append(n)
        return n
    FA.tagged_long_term = counted_long_term
    try:
        while lg.offseason["phase"] != "done":
            phase = lg.offseason["phase"]
            if phase == "fa":
                w = lg.offseason["wave"]
                table, room = wave_context(lg, w)
                OS.offseason_next(lg)
                signed = lg.offseason_report["fa_signings"][n_signed:]
                n_signed += len(signed)
                record_wave(lg, w, table, room, signed, stats, before, starters)
                (sign1 if w in FA.PRE_DRAFT_WAVES else sign2).extend(signed)
                if w == FA.PRE_DRAFT_WAVES[0]:
                    # ...and right after the first wave (the real day-after snapshots include the first
                    # day's signings).
                    stats["fa_day1"].append(sorted((C.cap_room(lg, t.id) / cap for t in lg.teams
                                                    if t.id != lg.user_team_id), reverse=True))
                if w == FA.PRE_DRAFT_WAVES[-1]:
                    stats["legal"].append(("pre-draft FA", [t for t, _ in C.audit(lg)]))
            else:
                OS.offseason_next(lg)
                if phase in ("draft", "drafting") and lg.offseason["phase"] == "fa":
                    stats["legal"].append(("draft", [t for t, _ in C.audit(lg)]))
    finally:
        FA.tagged_long_term = plain_long_term
    # Training camp (development), then the preseason's cut to 53 (the preseason's games are skipped).
    development.training_camp(lg, None, None)
    for t in lg.teams:
        lg.auto_depth_chart(t.id)
    lg.offseason = None
    cuts = cut_to_53(lg, lg.settings.get("salt", ""))
    # Week 1: everyone counts against the cap now.
    over = [(t, room) for t, room in C.audit(lg, top51=False)]
    stats["legal"].append(("week 1", [t for t, _ in over]))
    stats["missing"] += len(C.missing_contracts(lg))
    # Where last season's players are now.
    for pid, tid in before.items():
        p = lg.player(pid)
        now = FA.on_team(lg, pid)
        where = "gone" if now is None else "same" if now == tid else "new"
        e = exp_before[pid]
        eg = next(g for g, lo, hi in EXP_GROUPS if lo <= e <= hi)
        stats["move_all"][where] += 1
        stats["move_exp"][eg][where] += 1
        stats["move_pos"][GROUP_MOVE[p.position]][where] += 1
        if where == "gone":
            why = ("retired" if pid in retired else "left (unsigned, gave up)" if p.retired is not None
                   else "unsigned free agent")
            stats["gone_why"][eg][why] += 1
            stats["gone_why"]["pos " + GROUP_MOVE[p.position]][why] += 1
    for k, v in rep.items():
        if isinstance(v, (int, float)):
            stats["year"][k] += v
    stats["year"]["fa_signed_pre"] += len(sign1)
    stats["year"]["fa_signed_post"] += len(sign2)
    stats["year"]["tag_long_term"] += sum(long_term)
    stats["year"]["cut_down"] += cuts.get("cuts", 0)
    stats["year"]["unsigned_fa_week1"] += len(lg.free_agents())
    for s in sign1 + sign2:
        stats["waves"][s["wave"]] += 1
        share = s["apy"] / C.cap_for(lg, S)
        if share >= M.MARKET_LINE:
            stats["waves_market"][s["wave"]] += 1
    stats["seasons"] += 1
    stats["deals"].extend(d for d in lg.contract_log if d["season"] == S)
    snapshot_contracts(lg, stats)
    lg.stage, lg.week = "season_complete", 18
    return S0


def snapshot_contracts(lg, stats):
    """Pay ladder, payrolls and positional spending at week 1."""
    S = lg.season
    by = defaultdict(list)
    spend = defaultdict(float)
    for pid, c in lg.contracts.items():
        if c["kind"] == "practice":
            continue
        p = lg.player(pid)
        by[LADDER_GROUP[p.position]].append(c.get("new_apy", c["apy"]) / C.cap_for(lg, c["signed"]))
        spend[LADDER_GROUP[p.position]] += C.cap_hit(lg, c, S)
    for g, v in by.items():
        v.sort(reverse=True)
        stats["ladder"][g].append(v)
    total = sum(spend.values())
    for g, v in spend.items():
        stats["spend"][g].append(v / total)
    cap = C.cap_for(lg, S)
    for t in lg.teams:
        tc = C.team_cap(lg, t.id, top51=False)
        stats["payroll"].append(tc["used"] / tc["cap"])
        stats["room"].append(tc["room"] / cap)
        stats["dead"].append(tc["dead"] / cap)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(stats, n_leagues, real_deals_in_season):
    S = stats["seasons"]
    say("=" * 100)
    say(f"FREE AGENCY CHECK: {n_leagues} league(s), {S} offseason(s) in all. Real numbers in brackets.")
    say("=" * 100)
    # Legality
    bad = [(where, t) for where, ts in stats["legal"] for t in ts]
    say(f"Cap legality: AI teams over the cap at any checkpoint: {len(bad)} (must be 0)"
        + (f"  {bad[:6]}" if bad else ""))
    say(f"Players on a team without a contract at week 1: {stats['missing']} (must be 0)")
    if stats.get("over_in_season") is not None:
        am = stats.get("over_amounts") or []
        say(f"In-season (with --games): AI team-weeks over the cap: {stats['over_in_season']}"
            + (f" (by {C.fmt_money(-max(am))} to {C.fmt_money(-min(am))})" if am else ""))
    say()
    # Movement
    say("WHERE LAST SEASON'S PLAYERS ARE IN WEEK 1 (same team / new team / no team)")
    real = REAL_M["offseason"]

    def row(label, c, r):
        n = sum(c.values()) or 1
        say(f"  {label:7} n/season {n / S:6.0f}   same {pct(c['same'] / n)} [{pct(r['same'])}]   "
            f"new {pct(c['new'] / n)} [{pct(r['new_team'])}]   gone {pct(c['gone'] / n)} [{pct(r['gone'])}]")
    row("all", stats["move_all"], real["all"])
    for g, _lo, _hi in EXP_GROUPS:
        row(g, stats["move_exp"][g], real["by_experience_end_of_season"][g])
    pos_real = real["by_position"]
    for g in ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K", "P", "LS"):
        if g in pos_real:
            row(g, stats["move_pos"][g], pos_real[g])
    say("  why 'gone' (per season): " + "; ".join(
        f"{g}: " + ", ".join(f"{k} {v / S:.0f}" for k, v in stats["gone_why"][g].most_common())
        for g, _lo, _hi in EXP_GROUPS))
    say("  by position: " + "; ".join(
        f"{g[4:]}: " + ", ".join(f"{k.split(' ')[0]} {v / S:.0f}" for k, v in c.most_common())
        for g, c in sorted(stats["gone_why"].items()) if g.startswith("pos ")))
    say()
    # Deals
    deals = [d for d in stats["deals"] if d["kind"] not in ("rookie", "udfa")]
    all_deals = deals + real_deals_in_season
    say("VETERAN DEALS SIGNED IN A LEAGUE YEAR (everything but rookie deals, incl. practice squad deals"
        + (", in-season signings from --games" if real_deals_in_season else "; offseason only") + ")")
    n = len(all_deals) or 1
    mins = sum(1 for d in all_deals if d["apy_share"] <= M.MINIMUM_LINE)
    one = sum(1 for d in all_deals if d["years"] == 1)
    real_total = sum(v["veteran_deals_per_season"] for v in REAL_C["positions"].values())
    say(f"  deals per season {n / S:6.0f} [{real_total:.0f}; real counts include in-season and futures deals]")
    say(f"  at about the minimum (<= 0.65% of the cap) {pct(mins / n)} [76-87% by position]")
    say(f"  one-year deals {pct(one / n)} [75-80%]")
    no_ps = [d for d in all_deals if d["kind"] != "practice"]
    if no_ps:
        say(f"  (without practice squad deals: minimum {pct(sum(1 for d in no_ps if d['apy_share'] <= M.MINIMUM_LINE) / len(no_ps))}, "
            f"one-year {pct(sum(1 for d in no_ps if d['years'] == 1) / len(no_ps))})")
    kinds = Counter(d["kind"] for d in all_deals)
    say("  by kind per season: " + ", ".join(f"{k} {v / S:.0f}" for k, v in kinds.most_common()))
    say()
    say("MARKET DEALS (1%+ of the cap) per season, by position: sim [real]; median share; years; guaranteed; age 26-27 share")
    mk = [d for d in deals if d["apy_share"] >= M.MARKET_LINE]
    by = defaultdict(list)
    for d in mk:
        by[LADDER_GROUP[d["pos"]]].append(d)
    tot_sim = tot_real = 0
    for g in ("QB", "WR", "EDGE", "DT", "CB", "T", "LB", "S", "G", "TE", "RB", "C", "K", "P", "FB", "LS"):
        r = REAL_C["positions"][g]["market_deals_1pct_plus"]
        ds = by[g]
        tot_sim += len(ds) / S
        tot_real += r.get("n_per_season", 0)
        if not ds:
            say(f"  {g:5} {0:5.1f} [{r.get('n_per_season', 0):5.1f}]")
            continue
        yrs = [d["years"] for d in ds]
        g_sh = [d["guaranteed"] / max(1, d["value"]) for d in ds]
        a2627 = sum(1 for d in ds if 26 <= d["age"] <= 27) / len(ds)
        say(f"  {g:5} {len(ds) / S:5.1f} [{r.get('n_per_season', 0):5.1f}]   median {pct(st.median(d['apy_share'] for d in ds))} "
            f"[{pct(r.get('cap_pct_p50') or 0)}]   years {st.mean(yrs):.2f} [{r.get('years_mean') or 0:.2f}]   "
            f"gtd {pct(st.median(g_sh))} [{pct(r.get('guaranteed_share_median') or 0)}]   "
            f"age 26-27 {pct(a2627)} [{pct((r.get('age_dist') or {}).get('26-27', 0))}]")
    say(f"  total {tot_sim:6.1f} [{tot_real:6.1f}]")
    yd = Counter(min(d["years"], 6) for d in mk)
    real_yd = defaultdict(float)
    real_n = 0
    for g, v in REAL_C["positions"].items():
        m = v["market_deals_1pct_plus"]
        for k, s_ in (m.get("years_dist") or {}).items():
            real_yd[int(k)] += s_ * m["n_per_season"]
        real_n += m.get("n_per_season", 0)
    say("  market deal lengths: " + "  ".join(f"{k}y {pct(yd[k] / max(1, len(mk)))} [{pct(real_yd[k] / real_n)}]"
                                                for k in range(1, 7)))
    big = [d for d in deals if d["apy_share"] >= 0.05]
    by_ = Counter(min(d["years"], 6) for d in big)
    rb = sum(REAL_BIG_YEARS.values())
    say(f"  big deals (5%+) per season {len(big) / S:.1f} [{rb / 4:.0f}]; lengths: "
        + "  ".join(f"{k}y {pct(by_[k] / max(1, len(big)))} [{pct(REAL_BIG_YEARS[k] / rb)}]" for k in range(1, 7)))
    ages = Counter()
    for d in mk:
        a = d["age"]
        ages["<=25" if a <= 25 else "26-27" if a <= 27 else "28-29" if a <= 29 else "30-31" if a <= 31 else "32+"] += 1
    real_age = defaultdict(float)
    for g, v in REAL_C["positions"].items():
        m = v["market_deals_1pct_plus"]
        for k, s_ in (m.get("age_dist") or {}).items():
            real_age[k] += s_ * m["n_per_season"]
    say("  market deals by age: " + "  ".join(f"{k} {pct(ages[k] / max(1, len(mk)))} [{pct(real_age[k] / real_n)}]"
                                              for k in ("<=25", "26-27", "28-29", "30-31", "32+")))
    new_team = [d for d in mk if d.get("new_team")]
    say(f"  market deals with a new team {pct(len(new_team) / max(1, len(mk)))} [~50-57%, OTC team field, rough]")
    say()
    # Ladder
    say("PAY LADDER AT WEEK 1: Nth best-paid at each position (average per year, share of the cap at signing)")
    ranks = (1, 3, 5, 10, 16, 24, 32, 48, 64, 96)
    say("  pos   " + "".join(f"{'#' + str(r):>13}" for r in ranks))
    for g in ("QB", "WR", "EDGE", "T", "DT", "CB", "LB", "S", "G", "RB", "TE", "C", "K", "P", "FB", "LS"):
        lists = stats["ladder"][g]
        real_l = REAL_C["positions"][g]["ladder_active_2022"]
        cells = []
        for r in ranks:
            vals = [v[r - 1] for v in lists if len(v) >= r]
            rv = real_l.get(str(r))
            if not vals and rv is None:
                cells.append(" " * 13)
                continue
            s = f"{100 * st.mean(vals):.1f}" if vals else "-"
            cells.append(f"{s:>6} [{100 * rv:.1f}]".rjust(13) if rv is not None else f"{s:>6}      ".rjust(13))
        say(f"  {g:5} " + "".join(cells))
    say()
    say("POSITIONAL SPENDING (share of all cap dollars on contracts, week 1)")
    real_sp = REAL_C["active_cap_share_by_position"]
    say("  " + "  ".join(f"{g} {100 * st.mean(stats['spend'][g]):.1f} [{100 * real_sp[g]:.1f}]"
                         for g in sorted(real_sp, key=lambda k: -real_sp[k]) if stats["spend"][g]))
    say()
    say("TEAM PAYROLLS AT WEEK 1 (everyone counts)")
    pr = sorted(stats["payroll"])
    rm = sorted(stats["room"])
    say(f"  cap used: average {pct(st.mean(pr))}, lowest {pct(pr[0])}, 10th pct {pct(pr[len(pr) // 10])}, "
        f"90th pct {pct(pr[9 * len(pr) // 10])}, highest {pct(pr[-1])}  [real teams spend close to the cap]")
    say(f"  cap room: median {pct(st.median(rm))} of the cap; dead money average {pct(st.mean(stats['dead']))} "
        f"[real 2023-25: roughly 5-10% of the cap a team]")
    say()
    say("CAP ROOM WHEN FREE AGENCY OPENS (share of the cap, AI teams; real March 2024 in brackets, teams over "
        "the cap counted as 0)")
    real = sorted((x / REAL_CAP_2024 for x in REAL_FA_OPEN_2024), reverse=True)
    for label, rank in (("most room", 0), ("2nd", 1), ("5th", 4), ("8th", 7), ("median", None), ("24th", 23)):
        vals = [(st.median(v) if rank is None else v[rank]) for v in stats["fa_open"] if len(v) > (rank or 0)]
        rv = st.median(real) if rank is None else real[rank]
        say(f"  {label:10} {pct(st.mean(vals))}  [{pct(rv)}]")
    low = [sum(1 for x in v if x < 0.02) for v in stats["fa_open"]]
    say(f"  teams with under 2% of the cap: {st.mean(low):.1f} a year  [7-8 of 32 in 2024 and 2025]")
    say()
    years = sorted(REAL_FA_DAY1)
    say("CAP ROOM AFTER FREE AGENCY'S FIRST WAVE (share of the cap, AI teams; real just after the league year "
        f"opened: target = {REAL_FA_DAY1_TARGET_YEARS[0]}-{REAL_FA_DAY1_TARGET_YEARS[-1]} average, then "
        f"{' | '.join(str(y) for y in years)})")
    reals = {y: sorted((x / c for x in v), reverse=True) for y, (c, v) in REAL_FA_DAY1.items()}
    for label, rank in (("most room", 0), ("2nd", 1), ("5th", 4), ("8th", 7), ("median", None), ("24th", 23)):
        vals = [(st.median(v) if rank is None else v[rank]) for v in stats["fa_day1"] if len(v) > (rank or 0)]
        rv = {y: (st.median(r) if rank is None else r[rank]) for y, r in reals.items()}
        target = st.mean(rv[y] for y in REAL_FA_DAY1_TARGET_YEARS)
        say(f"  {label:10} {pct(st.mean(vals))}  [target {pct(target)}; {' | '.join(pct(rv[y]) for y in years)}]")
    low = [sum(1 for x in v if x < 0.02) for v in stats["fa_day1"]]
    lows = {y: sum(1 for x in r if x < 0.02) for y, r in reals.items()}
    say(f"  teams with under 2% of the cap: {st.mean(low):.1f} a year  "
        f"[target {st.mean(lows[y] for y in REAL_FA_DAY1_TARGET_YEARS):.1f}; {' | '.join(str(lows[y]) for y in years)}]")
    say()
    say("ROOKIE SCALE (average per year, share of the cap) by round: sim [real median 2017-22]")
    rk = defaultdict(list)
    for d in stats["deals"]:
        if d["kind"] == "rookie" and d.get("pick"):
            rk[(d["pick"] - 1) // 32 + 1].append(d["apy_share"])
    real_rk = REAL_C["rookie_scale_by_round"]
    say("  " + "  ".join(f"R{r} {100 * st.median(rk[r]):.2f}% [{100 * real_rk[str(r)]['median']:.2f}%]"
                         for r in range(1, 8) if rk[r]))
    say()
    y = stats["year"]
    say("THE LEAGUE YEAR, per season")
    say(f"  re-signed before free agency {y['resigned'] / S:.0f}, ERFA kept {y['erfa'] / S:.0f}, RFA tenders "
        f"{y['rfa_tenders'] / S:.0f}, let go {y['let_go'] / S:.0f}, reserve/future deals {y['futures'] / S:.0f}")
    say(f"  extensions {y['extensions'] / S:.0f}, fifth-year options exercised {y['options'] / S:.0f}, "
        f"franchise tags {y['tags'] / S:.1f} [{REAL_TAGS[0]}-{REAL_TAGS[1]}], tagged players signed long-term "
        f"{y['tag_long_term'] / S:.1f}, cap cuts {y['cap_cuts'] / S:.0f}")
    say(f"  free agent signings before the draft {y['fa_signed_pre'] / S:.0f}, after {y['fa_signed_post'] / S:.0f};"
        f" by wave: " + ", ".join(f"{w}: {stats['waves'][w] / S:.0f} ({stats['waves_market'][w] / S:.0f} market)"
                                   for w in sorted(stats['waves'])))
    say(f"  cut at the cut-down {y['cut_down'] / S:.0f}; free agents left unsigned at week 1 {y['unsigned_fa_week1'] / S:.0f}")
    say()


def fair_price_report(stats):
    """FOF8's cheap-star exploit: good players signing far below their worth
    while teams still have room. Two views: the same yardstick as the real NFL
    (last season's starters, 30 or younger, signing with a new team, against
    what real good free agents at the position signed for), and the game's own
    (good ratings too, against his market price)."""
    S = stats["seasons"]
    rf = REAL_FP
    real_val = rf["market_value"]
    say("FAIR PRICE: DO GOOD FREE AGENTS SIGN FAR BELOW THEIR WORTH? (FOF8's cheap-star exploit)")
    say(f"  A. Same yardstick as the real NFL: last season's starter (game: base-package starter on his depth chart; "
        f"real: {int(100 * rf['starter_snaps'])}%+ of snaps in the games he played), {rf['max_age']} or younger, "
        f"signed with a new team in free agency (offseason waves). Market value = what real good free agents at his "
        f"position signed for (median, share of the cap; real {rf['source'].split(';')[0]}).")
    a = [d for d in stats["fair"] if d["starter"] and d["age"] <= rf["max_age"] and d["last_team"] is not None
         and d["team"] != d["last_team"] and d["group"] in real_val]
    ra = rf["all"]
    if not a:
        say("     (no such signings)")
    else:
        for d in a:
            d["ratio_real"] = d["share"] / real_val[d["group"]]
        n = len(a)
        say(f"     per season {n / S:5.1f} [{ra['n_per_season']:.1f}]   median deal {pct(st.median(d['share'] for d in a))} "
            f"of the cap [{pct(ra['median_cap_pct'])}]")
        say(f"     under 60% of market value {pct(sum(d['ratio_real'] < 0.6 for d in a) / n)} [{pct(ra['under_60'])}]   "
            f"under 40% {pct(sum(d['ratio_real'] < 0.4 for d in a) / n)} [{pct(ra['under_40'])}]   "
            f"at about the minimum (<= 0.65%) {pct(sum(d['share'] <= M.MINIMUM_LINE for d in a) / n)} "
            f"[{pct(ra['minimum_level'])}]")
        gm = defaultdict(list)
        for d in a:
            gm[d["group"]].append(d["share"])
        say("     median deal by position, game [real]: " + "  ".join(
            f"{g} {100 * st.median(v):.1f} [{100 * real_val[g]:.1f}]"
            for g, v in sorted(gm.items(), key=lambda kv: -len(kv[1]))))
        by_w = Counter(d["wave"] for d in a)
        cheap_w = Counter(d["wave"] for d in a if d["ratio_real"] < FAIR_LINE)
        say("     by wave (signed / under 60%): " + ", ".join(f"{w}: {by_w[w]} / {cheap_w[w]}" for w in sorted(by_w)))
    # B. The game's own view: good ratings too, against the game's own price for him.
    say("  B. The game's own view: good ratings too (rated as a starter league-wide, priced 1%+ of the cap), "
        f"{rf['max_age']} or younger, any team, against his market price the day the wave opened. Real reference: A.")
    b = [d for d in stats["fair"] if d["good_rating"] and d["age"] <= rf["max_age"]]
    if not b:
        say("     (no such signings)")
        say()
        return
    for d in b:
        d["ratio"] = d["share"] / d["price"]
    cheap = [d for d in b if d["ratio"] < FAIR_LINE]
    n = len(b)
    say(f"     per season {n / S:5.1f}; median deal {pct(st.median(d['ratio'] for d in b))} of his price; "
        f"under 60% of his price {pct(len(cheap) / n)} ({len(cheap) / S:.1f} a season); under 40% "
        f"{pct(sum(d['ratio'] < 0.4 for d in b) / n)}; last season's starters among them "
        f"{pct(sum(d['starter'] for d in b) / n)}")
    by_w = Counter(d["wave"] for d in b)
    cheap_w = Counter(d["wave"] for d in cheap)
    say("     by wave (signed / under 60%): " + ", ".join(f"{w}: {by_w[w]} / {cheap_w[w]}" for w in sorted(by_w)))
    tiers = (("1-2% of the cap", 0.0, 0.02), ("2-5%", 0.02, 0.05), ("5%+ (stars)", 0.05, 9.0))
    say("     by his price: " + "   ".join(
        f"{label}: {len(t) / S:.1f} a season, under 60% {pct(sum(d['ratio'] < FAIR_LINE for d in t) / max(1, len(t)))}"
        for label, lo, hi in tiers for t in [[d for d in b if lo <= d["price"] < hi]]))
    if cheap:
        able = [sum(r >= d["price"] for r in d["rooms"]) for d in cheap]
        med = [st.median(d["rooms"]) for d in cheap if d["rooms"]]
        say(f"     when one of them signed under 60%: other AI teams with spendable room for his full price "
            f"{st.mean(able):.1f} on average (median {st.median(able)}); their median spendable room "
            f"{pct(st.mean(med))} of the cap")
        say("     cheapest (age, rating, price -> deal, wave, other teams with room for his price):")
        for d in sorted(cheap, key=lambda d: d["ratio"])[:8]:
            say(f"       {d['league']} {d['season']} {d['pos']:3} {d['name']}, {d['age']}, ovr {d['ovr']}: price "
                f"{pct(d['price'])} -> {pct(d['share'])} ({100 * d['ratio']:.0f}%), wave {d['wave']}, "
                f"{sum(r >= d['price'] for r in d['rooms'])} teams had room"
                f"{'; starter last season' if d['starter'] else ''}")
    say()


def top_signings(lg, n=12):
    S = lg.season
    ds = sorted((d for d in lg.contract_log if d["season"] == S and d["kind"] not in ("rookie", "practice")),
                key=lambda d: -d["apy"])[:n]
    say(f"Biggest deals of the {S} league year in league {lg.name or ''}:")
    for d in ds:
        p = lg.player(d["pid"])
        team = lg.team(d["team"]).abbrev
        say(f"  {team} {d['pos']:3} {p.first_name} {p.last_name}, {d['age']}, ovr {p.overall()}: {d['kind']} "
            f"{d['years']}y {C.fmt_money(d['value'])} ({C.fmt_money(d['apy'])}/yr, {pct(d['apy_share'])} of cap), "
            f"{C.fmt_money(d['guaranteed'])} gtd{'  (new team)' if d['new_team'] else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--games", action="store_true", help="play one real season per league first (slow)")
    args = ap.parse_args()
    t0 = time.time()
    stats = {"legal": [], "missing": 0, "move_all": Counter(), "move_exp": defaultdict(Counter),
             "move_pos": defaultdict(Counter), "year": Counter(), "waves": Counter(), "waves_market": Counter(),
             "deals": [], "ladder": defaultdict(list), "spend": defaultdict(list), "payroll": [], "room": [],
             "dead": [], "seasons": 0, "gone_why": defaultdict(Counter), "fa_open": [], "fa_day1": [], "fair": []}
    in_season = []
    day1 = {"ladder": defaultdict(list), "spend": defaultdict(list), "payroll": [], "room": [], "dead": []}
    seeds = [int(x) for x in args.leagues.split(",")]
    last = None
    for seed in seeds:
        lg = create_league(seed=seed)
        lg.name = f"league {seed}"
        lg.settings["salt"] = f"fa-check-{seed}"
        lg.user_team_id = None
        FA.initial_contracts(lg)
        cut_to_53(lg, f"fa-check-{seed}")       # a new league starts at camp: the cut to 53 first
        snapshot_contracts(lg, day1)
        rng = random.Random(f"fa-check-{seed}")
        if args.games:
            stats["over_in_season"] = stats.get("over_in_season", 0)
            new = play_real_season(lg, f"fa-check-{seed}", stats)
            in_season.extend(d for d in new if d["kind"] not in ("rookie", "udfa"))
        for k in range(args.seasons):
            lines = fake_season_lines(lg, rng)
            lg.team_history.extend(lines)
            offseason(lg, rng, stats, lines)
            print(f"  league {seed} offseason {k + 1} done ({time.time() - t0:.0f}s)")
        last = lg
    say(f"Day 1 (new leagues, before any offseason): cap used average {pct(st.mean(day1['payroll']))} "
        f"(lowest {pct(min(day1['payroll']))}, highest {pct(max(day1['payroll']))}), dead money {pct(st.mean(day1['dead']))}")
    say("  ladder #1/#5/#10/#32 QB " + " / ".join(
        f"{100 * st.mean(v[r - 1] for v in day1['ladder']['QB']):.1f}" for r in (1, 5, 10, 32))
        + "  WR " + " / ".join(f"{100 * st.mean(v[r - 1] for v in day1['ladder']['WR']):.1f}" for r in (1, 5, 10, 32)))
    if in_season:
        say(f"In-season deals (one real season per league): {len(in_season) / len(seeds):.0f} per season; "
            f"minimum {pct(sum(1 for d in in_season if d['apy_share'] <= M.MINIMUM_LINE) / len(in_season))}, "
            f"one-year {pct(sum(1 for d in in_season if d['years'] == 1) / len(in_season))}")
    say()
    report(stats, len(seeds), [d for d in in_season] if in_season else [])
    fair_price_report(stats)
    top_signings(last)
    say(f"\n({time.time() - t0:.0f} s)")
    (ROOT / "tools" / "free_agency_report.txt").write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
