# news_trades.py
# News and Bitter bits about player trades (Oct 23; trades.py). news.py calls
# trade_news() for each season while it builds the news. Everything comes from the
# trade log (league.trades["log"]: who went where for what, and when) and the
# league's records; nothing is saved here and nothing is invented: no made-up
# quotes about decisions, no reasons a team didn't give. Bitter gets an insider's
# scoop, the teams' welcomes and goodbyes, fans' reactions, and now and then the
# player himself; players you shopped around show up as rumors.

from .news import POS_WORD, join_and, plural, pos_abbr, possessive

# Calendar spots for offseason trades (news.py: negative = the offseason; -2 is the draft).
CAL = {"league_year": -4, "fa_early": -3.5, "pre_draft": -3, "draft": -2, "fa_late": -1.5}
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh"}


def _cal(ctx, e):
    when = e.get("when") or ""
    if e.get("phase") in CAL:
        return CAL[e["phase"]]
    if when == "Trade deadline":
        from .trades import DEADLINE_WEEK
        dw = DEADLINE_WEEK.get(ctx.league.settings.get("season_games", 17), 9)
        return 5 + dw + 0.6
    c = ctx.label_cal(when)
    return c + 0.4 if c >= 0 else -1


def _pick_text(e, key, long=True):
    s, r, o = (int(x) for x in key.split("-"))
    num = (e.get("picks") or {}).get(key, {}).get("num")
    if long:
        return f"a {s} {ORD.get(r, f'{r}th')}-round pick" + (f" (No. {num})" if num else "")
    return f"a {s} {ORD.get(r, str(r))}" + (f" (No. {num})" if num else "")


def _side(ctx, e, side, tid_from, long=True):
    """What one side sent, in words."""
    g = e["gave"][side]
    bits = []
    for pid in g["players"]:
        p = ctx.player(pid)
        if p:
            bits.append(f"{POS_WORD.get(p.position, p.position)} {p.name}" if long else f"{pos_abbr(p)} {p.name}")
    picks = sorted(g["picks"], key=lambda k: (int(k.split("-")[0]), int(k.split("-")[1])))
    for k in picks:
        o = int(k.split("-")[2])
        own = "" if o == tid_from else f" (from {ctx.full(o) if long else ctx.teams[o].abbrev})"
        bits.append(_pick_text(e, k, long) + own)
    return join_and(bits) if bits else "nothing"


def _record(ctx, tid, season, cal):
    """The team's record at the time (regular season trades only), as '5-3'."""
    if cal < 6:
        return None
    from .season import records
    if season != ctx.league.season:
        return None
    r = records(ctx.league).get(tid)
    if not r:
        return None
    return f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")


def trade_news(ctx, season):
    """Stories and bits for the trades made in league year `season`."""
    league = ctx.league
    t = getattr(league, "trades", None) or {}
    log = [e for e in t.get("log", []) if e["season"] == season]
    if not log and not t.get("shopped"):
        return
    rng = ctx.rng(season, "trades")
    deadline = []
    for e in log:
        a, b = e["teams"]
        if a not in ctx.teams or b not in ctx.teams:
            continue
        cal = _cal(ctx, e)
        if e.get("when") == "Trade deadline":
            deadline.append(e)
        players = [ctx.player(pid) for side in ("a", "b") for pid in e["gave"][side]["players"]]
        players = [p for p in players if p]
        if not players:
            continue
        info = e.get("info", {})
        # The headline player: the best known (by caliber), or the biggest contract.
        star = max(players, key=lambda p: (ctx.caliber(p), info.get(str(p.id), {}).get("cap", 0)))
        s_from = info.get(str(star.id), {}).get("from", a)
        s_to = b if s_from == a else a
        side_star = "a" if s_from == a else "b"
        other = "b" if side_star == "a" else "a"
        cap_share = info.get(str(star.id), {}).get("cap", 0)
        big = ctx.caliber(star) >= 72 or cap_share >= 0.08
        known = ctx.notable(star, s_from) or big
        imp = 22 + (16 if known else 0) + (14 if big else 0) + min(10, 2 * len(players)) + (8 if e.get("user") else 0)
        sent = _side(ctx, e, side_star, s_from)
        got = _side(ctx, e, other, s_to)
        L = ctx.short(star, s_to)
        heads = [f"{ctx.nick(s_from)} trade {pos_abbr(star)} {L} to {ctx.city(s_to)}",
                 f"{L} dealt to the {ctx.nick(s_to)}",
                 f"{ctx.nick(s_to)} land {pos_abbr(star)} {L} in a trade with {ctx.city(s_from)}",
                 f"Trade: {L} heads to {ctx.city(s_to)}",
                 f"{ctx.city(s_from)} moves {pos_abbr(star)} {L}"]
        if e.get("when") == "Trade deadline":
            heads += [f"Deadline deal: {L} to the {ctx.nick(s_to)}", f"{ctx.nick(s_to)} add {L} at the deadline"]
        head = ctx.pick(("trade-head", season, int(cal)), rng, heads)
        age = info.get(str(star.id), {}).get("age")
        open_ = ctx.pick(("trade-open", season, int(cal)), rng, [
            f"The {ctx.full(s_from)} have traded {sent} to the {ctx.full(s_to)} for {got}.",
            f"The {ctx.full(s_to)} have acquired {sent} from the {ctx.full(s_from)}, sending back {got}.",
            f"{star.name} is headed to {ctx.city(s_to)}: the {ctx.nick(s_from)} traded {sent} to the "
            f"{ctx.full(s_to)} for {got}.",
            f"In a trade between the {ctx.full(s_from)} and the {ctx.full(s_to)}, {sent} went to "
            f"{ctx.city(s_to)} and {got} went to {ctx.city(s_from)}."])
        body = [open_]
        inf = info.get(str(star.id), {})
        if age:
            yrs = inf.get("years", 0)
            body.append(f"{star.name} is {age}" + (f" and in his {ORD.get(inf.get('exp', 0) + 1, str(inf.get('exp', 0) + 1))} season"
                                                    if inf.get("exp") is not None and inf.get("exp") < 7 else "")
                        + (f", with {plural(yrs, 'season')} left on his contract" if yrs else "") + ".")
        if inf.get("kind") == "rookie" and star.draft_round == 1:
            body.append(f"He was a first-round pick in {star.draft_year}.")
        ra, rb = _record(ctx, s_to, season, cal), _record(ctx, s_from, season, cal)
        if ra and rb:
            body.append(f"The {ctx.nick(s_to)} are {ra}; the {ctx.nick(s_from)} are {rb}.")
        dead = (e.get("dead") or {}).get(str(s_from))
        from .contracts import cap_for, fmt_money
        if dead and dead >= 0.02 * cap_for(league, season) and inf.get("cap", 0) >= 0.05:
            body.append(f"The {ctx.nick(s_from)} keep {fmt_money(dead)} of his signing bonus on this season's cap.")
        ctx.add(season, cal, "trades", head, " ".join(body), teams=[s_from, s_to], players=[p.id for p in players],
                importance=imp, key=f"trade-{season}-{e['id']}")
        # Bitter: the scoop, the teams, the fans, sometimes the player.
        if known or rng.random() < 0.35:
            ins = ctx.insider(rng)
            short_got = _side(ctx, e, other, s_to, long=False)
            scoop = _fresh(ctx, ("trade-scoop", season, int(cal)), rng, [
                f"Trade: the {ctx.nick(s_to)} are acquiring {pos_abbr(star)} {star.name} from the {ctx.nick(s_from)} for {short_got}, per sources.",
                f"The {ctx.nick(s_from)} are sending {star.name} to {ctx.city(s_to)}. Return: {short_got}.",
                f"Deal done: {star.name} to the {ctx.nick(s_to)}. The {ctx.nick(s_from)} get {short_got}.",
                f"{ctx.nick(s_to)} get {pos_abbr(star)} {star.name}. {ctx.nick(s_from)} get {short_got}. I'm told it's done.",
                f"{star.name} has been traded to the {ctx.full(s_to)}, sources say. The {ctx.nick(s_from)} get {short_got}."])
            sid = ctx.post(season, cal, ins, scoop, teams=[s_from, s_to], players=[star.id], importance=imp - 4,
                           kind="trades")
            from . import bitter
            hello = _fresh(ctx, ("trade-hello", season), rng, [
                f"Welcome to {ctx.city(s_to)}, {star.name}! {bitter.tag(ctx, s_to)}",
                f"We've acquired {pos_abbr(star)} {star.name} from the {ctx.full(s_from)}. {bitter.tag(ctx, s_to)}",
                f"Trade alert: {star.name} is a {ctx.nick(s_to)[:-1] if ctx.nick(s_to).endswith('s') else ctx.nick(s_to)}. {bitter.tag(ctx, s_to)}",
                f"Say hello to {star.name}. {bitter.tag(ctx, s_to)}",
                f"Officially official: {pos_abbr(star)} {star.name} joins the {ctx.nick(s_to)}. {bitter.tag(ctx, s_to)}"])
            if hello and known:
                ctx.post(season, cal, bitter.team_account(ctx, s_to), hello, teams=[s_to], players=[star.id],
                         importance=imp - 8, kind="trades")
            bye = _fresh(ctx, ("trade-bye", season), rng, [
                f"Thank you, {star.name}. Best of luck in {ctx.city(s_to)}.",
                f"{star.name}, thanks for everything you gave this team. {bitter.tag(ctx, s_from)}",
                f"We've traded {pos_abbr(star)} {star.name} to the {ctx.full(s_to)}. Thank you, {star.last_name}."])
            if bye and known and (inf.get("exp", 0) or 0) >= 3:
                ctx.post(season, cal, bitter.team_account(ctx, s_from), bye, teams=[s_from], players=[star.id],
                         importance=imp - 12, kind="trades")
            happy = _fresh(ctx, ("trade-fan-in", season), rng, [
                f"{star.last_name.upper()}! Love this trade.",
                f"Didn't think we'd get {star.last_name}. Front office cooking.",
                f"Finally some help at {POS_WORD.get(star.position, star.position)}.",
                f"Give me {star.last_name} every day. Great pickup.",
                f"I'll take {star.name} for {short_got} all day."])
            if happy and sid:
                ctx.post(season, cal, ctx.fan(s_to, rng, 0), happy, teams=[s_to], players=[star.id], importance=16,
                         reply_to=sid, kind="trades")
            sad = _fresh(ctx, ("trade-fan-out", season), rng, [
                f"{short_got} for {star.last_name}? That's it?",
                f"Gonna miss {star.last_name}. Hope this works out.",
                f"Not sure what the plan is here, but okay.",
                f"Hate to see {star.last_name} go. Understand it though.",
                f"So we're rebuilding. Got it."])
            if sad and sid and known:
                ctx.post(season, cal, ctx.fan(s_from, rng, 1), sad, teams=[s_from], players=[star.id], importance=14,
                         reply_to=sid, kind="trades")
            if known and rng.random() < 0.4:
                me = _fresh(ctx, ("trade-player", season), rng, [
                    f"Grateful for every day in {ctx.city(s_from)}. {ctx.city(s_to)}, let's work.",
                    f"New chapter. Let's go {ctx.nick(s_to)}.",
                    f"{ctx.city(s_from)}, thank you for everything. On to the next.",
                    f"Can't wait to get to work in {ctx.city(s_to)}."])
                if me:
                    who = ctx.player_voice(star)
                    ctx.post(season, cal, (who[0], who[1], who[2], s_to), me, teams=[s_to], players=[star.id],
                             importance=18, kind="trades")
    # The deadline in one story.
    if len(deadline) >= 2:
        cal = _cal(ctx, deadline[0])
        lines = []
        for e in deadline:
            a, b = e["teams"]
            lines.append(f"{ctx.teams[a].abbrev} send {_side(ctx, e, 'a', a, long=False)} to {ctx.teams[b].abbrev} for "
                         f"{_side(ctx, e, 'b', b, long=False)}.")
        ctx.add(season, cal, "trades", f"Trade deadline: {plural(len(deadline), 'deal')} before the bell",
                f"The trade deadline has passed. The deals made on its last day:\n" + "\n".join(lines),
                teams=sorted({t for e in deadline for t in e["teams"]}), importance=46,
                key=f"trade-deadline-{season}")
    # Players you shopped around: the league hears about it.
    for pid, rec in (t.get("shopped") or {}).items():
        if not isinstance(rec, dict) or rec.get("season") != season:
            continue
        p = ctx.player(pid)
        tid = rec.get("team")
        if p is None or tid not in ctx.teams:
            continue
        cal = ctx.label_cal(rec.get("when") or "")
        cal = (cal + 0.2) if cal >= 0 else -3.8
        rumor = _fresh(ctx, ("trade-rumor", season, int(cal)), rng, [
            f"Hearing the {ctx.nick(tid)} are making {p.name} available. Several teams have called.",
            f"The {ctx.nick(tid)} are shopping {pos_abbr(p)} {p.name}, per league sources.",
            f"{p.name} is on the trade block in {ctx.city(tid)}, I'm told.",
            f"Keep an eye on {p.name}: the {ctx.nick(tid)} are listening to offers."])
        if rumor and ctx.notable(p, tid):
            ctx.post(season, cal, ctx.insider(rng), rumor, teams=[tid], players=[p.id], importance=26, kind="trades")


def _fresh(ctx, slot, rng, options):
    used = ctx.__dict__.setdefault("_trade_used", {}).setdefault(slot, set())
    free = [o for o in options if o not in used]
    if not free:
        return None
    o = rng.choice(free)
    used.add(o)
    return o
