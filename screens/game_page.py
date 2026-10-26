# game_page.py
# The Game tab: watch your team's game this week (Hall of Fame Game,
# preseason or regular season) play out snap by snap, the way FOF8's game
# screen works. The scoreboard, the field and the play-by-play update after
# every play; the box score fills in as you go. (The old "any two teams"
# exhibition picker is gone: preseason games are scheduled, as in the NFL.)
#
# Take over play calling (Oct 25; Blake: "one very important thing in fof8
# was the ability to call plays while watching the game of your team"): a
# box next to the speed buttons, like FOF8's. While it's ticked the game
# stops on each of your snaps, offense or defense, and shows the menu with
# your coordinator's suggestion; untick it and the call on screen goes to
# the staff and the game runs on by itself again. Tick and untick as often
# as you like, at any speed.
#
# This screen only SHOWS the game. Every football decision is made by the
# game engine (engine/sim), so it can be tuned without touching this file;
# what the menu offers and how calls are read is engine/sim/playcalling.py.

from html import escape

from nicegui import ui

from engine import season
from engine.sim.norms import build_norms
from engine.sim import text as T
from engine.sim import playcalling
from engine.sim.game import ASK
from engine.sim.stats import passer_rating
from .state import state, mark_changed

# Seconds between plays at each speed.
SPEEDS = {"Slow": 2.2, "Normal": 1.0, "Fast": 0.35, "Very fast": 0.08}

TURNOVER_WORDS = ("INTERCEPTED", "RECOVERED by", "Turnover on downs", "MUFFS", "BLOCKED")

# Keeps the play-by-play scrolled to the newest play while you're at the
# bottom; if you scroll up to read, it stays put until you scroll back down.
FOLLOW_JS = """
requestAnimationFrame(() => {
  const e = document.getElementById('pbp-log');
  if (!e) return;
  if (!e.dataset.watching) {
    e.dataset.watching = '1';
    e.dataset.stick = '1';
    e.addEventListener('scroll', () => {
      e.dataset.stick = (e.scrollHeight - e.scrollTop - e.clientHeight < 60) ? '1' : '0';
    });
  }
  if (e.dataset.stick === '1') { e.scrollTop = e.scrollHeight; }
});
"""


class Viewer:
    """The game being watched on this screen."""

    def __init__(self):
        self.game = None
        self.gen = None
        self.running = False
        self.speed = "Normal"
        self.last_drive = None
        self.shown = 0              # how many log events are on screen
        self.finished = False
        self.take_over = False      # "Take over play calling" is ticked
        self.my_idx = None          # your team's index in the game (0 home, 1 away), if it's in it
        self.your_call = None       # the label of the call you just made, tagged on the next play


_norms_cache = {}


def norms_for(league):
    key = id(league)
    if key not in _norms_cache:
        _norms_cache.clear()
        _norms_cache[key] = build_norms(league)
    return _norms_cache[key]


# ---------------------------------------------------------------------------
# Small HTML builders
# ---------------------------------------------------------------------------

def _timeouts_html(n, total=3):
    return "".join(f'<span class="to-dot{" used" if i >= n else ""}"></span>' for i in range(total))


def scoreboard_html(game):
    st = game.state
    home, away = game.teams
    if st.qtr <= 4:
        period = ["", "1st", "2nd", "3rd", "4th"][st.qtr]
    else:
        period = "OT"
    if game.finished:
        period = "Final" + (" (OT)" if game.overtime else "")
    clock = "" if game.finished else T.clock_text(st.clock)
    off = game.teams[st.poss]
    deff = game.teams[1 - st.poss]
    if game.finished:
        situation = ""
    elif game._need_kickoff:
        situation = f"{game.teams[game._kicking].abbrev} kicking off"
    elif game._need_pat:
        situation = f"{off.abbrev} try after touchdown"
    else:
        situation = f"{T.down_text(st.down, st.togo, st.yl)} at {T.spot(st.yl, off.abbrev, deff.abbrev)}"
    to_total = 2 if st.qtr >= 5 else 3

    def side(team, idx):
        has_ball = (not game.finished) and st.poss == idx and not game._need_kickoff
        ball = '<span class="poss-ball" title="Has the ball"></span>' if has_ball else '<span class="poss-ball off"></span>'
        return (f'<div class="sb-team">{ball}<div class="sb-abbrev">{escape(team.abbrev)}</div>'
                f'<div class="sb-name">{escape(team.name)}</div>'
                f'<div class="sb-score num">{st.score[idx]}</div>'
                f'<div class="sb-to" title="Timeouts left">{_timeouts_html(team.timeouts, to_total)}</div></div>')

    return (f'<div class="scoreboard">{side(away, 1)}'
            f'<div class="sb-mid"><div class="sb-period">{period}</div>'
            f'<div class="sb-clock num">{clock}</div>'
            f'<div class="sb-situation">{escape(situation)}</div>'
            f'<div class="sb-weather">{escape(game.weather.text())}</div></div>'
            f'{side(home, 0)}</div>')


def field_html(game):
    """A strip of the field: home team defends the left end zone. Blue line =
    line of scrimmage, yellow line = first-down marker."""
    st = game.state
    home, away = game.teams
    w = 1200
    parts = [f'<svg viewBox="0 0 {w} 80" class="field-strip">',
             '<rect x="0" y="0" width="1200" height="80" fill="#2F6B3F"/>',
             '<rect x="0" y="0" width="100" height="80" fill="#22512F"/>',
             '<rect x="1100" y="0" width="100" height="80" fill="#22512F"/>']
    for yd in range(0, 101, 5):
        x = 100 + yd * 10
        parts.append(f'<line x1="{x}" y1="0" x2="{x}" y2="80" stroke="white" stroke-opacity="'
                     f'{0.85 if yd % 10 == 0 else 0.35}" stroke-width="{2 if yd in (0, 100) else 1.2}"/>')
        if yd % 10 == 0 and 0 < yd < 100:
            num = yd if yd <= 50 else 100 - yd
            parts.append(f'<text x="{x}" y="74" class="f-num">{num}</text>')
    parts.append(f'<text x="50" y="49" class="f-ez">{escape(home.abbrev)}</text>')
    parts.append(f'<text x="1150" y="49" class="f-ez">{escape(away.abbrev)}</text>')
    if not game.finished and not game._need_kickoff:
        # Ball position measured from the home goal line (left).
        pos = 100 - st.yl if st.poss == 0 else st.yl
        x = 100 + pos * 10
        direction = 1 if st.poss == 0 else -1
        if not game._need_pat:
            fd = pos + direction * st.togo
            if 0 <= fd <= 100:
                fx = 100 + fd * 10
                parts.append(f'<line x1="{fx}" y1="0" x2="{fx}" y2="80" stroke="#F5C518" stroke-width="4"/>')
        parts.append(f'<line x1="{x}" y1="0" x2="{x}" y2="80" stroke="#5AA9E6" stroke-width="4"/>')
        parts.append(f'<ellipse cx="{x}" cy="38" rx="13" ry="8" fill="#7A4A21" stroke="white" stroke-width="1.5"/>')
        arrow_x = x + direction * 32
        parts.append(f'<text x="{arrow_x}" y="27" class="f-arrow">{"&#9654;" if direction > 0 else "&#9664;"}</text>')
    parts.append('</svg>')
    return "".join(parts)


def event_html(game, ev):
    off = game.teams[ev.poss]
    deff = game.teams[1 - ev.poss]
    if ev.kind in ("note", "quarter", "final", "timeout", "injury"):
        cls = {"quarter": "pbp-quarter", "final": "pbp-quarter pbp-final", "timeout": "pbp-note",
               "injury": "pbp-note pbp-injury"}.get(ev.kind, "pbp-note")
        return f'<div class="{cls}">{escape(ev.text)}</div>'
    clock = T.clock_text(ev.clock)
    if ev.kind == "kickoff":
        dd = "Kickoff"
    elif ev.kind == "xp":
        dd = "Extra point"
    elif ev.kind == "two_point":
        dd = "Two-point try"
    elif ev.down:
        dd = f"{T.down_text(ev.down, ev.togo, ev.yl)} at {T.spot(ev.yl, off.abbrev, deff.abbrev)}"
    else:
        dd = ""
    classes = ["pbp-row"]
    if ev.scoring:
        classes.append("pbp-score")
    elif any(w in ev.text for w in TURNOVER_WORDS):
        classes.append("pbp-turnover")
    elif ev.big:
        classes.append("pbp-big")
    detail = f'<div class="pbp-detail">{escape(ev.detail)}</div>' if ev.detail else ""
    score = ""
    if ev.scoring:
        home, away = game.teams
        score = f'<div class="pbp-scoreline">{escape(away.abbrev)} {ev.score[1]}, {escape(home.abbrev)} {ev.score[0]}</div>'
    return (f'<div class="{" ".join(classes)}"><span class="pbp-clock num">Q{min(ev.qtr, 5) if ev.qtr <= 4 else "OT"} {clock}</span>'
            f'<span class="pbp-team">{escape(off.abbrev)}</span>'
            f'<span class="pbp-dd">{escape(dd)}</span>'
            f'<div class="pbp-text">{escape(ev.text)}{detail}{score}</div></div>')


def drive_header_html(game, ev):
    off = game.teams[ev.poss]
    deff = game.teams[1 - ev.poss]
    start = T.spot(ev.yl, off.abbrev, deff.abbrev)
    return (f'<div class="pbp-drive">{escape(off.abbrev)} ball at {escape(start)}  '
            f'<span class="legend">Q{ev.qtr if ev.qtr <= 4 else "OT"} {T.clock_text(ev.clock)}</span></div>')


# ---------------------------------------------------------------------------
# Box score
# ---------------------------------------------------------------------------

class _Html(str):
    """A table cell that's already HTML (a player link), so it isn't escaped."""


def _table(title, head, rows, empty="None", left=(0,)):
    """A simple stats table. Columns listed in `left` are left-aligned (names,
    descriptions); the rest are numbers, right-aligned."""
    def cell(tag, i, c):
        cls = ' class="l"' if i in left else ""
        return f"<{tag}{cls}>{c if isinstance(c, _Html) else escape(str(c))}</{tag}>"
    h = "".join(cell("th", i, c) for i, c in enumerate(head))
    if not rows:
        body = f'<tr><td colspan="{len(head)}" class="legend l">{escape(empty)}</td></tr>'
    else:
        body = "".join("<tr>" + "".join(cell("td", i, c) for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="box-title">{escape(title)}</div><table class="box-table"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def _num(x):
    return int(round(x))


def box_score_html(game, idx):
    box = game.box
    team = game.teams[idx]
    lines = [(team.by_id[pid], line) for pid, line in box.players.items()
             if box.owner.get(pid) == idx and pid in team.by_id]

    def name(p):
        # A link: click it for his card (a pop-up on the game screen, popups.py).
        return _Html(f'<a class="plink" href="/player/{p.id}">{escape(T.short_name(p))}</a> ({p.position})')

    tid = getattr(team, "id", None)
    out = [f'<div class="box-team">' + (f'<a class="tlink" href="/team/{tid}">{escape(team.name)}</a>'
                                         if tid is not None else escape(team.name)) + '</div>']
    passing = sorted([(p, l) for p, l in lines if l.get("pass_att", 0) - l.get("spikes", 0) > 0 or l.get("sacked")],
                     key=lambda x: -x[1].get("pass_att", 0))
    out.append(_table("Passing", ["Player", "C/Att", "Yds", "TD", "Int", "Sacked", "Long", "Rating"],
                      [[name(p), f"{_num(l['pass_cmp'])}/{_num(l['pass_att'])}", _num(l["pass_yds"]),
                        _num(l["pass_td"]), _num(l["pass_int"]), f"{_num(l['sacked'])}-{_num(l['sacked_yds'])}",
                        _num(l["pass_long"]),
                        f"{passer_rating(l['pass_att'], l['pass_cmp'], l['pass_yds'], l['pass_td'], l['pass_int']):.1f}"]
                       for p, l in passing]))
    rushing = sorted([(p, l) for p, l in lines if l.get("rush_att")], key=lambda x: -x[1]["rush_yds"])
    out.append(_table("Rushing", ["Player", "Car", "Yds", "Avg", "TD", "Long"],
                      [[name(p), _num(l["rush_att"]), _num(l["rush_yds"]),
                        f"{l['rush_yds'] / l['rush_att']:.1f}", _num(l["rush_td"]), _num(l["rush_long"])]
                       for p, l in rushing]))
    receiving = sorted([(p, l) for p, l in lines if l.get("targets")], key=lambda x: (-x[1]["rec_yds"], -x[1]["rec"]))
    out.append(_table("Receiving", ["Player", "Rec", "Tgt", "Yds", "Avg", "TD", "Long"],
                      [[name(p), _num(l["rec"]), _num(l["targets"]), _num(l["rec_yds"]),
                        f"{l['rec_yds'] / l['rec']:.1f}" if l["rec"] else "0.0", _num(l["rec_td"]),
                        _num(l["rec_long"])] for p, l in receiving]))
    defense = sorted([(p, l) for p, l in lines if l.get("tkl") or l.get("ast") or l.get("sacks") or
                      l.get("def_int") or l.get("pd") or l.get("ff")],
                     key=lambda x: -(x[1]["tkl"] + x[1]["ast"]))
    out.append(_table("Defense", ["Player", "Tkl", "Solo", "Sacks", "TFL", "QB hits", "Int", "PD", "FF"],
                      [[name(p), _num(l["tkl"] + l["ast"]), _num(l["tkl"]), f"{l['sacks']:g}", f"{l['tfl']:g}",
                        _num(l["qb_hits"]), _num(l["def_int"]), _num(l["pd"]), _num(l["ff"])]
                       for p, l in defense]))
    kick = [(p, l) for p, l in lines if l.get("fga") or l.get("xpa")]
    out.append(_table("Kicking", ["Player", "FG", "Long", "XP", "Points"],
                      [[name(p), f"{_num(l['fgm'])}/{_num(l['fga'])}", _num(l["fg_long"]),
                        f"{_num(l['xpm'])}/{_num(l['xpa'])}", _num(3 * l["fgm"] + l["xpm"])] for p, l in kick]))
    punt = [(p, l) for p, l in lines if l.get("punts")]
    out.append(_table("Punting", ["Player", "Punts", "Yds", "Avg", "Inside 20", "Long"],
                      [[name(p), _num(l["punts"]), _num(l["punt_yds"]), f"{l['punt_yds'] / l['punts']:.1f}",
                        _num(l["punt_in20"]), _num(l["punt_long"])] for p, l in punt]))
    ret = [(p, l) for p, l in lines if l.get("kr") or l.get("pr")]
    out.append(_table("Returns", ["Player", "KR", "KR yds", "PR", "PR yds", "Long"],
                      [[name(p), _num(l["kr"]), _num(l["kr_yds"]), _num(l["pr"]), _num(l["pr_yds"]),
                        _num(max(l["kr_long"], l["pr_long"]))] for p, l in ret]))
    return "".join(out)


def team_stats_html(game):
    box = game.box
    home, away = game.teams
    a, h = box.team[1], box.team[0]

    def top(t):
        s = int(round(t["top"]))
        return f"{s // 60}:{s % 60:02d}"

    def pct(c, n):
        return f"{_num(c)}-{_num(n)}"

    def net_pass(t):
        return _num(t["pass_yds"] - t["sacked_yds"])

    rows = [
        ("First downs", _num(a["fd_rush"] + a["fd_pass"] + a["fd_pen"]), _num(h["fd_rush"] + h["fd_pass"] + h["fd_pen"])),
        ("   Rushing / Passing / Penalty", f"{_num(a['fd_rush'])} / {_num(a['fd_pass'])} / {_num(a['fd_pen'])}",
         f"{_num(h['fd_rush'])} / {_num(h['fd_pass'])} / {_num(h['fd_pen'])}"),
        ("Third downs", pct(a["third_conv"], a["third_att"]), pct(h["third_conv"], h["third_att"])),
        ("Fourth downs", pct(a["fourth_conv"], a["fourth_att"]), pct(h["fourth_conv"], h["fourth_att"])),
        ("Total plays", _num(a["plays"]), _num(h["plays"])),
        ("Total yards", _num(a["total_yds"]), _num(h["total_yds"])),
        ("Yards per play", f"{a['total_yds'] / a['plays']:.1f}" if a["plays"] else "0.0",
         f"{h['total_yds'] / h['plays']:.1f}" if h["plays"] else "0.0"),
        ("Rushing (att-yds)", f"{_num(a['rush_att'])}-{_num(a['rush_yds'])}", f"{_num(h['rush_att'])}-{_num(h['rush_yds'])}"),
        ("Passing (comp/att)", f"{_num(a['pass_cmp'])}/{_num(a['pass_att'])}", f"{_num(h['pass_cmp'])}/{_num(h['pass_att'])}"),
        ("Net passing yards", net_pass(a), net_pass(h)),
        ("Sacked (yds lost)", f"{_num(a['sacked'])}-{_num(a['sacked_yds'])}", f"{_num(h['sacked'])}-{_num(h['sacked_yds'])}"),
        ("Turnovers", _num(a["int_thrown"] + a["fum_lost"]), _num(h["int_thrown"] + h["fum_lost"])),
        ("   Interceptions / Fumbles lost", f"{_num(a['int_thrown'])} / {_num(a['fum_lost'])}",
         f"{_num(h['int_thrown'])} / {_num(h['fum_lost'])}"),
        ("Penalties (yds)", f"{_num(a['penalties'])}-{_num(a['penalty_yds'])}", f"{_num(h['penalties'])}-{_num(h['penalty_yds'])}"),
        ("Red zone (TD/trips)", pct(a["rz_td"], a["rz_trips"]), pct(h["rz_td"], h["rz_trips"])),
        ("Punts (avg)", f"{_num(a['punts'])} ({a['punt_yds'] / a['punts']:.1f})" if a["punts"] else "0",
         f"{_num(h['punts'])} ({h['punt_yds'] / h['punts']:.1f})" if h["punts"] else "0"),
        ("Time of possession", top(a), top(h)),
    ]
    body = "".join(f"<tr><td>{escape(k)}</td><td>{escape(str(x))}</td><td>{escape(str(y))}</td></tr>" for k, x, y in rows)
    return (f'<table class="box-table team-stats"><thead><tr><th></th><th>{escape(away.abbrev)}</th>'
            f'<th>{escape(home.abbrev)}</th></tr></thead><tbody>{body}</tbody></table>')


def line_score_html(game):
    home, away = game.teams
    qp = game.box.quarter_points
    n = max(4, len(qp[0]))
    head = "".join(f"<th>{i + 1 if i < 4 else 'OT'}</th>" for i in range(n))

    def row(team, idx):
        cells = "".join(f"<td>{qp[idx][i] if i < len(qp[idx]) else 0}</td>" for i in range(n))
        return f"<tr><td>{escape(team.abbrev)}</td>{cells}<td><b>{game.state.score[idx]}</b></td></tr>"

    return (f'<table class="box-table line-score"><thead><tr><th></th>{head}<th>Total</th></tr></thead>'
            f'<tbody>{row(away, 1)}{row(home, 0)}</tbody></table>')


def scoring_html(game):
    home, away = game.teams
    rows = []
    for sc in game.box.scoring:
        team = game.teams[sc["team"]]
        q = sc["qtr"] if sc["qtr"] <= 4 else "OT"
        rows.append([f"Q{q} {T.clock_text(sc['clock'])}", team.abbrev, sc["text"],
                     f"{away.abbrev} {sc['score'][0]}, {home.abbrev} {sc['score'][1]}"])
    return _table("Scoring summary", ["Time", "Team", "Play", "Score"], rows, empty="No scoring yet",
                  left=(0, 1, 2))


def drives_html(game):
    rows = []
    drives = list(game.box.drives)
    if game._drive is not None:
        d = dict(game._drive)
        d["result"] = d["result"] or "In progress"
        drives.append(d)
    for d in drives:
        team = game.teams[d["team"]]
        opp = game.teams[1 - d["team"]]
        t = int(round(d["time"]))
        q = d["qtr"] if d["qtr"] <= 4 else "OT"
        rows.append([team.abbrev, f"Q{q} {T.clock_text(d['clock'])}", T.spot(d["start_yl"], team.abbrev, opp.abbrev),
                     d["plays"], _num(d["yards"]), f"{t // 60}:{t % 60:02d}", d["result"]])
    return _table("Drive chart", ["Team", "Started", "Start", "Plays", "Yards", "Time", "Result"], rows,
                  empty="No drives yet", left=(0, 1, 2, 6))


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

class GameTabControls:
    """What other screens can ask of the Game tab."""

    def __init__(self, watch, busy, refresh):
        self.watch = watch        # start watching your game this week
        self.busy = busy          # True while a season game is being watched
        self.refresh = refresh    # redraw the "This week" line


# Before kickoff: the two teams side by side (Oct 22, "spruce up the UI").
TALE_CSS = """
<style>
  .tale { max-width: 980px; background: var(--paper); border: 1px solid var(--line); border-top: 3px solid var(--turf);
          border-radius: 3px; box-shadow: 0 1px 3px rgba(20, 40, 30, .08); overflow: hidden; }
  .tale-top { display: grid; grid-template-columns: 1fr auto 1fr; background: #18222B; color: white; }
  .tale-side { padding: 12px 18px; display: flex; flex-direction: column; }
  .tale-side.r { text-align: right; align-items: flex-end; }
  .tale-ab { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 46px; line-height: 1; }
  .tale-nm { font-size: 15px; opacity: .9; }
  .tale-rec { font-size: 13px; opacity: .7; }
  .tale-side.you .tale-ab { color: #F5C518; }
  .tale-mid { display: flex; align-items: center; padding: 0 22px; font-family: 'Barlow Condensed', sans-serif;
              font-weight: 700; font-size: 20px; letter-spacing: .1em; color: #F5C518; background: rgba(255,255,255,.06); }
  .tale-row { display: grid; grid-template-columns: 1fr 220px 1fr; padding: 6px 18px; border-top: 1px solid #EEF1EC;
              font-size: 14.5px; font-variant-numeric: tabular-nums; align-items: center; }
  .tale-row > :first-child { text-align: left; }
  .tale-row > :nth-child(2) { text-align: center; font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
                              font-size: 13.5px; color: var(--ink-soft); text-transform: uppercase; letter-spacing: .05em; }
  .tale-row > :last-child { text-align: right; }
  .tale-row .edge { font-weight: 700; color: #23703A; }
</style>
"""


# The call panel (Take over play calling).
CALL_CSS = """
<style>
  .call-panel { max-width: 1180px; background: var(--paper); border: 1px solid var(--line);
                border-left: 4px solid var(--flag); border-radius: 3px; padding: 10px 14px;
                box-shadow: 0 1px 3px rgba(20, 40, 30, .10); }
  .call-head { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 20px;
               letter-spacing: .03em; color: var(--ink); }
  .call-head .side { background: var(--turf); color: white; border-radius: 3px; padding: 1px 8px;
                     margin-right: 8px; font-size: 15px; letter-spacing: .08em; }
  .call-head .side.def { background: #9B2C2C; }
  .call-staff { font-size: 14px; color: var(--ink-soft); }
  .call-staff b { color: var(--ink); }
  .call-warn { font-size: 13.5px; color: #8A5A00; background: #FFF6D6; border: 1px solid #F0D98A;
               border-radius: 3px; padding: 2px 8px; }
  .call-btn.suggested { box-shadow: inset 0 0 0 2px var(--flag); }
  .call-legend { font-size: 12.5px; color: var(--ink-soft); }
  .pbp-yourcall { display: inline-block; font-size: 11.5px; font-weight: 700; letter-spacing: .05em;
                  background: var(--flag); color: var(--ink); border-radius: 2px; padding: 0 5px;
                  margin-right: 6px; text-transform: uppercase; }
</style>
"""


def _unit_avg(league, tid, starters, unit):
    from engine.scale import seen
    from . import theme
    ps = [p for p in league.team_players(tid) if p.id in starters and theme.unit_of(p.position) == unit
          and p.position not in ("K", "P", "LS")]
    return round(sum(seen(league, p) for p in ps) / len(ps)) if ps else None


def tale_html(league, g, you):
    """Away team on the left, home on the right; the better number in each row in green."""
    from engine import formatting as fmt
    from engine.scale import seen
    from .state import team_starter_ids
    rec = season.records(league)
    pre = season.is_preseason_game(g)
    sides = []
    for tid in (g["away"], g["home"]):
        r = rec[tid]
        gp = max(1, r["w"] + r["l"] + r["t"])
        starters = team_starter_ids(tid)
        qb = next((p for p in league.team_players(tid) if p.id in starters and p.position == "QB"), None)
        sides.append({"t": league.team(tid), "r": r, "gp": r["w"] + r["l"] + r["t"],
                      "pf": r["pf"] / gp, "pa": r["pa"] / gp,
                      "off": _unit_avg(league, tid, starters, "Offense"),
                      "def": _unit_avg(league, tid, starters, "Defense"),
                      "qb": qb, "qbr": seen(league, qb) if qb else None,
                      "last5": r["results"][-5:]})
    a, h = sides

    def row(label, va, vh, text=str, higher_better=True):
        ea = eh = ""
        if va is not None and vh is not None and va != vh:
            better_a = (va > vh) == higher_better
            ea, eh = ("edge", "") if better_a else ("", "edge")
        ta = text(va) if va is not None else "-"
        th = text(vh) if vh is not None else "-"
        return f'<div class="tale-row"><span class="{ea}">{ta}</span><span>{label}</span><span class="{eh}">{th}</span></div>'

    def wl(res):
        return "".join(f'<span class="wl-box wl-{x}">{x}</span>' for x in res) or "-"

    def side(s, cls):
        recs = "" if pre else season.record_text(s["r"])
        return (f'<div class="tale-side {cls}{" you" if s["t"].id == you else ""}"><span class="tale-ab">'
                f'{escape(s["t"].abbrev)}</span><span class="tale-nm">{escape(s["t"].name)}</span>'
                f'<span class="tale-rec">{recs}</span></div>')
    rows = ""
    if a["gp"] and h["gp"] and not pre:
        rows += row("Points per game", a["pf"], h["pf"], lambda v: f"{v:.1f}")
        rows += row("Points allowed per game", a["pa"], h["pa"], lambda v: f"{v:.1f}", higher_better=False)
        rows += (f'<div class="tale-row"><span>{wl(a["last5"])}</span><span>Last 5</span>'
                 f'<span>{wl(h["last5"])}</span></div>')
    rows += row("Offense starters", a["off"], h["off"], fmt.skill)
    rows += row("Defense starters", a["def"], h["def"], fmt.skill)
    qa = f'{escape(a["qb"].name)}, {fmt.skill(a["qbr"])}' if a["qb"] else "-"
    qh = f'{escape(h["qb"].name)}, {fmt.skill(h["qbr"])}' if h["qb"] else "-"
    ea = eh = ""
    if a["qbr"] is not None and h["qbr"] is not None and a["qbr"] != h["qbr"]:
        ea, eh = ("edge", "") if a["qbr"] > h["qbr"] else ("", "edge")
    rows += f'<div class="tale-row"><span class="{ea}">{qa}</span><span>Starting QB</span><span class="{eh}">{qh}</span></div>'
    mid = "VS" if g.get("neutral") else "AT"
    return (f'<div class="tale"><div class="tale-top">{side(a, "")}<div class="tale-mid">{mid}</div>'
            f'{side(h, "r")}</div>{rows}</div>')


def build_game_tab(on_season_game_done=None, on_open_summary=None):
    """Builds the Game tab. on_season_game_done is called after a season game
    you watched has been recorded; on_open_summary(game id) opens a played
    game's summary (box score) in the Schedule tab. Returns GameTabControls."""
    league = state.league
    viewer = Viewer()
    viewer.season_game = None       # the scheduled game being watched, if any

    with ui.column().classes("w-full px-8 py-4 gap-3"):
        @ui.refreshable
        def this_week():
            with ui.row().classes("items-center gap-4 w-full"):
                if season.season_over(league):
                    ui.label("The regular season is over.").classes("condensed text-2xl")
                    return
                pre = season.in_preseason(league)
                g = season.team_current_game(league, league.user_team_id) if league.user_team_id else None
                ui.label(season.week_label(league)).classes("condensed text-2xl")
                if g is None:
                    if pre and league.pre_week == 1:
                        txt = "Only the Hall of Fame Game is played this week; your team isn't in it."
                    else:
                        txt = "Your team has a preseason bye this week." if pre else "Your team has a bye this week."
                    ui.label(txt).classes("condensed text-xl")
                    return
                h, a = league.team(g["home"]), league.team(g["away"])
                joiner = "vs" if g.get("neutral") else "at"
                tag = ""
                if g.get("kind") == "hof":
                    tag = " (Hall of Fame Game, Canton, Ohio)"
                elif g.get("kind") == "glory_bowl":
                    tag = f" ({season.site_text(league, g)})"
                if g["played"]:
                    ui.label(f"Final: {a.name} {g['away_score']}, {h.name} {g['home_score']}"
                             + (" (OT)" if g["overtime"] else "")).classes("condensed text-xl")
                    if on_open_summary:
                        ui.button("Game summary", on_click=lambda gid=g["id"]: on_open_summary(gid)) \
                            .props("no-caps unelevated color=green-10") \
                            .tooltip("Box score, team stats, scoring and drives")
                    ui.label("Sim week plays the rest of the league.").classes("legend")
                    return
                ui.label(f"{a.name} {joiner} {h.name}{tag}").classes("condensed text-xl")
                if viewer.season_game is not None and not viewer.finished:
                    ui.label("Watching now, below. The result counts when the game ends.").classes("legend")
                    return
                ui.button("Watch this game", on_click=lambda: watch_season_game()) \
                    .props("no-caps unelevated color=green-10")
                if pre:
                    ui.label("Preseason: starters play only part of the game, and the result doesn't "
                             "count in the standings.").classes("legend")
                else:
                    ui.label("It counts: the result goes into the schedule and standings.").classes("legend")
            if g is not None and not g["played"]:
                ui.html(tale_html(league, g, league.user_team_id), sanitize=False).classes("w-full")
        ui.add_head_html(TALE_CSS)
        this_week()

        board = ui.html("").classes("w-full")
        field = ui.html("").classes("w-full")

        with ui.row().classes("items-center gap-3") as controls:
            play_btn = ui.button("Pause", on_click=lambda: toggle()).props("no-caps unelevated color=green-10")
            step_btn = ui.button("Next play", on_click=lambda: step(force=True)).props("no-caps outline color=green-10")
            ui.label("Speed").classes("condensed text-lg ml-4")
            speed_toggle = ui.toggle(list(SPEEDS), value=viewer.speed, on_change=lambda e: set_speed(e.value)) \
                .props("no-caps dense toggle-color=green-10")
            end_btn = ui.button("Sim to the end", on_click=lambda: sim_to_end()).props("no-caps flat color=green-10")
            take_box = ui.checkbox("Take over play calling", value=False, on_change=lambda e: set_take_over(e.value)) \
                .props("color=green-10").classes("ml-4")
            with take_box:
                ui.tooltip("Call your team's plays, offense and defense, from the next snap. Untick to hand "
                           "play calling back to your staff; tick and untick as often as you like.") \
                    .props("delay=900")
        controls.set_visibility(False)

        ui.add_head_html(CALL_CSS)
        call_box = ui.column().classes("w-full gap-1 call-panel")
        call_box.set_visibility(False)

        with ui.row().classes("w-full gap-6 items-start no-wrap") as main:
            with ui.column().classes("gap-1").style("flex: 1 1 58%; min-width: 0"):
                ui.label("Play-by-play").classes("panel-heading")
                with ui.element("div").classes("pbp-scroll").props("id=pbp-log"):
                    log_box = ui.column().classes("w-full gap-0")
            with ui.column().classes("gap-1").style("flex: 1 1 42%; min-width: 0"):
                with ui.tabs().props("no-caps dense align=left active-color=green-10 indicator-color=green-10") as stat_tabs:
                    t_team = ui.tab("Team stats")
                    t_away = ui.tab("Away box")
                    t_home = ui.tab("Home box")
                    t_score = ui.tab("Scoring")
                    t_drives = ui.tab("Drives")
                with ui.tab_panels(stat_tabs, value=t_team).classes("w-full box-panels"):
                    with ui.tab_panel(t_team).classes("p-0"):
                        line_html = ui.html("")
                        team_html = ui.html("")
                    with ui.tab_panel(t_away).classes("p-0"):
                        away_html = ui.html("")
                    with ui.tab_panel(t_home).classes("p-0"):
                        home_html = ui.html("")
                    with ui.tab_panel(t_score).classes("p-0"):
                        score_html = ui.html("")
                    with ui.tab_panel(t_drives).classes("p-0"):
                        drive_html = ui.html("")
        main.set_visibility(False)

    timer = ui.timer(SPEEDS[viewer.speed], lambda: step(), active=False)

    # ---- actions -------------------------------------------------------
    def watch_season_game():
        g = season.team_current_game(league, league.user_team_id) if league.user_team_id else None
        if g is None or g["played"]:
            this_week.refresh()
            return
        if viewer.season_game is g and not viewer.finished:
            return          # already watching it: just keep going
        viewer.season_game = g
        begin(season.new_game(league, g, norms_for(league)))
        this_week.refresh()

    def caller(game, idx, kind, suggested):
        """Your team's play caller: ask the screen while the box is ticked, else the staff calls it."""
        return ASK if viewer.take_over else None

    def begin(game):
        viewer.game = game
        viewer.my_idx = next((i for i, t in enumerate(game.teams) if t.id == league.user_team_id), None)
        if viewer.my_idx is not None:
            game.callers[viewer.my_idx] = caller
        take_box.set_visibility(viewer.my_idx is not None)
        viewer.your_call = None
        viewer.gen = viewer.game.events()
        viewer.last_drive = None
        viewer.shown = 0
        viewer.finished = False
        log_box.clear()
        ui.run_javascript("const e=document.getElementById('pbp-log'); if (e) { e.dataset.stick='1'; }")
        t_away.props(f'label="{viewer.game.teams[1].abbrev} box"')
        t_home.props(f'label="{viewer.game.teams[0].abbrev} box"')
        controls.set_visibility(True)
        main.set_visibility(True)
        viewer.running = True
        play_btn.text = "Pause"
        play_btn.enable()
        step_btn.enable()
        end_btn.enable()
        timer.interval = SPEEDS[viewer.speed]
        timer.activate()
        refresh_all()

    def set_take_over(on):
        viewer.take_over = bool(on)
        game = viewer.game
        if not on and game is not None and game.awaiting:
            answer(None)            # the call on screen goes to the staff; the game runs on

    def show_call():
        """The menu for the call the game is waiting for."""
        game = viewer.game
        p = playcalling.prompt(game)
        call_box.clear()
        if p is None:
            call_box.set_visibility(False)
            return
        st = game.state
        me, them = game.teams[p["team"]], game.teams[1 - p["team"]]
        off, deff = game.teams[st.poss], game.teams[1 - st.poss]
        defense = p["kind"] == "defense"
        if p["kind"] == "pat":
            where = "Try after touchdown"
        else:
            where = f"{T.down_text(st.down, st.togo, st.yl)} at {T.spot(st.yl, off.abbrev, deff.abbrev)}"
        period = f"Q{st.qtr}" if st.qtr <= 4 else "OT"
        score = f"{me.abbrev} {st.score[p['team']]}, {them.abbrev} {st.score[1 - p['team']]}"
        who = f'{escape(p["staff_title"])} <b>{escape(p["staff_name"])}</b>' if p["staff_name"] else "Your staff"
        with call_box:
            ui.html(f'<div class="call-head"><span class="side{" def" if defense else ""}">'
                    f'{"DEFENSE" if defense else "OFFENSE"}</span>Your call: {escape(where)} &middot; {period} '
                    f'{T.clock_text(st.clock)} &middot; {escape(score)}</div>')
            with ui.row().classes("items-center gap-3"):
                ui.html(f'<div class="call-staff">{who} suggests: <b>{escape(p["suggested_label"])}</b></div>')
                ui.button("Coach's call", on_click=lambda: answer(None)) \
                    .props("no-caps unelevated dense color=green-10").classes("px-3") \
                    .tooltip("Run the play your staff suggests")
            if p["keying"]:
                ui.html(f'<div class="call-warn">{who}: "They\'re keying on {escape(", ".join(p["keying"]))}. '
                        f'Mix it up."</div>')
            with ui.row().classes("gap-2 flex-wrap"):
                for key, label in p["options"]:
                    b = ui.button(label + (" ★" if key in p["fits"] else ""), on_click=lambda k=key: answer(k)) \
                        .props("no-caps outline dense color=green-10").classes("call-btn px-3")
                    if key == p["suggested"]:
                        b.classes("suggested")
                        b.tooltip("Your staff's suggestion")
                    elif key in p["fits"]:
                        b.tooltip("Fits your coordinator's scheme: runs a little better")
            ui.label("★ fits your coordinator's scheme. The other side reads your calls: call something "
                     "more often than your staff would and they start to expect it.").classes("call-legend")
        call_box.set_visibility(True)

    def answer(key):
        game = viewer.game
        if game is None or not game.awaiting:
            return
        p = playcalling.prompt(game)
        viewer.your_call = None if key is None else dict(p["options"]).get(key, key)
        game.answer = key
        call_box.set_visibility(False)
        with log_box:               # (the clicked button is about to be cleared away with the menu)
            step(force=True, answered=True)     # the play you called
            if not game.awaiting:
                call_box.clear()
        if viewer.running and not viewer.finished and viewer.game is not None and not viewer.game.awaiting:
            timer.activate()

    def toggle():
        if viewer.finished:
            return
        viewer.running = not viewer.running
        play_btn.text = "Pause" if viewer.running else "Resume"
        if viewer.running and not viewer.game.awaiting:
            timer.activate()
        else:
            timer.deactivate()

    def set_speed(name):
        viewer.speed = name
        timer.interval = SPEEDS[name]

    def advance():
        """Pull the next event from the engine. Returns False at the end."""
        try:
            next(viewer.gen)
            return True
        except StopIteration:
            return False

    def render_new_events():
        game = viewer.game
        new = game.log[viewer.shown:]
        with log_box:
            for ev in new:
                if ev.kind in ("play", "penalty", "punt", "fg") and ev.drive != viewer.last_drive:
                    viewer.last_drive = ev.drive
                    ui.html(drive_header_html(game, ev)).classes("w-full")
                html = event_html(game, ev)
                if viewer.your_call and ev.kind in ("play", "punt", "fg", "two_point", "xp", "penalty"):
                    # Tag the play you called.
                    html = html.replace('<div class="pbp-text">', '<div class="pbp-text"><span class="pbp-yourcall">'
                                        f'Your call: {escape(viewer.your_call)}</span>', 1)
                    viewer.your_call = None
                ui.html(html).classes("w-full")
        viewer.shown = len(game.log)
        # Follow the newest play, unless you've scrolled up to read earlier plays.
        ui.run_javascript(FOLLOW_JS)

    def step(force=False, answered=False):
        if viewer.game is None or viewer.finished:
            timer.deactivate()
            return
        if viewer.game.awaiting and not answered:
            return                  # waiting for your call
        if not viewer.running and not force:
            return
        # Skip ahead through events that don't need their own beat (the try
        # after a touchdown shows with the touchdown).
        more = advance()
        while more and viewer.game.log and viewer.game.log[-1].kind in ("injury",):
            more = advance()
        render_new_events()
        refresh_all()
        if not more or viewer.game.finished:
            finish()
            return
        if viewer.game.awaiting:
            timer.deactivate()      # the game waits for your call
            step_btn.disable()
            show_call()
        else:
            step_btn.enable()

    def sim_to_end():
        if viewer.game is None or viewer.finished:
            return
        timer.deactivate()
        viewer.take_over = False
        take_box.value = False
        call_box.set_visibility(False)
        if viewer.game.awaiting:
            viewer.game.answer = None
        while advance():
            if viewer.game.awaiting:
                viewer.game.answer = None
        render_new_events()
        refresh_all()
        finish()

    def finish():
        viewer.finished = True
        viewer.running = False
        timer.deactivate()
        play_btn.text = "Game over"
        play_btn.disable()
        step_btn.disable()
        end_btn.disable()
        call_box.set_visibility(False)
        g = viewer.season_game
        if g is not None and viewer.game.finished and not g["played"]:
            season.record_game(league, g, viewer.game)
            viewer.season_game = None
            # The game is over: clear the live view. The "This week" line now
            # shows the final score and a Game summary button.
            clear_view()
            mark_changed()
            ui.notify("Final score recorded in the schedule" +
                      (" (preseason: not in the standings)." if season.is_preseason_game(g) else " and standings."),
                      type="positive")
            this_week.refresh()
            if on_season_game_done:
                on_season_game_done()

    def refresh_all():
        game = viewer.game
        board.content = scoreboard_html(game)
        field.content = field_html(game)
        line_html.content = line_score_html(game)
        team_html.content = team_stats_html(game)
        away_html.content = box_score_html(game, 1)
        home_html.content = box_score_html(game, 0)
        score_html.content = scoring_html(game)
        drive_html.content = drives_html(game)

    def clear_view():
        viewer.game = None
        viewer.gen = None
        timer.deactivate()
        log_box.clear()
        board.content = ""
        field.content = ""
        call_box.set_visibility(False)
        call_box.clear()
        controls.set_visibility(False)
        main.set_visibility(False)

    def refresh_tab():
        """After simming: the week has moved on, so drop any finished game
        still on screen and redraw the 'This week' line."""
        if viewer.game is not None and viewer.finished:
            clear_view()
        this_week.refresh()

    def busy():
        return viewer.season_game is not None and viewer.game is not None and not viewer.finished

    return GameTabControls(watch=watch_season_game, busy=busy, refresh=refresh_tab)
