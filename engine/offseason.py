# offseason.py
# What happens between the Glory Bowl and next season's training camp, in the
# real NFL's order (run_offseason):
#   1. Retirements
#   2. The new league year: re-signings, tags, cap cuts, free agency (free_agency.py)
#   3. The draft and undrafted signings (draft.py, Step 8), more free agency
#   4. Camp opens: every team fills its 90-man roster (transactions.fill_camp_rosters)
#   5. The free-agent pool: old or long-unsigned players leave
#   6. Depth charts updated (the AI sets its own; yours keeps your order)
# The cut to 53 comes after the preseason (transactions.final_cuts, Oct 23);
# keep_value / template_cuts below are its rules.
#
# Retired players stay in the save (Player.retired = the year they retired)
# so their careers stay viewable.

import math
import random
from collections import defaultdict

from . import depth
from . import injuries
from .league import roster_value
from .teams import ROSTER_TEMPLATE, ROSTER_SIZE

# ---- Knobs ------------------------------------------------------------------
# Typical age a player at each position is done (retirement odds climb past it).
RETIRE_AGE = {"QB": 38, "RB": 31, "FB": 32, "WR": 33, "TE": 33, "T": 34, "G": 34, "C": 35,
              "DE": 33, "DT": 33, "OLB": 32, "ILB": 32, "CB": 32, "S": 33, "K": 40, "P": 39, "LS": 38}
RETIRE_AGE_SPREAD = 2.2      # years: how gradually the odds climb around that age
# (Oct 21: ages +1 and spread 1.6 -> 2.2, with each player's own aging profile, so a sim
# league's "still in the league next season" by pro season matches the real NFL's:
# careers had ended in a cliff around seasons 9-13; tools/retention_check.py.)
RETIRE_TALENT_K = 2.2        # better players (for their position) keep playing longer
RETIRE_GENERATIONAL_YEARS = 2.5   # Generational players last this much longer
RETIRE_AGE_FOLLOWS_PRIME = 1.0    # years later he's typically done per season his own prime runs long
HIGH_PICK_KEEP = 5.0         # (old flat bonus for this year's picks from rounds 1-3; replaced by DRAFT_KEEP)
# Who survives the cut to 53 (Oct 22). Real teams keep the young players they invested in and the
# picks they just made over similar veterans (and over last year's practice squad); without this,
# aged leagues piled up veterans (9+ seasons 15% of rosters by year 8 vs real 9%) because young
# players on the 53 were cut at 18% a year vs the real 5%, and rookies were 7.4% of week-1 rosters
# vs the real 12.3% (nflverse weekly rosters; docs/research/real_movement_summary.md). Values are
# roster_value points, tuned so those three match (scratchpad movement_fast.py).
DRAFT_KEEP = {1: 16.0, 2: 14.0, 3: 12.0, 4: 10.0, 5: 8.0, 6: 6.0, 7: 4.0}  # this year's picks, by round
UDFA_KEEP = 2.0              # this year's undrafted signings
INCUMBENT_YOUNG_KEEP = 0.0   # (tried: a bonus for young players who ended last season on the 53; real
INCUMBENT_YOUNG_EXP = 3      # young players churn MORE than the game's (only ~74% of 0-4 year players on a
                             # 53 at season's end are on a 53 the next week 1), so it's off)
VET_COST_K = 1.0             # stand-in for veterans' higher pay until contracts exist: roster_value points
VET_COST_FROM = 6            # off per season of experience beyond this (replace with real cap cost later)
# (Oct 22 night, with the old placeholder draft, now deleted: rookies 10.8% of rosters vs real 12.3,
# 9+ year veterans climbing to 15.3% by year 8 vs real ~9.2; the real draft, draft.py, took over Oct 23.)
FA_POOL_MAX = 260            # the free-agent pool keeps at most this many
FA_LEAVE_CHANCE = 0.30       # chance an unsigned free agent leaves the league each offseason
# ------------------------------------------------------------------------------


def _age(p, season):
    from datetime import date
    return p.age(date(season, 9, 1))


def _position_rank(players):
    """{player id: 0.0 (best at his position) .. 1.0 (worst)}, active players."""
    by_pos = defaultdict(list)
    for p in players:
        by_pos[p.position].append(p)
    out = {}
    for group in by_pos.values():
        group.sort(key=lambda p: p.overall(), reverse=True)
        n = max(1, len(group) - 1)
        for i, p in enumerate(group):
            out[p.id] = i / n
    return out


def retire_age(p):
    """The age he'd typically be done: his position's, plus Generational
    staying power, moved by his own aging profile (a player whose prime runs
    long plays longer; development.aging_profile)."""
    from .development import aging_profile
    shift, _rate = aging_profile(p)
    return (RETIRE_AGE.get(p.position, 32) + (RETIRE_GENERATIONAL_YEARS if p.generational else 0)
            + RETIRE_AGE_FOLLOWS_PRIME * shift)


def retirement_chance(p, season, rank):
    age = _age(p, season)
    typical = retire_age(p)
    x = (age - typical) / RETIRE_AGE_SPREAD + RETIRE_TALENT_K * (rank - 0.5)
    return 1 / (1 + math.exp(-x))


def retirements(league, rng):
    """Rostered players who retire this offseason (returns their ids)."""
    from .free_agency import retirement_contract_factor
    active = [p for p in league.players if p.retired is None and p.id in league.rosters]
    rank = _position_rank(active)
    gone = []
    for p in active:
        chance = retirement_chance(p, league.season, rank[p.id])
        # Some serious injuries end careers (about a third of players with a torn
        # Achilles never play again; injuries.py has each injury's push).
        for kind, _weeks in league.season_injuries.get(p.id, ()):
            chance = 1 - (1 - chance) * (1 - injuries.get(kind, p.position).retire)
        # Still under contract: real players rarely retire then, least of all young ones owed money
        # (Oct 24; free_agency.retirement_contract_factor, fitted to the real reserve/retired list).
        chance = min(1.0, chance * retirement_contract_factor(league, p, retire_age(p)))
        if rng.random() < chance:
            gone.append(p.id)
    return gone


def retire(league, pid):
    p = league.player(pid)
    p.retired = league.season - 1       # retired after the season just played
    league.rosters.pop(pid, None)


# ---------------------------------------------------------------------------
# Talent levels and the draft order
# ---------------------------------------------------------------------------

STARTER_COUNTS = {"QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 1, "T": 2, "G": 2, "C": 1, "DE": 2, "DT": 2,
                  "OLB": 2, "ILB": 1, "CB": 2, "S": 2, "K": 1, "P": 1, "LS": 1}


def starter_levels(league):
    """{position: average overall of each team's best players there} (a
    team's starters at that position, e.g. its top 3 WRs)."""
    out = {}
    for position, n in STARTER_COUNTS.items():
        tops = []
        for t in league.teams:
            group = sorted((p.overall() for p in league.team_players(t.id) if p.position == position), reverse=True)
            tops += group[:n]
        if tops:
            out[position] = sum(tops) / len(tops)
    return out


def talent_targets(league):
    """Each position's starter level in the league's first offseason, kept
    as the level the league's talent pipeline steers back toward."""
    t = league.settings.get("talent_targets")
    if not t:
        t = {k: round(v, 2) for k, v in starter_levels(league).items()}
        league.settings["talent_targets"] = t
    return t


def draft_order(league, season_lines):
    """Team ids, first pick first: teams that missed the playoffs by record
    (worst first), then playoff teams by how far they went, champion last."""
    def pct(r):
        g = r["w"] + r["l"] + r["t"]
        return (r["w"] + 0.5 * r["t"]) / g if g else 0.0
    stage = {"Missed the playoffs": 0, "Lost in the Wild Card round": 1, "Lost in the divisional round": 2,
             "Lost in the conference championship": 3}
    tie = random.Random(f"draft-order-{league.season}")
    coin = {r["team"]: tie.random() for r in season_lines}

    def key(r):
        res = r["result"]
        s = stage.get(res, 5 if res.startswith("Won") else 4)
        return (s, pct(r), coin[r["team"]])
    return [r["team"] for r in sorted(season_lines, key=key)]


def keep_value(league, p, tid):
    """How much a team wants to keep him at the cut to 53: his roster value,
    plus a bonus for this year's draft picks and undrafted signings, plus
    money (keep players whose cut would leave dead money, let go of players
    whose cut saves real cap room)."""
    last_53 = getattr(league, "last_53", None) or {}
    from .evaluation import seen
    v = roster_value(seen(league, tid, p))      # as this team's staff sees him (Oct 24)
    if p.draft_year == league.season:
        v += DRAFT_KEEP.get(p.draft_round, UDFA_KEEP)
    elif p.experience <= INCUMBENT_YOUNG_EXP and last_53.get(p.id) == tid:
        v += INCUMBENT_YOUNG_KEEP
    # Money (free_agency.cut_money_value) replaces the VET_COST_K stand-in (kept for
    # leagues without contracts).
    if getattr(league, "contracts", None):
        from .free_agency import cut_money_value
        v += cut_money_value(league, p)
    else:
        v -= VET_COST_K * max(0, p.experience - VET_COST_FROM)
    return v


def template_cuts(league, tid, players=None):
    """Who a team cuts to get to 53 with each position at its roster count:
    at each position with too many, the ones it least wants to keep."""
    by_pos = defaultdict(list)
    for p in (players if players is not None else league.team_players(tid)):
        by_pos[p.position].append(p)
    cuts = []
    for position, group in by_pos.items():
        want = ROSTER_TEMPLATE.get(position, 0)
        if len(group) > want:
            group.sort(key=lambda p: keep_value(league, p, tid), reverse=True)
            cuts += group[want:]
    return cuts


def cut_to_53(league):
    """Every team cuts down to 53 with each position at its roster count:
    the lowest-rated players at positions with too many go (this year's
    picks get a bonus; see keep_value). Returns [(pid, team)]. (Tools that skip the
    preseason; the season itself makes its cuts in transactions.final_cuts.)"""
    cuts = []
    for t in league.teams:
        for p in template_cuts(league, t.id):
            league.rosters.pop(p.id, None)
            cuts.append((p.id, t.id))
    return cuts


def fill_short_positions(league, rng, teams=None):
    """Any position still short (more retirements than rookies there): sign
    the best free agent at that position the team can afford (with contracts:
    he's paid what he asks, so a capped-out team takes a street free agent)."""
    from . import free_agency as FA
    money = bool(getattr(league, "contracts", None))
    signed = []
    for t in (teams if teams is not None else league.teams):
        roster = league.team_players(t.id)
        have = defaultdict(int)
        for p in roster:
            have[p.position] += 1
        due = 0             # $K of this team's fills here, not on the books until free_agency.sync
        for position, want in ROSTER_TEMPLATE.items():
            while have[position] < want:
                fas = [p for p in league.free_agents() if p.position == position]
                if money:
                    fas = [p for p in fas if FA.affordable(league, t.id, p.id, also=due)]
                if not fas:
                    # A made-up street free agent, at undrafted-rookie level (draft.py; made at
                    # full starting-league level before Oct 23, an outside source of talent).
                    from .draft import street_free_agent
                    p = street_free_agent(position, experience=rng.choice([0, 1, 2]), season_year=league.season)
                    league.players.append(p)
                    if money:
                        from . import contracts as C
                        due += C.min_salary(league, p.experience)
                else:
                    p = max(fas, key=roster_value)
                    if money:
                        due += FA.asking_hit(league, t.id, p.id)
                league.rosters[p.id] = t.id
                have[position] += 1
                signed.append((p.id, t.id))
    return signed


def trim_free_agents(league, rng):
    """Old or long-unsigned free agents leave the league; the pool keeps at
    most FA_POOL_MAX players. Those who leave are marked retired."""
    left = []
    for p in league.free_agents():
        age = _age(p, league.season)
        if age >= retire_age(p) or rng.random() < FA_LEAVE_CHANCE * (0 if p.experience == 0 else 1):
            p.retired = league.season - 1
            left.append(p.id)
    fas = sorted(league.free_agents(), key=roster_value, reverse=True)
    for p in fas[FA_POOL_MAX:]:
        p.retired = league.season - 1
        left.append(p.id)
    return left


def update_depth_charts(league, before):
    """AI teams set their whole depth chart. Your team keeps your order:
    players who left come off; where your starter at a spot left, the best
    fit there (the AI's pick) becomes the starter, with your remaining
    choices behind him, then the AI's backups to fill the list.
    (The first version just moved your next listed player up, so after
    a few unmanaged offseasons an emergency backup, a QB listed fourth at
    tight end, could end up starting there.)"""
    for t in league.teams:
        if t.id != league.user_team_id:
            league.auto_depth_chart(t.id)
            continue
        roster_ids = {p.id for p in league.team_players(t.id)}
        auto = depth.auto_depth_chart(league.team_players(t.id))
        chart = league.depth_charts.get(t.id, {})
        for slot, ids in auto.items():
            old = chart.get(slot, [])
            kept = [pid for pid in old if pid in roster_ids]
            if not old or old[0] not in roster_ids:
                starter = ids[:1]
                kept = starter + [pid for pid in kept if pid not in starter]
            fill = [pid for pid in ids if pid not in kept]
            chart[slot] = (kept + fill)[:max(len(old), len(ids))]
        league.depth_charts[t.id] = chart


# ---------------------------------------------------------------------------
# The whole offseason
# ---------------------------------------------------------------------------

def run_offseason(league, season_lines, rng=None):
    """The whole offseason at once for the new league.season (already
    advanced): every phase below in order, your team's decisions left to
    their defaults (expiring players you haven't re-signed become free
    agents). Tools use this; the game plays the phases one at a time with
    you in between (season.advance_offseason). season_lines: the finished
    season's team lines (for the draft order). Returns the report."""
    offseason_start(league, season_lines, rng)
    while league.offseason["phase"] != "done":
        offseason_next(league, rng)
    return league.offseason_report


# ---------------------------------------------------------------------------
# The offseason, phase by phase (Oct 23; Blake: "Phases, Next button")
# ---------------------------------------------------------------------------
# The real NFL's order: retirements, the new league year (cap, AI re-signings, tags, cap
# cuts) and your exclusive window with your expiring players; free agency in waves (you
# place offers before each); the draft and rookie deals, undrafted signings; free agency
# after the draft; then training camp opens with 90-man rosters. The cut to 53 and practice
# squads come after the preseason (transactions.final_cuts). league.offseason (saved) holds
# where we are: {"phase": "resign" | "fa" | "draft" | "camp" | "done", "wave": next free
# agency wave, "order": draft order, "before": rosters at the start, ...}.
# (Until Oct 23 the offseason ran while the league still said "season complete", so the
# money rules counted all 18 weeks of the new season as paid: every offseason cut charged a
# vested veteran's whole salary as dead money, and the top-51 rule was off.)

def _phase_rng(league, name, rng=None):
    return rng or random.Random(f"offseason-{league.settings.get('salt', '')}-{league.season}-{name}")


def offseason_start(league, season_lines, rng=None):
    """Retirements, the draft order and the start of the league year (AI teams
    decide their expiring players; yours wait for you in league.fa['pending'])."""
    from . import contracts as C
    from . import free_agency as FA
    FA.ensure(league)
    league.stage = "offseason"
    r = _phase_rng(league, "start", rng)
    before = {t.id: [p.id for p in league.team_players(t.id)] for t in league.teams}
    retired = [[pid, league.rosters.get(pid)] for pid in retirements(league, r)]
    for pid, _tid in retired:
        C.retire(league, pid)
        retire(league, pid)
    order = draft_order(league, season_lines)
    # This year's draft class is announced (the combine, late February, before the league
    # year), so you can scout it during free agency (draft_day.py, scouting.py; Blake,
    # Oct 23: scout before the draft). Made from the rosters as the season ended: after
    # the league year starts, teams' expiring players are gone and every position looks
    # emptier than it will be by the draft (measured: the class leaned toward K/P/LS and
    # QB starters slipped over 22 seasons).
    from . import draft_day
    draft_day.new_class(league, _phase_rng(league, "class", rng))
    fa_report = FA.league_year_start(league, r, draft_order=order)
    league.fa["wave"] = None            # the exclusive window: your players ask their re-sign price
    league.offseason = {"phase": "resign", "wave": FA.PRE_DRAFT_WAVES[0], "order": order,
                        "before": {str(k): v for k, v in before.items()}}
    league.offseason_report = {"season": league.season, "retired": retired, "draft": [], "udfa": [], "cuts": [],
                               "signed": [], "fa_left": [], "free_agency": dict(fa_report or {}),
                               "draft_trades": [], "fa_signings": []}
    # The coaching carousel comes first (staff.py, Oct 24; real: Black Monday into
    # February). Its own dice, so the rest of the offseason draws exactly as before.
    from . import staff
    if getattr(league, "staff", None):
        staff.carousel_start(league, season_lines,
                             random.Random(f"coaching-{league.settings.get('salt', '')}-{league.season}"))
        league.offseason["phase"] = "coaching"
    return league.offseason_report


def offseason_next(league, rng=None):
    """Play the current phase and move to the next one. Returns the phase now."""
    from . import free_agency as FA
    st = league.offseason
    rep = league.offseason_report
    phase = st["phase"]
    if phase == "coaching":
        # One round of the coaching carousel (staff.py); after the last, the league year.
        from . import staff
        rnd = (league.staff.get("carousel") or {}).get("round", 3)
        if staff.carousel_next(league, random.Random(
                f"coaching-{league.settings.get('salt', '')}-{league.season}-{rnd}")):
            st["phase"] = "resign"
    elif phase == "resign":
        # The market opens: your expiring players you haven't re-signed become free agents.
        FA.open_market(league)
        st["phase"] = "fa"
        league.fa["wave"] = st["wave"]
    elif phase == "fa":
        wave = st["wave"]
        before_draft = wave in FA.PRE_DRAFT_WAVES
        signed = FA.market(league, (wave,), _phase_rng(league, f"fa{wave}", rng), before_draft=before_draft)
        rep["fa_signings"] = rep.get("fa_signings", []) + [
            {k: s[k] for k in ("wave", "pid", "team", "apy", "years", "former")} for s in signed]
        league.fa["user_offers"] = {}
        later = [w for w in FA.PRE_DRAFT_WAVES + FA.POST_DRAFT_WAVES if w > wave]
        if wave == FA.PRE_DRAFT_WAVES[-1]:
            st["phase"] = "draft"
        elif not later:
            st["phase"] = "camp"
        if later:
            st["wave"] = later[0]
            league.fa["wave"] = later[0]
    elif phase == "draft":
        # The draft starts: it stops when your team is on the clock (the Draft tab;
        # draft_day.py). With no picks of yours left to make it's over right away.
        r = _phase_rng(league, "draft", rng)
        if _draft_phase(league, r):
            _draft_done(league, r)
            st["phase"] = "fa"
            league.fa["wave"] = st["wave"]
        else:
            st["phase"] = "drafting"
    elif phase == "drafting":
        # Next during the draft: your staff makes the rest of your picks.
        _draft_done(league, _phase_rng(league, "draft", rng))
        st["phase"] = "fa"
        league.fa["wave"] = st["wave"]
    elif phase == "camp":
        _camp_phase(league, _phase_rng(league, "camp", rng))
        st["phase"] = "done"
    return st["phase"]


def _draft_phase(league, rng):
    """The draft starts (Step 8, draft.py / draft_day.py): AI boards with real
    scouting error, needs, QB rules, draft-day trades. The AI picks until your
    team is on the clock. Returns True if the draft is already over."""
    from . import draft_day
    return draft_day.start(league, league.offseason["order"], rng)


def _draft_done(league, rng):
    """The draft is over (your staff makes any picks you haven't): rookie deals,
    undrafted signings by the teams' boards, the draft history and report."""
    from . import draft_day
    draft_day.finish(league, rng)


def _camp_phase(league, rng):
    """Training camp opens: tagged players' long-term deals, AI teams under the cap
    (top-51 rule), 90-man camp rosters filled, the free-agent pool trimmed, depth charts."""
    from . import free_agency as FA
    from . import transactions
    rep = league.offseason_report
    FA.tagged_long_term(league, rng)
    FA.final_compliance(league)
    FA.sync(league)
    # Every team fills its 90-man roster with camp bodies (yours: your staff, cheap young
    # players at the positions you're thinnest; cut whoever you like).
    filled = transactions.fill_camp_rosters(league, rng, "Training camp")
    FA.sync(league, "training camp")
    left = trim_free_agents(league, rng)
    before = {int(k): set(v) for k, v in league.offseason.get("before", {}).items()}
    update_depth_charts(league, before)
    # Sanity: every team has a full 53 at least, and no more than 90.
    for t in league.teams:
        n = len(league.team_players(t.id))
        assert ROSTER_SIZE <= n <= transactions.roster_rules.CAMP_LIMIT, (t.abbrev, n)
    rep["signed"] = [list(x) for x in filled]
    rep["fa_left"] = left
