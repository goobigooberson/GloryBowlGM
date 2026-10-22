# injury_report.py
# The week-to-week life of injuries, shared by the season loop and the
# realism tools so both play by the same rules (engine/injuries.py has the
# real-data numbers):
#   - who can't play this week; who plays hurt (listed Questionable) and how
#     much it costs him, by injury
#   - after a game: injuries from it; playing through an injury can aggravate
#     it; in a player's first games back it can flare up (by injury)
#   - game-day status for the next game: Out / Doubtful / Questionable /
#     Injured reserve / Concussion protocol
#   - each week: injuries heal by a week
#
# State: `injuries` {player id: {team, weeks left, part, week hurt, kind,
# initial, status}} and `recovering` {player id: {kind, team, games}}, plain
# dicts the caller owns (the season keeps them on the League and saves them).
# `dice(cal, pid, what)` gives a random.Random for one player and week (the
# season seeds it so a week replays the same).

from . import injuries as I


class InjuryReport:
    def __init__(self, injuries, recovering, dice, on_injury=None):
        """on_injury(pid, team, kind, weeks, how): told about every injury, for
        a player's injury history. how: "" (new), "played through" (a knock
        that cost no games), "aggravated", "re-injured"."""
        self.injuries = injuries
        self.recovering = recovering
        self.dice = dice
        self.on_injury = on_injury or (lambda *a: None)

    # ---- Before a game ------------------------------------------------------
    def unavailable(self, team_id, cal):
        """Players who can't play this week because of an injury from an earlier week."""
        return {pid for pid, inj in self.injuries.items()
                if inj["team"] == team_id and inj["weeks"] > 0 and inj["week"] < cal}

    def playing_hurt(self, team_id, cal):
        """{player id: rating points off} for players listed Questionable this
        week who play (by injury: a hamstring slows a player down, a bruised
        hand barely matters; injuries.RECOVERY)."""
        return {pid: I.recovery(inj.get("kind"))[0] for pid, inj in self.injuries.items()
                if inj["team"] == team_id and inj["weeks"] <= 0 and inj.get("status") == "Questionable"
                and inj["week"] < cal}

    # ---- After a game -------------------------------------------------------
    def after_game(self, team_ids, cal, played_ids, game_injuries):
        """game_injuries: {team id: [(pid, weeks out, kind)]} from the game.
        Returns [(pid, kind, weeks)] for injuries that cost games."""
        listed = set()
        for pid, inj in list(self.injuries.items()):
            if (inj["team"] in team_ids and inj["weeks"] <= 0 and inj.get("status") == "Questionable"
                    and inj["week"] < cal and pid in played_ids):
                listed.add(pid)
                rng = self.dice(cal, pid, "aggravate")
                if rng.random() < I.recovery(inj.get("kind"))[1]:
                    self._flare_up(pid, inj.get("kind"), inj["team"], cal, rng, "aggravated")
        for pid, rec in list(self.recovering.items()):
            if rec["team"] not in team_ids or pid not in played_ids:
                continue
            if pid not in listed:
                rng = self.dice(cal, pid, "flare")
                if rng.random() < I.recovery(rec["kind"])[2]:
                    self._flare_up(pid, rec["kind"], rec["team"], cal, rng, "re-injured")
                    self.recovering.pop(pid, None)
                    continue
            rec["games"] -= 1
            if rec["games"] <= 0:
                self.recovering.pop(pid, None)
        new = []
        for tid, hurt in game_injuries.items():
            for pid, weeks_out, kind in hurt:
                if weeks_out > 0:
                    new.append(self.add_injury(pid, tid, kind, weeks_out, cal))
                elif pid not in self.injuries or self.injuries[pid]["weeks"] <= 0:
                    # A knock that cost no games: listed Questionable for the next game (he plays).
                    if self.dice(cal, pid, "minor").random() < I.MINOR_QUESTIONABLE:
                        self.injuries[pid] = {"team": tid, "weeks": 0, "part": I.name(kind), "week": cal,
                                              "kind": kind, "initial": 0, "status": "Questionable"}
                    self.on_injury(pid, tid, kind, 0, "played through")
        return new

    def add_injury(self, pid, tid, kind, weeks_out, cal, how=""):
        """A new injury that costs games (from a game or a practice). A
        'season' injury lasts 12-16 weeks about 1 time in 11 (injuries.py).
        Returns (pid, kind, weeks)."""
        if weeks_out >= I.SEASON_ENDING_WEEKS:
            rng = self.dice(cal, pid, "length")
            if rng.random() < I.SEASON_GROUP_RETURNS:
                weeks_out = rng.randint(*I.SEASON_GROUP_RETURN_WEEKS)
        old = self.injuries.get(pid)
        self.injuries[pid] = {"team": tid, "weeks": weeks_out, "part": I.name(kind), "week": cal,
                              "kind": kind, "initial": weeks_out}
        if old and old.get("reserve"):
            self.injuries[pid]["reserve"] = old["reserve"]
        self.recovering.pop(pid, None)
        self.set_status(pid, self.injuries[pid], cal)
        self.on_injury(pid, tid, kind, weeks_out, how)
        return pid, kind, weeks_out

    def practice_injuries(self, teams, cal, per_team, how="", weight=None, key="practice"):
        """Game-costing injuries in a week of practice (training camp and the
        preseason). teams: {team id: [players practicing]}; per_team: expected
        injuries per team this week. Durable players get hurt less often and
        less badly (the same rules as games). weight: optional {pid: how much
        more or less he's exposed} (1.0 = the team's average). Returns
        [(pid, kind, weeks)]."""
        from .sim import tuning as T
        import math
        new = []
        for tid, players in teams.items():
            healthy = [p for p in players if not (p.id in self.injuries and self.injuries[p.id]["weeks"] > 0)]
            if not healthy:
                continue
            w = {p.id: math.exp(-T.DURABILITY_K * ((p.durability if p.durability is not None else 50) - 50) / 15)
                 * (weight.get(p.id, 1.0) if weight else 1.0) for p in healthy}
            mean_w = sum(w.values()) / len(w)
            for p in healthy:
                rng = self.dice(cal, p.id, key)
                if rng.random() < per_team * w[p.id] / mean_w / len(healthy):
                    dur = p.durability if p.durability is not None else 50
                    u = min(0.999, max(0.0, rng.random() - T.DURABILITY_SEVERITY * (dur - 50) / 15))
                    grp, lo, hi = I.length_group(u)
                    weeks = lo + int(rng.random() * (hi - lo + 1))
                    kind = I.pick_kind(grp, rng.random())
                    new.append(self.add_injury(p.id, tid, kind, weeks, cal, how))
        return new

    def _flare_up(self, pid, kind, team, cal, rng, how):
        """The injury came back: he misses 1-3 more games."""
        weeks = rng.randint(*I.AGGRAVATE_WEEKS)
        self.injuries[pid] = {"team": team, "weeks": weeks, "part": f"{I.name(kind)} ({how})",
                              "week": cal, "kind": kind, "initial": weeks, "aggravated": True}
        self.set_status(pid, self.injuries[pid], cal)
        self.on_injury(pid, team, kind, weeks, how)

    # ---- Game-day status ----------------------------------------------------
    def set_status(self, pid, inj, cal):
        """Status for his next game (real NFL report patterns, injuries.py)."""
        w = inj["weeks"]
        if inj.get("reserve"):
            # On a reserve list (transactions.py): that's his status until he's activated.
            inj["status"] = "Injured reserve" if inj["reserve"] == "IR" else "Physically unable to perform"
        elif w <= 0:
            inj["status"] = "Questionable"
        elif I.is_concussion(inj.get("kind")):
            # The NFL's concussion protocol: he can't play until he's cleared.
            inj["status"] = "Concussion protocol"
        elif inj.get("initial", w) >= I.INJURED_RESERVE_WEEKS:
            # A long injury still on the 53 (not moved to injured reserve): listed Out.
            inj["status"] = "Out"
        else:
            table = I.STATUS_LAST_MISSED if w == 1 else I.STATUS_STILL_OUT
            inj["status"] = I.pick_status(table, self.dice(cal, pid, "status").random())

    def status(self, pid):
        """'Out', 'Doubtful', 'Questionable', 'Injured reserve', 'Concussion
        protocol', or None (healthy)."""
        inj = self.injuries.get(pid)
        if not inj:
            return None
        if inj.get("status"):
            return inj["status"]
        return "Out" if inj["weeks"] > 0 else None       # saves from before game-day statuses

    # ---- End of the week ----------------------------------------------------
    def end_week(self, cal):
        """Heal everyone by a week; set statuses for next week's game."""
        for pid in list(self.injuries):
            inj = self.injuries[pid]
            if inj["week"] >= cal:
                continue                       # hurt in this week's game: his first missed game is next week
            if inj["weeks"] <= 0:
                del self.injuries[pid]         # a Questionable listing for this week's game: done
                continue
            inj["weeks"] -= 1
            if inj["weeks"] > 0:
                self.set_status(pid, inj, cal + 1)
                continue
            # Healed. His first few games back carry a chance it flares up (by injury).
            if inj.get("kind"):
                self.recovering[pid] = {"kind": inj["kind"], "team": inj["team"], "games": I.COMEBACK_GAMES}
            if (not I.is_concussion(inj.get("kind"))
                    and self.dice(cal, pid, "return").random() < I.RETURN_QUESTIONABLE):
                # Still on the report for his first game back (he plays). (A player
                # cleared from the concussion protocol is cleared.)
                inj.update(weeks=0, week=cal, status="Questionable")
            else:
                del self.injuries[pid]
