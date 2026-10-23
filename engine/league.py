# league.py
# Builds a brand-new fictional league: 32 teams with full 53-man rosters,
# plus a pool of unsigned free agents.
#
# How rosters are filled, in plain terms:
#   1. For each position, generate a big pool of players (2.5 for every
#      roster spot). Pro players are the best of a much larger group, and
#      this mirrors that.
#   2. Keep the best of the pool for the league. "Best" mixes current
#      ability with potential, so teams keep some raw young players too.
#   3. Hand them out to teams in tiers (the 32 best QBs are the starters,
#      the next 32 the backups...), with some luck mixed in so a few teams
#      end up stronger or weaker than others.
#   4. The best of the leftovers become free agents.
#   5. A few Generational players are created and placed on random teams.
#   6. Every player gets a draft history (round, or undrafted) and a college
#      that fits it, so first-rounders mostly come from big programs.

import random
from dataclasses import dataclass, field

from .player import generate_player, Player
from . import colleges
from . import depth
from . import transactions
from .transactions import PS_TEMPLATE
from .teams import Team, make_teams, ROSTER_TEMPLATE, ROSTER_SIZE

# ---- Balance settings: change these to tune the league ------------------
POOL_FACTOR = 2.5          # players generated per roster spot
MIN_POOL = 100             # never fewer than this per position (so K and P have real competition)
POTENTIAL_WEIGHT = 0.5     # how much teams value upside vs current ability
PARITY_LUCK = 4.0          # higher = bigger gap between strong and weak teams
# Optional: give each team a hidden organization strength that tilts which
# players it lands in every position tier, so strong teams tend to be good in
# several places at once. Off (0.0) by Blake's decision: starting teams are
# fairly even, and the gaps grow over the seasons from team building. In game
# sim tests, 0.4 gave an NFL-like spread of team strength from day one.
ORG_STRENGTH = 0.0
FREE_AGENTS_PER_TEAM = 4   # size of the starting free-agent pool, per team
PS_POOL_FACTOR = 1.5       # young leftovers kept per practice squad spot (the squads pick the best)
GENERATIONAL_RATE = 1 / 400  # chance that any given roster player is Generational
# Most Generational players allowed at once at these positions (Blake: a
# Generational fullback, kicker or punter should be a true rarity).
# Positions not listed have no limit beyond the overall rarity.
GENERATIONAL_LIMITS = {"FB": 1, "K": 1, "P": 1, "LS": 1}
DRAFT_SCOUTING_MISS = 6.0  # how much past drafts misjudged players (busts and late gems)
# Captain vote (Blake, Oct 20): extra votes, on top of leadership, experience,
# popularity and luck (see League.vote_captains).
CAPTAIN_QB_BONUS = 14       # the starting QB: real teams almost always make him a captain
CAPTAIN_RETURNING_BONUS = 5  # last season's captain usually gets voted in again
CAPTAIN_GENERATIONAL_BONUS = 6  # teammates' respect for a Generational player
# --------------------------------------------------------------------------

# League settings chosen on the New game screen (stored in the save file).
#   season_games: regular season games per team (16 or 17)
#   roster_method: how the starting rosters were filled
#       "random" = random generated rosters (fairly even teams)
#       "startup_draft" and "legacy" come later
DEFAULT_SETTINGS = {"season_games": 17, "roster_method": "random"}
ROSTER_METHODS = {"startup_draft": "Startup draft", "random": "Random generated rosters",
                  "legacy": "Legacy rosters (real NFL seasons)"}


@dataclass
class League:
    season: int
    teams: list
    players: list = field(default_factory=list)   # every player, signed or not
    # player id -> team id. Players missing from here are free agents.
    rosters: dict = field(default_factory=dict)
    # team id -> {spot: [player ids, starter first]} (see depth.py)
    depth_charts: dict = field(default_factory=dict)
    # team id -> {"Offense": player id, "Defense": player id}
    captains: dict = field(default_factory=dict)
    # The team you run as GM. Every other team is AI-controlled.
    user_team_id: int = None
    # The save's name (shown in Load game) and its league settings.
    name: str = ""
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))
    # The season in progress (see season.py and schedule.py).
    schedule: list = field(default_factory=list)   # every game: id, week, home, away, kind, played, scores
    preseason: list = field(default_factory=list)  # preseason games (weeks 1-5; week 1 = Hall of Fame Game)
    pre_week: int = 1                              # the preseason week being played next
    week: int = 1                                  # the regular-season week being played next
    stage: str = "regular_season"                  # preseason / regular_season / playoffs / season_complete
    playoffs: list = field(default_factory=list)   # playoff games (week = round: 1 Wild Card ... 5 Glory Bowl)
    playoff_round: int = 0                         # the playoff round being played next (4 = off week)
    playoff_seeds: dict = None                     # conference -> [7 team ids, seed 1 first]
    # History, kept for good (Blake: every player's whole career must be saved).
    career: list = field(default_factory=list)       # player season lines: pid, season, phase, team, stats
    team_history: list = field(default_factory=list) # team season lines: record, finish, seed, playoff result
    champions: dict = field(default_factory=dict)    # season -> champion team id
    draft_history: list = field(default_factory=list)  # every pick: season, round, pick, team, pid
    offseason_report: dict = None                    # what happened in the last offseason (Offseason screen)
    rating_history: list = field(default_factory=list)  # every player's overall/potential each season
    season_injuries: dict = field(default_factory=dict) # player id -> [[injury kind, weeks], ...] this season
                                                        # (only injuries that can mark a career; injuries.py)
    injuries: dict = field(default_factory=dict)   # player id -> {team, weeks left, part, week hurt}
    injury_history: list = field(default_factory=list)  # every injury for good: {pid, season, game, team,
                                                        # kind, weeks, how} (season.record_game)
    recovering: dict = field(default_factory=dict)  # player id -> {kind, team, games}: back from an injury,
                                                    # first games still at risk of a flare-up (injuries.py)
    boxes: dict = field(default_factory=dict)      # game id -> box score of a played game
    division_ranks: dict = None                    # team id -> place in division last season (None = first season)
    # Roster moves (transactions.py). rosters above is the 53-man roster only.
    practice: dict = field(default_factory=dict)     # player id -> team id: practice squads (16 each)
    reserve: dict = field(default_factory=dict)      # player id -> {team, list (IR/PUP), since, games missed}
    waivers: list = field(default_factory=list)      # waived this week: {pid, team, cal}
    transactions: list = field(default_factory=list)  # every move, kept for good: {season, when, team, pid, move, note}
    ir_returns: dict = field(default_factory=dict)   # team id -> players brought back from IR this season
    elevations: dict = field(default_factory=dict)   # player id -> game-day elevations this season
    elevated: dict = field(default_factory=dict)     # team id -> [player ids] elevated for this week's game
    staff_requests: list = field(default_factory=list)  # your staff asks before a bigger move (transactions.py)
    # Money (contracts.py, free_agency.py; built Oct 22-23).
    contracts: dict = field(default_factory=dict)    # player id -> contract {team, kind, years [{season, base,
                                                     # bonus, gtd}], apy, value, guaranteed, signing_bonus, ...}
    cap_history: dict = field(default_factory=dict)  # season -> salary cap ($K)
    cap_carry: dict = field(default_factory=dict)    # team -> {season: unused cap carried over ($K)}
    cap_charges: dict = field(default_factory=dict)  # team -> {season: dead money and other charges ($K)}
    contract_log: list = field(default_factory=list)  # every signing, kept for good
    june1_used: dict = field(default_factory=dict)   # team -> {season: June 1 cuts used}
    fa: dict = field(default_factory=dict)           # this league year's free agency state
    tv: dict = field(default_factory=dict)           # TV and labor deals, shocks, league buzz,
                                                     # next year's cap projection (league_money.py)
    offseason: dict = None                           # where the offseason is (offseason.py), None in-season
    long_injuries: dict = field(default_factory=dict)  # player id -> {kind, week, team}: season-ending
                                                       # injuries this season (next season's carryover)
    draft: dict = None                               # this year's draft class and draft in progress, or a
                                                     # startup draft (draft_day.py); None when there's none

    def team_players(self, team_id):
        """The team's 53-man roster (the players who can play)."""
        return self.in_order(pid for pid, t in self.rosters.items() if t == team_id)

    def in_order(self, pids):
        """These players, in the order of self.players (what a scan of the whole
        list would give; Oct 22, for speed: rosters are a small part of a league's
        players once retired players pile up). Players are only ever added to the
        list, so each one's place is remembered until it grows."""
        order = self.__dict__.get("_order")
        if order is None or len(order) != len(self.players):
            order = {p.id: i for i, p in enumerate(self.players)}
            self.__dict__["_order"] = order
        players = self.players
        return [players[i] for i in sorted(order[pid] for pid in pids if pid in order)]

    def free_agents(self):
        """Unsigned players who are still playing (retired players aren't free
        agents; neither are practice squad or injured reserve players, nor
        draft prospects before the draft is over: draft_day.py)."""
        pool = set((self.draft or {}).get("pool", ()))
        return [p for p in self.players if p.id not in self.rosters and p.retired is None
                and p.id not in self.practice and p.id not in self.reserve and p.id not in pool]

    def __setstate__(self, state):
        """Unpickling (tools that keep a league in a .pkl file): new players made
        after this (draft classes, camp bodies) must get fresh ids, as
        database.load_league makes sure for saves. (Before Oct 24 a pickled league
        restarted ids at 1: new players took old players' ids and their contracts,
        and the money rules then charged huge dead money for them.)"""
        self.__dict__.update(state)
        from . import player as player_module
        if self.players:
            player_module._next_id = max(player_module._next_id, max(p.id for p in self.players) + 1)

    def player(self, pid):
        """A player (active or retired) by id."""
        index = self.__dict__.get("_index")
        if index is None or len(index) != len(self.players):
            index = {p.id: p for p in self.players}
            self.__dict__["_index"] = index
        return index[pid]

    def team(self, team_id):
        return next(t for t in self.teams if t.id == team_id)

    def auto_depth_chart(self, team_id):
        """Let the AI set this team's depth chart (giving its recent high draft
        picks a real chance: draft.draft_capital)."""
        pick_of = {d["pid"]: d["pick"] for d in self.draft_history[-1000:]}
        # As the team's own staff sees its players (Oct 24; evaluation.py: close to the truth,
        # since coaches see their players every day).
        from .evaluation import seen
        players = [seen(self, team_id, p) for p in self.team_players(team_id)]
        self.depth_charts[team_id] = depth.auto_depth_chart(players, pick_of=pick_of)

    def vote_captains(self, team_id, rng=random):
        """Captains are voted on by the players, not picked by the GM: one for
        the offense, one for the defense. Players mostly vote for leaders,
        lean toward veterans and well-liked starters, and the vote isn't
        perfectly predictable. The starting quarterback, last season's
        captain and Generational players get extra votes. Held once a season
        (for now, when the league is created; later, each preseason)."""
        chart = self.depth_charts.get(team_id, {})
        starters = depth.starter_ids(chart)
        starting_qb = (chart.get("QB") or [None])[0]
        previous = self.captains.get(team_id, {})
        chosen = {}
        for unit in ("Offense", "Defense"):
            group = [p for p in self.team_players(team_id)
                     if depth.unit_of_position(p.position) == unit]
            voters_pick = [p for p in group if p.id in starters] or group
            if not voters_pick:
                continue

            def votes(p):
                v = (p.leadership * 0.7 + min(p.experience, 10) * 2.0
                     + p.popularity * 0.1 + rng.gauss(0, 4))
                if p.id == starting_qb:
                    v += CAPTAIN_QB_BONUS
                if p.id == previous.get(unit):
                    v += CAPTAIN_RETURNING_BONUS
                if p.generational:
                    v += CAPTAIN_GENERATIONAL_BONUS
                return v
            chosen[unit] = max(voters_pick, key=votes).id
        self.captains[team_id] = chosen

    def generational_allowed(self, position):
        """Can another Generational player appear at this position right now?
        Future draft classes must check this too."""
        limit = GENERATIONAL_LIMITS.get(position)
        if limit is None:
            return True
        current = sum(p.generational and p.position == position and p.retired is None for p in self.players)
        return current < limit


def roster_value(p: Player):
    """How a team rates a player when deciding who makes the roster."""
    return (1 - POTENTIAL_WEIGHT) * p.overall() + POTENTIAL_WEIGHT * p.overall("potential")


def create_league(season=2026, seed=None, camp=True):
    """A new generated league. camp: it starts at training camp, with 90-man
    camp rosters (the practice squads and camp bodies join each 53) and final
    cuts after the preseason, like every later season (Oct 23); camp=False
    keeps each team's 53 and practice squad (tools that play games without a
    preseason, and the rating scale)."""
    if seed is not None:
        random.seed(seed)
    teams = make_teams()
    n_teams = len(teams)
    league = League(season=season, teams=teams)

    # 5 (decided first). How many Generational players, and where.
    roster_spots = n_teams * ROSTER_SIZE
    n_generational = sum(random.random() < GENERATIONAL_RATE for _ in range(roster_spots))
    n_generational = max(3, min(7, n_generational))   # keep it between 3 and 7
    spot_list = [p for p, count in ROSTER_TEMPLATE.items() for _ in range(count)]
    generational_positions = []
    while len(generational_positions) < n_generational:
        choice = random.choice(spot_list)
        limit = GENERATIONAL_LIMITS.get(choice)
        if limit is None or generational_positions.count(choice) < limit:
            generational_positions.append(choice)

    org = {t.id: random.gauss(0, ORG_STRENGTH) for t in teams}
    extra_pool = []

    for position, per_team in ROSTER_TEMPLATE.items():
        needed = per_team * n_teams

        # 1. The pool
        pool = [generate_player(position, season_year=season)
                for _ in range(max(MIN_POOL, int(needed * POOL_FACTOR)))]

        # Generational players at this position are guaranteed a roster spot.
        locked = [generate_player(position, season_year=season, generational=True)
                  for _ in range(generational_positions.count(position))]

        # 2. Keep the best
        pool.sort(key=roster_value, reverse=True)
        keep = locked + pool[:needed - len(locked)]
        leftovers = pool[needed - len(locked):]

        # 3. Hand out in tiers, with luck. Each team gets exactly one player
        #    from each tier, so every roster has the right number per position.
        keep.sort(key=lambda p: roster_value(p) + random.gauss(0, PARITY_LUCK), reverse=True)
        for tier_start in range(0, needed, n_teams):
            tier = keep[tier_start:tier_start + n_teams]
            # Better organizations tend to land the better players in each tier.
            team_order = sorted(teams, key=lambda t: org[t.id] + random.gauss(0, 1), reverse=True)
            for player, team in zip(tier, team_order):
                league.rosters[player.id] = team.id
        league.players.extend(keep)

        # 4. Free agents: the best leftovers, spread across positions
        #    in the same proportions as a roster.
        n_free = round(FREE_AGENTS_PER_TEAM * n_teams * per_team / ROSTER_SIZE)
        league.players.extend(leftovers[:n_free])
        # Young leftovers kept for the practice squads (added at the end, below).
        young = [p for p in leftovers[n_free:] if p.experience <= 2]
        extra_pool.extend(young[:round(PS_POOL_FACTOR * PS_TEMPLATE.get(position, 0) * n_teams)])

    # 6. Draft history, position by position. Rank each position group by how
    #    good the players looked coming out of college (mostly their ceiling),
    #    with some misjudgment mixed in. The best get drafted, in rounds that
    #    match how that position really goes in the draft (kickers late,
    #    QBs often early); the rest went undrafted.
    for position, per_team in ROSTER_TEMPLATE.items():
        group = [p for p in league.players if p.position == position]
        group.sort(key=lambda p: 0.7 * p.overall("potential") + 0.3 * p.overall()
                                 + random.gauss(0, DRAFT_SCOUTING_MISS),
                   reverse=True)
        drafted_share = colleges.DRAFT_BY_POSITION[position][0]
        n_drafted = round(drafted_share * per_team * n_teams)
        for p, rnd in zip(group, colleges.rounds_for_position(position, len(group), n_drafted)):
            p.set_draft_history(rnd)

    # 7. Every team's depth chart (set by the AI), then the players vote
    #    for captains.
    for team in teams:
        league.auto_depth_chart(team.id)
        league.vote_captains(team.id)

    # 8. Practice squads (16 per team, real NFL rules; transactions.py), from the
    #    best young leftovers and free agents. Done last so everything above
    #    comes out the same as before practice squads existed.
    for p in extra_pool:
        # Young players nobody kept: a recent early-round pick would still be on a roster.
        if 1 <= p.draft_round <= 3:
            p.set_draft_history(0)
    league.players.extend(extra_pool)
    transactions.form_practice_squads(league, league.injuries, league.recovering)

    # 9. Contracts: every player on a team gets a realistic one (free_agency.py), as if
    #    the league had been running for years (past caps, rookie deals, veterans' deals).
    if "salt" not in league.settings:
        league.settings["salt"] = random.randrange(1 << 30)
    from . import free_agency
    free_agency.initial_contracts(league)
    # 10. Coaching staffs and front offices (staff.py, Oct 24; seeded by the league's salt).
    from . import staff
    staff.ensure(league)
    if camp:
        # 10. Training camp opens (Oct 23): practice squads and camp bodies join the 53s.
        league.stage = "preseason"
        transactions.open_camp(league, random.Random(f"camp-{league.settings['salt']}"))
        free_agency.sync(league, "training camp")
        for team in teams:
            league.auto_depth_chart(team.id)
    return league
