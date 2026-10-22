# text.py
# Play-by-play descriptions, written the way NFL game books read:
#   (12:34) (Shotgun) J.Smith pass short right to T.Jones to BOS 45 for 12 yards (D.Brown).

def short_name(p):
    if p is None:
        return "Team"
    return f"{p.first_name[0]}.{p.last_name}"


def spot(yl, off_abbrev, def_abbrev):
    """Yard line from the offense's view: yl = yards to the opponent's goal."""
    yl = int(round(yl))
    if yl <= 0:
        return f"{def_abbrev} end zone"
    if yl >= 100:
        return f"{off_abbrev} end zone"
    if yl == 50:
        return "50"
    if yl > 50:
        return f"{off_abbrev} {100 - yl}"
    return f"{def_abbrev} {yl}"


def clock_text(seconds):
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def down_text(down, togo, yl):
    ordinal = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(down, f"{down}th")
    dist = "Goal" if togo >= yl else str(togo)
    return f"{ordinal} & {dist}"


def yards_text(n):
    if n == 0:
        return "no gain"
    if n == 1:
        return "1 yard"
    if n == -1:
        return "-1 yard"
    return f"{n} yards"


def _tacklers(res):
    names = [short_name(p) for p in res.tacklers]
    if res.assist is not None:
        names.append(short_name(res.assist))
    return f" ({'; '.join(names)})" if names else ""


GAP_WORDS = {("left", "end"): "left end", ("left", "tackle"): "left tackle", ("left", "guard"): "left guard",
             ("middle", "guard"): "up the middle", ("right", "guard"): "right guard",
             ("right", "tackle"): "right tackle", ("right", "end"): "right end"}


def describe(res, before, off, deff, shotgun=False):
    """Text for a scrimmage play. `before` is the state at the snap."""
    o, d = off.abbrev, deff.abbrev
    yl = before.yl
    end_yl = yl - res.yards
    k = res.kind
    if k in ("run", "sneak"):
        where = "up the middle" if k == "sneak" else GAP_WORDS.get((res.direction, res.gap), res.direction)
        if res.td:
            s = f"{short_name(res.rusher)} {where} for {yards_text(res.yards)}, TOUCHDOWN."
        elif res.safety:
            s = f"{short_name(res.rusher)} {where} tackled in the end zone for a SAFETY{_tacklers(res)}."
        elif res.oob:
            s = f"{short_name(res.rusher)} {where} ran ob at {spot(end_yl, o, d)} for {yards_text(res.yards)}."
        else:
            s = f"{short_name(res.rusher)} {where} to {spot(end_yl, o, d)} for {yards_text(res.yards)}{_tacklers(res)}."
    elif k == "scramble":
        lead = f"{short_name(res.rusher)} scrambles {res.direction or 'up the middle'}"
        if res.direction in ("left", "right"):
            lead += " end"
        if res.td:
            s = f"{lead} for {yards_text(res.yards)}, TOUCHDOWN."
        elif res.oob:
            s = f"{lead} ran ob at {spot(end_yl, o, d)} for {yards_text(res.yards)}."
        else:
            s = f"{lead} to {spot(end_yl, o, d)} for {yards_text(res.yards)}{_tacklers(res)}."
    elif k == "kneel":
        s = f"{short_name(res.rusher)} kneels to {spot(end_yl, o, d)} for {yards_text(res.yards)}."
    elif k == "spike":
        s = f"{short_name(res.passer)} spiked the ball to stop the clock."
    elif k == "sack":
        names = "; ".join(short_name(p) for p in res.sackers)
        if res.safety:
            s = f"{short_name(res.passer)} sacked in the end zone for a SAFETY ({names})."
        else:
            s = f"{short_name(res.passer)} sacked at {spot(end_yl, o, d)} for {yards_text(res.yards)} ({names})."
    elif k == "pass":
        qb = short_name(res.passer)
        if res.throwaway:
            s = f"{qb} pass incomplete, thrown away under pressure."
        elif res.complete:
            lead = f"{qb} pass {res.depth_word} {res.direction} to {short_name(res.receiver)}"
            if res.td:
                s = f"{lead} for {yards_text(res.yards)}, TOUCHDOWN."
            elif res.oob:
                s = f"{lead} ran ob at {spot(end_yl, o, d)} for {yards_text(res.yards)}."
            else:
                s = f"{lead} to {spot(end_yl, o, d)} for {yards_text(res.yards)}{_tacklers(res)}."
        elif res.interception:
            catch_yl = yl - (res.air_yards or 0)
            lead = (f"{qb} pass {res.depth_word} {res.direction} intended for {short_name(res.receiver)} "
                    f"INTERCEPTED by {short_name(res.interceptor)}")
            if res.touchback:
                s = f"{lead} in the end zone. Touchback."
            elif res.def_td:
                s = f"{lead} at {spot(catch_yl, o, d)}. {short_name(res.interceptor)} returns it for a TOUCHDOWN."
            else:
                ret_yl = 100 - res.new_yl      # interceptor's team yards from... shown from offense view
                s = (f"{lead} at {spot(catch_yl, o, d)}. {short_name(res.interceptor)} to "
                     f"{spot(100 - res.new_yl, o, d) if res.new_yl is not None else ''} for "
                     f"{yards_text(res.return_yards)}.")
        else:
            lead = f"{qb} pass incomplete {res.depth_word} {res.direction} to {short_name(res.receiver)}"
            if res.dropped:
                s = f"{lead} (dropped)."
            elif res.pd_by is not None and getattr(res, "batted", False):
                s = f"{lead}, batted down at the line by {short_name(res.pd_by)}."
            elif res.pd_by is not None:
                s = f"{lead} ({short_name(res.pd_by)})."
            else:
                s = f"{lead}."
    else:
        s = ""
    if res.fumble:
        carrier = res.rusher or (res.receiver if res.complete else None) or res.passer
        if res.fumble_lost:
            team = d
            rec = short_name(res.recovered_by)
            if res.def_td:
                s += f" FUMBLES, RECOVERED by {team}-{rec} and returned for a TOUCHDOWN."
            else:
                s += f" {short_name(carrier)} FUMBLES ({short_name(res.forced_by)}), RECOVERED by {team}-{rec}."
        else:
            s += f" {short_name(carrier)} FUMBLES ({short_name(res.forced_by)}), recovered by {o}."
    if shotgun and k in ("pass", "sack", "scramble"):
        s = "(Shotgun) " + s
    return s


def describe_penalty(pen, before, off, deff, declined=False, offsetting=False):
    team = off if pen.side == "off" else deff
    who = f"{team.abbrev}-{short_name(pen.player)}" if pen.player is not None else team.abbrev
    if declined:
        return f"PENALTY on {who}, {pen.name}, declined."
    where = spot(before.yl, off.abbrev, deff.abbrev)
    tail = " - No Play." if pen.timing in ("pre", "prev", "spot") else "."
    return f"PENALTY on {who}, {pen.name}, {pen.yards} yards, enforced at {where}{tail}"


def describe_kickoff(res, kick, recv, from_yl=65):
    kicker = short_name(res.kicker)
    kspot = spot(from_yl, kick.abbrev, recv.abbrev)
    if res.kind == "onside":
        if res.change_poss:
            return f"{kicker} kicks onside from {kspot}. RECOVERED by {recv.abbrev}-{short_name(res.recovered_by)}."
        return f"{kicker} kicks onside from {kspot}. RECOVERED by {kick.abbrev}-{short_name(res.recovered_by)}!"
    if res.touchback:
        return f"{kicker} kicks {res.kick_distance} yards from {kspot} to the end zone, Touchback to the {recv.abbrev} 35."
    if res.note == "out of bounds":
        return f"{kicker} kicks from {kspot} out of bounds. Ball placed at the {recv.abbrev} 40."
    land = max(-9, 100 - res.kick_distance - (100 - from_yl) - 0)
    ret = short_name(res.returner)
    if res.def_td:
        return f"{kicker} kicks {res.kick_distance} yards from {kspot}. {ret} returns it {res.return_yards} yards for a TOUCHDOWN!"
    end = spot(res.new_yl, recv.abbrev, kick.abbrev) if res.new_yl is not None else ""
    tk = _tacklers(res)
    s = f"{kicker} kicks {res.kick_distance} yards from {kspot}. {ret} to {end} for {yards_text(res.return_yards)}{tk}."
    if res.fumble:
        if res.fumble_lost:
            s += f" {ret} FUMBLES, RECOVERED by {kick.abbrev}-{short_name(res.recovered_by)}."
        else:
            s += f" {ret} FUMBLES, recovered by {recv.abbrev}."
    return s


def describe_punt(res, before, kick, recv):
    p = short_name(res.punter)
    ls = short_name(res.snapper)
    if res.note == "bad snap":
        return f"Bad snap to {p}! The punt is not got away; {recv.abbrev} takes over."
    if res.blocked:
        if res.def_td:
            return f"{p} punt is BLOCKED and returned for a TOUCHDOWN!"
        return f"{p} punt is BLOCKED. {recv.abbrev} recovers."
    land_spot = spot(before.yl - res.kick_distance, kick.abbrev, recv.abbrev)
    s = f"{p} punts {res.kick_distance} yards to {land_spot}, Center-{ls}."
    if res.touchback:
        return s + " Touchback."
    if res.fair_catch:
        return s + f" Fair catch by {short_name(res.returner)}."
    if res.oob:
        return s + " Out of bounds."
    if res.downed:
        return s + f" Downed by {kick.abbrev}."
    if res.muffed:
        if res.fumble_lost:
            return s + f" {short_name(res.returner)} MUFFS the catch, RECOVERED by {kick.abbrev}-{short_name(res.recovered_by)}!"
        s += f" {short_name(res.returner)} muffs it but recovers."
    if res.def_td:
        return s + f" {short_name(res.returner)} returns it for a TOUCHDOWN!"
    end = spot(res.new_yl, recv.abbrev, kick.abbrev) if res.new_yl is not None else ""
    tk = _tacklers(res)
    return s + f" {short_name(res.returner)} to {end} for {yards_text(res.return_yards)}{tk}."


def describe_fg(res, kick):
    k = short_name(res.kicker)
    tail = f", Center-{short_name(res.snapper)}, Holder-{short_name(res.holder)}."
    if res.blocked:
        extra = " Returned for a TOUCHDOWN!" if res.def_td else ""
        return f"{k} {res.kick_distance} yard field goal is BLOCKED{tail}{extra}"
    if res.made:
        return f"{k} {res.kick_distance} yard field goal is GOOD{tail}"
    side = "Wide Right" if res.kick_distance % 2 else "Wide Left"
    if res.kick_distance >= 52 and res.kick_distance % 3 == 0:
        side = "Short"
    return f"{k} {res.kick_distance} yard field goal is No Good, {side}{tail}"


def describe_xp(res):
    k = short_name(res.kicker)
    if res.blocked:
        return f"{k} extra point is BLOCKED."
    return f"{k} extra point is GOOD." if res.made else f"{k} extra point is No Good."


# ---------------------------------------------------------------------------
# Detail line: what happened on the field (shown under each play)
# ---------------------------------------------------------------------------

CONCEPT_WORDS = {"screen": "screen", "quick": "quick game", "dropback": "dropback",
                 "play_action": "play action", "deep": "deep shot", "hail_mary": "Hail Mary"}
GAP_STYLE = {"guard": "inside run", "tackle": "off-tackle run", "end": "outside run"}


def detail(res, call, dcall, shotgun=False):
    k = res.kind
    parts = []
    off = call.package
    if k in ("pass", "sack", "scramble"):
        off += (", shotgun" if shotgun else ", under center") + ", " + CONCEPT_WORDS.get(call.concept, "pass")
    elif k == "sneak":
        off += ", QB sneak"
    elif k == "run":
        off += ", " + ("QB keeper" if call.carrier == "QB" else GAP_STYLE.get(call.gap, "run"))
    else:
        return ""
    d = dcall.package
    if getattr(dcall, "loaded", False):
        d += ", 8 in the box"
    if k in ("pass", "sack", "scramble"):
        d += ", " + ("man" if dcall.coverage == "man" else "zone") + " coverage"
    if dcall.blitzers:
        d += f", {len(dcall.blitzers) + 4}-man rush"
    if dcall.prevent:
        d += ", prevent"
    parts.append(f"{off} vs {d}.")
    if k == "sack":
        if res.beat is not None:
            parts.append(f"{short_name(res.pressure_by)} beat {short_name(res.beat)}.")
        else:
            parts.append(f"{short_name(res.pressure_by)} came free.")
    elif k == "scramble":
        parts.append("Pressure flushed him out." if res.pressure_by else "Nobody open; he took off.")
    elif k == "pass":
        if res.pressure_by is not None:
            who = f"{short_name(res.pressure_by)} beat {short_name(res.beat)}" if res.beat is not None \
                else f"{short_name(res.pressure_by)} came free"
            parts.append(f"Pressure: {who}.")
        if getattr(res, "bracket", None) is not None and res.bracket is not res.receiver:
            parts.append(f"Extra coverage rolled to {short_name(res.bracket)}.")
        if res.throwaway:
            parts.append("Nobody open.")
        elif res.sep is not None and res.receiver is not None:
            if res.cover_def is None or res.sep > 1.3:
                parts.append(f"{short_name(res.receiver)} was wide open.")
            elif res.sep < -0.6:
                parts.append(f"Tight coverage by {short_name(res.cover_def)}.")
            elif res.complete and res.yac >= 10:
                parts.append(f"{short_name(res.receiver)} broke free after the catch.")
    elif k == "run":
        e = res.block_edge or 0.0
        if res.yards <= 0 and res.tacklers:
            parts.append(f"Stuffed by {short_name(res.tacklers[0])}." if e < 0 else "Penetration in the backfield.")
        elif res.yards >= 12:
            parts.append("Big hole, and he hit it." if e > 0.3 else "He made a man miss and broke into the open.")
        elif e > 0.6:
            parts.append("The line won up front.")
        elif e < -0.6:
            parts.append("The defense won at the point of attack.")
    return " ".join(parts)


def describe_two_point(res, off, deff):
    k = res.kind
    if k in ("run", "sneak", "scramble"):
        where = "up the middle" if k == "sneak" else GAP_WORDS.get((res.direction, res.gap), res.direction or "up the middle")
        if k == "scramble":
            return f"{short_name(res.rusher)} scrambles"
        return f"{short_name(res.rusher)} rushes {where}"
    if k == "sack":
        return f"{short_name(res.passer)} is sacked"
    if res.throwaway:
        return f"{short_name(res.passer)} throws it away"
    if res.complete:
        return f"{short_name(res.passer)} pass to {short_name(res.receiver)} is complete"
    if res.interception:
        return f"{short_name(res.passer)} pass to {short_name(res.receiver)} is INTERCEPTED by {short_name(res.interceptor)}"
    return f"{short_name(res.passer)} pass to {short_name(res.receiver)} is incomplete"
