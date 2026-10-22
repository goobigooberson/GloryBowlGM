# tools/team_sport_test.py
# Is it a team sport? Two controlled experiments (Blake's FOF8 test):
#
# 1. Supporting cast: build a truly stacked offense around one team (the
#    league's best starter at every OL, WR1-3, TE and RB spot moved onto it),
#    an average one (as generated) and a truly weak one (the league's worst
#    starters), keep the defense the same, then drop in the same QB or RB and
#    play the same opponents. A below-average QB should put up good numbers
#    and win with a stacked cast.
# 2. Great QB, bad roster: a realistically bad team (the 26th-best starter of
#    32 at every spot, offense and defense) with an average QB, the league's
#    best QB, and a generated Generational QB. Great QBs should make a bad
#    team competitive.
#
# Changes and saves nothing (works on copies).
# Run from the project folder (several minutes):
#     python tools/team_sport_test.py
#     python tools/team_sport_test.py --league saved --games 160
# Reference results (Oct 19, league 101, 160-200 games each; exact numbers vary by league
# and need 150+ games per test to settle):
#   below-average QB (64): stacked 97.8 rating / 9.5 wins, average 94.4 / 7.3, weak 74.2 / 2.2
#   best QB (93): stacked 117.8 / 13.8, average 114.4 / 11.4, weak 92.5 / 6.6
#   below-average RB (66): 4.65 YPC stacked, 4.19 average, 3.64 weak
#   bad roster: average QB 4.0 wins, best QB 7.9, Generational QB 8.6
#   weak-cast sacks should stay under the NFL record (76): was 67

import argparse
import copy
import random

import simlab
from engine.player import generate_player
from engine.sim.game import Game
from engine.sim.norms import build_norms
from engine.sim.stats import passer_rating

OL = ("LT", "LG", "C", "RG", "RT")
REC = ("WR1", "WR2", "WR3", "TE1")
DEF = ("LE", "LDT", "RDT", "RE", "WLB", "MLB", "SLB", "CB1", "CB2", "NB", "FS", "SS")


class Lab:
    def __init__(self, league):
        self.base = league
        self.ids = [t.id for t in league.teams]
        self.target = self.ids[3]

    def P(self, lg):
        return {p.id: p for p in lg.players}

    def starter(self, lg, tid, slot, P=None):
        P = P or self.P(lg)
        lst = lg.depth_charts[tid].get(slot, [])
        return P.get(lst[0]) if lst else None

    def avg(self, lg, tid, slots):
        P = self.P(lg)
        v = [self.starter(lg, tid, s, P).overall() for s in slots if self.starter(lg, tid, s, P)]
        return sum(v) / len(v)

    def place(self, lg, pid, slot, tid):
        """Make player pid the starter at slot for team tid (swapping teams with that starter)."""
        old_tid = lg.rosters[pid]
        cur = lg.depth_charts[tid][slot][0]
        if cur == pid:
            return
        lg.rosters[pid], lg.rosters[cur] = tid, old_tid
        for t, a, b in ((tid, cur, pid), (old_tid, pid, cur)):
            ch = lg.depth_charts[t]
            for s, lst in ch.items():
                ch[s] = [b if x == a else x for x in lst]

    def build_cast(self, lg, best):
        """Move the league's best (or worst) starter at each offensive spot onto the target team."""
        for slot in OL + REC + ("RB",):
            P = self.P(lg)
            cands = [self.starter(lg, t, slot, P) for t in self.ids if t != self.target]
            cands = [p for p in cands if p is not None]
            pick = max(cands, key=lambda p: p.overall()) if best else min(cands, key=lambda p: p.overall())
            if (self.starter(lg, self.target, slot, P).overall() < pick.overall()) == best:
                self.place(lg, pick.id, slot, self.target)

    def bad_roster(self, lg, rank=26):
        for slot in ("RB",) + OL + REC + DEF:
            P = self.P(lg)
            cands = sorted([self.starter(lg, t, slot, P) for t in self.ids if self.starter(lg, t, slot, P)],
                           key=lambda p: -p.overall())
            pick = cands[rank - 1]
            if pick.id != self.starter(lg, self.target, slot, P).id and lg.rosters[pick.id] != self.target:
                self.place(lg, pick.id, slot, self.target)

    def run(self, lg, pid, n, seed=7):
        norms = build_norms(lg)
        rng = random.Random(seed)
        others = [t for t in self.ids if t != self.target]
        tot = dict(att=0, cmp=0, yds=0, td=0, it=0, sacked=0, car=0, ryds=0, rtd=0, pts=0, opp=0, w=0)
        for i in range(n):
            opp = others[i % len(others)]
            home, away = (self.target, opp) if i % 2 == 0 else (opp, self.target)
            g = Game(lg, home, away, seed=rng.random(), norms=norms).run()
            me = 0 if home == self.target else 1
            line = g.box.players.get(pid, {})
            for k, kk in (("att", "pass_att"), ("cmp", "pass_cmp"), ("yds", "pass_yds"), ("td", "pass_td"),
                          ("it", "pass_int"), ("sacked", "sacked"), ("car", "rush_att"), ("ryds", "rush_yds"),
                          ("rtd", "rush_td")):
                tot[k] += line.get(kk, 0)
            pf, pa = g.state.score[me], g.state.score[1 - me]
            tot["pts"] += pf
            tot["opp"] += pa
            tot["w"] += 1 if pf > pa else (0.5 if pf == pa else 0)
        return tot


def qb_line(t, n):
    f = 17 / n
    return (f"{t['yds']*f:5.0f} yds {100*t['cmp']/max(1,t['att']):4.1f}% {t['yds']/max(1,t['att']):4.1f} YPA "
            f"{t['td']*f:4.1f} TD {t['it']*f:4.1f} INT sacks {t['sacked']*f:4.1f} "
            f"rating {passer_rating(t['att'], t['cmp'], t['yds'], t['td'], t['it']):5.1f} | "
            f"team {t['pts']/n:4.1f}-{t['opp']/n:4.1f}, wins per 17: {17*t['w']/n:4.1f}")


def rb_line(t, n):
    f = 17 / n
    return (f"{t['ryds']*f:5.0f} yds {t['car']*f:4.0f} car {t['ryds']/max(1,t['car']):4.2f} YPC {t['rtd']*f:4.1f} TD | "
            f"team {t['pts']/n:4.1f}-{t['opp']/n:4.1f}, wins per 17: {17*t['w']/n:4.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="101")
    ap.add_argument("--games", type=int, default=160)
    args = ap.parse_args()
    base = simlab.get_league(args.league, camp=False)
    lab = Lab(base)
    n = args.games
    P = lab.P(base)
    qbs = sorted([lab.starter(base, t, "QB", P) for t in lab.ids], key=lambda p: p.overall())
    rbs = sorted([lab.starter(base, t, "RB", P) for t in lab.ids], key=lambda p: p.overall())
    weak_qb, best_qb, avg_qb, weak_rb = qbs[6], qbs[-1], qbs[15], rbs[6]

    print(f"League {args.league}, {n} games per test, same opponents. Per-17-game pace.\n")
    print("1) SAME PLAYER, DIFFERENT SUPPORTING CAST (defense unchanged)")
    casts = {}
    for name, flag in (("stacked", True), ("average", None), ("weak", False)):
        lg = copy.deepcopy(base)
        if flag is not None:
            lab.build_cast(lg, flag)
        casts[name] = lg
        print(f"   {name:8} cast: OL {lab.avg(lg, lab.target, OL):.0f}, receivers {lab.avg(lg, lab.target, REC):.0f}, "
              f"RB {lab.avg(lg, lab.target, ('RB',)):.0f}")
    for label, player, slot, fmt in ((f"Below-average QB ({weak_qb.overall():.0f})", weak_qb, "QB", qb_line),
                                     (f"Best QB in league ({best_qb.overall():.0f})", best_qb, "QB", qb_line),
                                     (f"Below-average RB ({weak_rb.overall():.0f})", weak_rb, "RB", rb_line)):
        print(f"\n   {label}")
        for name, lg0 in casts.items():
            lg = copy.deepcopy(lg0)
            lab.place(lg, player.id, slot, lab.target)
            print(f"     {name:8}: {fmt(lab.run(lg, player.id, n), n)}")

    print("\n2) GREAT QB, BAD ROSTER (26th-best starter of 32 at every spot)")
    random.seed(4)
    gen = None
    for i in range(40):
        g = generate_player("QB", experience=6, generational=True, rng_seed=100 + i)
        if gen is None or g.overall() > gen.overall():
            gen = g
    for label, qb, new in ((f"Average starting QB ({avg_qb.overall():.0f})", avg_qb, False),
                           (f"Best QB in league ({best_qb.overall():.0f})", best_qb, False),
                           (f"Generational QB ({gen.overall():.0f})", gen, True)):
        lg = copy.deepcopy(base)
        lab.bad_roster(lg)
        if new:
            q = copy.deepcopy(qb)
            q.id = max(p.id for p in lg.players) + 1
            lg.players.append(q)
            old = lab.starter(lg, lab.target, "QB").id
            lg.rosters[q.id] = lab.target
            del lg.rosters[old]
            for s, lst in lg.depth_charts[lab.target].items():
                lg.depth_charts[lab.target][s] = [q.id if x == old else x for x in lst]
            pid = q.id
        else:
            lab.place(lg, qb.id, "QB", lab.target)
            pid = qb.id
        print(f"   {label:28} {qb_line(lab.run(lg, pid, n, seed=9), n)}")


if __name__ == "__main__":
    main()
