# draft_page.py
# The Draft tab (Step 8's screens; Blake, Oct 23: scout the class before the draft,
# fewer and harder scouting choices, interviews read the person and his football
# mind, combine results in real units with where they rank):
#   Prospects    this year's class, from the start of the league year: your staff's
#                grade of each prospect as a range that narrows as you scout, and the
#                scouting itself (film study, cross-checks, top-30 visits, interviews),
#                until the draft starts
#   Draft room   the draft, pick by pick from pick 1: who's on the clock, your staff's
#                board, your needs, trade offers and your own offers; the draft runs itself
#                at the speed you choose (Pause / Slow / Normal / Fast / To my pick) and
#                waits when you're on the clock; draft a player, let your staff pick,
#                step one pick, or let your staff finish
#   Results      every pick of this draft (or an earlier one) and the draft-day trades
# A new league's startup draft (every team drafts its 53-man roster) gets its own room
# here too. Screens read the engine only (draft_day.py, scouting.py).
#
# The look (Blake, Oct 22: "much less like a google form"; his reference is FOF8's
# Amateur Draft Preview): one dense board table across the page with a green header
# row, combine results in real units colored by where they rank at the position
# (FOF8's colors: red superior, blue great, green poor), a column of big action
# buttons on the right, and a running pick log under the table. A prospect's full
# report, the draft order, trades and needs open as pop-ups (popups.py).
# Click a row to select him, double-click (or click his name) for his report,
# right-click (or click the star) to mark him for later.

import asyncio
import time
import traceback
from html import escape

from nicegui import ui

from engine import draft_day as DD
from engine import formatting as fmt
from engine import positions as pos
from engine import saves
from engine import scouting as S
from engine import season as SEASON
from engine.draft import ROSTER_SIZE, STARTUP_SNAKE
from engine.scale import seen     # your staff's evaluation (Oct 24; engine/evaluation.py)
from engine.teams import ROSTER_TEMPLATE
from . import popups, theme
from .state import state, mark_changed

POSITION_ORDER = list(ROSTER_TEMPLATE)
PLURAL = {"T": "tackles", "G": "guards", "C": "centers", "S": "safeties", "K": "kickers", "P": "punters",
          "LS": "long snappers"}
STEP_COST = {"film": f"{S.FILM_HOURS} hours", "cross": f"{S.CROSS_CHECK_HOURS} hours",
             "visit": "1 visit", "interview": "1 interview"}
STEP_SHORT = {"film": f"Film ({S.FILM_HOURS} h)", "cross": f"Cross-check ({S.CROSS_CHECK_HOURS} h)",
              "visit": "Top-30 visit", "interview": "Interview"}
STEP_HELP = {
    "film": "Your scouts study his college tape: clears most of what the whole league has wrong about him.",
    "cross": "A second scout checks the first one's work: clears more of what's still wrong.",
    "visit": "He visits your building (top-30 visit): the best look your staff gets at him.",
    "interview": ("Your staff's read on the person (leadership, loyalty, wanting to win, how steady he is). "
                  "It almost always turns up a character red flag if he has one, and how he talks football "
                  "sharpens his grade a little."),
}

# Combine colors (FOF8's, from Blake's reference): where a result ranks at his position
# in this class (or, in the startup draft, among every player at his position).
SUPERIOR_TOP = 0.10          # best 10% at his position: red ("superior")
GREAT_TOP = 0.25             # the rest of the best 25%: blue ("great")
POOR_BOTTOM = 0.20           # worst 20%: green ("poor")

# Combine columns: key, column label, what it is (header tooltip).
COMBINE_COLS = [
    ("forty", "40", "40-yard dash, seconds"),
    ("bench", "Bench", "Bench press: reps of 225 lbs"),
    ("vertical", "Vert", "Vertical jump, inches"),
    ("broad", "Broad", "Broad jump, feet and inches"),
    ("cone", "3-cone", "3-cone drill, seconds"),
    ("shuttle", "Shuttle", "20-yard shuttle, seconds"),
    ("intel", "Intel", "Intelligence test, out of 50"),
    ("drill", "Drill", "Position drill, out of 100"),
]

# Draft speed (Blake, Oct 22: "it shouldnt just be skip pick/teleports to your pick. It
# should start at 1st overall and then you should be able to select a draft speed... you
# watch pick by pick until its your turn"): seconds between picks while the draft runs
# itself. "To my pick" makes the picks all at once; every speed waits when you're on the
# clock. The speed you last ran it at is remembered (saves/settings.json).
SPEEDS = {"Pause": None, "Slow": 4.0, "Normal": 2.0, "Fast": 0.5, "To my pick": 0.0}
SPEED_HELP = {
    "Pause": "Stop the draft after the pick being made",
    "Slow": "A pick about every 4 seconds",
    "Normal": "A pick about every 2 seconds",
    "Fast": "A pick about every half second",
    "To my pick": "Every pick until you're on the clock, at once",
}
TICK = 0.1          # how often the draft room's timer checks whether the next pick is due (seconds)
BURST = 8           # "To my pick": picks made between screen updates


def _plural(position):
    return PLURAL.get(position, position + "s")


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return str(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


async def _maybe(result):
    """Await a callback's result if it's a coroutine (main_page's Next is async)."""
    if hasattr(result, "__await__"):
        await result


def range_text(r):
    """(61, 68) -> 'Good (61-68)', by the middle of the range."""
    lo, hi = r
    word = fmt.skill_word((lo + hi) // 2)
    return f"{word} ({lo}-{hi})" if lo != hi else f"{word} ({lo})"


def range_color(r):
    return theme.RATING_COLORS[fmt.skill_word((r[0] + r[1]) // 2)]


def scouted_html(steps):
    out = []
    for k, letter in (("film", "F"), ("cross", "C"), ("visit", "V"), ("interview", "I")):
        on = k in steps
        out.append(f'<span title="{S.STEP_NAMES[k]}{"" if on else ": not yet"}" class="sc{" on" if on else ""}">'
                   f'{letter}</span>')
    return "".join(out)


def _team_abbrev(league, tid):
    return league.team(tid).abbrev


def _pos_tag(position):
    return f'<span class="pos-tag" style="{theme.position_style(position)}">{position}</span>'


# ---------------------------------------------------------------------------
# Combine cells: real units, colored by rank at the position
# ---------------------------------------------------------------------------

def _tier(rank, n):
    """'sup' / 'great' / 'poor' / '' for a result ranked `rank` of `n` at his position."""
    if not rank or not n or n < 3:
        return ""
    if rank <= max(1, round(n * SUPERIOR_TOP)):
        return "sup"
    if rank <= max(1, round(n * GREAT_TOP)):
        return "great"
    if rank > n - max(1, round(n * POOR_BOTTOM)):
        return "poor"
    return ""


def _combine_value(p, key):
    if key == "intel":
        return p.intel_test
    if key == "drill":
        return p.position_drill
    return p.combine.get(key)


def _short(key, v):
    """The number as the table shows it, in its real unit (the header says which)."""
    if v is None:
        return "—"
    if key in ("forty", "cone", "shuttle"):
        return f"{v:.2f}"
    if key == "vertical":
        return f'{v:g}"'
    if key == "broad":
        v = round(v)
        return f"{v // 12}'{v % 12:02d}\""
    return str(v)


def _long(key, v):
    if key == "intel":
        return f"{v} out of 50"
    if key == "drill":
        return f"{v} out of 100"
    return fmt.drill(key, v)


def combine_fields(p, ranks):
    """Row fields for the combine columns: c_ (sort), t_ (text), k_ (color class), h_ (tooltip)."""
    out = {}
    pl = _plural(p.position)
    for key, _label, what in COMBINE_COLS:
        v = _combine_value(p, key)
        if v is None:
            out.update({f"c_{key}": 99.0 if key in S.LOW_IS_FAST else -1.0, f"t_{key}": "—",
                        f"k_{key}": "dnt", f"h_{key}": f"{what}: did not test"})
            continue
        rk = ranks.get(key)
        tip = _long(key, v) + (f" ({ordinal(rk[0])} of {rk[1]} {pl})" if rk else "")
        out.update({f"c_{key}": v, f"t_{key}": _short(key, v), f"k_{key}": _tier(*rk) if rk else "",
                    f"h_{key}": tip})
    return out


def combine_columns():
    return [{"name": key, "label": label, "field": f"c_{key}", "sortable": True, "align": "right",
             "tip": what + ". Red: superior (best 10% at his position), blue: great (best 25%), green: poor "
                           "(worst 20%)."}
            for key, label, what in COMBINE_COLS]


def _col(name, label, field, tip, align="left", **extra):
    return dict({"name": name, "label": label, "field": field, "sortable": True, "align": align, "tip": tip},
                **extra)


HEIGHT_FMT = {":format": 'v => Math.floor(v / 12) + "-" + (v % 12)'}

PROSPECT_COLS = [
    _col("mark", "Mark", "marked", "Your marks. Right-click a row (or click the star) to mark a player for "
                                   "later.", align="center"),
    _col("board", "Board", "board", "Your staff's board: where he ranks among the prospects left (talent, "
                                    "position value and age; red flags it knows about)", align="right"),
    _col("media", "Media", "media", "The media's big board (it doesn't know about red flags)", align="right"),
    _col("name", "Name", "name", "Click his name (or double-click the row) for his full report"),
    _col("pos", "Pos", "pos_sort", "Position"),
    _col("age", "Age", "age", "Age on draft day", align="right"),
    _col("height", "Ht", "height", "Height (feet-inches)", align="right", **HEIGHT_FMT),
    _col("weight", "Wt", "weight", "Weight (lbs)", align="right"),
    _col("pot_cloud", "Potential", "pot_mid", "Your staff's view of how good he can become: where the cloud sits "
                                              "is their best guess, how wide and blurry it is is how unsure they are "
                                              "(scouting tightens it). Sort to rank by their best guess."),
    _col("devl", "Devl", "devl", "Developed %: how much of his potential he arrives with, your staff's estimate "
                                 "(it sharpens as you scout)", align="right", **{":format": 'v => v + "%"'}),
    _col("take", "Staff take", "take_sort", "Your staff's impression vs his buzz, once your scouts have watched his "
                                            "film: Hidden gem, Sleeper, Fair value, Wild card, Overhyped, Fool's "
                                            "gold. It's their opinion: better staffs are wrong less."),
] + combine_columns() + [
    _col("scouted", "Scouted", "scout_n", "What your scouts have done: F film study, C cross-check, V top-30 "
                                          "visit, I interview"),
    _col("flag", "Flag", "flag", "Red flags your staff knows about (medical: every team knows; character: "
                                 "found in your interview)"),
    _col("college", "College", "college", "College"),
]

STARTUP_COLS = [
    _col("mark", "Mark", "marked", "Your marks. Right-click a row (or click the star) to mark a player for "
                                   "later.", align="center"),
    _col("board", "Board", "board", "Your staff's board for your next pick (talent, position value and "
                                    "your roster's open spots)", align="right"),
    _col("name", "Name", "name", "Click his name (or double-click the row) for his player card"),
    _col("pos", "Pos", "pos_sort", "Position"),
    _col("age", "Age", "age", "Age on September 1", align="right"),
    _col("exp", "Exp", "exp", "Seasons in the league (R = rookie)", align="right",
         **{":format": 'v => v === 0 ? "R" : v'}),
    _col("height", "Ht", "height", "Height (feet-inches)", align="right", **HEIGHT_FMT),
    _col("weight", "Wt", "weight", "Weight (lbs)", align="right"),
    _col("ovr", "Overall", "ovr", "Overall rating now"),
    _col("pot", "Potential", "pot", "How good he could become"),
] + combine_columns() + [
    _col("college", "College", "college", "College"),
]


def add_board_slots(table, rating_cells):
    """The board table's look: header tooltips, position badges, clickable names,
    rating swatches, colored combine numbers, marks. rating_cells: [(column, text
    field, color field)]."""
    table.add_slot("header-cell", r"""
        <q-th :props="props" :title="props.col.tip">{{ props.col.label }}</q-th>""")
    table.add_slot("body-cell-mark", r"""
        <q-td :props="props"><span class="mark" :class="{on: props.row.marked}"
          :title="props.row.marked ? 'Marked: click to unmark' : 'Click to mark him for later'"
          >{{ props.row.marked ? '★' : '☆' }}</span></q-td>""")
    table.add_slot("body-cell-name", r"""
        <q-td :props="props"><span class="pname">{{ props.row.name }}</span></q-td>""")
    table.add_slot("body-cell-pos", r"""
        <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
    table.add_slot("body-cell-scouted", r"""
        <q-td :props="props"><span v-html="props.row.scouted"></span></q-td>""")
    table.add_slot("body-cell-pot_cloud", r"""
        <q-td :props="props"><span v-html="props.row.pot_html"></span></q-td>""")
    table.add_slot("body-cell-take", r"""
        <q-td :props="props"><span v-if="props.row.take" class="take-chip" :title="props.row.take_tip"
          :style="{background: props.row.take_color}">{{ props.row.take }}</span></q-td>""")
    table.add_slot("body-cell-flag", r"""
        <q-td :props="props"><span v-if="props.row.flag" class="inj-tag inj-out">{{ props.row.flag }}</span></q-td>""")
    for col, text, color in rating_cells:
        table.add_slot(f"body-cell-{col}", f"""
            <q-td :props="props"><span class="rating num">
              <span class="swatch" :style="{{background: props.row.{color}}}"></span>
              {{{{ props.row.{text} }}}}</span></q-td>""")
    for key, _label, _what in COMBINE_COLS:
        table.add_slot(f"body-cell-{key}", f"""
            <q-td :props="props"><span class="cmb num" :class="'cmb-' + props.row.k_{key}"
              :title="props.row.h_{key}">{{{{ props.row.t_{key} }}}}</span></q-td>""")


# ---------------------------------------------------------------------------
# Table rows
# ---------------------------------------------------------------------------

def board_ranks(league):
    """{pid: place on your staff's board among the prospects not yet drafted}."""
    board = DD.board(league)
    ranked = sorted(DD.available(league), key=lambda p: board.get(p.id, -99), reverse=True)
    return {p.id: i + 1 for i, p in enumerate(ranked)}


def prospect_rows(league, players, marks=frozenset()):
    uid = league.user_team_id
    st = DD.stats(league)
    board_rank = board_ranks(league)
    media = DD.media_ranks(league)
    cr = DD.combine_ranks(league)
    rows = []
    for p in players:
        now, ceil = S.grade_ranges(league, uid, p, st)
        steps = S.done_steps(league, p.id)
        rep_flag = (S.known_flag(league, uid, p) or "").title()
        imp = S.impression(league, uid, p, st)
        row = {
            "id": p.id, "marked": p.id in marks, "board": board_rank.get(p.id, 999), "media": media.get(p.id, 999),
            "pos": p.position, "pos_style": theme.position_style(p.position),
            "pos_sort": POSITION_ORDER.index(p.position) * 1000 + board_rank.get(p.id, 999),
            "name": p.name, "age": round(_draft_age(league, p), 1),
            "college": p.college, "height": p.height, "weight": p.weight,
            "pot_html": mini_cloud(ceil), "pot_mid": (ceil[0] + ceil[1]) / 2,
            "devl": S.developed(league, uid, p),
            "scouted": scouted_html(steps), "scout_n": len(steps), "flag": rep_flag,
            "take": imp["word"] if imp else "", "take_color": imp["color"] if imp else "",
            "take_tip": imp["tip"] if imp else "", "take_sort": TAKE_ORDER.get(imp["key"] if imp else None, 9),
        }
        row.update(combine_fields(p, cr.get(p.id, {})))
        rows.append(row)
    return rows


def _draft_age(league, p):
    from datetime import date
    return (date(league.season, 4, 25) - p.birth_date).days / 365.25


def _marks(league):
    """Players you've marked (kept in the save with the draft: league.draft["marks"])."""
    d = getattr(league, "draft", None) or {}
    return frozenset(d.get("marks") or [])


def _toggle_mark(league, pid):
    d = getattr(league, "draft", None)
    if not d:
        return False
    marks = d.setdefault("marks", [])
    if pid in marks:
        marks.remove(pid)
        return False
    marks.append(pid)
    return True


# ---------------------------------------------------------------------------
# How your staff's knowledge looks (Blake, Oct 22: fuzzy cloud bars and a skill web
# that tighten as you scout; the staff's impression in scout slang)
# ---------------------------------------------------------------------------

TAKE_ORDER = {"gem": 0, "sleeper": 1, "wild": 2, "fair": 3, "hyped": 4, "fools": 5}
_PREV = {}          # pid -> the skill ranges last shown in his report (the clouds shrink from there)


def take_chip(imp, big=False):
    """Your staff's impression as a colored chip (or a note that film comes first)."""
    if not imp:
        return ('<span class="take-chip none" title="Your scouts form an opinion once they\'ve watched his '
                'film">No read yet</span>')
    return (f'<span class="take-chip{" big" if big else ""}" style="background:{imp["color"]}" '
            f'title="{escape(imp["tip"])}">{escape(imp["word"])}</span>')


POT_CLOUD = "#2F6FBF"             # one color for every cloud (a rating-tier color would give the band away)


def mini_cloud(r, big=False):
    """Your staff's read of his potential as a small cloud on a track, no number: where it
    sits is their best guess, how wide and blurry it is is how unsure they are (Blake,
    Oct 22: "youre supposed to visually guess and not know the exact number")."""
    w = max(3, r[1] - r[0])
    return (f'<span class="mcloud-track{" big" if big else ""}"><span class="mcloud" style="left:{r[0]}%;'
            f'width:{w}%;--c:{POT_CLOUD};filter:blur({_blur(w * 0.6)})"></span></span>')


def _blur(width):
    return f"{max(0.0, min(6.0, (width - 4) / 5)):.1f}px"


def cloud_row(label, pot, prev=None):
    """One skill as a fuzzy cloud on a 0-100 track: your staff's view of how good he can
    become at it (Blake, Oct 22: one bar, shrinking toward the staff's view of his
    potential; his Developed % says how much of it he arrives with). Wide and blurry =
    your staff isn't sure; it tightens into a sharp mark as you scout. prev: the range
    last shown, so the cloud visibly shrinks from there. No numbers, words or number
    tooltips: you judge him by eye, like FOF8."""
    r0 = prev or pot
    w, w0 = max(2, pot[1] - pot[0]), max(2, r0[1] - r0[0])
    style = (f"--l0:{r0[0]}%;--w0:{w0}%;--l1:{pot[0]}%;--w1:{w}%;--c:{POT_CLOUD};"
             f"--b0:{_blur(w0)};--b1:{_blur(w)}")
    mid = (pot[0] + pot[1]) / 2
    return (f'<div class="cloud-row"><span>{escape(label)}</span>'
            f'<div class="cloud-track"><div class="cloud pot" style="{style}"></div>'
            f'<div class="cloud-mid" style="left:{mid}%;opacity:{0.9 if pot[1] - pot[0] <= 6 else 0.0}"></div>'
            f'</div></div>')


def skill_web(skills, prev=None, size=270):
    """His skills as a web: the shaded band runs from the low to the high end of your
    staff's view of his potential at each skill, tightening into a crisp outline as you
    scout. skills: [(label, potential range)]; prev: {label: range} last shown, so the
    band shrinks from there."""
    import math
    n = len(skills)
    if n < 3:
        return ""
    cx = cy = size / 2
    rad = size / 2 - 46

    def pt(i, v):
        a = -math.pi / 2 + 2 * math.pi * i / n
        r = rad * max(0, min(100, v)) / 100
        return cx + r * math.cos(a), cy + r * math.sin(a)

    def poly(vals):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(vals)))

    def band(hi, lo):
        outer = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(hi))) + " Z"
        inner = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(lo))) + " Z"
        return outer + " " + inner
    p0 = prev or {}
    hi = [r[1] for _l, r in skills]
    lo = [r[0] for _l, r in skills]
    hi0 = [p0.get(lab, r)[1] for lab, r in skills]
    lo0 = [p0.get(lab, r)[0] for lab, r in skills]
    grid = "".join(f'<polygon points="{poly([g] * n)}" class="web-grid"/>' for g in (25, 50, 75, 100))
    spokes = "".join(f'<line x1="{cx}" y1="{cy}" x2="{pt(i, 100)[0]:.1f}" y2="{pt(i, 100)[1]:.1f}" class="web-grid"/>'
                     for i in range(n))
    labels = []
    for i, (lab, _r) in enumerate(skills):
        x, y = pt(i, 118)
        anchor = "middle" if abs(x - cx) < 8 else ("start" if x > cx else "end")
        short = lab.replace("Pass Rush ", "Rush ").replace("Coverage", "Cov.").replace("Passing", "Pass")
        labels.append(f'<text x="{x:.1f}" y="{y + 3:.1f}" text-anchor="{anchor}" class="web-label">{escape(short)}</text>')
    d1, d0 = band(hi, lo), band(hi0, lo0)
    pad = 70                       # room for the labels on the left and right
    return (f'<svg viewBox="{-pad} 0 {size + 2 * pad} {size}" class="skill-web" role="img" aria-label="Skill web">'
            f'{grid}{spokes}'
            f'<path d="{d1}" class="web-band" fill-rule="evenodd">'
            f'<animate attributeName="d" from="{d0}" to="{d1}" dur="0.9s" fill="freeze" calcMode="spline" '
            f'keySplines="0.2 0.8 0.3 1" keyTimes="0;1"/></path>'
            f'{"".join(labels)}</svg>')


# ---------------------------------------------------------------------------
# A prospect's report (pop-up)
# ---------------------------------------------------------------------------

def prospect_html(league, p, prev_store=None):
    """(header html, left column html, right column html) of a prospect's report.
    prev_store: where the skill ranges last shown are kept (the clouds and the web
    shrink from there after a scouting step)."""
    uid = league.user_team_id
    media = DD.media_ranks(league)
    st = DD.stats(league)
    rep = S.report(league, uid, p, media.get(p.id), st)
    pub, staff = rep["public"], rep["staff"]
    left = DD.available(league)
    your_rank = board_ranks(league).get(p.id)
    cr = DD.combine_ranks(league).get(p.id, {})
    pl = _plural(p.position)

    def fact_grid(rows):
        return '<div class="facts">' + "".join(
            f'<span class="k">{escape(k)}</span><span class="num">{v}</span>' for k, v in rows) + "</div>"

    flags = []
    if pub["medical_flag"]:
        flags.append("Medical red flag (from the combine medicals: every team knows)")
    if rep["interview"] and rep["interview"].get("character_flag"):
        flags.append("Character red flag (turned up in his interview)")
    facts = [("Age", f"{pub['age']} on draft day"), ("Size", escape(fmt.size(pub["height"], pub["weight"]))
                                                     + (f"  ({escape(p.build_note)})" if p.build_note else "")),
             ("College", escape(pub["college"])), ("Hometown", escape(p.hometown)),
             ("Media big board", f"#{pub['media_rank']}" if pub["media_rank"] else "-"),
             ("Your board", f"#{your_rank} of {len(left)} left" if your_rank else "Drafted")]
    if flags:
        facts.append(("Red flags", "<br>".join(f'<b style="color:#A3321F">{escape(f)}</b>' for f in flags)))

    listed = [(pos.SKILLS[s][0], staff["skills"][s]["ceiling"])
              for s, _w in pos.POSITIONS[p.position][1] if s in staff["skills"]]
    prev = (prev_store or {}).get(p.id)
    skills = skill_web(listed, prev) + "".join(cloud_row(lab, r, (prev or {}).get(lab)) for lab, r in listed)
    if prev_store is not None:
        prev_store[p.id] = {lab: r for lab, r in listed}
    devl = S.developed(league, uid, p)
    imp = S.impression(league, uid, p, st)
    proj = S.projections(league, uid, p, st, media.get(p.id))
    if proj["scouts"]:
        (a, pa), (b, pb) = proj["scouts"]
        proj_line = (f"Big boards: <b>{escape(proj['media'] or '-')}</b> · {escape(a)}: <b>{escape(pa)}</b> · "
                     f"{escape(b)}: <b>{escape(pb)}</b> <span style='opacity:.8'>(a cross-check settles it)</span>")
    elif proj["staff"]:
        proj_line = (f"Big boards: <b>{escape(proj['media'] or '-')}</b> · Your staff: "
                     f"<b>{escape(proj['staff'])}</b>")
    else:
        proj_line = (f"Big boards: <b>{escape(proj['media'] or '-')}</b> · Your staff: no read until your scouts "
                     f"watch his film")
    note_items = S.notes(league, uid, p, st, cr)
    film_notes = [n["text"] for n in note_items if n["kind"] == "film"]
    person_notes = [n["text"] for n in note_items if n["kind"] == "person"]
    if note_items:
        notes_html = ('<div class="scout-notes">'
                      + "".join(f'<div class="sn film">{escape(t)}</div>' for t in film_notes)
                      + "".join(f'<div class="sn person">{escape(t)}</div>' for t in person_notes)
                      + '</div><div class="legend" style="margin-top:4px">From your scouts: film notes, then the '
                        'interview. Their view, so they can be wrong.</div>')
    else:
        notes_html = '<div class="legend">No notes yet: your scouts start with his film.</div>'

    combine_rows = []
    for key, _label, what in COMBINE_COLS:
        v = _combine_value(p, key)
        name = fmt.DRILL_LABELS[key][0] if key in fmt.DRILL_LABELS else (
            "Intelligence test" if key == "intel" else "Position drill")
        if v is None:
            combine_rows.append(f'<tr><td class="l">{name}</td><td class="cmb-dnt">Did not test</td><td></td></tr>')
            continue
        rk = cr.get(key)
        tier = _tier(*rk) if rk else ""
        combine_rows.append(f'<tr><td class="l">{name}</td><td class="cmb cmb-{tier}">{escape(_long(key, v))}</td>'
                            f'<td class="legend">{f"{ordinal(rk[0])} of {rk[1]} {pl}" if rk else ""}</td></tr>')
    combine = ('<table class="box-table"><thead><tr><th class="l">Drill</th><th>Result</th>'
               f'<th>Rank at {p.position} in this class</th></tr></thead><tbody>{"".join(combine_rows)}</tbody></table>'
               + _legend_html())
    if rep["interview"]:
        iv = rep["interview"]
        person = fact_grid([(S.PERSONALITY_NAMES[t], escape(fmt.trait(iv[t]))) for t in S.PERSONALITY])
        person += ('<div class="legend" style="margin-top:6px">Your staff\'s read from the interview (it can be '
                   'off by a few points). ' + ("<b>Character red flag.</b>" if iv.get("character_flag")
                                               else "No character concerns came up.") + '</div>')
    else:
        person = ('<div class="legend">Not interviewed. ' + escape(STEP_HELP["interview"]) + '</div>')
    done = staff["scouted"]
    scouted = ", ".join(S.STEP_NAMES[k] for k in done) if done else "nothing yet: this is the league's word on him"
    now, ceil = staff["now"], staff["ceiling"]
    head = f"""
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:4px">
      {_pos_tag(p.position)}
      <span class="team-name" style="line-height:1">{escape(p.name)}</span>
      <span style="opacity:.85">{escape(pos.POSITIONS[p.position][0])} · {escape(pub["college"])} ·
        draft prospect</span>
    </div>
    <div style="display:flex;gap:22px;margin-top:8px;flex-wrap:wrap;font-size:17px;align-items:center">
      {take_chip(imp, big=True)}
      <span class="grade-cloud">Potential {mini_cloud(ceil, big=True)}</span>
      <span class="grade-cloud">Developed {devl}%</span>
    </div>
    <div style="font-size:14px;margin-top:6px">{proj_line}</div>
    <div style="opacity:.85;font-size:13px;margin-top:4px">Your staff's read. Scouted: {escape(scouted)}. The clouds
      are how good he can become (where one sits is their best guess, how wide and blurry it is is how unsure they
      are); Developed % is how much of that he arrives with. Both sharpen as you scout him, and some doubt always
      stays.</div>"""
    left_col = f"""
    <h3 style="margin-top:0">Bio</h3>{fact_grid(facts)}
    <h3>Ratings (your staff's view)</h3>{skills}
    <div class="legend" style="margin-top:6px">Each cloud is your staff's view of how good he can become at
      that skill; the web shows the same thing for all of them at once. Wide and blurry means they aren't sure.
      They tighten as you scout.</div>"""
    right_col = f"""
    <h3 style="margin-top:0">Scout's notes</h3>{notes_html}
    <h3>Combine</h3>{combine}
    <h3>Interview</h3>{person}"""
    return head, left_col, right_col


def _legend_html():
    return ('<div class="dlegend">Combine colors, by where he ranks at his position: '
            '<span class="cmb cmb-sup">red = superior</span> (best 10%), '
            '<span class="cmb cmb-great">blue = great</span> (best 25%), '
            '<span class="cmb cmb-poor">green = poor</span> (worst 20%). '
            '<span class="cmb-dnt">—</span> did not test. Hover a number for its rank.</div>')


# ---------------------------------------------------------------------------
# The look of this page (screens only; the shared look is theme.py)
# ---------------------------------------------------------------------------

CSS = f"""
<style>
  .dtop {{ display:flex; align-items:center; gap:10px 18px; flex-wrap:wrap; padding:8px 16px;
          background:var(--paper); border-bottom:1px solid var(--line); }}
  .dtitle {{ font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:27px; line-height:1;
            color:var(--turf); white-space:nowrap; }}
  .dviews {{ display:flex; gap:2px; }}
  .dviews .q-btn {{ font-family:'Barlow Condensed',sans-serif; font-weight:600; font-size:17px; color:#4F5A63;
                   border-bottom:3px solid transparent; border-radius:0; padding:2px 12px; min-height:38px; }}
  .dviews .q-btn.on {{ color:var(--turf); border-bottom-color:var(--turf); }}
  .dstat {{ display:flex; gap:16px; align-items:center; flex-wrap:wrap; font-size:13.5px; }}
  .dstat .m {{ display:flex; flex-direction:column; gap:2px; min-width:118px; }}
  .dstat .m b {{ font-variant-numeric:tabular-nums; }}
  .meter {{ height:6px; background:#E3E8E1; border-radius:3px; overflow:hidden; }}
  .meter > div {{ background:var(--turf); height:100%; }}

  .dboard-table {{ background:var(--paper); border:1px solid var(--line); border-radius:4px; }}
  .dboard-table thead tr th {{ position:sticky; top:0; z-index:2; background:var(--turf); color:white;
     font-family:'Barlow Condensed',sans-serif; font-weight:600; font-size:14.5px; letter-spacing:.02em;
     padding:5px 6px; white-space:nowrap; }}
  .dboard-table thead tr th .q-table__sort-icon {{ color:{theme.FLAG}; }}
  .dboard-table thead tr th:not(.sorted) .q-table__sort-icon {{ display:none; }}
  .dboard-table tbody td {{ font-size:13.5px; padding:1px 6px !important; height:27px; white-space:nowrap; }}
  .dboard-table tbody tr {{ cursor:pointer; }}
  .dboard-table tbody tr:nth-child(even) td {{ background:#F6F8F5; }}
  .dboard-table tbody tr:hover td {{ background:#EEF4EA; }}
  .dboard-table tbody tr.is-marked td {{ background:#E8F0FB; }}
  .dboard-table tbody tr.is-mine td {{ background:#FFF6CF; }}
  .dboard-table tbody tr.is-selected td {{ background:#FFE98A !important; }}
  .dboard-table tbody tr.is-selected td:first-child {{ box-shadow:inset 4px 0 0 #C99A06; }}
  .dboard-table .pos-tag {{ min-width:32px; font-size:13px; padding:0 5px; }}
  .dboard-table .rating .swatch {{ width:9px; height:9px; }}
  .pname {{ font-weight:600; cursor:pointer; }}
  .pname:hover {{ color:var(--turf); text-decoration:underline; }}
  .mark {{ color:#B7BFB6; font-size:16px; cursor:pointer; padding:0 3px; }}
  .mark.on {{ color:#D99A00; }}
  .cmb {{ font-variant-numeric:tabular-nums; }}
  .cmb-sup {{ color:#C62828; font-weight:700; }}
  .cmb-great {{ color:#1D5FBF; font-weight:700; }}
  .cmb-poor {{ color:#2E7D32; }}
  .cmb-dnt {{ color:#A3ABA2; }}
  .sc {{ display:inline-block; width:16px; text-align:center; border-radius:3px; margin-right:2px; font-size:11.5px;
        font-weight:600; background:#EEF1EC; color:#9AA39A; }}
  .sc.on {{ background:#2E8B47; color:white; }}
  .dlegend {{ font-size:12.5px; color:var(--ink-soft); padding:4px 2px 0; }}
  .dtools {{ display:flex; align-items:center; gap:6px 14px; flex-wrap:wrap; }}
  .dtools .hint {{ font-size:12.5px; color:var(--ink-soft); }}

  .rail {{ flex:0 0 250px; width:250px; display:flex; flex-direction:column; gap:7px; }}
  .rail .q-btn.rb {{ width:100%; min-height:40px; border-radius:6px; font-family:'Barlow Condensed',sans-serif;
                    font-size:17px; font-weight:600; letter-spacing:.01em; }}
  .rail .q-btn.rb.main {{ background:var(--turf); color:white; }}
  .rail .q-btn.rb.go {{ background:{theme.FLAG}; color:var(--ink); min-height:48px; font-size:19px; }}
  .rail .q-btn.rb.alt {{ background:white; color:var(--turf); box-shadow:inset 0 0 0 1.5px var(--turf); }}
  .rail .q-btn.rb.quiet {{ background:#E9EEE6; color:var(--ink); }}
  .rail .rsep {{ height:1px; background:var(--line); margin:3px 0; }}
  .rail-card {{ background:var(--paper); border:1px solid var(--line); border-radius:6px; padding:9px 11px; }}
  .rail-card .rc-name {{ font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:21px; line-height:1.1; }}
  .rail-card .q-btn.sb {{ font-size:13px; min-height:30px; border-radius:4px; padding:0 6px; }}
  .spd-lab {{ font-size:12px; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.05em;
             margin:2px 0 -3px; }}
  .spd {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:3px; }}
  .spd .q-btn {{ border-radius:4px; min-height:32px; padding:0 2px; font-family:'Barlow Condensed',sans-serif;
                font-size:15.5px; font-weight:600; background:#E9EEE6; color:var(--ink); }}
  .spd .q-btn.wide {{ grid-column:1 / -1; }}
  .spd .q-btn.on {{ background:var(--turf); color:white; }}
  .spd .q-btn.on.pz {{ background:#5B6670; }}
  .rail .q-checkbox {{ font-size:13px; }}

  .clock {{ display:flex; align-items:stretch; background:#18222B; color:white; border-radius:6px;
           overflow:hidden; margin:10px 16px 0; min-height:62px; }}
  .clock.mine {{ box-shadow:inset 0 0 0 3px {theme.FLAG}; }}
  .clock .pk {{ background:{theme.FLAG}; color:var(--ink); padding:5px 16px; display:flex; flex-direction:column;
               justify-content:center; text-align:center; font-family:'Barlow Condensed',sans-serif; }}
  .clock .pk .r {{ font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }}
  .clock .pk .n {{ font-size:32px; font-weight:700; line-height:1; }}
  .clock .who {{ flex:1; min-width:0; padding:6px 16px; display:flex; flex-direction:column; justify-content:center; }}
  .clock .who .t {{ font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:26px; line-height:1.05;
                   white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .clock .who .s {{ font-size:13px; opacity:.85; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .clock .oc {{ display:inline-block; background:{theme.FLAG}; color:var(--ink); font-size:17px; padding:0 8px;
               border-radius:3px; margin-left:10px; letter-spacing:.05em; vertical-align:3px; }}
  .clock .up {{ display:flex; align-items:center; gap:4px; padding:6px 14px; border-left:1px solid rgba(255,255,255,.14); }}
  .clock .up .lab {{ font-size:12px; opacity:.7; text-transform:uppercase; letter-spacing:.06em; margin-right:4px; }}
  .clock .up .u {{ background:rgba(255,255,255,.09); border-radius:3px; padding:2px 6px; font-size:13px;
                  text-align:center; min-width:46px; line-height:1.2; }}
  .clock .up .u b {{ display:block; font-family:'Barlow Condensed',sans-serif; font-size:16px; }}
  .clock .up .u.me {{ background:{theme.FLAG}; color:var(--ink); }}
  .clock .live {{ display:flex; flex-direction:column; justify-content:center; align-items:center; padding:4px 12px;
                 border-left:1px solid rgba(255,255,255,.14); font-family:'Barlow Condensed',sans-serif;
                 font-size:14px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; min-width:84px; }}
  .clock .live .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; background:#E53935;
                      margin-right:5px; animation:dlive 1.4s ease-in-out infinite; }}
  .clock .live.paused {{ opacity:.65; }}
  .clock .live.paused .dot {{ background:#9AA39A; animation:none; }}
  @keyframes dlive {{ 50% {{ opacity:.25; }} }}

  .dbottom {{ display:flex; gap:10px; margin-top:6px; }}
  .dlog {{ background:var(--paper); border:1px solid var(--line); border-radius:4px; height:138px; overflow-y:auto;
          padding:3px 10px; font-size:13.5px; }}
  .dlog .lh {{ font-family:'Barlow Condensed',sans-serif; font-weight:600; color:var(--turf); font-size:15px;
              position:sticky; top:0; background:var(--paper); padding:2px 0; }}
  .dlog .ln {{ padding:1px 0; border-bottom:1px solid #F0F2EE; white-space:nowrap; overflow:hidden;
              text-overflow:ellipsis; }}
  .dlog .ln.me {{ background:#FFF6CF; }}
  .dlog .ln.fresh {{ animation:dfresh 1.6s ease-out; }}
  @keyframes dfresh {{ from {{ background:#FFE98A; }} }}
  .dlog .star {{ color:#D99A00; }}
  .dlog .lc {{ color:#3F4A52; }}        /* the player's college, right after his name */
  .dlog .lp {{ display:inline-block; min-width:62px; color:var(--ink-soft); font-variant-numeric:tabular-nums; }}
  .dlog .lt {{ display:inline-block; min-width:38px; font-weight:600; }}
  .dlog .pos-tag {{ min-width:30px; font-size:12.5px; padding:0 4px; }}
  .needchips {{ display:flex; flex-wrap:wrap; gap:4px; }}
  .needchips .nc {{ border:1px solid var(--line); border-radius:3px; padding:0 6px 0 0; font-size:13px;
                   display:inline-flex; align-items:center; gap:5px; background:var(--paper); }}
  .needchips .nc .pos-tag {{ min-width:30px; font-size:12.5px; padding:0 4px; border-radius:3px 0 0 3px; }}
  .needchips .nc.short b {{ color:#A3321F; }}
  .needchips .nc.full {{ opacity:.55; }}
  :root {{ --dlog-h: 138px; }}
  .dlog {{ height:var(--dlog-h); }}
  @media (max-width: 1480px) {{
    .dboard-table tbody td {{ font-size:12.5px; padding:1px 4px !important; }}
    .dboard-table thead tr th {{ font-size:13.5px; padding:4px 4px; }}
    .rail {{ flex-basis:222px; width:222px; }}
    .rail .q-btn.rb {{ font-size:16px; }}
  }}
  .dorder td.l a {{ color:inherit; }}
  /* The boards fill the window below the green bar: --bar-h is the bar's real height
     (it grows to two rows on narrower windows), set by the script below. */
  .dfill-prospects {{ height:calc(100vh - var(--bar-h, 60px) - 162px); }}
  .dfill-room {{ height:calc(100vh - var(--bar-h, 60px) - 254px - var(--dlog-h)); }}
  .dfill-results {{ height:calc(100vh - var(--bar-h, 60px) - 140px); }}
  .dfill-side {{ height:calc(100vh - var(--bar-h, 60px) - 90px); }}
  @media (max-height: 820px) {{ :root {{ --dlog-h: 96px; }} }}
  .dorder tr.now td {{ background:#FFE98A; }}
  .dorder tr.me td {{ background:#FFF6CF; }}

  .take-chip {{ display:inline-block; color:white; font-size:12px; font-weight:600; padding:1px 8px;
               border-radius:10px; white-space:nowrap; letter-spacing:.01em; }}
  .take-chip.big {{ font-size:15px; padding:3px 12px; border-radius:14px; box-shadow:0 1px 3px rgba(0,0,0,.25); }}
  .take-chip.none {{ background:#E3E8E1; color:#7A847A; font-weight:500; }}
  .cloud-row {{ display:grid; grid-template-columns:150px 1fr; align-items:center; gap:10px;
               padding:3px 0; font-size:13.5px; }}
  .cloud-track {{ position:relative; height:16px; border-radius:8px; overflow:hidden;
                 background:repeating-linear-gradient(90deg,#F0F3EE 0 calc(25% - 1px),#DDE3DA calc(25% - 1px) 25%); }}
  .cloud {{ position:absolute; top:1px; bottom:1px; left:var(--l1); width:var(--w1); border-radius:999px;
           filter:blur(var(--b1)); animation:cloud-in .9s cubic-bezier(.2,.8,.3,1) both; }}
  .cloud.pot {{ background:radial-gradient(ellipse at center,var(--c) 0%,var(--c) 45%,transparent 100%);
               top:2px; bottom:2px; }}
  .cloud-mid {{ position:absolute; top:2px; bottom:2px; width:2px; margin-left:-1px; background:#1E2A22;
               border-radius:1px; transition:opacity .6s; }}
  @keyframes cloud-in {{ from {{ left:var(--l0); width:var(--w0); filter:blur(var(--b0)); }}
                        to {{ left:var(--l1); width:var(--w1); filter:blur(var(--b1)); }} }}
  .skill-web {{ display:block; width:410px; max-width:100%; height:270px; margin:2px auto 6px; }}
  .skill-web .web-grid {{ fill:none; stroke:#DCE2D9; stroke-width:1; }}
  .skill-web .web-band {{ fill:rgba(47,111,191,.32); stroke:rgba(47,111,191,.8); stroke-width:1; }}
  .skill-web .web-label {{ font-size:10px; fill:#4F5A63; font-family:'Barlow',sans-serif; }}
  .scout-notes {{ background:#FFFBEA; border:1px solid #EADFAE; border-left:4px solid #D9B84A; border-radius:3px;
                 padding:6px 10px; }}
  .scout-notes .sn {{ font-family:'Barlow Condensed',sans-serif; font-size:16px; padding:2px 0 2px 16px;
                     position:relative; }}
  .scout-notes .sn::before {{ content:'\u2022'; position:absolute; left:2px; color:#B08A1C; }}
  .scout-notes .sn.person {{ color:#5A4A86; }}

  .mcloud-track {{ position:relative; display:inline-block; vertical-align:middle; width:86px; height:12px;
                  border-radius:6px; overflow:hidden;
                  background:repeating-linear-gradient(90deg,#EEF2EC 0 calc(25% - 1px),#D9E0D6 calc(25% - 1px) 25%); }}
  .mcloud-track.big {{ width:150px; height:16px; border-radius:8px; }}
  .mcloud {{ position:absolute; top:1px; bottom:1px; border-radius:999px;
            background:radial-gradient(ellipse at center,var(--c) 0%,var(--c) 45%,transparent 100%); }}
  .grade-cloud {{ display:inline-flex; align-items:center; gap:8px; white-space:nowrap; }}
  .grade-cloud.small {{ font-size:13.5px; gap:6px; margin:1px 0; }}
  .grade-cloud.small .mcloud-track {{ width:150px; }}
</style>
"""

# The bar's height, for the board heights above (.dfill-*).
BAR_JS = """
<script>
(() => {
  const set = () => {
    const bar = document.querySelector('.top-band');
    if (bar) document.documentElement.style.setProperty('--bar-h', bar.offsetHeight + 'px');
    return bar;
  };
  const start = () => { const bar = set(); if (!bar) return setTimeout(start, 300); new ResizeObserver(set).observe(bar); };
  start();
})();
</script>
"""


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

def build_draft_tab(on_change=None, on_next=None, on_startup_done=None):
    """Builds the Draft tab. on_change: redraw the header and season bar after a
    move. on_next: the offseason's Next (starts the draft, or finishes it).
    on_startup_done: the startup draft is over (camp opens). Returns a function
    that refreshes it."""
    league = state.league
    ui.add_head_html(CSS)
    ui.add_head_html(BAR_JS)
    remembered = saves.load_app_settings()
    speed = remembered.get("draft_speed")
    view = {"v": None, "pid": None, "pos": "All positions", "need_only": False, "marked_only": False,
            "season": None, "round": "All rounds", "team": "All teams",
            # the speed the draft last ran at (the room always opens paused)
            "speed": speed if speed in SPEEDS and speed != "Pause" else "Normal",
            "pause_marked": bool(remembered.get("draft_pause_marked", True))}
    # The draft running itself: "mode" is the speed you chose ("Pause" = stopped; it waits
    # anyway while you're on the clock), "last" when the last pick went in, "busy" while
    # the timer is making picks (nothing else moves the draft then).
    live = {"mode": "Pause", "last": 0.0, "busy": False, "fresh": None}
    ctx = {"table": None, "dialog": None}

    def views():
        if DD.in_startup(league):
            return ["Startup draft"]
        if DD.drafting(league):
            return ["Draft room", "Prospects", "Results"]
        if DD.has_class(league):
            return ["Prospects", "Results"]
        return ["Results"]

    def phase_key():
        ph = SEASON.offseason_phase(league)
        return ph[0] if ph else None

    @ui.refreshable
    def body():
        ctx["table"] = None
        vs = views()
        if view["v"] not in vs or view.get("was") != vs[0]:
            view["v"] = vs[0]            # e.g. the draft just started: the draft room
            view["pid"] = None
        view["was"] = vs[0]
        with ui.element("div").classes("dtop w-full"):
            if DD.in_startup(league):
                title = f"{league.season} Startup Draft"
            elif DD.has_class(league):
                title = f"{league.season} Draft"
            else:
                title = "Draft history"
            ui.html(f'<span class="dtitle">{title}</span>', sanitize=False)
            if len(vs) > 1:
                with ui.element("div").classes("dviews"):
                    for v in vs:
                        ui.button(v, on_click=lambda v=v: set_view(v)).props("flat no-caps dense") \
                            .classes("on" if v == view["v"] else "")
            ui.element("div").style("flex:1")
            top_status()
        if view["v"] == "Startup draft":
            startup_view()
        elif view["v"] == "Draft room":
            room_view()
        elif view["v"] == "Prospects":
            prospects_view()
        else:
            results_view()

    def set_view(v):
        view["v"] = v
        view["pid"] = None
        body.refresh()

    @ui.refreshable
    def top_status():
        if league.user_team_id is None:
            ui.label("Pick your team first.").classes("legend")
            return
        if DD.in_startup(league):
            room = DD.startup_room(league)
            have = sum(1 for pk in (room.picks if room else []) if pk["team"] == league.user_team_id)
            ui.html(f'<div class="dstat">Every team drafts its 53-man roster · your roster so far: '
                    f'<b>{have} of 53</b></div>', sanitize=False)
        elif DD.scouting_open(league):
            b = S.budget(league)
            meters = "".join(
                f'<div class="m"><span>{label}: <b>{b[k][0]}</b> of {b[k][1]} left</span>'
                f'<div class="meter"><div style="width:{100 * b[k][0] / max(1, b[k][1]):.0f}%"></div></div></div>'
                for k, label in (("hours", "Scouting hours"), ("interviews", "Interviews"),
                                 ("visits", "Top-30 visits")))
            ui.html(f'<div class="dstat"><span class="legend">{len(DD.prospects(league))} prospects</span>'
                    f'{meters}</div>', sanitize=False) \
                .tooltip("Scouting ends when the draft starts (after free agency wave 4).")
        elif DD.drafting(league):
            mine = DD.your_slots(league)
            nxt = (f"Your next pick: <b>#{mine[0]['pick']}</b> (round {mine[0]['round']}) · {len(mine)} left"
                   if mine else "You have no picks left in this draft")
            ui.html(f'<div class="dstat">{nxt} · scouting is over</div>', sanitize=False)
        elif not DD.has_class(league):
            ui.html('<div class="dstat legend">The next class is announced at the start of the league year, '
                    'right after the season. You scout it during free agency, then draft it.</div>',
                    sanitize=False)

    # ---- Pieces shared by the boards ---------------------------------------------
    def toolbar(extra=None, hint=None):
        with ui.element("div").classes("dtools"):
            ui.select(["All positions"] + POSITION_ORDER, value=view["pos"],
                      on_change=lambda e: (view.update(pos=e.value), body.refresh())) \
                .props("dense outlined options-dense").classes("w-40")
            ui.label("Show position").classes("legend")
            ui.checkbox("Marked only", value=view["marked_only"],
                        on_change=lambda e: (view.update(marked_only=e.value), body.refresh())) \
                .props("dense").tooltip("Only the players you've marked (right-click a row, or click its star)")
            if extra:
                extra()
            ui.label(hint or "Click a row to select · double-click or click a name for the full report · "
                              "right-click to mark").classes("hint")

    def filtered(players):
        if view["pos"] != "All positions":
            players = [p for p in players if p.position == view["pos"]]
        if view["marked_only"]:
            marks = _marks(league)
            players = [p for p in players if p.id in marks]
        return players

    def board_table(rows, columns, rating_cells, fill, sort_by="board", on_open=None):
        """fill: "prospects" or "room" (how much of the window the table gets)."""
        table = ui.table(rows=rows, columns=columns, row_key="id",
                         pagination={"rowsPerPage": 0, "sortBy": sort_by}) \
            .props("flat dense virtual-scroll hide-bottom") \
            .classes(f"dboard-table w-full dfill-{fill}")
        add_board_slots(table, rating_cells)
        ctx["table"] = table
        highlight()
        def clicked(e):
            # One click handler: on the star = mark, on the name = his report, anywhere else = select.
            a = _arg(e)
            if not isinstance(a, dict):
                return
            if a.get("on") == "mark":
                toggle_mark(a["id"])
            else:
                select(a["id"])
                if a.get("on") == "name":
                    on_open(a["id"])
        table.on("rowClick", clicked, js_handler="(evt, row) => emit({id: row.id, on: evt.target.closest('.mark') "
                                                 "? 'mark' : (evt.target.closest('.pname') ? 'name' : '')})")
        table.on("rowDblclick", lambda e: on_open(_arg(e)),        # (a name already opened on its click)
                 js_handler="(evt, row) => { if (!evt.target.closest('.pname, .mark')) emit(row.id); }")
        table.on("rowContextmenu", lambda e: toggle_mark(_arg(e)),
                 js_handler="(evt, row) => { evt.preventDefault(); emit(row.id); }")
        return table

    def _arg(e):
        a = e.args
        while isinstance(a, list):
            a = a[0] if a else None
        return a

    def highlight():
        t = ctx.get("table")
        if t is not None:
            sel = view["pid"] if view["pid"] is not None else -1
            t.props(f':table-row-class-fn="row => (row.id === {sel} ? \'is-selected\' : \'\') + '
                    f'(row.marked ? \' is-marked\' : \'\') + (row.mine ? \' is-mine\' : \'\')"')

    def select(pid):
        view["pid"] = pid
        highlight()
        rail.refresh()

    def toggle_mark(pid):
        if pid is None:
            return
        on = _toggle_mark(league, pid)
        mark_changed()
        t = ctx.get("table")
        if t is not None:
            for r in t.rows:
                if r["id"] == pid:
                    r["marked"] = on
            if view["marked_only"] and not on:
                t.rows = [r for r in t.rows if r["id"] != pid]
            t.update()
        if on_change:
            on_change()
        rail.refresh()

    def drop_rows(pids):
        """Players just drafted: off the board."""
        gone = set(pids)
        t = ctx.get("table")
        if t is not None:
            t.rows = [r for r in t.rows if r["id"] not in gone]
            t.update()
        if view["pid"] in gone:
            view["pid"] = None
            rail.refresh()

    def redraw_table():
        """New rows for the prospect table (after scouting)."""
        t = ctx.get("table")
        if t is not None and view["v"] in ("Prospects", "Draft room"):
            t.rows = prospect_rows(league, filtered(DD.available(league)), _marks(league))
            t.update()

    def rb(label, on_click, kind="main", tip=None, enabled=True):
        """A big button in the right-hand column."""
        b = ui.button(label, on_click=on_click, color=None) \
            .props("no-caps unelevated" + ("" if enabled else " disable")).classes(f"rb {kind}")
        if tip:
            b.tooltip(tip)
        return b

    @ui.refreshable
    def rail():
        if view["v"] == "Startup draft":
            startup_rail()
        elif view["v"] == "Draft room":
            room_rail()
        else:
            prospects_rail()

    # ---- The selected prospect (top of the right-hand column) ----------------------
    def selected_card(scouting=True):
        pid = view["pid"]
        pool = {p.id: p for p in DD.prospects(league)}
        with ui.element("div").classes("rail-card"):
            if pid is None or pid not in pool:
                ui.html('<div class="rc-name" style="color:var(--ink-soft)">No prospect selected</div>'
                        '<div class="legend">Click a row to select a prospect.</div>', sanitize=False)
                return
            p = pool[pid]
            now, ceil = S.grade_ranges(league, league.user_team_id, p, DD.stats(league))
            flag = (S.known_flag(league, league.user_team_id, p) or "").title()
            ui.html(f'<div style="display:flex;gap:6px;align-items:center">{_pos_tag(p.position)}'
                    f'<span class="legend">{escape(p.college)}</span>'
                    + (f'<span class="inj-tag inj-out">{flag}</span>' if flag else "") + '</div>',
                    sanitize=False)
            ui.label(p.name).classes("rc-name pname").on("click", lambda: open_report(pid)) \
                .tooltip("His full report")
            imp = S.impression(league, league.user_team_id, p, DD.stats(league))
            proj = S.projections(league, league.user_team_id, p, DD.stats(league), DD.media_ranks(league).get(p.id))
            ui.html(f'<div class="grade-cloud small">Potential {mini_cloud(ceil)}</div>'
                    f'<div class="grade-cloud small">Developed {S.developed(league, league.user_team_id, p)}%</div>'
                    f'<div style="margin-top:4px">{take_chip(imp)}</div>'
                    f'<div class="legend" style="margin-top:2px">Boards: {escape(proj["media"] or "-")}'
                    + (f' · Staff: {escape(proj["staff"])}' if proj["staff"] else "") + '</div>', sanitize=False)
            open_ = DD.scouting_open(league)
            if scouting and (open_ or S.done_steps(league, pid)):
                with ui.element("div").style("display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:6px"):
                    for k in S.STEPS:
                        done = k in S.done_steps(league, pid)
                        ok, why = S.can_do(league, pid, k, open_)
                        b = ui.button(f"{S.STEP_NAMES[k]} ✓" if done else STEP_SHORT[k],
                                      on_click=lambda k=k: scout(pid, k)) \
                            .props(f"no-caps dense {'unelevated color=green-10' if not done else 'flat color=green-10'}"
                                   f" {'' if ok else 'disable'}").classes("sb")
                        b.tooltip(f"{S.STEP_NAMES[k]} ({STEP_COST[k]}): {STEP_HELP[k]}" if ok else
                                  (f"{S.STEP_NAMES[k]}: done" if done else why))
            marked = pid in _marks(league)
            with ui.row().classes("w-full no-wrap gap-1 mt-2"):
                ui.button("Full report", on_click=lambda: open_report(pid)) \
                    .props("no-caps dense outline color=green-10").classes("sb").style("flex:1")
                ui.button("Unmark" if marked else "Mark ☆", on_click=lambda: toggle_mark(pid)) \
                    .props("no-caps dense outline color=green-10").classes("sb").style("flex:1") \
                    .tooltip("Mark him for later (also: right-click his row)")

    def scout(pid, what):
        ok, msg = S.do(league, pid, what, DD.scouting_open(league))
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            mark_changed()
            redraw_table()
            top_status.refresh()
            rail.refresh()
            report_body = ctx.get("report_refresh")
            if report_body:
                report_body()

    # ---- A prospect's report (pop-up) ---------------------------------------------
    def open_report(pid):
        pool = {p.id: p for p in DD.prospects(league)}
        if pid not in pool:
            return
        p = pool[pid]

        @ui.refreshable
        def head():
            h, _l, _r = prospect_html(league, p)
            ui.html(h, sanitize=False)

        @ui.refreshable
        def content():
            _h, left_col, right_col = prospect_html(league, p, _PREV)
            with ui.element("div").classes("report px-6 py-4 m-4"):
                actions(p)
                with ui.element("div").style("display:grid;grid-template-columns:1fr 1fr;gap:6px 30px"):
                    ui.html(f"<div>{left_col}</div>", sanitize=False)
                    ui.html(f"<div>{right_col}</div>", sanitize=False)

        def actions(p):
            open_ = DD.scouting_open(league)
            with ui.row().classes("items-center gap-2 mb-2"):
                if DD.user_on_clock(league) and any(q.id == p.id for q in DD.available(league)):
                    ui.button(f"Draft {p.name}", on_click=lambda: (dlg.close(), draft_him(p.id))) \
                        .props("no-caps unelevated").style(f"background:{theme.FLAG};color:{theme.INK}")
                if open_ or S.done_steps(league, p.id):
                    for k in S.STEPS:
                        done = k in S.done_steps(league, p.id)
                        ok, why = S.can_do(league, p.id, k, open_)
                        b = ui.button(f"{S.STEP_NAMES[k]}: done" if done else f"{S.STEP_NAMES[k]} ({STEP_COST[k]})",
                                      on_click=lambda k=k: scout(p.id, k)) \
                            .props(f"no-caps dense {'unelevated color=green-10' if not done else 'flat color=green-10'}"
                                   f" {'' if ok else 'disable'}")
                        b.tooltip(STEP_HELP[k] if ok or done else why)
                marked = p.id in _marks(league)
                ui.button("Unmark" if marked else "Mark ☆",
                          on_click=lambda: (toggle_mark(p.id), content.refresh())) \
                    .props("no-caps dense outline color=green-10")

        def refresh_report():
            head.refresh()
            content.refresh()
        dlg = popups.open_window("Draft prospect", 1100, content, draw_head=head)
        ctx["report_refresh"] = refresh_report
        dlg.on("hide", lambda: ctx.update(report_refresh=None))

    # ---- Prospects (scouting) -------------------------------------------------
    def prospects_view():
        with ui.row().classes("w-full no-wrap items-start").style("gap:12px;padding:8px 16px 0"):
            with ui.column().classes("gap-1").style("flex:1 1 0;min-width:0"):
                toolbar()
                board_table(prospect_rows(league, filtered(DD.available(league)), _marks(league)), PROSPECT_COLS,
                            [], "prospects", on_open=open_report)
                ui.html(_legend_html(), sanitize=False)
            with ui.element("div").classes("rail"):
                rail()

    def prospects_rail():
        selected_card()
        ui.element("div").classes("rsep")
        key = phase_key()
        if DD.scouting_open(league):
            if key == "draft":
                rb("Begin draft", lambda: begin_draft(), "go",
                   "Scouting ends and the draft starts at pick 1: you watch it pick by pick at the speed you "
                   "choose. Same as Next in the bar above.")
            else:
                rb("Begin draft", None, "go", enabled=False)
                ui.label("The draft starts after free agency wave 4: keep scouting until then (Next in the bar "
                         "plays each wave).").classes("legend")
        ui.html('<div class="rail-card legend" style="font-size:12.5px"><b>How scouting works</b><br>'
                + "<br>".join(f'<b>{S.STEP_NAMES[k]}</b> ({STEP_COST[k]}): {escape(STEP_HELP[k])}' for k in S.STEPS)
                + '</div>', sanitize=False)

    async def begin_draft():
        if on_next:
            await _maybe(on_next())

    # ---- The draft room --------------------------------------------------------
    def room_view():
        clock_bar()
        with ui.row().classes("w-full no-wrap items-start").style("gap:12px;padding:8px 16px 0"):
            with ui.column().classes("gap-1").style("flex:1 1 0;min-width:0"):
                toolbar(hint="Sorted by your staff's board · click a row to select · double-click or click a "
                             "name for his report · right-click to mark")
                board_table(prospect_rows(league, filtered(DD.available(league)), _marks(league)), PROSPECT_COLS,
                            [], "room", on_open=open_report)
                ui.html(_legend_html(), sanitize=False)
                with ui.element("div").classes("dbottom w-full"):
                    draft_log()
            with ui.element("div").classes("rail"):
                rail()

    def upcoming_html(slots, uid, label="Up next"):
        if not slots:
            return ""
        return (f'<div class="up"><span class="lab">{label}</span>' + "".join(
            f'<span class="u{" me" if s["team"] == uid else ""}"><b>#{s["pick"]}</b>'
            f'{escape(_team_abbrev(league, s["team"]))}</span>' for s in slots) + "</div>")

    @ui.refreshable
    def clock_bar():
        slot = DD.on_clock(league)
        uid = league.user_team_id
        if slot is None:
            ui.html('<div class="clock"><div class="who"><div class="t">The draft is over.</div></div></div>',
                    sanitize=False)
            return
        team = league.team(slot["team"])
        via = f" (pick from {league.team(slot['from']).abbrev})" if slot["from"] != slot["team"] else ""
        yours = slot["team"] == uid
        choice, cslot = DD.staff_choice(league)
        staff = ""
        if choice is not None and cslot is not None:
            q = league.player(choice)
            staff = (f"Your staff would take {q.position} {escape(q.name)}"
                     + (" here." if yours else f" with pick #{cslot['pick']} if the draft were there now."))
        upcoming = [s for s in DD.all_slots(league) if s["pid"] is None and s["pick"] > slot["pick"]][:6]
        ui.html(f'<div class="clock{" mine" if yours else ""}">'
                f'<div class="pk"><span class="r">Round {slot["round"]}</span><span class="n">#{slot["pick"]}</span></div>'
                f'<div class="who"><div class="t">{escape(team.abbrev)} · {escape(team.name)}'
                + ('<span class="oc">YOU ARE ON THE CLOCK</span>' if yours else '<span style="opacity:.7;font-size:17px">'
                   ' on the clock</span>')
                + f'</div><div class="s">{escape(via)}{" · " if via and staff else ""}{staff}</div></div>'
                + upcoming_html(upcoming, uid) + live_html(yours) + '</div>', sanitize=False)

    def live_html(yours):
        """The clock strip's corner: is the draft running, and at what speed."""
        mode = live["mode"]
        if yours:
            return ""
        if mode == "Pause":
            return '<div class="live paused"><span><span class="dot"></span>Paused</span></div>'
        return (f'<div class="live"><span><span class="dot"></span>Live</span>'
                f'<span style="font-weight:500;opacity:.8">{escape(mode)}</span></div>')

    @ui.refreshable
    def draft_log():
        uid = league.user_team_id
        made = DD.made_picks(league)
        marks = _marks(league)
        lines = "".join(
            f'<div class="ln{" me" if pk["team"] == uid else ""}{" fresh" if pk["pick"] == live["fresh"] else ""}">'
            f'<span class="lp">Rd {pk["round"]} #{pk["pick"]}'
            f'</span><span class="lt">{escape(_team_abbrev(league, pk["team"]))}</span>'
            f'{_pos_tag(league.player(pk["pid"]).position)} '
            + ('<span class="star" title="You marked him">★</span> ' if pk["pid"] in marks else "")
            + f'<b>{escape(league.player(pk["pid"]).name)}</b> '
            f'<span class="lc">{escape(league.player(pk["pid"]).college)}</span> '
            f'<span class="legend">· media #{pk.get("board_rank") or "-"}'
            f'</span></div>' for pk in reversed(made[-80:])) or '<div class="legend">No picks yet.</div>'
        trades = DD.trades(league)
        tlines = "".join(_trade_line(league, t) for t in trades[::-1]) or '<div class="legend">None yet.</div>'
        ui.html(f'<div class="dlog" style="flex:1 1 0;min-width:0"><div class="lh">Draft log (latest first; '
                f'yours highlighted)</div>{lines}</div>', sanitize=False).style("flex:1 1 0;min-width:0")
        ui.html(f'<div class="dlog" style="width:300px"><div class="lh">Draft-day trades</div>{tlines}</div>',
                sanitize=False)

    def room_rail():
        selected_card(scouting=False)
        ui.element("div").classes("rsep")
        slot = DD.on_clock(league)
        uid = league.user_team_id
        yours = slot is not None and slot["team"] == uid
        avail = {p.id for p in DD.available(league)}
        busy_now = running()
        if slot is None:
            ui.label("The draft is over.").classes("legend")
        elif yours:
            pid = view["pid"]
            rb("Draft selected player", lambda: draft_him(view["pid"]), "go",
               f"Draft {league.player(pid).name}" if pid in avail else "Click a prospect in the list first",
               enabled=pid in avail)
            rb("Let my staff pick", lambda: staff_picks(), "main",
               "Your staff takes the best player on your board, with your needs in mind")
            n = len(DD.offers(league))
            rb(f"Trade offers ({n})", lambda: open_trades(), "alt",
               "Teams behind you that want to move up into this pick" if n else
               "Nobody behind you wants to move up badly enough. You can still make your own offer here.")
            speed_control(yours)
        else:
            go_button()
            speed_control(yours)
            rb("Next pick", lambda: next_pick(), "main",
               "The team on the clock makes its pick (it may trade first). Pause first to offer that team a "
               "trade for this pick.", enabled=not busy_now)
        ui.element("div").classes("rsep")
        if slot is not None:
            rb("Have staff finish draft", lambda: finish_it(), "quiet",
               "Your staff makes the rest of your picks (no trades) and the draft finishes. Same as Next in the "
               "bar above.", enabled=not busy_now)
        rb("View draft order", lambda: open_order(), "quiet", "Every pick of this draft: who picks, who was taken")
        if slot is not None and not yours:
            rb("Offer trade", lambda: open_trades(), "quiet", "Offer picks for another team's picks",
               enabled=not busy_now)
        rb("Team needs", lambda: open_needs(), "quiet", "Where your roster is thin, as your staff sees it")

    def go_button():
        """The big yellow button: start or carry on at your speed, or pause."""
        if running():
            rb("Pause draft", lambda: pause(), "go", "Stop the draft after the pick being made")
        else:
            room = DD.startup_room(league) if DD.in_startup(league) else None
            started = bool(room.picks if room is not None else DD.made_picks(league))
            sp = view["speed"]
            rb(f"{'Continue' if started else 'Start'} draft · {sp}", lambda: set_speed(view["speed"]), "go",
               f"The draft runs itself at {sp} speed ({SPEED_HELP[sp].lower()}) and waits when you're on the "
               f"clock. Choose another speed below.")

    def speed_control(yours):
        """Draft speed: Pause, Slow, Normal, Fast, To my pick. While you're on the
        clock the draft waits for you; the speed is what happens after your pick."""
        ui.html(f'<div class="spd-lab">{"Draft speed after your pick" if yours else "Draft speed"}</div>',
                sanitize=False)
        with ui.element("div").classes("spd"):
            for m in SPEEDS:
                cls = ("on " if live["mode"] == m else "") + ("pz " if m == "Pause" else "") \
                    + ("wide" if m == "To my pick" else "")
                ui.button(m, on_click=lambda m=m: set_speed(m), color=None) \
                    .props("no-caps unelevated dense").classes(cls).tooltip(SPEED_HELP[m])
        ui.checkbox("Pause when a player I marked is taken", value=view["pause_marked"],
                    on_change=lambda e: remember_pause_marked(e.value)).props("dense") \
            .tooltip("Mark players by right-clicking their row (or clicking the star)")

    # ---- The draft running itself (the timer; Blake, Oct 22) -----------------------
    # One timer for the room (made at the bottom of build_draft_tab). Each tick, if
    # the draft is running and the next pick is due at your speed, the team on the
    # clock picks (draft_day.step: the same picks as running it straight through).
    # It waits while you're on the clock and pauses by itself when a player you
    # marked is taken (if you ticked that box). A tick never waits on anything slow
    # (an AI pick takes a few milliseconds), so nothing can hang it: an error or a
    # pick that doesn't go through pauses the draft and says so.
    def running():
        return live["mode"] != "Pause"

    def _engine():
        """The draft this room runs: (who's on the clock, make picks, show picks)."""
        if DD.in_startup(league):
            return DD.startup_on_clock, DD.startup_sim_until, startup_picked
        return DD.on_clock, DD.sim_until, picked

    def set_speed(mode):
        """A Draft speed button. Any speed but Pause starts the draft (or keeps it
        going at the new speed); the next pick goes right away."""
        if mode != "Pause":
            view["speed"] = mode
            _remember("draft_speed", mode)
        live["mode"] = mode
        live["last"] = 0.0
        speed_changed()
        clock, _until, _show = _engine()
        slot = clock(league)
        if mode != "Pause" and slot is not None and slot["team"] == league.user_team_id:
            ui.notify(f"You're on the clock: after your pick the draft goes on at {mode} speed.", position="top")

    def pause():
        if running():
            live["mode"] = "Pause"
            speed_changed()

    def speed_changed():
        rail.refresh()
        (startup_bar if DD.in_startup(league) else clock_bar).refresh()

    async def halt():
        """Pause, and let a pick being made finish (before the offseason's Next
        finishes the draft, or the room is closed)."""
        pause()
        t0 = time.monotonic()
        while live["busy"] and time.monotonic() - t0 < 5:
            await asyncio.sleep(0.02)

    def _remember(key, value):
        try:
            saves.set_app_setting(key, value)
        except OSError:
            pass                         # (only a convenience; the draft doesn't need it)

    def remember_pause_marked(on):
        view["pause_marked"] = bool(on)
        _remember("draft_pause_marked", bool(on))

    async def tick():
        mode = live["mode"]
        if mode == "Pause" or live["busy"]:
            return
        if time.monotonic() - live["last"] < SPEEDS[mode]:
            return
        clock, until, show = _engine()
        uid = league.user_team_id
        slot = clock(league)
        if slot is None or slot["team"] == uid:
            return                        # waiting for your pick (or it's over)
        live["busy"] = True
        made = []
        try:
            marks = _marks(league) if view["pause_marked"] else set()
            stop = (lambda pk: pk["pid"] in marks) if marks else None
            while True:
                batch = until(league, stop=stop, most=BURST if mode == "To my pick" else 1)
                made += batch
                if batch:
                    show(batch)
                if (mode != "To my pick" or not batch or live["mode"] != mode
                        or (stop is not None and stop(batch[-1]))):
                    break
                slot = clock(league)
                if slot is None or slot["team"] == uid:
                    break
                await asyncio.sleep(0)    # let the screen draw between bursts
            slot = clock(league)
            if not made and slot is not None and slot["team"] != uid:
                pause()
                ui.notify(f"Pick {slot['pick']} didn't go through, so the draft is paused. Try Next pick.",
                          type="warning", position="top")
            elif made and stop is not None and stop(made[-1]):
                pk = made[-1]
                p = league.player(pk["pid"])
                pause()
                ui.notify(f"A player you marked is gone: {league.team(pk['team']).name} take {p.position} {p.name} "
                          f"with pick {pk['pick']}. The draft is paused.", type="warning", position="top",
                          multi_line=True)
        except Exception as e:            # never leave the timer stuck: pause and say so
            traceback.print_exc()
            pause()
            ui.notify(f"The draft paused: something went wrong making a pick ({e}).", type="negative",
                      position="top", multi_line=True)
        finally:
            live["busy"] = False
            live["last"] = time.monotonic()
        slot = clock(league)
        if slot is None or slot["team"] == uid:
            reached_stop(slot)

    def reached_stop(slot):
        """The draft got to your pick, or the last pick is in."""
        if DD.in_startup(league):
            if slot is None:
                pause()
                later(startup_finish)
                return
            ui.notify(f"You're on the clock with pick {slot['pick']:,}.", type="positive", position="top")
            later(startup_after)
            return
        if slot is None:
            pause()
            later(after_move)
            return
        n = len(DD.offers(league))
        ui.notify(f"You're on the clock with pick {slot['pick']}."
                  + (f" {n} team{'s' if n > 1 else ''} called with trade offers (Trade offers)." if n else ""),
                  type="positive", position="top", multi_line=True)
        later(after_move)

    def later(fn):
        """Run fn (async) on its own, outside the timer's tick, so a long step
        (finishing the draft, opening camp) can never hold the timer up."""
        ui.timer(0.01, fn, once=True)

    async def after_move():
        mark_changed()
        if DD.drafting(league) and DD.on_clock(league) is None and on_next:
            pause()
            ui.notify("The last pick is in.", type="positive", position="top")
            await _maybe(on_next())
            return
        live["last"] = time.monotonic()   # (after your pick, the next one waits a beat at your speed)
        if on_change:
            on_change()
        refresh()

    def picked(made):
        """AI picks while the draft runs: off the board, onto the log."""
        mark_changed()
        live["fresh"] = made[-1]["pick"]
        drop_rows([pk["pid"] for pk in made])
        clock_bar.refresh()
        draft_log.refresh()
        top_status.refresh()

    async def draft_him(pid):
        if pid is None:
            ui.notify("Click a prospect in the list first.", position="top")
            return
        ok, msg = DD.pick(league, pid)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            view["pid"] = None
            await after_move()

    async def staff_picks():
        ok, msg = DD.staff_pick(league)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            await after_move()

    async def next_pick():
        if live["busy"]:
            return
        made = DD.step(league)
        if made:
            p = league.player(made["pid"])
            live["fresh"] = made["pick"]
            ui.notify(f"Pick {made['pick']}: {league.team(made['team']).name} take {p.position} {p.name}.",
                      position="top")
        await after_move()

    async def finish_it():
        await halt()
        if on_next:
            await _maybe(on_next())

    # ---- Pop-ups: draft order, trades, needs ------------------------------------------
    def open_order():
        uid = league.user_team_id
        slot = DD.on_clock(league)
        now_pick = slot["pick"] if slot else None

        def draw():
            rows = []
            for s in DD.all_slots(league):
                cls = "now" if s["pick"] == now_pick else ("me" if s["team"] == uid else "")
                frm = f"from {_team_abbrev(league, s['from'])}" if s["from"] != s["team"] else ""
                if s["pid"] is not None:
                    q = league.player(s["pid"])
                    who = f'{_pos_tag(q.position)} {escape(q.name)} <span class="legend">{escape(q.college)}</span>'
                else:
                    who = '<span class="legend">on the clock</span>' if cls == "now" else ""
                rows.append(f'<tr id="slot-{s["pick"]}" class="{cls}"><td>{s["round"]}</td><td>{s["pick"]}</td>'
                            f'<td class="l"><b>{escape(_team_abbrev(league, s["team"]))}</b> '
                            f'{escape(league.team(s["team"]).name)}</td><td class="l legend">{frm}</td>'
                            f'<td class="l">{who}</td></tr>')
            mine = ", ".join(f"#{s['pick']}" for s in DD.your_slots(league)) or "none"
            ui.html(f'<div class="report px-5 py-4 m-4"><div class="legend" style="margin-bottom:6px">Your picks '
                    f'to come: {mine}. Yours are highlighted; the pick on the clock is in yellow.</div>'
                    '<table class="box-table dorder"><thead><tr><th>Round</th><th>Pick</th><th class="l">Team</th>'
                    '<th class="l">Pick from</th><th class="l">Selection</th></tr></thead><tbody>'
                    + "".join(rows) + "</tbody></table></div>", sanitize=False)
        popups.open_window("Draft order", 820, draw)
        if now_pick:
            ui.run_javascript(f'setTimeout(() => document.getElementById("slot-{now_pick}")'
                              f'?.scrollIntoView({{block: "center"}}), 600)')

    def open_trades():
        if not DD.user_on_clock(league):
            pause()                       # (an offer for the pick on the clock: it waits for you)

        @ui.refreshable
        def draw():
            with ui.element("div").classes("report px-6 py-5 m-4"):
                trades_panel()
        ctx["dialog"] = popups.open_window("Trades", 640, draw)
        ctx["trades_refresh"] = draw.refresh

    def close_dialog():
        d = ctx.get("dialog")
        if d is not None:
            d.close()
            ctx["dialog"] = None

    def trades_panel():
        uid = league.user_team_id
        slot = DD.on_clock(league)
        if slot is None:
            ui.label("The draft is over.").classes("legend")
            return
        ui.html("<h3 style='margin-top:0'>Offers for your pick</h3>", sanitize=False)
        if slot["team"] != uid:
            ui.label("When you're on the clock, teams behind you that want to move up call with offers "
                     "here.").classes("legend")
        else:
            offs = DD.offers(league)
            if not offs:
                ui.label("No calls: nobody behind you wants to move up badly enough.").classes("legend")
            for o in offs:
                with ui.row().classes("items-center gap-2 no-wrap w-full").style("border-bottom:1px solid #EEF1EC;padding:4px 0"):
                    ui.html(f'<div><b>{escape(league.team(o["team"]).name)}</b> offer '
                            f'{escape(DD.pick_list(league, o["gives"]))} '
                            f'<span class="legend">({o["chart_points"]:,} chart points for your '
                            f'{o["for_points"]:,})</span></div>', sanitize=False).style("flex:1")
                    ui.button("Accept", on_click=lambda o=o: take_offer(o)).props("no-caps dense color=green-10")
        ui.html("<h3>Make an offer</h3>", sanitize=False)
        ui.label("Picks in this draft, or next year's. AI teams want at least full value by the Jimmy Johnson "
                 "trade chart (what real teams use); a pick next year is worth about a round less to them "
                 "(the real market's rule of thumb). A team on the clock (or a few picks from it) that loves a "
                 "player still on the board won't move down.").classes("legend")
        others = {t.id: t.name for t in sorted(league.teams, key=lambda t: t.name) if t.id != uid}
        offer = view.setdefault("offer", {"team": None, "give": [], "get": [], "clock": None})
        if offer["team"] not in others or offer.get("clock") != slot["pick"]:
            # A new team on the clock: the offer form starts with that team and its pick.
            offer.update(team=slot["team"] if slot["team"] != uid else next(iter(others)),
                         get=[slot["pick"]] if slot["team"] != uid else [], give=[], clock=slot["pick"])
        mine = DD.your_slots(league)
        theirs = DD.slots_left(league, offer["team"])

        def label(s):
            return f"#{s['pick']} (round {s['round']}, {DD.chart_points(s['pick']):,} pts)"

        def options(slots, team):
            # This draft's picks by number, then next year's (worth to the team that would get them).
            out = {s["pick"]: label(s) for s in slots}
            other = offer["team"] if team == uid else uid
            for key, name in DD.next_year_picks(league, team):
                out[key] = f"{name} (next year, ~{DD.future_points(league, key, other):,} pts)"
            return out
        ui.select(others, value=offer["team"], label="Trade with",
                  on_change=lambda e: (offer.update(team=e.value, get=[]), ctx["trades_refresh"]())) \
            .props("dense outlined options-dense").classes("w-full mt-2")
        theirs_opts = options(theirs, offer["team"])
        mine_opts = options(mine, uid)
        ui.select(theirs_opts, value=[x for x in offer["get"] if x in theirs_opts],
                  multiple=True, label="You get",
                  on_change=lambda e: (offer.update(get=list(e.value or [])), preview.refresh())) \
            .props("dense outlined options-dense use-chips").classes("w-full mt-1")
        ui.select(mine_opts, value=[x for x in offer["give"] if x in mine_opts],
                  multiple=True, label="You give",
                  on_change=lambda e: (offer.update(give=list(e.value or [])), preview.refresh())) \
            .props("dense outlined options-dense use-chips").classes("w-full mt-1")

        @ui.refreshable
        def preview():
            give, get = offer["give"], offer["get"]
            if give and get:
                ok, why = DD.trade_check(league, offer["team"], give, get)
                ui.html(f'<div class="{"legend" if ok else "problem"}" style="margin-top:6px">'
                        f'{"They would take it: " if ok else ""}{escape(why)}</div>', sanitize=False)
                ui.button("Propose trade", on_click=lambda: propose()) \
                    .props(f"no-caps unelevated color=green-10 dense {'' if ok else 'disable'}").classes("mt-1")
            else:
                ui.label("Choose picks on both sides.").classes("legend mt-1")
        preview()

        async def propose():
            ok, msg = DD.propose(league, offer["team"], offer["give"], offer["get"])
            ui.notify(msg, type="positive" if ok else "warning", position="top", multi_line=True)
            if ok:
                offer.update(give=[], get=[])
                close_dialog()
                await after_move()

    async def take_offer(o):
        ok, msg = DD.accept_offer(league, o)
        ui.notify(msg, type="positive" if ok else "warning", position="top", multi_line=True)
        if ok:
            close_dialog()
            await after_move()

    def open_needs():
        def draw():
            rows, note = DD.needs(league, league.user_team_id)
            body_rows = "".join(
                f'<tr><td class="l">{_pos_tag(r["pos"])}</td>'
                f'<td class="l">{r["need"]}</td><td>{fmt.skill(r["weakest"])}</td><td>{fmt.skill(r["typical"])}</td>'
                f'<td>{r["bodies"]} / {r["spots"]}</td></tr>' for r in rows)
            ui.html('<div class="report px-6 py-5 m-4">'
                    '<div class="legend">Need: how far your weakest starter there (as your staff expects him in a '
                    'season or two) is below a typical NFL starter, and whether you have enough bodies for a '
                    '53-man roster.</div>'
                    + (f'<div class="notice" style="margin-top:6px">{escape(note)}</div>' if note else "")
                    + '<table class="box-table" style="margin-top:8px"><thead><tr><th class="l">Pos</th>'
                      '<th class="l">Need</th><th>Your weakest starter</th><th>Typical starter</th>'
                      f'<th>Players / 53-man spots</th></tr></thead><tbody>{body_rows}</tbody></table></div>',
                    sanitize=False)
        popups.open_window("Your needs", 640, draw)

    # ---- Results -----------------------------------------------------------------
    def results_view():
        seasons = sorted({d["season"] for d in league.draft_history}, reverse=True)
        current = DD.drafting(league)
        options = ([league.season] if current else []) + [s for s in seasons if not (current and s == league.season)]
        if not options:
            ui.label("No drafts yet. This league's first draft is after its first season.") \
                .classes("legend px-4 py-4")
            return
        if view["season"] not in options:
            view["season"] = options[0]
        s = view["season"]
        if current and s == league.season:
            picks = DD.made_picks(league)
            trades = DD.trades(league)
        else:
            picks = [d for d in league.draft_history if d["season"] == s]
            rep = league.offseason_report or {}
            trades = rep.get("draft_trades", []) if rep.get("season") == s else []
        teams = {t.id: t.name for t in sorted(league.teams, key=lambda t: t.name)}
        rounds = sorted({d["round"] for d in picks})
        rows = []
        for d in picks:
            if view["round"] != "All rounds" and d["round"] != view["round"]:
                continue
            if view["team"] != "All teams" and d["team"] != view["team"]:
                continue
            p = league.player(d["pid"])
            rows.append({"id": d["pid"], "pick": d["pick"], "round": d["round"], "team": _team_abbrev(league, d["team"]),
                         "via": _team_abbrev(league, d["from"]) if d.get("from") not in (None, d["team"]) else "",
                         "pos": p.position, "pos_style": theme.position_style(p.position), "name": p.name,
                         "pos_sort": POSITION_ORDER.index(p.position) * 1000 + d["pick"],
                         "college": p.college, "media": d.get("board_rank") or 999,
                         "gap": (d.get("board_rank") or d["pick"]) - d["pick"],
                         "mine": d["team"] == league.user_team_id})
        cols = [_col("pick", "Pick", "pick", "Overall pick", align="right"),
                _col("round", "Round", "round", "Round", align="right"),
                _col("team", "Team", "team", "The team that made the pick"),
                _col("via", "Pick from", "via", "Whose pick it was originally (draft-day and earlier trades)"),
                _col("name", "Name", "name", "Click his name for his player card"),
                _col("pos", "Pos", "pos_sort", "Position"),
                _col("college", "College", "college", "College"),
                _col("media", "Media", "media", "Where the media's big board had him (a big gap is a reach or a "
                                                "steal)", align="right", **{":format": 'v => v === 999 ? "-" : v'}),
                _col("gap", "Value", "gap", "Media rank minus pick: positive = he went earlier than the media "
                                            "expected (a reach), negative = later (a steal)", align="right",
                     **{":format": 'v => v > 0 ? "+" + v : v'})]
        with ui.row().classes("w-full no-wrap items-start").style("gap:12px;padding:8px 16px 0"):
            with ui.column().classes("gap-1").style("flex:1 1 0;min-width:0"):
                with ui.element("div").classes("dtools"):
                    ui.select(options, value=s, label="Draft",
                              on_change=lambda e: (view.update(season=e.value), body.refresh())) \
                        .props("dense outlined options-dense").classes("w-28")
                    ui.select(["All rounds"] + rounds, value=view["round"] if view["round"] in rounds else "All rounds",
                              label="Round", on_change=lambda e: (view.update(round=e.value), body.refresh())) \
                        .props("dense outlined options-dense").classes("w-32")
                    ui.select({"All teams": "All teams", **teams}, value=view["team"], label="Team",
                              on_change=lambda e: (view.update(team=e.value), body.refresh())) \
                        .props("dense outlined options-dense").classes("w-52")
                    ui.label("Every pick in order. Your picks are highlighted."
                             + ("" if not current else " Player cards open once the draft is over.")).classes("hint")
                table = ui.table(rows=rows, columns=cols, row_key="id",
                                 pagination={"rowsPerPage": 0, "sortBy": "pick"}) \
                    .props("flat dense virtual-scroll hide-bottom") \
                    .classes("dboard-table w-full dfill-results")
                table.add_slot("header-cell", r"""
                    <q-th :props="props" :title="props.col.tip">{{ props.col.label }}</q-th>""")
                table.add_slot("body-cell-pos", r"""
                    <q-td :props="props"><span class="pos-tag" :style="props.row.pos_style">{{ props.row.pos }}</span></q-td>""")
                table.add_slot("body-cell-name", r"""
                    <q-td :props="props"><span class="pname">{{ props.row.name }}</span></q-td>""")
                table.props(r''':table-row-class-fn="row => row.mine ? 'is-mine' : ''"''')
                table.on("rowClick", lambda e: popups.show_player(e.args[1]["id"])
                         if not DD.drafting(league) else None)
            ui.html('<div class="rail-card dfill-side" style="flex:0 0 330px;overflow-y:auto">'
                    '<div class="rc-name" style="color:var(--turf)">Draft-day trades</div>'
                    + ("".join(_trade_line(league, t) for t in trades)
                       or '<div class="legend">None on record for this draft (trades are kept for the latest '
                          'draft).</div>')
                    + '</div>', sanitize=False)

    # ---- The startup draft ---------------------------------------------------------
    def startup_view():
        startup_bar()
        uid = league.user_team_id
        with ui.row().classes("w-full no-wrap items-start").style("gap:12px;padding:8px 16px 0"):
            with ui.column().classes("gap-1").style("flex:1 1 0;min-width:0"):
                toolbar(extra=lambda: ui.checkbox(
                    "Only positions I still need", value=view["need_only"],
                    on_change=lambda e: (view.update(need_only=e.value), body.refresh())).props("dense"),
                    hint="Your staff's best 300 · click a row to select · double-click or click a name for his "
                         "card · right-click to mark")
                startup_table(uid)
                ui.html(_legend_html().replace("in this class", ""), sanitize=False)
                with ui.element("div").classes("dbottom w-full"):
                    startup_log()
            with ui.element("div").classes("rail"):
                rail()

    def _startup_upcoming(room, k):
        """The next k picks of the startup draft (the same snake order draft.StartupRoom uses)."""
        n0, per = len(room.picks), len(room.order)
        out = []
        for n in range(n0, min(n0 + k, ROSTER_SIZE * per)):
            rnd = n // per + 1
            this = room.order if (not STARTUP_SNAKE or rnd % 2 == 1) else list(reversed(room.order))
            out.append({"pick": n + 1, "round": rnd, "team": this[n % per]})
        return out

    @ui.refreshable
    def startup_bar():
        uid = league.user_team_id
        room = DD.startup_room(league)
        slot = DD.startup_on_clock(league)
        total = 53 * len(league.teams)
        if slot is None or room is None:
            ui.html('<div class="clock"><div class="who"><div class="t">The startup draft is over.</div></div></div>',
                    sanitize=False)
            return
        team = league.team(slot["team"])
        yours = slot["team"] == uid
        staff = ""
        if yours:
            ch = DD.startup_staff_choice(league)
            if ch is not None:
                q = league.player(ch)
                staff = f"Your staff would take {q.position} {escape(q.name)}."
        else:
            nxt = next((s for s in _startup_upcoming(room, 2 * len(room.order) + 1) if s["team"] == uid), None)
            if nxt:
                staff = f"Your next pick: #{nxt['pick']:,} (round {nxt['round']}), {nxt['pick'] - slot['pick']} picks away."
        upcoming = _startup_upcoming(room, 7)[1:]
        ui.html(f'<div class="clock{" mine" if yours else ""}">'
                f'<div class="pk"><span class="r">Round {slot["round"]} of 53</span>'
                f'<span class="n">#{slot["pick"]:,}</span></div>'
                f'<div class="who"><div class="t">{escape(team.abbrev)} · {escape(team.name)}'
                + ('<span class="oc">YOU ARE ON THE CLOCK</span>' if yours else '<span style="opacity:.7;font-size:17px">'
                   ' on the clock</span>')
                + f'</div><div class="s">Pick {slot["pick"]:,} of {total:,}. {staff}</div></div>'
                + upcoming_html(upcoming, uid) + '</div>', sanitize=False)

    def _sept1(lg):
        from datetime import date
        return date(lg.season, 9, 1)

    def startup_table(uid):
        r_need = {x["pos"]: x for x in DD.startup_needs(league, uid)}
        room = DD.startup_room(league)
        avail = room.available() if room else []
        if view["pos"] != "All positions":
            avail = [p for p in avail if p.position == view["pos"]]
        if view["need_only"]:
            avail = [p for p in avail if r_need.get(p.position, {}).get("have", 0) < r_need.get(p.position, {}).get("spots", 0)]
        marks = _marks(league)
        if view["marked_only"]:
            avail = [p for p in avail if p.id in marks]
        score = room.scores(uid, avail) if room else {}
        avail.sort(key=lambda p: score[p.id], reverse=True)
        if room is not None and ctx.get("cr_of") is not room:
            ctx["cr_of"], ctx["cr"] = room, S.combine_ranks(room.pool)
        cr = ctx.get("cr") or {}
        rows = []
        for i, p in enumerate(avail[:300]):
            ovr, pot = seen(league, p), seen(league, p, "potential")
            row = {"id": p.id, "marked": p.id in marks, "board": i + 1, "pos": p.position,
                   "pos_style": theme.position_style(p.position),
                   "pos_sort": POSITION_ORDER.index(p.position) * 1000 + i, "name": p.name,
                   "age": p.age(_sept1(league)), "exp": p.experience, "height": p.height, "weight": p.weight,
                   "ovr": ovr, "ovr_txt": fmt.skill(ovr), "ovr_color": theme.RATING_COLORS[fmt.skill_word(ovr)],
                   "pot": pot, "pot_txt": fmt.skill(pot), "pot_color": theme.RATING_COLORS[fmt.skill_word(pot)],
                   "college": p.college}
            row.update(combine_fields(p, cr.get(p.id, {})))
            rows.append(row)
        board_table(rows, STARTUP_COLS, [("ovr", "ovr_txt", "ovr_color"), ("pot", "pot_txt", "pot_color")],
                    "room", on_open=popups.show_player)

    @ui.refreshable
    def startup_log():
        uid = league.user_team_id
        room = DD.startup_room(league)
        picks = room.picks[-80:] if room else []
        marks = _marks(league)
        lines = "".join(
            f'<div class="ln{" me" if pk["team"] == uid else ""}{" fresh" if pk["pick"] == live["fresh"] else ""}">'
            f'<span class="lp">Rd {pk["round"]} #{pk["pick"]:,}'
            f'</span><span class="lt">{escape(_team_abbrev(league, pk["team"]))}</span>'
            f'{_pos_tag(league.player(pk["pid"]).position)} '
            + ('<span class="star" title="You marked him">★</span> ' if pk["pid"] in marks else "")
            + f'<a class="pname" style="color:inherit;text-decoration:none" href="/player/{pk["pid"]}">'
            f'{escape(league.player(pk["pid"]).name)}</a> '
            f'<span class="lc">{escape(league.player(pk["pid"]).college)}</span> '
            f'<span class="legend">({seen(league, league.player(pk["pid"]))})'
            f'</span></div>' for pk in reversed(picks)) or '<div class="legend">No picks yet.</div>'
        ui.html(f'<div class="dlog"><div class="lh">Draft log (latest first; yours highlighted)</div>{lines}</div>',
                sanitize=False).style("flex:1 1 0;min-width:0")
        needs = DD.startup_needs(league, uid)
        have = sum(x["have"] for x in needs)
        chips = "".join(
            f'<span class="nc{" short" if x["have"] < x["spots"] else " full"}" title="{x["have"]} of '
            f'{x["spots"]} {_plural(x["pos"])} drafted">{_pos_tag(x["pos"])}<b>{x["have"]}</b>/{x["spots"]}</span>'
            for x in needs)
        ui.html(f'<div class="dlog" style="width:340px"><div class="lh">Your roster: {have} of 53</div>'
                f'<div class="needchips">{chips}</div><div class="legend" style="margin-top:4px">Each position '
                f'fills to its roster count; you can\'t draft past it. Faded: full.</div></div>', sanitize=False)

    def startup_rail():
        startup_selected()
        ui.element("div").classes("rsep")
        slot = DD.startup_on_clock(league)
        uid = league.user_team_id
        yours = slot is not None and slot["team"] == uid
        if slot is None:
            ui.label("The startup draft is over.").classes("legend")
        elif yours:
            pid = view["pid"]
            room = DD.startup_room(league)
            ok = pid is not None and room is not None and pid not in room.taken
            rb("Draft selected player", lambda: startup_draft_him(view["pid"]), "go",
               f"Draft {league.player(pid).name}" if ok else "Click a player in the list first", enabled=ok)
            rb("Let my staff pick", lambda: startup_staff(), "main",
               "Your staff takes the best player for your roster")
            speed_control(yours)
        else:
            go_button()
            speed_control(yours)
            rb("Next pick", lambda: startup_next(), "main", "The team on the clock makes its pick",
               enabled=not running())
        ui.element("div").classes("rsep")
        rb("Have staff finish draft", lambda: startup_finish(), "quiet",
           "Your staff makes the rest of your picks, then training camp opens", enabled=not running())
        rb("My roster", lambda: open_startup_roster(), "quiet", "Who you've drafted so far, by position")

    def startup_selected():
        pid = view["pid"]
        with ui.element("div").classes("rail-card"):
            room = DD.startup_room(league)
            if pid is None or room is None or pid in room.taken:
                ui.html('<div class="rc-name" style="color:var(--ink-soft)">No player selected</div>'
                        '<div class="legend">Click a row to select a player.</div>', sanitize=False)
                return
            p = league.player(pid)
            ovr, pot = seen(league, p), seen(league, p, "potential")
            exp = "Rookie" if p.experience == 0 else f"{p.experience} season{'s' if p.experience != 1 else ''}"
            ui.html(f'<div style="display:flex;gap:6px;align-items:center">{_pos_tag(p.position)}'
                    f'<span class="legend">Age {p.age(_sept1(league))} · {exp}</span></div>', sanitize=False)
            ui.label(p.name).classes("rc-name pname").on("click", lambda: popups.show_player(pid)) \
                .tooltip("His player card")
            ui.html(f'<div class="legend">{escape(fmt.size(p.height, p.weight))} · {escape(p.college)}</div>'
                    f'<div class="rating" style="font-size:13.5px"><span class="swatch" style="background:'
                    f'{theme.RATING_COLORS[fmt.skill_word(ovr)]}"></span>Overall {fmt.skill(ovr)}</div>'
                    f'<div class="rating" style="font-size:13.5px"><span class="swatch" style="background:'
                    f'{theme.RATING_COLORS[fmt.skill_word(pot)]}"></span>Potential {fmt.skill(pot)}</div>',
                    sanitize=False)
            marked = pid in _marks(league)
            with ui.row().classes("w-full no-wrap gap-1 mt-2"):
                ui.button("Player card", on_click=lambda: popups.show_player(pid)) \
                    .props("no-caps dense outline color=green-10").classes("sb").style("flex:1")
                ui.button("Unmark" if marked else "Mark ☆", on_click=lambda: toggle_mark(pid)) \
                    .props("no-caps dense outline color=green-10").classes("sb").style("flex:1")

    def open_startup_roster():
        def draw():
            room = DD.startup_room(league)
            uid = league.user_team_id
            r_need = {x["pos"]: x for x in DD.startup_needs(league, uid)}
            mine = [league.player(pk["pid"]) for pk in (room.picks if room else []) if pk["team"] == uid]
            by_pos = {}
            for p in mine:
                by_pos.setdefault(p.position, []).append(p)
            lines = []
            for position in POSITION_ORDER:
                need = r_need.get(position, {"have": 0, "spots": ROSTER_TEMPLATE[position]})
                names = ", ".join(f'<a href="/player/{p.id}">{escape(p.name)}</a> ({seen(league, p)})'
                                  for p in by_pos.get(position, []))
                short = ' style="color:#A3321F;font-weight:600"' if need["have"] < need["spots"] else ""
                lines.append(f'<tr><td class="l">{_pos_tag(position)}</td><td{short}>'
                             f'{need["have"]} / {need["spots"]}</td><td class="l">{names or "-"}</td></tr>')
            ui.html(f'<div class="report px-6 py-5 m-4"><div class="legend">{len(mine)} of 53 drafted. Each position '
                    'fills to its roster count; you can\'t draft past it.</div>'
                    '<table class="box-table" style="margin-top:6px"><thead><tr><th class="l">Pos</th><th>Have</th>'
                    f'<th class="l">Players (overall)</th></tr></thead><tbody>{"".join(lines)}</tbody></table></div>',
                    sanitize=False)
        popups.open_window("Your roster so far", 760, draw)

    def startup_picked(made):
        mark_changed()
        live["fresh"] = made[-1]["pick"]
        drop_rows([pk["pid"] for pk in made])
        startup_bar.refresh()
        startup_log.refresh()
        top_status.refresh()
        if on_change:
            on_change()                   # (the green bar shows the pick on the clock)

    async def startup_after():
        mark_changed()
        if DD.startup_on_clock(league) is None:
            await startup_finish()
            return
        live["last"] = time.monotonic()
        if on_change:
            on_change()
        refresh()

    async def startup_draft_him(pid):
        if pid is None:
            ui.notify("Click a player in the list first.", position="top")
            return
        ok, msg = DD.startup_pick(league, pid)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            view["pid"] = None
            await startup_after()

    async def startup_staff():
        ok, msg = DD.startup_staff_pick(league)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            await startup_after()

    async def startup_next():
        if live["busy"]:
            return
        made = DD.startup_step(league)
        if made:
            p = league.player(made["pid"])
            live["fresh"] = made["pick"]
            ui.notify(f"Pick {made['pick']}: {league.team(made['team']).name} take {p.position} {p.name}.",
                      position="top")
        await startup_after()

    async def startup_finish():
        await halt()
        if on_startup_done:
            await _maybe(on_startup_done())

    def refresh():
        body.refresh()

    with ui.column().classes("w-full gap-0"):
        body()
        ui.timer(TICK, tick)              # the draft running itself (tick, above)
    refresh.pause = pause                 # main_page: closing the draft room pauses the draft
    refresh.halt = halt                   # ...and the offseason's Next waits for a pick being made
    return refresh


def _trade_line(league, t):
    up, down = league.team(t["up"]).abbrev, league.team(t["down"]).abbrev
    you = league.user_team_id in (t["up"], t["down"])
    got = t["got"] + t.get("got_future", [])
    gave = t["gave"] + t.get("gave_future", [])
    return (f'<div class="ln" style="white-space:normal;{"font-weight:600;background:#FFF6CF" if you else ""}">'
            f'{up} get {escape(DD.pick_list(league, got))}; {down} get {escape(DD.pick_list(league, gave))} '
            f'<span class="legend">(chart {t["jj_ratio"]:.2f}x)</span></div>')
