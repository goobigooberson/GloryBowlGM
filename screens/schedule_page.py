# schedule_page.py
# The Schedule tab. Two views:
#   League week: every game of one week (scores once played). The weeks run
#     from the Hall of Fame Game and the preseason weeks to the last
#     regular-season week.
#   Team season: one team's whole schedule, preseason first, with results
#     and its record (preseason games don't count in the record).
# Click a played game to see its box score in the panel on the right (the
# same layout as the Game tab's box score).
#
# Weeks are counted on one calendar here: 1-5 are the preseason (1 = Hall of
# Fame Game), then regular-season week 1 is calendar week 6.

from collections import defaultdict
from html import escape

from nicegui import ui

from engine import playoffs as po
from engine import season as S
from engine import schedule as sched
from .state import state, FREE_AGENTS
from . import game_page as G

P = S.PRESEASON_WEEKS


# ---------------------------------------------------------------------------
# A played game, rebuilt from its saved box score so the Game tab's box score
# pieces can draw it (they expect a live game).
# ---------------------------------------------------------------------------

class _TeamView:
    def __init__(self, team, players):
        self.id, self.name, self.abbrev = team.id, team.name, team.abbrev
        self.by_id = players


class _Box:
    pass


class _State:
    pass


class StoredGame:
    def __init__(self, league, g):
        box = league.boxes[g["id"]]
        by_id = {p.id: p for p in league.players}
        ids = (g["home"], g["away"])
        idx_of = {g["home"]: 0, g["away"]: 1}
        players = [{}, {}]
        self.box = _Box()
        self.box.players, self.box.owner = {}, {}
        for pid_s, line in box["players"].items():
            pid = int(pid_s)
            p = by_id.get(pid)
            if p is None:
                continue
            i = idx_of[line["team"]]
            players[i][pid] = p
            self.box.players[pid] = defaultdict(float, {k: v for k, v in line.items() if k != "team"})
            self.box.owner[pid] = i
        self.teams = [_TeamView(league.team(ids[i]), players[i]) for i in (0, 1)]
        self.box.team = [defaultdict(float, box["team"][0]), defaultdict(float, box["team"][1])]
        self.box.quarter_points = box["quarters"]
        self.box.scoring = [{**s, "team": idx_of[s["team"]], "score": tuple(s["score"])} for s in box["scoring"]]
        self.box.drives = [{**d, "team": idx_of[d["team"]]} for d in box["drives"]]
        self._drive = None
        self.state = _State()
        self.state.score = [g["home_score"], g["away_score"]]
        self.overtime = g["overtime"]
        self.finished = True
        self.weather_text = box.get("weather", "")


def result_text(g, team_id):
    """'W 27-20', 'L 17-24 (OT)', 'T 20-20' from this team's side."""
    mine = g["home_score"] if g["home"] == team_id else g["away_score"]
    theirs = g["away_score"] if g["home"] == team_id else g["home_score"]
    k = "W" if mine > theirs else ("L" if mine < theirs else "T")
    return k, f"{k} {mine}-{theirs}" + (" (OT)" if g["overtime"] else "")


def date_text(year, week):
    d = sched.week_sunday(year, week)
    return f"{d:%a}, {d:%b} {d.day}"


def pre_date_text(year, week):
    d = sched.preseason_date(year, week)
    return f"{d:%a}, {d:%b} {d.day}"


def cal_name(league, cal):
    """Name and date of a calendar week: 'Hall of Fame Game  (Thu, Aug 6)'."""
    n = S.n_weeks(league)
    if cal <= P:
        name = "Hall of Fame Game" if cal == 1 else f"Preseason week {cal - 1}"
        return name, pre_date_text(league.season, cal)
    if cal <= P + n:
        return f"Week {cal - P}", date_text(league.season, cal - P)
    rnd = cal - P - n
    name = po.championship_name(league) if rnd == 5 else po.ROUND_NAMES[rnd]
    return name, date_text(league.season, n + rnd)


def cal_games(league, cal):
    n = S.n_weeks(league)
    if cal <= P:
        return [g for g in league.preseason if g["week"] == cal]
    if cal <= P + n:
        return S.week_games(league, cal - P)
    return [g for g in league.playoffs if g["week"] == cal - P - n]


def game_box(league, g):
    """One played game's summary: line score, team stats, both box scores,
    scoring and drives. Drawn in the Schedule tab's right-hand panel and in
    the Game summary pop-up (popups.py)."""
    game = StoredGame(league, g)
    home, away = game.teams
    ui.label(f"{away.name} {g['away_score']}, {home.name} {g['home_score']}"
             + ("  (OT)" if g["overtime"] else "")).classes("condensed text-2xl")
    if S.is_preseason_game(g):
        name, when = cal_name(league, g["week"])
        where = sched.HOF_SITE if g.get("neutral") else f"at {home.name}"
        weather = game.weather_text.replace(sched.HOF_SITE + ". ", "")
        ui.label(f"{name} (preseason)  ·  {when}  ·  {where}  ·  {weather}").classes("legend")
    elif S.is_playoff_game(g):
        name, when = cal_name(league, S.game_calendar(league, g))
        site = S.site_text(league, g)
        where = site if g.get("neutral") else f"at {home.name}"
        weather = game.weather_text.replace(site + ". ", "") if site else game.weather_text
        ui.label(f"{name}  ·  {when}  ·  {where}  ·  {weather}").classes("legend")
    else:
        ui.label(f"Week {g['week']}  ·  {date_text(league.season, g['week'])}  ·  at {home.name}  ·  "
                 f"{game.weather_text}").classes("legend")
    with ui.tabs().props("no-caps dense align=left active-color=green-10 indicator-color=green-10") as tabs:
        t_team = ui.tab("Team stats")
        t_away = ui.tab(f"{away.abbrev} box")
        t_home = ui.tab(f"{home.abbrev} box")
        t_score = ui.tab("Scoring")
        t_drives = ui.tab("Drives")
    with ui.tab_panels(tabs, value=t_team).classes("w-full").style("background:transparent"):
        with ui.tab_panel(t_team).classes("p-0"):
            ui.html(G.line_score_html(game) + G.team_stats_html(game), sanitize=False)
        with ui.tab_panel(t_away).classes("p-0"):
            ui.html(G.box_score_html(game, 1), sanitize=False)
        with ui.tab_panel(t_home).classes("p-0"):
            ui.html(G.box_score_html(game, 0), sanitize=False)
        with ui.tab_panel(t_score).classes("p-0"):
            ui.html(G.scoring_html(game), sanitize=False)
        with ui.tab_panel(t_drives).classes("p-0"):
            ui.html(G.drives_html(game), sanitize=False)


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

def build_schedule_tab():
    """Builds the Schedule tab. Returns a function that refreshes it."""
    league = state.league
    has_pre = bool(league.preseason)
    first_cal = 1 if has_pre else P + 1

    def last_cal():
        # The playoff rounds appear once the playoffs have been seeded.
        return P + S.n_weeks(league) + (5 if league.playoffs else 0)

    def clamp(cal):
        return max(first_cal, min(last_cal(), int(cal)))

    view = {"mode": "League week", "week": clamp(S.calendar(league)), "game": None}

    with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
        mode_toggle = ui.toggle(["League week", "Team season"], value=view["mode"],
                                on_change=lambda e: set_mode(e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")

        @ui.refreshable
        def week_picker():
            if view["mode"] != "League week":
                ui.label("Showing the team picked in the Team list at the top. Click a played game "
                         "for its box score.").classes("legend")
                return
            weeks = {}
            for cal in range(first_cal, last_cal() + 1):
                name, when = cal_name(league, cal)
                weeks[cal] = f"{name}  ({when})"
            ui.button(icon="chevron_left", on_click=lambda: set_week(view["week"] - 1)) \
                .props("flat round dense" + (" disable" if view["week"] <= first_cal else "")).tooltip("Previous week")
            ui.select(weeks, value=view["week"], on_change=lambda e: set_week(e.value)) \
                .props("dense outlined options-dense").classes("w-72")
            ui.button(icon="chevron_right", on_click=lambda: set_week(view["week"] + 1)) \
                .props("flat round dense" + (" disable" if view["week"] >= last_cal() else "")) \
                .tooltip("Next week")
            ui.label("Click a played game for its box score.").classes("legend")
        week_picker()

    with ui.row().classes("w-full px-8 py-4 gap-5 no-wrap items-start"):
        list_column = ui.column().classes("gap-0").style(
            "flex: 1 1 0; min-width: 0; height: calc(100vh - 330px); overflow-y: auto")
        with list_column:
            @ui.refreshable
            def games_list():
                rec = S.records(league)
                if view["mode"] == "League week":
                    league_week(rec)
                else:
                    team_season(rec)

        box_column = ui.element("div").classes("report px-5 py-4") \
            .style("flex: 0 0 640px; height: calc(100vh - 330px); overflow-y: auto")
        with box_column:
            @ui.refreshable
            def box_panel():
                g = next((x for x in S.all_games(league) if x["id"] == view["game"]), None)
                if g is None or not g["played"]:
                    ui.label("No game selected").classes("condensed text-2xl")
                    ui.label("Click a game that's been played to see its box score: line score, "
                             "team stats, both teams' players, scoring and drives.").classes("legend")
                    return
                game_box(league, g)

    # ---- views ----------------------------------------------------------
    def league_week(rec):
        cal = view["week"]
        pre = cal <= P
        post = cal > P + S.n_weeks(league)
        rnd = cal - P - S.n_weeks(league)
        name, when = cal_name(league, cal)
        ui.label(f"{name}  ·  {when}" + ("  ·  preseason games don't count in the standings" if pre else "")) \
            .classes("panel-heading").style("margin-top:0")
        games = cal_games(league, cal)

        def rec_txt(tid):
            if pre:
                return ""
            if post:
                return f' <span class="legend">(#{po.seed_of(league, tid)} seed)</span>'
            return f' <span class="legend">({S.record_text(rec[tid])})</span>'

        if post and not games:
            ui.label("No games this week: the week off before the Glory Bowl." if rnd == 4 else
                     "Not set yet: these matchups come from the results of the round before.") \
                .classes("legend")
            return

        for g in games:
            h, a = league.team(g["home"]), league.team(g["away"])
            mine = league.user_team_id in (g["home"], g["away"])
            sel = " is-selected" if g["id"] == view["game"] else ""
            joiner = "vs" if g.get("neutral") else "at"
            if g["played"]:
                aw = "win" if g["away_score"] > g["home_score"] else ""
                hw = "win" if g["home_score"] > g["away_score"] else ""
                score = f'{g["away_score"]} - {g["home_score"]}'
                note = "Final" + (" (OT)" if g["overtime"] else "")
            else:
                aw = hw = ""
                score = joiner
                note = "Not played yet"
            if g.get("neutral"):
                note += f"  ·  {S.site_text(league, g)}"
            row = ui.html(
                f'<div class="sched-row{" mine" if mine else ""}{sel}">'
                f'<span class="{aw}">{escape(a.name)}{rec_txt(a.id)}</span>'
                f'<span class="score num">{score}</span>'
                f'<span class="{hw}">{escape(h.name)}{rec_txt(h.id)}</span>'
                f'<span class="legend">{note}</span></div>', sanitize=False).classes("w-full")
            row.on("click", lambda _e, gid=g["id"]: pick_game(gid))
        playing = {t for g in games for t in (g["home"], g["away"])}
        off = sorted(t.abbrev for t in league.teams if t.id not in playing)
        if post:
            if rnd == 1 and league.playoff_seeds:
                byes = [league.team(ids[0]).name for ids in league.playoff_seeds.values()]
                ui.label("First-round bye (#1 seeds): " + ", ".join(byes)).classes("legend mt-2")
        elif off and not (pre and cal == 1):
            ui.label(("Preseason bye: " if pre else "Bye: ") + ", ".join(off)).classes("legend mt-2")
        elif pre and cal == 1:
            ui.label("Only the Hall of Fame Game is played this week. Its two teams get a bye in "
                     "one of the other preseason weeks, so everyone plays 4 preseason games.") \
                .classes("legend mt-2")

    def team_season(rec):
        tid = state.team_id
        if tid == FREE_AGENTS:
            ui.label("Free agents don't have a schedule").classes("condensed text-2xl")
            ui.label("Pick a team from the Team list at the top.").classes("legend")
            return
        team = league.team(tid)
        r = rec[tid]
        now = S.calendar(league)
        over = S.season_over(league)
        head = ('<div class="team-sched depth-head"><span>Week</span><span>Date</span><span>Opponent</span>'
                '<span>Result</span><span>Record</span></div>')
        if has_pre:
            ui.label(f"{team.name}  ·  Preseason").classes("panel-heading").style("margin-top:0")
            ui.html(head, sanitize=False).classes("w-full")
            by_week = {g["week"]: g for g in S.team_preseason(league, tid)}
            for cal in range(1, P + 1):
                name, when = cal_name(league, cal)
                short = "HOF" if cal == 1 else f"P{cal - 1}"
                current = " current" if cal == now and not over else ""
                g = by_week.get(cal)
                if g is None:
                    txt = "No game (Hall of Fame Game week)" if cal == 1 else "Preseason bye"
                    ui.html(f'<div class="team-sched bye{current}"><span>{short}</span><span>{when}</span>'
                            f'<span>{txt}</span><span></span><span></span></div>',
                            sanitize=False).classes("w-full")
                    continue
                game_row(g, tid, short, when, current, None)
        ui.label(f"{team.name}  ·  Regular season  ·  {S.record_text(r)}").classes("panel-heading") \
            .style("margin-top:0" if not has_pre else "")
        ui.html(head, sanitize=False).classes("w-full")
        w_l = [0, 0, 0]
        by_week = {g["week"]: g for g in S.team_schedule(league, tid)}
        for week in range(1, S.n_weeks(league) + 1):
            current = " current" if P + week == now and not over else ""
            g = by_week.get(week)
            if g is None:
                ui.html(f'<div class="team-sched bye{current}"><span>{week}</span>'
                        f'<span>{date_text(league.season, week)}</span><span>Bye week</span><span></span>'
                        f'<span></span></div>', sanitize=False).classes("w-full")
                continue
            game_row(g, tid, str(week), date_text(league.season, week), current, (w_l, rec))
        mine = [g for g in league.playoffs if tid in (g["home"], g["away"])]
        if mine:
            seed = po.seed_of(league, tid)
            ui.label(f"{team.name}  ·  Playoffs  ·  #{seed} seed").classes("panel-heading")
            ui.html(head.replace("Record", ""), sanitize=False).classes("w-full")
            for g in sorted(mine, key=lambda g: g["week"]):
                rname, when = cal_name(league, P + S.n_weeks(league) + g["week"])
                current = " current" if S.game_calendar(league, g) == now and not over else ""
                game_row(g, tid, {1: "WC", 2: "DIV", 3: "CONF", 5: "GB"}[g["week"]], when, current, None)
        elif league.playoff_seeds:
            ui.label(f"{team.name}  ·  Playoffs").classes("panel-heading")
            ui.label("Didn't make the playoffs.").classes("legend")

    def game_row(g, tid, week_txt, when, current, running):
        home = g["home"] == tid
        opp = league.team(g["away"] if home else g["home"])
        where = "vs" if (home or g.get("neutral")) else "at"
        extra = ""
        if running is not None:
            extra = f' <span class="legend">({S.record_text(running[1][opp.id])})</span>'
        if g.get("kind") == "hof":
            extra += f' <span class="legend">· Hall of Fame Game, {sched.HOF_SITE}</span>'
        elif S.is_playoff_game(g):
            extra += f' <span class="legend">(#{po.seed_of(league, opp.id)} seed)</span>'
            if g.get("neutral"):
                extra += f' <span class="legend">· {po.championship_name(league)}, {S.site_text(league, g)}</span>'
        opp_txt = f'{where} {escape(opp.name)}{extra}'
        sel = " is-selected" if g["id"] == view["game"] else ""
        record = ""
        if g["played"]:
            k, txt = result_text(g, tid)
            if running is not None:
                w_l = running[0]
                w_l["WLT".index(k)] += 1
                record = f"{w_l[0]}-{w_l[1]}" + (f"-{w_l[2]}" if w_l[2] else "")
            res = f'<span class="res-{k.lower()}">{txt}</span>'
            cls = " played"
        else:
            res, cls = '<span class="legend">-</span>', ""
        row = ui.html(f'<div class="team-sched{cls}{current}{sel}"><span>{week_txt}</span>'
                      f'<span>{when}</span><span>{opp_txt}</span>'
                      f'<span>{res}</span><span class="num">{record}</span></div>',
                      sanitize=False).classes("w-full")
        if g["played"]:
            row.on("click", lambda _e, gid=g["id"]: pick_game(gid))

    # ---- actions ----------------------------------------------------------
    def set_mode(mode):
        view["mode"] = mode
        week_picker.refresh()
        games_list.refresh()

    def set_week(cal):
        view["week"] = clamp(cal)
        week_picker.refresh()
        games_list.refresh()

    def pick_game(gid):
        view["game"] = gid
        games_list.refresh()
        box_panel.refresh()

    def refresh(follow_week=False):
        if follow_week:
            # After simming, show the week just played.
            view["week"] = clamp(S.calendar(league) - 1 if not S.season_over(league) else last_cal())
        week_picker.refresh()
        games_list.refresh()
        box_panel.refresh()

    def show_game(gid):
        """Open one game's summary: its week in the list, its box score on the right."""
        g = next((x for x in S.all_games(league) if x["id"] == gid), None)
        if g is None:
            return
        view["mode"] = "League week"
        view["week"] = clamp(S.game_calendar(league, g))
        view["game"] = gid
        mode_toggle.value = "League week"
        refresh()

    refresh.show_game = show_game

    # Draw the list and the box panel now that everything they use exists.
    with list_column:
        games_list()
    with box_column:
        box_panel()
    return refresh
