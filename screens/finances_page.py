# finances_page.py
# Team finances (Oct 26; Blake: "two prices a year", "full books, all teams"):
#   Finances          (Team section) a team's business: your two ticket prices with your
#                     staff's recommendation and forecast, the profit and loss, every home
#                     game's crowd, the stadium and market, past seasons. Other teams: view only.
#   League finances   (League section) every team's revenue, profit, crowds, ticket price and
#                     value, like the Forbes list.
# Rules live in engine/finances.py; this file only draws them.

from html import escape

from nicegui import ui

from engine import finances as F
from engine import formatting as fmt
from engine import season
from . import popups
from .state import state, FREE_AGENTS, mark_changed

CSS = """
<style>
  .fin-grid { display: grid; grid-template-columns: minmax(0, 1fr) 430px; gap: 20px; align-items: start; }
  @media (max-width: 1250px) { .fin-grid { grid-template-columns: minmax(0, 1fr); } }
  .fin-table td.num, .fin-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .fin-table tr.total td { font-weight: 700; border-top: 2px solid var(--line); }
  .fin-table tr.group td { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 15px;
                           text-transform: uppercase; letter-spacing: .04em; color: var(--ink-soft);
                           background: #F4F6F8; }
  .fin-table td.neg { color: #9B2C2C; }
  .fin-facts { display: grid; grid-template-columns: auto 1fr; gap: 3px 14px; font-size: 14px; }
  .fin-facts .k { color: var(--ink-soft); }
  .price-box { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; }
  .price-box .q-field { width: 170px; }
  .fin-forecast { font-size: 14px; margin-top: 8px; }
  .fin-forecast b { font-family: 'Barlow Condensed', sans-serif; font-size: 16px; }
</style>
"""

LINE_TIPS = {
    "national": "Every team's equal share of the league's TV deals and national sponsors (about 62% of a real "
                "team's revenue). It grows with the salary cap.",
    "gate": "Regular seats: your price x tickets sold, every home game (preseason included, as in season-ticket "
            "packages). Playoff tickets go to the league.",
    "club": "Club seats (premium seats with their own lounge).",
    "suites": "Luxury suites, leased for the season.",
    "vts_in": "Your 1/32 share of the visiting teams' pool: part of every team's ticket money is shared league-wide.",
    "vts_out": "What your ticket sales put into the visiting teams' pool.",
    "sponsors": "Local sponsors and stadium naming rights: they follow your franchise's following, a new "
                "stadium and winning.",
    "concessions": "Food, drink and parking: your share, per fan in the seats.",
    "store": "The team store on game days.",
    "events": "Concerts, college games and other events at your stadium (new stadiums draw more).",
    "media": "Local radio and preseason TV (small in the NFL: the big TV money is national).",
    "playoffs": "Home playoff games: the league keeps the tickets; you keep concessions and parking.",
    "players": "Cash actually paid to players this season: salaries plus signing bonuses paid up front "
               "(different from the cap number, which spreads bonuses over the years).",
    "benefits": "Player pensions, health care and other benefits (about a quarter of the cap).",
    "staff": "Your coaches, scouts and trainers (the owner's staff budget), plus fired coaches still owed.",
    "operations": "Running the team and the stadium: game days, travel, the front office, marketing, rent.",
}


def _viewing(league):
    return league.user_team_id if state.team_id == FREE_AGENTS else state.team_id


def _m(k):
    return fmt.money(k) if k is not None else "-"


def _money_cell(k):
    if k is None:
        return '<td class="num">-</td>'
    return f'<td class="num{" neg" if k < 0 else ""}">{escape(_m(k))}</td>'


def _record(league, tid, s):
    r = next((x for x in league.team_history if x["team"] == tid and x["season"] == s), None)
    if not r:
        return ""
    return f'{r["w"]}-{r["l"]}' + (f'-{r["t"]}' if r["t"] else "")


def build_finances_tab(on_change=None):
    """Builds the Finances page (Team section). Returns a function that refreshes it."""
    league = state.league
    ui.add_head_html(CSS)
    form = {"general": None, "club": None, "tid": None, "season": None}

    def changed():
        mark_changed()
        refresh()
        if on_change:
            on_change()

    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def banner():
            tid = _viewing(league)
            if tid is None:
                ui.label("Pick your team first.").classes("legend")
                return
            team = league.team(tid)
            b = F.books(league, tid)
            a = F.attendance(league, tid)
            lines = b["lines"]
            when = "this season" if not b.get("closed") else str(league.season)
            pills = (f'<span class="stat-pill" title="Projected for the full season: what&#39;s been earned so far '
                     f'plus your staff&#39;s forecast for the home games left"><b>{_m(lines["revenue"])}</b> '
                     f'Revenue ({when})</span>'
                     f'<span class="stat-pill {"is-good" if lines["profit"] >= 0 else "is-warn"}" title="Revenue less '
                     f'expenses (before taxes, interest and stadium debt)"><b>{_m(lines["profit"])}</b> Profit</span>')
            if a["avg"]:
                pills += (f'<span class="stat-pill"><b>{fmt.crowd(a["avg"])}</b> Average crowd '
                          f'({fmt.share(a["fill"])} of seats)</span>')
            pills += (f'<span class="stat-pill" title="An estimate of what the team would sell for: about 11 times '
                      f'revenue, a bit more in a big market (how Forbes values NFL teams)">'
                      f'<b>{_m(F.franchise_value(league, tid))}</b> Team value</span>'
                      f'<span class="stat-pill" title="How much of a following the franchise has: its history and '
                      f'tradition, plus the last three seasons"><b>{escape(fmt.trait(F.fan_support(league, tid)))}</b> '
                      f'Fan support</span>')
            with ui.element("div").classes("page-toolbar"):
                with ui.element("div").classes("toolbar-group"):
                    ui.html(f'<span class="staff-banner"><span class="big">{escape(team.name)} business</span></span>',
                            sanitize=False)
                    ui.html(f'<div class="stat-pill-row">{pills}</div>', sanitize=False)
            if tid != league.user_team_id:
                ui.label("Another team's books: view only.").classes("legend")
        banner()

    with ui.element("div").classes("w-full px-8 py-3"):
        with ui.element("div").classes("fin-grid"):
            with ui.column().classes("gap-4").style("min-width:0"):
                @ui.refreshable
                def prices_view():
                    tid = _viewing(league)
                    if tid is None:
                        return
                    p = F.prices(league, tid) or {}
                    mine = tid == league.user_team_id
                    is_open = mine and F.prices_open(league)
                    rg, rc = F.recommended(league, tid) if mine else (None, None)
                    if form["tid"] != tid or form["season"] != league.season:
                        form.update({"general": p.get("general"), "club": p.get("club"), "tid": tid,
                                     "season": league.season})
                    with ui.element("div").classes("report px-5 py-4 w-full"):
                        ui.label(f"Ticket prices, {league.season}").classes("panel-heading").style("margin-top:0")
                        if mine:
                            ui.label("Set once a year, before the first game: a price for regular seats and one "
                                     "for club seats (suites are priced from the club seats). Too high and seats "
                                     "go empty; too low and you leave money on the table, though full stadiums "
                                     "help the crowd's mood.").classes("legend")
                        with ui.element("div").classes("price-box").style("margin-top:8px"):
                            gen = ui.number("Regular seat, a game ($)", value=form["general"], min=10, step=1, format="%.0f") \
                                .props("dense outlined")
                            clb = ui.number("Club seat, a game ($)", value=form["club"], min=10, step=5, format="%.0f") \
                                .props("dense outlined")
                            if not is_open:
                                gen.disable()
                                clb.disable()
                            if mine and is_open:
                                ui.button("Use recommended", icon="tips_and_updates",
                                          on_click=lambda: (gen.set_value(rg), clb.set_value(rc))) \
                                    .props("no-caps outline dense color=green-10") \
                                    .tooltip(f"Your staff's pick: {fmt.price(rg)} and {fmt.price(rc)}, just under "
                                             f"what they think sells out")
                                ui.button("Set prices", icon="check", on_click=lambda: save(gen.value, clb.value)) \
                                    .props("no-caps unelevated dense color=green-10")
                        forecast_box = ui.html("", sanitize=False).classes("fin-forecast")

                        def show_forecast():
                            g, c = gen.value or 0, clb.value or 0
                            form["general"], form["club"] = g, c
                            if not g or not c:
                                forecast_box.content = ""
                                return
                            f = F.forecast(league, tid, g, c)
                            suite = c * F.SUITE_SEATS * 10 * F.SUITE_MULT / 1000
                            txt = (f'Your staff expects <b>{fmt.crowd(f["attendance"])}</b> a game '
                                   f'({fmt.share(f["fill"])} of regular seats, {fmt.share(f["club_fill"])} of club '
                                   f'seats sold) and <b>{_m(f["gate_k"])}</b> in tickets a game. '
                                   f'A suite: {_m(suite)} for the season.')
                            fam = F.family_of_four(league, tid)
                            if fam and p.get("general"):
                                fam = fam - 4 * p["general"] + 4 * g
                                txt += (f'<br>A family of four (4 regular seats, parking, 4 hot dogs, 4 sodas, '
                                        f'2 beers, 2 caps): <b>{fmt.price(fam)}</b>.')
                            if mine and rg:
                                txt += (f'<br><span class="legend">Recommended: {fmt.price(rg)} regular, '
                                        f'{fmt.price(rc)} club. Forecasts are your staff&#39;s estimates; the real '
                                        f'demand moves with the season.</span>')
                            if not is_open:
                                txt += ('<br><span class="legend">Set for the season (prices can change before '
                                        'next season&#39;s first game).</span>')
                            forecast_box.content = txt
                        gen.on_value_change(lambda _e: show_forecast())
                        clb.on_value_change(lambda _e: show_forecast())
                        show_forecast()
                prices_view()

                @ui.refreshable
                def books_view():
                    tid = _viewing(league)
                    if tid is None:
                        return
                    b = F.books(league, tid)
                    hist = F.history(league, tid)
                    last = hist[0] if hist and hist[0]["season"] < league.season else None
                    so_far = b.get("so_far") or {}
                    closed = b.get("closed")
                    head_cells = ('<th>Line</th>'
                                  + ('' if closed else '<th class="num" title="Game-day money earned so far">So far</th>')
                                  + f'<th class="num" title="{"The season&#39;s books" if closed else "Full season: so far plus the forecast for the home games left"}">'
                                  + f'{league.season}{"" if closed else " (projected)"}</th>'
                                  + (f'<th class="num">{last["season"]}</th>' if last else ''))
                    rows = []
                    so_far_keys = {"gate": "gate", "club": "club", "concessions": "concessions", "playoffs": "playoffs"}
                    ncol = 2 + (0 if closed else 1) + (1 if last else 0)
                    for title, keys in (("Revenue", F.LINES_REVENUE), ("Expenses", F.LINES_EXPENSE)):
                        rows.append(f'<tr class="group"><td colspan="{ncol}">{title}</td></tr>')
                        for key, label in keys:
                            v = b["lines"].get(key)
                            if not v and not (last and last.get(key)):
                                continue
                            sf = so_far.get(so_far_keys.get(key)) if key in so_far_keys else None
                            rows.append(f'<tr><td title="{escape(LINE_TIPS.get(key, ""))}">{escape(label)}</td>'
                                        + ('' if closed else (_money_cell(sf) if sf else
                                                              '<td class="num">-</td>' if sf is not None else '<td></td>'))
                                        + _money_cell(v) + (_money_cell(last.get(key)) if last else '') + '</tr>')
                        tot = "revenue" if title == "Revenue" else "expenses"
                        rows.append(f'<tr class="total"><td>Total {title.lower()}</td>' + ('' if closed else '<td></td>')
                                    + _money_cell(b["lines"][tot]) + (_money_cell(last[tot]) if last else '') + '</tr>')
                    rows.append('<tr class="total"><td>Profit</td>' + ('' if closed else '<td></td>')
                                + _money_cell(b["lines"]["profit"]) + (_money_cell(last["profit"]) if last else '')
                                + '</tr>')
                    with ui.element("div").classes("report px-5 py-4 w-full"):
                        ui.label("Profit and loss").classes("panel-heading").style("margin-top:0")
                        if not closed and b.get("games_left"):
                            ui.label(f"{b['games_left']} home games left: their ticket and game-day money is your "
                                     f"staff's forecast at this season's prices. Hover a line for what it is.") \
                                .classes("legend")
                        ui.html(f'<table class="ledger-table fin-table"><thead><tr>{head_cells}</tr></thead>'
                                f'<tbody>{"".join(rows)}</tbody></table>', sanitize=False)
                books_view()

                @ui.refreshable
                def games_view():
                    tid = _viewing(league)
                    if tid is None:
                        return
                    games = F.home_games(league, tid)
                    with ui.element("div").classes("report px-5 py-4 w-full"):
                        ui.label(f"Home games, {league.season}").classes("panel-heading").style("margin-top:0")
                        if not games:
                            ui.label("No home games played yet this season.").classes("legend")
                            return
                        kinds = {"preseason": "Preseason", "regular": "Week", "playoffs": "Playoffs"}
                        rows = []
                        for r in games:
                            opp = league.team(r["away"])
                            when = (f'Week {r["week"]}' if r["kind"] == "regular" else kinds[r["kind"]])
                            rows.append(f'<tr><td>{escape(when)}</td><td>{popups.team_link(opp, opp.abbrev)}</td>'
                                        f'<td class="num">{fmt.crowd(r["att"])}</td>'
                                        f'<td class="num">{fmt.share(r["att"] / r["capacity"])}</td>'
                                        f'<td class="num">{fmt.price(r["price"]) if r["kind"] != "playoffs" else "-"}</td>'
                                        + _money_cell(r["gate"] + r["club_gate"]) + _money_cell(r["conc"]) + '</tr>')
                        ui.html('<table class="ledger-table fin-table"><thead><tr><th>Game</th><th>Opponent</th>'
                                '<th class="num">Crowd</th><th class="num" title="Of the stadium&#39;s capacity">'
                                'Seats sold</th><th class="num">Regular seat</th>'
                                '<th class="num" title="Regular and club seats (playoff tickets go to the league)">'
                                'Tickets</th><th class="num">Concessions, parking, store</th></tr></thead>'
                                f'<tbody>{"".join(rows)}</tbody></table>', sanitize=False)
                games_view()

            with ui.element("div").classes("report inspector px-6 py-5"):
                @ui.refreshable
                def side():
                    tid = _viewing(league)
                    if tid is None:
                        return
                    st = F.stadium(league, tid)
                    t = F.team(league, tid)
                    age = F.stadium_age(league, tid)
                    roof = {"dome": "Dome", "retractable": "Retractable roof", "outdoor": "Open air"}[st["roof"]]
                    ui.label("Stadium").classes("panel-heading").style("margin-top:0")
                    facts = [("Name", st["name"]), ("Opened", f'{st["opened"]} ({"new this year" if age == 0 else f"{age} years old"})'),
                             ("Capacity", fmt.crowd(st["capacity"])), ("Club seats", fmt.crowd(st["club"])),
                             ("Luxury suites", str(st["suites"])), ("Roof", roof)]
                    ui.html('<div class="fin-facts">' + "".join(f'<span class="k">{k}</span><span>{escape(v)}</span>'
                                                                 for k, v in facts) + '</div>', sanitize=False)
                    ui.label("A newer stadium earns more (premium seats, sponsors, prices); the edge fades over "
                             "about ten years. Building and renovating come in a later step.").classes("legend")
                    ui.label("Market").classes("panel-heading")
                    facts = [("Size", f'{F.market_word(t["market"])} ({t["market"]:.1f}M TV homes)'),
                             ("Local income", f'${t["income"]}K a household (median)'),
                             ("Fan support", fmt.trait(F.fan_support(league, tid)))]
                    ui.html('<div class="fin-facts">' + "".join(f'<span class="k">{k}</span><span>{escape(v)}</span>'
                                                                 for k, v in facts) + '</div>', sanitize=False)
                    ui.label("In the real NFL a team's own following matters far more than its city's size "
                             "(the Packers out-earn most big-market teams).").classes("legend")
                    if tid == league.user_team_id:
                        f, word = F.owner_money_factor(league, tid)
                        ui.label("Your owner").classes("panel-heading")
                        ui.label(word.capitalize() + "." if word else
                                 "Winning comes first; the money is where he expects it.").classes("legend") \
                            .tooltip("With 'Owner can fire you' on (Staff page), losing money or making much less "
                                     "than your market should raises the odds a little; strong profits lower them "
                                     "a little. Profits also slowly move his staff budget.")
                    hist = F.history(league, tid)
                    ui.label("Past seasons").classes("panel-heading")
                    if not hist:
                        ui.label("No finished seasons yet.").classes("legend")
                        return
                    rows = "".join(f'<tr><td>{h["season"]}</td><td>{_record(league, tid, h["season"])}</td>'
                                   f'<td class="num">{fmt.crowd(h.get("att_avg"))}</td>'
                                   f'<td class="num">{fmt.price(h["price"]) if h.get("price") else "-"}</td>'
                                   + _money_cell(h["revenue"]) + _money_cell(h["profit"]) + '</tr>'
                                   for h in hist[:10])
                    ui.html('<table class="ledger-table fin-table"><thead><tr><th>Season</th><th>Record</th>'
                            '<th class="num">Crowd</th><th class="num">Ticket</th><th class="num">Revenue</th>'
                            f'<th class="num">Profit</th></tr></thead><tbody>{rows}</tbody></table>', sanitize=False)
                side()

    def save(g, c):
        ok, msg = F.set_your_prices(league, g or 0, c or 0)
        ui.notify(msg, type="positive" if ok else "warning")
        if ok:
            changed()

    def refresh():
        banner.refresh()
        prices_view.refresh()
        books_view.refresh()
        games_view.refresh()
        side.refresh()

    return refresh


SORTS = {"Revenue": "revenue", "Profit": "profit", "Crowd": "att", "Ticket": "price", "Value": "value",
         "Fan support": "support", "Market": "market"}


def build_league_finances_tab():
    """Builds the League finances page (League section). Returns a function that refreshes it."""
    league = state.league
    ui.add_head_html(CSS)
    view = {"season": None, "sort": "Revenue"}

    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def toolbar():
            seasons = sorted(set(F.ensure(league)["books"]) | {league.season}, reverse=True)
            if view["season"] not in seasons:
                view["season"] = seasons[0]
            with ui.element("div").classes("page-toolbar"):
                with ui.element("div").classes("toolbar-group"):
                    ui.html('<span class="staff-banner"><span class="big">League finances</span></span>', sanitize=False)
                    ui.select({s: (f"{s} (projected)" if s == league.season and s not in F.ensure(league)["books"]
                                   else str(s)) for s in seasons},
                              value=view["season"], label="Season",
                              on_change=lambda e: (view.update(season=e.value), table_view.refresh())) \
                        .props("dense outlined").style("min-width:170px")
                    ui.select(list(SORTS), value=view["sort"], label="Sort by",
                              on_change=lambda e: (view.update(sort=e.value), table_view.refresh())) \
                        .props("dense outlined").style("min-width:150px")
        toolbar()

    with ui.element("div").classes("w-full px-8 py-3"):
        @ui.refreshable
        def table_view():
            rows = F.league_table(league, view["season"])
            key = SORTS[view["sort"]]
            rows.sort(key=lambda r: -(r[key] or 0))
            mine = league.user_team_id
            body = []
            for i, r in enumerate(rows, start=1):
                t = league.team(r["team"])
                style = ' style="background:#FFF6CF"' if r["team"] == mine else ""
                body.append(f'<tr{style}><td class="num">{i}</td><td>{popups.team_link(t, t.name)}</td>'
                            f'<td>{F.market_word(r["market"])}</td><td class="num">{r["stadium_age"]}</td>'
                            f'<td class="num">{fmt.crowd(r["capacity"])}</td><td class="num">{fmt.crowd(r["att"])}</td>'
                            f'<td class="num">{fmt.share(r["fill"])}</td>'
                            f'<td class="num">{fmt.price(r["price"]) if r["price"] else "-"}</td>'
                            + _money_cell(r["revenue"]) + _money_cell(r["local"]) + _money_cell(r["profit"])
                            + _money_cell(r["value"])
                            + f'<td>{escape(fmt.trait(r["support"]))}</td></tr>')
            with ui.element("div").classes("report px-5 py-4 w-full"):
                closed = rows and rows[0]["closed"]
                ui.label("Every team's books" + ("" if closed else ": this season so far plus the forecast for "
                                                 "the home games left")).classes("legend")
                ui.html('<table class="ledger-table fin-table"><thead><tr><th class="num">#</th><th>Team</th>'
                        '<th>Market</th><th class="num" title="Years since the stadium opened (or was rebuilt)">'
                        'Stadium age</th><th class="num">Capacity</th><th class="num">Average crowd</th>'
                        '<th class="num">Seats sold</th><th class="num">Regular seat</th><th class="num">Revenue</th>'
                        '<th class="num" title="Revenue other than the national share every team gets">'
                        'Local revenue</th><th class="num">Profit</th><th class="num" title="Estimated sale value">'
                        'Team value</th><th>Fan support</th></tr></thead>'
                        f'<tbody>{"".join(body)}</tbody></table>', sanitize=False)
                ui.label("Revenue: national TV money (the same for every team) plus tickets, suites, sponsors, "
                         "concessions and local media. Profit: before taxes, interest and stadium debt. Team value: "
                         "an estimate, about 11 times revenue.").classes("legend")
        table_view()

    def refresh():
        toolbar.refresh()
        table_view.refresh()

    return refresh
