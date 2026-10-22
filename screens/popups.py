# popups.py
# Pop-up windows over the game screen (Blake, Oct 21: "like how front office
# football does it"). The tabs stay the home base; a player's card, a game's
# summary and the offseason report open in a pop-up on top of whatever tab
# you're on, and closing it (X, Esc, or a click outside) puts you right back,
# with the tab's scroll position and filters as you left them.
#
# Pop-ups stack (Blake's pick): click a player inside one and his card opens
# on top of it, a little down and to the right; close it to get back to the
# one underneath. Drag a pop-up by its green header to move it.
#
# Pop-ups block the screen behind them, so nothing can be simmed while one is
# open: each one is drawn fresh when it opens and is never out of date.
#
# The game page calls install() once. Any player link on that page
# (<a href="/player/12">) then opens a pop-up instead of leaving the page.
# On other pages (the stand-alone player card page) links work as before.

from nicegui import context, ui

from .state import state

CASCADE = 28                 # px each stacked pop-up sits down and right of the one below it

_CSS = """
<style>
.fof-popup { padding: 0; overflow: hidden; display: flex; flex-direction: column;
             max-width: 96vw !important; max-height: 92vh !important; background: var(--chalk); }
.fof-popup-head { cursor: move; user-select: none; }
.fof-popup-body { overflow-y: auto; min-height: 0; }
.fof-stacked .q-dialog__backdrop { background: rgba(0, 0, 0, 0.12); }
</style>
"""

# Player links open pop-ups; pop-ups move when dragged by their header.
_JS = """
<script>
document.addEventListener('click', e => {
  const a = e.target.closest && e.target.closest('a[href^="/player/"]');
  if (!a || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const pid = parseInt(a.getAttribute('href').split('/')[2]);
  if (isNaN(pid)) return;
  e.preventDefault();
  e.stopPropagation();
  emitEvent('fof_player', pid);
}, true);
document.addEventListener('mousedown', e => {
  const head = e.target.closest && e.target.closest('.fof-popup-head');
  if (!head || e.button !== 0 || e.target.closest('button, a, input, .q-field')) return;
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


class _Host:
    """The pop-ups open on one game page (one per window)."""

    def __init__(self):
        self.box = ui.element("div")          # pop-ups are built in here
        self.open = []                        # open pop-ups, bottom first


def install():
    """The game page calls this once: player links open pop-ups from then on."""
    ui.add_head_html(_CSS)
    ui.add_body_html(_JS)
    host = _Host()
    context.client.fof_popups = host

    def on_player(e):
        pid = e.args[0] if isinstance(e.args, list) else e.args
        open_player(int(pid))
    ui.on("fof_player", on_player)


def _host():
    return getattr(context.client, "fof_popups", None)


def show_player(pid):
    """A player's card: a pop-up on the game page, else his card page."""
    if _host() is None:
        ui.navigate.to(f"/player/{pid}")
    else:
        open_player(pid)


def _popup(width):
    """Opens an empty pop-up; returns (header, body) to draw into."""
    host = _host()
    depth = len(host.open)
    shift = CASCADE * depth
    with host.box:
        dialog = ui.dialog()
        if depth:
            dialog.classes("fof-stacked")
        with dialog:
            card = ui.card().classes("fof-popup").style(
                f"width:{width}px; transform:translate({shift}px, {shift}px)")
            card.props(f'data-dx="{shift}" data-dy="{shift}"')
            with card:
                head = ui.element("div").classes("field-band fof-popup-head w-full px-6 pt-3 pb-4")
                body = ui.element("div").classes("fof-popup-body w-full")
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


def open_player(pid):
    from . import player_card_page as PC
    league = state.league
    p = next((x for x in league.players if x.id == pid), None)
    dialog, head, body = _popup(1440)
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
    dialog, head, body = _popup(900)
    with head:
        _title_row(dialog, "Game summary")
    with body:
        with ui.element("div").classes("report px-6 py-5 m-4"):
            SP.game_box(league, g)


def open_offseason():
    from . import offseason_page as OP
    league = state.league
    dialog, head, body = _popup(1440)
    with head:
        _title_row(dialog, "Offseason report")
        OP.report_header(league)
    with body:
        OP.report_body(league)
