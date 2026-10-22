# tools/injury_careers_real.py
# What a serious injury does to a real NFL career, beyond normal turnover.
# Real players with a season-ending injury (2013-2024, not 2020-21's reserve
# data) are compared with uninjured players at the same position group,
# career stage and role (how much they played):
#   back       share who play the next season (injured vs matched uninjured)
#   share +1   change in his share of snaps per game played, next season vs
#              the injury season (returners), minus the matched players' change
#   share +2   the same two seasons later
# Season-ending = hurt in weeks 1-14, missed the rest of the season (see
# injury_data.episodes_all). The body part comes from the weekly reports;
# injuries that went straight to injured reserve have no body part and are
# grouped as "unknown (straight to IR)".
#
# Run from the project folder:  python tools/injury_careers_real.py

import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aging_curves import rows, num, GROUP, load_people  # noqa: E402
import injury_data  # noqa: E402

POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR/TE", "TE": "WR/TE", "T": "OL", "G": "OL", "C": "OL",
             "DE": "DL", "DT": "DL", "LB": "LB", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB"}
INJ_GROUP = {"knee": "knee", "achilles": "achilles", "foot": "foot", "shoulder": "shoulder",
             "ankle": "other lower body", "hamstring": "other lower body", "calf": "other lower body",
             "quad": "other lower body", "hip": "other lower body", "groin": "other lower body",
             "not on a report": "unknown (straight to IR)"}


def season_shares():
    """{(pfr id, season): (position group, season number, share per game played, games)}."""
    by_pfr, _g, by_name = load_people()
    out = {}
    for year in range(2013, 2026):
        acc = defaultdict(lambda: [0.0, 0, None, None])
        for r in rows(f"snap_counts_{year}.csv.gz"):
            if r["game_type"] != "REG":
                continue
            grp = GROUP.get(r["position"])
            if grp not in POS_GROUP:
                continue
            pct = num(r["offense_pct"]) if grp in ("QB", "RB", "FB", "WR", "TE", "T", "G", "C") else num(r["defense_pct"])
            a = acc[r["pfr_player_id"]]
            if pct > 0:
                a[0] += pct
                a[1] += 1
            a[2], a[3] = grp, r["player"]
        for pid, (tot, games, grp, name) in acc.items():
            info = by_pfr.get(pid) or by_name.get((name, year))
            if not info or not games:
                continue
            out[(pid, year)] = (POS_GROUP[grp], year - info["rookie"] + 1, tot / games, games)
    return out


def main():
    shares = season_shares()
    gsis_to_pfr = {}
    for year in range(2012, 2026):
        for r in rows(f"roster_{year}.csv.gz"):
            if r.get("gsis_id") and r.get("pfr_id"):
                gsis_to_pfr[r["gsis_id"]] = r["pfr_id"]
    # Season-ending injuries, with the player's pfr id: re-run the episode finder
    # keeping ids (injury_data.episodes_all drops them).
    eps = injury_data.episodes_all(with_ids=True)
    hurt = {}                                   # (pfr id, season) -> injury group
    for year, wk, part, missed, left, pid in eps:
        if missed is None and wk <= 14 and left >= 3:
            hurt[(pid, year)] = INJ_GROUP.get(part, "other")
    any_long = {(pid, y) for y, wk, part, m, left, pid in eps if m is None or (m and m >= 4)}

    def bucket(sn, share):
        return (min(sn, 10) // 2, round(share * 4) / 4)

    # Matched uninjured: same position group, season-number band, share band.
    ctrl = defaultdict(lambda: [0, 0, [], []])
    for (pid, y), (pg, sn, sh, g) in shares.items():
        if y > 2024 or y in (2019, 2020) or (pid, y) in any_long or sh < 0.3 or g < 6:
            continue
        c = ctrl[(pg,) + bucket(sn, sh)]
        c[0] += 1
        nxt = shares.get((pid, y + 1))
        if nxt:
            c[1] += 1
            c[2].append(nxt[2] - sh)
            nx2 = shares.get((pid, y + 2))
            if nx2:
                c[3].append(nx2[2] - sh)
    res = defaultdict(lambda: {"n": 0, "back": 0, "exp_back": 0.0, "d1": [], "e1": [], "d2": [], "e2": []})
    for (pid, y), ig in hurt.items():
        if y > 2024 or y in (2019, 2020):
            continue
        cur = shares.get((pid, y))
        if not cur or cur[2] < 0.3:
            continue
        pg, sn, sh, g = cur
        c = ctrl.get((pg,) + bucket(sn, sh))
        if not c or c[0] < 15:
            continue
        for key in ((ig, pg), (ig, "all"), ("all season-ending", pg)):
            r = res[key]
            r["n"] += 1
            r["exp_back"] += c[1] / c[0]
            nxt = shares.get((pid, y + 1))
            if nxt:
                r["back"] += 1
                r["d1"].append(nxt[2] - sh)
                r["e1"].append(mean(c[2]) if c[2] else 0)
                nx2 = shares.get((pid, y + 2))
                if nx2:
                    r["d2"].append(nx2[2] - sh)
                    r["e2"].append(mean(c[3]) if c[3] else 0)
    print("Real NFL season-ending injuries vs matched uninjured players (share = snaps per game played)")
    print(f"{'injury':26}{'pos':7}{'n':>5}{'back':>7}{'matched':>9}{'share +1':>10}{'share +2':>10}")
    order = ["all season-ending", "knee", "achilles", "foot", "shoulder", "other lower body",
             "unknown (straight to IR)", "other"]
    for ig in order:
        for pg in ["all", "QB", "RB", "WR/TE", "OL", "DL", "LB", "DB"]:
            r = res.get((ig, pg))
            if not r or r["n"] < 12:
                continue
            d1 = mean(a - b for a, b in zip(r["d1"], r["e1"])) if r["d1"] else 0
            d2 = mean(a - b for a, b in zip(r["d2"], r["e2"])) if r["d2"] else 0
            print(f"{ig:26}{pg:7}{r['n']:5}{100 * r['back'] / r['n']:6.0f}%{100 * r['exp_back'] / r['n']:8.0f}%"
                  f"{100 * d1:+9.1f}pt{100 * d2:+9.1f}pt" + ("" if len(r["d2"]) >= 10 else "  (few)"))


if __name__ == "__main__":
    main()
