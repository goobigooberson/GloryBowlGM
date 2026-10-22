# home_page.py
# The Home page: the overview you land on (layout research, Oct 21). This
# week's game, what needs you, your division, team leaders, injuries and the
# latest headlines, each linking to the full page. Fits on one screen.

import asyncio
from html import escape

from nicegui import background_tasks, run, ui

from engine import news
from engine import playoffs as po
from engine import season
from engine import stats
from engine import transactions
from . import popups, theme
from .schedule_page import date_text, pre_date_text, result_text
from .state import state, injury_code, injury_text, mark_changed

KIND_LABELS = {"game": "Game", "performance": "Big game", "milestone": "Milestone", "injury": "Injuries",
               "moves": "Roster moves", "playoffs": "Playoffs", "draft": "Draft", "retirement": "Retirement",
               "season": "Season", "awards": "Awards", "storyline": "Storyline", "rankings": "Rankings",
               "business": "Business"}
HEADLINES = 6           # stories in "Around the league"
YOUR_HEADLINES = 2      # of them, at most this many about your team (listed first)
INJURIES_SHOWN = 8


def _pos(p):
    return f'<span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span>'


def _plink(p):
    return f'<a class="plink" href="/player/{p.id}">{escape(p.name)}</a>'


def _wl(results):
    return "".join(f'<span class="wl-box wl-{r}">{r}</span>' for r in results)


def build_home_tab(go, watch, open_summary, on_change):
    """Builds the Home page. go(tab) shows another tab; watch() plays your game in
    the Game tab; open_summary(gid) opens a box score; on_change() redraws the
    other tabs after a move made here. Returns (refresh, settle): refresh()
    redraws it, `await settle()` waits for headlines still loading (the sim
    must not change the league while news is being read)."""
    league = state.league
    news_box = {"items": None, "mine": [], "task": None, "again": False}

    def you():
        return league.team(league.user_team_id) if league.user_team_id else None

    def link_button(text, on_click):
        ui.element("button").classes("home-link").props('type="button"').on("click", lambda _e: on_click()) \
            ._text = text

    def card_head(title, link=None):
        with ui.element("div").classes("hcard-h"):
            ui.html(title, sanitize=False)
            if link:
                link_button(*link)

    # ---- This week -------------------------------------------------------
    @ui.refreshable
    def this_week():
        team = you()
        if team is None:
            return
        rec = season.records(league)
        with ui.element("section").classes("hcard").props('aria-label="This week"'):
            if season.in_offseason(league):
                key, title, text = season.offseason_phase(league)
                ui.label(f"{league.season} offseason").classes("hkind hkind-turf")
                ui.label(title).classes("home-big")
                ui.label(text).classes("legend").style("margin-top:2px")
                with ui.row().classes("gap-2 mt-3"):
                    if league.offseason_report and league.offseason_report.get("season") == league.season:
                        ui.button("Offseason report", on_click=popups.open_offseason) \
                            .props("no-caps outline color=green-10")
                    if key in ("draft", "drafting"):
                        ui.button("Go to the draft room" if key == "drafting" else "Scout the draft class",
                                  on_click=lambda: go("Draft")).props("no-caps unelevated color=green-10")
                    elif key == "coaching":
                        ui.button("Go to Staff", on_click=lambda: go("Staff")) \
                            .props("no-caps unelevated color=green-10")
                    else:
                        ui.button("Go to Contracts", on_click=lambda: go("Contracts")) \
                            .props("no-caps unelevated color=green-10")
                return
            if season.season_over(league):
                champ = po.champion(league)
                ui.label(f"{league.season} season complete").classes("hkind hkind-turf")
                ui.label(f"{team.name} finished {season.record_text(rec[team.id])}").classes("home-big")
                if champ:
                    ui.label(f"{po.championship_name(league)} champion: {league.team(champ).name}") \
                        .classes("legend")
                last_game(team)
                return
            pre, post = season.in_preseason(league), season.in_playoffs(league)
            if pre:
                when = f"{season.week_label(league)} · {pre_date_text(league.season, league.pre_week)}"
            elif post:
                d = po.round_date(league, league.playoff_round)
                when = f"{season.week_label(league)} · {d:%A}, {d:%b} {d.day}"
            else:
                when = f"Week {league.week} · {date_text(league.season, league.week)}"
            ui.label(f"This week · {when}").classes("hkind hkind-turf")
            g = season.team_current_game(league, team.id)
            with ui.row().classes("w-full items-center gap-4 mt-1").style("flex-wrap:wrap"):
                with ui.column().classes("gap-0").style("flex:1 1 260px"):
                    if g is None:
                        ui.label(_no_game_text(team, pre, post)).classes("home-big")
                    else:
                        home = g["home"] == team.id
                        # A scoreboard: away team left, home team right (Oct 22, "spruce up the UI").
                        def tag(tid):
                            if pre:
                                return ""
                            if post:
                                seed = po.seed_of(league, tid)
                                return f"#{seed} seed" if seed else ""
                            return season.record_text(rec[tid])

                        def side(tid, score):
                            t = league.team(tid)
                            won = g["played"] and score == max(g["home_score"], g["away_score"]) \
                                and g["home_score"] != g["away_score"]
                            return (f'<div class="mt-team{" you" if tid == team.id else ""}">'
                                    f'<span class="mt-ab">{escape(t.abbrev)}</span>'
                                    f'<span class="mt-nm">{popups.team_link(t, t.nickname)}</span>'
                                    f'<span class="mt-rec">{tag(tid)}</span>'
                                    + (f'<span class="mt-pts{" won" if won else ""}">{score}</span>'
                                       if g["played"] else "") + '</div>')
                        mid = ("FINAL" + (" (OT)" if g["overtime"] else "")) if g["played"] else \
                            ("VS" if g.get("neutral") else "AT")
                        ui.html(f'<div class="matchup">{side(g["away"], g["away_score"])}'
                                f'<div class="mt-mid">{mid}</div>{side(g["home"], g["home_score"])}</div>',
                                sanitize=False).classes("w-full")
                        kind = ("Hall of Fame Game" if g.get("kind") == "hof" else "Preseason game" if pre
                                else "Playoff game" if post else "Home game" if home else "Road game")
                        site = f" · {season.site_text(league, g)}" if g.get("neutral") else ""
                        ui.label(kind + site).classes("legend").style("margin-top:4px")
                if g is not None and not g["played"]:
                    ui.button("Watch my game", on_click=watch).props("no-caps outline color=green-10") \
                        .tooltip("Play it snap by snap. The other games sim when you press Sim week.")
            last_game(team)

    def _no_game_text(team, pre, post):
        if pre and league.pre_week == 1:
            return "Only the Hall of Fame Game is played this week"
        if post:
            seed = po.seed_of(league, team.id)
            if seed is None:
                return "Missed the playoffs"
            if any(g["played"] and po.loser(g) == team.id for g in league.playoffs):
                return "Season over: out of the playoffs"
            if league.playoff_round == 1 and seed == 1:
                return "First-round bye (#1 seed)"
            if league.playoff_round == 4:
                return "Pro Bowl week (no game)"
            return f"#{seed} seed: no game this week"
        return "Preseason bye" if pre else "Bye week"

    def last_game(team):
        last = season.last_team_game(league, team.id)
        if last is None:
            return
        opp = league.team(last["away"] if last["home"] == team.id else last["home"])
        k, txt = result_text(last, team.id)
        where = "vs" if last["home"] == team.id else "at"
        head = next((s["headline"] for s in news_box["mine"] if s.get("kind") == "game"
                     and set(s.get("teams") or []) == {last["home"], last["away"]}), None)
        with ui.element("div").classes("home-last"):
            ui.label("Last game").classes("hkind")
            ui.html(f'<b>{_wl([k])} {txt.split(" ", 1)[1]} {where} {popups.team_link(opp)}</b>', sanitize=False)
            if head:
                ui.label(head).classes("legend").style("font-style:italic")
            link_button("Game summary", lambda gid=last["id"]: open_summary(gid))

    # ---- Needs your attention -------------------------------------------
    @ui.refreshable
    def attention():
        team = you()
        if team is None:
            return
        items = _attention_items(team.id)
        with ui.element("section").classes("hcard").props('aria-label="Needs your attention"'):
            card_head(f'Needs your attention <span class="hcount">({len(items)})</span>',
                      ("Open roster", lambda: go("Roster")))
            if not items:
                ui.label("Nothing needs you right now.").classes("legend").style("padding:6px 0")
            for it in items:
                with ui.element("div").classes("att-row"):
                    ui.label(it["tag"]).classes("att-tag " + it["tag_class"])
                    ui.html(it["html"], sanitize=False).classes("att-text")
                    with ui.row().classes("gap-2 no-wrap"):
                        for label, fn, primary in it["buttons"]:
                            ui.button(label, on_click=fn).props(
                                "no-caps " + ("unelevated color=green-10" if primary else "outline color=green-10"))

    def _attention_items(tid):
        items = []
        for i, r in enumerate(season.staff_requests(league)):
            items.append({"tag": "Staff asks", "tag_class": "att-ask", "html": escape(r["why"]),
                          "buttons": [("Approve", lambda i=i: answer(i, True), True),
                                      ("Decline", lambda i=i: answer(i, False), False)]})
        if not season.user_moves_open(league):
            return items
        handled = set()
        if not transactions.in_camp(league):
            roster = [p for p in league.players if league.rosters.get(p.id) == tid]
            for p in sorted(roster, key=lambda p: -transactions.injured_weeks(league, league.injuries, p.id)):
                weeks = transactions.injured_weeks(league, league.injuries, p.id)
                if weeks < transactions.IR_AT_WEEKS or not any(a == "ir" for a, _l, _t in season.user_options(league, p.id)):
                    continue
                handled.add(f"{p.position} {p.first_name} {p.last_name} ")
                part = league.injuries[p.id].get("part", "injury")
                items.append({"tag": "Suggestion", "tag_class": "att-sg",
                              "html": (f'{_pos(p)} {_plink(p)}: {escape(part)}, out about {weeks} more weeks.'
                                       f'<div class="legend">Injured reserve would free his roster spot (he\'d '
                                       f'miss at least {transactions.IR_MIN_GAMES} games).</div>'),
                              "buttons": [("Place on IR", lambda pid=p.id: move("ir", pid), True)]})
            for p in transactions.reserve_players(league, tid):
                if league.reserve[p.id]["list"] != "PSIR" and transactions.can_return(league, league.injuries, p.id):
                    handled.add(f"{p.position} {p.first_name} {p.last_name} ")
                    items.append({"tag": "Ready", "tag_class": "att-sg",
                                  "html": f'{_pos(p)} {_plink(p)} is healthy and can come off the reserve list.',
                                  "buttons": [("Activate", lambda pid=p.id: move("activate", pid), True)]})
        game_day = []
        for w in transactions.roster_warnings(league, league.injuries, tid):
            if any(w.startswith(h) for h in handled):
                continue
            urgent = "game day needs" in w
            item = {"tag": "Game day" if urgent else "Roster", "tag_class": "att-gd" if urgent else "att-sg",
                    "html": escape(w), "buttons": [("Open roster", lambda: go("Roster"), False)]}
            (game_day if urgent else items).append(item)
        return game_day + items      # game-day shortfalls first

    def answer(index, approve):
        done, msg = season.answer_staff_request(league, index, approve)
        ui.notify(msg, type="positive" if done else "warning", position="top")
        mark_changed()
        on_change()

    def move(action, pid):
        done, msg = season.user_move(league, action, pid)
        ui.notify(msg, type="positive" if done else "warning", position="top")
        if done:
            mark_changed()
            on_change()

    # ---- Division ----------------------------------------------------------
    @ui.refreshable
    def division():
        team = you()
        if team is None:
            return
        rec = season.records(league)
        ids = season.division_standings(league, rec)[team.conference][team.division]
        rows = ['<div class="div-row div-head"><span>Team</span><span class="num">W-L</span>'
                '<span class="num">PF</span><span class="num">PA</span><span class="num">Last 5</span></div>']
        for t in ids:
            r = rec[t]
            rows.append(f'<div class="div-row{" mine" if t == team.id else ""}"><span>{popups.team_link(league.team(t))}'
                        f'</span><span class="num">{season.record_text(r)}</span><span class="num">{r["pf"]}</span>'
                        f'<span class="num">{r["pa"]}</span><span class="num">{_wl(r["results"][-5:])}</span></div>')
        with ui.element("section").classes("hcard").props('aria-label="Division"'):
            card_head(f"{escape(team.division)} Division", ("Full standings", lambda: go("Standings")))
            ui.html("".join(rows), sanitize=False)

    # ---- Team leaders --------------------------------------------------------
    @ui.refreshable
    def leaders():
        team = you()
        if team is None:
            return
        totals = stats.team_player_totals(league, team.id)
        cats = [("Passing", "pass_yds", lambda s: f'{s["pass_yds"]:,} yds · {s.get("pass_td", 0)} TD'),
                ("Rushing", "rush_yds", lambda s: f'{s["rush_yds"]:,} yds · {s.get("rush_td", 0)} TD'),
                ("Receiving", "rec_yds", lambda s: f'{s.get("rec", 0)} rec · {s["rec_yds"]:,} yds'),
                ("Sacks", "sacks", lambda s: f'{s["sacks"]:.1f}'),
                ("Tackles", "tkl", lambda s: f'{s["tkl"]}'),
                ("Interceptions", "def_int", lambda s: f'{s["def_int"]}')]
        rows = []
        for label, key, show in cats:
            best = max(totals.items(), key=lambda kv: kv[1].get(key, 0), default=None)
            if not best or not best[1].get(key):
                continue
            p = league.player(best[0])
            vals = {k: (int(v) if isinstance(v, float) and k != "sacks" and v == int(v) else v)
                    for k, v in best[1].items()}
            rows.append(f'<div class="lead-row"><span class="hkind">{label}</span><span>{_pos(p)} {_plink(p)}</span>'
                        f'<span class="num" style="font-weight:600">{show(vals)}</span></div>')
        with ui.element("section").classes("hcard").props('aria-label="Team leaders"'):
            card_head(f"Team leaders, {league.season}", ("Team stats", lambda: go("Stats")))
            if rows:
                ui.html("".join(rows), sanitize=False)
            else:
                ui.label("No regular-season games yet this season.").classes("legend")

    # ---- Injuries ------------------------------------------------------------
    @ui.refreshable
    def injuries():
        team = you()
        if team is None:
            return
        hurt = [(pid, inj) for pid, inj in league.injuries.items()
                if inj.get("team") == team.id and injury_code(pid)]
        hurt.sort(key=lambda x: -x[1].get("weeks", 0))
        with ui.element("section").classes("hcard").props('aria-label="Injuries"'):
            card_head(f'Injuries <span class="hcount">({len(hurt)})</span>')
            if not hurt:
                ui.label("Nobody on your team is hurt.").classes("legend")
            rows = []
            for pid, inj in hurt[:INJURIES_SHOWN]:
                p = league.player(pid)
                code = injury_code(pid)
                rows.append(f'<div class="inj-row"><span>{_pos(p)}</span><span>{_plink(p)} <span class="legend">'
                            f'{escape(inj.get("part", ""))}</span></span><span class="inj-tag inj-{code.lower()}" '
                            f'title="{escape(injury_text(pid) or "")}">{code}</span></div>')
            if len(hurt) > INJURIES_SHOWN:
                rows.append(f'<div class="legend" style="padding-top:6px">and {len(hurt) - INJURIES_SHOWN} more '
                            f'(Roster page)</div>')
            ui.html("".join(rows), sanitize=False)

    # ---- Around the league (Bitter) ------------------------------------------
    @ui.refreshable
    def headlines():
        with ui.element("section").classes("hcard").props('aria-label="Around the league"'):
            card_head("Around the league", ("Open Bitter", lambda: go("Bitter")))
            if news_box["items"] is None:
                ui.label("Loading headlines...").classes("legend")
                return
            if not news_box["items"]:
                ui.label("No stories yet.").classes("legend")
            for s, mine in news_box["items"]:
                b = ui.element("button").classes("story-btn").props('type="button"').on("click", lambda _e: go("Bitter"))
                with b:
                    ui.label(("Your team · " if mine else "") + KIND_LABELS.get(s.get("kind"), "News")) \
                        .classes("hkind")
                    ui.label(s["headline"]).classes("story-head")

    def read_news():
        tid = league.user_team_id
        mine = [s for s in news.stories(league, team_id=tid) if s.get("season") == league.season] if tid else []
        everyone = [s for s in news.stories(league) if s.get("season") == league.season]
        picked = [(s, True) for s in mine[:YOUR_HEADLINES]]
        seen = {s["id"] for s, _m in picked}
        picked += [(s, False) for s in everyone if s["id"] not in seen][:HEADLINES - len(picked)]
        return mine, picked

    async def load_news():
        # Reads the news in the background (it can take a few seconds late in a
        # season) and goes again if something changed while it was reading.
        while news_box["again"]:
            news_box["again"] = False
            for _try in range(3):
                try:
                    mine, picked = await run.io_bound(read_news)
                    break
                except Exception:   # the league changed while it was being read: try again shortly
                    await asyncio.sleep(1.0)
            else:
                mine, picked = [], []
            news_box["mine"], news_box["items"] = mine, picked
        news_box["task"] = None
        headlines.refresh()
        this_week.refresh()

    def refresh_news():
        news_box["again"] = True
        if news_box["task"] is None:
            news_box["task"] = background_tasks.create(load_news())

    # ---- Layout --------------------------------------------------------------
    with ui.element("div").classes("home-grid"):
        with ui.element("div").classes("home-col").style("flex: 1.35 1 440px"):
            this_week()
            attention()
        with ui.element("div").classes("home-col").style("flex: 1 1 330px"):
            division()
            leaders()
        with ui.element("div").classes("home-col").style("flex: 1 1 330px"):
            injuries()
            headlines()

    def refresh():
        for part in (this_week, attention, division, leaders, injuries):
            part.refresh()
        refresh_news()

    async def settle():
        while news_box["task"] is not None:
            await asyncio.sleep(0.1)

    refresh_news()
    return refresh, settle


CSS = f"""
<style>
  .home-grid {{ display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-start; width: 100%;
               max-width: 1560px; margin: 0 auto; padding: 14px 16px; }}
  .home-col {{ display: flex; flex-direction: column; gap: 14px; min-width: 0; }}
  .hcard {{ background: {theme.PAPER}; border: 1px solid {theme.LINE}; border-radius: 6px; padding: 14px 16px; }}
  .hcard-h {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 19px; color: {theme.TURF};
             display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 6px; }}
  .hcount {{ color: {theme.INK_SOFT}; font-weight: 600; }}
  .hkind {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 12.5px; text-transform: uppercase;
           letter-spacing: .05em; color: {theme.INK_SOFT}; }}
  .hkind-turf {{ color: {theme.TURF}; }}
  .home-big {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 30px; line-height: 1.1; }}
  .home-big-soft {{ color: {theme.INK_SOFT}; font-weight: 600; font-size: 22px; margin-left: 6px; }}
  .home-last {{ border-top: 1px solid #EEF1EC; margin-top: 12px; padding-top: 10px; display: flex; flex-wrap: wrap;
               align-items: baseline; gap: 4px 14px; }}
  .home-link {{ background: none; border: 0; padding: 0; font: 500 14px 'Barlow', sans-serif; color: {theme.TURF};
               text-decoration: underline; cursor: pointer; }}
  .home-link:hover {{ color: {theme.TURF_DARK}; }}
  .att-row {{ display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: 4px 12px; align-items: center;
             padding: 8px 0; border-top: 1px solid #EEF1EC; font-size: 14.5px; line-height: 1.35; }}
  .att-tag {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 12px; text-transform: uppercase;
             letter-spacing: .04em; padding: 2px 7px; border-radius: 3px; white-space: nowrap; justify-self: start; }}
  .att-gd {{ background: #FCE3DD; color: #8E2A19; }}
  .att-sg {{ background: #EEF1EC; color: #46515A; }}
  .att-ask {{ background: #FFF6CF; color: #6B5300; }}
  .wl-box {{ display: inline-flex; width: 19px; height: 19px; align-items: center; justify-content: center;
            border-radius: 3px; font: 700 12px 'Barlow Condensed', sans-serif; color: white; margin-left: 2px;
            vertical-align: 1px; }}
  .wl-W {{ background: #23703A; }} .wl-L {{ background: #A3321F; }} .wl-T {{ background: #6B757D; }}
  .div-row {{ display: grid; grid-template-columns: minmax(0, 1fr) 46px 40px 40px 112px; gap: 8px; align-items: center;
             padding: 5px 6px; border-top: 1px solid #EEF1EC; font-size: 14.5px; font-variant-numeric: tabular-nums; }}
  .div-row .num {{ text-align: right; }}
  .div-row.mine {{ background: #FFF6CF; font-weight: 600; }}
  .div-head {{ font: 600 14px 'Barlow Condensed', sans-serif; color: {theme.INK_SOFT}; border-top: 0; padding-top: 0; }}
  .lead-row {{ display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: 10px; align-items: center;
              padding: 6px 0; border-top: 1px solid #EEF1EC; font-size: 14.5px; }}
  .inj-row {{ display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 10px; align-items: center;
             padding: 6px 0; border-top: 1px solid #EEF1EC; font-size: 14.5px; }}
  .story-btn {{ display: block; width: 100%; text-align: left; background: transparent; border: 0;
               border-top: 1px solid #EEF1EC; padding: 8px 0; font: inherit; color: inherit; cursor: pointer; }}
  .story-btn:hover .story-head {{ text-decoration: underline; }}
  .story-head {{ font-weight: 600; font-size: 15px; line-height: 1.3; }}
  /* Card titles as a green header band, like the draft board's header row */
  .hcard-h {{ margin: -14px -16px 8px; padding: 7px 16px 6px; background: {theme.TURF}; color: white;
             border-radius: 3px 3px 0 0; font-size: 18px; letter-spacing: .02em; }}
  .hcard-h .hcount {{ color: rgba(255,255,255,.75); }}
  .hcard-h .home-link {{ color: {theme.FLAG}; font-size: 13.5px; }}
  .hcard-h .home-link:hover {{ color: white; }}
  /* This week's game as a scoreboard */
  .matchup {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: stretch; margin-top: 8px;
             background: #18222B; color: white; border-radius: 4px; overflow: hidden; }}
  .mt-team {{ display: grid; grid-template-columns: auto 1fr auto; grid-template-rows: auto auto; column-gap: 10px;
             align-items: center; padding: 10px 12px; min-width: 0; }}
  .mt-team.you {{ box-shadow: inset 0 -3px 0 {theme.FLAG}; }}
  .mt-ab {{ grid-row: 1 / 3; font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 36px;
           line-height: 1; }}
  .mt-nm {{ font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .mt-nm a {{ color: white; }}
  .mt-rec {{ grid-column: 2; font-size: 13px; opacity: .7; font-variant-numeric: tabular-nums; }}
  .mt-pts {{ grid-column: 3; grid-row: 1 / 3; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
            font-size: 38px; opacity: .6; }}
  .mt-pts.won {{ opacity: 1; color: {theme.FLAG}; }}
  .mt-mid {{ display: flex; align-items: center; justify-content: center; padding: 0 14px;
            font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 16px; letter-spacing: .08em;
            background: rgba(255,255,255,.07); color: {theme.FLAG}; }}
</style>
"""
