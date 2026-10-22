# formations.py
# Draws a package as a picture of the field: where each spot lines up, with
# the player's name and his rating at that spot. Seen from behind your own
# unit, so left on the picture is your left.

from html import escape

from engine import depth
from engine import formatting as fmt
from engine.scale import shown
from . import theme

WIDTH, HEIGHT = 900, 370
LOS_Y = 70                     # line of scrimmage, near the top

# Where each spot stands: (x, y). y grows toward the viewer (away from the ball).
_OL = {"LT": (330, 110), "LG": (390, 110), "C": (450, 110), "RG": (510, 110), "RT": (570, 110)}
_SHOTGUN = {"QB": (450, 205), "RB": (505, 205)}
_UNDER_CENTER = {"QB": (450, 165), "RB": (450, 250)}
_I_FORM = {"QB": (450, 160), "FB": (450, 210), "RB": (450, 262)}

OFFENSE_SPOTS = {
    "11 personnel": {**_OL, **_SHOTGUN, "TE1": (630, 112), "WR1": (80, 110), "WR2": (820, 130),
                     "WR3": (725, 140)},
    "12 personnel": {**_OL, **_UNDER_CENTER, "TE1": (630, 112), "TE2": (270, 112),
                     "WR1": (80, 110), "WR2": (820, 130)},
    "21 personnel": {**_OL, **_I_FORM, "TE1": (630, 112), "WR1": (80, 110), "WR2": (820, 130)},
    "13 personnel": {**_OL, **_UNDER_CENTER, "TE1": (630, 112), "TE2": (270, 112),
                     "TE3": (680, 160), "WR1": (80, 110)},
    "22 personnel": {**_OL, **_I_FORM, "TE1": (630, 112), "TE2": (270, 112), "WR1": (80, 110)},
    "10 personnel": {**_OL, **_SHOTGUN, "WR1": (80, 110), "WR2": (820, 130),
                     "WR3": (725, 140), "WR4": (175, 140)},
}

_DL = {"LE": (300, 105), "LDT": (400, 105), "RDT": (500, 105), "RE": (600, 105)}
DEFENSE_SPOTS = {
    "Base 4-3": {**_DL, "WLB": (330, 185), "MLB": (450, 195), "SLB": (570, 185),
                 "CB1": (90, 115), "CB2": (810, 115), "FS": (370, 280), "SS": (540, 265)},
    "Nickel":   {**_DL, "WLB": (390, 190), "MLB": (510, 190), "NB": (705, 140),
                 "CB1": (90, 115), "CB2": (810, 115), "FS": (370, 280), "SS": (540, 265)},
    "Dime":     {**_DL, "MLB": (450, 195), "NB": (705, 140), "DB": (195, 140),
                 "CB1": (90, 115), "CB2": (810, 115), "FS": (370, 280), "SS": (540, 265)},
}

UNIT_PACKAGES = {"Offense": list(OFFENSE_SPOTS), "Defense": list(DEFENSE_SPOTS)}


def formation_svg(chart, package, player_lookup):
    """SVG picture of who lines up where in a package."""
    spots = OFFENSE_SPOTS.get(package) or DEFENSE_SPOTS[package]
    unit = "Offense" if package in OFFENSE_SPOTS else "Defense"
    lineup = depth.on_field(chart, package)

    parts = [f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" class="formation" role="img" '
             f'aria-label="{escape(package)} formation">',
             f'<rect width="{WIDTH}" height="{HEIGHT}" rx="4" fill="{theme.TURF}"/>']
    # Yard lines every 5 yards, and the line of scrimmage in flag yellow.
    for y in range(LOS_Y + 60, HEIGHT, 60):
        parts.append(f'<line x1="0" x2="{WIDTH}" y1="{y}" y2="{y}" stroke="white" stroke-opacity="0.13" stroke-width="2"/>')
    parts.append(f'<line x1="0" x2="{WIDTH}" y1="{LOS_Y}" y2="{LOS_Y}" stroke="{theme.FLAG}" stroke-width="3"/>')
    parts.append(f'<text x="12" y="{LOS_Y - 8}" class="f-note">Line of scrimmage</text>')
    parts.append(f'<text x="{WIDTH - 12}" y="{HEIGHT - 12}" text-anchor="end" class="f-note">'
                 f'Seen from behind your {unit.lower()}</text>')

    for slot, (x, y) in spots.items():
        pid = lineup.get(slot)
        p = player_lookup(pid) if pid else None
        if p is None:
            parts.append(f'<circle cx="{x}" cy="{y}" r="19" fill="none" stroke="white" '
                         f'stroke-dasharray="4 3" stroke-opacity="0.7"/>')
            parts.append(f'<text x="{x}" y="{y + 5}" text-anchor="middle" class="f-slot">{slot}</text>')
            parts.append(f'<text x="{x}" y="{y + 38}" text-anchor="middle" class="f-name">empty</text>')
            continue
        from engine.evaluation import user_view       # your staff's evaluation (Oct 24)
        from .state import state
        rating = shown(depth.rating_at(user_view(state.league, p), slot), depth.SLOTS[slot][1] if slot in depth.SLOTS else p.position)
        rcolor = theme.RATING_COLORS[fmt.skill_word(rating)]
        natural = depth.SLOTS[slot][1]
        color = theme.POSITION_COLORS[natural]
        text = theme._text_on(color)
        parts.append(f'<circle cx="{x}" cy="{y}" r="19" fill="{color}" stroke="white" stroke-width="2"/>')
        parts.append(f'<text x="{x}" y="{y + 5}" text-anchor="middle" class="f-slot" style="fill:{text}">{slot}</text>')
        parts.append(f'<text x="{x}" y="{y + 38}" text-anchor="middle" class="f-name">'
                     f'{escape(p.last_name)}</text>')
        parts.append(f'<rect x="{x - 15}" y="{y + 44}" width="30" height="17" rx="3" fill="{rcolor}"/>')
        parts.append(f'<text x="{x}" y="{y + 57}" text-anchor="middle" class="f-rating" '
                     f'style="fill:{theme._text_on(rcolor)}">{rating}</text>')
    parts.append("</svg>")
    return "".join(parts)
