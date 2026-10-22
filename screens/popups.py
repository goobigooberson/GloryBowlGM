# popups.py
# Pop-up windows over the game screen (Blake, Oct 21: "like how front office
# football does it"; Oct 22: "go harder on making more things pop ups").
# The pages stay the home base; a player's card, a team, a game's summary and
# the offseason report open in a pop-up on top of whatever page you're on, and
# closing it (X, Esc, or a click outside) puts you right back, with the page's
# scroll position and filters as you left them.
#
# Pop-ups stack (Blake's pick): click a player inside one and his card opens
# on top of it, a little down and to the right; close it to get back to the
# one underneath. Drag a pop-up by its green header to move it.
#
# Pop-ups block the screen behind them, so nothing can be simmed while one is
# open: each one is drawn fresh when it opens and is never out of date.
#
# The game page calls install() once. Any link on that page to a player
# (<a href="/player/12">), a team (/team/3) or a played game (/game/57) then
# opens a pop-up instead of leaving the page; player_link(), team_link() and
# game_link() write those links. On other pages (the stand-alone player card
# page) player links work as before.

from html import escape

from nicegui import context, ui

from .state import state

CASCADE = 28                 # px each stacked pop-up sits down and right of the one below it

_CSS = """
<style>
.fof-popup { padding: 0; overflow: hidden; display: flex; flex-direction: column;
             max-width: 96vw !important; max-height: 92vh !important; background: var(--chalk);
             border-radius: 4px !important; box-shadow: 0 18px 50px rgba(0,0,0,.35) !important; }
.fof-popup-head { cursor: move; user-select: none; }
.fof-popup-body { overflow-y: auto; min-height: 0; }
.fof-stacked .q-dialog__backdrop { background: rgba(0, 0, 0, 0.12); }
.fof-tabs { border-bottom: 1px solid var(--line); background: #E9EEE6; padding: 0 16px; }
.tlink { color: inherit; text-decoration: none; }
.tlink:hover { color: var(--turf); text-decoration: underline; }
.team-head-abbr { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 44px; line-height: 1; }
</style>
"""

# Links open pop-ups; pop-ups move when dragged by their header.
_JS = """
<script>
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[href^="/player/"], a[href^="/team/"], a[href^="/game/"]');
  if (!a || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const parts = a.getAttribute('href').split('/');
  const id = parseInt(parts[2]);
  if (isNaN(id)) return;
  e.preventDefault();
  e.stopPropagation();
  emitEvent('fof_open', [parts[1], id]);
}, true);
document.addEventListener('mousedown', e => {
  const head = e.target.closest && e.target.closest('.fof-popup-head');
  if (!head || e.button !== 0 || e.target.closest('button, a, input, .q-field, .q-tab')) return;
  const card = head.closest('.fof-popup');
  const x0 = e.clientX, y0 = e.clientY;
  const dx0 = parseFloat(card.dataset.dx || 0), dy0 = parseFloat(card.dataset.dy || 0);
  const r = card.getBoundingClientRect(), hh = head.getBoundingClientRect().height;
  const move = ev => {
    // Keep the header (and its close button) on screen.
    const mx = Math.min(Math.max(ev.clientX - x0, 120 - r.right), innerWidth - 120 - r.left);
    const my = Math.min(Math.max(ev.clientY - y0, -r.top), innerHeight - hh - r.top);
    const dx = dx0 + mx, dy = dy0 + my;
    card.dataset.dx = dx; card.dataset.dy = dy;
    card.style.transform = `translate(${dx}px, ${dy}px)`;
  };
  const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); };
  document.addEventListener('mousemove', move);
  document.addEventListener('mouseup', up);
  e.preventDefault();
});
</script>
"""


# ---- Links (any screen can write these; on the game page they open pop-ups) ----

def player_link(p, text=None):
    return f'<a class="plink" href="/player/{p.id}">{escape(text if text is not None else p.name)}</a>'


def team_link(team, text=None):
    return f'<a class="tlink" href="/team/{team.id}">{escape(text if text is not None else team.name)}</a>'


def game_link(gid, html_text):
    """html_text is already HTML (escape it first)."""
    return f'<a class="tlink" href="/game/{gid}">{html_text}</a>'


class _Host:
    """The pop-ups open on one game page (one per window)."""

    def __init__(self):
        self.box = ui.element("div")          # pop-ups are built in here
        self.open = []                        # open pop-ups, bottom first
        self.view_team = None                 # main page: show this team on the pages behind


def install():
    """The game page calls this once: links open pop-ups from then on."""
    ui.add_head_html(_CSS)
    ui.add_body_html(_JS)
    host = _Host()
    context.client.fof_popups = host

    def on_open(e):
        kind, num = e.args if isinstance(e.args, list) else (None, None)
        if kind == "player":
            open_player(int(num))
        elif kind == "team":
            open_team(int(num))
        elif kind == "game":
            open_game(int(num))
    ui.on("fof_open", on_open)


def set_view_team(handler):
    """The main page's 'show this team' (the team picker in the green bar)."""
    host = _host()
    if host is not None:
        host.view_team = handler


def _host():
    return getattr(context.client, "fof_popups", None)


def show_player(pid):
    """A player's card: a pop-up on the game page, else his card page."""
    if _host() is None:
        ui.navigate.to(f"/player/{pid}")
    else:
        open_player(pid)


def close_all():
    """Close every open pop-up (before a big change such as a reload)."""
    host = _host()
    for dialog in list(host.open if host else []):
        dialog.close()


def _popup(width, height=None):
    """Opens an empty pop-up; returns (dialog, header, body) to draw into.
    height: a fixed height (CSS, e.g. '92vh') for windows with their own scrolling."""
    host = _host()
    depth = len(host.open)
    shift = CASCADE * depth
    with host.box:
        dialog = ui.dialog()
        if depth:
            dialog.classes("fof-stacked")
        with dialog:
            card = ui.card().classes("fof-popup").style(
                f"width:{width}; transform:translate({shift}px, {shift}px)"
                + (f"; height:{height}" if height else ""))
            card.props(f'data-dx="{shift}" data-dy="{shift}"')
            with card:
                head = ui.element("div").classes("field-band fof-popup-head w-full px-6 pt-3 pb-4")
                body = ui.element("div").classes("fof-popup-body w-full").style("flex:1 1 auto")
    host.open.append(dialog)

    def gone():
        if dialog in host.open:
            host.open.remove(dialog)
        dialog.delete()
    dialog.on("hide", gone)
    dialog.open()
    return dialog, head, body


def _title_row(dialog, title):
    with ui.row().classes("w-full items-center justify-between no-wrap"):
        ui.label(title).classes("condensed text-lg opacity-90")
        ui.button(icon="close", on_click=dialog.close).props("flat round dense color=white") \
            .tooltip("Close (Esc)")


def _px(width):
    return f"{width}px" if isinstance(width, int) else width


def open_player(pid):
    from . import player_card_page as PC
    league = state.league
    p = next((x for x in league.players if x.id == pid), None)
    dialog, head, body = _popup(_px(1440))
    with head:
        _title_row(dialog, "Player card")
        if p is None:
            ui.label("Player not found").classes("team-name mt-2")
            return
        PC.card_header(league, p)
    with body:
        PC.card_body(league, p)


def open_game(gid):
    from engine import season as S
    from . import schedule_page as SP
    league = state.league
    g = next((x for x in S.all_games(league) if x["id"] == gid), None)
    if g is None or not g["played"]:
        return
    dialog, head, body = _popup(_px(900))
    with head:
        _title_row(dialog, "Game summary")
    with body:
        with ui.element("div").classes("report px-6 py-5 m-4"):
            SP.game_box(league, g)


def open_team(tid):
    """Any team, FOF8's team window: its season and stats, and its roster."""
    from datetime import date
    from engine import season as S
    from engine import stats as ST
    from engine import transactions
    from . import roster_page as RP
    from . import stats_page as SPg
    from .state import team_starter_ids
    league = state.league
    team = league.team(tid)
    dialog, head, body = _popup(_px(1440), "92vh")
    with head:
        _title_row(dialog, "Team")
        rec = S.records(league)[tid]
        played = rec["w"] + rec["l"] + rec["t"]
        sub = [f"{team.conference} Conference, {team.division} Division"]
        if played and not S.in_offseason(league):
            order = S.division_standings(league)[team.conference][team.division]
            if tid in order:
                sub.append(f"{S.record_text(rec)} · {('1st', '2nd', '3rd', '4th')[order.index(tid)]} in the division")
        with ui.row().classes("items-end gap-5 mt-2 w-full no-wrap"):
            ui.label(team.abbrev).classes("team-head-abbr")
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-center gap-3"):
                    ui.label(team.name).classes("team-name")
                    if tid == league.user_team_id:
                        ui.label("Your team").classes("your-team-badge")
                ui.label("   ·   ".join(sub)).classes("opacity-80")
            ui.element("div").style("flex:1")
            host = _host()
            if host and host.view_team:
                ui.button("Show on the team pages", icon="open_in_browser",
                          on_click=lambda: (dialog.close(), host.view_team(tid))) \
                    .props("outline color=white no-caps") \
                    .tooltip("Close this window and look at this team's roster, depth chart and schedule "
                             "on the pages behind it (the team picker in the green bar)")
    with body:
        with ui.tabs().props("no-caps dense align=left active-color=green-10 indicator-color=green-10") \
                .classes("fof-tabs w-full") as tabs:
            t_sum = ui.tab("Team summary")
            t_roster = ui.tab("Roster")
        with ui.tab_panels(tabs, value=t_sum, animated=False).classes("w-full") \
                .style("background:transparent"):
            with ui.tab_panel(t_sum).classes("px-6 py-4"):
                ui.html(SPg.team_summary_html(league, tid, ST.REGULAR), sanitize=False).classes("w-full")
            with ui.tab_panel(t_roster).classes("px-6 py-4"):
                today = date(league.season, 9, 1)
                starters = team_starter_ids(tid)
                caps = set(league.captains.get(tid, {}).values())
                players = league.team_players(tid)
                ps = transactions.practice_players(league, tid)
                rows = [RP.player_row(p, today, starters, caps) for p in players]
                rows += [{**RP.player_row(p, today, starters, caps), "name": p.name + " (practice squad)"}
                         for p in ps]
                ui.label(f"{len(players)} on the roster, {len(ps)} on the practice squad. "
                         "Click a player for his card.").classes("legend mb-2")
                table = ui.table(rows=rows, columns=RP.COLUMNS, row_key="id",
                                 pagination={"rowsPerPage": 0, "sortBy": "pos"}) \
                    .props("flat dense hide-bottom").classes("roster-table w-full")
                RP.add_table_slots(table)
                table.on("rowClick", lambda e: open_player(e.args[1]["id"]))


class KeptWindow:
    """A big window that stays built while it's closed (the draft room): the
    page keeps refreshing what's inside, so it's up to date whenever it opens,
    and your place in it (filters, scroll) is kept. build() draws the inside and
    its return value is kept as .content. Pages inside that size themselves from
    the green bar's height (--bar-h) fit the window instead."""

    HEAD_PX = 48

    def __init__(self, title, build, width="96vw", height="92vh"):
        host = _host()
        self.host = host
        with host.box:
            self.dialog = ui.dialog()
            with self.dialog:
                card = ui.card().classes("fof-popup").style(f"width:{width}; height:{height}")
                with card:
                    with ui.element("div").classes("field-band fof-popup-head w-full px-5 py-2"):
                        _title_row(self.dialog, title)
                    with ui.element("div").classes("fof-popup-body w-full").style(
                            f"flex:1 1 auto; --bar-h: calc(100vh - {height} + {self.HEAD_PX}px)"):
                        self.content = build()

        def shown(e):
            if e.value and self.dialog not in host.open:
                host.open.append(self.dialog)
            elif not e.value and self.dialog in host.open:
                host.open.remove(self.dialog)
        self.dialog.on_value_change(shown)

    def open(self):
        self.dialog.open()

    def close(self):
        self.dialog.close()


def open_window(title, width, draw_body, draw_head=None, height=None):
    """A pop-up for a page's own detail view (the Draft page's prospect reports,
    draft order, trade offers...). draw_body() and draw_head() draw into it.
    width: pixels, or any CSS width. Returns the dialog (close it with dialog.close())."""
    dialog, head, body = _popup(_px(width), height)
    with head:
        _title_row(dialog, title)
        if draw_head:
            draw_head()
    with body:
        draw_body()
    return dialog


def open_offseason():
    from . import offseason_page as OP
    league = state.league
    dialog, head, body = _popup(_px(1440))
    with head:
        _title_row(dialog, "Offseason report")
        OP.report_header(league)
    with body:
        OP.report_body(league)
