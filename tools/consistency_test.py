# tools/consistency_test.py
# Does it feel random and real, not like a formula? Replays the SAME league
# (same rosters, ratings frozen) for several seasons and measures:
#   - how much an established full-time player's numbers typically change
#     from one season to the next, vs the real NFL (median % change)
#   - examples: the same player's seasons side by side
#   - how often the highest-rated player at a position leads the league
# Note: real players also age, change teams and roles, so real numbers should
# move a little MORE than frozen sim rosters, never much less.
# Changes and saves nothing.
#
# Run from the project folder (about 30-60 seconds per season):
#     python tools/consistency_test.py
#     python tools/consistency_test.py --league saved --seasons 4

import argparse
import json
from pathlib import Path

import measures as M
import simlab

HERE = Path(__file__).resolve().parent
BENCH = json.loads((HERE / "real_nfl_benchmarks.json").read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="saved" if simlab.SAVE_FILE.exists() else "101")
    ap.add_argument("--seasons", type=int, default=4)
    args = ap.parse_args()
    league = simlab.get_league(args.league)
    norms = simlab.build_norms(league)
    ovr = {p.id: p.overall() for p in league.players}
    seasons = []
    for i in range(args.seasons):
        s = simlab.play_season(league, seed=f"consistency-{i}", norms=norms)
        seasons.append({p["pid"]: p for p in s["players"]})
        print(f"  season {i + 1} done", flush=True)

    def snaps(p):
        return p.get("off_snaps", 0) + p.get("def_snaps", 0)

    def change(stat, positions, minimum, min_snaps, pct=True, vol=None):
        out = []
        for a in range(len(seasons)):
            for b in range(a + 1, len(seasons)):
                for pid, p in seasons[a].items():
                    q = seasons[b].get(pid)
                    if q is None or p["pos"] not in positions or snaps(p) < min_snaps or snaps(q) < min_snaps:
                        continue
                    if vol:
                        if p.get(vol, 0) < minimum or q.get(vol, 0) < minimum:
                            continue
                    elif p.get(stat, 0) < minimum:
                        continue
                    if pct:
                        out.append(abs(q.get(stat, 0) - p[stat]) / p[stat])
                    else:
                        out.append(abs(q.get(stat, 0) - p.get(stat, 0)))
        return M.median(out), len(out)

    for s in seasons:
        for p in s.values():
            p["ypc"] = p.get("rush_yds", 0) / p["rush_att"] if p.get("rush_att") else 0
            p["ypa"] = p.get("pass_yds", 0) / p["pass_att"] if p.get("pass_att") else 0
            p["ypt"] = p.get("rec_yds", 0) / p["targets"] if p.get("targets") else 0
    real = BENCH["consistency"]
    print(f"\nTYPICAL CHANGE FROM ONE SEASON TO THE NEXT (league {args.league}, {args.seasons} replays, frozen ratings)")
    for label, key, stat, pos, minimum, ms, pct, vol in (
            ("WR targets (90+)", "wr_targets_pct", "targets", ("WR",), 90, 750, True, None),
            ("WR receiving yards (800+)", "wr_rec_yds_pct", "rec_yds", ("WR",), 800, 750, True, None),
            ("RB carries (180+)", "rb_carries_pct", "rush_att", ("RB",), 180, 450, True, None),
            ("QB passing yards (3000+)", "qb_pass_yds_pct", "pass_yds", ("QB",), 3000, 950, True, None),
            ("Edge sacks (7+)", "edge_sacks_pct", "sacks", ("DE", "OLB"), 7, 600, True, None),
            ("Tackles (90+)", "tackles_pct", "tackles", ("ILB", "OLB", "CB", "S", "DE", "DT"), 90, 750, True, None),
            ("RB yards per carry (150+ car)", "rb_ypc_abs", "ypc", ("RB",), 150, 0, False, "rush_att"),
            ("QB yards per attempt (350+ att)", "qb_ypa_abs", "ypa", ("QB",), 350, 0, False, "pass_att"),
            ("WR yards per target (80+ tgt)", "wr_ypt_abs", "ypt", ("WR",), 80, 0, False, "targets")):
        v, n = change(stat, pos, minimum, ms, pct, vol)
        if pct:
            print(f"  {label:34} sim {100*v:4.0f}%   real {100*real[key]:4.0f}%   (n={n})")
        else:
            print(f"  {label:34} sim {v:5.2f}   real {real[key]:5.2f}   (n={n})")

    print("\nSAME PLAYER, SAME RATINGS, EACH REPLAY")
    for pos, stat in (("QB", "pass_yds"), ("RB", "rush_yds"), ("WR", "rec_yds"), ("DE", "sacks"), ("ILB", "tackles")):
        # (Players made up and signed during a replay aren't in the league afterward: skip them.)
        best = sorted({pid for s in seasons for pid, p in s.items() if p["pos"] == pos and pid in ovr},
                      key=lambda pid: -ovr[pid])[:3]
        for pid in best:
            vals = [round(s[pid].get(stat, 0)) if pid in s else 0 for s in seasons]
            print(f"  {pos} rated {ovr[pid]:.0f}: {stat} {vals}")

    print("\nDOES THE HIGHEST-RATED PLAYER LEAD THE LEAGUE? (his finish each replay)")
    for pos, stat in (("QB", "pass_yds"), ("RB", "rush_yds"), ("WR", "rec_yds"), ("DE", "sacks"), ("ILB", "tackles")):
        ranks = []
        for s in seasons:
            group = [p for p in s.values() if p["pos"] == pos]
            if not group:
                continue
            best = max(group, key=lambda p: ovr.get(p["pid"], 0))
            order = sorted(group, key=lambda p: -p.get(stat, 0))
            ranks.append(order.index(best) + 1)
        print(f"  {pos} {stat}: {ranks}")


if __name__ == "__main__":
    main()
