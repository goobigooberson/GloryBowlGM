# weather.py
# Game-day weather for each home stadium, and how it affects play.
#
# Climate numbers are typical afternoon highs (°F), the chance of rain or
# snow on a given game day, and average wind, by month. They're rough
# real-world averages for each city, not exact records.

import random
from dataclasses import dataclass
from datetime import date, timedelta

# Roof: "dome" (always indoors), "retractable" (closed in bad weather),
# "outdoor". Home cities are the fictional teams' cities in teams.py.
STADIUMS = {
    # abbrev: (roof, {month: (avg high F, precip chance, avg wind mph)})
    "BOS": ("outdoor", {9: (73, .22, 11), 10: (62, .25, 12), 11: (52, .27, 13), 12: (41, .28, 13), 1: (37, .28, 14)}),
    "NYK": ("outdoor", {9: (76, .22, 10), 10: (65, .22, 11), 11: (54, .25, 12), 12: (43, .27, 12), 1: (39, .27, 13)}),
    "PHI": ("outdoor", {9: (78, .22, 9), 10: (67, .22, 10), 11: (56, .25, 11), 12: (45, .27, 11), 1: (41, .27, 12)}),
    "BUF": ("outdoor", {9: (71, .30, 11), 10: (59, .35, 13), 11: (48, .45, 14), 12: (37, .55, 14), 1: (32, .55, 15)}),
    "BAL": ("outdoor", {9: (79, .22, 8), 10: (68, .22, 9), 11: (57, .24, 10), 12: (46, .26, 10), 1: (42, .26, 11)}),
    "WAS": ("outdoor", {9: (80, .22, 8), 10: (69, .22, 9), 11: (58, .24, 9), 12: (47, .26, 10), 1: (44, .26, 10)}),
    "PIT": ("outdoor", {9: (75, .27, 8), 10: (63, .28, 9), 11: (51, .33, 10), 12: (40, .40, 11), 1: (36, .40, 11)}),
    "CIN": ("outdoor", {9: (79, .25, 7), 10: (67, .27, 8), 11: (55, .30, 9), 12: (44, .33, 10), 1: (39, .33, 10)}),
    "CLE": ("outdoor", {9: (74, .27, 10), 10: (63, .30, 12), 11: (51, .38, 13), 12: (40, .45, 13), 1: (35, .45, 14)}),
    "DET": ("dome", {}),
    "CHI": ("outdoor", {9: (75, .25, 10), 10: (63, .27, 12), 11: (49, .30, 13), 12: (36, .33, 13), 1: (31, .33, 13)}),
    "IND": ("retractable", {9: (78, .25, 8), 10: (66, .27, 9), 11: (53, .30, 10), 12: (41, .33, 11), 1: (37, .33, 11)}),
    "CHA": ("outdoor", {9: (82, .20, 6), 10: (72, .18, 6), 11: (62, .20, 7), 12: (53, .22, 7), 1: (51, .22, 7)}),
    "ATL": ("retractable", {}),
    "MIA": ("outdoor", {9: (89, .40, 9), 10: (86, .30, 10), 11: (80, .18, 10), 12: (77, .15, 10), 1: (76, .15, 10)}),
    "TAM": ("outdoor", {9: (90, .35, 8), 10: (85, .20, 8), 11: (78, .13, 8), 12: (73, .13, 8), 1: (71, .13, 9)}),
    "MIN": ("dome", {}),
    "KCY": ("outdoor", {9: (79, .22, 10), 10: (67, .22, 11), 11: (54, .20, 11), 12: (42, .22, 11), 1: (38, .22, 11)}),
    "STL": ("dome", {}),
    "NSH": ("outdoor", {9: (84, .20, 6), 10: (73, .20, 7), 11: (61, .25, 8), 12: (51, .28, 8), 1: (48, .28, 9)}),
    "HOU": ("retractable", {}),
    "DAL": ("retractable", {}),
    "SAN": ("dome", {}),
    "NOR": ("dome", {}),
    "SEA": ("outdoor", {9: (70, .18, 7), 10: (60, .40, 8), 11: (51, .55, 9), 12: (45, .55, 9), 1: (48, .55, 9)}),
    "POR": ("outdoor", {9: (75, .15, 6), 10: (63, .38, 7), 11: (52, .55, 8), 12: (45, .55, 8), 1: (47, .55, 8)}),
    "SFO": ("outdoor", {9: (80, .03, 10), 10: (75, .08, 9), 11: (65, .20, 8), 12: (58, .28, 8), 1: (59, .30, 8)}),
    "DEN": ("outdoor", {9: (79, .12, 9), 10: (66, .15, 9), 11: (52, .18, 9), 12: (43, .18, 9), 1: (45, .18, 9)}),
    "LAS": ("dome", {}),
    "SDG": ("outdoor", {9: (76, .03, 7), 10: (74, .05, 7), 11: (70, .10, 6), 12: (66, .15, 6), 1: (66, .17, 6)}),
    "LVG": ("dome", {}),
    "PHX": ("retractable", {}),
}

SEASON_OPENER = (9, 10)   # week 1 kicks off around September 10


@dataclass
class Weather:
    indoors: bool
    temp: int = 70          # °F
    wind: int = 0           # mph
    precip: str = "none"    # none, rain, snow
    roof: str = "outdoor"

    def text(self):
        if self.indoors:
            return "Dome" if self.roof == "dome" else "Roof closed"
        sky = {"none": "Clear", "rain": "Rain", "snow": "Snow"}[self.precip]
        if self.precip == "none" and self.temp < 40:
            sky = "Cold"
        return f"{sky}, {self.temp}°F, wind {self.wind} mph"

    # ---- effects (all small; football is mostly played in normal weather) ----
    def pass_logit(self, air_yards):
        """Change to completion odds for a throw of this depth."""
        if self.indoors:
            return 0.0
        e = 0.0
        if self.wind > 10:
            e -= 0.006 * (self.wind - 10) * (1.0 + max(0, air_yards) / 15)
        if self.precip == "rain":
            e -= 0.10
        elif self.precip == "snow":
            e -= 0.16
        if self.temp < 25:
            e -= 0.05
        return e

    def fumble_mult(self):
        if self.indoors:
            return 1.0
        m = {"none": 1.0, "rain": 1.35, "snow": 1.45}[self.precip]
        return m * (1.12 if self.temp < 25 else 1.0)

    def fg_logit(self, distance):
        if self.indoors:
            return 0.0
        e = 0.0
        if self.wind > 8:
            e -= 0.0025 * (self.wind - 8) * max(0, distance - 25)
        if self.temp < 32:
            e -= 0.25
        if self.precip == "rain":
            e -= 0.15
        elif self.precip == "snow":
            e -= 0.25
        return e

    def fg_range_loss(self):
        """Yards of range lost to wind and cold."""
        if self.indoors:
            return 0
        return max(0, (self.wind - 10) // 3) + (3 if self.temp < 32 else 0)

    def punt_yards(self):
        if self.indoors:
            return 0.0
        return -0.15 * max(0, self.wind - 10) - (2.0 if self.temp < 30 else 0.0)


def game_date(season, week):
    start = date(season, *SEASON_OPENER)
    return start + timedelta(days=7 * (week - 1))


def generate(home_abbrev, season=2026, week=1, rng=random):
    roof, climate = STADIUMS.get(home_abbrev, ("outdoor", {}))
    if roof == "dome":
        return Weather(indoors=True, roof="dome")
    month = game_date(season, week).month
    if month == 8 and climate and 8 not in climate:
        # Preseason games in August: September's weather, a few degrees warmer.
        h, p, w = climate[9]
        climate = {8: (h + 4, p, w)}
    avg_high, precip_chance, avg_wind = climate.get(month, (65, 0.2, 8)) if climate else (75, 0.1, 6)
    temp = round(rng.gauss(avg_high - 2, 7))
    wind = max(0, round(rng.gammavariate(2.2, avg_wind / 2.2)))
    precip = "none"
    if rng.random() < precip_chance * 0.7:      # not every wet day rains during the game
        precip = "snow" if temp <= 33 else "rain"
    if roof == "retractable":
        if precip != "none" or temp < 50 or temp > 88:
            return Weather(indoors=True, roof="retractable")
        return Weather(indoors=False, temp=temp, wind=min(wind, 8), precip="none", roof="retractable")
    return Weather(indoors=False, temp=temp, wind=wind, precip=precip, roof="outdoor")
