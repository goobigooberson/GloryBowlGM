# bitter.py
# Bitter: the league's social media site (the Bitter tab). Accounts post "bits":
# news outlets share every story as a clickable article, insiders break news,
# team accounts and beat writers post finals, a hot-take TV host makes
# predictions (and a receipts account holds him to them), a grumpy columnist, a
# fantasy guy, a former lineman who watches film, a meme account, fictional
# celebrities who root for teams, players and fans. Bits get replies,
# quote-bits, likes and rebits, and the page shows what's trending.
#
# engine/news.py works out what happened (it calls the react_* functions here
# with the facts); this file decides who reacts and how, and assembles the
# timeline the screen shows. Wording lives in engine/bitter_words.py.
#
# Freshness (Oct 24, Blake: "the tweets that are visible feel completely new and
# in reaction to whats happening... there should not be word for word repeats"):
# reactions hand news.py a news_words.Say (which list, which facts), and news.py
# words every bit of a season in calendar order so that no bit repeats another
# and no shape of words comes back in the same week (news_words.Writer.fresh).
# Every reaction gets the specifics: the player and his line, the play that
# decided it, the score, the streak, the record, who's next. Accounts remember
# their takes and follow up (Rex Harmon, Big T, Fantasy Freddie, the fans).
#
# Rules: every account is invented (none imitates a real person); PG-13 (no
# swearing); opinions are fine, made-up facts are not. Likes, rebits, replies
# and follower counts are invented flavor, the same every time for a league.
# Feel choices here are PROVISIONAL, for Blake's review (docs/news-design.md).

import random
import re
import zlib

from .news_words import Say

# ---- The cast (invented) ---------------------------------------------------------
PERSONAS = {
    "LeagueWire": ("League Wire", "Outlet", "League news, scores and stories.", 4_800_000),
    "GridironDaily": ("Gridiron Daily", "Outlet", "Features, power rankings, previews.", 2_100_000),
    "KesslerReports": ("Dana Kessler", "Insider", "League insider. DMs open for tips.", 2_400_000),
    "OkaforScoop": ("Marcus Okafor", "Insider", "Breaking news and the stories behind it.", 1_900_000),
    "ToriVanceNews": ("Tori Vance", "Insider", "Reporter. Injuries, transactions, the draft.", 1_200_000),
    "StatDesk": ("League Stat Desk", "Stats", "Numbers, notes and nuggets.", 1_100_000),
    "RexTakes": ("Rex Harmon", "TV host", "Host of Rex Unfiltered weekdays. Loud and usually right.", 1_600_000),
    "WaltBrennan": ("Walt Brennan", "Columnist", "Old-school columnist. Run the ball.", 210_000),
    "FantasyFreddie": ("Fantasy Freddie", "Fantasy analyst", "Start 'em, sit 'em, regret 'em.", 640_000),
    "BigTHolloway": ('Terrence "Big T" Holloway', "Analyst", "11 years in the trenches. Film don't lie.", 380_000),
    "GridironMemes": ("Gridiron Memes", "Parody", "Parody account. Not affiliated with anyone.", 2_900_000),
    "ReceiptsFB": ("Football Receipts", "Receipts", "We keep the takes so you don't have to.", 870_000),
}
# Fictional celebrities: (name, handle, style, what they do). Each roots for one team
# (picked per league).
CELEBS = [("Lil Blitz", "LilBlitz", "rapper", "Rapper"), ("Nova Reyes", "NovaReyes", "popstar", "Pop star"),
          ("Wade Harlan", "WadeHarlan", "country", "Country singer"),
          ("Celeste Monroe", "CelesteMonroe", "actress", "Actress"),
          ("Danny Kowalczyk", "DannyKowalczyk", "comedian", "Comedian"),
          ("Tre Calloway", "TreCalloway3", "hoops", "Pro basketball player"),
          ("Rocco Bellini", "ChefRocco", "chef", "Celebrity chef"),
          ("Big Country Boone", "BigCountryBoone", "wrestler", "Pro wrestler"),
          ("DJ Kilowatt", "DJKilowatt", "dj", "DJ"), ("Marisol Vega", "MarisolVegaShow", "host", "Talk show host")]
# Each team's hashtag.
TEAM_TAGS = {"BOS": "#HoistTheSails", "NYK": "#KnightsRise", "PHI": "#RingTheBell", "BUF": "#LetItSnow",
             "BAL": "#FullSpeedAhead", "WAS": "#HoldTheLine", "PIT": "#ForgedInIron", "CIN": "#RideTheRiver",
             "CLE": "#StokeTheFire", "DET": "#BuiltDifferent", "CHI": "#AllAboard", "IND": "#FeelTheSpeed",
             "CHA": "#RoyalBlood", "ATL": "#RiseFromTheAshes", "MIA": "#BiteBack", "TAM": "#BringTheStorm",
             "MIN": "#DeepFreeze", "KCY": "#SingTheBlues", "STL": "#OnTarget", "NSH": "#OutlawCountry",
             "HOU": "#StrikeOil", "DAL": "#StampedeOn", "SAN": "#VamosVaqueros", "NOR": "#KreweLove",
             "SEA": "#MakeSomeNoise", "POR": "#TimberTime", "SFO": "#RollInTheFog", "DEN": "#PeakSeason",
             "LAS": "#StarPower", "SDG": "#SurfsUp", "LVG": "#AllIn", "PHX": "#FeelTheSting"}

CATS = {"headlines": "Headlines", "teams": "Team accounts", "reporters": "Reporters and insiders",
        "takes": "Hot takes and analysis", "stats": "Stats", "players": "Players", "fans": "Fans",
        "celebs": "Celebrities"}

# "For you" (the league-wide view): about this many top-level bits a week (Blake,
# Oct 24: about 80, every one tied to something that happened), mixed like a real
# feed: these shares of the week go to each kind of account first (the most
# important of each), then the rest to the most important bits of any kind.
# PROVISIONAL (the mix). A team's or a player's view shows everything about them.
FOR_YOU_PER_WEEK = 80
FOR_YOU_MIX = {"headlines": 0.30, "reporters": 0.08, "stats": 0.06, "teams": 0.12, "takes": 0.14, "fans": 0.14,
               "celebs": 0.07, "players": 0.09}
FOR_YOU_FLOOR = 16          # nothing less important than this makes For you

# How a team's fans are split: 0 the homer, 1 the worrier, 2 the trash talker.
HOMER, WORRIER, TROLL = 0, 1, 2


def persona(key):
    name, role, _bio, _f = PERSONAS[key]
    return (name, key, role, None)


def tag(ctx, tid):
    return TEAM_TAGS.get(ctx.teams[tid].abbrev, "#" + re.sub(r"[^A-Za-z]", "", ctx.teams[tid].nickname) + "Win")


def team_account(ctx, tid):
    t = ctx.teams[tid]
    return (t.name, re.sub(r"[^A-Za-z]", "", t.nickname)[:15], "Team account", tid)


def celebrity(ctx, tid):
    """(who, style) for the celebrity who roots for this team, or None."""
    fans = ctx.__dict__.get("_celebs")
    if fans is None:
        r = random.Random(f"celebs-{ctx.salt}")
        teams = r.sample(sorted(ctx.teams), len(CELEBS))
        fans = {t: c for t, c in zip(teams, CELEBS)}
        ctx._celebs = fans
    c = fans.get(tid)
    if not c:
        return None
    name, handle, style, what = c
    return (name, handle, f"{what} · {ctx.teams[tid].nickname} fan", tid), style


def _week_cap(ctx, key, season, week, limit):
    """At most `limit` bits of one kind per week (so no account floods the timeline)."""
    caps = ctx.__dict__.setdefault("_caps", {})
    k = (key, season, week)
    if caps.get(k, 0) >= limit:
        return False
    caps[k] = caps.get(k, 0) + 1
    return True


def _takes(ctx):
    """What accounts said that they (or someone) will come back to: Rex's calls,
    Big T's film notes, Freddie's meltdowns, fans' takes on players."""
    return ctx.__dict__.setdefault("_takes", [])


def remember(ctx, kind, season, week, who, bit_id, **about):
    if bit_id:
        _takes(ctx).append(dict(about, kind=kind, season=season, week=week, who=who, id=bit_id))


# Player personalities on Bitter (Blake, Oct 23: "a lot generic, but then there's some
# wild ones who are bold and/or weird and cryptic like some NFL players"). Picked at
# random for each player in each league (never from his ratings).
PERSONALITIES = (("bold", 0.10), ("cryptic", 0.06), ("weird", 0.04))


def personality(ctx, p):
    """'bold', 'cryptic', 'weird' or None (most players)."""
    r = random.Random(f"persona-{ctx.salt}-{p.id}").random()
    for kind, share in PERSONALITIES:
        if r < share:
            return kind
        r -= share
    return None


def _voice_ok(ctx, p, line):
    """Players whose own posts show up: good players, and anyone who played a starter's
    share of that game (from the box score, so it never changes with later depth charts)."""
    return ctx.caliber(p) >= 62 or line.get("off_snaps", 0) + line.get("def_snaps", 0) >= 35


def player_post(ctx, season, cal, p, tid, won, rng, imp, opp_tid=None, facts=None):
    """A player's own bit after his game, in his voice. facts: score, rec, got (his line in words)."""
    voice = personality(ctx, p)
    f = dict(facts or {}, opp=ctx.nick(opp_tid) if opp_tid else "them", city=ctx.city(tid))
    f.setdefault("score", "")
    f.setdefault("rec", "")
    f["got"] = f.get("got") or ""
    if voice == "bold":
        name = "player_win_bold" if won else "player_loss_bold"
    elif voice == "cryptic" and (not won or rng.random() < 0.5):
        name = "player_cryptic"
    elif voice == "weird" and rng.random() < 0.5:
        name = "player_weird"
    else:
        name = "player_win" if won else "player_loss"
    if name in ("player_win", "player_loss") and not (f["score"] and f["rec"]):
        return None
    return ctx.post(season, cal, ctx.player_voice(p), Say(name, f), teams=[tid], players=[p.id],
                    importance=imp + (6 if voice else 0))


def _division_rivals(ctx, tid):
    t = ctx.teams[tid]
    return [o for o in ctx.teams.values() if o.conference == t.conference and o.division == t.division and o.id != tid]


def _team_weeks(track):
    """{team: [(week, opponent), ...]} for the regular season (cached on the track)."""
    tw = track.__dict__.get("_team_weeks")
    if tw is None:
        tw = {}
        for g in sorted(track.schedule, key=lambda g: g["week"]):
            tw.setdefault(g["home"], []).append((g["week"], g["away"]))
            tw.setdefault(g["away"], []).append((g["week"], g["home"]))
        track._team_weeks = tw
    return tw


def next_game(track, tid, week):
    """(week, opponent) of a team's next regular-season game after `week`, or None."""
    if track is None:
        return None
    return next(((w, o) for w, o in _team_weeks(track).get(tid, ()) if w > week), None)


# ---------------------------------------------------------------------------
# Reactions (called from engine/news.py with the facts it already worked out)
# ---------------------------------------------------------------------------

def _game_facts(ctx, f, g, phase, W, L, sp, lp, tw_, tl_, track):
    # (f["_season"]: the season, set by news.py)
    """Everything a reaction to this game can mention (see bitter_words.py)."""
    from .news import num, plural
    from . import playoffs as po
    ws, ls = f["ws"], f["ls"]
    margin = ws - ls
    week = g["week"]
    regular = phase == "regular"
    wt, lt = ctx.teams[W], ctx.teams[L]
    wr, lr = f.get("_wrec"), f.get("_lrec")
    gf = {"Wn": wt.nickname, "Ln": lt.nickname, "Wc": wt.city, "Lc": lt.city, "WN": wt.nickname.upper(),
          "LN": lt.nickname.upper(), "city": wt.city, "CITY": wt.city.upper(), "tag": tag(ctx, W), "ltag": tag(ctx, L),
          "score": f["score"], "ws": ws, "ls": ls, "margin": margin, "margin_t": plural(margin, "point"),
          "margin_pt": f"{num(margin)}-point", "champ": f["champ"], "div": wt.division,
          "star": bool(sp and f.get("star_got")), "star_last": sp.last_name if sp else "",
          "star_got": f.get("star_got", ""), "lstar": bool(lp and f.get("lstar_got")),
          "lstar_last": lp.last_name if lp else "", "lstar_got": f.get("lstar_got", ""),
          "rec": regular and bool(f.get("wrec")), "wrec": f.get("wrec", ""), "lrec": f.get("lrec", ""),
          "wrec_b": f.get("wrec_b", ""), "lrec_b": f.get("lrec_b", ""),
          "wstreak": bool(f.get("wstreak")), "n_w": f.get("n_w") or "", "lstreak": bool(f.get("lstreak")),
          "n_l": f.get("n_l") or "",
          "late": bool(f.get("_late") and f.get("has_desc")), "goahead": f.get("goahead", ""),
          "clock": f.get("clock", ""), "comeback": f.get("max_def", 0) >= 10, "max_def": f.get("max_def", 0),
          "ot": bool(f.get("ot")), "ot_s": " (OT)" if f.get("ot") else "",
          "takeaways": tl_["give"] >= 3, "to_n": num(tl_["give"]), "sacks4": tl_["sacked"] >= 4,
          "sk_n": num(tl_["sacked"]), "ground": tw_["rush"] >= 170, "rw": tw_["rush"],
          "snow": bool(f.get("snow")), "rain": bool(f.get("rain")), "frigid": bool(f.get("frigid")),
          "temp": f.get("temp", ""), "avenge": bool(f.get("avenge")), "sweep": bool(f.get("sweep")),
          "prev_week": f.get("prev_week", ""), "prev_score": f.get("prev_score", ""),
          "took_first": regular and bool(f.get("took_first")), "first_win": bool(f.get("first_win")),
          "unbeaten": bool(f.get("unbeaten")), "snap_w": bool(f.get("snap_w")), "upset": bool(f.get("upset")),
          "shutout": ls == 0, "blowout": margin >= 21, "close": margin <= 3 and not f.get("ot"),
          "outgained": tl_["yds"] - tw_["yds"] >= 80, "yds_gap": tl_["yds"] - tw_["yds"],
          "lpen": tl_["pen"] >= 10, "pen_n": num(tl_["pen"]), "peny": tl_["pen_yds"],
          "rival": L in [o.id for o in _division_rivals(ctx, W)],
          "playoffs": phase == "playoffs", "rnd": po.ROUND_NAMES.get(week, "") if phase == "playoffs" else "",
          "lbetter": bool(regular and wr and lr and (lr[0] + 0.5 * lr[2]) / max(1, sum(lr[:3]))
                          > (wr[0] + 0.5 * wr[2]) / max(1, sum(wr[:3]))),
          "road_loss": L == g["away"] and not g.get("neutral"), "home_loss": L == g["home"] and not g.get("neutral")}
    if f.get("hw") is not None and f["hw"] < f["hl"]:
        gf.update(trailed_half=True, hw_t=f"{f['hl']}-{f['hw']}")
    if phase == "playoffs" and week == 5:
        titles = sum(1 for s, t in ctx.league.champions.items() if t == W and s < f.get("_season", 10 ** 6))
        gf.update(first_title=bool(f.get("first_title")), repeat_title=not f.get("first_title"),
                  titles_n=titles + 1)
    if regular:
        for side, key in ((W, ""), (L, "l")):
            nx = next_game(track, side, week)
            if nx:
                gf.update({f"{key}has_next": True, f"{key}next": ctx.nick(nx[1]), f"{key}next_week": nx[0]})
        again = next(((w, o) for w, o in _team_weeks(track).get(W, ()) if w > week and o == L), None) if track else None
        if again:
            gf.update(rematch=True, rematch_week=again[0])
    return gf


def _beat_facts(ctx, side, W, L, f, star, tw_, tl_, track, phase, week):
    """One team's game, from its beat writer's side."""
    from .news import num, stat_line
    won = side == W
    other = L if won else W
    mine, theirs = (tw_, tl_) if won else (tl_, tw_)
    p = ctx.player(star[0]) if star and star[2] >= 8 else None
    rec = (f.get("wrec") if won else f.get("lrec")) or ""
    bf = {"T": ctx.city(side), "O": ctx.city(other), "pf": f["ws"] if won else f["ls"],
          "pa": f["ls"] if won else f["ws"], "ot_s": " in OT" if f.get("ot") else "", "rec": rec,
          "st": bool(p), "st_name": p.name if p else "", "st_line": stat_line(star[1]) if p else "",
          "takes": theirs["give"] >= 2, "take_n": num(theirs["give"]), "gives": mine["give"] >= 2,
          "give_n": num(mine["give"]), "rush": mine["rush"] >= 150, "ry": mine["rush"],
          "sacked": mine["sacked"] >= 4, "sk_n": num(mine["sacked"])}
    if not bf["st_line"]:
        bf["st"] = False
    nx = next_game(track, side, week) if phase == "regular" else None
    if nx:
        bf.update(next=ctx.city(nx[1]), next_week=nx[0], has_next=True)
    return bf


def react_game(ctx, season, cal, phase, g, f, W, L, sp, lp, imp, rng, tw_, tl_, star_def=None, lines=None,
               track=None, stars=None):
    """Team accounts, beat writers, fans, the TV host, memes, celebrities and analysts react to a game."""
    from .news import num
    tie = f.get("tie")
    week = g["week"]
    if phase == "preseason" or tie:
        return
    gf = _game_facts(ctx, f, g, phase, W, L, sp, lp, tw_, tl_, track)
    champ = phase == "playoffs" and week == 5
    # The winner's team account, with fans replying.
    bucket = "team_champ" if champ else ("team_playoff_win" if phase == "playoffs" else "team_win")
    top = ctx.post(season, cal, team_account(ctx, W), Say(bucket, gf), teams=[W, L],
                   players=[sp.id] if sp else (), importance=imp - 2, kind="final")
    # Fans: the playoffs get their own lines (NICK and opp: the fan's own team and the other one).
    homer = "fan_champ" if champ else "fan_playoff_win" if phase == "playoffs" else "fan_reply_win"
    ctx.post(season, cal, ctx.fan(W, rng, HOMER), Say(homer, dict(gf, NICK=gf["WN"], opp=gf["Ln"])), teams=[W],
             reply_to=top, importance=10)
    if rng.random() < 0.5:
        ctx.post(season, cal, ctx.fan(L, rng, TROLL), Say("fan_salty", gf), teams=[L], reply_to=top, importance=8)
    # The loser's account.
    if rng.random() < 0.6 or phase == "playoffs":
        ltop = ctx.post(season, cal, team_account(ctx, L), Say("team_loss", gf), teams=[L, W],
                        importance=imp - 12, kind="final")
        worrier = "fan_playoff_loss" if phase == "playoffs" else "fan_loss"
        ctx.post(season, cal, ctx.fan(L, rng, WORRIER), Say(worrier, dict(gf, NICK=gf["LN"], opp=gf["Wn"])),
                 teams=[L], reply_to=ltop, importance=8)
    # Each team's beat writer.
    for side, star in ((W, (stars or (None, None))[0]), (L, (stars or (None, None))[1])):
        bf = _beat_facts(ctx, side, W, L, f, star, tw_, tl_, track, phase, week)
        ctx.post(season, cal, ctx.beat(side), Say("beat_win" if side == W else "beat_loss", bf), teams=[W, L],
                 players=[star[0]] if bf["st"] else (), importance=imp - 10)
    # Fans who go all in on a hot start or give up on a slide (they'll hear about it later).
    if phase == "regular":
        wr, lr = f.get("_wrec"), f.get("_lrec")
        taken = {(t["season"], t["kind"], t.get("team")) for t in _takes(ctx)}
        if wr and sum(wr[:3]) >= 5 and wr[1] <= 1 and f.get("wstreak") and (season, "fan_parade", W) not in taken:
            who = ctx.fan(W, rng, HOMER)
            pid = ctx.post(season, cal, who, Say("fan_parade", dict(gf, NICK=gf["WN"])), teams=[W], importance=24)
            remember(ctx, "fan_parade", season, week, who, pid, team=W)
        if lr and sum(lr[:3]) >= 4 and lr[0] <= lr[1] - 3 and f.get("lstreak") and                 (season, "fan_doom", L) not in taken and week <= ctx.n_weeks - 4:
            who = ctx.fan(L, rng, WORRIER)
            pid = ctx.post(season, cal, who, Say("fan_doom", gf), teams=[L], importance=22)
            remember(ctx, "fan_doom", season, week, who, pid, team=L)
    # A division rival enjoys it.
    rivals = [o for o in _division_rivals(ctx, L) if o.id != W]
    if rivals and phase == "regular" and rng.random() < 0.3:
        rv = rng.choice(rivals)
        ctx.post(season, cal, ctx.fan(rv.id, rng, TROLL), Say("fan_rival_dunk", gf), teams=[rv.id, L], importance=16)
    # Rex Harmon: takes that get remembered.
    rf = dict(gf, Tc="", rec="", lrec_b=f.get("lrec_b", ""), wrec_b=f.get("wrec_b", ""))
    said = {(t["season"], t["team"]) for t in _takes(ctx) if t["kind"].startswith("rex")}
    if phase == "regular":
        wr, lr = f.get("_wrec"), f.get("_lrec")
        if f.get("upset") and _week_cap(ctx, "rex_fraud", season, week, 1):
            ctx.post(season, cal, persona("RexTakes"), Say("rex_fraud", rf), teams=[W, L], importance=40)
        if (f.get("wstreak") and wr and wr[1] <= 1 and sum(wr[:3]) >= 5 and (season, W) not in said
                and _week_cap(ctx, "rex", season, week, 2)):
            pid = ctx.post(season, cal, persona("RexTakes"), Say("rex_champ", dict(rf, Tc=ctx.city(W),
                           rec=f.get("wrec", ""))), teams=[W], importance=44)
            remember(ctx, "rex_champ", season, week, None, pid, team=W)
        if (lr and sum(lr[:3]) >= 4 and lr[0] + 0.5 * lr[2] <= 0.25 * sum(lr[:3]) and (season, L) not in said
                and _week_cap(ctx, "rex", season, week, 2)):
            pid = ctx.post(season, cal, persona("RexTakes"), Say("rex_done", dict(rf, Tc=ctx.city(L),
                           rec=f.get("lrec", ""))), teams=[L], importance=44)
            remember(ctx, "rex_done", season, week, None, pid, team=L)
    # Memes.
    mf = dict(gf, kicker=f.get("_kicker", ""))
    memes = []
    if gf["shutout"]:
        memes.append("meme_shutout")
    if gf["margin"] >= 30:
        memes.append("meme_blowout")
    if gf["ot"]:
        memes.append("meme_ot")
    if f.get("max_def", 0) >= 17:
        memes.append("meme_comeback")
    if f.get("winless") and lr_ok(f) and f["_lrec"][1] >= 5:
        memes.append("meme_winless")
    if f.get("_kicker"):
        memes.append("meme_kicker")
    if f.get("lstreak") and lr_ok(f) and f["_lrec"][3][-1:] == "L" and rng.random() < 0.4:
        memes.append("meme_streak_loss")
    if f.get("wstreak") and rng.random() < 0.3:
        memes.append("meme_streak_win")
    if f.get("upset") and rng.random() < 0.4:
        memes.append("meme_upset")
    if champ:
        memes.append("meme_champ")
    if memes and (champ or rng.random() < 0.6) and _week_cap(ctx, "meme", season, cal, 4):
        ctx.post(season, cal, persona("GridironMemes"), Say(rng.choice(memes), mf), teams=[W, L], importance=34)
    # Celebrities.
    cw = celebrity(ctx, W)
    if cw:
        who, style = cw
        cf = dict(gf, Nick=ctx.nick(W))
        big = (phase == "playoffs" or gf["margin"] >= 17 or f.get("wstreak") or f.get("took_first")
               or gf["rival"] or rng.random() < 0.2)
        if champ:
            ctx.post(season, cal, who, Say("celeb_champ", cf), teams=[W], importance=60)
        elif gf["margin"] <= 3 or gf["ot"]:
            # A nail-biter: "please, for my health".
            ctx.post(season, cal, who, Say("celeb_win_close", cf), teams=[W], importance=38)
        elif big:
            name = f"celeb_win_{style}" if rng.random() < 0.6 else "celeb_win"
            ctx.post(season, cal, who, Say(name, cf), teams=[W], importance=36)
    cl = celebrity(ctx, L)
    if cl and (phase == "playoffs" or rng.random() < 0.35):
        ctx.post(season, cal, cl[0], Say("celeb_loss", dict(gf, rec=bool(gf["lrec"]))), teams=[L], importance=26)
    # The league's louder (and stranger) players speak up after the game.
    for pid, line in (lines or {}).items():
        p = ctx.player(pid)
        tid = line.get("team")
        if p is None or tid not in (W, L) or not _voice_ok(ctx, p, line):
            continue
        voice = personality(ctx, p)
        won = tid == W
        prng = random.Random(f"pvoice-{ctx.salt}-{g['id']}-{pid}")
        if (voice == "bold" and prng.random() < (0.3 if won else 0.2)) or \
                (voice == "cryptic" and not won and prng.random() < 0.3):
            player_post(ctx, season, cal, p, tid, won, prng, 26, L if won else W,
                        {"score": gf["score"], "rec": gf["wrec"] if won else gf["lrec"]})
    # Big T on the trenches (and he remembers the lines he called out).
    if tl_["sacked"] >= 5 and rng.random() < 0.5 and _week_cap(ctx, "bigt", season, week, 2):
        pid = ctx.post(season, cal, persona("BigTHolloway"), Say("bigt_sacks", dict(gf, n=num(tl_["sacked"]))),
                       teams=[W, L], importance=32)
        if phase == "regular":
            remember(ctx, "bigt_line", season, week, None, pid, team=L, n=tl_["sacked"])
    elif tw_["rush"] >= 200 and rng.random() < 0.5 and _week_cap(ctx, "bigt", season, week, 2):
        ctx.post(season, cal, persona("BigTHolloway"), Say("bigt_rush", gf), teams=[W], importance=32)
    elif star_def and rng.random() < 0.4 and _week_cap(ctx, "bigt", season, week, 2):
        p, got = star_def
        ctx.post(season, cal, persona("BigTHolloway"), Say("bigt_def", dict(gf, name=p.name, got=got)),
                 teams=[W], players=[p.id], importance=30)


def lr_ok(f):
    return bool(f.get("_lrec"))


def react_performance(ctx, season, cal, week, p, tid, stat, got, ints, rng, imp, opp=None, track=None):
    """Fantasy Freddie on the biggest fantasy days (and the worst); he remembers his meltdowns."""
    f = {"last": p.last_name, "got": got, "ints": ints, "opp": ctx.nick(opp) if opp else "them"}
    if stat == "pass_int":
        if _week_cap(ctx, "freddie_bust", season, week, 1):
            pid = ctx.post(season, cal, persona("FantasyFreddie"), Say("freddie_bust", f), teams=[tid],
                           players=[p.id], importance=30)
            remember(ctx, "freddie_bust", season, week, None, pid, pid_=p.id)
        return
    if stat not in ("pass_yds", "pass_td", "rush_yds", "rush_td", "rec_yds", "rec_td", "rec"):
        return
    # Freddie takes back a meltdown about this player (once).
    for t in _takes(ctx):
        if t["kind"] == "freddie_bust" and t["pid_"] == p.id and t["season"] == season and t["week"] < week \
                and not t.get("settled"):
            t["settled"] = True
            ctx.post(season, cal, persona("FantasyFreddie"), Say("freddie_crow", dict(f, k=t["week"], w=week)),
                     teams=[tid], players=[p.id], quote={"of": t["id"], "when": f"Week {t['week']}"},
                     importance=imp - 6)
            return
    if rng.random() < 0.6 and _week_cap(ctx, "freddie", season, week, 3):
        ctx.post(season, cal, persona("FantasyFreddie"), Say("freddie_boom", f), teams=[tid], players=[p.id],
                 importance=imp - 12)


def react_injury(ctx, season, cal, p, tid, part, vp, rng, imp, parent):
    if p.position in ("QB", "RB", "WR", "TE") and rng.random() < 0.6:
        ctx.post(season, cal, persona("FantasyFreddie"), Say("freddie_injury", {"name": p.name, "part": part, "vp": vp}),
                 teams=[tid], players=[p.id], reply_to=parent, importance=10)


def react_week(ctx, season, track, w, games):
    """Weekly: receipts on the TV host's old takes, follow-ups on other remembered
    takes, the columnist's column, rematch week for the fans."""
    from . import storylines as SL
    from .news import num, plural
    cal = 5 + w + 0.65
    rng = ctx.rng(season, "bitterweek", w)
    for t in _takes(ctx):
        if t["season"] != season or t["week"] >= w or t.get("settled"):
            continue
        quote = {"of": t["id"], "when": f"Week {t['week']}"}
        if t["kind"] in ("rex_done", "rex_champ"):
            kind, n = track.streak_of(t["team"], w)
            since = track.record(t["team"], w, since=t["week"])
            wrong = (t["kind"] == "rex_done" and kind == "W" and n >= 3) or \
                    (t["kind"] == "rex_champ" and kind == "L" and n >= 3)
            if wrong:
                t["settled"] = True
                ctx.post(season, cal, persona("ReceiptsFB"), Say("receipts", {
                    "Tc": ctx.city(t["team"]), "since_rec": SL.rec_text(since), "k": t["week"]}), teams=[t["team"]],
                    quote=quote, importance=46)
            elif t["kind"] == "rex_done" and w == ctx.n_weeks:
                r = track.record(t["team"], w)
                if SL.pct(r) < 0.5:
                    t["settled"] = True
                    ctx.post(season, cal, persona("RexTakes"), Say("rex_right", {
                        "k": t["week"], "Tc": ctx.city(t["team"]), "rec": SL.rec_text(r)}), teams=[t["team"]],
                        quote=quote, importance=40)
        elif t["kind"] in ("fan_parade", "fan_doom"):
            kind, n = track.streak_of(t["team"], w)
            r = track.record(t["team"], w)
            facts = {"Tc": ctx.city(t["team"]), "k": t["week"], "n": num(n), "rec": SL.rec_text(r),
                     "since_rec": SL.rec_text(track.record(t["team"], w, since=t["week"])), "tag": tag(ctx, t["team"])}
            if t["kind"] == "fan_parade" and kind == "L" and n >= 3:
                t["settled"] = True
                rivals = _division_rivals(ctx, t["team"])
                if rivals:
                    rv = random.Random(f"parade-{ctx.salt}-{season}-{t['team']}").choice(rivals)
                    ctx.post(season, cal, ctx.fan(rv.id, rng, TROLL), Say("fan_parade_bust", facts),
                             teams=[rv.id, t["team"]], quote=quote, importance=30)
            elif t["kind"] == "fan_doom" and kind == "W" and n >= 3 and SL.pct(r) >= 0.45:
                t["settled"] = True
                ctx.post(season, cal, t["who"], Say("fan_doom_crow", facts), teams=[t["team"]], quote=quote,
                         importance=28)
            elif t["kind"] == "fan_doom" and w == ctx.n_weeks:
                t["settled"] = True
                if SL.pct(r) < 0.4:
                    ctx.post(season, cal, t["who"], Say("fan_doom_right", facts), teams=[t["team"]], quote=quote,
                             importance=24)
        elif t["kind"] == "bigt_line":
            # Big T comes back to a line he called out: better, or the same old story.
            game = next((x for x in track.team_games.get(t["team"], ()) if x[0] == w), None)
            if w - t["week"] > 8:
                t["settled"] = True
            if not game:
                continue
            _w, g, opp, pf, pa, idx = game
            sacked = int(((track.boxes.get(g["id"]) or {}).get("team", [{}, {}])[idx] or {}).get("sacked", 0))
            facts = {"Tc": ctx.city(t["team"]), "k": t["week"], "k_n": num(t["n"]), "n": num(sacked),
                     "n_t": plural(sacked, "sack") if sacked else "no sacks", "score": f"{max(pf, pa)}-{min(pf, pa)}"}
            if sacked <= 1 and pf > pa:
                t["settled"] = True
                ctx.post(season, cal, persona("BigTHolloway"), Say("bigt_credit", facts), teams=[t["team"]],
                         quote=quote, importance=34)
            elif sacked >= 5:
                t["settled"] = True
                ctx.post(season, cal, persona("BigTHolloway"), Say("bigt_again", facts), teams=[t["team"]],
                         quote=quote, importance=34)
        elif t["kind"] == "fan_bench":
            # A fan who wanted the quarterback benched, three games later.
            r = track.qb_recent(t["pid_"], w)
            p = ctx.player(t["pid_"])
            gl = track.games_of(t["pid_"], w)
            if not r or not p or not gl or gl[-1][0] != w or len([x for x in gl if x[0] > t["week"]]) < 3:
                if w - t["week"] > 8:
                    t["settled"] = True
                continue
            t["settled"] = True
            facts = {"last": p.last_name, "k": t["week"], "rating": f"{r['rating']:.1f}"}
            if r["rating"] >= 95:
                ctx.post(season, cal, t["who"], Say("fan_crow", facts), teams=[t["team"]], players=[p.id],
                         quote=quote, importance=30)
            elif r["rating"] < 70:
                ctx.post(season, cal, t["who"], Say("fan_again", facts), teams=[t["team"]], players=[p.id],
                         quote=quote, importance=28)
        elif t["kind"] == "fan_believe":
            # A fan who called a breakout, a month later.
            if w - t["week"] < 4:
                continue
            t["settled"] = True
            p = ctx.player(t["pid_"])
            if not p or len([x for x in track.games_of(p.id, w) if x[0] > t["week"]]) < 3:
                continue
            from .news import impact, season_amount
            tot = track.totals(p.id, w)
            main = max(impact(tot).items(), key=lambda kv: kv[1], default=(None, 0))[0]
            stat = {"pass": "pass_yds", "rush": "rush_yds", "rec": "rec_yds", "def": "sacks"}.get(main)
            if stat and tot.get(stat):
                ctx.post(season, cal, t["who"], Say("fan_called", {
                    "last": p.last_name, "k": t["week"], "season_amount": season_amount(stat, tot[stat])}),
                    teams=[t["team"]], players=[p.id], quote=quote, importance=28)
    # Walt's weekly column-in-a-bit: the week's most old-school (or least) game.
    best = None
    month = "December" if w >= 13 else "November" if w >= 9 else "October" if w >= 4 else "September"
    for g in games:
        b = track.boxes.get(g["id"])
        if not b or g["week"] != w:
            continue
        hs, as_ = g["home_score"], g["away_score"]
        W, L = (g["home"], g["away"]) if hs >= as_ else (g["away"], g["home"])
        ws, ls = max(hs, as_), min(hs, as_)
        wi, li = (0, 1) if W == g["home"] else (1, 0)
        rush = int(b["team"][wi].get("rush_yds", 0))
        give = int(b["team"][li].get("int_thrown", 0) + b["team"][li].get("fum_lost", 0))
        facts = {"Wc": ctx.city(W), "Lc": ctx.city(L), "ws": ws, "ls": ls, "score": f"{ws}-{ls}", "rw": rush,
                 "total": ws + ls, "give_n": num(give), "month": month}
        for name, score in (("walt_lowscore", 30 - (ws + ls)), ("walt_shootout", (ws + ls) - 70),
                            ("walt_rush", (rush - 220) / 4), ("walt_turnovers", (give - 4) * 6)):
            if score > 0 and (best is None or score > best[0]):
                best = (score, name, facts, [W, L])
    if best and rng.random() < 0.8:
        ctx.post(season, cal, persona("WaltBrennan"), Say(best[1], best[2]), teams=best[3], importance=33)
    _rematch_week(ctx, season, track, w, cal)
    _player_week(ctx, season, track, w, cal)


def _rematch_week(ctx, season, track, w, cal):
    """Before a rematch, the side that lost the first meeting hasn't forgotten."""
    for g in track.schedule:
        if g["week"] != w + 1:
            continue
        for me, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
            prev = track.meetings(me, opp, w + 1)
            if not prev:
                continue
            pw, _pg, _o, pf, pa, _i = prev[-1]
            rng = random.Random(f"rematch-{ctx.salt}-{season}-{w}-{me}")
            if pf < pa and rng.random() < 0.6:
                ctx.post(season, cal + 0.1, ctx.fan(me, rng, TROLL), Say("fan_rematch", {
                    "k": pw, "Opp": ctx.nick(opp), "Me": ctx.nick(me), "their": pa, "my": pf, "tag": tag(ctx, me)}),
                    teams=[me, opp], importance=22)


def _player_week(ctx, season, track, w, cal):
    """Midweek: the weird and cryptic players post whatever is on their minds; bold
    players guarantee wins, and last week's guarantees are settled."""
    guarantees = ctx.__dict__.setdefault("guarantees", [])
    # Settle the guarantees made for this week's games.
    for gu in guarantees:
        if gu["season"] != season or gu["week"] != w or gu.get("settled"):
            continue
        gu["settled"] = True
        game = next((x for x in track.team_games.get(gu["team"], ()) if x[0] == w), None)
        if not game:
            continue
        _w, _g, opp, pf, pa, _i = game
        quote = {"of": gu["id"], "when": f"Week {w - 1}"}
        p = ctx.player(gu["pid"])
        facts = {"name": p.name, "last": p.last_name, "Tc": ctx.city(gu["team"]), "opp": ctx.nick(opp),
                 "score": f"{max(pf, pa)}-{min(pf, pa)}", "pf": pf, "pa": pa}
        if pf > pa:
            ctx.post(season, 5 + w + 0.62, ctx.player_voice(p), Say("player_told", facts), teams=[gu["team"]],
                     players=[p.id], quote=quote, importance=36)
        elif pf < pa:
            ctx.post(season, 5 + w + 0.62, persona("ReceiptsFB"), Say("receipts_player", facts),
                     teams=[gu["team"], opp], players=[p.id], quote=quote, importance=42)
    # This week's players, as they were this week (so a player who's since moved posts for the right team).
    played, lines = {}, {}
    for pid, gl in track.player_games.items():
        last = gl[-1] if gl[-1][0] <= w else next((x for x in reversed(gl) if x[0] <= w), None)
        if last and last[0] == w:
            played[pid], lines[pid] = last[2], last[3]
    nxt = {t for g in track.schedule if g["week"] == w + 1 for t in (g["home"], g["away"])}
    made = 0
    for pid in sorted(played):
        p = ctx.player(pid)
        tid = played[pid]
        if p is None or not _voice_ok(ctx, p, lines[pid]):
            continue
        voice = personality(ctx, p)
        if not voice:
            continue
        rng = random.Random(f"midweek-{ctx.salt}-{season}-{w}-{pid}")
        if voice in ("weird", "cryptic") and rng.random() < 0.12:
            facts = {"city": ctx.city(tid), "cold": w >= 12 and ctx.teams[tid].abbrev in COLD_CITIES,
                     "bye": tid not in nxt}
            ctx.post(season, cal, ctx.player_voice(p), Say(f"player_{voice}", facts), teams=[tid],
                     players=[p.id], importance=30)
        elif voice == "bold" and tid in nxt and made < 2 and rng.random() < 0.08:
            g = next(g for g in track.schedule if g["week"] == w + 1 and tid in (g["home"], g["away"]))
            opp = g["away"] if g["home"] == tid else g["home"]
            pid_ = ctx.post(season, cal + 0.05, ctx.player_voice(p), Say("player_guarantee", {"opp": ctx.nick(opp)}),
                            teams=[tid, opp], players=[p.id], importance=40)
            guarantees.append({"season": season, "week": w + 1, "team": tid, "pid": p.id, "id": pid_})
            made += 1


COLD_CITIES = {"BOS", "NYK", "PHI", "BUF", "PIT", "CLE", "DET", "CHI", "MIN", "DEN", "CIN", "IND", "KCY", "WAS",
               "BAL", "STL"}


def react_rankings(ctx, season, cal, top_tid, rng, rec=""):
    if rng.random() < 0.4:
        ctx.post(season, cal, persona("RexTakes"), Say("rex_rank", {"top": ctx.city(top_tid), "rec": rec}),
                 teams=[top_tid], importance=34)


def react_pick(ctx, season, cal, d, q, rng, first_of_team=False):
    """A first-round pick: the team announces it; fans and their celebrity react."""
    from .news import POS_WORD
    tid = d["team"]
    f = {"pick": d["pick"], "season": season, "T": ctx.full(tid), "pos": q.position, "name": q.name,
         "college": q.college, "city": ctx.city(tid), "Nick": ctx.nick(tid), "tag": tag(ctx, tid), "last": q.last_name,
         "pos_word": POS_WORD.get(q.position, q.position), "first_of_team": first_of_team}
    top = ctx.post(season, cal, team_account(ctx, tid), Say("team_pick", f), teams=[tid], players=[q.id],
                   importance=36 if d["pick"] > 1 else 60)
    ctx.post(season, cal, ctx.fan(tid, rng, rng.choice([HOMER, WORRIER])), Say("fan_pick_reply", f),
             teams=[tid], reply_to=top, importance=8)
    c = celebrity(ctx, tid)
    if c:
        ctx.post(season, cal, c[0], Say("celeb_draft", f), teams=[tid], players=[q.id], importance=30)


def react_last_pick(ctx, season, cal, d, q, rng):
    ctx.post(season, cal, persona("GridironMemes"), Say("meme_irrelevant", {
        "name": q.name, "pick": d["pick"], "season": season, "pos": q.position, "college": q.college}),
        teams=[d["team"]], players=[q.id], importance=30)


def react_clinch(ctx, season, cal, tid, what, rng, rec="", left_t=""):
    t = ctx.teams[tid]
    f = {"city": t.city, "tag": tag(ctx, tid), "div": t.division, "champ": ctx.champ_name(season), "rec": rec,
         "left_t": left_t or "games", "conf": f"{t.conference} Conference", "Nick": t.nickname}
    if what in ("berth", "div", "top"):
        ctx.post(season, cal, team_account(ctx, tid), Say(f"team_clinch_{what}", f), teams=[tid], importance=50)
        c = celebrity(ctx, tid)
        if c:
            ctx.post(season, cal, c[0], Say("celeb_clinch", f), teams=[tid], importance=34)


def react_sign(ctx, season, cal, tid, p, rng, back=False, extra=None):
    f = dict({"city": ctx.city(tid), "name": p.name, "last": p.last_name, "pos": p.position, "tag": tag(ctx, tid),
              "Nick": ctx.nick(tid), "exp": p.experience >= 4, "exp_t": f"{p.experience} years",
              "list_name": "injured reserve", "prev": False, "prev_team": "", "out": False, "out_t": ""},
             **(extra or {}))
    ctx.post(season, cal, team_account(ctx, tid), Say("team_back" if back else "team_sign", f),
             teams=[tid], players=[p.id], importance=24)


def react_retire(ctx, season, cal, tid, p, rng):
    from .news import num
    ctx.post(season, cal, team_account(ctx, tid), Say("team_retire", {
        "name": p.name, "Nick": ctx.nick(tid), "tag": tag(ctx, tid),
        "seasons_t": f"{num(p.experience).capitalize()} seasons"}), teams=[tid], players=[p.id], importance=30)


# ---------------------------------------------------------------------------
# The timeline
# ---------------------------------------------------------------------------

def category(role):
    if role == "Outlet":
        return "headlines"
    if role == "Team account":
        return "teams"
    if role == "Insider" or role.endswith("beat writer"):
        return "reporters"
    if role == "Stats":
        return "stats"
    if role == "Player":
        return "players"
    if role.endswith(" fan") and "·" not in role:
        return "fans"
    if "·" in role:
        return "celebs"
    return "takes"


def _followers(bit, league):
    h = bit["handle"].lstrip("@")
    if h in PERSONAS:
        return PERSONAS[h][3]
    r = random.Random(f"followers-{h}")
    cat = bit["cat"]
    if cat == "teams":
        return r.randint(600, 2200) * 1000
    if cat == "celebs":
        return r.randint(2, 40) * 1_000_000 + r.randint(0, 999) * 1000
    if cat == "reporters":
        return r.randint(40, 140) * 1000
    if cat == "players":
        # Famous players have big followings (popularity: the game's own 1-99 rating of how well known he is).
        try:
            pop = league.player(bit["players"][0]).popularity if bit["players"] else 20
        except (KeyError, ValueError):
            pop = 20
        return int((3000 + pop * pop * 120) * r.uniform(0.7, 1.3))
    return r.randint(4, 250) * 100


def short_count(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n // 1000}K"
    if n >= 1000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return str(n)


def _engage(bit, followers):
    r = random.Random(f"engage-{bit['id']}")
    rate = {"headlines": 0.0012, "teams": 0.004, "reporters": 0.003, "takes": 0.004, "stats": 0.0015,
            "players": 0.01, "fans": 0.004, "celebs": 0.003}[bit["cat"]]
    likes = followers * rate * (0.3 + bit["importance"] / 50) * r.lognormvariate(0, 0.6)
    if bit["cat"] == "fans" and r.random() < 0.03:
        likes *= 40            # now and then a fan's bit goes viral
    likes = int(likes) + r.randint(0, 9)
    return {"likes": likes, "rebits": int(likes * r.uniform(0.08, 0.25)),
            "reply_count": int(likes * r.uniform(0.02, 0.08)) + len(bit.get("replies", ()))}


ARTICLE_ACCOUNTS = {"game": ("LeagueWire", "wire_game"), "performance": ("LeagueWire", "wire_news"),
                    "milestone": ("GridironDaily", "daily_feature"), "storyline": ("GridironDaily", "daily_feature"),
                    "rankings": ("GridironDaily", "daily_feature"), "season": ("LeagueWire", "wire_news"),
                    "awards": ("LeagueWire", "wire_news"), "playoffs": ("LeagueWire", "wire_news"),
                    "draft": ("LeagueWire", "wire_news"), "retirement": ("LeagueWire", "wire_news"),
                    "moves": ("LeagueWire", "wire_news"), "injury": ("LeagueWire", "wire_news"),
                    "business": ("LeagueWire", "wire_news")}
_LEADS = {"wire_game": ("", "RECAP: ", "FINAL: "), "wire_news": ("", "NEWS: ", "JUST IN: "),
          "daily_feature": ("", "NEW: ", "Read: ")}


def _article_shape(text, item, league, teams_re):
    """The article bit's words with its names, teams and numbers taken out."""
    s = text.replace("Hall of Fame", "HOF")
    for pid in item["players"][:12]:
        try:
            p = league.player(pid)
        except (KeyError, ValueError):
            continue
        s = s.replace(p.name, "N").replace(p.last_name, "N")
    s = teams_re.sub("T", s)
    return _NUMBER_WORDS.sub("9", re.sub(r"\d[\d,.]*", "9", s)).lower()


_NUMBER_WORDS = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|first|second|third|"
                           r"fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b", re.I)


# Sentence ends, but not "St. Louis" or "No. 1".
_SENTENCE = re.compile(r"(?<!\bSt\.)(?<!\bNo\.)(?<!\bJr\.)(?<=[.!?])\s")


def _teams_re(league):
    names = tuple(sorted({w for t in league.teams for w in (t.name, t.city, t.nickname)}, key=len, reverse=True))
    if _TEAMS_RE.get("key") != names:
        _TEAMS_RE.update(key=names, re=re.compile("|".join(re.escape(w) for w in names)))
    return _TEAMS_RE["re"]


_TEAMS_RE = {}


def _move_rank(sentence):
    """Which of a team's moves leads its transactions bit (lowest first)."""
    for i, words in enumerate(("injured reserve", "Released", "Waived", "Claimed", "Activated", "Signed", "Promoted")):
        if words in sentence and "practice squad" not in sentence:
            return i
    return 9 if sentence.startswith("Elevated") else 8


def _article_bits(items, league):
    """Every story as an outlet's bit, in calendar order. A written story leads with
    its first sentence (the headline goes on the article card); a list (rankings,
    an injury report, a team's moves) leads with its headline and its first line.
    No two article bits say the same thing, and the same shape of words isn't
    used twice in a week."""
    out = []
    seen, shapes = set(), set()
    teams_re = _teams_re(league)
    for item in sorted(items, key=lambda x: (x["season"], x["cal"], -x["importance"], x["id"])):
        rng = random.Random(f"article-{item['id']}")
        key, words = ARTICLE_ACCOUNTS.get(item["kind"], ("LeagueWire", "wire_news"))
        name, role, _bio, _f = PERSONAS[key]
        body = item["body"].split("\n")
        sents = _SENTENCE.split(body[0])
        first = sents[0]
        cands = []
        m = re.match(r"(.+) transactions: (.+)$", item["headline"])
        if m and len(body) == 1:
            # A team's week of moves: lead with the most notable one.
            best = min(sents, key=_move_rank).rstrip(".")
            cands.append(f"{m.group(1)}, {m.group(2)}: {best[:1].lower() + best[1:]}"
                         + (f" (+{len(sents) - 1} more)" if len(sents) > 1 else ""))
        elif len(body) == 1 and 40 <= len(first) <= 240:
            cands.append(first)
        elif len(body) > 1:
            numbered = next((x.strip() for x in body if re.match(r"\d+\. ", x.strip())), None)
            line = numbered or (body[1].strip() if len(body[0]) > 140 or ":" in body[0] else body[0].strip())
            if 0 < len(line) <= 160:
                more = len(body) - 2 if line == body[1].strip() else len(body) - 1
                cands.append(f"{item['headline']}: {line.rstrip('.')}" + (f" (+{more} more)" if more > 0 else ""))
        leads = list(_LEADS[words])
        rng.shuffle(leads)
        heads = [lead + item["headline"] for lead in leads]
        cands = (heads + cands) if rng.random() < 0.25 else (cands + heads)
        text = None
        week = (item["season"], int(item["cal"]))
        # (Shapes only matter for stories that can make For you.)
        shaped = item["importance"] >= 25
        for c in cands:
            if c.lower() in seen:
                continue
            if not shaped or (week, _article_shape(c, item, league, teams_re)) not in shapes:
                text = c
                break
        if text is None:
            text = next((c for c in cands if c.lower() not in seen), None)
        if text is None:
            continue
        seen.add(text.lower())
        shape = _article_shape(text, item, league, teams_re) if shaped else None
        shapes.add((week, shape))
        out.append({"id": "a-" + item["id"], "season": item["season"], "cal": item["cal"], "when": item["when"],
                    "name": name, "handle": "@" + key, "role": role, "team": None, "text": text,
                    "teams": item["teams"], "players": item["players"], "importance": item["importance"],
                    "article": item, "reply_to": None, "quote": None, "_shape": shape})
    return out


def _wobble(key, size):
    """A fixed nudge between -size and +size for this key (cheaper than seeding a Random)."""
    return (zlib.crc32(key.encode()) % 10_001) / 10_000 * 2 * size - size


def _for_you(tops, league):
    """About FOR_YOU_PER_WEEK top-level bits a week, mixed by kind of account (FOR_YOU_MIX)."""
    weeks = {}
    for b in tops:
        if b["importance"] >= FOR_YOU_FLOOR:
            weeks.setdefault((b["season"], int(b["cal"])), []).append(b)
    keep = []
    for week_bits in weeks.values():
        score = lambda b: -(b["importance"] + _wobble(b["id"], 6))
        week_bits.sort(key=score)
        # Two outlet bits shaped the same ("X has retired after 12 seasons", or two teams'
        # "draft class" lists) don't both make it.
        chosen, by_cat, shapes = set(), {}, set()

        def take(b):
            if b["cat"] == "headlines":
                if b.get("_shape") is None:
                    b["_shape"] = _article_shape(b["text"], b["article"], league, _teams_re(league))
                if b.get("_hshape") is None:
                    b["_hshape"] = _article_shape(b["article"]["headline"], b["article"], league, _teams_re(league))
                if b["_shape"] in shapes or b["_hshape"] in shapes:
                    return
                shapes.update((b["_shape"], b["_hshape"]))
            chosen.add(b["id"])
            by_cat[b["cat"]] = by_cat.get(b["cat"], 0) + 1

        for b in week_bits:
            if by_cat.get(b["cat"], 0) < round(FOR_YOU_MIX.get(b["cat"], 0) * FOR_YOU_PER_WEEK):
                take(b)
        for b in week_bits:
            if len(chosen) >= FOR_YOU_PER_WEEK:
                break
            if b["id"] not in chosen:
                take(b)
        keep += [b for b in week_bits if b["id"] in chosen]
    return keep


def timeline(league, past_games=None, team_id=None, player_id=None, season=None, cats=None, min_importance=None):
    """Everything the Bitter page shows:
    {"bits": [top-level bits, newest first, each with its "replies"],
     "trending": [(label, count text)], "follow": [account dicts]}."""
    from . import news
    data = news.build(league, past_games)
    articles = data.get("_articles")
    if articles is None:
        articles = data["_articles"] = _article_bits(data["items"], league)   # cached with the build
    bits = [dict(a) for a in articles] + [dict(p) for p in data["posts"]]
    by_id = {}
    for b in bits:
        b["cat"] = category(b["role"])
        b.setdefault("reply_to", None)
        b.setdefault("quote", None)
        b["replies"] = []
        by_id[b["id"]] = b
    tops = []
    for b in bits:
        parent = by_id.get(b["reply_to"]) if b["reply_to"] else None
        if parent is not None:
            parent["replies"].append(b)
        else:
            tops.append(b)
    for_you = min_importance is None and team_id is None and player_id is None
    floor = min_importance or 0

    def keep(b):
        if season is not None and b["season"] != season:
            return False
        if team_id is not None and team_id not in b["teams"] and b.get("team") != team_id:
            return False
        if player_id is not None and player_id not in b["players"]:
            return False
        if cats is not None and b["cat"] not in cats:
            return False
        return b["importance"] >= floor

    shown = [b for b in tops if keep(b)]
    if for_you:
        shown = _for_you(shown, league)
    # Newest week first; within a week, the bigger bits first, but loosely, so the
    # outlets' articles and everybody else's takes mix the way a real feed does.
    jitter = lambda b: _wobble("order" + b["id"], 12)
    shown.sort(key=lambda b: (-b["season"], -int(b["cal"]), -(b["importance"] + jitter(b))))
    for b in shown:
        for x in [b] + b["replies"]:
            if "likes" not in x:
                x["followers"] = _followers(x, league)
                x.update(_engage(x, x["followers"]))
        b["replies"].sort(key=lambda x: -x["likes"])
    return {"bits": shown, "trending": trending(shown, league), "follow": follow(league)}


def trending(bits, league):
    """What's trending in the latest weeks shown: hashtags, players and teams, by engagement."""
    if not bits:
        return []
    # The latest week with games in it (or simply the latest week).
    weeks = sorted({(b["season"], int(b["cal"])) for b in bits if b.get("kind") == "final"}
                   or {(b["season"], int(b["cal"])) for b in bits})
    recent = set(weeks[-2:])
    score = {}
    for b in bits:
        if (b["season"], int(b["cal"])) not in recent:
            continue
        w = b.get("likes", 0) + 3 * b.get("rebits", 0)
        for h in re.findall(r"#\w+", b["text"]):
            score[h] = score.get(h, 0) + w
        # People and teams the bit is about (only a few, so league-wide lists don't count).
        if len(b["players"]) <= 3:
            for pid in b["players"]:
                try:
                    name = league.player(pid).name
                except (KeyError, ValueError):
                    continue
                score[name] = score.get(name, 0) + w // 2
        if len(b["teams"]) <= 2:
            for tid in b["teams"]:
                t = next((t for t in league.teams if t.id == tid), None)
                if t:
                    score[t.nickname] = score.get(t.nickname, 0) + w // 3
    top = sorted(score.items(), key=lambda kv: -kv[1])[:8]
    return [(label, f"{short_count(max(120, v // 6))} bits") for label, v in top]


def follow(league):
    keys = ["RexTakes", "GridironMemes", "ReceiptsFB", "FantasyFreddie", "BigTHolloway", "WaltBrennan"]
    return [{"name": PERSONAS[k][0], "handle": "@" + k, "bio": PERSONAS[k][2],
             "followers": short_count(PERSONAS[k][3])} for k in keys]


def initials(name):
    words = [w for w in re.findall(r"[A-Za-z]+", name) if w[0].isupper()]
    return ((words[0][0] + (words[-1][0] if len(words) > 1 else "")) if words else name[:2]).upper()


def avatar_color(handle):
    r = random.Random(f"avatar-{handle}")
    return f"hsl({r.randint(0, 359)}, {r.randint(35, 60)}%, {r.randint(32, 46)}%)"


def verified(bit):
    return bit["cat"] in ("headlines", "teams", "reporters", "takes", "stats", "celebs") or \
        (bit["cat"] == "players" and bit.get("followers", 0) >= 100_000)
