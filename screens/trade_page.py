# trade_page.py
# The Trades tab (Oct 23; engine/trades.py). Blake's choices: AI teams call you with
# offers at real NFL rates; future picks up to three drafts out; the other GM answers in
# words like a phone call ("not interested", "close, add a little", or a counter-offer),
# with no value meter or numbers, and a GM you keep insulting stops taking your calls for
# a while; trades are open from the new league year to the real deadline.
#   Make a trade   pick a team, tick players and picks on both sides, see the cap and
#                  roster effect, then make the call
#   Offers         AI teams' calls to you (each good until the next week or phase)
#   Shop a player  which teams want one of your players, how keen they are, their offers
#   Trade log      every trade in the league
# Screens read the engine only.

from html import escape

from nicegui import ui

from engine import contracts as C
from engine import free_agency as FA
from engine import trades as T
from engine.scale import seen
from engine.teams import ROSTER_TEMPLATE
from . import popups, theme
from .state import state, mark_changed

POSITION_ORDER = list(ROSTER_TEMPLATE)
VIEWS = ["Make a trade", "Offers to you", "Shop a player", "Trade log"]
PLAYER_COLS = [
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "right"},
    {"name": "pot", "label": "Potential", "field": "pot", "sortable": True, "align": "right"},
    {"name": "apy", "label": "Per year", "field": "apy", "sortable": True, "align": "right"},
    {"name": "left", "label": "Years left", "field": "left", "sortable": True, "align": "right"},
    {"name": "hit", "label": "Cap hit now", "field": "hit", "sortable": True, "align": "right"},
]
PICK_COLS = [
    {"name": "label", "label": "Pick", "field": "label", "sortable": False, "align": "left"},
    {"name": "where", "label": "Where it falls", "field": "where", "sortable": False, "align": "left"},
]
LOG_COLS = [
    {"name": "when", "label": "When", "field": "when", "sortable": False, "align": "left"},
    {"name": "a", "label": "Team", "field": "a", "sortable": True, "align": "left"},
    {"name": "a_gave", "label": "Sent", "field": "a_gave", "sortable": False, "align": "left"},
    {"name": "b", "label": "Team", "field": "b", "sortable": True, "align": "left"},
    {"name": "b_gave", "label": "Sent", "field": "b_gave", "sortable": False, "align": "left"},
]

CSS = """
<style>
  .trade-side h3 { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 22px; margin: 0 0 4px; }
  .trade-sum { background: var(--paper); border: 1px solid var(--line); border-top: 3px solid var(--turf);
               border-radius: 3px; padding: 10px 16px; }
  .trade-sum .k { font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 13px;
                  text-transform: uppercase; letter-spacing: .05em; color: var(--ink-soft); }
  .call-box { border-left: 5px solid var(--turf); background: #F3F7F1; padding: 12px 16px; border-radius: 3px; }
  .call-box .who { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 20px; }
  .call-box .said { font-size: 19px; margin-top: 4px; }
  .offer-card { background: var(--paper); border: 1px solid var(--line); border-radius: 4px; padding: 12px 16px;
                margin-bottom: 10px; }
  .offer-card .team { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 21px; }
  .offer-card .note { font-style: italic; margin: 4px 0 6px; }
  .mine-row td { background: #FFF6CF; }
</style>
"""


def _m(k):
    return C.fmt_money(k)


def _age(league, p):
    from datetime import date
    return p.age(date(league.season, 9, 1))


def player_rows(league, tid, exclude_untradable=True):
    rows = []
    for p in league.team_players(tid):
        if exclude_untradable and not T.tradable(league, p.id, tid)[0]:
            continue
        c = league.contracts.get(p.id)
        if c is None:
            continue
        hit = C.cap_hit(league, c)
        rows.append({"id": p.id, "pos": p.position, "pos_style": theme.position_style(p.position),
                     "pos_sort": POSITION_ORDER.index(p.position) * 1000 - seen(league, p),
                     "name": p.name, "age": _age(league, p), "ovr": seen(league, p),
                     "pot": seen(league, p, "potential"), "apy": c["apy"], "apy_t": _m(c["apy"]),
                     "left": C.years_left(c, league.season), "hit": hit, "hit_t": _m(hit)})
    return rows


def pick_rows(league, tid):
    out = []
    for k in T.team_picks(league, tid):
        num = T.pick_number(league, k)
        where = (f"No. {num} overall" if num else
                 {"early": "Likely early in the round", "middle": "Likely mid-round",
                  "late": "Likely late in the round"}[T.pick_words(league, k)])
        out.append({"id": k, "label": T.pick_label(league, k, short=True), "where": where})
    return out


def deal_html(league, you, other, give, get, release=()):
    """The deal in words, with what it does to both caps and rosters."""
    yours = T.side_text(league, give)
    theirs = T.side_text(league, get)
    html = (f'<div class="facts"><span class="k">You give</span><span>{escape(yours)}</span>'
            f'<span class="k">You get</span><span>{escape(theirs)}</span>')
    if give["players"] or get["players"]:
        eff = T.cap_effect(league, you, other, {"a": give, "b": get})
        e = eff[you]
        html += (f'<span class="k">Your cap room</span><span>{_m(e["room_before"])} now, {_m(e["room_after"])} after'
                 + (f' (dead money from players you send: {_m(e["dead"])})' if e["dead"] else "") + '</span>')
        o = eff[other]
        html += (f'<span class="k">Their cap room</span><span>{_m(o["room_before"])} now, {_m(o["room_after"])} '
                 f'after</span>')
        from engine import transactions as TR
        n = T.roster_after(league, you, len(get["players"]), len(give["players"])) - len(release)
        html += (f'<span class="k">Your roster</span><span>{n} of {TR.roster_limit(league)}'
                 + (f' (after releasing {len(release)})' if release else '') + '</span>')
    return html + "</div>"


def build_trade_tab(on_change=None):
    """Builds the Trades tab. Returns a function that refreshes it."""
    league = state.league
    ui.add_head_html(CSS)
    st = {"view": VIEWS[0], "other": None, "give_p": set(), "give_k": set(), "get_p": set(), "get_k": set(),
          "shop": None, "shop_res": None, "log": "Your trades", "release": set(), "release_for": {}}

    def you():
        return league.user_team_id

    def others():
        return {t.id: t.name for t in league.teams if t.id != you()}

    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def header():
            if you() is None:
                ui.label("Pick your team first.").classes("legend")
                return
            ok, why = T.window(league)
            if ok:
                extra = "" if why.startswith("Deadline week") else (escape(why) + " ")
                text = (f'<b>Trades are open.</b> {extra}{escape(T.deadline_words(league))} '
                        f'Picks in the next three drafts can be traded.')
            else:
                text = f'<b>Trades are closed.</b> {escape(why)}'
            n = len(T.inbox(league))
            if n:
                text += f' <b>{n} offer{"s" if n != 1 else ""} waiting</b> (Offers to you).'
            ui.html(f'<div class="notice">{text}</div>', sanitize=False)
        header()

    with ui.row().classes("w-full px-8 pt-3 items-center gap-4"):
        toggle = ui.toggle(VIEWS, value=st["view"], on_change=lambda e: set_view(e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")

    body = ui.element("div").classes("w-full px-8 py-3")

    # ---- the phone call -------------------------------------------------------
    with ui.dialog() as call_dialog, ui.card().classes("p-6").style("min-width:520px; max-width:640px"):
        call_html = ui.html("", sanitize=False)
        call_buttons = ui.row().classes("justify-end w-full mt-3 gap-2")

    def show_call(ans, give, get):
        other = st["other"]
        gm = escape(ans.get("gm") or "")
        html = (f'<div class="call-box"><div class="who">{gm}, {escape(league.team(other).name)}</div>'
                f'<div class="said">"{escape(ans["words"])}"</div></div>')
        counter = ans.get("counter")
        if counter:
            html += (f'<div class="legend" style="margin-top:10px">What they\'d do:</div>'
                     + deal_html(league, you(), other, counter["a"], counter["b"]))
        call_html.content = html
        call_buttons.clear()
        with call_buttons:
            if ans["kind"] == "accept":
                ui.button("Hang up (back out)", on_click=lambda: (T.back_out(league, other), call_dialog.close(),
                                                                  mark_changed(), refresh())) \
                    .props("flat no-caps color=red-9").tooltip("GMs remember when you back out of a deal")
                ui.button("Make the trade", on_click=lambda: do_trade(other, give, get)) \
                    .props("no-caps color=green-10")
            elif counter:
                ui.button("No thanks", on_click=call_dialog.close).props("flat no-caps")
                ui.button("Load it to edit", on_click=lambda: load_deal(other, counter)).props("outline no-caps color=green-10")
                ui.button("Take their offer", on_click=lambda: do_trade(other, counter["a"], counter["b"])) \
                    .props("no-caps color=green-10")
            else:
                ui.button("OK", on_click=call_dialog.close).props("no-caps color=green-10")
        call_dialog.open()

    def do_trade(other, give, get):
        call_dialog.close()
        ok, msg, _e = T.make_user_trade(league, other, give, get, release=sorted(st["release"]))
        ui.notify(msg, type="positive" if ok else "warning", multi_line=True)
        if ok:
            clear()
            changed()

    def load_deal(other, deal):
        call_dialog.close()
        st["other"] = other
        st["give_p"], st["give_k"] = set(deal["a"]["players"]), set(deal["a"]["picks"])
        st["get_p"], st["get_k"] = set(deal["b"]["players"]), set(deal["b"]["picks"])
        st["view"] = "Make a trade"
        toggle.value = "Make a trade"
        refresh()

    def clear():
        for k in ("give_p", "give_k", "get_p", "get_k", "release"):
            st[k] = set()

    def release_picker(give, get, chosen, on_pick):
        """A full roster: pick who you'd release when the trade goes through."""
        need = T.room_needed(league, give, get)
        if not need:
            return
        opts = {}
        for q in sorted(league.team_players(you()), key=lambda q: seen(league, q)):
            if q.id not in give["players"] and not FA.release_block(league, q.id):
                opts[q.id] = f"{q.position} {q.name} ({seen(league, q)})"
        ui.select(opts, value=[x for x in chosen if x in opts], multiple=True,
                  label=f"Release to make room ({need} needed; cut when the trade goes through)",
                  on_change=lambda e: on_pick(set(e.value or []))) \
            .props("dense outlined options-dense use-chips").classes("w-full mt-2")

    def current():
        return ({"players": sorted(st["give_p"]), "picks": sorted(st["give_k"])},
                {"players": sorted(st["get_p"]), "picks": sorted(st["get_k"])})

    def make_call():
        if st["other"] is None:
            ui.notify("Pick a team to call.")
            return
        give, get = current()
        ans = T.answer(league, st["other"], give, get, release=sorted(st["release"]))
        mark_changed()
        show_call(ans, give, get)
        summary.refresh()

    # ---- tables -----------------------------------------------------------------
    def players_table(rows, chosen, key):
        tbl = ui.table(rows=rows, columns=PLAYER_COLS, row_key="id", selection="multiple",
                       pagination={"rowsPerPage": 0, "sortBy": "pos"}) \
            .props("flat dense virtual-scroll hide-bottom").classes("roster-table w-full") \
            .style("height: calc(50vh - 210px); min-height: 230px")
        tbl.add_slot("body-cell-pos", r"""
            <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
        tbl.add_slot("body-cell-name", r"""
            <q-td :props="props"><a class="plink pname" :href="'/player/' + props.row.id">{{ props.row.name }}</a></q-td>""")
        for k, txt in (("apy", "apy_t"), ("hit", "hit_t")):
            tbl.add_slot(f"body-cell-{k}", f"""<q-td :props="props" class="num">{{{{ props.row.{txt} }}}}</q-td>""")
        tbl.selected = [r for r in rows if r["id"] in chosen]
        tbl.on_select(lambda e, key=key, tbl=tbl: picked(key, tbl))
        return tbl

    def picks_table(rows, chosen, key):
        tbl = ui.table(rows=rows, columns=PICK_COLS, row_key="id", selection="multiple",
                       pagination={"rowsPerPage": 0}) \
            .props("flat dense virtual-scroll hide-bottom").classes("roster-table w-full") \
            .style("height: 150px")
        tbl.selected = [r for r in rows if r["id"] in chosen]
        tbl.on_select(lambda e, key=key, tbl=tbl: picked(key, tbl))
        return tbl

    def picked(key, tbl):
        st[key] = {r["id"] for r in tbl.selected}
        summary.refresh()

    @ui.refreshable
    def summary():
        if st["other"] is None:
            return
        give, get = current()
        mood = T.mood_words(league, st["other"])
        both = bool((give["players"] or give["picks"]) and (get["players"] or get["picks"]))
        legal, problem = (T.check_deal(league, you(), st["other"], {"a": give, "b": get},
                                       release=sorted(st["release"])) if both else (False, ""))
        with ui.element("div").classes("trade-sum w-full"):
            ui.html(f'<div class="k">The deal</div>' + deal_html(league, you(), st["other"], give, get, st["release"]),
                    sanitize=False)
            if both:
                release_picker(give, get, st["release"], lambda v: (st.update(release=v), summary.refresh()))
            if both and not legal:
                ui.html(f'<div class="notice" style="margin-top:6px"><b>Not allowed:</b> {escape(problem)}</div>',
                        sanitize=False)
            with ui.row().classes("items-center gap-3 mt-2"):
                ui.button("Make the call", icon="call", on_click=make_call) \
                    .props("no-caps color=green-10" + ("" if both and legal else " disable"))
                ui.button("Clear", on_click=lambda: (clear(), refresh())).props("flat no-caps")
                ui.label(f"{T._gm_name(league, st['other'])}: {mood}").classes("legend")

    def make_view():
        if you() is None:
            return
        opts = others()
        with ui.row().classes("items-center gap-4 mb-2"):
            ui.select(opts, value=st["other"], label="Trade with",
                      on_change=lambda e: (st.update(other=e.value, get_p=set(), get_k=set()), refresh())) \
                .props("dense outlined options-dense").classes("w-72")
            ui.label("Tick players and picks on both sides, then make the call. Click a name for his player card.") \
                .classes("legend")
        with ui.row().classes("w-full gap-5 no-wrap items-start"):
            with ui.element("div").classes("trade-side").style("flex: 1 1 0; min-width: 0"):
                ui.html("<h3>You give</h3>", sanitize=False)
                players_table(player_rows(league, you()), st["give_p"], "give_p")
                ui.label("Your picks").classes("legend mt-2")
                picks_table(pick_rows(league, you()), st["give_k"], "give_k")
            with ui.element("div").classes("trade-side").style("flex: 1 1 0; min-width: 0"):
                if st["other"] is None:
                    ui.html("<h3>You get</h3>", sanitize=False)
                    ui.label("Pick a team to trade with.").classes("legend")
                else:
                    ui.html(f"<h3>You get from the {escape(league.team(st['other']).name)}</h3>", sanitize=False)
                    players_table(player_rows(league, st["other"]), st["get_p"], "get_p")
                    ui.label("Their picks").classes("legend mt-2")
                    picks_table(pick_rows(league, st["other"]), st["get_k"], "get_k")
        with ui.element("div").classes("w-full mt-3"):
            summary()

    def offers_view():
        offers = T.inbox(league)
        if not offers:
            ui.label("No offers right now. AI teams call now and then, more around the draft and near the trade "
                     "deadline; each offer is good until the next week or offseason phase.").classes("legend")
            return
        for o in offers:
            with ui.element("div").classes("offer-card"):
                ui.html(f'<div class="team">{escape(league.team(o["team"]).name)}</div>'
                        f'<div class="legend">{escape(o["gm"])} called · {escape(o["when"])} · good until your next '
                        f'week or phase</div><div class="note">"{escape(o["note"])}"</div>'
                        + deal_html(league, you(), o["team"], o["give"], o["get"]), sanitize=False)
                release_picker(o["give"], o["get"], st["release_for"].get(o["id"], set()),
                               lambda v, o=o: st["release_for"].__setitem__(o["id"], v))
                with ui.row().classes("gap-2 mt-2"):
                    ui.button("Accept", on_click=lambda o=o: take(o["id"])).props("no-caps color=green-10")
                    ui.button("Decline", on_click=lambda o=o: (T.decline_offer(league, o["id"]), changed())) \
                        .props("flat no-caps")
                    ui.button("Edit it and call back", on_click=lambda o=o: load_deal(
                        o["team"], {"a": o["give"], "b": o["get"]})).props("outline no-caps color=green-10")

    def take(offer_id):
        ok, msg = T.take_offer(league, offer_id, release=sorted(st["release_for"].get(offer_id, set())))
        ui.notify(msg, type="positive" if ok else "warning", multi_line=True)
        changed()

    def shop_view():
        if you() is None:
            return
        rows = player_rows(league, you())
        with ui.row().classes("w-full gap-5 no-wrap items-start"):
            with ui.element("div").style("flex: 1 1 0; min-width: 0"):
                ui.label("Pick one of your players and shop him around: you'll see which teams want him, how keen "
                         "they are and what they'd give. Word gets around the league.").classes("legend mb-1")
                tbl = ui.table(rows=rows, columns=PLAYER_COLS, row_key="id", selection="single",
                               pagination={"rowsPerPage": 0, "sortBy": "pos"}) \
                    .props("flat dense virtual-scroll hide-bottom").classes("roster-table w-full") \
                    .style("height: calc(100vh - 360px)")
                tbl.add_slot("body-cell-pos", r"""
                    <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
                for k, txt in (("apy", "apy_t"), ("hit", "hit_t")):
                    tbl.add_slot(f"body-cell-{k}", f"""<q-td :props="props" class="num">{{{{ props.row.{txt} }}}}</q-td>""")
                tbl.selected = [r for r in rows if r["id"] == st["shop"]]
                tbl.on_select(lambda e: st.update(shop=(tbl.selected[0]["id"] if tbl.selected else None)))
                ui.button("Shop him", icon="campaign", on_click=do_shop).props("no-caps color=green-10 mt-2")
            with ui.element("div").classes("report px-6 py-5").style("flex: 0 0 520px; height: calc(100vh - 330px);"
                                                                    " overflow-y: auto"):
                res = st["shop_res"]
                if not res:
                    ui.label("No player shopped yet.").classes("legend")
                    return
                pid, offers = res
                p = league.player(pid)
                ui.html(f'<h3>{escape(p.position)} {escape(p.name)}: who called</h3>', sanitize=False)
                if not offers:
                    ui.label("Nobody bit. No team wants to give up anything for him right now.").classes("legend")
                for o in offers:
                    with ui.element("div").classes("offer-card"):
                        ui.html(f'<div class="team">{escape(league.team(o["team"]).name)}</div>'
                                f'<div class="legend">{escape(o["gm"])} · {escape(o["interest"])}</div>'
                                + deal_html(league, you(), o["team"], o["deal"]["a"], o["deal"]["b"]), sanitize=False)
                        ui.button("Take it", on_click=lambda o=o: shop_take(o)).props("no-caps color=green-10 mt-1")

    def do_shop():
        if st["shop"] is None:
            ui.notify("Pick one of your players first.")
            return
        ok, why = T.window(league)
        if not ok:
            ui.notify(why)
            return
        st["shop_res"] = (st["shop"], T.shop(league, st["shop"]))
        mark_changed()
        refresh()

    def shop_take(o):
        st["other"] = o["team"]
        ok, msg, _e = T.make_user_trade(league, o["team"], o["deal"]["a"], o["deal"]["b"])
        ui.notify(msg, type="positive" if ok else "warning", multi_line=True)
        if ok:
            st["shop_res"] = None
            changed()

    def log_view():
        with ui.row().classes("items-center gap-4 mb-2"):
            ui.toggle(["Your trades", "All trades"], value=st["log"],
                      on_change=lambda e: (st.update(log=e.value), refresh())) \
                .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")
        rows = []
        for e in reversed(T.log(league)):
            if st["log"] == "Your trades" and you() not in e["teams"]:
                continue
            a, b = e["teams"]
            rows.append({"id": e["id"], "when": f'{e["season"]} · {e["when"]}', "a": league.team(a).abbrev,
                         "a_gave": T.side_text(league, e["gave"]["a"], short=True), "b": league.team(b).abbrev,
                         "b_gave": T.side_text(league, e["gave"]["b"], short=True)})
        if not rows:
            ui.label("No trades yet." if st["log"] == "All trades" else "You haven't made a trade yet.") \
                .classes("legend")
            return
        ui.table(rows=rows, columns=LOG_COLS, row_key="id", pagination={"rowsPerPage": 0}) \
            .props("flat dense virtual-scroll hide-bottom wrap-cells").classes("roster-table w-full") \
            .style("height: calc(100vh - 330px)")

    def refresh():
        header.refresh()
        body.clear()
        with body:
            {"Make a trade": make_view, "Offers to you": offers_view, "Shop a player": shop_view,
             "Trade log": log_view}[st["view"]]()

    def changed():
        mark_changed()
        refresh()
        if on_change:
            on_change()

    def set_view(v):
        st["view"] = v
        refresh()

    def outer_refresh():
        # Players who left a side (traded, cut) drop out of the deal being built.
        if you() is not None:
            mine = {pid for pid, t in league.rosters.items() if t == you()}
            st["give_p"] &= mine
            if st["other"] is not None:
                theirs = {pid for pid, t in league.rosters.items() if t == st["other"]}
                st["get_p"] &= theirs
            st["give_k"] = {k for k in st["give_k"] if T.owner(league, k) == you()}
            st["get_k"] = {k for k in st["get_k"] if st["other"] is not None and T.owner(league, k) == st["other"]}
        refresh()

    refresh()
    return outer_refresh
