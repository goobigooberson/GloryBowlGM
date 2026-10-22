# stats_page.py
# The Stats tab:
#   Team summary: one team's record, results, team and opponent stats with
#     league ranks, and every player's stats (like FOF8's Team Summary).
#   League leaders: the top 5 in every major stat (rate stats need the
#     NFL's minimum amount of play; see engine/stats.py).
#   Player stats: every player's season line by category (passing,
#     rushing, receiving, defense, kicking, punting, returns), sortable.
#   Team stats: every team's offense and defense per game, sortable.
# A switch picks the regular season or the playoffs (the NFL keeps them
# apart). Preseason games never count.

from html import escape

from nicegui import ui

from engine import stats as ST
from .state import state
from . import popups, theme

# Player stats tables: (column key, heading, format). Keys are raw totals
# or derived numbers from engine/stats.derived.
CATEGORY_COLUMNS = {
    "Passing": ("pass_att", [("pass_cmp", "Cmp", "int"), ("att", "Att", "int"), ("cmp_pct", "Cmp%", "1f"),
                             ("pass_yds", "Yds", "int"), ("ypa", "Y/A", "1f"), ("pass_td", "TD", "int"),
                             ("pass_int", "Int", "int"), ("sacked", "Sck", "int"), ("rating", "Rating", "1f"),
                             ("pass_long", "Long", "int")]),
    "Rushing": ("rush_att", [("rush_att", "Att", "int"), ("rush_yds", "Yds", "int"), ("ypc", "Y/C", "1f"),
                             ("rush_td", "TD", "int"), ("rush_long", "Long", "int"), ("fum_lost", "Fum lost", "int")]),
    "Receiving": ("targets", [("targets", "Tgt", "int"), ("rec", "Rec", "int"), ("rec_yds", "Yds", "int"),
                              ("ypr", "Y/R", "1f"), ("rec_td", "TD", "int"), ("rec_long", "Long", "int"),
                              ("rec_yac", "YAC", "int"), ("drops", "Drops", "int")]),
    "Defense": ("tackles", [("tackles", "Tkl", "int"), ("tkl", "Solo", "int"), ("ast", "Ast", "int"),
                            ("sacks", "Sacks", "1f"), ("tfl", "TFL", "1f"), ("qb_hits", "QB hits", "int"),
                            ("def_int", "Int", "int"), ("pd", "PD", "int"), ("ff", "FF", "int"),
                            ("fr", "FR", "int"), ("def_td", "TD", "int")]),
    "Kicking": ("fga", [("fgm", "FGM", "int"), ("fga", "FGA", "int"), ("fg_pct", "FG%", "1f"),
                        ("fg_long", "Long", "int"), ("xpm", "XPM", "int"), ("xpa", "XPA", "int"),
                        ("points", "Pts", "int")]),
    "Punting": ("punts", [("punts", "Punts", "int"), ("punt_yds", "Yds", "int"), ("punt_avg", "Avg", "1f"),
                          ("punt_in20", "In 20", "int"), ("punt_tb", "TB", "int"), ("punt_long", "Long", "int")]),
    "Returns": ("returns", [("kr", "KR", "int"), ("kr_yds", "KR yds", "int"), ("kr_avg", "KR avg", "1f"),
                            ("pr", "PR", "int"), ("pr_yds", "PR yds", "int"), ("pr_avg", "PR avg", "1f"),
                            ("ret_td", "TD", "int")]),
}


def _val(s, key):
    if key == "att":
        return ST.pass_att(s)
    if key == "returns":
        return s.get("kr", 0) + s.get("pr", 0)
    return ST.value(s, key)


def _fmt(v, how):
    return ST.fmt_value(v, how) if how != "int" else str(int(round(v)))


def player_stat_lines(league, pid):
    """A player's season lines for the player report: [(phase title,
    category, [(heading, value text)])] for every category he has stats in."""
    out = []
    for phase, title in ((ST.REGULAR, f"{league.season} regular season"), (ST.PLAYOFFS, f"{league.season} playoffs")):
        s = ST.player_totals(league, phase).get(pid)
        if not s:
            continue
        for cat, (need, cols) in CATEGORY_COLUMNS.items():
            if _val(s, need) > 0:
                out.append((title, cat, [("G", str(int(s["gp"])))] +
                            [(head, _fmt(_val(s, key), how)) for key, head, how in cols]))
    return out


def player_stats_html(league, pid):
    lines = player_stat_lines(league, pid)
    if not lines:
        return '<div class="legend">No regular-season or playoff stats yet (preseason games don\'t count).</div>'
    html = []
    for title, cat, cells in lines:
        head = "".join(f"<th>{escape(h)}</th>" for h, _v in cells)
        body = "".join(f"<td>{escape(v)}</td>" for _h, v in cells)
        html.append(f'<div class="box-title">{escape(cat)} · {escape(title)}</div>'
                    f'<table class="box-table"><thead><tr>{head}</tr></thead><tbody><tr>{body}</tr></tbody></table>')
    return "".join(html)


def _rank_text(rank):
    r, tied = rank
    return f"{r}{' (T)' if tied else ''}"


def _game_label(league, row):
    from engine import playoffs as po
    if row["kind"] == "playoffs":
        return {1: "Wild Card", 2: "Divisional", 3: "Conf. champ.", 5: po.championship_name(league)}.get(row["week"], "")
    return f"Week {row['week']}"


def team_summary_html(league, team_id, phase):
    """FOF8-style Team Summary: record and history, game log, team and
    opponent stats with league ranks, and every player's stats for this team."""
    s = ST.team_summary(league, team_id, phase)
    team = league.team(team_id)
    rec = s["record"]
    h = s["history"]
    # ---- Left: the season, history, game log
    rows = [("Season", str(league.season)),
            ("Record", f"{rec['w']}-{rec['l']}" + (f"-{rec['t']}" if rec["t"] else "")),
            ("Points for / against", f"{rec['pf']} / {rec['pa']}")]
    if s["seed"]:
        rows.append(("Playoff seed", f"#{s['seed']}"))
    if s["playoff_result"] and s["seed"]:
        rows.append(("Playoffs", s["playoff_result"]))
    if h["seasons"]:
        rows += [("Past seasons", str(h["seasons"])),
                 ("All-time record", f"{h['w'] + rec['w']}-{h['l'] + rec['l']}"
                                     + (f"-{h['t'] + rec['t']}" if h["t"] + rec["t"] else "")),
                 ("Playoff trips", str(h["playoffs"])),
                 (f"{'Glory Bowl'} titles", str(h["titles"]))]
    facts = "".join(f'<tr><td class="l">{escape(k)}</td><td>{escape(v)}</td></tr>' for k, v in rows)
    log = []
    for g in s["log"]:
        opp = league.team(g["opp"]).abbrev
        where = "vs" if g["home"] or g["neutral"] else "at"
        if g["played"]:
            color = {"W": "#1B5E20", "L": "#B71C1C", "T": "#555"}[g["result"]]
            score = (f'<span style="color:{color};font-weight:700">{g["result"]}</span> '
                     f'{g["pf"]}-{g["pa"]}{" OT" if g["ot"] else ""}')
        else:
            score = '<span class="legend">-</span>'
        log.append(f'<tr><td class="l">{escape(_game_label(league, g))}</td><td class="l">{where} '
                   f'{popups.team_link(league.team(g["opp"]), opp)}</td>'
                   f'<td class="l">{score}</td></tr>')
    left = (f'<div class="box-title" style="margin-top:0">{escape(team.name)}</div>'
            f'<table class="box-table"><tbody>{facts}</tbody></table>'
            f'<div class="box-title">Games</div>'
            f'<table class="box-table"><thead><tr><th class="l">Week</th><th class="l">Opponent</th>'
            f'<th class="l">Result</th></tr></thead><tbody>{"".join(log)}</tbody></table>')

    # ---- Middle: team and opponent stats, league rank (1 = best)
    def side(title, lines):
        body = "".join(
            f'<tr><td class="l">{escape(label)}</td>'
            f'<td>{(f"{v:+.0f}" if how == "+int" else ST.fmt_value(v, how))}</td>'
            f'<td>{_rank_text(rank)}</td></tr>' for label, v, how, rank in lines)
        return (f'<div class="box-title">{escape(title)}</div><table class="box-table"><thead><tr>'
                f'<th class="l">Stat</th><th>Value</th><th>Rank</th></tr></thead><tbody>{body}</tbody></table>')
    if s["offense"]:
        middle = (side(f"{team.abbrev} offense", s["offense"]) + side("Opponents (what the defense allowed)", s["defense"])
                  + '<div class="legend" style="margin-top:6px">Rank among the league\'s teams (in the playoffs '
                    'view, among playoff teams), 1 = best (for the defense, 1 = allowed the least; sacks and '
                    'takeaways: the most). (T) = tied.</div>')
    else:
        middle = '<div class="legend">No games played yet.</div>'

    # ---- Right: every player's stats for this team
    by_id = {p.id: p for p in league.players}
    sort_key = {"Passing": "pass_yds", "Rushing": "rush_yds", "Receiving": "rec_yds", "Defense": "tackles",
                "Kicking": "fgm", "Punting": "punts", "Returns": "kr_yds"}
    right = []
    for cat, (need, cols) in CATEGORY_COLUMNS.items():
        lines = [(pid, st) for pid, st in s["players"].items() if _val(st, need) > 0 and pid in by_id]
        if not lines:
            continue
        lines.sort(key=lambda x: -_val(x[1], sort_key[cat]))
        head = "".join(f"<th>{escape(hd)}</th>" for _k, hd, _h in cols)
        body = []
        for pid, st in lines:
            p = by_id[pid]
            cells = "".join(f"<td>{_fmt(_val(st, k), how)}</td>" for k, _hd, how in cols)
            body.append(f'<tr><td class="l"><span class="pos-tag" style="{theme.position_style(p.position)}">'
                        f'{p.position}</span> <a href="/player/{pid}" class="plink">{escape(p.name)}</a></td>'
                        f'<td>{int(st["gp"])}</td>{cells}</tr>')
        right.append(f'<div class="box-title">{escape(cat)}</div><table class="box-table"><thead><tr>'
                     f'<th class="l">Player</th><th>G</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>')
    if not right:
        right = ['<div class="legend">No player stats yet.</div>']
    return (f'<div style="display:grid;grid-template-columns:minmax(260px,300px) minmax(340px,400px) 1fr;'
            f'gap:18px;width:100%;align-items:start">'
            f'<div class="menu-panel" style="padding:10px 14px">{left}</div>'
            f'<div class="menu-panel" style="padding:10px 14px">{middle}</div>'
            f'<div class="menu-panel" style="padding:10px 14px;overflow-x:auto">{"".join(right)}'
            f'<div class="legend" style="margin-top:6px">Click a player for his card.</div></div></div>')


def build_stats_tab():
    """Builds the Stats tab. Returns a function that refreshes it."""
    league = state.league
    view = {"mode": "Team summary", "phase": ST.REGULAR, "category": "Passing", "team": "all",
            "summary_team": league.user_team_id or league.teams[0].id}
    team_opts = {"all": "All teams", **{t.id: t.name for t in sorted(league.teams, key=lambda t: t.name)}}
    one_team_opts = {t.id: t.name + (" (your team)" if t.id == league.user_team_id else "")
                     for t in sorted(league.teams, key=lambda t: t.name)}

    with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
        ui.toggle(["Team summary", "League leaders", "Player stats", "Team stats"], value=view["mode"],
                  on_change=lambda e: set_view(mode=e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")

        @ui.refreshable
        def controls():
            has_playoffs = bool(ST.team_games(league, ST.PLAYOFFS))
            ui.toggle({ST.REGULAR: "Regular season", ST.PLAYOFFS: "Playoffs"}, value=view["phase"],
                      on_change=lambda e: set_view(phase=e.value)) \
                .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9"
                       + ("" if has_playoffs else " disable"))
            if view["mode"] == "Team summary":
                ui.select(one_team_opts, value=view["summary_team"], label="Team",
                          on_change=lambda e: set_view(summary_team=e.value)) \
                    .props("dense outlined options-dense").classes("w-64")
            elif view["mode"] == "Player stats":
                ui.select(list(CATEGORY_COLUMNS), value=view["category"], label="Category",
                          on_change=lambda e: set_view(category=e.value)) \
                    .props("dense outlined options-dense").classes("w-40")
                ui.select(team_opts, value=view["team"], label="Team",
                          on_change=lambda e: set_view(team=e.value)) \
                    .props("dense outlined options-dense").classes("w-56")
                ui.label("Click a column heading to sort.").classes("legend")
            elif view["mode"] == "League leaders":
                ui.label("Rate stats (rating, yards per carry...) need the NFL's minimum: 14 pass attempts, "
                         "6.25 carries or 1.875 catches per team game.").classes("legend")
        controls()

    body_col = ui.column().classes("w-full px-8 py-4 gap-3")

    @ui.refreshable
    def body():
        if view["mode"] == "Team summary":
            # Shown even before any games: the schedule and franchise history.
            ui.html(team_summary_html(league, view["summary_team"], view["phase"]), sanitize=False).classes("w-full")
            return
        if not ST.team_games(league, view["phase"]):
            ui.label("No games played yet." if view["phase"] == ST.REGULAR else "No playoff games yet.") \
                .classes("condensed text-2xl")
            ui.label("Stats count regular-season and playoff games only; preseason games don't count.") \
                .classes("legend")
            return
        if view["mode"] == "League leaders":
            leaders_view()
        elif view["mode"] == "Player stats":
            players_view()
        else:
            teams_view()

    def leaders_view():
        mine = league.user_team_id
        with ui.element("div").style("display:grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); "
                                     "gap: 14px; width:100%"):
            for cat, stats in ST.LEADER_CATEGORIES.items():
                for key, label, how, per_game, min_of, _hi in stats:
                    rows = ST.leaders(league, key, view["phase"], n=5, per_game_min=per_game, min_of=min_of)
                    lines = []
                    for i, (p, tid, v) in enumerate(rows, start=1):
                        team = league.team(tid)
                        cls = ' style="background:#FFF6CF;font-weight:600"' if tid == mine else ""
                        lines.append(f'<tr{cls}><td>{i}</td><td class="l"><span class="pos-tag" '
                                     f'style="{theme.position_style(p.position)}">{p.position}</span> '
                                     f'{popups.player_link(p)}</td><td class="l">{popups.team_link(team, team.abbrev)}</td>'
                                     f'<td><b>{ST.fmt_value(v, how)}</b></td></tr>')
                    if not lines:
                        lines.append('<tr><td colspan="4" class="l legend">Nobody qualifies yet</td></tr>')
                    ui.html(f'<div class="menu-panel" style="padding:10px 14px">'
                            f'<div class="box-title" style="margin-top:0">{escape(label)}</div>'
                            f'<table class="box-table"><tbody>{"".join(lines)}</tbody></table></div>',
                            sanitize=False)

    def players_view():
        need, cols = CATEGORY_COLUMNS[view["category"]]
        totals = ST.player_totals(league, view["phase"])
        by_id = {p.id: p for p in league.players}
        rows = []
        for pid, s in totals.items():
            p = by_id.get(pid)
            if p is None or _val(s, need) <= 0:
                continue
            if view["team"] != "all" and s["team"] != view["team"]:
                continue
            row = {"id": pid, "name": p.name, "pos": p.position, "pos_style": theme.position_style(p.position),
                   "team": league.team(s["team"]).abbrev, "gp": int(s["gp"]),
                   "mine": s["team"] == league.user_team_id}
            for key, _head, how in cols:
                v = _val(s, key)
                row[key] = round(v, 1) if how != "int" else int(round(v))
            rows.append(row)
        sort_key = {"Passing": "pass_yds", "Rushing": "rush_yds", "Receiving": "rec_yds", "Defense": "tackles",
                    "Kicking": "fgm", "Punting": "punts", "Returns": "kr_yds"}[view["category"]]
        columns = [{"name": "name", "label": "Player", "field": "name", "sortable": True, "align": "left"},
                   {"name": "team", "label": "Team", "field": "team", "sortable": True, "align": "left"},
                   {"name": "gp", "label": "G", "field": "gp", "sortable": True}]
        columns += [{"name": key, "label": head, "field": key, "sortable": True} for key, head, _how in cols]
        table = ui.table(rows=rows, columns=columns, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": sort_key, "descending": True}) \
            .props("flat dense virtual-scroll hide-bottom").classes("roster-table w-full") \
            .style("height: calc(100vh - 340px)")
        table.add_slot("body-cell-name", r"""
            <q-td :props="props" :style="props.row.mine ? 'background:#FFF6CF;font-weight:600' : ''">
              <span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span>
              <a class="plink pname" :href="'/player/' + props.row.id">{{ props.row.name }}</a>
            </q-td>""")
        table.on("rowClick", lambda e: popups.show_player(e.args[1]["id"]))
        ui.label(f"{len(rows)} players. Your team's players are highlighted. Click a player for his card.") \
            .classes("legend")

    def teams_view():
        tt = ST.team_totals(league, view["phase"])
        rows = []
        for t in league.teams:
            r = tt[t.id]
            g = r["g"]
            if not g:
                continue
            o, d = r["off"], r["def"]

            def pg(x):
                return round(x / g, 1)
            rows.append({
                "id": t.id, "team": t.name, "g": g, "mine": t.id == league.user_team_id,
                "pf": pg(r["pf"]), "pa": pg(r["pa"]),
                "yds": pg(o["rush_yds"] + o["pass_yds"] - o["sacked_yds"]),
                "pass": pg(o["pass_yds"] - o["sacked_yds"]), "rush": pg(o["rush_yds"]),
                "to": int(o["int_thrown"] + o["fum_lost"]),
                "yds_a": pg(d["rush_yds"] + d["pass_yds"] - d["sacked_yds"]),
                "pass_a": pg(d["pass_yds"] - d["sacked_yds"]), "rush_a": pg(d["rush_yds"]),
                "take": int(d["int_thrown"] + d["fum_lost"]), "sacks": int(d["sacked"]),
                "third": round(100 * o["third_conv"] / o["third_att"], 1) if o["third_att"] else 0.0,
            })
        heads = [("team", "Team"), ("g", "G"), ("pf", "Pts/G"), ("pa", "Opp pts/G"), ("yds", "Yds/G"),
                 ("pass", "Pass/G"), ("rush", "Rush/G"), ("third", "3rd down %"), ("to", "Giveaways"),
                 ("yds_a", "Yds allowed/G"), ("pass_a", "Pass allowed/G"), ("rush_a", "Rush allowed/G"),
                 ("take", "Takeaways"), ("sacks", "Sacks")]
        columns = [{"name": k, "label": h, "field": k, "sortable": True, "align": "left" if k == "team" else "right"}
                   for k, h in heads]
        table = ui.table(rows=rows, columns=columns, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": "pf", "descending": True}) \
            .props("flat dense hide-bottom").classes("roster-table w-full")
        table.add_slot("body-cell-team", r"""
            <q-td :props="props" :style="props.row.mine ? 'background:#FFF6CF;font-weight:600' : ''">
              <a class="tlink pname" :href="'/team/' + props.row.id">{{ props.row.team }}</a></q-td>""")
        table.on("rowClick", lambda e: popups.open_team(e.args[1]["id"]))
        ui.label("Per game. Click a team for its window. Yards are net (sack yardage taken off passing).").classes("legend")

    def set_view(**kw):
        view.update(kw)
        controls.refresh()
        body.refresh()

    def refresh():
        controls.refresh()
        body.refresh()

    with body_col:
        body()
    return refresh
