# news_finances.py
# News about the teams' business (engine/finances.py, Oct 26): ticket prices for the
# new season (the big raises, the freezes, yours), empty seats during the season, and
# the yearly team values list. Kept apart from news.py, which calls finance_news() for
# each season while it builds the news. Everything comes from league.finances; nothing
# is saved here.

from . import finances as F
from . import formatting as fmt

CAL_PRICES = -3       # ticket prices go out before free agency (FOF8's order too)
CAL_VALUES = 0.5      # the yearly team values (the real Forbes list comes out in August)
BIG_RAISE = 0.12      # a raise this big is news
EMPTY = 0.85          # a home game this far from full is news


def _fresh(ctx, slot, rng, options):
    """One of the options not used yet in this slot this season, or None."""
    used = ctx.__dict__.setdefault("_fin_used", {}).setdefault(slot, set())
    free = [o for o in options if o not in used]
    if not free:
        return None
    o = rng.choice(free)
    used.add(o)
    return o


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _record(league, tid, season):
    r = next((x for x in league.team_history if x["team"] == tid and x["season"] == season), None)
    if not r:
        return None, ""
    g = r["w"] + r["l"] + r["t"]
    return ((r["w"] + 0.5 * r["t"]) / g if g else 0.5), f'{r["w"]}-{r["l"]}' + (f'-{r["t"]}' if r["t"] else "")


def finance_news(ctx, season):
    league = ctx.league
    fin = getattr(league, "finances", None)
    if not fin or not fin.get("teams"):
        return
    rng = ctx.rng(season, "finances")
    _prices(ctx, season, fin, rng)
    _empty_seats(ctx, season, fin, rng)
    _values(ctx, season, fin)


def _prices(ctx, season, fin, rng):
    league = ctx.league
    now, before = fin["prices"].get(season), fin["prices"].get(season - 1)
    if not now or not before:
        return
    changes = {tid: now[tid]["general"] / before[tid]["general"] - 1 for tid in now if tid in before and tid in ctx.teams}
    if not changes:
        return
    avg = sum(changes.values()) / len(changes)
    raisers = sorted((t for t, c in changes.items() if c >= BIG_RAISE), key=lambda t: -changes[t])
    frozen = [t for t, c in changes.items() if abs(c) < 0.005]
    cut = [t for t, c in changes.items() if c <= -0.005]
    # The league-wide roundup.
    body = (f"Teams have set their ticket prices for {season}: the average regular seat goes up "
            f"{avg * 100:.1f}%, to about {fmt.price(sum(now[t]['general'] for t in changes) / len(changes))} a game.")
    if raisers:
        names = ", ".join(f"the {ctx.nick(t)} ({changes[t] * 100:+.0f}%)" for t in raisers[:3])
        body += f" The biggest raises: {names}."
    if frozen:
        body += f" {len(frozen)} {'team is' if len(frozen) == 1 else 'teams are'} holding prices where they were."
    if cut:
        body += f" {', '.join('the ' + ctx.nick(t) for t in cut[:2])} cut prices."
    ctx.add(season, CAL_PRICES, "business", f"Ticket prices up {avg * 100:.1f}% around the league for {season}", body,
            teams=raisers[:3], importance=27, key=f"prices-{season}")
    # The big raises: after a good season fans grumble and pay; after a bad one they're angry.
    for tid in raisers[:3]:
        wp, rec = _record(league, tid, season - 1)
        if wp is None:
            continue
        c = changes[tid]
        head = f"{ctx.teams[tid].name} raise ticket prices {c * 100:.0f}%"
        if wp >= 0.6:
            body = (f"Coming off a {rec} season, the {ctx.nick(tid)} are raising the average regular seat "
                    f"{c * 100:.0f}% to {fmt.price(now[tid]['general'])}. Demand is up, and the team is pricing to it.")
            fan_txt = _fresh(ctx, ("raise-good", season), rng, [
                f"{c * 100:.0f}% more. Worth it if we keep winning.", "They know we'll pay. We will.",
                f"{fmt.price(now[tid]['general'])} a seat. Winning isn't cheap, I guess."])
        else:
            body = (f"After a {rec} season, the {ctx.nick(tid)} are raising the average regular seat "
                    f"{c * 100:.0f}% to {fmt.price(now[tid]['general'])}, and season-ticket holders aren't happy.")
            fan_txt = _fresh(ctx, ("raise-bad", season), rng, [
                f"{rec} and they raise prices {c * 100:.0f}%? Bold.", "Paying more to watch the same team. Great.",
                f"{fmt.price(now[tid]['general'])} to watch this? Not renewing."])
        ctx.add(season, CAL_PRICES, "business", head, body, teams=[tid], importance=22 + (8 if tid == league.user_team_id else 0),
                key=f"raise-{season}-{tid}")
        if fan_txt:
            ctx.post(season, CAL_PRICES, ctx.fan(tid, rng, 0 if wp >= 0.6 else 1), fan_txt, teams=[tid],
                     importance=18, kind="business")
    # Your prices, if you set them yourself and they're not already in the stories above.
    mine = league.user_team_id
    if mine in changes and now[mine].get("set_by") == "you" and mine not in raisers[:3]:
        c = changes[mine]
        word = "raise" if c > 0.005 else "cut" if c < -0.005 else "hold"
        head = {"raise": f"{ctx.teams[mine].name} raise ticket prices {c * 100:.0f}%",
                "cut": f"{ctx.teams[mine].name} cut ticket prices {-c * 100:.0f}%",
                "hold": f"{ctx.teams[mine].name} hold ticket prices for {season}"}[word]
        body = (f"The average regular seat will cost {fmt.price(now[mine]['general'])} a game this season"
                + ("." if word == "hold" else f", {'up' if c > 0 else 'down'} from {fmt.price(before[mine]['general'])}."))
        ctx.add(season, CAL_PRICES, "business", head, body, teams=[mine], importance=30, key=f"yourprices-{season}")


def _empty_seats(ctx, season, fin, rng):
    """The emptiest home game of each team that had one well short of full (the
    game-by-game detail is kept for this season and last)."""
    league = ctx.league
    games = fin["games"].get(season) or {}
    worst = {}
    for gid, r in games.items():
        if r["kind"] != "regular" or r["home"] not in ctx.teams:
            continue
        share = r["att"] / r["capacity"]
        if share < EMPTY and (r["home"] not in worst or share < worst[r["home"]][0]):
            worst[r["home"]] = (share, r)
    for tid, (share, r) in sorted(worst.items(), key=lambda kv: kv[1][0])[:4]:
        cal = 5 + r["week"]
        opp = ctx.teams.get(r["away"])
        head = f"Empty seats for the {ctx.nick(tid)}: {fmt.crowd(r['att'])} at home"
        body = (f"The {ctx.nick(tid)} drew {fmt.crowd(r['att'])} against the {ctx.nick(r['away']) if opp else 'visitors'}, "
                f"{share * 100:.0f}% of a {fmt.crowd(r['capacity'])}-seat stadium, with regular seats at "
                f"{fmt.price(r['price'])}.")
        ctx.add(season, cal, "business", head, body, teams=[tid], importance=20 + (10 if tid == league.user_team_id else 0),
                key=f"empty-{season}-{tid}")
        fan_txt = _fresh(ctx, ("empty", season), rng, [
            "Plenty of good seats still available.", f"{share * 100:.0f}% full. Can't blame anyone at these prices.",
            "You could hear the vendors from the upper deck.", "Lower the prices or win some games. Pick one."])
        if fan_txt:
            ctx.post(season, cal, ctx.fan(tid, rng, 2), fan_txt, teams=[tid], importance=16, kind="business")


def _values(ctx, season, fin):
    """The yearly list of team values (last season's books), at training camp."""
    books = fin["books"].get(season - 1)
    if not books:
        return
    rows = sorted(((r.get("value") or 0, tid) for tid, r in books.items() if tid in ctx.teams), reverse=True)
    if not rows:
        return
    top = rows[:3]
    avg_v = sum(v for v, _ in rows) / len(rows)
    avg_rev = sum(books[t]["revenue"] for _, t in rows) / len(rows)
    losers = [t for _, t in rows if books[t]["profit"] < 0]
    body = (f"The {ctx.nick(top[0][1])} are the league's most valuable team at about {fmt.money(top[0][0])}, "
            f"ahead of the {ctx.nick(top[1][1])} ({fmt.money(top[1][0])}) and the {ctx.nick(top[2][1])} "
            f"({fmt.money(top[2][0])}). The average team is worth about {fmt.money(avg_v)} on "
            f"{fmt.money(avg_rev)} in revenue last season; the {ctx.nick(rows[-1][1])} rank last at "
            f"{fmt.money(rows[-1][0])}.")
    if losers:
        body += (f" {len(losers)} {'team' if len(losers) == 1 else 'teams'} lost money last season"
                 f" ({', '.join('the ' + ctx.nick(t) for t in losers[:3])}).")
    mine = ctx.league.user_team_id
    if mine in books:
        rank = next(i for i, (_, t) in enumerate(rows, start=1) if t == mine)
        body += f" The {ctx.nick(mine)} rank {_ordinal(rank)} at {fmt.money(books[mine].get('value') or 0)}."
    ctx.add(season, CAL_VALUES, "business", f"Team values: the {ctx.nick(top[0][1])} lead at {fmt.money(top[0][0])}",
            body, teams=[top[0][1]], importance=28, key=f"values-{season}")
