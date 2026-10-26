# theme.py
# The game's look: colors, fonts and shared styles. Every screen uses these,
# so changing a color here changes it everywhere.

# ---- Colors --------------------------------------------------------------
TURF = "#1F4A35"      # deep field green: header band
TURF_DARK = "#163626"
CHALK = "#E4E8EE"     # page background: broadcast slate (Gemini's Step 1, Oct 24; was #ECEFEA)
PAPER = "#FFFFFF"     # tables and panels
INK = "#18222B"       # main text
INK_SOFT = "#5B6670"  # secondary text
LINE = "#CFD6DF"      # table rules and borders (Gemini's Step 1, Oct 24; was #D9DED8)
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
    --team-accent: {FLAG}; --team-accent-ink: {INK}; --team-link: {FLAG};
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
# Oct 24: replaced with Gemini's "front-office polish" version (Blake designs the look with
# Gemini): bevelled buttons, tighter tables with green uppercase headers and column lines,
# bold starters on the depth chart, aligned numbers, squarer fields and menus.
DESKTOP_CSS = f"""
<style>
  /* Instant page switches; quick pop-ups (a desktop program doesn't slide) */
  body [class*="q-transition--slide"], body [class*="q-transition--jump"] {{
    transition: none !important; animation: none !important; }}
  body .q-dialog__inner[class*="q-transition--"], body .q-dialog__backdrop[class*="q-transition--"] {{
    transition-duration: .08s !important; }}
  body .q-ripple {{ display: none !important; }}

  /* Global numeric alignment for sports stats & salaries */
  body table, body .q-table, body .depth-row, body .sched-row, body .team-sched {{
    font-variant-numeric: tabular-nums;
  }}

  /* Buttons: tactile desktop bevel, squarer corners, firmer typography */
  body .q-btn {{
    border-radius: 3px; font-weight: 600; letter-spacing: 0.01em;
    box-shadow: 0 1px 0 rgba(0,0,0,0.12);
  }}
  body .q-btn--flat, body .q-btn--unelevated {{ box-shadow: none; }}
  body .q-btn--outline:before {{ border-width: 1px; }}

  /* Segmented button groups (Roster / Practice squad / ...) */
  body .q-btn-toggle {{
    border: 1px solid #B8C3B5; border-radius: 3px; overflow: hidden;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.06); background: #EAEEE8;
  }}
  body .q-btn-toggle .q-btn {{
    border-radius: 0; min-height: 31px; padding: 0 12px; font-weight: 600;
    font-size: 13.5px; box-shadow: none;
  }}
  body .q-btn-toggle .q-btn.bg-white {{
    background: #F4F7F2 !important; color: #3A4650 !important; font-weight: 500;
  }}
  body .q-btn-toggle .q-btn.bg-white:hover {{ background: #E5ECE2 !important; color: var(--ink) !important; }}
  body .q-btn-toggle .q-btn + .q-btn {{ border-left: 1px solid #C2CCC0; }}

  /* Drop-downs and text boxes: compact desktop toolbar height */
  body .q-field--outlined .q-field__control {{
    border-radius: 3px; background: #FFFFFF; box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  }}
  body .q-field--outlined .q-field__control:before {{ border-color: #B8C3B5; }}
  body .q-field--outlined.q-field--dense .q-field__control {{ min-height: 32px; }}
  body .q-field--dense .q-field__native, body .q-field--dense .q-field__input {{
    min-height: 30px; padding: 0; font-size: 13.5px; font-weight: 500;
  }}
  body .q-field--dense .q-field__marginal {{ height: 32px; }}
  body .q-menu {{ border-radius: 3px; border: 1px solid #B8C3B5; box-shadow: 0 8px 24px rgba(15,30,20,.22); }}
  body .q-menu .q-item {{ min-height: 28px; padding: 4px 12px; font-size: 14px; }}

  /* Cards & Side Panels: crisp ledger borders with turf accent bar */
  body .report, body .hcard, body .box-panels {{
    border-radius: 3px; border: 1px solid #C8D0C5;
    border-top: 3px solid var(--turf);
    box-shadow: 0 1px 3px rgba(20, 35, 25, .07);
  }}
  body .menu-panel {{
    border-radius: 3px; border: 1px solid #C8D0C5;
    box-shadow: 0 2px 6px rgba(20, 35, 25, .08);
  }}

  /* Data Tables (Roster, Contracts, Trades, Staff, Stats):
     Tighter padding so 11-column tables never clip on the right edge */
  body .roster-table {{
    border-radius: 3px; border: 1px solid #C2CBC0;
    border-top: none; box-shadow: 0 1px 3px rgba(20, 35, 25, .06);
  }}
  body .roster-table .q-table__middle {{ overflow-x: auto; }}
  body .roster-table thead th {{
    background: var(--turf); color: #FFFFFF; border-bottom: 2px solid var(--turf-dark);
    border-right: 1px solid rgba(255,255,255,0.10);
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600;
    font-size: 14px; text-transform: uppercase; letter-spacing: .035em;
    padding: 5px 8px !important; height: 30px !important;
    position: sticky; top: 0; z-index: 2;
  }}
  body .roster-table thead th:last-child {{ border-right: none; }}
  body .roster-table thead th .q-table__sort-icon {{ color: var(--flag); }}
  body .roster-table thead th.sorted .q-table__sort-icon {{ opacity: 0.9; }}   /* (Claude: only the sorted column's arrow shows) */
  body .roster-table tbody td {{
    padding: 4px 8px !important; height: 29px !important;
    font-size: 14px; border-bottom: 1px solid #E6EAE4;
    border-right: 1px solid #F0F3EE;
  }}
  body .roster-table tbody td:last-child {{ border-right: none; }}
  /* (Claude: the scrolling spacer rows must stay zero height, or a blank strip shows under the header) */
  body .roster-table tbody.q-virtual-scroll__padding td {{ height: auto !important; padding: 0 !important; border: 0 !important; }}
  body .roster-table tbody tr:nth-child(even) td {{ background: #F7F9F6; }}
  body .roster-table tbody tr:hover td {{ background: #E6F0E2 !important; }}
  body .roster-table tbody tr.is-selected td {{
    background: #FFF4BF !important; font-weight: 500;
  }}

  /* Standings & Box Tables */
  body .standings {{
    border-radius: 3px; border: 1px solid #C2CBC0; border-top: none;
    box-shadow: 0 1px 3px rgba(20, 35, 25, .06);
  }}
  body .standings th {{
    background: var(--turf); color: white; border-bottom: 2px solid var(--turf-dark);
    font-size: 13.5px; text-transform: uppercase; letter-spacing: .03em; padding: 4px 8px;
  }}
  body .standings td {{ padding: 4px 8px; font-size: 14px; }}
  body .standings tbody tr:nth-child(even) td {{ background: #F7F9F6; }}
  body .standings tbody tr:hover td {{ background: #E6F0E2; }}
  body .standings tr.mine td {{ background: #FFF4BF; font-weight: 600; }}
  body .standings caption {{ padding: 2px 0 5px; font-size: 18px; letter-spacing: .01em; }}

  body .box-table th {{
    background: #E4EAE2; color: #243029; text-transform: uppercase;
    font-size: 12.5px; letter-spacing: .03em; padding: 4px 6px;
  }}
  body .box-table tbody tr:nth-child(even) td {{ background: #F9FAF8; }}
  body .box-table tbody tr:hover td {{ background: #EBF2E8; }}

  /* Depth Chart Grid: Give Starters visual priority over 2nd-4th string */
  body .depth-head {{
    background: var(--turf) !important; color: white !important;
    padding: 5px 10px; border-radius: 3px 3px 0 0;
    text-transform: uppercase; letter-spacing: .03em; font-size: 13.5px;
  }}
  body .depth-row {{
    padding: 4px 10px; font-size: 13.5px; border-left: 1px solid #C8D0C5;
    border-right: 1px solid #C8D0C5;
  }}
  body .depth-row:not(.depth-head) > span:nth-child(3) {{
    font-weight: 600; background: rgba(31, 74, 53, 0.045);
    padding: 2px 6px; border-radius: 2px;
  }}
  body .depth-row:hover {{ background: #E6F0E2; }}
  body .depth-row.is-selected {{ background: #FFF4BF; box-shadow: inset 4px 0 0 var(--flag); }}

  /* Schedule rows */
  body .sched-row:hover, body .team-sched.played:hover {{ background: #E6F0E2; }}
  body .sched-row.is-selected, body .team-sched.is-selected {{ background: #FFF4BF; }}

  /* Links to players and teams: crisp hover state */
  body .pname {{ color: inherit; font-weight: 600; text-decoration: none; }}
  body .pname:hover {{ color: var(--turf); text-decoration: underline; }}

  /* Thin desktop scrollbars */
  ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
  ::-webkit-scrollbar-track {{ background: #E4E8E1; }}
  ::-webkit-scrollbar-thumb {{
    background: #A8B4A4; border-radius: 5px; border: 2px solid #E4E8E1;
  }}
  ::-webkit-scrollbar-thumb:hover {{ background: #7D8C78; }}
</style>
"""
HEAD_HTML += DESKTOP_CSS


# ---- Team colors (Gemini's Step 1, Oct 24) -------------------------------
# Each team's (primary, accent). The game screen takes on the colors of the team
# you're looking at: --turf (the bar, table headers, panel edges) becomes the
# primary and --team-accent (the bar's bottom edge, the active section, the
# team badge's edge) the accent. Every primary keeps white text readable on it
# (contrast 4.5:1 or better) and every accent stands out on its primary (3:1+);
# tools: _contrast(). Blake/Gemini gave PIT, TAM, BAL, DAL, DEN; CIN's orange is
# a shade deeper than Gemini's #D44515 and MIA's teal deeper than #006778 so they
# pass those checks. The rest are Claude's picks to fit each nickname.
TEAM_COLORS = {
    "BOS": ("#0B2545", "#C9A227"),   # Harbormen: navy and brass
    "NYK": ("#2B2D42", "#C0C7D0"),   # Knights: gunmetal and armor silver
    "PHI": ("#10403B", "#7FD1B9"),   # Liberty: deep green and statue patina
    "BUF": ("#1E3A5C", "#A9DEF9"),   # Blizzard: storm blue and ice
    "BAL": ("#241773", "#9E7C0C"),   # Clippers
    "WAS": ("#283618", "#DDA15E"),   # Sentinels: olive drab and brass
    "PIT": ("#181C20", "#FFB612"),   # Ironmen
    "CIN": ("#C23D12", "#181C20"),   # Rivermen
    "CLE": ("#2B2B2E", "#F2701E"),   # Forge: charcoal and molten orange
    "DET": ("#21374F", "#A8DADC"),   # Mechanics: steel and chrome
    "CHI": ("#5A0D12", "#E9C46A"),   # Express: maroon and brass
    "IND": ("#14213D", "#FCA311"),   # Speed: navy and racing amber
    "CHA": ("#3D1A6E", "#E8C547"),   # Monarchs: royal purple and gold
    "ATL": ("#7A0E14", "#FF8C1A"),   # Firebirds: deep red and flame
    "MIA": ("#00485A", "#F26522"),   # Barracudas
    "TAM": ("#092C5C", "#4B9CD3"),   # Storm
    "MIN": ("#0F3D3E", "#B8F2E6"),   # Freeze: deep teal and frost
    "KCY": ("#0A2240", "#6CACE4"),   # Blues
    "STL": ("#1E3D2F", "#D9B44A"),   # Archers: forest green and gold
    "NSH": ("#2A1B12", "#E0A458"),   # Outlaws: saddle brown and tan
    "HOU": ("#0D1B2A", "#E2403A"),   # Wildcatters: oil black and derrick red
    "DAL": ("#003594", "#869397"),   # Stampede
    "SAN": ("#4A1C1C", "#F2C14E"),   # Vaqueros: oxblood and sun gold
    "NOR": ("#0B5D3B", "#F4C430"),   # Krewe: Mardi Gras green and gold
    "SEA": ("#0B3C49", "#3FD0C9"),   # Sound: deep water and aqua
    "POR": ("#23331F", "#E07A5F"),   # Lumberjacks: forest and flannel
    "SFO": ("#2F3E46", "#E8743B"),   # Fog: slate and bridge orange
    "DEN": ("#13264B", "#E85A19"),   # Peaks
    "LAS": ("#0E0E2C", "#F5D547"),   # Stars: midnight and star gold
    "SDG": ("#08415C", "#F9C74F"),   # Surf: ocean and sunshine
    "LVG": ("#141414", "#E63946"),   # High Rollers: black and casino red
    "PHX": ("#4A1410", "#F7B32B"),   # Scorpions: rust and desert gold
}
DEFAULT_TEAM_COLORS = (TURF, FLAG)   # the main menu, the free agent pool, unknown teams


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _darken(hex_color, share):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(round(c * (1 - share)) for c in (r, g, b)))


def team_colors(team_abbrev):
    """(primary, accent) for a team's abbreviation; the classic green and flag yellow otherwise."""
    return TEAM_COLORS.get(team_abbrev or "", DEFAULT_TEAM_COLORS)


def team_css_vars(team_abbrev, is_user_team=True):
    """A <style> tag that recolors the game screen for this team (see TEAM_COLORS).
    None or "FA" (the free agent pool) gives the classic green. `is_user_team` is
    passed along as --team-is-user (1/0) for styles that want to tell them apart."""
    primary, accent = team_colors(team_abbrev)
    # --team-link: small link text on the team color (Home's card headers): the accent
    # where it reads well enough for small text (4.5:1), white where it doesn't (CIN, MIA...).
    link = accent if _contrast(accent, primary) >= 4.5 else "#FFFFFF"
    return (f"<style>:root {{ --turf: {primary}; --turf-dark: {_darken(primary, 0.18)}; "
            f"--team-accent: {accent}; --team-accent-ink: {_text_on(accent)}; --team-link: {link}; "
            f"--team-is-user: {1 if is_user_team else 0}; }}</style>")


# ---- Top bar and docked page strip (Gemini's Step 1, Oct 24) --------------
# Gemini's TOPBAR_CSS, fitted to the game's class names: its ".field-band" rules
# are on ".top-band" (".field-band" is the big header on the menu screens and
# would have been squashed to 58 px). Plain string, not an f-string.
TOPBAR_CSS = """
<style>
  body { background: var(--chalk); }

  /* Primary 60px franchise header bar */
  .top-band {
    background-color: var(--turf);
    background-image:
      linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(0,0,0,0.18) 100%),
      repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 64px);
    border-bottom: 3px solid var(--team-accent, var(--flag));
    box-shadow: 0 2px 8px rgba(10, 20, 30, 0.18);
    min-height: 58px;
    padding: 0 14px !important;
    color: #FFFFFF;
  }

  /* Franchise badge button (left of the top bar) */
  .team-picker-btn {
    background: rgba(0, 0, 0, 0.24) !important;
    border: 1px solid rgba(255, 255, 255, 0.16) !important;
    border-left: 4px solid var(--team-accent, var(--flag)) !important;
    border-radius: 4px !important;
    padding: 4px 12px !important;
    transition: background 0.12s ease;
  }
  .team-picker-btn:hover { background: rgba(0, 0, 0, 0.38) !important; }
  .team-picker-btn .tsub { max-width: none !important; }
  .view-only-pill {
    background: var(--team-accent, var(--flag)); color: var(--team-accent-ink, #18222B);
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 13px; letter-spacing: .06em;
    text-transform: uppercase; padding: 3px 10px; border-radius: 999px; white-space: nowrap;
  }

  /* The 6 section tabs inside the top bar */
  .nav-hub-btn {
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    font-size: 16.5px !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
    color: rgba(255, 255, 255, 0.78) !important;
    background: transparent !important;
    border: 0;
    border-radius: 0 !important;
    padding: 0 13px !important;
    min-height: 55px !important;
    border-bottom: 3px solid transparent !important;
    box-shadow: none !important;
    cursor: pointer;
  }
  .nav-hub-btn:hover { color: #FFFFFF !important; background: rgba(255, 255, 255, 0.08) !important; }
  .nav-hub-btn.is-active {
    color: #FFFFFF !important;
    background: rgba(255, 255, 255, 0.12) !important;
    border-bottom: 3px solid var(--team-accent, var(--flag)) !important;
  }

  /* Right side: the week and the Sim buttons */
  .topbar-Sim-cluster {
    background: rgba(0, 0, 0, 0.22);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    padding: 3px 6px 3px 12px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .bar-primary-action {
    background: var(--flag) !important;
    color: #141C24 !important;
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 700 !important;
    font-size: 15.5px !important;
    letter-spacing: 0.02em !important;
    padding: 4px 14px !important;
    border-radius: 3px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.25) !important;
  }
  .bar-primary-action:hover { filter: brightness(1.06); }

  /* Full-width docked page strip (Roster | Depth chart | Contracts | ...) */
  .subnav-strip {
    width: 100%;
    background: #FFFFFF;
    border-bottom: 1px solid #C6CFD9;
    box-shadow: 0 1px 3px rgba(15, 25, 35, 0.05);
    padding: 0 20px !important;
    min-height: 38px;
    display: flex;
    align-items: stretch;
    gap: 4px;
  }
  .subnav-btn {
    font-family: 'Barlow Condensed', sans-serif !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    letter-spacing: 0.02em !important;
    color: #4A5562 !important;
    background: transparent !important;
    border: 0;
    border-radius: 0 !important;
    padding: 0 14px !important;
    min-height: 38px !important;
    border-bottom: 3px solid transparent !important;
    box-shadow: none !important;
    cursor: pointer;
  }
  .subnav-btn:hover { color: var(--turf) !important; background: #F2F5F8 !important; }
  .subnav-btn.is-active {
    color: var(--turf) !important;
    font-weight: 700 !important;
    border-bottom: 3px solid var(--turf) !important;
    background: rgba(0, 0, 0, 0.02) !important;
  }
  .subnav-badge {
    display: inline-block;
    background: #B45309;
    color: #FFFFFF;
    font-family: 'Barlow', sans-serif;
    font-size: 11px;
    font-weight: 700;
    line-height: 1;
    padding: 2px 5px;
    border-radius: 8px;
    margin-left: 5px;
    vertical-align: 1px;
  }
</style>
"""
HEAD_HTML += TOPBAR_CSS


# ---- Step 2: toolbars, the cap ledger, docked inspector panels (Gemini, Oct 25) ----
# Gemini's STEP_2_CSS, added after DESKTOP_CSS (a plain string, so its braces needn't
# be doubled). Changed by Claude, marked below: the side-panel rules apply only to
# panels with the "inspector" class (Gemini's "body .report" would have stretched
# every .report box in the game, ~25 of them, to 460 px), and the panel header's
# negative margins match those panels' padding (px-6 py-5 = 24 px / 20 px).
STEP2_CSS = """
<style>
  /* Unified control toolbar above tables (Roster, Contracts, Trades, Staff) */
  .page-toolbar {
    width: 100%;
    background: #FFFFFF;
    border: 1px solid #C6CFD9;
    border-left: 4px solid var(--turf);
    border-radius: 3px;
    padding: 8px 12px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(15, 25, 35, 0.04);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px 14px;
  }
  .page-toolbar .toolbar-group { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; }

  /* Compact KPI stat pills for roster counts and staff budgets */
  .stat-pill-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .stat-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: #F1F4F8; border: 1px solid #D0D8E2; border-radius: 3px;
    padding: 2px 9px; font-size: 13px; color: var(--ink-soft); font-variant-numeric: tabular-nums;
  }
  .stat-pill b { font-family: 'Barlow Condensed', sans-serif; font-size: 15px; font-weight: 700; color: var(--ink); }
  .stat-pill.is-good { background: #EBF5EC; border-color: #B7DFB9; color: #1E6B34; }
  .stat-pill.is-warn { background: #FFF6CF; border-color: #E6CE6A; color: #7A5C00; }

  /* Contracts: the salary cap ledger */
  .cap-ledger {
    width: 100%; background: #FFFFFF; border: 1px solid #C6CFD9; border-top: 3px solid var(--turf);
    border-radius: 3px; box-shadow: 0 1px 3px rgba(15, 25, 35, 0.06); padding: 10px 14px; margin-bottom: 8px;
  }
  .cap-kpi-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 0;
    border: 1px solid #DCE2EA; border-radius: 3px; background: #F8FAFC; margin-bottom: 8px;
  }
  .cap-kpi { padding: 6px 12px; border-right: 1px solid #DCE2EA; }
  .cap-kpi:last-child { border-right: none; }
  .cap-kpi-label {
    font-family: 'Barlow Condensed', sans-serif; font-size: 12px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-soft);
  }
  .cap-kpi-val {
    font-family: 'Barlow Condensed', sans-serif; font-size: 26px; font-weight: 700; line-height: 1.05;
    color: var(--ink); font-variant-numeric: tabular-nums;
  }
  .cap-kpi-val small { font-size: 14px; font-weight: 600; color: var(--ink-soft); }   /* (Claude: "of $348M") */
  .cap-kpi-val.room-pos { color: #1E7E3E; }
  .cap-kpi-val.room-neg { color: #B23A2A; }
  .cap-kpi-val.dead-val { color: #B85D19; }
  .cap-bar-track {
    width: 100%; height: 12px; background: #E2E8F0; border-radius: 3px; overflow: hidden;
    display: flex; box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
  }

  /* Split view and the docked right-hand inspector panel */
  .split-workspace { display: flex; align-items: flex-start; gap: 12px; width: 100%; }
  .split-main-table { flex: 1 1 0%; min-width: 0; width: 100%; }
  body .report.inspector { min-height: 460px; display: flex; flex-direction: column; }   /* (Claude: scoped) */
  .inspector-header {
    background: var(--turf); color: #FFFFFF;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 15px;
    text-transform: uppercase; letter-spacing: 0.04em;
    padding: 6px 12px;
    margin: -20px -24px 12px -24px;        /* (Claude: matches the panels' px-6 py-5) */
    border-radius: 2px 2px 0 0;
    border-bottom: 2px solid var(--team-accent, var(--flag));
  }
  .inspector-empty {
    flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 36px 20px; color: var(--ink-soft);
    background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 3px; margin-top: 4px;
  }
  .inspector-empty-title {
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 19px; color: var(--ink);
    margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.02em;
  }

  /* (Claude) One-line ledger tables: the Roster's Moves view and the Staff page's coaching moves */
  .ledger-table { width: 100%; border-collapse: collapse; font-size: 14px; background: #FFFFFF; }
  .ledger-table th {
    background: var(--turf); color: #FFFFFF; text-align: left; padding: 5px 10px;
    font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 14px;
    text-transform: uppercase; letter-spacing: .035em; position: sticky; top: 0; z-index: 1;
  }
  .ledger-table td { padding: 4px 10px; border-bottom: 1px solid #E6EAE4; white-space: nowrap; }
  .ledger-table td.wrap { white-space: normal; }
  .ledger-table tbody tr:nth-child(even) td { background: #F7F9F6; }
  .ledger-table tbody tr:hover td { background: #E6F0E2; }
</style>
"""
HEAD_HTML += STEP2_CSS


# ---- Step 3: the Home dashboard (Gemini, Oct 25) ---------------------------
# Gemini's STEP_3_HOME_CSS (plain string). Claude's changes and additions are
# marked "(Claude)": the grid's padding and a narrow-window fallback, link-button
# resets, the header link color per team (--team-link), a readable win green,
# score and link styles inside the matchup, the injury row's column order, and
# .offseason-hero (named in Gemini's plan but missing from its CSS).
STEP3_HOME_CSS = """
<style>
  .home-grid {
    display: grid;
    grid-template-columns: 1.15fr 1.1fr 0.95fr;
    gap: 12px;
    width: 100%;
    align-items: start;
    padding: 12px 16px;                 /* (Claude) */
  }
  .home-col { display: flex; flex-direction: column; min-width: 0; }      /* (Claude) */
  @media (max-width: 1150px) {          /* (Claude) a narrow window: one column under another */
    .home-grid { grid-template-columns: minmax(0, 1fr); }
  }

  /* Dashboard card container and header band */
  body .hcard {
    background: #FFFFFF;
    border: 1px solid #C4CDD8;
    border-top: none;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(15, 25, 35, 0.06);
    overflow: hidden;
    margin-bottom: 12px;
    padding: 0;                          /* (Claude) the body has the padding */
  }
  .hcard-head {
    background: var(--turf);
    color: #FFFFFF;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid var(--team-accent, var(--flag));
  }
  .hcard-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 15.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #FFFFFF;
  }
  .hcard-title .hcount { color: rgba(255,255,255,.75); }                /* (Claude) */
  .hcard-link {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600;
    font-size: 13.5px;
    color: var(--team-link, var(--flag));                              /* (Claude: readable on every team) */
    text-decoration: none;
    letter-spacing: 0.02em;
    background: none; border: 0; padding: 0; cursor: pointer;         /* (Claude: it's a button) */
  }
  .hcard-link:hover {
    text-decoration: underline;
    filter: brightness(1.1);
  }
  .hcard-body {
    padding: 10px 12px;
  }

  /* "This week" broadcast matchup hero */
  .matchup-hero {
    background: linear-gradient(180deg, var(--turf-dark) 0%, #101A22 100%);
    color: #FFFFFF;
    padding: 14px 16px;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 12px;
  }
  .matchup-side { display: flex; flex-direction: column; min-width: 0;
                  align-items: flex-start; }      /* (Claude: the record pill fits its text, not the column) */
  .matchup-side.home-side { text-align: right; align-items: flex-end; }
  .matchup-abbrev {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 40px;
    line-height: 0.92;
    letter-spacing: 0.02em;
  }
  .matchup-side.is-you .matchup-abbrev { color: var(--flag); }          /* (Claude) your team */
  .matchup-teamname {
    font-size: 13.5px;
    color: rgba(255, 255, 255, 0.82);
    font-weight: 500;
    margin-top: 2px;
  }
  .matchup-teamname a { color: inherit; }                               /* (Claude) */
  .matchup-record {
    display: inline-block;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600;
    font-size: 14px;
    background: rgba(255, 255, 255, 0.12);
    padding: 1px 7px;
    border-radius: 3px;
    margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }
  .matchup-score {                                                      /* (Claude) a played game's score */
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 30px; line-height: 1;
    margin-top: 4px; opacity: .65; font-variant-numeric: tabular-nums;
  }
  .matchup-score.won { opacity: 1; color: var(--flag); }
  .matchup-vs-badge {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 15px;
    color: var(--flag);
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .matchup-vs-badge.final { width: auto; padding: 0 9px; border-radius: 17px; font-size: 13px; }   /* (Claude) */
  .matchup-actions {
    background: #F8FAFC;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #E2E8F0;
    gap: 10px;
  }
  .last-game-strip {
    background: #F1F5F9;
    padding: 7px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 13.5px;
  }
  .last-game-strip .lg-mid { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
                             white-space: nowrap; }                     /* (Claude) */
  .last-game-pill {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 13.5px;
    padding: 1px 7px;
    border-radius: 3px;
    white-space: nowrap;
  }
  .last-game-pill.is-win { background: #DEF7EC; color: #03543F; border: 1px solid #84E1BC; }
  .last-game-pill.is-loss { background: #FDE8E8; color: #9B1C1C; border: 1px solid #F8B4B4; }
  .last-game-pill.is-tie { background: #EEF1F4; color: #334155; border: 1px solid #CBD5E1; }   /* (Claude) */
  .home-textlink { background: none; border: 0; padding: 0; cursor: pointer; font: inherit;      /* (Claude) */
                   color: var(--turf); text-decoration: underline; text-align: left; }

  /* (Claude) The offseason's phase card: same look as the matchup */
  .offseason-hero {
    background: linear-gradient(180deg, var(--turf-dark) 0%, #101A22 100%);
    color: #FFFFFF;
    padding: 14px 16px;
  }
  .offseason-hero .oh-kicker { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 12.5px;
                               text-transform: uppercase; letter-spacing: .06em; color: var(--flag); }
  .offseason-hero .oh-title { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 30px;
                              line-height: 1.05; margin-top: 2px; }
  .offseason-hero .oh-text { font-size: 14px; line-height: 1.45; color: rgba(255,255,255,.85); margin-top: 6px; }

  /* "Needs your attention" action rows */
  .attn-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-left: 4px solid var(--turf);
    border-radius: 3px;
    margin-bottom: 7px;
  }
  .attn-row:last-child { margin-bottom: 0; }
  .attn-row.attn-urgent { background: #FEF2F2; border-color: #FECACA; border-left-color: #DC2626; }
  .attn-row.attn-trade { background: #FFFBEB; border-color: #FDE68A; border-left-color: #D97706; }
  .attn-badge {
    display: inline-block;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 1px 5px;
    border-radius: 2px;
    background: #E2E8F0;
    color: #334155;
    margin-bottom: 2px;
  }
  .attn-urgent .attn-badge { background: #FEE2E2; color: #991B1B; }
  .attn-trade .attn-badge { background: #FEF3C7; color: #92400E; }
  .attn-text { font-size: 13.5px; line-height: 1.3; color: var(--ink); }
  .attn-main { min-width: 0; }                                          /* (Claude) */
  .attn-actions { display: flex; gap: 6px; flex: none; }               /* (Claude) */

  /* Division standings: last-5 streak chiclets */
  .streak-strip { display: inline-flex; gap: 2px; align-items: center; justify-content: flex-end; }
  .streak-box {
    width: 17px;
    height: 17px;
    border-radius: 2px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 11.5px;
    line-height: 17px;
    text-align: center;
    color: #FFFFFF;
  }
  .streak-box.w { background: #23703A; }    /* (Claude: Gemini's #2E8B47 gave white letters only 4.3:1) */
  .streak-box.l { background: #C2423C; }
  .streak-box.t { background: #64748B; }

  /* 2x3 team leaders grid */
  .leaders-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .leader-tile {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 3px;
    padding: 6px 9px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .leader-cat {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ink-soft);
    margin-bottom: 2px;
  }
  .leader-main { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
  .leader-player { font-size: 13.5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .leader-stat {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 16px;
    color: var(--turf);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* Right column: injuries and the Bitter news wire */
  .home-inj-row {
    display: grid;
    grid-template-columns: 38px max-content minmax(0, 1fr) auto;   /* (Claude: name, then the description truncates) */
    align-items: center;
    gap: 6px;
    padding: 4px 0;
    border-bottom: 1px solid #F1F5F9;
    font-size: 13.5px;
  }
  .home-inj-row:last-child { border-bottom: none; }
  .home-inj-desc { color: var(--ink-soft); font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .wire-item { padding: 6px 4px; border-bottom: 1px solid #EEF2F6; transition: background 0.1s ease; }
  .wire-item:last-child { border-bottom: none; }
  .wire-item:hover { background: #F8FAFC; }
  .wire-tag {
    display: inline-block;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--turf);
    background: #E8EEF5;
    padding: 0 5px;
    border-radius: 2px;
    margin-right: 6px;
  }
  .wire-tag.is-mine { background: #FEF3C7; color: #92400E; }
  .wire-headline {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--ink);
    text-decoration: none;
    background: none; border: 0; padding: 0; cursor: pointer; text-align: left;   /* (Claude: it's a button) */
  }
  .wire-headline:hover { color: var(--turf); text-decoration: underline; }
</style>
"""
HEAD_HTML += STEP3_HOME_CSS
