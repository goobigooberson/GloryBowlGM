# main_page.py
# The game screen: one slim green bar (your team, the six sections, the week,
# Sim, save status, Menu), a row of page buttons for the section you're in,
# and the pages underneath. Each page lives in its own file; nav.py sorts the
# pages into sections (layout research and mockup, Oct 21).

from datetime import datetime
from html import escape

from nicegui import run, ui

from engine import draft_day
from engine import formatting as fmt
from engine import saves
from engine import playoffs as po
from engine import season
from engine.scale import shown
from . import nav, popups, theme
from .home_page import build_home_tab, CSS as HOME_CSS
from .state import (state, FREE_AGENTS, team_starter_ids, mark_changed, save_now, save_copy,
                    close_game, start_next_season, advance_offseason, finish_startup)
from .contracts_page import build_contracts_tab
from .draft_page import build_draft_tab
from .roster_page import build_roster_tab
from .depth_page import build_depth_tab
from .counts_page import build_counts_tab
from .schedule_page import build_schedule_tab, date_text, pre_date_text, result_text
from .standings_page import build_standings_tab
from .stats_page import build_stats_tab
from .playoffs_page import build_playoffs_tab
from .game_page import build_game_tab
from .news_page import build_news_tab
from .awards_page import build_awards_tab


class _NoGame:
    """Stands in for the Game tab while it doesn't exist (a startup draft)."""

    def busy(self):
        return False

    def refresh(self):
        return None

    def watch(self):
        return None


def build_page():
    ui.add_head_html(theme.HEAD_HTML)
    ui.add_head_html(nav.CSS)
    ui.add_head_html(HOME_CSS)
    popups.install()            # player cards, game summaries, the offseason report open as pop-ups
    ui.query("body").style(f"background:{theme.CHALK}")

    league = state.league
    team_options = {FREE_AGENTS: "Free agents"}          # listed first
    for t in sorted(league.teams, key=lambda t: t.name):
        team_options[t.id] = t.name + ("  (your team)" if t.id == league.user_team_id else "")
    team_names = {t.id: t.name for t in sorted(league.teams, key=lambda t: t.name)}

    # The pages that exist right now (during a new league's startup draft only the
    # Draft page: no rosters, games or contracts yet), and the one to open on.
    startup = draft_day.in_startup(league)
    pages = ["Draft"] if startup else ["Home", "Roster", "Contracts", "Draft", "Depth chart", "Position counts",
                                        "Schedule", "Standings", "Stats", "Playoffs", "Bitter", "Awards", "Game"]
    phase = season.offseason_phase(league)
    if startup:
        first_page = "Draft"
    elif phase and phase[0] in ("draft", "drafting"):
        first_page = nav.tab_name(getattr(state, "main_tab", None)) or "Draft"
    else:
        first_page = nav.tab_name(getattr(state, "main_tab", None)) or "Home"
    if first_page not in pages:
        first_page = pages[0]
    showing = {"page": first_page}

    def go(page):
        tabs.set_value(page)

    # ---- The slim green bar ------------------------------------------------
    # Your team (click to look at another team), the sections, the week and
    # Sim, save status, Menu. Turns slate gray while you look at a team that
    # isn't yours. (Layout research, Oct 21: one bar instead of three.)
    band = ui.element("div").classes("top-band w-full px-4 py-2")
    with band:
        band_row = ui.row().classes("w-full items-center no-wrap").style("gap:8px 14px; flex-wrap:wrap")
    with band_row:
        @ui.refreshable
        def team_banner():
            mine = state.team_id == league.user_team_id
            if mine:
                band.classes(remove="other")
            else:
                band.classes(add="other")
            if state.team_id == FREE_AGENTS:
                abbrev, name = "FA", "Free agent pool"
                sub = f"{len(league.free_agents())} unsigned players"
            else:
                team = league.team(state.team_id)
                abbrev, name = team.abbrev, team.name
                parts = []
                rec = season.records(league)[team.id]
                if rec["w"] + rec["l"] + rec["t"] and not season.in_offseason(league):
                    order = season.division_standings(league)[team.conference][team.division]
                    place = ("1st", "2nd", "3rd", "4th")[order.index(team.id)] if team.id in order else ""
                    parts.append(f"{season.record_text(rec)} · {place} in the {team.division}")
                else:
                    parts.append(f"{team.division} Division")
                if not startup:
                    ids = team_starter_ids(team.id)
                    starters = [p for p in league.team_players(team.id) if p.id in ids]
                    if starters:
                        avg = round(sum(shown(p.overall(), p.position) for p in starters) / len(starters))
                        parts.append(f"Starters: {fmt.skill(avg)}")
                sub = " · ".join(parts)
            with ui.element("button").classes("team-btn") \
                    .props('type="button" aria-label="Your team. Click to look at another team"'):
                ui.html(f'<span style="display:flex;align-items:center;gap:10px"><span class="abbr">{escape(abbrev)}'
                        f'</span><span style="display:flex;flex-direction:column"><span class="tname">{escape(name)}'
                        f'</span><span class="tsub">{escape(sub)}</span></span><svg width="12" height="12" '
                        f'viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" '
                        f'aria-hidden="true"><path d="M2 4l4 4 4-4"/></svg></span>', sanitize=False)
                with ui.menu().props('max-height="70vh"'):
                    for tid, label in team_options.items():
                        ui.menu_item(label, on_click=lambda tid=tid: change_team(tid))
            if not mine and league.user_team_id is not None:
                if state.team_id != FREE_AGENTS:
                    ui.label("View only").classes("view-only") \
                        .tooltip("Only your own team's depth chart and roster can be changed.")
                ui.button("My team", on_click=lambda: change_team(league.user_team_id)) \
                    .props("no-caps outline color=white").tooltip("Back to your own team")
        team_banner()

        @ui.refreshable
        def section_nav():
            nav.section_buttons(pages, showing["page"], go)
        section_nav()
        ui.element("div").style("flex:1")
        season_row = ui.row().classes("items-center no-wrap").style("gap:10px")

        @ui.refreshable
        def save_bar():
            if state.dirty:
                ui.button("Unsaved changes: Save", on_click=lambda: do_save()) \
                    .props("no-caps unelevated").style(f"background:{theme.FLAG};color:{theme.INK}") \
                    .tooltip("Save your game (Ctrl+S)")
            else:
                ui.label("Saved").classes("save-chip") \
                    .tooltip("All changes are saved.")
        save_bar()
        state.on_save_status = save_bar.refresh

        with ui.button("Menu").props("no-caps outline color=white") \
                .tooltip(f"{league.name} · {league.season} season: save, save a copy, main menu"):
            with ui.menu():
                ui.menu_item(f"{league.name}  ·  {league.season} season").props("disable")
                ui.menu_item("Save  (Ctrl+S)", on_click=lambda: do_save())
                ui.menu_item("Save a copy...", on_click=lambda: open_copy_dialog()) \
                    .tooltip("Write your game as it is now to a new save, e.g. a backup before a big decision. "
                             "You keep playing this one.")
                ui.menu_item("Main menu", on_click=lambda: leave())

    # ---- No team chosen yet (saves from before New game existed): ask once
    if league.user_team_id is None:
        with ui.row().classes("w-full px-8 py-3 items-center gap-3 choose-team"):
            ui.label("Which team will you run? You're the GM of one team; "
                     "the other 31 are run by the AI.").classes("condensed text-lg")
            pick = ui.select(team_names, label="Your team").props("dense outlined options-dense").classes("w-64")
            ui.button("Take over this team", on_click=lambda: choose_team(pick.value)) \
                .props("no-caps unelevated color=green-10")

    # ---- Season bar: the week, your game, Watch / Sim -------------------
    # (These two are defined before the bar is first drawn: opening the page
    # after the season ended, or during the playoffs, draws it right away.)
    def user_playoff_status():
        """Your team during the playoffs, when it has no game this week."""
        tid = league.user_team_id
        seed = po.seed_of(league, tid)
        if seed is None:
            return "Missed the playoffs"
        lost = next((g for g in league.playoffs if g["played"] and po.loser(g) == tid), None)
        if lost:
            return f"Season over: lost in the {po.ROUND_NAMES[lost['week']].replace(' round', '').lower()} round" \
                if lost["week"] < 3 else "Season over: lost in the conference championship"
        if league.playoff_round == 1 and seed == 1:
            return "First-round bye (#1 seed)"
        if league.playoff_round == 4:
            return "Pro Bowl week (no game), then the Glory Bowl"
        return f"#{seed} seed"

    def user_season_text(rec):
        tid = league.user_team_id
        team = league.team(tid)
        text = f"{team.name} finished {season.record_text(rec[tid])}"
        if po.champion(league) == tid:
            return text + " and won the " + po.championship_name(league) + "!"
        seed = po.seed_of(league, tid)
        if seed is None:
            return text + " and missed the playoffs."
        lost = next((g for g in league.playoffs if g["played"] and po.loser(g) == tid), None)
        if lost and lost["week"] == 5:
            return text + f" and lost the {po.championship_name(league)}."
        if lost:
            where = {1: "Wild Card round", 2: "Divisional round", 3: "conference championship"}[lost["week"]]
            return text + f" (#{seed} seed) and lost in the {where}."
        return text + "."

    with season_row:
        # The week and the buttons that move the season along, in the green bar
        # (the longer text, your last game and Watch my game are on the Home page).
        def two_lines(top, bottom="", tip=None):
            with ui.column().classes("gap-0 items-end"):
                ui.label(top).classes("band-week")
                if bottom:
                    b = ui.label(bottom).classes("band-sub")
                    if tip or len(bottom) > 60:
                        b.tooltip(tip or bottom)

        BTN = "no-caps unelevated color=white text-color=green-10"
        BTN_OUT = "no-caps outline color=white"

        @ui.refreshable
        def season_bar():
            if draft_day.in_startup(league):
                # A new league's startup draft (draft_day.py): only the Draft tab until it's over.
                slot = draft_day.startup_on_clock(league)
                line = ""
                if slot:
                    yours = slot["team"] == league.user_team_id
                    line = (f"Round {slot['round']} of 53, pick {slot['pick']:,}: "
                            + ("you're on the clock" if yours else f"{league.team(slot['team']).name} on the clock"))
                two_lines(f"{league.season} startup draft", line,
                          "Every team drafts its 53-man roster. Training camp opens when it's over.")
                ui.button("Go to the draft room", on_click=lambda: tabs.set_value(draft_tab)).props(BTN)
                return
            rec = season.records(league)
            total = season.n_weeks(league)
            if season.season_over(league):
                champ = po.champion(league)
                two_lines(f"{league.season} season complete",
                          f"{po.championship_name(league)} champion: {league.team(champ).name}" if champ else "",
                          user_season_text(rec) if league.user_team_id else None)
                ui.button(f"Start the {league.season + 1} offseason", on_click=lambda: next_season()) \
                    .props(BTN) \
                    .tooltip("Keeps this season's stats and results for good, then starts the new league year: "
                             "players a year older, retirements, and your expiring contracts. The offseason "
                             "then goes step by step: re-signings, free agency waves, the draft, more free "
                             "agency, then training camp.")
                return
            if season.in_offseason(league):
                key, title, text = season.offseason_phase(league)
                two_lines(f"{league.season} offseason", title, text)     # the full text is on Home
                if league.offseason_report and league.offseason_report.get("season") == league.season:
                    ui.button("Offseason report", on_click=lambda: popups.open_offseason()) \
                        .props("no-caps flat color=white") \
                        .tooltip("Retirements, free agency, the draft and undrafted signings so far")
                if key in ("draft", "drafting") or draft_day.scouting_open(league):
                    ui.button("Go to the draft room" if key == "drafting" else "Scout the draft class",
                              on_click=lambda: tabs.set_value(draft_tab)) \
                        .props(BTN_OUT) \
                        .tooltip("The Draft page" + (": make your picks" if key == "drafting" else
                                                     ": scout this year's class before the draft"))
                nxt = {"resign": "Next: open free agency", "draft": "Next: start the draft",
                       "drafting": "Next: staff finishes the draft",
                       "camp": "Next: open training camp"}.get(key, "Next: play out this wave")
                nxt_btn = ui.button(nxt, on_click=lambda: next_phase()).props(BTN)
                tip = {"draft": "Scouting ends and the draft starts. It stops when you're on the clock.",
                       "drafting": "Your staff makes the rest of your picks (no trades) and the draft finishes; "
                                   "then free agency goes on (waves 5-7)."}.get(key)
                if tip:
                    nxt_btn.tooltip(tip)
                return
            pre = season.in_preseason(league)
            post = season.in_playoffs(league)
            if pre:
                top = (f"{league.season} preseason  ·  {season.week_label(league)}  ·  "
                       f"{pre_date_text(league.season, league.pre_week)}")
            elif post:
                d = po.round_date(league, league.playoff_round)
                top = f"{league.season} playoffs  ·  {season.week_label(league)}  ·  {d:%a}, {d:%b} {d.day}"
            else:
                top = f"Week {league.week} of {total}  ·  {date_text(league.season, league.week)}"
            g = None
            line = ""
            if league.user_team_id:
                team = league.team(league.user_team_id)
                g = season.team_current_game(league, team.id)
                if g is None:
                    if pre and league.pre_week == 1:
                        line = "Only the Hall of Fame Game is played this week"
                    elif post:
                        line = user_playoff_status()
                    else:
                        line = "Preseason bye" if pre else "Bye week"
                else:
                    home = g["home"] == team.id
                    opp = league.team(g["away"] if home else g["home"])
                    where = "vs" if home or g.get("neutral") else "at"
                    tag = "Hall of Fame Game: " if g.get("kind") == "hof" else ""
                    if g["played"]:
                        _k, txt = result_text(g, team.id)
                        line = f"{tag}{where} {opp.name}: {txt}"
                    else:
                        if pre:
                            opp_rec = ""
                        elif post:
                            opp_rec = f" (#{po.seed_of(league, opp.id)} seed)"
                        else:
                            opp_rec = f" ({season.record_text(rec[opp.id])})"
                        line = f"This week: {tag}{where} {opp.name}{opp_rec}"
            two_lines(top, line)
            rep = league.offseason_report
            if pre and rep and rep.get("season") == league.season:
                ui.button("Offseason report", on_click=lambda: popups.open_offseason()) \
                    .props("no-caps flat color=white") \
                    .tooltip("Retirements, the draft, undrafted signings and cuts this offseason")
            here = season.calendar(league)
            ui.button("Sim week", on_click=lambda: sim_through(here)) \
                .props(BTN) \
                .tooltip("Play every game this week" + (" (yours too)" if g is not None and not g["played"] else "")
                         + ". To watch yours snap by snap, use Watch my game on the Home page.")
            P = season.PRESEASON_WEEKS
            later = {}
            if pre:
                for w in range(league.pre_week + 1, P):
                    later[w] = f"Through preseason week {w - 1}"
                later[P] = "To the end of the preseason"
                later[P + 1] = "Through regular-season week 1"
            elif not post:
                for w in range(league.week + 1, total):
                    later[P + w] = f"Through week {w}"
            if not post:
                later[P + total] = "To the end of the regular season"
            else:
                for r in range(league.playoff_round + 1, 4):
                    later[P + total + r] = f"Through the {po.ROUND_NAMES[r].lower()}"
            later[P + total + 5] = f"Through the {po.championship_name(league)}"
            with ui.dropdown_button("Sim ahead", auto_close=True).props(BTN_OUT):
                for cal, label in later.items():
                    ui.item(label, on_click=lambda _e, cal=cal: sim_through(cal))
        season_bar()

    # ---- Page buttons for the section you're in (Team: Roster, Depth chart...) --
    @ui.refreshable
    def page_row():
        nav.page_buttons(pages, showing["page"], go)
    page_row()

    # ---- Tabs -----------------------------------------------------------
    # The pages. Their tab row is hidden: the section and page buttons above
    # (nav.py) switch between them. During a new league's startup draft only the
    # Draft tab exists (no rosters, games or contracts yet); the other tabs'
    # refreshes do nothing then.
    with ui.tabs().props("no-caps align=left active-color=green-10 indicator-color=green-10 dense") \
            .classes("w-full px-6 main-tabs").style("display:none") as tabs:
        if not startup:
            home_tab = ui.tab("Home")        # the overview (home_page.py)
            roster_tab = ui.tab("Roster")
            contracts_tab = ui.tab("Contracts")
        draft_tab = ui.tab("Draft")          # scouting, the draft room, results (draft_page.py)
        if not startup:
            depth_tab = ui.tab("Depth chart")
            counts_tab = ui.tab("Position counts")
            schedule_tab = ui.tab("Schedule")
            standings_tab = ui.tab("Standings")
            stats_tab = ui.tab("Stats")
            playoffs_tab = ui.tab("Playoffs")
            news_tab = ui.tab("Bitter")      # the league's social media site (Blake's name, Oct 23)
            awards_tab = ui.tab("Awards")
            game_tab = ui.tab("Game")
    # Come back to the tab you were on (e.g. after opening a player card). Bitter is
    # rebuilt only while you're looking at it (it rebuilds the whole season's news, ~1 s
    # by week 4 and several by the playoffs); otherwise it catches up when you open it.
    news_stale = {"yes": False}

    def news_showing():
        if startup:
            return False
        v = tabs.value
        return v is news_tab or v == "Bitter" or getattr(v, "props", {}).get("name") == "Bitter"

    # Home is redrawn only while you're looking at it, like Bitter (it reads the news).
    home_stale = {"yes": False}

    def on_tab(e):
        state.main_tab = e.value
        showing["page"] = nav.tab_name(e.value) or showing["page"]
        section_nav.refresh()
        page_row.refresh()
        if news_stale["yes"] and news_showing():
            news_stale["yes"] = False
            refresh_news_now()
        if home_stale["yes"] and showing["page"] == "Home":
            home_stale["yes"] = False
            refresh_home_now()
    tabs.on_value_change(on_tab)
    first_tab = first_page

    def noop(*_a, **_k):
        return None
    refresh_roster = refresh_contracts = refresh_depth = refresh_counts = refresh_schedule = noop
    refresh_standings = refresh_stats = refresh_playoffs = refresh_news = refresh_awards = noop
    refresh_home = noop

    async def home_settle():
        return None
    game_ctrl = _NoGame()
    with ui.tab_panels(tabs, value=first_tab).classes("w-full").style("background:transparent"):
        if not startup:
            with ui.tab_panel(home_tab).classes("p-0"):
                refresh_home_now, home_settle = build_home_tab(
                    go=go, watch=lambda: watch_my_game(), open_summary=lambda gid: open_summary(gid),
                    on_change=lambda: after_games(follow_week=False))

                def refresh_home():
                    if showing["page"] == "Home":
                        home_stale["yes"] = False
                        refresh_home_now()
                    else:
                        home_stale["yes"] = True
            with ui.tab_panel(roster_tab).classes("p-0"):
                refresh_roster = build_roster_tab()
            with ui.tab_panel(contracts_tab).classes("p-0"):
                refresh_contracts = build_contracts_tab(
                    on_change=lambda: (season_bar.refresh(), team_banner.refresh(), refresh_roster()))
        with ui.tab_panel(draft_tab).classes("p-0"):
            refresh_draft = build_draft_tab(
                on_change=lambda: (season_bar.refresh(), team_banner.refresh()),
                on_next=lambda: next_phase(), on_startup_done=lambda: startup_done())
        if not startup:
            with ui.tab_panel(depth_tab).classes("p-0"):
                refresh_depth = build_depth_tab(
                    on_change=lambda: (team_banner.refresh(), refresh_roster(), refresh_counts()))
            with ui.tab_panel(counts_tab).classes("p-0"):
                refresh_counts = build_counts_tab()
            with ui.tab_panel(schedule_tab).classes("p-0"):
                refresh_schedule = build_schedule_tab()
            with ui.tab_panel(standings_tab).classes("p-0"):
                refresh_standings = build_standings_tab()
            with ui.tab_panel(stats_tab).classes("p-0"):
                refresh_stats = build_stats_tab()
            with ui.tab_panel(playoffs_tab).classes("p-0"):
                refresh_playoffs = build_playoffs_tab(on_open_summary=lambda gid: open_summary(gid))
            with ui.tab_panel(news_tab).classes("p-0"):
                refresh_news_now = build_news_tab(on_open_summary=lambda gid: open_summary(gid))

                def refresh_news():
                    if news_showing():
                        news_stale["yes"] = False
                        refresh_news_now()
                    else:
                        news_stale["yes"] = True
            with ui.tab_panel(awards_tab).classes("p-0"):
                refresh_awards = build_awards_tab()
            with ui.tab_panel(game_tab).classes("p-0"):
                game_ctrl = build_game_tab(on_season_game_done=lambda: after_games(follow_week=False),
                                           on_open_summary=lambda gid: open_summary(gid))

    # ---- Simming (one small window that shows progress) ----------------
    with ui.dialog().props("persistent") as sim_dialog, ui.card().classes("p-6").style("min-width:420px"):
        sim_label = ui.label("").classes("condensed text-2xl")
        sim_bar = ui.linear_progress(value=0, show_value=False).props("color=green-10")
        ui.label("Every game is played in full, snap by snap, so each week takes a few seconds.") \
            .classes("legend")
        with ui.row().classes("justify-end w-full mt-2"):
            stop_btn = ui.button("Stop after this week", on_click=lambda: stop_sim()).props("flat no-caps")
    sim = {"stop": False}

    def stop_sim():
        sim["stop"] = True
        stop_btn.disable()
        stop_btn.text = "Stopping after this week..."

    async def sim_through(target):
        """Sim week by week through calendar week `target` (preseason weeks
        1-5, then regular-season week 1 = 6 ...)."""
        if game_ctrl.busy():
            ui.notify("You're watching your game in the Game tab. Finish it (or use Sim to the end) first.")
            return
        if season.season_over(league):
            return
        await home_settle()             # Home may still be reading the news; let it finish first
        first = season.calendar(league)
        sim["stop"] = False
        stop_btn.enable()
        stop_btn.text = "Stop after this week"
        sim_dialog.open()
        while not season.season_over(league) and season.calendar(league) <= target and not sim["stop"]:
            if season.cap_hold(league):
                break                   # over the cap at the start of the regular season (told below)
            sim_label.text = f"Simming: {season.week_label(league)}..."
            sim_bar.value = (season.calendar(league) - first) / max(1, target - first + 1)
            await run.io_bound(season.play_week, league)
        sim_dialog.close()
        mark_changed()
        after_games(follow_week=True)
        show_cap_hold()

    # ---- The salary cap deadlines (real NFL: under the cap when the league year and the
    # regular season start; season.cap_hold) -------------------------------------------
    with ui.dialog() as cap_dialog, ui.card().classes("p-6").style("min-width:460px; max-width:560px"):
        cap_text = ui.html("", sanitize=False)
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Roster tab (your staff's suggestions)",
                      on_click=lambda: (cap_dialog.close(), tabs.set_value(roster_tab))).props("flat no-caps")
            ui.button("Contracts tab", on_click=lambda: (cap_dialog.close(), tabs.set_value(contracts_tab))) \
                .props("no-caps color=green-10")

    def show_cap_hold():
        """True (and explains) if you're over the cap at a deadline."""
        from engine.contracts import fmt_money
        hold = season.cap_hold(league)
        if not hold:
            return False
        cap_text.content = (f'<div class="condensed text-2xl">You&#39;re {fmt_money(hold["short"])} over the salary cap</div>'
                            f'<div class="legend" style="margin-top:6px">The NFL&#39;s cap is hard: every team must be under '
                            f'it when {hold["when"]}. Get under it first: restructure or release players on the '
                            f'Contracts tab (Payroll; the cap effect is shown before you confirm), or approve your '
                            f'staff&#39;s suggestions on the Roster tab.</div>')
        cap_dialog.open()
        return True

    def next_season():
        if game_ctrl.busy():
            ui.notify("Finish the game you're watching first.")
            return
        start_next_season()
        state.main_tab = "Contracts"
        ui.notify(f"The {league.season - 1} season is in the books. The {league.season} league year begins.",
                  type="positive")
        ui.navigate.reload()

    # ---- The offseason's Next button ------------------------------------------
    with ui.dialog() as unsigned_dialog, ui.card().classes("p-6").style("min-width:460px"):
        unsigned_text = ui.html("", sanitize=False)
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Go back", on_click=unsigned_dialog.close).props("flat no-caps")
            ui.button("Open free agency anyway", on_click=lambda: confirm_next()) \
                .props("no-caps color=green-10")

    async def confirm_next():
        unsigned_dialog.close()
        await next_phase(True)

    async def next_phase(confirmed=False):
        from engine import free_agency as FA
        key = season.offseason_phase(league)[0] if season.in_offseason(league) else None
        if show_cap_hold():
            return
        await home_settle()             # Home may still be reading the news; let it finish first
        if key == "resign" and not confirmed:
            lost = [r for r in FA.expiring_for_you(league) if r["why"]]
            if lost:
                items = "".join(f"<li>{league.player(r['pid']).position} {league.player(r['pid']).name}: "
                                f"{r['why']}</li>" for r in lost)
                unsigned_text.content = (f'<div class="condensed text-2xl">These players become free agents</div>'
                                         f'<div class="legend">You haven\'t re-signed them. Other teams can sign '
                                         f'them in free agency (you can still bid).</div><ul style="margin:8px 0 0 '
                                         f'18px">{items}</ul>')
                unsigned_dialog.open()
                return
        sim_label.text = {"resign": "Opening free agency...", "draft": "Starting the draft...",
                          "drafting": "Finishing the draft and signing rookies...",
                          "camp": "Opening training camp..."}.get(key, "Playing out the free agency wave...")
        sim_bar.value = 0.5
        stop_btn.disable()
        sim_dialog.open()
        phase = await run.io_bound(advance_offseason)
        sim_dialog.close()
        if phase is None:
            state.main_tab = "Roster"
            ui.notify(f"Training camp is open. The {league.season} preseason starts with the Hall of Fame Game.",
                      type="positive")
            ui.navigate.reload()
            return
        if phase == "drafting":
            # The draft is waiting for your pick (the Draft tab).
            tabs.set_value(draft_tab)
            ui.notify("You're on the clock.", type="positive", position="top")
        elif key == "drafting":
            ui.notify(f"The {league.season} draft is complete. Rookies are signed; free agency goes on.",
                      type="positive", position="top")
        after_games(follow_week=False)

    async def startup_done():
        """The startup draft is over: your staff makes any picks left, then camp opens."""
        sim_label.text = "Finishing the startup draft, then opening training camp..."
        sim_bar.value = 0.5
        stop_btn.disable()
        sim_dialog.open()
        await run.io_bound(finish_startup)
        sim_dialog.close()
        state.main_tab = "Roster"
        ui.notify(f"Rosters are drafted and training camp is open. The {league.season} preseason starts with "
                  f"the Hall of Fame Game.", type="positive")
        ui.navigate.reload()

    def open_summary(gid):
        popups.open_game(gid)

    def watch_my_game():
        tabs.set_value(game_tab)
        game_ctrl.watch()

    def after_games(follow_week):
        season_bar.refresh()
        team_banner.refresh()
        refresh_roster()
        refresh_contracts()
        refresh_draft()
        refresh_depth()
        refresh_counts()
        refresh_schedule(follow_week=follow_week)
        refresh_standings()
        refresh_stats()
        refresh_playoffs()
        refresh_news()
        refresh_awards()
        refresh_home()
        game_ctrl.refresh()

    # ---- Ctrl+S saves -----------------------------------------------------
    def on_key(e):
        if e.action.keydown and not e.action.repeat and e.modifiers.ctrl and e.key.name.lower() == "s":
            do_save()
    ui.keyboard(on_key=on_key, ignore=[])
    # Stop the window's own Ctrl+S ("save this web page") from taking the key.
    ui.add_body_html("<script>document.addEventListener('keydown', e => {"
                     "if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') e.preventDefault();"
                     "});</script>")

    # ---- Leaving with unsaved changes (one small dialog) ----------------
    with ui.dialog() as leave_dialog, ui.card().classes("p-6"):
        ui.label("Save before leaving?").classes("condensed text-2xl")
        ui.label("You have unsaved changes in this game.").classes("legend")
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Cancel", on_click=leave_dialog.close).props("flat no-caps")
            ui.button("Leave without saving", on_click=lambda: go_to_menu(save=False)) \
                .props("flat no-caps color=red-9")
            ui.button("Save and leave", on_click=lambda: go_to_menu(save=True)) \
                .props("no-caps color=green-10")

    # ---- Save a copy (one small dialog) ----------------------------------
    with ui.dialog() as copy_dialog, ui.card().classes("p-6").style("min-width:420px"):
        ui.label("Save a copy").classes("condensed text-2xl")
        ui.label("Writes your game as it is right now to a new save. You keep playing "
                 "this one; load the copy any time from Load game.").classes("legend")
        copy_name = ui.input("Name of the copy").props("outlined dense").classes("w-full mt-2")
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Cancel", on_click=copy_dialog.close).props("flat no-caps")
            ui.button("Save copy", on_click=lambda: do_copy()).props("no-caps color=green-10")

    def open_copy_dialog():
        copy_name.value = f"{league.name} (copy {datetime.now():%b %d})"
        copy_dialog.open()

    def do_copy():
        name = (copy_name.value or "").strip()
        if not name:
            ui.notify("Give the copy a name first.")
            return
        if saves.name_taken(name):
            ui.notify("There's already a save with that name. Pick another.")
            return
        save_copy(name)
        copy_dialog.close()
        ui.notify(f'Saved a copy called "{name}".', type="positive")

    def do_save():
        if not state.dirty:
            return
        save_now()
        ui.notify("Game saved.", type="positive")

    def leave():
        if state.dirty:
            leave_dialog.open()
        else:
            go_to_menu(save=False)

    def go_to_menu(save):
        if save:
            save_now()
        close_game()
        ui.navigate.to("/")

    def choose_team(team_id):
        if team_id is None:
            ui.notify("Choose a team first.")
            return
        league.user_team_id = team_id
        state.team_id = team_id
        mark_changed()
        ui.navigate.reload()

    def change_team(team_id):
        state.team_id = team_id
        state.selected_id = None
        team_banner.refresh()
        refresh_roster()
        refresh_depth()
        refresh_counts()
        refresh_schedule()
        refresh_news()
