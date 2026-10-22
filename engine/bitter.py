# bitter.py
# Bitter: the league's social media site (the News tab). Accounts post "bits":
# news outlets share every story as a clickable article, insiders break news,
# team accounts post finals, a hot-take TV host makes predictions (and a
# receipts account holds him to them), a grumpy columnist, a fantasy guy, a
# former lineman who watches film, a meme account, fictional celebrities who
# root for teams, players and fans. Bits get replies, quote-bits, likes and
# rebits, and the page shows what's trending.
#
# engine/news.py works out what happened (it calls the react_* functions here
# with the facts); this file decides who reacts and how, and assembles the
# timeline the screen shows. Wording lives in engine/bitter_words.py.
#
# Rules: every account is invented (none imitates a real person); PG-13 (no
# swearing); opinions are fine, made-up facts are not. Likes, rebits, replies
# and follower counts are invented flavor, the same every time for a league.
# Feel choices here are PROVISIONAL, for Blake's review (docs/news-design.md).

import random
import re

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

# How important a bit must be (0-100) to show in "For you", by kind of account.
FOR_YOU_BARS = {"headlines": 25, "teams": 25, "reporters": 25, "stats": 25, "takes": 18, "players": 22,
                "celebs": 18, "fans": 14}

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


def player_post(ctx, season, cal, p, tid, won, rng, imp, opp_tid=None):
    """A player's own bit after his game, in his voice."""
    voice = personality(ctx, p)
    f = {"opp": ctx.nick(opp_tid) if opp_tid else "them", "city": ctx.city(tid)}
    if voice == "bold":
        text = ctx.writer.say("player_win_bold" if won else "player_loss_bold", rng, f)
    elif voice == "cryptic" and (not won or rng.random() < 0.5):
        text = ctx.writer.say("player_cryptic", rng, f)
    elif voice == "weird" and rng.random() < 0.5:
        text = ctx.writer.say("player_weird", rng, f)
    else:
        text = ctx.writer.say("player_win" if won else "player_loss", rng, f)
    return ctx.post(season, cal, ctx.player_voice(p), text, teams=[tid], players=[p.id],
                    importance=imp + (6 if voice else 0))


def _division_rivals(ctx, tid):
    t = ctx.teams[tid]
    return [o for o in ctx.teams.values() if o.conference == t.conference and o.division == t.division and o.id != tid]


# ---------------------------------------------------------------------------
# Reactions (called from engine/news.py with the facts it already worked out)
# ---------------------------------------------------------------------------

def react_game(ctx, season, cal, phase, g, f, W, L, sp, lp, imp, rng, tw_, tl_, star_def=None, lines=None):
    """Team accounts, fans, the TV host, memes, celebrities and analysts react to a game."""
    from .news import num
    W_ = ctx.writer
    tie = f.get("tie")
    week = g["week"]
    if phase == "preseason" or tie:
        return
    ws, ls = f["ws"], f["ls"]
    margin = ws - ls
    champ = phase == "playoffs" and week == 5
    base = {"tag": tag(ctx, W), "city": ctx.city(W), "CITY": ctx.city(W).upper(), "Nick": ctx.nick(W),
            "NICK": ctx.nick(W).upper(), "OPP": ctx.nick(L).upper(), "opp": ctx.nick(L), "score": f["score"],
            "champ": f["champ"], "star_last": sp.last_name if sp else "", "star": bool(sp)}
    # The winner's team account, with fans replying.
    team_f = dict(base, me=ctx.nick(W), them=ctx.nick(L), my=ws, their=ls, rec=f.get("wrec", ""),
                  streak3=bool(f.get("wstreak")), streak_n=(f.get("n_w") or "").capitalize(), close=margin <= 3,
                  div="")
    bucket = "team_champ" if champ else ("team_playoff_win" if phase == "playoffs" else "team_win")
    top = ctx.post(season, cal, team_account(ctx, W), W_.say(bucket, rng, team_f), teams=[W, L],
                   players=[sp.id] if sp else (), importance=imp - 2, kind="final")
    ctx.post(season, cal, ctx.fan(W, rng, HOMER), W_.say("fan_reply_win", rng, base), teams=[W], reply_to=top,
             importance=10)
    if rng.random() < 0.5:
        ctx.post(season, cal, ctx.fan(L, rng, TROLL), W_.say("fan_salty", rng, base), teams=[L], reply_to=top,
                 importance=8)
    # The loser's account.
    if rng.random() < 0.6 or phase == "playoffs":
        lf = dict(base, me=ctx.nick(L), them=ctx.nick(W), my=ls, their=ws, star_last=lp.last_name if lp else "",
                  star=bool(lp))
        ltop = ctx.post(season, cal, team_account(ctx, L), W_.say("team_loss", rng, lf), teams=[L, W],
                        importance=imp - 12, kind="final")
        ctx.post(season, cal, ctx.fan(L, rng, WORRIER), W_.say("fan_loss", rng, {
            "rec": f.get("lrec", ""), "score": f["score"], "nick": ctx.nick(L)}), teams=[L], reply_to=ltop,
            importance=8)
    # A division rival enjoys it.
    rivals = [o for o in _division_rivals(ctx, L) if o.id != W]
    if rivals and phase == "regular" and rng.random() < 0.3:
        rv = rng.choice(rivals)
        ctx.post(season, cal, ctx.fan(rv.id, rng, TROLL), W_.say("fan_rival_dunk", rng, {"opp": ctx.nick(L)}),
                 teams=[rv.id, L], importance=16)
    # Rex Harmon: takes that get remembered.
    takes = ctx.__dict__.setdefault("rex_takes", [])
    said = {(t["season"], t["team"]) for t in takes}
    if phase == "regular":
        wr = f.get("_wrec"), f.get("_lrec")
        if f.get("upset") and _week_cap(ctx, "rex_fraud", season, week, 1):
            ctx.post(season, cal, persona("RexTakes"), W_.say("rex_fraud", rng, f), teams=[W, L], importance=40)
        if (f.get("wstreak") and wr[0] and wr[0][1] <= 1 and sum(wr[0][:3]) >= 5 and (season, W) not in said
                and _week_cap(ctx, "rex", season, week, 2)):
            text = W_.say("rex_champ", rng, {"Tc": ctx.city(W), "champ": f["champ"]})
            pid = ctx.post(season, cal, persona("RexTakes"), text, teams=[W], importance=44)
            takes.append({"season": season, "week": week, "team": W, "kind": "champ", "text": text, "id": pid})
        lr = wr[1]
        if (lr and sum(lr[:3]) >= 4 and lr[0] + 0.5 * lr[2] <= 0.25 * sum(lr[:3]) and (season, L) not in said
                and _week_cap(ctx, "rex", season, week, 2)):
            text = W_.say("rex_done", rng, {"Tc": ctx.city(L), "rec": f.get("lrec", "")})
            pid = ctx.post(season, cal, persona("RexTakes"), text, teams=[L], importance=44)
            takes.append({"season": season, "week": week, "team": L, "kind": "done", "text": text, "id": pid})
    # Memes.
    mf = dict(f, kicker=f.get("_kicker", ""))
    memes = []
    if ls == 0:
        memes.append("meme_shutout")
    if margin >= 30:
        memes.append("meme_blowout")
    if f.get("ot"):
        memes.append("meme_ot")
    if f.get("max_def", 0) >= 17:
        memes.append("meme_comeback")
    if f.get("winless") and f.get("_lrec") and f["_lrec"][1] >= 5:
        memes.append("meme_winless")
    if f.get("_kicker"):
        memes.append("meme_kicker")
    if f.get("lstreak") and f.get("_lrec") and f["_lrec"][3][-1:] == "L" and rng.random() < 0.4:
        memes.append("meme_streak_loss")
    if f.get("wstreak") and rng.random() < 0.3:
        memes.append("meme_streak_win")
    if champ:
        memes.append("meme_champ")
    if memes and (champ or rng.random() < 0.6) and _week_cap(ctx, "meme", season, cal, 4):
        ctx.post(season, cal, persona("GridironMemes"), W_.say(rng.choice(memes), rng, mf), teams=[W, L],
                 importance=34)
    # Celebrities.
    cw = celebrity(ctx, W)
    if cw:
        who, style = cw
        big = (phase == "playoffs" or margin >= 17 or f.get("wstreak") or f.get("took_first")
               or L in [o.id for o in _division_rivals(ctx, W)] or rng.random() < 0.2)
        if champ:
            ctx.post(season, cal, who, W_.say("celeb_champ", rng, base), teams=[W], importance=60)
        elif margin <= 3 or f.get("ot"):
            # A nail-biter: "please, for my health".
            ctx.post(season, cal, who, W_.say("celeb_win_close", rng, base), teams=[W], importance=38)
        elif big:
            name = f"celeb_win_{style}" if rng.random() < 0.65 else "celeb_win"
            ctx.post(season, cal, who, W_.say(name, rng, base), teams=[W], importance=36)
    cl = celebrity(ctx, L)
    if cl and (phase == "playoffs" or rng.random() < 0.35):
        ctx.post(season, cal, cl[0], W_.say("celeb_loss", rng, {"Nick": ctx.nick(L)}), teams=[L], importance=26)
    # The league's louder (and stranger) players speak up after the game.
    for pid, line in (lines or {}).items():
        p = ctx.player(pid)
        tid = line.get("team")
        if p is None or tid not in (W, L) or not ctx.notable(p, tid):
            continue
        voice = personality(ctx, p)
        won = tid == W
        prng = random.Random(f"pvoice-{ctx.salt}-{g['id']}-{pid}")
        if (voice == "bold" and prng.random() < (0.3 if won else 0.2)) or \
                (voice == "cryptic" and not won and prng.random() < 0.3):
            player_post(ctx, season, cal, p, tid, won, prng, 26, L if won else W)
    # Big T on the trenches.
    if tl_["sacked"] >= 5 and rng.random() < 0.5 and _week_cap(ctx, "bigt", season, week, 2):
        ctx.post(season, cal, persona("BigTHolloway"), W_.say("bigt_sacks", rng, dict(f, n=num(tl_["sacked"]))),
                 teams=[W, L], importance=32)
    elif tw_["rush"] >= 200 and rng.random() < 0.5 and _week_cap(ctx, "bigt", season, week, 2):
        ctx.post(season, cal, persona("BigTHolloway"), W_.say("bigt_rush", rng, f), teams=[W], importance=32)
    elif star_def and rng.random() < 0.4 and _week_cap(ctx, "bigt", season, week, 2):
        p, got = star_def
        ctx.post(season, cal, persona("BigTHolloway"), W_.say("bigt_def", rng, {"name": p.name, "got": got}),
                 teams=[W], players=[p.id], importance=30)


def react_performance(ctx, season, cal, week, p, tid, stat, got, ints, rng, imp):
    """Fantasy Freddie on the biggest fantasy days (and the worst)."""
    W_ = ctx.writer
    if stat == "pass_int":
        if _week_cap(ctx, "freddie_bust", season, week, 1):
            ctx.post(season, cal, persona("FantasyFreddie"), W_.say("freddie_bust", rng, {
                "last": p.last_name, "ints": ints}), teams=[tid], players=[p.id], importance=30)
        return
    if stat in ("pass_yds", "pass_td", "rush_yds", "rush_td", "rec_yds", "rec_td", "rec") \
            and rng.random() < 0.6 and _week_cap(ctx, "freddie", season, week, 3):
        ctx.post(season, cal, persona("FantasyFreddie"), W_.say("freddie_boom", rng, {
            "last": p.last_name, "got": got}), teams=[tid], players=[p.id], importance=imp - 12)


def react_injury(ctx, season, cal, p, tid, part, vp, rng, imp, parent):
    W_ = ctx.writer
    ctx.post(season, cal, ctx.fan(tid, rng, WORRIER), W_.say("fan_reply_injury", rng, {}), teams=[tid],
             players=[p.id], reply_to=parent, importance=8)
    if p.position in ("QB", "RB", "WR", "TE") and rng.random() < 0.6:
        ctx.post(season, cal, persona("FantasyFreddie"), W_.say("freddie_injury", rng, {
            "name": p.name, "part": part, "vp": vp}), teams=[tid], players=[p.id], reply_to=parent, importance=10)


def react_week(ctx, season, track, w, games):
    """Weekly: receipts on the TV host's old takes, the columnist's column."""
    from . import storylines as SL
    W_ = ctx.writer
    cal = 5 + w + 0.65
    rng = ctx.rng(season, "bitterweek", w)
    for t in ctx.__dict__.get("rex_takes", []):
        if t["season"] != season or t["week"] >= w or t.get("settled"):
            continue
        kind, n = track.streak_of(t["team"], w)
        since = track.record(t["team"], w, since=t["week"])
        quote = {"name": "Rex Harmon", "handle": "@RexTakes", "text": t["text"], "when": f"Week {t['week']}"}
        wrong = (t["kind"] == "done" and kind == "W" and n >= 3) or (t["kind"] == "champ" and kind == "L" and n >= 3)
        if wrong:
            t["settled"] = True
            ctx.post(season, cal, persona("ReceiptsFB"), W_.say("receipts", rng, {
                "Tc": ctx.city(t["team"]), "since_rec": SL.rec_text(since)}), teams=[t["team"]], quote=quote,
                importance=46)
        elif t["kind"] == "done" and w == ctx.n_weeks:
            r = track.record(t["team"], w)
            if SL.pct(r) < 0.5:
                t["settled"] = True
                ctx.post(season, cal, persona("RexTakes"), W_.say("rex_right", rng, {
                    "k": t["week"], "Tc": ctx.city(t["team"]), "rec": SL.rec_text(r)}), teams=[t["team"]],
                    quote=quote, importance=40)
    # Walt's weekly column-in-a-bit: the week's most old-school (or least) game.
    week_games = [x for x in track.team_games.items()]
    best = None
    for g in games:
        b = track.boxes.get(g["id"])
        if not b or g["week"] != w:
            continue
        hs, as_ = g["home_score"], g["away_score"]
        W, L = (g["home"], g["away"]) if hs >= as_ else (g["away"], g["home"])
        ws, ls = max(hs, as_), min(hs, as_)
        wi = 0 if W == g["home"] else 1
        rush = int(b["team"][wi].get("rush_yds", 0))
        facts = {"Wc": ctx.city(W), "Lc": ctx.city(L), "ws": ws, "ls": ls, "score": f"{ws}-{ls}", "rw": rush,
                 "wrec": SL.rec_text(track.record(W, w))}
        for name, score in (("walt_lowscore", 30 - (ws + ls)), ("walt_shootout", (ws + ls) - 70),
                            ("walt_rush", (rush - 220) / 4)):
            if score > 0 and (best is None or score > best[0]):
                best = (score, name, facts, [W, L])
    if best and rng.random() < 0.8:
        ctx.post(season, cal, persona("WaltBrennan"), W_.say(best[1], rng, best[2]), teams=best[3], importance=33)
    _player_week(ctx, season, track, w, cal)


def _player_week(ctx, season, track, w, cal):
    """Midweek: the weird and cryptic players post whatever is on their minds; bold
    players guarantee wins, and last week's guarantees are settled."""
    from . import storylines as SL
    W_ = ctx.writer
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
        quote = {"name": gu["name"], "handle": gu["handle"], "text": gu["text"], "when": f"Week {w - 1}"}
        p = ctx.player(gu["pid"])
        rng = random.Random(f"settle-{ctx.salt}-{season}-{w}-{gu['pid']}")
        if pf > pa:
            ctx.post(season, 5 + w + 0.62, ctx.player_voice(p), W_.say("player_told", rng, {}), teams=[gu["team"]],
                     players=[p.id], quote=quote, importance=36)
        elif pf < pa:
            ctx.post(season, 5 + w + 0.62, persona("ReceiptsFB"), W_.say("receipts_player", rng, {
                "name": p.name, "Tc": ctx.city(gu["team"]), "score": f"{pa}-{pf}"}), teams=[gu["team"], opp],
                players=[p.id], quote=quote, importance=42)
    # This week's players, as they were this week (so a player who's since moved posts for the right team).
    played = {}
    for pid, gl in track.player_games.items():
        last = gl[-1] if gl[-1][0] <= w else next((x for x in reversed(gl) if x[0] <= w), None)
        if last and last[0] == w:
            played[pid] = last[2]
    nxt = {t for g in track.schedule if g["week"] == w + 1 for t in (g["home"], g["away"])}
    made = 0
    for pid in sorted(played):
        p = ctx.player(pid)
        tid = played[pid]
        if p is None or not ctx.notable(p, tid):
            continue
        voice = personality(ctx, p)
        if not voice:
            continue
        rng = random.Random(f"midweek-{ctx.salt}-{season}-{w}-{pid}")
        if voice in ("weird", "cryptic") and rng.random() < 0.12:
            ctx.post(season, cal, ctx.player_voice(p), W_.say(f"player_{voice}", rng, {}), teams=[tid],
                     players=[p.id], importance=30)
        elif voice == "bold" and tid in nxt and made < 2 and rng.random() < 0.08:
            g = next(g for g in track.schedule if g["week"] == w + 1 and tid in (g["home"], g["away"]))
            opp = g["away"] if g["home"] == tid else g["home"]
            text = W_.say("player_guarantee", rng, {"opp": ctx.nick(opp)})
            pid_ = ctx.post(season, cal + 0.05, ctx.player_voice(p), text, teams=[tid, opp], players=[p.id],
                            importance=40)
            who = ctx.player_voice(p)
            guarantees.append({"season": season, "week": w + 1, "team": tid, "pid": p.id, "text": text,
                               "name": who[0], "handle": "@" + who[1], "id": pid_})
            made += 1


def react_rankings(ctx, season, cal, top_tid, rng):
    if rng.random() < 0.4:
        ctx.post(season, cal, persona("RexTakes"), ctx.writer.say("rex_rank", rng, {"top": ctx.city(top_tid)}),
                 teams=[top_tid], importance=34)


def react_pick(ctx, season, cal, d, q, rng):
    """A first-round pick: the team announces it; fans and their celebrity react."""
    W_ = ctx.writer
    tid = d["team"]
    f = {"pick": d["pick"], "season": season, "T": ctx.full(tid), "pos": q.position, "name": q.name,
         "college": q.college, "city": ctx.city(tid), "Nick": ctx.nick(tid), "tag": tag(ctx, tid), "last": q.last_name}
    top = ctx.post(season, cal, team_account(ctx, tid), W_.say("team_pick", rng, f), teams=[tid], players=[q.id],
                   importance=36 if d["pick"] > 1 else 60)
    ctx.post(season, cal, ctx.fan(tid, rng, rng.choice([HOMER, WORRIER])), W_.say("fan_reply_pick", rng, f),
             teams=[tid], reply_to=top, importance=8)
    c = celebrity(ctx, tid)
    if c:
        ctx.post(season, cal, c[0], W_.say("celeb_draft", rng, f), teams=[tid], players=[q.id], importance=30)


def react_last_pick(ctx, season, cal, d, q, rng):
    ctx.post(season, cal, persona("GridironMemes"), ctx.writer.say("meme_irrelevant", rng, {
        "name": q.name, "pick": d["pick"]}), teams=[d["team"]], players=[q.id], importance=30)


def react_clinch(ctx, season, cal, tid, what, rng):
    W_ = ctx.writer
    t = ctx.teams[tid]
    f = {"city": t.city, "tag": tag(ctx, tid), "div": t.division, "champ": ctx.champ_name(season)}
    if what in ("berth", "div", "top"):
        ctx.post(season, cal, team_account(ctx, tid), W_.say(f"team_clinch_{what}", rng, f), teams=[tid],
                 importance=50)
        c = celebrity(ctx, tid)
        if c:
            ctx.post(season, cal, c[0], W_.say("celeb_clinch", rng, f), teams=[tid], importance=34)


def react_sign(ctx, season, cal, tid, p, rng, back=False):
    f = {"city": ctx.city(tid), "name": p.name, "last": p.last_name, "pos": p.position, "tag": tag(ctx, tid)}
    ctx.post(season, cal, team_account(ctx, tid), ctx.writer.say("team_back" if back else "team_sign", rng, f),
             teams=[tid], players=[p.id], importance=24)


def react_retire(ctx, season, cal, tid, p, rng):
    ctx.post(season, cal, team_account(ctx, tid), ctx.writer.say("team_retire", rng, {
        "name": p.name, "Nick": ctx.nick(tid), "tag": tag(ctx, tid)}), teams=[tid], players=[p.id], importance=30)


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


def _article_bit(ctx_writer, item):
    rng = random.Random(f"article-{item['id']}")
    key, words = ARTICLE_ACCOUNTS.get(item["kind"], ("LeagueWire", "wire_news"))
    name, role, _bio, _f = PERSONAS[key]
    # A written story leads with its first sentence (the headline goes on the article
    # card); a list (rankings, a preview, an injury report) leads with its headline.
    first = re.split(r"(?<=[.!?])\s", item["body"].split("\n")[0], maxsplit=1)[0]
    if "\n" not in item["body"] and 40 <= len(first) <= 240 and rng.random() < 0.75:
        text = first
    else:
        text = ctx_writer.say(words, rng, {"headline": item["headline"]})
    return {"id": "a-" + item["id"], "season": item["season"], "cal": item["cal"], "when": item["when"],
            "name": name, "handle": "@" + key, "role": role, "team": None, "text": text, "teams": item["teams"],
            "players": item["players"], "importance": item["importance"], "article": item, "reply_to": None,
            "quote": None}


def timeline(league, past_games=None, team_id=None, player_id=None, season=None, cats=None, min_importance=None):
    """Everything the Bitter page shows:
    {"bits": [top-level bits, newest first, each with its "replies"],
     "trending": [(label, count text)], "follow": [account dicts]}."""
    from . import news
    from .news_words import Writer, BANK
    from .bitter_words import BITTER_BANK
    data = news.build(league, past_games)
    writer = Writer({**BANK, **BITTER_BANK})
    bits = [_article_bit(writer, x) for x in data["items"]] + [dict(p) for p in data["posts"]]
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
    # "For you" (the league-wide view): the bigger news, plus plenty of personality
    # (Blake: "as much news as will make it feel real"). PROVISIONAL.
    bars = FOR_YOU_BARS if min_importance is None and team_id is None and player_id is None else None
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
        return b["importance"] >= (bars[b["cat"]] if bars else floor)

    shown = [b for b in tops if keep(b)]
    # Newest week first; within a week, the bigger bits first, but loosely, so the
    # outlets' articles and everybody else's takes mix the way a real feed does.
    jitter = lambda b: random.Random(f"order-{b['id']}").uniform(-12, 12)
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
