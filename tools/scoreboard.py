# tools/scoreboard.py
# The scoreboard: one command runs the game's checks side by side, boils them
# down to headline numbers next to the real NFL, and compares them with the
# last saved baseline, flagging only changes bigger than the numbers' normal
# run-to-run swing.
#
#   python tools/scoreboard.py                     # default suites (~6-8 minutes)
#   python tools/scoreboard.py --suites fa,sim     # only some suites
#   python tools/scoreboard.py --full              # also the draft suite (~10 more minutes)
#   python tools/scoreboard.py --save-baseline     # run, then make this run the baseline
#   python tools/scoreboard.py --report-only       # re-print the last run against the baseline
#   python tools/scoreboard.py --all               # print every measure, not just the changes
#   python tools/scoreboard.py --suites fa --set free_agency.WAVE_ROUNDS=1
#                                                  # try a knob without editing code (engine.<module>.<NAME>)
#
# Suites (each job is one league or one season, all in one pool of processes):
#   fa           free agency, contracts and the cap (tools/free_agency_check.py on the
#                league lab, tools/lab.py: the game's own seasons and offseasons, fast
#                games): one unit per offseason
#   sim          the game sim's stats (tools/realism_check.py's measures, tools/simlab.py
#                seasons): league averages and every "how common is this season" measure,
#                one unit per season
#   determinism  the same league twice in separate processes must come out identical
#   speed        CPU seconds per week of real games and per offseason Next click (one league,
#                run alone at the end so the other jobs don't slow it)
#   draft        (--full) the draft over 22 seasons (tools/draft_check.py's harness)
#   rookies      drafted rookies' playing time by round and the draft board's Developed %
#                (tools/rookie_check.py on lab leagues, fast games): one unit per league
#   integration  the whole game with a team of yours, start to finish, save/load at every
#                stage (tools/integration_check.py): problems must be 0
# The sim suite also reports QB season styles (tools/qb_style_check.py: efficient low-volume
# passers, running QBs, pass attempts per game).
#
# How to read it. Each measure is averaged over its units (offseasons, seasons, leagues).
# Its noise band is how much that average would swing from luck alone (the spread of the
# units / the square root of how many there are). A change from the baseline counts only if
# it's more than 3 times the two runs' combined noise; then it says IMPROVED or REGRESSED
# if it moved toward or away from the real NFL, CHANGED if there's no real number. Measures
# that must be zero (cap legality, determinism) are flagged BROKEN on any miss. Speed is
# flagged when it's over 25% slower or faster. The same build always gives the same numbers
# (every league's dice are fixed), so the bands guard against changes that only reshuffle
# luck.
#
# Writes tools/scoreboard/latest.json and tools/scoreboard/report.txt (and baseline.json with
# --save-baseline). Nothing in the game or your saves is changed.

import argparse
import json
import math
import statistics as st
import sys
import time
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = HERE / "scoreboard"
SIGMA = 3.0                   # a change counts if it's more than this many times the combined noise
SPEED_TOLERANCE = 0.25        # speed: flagged past this share slower or faster

FA_SEEDS = (101, 102, 103)
FA_OFFSEASONS = 4
SIM_SEEDS = (101, 102, 103, 104)
SIM_SEASONS = 4
DRAFT_SEEDS = (101, 102, 104, 105, 106, 107)
DRAFT_SEASONS = 22
DET_SEED = 211
ROOKIE_SEEDS = (301, 302, 303, 304)
ROOKIE_SEASONS = 7            # classes from the 2nd and 3rd league years followed 5 seasons
INTEGRATION_SEASONS = 3
SPEED_SEED = 212

# ---- Real targets and labels ------------------------------------------------------------

def _fa_real():
    import free_agency_check as F
    years = F.REAL_FA_DAY1_TARGET_YEARS
    reals = {y: sorted((x / c for x in v), reverse=True) for y, (c, v) in F.REAL_FA_DAY1.items()}

    def avg(fn):
        return st.mean(fn(reals[y]) for y in years)
    rf, rm = F.REAL_FP["all"], F.REAL_M["offseason"]
    kinds = json.loads((ROOT / "docs" / "research" / "real_deal_kinds.json").read_text())["per_season"]
    return {
        "room_w1_most": avg(lambda r: r[0]), "room_w1_5th": avg(lambda r: r[4]),
        "room_w1_median": avg(st.median), "room_w1_24th": avg(lambda r: r[23]),
        "teams_under_2pct_w1": avg(lambda r: sum(x < 0.02 for x in r)),
        "same_all": rm["all"]["same"], "new_all": rm["all"]["new_team"], "gone_all": rm["all"]["gone"],
        "gone_0_2": rm["by_experience_end_of_season"]["0-2"]["gone"],
        "gone_3_4": rm["by_experience_end_of_season"]["3-4"]["gone"],
        "gone_5_7": rm["by_experience_end_of_season"]["5-7"]["gone"],
        "gone_8p": rm["by_experience_end_of_season"]["8+"]["gone"],
        "illegal": 0, "over_cap_team_weeks": 0,
        "market_new_team": kinds["new_team"], "market_resigned": kinds["re_signed"],
        "market_extensions": kinds["extension"],
        "market_deals": kinds["new_team"] + kinds["re_signed"] + kinds["extension"],
        "fair_good_fa_signings": rf["n_per_season"], "fair_under_60pct": rf["under_60"],
        "fair_under_40pct": rf["under_40"], "fair_minimum": rf["minimum_level"],
        "camp_unsigned_stars": 0.0, "tags": 10.0,
    }


FA_LABELS = {
    "room_w1_most": ("cap room after FA's first wave: most", "pct"),
    "room_w1_5th": ("cap room after the first wave: 5th most", "pct"),
    "room_w1_median": ("cap room after the first wave: median team", "pct"),
    "room_w1_24th": ("cap room after the first wave: 24th", "pct"),
    "teams_under_2pct_w1": ("teams under 2% of the cap after the first wave", "n"),
    "room_open_median": ("cap room when FA opens: median team", "pct"),
    "same_all": ("last season's players on the same team at week 1", "pct"),
    "new_all": ("...on a new team", "pct"), "gone_all": ("...out of the league", "pct"),
    "gone_0_2": ("out of the league: 0-2 seasons", "pct"), "gone_3_4": ("out of the league: 3-4 seasons", "pct"),
    "gone_5_7": ("out of the league: 5-7 seasons", "pct"), "gone_8p": ("out of the league: 8+ seasons", "pct"),
    "illegal": ("cap legality misses at offseason checkpoints + missing contracts (must be 0)", "n"),
    "over_cap_team_weeks": ("AI team-weeks over the cap during seasons (must be 0)", "n"),
    "in_season_deals": ("deals signed during a season", "n"),
    "market_deals": ("market deals (1%+ of the cap) a league year", "n"),
    "market_new_team": ("market deals with a new team", "n"), "market_resigned": ("market re-signings", "n"),
    "market_extensions": ("market extensions", "n"),
    "fair_good_fa_signings": ("good free agents changing teams (fair-price check)", "n"),
    "fair_under_60pct": ("...signing under 60% of market value", "pct"),
    "fair_under_40pct": ("...under 40%", "pct"), "fair_minimum": ("...at about the minimum", "pct"),
    "camp_unsigned_good": ("good players 30 or younger unsigned at camp", "n"),
    "camp_unsigned_stars": ("star-priced players unsigned at camp (your bargain window)", "n"),
    "tags": ("franchise tags", "n"), "cap_cuts": ("cap cuts", "n"), "extensions": ("extensions", "n"),
    "wk1_cap_used": ("cap used at week 1 (average team)", "pct"), "wk1_dead": ("dead money at week 1", "pct"),
}
MUST_BE_ZERO = {"fa.illegal", "fa.over_cap_team_weeks", "determinism.mismatch", "integration.problems"}

# ---- Jobs ------------------------------------------------------------------------------

def apply_overrides():
    """--set module.NAME=value (passed to every process in SCOREBOARD_SET)."""
    import importlib
    import os
    for item in filter(None, os.environ.get("SCOREBOARD_SET", "").split(";")):
        key, value = item.split("=", 1)
        mod, name = key.rsplit(".", 1)
        m = importlib.import_module(mod if mod.startswith(("engine", "tools")) else "engine." + mod)
        if not hasattr(m, name):
            raise SystemExit(f"--set: {mod} has no {name}")
        setattr(m, name, eval(value))


def work(job):
    """One job in its own process. Returns (suite, part)."""
    apply_overrides()
    kind = job[0]
    if kind == "fa":
        import free_agency_check as F
        _k, seed, seasons = job
        stats, _day1, _top = F.run_league((seed, seasons, "fast"))
        return kind, {"units": stats["units"], "season_units": stats["season_units"]}
    if kind == "sim":
        import measures as MS
        import simlab
        _k, seed, i = job
        league = simlab.get_league(str(seed))
        import qb_style_check as QS
        res = simlab.play_season(league, seed=f"{seed}-{i}", norms=simlab.build_norms(league))
        plays = res["team_tot"].get("plays", 0) / max(1, res["team_games"])
        qb, att_pg = QS.season_measures(QS.game_qbs(res["players"], plays))
        return kind, {"avg": simlab.league_averages(res["team_tot"], res["team_games"]),
                      "common": MS.measure(res["players"]), "qb": qb, "qb_att_pg": att_pg, "seed": seed}
    if kind == "rookies":
        import rookie_check as RK
        return kind, RK.run_league((job[1], job[2]))
    if kind == "integration":
        import integration_check as IC
        res = IC.run(job[1], say=lambda *a, **k: None)
        return kind, {"problems": res["problems"], "health": res["health"]}
    if kind == "determinism":
        from lab import Lab, fingerprint
        lab = Lab(job[1]).run(1)
        return kind, {"fp": fingerprint(lab.league)}
    if kind == "draft":
        import draft_check as DC
        _k, seed, seasons = job
        return kind, {"result": DC._worker((seed, seasons))}
    raise ValueError(kind)


def speed_suite():
    """Seconds per week with the real sim and per offseason Next click (one league, run alone).
    CPU time of this process, not the clock: other programs (or another session's jobs) running
    at the same time would otherwise show up as the game getting slower."""
    apply_overrides()
    from lab import Lab
    from engine import season as SEASON
    clock = time.process_time
    lab = Lab(SPEED_SEED, "real")
    lg = lab.league
    weeks, phases = [], defaultdict(list)
    t = [clock()]

    def tick(_lab, **_info):
        now = clock()
        d, t[0] = now - t[0], now
        return d

    def week_end(_lab, label):
        d = tick(_lab)
        if SEASON.in_regular_season(lg) and lg.week > 1:
            weeks.append(d)
    lab.on("week_end", week_end)
    lab.on("phase_before", lambda _lab, phase, wave: tick(_lab))
    lab.on("phase_after", lambda _lab, phase, wave: phases["fa wave" if phase == "fa" else phase].append(tick(_lab)))
    lab.play_season()
    t[0] = clock()
    t0 = clock()
    lab.play_offseason()
    total = clock() - t0
    out = {"sec_per_week_real_games": weeks, "sec_per_fa_wave": phases["fa wave"],
           "sec_offseason_total": [total]}
    for k in ("resign", "draft", "camp"):
        if phases.get(k):
            out[f"sec_{k}_phase"] = phases[k]
    return out


# ---- Combining into measures -------------------------------------------------------------

def measure(values, real=None, label=None, unit="n", lo=None, hi=None):
    v = [x for x in values if x is not None]
    n = len(v)
    mean = st.mean(v) if v else None
    se = (st.stdev(v) / math.sqrt(n)) if n > 1 else 0.0
    return {"mean": mean, "se": se, "n": n, "real": real, "label": label or "", "unit": unit,
            "real_lo": lo, "real_hi": hi}


def combine(parts):
    """{suite: [parts]} -> {"suite.measure": measure}."""
    out = {}
    if parts.get("fa"):
        import free_agency_check as F
        real = _fa_real()
        vals = defaultdict(list)
        for p in parts["fa"]:
            for u in p["units"] + p["season_units"]:
                for k, v in u.items():
                    vals[k].append(v)
        for k, v in vals.items():
            label, unit = FA_LABELS.get(k, (k, "n"))
            out[f"fa.{k}"] = measure(v, real.get(k), label, unit)
    if parts.get("sim"):
        bench = json.loads((HERE / "real_nfl_benchmarks.json").read_text(encoding="utf-8"))
        import realism_check as RC
        labels = dict((key, label) for label, key in RC.LEAGUE_LABELS)
        for key, rv in bench["league_per_team_game"].items():
            if key in labels:
                out[f"sim.avg.{key}"] = measure([p["avg"][key] for p in parts["sim"]], rv,
                                                f"league average per team-game: {labels[key]}")
        for key, r in bench["common"].items():
            vals = [p["common"].get(key) for p in parts["sim"]]
            if any(v is not None for v in vals):
                out[f"sim.common.{key}"] = measure(vals, r["mean"], key, lo=r["min"], hi=r["max"])
        import qb_style_check as QS
        qreal = QS.real()
        for key in ("qb_efficient_low_volume", "qb_600_rush"):
            r = qreal[key]
            out[f"sim.qb.{key}"] = measure([p["qb"][key] for p in parts["sim"] if "qb" in p], r["mean"],
                                           QS.LABELS[key], lo=r["min"], hi=r["max"])
        # Attempts per game: percentiles of all seasons' starters, one value per league (4 seasons each).
        by_league = defaultdict(list)
        for p in parts["sim"]:
            by_league[p.get("seed")] += p.get("qb_att_pg", [])
        for key in ("qb_att_pg_p10", "qb_att_pg_p50", "qb_att_pg_p90"):
            vals = [QS.percentiles(v).get(key) for v in by_league.values() if v]
            out[f"sim.qb.{key}"] = measure(vals, qreal[key]["mean"], QS.LABELS[key])
    if parts.get("rookies"):
        import rookie_check as RK
        rl = RK.real()
        names = {"rookie_regular": "drafted rookies who are regulars (half the snaps) as rookies",
                 "started_as_rookie": "eventual regulars (years 1-5) who already were as rookies",
                 "ever": "drafted players who are regulars in years 1-5"}
        for b, _r in RK.BUCKETS:
            for k, lbl in names.items():
                vals = [RK.summarize(p["players"])[b][k] for p in parts["rookies"] if p["players"]]
                out[f"rookies.r{b}.{k}"] = measure(vals, rl[b][k], f"round {b}: {lbl}", "pct")
        for k, lbl in (("devl_70plus", "draft board: drafted players shown 70%+ developed"),
                       ("devl_80plus", "draft board: ...80%+ developed")):
            vals = [RK.devl_shares(p["devl"]).get(k) for p in parts["rookies"]]
            out[f"rookies.{k}"] = measure(vals, None, lbl, "pct")
    if parts.get("integration"):
        ip = parts["integration"][0]
        out["integration.problems"] = measure([len(ip["problems"])], 0,
                                              "whole-game test (your team, save/load each stage): problems (must be 0)")
        out["integration.starters_last_season"] = measure([ip["health"][-1][2]] if ip["health"] else [], None,
                                                          "whole-game test: starters' average overall, last season")
    if parts.get("determinism"):
        fps = [p["fp"] for p in parts["determinism"]]
        out["determinism.mismatch"] = measure([0 if len(set(fps)) == 1 else 1], 0,
                                              "same league twice in separate processes differs (must be 0)")
    if parts.get("speed"):
        sp = parts["speed"][0]
        names = {"sec_per_week_real_games": "seconds per regular-season week (real games, one league)",
                 "sec_per_fa_wave": "seconds per free agency Next click", "sec_offseason_total": "seconds for a whole offseason",
                 "sec_resign_phase": "seconds: start of league year phase", "sec_draft_phase": "seconds: the draft (no picks of yours)",
                 "sec_camp_phase": "seconds: training camp phase"}
        for k, v in sp.items():
            out[f"speed.{k}"] = measure(v, None, names.get(k, k), "sec")
    if parts.get("draft"):
        out.update(_draft_measures(parts["draft"]))
    return out


def _draft_measures(parts):
    import draft_outcomes as DO
    import draft_check as DC
    real = json.loads((ROOT / "docs" / "research" / "real_draft.json").read_text())
    real_te = json.loads((ROOT / "docs" / "research" / "real_te_draft.json").read_text())
    vals = defaultdict(list)
    for p in parts:
        r = p["result"]
        run = DC._runs_for_outcomes([r])[0]
        cs = DO.careers([run], min_seasons=DC.MIN_SEASONS, skip_first=DC.SKIP_FIRST)
        by_r = DO.summarize(cs, "round")
        for rnd in (1, 2, 3):
            if by_r.get(rnd):
                vals[f"r{rnd}_starter_3plus"].append(by_r[rnd]["starter_3plus_seasons"])
                vals[f"r{rnd}_never_started"].append(by_r[rnd]["never_started"])
        vals["rookies_among_starters"].append(DO.rookie_share_of_starters([run], DC.SKIP_FIRST))
        vals["players_9plus_seasons"].append(DO.veteran_share([run], DC.SKIP_FIRST))
        firsts = []
        for d in r["drafts"]:
            tes = sorted(pk["pick"] for pk in d["picks"] if d["notes"][pk["pid"]]["pos"] == "TE")
            if tes:
                firsts.append(tes[0])
        vals["first_te_pick"].append(st.median(firsts) if firsts else None)
    rr = real["by_round"]
    reals = {"r1_starter_3plus": rr["1"]["starter_3plus_seasons"], "r2_starter_3plus": rr["2"]["starter_3plus_seasons"],
             "r3_starter_3plus": rr["3"]["starter_3plus_seasons"], "r1_never_started": rr["1"]["never_started"],
             "r2_never_started": rr["2"]["never_started"], "r3_never_started": rr["3"]["never_started"],
             "rookies_among_starters": DO.REAL_ROOKIE_SHARE_OF_STARTERS, "players_9plus_seasons": 0.09,
             "first_te_pick": real_te["first_te_pick"]["median"]}
    labels = {"r1_starter_3plus": "round 1 picks who start 3+ seasons", "r2_starter_3plus": "round 2 ... 3+ seasons",
              "r3_starter_3plus": "round 3 ... 3+ seasons", "r1_never_started": "round 1 picks who never start",
              "r2_never_started": "round 2 never start", "r3_never_started": "round 3 never start",
              "rookies_among_starters": "drafted rookies among starters", "players_9plus_seasons": "players with 9+ seasons",
              "first_te_pick": "first tight end taken (median pick)"}
    return {f"draft.{k}": measure(v, reals.get(k), labels.get(k, k), "n" if k == "first_te_pick" else "pct")
            for k, v in vals.items()}


# ---- Comparing with the baseline -----------------------------------------------------------

def verdict(key, now, base):
    """(flag, why) for one measure: BROKEN, REGRESSED, IMPROVED, CHANGED, SLOWER, FASTER, or ''."""
    m = now["mean"]
    if key in MUST_BE_ZERO:
        return ("BROKEN", "must be 0") if m and m > 0 else ("", "")
    if base is None or base.get("mean") is None or m is None:
        return "", "new measure" if base is None else ""
    b = base["mean"]
    if key.startswith("speed."):
        if b and abs(m - b) / b > SPEED_TOLERANCE:
            return ("SLOWER" if m > b else "FASTER"), f"{100 * (m - b) / b:+.0f}%"
        return "", ""
    noise = math.sqrt(now["se"] ** 2 + base["se"] ** 2)
    if abs(m - b) <= SIGMA * noise or abs(m - b) < 1e-9:
        return "", ""
    real = now.get("real")
    if real is None:
        return "CHANGED", f"{(m - b) / noise:+.1f} x noise" if noise else "changed"
    closer = abs(m - real) < abs(b - real)
    return ("IMPROVED" if closer else "REGRESSED"), f"{(m - b) / noise:+.1f} x noise" if noise else ""


def fmt(m, unit):
    if m is None:
        return "-"
    if unit == "pct":
        return f"{100 * m:.1f}%"
    if unit == "sec":
        return f"{m:.2f}s"
    return f"{m:.1f}" if abs(m) < 1000 else f"{m:.0f}"


def outside_real(meas):
    lo, hi, m = meas.get("real_lo"), meas.get("real_hi"), meas["mean"]
    if lo is None or hi is None or m is None:
        return ""
    if m > hi * 1.03 + 0.5:
        return "HIGH"
    if m < lo * 0.97 - 0.5:
        return "low"
    return ""


def report(latest, baseline, show_all=False):
    lines = []
    say = lines.append
    meta, base_meta = latest.get("_meta", {}), (baseline or {}).get("_meta", {})
    say("=" * 110)
    say(f"SCOREBOARD {meta.get('when', '')}  suites: {', '.join(meta.get('suites', []))}  "
        f"({meta.get('seconds', 0):.0f} s)" + (f"  knobs set: {'; '.join(meta['set'])}" if meta.get("set") else ""))
    say(f"Compared with the baseline of {base_meta.get('when', '(none saved yet: run with --save-baseline)')}. "
        f"A change counts if it's more than {SIGMA:.0f}x the normal run-to-run swing.")
    say("=" * 110)
    rows = []
    for key, now in latest.items():
        if key.startswith("_"):
            continue
        base = (baseline or {}).get(key)
        flag, why = verdict(key, now, base)
        rows.append((key, now, base, flag, why))
    broken = [r for r in rows if r[3] == "BROKEN"]
    say("MUST BE ZERO: " + ("all fine" if not broken else ""))
    for key, now, base, flag, why in broken:
        say(f"  BROKEN  {key}: {now['label']} = {fmt(now['mean'], now['unit'])}")
    order = {"REGRESSED": 0, "SLOWER": 1, "IMPROVED": 2, "FASTER": 3, "CHANGED": 4}
    changed = sorted((r for r in rows if r[3] in order), key=lambda r: (order[r[3]], r[0]))
    say("")
    say(f"CHANGES BIGGER THAN THE NOISE ({len(changed)}):" if baseline else "CHANGES: (no baseline yet)")
    if changed:
        say(f"  {'verdict':10}{'measure':38}{'now':>12}{'(noise)':>10}{'baseline':>11}{'real':>10}  why")
    for key, now, base, flag, why in changed:
        noise = SIGMA * math.sqrt(now["se"] ** 2 + ((base or {}).get("se") or 0) ** 2)
        say(f"  {flag:10}{key[:37]:38}{fmt(now['mean'], now['unit']):>12}{'+/-' + fmt(noise, now['unit']):>10}"
            f"{fmt((base or {}).get('mean'), now['unit']):>11}{fmt(now.get('real'), now['unit']):>10}  {why}"
            + (f"  ({now['label']})" if now["label"] and not now["label"].startswith(key.split('.')[-1]) else ""))
    out_now = [(k, m) for k, m in latest.items() if not k.startswith("_") and outside_real(m)]
    say("")
    say(f"OUTSIDE THE REAL RANGE NOW (sim measures with a real five-season range): {len(out_now)}")
    if out_now:
        say("  " + ", ".join(f"{k.split('.', 2)[-1]} {outside_real(m)}" for k, m in out_now))
    quiet = len(rows) - len(changed) - len(broken)
    say("")
    say(f"Everything else ({quiet} measures) is within the noise of the baseline." if baseline
        else f"{quiet} measures recorded.")
    if show_all or not baseline:
        say("")
        say(f"ALL MEASURES  {'measure':40}{'now':>12}{'(noise)':>10}{'real':>10}  label")
        for key, now, base, flag, why in sorted(rows):
            if key.startswith("sim.common.") and not show_all:
                continue
            say(f"  {key[:52]:52}{fmt(now['mean'], now['unit']):>12}{'+/-' + fmt(SIGMA * now['se'], now['unit']):>10}"
                f"{fmt(now.get('real'), now['unit']):>10}  {now['label']}")
        if not show_all:
            say("  (the sim's 300 'how common' measures are left out here: --all shows them)")
    return "\n".join(lines)


# ---- Main ----------------------------------------------------------------------------------

def run(suites, workers):
    jobs = []
    if "fa" in suites:
        jobs += [("fa", s, FA_OFFSEASONS) for s in FA_SEEDS]
    if "draft" in suites:
        jobs += [("draft", s, DRAFT_SEASONS) for s in DRAFT_SEEDS]
    if "determinism" in suites:
        jobs += [("determinism", DET_SEED), ("determinism", DET_SEED)]
    if "sim" in suites:
        jobs += [("sim", s, i) for s in SIM_SEEDS for i in range(SIM_SEASONS)]
    if "rookies" in suites:
        jobs += [("rookies", s, ROOKIE_SEASONS) for s in ROOKIE_SEEDS]
    if "integration" in suites:
        jobs += [("integration", INTEGRATION_SEASONS)]
    parts = defaultdict(list)
    done = 0
    if jobs:
        with Pool(min(workers, len(jobs)), maxtasksperchild=1) as pool:
            for kind, part in pool.imap_unordered(work, jobs):
                parts[kind].append(part)
                done += 1
                print(f"  {done}/{len(jobs)} jobs done ({kind})", flush=True)
    if "speed" in suites:
        print("  speed (alone)...", flush=True)
        parts["speed"].append(speed_suite())
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="fa,sim,determinism,rookies,integration,speed")
    ap.add_argument("--full", action="store_true", help="also the draft suite")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--set", action="append", default=[], help="module.NAME=value: try a knob (engine module)")
    a = ap.parse_args()
    if a.set:
        import os
        os.environ["SCOREBOARD_SET"] = ";".join(a.set)
    OUT.mkdir(exist_ok=True)
    base_file, latest_file = OUT / "baseline.json", OUT / "latest.json"
    baseline = json.loads(base_file.read_text()) if base_file.exists() else None
    if a.report_only:
        latest = json.loads(latest_file.read_text())
    else:
        suites = [s.strip() for s in a.suites.split(",") if s.strip()] + (["draft"] if a.full else [])
        t0 = time.time()
        parts = run(suites, a.workers)
        latest = combine(parts)
        latest["_meta"] = {"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "suites": suites,
                           "seconds": time.time() - t0, "set": a.set}
        latest_file.write_text(json.dumps(latest, indent=1))
    text = report(latest, baseline, a.all)
    print(text)
    (OUT / "report.txt").write_text(text, encoding="utf-8")
    if a.save_baseline:
        base_file.write_text(json.dumps(latest, indent=1))
        print(f"\n(Saved as the baseline: {base_file})")


if __name__ == "__main__":
    main()
