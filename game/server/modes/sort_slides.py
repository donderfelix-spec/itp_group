"""The minigame of the Lecture Hall, station 1: "Sort the slides".

Five slides lie shuffled in a pile; the player drags them into the order of
a presentation (DESIGN.md, section 8, row 1). The server only shuffles the
pile; the browser plays it (S-19).

The right order is sent along. It is no secret: everyone may know how a
presentation is built.
"""

from server.modes.minigame import Minigame

# The slides in the right order, from DESIGN.md, section 8.
RIGHT_ORDER = ("Title", "Agenda", "Analysis", "Results", "Q&A")

# How often the pile is shuffled again if it comes out already sorted.
# One try is sorted with a chance of 1 in 120, so five are plenty.
SHUFFLE_TRIES = 5


def move_first_to_end(slides: list) -> list:
    """The same slides with the first one moved to the end: never the sorted order."""
    return slides[1:] + slides[:1]


def shuffled_pile(rng) -> list:
    """The five slides in a shuffled order that is never the right order.

    The number of tries is fixed, so this ends even with a random generator
    that keeps giving the sorted order. Then a fixed unsorted order is used.
    """
    for _ in range(SHUFFLE_TRIES):
        slides = list(RIGHT_ORDER)
        rng.shuffle(slides)
        if slides != list(RIGHT_ORDER):
            return slides
    return move_first_to_end(list(RIGHT_ORDER))


def make_content(rng) -> dict:
    """What the browser needs: the right order and the shuffled pile."""
    return {"kind": "sort_slides", "order": list(RIGHT_ORDER), "slides": shuffled_pile(rng)}


# Stops a script that reports "done" at once; a quick, correct player is
# not punished (S-93).
MINIGAME = Minigame(title="Sort the slides", min_seconds=1, make_content=make_content)
