# tools/make_test_saves.py
# The standard test saves: one command rebuilds a fixed set of saves at every
# moment of a game's year, made through the same engine calls the screens make
# (New game's startup draft, Sim week, Start the offseason, the offseason's
# Next button, the Contracts tab's franchise tag and free agency offers, the
# draft room). Your team is a human team, as in a real game
# (league.user_team_id is set).
#
#   python tools/make_test_saves.py                 # ~2 minutes; the saves go in tools/data/test_saves/
#   python tools/make_test_saves.py --games fast    # made-up game results (screens without real stats)
#   python tools/make_test_saves.py --seed 7 --team DAL
#
# The same seed and team always make the same saves (each one's "fingerprint"
# in index.json shows it: rosters, contracts and ratings; the files' saved-at
# times differ). The folder is git-ignored and is wiped and rebuilt each time;
# your own saves (saves/) are never touched.
#
# Games: the first season is played with the real game sim by default, because
# almost every screen shows its stats (box scores, leaders, awards, Bitter).
# The offseason plays no games, so nothing there is faster with --games fast.
#
# The moments, in order (index.json lists each with what to expect on screen):
#   01 startup draft, you on the clock     11 offseason: you franchise-tagged a player
#   02 new game (startup draft done, camp) 12 free agency wave 1 (one offer of yours out)
#   03 preseason (two weeks in)            13 free agency wave 2 (one offer of yours out)
#   04 mid-season (week 8 next)            14 the draft is next (last scouting)
#   05 trade deadline week (week 9 next)   15 draft day: pick 1 on the clock
#   06 regular season over (Wild Card next)16 the draft: you on the clock
#   07 playoffs (divisional round next)    17 after the draft (free agency wave 5)
#   08 season complete (Glory Bowl played) 18 free agency over (training camp next)
#   09 offseason: coaching carousel        19 training camp open (next preseason, 90-man rosters)
#   10 offseason: re-sign your players

import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from engine import draft_day as DD                        # noqa: E402
from engine import free_agency as FA                      # noqa: E402
from engine import gm as GM                               # noqa: E402
from engine import saves                                  # noqa: E402
from engine import season as SEASON                       # noqa: E402
from engine.database import save_league, write_history    # noqa: E402
from engine.league import create_league                   # noqa: E402
import lab as LAB                                         # noqa: E402

OUT_DIR = ROOT / "tools" / "data" / "test_saves"
SEED = 2026
TEAM = "PIT"
FIRST_SEASON = 2026
# New game's defaults (screens/new_game_page.py, settings_now)
SETTINGS = {"season_games": 17, "roster_method": "startup_draft", "owner_can_fire": False}


class Builder:
    def __init__(self, out, seed, team, games):
        self.out, self.seed, self.games = out, seed, games
        self.index = []
        self.history = None          # stands in for a save whose history file (finished seasons' box scores) is copied
        self.t0 = time.time()
        self.league = self._new_game(team)

    # ---- New game -------------------------------------------------------------
    def _new_game(self, team):
        """What New game does with "Startup draft" (state.generate_league ->
        draft_day.startup_league, then state.start_new_game), with a seed so the
        same league comes out every time."""
        league = create_league(season=FIRST_SEASON, seed=self.seed, camp=False)
        league.settings.update(SETTINGS)
        DD.startup_order(league, random.Random(f"startup-order-{league.settings['salt']}"))
        tid = next((t.id for t in league.teams if t.abbrev == team), None)
        if tid is None:
            raise SystemExit(f"No team {team!r}; pick one of: {' '.join(t.abbrev for t in league.teams)}")
        league.user_team_id = tid
        league.name = f"Test league {self.seed}"
        GM.ensure(league)
        DD.startup_begin(league)
        return league

    # ---- Saving ---------------------------------------------------------------
    def save(self, key, title, expect=(), note=""):
        lg = self.league
        path = self.out / f"{key}.db"
        lg.name = f"Test {key[:2]}: {title}"
        save_league(lg, path)
        if self.history is not None:
            saves.copy_history(self.history, path)      # (copies the history file beside it)
        entry = {"key": key, "file": path.name, "name": lg.name, "title": title,
                 "season": lg.season, "stage": lg.stage, "week": lg.week,
                 "phase": (SEASON.offseason_phase(lg) or [None])[0],
                 "wave": (lg.offseason or {}).get("wave") if SEASON.in_offseason(lg) else None,
                 "expect": list(expect), "note": note, "fingerprint": LAB.fingerprint(lg)}
        self.index.append(entry)
        print(f"  {key:<24} {title}  ({time.time() - self.t0:.0f}s)" + (f"  [{note}]" if note else ""))

    # ---- Playing --------------------------------------------------------------
    def _patch(self):
        if self.games != "fast":
            return None
        saved = (SEASON.Game, SEASON.build_norms)
        SEASON.Game = LAB.FakeGame
        SEASON.build_norms = lambda league: None
        return saved

    def sim_week(self):
        """Sim week (main_page.sim_through -> season.play_week)."""
        saved = self._patch()
        try:
            self._cap_ok(lambda: SEASON.play_week(self.league))
        finally:
            if saved is not None:
                SEASON.Game, SEASON.build_norms = saved

    def sim_until(self, done):
        while not done(self.league):
            if SEASON.season_over(self.league):
                raise RuntimeError("the season ended before the moment was reached")
            self.sim_week()

    def next_phase(self):
        """The offseason's Next button (state.advance_offseason)."""
        return self._cap_ok(lambda: SEASON.advance_offseason(self.league))

    def _cap_ok(self, fn):
        """At the NFL's cap deadlines you can't go on while over the cap; a player
        approves his staff's suggested moves (Roster tab), as here."""
        for _ in range(30):
            try:
                return fn()
            except SEASON.CapHold:
                reqs = SEASON.staff_requests(self.league)
                if not reqs:
                    raise
                SEASON.answer_staff_request(self.league, 0, True)
        raise RuntimeError("still over the cap after 30 of the staff's moves")

    def start_offseason(self):
        """Start the offseason (main_page.next_season: the owner's review, then
        state.start_next_season: begin_offseason and the history file)."""
        GM.owner_review(self.league)
        finished = SEASON.begin_offseason(self.league)
        # (as if for a save called "_history": every later save gets a copy of its history file)
        self.history = self.out / "_history.db"
        write_history(saves.history_path(self.history), finished)

    # ---- Your decisions on the Contracts tab ----------------------------------
    def franchise_tag(self):
        """Tag one of your expiring players (Contracts tab, Re-sign: 'Franchise tag')."""
        rows = [r for r in FA.expiring_for_you(self.league) if r["tag"]]
        if not rows:
            return "no player of yours could be tagged"
        rows.sort(key=lambda r: (r["advice"] != "Tag", -r["ask"]["apy"]))
        r = rows[0]
        done, msg = FA.tag_or_tender(self.league, r["pid"], "tag")
        p = self.league.player(r["pid"])
        return f"tagged {p.position} {p.name}" if done else f"tag refused: {msg}"

    def fa_offer(self):
        """One free agency offer at his asking terms (Contracts tab, Free agency:
        'Make offer'), so 'Your offers this wave' has something in it."""
        lg = self.league
        wave = lg.fa.get("wave")
        fas = sorted(FA.free_agent_list(lg), key=lambda p: -p.overall())
        for p in fas[10:80]:       # past the very top of the market, which your cap may not fit
            ask = FA.asking_terms(lg, p.id, lg.user_team_id, wave)
            result, _msg = FA.place_offer(lg, p.id, ask["apy"], ask["years"], ask["guaranteed"])
            if result == "accept":
                return f"offer to {p.position} {p.name}"
        return "no free agent took an offer at his asking price"

    # ---- The whole year -------------------------------------------------------
    def run(self):
        lg = self.league
        S = SEASON
        # The startup draft: the AI picks until you're on the clock.
        DD.startup_sim_to_user(lg)
        self.save("01-startup-draft", "Startup draft, you're on the clock", ["startup_draft"])
        # "Finish the draft" (state.finish_startup): your staff makes the rest of your picks.
        DD.startup_finish(lg)
        self.save("02-new-game", "New game: rosters drafted, training camp open")
        self.sim_week()
        self.sim_week()
        played = ["games_played"]               # a Game summary to open
        self.save("03-preseason", "Preseason, two weeks in", played)
        self.sim_until(lambda l: S.in_regular_season(l) and l.week >= 8)
        self.save("04-midseason", "Regular season, week 8 next", played)
        from engine import trades
        self.sim_until(lambda l: S.in_regular_season(l) and l.week >= trades.deadline_week(l))
        self.save("05-trade-deadline", f"Trade deadline week (week {lg.week})", played)
        self.sim_until(S.in_playoffs)
        self.save("06-regular-season-end", "Regular season over, Wild Card round next", played)
        self.sim_until(lambda l: S.in_playoffs(l) and l.playoff_round >= 2)
        self.save("07-playoffs", "Playoffs, divisional round next", played)
        self.sim_until(S.season_over)
        self.save("08-season-complete", "Season complete, Glory Bowl played", played)

        self.start_offseason()
        expect = ["offseason_report"]
        if S.offseason_phase(lg)[0] == "coaching":
            self.save("09-coaching", "Offseason: coaching carousel", expect)
            while S.offseason_phase(lg)[0] == "coaching":
                self.next_phase()
        self.save("10-resign", "Offseason: re-sign your players", expect + ["contracts_resign"])
        self.save("11-franchise-tag", "Offseason: after your franchise tag", expect + ["contracts_resign"],
                  note=self.franchise_tag())
        self.next_phase()                       # the market opens: wave 1
        self.save("12-fa-wave1", "Free agency, wave 1", expect + ["contracts_fa"], note=self.fa_offer())
        self.next_phase()
        self.save("13-fa-wave2", "Free agency, wave 2", expect + ["contracts_fa"], note=self.fa_offer())
        while S.offseason_phase(lg)[0] == "fa":
            self.next_phase()
        self.save("14-draft-next", "The draft is next", expect)
        self.next_phase()                       # the draft starts: pick 1 on the clock
        if S.offseason_phase(lg)[0] != "drafting":
            raise RuntimeError("the draft didn't start (no picks of yours?)")
        self.save("15-draft-day", "Draft day, pick 1 on the clock", expect + ["draft_room"])
        if not DD.user_on_clock(lg):
            DD.sim_to_user(lg)
        if DD.user_on_clock(lg):
            self.save("16-draft-your-pick", "The draft, you're on the clock", expect + ["draft_room"])
        else:
            print("  (no pick of yours left in the draft: 16 skipped)")
        self.next_phase()                       # your staff makes the rest of your picks
        self.save("17-after-draft", "After the draft, free agency wave 5", expect)
        while S.offseason_phase(lg)[0] == "fa":
            self.next_phase()
        self.save("18-camp-next", "Free agency over, training camp next", expect)
        self.next_phase()                       # training camp opens, next season's schedule
        self.save("19-training-camp", f"Training camp open, {lg.season} preseason")


def empty_folder(folder):
    """Delete what's in a folder but keep the folder (OneDrive can briefly lock a
    folder that was just emptied, so removing the folder itself fails now and then)."""
    import os, stat
    folder.mkdir(parents=True, exist_ok=True)

    def retry(fn, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        time.sleep(0.2)
        fn(path)
    for item in folder.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item, onexc=retry)
        else:
            item.unlink()


def main():
    ap = argparse.ArgumentParser(description="Rebuild the standard test saves.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--team", default=TEAM, help="your team's abbreviation (default PIT)")
    ap.add_argument("--games", choices=("real", "fast"), default="real",
                    help="real: the game sim (default); fast: made-up results, no game stats")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args()
    out = a.out.resolve()
    if out == saves.SAVES_DIR.resolve() or saves.SAVES_DIR.resolve() in out.parents:
        raise SystemExit("Refusing to write test saves into your saves folder.")
    empty_folder(out)
    print(f"Building test saves (seed {a.seed}, your team {a.team}, {a.games} games) in {out}")
    b = Builder(out, a.seed, a.team, a.games)
    b.run()
    (out / "index.json").write_text(json.dumps({
        "seed": a.seed, "team": a.team, "games": a.games, "saves": b.index}, indent=2), encoding="utf-8")
    print(f"{len(b.index)} saves in {time.time() - b.t0:.0f}s; list: {out / 'index.json'}")


if __name__ == "__main__":
    main()
