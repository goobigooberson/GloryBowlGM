# tools/same_results.py
# Proves that a change gives exactly the same results as an earlier version of the game
# (Oct 25, made for the speed work: "make sure it wont compromise development accuracy").
#
# It plays the same lab leagues (tools/lab.py) on this folder's code and on an earlier
# commit's code side by side, and compares the whole league (lab.fingerprint_parts: every
# field of the league, every player with his hidden values, the shared dice) at every
# checkpoint: after creation, at week 1, at the end of each season and after every
# offseason phase. One differing checkpoint and it names the first one and which parts
# differ. It also prints each side's CPU time (both run at the same time, so they see
# the same load from other programs).
#
#   python tools/same_results.py                         # against main: seeds 101 202 303, 1 season, fast games
#   python tools/same_results.py --ref 8e2eea9 --seasons 3
#   python tools/same_results.py --games real --seeds 101 --seasons 2
#
# The earlier code is unpacked with `git archive` into a temporary folder (deleted after);
# nothing in this folder changes. Both sides use THIS folder's fingerprint code, so a
# newer, stricter fingerprint also checks the old code.

import argparse
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fingerprint_module():
    """This folder's lab.py fingerprint code, loaded under its own name (the code being
    checked is imported as `lab` from its own folder)."""
    spec = importlib.util.spec_from_file_location("same_results_fp", ROOT / "tools" / "lab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def worker(root, seed, seasons, games, out):
    """Play one lab league on the code in root; write its checkpoints and CPU times."""
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(Path(root) / "tools"))
    from lab import Lab              # first: the engine checked is the one in root
    fp = _fingerprint_module()
    cps, cpu = [], {"fingerprint": 0.0}
    clock = time.process_time
    mark = [clock()]

    def tick(part):
        now = clock()
        cpu[part] = cpu.get(part, 0.0) + now - mark[0]
        mark[0] = now

    def cp(label):
        t = clock()
        cps.append([label, fp.fingerprint_parts(lab.league)])
        cpu["fingerprint"] += clock() - t
        mark[0] = clock()

    lab = Lab(seed, games)
    tick("create")
    cp("created")
    lab.on("week_end", lambda lab, label: tick("season"))
    lab.on("regular_season", lambda lab: cp(f"{lab.league.season} week 1"))
    lab.on("season_end", lambda lab: (tick("season"), cp(f"{lab.league.season} season over")))
    lab.on("offseason_start", lambda lab: (tick("offseason"), cp("offseason start")))
    lab.on("phase_after", lambda lab, phase, wave: (tick("offseason"),
                                                     cp(f"{lab.league.season} {phase} {wave or ''}".strip())))
    lab.run(seasons=seasons)
    Path(out).write_text(json.dumps({"cps": cps, "cpu": cpu}))


def compare(a, b):
    """(first differing checkpoint and parts, or None; checkpoints compared)."""
    for (la, pa), (lb, pb) in zip(a["cps"], b["cps"]):
        if la != lb or pa != pb:
            return f"{la}: {sorted(k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k))}", len(a["cps"])
    if len(a["cps"]) != len(b["cps"]):
        return f"{len(a['cps'])} checkpoints vs {len(b['cps'])}", len(a["cps"])
    return None, len(a["cps"])


def main():
    ap = argparse.ArgumentParser(description="Same lab leagues on an earlier commit and on this folder: "
                                             "identical results, and CPU time.")
    ap.add_argument("--ref", default="main", help="the earlier version (a commit, branch or tag; default main)")
    ap.add_argument("--seeds", type=int, nargs="+", default=[101, 202, 303])
    ap.add_argument("--seasons", type=int, default=1)
    ap.add_argument("--games", choices=("fast", "real"), default="fast")
    ap.add_argument("--worker", nargs=5, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.worker:
        root, seed, seasons, games, out = a.worker
        worker(root, int(seed), int(seasons), games, out)
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        old = Path(tmp) / "old"
        old.mkdir()
        archive = subprocess.run(["git", "archive", a.ref, "engine", "tools/lab.py"], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(old, filter="data")
        print(f"{a.ref} vs this folder: seeds {a.seeds}, {a.seasons} season(s), {a.games} games")
        procs = []
        for seed in a.seeds:
            for side, root in (("old", old), ("new", ROOT)):
                out = Path(tmp) / f"{side}-{seed}.json"
                procs.append((seed, side, out, subprocess.Popen(
                    [sys.executable, __file__, "--worker", str(root), str(seed), str(a.seasons), a.games,
                     str(out)], env=env)))
        for *_x, proc in procs:
            proc.wait()
        bad = 0
        for seed in a.seeds:
            res = {side: json.loads(out.read_text()) for s, side, out, _p in procs if s == seed}
            diff, n = compare(res["old"], res["new"])
            cpu = {side: sum(v for k, v in r["cpu"].items() if k != "fingerprint") for side, r in res.items()}
            parts = len(res["new"]["cps"][0][1])
            print(f"  seed {seed}: {'IDENTICAL' if diff is None else 'DIFFERENT at ' + diff} "
                  f"({n} checkpoints x {parts} parts); CPU {cpu['old']:.1f}s -> {cpu['new']:.1f}s "
                  f"({cpu['old'] / max(cpu['new'], 1e-9):.2f}x)")
            bad += diff is not None
        print("Same results." if not bad else f"{bad} league(s) came out differently.")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
