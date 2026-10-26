# news_history.py
# News and Bitter bits about the Hall of Fame (engine/hall_of_fame.py, Oct 25):
# the class elected the week of the Glory Bowl, and its enshrinement at the
# Hall of Fame Game the next summer. news.py calls hall_of_fame_news() for each
# season. Everything comes from the vote records and the players' careers.

from . import hall_of_fame as HOF
from .news import POS_WORD, join_and

NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
ORD = {2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth",
       10: "10th"}


def _ballot_words(n):
    return "on his first ballot" if n == 1 else f"in his {ORD.get(n, f'{n}th')} year on the ballot"


def _career_words(ctx, p, r):
    teams = [ctx.teams[t].nickname for t in r["teams"][:2] if t in ctx.teams]
    years = f"{r['first']}-{r['last']}" if r["first"] else ""
    honors = []
    if r["ap1"] + r.get("ap1_spec", 0):
        n = r["ap1"] + r.get("ap1_spec", 0)
        honors.append(f"{n}-time first-team All-Pro" if n > 1 else "a first-team All-Pro")
    if r["pb"]:
        honors.append(f"{r['pb']}-time Pro Bowler" if r["pb"] > 1 else "a Pro Bowler")
    awards = [name for _s, name in r["awards"]]
    if "Most Valuable Player" in awards:
        k = awards.count("Most Valuable Player")
        honors.append(f"{k}-time MVP" if k > 1 else "an MVP")
    if r["titles"]:
        honors.append(f"{len(r['titles'])}-time champion" if len(r["titles"]) > 1 else "a champion")
    return (f"{POS_WORD.get(p.position, p.position)} {p.name} ({' and '.join(teams)}, {years})",
            join_and(honors) if honors else "")


def hall_of_fame_news(ctx, season):
    league = ctx.league
    b = HOF.ballot(league, season)
    if b and any(x[3] for x in b["ballot"]):
        _class_elected(ctx, season, b)
    prev = HOF.ballot(league, season - 1)
    if prev and any(x[3] for x in prev["ballot"]):
        _enshrined(ctx, season, prev)


def _class_elected(ctx, season, b):
    cal = 5 + ctx.n_weeks + 5 + 0.15         # the week of the Glory Bowl, with the season awards
    rng = ctx.rng(season, "hof")
    elected = [(ctx.player(pid), votes, ballot_no) for pid, votes, ballot_no, ok in b["ballot"] if ok]
    elected = [e for e in elected if e[0] is not None]
    if not elected:
        return
    lines, teams = [], []
    for p, votes, ballot_no in elected:
        r = HOF.resume(ctx.league, p.id)
        who, honors = _career_words(ctx, p, r)
        line = (f"{who}" + (f", {honors}," if honors else "") + f" got {votes} of {HOF.VOTERS} votes "
                f"{_ballot_words(ballot_no)}.")
        lines.append(line[0].upper() + line[1:])
        teams += r["teams"][:2]
    names = join_and([p.name for p, _v, _b in elected])
    year = b["class_of"]
    head = ctx.pick(("hofhead", season), rng, [f"Hall of Fame Class of {year}: {names}",
                                               f"{names} elected to the Hall of Fame",
                                               f"Hall calls: {names}"])
    if len(head) > 95:
        head = f"Hall of Fame elects a Class of {year} of {len(elected)}"
    missed = [(ctx.player(pid), votes) for pid, votes, _bn, ok in b["ballot"] if not ok and ctx.player(pid)]
    near = ""
    if missed and missed[0][1] >= 30:
        p, votes = missed[0]
        need = round(HOF.NEEDED * HOF.VOTERS)
        near = (f" {p.name} came closest of the rest with {votes} votes, {need - votes} short."
                if votes < need else f" {p.name} also reached {votes} votes but waits a year: "
                                     f"the Hall takes at most {HOF.CLASS_LIMIT} a year.")
    count = NUMBER.get(len(elected), str(len(elected)))
    lead = (f"The {HOF.VOTERS}-member selection committee elected {count} "
            f"{'player' if len(elected) == 1 else 'players'} to the Hall of Fame as the Class of {year}. ")
    ctx.add(season, cal, "awards", head, lead + " ".join(lines) + near
            + (" He'll" if len(elected) == 1 else " They'll") + " be enshrined the week of next summer's Hall of "
            "Fame Game.", teams=list(dict.fromkeys(teams)),
            players=[p.id for p, _v, _b in elected], importance=78, key=f"hof-{season}")
    ctx.post(season, cal, ctx.stat_desk(), f"Hall of Fame Class of {year}: "
             + "; ".join(f"{p.name} ({p.position}, {votes}/{HOF.VOTERS} votes)" for p, votes, _b in elected),
             teams=list(dict.fromkeys(teams)), players=[p.id for p, _v, _b in elected], importance=55)
    for p, votes, ballot_no in elected:
        r = HOF.resume(ctx.league, p.id)
        if not r["teams"] or r["teams"][0] not in ctx.teams:
            continue
        tid = r["teams"][0]
        text = (f"{p.name} is a Hall of Famer{' on the first ballot' if ballot_no == 1 else ''}. "
                f"{r['seasons']} seasons, and the {ctx.teams[tid].nickname} got the best of them. Canton calls.")
        ctx.post(season, cal + 0.01, ctx.beat(tid), text, teams=[tid], players=[p.id], importance=40)


def _enshrined(ctx, season, b):
    cal = 1.2                                # Hall of Fame Game week, the summer after the vote
    elected = [ctx.player(pid) for pid, _v, _bn, ok in b["ballot"] if ok]
    elected = [p for p in elected if p is not None]
    if not elected:
        return
    year = b["class_of"]
    teams = []
    for p in elected:
        teams += HOF.resume(ctx.league, p.id)["teams"][:1]
    ctx.add(season, cal, "awards", f"Class of {year} enshrined in the Hall of Fame",
            f"{join_and([p.name for p in elected])} "
            + ("took his place in the Hall of Fame before the Hall of Fame Game: the gold jacket, and his bust "
               "unveiled." if len(elected) == 1 else "took their places in the Hall of Fame before the Hall of "
                                                     "Fame Game, in gold jackets, with their busts unveiled."),
            teams=list(dict.fromkeys(teams)), players=[p.id for p in elected], importance=55,
            key=f"hof-enshrined-{season}")
