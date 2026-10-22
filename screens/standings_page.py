# standings_page.py
# The Standings tab: every division, both conferences side by side, with
# the columns fans expect (W, L, T, Pct, points for/against, home, away,
# division and conference records, streak). Your team is highlighted.

from html import escape

from nicegui import ui

from engine import playoffs as po
from engine import season as S
from .popups import team_link
from .state import state


def _rec(x):
    w, l, t = x
    return f"{w}-{l}" + (f"-{t}" if t else "")


def _pct(r):
    p = r["pct"]
    return "1.000" if p >= 1 else f"{p:.3f}".lstrip("0") if r["w"] + r["l"] + r["t"] else ".000"


def division_table(league, name, team_ids, rec):
    seeded = bool(league.playoff_seeds)
    cols = ("Team", "W", "L", "T", "Pct", "PF", "PA", "Net", "Home", "Away", "Div", "Conf", "Streak") \
        + (("Seed",) if seeded else ())
    head = "".join(f"<th>{h}</th>" for h in cols)
    rows = []
    for tid in team_ids:
        r = rec[tid]
        team = league.team(tid)
        net = r["pf"] - r["pa"]
        mine = ' class="mine"' if tid == league.user_team_id else ""
        seed = ""
        if seeded:
            s = po.seed_of(league, tid)
            seed = f"<td>{s if s else '-'}</td>"
        rows.append(f"<tr{mine}><td>{team_link(team)}</td><td>{r['w']}</td><td>{r['l']}</td><td>{r['t']}</td>"
                    f"<td>{_pct(r)}</td><td>{r['pf']}</td><td>{r['pa']}</td><td>{net:+d}</td>"
                    f"<td>{_rec(r['home'])}</td><td>{_rec(r['away'])}</td><td>{_rec(r['div'])}</td>"
                    f"<td>{_rec(r['conf'])}</td><td>{r['streak']}</td>{seed}</tr>")
    return (f'<table class="standings"><caption>{escape(name)}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def build_standings_tab():
    """Builds the Standings tab. Returns a function that refreshes it."""
    league = state.league

    @ui.refreshable
    def tables():
        rec = S.records(league)
        stand = S.division_standings(league, rec)
        played = sum(g["played"] for g in league.schedule)
        with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
            if played == 0:
                ui.label("No games played yet.").classes("legend")
            else:
                ui.label("Ties are broken with the NFL's tiebreakers: head-to-head, division record, "
                         "common games, conference record, strength of victory, strength of schedule, "
                         "net points." + (" Seed = playoff seed (1-4 division winners, 5-7 wild cards)."
                                          if league.playoff_seeds else "")).classes("legend")
        with ui.row().classes("w-full px-8 py-3 gap-6 no-wrap items-start"):
            for conf, divs in stand.items():
                with ui.column().classes("gap-0").style("flex: 1 1 0; min-width: 0"):
                    ui.label(f"{conf} Conference").classes("depth-unit").style("margin-top:0")
                    ui.html("".join(division_table(league, name, ids, rec) for name, ids in divs.items()),
                            sanitize=False).classes("w-full")
    tables()
    return tables.refresh
