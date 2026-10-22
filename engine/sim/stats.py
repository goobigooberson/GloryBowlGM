# stats.py
# The box score: every player's and team's stats, built up play by play.

from collections import defaultdict


def _blank():
    return defaultdict(float)


class BoxScore:
    def __init__(self, game):
        self.game = game
        self.players = defaultdict(_blank)     # player id -> stat -> value
        self.owner = {}                        # player id -> team index
        self.team = [defaultdict(float), defaultdict(float)]
        self.quarter_points = [[0, 0, 0, 0], [0, 0, 0, 0]]
        self.drives = []
        self.scoring = []

    # ---- helpers ----
    def _p(self, player, team_idx):
        self.owner[player.id] = team_idx
        return self.players[player.id]

    def add(self, player, team_idx, key, value=1):
        if player is None:
            return
        self._p(player, team_idx)[key] += value

    def best(self, player, team_idx, key, value):
        if player is None:
            return
        line = self._p(player, team_idx)
        if value > line[key]:
            line[key] = value

    def points(self, team_idx, qtr, pts):
        q = min(qtr, 5) - 1
        while len(self.quarter_points[team_idx]) <= q:
            self.quarter_points[0].append(0)
            self.quarter_points[1].append(0)
        self.quarter_points[team_idx][q] += pts

    def snaps(self, ids, team_idx, key):
        for pid in ids:
            self.owner.setdefault(pid, team_idx)
            self.players[pid][key] += 1

    # ---- crediting a play ----
    def credit(self, res, off_idx, before):
        """Credit stats for a scrimmage play that counted (not erased by a penalty)."""
        d_idx = 1 - off_idx
        t = self.team[off_idx]
        dt = self.team[d_idx]
        kind = res.kind
        if kind in ("run", "sneak", "scramble"):
            r = res.rusher
            self.add(r, off_idx, "rush_att")
            self.add(r, off_idx, "rush_yds", res.yards)
            self.best(r, off_idx, "rush_long", res.yards)
            t["rush_att"] += 1
            t["rush_yds"] += res.yards
            if kind == "scramble":
                t["scrambles"] += 1
                t["scramble_yds"] += res.yards
                t["dropbacks"] += 1
            else:
                t["designed_runs"] += 1
                t["designed_yds"] += res.yards
            if res.td:
                self.add(r, off_idx, "rush_td")
                t["rush_td"] += 1
            if res.first_down and not res.td:
                self.add(r, off_idx, "rush_1d")
        elif kind == "pass":
            qb = res.passer
            self.add(qb, off_idx, "pass_att")
            t["pass_att"] += 1
            t["dropbacks"] += 1
            if res.receiver is not None:
                self.add(res.receiver, off_idx, "targets")
            if res.complete:
                self.add(qb, off_idx, "pass_cmp")
                self.add(qb, off_idx, "pass_yds", res.yards)
                self.best(qb, off_idx, "pass_long", res.yards)
                self.add(res.receiver, off_idx, "rec")
                self.add(res.receiver, off_idx, "rec_yds", res.yards)
                self.add(res.receiver, off_idx, "rec_yac", res.yac)
                self.best(res.receiver, off_idx, "rec_long", res.yards)
                t["pass_cmp"] += 1
                t["pass_yds"] += res.yards
                if res.td:
                    self.add(qb, off_idx, "pass_td")
                    self.add(res.receiver, off_idx, "rec_td")
                    t["pass_td"] += 1
            if res.dropped:
                self.add(res.receiver, off_idx, "drops")
            if res.interception:
                self.add(qb, off_idx, "pass_int")
                t["int_thrown"] += 1
                self.add(res.interceptor, d_idx, "def_int")
                self.add(res.interceptor, d_idx, "int_yds", res.return_yards)
                self.add(res.interceptor, d_idx, "pd")
                if res.def_td:
                    self.add(res.interceptor, d_idx, "def_td")
            if res.pd_by is not None:
                self.add(res.pd_by, d_idx, "pd")
        elif kind == "sack":
            qb = res.passer
            self.add(qb, off_idx, "sacked")
            self.add(qb, off_idx, "sacked_yds", -res.yards)
            t["sacked"] += 1
            t["sacked_yds"] += -res.yards
            t["dropbacks"] += 1
            share = 1.0 / len(res.sackers) if res.sackers else 0
            for s in res.sackers:
                self.add(s, d_idx, "sacks", share)
                if res.yards < 0 and len(res.sackers) == 1:
                    self.add(s, d_idx, "tfl")         # NFL: a shared sack gives no tackle for loss
                self.add(s, d_idx, "tkl" if len(res.sackers) == 1 else "ast")
            if res.safety and res.sackers:
                self.add(res.sackers[0], d_idx, "safeties")
        elif kind == "kneel":
            self.add(res.rusher, off_idx, "rush_att")
            self.add(res.rusher, off_idx, "rush_yds", res.yards)
            t["rush_att"] += 1
            t["rush_yds"] += res.yards
            t["kneels"] += 1
        elif kind == "spike":
            self.add(res.passer, off_idx, "pass_att")
            t["pass_att"] += 1
            t["spikes"] += 1
        if res.qb_hit_by is not None:
            self.add(res.qb_hit_by, d_idx, "qb_hits")
            t["qb_hits_taken"] += 1
        if res.tacklers and kind not in ("sack",):
            # NFL scoring: a tackle made alone is a solo tackle ("tkl"); when two
            # players bring him down, each gets an assisted tackle ("ast").
            if res.assist is not None:
                self.add(res.tacklers[0], d_idx, "ast")
                self.add(res.assist, d_idx, "ast")
            else:
                self.add(res.tacklers[0], d_idx, "tkl")
            # Tackles for loss: runs stopped behind the line, and catches
            # dropped for a loss of 2+ (the sim throws a few more completions
            # behind the line than the NFL; 2+ keeps the count at the real level).
            if res.tfl or (kind in ("run", "sneak") and res.yards < 0) or (kind == "pass" and res.yards <= -2):
                self.add(res.tacklers[0], d_idx, "tfl")
            if res.safety and kind in ("run", "sneak", "scramble"):
                self.add(res.tacklers[0], d_idx, "safeties")
        if res.fumble:
            carrier = res.rusher or (res.receiver if res.complete else None) or res.passer
            self.add(carrier, off_idx, "fum")
            t["fum"] += 1
            if res.forced_by is not None:
                self.add(res.forced_by, d_idx, "ff")
            if res.fumble_lost:
                self.add(carrier, off_idx, "fum_lost")
                t["fum_lost"] += 1
                if res.recovered_by is not None:
                    self.add(res.recovered_by, d_idx, "fr")
                    if res.def_td:
                        self.add(res.recovered_by, d_idx, "def_td")
        if kind in ("run", "sneak", "scramble", "pass", "sack", "kneel", "spike"):
            t["plays"] += 1
            gained = res.yards
            t["total_yds"] += gained
            if before.down == 3:
                t["third_att"] += 1
                if res.first_down or res.td:
                    t["third_conv"] += 1
            if before.down == 4:
                t["fourth_att"] += 1
                if res.first_down or res.td:
                    t["fourth_conv"] += 1
            if res.first_down or res.td:
                if kind in ("pass",):
                    t["fd_pass"] += 1
                elif kind != "sack":
                    t["fd_rush"] += 1

    def credit_penalty(self, pen, team_idx):
        t = self.team[team_idx]
        t["penalties"] += 1
        t["penalty_yds"] += pen.yards
        if pen.player is not None:
            self.add(pen.player, team_idx, "pen")
            self.add(pen.player, team_idx, "pen_yds", pen.yards)

    def credit_kick(self, res, kick_idx):
        recv_idx = 1 - kick_idx
        k = self.team[kick_idx]
        r = self.team[recv_idx]
        if res.kind in ("punt", "kickoff") and res.returner is not None and (res.fumble or res.muffed):
            # Return fumbles and muffed punts count as the returner's fumbles and in his
            # team's fumbles lost, as the NFL counts them (before Oct 22 they weren't counted).
            self.add(res.returner, recv_idx, "fum")
            r["fum"] += 1
            if res.fumble_lost:
                self.add(res.returner, recv_idx, "fum_lost")
                r["fum_lost"] += 1
        if res.kind == "punt":
            self.add(res.punter, kick_idx, "punts")
            self.add(res.punter, kick_idx, "punt_yds", res.kick_distance)
            self.best(res.punter, kick_idx, "punt_long", res.kick_distance)
            k["punts"] += 1
            k["punt_yds"] += res.kick_distance
            if res.blocked:
                self.add(res.punter, kick_idx, "punt_blocked")
            if res.touchback:
                self.add(res.punter, kick_idx, "punt_tb")
                k["punt_tb"] += 1
            if res.new_yl is not None and res.new_yl >= 80 and not res.touchback and not res.blocked:
                self.add(res.punter, kick_idx, "punt_in20")
            if res.returner is not None and not res.fair_catch and not (res.muffed and res.fumble_lost):
                self.add(res.returner, recv_idx, "pr")
                self.add(res.returner, recv_idx, "pr_yds", res.return_yards)
                self.best(res.returner, recv_idx, "pr_long", res.return_yards)
                r["pr"] += 1
                r["pr_yds"] += res.return_yards
                self.add(res.punter, kick_idx, "punt_ret_yds", res.return_yards)
                if res.def_td:
                    self.add(res.returner, recv_idx, "pr_td")
                    r["ret_td"] += 1
            if res.fair_catch:
                self.add(res.returner, recv_idx, "pr_fc")
        elif res.kind == "kickoff":
            if res.returner is not None and not res.touchback:
                self.add(res.returner, recv_idx, "kr")
                self.add(res.returner, recv_idx, "kr_yds", res.return_yards)
                self.best(res.returner, recv_idx, "kr_long", res.return_yards)
                r["kr"] += 1
                r["kr_yds"] += res.return_yards
                if res.def_td:
                    self.add(res.returner, recv_idx, "kr_td")
                    r["ret_td"] += 1
        elif res.kind == "fg":
            self.add(res.kicker, kick_idx, "fga")
            band = _fg_band(res.kick_distance)
            self.add(res.kicker, kick_idx, f"fga_{band}")
            k["fga"] += 1
            if res.made:
                self.add(res.kicker, kick_idx, "fgm")
                self.add(res.kicker, kick_idx, f"fgm_{band}")
                self.best(res.kicker, kick_idx, "fg_long", res.kick_distance)
                k["fgm"] += 1
            if res.blocked:
                self.add(res.kicker, kick_idx, "fg_blocked")
        elif res.kind == "xp":
            self.add(res.kicker, kick_idx, "xpa")
            k["xpa"] += 1
            if res.made:
                self.add(res.kicker, kick_idx, "xpm")
                k["xpm"] += 1
        # Coverage tackles count in a player's tackle totals, like the NFL's
        # official stats; st_tkl keeps the special teams count on its own.
        if res.tacklers and res.kind in ("kickoff", "punt"):
            if res.assist is not None:
                for tk in (res.tacklers[0], res.assist):
                    self.add(tk, kick_idx, "ast")
                    self.add(tk, kick_idx, "st_tkl")
            else:
                self.add(res.tacklers[0], kick_idx, "tkl")
                self.add(res.tacklers[0], kick_idx, "st_tkl")


def _fg_band(d):
    if d < 30:
        return "0_29"
    if d < 40:
        return "30_39"
    if d < 50:
        return "40_49"
    return "50"


def passer_rating(att, cmp_, yds, td, ints):
    if att <= 0:
        return 0.0
    a = max(0, min(2.375, (cmp_ / att - 0.3) * 5))
    b = max(0, min(2.375, (yds / att - 3) * 0.25))
    c = max(0, min(2.375, td / att * 20))
    d = max(0, min(2.375, 2.375 - ints / att * 25))
    return (a + b + c + d) / 6 * 100
