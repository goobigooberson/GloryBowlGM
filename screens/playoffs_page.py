# playoffs_page.py
# The Playoffs tab: the bracket. Each conference's seven seeds and its games
# round by round (Wild Card, Divisional, Conference championship), then the
# Glory Bowl. Click a played game to open its summary in the Schedule tab.
# Before the regular season ends it explains how the field is decided.

from html import escape

from nicegui import ui

from engine import awards as A
from engine import playoffs as po
from engine import season as S
from .state import state


def build_playoffs_tab(on_open_summary=None):
    """Builds the Playoffs tab. Returns a function that refreshes it."""
    league = state.league

    @ui.refreshable
    def body():
        with ui.column().classes("w-full px-8 py-4 gap-3"):
            if not league.playoff_seeds:
                ui.label("The playoff field is set after the last regular-season week").classes("condensed text-2xl")
                ui.label("7 teams per conference: the 4 division winners (seeds 1-4, by record) and the 3 best "
                         "other teams (wild cards, seeds 5-7). Only the #1 seed gets a first-round bye. Ties "
                         "are broken with the NFL's tiebreakers. Rounds: Wild Card, Divisional, Conference "
                         f"championship, a week off, then the {po.championship_name(league)}.").classes("legend")
                return
            champ = po.champion(league)
            if champ:
                ui.label(f"{po.championship_name(league)} champion: {league.team(champ).name}") \
                    .classes("condensed text-3xl").style("color: var(--turf)")
            rec = S.records(league)
            with ui.row().classes("w-full gap-6 no-wrap items-start"):
                for conf in sorted(league.playoff_seeds):
                    with ui.column().classes("gap-2").style("flex: 1 1 0; min-width: 0"):
                        ui.label(f"{conf} Conference").classes("depth-unit").style("margin-top:0")
                        seeds_html = []
                        for i, tid in enumerate(league.playoff_seeds[conf], start=1):
                            t = league.team(tid)
                            how = "division winner" if i <= 4 else "wild card"
                            mine = ' class="mine"' if tid == league.user_team_id else ""
                            out = any(g["played"] and po.loser(g) == tid for g in league.playoffs)
                            name = f"<s>{escape(t.name)}</s>" if out else escape(t.name)
                            seeds_html.append(f'<tr{mine}><td>{i}</td><td style="text-align:left">{name}</td>'
                                              f'<td>{S.record_text(rec[tid])}</td><td style="text-align:left">{how}</td></tr>')
                        ui.html('<table class="standings"><caption>Seeds</caption><thead><tr><th>#</th>'
                                '<th style="text-align:left">Team</th><th>Record</th>'
                                '<th style="text-align:left">How</th></tr></thead>'
                                f'<tbody>{"".join(seeds_html)}</tbody></table>', sanitize=False).classes("w-full")
                        for rnd in (1, 2, 3):
                            games = [g for g in league.playoffs if g["week"] == rnd
                                     and league.team(g["home"]).conference == conf]
                            ui.label(po.ROUND_NAMES[rnd]).classes("box-title")
                            if not games:
                                ui.label("Not set yet").classes("legend")
                            for g in games:
                                game_row(g)
            pb = A.records(league, "pro_bowl_games", league.season)
            if pb:
                sc = pb[0]["score"]
                ui.label("Pro Bowl (the week off): " + ", ".join(f"{c} {v}" for c, v in
                                                                  sorted(sc.items(), key=lambda kv: -kv[1]))
                         + "  ·  rosters, replacements and MVPs in the Awards tab").classes("legend")
            gb = [g for g in league.playoffs if g["week"] == 5]
            ui.label(po.championship_name(league) + f"  ·  {S.site_text(league, {'kind': 'glory_bowl'})}") \
                .classes("depth-unit")
            if not gb:
                ui.label("The two conference champions meet after a week off.").classes("legend")
            for g in gb:
                game_row(g)

    def game_row(g):
        h, a = league.team(g["home"]), league.team(g["away"])
        sh, sa = po.seed_of(league, h.id), po.seed_of(league, a.id)
        mine = league.user_team_id in (g["home"], g["away"])
        joiner = "vs" if g.get("neutral") else "at"
        if g["played"]:
            aw = "win" if g["away_score"] > g["home_score"] else ""
            hw = "win" if g["home_score"] > g["away_score"] else ""
            score = f'{g["away_score"]} - {g["home_score"]}'
            note = "Final" + (" (OT)" if g["overtime"] else "") + "  ·  Game summary"
        else:
            aw = hw = ""
            score = joiner
            note = "Not played yet"
        row = ui.html(f'<div class="sched-row{" mine" if mine else ""}">'
                      f'<span class="{aw}"><span class="legend">#{sa}</span> {escape(a.name)}</span>'
                      f'<span class="score num">{score}</span>'
                      f'<span class="{hw}"><span class="legend">#{sh}</span> {escape(h.name)}</span>'
                      f'<span class="legend">{note}</span></div>', sanitize=False).classes("w-full")
        if g["played"] and on_open_summary:
            row.on("click", lambda _e, gid=g["id"]: on_open_summary(gid))

    body()
    return body.refresh
