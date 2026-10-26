# tools/free_agency_check.py
# Contracts, the salary cap and free agency vs the real NFL.
#
# Plays generated leagues through the game's own seasons and offseasons with
# the league lab (tools/lab.py: New Game's league, season.play_week week by
# week with every roster move, injury, trade and money rule, the offseason
# phase by phase as the Next button plays it, the cut from 90 to 53 after the
# preseason) and measures, at the moments that matter (the season's end, each
# free agency wave, week 1), every benchmark next to the real numbers:
#   where players go (same team / new team / out of the league), the deals
#   signed (minimum share, one-year share, market deals by position, lengths,
#   guarantees, ages), the pay ladder by position, team payrolls, positional
#   spending, rookie scale, tags/extensions, cap legality (offseason
#   checkpoints and every week of the seasons), in-season signings; and the
#   "fair price" check: do good players sign far below their worth while teams
#   still have room (FOF8's cheap-star exploit; real yardstick from
#   docs/research/fair_price.py)?
# Games are made up from team strength by default (lab "fast" games: the
# season loop around them is the game's own); --games plays the real sim (slow).
# Each league runs in its own process, side by side.
#
#   python tools/free_agency_check.py                 (leagues 101,102; 3 offseasons each)
#   python tools/free_agency_check.py --leagues 101,102,103 --seasons 4
#   python tools/free_agency_check.py --games
# Writes tools/free_agency_report.txt. Nothing is saved; your saves are never touched.
# tools/scoreboard.py uses collect() and headline() from here.

import argparse
import json
import statistics as st
import sys
import time
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from engine import contracts as C                     # noqa: E402
from engine import cap_market as M                    # noqa: E402
from engine import free_agency as FA                  # noqa: E402
from engine import season as SEASON                   # noqa: E402
from engine import depth as DEPTH                     # noqa: E402
from engine import transactions as TX                 # noqa: E402

RESEARCH = ROOT / "docs" / "research"
REAL_C = json.loads((RESEARCH / "real_contracts.json").read_text())
REAL_M = json.loads((RESEARCH / "real_movement.json").read_text())
REAL_FP = json.loads((RESEARCH / "real_fair_price.json").read_text())
# Big deals (5%+ of the cap), 2019-22: 321 deals by length (real_contracts_summary.md)
REAL_BIG_YEARS = {1: 61, 2: 32, 3: 86, 4: 90, 5: 46, 6: 6}
# Franchise tags per year (real 2019-24, public tag trackers): about 6-14, usually ~7-9.
REAL_TAGS = (6, 14)
GROUP_MOVE = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "T": "OL", "G": "OL", "C": "OL",
              "DE": "DL", "DT": "DL", "OLB": "LB", "ILB": "LB", "CB": "DB", "S": "DB", "K": "K", "P": "P", "LS": "LS"}
LADDER_GROUP = {"QB": "QB", "RB": "RB", "FB": "FB", "WR": "WR", "TE": "TE", "T": "T", "G": "G", "C": "C",
                "DE": "EDGE", "DT": "DT", "OLB": "LB", "ILB": "LB", "CB": "CB", "S": "S", "K": "K", "P": "P",
                "LS": "LS"}
EXP_GROUPS = (("0-2", 0, 2), ("3-4", 3, 4), ("5-7", 5, 7), ("8+", 8, 99))
# Cap room when free agency opened, March 2, 2024 (OverTheCap via CBS Sports; $255.4M cap; $M).
# Teams over the cap had to get under it by the start of the league year (March 13), so they
# count as 0 here. 2025 (CBS, March 5; tiers only): 5 teams over, 6 at $0-20M, 5 at $20-40M,
# 9 at $40-60M, 6 at $60-100M, New England $127M ($279.2M cap): a median of about 14%.
REAL_FA_OPEN_2024 = [101.8, 91.5, 78.7, 75.7, 70.1, 69.7, 56.8, 52.5, 48.6, 42.0, 41.9, 40.9, 37.6, 37.6, 35.0,
                     34.8, 32.6, 29.2, 20.7, 13.6, 12.5, 12.2, 8.0, 6.8, 3.5, 0, 0, 0, 0, 0, 0, 0]
REAL_CAP_2024 = 255.4
# Cap room just after each new league year opened, after the first day or two of signings
# (OverTheCap's "Cap Space" via the Internet Archive: March 19, 2021, March 17, 2022, March 17,
# 2023, March 14, 2024, March 13, 2025; $M). The game's match is right after free agency's
# first wave. The target is the average without 2021 (the COVID year, when the cap fell).
REAL_FA_DAY1_TARGET_YEARS = (2022, 2023, 2024, 2025)
REAL_FA_DAY1 = {
    2021: (182.5, [43.6, 37.6, 34.1, 32.4, 29.1, 28.0, 21.2, 15.7, 15.1, 14.1, 12.5, 12.5, 11.7, 10.7, 10.6, 9.0,
                   8.7, 7.1, 5.5, 4.0, 3.0, 2.7, 1.5, 1.3, 0.6, 0.4, -1.3, -2.3, -3.6, -7.6, -12.0, -18.7]),
    2022: (208.2, [44.3, 39.7, 37.3, 34.6, 32.1, 29.4, 26.6, 24.8, 22.7, 21.0, 19.8, 17.4, 16.3, 15.7, 14.0, 14.0,
                   13.3, 13.1, 13.0, 12.0, 12.0, 9.2, 8.3, 6.6, 0.9, 0.8, 0.7, -3.6, -8.2, -9.4, -9.6, -10.7]),
    2023: (224.8, [44.9, 33.6, 23.8, 23.2, 22.8, 22.7, 21.4, 21.3, 21.0, 20.3, 19.8, 19.3, 18.7, 17.5, 17.4, 17.3,
                   15.5, 15.1, 14.7, 14.1, 12.3, 11.9, 10.6, 9.3, 8.5, 8.4, 7.9, 5.8, 5.3, 3.3, -1.4, -2.5]),
    2024: (255.4, [72.1, 68.0, 57.2, 56.3, 45.7, 40.6, 40.0, 34.2, 31.9, 29.2, 26.8, 26.0, 21.0, 18.9, 17.8, 17.3,
                   15.3, 15.1, 12.9, 11.9, 10.8, 9.8, 4.7, 3.6, 3.4, 3.0, 2.2, 1.2, 1.1, -1.8, -2.2, -7.8]),
    2025: (279.2, [100.9, 83.0, 70.2, 66.1, 60.8, 55.3, 53.6, 48.2, 47.5, 47.3, 46.4, 43.7, 35.1, 34.5, 33.8, 32.8,
                   32.2, 32.1, 28.4, 27.5, 26.1, 23.9, 22.6, 16.5, 13.8, 11.8, 9.9, 6.9, 6.3, 6.2, 0.8, -10.3]),
}

out_lines = []


def say(s=""):
    print(s)
    out_lines.append(s)


def pct(x):
    return f"{100 * x:5.1f}%"


# ---------------------------------------------------------------------------
# Fair price: free agency wave by wave, with what each player was worth and
# what room every AI team had when the wave opened
# ---------------------------------------------------------------------------

FAIR_LINE = 0.6            # "far below his worth": under this share of his market value


def wave_context(lg, w):
    """What every free agent is worth and the room every AI team has, as wave w opens."""
    cap = C.cap_for(lg, lg.season)
    pre = w in FA.PRE_DRAFT_WAVES
    room = {tid: (C.cap_room(lg, tid) - FA._reserve_share(lg, tid, pre) * cap + FA._restructure_left(lg, tid)) / cap
            for tid in FA.ai_teams(lg)}
    return M.market_table(lg), room


def record_wave(lg, w, table, room, signed, stats, before, starters):
    """For each signing of the wave: the player's market price, his ask, whether
    he was a starter last season, and the room every other AI team had."""
    cap = C.cap_for(lg, lg.season)
    for s_ in signed:
        p = lg.player(s_["pid"])
        info = table[p.id]
        stats["fair"].append({
            "pid": p.id, "pos": p.position, "group": LADDER_GROUP[p.position], "age": FA._age(lg, p),
            "ovr": p.overall(), "wave": w, "share": s_["apy"] / cap, "price": info["price"],
            "ask": FA.ask_share(info, w), "good_rating": info["price"] >= M.MARKET_LINE and FA.starter_level(info),
            "starter": p.id in starters, "last_team": before.get(p.id), "team": s_["team"],
            "rooms": sorted(r for t, r in room.items() if t != s_["team"]),
            "name": f"{p.first_name} {p.last_name}", "season": lg.season, "league": lg.name})


def new_stats():
    return {"legal": [], "missing": 0, "move_all": Counter(), "move_exp": defaultdict(Counter),
            "move_pos": defaultdict(Counter), "year": Counter(), "waves": Counter(), "waves_market": Counter(),
            "deals": [], "ladder": defaultdict(list), "spend": defaultdict(list), "payroll": [], "room": [],
            "dead": [], "seasons": 0, "gone_why": defaultdict(Counter), "fa_open": [], "fa_day1": [], "fair": [],
            "camp_unsigned": [], "over_in_season": 0, "over_amounts": [], "in_season": [],
            "units": [], "season_units": []}


def new_day1():
    return {"ladder": defaultdict(list), "spend": defaultdict(list), "payroll": [], "room": [], "dead": []}


def merge(into, part):
    """Add one league's numbers into the running totals."""
    for k, v in part.items():
        if k not in into:
            into[k] = v
        elif isinstance(v, Counter):
            into[k].update(v)
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, Counter):
                    into[k][kk].update(vv)
                else:
                    into[k][kk].extend(vv)
        elif isinstance(v, list):
            into[k].extend(v)
        else:
            into[k] += v
    return into


class Tracker:
    """Measures one lab league (tools/lab.py) at the moments that matter: the
    season's end (who's where), the new league year (cap room as free agency
    opens), each free agency wave (prices, room, signings), week 1 after the
    cut to 53 (where everyone ended up, the deals, legality), every week of the
    season (teams over the cap). Each offseason also leaves a "unit" of
    headline numbers (headline(), tools/scoreboard.py)."""

    def __init__(self, stats, day1):
        self.stats, self.day1 = stats, day1
        self.cur = None             # the offseason being measured, until the next week 1
        self.week1_log = None       # contract_log length at the last week 1 (in-season deals come after it)
        self.season_over = 0        # AI team-weeks over the cap this season
        self.season_short = Counter()   # AI regular-season team-weeks by players on the 53
        self.season_ps = []         # ...and their practice squad sizes
        self.long_term = []         # tagged players signed long-term, by camp phase (FA.tagged_long_term)
        self.year_started = False   # a league year begun in this run (the new league's first one is set up, not played)
        self.dead20 = Counter()     # each team's run of seasons ending with 20%+ of its cap in dead money
        self.open2 = Counter()      # ...and of league years opening free agency under 2% of the cap

    def attach(self, lab):
        for event, fn in (("season_end", self.season_end), ("offseason_start", self.offseason_start),
                          ("phase_before", self.phase_before), ("phase_after", self.phase_after),
                          ("regular_season", self.week1), ("week_end", self.week_end)):
            lab.on(event, fn)

    def week_end(self, lab, label):
        lg = lab.league
        if self.week1_log is None or SEASON.in_preseason(lg):
            return
        over = [room for t, room in C.audit(lg) if t != lg.user_team_id]
        self.stats["over_in_season"] += len(over)
        self.stats["over_amounts"].extend(over)
        self.season_over += len(over)
        if label.startswith("Week"):
            # How many AI teams carry fewer than 53 (Oct 25: a team at the cap with nothing left
            # to restructure or cut plays short rather than go over; transactions.injury_cover).
            for t in lg.teams:
                if t.id != lg.user_team_id:
                    n = sum(1 for x in lg.rosters.values() if x == t.id)
                    self.season_short[min(53, n)] += 1
                    self.season_ps.append(len(TX.practice_players(lg, t.id)))

    def season_end(self, lab):
        lg = lab.league
        if self.week1_log is not None:
            new = [d for d in lg.contract_log[self.week1_log:] if d["kind"] not in ("rookie", "udfa")]
            self.stats["in_season"].extend(new)
            n = sum(self.season_short.values()) or 1
            self.stats["season_units"].append({
                "in_season_deals": len(new), "over_cap_team_weeks": self.season_over,
                "short_53": sum(c for k, c in self.season_short.items() if k < 53) / n,
                "short_51": sum(c for k, c in self.season_short.items() if k <= 51) / n,
                "short_50": sum(c for k, c in self.season_short.items() if k <= 50) / n,
                "ps_size": st.mean(self.season_ps) if self.season_ps else None})
            if self.year_started:
                self.stats["season_units"][-1].update(self._money_unit(lg))
        self.season_over = 0
        self.season_short, self.season_ps = Counter(), []
        before = {pid: tid for pid, tid in lg.rosters.items()}
        for pid, r in lg.reserve.items():
            before[pid] = r["team"]
        starters = set()                 # last season's starters (the base packages of each depth chart)
        for t in lg.teams:
            starters |= DEPTH.starter_ids(lg.depth_charts.get(t.id, {}))
        self.cur = {"before": before, "exp": {pid: lg.player(pid).experience for pid in before},
                    "starters": starters, "log0": len(lg.contract_log), "legal0": len(self.stats["legal"]),
                    "fair0": len(self.stats["fair"]), "camp0": len(self.stats["camp_unsigned"]),
                    "lt0": len(self.long_term), "sign1": [], "sign2": [], "n_signed": 0}

    def _money_unit(self, lg):
        """Dead money, restructures and void years over the league year just played (Oct 26),
        measured at the season's end like Spotrac's team cap tables."""
        S = lg.season
        cap = C.cap_for(lg, S)
        teams = [t.id for t in lg.teams if t.id != lg.user_team_id]
        dead = sorted(C.charges(lg, t, S) / cap for t in teams)
        for t in teams:
            self.dead20[t] = self.dead20[t] + 1 if C.charges(lg, t, S) >= 0.20 * cap else 0
        rs = lg.fa.get("restructures", {})
        conv = {t: rs.get(t, (0, 0))[0] / cap for t in teams}
        ways = lg.fa.get("approach", {})

        def by(way):
            v = [conv[t] for t in teams if ways.get(t, "normal") == way]
            return st.mean(v) if v else None
        n = len(teams)
        return {"dead_end_mean": st.mean(dead), "dead_end_p90": dead[min(n - 1, int(0.9 * n))],
                "dead_end_20": sum(x >= 0.20 for x in dead), "dead20_streak_max": max(self.dead20.values()),
                "restr_none": sum(conv[t] == 0 for t in teams) / n,
                "restr_mid": sum(0.036 <= conv[t] < 0.082 for t in teams) / n,
                "restr_big": sum(conv[t] >= 0.082 for t in teams) / n,
                "restr_mean": st.mean(conv.values()),
                "restr_allin": by("all_in"), "restr_rebuild": by("rebuild"),
                "restr_void_years": sum(v[1] for v in rs.values()),
                "void_deals_open": sum(1 for c in lg.contracts.values() if C.void_list(c))}

    def offseason_start(self, lab):
        lg, cur, stats = lab.league, self.cur, self.stats
        cur["S"] = lg.season
        self.year_started = True
        cur["retired"] = {pid for pid, _t in lg.offseason_report["retired"]}
        cur["rep"] = dict(lg.offseason_report.get("free_agency") or {})
        stats["legal"].append(("league year", [t for t, _ in C.audit(lg)]))
        # Cap room the day free agency opens (after re-signings, tags, cap cuts; top 51 counts).
        cap = C.cap_for(lg, lg.season)
        cur["open"] = sorted((C.cap_room(lg, t.id) / cap for t in lg.teams if t.id != lg.user_team_id),
                             reverse=True)
        stats["fa_open"].append(cur["open"])
        # Void years that just voided (Oct 26): their money is this league year's dead money.
        teams = [t.id for t in lg.teams if t.id != lg.user_team_id]
        vd = lg.fa.get("voided", {})
        vshare = sorted((vd.get(t, (0, 0))[1] / cap for t in teams), reverse=True)
        cur["void"] = {"voided": sum(vd.get(t, (0, 0))[0] for t in teams), "voided_teams": sum(t in vd for t in teams),
                       "void_dead_mean": st.mean(vshare), "void_dead_max": vshare[0],
                       "void_dead_10": sum(x >= 0.10 for x in vshare)}
        room = {t.id: C.cap_room(lg, t.id) / cap for t in lg.teams if t.id != lg.user_team_id}
        for t, r in room.items():
            self.open2[t] = self.open2[t] + 1 if r < 0.02 else 0
        cur["void"]["open2_streak_max"] = max(self.open2.values())

    def phase_before(self, lab, phase, wave):
        if phase == "fa":
            self.cur["ctx"] = wave_context(lab.league, wave)

    def phase_after(self, lab, phase, wave):
        lg, cur, stats = lab.league, self.cur, self.stats
        if phase == "fa":
            table, room = cur.pop("ctx")
            signed = lg.offseason_report["fa_signings"][cur["n_signed"]:]
            cur["n_signed"] += len(signed)
            record_wave(lg, wave, table, room, signed, stats, cur["before"], cur["starters"])
            (cur["sign1"] if wave in FA.PRE_DRAFT_WAVES else cur["sign2"]).extend(signed)
            cap = C.cap_for(lg, lg.season)
            if wave == FA.PRE_DRAFT_WAVES[0]:
                # ...and right after the first wave (the real day-after snapshots include the first day's signings).
                cur["day1"] = sorted((C.cap_room(lg, t.id) / cap for t in lg.teams if t.id != lg.user_team_id),
                                     reverse=True)
                stats["fa_day1"].append(cur["day1"])
            if wave == FA.PRE_DRAFT_WAVES[-1]:
                stats["legal"].append(("pre-draft FA", [t for t, _ in C.audit(lg)]))
            if wave == FA.POST_DRAFT_WAVES[-1]:
                # Still unsigned as camp opens: the late-bargain window (what each would ask you now).
                table = M.market_table(lg)
                for p in FA.free_agent_list(lg):
                    info = table[p.id]
                    if info["price"] >= M.MARKET_LINE and FA.starter_level(info) and FA._age(lg, p) <= 30:
                        stats["camp_unsigned"].append({"price": info["price"], "ask": FA.ask_share(info, wave),
                                                       "starter": p.id in cur["starters"], "ovr": p.overall()})
        elif phase in ("draft", "drafting") and (lg.offseason or {}).get("phase") == "fa":
            stats["legal"].append(("draft", [t for t, _ in C.audit(lg)]))

    def week1(self, lab):
        lg, cur, stats = lab.league, self.cur, self.stats
        self.week1_log = len(lg.contract_log)
        if cur is None or "S" not in cur:
            snapshot_contracts(lg, self.day1)        # a new league's first week 1
            return
        S = cur["S"]
        # Week 1: everyone counts against the cap now.
        stats["legal"].append(("week 1", [t for t, _ in C.audit(lg, top51=False)]))
        missing = len(C.missing_contracts(lg))
        stats["missing"] += missing
        # Where last season's players are now.
        move, move_exp = Counter(), defaultdict(Counter)
        for pid, tid in cur["before"].items():
            p = lg.player(pid)
            now = FA.on_team(lg, pid)
            where = "gone" if now is None else "same" if now == tid else "new"
            e = cur["exp"][pid]
            eg = next(g for g, lo, hi in EXP_GROUPS if lo <= e <= hi)
            move[where] += 1
            move_exp[eg][where] += 1
            stats["move_all"][where] += 1
            stats["move_exp"][eg][where] += 1
            stats["move_pos"][GROUP_MOVE[p.position]][where] += 1
            if where == "gone":
                why = ("retired" if pid in cur["retired"] else "left (unsigned, gave up)" if p.retired is not None
                       else "unsigned free agent")
                stats["gone_why"][eg][why] += 1
                stats["gone_why"]["pos " + GROUP_MOVE[p.position]][why] += 1
        rep = cur["rep"]
        for k, v in rep.items():
            if isinstance(v, (int, float)):
                stats["year"][k] += v
        stats["year"]["fa_signed_pre"] += len(cur["sign1"])
        stats["year"]["fa_signed_post"] += len(cur["sign2"])
        stats["year"]["tag_long_term"] += sum(self.long_term[cur["lt0"]:])
        stats["year"]["cut_down"] += (getattr(lg, "final_cuts", None) or {}).get("cuts", 0)
        stats["year"]["unsigned_fa_week1"] += len(lg.free_agents())
        for s_ in cur["sign1"] + cur["sign2"]:
            stats["waves"][s_["wave"]] += 1
            if s_["apy"] / C.cap_for(lg, S) >= M.MARKET_LINE:
                stats["waves_market"][s_["wave"]] += 1
        stats["seasons"] += 1
        deals = lg.contract_log[cur["log0"]:]
        stats["deals"].extend(deals)
        snapshot_contracts(lg, stats)
        stats["units"].append(self._unit(lg, cur, deals, move, move_exp, missing))
        self.cur = None

    def _unit(self, lg, cur, deals, move, move_exp, missing):
        """This offseason's headline numbers (tools/scoreboard.py averages them and
        measures how much they swing from one offseason to the next)."""
        stats = self.stats
        d1 = cur.get("day1") or [0.0] * 32
        u = {"room_w1_most": d1[0], "room_w1_5th": d1[4], "room_w1_median": st.median(d1),
             "room_w1_24th": d1[23], "teams_under_2pct_w1": sum(x < 0.02 for x in d1),
             "room_open_median": st.median(cur["open"]), "room_open_24th": cur["open"][23],
             "teams_under_2pct_open": sum(x < 0.02 for x in cur["open"])}
        u.update(cur.get("void") or {})
        n = sum(move.values()) or 1
        u.update(same_all=move["same"] / n, new_all=move["new"] / n, gone_all=move["gone"] / n)
        for g, _lo, _hi in EXP_GROUPS:
            c = move_exp[g]
            u["gone_" + g.replace("+", "p").replace("-", "_")] = c["gone"] / (sum(c.values()) or 1)
        u["illegal"] = sum(len(ts) for _w, ts in stats["legal"][cur["legal0"]:]) + missing
        mk = [d for d in deals if d["kind"] not in ("rookie", "udfa", "practice") and d["apy_share"] >= M.MARKET_LINE]
        u["market_deals"] = len(mk)
        u["market_new_team"] = sum(1 for d in mk if d["kind"] != "extension" and d.get("new_team"))
        u["market_resigned"] = sum(1 for d in mk if d["kind"] != "extension" and not d.get("new_team"))
        u["market_extensions"] = sum(1 for d in mk if d["kind"] == "extension")
        real_val = REAL_FP["market_value"]
        a = [d for d in stats["fair"][cur["fair0"]:] if d["starter"] and d["age"] <= REAL_FP["max_age"]
             and d["last_team"] is not None and d["team"] != d["last_team"] and d["group"] in real_val]
        u["fair_good_fa_signings"] = len(a)
        if a:
            u["fair_under_60pct"] = sum(d["share"] / real_val[d["group"]] < 0.6 for d in a) / len(a)
            u["fair_under_40pct"] = sum(d["share"] / real_val[d["group"]] < 0.4 for d in a) / len(a)
            u["fair_minimum"] = sum(d["share"] <= M.MINIMUM_LINE for d in a) / len(a)
        camp = stats["camp_unsigned"][cur["camp0"]:]
        u["camp_unsigned_good"] = len(camp)
        u["camp_unsigned_stars"] = sum(d["price"] >= 0.05 for d in camp)
        rep = cur["rep"]
        u.update(tags=rep.get("tags", 0), cap_cuts=rep.get("cap_cuts", 0), extensions=rep.get("extensions", 0))
        cap = C.cap_for(lg, lg.season)
        tcs = [C.team_cap(lg, t.id, top51=False) for t in lg.teams]
        u["wk1_cap_used"] = st.mean(tc["used"] / tc["cap"] for tc in tcs)
        u["wk1_dead"] = st.mean(tc["dead"] / cap for tc in tcs)
        return u


def run_league(job):
    """One league in its own process: (seed, offseasons, games) -> (stats, day1, top signings)."""
    seed, seasons, games = job
    from lab import Lab
    stats, day1 = new_stats(), new_day1()
    tr = Tracker(stats, day1)
    plain = FA.tagged_long_term

    def counted(*a, **k):
        n = plain(*a, **k)
        tr.long_term.append(n)
        return n
    FA.tagged_long_term = counted
    lab = Lab(seed, games)
    tr.attach(lab)
    for _ in range(seasons):
        lab.play_season()
        lab.play_offseason()
    lab.play_season(until="week1")
    return stats, day1, top_signings(lab.league)


def collect(seeds, seasons, games="fast", workers=6):
    """Every league side by side, merged: (stats, day1, top signings of the last league)."""
    from multiprocessing import Pool
    stats, day1, top = new_stats(), new_day1(), []
    with Pool(min(len(seeds), workers), maxtasksperchild=1) as pool:
        for st_, d1, tp in pool.imap(run_league, [(s, seasons, games) for s in seeds]):
            merge(stats, st_)
            merge(day1, d1)
            top = tp
    return stats, day1, top


def headline(stats):
    """{measure: [one value per offseason (or season)]} for tools/scoreboard.py."""
    out = defaultdict(list)
    for u in stats["units"]:
        for k, v in u.items():
            out[k].append(v)
    for u in stats["season_units"]:
        for k, v in u.items():
            out[k].append(v)
    return dict(out)


def snapshot_contracts(lg, stats):
    """Pay ladder, payrolls and positional spending at week 1."""
    S = lg.season
    by = defaultdict(list)
    spend = defaultdict(float)
    for pid, c in lg.contracts.items():
        if c["kind"] == "practice":
            continue
        p = lg.player(pid)
        by[LADDER_GROUP[p.position]].append(c.get("new_apy", c["apy"]) / C.cap_for(lg, c["signed"]))
        spend[LADDER_GROUP[p.position]] += C.cap_hit(lg, c, S)
    for g, v in by.items():
        v.sort(reverse=True)
        stats["ladder"][g].append(v)
    total = sum(spend.values())
    for g, v in spend.items():
        stats["spend"][g].append(v / total)
    cap = C.cap_for(lg, S)
    for t in lg.teams:
        tc = C.team_cap(lg, t.id, top51=False)
        stats["payroll"].append(tc["used"] / tc["cap"])
        stats["room"].append(tc["room"] / cap)
        stats["dead"].append(tc["dead"] / cap)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(stats, n_leagues):
    S = stats["seasons"]
    say("=" * 100)
    say(f"FREE AGENCY CHECK: {n_leagues} league(s), {S} offseason(s) in all. Real numbers in brackets.")
    say("=" * 100)
    # Legality
    bad = [(where, t) for where, ts in stats["legal"] for t in ts]
    say(f"Cap legality: AI teams over the cap at any checkpoint: {len(bad)} (must be 0)"
        + (f"  {bad[:6]}" if bad else ""))
    say(f"Players on a team without a contract at week 1: {stats['missing']} (must be 0)")
    am = stats.get("over_amounts") or []
    say(f"During the seasons: AI team-weeks over the cap: {stats['over_in_season']} (must be 0)"
        + (f" (by {C.fmt_money(-max(am))} to {C.fmt_money(-min(am))})" if am else ""))
    say()
    # Movement
    say("WHERE LAST SEASON'S PLAYERS ARE IN WEEK 1 (same team / new team / no team)")
    real = REAL_M["offseason"]

    def row(label, c, r):
        n = sum(c.values()) or 1
        say(f"  {label:7} n/season {n / S:6.0f}   same {pct(c['same'] / n)} [{pct(r['same'])}]   "
            f"new {pct(c['new'] / n)} [{pct(r['new_team'])}]   gone {pct(c['gone'] / n)} [{pct(r['gone'])}]")
    row("all", stats["move_all"], real["all"])
    for g, _lo, _hi in EXP_GROUPS:
        row(g, stats["move_exp"][g], real["by_experience_end_of_season"][g])
    pos_real = real["by_position"]
    for g in ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K", "P", "LS"):
        if g in pos_real:
            row(g, stats["move_pos"][g], pos_real[g])
    say("  why 'gone' (per season): " + "; ".join(
        f"{g}: " + ", ".join(f"{k} {v / S:.0f}" for k, v in stats["gone_why"][g].most_common())
        for g, _lo, _hi in EXP_GROUPS))
    say("  by position: " + "; ".join(
        f"{g[4:]}: " + ", ".join(f"{k.split(' ')[0]} {v / S:.0f}" for k, v in c.most_common())
        for g, c in sorted(stats["gone_why"].items()) if g.startswith("pos ")))
    say()
    # Deals
    deals = [d for d in stats["deals"] if d["kind"] not in ("rookie", "udfa")]
    all_deals = deals + stats["in_season"]
    say("VETERAN DEALS SIGNED IN A LEAGUE YEAR (everything but rookie deals, incl. practice squad deals and "
        "the season's signings)")
    n = len(all_deals) or 1
    mins = sum(1 for d in all_deals if d["apy_share"] <= M.MINIMUM_LINE)
    one = sum(1 for d in all_deals if d["years"] == 1)
    real_total = sum(v["veteran_deals_per_season"] for v in REAL_C["positions"].values())
    say(f"  deals per season {n / S:6.0f} [{real_total:.0f}; real counts include in-season and futures deals]")
    say(f"  at about the minimum (<= 0.65% of the cap) {pct(mins / n)} [76-87% by position]")
    say(f"  one-year deals {pct(one / n)} [75-80%]")
    no_ps = [d for d in all_deals if d["kind"] != "practice"]
    if no_ps:
        say(f"  (without practice squad deals: minimum {pct(sum(1 for d in no_ps if d['apy_share'] <= M.MINIMUM_LINE) / len(no_ps))}, "
            f"one-year {pct(sum(1 for d in no_ps if d['years'] == 1) / len(no_ps))})")
    kinds = Counter(d["kind"] for d in all_deals)
    say("  by kind per season: " + ", ".join(f"{k} {v / S:.0f}" for k, v in kinds.most_common()))
    say()
    say("MARKET DEALS (1%+ of the cap) per season, by position: sim [real]; median share; years; guaranteed; age 26-27 share")
    mk = [d for d in deals if d["apy_share"] >= M.MARKET_LINE]
    by = defaultdict(list)
    for d in mk:
        by[LADDER_GROUP[d["pos"]]].append(d)
    tot_sim = tot_real = 0
    for g in ("QB", "WR", "EDGE", "DT", "CB", "T", "LB", "S", "G", "TE", "RB", "C", "K", "P", "FB", "LS"):
        r = REAL_C["positions"][g]["market_deals_1pct_plus"]
        ds = by[g]
        tot_sim += len(ds) / S
        tot_real += r.get("n_per_season", 0)
        if not ds:
            say(f"  {g:5} {0:5.1f} [{r.get('n_per_season', 0):5.1f}]")
            continue
        yrs = [d["years"] for d in ds]
        g_sh = [d["guaranteed"] / max(1, d["value"]) for d in ds]
        a2627 = sum(1 for d in ds if 26 <= d["age"] <= 27) / len(ds)
        say(f"  {g:5} {len(ds) / S:5.1f} [{r.get('n_per_season', 0):5.1f}]   median {pct(st.median(d['apy_share'] for d in ds))} "
            f"[{pct(r.get('cap_pct_p50') or 0)}]   years {st.mean(yrs):.2f} [{r.get('years_mean') or 0:.2f}]   "
            f"gtd {pct(st.median(g_sh))} [{pct(r.get('guaranteed_share_median') or 0)}]   "
            f"age 26-27 {pct(a2627)} [{pct((r.get('age_dist') or {}).get('26-27', 0))}]")
    say(f"  total {tot_sim:6.1f} [{tot_real:6.1f}]")
    yd = Counter(min(d["years"], 6) for d in mk)
    real_yd = defaultdict(float)
    real_n = 0
    for g, v in REAL_C["positions"].items():
        m = v["market_deals_1pct_plus"]
        for k, s_ in (m.get("years_dist") or {}).items():
            real_yd[int(k)] += s_ * m["n_per_season"]
        real_n += m.get("n_per_season", 0)
    say("  market deal lengths: " + "  ".join(f"{k}y {pct(yd[k] / max(1, len(mk)))} [{pct(real_yd[k] / real_n)}]"
                                                for k in range(1, 7)))
    big = [d for d in deals if d["apy_share"] >= 0.05]
    by_ = Counter(min(d["years"], 6) for d in big)
    rb = sum(REAL_BIG_YEARS.values())
    say(f"  big deals (5%+) per season {len(big) / S:.1f} [{rb / 4:.0f}]; lengths: "
        + "  ".join(f"{k}y {pct(by_[k] / max(1, len(big)))} [{pct(REAL_BIG_YEARS[k] / rb)}]" for k in range(1, 7)))
    ages = Counter()
    for d in mk:
        a = d["age"]
        ages["<=25" if a <= 25 else "26-27" if a <= 27 else "28-29" if a <= 29 else "30-31" if a <= 31 else "32+"] += 1
    real_age = defaultdict(float)
    for g, v in REAL_C["positions"].items():
        m = v["market_deals_1pct_plus"]
        for k, s_ in (m.get("age_dist") or {}).items():
            real_age[k] += s_ * m["n_per_season"]
    say("  market deals by age: " + "  ".join(f"{k} {pct(ages[k] / max(1, len(mk)))} [{pct(real_age[k] / real_n)}]"
                                              for k in ("<=25", "26-27", "28-29", "30-31", "32+")))
    new_team = [d for d in mk if d.get("new_team")]
    say(f"  market deals with a new team {pct(len(new_team) / max(1, len(mk)))} [~50-57%, OTC team field, rough]")
    say()
    # Ladder
    say("PAY LADDER AT WEEK 1: Nth best-paid at each position (average per year, share of the cap at signing)")
    ranks = (1, 3, 5, 10, 16, 24, 32, 48, 64, 96)
    say("  pos   " + "".join(f"{'#' + str(r):>13}" for r in ranks))
    for g in ("QB", "WR", "EDGE", "T", "DT", "CB", "LB", "S", "G", "RB", "TE", "C", "K", "P", "FB", "LS"):
        lists = stats["ladder"][g]
        real_l = REAL_C["positions"][g]["ladder_active_2022"]
        cells = []
        for r in ranks:
            vals = [v[r - 1] for v in lists if len(v) >= r]
            rv = real_l.get(str(r))
            if not vals and rv is None:
                cells.append(" " * 13)
                continue
            s = f"{100 * st.mean(vals):.1f}" if vals else "-"
            cells.append(f"{s:>6} [{100 * rv:.1f}]".rjust(13) if rv is not None else f"{s:>6}      ".rjust(13))
        say(f"  {g:5} " + "".join(cells))
    say()
    say("POSITIONAL SPENDING (share of all cap dollars on contracts, week 1)")
    real_sp = REAL_C["active_cap_share_by_position"]
    say("  " + "  ".join(f"{g} {100 * st.mean(stats['spend'][g]):.1f} [{100 * real_sp[g]:.1f}]"
                         for g in sorted(real_sp, key=lambda k: -real_sp[k]) if stats["spend"][g]))
    say()
    say("TEAM PAYROLLS AT WEEK 1 (everyone counts)")
    pr = sorted(stats["payroll"])
    rm = sorted(stats["room"])
    say(f"  cap used: average {pct(st.mean(pr))}, lowest {pct(pr[0])}, 10th pct {pct(pr[len(pr) // 10])}, "
        f"90th pct {pct(pr[9 * len(pr) // 10])}, highest {pct(pr[-1])}  [real teams spend close to the cap]")
    say(f"  cap room: median {pct(st.median(rm))} of the cap; dead money average {pct(st.mean(stats['dead']))} "
        f"[real 2023-25: roughly 5-10% of the cap a team]")
    say()
    say("CAP ROOM WHEN FREE AGENCY OPENS (share of the cap, AI teams; real March 2024 in brackets, teams over "
        "the cap counted as 0)")
    real = sorted((x / REAL_CAP_2024 for x in REAL_FA_OPEN_2024), reverse=True)
    for label, rank in (("most room", 0), ("2nd", 1), ("5th", 4), ("8th", 7), ("median", None), ("24th", 23)):
        vals = [(st.median(v) if rank is None else v[rank]) for v in stats["fa_open"] if len(v) > (rank or 0)]
        rv = st.median(real) if rank is None else real[rank]
        say(f"  {label:10} {pct(st.mean(vals))}  [{pct(rv)}]")
    low = [sum(1 for x in v if x < 0.02) for v in stats["fa_open"]]
    say(f"  teams with under 2% of the cap: {st.mean(low):.1f} a year  [7-8 of 32 in 2024 and 2025]")
    say()
    years = sorted(REAL_FA_DAY1)
    say("CAP ROOM AFTER FREE AGENCY'S FIRST WAVE (share of the cap, AI teams; real just after the league year "
        f"opened: target = {REAL_FA_DAY1_TARGET_YEARS[0]}-{REAL_FA_DAY1_TARGET_YEARS[-1]} average, then "
        f"{' | '.join(str(y) for y in years)})")
    reals = {y: sorted((x / c for x in v), reverse=True) for y, (c, v) in REAL_FA_DAY1.items()}
    for label, rank in (("most room", 0), ("2nd", 1), ("5th", 4), ("8th", 7), ("median", None), ("24th", 23)):
        vals = [(st.median(v) if rank is None else v[rank]) for v in stats["fa_day1"] if len(v) > (rank or 0)]
        rv = {y: (st.median(r) if rank is None else r[rank]) for y, r in reals.items()}
        target = st.mean(rv[y] for y in REAL_FA_DAY1_TARGET_YEARS)
        say(f"  {label:10} {pct(st.mean(vals))}  [target {pct(target)}; {' | '.join(pct(rv[y]) for y in years)}]")
    low = [sum(1 for x in v if x < 0.02) for v in stats["fa_day1"]]
    lows = {y: sum(1 for x in r if x < 0.02) for y, r in reals.items()}
    say(f"  teams with under 2% of the cap: {st.mean(low):.1f} a year  "
        f"[target {st.mean(lows[y] for y in REAL_FA_DAY1_TARGET_YEARS):.1f}; {' | '.join(str(lows[y]) for y in years)}]")
    say()
    say("ROOKIE SCALE (average per year, share of the cap) by round: sim [real median 2017-22]")
    rk = defaultdict(list)
    for d in stats["deals"]:
        if d["kind"] == "rookie" and d.get("pick"):
            rk[(d["pick"] - 1) // 32 + 1].append(d["apy_share"])
    real_rk = REAL_C["rookie_scale_by_round"]
    say("  " + "  ".join(f"R{r} {100 * st.median(rk[r]):.2f}% [{100 * real_rk[str(r)]['median']:.2f}%]"
                         for r in range(1, 8) if rk[r]))
    say()
    y = stats["year"]
    say("THE LEAGUE YEAR, per season")
    say(f"  re-signed before free agency {y['resigned'] / S:.0f}, ERFA kept {y['erfa'] / S:.0f}, RFA tenders "
        f"{y['rfa_tenders'] / S:.0f}, let go {y['let_go'] / S:.0f}, reserve/future deals {y['futures'] / S:.0f}")
    say(f"  extensions {y['extensions'] / S:.0f}, fifth-year options exercised {y['options'] / S:.0f}, "
        f"franchise tags {y['tags'] / S:.1f} [{REAL_TAGS[0]}-{REAL_TAGS[1]}], tagged players signed long-term "
        f"{y['tag_long_term'] / S:.1f}, cap cuts {y['cap_cuts'] / S:.0f}")
    say(f"  free agent signings before the draft {y['fa_signed_pre'] / S:.0f}, after {y['fa_signed_post'] / S:.0f};"
        f" by wave: " + ", ".join(f"{w}: {stats['waves'][w] / S:.0f} ({stats['waves_market'][w] / S:.0f} market)"
                                   for w in sorted(stats['waves'])))
    say(f"  cut at the cut-down {y['cut_down'] / S:.0f}; free agents left unsigned at week 1 {y['unsigned_fa_week1'] / S:.0f}")
    say()


def fair_price_report(stats):
    """FOF8's cheap-star exploit: good players signing far below their worth
    while teams still have room. Two views: the same yardstick as the real NFL
    (last season's starters, 30 or younger, signing with a new team, against
    what real good free agents at the position signed for), and the game's own
    (good ratings too, against his market price)."""
    S = stats["seasons"]
    rf = REAL_FP
    real_val = rf["market_value"]
    say("FAIR PRICE: DO GOOD FREE AGENTS SIGN FAR BELOW THEIR WORTH? (FOF8's cheap-star exploit)")
    say(f"  A. Same yardstick as the real NFL: last season's starter (game: base-package starter on his depth chart; "
        f"real: {int(100 * rf['starter_snaps'])}%+ of snaps in the games he played), {rf['max_age']} or younger, "
        f"signed with a new team in free agency (offseason waves). Market value = what real good free agents at his "
        f"position signed for (median, share of the cap; real {rf['source'].split(';')[0]}).")
    a = [d for d in stats["fair"] if d["starter"] and d["age"] <= rf["max_age"] and d["last_team"] is not None
         and d["team"] != d["last_team"] and d["group"] in real_val]
    ra = rf["all"]
    if not a:
        say("     (no such signings)")
    else:
        for d in a:
            d["ratio_real"] = d["share"] / real_val[d["group"]]
        n = len(a)
        say(f"     per season {n / S:5.1f} [{ra['n_per_season']:.1f}]   median deal {pct(st.median(d['share'] for d in a))} "
            f"of the cap [{pct(ra['median_cap_pct'])}]")
        say(f"     under 60% of market value {pct(sum(d['ratio_real'] < 0.6 for d in a) / n)} [{pct(ra['under_60'])}]   "
            f"under 40% {pct(sum(d['ratio_real'] < 0.4 for d in a) / n)} [{pct(ra['under_40'])}]   "
            f"at about the minimum (<= 0.65%) {pct(sum(d['share'] <= M.MINIMUM_LINE for d in a) / n)} "
            f"[{pct(ra['minimum_level'])}]")
        gm = defaultdict(list)
        for d in a:
            gm[d["group"]].append(d["share"])
        say("     median deal by position, game [real]: " + "  ".join(
            f"{g} {100 * st.median(v):.1f} [{100 * real_val[g]:.1f}]"
            for g, v in sorted(gm.items(), key=lambda kv: -len(kv[1]))))
        by_w = Counter(d["wave"] for d in a)
        cheap_w = Counter(d["wave"] for d in a if d["ratio_real"] < FAIR_LINE)
        say("     by wave (signed / under 60%): " + ", ".join(f"{w}: {by_w[w]} / {cheap_w[w]}" for w in sorted(by_w)))
    # B. The game's own view: good ratings too, against the game's own price for him.
    say("  B. The game's own view: good ratings too (rated as a starter league-wide, priced 1%+ of the cap), "
        f"{rf['max_age']} or younger, any team, against his market price the day the wave opened. Real reference: A.")
    b = [d for d in stats["fair"] if d["good_rating"] and d["age"] <= rf["max_age"]]
    if not b:
        say("     (no such signings)")
        say()
        return
    for d in b:
        d["ratio"] = d["share"] / d["price"]
    cheap = [d for d in b if d["ratio"] < FAIR_LINE]
    n = len(b)
    say(f"     per season {n / S:5.1f}; median deal {pct(st.median(d['ratio'] for d in b))} of his price; "
        f"under 60% of his price {pct(len(cheap) / n)} ({len(cheap) / S:.1f} a season); under 40% "
        f"{pct(sum(d['ratio'] < 0.4 for d in b) / n)}; last season's starters among them "
        f"{pct(sum(d['starter'] for d in b) / n)}")
    by_w = Counter(d["wave"] for d in b)
    cheap_w = Counter(d["wave"] for d in cheap)
    say("     by wave (signed / under 60%): " + ", ".join(f"{w}: {by_w[w]} / {cheap_w[w]}" for w in sorted(by_w)))
    tiers = (("1-2% of the cap", 0.0, 0.02), ("2-5%", 0.02, 0.05), ("5%+ (stars)", 0.05, 9.0))
    say("     by his price: " + "   ".join(
        f"{label}: {len(t) / S:.1f} a season, under 60% {pct(sum(d['ratio'] < FAIR_LINE for d in t) / max(1, len(t)))}"
        for label, lo, hi in tiers for t in [[d for d in b if lo <= d["price"] < hi]]))
    if cheap:
        able = [sum(r >= d["price"] for r in d["rooms"]) for d in cheap]
        med = [st.median(d["rooms"]) for d in cheap if d["rooms"]]
        say(f"     when one of them signed under 60%: other AI teams with spendable room for his full price "
            f"{st.mean(able):.1f} on average (median {st.median(able)}); their median spendable room "
            f"{pct(st.mean(med))} of the cap")
        say("     cheapest (age, rating, price -> deal, wave, other teams with room for his price):")
        for d in sorted(cheap, key=lambda d: d["ratio"])[:8]:
            say(f"       {d['league']} {d['season']} {d['pos']:3} {d['name']}, {d['age']}, ovr {d['ovr']}: price "
                f"{pct(d['price'])} -> {pct(d['share'])} ({100 * d['ratio']:.0f}%), wave {d['wave']}, "
                f"{sum(r >= d['price'] for r in d['rooms'])} teams had room"
                f"{'; starter last season' if d['starter'] else ''}")
    u = stats.get("camp_unsigned") or []
    say(f"  C. Still unsigned when camp opens (good ratings, {rf['max_age']} or younger; the late-bargain window: you can "
        f"sign any of them at his ask): {len(u) / S:.1f} a season")
    if u:
        say(f"     last season's starters {pct(sum(d['starter'] for d in u) / len(u))}; median rating {st.median(d['ovr'] for d in u):.0f}; "
            f"median price {pct(st.median(d['price'] for d in u))} of the cap, asking {pct(st.median(d['ask'] for d in u))} "
            f"({pct(st.median(d['ask'] / d['price'] for d in u))} of his price); priced 5%+ (stars) {sum(d['price'] >= 0.05 for d in u) / S:.1f} a season")
    say()


def top_signings(lg, n=12):
    """The biggest deals of the league's latest league year, as report lines."""
    S = lg.season
    ds = sorted((d for d in lg.contract_log if d["season"] == S and d["kind"] not in ("rookie", "practice")),
                key=lambda d: -d["apy"])[:n]
    out = [f"Biggest deals of the {S} league year in {lg.name or 'the league'}:"]
    for d in ds:
        p = lg.player(d["pid"])
        team = lg.team(d["team"]).abbrev
        out.append(f"  {team} {d['pos']:3} {p.first_name} {p.last_name}, {d['age']}, ovr {p.overall()}: {d['kind']} "
                   f"{d['years']}y {C.fmt_money(d['value'])} ({C.fmt_money(d['apy'])}/yr, {pct(d['apy_share'])} of "
                   f"cap), {C.fmt_money(d['guaranteed'])} gtd{'  (new team)' if d['new_team'] else ''}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="101,102")
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--games", action="store_true", help="play the real sim's games (slow)")
    args = ap.parse_args()
    t0 = time.time()
    seeds = [int(x) for x in args.leagues.split(",")]
    stats, day1, top = collect(seeds, args.seasons, "real" if args.games else "fast")
    say(f"Day 1 (new leagues at their first week 1): cap used average {pct(st.mean(day1['payroll']))} "
        f"(lowest {pct(min(day1['payroll']))}, highest {pct(max(day1['payroll']))}), dead money {pct(st.mean(day1['dead']))}")
    say("  ladder #1/#5/#10/#32 QB " + " / ".join(
        f"{100 * st.mean(v[r - 1] for v in day1['ladder']['QB']):.1f}" for r in (1, 5, 10, 32))
        + "  WR " + " / ".join(f"{100 * st.mean(v[r - 1] for v in day1['ladder']['WR']):.1f}" for r in (1, 5, 10, 32)))
    ins = stats["in_season"]
    if ins:
        n_s = max(1, len(stats["season_units"]))
        say(f"Signed during the seasons: {len(ins) / n_s:.0f} deals a season; "
            f"minimum {pct(sum(1 for d in ins if d['apy_share'] <= M.MINIMUM_LINE) / len(ins))}, "
            f"one-year {pct(sum(1 for d in ins if d['years'] == 1) / len(ins))}")
    say()
    report(stats, len(seeds))
    fair_price_report(stats)
    for line in top:
        say(line)
    say(f"\n({time.time() - t0:.0f} s, {'real' if args.games else 'fast'} games)")
    (ROOT / "tools" / "free_agency_report.txt").write_text("\n".join(out_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
