# tools/gm_check.py
# General managers and front-office habits vs the real NFL (Oct 22; engine/gm.py).
#
# Runs generated leagues through many offseasons with the game's own offseason
# (coaching carousel, GM changes, the new league year, free agency, the draft,
# cuts) and made-up seasons (tools/draft_lab.py: records from team strength, no
# games), then measures what docs/research/gm_research.py measured for the real
# NFL (docs/research/real_gm.json):
#   - turnover: GM changes a year (and the spread), head coach changes, both in
#     the same offseason, a new GM replacing the coach he inherited, GM tenure,
#     retreads, the odds of a GM change by record and tenure;
#   - habits, and whether they stay with the team or go with the GM: draft-day
#     trades (net trade-downs), free agency spending on other teams' players,
#     own players' share of the money (re-signings and extensions), dead money,
#     cap room left at the season's end; each three ways (the team's odd vs even
#     years; the same GM's odd vs even years; the same team before and after a
#     GM change), plus restructures.
# Without GMs (an older engine) the head coach stands in for the GM.
#
#   python tools/gm_check.py                         (leagues 101,102,104,105,106,107; 16 seasons)
#   python tools/gm_check.py --leagues 101,102 --seasons 10
# Writes tools/gm_report.txt. Nothing is saved; your saves are never touched.

import argparse
import json
import math
import pickle
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

REAL = json.loads((ROOT / "docs" / "research" / "real_gm.json").read_text())
SKIP = 2            # the first offseasons still carry the new league's made-up contracts


def _worker(args):
    seed, seasons = args
    import ast, os
    from engine import free_agency as FA, gm as G
    # Experiments: FA_KNOBS="NAME=value;..." sets free_agency.py (or gm.py: "gm.NAME=value") knobs in every worker.
    for kv in filter(None, os.environ.get("FA_KNOBS", "").split(";")):
        k, v = kv.split("=", 1)
        mod, k = (G, k[3:]) if k.strip().startswith("gm.") else (FA, k)
        setattr(mod, k.strip(), ast.literal_eval(v.strip()))
    from tools import draft_lab
    from engine import contracts as C, draft_day as DD
    from engine.league import create_league
    random.seed(f"lab-{seed}")
    league = create_league(seed=seed, camp=False)
    league.settings["salt"] = f"lab{seed}"
    rng = random.Random(f"lab-run-{seed}")
    rooms = []
    plain_finish, plain_restr = DD.finish, C.restructure
    restr = defaultdict(int)

    def finish(lg, *a, **k):
        room = plain_finish(lg, *a, **k)
        rooms.append({"season": room.season, "trades": list(room.trades)})
        return room

    def restructure(lg, pid, amount=None):
        c = lg.contracts.get(pid)
        saved = plain_restr(lg, pid, amount)
        if c is not None and saved:
            restr[(c["team"], lg.season)] += saved / C.cap_for(lg, lg.season)
        return saved
    DD.finish, C.restructure = finish, restructure
    hc, gm, wins, playoff, room_end = {}, {}, {}, set(), {}
    gm_info, hc_q = {}, {}
    over = []
    from engine import staff as SF

    def note_people():
        S = league.season
        st_ = getattr(league, "staff", None) or {}
        for t in league.teams:
            jobs = st_.get("jobs", {}).get(str(t.id), {})
            hc[(t.id, S)] = jobs.get("HC")
            c = SF.coach(league, jobs.get("HC")) if st_ else None
            if c:
                hc_q[(t.id, S)] = (SF._true_score(c, "HC"), SF.reputation_score(c, "HC"))
            g = (st_.get("gm") or {}).get("jobs", {}).get(str(t.id))
            gm[(t.id, S)] = g
            if g is not None:
                p = st_["gm"]["people"][str(g)]
                gm_info[g] = {"name": p["name"], "interim": p.get("interim", False), "judge": p.get("judge")}
    first = league.season
    try:
        note_people()
        for i in range(seasons):
            S = league.season
            lines, share = draft_lab.fake_season(league, rng)
            for r in lines:
                g = r["w"] + r["l"] + r["t"]
                wins[(r["team"], S)] = (r["w"] + 0.5 * r["t"]) * 17 / max(1, g)
            seeded = sorted(lines, key=lambda r: -(r["w"] + 0.5 * r["t"]))[:14]
            playoff.update((r["team"], S) for r in seeded)
            draft_lab.next_season(league, lines, share, rng)
            note_people()
            for t in league.teams:
                room_end[(t.id, league.season)] = C.cap_room(league, t.id) / C.cap_for(league, league.season)
            over.append(len(C.audit(league, top51=False)))
    finally:
        DD.finish, C.restructure = plain_finish, plain_restr
    cap = {s: C.cap_for(league, s) for s in range(first, league.season + 1)}
    dead = {(tid, s): v / cap[s] for tid, d in league.cap_charges.items() for s, v in d.items() if s in cap}
    log = [{k: e.get(k) for k in ("season", "team", "new_team", "apy_share", "kind", "phase")}
           for e in league.contract_log]
    gmst = (getattr(league, "staff", None) or {}).get("gm") or {}
    gm_log = list(gmst.get("log", []))
    people = {int(k): {"name": v["name"], "judge": v.get("judge"), "style": v.get("style"), "exp": v.get("exp")}
              for k, v in (gmst.get("people") or {}).items()}
    hc_hired = {}
    for e in (getattr(league, "staff", None) or {}).get("log", []):
        if e["job"] == "HC" and e["move"] == "hired":
            hc_hired[(e["team"], e["season"])] = e["cid"]
    return {"seed": seed, "first": first, "last": league.season,
            "teams": [t.id for t in league.teams], "hc": hc, "gm": gm, "wins": wins, "playoff": playoff,
            "rooms": rooms, "restr": dict(restr), "dead": dead, "room_end": room_end, "log": log,
            "gm_log": gm_log, "people": people, "gm_info": gm_info, "hc_q": hc_q,
            "over": over}


def corr(a, b):
    if len(a) < 3:
        return float("nan")
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def habit(val, years, teams, boss):
    """The research script's three persistence measures (boss[(team, year)] = the
    person in charge that year)."""
    out = {}
    o = [st.mean(val.get((t, y), 0) for y in years if y % 2) for t in teams]
    e = [st.mean(val.get((t, y), 0) for y in years if not y % 2) for t in teams]
    out["team_odd_even_corr"] = corr(o, e)
    out["team_mean_sd"] = st.pstdev([st.mean(val.get((t, y), 0) for y in years) for t in teams])
    yrs = defaultdict(list)
    for t in teams:
        for y in years:
            if (t, y) in val:
                yrs[(t, boss.get((t, y)))].append((y, val[(t, y)]))
    a, b = [], []
    for k, lst in yrs.items():
        if len(lst) >= 4 and any(y % 2 for y, _ in lst) and any(not y % 2 for y, _ in lst):
            a.append(st.mean(v for y, v in lst if y % 2))
            b.append(st.mean(v for y, v in lst if not y % 2))
    out["same_gm_odd_even_corr"] = corr(a, b)
    a, b = [], []
    for t in teams:
        seq = []
        for y in years:
            k = (t, boss.get((t, y)))
            if not seq or seq[-1] != k:
                seq.append(k)
        blocks = [k for k in seq if len(yrs[k]) >= 3]
        for k1, k2 in zip(blocks, blocks[1:]):
            a.append(st.mean(v for _, v in yrs[k1]))
            b.append(st.mean(v for _, v in yrs[k2]))
    out["same_team_next_gm_corr"] = corr(a, b)
    out["n_pairs"] = len(a)
    # the same GM at two teams (his years at each, 2+ each)
    by_gm = defaultdict(dict)
    for (t, g), lst in yrs.items():
        if g is not None and len(lst) >= 2:
            by_gm[g][t] = st.mean(v for _, v in lst)
    a = [list(d.values())[0] for d in by_gm.values() if len(d) >= 2]
    b = [list(d.values())[1] for d in by_gm.values() if len(d) >= 2]
    out["same_gm_two_teams_corr"] = corr(a, b)
    out["n_movers"] = len(a)
    s1, s2, d1, d2 = [], [], [], []
    for t in teams:
        for y in years:
            if y - 1 in years and (t, y) in val and (t, y - 1) in val:
                same = boss.get((t, y)) == boss.get((t, y - 1))
                (s1 if same else d1).append(val[(t, y - 1)])
                (s2 if same else d2).append(val[(t, y)])
    out["next_year_corr_same_gm"] = corr(s1, s2)
    out["next_year_corr_new_gm"] = corr(d1, d2)
    return out


def measure(r):
    teams = r["teams"]
    first, last = r["first"], r["last"]
    has_gm = any(v is not None for v in r["gm"].values())
    boss = r["gm"] if has_gm else r["hc"]
    m = {"has_gm": has_gm}
    # ---- turnover (offseasons first+1 .. last) ----
    gch, hch, both, g_with_h, h_with_g = [], [], 0, [0, 0], [0, 0]
    odds = defaultdict(lambda: [0, 0])
    for y in range(first + 1, last + 1):
        g = h = 0
        for t in teams:
            gc = has_gm and r["gm"].get((t, y)) != r["gm"].get((t, y - 1))
            hc_ = r["hc"].get((t, y)) != r["hc"].get((t, y - 1))
            g += gc
            h += hc_
            both += gc and hc_
            g_with_h[0] += gc and hc_
            g_with_h[1] += gc
            h_with_g[0] += gc and hc_
            h_with_g[1] += hc_
            if has_gm:
                w = r["wins"].get((t, y - 1), 8.5)
                wb = "0-4" if w < 4.5 else "5-6" if w < 6.5 else "7-8" if w < 8.5 else "9-10" if w < 10.5 else "11+"
                odds[wb][0] += gc
                odds[wb][1] += 1
                k = "playoffs" if (t, y - 1) in r["playoff"] else "no playoffs"
                odds[k][0] += gc
                odds[k][1] += 1
        gch.append(g)
        hch.append(h)
    n = len(gch)
    m["gm_changes"] = gch
    m["hc_changes"] = hch
    m["both_per_year"] = both / n
    m["gm_with_hc"] = g_with_h[0] / max(1, g_with_h[1])
    m["hc_with_gm"] = h_with_g[0] / max(1, h_with_g[1])
    m["odds"] = {k: v for k, v in odds.items()}
    # a new GM who kept the coach: replaced within 2 seasons?
    keep = [0, 0]
    for t in teams:
        for y in range(first + 1, last - 1):
            if has_gm and r["gm"].get((t, y)) != r["gm"].get((t, y - 1)) and r["hc"].get((t, y)) == r["hc"].get((t, y - 1)):
                keep[1] += 1
                keep[0] += (r["hc"].get((t, y + 1)) != r["hc"].get((t, y))
                            or r["hc"].get((t, y + 2)) != r["hc"].get((t, y + 1)))
    m["kept_then_replaced"] = keep
    # tenures (completed inside the run, started after the first season)
    lens, starts = [], []
    for t in teams:
        cur, since = None, None
        for y in range(first, last + 1):
            g = r["gm"].get((t, y)) if has_gm else r["hc"].get((t, y))
            if g != cur:
                if cur is not None and since > first:
                    lens.append(y - since)
                cur, since = g, y
                if y > first:
                    starts.append(g)
    m["tenures"] = lens
    if has_gm:
        seen_before = defaultdict(set)
        retread = 0
        for t in teams:
            for y in range(first, last + 1):
                g = r["gm"].get((t, y))
                if y > first and g != r["gm"].get((t, y - 1)) and g is not None:
                    retread += any(g in seen_before[o] for o in teams if o != t)
                seen_before[t].add(g)
        m["retread"] = retread / max(1, len(starts))
    # ---- habits ----
    years = range(first + SKIP, last)
    net = defaultdict(float)
    for d in r["rooms"]:
        for tr in d["trades"]:
            net[(tr["up"], d["season"])] -= 1
            net[(tr["down"], d["season"])] += 1
    for t in teams:
        for y in years:
            net.setdefault((t, y), 0.0)
    m["trade"] = habit(net, years, teams, boss)
    m["trades_per_draft"] = sum(len(d["trades"]) for d in r["rooms"]) / max(1, len(r["rooms"]))
    outside, own = defaultdict(float), defaultdict(float)
    for e in r["log"]:
        if e["apy_share"] is None or e["apy_share"] < 0.01 or e["kind"] in ("rookie", "practice", "udfa", "futures"):
            continue
        if e["phase"] and "rookie" in str(e["phase"]):
            continue
        k = (e["team"], e["season"])
        if e["new_team"]:
            outside[k] += e["apy_share"]
        else:
            own[k] += e["apy_share"]
    for t in teams:
        for y in years:
            outside.setdefault((t, y), 0.0)
            own.setdefault((t, y), 0.0)
    share = {k: own[k] / (own[k] + outside[k]) if own[k] + outside[k] else 0.5 for k in own}
    m["fa"] = habit(outside, years, teams, boss)
    m["fa"]["mean"] = st.mean(outside[(t, y)] for t in teams for y in years)
    m["fa"]["sd_team_year"] = st.pstdev([outside[(t, y)] for t in teams for y in years])
    m["own"] = habit(own, years, teams, boss)
    m["resign"] = habit(share, years, teams, boss)
    m["resign"]["mean"] = st.mean(share[(t, y)] for t in teams for y in years)
    dead = {k: v for k, v in r["dead"].items() if k[1] in years}
    for t in teams:
        for y in years:
            dead.setdefault((t, y), 0.0)
    m["dead"] = habit(dead, years, teams, boss)
    m["dead"]["mean"] = st.mean(dead[(t, y)] for t in teams for y in years)
    m["dead"]["sd_team_year"] = st.pstdev([dead[(t, y)] for t in teams for y in years])
    room = {k: v for k, v in r["room_end"].items() if k[1] in years}
    m["room"] = habit(room, years, teams, boss)
    m["room"]["mean"] = st.mean(room.values())
    # the GM's eye for coaches: new head coaches' true quality minus reputation, by his judge
    jx, jy = [], []
    for t in teams:
        for y in range(first + 1, last + 1):
            if r["hc"].get((t, y)) != r["hc"].get((t, y - 1)) and (t, y) in r.get("hc_q", {}):
                g = r["gm"].get((t, y))
                jd = (r["gm_info"].get(g) or {}).get("judge")
                if jd is not None:
                    tq, rq = r["hc_q"][(t, y)]
                    jx.append(jd)
                    jy.append(tq - rq)
    m["judge_corr"] = corr(jx, jy) if len(jx) > 5 else float("nan")
    m["judge_n"] = len(jx)
    rs = {(t, y): r["restr"].get((t, y), 0.0) for t in teams for y in years}
    m["restr"] = habit(rs, years, teams, boss)
    vals = list(rs.values())
    m["restr"]["any"] = sum(v > 0.001 for v in vals) / len(vals)
    m["restr"]["over_3_6"] = sum(v > 6.5 / 182.5 for v in vals) / len(vals)
    m["restr"]["over_8_2"] = sum(v > 15 / 182.5 for v in vals) / len(vals)
    return m


def report(results, out):
    ms = [measure(r) for r in results]
    w = out.append
    has_gm = all(m["has_gm"] for m in ms)
    T = REAL["turnover"]

    def avg(key, sub=None):
        vals = [(m[key] if sub is None else m[key][sub]) for m in ms]
        vals = [v for v in vals if v == v]
        return st.mean(vals) if vals else float("nan")
    w(f"GM check: {len(results)} leagues x {results[0]['last'] - results[0]['first']} seasons "
      f"({'with GMs' if has_gm else 'NO GMs: the head coach stands in for the GM'})  (sim | real)")
    w("")
    w("1. TURNOVER")
    g = [x for m in ms for x in m["gm_changes"]]
    h = [x for m in ms for x in m["hc_changes"]]
    sd_g = st.mean(st.stdev(m["gm_changes"]) for m in ms) if has_gm else float("nan")
    w(f"   GM changes a year {st.mean(g):.2f} | {T['gm_changes_per_year']}, spread {sd_g:.2f} | {T['gm_changes_sd']}, "
      f"fewest-most {min(g)}-{max(g)} | {T['gm_changes_min_max'][0]}-{T['gm_changes_min_max'][1]}")
    w(f"   head coach changes a year {st.mean(h):.2f} | {T['hc_changes_per_year']} (1999-2025: 6.6), spread "
      f"{st.mean(st.stdev(m['hc_changes']) for m in ms):.2f} | {T['hc_changes_sd']}")
    if has_gm:
        w(f"   both in the same offseason a year {avg('both_per_year'):.2f} | {T['both_same_offseason_per_year']}; "
          f"GM changes that come with a new head coach {avg('gm_with_hc') * 100:.0f}% | {T['share_of_gm_changes_with_new_hc'] * 100:.0f}%; "
          f"head coach changes that come with a new GM {avg('hc_with_gm') * 100:.0f}% | {T['share_of_hc_changes_with_new_gm'] * 100:.0f}%")
        k = [sum(m["kept_then_replaced"][0] for m in ms), sum(m["kept_then_replaced"][1] for m in ms)]
        w(f"   a new GM who kept the head coach replaced him within 2 seasons {100 * k[0] / max(1, k[1]):.0f}% (n {k[1]}) | "
          f"{T['new_gm_kept_coach_then_replaced_within_2_seasons'] * 100:.0f}% (n {T['n_kept']})")
        lens = [x for m in ms for x in m["tenures"]]
        if lens:
            w(f"   GM tenure (completed, in seasons) mean {st.mean(lens):.1f} | {T['tenure_mean']}, median {st.median(lens):.0f} | "
              f"{T['tenure_median']}; 1 season {100 * sum(x == 1 for x in lens) / len(lens):.0f}% | {T['tenure_share']['1'] * 100:.0f}%, "
              f"5+ {100 * sum(x >= 5 for x in lens) / len(lens):.0f}% | {(T['tenure_share']['5-9'] + T['tenure_share']['10+']) * 100:.0f}% "
              f"(the run's length cuts off the longest)")
        w(f"   new GMs who were a GM before (another team): {avg('retread') * 100:.0f}% | {T['retread_share_of_new_gms'] * 100:.0f}%")
        odds = defaultdict(lambda: [0, 0])
        for m in ms:
            for kk, (a, b) in m["odds"].items():
                odds[kk][0] += a
                odds[kk][1] += b
        real_odds = REAL["gm_change_odds"]
        w("   chance of a GM change by last season's wins (per 17): " + "  ".join(
            f"{kk} {100 * odds[kk][0] / max(1, odds[kk][1]):.0f}% | {real_odds[kk + ' | all'][0] * 100:.0f}%"
            for kk in ("0-4", "5-6", "7-8", "9-10", "11+", "playoffs", "no playoffs")))
    w("")
    w("2. HABITS: STAY WITH THE TEAM, OR GO WITH THE GM? (correlations; 'same GM' = his own odd vs even years,")
    w("   'next GM' = the same team's GM before vs after a change, 'next year' = one season to the next)")
    for key, rk, label in (("trade", "trade_habit", "draft-day trades (net trade-downs per draft)"),
                           ("fa", "fa_spending", "free agency: other teams' players (market deals, share of the cap)"),
                           ("own", "own_spending", "own players' market money (re-signs, extensions, share of the cap)"),
                           ("resign", "resign_share", "own players' share of the market money (re-signs, extensions)"),
                           ("dead", "dead_money", "dead money (share of the cap)"),
                           ("room", "cap_left", "cap room left at the season's end"),
                           ("restr", None, "restructures (cap room made, share of the cap)")):
        rv = REAL.get(rk, {}) if rk else {}

        def f(x):
            return "  -  " if x is None or x != x else f"{x:+.2f}"
        w(f"   {label}")
        w(f"     team odd/even {f(avg(key, 'team_odd_even_corr'))} | {f(rv.get('team_odd_even_corr'))}"
          f"   same GM {f(avg(key, 'same_gm_odd_even_corr'))} | {f(rv.get('same_gm_odd_even_corr'))}"
          f"   next GM {f(avg(key, 'same_team_next_gm_corr'))} | {f(rv.get('same_team_next_gm_corr'))}"
          f"   next year same GM {f(avg(key, 'next_year_corr_same_gm'))} | {f(rv.get('next_year_corr_same_gm'))}"
          f", new GM {f(avg(key, 'next_year_corr_new_gm'))} | {f(rv.get('next_year_corr_new_gm'))}"
          + (f"   his next team {f(avg(key, 'same_gm_two_teams_corr'))} (n {sum(m[key].get('n_movers', 0) for m in ms)})"
             f" | {f(rv.get('same_gm_two_teams_corr'))} (n {len(rv.get('movers', []))})" if has_gm else ""))
        if key == "fa":
            w(f"     average {avg('fa', 'mean') * 100:.1f}% | {rv['mean_pct_of_cap']}% of the cap a team a year, spread "
              f"team-year {avg('fa', 'sd_team_year') * 100:.1f}% | {rv['team_year_sd_pct']}%, teams' averages "
              f"{avg('fa', 'team_mean_sd') * 100:.1f}% | {rv['team_mean_sd_pct']}%")
        if key == "resign":
            w(f"     average {avg('resign', 'mean'):.2f} | {rv['mean']}, teams' averages spread {avg('resign', 'team_mean_sd'):.3f} | "
              f"{rv['team_mean_sd']}")
        if key == "dead":
            w(f"     average {avg('dead', 'mean') * 100:.1f}% | {rv['mean'] * 100:.1f}% (real 2013-25 incl. void years; "
              f"2016-20 ~8%), spread team-year {avg('dead', 'sd_team_year') * 100:.1f}% | {rv['sd_team_year'] * 100:.1f}%, "
              f"teams' averages {avg('dead', 'team_mean_sd') * 100:.1f}% | {rv['team_mean_sd'] * 100:.1f}%")
        if key == "room":
            w(f"     average {avg('room', 'mean') * 100:.1f}% | {rv['mean'] * 100:.1f}%")
        if key == "restr":
            ro = REAL["restructures_otc_2021"]
            w(f"     teams restructuring at all in a year {avg('restr', 'any') * 100:.0f}% | {ro['share_teams_any_restructure_a_year'] * 100:.0f}%"
              f" (2013-20; ~73% 2020-21), more than 3.6% of the cap {avg('restr', 'over_3_6') * 100:.0f}% | "
              f"{ro['share_major_over_6_5M'] * 100:.0f}%, more than 8.2% {avg('restr', 'over_8_2') * 100:.0f}% | {ro['share_15M_plus'] * 100:.0f}%")
    w(f"   draft-day trades a draft {st.mean(m['trades_per_draft'] for m in ms):.1f} | 21.1 (pick-for-pick)")
    w(f"   cap legality: teams over the cap (everyone counting) after the cut to 53: "
      f"{sum(sum(r.get('over', [])) for r in results)} in {sum(len(r.get('over', [])) for r in results)} league-seasons (must be 0)")
    if has_gm:
        w(f"   GMs' eye for coaches: new head coaches' true quality minus reputation vs the hiring GM's hidden skill, "
          f"correlation {avg('judge_corr'):+.2f} (n {sum(m['judge_n'] for m in ms)}; no real measure: PROVISIONAL)")
    w("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102,104,105,106,107")
    ap.add_argument("--seasons", type=int, default=16)
    ap.add_argument("--out", default=str(ROOT / "tools" / "gm_report.txt"))
    ap.add_argument("--save", help="also keep the raw results in this file (pickle)")
    ap.add_argument("--load", help="report on raw results saved earlier with --save (no new run)")
    a = ap.parse_args()
    t0 = time.time()
    if a.load:
        results = pickle.load(open(a.load, "rb"))
    else:
        seeds = [int(x) for x in a.leagues.split(",")]
        with Pool(min(len(seeds), 6)) as pool:
            results = pool.map(_worker, [(s, a.seasons) for s in seeds])
        if a.save:
            pickle.dump(results, open(a.save, "wb"))
    out = []
    report(results, out)
    out.append(f"({time.time() - t0:.0f} s)")
    text = "\n".join(out)
    print(text)
    Path(a.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
