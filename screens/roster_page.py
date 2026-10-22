# roster_page.py
# The Roster tab: every player on the chosen team (or the free agent pool)
# in a sortable table. Click a player to read his full report on the right.
#
# Note: ratings shown here are the TRUE ratings. Once scouting exists, this
# screen will show what your scouts believe instead.

from datetime import date
from html import escape

from nicegui import ui

from engine import formatting as fmt
from engine import injuries
from engine import positions as pos
from engine import season
from engine import transactions
from engine.scale import shown
from engine.teams import ROSTER_TEMPLATE
from . import popups, theme
from .state import state, FREE_AGENTS, team_starter_ids, injury_text, injury_code, mark_changed
from .stats_page import player_stats_html

POSITION_ORDER = list(ROSTER_TEMPLATE)


# ---------------------------------------------------------------------------
# Data for the table
# ---------------------------------------------------------------------------

GROUPS = ["Roster", "Practice squad", "Reserve lists", "Moves"]


def current_players():
    league = state.league
    group = getattr(state, "roster_group", GROUPS[0])
    if state.team_id == FREE_AGENTS:
        players = league.free_agents()
    elif group == "Practice squad":
        players = transactions.practice_players(league, state.team_id)
    elif group == "Reserve lists":
        players = transactions.reserve_players(league, state.team_id)
    else:
        players = league.team_players(state.team_id)
    if state.unit != "All":
        players = [p for p in players if p.position in theme.UNITS[state.unit]]
    if state.position != "All positions":
        players = [p for p in players if p.position == state.position]
    return players


def rating_cell(value):
    word = fmt.skill_word(value)
    return word, theme.RATING_COLORS[word]


def player_row(p, today, starters, captains=(), cuts=(), keeps=()):
    ovr, pot = shown(p.overall(), p.position), shown(p.overall("potential"), p.position)
    ovr_word, ovr_color = rating_cell(ovr)
    pot_word, pot_color = rating_cell(pot)
    return {
        "id": p.id,
        # Training camp, your team: your staff's cut list and your keep marks.
        "cut": p.id in cuts, "keep": p.id in keeps,
        "pos": p.position,
        # Sorting by position keeps roster order (QB, RB, ... P), best first.
        "pos_sort": POSITION_ORDER.index(p.position) * 1000 + (999 - ovr),
        "pos_style": theme.position_style(p.position),
        "starter": p.id in starters,
        "captain": p.id in captains,
        "name": p.name,
        "inj": injury_text(p.id) or "", "inj_code": injury_code(p.id),
        "inj_class": "inj-tag inj-" + injury_code(p.id).lower(),
        "age": p.age(today),
        "exp": p.experience,
        "height": p.height,
        "weight": p.weight,
        "ovr": ovr, "ovr_word": ovr_word, "ovr_color": ovr_color,
        "pot": pot, "pot_word": pot_word, "pot_color": pot_color,
        "draft_sort": p.draft_year * 10 + (p.draft_round or 8),
        "draft_text": "Undrafted" if p.draft_round == 0 else f"Round {p.draft_round}, {p.draft_year}",
        "college": p.college,
    }


COLUMNS = [
    {"name": "pos", "label": "Pos", "field": "pos_sort", "sortable": True, "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "sortable": True, "align": "right"},
    {"name": "exp", "label": "Exp", "field": "exp", "sortable": True, "align": "right",
     ":format": 'v => v === 0 ? "R" : v'},
    {"name": "height", "label": "Height", "field": "height", "sortable": True, "align": "right",
     ":format": 'v => Math.floor(v / 12) + "-" + (v % 12)'},
    {"name": "weight", "label": "Weight", "field": "weight", "sortable": True, "align": "right"},
    {"name": "ovr", "label": "Overall", "field": "ovr", "sortable": True, "align": "left"},
    {"name": "pot", "label": "Potential", "field": "pot", "sortable": True, "align": "left"},
    {"name": "draft", "label": "Drafted", "field": "draft_sort", "sortable": True, "align": "left"},
    {"name": "college", "label": "College", "field": "college", "sortable": True, "align": "left"},
]


# ---------------------------------------------------------------------------
# Player report (right-hand panel)
# ---------------------------------------------------------------------------

def injury_history_html(league, p):
    """Health now, and 'Past injuries: View record': hover it for every injury
    he's had (like FOF8's), closing when the mouse leaves."""
    status = injury_text(p.id)
    rows = season.injury_history(league, p.id)
    last = p.name.split()[-1]
    now = f"{escape(last)} is currently healthy." if not status else f"{escape(last)}: {escape(status)}."
    if not rows:
        record = '<span class="legend">None</span>'
    else:
        lines = []
        for r in rows:
            name = injuries.name(r["kind"])
            if r["how"] in ("aggravated", "re-injured"):
                name += f" ({r['how']})"
            w = r["weeks"]
            missed = ("Played through" if w <= 0 else "Rest of season" if w >= injuries.SEASON_ENDING_WEEKS
                      else f"{w} game{'s' if w != 1 else ''}")
            team = league.team(r["team"]).abbrev if r["team"] else "-"
            lines.append(f'<tr><td class="l">{r["season"]}</td><td class="l">{escape(r["game"])}</td>'
                         f'<td class="l">{team}</td><td class="l">{escape(name)}</td><td>{missed}</td></tr>')
        record = (f'<span class="inj-hist"><span class="inj-hist-link">View record ({len(rows)})</span>'
                  f'<span class="inj-hist-box"><table class="box-table"><thead><tr><th class="l">Year</th>'
                  f'<th class="l">Game</th><th class="l">Team</th><th class="l">Injury</th><th>Missed</th>'
                  f'</tr></thead><tbody>{"".join(lines)}</tbody></table>'
                  f'<span class="inj-hist-now">{now}</span></span></span>')
    health = escape(status) if status else "Healthy"
    return (f'<div class="facts inj-hist-row"><span class="k">Health</span><span class="num">{health}</span>'
            f'<span class="k">Past injuries</span><span class="num">{record}</span></div>')


def contract_text(league, pid):
    """'$12.5M a year through 2029 (3 seasons left; $20.0M guaranteed); this season's cap hit $10.1M'
    or 'None'."""
    c = (getattr(league, "contracts", None) or {}).get(pid)
    if not c:
        return "None"
    from engine import contracts as C
    last = C.last_season(c)
    left = C.years_left(c, league.season)
    kind = {"practice": "practice squad deal", "futures": "reserve/future deal", "tag": "franchise tag",
            "tender": "tender", "rookie": "rookie deal", "minimum": "minimum deal"}.get(c["kind"], "")
    n = len(c["years"])
    gtd = f", {C.fmt_money(c['guaranteed'])} guaranteed" if c.get("guaranteed") else ""
    return (f"{C.fmt_money(c['apy'])} a year through {last} ({left} season{'s' if left != 1 else ''} left of a "
            f"{n}-year deal signed in {c.get('signed', '?')}{gtd})"
            + (f", {kind}" if kind else "") + f"; cap hit this season {C.fmt_money(C.cap_hit(league, c))}")


def report_html(p, with_stats=True):
    """The player report. with_stats=False leaves out this season's stats
    (the full player card shows the whole career instead)."""
    league = state.league
    today = date(league.season, 9, 1)
    team_id, where = transactions.team_of(league, p.id)
    team_txt = league.team(team_id).name if team_id else "Free agent"
    if where == "practice":
        team_txt += " (practice squad)"
    elif where == "reserve":
        team_txt += " (" + {"IR": "injured reserve", "PUP": "PUP list",
                            "PSIR": "practice squad injured list"}[league.reserve[p.id]["list"]] + ")"
    elif team_id is None and any(w["pid"] == p.id for w in league.waivers):
        team_txt = "On waivers"
    pos_name = pos.POSITIONS[p.position][0]
    pos_style = theme.position_style(p.position)
    exp = "Rookie" if p.experience == 0 else f"{p.experience} season{'s' if p.experience != 1 else ''}"
    ovr, pot = shown(p.overall(), p.position), shown(p.overall("potential"), p.position)

    facts = [
        ("Team", team_txt),
        ("Contract", contract_text(league, p.id)),
        ("Size", fmt.size(p.height, p.weight) + (f"  ({p.build_note})" if p.build_note else "")),
        ("Age", f"{p.age(today)} (born {p.birth_date:%b %d, %Y})"),
        ("Experience", exp),
        ("College", p.college),
        ("Drafted", "Undrafted" if p.draft_round == 0 else f"Round {p.draft_round}, {p.draft_year}"),
        ("Hometown", p.hometown),
    ]
    from engine import awards
    honors = awards.honors_summary(league, p.id)
    if honors:
        facts.append(("Honors", honors))          # awards.py: MVP, All-Pro, Pro Bowl, Player of the Week...
    combine =[(fmt.DRILL_LABELS[d][0], fmt.drill(d, p.combine[d])) for d in pos.COMBINE_DRILLS]
    combine += [("Intelligence test", f"{p.intel_test} out of 50"),
                ("Position drill", str(p.position_drill))]
    traits = [("Loyalty", p.loyalty), ("Wants a winner", p.wants_winner),
              ("Leadership", p.leadership), ("Volatility", p.volatility),
              ("Popularity", p.popularity)]

    def fact_grid(rows):
        return '<div class="facts">' + "".join(
            f'<span class="k">{escape(k)}</span><span class="num">{escape(v)}</span>' for k, v in rows
        ) + "</div>"

    def skill_row(label, cur, potential):
        cur, potential = shown(cur, p.position), shown(potential, p.position)
        word, color = rating_cell(cur)
        return (f'<div class="skill-row"><span>{escape(label)}</span>'
                f'<div class="skill-bar" title="Now {cur}, potential {potential}">'
                f'<div class="pot" style="width:{potential}%"></div>'
                f'<div class="cur" style="width:{cur}%;background:{color}"></div></div>'
                f'<span class="num">{word} ({cur}) / {potential}</span></div>')

    skills = "".join(
        skill_row(pos.SKILLS[s][0], *p.skills[s])
        for s, _w in pos.POSITIONS[p.position][1]
        if s not in pos.HIDDEN_SKILLS)          # hidden ratings never appear on screen

    ovr_word, ovr_color = rating_cell(ovr)
    return f"""
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
      <span class="pos-tag" style="{pos_style}">{p.position}</span>
      <span class="legend">{escape(pos_name)}</span>
    </div>
    <h2 style="margin-top:6px">{escape(p.name)}</h2>
    <div class="rating" style="margin-top:8px;font-size:17px">
      <span class="swatch" style="background:{ovr_color};width:14px;height:14px"></span>
      <span>Overall {ovr_word} ({ovr})</span>
      <span class="legend">potential {pot}</span>
    </div>
    <h3>Bio</h3>{fact_grid(facts)}
    {injury_history_html(league, p)}
    <h3>Ratings</h3>
    {skills}
    <div class="legend" style="margin-top:6px">Dark bar: ability now. Light bar: room to grow.</div>
    {f"<h3>Season stats</h3>{player_stats_html(league, p.id)}" if with_stats else ""}
    <h3>Combine</h3>{fact_grid(combine)}
    <h3>Personality</h3>{fact_grid([(k, fmt.trait(v)) for k, v in traits])}
    """


# ---------------------------------------------------------------------------
# Roster moves: counts and warnings, and the list of moves
# ---------------------------------------------------------------------------

def roster_notice_html():
    """Above the table: the team's roster counts; for your team, anything that
    needs a move and any moves your staff made when you simmed ahead."""
    league = state.league
    tid = state.team_id
    if tid == FREE_AGENTS:
        waived = len(league.waivers)
        return (f'<div class="legend">{len(league.free_agents())} free agents'
                + (f'; {waived} players on waivers this week (they become free agents if nobody claims them)'
                   if waived else '') + '. Free agents with a red tag are hurt: nobody signs them until they heal.</div>')
    n53 = len(league.team_players(tid))
    nps = len(transactions.practice_players(league, tid))
    nres = len(transactions.reserve_players(league, tid))
    if transactions.in_camp(league):
        counts = (f'Training camp roster: <b>{n53}</b> of {transactions.roster_rules.CAMP_LIMIT} &nbsp;·&nbsp; '
                  f'Injured reserve: <b>{nres}</b> &nbsp;·&nbsp; Final cuts after the last preseason game: '
                  f'{transactions.ROSTER_SIZE} make the team, then practice squads ({transactions.PRACTICE_SQUAD_SIZE}) '
                  f'are signed')
    else:
        counts = (f'53-man roster: <b>{n53}</b> of {transactions.ROSTER_SIZE} &nbsp;·&nbsp; Practice squad: '
                  f'<b>{nps}</b> of {transactions.PRACTICE_SQUAD_SIZE} &nbsp;·&nbsp; Reserve lists: <b>{nres}</b> '
                  f'&nbsp;·&nbsp; Back from injured reserve this season: <b>{league.ir_returns.get(tid, 0)}</b> of '
                  f'{transactions.IR_RETURNS}')
    if tid != league.user_team_id:
        return f'<div class="legend">{counts}</div>'
    parts = [f'<div class="legend" style="margin-bottom:6px">{counts}</div>']
    staff = getattr(league, "staff_moves", None) or []
    if staff:
        items = "".join(f"<li>{escape(_move_text(t))}</li>" for t in staff)
        parts.append(f'<div class="notice" style="margin-bottom:6px"><b>Your staff made these moves</b> so your '
                     f'team could take the field (you simmed ahead):<ul style="margin:4px 0 0 18px">{items}</ul></div>')
    warnings = transactions.roster_warnings(league, league.injuries, tid) if season.user_moves_open(league) else []
    if warnings:
        items = "".join(f"<li>{escape(w)}</li>" for w in warnings)
        parts.append(f'<div class="notice"><b>Roster to-do</b> (click a player for his moves):'
                     f'<ul style="margin:4px 0 0 18px">{items}</ul></div>')
    return "".join(parts)


def _move_text(t):
    league = state.league
    p = league.player(t["pid"])
    team = league.team(t["team"]).abbrev if t["team"] else ""
    note = f" ({t['note']})" if t.get("note") else ""
    return f"{t['when']}: {team} {t['move'].lower()} {p.position} {p.first_name} {p.last_name}{note}"


def moves_html():
    """Every roster move this season, newest first (your team's, or every
    team's from the Free agents view)."""
    league = state.league
    tid = state.team_id
    rows = [t for t in reversed(league.transactions) if t["season"] == league.season
            and (tid == FREE_AGENTS or t["team"] == tid)]
    if not rows:
        return '<div class="legend">No roster moves yet this season.</div>'
    lines = []
    for t in rows[:600]:
        p = league.player(t["pid"])
        team = league.team(t["team"]).abbrev if t["team"] else ""
        lines.append(f'<tr><td>{escape(t["when"])}</td><td>{team}</td><td>{escape(t["move"])}</td>'
                     f'<td><span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span> '
                     f'<a class="plink" href="/player/{p.id}">{escape(p.name)}</a></td>'
                     f'<td class="legend">{escape(t.get("note") or "")}</td></tr>')
    title = "Every team's roster moves" if tid == FREE_AGENTS else f"{league.team(tid).name}: roster moves"
    return (f'<h3 style="margin-top:0">{escape(title)}, {league.season}</h3>'
            f'<table class="move-list"><thead><tr><th class="l">When</th><th class="l">Team</th>'
            f'<th class="l">Move</th><th class="l">Player</th><th class="l">Note</th></tr></thead>'
            f'<tbody>{"".join(lines)}</tbody></table>')


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

def build_roster_tab():
    """Builds the Roster tab. Returns a function that refreshes it."""
    league = state.league
    today = date(league.season, 9, 1)

    if not hasattr(state, "roster_group"):
        state.roster_group = GROUPS[0]

    # ---- Your roster: counts, warnings, moves your staff made -----------
    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def notices():
            requests = season.staff_requests(league) if state.team_id == league.user_team_id else []
            if requests:
                # Your staff checks in before a bigger-than-normal move (Blake: no surprise cuts).
                with ui.element("div").classes("notice").style("margin-bottom:6px"):
                    ui.html("<b>Your staff wants to check with you first</b> (nothing happens until you "
                            "answer; unanswered requests are dropped when the week is played):", sanitize=False)
                    for i, r in enumerate(requests):
                        with ui.row().classes("items-center gap-2 mt-1"):
                            ui.label(r["why"])
                            ui.button("Approve", on_click=lambda i=i: answer(i, True)) \
                                .props("no-caps unelevated dense color=green-10")
                            ui.button("Decline", on_click=lambda i=i: answer(i, False)) \
                                .props("no-caps outline dense color=green-10")
            html = roster_notice_html()
            if html:
                ui.html(html, sanitize=False)
        notices()

    # ---- Filters --------------------------------------------------------
    with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
        ui.toggle(GROUPS, value=state.roster_group, on_change=lambda e: set_filter(group=e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9") \
            .tooltip("Roster: the 53 who can play (up to 90 in training camp, until final cuts after the "
                     "preseason). Practice squad: 16 who practice and can be promoted or elevated for a game. "
                     "Reserve lists: injured reserve and PUP. Moves: every signing, release and injured "
                     "reserve move this season.")
        ui.toggle(["All", "Offense", "Defense", "Special teams"], value=state.unit,
                  on_change=lambda e: set_filter(unit=e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")
        position_select = ui.select(["All positions"] + POSITION_ORDER, value=state.position,
                                    on_change=lambda e: set_filter(position=e.value)) \
            .props("dense outlined options-dense").classes("w-44")
        ui.html('<span class="key"><span class="starter-dot">●</span> Starter on the depth chart '
                '<span class="captain-star">★</span> Captain</span>', sanitize=False)
        ui.label("Click a player to see his full report.").classes("legend")
        if state.team_id == league.user_team_id:
            ui.toggle({False: "I run my practice squad", True: "Staff runs practice squad + injury cover"},
                      value=transactions.staff_runs_practice_squad(league),
                      on_change=lambda e: set_ps_staff(e.value)) \
                .props("no-caps unelevated dense toggle-color=green-10 color=white text-color=grey-9") \
                .tooltip("You: your moves are never overridden, but whatever you leave undone your staff "
                         "finishes when the week is simmed (fills empty spots, moves injured players to the "
                         "practice squad injured list, calls players up when you're short on game day). "
                         "Staff: your staff also swaps in better young players now and then, elevates "
                         "players for depth, fills open spots on your 53, and when injuries leave a position "
                         "thin signs or promotes a player for now and lets a spare player at another position "
                         "go, like an AI team. Injured reserve, activations and other cuts stay yours.")

    # ---- Table and report ----------------------------------------------
    with ui.row().classes("w-full px-8 py-4 gap-5 no-wrap items-start"):
        table = ui.table(rows=[], columns=COLUMNS, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": "pos"}) \
            .props("flat dense virtual-scroll hide-bottom") \
            .classes("roster-table").style("flex: 1 1 0; min-width: 0; height: calc(100vh - 300px)")
        table.add_slot("body-cell-pos", r"""
            <q-td :props="props">
              <span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span>
              <span v-if="props.row.starter" class="starter-dot" title="Starter"> ●</span>
              <span v-if="props.row.captain" class="captain-star" title="Captain"> ★</span>
            </q-td>""")
        for key in ("ovr", "pot"):
            table.add_slot(f"body-cell-{key}", f"""
                <q-td :props="props">
                  <span class="rating num">
                    <span class="swatch" :style="{{background: props.row.{key}_color}}"></span>
                    {{{{ props.row.{key}_word }}}} ({{{{ props.row.{key} }}}})
                  </span>
                </q-td>""")
        table.add_slot("body-cell-name", r"""
            <q-td :props="props">{{ props.row.name }}<span v-if="props.row.inj" :class="props.row.inj_class"
              :title="props.row.inj">{{ props.row.inj_code }}</span><span v-if="props.row.cut" class="cut-tag"
              title="Your staff would cut him at final cuts (unless you cut someone else or mark him Keep)">CUT</span><span
              v-if="props.row.keep" class="cut-tag keep" title="You marked him: your staff won't cut him">KEEP</span></q-td>""")
        table.add_slot("body-cell-draft", r"""
            <q-td :props="props">{{ props.row.draft_text }}</q-td>""")
        table.on("rowClick", lambda e: select_player(e.args[1]["id"]))
        moves_box = ui.element("div").classes("report px-6 py-5") \
            .style("flex: 1 1 0; min-width: 0; height: calc(100vh - 300px); overflow-y: auto")
        with moves_box:
            @ui.refreshable
            def moves_view():
                ui.html(moves_html(), sanitize=False)
            moves_view()

        with ui.element("div").classes("report px-6 py-5") \
                .style("flex: 0 0 470px; height: calc(100vh - 300px); overflow-y: auto"):
            @ui.refreshable
            def report():
                p = next((x for x in league.players if x.id == state.selected_id), None)
                if p is None:
                    ui.label("No player selected").classes("condensed text-2xl")
                    ui.label("Click any row in the table to see that player's bio, "
                             "ratings, combine results and personality.").classes("legend")
                else:
                    ui.button("Open player card", icon="badge",
                              on_click=lambda pid=p.id: popups.show_player(pid)) \
                        .props("no-caps outline color=green-10 dense").classes("mb-2") \
                        .tooltip("Full card: bio, ratings and every season of his career stats")
                    options = season.user_options(league, p.id)
                    if options:
                        with ui.element("div").classes("move-actions"):
                            for action, label, tip in options:
                                ui.button(label, on_click=lambda a=action, pid=p.id: do_move(a, pid)) \
                                    .props("no-caps unelevated color=green-10 dense").tooltip(tip)
                    ui.html(report_html(p), sanitize=False)
            report()

    # ---- Actions --------------------------------------------------------
    def refresh():
        moves = state.roster_group == "Moves"
        table.set_visibility(not moves)
        moves_box.set_visibility(moves)
        if moves:
            moves_view.refresh()
        players = current_players()
        starters = team_starter_ids(state.team_id)
        captains = set(league.captains.get(state.team_id, {}).values())
        cuts, keeps = set(), set()
        if state.team_id == league.user_team_id and transactions.in_camp(league) and state.roster_group == GROUPS[0]:
            cuts = {p.id for p in transactions.staff_cut_list(league, league.injuries, state.team_id)}
            keeps = transactions.camp_keeps(league)
        table.rows = [player_row(p, today, starters, captains, cuts, keeps) for p in players]
        mark_selected()
        report.refresh()
        notices.refresh()

    def answer(index, approve):
        done, msg = season.answer_staff_request(league, index, approve)
        ui.notify(msg, type="positive" if done else "warning", position="top")
        mark_changed()
        refresh()

    def set_ps_staff(value):
        league.settings["ps_staff"] = bool(value)
        mark_changed()
        ui.notify("Your staff runs your practice squad and short-term injury signings." if value
                  else "You run your practice squad (your staff only finishes what you leave undone).",
                  position="top")

    def do_move(action, pid):
        done, msg = season.user_move(league, action, pid)
        ui.notify(msg, type="positive" if done else "warning", position="top")
        if done:
            mark_changed()
            refresh()

    def mark_selected():
        sid = state.selected_id if state.selected_id is not None else -1
        table.props(f':table-row-class-fn="row => row.id === {sid} ? \'is-selected\' : \'\'"')

    def set_filter(unit=None, position=None, group=None):
        if group is not None:
            state.roster_group = group
        if unit is not None:
            state.unit = unit
            state.position = "All positions"
            options = ["All positions"] + (POSITION_ORDER if unit == "All" else theme.UNITS[unit])
            position_select.set_options(options, value="All positions")
        if position is not None:
            state.position = position
        refresh()

    def select_player(player_id):
        state.selected_id = player_id
        mark_selected()
        report.refresh()

    refresh()
    return refresh
