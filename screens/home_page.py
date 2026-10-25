# home_page.py
# The Home page: the overview you land on (layout research, Oct 21). This
# week's game, what needs you, your division, team leaders, injuries and the
# latest headlines, each linking to the full page. Fits on one screen.
#
# Look (Gemini's Step 3, Oct 25; styles in theme.STEP3_HOME_CSS): three columns,
# every card with a team-colored header band and a quick link, the week's game as
# a broadcast matchup with the last game as a strip under it, "Needs your
# attention" as an inbox of action rows, team leaders as a 2x3 grid.

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


def _streak(results):
    """The last results as small colored boxes (W green, L red, T gray)."""
    boxes = "".join(f'<span class="streak-box {r.lower()}">{r}</span>' for r in results)
    return f'<span class="streak-strip">{boxes}</span>'


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

    def card(title_html, link=None, aria=""):
        """A dashboard card: a team-colored header band (title, quick link) over a body.
        Returns (card, body); full-width parts (the matchup) go straight in the card."""
        sec = ui.element("section").classes("hcard").props(f'aria-label="{escape(aria)}"')
        with sec:
            with ui.element("div").classes("hcard-head"):
                ui.html(f'<span class="hcard-title">{title_html}</span>', sanitize=False)
                if link:
                    text, fn = link
                    ui.element("button").classes("hcard-link").props('type="button"') \
                        .on("click", lambda _e: fn())._text = f"{text} →"
        return sec

    def body(sec):
        with sec:
            return ui.element("div").classes("hcard-body")

    def text_button(text, fn, cls="home-textlink"):
        # (title: the full text on hover, where a strip cuts it short)
        ui.element("button").classes(cls).props(f'type="button" title="{escape(text)}"') \
            .on("click", lambda _e: fn())._text = text

    def main_button(text, fn):
        """The card's main action, in the team's color."""
        return ui.button(text, on_click=fn, color=None).props("no-caps unelevated dense") \
            .style("background:var(--turf); color:#fff; padding:2px 14px")

    def side_button(text, fn):
        return ui.button(text, on_click=fn, color=None).props("no-caps outline dense") \
            .style("color:var(--turf); padding:2px 12px")

    # ---- This week -------------------------------------------------------
    @ui.refreshable
    def this_week():
        team = you()
        if team is None:
            return
        rec = season.records(league)
        if season.in_offseason(league):
            key, title, text = season.offseason_phase(league)
            sec = card(f"{league.season} offseason", ("Contracts", lambda: go("Contracts")), "This week")
            with sec:
                ui.html(f'<div class="offseason-hero"><div class="oh-kicker">Now</div>'
                        f'<div class="oh-title">{escape(title)}</div><div class="oh-text">{escape(text)}</div></div>',
                        sanitize=False)
                with ui.element("div").classes("matchup-actions"):
                    if key in ("draft", "drafting"):
                        main_button("Go to the draft room" if key == "drafting" else "Scout the draft class",
                                    lambda: go("Draft"))
                    elif key == "coaching":
                        main_button("Go to Staff", lambda: go("Staff"))
                    else:
                        main_button("Go to Contracts", lambda: go("Contracts"))
                    if league.offseason_report and league.offseason_report.get("season") == league.season:
                        side_button("Offseason report", popups.open_offseason)
            return
        if season.season_over(league):
            champ = po.champion(league)
            sec = card(f"{league.season} season complete", ("Standings", lambda: go("Standings")), "This week")
            with sec:
                champ_line = (f'{escape(po.championship_name(league))} champion: '
                              f'{escape(league.team(champ).name)}') if champ else ""
                ui.html(f'<div class="offseason-hero"><div class="oh-kicker">Final record</div>'
                        f'<div class="oh-title">{escape(team.name)} finished '
                        f'{season.record_text(rec[team.id])}</div><div class="oh-text">{champ_line}</div></div>',
                        sanitize=False)
                last_game(team)
            return
        pre, post = season.in_preseason(league), season.in_playoffs(league)
        if pre:
            when = f"{season.week_label(league)} · {pre_date_text(league.season, league.pre_week)}"
        elif post:
            d = po.round_date(league, league.playoff_round)
            when = f"{season.week_label(league)} · {d:%a}, {d:%b} {d.day}"
        else:
            when = f"Week {league.week} · {date_text(league.season, league.week)}"
        sec = card(f"This week · {escape(when)}", ("Schedule", lambda: go("Schedule")), "This week")
        g = season.team_current_game(league, team.id)
        with sec:
            if g is None:
                ui.html(f'<div class="offseason-hero"><div class="oh-kicker">No game</div>'
                        f'<div class="oh-title">{escape(_no_game_text(team, pre, post))}</div></div>',
                        sanitize=False)
            else:
                home = g["home"] == team.id

                def tag(tid):
                    if pre:
                        return ""
                    if post:
                        seed = po.seed_of(league, tid)
                        return f"#{seed} seed" if seed else ""
                    return season.record_text(rec[tid])

                def side(tid, score, cls):
                    t = league.team(tid)
                    won = g["played"] and score == max(g["home_score"], g["away_score"]) \
                        and g["home_score"] != g["away_score"]
                    rec_pill = f'<span class="matchup-record">{tag(tid)}</span>' if tag(tid) else ""
                    pts = (f'<div class="matchup-score{" won" if won else ""}">{score}</div>'
                           if g["played"] else "")
                    return (f'<div class="matchup-side {cls}{" is-you" if tid == team.id else ""}">'
                            f'<div class="matchup-abbrev">{escape(t.abbrev)}</div>'
                            f'<div class="matchup-teamname">{popups.team_link(t)}</div>{rec_pill}{pts}</div>')
                # Away team on the left, home team on the right, like a TV scoreboard.
                if g["played"]:
                    badge = f'<div class="matchup-vs-badge final">FINAL{" OT" if g["overtime"] else ""}</div>'
                else:
                    badge = f'<div class="matchup-vs-badge">{"VS" if g.get("neutral") else "@"}</div>'
                ui.html(f'<div class="matchup-hero">{side(g["away"], g["away_score"], "")}{badge}'
                        f'{side(g["home"], g["home_score"], "home-side")}</div>', sanitize=False)
                kind = ("Hall of Fame Game" if g.get("kind") == "hof" else "Preseason game" if pre
                        else "Playoff game" if post else "Home game" if home else "Road game")
                site = f" · {season.site_text(league, g)}" if g.get("neutral") else ""
                with ui.element("div").classes("matchup-actions"):
                    ui.label(kind + site).classes("legend")
                    if not g["played"]:
                        main_button("Watch my game", watch) \
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
        """Your last game as a strip at the bottom of the card: result, the story, the box score."""
        last = season.last_team_game(league, team.id)
        if last is None:
            return
        opp = league.team(last["away"] if last["home"] == team.id else last["home"])
        k, txt = result_text(last, team.id)
        where = "vs" if last["home"] == team.id else "at"
        head = next((s["headline"] for s in news_box["mine"] if s.get("kind") == "game"
                     and set(s.get("teams") or []) == {last["home"], last["away"]}), None)
        with ui.element("div").classes("last-game-strip"):
            pill = {"W": "is-win", "L": "is-loss"}.get(k, "is-tie")
            ui.html(f'<span class="last-game-pill {pill}">{escape(txt)}</span>', sanitize=False)
            with ui.element("div").classes("lg-mid"):
                ui.html(f'Last game {where} {popups.team_link(opp)}{" · " if head else ""}',
                        sanitize=False).style("display:inline")
                if head:
                    text_button(head, lambda: go("Bitter"))
            text_button("Game summary", lambda gid=last["id"]: open_summary(gid))

    # ---- Needs your attention -------------------------------------------
    @ui.refreshable
    def attention():
        team = you()
        if team is None:
            return
        items = _attention_items(team.id)
        sec = card(f'Needs your attention <span class="hcount">({len(items)})</span>',
                   ("Open roster", lambda: go("Roster")), "Needs your attention")
        with body(sec):
            if not items:
                ui.label("Nothing needs you right now.").classes("legend")
            for it in items:
                with ui.element("div").classes(f"attn-row {it['kind']}"):
                    ui.html(f'<div class="attn-main"><span class="attn-badge">{escape(it["tag"])}</span>'
                            f'<div class="attn-text">{it["html"]}</div></div>', sanitize=False) \
                        .style("min-width:0")
                    with ui.element("div").classes("attn-actions"):
                        for label, fn, primary in it["buttons"]:
                            (main_button if primary else side_button)(label, fn)

    def _attention_items(tid):
        # kind: attn-urgent (game-day shortfalls), attn-trade (trade calls, staff requests),
        # attn-info (injured reserve, activations, roster notes)
        items = []
        for i, r in enumerate(season.staff_requests(league)):
            items.append({"tag": "Staff asks", "kind": "attn-trade", "html": escape(r["why"]),
                          "buttons": [("Approve", lambda i=i: answer(i, True), True),
                                      ("Decline", lambda i=i: answer(i, False), False)]})
        # AI teams' trade offers (trades.py, Oct 23): each good until the next week or phase.
        from engine import trades
        for o in trades.inbox(league):
            team_name = league.team(o["team"]).name
            items.append({"tag": "Trade call", "kind": "attn-trade",
                          "html": (f'The {escape(team_name)} called: they want '
                                   f'{escape(trades.side_text(league, o["give"]))} for '
                                   f'{escape(trades.side_text(league, o["get"]))}.'
                                   f'<div class="legend">Good until your next week or phase.</div>'),
                          "buttons": [("See offers", lambda: go("Trades"), True)]})
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
                items.append({"tag": "Suggestion", "kind": "attn-info",
                              "html": (f'{_pos(p)} {_plink(p)}: {escape(part)}, out about {weeks} more weeks.'
                                       f'<div class="legend">Injured reserve would free his roster spot (he\'d '
                                       f'miss at least {transactions.IR_MIN_GAMES} games).</div>'),
                              "buttons": [("Place on IR", lambda pid=p.id: move("ir", pid), True)]})
            for p in transactions.reserve_players(league, tid):
                if league.reserve[p.id]["list"] != "PSIR" and transactions.can_return(league, league.injuries, p.id):
                    handled.add(f"{p.position} {p.first_name} {p.last_name} ")
                    items.append({"tag": "Ready", "kind": "attn-info",
                                  "html": f'{_pos(p)} {_plink(p)} is healthy and can come off the reserve list.',
                                  "buttons": [("Activate", lambda pid=p.id: move("activate", pid), True)]})
        game_day = []
        for w in transactions.roster_warnings(league, league.injuries, tid):
            if any(w.startswith(h) for h in handled):
                continue
            urgent = "game day needs" in w
            item = {"tag": "Shortfall" if urgent else "Roster", "kind": "attn-urgent" if urgent else "attn-info",
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
                        f'<span class="num">{r["pa"]}</span><span class="num">{_streak(r["results"][-5:])}</span></div>')
        sec = card(f"{escape(team.division)} Division", ("Full standings", lambda: go("Standings")), "Division")
        with body(sec):
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
        tiles = []
        for label, key, show in cats:
            best = max(totals.items(), key=lambda kv: kv[1].get(key, 0), default=None)
            if not best or not best[1].get(key):
                continue
            p = league.player(best[0])
            vals = {k: (int(v) if isinstance(v, float) and k != "sacks" and v == int(v) else v)
                    for k, v in best[1].items()}
            tiles.append(f'<div class="leader-tile"><div class="leader-cat">{label}</div>'
                         f'<div class="leader-main"><span class="leader-player">{_pos(p)} {_plink(p)}</span>'
                         f'<span class="leader-stat">{show(vals)}</span></div></div>')
        sec = card(f"Team leaders, {league.season}", ("Team stats", lambda: go("Stats")), "Team leaders")
        with body(sec):
            if tiles:
                ui.html(f'<div class="leaders-grid">{"".join(tiles)}</div>', sanitize=False)
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
        sec = card(f'Injuries <span class="hcount">({len(hurt)})</span>', ("Roster", lambda: go("Roster")),
                   "Injuries")
        with body(sec):
            if not hurt:
                ui.label("Nobody on your team is hurt.").classes("legend")
            rows = []
            for pid, inj in hurt[:INJURIES_SHOWN]:
                p = league.player(pid)
                code = injury_code(pid)
                rows.append(f'<div class="home-inj-row"><span>{_pos(p)}</span><span>{_plink(p)}</span>'
                            f'<span class="home-inj-desc">{escape(inj.get("part", ""))}</span>'
                            f'<span class="inj-tag inj-{code.lower()}" title="{escape(injury_text(pid) or "")}">'
                            f'{code}</span></div>')
            if len(hurt) > INJURIES_SHOWN:
                rows.append(f'<div class="legend" style="padding-top:6px">and {len(hurt) - INJURIES_SHOWN} more '
                            f'(Roster page)</div>')
            ui.html("".join(rows), sanitize=False)

    # ---- Around the league (Bitter) ------------------------------------------
    @ui.refreshable
    def headlines():
        sec = card("Around the league", ("Open Bitter", lambda: go("Bitter")), "Around the league")
        with body(sec):
            if news_box["items"] is None:
                ui.label("Loading headlines...").classes("legend")
                return
            if not news_box["items"]:
                ui.label("No stories yet.").classes("legend")
            for s, mine in news_box["items"]:
                with ui.element("div").classes("wire-item"):
                    ui.html(f'<span class="wire-tag{" is-mine" if mine else ""}">'
                            f'{"Your team" if mine else KIND_LABELS.get(s.get("kind"), "News")}</span>',
                            sanitize=False).style("display:inline")
                    text_button(s["headline"], lambda: go("Bitter"), "wire-headline")

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

    # ---- Layout: three columns -----------------------------------------------
    with ui.element("div").classes("home-grid"):
        with ui.element("div").classes("home-col"):
            this_week()
            attention()
        with ui.element("div").classes("home-col"):
            division()
            leaders()
        with ui.element("div").classes("home-col"):
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


# The cards, matchup, inbox, leaders and wire are theme.STEP3_HOME_CSS (Gemini's
# Step 3); these are the Home-only pieces it doesn't cover.
CSS = f"""
<style>
  .hcount {{ color: {theme.INK_SOFT}; font-weight: 600; }}
  .legend a.tlink, .matchup-actions .legend {{ white-space: nowrap; }}
  .div-row {{ display: grid; grid-template-columns: minmax(0, 1fr) 46px 40px 40px 104px; gap: 8px; align-items: center;
             padding: 5px 6px; border-top: 1px solid #EEF1EC; font-size: 14px; font-variant-numeric: tabular-nums; }}
  .div-row .num {{ text-align: right; }}
  .div-row.mine {{ background: #FFF6CF; font-weight: 600; }}
  .div-head {{ font: 600 13.5px 'Barlow Condensed', sans-serif; color: {theme.INK_SOFT}; border-top: 0; padding-top: 0;
              text-transform: uppercase; letter-spacing: .03em; }}
</style>
"""
