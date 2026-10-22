# tools/ai_views_check.py
# How well do AI teams know the players they pay? The game vs the real NFL.
#
# Blake (Oct 22): AI teams "should not know what the real number is and should
# be guessing" (engine/evaluation.py: each staff's view of a player). Real
# teams know their own players better than other teams' players, and players
# with lots of tape better than part-timers. Measured from real data the same
# way in both:
#   every veteran market deal (1%+ of the cap, not a rookie deal), split into
#   "own" (signed by the team he played for last season: re-signings,
#   extensions, tags) and "other" (signed by a new team); his price ranked at
#   his position that year; then what he gave the signing team the next season:
#   his share of its snaps (0 if he was cut, hurt all year or didn't play).
# Real (OverTheCap contracts + PFR snap counts, 2,409 deals signed 2014-21;
# script: docs/research/real_own_vs_other.py):
#   correlation of price with snap share   own 0.46   other 0.33
#   paid like a starter (top 40% of price) but under 25% of snaps   own 12%  other 17%
#   by last season's snap share (tape):  under 30%  0.34/0.25, bust 24%/32%
#                                         30-60%    0.36/0.19, bust 14%/20%
#                                         60%+      0.22/0.27, bust 10%/12%
# If AI teams saw true ratings, the game's correlations would run too high and
# its busts too rare, mostly for other teams' players.
#
#   python tools/ai_views_check.py                       (leagues 101,102; 3 offseasons each)
#   python tools/ai_views_check.py --leagues 101,102,103,104 --seasons 3
#   python tools/ai_views_check.py --other-sd 4.5 --own-sd 1.5 --shared 0.4   (try knobs)
#   python tools/ai_views_check.py --truth                (AI teams see true ratings: the old way)
# Writes tools/ai_views_report.txt. Nothing is saved; your saves are never touched.

import argparse
import math
import random
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from engine import evaluation as E                    # noqa: E402
from engine import free_agency as FA                  # noqa: E402
from engine.league import create_league               # noqa: E402
import free_agency_check as FAC                       # noqa: E402
import simlab                                         # noqa: E402

GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OT", "G": "IOL", "C": "IOL",
         "DE": "EDGE", "DT": "IDL", "OLB": "LB", "ILB": "LB", "CB": "CB", "S": "S"}
MARKET = 0.01               # market deals only (real: 1%+ of the cap)
STARTER_PRICE = 0.6         # "paid like a starter": top 40% of price at his position that year
BUST_SHARE = 0.25
TAPE = ((0.0, 0.3), (0.3, 0.6), (0.6, 9.0))
REAL = {"corr": (0.46, 0.33), "bust": (0.12, 0.17),
        "tape": {(0.0, 0.3): (0.34, 0.25, 0.24, 0.32), (0.3, 0.6): (0.36, 0.19, 0.14, 0.20),
                 (0.6, 9.0): (0.22, 0.27, 0.10, 0.12)}}

# simlab's season result leaves out positions without box-score stats; linemen's snaps count here.
simlab.GROUP = dict(simlab.GROUP, T="OL", G="OL", C="OL", LS="LS")

out_lines = []


def say(s=""):
    print(s)
    out_lines.append(s)


def pearson(a, b):
    if len(a) < 3:
        return float("nan")
    ma, mb = st.fmean(a), st.fmean(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else float("nan")


def snap_shares(season):
    """{pid: (team, share of that team's snaps)} from simlab.play_season's result.
    A team's snaps are its busiest player's (a center or safety plays about all of them)."""
    off = defaultdict(float)
    dfn = defaultdict(float)
    for d in season["players"]:
        off[d["team"]] = max(off[d["team"]], d.get("off_snaps", 0))
        dfn[d["team"]] = max(dfn[d["team"]], d.get("def_snaps", 0))
    out = {}
    for d in season["players"]:
        t = d["team"]
        s = max(d.get("off_snaps", 0) / (off[t] or 1), d.get("def_snaps", 0) / (dfn[t] or 1))
        out[d["pid"]] = (t, min(1.0, s))
    return out


def new_stats():
    return {"legal": [], "missing": 0, "move_all": defaultdict(int), "move_exp": defaultdict(lambda: defaultdict(int)),
            "move_pos": defaultdict(lambda: defaultdict(int)), "year": defaultdict(int), "waves": defaultdict(int),
            "waves_market": defaultdict(int), "deals": [], "ladder": defaultdict(list), "spend": defaultdict(list),
            "payroll": [], "room": [], "dead": [], "seasons": 0, "gone_why": defaultdict(lambda: defaultdict(int)),
            "fa_open": []}


def run_league(seed, seasons, rows):
    lg = create_league(seed=seed)
    lg.settings["salt"] = f"ai-views-{seed}"
    lg.user_team_id = None
    FA.initial_contracts(lg)
    rng = random.Random(f"ai-views-{seed}")
    stats = new_stats()
    last = snap_shares(simlab.play_season(lg, f"ai-views-{seed}-0"))
    for k in range(seasons):
        lines = FAC.fake_season_lines(lg, rng)
        lg.team_history.extend(lines)
        n_log = len(lg.contract_log)
        FAC.offseason(lg, rng, stats, lines)
        deals = [d for d in lg.contract_log[n_log:]
                 if d["season"] == lg.season and d["kind"] not in ("rookie", "udfa", "practice")
                 and d["apy_share"] >= MARKET and d["pos"] in GROUP]
        lg.stage, lg.week = "preseason", 1
        now = snap_shares(simlab.play_season(lg, f"ai-views-{seed}-{k + 1}"))
        lg.stage, lg.week = "season_complete", 18
        seen = set()
        for d in reversed(deals):            # a player's last deal of the offseason counts
            pid = d["pid"]
            if pid in seen or pid not in last:
                continue                     # one deal per player; he must have played last season
            seen.add(pid)
            t_before, tape = last[pid]
            team, share = now.get(pid, (None, 0.0))
            rows.append({"g": GROUP[d["pos"]], "season": (seed, lg.season), "pct": d["apy_share"],
                         "own": t_before == d["team"], "tape": tape,
                         "out": share if team == d["team"] else 0.0})
        last = now
        print(f"  league {seed} offseason {k + 1}: {len(seen)} market deals")


def report(rows, label):
    by = defaultdict(list)
    for r in rows:
        by[(r["g"], r["season"])].append(r)
    for grp in by.values():
        grp.sort(key=lambda r: r["pct"])
        n = len(grp)
        for i, r in enumerate(grp):
            r["pp"] = (i + 0.5) / n
    nd = NormalDist()

    def corr(sel):
        return pearson([nd.inv_cdf(r["pp"]) for r in sel], [r["out"] for r in sel])

    def bust(sel):
        top = [r for r in sel if r["pp"] >= STARTER_PRICE]
        return (sum(r["out"] < BUST_SHARE for r in top) / len(top), len(top)) if top else (float("nan"), 0)

    own = [r for r in rows if r["own"]]
    oth = [r for r in rows if not r["own"]]
    say(f"== {label} ==")
    say(f"Market deals measured: {len(rows)} (own {len(own)}, other {len(oth)}); real 2,409 (1,263 / 1,146)")
    say(f"Mean snap share next season: own {st.fmean(r['out'] for r in own):.2f} (real 0.47), "
        f"other {st.fmean(r['out'] for r in oth):.2f} (real 0.43)")
    say("")
    say("                                       game own  real own   game other  real other")
    say(f"corr(price, snap share)                  {corr(own):5.2f}     {REAL['corr'][0]:5.2f}       "
        f"{corr(oth):5.2f}      {REAL['corr'][1]:5.2f}")
    bo, bt = bust(own), bust(oth)
    say(f"paid like a starter, <25% of snaps      {bo[0]:5.0%}     {REAL['bust'][0]:5.0%}       "
        f"{bt[0]:5.0%}      {REAL['bust'][1]:5.0%}      (n {bo[1]} / {bt[1]})")
    say("")
    say("By last season's snap share (tape)       corr own/other (real)        bust own/other (real)")
    for lo, hi in TAPE:
        o = [r for r in own if lo <= r["tape"] < hi]
        t = [r for r in oth if lo <= r["tape"] < hi]
        ro = REAL["tape"][(lo, hi)]
        name = f"{lo:.0%}-{hi:.0%}" if hi < 2 else f"{lo:.0%}+"
        say(f"  {name:<8} n {len(o):4d}/{len(t):4d}            {corr(o):5.2f}/{corr(t):5.2f} ({ro[0]:.2f}/{ro[1]:.2f})"
            f"        {bust(o)[0]:4.0%}/{bust(t)[0]:4.0%} ({ro[2]:.0%}/{ro[3]:.0%})")
    say("")
    say("By position group: corr own / other")
    for g in ("QB", "RB", "WR", "TE", "OT", "IOL", "EDGE", "IDL", "LB", "CB", "S"):
        o = [r for r in own if r["g"] == g]
        t = [r for r in oth if r["g"] == g]
        say(f"  {g:<5} {corr(o):5.2f} (n {len(o):3d})   {corr(t):5.2f} (n {len(t):3d})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--own-sd", type=float)
    ap.add_argument("--other-sd", type=float)
    ap.add_argument("--shared", type=float)
    ap.add_argument("--truth", action="store_true", help="AI teams see true ratings (the old way)")
    args = ap.parse_args()
    t0 = time.time()
    if args.own_sd is not None:
        E.OWN_SD = args.own_sd
    if args.other_sd is not None:
        E.OTHER_SD = args.other_sd
    if args.shared is not None:
        E.SHARED = args.shared
    if args.truth:
        E.seen_skills = lambda league, tid, p: dict(p.skills)
        E.public_skills = lambda league, p: dict(p.skills)
    label = ("AI teams see TRUE ratings" if args.truth else
             f"evaluation.py: OWN_SD {E.OWN_SD}, OTHER_SD {E.OTHER_SD}, SHARED {E.SHARED}, EVAL_K {E.EVAL_K}")
    rows = []
    for seed in [int(x) for x in args.leagues.split(",")]:
        run_league(seed, args.seasons, rows)
    report(rows, label)
    say(f"\n({time.time() - t0:.0f} s)")
    (ROOT / "tools" / "ai_views_report.txt").write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
