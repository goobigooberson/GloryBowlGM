# news_front_office.py
# News about the people who run the teams (Oct 22): general managers (gm.py)
# and head coaches (staff.py) fired, hired and retiring after each season, and
# the two going out together when an owner cleans house. Kept apart from
# news.py, which calls front_office_news() for each season while it builds the
# news. Everything comes from the league's own records (the GM and staff logs);
# nothing is saved here. Bitter gets an insider's scoop, the team's welcome and
# its fans' reactions.

from .news import article, join_and, plural, possessive

CAL_FIRED = -6        # right after the season (the real "Black Monday")
CAL_HIRED = -5        # January into February


def _gm_record(p, tid):
    rec = [r for r in p["record"] if r["team"] == tid and not r.get("interim")]
    w = sum(r["w"] for r in rec)
    l_ = sum(r["l"] for r in rec)
    t_ = sum(r["t"] for r in rec)
    trips = sum(1 for r in rec if r.get("seed"))
    titles = [r["season"] for r in rec if (r.get("result") or "").startswith("Won")]
    return rec, w, l_, t_, trips, titles


def _wl(w, l_, t_):
    return f"{w}-{l_}" + (f"-{t_}" if t_ else "")


def _a(w):
    """'a' or 'an' before a record that starts with this many wins ('an 8-9 season', 'an 11-6')."""
    return "an" if str(w).startswith("8") or w in (11, 18) else "a"


def _fresh(ctx, slot, rng, options):
    """One of the options not used yet in this slot this season (a bit's shape is used
    once a week at most: tools/bitter_check.py), or None when they're all used."""
    used = ctx.__dict__.setdefault("_fo_used", {}).setdefault(slot, set())
    free = [o for o in options if o not in used]
    if not free:
        return None
    o = rng.choice(free)
    used.add(o)
    return o


def _hc_record(c, tid):
    rec = [r for r in c["record"] if r["team"] == tid and r["job"] == "HC" and not r.get("interim")]
    return rec, sum(r["w"] for r in rec), sum(r["l"] for r in rec), sum(r["t"] for r in rec), \
        sum(1 for r in rec if r.get("seed"))


def _last_line(ctx, season, tid):
    return next((r for r in ctx.league.team_history if r["team"] == tid and r["season"] == season - 1), None)


def _gm_open(ctx, season, rng, tid, name, age):
    return ctx.pick(("gm-hired-open", season), rng, [
        f"The {ctx.full(tid)} have hired {name}, {age}, as general manager.",
        f"{name}, {age}, is the new general manager of the {ctx.full(tid)}.",
        f"The {ctx.nick(tid)} have their new GM: {name}, {age}.",
        f"The {ctx.full(tid)} have handed their front office to {name}, {age}.",
        f"After their search, the {ctx.full(tid)} named {name}, {age}, general manager."])


def front_office_news(ctx, season):
    """Stories and bits for the offseason that opened league year `season`."""
    league = ctx.league
    st = getattr(league, "staff", None)
    if not st or season <= ctx.first:
        return
    from . import gm as G
    from . import staff as S
    gmlog = [e for e in (st.get("gm") or {}).get("log", []) if e["season"] == season and not e.get("quiet")]
    hclog = [e for e in st.get("log", []) if e["season"] == season and e["job"] == "HC"
             and e["move"] in ("fired", "retired", "hired")]
    gm_out = {e["team"]: e for e in gmlog if e["move"] in ("fired", "retired")}
    hc_out = {e["team"]: e for e in hclog if e["move"] in ("fired", "retired")}
    rng = ctx.rng(season, "front-office")
    done_hc = set()
    # 1. GMs out (with the head coach, when both go).
    for tid, e in sorted(gm_out.items()):
        if tid not in ctx.teams:
            continue
        p = G.person(league, e["gid"])
        if not p:
            continue
        rec, w, l_, t_, trips, titles = _gm_record(p, tid)
        n = len(rec)
        last = _last_line(ctx, season, tid)
        last_txt = f" after {_a(last['w'])} {_wl(last['w'], last['l'], last['t'])} season" if last else ""
        hce = hc_out.get(tid)
        both = hce is not None and hce["move"] == "fired" and e["move"] == "fired"
        team = ctx.full(tid)
        if e["move"] == "retired":
            head = ctx.pick(("gm-ret", season), rng, [f"{p['name']} retires as {ctx.nick(tid)} general manager",
                                                     f"{ctx.nick(tid)} GM {p['name']} steps away"])
            body = ctx.pick(("gm-ret-open", season), rng, [
                f"{p['name']} is retiring as general manager of the {team} after {plural(n, 'season')} in the job.",
                f"After {plural(n, 'season')} running the {team}, {p['name']} is stepping away.",
                f"The {team} will need a new general manager: {p['name']} is retiring."])
            body += f" His teams went {_wl(w, l_, t_)}." if n else ""
            imp = 30 + min(15, 2 * n) + 6 * len(titles)
        elif both:
            c = S.coach(league, hce["cid"])
            hrec = _hc_record(c, tid) if c else ([], 0, 0, 0, 0)
            head = ctx.pick(("gm-both", season), rng, [
                f"{ctx.nick(tid)} clean house: GM {p['name']} and coach {hce['name']} fired",
                f"{ctx.nick(tid)} fire general manager {p['name']} and head coach {hce['name']}",
                f"Fresh start in {ctx.city(tid)}: {p['name']}, {hce['name']} out"])
            body = (ctx.pick(("gm-both-open", season), rng, [
                        f"The {team} have fired general manager {p['name']} and head coach {hce['name']}{last_txt}. ",
                        f"It's a clean sweep in {ctx.city(tid)}: general manager {p['name']} and head coach "
                        f"{hce['name']} are both out{last_txt}. ",
                        f"The {ctx.nick(tid)} owner has seen enough{last_txt}: GM {p['name']} and coach {hce['name']} "
                        f"have been let go. "])
                    + f"{p['name']} ran the front office for {plural(n, 'season')} ({_wl(w, l_, t_)}"
                    + (f", {plural(trips, 'playoff trip')}" if trips else ", no playoff trips") + ")"
                    + (f"; {hce['name']} coached {plural(len(hrec[0]), 'season')} ({_wl(hrec[1], hrec[2], hrec[3])})."
                       if hrec[0] else ".")
                    + " The owner will hire a new general manager first, and he'll pick the next coach.")
            imp = 55
            done_hc.add(tid)
        else:
            head = ctx.pick(("gm-fired", season), rng, [f"{ctx.nick(tid)} fire general manager {p['name']}",
                                                       f"{p['name']} out as {ctx.nick(tid)} GM",
                                                       f"{ctx.city(tid)} moves on from GM {p['name']}"])
            body = (ctx.pick(("gm-fired-open", season), rng, [
                        f"The {team} have fired general manager {p['name']}{last_txt}. ",
                        f"{p['name']} is out as the {possessive(team)} general manager{last_txt}. ",
                        f"The {ctx.nick(tid)} are looking for a new general manager{last_txt}: {p['name']} has been fired. "])
                    + f"In {plural(n, 'season')} his teams went {_wl(w, l_, t_)}" + (f" with {plural(trips, 'playoff trip')}" if trips else
                                                      " and never made the playoffs") + ".")
            hc = S.staff_of(league, tid)["HC"]
            if tid in hc_out:
                pass
            elif hc:
                body += f" Head coach {hc['name']} stays, for now: the new GM will decide his future."
            imp = 45 + min(8, n)
        ctx.add(season, CAL_FIRED, "front_office", head, body, teams=[tid], importance=imp,
                key=f"gm-out-{season}-{tid}")
        if e["move"] == "fired":
            ins = ctx.insider(rng)
            scoop = _fresh(ctx, ("gm-scoop", season), rng, [
                f"Sources: the {ctx.nick(tid)} have fired GM {p['name']}" + (f" and HC {hce['name']}." if both else "."),
                f"The {ctx.nick(tid)} are moving on from general manager {p['name']}, I'm told"
                + (f". {hce['name']} is out as well." if both else "."),
                f"{p['name']} is out as {ctx.nick(tid)} GM after {plural(n, 'season')}, per sources.",
                f"Change at the top in {ctx.city(tid)}: {p['name']} won't be back as GM"
                + (f", and neither will {hce['name']}." if both else "."),
                f"Hearing the {ctx.nick(tid)} have let general manager {p['name']} go"
                + (f" along with {hce['name']}." if both else ".")])
            if scoop:
                ctx.post(season, CAL_FIRED, ins, scoop, teams=[tid], importance=imp - 5, kind="front_office")
            mood = rng.random()
            if w < l_:
                fan_txt = _fresh(ctx, ("gm-fan-bad", season), rng, [f"Finally. {plural(n, 'year')} of this. Thank you, ownership.",
                                      f"{_wl(w, l_, t_)}. That's the whole review. Bye, {p['name'].split()[-1]}.",
                                      "About time. Now get the next one right.",
                                      f"Whoever's next: the bar is on the floor. {_wl(w, l_, t_)}."])
            else:
                fan_txt = _fresh(ctx, ("gm-fan-good", season), rng, [f"{_wl(w, l_, t_)} and {plural(trips, 'playoff trip')} and he's fired? Bold move.",
                                      "Didn't see this coming. Hope ownership has a plan.",
                                      f"Not sure this was the problem. {p['name'].split()[-1]} built a decent roster."])
            if fan_txt:
                ctx.post(season, CAL_FIRED, ctx.fan(tid, rng, 0 if mood < 0.5 else 1), fan_txt, teams=[tid],
                         importance=24, kind="front_office")
    # 2. Head coaches out (alone).
    for e in hclog:
        tid = e["team"]
        if e["move"] not in ("fired", "retired") or tid in done_hc or tid not in ctx.teams:
            continue
        c = S.coach(league, e["cid"])
        if not c:
            continue
        rec, w, l_, t_, trips = _hc_record(c, tid)
        n = len(rec)
        if n == 0:
            continue
        last = _last_line(ctx, season, tid)
        if e["move"] == "retired":
            head = ctx.pick(("hc-ret", season), rng, [f"{ctx.nick(tid)} coach {c['name']} retires",
                                                     f"{c['name']} retires from coaching",
                                                     f"{ctx.city(tid)} coach {c['name']} calls it a career",
                                                     f"{c['name']} steps away from the {ctx.nick(tid)} sideline",
                                                     f"Retirement opens the {ctx.city(tid)} coaching job"])
            body = ctx.pick(("hc-ret-open", season), rng, [
                f"{c['name']} is retiring after {plural(n, 'season')} as head coach of the {ctx.full(tid)} ({_wl(w, l_, t_)}).",
                f"The {ctx.full(tid)} need a new head coach: {c['name']} has retired ({_wl(w, l_, t_)} in {plural(n, 'season')}).",
                f"After {plural(n, 'season')} and {_a(w)} {_wl(w, l_, t_)} record in {ctx.city(tid)}, {c['name']} is done coaching.",
                f"{c['name']} has coached his last game: he's retiring from the {ctx.full(tid)} ({_wl(w, l_, t_)}).",
                f"The {ctx.nick(tid)} announced that coach {c['name']} is retiring ({_wl(w, l_, t_)} in {plural(n, 'season')})."])
            imp = 34 + min(12, n)
        else:
            gmp = G.gm_of(league, tid)
            new_gm = gmp is not None and gmp.get("since") == season
            head = ctx.pick(("hc-fired", season), rng, [f"{ctx.nick(tid)} fire head coach {c['name']}",
                                                       f"{c['name']} out as {ctx.nick(tid)} head coach",
                                                       f"{ctx.city(tid)} parts ways with coach {c['name']}",
                                                       f"{c['name']} fired by the {ctx.nick(tid)}",
                                                       f"Coaching change in {ctx.city(tid)}: {c['name']} out",
                                                       f"{ctx.nick(tid)} show coach {c['name']} the door"])
            after = f" after {_a(last['w'])} {_wl(last['w'], last['l'], last['t'])} season" if last else ""
            body = (ctx.pick(("hc-fired-open", season), rng, [
                        f"The {ctx.full(tid)} have fired head coach {c['name']}{after}.",
                        f"{c['name']} is out as head coach of the {ctx.full(tid)}{after}.",
                        f"The {ctx.nick(tid)} have moved on from coach {c['name']}{after}.",
                        f"There's a head coaching opening in {ctx.city(tid)}: {c['name']} has been fired{after}.",
                        f"Coach {c['name']} won't be back with the {ctx.full(tid)}{after}.",
                        f"The {ctx.full(tid)} let head coach {c['name']} go{after}."])
                    + f" He went {_wl(w, l_, t_)} in {plural(n, 'season')}"
                    + (f" with {plural(trips, 'playoff trip')}." if trips else ".")
                    + (f" It's the first big call for new general manager {gmp['name']}." if new_gm else ""))
            imp = 40 + min(8, n)
        ctx.add(season, CAL_FIRED, "front_office", head, body, teams=[tid], importance=imp,
                key=f"hc-out-{season}-{tid}")
    # 3. New GMs.
    for e in gmlog:
        tid = e["team"]
        if e["move"] != "hired" or tid not in ctx.teams:
            continue
        p = G.person(league, e["gid"])
        if not p:
            continue
        past = [r for r in p["record"] if r["team"] != tid and not r.get("interim") and r["season"] < season]
        frm = p.get("from") or ""
        head = ctx.pick(("gm-hired", season), rng, [f"{ctx.nick(tid)} name {p['name']} general manager",
                                                   f"{p['name']} hired as {ctx.nick(tid)} GM",
                                                   f"{ctx.nick(tid)} pick {p['name']} to run the front office",
                                                   f"New {ctx.nick(tid)} GM: {p['name']}",
                                                   f"{p['name']} takes over the {ctx.city(tid)} front office"])
        age = season - p["born"]
        if past:
            teams = []
            for r in past:
                if r["team"] not in teams:
                    teams.append(r["team"])
            w = sum(r["w"] for r in past)
            l_ = sum(r["l"] for r in past)
            t_ = sum(r["t"] for r in past)
            body = (_gm_open(ctx, season, rng, tid, p['name'], age) + " He ran the "
                    + join_and([f"{ctx.full(t)}" for t in teams if t in ctx.teams])
                    + f" front office for {plural(len(past), 'season')} ({_wl(w, l_, t_)}).")
            known = G.style_words(league, p)
            if known:
                body += f" Around the league he's known for one thing above all: {known[0][1].lower()}."
        else:
            if p.get("from_team") in ctx.teams and p.get("from_job"):
                job = p["from_job"].lower()
                was = f"He was the {possessive(ctx.full(p['from_team']))} {job}"
            else:
                was = f"He was {article(frm)} {frm.lower()} elsewhere in the league" if frm else ""
            if not frm and p.get("exp"):
                body = (_gm_open(ctx, season, rng, tid, p['name'], age) + " He's run a front "
                        f"office before ({plural(p['exp'], 'season')} as a GM, before this league's records begin).")
            else:
                body = (_gm_open(ctx, season, rng, tid, p['name'], age) + " "
                        + (f"{was}, and it's his first time running a front office." if frm else "He's a first-time GM."))
            if p.get("from_team") in ctx.teams and p.get("from_job"):
                body += (f" The {ctx.nick(p['from_team'])} can't block a promotion, so they'll need a new "
                         f"{p['from_job'].lower()}.")
        hc = S.staff_of(league, tid)["HC"]
        if hc and (hc.get("since") or 0) < season:
            body += f" His first decision: whether to keep head coach {hc['name']}."
        ctx.add(season, CAL_HIRED, "front_office", head, body, teams=[tid] + ([p["from_team"]] if p.get("from_team") in ctx.teams else []),
                importance=42, key=f"gm-in-{season}-{tid}")
        from . import bitter
        hello = _fresh(ctx, ("gm-welcome", season), rng, [
            f"Welcome to {ctx.city(tid)}, {p['name']}. Our new general manager. {bitter.tag(ctx, tid)}",
            f"We've named {p['name']} our general manager. {bitter.tag(ctx, tid)}",
            f"Please welcome GM {p['name']} to the {ctx.nick(tid)}! {bitter.tag(ctx, tid)}",
            f"Introducing the new general manager of the {ctx.full(tid)}: {p['name']}. {bitter.tag(ctx, tid)}",
            f"{p['name']} is officially our GM. Let's build. {bitter.tag(ctx, tid)}",
            f"A new era starts today. {p['name']} will lead our front office. {bitter.tag(ctx, tid)}"])
        if hello:
            ctx.post(season, CAL_HIRED, bitter.team_account(ctx, tid), hello, teams=[tid], importance=30,
                     kind="front_office")
    # 4. New head coaches.
    for e in hclog:
        tid = e["team"]
        if e["move"] != "hired" or tid not in ctx.teams:
            continue
        c = S.coach(league, e["cid"])
        if not c:
            continue
        before = [r for r in c["record"] if r["job"] == "HC" and not r.get("interim") and r["season"] < season]
        bg = S.GROUP_NAMES.get(c.get("bg"), "").lower()
        if before:
            w = sum(r["w"] for r in before)
            l_ = sum(r["l"] for r in before)
            t_ = sum(r["t"] for r in before)
            past = f"He's been a head coach before ({plural(len(before), 'season')}, {_wl(w, l_, t_)})."
        elif c.get("college"):
            past = "He comes from the college game."
        else:
            prev = [r for r in c["record"] if r["season"] == season - 1]
            past = (f"He was the {possessive(ctx.full(prev[-1]['team']))} {S.JOB_NAMES[prev[-1]['job']].lower()}"
                    if prev and prev[-1]["team"] in ctx.teams else "He's a first-time head coach")
            past += (f", with a background coaching {bg}." if bg else ".")
        gmp = G.gm_of(league, tid)
        hired_by = ""
        if gmp is not None and gmp.get("since") == season:
            hired_by = f" It's the first hire of new general manager {gmp['name']}."
        elif gmp is not None:
            hired_by = f" General manager {gmp['name']} made the hire."
        head = ctx.pick(("hc-hired", season), rng, [f"{ctx.nick(tid)} hire {c['name']} as head coach",
                                                   f"{c['name']} named {ctx.nick(tid)} head coach",
                                                   f"{ctx.nick(tid)} land {c['name']} as their next coach",
                                                   f"{ctx.nick(tid)} turn to {c['name']}",
                                                   f"{c['name']} gets the {ctx.city(tid)} job",
                                                   f"It's {c['name']} for the {ctx.nick(tid)}",
                                                   f"{ctx.city(tid)} picks {c['name']} to coach",
                                                   f"New {ctx.nick(tid)} coach: {c['name']}"])
        a = season - c["born"]
        body = ctx.pick(("hc-hired-open", season), rng, [
            f"The {ctx.full(tid)} have hired {c['name']}, {a}, as head coach.",
            f"{c['name']}, {a}, is the new head coach of the {ctx.full(tid)}.",
            f"The {ctx.nick(tid)} have their new head coach: {c['name']}, {a}.",
            f"{c['name']} will coach the {ctx.full(tid)}, the team announced.",
            f"The {ctx.city(tid)} job goes to {c['name']}, {a}.",
            f"After their search, the {ctx.full(tid)} settled on {c['name']}, {a}, as head coach.",
            f"The {ctx.full(tid)} turned to {c['name']} to lead the team.",
            f"It's official in {ctx.city(tid)}: {c['name']} takes over as head coach.",
            f"{c['name']} has a head coaching job: the {ctx.full(tid)} hired him.",
            f"Meet the new {ctx.nick(tid)} coach, {c['name']}, {a}.",
            f"The {ctx.full(tid)} named {c['name']} their head coach.",
            f"{c['name']}, {a}, gets the keys to the {ctx.full(tid)}."]) + f" {past}{hired_by}"
        ctx.add(season, CAL_HIRED, "front_office", head, body, teams=[tid], importance=40,
                key=f"hc-in-{season}-{tid}-{c['id']}")
