# news_money.py
# News about the league's money (engine/league_money.py, Oct 24): each league
# year's salary cap, new TV deals, labor deals and revenue shocks. Kept apart
# from news.py, which calls money_news() for each season while it builds the
# news. Everything comes from the league's own records (league.cap_history and
# league.tv); nothing is saved here.

from . import contracts as C
from . import league_money as LM

CAL = -4          # the start of the league year (March), before the retirements and the draft


def _pct(x):
    return f"{x * 100:.1f}%"


def _cap(k):
    """A cap figure the way the league announces it: '$301.2M', '$1.17B'."""
    return f"${k / 1000:.1f}M" if k < 999_500 else C.fmt_money(k)


def money_news(ctx, season):
    """Stories for league year `season` (seasons after the league's first; the
    first starts at training camp)."""
    league = ctx.league
    if season <= ctx.first or season not in league.cap_history:
        return
    tv = LM.ensure(league)
    cap, prev = league.cap_history[season], C.cap_for(league, season - 1)
    change = cap / prev - 1
    rng = ctx.rng(season, "money")
    # 1. The cap for the new league year.
    deal = next((d for d in tv["deals"] if d["start"] == season and not d.get("real")), None)
    labor = next((d for d in tv["labor"] if d["start"] == season and not d.get("real")), None)
    shock = tv["shocks"].get(season)
    if change >= 0:
        head = ctx.pick(("cap", season), rng, [f"Salary cap set at {_cap(cap)} for {season}",
                                               f"{season} salary cap: {_cap(cap)}, up {_pct(change)}"])
        body = (f"The league has told its teams the {season} salary cap is {_cap(cap)}, "
                f"up {C.fmt_money(cap - prev)} ({_pct(change)}) from last year's {_cap(prev)}.")
    else:
        head = f"Salary cap falls to {_cap(cap)} for {season}"
        body = (f"The league has told its teams the {season} salary cap is {_cap(cap)}, "
                f"down {C.fmt_money(prev - cap)} ({_pct(-change)}) from last year's {_cap(prev)}.")
    if shock is not None:
        body += " The drop comes from last year's fall in league revenue; the lost money is expected back over the next two seasons."
    elif deal:
        body += f" It's the first year of the new TV deals, and the new money shows."
    elif labor and labor["kind"] == "owners":
        body += " The new labor deal gives the owners a bigger share, and the cap grows slowly while it takes effect."
    elif change >= 0.11:
        body += " It's one of the biggest jumps in league history, and teams across the league have room to spend."
    elif change < 0.03:
        body += " Teams near the cap will have to cut or restructure before free agency opens."
    nxt = tv["proj"].get(season + 1)
    if nxt:
        body += f" Teams were told to expect about {_cap(nxt)} for {season + 1}."
    imp = 30 + (15 if change >= 0.11 or change < 0.02 else 0)
    ctx.add(season, CAL, "business", head, body, importance=imp, key=f"cap-{season}")
    # 2. A TV deal signed this league year.
    for d in tv["deals"]:
        if d.get("signed") != season or d.get("real"):
            continue
        value = d.get("value_k") or LM.tv_value_per_year(C.cap_for(league, d["start"]))
        more = value / LM.tv_value_per_year(cap) - 1      # vs what the current deals pay this year
        word = LM.buzz_word(d.get("buzz", 0))
        head = ctx.pick(("tv", season), rng, [f"League signs new TV deals worth about {C.fmt_money(value)} a year",
                                              f"New TV deals: about {C.fmt_money(value)} a year from {d['start']}"])
        body = (f"The league has signed new TV deals that start in {d['start']} and run through {d['end']}, "
                f"worth about {C.fmt_money(value)} a year, "
                + (f"{_pct(more)} more than the current deals pay." if more >= 0
                   else f"{_pct(-more)} less than the current deals pay."))
        body += {"booming": " With ratings booming after close races and record-setting seasons, the networks paid up.",
                 "strong": " Strong ratings in recent seasons helped push the price up.",
                 "soft": " Ratings had softened in recent seasons, and the networks paid accordingly.",
                 "slumping": " With ratings slumping, the league took less than it hoped for.",
                 "steady": ""}[word]
        if d["jump"] >= 0.12:
            body += f" Teams expect a big jump in the cap in {d['start']}."
        elif d["jump"] < 0.03:
            body += " The cap won't get much of a boost from them."
        ctx.add(season, CAL, "business", head, body, importance=45 + (10 if d["jump"] >= 0.15 else 0),
                key=f"tv-{d['start']}")
    # 3. A labor deal agreed this league year (it starts next season).
    for d in tv["labor"]:
        if d.get("signed") != season or d.get("real"):
            continue
        heads = {"owners": "Owners win a bigger share in a new labor deal",
                 "smooth": "League and players agree to a new labor deal",
                 "players": "Players win a bigger share in a new labor deal"}
        texts = {"owners": " After hard bargaining, the players' share of revenue goes down: expect the cap to grow slowly for a few years.",
                 "smooth": " The players' share of revenue stays about where it was.",
                 "players": " The players' share of revenue goes up, so the cap gets a boost in the first year."}
        body = (f"The league and the players' union have agreed to a new labor deal for {d['start']} through {d['end']}."
                + texts[d["kind"]])
        ctx.add(season, CAL, "business", heads[d["kind"]], body, importance=40, key=f"labor-{d['start']}")
    # 4. A shock announced this league year (next season's cap drops).
    g = tv["shocks"].get(season + 1)
    if g is not None:
        body = (f"League revenue has fallen sharply, and teams have been told the {season + 1} salary cap will drop "
                f"by about {_pct(-g)}. Teams with big contracts will have to cut or restructure; the lost money "
                "is expected back over the following seasons.")
        ctx.add(season, CAL, "business", f"League revenue falls: the {season + 1} cap will drop", body,
                importance=55, key=f"shock-{season + 1}")
