# tools/playcall_check.py
# Is calling your own plays balanced? A bot "user" calls one team's plays in
# every regular-season game of lab leagues (tools/lab.py, the real game sim),
# with a simple fixed strategy, and the bot's teams' results are compared
# with the coordinators' own calls (strategy "coach", which plays exactly the
# same games as no one calling plays).
#
# The bot's side in each game alternates home/away by game id, so home field
# cancels out. Teams are whatever the league drew, so the comparison is the
# bot's average point margin per game against the "coach" run on the same
# league seeds.
#
#   python tools/playcall_check.py                          # every strategy, 6 leagues
#   python tools/playcall_check.py --strategies coach,always_run --leagues 4
#   python tools/playcall_check.py --set READ_PASS_SEP=1.5  # try a knob (engine/sim/tuning.py)
#
# Writes tools/playcall_report.txt (and .json).

import argparse
import json
import math
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import season as SEASON          # noqa: E402
from engine.sim import coach                 # noqa: E402
from engine.sim import tuning as TUNING      # noqa: E402

RUNS = ("run_inside", "run_outside")
PASSES = ("pass_short", "pass_medium", "pass_long", "screen", "play_action")


def _pick(rng, seq):
    return seq[int(rng.random() * len(seq))]


def make_strategy(name, seed):
    """A bot caller: fn(game, team index, kind, suggested) -> menu key or None (the staff's
    call). Offense bots leave defense, 4th downs and two-point tries to the staff and vice
    versa. Its own dice, so the game's dice are only used by the sim itself."""
    rng = random.Random(f"bot-{name}-{seed}")

    def offense(fn):
        return lambda g, i, kind, sug: fn(g, sug) if kind == "offense" else None

    def defense(fn):
        return lambda g, i, kind, sug: fn(g, sug) if kind == "defense" else None

    def pass_early(g, sug):
        # The "analytics" fan: half of the coach's 1st/2nd-down runs become passes.
        if sug in RUNS and g.state.down <= 2 and rng.random() < 0.5:
            return _pick(rng, ("pass_short", "pass_medium", "play_action"))
        return None

    def run_more(g, sug):
        # The old-school fan: half of the coach's 1st/2nd-down passes become runs.
        if sug in PASSES and g.state.down <= 2 and rng.random() < 0.5:
            return _pick(rng, RUNS)
        return None

    def situational(g, sug):
        # A plausible human: run on short yardage, pass on 3rd and long, play action on 1st
        # and 10, otherwise the coach.
        st = g.state
        if st.togo <= 2:
            return _pick(rng, ("run_inside", "run_inside", "sneak")) if st.togo <= 1 else "run_inside"
        if st.down >= 3 and st.togo >= 7:
            return _pick(rng, ("pass_medium", "pass_long"))
        if st.down == 1 and st.togo == 10 and rng.random() < 0.5:
            return "play_action"
        return None

    def best_fit(g, sug):
        # Always the play in the coach's run/pass group that suits the coordinator best.
        from engine.sim import playcalling
        fit = playcalling.fit_offense(g.teams[g.state.poss])
        group = RUNS if sug in RUNS + ("sneak",) else PASSES
        return max(group, key=lambda k: fit.get(k, 0.0)) if fit else None

    def fourth_go(g, i, kind, sug):
        # Goes for it on 4th and 4 or less wherever the coach would punt or kick.
        if kind == "fourth" and sug in ("punt", "field_goal") and g.state.togo <= 4:
            return _pick(rng, ("run_inside", "pass_short", "pass_medium"))
        return None

    def coach_after_one(g, i, kind, sug):
        # One call of its own on each side at the start of every game (so the other side reads
        # it from then on), then always the staff's call: reading must not cost it anything.
        done = g.__dict__.setdefault("_bot_done", set())
        side = "def" if kind == "defense" else ("off" if kind == "offense" else None)
        if side is None or side in done:
            return None
        done.add(side)
        menu = tuple(coach.DEF_MENU) if side == "def" else RUNS + PASSES
        return _pick(rng, tuple(k for k in menu if k != sug))

    table = {
        "coach": lambda g, i, kind, sug: None,
        "coach_after_one": coach_after_one,
        "always_run": offense(lambda g, sug: _pick(rng, RUNS)),
        "always_pass": offense(lambda g, sug: sug if sug in PASSES
                               else _pick(rng, ("pass_short", "pass_medium", "pass_medium", "play_action"))),
        "always_deep": offense(lambda g, sug: "pass_long"),
        "always_short": offense(lambda g, sug: "pass_short"),
        "always_pa": offense(lambda g, sug: "play_action"),
        "always_screen": offense(lambda g, sug: "screen"),
        "random": offense(lambda g, sug: _pick(rng, RUNS + PASSES)),
        "pass_early": offense(pass_early),
        "run_more": offense(run_more),
        "situational": offense(situational),
        "best_fit": offense(best_fit),
        "fourth_go": fourth_go,
        "d_zone": defense(lambda g, sug: "zone"),
        "d_man": defense(lambda g, sug: "man"),
        "d_blitz": defense(lambda g, sug: _pick(rng, coach.BLITZ_CHOICES)),
        "d_all_out": defense(lambda g, sug: "all_out"),
        "d_run_stop": defense(lambda g, sug: "run_stop"),
        "d_prevent": defense(lambda g, sug: "prevent"),
        "d_random": defense(lambda g, sug: _pick(rng, tuple(coach.DEF_MENU))),
    }
    return table[name]


STRATEGIES = ("coach", "coach_after_one", "always_run", "always_pass", "always_deep", "always_short", "always_pa",
              "always_screen", "random", "pass_early", "run_more", "situational", "best_fit", "fourth_go",
              "d_zone", "d_man", "d_blitz", "d_all_out", "d_run_stop", "d_prevent", "d_random")


def run_one(job):
    strategy, seed, knobs = job
    for k, v in knobs.items():
        setattr(TUNING, k, v)
    from lab import Lab
    t0 = time.process_time()
    lab = Lab(seed, games="real")
    probe = float(strategy.split(":")[1]) if strategy.startswith("probe:") else None
    caller = make_strategy("coach" if probe is not None else strategy, seed)
    rows = []
    original = SEASON.new_game

    def new_game(league, g, norms=None):
        game = original(league, g, norms)
        if SEASON.in_regular_season(league) and not SEASON.is_preseason_game(g):
            side = g["id"] % 2 if isinstance(g["id"], int) else hash(str(g["id"])) % 2
            game.callers[side] = caller
            game._bot_side = side
            if probe is not None:
                # "probe:X": the coordinators' own calls, but every offensive play of the bot's side
                # gets read X (what a read is worth in yards, for setting the READ_* knobs).
                def called(off_idx, def_idx, off, deff, call, dcall, side=side):
                    if off_idx == side and call.kind in ("run", "pass", "sneak") and call.concept != "hail_mary":
                        call.read = probe
                    return
                    yield
                game._called_plays = called
            rows.append(game)
        return game

    # The reads the bot's plays got (offense: by run/pass; defense: the offense's edge).
    from engine.sim import playcalling
    reads = {"run": [], "pass": [], "def": []}
    off_edge, def_edge = playcalling.Book.offense_edge, playcalling.Book.defense_edge

    def offense_edge(self, state, odds, choice):
        e = off_edge(self, state, odds, choice)
        reads[playcalling.OFF_GROUP[choice]].append(e)
        return e

    def defense_edge(self, state, odds, choice):
        e = def_edge(self, state, odds, choice)
        reads["def"].append(e)
        return e
    playcalling.Book.offense_edge, playcalling.Book.defense_edge = offense_edge, defense_edge

    SEASON.new_game = new_game
    try:
        lab.play_season(until="week1")
        lg = lab.league
        while SEASON.in_regular_season(lg) and not SEASON.season_over(lg):
            SEASON.play_week(lg)
            if not SEASON.in_regular_season(lg):
                break
    finally:
        SEASON.new_game = original
    out = []
    for game in rows:
        if not game.finished:
            continue
        b = game._bot_side
        bx = game.box.team
        out.append({"margin": game.state.score[b] - game.state.score[1 - b],
                    "pf": game.state.score[b], "pa": game.state.score[1 - b],
                    "plays": bx[b]["plays"], "yds": bx[b]["total_yds"],
                    "pass_att": bx[b]["pass_att"], "rush_att": bx[b]["rush_att"],
                    "to": bx[b]["int_thrown"] + bx[b]["fum_lost"], "sacked": bx[b]["sacked"],
                    "pass_net": bx[b]["pass_yds"] - bx[b]["sacked_yds"], "rush_yds": bx[b]["rush_yds"],
                    "opp_yds": bx[1 - b]["total_yds"], "opp_plays": bx[1 - b]["plays"]})
    if out:
        out[0]["reads"] = {k: (sum(v), len(v)) for k, v in reads.items()}
    return strategy, seed, out, time.process_time() - t0


def summarize(rows):
    n = len(rows)
    if not n:
        return {}
    m = [r["margin"] for r in rows]
    mean = sum(m) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in m) / max(1, n - 1))

    def tot(k):
        return sum(r[k] for r in rows)
    rd = {}
    for r in rows:
        for k, (s, c) in r.get("reads", {}).items():
            a = rd.setdefault(k, [0.0, 0])
            a[0] += s
            a[1] += c
    reads = {k: (s / c if c else 0.0) for k, (s, c) in rd.items()}
    return {"games": n, "read_run": reads.get("run", 0.0), "read_pass": reads.get("pass", 0.0),
            "read_def": reads.get("def", 0.0), "margin": mean, "se": sd / math.sqrt(n), "pf": tot("pf") / n, "pa": tot("pa") / n,
            "ypp": tot("yds") / max(1, tot("plays")),
            "pass_rate": tot("pass_att") / max(1, tot("pass_att") + tot("rush_att")),
            "to": tot("to") / n, "sacked": tot("sacked") / n, "plays": tot("plays") / n,
            "pass_ypp": tot("pass_net") / max(1, tot("pass_att") + tot("sacked")),
            "rush_ypc": tot("rush_yds") / max(1, tot("rush_att")),
            "opp_ypp": tot("opp_yds") / max(1, tot("opp_plays"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default=",".join(STRATEGIES))
    ap.add_argument("--leagues", type=int, default=6)
    ap.add_argument("--seed0", type=int, default=501)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--set", action="append", default=[], help="NAME=value, a knob in engine/sim/tuning.py")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "playcall_report.txt"))
    a = ap.parse_args()
    knobs = {}
    for kv in a.set:
        k, v = kv.split("=")
        assert hasattr(TUNING, k), k
        knobs[k] = float(v)
    strategies = a.strategies.split(",")
    seeds = [a.seed0 + k for k in range(a.leagues)]
    jobs = [(s, seed, knobs) for seed in seeds for s in strategies]
    t0 = time.time()
    results = {s: [] for s in strategies}
    with Pool(min(a.workers, len(jobs)), maxtasksperchild=1) as pool:
        for strategy, seed, rows, cpu in pool.imap_unordered(run_one, jobs):
            results[strategy].extend(rows)
            print(f"  {strategy} league {seed}: {len(rows)} games, {cpu:.0f}s cpu", flush=True)
    base = summarize(results.get("coach", []))
    lines = [f"Play-calling balance: {a.leagues} lab leagues x 1 regular season, the bot calls one side of every game",
             f"(seeds {seeds[0]}-{seeds[-1]}; {time.time() - t0:.0f} s)" + (f"; knobs {knobs}" if knobs else ""), "",
             f"{'strategy':14s} {'games':>5s} {'margin':>7s} {'+-se':>5s} {'vs coach':>8s} {'pts for':>7s} {'pts vs':>6s} "
             f"{'yds/play':>8s} {'pass %':>6s} {'TO':>5s} {'sacked':>6s} {'plays':>5s} {'pass ypp':>8s} {'rush ypc':>8s} "
             f"{'opp ypp':>7s} {'read run':>8s} {'read pass':>9s} {'read def':>8s}"]
    summary = {"knobs": knobs}
    for s in strategies:
        r = summarize(results[s])
        summary[s] = r
        if not r:
            continue
        vs = r["margin"] - base["margin"] if base else float("nan")
        lines.append(f"{s:14s} {r['games']:5d} {r['margin']:+7.2f} {r['se']:5.2f} {vs:+8.2f} {r['pf']:7.1f} {r['pa']:6.1f} "
                     f"{r['ypp']:8.2f} {100 * r['pass_rate']:6.1f} {r['to']:5.2f} {r['sacked']:6.2f} {r['plays']:5.1f} "
                     f"{r['pass_ypp']:8.2f} {r['rush_ypc']:8.2f} {r['opp_ypp']:7.2f} {r['read_run']:+8.3f} "
                     f"{r['read_pass']:+9.3f} {r['read_def']:+8.3f}")
    lines += ["", "vs coach = the bot's point margin a game minus the coordinators' own calls' (same leagues);",
              "pass ypp = net yards per dropback (sacks included); opp ypp = the opponent's yards per play;",
              "read = average edge on the bot's plays once it's being read (- = the other side expects it;",
              "read def = the opposing offense's edge from reading the bot's defense)."]
    text = "\n".join(lines)
    print(text)
    Path(a.out).write_text(text + "\n", encoding="utf-8", newline="\n")
    Path(a.out).with_suffix(".json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
