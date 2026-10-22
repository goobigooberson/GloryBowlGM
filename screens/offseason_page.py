# offseason_page.py
# The Offseason report (/offseason): what happened between the Glory Bowl
# and the new season. Your team first (retirements, draft picks, undrafted
# signings, releases), then the league: notable retirements and the whole
# draft, round by round. Click any player for his card.

from html import escape

from nicegui import ui

from engine.scale import shown
from .state import state
from . import theme


def _player_line(league, pid, extra=""):
    p = league.player(pid)
    return (f'<a href="/player/{pid}" style="color:inherit;text-decoration:none">'
            f'<span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span> '
            f'{escape(p.name)}</a> <span class="legend">{escape(extra)}</span>')


def build_offseason_page():
    league = state.league
    ui.add_head_html(theme.HEAD_HTML)
    ui.query("body").style(f"background:{theme.CHALK}")
    with ui.element("div").classes("field-band w-full px-8 pt-4 pb-5"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Front Office Football  |  {league.name}").classes("condensed text-lg opacity-90")
            ui.button("Back to the game", icon="arrow_back", on_click=lambda: ui.navigate.to("/game")) \
                .props("outline color=white no-caps")
        report_header(league)
    report_body(league)


def report_header(league):
    """The title lines (drawn inside the green band). On the game screen the
    report opens as a pop-up (popups.py); /offseason is the same as a page."""
    rep = league.offseason_report
    ui.label(f"{rep['season'] - 1}-{rep['season'] % 100:02d} offseason" if rep else "Offseason") \
        .classes("team-name mt-3")
    ui.label("Retirements, free agency, the draft, undrafted signings and training camp, so far. Your "
             "staff makes your draft picks for now (the draft screens come later).").classes("opacity-80")


def report_body(league):
    rep = league.offseason_report
    if not rep:
        ui.label("No offseason has happened in this league yet.").classes("px-8 py-6 legend")
        return
    you = league.user_team_id
    with ui.row().classes("w-full px-8 py-4 gap-6 no-wrap items-start"):
        # ---- Your team ----------------------------------------------------
        with ui.element("div").classes("report px-6 py-5").style("flex: 0 0 520px"):
            team = league.team(you).name if you else "Your team"
            ui.label(team).classes("condensed").style("font-size:28px;font-weight:700")

            def section(title, items):
                ui.label(title).classes("panel-heading")
                if not items:
                    ui.label("None").classes("legend")
                for html in items:
                    ui.html(html, sanitize=False).classes("edit-row w-full")

            section("Retired", [_player_line(league, pid, f"age {_age(league, pid)}, {league.player(pid).experience} seasons")
                                for pid, tid in rep["retired"] if tid == you])
            from engine import contracts as C
            fa = rep.get("fa_signings", [])
            section("Signed in free agency", [_player_line(league, s["pid"], f"wave {s['wave']}  ·  "
                                                           f"{s['years']} yr, {C.fmt_money(s['apy'])} a year")
                                              for s in fa if s["team"] == you])
            section("Left in free agency", [_player_line(league, s["pid"], f"to {league.team(s['team']).abbrev}  ·  "
                                                         f"{s['years']} yr, {C.fmt_money(s['apy'])} a year")
                                            for s in fa if s.get("former") == you and s["team"] != you])
            section("Draft picks", [_player_line(league, d["pid"], f"round {d['round']}, pick {d['pick']}  ·  "
                                                 f"{league.player(d['pid']).college}  ·  overall {shown(league.player(d['pid']).overall(), league.player(d['pid']).position)}, "
                                                 f"potential {shown(league.player(d['pid']).overall('potential'), league.player(d['pid']).position)}")
                                    for d in rep["draft"] if d["team"] == you])
            section("Undrafted rookies signed", [_player_line(league, pid, league.player(pid).college)
                                                 for pid, tid in rep["udfa"] if tid == you])
            if rep["cuts"]:          # offseasons before Oct 23 cut to 53 here
                section("Released", [_player_line(league, pid, f"overall {shown(league.player(pid).overall(), league.player(pid).position)}")
                                     for pid, tid in rep["cuts"] if tid == you])
            section("Signed for training camp (by your staff; cut anyone you like)",
                    [_player_line(league, pid, "free agent") for pid, tid in rep["signed"] if tid == you])
            ui.label("Cuts to 53 come after the last preseason game (final cuts): the Roster tab marks the "
                     "players your staff would cut.").classes("legend mt-1")
        # ---- League ---------------------------------------------------------
        with ui.element("div").classes("report px-6 py-5").style("flex: 1 1 0; min-width: 0"):
            ui.label("Around the league").classes("condensed").style("font-size:28px;font-weight:700")
            ui.label("Notable retirements").classes("panel-heading")
            # The best players to retire (by rating, then how long they lasted).
            notable = sorted((pid for pid, _t in rep["retired"]),
                             key=lambda pid: (-league.player(pid).overall(), -league.player(pid).experience))[:15]
            for pid in notable:
                p = league.player(pid)
                ui.html(_player_line(league, pid, f"overall {shown(p.overall(), p.position)}  ·  age {_age(league, pid)}  ·  "
                                     f"{p.experience} seasons  ·  {_career_games(league, pid)} career games here"),
                        sanitize=False).classes("edit-row w-full")
            ui.label(f"{len(rep['retired'])} players retired in all; {len(rep['fa_left'])} unsigned free agents "
                     "left the league.").classes("legend mt-1")
            ui.label("The draft").classes("panel-heading")
            for rnd in range(1, 8):
                picks = [d for d in rep["draft"] if d["round"] == rnd]
                rows = "".join(
                    f"<tr{' style=\"background:#FFF6CF;font-weight:600\"' if d['team'] == you else ''}>"
                    f"<td>{d['pick']}</td><td class='l'>{league.team(d['team']).abbrev}</td>"
                    f"<td class='l'>{_player_line(league, d['pid'])}</td>"
                    f"<td class='l'>{escape(league.player(d['pid']).college)}</td></tr>" for d in picks)
                ui.html(f'<div class="box-title">Round {rnd}</div><table class="box-table"><thead><tr>'
                        f'<th>Pick</th><th class="l">Team</th><th class="l">Player</th><th class="l">College</th>'
                        f'</tr></thead><tbody>{rows}</tbody></table>', sanitize=False).classes("w-full")


def _age(league, pid):
    """Age during his last season for retired players, else this season."""
    from datetime import date
    p = league.player(pid)
    return p.age(date(p.retired if p.retired is not None else league.season, 9, 1))


def _career_games(league, pid):
    return int(sum(r["stats"].get("gp", 0) for r in league.career if r["pid"] == pid and r["phase"] == "regular"))
