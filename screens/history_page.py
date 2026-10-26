# history_page.py
# League history, the record book and the Hall of Fame (Oct 25; FOF8's
# "reward loop"). Three pages in the League section and the team window's
# History tab:
#   - History: every finished season (champion, runner-up, MVP, best record),
#     each franchise's all-time record, and one season in full (every team's
#     finish, the award winners, the league's leaders).
#   - Records: single game, single season and career records (regular season
#     or playoffs; league-wide or one franchise's), team records, and the
#     all-time career leaders with filters (active or retired, position, team).
#   - Hall of Fame: its members by class, each year's vote, who's eligible next.
# Everything comes from engine/history.py and engine/hall_of_fame.py. Names
# open the player card and teams the team window (popups.player_link / team_link).

from html import escape

from nicegui import ui

from engine import awards as A
from engine import hall_of_fame as HOF
from engine import history as H
from engine import playoffs as po
from engine import stats as ST
from . import popups, theme
from .state import state

TOGGLE = "no-caps unelevated toggle-color=green-10 color=white text-color=grey-9"
SELECT = "dense outlined options-dense"
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------------------
# Small pieces
# ---------------------------------------------------------------------------

def _player(league, pid):
    try:
        return league.player(pid)
    except (KeyError, TypeError):
        return None


def _name(league, pid, tag=True, mark=True):
    """Position tag and linked name; 'HOF' after a Hall of Famer's name."""
    p = _player(league, pid)
    if p is None:
        return "?"
    out = (f'<span class="pos-tag" style="{theme.position_style(p.position)}">{p.position}</span> '
           if tag else "") + popups.player_link(p)
    if mark and HOF.member(league, pid):
        out += ' <span class="hof-mark" title="Hall of Fame">HOF</span>'
    return out


def _team(league, tid, abbrev=True):
    try:
        t = league.team(tid)
    except StopIteration:
        return ""
    return popups.team_link(t, t.abbrev if abbrev else t.name)


def _teams(league, tids):
    return ", ".join(_team(league, t) for t in tids)


def _record(h):
    return f"{h['w']}-{h['l']}" + (f"-{h['t']}" if h.get("t") else "")


def _table(head, rows, style=""):
    """head: [(text, left?)]; rows: lists of cell HTML (first `left` columns align left)."""
    th = "".join(f"<th class='l'>{escape(t)}</th>" if left else f"<th>{escape(t)}</th>" for t, left in head)
    body = "".join("<tr>" + "".join(f"<td class='l'>{c}</td>" if head[i][1] else f"<td>{c}</td>"
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table class='box-table' style='{style}'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _panel(title, inner, legend=""):
    return (f"<div class='report px-5 py-4' style='min-width:0'><div class='panel-heading' style='margin-top:0'>"
            f"{escape(title)}</div>{inner}" + (f"<div class='legend' style='margin-top:6px'>{legend}</div>"
                                                if legend else "") + "</div>")


def _grid(panels, min_px=420):
    return (f"<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax({min_px}px,1fr));gap:14px;"
            f"width:100%;align-items:start'>{''.join(panels)}</div>")


def _empty(title, text):
    return (f"<div class='report px-5 py-4'><div class='inspector-empty'><div class='inspector-empty-title'>"
            f"{escape(title)}</div><div>{escape(text)}</div></div></div>")


CSS = f"""
<style>
  .hof-mark {{ display:inline-block; font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:11px;
              letter-spacing:.04em; color:#5C4300; background:#F5D76E; border:1px solid #C9A227; border-radius:3px;
              padding:0 4px; line-height:15px; vertical-align:1px; }}
  .hof-badge {{ display:inline-block; font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:17px;
               letter-spacing:.03em; color:#3B2B00; background:linear-gradient(#F7DC7A,#E3B93A);
               border:1px solid #B48A12; border-radius:4px; padding:1px 10px; }}
  .hist-kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); border:1px solid #DCE2EA;
               border-radius:3px; background:#F8FAFC; margin-bottom:10px; }}
  .hist-kpis > div {{ padding:6px 12px; border-right:1px solid #DCE2EA; }}
  .hist-kpis > div:last-child {{ border-right:none; }}
  .hist-kpis .k {{ font-family:'Barlow Condensed',sans-serif; font-size:12px; font-weight:700; text-transform:uppercase;
                  letter-spacing:.04em; color:var(--ink-soft); }}
  .hist-kpis .v {{ font-family:'Barlow Condensed',sans-serif; font-size:24px; font-weight:700; line-height:1.05; }}
  .box-table tr.mine td {{ background:#FFF6CF !important; font-weight:600; }}
  .box-table tr.champ td {{ background:#FBF3D5; }}
</style>
"""


def _kpis(items):
    return "<div class='hist-kpis'>" + "".join(f"<div><div class='k'>{escape(k)}</div><div class='v'>{v}</div></div>"
                                                for k, v in items) + "</div>"


def _value(v, key):
    return ST.fmt_value(v, H.STAT_INFO[key][1])


# ---------------------------------------------------------------------------
# History: champions, franchises, one season
# ---------------------------------------------------------------------------

def champions_html(league):
    seasons = H.seasons(league)
    if not seasons:
        return _empty("No finished seasons yet", "Each season's champion, awards and leaders are kept here "
                                                 "once its " + po.CHAMPIONSHIP + " is played and the offseason starts.")
    rows = []
    for s in seasons:
        sm = H.season_summary(league, s)
        best = max(sm["teams"], key=lambda h: (h["w"] + 0.5 * h["t"], h["pf"] - h["pa"]))
        mvp = sm["awards"].get("mvp")
        gb = sm["gb_mvp"]
        champ = sm["champion"]
        rows.append([f"<b>{s}</b>", escape(sm["name"]),
                     f"<b>{_team(league, champ, False)}</b>" if champ is not None else "",
                     _team(league, sm["runner_up"], False) if sm["runner_up"] is not None else "",
                     _name(league, mvp["pid"]) + f" ({_team(league, mvp['team'])})" if mvp else "",
                     _name(league, gb["pid"]) if gb else "",
                     f"{_team(league, best['team'])} {_record(best)}"])
    return _panel("Champions", _table([("Season", True), ("Game", True), ("Champion", True), ("Runner-up", True),
                                       ("MVP", True), (f"{po.CHAMPIONSHIP} MVP", True), ("Best record", True)], rows),
                  "Click a season in the Season view for every team's finish, the award winners and the leaders. "
                  "HOF = in the Hall of Fame.")


def franchises_html(league):
    if not H.seasons(league):
        return ""
    rows = []
    for t in league.teams:
        f = H.franchise(league, t.id)["totals"]
        g = f["w"] + f["l"] + f["t"]
        pct = (f["w"] + 0.5 * f["t"]) / g if g else 0
        rows.append((len(f["titles"]), pct, t, f))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2].name))
    cells = []
    for titles, pct, t, f in rows:
        cls = " class='mine'" if t.id == league.user_team_id else ""
        cells.append((cls, [_team(league, t.id, False), f"{f['w']}-{f['l']}" + (f"-{f['t']}" if f["t"] else ""),
                            f"{pct:.3f}".lstrip("0"), str(f["playoffs"]), f"{f['playoff_w']}-{f['playoff_l']}",
                            str(f["division_titles"]), str(len(f["finals"]) + titles),
                            ", ".join(str(s) for s in f["titles"]) or "-"]))
    head = [("Team", True), ("All-time record", False), ("Win %", False), ("Playoffs", False),
            ("Playoff record", False), ("Division titles", False), (f"{po.CHAMPIONSHIP} games", False),
            ("Titles", True)]
    th = "".join(f"<th class='l'>{escape(t)}</th>" if left else f"<th>{escape(t)}</th>" for t, left in head)
    body = "".join(f"<tr{cls}>" + "".join(f"<td class='l'>{c}</td>" if head[i][1] else f"<td>{c}</td>"
                                         for i, c in enumerate(r)) + "</tr>" for cls, r in cells)
    return _panel("Franchises, all time", f"<table class='box-table'><thead><tr>{th}</tr></thead><tbody>{body}"
                  "</tbody></table>", "Finished seasons only. Click a team for its window; its History tab has "
                  "the year by year, best players and franchise records.")


LEADER_LABELS = {"pass_yds": "Passing yards", "pass_td": "Passing touchdowns", "rush_yds": "Rushing yards",
                 "rec": "Receptions", "rec_yds": "Receiving yards", "sacks": "Sacks", "def_int": "Interceptions",
                 "tackles": "Tackles", "fgm": "Field goals made"}


def season_html(league, season):
    sm = H.season_summary(league, season)
    champ, runner = sm["champion"], sm["runner_up"]
    top = []
    if champ is not None:
        gb = next((h for h in sm["teams"] if h["team"] == champ), None)
        top.append(f"<div style='font-size:13px;color:var(--ink-soft)'>{escape(sm['name'])} champion</div>"
                   f"<div class='condensed' style='font-size:34px;font-weight:700;line-height:1.05'>"
                   f"{_team(league, champ, False)}</div>"
                   f"<div class='legend'>{_record(gb) if gb else ''} in the regular season"
                   + (f"; beat the {_team(league, runner, False)}" if runner is not None else "") + "</div>")
    lines = []
    for h in sm["teams"]:
        t = league.team(h["team"])
        cls = " class='mine'" if t.id == league.user_team_id else (" class='champ'" if t.id == champ else "")
        lines.append((cls, [_team(league, t.id, False), _record(h), str(h["pf"]), str(h["pa"]),
                            f"{h['pf'] - h['pa']:+d}", f"{ORDINAL.get(h.get('div_rank'), '')} {escape(t.division)}",
                            str(h["seed"] or ""), escape(h.get("result") or "")]))
    head = [("Team", True), ("Record", False), ("PF", False), ("PA", False), ("Diff", False),
            ("Division finish", True), ("Seed", False), ("How it ended", True)]
    th = "".join(f"<th class='l'>{escape(t)}</th>" if left else f"<th>{escape(t)}</th>" for t, left in head)
    body = "".join(f"<tr{cls}>" + "".join(f"<td class='l'>{c}</td>" if head[i][1] else f"<td>{c}</td>"
                                         for i, c in enumerate(r)) + "</tr>" for cls, r in lines)
    standings = _panel(f"{season} season: every team's finish",
                       f"<table class='box-table'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>",
                       "Ordered by how far each team went, then by record. PF / PA = points for / against.")
    aw = []
    for key, name, _short in A.SEASON_AWARDS:
        r = sm["awards"].get(key)
        if r:
            aw.append([escape(name), _name(league, r["pid"]), _team(league, r["team"])])
    if sm["gb_mvp"]:
        r = sm["gb_mvp"]
        aw.append([f"{escape(sm['name'])} MVP", _name(league, r["pid"]), _team(league, r["team"])])
    awards = _panel("Awards", _table([("Award", True), ("Player", True), ("Team", True)], aw) if aw else
                    "<div class='legend'>No awards on record for this season.</div>")
    led = [[escape(LEADER_LABELS[k]), _name(league, pid), _teams(league, tids), _value(v, k)]
           for k, (v, pid, tids) in sm["leaders"].items()]
    leaders = _panel("League leaders", _table([("Stat", True), ("Player", True), ("Team", True), ("Total", False)],
                                              led), "Regular season.")
    return (f"<div class='report px-5 py-4' style='margin-bottom:14px'>{''.join(top)}</div>"
            + f"<div style='display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:14px;"
              f"align-items:start'>{standings}<div style='display:flex;flex-direction:column;gap:14px'>{awards}"
              f"{leaders}</div></div>")


def build_history_tab():
    league = state.league
    ui.add_head_html(CSS)
    view = {"mode": "champions", "season": None}

    def set_view(**kw):
        view.update(kw)
        body.refresh()

    ready = {"yes": False}       # drawn the first time the page is shown (main_page: lazy pages)

    @ui.refreshable
    def body():
        if not ready["yes"]:
            return
        seasons = H.seasons(league)
        with ui.element("div").classes("page-toolbar"):
            with ui.element("div").classes("toolbar-group"):
                ui.toggle({"champions": "Champions", "franchises": "Franchises", "season": "One season"},
                          value=view["mode"], on_change=lambda e: set_view(mode=e.value)).props(TOGGLE)
                if view["mode"] == "season" and seasons:
                    s = view["season"] if view["season"] in seasons else seasons[0]
                    ui.select({x: str(x) for x in seasons}, value=s, label="Season",
                              on_change=lambda e: set_view(season=e.value)).props(SELECT).classes("w-32")
            ui.label(f"{len(seasons)} finished season{'s' if len(seasons) != 1 else ''}").classes("legend")
        if view["mode"] == "season" and seasons:
            s = view["season"] if view["season"] in seasons else seasons[0]
            ui.html(season_html(league, s), sanitize=False).classes("w-full")
        elif view["mode"] == "franchises":
            ui.html(franchises_html(league) or champions_html(league), sanitize=False).classes("w-full")
        else:
            ui.html(champions_html(league), sanitize=False).classes("w-full")

    with ui.column().classes("w-full px-8 py-4 gap-3"):
        body()

    def refresh():
        ready["yes"] = True
        body.refresh()
    return refresh


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def _when(league, r, scope):
    if scope == "career":
        a, b = r["season"]
        return f"{a}-{b}" if a != b else str(a)
    s = f"{r['season']}" + ("*" if r["current"] else "")
    g = r.get("game")
    if g:
        wk = f"Week {g['week']}" if g["phase"] == ST.REGULAR else po.ROUND_NAMES.get(g["week"], "Playoffs")
        if g["phase"] != ST.REGULAR and g["week"] == 5:
            wk = H.championship_name(league, r["season"])
        s += f", {escape(wk)} vs {_team(league, g['opp'])}"
    return s


def record_panel(league, key, scope, phase, team=None, n=10):
    label, how = H.STAT_INFO[key][0], H.STAT_INFO[key][1]
    rows = H.records(league, key, scope, phase, n=n, team=team)
    if not rows:
        return ""
    cells = []
    for i, r in enumerate(rows, start=1):
        cells.append([str(i), _name(league, r["pid"]), _teams(league, r["teams"][:3] if scope == "career"
                                                                else r["teams"]),
                      f"<span style='white-space:nowrap'>{_when(league, r, scope)}</span>",
                      f"<b>{ST.fmt_value(r['value'], how)}</b>"])
    return _panel(label, _table([("#", False), ("Player", True), ("Team", True),
                                 ("Years" if scope == "career" else "When", True), ("Total", False)], cells))


def min_note(scope, phase):
    if scope == "game":
        return "Single-game passer rating and completion %: at least 20 attempts; yards per carry: 10 carries."
    if scope == "season":
        return ("Rate stats need the NFL's minimums per team game (14 pass attempts, 6.25 carries, 1 field goal "
                "try, 2.5 punts)." if phase == ST.REGULAR else "Rate stats need two games' worth of tries.")
    return ("Rate stats need the NFL's career minimums: 1,500 pass attempts, 750 carries, 100 field goal tries, "
            "250 punts." if phase == ST.REGULAR else "Rate stats need a tenth of the regular-season career minimums.")


def team_records_html(league, team=None, phase=ST.REGULAR):
    panels = []
    if phase == ST.REGULAR:
        tr = H.team_season_records(league, n=10, team=team)
        for key, label, _hi in H.TEAM_SEASON_STATS:
            rows = tr[key]
            if not rows:
                continue
            val = (lambda h: f"{h['pf'] - h['pa']:+d}") if key == "diff" else (lambda h, k=key: str(h[k]))
            panels.append(_panel(f"{label} (season)", _table(
                [("#", False), ("Team", True), ("Season", True), ("Record", False), ("Total", False)],
                [[str(i), _team(league, h["team"], False), str(h["season"]), _record(h), f"<b>{val(h)}</b>"]
                 for i, h in enumerate(rows, start=1)])))
    tg = H.team_game_records(league, n=10, team=team, phase=phase)
    for key, label in (("pts", "Most points in a game"), ("margin", "Biggest win")):
        rows = tg[key]
        if rows:
            panels.append(_panel(label, _table(
                [("#", False), ("Team", True), ("When", True), ("Opponent", True), ("Total", False)],
                [[str(i), _team(league, r[2], False),
                  f"{r[4]}, " + (f"Week {r[5]}" if phase == ST.REGULAR else escape(po.ROUND_NAMES.get(r[5], ""))),
                  _team(league, r[3]), f"<b>{r[0]:+d}</b>" if key == "margin" else f"<b>{r[0]}</b>"]
                 for i, r in enumerate(rows, start=1)])))
    if not panels:
        return _empty("No team records yet", "Team records start with the first finished games.")
    return _grid(panels, 440) + ("<div class='legend' style='margin-top:6px'>Season records count finished "
                                 "seasons.</div>" if phase == ST.REGULAR else "")


STATUS = {"all": "Active and retired", "active": "Active", "retired": "Retired", "hof": "Hall of Fame"}
POSITIONS = ["QB", "RB", "FB", "WR", "TE", "T", "G", "C", "DE", "DT", "OLB", "ILB", "CB", "S", "K", "P", "LS"]


def career_leaders_html(league, key, phase=ST.REGULAR, status="all", position="all", team=None, n=50):
    label, how = H.STAT_INFO[key][0], H.STAT_INFO[key][1]
    totals = H.career_totals(league, phase, team)
    keep = set()
    for pid in totals:
        p = _player(league, pid)
        if p is None:
            continue
        if position != "all" and p.position != position:
            continue
        if status == "active" and p.retired is not None:
            continue
        if status == "retired" and p.retired is None:
            continue
        if status == "hof" and not HOF.member(league, pid):
            continue
        keep.add(pid)
    rows = H.records(league, key, "career", phase, n=n, team=team, players=keep)
    if not rows:
        return _empty("Nobody yet", "No player matches these filters with this stat.")
    cells = []
    for i, r in enumerate(rows, start=1):
        p = league.player(r["pid"])
        e = totals[r["pid"]]
        st = ("Hall of Fame" if HOF.member(league, p.id) else "Active" if p.retired is None
              else f"Retired ({p.retired})")
        cls = "<b>" if p.retired is None else ""
        cells.append([str(i), _name(league, p.id), _teams(league, e["teams"][:3]),
                      _when(league, r, "career"), str(e["seasons"]), str(int(e["stats"].get("gp", 0))),
                      escape(st), f"{cls}{ST.fmt_value(r['value'], how)}{'</b>' if cls else ''}"])
    return _panel(f"All-time {label.lower()} leaders", _table(
        [("#", False), ("Player", True), ("Teams", True), ("Years", True), ("Seasons", False), ("G", False),
         ("Status", True), (label, False)], cells),
        "Active players' totals in bold (they include the season in progress). Teams: most games first. "
        + escape(min_note("career", phase)))


def build_records_tab():
    league = state.league
    ui.add_head_html(CSS)
    view = {"scope": "season", "phase": ST.REGULAR, "cat": "Passing", "team": "all", "stat": "pass_yds",
            "status": "all", "pos": "all"}
    team_opts = {"all": "Whole league", **{t.id: t.name for t in sorted(league.teams, key=lambda t: t.name)}}
    stat_opts = {k: f"{cat}: {label}" for cat, rows in H.RECORD_STATS.items() for k, label, *_r in rows
                 if k not in H.LONGEST}

    def backfill():
        """An older save: its finished seasons' single games from the history file, once."""
        if not H.missing_seasons(league):
            return
        past = []
        path = getattr(state, "save_path", None)
        if path:
            from engine import saves
            from engine.database import read_history
            try:
                past = read_history(saves.history_path(path))
            except Exception:
                past = []
        H.backfill_games(league, past)

    def set_view(**kw):
        view.update(kw)
        body.refresh()

    ready = {"yes": False}       # drawn the first time the page is shown (main_page: lazy pages)

    @ui.refreshable
    def body():
        if not ready["yes"]:
            return
        team = None if view["team"] == "all" else view["team"]
        with ui.element("div").classes("page-toolbar"):
            with ui.element("div").classes("toolbar-group"):
                ui.toggle({"game": "Single game", "season": "Single season", "career": "Career",
                           "team": "Team records", "leaders": "Career leaders"}, value=view["scope"],
                          on_change=lambda e: set_view(scope=e.value)).props(TOGGLE)
                ui.toggle({ST.REGULAR: "Regular season", ST.PLAYOFFS: "Playoffs"}, value=view["phase"],
                          on_change=lambda e: set_view(phase=e.value)).props(TOGGLE)
            with ui.element("div").classes("toolbar-group"):
                if view["scope"] in ("game", "season", "career"):
                    ui.select(list(H.RECORD_STATS), value=view["cat"], label="Category",
                              on_change=lambda e: set_view(cat=e.value)).props(SELECT).classes("w-36")
                if view["scope"] == "leaders":
                    ui.select(stat_opts, value=view["stat"], label="Stat",
                              on_change=lambda e: set_view(stat=e.value)).props(SELECT).classes("w-64")
                    ui.select(STATUS, value=view["status"], label="Players",
                              on_change=lambda e: set_view(status=e.value)).props(SELECT).classes("w-44")
                    ui.select({"all": "All positions", **{p: p for p in POSITIONS}}, value=view["pos"],
                              label="Position", on_change=lambda e: set_view(pos=e.value)).props(SELECT).classes("w-36")
                ui.select(team_opts, value=view["team"], label="Records of",
                          on_change=lambda e: set_view(team=e.value)).props(SELECT).classes("w-56")
        if view["scope"] == "game":
            backfill()
        if view["scope"] == "team":
            ui.html(team_records_html(league, team, view["phase"]), sanitize=False).classes("w-full")
            return
        if view["scope"] == "leaders":
            ui.html(career_leaders_html(league, view["stat"], view["phase"], view["status"], view["pos"], team),
                    sanitize=False).classes("w-full")
            return
        panels = [record_panel(league, k, view["scope"], view["phase"], team)
                  for k, *_r in H.RECORD_STATS[view["cat"]]]
        panels = [p for p in panels if p]
        if not panels:
            ui.html(_empty("No records yet", "Records start with the first games played."), sanitize=False) \
                .classes("w-full")
            return
        who = "League" if team is None else f"{league.team(team).name} franchise"
        ui.html(_grid(panels) + f"<div class='legend' style='margin-top:6px'>{escape(who)} records, "
                f"{'regular season' if view['phase'] == ST.REGULAR else 'playoffs'}. * = the season in progress. "
                f"{escape(min_note(view['scope'], view['phase']))} Franchise records count only games for that "
                "team. HOF = in the Hall of Fame.</div>", sanitize=False).classes("w-full")

    with ui.column().classes("w-full px-8 py-4 gap-3"):
        body()

    def refresh():
        ready["yes"] = True
        body.refresh()
    return refresh


# ---------------------------------------------------------------------------
# Hall of Fame
# ---------------------------------------------------------------------------

def _resume_bits(r):
    bits = []
    if r["ap1"] or r.get("ap1_spec"):
        n = r["ap1"] + r.get("ap1_spec", 0)
        bits.append(f"{n}x first-team All-Pro")
    if r["pb"]:
        bits.append(f"{r['pb']}x Pro Bowl")
    big = [name for _s, name in r["awards"]]
    for name in dict.fromkeys(big):
        k = big.count(name)
        bits.append(f"{k}x {name}" if k > 1 else name)
    if r["titles"]:
        bits.append(f"{len(r['titles'])}x champion")
    return " · ".join(bits) or "-"


def _career_line(league, p, r):
    s = r["stats"]
    g = HOF.HOF_GROUP.get(p.position)
    f = lambda k: int(round(s.get(k, 0) or 0))
    if g == "QB":
        return f"{f('pass_yds'):,} pass yds, {f('pass_td')} TD"
    if g == "RB":
        return f"{f('rush_yds'):,} rush yds, {f('rush_td') + f('rec_td')} TD"
    if g in ("WR", "TE"):
        return f"{f('rec'):,} rec, {f('rec_yds'):,} yds, {f('rec_td')} TD"
    if g in ("DL", "LB"):
        return f"{s.get('sacks', 0):.1f} sacks, {f('tkl') + f('ast'):,} tackles"
    if g == "DB":
        return f"{f('def_int')} INT, {f('pd')} PD"
    if g == "K":
        return f"{f('fgm')} FG"
    if g == "P":
        return f"{f('punts')} punts"
    return f"{r['games']} games"


def members_html(league, position="all"):
    classes = HOF.classes(league)
    if not classes:
        first_vote = league.settings.get("first_season", league.season) + HOF.WAIT
        return _empty("The Hall of Fame is empty",
                      f"Players are eligible {HOF.WAIT} seasons after their last one, so the first vote that can "
                      f"elect anyone with a career in this league is the week of the {first_vote} "
                      f"{po.CHAMPIONSHIP} at the earliest. Careers count only from the league's first season, "
                      "so the first classes are small.")
    panels = []
    for year, ms in classes.items():
        rows = []
        for m in sorted(ms, key=lambda m: -m["votes"]):
            p = _player(league, m["pid"])
            if p is None or (position != "all" and p.position != position):
                continue
            r = HOF.resume(league, p.id)
            rows.append([_name(league, p.id, mark=False), _teams(league, r["teams"][:3]),
                         f"{r['first']}-{r['last']}" if r["first"] else "", str(r["seasons"]),
                         escape(_career_line(league, p, r)), escape(_resume_bits(r)),
                         f"{m['votes']} of {HOF.VOTERS}", "First" if m["ballot"] == 1 else _ord(m["ballot"])])
        if rows:
            panels.append(_panel(f"Class of {year}", _table(
                [("Player", True), ("Teams", True), ("Years", True), ("Seasons", False), ("Career", True),
                 ("Honors", True), ("Votes", False), ("Ballot", False)], rows)))
    if not panels:
        return _empty("No members at this position", "Try All positions.")
    return "".join(f"<div style='margin-bottom:14px'>{p}</div>" for p in panels)


def ballot_html(league, season):
    b = HOF.ballot(league, season)
    if not b or not b["ballot"]:
        return _empty(f"No candidates in {season}", "Nobody eligible that year had a career voters would consider.")
    rows = []
    need = round(HOF.NEEDED * HOF.VOTERS)
    for pid, votes, ballot_no, elected in b["ballot"]:
        p = _player(league, pid)
        if p is None:
            continue
        r = HOF.resume(league, pid)
        rows.append([_name(league, pid, mark=False), _teams(league, r["teams"][:3]), str(r["seasons"]),
                     escape(_resume_bits(r)), f"{votes} ({round(100 * votes / HOF.VOTERS)}%)",
                     str(ballot_no), "<b>Elected</b>" if elected else ("Held over (class limit)" if votes >= need
                                                                       else "")])
    legend = (f"The finalists: the {HOF.FINALISTS} candidates with the most votes of the {b['considered']} considered. "
              f"{need} of {HOF.VOTERS} votes ({round(100 * HOF.NEEDED)}%) elects; at most {HOF.CLASS_LIMIT} a year. "
              "Ballot = his year on the ballot (1 = first year eligible).")
    return _panel(f"The vote for the Class of {b['class_of']} (the week of the {season} season's "
                  f"{po.CHAMPIONSHIP})", _table([("Candidate", True), ("Teams", True), ("Seasons", False),
                                                  ("Honors", True), ("Votes", False), ("Ballot", False),
                                                  ("Result", True)], rows), legend)


def eligible_next_html(league):
    rows = []
    for p, r in HOF.eligible_next(league):
        rows.append([_name(league, p.id, mark=False), _teams(league, r["teams"][:3]),
                     f"{r['first']}-{r['last']}" if r["first"] else "", escape(_career_line(league, p, r)),
                     escape(_resume_bits(r))])
    if not rows:
        return ""
    return _panel(f"First eligible next year (retired after the {league.season - HOF.WAIT + 1} season)", _table(
        [("Player", True), ("Teams", True), ("Years", True), ("Career", True), ("Honors", True)], rows),
        "The strongest careers on the record, best first. Their fate is up to the 50 voters.")


def build_hof_tab():
    league = state.league
    ui.add_head_html(CSS)
    view = {"mode": "members", "pos": "all", "season": None}

    def set_view(**kw):
        view.update(kw)
        body.refresh()

    ready = {"yes": False}       # drawn the first time the page is shown (main_page: lazy pages)

    @ui.refreshable
    def body():
        if not ready["yes"]:
            return
        votes = [v["season"] for v in HOF.ensure(league)["votes"] if v["ballot"]]
        n = len(HOF.members(league))
        with ui.element("div").classes("page-toolbar"):
            with ui.element("div").classes("toolbar-group"):
                ui.html("<span class='hof-badge'>Hall of Fame</span>", sanitize=False)
                ui.toggle({"members": f"Members ({n})", "votes": "The vote", "next": "Eligible next year"},
                          value=view["mode"], on_change=lambda e: set_view(mode=e.value)).props(TOGGLE)
                if view["mode"] == "members":
                    ui.select({"all": "All positions", **{p: p for p in POSITIONS}}, value=view["pos"],
                              label="Position", on_change=lambda e: set_view(pos=e.value)).props(SELECT) \
                        .classes("w-36")
                if view["mode"] == "votes" and votes:
                    s = view["season"] if view["season"] in votes else votes[-1]
                    ui.select({x: f"Class of {x + 1}" for x in reversed(votes)}, value=s, label="Year",
                              on_change=lambda e: set_view(season=e.value)).props(SELECT).classes("w-40")
            ui.label(f"Eligible {HOF.WAIT} seasons after retiring · {HOF.VOTERS} media voters · "
                     f"{round(100 * HOF.NEEDED)}% to get in · at most {HOF.CLASS_LIMIT} a year").classes("legend")
        if view["mode"] == "votes":
            if not votes:
                ui.html(_empty("No votes yet", "The Hall of Fame vote is held the week of the "
                                               f"{po.CHAMPIONSHIP}, once there are eligible candidates."),
                        sanitize=False).classes("w-full")
            else:
                s = view["season"] if view["season"] in votes else votes[-1]
                ui.html(ballot_html(league, s), sanitize=False).classes("w-full")
        elif view["mode"] == "next":
            ui.html(eligible_next_html(league) or _empty("Nobody notable", "No player first eligible next year has "
                                                         "a career voters would consider."),
                    sanitize=False).classes("w-full")
        else:
            ui.html(members_html(league, view["pos"]), sanitize=False).classes("w-full")

    with ui.column().classes("w-full px-8 py-4 gap-3"):
        body()

    def refresh():
        ready["yes"] = True
        body.refresh()
    return refresh


# ---------------------------------------------------------------------------
# The team window's History tab
# ---------------------------------------------------------------------------

FRANCHISE_RECORD_STATS = ["pass_yds", "pass_td", "rush_yds", "rush_td", "rec", "rec_yds", "rec_td", "sacks",
                          "def_int", "tackles", "fgm", "points"]


def franchise_html(league, tid):
    f = H.franchise(league, tid)
    t = f["totals"]
    team = league.team(tid)
    if not t["seasons"]:
        return _empty("No finished seasons yet", f"The {team.name}' history starts when the first season ends.")
    g = t["w"] + t["l"] + t["t"]
    out = [CSS, _kpis([("Seasons", t["seasons"]),
                       ("All-time record", f"{t['w']}-{t['l']}" + (f"-{t['t']}" if t["t"] else "")),
                       ("Win %", f"{(t['w'] + 0.5 * t['t']) / g:.3f}".lstrip("0") if g else "-"),
                       ("Playoff seasons", t["playoffs"]), ("Playoff record", f"{t['playoff_w']}-{t['playoff_l']}"),
                       ("Division titles", t["division_titles"]),
                       (f"{po.CHAMPIONSHIP} titles", len(t["titles"]))])]
    years = [[str(h["season"]), _record(h), str(h["pf"]), str(h["pa"]),
              f"{ORDINAL.get(h.get('div_rank'), '')}", str(h["seed"] or ""),
              ("<b>" + escape(h.get("result") or "") + "</b>") if league.champions.get(h["season"]) == tid
              else escape(h.get("result") or "")] for h in f["years"]]
    year_panel = _panel("Year by year", _table([("Season", True), ("Record", False), ("PF", False), ("PA", False),
                                                ("Division", False), ("Seed", False), ("How it ended", True)], years))
    best = []
    for pid, hon, car in f["best"][:12]:
        p = _player(league, pid)
        if p is None:
            continue
        bits = []
        if hon["awards"]:
            bits.append(", ".join(f"{n} ({s})" for s, n in sorted(hon["awards"])))
        if hon["ap1"]:
            bits.append(f"{hon['ap1']}x All-Pro")
        if hon["ap2"]:
            bits.append(f"{hon['ap2']}x 2nd-team All-Pro")
        if hon["pb"]:
            bits.append(f"{hon['pb']}x Pro Bowl")
        yrs = f"{car['first']}-{car['last']}" if car else ""
        best.append([_name(league, pid), yrs, str(car["seasons"]) if car else "", escape(" · ".join(bits))])
    best_panel = _panel("Best players", _table([("Player", True), ("Years here", True), ("Seasons", False),
                                                ("Honors with the team", True)], best)
                        if best else "<div class='legend'>No honors won for this team yet.</div>",
                        "Ranked by awards, All-Pros and Pro Bowls won while with this team.")
    leaders = []
    for key in FRANCHISE_RECORD_STATS:
        car = H.records(league, key, "career", ST.REGULAR, n=1, team=tid)
        sea = H.records(league, key, "season", ST.REGULAR, n=1, team=tid)
        gam = H.records(league, key, "game", ST.REGULAR, n=1, team=tid) if key in H.GAME_STATS else []
        if not car:
            continue
        cell = lambda rows, scope: (f"{_name(league, rows[0]['pid'], tag=False)} "
                                    f"<b>{_value(rows[0]['value'], key)}</b> ({_when(league, rows[0], scope)})"
                                    if rows else "")
        leaders.append([escape(H.STAT_INFO[key][0]), cell(car, "career"), cell(sea, "season"), cell(gam, "game")])
    rec_panel = _panel("Franchise records", _table([("Stat", True), ("Career", True), ("Season", True),
                                                    ("Game", True)], leaders),
                       "Regular season, games for this team only. * = the season in progress. The Records page "
                       "(League section) has each franchise's top 10s.")
    hof = [m for m in HOF.members(league) if tid in HOF.resume(league, m["pid"])["teams"]]
    hof_rows = [[_name(league, m["pid"], mark=False), f"Class of {m['class_of']}",
                 "Mostly here" if m.get("team") == tid else "Also played here"] for m in hof]
    hof_panel = _panel("Hall of Famers", _table([("Player", True), ("Class", True), ("", True)], hof_rows)) \
        if hof_rows else ""
    out.append(f"<div style='display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:14px;"
               f"align-items:start'><div style='display:flex;flex-direction:column;gap:14px'>{year_panel}"
               f"{hof_panel}</div><div style='display:flex;flex-direction:column;gap:14px'>{rec_panel}{best_panel}"
               f"</div></div>")
    return "".join(out)
