# news_awards.py
# News stories and social posts about the league's awards and the Pro Bowl
# (engine/awards.py), for the News tab. Kept apart from news.py, which calls
# awards_news() for each season while it builds the news; it uses news.py's
# word helpers and its builder (ctx). Like the rest of the news, everything
# comes from the league's records: who won, the votes, the stats they were
# voted on. Nothing is invented and no ratings are mentioned.

from collections import defaultdict

from . import awards as A
from . import playoffs as po
from . import season as S
from .news import (POS_WORD, _f, game_phrase, join_and, num, phrase, plural, pos_abbr, sacks_text, stat_line, yds)
from .news_words import Say


# ---------------------------------------------------------------------------
# Awards and the Pro Bowl (engine/awards.py, Oct 23). Everything here comes
# from the league's award records: who won, the votes, the stats they were
# voted on. The calendar follows the real NFL: Players of the Week after each
# week, Players of the Month, the MVP race, Pro Bowl rosters before the last
# week, All-Pro at the start of the playoffs, Pro Bowl changes once the
# Glory Bowl teams are set, the Pro Bowl in the week off, the season awards
# the week of the Glory Bowl, the Glory Bowl MVP after it.
# ---------------------------------------------------------------------------

def _yds_word(n):
    return f"{int(round(n)):,}"


def season_phrase(p, s, games=None):
    """His season (or month) in words, by position: 'threw for 4,812 yards,
    38 touchdowns and nine interceptions'."""
    g = A.group_of(p.position)
    if g == "QB" and _f(s, "pass_att") >= 20:
        ints = _f(s, "pass_int")
        bits = [f"threw for {_yds_word(_f(s, 'pass_yds'))} yards, {plural(_f(s, 'pass_td'), 'touchdown')} "
                f"and {plural(ints, 'interception') if ints else 'no interceptions'}"]
        if _f(s, "rush_yds") >= 250 or _f(s, "rush_td") >= 5:
            bits.append(f"ran for {_yds_word(_f(s, 'rush_yds'))} yards" +
                        (f" and {plural(_f(s, 'rush_td'), 'score')}" if _f(s, "rush_td") else ""))
        return join_and(bits)
    if g in ("RB", "FB") and (_f(s, "rush_att") >= 20 or _f(s, "rec") >= 15):
        bits = []
        if _f(s, "rush_att") >= 20:
            bits.append(f"ran for {_yds_word(_f(s, 'rush_yds'))} yards and {plural(_f(s, 'rush_td'), 'touchdown')}")
        if _f(s, "rec") >= 15:
            bits.append(f"caught {plural(_f(s, 'rec'), 'pass', 'passes')} for {_yds_word(_f(s, 'rec_yds'))} yards")
        return join_and(bits)
    if g in ("WR", "TE", "RB") and _f(s, "rec"):
        return (f"caught {plural(_f(s, 'rec'), 'pass', 'passes')} for {_yds_word(_f(s, 'rec_yds'))} yards and "
                f"{plural(_f(s, 'rec_td'), 'touchdown')}")
    if g in A.DEFENSE_GROUPS:
        bits = []
        tk = _f(s, "tkl") + _f(s, "ast")
        if _f(s, "sacks") >= 1:
            bits.append(f"had {sacks_text(_f(s, 'sacks'))}")
        if _f(s, "def_int"):
            bits.append(f"{plural(_f(s, 'def_int'), 'interception')}")
        if tk >= 60 or g in ("LB",) or not bits:
            bits.append(f"{plural(tk, 'tackle')}")
        if _f(s, "ff") >= 2:
            bits.append(f"{plural(_f(s, 'ff'), 'forced fumble')}")
        if _f(s, "pd") >= 10:
            bits.append(f"{num(_f(s, 'pd'))} passes defensed")
        if _f(s, "def_td"):
            bits.append(f"{plural(_f(s, 'def_td'), 'defensive touchdown')}")
        text = join_and(bits)
        return text if text.startswith("had") else "had " + text
    if p.position == "K" and _f(s, "fga"):
        return (f"made {int(_f(s, 'fgm'))} of {int(_f(s, 'fga'))} field goals"
                + (f", the longest from {int(_f(s, 'fg_long'))} yards" if _f(s, "fgm") else ""))
    if p.position == "P" and _f(s, "punts"):
        return (f"averaged {_f(s, 'punt_yds') / _f(s, 'punts'):.1f} yards on {plural(_f(s, 'punts'), 'punt')}, "
                f"with {num(_f(s, 'punt_in20'))} inside the 20")
    if _f(s, "kr") + _f(s, "pr") >= 10:
        td = _f(s, "kr_td") + _f(s, "pr_td")
        return (f"returned {plural(_f(s, 'kr') + _f(s, 'pr'), 'kick')} for {_yds_word(_f(s, 'kr_yds') + _f(s, 'pr_yds'))}"
                f" yards" + (f" and {plural(td, 'touchdown')}" if td else ""))
    if _f(s, "st_tkl") >= 3:
        return f"made {plural(_f(s, 'st_tkl'), 'tackle')} on special teams"
    gp = int(_f(s, "gp"))
    if gp:
        return f"played in {'all ' + num(gp) if games and gp >= games else num(gp)} games"
    return "played a key role all season"


def _st_game_phrase(s, rng):
    bits = []
    if _f(s, "fga"):
        bits.append(f"made {int(_f(s, 'fgm'))} of {int(_f(s, 'fga'))} field goals" +
                    (f", the longest from {int(_f(s, 'fg_long'))} yards" if _f(s, "fgm") else ""))
    if _f(s, "kr_td") or _f(s, "pr_td"):
        bits.append(phrase(s, "ret", rng))
    elif _f(s, "kr") + _f(s, "pr") >= 2 and _f(s, "kr_yds") + _f(s, "pr_yds") >= 60:
        bits.append(f"returned {plural(_f(s, 'kr') + _f(s, 'pr'), 'kick')} for "
                    f"{yds(_f(s, 'kr_yds') + _f(s, 'pr_yds'))}")
    if _f(s, "punts") >= 3:
        bits.append(f"averaged {_f(s, 'punt_yds') / _f(s, 'punts'):.1f} yards on {plural(_f(s, 'punts'), 'punt')}"
                    + (f", {num(_f(s, 'punt_in20'))} inside the 20" if _f(s, "punt_in20") else ""))
    return join_and(bits) or "made the plays on special teams"


def _who(ctx, pid, tid):
    """'QB John Smith (BOS)' and the player."""
    p = ctx.player(pid)
    if p is None:
        return "", None
    return f"{pos_abbr(p)} {p.name} ({ctx.teams[tid].abbrev})", p


def _week_cal(w):
    return 5 + w + 0.6


def awards_news(ctx, season):
    league = ctx.league
    aw = getattr(league, "awards", None)
    if not aw:
        return
    A.ensure(league)
    n = ctx.n_weeks
    _news_weekly(ctx, season)
    _news_monthly(ctx, season)
    _news_mvp_watch(ctx, season)
    _news_pro_bowl(ctx, season, n)
    _news_all_pro(ctx, season, n)
    _news_pro_bowl_game(ctx, season, n)
    _news_season_awards(ctx, season, n)
    _news_gb_mvp(ctx, season, n)


def _news_weekly(ctx, season):
    rows = A.records(ctx.league, "weekly", season)
    by = defaultdict(dict)
    for r in rows:
        by[(r["week"], r["conf"])][r["kind"]] = r
    for (week, conf), kinds in sorted(by.items()):
        rng = ctx.rng(season, "pow", week, conf)
        cal = _week_cal(week)
        sents, names, players, teams, by_pid = [], [], [], [], {}
        for kind in ("off", "def", "st"):
            r = kinds.get(kind)
            if not r:
                continue
            who, p = _who(ctx, r["pid"], r["team"])
            if p is None:
                continue
            s = r["line"]
            res = (f"a {r['pf']}-{r['pa']} win over" if r["pf"] > r["pa"] else
                   f"a {r['pa']}-{r['pf']} loss to" if r["pf"] < r["pa"] else f"a {r['pf']}-{r['pa']} tie with")
            if kind == "st":
                what = _st_game_phrase(s, rng)
            else:
                what = game_phrase(s, rng, 3 if kind == "off" else 2) or ("made the plays on defense" if kind == "def"
                                                                          else "led the offense")
            sents.append(f"{A.WEEKLY_KINDS[kind].replace('Special Teams', 'Special teams')}: {who} {what} in "
                         f"{res} the {ctx.full(r['opp'])}.")
            names.append(ctx.short(p, r["team"]))
            players.append(p.id)
            teams.append(r["team"])
            by_pid[p.id] = r
        if not names:
            continue
        head = ctx.pick(("powhead", season, conf), rng, [
            f"{conf} Conference Players of the Week: {join_and(names)}",
            f"{join_and(names)} named {conf} Conference Players of the Week",
            f"Week {week} honors in the {conf}: {join_and(names)}"])
        ctx.add(season, cal, "awards", head, f"The league's {conf} Conference Players of the Week for Week {week}.\n"
                + "\n".join(sents), teams=teams, players=players, importance=36, key=f"pow-{season}-{week}-{conf}")
        picked = [(k, ctx.player(kinds[k]["pid"]), kinds[k]["team"]) for k in ("off", "def", "st")
                  if k in kinds and ctx.player(kinds[k]["pid"])]
        side = {"off": "offense", "def": "defense", "st": "special teams"}
        ctx.post(season, cal, ctx.stat_desk(), Say("stat_pow", {
            "conf": conf, "week": week,
            "who": "; ".join(f"{side[k].capitalize()} {q.name}" for k, q, _t in picked),
            "who2": join_and([f"{q.name} ({side[k]})" for k, q, _t in picked]),
            "who3": join_and([f"{pos_abbr(q)} {q.name} of {ctx.city(t)}" for _k, q, t in picked])}),
            teams=teams, players=players, importance=32)
        for pid, tid in zip(players, teams):
            prng = ctx.rng(season, "powpost", week, pid)
            if prng.random() < 0.3:
                r = by_pid[pid]
                ctx.post(season, cal, ctx.player_voice(ctx.player(pid)), Say("player_pow", {
                    "week": week, "opp": ctx.nick(r["opp"]), "score": f"{max(r['pf'], r['pa'])}-{min(r['pf'], r['pa'])}",
                    "won": r["pf"] > r["pa"], "lost": r["pf"] < r["pa"]}), teams=[tid], players=[pid], importance=22)


def _news_monthly(ctx, season):
    rows = A.records(ctx.league, "monthly", season)
    by = defaultdict(list)
    for r in rows:
        by[r["month"]].append(r)
    label = {"off": "offense", "def": "defense", "st": "special teams"}
    for month, rs in by.items():
        last_week = max(r["weeks"][1] for r in rs)
        cal = _week_cal(last_week) + 0.05
        rng = ctx.rng(season, "month", month)
        lines, players, teams, heads = [], [], [], []
        for r in sorted(rs, key=lambda r: (r["conf"] or "~", ["off", "def", "st", "orook", "drook"].index(r["kind"]))):
            who, p = _who(ctx, r["pid"], r["team"])
            if p is None:
                continue
            rec = f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
            if r["conf"]:
                tag = f"{r['conf']} {label[r['kind']]}"
            else:
                tag = "Offensive Rookie of the Month" if r["kind"] == "orook" else "Defensive Rookie of the Month"
            lines.append(f"{tag}: {who} {season_phrase(p, r['line'])} as the {ctx.nick(r['team'])} went {rec}.")
            players.append(p.id)
            teams.append(r["team"])
            if r["kind"] in ("off", "def"):
                heads.append(ctx.short(p, r["team"]))
        if not lines:
            continue
        ctx.add(season, cal, "awards", ctx.pick(("monthhead", season), rng, [
            f"{month} Players of the Month: {join_and(heads[:4])}",
            f"{join_and(heads[:4])} lead {month} honors"]),
            f"The league's Players of the Month for {month}" +
            (" (and the first week of January)" if month == "December" and last_week >= ctx.n_weeks - 1 else "") +
            ".\n" + "\n".join(lines), teams=teams, players=players, importance=40, key=f"month-{season}-{month}")


def _news_mvp_watch(ctx, season):
    for r in A.records(ctx.league, "mvp_watch", season):
        week = r["week"]
        cal = _week_cal(week) + 0.1
        rng = ctx.rng(season, "watch", week)
        lines, players, teams = [], [], []
        for i, (pid, tid, line, rec) in enumerate(r["top"], start=1):
            who, p = _who(ctx, pid, tid)
            if p is None:
                continue
            w, l, t = rec
            lines.append(f"{i}. {who}, {w}-{l}" + (f"-{t}" if t else "") + f": {season_phrase(p, line)}.")
            players.append(pid)
            teams.append(tid)
        if not players:
            continue
        lead = ctx.player(players[0])
        ctx.add(season, cal, "awards", ctx.pick(("watchhead", season), rng, [
            f"MVP watch after Week {week}: {ctx.short(lead, teams[0])} leads the race",
            f"MVP race, Week {week}: {ctx.short(lead, teams[0])} on top",
            f"Who's the MVP after Week {week}? The case for {ctx.short(lead, teams[0])}"]),
            f"How the MVP race looks to the league's media after Week {week} (stats and records through Week {week}; "
            f"the vote comes after the season):\n" + "\n".join(lines), teams=teams, players=players,
            importance=44, key=f"watch-{season}-{week}")
        names = [ctx.player(pid).last_name for pid in players[:3]]
        ctx.post(season, cal, ctx.insider(rng), Say("ins_mvp_ballot", {
            "week": week, "list": " ".join(f"{i}. {nm}" for i, nm in enumerate(names, start=1)),
            "first": names[0], "rest": join_and(names[1:]), "two": len(names) >= 2,
            "lead_city": ctx.city(teams[0])}), teams=teams[:3], players=players[:3], importance=36)


_OUT_WHY = {"injured": "is injured", "declined": "will not play"}


def _news_pro_bowl(ctx, season, n):
    league = ctx.league
    rows = A.records(league, "pro_bowl", season)
    if not rows:
        return
    cal = _week_cal(n - 1) + 0.2
    for conf in sorted({r["conf"] for r in rows}):
        rng = ctx.rng(season, "pbroster", conf)
        lines = []
        for spot, label, *_rest in A.PRO_BOWL_SPOTS:
            picks = sorted((r for r in rows if r["conf"] == conf and r["spot"] == spot and r["role"] == "selected"),
                           key=lambda r: r["rank"])
            if picks:
                lines.append(f"{label}: " + ", ".join(
                    f"{ctx.player(r['pid']).name} ({ctx.teams[r['team']].abbrev})" + (" (starter)" if r["starter"]
                                                                                      and len(picks) > 1 else "")
                    for r in picks if ctx.player(r["pid"])) + ".")
        sel = [r for r in rows if r["conf"] == conf and r["role"] == "selected"]
        qb = next((r for r in sel if r["spot"] == "QB" and r["starter"]), None)
        head = f"{conf} Conference Pro Bowl roster announced"
        if qb and ctx.player(qb["pid"]):
            head = ctx.pick(("pbhead", season), rng, [
                f"{conf} Pro Bowl roster set; {ctx.short(ctx.player(qb['pid']), qb['team'])} to start at quarterback",
                f"{ctx.short(ctx.player(qb['pid']), qb['team'])} leads the {conf} Conference's Pro Bowl picks"])
        ctx.add(season, cal, "awards", head,
                f"The {conf} Conference's {len(sel)} Pro Bowl players for {season}, voted by fans, players and "
                f"coaches (each a third of the vote). Starters are the top vote-getters at each position.\n"
                + "\n".join(lines), teams=sorted({r["team"] for r in sel}), players=[r["pid"] for r in sel],
                importance=55, key=f"pbroster-{season}-{conf}")
    # Each team's Pro Bowlers (team news).
    by_team = defaultdict(list)
    for r in rows:
        if r["role"] == "selected":
            by_team[r["team"]].append(r)
    for tid, rs in by_team.items():
        ps = [ctx.player(r["pid"]) for r in rs]
        ps = [p for p in ps if p]
        if not ps:
            continue
        rng = ctx.rng(season, "pbteam", tid)
        names = join_and([f"{pos_abbr(p)} {p.name}" for p in ps])
        ctx.add(season, cal, "awards",
                f"{num(len(ps)).capitalize()} Pro Bowlers for the {ctx.full(tid)}"
                if len(ps) > 1 else f"{ctx.short(ps[0], tid)} named to the Pro Bowl",
                f"{names} {'was' if len(ps) == 1 else 'were'} named to the {season} Pro Bowl"
                f" for the {ctx.full(tid)}.", teams=[tid], players=[p.id for p in ps],
                # Team news only (under the league view's 25): league-wide, the two conference
                # roster stories already list everyone.
                importance=18 + min(len(ps), 5), key=f"pbteam-{season}-{tid}")
        for p in ps:
            prng = ctx.rng(season, "pbpost", p.id)
            if prng.random() < 0.35:
                ctx.post(season, cal, ctx.player_voice(p), Say("player_probowl", {
                    "season": season, "city": ctx.city(tid)}), teams=[tid], players=[p.id], importance=24)
        if rng.random() < 0.5:
            ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_probowl", {
                "n": num(len(ps)).capitalize(), "Nick": ctx.nick(tid), "last": ps[0].last_name, "one": len(ps) == 1}),
                teams=[tid], players=[p.id for p in ps], importance=18)
    # Snubs: the first alternates with the strongest cases.
    firsts = [r for r in rows if r["role"] == "alternate" and r["spot"] not in ("RS", "ST", "LS")
              and r["rank"] == 1 + next(cnt for s, _l, cnt, *_x in A.PRO_BOWL_SPOTS if s == r["spot"])]
    firsts.sort(key=lambda r: -r.get("case", 0))
    snubs = [r for r in firsts if ctx.player(r["pid"])][:4]
    if snubs:
        rng = ctx.rng(season, "snubs")
        lines = []
        for r in snubs:
            p = ctx.player(r["pid"])
            lines.append(f"{pos_abbr(p)} {p.name} ({ctx.teams[r['team']].abbrev}), the first alternate among "
                         f"{r['conf']} Conference {A.PRO_BOWL_LABEL[r['spot']].lower()}, "
                         f"{season_phrase(p, r['line'])}.")
        ctx.add(season, cal + 0.01, "awards", ctx.pick(("snubhead", season), rng, [
            f"Pro Bowl snubs: {join_and([ctx.player(r['pid']).last_name for r in snubs[:3]])} left out",
            f"Left out of the Pro Bowl: {ctx.short(ctx.player(snubs[0]['pid']), snubs[0]['team'])} and more"]),
            "Not everyone with a case made it. They're alternates, so they could still get in.\n" + "\n".join(lines),
            teams=[r["team"] for r in snubs], players=[r["pid"] for r in snubs], importance=42,
            key=f"snubs-{season}")
        for r in snubs:
            prng = ctx.rng(season, "snubpost", r["pid"])
            if prng.random() < 0.4:
                ctx.post(season, cal, ctx.player_voice(ctx.player(r["pid"])), Say("player_snub", {
                    "spot": A.PRO_BOWL_LABEL[r["spot"]].lower(), "season": season}),
                    teams=[r["team"]], players=[r["pid"]], importance=26)
    # Changes once the Glory Bowl teams are set.
    changes = [r for r in rows if r.get("added")]
    if changes:
        cal2 = 5 + n + 3 + 0.5
        for conf in sorted({r["conf"] for r in changes}):
            lines, players, teams = [], [], []
            for r in sorted((x for x in changes if x["conf"] == conf), key=lambda r: r["spot"]):
                gone = next((x for x in rows if x["pid"] == r["replaces"] and x["role"] == "selected"), None)
                p, q = ctx.player(r["pid"]), ctx.player(r["replaces"])
                if not (p and q and gone):
                    continue
                why = (f"will play in {ctx.champ_name(season)}" if gone["out"] == "glory_bowl"
                       else _OUT_WHY.get(gone["out"], "will not play"))
                lines.append(f"{pos_abbr(p)} {p.name} ({ctx.teams[r['team']].abbrev}) replaces {q.name} "
                             f"({ctx.teams[gone['team']].abbrev}), who {why}.")
                players += [p.id, q.id]
                teams += [r["team"], gone["team"]]
            unfilled = [x for x in rows if x["conf"] == conf and x["role"] == "selected" and x["out"]
                        and not any(c["replaces"] == x["pid"] for c in changes)]
            if unfilled:
                lines.append(f"{plural(len(unfilled), 'spot').capitalize()} could not be filled by an alternate "
                             f"and will be covered by the rest of the roster.")
            if lines:
                ctx.add(season, cal2, "awards", f"{conf} Conference Pro Bowl changes",
                        f"The {conf} Conference's Pro Bowl roster changes now that the {ctx.champ_name(season)} "
                        f"teams are set:\n" + "\n".join(lines), teams=teams, players=players, importance=30,
                        key=f"pbchanges-{season}-{conf}")
                for pid, tid in zip(players[::2], teams[::2]):
                    prng = ctx.rng(season, "pbadd", pid)
                    if prng.random() < 0.35:
                        ctx.post(season, cal2, ctx.player_voice(ctx.player(pid)), Say("player_pb_add", {
                            "season": season, "city": ctx.city(tid)}), teams=[tid], players=[pid], importance=20)


def _news_all_pro(ctx, season, n):
    rows = A.records(ctx.league, "all_pro", season)
    if not rows:
        return
    cal = 6 + n + 0.2
    rng = ctx.rng(season, "allpro")
    order = [s for s, *_x in A.ALL_PRO_SPOTS]
    parts = []
    for team_no in (1, 2):
        lines = []
        for spot in order:
            picks = [r for r in rows if r["team_no"] == team_no and r["spot"] == spot]
            if picks:
                lines.append(f"{A.ALL_PRO_LABEL[spot]}: " + ", ".join(
                    f"{ctx.player(r['pid']).name} ({ctx.teams[r['team']].abbrev})" for r in picks
                    if ctx.player(r["pid"])))
        parts.append(("First team" if team_no == 1 else "Second team") + ":\n" + "\n".join(lines))
    unanimous = [r for r in rows if r["team_no"] == 1 and r["firsts"] == 50 and ctx.player(r["pid"])]
    unan_text = ""
    if unanimous:
        unan_text = (f" {join_and([ctx.player(r['pid']).name for r in unanimous])} "
                     f"{'was a unanimous choice' if len(unanimous) == 1 else 'were unanimous choices'}, "
                     f"named on the first team by all 50 voters.")
    top = [r for r in rows if r["team_no"] == 1 and r["spot"] == "QB"]
    head_names = [ctx.player(r["pid"]).last_name for r in (unanimous or top)[:2] if ctx.player(r["pid"])]
    ctx.add(season, cal, "awards", ctx.pick(("aphead", season), rng, [
        f"{season} All-Pro team: {join_and(head_names)} lead the first team" if head_names else
        f"The {season} All-Pro team",
        f"All-Pro: {join_and(head_names)} headline the {season} first team" if head_names else
        f"The {season} All-Pro team is out"]),
        f"The league's 50-member media panel picked its All-Pro teams for the {season} regular season.{unan_text}\n"
        + "\n\n".join(parts), teams=sorted({r["team"] for r in rows}), players=[r["pid"] for r in rows],
        importance=60, key=f"allpro-{season}")
    for r in rows:
        p = ctx.player(r["pid"])
        if p is None:
            continue
        which = "first" if r["team_no"] == 1 else "second"
        votes = (f" He was on {r['firsts']} of the 50 first-team ballots." if r["team_no"] == 1 else "")
        ctx.add(season, cal, "awards", f"{ctx.short(p, r['team'])} named {which}-team All-Pro",
                f"{ctx.full(r['team'])} {POS_WORD[p.position]} {p.name} is a {which}-team All-Pro "
                f"({A.ALL_PRO_LABEL[r['spot']].lower()}) after he {season_phrase(p, r['line'], n - 1)}.{votes}",
                teams=[r["team"]], players=[p.id], importance=24 if r["team_no"] == 1 else 16,
                key=f"ap-{season}-{r['spot']}-{r['pid']}")
        prng = ctx.rng(season, "appost", p.id)
        if r["team_no"] == 1 and prng.random() < 0.35:
            ctx.post(season, cal, ctx.player_voice(p), Say("player_allpro", {
                "home": p.hometown.split(",")[0] if p.hometown else "", "season": season, "city": ctx.city(r["team"]),
                "votes": r["firsts"]}),
                teams=[r["team"]], players=[p.id], importance=28)
    ctx.post(season, cal, ctx.stat_desk(), f"{season} first-team All-Pros by team: " + ", ".join(
        f"{ctx.teams[t].abbrev} {c}" for t, c in sorted(
            defaultdict(int, {t: sum(1 for r in rows if r['team_no'] == 1 and r['team'] == t)
                              for t in {r['team'] for r in rows}}).items(), key=lambda kv: -kv[1]) if c),
        importance=34)


def _news_pro_bowl_game(ctx, season, n):
    for g in A.records(ctx.league, "pro_bowl_games", season):
        cal = 5 + n + 4 + 0.5
        rng = ctx.rng(season, "pbgame")
        sc = g["score"]
        confs = sorted(sc, key=lambda c: -sc[c])
        w, l = confs[0], confs[1]
        tie = sc[w] == sc[l]
        mvps = []
        for k, side in (("mvp_off", "offensive"), ("mvp_def", "defensive")):
            pid = g.get(k)
            p = ctx.player(pid) if pid else None
            line = g["players"].get(str(pid)) or g["players"].get(pid) if pid else None
            if p and line:
                tid = A._team_now(ctx.league, p.id) or next(
                    (r["team"] for r in A.records(ctx.league, "pro_bowl", season) if r["pid"] == p.id), None)
                team = f" of the {ctx.full(tid)}" if tid else ""
                mvps.append((p, side, f"{p.name}{team} was the {side} MVP: he "
                                      f"{game_phrase(line, rng, 2) or 'made the key plays'}."))
        head = (f"{w} and {l} tie in the Pro Bowl, {sc[w]}-{sc[l]}" if tie else
                ctx.pick(("pbghead", season), rng, [f"{w} Conference wins the Pro Bowl, {sc[w]}-{sc[l]}",
                                                    f"{w} beats {l} {sc[w]}-{sc[l]} in the Pro Bowl"]))
        body = (f"The {w} Conference beat the {l} Conference {sc[w]}-{sc[l]}" if not tie else
                f"The {w} and {l} Conferences played to a {sc[w]}-{sc[l]} tie") + \
            (" in overtime" if g.get("overtime") else "") + f" in the {season} Pro Bowl in {g['site']}. " + \
            " ".join(m[2] for m in mvps) + " Pro Bowl stats don't count in season or career totals."
        ctx.add(season, cal, "awards", head, body, players=[m[0].id for m in mvps], importance=48,
                key=f"pbgame-{season}")
        ctx.post(season, cal, ctx.stat_desk(), f"Pro Bowl final: {w} {sc[w]}, {l} {sc[l]}." +
                 "".join(f" {side.capitalize()} MVP: {p.name}." for p, side, _t in mvps),
                 players=[m[0].id for m in mvps], importance=36)


def _draft_text(ctx, p):
    d = next((d for d in ctx.league.draft_history if d["pid"] == p.id), None)
    if d:
        return f"the No. {d['pick']} pick in the {d['season']} draft"
    if p.draft_round == 0:
        return "an undrafted rookie"
    return f"a round {p.draft_round} pick"


def _news_season_awards(ctx, season, n):
    league = ctx.league
    rows = A.records(league, "season", season)
    if not rows:
        return
    cal = 5 + n + 5
    seeds = {}
    for h in league.team_history:
        if h["season"] == season:
            seeds[h["team"]] = (h.get("seed"), h["w"], h["l"], h["t"])
    if season == league.season:
        rec = S.records(league)
        for tid, r in rec.items():
            seeds[tid] = (po.seed_of(league, tid), r["w"], r["l"], r["t"])
    imp = {"mvp": 85, "opoy": 70, "dpoy": 70, "oroy": 60, "droy": 60, "cpoy": 55}
    winners = []
    prev = defaultdict(lambda: defaultdict(float))
    for r in league.career:
        if r["season"] == season - 1 and r["phase"] == "regular":
            for k, v in r["stats"].items():
                if isinstance(v, (int, float)):
                    prev[r["pid"]][k] += v
    for r in sorted(rows, key=lambda r: [a for a, *_x in A.SEASON_AWARDS].index(r["award"])):
        p = ctx.player(r["pid"])
        if p is None:
            continue
        tid = r["team"]
        rng = ctx.rng(season, "award", r["award"])
        name = A.AWARD_NAME[r["award"]]
        seed, w, l, t = seeds.get(tid, (None, 0, 0, 0))
        record = f"{w}-{l}" + (f"-{t}" if t else "")
        team_bit = f"as the {ctx.nick(tid)} went {record}"
        if seed == 1:
            team_bit += " and earned the No. 1 seed"
        elif seed:
            team_bit += " and made the playoffs"
        L = ctx.short(p, tid)
        if r["award"] == "mvp":
            head = ctx.pick(("awhead", season), rng, [f"{L} named MVP", f"{L} wins MVP",
                                                      f"MVP: {L} of the {ctx.nick(tid)}"])
            lead = f"{ctx.city(tid)} {POS_WORD[p.position]} {p.name} is the league's Most Valuable Player for {season}."
        elif r["award"] in ("oroy", "droy"):
            side = "offense" if r["award"] == "oroy" else "defense"
            head = f"{L} named {name}"
            lead = (f"{ctx.city(tid)} {POS_WORD[p.position]} {p.name}, {_draft_text(ctx, p)}, is the {season} {name}, "
                    f"the best rookie on {side}.")
        elif r["award"] == "cpoy":
            head = f"{L} named {name}"
            last = prev.get(p.id, {})
            gp = int(last.get("gp", 0))
            if r.get("kind") == "injury":
                why = (f"after an injury limited him to {plural(gp, 'game')} last season" if gp else
                       "after an injury cost him all of last season")
            else:
                why = (f"a year after he {season_phrase(p, last)}" if gp else "a year after he didn't play")
            lead = f"{ctx.city(tid)} {POS_WORD[p.position]} {p.name} is the {season} {name}, {why}."
        else:
            head = ctx.pick(("awhead2", season), rng, [f"{L} named {name}", f"{L} wins {name}"])
            lead = f"{ctx.city(tid)} {POS_WORD[p.position]} {p.name} is the {season} {name}."
        sents = [lead, f"He {season_phrase(p, r['line'], n - 1)} {team_bit}."]
        v = r["votes"]
        firsts, pts = v[0][2], v[0][3]
        vote = (f"He was the unanimous choice, first on all 50 ballots of the league's media panel." if firsts == 50 else
                f"He received {firsts} of 50 first-place votes and {pts} points from the league's 50-member media panel.")
        sents.append(vote)
        others = []
        for pid, tid2, f1, pts2 in v[1:3]:
            q = ctx.player(pid)
            if q:
                others.append(f"{pos_abbr(q)} {q.name} ({ctx.teams[tid2].abbrev}, {pts2} points"
                              + (f", {plural(f1, 'first-place vote')}" if f1 else "") + ")")
        if others:
            sents.append(f"Next: {join_and(others)}.")
        ctx.add(season, cal, "awards", head, " ".join(sents), teams=[tid] + [x[1] for x in v[1:3]],
                players=[p.id] + [x[0] for x in v[1:3]], importance=imp[r["award"]], key=f"award-{season}-{r['award']}")
        winners.append((r["award"], p, tid))
        ctx.post(season, cal, ctx.insider(rng), f"{name}: {p.name}, {ctx.full(tid)}." +
                 (f" Unanimous." if firsts == 50 else f" {firsts} of 50 first-place votes."),
                 teams=[tid], players=[p.id], importance=imp[r["award"]] - 15)
        if rng.random() < 0.6:
            ctx.post(season, cal, ctx.player_voice(p), Say("player_award", {"award": name, "city": ctx.city(tid)}),
                     teams=[tid], players=[p.id], importance=imp[r["award"]] - 20)
        if rng.random() < 0.6:
            ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_award", {
                "last": p.last_name, "LAST": p.last_name.upper(), "award": name, "AWARD": name.upper(),
                "Nick": ctx.nick(tid)}), teams=[tid], players=[p.id], importance=20)
    if len(winners) >= 3:
        ctx.add(season, cal, "awards", f"The {season} award winners",
                f"The league handed out its {season} awards, voted by a 50-member media panel on the regular season, "
                f"the week of {ctx.champ_name(season)}.\n" + "\n".join(
                    f"{A.AWARD_NAME[a]}: {pos_abbr(p)} {p.name} ({ctx.teams[t].abbrev})" for a, p, t in winners) +
                "".join(f"\n{x['text']}" for x in A.records(league, "notes", season) if x.get("award") == "cpoy"),
                teams=[t for _a, _p, t in winners], players=[p.id for _a, p, _t in winners], importance=72,
                key=f"awards-{season}")


def _news_gb_mvp(ctx, season, n):
    for r in A.records(ctx.league, "gb_mvp", season):
        p = ctx.player(r["pid"])
        if p is None:
            continue
        rng = ctx.rng(season, "gbmvp")
        cal = 5 + n + 5 + 0.2
        name = ctx.champ_name(season)
        line = r["line"]
        what = game_phrase(line, rng, 3) if A.group_of(p.position) not in ("K", "P") else _st_game_phrase(line, rng)
        ctx.add(season, cal, "awards", ctx.pick(("gbhead", season), rng, [f"{ctx.short(p, r['team'])} named {name} MVP",
                                                                          f"{name} MVP: {ctx.short(p, r['team'])}"]),
                f"{ctx.full(r['team'])} {POS_WORD[p.position]} {p.name} is the Most Valuable Player of {name}. "
                f"He {what or 'made the plays that mattered'}.", teams=[r["team"]], players=[p.id], importance=74,
                key=f"gbmvp-{season}")
        ctx.post(season, cal, ctx.stat_desk(), f"{name} MVP: {p.name} ({ctx.teams[r['team']].abbrev}). "
                 f"{stat_line(line)}", teams=[r["team"]], players=[p.id], importance=50)
