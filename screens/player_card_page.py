# player_card_page.py
# The full player card (like FOF8's): bio, ratings, combine and personality
# on the left; his whole career stats on the right. One table per stat
# category he has played in, a row per season (and per team if he played for
# more than one that year), the season in progress marked, and a Career
# totals row at the bottom. Regular season and playoffs are shown apart.
# Preseason games never count.
# On the game screen the card opens as a pop-up (popups.py); /player/{id} is
# the same card as its own page.

from html import escape

from nicegui import ui

from engine import awards as AW
from engine import stats as ST
from engine.scale import shown
from .state import state, injury_text
from . import theme
from .roster_page import report_html
from .stats_page import CATEGORY_COLUMNS, _val, _fmt


def career_table(league, pid, phase, cat):
    """HTML table for one category, or '' if he has nothing in it."""
    need, cols = CATEGORY_COLUMNS[cat]
    rows = [r for r in ST.career_lines(league, pid, phase) if _val(r["stats"], need) > 0]
    if not rows:
        return ""
    head = "<th class='l'>Year</th><th class='l'>Team</th><th>G</th>" + \
        "".join(f"<th>{escape(h)}</th>" for _k, h, _f in cols)
    body = []
    for r in rows:
        s = r["stats"]
        team = league.team(r["team"]).abbrev
        year = f"{r['season']}" + (" *" if r["current"] else "")
        body.append(f"<tr><td class='l'>{year}</td><td class='l'>{team}</td><td>{int(s.get('gp', 0))}</td>" +
                    "".join(f"<td>{_fmt(_val(s, k), how)}</td>" for k, _h, how in cols) + "</tr>")
    tot = ST.add_up([r["stats"] for r in rows])
    seasons = len({r["season"] for r in rows})
    body.append(f"<tr style='font-weight:700;border-top:2px solid var(--line)'><td class='l'>Career</td>"
                f"<td class='l'>{seasons} season{'s' if seasons != 1 else ''}</td><td>{int(tot.get('gp', 0))}</td>" +
                "".join(f"<td>{_fmt(_val(tot, k), how)}</td>" for k, _h, how in cols) + "</tr>")
    return (f'<div class="box-title">{escape(cat)}</div>'
            f'<table class="box-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>')


def build_player_card(pid):
    league = state.league
    p = next((x for x in league.players if x.id == pid), None)
    ui.add_head_html(theme.HEAD_HTML)
    ui.query("body").style(f"background:{theme.CHALK}")
    with ui.element("div").classes("field-band w-full px-8 pt-4 pb-5"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Front Office Football  |  {league.name}  |  Player card").classes("condensed text-lg opacity-90")
            ui.button("Back to the game", icon="arrow_back", on_click=lambda: ui.navigate.to("/game")) \
                .props("outline color=white no-caps")
        if p is None:
            ui.label("Player not found").classes("team-name mt-3")
            return
        card_header(league, p)
    card_body(league, p)


def card_header(league, p):
    """Position tag, name, team and injury (drawn inside the green band)."""
    from engine import transactions
    tid, where = transactions.team_of(league, p.id)
    if p.retired is not None:
        team = f"Retired after the {p.retired} season"
    else:
        team = league.team(tid).name if tid else "Free agent"
        if where == "practice":
            team += " (practice squad)"
        elif where == "reserve":
            team += " (reserve list)"
    with ui.row().classes("items-end gap-5 mt-3"):
        ui.html(f'<span class="pos-tag" style="{theme.position_style(p.position)};font-size:28px;'
                f'padding:4px 12px">{p.position}</span>', sanitize=False)
        with ui.column().classes("gap-0"):
            ui.label(p.name).classes("team-name")
            inj = injury_text(p.id)
            ui.label(team + (f"   ·   {inj}" if inj else "")).classes("opacity-80")


def card_body(league, p):
    """The report on the left; honors, career stats and ratings by season on the right."""
    with ui.row().classes("w-full px-8 py-4 gap-6 no-wrap items-start"):
        with ui.element("div").classes("report px-6 py-5").style("flex: 0 0 460px"):
            ui.html(report_html(p, with_stats=False), sanitize=False)
        with ui.element("div").classes("report px-6 py-5").style("flex: 1 1 0; min-width: 0; overflow-x: auto"):
            honors = AW.player_honors(league, p.id)
            if honors:
                ui.label("Awards and honors").classes("condensed").style("font-size:30px;font-weight:700;line-height:1.1")
                ui.label(AW.honors_summary(league, p.id)).classes("legend")
                rows = "".join(f"<tr><td class='l'>{season}</td><td class='l'>{escape(text)}</td></tr>"
                               for season, _sort, text in honors)
                ui.html(f'<table class="box-table" style="max-width:720px;margin-bottom:14px"><thead><tr>'
                        f'<th class="l">Season</th><th class="l">Honor</th></tr></thead><tbody>{rows}</tbody></table>',
                        sanitize=False)
            ui.label("Career stats").classes("condensed").style("font-size:30px;font-weight:700;line-height:1.1")
            ui.label("Regular season and playoffs are kept apart, as in the NFL; preseason games don't count. "
                     "* = season in progress.").classes("legend")
            any_stats = False
            for phase, title in ((ST.REGULAR, "Regular season"), (ST.PLAYOFFS, "Playoffs")):
                tables = "".join(career_table(league, p.id, phase, cat) for cat in CATEGORY_COLUMNS)
                if tables:
                    any_stats = True
                    ui.label(title).classes("panel-heading")
                    ui.html(tables, sanitize=False).classes("w-full")
            if not any_stats:
                ui.label("No regular-season or playoff stats yet.").classes("legend mt-3")
            hist = [r for r in league.rating_history if r["pid"] == p.id]
            if hist:
                ui.label("Ratings by season").classes("panel-heading")
                ui.label("Overall and potential at each training camp (the first row is when he joined the "
                         "league). Development happens at camp; see how his ceiling moved.").classes("legend")
                rows = "".join(f"<tr><td class='l'>{r['season']}</td><td>{shown(r['ovr'], p.position)}</td>"
                               f"<td>{shown(r['pot'], p.position)}</td></tr>"
                               for r in sorted(hist, key=lambda r: r["season"]))
                ui.html(f'<table class="box-table" style="max-width:360px"><thead><tr><th class="l">Season</th>'
                        f'<th>Overall</th><th>Potential</th></tr></thead><tbody>{rows}</tbody></table>',
                        sanitize=False)
