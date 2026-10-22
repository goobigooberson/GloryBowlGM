# draft_page.py
# The Draft tab (Step 8's screens; Blake, Oct 23: scout the class before the draft,
# fewer and harder scouting choices, interviews read the person and his football
# mind, combine results in real units with where they rank):
#   Prospects    this year's class, from the start of the league year: your staff's
#                grade of each prospect as a range that narrows as you scout, and the
#                scouting itself (film study, cross-checks, top-30 visits, interviews),
#                until the draft starts
#   Draft room   the draft, pick by pick: who's on the clock, your staff's board, your
#                needs, trade offers and your own offers; draft a player, let your staff
#                pick, step one pick, sim to your next pick, or let your staff finish
#   Results      every pick of this draft (or an earlier one) and the draft-day trades
# A new league's startup draft (every team drafts its 53-man roster) gets its own room
# here too. Screens read the engine only (draft_day.py, scouting.py).

from html import escape

from nicegui import run, ui

from engine import draft_day as DD
from engine import formatting as fmt
from engine import positions as pos
from engine import scouting as S
from engine.scale import shown
from engine.teams import ROSTER_TEMPLATE
from . import popups, theme
from .state import state, mark_changed

POSITION_ORDER = list(ROSTER_TEMPLATE)
PLURAL = {"T": "tackles", "G": "guards", "C": "centers", "S": "safeties", "K": "kickers", "P": "punters",
          "LS": "long snappers"}
STEP_COST = {"film": f"{S.FILM_HOURS} hours", "cross": f"{S.CROSS_CHECK_HOURS} hours",
             "visit": "1 visit", "interview": "1 interview"}
STEP_HELP = {
    "film": "Your scouts study his college tape: clears most of what the whole league has wrong about him.",
    "cross": "A second scout checks the first one's work: clears more of what's still wrong.",
    "visit": "He visits your building (top-30 visit): the best look your staff gets at him.",
    "interview": ("Your staff's read on the person (leadership, loyalty, wanting to win, how steady he is). "
                  "It almost always turns up a character red flag if he has one, and how he talks football "
                  "sharpens his grade a little."),
}


def _plural(position):
    return PLURAL.get(position, position + "s")


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return str(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


async def _maybe(result):
    """Await a callback's result if it's a coroutine (main_page's Next is async)."""
    if hasattr(result, "__await__"):
        await result


def range_text(r):
    """(61, 68) -> 'Good (61-68)', by the middle of the range."""
    lo, hi = r
    word = fmt.skill_word((lo + hi) // 2)
    return f"{word} ({lo}-{hi})" if lo != hi else f"{word} ({lo})"


def range_color(r):
    return theme.RATING_COLORS[fmt.skill_word((r[0] + r[1]) // 2)]


def scouted_html(steps):
    out = []
    for k, letter in (("film", "F"), ("cross", "C"), ("visit", "V"), ("interview", "I")):
        on = k in steps
        out.append(f'<span title="{S.STEP_NAMES[k]}{"" if on else ": not yet"}" style="display:inline-block;'
                   f'width:17px;text-align:center;border-radius:3px;margin-right:2px;font-size:12px;'
                   f'font-weight:600;{"background:#2E8B47;color:white" if on else "background:#EEF1EC;color:#9AA39A"}">'
                   f'{letter}</span>')
    return "".join(out)


def _team_abbrev(league, tid):
    return league.team(tid).abbrev


# ---------------------------------------------------------------------------
# Table rows
# ---------------------------------------------------------------------------

PROSPECT_COLS = [
    {"name": "board", "label": "Board", "field": "board", "sortable": True, "align": "right"},
    {"name": "media", "label": "Media", "field": "media", "sortable": True, "align": "right"},
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "height", "label": "Height", "field": "height", "sortable": True, "align": "right",
     ":format": 'v => Math.floor(v / 12) + "-" + (v % 12)'},
    {"name": "weight", "label": "Weight", "field": "weight", "sortable": True, "align": "right"},
    {"name": "forty", "label": "40", "field": "forty", "sortable": True, "align": "right",
     ":format": 'v => v ? v.toFixed(2) : "-"'},
    {"name": "now", "label": "Now", "field": "now_mid", "sortable": True, "align": "left"},
    {"name": "ceiling", "label": "Ceiling", "field": "ceil_mid", "sortable": True, "align": "left"},
    {"name": "scouted", "label": "Scouted", "field": "scout_n", "sortable": True, "align": "left"},
    {"name": "flag", "label": "Flag", "field": "flag", "sortable": True, "align": "left"},
]


def board_ranks(league):
    """{pid: place on your staff's board among the prospects not yet drafted}."""
    board = DD.board(league)
    ranked = sorted(DD.available(league), key=lambda p: board.get(p.id, -99), reverse=True)
    return {p.id: i + 1 for i, p in enumerate(ranked)}


def prospect_rows(league, players):
    uid = league.user_team_id
    st = DD.stats(league)
    board_rank = board_ranks(league)
    media = DD.media_ranks(league)
    rows = []
    for p in players:
        now, ceil = S.grade_ranges(league, uid, p, st)
        steps = S.done_steps(league, p.id)
        rep_flag = (S.known_flag(league, uid, p) or "").title()
        rows.append({
            "id": p.id, "board": board_rank.get(p.id, 999), "media": media.get(p.id, 999),
            "pos": p.position, "pos_style": theme.position_style(p.position),
            "pos_sort": POSITION_ORDER.index(p.position) * 1000 + board_rank.get(p.id, 999),
            "name": p.name, "age": round(_draft_age(league, p), 1),
            "college": p.college, "height": p.height, "weight": p.weight,
            "forty": p.combine.get("forty"),
            "now": range_text(now), "now_mid": (now[0] + now[1]) / 2, "now_color": range_color(now),
            "ceil": range_text(ceil), "ceil_mid": (ceil[0] + ceil[1]) / 2, "ceil_color": range_color(ceil),
            "scouted": scouted_html(steps), "scout_n": len(steps), "flag": rep_flag,
        })
    return rows


def _draft_age(league, p):
    from datetime import date
    return (date(league.season, 4, 25) - p.birth_date).days / 365.25


def add_prospect_slots(table):
    table.add_slot("body-cell-pos", r"""
        <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
    for key, color in (("now", "now_color"), ("ceiling", "ceil_color")):
        field = "now" if key == "now" else "ceil"
        table.add_slot(f"body-cell-{key}", f"""
            <q-td :props="props"><span class="rating num">
              <span class="swatch" :style="{{background: props.row.{color}}}"></span>
              {{{{ props.row.{field} }}}}</span></q-td>""")
    table.add_slot("body-cell-scouted", r"""
        <q-td :props="props"><span v-html="props.row.scouted"></span></q-td>""")
    table.add_slot("body-cell-flag", r"""
        <q-td :props="props"><span v-if="props.row.flag" class="inj-tag inj-out">{{ props.row.flag }}</span></q-td>""")


# ---------------------------------------------------------------------------
# A prospect's report (right-hand panel)
# ---------------------------------------------------------------------------

def prospect_html(league, p):
    uid = league.user_team_id
    media = DD.media_ranks(league)
    st = DD.stats(league)
    rep = S.report(league, uid, p, media.get(p.id), st)
    pub, staff = rep["public"], rep["staff"]
    left = DD.available(league)
    your_rank = board_ranks(league).get(p.id)
    cr = DD.combine_ranks(league).get(p.id, {})
    pl = _plural(p.position)

    def fact_grid(rows):
        return '<div class="facts">' + "".join(
            f'<span class="k">{escape(k)}</span><span class="num">{v}</span>' for k, v in rows) + "</div>"

    flags = []
    if pub["medical_flag"]:
        flags.append("Medical red flag (from the combine medicals: every team knows)")
    if rep["interview"] and rep["interview"].get("character_flag"):
        flags.append("Character red flag (turned up in his interview)")
    facts = [("Age", f"{pub['age']} on draft day"), ("Size", escape(fmt.size(pub["height"], pub["weight"]))
                                                     + (f"  ({escape(p.build_note)})" if p.build_note else "")),
             ("College", escape(pub["college"])), ("Hometown", escape(p.hometown)),
             ("Media big board", f"#{pub['media_rank']}" if pub["media_rank"] else "-"),
             ("Your board", f"#{your_rank} of {len(left)} left" if your_rank else "Drafted")]
    if flags:
        facts.append(("Red flags", "<br>".join(escape(f) for f in flags)))

    def skill_row(label, now, ceil):
        word, color = fmt.skill_word((now[0] + now[1]) // 2), range_color(now)
        return (f'<div class="skill-row"><span>{escape(label)}</span>'
                f'<div class="skill-bar" title="Now {now[0]}-{now[1]}, ceiling {ceil[0]}-{ceil[1]}">'
                f'<div style="position:absolute;top:0;bottom:0;left:{ceil[0]}%;width:{max(1, ceil[1] - ceil[0])}%;'
                f'background:#D7E3D3;border-radius:2px"></div>'
                f'<div style="position:absolute;top:0;bottom:0;left:{now[0]}%;width:{max(1, now[1] - now[0])}%;'
                f'background:{color};border-radius:2px"></div></div>'
                f'<span class="num">{word} ({now[0]}-{now[1]}) / {ceil[0]}-{ceil[1]}</span></div>')
    skills = "".join(skill_row(pos.SKILLS[s][0], staff["skills"][s]["now"], staff["skills"][s]["ceiling"])
                     for s, _w in pos.POSITIONS[p.position][1] if s in staff["skills"])

    def ranked_txt(key, text):
        if key in cr:
            rk, n = cr[key]
            return f"{escape(text)} <span class='legend'>({ordinal(rk)} of {n} {pl})</span>"
        return escape(text)
    combine = [(fmt.DRILL_LABELS[d][0], ranked_txt(d, fmt.drill(d, pub["combine"].get(d))))
               for d in pos.COMBINE_DRILLS]
    combine += [("Intelligence test", ranked_txt("intel", f"{pub['intel_test']} out of 50")),
                ("Position drill", ranked_txt("drill", str(pub["position_drill"])))]
    done = staff["scouted"]
    if rep["interview"]:
        iv = rep["interview"]
        person = fact_grid([(S.PERSONALITY_NAMES[t], escape(fmt.trait(iv[t]))) for t in S.PERSONALITY])
        person += ('<div class="legend" style="margin-top:6px">Your staff\'s read from the interview (it can be '
                   'off by a few points). ' + ("<b>Character red flag.</b>" if iv.get("character_flag")
                                               else "No character concerns came up.") + '</div>')
    else:
        person = ('<div class="legend">Not interviewed. ' + escape(STEP_HELP["interview"]) + '</div>')
    scouted = ", ".join(S.STEP_NAMES[k] for k in done) if done else "Nothing yet: this is the league's word on him"
    now, ceil = staff["now"], staff["ceiling"]
    top = f"""
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
      <span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span>
      <span class="legend">{escape(pos.POSITIONS[p.position][0])} · draft prospect · {escape(pub["college"])}</span>
    </div>
    <h2 style="margin-top:6px">{escape(p.name)}</h2>
    <div class="rating" style="margin-top:8px;font-size:17px">
      <span class="swatch" style="background:{range_color(now)};width:14px;height:14px"></span>
      <span>Now {range_text(now)}</span><span class="legend">ceiling {range_text(ceil)}</span>
    </div>
    <div class="legend" style="margin-top:4px">Your staff's grade. Scouted: {escape(scouted)}. The ranges narrow
      as you scout him; the truth is inside about 2 times in 3, and some doubt always stays.</div>"""
    return top, f"""
    <h3>Bio</h3>{fact_grid(facts)}
    <h3>Ratings (your staff's view)</h3>{skills}
    <div class="legend" style="margin-top:6px">Dark: his ability now. Light: how good he could become.</div>
    <h3>Combine</h3>{fact_grid(combine)}
    <h3>Interview</h3>{person}
    """


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

def build_draft_tab(on_change=None, on_next=None, on_startup_done=None):
    """Builds the Draft tab. on_change: redraw the header and season bar after a
    move. on_next: the offseason's Next (finishes the draft). on_startup_done:
    the startup draft is over (camp opens). Returns a function that refreshes it."""
    league = state.league
    view = {"v": None, "pid": None, "pos": "All positions", "side": "Prospect", "need_only": False,
            "busy": False, "season": None}

    def views():
        if DD.in_startup(league):
            return ["Startup draft"]
        if DD.drafting(league):
            return ["Draft room", "Prospects", "Results"]
        if DD.has_class(league):
            return ["Prospects", "Results"]
        return ["Results"]

    def changed():
        mark_changed()
        if on_change:
            on_change()
        refresh()

    @ui.refreshable
    def body():
        ctx["table"] = None
        vs = views()
        if view["v"] not in vs or view.get("was") != vs[0]:
            view["v"] = vs[0]            # e.g. the draft just started: the draft room
            view["pid"] = None
        view["was"] = vs[0]
        with ui.row().classes("w-full px-8 pt-3 items-center gap-4"):
            if len(vs) > 1:
                ui.toggle(vs, value=view["v"], on_change=lambda e: set_view(e.value)) \
                    .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9") \
                    .tooltip("Prospects: this year's class and your scouting. Draft room: the draft, pick by "
                             "pick. Results: every pick and the draft-day trades.")
            header()
        if view["v"] == "Startup draft":
            startup_view()
        elif view["v"] == "Draft room":
            room_view()
        elif view["v"] == "Prospects":
            prospects_view()
        else:
            results_view()

    def set_view(v):
        view["v"] = v
        view["pid"] = None
        body.refresh()

    ctx = {"table": None}            # the prospect (or startup) table on screen

    @ui.refreshable
    def side():
        """The right-hand panel: redrawn alone when you click a player (the big
        table stays as it is, so clicks are quick)."""
        if view["v"] == "Draft room":
            room_side()
        elif view["v"] == "Startup draft":
            startup_side()
        else:
            prospect_panel()

    def highlight():
        t = ctx.get("table")
        if t is not None and view["pid"] is not None:
            t.props(f':table-row-class-fn="row => row.id === {view["pid"]} ? \'is-selected\' : \'\'"')

    @ui.refreshable
    def header():
        if league.user_team_id is None:
            ui.label("Pick your team first.").classes("legend")
            return
        if DD.in_startup(league):
            return
        if DD.scouting_open(league):
            b = S.budget(league)
            ui.html(f'<div class="legend">The {league.season} class: {len(DD.prospects(league))} prospects. '
                    f'Scouting left: <b>{b["hours"][0]}</b> of {b["hours"][1]} hours · <b>{b["interviews"][0]}</b> '
                    f'of {b["interviews"][1]} interviews · <b>{b["visits"][0]}</b> of {b["visits"][1]} top-30 '
                    f'visits. Scouting ends when the draft starts (after free agency wave 4).</div>',
                    sanitize=False)
        elif DD.drafting(league):
            mine = DD.your_slots(league)
            nxt = (f"Your next pick: #{mine[0]['pick']} (round {mine[0]['round']}); {len(mine)} left"
                   if mine else "You have no picks left in this draft")
            ui.html(f'<div class="legend">The {league.season} draft · {nxt} · scouting is over.</div>',
                    sanitize=False)
        elif not DD.has_class(league):
            ui.html('<div class="legend">The next draft class is announced at the start of the league year, '
                    'right after the season. You scout it during free agency, then draft it.</div>',
                    sanitize=False)

    # ---- Prospects (scouting) -------------------------------------------------
    def position_filter():
        ui.select(["All positions"] + POSITION_ORDER, value=view["pos"],
                  on_change=lambda e: (view.update(pos=e.value), body.refresh())) \
            .props("dense outlined options-dense").classes("w-44")

    def filtered(players):
        if view["pos"] != "All positions":
            players = [p for p in players if p.position == view["pos"]]
        return players

    def prospect_table(players, sort_by="board", height="calc(100vh - 330px)"):
        rows = prospect_rows(league, players)
        table = ui.table(rows=rows, columns=PROSPECT_COLS, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": sort_by}) \
            .props("flat dense virtual-scroll hide-bottom") \
            .classes("roster-table").style(f"flex: 1 1 0; min-width: 0; height: {height}")
        add_prospect_slots(table)
        ctx["table"] = table
        highlight()
        table.on("rowClick", lambda e: select(e.args[1]["id"]))
        return table

    def select(pid):
        view["pid"] = pid
        view["side"] = "Prospect"
        highlight()
        side.refresh()
        if view["v"] == "Draft room":
            clock_bar.refresh()

    def redraw_table():
        """New rows for the prospect table (after scouting or a pick)."""
        t = ctx.get("table")
        if t is not None:
            t.rows = prospect_rows(league, filtered(DD.available(league)))
            t.update()

    def prospects_view():
        with ui.row().classes("w-full px-8 pt-2 items-center gap-4"):
            position_filter()
            ui.label("Click a prospect for his report and to scout him. Your board: your staff's ranking "
                     "(talent, position value and age; red flags it knows about).").classes("legend")
        with ui.row().classes("w-full px-8 py-3 gap-5 no-wrap items-start"):
            prospect_table(filtered(DD.available(league)))
            with ui.element("div").classes("report px-6 py-5") \
                    .style("flex: 0 0 440px; height: calc(100vh - 330px); overflow-y: auto"):
                side()

    def prospect_panel():
        pid = view["pid"]
        pool = {p.id: p for p in DD.prospects(league)}
        if pid is None or pid not in pool:
            ui.label("No prospect selected").classes("condensed text-2xl")
            ui.label("Click any prospect to see his combine, your staff's grade and what your scouts can "
                     "still learn about him.").classes("legend")
            ui.html('<h3 style="margin-top:12px">How scouting works</h3>' + "".join(
                f'<div class="legend" style="margin-bottom:6px"><b>{S.STEP_NAMES[k]}</b> '
                f'({STEP_COST[k]}): {escape(STEP_HELP[k])}</div>' for k in S.STEPS), sanitize=False)
            return
        p = pool[pid]
        if DD.user_on_clock(league) and any(q.id == pid for q in DD.available(league)):
            ui.button(f"Draft {p.name}", on_click=lambda: draft_him(pid)) \
                .props("no-caps unelevated color=green-10").classes("mb-2")
        top, rest = prospect_html(league, p)
        ui.html(top, sanitize=False)
        open_ = DD.scouting_open(league)
        if open_ or S.done_steps(league, pid):
            scouting_buttons(pid, open_)
        ui.html(rest, sanitize=False)

    def scouting_buttons(pid, open_):
        ui.html("<h3>Scouting</h3>", sanitize=False)
        with ui.column().classes("gap-1"):
            for k in S.STEPS:
                done = k in S.done_steps(league, pid)
                ok, why = S.can_do(league, pid, k, open_)
                with ui.row().classes("items-center gap-2 no-wrap"):
                    b = ui.button(f"{S.STEP_NAMES[k]} ({STEP_COST[k]})" if not done else f"{S.STEP_NAMES[k]}: done",
                                  on_click=lambda k=k: scout(pid, k)) \
                        .props(f"no-caps dense {'unelevated color=green-10' if not done else 'flat color=green-10'}"
                               f" {'' if ok else 'disable'}")
                    b.tooltip(STEP_HELP[k] if ok or done else why)
                    if not ok and not done:
                        ui.label(why).classes("legend")

    def scout(pid, what):
        ok, msg = S.do(league, pid, what, DD.scouting_open(league))
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            mark_changed()
            redraw_table()
            header.refresh()
            side.refresh()

    # ---- The draft room --------------------------------------------------------
    def room_view():
        clock_bar()
        with ui.row().classes("w-full px-8 pt-1 items-center gap-4"):
            position_filter()
            ui.label("Sorted by your staff's board. Click a prospect for his report.").classes("legend")
        with ui.row().classes("w-full px-8 py-3 gap-5 no-wrap items-start"):
            prospect_table(filtered(DD.available(league)), height="calc(100vh - 400px)")
            with ui.column().classes("gap-2").style("flex: 0 0 460px"):
                side()

    def room_side():
        ui.toggle(["Prospect", "Trades", "Needs", "Picks"], value=view["side"],
                  on_change=lambda e: (view.update(side=e.value), side.refresh())) \
            .props("no-caps unelevated dense toggle-color=green-10 color=white text-color=grey-9")
        with ui.element("div").classes("report px-6 py-5 w-full") \
                .style("height: calc(100vh - 440px); overflow-y: auto"):
            {"Prospect": prospect_panel, "Trades": trades_panel, "Needs": needs_panel,
             "Picks": picks_panel}[view["side"]]()

    @ui.refreshable
    def clock_bar():
        slot = DD.on_clock(league)
        uid = league.user_team_id
        with ui.row().classes("w-full px-8 pt-2 items-center gap-3"):
            with ui.element("div").classes("notice").style("flex:1"):
                if slot is None:
                    ui.html("<b>The draft is over.</b>", sanitize=False)
                else:
                    team = league.team(slot["team"])
                    via = f" (from {league.team(slot['from']).abbrev})" if slot["from"] != slot["team"] else ""
                    yours = slot["team"] == uid
                    choice, cslot = DD.staff_choice(league)
                    staff = ""
                    if choice is not None and cslot is not None:
                        q = league.player(choice)
                        staff = (f" Your staff would take <b>{q.position} {escape(q.name)}</b>"
                                 + (" here." if yours else f" with pick #{cslot['pick']} if the draft were there now."))
                    ui.html(f'<span class="condensed" style="font-size:22px;font-weight:700">'
                            f'Round {slot["round"]}, pick {slot["pick"]}: '
                            f'{"YOU ARE ON THE CLOCK" if yours else escape(team.name) + via}</span>'
                            f'<span class="legend" style="margin-left:10px">{staff}</span>', sanitize=False)
            if slot is not None and slot["team"] == uid:
                pid = view["pid"]
                avail = {p.id for p in DD.available(league)}
                b = ui.button("Draft selected player", on_click=lambda: draft_him(view["pid"])) \
                    .props(f"no-caps unelevated color=green-10 {'' if pid in avail else 'disable'}")
                b.tooltip("Click a prospect in the list first" if pid not in avail else
                          f"Draft {league.player(pid).name}")
                ui.button("Let my staff pick", on_click=lambda: staff_picks()) \
                    .props("no-caps outline color=green-10") \
                    .tooltip("Your staff takes the best player on your board, with your needs in mind")
            elif slot is not None:
                ui.button("Next pick", on_click=lambda: next_pick()).props("no-caps outline color=green-10") \
                    .tooltip("The team on the clock makes its pick (it may trade first). Stop here to offer "
                             "that team a trade for this pick.")
                if DD.your_slots(league):
                    ui.button("Sim to my pick", on_click=lambda: sim_to_mine()) \
                        .props("no-caps unelevated color=green-10") \
                        .tooltip("Every pick until you're on the clock again")
            if slot is not None:
                ui.button("Staff finishes the draft", on_click=lambda: finish_it()) \
                    .props("no-caps flat color=green-10") \
                    .tooltip("Your staff makes the rest of your picks (no trades) and the draft finishes. "
                             "Same as Next in the bar above.")

    async def busy(fn, *args):
        if view["busy"]:
            return None
        view["busy"] = True
        try:
            return await run.io_bound(fn, league, *args)
        finally:
            view["busy"] = False

    async def after_move():
        mark_changed()
        if DD.drafting(league) and DD.on_clock(league) is None and on_next:
            ui.notify("The last pick is in.", type="positive", position="top")
            await _maybe(on_next())
            return
        if on_change:
            on_change()
        refresh()

    async def draft_him(pid):
        if pid is None:
            ui.notify("Click a prospect in the list first.", position="top")
            return
        ok, msg = DD.pick(league, pid)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            view["pid"] = None
            await after_move()

    async def staff_picks():
        ok, msg = DD.staff_pick(league)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            await after_move()

    async def next_pick():
        made = DD.step(league)
        if made:
            p = league.player(made["pid"])
            ui.notify(f"Pick {made['pick']}: {league.team(made['team']).name} take {p.position} {p.name}.",
                      position="top")
        await after_move()

    async def sim_to_mine():
        await busy(DD.sim_to_user)
        await after_move()

    async def finish_it():
        if on_next:
            await _maybe(on_next())

    def trades_panel():
        uid = league.user_team_id
        slot = DD.on_clock(league)
        if slot is None:
            ui.label("The draft is over.").classes("legend")
            return
        ui.html("<h3 style='margin-top:0'>Offers for your pick</h3>", sanitize=False)
        if slot["team"] != uid:
            ui.label("When you're on the clock, teams behind you that want to move up call with offers "
                     "here.").classes("legend")
        else:
            offs = DD.offers(league)
            if not offs:
                ui.label("No calls: nobody behind you wants to move up badly enough.").classes("legend")
            for o in offs:
                with ui.row().classes("items-center gap-2 no-wrap w-full").style("border-bottom:1px solid #EEF1EC;padding:4px 0"):
                    ui.html(f'<div><b>{escape(league.team(o["team"]).name)}</b> offer pick'
                            f'{"s" if len(o["gives"]) > 1 else ""} {", ".join(map(str, o["gives"]))} '
                            f'<span class="legend">({o["chart_points"]:,} chart points for your '
                            f'{o["for_points"]:,})</span></div>', sanitize=False).style("flex:1")
                    ui.button("Accept", on_click=lambda o=o: take_offer(o)).props("no-caps dense color=green-10")
        ui.html("<h3>Make an offer</h3>", sanitize=False)
        ui.label("Picks in this draft only. AI teams want at least full value by the Jimmy Johnson trade "
                 "chart (what real teams use), and a team on the clock (or a few picks from it) that loves a "
                 "player still on the board won't move down.").classes("legend")
        others = {t.id: t.name for t in sorted(league.teams, key=lambda t: t.name) if t.id != uid}
        offer = view.setdefault("offer", {"team": None, "give": [], "get": [], "clock": None})
        if offer["team"] not in others or offer.get("clock") != slot["pick"]:
            # A new team on the clock: the offer form starts with that team and its pick.
            offer.update(team=slot["team"] if slot["team"] != uid else next(iter(others)),
                         get=[slot["pick"]] if slot["team"] != uid else [], give=[], clock=slot["pick"])
        mine = DD.your_slots(league)
        theirs = DD.slots_left(league, offer["team"])

        def label(s):
            return f"#{s['pick']} (round {s['round']}, {DD.chart_points(s['pick']):,} pts)"
        ui.select(others, value=offer["team"], label="Trade with",
                  on_change=lambda e: (offer.update(team=e.value, get=[]), side.refresh())) \
            .props("dense outlined options-dense").classes("w-full mt-2")
        ui.select({s["pick"]: label(s) for s in theirs}, value=[x for x in offer["get"] if x in {s["pick"] for s in theirs}],
                  multiple=True, label="You get",
                  on_change=lambda e: (offer.update(get=list(e.value or [])), preview.refresh())) \
            .props("dense outlined options-dense use-chips").classes("w-full mt-1")
        ui.select({s["pick"]: label(s) for s in mine}, value=[x for x in offer["give"] if x in {s["pick"] for s in mine}],
                  multiple=True, label="You give",
                  on_change=lambda e: (offer.update(give=list(e.value or [])), preview.refresh())) \
            .props("dense outlined options-dense use-chips").classes("w-full mt-1")

        @ui.refreshable
        def preview():
            give, get = offer["give"], offer["get"]
            if give and get:
                ok, why = DD.trade_check(league, offer["team"], give, get)
                ui.html(f'<div class="{"legend" if ok else "problem"}" style="margin-top:6px">'
                        f'{"They would take it: " if ok else ""}{escape(why)}</div>', sanitize=False)
                ui.button("Propose trade", on_click=lambda: propose()) \
                    .props(f"no-caps unelevated color=green-10 dense {'' if ok else 'disable'}").classes("mt-1")
            else:
                ui.label("Choose picks on both sides.").classes("legend mt-1")
        preview()

        async def propose():
            ok, msg = DD.propose(league, offer["team"], offer["give"], offer["get"])
            ui.notify(msg, type="positive" if ok else "warning", position="top", multi_line=True)
            if ok:
                offer.update(give=[], get=[])
                await after_move()

    async def take_offer(o):
        ok, msg = DD.accept_offer(league, o)
        ui.notify(msg, type="positive" if ok else "warning", position="top", multi_line=True)
        if ok:
            await after_move()

    def needs_panel():
        rows, note = DD.needs(league, league.user_team_id)
        body_rows = "".join(
            f'<tr><td class="l"><span class="pos-tag" style="{theme.position_style(r["pos"])}">{r["pos"]}</span></td>'
            f'<td class="l">{r["need"]}</td><td>{r["weakest"]}</td><td>{r["typical"]}</td>'
            f'<td>{r["bodies"]} / {r["spots"]}</td></tr>' for r in rows)
        ui.html('<h3 style="margin-top:0">Your needs</h3>'
                '<div class="legend">Need: how far your weakest starter there (as your staff expects him in a '
                'season or two) is below a typical NFL starter, and whether you have enough bodies for a '
                '53-man roster.</div>'
                + (f'<div class="notice" style="margin-top:6px">{escape(note)}</div>' if note else "")
                + '<table class="box-table" style="margin-top:8px"><thead><tr><th class="l">Pos</th>'
                  '<th class="l">Need</th><th>Your weakest starter</th><th>Typical starter</th>'
                  f'<th>Players / 53-man spots</th></tr></thead><tbody>{body_rows}</tbody></table>', sanitize=False)

    def picks_panel():
        uid = league.user_team_id
        mine = DD.your_slots(league)
        made = DD.made_picks(league)
        ui.html('<h3 style="margin-top:0">Your picks to come</h3>' + (
            "<div>" + ", ".join(f"#{s['pick']} (round {s['round']}"
                                + (f", from {_team_abbrev(league, s['from'])}" if s["from"] != uid else "") + ")"
                                for s in mine) + "</div>" if mine else '<div class="legend">None left.</div>'),
                sanitize=False)
        yours = [pk for pk in made if pk["team"] == uid]
        if yours:
            ui.html("<h3>Your picks</h3>" + "".join(
                f'<div>#{pk["pick"]} <span class="pos-tag" style="{theme.position_style(league.player(pk["pid"]).position)}">'
                f'{league.player(pk["pid"]).position}</span> {escape(league.player(pk["pid"]).name)}</div>'
                for pk in yours), sanitize=False)
        ui.html("<h3>Latest picks</h3>" + "".join(
            f'<div>#{pk["pick"]} {_team_abbrev(league, pk["team"])} '
            f'<span class="pos-tag" style="{theme.position_style(league.player(pk["pid"]).position)}">'
            f'{league.player(pk["pid"]).position}</span> {escape(league.player(pk["pid"]).name)} '
            f'<span class="legend">(media #{pk.get("board_rank") or "-"})</span></div>'
            for pk in reversed(made[-12:])) or '<div class="legend">No picks yet.</div>', sanitize=False)
        tr = DD.trades(league)
        if tr:
            ui.html("<h3>Trades</h3>" + "".join(_trade_line(league, t) for t in tr[-8:][::-1]), sanitize=False)

    # ---- Results -----------------------------------------------------------------
    def results_view():
        seasons = sorted({d["season"] for d in league.draft_history}, reverse=True)
        current = DD.drafting(league)
        options = ([league.season] if current else []) + [s for s in seasons if not (current and s == league.season)]
        if not options:
            ui.label("No drafts yet. This league's first draft is after its first season.") \
                .classes("legend px-8 py-4")
            return
        if view["season"] not in options:
            view["season"] = options[0]
        with ui.row().classes("w-full px-8 pt-2 items-center gap-4"):
            ui.select(options, value=view["season"], label="Draft",
                      on_change=lambda e: (view.update(season=e.value), body.refresh())) \
                .props("dense outlined options-dense").classes("w-40")
            ui.label("Every pick in order. Media rank: where the media's big board had him (a big gap is a "
                     "reach or a steal).").classes("legend")
        s = view["season"]
        if current and s == league.season:
            picks = DD.made_picks(league)
            trades = DD.trades(league)
        else:
            picks = [d for d in league.draft_history if d["season"] == s]
            rep = league.offseason_report or {}
            trades = rep.get("draft_trades", []) if rep.get("season") == s else []
        rows = []
        for d in picks:
            p = league.player(d["pid"])
            rows.append({"id": d["pid"], "pick": d["pick"], "round": d["round"], "team": _team_abbrev(league, d["team"]),
                         "via": _team_abbrev(league, d["from"]) if d.get("from") not in (None, d["team"]) else "",
                         "pos": p.position, "pos_style": theme.position_style(p.position), "name": p.name,
                         "college": p.college, "media": d.get("board_rank") or 999,
                         "mine": d["team"] == league.user_team_id})
        cols = [{"name": "pick", "label": "Pick", "field": "pick", "sortable": True, "align": "right"},
                {"name": "round", "label": "Round", "field": "round", "sortable": True, "align": "right"},
                {"name": "team", "label": "Team", "field": "team", "sortable": True, "align": "left"},
                {"name": "via", "label": "Pick from", "field": "via", "sortable": True, "align": "left"},
                {"name": "pos", "label": "Pos", "field": "pos", "sortable": True, "align": "left"},
                {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
                {"name": "college", "label": "College", "field": "college", "sortable": True, "align": "left"},
                {"name": "media", "label": "Media rank", "field": "media", "sortable": True, "align": "right",
                 ":format": 'v => v === 999 ? "-" : v'}]
        with ui.row().classes("w-full px-8 py-3 gap-5 no-wrap items-start"):
            table = ui.table(rows=rows, columns=cols, row_key="id", pagination={"rowsPerPage": 0, "sortBy": "pick"}) \
                .props("flat dense virtual-scroll hide-bottom") \
                .classes("roster-table").style("flex: 1 1 0; min-width: 0; height: calc(100vh - 330px)")
            table.add_slot("body-cell-pos", r"""
                <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
            table.props(r''':table-row-class-fn="row => row.mine ? 'is-selected' : ''"''')
            table.on("rowClick", lambda e: popups.show_player(e.args[1]["id"])
                     if not DD.drafting(league) else None)
            with ui.element("div").classes("report px-6 py-5") \
                    .style("flex: 0 0 420px; height: calc(100vh - 330px); overflow-y: auto"):
                ui.html('<h3 style="margin-top:0">Draft-day trades</h3>'
                        + ("".join(_trade_line(league, t) for t in trades)
                           or '<div class="legend">None on record for this draft (trades are kept for the latest '
                              'draft).</div>')
                        + '<div class="legend" style="margin-top:8px">Your picks are highlighted.</div>',
                        sanitize=False)

    # ---- The startup draft ---------------------------------------------------------
    def startup_view():
        uid = league.user_team_id
        startup_bar()
        r_need = {x["pos"]: x for x in DD.startup_needs(league, uid)}
        startup_table(r_need)

    @ui.refreshable
    def startup_bar():
        uid = league.user_team_id
        slot = DD.startup_on_clock(league)
        total = 53 * len(league.teams)
        with ui.row().classes("w-full px-8 pt-2 items-center gap-3"):
            with ui.element("div").classes("notice").style("flex:1"):
                if slot is None:
                    ui.html("<b>The startup draft is over.</b>", sanitize=False)
                else:
                    team = league.team(slot["team"])
                    yours = slot["team"] == uid
                    ch = DD.startup_staff_choice(league) if yours else None
                    staff = ""
                    if ch is not None:
                        q = league.player(ch)
                        staff = f" Your staff would take <b>{q.position} {escape(q.name)}</b>."
                    ui.html(f'<span class="condensed" style="font-size:22px;font-weight:700">Startup draft · round '
                            f'{slot["round"]} of 53 · pick {slot["pick"]:,} of {total:,}: '
                            f'{"YOU ARE ON THE CLOCK" if yours else escape(team.name)}</span>'
                            f'<span class="legend" style="margin-left:10px">{staff}</span>', sanitize=False)
            if slot is not None and slot["team"] == uid:
                pid = view["pid"]
                b = ui.button("Draft selected player", on_click=lambda: startup_draft_him(view["pid"])) \
                    .props(f"no-caps unelevated color=green-10 {'' if pid else 'disable'}")
                b.tooltip("Click a player in the list first" if not pid else f"Draft {league.player(pid).name}")
                ui.button("Let my staff pick", on_click=lambda: startup_staff()).props("no-caps outline color=green-10")
            elif slot is not None:
                ui.button("Next pick", on_click=lambda: startup_next()).props("no-caps outline color=green-10")
                ui.button("Sim to my pick", on_click=lambda: startup_to_mine()).props("no-caps unelevated color=green-10")
            ui.button("Staff finishes the draft", on_click=lambda: startup_finish()) \
                .props("no-caps flat color=green-10") \
                .tooltip("Your staff makes the rest of your picks, then training camp opens")

    def startup_table(r_need):
        uid = league.user_team_id
        with ui.row().classes("w-full px-8 pt-1 items-center gap-4"):
            position_filter()
            ui.checkbox("Only positions I still need", value=view["need_only"],
                        on_change=lambda e: (view.update(need_only=e.value), body.refresh()))
            ui.label("Every rostered player is in the pool; each team drafts a full 53 (each position to its "
                     "roster count). Showing the best 300 on your staff's board.").classes("legend")
        room = DD.startup_room(league)
        avail = room.available() if room else []
        if view["pos"] != "All positions":
            avail = [p for p in avail if p.position == view["pos"]]
        if view["need_only"]:
            avail = [p for p in avail if r_need.get(p.position, {}).get("have", 0) < r_need.get(p.position, {}).get("spots", 0)]
        score = {p.id: room.score(uid, p) for p in avail} if room else {}
        avail.sort(key=lambda p: score[p.id], reverse=True)
        rows = []
        for i, p in enumerate(avail[:300]):
            ovr, pot = shown(p.overall(), p.position), shown(p.overall("potential"), p.position)
            rows.append({"id": p.id, "board": i + 1, "pos": p.position, "pos_style": theme.position_style(p.position),
                         "pos_sort": POSITION_ORDER.index(p.position) * 1000 + i, "name": p.name,
                         "age": p.age(_sept1(league)), "exp": p.experience,
                         "ovr": ovr, "ovr_txt": fmt.skill(ovr), "ovr_color": theme.RATING_COLORS[fmt.skill_word(ovr)],
                         "pot": pot, "pot_txt": fmt.skill(pot), "pot_color": theme.RATING_COLORS[fmt.skill_word(pot)],
                         "college": p.college})
        cols = [{"name": "board", "label": "Your board", "field": "board", "sortable": True, "align": "right"},
                {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
                {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
                {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
                {"name": "exp", "label": "Exp", "field": "exp", "sortable": True, "align": "right",
                 ":format": 'v => v === 0 ? "R" : v'},
                {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "left"},
                {"name": "pot", "label": "Potential", "field": "pot", "sortable": True, "align": "left"},
                {"name": "college", "label": "College", "field": "college", "sortable": True, "align": "left"}]
        with ui.row().classes("w-full px-8 py-3 gap-5 no-wrap items-start"):
            table = ui.table(rows=rows, columns=cols, row_key="id", pagination={"rowsPerPage": 0, "sortBy": "board"}) \
                .props("flat dense virtual-scroll hide-bottom") \
                .classes("roster-table").style("flex: 1 1 0; min-width: 0; height: calc(100vh - 400px)")
            table.add_slot("body-cell-pos", r"""
                <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
            for key in ("ovr", "pot"):
                table.add_slot(f"body-cell-{key}", f"""
                    <q-td :props="props"><span class="rating num">
                      <span class="swatch" :style="{{background: props.row.{key}_color}}"></span>
                      {{{{ props.row.{key}_txt }}}}</span></q-td>""")
            ctx["table"] = table
            highlight()
            table.on("rowClick", lambda e: select_startup(e.args[1]["id"]))
            with ui.column().classes("gap-2").style("flex: 0 0 440px"):
                side()

    def select_startup(pid):
        view["pid"] = pid
        view["side"] = "Player"
        highlight()
        side.refresh()
        startup_bar.refresh()

    def startup_side():
        r_need = {x["pos"]: x for x in DD.startup_needs(league, league.user_team_id)}
        which = view["side"] if view["side"] in ("Player", "My roster", "Picks") else "My roster"
        ui.toggle(["Player", "My roster", "Picks"], value=which,
                  on_change=lambda e: (view.update(side=e.value), side.refresh())) \
            .props("no-caps unelevated dense toggle-color=green-10 color=white text-color=grey-9")
        with ui.element("div").classes("report px-6 py-5 w-full") \
                .style("height: calc(100vh - 440px); overflow-y: auto"):
            if which == "Player":
                startup_player_panel()
            elif which == "My roster":
                startup_roster_panel(r_need)
            else:
                startup_picks_panel()

    def _sept1(lg):
        from datetime import date
        return date(lg.season, 9, 1)

    def startup_player_panel():
        pid = view["pid"]
        if pid is None:
            ui.label("Click a player in the list.").classes("legend")
            return
        p = league.player(pid)
        ovr, pot = shown(p.overall(), p.position), shown(p.overall("potential"), p.position)
        skills = "".join(
            f'<div class="skill-row"><span>{escape(pos.SKILLS[s][0])}</span><div class="skill-bar">'
            f'<div class="pot" style="width:{shown(p.skills[s][1], p.position)}%"></div>'
            f'<div class="cur" style="width:{shown(p.skills[s][0], p.position)}%;'
            f'background:{theme.RATING_COLORS[fmt.skill_word(shown(p.skills[s][0], p.position))]}"></div></div>'
            f'<span class="num">{fmt.skill(shown(p.skills[s][0], p.position))} / {shown(p.skills[s][1], p.position)}</span></div>'
            for s, _w in pos.POSITIONS[p.position][1] if s not in pos.HIDDEN_SKILLS)
        exp = "Rookie" if p.experience == 0 else f"{p.experience} season{'s' if p.experience != 1 else ''}"
        drafted = "Undrafted" if p.draft_round == 0 else f"Round {p.draft_round}, {p.draft_year}"
        ui.html(f'<span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span>'
                f'<h2 style="margin-top:6px">{escape(p.name)}</h2>'
                f'<div class="legend">Age {p.age(_sept1(league))} · {exp} · {escape(fmt.size(p.height, p.weight))} · '
                f'{escape(p.college)} · {drafted}</div>'
                f'<div class="rating" style="margin-top:8px;font-size:17px"><span class="swatch" style="background:'
                f'{theme.RATING_COLORS[fmt.skill_word(ovr)]};width:14px;height:14px"></span>'
                f'<span>Overall {fmt.skill(ovr)}</span><span class="legend">potential {pot}</span></div>'
                f'<h3>Ratings</h3>{skills}', sanitize=False)
        slot = DD.startup_on_clock(league)
        if slot and slot["team"] == league.user_team_id:
            ui.button(f"Draft {p.name}", on_click=lambda: startup_draft_him(pid)) \
                .props("no-caps unelevated color=green-10").classes("mt-2")

    def startup_roster_panel(r_need):
        room = DD.startup_room(league)
        uid = league.user_team_id
        mine = [league.player(pk["pid"]) for pk in (room.picks if room else []) if pk["team"] == uid]
        by_pos = {}
        for p in mine:
            by_pos.setdefault(p.position, []).append(p)
        lines = []
        for position in POSITION_ORDER:
            need = r_need.get(position, {"have": 0, "spots": ROSTER_TEMPLATE[position]})
            names = ", ".join(f"{escape(p.name)} ({shown(p.overall(), p.position)})" for p in by_pos.get(position, []))
            short = ' style="color:#A3321F"' if need["have"] < need["spots"] else ""
            lines.append(f'<tr><td class="l"><span class="pos-tag" style="{theme.position_style(position)}">'
                         f'{position}</span></td><td{short}>'
                         f'{need["have"]} / {need["spots"]}</td><td class="l">{names or "-"}</td></tr>')
        ui.html(f'<h3 style="margin-top:0">Your roster so far ({len(mine)} of 53)</h3>'
                '<div class="legend">Each position fills to its roster count; you can\'t draft past it.</div>'
                '<table class="box-table" style="margin-top:6px"><thead><tr><th class="l">Pos</th><th>Have</th>'
                f'<th class="l">Players (overall)</th></tr></thead><tbody>{"".join(lines)}</tbody></table>',
                sanitize=False)

    def startup_picks_panel():
        room = DD.startup_room(league)
        picks = room.picks[-20:] if room else []
        ui.html('<h3 style="margin-top:0">Latest picks</h3>' + "".join(
            f'<div>#{pk["pick"]} {_team_abbrev(league, pk["team"])} '
            f'<span class="pos-tag" style="{theme.position_style(league.player(pk["pid"]).position)}">'
            f'{league.player(pk["pid"]).position}</span> {escape(league.player(pk["pid"]).name)} '
            f'<span class="legend">({shown(league.player(pk["pid"]).overall(), league.player(pk["pid"]).position)})</span></div>'
            for pk in reversed(picks)) or '<div class="legend">No picks yet.</div>', sanitize=False)

    async def startup_after():
        mark_changed()
        if DD.startup_on_clock(league) is None:
            await startup_finish()
            return
        if on_change:
            on_change()
        refresh()

    async def startup_draft_him(pid):
        if pid is None:
            ui.notify("Click a player in the list first.", position="top")
            return
        ok, msg = DD.startup_pick(league, pid)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            view["pid"] = None
            await startup_after()

    async def startup_staff():
        ok, msg = DD.startup_staff_pick(league)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            await startup_after()

    async def startup_next():
        made = DD.startup_step(league)
        if made:
            p = league.player(made["pid"])
            ui.notify(f"Pick {made['pick']}: {league.team(made['team']).name} take {p.position} {p.name}.",
                      position="top")
        await startup_after()

    async def startup_to_mine():
        await busy(DD.startup_sim_to_user)
        await startup_after()

    async def startup_finish():
        if on_startup_done:
            await _maybe(on_startup_done())

    def refresh():
        body.refresh()

    with ui.column().classes("w-full gap-0"):
        body()
    return refresh


def _trade_line(league, t):
    up, down = league.team(t["up"]).abbrev, league.team(t["down"]).abbrev
    you = league.user_team_id in (t["up"], t["down"])
    return (f'<div style="padding:3px 0;border-bottom:1px solid #F0F2EE{";font-weight:600" if you else ""}">'
            f'{up} get pick{"s" if len(t["got"]) > 1 else ""} {", ".join(map(str, t["got"]))}; {down} get '
            f'{", ".join(map(str, t["gave"]))} <span class="legend">(chart {t["jj_ratio"]:.2f}x)</span></div>')
