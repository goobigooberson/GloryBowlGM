# staff_page.py
# The Staff page (Team section): your coaching staff and front office, the
# owner's staff budget, and the coaching carousel after the season (Blake,
# Oct 24; design: docs/staff-design.md). Other teams' staffs are view-only.
#
# Coaches' ratings are their REPUTATION (Blake chose "reputation + track
# record"): what the league believes, which can be off; their true ability is
# hidden inside the engine. Rules live in engine/staff.py; this file only
# draws them.

from html import escape

from nicegui import ui

from engine import formatting as fmt
from engine import gm as G
from engine import season
from engine import staff as S
from engine.contracts import fmt_money
from . import popups, theme
from .state import state, FREE_AGENTS, mark_changed

COLUMNS = [
    {"name": "job", "label": "Job", "field": "job", "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "align": "left"},
    {"name": "age", "label": "Age", "field": "age", "align": "right"},
    {"name": "bg", "label": "Background", "field": "bg", "align": "left"},
    {"name": "dev", "label": "Development", "field": "dev", "align": "left"},
    {"name": "eval", "label": "Evaluating", "field": "eval", "align": "left"},
    {"name": "other", "label": "Conditioning / Rehab", "field": "other", "align": "left"},
    {"name": "through", "label": "Contract through", "field": "through", "align": "right"},
    {"name": "salary", "label": "Salary", "field": "salary", "align": "right"},
]
COLUMN_TIPS = {
    "Job": "The 8 jobs you hire: 5 coaches, two scouting directors and the head trainer.",
    "Background": "The position group he coached. A coach develops his own group best (FOF8's "
                  "'specializes in the position').",
    "Development": "Reputation for developing players: how much of their ceiling they reach and whether it "
                   "grows. Reputations can be off; a long record makes them more reliable.",
    "Evaluating": "Reputation for reading players: how close the ratings you see are to the truth.",
    "Conditioning / Rehab": "Strength coach: keeping players healthy. Head trainer: getting them back from injury.",
}


def _rating(v):
    if v is None:
        return "-", "inherit"
    word = fmt.skill_word(v)
    return f"{word} ({v})", theme.RATING_COLORS[word]


def _row(league, job, c):
    if c is None:
        return {"id": -1, "job": S.JOB_SHORT[job], "name": "(open)", "age": "", "bg": "", "dev": "-",
                "eval": "-", "other": "-", "through": "", "salary": "", "dev_c": "inherit",
                "eval_c": "inherit", "other_c": "inherit", "jobkey": job}
    v = S.view(league, c)
    rep = v["reputation"]
    dev, dev_c = _rating(rep.get("dev"))
    ev, ev_c = _rating(rep.get("eval"))
    other, other_c = _rating(rep.get("cond", rep.get("rehab")))
    name = c["name"] + (" (interim)" if c.get("interim") else "")
    return {"id": c["id"], "job": S.JOB_SHORT[job], "name": name, "age": v["age"],
            "bg": S.GROUP_NAMES.get(c.get("bg"), "") if c["track"] == "coach" else "-",
            "dev": dev, "eval": ev, "other": other, "dev_c": dev_c, "eval_c": ev_c, "other_c": other_c,
            "through": c["through"] or "", "salary": fmt_money(c["salary"]), "jobkey": job}


def style_words(c, job):
    """His style in words (what the sim plays like with him calling it)."""
    st = c.get("style") or {}
    out = []

    def lean(k, hi, lo, cut=0.8):
        v = st.get(k, 0)
        if v >= cut:
            out.append(hi)
        elif v <= -cut:
            out.append(lo)
    # The game uses the offensive coordinator's offense, the defensive coordinator's
    # defense and the head coach's 4th-down calls (engine/staff.style).
    if job == "OC":
        lean("pass", "pass-heavy", "run-first")
        lean("pace", "slow, methodical tempo", "up-tempo")
        lean("rb_split", "running back by committee", "rides one workhorse back")
        lean("heavy", "likes two-tight-end sets", "rarely uses two tight ends")
    if job == "DC":
        lean("man", "man coverage", "zone coverage")
        lean("blitz", "blitzes a lot", "rarely blitzes")
        lean("shade", "rolls coverage to the other team's best receiver", "plays it straight")
    if job == "HC":
        lean("aggr", "aggressive on 4th down", "conservative on 4th down")
    return out


def coach_html(league, c, job):
    v = S.view(league, c, job=job)
    teams = {t.id: t for t in league.teams}
    now = S.JOB_NAMES.get(c["job"], "") if c["team"] is not None else (
        "College coach" if c.get("college") else "New to the NFL" if c.get("new") is not None else "Out of work")
    parts = [f'<div class="condensed text-2xl">{escape(c["name"])}</div>',
             f'<div class="legend">{escape(now)}'
             + (" (interim)" if c.get("interim") else "")
             + (f' · {escape(teams[c["team"]].name)}' if c["team"] in teams and c["team"] != league.user_team_id
                else "") + f' · age {v["age"]}</div>']
    if c["track"] == "coach":
        parts.append(f'<div>Background: <b>{escape(S.GROUP_NAMES.get(c.get("bg"), "-"))}</b></div>')
    rows = "".join(f'<tr><td>{escape(S.RATING_NAMES[k])}</td>'
                   f'<td style="color:{_rating(r)[1]};font-weight:600">{escape(_rating(r)[0])}</td></tr>'
                   for k, r in v["reputation"].items())
    parts.append('<div class="panel-heading">Reputation</div>'
                 '<div class="legend">What the league believes. It can be off, more so for coaches with a '
                 'short record.</div>'
                 f'<table class="staff-mini">{rows}</table>')
    words = style_words(c, job) if job in ("HC", "OC", "DC") else []
    if words:
        parts.append('<div class="panel-heading">Style</div><div>' + escape(", ".join(words)).capitalize()
                     + "</div>")
    exp = v["exp"]
    lines = [f"{exp['years']} seasons coaching" if c["track"] == "coach" else f"{exp['years']} seasons in the NFL"]
    if exp.get("HC"):
        w, l_, t_ = v["hc_record"]
        rec = f"{w}-{l_}" + (f"-{t_}" if t_ else "")
        lines.append(f"{exp['HC']} as a head coach ({rec} in this league)" if w + l_ + t_ else
                     f"{exp['HC']} as a head coach")
    if exp.get("coord"):
        lines.append(f"{exp['coord']} as a coordinator")
    if v["college"]:
        lines.append("comes from the college game")
    if v["mentor"]:
        lines.append(f"coaching tree: worked under {v['mentor']}")
    parts.append('<div class="panel-heading">Career</div><div>' + escape("; ".join(lines)) + "</div>")
    if c["team"] is not None:
        parts.append(f'<div>Contract through {c["through"]}, {fmt_money(c["salary"])} a year</div>')
    recs = list(reversed(c["record"][-12:]))
    if recs:
        body = "".join(
            f'<tr><td>{r["season"]}</td><td>{escape(teams[r["team"]].abbrev if r["team"] in teams else "")}</td>'
            f'<td>{escape(S.JOB_SHORT.get(r["job"], r["job"]))}{" (interim)" if r.get("interim") else ""}</td>'
            f'<td>{r["w"]}-{r["l"]}{"-" + str(r["t"]) if r["t"] else ""}</td><td>{escape(r.get("result") or "")}</td></tr>'
            for r in recs)
        parts.append('<div class="panel-heading">Record</div><table class="staff-mini"><tr><th>Season</th>'
                     '<th>Team</th><th>Job</th><th>W-L</th><th>Result</th></tr>' + body + "</table>")
    notes = list(reversed(c.get("dev_notes", [])[-8:]))
    if notes:
        body = "".join(
            f'<tr><td>{n["season"]}</td><td>{escape(teams[n["team"]].abbrev if n["team"] in teams else "")}</td>'
            f'<td>{escape(S.GROUP_NAMES.get(n["group"], ""))} ({n["n"]})</td>'
            f'<td>{"+" if n["vs_league"] >= 0 else ""}{n["vs_league"]:.1f}</td></tr>' for n in notes)
        parts.append('<div class="panel-heading">How his young players developed</div>'
                     '<div class="legend">Change in potential at camp of his group\'s players in their first four '
                     'seasons, versus the league\'s young players at those positions (points a year). '
                     'Small groups are mostly luck.</div>'
                     '<table class="staff-mini"><tr><th>Camp</th><th>Team</th><th>Group (players)</th>'
                     '<th>vs league</th></tr>' + body + "</table>")
    return "".join(parts)


def _wl(rec):
    w, l_, t_ = rec
    return f"{w}-{l_}" + (f"-{t_}" if t_ else "")


def gm_html(league, tid, compact=False):
    """A team's general manager (gm.py): you for your team; for an AI team his
    reputation (what the league believes; his eye for coaches is hidden), his
    record, where he came from and what he's known for."""
    teams = {t.id: t for t in league.teams}
    if tid == league.user_team_id:
        return ('<div class="panel-heading" style="margin-top:0">General manager</div>'
                '<div><b>You.</b> You run the front office: the draft, free agency, contracts and hiring the '
                'coaching staff.</div>')
    p = G.gm_of(league, tid)
    if not p:
        return ('<div class="panel-heading" style="margin-top:0">General manager</div>'
                '<div class="legend">The job is open.</div>')
    v = G.view(league, p)
    rep, col = _rating(v["reputation"])
    here = [r for r in v["history"] if r["team"] == tid]
    parts = ['<div class="panel-heading" style="margin-top:0">General manager</div>',
             f'<div class="condensed text-2xl">{escape(v["name"])}</div>',
             f'<div class="legend">Age {v["age"]} · GM here since {v["since"]}'
             + (f' · came from: {escape(v["from"])}' if v["from"] and not compact else "") + '</div>',
             f'<div>Reputation: <span style="color:{col};font-weight:600">{escape(rep)}</span> '
             "<span class=\"legend\">(what the league thinks of him as a team builder; it follows his teams' "
             'results)</span></div>']
    line = []
    if here:
        trips = sum(1 for r in here if r.get("seed"))
        line.append(f"here {_wl(v['here'])} in {len(here)} season{'s' if len(here) != 1 else ''}"
                    + (f", {trips} playoff trip{'s' if trips != 1 else ''}" if trips else ", no playoff trips"))
    others = sorted({teams[r["team"]].abbrev for r in v["history"] if r["team"] != tid and r["team"] in teams})
    if others:
        line.append(f"before: GM of {', '.join(others)}")
    if v["titles"]:
        line.append(f"{v['titles']} title{'s' if v['titles'] != 1 else ''}")
    if not v["history"]:
        line.append("first season as a GM")
    parts.append("<div>Record: " + escape("; ".join(line)) + "</div>")
    if v["styles"]:
        parts.append('<div>Known for: <b>' + escape("; ".join(w for _a, w in v["styles"])) + '</b></div>')
    else:
        parts.append('<div class="legend">No strong habits on draft day, in free agency or with the cap.</div>')
    if not compact and v["history"]:
        body = "".join(
            f'<tr><td>{r["season"]}</td><td>{escape(teams[r["team"]].abbrev if r["team"] in teams else "")}</td>'
            f'<td>{r["w"]}-{r["l"]}{"-" + str(r["t"]) if r["t"] else ""}</td><td>{escape(r.get("result") or "")}</td></tr>'
            for r in reversed(v["history"][-10:]))
        parts.append('<table class="staff-mini"><tr><th>Season</th><th>Team</th><th>W-L</th><th>Result</th></tr>'
                     + body + "</table>")
    return "".join(parts)


def open_league_gms():
    """Every team's general manager and head coach, in a pop-up."""
    league = state.league
    rows = []
    for t in sorted(league.teams, key=lambda t: t.name):
        hc = S.staff_of(league, t.id)["HC"]
        p = G.gm_of(league, t.id)
        v = G.view(league, p) if p else None
        rep, col = _rating(v["reputation"]) if v else ("-", "inherit")
        rows.append({"id": t.id, "team": t.name,
                     "gm": "You" if t.id == league.user_team_id else (v["name"] if v else "(open)"),
                     "age": v["age"] if v else "", "rep": rep, "rep_c": col, "since": v["since"] if v else "",
                     "here": _wl(v["here"]) if v and v["seasons"] else "-",
                     "known": "; ".join(w for _a, w in v["styles"]) if v else "",
                     "hc": (hc["name"] + (" (interim)" if hc.get("interim") else "")) if hc else "(open)",
                     "hc_since": hc["since"] if hc else ""})
    cols = [{"name": "team", "label": "Team", "field": "team", "align": "left", "sortable": True},
            {"name": "gm", "label": "General manager", "field": "gm", "align": "left"},
            {"name": "age", "label": "Age", "field": "age", "align": "right"},
            {"name": "rep", "label": "Reputation", "field": "rep", "align": "left"},
            {"name": "since", "label": "GM since", "field": "since", "align": "right", "sortable": True},
            {"name": "here", "label": "Record there", "field": "here", "align": "right"},
            {"name": "known", "label": "Known for", "field": "known", "align": "left"},
            {"name": "hc", "label": "Head coach", "field": "hc", "align": "left"},
            {"name": "hc_since", "label": "Coach since", "field": "hc_since", "align": "right", "sortable": True}]

    def body():
        ui.label("Reputations are what the league believes (they follow a GM's results); how well a GM judges "
                 "coaches is hidden. Click a team for its window.").classes("legend")
        t = ui.table(rows=rows, columns=cols, row_key="id", pagination={"rowsPerPage": 0}) \
            .props("flat dense hide-bottom").classes("roster-table w-full")
        t.add_slot("body-cell-rep", '<q-td :props="props"><span :style="{color: props.row.rep_c, fontWeight: 600}">'
                                    '{{ props.value }}</span></q-td>')
        t.on("rowClick", lambda e: popups.open_team(e.args[1]["id"]))
    popups.open_window("General managers and head coaches", 1320, body)


CSS = f"""
<style>
  .staff-mini {{ border-collapse: collapse; margin: 4px 0 6px; font-size: 14px; }}
  .staff-mini td, .staff-mini th {{ padding: 2px 10px 2px 0; text-align: left; }}
  .staff-mini th {{ color: var(--ink-soft); font-weight: 600; }}
  .staff-banner {{ display: flex; flex-wrap: wrap; gap: 18px; align-items: baseline; }}
  .staff-banner .big {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 22px; }}
  .carousel-box {{ border-left: 4px solid {theme.FLAG}; }}
</style>
"""


def build_staff_tab(on_change=None):
    """Builds the Staff page. Returns a function that refreshes it."""
    league = state.league
    S.ensure(league)
    ui.add_head_html(CSS)
    if not hasattr(state, "staff_selected"):
        state.staff_selected = None

    def viewing():
        return league.user_team_id if state.team_id == FREE_AGENTS else state.team_id

    def mine():
        return viewing() == league.user_team_id

    def changed():
        mark_changed()
        refresh()
        if on_change:
            on_change()

    # ---- Budget and carousel status ------------------------------------
    with ui.element("div").classes("w-full px-8 pt-3"):
        @ui.refreshable
        def banner():
            tid = viewing()
            team = next(t for t in league.teams if t.id == tid)
            bud, pay = S.budget(league, tid), S.payroll(league, tid)
            dead = S.dead_money(league, tid)
            with ui.element("div").classes("staff-banner"):
                ui.html(f'<span class="big">{escape(team.name)} staff</span>', sanitize=False)
                ui.html(f'Owner\'s staff budget <b>{fmt_money(bud)}</b> · paid <b>{fmt_money(pay)}</b> · '
                        f'room <b>{fmt_money(bud - pay)}</b>', sanitize=False) \
                    .tooltip("Each owner sets a yearly budget for the 8 jobs (some spend, some are cheap). "
                             "Coaches' pay is outside the player salary cap.")
                if dead:
                    ui.html(f'<span class="legend">Still owed to fired coaches: {fmt_money(dead)} this season '
                            f'(paid by the owner, not from your staff budget)</span>', sanitize=False)
                ui.button("General managers", icon="groups", on_click=open_league_gms) \
                    .props("no-caps flat dense color=green-10") \
                    .tooltip("Every team's general manager and head coach")
            if not mine():
                ui.label("Another team's staff: view only.").classes("legend")
                with ui.element("div").classes("report px-5 py-3").style("margin-top:6px; max-width:900px"):
                    ui.html(gm_html(league, tid, compact=True), sanitize=False)
                return
            car = league.staff.get("carousel")
            if car:
                with ui.element("div").classes("notice carousel-box").style("margin-top:6px"):
                    ui.html(f'<b>Coaching carousel, round {car["round"]} of 3: {S.ROUND_NAMES[car["round"]]}.</b> '
                            'Fire or extend your coaches, then make offers for your open jobs (Candidates). '
                            'Next (in the green bar) settles the round: every candidate takes the offer he likes '
                            'best, yours or another team\'s. Jobs still open after round 3 get your staff\'s pick.',
                            sanitize=False)
                    expiring = [j for j in car.get("expiring", ()) if S.staff_of(league, tid)[j]
                                and (S.staff_of(league, tid)[j]["through"] or 0) < league.season]
                    if expiring:
                        ui.html("<b>Contracts that ran out:</b> "
                                + ", ".join(escape(f"{S.JOB_SHORT[j]} {S.staff_of(league, tid)[j]['name']}")
                                            for j in expiring)
                                + ". Extend them now, or they leave when you press Next.", sanitize=False)
            elif season.in_offseason(league) or season.in_preseason(league) or season.in_regular_season(league):
                ui.label("Firing a coach now puts an interim in his job until the coaching carousel after "
                         "the season.").classes("legend")
        banner()

    # ---- Staff table, carousel, report ---------------------------------
    with ui.row().classes("w-full px-8 py-3 gap-5 no-wrap items-start"):
        with ui.column().classes("gap-3").style("flex: 1 1 0; min-width: 0"):
            table = ui.table(rows=[], columns=COLUMNS, row_key="id").props("flat dense hide-bottom") \
                .classes("roster-table w-full")
            for col in ("dev", "eval", "other"):
                table.add_slot(f"body-cell-{col}",
                               f'<q-td :props="props"><span :style="{{color: props.row.{col}_c, fontWeight: 600}}">'
                               '{{ props.value }}</span></q-td>')
            for col in COLUMNS:
                col["tip"] = COLUMN_TIPS.get(col["label"], "")
            table.columns = COLUMNS
            table.add_slot("header-cell", '<q-th :props="props">{{ props.col.label }}'
                                          '<q-tooltip v-if="props.col.tip">{{ props.col.tip }}</q-tooltip></q-th>')
            table.on("rowClick", lambda e: select(e.args[1]["id"]))

            @ui.refreshable
            def carousel_view():
                car = league.staff.get("carousel")
                if not mine():
                    return
                tid = viewing()
                if car:
                    with ui.element("div").classes("report px-5 py-4 w-full"):
                        ui.label("Your open jobs").classes("panel-heading").style("margin-top:0")
                        open_jobs = S.vacancies(league, tid)
                        if not open_jobs:
                            ui.label("None: every job is filled. Fire a coach to open his job.").classes("legend")
                        with ui.row().classes("gap-2"):
                            for job in open_jobs:
                                ui.button(f"Candidates: {S.JOB_NAMES[job].lower()}",
                                          on_click=lambda j=job: open_candidates(j)) \
                                    .props("no-caps unelevated color=green-10 dense")
                        offers = car.get("offers", {})
                        if offers:
                            ui.label("Your offers (settled at Next)").classes("panel-heading")
                            for cid, o in offers.items():
                                c = S.coach(league, cid)
                                with ui.row().classes("items-center gap-2"):
                                    ui.label(f"{S.JOB_SHORT[o['job']]}: {c['name']}, {fmt_money(o['salary'])} a year "
                                             f"for {o['years']} years · "
                                             f"{S.interest(league, c['id'], tid, o['job'], o['salary'])}")
                                    ui.button("Withdraw", on_click=lambda k=cid: withdraw(k)) \
                                        .props("no-caps flat dense color=grey-8")
                        mine_results = [r for r in car.get("results", []) if r["team"] == tid]
                        if mine_results:
                            ui.label("Earlier rounds").classes("panel-heading")
                            for r in mine_results:
                                ui.label(f"{r['name']} turned down your offer" if r.get("declined") else
                                         f"Hired {r['name']} as {S.JOB_NAMES[r['job']].lower()}")
                moves = [e for e in league.staff["log"] if e["season"] == league.season
                         and e["move"] in ("hired", "fired", "retired", "interim")]
                # General managers first: owners change them before the coaches (gm.py, Oct 22).
                moves = [{**e, "job": "GM"} for e in G.log(league, league.season)
                         if e["move"] in ("hired", "fired", "retired") and not e.get("quiet")] + moves
                if moves:
                    teams = {t.id: t for t in league.teams}
                    with ui.element("div").classes("report px-5 py-4 w-full"):
                        ui.label(f"Coaching moves around the league, {league.season}").classes("panel-heading") \
                            .style("margin-top:0")
                        verbs = {"hired": "hired", "fired": "fired", "retired": "retired", "interim": "named interim"}
                        lines = "".join(
                            f'<tr><td>{escape(teams[e["team"]].abbrev) if e["team"] in teams else ""}</td>'
                            f'<td>{escape(verbs[e["move"]])}</td>'
                            f'<td>{escape("General manager" if e["job"] == "GM" else S.JOB_SHORT.get(e["job"], ""))}</td>'
                            f'<td>{escape(e["name"])}</td><td class="legend">{escape(e.get("note") or "")}</td></tr>'
                            for e in reversed(moves[-60:]))
                        ui.html('<table class="staff-mini"><tr><th>Team</th><th>Move</th><th>Job</th><th>Coach</th>'
                                f'<th></th></tr>{lines}</table>', sanitize=False)
            carousel_view()

        with ui.element("div").classes("report px-6 py-5") \
                .style("flex: 0 0 470px; height: calc(100vh - 230px); overflow-y: auto"):
            @ui.refreshable
            def report():
                cid = state.staff_selected
                c = S.coach(league, cid) if cid is not None else None
                if c is None or c["team"] != viewing():
                    ui.label("No coach selected").classes("panel-heading").style("margin-top:0")
                    ui.label("Click a row for his reputation, style, record and your options (extend, fire).") \
                        .classes("legend")
                    return
                job = c["job"]
                if mine():
                    with ui.row().classes("gap-2 mb-2"):
                        if (c["through"] or 0) <= league.season and not c.get("interim"):
                            ui.button("Extend", icon="draw", on_click=lambda: extend(job)) \
                                .props("no-caps unelevated color=green-10 dense") \
                                .tooltip(f"Keep him: a new contract at his asking price "
                                         f"({fmt_money(S.market_value(league, c, job))} a year)")
                        ui.button("Fire", icon="logout", on_click=lambda: confirm_fire(job)) \
                            .props("no-caps outline color=red-9 dense") \
                            .tooltip("He's still owed the rest of his contract (the owner pays it)")
                ui.html(coach_html(league, c, job), sanitize=False)
            report()

    # ---- Candidates (a pop-up over the page) ---------------------------
    def open_candidates(job):
        tid = viewing()
        pool = S.candidates(league, job, tid)
        pool.sort(key=lambda c: -S.reputation_score(c, job))
        teams = {t.id: t for t in league.teams}
        cols = [{"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "age", "label": "Age", "field": "age", "align": "right"},
                {"name": "now", "label": "Now", "field": "now", "align": "left"},
                {"name": "bg", "label": "Background", "field": "bg", "align": "left"},
                {"name": "dev", "label": "Development", "field": "dev", "align": "left"},
                {"name": "eval", "label": "Evaluating", "field": "eval", "align": "left"},
                {"name": "other", "label": "Conditioning / Rehab", "field": "other", "align": "left"},
                {"name": "exp", "label": "Experience", "field": "exp", "align": "left"},
                {"name": "ask", "label": "Asking", "field": "ask", "align": "right"},
                {"name": "interest", "label": "Interest at his asking price", "field": "interest", "align": "left"}]
        rows = []
        for c in pool[:150]:
            r = _row(league, job, c)
            ask = S.market_value(league, c, job)
            now = ("Out of work" if c["team"] is None else
                   f"{S.JOB_SHORT[c['job']]}, {teams[c['team']].abbrev}" if c["team"] in teams else "")
            if c.get("college"):
                now = "College coach"
            elif c.get("new") is not None:
                now = "NFL assistant" if c["track"] == "coach" else "Assistant"
            exp = c["exp"]
            r.update({"now": now, "ask": fmt_money(ask), "ask_k": ask,
                      "exp": (f"HC {exp['HC']} yrs" if exp.get("HC") else
                              f"Coordinator {exp['coord']} yrs" if exp.get("coord") else f"{exp['years']} yrs"),
                      "interest": S.interest(league, c["id"], tid, job, ask)})
            rows.append(r)

        def body():
            ui.label(f"{len(pool)} candidates. Ratings are reputations (the truth is hidden). Their teams can't "
                     "stop a coach from taking a promotion. Click a row to make an offer.").classes("legend")
            t = ui.table(rows=rows, columns=cols, row_key="id", pagination={"rowsPerPage": 0}) \
                .props("flat dense virtual-scroll hide-bottom").classes("roster-table w-full") \
                .style("height: 60vh")
            for col in ("dev", "eval", "other"):
                t.add_slot(f"body-cell-{col}",
                           f'<q-td :props="props"><span :style="{{color: props.row.{col}_c, fontWeight: 600}}">'
                           '{{ props.value }}</span></q-td>')
            t.on("rowClick", lambda e: offer_dialog(e.args[1]["id"], job, dlg))
        dlg = popups.open_window(f"Candidates: {S.JOB_NAMES[job].lower()}", 1180, body)

    def offer_dialog(cid, job, parent):
        tid = viewing()
        c = S.coach(league, cid)
        ask = S.market_value(league, c, job)
        years_opts = sorted(S.CONTRACT_YEARS[job])
        st = {"salary": ask, "years": years_opts[-1]}

        def body():
            ui.html(coach_html(league, c, job), sanitize=False)
            ui.separator()
            ui.label(f"His asking price: {fmt_money(ask)} a year. Your budget room: "
                     f"{fmt_money(S.room(league, tid))}.").classes("legend")
            with ui.row().classes("items-center gap-3"):
                sal = ui.number("Salary a year ($K)", value=ask, step=25, min=0, format="%.0f") \
                    .props("dense outlined").classes("w-48")
                yrs = ui.select({y: f"{y} years" for y in range(1, 7)}, value=st["years"], label="Years") \
                    .props("dense outlined").classes("w-32")
            interest = ui.label("").classes("condensed text-xl")

            def update():
                st["salary"] = int(sal.value or 0)
                st["years"] = int(yrs.value)
                interest.text = S.interest(league, cid, tid, job, st["salary"])
            sal.on_value_change(lambda _e: update())
            yrs.on_value_change(lambda _e: update())
            update()

            def go():
                ok, msg = S.make_offer(league, cid, job, st["salary"], st["years"])
                ui.notify(msg, type="positive" if ok else "warning", position="top")
                if ok:
                    dlg.close()
                    parent.close()
                    changed()
            ui.button("Make offer", icon="send", on_click=go).props("no-caps unelevated color=green-10")
        dlg = popups.open_window(f"Offer: {c['name']}", 560, body)

    # ---- Actions --------------------------------------------------------
    def select(cid):
        state.staff_selected = cid if cid != -1 else None
        mark_selected()
        report.refresh()

    def mark_selected():
        sid = state.staff_selected if state.staff_selected is not None else -2
        table.props(f':table-row-class-fn="row => row.id === {sid} ? \'is-selected\' : \'\'"')

    def extend(job):
        ok, msg = S.extend(league, league.user_team_id, job)
        ui.notify(msg, type="positive" if ok else "warning", position="top")
        if ok:
            changed()

    def withdraw(cid):
        S.withdraw_offer(league, cid)
        changed()

    def confirm_fire(job):
        tid = league.user_team_id
        c = S.staff_of(league, tid)[job]
        if not c:
            return
        owed_years = max(0, (c["through"] or 0) - league.season + 1)
        in_car = S.in_carousel(league)

        def do():
            if in_car:
                S.fire(league, tid, job)
                msg = f"{c['name']} fired. His job is open: see Candidates."
            else:
                _f, interim = S.fire_in_season(league, tid, job)
                msg = (f"{c['name']} fired. {interim['name']} takes over as interim until the coaching carousel."
                       if interim else f"{c['name']} fired.")
            ui.notify(msg, type="positive", position="top")
            state.staff_selected = None
            dlg.close()
            changed()

        with ui.dialog() as dlg, ui.card().classes("p-6").style("max-width:520px"):
            ui.label(f"Fire {c['name']}?").classes("condensed text-2xl")
            ui.label((f"He's owed {fmt_money(c['salary'])} a year for {owed_years} more season"
                      f"{'s' if owed_years != 1 else ''} (the owner pays it, not your staff budget; less what "
                      f"his next job pays). " if owed_years and not c.get("interim") else "")
                     + ("His job opens for the carousel." if in_car else
                        "Someone on your staff takes over as interim until the coaching carousel after the season."))
            with ui.row().classes("justify-end w-full mt-2 gap-2"):
                ui.button("Cancel", on_click=dlg.close).props("flat no-caps")
                ui.button("Fire him", on_click=do).props("no-caps unelevated color=red-9")
        dlg.open()

    def refresh():
        tid = viewing()
        table.rows = [_row(league, job, c) for job, c in S.staff_of(league, tid).items()]
        mark_selected()
        banner.refresh()
        carousel_view.refresh()
        report.refresh()

    refresh()
    return refresh
