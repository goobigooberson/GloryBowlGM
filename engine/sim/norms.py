# norms.py
# What an "average starter" looks like at each position, measured from the
# league itself. The sim compares every player to these averages (z-scores),
# so it stays calibrated even if the league's overall talent drifts over the
# years.

from statistics import mean, pstdev

from .. import positions as pos

# How many players per team count as starters when measuring the average.
STARTERS_PER_POSITION = {
    "QB": 1, "RB": 1, "FB": 1, "WR": 3, "TE": 2, "T": 2, "G": 2, "C": 1,
    "DE": 2, "DT": 2, "OLB": 2, "ILB": 1, "CB": 3, "S": 2, "K": 1, "P": 1, "LS": 1,
}
MIN_SD = 4.0          # never treat a skill as more uniform than this
DEFAULT = (55.0, 10.0)


class Norms:
    def __init__(self):
        self.stats = {}          # (position, skill) -> (mean, sd)
        self.overall = {}        # position -> (mean, sd) of overall rating
        self.any_position = {}   # skill -> (mean, sd) across every position that has it

    def get(self, position, skill):
        key = (position, skill)
        if key in self.stats:
            return self.stats[key]
        return self.any_position.get(skill, DEFAULT)

    def overall_of(self, position):
        return self.overall.get(position, DEFAULT)


def _summary(values):
    if len(values) < 2:
        return DEFAULT
    return mean(values), max(MIN_SD, pstdev(values))


def build_norms(league):
    """Measure the league's average starter at each position."""
    from ..player import fill_new_ratings
    for p in league.players:
        fill_new_ratings(p)
    norms = Norms()
    by_skill_all = {}
    for position, per_team in STARTERS_PER_POSITION.items():
        values = {}
        overalls = []
        skill_list = [s for s, _w in pos.POSITIONS[position][1]]
        for team in league.teams:
            group = sorted((p for p in league.team_players(team.id) if p.position == position),
                           key=lambda p: p.overall(), reverse=True)[:per_team]
            for p in group:
                overalls.append(p.overall())
                for s in skill_list:
                    values.setdefault(s, []).append(p.skills[s][0])
                    by_skill_all.setdefault(s, []).append(p.skills[s][0])
        norms.overall[position] = _summary(overalls)
        for s, vals in values.items():
            norms.stats[(position, s)] = _summary(vals)
    for s, vals in by_skill_all.items():
        norms.any_position[s] = _summary(vals)

    # Return men: the two best at each return skill per team, whatever position.
    for skill, slot in (("kick_return", "KR"), ("punt_return", "PR")):
        vals = []
        for team in league.teams:
            best = sorted((p.skills[skill][0] for p in league.team_players(team.id) if skill in p.skills),
                          reverse=True)[:2]
            vals.extend(best)
        norms.stats[(slot, skill)] = _summary(vals)
    return norms
