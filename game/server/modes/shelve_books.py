"""Minigame of station 4, CTT Student Hall: "Shelve the books" (DESIGN.md, section 8).

Six numbered books lie mixed up on a table. The player clicks them onto the
shelf, lowest number first. The server only draws the numbers and the order
they lie in; the browser plays the minigame (S-19). The numbers themselves
are no secret: the player sees them all and sorts them.
"""

from server.modes.minigame import Minigame

BOOK_COUNT = 6
# Shelf numbers like the ones on the spine of a library book: three digits.
LOWEST_NUMBER = 100
HIGHEST_NUMBER = 999
# How often the books are mixed again if they came out already sorted.
SHUFFLE_TRIES = 5
# Nobody reads six numbers and clicks six books in less time than this.
MIN_SECONDS = 3


def is_ascending(numbers: list) -> bool:
    return numbers == sorted(numbers)


def mix(books: list, rng) -> list:
    """The books in a mixed order that is never the solution itself.

    A shuffle can leave the books sorted by chance. Then it is tried again a
    few times, and if luck stays that bad the books are laid out backwards,
    so this function always ends.
    """
    mixed = list(books)
    for _ in range(SHUFFLE_TRIES):
        rng.shuffle(mixed)
        if not is_ascending(mixed):
            return mixed
    return sorted(mixed, reverse=True)


def make_content(rng) -> dict:
    """Six different shelf numbers, in the order the books lie on the table."""
    numbers = rng.sample(range(LOWEST_NUMBER, HIGHEST_NUMBER + 1), BOOK_COUNT)
    return {"kind": "shelve_books", "books": mix(numbers, rng)}


MINIGAME = Minigame(title="Shelve the books", min_seconds=MIN_SECONDS, make_content=make_content)
