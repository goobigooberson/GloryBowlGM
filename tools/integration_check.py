# tools/integration_check.py
# The whole game, start to finish, through the same engine calls the screens make
# (Oct 25: was a scratchpad script the main session ran before every big commit).
# A startup-draft league with a team of yours (staff picks for you) -> camp,
# preseason, final cuts -> the season -> playoffs -> every offseason phase with you
# in it (re-sign, tag, tender, free agency offers, your draft pick, cap moves your
# staff asks for) -> camp ..., with save/load round trips at each stage. Checks:
# 53-man AI rosters and no missing contracts at week 1, no AI team over the cap,
# save/load keeps the league the same, the offseason ends in camp, no crashes.
# Prints each season's league health and the problems found (must be 0).
#
#   python tools/integration_check.py              # 6 seasons (~15 minutes)
#   python tools/integration_check.py --seasons 3
#
# Saves go to a temporary folder (deleted afterward); your saves are never touched.

import argparse
import collections
import os
import statistics as st
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import draft_day, season as S, free_agency as FA, contracts as C, transactions as TR  # noqa: E402
from engine.database import save_league, load_league  # noqa: E402
from engine.teams import ROSTER_SIZE  # noqa: E402


def _print(*a, **_k):
    print(*a, flush=True)


def run(N=6, scratch=None, say=_print):
    """Plays N seasons. Returns {"problems": [...], "health": [(season, point-diff SD,
    starters' average overall, 9+ year veterans %, your record), ...]}."""
    own_dir = scratch is None
    scratch = scratch or tempfile.mkdtemp(prefix="fof-integration-")
    problems = []

    def check(cond, what):
        if not cond:
            problems.append(what)
            say("  PROBLEM: " + what)

    def roundtrip(lg, tag):
        path = os.path.join(scratch, f"integ_{tag}.db")
        save_league(lg, path)
        lg2 = load_league(path)
        for attr in ("season", "stage", "week", "pre_week"):
            check(getattr(lg2, attr) == getattr(lg, attr), f"{tag}: save/load changed {attr}")
        check(len(lg2.contracts) == len(lg.contracts), f"{tag}: save/load changed contract count")
        check(dict(lg2.rosters) == dict(lg.rosters), f"{tag}: save/load changed rosters")
        check(lg2.offseason == lg.offseason, f"{tag}: save/load changed the offseason state")
        check((lg2.tv or {}) == (lg.tv or {}), f"{tag}: save/load changed the TV/cap records")
        check(lg2.cap_history == lg.cap_history, f"{tag}: save/load changed the cap history")
        check((getattr(lg2, "finances", None) or {}) == (getattr(lg, "finances", None) or {}),
              f"{tag}: save/load changed the team finances")
        try:
            os.remove(path)
        except OSError:
            pass
        return lg2

    t0 = time.time()
    lg = draft_day.startup_league(2026, {"roster_method": "startup_draft", "season_games": 17})
    lg.name = "Integration"
    lg.user_team_id = 7
    draft_day.startup_begin(lg)
    mine = 0
    while draft_day.startup_on_clock(lg) and mine < 10:
        slot = draft_day.startup_on_clock(lg)
        if slot["team"] != lg.user_team_id:
            draft_day.startup_sim_to_user(lg)
            continue
        draft_day.startup_pick(lg, draft_day.startup_staff_choice(lg))
        mine += 1
    lg = roundtrip(lg, "startup")
    draft_day.startup_finish(lg)
    say(f"startup draft done in {time.time() - t0:.0f}s; stage {lg.stage}; rosters {collections.Counter(len(lg.team_players(t.id)) for t in lg.teams)}")
    check(TR.in_camp(lg), "after the startup draft the league should be in camp")

    health = []
    fa_open = []
    for yr in range(N):
        ts = time.time()
        try:
            # Preseason through the Glory Bowl.
            weeks = 0
            while not S.season_over(lg):
                if lg.stage == "regular_season" and lg.week == 1 and weeks and not lg.boxes:
                    for t in lg.teams:
                        n = len(lg.team_players(t.id))
                        if t.id != lg.user_team_id:
                            check(n == ROSTER_SIZE, f"{lg.season} week 1: {t.abbrev} has {n}")
                    check(len(C.missing_contracts(lg)) == 0, f"{lg.season} week 1: missing contracts")
                    over = [t.abbrev for t in lg.teams if t.id != lg.user_team_id and C.cap_room(lg, t.id, top51=False) < 0]
                    check(not over, f"{lg.season} week 1: AI teams over the cap {over}")
                # Your staff asks about cap moves: approve them (a real player might).
                for i in range(len(S.staff_requests(lg)) - 1, -1, -1):
                    S.answer_staff_request(lg, i, True)
                S.play_week(lg)
                weeks += 1
                if lg.stage == "regular_season" and lg.week == 9 and weeks < 40:
                    lg = roundtrip(lg, f"{lg.season}-midseason")
            rec = S.records(lg)
            diffs = [(r["pf"] - r["pa"]) / 17 for r in rec.values()]
            starters = []
            from engine import depth
            for t in lg.teams:
                ids = depth.starter_ids(lg.depth_charts.get(t.id, {}))
                starters += [lg.player(pid).overall() for pid in ids if pid in lg.rosters]
            vets = sum(1 for pid in lg.rosters if lg.player(pid).experience >= 9) / max(1, len(lg.rosters))
            u = rec[lg.user_team_id]
            health.append((lg.season, round(st.pstdev(diffs), 2), round(st.mean(starters), 1), round(100 * vets, 1),
                           f"{u['w']}-{u['l']}"))
            say(f"season {lg.season} done in {time.time() - ts:.0f}s: point-diff SD {health[-1][1]}, starters {health[-1][2]}, "
                  f"9+ yr vets {health[-1][3]}%, your team {health[-1][4]}")
            if yr == N - 1:
                break
            # The offseason, phase by phase, with you in it.
            to = time.time()
            S.begin_offseason(lg)
            rows = FA.expiring_for_you(lg)
            signed = tagged = 0
            for r in rows:
                if r["advice"] == "Re-sign":
                    res, _m = FA.resign_offer(lg, r["pid"], r["ask"]["apy"], r["ask"]["years"], r["ask"]["guaranteed"])
                    signed += res == "accept"
                elif r["advice"] == "Tag" and not tagged:
                    ok, _m = FA.tag_or_tender(lg, r["pid"], "tag")
                    tagged += ok
                elif r["advice"] == "Tender":
                    kind = next(iter(r["tenders"]), None)
                    if kind:
                        FA.tag_or_tender(lg, r["pid"], kind)
            lg = roundtrip(lg, f"{lg.season}-resign")
            offers = won = 0
            while S.in_offseason(lg):
                key = lg.offseason["phase"]
                if key == "fa" and lg.fa.get("wave") == 1 and not lg.fa.get("_measured"):
                    lg.fa["_measured"] = True
                    cap = C.cap_for(lg, lg.season)
                    rooms = sorted((C.cap_room(lg, t.id) / cap for t in lg.teams if t.id != lg.user_team_id), reverse=True)
                    fa_open.append(rooms)
                    ap = collections.Counter(FA.approach(lg, t.id) for t in lg.teams if t.id != lg.user_team_id)
                    tv = lg.tv
                    ev = [f"deal {d['start']}-{d['end']} +{d['jump']*100:.0f}pts buzz {d['buzz']:+.2f}"
                          for d in tv["deals"] if d.get("signed") == lg.season]
                    ev += [f"labor {d['kind']}" for d in tv["labor"] if d.get("signed") == lg.season]
                    ev += [f"SHOCK next year {g*100:+.1f}%" for s2, g in tv["shocks"].items() if s2 == lg.season + 1]
                    say(f"  {lg.season} cap {C.fmt_money(cap)} ({(cap / C.cap_for(lg, lg.season - 1) - 1) * 100:+.1f}%), "
                          f"next projected {C.fmt_money(C.cap_for(lg, lg.season + 1))}; buzz {tv['buzz'].get(lg.season - 1)}; "
                          f"{'; '.join(ev)}")
                    say(f"    room at FA open: top {rooms[0]*100:.0f}%, 5th {rooms[4]*100:.0f}%, median {st.median(rooms)*100:.1f}%, "
                          f"24th {rooms[23]*100:.1f}%, under 2%: {sum(r < 0.02 for r in rooms)}; approaches {dict(ap)}")
                    books = (lg.finances or {}).get("books", {}).get(lg.season - 1)
                    check(bool(books) and len(books) == len(lg.teams), f"{lg.season - 1}: team finances not closed")
                    if books:
                        mine_b = books.get(lg.user_team_id, {})
                        say(f"    {lg.season - 1} books: revenue {C.fmt_money(st.mean(b['revenue'] for b in books.values()))}, "
                              f"profit {C.fmt_money(st.mean(b['profit'] for b in books.values()))} "
                              f"({sum(b['profit'] < 0 for b in books.values())} losing money), crowd "
                              f"{st.mean(b['att_avg'] or 0 for b in books.values()):,.0f}; yours "
                              f"{C.fmt_money(mine_b.get('profit', 0))} at ${mine_b.get('price')}")
                if key == "fa":
                    fas = sorted(FA.free_agent_list(lg), key=lambda p: -p.overall())[:40]
                    placed = []
                    for p in fas:
                        if len(placed) >= 2:
                            break
                        ask = FA.asking_terms(lg, p.id, lg.user_team_id, lg.fa["wave"])
                        if ask["apy"] > 0.04 * C.cap_for(lg, lg.season):
                            continue
                        res, _m = FA.place_offer(lg, p.id, ask["apy"], ask["years"], ask["guaranteed"])
                        if res == "accept":
                            placed.append(p.id)
                    offers += len(placed)
                    S.advance_offseason(lg)
                    won += sum(1 for pid in placed if lg.rosters.get(pid) == lg.user_team_id)
                elif key == "drafting":
                    if draft_day.user_on_clock(lg):
                        pid, _slot = draft_day.staff_choice(lg)
                        ok, _m = draft_day.pick(lg, pid)
                        check(ok, f"{lg.season}: your draft pick failed: {_m}")
                    lg = roundtrip(lg, f"{lg.season}-drafting")
                    S.advance_offseason(lg)
                else:
                    if S.cap_hold(lg):
                        # Over the hard cap at the new league year (Blake's rule): accept your staff's
                        # suggested restructures and cuts, as a player would, then move on.
                        short = S.cap_hold(lg)["short"]
                        for i in range(len(S.staff_requests(lg)) - 1, -1, -1):
                            S.answer_staff_request(lg, i, True)
                        hold = S.cap_hold(lg)
                        say(f"    {lg.season}: you were {C.fmt_money(short)} over the cap; after your staff's moves "
                              f"{'still ' + C.fmt_money(hold['short']) + ' over' if hold else 'under'}")
                        check(not hold, f"{lg.season}: your staff's cap moves didn't get you under the cap")
                        if hold:
                            break
                    S.advance_offseason(lg)
            say(f"  offseason {lg.season} in {time.time() - to:.0f}s: re-signed {signed}, tagged {tagged}, offers {offers}, "
                  f"won {won}; camp {TR.in_camp(lg)}; sizes {sorted({len(lg.team_players(t.id)) for t in lg.teams})}")
            check(TR.in_camp(lg) and lg.stage == "preseason", f"{lg.season}: after the offseason not in camp/preseason")
        except Exception:
            problems.append(f"{lg.season}: crash")
            traceback.print_exc()
            break
    say(f"\n{N} seasons in {time.time() - t0:.0f}s")
    say("season, point-diff SD (real ~6), starters avg, 9+ yr vets % (real ~9), your record")
    for h in health:
        say("  ", h)
    if fa_open:
        allr = sorted((r for v in fa_open for r in v), reverse=True)
        n = len(allr)
        say(f"room at FA open, all offseasons: median {st.median(allr)*100:.1f}% [real ~14], 75th pct "
              f"{allr[n//4]*100:.1f}%, 25th pct {allr[3*n//4]*100:.1f}% [real ~3], under 2% per year "
              f"{sum(r < 0.02 for r in allr)/len(fa_open):.1f} [real 7-8]")
    say("PROBLEMS:", len(problems))
    for p in problems:
        say("  ", p)

    if own_dir:
        try:
            os.rmdir(scratch)
        except OSError:
            pass
    return {"problems": problems, "health": health}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, default=6)
    a = ap.parse_args()
    res = run(a.seasons)
    sys.exit(1 if res["problems"] else 0)


if __name__ == "__main__":
    main()
