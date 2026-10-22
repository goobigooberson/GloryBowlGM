# counts_page.py
# The Position counts tab: how many players a team has at each position and
# position group, who's active on game day, and the minimum required.

from html import escape

from nicegui import ui

from engine import roster_rules as rules
from . import theme
from .state import state, FREE_AGENTS


def build_counts_tab():
    """Builds the Position counts tab. Returns a function that refreshes it."""
    league = state.league

    with ui.row().classes("w-full px-8 py-4 gap-6 no-wrap items-start"):
        with ui.column().classes("gap-2").style("flex: 0 0 640px"):
            @ui.refreshable
            def table():
                if state.team_id == FREE_AGENTS:
                    ui.label("Free agents aren't a team").classes("condensed text-2xl")
                    ui.label("Pick a team from the Team list at the top.").classes("legend")
                    return
                roster = league.team_players(state.team_id)
                active = rules.game_day_actives(roster, league.depth_charts.get(state.team_id, {}))
                rows = rules.distribution(roster, active)
                body = []
                for r in rows:
                    if len(r["positions"]) == 1:
                        swatch = (f'<span class="count-swatch" '
                                  f'style="background:{theme.POSITION_COLORS[r["positions"][0]]}"></span>')
                    else:
                        swatch = '<span class="count-swatch" style="background:transparent"></span>'
                    classes = []
                    if r["is_group"]:
                        classes.append("count-group")
                    if r["short"]:
                        classes.append("count-short")
                    flag = ' <span class="count-flag">below minimum</span>' if r["short"] else ""
                    body.append(
                        f'<tr class="{" ".join(classes)}"><td>{swatch}{escape(r["label"])}{flag}</td>'
                        f'<td class="num">{r["active"]}</td><td class="num">{r["required"]}</td>'
                        f'<td class="num">{r["on_roster"]}</td></tr>')
                ui.html('<table class="counts-table"><thead><tr><th>Position</th>'
                        '<th>Active</th><th>Required</th><th>On roster</th></tr></thead>'
                        f'<tbody>{"".join(body)}</tbody></table>', sanitize=False).classes("w-full")

                from engine import transactions
                problems = rules.roster_problems(roster, active, transactions.roster_limit(league))
                if problems:
                    for note in problems:
                        ui.label(note).classes("depth-warning w-full")
                else:
                    ui.label("This roster meets every game-day minimum.").classes("legend")
            table()

        with ui.column().classes("gap-2 report px-6 py-5").style("flex: 0 1 460px"):
            ui.label("How roster rules work").classes("panel-heading").style("margin-top:0")
            ui.html(f"""
                <p>A team carries up to <b>{rules.ROSTER_LIMIT}</b> players (up to {rules.CAMP_LIMIT} in
                training camp and the preseason, until final cuts). On game day,
                <b>{rules.ACTIVE_LIMIT}</b> of them are active if at least {rules.OL_FOR_FULL_LIMIT}
                are offensive linemen ({rules.ACTIVE_LIMIT_FEW_OL} otherwise), as in the real NFL, and
                the rest sit out. One inactive quarterback is the <b>emergency third QB</b>: he can
                come in only if both active quarterbacks are knocked out of the game.</p>
                <p>The active players must include at least the <b>Required</b> number at each
                position and position group, so every formation can be filled and an injury
                doesn't leave a hole. Rows in bold are groups that add up several positions.</p>
                <p><b>Active</b> is chosen automatically for now: the least-needed backups sit
                out. You'll be able to pick your own inactives later, and injured players will
                always sit out.</p>
                <p>These rules also stop the AI from building lopsided rosters when signing and
                cutting players.</p>""", sanitize=False).classes("legend counts-help")

    def refresh():
        table.refresh()

    return refresh
