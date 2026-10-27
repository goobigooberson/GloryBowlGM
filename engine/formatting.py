# formatting.py
# Turns raw numbers into the way football fans expect to read them.
# Every screen in the game should use these, so the formats stay consistent.


def height(inches):
    """74 -> '6-2'"""
    return f"{inches // 12}-{inches % 12}"


def weight(lbs):
    """215 -> '215 lbs'"""
    return f"{lbs} lbs"


def size(inches, lbs):
    """(74, 215) -> '6-2, 215 lbs'"""
    return f"{height(inches)}, {weight(lbs)}"


def seconds(value):
    """4.523 -> '4.52 sec'"""
    return f"{value:.2f} sec"


def reps(value):
    """23 -> '23 reps'"""
    return f"{value} reps"


def jump(inches):
    """Broad jump. 117 -> '9 ft 9 in'"""
    return f"{inches // 12} ft {inches % 12} in"


def vertical(inches):
    """35.5 -> '35.5 in'"""
    return f"{inches:g} in"


NOT_TESTED = "Did not test"

# How each combine drill is labeled and displayed.
DRILL_LABELS = {
    "forty":    ("40-yard dash", seconds),
    "bench":    ("Bench press (225 lbs)", reps),
    "vertical": ("Vertical jump", vertical),
    "broad":    ("Broad jump", jump),
    "cone":     ("3-cone drill", seconds),
    "shuttle":  ("20-yard shuttle", seconds),
}


def drill(name, value):
    """('forty', 4.52) -> '4.52 sec'; a skipped drill -> 'Did not test'"""
    if value is None:
        return NOT_TESTED
    return DRILL_LABELS[name][1](value)


# ---------------------------------------------------------------------------
# Word scales. Each list: (lowest number that earns the word, word).
# ---------------------------------------------------------------------------

# For skill ratings and overall: how good he is.
SKILL_WORDS = [
    (90, "Elite"),
    (80, "Very Good"),
    (65, "Good"),
    (45, "Average"),
    (30, "Bad"),
    (15, "Very Bad"),
    (0,  "Atrocious"),
]

# For personality traits, where high isn't always good (high volatility is
# risky, high loyalty is neither good nor bad). Same cutoffs, neutral words.
TRAIT_WORDS = [
    (90, "Extremely High"),
    (80, "Very High"),
    (65, "High"),
    (45, "Average"),
    (30, "Low"),
    (15, "Very Low"),
    (0,  "Extremely Low"),
]


def _word(value, scale):
    for floor, word in scale:
        if value >= floor:
            return word
    return scale[-1][1]


def skill_word(value):
    return _word(value, SKILL_WORDS)


def skill(value):
    """87 -> 'Very Good (87)'"""
    return f"{skill_word(value)} ({value})"


def trait(value):
    """87 -> 'Very High (87)'"""
    return f"{_word(value, TRAIT_WORDS)} ({value})"


def bar(current, potential, width=20):
    """A text bar: '#' is current ability, '+' is room left to grow.
    Example: [##########++++......]"""
    filled = round(current / 100 * width)
    grow = max(0, round(potential / 100 * width) - filled)
    empty = width - filled - grow
    return "[" + "#" * filled + "+" * grow + "." * empty + "]"


# ---------------------------------------------------------------------------
# Money (team finances, Oct 26): the way the sports pages print it.
# ---------------------------------------------------------------------------

def money(k):
    """$K -> '$72.6M', '$885K', '-$1.2M', '$1.17B'."""
    sign = "-" if k < 0 else ""
    k = abs(k)
    if k >= 999_500:
        return f"{sign}${k / 1_000_000:.2f}B" if k < 99_995_000 else f"{sign}${k / 1_000_000:.0f}B"
    if k >= 1000:
        m = k / 1000
        return f"{sign}${m:.1f}M" if m < 100 else f"{sign}${m:.0f}M"
    return f"{sign}${round(k)}K"


def price(dollars):
    """158.4 -> '$158'; a suite's season price in $K goes through money()."""
    return f"${round(dollars):,}"


def crowd(n):
    """68412 -> '68,412'"""
    return f"{round(n):,}" if n is not None else "-"


def share(x, digits=0):
    """0.973 -> '97%'"""
    return f"{x * 100:.{digits}f}%" if x is not None else "-"
