# tools/finance_check.py
# Team finances vs the real NFL (Oct 26; engine/finances.py).
#
# Plays lab leagues (tools/lab.py: the game's own season and offseason, fast
# games) for several seasons and measures every team's closed books against the
# real numbers in docs/research/real_finance.json (docs/research/finance_research.py):
#   - revenue per team (as a share of that season's cap, so years compare): average,
#     spread, lowest, highest; local revenue's spread; where the money comes from;
#   - profit: average, middle, spread, lowest, highest; cash paid to players;
#   - ticket prices: spread across teams, the yearly change (and how often a team cuts);
#   - attendance: the average crowd, the spread across teams, how full stadiums are,
#     the yearly change, and how the crowd follows winning (this season, last season);
#   - franchise values; the owner's money view of each team.
#
#   python tools/finance_check.py                       (leagues 101,102,103; 5 seasons)
#   python tools/finance_check.py --leagues 101 --seasons 3
# Writes tools/finance_report.txt. Nothing is saved; your saves are never touched.

import argparse
import json
import statistics as st
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "docs" / "research"))

REAL = json.loads((ROOT / "docs" / "research" / "real_finance.json").read_text())
PUB = REAL["published"]


def play(args):
    seed, seasons = args
    from lab import Lab
    from engine import contracts as C, finances as F
    lab = Lab(seed)
    rows = []

    def closed(lab, **_):
        L = lab.league
        S = L.season - 1
        books = L.finances["books"].get(S)
        if not books:
            return
        hist = {(r["team"], r["season"]): r for r in L.team_history}
        champ = L.champions.get(S)
        for t in L.teams:
            b = dict(books[t.id])
            r = hist.get((t.id, S), {})
            p = hist.get((t.id, S - 1))
            g = r.get("w", 0) + r.get("l", 0) + r.get("t", 0)
            b.update({"seed": seed, "season": S, "team": t.id, "cap": C.cap_for(L, S),
                      "wp": (r.get("w", 0) + 0.5 * r.get("t", 0)) / g if g else 0.5,
                      "wp_last": ((p["w"] + 0.5 * p["t"]) / max(1, p["w"] + p["l"] + p["t"])) if p else None,
                      "po_last": bool(p and p.get("seed")), "champ": champ == t.id,
                      "money": F.owner_money_factor(L, t.id)[0],
                      "capacity": F.stadium(L, t.id)["capacity"], "age": F.stadium_age(L, t.id, S),
                      "market": F.team(L, t.id)["market"], "brand": F.team(L, t.id)["brand"]})
            rows.append(b)
    lab.on("offseason_start", closed)
    lab.run(seasons=seasons)
    return rows


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]


def ols(X, y):
    from finance_research import ols as _ols
    return _ols(X, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102,103")
    ap.add_argument("--seasons", type=int, default=5)
    a = ap.parse_args()
    t0 = time.time()
    seeds = [int(x) for x in a.leagues.split(",")]
    with Pool(min(len(seeds), 8)) as pool:
        rows = [r for part in pool.map(play, [(s, a.seasons) for s in seeds]) for r in part]
    out = []

    def line(name, game, real, note=""):
        out.append(f"  {name:<44} {game:>22}   {real:>22}   {note}")

    def head(text):
        out.append("")
        out.append(text)
        out.append(f"  {'':<44} {'game':>22}   {'real':>22}")

    def stats(v, k=1.0, fmt="{:.2f}"):
        return f"{fmt.format(st.mean(v) * k)} (sd {fmt.format(st.pstdev(v) * k)})"

    def x(r, key):
        return r[key] / r["cap"]

    f24 = PUB["forbes_2024"]
    cap24 = 255.4
    real_rev = [v[0] / cap24 for v in f24.values()]
    real_op = [v[1] / cap24 for v in f24.values()]
    real_local = [(v[0] - 433) / cap24 for k, v in f24.items()]
    real_local_nodal = [(v[0] - 433) / cap24 for k, v in f24.items() if k != "DAL"]
    sp = PUB["sportico_2025"]
    out.append(f"Team finances vs the real NFL ({len(seeds)} leagues x {a.seasons} seasons, "
               f"{len(rows)} team-seasons; {time.time() - t0:.0f} s)")
    out.append("Money is shown as a share of that season's cap (x cap) so seasons compare; real: Forbes 2024 "
               "(cap $255.4M), Sportico 2025 (cap $279.2M), OverTheCap 2026 (cap $301.2M).")

    head("REVENUE PER TEAM (x cap)")
    rev = [x(r, "revenue") for r in rows]
    line("average (spread)", stats(rev), stats(real_rev), "Forbes 2024; Sportico 2025 avg 2.63")
    line("lowest / middle / highest", f"{min(rev):.2f} / {st.median(rev):.2f} / {max(rev):.2f}",
         f"{min(real_rev):.2f} / {st.median(real_rev):.2f} / {max(real_rev):.2f}")
    loc = [x(r, "local") for r in rows]
    line("local revenue: average (spread)", stats(loc), stats(real_local), "Forbes minus $433M national")
    line("local revenue without the top 3%: spread", f"{st.pstdev(sorted(loc)[:int(len(loc) * .97)]):.2f}",
         f"{st.pstdev(real_local_nodal):.2f}", "real: without Dallas")
    line("highest / average", f"{max(rev) / st.mean(rev):.2f}", f"{max(real_rev) / st.mean(real_rev):.2f}",
         "a Dallas-like giant is rare")

    head("WHERE THE MONEY COMES FROM (share of revenue)")
    tot = sum(r["revenue"] for r in rows)
    share = lambda keys: sum(sum(r[k] for k in keys) for r in rows) / tot
    line("national", f"{share(['national']):.1%}", f"{sp['national']:.0%}")
    line("tickets and suites (incl. visiting share)", f"{share(['gate', 'club', 'suites', 'vts_in', 'vts_out']):.1%}",
         f"{sp['tickets_suites']:.0%}")
    line("sponsors", f"{share(['sponsors']):.1%}", f"{sp['sponsorship']:.0%}")
    line("concessions, parking, store, events", f"{share(['concessions', 'store', 'events', 'playoffs']):.1%}",
         f"{sp['concessions_parking_events']:.0%}")
    line("local media", f"{share(['media']):.1%}", f"{sp['local_media']:.0%}")
    vts = [x(r, "vts_in") * r["cap"] / 1000 * 279.2 / (r["cap"] / 1000) for r in rows]
    line("visiting teams' share a team ($M at a $279M cap)", f"{st.mean(vts):.0f}", f"{sp['vts_per_team_m']}")
    gate = [(r["gate"] + r["club"]) / r["cap"] for r in rows]
    line("regular + club gate (x cap): low / high", f"{min(gate):.2f} / {max(gate):.2f}",
         f"{81 / cap24:.2f} / {176 / cap24:.2f}", "Sportico 2024")

    head("PROFIT (x cap)")
    prof = [x(r, "profit") for r in rows]
    line("average (spread)", stats(prof), stats(real_op), f"Sportico 2025 avg {sp['profit_avg_m'] / 279.2:.2f}")
    line("lowest / middle / highest", f"{min(prof):.2f} / {st.median(prof):.2f} / {max(prof):.2f}",
         f"{min(real_op):.2f} / {st.median(real_op):.2f} / {max(real_op):.2f}")
    line("teams losing money", f"{sum(1 for v in prof if v < 0) / len(prof):.1%}", "0 of 32 (2024)",
         "Packers FY2021 (no fans) and FY2026 (-$1M)")
    cash = [-x(r, "players") for r in rows]
    oc = PUB["otc_cash_2026"]
    line("cash paid to players: average (spread)", stats(cash),
         f"{oc['mean_m'] / oc['cap_m']:.2f} (sd {oc['sd_m'] / oc['cap_m']:.2f})", "OverTheCap 2026")
    line("cash paid to players: low / high", f"{min(cash):.2f} / {max(cash):.2f}",
         f"{oc['min_m'] / oc['cap_m']:.2f} / {oc['max_m'] / oc['cap_m']:.2f}")
    b = ols([(c,) for c in rev], prof)[0]
    rb = ols([(c,) for c in [v for k, v in zip(f24, real_rev) if k != "DAL"]],
             [v for k, v in zip(f24, real_op) if k != "DAL"])[0]
    line("profit per extra $1 of revenue", f"{b[1]:.2f}", f"{rb[1]:.2f}", "Forbes 2024 without Dallas")

    out.append("  by season of the league (average x cap): revenue / cash to players / profit / teams losing money")
    for k in sorted({r["season"] for r in rows}):
        rs = [r for r in rows if r["season"] == k]
        out.append(f"    {k}: {st.mean(x(r, 'revenue') for r in rs):.2f} / {st.mean(-x(r, 'players') for r in rs):.2f} / "
                   f"{st.mean(x(r, 'profit') for r in rs):.2f} / {sum(r['profit'] < 0 for r in rs) / len(rs):.0%}")

    head("TICKET PRICES")
    price26 = [r["price"] * 301_200 / r["cap"] for r in rows]
    fci = [v[0] for v in PUB["fci_2023"].values()]
    line("average regular seat (2026 $)", f"${st.mean(price26):.0f}", f"${136.38 * 301.2 / 255.4:.0f}",
         "TMR 2024 at the 2026 cap")
    line("spread across teams (share of average)", f"{st.pstdev(price26) / st.mean(price26):.1%}",
         f"{st.pstdev(fci) / st.mean(fci):.1%}", "TMR 2023")
    line("cheapest / dearest vs average", f"{min(price26) / st.mean(price26):.2f} / {max(price26) / st.mean(price26):.2f}",
         f"{min(fci) / st.mean(fci):.2f} / {max(fci) / st.mean(fci):.2f}")
    by = {(r["seed"], r["team"], r["season"]): r for r in rows}
    ch = [100 * (r["price"] / by[(r["seed"], r["team"], r["season"] - 1)]["price"] - 1)
          for r in rows if (r["seed"], r["team"], r["season"] - 1) in by]
    rch = PUB["fci_2023_change"]
    if ch:
        line("yearly change %: average (spread)", stats(ch, fmt="{:.1f}"), stats(rch, fmt="{:.1f}"), "TMR 2023")
        line("yearly change %: lowest / highest", f"{min(ch):.1f} / {max(ch):.1f}", f"{min(rch):.1f} / {max(rch):.1f}")
        line("teams cutting prices", f"{sum(1 for v in ch if v < -0.5) / len(ch):.1%}", "0 of 24")

    head("ATTENDANCE (regular season home games)")
    att = [r["att_avg"] for r in rows if r["att_avg"]]
    ry = [v for y, v in REAL["years"].items() if int(y) >= 2022]
    line("average crowd", f"{st.mean(att):,.0f}", f"{st.mean(v['avg'] for v in ry):,.0f}", "ESPN 2022-25")
    line("spread across teams", f"{st.mean(st.pstdev([r['att_avg'] for r in rows if r['seed'] == s and r['season'] == y]) for s, y in {(r['seed'], r['season']) for r in rows}):,.0f}",
         f"{st.mean(v['sd'] for v in ry):,.0f}")
    fill = [r["fill"] for r in rows if r["fill"]]
    bp = REAL["below_era_peak"]
    line("share of seats sold: middle", f"{st.median(fill):.3f}", f"{bp['median']:.3f}", "real: vs the stadium's best year")
    line("share of seats sold: bottom 25% / 10%", f"{pct(fill, .25):.3f} / {pct(fill, .10):.3f}",
         f"{bp['p25']:.3f} / {bp['p10']:.3f}")
    ach = [r["att_avg"] / by[(r["seed"], r["team"], r["season"] - 1)]["att_avg"] - 1 for r in rows
           if (r["seed"], r["team"], r["season"] - 1) in by and r["att_avg"]]
    if ach:
        line("yearly change: middle size", f"{st.median(abs(v) for v in ach):.3f}", f"{REAL['yoy_change']['median_abs']:.3f}")
    # Crowd vs the team's own average over the run, against winning (as the real regression).
    mean_att = {}
    for r in rows:
        mean_att.setdefault((r["seed"], r["team"]), []).append(r["att_avg"])
    X, Y = [], []
    for r in rows:
        if r["wp_last"] is None:
            continue
        X.append((r["wp"] - 0.5, r["wp_last"] - 0.5, 1.0 if r["po_last"] else 0.0))
        Y.append(r["att_avg"] / st.mean(mean_att[(r["seed"], r["team"])]) - 1)
    if len(Y) > 10:
        bw, _ = ols(X, Y)
        rw = REAL["winning_trimmed"]["beta"]
        line("crowd per 1.0 of win%: this season", f"{bw[1]:+.3f}", f"{rw[1]:+.3f} ({REAL['winning']['beta'][1]:+.3f})",
             "real: odd years out (all years)")
        line("crowd per 1.0 of win%: last season", f"{bw[2]:+.3f}", f"{rw[2]:+.3f} ({REAL['winning']['beta'][2]:+.3f})")
        line("crowd: playoffs last season", f"{bw[3]:+.3f}", f"{rw[4]:+.3f} ({REAL['winning']['beta'][4]:+.3f})")

    head("FRANCHISE VALUE AND THE OWNER")
    val = [r["value"] / r["revenue"] for r in rows if r.get("value")]
    line("value / revenue", f"{st.mean(val):.1f}", "10.7", "Forbes 2025")
    mf = [r["money"] for r in rows]
    line("owner unhappy with money (factor >= 1.05)", f"{sum(1 for v in mf if v >= 1.05) / len(mf):.1%}", "-",
         "raises the firing chance (setting on)")
    line("owner pleased with money (factor <= 0.95)", f"{sum(1 for v in mf if v <= 0.95) / len(mf):.1%}", "-")

    head("WHAT DRIVES REVENUE (local revenue x cap on each, one at a time)")
    for key, label in (("brand", "franchise pull (per spread)"), ("market", "market (TV homes, M)"),
                       ("age", "stadium age (years)"), ("wp_last", "last season's win%")):
        pairs = [(r[key], x(r, "local")) for r in rows if r.get(key) is not None]
        bb = ols([(p[0],) for p in pairs], [p[1] for p in pairs])
        line(label, f"{bb[0][1]:+.3f} (R2 {bb[1]:.2f})", "")
    text = "\n".join(out)
    (ROOT / "tools" / "finance_report.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
