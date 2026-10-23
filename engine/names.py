# names.py
# Lists used to make fictional players feel real.

from .name_data import ELDER_FIRST_COUNTS, FIRST_COUNTS, LAST_COUNTS

# The name pool comes from real NFL rosters 1999-2025 (name_data.py, made by
# tools/make_names.py; Blake, Oct 22: "massively expand the name pool to be very large and
# varied"): about 4,000 first names and 6,800 last names, each listed as many times as real
# players had it, so random.choice() draws them as often as a real locker room has them
# (Chris and Michael common, Ja'Marr rare). Before: 163 first and 175 last names.
FIRST_NAMES = [name for name, n in FIRST_COUNTS.items() for _ in range(n)]
LAST_NAMES = [name for name, n in LAST_COUNTS.items() for _ in range(n)]
# Coaches, GMs and other grown-ups: first names of players who entered before 2008.
ELDER_FIRST_NAMES = [name for name, n in ELDER_FIRST_COUNTS.items() for _ in range(n)]


def person(rng):
    """(first, last) for a made-up player, drawn like the real pool (now and then that's a
    real player's full name, as with real people: Blake, Oct 22)."""
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def elder(rng):
    """(first, last) for a coach, GM or other grown-up (an older generation's first names)."""
    return rng.choice(ELDER_FIRST_NAMES), rng.choice(LAST_NAMES)


# Colleges now live in colleges.py, built from real draft history.

HOMETOWNS = [
    "Atlanta, GA", "Austin, TX", "Baltimore, MD", "Baton Rouge, LA", "Birmingham, AL",
    "Boise, ID", "Charlotte, NC", "Chicago, IL", "Cincinnati, OH", "Cleveland, OH",
    "Columbia, SC", "Columbus, OH", "Dallas, TX", "Denver, CO", "Des Moines, IA",
    "Detroit, MI", "Durham, NC", "El Paso, TX", "Fayetteville, NC", "Fort Worth, TX",
    "Fresno, CA", "Gainesville, FL", "Greenville, SC", "Houston, TX", "Indianapolis, IN",
    "Jackson, MS", "Jacksonville, FL", "Kansas City, MO", "Knoxville, TN",
    "Las Vegas, NV", "Little Rock, AR", "Los Angeles, CA", "Louisville, KY",
    "Memphis, TN", "Miami, FL", "Milwaukee, WI", "Minneapolis, MN", "Mobile, AL",
    "Nashville, TN", "New Orleans, LA", "Newark, NJ", "Norfolk, VA", "Oakland, CA",
    "Oklahoma City, OK", "Omaha, NE", "Orlando, FL", "Philadelphia, PA",
    "Phoenix, AZ", "Pittsburgh, PA", "Portland, OR", "Raleigh, NC", "Richmond, VA",
    "Sacramento, CA", "Salt Lake City, UT", "San Antonio, TX", "San Diego, CA",
    "Savannah, GA", "Seattle, WA", "Shreveport, LA", "St. Louis, MO", "Tampa, FL",
    "Toledo, OH", "Tucson, AZ", "Tulsa, OK", "Wichita, KS", "Wilmington, NC",
]
