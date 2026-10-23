# news_page.py
# Bitter, the league's social media site (the News tab). One page: the
# timeline of bits in the middle, which kinds of accounts to show on the left,
# what's trending and who to follow on the right. No pop-up windows.
#
# News outlets post every story as a bit with an article card: click "Read the
# full story" to open it in place. Click a player's name to open his player
# card; a game recap has a "Game summary" button for its box score (this
# season's games). Everything comes from engine/bitter.py and engine/news.py,
# built from what the league already records.

import re
from html import escape

from nicegui import ui

from engine import bitter
from engine import news
from engine import saves
from engine import transactions
from engine.database import read_history
from .state import state

PAGE = 40            # bits shown at a time ("Show more" adds this many)
REPLIES_SHOWN = 2    # replies shown under a bit before "Show more replies"

SCOPES = {"league": "For you", "mine": "Your team", "team": "A team", "player": "A player"}
KIND_COLORS = {"game": "#2F6690", "performance": "#B8860B", "milestone": "#6B5B95", "injury": "#A3321F",
               "moves": "#4A5A66", "playoffs": "#1F4A35", "draft": "#8A5A2B", "retirement": "#5B6670",
               "season": "#2E8B57", "awards": "#9C7A1C", "storyline": "#B5523B", "rankings": "#3B6E8F",
               "business": "#55606E", "front_office": "#3E4E7A"}

CSS = """
<style>
  .bitter-logo { display: flex; align-items: center; gap: 8px; font-family: 'Barlow Condensed', sans-serif;
                 font-weight: 800; font-size: 30px; color: #1F4A35; letter-spacing: 0.5px; }
  .bitter-logo .mark { width: 34px; height: 34px; border-radius: 50%; background: #1F4A35; color: #F5C518;
                       display: flex; align-items: center; justify-content: center; font-size: 22px; }
  .bit { background: #fff; border: 1px solid #E1E5E0; border-radius: 10px; padding: 12px 14px 8px;
         margin-bottom: 10px; display: grid; grid-template-columns: 46px 1fr; gap: 10px; }
  .bit.mine { box-shadow: inset 4px 0 0 #F5C518; }
  .bit .av { width: 42px; height: 42px; border-radius: 50%; color: #fff; display: flex; align-items: center;
             justify-content: center; font-weight: 700; font-size: 15px; }
  .bit .who { font-weight: 700; font-size: 15px; color: #18222B; }
  .bit .check { display: inline-flex; width: 15px; height: 15px; border-radius: 50%; background: #D4A017;
                color: #fff; font-size: 11px; align-items: center; justify-content: center; margin-left: 3px;
                vertical-align: 1px; }
  .bit .handle, .bit .when { color: #66717A; font-size: 13.5px; }
  .bit .role { color: #66717A; font-size: 12px; }
  .bit .text { font-size: 15px; line-height: 1.42; margin: 3px 0 6px; white-space: pre-line; color: #18222B; }
  .bit .tag { color: #2F6690; }
  .bit .mention { color: #2F6690; }
  .bit .card { border: 1px solid #E1E5E0; border-radius: 10px; padding: 9px 12px; margin: 4px 0 6px; background: #FAFBF9; }
  .bit .card .kind { color: #fff; font-family: 'Barlow Condensed', sans-serif; font-weight: 600; font-size: 12.5px;
                     padding: 0 7px; border-radius: 3px; }
  .bit .card .head { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 19px; line-height: 1.15;
                     margin: 4px 0 2px; }
  .bit .card details summary { cursor: pointer; color: #2F6690; font-size: 13.5px; margin-top: 3px; }
  .bit .card .body { font-size: 14.5px; line-height: 1.45; white-space: pre-line; margin-top: 6px; }
  .bit .quote { border: 1px solid #E1E5E0; border-radius: 10px; padding: 8px 12px; margin: 4px 0 6px; }
  .bit .quote .qwho { font-weight: 700; font-size: 13.5px; }
  .bit .quote .qtext { font-size: 14px; margin-top: 2px; }
  .bit .stats { display: flex; gap: 26px; color: #66717A; font-size: 13px; margin-top: 2px; }
  .bit .stats .material-icons { font-size: 16px; vertical-align: -3px; margin-right: 4px; }
  .bit .replies { border-top: 1px solid #EEF1EC; margin-top: 8px; padding-top: 6px; }
  .bit .reply { display: grid; grid-template-columns: 34px 1fr; gap: 8px; padding: 6px 0; }
  .bit .reply .av { width: 30px; height: 30px; font-size: 12px; }
  .bit .reply .text { font-size: 14px; margin: 1px 0 2px; }
  .bit .replies details summary { cursor: pointer; color: #2F6690; font-size: 13.5px; padding: 4px 0; }
  .side-box { background: #fff; border: 1px solid #E1E5E0; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; }
  .side-box .title { font-family: 'Barlow Condensed', sans-serif; font-weight: 800; font-size: 21px; margin-bottom: 6px; }
  .trend { padding: 6px 0; border-bottom: 1px solid #F0F2EE; }
  .trend:last-child { border-bottom: none; }
  .trend .label { font-weight: 700; font-size: 15px; }
  .trend .meta { color: #66717A; font-size: 12.5px; }
  .follow { padding: 7px 0; display: grid; grid-template-columns: 38px 1fr; gap: 8px; }
  .follow .av { width: 34px; height: 34px; border-radius: 50%; color: #fff; display: flex; align-items: center;
                justify-content: center; font-weight: 700; font-size: 13px; }
  .bitter-side .q-checkbox__label { font-size: 14.5px; }
</style>
"""


def _player_list(league, ids):
    out = []
    for pid in ids:
        try:
            out.append(league.player(pid))
        except (KeyError, ValueError):
            pass
    return out


def _format(text, players):
    """Escaped text: player names link to their cards, #hashtags and @handles in color."""
    out = escape(text, quote=False)
    for p in sorted(players, key=lambda p: -len(p.name)):
        name = escape(p.name, quote=False)
        if name in out:
            out = out.replace(name, f"\x00{p.id}\x01", 1)
    out = re.sub(r"(?<![&\w])(#[A-Za-z]\w*)", r'<span class="tag">\1</span>', out)
    out = re.sub(r"(?<![\w&])(@\w+)", r'<span class="mention">\1</span>', out)
    by_id = {p.id: p for p in players}
    return re.sub(r"\x00(\d+)\x01", lambda m: f'<a class="plink" href="/player/{m.group(1)}">'
                                              f'{escape(by_id[int(m.group(1))].name)}</a>', out)


def _avatar(b, size_class=""):
    return (f'<div class="av {size_class}" style="background:{bitter.avatar_color(b["handle"])}">'
            f'{escape(bitter.initials(b["name"]))}</div>')


def _header(b):
    check = '<span class="check" title="Bitter Gold: a verified account">✔</span>' if bitter.verified(b) else ""
    return (f'<span class="who">{escape(b["name"])}</span>{check} <span class="handle">{escape(b["handle"])}</span>'
            f' <span class="when">· {b["season"]} {escape(b["when"])}</span>'
            f'<div class="role">{escape(b["role"])}</div>')


def _bit_html(league, b, mine):
    players = _player_list(league, b["players"])
    parts = [f'<div class="bit{" mine" if mine else ""}">{_avatar(b)}<div>{_header(b)}']
    parts.append(f'<div class="text">{_format(b["text"], players)}</div>')
    q = b.get("quote")
    if q:
        parts.append(f'<div class="quote"><span class="qwho">{escape(q["name"])}</span> '
                     f'<span class="handle">{escape(q["handle"])} · {escape(q["when"])}</span>'
                     f'<div class="qtext">{escape(q["text"])}</div></div>')
    art = b.get("article")
    if art:
        color = KIND_COLORS.get(art["kind"], "#5B6670")
        parts.append(f'<div class="card"><span class="kind" style="background:{color}">'
                     f'{escape(news.TYPES.get(art["kind"], art["kind"]))}</span>'
                     + ("" if art["headline"] in b["text"] else f'<div class="head">{escape(art["headline"])}</div>') +
                     f'<details><summary>Read the full story</summary><div class="body">'
                     f'{_format(art["body"], players)}</div></details></div>')
    parts.append(f'<div class="stats"><span title="Replies"><span class="material-icons">chat_bubble_outline</span>'
                 f'{bitter.short_count(b.get("reply_count", 0))}</span>'
                 f'<span title="Rebits"><span class="material-icons">repeat</span>{bitter.short_count(b.get("rebits", 0))}</span>'
                 f'<span title="Likes"><span class="material-icons">favorite_border</span>'
                 f'{bitter.short_count(b.get("likes", 0))}</span></div>')
    reps = b.get("replies") or []
    if reps:
        def rep(r):
            return (f'<div class="reply">{_avatar(r)}<div>{_header(r)}'
                    f'<div class="text">{_format(r["text"], _player_list(league, r["players"]))}</div>'
                    f'<div class="stats"><span title="Likes"><span class="material-icons">favorite_border</span>'
                    f'{bitter.short_count(r.get("likes", 0))}</span></div></div></div>')
        parts.append('<div class="replies">' + "".join(rep(r) for r in reps[:REPLIES_SHOWN]))
        if len(reps) > REPLIES_SHOWN:
            parts.append(f'<details><summary>Show {len(reps) - REPLIES_SHOWN} more '
                         f'{"reply" if len(reps) - REPLIES_SHOWN == 1 else "replies"}</summary>'
                         + "".join(rep(r) for r in reps[REPLIES_SHOWN:]) + "</details>")
        parts.append("</div>")
    parts.append("</div></div>")
    return "".join(parts)


def build_news_tab(on_open_summary=None):
    """Builds the Bitter tab. Returns a function that refreshes it."""
    league = state.league
    ui.add_head_html(CSS)
    defaults = {"news_scope": "league", "news_team": league.user_team_id or league.teams[0].id,
                "news_player": None, "news_cats": set(bitter.CATS), "news_season": 0, "news_minor": False,
                "news_shown": PAGE}
    for k, v in defaults.items():
        if not hasattr(state, k):
            setattr(state, k, v)
    history = {}     # season -> its games from the save's history file (loaded when you pick that season)

    def chosen_season():
        """news_season: 0 = this season (the default), -1 = all seasons, else a year."""
        s = state.news_season or 0
        return league.season if s == 0 else (None if s == -1 else s)

    def past_games():
        s = chosen_season()
        if s is None or s == league.season or state.save_path is None:
            return None
        if s not in history:
            try:
                history[s] = read_history(saves.history_path(state.save_path), s)
            except Exception:
                history[s] = []
        return history[s]

    def filters():
        scope = state.news_scope
        team = {"mine": league.user_team_id, "team": state.news_team}.get(scope)
        if scope == "mine" and team is None:
            team = state.news_team
        player = state.news_player if scope == "player" else None
        minimum = 0 if scope == "league" and state.news_minor else None
        return team, player, chosen_season(), minimum

    def set_value(name, value, reset=True):
        setattr(state, name, value)
        if reset:
            state.news_shown = PAGE
        body.refresh()

    def toggle_cat(cat, on):
        cats = set(state.news_cats)
        (cats.add if on else cats.discard)(cat)
        set_value("news_cats", cats)

    @ui.refreshable
    def body():
        pg = past_games()
        team, player, season_, minimum = filters()
        waiting = state.news_scope == "player" and player is None
        data = {"bits": [], "trending": [], "follow": bitter.follow(league)} if waiting else \
            bitter.timeline(league, pg, team_id=team, player_id=player, season=season_, min_importance=minimum)
        all_bits = data["bits"]
        cats = state.news_cats or set()
        bits = [b for b in all_bits if b["cat"] in cats]
        counts = {}
        for b in all_bits:
            counts[b["cat"]] = counts.get(b["cat"], 0) + 1

        # ---- Top bar ----------------------------------------------------------
        with ui.row().classes("w-full px-8 pt-4 items-center gap-4"):
            ui.html('<div class="bitter-logo"><div class="mark">b</div>Bitter</div>', sanitize=False)
            ui.toggle(SCOPES, value=state.news_scope, on_change=lambda e: set_value("news_scope", e.value)) \
                .props("no-caps unelevated toggle-color=green-10 color=white text-color=grey-9") \
                .tooltip("For you: the bigger bits from around the league. Your team, a team or a player: "
                         "everything about them.")
            if state.news_scope == "team":
                ui.select({t.id: t.name for t in sorted(league.teams, key=lambda t: t.name)}, label="Team",
                          value=state.news_team, on_change=lambda e: set_value("news_team", e.value)) \
                    .props("dense outlined options-dense").classes("w-60")
            if state.news_scope == "player":
                known = news.news_players(league, pg)
                options = {}
                for pid in sorted(known, key=lambda pid: (-known[pid], pid)):
                    try:
                        p = league.player(pid)
                    except KeyError:
                        continue
                    tid = transactions.team_of(league, pid)[0]
                    where = league.team(tid).abbrev if tid else ("retired" if p.retired is not None else "FA")
                    n = known[pid]
                    options[pid] = f"{p.name} ({p.position}, {where}, {n} {'story' if n == 1 else 'stories'})"
                if state.news_player not in options:
                    state.news_player = state.selected_id if state.selected_id in options else None
                ui.select(options, label="Player (type to search)", value=state.news_player, with_input=True,
                          on_change=lambda e: set_value("news_player", e.value)) \
                    .props("dense outlined options-dense").classes("w-80")
            seasons = news.seasons(league, pg)
            season_opts = {0: f"This season ({league.season})", -1: "All seasons"}
            season_opts.update({s: str(s) for s in seasons if s != league.season})
            ui.select(season_opts, label="Season", value=state.news_season or 0,
                      on_change=lambda e: set_value("news_season", e.value)) \
                .props("dense outlined options-dense").classes("w-44") \
                .tooltip("Pick one earlier season to include its game recaps (read from the save's history "
                         "file). All seasons shows earlier seasons' other news.")
            if state.news_scope == "league":
                ui.checkbox("Include minor bits", value=state.news_minor,
                            on_change=lambda e: set_value("news_minor", e.value)) \
                    .tooltip("Every transaction, every injury, preseason games, every fan reaction. "
                             "Off: only the bigger bits league-wide.")

        with ui.row().classes("w-full px-8 py-4 gap-5 no-wrap items-start"):
            # ---- Left: which accounts ------------------------------------------
            with ui.column().classes("bitter-side gap-0").style("width: 220px; flex: none"):
                ui.label("Show bits from").classes("panel-heading")
                for cat, label in bitter.CATS.items():
                    ui.checkbox(f"{label} ({counts.get(cat, 0)})", value=cat in cats,
                                on_change=lambda e, c=cat: toggle_cat(c, e.value)).props("dense color=green-10")
                with ui.row().classes("gap-1 mt-2"):
                    ui.button("All", on_click=lambda: set_value("news_cats", set(bitter.CATS))) \
                        .props("no-caps flat dense color=green-10").tooltip("Show every kind of account")
                    ui.button("None", on_click=lambda: set_value("news_cats", set())) \
                        .props("no-caps flat dense color=green-10").tooltip("Clear, then tick the ones you want")
                ui.label("A yellow edge means the bit involves your team. Every account on Bitter is "
                         "made up; opinions are theirs, the facts are the league's.").classes("legend mt-3")

            # ---- Middle: the timeline --------------------------------------------
            with ui.column().classes("gap-0").style("flex: 1 1 0; min-width: 0; max-width: 760px"):
                if waiting:
                    ui.label("Pick a player above (type part of his name) to see every bit about him.") \
                        .classes("legend")
                elif not bits:
                    ui.label("Nothing here yet. Sim a week, or widen the filters.").classes("legend")
                for b in bits[:state.news_shown]:
                    mine = league.user_team_id in b["teams"] or b.get("team") == league.user_team_id
                    ui.html(_bit_html(league, b, mine), sanitize=False).classes("w-full")
                    art = b.get("article")
                    m = re.match(r"game-(\d+)-(\d+)$", art["id"]) if art else None
                    if m and on_open_summary and int(m.group(1)) == league.season and int(m.group(2)) in league.boxes:
                        ui.button("Game summary", on_click=lambda _e, gid=int(m.group(2)): on_open_summary(gid)) \
                            .props("no-caps flat dense color=green-10").classes("-mt-2 mb-2") \
                            .tooltip("Box score, team stats, scoring and drives for this game")
                if len(bits) > state.news_shown:
                    ui.button(f"Show {min(PAGE, len(bits) - state.news_shown)} more bits",
                              on_click=lambda: set_value("news_shown", state.news_shown + PAGE, reset=False)) \
                        .props("no-caps outline color=green-10")

            # ---- Right: trending and who to follow ----------------------------------
            with ui.column().classes("gap-0").style("width: 320px; flex: none"):
                trends = "".join(f'<div class="trend"><div class="meta">Trending in the league</div>'
                                 f'<div class="label">{escape(label)}</div><div class="meta">{escape(count)}</div></div>'
                                 for label, count in data["trending"]) or \
                    '<div class="meta">Nothing trending yet.</div>'
                ui.html(f'<div class="side-box"><div class="title">What\'s happening</div>{trends}</div>',
                        sanitize=False).classes("w-full")
                follows = "".join(
                    f'<div class="follow"><div class="av" style="background:{bitter.avatar_color(a["handle"])}">'
                    f'{escape(bitter.initials(a["name"]))}</div><div><b>{escape(a["name"])}</b> '
                    f'<span class="role">{escape(a["handle"])}</span><div class="role">{escape(a["bio"])}</div>'
                    f'<div class="role">{escape(a["followers"])} followers</div></div></div>' for a in data["follow"])
                ui.html(f'<div class="side-box"><div class="title">Who to follow</div>{follows}</div>',
                        sanitize=False).classes("w-full")

    body()
    return body.refresh
