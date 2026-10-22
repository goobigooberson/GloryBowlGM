# tools/recenter.py
# Re-measures tuning.CENTER: the league-wide average of each matchup
# adjustment in the sim (completion by depth, interception, yards after
# catch, runs, returns...). Each adjustment is centered on that average so an
# AVERAGE matchup reproduces the real NFL baseline exactly and only the
# differences between players move results.
#
# When to run it: after changing anything that shifts matchup adjustments as
# a whole (the *_K knobs in tuning.py, how a skill is read in plays.py, the
# rating scale or norms, or player generation). Then run realism_check.py.
#
# Run from the project folder (about 10-20 minutes at the defaults):
#     python tools/recenter.py            (measure and show; changes nothing)
#     python tools/recenter.py --write    (also writes the new CENTER block into engine/sim/tuning.py)
#
# Method (same as calibration on Oct 19): three generated leagues (seeds 7, 9,
# 11), 500 games x 3 rounds each; interception and throwaway sites are
# multiplicative, so they're centered so the average multiplier is exactly 1.

import argparse
import math
import random
import re

import simlab
from engine.sim import plays as P
from engine.sim import tuning as T
from engine.sim.game import Game
from engine.sim.norms import build_norms

TUNING = simlab.ROOT / "engine" / "sim" / "tuning.py"


def measure(seed, games, rounds):
    league = simlab.get_league(str(seed), camp=False)
    norms = build_norms(league)
    ids = [t.id for t in league.teams]
    for rnd in range(rounds):
        P.RECORD = {}
        rng = random.Random(99 + rnd)
        for _ in range(games):
            h, a = rng.sample(ids, 2)
            Game(league, h, a, seed=rng.random(), norms=norms).run()
        for site, vals in P.RECORD.items():
            if site.startswith(("int", "throwaway")):
                T.CENTER[site] = math.log(sum(math.exp(v) for v in vals) / len(vals))
            else:
                T.CENTER[site] = sum(vals) / len(vals)
        P.RECORD = None
        print(f"  league {seed}, round {rnd + 1} done", flush=True)
    return dict(T.CENTER)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=500)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    start = dict(T.CENTER)
    results = []
    for seed in (7, 9, 11):
        T.CENTER.clear()
        T.CENTER.update(start)
        results.append(measure(seed, args.games, args.rounds))
    avg = {k: round(sum(r[k] for r in results) / len(results), 3) for k in sorted(results[0])}
    print("\nsite            old      new")
    for k, v in avg.items():
        print(f"  {k:12} {start.get(k, 0):7.3f}  {v:7.3f}")
    if args.write:
        text = TUNING.read_text(encoding="utf-8")
        block = "CENTER = {\n" + ",\n".join(f'    "{k}": {v}' for k, v in avg.items()) + ",\n}"
        new, count = re.subn(r"CENTER = \{[^}]*\}", block, text, count=1)
        if count != 1:
            raise SystemExit("Couldn't find the CENTER block in tuning.py; nothing written.")
        TUNING.write_text(new, encoding="utf-8")
        print(f"\nWrote the new CENTER block to {TUNING}")
    else:
        print("\n(Nothing written. Add --write to update engine/sim/tuning.py.)")


if __name__ == "__main__":
    main()
