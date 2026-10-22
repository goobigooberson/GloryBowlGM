# tools/free_agency_check.py
# Contracts, the salary cap and free agency vs the real NFL.
#
# Builds generated leagues (engine.league.create_league), gives them contracts
# (free_agency.initial_contracts), then runs offseasons in the real order:
#   season ends -> retirements -> new league year (cap, re-signings, tags,
#   extensions, cap cuts) -> free agency (4 waves) -> draft + rookie deals ->
#   undrafted -> free agency (3 more waves) -> cut to 53 -> practice squads ->
#   training camp (development)
# and prints the sim next to the real numbers for every benchmark:
#   where players go (same team / new team / out of the league), the deals
#   signed (minimum share, one-year share, market deals by position, lengths,
#   guarantees, ages), the pay ladder by position, team payrolls, positional
#   spending, rookie scale, tags/extensions, and cap legality.
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
from engine.league import create_league               # noqa: E402

RESEARCH = ROOT / "docs" / "research"
REAL_C = json.loads((RESEARCH / "real_contracts.json").read_text())
REAL_M = json.loads((RESEARCH / "real_movement.json").read_text())
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
# One offseason, in the real order
# ---------------------------------------------------------------------------

def offseason(lg, rng, stats, lines):
    S0 = lg.season
    before = {pid: tid for pid, tid in lg.rosters.items()}
    for pid, r in lg.reserve.items():
        before[pid] = r["team"]
    exp_before = {pid: lg.player(pid).experience for pid in before}
    TR.end_of_season(lg)
    for p in lg.players:
        if p.id in lg.rosters:
            p.experience += 1
    lg.season += 1
    lg.stage, lg.week, lg.pre_week = "preseason", 1, 1
    S = lg.season
    # Retirements (their contracts end; bonus money stays on the cap).
    retired = set(OS.retirements(lg, rng))
    for pid in retired:
        C.retire(lg, pid)
        OS.retire(lg, pid)
    order = OS.draft_order(lg, lines)
    FA.ensure(lg)
    rep = FA.league_year_start(lg, rng, draft_order=order)
    stats["legal"].append(("league year", [t for t, _ in C.audit(lg)]))
    sign1 = FA.market(lg, FA.PRE_DRAFT_WAVES, rng)
    stats["legal"].append(("pre-draft FA", [t for t, _ in C.audit(lg)]))
    from engine import draft as D       # the real draft (Step 8; the placeholder in offseason.py is gone)
    rookies = D.make_class(lg, rng)
    lg.players.extend(rookies)
    picks, undrafted = D.run_draft(lg, rookies, order, rng)
    FA.sign_draft_picks(lg, picks)
    udfa, _unsigned = D.sign_undrafted(lg, undrafted, rng)
    FA.sign_undrafted(lg, udfa)
    stats["legal"].append(("draft", [t for t, _ in C.audit(lg)]))
    sign2 = FA.market(lg, FA.POST_DRAFT_WAVES, rng)
    lt = FA.tagged_long_term(lg, rng)
    cuts = FA.cut_down(lg)
    OS.fill_short_positions(lg, rng)
    FA.sync(lg, "cut-down")
    released = defaultdict(list)
    for pid, tid in cuts:
        released[tid].append(lg.player(pid))
    TR.form_practice_squads(lg, {}, {}, released, rng)
    FA.sync(lg, "practice squads")
    FA.final_compliance(lg)
    FA.sync(lg, "final cuts")
    OS.trim_free_agents(lg, rng)
    for p in rookies:
        p.__dict__.pop("_board", None)
        p.__dict__.pop("_grade", None)
    OS.update_depth_charts(lg, None)
    lg.draft_history.extend(picks)
    development.training_camp(lg, None, None)
    for t in lg.teams:
        lg.auto_depth_chart(t.id)
    # Week 1: everyone counts against the cap now.
    lg.stage, lg.week = "regular_season", 1
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
        stats["year"][k] += v
    stats["year"]["fa_signed_pre"] += len(sign1)
    stats["year"]["fa_signed_post"] += len(sign2)
    stats["year"]["tag_long_term"] += lt
    stats["year"]["cut_down"] += len(cuts)
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
             "dead": [], "seasons": 0, "gone_why": defaultdict(Counter)}
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
    top_signings(last)
    say(f"\n({time.time() - t0:.0f} s)")
    (ROOT / "tools" / "free_agency_report.txt").write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
