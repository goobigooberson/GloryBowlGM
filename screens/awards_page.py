# awards_page.py
# The Awards tab: each season's official honors in one place. A season picker
# and five views: Season awards (MVP and the rest, with the media vote), All-
# Pro teams, the Pro Bowl (rosters by conference, replacements, the game),
# Players of the Week and Month, and History (every season's winners).
# Everything comes from engine/awards.py. Click a name to open his player card.

from html import escape

from nicegui import ui

from engine import awards as A
from engine import playoffs as po
from engine.news_awards import season_phrase
from .state import state

VIEWS = {"season": "Season awards", "allpro": "All-Pro", "probowl": "Pro Bowl", "weekly": "Players of the Week",
         "history": "History"}


def _link(league, pid, team=None):
    try:
        p = league.player(pid)
    except KeyError:
        return "?"
    name = f'<a class="plink" href="/player/{pid}">{escape(p.name)}</a>'
    if team is not None and team == league.user_team_id:
        name = f"<b>{name}</b>"
    return name


def _abbr(league, tid):
    try:
        return league.team(tid).abbrev
    except Exception:
        return ""


def build_awards_tab():
    """Builds the Awards tab. Returns a function that refreshes it."""
    league = state.league
    for k, v in {"awards_view": "season", "awards_season": None}.items():
        if not hasattr(state, k):
            setattr(state, k, v)

    def set_value(name, value):
        setattr(state, name, value)
        body.refresh()

    @ui.refreshable
    def body():
        A.ensure(league)
        seasons = sorted(set(A.seasons(league)) | {league.season}, reverse=True)
        season = state.awards_season if state.awards_season in seasons else league.season
        with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
            ui.toggle(VIEWS, value=state.awards_view, on_change=lambda e: set_value("awards_view", e.value)) \
                .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")
            if state.awards_view != "history":
                ui.select({s: str(s) for s in seasons}, label="Season", value=season,
                          on_change=lambda e: set_value("awards_season", e.value)) \
                    .props("dense outlined options-dense").classes("w-32")
        with ui.column().classes("w-full px-8 py-4 gap-3"):
            {"season": season_view, "allpro": all_pro_view, "probowl": pro_bowl_view, "weekly": weekly_view,
             "history": history_view}[state.awards_view](season)
            ui.label("Names in bold are your players. Votes: a 50-member media panel (season awards: each voter "
                     "ranks five, 10-5-3-2-1 points; All-Pro: each voter picks first and second teams). Pro Bowl: "
                     "fans, players and coaches each count for a third.").classes("legend mt-2")

    # ---- Season awards ----------------------------------------------------
    def season_view(season):
        rows = A.winners(league, season)
        n = league.settings.get("season_games", 17)
        if not rows:
            ui.label("The season awards are voted on the regular season and announced the week of the "
                     f"{po.CHAMPIONSHIP}.").classes("condensed text-xl")
            watch = A.records(league, "mvp_watch", season)
            if watch:
                w = watch[-1]
                ui.label(f"MVP watch after Week {w['week']} (the media's top five)").classes("panel-heading")
                items = []
                for i, (pid, tid, line, rec) in enumerate(w["top"], start=1):
                    p = league.player(pid)
                    items.append(f"<tr><td>{i}</td><td class='l'>{_link(league, pid, tid)}</td>"
                                 f"<td class='l'>{p.position}, {_abbr(league, tid)} ({rec[0]}-{rec[1]}"
                                 f"{'-' + str(rec[2]) if rec[2] else ''})</td>"
                                 f"<td class='l'>{escape(season_phrase(p, line))}</td></tr>")
                ui.html("<table class='box-table' style='max-width:900px'><thead><tr><th>#</th><th class='l'>Player"
                        "</th><th class='l'>Team</th><th class='l'>Season so far</th></tr></thead><tbody>"
                        + "".join(items) + "</tbody></table>", sanitize=False).classes("w-full")
            return
        with ui.row().classes("w-full gap-4 items-stretch"):
            for award, name, _short in A.SEASON_AWARDS:
                r = rows.get(award)
                with ui.element("div").classes("report px-5 py-4").style("flex: 1 1 420px; min-width: 380px"):
                    ui.label(name).classes("panel-heading")
                    if not r:
                        note = next((x["text"] for x in A.records(league, "notes", season)
                                     if x.get("award") == award), "Not awarded.")
                        ui.label(note).classes("legend")
                        continue
                    p = league.player(r["pid"])
                    extra = ""
                    if award == "cpoy":
                        extra = " (back from injury)" if r.get("kind") == "injury" else " (back from a lost season)"
                    ui.html(f"<div style='font-size:20px;font-weight:700'>{_link(league, r['pid'], r['team'])}</div>"
                            f"<div class='legend'>{p.position}, {escape(league.team(r['team']).name)}{extra}</div>"
                            f"<div style='margin:4px 0 8px'>{escape(season_phrase(p, r['line'], n).capitalize())}"
                            f"</div>", sanitize=False)
                    vt = "".join(f"<tr><td class='l'>{_link(league, pid, tid)}</td><td class='l'>{_abbr(league, tid)}"
                                 f"</td><td>{f1}</td><td>{pts}</td></tr>" for pid, tid, f1, pts in r["votes"])
                    ui.html("<table class='box-table'><thead><tr><th class='l'>Vote</th><th class='l'>Team</th>"
                            "<th>1st place</th><th>Points</th></tr></thead><tbody>" + vt + "</tbody></table>",
                            sanitize=False).classes("w-full")
        gb = A.records(league, "gb_mvp", season)
        if gb:
            r = gb[0]
            p = league.player(r["pid"])
            first = league.settings.get("first_season", season)
            ui.html(f"<div class='panel-heading'>{po.CHAMPIONSHIP} {po.roman(season - first + 1)} MVP</div>"
                    f"<div>{_link(league, r['pid'], r['team'])} ({p.position}, {_abbr(league, r['team'])})</div>",
                    sanitize=False)

    # ---- All-Pro --------------------------------------------------------------
    def all_pro_view(season):
        rows = A.records(league, "all_pro", season)
        if not rows:
            ui.label("The All-Pro teams are announced at the start of the playoffs.").classes("condensed text-xl")
            return
        body_rows = []
        for spot, label, _n, _pool in A.ALL_PRO_SPOTS:
            cells = []
            for team_no in (1, 2):
                picks = [r for r in rows if r["spot"] == spot and r["team_no"] == team_no]
                cells.append("<br>".join(
                    f"{_link(league, r['pid'], r['team'])} <span class='legend'>{_abbr(league, r['team'])}"
                    + (f" · {r['firsts']} votes" if team_no == 1 else "") + "</span>" for r in picks))
            body_rows.append(f"<tr><td class='l'><b>{escape(label)}</b></td><td class='l'>{cells[0]}</td>"
                             f"<td class='l'>{cells[1]}</td></tr>")
        ui.html("<table class='box-table' style='max-width:1000px'><thead><tr><th class='l'>Position</th>"
                "<th class='l'>First team (first-team votes, of 50)</th><th class='l'>Second team</th></tr></thead>"
                "<tbody>" + "".join(body_rows) + "</tbody></table>", sanitize=False).classes("w-full")

    # ---- Pro Bowl -------------------------------------------------------------
    def pro_bowl_view(season):
        rows = A.records(league, "pro_bowl", season)
        if not rows:
            ui.label("Pro Bowl rosters are announced before the last week of the regular season: fans, players "
                     "and coaches each count for a third of the vote.").classes("condensed text-xl")
            return
        first = league.settings.get("first_season", season)
        gname = f"{po.CHAMPIONSHIP} {po.roman(season - first + 1)}"
        why = {"glory_bowl": f"playing in {gname}", "injured": "injured", "declined": "not playing"}
        games = A.records(league, "pro_bowl_games", season)
        if games:
            g = games[0]
            sc = g["score"]
            confs = sorted(sc, key=lambda c: -sc[c])
            mvps = []
            for k, label in (("mvp_off", "Offensive MVP"), ("mvp_def", "Defensive MVP")):
                if g.get(k):
                    mvps.append(f"{label}: {_link(league, g[k])}")
            ui.html(f"<div class='depth-unit' style='margin-top:0'>Pro Bowl: {confs[0]} {sc[confs[0]]}, "
                    f"{confs[1]} {sc[confs[1]]}{' (OT)' if g.get('overtime') else ''}</div>"
                    f"<div class='legend'>{escape(g['site'])} · {escape(g.get('weather', ''))}</div>"
                    f"<div>{' · '.join(mvps)}</div>"
                    f"<div class='legend'>Pro Bowl stats never count in season or career totals.</div>",
                    sanitize=False)
            ui.html(_pro_bowl_box(league, g), sanitize=False).classes("w-full")
        with ui.row().classes("w-full gap-6 no-wrap items-start"):
            for conf in sorted({r["conf"] for r in rows}):
                with ui.column().classes("gap-1").style("flex: 1 1 0; min-width: 0"):
                    ui.label(f"{conf} Conference").classes("depth-unit").style("margin-top:0")
                    trs = []
                    for spot, label, n, _st, _pool in A.PRO_BOWL_SPOTS:
                        group = sorted((r for r in rows if r["conf"] == conf and r["spot"] == spot),
                                       key=lambda r: r["rank"])
                        cells = []
                        for r in group:
                            if r["role"] == "selected":
                                tag = " ★" if r["starter"] else ""
                                note = f" <span class='legend'>({why[r['out']]})</span>" if r["out"] else ""
                                name = _link(league, r["pid"], r["team"])
                                if r["out"]:
                                    name = f"<s>{name}</s>"
                                cells.append(f"{name}{tag} <span class='legend'>{_abbr(league, r['team'])}</span>{note}")
                            elif r["added"]:
                                cells.append(f"{_link(league, r['pid'], r['team'])} <span class='legend'>"
                                             f"{_abbr(league, r['team'])} (added)</span>")
                        alts = [r for r in group if r["role"] == "alternate" and not r["added"]]
                        alt = ", ".join(f"{_link(league, r['pid'], r['team'])}" for r in alts[:3])
                        trs.append(f"<tr><td class='l'><b>{escape(label)}</b></td><td class='l'>{'<br>'.join(cells)}"
                                   f"</td><td class='l legend'>{alt}</td></tr>")
                    ui.html("<table class='box-table'><thead><tr><th class='l'>Position</th><th class='l'>Players "
                            "(★ starter)</th><th class='l'>Alternates</th></tr></thead><tbody>" + "".join(trs) +
                            "</tbody></table>", sanitize=False).classes("w-full")

    # ---- Players of the Week / Month -------------------------------------------
    def weekly_view(season):
        rows = A.records(league, "weekly", season)
        if not rows:
            ui.label("Players of the Week are named after each regular-season week.").classes("condensed text-xl")
            return
        confs = A.conferences(league)
        head = "".join(f"<th class='l'>{c[:4]}. {A.WEEKLY_KINDS[k].split()[0]}</th>" for c in confs
                       for k in A.WEEKLY_KINDS)
        trs = []
        for w in sorted({r["week"] for r in rows}):
            cells = []
            for c in confs:
                for k in A.WEEKLY_KINDS:
                    r = next((x for x in rows if x["week"] == w and x["conf"] == c and x["kind"] == k), None)
                    if r:
                        p = league.player(r["pid"])
                        cells.append(f"<td class='l'>{_link(league, r['pid'], r['team'])} <span class='legend'>"
                                     f"{p.position} {_abbr(league, r['team'])}</span></td>")
                    else:
                        cells.append("<td></td>")
            trs.append(f"<tr><td class='l'>Week {w}</td>{''.join(cells)}</tr>")
        ui.html("<table class='box-table'><thead><tr><th class='l'>Week</th>" + head + "</tr></thead><tbody>"
                + "".join(trs) + "</tbody></table>", sanitize=False).classes("w-full")
        months = A.records(league, "monthly", season)
        if months:
            ui.label("Players of the Month").classes("panel-heading")
            names = {"off": "Offense", "def": "Defense", "st": "Special teams", "orook": "Offensive rookie",
                     "drook": "Defensive rookie"}
            trs = []
            for m in A.MONTHS:
                for r in [x for x in months if x["month"] == m]:
                    p = league.player(r["pid"])
                    where = f"{r['conf']} " if r["conf"] else "League "
                    trs.append(f"<tr><td class='l'>{m}</td><td class='l'>{where}{names[r['kind']].lower()}</td>"
                               f"<td class='l'>{_link(league, r['pid'], r['team'])} <span class='legend'>"
                               f"{p.position} {_abbr(league, r['team'])}</span></td>"
                               f"<td class='l'>{escape(season_phrase(p, r['line']))}</td></tr>")
            ui.html("<table class='box-table'><thead><tr><th class='l'>Month</th><th class='l'>Award</th>"
                    "<th class='l'>Player</th><th class='l'>That month</th></tr></thead><tbody>" + "".join(trs)
                    + "</tbody></table>", sanitize=False).classes("w-full")

    # ---- History ---------------------------------------------------------------
    def history_view(_season):
        seasons = sorted({r["season"] for r in A.records(league, "season")}, reverse=True)
        if not seasons:
            ui.label("No season awards yet: the first ones come the week of the "
                     f"{po.championship_name(league)}.").classes("condensed text-xl")
            return
        first = league.settings.get("first_season", league.season)
        head = "".join(f"<th class='l'>{escape(short)}</th>" for _a, _n, short in A.SEASON_AWARDS)
        trs = []
        for s in seasons:
            w = A.winners(league, s)
            cells = "".join(
                f"<td class='l'>{_link(league, w[a]['pid'], w[a]['team'])} <span class='legend'>"
                f"{league.player(w[a]['pid']).position} {_abbr(league, w[a]['team'])}</span></td>" if a in w else
                "<td class='l legend'>-</td>" for a, _n, _s in A.SEASON_AWARDS)
            gb = A.records(league, "gb_mvp", s)
            champ = league.champions.get(s) or (po.champion(league) if s == league.season else None)
            gbc = (f"<td class='l'>{_link(league, gb[0]['pid'], gb[0]['team'])}</td>" if gb else "<td></td>")
            trs.append(f"<tr><td class='l'><b>{s}</b></td>{cells}{gbc}<td class='l'>"
                       f"{escape(league.team(champ).name) if champ else ''}</td></tr>")
        ui.html("<table class='box-table'><thead><tr><th class='l'>Season</th>" + head +
                f"<th class='l'>{po.CHAMPIONSHIP} MVP</th><th class='l'>Champion</th></tr></thead><tbody>"
                + "".join(trs) + "</tbody></table>", sanitize=False).classes("w-full")
        ui.label(f"Glory Bowl numbering starts with the league's first season ({first}).").classes("legend")

    body()
    return body.refresh


def _pro_bowl_box(league, g):
    """The Pro Bowl's top performers: passing, rushing, receiving, defense."""
    lines = []
    for pid_s, s in g["players"].items():
        try:
            p = league.player(int(pid_s))
        except (KeyError, ValueError):
            continue
        lines.append((p, s))
    out = []
    for title, key, fmt in (("Passing", "pass_yds", lambda s: f"{int(s.get('pass_cmp', 0))}/{int(s.get('pass_att', 0))}, "
                                                             f"{int(s.get('pass_yds', 0))} yds, {int(s.get('pass_td', 0))} TD, "
                                                             f"{int(s.get('pass_int', 0))} INT"),
                            ("Rushing", "rush_yds", lambda s: f"{int(s.get('rush_att', 0))} car, {int(s.get('rush_yds', 0))} yds, "
                                                             f"{int(s.get('rush_td', 0))} TD"),
                            ("Receiving", "rec_yds", lambda s: f"{int(s.get('rec', 0))} rec, {int(s.get('rec_yds', 0))} yds, "
                                                              f"{int(s.get('rec_td', 0))} TD"),
                            ("Defense", "sacks", lambda s: f"{s.get('sacks', 0):g} sacks, {int(s.get('def_int', 0))} INT, "
                                                          f"{int(s.get('tkl', 0) + s.get('ast', 0))} tkl")):
        top = sorted((x for x in lines if x[1].get(key)), key=lambda x: -x[1].get(key, 0))[:3]
        if key == "sacks":
            top = sorted(lines, key=lambda x: -(4 * x[1].get("sacks", 0) + 5 * x[1].get("def_int", 0)
                                                + 0.5 * (x[1].get("tkl", 0) + x[1].get("ast", 0))))[:3]
        if top:
            out.append(f"<td class='l' style='vertical-align:top'><b>{title}</b><br>" + "<br>".join(
                f"{_link(league, p.id)} <span class='legend'>{escape(s['conf'][:4])}.</span> {fmt(s)}"
                for p, s in top) + "</td>")
    return "<table class='box-table'><tr>" + "".join(out) + "</tr></table>"
