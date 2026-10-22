# teams.py
# The league's teams and how a roster is built. Pure data: edit freely.
# All team names are invented for this game.

from dataclasses import dataclass


@dataclass
class Team:
    id: int
    city: str
    nickname: str
    abbrev: str
    conference: str
    division: str

    @property
    def name(self):
        return f"{self.city} {self.nickname}"


# (city, nickname, abbreviation, conference, division)
TEAM_LIST = [
    # Eastern Conference
    ("Boston",        "Harbormen",    "BOS", "Eastern", "Northeast"),
    ("New York",      "Knights",      "NYK", "Eastern", "Northeast"),
    ("Philadelphia",  "Liberty",      "PHI", "Eastern", "Northeast"),
    ("Buffalo",       "Blizzard",     "BUF", "Eastern", "Northeast"),
    ("Baltimore",     "Clippers",     "BAL", "Eastern", "Atlantic"),
    ("Washington",    "Sentinels",    "WAS", "Eastern", "Atlantic"),
    ("Pittsburgh",    "Ironmen",      "PIT", "Eastern", "Atlantic"),
    ("Cincinnati",    "Rivermen",     "CIN", "Eastern", "Atlantic"),
    ("Cleveland",     "Forge",        "CLE", "Eastern", "Central"),
    ("Detroit",       "Mechanics",    "DET", "Eastern", "Central"),
    ("Chicago",       "Express",      "CHI", "Eastern", "Central"),
    ("Indianapolis",  "Speed",        "IND", "Eastern", "Central"),
    ("Charlotte",     "Monarchs",     "CHA", "Eastern", "South"),
    ("Atlanta",       "Firebirds",    "ATL", "Eastern", "South"),
    ("Miami",         "Barracudas",   "MIA", "Eastern", "South"),
    ("Tampa",         "Storm",        "TAM", "Eastern", "South"),
    # Western Conference
    ("Minneapolis",   "Freeze",       "MIN", "Western", "Midwest"),
    ("Kansas City",   "Blues",        "KCY", "Western", "Midwest"),
    ("St. Louis",     "Archers",      "STL", "Western", "Midwest"),
    ("Nashville",     "Outlaws",      "NSH", "Western", "Midwest"),
    ("Houston",       "Wildcatters",  "HOU", "Western", "Gulf"),
    ("Dallas",        "Stampede",     "DAL", "Western", "Gulf"),
    ("San Antonio",   "Vaqueros",     "SAN", "Western", "Gulf"),
    ("New Orleans",   "Krewe",        "NOR", "Western", "Gulf"),
    ("Seattle",       "Sound",        "SEA", "Western", "Northwest"),
    ("Portland",      "Lumberjacks",  "POR", "Western", "Northwest"),
    ("San Francisco", "Fog",          "SFO", "Western", "Northwest"),
    ("Denver",        "Peaks",        "DEN", "Western", "Northwest"),
    ("Los Angeles",   "Stars",        "LAS", "Western", "Pacific"),
    ("San Diego",     "Surf",         "SDG", "Western", "Pacific"),
    ("Las Vegas",     "High Rollers", "LVG", "Western", "Pacific"),
    ("Phoenix",       "Scorpions",    "PHX", "Western", "Pacific"),
]


# How many players of each position a 53-man roster carries.
# Based on typical NFL roster construction (9 OL, 9 DL, 7 LB, 9 DB, 3 specialists).
ROSTER_TEMPLATE = {
    "QB": 3, "RB": 3, "FB": 1, "TE": 3, "WR": 6,
    "T": 4, "G": 3, "C": 2,
    "DE": 5, "DT": 4, "OLB": 4, "ILB": 3,
    "CB": 5, "S": 4,
    "K": 1, "P": 1, "LS": 1,
}

# How many at each position start: 11 on offense (1 RB, 1 TE, 3 WR, the most
# common modern grouping) and 11 on a base 4-3 defense, plus K and P.
# Real depth charts and formations come in a later step.
STARTERS = {
    "QB": 1, "RB": 1, "FB": 0, "TE": 1, "WR": 3,
    "T": 2, "G": 2, "C": 1,
    "DE": 2, "DT": 2, "OLB": 2, "ILB": 1,
    "CB": 2, "S": 2,
    "K": 1, "P": 1, "LS": 1,
}

ROSTER_SIZE = sum(ROSTER_TEMPLATE.values())   # 53


def make_teams():
    return [Team(i + 1, *row) for i, row in enumerate(TEAM_LIST)]
