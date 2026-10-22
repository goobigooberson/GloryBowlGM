# new_game_page.py
# New game, in two steps on one screen:
#   1. League settings: first season, regular season games, how teams are
#      built (a startup draft, or random generated rosters).
#   2. Choose your team: the league is built, and a table shows every team's
#      strength (or, for a startup draft, where it picks) so you can choose
#      with your eyes open (or let the game pick). Name the save, then Start
#      game. Nothing is saved until then; a startup draft starts right away.

import random

from nicegui import run, ui

from engine import depth
from engine import draft_day
from engine import formatting as fmt
from engine import saves
from engine.league import ROSTER_METHODS
from engine.scale import shown, seen
from . import theme
from .state import state, generate_league, start_new_game

COLUMNS = [
    {"name": "team", "label": "Team", "field": "team", "sortable": True, "align": "left"},
    {"name": "div", "label": "Division", "field": "div_sort", "sortable": True, "align": "left"},
    {"name": "all", "label": "Starters", "field": "all", "sortable": True, "align": "left"},
    {"name": "off", "label": "Offense", "field": "off", "sortable": True, "align": "left"},
    {"name": "def", "label": "Defense", "field": "def", "sortable": True, "align": "left"},
    {"name": "qb", "label": "Starting QB", "field": "qb_ovr", "sortable": True, "align": "left"},
    {"name": "best", "label": "Best player", "field": "best_ovr", "sortable": True, "align": "left"},
]


def team_rows(league):
    rows = []
    for t in league.teams:
        roster = league.team_players(t.id)
        ids = depth.starter_ids(league.depth_charts.get(t.id, {}))
        starters = [p for p in roster if p.id in ids]

        def avg(group):
            return round(sum(seen(league, p, viewer=None) for p in group) / len(group)) if group else 0
        off = [p for p in starters if theme.unit_of(p.position) == "Offense"]
        dfn = [p for p in starters if theme.unit_of(p.position) == "Defense"]
        qb_ids = league.depth_charts.get(t.id, {}).get("QB", [])
        qb = next((p for p in roster if qb_ids and p.id == qb_ids[0]), None)
        best = max(roster, key=lambda p: seen(league, p, viewer=None))   # what the league believes (no team of yours yet)
        row = {"id": t.id, "team": t.name, "div": f"{t.conference} {t.division}",
               "div_sort": f"{t.conference} {t.division} {t.name}",
               "qb_name": qb.name if qb else "-", "qb_ovr": seen(league, qb, viewer=None) if qb else 0,
               "best_name": f"{best.position} {best.name}", "best_ovr": seen(league, best, viewer=None)}
        for key, value in (("all", avg(starters)), ("off", avg(off)), ("def", avg(dfn)),
                           ("qb", row["qb_ovr"]), ("best", row["best_ovr"])):
            word = fmt.skill_word(value)
            row[key + "_txt"] = f"{word} ({value})"
            row[key + "_color"] = theme.RATING_COLORS[word]
            if key in ("all", "off", "def"):
                row[key] = value
        rows.append(row)
    return rows


STARTUP_COLUMNS = [
    {"name": "first", "label": "Round 1 pick", "field": "first", "sortable": True, "align": "right"},
    {"name": "second", "label": "Round 2 pick", "field": "second", "sortable": True, "align": "right"},
    {"name": "team", "label": "Team", "field": "team", "sortable": True, "align": "left"},
    {"name": "div", "label": "Division", "field": "div_sort", "sortable": True, "align": "left"},
]


def startup_rows(league):
    """New game with a startup draft: each team and where it picks."""
    n = len(league.teams)
    rows = []
    for t in league.teams:
        first = draft_day.startup_slot(league, t.id)
        rows.append({"id": t.id, "team": t.name, "div": f"{t.conference} {t.division}",
                     "div_sort": f"{t.conference} {t.division} {t.name}", "first": first,
                     "second": 2 * n + 1 - first})
    return rows


def build_new_game_page():
    ui.add_head_html(theme.HEAD_HTML)
    ui.query("body").style(f"background:{theme.CHALK}")
    # Startup draft first: Blake's main way to start a league (CLAUDE.md).
    form = {"season": 2026, "season_games": 17, "roster_method": "startup_draft",
            "team_id": None, "name": "", "name_edited": False}
    state.pending_league = None
    step = {"n": 1}

    with ui.element("div").classes("field-band w-full px-10 pt-8 pb-6"):
        with ui.row().classes("w-full items-end justify-between"):
            with ui.column().classes("gap-2"):
                ui.label("New game").classes("menu-title")

                @ui.refreshable
                def steps():
                    with ui.row().classes("gap-2"):
                        ui.label("1  League settings").classes("step-chip" + (" on" if step["n"] == 1 else ""))
                        ui.label("2  Choose your team").classes("step-chip" + (" on" if step["n"] == 2 else ""))
                steps()
            ui.button("Main menu", on_click=lambda: back_to_menu()).props("outline color=white no-caps")

    @ui.refreshable
    def body():
        if step["n"] == 1:
            settings_step()
        else:
            team_step()

    # ---- Step 1: league settings ----------------------------------------
    def settings_step():
        with ui.column().classes("px-10 py-8 gap-0").style("width: 760px; max-width: 100%"):
            with ui.column().classes("menu-panel p-6 gap-0 w-full"):
                ui.label("League settings").classes("menu-heading")

                ui.label("First season").classes("field-label")
                ui.number(value=form["season"], min=2000, max=2099, precision=0, format="%d",
                          on_change=lambda e: form.update(season=int(e.value) if e.value else 2026)) \
                    .props("outlined dense").classes("w-40")
                ui.label("The year your first season is played. Player ages and draft years are "
                         "built around it.").classes("legend")

                ui.label("Regular season games").classes("field-label")
                ui.toggle({17: "17 games", 16: "16 games"}, value=form["season_games"],
                          on_change=lambda e: form.update(season_games=e.value)) \
                    .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")
                ui.label("The NFL has played 17 since 2021 (16 before that). Each team gets "
                         "one bye week either way.").classes("legend")

                ui.label("How teams are built").classes("field-label")
                ui.radio({"startup_draft": ROSTER_METHODS["startup_draft"], "random": ROSTER_METHODS["random"]},
                         value=form["roster_method"], on_change=lambda e: form.update(roster_method=e.value)) \
                    .props("color=green-10")
                ui.html('<div class="legend" style="padding-left:34px"><b>Startup draft:</b> every player in the '
                        'league goes into one pool and the 32 teams draft full 53-man rosters, 53 rounds, the order '
                        'reversing each round (snake). You make your own picks (or let your staff). Teams that draft '
                        'well start strong, teams that draft badly start weak. Then training camp opens.</div>'
                        '<div class="legend" style="padding-left:34px;margin-top:4px"><b>Random generated rosters:</b> '
                        'every team gets a 90-man training camp roster of new players and cuts to 53 after the '
                        'preseason. Teams start fairly even; the gaps grow over the seasons.</div>', sanitize=False)
                ui.html(f'<div class="coming-later"><b>{ROSTER_METHODS["legacy"]}</b>: real rosters '
                        'from a chosen season. Coming in a later step.</div>', sanitize=False)

            with ui.row().classes("w-full justify-end mt-4"):
                create_btn = ui.button("Build the league", on_click=lambda: build_league(create_btn)) \
                    .props("no-caps unelevated color=green-10 size=lg")

    async def build_league(button):
        button.props("loading")
        state.pending_league = await run.io_bound(generate_league, form["season"], settings_now())
        form["team_id"] = None
        step["n"] = 2
        steps.refresh()
        body.refresh()

    # ---- Step 2: choose your team ---------------------------------------
    def team_step():
        league = state.pending_league
        startup = draft_day.in_startup(league)
        rows = startup_rows(league) if startup else team_rows(league)
        with ui.row().classes("w-full px-10 py-6 gap-5 no-wrap items-start"):
            with ui.column().classes("gap-2").style("flex: 1 1 0; min-width: 0"):
                ui.label("Click a team to choose it. Click a column heading to sort."
                         + (" Rosters don't exist yet: the startup draft builds them. The order was drawn by lot "
                            "and reverses every round." if startup else "")).classes("legend")
                table = ui.table(rows=rows, columns=STARTUP_COLUMNS if startup else COLUMNS, row_key="id",
                                 pagination={"rowsPerPage": 0, "sortBy": "first" if startup else "div"}) \
                    .props("flat dense virtual-scroll hide-bottom") \
                    .classes("roster-table w-full").style("height: calc(100vh - 290px)")
                table.add_slot("body-cell-div", r"""
                    <q-td :props="props">{{ props.row.div }}</q-td>""")
                for key in ("all", "off", "def"):
                    table.add_slot(f"body-cell-{key}", f"""
                        <q-td :props="props"><span class="rating num">
                          <span class="swatch" :style="{{background: props.row.{key}_color}}"></span>
                          {{{{ props.row.{key}_txt }}}}</span></q-td>""")
                for key in ("qb", "best"):
                    table.add_slot(f"body-cell-{key}", f"""
                        <q-td :props="props"><span class="rating num">
                          <span class="swatch" :style="{{background: props.row.{key}_color}}"></span>
                          {{{{ props.row.{key}_name }}}}, {{{{ props.row.{key}_ovr }}}}</span></q-td>""")
                table.on("rowClick", lambda e: pick(e.args[1]["id"]))

            with ui.column().classes("menu-panel p-6 gap-1").style("flex: 0 0 400px"):
                @ui.refreshable
                def choice():
                    tid = form["team_id"]
                    ui.label("Your team").classes("menu-heading")
                    if tid is None:
                        ui.label("None chosen yet").classes("condensed text-2xl")
                        ui.label("You're the GM of one team; the other 31 are run by the AI.") \
                            .classes("legend")
                    elif startup:
                        team = league.team(tid)
                        r = next(x for x in rows if x["id"] == tid)
                        ui.label(team.name).classes("condensed text-3xl")
                        ui.label(f"{team.conference} Conference, {team.division} Division").classes("legend")
                        ui.html(f'<div class="facts" style="margin-top:8px">'
                                f'<span class="k">Startup draft</span><span>pick {r["first"]} in round 1, '
                                f'{r["second"]} in round 2 (snake)</span></div>', sanitize=False)
                    else:
                        team = league.team(tid)
                        r = next(x for x in rows if x["id"] == tid)
                        ui.label(team.name).classes("condensed text-3xl")
                        ui.label(f"{team.conference} Conference, {team.division} Division").classes("legend")
                        ui.html(f'<div class="facts" style="margin-top:8px">'
                                f'<span class="k">Starters</span><span>{r["all_txt"]}</span>'
                                f'<span class="k">Offense</span><span>{r["off_txt"]}</span>'
                                f'<span class="k">Defense</span><span>{r["def_txt"]}</span>'
                                f'<span class="k">Starting QB</span><span>{r["qb_name"]}, {r["qb_ovr"]}</span>'
                                f'<span class="k">Best player</span><span>{r["best_name"]}, {r["best_ovr"]}</span>'
                                f'</div>', sanitize=False)
                choice()
                ui.button("Pick a team for me", on_click=lambda: pick(random.choice(league.teams).id)) \
                    .props("no-caps flat color=green-10 dense").classes("self-start mt-1")

                ui.label("Save name").classes("field-label")
                name_input = ui.input(value=form["name"], placeholder="Choose a team first",
                                      on_change=lambda e: name_typed(e.value)) \
                    .props("outlined dense").classes("w-full")
                ui.label("You'll find it under this name in Load game.").classes("legend")

                ui.label("Settings").classes("field-label")
                ui.label(f"First season {league.season}   ·   {form['season_games']} games   ·   "
                         f"{ROSTER_METHODS[form['roster_method']]}").classes("legend")

                ui.button("Start game", on_click=lambda: start()) \
                    .props("no-caps unelevated color=green-10 size=lg").classes("w-full mt-4")
                with ui.row().classes("w-full justify-between mt-1"):
                    ui.button("Back to settings", on_click=lambda: go_back()).props("no-caps flat color=grey-9 dense")
                    ui.button("Build a different league", on_click=lambda: rebuild()) \
                        .props("no-caps flat color=grey-9 dense") \
                        .tooltip("Throw this league away and generate new rosters")

        def pick(team_id):
            form["team_id"] = team_id
            table.props(f':table-row-class-fn="row => row.id === {team_id} ? \'is-selected\' : \'\'"')
            if not form["name_edited"]:
                form["name"] = f"{league.team(team_id).name} {league.season}"
                name_input.set_value(form["name"])
                form["name_edited"] = False
            choice.refresh()

        def name_typed(value):
            form["name"] = value or ""
            team = league.team(form["team_id"]) if form["team_id"] else None
            auto = f"{team.name} {league.season}" if team else ""
            form["name_edited"] = bool(value) and value != auto

        def start():
            if form["team_id"] is None:
                ui.notify("Choose your team first (or use Pick a team for me).")
                return
            name = form["name"].strip() or f"{league.team(form['team_id']).name} {league.season}"
            base, n = name, 2
            while saves.name_taken(name):
                name = f"{base} ({n})"
                n += 1
            start_new_game(league, name, form["team_id"])
            ui.navigate.to("/game")

        def go_back():
            state.pending_league = None
            step["n"] = 1
            steps.refresh()
            body.refresh()

        async def rebuild():
            ui.notify("Building a new league...")
            state.pending_league = await run.io_bound(generate_league, league.season, settings_now())
            form["team_id"] = None
            if not form["name_edited"]:
                form["name"] = ""
            body.refresh()

    def settings_now():
        return {"season_games": form["season_games"], "roster_method": form["roster_method"]}

    def back_to_menu():
        state.pending_league = None
        ui.navigate.to("/")

    body()
