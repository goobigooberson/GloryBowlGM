# nav.py
# The game screen's navigation: one slim green bar with six sections (Home,
# Team, Schedule, League, Draft, Bitter), each holding one or more of the old
# tabs, shown as a row of page buttons under the bar. From the layout research
# and the mockup Blake approved (docs/layout-research.md).
#
# The old tabs still exist underneath (main_page.py builds them, hidden), so
# every "go to the Draft tab" call keeps working; this file only decides which
# section a tab belongs to and draws the buttons.

from nicegui import ui

from . import theme

# Section -> its pages (the tab names in main_page.py), in order.
SECTIONS = [
    ("Home", ["Home"]),
    ("Team", ["Roster", "Depth chart", "Position counts", "Contracts", "Trades", "Staff"]),
    ("Schedule", ["Schedule", "Game", "Playoffs"]),
    ("League", ["Standings", "Stats", "Awards"]),
    ("Draft", ["Draft"]),
    ("Bitter", ["Bitter"]),
]
PAGE_LABELS = {"Game": "Watch a game"}      # page button text when it differs from the tab name


def tab_name(value):
    """The tab's name, whether NiceGUI hands us the name or the tab itself."""
    if isinstance(value, str):
        return value
    props = getattr(value, "props", None) or getattr(value, "_props", None) or {}
    return props.get("name")


def section_of(tab):
    for name, pages in SECTIONS:
        if tab in pages:
            return name
    return SECTIONS[0][0]


def section_buttons(available, current, go):
    """The section buttons in the green bar. `available`: tab names that exist
    right now; `current`: the tab showing; `go(tab)` shows a tab."""
    here = section_of(current)
    last = _last_pages()
    with ui.element("nav").classes("flex flex-wrap").style("gap:2px").props('aria-label="Sections"'):
        for name, pages in SECTIONS:
            pages = [p for p in pages if p in available]
            if not pages:
                continue
            target = last.get(name) if last.get(name) in pages else pages[0]
            ui.element("button").classes("hub-btn" + (" on" if name == here else "")) \
                .on("click", lambda _e, t=target: go(t)) \
                .props(f'type="button"{" aria-current=page" if name == here else ""}') \
                ._text = name
    _last_pages()[here] = current


def page_buttons(available, current, go):
    """The row of page buttons under the bar, for a section with more than one page."""
    here = section_of(current)
    pages = [p for p in dict(SECTIONS)[here] if p in available]
    if len(pages) < 2:
        return
    with ui.element("div").classes("sub-row w-full").props('role="navigation" aria-label="Pages"'):
        for p in pages:
            b = ui.element("button").classes("sub-btn" + (" on" if p == current else "")) \
                .on("click", lambda _e, t=p: go(t)).props('type="button"')
            b._text = PAGE_LABELS.get(p, p)


def _last_pages():
    """The page you last looked at in each section, so a section button takes you back there."""
    from .state import state
    if not hasattr(state, "section_pages"):
        state.section_pages = {}
    return state.section_pages


CSS = f"""
<style>
  .top-band {{
    background-color: {theme.TURF};
    background-image: repeating-linear-gradient(90deg, rgba(255,255,255,0.08) 0 2px, transparent 2px 64px);
    color: white;
  }}
  .top-band.other {{ background-color: #3B4650; }}
  .team-btn {{ display: flex; align-items: center; gap: 10px; background: transparent; color: white;
              border: 1px solid rgba(255,255,255,.28); border-radius: 4px; padding: 2px 10px 2px 8px;
              min-height: 44px; cursor: pointer; font: inherit; text-align: left; }}
  .team-btn:hover {{ background: rgba(255,255,255,.08); }}
  .team-btn .abbr {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 30px; line-height: 1; }}
  .team-btn .tname {{ font-weight: 600; font-size: 16px; line-height: 1.15; white-space: nowrap; }}
  .team-btn .tsub {{ font-size: 12.5px; opacity: .85; line-height: 1.15; white-space: nowrap;
                   max-width: 210px; overflow: hidden; text-overflow: ellipsis; }}
  .view-only {{ background: {theme.FLAG}; color: {theme.INK}; font-weight: 600; font-size: 13px;
               padding: 3px 8px; border-radius: 3px; white-space: nowrap; }}
  .hub-btn {{ background: transparent; border: 0; border-bottom: 3px solid transparent;
             color: rgba(255,255,255,.85); font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
             font-size: 18px; padding: 8px 9px 5px; min-height: 44px; cursor: pointer; }}
  .hub-btn:hover {{ color: white; }}
  .hub-btn.on {{ color: white; border-bottom-color: {theme.FLAG}; }}
  .band-week {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 18px; line-height: 1.2;
               white-space: nowrap; }}
  .band-sub {{ font-size: 12.5px; opacity: .9; line-height: 1.25; max-width: 340px;
              overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .save-chip {{ font-size: 13px; padding: 3px 9px; border-radius: 3px; background: rgba(255,255,255,.14);
               white-space: nowrap; }}
  /* The bar's buttons (Oct 22; Blake: the top-right boxes "look like google form boxes").
     go = the main action (Sim week, Next...), yellow like a penalty flag; alt = dark
     buttons that sit in the bar; flat = text only. */
  .top-band .bar-btn {{ font-family: 'Barlow Condensed', sans-serif; font-size: 17px; font-weight: 700;
     letter-spacing: .02em; border-radius: 4px; min-height: 40px; padding: 0 14px; }}
  .top-band .bar-btn .q-icon {{ font-size: 20px; margin-right: 6px; }}
  .top-band .bar-btn.go {{ background: {theme.FLAG}; color: {theme.INK};
     box-shadow: 0 2px 0 #B8900A, 0 3px 8px rgba(0,0,0,.25); }}
  .top-band .bar-btn.go:hover {{ background: #FFD43B; }}
  .top-band .bar-btn.alt {{ background: rgba(0,0,0,.22); color: white; box-shadow: inset 0 0 0 1px rgba(255,255,255,.22); }}
  .top-band .bar-btn.alt:hover {{ background: rgba(0,0,0,.34); }}
  .top-band .bar-btn.flat {{ background: transparent; color: white; opacity: .9; padding: 0 8px; }}
  .top-band .bar-btn.flat:hover {{ opacity: 1; background: rgba(255,255,255,.08); }}
  .top-band .bar-btn.save {{ background: transparent; color: {theme.FLAG}; box-shadow: inset 0 0 0 2px {theme.FLAG}; }}
  .top-band .bar-btn.save:hover {{ background: rgba(245,197,24,.15); }}
  .top-band .q-btn-dropdown.bar-btn .q-btn-dropdown__arrow {{ margin-left: 4px; }}
  .bar-saved {{ display: inline-flex; align-items: center; gap: 4px; font-size: 13px; opacity: .75;
     white-space: nowrap; padding: 0 4px; }}
  .bar-saved .material-icons {{ font-size: 16px; color: #8FD19E; }}
  .sub-row {{ display: flex; flex-wrap: wrap; gap: 2px; padding: 0 16px; background: #E9EEE6;
             border-bottom: 1px solid {theme.LINE}; }}
  .sub-btn {{ background: transparent; border: 0; border-bottom: 3px solid transparent;
             font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 17px; color: #4F5A63;
             padding: 6px 12px 3px; min-height: 42px; cursor: pointer; }}
  .sub-btn:hover {{ color: {theme.INK}; }}
  .sub-btn.on {{ color: {theme.TURF}; border-bottom-color: {theme.TURF}; }}
</style>
"""
