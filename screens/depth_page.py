# depth_page.py
# The Depth chart tab. Pick a unit (Offense, Defense, Special teams).
# Left: a picture of the chosen package on the field, then every spot in
# that unit with its starter and backups. Right: edit the spot you clicked
# and choose captains. Only your own team can be edited; other teams are
# view-only.

from html import escape

from nicegui import ui

from engine import depth
from engine import formatting as fmt
from engine.scale import shown
from . import theme
from .formations import formation_svg, UNIT_PACKAGES
from .popups import player_link
from .state import state, FREE_AGENTS, is_user_team, mark_changed, injury_tag

RANK_NAMES = ["Starter", "2nd", "3rd", "4th"]
UNITS = ["Offense", "Defense", "Special teams"]


def chip(value, position=None):
    """A small colored rating: swatch + number (value is the engine's
    internal rating; shown on the players' scale, engine/scale.py)."""
    value = shown(value, position)
    color = theme.RATING_COLORS[fmt.skill_word(value)]
    return (f'<span class="rating num" title="{fmt.skill(value)}">'
            f'<span class="swatch" style="background:{color}"></span>{value}</span>')


def pos_tag(code):
    """A colored tag for a position (QB) or a depth chart spot (LT uses T's color)."""
    position = depth.SLOTS[code][1] if code in depth.SLOTS else code
    if position in ("KR", "PR"):
        position = "RET"
    return f'<span class="pos-tag" style="{theme.position_style(position)}">{code}</span>'


def build_depth_tab(on_change):
    """Builds the Depth chart tab. on_change is called after every edit
    (so other tabs can update). Returns a function that refreshes this tab."""
    league = state.league
    by_id = {p.id: p for p in league.players}

    def chart():
        return league.depth_charts.setdefault(state.team_id, {})

    def roster():
        return league.team_players(state.team_id)

    def editable():
        return is_user_team(state.team_id)

    def marks(p):
        """★ for a captain. (Starters are obvious on this tab: the Starter column.)"""
        caps = league.captains.get(state.team_id, {}).values()
        return '<span class="captain-star" title="Captain">★</span> ' if p.id in caps else ""

    # ---- Top bar --------------------------------------------------------
    with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
        ui.toggle(UNITS, value=state.depth_unit, on_change=lambda e: set_unit(e.value)) \
            .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9")

        ui.html('<span class="key"><span class="starter-dot">●</span> Starter '
                '<span class="captain-star">★</span> Captain</span>', sanitize=False)

        @ui.refreshable
        def top_controls():
            if state.team_id == FREE_AGENTS:
                return
            if editable():
                ui.button("Auto-fill depth chart", on_click=lambda: auto_fill()) \
                    .props("no-caps unelevated color=green-10") \
                    .tooltip("Let the AI set your whole depth chart. You can still change anything after.")
            else:
                ui.label("View only: you can change your own team's depth chart, not other teams'.") \
                    .classes("legend")
        top_controls()

    with ui.row().classes("w-full px-8 py-4 gap-5 no-wrap items-start"):
        # ---- Left: picture and spot list --------------------------------
        with ui.column().classes("gap-0 depth-board") \
                .style("flex: 1 1 0; min-width: 0; height: calc(100vh - 300px); overflow-y: auto"):
            @ui.refreshable
            def board():
                if state.team_id == FREE_AGENTS:
                    ui.label("Free agents don't have a depth chart").classes("condensed text-2xl")
                    ui.label("Pick a team from the Team list at the top.").classes("legend")
                    return
                c = chart()
                unit = state.depth_unit
                for note in depth.problems(c, roster()):
                    ui.label(note).classes("depth-warning w-full")

                if unit in UNIT_PACKAGES:
                    with ui.row().classes("items-center gap-3 mb-2"):
                        ui.label("Formation").classes("condensed text-lg")
                        ui.select(UNIT_PACKAGES[unit], value=state.packages[unit],
                                  on_change=lambda e: set_package(e.value)) \
                            .props("dense outlined options-dense").classes("w-48")
                        ui.label(PACKAGE_NOTES[state.packages[unit]]).classes("legend")
                    ui.html(formation_svg(c, state.packages[unit], by_id.get), sanitize=False) \
                        .classes("w-full")

                header = "".join(f"<span>{r}</span>" for r in RANK_NAMES)
                ui.html(f'<div class="depth-row depth-head"><span>Spot</span><span></span>{header}</div>',
                        sanitize=False).classes("w-full mt-3")
                for slot, (label, _pos, slot_unit) in depth.SLOTS.items():
                    if slot_unit != unit:
                        continue
                    ids = c.get(slot, [])
                    cells = []
                    for i in range(depth.DEPTH_SIZE):
                        p = by_id.get(ids[i]) if i < len(ids) else None
                        if p is None:
                            cells.append('<span class="legend">-</span>')
                        else:
                            cells.append(f'<span>{marks(p)}{player_link(p)} <span class="legend">{p.position}</span> '
                                         f'{chip(depth.rating_at(p, slot), depth.SLOTS[slot][1])}{injury_tag(p.id)}</span>')
                    selected = " is-selected" if slot == state.depth_slot else ""
                    row = ui.html(f'<div class="depth-row{selected}">{pos_tag(slot)}'
                                  f'<span class="legend">{escape(label)}</span>{"".join(cells)}</div>',
                                  sanitize=False).classes("w-full")
                    row.on("click", lambda _e, s=slot: select_slot(s))
            board()

        # ---- Right: captains and the spot editor -------------------------
        panel = ui.element("div").classes("report px-6 py-5") \
            .style("flex: 0 0 470px; height: calc(100vh - 300px); overflow-y: auto")

    @ui.refreshable
    def side_panel():
        if state.team_id == FREE_AGENTS:
            return
        captains_box()
        spot_box()

    # ---- Side panel pieces ---------------------------------------------
    def captains_box():
        ui.label("Captains").classes("panel-heading").style("margin-top:0")
        ui.label("Voted on by the players each season, mostly for leadership. "
                 "Better leaders give their unit a very small boost in games.").classes("legend")
        caps = league.captains.get(state.team_id, {})
        for unit in ("Offense", "Defense"):
            p = by_id.get(caps.get(unit))
            with ui.row().classes("w-full items-center no-wrap gap-2 edit-row"):
                ui.label(unit).classes("legend").style("width:62px")
                if p:
                    ui.html(f'<span class="captain-star">★</span> {pos_tag(p.position)} '
                            f'{player_link(p)} <span class="legend">leadership '
                            f'{fmt.trait(p.leadership)}</span>', sanitize=False)
                else:
                    ui.label("None").classes("legend")

    def spot_box():
        slot = state.depth_slot
        label, natural, _unit = depth.SLOTS[slot]
        c = chart()
        ids = c.setdefault(slot, [])

        ui.html(pos_tag(slot), sanitize=False).classes("mt-5")
        ui.label(label).classes("condensed").style("font-size:30px;font-weight:700;line-height:1.1")
        if slot == "RB3":
            ui.label("Plays running back in passing situations: 3rd and 4th down with 4+ to go, 2nd and 8+, "
                     "the two-minute drill, and two scores down in the 4th quarter. Rated on pass blocking, "
                     "hands, route running and elusiveness; the arrow shows his ceiling here.").classes("legend")
        else:
            natural_txt = {"KR": "Kick returns", "PR": "Punt returns"}.get(natural, f"Natural position: {natural}")
            ui.label(f"{natural_txt}. Rating shown is how he'd play this spot now; "
                     f"the arrow shows his ceiling here.").classes("legend")

        ui.label("Depth order").classes("panel-heading")
        if not ids:
            ui.label("Nobody listed." + (" Add a player below." if editable() else "")).classes("legend")
        for i, pid in enumerate(ids):
            p = by_id.get(pid)
            if p is None:
                continue
            with ui.row().classes("w-full items-center no-wrap gap-2 edit-row"):
                ui.label(RANK_NAMES[i]).classes("legend").style("width:52px")
                ui.html(player_line(p, slot), sanitize=False).style("flex:1")
                if editable():
                    ui.button(icon="arrow_upward", on_click=lambda _e, i=i: move(i, -1)) \
                        .props("flat round dense" + (" disable" if i == 0 else "")).tooltip("Move up")
                    ui.button(icon="arrow_downward", on_click=lambda _e, i=i: move(i, 1)) \
                        .props("flat round dense" + (" disable" if i == len(ids) - 1 else "")).tooltip("Move down")
                    ui.button(icon="close", on_click=lambda _e, i=i: remove(i)) \
                        .props("flat round dense").tooltip("Remove from this spot")

        if not editable():
            return
        ui.label("Add a player").classes("panel-heading")
        ui.label("Best fits first.").classes("legend")
        starts_at = {}
        for s, lst in c.items():
            if lst:
                starts_at.setdefault(lst[0], []).append(s)
        candidates = sorted([p for p in roster() if p.id not in ids],
                            key=lambda p: depth.rating_at(p, slot), reverse=True)
        full = len(ids) >= depth.DEPTH_SIZE
        for p in candidates:
            with ui.row().classes("w-full items-center no-wrap gap-2 edit-row"):
                extra = ""
                if p.id in starts_at:
                    extra = f' <span class="legend">starts at {", ".join(starts_at[p.id])}</span>'
                ui.html(player_line(p, slot) + extra, sanitize=False).style("flex:1")
                ui.button("Starter", on_click=lambda _e, pid=p.id: add(pid, as_starter=True)) \
                    .props("flat dense no-caps color=green-10").tooltip("Make him the starter here")
                ui.button("Backup", on_click=lambda _e, pid=p.id: add(pid, as_starter=False)) \
                    .props("flat dense no-caps color=grey-8" + (" disable" if full else "")) \
                    .tooltip("Add him at the bottom of this spot's list")

    def player_line(p, slot):
        """Name, rating now, ceiling at this spot, and any penalty in words."""
        fit = depth.spot_fit(p, slot)
        side = {"L": "left side", "R": "right side", "B": "either side"}.get(p.side, "")
        side_txt = f' <span class="legend">({side})</span>' if side else ""
        spot_pos = depth.SLOTS[slot][1]
        ceiling = (f' <span class="legend">→ {shown(fit["ceiling"], spot_pos)}</span>'
                   if shown(fit["ceiling"], spot_pos) > shown(fit["now"], spot_pos) else "")
        notes = f'<div class="fit-note">{escape("; ".join(fit["notes"]))}</div>' if fit["notes"] else ""
        size = f' <span class="size-note">{escape(fit["size"])}</span>' if fit["size"] else ""
        return (f'{pos_tag(p.position)} {player_link(p)}{side_txt} {chip(fit["now"], spot_pos)}{ceiling}{size}'
                f'{injury_tag(p.id)}{notes}')

    # ---- Actions --------------------------------------------------------
    def saved():
        mark_changed()
        board.refresh()
        side_panel.refresh()
        on_change()

    def set_unit(unit):
        state.depth_unit = unit
        first = next(s for s, v in depth.SLOTS.items() if v[2] == unit)
        if depth.SLOTS[state.depth_slot][2] != unit:
            state.depth_slot = first
        board.refresh()
        side_panel.refresh()

    def select_slot(slot):
        state.depth_slot = slot
        board.refresh()
        side_panel.refresh()

    def set_package(package):
        state.packages[state.depth_unit] = package
        board.refresh()

    def move(i, step):
        ids = chart()[state.depth_slot]
        j = i + step
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            saved()

    def remove(i):
        del chart()[state.depth_slot][i]
        saved()

    def add(pid, as_starter):
        ids = chart().setdefault(state.depth_slot, [])
        if as_starter:
            ids.insert(0, pid)
            del ids[depth.DEPTH_SIZE:]           # the 5th player drops off the list
        elif len(ids) < depth.DEPTH_SIZE:
            ids.append(pid)
        else:
            ui.notify("This spot holds 4 players. Remove one first.")
            return
        saved()

    def auto_fill():
        league.auto_depth_chart(state.team_id)
        ui.notify("The AI set your depth chart.")
        saved()

    def refresh():
        top_controls.refresh()
        board.refresh()
        side_panel.refresh()

    with panel:          # drawn last, once everything it uses exists
        side_panel()
    return refresh


PACKAGE_NOTES = {
    "11 personnel": "1 back, 1 tight end, 3 receivers. The most common modern grouping.",
    "12 personnel": "1 back, 2 tight ends, 2 receivers.",
    "21 personnel": "Fullback and halfback, 1 tight end, 2 receivers.",
    "13 personnel": "1 back, 3 tight ends, 1 receiver. Short yardage.",
    "22 personnel": "Fullback and halfback, 2 tight ends, 1 receiver. Goal line.",
    "10 personnel": "1 back, no tight end, 4 receivers.",
    "Base 4-3": "4 linemen, 3 linebackers, 4 defensive backs.",
    "Nickel": "A 5th defensive back replaces a linebacker. Used against 3 receivers.",
    "Dime": "6 defensive backs, 1 linebacker. Passing downs.",
}
