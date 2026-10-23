# tools/draft_check.py
# Draft realism check (Step 8): makes draft classes, runs the AI draft year
# after year in several generated leagues (tools/draft_lab.py: the real
# offseason and development, games skipped), follows every pick's career,
# and prints the sim next to the real NFL for every draft benchmark in
# docs/research/real_draft_summary.md and real_draft_ai_summary.md.
#
#   python tools/draft_check.py                      (6 leagues x 22 seasons, ~3 minutes)
#   python tools/draft_check.py --leagues 101,102 --seasons 16
#
# Writes tools/draft_report.txt. How to read it: each line is "sim | real".
# Career measures use classes drafted after the first 3 seasons (the league
# is still settling from its made-up start) that have been followed for at
# least 8 seasons. "Starter" in the sim = on the depth chart as a starter at
# training camp and not out 9+ games; real = PFR's seasons as a starter for
# career rates, 50%+ of his team's snaps for the year-by-year rates.
# Nothing is saved or changed.

import argparse
import json
import math
import statistics as st
import sys
import time
from collections import defaultdict, Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import draft_outcomes as DO     # noqa: E402

RESEARCH = ROOT / "docs" / "research"
GROUPS = ["QB", "RB", "WR", "TE", "OL", "DE", "DT", "LB", "DB", "K/P"]
MIN_SEASONS = 8
SKIP_FIRST = 3


def _worker(args):
    seed, seasons = args
    from tools import draft_lab
    from engine import draft, scale
    r = draft_lab.run(seed, seasons, quiet=True)
    league = r["league"]
    info = {}
    drafted = {pk["pid"] for pk in r["picks"]}
    for p in league.players:
        if p.id in drafted:
            info[p.id] = {"pos": p.position, "combine": dict(p.combine), "wt": p.weight, "ht": p.height,
                          "birth": p.birth_date.isoformat(), "draft_year": p.draft_year}
    shown = {}
    for s, snap in r["seasons"].items():
        vals = [scale.shown(v[2], league.player(pid).position) for pid, v in snap.items()]
        st_vals = [v[2] for pid, v in snap.items() if v[1]]
        by_pos = defaultdict(list)
        for pid, v in snap.items():
            if v[1]:
                by_pos[league.player(pid).position].append(v[2])
        shown[s] = {"80+": sum(x >= 80 for x in vals), "90+": sum(x >= 90 for x in vals),
                    "median": st.median(vals), "starter_avg": sum(st_vals) / max(1, len(st_vals)),
                    "pos": {k: st.mean(v) for k, v in by_pos.items()}}
    skills = {int(k): v for k, v in league.settings.get("draft_skill", {}).items()}
    posall = {p.id: p.position for p in league.players}
    return {"seed": seed, "picks": r["picks"], "seasons": r["seasons"], "drafts": r["drafts"], "info": info, "posall": posall,
            "shown": shown, "skills": skills}


class _L:
    """Stand-in for a league in draft_outcomes (needs player(pid).position)."""
    def __init__(self, posall):
        self.posall = posall

    def player(self, pid):
        class P:
            pass
        p = P()
        p.id = pid
        p.position = self.posall[pid]
        return p


def _runs_for_outcomes(results):
    return [{"picks": r["picks"], "seasons": r["seasons"], "league": _L(r["posall"])} for r in results]


def fmt(x, pct=True):
    if x is None:
        return "  -  "
    return f"{100 * x:4.0f}%" if pct else f"{x:5.2f}"


def report(results, out):
    real = json.load(open(RESEARCH / "real_draft.json"))
    real_ai = json.load(open(RESEARCH / "real_draft_ai.json"))
    w = out.append
    runs = _runs_for_outcomes(results)
    cs = DO.careers(runs, min_seasons=MIN_SEASONS, skip_first=SKIP_FIRST)
    n_drafts = sum(len([d for d in r["drafts"]]) for r in results)
    w(f"Leagues: {', '.join(str(r['seed']) for r in results)}; drafts run: {n_drafts}; "
      f"careers followed (classes after year {SKIP_FIRST}, {MIN_SEASONS}+ seasons): {len(cs)}")
    w("")

    # 1. Pick bands
    w("1. WHAT A PICK SLOT GETS YOU (sim | real)")
    w(f"{'Picks':>8} {'n':>5}  {'Starter 3+':>13}  {'Starter 5+':>13}  {'Pro Bowl':>13}  {'Never started':>13}")
    res = DO.summarize(cs, "band")
    for a, b in DO.BANDS:
        k = f"{a}-{b}"
        rk = "221-256" if k == "221-262" else k
        rv = real["by_pick_band"].get(rk)
        v = res.get(k)
        if not v or not rv:
            continue
        w(f"{k:>8} {v['n']:5d}  {fmt(v['starter_3plus_seasons'])} | {fmt(rv['starter_3plus_seasons'])}"
          f"  {fmt(v['starter_5plus_seasons'])} | {fmt(rv['starter_5plus_seasons'])}"
          f"  {fmt(v['pro_bowl'])} | {fmt(rv['pro_bowl'])}  {fmt(v['never_started'])} | {fmt(rv['never_started'])}")
    pbs = [c["pro_bowls"] for c in cs if c["pro_bowls"] > 0]
    n_classes = sum(len({c["season"] for c in DO.careers([run], MIN_SEASONS, SKIP_FIRST)}) for run in runs)
    if pbs:
        w(f"   Pro Bowlers per class {len(pbs) / max(1, n_classes):.1f} | 30.6, selections each "
          f"{st.mean(pbs):.1f} | 3.0, only once {100 * sum(x == 1 for x in pbs) / len(pbs):.0f}% | 38%"
          f"  (careers followed {MIN_SEASONS}+ seasons, so a bit short of whole careers)")
    w("")
    w("   Starting in each of his first 4 seasons (sim | real, real = 50%+ of snaps)")
    for a, b in DO.BANDS:
        k = f"{a}-{b}"
        v = res.get(k)
        if not v:
            continue
        rv = DO.REAL_START_BY_YEAR[k]
        w(f"{k:>8}  " + "  ".join(f"yr{y + 1} {fmt(v['start_by_year'][y])} | {fmt(rv[y])}" for y in range(4)))
    w("")

    # 2. Rounds and position x round
    w("2. BY ROUND (sim | real)")
    res_r = DO.summarize(cs, "round")
    for rnd in range(1, 8):
        v, rv = res_r.get(rnd), real["by_round"][str(rnd)]
        if v:
            w(f"   R{rnd}: starter 3+ {fmt(v['starter_3plus_seasons'])} | {fmt(rv['starter_3plus_seasons'])}"
              f"   Pro Bowl {fmt(v['pro_bowl'])} | {fmt(rv['pro_bowl'])}"
              f"   never started {fmt(v['never_started'])} | {fmt(rv['never_started'])}")
    w("")
    w("   By position and round: starter 3+ seasons / Pro Bowl, sim (n) | real")
    acc = defaultdict(list)
    for c in cs:
        acc[(c["group"], c["round"])].append(c)
    for g in GROUPS:
        cells = []
        for rnd in range(1, 8):
            group = acc.get((g, rnd), [])
            rv = real["by_position_round"].get(g, {}).get(str(rnd))
            if not group:
                cells.append(f"R{rnd} -")
                continue
            s3 = sum(sum(c["starts"]) >= 3 for c in group) / len(group)
            pb = sum(c["pro_bowls"] > 0 for c in group) / len(group)
            r3 = f"{100 * rv['starter_3plus_seasons']:.0f}/{100 * rv['pro_bowl']:.0f}" if rv else "-"
            cells.append(f"R{rnd} {100 * s3:.0f}/{100 * pb:.0f}({len(group)})|{r3}")
        w(f"   {g:>4}: " + "  ".join(cells))
    w("")

    # 3. Composition
    w("3. WHO GOES WHERE: picks per draft by position and round (sim | real scaled to 224 picks)")
    comp = defaultdict(lambda: defaultdict(int))
    first_pick = defaultdict(list)
    ages = defaultdict(list)
    n_d = 0
    for r in results:
        for d in r["drafts"]:
            n_d += 1
            seen = set()
            for pk in sorted(d["picks"], key=lambda x: x["pick"]):
                g = DO.GROUP[d["notes"][pk["pid"]]["pos"]]
                comp[g][pk["round"]] += 1
                if g not in seen:
                    first_pick[g].append(pk["pick"])
                    seen.add(g)
                ages[pk["round"]].append(d["notes"][pk["pid"]]["age"])
    scale_ = 224 / 257
    real_comp = real["picks_per_draft_by_position_round"]
    for g in GROUPS:
        rv = real_comp.get(g, {})
        cells = [f"R{rnd} {comp[g][rnd] / n_d:4.1f}|{rv.get(str(rnd), 0) * scale_:4.1f}" for rnd in range(1, 8)]
        tot = sum(comp[g].values()) / n_d
        w(f"   {g:>4}: " + " ".join(cells) + f"   total {tot:5.1f}|{rv.get('total', 0) * scale_:5.1f}")
    w("   First pick at each position (median): " + ", ".join(
        f"{g} {st.median(first_pick[g]):.0f}|{real['first_pick_at_position_median'].get(g, '-')}"
        for g in GROUPS if first_pick[g]))
    te_rounds = [comp["TE"][rnd] / n_d for rnd in range(1, 8)]
    w("   TEs per round: " + " ".join(f"{x:.1f}" for x in te_rounds) +
      "   (real scaled: " + " ".join(f"{real_comp['TE'][str(r)] * scale_:.1f}" for r in range(1, 8)) + ")")
    w("   Age at the draft by round: " + ", ".join(
        f"R{r} {st.mean(ages[r]):.1f}|{real['age_at_draft_by_round'][str(r)]}" for r in range(1, 8)))
    w("")

    # 4. TEs: good TEs by round
    w("4. TIGHT ENDS (the FOF8 'TEs fall late' exploit)")
    te = [c for c in cs if c["group"] == "TE"]
    if te:
        good = Counter(c["round"] for c in te if sum(c["starts"]) >= 5 or c["pro_bowls"] > 0)
        pbte = Counter(c["round"] for c in te if c["pro_bowls"] > 0)
        tot = Counter(c["round"] for c in te)
        rg = real["te_focus"]["good_te_by_round"]
        rp = real["te_focus"]["pro_bowl_te_by_round"]
        rn = real["picks_per_draft_by_position_round"]["TE"]
        w("   Share of all good TEs (5+ seasons started or a Pro Bowl) by round, sim | real: " +
          " ".join(f"R{r} {100 * good[r] / max(1, sum(good.values())):.0f}|{100 * rg[str(r)] / sum(rg.values()):.0f}%"
                   for r in range(1, 8)))
        w("   Share of Pro Bowl TEs by round, sim | real: " +
          " ".join(f"R{r} {100 * pbte[r] / max(1, sum(pbte.values())):.0f}|{100 * rp[str(r)] / sum(rp.values()):.0f}%"
                   for r in range(1, 8)))
        # Best TE prospects by true grade: where did they go?
        best = []
        for r in results:
            for d in r["drafts"]:
                tes = sorted(((n["grade"], pid) for pid, n in d["notes"].items() if n["pos"] == "TE"), reverse=True)
                pick_of = {pk["pid"]: pk["pick"] for pk in d["picks"]}
                if tes:
                    best.append(pick_of[tes[0][1]])
        w(f"   The class's truly best TE was picked at: median {st.median(best):.0f}, "
          f"after round 3 in {100 * sum(b > 96 for b in best) / len(best):.0f}% of drafts")
    w("")

    # 5. Board vs pick
    w("5. TEAMS FOLLOW THE CONSENSUS BOARD, WITH REAL SCATTER (board rank vs actual pick)")
    gaps = defaultdict(list)
    xs, ys = [], []
    falls = []
    for r in results:
        for d in r["drafts"]:
            for pk in d["picks"]:
                br = pk.get("board_rank")
                if br is None or br > 100:
                    continue
                band = "1-10" if br <= 10 else "11-32" if br <= 32 else "33-64" if br <= 64 else "65-100"
                gaps[band].append(pk["pick"] - br)
                xs.append(math.log(br))
                ys.append(math.log(pk["pick"]))
                if pk["pick"] - br >= 60:
                    falls.append(d["notes"][pk["pid"]]["flag"])
    rb = real_ai["board_vs_pick_2023"]["by_rank_band"]
    for band in ("1-10", "11-32", "33-64", "65-100"):
        g = sorted(gaps[band])
        if not g:
            continue
        p10, p90 = g[len(g) // 10], g[(9 * len(g)) // 10]
        w(f"   ranked {band:>6}: typical gap {st.median([abs(x) for x in g]):4.0f} | {rb[band]['abs_median']}"
          f"   80% range {p10:+d} to {p90:+d} | {rb[band]['p10']:+d} to {rb[band]['p90']:+d}")
    if len(xs) > 2:
        mx, my = st.mean(xs), st.mean(ys)
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        corr = cov / math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
        w(f"   rank-pick correlation (log): {corr:.2f} | {real_ai['board_vs_pick_2023']['rank_pick_correlation']}")
    undrafted = 0
    tot100 = 0
    for r in results:
        for d in r["drafts"]:
            ranks = {pk.get("board_rank") for pk in d["picks"]}
            tot100 += 1
            undrafted += sum(1 for k in range(1, 101) if k not in ranks)
    w(f"   top-100 ranked prospects left undrafted per draft: {undrafted / max(1, tot100):.1f} | "
      f"{len(real_ai['board_vs_pick_2023']['ranked_top100_undrafted'])} (2023, many of them hurt or off-field)")
    if falls:
        c = Counter(f or "none" for f in falls)
        w(f"   falls of 60+ picks per draft: {len(falls) / n_d:.1f}; reason: " +
          ", ".join(f"{k} {v}" for k, v in c.most_common()))
    w("")

    # 6. Need
    w("6. NEED: chance a team takes the position in rounds 1-2, normally | after a 1st-rounder there"
      " in the last 3 drafts (sim | real)")
    take = defaultdict(lambda: [0, 0, 0, 0])
    for r in results:
        r1 = defaultdict(set)   # (team, group) -> years with an R1 pick
        early = defaultdict(set)
        teams = set()
        for d in r["drafts"]:
            for pk in d["picks"]:
                g = DO.GROUP[d["notes"][pk["pid"]]["pos"]]
                teams.add(pk["team"])
                if pk["round"] == 1:
                    r1[(pk["team"], g)].add(d["season"])
                if pk["round"] <= 2:
                    early[(pk["team"], g)].add(d["season"])
        seasons_ = sorted(d["season"] for d in r["drafts"])
        for s in seasons_[3:]:
            for t in teams:
                for g in GROUPS:
                    recent = any(s - 3 <= y < s for y in r1[(t, g)])
                    took = s in early[(t, g)]
                    idx = 2 if recent else 0
                    take[g][idx] += took
                    take[g][idx + 1] += 1
    need_real = real_ai["need_recent_first_rounder"]
    for g in GROUPS:
        if g not in need_real:
            continue
        a, n0, b, n1 = take[g]
        w(f"   {g:>3}: {fmt(a / max(1, n0))} | {fmt(need_real[g]['p_take_r1_r2'])}"
          f"    after a recent R1: {fmt(b / max(1, n1))} (n {n1}) | "
          f"{fmt(need_real[g]['p_take_r1_r2_after_r1_pick_there_in_last_3_drafts'])}")
    w("")

    # 7. QB
    w("7. QBs: the team's starting QB before the draft, and how often it took a QB (sim | real)")
    qb = defaultdict(lambda: [0, 0, 0])   # took R1, took R1-2, team-drafts
    names = {"young_good": "young_R1-2_starter_good", "young": "young_R1-2_starter_not_good",
             "good": "other_starter_good", "other": "other_starter_not_good"}
    for r in results:
        for d in r["drafts"]:
            took = defaultdict(set)
            sit = {}
            for pk in d["picks"]:
                n = d["notes"][pk["pid"]]
                sit.setdefault(pk["team"], n["qb"])
                if n["pos"] == "QB":
                    took[pk["team"]].add(pk["round"])
            for t, s in sit.items():
                qb[s][2] += 1
                qb[s][0] += 1 in took[t]
                qb[s][1] += bool(took[t] & {1, 2})
    for s, key in names.items():
        a, b, n = qb[s]
        rv = real_ai["qb_need"][key]
        w(f"   {s:>10} (n {n:4d}): QB in R1 {fmt(a / max(1, n))} | {fmt(rv['p_qb_r1'])}"
          f"   R1-2 {fmt(b / max(1, n))} | {fmt(rv['p_qb_r1_r2'])}")
    w("")

    # 8. Trades
    w("8. DRAFT-DAY TRADES (sim | real 2010-26, same-year pick-for-pick)")
    trades = [t for r in results for d in r["drafts"] for t in d["trades"]]
    w(f"   per draft: {len(trades) / max(1, n_d):.1f} | {real_ai['draft_trades']['per_draft']} (real drafts "
      f"have ~257 picks, this one 224: scaled {real_ai['draft_trades']['per_draft'] * 224 / 257:.1f})")
    bands = [("1-10", 1, 10), ("11-32", 11, 32), ("33-64", 33, 64), ("65-128", 65, 128), ("129-262", 129, 262)]
    rt = real_ai["draft_trades"]["by_top_pick"]
    for name, a, b in bands:
        g = [t for t in trades if a <= min(t["got"]) <= b]
        if not g:
            w(f"   top pick {name:>7}: none | {rt[name]['n']}")
            continue
        w(f"   top pick {name:>7}: {len(g) / n_d:4.1f} a draft | {rt[name]['n'] / 17:.1f}"
          f"   chart ratio {st.median(t['jj_ratio'] for t in g):.2f} | {rt[name]['jimmy_johnson_ratio_median']}"
          f"   picks given {st.median(len(t['gave']) for t in g):.0f} | {rt[name]['picks_given_median']}"
          f"   spots moved {st.median(min(t['gave']) - min(t['got']) for t in g):.0f} | {rt[name]['spots_moved_median']}")
    w("")

    # 9. Age
    w("9. AGE AT THE DRAFT: career value vs his slot (1.00 = as expected; sim | real)")
    # Expected value at each pick: the average of every career within 8 picks of it
    # (a pick band is too wide: older prospects go later within a band).
    by_pick = defaultdict(list)
    for c in cs:
        by_pick[c["pick"]].append(sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"])
    slot_at = {}
    for k in range(1, 263):
        vals = [v for j in range(max(1, k - 8), k + 9) for v in by_pick.get(j, ())]
        slot_at[k] = st.mean(vals) if vals else 0.0

    def value(c):
        return sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"]
    vs = defaultdict(lambda: [0.0, 0.0, 0])     # value, expected at his slot, players
    for r, run in zip(results, runs):
        notes = {}
        for d in r["drafts"]:
            notes.update(d["notes"])
        for c in DO.careers([run], min_seasons=MIN_SEASONS, skip_first=SKIP_FIRST):
            n = notes.get(c["pid"])
            if not n:
                continue
            a = n["age"] + 0.5           # about PFR's whole-year age (see the note below)
            key = "21 or younger" if a < 22 else "22" if a < 23 else "23" if a < 24 else "24+"
            vs[key][0] += value(c)
            vs[key][1] += slot_at[c["pick"]]
            vs[key][2] += 1
    # The real ratios average about 1.11 (PFR's slot expectation runs a bit low), so each
    # group is also shown relative to its own data's average.
    ra = real_ai["age_effect"]
    real_mean = sum(ra[k]["career_av_vs_slot"] * ra[k]["n"] for k in ra if k != "note") / sum(
        ra[k]["n"] for k in ra if k != "note")
    sim_mean = sum(v for v, e, n in vs.values()) / max(1e-9, sum(e for v, e, n in vs.values()))
    for key in ("21 or younger", "22", "23", "24+"):
        v, e, n = vs[key]
        if n:
            rv = ra[key]["career_av_vs_slot"]
            w(f"   {key:>13}: {v / e:.2f} (n {n}) | {rv}    relative to average: {v / e / sim_mean:.2f} | "
              f"{rv / real_mean:.2f}")
    w("   (sim ages here = age on draft day + half a year, about PFR's whole-year age; value = seasons as a"
      " starter + 1.5 per Pro Bowl + 0.25 per season on a roster)")
    w("")

    # 10. Team skill
    w("10. SOME TEAMS REALLY ARE BETTER DRAFTERS (career value vs slot by team, odd vs even drafts)")
    corr_vals = []
    spread = []
    for r, run in zip(results, runs):
        odd, even, all_ = (defaultdict(lambda: [0.0, 0.0]) for _ in range(3))
        for c in DO.careers([run], min_seasons=MIN_SEASONS, skip_first=SKIP_FIRST):
            t = c["team"]
            for acc in (odd if c["season"] % 2 else even, all_):
                acc[t][0] += value(c)
                acc[t][1] += slot_at[c["pick"]]
        ts = [t for t in all_ if odd[t][1] and even[t][1]]
        if len(ts) > 3:
            a = [odd[t][0] / odd[t][1] for t in ts]
            b = [even[t][0] / even[t][1] for t in ts]
            ma, mb = st.mean(a), st.mean(b)
            cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
            corr_vals.append(cov / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)))
            spread += [all_[t][0] / all_[t][1] for t in ts]
    ts = real_ai["team_drafting_skill"]
    if corr_vals:
        spread.sort()
        w(f"   odd vs even correlation: {st.mean(corr_vals):.2f} | {ts['odd_vs_even_year_correlation']}"
          f"   best team {spread[-1]:.2f} | {ts['team_av_vs_slot_best']}, worst {spread[0]:.2f} | {ts['worst']},"
          f" middle half {spread[len(spread) // 4]:.2f}-{spread[(3 * len(spread)) // 4]:.2f} | {ts['p25']}-{ts['p75']}")
    w("")

    # 11. Combine
    w("11. COMBINE: rounds 1-2 vs rounds 3-7 averages (sim | real)")
    comb = defaultdict(lambda: defaultdict(lambda: ([], [])))
    for r in results:
        rnd_of = {pk["pid"]: pk["round"] for pk in r["picks"]}
        for pid, inf in r["info"].items():
            g = DO.GROUP[inf["pos"]]
            early = rnd_of.get(pid, 9) <= 2
            for drill, v in inf["combine"].items():
                if v is not None:
                    comb[g][drill][0 if early else 1].append(v)
            comb[g]["wt"][0 if early else 1].append(inf["wt"])
    rc = real["combine_rounds_1_2_vs_later_means"]
    keymap = {"forty": "forty", "vertical": "vertical", "broad": "broad_jump", "cone": "cone", "bench": "bench", "wt": "wt"}
    for g in GROUPS:
        if g == "K/P":
            continue
        cells = []
        for drill in ("forty", "vertical", "broad", "cone", "bench", "wt"):
            e, l = comb[g][drill]
            rv = rc.get(g, {}).get(keymap[drill])
            if not e or not l or not rv:
                continue
            d1 = 2 if drill in ("forty", "cone") else 1
            cells.append(f"{drill} {st.mean(e):.{d1}f}/{st.mean(l):.{d1}f}|{rv[0]:.{d1}f}/{rv[1]:.{d1}f}")
        w(f"   {g:>3}: " + "  ".join(cells))
    w("")

    front_offices(results, runs, w)
    league_health(results, runs, w)
    return out


def _corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den if den else 0.0


def front_offices(results, runs, w):
    """How smart and how human the AI front offices are (docs/research/real_draft_habits.json)."""
    hab = json.load(open(RESEARCH / "real_draft_habits.json"))
    w("13. FRONT OFFICES: SMART, BUT HUMAN (sim | real)")
    # Trade habits
    corrs, sds, per_deal, vs_value = [], [], [], []
    qb_up = defaultdict(lambda: [0, 0])
    qb_all = defaultdict(lambda: [0, 0])
    bands = [("1-10", 1, 10), ("11-32", 11, 32), ("33-64", 33, 64), ("65-262", 65, 262)]
    for r, run in zip(results, runs):
        net = defaultdict(lambda: defaultdict(int))
        deals = 0
        for d in r["drafts"]:
            pos_at = {pk["pick"]: d["notes"][pk["pid"]]["pos"] for pk in d["picks"]}
            for t in d["trades"]:
                net[t["up"]][d["season"]] -= 1
                net[t["down"]][d["season"]] += 1
                deals += 1
                top = min(t["got"])
                for name, a, b in bands:
                    if a <= top <= b:
                        qb_up[name][0] += pos_at.get(top) == "QB"
                        qb_up[name][1] += 1
            for pk in d["picks"]:
                for name, a, b in bands:
                    if a <= pk["pick"] <= b:
                        qb_all[name][0] += pos_at[pk["pick"]] == "QB"
                        qb_all[name][1] += 1
        seasons_ = sorted(d["season"] for d in r["drafts"])
        teams = sorted({t for d in r["drafts"] for t in d.get("teams", {})} or {pk["team"] for pk in r["picks"]})
        if not seasons_ or not teams:
            continue
        odd = [st.mean(net[t][s] for s in seasons_ if s % 2) for t in teams]
        even = [st.mean(net[t][s] for s in seasons_ if not s % 2) for t in teams]
        corrs.append(_corr(odd, even))
        means = [sum(net[t][s] for s in seasons_) / len(seasons_) for t in teams]
        sds.append(st.pstdev(means))
        per_deal.append(st.pstdev(means) / max(1e-9, 2 * deals / len(seasons_) / len(teams)))
        # trade habit vs drafting value
        cs = DO.careers([run], min_seasons=MIN_SEASONS, skip_first=SKIP_FIRST)
        by_pick = defaultdict(list)
        for c in cs:
            by_pick[c["pick"]].append(sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"])
        exp = {k: st.mean(v) for k in range(1, 263)
               if (v := [x for j in range(max(1, k - 8), k + 9) for x in by_pick.get(j, [])])}
        val = defaultdict(lambda: [0.0, 0.0])
        for c in cs:
            val[c["team"]][0] += sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"]
            val[c["team"]][1] += exp[c["pick"]]
        common = [t for t in teams if val[t][1]]
        if len(common) > 3:
            vs_value.append(_corr([means[teams.index(t)] for t in common], [val[t][0] / val[t][1] for t in common]))
    h = hab["habit"]
    if corrs:
        w(f"   trade habit lasts (net trade-downs per draft, odd vs even years): {st.mean(corrs):.2f} | "
          f"{h['net_trade_downs_odd_vs_even_corr']}")
        w(f"   spread of teams' habits (net trade-downs per draft, sd): {st.mean(sds):.2f} | {h['team_net_per_draft_sd']}"
          f"   per deal a team makes: {st.mean(per_deal):.2f} | {h['team_net_per_draft_sd'] / h['deals_per_team_draft']:.2f}"
          f"  (real counts deals with future picks too)")
        if vs_value:
            w(f"   trade-down habit vs drafting value: {st.mean(vs_value):+.2f} | {h['trade_down_habit_vs_drafting_value_corr']:+.2f}"
              f" (a habit, not a sign of skill)")
    tu = hab["trade_up_targets"]
    w("   QBs among the players teams traded up for (vs QBs among all picks there): " + "   ".join(
        f"picks {name}: {100 * qb_up[name][0] / max(1, qb_up[name][1]):.0f}% vs {100 * qb_all[name][0] / max(1, qb_all[name][1]):.0f}%"
        f" (n {qb_up[name][1]}) | {100 * tu[name]['qb_share_of_trade_ups']:.0f}% vs {100 * tu[name]['qb_share_of_all_picks']:.0f}%"
        for name, a, b in bands[:2]))
    # Big reaches
    reach_n, reach_max, n_d = 0, 0, 0
    for r in results:
        for d in r["drafts"]:
            n_d += 1
            biggest = 0
            for pk in d["picks"]:
                br = pk.get("board_rank")
                if br and br <= 100 and br - pk["pick"] >= 20:
                    reach_n += 1
                    biggest = max(biggest, br - pk["pick"])
            reach_max += biggest
    rr = hab["reaches_2023"]
    w(f"   big reaches (top-100 big-board players taken 20+ picks before their rank) per draft: "
      f"{reach_n / max(1, n_d):.1f} | {rr['count']} (2023, of 89 matched); biggest per draft {reach_max / max(1, n_d):.0f} | {rr['biggest']}")
    # Speed: does a prospect's 40 still predict beating his slot?
    real_speed = {"RB": 0.25, "TE": 0.23, "LB": 0.15, "WR": 0.01, "DB": 0.0, "DE": 0.0, "QB": 0.10}
    pts = defaultdict(list)
    for r, run in zip(results, runs):
        cs = DO.careers([run], min_seasons=MIN_SEASONS, skip_first=SKIP_FIRST)
        by_pick = defaultdict(list)
        for c in cs:
            by_pick[c["pick"]].append(sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"])
        exp = {k: st.mean(v) for k in range(1, 263)
               if (v := [x for j in range(max(1, k - 8), k + 9) for x in by_pick.get(j, [])])}
        for c in cs:
            inf = r["info"].get(c["pid"])
            if inf and inf["combine"].get("forty") is not None:
                g = DO.GROUP[inf["pos"]]
                pts[g].append((-inf["combine"]["forty"],
                               sum(c["starts"]) + 1.5 * c["pro_bowls"] + 0.25 * c["seasons_on_roster"] - exp[c["pick"]]))
    w("   40 time vs beating his draft slot (correlation; real teams price speed in at WR/DB/DE, not at RB/TE): " +
      "  ".join(f"{g} {_corr(*zip(*pts[g])):+.2f}|{real_speed[g]:+.2f}" for g in real_speed if len(pts[g]) > 30))
    w("")


def league_health(results, runs, w):
    w("12. LEAGUE HEALTH OVER THE SEASONS (sim | real)")
    w(f"   drafted rookies among starters (not K/P/LS): {fmt(DO.rookie_share_of_starters(runs, SKIP_FIRST))} | "
      f"{fmt(DO.REAL_ROOKIE_SHARE_OF_STARTERS)} (real: 50%+ snap players)")
    w(f"   players with 9+ seasons: {fmt(DO.veteran_share(runs, SKIP_FIRST))} | 9% (real week-1 rosters 2021-26)")
    # Rookies on the 53 and who's still in the league a year later, by experience.
    rook, tot = 0, 0
    stay = defaultdict(lambda: [0, 0])
    for r in results:
        ss = sorted(r["seasons"])
        for s in ss[SKIP_FIRST:]:
            snap = r["seasons"][s]
            nxt = r["seasons"].get(s + 1)
            rook += sum(v[4] == 0 for v in snap.values())
            tot += len(snap)
            if nxt is None:
                continue
            for pid, v in snap.items():
                e = min(v[4], 12)
                stay[e][0] += pid in nxt
                stay[e][1] += 1
    w(f"   rookies on the 53 (drafted + undrafted): {fmt(rook / max(1, tot))} | 12.3% (real week-1 53s)")
    real_stay = {0: 74, 1: 75, 2: 74, 3: 74, 4: 74, 5: 73, 6: 71, 7: 69, 8: 64, 9: 58, 10: 64, 11: 62, 12: 60}
    w("   on a 53 again next season, by seasons of experience (sim | real, main session's real_stay.py): " +
      " ".join(f"{e}:{100 * a / max(1, n):.0f}|{real_stay[e]}" for e, (a, n) in sorted(stay.items())))
    for r in results:
        sh = r["shown"]
        ss = sorted(sh)
        pick = [ss[0], ss[len(ss) // 4], ss[len(ss) // 2], ss[(3 * len(ss)) // 4], ss[-1]]
        w(f"   league {r['seed']}: on screen 80+ / 90+ / median / starters' internal avg by season: " +
          "  ".join(f"{s}: {sh[s]['80+']}/{sh[s]['90+']}/{sh[s]['median']:.0f}/{sh[s]['starter_avg']:.1f}" for s in pick))
    # Each position's starters (internal ratings): the first season vs the last 5, all leagues.
    drift = defaultdict(lambda: [[], []])
    for r in results:
        sh = r["shown"]
        ss = sorted(sh)
        for pos_, v in sh[ss[0]].get("pos", {}).items():
            drift[pos_][0].append(v)
        for s in ss[-5:]:
            for pos_, v in sh[s].get("pos", {}).items():
                drift[pos_][1].append(v)
    if drift:
        w("   starters' average by position, first season -> last 5 seasons (internal): " +
          " ".join(f"{p} {st.mean(a):.0f}->{st.mean(b):.0f}" for p, (a, b) in drift.items() if a and b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102,104,105,106,107")
    ap.add_argument("--seasons", type=int, default=22)
    ap.add_argument("--out", default=str(ROOT / "tools" / "draft_report.txt"))
    ap.add_argument("--save", help="also keep the raw results in this file (pickle)")
    ap.add_argument("--load", help="report on raw results saved earlier with --save (no new run)")
    a = ap.parse_args()
    seeds = [int(x) for x in a.leagues.split(",")]
    t0 = time.time()
    import pickle
    if a.load:
        results = pickle.load(open(a.load, "rb"))
        seeds = [r["seed"] for r in results]
    else:
        with Pool(min(len(seeds), 6)) as pool:
            results = pool.map(_worker, [(s, a.seasons) for s in seeds])
        if a.save:
            pickle.dump(results, open(a.save, "wb"))
    out = [f"Draft realism check (engine/draft.py), {len(seeds)} leagues x {a.seasons} seasons, "
           f"{time.time() - t0:.0f} s", ""]
    report(results, out)
    text = "\n".join(out)
    print(text)
    Path(a.out).write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
