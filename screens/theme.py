# theme.py
# The game's look: colors, fonts and shared styles. Every screen uses these,
# so changing a color here changes it everywhere.

# ---- Colors --------------------------------------------------------------
TURF = "#1F4A35"      # deep field green: header band
TURF_DARK = "#163626"
CHALK = "#ECEFEA"     # page background (a shade darker Oct 22, so panels stand out like windows)
PAPER = "#FFFFFF"     # tables and panels
INK = "#18222B"       # main text
INK_SOFT = "#5B6670"  # secondary text
LINE = "#D9DED8"      # table rules and borders
FLAG = "#F5C518"      # penalty-flag yellow: selection and focus

# One color per rating word. Elite is blue ("blue chip"), then green, light
# green, yellow, orange and browns, so neighboring tiers are easy to tell apart.
RATING_COLORS = {
    "Elite":     "#2563B8",
    "Very Good": "#2E8B47",
    "Good":      "#93B83E",
    "Average":   "#E3C13B",
    "Bad":       "#E07B24",
    "Very Bad":  "#8B5A2B",
    "Atrocious": "#5A3A1F",
}

# Position groups, used for filters and the colored position tags.
UNITS = {
    "Offense": ["QB", "RB", "FB", "TE", "WR", "T", "G", "C"],
    "Defense": ["DE", "DT", "OLB", "ILB", "CB", "S"],
    "Special teams": ["K", "P", "LS"],
}
UNIT_COLORS = {"Offense": "#2F6690", "Defense": "#9B2C2C", "Special teams": "#6B5B95"}

# One color per position, grouped by family so related positions look
# related: warm reds/oranges for the backfield, purples for receivers,
# blues for the offensive line, navies for the defensive line, greens for
# linebackers, golds for the secondary, browns for specialists.
POSITION_COLORS = {
    "QB":  "#D9822B",
    "RB":  "#C2423C",
    "FB":  "#9A4652",
    "TE":  "#A2639E",
    "WR":  "#6A4C9C",
    "C":   "#2C7DA0",
    "G":   "#4A9CC9",
    "T":   "#6B8FB3",
    "DE":  "#2E3B73",
    "DT":  "#4A5A96",
    "OLB": "#5C8A36",
    "ILB": "#3C6E3C",
    "CB":  "#F5D76E",
    "S":   "#C9952B",
    "K":   "#7C6F66",
    "P":   "#9A8E85",
    "LS":  "#8A8580",
    "RET": "#8B6B4F",    # kick and punt returners on the depth chart
}


def _luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _text_on(hex_color):
    """White or dark text, whichever is easier to read on this color."""
    bg = _luminance(hex_color)
    white = 1.05 / (bg + 0.05)
    dark = (bg + 0.05) / (_luminance("#18222B") + 0.05)
    return "#FFFFFF" if white >= dark else "#18222B"


def position_style(position):
    """CSS for a position tag: its color and readable text."""
    color = POSITION_COLORS.get(position, "#6B6B6B")
    return f"background:{color};color:{_text_on(color)}"


def unit_of(position):
    for unit, positions in UNITS.items():
        if position in positions:
            return unit
    return "Offense"


HEAD_HTML = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --turf: {TURF}; --turf-dark: {TURF_DARK}; --chalk: {CHALK}; --paper: {PAPER};
    --ink: {INK}; --ink-soft: {INK_SOFT}; --line: {LINE}; --flag: {FLAG};
  }}
  body {{
    background: var(--chalk); color: var(--ink);
    font-family: 'Barlow', 'Segoe UI', sans-serif; font-size: 15px;
  }}
  .nicegui-content {{ padding: 0 !important; gap: 0 !important; }}
  .condensed {{ font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; }}
  .num {{ font-variant-numeric: tabular-nums; }}

  /* Header band with yard lines: thin chalk stripes every 5 "yards" */
  .field-band {{
    background-color: var(--turf);
    background-image: repeating-linear-gradient(90deg,
        rgba(255,255,255,0.10) 0 2px, transparent 2px 64px);
    color: white;
  }}
  .team-abbrev {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 72px; line-height: 0.9; letter-spacing: 0.01em;
  }}
  .team-name {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 30px; }}

  /* Tables */
  .roster-table {{ background: var(--paper); border: 1px solid var(--line); border-radius: 4px; }}
  .roster-table thead th {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 15px;
    color: var(--ink-soft); background: var(--paper);
  }}
  .roster-table tbody td {{ font-size: 14.5px; }}
  .roster-table tbody tr {{ cursor: pointer; }}
  .roster-table tbody tr.is-selected td {{ background: #FFF6CF; }}
  .roster-table tbody tr.is-selected td:first-child {{ box-shadow: inset 4px 0 0 var(--flag); }}

  .pos-tag {{
    display: inline-block; min-width: 36px; text-align: center; padding: 1px 6px;
    border-radius: 3px; font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600; font-size: 14px;
  }}
  .starter-dot {{ color: #2E8B57; font-size: 13px; }}
  .captain-star {{ color: #C9A227; font-size: 16px; }}
  .key {{ display: inline-flex; gap: 6px; align-items: center; padding: 3px 10px;
         border: 1px solid var(--line); border-radius: 3px; background: var(--paper);
         font-size: 13.5px; color: var(--ink-soft); }}
  .key .captain-star {{ margin-left: 10px; }}
  .size-note {{ font-size: 12px; color: var(--ink-soft); font-style: italic; }}
  .fit-note {{ font-size: 12.5px; color: #A0611B; margin-left: 44px; }}
  .formation {{ width: 100%; max-width: 900px; display: block; }}
  .formation .f-slot {{ fill: white; font: 600 12px 'Barlow Condensed', sans-serif; }}
  .formation .f-name {{ fill: white; font: 500 13px 'Barlow', sans-serif; }}
  .formation .f-rating {{ fill: white; font: 600 12px 'Barlow', sans-serif; }}
  .formation .f-note {{ fill: white; fill-opacity: 0.75; font: 500 13px 'Barlow', sans-serif; }}

  .rating {{ display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }}
  .rating .swatch {{ width: 10px; height: 10px; border-radius: 2px; flex: none;
                    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.12); }}

  /* Player report panel */
  .report {{ background: var(--paper); border: 1px solid var(--line); border-radius: 4px; }}
  .report h2 {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 34px;
               line-height: 1; margin: 0; }}
  .report h3 {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 19px;
               margin: 18px 0 6px; color: var(--turf); border-bottom: 1px solid var(--line);
               padding-bottom: 3px; }}
  .facts {{ display: grid; grid-template-columns: max-content 1fr; gap: 3px 16px; }}
  .facts .k {{ color: var(--ink-soft); }}
  .skill-row {{ display: grid; grid-template-columns: 138px 1fr 152px; align-items: center;
               gap: 10px; padding: 2px 0; }}
  .skill-row > span:last-child {{ white-space: nowrap; }}
  .skill-bar {{ position: relative; height: 10px; background: #EEF1EC; border-radius: 2px; }}
  .skill-bar .pot {{ position: absolute; inset: 0 auto 0 0; background: #D7E3D3; border-radius: 2px; }}
  .skill-bar .cur {{ position: absolute; inset: 0 auto 0 0; border-radius: 2px; }}
  .legend {{ color: var(--ink-soft); font-size: 13px; }}

  .your-team-badge {{ background: var(--flag); color: var(--ink); font-weight: 600; font-size: 13px;
                     padding: 2px 8px; border-radius: 3px; }}
  .choose-team {{ background: #FFF6CF; border-bottom: 1px solid #E8D88A; }}

  /* Tabs */
  .main-tabs {{ border-bottom: 1px solid var(--line); background: var(--chalk); }}
  .main-tabs .q-tab__label {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 18px; }}

  /* Depth chart */
  .depth-unit {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 20px;
                color: var(--turf); margin: 14px 0 2px; }}
  .depth-row {{ display: grid; grid-template-columns: 52px 150px repeat(4, minmax(0, 1fr));
               gap: 10px; align-items: center; padding: 5px 10px; background: var(--paper);
               border-bottom: 1px solid var(--line); cursor: pointer; font-size: 14px; }}
  .depth-row > span {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .depth-row:hover {{ background: #F7FAF5; }}
  .depth-row.is-selected {{ background: #FFF6CF; box-shadow: inset 4px 0 0 var(--flag); }}
  .depth-head {{ cursor: default; background: transparent; color: var(--ink-soft);
                font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 15px; }}
  .depth-head:hover {{ background: transparent; }}
  .depth-warning {{ background: #FCEBD9; border-left: 4px solid #D08A2E; padding: 6px 10px;
                   margin-bottom: 6px; font-size: 14px; }}
  .lineup {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }}
  .lineup-spot {{ background: var(--paper); border: 1px solid var(--line); border-radius: 3px;
                 padding: 3px 8px; font-size: 13.5px; display: inline-flex; gap: 6px; align-items: center; }}
  .lineup-spot b {{ font-family: 'Barlow Condensed', sans-serif; color: var(--ink-soft); }}
  .panel-heading {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 19px;
                   color: var(--turf); margin-top: 18px; border-bottom: 1px solid var(--line);
                   padding-bottom: 3px; width: 100%; }}
  .edit-row {{ padding: 3px 0; border-bottom: 1px solid #EEF1EC; }}

  /* Position counts */
  .counts-table {{ width: 100%; border-collapse: collapse; background: var(--paper);
                  border: 1px solid var(--line); font-size: 15px; }}
  .counts-table th {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 16px;
                     color: var(--ink-soft); text-align: right; padding: 6px 14px;
                     border-bottom: 2px solid var(--line); }}
  .counts-table th:first-child, .counts-table td:first-child {{ text-align: left; }}
  .counts-table td {{ padding: 4px 14px; border-bottom: 1px solid #EEF1EC; text-align: right; }}
  .counts-table tr.count-group td {{ font-weight: 600; background: #F4F6F3; }}
  .counts-table tr.count-short td {{ color: #A3321F; }}
  .count-flag {{ font-size: 12px; font-weight: 600; background: #FCE3DD; color: #A3321F;
                padding: 1px 6px; border-radius: 3px; margin-left: 6px; }}
  .count-swatch {{ display: inline-block; width: 11px; height: 11px; border-radius: 2px;
                  margin-right: 8px; vertical-align: -1px; }}
  .counts-help p {{ margin: 0 0 10px; line-height: 1.45; }}

  /* Game screen */
  .scoreboard {{ display: grid; grid-template-columns: 1fr 300px 1fr; background: var(--turf-dark);
                color: white; border-radius: 4px; overflow: hidden; }}
  .sb-team {{ display: grid; grid-template-columns: 22px auto 1fr auto; grid-template-rows: auto auto;
             column-gap: 12px; align-items: center; padding: 10px 18px; }}
  .sb-abbrev {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 40px; line-height: 1; }}
  .sb-name {{ font-size: 14px; opacity: 0.8; }}
  .sb-score {{ grid-row: 1 / span 2; grid-column: 4; font-family: 'Barlow Condensed', sans-serif;
              font-weight: 700; font-size: 56px; line-height: 1; }}
  .sb-to {{ grid-column: 2 / span 2; display: flex; gap: 5px; }}
  .to-dot {{ width: 22px; height: 5px; background: var(--flag); border-radius: 2px; }}
  .to-dot.used {{ background: rgba(255,255,255,0.18); }}
  .poss-ball {{ grid-row: 1 / span 2; width: 16px; height: 10px; border-radius: 50%; background: #B9773A;
               box-shadow: 0 0 0 2px white; }}
  .poss-ball.off {{ visibility: hidden; }}
  .sb-mid {{ text-align: center; padding: 8px 6px; background: rgba(0,0,0,0.25); }}
  .sb-period {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 18px; opacity: 0.85; }}
  .sb-clock {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 38px; line-height: 1.05; }}
  .sb-situation {{ font-size: 15px; font-weight: 600; color: var(--flag); min-height: 20px; }}
  .sb-weather {{ font-size: 12px; opacity: 0.7; }}
  .field-strip {{ width: 100%; height: auto; display: block; border-radius: 3px; }}
  .field-strip .f-num {{ fill: white; fill-opacity: 0.8; font: 600 15px 'Barlow Condensed', sans-serif; text-anchor: middle; }}
  .field-strip .f-ez {{ fill: white; fill-opacity: 0.75; font: 700 30px 'Barlow Condensed', sans-serif; text-anchor: middle; }}
  .field-strip .f-arrow {{ fill: white; font-size: 20px; text-anchor: middle; }}
  .pbp-scroll {{ height: 560px; overflow-y: auto; width: 100%; background: var(--paper);
                border: 1px solid var(--line); border-radius: 4px; }}
  .pbp-row {{ display: grid; grid-template-columns: 74px 44px 168px 1fr; gap: 8px; padding: 5px 10px;
             border-bottom: 1px solid #EEF1EC; font-size: 14px; align-items: start; }}
  .pbp-clock {{ color: var(--ink-soft); font-size: 13px; }}
  .pbp-team {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; }}
  .pbp-dd {{ color: var(--ink-soft); font-size: 13px; }}
  .pbp-detail {{ color: var(--ink-soft); font-size: 12.5px; margin-top: 2px; }}
  .pbp-scoreline {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 15px;
                   color: var(--turf); margin-top: 2px; }}
  .pbp-score {{ background: #EEF7EA; box-shadow: inset 4px 0 0 #2E8B47; }}
  .pbp-score .pbp-text {{ font-weight: 600; }}
  .pbp-turnover {{ background: #FCEDEA; box-shadow: inset 4px 0 0 #B23A2A; }}
  .pbp-big {{ box-shadow: inset 4px 0 0 var(--flag); }}
  .pbp-drive {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 16px;
               background: #F4F6F3; padding: 6px 10px; border-bottom: 1px solid var(--line);
               border-top: 2px solid var(--line); color: var(--turf); }}
  .pbp-note {{ text-align: center; color: var(--ink-soft); font-size: 13px; padding: 4px; border-bottom: 1px solid #EEF1EC; }}
  .pbp-injury {{ color: #A3321F; }}
  .pbp-quarter {{ text-align: center; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
                 font-size: 16px; padding: 6px; background: var(--turf); color: white; }}
  .pbp-final {{ font-size: 20px; }}
  .box-panels {{ background: var(--paper) !important; border: 1px solid var(--line); border-radius: 4px;
                padding: 6px 12px 12px; max-height: 620px; overflow-y: auto; }}
  .box-team {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 22px; color: var(--turf); margin-top: 4px; }}
  .box-title {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 17px;
               color: var(--ink-soft); margin: 10px 0 2px; }}
  .box-table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
  .box-table th {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 14px; color: var(--ink-soft);
                  text-align: right; padding: 3px 6px; border-bottom: 1px solid var(--line); }}
  .box-table td {{ text-align: right; padding: 2px 6px; border-bottom: 1px solid #F0F2EE; white-space: nowrap; }}
  .box-table th.l, .box-table td.l {{ text-align: left; white-space: normal; }}
  .plink {{ color: inherit; text-decoration: none; }}
  .plink:hover {{ color: var(--turf); text-decoration: underline; }}
  .team-stats td:first-child {{ white-space: pre; color: var(--ink-soft); text-align: left; }}
  .line-score td:first-child {{ text-align: left; }}
  .line-score {{ margin: 8px 0 10px; font-size: 15px; }}

  /* Main menu, New game, Load game, Settings */
  .menu-title {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 64px;
                line-height: 0.95; }}
  .menu-sub {{ font-size: 16px; opacity: 0.85; }}
  .menu-panel {{ background: var(--paper); border: 1px solid var(--line); border-radius: 4px; }}
  .menu-button {{ width: 100%; justify-content: flex-start; }}
  .menu-button .q-btn__content {{ justify-content: flex-start; text-align: left; }}
  .menu-heading {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 28px;
                  color: var(--turf); line-height: 1.1; }}
  .field-label {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 17px;
                 color: var(--ink); margin-top: 14px; }}
  .step-chip {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 15px;
               padding: 2px 10px; border-radius: 3px; background: rgba(255,255,255,0.15); }}
  .step-chip.on {{ background: var(--flag); color: var(--ink); }}
  .coming-later {{ color: var(--ink-soft); font-size: 14px; padding: 3px 0 3px 34px; }}
  .coming-later b {{ font-weight: 600; }}
  .save-row {{ display: grid; grid-template-columns: 78px 1fr auto; gap: 16px; align-items: center; width: 100%;
              padding: 12px 16px; border-bottom: 1px solid var(--line); background: var(--paper); }}
  .save-row:last-child {{ border-bottom: none; }}
  .save-abbrev {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 36px;
                 color: var(--turf); line-height: 1; text-align: center; }}
  .save-name {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 22px; line-height: 1.1; }}
  .notice {{ background: #FFF6CF; border: 1px solid #E8D88A; border-left: 4px solid var(--flag);
            padding: 10px 14px; border-radius: 3px; }}
  .problem {{ color: #A3321F; font-size: 14px; }}
  .save-status {{ font-size: 13.5px; padding: 3px 10px; border-radius: 3px; white-space: nowrap; }}
  .save-status.clean {{ background: rgba(255,255,255,0.12); }}
  .save-status.unsaved {{ background: var(--flag); color: var(--ink); font-weight: 600; }}

  /* Season: bar, schedule, standings, injuries */
  .inj-tag {{ display: inline-block; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
             font-size: 12px; line-height: 1.3; padding: 0 5px; border-radius: 3px; margin-left: 4px;
             background: #B23A2A; color: white; vertical-align: 1px; }}
  .inj-tag.inj-q {{ background: #E8B020; color: #2A2A2A; }}
  .inj-tag.inj-d {{ background: #E07A1F; }}
  .inj-tag.inj-ir {{ background: #6E1B12; }}
  .inj-tag.inj-conc {{ background: #5B3F8C; }}
  .inj-tag.inj-pup {{ background: #4A4A4A; }}
  /* Training camp: your staff's cut list and your keep marks */
  .cut-tag {{ display: inline-block; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
             font-size: 12px; line-height: 1.3; padding: 0 5px; border-radius: 3px; margin-left: 4px;
             border: 1px solid #8A8A8A; color: #5A5A5A; vertical-align: 1px; }}
  .cut-tag.keep {{ border-color: #2E7D32; color: #2E7D32; }}
  /* Roster moves */
  .move-list {{ font-size: 14px; }}
  .move-list td {{ padding: 2px 8px 2px 0; vertical-align: top; }}
  .move-actions {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 10px; }}
  /* Injury history: hover "View record" for a box that closes when the mouse leaves */
  .inj-hist-row {{ position: relative; }}
  .inj-hist {{ display: inline-block; }}
  .inj-hist-link {{ color: #B23A2A; font-weight: 600; cursor: default; text-decoration: underline dotted; }}
  .inj-hist-box {{ display: none; position: absolute; z-index: 60; left: 0; right: 0; top: 100%; margin-top: 2px;
                  min-width: 380px; max-height: 340px; overflow-y: auto; background: white;
                  border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 6px 20px rgba(0,0,0,.18);
                  padding: 6px 8px; text-align: left; font-weight: 400; }}
  .inj-hist:hover .inj-hist-box {{ display: block; }}
  .inj-hist-now {{ display: block; margin-top: 6px; color: var(--ink-soft); font-size: 13px; }}
  .season-bar {{ background: #E9EEE6; border-bottom: 1px solid var(--line); }}
  .season-week {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 22px; color: var(--turf); }}
  .season-matchup {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 19px; }}
  .sched-row {{ display: grid; grid-template-columns: 1fr 70px 1fr 150px; gap: 10px; align-items: center;
               padding: 7px 12px; background: var(--paper); border-bottom: 1px solid var(--line);
               cursor: pointer; font-size: 14.5px; }}
  .sched-row:hover {{ background: #F7FAF5; }}
  .sched-row.is-selected {{ background: #FFF6CF; box-shadow: inset 4px 0 0 var(--flag); }}
  .sched-row.mine {{ font-weight: 600; }}
  .sched-row .win {{ font-weight: 700; }}
  .sched-row .score {{ text-align: center; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
                      font-size: 18px; }}
  .team-sched {{ display: grid; grid-template-columns: 60px 110px 1fr 150px 70px; gap: 10px; align-items: center;
                padding: 7px 12px; background: var(--paper); border-bottom: 1px solid var(--line); font-size: 14.5px; }}
  .team-sched.played {{ cursor: pointer; }}
  .team-sched.played:hover {{ background: #F7FAF5; }}
  .team-sched.is-selected {{ background: #FFF6CF; box-shadow: inset 4px 0 0 var(--flag); }}
  .team-sched.bye {{ color: var(--ink-soft); font-style: italic; }}
  .team-sched.current {{ box-shadow: inset 4px 0 0 var(--turf); }}
  .res-w {{ color: #2E8B47; font-weight: 700; }}
  .res-l {{ color: #A3321F; font-weight: 700; }}
  .res-t {{ color: var(--ink-soft); font-weight: 700; }}
  .standings {{ width: 100%; border-collapse: collapse; background: var(--paper); border: 1px solid var(--line);
               font-size: 14.5px; font-variant-numeric: tabular-nums; margin-bottom: 14px; }}
  .standings th {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 15px; color: var(--ink-soft);
                  text-align: right; padding: 5px 10px; border-bottom: 2px solid var(--line); }}
  .standings td {{ text-align: right; padding: 4px 10px; border-bottom: 1px solid #EEF1EC; }}
  .standings th:first-child, .standings td:first-child {{ text-align: left; }}
  .standings tr.mine td {{ background: #FFF6CF; font-weight: 600; }}
  .standings caption {{ text-align: left; font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
                       font-size: 19px; color: var(--turf); padding: 2px 0 4px; }}

  :focus-visible {{ outline: 3px solid var(--flag) !important; outline-offset: 1px; }}
</style>
"""


# ---- Desktop feel (Oct 22; Blake: "still feels a little clunky and too much like
# a google form"). Applied on top of everything above: pages switch instantly,
# pop-ups open fast, no web-style ripples, button groups look like one control,
# tables have shaded headers, striped and highlighted rows, panels sit like
# windows with a green top edge. "body " in front wins over each page's own
# styles. To undo any of it, delete its lines here.
DESKTOP_CSS = f"""
<style>
  /* Instant page switches; quick pop-ups (a desktop program doesn't slide) */
  body [class*="q-transition--slide"], body [class*="q-transition--jump"] {{
    transition: none !important; animation: none !important; }}
  body .q-dialog__inner[class*="q-transition--"], body .q-dialog__backdrop[class*="q-transition--"] {{
    transition-duration: .09s !important; }}
  body .q-ripple {{ display: none !important; }}

  /* Buttons: squarer, firmer */
  body .q-btn {{ border-radius: 3px; font-weight: 600; letter-spacing: 0; }}
  body .q-btn--outline:before {{ border-width: 1px; }}

  /* Button groups (Roster / Practice squad / ...) look like one segmented control */
  body .q-btn-toggle {{ border: 1px solid #C7D0C4; border-radius: 3px; overflow: hidden; box-shadow: none; }}
  body .q-btn-toggle .q-btn {{ border-radius: 0; min-height: 34px; padding: 0 14px; font-weight: 500; }}
  body .q-btn-toggle .q-btn.bg-white {{ background: #F3F6F1 !important; color: #3C4852 !important; }}
  body .q-btn-toggle .q-btn.bg-white:hover {{ background: #E4EBE1 !important; }}
  body .q-btn-toggle .q-btn + .q-btn {{ border-left: 1px solid #C7D0C4; }}
  body .q-btn-toggle .q-btn:not(.bg-white) {{ font-weight: 600; }}

  /* Drop-downs and text boxes: compact and square, not form fields */
  body .q-field--outlined .q-field__control {{ border-radius: 3px; background: #FFFFFF; }}
  body .q-field--outlined .q-field__control:before {{ border-color: #C7D0C4; }}
  body .q-field--outlined.q-field--dense .q-field__control {{ min-height: 36px; }}
  body .q-field--dense .q-field__native, body .q-field--dense .q-field__input {{ min-height: 34px; padding: 0; }}
  body .q-field--dense .q-field__marginal {{ height: 36px; }}
  body .q-menu {{ border-radius: 3px; box-shadow: 0 6px 18px rgba(0,0,0,.18); }}
  body .q-menu .q-item {{ min-height: 30px; padding: 4px 12px; }}

  /* Panels sit like windows: green top edge, squarer corners, a faint shadow */
  body .report, body .hcard, body .roster-table, body .box-panels {{
    border-radius: 3px; border-top: 3px solid var(--turf); box-shadow: 0 1px 3px rgba(20, 40, 30, .08); }}
  body .menu-panel {{ border-radius: 3px; box-shadow: 0 1px 3px rgba(20, 40, 30, .08); }}

  /* Tables: shaded header, striped rows, row highlight under the mouse */
  /* Header rows in the accent green, like the draft board (Blake liked its look, Oct 22) */
  body .roster-table thead th {{ background: var(--turf); color: white; border-bottom: 0; letter-spacing: .02em; }}
  body .roster-table thead th .q-table__sort-icon {{ color: var(--flag); }}
  body .roster-table thead tr th {{ position: sticky; top: 0; z-index: 2; }}
  body .roster-table tbody tr:nth-child(even) td {{ background: #F7F9F6; }}
  body .roster-table tbody tr:hover td {{ background: #EAF2E6; }}
  body .roster-table tbody tr.is-selected td {{ background: #FFF6CF; }}
  body .box-table th {{ background: #EEF2EC; color: #2F3B34; }}
  body .box-table tbody tr:hover td {{ background: #F1F6EE; }}
  body .standings {{ border-radius: 3px; border-top: 3px solid var(--turf); box-shadow: 0 1px 3px rgba(20, 40, 30, .08); }}
  body .standings th {{ background: var(--turf); color: white; border-bottom: 0; }}
  body .standings tbody tr:nth-child(even) td {{ background: #F7F9F6; }}
  body .standings tbody tr:hover td {{ background: #EAF2E6; }}
  body .standings tr.mine td {{ background: #FFF6CF; }}
  body .standings caption {{ padding: 2px 0 6px; }}
  body .sched-row:hover, body .team-sched.played:hover {{ background: #EAF2E6; }}
  body .sched-row.is-selected, body .team-sched.is-selected {{ background: #FFF6CF; }}

  /* Links to players and teams: plain text until you point at them */
  body .pname {{ color: inherit; font-weight: 600; text-decoration: none; }}
  body .pname:hover {{ color: var(--turf); text-decoration: underline; }}

  /* Thin desktop scrollbars */
  ::-webkit-scrollbar {{ width: 11px; height: 11px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: #BAC4B6; border-radius: 6px; border: 3px solid transparent;
                               background-clip: content-box; }}
  ::-webkit-scrollbar-thumb:hover {{ background: #8E9B89; border: 3px solid transparent; background-clip: content-box; }}
</style>
"""
HEAD_HTML += DESKTOP_CSS
