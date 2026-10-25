# tools/sweep.py
# The knob sweep: try several values of engine settings side by side and rank them against
# the real NFL, in one command (Oct 25; Blake: "make development efficient", "make sure it
# wont compromise development accuracy"). Tonight's draft readiness was tuned by hand: four
# variants, four lab leagues each, separate processes, compared by eye. This does that.
#
#   python tools/sweep.py --suites rookies \
#       --try "draft.PROSPECT_READY_MEAN=0.80,0.82,0.85" --try "draft.PROSPECT_READY_SD=0.05,0.08"
#   python tools/sweep.py --suites rookies --variant "draft.PROSPECT_READY_MEAN=0.88;draft.PROSPECT_READY_SD=0.05" \
#       --variant "draft.PROSPECT_READY_MEAN=0.82;draft.PROSPECT_READY_SD=0.08" --leagues 8
#   python tools/sweep.py --suites sim --try "sim.tuning.SACK_K=0.9,1.0,1.1" --targets sim.common.edge_sacks>=10
#
# How it works:
#   - Variants: every combination of the --try values (a grid), plus any --variant lists
#     ("a=1;b=2": knobs set together). The code as it is (no knob changed) always runs too,
#     as "current". Knob names are engine.<module>.<NAME>, as tools/scoreboard.py --set.
#     (A setting another module copied with "from x import NAME" at import time isn't
#     reached this way; such knobs need the module that reads them.)
#   - Each variant plays the chosen suites' jobs (tools/scoreboard.py: the same leagues,
#     seeds and measures), all variants in one pool of processes, a fresh process per job.
#   - Targets: the measures to rank by (default: every measure of the chosen suites that has
#     a real NFL value). Each target's gap to real is counted in units of its noise (how much
#     that average swings from luck: spread of the units / the square root of their number),
#     with a floor of FLOOR_SHARE of the real value so a near-zero noise band can't dominate.
#     Score = the average of those gaps. Lower is closer to the real NFL. A difference
#     between two variants' scores of less than about 1 is within luck.
#   - Side effects: any other measure that moved from "current" by more than 3x the combined
#     noise is listed for each variant, so a fix in one place that breaks another shows.
#   - It only measures: it never writes a setting into the code. You read the table and decide.
#
# Writes tools/sweep/last_sweep.json and tools/sweep/last_sweep.txt (git-ignored).

import argparse
import itertools
import json
import math
import os
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import scoreboard as SB  # noqa: E402

OUT = HERE / "sweep"
FLOOR_SHARE = 0.02            # a target's noise counts as at least 2% of its real value
SUITES = ("fa", "sim", "rookies", "draft", "integration")


def jobs_for(suites, leagues=None):
    """The scoreboard's jobs for these suites; leagues: more (or fewer) leagues per suite."""
    def seeds(base):
        if not leagues:
            return base
        out = list(base[:leagues])
        nxt = max(base) + 1
        while len(out) < leagues:
            out.append(nxt)
            nxt += 1
        return tuple(out)
    jobs = []
    if "fa" in suites:
        jobs += [("fa", s, SB.FA_OFFSEASONS) for s in seeds(SB.FA_SEEDS)]
    if "draft" in suites:
        jobs += [("draft", s, SB.DRAFT_SEASONS) for s in seeds(SB.DRAFT_SEEDS)]
    if "sim" in suites:
        jobs += [("sim", s, i) for s in seeds(SB.SIM_SEEDS) for i in range(SB.SIM_SEASONS)]
    if "rookies" in suites:
        jobs += [("rookies", s, SB.ROOKIE_SEASONS) for s in seeds(SB.ROOKIE_SEEDS)]
    if "integration" in suites:
        jobs += [("integration", SB.INTEGRATION_SEASONS)]
    return jobs


def _work(item):
    """(variant index, its settings, scoreboard job) in a fresh process."""
    vi, settings, job = item
    os.environ["SCOREBOARD_SET"] = settings
    kind, part = SB.work(job)
    return vi, kind, part


def variants_from(tries, explicit):
    grid = []
    for t in tries or ():
        key, values = t.split("=", 1)
        grid.append([f"{key}={v.strip()}" for v in values.split(",")])
    out = [";".join(c) for c in itertools.product(*grid)] if grid else []
    out += list(explicit or ())
    return ["", *[v for v in out if v]]


def score(meas, targets):
    """(score, {target: gap in noise units}) for one variant's measures."""
    gaps = {}
    for k in targets:
        m = meas.get(k)
        if not m or m.get("mean") is None or m.get("real") is None:
            continue
        noise = max(m["se"], FLOOR_SHARE * abs(m["real"]), 1e-9)
        gaps[k] = abs(m["mean"] - m["real"]) / noise
    return (sum(gaps.values()) / len(gaps) if gaps else float("nan")), gaps


def side_effects(meas, current, targets):
    out = []
    for k, m in meas.items():
        if k in targets or k.startswith("speed.") or k not in current:
            continue
        b = current[k]
        if m.get("mean") is None or b.get("mean") is None:
            continue
        noise = math.sqrt(m["se"] ** 2 + b["se"] ** 2)
        if noise and abs(m["mean"] - b["mean"]) > SB.SIGMA * noise:
            out.append((k, b["mean"], m["mean"], (m["mean"] - b["mean"]) / noise, m.get("real")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="rookies", help="comma list of " + ", ".join(SUITES))
    ap.add_argument("--try", dest="tries", action="append", help='"module.NAME=v1,v2,..." (several make a grid)')
    ap.add_argument("--variant", action="append", help='"module.A=1;module.B=2": knobs set together')
    ap.add_argument("--targets", default="", help="comma list of measure names (default: all with a real value)")
    ap.add_argument("--leagues", type=int, default=0, help="leagues per suite (default: the scoreboard's)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    a = ap.parse_args()
    suites = [s.strip() for s in a.suites.split(",") if s.strip()]
    for s in suites:
        if s not in SUITES:
            raise SystemExit(f"unknown suite {s}: use {', '.join(SUITES)}")
    variants = variants_from(a.tries, a.variant)
    if len(variants) == 1:
        raise SystemExit("nothing to try: give --try or --variant")
    jobs = jobs_for(suites, a.leagues)
    items = [(vi, v, job) for vi, v in enumerate(variants) for job in jobs]
    print(f"{len(variants)} variants x {len(jobs)} jobs = {len(items)} jobs, {a.workers} at a time", flush=True)
    parts = defaultdict(lambda: defaultdict(list))
    with Pool(min(a.workers, len(items)), maxtasksperchild=1) as pool:
        for n, (vi, kind, part) in enumerate(pool.imap_unordered(_work, items), 1):
            parts[vi][kind].append(part)
            if n % max(1, len(items) // 10) == 0 or n == len(items):
                print(f"  {n}/{len(items)} done", flush=True)
    meas = {vi: SB.combine(parts[vi]) for vi in range(len(variants))}
    targets = [t.strip() for t in a.targets.split(",") if t.strip()] or sorted(
        k for k, m in meas[0].items() if m.get("real") is not None and not k.startswith("speed.")
        and k not in SB.MUST_BE_ZERO)
    lines = []
    say = lambda s="": lines.append(s) or print(s)  # noqa: E731
    say(f"KNOB SWEEP  suites: {', '.join(suites)}  leagues per suite: {a.leagues or 'scoreboard default'}")
    say(f"Score = average gap to the real NFL, in noise units (lower is closer; under ~1 apart is luck). "
        f"{len(targets)} targets.")
    ranked = sorted(range(len(variants)), key=lambda vi: score(meas[vi], targets)[0])
    for rank, vi in enumerate(ranked, 1):
        sc, _g = score(meas[vi], targets)
        say(f"  {rank}. score {sc:5.2f}  {variants[vi] or 'current (no change)'}")
    say()
    say("Targets, game by variant (noise) / real:")
    head = "  " + f"{'measure':48}" + "".join(f"{('v' + str(vi)):>16}" for vi in range(len(variants))) + f"{'real':>10}"
    say(head)
    for k in targets:
        row = f"  {k[:48]:48}"
        for vi in range(len(variants)):
            m = meas[vi].get(k)
            row += f"{m['mean']:>10.3f}({m['se']:.3f})" if m and m.get("mean") is not None else f"{'-':>16}"
        r = meas[0].get(k, {}).get("real")
        row += f"{r:>10.3f}" if r is not None else f"{'-':>10}"
        say(row)
    say("  (v0 = current; " + "; ".join(f"v{vi} = {v}" for vi, v in enumerate(variants) if vi) + ")")
    say()
    say("Side effects (other measures that moved from current beyond 3x the noise):")
    any_side = False
    for vi in range(1, len(variants)):
        se = side_effects(meas[vi], meas[0], set(targets))
        for k, b, m, z, r in se:
            any_side = True
            say(f"  v{vi} {k}: {b:.3f} -> {m:.3f} ({z:+.1f} x noise; real {r if r is not None else '-'})")
    if not any_side:
        say("  none")
    for k in SB.MUST_BE_ZERO:
        bad = [vi for vi in range(len(variants)) if (meas[vi].get(k) or {}).get("mean")]
        if bad:
            say(f"  must be zero: {k} = " + ", ".join(f"v{vi} {meas[vi][k]['mean']:.2f}" for vi in bad))
    OUT.mkdir(exist_ok=True)
    (OUT / "last_sweep.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "last_sweep.json").write_text(json.dumps({"variants": variants, "targets": targets,
                                                     "measures": {str(k): v for k, v in meas.items()}}, indent=1),
                                         encoding="utf-8")


if __name__ == "__main__":
    main()
