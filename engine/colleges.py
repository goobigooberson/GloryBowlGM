# colleges.py
# Which schools players come from, based on REAL NFL draft history.
#
# Source: every NFL draft pick 2012-2026 (nflverse open dataset,
# github.com/nflverse/nflverse-data). Each school lists how many players it
# had drafted in rounds 1 through 7 over those 15 drafts.
#
# The game uses these counts as odds: a first-round talent is very likely to
# come from a school that produces first-rounders (Alabama, Ohio State,
# Georgia...), while a seventh-rounder or undrafted player could come from
# almost anywhere. A small-school first-rounder still happens, about as
# often as it does in real life (roughly 1 in 40 first-round picks).
#
# Generated from the data; don't edit by hand unless you mean to.

#  school: (round 1, round 2, round 3, round 4, round 5, round 6, round 7)
DRAFT_COUNTS = {
    'Alabama': (44, 25, 15, 14, 16, 10, 10),
    'Ohio State': (32, 21, 20, 13, 10, 9, 9),
    'Georgia': (25, 14, 17, 14, 16, 14, 11),
    'LSU': (21, 19, 18, 14, 8, 15, 12),
    'Michigan': (14, 11, 20, 9, 12, 13, 11),
    'Florida': (16, 11, 10, 15, 16, 11, 7),
    'Clemson': (19, 11, 9, 14, 14, 7, 6),
    'Notre Dame': (13, 15, 12, 8, 12, 11, 6),
    'Oklahoma': (8, 11, 10, 20, 6, 10, 12),
    'Penn State': (9, 15, 9, 11, 12, 12, 9),
    'Miami (FL)': (10, 3, 10, 11, 12, 14, 12),
    'Florida State': (11, 15, 6, 10, 9, 9, 7),
    'Oregon': (14, 6, 8, 10, 9, 11, 9),
    'Texas': (8, 8, 10, 9, 11, 10, 6),
    'Texas A&M': (11, 10, 12, 10, 7, 8, 4),
    'USC': (12, 9, 11, 10, 5, 6, 7),
    'Auburn': (5, 6, 9, 11, 11, 10, 5),
    'Washington': (12, 15, 4, 8, 8, 5, 5),
    'Iowa': (8, 6, 9, 11, 9, 4, 9),
    'South Carolina': (7, 8, 4, 9, 7, 8, 11),
    'UCLA': (7, 6, 7, 7, 12, 7, 7),
    'Stanford': (6, 7, 11, 8, 9, 8, 3),
    'Wisconsin': (5, 6, 7, 10, 10, 6, 5),
    'Ole Miss': (6, 11, 4, 5, 5, 7, 9),
    'Arkansas': (2, 1, 9, 8, 8, 12, 6),
    'Utah': (6, 6, 7, 8, 5, 6, 6),
    'Missouri': (5, 10, 5, 7, 6, 5, 5),
    'Tennessee': (5, 5, 11, 7, 3, 10, 2),
    'TCU': (6, 6, 6, 6, 5, 7, 6),
    'Mississippi State': (6, 7, 6, 4, 3, 9, 6),
    'North Carolina': (7, 4, 7, 8, 7, 1, 7),
    'Kentucky': (4, 5, 6, 6, 4, 8, 4),
    'Michigan State': (3, 5, 2, 10, 2, 10, 5),
    'NC State': (3, 3, 9, 7, 5, 2, 8),
    'Louisville': (8, 2, 8, 4, 3, 7, 4),
    'Pittsburgh': (3, 2, 3, 9, 7, 6, 6),
    'Virginia Tech': (6, 0, 4, 4, 4, 15, 3),
    'Baylor': (3, 4, 5, 4, 2, 10, 7),
    'California': (1, 2, 6, 7, 5, 3, 10),
    'Boston College': (4, 4, 7, 3, 2, 7, 6),
    'Cincinnati': (1, 5, 6, 6, 5, 3, 7),
    'Maryland': (3, 1, 6, 5, 7, 4, 6),
    'Illinois': (3, 6, 9, 1, 3, 5, 4),
    'West Virginia': (4, 2, 8, 5, 8, 3, 1),
    'Arizona State': (5, 1, 3, 8, 4, 4, 5),
    'Boise State': (4, 4, 4, 2, 7, 7, 2),
    'Nebraska': (0, 6, 3, 3, 4, 7, 7),
    'Minnesota': (1, 7, 2, 5, 8, 1, 5),
    'Texas Tech': (4, 3, 4, 4, 3, 4, 7),
    'Kansas State': (1, 5, 4, 1, 4, 6, 7),
    'Oklahoma State': (3, 3, 2, 4, 3, 6, 7),
    'UCF': (4, 3, 5, 4, 2, 4, 3),
    'Houston': (4, 3, 3, 3, 2, 4, 5),
    'Oregon State': (2, 1, 7, 1, 5, 4, 4),
    'Purdue': (1, 2, 1, 4, 9, 2, 5),
    'Arizona': (2, 2, 1, 3, 4, 6, 5),
    'Indiana': (2, 3, 3, 4, 4, 4, 3),
    'Rutgers': (0, 2, 5, 1, 1, 5, 9),
    'San Diego State': (2, 1, 4, 6, 3, 4, 3),
    'Wake Forest': (1, 2, 1, 6, 4, 6, 3),
    'Iowa State': (1, 3, 4, 6, 2, 1, 3),
    'Syracuse': (2, 1, 4, 2, 3, 2, 6),
    'Colorado': (1, 4, 2, 2, 2, 5, 3),
    'Georgia Tech': (1, 4, 0, 2, 1, 6, 5),
    'Northwestern': (3, 0, 1, 3, 5, 1, 6),
    'SMU': (0, 3, 3, 2, 2, 4, 5),
    'Temple': (1, 2, 2, 2, 6, 2, 4),
    'BYU': (2, 2, 4, 2, 3, 1, 4),
    'Memphis': (2, 1, 3, 3, 4, 0, 5),
    'Virginia': (0, 1, 4, 1, 6, 5, 1),
    'Washington State': (2, 0, 4, 2, 4, 3, 3),
    'Connecticut': (1, 2, 6, 2, 0, 4, 2),
    'Tulane': (0, 0, 3, 1, 3, 4, 6),
    'Vanderbilt': (0, 6, 1, 0, 3, 1, 5),
    'Duke': (3, 0, 1, 4, 4, 2, 1),
    'Louisiana': (0, 1, 2, 4, 1, 4, 3),
    'Louisiana Tech': (1, 0, 3, 5, 2, 4, 0),
    'North Dakota State': (3, 3, 1, 2, 4, 1, 1),
    'Western Kentucky': (0, 1, 5, 3, 2, 1, 3),
    'Western Michigan': (1, 4, 1, 1, 2, 2, 4),
    'Kansas': (0, 0, 1, 1, 4, 6, 1),
    'Toledo': (1, 1, 3, 1, 2, 1, 4),
    'Utah State': (1, 1, 3, 4, 0, 1, 3),
    'Fresno State': (0, 2, 0, 4, 2, 4, 0),
    'Appalachian State': (0, 1, 1, 1, 5, 1, 2),
    'Colorado State': (0, 3, 3, 0, 3, 1, 1),
    'Marshall': (0, 3, 0, 1, 2, 2, 3),
    'Nevada': (0, 2, 0, 3, 2, 2, 2),
    'South Florida': (0, 0, 2, 1, 3, 2, 3),
    'Southern Miss': (0, 1, 3, 1, 0, 5, 1),
    'Central Michigan': (1, 2, 1, 0, 1, 3, 2),
    'Wyoming': (1, 0, 2, 1, 1, 4, 1),
    'San Jose State': (0, 0, 1, 2, 1, 3, 2),
    'Florida Atlantic': (0, 0, 3, 1, 1, 1, 2),
    'Coastal Carolina': (0, 0, 0, 2, 1, 3, 1),
    'FIU': (0, 1, 2, 1, 0, 1, 2),
    'Georgia Southern': (0, 0, 2, 0, 3, 1, 1),
    'Miami (OH)': (0, 1, 1, 0, 2, 0, 3),
    'Northern Illinois': (1, 1, 1, 0, 0, 1, 3),
    'Northern Iowa': (1, 0, 2, 2, 1, 1, 0),
    'South Dakota State': (0, 1, 1, 2, 1, 0, 2),
    'UAB': (0, 0, 1, 1, 1, 3, 1),
    'Buffalo': (1, 0, 1, 0, 1, 1, 2),
    'Massachusetts': (0, 1, 0, 0, 1, 1, 3),
    'Navy': (0, 0, 0, 0, 1, 2, 3),
    'Ohio': (0, 0, 1, 0, 1, 1, 3),
    'Rice': (0, 1, 2, 0, 1, 1, 1),
    'Central Arkansas': (0, 0, 0, 2, 0, 1, 2),
    'Charlotte': (0, 0, 3, 1, 0, 0, 1),
    'East Carolina': (0, 1, 1, 2, 0, 0, 1),
    'Eastern Michigan': (0, 0, 0, 2, 0, 2, 1),
    'Georgia State': (0, 0, 1, 0, 0, 3, 1),
    'Hawaii': (0, 1, 0, 0, 0, 0, 4),
    'Montana': (0, 0, 1, 0, 1, 1, 2),
    'Old Dominion': (0, 0, 1, 1, 0, 2, 1),
    'Samford': (0, 2, 0, 0, 2, 0, 1),
    'South Carolina State': (0, 1, 1, 2, 0, 1, 0),
    'Tennessee State': (0, 0, 0, 0, 2, 0, 3),
    'Troy': (0, 0, 1, 1, 2, 1, 0),
    'Tulsa': (2, 0, 0, 1, 1, 0, 1),
    'UTSA': (1, 0, 0, 1, 2, 1, 0),
    'William & Mary': (0, 0, 1, 1, 1, 1, 1),
    'Ball State': (0, 0, 0, 0, 2, 1, 1),
    'Bowling Green': (0, 0, 1, 0, 0, 3, 0),
    'Chattanooga': (1, 0, 0, 0, 1, 1, 1),
    'Delaware': (0, 1, 0, 1, 2, 0, 0),
    'Eastern Washington': (0, 0, 1, 2, 0, 0, 1),
    'Illinois State': (0, 0, 0, 0, 2, 1, 1),
    'Liberty': (0, 0, 1, 2, 0, 1, 0),
    'Maine': (0, 0, 0, 1, 0, 2, 1),
    'Middle Tennessee': (0, 0, 1, 0, 1, 0, 2),
    'Montana State': (0, 1, 0, 0, 0, 1, 2),
    'New Mexico State': (0, 0, 0, 1, 1, 1, 1),
    'Princeton': (0, 0, 0, 1, 1, 1, 1),
    'South Alabama': (0, 1, 1, 0, 1, 0, 1),
    'Southern Utah': (0, 0, 0, 1, 2, 0, 1),
    'UTEP': (0, 1, 0, 1, 1, 1, 0),
    'Air Force': (0, 0, 0, 0, 0, 1, 2),
    'Arkansas State': (0, 0, 1, 0, 1, 0, 1),
    'James Madison': (0, 0, 0, 1, 0, 0, 2),
    'New Mexico': (0, 0, 0, 0, 0, 1, 2),
    'North Carolina A&T': (0, 0, 1, 1, 0, 0, 1),
    'Sam Houston State': (0, 1, 0, 0, 1, 0, 1),
    'South Dakota': (0, 0, 0, 0, 0, 1, 2),
    'Southeast Missouri State': (0, 0, 0, 0, 0, 2, 1),
    'Southeastern Louisiana': (0, 1, 0, 1, 0, 1, 0),
    'Stephen F. Austin': (0, 0, 0, 1, 2, 0, 0),
    'Valdosta State': (0, 0, 0, 1, 0, 0, 2),
    'Villanova': (0, 1, 0, 0, 0, 1, 1),
    'Yale': (0, 0, 1, 0, 0, 1, 1),
    'Youngstown State': (0, 0, 1, 0, 1, 1, 0),
    'Akron': (0, 0, 0, 0, 1, 1, 0),
    'Alabama State': (1, 0, 0, 0, 0, 0, 1),
    'Ashland': (0, 1, 0, 0, 0, 0, 1),
    'Charleston (WV)': (0, 0, 0, 1, 0, 0, 1),
    'Concordia-St. Paul': (0, 0, 0, 0, 0, 1, 1),
    'East Central': (0, 0, 0, 0, 0, 0, 2),
    'Eastern Illinois': (0, 1, 0, 0, 0, 1, 0),
    'Eastern Kentucky': (0, 1, 0, 0, 0, 0, 1),
    'Elon': (0, 0, 0, 0, 0, 1, 1),
    'Fordham': (0, 0, 0, 1, 0, 1, 0),
    'Grand Valley State': (0, 0, 0, 0, 1, 0, 1),
    'Harvard': (0, 0, 0, 1, 1, 0, 0),
    'Idaho': (0, 0, 0, 0, 1, 0, 1),
    'Jackson State': (0, 0, 0, 0, 0, 1, 1),
    'Jacksonville State': (0, 0, 0, 0, 1, 1, 0),
    'Kent State': (0, 0, 2, 0, 0, 0, 0),
    'Lenoir-Rhyne': (0, 1, 0, 0, 0, 0, 1),
    'Louisiana-Monroe': (0, 0, 0, 0, 1, 1, 0),
    'Midwestern State': (0, 1, 0, 0, 1, 0, 0),
    'Missouri Western State': (0, 0, 0, 0, 0, 1, 1),
    'Murray State': (0, 0, 1, 0, 0, 1, 0),
    'New Hampshire': (0, 0, 0, 0, 0, 1, 1),
    'Northwest Missouri State': (0, 0, 0, 0, 0, 2, 0),
    'Northwestern State': (0, 0, 0, 0, 0, 1, 1),
    'Richmond': (0, 0, 0, 1, 1, 0, 0),
    'Sacramento State': (0, 0, 1, 0, 1, 0, 0),
    'Southern Illinois': (0, 1, 0, 0, 1, 0, 0),
    'Tarleton State': (0, 0, 0, 0, 1, 1, 0),
    'Texas State': (0, 0, 1, 0, 1, 0, 0),
    'Towson': (0, 0, 1, 0, 1, 0, 0),
    'UT Martin': (0, 0, 0, 0, 1, 0, 1),
    'Wagner': (0, 0, 0, 0, 0, 2, 0),
    'Washburn': (0, 0, 0, 0, 0, 1, 1),
    'West Georgia': (0, 0, 0, 0, 1, 1, 0),
    'Abilene Christian': (0, 0, 0, 0, 0, 0, 1),
    'Alabama A&M': (0, 0, 0, 0, 1, 0, 0),
    'Albany State': (0, 0, 0, 1, 0, 0, 0),
    'Albion': (0, 0, 0, 0, 1, 0, 0),
    'Arkansas-Pine Bluff': (0, 0, 1, 0, 0, 0, 0),
    'Bloomsburg': (0, 0, 0, 1, 0, 0, 0),
    'British Columbia': (0, 0, 0, 1, 0, 0, 0),
    'Bucknell': (0, 0, 0, 1, 0, 0, 0),
    'Cal (PA)': (0, 0, 0, 0, 0, 1, 0),
    'Cal Poly': (0, 0, 0, 0, 1, 0, 0),
    'Central Missouri State': (0, 0, 0, 0, 1, 0, 0),
    'Chadron State': (0, 0, 0, 0, 0, 0, 1),
    'Colorado State-Pueblo': (0, 0, 0, 0, 0, 1, 0),
    'Cornell': (0, 0, 0, 1, 0, 0, 0),
    'Dayton': (0, 0, 1, 0, 0, 0, 0),
    'Delaware State': (0, 0, 0, 1, 0, 0, 0),
    'Drake': (0, 0, 0, 0, 1, 0, 0),
    'East Texas A&M': (0, 0, 0, 0, 0, 0, 1),
    'Fayetteville State': (0, 0, 0, 1, 0, 0, 0),
    'Ferris State': (0, 0, 0, 0, 0, 0, 1),
    'Findlay': (0, 0, 0, 0, 0, 1, 0),
    'Florida A&M': (0, 0, 0, 0, 0, 0, 1),
    'Fort Hays State': (0, 0, 1, 0, 0, 0, 0),
    'Furman': (0, 0, 0, 1, 0, 0, 0),
    'Grambling State': (0, 0, 1, 0, 0, 0, 0),
    'Harding': (0, 0, 0, 0, 0, 0, 1),
    'Hobart': (0, 1, 0, 0, 0, 0, 0),
    'Holy Cross': (0, 0, 0, 0, 0, 0, 1),
    'Houston Christian': (0, 0, 1, 0, 0, 0, 0),
    'Humboldt State': (0, 0, 1, 0, 0, 0, 0),
    'Kennesaw State': (0, 0, 0, 0, 0, 0, 1),
    'Kutztown': (0, 0, 0, 0, 1, 0, 0),
    'Lamar': (0, 0, 1, 0, 0, 0, 0),
    'Lindenwood': (0, 0, 0, 1, 0, 0, 0),
    'Manitoba': (0, 0, 0, 1, 0, 0, 0),
    'Marist': (0, 0, 0, 0, 0, 0, 1),
    'Mars Hill': (0, 0, 0, 0, 0, 0, 1),
    'McGill': (0, 0, 0, 0, 0, 1, 0),
    'Missouri Southern': (0, 0, 1, 0, 0, 0, 0),
    'Missouri State': (0, 0, 0, 0, 1, 0, 0),
    'Monmouth': (0, 0, 0, 0, 0, 0, 1),
    'Morgan State': (0, 0, 0, 0, 0, 0, 1),
    'Newberry': (0, 0, 0, 0, 0, 0, 1),
    'North Alabama': (0, 1, 0, 0, 0, 0, 0),
    'North Carolina Central': (0, 0, 0, 1, 0, 0, 0),
    'North Dakota': (0, 0, 0, 0, 1, 0, 0),
    'North Texas': (0, 0, 0, 1, 0, 0, 0),
    'Northeastern State': (0, 0, 0, 0, 0, 0, 1),
    'Northern Michigan': (0, 0, 0, 0, 0, 0, 1),
    'Ouachita Baptist': (0, 0, 0, 0, 0, 1, 0),
    'Pennsylvania': (0, 0, 0, 0, 1, 0, 0),
    'Pittsburg State': (0, 0, 1, 0, 0, 0, 0),
    'Portland State': (0, 0, 0, 0, 0, 0, 1),
    'Prairie View A&M': (0, 0, 0, 0, 0, 0, 1),
    'Presbyterian': (0, 0, 0, 0, 0, 1, 0),
    'Regina': (0, 0, 1, 0, 0, 0, 0),
    'Rhode Island': (0, 0, 0, 0, 1, 0, 0),
    'Saginaw Valley State': (0, 0, 0, 0, 0, 0, 1),
    "Saint John's": (0, 0, 0, 1, 0, 0, 0),
    'San Diego': (0, 0, 0, 0, 1, 0, 0),
    'Sioux Falls': (0, 0, 1, 0, 0, 0, 0),
    'Southern': (0, 0, 0, 0, 0, 0, 1),
    'Texas Southern': (0, 0, 0, 1, 0, 0, 0),
    'UNLV': (0, 0, 0, 0, 0, 0, 1),
    'Virginia State': (0, 0, 0, 0, 0, 1, 0),
    'Weber State': (0, 0, 0, 1, 0, 0, 0),
    'West Alabama': (0, 0, 0, 0, 1, 0, 0),
    'Western Carolina': (0, 0, 0, 0, 0, 0, 1),
    'Western Illinois': (0, 0, 1, 0, 0, 0, 0),
    'Western Oregon': (0, 0, 0, 0, 0, 1, 0),
    'Wingate': (0, 0, 0, 0, 0, 0, 1),
    'Wisconsin-Whitewater': (0, 0, 1, 0, 0, 0, 0),
}

# Share of real NFL roster players by how they entered the league
# (Over The Cap, 2023 roster breakdown). 0 = undrafted.
ROSTER_SHARE_BY_ROUND = {
    1: 14.1, 2: 12.4, 3: 13.2, 4: 10.5, 5: 10.1, 6: 8.6, 7: 6.0, 0: 24.9,
}


# How each position enters the league, from the same 2012-2026 draft data.
#   position: (share of roster players who were drafted at all,
#              (share of that position's picks made in round 1, 2, ... 7))
# Kickers, punters and fullbacks are rarely drafted and never in round 1;
# QBs go in round 1 more than any other position (27% of QB picks).
# The drafted share is an estimate: drafted players per year at the position
# compared with roster spots, scaled so the whole league matches the real
# 75% drafted / 25% undrafted split.
DRAFT_BY_POSITION = {
    "QB": (0.60, (0.272, 0.064, 0.121, 0.133, 0.104, 0.156, 0.15)),
    "RB": (0.95, (0.068, 0.11, 0.129, 0.2, 0.155, 0.174, 0.165)),
    "FB": (0.16, (0.0, 0.0, 0.0, 0.067, 0.133, 0.533, 0.267)),
    "TE": (0.76, (0.064, 0.141, 0.173, 0.168, 0.177, 0.118, 0.159)),
    "WR": (0.84, (0.135, 0.145, 0.148, 0.145, 0.119, 0.164, 0.143)),
    "T": (0.81, (0.172, 0.118, 0.161, 0.116, 0.107, 0.175, 0.152)),
    "G": (0.78, (0.122, 0.103, 0.162, 0.149, 0.135, 0.172, 0.156)),
    "C": (0.63, (0.127, 0.117, 0.164, 0.12, 0.117, 0.177, 0.177)),
    "DE": (0.67, (0.155, 0.13, 0.167, 0.133, 0.149, 0.099, 0.167)),
    "DT": (0.94, (0.136, 0.13, 0.161, 0.136, 0.13, 0.158, 0.15)),
    "OLB": (0.71, (0.114, 0.122, 0.146, 0.141, 0.19, 0.139, 0.148)),
    "ILB": (0.60, (0.106, 0.112, 0.142, 0.151, 0.196, 0.148, 0.145)),
    "CB": (0.81, (0.115, 0.132, 0.142, 0.14, 0.163, 0.154, 0.154)),
    "S": (0.81, (0.096, 0.127, 0.143, 0.147, 0.163, 0.151, 0.173)),
    "K": (0.31, (0.0, 0.033, 0.033, 0.067, 0.267, 0.367, 0.233)),
    "P": (0.30, (0.0, 0.0, 0.034, 0.138, 0.241, 0.31, 0.276)),
    # Long snappers: 9 drafted 2012-2026, all in rounds 5-7. Drafted share is
    # an estimate (very few are drafted, but they last a long time).
    "LS": (0.15, (0.0, 0.0, 0.0, 0.0, 0.111, 0.556, 0.333)),
}


import random

ROUNDS = [1, 2, 3, 4, 5, 6, 7, 0]


def pick_college(draft_round):
    """Choose a school for a player who went in this round (0 = undrafted)."""
    schools = list(DRAFT_COUNTS)
    if draft_round == 1:
        # Only schools that have actually produced first-rounders.
        weights = [DRAFT_COUNTS[s][0] for s in schools]
    elif draft_round in range(2, 8):
        # Small bonus so any school can occasionally produce a mid/late pick.
        weights = [DRAFT_COUNTS[s][draft_round - 1] + 0.1 for s in schools]
    else:
        # Undrafted players: spread widely, small schools much more common.
        # (Estimate: no complete public list of undrafted signings exists.)
        weights = [sum(DRAFT_COUNTS[s][3:]) ** 0.6 + 0.5 for s in schools]
    return random.choices(schools, weights=weights)[0]


def rounds_for_position(position, n_players, n_drafted):
    """Draft rounds for a position group ranked best to worst.
    The top n_drafted were drafted, split across rounds the way real drafts
    split that position; the rest went undrafted."""
    _share, round_shares = DRAFT_BY_POSITION[position]
    # Early picks last longer in the league, so a roster holds more of them
    # than a single draft does. Weight each round by how well its players
    # stick around (real roster share of the round / its 1-in-7 share of picks).
    drafted_total = sum(v for r, v in ROSTER_SHARE_BY_ROUND.items() if r != 0)
    stick = [ROSTER_SHARE_BY_ROUND[r] / drafted_total * 7 for r in range(1, 8)]
    weighted = [share * k for share, k in zip(round_shares, stick)]
    weighted = [w / sum(weighted) for w in weighted]
    rounds = []
    for rnd, share in enumerate(weighted, start=1):
        rounds += [rnd] * round(share * n_drafted)
    rounds = (rounds + [7] * n_drafted)[:n_drafted]   # fix rounding to exact count
    return rounds + [0] * (n_players - n_drafted)


def round_from_percentile(pct):
    """pct: 0.0 = best player in the group, 1.0 = worst.
    Returns the draft round (0 = undrafted) using real roster shares."""
    total = sum(ROSTER_SHARE_BY_ROUND.values())
    running = 0
    for rnd in ROUNDS:
        running += ROSTER_SHARE_BY_ROUND[rnd] / total
        if pct < running:
            return rnd
    return 0
