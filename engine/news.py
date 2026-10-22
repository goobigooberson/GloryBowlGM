# news.py
# The News tab: news stories and social media posts about the league, all
# built from what the league already records, so a save needs nothing new:
#   - game results and box scores (league.preseason / schedule / playoffs,
#     league.boxes; past seasons' games from the save's history file, if the
#     screen passes them in)
#   - season and career stats (league.career), team history and champions
#   - injuries (league.injury_history) and this week's game-day statuses
#   - roster moves (league.transactions), the draft (league.draft_history),
#     retirements (Player.retired), captains, the offseason report
# Nothing here changes the league. The same league always gives the same
# stories in the same words: each story's dice are seeded by what it's about.
#
# Rules (CLAUDE.md, Blake):
#   - Never invent facts. Every number and event comes from the data above.
#     Fans' opinions and plain colour ("a rough afternoon") are fine; made-up
#     events, numbers or quotes about decisions are not.
#   - Never mention hidden ratings (consistency, durability, Generational
#     status, development). Ratings only decide which players are newsworthy,
#     on the Oct 22 shown scale (scale.legacy_shown), and are never printed.
#   - Varied wording: each kind of story has several ways to say it, and the
#     same way isn't used twice in the same week while others are unused.
#
# Feel choices (how much news, what counts as big, the outlet's weekly
# standouts, the social personas) are PROVISIONAL, for Blake's review
# (docs/news-design.md).

import random
import re
from collections import defaultdict

from . import depth
from . import injuries as I
from . import names
from . import playoffs as po
from . import season as S
from . import storylines as SL
from .news_words import Say, Writer
from .scale import legacy_shown
from .sim.text import short_name

# ---- Knobs (PROVISIONAL, for Blake's review) ---------------------------------
TYPES = {
    "game": "Game stories",
    "performance": "Big performances",
    "milestone": "Milestones and records",
    "injury": "Injuries",
    "moves": "Roster moves",
    "playoffs": "Playoff race",
    "draft": "Draft",
    "retirement": "Retirements",
    "season": "Season and team news",
    "awards": "Awards and honors",
    "storyline": "Storylines",
    "rankings": "Rankings and previews",
    "business": "League business",
}
LEAGUE_VIEW_MIN = 25       # the league-wide view shows stories at least this important (0-100)
POST_LEAGUE_VIEW_MIN = 30  # ...and social posts at least this important
NOTABLE = 62               # shown overall: a player good enough that his injury or release is news
STAR = 72                  # shown overall: a star (bigger headlines)
STANDOUTS = True           # the outlet's own "Week N standouts" (not an official league award)

# One game, worth its own story (stat, at least, importance, what it is).
FEATS = [
    ("pass_yds", 400, 55, "pass_yds"), ("pass_td", 5, 60, "pass_td"),
    ("rush_yds", 175, 55, "rush_yds"), ("rush_td", 3, 50, "rush_td"),
    ("rec_yds", 175, 55, "rec_yds"), ("rec_td", 3, 55, "rec_td"), ("rec", 14, 45, "rec"),
    ("sacks", 3, 50, "sacks"), ("def_int", 2, 45, "def_int"), ("def_td", 1, 40, "def_td"),
    ("kr_td", 1, 40, "kr_td"), ("pr_td", 1, 40, "pr_td"), ("fgm", 5, 40, "fgm"), ("fg_long", 57, 45, "fg_long"),
    ("pass_int", 4, 35, "pass_int"),
]
# Big games by position (Blake, Oct 23: "a dominant performance for all positions";
# his QB rule: 300+ yards or 3+ TD passes with 0-1 INT, or a huge day like 450
# yards, 4 TDs and 2 INTs). Two levels, set from real NFL games 2015-2025
# (tools/big_games_real.py prints how often each happens a week):
#   big (1): celebrated on Bitter (the stat desk, fantasy guy, fans). Real NFL: about
#            8 QBs, 5 RBs, 6 WRs, 2 TEs, 5 pass rushers a week.
#   dominant (2): also its own news story. Real NFL: about 2-3 QBs, 1-2 RBs, 1-2 WRs a week.
POS_GROUP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE", "DE": "DL", "DT": "DL", "OLB": "LB",
             "ILB": "LB", "CB": "DB", "S": "DB", "K": "K"}
BIG_GAME_IMPORTANCE = {"QB": 55, "RB": 50, "WR": 50, "TE": 46, "DL": 48, "LB": 46, "DB": 46, "K": 40}


def big_game(position, s):
    """(level, headline stat, importance) for one game line: level 2 dominant,
    1 big, 0 neither."""
    v = lambda k: s.get(k, 0) or 0
    g = POS_GROUP.get(position)
    py, ptd, pint, ry = v("pass_yds"), v("pass_td"), v("pass_int"), v("rush_yds")
    rtd, rec, recy, rectd = v("rush_td"), v("rec"), v("rec_yds"), v("rec_td")
    sk, di, dtd, ff, tfl, pd = v("sacks"), v("def_int"), v("def_td"), v("ff"), v("tfl"), v("pd")
    tk = v("tkl") + v("ast")
    scrim, tds = ry + recy, rtd + rectd
    level, stat, extra = 0, None, 0
    if g == "QB":
        if (py >= 300 and ptd >= 3 and pint <= 1) or py >= 400 or ptd >= 4 or ry >= 100:
            level = 2
        elif ((py >= 300 or ptd >= 3) and pint <= 1) or py / 25 + 4 * ptd - 3 * pint >= 22:
            level = 1
        stat = "pass_td" if ptd >= 4 else ("rush_yds" if ry >= 100 and py < 300 else "pass_yds")
        extra = 10 if py >= 450 or ptd >= 5 else 0
        if not level and pint >= 4:
            return 2, "pass_int", 35
    elif g == "RB":
        if scrim >= 200 or tds >= 3 or (ry >= 150 and tds >= 1) or (scrim >= 175 and tds >= 1):
            level = 2
        elif (ry >= 100 and tds >= 1) or scrim >= 150:
            level = 1
        stat = "rush_td" if rtd >= 3 else ("rush_yds" if ry >= 100 or recy < 100 else "rec_yds")
        extra = 10 if scrim >= 225 or tds >= 4 else 0
    elif g in ("WR", "TE"):
        if g == "WR":
            if recy >= 150 or rectd >= 3 or (recy >= 125 and rectd >= 2):
                level = 2
            elif (recy >= 100 and rectd >= 1) or (rec >= 10 and recy >= 120):
                level = 1
        else:
            if recy >= 125 or rectd >= 3 or (recy >= 100 and rectd >= 2):
                level = 2
            elif recy >= 100 or rectd >= 2:
                level = 1
        stat = "rec_td" if rectd >= 3 else ("rec" if rec >= 13 and recy < 150 else "rec_yds")
        extra = 10 if recy >= 200 or rectd >= 4 else 0
    elif g in ("DL", "LB", "DB"):
        if g == "DL":
            if sk >= 3 or (sk >= 2 and ff >= 1) or dtd >= 1:
                level = 2
            elif sk >= 2 or (sk >= 1 and ff >= 1) or tfl >= 3 or di >= 1:
                level = 1
        elif g == "LB":
            if sk >= 3 or tk >= 18 or dtd >= 1 or di >= 2 or (di >= 1 and sk >= 1):
                level = 2
            elif sk >= 2 or tk >= 15 or di >= 1 or (tk >= 12 and (sk >= 1 or tfl >= 1)):
                level = 1
        else:
            if di >= 2 or dtd >= 1 or (di >= 1 and sk >= 1):
                level = 2
            elif di >= 1 and pd >= 3:
                level = 1
        stat = ("def_td" if dtd else "def_int" if di >= 2 or (g == "DB" and di) else
                "sacks" if sk >= 1 else "tackles" if tk >= 12 else "def_int" if di else "sacks")
        extra = 10 if sk >= 4 or di >= 3 else 0
    elif g == "K":
        fgm, fl = v("fgm"), v("fg_long")
        if fgm >= 5 or fl >= 58:
            level = 2
        elif fgm >= 4 or fl >= 55:
            level = 1
        stat = "fgm" if fgm >= 4 else "fg_long"
    if v("kr_td") or v("pr_td"):
        return 2, "kr_td" if v("kr_td") else "pr_td", 42
    if not level:
        return 0, None, 0
    return level, stat, BIG_GAME_IMPORTANCE.get(g, 40) + extra


# Season marks (regular season) and career marks (players whose whole career is
# in the league's records).
SEASON_MARKS = {"pass_yds": [4000, 5000], "pass_td": [30, 40, 50], "rush_yds": [1000, 1500, 2000],
                "rush_td": [15, 20], "rec_yds": [1000, 1500, 2000], "rec": [100, 125], "rec_td": [12, 15, 20],
                "sacks": [10, 15, 20], "def_int": [7, 10]}
CAREER_MARKS = {"pass_yds": [10000, 20000, 30000, 40000, 50000, 60000, 70000], "pass_td": [100, 200, 300, 400, 500],
                "rush_yds": [5000, 7500, 10000, 12500, 15000], "rush_td": [50, 75, 100],
                "rec_yds": [5000, 7500, 10000, 12500, 15000], "rec": [500, 750, 1000], "rec_td": [50, 75, 100],
                "sacks": [50, 75, 100, 125, 150], "def_int": [25, 40, 50]}
STAT_WORDS = {"pass_yds": "passing yards", "pass_td": "touchdown passes", "rush_yds": "rushing yards",
              "rush_td": "rushing touchdowns", "rec_yds": "receiving yards", "rec": "catches",
              "rec_td": "touchdown catches", "sacks": "sacks", "def_int": "interceptions"}
# -------------------------------------------------------------------------------

POS_WORD = {"QB": "quarterback", "RB": "running back", "FB": "fullback", "WR": "wide receiver", "TE": "tight end",
            "T": "tackle", "G": "guard", "C": "center", "DE": "defensive end", "DT": "defensive tackle",
            "OLB": "linebacker", "ILB": "linebacker", "CB": "cornerback", "S": "safety", "K": "kicker",
            "P": "punter", "LS": "long snapper"}
POS_ABBR = {"T": "OT", "G": "OG"}

INSIDERS = [("Dana Kessler", "KesslerReports"), ("Marcus Okafor", "OkaforScoop"), ("Tori Vance", "ToriVanceNews")]
STAT_DESK = ("League Stat Desk", "StatDesk")

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
        9: "ninth", 10: "10th"}


# ---------------------------------------------------------------------------
# Small word helpers
# ---------------------------------------------------------------------------

def num(n):
    """AP style: one to nine in words, 10 and up in figures."""
    n = int(round(n))
    return _WORDS[n] if 0 <= n <= 9 else f"{n:,}"


def plural(n, word, many=None):
    n = int(round(n))
    return f"{num(n)} {word if n == 1 else (many or word + 's')}"


def ordinal(n):
    if n in _ORD:
        return _ORD[n]
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def yds(n):
    n = int(round(n))
    return f"{n:,} yard{'' if n == 1 else 's'}"


def td_text(n):
    return "a touchdown" if n == 1 else f"{num(n)} touchdowns"


def sacks_text(x):
    if abs(x - round(x)) < 1e-9:
        return "a sack" if round(x) == 1 else plural(round(x), "sack")
    return f"{x:g} sacks"


def join_and(parts):
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return "".join(parts)
    if len(parts) == 2:
        sep = ", and " if " and " in parts[0] or "," in parts[0] else " and "
        return parts[0] + sep + parts[1]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


def possessive(name):
    return name + ("'" if name.endswith("s") else "'s")


def article(phrase):
    return "an" if phrase[:1].lower() in "aeiou" or phrase.startswith(("MCL", "LCL")) else "a"


def pos_abbr(p):
    return POS_ABBR.get(p.position, p.position)


def pos_plural(position, n):
    word = POS_WORD[position]
    return f"{num(n)} {word if n == 1 else ('safeties' if word == 'safety' else word + 's')}"


def season_amount(stat, total):
    """'1,204 rushing yards', '11 touchdown passes', '9.5 sacks'."""
    if stat == "sacks":
        return sacks_text(total)
    if stat.endswith("_yds"):
        return f"{int(total):,} {STAT_WORDS[stat]}"
    if stat == "rec":
        return plural(total, "catch", "catches")
    if stat == "pass_td":
        return plural(total, "touchdown pass", "touchdown passes")
    if stat in ("rush_td", "rec_td"):
        return plural(total, STAT_WORDS[stat][:-1])
    if stat == "def_int":
        return plural(total, "interception")
    return f"{total:g} {STAT_WORDS.get(stat, stat)}"


def second_mentions(text, players):
    """Full name the first time, last name after that (newspaper style)."""
    for p in players:
        if p is None or text.count(p.name) < 2:
            continue
        i = text.index(p.name) + len(p.name)
        text = text[:i] + text[i:].replace(p.name, p.last_name)
    return text


def fmt_clock(c):
    if isinstance(c, (int, float)):
        c = int(c)
        return f"{c // 60}:{c % 60:02d}"
    return str(c)


_BARE_PARTS = {"ankle", "back", "calf", "groin", "hamstring", "hand", "hip", "knee", "shoulder", "head"}
_NO_ARTICLE = ("broken ribs", "turf toe")
_PART_FALLBACK = {"stinger": "neck", "neck_strain": "neck", "neck_stinger": "neck", "elbow": "elbow",
                  "elbow_bad": "elbow", "chest": "chest", "broken_arm": "arm", "achilles": "Achilles",
                  "broken_leg": "leg", "pectoral": "pectoral", "serious": "undisclosed"}


def injury_phrase(kind):
    """'a torn ACL', 'broken ribs', 'a hamstring injury', 'a severe high ankle sprain'."""
    name = I.name(kind) if kind else "injury"
    base, _, extra = name.partition(" (")
    extra = extra.rstrip(")")
    if base == "core muscle surgery":
        return "a core muscle injury that needed surgery"
    if base == "neck/back surgery":
        return "a back injury that needed surgery"
    if base == "ribs":
        base = "rib injury"
    elif base in _BARE_PARTS:
        base += " injury"
    elif base == "serious injury":
        return "a serious injury"
    if extra in ("severe", "serious"):
        base = f"{extra} {base}"
    if base in _NO_ARTICLE:
        out = base
    else:
        out = f"{article(base)} {base}"
    if extra == "surgery":
        out += " that needed surgery"
    return out


def injury_short(kind):
    """The body part, the way an injury report lists it: 'knee', 'hamstring'."""
    if not kind:
        return "injury"
    part = getattr(I, "PART", {}).get(kind) or _PART_FALLBACK.get(kind)
    if part:
        return part
    return I.name(kind).partition(" (")[0]


# ---------------------------------------------------------------------------
# What stood out in one player's game (box score line)
# ---------------------------------------------------------------------------

def _f(s, k):
    return s.get(k, 0) or 0


def impact(s):
    """{category: weight} for one game line: how much each part of his game stood out."""
    att = _f(s, "pass_att") - _f(s, "spikes")
    out = {}
    if att >= 8:
        out["pass"] = _f(s, "pass_yds") / 25 + 4 * _f(s, "pass_td") - 3 * _f(s, "pass_int")
    if _f(s, "rush_yds") >= 40 or _f(s, "rush_td"):
        out["rush"] = _f(s, "rush_yds") / 10 + 6 * _f(s, "rush_td")
    if _f(s, "rec") and (_f(s, "rec_yds") >= 50 or _f(s, "rec_td")):
        out["rec"] = _f(s, "rec_yds") / 10 + 6 * _f(s, "rec_td") + 0.5 * _f(s, "rec")
    d = (4 * _f(s, "sacks") + 5 * _f(s, "def_int") + 6 * _f(s, "def_td") + 3 * _f(s, "ff") + 2 * _f(s, "fr")
         + 1.5 * _f(s, "tfl") + 0.4 * (_f(s, "tkl") + _f(s, "ast")) + _f(s, "pd"))
    if d >= 5:
        out["def"] = d
    if _f(s, "fgm") >= 3 or _f(s, "fg_long") >= 50:
        out["kick"] = 1.5 * _f(s, "fgm") + (2 if _f(s, "fg_long") >= 50 else 0)
    if _f(s, "kr_td") or _f(s, "pr_td"):
        out["ret"] = 7 * (_f(s, "kr_td") + _f(s, "pr_td")) + (_f(s, "kr_yds") + _f(s, "pr_yds")) / 25
    return out


def total_impact(s):
    return sum(max(0, v) for v in impact(s).values())


def phrase(s, cat, rng):
    """One part of his game in words, starting with a past-tense verb."""
    if cat == "pass":
        att = int(_f(s, "pass_att") - _f(s, "spikes"))
        c, y, td, it = int(_f(s, "pass_cmp")), _f(s, "pass_yds"), int(_f(s, "pass_td")), int(_f(s, "pass_int"))
        if td and it:
            tail = f" with {td_text(td)} and {plural(it, 'interception')}"
        elif td:
            tail = f" and {td_text(td)}"
        elif it:
            tail = f" with {plural(it, 'interception')}"
        else:
            tail = ""
        return rng.choice([f"completed {c} of {att} passes for {yds(y)}{tail}", f"threw for {yds(y)}{tail}",
                           f"went {c}-for-{att} for {yds(y)}{tail}", f"passed for {yds(y)}{tail}"])
    if cat == "rush":
        a, y, td = int(_f(s, "rush_att")), _f(s, "rush_yds"), int(_f(s, "rush_td"))
        if y < 40:
            return "ran for a score" if td == 1 else f"ran for {num(td)} scores"
        tail = f" and {td_text(td)}" if td else ""
        return rng.choice([f"ran for {yds(y)}{tail} on {plural(a, 'carry', 'carries')}", f"rushed for {yds(y)}{tail}",
                           f"carried {plural(a, 'time')} for {yds(y)}{tail}"])
    if cat == "rec":
        r, y, td = int(_f(s, "rec")), _f(s, "rec_yds"), int(_f(s, "rec_td"))
        tail = f" and {td_text(td)}" if td else ""
        return rng.choice([f"caught {plural(r, 'pass', 'passes')} for {yds(y)}{tail}",
                           f"had {plural(r, 'catch', 'catches')} for {yds(y)}{tail}",
                           f"hauled in {plural(r, 'pass', 'passes')} for {yds(y)}{tail}"])
    if cat == "def":
        bits = []
        if _f(s, "sacks"):
            bits.append(rng.choice(["had ", "recorded "]) + sacks_text(_f(s, "sacks")))
        di = int(_f(s, "def_int"))
        dtd = int(_f(s, "def_td"))
        pick_six = dtd and di and not _f(s, "fr")
        if di and pick_six:
            if di == 1:
                bits.append("returned an interception for a touchdown")
            else:
                bits.append(f"intercepted {num(di)} passes, returning {'one' if dtd == 1 else num(dtd)} for "
                            f"{'a touchdown' if dtd == 1 else 'touchdowns'}")
        elif di:
            bits.append(rng.choice(["intercepted ", "picked off "]) + ("a pass" if di == 1 else f"{num(di)} passes"))
        if dtd and not pick_six:
            if _f(s, "fr") and not di:
                bits.append("returned a fumble for a touchdown")
            else:
                bits.append("scored on defense")
        ff = int(_f(s, "ff"))
        if ff:
            bits.append("forced a fumble" if ff == 1 else f"forced {num(ff)} fumbles")
        tk = int(_f(s, "tkl") + _f(s, "ast"))
        if tk >= 10 or not bits:
            bits.append(f"made {plural(tk, 'tackle')}")
        return join_and(bits)
    if cat == "kick":
        fgm, fl = int(_f(s, "fgm")), int(_f(s, "fg_long"))
        out = f"kicked {plural(fgm, 'field goal')}"
        if fl >= 50:
            out += f" (the longest from {fl} yards)" if fgm > 1 else f" from {fl} yards"
        return out
    if cat == "ret":
        bits = []
        if _f(s, "kr_td"):
            bits.append("returned a kickoff for a touchdown")
        if _f(s, "pr_td"):
            bits.append("returned a punt for a touchdown")
        return join_and(bits)
    return ""


def game_phrase(s, rng, parts=2):
    """His game in words (the parts that stood out most): 'threw for 312
    yards and two touchdowns, and ran for a score'."""
    imp = sorted(impact(s).items(), key=lambda kv: -kv[1])[:parts]
    imp.sort(key=lambda kv: kv[0] != "pass")          # a quarterback's passing comes first
    return join_and([phrase(s, cat, rng) for cat, w in imp if w > 0])


def noun(s, cat, rng):
    """One part of his game as a noun phrase: '139 rushing yards and two touchdowns'."""
    if cat == "pass":
        att = int(_f(s, "pass_att") - _f(s, "spikes"))
        c, y, td, it = int(_f(s, "pass_cmp")), _f(s, "pass_yds"), int(_f(s, "pass_td")), int(_f(s, "pass_int"))
        tdp = plural(td, "touchdown pass", "touchdown passes")
        opts = [f"{int(y):,} passing yards" + (f" and {tdp}" if td else ""),
                f"{c}-of-{att} passing for {yds(y)}" + (f" and {tdp}" if td else "")]
        if td >= 2 and not it:
            opts.append(f"{int(y):,} passing yards, {tdp} and no interceptions")
        return rng.choice(opts)
    if cat == "rush":
        a, y, td = int(_f(s, "rush_att")), _f(s, "rush_yds"), int(_f(s, "rush_td"))
        if y < 40:
            return "a rushing touchdown" if td == 1 else f"{num(td)} rushing touchdowns"
        tail = f" and {td_text(td)}" if td else ""
        return rng.choice([f"{int(y):,} rushing yards{tail}", f"{yds(y)}{tail} on {plural(a, 'carry', 'carries')}"])
    if cat == "rec":
        r, y, td = int(_f(s, "rec")), _f(s, "rec_yds"), int(_f(s, "rec_td"))
        tail = f" and {td_text(td)}" if td else ""
        return rng.choice([f"{plural(r, 'catch', 'catches')} for {yds(y)}{tail}",
                           f"{int(y):,} receiving yards{tail}" + (f" on {plural(r, 'catch', 'catches')}" if not td else "")])
    if cat == "def":
        bits = []
        if _f(s, "sacks"):
            bits.append(sacks_text(_f(s, "sacks")))
        di, dtd = int(_f(s, "def_int")), int(_f(s, "def_td"))
        if di:
            bits.append("an interception" if di == 1 else f"{num(di)} interceptions")
        if dtd:
            bits.append("a defensive touchdown" if dtd == 1 else f"{num(dtd)} defensive touchdowns")
        ff = int(_f(s, "ff"))
        if ff:
            bits.append("a forced fumble" if ff == 1 else f"{num(ff)} forced fumbles")
        tk = int(_f(s, "tkl") + _f(s, "ast"))
        if tk >= 10 or not bits:
            bits.append(plural(tk, "tackle"))
        return join_and(bits)
    if cat == "kick":
        return plural(_f(s, "fgm"), "field goal")
    if cat == "ret":
        return "a return touchdown" if _f(s, "kr_td") + _f(s, "pr_td") == 1 else "two return touchdowns"
    return ""


def game_noun(s, rng, parts=2):
    """His game as a noun phrase (the parts that stood out most)."""
    imp = sorted(impact(s).items(), key=lambda kv: -kv[1])[:parts]
    imp.sort(key=lambda kv: kv[0] != "pass")
    return join_and([noun(s, cat, rng) for cat, w in imp if w > 0])


def stat_line(s):
    """Compact stat line for social posts: '24/33, 312 yds, 3 TD, 1 INT'."""
    bits = []
    att = int(_f(s, "pass_att") - _f(s, "spikes"))
    if att >= 8:
        bits.append(f"{int(_f(s, 'pass_cmp'))}/{att}, {int(_f(s, 'pass_yds'))} yds, {int(_f(s, 'pass_td'))} TD, "
                    f"{int(_f(s, 'pass_int'))} INT")
    if _f(s, "rush_att") >= 5 or _f(s, "rush_td"):
        bits.append(f"{int(_f(s, 'rush_att'))} car, {int(_f(s, 'rush_yds'))} yds" +
                    (f", {int(_f(s, 'rush_td'))} TD" if _f(s, "rush_td") else ""))
    if _f(s, "rec") >= 3 or _f(s, "rec_td"):
        bits.append(f"{int(_f(s, 'rec'))} rec, {int(_f(s, 'rec_yds'))} yds" +
                    (f", {int(_f(s, 'rec_td'))} TD" if _f(s, "rec_td") else ""))
    d = []
    if _f(s, "tkl") + _f(s, "ast") >= 5:
        d.append(f"{int(_f(s, 'tkl') + _f(s, 'ast'))} tkl")
    if _f(s, "sacks"):
        d.append(f"{_f(s, 'sacks'):g} sack{'' if _f(s, 'sacks') == 1 else 's'}")
    if _f(s, "def_int"):
        d.append(f"{int(_f(s, 'def_int'))} INT")
    if _f(s, "ff"):
        d.append(f"{int(_f(s, 'ff'))} FF")
    if _f(s, "def_td"):
        d.append(f"{int(_f(s, 'def_td'))} TD")
    if d:
        bits.append(", ".join(d))
    if _f(s, "fga"):
        bits.append(f"{int(_f(s, 'fgm'))}/{int(_f(s, 'fga'))} FG" +
                    (f", long {int(_f(s, 'fg_long'))}" if _f(s, "fgm") else ""))
    if _f(s, "kr_td") or _f(s, "pr_td"):
        bits.append(f"{int(_f(s, 'kr_td') + _f(s, 'pr_td'))} return TD")
    return "; ".join(bits)


# ---------------------------------------------------------------------------
# The builder
# ---------------------------------------------------------------------------

class _Ctx:
    def __init__(self, league):
        self.league = league
        self.salt = league.settings.get("salt", "")
        self.first = league.settings.get("first_season", league.season)
        self.n_weeks = S.n_weeks(league)
        self.teams = {t.id: t for t in league.teams}
        self.items = []
        self.posts = []
        self._used = defaultdict(set)
        from .bitter_words import BITTER_BANK
        from .news_words import BANK
        self.writer = Writer({**BANK, **BITTER_BANK})
        self.starters = {t.id: depth.starter_ids(league.depth_charts.get(t.id, {})) for t in league.teams}

    # ---- dice and wording ----
    def rng(self, *key):
        return random.Random("news-" + "-".join(str(k) for k in (self.salt,) + key))

    def pick(self, slot, rng, options):
        """One of the options, not one already used in this slot (e.g. this
        week's game headlines) while others are still unused."""
        used = self._used[slot]
        free = [i for i in range(len(options)) if i not in used]
        if not free:
            used.clear()
            free = list(range(len(options)))
        i = rng.choice(free)
        used.add(i)
        return options[i]

    # ---- names ----
    def city(self, tid):
        return self.teams[tid].city

    def nick(self, tid):
        return self.teams[tid].nickname

    def full(self, tid):
        return self.teams[tid].name

    def player(self, pid):
        try:
            return self.league.player(int(pid))
        except (KeyError, ValueError, TypeError):
            return None

    def short(self, p, tid=None):
        """His last name for a headline, or his full name if a teammate has the
        same last name or it's also a city or team name ('Washington')."""
        if "_lastnames" not in self.__dict__:
            seen = defaultdict(int)
            for q in self.league.players:
                if q.retired is None:
                    seen[(S.transactions.team_of(self.league, q.id)[0], q.last_name)] += 1
            self._lastnames = seen
            self._places = {w for t in self.teams.values() for w in (t.city, t.nickname, t.abbrev)}
        if p.last_name in self._places or (tid is not None and self._lastnames.get((tid, p.last_name), 0) > 1):
            return p.name
        return p.last_name

    def caliber(self, p):
        # The Oct 22 scale NOTABLE and STAR were tuned on (never printed), not the
        # rarer top ratings screens show since Oct 24.
        return legacy_shown(p.overall(), p.position)

    def notable(self, p, tid=None):
        return p is not None and (self.caliber(p) >= NOTABLE or p.id in self.starters.get(tid, ()))

    def champ_name(self, season):
        return f"{po.CHAMPIONSHIP} {po.roman(season - self.first + 1)}"

    # ---- calendar ----
    def when(self, season, cal):
        if cal < 0:
            return "Draft" if cal == -2 else "Offseason"
        if cal < 1:
            return "Training camp"
        if cal < 2:
            return "Hall of Fame Game week"
        if cal < 5.5:
            return f"Preseason week {int(cal) - 1}"
        if cal < 6:
            return "Final cuts"
        if cal < 6 + self.n_weeks:
            return f"Week {int(cal) - 5}"
        r = int(cal) - 5 - self.n_weeks
        if r == 5:
            return self.champ_name(season)
        if r > 5:
            return "Season complete"
        return po.ROUND_NAMES.get(r, "Playoffs")

    def label_cal(self, label):
        """Calendar order of a week label from the season ('Week 7', 'Final cuts', ...)."""
        label = label or ""
        if label == "Training camp":
            return 0
        if label.startswith("Hall of Fame Game"):
            return 1
        m = re.match(r"Preseason week (\d+)", label)
        if m:
            return int(m.group(1)) + 1
        if label == "Final cuts":
            return 5.5
        m = re.match(r"Week (\d+)$", label)
        if m:
            return 5 + int(m.group(1))
        for r, name in po.ROUND_NAMES.items():
            if label == name:
                return 5 + self.n_weeks + r
        if label.startswith(po.CHAMPIONSHIP):
            return 5 + self.n_weeks + 5
        return -1

    def game_cal(self, phase, g):
        if phase == "preseason":
            return g["week"]
        if phase == "playoffs":
            return 5 + self.n_weeks + g["week"]
        return 5 + g["week"]

    def game_label(self, season, phase, g):
        if phase == "preseason":
            return "Hall of Fame Game" if g.get("kind") == "hof" else f"Preseason week {g['week'] - 1}"
        if phase == "playoffs":
            return self.champ_name(season) if g["week"] == 5 else po.ROUND_NAMES[g["week"]]
        return f"Week {g['week']}"

    # ---- output ----
    def add(self, season, cal, kind, headline, body, teams=(), players=(), importance=30, key=None):
        # Two players with the same last name in the same week: the second headline gets his full name.
        heads = self.__dict__.setdefault("_heads", set())
        if (season, int(cal), headline) in heads and players:
            p = self.player(players[0])
            if p and p.last_name in headline and p.name not in headline:
                headline = headline.replace(p.last_name, p.name, 1)
        heads.add((season, int(cal), headline))
        if key is None:      # an id that stays the same as later weeks are played
            keys = self.__dict__.setdefault("_item_keys", defaultdict(int))
            keys[(kind, season, cal)] += 1
            key = f"{kind}-{season}-{cal}-{keys[(kind, season, cal)]}"
        self.items.append({"id": key, "season": season, "cal": cal,
                           "when": self.when(season, cal), "kind": kind, "headline": headline, "body": body,
                           "teams": [t for t in teams if t], "players": [p for p in players if p],
                           "importance": max(0, min(100, round(importance)))})

    def post(self, season, cal, who, text, teams=(), players=(), importance=20, reply_to=None, quote=None,
             kind=None):
        """A bit on Bitter (engine/bitter.py). text: the words, or a news_words.Say
        (worded later, in calendar order, by finish_posts, so nothing repeats).
        reply_to: the id of the bit it answers; quote: {"of": the id of the bit it
        quotes, "when": its week label}. Returns its id (a bit that can't be said
        freshly is dropped later, with its replies)."""
        name, handle, role, team = who
        if not text or reply_to is False:
            return None
        # The id stays the same as later weeks are played (likes and rebits are seeded by it).
        keys = self.__dict__.setdefault("_post_keys", defaultdict(int))
        keys[(season, cal, handle)] += 1
        pid = f"post-{season}-{cal}-{handle}-{keys[(season, cal, handle)]}"
        self.posts.append({"id": pid, "season": season, "cal": cal,
                           "when": self.when(season, cal), "name": name, "handle": "@" + handle, "role": role,
                           "team": team, "text": text, "teams": [t for t in teams if t],
                           "players": [p for p in players if p], "importance": max(0, min(100, round(importance))),
                           "reply_to": reply_to, "quote": quote, "kind": kind})
        return pid

    def finish_posts(self, start):
        """Word the bits made since posts[start] (one season's), in calendar order:
        each Say gets wording that hasn't been used too much this season
        (news_words.Writer.fresh), and a bit written in full must not repeat one
        word for word. A bit that can't be said freshly is dropped, with its
        replies and any bit quoting it. Calendar order (not the order the
        sections run in) keeps a week's bits the same after later weeks are played."""
        new = self.posts[start:]
        order = sorted(range(len(new)), key=lambda i: (new[i]["season"], new[i]["cal"], i))
        done, keep = {}, []
        for i in order:
            b = new[i]
            q = b["quote"]
            if (b["reply_to"] and b["reply_to"] not in done) or (q and "of" in q and q["of"] not in done):
                continue
            t = b["text"]
            if isinstance(t, Say):
                rng = random.Random(f"bit-{self.salt}-{b['season']}-{b['cal']}-{b['handle']}-{t.name}-"
                                    f"{b['teams']}-{b['players']}")
                t = self.writer.fresh(t.name, rng, t.facts, int(b["cal"]))
            elif not self.writer.claim(t):
                t = ""
            if not t:
                continue
            b["text"] = t
            if q and "of" in q:
                src = done[q["of"]]
                b["quote"] = {"name": src["name"], "handle": src["handle"], "text": src["text"],
                              "when": q.get("when") or src["when"]}
            done[b["id"]] = b
            keep.append(b)
        self.posts[start:] = keep

    # ---- social personas (invented; no real reporters) ----
    def insider(self, rng):
        name, handle = rng.choice(INSIDERS)
        return (name, handle, "Insider", None)

    def stat_desk(self):
        return (STAT_DESK[0], STAT_DESK[1], "Stats", None)

    def beat(self, tid):
        r = random.Random(f"beat-{tid}")
        first, last = r.choice(names.FIRST_NAMES), r.choice(names.LAST_NAMES)
        handle = re.sub(r"[^A-Za-z]", "", f"{last}On{self.nick(tid)}")[:20]
        return (f"{first} {last}", handle, f"{self.nick(tid)} beat writer", tid)

    def fan(self, tid, rng, mood=None):
        """One of the team's three fan accounts (mood: 0 the homer, 1 the worrier,
        2 the trash talker; None: any of them)."""
        t = self.teams[tid]
        nick, city = re.sub(r"[^A-Za-z]", "", t.nickname), re.sub(r"[^A-Za-z]", "", t.city)
        r = random.Random(f"fans-{tid}")
        pool = [f"{nick}Nation", f"{city}Diehard", f"{t.abbrev}Faithful", f"Section{r.randint(101, 349)}{nick}",
                f"{nick}4Life", f"Old{city}Fan", f"{nick}Talk{r.randint(2, 99)}", f"{t.abbrev}til I die".replace(" ", "")]
        handles = r.sample(pool, 3)
        h = handles[mood] if mood is not None else rng.choice(handles)
        return (h, h, f"{t.nickname} fan", tid)

    def player_voice(self, p):
        r = random.Random(f"handle-{p.id}")
        first, last = re.sub(r"[^A-Za-z]", "", p.first_name), re.sub(r"[^A-Za-z]", "", p.last_name)
        handle = r.choice([f"{first}{last}", f"{first[0]}{last}{r.randint(1, 99)}", f"Real{first}{last}",
                           f"{first}_{last}"])[:20]
        tid = S.transactions.team_of(self.league, p.id)[0] if hasattr(S, "transactions") else None
        return (p.name, handle, "Player", tid)


def _box(league, gid):
    return league.boxes.get(gid) or league.boxes.get(str(gid))


# ---------------------------------------------------------------------------
# A season's games
# ---------------------------------------------------------------------------

def _season_games(ctx, season, past_games):
    """[(phase, game, box)] for one season, in calendar order."""
    league = ctx.league
    if season == league.season:
        out = []
        for phase, games in (("preseason", league.preseason), ("regular", league.schedule),
                             ("playoffs", league.playoffs)):
            for g in games:
                out.append((phase, g, _box(league, g["id"]) if g.get("played") else None))
    else:
        out = [(r["phase"], r["game"], r.get("box")) for r in past_games or () if r["season"] == season]
    out.sort(key=lambda x: (ctx.game_cal(x[0], x[1]), x[1]["id"]))
    return out


def _rec_text(r):
    w, l, t = r[0], r[1], r[2]
    return f"{w}-{l}" + (f"-{t}" if t else "")


def _streak(res):
    if not res:
        return "", 0
    n = 1
    while n < len(res) and res[-n - 1] == res[-1]:
        n += 1
    return res[-1], n


def _records_by_week(ctx, games):
    """{week: {team: (w, l, t, results)}} after each regular-season week (0 = before week 1)."""
    rec = {tid: [0, 0, 0, ""] for tid in ctx.teams}
    out = {0: {tid: tuple(r) for tid, r in rec.items()}}
    reg = [g for ph, g, _b in games if ph == "regular"]
    for w in range(1, ctx.n_weeks + 1):
        for g in reg:
            if g["week"] != w or not g.get("played"):
                continue
            for tid, pf, pa in ((g["home"], g["home_score"], g["away_score"]),
                                (g["away"], g["away_score"], g["home_score"])):
                k = 0 if pf > pa else (1 if pf < pa else 2)
                rec[tid][k] += 1
                rec[tid][3] += "WLT"[k]
        out[w] = {tid: tuple(r) for tid, r in rec.items()}
    return out


def _pct(r):
    g = r[0] + r[1] + r[2]
    return (r[0] + 0.5 * r[2]) / g if g else 0.0


def _lines(box):
    return {int(k): v for k, v in (box or {}).get("players", {}).items()}


def _star(ctx, lines, tid):
    best = None
    for pid, s in lines.items():
        if s.get("team") != tid:
            continue
        w = total_impact(s)
        if best is None or w > best[2]:
            best = (pid, s, w)
    return best


_SCORE_RES = [
    (re.compile(r"^(?P<a>.+?) (?P<y>\d+) yd pass from (?P<b>.+?)(?: \(|$)"), "pass"),
    (re.compile(r"^(?P<a>.+?) (?P<y>\d+) yd run"), "run"),
    (re.compile(r"^(?P<a>.+?) (?P<y>\d+) yd field goal"), "fg"),
    (re.compile(r"^(?P<a>.+?) (?P<y>\d+) yd (?P<k>interception|fumble|kickoff|punt|blocked punt) return"), "ret"),
]


def _describe_score(ctx, text, lines):
    """'J.Smith 12 yd pass from K.Jones (M.Brown kick)' -> "Kip Jones's
    12-yard touchdown pass to Jay Smith" (None if it can't be read)."""
    full = {}
    for pid in lines:
        p = ctx.player(pid)
        if p is not None:
            full.setdefault(short_name(p), set()).add(p.name)
    name = lambda s: next(iter(full[s])) if len(full.get(s, ())) == 1 else s
    for rx, kind in _SCORE_RES:
        m = rx.match(text or "")
        if not m:
            continue
        a, y = name(m.group("a")), int(m.group("y"))
        if kind == "pass":
            return f"{possessive(name(m.group('b')))} {y}-yard touchdown pass to {a}"
        if kind == "run":
            return f"{possessive(a)} {y}-yard touchdown run"
        if kind == "fg":
            return f"{possessive(a)} {y}-yard field goal"
        return f"{possessive(a)} {y}-yard {m.group('k')} return for a touchdown"
    return None


# Verbs: (present after a city, present after a plural, past).
VERBS = {
    "blowout": [("routs", "rout", "routed"), ("rolls past", "roll past", "rolled past"), ("crushes", "crush", "crushed"),
                ("blows out", "blow out", "blew out"), ("cruises past", "cruise past", "cruised past"),
                ("pounds", "pound", "pounded")],
    "close": [("edges", "edge", "edged"), ("holds off", "hold off", "held off"), ("slips past", "slip past", "slipped past"),
              ("survives", "survive", "survived"), ("squeaks past", "squeak past", "squeaked past")],
    "comeback": [("rallies past", "rally past", "rallied past"), ("comes back to beat", "come back to beat", "came back to beat"),
                 ("storms back to beat", "storm back to beat", "stormed back to beat")],
    "ot": [("outlasts", "outlast", "outlasted"), ("edges", "edge", "edged"), ("survives", "survive", "survived"),
           ("beats", "beat", "beat")],
    "upset": [("stuns", "stun", "stunned"), ("upsets", "upset", "upset"), ("knocks off", "knock off", "knocked off")],
    "shutout": [("shuts out", "shut out", "shut out"), ("blanks", "blank", "blanked")],
    "default": [("beats", "beat", "beat"), ("defeats", "defeat", "defeated"), ("tops", "top", "topped"),
                ("downs", "down", "downed"), ("gets past", "get past", "got past"), ("handles", "handle", "handled")],
}


def _team_stats(box, idx):
    t = (box or {}).get("team", [{}, {}])[idx] or {}
    return {"yds": int(t.get("rush_yds", 0) + t.get("pass_yds", 0) - t.get("sacked_yds", 0)),
            "rush": int(t.get("rush_yds", 0)), "give": int(t.get("int_thrown", 0) + t.get("fum_lost", 0)),
            "sacked": int(t.get("sacked", 0)), "pen": int(t.get("penalties", 0)),
            "pen_yds": int(t.get("penalty_yds", 0))}


def _times(n):
    return {0: "none", 1: "once", 2: "twice"}.get(n, f"{num(n)} times")


def _gb_text(gb):
    if gb == 0.5:
        return "a half-game"
    whole = int(gb)
    half = gb - whole >= 0.5
    if whole == 1 and not half:
        return "one game"
    return f"{num(whole)}{' and a half' if half else ''} games"


def _division_facts(ctx, track, tid, week):
    """Where a team stands in its division after `week` (and whether it just took the lead)."""
    t = ctx.teams[tid]
    key = (t.conference, t.division)
    now = track.division_table(week)[key]
    prev = track.division_table(week - 1)[key] if week > 1 else None
    leader = now[0]
    mine = next(x for x in now if x[0] == tid)
    gb = ((leader[1][0] - mine[1][0]) + (mine[1][1] - leader[1][1])) / 2
    tied = [x for x in now if x[0] != tid and SL.pct(x[1]) == SL.pct(mine[1]) and x[1][:2] == mine[1][:2]]
    facts = {"wdiv": t.division}
    if gb > 0:
        facts.update(div_kind="behind", gb=_gb_text(gb), div_leader=ctx.city(leader[0]))
        return facts
    if tied:
        facts.update(div_kind="tied", div_mate=ctx.city(tied[0][0]))
        return facts
    second = now[1]
    lead = ((mine[1][0] - second[1][0]) + (second[1][1] - mine[1][1])) / 2
    was_leader = False
    if prev:
        p_lead = prev[0]
        p_mine = next(x for x in prev if x[0] == tid)
        was_leader = SL.pct(p_mine[1]) >= SL.pct(p_lead[1]) and sum(p_mine[1]) > 0
    gb_text = _gb_text(lead)
    gb_adj = "half-game" if lead == 0.5 else gb_text.replace(" and a half games", "-and-a-half-game") \
        .replace(" games", "-game").replace(" game", "-game")
    facts.update(div_kind="alone", gb=gb_text, gb_adj=gb_adj, took_first=not was_leader and week >= 4)
    return facts


def _game_story(ctx, season, phase, g, box, recs, track=None, posts=True):
    league = ctx.league
    W_ = ctx.writer
    h, a, hs, as_ = g["home"], g["away"], g["home_score"], g["away_score"]
    cal = ctx.game_cal(phase, g)
    label = ctx.game_label(season, phase, g)
    rng = ctx.rng(season, "game", g["id"])
    lines = _lines(box)
    tie = hs == as_
    W, L = (h, a) if hs >= as_ else (a, h)
    ws, ls = max(hs, as_), min(hs, as_)
    margin = ws - ls
    ot = bool(g.get("overtime"))
    week = g["week"]
    regular = phase == "regular"
    starW, starL = _star(ctx, lines, W), _star(ctx, lines, L)
    sp = ctx.player(starW[0]) if starW and starW[2] >= 10 else None
    lp = ctx.player(starL[0]) if starL and starL[2] >= 10 else None

    # ---- How the game went (scores in the scoring list are [away, home]) ----
    max_def, goahead, lead_before = 0, None, 0
    for sc in (box or {}).get("scoring", []):
        w_pts = sc["score"][1] if W == h else sc["score"][0]
        l_pts = sc["score"][0] if W == h else sc["score"][1]
        max_def = max(max_def, l_pts - w_pts)
        lead = w_pts - l_pts
        if lead_before <= 0 < lead:
            goahead = sc
        lead_before = lead
    quarters = (box or {}).get("quarters")
    half = None
    if quarters and len(quarters[0]) >= 2:
        hh, ah = sum(quarters[0][:2]), sum(quarters[1][:2])
        half = (hh, ah) if W == h else (ah, hh)
    before = recs.get(week - 1, {}) if regular else {}
    after = recs.get(week, {}) if regular else {}
    upset = (regular and week >= 4 and not tie and _pct(before.get(W, (0, 0, 0))) + 0.3
             <= _pct(before.get(L, (0, 0, 0))) and sum(before.get(L, (0, 0, 0))[:3]) >= 3)
    comeback = not tie and max_def >= 14
    late = (not tie and goahead is not None and goahead["qtr"] >= 4
            and (goahead["qtr"] == 5 or (isinstance(goahead["clock"], (int, float)) and goahead["clock"] <= 150)))
    if tie:
        cat = None
    elif comeback:
        cat = "comeback"
    elif ot:
        cat = "ot"
    elif upset:
        cat = "upset"
    elif ls == 0:
        cat = "shutout"
    elif margin >= 21:
        cat = "blowout"
    elif margin <= 3:
        cat = "close"
    else:
        cat = "default"
    verbs = [v for v in VERBS.get(cat, [])
             if not (v[0] == "handles" and margin < 10) and not (v[0] == "gets past" and margin > 10)]
    v_s, v_p, v_past = ctx.pick(("verb", season, cat), rng, verbs) if verbs else ("ties", "tie", "tied")

    # ---- Facts ----
    f = {"W": ctx.full(W), "L": ctx.full(L), "Wc": ctx.city(W), "Lc": ctx.city(L), "Wn": ctx.nick(W),
         "Ln": ctx.nick(L), "Wc_poss": possessive(ctx.city(W)), "Lc_poss": possessive(ctx.city(L)),
         "score": f"{ws}-{ls}", "ws": ws, "ls": ls, "ot": " in overtime" if ot else "", "ot_s": " in OT" if ot else "",
         "v_s": v_s, "v_p": v_p, "v_past": v_past, "max_def": max_def, "champ": ctx.champ_name(season),
         "wconf": ctx.teams[W].conference, "tie": tie}
    if regular:
        f["when"] = f" in Week {week}"
    elif phase == "preseason":
        f["when"] = f" in the {label}" if g.get("kind") == "hof" else " in a preseason game"
    else:
        f["when"] = {1: " in the Wild Card round", 2: " in the divisional round",
                     3: f" in the {ctx.teams[W].conference} Conference championship",
                     5: f" in {ctx.champ_name(season)}"}[week]
    site = S.site_text(league, g) if g.get("neutral") else ""
    if site:
        f["where"] = f" in {site}"
    else:
        f["where"] = rng.choice([" at home", ""]) if W == h else rng.choice([" on the road", ""])
    f["where_h"] = " on the road" if W == a and not g.get("neutral") else ""
    if sp:
        f.update(star=sp.name, star_last=sp.last_name, star_poss=possessive(sp.name), star_h=ctx.short(sp, W),
                 star_last_poss=possessive(sp.last_name), star_does=game_phrase(starW[1], rng),
                 star_got=game_noun(starW[1], rng), bigstar=starW[2] >= 18)
    if lp:
        f.update(lstar=lp.name, lstar_last=lp.last_name, lstar_poss=possessive(lp.name), lstar_h=ctx.short(lp, L),
                 lstar_does=game_phrase(starL[1], rng), lstar_got=game_noun(starL[1], rng, parts=1),
                 lstar_big=starL[2] >= 25 and margin <= 10 and not tie)
    if half:
        f.update(hw=half[0], hl=half[1])
    wi, li = (0, 1) if W == h else (1, 0)
    tw_, tl_ = _team_stats(box, wi), _team_stats(box, li)
    lqb = max((ctx.player(pid) for pid, s in lines.items() if s.get("team") == L and s.get("pass_att", 0) >= 5),
              key=lambda p: lines[p.id].get("pass_att", 0) if p else 0, default=None)
    f.update(yw=tw_["yds"], yl=tl_["yds"], rw=tw_["rush"], tw=tl_["give"], tl=tw_["give"],
             takeaways_w=plural(tl_["give"], "turnover"), giveaways_w_t=_times(tw_["give"]),
             giveaways_l_t=_times(tl_["give"]), gw=tw_["give"] > 0, gl_n=num(tl_["give"]) if tl_["give"] else "none",
             gw_n=num(tw_["give"]) if tw_["give"] else "none", sacks_w_t=_times(tl_["sacked"]),
             lqb=lqb.name if lqb else "", pen_l=tl_["pen"], peny_l=tl_["pen_yds"])
    if goahead:
        desc = _describe_score(ctx, goahead["text"], lines)
        f.update(goahead=desc or "", clock=fmt_clock(goahead["clock"]), has_desc=bool(desc))
    m = re.search(r"(Rain|Snow|Clear|Cold), (-?\d+)°F, wind (\d+) mph", (box or {}).get("weather", ""))
    if m:
        f.update(rain=m.group(1) == "Rain", snow=m.group(1) == "Snow", windy=int(m.group(3)) >= 22,
                 frigid=int(m.group(2)) <= 15, wind=m.group(3), temp=m.group(2),
                 wx_city=site or ctx.city(h), weather_h=m.group(1) == "Snow", wx="snowy")
    if regular:
        wa, la = after.get(W, (0, 0, 0, "")), after.get(L, (0, 0, 0, ""))
        wb, lb = before.get(W, (0, 0, 0, "")), before.get(L, (0, 0, 0, ""))
        f.update(wrec=_rec_text(wa), lrec=_rec_text(la), wrec_b=_rec_text(wb), lrec_b=_rec_text(lb),
                 midseason=week >= 6)
        w_st, l_st = _streak(wa[3]), _streak(la[3])
        if not tie:
            if w_st[0] == "W" and w_st[1] >= 3:
                f.update(wstreak=True, n_w=num(w_st[1]), w_ord=ordinal(w_st[1]))
            if l_st[0] == "L" and l_st[1] >= 3:
                f.update(lstreak=True, n_l=num(l_st[1]), l_ord=ordinal(l_st[1]))
            wb_st, lb_st = _streak(wb[3]), _streak(lb[3])
            if wb_st[0] == "L" and wb_st[1] >= 3 and wb[0] > 0:
                last_w = max(i for i, r in enumerate(wb[3]) if r == "W")
                wk = [x[0] for x in track.team_games.get(W, ())][last_w] if track else None
                f.update(snap_w=num(wb_st[1]), last_win=f"Week {wk}" if wk else "early in the season")
            if lb_st[0] == "W" and lb_st[1] >= 3:
                f.update(snap_l=num(lb_st[1]))
            if wa[0] == 1 and sum(wa[:3]) >= 3:
                f["first_win"] = True
            if la[0] == 0 and la[2] == 0 and sum(la[:3]) >= 4:
                f["winless"] = True
            if wa[1] == 0 and wa[2] == 0 and wa[0] >= 4:
                unbeaten = [t for t, r in after.items() if r[1] == 0 and r[2] == 0 and r[0] > 0]
                f.update(unbeaten=True, last_unbeaten=len(unbeaten) == 1, unbeaten_n=num(len(unbeaten)))
            if len(wa[3]) >= 4:
                f["w_last4"] = num(wa[3][-4:].count("W"))
        if ws + ls >= 65:
            f["shootout"] = True
        if ws <= 16 and ls > 0:
            f["lowscore"] = True
        f["plainwin"] = cat in ("default", "close", "blowout", "upset", "shutout")
    # ---- Storylines from earlier weeks ----
    story_bits = []
    if track and regular:
        if sp:
            best = max(track.streaks_for(sp.id, week), key=lambda x: x[1] - x[4], default=None)
            if best and best[1] >= best[4]:
                f.update(star_streak=True, streak_n=num(best[1]), streak_ord=ordinal(best[1]),
                         streak_what=best[2], streak_whats=best[3])
                story_bits.append("star_streak")
        for pid, tid, kind, missed, line, gg in track.comebacks(week):
            if gg["id"] != g["id"]:
                continue
            p = ctx.player(pid)
            # If he's already one of the game's top players, his stats are told there.
            cp_does = "" if p in (sp, lp) else game_phrase(line, rng)
            f.update(cp=p.name, cp_h=ctx.short(p, tid), cp_what=injury_phrase(kind), cp_does=cp_does,
                     cp_won=tid == W and not tie and bool(cp_does), cp_lost=tid == L and not tie and bool(cp_does))
            story_bits.append("comeback_player" if cp_does else "comeback_player_plain")
            break
        for tid in (L, W):
            fo = track.fallout(tid, week)
            # Only at telling moments, so it doesn't come up every week.
            telling = fo and (sum(fo[4]) in (2, 4, 7) or (sum(fo[4]) >= 3 and not 0.25 < SL.pct(fo[4]) < 0.8))
            if telling and _big_loss(ctx, fo) and rng.random() < 0.5:
                pid, iw, kind, rb, rs, _pb, _ps = fo
                f.update(inj_team=ctx.city(tid), inj_player=ctx.player(pid).name, inj_what=injury_phrase(kind),
                         inj_week=iw, since_rec=SL.rec_text(rs))
                story_bits.append("since_injury")
                break
        prev = track.meetings(W, L, week)
        if prev and not tie:
            pw, pg_, _opp, pf, pa, _i = prev[-1]
            f.update(prev_week=pw, prev_score=f"{max(pf, pa)}-{min(pf, pa)}")
            if pf < pa:
                f["avenge"] = True
                story_bits.append("series_avenge")
            elif pf > pa:
                f["sweep"] = True
                story_bits.append("series_sweep")
        if week >= 4 and not tie:
            f.update(_division_facts(ctx, track, W, week))
    if phase == "playoffs" and week == 5 and not tie:
        titles = sum(1 for s, t in league.champions.items() if t == W and s < season)
        f.update(first_title=titles == 0, titles_n=ordinal(titles + 1))

    # ---- Headline ----
    if tie:
        headline = W_.say("head_tie", rng, f)
    elif phase == "preseason":
        headline = W_.say("head_hof" if g.get("kind") == "hof" else "head_preseason", rng, f)
    elif phase == "playoffs":
        headline = W_.say({1: "head_wildcard", 2: "head_divisional", 3: "head_conference", 5: "head_final"}[week],
                          rng, f)
    else:
        headline = W_.say("head", rng, f)

    # ---- Body ----
    sents = []
    if tie:
        sents.append(W_.say("lead_tie", rng, f))
        if sp:
            sents.append(f"{sp.name} {f['star_does']} for the {ctx.nick(W)}.")
        if lp:
            sents.append(W_.say("loser_line", rng, f).replace(" in the loss", "").replace(" in defeat", ""))
    else:
        star_is_def = bool(starW) and max(impact(starW[1]).items(), key=lambda kv: kv[1], default=("", 0))[0] == "def"
        if comeback:
            lead_kind = "lead_comeback"
        elif upset and rng.random() < 0.6:
            lead_kind = "lead_upset"
        elif ls == 0 and rng.random() < 0.5:
            lead_kind = "lead_shutout"
        elif margin >= 21 and rng.random() < 0.4:
            lead_kind = "lead_blowout"
        elif sp and star_is_def:
            lead_kind = "lead_defense"
        elif sp and rng.random() < 0.65:
            lead_kind = "lead_star"
        else:
            lead_kind = "lead_plain"
        sents.append(W_.say(lead_kind, rng, f))
        if sp and lead_kind not in ("lead_star", "lead_defense"):
            sents.append(W_.say("star_extra", rng, f))
        # How it was won.
        if ot and goahead and goahead["qtr"] == 5:
            sents.append(W_.say("how_ot" if f.get("has_desc") else "how_ot_plain", rng, f))
        elif late and goahead:
            sents.append(W_.say("how_late" if f.get("has_desc") else "how_late_plain", rng, f))
        elif comeback and lead_kind != "lead_comeback":
            sents.append(W_.say("how_comeback", rng, f))
        elif ls == 0 and lead_kind != "lead_shutout":
            sents.append(W_.say("how_shutout", rng, f))
        elif half and margin >= 17 and half[0] > half[1]:
            sents.append(W_.say("how_half_lead", rng, f))
        elif half and half[0] < half[1] and not comeback:
            sents.append(W_.say("how_half_trail", rng, f))
        # One box-score angle, the most striking.
        angles = []
        if tl_["give"] - tw_["give"] >= 2:
            angles.append((tl_["give"] - tw_["give"] + 1, "angle_turnovers"))
        if tw_["yds"] - tl_["yds"] >= 120:
            angles.append(((tw_["yds"] - tl_["yds"]) / 60, "angle_yards"))
        if tl_["yds"] - tw_["yds"] >= 80:
            angles.append(((tl_["yds"] - tw_["yds"]) / 40, "angle_yards_lost"))
        if tw_["rush"] >= 180:
            angles.append((tw_["rush"] / 70, "angle_rush"))
        if tl_["sacked"] >= 5 and lqb:
            angles.append((tl_["sacked"] - 2, "angle_sacks"))
        if tl_["pen"] >= 10:
            angles.append((tl_["pen"] - 8, "angle_penalties"))
        if angles and rng.random() < 0.8:
            sents.append(W_.say(max(angles)[1], rng, f))
        for bit in story_bits[:2]:
            sents.append(W_.say(bit, rng, f))
        if lp:
            sents.append(W_.say("loser_line", rng, f))
    if any(f.get(k) for k in ("rain", "snow", "windy", "frigid")) and (f.get("snow") or rng.random() < 0.5):
        sents.append(W_.say("weather", rng, f))
    if regular and not tie:
        if f.get("first_win"):
            sents.append(W_.say("rec_first_win", rng, f))
        elif f.get("snap_w"):
            sents.append(W_.say("rec_snap_w", rng, f))
        elif f.get("unbeaten"):
            sents.append(W_.say("rec_unbeaten", rng, f))
        elif f.get("wstreak"):
            sents.append(W_.say("rec_wstreak", rng, f))
        elif f.get("snap_l"):
            sents.append(W_.say("rec_snap_l", rng, f))
        elif f.get("winless"):
            sents.append(W_.say("rec_winless", rng, f))
        elif f.get("lstreak"):
            sents.append(W_.say("rec_lstreak", rng, f))
        else:
            sents.append(W_.say("rec_plain", rng, f))
        if f.get("took_first"):
            sents.append(W_.say("div_took_first", rng, f))
        elif (f.get("div_kind") and week >= 8 and rng.random() < 0.4
              and not (f["div_kind"] == "behind" and f.get("gb") not in ("a half-game", "one game", "one and a half games",
                                                                       "two games"))):
            sents.append(W_.say({"alone": "div_alone", "tied": "div_tied", "behind": "div_behind"}[f["div_kind"]],
                                rng, f))
    elif regular:
        sents.append(f"{ctx.city(a)} is {_rec_text(after.get(a, (0, 0, 0)))}, "
                     f"{ctx.city(h)} {_rec_text(after.get(h, (0, 0, 0)))}.")
    if phase == "playoffs" and week == 5 and not tie:
        sents.append(f"It is {f['Wc_poss']} first championship." if f["first_title"] else
                     f"It is {f['Wc_poss']} {f['titles_n']} championship.")

    # ---- Importance ----
    if phase == "preseason":
        imp = 25 if g.get("kind") == "hof" else 10
    elif phase == "playoffs":
        imp = {1: 60, 2: 65, 3: 78, 5: 100}[week]
    else:
        imp = 30 + 12 * upset + 10 * comeback + 6 * ot + 4 * late + 6 * bool(f.get("took_first")) \
            + 6 * bool(f.get("unbeaten")) + 4 * bool(f.get("snap_w") or f.get("snap_l")) + 3 * len(story_bits)
        if week >= 6 and _pct(after.get(W, (0, 0, 0))) >= 0.6 and _pct(after.get(L, (0, 0, 0))) >= 0.6:
            imp += 10
    kind = "playoffs" if phase == "playoffs" and week == 5 else "game"
    players = [x[0] for x in (starW, starL) if x and x[2] >= 10]
    body = second_mentions(" ".join(s for s in sents if s), [ctx.player(pid) for pid in lines])
    ctx.add(season, cal, kind, headline, body, teams=[W, L], players=players, importance=min(imp, 100),
            key=f"game-{season}-{g['id']}")

    if not posts:
        return
    # ---- Bitter ----
    if phase == "preseason" or tie:
        for tid, won in ((W, True), (L, False)):
            _fan_post(ctx, season, cal, tid, ctx.rng(season, "fan", g["id"], tid), None if tie else won, margin,
                      phase, week, after.get(tid) if regular else None, sp if won and not tie else None, W, L, ws, ls)
    else:
        from . import bitter
        f.update(upset=upset, _wrec=after.get(W), _lrec=after.get(L), _late=late)
        if late and goahead and "field goal" in (goahead.get("text") or ""):
            f["_kicker"] = (f.get("goahead") or "").split("'")[0]
        star_def = None
        if sp and max(impact(starW[1]).items(), key=lambda kv: kv[1], default=("", 0))[0] == "def" \
                and impact(starW[1]).get("def", 0) >= 16:
            star_def = (sp, game_noun(starW[1], rng, parts=1))
        f["_season"] = season
        bitter.react_game(ctx, season, cal, phase, g, f, W, L, sp, lp, imp, ctx.rng(season, "bitter", g["id"]),
                          tw_, tl_, star_def, lines, track=track, stars=(starW, starL))
        if phase == "playoffs" and week == 5:
            # The TV host takes a victory lap if he called it.
            for t in bitter._takes(ctx):
                if t["season"] == season and t.get("team") == W and t["kind"] == "rex_champ" and not t.get("settled"):
                    t["settled"] = True
                    ctx.post(season, cal, bitter.persona("RexTakes"), Say("rex_right_champ", {
                        "k": t["week"], "Tc": ctx.city(W), "champ": ctx.champ_name(season)}), teams=[W],
                        quote={"of": t["id"], "when": f"Week {t['week']}"}, importance=60)
        if phase == "playoffs" and week == 5 and not tie:
            ctx.post(season, cal, ctx.insider(ctx.rng(season, "beat", g["id"])),
                     f"The {ctx.full(W)} are your {ctx.champ_name(season)} champions. {ws}-{ls}"
                     f"{' in OT' if ot else ''} over {ctx.city(L)}.", teams=[W, L], importance=95)


def _fan_post(ctx, season, cal, tid, rng, won, margin, phase, week, rec, star, W, L, ws, ls):
    """A fan after a preseason game or a tie (other games: engine/bitter.py, react_game)."""
    opp = L if tid == W else W
    if phase == "preseason":
        if rng.random() > 0.3:
            return
        bucket = "fan_preseason"
    elif won is None:
        bucket = "fan_tie"
    else:
        return
    facts = {"NICK": ctx.nick(tid).upper(), "nick": ctx.nick(tid), "star": star.last_name if star else "",
             "city": ctx.city(tid), "opp": ctx.nick(opp), "score": f"{ws}-{ls}", "lost": won is False}
    ctx.post(season, cal, ctx.fan(tid, rng), Say(bucket, facts), teams=[tid], importance=12)


# ---------------------------------------------------------------------------
# Big performances, milestones and records (one regular season at a time)
# ---------------------------------------------------------------------------

def _career_base(ctx, season):
    """{pid: regular-season totals before this season} from the archived career lines."""
    out = defaultdict(lambda: defaultdict(float))
    for r in ctx.league.career:
        if r["phase"] == "regular" and r["season"] < season:
            for k, v in r["stats"].items():
                if not k.endswith("_long"):
                    out[r["pid"]][k] += v
    return out


def _season_records(ctx, season):
    """{stat: (value, pid, season)}: the most in a regular season before this one."""
    by = defaultdict(lambda: defaultdict(float))
    for r in ctx.league.career:
        if r["phase"] == "regular" and r["season"] < season:
            for k in SEASON_MARKS:
                by[(r["pid"], r["season"])][k] += r["stats"].get(k, 0)
    best = {}
    for (pid, s), t in by.items():
        for k, v in t.items():
            if v > best.get(k, (0,))[0]:
                best[k] = (v, pid, s)
    return best


def _whole_career_known(ctx, p):
    """Is his whole pro career in the league's records? (Veterans who were
    already in the league when it began have earlier seasons we don't have.)"""
    return p.draft_year >= ctx.first


def _performances_and_milestones(ctx, season, games, recs, track=None):
    reg = [(g, b) for ph, g, b in games if ph == "regular" and g.get("played") and b]
    if not reg:
        return
    running = defaultdict(lambda: defaultdict(float))
    gp = defaultdict(int)
    career = _career_base(ctx, season)
    records = _season_records(ctx, season) if season > ctx.first else {}
    best_game = defaultdict(list)          # stat -> [(week, value, pid, gid)]
    team_games = defaultdict(int)
    for w in range(1, ctx.n_weeks + 1):
        week_games = [(g, b) for g, b in reg if g["week"] == w]
        if not week_games:
            continue
        cal = 5 + w
        before = {}
        for g, b in week_games:
            team_games[g["home"]] += 1
            team_games[g["away"]] += 1
            for pid, s in _lines(b).items():
                before[pid] = dict(running[pid])
                gp[pid] += 1
                for k, v in s.items():
                    if k == "team" or not isinstance(v, (int, float)):
                        continue
                    running[pid][k] = max(running[pid][k], v) if k.endswith("_long") else running[pid][k] + v
                for stat, *_ in FEATS:
                    if s.get(stat):
                        best_game[stat].append((w, s[stat], pid, g["id"]))
        standouts = {"off": None, "def": None}
        first_item = len(ctx.items)
        for g, b in week_games:
            lines = _lines(b)
            for pid, s in lines.items():
                p = ctx.player(pid)
                if p is None:
                    continue
                _performance(ctx, season, w, cal, g, p, s, running, best_game, track)
                _milestones(ctx, season, w, cal, g, p, s, before.get(pid, {}), running[pid], gp[pid], career,
                            records, team_games)
                imp = impact(s)
                off = sum(v for k, v in imp.items() if k in ("pass", "rush", "rec", "ret"))
                de = imp.get("def", 0)
                if off and (standouts["off"] is None or off > standouts["off"][0]):
                    standouts["off"] = (off, p, s, g)
                if de and (standouts["def"] is None or de > standouts["def"][0]):
                    standouts["def"] = (de, p, s, g)
        # A busy week of season milestones (late in the season, many players pass 1,000
        # yards at once): one roll-up story league-wide; each one stays in team and player views.
        marks = [x for x in ctx.items[first_item:] if x["id"].startswith("smark-")]
        if len(marks) >= 4:
            for x in marks:
                x["importance"] = min(x["importance"], 22)
            ctx.add(season, cal + 0.05, "milestone", ctx.pick(("markroll", season), ctx.rng(season, "markroll", w), [
                f"Milestones of Week {w}", f"Week {w} milestones: {len(marks)} players reach season marks",
                f"Passing the marks: Week {w}'s milestones"]),
                "\n".join(x["body"].split(". ")[0] + "." for x in marks), teams=sorted({t for x in marks for t in x["teams"]}),
                players=[p for x in marks for p in x["players"]], importance=40, key=f"markroll-{season}-{w}")
        # The outlet's own picks, only for weeks without the league's official
        # Players of the Week (saves from before the awards existed).
        official = any(r["season"] == season and r["week"] == w
                       for r in (getattr(ctx.league, "awards", None) or {}).get("weekly", ()))
        if STANDOUTS and standouts["off"] and standouts["def"] and not official:
            _standouts(ctx, season, w, cal, standouts)
        _clinches(ctx, season, w, games, recs)


def _result_phrase(ctx, g, tid):
    home = g["home"] == tid
    pf, pa = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
    opp = ctx.full(g["away"] if home else g["home"])
    if pf > pa:
        return f"a {pf}-{pa} win over the {opp}", True
    if pf < pa:
        return f"a {pa}-{pf} loss to the {opp}", False
    return f"a {pf}-{pa} tie with the {opp}", None


def _performance(ctx, season, week, cal, g, p, s, running, best_game, track=None):
    level, stat, imp = big_game(p.position, s)
    if not level:
        return
    tid = s["team"]
    rng = ctx.rng(season, "perf", g["id"], p.id)
    res, won = _result_phrase(ctx, g, tid)
    opp = g["away"] if g["home"] == tid else g["home"]
    oc, on = ctx.city(opp), ctx.nick(opp)
    tail = f" in win over {oc}" if won else (f" in loss to {oc}" if won is False else f" in tie with {oc}")
    v = _f(s, "tkl") + _f(s, "ast") if stat == "tackles" else s.get(stat, 0)
    L = ctx.short(p, tid)
    heads = {
        "pass_yds": [f"{L} throws for {int(v)} yards{tail}", f"{L} lights up {on} for {int(v)} passing yards",
                     f"{int(v)} yards through the air for {L}{tail}"],
        "pass_td": [f"{L} throws {num(v)} touchdown passes{tail}", f"{L} tosses {num(v)} TDs{tail}"],
        "rush_yds": [f"{L} runs for {int(v)} yards{tail}", f"{L} gashes {on} for {int(v)} yards on the ground",
                     f"{int(v)} rushing yards for {L}{tail}"],
        "rush_td": [f"{L} scores {num(v)} rushing touchdowns{tail}", f"{L} runs in {num(v)} TDs{tail}"],
        "rec_yds": [f"{L} piles up {int(v)} receiving yards{tail}", f"{L} torches {on} for {int(v)} yards",
                    f"{int(v)} receiving yards for {L}{tail}"],
        "rec_td": [f"{L} catches {num(v)} touchdown passes{tail}", f"{L} hauls in {num(v)} TDs{tail}"],
        "rec": [f"{L} hauls in {int(v)} catches{tail}", f"{int(v)} catches for {L}{tail}"],
        "sacks": [f"{L} records {sacks_text(v)}{tail}", f"{L} wreaks havoc with {sacks_text(v)}",
                  f"{sacks_text(v).capitalize()} for {L}{tail}"],
        "def_int": [f"{L} picks off {num(v)} passes{tail}", f"{L} intercepts {num(v)}{tail}"],
        "def_td": [f"{L} takes it to the house{tail}", f"{L} scores on defense{tail}"],
        "kr_td": [f"{L} returns a kickoff for a touchdown{tail}", f"{L} takes a kickoff the distance{tail}"],
        "pr_td": [f"{L} returns a punt for a touchdown{tail}", f"{L} takes a punt back for a score{tail}"],
        "fgm": [f"{L} kicks {num(v)} field goals{tail}",
                f"{L} goes {int(_f(s, 'fgm'))}-for-{int(_f(s, 'fga'))} on field goals{tail}"],
        "fg_long": [f"{L} hits from {int(v)} yards{tail}", f"{int(v)}-yarder for {L}{tail}"],
        "pass_int": [f"{L} throws {num(v)} interceptions{tail}", f"Rough day for {L}: {num(v)} interceptions"],
        "tackles": [f"{L} makes {int(v)} tackles{tail}", f"{L} everywhere for {ctx.city(tid)}: {int(v)} tackles",
                    f"{int(v)} tackles for {L}{tail}"],
    }[stat]
    heads = [x for x in heads if x]
    headline = ctx.pick(("perf", season, stat), rng, heads)
    W_ = ctx.writer
    pf, pa = (g["home_score"], g["away_score"]) if g["home"] == tid else (g["away_score"], g["home_score"])
    f = {"Tc": ctx.city(tid), "Tc_poss": possessive(ctx.city(tid)), "T": ctx.full(tid),
         "pos_word": POS_WORD[p.position], "name": p.name, "when": f" in Week {week}", "result": res,
         "result_short": (f"{max(pf, pa)}-{min(pf, pa)} " + ("win over " if won else "loss to " if won is False else
                                                             "tie with ") + oc),
         "does": phrase(s, "pass", rng) if stat == "pass_int" else game_phrase(s, rng, parts=3),
         "got": game_noun(s, rng, parts=3), "stat_words": STAT_WORDS.get(stat, "")}
    if stat == "pass_int":
        sents = [f"{ctx.city(tid)} {POS_WORD[p.position]} {p.name} {f['does']} in {res} in Week {week}."]
    else:
        sents = [W_.say("perf_lead", rng, f)]
    # The most by anyone in a game this season? (From Week 3 on.)
    if week >= 3 and stat != "pass_int":
        others = [x[1] for x in best_game[stat] if x[0] <= week and not (x[2] == p.id and x[3] == g["id"])]
        if others and v > max(others):
            if stat in STAT_WORDS:
                sents.append(W_.say("perf_best", rng, f))
            elif stat == "fg_long":
                sents.append("It's the longest field goal in the league this season.")
    # A streak he's on.
    if track and stat != "pass_int":
        best = max(track.streaks_for(p.id, week), key=lambda x: x[1] - x[4], default=None)
        if best and best[1] >= best[4]:
            sents.append(W_.say("perf_streak", rng, {"streak_n": num(best[1]), "streak_ord": ordinal(best[1]),
                                                     "streak_what": best[2], "streak_whats": best[3]}))
    # Where he stands for the season.
    if stat in STAT_WORDS and week >= 2:
        total = running[p.id].get(stat, 0)
        better = sum(1 for pid, t in running.items() if t.get(stat, 0) > total)
        f.update(season_amount=season_amount(stat, total), rank="the most in the league" if better == 0 else (
            f"{ordinal(better + 1)} in the league" if better < 5 else ""))
        sents.append(W_.say("perf_rank" if f["rank"] else "perf_total", rng, f))
    if level == 2:
        # A dominant game: its own story. (A big one is celebrated on Bitter only.)
        ctx.add(season, cal, "performance", headline, " ".join(sents), teams=[tid, opp], players=[p.id],
                importance=imp + (5 if ctx.caliber(p) >= STAR else 0), key=f"perf-{season}-{g['id']}-{p.id}")
    else:
        imp = 32
    from . import bitter
    bitter.react_performance(ctx, season, cal, week, p, tid, stat, f["got"], num(_f(s, "pass_int")), rng, imp,
                             opp=opp, track=track)
    # Social: the stat desk on dominant games; the player himself and a fan sometimes.
    if stat != "pass_int":
        if level == 2:
            ctx.post(season, cal, ctx.stat_desk(), Say("stat_dominant", {
                "name": p.name, "abbr": ctx.teams[tid].abbrev, "oabbr": ctx.teams[opp].abbrev, "line": stat_line(s),
                "rank": bool(f.get("rank")), "rank_t": f"{f.get('season_amount', '')}, {f.get('rank', '')}".capitalize()
                if f.get("rank") else ""}), teams=[tid], players=[p.id],
                importance=imp - (15 if stat in ("fgm", "fg_long") else 5))
        if stat in ("fgm", "fg_long"):
            return
        pf, pa = (g["home_score"], g["away_score"]) if g["home"] == tid else (g["away_score"], g["home_score"])
        rec = SL.rec_text(track.record(tid, week)) if track else ""
        if rng.random() < 0.45:
            bitter.player_post(ctx, season, cal, p, tid, won, rng, imp - 15, opp, {
                "score": f"{max(pf, pa)}-{min(pf, pa)}", "rec": rec, "got": f["got"]})
        if rng.random() < 0.5:
            skill = stat in ("pass_yds", "pass_td", "rush_yds", "rush_td", "rec_yds", "rec_td", "rec")
            ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_perf_win" if won is not False else "fan_perf_loss", {
                "last": p.last_name, "LAST": p.last_name.upper(), "got": f["got"], "opp": ctx.nick(opp),
                "skill": skill, "qb": skill and p.position == "QB", "defense": not skill}),
                teams=[tid], players=[p.id], importance=15)


def _milestones(ctx, season, week, cal, g, p, s, before, after, games_played, career, records, team_games):
    tid = s["team"]
    opp = g["away"] if g["home"] == tid else g["home"]
    rng = ctx.rng(season, "mile", g["id"], p.id)
    done = set()
    # League single-season records (since the league began).
    for stat, (val, holder, held_season) in records.items():
        b, a = before.get(stat, 0), after.get(stat, 0)
        if b <= val < a:
            hp = ctx.player(holder)
            who = f"{hp.name} ({held_season})" if hp else str(held_season)
            words = STAT_WORDS[stat]
            amount = f"{a:g}" if stat == "sacks" else f"{int(a):,}"
            ctx.add(season, cal, "milestone", ctx.pick(("rec", season, cal), rng, [
                f"{ctx.short(p, tid)} sets league record for {words} in a season",
                f"Record: {ctx.short(p, tid)} passes {hp.last_name if hp else 'the old mark'} for most {words} in a season"]),
                f"{p.name} of the {ctx.full(tid)} has {amount} {words} this season after Week {week} against the "
                f"{ctx.full(opp)}, the most in a season since the league began in {ctx.first}. The old record was "
                f"{val:g} by {who}.", teams=[tid], players=[p.id] + ([holder] if hp else []), importance=75,
                key=f"rec-{season}-{stat}-{p.id}")
            ctx.post(season, cal, ctx.stat_desk(), Say("stat_record", {
                "name": p.name, "amount": amount, "words": words, "old": f"{val:g}", "who": who}),
                teams=[tid], players=[p.id], importance=70)
            done.add(stat)
    # Season marks.
    for stat, marks in SEASON_MARKS.items():
        if stat in done:
            continue
        b, a = before.get(stat, 0), after.get(stat, 0)
        crossed = [m for m in marks if b < m <= a]
        if not crossed:
            continue
        m = crossed[-1]
        words = STAT_WORDS[stat]
        mark = f"{m:,}"
        pace = ""
        tg = team_games.get(tid, 0)
        season_games = ctx.n_weeks - 1
        if tg and week <= ctx.n_weeks - 3:
            proj = a / tg * season_games
            pace = f" He's on pace for about {int(round(proj, -1 if proj >= 100 else 0)):,} over {season_games} games."
        ctx.add(season, cal, "milestone", ctx.pick(("smark", season, cal), rng, [
            f"{ctx.short(p, tid)} reaches {mark} {words}", f"{ctx.short(p, tid)} tops {mark} {words} for the season",
            f"{mark} {words} and counting for {ctx.short(p, tid)}"]),
            f"{p.name} ({ctx.teams[tid].abbrev}, {pos_abbr(p)}) reached {mark} {words} for the season in Week {week} "
            f"against the {ctx.full(opp)}. He has {season_amount(stat, a)} through "
            f"{plural(games_played, 'game')}.{pace}", teams=[tid], players=[p.id],
            importance=34 + 6 * marks.index(m), key=f"smark-{season}-{stat}-{p.id}-{m}")
        ctx.post(season, cal, ctx.stat_desk(), Say("stat_mark", {
            "name": p.name, "abbr": ctx.teams[tid].abbrev, "amount": f"{a:g}" if stat == "sacks" else f"{int(a):,}",
            "words": words, "week": week, "mark": mark, "gp_t": plural(games_played, "game"), "pace": bool(pace) and
            f"about {int(round(proj, -1 if proj >= 100 else 0)):,}"}), teams=[tid], players=[p.id],
            importance=30 + 6 * marks.index(m))
    # Career marks (only players whose whole career is on record).
    if not _whole_career_known(ctx, p):
        return
    base = career.get(p.id, {})
    for stat, marks in CAREER_MARKS.items():
        b = base.get(stat, 0) + before.get(stat, 0)
        a = base.get(stat, 0) + after.get(stat, 0)
        crossed = [m for m in marks if b < m <= a]
        if not crossed:
            continue
        m = crossed[-1]
        words = STAT_WORDS[stat]
        ctx.add(season, cal, "milestone", ctx.pick(("cmark", season, cal), rng, [
            f"{ctx.short(p, tid)} reaches {m:,} career {words}", f"Milestone: {m:,} career {words} for {ctx.short(p, tid)}"]),
            f"{p.name} of the {ctx.full(tid)} reached {m:,} career {words} in Week {week} against the "
            f"{ctx.full(opp)}, in his {ordinal(season - p.draft_year + 1)} season.", teams=[tid], players=[p.id],
            importance=45 + 5 * marks.index(m), key=f"cmark-{season}-{stat}-{p.id}-{m}")


def _standouts(ctx, season, week, cal, st):
    rng = ctx.rng(season, "standouts", week)
    o, d = st["off"], st["def"]
    po_, pd_ = o[1], d[1]
    def res(g, s):
        r, won = _result_phrase(ctx, g, s["team"])
        return r
    body = (f"Offense: {po_.name} ({ctx.teams[o[2]['team']].abbrev}) {game_phrase(o[2], rng, 3)} in {res(o[3], o[2])}. "
            f"Defense: {pd_.name} ({ctx.teams[d[2]['team']].abbrev}) {game_phrase(d[2], rng, 1)} in {res(d[3], d[2])}.")
    ctx.add(season, cal, "performance", ctx.pick(("stand", season), rng, [
        f"Week {week} standouts: {po_.last_name} and {pd_.last_name}",
        f"Our Week {week} picks: {po_.last_name} on offense, {pd_.last_name} on defense",
        f"Best of Week {week}: {po_.last_name}, {pd_.last_name}"]),
        body, teams=[o[2]["team"], d[2]["team"]], players=[po_.id, pd_.id], importance=40,
        key=f"standouts-{season}-{week}")


# ---------------------------------------------------------------------------
# Playoff race: clinching and elimination (careful math: only certain
# outcomes; ties count against the team, so a clinch is never announced early)
# ---------------------------------------------------------------------------

def _clinches(ctx, season, week, games, recs):
    if week < 8:
        return
    league = ctx.league
    reg = [g for ph, g, _b in games if ph == "regular"]
    rec = recs.get(week)
    prev = recs.get(week - 1)
    if not rec or any(not g.get("played") for g in reg if g["week"] == week):
        return
    left = defaultdict(int)
    for g in reg:
        if g["week"] > week:
            left[g["home"]] += 1
            left[g["away"]] += 1

    def status(rec, left):
        pts = {tid: r[0] + 0.5 * r[2] for tid, r in rec.items()}
        mx = {tid: pts[tid] + left[tid] for tid in rec}
        out = {}
        for tid, t in ctx.teams.items():
            conf = [o for o in ctx.teams.values() if o.conference == t.conference and o.id != tid]
            div = [o for o in conf if o.division == t.division]
            div_won = all(mx[o.id] < pts[tid] for o in div)
            top = all(mx[o.id] < pts[tid] for o in conf)
            threats = defaultdict(int)
            for o in conf:
                if mx[o.id] >= pts[tid]:
                    threats[o.division] += 1
            berth = div_won or sum(max(0, n - 1) for n in threats.values()) <= 2
            sure = defaultdict(int)
            for o in conf:
                if pts[o.id] > mx[tid]:
                    sure[o.division] += 1
            out_div = sure.get(t.division, 0) > 0
            elim = out_div and sum(max(0, n - 1) for n in sure.values()) >= 3
            out[tid] = {"top": top, "div": div_won, "berth": berth, "elim": elim}
        return out

    now = status(rec, left)
    left_prev = defaultdict(int)
    for g in reg:
        if g["week"] > week - 1:
            left_prev[g["home"]] += 1
            left_prev[g["away"]] += 1
    before = status(prev, left_prev) if prev else {}
    cal = 5 + week + 0.5
    for tid, st in now.items():
        b = before.get(tid, {})
        rng = ctx.rng(season, "clinch", week, tid)
        c, t = ctx.city(tid), ctx.teams[tid]
        r = _rec_text(rec[tid])
        news = None
        if st["top"] and not b.get("top"):
            news = (f"{c} clinches the {t.conference} Conference's top seed",
                    f"At {r}, the {t.name} have locked up the No. 1 seed in the {t.conference} Conference and the "
                    f"only first-round bye, with home field through the conference championship.", 72, "top")
        elif st["div"] and not b.get("div"):
            news = (ctx.pick(("clinch", season, week), rng, [f"{c} clinches the {t.division} Division",
                                                             f"{c} wraps up {t.division} title"]),
                    f"The {t.name} ({r}) have clinched the {t.division} Division" +
                    (f" with {plural(left[tid], 'game')} to play." if left[tid] else " on the last weekend of the "
                     "regular season."), 65, "div")
        elif st["berth"] and not b.get("berth"):
            news = (ctx.pick(("clinch", season, week), rng, [f"{c} clinches a playoff spot",
                                                             f"{c} is in: playoff berth secured"]),
                    f"The {t.name} ({r}) have clinched at least a wild card spot in the {t.conference} Conference "
                    f"playoffs.", 60, "berth")
        elif st["elim"] and not b.get("elim"):
            news = (ctx.pick(("elim", season, week), rng, [f"{c} eliminated from playoff contention",
                                                           f"{possessive(c)} playoff hopes end"]),
                    f"At {r}, the {t.name} can no longer reach the playoffs.", 40, "elim")
        if news:
            ctx.add(season, cal, "playoffs", news[0], news[1], teams=[tid], importance=news[2],
                    key=f"clinch-{season}-{tid}-{news[3]}")
            ff = {"rec": r, "city": c}
            if news[3] == "elim":
                ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_elim", ff), teams=[tid], importance=20)
            else:
                ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_clinch", ff), teams=[tid], importance=40)
                ctx.post(season, cal, ctx.beat(tid), Say("beat_clinch", {
                    "headline": news[0], "headline_lc": news[0][:1].lower() + news[0][1:], "rec": r}),
                    teams=[tid], importance=news[2] - 10)
                from . import bitter
                bitter.react_clinch(ctx, season, cal, tid, news[3], rng, rec=r,
                                    left_t=plural(left[tid], "game") if left[tid] else "one weekend")


# ---------------------------------------------------------------------------
# Injuries, moves, the draft, retirements, the season
# ---------------------------------------------------------------------------

def _injuries(ctx, season, games):
    """Game-costing injuries from the injury history."""
    league = ctx.league
    total_end = 5 + ctx.n_weeks + 5
    opponents = {}
    for phase, g, _b in games:
        lab = ctx.game_label(season, phase, g)
        opponents[(g["home"], lab)] = g["away"]
        opponents[(g["away"], lab)] = g["home"]
    hurt_before = set()
    # Two injuries to one player in the same game (a flare-up, then a new one) make one story.
    entries = [(n, e) for n, e in enumerate(league.injury_history)
               if e["season"] == season and (e.get("weeks") or 0) > 0]
    last_of = {(e["pid"], e.get("game")): n for n, e in entries}
    first_what = {}
    for n, e in entries:
        if last_of[(e["pid"], e.get("game"))] != n:
            first_what[(e["pid"], e.get("game"))] = e
    for n, e in entries:
        if last_of[(e["pid"], e.get("game"))] != n:
            continue
        p = ctx.player(e["pid"])
        if p is None or e.get("team") not in ctx.teams:
            continue
        tid = e["team"]
        cal = ctx.label_cal(e.get("game"))
        if cal < 0:
            continue
        cal += 0.2
        rng = ctx.rng(season, "inj", n)
        weeks = e["weeks"]
        remaining = total_end - int(cal)
        season_over = weeks >= I.SEASON_ENDING_WEEKS or weeks >= remaining
        # Back, at the earliest, after the last regular-season week.
        rest_of_regular = (not season_over and 6 <= cal and int(cal) <= 5 + ctx.n_weeks - 3
                           and int(cal) + weeks > 5 + ctx.n_weeks)
        opp = opponents.get((tid, e.get("game")))
        how = e.get("how") or ""
        where = ("in practice during training camp" if e.get("game") == "Training camp"
                 else f"in {e.get('game')}" + (f" against the {ctx.full(opp)}" if opp else ""))
        inj = injury_phrase(e.get("kind"))
        part = injury_short(e.get("kind"))
        concussion = I.is_concussion(e.get("kind"))
        if how in ("aggravated", "re-injured"):
            what = f"{'aggravated' if how == 'aggravated' else 're-injured'} his {part}"
        elif concussion:
            what = "suffered a concussion"
        else:
            what = f"suffered {inj}"
        earlier = first_what.get((e["pid"], e.get("game")))
        if earlier:
            e_how = earlier.get("how") or ""
            first = (f"{'aggravated' if e_how == 'aggravated' else 're-injured'} his {injury_short(earlier.get('kind'))}"
                     if e_how in ("aggravated", "re-injured") else f"suffered {injury_phrase(earlier.get('kind'))}")
            what = f"{first} and {what.replace('suffered ', '')}" if what.startswith("suffered") and \
                first.startswith("suffered") else f"{first}, then {what}"
        if season_over:
            vp = rng.choice(["will miss the rest of the season", "is out for the season"])
        elif rest_of_regular:
            vp = "is expected to miss the rest of the regular season"
        elif concussion:
            vp = "is in the league's concussion protocol"
        else:
            vp = f"is expected to miss about {plural(weeks, 'week')}"
        notable = ctx.notable(p, tid)
        star = ctx.caliber(p) >= STAR or (p.position == "QB" and p.id in ctx.starters.get(tid, ()))
        long_out = season_over or rest_of_regular
        # League-wide (25+): a notable player out 4+ weeks or for the season, or any star.
        imp = ((12 if not notable else 20) + (10 if weeks >= 4 else 0) + (15 if long_out and notable else 0)
               + (12 if star else 0))
        c = ctx.city(tid)
        L = ctx.short(p, tid)
        bare = inj.split(" ", 1)[1] if inj.startswith(("a ", "an ")) else inj
        if season_over:
            heads = [f"{c} loses {pos_abbr(p)} {L} for the season", f"{possessive(c)} {L} out for season with {bare}",
                     f"Season over for {possessive(c)} {L}"]
        elif rest_of_regular:
            heads = [f"{possessive(c)} {L} out for the regular season with {bare}",
                     f"{c} without {pos_abbr(p)} {L} for the rest of the regular season"]
        elif concussion:
            heads = [f"{possessive(c)} {L} in concussion protocol", f"{c} {pos_abbr(p)} {L} suffers concussion"]
        elif p.id in hurt_before:
            heads = [f"{possessive(c)} {L} hurt again, out about {plural(weeks, 'week')}",
                     f"Another injury for {possessive(c)} {L}"]
        else:
            heads = [f"{possessive(c)} {L} expected to miss about {plural(weeks, 'week')}",
                     f"{c} {pos_abbr(p)} {L} hurt, out about {plural(weeks, 'week')}",
                     f"{possessive(c)} {L} sidelined by {part} injury" if part not in ("injury", "undisclosed") else
                     f"{possessive(c)} {L} sidelined"]
        headline = ctx.pick(("inj", season, int(cal)), rng, heads)
        hurt_before.add(p.id)
        body = f"{ctx.full(tid)} {POS_WORD[p.position]} {p.name} {what} {where} and {vp}."
        if star and long_out and p.id in ctx.starters.get(tid, ()):
            body += f" He was {possessive(c)} starting {POS_WORD[p.position]}."
        ctx.add(season, cal, "injury", headline, body, teams=[tid], players=[p.id], importance=imp,
                key=f"inj-{season}-{n}")
        if notable and imp >= 40:
            wk = int(cal)
            inf = {"c": c, "pos": pos_abbr(p), "pos_word": POS_WORD[p.position], "name": p.name, "last": p.last_name,
                   "part": part, "vp": vp, "bare": bare, "partok": part not in ("injury", "undisclosed"),
                   "city": ctx.city(tid)}
            top = ctx.post(season, cal, ctx.insider(rng), Say("ins_injury", inf), teams=[tid], players=[p.id],
                           importance=imp - 5)
            ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_injury", inf), teams=[tid], players=[p.id],
                     importance=imp - 15, reply_to=top)
            from . import bitter
            bitter.react_injury(ctx, season, cal, p, tid, part, vp, rng, imp, top)
            if long_out and rng.random() < 0.6:
                ctx.post(season, cal, ctx.player_voice(p), Say("player_injury", dict(inf, season_out="season" in vp)),
                         teams=[tid], players=[p.id], importance=imp - 10)


_MOVE_TEXT = {
    "Placed on injured reserve": "placed {pos} {name} on injured reserve",
    "Placed on PUP": "placed {pos} {name} on the physically unable to perform list",
    "Activated from injured reserve": "activated {pos} {name} from injured reserve",
    "Activated from PUP": "activated {pos} {name} from the physically unable to perform list",
    "Released from practice squad": "released {pos} {name} from the practice squad",
    "Waived": "waived {pos} {name}",
    "Released": "released {pos} {name}",
    "Signed": "signed {pos} {name}",
    "Signed to practice squad": "signed {pos} {name} to the practice squad",
    "Promoted from practice squad": "promoted {pos} {name} from the practice squad",
    "Placed on practice squad injured list": "placed {pos} {name} on the practice squad injured list",
    "Back to practice squad": "returned {pos} {name} to the practice squad",
    "Elevated for the game": "elevated {pos} {name} from the practice squad for the game",
}


def _moves(ctx, season):
    league = ctx.league
    groups = defaultdict(list)
    for n, t in enumerate(league.transactions):
        if t.get("season") != season or t.get("team") not in ctx.teams:
            continue
        groups[(t.get("when"), t["team"])].append((n, t))
    last_release = {}
    for n, t in enumerate(league.transactions):
        if t.get("move") in ("Released", "Waived") and t.get("season") == season:
            last_release.setdefault(t["pid"], []).append((n, t))
    # Cut-downs and camp (final cuts, training camp, the preseason, the offseason) log
    # hundreds of moves at once: those get one league-wide roll-up story each, and only
    # a star's release gets a story of its own.
    rollup = defaultdict(lambda: {"cut": [], "signed": []})
    for (when, tid), moves in groups.items():
        cal = ctx.label_cal(when)
        cal = cal + 0.3 if cal >= 0 else -1
        bulk = cal < 6 or when in ("Final cuts", "Training camp")
        lines = []
        players = []
        for n, t in moves:
            p = ctx.player(t["pid"])
            if p is None:
                continue
            tmpl = _MOVE_TEXT.get(t["move"], t["move"] + ": {pos} {name}")
            txt = tmpl.format(pos=pos_abbr(p), name=p.name)
            if t.get("note"):
                txt += " (" + re.sub(r" \((.*)\)$", r", \1", t["note"]) + ")"
            lines.append(txt[0].upper() + txt[1:] + ".")
            players.append(p.id)
            if not bulk:
                _notable_move(ctx, season, cal, n, t, p, last_release)
                continue
            c = ctx.caliber(p)
            # Veterans only (specialists rate high on their own scale, so they need real experience too).
            vet = p.experience >= (5 if p.position in ("K", "P", "LS") else 3)
            weight = c + 2 * min(p.experience, 8) - (15 if p.position in ("K", "P", "LS") else 0)
            if t["move"] in ("Released", "Waived"):
                if c >= STAR - 4 and vet and p.position not in ("K", "P", "LS"):
                    _notable_move(ctx, season, cal, n, t, p, last_release)
                elif vet and (c >= NOTABLE - 4 or (p.experience >= 7 and c >= 50)):
                    rollup[(when, cal)]["cut"].append((weight, p, tid))
            elif t["move"] == "Signed" and p.experience >= 5 and (c >= 50 or p.experience >= 8):
                rollup[(when, cal)]["signed"].append((weight, p, tid))
        if not lines:
            continue
        if len(lines) > 12:
            # A big day (cut-downs): the counts, then the names fans know.
            counts = defaultdict(int)
            for _n, t in moves:
                counts[t["move"]] += 1
            summary = "; ".join(f"{m.lower()}: {k}" for m, k in sorted(counts.items(), key=lambda kv: -kv[1]))
            known = sorted((ctx.player(t["pid"]) for _n, t in moves if ctx.player(t["pid"])),
                           key=lambda q: -ctx.caliber(q))[:8]
            body = (f"{len(lines)} moves ({summary}). Among them: "
                    + ", ".join(f"{pos_abbr(q)} {q.name} ({next(t['move'] for _n, t in moves if t['pid'] == q.id).lower()})"
                                for q in known) + ".")
        else:
            body = " ".join(lines)
        ctx.add(season, cal, "moves", f"{ctx.full(tid)} transactions: {when or 'offseason'}", body,
                teams=[tid], players=players, importance=12, key=f"moves-{season}-{when}-{tid}")
    for (when, cal), r in rollup.items():
        label = when or "the offseason"
        for kind, rows, imp in (("cut", r["cut"], 45), ("signed", r["signed"], 30)):
            if not rows:
                continue
            rows.sort(key=lambda x: -x[0])
            names = [f"{ctx.teams[tid].abbrev} {pos_abbr(p)} {p.name}" + (f" ({plural(p.experience, 'season')})"
                                                                         if p.experience else " (rookie)")
                     for _c, p, tid in rows[:15]]
            more = f"\n...and {len(rows) - 15} more." if len(rows) > 15 else ""
            if kind == "cut":
                head = f"{label}: the notable veterans let go"
                intro = plural(len(rows), 'veteran')
                intro = intro[:1].upper() + intro[1:] + \
                    f" of note {'was' if len(rows) == 1 else 'were'} released or waived."
            else:
                head = f"{label}: veterans signed"
                intro = f"Teams signed {plural(len(rows), 'veteran')} of five or more seasons."
            ctx.add(season, cal, "moves", head[0].upper() + head[1:], intro + "\n" + "\n".join(names) + more,
                    teams=sorted({x[2] for x in rows}), players=[x[1].id for x in rows], importance=imp,
                    key=f"rollup-{season}-{when}-{kind}")


def _notable_move(ctx, season, cal, n, t, p, last_release):
    tid, move = t["team"], t["move"]
    rng = ctx.rng(season, "move", n)
    c, L = ctx.city(tid), ctx.short(p, tid)
    cal_imp = ctx.caliber(p)
    if move in ("Released", "Waived") and (cal_imp >= NOTABLE - 4 or (p.experience >= 7 and cal_imp >= 50)):
        vet = "veteran " if p.experience >= 6 else ""
        heads = [f"{c} releases {vet}{pos_abbr(p)} {p.name}", f"{c} cuts {pos_abbr(p)} {L}",
                 f"{L} let go by {c}"]
        body = (f"The {ctx.full(tid)} {'waived' if move == 'Waived' else 'released'} {vet}{POS_WORD[p.position]} "
                f"{p.name}, {'a ' + plural(p.experience, 'year') + ' pro' if p.experience else 'a rookie'}"
                f"{', in ' + t['when'] if t.get('when') else ''}.")
        if t.get("note"):
            body += f" Note: {t['note']}."
        ctx.add(season, cal, "moves", ctx.pick(("rel", season, int(cal)), rng, heads), body, teams=[tid],
                players=[p.id], importance=26 + (10 if cal_imp >= NOTABLE else 0), key=f"rel-{season}-{n}")
        ctx.post(season, cal, ctx.insider(rng), Say("ins_release", {
            "c": c, "vet": vet, "pos": pos_abbr(p), "name": p.name, "exp": p.experience >= 4,
            "exp_t": f"{p.experience}-year"}), teams=[tid], players=[p.id], importance=28)
    elif move == "Signed" and (cal_imp >= NOTABLE - 4 or p.experience >= 6):
        prior = [x for x in last_release.get(p.id, []) if x[0] < n and x[1]["team"] != tid]
        frm = (f" He was {'waived' if prior[-1][1]['move'] == 'Waived' else 'released'} by the "
               f"{ctx.full(prior[-1][1]['team'])}" + (f" in {prior[-1][1]['when']}" if prior[-1][1].get("when") else "")
               + ".") if prior else ""
        heads = [f"{c} signs {pos_abbr(p)} {p.name}", f"{L} lands with {c}", f"{c} adds {pos_abbr(p)} {L}"]
        body = (f"The {ctx.full(tid)} signed {POS_WORD[p.position]} {p.name}"
                f"{', a ' + plural(p.experience, 'year') + ' pro' if p.experience else ''}.{frm}")
        ctx.add(season, cal, "moves", ctx.pick(("sign", season, int(cal)), rng, heads), body, teams=[tid],
                players=[p.id], importance=24 + (8 if cal_imp >= NOTABLE else 0), key=f"sign-{season}-{n}")
        from . import bitter
        bitter.react_sign(ctx, season, cal, tid, p, rng, extra={
            "prev": bool(prior), "prev_team": ctx.full(prior[-1][1]["team"]) if prior else ""})
    elif move.startswith("Activated from") and ctx.notable(p, tid):
        from . import bitter
        list_name = "injured reserve" if "injured" in move else "the PUP list"
        bitter.react_sign(ctx, season, cal, tid, p, rng, back=True, extra={"list_name": list_name})
        ctx.add(season, cal, "moves", ctx.pick(("act", season, int(cal)), rng, [
            f"{c} activates {pos_abbr(p)} {L} from {'injured reserve' if 'injured' in move else 'PUP'}",
            f"{c} gets {L} back"]),
            f"The {ctx.full(tid)} activated {POS_WORD[p.position]} {p.name} from "
            f"{'injured reserve' if 'injured' in move else 'the physically unable to perform list'}"
            f"{' in ' + t['when'] if t.get('when') else ''}.", teams=[tid], players=[p.id], importance=34,
            key=f"act-{season}-{n}")
        ctx.post(season, cal, ctx.fan(tid, rng), Say("fan_back", {
            "last": p.last_name, "LAST": p.last_name.upper(), "list_name": list_name}),
            teams=[tid], players=[p.id], importance=15)
    elif move == "Promoted from practice squad":
        ctx.add(season, cal, "moves", ctx.pick(("promo", season, int(cal)), rng, [
            f"{c} promotes {pos_abbr(p)} {L} to the 53", f"{L} earns a roster spot in {c}"]),
            f"The {ctx.full(tid)} promoted {POS_WORD[p.position]} {p.name} from the practice squad to the 53-man "
            f"roster.", teams=[tid], players=[p.id], importance=16, key=f"promo-{season}-{n}")
        # The player celebrates his first call-up of the season (not every game-day elevation).
        promoted = ctx.__dict__.setdefault("_promoted", set())
        if (season, p.id) not in promoted and rng.random() < 0.3:
            ctx.post(season, cal, ctx.player_voice(p), Say("player_promo", {"city": c, "Nick": ctx.nick(tid)}),
                     teams=[tid], players=[p.id], importance=14)
        promoted.add((season, p.id))


def _draft(ctx, season):
    league = ctx.league
    picks = sorted((d for d in league.draft_history if d["season"] == season), key=lambda d: d["pick"])
    if not picks:
        return
    cal = -2
    rng = ctx.rng(season, "draft")
    first = picks[0]
    p = ctx.player(first["pid"])
    prev = {h["team"]: h for h in league.team_history if h["season"] == season - 1}

    def combine_note(p):
        c = p.combine or {}
        if c.get("forty") and c["forty"] <= 4.40:
            return f"He ran the 40-yard dash in {c['forty']:.2f} seconds at the combine."
        if c.get("bench") and c["bench"] >= 33:
            return f"He did {c['bench']} bench press reps at the combine."
        if c.get("vertical") and c["vertical"] >= 40:
            return f"He jumped {c['vertical']:g} inches in the vertical at the combine."
        return ""

    if p:
        tid = first["team"]
        h = prev.get(tid)
        why = f" {ctx.city(tid)} earned the pick with a {h['w']}-{h['l']}{'-' + str(h['t']) if h['t'] else ''} " \
              f"record in {season - 1}." if h else ""
        ctx.add(season, cal, "draft", ctx.pick(("d1", season), rng, [
            f"{ctx.city(tid)} takes {pos_abbr(p)} {p.name} first overall", f"{p.name} goes No. 1 to {ctx.city(tid)}"]),
            f"The {ctx.full(tid)} made {POS_WORD[p.position]} {p.name} of {p.college} the first pick of the {season} "
            f"draft.{why} {combine_note(p)}".strip(), teams=[tid], players=[p.id], importance=75,
            key=f"draft1-{season}")
        pf = {"c": ctx.city(tid), "city": ctx.city(tid), "name": p.name, "pos": pos_abbr(p), "college": p.college}
        ctx.post(season, cal, ctx.insider(rng), Say("ins_first_pick", pf), teams=[tid], players=[p.id], importance=70)
        ctx.post(season, cal, ctx.player_voice(p), Say("player_first_pick", pf), teams=[tid], players=[p.id],
                 importance=50)
    rnd1 = [d for d in picks if d["round"] == 1]
    lines = []
    for d in rnd1:
        q = ctx.player(d["pid"])
        if q:
            lines.append(f"{d['pick']}. {ctx.teams[d['team']].abbrev}: {pos_abbr(q)} {q.name}, {q.college}")
    if lines:
        by_pos = defaultdict(int)
        for d in rnd1:
            q = ctx.player(d["pid"])
            if q:
                by_pos[q.position] += 1
        most = max(by_pos.items(), key=lambda kv: kv[1])
        note = (f"{pos_plural(most[0], most[1]).capitalize()} went in the first round, the most of any position."
                if most[1] >= 4 else "")
        ctx.add(season, cal, "draft", f"{season} draft: the first round", "\n".join(lines) + ("\n" + note if note else ""),
                teams=list({d["team"] for d in rnd1}), players=[d["pid"] for d in rnd1], importance=60,
                key=f"draftr1-{season}")
        from . import bitter
        for d in rnd1:
            q = ctx.player(d["pid"])
            if q is None:
                continue
            frng = ctx.rng(season, "dfan", d["pick"])
            first_of_team = d["pick"] == min(x["pick"] for x in picks if x["team"] == d["team"])
            bitter.react_pick(ctx, season, cal, d, q, frng, first_of_team=first_of_team)
            ctx.post(season, cal, ctx.fan(d["team"], frng), Say("fan_pick", {
                "last": q.last_name, "pick": d["pick"], "pos_word": POS_WORD[q.position], "college": q.college,
                "city": ctx.city(d["team"])}), teams=[d["team"]], players=[q.id], importance=18)
    # Each team's class.
    by_team = defaultdict(list)
    for d in picks:
        by_team[d["team"]].append(d)
    for tid, ds in by_team.items():
        lines = []
        for d in ds:
            q = ctx.player(d["pid"])
            if q:
                lines.append(f"Round {d['round']} (No. {d['pick']}): {pos_abbr(q)} {q.name}, {q.college}")
        ctx.add(season, cal, "draft", f"{ctx.full(tid)} {season} draft class", "\n".join(lines), teams=[tid],
                players=[d["pid"] for d in ds], importance=18, key=f"dclass-{season}-{tid}")
    last = picks[-1]
    q = ctx.player(last["pid"])
    if q and len(picks) > 32:
        ctx.add(season, cal, "draft", f"{q.name} is this year's Mr. Irrelevant",
                f"{ctx.city(last['team'])} took {POS_WORD[q.position]} {q.name} of {q.college} with the last pick of "
                f"the {season} draft, No. {last['pick']} overall.", teams=[last["team"]], players=[q.id],
                importance=26, key=f"draftlast-{season}")
        from . import bitter
        bitter.react_last_pick(ctx, season, cal, last, q, ctx.rng(season, "lastpick"))


def _career_summary(ctx, p):
    """(seasons on record, teams, regular-season totals, titles) from his career lines."""
    by_pid = ctx.__dict__.get("_career_by_pid")
    if by_pid is None:      # indexed once per build (looping over every career line per player was slow)
        by_pid = ctx._career_by_pid = defaultdict(list)
        for r in ctx.league.career:
            by_pid[r["pid"]].append(r)
    rows = by_pid.get(p.id, ())
    reg = [r for r in rows if r["phase"] == "regular"]
    totals = defaultdict(float)
    for r in reg:
        for k, v in r["stats"].items():
            if not k.endswith("_long"):
                totals[k] += v
    teams = []
    for r in sorted(reg, key=lambda r: r["season"]):
        if r["team"] not in teams:
            teams.append(r["team"])
    titles = sorted({r["season"] for r in rows if ctx.league.champions.get(r["season"]) == r["team"]})
    return len({r["season"] for r in reg}), teams, totals, titles


def _career_numbers(p, t):
    bits = []
    if t.get("pass_yds", 0) >= 3000:
        bits.append(f"{int(t['pass_yds']):,} passing yards and {plural(t.get('pass_td', 0), 'touchdown pass', 'touchdown passes')}")
    if t.get("rush_yds", 0) >= 1500:
        bits.append(f"{int(t['rush_yds']):,} rushing yards")
    if t.get("rec_yds", 0) >= 1500:
        bits.append(f"{int(t.get('rec', 0)):,} catches for {int(t['rec_yds']):,} yards")
    if t.get("sacks", 0) >= 15:
        bits.append(f"{t['sacks']:g} sacks")
    if t.get("def_int", 0) >= 8:
        bits.append(plural(t["def_int"], "interception"))
    if t.get("fgm", 0) >= 50:
        bits.append(f"{int(t['fgm'])} field goals")
    return join_and(bits[:2])


def _retirements(ctx, season):
    """Players who retired after season-1 (announced this offseason)."""
    league = ctx.league
    rep = league.offseason_report if (league.offseason_report or {}).get("season") == season else None
    from_roster = {pid: tid for pid, tid in (rep or {}).get("retired", [])}
    for p in league.players:
        if p.retired != season - 1:
            continue
        cal_now = ctx.caliber(p)
        if p.experience < 6 and cal_now < NOTABLE:
            continue
        seasons, teams, totals, titles = _career_summary(ctx, p)
        rng = ctx.rng(season, "retire", p.id)
        whole = _whole_career_known(ctx, p)
        last_team = teams[-1] if teams else from_roster.get(p.id)
        nums = _career_numbers(p, totals)
        team_txt = ""
        if teams:
            names_ = join_and([f"the {ctx.full(t)}" for t in teams])
            team_txt = f" He played for {names_}." if whole else f" Since {ctx.first} he played for {names_}."
        stats_txt = ""
        if nums:
            if whole:
                stats_txt = f" He finishes his career with {nums}."
            elif seasons == 1:
                stats_txt = f" In his final season he had {nums}."
            else:
                stats_txt = f" In {plural(seasons, 'season')} since {ctx.first} he had {nums}."
        title_txt = ""
        if titles:
            title_txt = f" He won {join_and([ctx.champ_name(s) for s in titles])}."
        unsigned = p.id not in from_roster and rep is not None
        if not teams and from_roster.get(p.id) in ctx.teams:
            team_txt = f" He was on the {ctx.full(from_roster[p.id])} roster."
        body = (f"{POS_WORD[p.position].capitalize()} {p.name} has retired after {plural(p.experience, 'pro season')}."
                + (" He was a free agent." if unsigned else "") + team_txt + stats_txt + title_txt)
        imp = (14 + min(16, 2 * max(0, p.experience - 5)) + (14 if cal_now >= NOTABLE else 0) + 8 * len(titles)
               + (8 if nums else 0))
        heads = [f"{p.name} retires after {num(p.experience)} seasons", f"{pos_abbr(p)} {p.name} calls it a career",
                 f"{pos_abbr(p)} {p.name} retires"]     # (with the position: two players can share a name)
        ctx.add(season, -3, "retirement", ctx.pick(("ret", season), rng, heads), body,
                teams=[last_team] if last_team else [], players=[p.id], importance=imp, key=f"retire-{p.id}")
        if imp >= 40 and last_team in ctx.teams and not unsigned:
            from . import bitter
            bitter.react_retire(ctx, season, -3, last_team, p, rng)
        if imp >= 35:
            ctx.post(season, -3, ctx.player_voice(p), Say("player_retire", {
                "seasons_t": f"{num(p.experience).capitalize()} seasons", "has_city": last_team in ctx.teams,
                "city": ctx.city(last_team) if last_team in ctx.teams else ""}),
                teams=[last_team] if last_team else [], players=[p.id], importance=imp)


def _season_summary(ctx, season, games):
    """The season in review (after the championship) and the playoff field."""
    league = ctx.league
    current = season == league.season
    if current and not S.season_over(league):
        lines_t = None
    else:
        lines_t = [h for h in league.team_history if h["season"] == season]
    if current and S.season_over(league):
        lines_t = S.team_season_summary(league)
    if not lines_t:
        return
    champ = league.champions.get(season) or (po.champion(league) if current else None)
    cal = 5 + ctx.n_weeks + 6
    best = max(lines_t, key=lambda h: (h["w"] + 0.5 * h["t"], h["pf"] - h["pa"]))
    sents = []
    if champ:
        h = next((x for x in lines_t if x["team"] == champ), None)
        sents.append(f"The {ctx.full(champ)} won {ctx.champ_name(season)}" +
                     (f" after a {h['w']}-{h['l']}{'-' + str(h['t']) if h['t'] else ''} regular season." if h else "."))
    sents.append(f"Best regular-season record: {ctx.full(best['team'])}, {best['w']}-{best['l']}"
                 f"{'-' + str(best['t']) if best['t'] else ''}.")
    totals = defaultdict(lambda: defaultdict(float))
    if current:
        from . import stats
        for pid, s in stats.player_totals(league, stats.REGULAR).items():
            totals[pid] = s
    else:
        for r in league.career:
            if r["season"] == season and r["phase"] == "regular":
                for k, v in r["stats"].items():
                    totals[r["pid"]][k] += v
    leaders = []
    for stat, label in (("pass_yds", "passing yards"), ("rush_yds", "rushing yards"), ("rec_yds", "receiving yards"),
                        ("sacks", "sacks"), ("def_int", "interceptions")):
        if not totals:
            break
        pid, s = max(totals.items(), key=lambda kv: kv[1].get(stat, 0))
        p = ctx.player(pid)
        if p and s.get(stat):
            v = s[stat]
            leaders.append(f"{label}: {p.name} ({v:g})" if stat == "sacks" else f"{label}: {p.name} ({int(v):,})")
    if leaders:
        sents.append("League leaders, " + "; ".join(leaders) + ".")
    ctx.add(season, cal, "season", f"{season} in review", " ".join(sents), teams=[champ] if champ else [],
            importance=62, key=f"review-{season}")


def _playoff_field(ctx, season):
    league = ctx.league
    if season == league.season:
        seeds = league.playoff_seeds
        if not seeds:
            return
    else:
        hist = [h for h in league.team_history if h["season"] == season and h.get("seed")]
        seeds = defaultdict(list)
        for h in sorted(hist, key=lambda h: h["seed"]):
            seeds[ctx.teams[h["team"]].conference].append(h["team"])
        if not seeds:
            return
    cal = 5 + ctx.n_weeks + 0.9
    lines = []
    for conf in sorted(seeds):
        lines.append(f"{conf}: " + ", ".join(f"{i}. {ctx.city(t)}" for i, t in enumerate(seeds[conf], start=1)))
    lines.append("The No. 1 seeds have a first-round bye.")
    ctx.add(season, cal, "playoffs", f"The {season} playoff field is set", "\n".join(lines),
            teams=[t for ids in seeds.values() for t in ids], importance=58, key=f"field-{season}")
    for conf in seeds:
        for t in seeds[conf]:
            rng = ctx.rng(season, "fieldfan", t)
            if rng.random() < 0.5:
                seed = seeds[conf].index(t) + 1
                ctx.post(season, cal, ctx.fan(t, rng), Say("fan_field", {"seed": seed, "NICK": ctx.nick(t).upper()}),
                         teams=[t], importance=25)


def _captains(ctx, season):
    league = ctx.league
    if season != league.season or not league.captains:
        return
    for tid, caps in league.captains.items():
        if tid not in ctx.teams:
            continue
        o, d = ctx.player(caps.get("Offense")), ctx.player(caps.get("Defense"))
        if not (o and d):
            continue
        ctx.add(season, 0.5, "season", f"{ctx.full(tid)} captains: {o.last_name} and {d.last_name}",
                f"{ctx.full(tid)} players voted {pos_abbr(o)} {o.name} the offensive captain and {pos_abbr(d)} "
                f"{d.name} the defensive captain for {season}.", teams=[tid], players=[o.id, d.id], importance=14,
                key=f"capt-{season}-{tid}")


def _injury_reports(ctx):
    """This week's game-day injury report (Out / Doubtful / Questionable) for
    each team with a game left, and the key names league-wide."""
    league = ctx.league
    if S.season_over(league):
        return
    season, cal = league.season, S.calendar(league)
    games = S.current_games(league)
    playing = {t for g in games if not g.get("played") for t in (g["home"], g["away"])}
    if not playing:
        return
    order = ["Out", "Concussion protocol", "Doubtful", "Questionable"]
    key = []
    for tid in sorted(playing):
        g = next(x for x in games if tid in (x["home"], x["away"]))
        opp = g["away"] if g["home"] == tid else g["home"]
        by = defaultdict(list)
        for pid, inj in league.injuries.items():
            if inj.get("team") != tid or league.rosters.get(pid) != tid:
                continue
            st = S.injury_status(league, pid)
            if st not in order:
                continue
            p = ctx.player(pid)
            if p is None:
                continue
            by[st].append(p)
            if ctx.notable(p, tid) and st != "Questionable":
                key.append((tid, p, st, inj.get("kind")))
        if not by:
            continue
        parts = []
        for st in order:
            if by[st]:
                parts.append(f"{st}: " + ", ".join(f"{pos_abbr(p)} {p.name} ({injury_short(league.injuries[p.id].get('kind'))})"
                                                  for p in sorted(by[st], key=lambda q: -ctx.caliber(q))) + ".")
        ctx.add(season, cal, "injury", f"{ctx.full(tid)} injury report: {S.week_label(league)} vs {ctx.city(opp)}",
                "\n".join(parts), teams=[tid], players=[p.id for st in order for p in by[st]], importance=18,
                key=f"report-{season}-{cal}-{tid}")
    if key:
        lines = [f"{ctx.teams[tid].abbrev} {pos_abbr(p)} {p.name} ({injury_short(kind)}): {st.lower()}"
                 for tid, p, st, kind in sorted(key, key=lambda x: -ctx.caliber(x[1]))[:12]]
        ctx.add(season, cal, "injury", f"Key players out for {S.week_label(league)}", "\n".join(lines),
                teams=[k[0] for k in key], players=[k[1].id for k in key], importance=34, key=f"keyout-{season}-{cal}")


def _playoff_picture(ctx):
    league = ctx.league
    if not S.in_regular_season(league) or league.week < 11:
        return
    try:
        seeds = po.seeds(league)
    except Exception:
        return
    rec = S.records(league)
    cal = S.calendar(league) - 0.1
    lines = []
    for conf in sorted(seeds):
        ids = seeds[conf]
        lines.append(f"{conf}: " + ", ".join(f"{i}. {ctx.city(t)} ({S.record_text(rec[t])})"
                                             for i, t in enumerate(ids, start=1)))
        hunt = sorted((t for t in ctx.teams.values() if t.conference == conf and t.id not in ids),
                      key=lambda t: -rec[t.id]["pct"])[:3]
        if hunt:
            lines.append("In the hunt: " + ", ".join(f"{ctx.city(t.id)} ({S.record_text(rec[t.id])})" for t in hunt))
    ctx.add(league.season, cal, "playoffs", f"If the season ended today: the playoff picture after Week {league.week - 1}",
            "\n".join(lines), teams=[t for ids in seeds.values() for t in ids], importance=45,
            key=f"picture-{league.season}-{league.week}")


# ---------------------------------------------------------------------------
# Storylines and features: what's building over the season (engine/storylines.py)
# ---------------------------------------------------------------------------

_STREAK_STAT = {"rush100": "rush_yds", "rec100": "rec_yds", "pass300": "pass_yds", "pass2td": "pass_td",
                "sack": "sacks", "int": "def_int"}


def _sum_lines(lines):
    t = defaultdict(float)
    for s in lines:
        for k, v in s.items():
            if k != "team" and isinstance(v, (int, float)):
                t[k] = max(t[k], v) if k.endswith("_long") else t[k] + v
    return t


def _season_line(t, position):
    """'4,012 passing yards, 31 TD passes, 9 INT' for rankings and watches."""
    g = lambda k: t.get(k, 0)
    if position == "QB":
        out = f"{int(g('pass_yds')):,} passing yards, {int(g('pass_td'))} TD passes, {int(g('pass_int'))} INT"
        if g("rush_yds") >= 250:
            out += f", {int(g('rush_yds'))} rushing yards"
        return out
    if position in ("RB", "FB"):
        out = f"{int(g('rush_yds')):,} rushing yards, {int(g('rush_td'))} rushing TDs"
        if g("rec_yds") >= 200:
            out += f", {int(g('rec_yds'))} receiving yards"
        return out
    if position in ("WR", "TE"):
        return f"{int(g('rec'))} catches, {int(g('rec_yds')):,} yards, {int(g('rec_td'))} TDs"
    bits = []
    if g("sacks"):
        bits.append(f"{g('sacks'):g} sacks")
    if g("def_int"):
        bits.append(f"{int(g('def_int'))} INT")
    if g("ff"):
        bits.append(f"{int(g('ff'))} forced fumbles")
    bits.append(f"{int(g('tkl') + g('ast'))} tackles")
    return ", ".join(bits)


def _big_loss(ctx, fo):
    """Is this lost player big enough to keep mentioning (a star, or the quarterback)?"""
    p = ctx.player(fo[0]) if fo else None
    return p is not None and (p.position == "QB" or ctx.caliber(p) >= NOTABLE + 6)


def _in_game(ctx, g, tid, week):
    res, won = _result_phrase(ctx, g, tid)
    return f"in {res} in Week {week}", won


def _features(ctx, season, track):
    if not track.weeks:
        return
    records = _season_records(ctx, season) if season > ctx.first else {}
    done = set()           # once-a-season stories already written: (kind, who)
    slumps = {}            # quarterback -> week of his last slump story
    prev_order = None
    for w in track.weeks:
        if any(not g.get("played") for g in track.schedule if g["week"] == w):
            break          # this week isn't finished yet
        cal = 5 + w + 0.6
        _streak_stories(ctx, season, track, w, cal)
        _comeback_stories(ctx, season, track, w, cal)
        _fallout_stories(ctx, season, track, w, cal)
        _breakout_stories(ctx, season, track, w, cal, done)
        _slump_stories(ctx, season, track, w, cal, slumps)
        _team_turn_stories(ctx, season, track, w, cal, done)
        if w in (8, 11, 14) and w <= ctx.n_weeks - 3:
            _pace_stories(ctx, season, track, w, cal, records)
        if w >= 12 and w % 2 == 0 and w < ctx.n_weeks:
            _division_races(ctx, season, track, w, cal)
        if w in (10, 13, 16) and w < ctx.n_weeks:
            _draft_race(ctx, season, track, w, cal)
        from . import bitter
        bitter.react_week(ctx, season, track, w, track.schedule)
        if w >= 2:
            prev_order = _power_rankings(ctx, season, track, w, cal + 0.1, prev_order)
            bitter.react_rankings(ctx, season, cal + 0.1, prev_order[0], ctx.rng(season, "rexrank", w),
                                  rec=SL.rec_text(track.record(prev_order[0], w)))
        elif w == 1:
            prev_order = SL.rank_order(track, 1)
        if w < ctx.n_weeks:
            _preview(ctx, season, track, w, cal + 0.2)
        # (The MVP race comes from the league's awards: engine/news_awards.py.)
        if w in (5, 8, 11, 14, 17) and w < ctx.n_weeks + 1:
            _watch(ctx, season, track, w, cal + 0.15, rookies=True)


def _streak_stories(ctx, season, track, w, cal):
    W_ = ctx.writer
    for pid, gl in track.player_games.items():
        if gl[-1][0] < w or not any(x[0] == w for x in gl):
            continue
        hits = [s for s in track.streaks_for(pid, w) if s[1] == s[4] or (s[1] > s[4] and (s[1] - s[4]) % 2 == 0)]
        if not hits:
            continue
        key, n, one, many, at = max(hits, key=lambda s: s[1] - s[4])
        p = ctx.player(pid)
        if p is None:
            continue
        _w, g, tid, line = next(x for x in gl if x[0] == w)
        rng = ctx.rng(season, "streak", pid, w)
        in_game, won = _in_game(ctx, g, tid, w)
        t = track.totals(pid, w)
        stat = _STREAK_STAT.get(key)
        amount = season_amount(stat, t.get(stat, 0)) if stat else plural(t.get("rush_td", 0) + t.get("rec_td", 0),
                                                                            "touchdown")
        gp = len(track.games_of(pid, w))
        f = {"last": ctx.short(p, tid), "name": p.name, "Tc": ctx.city(tid), "Tc_poss": possessive(ctx.city(tid)),
             "T": ctx.full(tid), "pos_word": POS_WORD[p.position], "streak_n": num(n), "streak_ord": ordinal(n),
             "streak_what": one, "streak_whats": many, "in_game": in_game, "in_game_cap": in_game[:1].upper() + in_game[1:],
             "does": game_phrase(line, rng), "season_amount": amount, "gp_t": plural(gp, "game"),
             "abbr": ctx.teams[tid].abbrev}
        body = " ".join(x for x in (W_.say("streak_body", rng, f), W_.say("streak_season", rng, f)) if x)
        imp = min(55, 36 + 3 * (n - at)) + (6 if ctx.caliber(p) >= STAR else 0)
        ctx.add(season, cal, "storyline", W_.say("streak_head", rng, f), body, teams=[tid], players=[pid],
                importance=imp, key=f"streak-{season}-{pid}-{key}-{n}")
        ctx.post(season, cal, ctx.stat_desk(), Say("stat_streak", f), teams=[tid], players=[pid],
                 importance=imp - 6)
        if rng.random() < 0.35:
            ctx.post(season, cal, ctx.player_voice(p), Say("player_streak", f), teams=[tid], players=[pid],
                     importance=imp - 16)


def _comeback_stories(ctx, season, track, w, cal):
    W_ = ctx.writer
    for pid, tid, kind, missed, line, g in track.comebacks(w):
        p = ctx.player(pid)
        rng = ctx.rng(season, "comeback", pid, w)
        in_game, won = _in_game(ctx, g, tid, w)
        part = injury_short(kind)
        f = {"last": ctx.short(p, tid), "name": p.name, "Tc": ctx.city(tid), "Tc_poss": possessive(ctx.city(tid)),
             "pos_word": POS_WORD[p.position], "cp_what": injury_phrase(kind),
             "cp_short": part if part in ("concussion", "injury") else f"{part} injury", "out_t": plural(missed, "game"),
             "in_game": in_game, "in_game_cap": in_game[:1].upper() + in_game[1:],
             "does": game_phrase(line, rng), "Tc_": ctx.city(tid)}
        star = ctx.caliber(p) >= STAR
        ctx.add(season, cal, "storyline", W_.say("comeback_head", rng, f),
                W_.say("comeback_body" if f["does"] else "comeback_body_plain", rng, f),
                teams=[tid], players=[pid], importance=30 + 12 * star + min(10, missed),
                key=f"comeback-{season}-{pid}-{w}")
        if rng.random() < 0.6:
            ctx.post(season, cal, ctx.player_voice(p), Say("player_comeback", f), teams=[tid], players=[pid],
                     importance=26 + 10 * star)


def _fallout_stories(ctx, season, track, w, cal):
    W_ = ctx.writer
    for tid in ctx.teams:
        lg = track.last_game(tid, w)
        if not lg or lg[0] != w:
            continue
        fo = track.fallout(tid, w)
        if not fo or sum(fo[4]) not in (3, 6):
            continue
        pid, iw, kind, rb, rs, pb, ps = fo
        p = ctx.player(pid)
        rng = ctx.rng(season, "fallout", tid, w)
        ppg_b = pb[0] / pb[2] if pb[2] else 0
        ppg_a = ps[0] / ps[2] if ps[2] else 0
        f = {"Tc": ctx.city(tid), "T": ctx.full(tid), "pos_word": POS_WORD[p.position], "inj_player": p.name,
             "inj_last": ctx.short(p, tid), "inj_what": injury_phrase(kind), "inj_week": iw,
             "since_rec": SL.rec_text(rs), "before_rec": SL.rec_text(rb), "ppg_before": f"{ppg_b:.1f}",
             "ppg_after": f"{ppg_a:.1f}", "good": SL.pct(rs) >= 0.6, "bad": SL.pct(rs) <= 0.34}
        sents = [W_.say("fallout_body", rng, f)]
        if pb[2] and ppg_b - ppg_a >= 4:
            sents.append(W_.say("fallout_scoring", rng, f))
        elif pb[2] and ppg_a - ppg_b >= 4:
            sents.append(W_.say("fallout_scoring_up", rng, f))
        ctx.add(season, cal, "storyline", W_.say("fallout_head", rng, f), " ".join(sents), teams=[tid],
                players=[pid], importance=(38 if _big_loss(ctx, fo) and (f["good"] or f["bad"]) else 20)
                + (8 if p.position == "QB" else 0),
                key=f"fallout-{season}-{tid}-{pid}-{sum(rs)}")


def _breakout_stories(ctx, season, track, w, cal, done):
    if w < 4:
        return
    W_ = ctx.writer
    for pid, gl in track.player_games.items():
        gl = [x for x in gl if x[0] <= w]          # only what was known after week w
        if not gl or gl[-1][0] != w or ("breakout", pid) in done or len(gl) < 3:
            continue
        p = ctx.player(pid)
        if p is None or p.position in ("K", "P", "LS") or ctx.caliber(p) >= STAR:
            continue
        pro_year = season - p.draft_year + 1
        if not (p.draft_round == 0 or p.draft_round >= 4 or pro_year <= 2):
            continue
        last3 = gl[-3:]
        imps = [total_impact(x[3]) for x in last3]
        if min(imps) < 11 or sum(imps) < 48:
            continue
        done.add(("breakout", pid))
        tid = last3[-1][2]
        rng = ctx.rng(season, "breakout", pid)
        origin = ("an undrafted free agent" if p.draft_round == 0 else
                  f"{article(ordinal(p.draft_round))} {ordinal(p.draft_round)}-round pick in {p.draft_year}")
        if pro_year == 1:
            origin = ("an undrafted free agent this year" if p.draft_round == 0 else
                      f"{article(ordinal(p.draft_round))} {ordinal(p.draft_round)}-round pick this year")
        f = {"last": ctx.short(p, tid), "name": p.name, "Tc": ctx.city(tid), "Tc_poss": possessive(ctx.city(tid)),
             "T": ctx.full(tid), "origin": origin, "late_pick": p.draft_round == 0 or p.draft_round >= 4,
             "recent_got": game_noun(_sum_lines(x[3] for x in last3), rng)}
        t = track.totals(pid, w)
        body = [W_.say("breakout_body", rng, f), W_.say("breakout_recent", rng, f)]
        main = max(impact(t).items(), key=lambda kv: kv[1], default=(None, 0))[0]
        stat = {"pass": "pass_yds", "rush": "rush_yds", "rec": "rec_yds", "def": "sacks"}.get(main)
        if stat and t.get(stat):
            body.append(f"For the season: {season_amount(stat, t[stat])} in {plural(len(track.games_of(pid, w)), 'game')}.")
        ctx.add(season, cal, "storyline", W_.say("breakout_head", rng, f), " ".join(body), teams=[tid],
                players=[pid], importance=45, key=f"breakout-{season}-{pid}")
        who = ctx.fan(tid, rng)
        bid = ctx.post(season, cal, who, Say("fan_breakout", f), teams=[tid], players=[pid], importance=28)
        from . import bitter
        bitter.remember(ctx, "fan_believe", season, w, who, bid, pid_=pid, team=tid)


def _slump_stories(ctx, season, track, w, cal, slumps):
    W_ = ctx.writer
    for pid, gl in track.player_games.items():
        gl = [x for x in gl if x[0] <= w]          # only what was known after week w
        if not gl or gl[-1][0] != w:
            continue
        p = ctx.player(pid)
        if p is None or p.position != "QB" or w - slumps.get(pid, -99) < 4:
            continue
        r = track.qb_recent(pid, w)
        if not r or r["att"] < 70 or r["rating"] >= 62:
            continue
        slumps[pid] = w
        tid = gl[-1][2]
        res = []
        for _w, g, t, _s in r["games"]:
            pf, pa = (g["home_score"], g["away_score"]) if g["home"] == t else (g["away_score"], g["home_score"])
            res.append("W" if pf > pa else "L" if pf < pa else "T")
        rng = ctx.rng(season, "slump", pid, w)
        f = {"name": p.name, "last": ctx.short(p, tid), "Tc": ctx.city(tid), "Tn": ctx.nick(tid),
             "rating": f"{r['rating']:.1f}", "pct": round(100 * r["cmp"] / r["att"]) if r["att"] else 0,
             "tds_t": "no touchdown passes" if not r["td"] else plural(r["td"], "touchdown pass", "touchdown passes"),
             "ints_t": plural(r["int"], "interception"), "last3_rec": SL.rec_text(SL.rec_of(res))}
        ctx.add(season, cal, "storyline", W_.say("slump_head", rng, f),
                W_.say("slump_body", rng, f) + " " + W_.say("slump_team", rng, f), teams=[tid], players=[pid],
                importance=40 + (8 if ctx.notable(p, tid) else 0), key=f"slump-{season}-{pid}-{w}")
        if rng.random() < 0.6:
            who = ctx.fan(tid, rng)
            bid = ctx.post(season, cal, who, Say("fan_slump", f), teams=[tid], players=[pid], importance=24)
            from . import bitter
            bitter.remember(ctx, "fan_bench", season, w, who, bid, pid_=pid, team=tid)


def _team_turn_stories(ctx, season, track, w, cal, done):
    W_ = ctx.writer
    for tid in ctx.teams:
        lg = track.last_game(tid, w)
        if not lg or lg[0] != w:
            continue
        res = track.results(tid, w)
        kind, n = track.streak_of(tid, w)
        if n < 3:
            continue
        start = res[:-n]
        if len(start) < 3:
            continue
        sr, now = SL.rec_of(start), SL.rec_of(res)
        story = None
        if kind == "W" and SL.pct(sr) <= 0.25 and SL.pct(now) >= 0.5 and ("turn", tid) not in done:
            story = ("turnaround", "fan_turnaround")
        elif kind == "L" and SL.pct(sr) >= 0.75 and len(start) >= 4 and n >= 3 and ("collapse", tid) not in done:
            story = ("collapse", "fan_collapse")
        if not story:
            continue
        done.add(("turn" if story[0] == "turnaround" else "collapse", tid))
        rng = ctx.rng(season, story[0], tid, w)
        f = {"Tc": ctx.city(tid), "T": ctx.full(tid), "Tn": ctx.nick(tid), "start_rec": SL.rec_text(sr),
             "rec": SL.rec_text(now), "n_t": num(n)}
        ctx.add(season, cal, "storyline", W_.say(f"{story[0]}_head", rng, f), W_.say(f"{story[0]}_body", rng, f),
                teams=[tid], importance=45, key=f"{story[0]}-{season}-{tid}")
        ctx.post(season, cal, ctx.fan(tid, rng), Say(story[1], f), teams=[tid], importance=26)


def _pace_stories(ctx, season, track, w, cal, records):
    W_ = ctx.writer
    games = ctx.n_weeks - 1
    for pid, gl in track.player_games.items():
        if not gl or gl[0][0] > w:
            continue
        p = ctx.player(pid)
        if p is None:
            continue
        tid = [x for x in gl if x[0] <= w][-1][2]
        tg = len(track.results(tid, w))
        if not tg:
            continue
        t = track.totals(pid, w)
        for stat, mark in SL.PACE_MARKS.items():
            pace = t.get(stat, 0) / tg * games
            if pace < mark:
                continue
            rec = records.get(stat)
            rng = ctx.rng(season, "pace", pid, stat, w)
            f = {"last": ctx.short(p, tid), "name": p.name, "T": ctx.full(tid), "Tc": ctx.city(tid),
                 "pos_word": POS_WORD[p.position], "pace_mark": f"{mark:,}", "stat_words": STAT_WORDS[stat],
                 "pace_val": f"{pace:.1f}" if stat == "sacks" else f"{int(round(pace)):,}", "week": w, "games": games,
                 "season_amount": season_amount(stat, t.get(stat, 0)), "record_pace": bool(rec and pace > rec[0])}
            body = [W_.say("pace_body", rng, f)]
            if rec:
                hp = ctx.player(rec[1])
                f.update(rec_val=f"{rec[0]:g}" if stat == "sacks" else f"{int(rec[0]):,}",
                         rec_holder=hp.name if hp else "a former player", rec_season=rec[2])
                body.append(W_.say("pace_record", rng, f))
            ctx.add(season, cal, "milestone", W_.say("pace_head", rng, f), " ".join(body), teams=[tid],
                    players=[pid], importance=50 + (10 if f["record_pace"] else 0), key=f"pace-{season}-{pid}-{stat}-{w}")


def _division_races(ctx, season, track, w, cal):
    W_ = ctx.writer
    for (conf, div), rows in track.division_table(w).items():
        (t1, r1, _d1), (t2, r2, _d2) = rows[0], rows[1]
        gap = ((r1[0] - r2[0]) + (r2[1] - r1[1])) / 2
        if gap > 1:
            continue
        rng = ctx.rng(season, "race", div, w)
        parts = [f"{ctx.city(t1)} is {SL.rec_text(r1)}."]
        for t, r, _d in rows[1:]:
            back = ((r1[0] - r[0]) + (r[1] - r1[1])) / 2
            if back > 2:
                break
            parts.append(f"{ctx.city(t)} is {SL.rec_text(r)}" + (f", {_gb_text(back)} back." if back else "."))
        left = track.games_left(t1, w)
        f = {"div": div, "lead_team": ctx.city(t1), "chase_team": ctx.city(t2), "gap": _gb_text(gap) if gap else "",
             "tied": gap == 0, "rec": SL.rec_text(r1), "lines": " ".join(parts),
             "games_left_t": f"{ctx.city(t1)} has {plural(left, 'game')}"}
        ctx.add(season, cal, "playoffs", W_.say("race_head", rng, f), W_.say("race_body", rng, f),
                teams=[x[0] for x in rows], importance=48, key=f"race-{season}-{div}-{w}")


def _draft_race(ctx, season, track, w, cal):
    W_ = ctx.writer
    rows = []
    for tid in ctx.teams:
        r = track.record(tid, w)
        pf, pa, _n = track.points(tid, w)
        rows.append((SL.pct(r), pf - pa, tid, r))
    rows.sort()
    bottom = rows[:5]
    rng = ctx.rng(season, "draftrace", w)
    f = {"worst_team": ctx.city(bottom[0][2]), "week": w,
         "lines": ", ".join(f"{ctx.city(t)} ({SL.rec_text(r)})" for _p, _d, t, r in bottom)}
    ctx.add(season, cal, "draft", W_.say("pick_head", rng, f), W_.say("pick_body", rng, f),
            teams=[x[2] for x in bottom], importance=35, key=f"draftrace-{season}-{w}")


def _rank_blurb(ctx, track, tid, w, rng):
    bits = []
    lg = track.last_game(tid, w)
    if lg and lg[0] == w:
        _w, g, opp, pf, pa, _i = lg
        oc = ctx.city(opp)
        last = (f"Beat {oc} {pf}-{pa}." if pf > pa else f"Lost to {oc} {pa}-{pf}." if pf < pa else
                f"Tied {oc} {pf}-{pa}.")
    else:
        last = f"Had a bye in Week {w}."
    r = track.record(tid, w)
    kind, n = track.streak_of(tid, w)
    extra = []
    if r[1] == 0 and r[2] == 0 and r[0] >= 3:
        extra.append("Still unbeaten.")
    elif r[0] == 0 and r[2] == 0 and r[1] >= 3:
        extra.append("Still looking for a first win.")
    elif n >= 3:
        extra.append(f"{'Won' if kind == 'W' else 'Lost'} {num(n)} straight.")
    fo = track.fallout(tid, w)
    if fo and sum(fo[4]) >= 2 and _big_loss(ctx, fo):
        p = ctx.player(fo[0])
        extra.append(f"{SL.rec_text(fo[4])} since losing {pos_abbr(p)} {p.last_name}.")
    best = None
    for pid, gl in track.player_games.items():
        lw = next((x for x in reversed(gl) if x[0] <= w), None)     # his latest game as of week w
        if lw and lw[0] == w and lw[2] == tid:
            for s in track.streaks_for(pid, w):
                if s[1] >= 3 and (best is None or s[1] > best[1][1]):
                    best = (pid, s)
    if best:
        extra.append(f"{ctx.player(best[0]).last_name}: {num(best[1][1])} straight {best[1][3]}.")
    if extra:
        bits = [last, extra[0]] if rng.random() < 0.5 else [extra[0], last]
        if len(extra) > 1 and rng.random() < 0.4:
            bits.append(extra[1])
    else:
        bits = [last]
    return " ".join(bits)


def _power_rankings(ctx, season, track, w, cal, prev):
    W_ = ctx.writer
    order = SL.rank_order(track, w)
    rng = ctx.rng(season, "rank", w)
    moves = {}
    if prev:
        for i, tid in enumerate(order):
            moves[tid] = prev.index(tid) - i
    lines = []
    for i, tid in enumerate(order, start=1):
        mv = moves.get(tid)
        mtxt = "" if mv is None else (f", up {mv}" if mv > 0 else f", down {-mv}" if mv < 0 else ", no change")
        lines.append(f"{i}. {ctx.city(tid)} ({SL.rec_text(track.record(tid, w))}{mtxt}): "
                     f"{_rank_blurb(ctx, track, tid, w, rng)}")
    riser = max(moves, key=lambda t: moves[t], default=None)
    faller = min(moves, key=lambda t: moves[t], default=None)
    f = {"week": w, "top": ctx.city(order[0]),
         "mover": ctx.city(riser) if riser is not None and moves[riser] >= 4 else "",
         "same_top": bool(prev) and prev[0] == order[0], "new_top": bool(prev) and prev[0] != order[0]}
    ctx.add(season, cal, "rankings", W_.say("rank_head", rng, f),
            W_.say("rank_intro", rng, f) + "\n" + "\n".join(lines), teams=list(order), importance=50,
            key=f"rank-{season}-{w}")
    # Fans react.
    rk = lambda tid: {"rank": order.index(tid) + 1, "rec": SL.rec_text(track.record(tid, w)),
                      "jump": num(abs(moves.get(tid, 0))), "same_top": f["same_top"]}
    frng = ctx.rng(season, "rankfans", w)
    ctx.post(season, cal, ctx.fan(order[0], frng), Say("fan_rank_top", rk(order[0])), teams=[order[0]], importance=30)
    if riser is not None and moves[riser] >= 3:
        ctx.post(season, cal, ctx.fan(riser, frng), Say("fan_rank_up", rk(riser)), teams=[riser], importance=24)
    if faller is not None and moves[faller] <= -3:
        ctx.post(season, cal, ctx.fan(faller, frng), Say("fan_rank_down", rk(faller)), teams=[faller], importance=24)
    return order


def _preview(ctx, season, track, w, cal):
    W_ = ctx.writer
    nxt = [g for g in track.schedule if g["week"] == w + 1]
    if not nxt:
        return
    table = track.division_table(w)
    rng = ctx.rng(season, "preview", w)
    scored = []
    for g in nxt:
        a, h = g["away"], g["home"]
        ra, rh = track.record(a, w), track.record(h, w)
        ta, th = ctx.teams[a], ctx.teams[h]
        same_div = (ta.conference, ta.division) == (th.conference, th.division)
        angles = []
        score = 40 * (SL.pct(ra) + SL.pct(rh)) + (12 if same_div else 0)
        if same_div and w >= 8:
            rows = table[(ta.conference, ta.division)]
            top2 = {rows[0][0], rows[1][0]}
            gap = ((rows[0][1][0] - rows[1][1][0]) + (rows[1][1][1] - rows[0][1][1])) / 2
            if {a, h} == top2 and gap <= 1:
                angles.append(f"First place in the {ta.division} is on the line.")
                score += 25
        for t, r in ((a, ra), (h, rh)):
            if r[1] == 0 and r[2] == 0 and r[0] >= 4:
                angles.append(f"{ctx.city(t)} is unbeaten.")
                score += 10
        prev = track.meetings(a, h, w + 1)
        if prev:
            pw, _pg, _opp, pf, pa, _i = prev[-1]
            winner = a if pf > pa else h
            angles.append(f"{ctx.city(winner)} won the first meeting {max(pf, pa)}-{min(pf, pa)} in Week {pw}.")
            score += 5
        for t in (a, h):
            kind, n = track.streak_of(t, w)
            if n >= 3:
                angles.append(f"{ctx.city(t)} has {'won' if kind == 'W' else 'lost'} {num(n)} straight.")
                score += 4
        for t in (a, h):
            for pid, gl in track.player_games.items():
                if gl[-1][0] == w and gl[-1][2] == t:
                    for s in track.streaks_for(pid, w):
                        if s[1] >= 3:
                            angles.append(f"{ctx.player(pid).name} brings {num(s[1])} straight {s[3]}.")
                            score += 3
                            break
        for t in (a, h):
            fo = track.fallout(t, w)
            if fo and sum(fo[4]) >= 2 and _big_loss(ctx, fo):
                angles.append(f"{ctx.city(t)} is {SL.rec_text(fo[4])} since losing {ctx.player(fo[0]).name}.")
        rng.shuffle(angles[1:]) if len(angles) > 2 else None
        scored.append((score, g, ra, rh, angles))
    scored.sort(key=lambda x: -x[0])
    top = scored[:3]
    lines = []
    for _s, g, ra, rh, angles in top:
        lines.append(f"{ctx.city(g['away'])} ({SL.rec_text(ra)}) at {ctx.city(g['home'])} ({SL.rec_text(rh)}). "
                     + " ".join(angles[:2]))
    f = {"week": w + 1, "top_game": f"{ctx.city(top[0][1]['away'])} at {ctx.city(top[0][1]['home'])}"}
    ctx.add(season, cal, "rankings", W_.say("preview_head", rng, f), "\n".join(x.strip() for x in lines),
            teams=[t for x in top for t in (x[1]["home"], x[1]["away"])], importance=42,
            key=f"preview-{season}-{w + 1}")


def _watch(ctx, season, track, w, cal, rookies):
    W_ = ctx.writer
    cands = []
    for pid, gl in track.player_games.items():
        gl = [x for x in gl if x[0] <= w]
        if not gl:
            continue
        p = ctx.player(pid)
        if p is None or p.position in ("K", "P", "LS"):
            continue
        if rookies and p.draft_year != season:
            continue
        if not rookies and len(gl) < 0.6 * len(track.results(gl[-1][2], w)):
            continue
        tid = gl[-1][2]
        t = track.totals(pid, w)
        score = total_impact(t) * (1.0 if rookies else 0.55 + SL.pct(track.record(tid, w)))
        cands.append((score, pid, tid, t))
    cands.sort(key=lambda x: -x[0])
    top = cands[:5]
    if not top:
        return
    rng = ctx.rng(season, "watch", rookies, w)
    lines = []
    for i, (_s, pid, tid, t) in enumerate(top, start=1):
        p = ctx.player(pid)
        draft = (" (undrafted)" if p.draft_round == 0 else f" (Round {p.draft_round})") if rookies else ""
        lines.append(f"{i}. {p.name}, {pos_abbr(p)}, {ctx.city(tid)} ({SL.rec_text(track.record(tid, w))}){draft}: "
                     f"{_season_line(t, p.position)}.")
    lead = ctx.player(top[0][1])
    f = {"week": w, "top": lead.name}
    kind = "rookie" if rookies else "mvp"
    ctx.add(season, cal, "rankings", W_.say(f"{kind}_head", rng, f),
            W_.say(f"{kind}_intro", rng, f) + "\n" + "\n".join(lines), teams=[x[2] for x in top],
            players=[x[1] for x in top], importance=40 if rookies else 50, key=f"{kind}-{season}-{w}")
    if not rookies:
        ctx.post(season, cal, ctx.fan(top[0][2], rng), Say("fan_mvp", {
            "last": lead.last_name, "line": _season_line(top[0][3], lead.position)}),
            teams=[top[0][2]], players=[lead.id], importance=26)


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

_cache = {}


def _cache_key(league, past_games):
    played = sum(1 for g in S.all_games(league) if g.get("played"))
    aw = getattr(league, "awards", None) or {}
    return (id(league), league.season, league.stage, S.calendar(league), played, len(league.transactions),
            len(league.injury_history), len(league.draft_history), len(league.career),
            len(past_games or ()), tuple(sorted({r["season"] for r in past_games or ()})), len(league.boxes),
            league.user_team_id, tuple(len(v) for v in aw.values()))


def build(league, past_games=None):
    """Every story and post the league's records support:
    {"items": [...], "posts": [...]}, newest first (within a week, the most
    important first). past_games: earlier seasons' games from the save's
    history file (database.read_history), for their game stories; without
    them, earlier seasons still get their draft, retirements, injuries,
    moves, playoff field and season review."""
    key = _cache_key(league, past_games)
    if key in _cache:
        return _cache[key]
    ctx = _Ctx(league)
    seasons = sorted({ctx.first, league.season} | {h["season"] for h in league.team_history}
                     | {d["season"] for d in league.draft_history} | {r["season"] for r in (past_games or ())})
    for season in seasons:
        ctx.writer.new_season(season)
        start = len(ctx.posts)
        games = _season_games(ctx, season, past_games)
        recs = _records_by_week(ctx, games)
        track = SL.SeasonTrack(ctx, season, games)
        from .news_awards import awards_news   # awards and the Pro Bowl (Oct 23)
        from .news_money import money_news     # the cap, TV and labor deals (Oct 24)
        sections = [lambda: [_game_story(ctx, season, phase, g, box, recs, track)
                             for phase, g, box in games if g.get("played") and box],
                    lambda: _performances_and_milestones(ctx, season, games, recs, track),
                    lambda: _features(ctx, season, track), lambda: _injuries(ctx, season, games),
                    lambda: _moves(ctx, season), lambda: _draft(ctx, season), lambda: _retirements(ctx, season),
                    lambda: _playoff_field(ctx, season), lambda: _season_summary(ctx, season, games),
                    lambda: _captains(ctx, season), lambda: awards_news(ctx, season), lambda: money_news(ctx, season),
                    lambda: ctx.finish_posts(start)]   # Bitter's bits, worded in calendar order (Oct 24)
        for section in sections:
            # Each kind of news keeps its own memory of recent wording, so a story
            # written for Week 3 reads the same after Week 9 is played.
            ctx.writer.recent.clear()
            section()
    _injury_reports(ctx)
    _playoff_picture(ctx)
    order = lambda x: (-x["season"], -x["cal"], -x["importance"])
    out = {"items": sorted(ctx.items, key=order), "posts": sorted(ctx.posts, key=order),
           "errors": list(ctx.writer.errors)}      # wording that couldn't be filled in (tools/news_check.py)
    _cache.clear()
    _cache[key] = out
    return out


def _matches(x, team_id, player_id, kinds, season, min_importance):
    if season is not None and x["season"] != season:
        return False
    if team_id is not None and team_id not in x["teams"]:
        return False
    if player_id is not None and player_id not in x["players"]:
        return False
    if kinds is not None and x.get("kind") not in kinds:
        return False
    return x["importance"] >= min_importance


def stories(league, team_id=None, player_id=None, kinds=None, season=None, min_importance=None, past_games=None):
    """News stories, newest first. With no team or player, only stories at
    least LEAGUE_VIEW_MIN important (the league-wide view)."""
    if min_importance is None:
        min_importance = LEAGUE_VIEW_MIN if team_id is None and player_id is None else 0
    return [x for x in build(league, past_games)["items"]
            if _matches(x, team_id, player_id, kinds, season, min_importance)]


def posts(league, team_id=None, player_id=None, season=None, min_importance=None, past_games=None):
    """Social media posts, newest first (same filters as stories)."""
    if min_importance is None:
        min_importance = POST_LEAGUE_VIEW_MIN if team_id is None and player_id is None else 0
    return [x for x in build(league, past_games)["posts"]
            if _matches(x, team_id, player_id, None, season, min_importance)]


def seasons(league, past_games=None):
    """Seasons that have news, newest first."""
    return sorted({x["season"] for x in build(league, past_games)["items"]}, reverse=True)


def news_players(league, past_games=None):
    """{player id: number of stories}, for the 'a player' filter."""
    out = defaultdict(int)
    for x in build(league, past_games)["items"]:
        for pid in x["players"]:
            out[pid] += 1
    return dict(out)
