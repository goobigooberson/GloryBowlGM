# contracts_page.py
# The Contracts tab (Oct 23; Blake: you run your own contracts, the offseason in phases
# with a Next button, offer / counter / patience, rough interest from other teams only):
#   Payroll      every contract on your team: cap hits this season and next, guarantees,
#                what cutting him would cost; your cap room (any time). Click a player to
#                offer an extension, restructure his deal or cut him (June 1 choice), each
#                with the cap effect shown before you confirm
#   Re-sign      the start of the league year: your expiring players with your staff's
#                advice and what each asks; negotiate, tag or tender them; your
#                first-rounders' fifth-year options (until the draft)
#   Free agency  the free-agent board during the offseason waves: what each asks, how much
#                other teams are interested, your offers (he decides when the wave plays out)
# Screens read the engine only (free_agency.py, contracts.py, league_money.py).

from datetime import date
from html import escape

from nicegui import ui

from engine import contracts as C
from engine import free_agency as FA
from engine import league_money as LM
from engine import season
from engine.scale import shown
from engine.teams import ROSTER_TEMPLATE
from . import popups, theme
from .state import state, mark_changed

POSITION_ORDER = list(ROSTER_TEMPLATE)
VIEWS = ["Payroll", "Re-sign", "Free agency"]


def _m(k):
    return C.fmt_money(k)


def _cap_line(league, tid):
    cap = C.team_cap(league, tid)
    top51 = C.top51_in_force(league)
    nxt = C.commitments(league, tid, league.season + 1)
    nxt_cap = C.cap_for(league, league.season + 1)
    offers = league.fa.get("user_offers", {}) if season.in_offseason(league) else {}
    tied = sum(o["apy"] for o in offers.values())
    return (f'{league.season} salary cap <b>{_m(cap["cap"])}</b> &nbsp;·&nbsp; used <b>{_m(cap["used"])}</b>'
            + (" (top 51 contracts, the offseason rule)" if top51 else "")
            + f' &nbsp;·&nbsp; room <b>{_m(cap["room"])}</b>'
            + (f' &nbsp;·&nbsp; standing offers {_m(tied)}' if tied else "")
            + f' &nbsp;·&nbsp; dead money {_m(cap["dead"])}'
            + f' &nbsp;·&nbsp; {league.season + 1}: {_m(nxt)} committed of a projected {_m(nxt_cap)}'
            + _league_money_line(league))


def _league_money_line(league):
    """Where the cap is headed: next year's projection and the TV and labor deals."""
    o = LM.outlook(league)
    ch = o["next_change"]
    bits = [f'{o["next_season"]} cap projected {_m(o["next_cap"])} ({"+" if ch >= 0 else ""}{ch * 100:.1f}%'
            + (", revenue fell" if o["shock"] else "") + ")"]
    if o["next_deal"]:
        bits.append(f'new TV deals signed for {o["next_deal"][0]}-{o["next_deal"][1]}')
    elif o["deal_end"]:
        bits.append(f'TV deals run through {o["deal_end"]}')
    if o["labor_end"]:
        bits.append(f'labor deal through {o["labor_end"]}')
    return '<br><span style="opacity:.75">League money: ' + " &nbsp;·&nbsp; ".join(bits) + "</span>"


def advice_text(r):
    """Your staff's advice on an expiring player, in words."""
    a, why = r["advice"], r["why"]
    if a == "Let go":
        return (f"Let go: he asks more than he's worth to you, though he's {why}" if why
                else "Let go: you can do better for the money")
    if a == "Tag":
        return f"Tag him: a long deal costs too much, but you need him ({why})" if why else "Tag him"
    if a == "Tender":
        return "Tender him (a cheap one-year deal; he can't leave)"
    return f"Re-sign ({why})" if why else "Re-sign: worth what he's asking"


def option_advice(r):
    """Your staff's advice on a fifth-year option, in words."""
    if r["advice"] == "Exercise":
        return f"Exercise it: he's worth about {_m(r['worth'])} a year to the market, more than the option costs"
    return f"Decline it: the option ({_m(r['salary'])}) costs more than he's worth (about {_m(r['worth'])})"


def _age(league, p):
    return p.age(date(league.season, 9, 1))


def payroll_rows(league, tid):
    from engine import transactions as TR
    rows = []
    for pid in C.players_with_team(league, tid):
        c = league.contracts.get(pid)
        if c is None or c["team"] != tid:
            continue
        p = league.player(pid)
        _t, where = TR.team_of(league, pid)
        prev = C.release_preview(league, pid)
        dead = sum(prev["dead"].values())
        rows.append({
            "id": pid, "pos": p.position, "pos_style": theme.position_style(p.position),
            "pos_sort": POSITION_ORDER.index(p.position) * 1000 - shown(p.overall(), p.position),
            "name": p.name + {"practice": " (practice squad)", "reserve": " (reserve list)"}.get(where, ""),
            "age": _age(league, p),
            "ovr": shown(p.overall(), p.position),
            "kind": {"practice": "Practice squad", "futures": "Reserve/future", "tag": "Franchise tag",
                     "tender": "Tender", "rookie": "Rookie", "udfa": "Undrafted rookie", "minimum": "Minimum",
                     "extension": "Extension", "veteran": "Veteran"}.get(c["kind"], c["kind"].title()),
            "through": C.last_season(c), "left": C.years_left(c, league.season),
            "apy": c["apy"], "apy_t": _m(c["apy"]),
            "hit": C.cap_hit(league, c), "hit_t": _m(C.cap_hit(league, c)),
            "next": C.cap_hit(league, c, league.season + 1), "next_t": _m(C.cap_hit(league, c, league.season + 1)),
            "dead": dead, "dead_t": _m(dead), "save": prev["savings"], "save_t": _m(prev["savings"]),
        })
    return rows


PAY_COLS = [
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "right"},
    {"name": "kind", "label": "Deal", "field": "kind", "sortable": True, "align": "left"},
    {"name": "through", "label": "Through", "field": "through", "sortable": True, "align": "right"},
    {"name": "apy", "label": "Per year", "field": "apy", "sortable": True, "align": "right"},
    {"name": "hit", "label": "Cap hit now", "field": "hit", "sortable": True, "align": "right"},
    {"name": "next", "label": "Next year", "field": "next", "sortable": True, "align": "right"},
    {"name": "dead", "label": "Dead if cut", "field": "dead", "sortable": True, "align": "right"},
    {"name": "save", "label": "Saves if cut", "field": "save", "sortable": True, "align": "right"},
]
RESIGN_COLS = [
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "right"},
    {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
    {"name": "ask", "label": "Asking (per year)", "field": "ask", "sortable": True, "align": "right"},
    {"name": "years", "label": "Years", "field": "years", "sortable": True, "align": "right"},
    {"name": "advice", "label": "Staff advice", "field": "advice", "sortable": True, "align": "left"},
]
FA_COLS = [
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "exp", "label": "Exp", "field": "exp", "sortable": True, "align": "right"},
    {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "right"},
    {"name": "pot", "label": "Potential", "field": "pot", "sortable": True, "align": "right"},
    {"name": "ask", "label": "Asking (per year)", "field": "ask", "sortable": True, "align": "right"},
    {"name": "years", "label": "Years", "field": "years", "sortable": True, "align": "right"},
    {"name": "interest", "label": "Other teams", "field": "interest", "sortable": True, "align": "left"},
    {"name": "offer", "label": "Your offer", "field": "offer", "sortable": True, "align": "left"},
]
MONEY_SLOTS = {"apy": "apy_t", "hit": "hit_t", "next": "next_t", "dead": "dead_t", "save": "save_t", "ask": "ask_t"}


def build_contracts_tab(on_change=None):
    """Builds the Contracts tab. Returns a function that refreshes it."""
    league = state.league
    view = {"v": "Payroll", "pid": None, "pos": "All positions"}

    def default_view():
        ph = season.offseason_phase(league)
        if ph and ph[0] == "resign":
            return "Re-sign"
        if ph and ph[0] == "fa":
            return "Free agency"
        return "Payroll"
    view["v"] = default_view()

    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def header():
            tid = league.user_team_id
            if tid is None:
                ui.label("Pick your team first.").classes("legend")
                return
            ui.html(f'<div class="legend">{_cap_line(league, tid)}</div>', sanitize=False)
            ph = season.offseason_phase(league)
            if ph:
                ui.html(f'<div class="notice" style="margin-top:6px"><b>{escape(ph[1])}.</b> {escape(ph[2])} '
                        f'Press <b>Next</b> in the bar above when you\'re done.</div>', sanitize=False)
            opts = FA.options_for_you(league)
            if opts:
                names = ", ".join(f"{league.player(r['pid']).position} {escape(league.player(r['pid']).name)}"
                                  for r in opts)
                ui.html(f'<div class="notice" style="margin-top:6px"><b>Fifth-year option to decide:</b> {names} '
                        f'(Re-sign view). The deadline is the draft: an option you haven\'t exercised by then '
                        f'is declined.</div>', sanitize=False)
        header()

    with ui.row().classes("w-full px-8 pt-3 items-center gap-4"):
        toggle = ui.toggle(VIEWS, value=view["v"], on_change=lambda e: set_view(e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9") \
            .tooltip("Payroll: every contract on your team. Re-sign: your expiring players, at the start of "
                     "the league year. Free agency: the free-agent board during the offseason's waves.")
        pos_select = ui.select(["All positions"] + POSITION_ORDER, value="All positions",
                               on_change=lambda e: set_pos(e.value)) \
            .props("dense outlined options-dense").classes("w-44")
        ui.label("Click a player for his details and your options.").classes("legend")

    with ui.row().classes("w-full px-8 py-4 gap-5 no-wrap items-start"):
        table = ui.table(rows=[], columns=PAY_COLS, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": "pos"}) \
            .props("flat dense virtual-scroll hide-bottom") \
            .classes("roster-table").style("flex: 1 1 0; min-width: 0; height: calc(100vh - 330px)")
        table.add_slot("body-cell-pos", r"""
            <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
        # The name opens his card (popups.py); the rest of the row opens the contract panel.
        table.add_slot("body-cell-name", r"""
            <q-td :props="props"><a class="plink pname" :href="'/player/' + props.row.id">{{ props.row.name }}</a></q-td>""")
        for key, txt in MONEY_SLOTS.items():
            table.add_slot(f"body-cell-{key}", f"""
                <q-td :props="props" class="num">{{{{ props.row.{txt} }}}}</q-td>""")
        table.on("rowClick", lambda e: select(e.args[1]["id"]))

        with ui.element("div").classes("report px-6 py-5") \
                .style("flex: 0 0 440px; height: calc(100vh - 330px); overflow-y: auto"):
            @ui.refreshable
            def panel():
                pid = view["pid"]
                if pid is None:
                    ui.label("No player selected").classes("condensed text-2xl")
                    ui.label({"Payroll": "Click a contract to see it year by year, and to extend, restructure or "
                                         "release him (the cap effect is shown before anything happens).",
                              "Re-sign": "Click one of your expiring players to negotiate, tag or tender him, or "
                                         "a first-rounder to decide his fifth-year option.",
                              "Free agency": "Click a free agent to see what he's asking and make an offer."}
                             [view["v"]]).classes("legend")
                    if view["v"] == "Free agency":
                        offers_box()
                    return
                p = league.player(pid)
                ui.button("Open player card", icon="badge", on_click=lambda: popups.show_player(pid)) \
                    .props("no-caps outline color=green-10 dense").classes("mb-2")
                ui.html(f'<span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span>'
                        f'<h2 style="margin-top:6px">{escape(p.name)}</h2>'
                        f'<div class="legend">Age {_age(league, p)} · {p.experience} season'
                        f'{"s" if p.experience != 1 else ""} · Overall {shown(p.overall(), p.position)} · '
                        f'potential {shown(p.overall("potential"), p.position)}</div>', sanitize=False)
                if view["v"] == "Payroll":
                    contract_panel(pid)
                elif view["v"] == "Re-sign":
                    opt = {r["pid"]: r for r in FA.options_for_you(league)}.get(pid)
                    if opt:
                        option_panel(pid, opt)
                    else:
                        resign_panel(pid)
                else:
                    fa_panel(pid)
            panel()

    # ---- Confirming a money move (one dialog, the effect spelled out) --------
    with ui.dialog() as confirm_dialog, ui.card().classes("p-6").style("min-width:480px; max-width:560px"):
        confirm_html = ui.html("", sanitize=False)
        with ui.row().classes("justify-end w-full mt-3 gap-2"):
            ui.button("Go back", on_click=confirm_dialog.close).props("flat no-caps")
            confirm_btn = ui.button("Confirm").props("no-caps color=green-10")
    pending_action = {"fn": None}

    def ask_confirm(title, body_html, button_label, fn):
        confirm_html.content = f'<div class="condensed text-2xl">{escape(title)}</div>{body_html}'
        confirm_btn.text = button_label
        pending_action["fn"] = fn
        confirm_dialog.open()

    def do_confirmed():
        confirm_dialog.close()
        fn, pending_action["fn"] = pending_action["fn"], None
        if fn:
            fn()
    confirm_btn.on_click(do_confirmed)

    def _dead_text(dead):
        return ", ".join(f"{s}: {_m(v)}" for s, v in sorted(dead.items())) or "none"

    # ---- Panels -----------------------------------------------------------
    def contract_panel(pid):
        c = league.contracts.get(pid)
        if c is None:
            ui.label("No contract.").classes("legend")
            return
        rows = "".join(
            f'<tr><td class="l">{y["season"]}</td><td>{_m(y["base"])}</td><td>{_m(y["bonus"])}</td>'
            f'<td>{_m(C.cap_hit(league, c, y["season"]))}</td><td>{_m(y["gtd"])}</td></tr>'
            for y in c["years"] if y["season"] >= league.season)
        opt = c.get("option") or {}
        opt_line = ""
        if opt.get("exercised") is True:
            opt_line = f' Fifth-year option exercised ({opt["season"]}).'
        elif opt.get("exercised") is False:
            opt_line = " Fifth-year option declined."
        elif opt:
            opt_line = f' Fifth-year option for {opt["season"]} not decided yet.'
        ui.html(f'<h3>Contract</h3><div class="legend">{escape(c["kind"].title())} deal signed in {c.get("signed", "?")}: '
                f'{len(c["years"])} years, {_m(c["value"])} in all, {_m(c["guaranteed"])} guaranteed.'
                f'{" Restructured." if c.get("restructured") else ""}{opt_line}</div>'
                f'<table class="box-table" style="margin-top:6px"><thead><tr><th class="l">Season</th><th>Base</th>'
                f'<th>Bonus</th><th>Cap hit</th><th>Guaranteed</th></tr></thead><tbody>{rows}</tbody></table>',
                sanitize=False)
        if c["team"] != league.user_team_id:
            return
        from engine import cap_market
        table = cap_market.market_table(league)
        extension_section(pid, c, table)
        restructure_section(pid, c)
        release_section(pid, c)

    def extension_section(pid, c, table):
        ui.html('<h3>Extension</h3>', sanitize=False)
        ok, why = FA.extension_check(league, pid, table)
        if not ok:
            ui.label(why).classes("legend")
            return
        ask = FA.extension_ask(league, pid, table)
        S = league.season
        ui.html(f'<div class="facts"><span class="k">He\'s asking</span><span>{_m(ask["apy"])} a year</span>'
                f'<span class="k">New years</span><span>{ask["years"]} (from {S + 1}, through {S + ask["years"]})</span>'
                f'<span class="k">Guaranteed</span><span>{_m(ask["guaranteed"])}</span></div>'
                f'<div class="legend" style="margin-top:6px">This season\'s salary stays as it is; the new years '
                f'start in {S + 1}' + (f' and replace what\'s left of his current deal' if ask["min_years"] > 1 else '')
                + '. The new signing bonus is spread from this season on (at most 5 seasons), so part of it counts '
                  'on your cap now. Close offers get a counter; three low offers and he stops talking until next '
                  'league year.</div>', sanitize=False)

        def offer(apy, years, gtd):
            if years < ask["min_years"]:
                ui.notify(f"An extension has to run at least {ask['min_years']} seasons from {S + 1}.",
                          type="warning", position="top")
                return
            prev = FA.extension_preview(league, pid, apy, years, gtd)
            new = prev["contract"]
            yrs = "".join(f'<tr><td class="l">{y["season"]}</td><td>{_m(y["base"])}</td><td>{_m(y["bonus"])}</td>'
                          f'<td>{_m(C.cap_hit(league, new, y["season"]))}</td></tr>' for y in new["years"])
            body = (f'<div class="legend">{years} new year{"s" if years != 1 else ""} at {_m(apy)} a year, '
                    f'{_m(gtd)} guaranteed: signed through {prev["through"]}.</div>'
                    f'<div class="facts" style="margin-top:6px"><span class="k">Cap hit this season</span>'
                    f'<span>{_m(prev["hit_before"])} now, {_m(prev["hit_now"])} after</span>'
                    f'<span class="k">Your cap room after</span>'
                    f'<span>{_m(C.cap_room(league, league.user_team_id) - (prev["hit_now"] - prev["hit_before"]))}</span></div>'
                    f'<table class="box-table" style="margin-top:6px"><thead><tr><th class="l">Season</th><th>Base</th>'
                    f'<th>Bonus</th><th>Cap hit</th></tr></thead><tbody>{yrs}</tbody></table>'
                    f'<div class="legend" style="margin-top:6px">If he says yes, it\'s signed.</div>')

            def go():
                result, msg = FA.extension_offer(league, pid, apy, years, gtd)
                ui.notify(msg, type="positive" if result == "accept" else ("warning" if result == "counter" else "negative"),
                          position="top", multi_line=True)
                if result == "accept":
                    changed()
                elif result == "reject":
                    panel.refresh()           # (his patience may be gone)
            ask_confirm(f"Offer {league.player(pid).name} an extension?", body, "Make offer", go)
        money_form(ask, offer, "Offer extension...", min_years=ask["min_years"],
                   years_label=f"New years (from {S + 1})")

    def restructure_section(pid, c):
        ui.html('<h3>Restructure</h3>', sanitize=False)
        ok, why = FA.restructure_check(league, pid)
        if not ok:
            ui.label(why).classes("legend")
            return
        first = C.restructure_preview(league, pid)
        amt = ui.number("Salary to turn into bonus ($ millions)", value=round(first["max"] / 1000, 2), step=0.1,
                        min=0, max=round(first["max"] / 1000, 2), format="%.2f") \
            .props("dense outlined").classes("w-full mt-1")
        effect = ui.html("", sanitize=False)

        def preview():
            k = int(round((amt.value or 0) * 1000))
            return C.restructure_preview(league, pid, k)

        def effect_html(pr):
            later = "".join(f'<tr><td class="l">{s}</td><td>{_m(pr["hits"][s][0])}</td><td>{_m(pr["hits"][s][1])}</td></tr>'
                            for s in sorted(pr["hits"]))
            return (f'<div class="facts" style="margin-top:6px"><span class="k">Cap room this season</span>'
                    f'<span>+{_m(pr["savings"])}</span>'
                    f'<span class="k">Dead money if cut after</span><span>{_m(pr["dead_after"])} '
                    f'(now {_m(pr["dead_before"])})</span></div>'
                    f'<table class="box-table" style="margin-top:6px"><thead><tr><th class="l">Season</th>'
                    f'<th>Cap hit now</th><th>After</th></tr></thead><tbody>{later}</tbody></table>')

        def show():
            effect.content = effect_html(preview())
        amt.on_value_change(lambda _e: show())
        show()
        ui.label(f"Up to {_m(first['max'])}: his salary this season above the minimum"
                 + (" still to be paid" if C.pay_week(league) else "")
                 + ". The money is guaranteed once it's a bonus; it comes back as cap hits in later years.") \
            .classes("legend mt-1")

        def ask_it():
            pr = preview()
            if pr["amount"] <= 0:
                ui.notify("Pick an amount to restructure.", type="warning", position="top")
                return

            def go():
                done, msg = FA.your_restructure(league, pid, pr["amount"])
                ui.notify(msg, type="positive" if done else "negative", position="top", multi_line=True)
                if done:
                    changed()
            ask_confirm(f"Restructure {league.player(pid).name}'s contract?",
                        f'<div class="legend">{_m(pr["amount"])} of his {league.season} salary becomes a signing '
                        f'bonus spread over {len(pr["added"]) + 1} seasons.</div>{effect_html(pr)}',
                        "Restructure", go)
        ui.button("Restructure...", on_click=ask_it).props("no-caps outline color=green-10 dense").classes("mt-2")

    def release_section(pid, c):
        ui.html('<h3>Release</h3>', sanitize=False)
        ch = FA.release_choices(league, pid)
        plain, june = ch["plain"], ch["june1"]
        rows = (f'<span class="k">Release now</span><span>dead money {_dead_text(plain["dead"])}; '
                f'saves {_m(plain["savings"])} this season</span>')
        if june:
            rows += (f'<span class="k">As a post-June 1 cut</span><span>dead money {_dead_text(june["dead"])}; '
                     f'saves {_m(june["savings"])} this season</span>')
        note = ""
        if ch["after_june1"]:
            note = "It's after June 1: a cut's bonus money for later years counts next season."
        elif june:
            note = (f"A post-June 1 designation pushes his later bonus money to next season ({ch['june1_left']} "
                    f"left this spring)." + (" Your staff suggests it." if ch["best_june1"] else ""))
        elif ch["june1_left"] and season.in_offseason(league):
            note = "A post-June 1 designation wouldn't change anything for him (no bonus money in later years)."
        ui.html(f'<div class="facts">{rows}</div>'
                + (f'<div class="legend" style="margin-top:6px">{escape(note)}</div>' if note else ''), sanitize=False)
        if ch["blocked"]:
            ui.label(ch["blocked"]).classes("legend mt-1")
            return
        p = league.player(pid)
        waived = p.experience < 4 and c["kind"] != "practice"

        def ask_it(j1):
            pr = june if j1 else plain

            def go():
                done, msg = FA.your_release(league, pid, june1=j1)
                ui.notify(msg, type="positive" if done else "negative", position="top", multi_line=True)
                if done:
                    view["pid"] = None
                    changed()
            ask_confirm(f"Release {p.name}?" if not j1 else f"Release {p.name} as a post-June 1 cut?",
                        f'<div class="facts" style="margin-top:6px"><span class="k">Dead money</span>'
                        f'<span>{_dead_text(pr["dead"])}</span><span class="k">Cap room this season</span>'
                        f'<span>+{_m(pr["savings"])}</span><span class="k">Your room after</span>'
                        f'<span>{_m(C.cap_room(league, league.user_team_id) + pr["savings"])}</span></div>'
                        f'<div class="legend" style="margin-top:6px">'
                        + ("He's waived: other teams can claim him (and take over his salary)."
                           if waived else "He becomes a free agent.") + '</div>',
                        "Release", go)
        with ui.row().classes("gap-2 mt-2"):
            ui.button("Release...", on_click=lambda: ask_it(False)).props("no-caps outline color=red-9 dense")
            if june:
                ui.button("Release as post-June 1...", on_click=lambda: ask_it(True)) \
                    .props("no-caps outline color=red-9 dense")

    def option_panel(pid, r):
        p = league.player(pid)
        ui.html(f'<h3>Fifth-year option</h3><div class="facts">'
                f'<span class="k">Option year</span><span>{r["season"]}</span>'
                f'<span class="k">Salary</span><span>{_m(r["salary"])}, fully guaranteed</span>'
                f'<span class="k">Level</span><span>{"Playing time: he starts (average of the 3rd-20th biggest cap numbers at his position)" if r["starter"] else "Basic (average of the 3rd-25th biggest cap numbers at his position)"}</span>'
                f'<span class="k">Your staff</span><span>{escape(option_advice(r))}</span></div>'
                f'<div class="legend" style="margin-top:6px">Exercise it and he\'s signed through {r["season"]} '
                f'at that salary (it counts on next season\'s cap). Decline it and he plays out his rookie deal '
                f'this season, then can become a free agent (you can still extend him before then). The '
                f'deadline is the draft: an option you haven\'t exercised by then is declined.</div>',
                sanitize=False)

        def decide(ex):
            done, msg = FA.decide_option(league, pid, ex)
            ui.notify(msg, type="positive" if done else "negative", position="top", multi_line=True)
            if done:
                changed()
        with ui.row().classes("gap-2 mt-3"):
            ui.button(f"Exercise: {_m(r['salary'])} for {r['season']}",
                      on_click=lambda: ask_confirm(f"Exercise {p.name}'s fifth-year option?",
                                                   f'<div class="legend">{_m(r["salary"])} in {r["season"]}, fully '
                                                   f'guaranteed. Your {r["season"]} commitments go up by that much.</div>',
                                                   "Exercise", lambda: decide(True))) \
                .props("no-caps unelevated color=green-10 dense")
            ui.button("Decline", on_click=lambda: ask_confirm(f"Decline {p.name}'s fifth-year option?",
                                                              '<div class="legend">He can become a free agent after '
                                                              'this season.</div>', "Decline", lambda: decide(False))) \
                .props("no-caps outline color=red-9 dense")

    def money_form(ask, on_submit, submit_label, min_years=1, years_label="Years"):
        apy = ui.number("Per year ($ millions)", value=round(ask["apy"] / 1000, 2), step=0.05, min=0.5,
                        format="%.2f").props("dense outlined").classes("w-full mt-2")
        years = ui.number(years_label, value=ask["years"], step=1, min=min_years, max=max(5, min_years), format="%d") \
            .props("dense outlined").classes("w-full mt-1")
        gtd = ui.number("Guaranteed in all ($ millions)", value=round(ask["guaranteed"] / 1000, 2), step=0.1,
                        min=0, format="%.2f").props("dense outlined").classes("w-full mt-1")
        ui.button(submit_label, on_click=lambda: on_submit(int(round((apy.value or 0) * 1000)),
                                                           int(years.value or 1),
                                                           int(round((gtd.value or 0) * 1000)))) \
            .props("no-caps unelevated color=green-10").classes("mt-2")

    def resign_panel(pid):
        rows = {r["pid"]: r for r in FA.expiring_for_you(league)}
        r = rows.get(pid)
        if r is None:
            ui.label("He's no longer one of your expiring players.").classes("legend")
            return
        ask = r["ask"]
        ui.html(f'<h3>He\'s asking</h3><div class="facts">'
                f'<span class="k">Per year</span><span>{_m(ask["apy"])}</span>'
                f'<span class="k">Years</span><span>{ask["years"]}</span>'
                f'<span class="k">Guaranteed</span><span>{_m(ask["guaranteed"])}</span>'
                f'<span class="k">Status</span><span>{ {"UFA": "Unrestricted free agent", "RFA": "Restricted free agent", "ERFA": "Exclusive-rights free agent"}.get(r["status"], r["status"])}</span>'
                f'<span class="k">Your staff</span><span>{escape(advice_text(r))}</span></div>'
                f'<div class="legend" style="margin-top:6px">Close offers get a counter; offers well short wear '
                f'his patience (three and he stops talking until the market opens). Guaranteed money counts '
                f'extra; older players value more years.</div>', sanitize=False)

        def offer(apy, years, gtd):
            result, msg = FA.resign_offer(league, pid, apy, years, gtd)
            ui.notify(msg, type="positive" if result == "accept" else ("warning" if result == "counter" else "negative"),
                      position="top")
            if result == "accept":
                changed()
        money_form(ask, offer, "Make offer")
        if r["tag"]:
            ui.button(f"Franchise tag: {_m(r['tag'])} for one year", on_click=lambda: tag("tag")) \
                .props("no-caps outline color=green-10 dense").classes("mt-3") \
                .tooltip("One year, fully guaranteed. One tag a team a year.")
        for lvl, amt in r["tenders"].items():
            name = {"erfa": "Exclusive-rights tender", "rofr": "Right-of-first-refusal tender",
                    "second": "Second-round tender", "first": "First-round tender"}[lvl]
            ui.button(f"{name}: {_m(amt)}", on_click=lambda lvl=lvl: tag(lvl)) \
                .props("no-caps outline color=green-10 dense").classes("mt-2")
        ui.label("Anyone you haven't signed becomes a free agent when you press Next.").classes("legend mt-3")

        def tag(kind):
            done, msg = FA.tag_or_tender(league, pid, kind)
            ui.notify(msg, type="positive" if done else "warning", position="top")
            if done:
                changed()

    def fa_panel(pid):
        if not season.in_offseason(league) or season.offseason_phase(league)[0] not in ("fa", "draft"):
            ui.label("Free agency offers are made during the offseason's free agency waves. During the season, "
                     "sign free agents from the Roster tab (pick Free agents in the team list).").classes("legend")
            return
        wave = league.fa.get("wave")
        ask = FA.asking_terms(league, pid, league.user_team_id, wave)
        mine = league.fa.get("user_offers", {}).get(pid)
        inter = FA.interest(league, [pid]).get(pid, "")
        ui.html(f'<h3>He\'s asking (this wave)</h3><div class="facts">'
                f'<span class="k">Per year</span><span>{_m(ask["apy"])}</span>'
                f'<span class="k">Years</span><span>{ask["years"]}</span>'
                f'<span class="k">Guaranteed</span><span>{_m(ask["guaranteed"])}</span>'
                f'<span class="k">Other teams</span><span>{inter} interested</span></div>'
                f'<div class="legend" style="margin-top:6px">Asking prices drop in later waves, but other teams '
                f'may sign him first. He picks the offer he likes best when the wave plays out: money first, then '
                f'a winner, loyalty and playing time.</div>', sanitize=False)
        if mine:
            ui.html(f'<div class="notice" style="margin-top:8px">Your offer: {_m(mine["apy"])} a year, '
                    f'{mine["years"]} year{"s" if mine["years"] != 1 else ""}, {_m(mine["guaranteed"])} '
                    f'guaranteed.</div>', sanitize=False)
            ui.button("Withdraw offer", on_click=lambda: (FA.withdraw_offer(league, pid), changed())) \
                .props("no-caps outline color=red-9 dense").classes("mt-2")

        def offer(apy, years, gtd):
            result, msg = FA.place_offer(league, pid, apy, years, gtd)
            ui.notify(msg, type="positive" if result == "accept" else ("warning" if result == "counter" else "negative"),
                      position="top")
            if result == "accept":
                changed()
        money_form(ask, offer, "Make offer" if not mine else "Change offer")

    def offers_box():
        offers = league.fa.get("user_offers", {})
        if not offers:
            return
        lines = "".join(f'<li>{escape(league.player(pid).position)} {escape(league.player(pid).name)}: '
                        f'{_m(o["apy"])} x {o["years"]}</li>' for pid, o in offers.items())
        ui.html(f'<h3>Your offers this wave</h3><ul style="margin:4px 0 0 18px">{lines}</ul>', sanitize=False)

    # ---- Data ---------------------------------------------------------------
    def rows_for():
        tid = league.user_team_id
        if tid is None:
            return [], PAY_COLS
        if view["v"] == "Payroll":
            return payroll_rows(league, tid), PAY_COLS
        if view["v"] == "Re-sign":
            out = []
            for r in FA.expiring_for_you(league):
                p = league.player(r["pid"])
                out.append({"id": p.id, "pos": p.position, "pos_style": theme.position_style(p.position),
                            "pos_sort": POSITION_ORDER.index(p.position) * 1000 - shown(p.overall(), p.position),
                            "name": p.name, "age": _age(league, p), "ovr": shown(p.overall(), p.position),
                            "status": r["status"], "ask": r["ask"]["apy"], "ask_t": _m(r["ask"]["apy"]),
                            "years": r["ask"]["years"], "advice": advice_text(r)})
            for r in FA.options_for_you(league):
                p = league.player(r["pid"])
                out.append({"id": p.id, "pos": p.position, "pos_style": theme.position_style(p.position),
                            "pos_sort": POSITION_ORDER.index(p.position) * 1000 - shown(p.overall(), p.position),
                            "name": p.name, "age": _age(league, p), "ovr": shown(p.overall(), p.position),
                            "status": f"Fifth-year option ({r['season']})", "ask": r["salary"],
                            "ask_t": _m(r["salary"]), "years": 1, "advice": option_advice(r)})
            return out, RESIGN_COLS
        # Free agency board: the best 250 by overall (all if a position is picked).
        if not season.in_offseason(league):
            return [], FA_COLS
        wave = league.fa.get("wave")
        fas = FA.free_agent_list(league)
        if view["pos"] != "All positions":
            fas = [p for p in fas if p.position == view["pos"]]
        fas = sorted(fas, key=lambda p: -shown(p.overall(), p.position))[:250]
        from engine import cap_market
        table = cap_market.market_table(league)        # once (slow to build), not once per player
        inter = FA.interest(league, [p.id for p in fas], wave, table=table)
        offers = league.fa.get("user_offers", {})
        out = []
        for p in fas:
            ask = FA.asking_terms(league, p.id, tid, wave, table=table)
            o = offers.get(p.id)
            out.append({"id": p.id, "pos": p.position, "pos_style": theme.position_style(p.position),
                        "pos_sort": POSITION_ORDER.index(p.position) * 1000 - shown(p.overall(), p.position),
                        "name": p.name, "age": _age(league, p), "exp": p.experience,
                        "ovr": shown(p.overall(), p.position), "pot": shown(p.overall("potential"), p.position),
                        "ask": ask["apy"], "ask_t": _m(ask["apy"]), "years": ask["years"],
                        "interest": inter.get(p.id, ""), "offer": f"{_m(o['apy'])} x {o['years']}" if o else ""})
        return out, FA_COLS

    def refresh():
        rows, cols = rows_for()
        if view["v"] == "Payroll" or view["v"] == "Re-sign":
            rows = [r for r in rows if view["pos"] == "All positions" or r["pos"] == view["pos"]]
        table.columns = cols
        table.rows = rows
        if view["pid"] is not None and view["pid"] not in {r["id"] for r in rows}:
            view["pid"] = None
        header.refresh()
        panel.refresh()

    def changed():
        mark_changed()
        refresh()
        if on_change:
            on_change()

    def set_view(v):
        view["v"] = v
        view["pid"] = None
        refresh()

    def set_pos(v):
        view["pos"] = v
        refresh()

    def select(pid):
        view["pid"] = pid
        panel.refresh()

    def outer_refresh():
        v = default_view()
        if season.in_offseason(league) and v != view["v"] and view["v"] != "Payroll":
            view["v"] = v
            toggle.value = v
        refresh()

    refresh()
    return outer_refresh
