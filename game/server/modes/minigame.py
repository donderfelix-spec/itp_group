"""What the server knows about one minigame.

The browser plays a minigame; the server does not replay it (S-19). The server
only draws the content (which dishes, which drink, which prices), so the
browser cannot pick an easy task for itself, and it knows how long the
minigame takes at the very least, so "done" after half a second does not count.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Minigame:
    # The title in the header of the window, from DESIGN.md, section 8.
    title: str
    # A task reported as done sooner than this was not played (S-93).
    min_seconds: float
    # `make_content(rng) -> dict` draws what the browser needs to show the
    # task. `rng` is a random generator (the `random` module or a
    # `random.Random`); the function uses no other randomness and no clock.
    # The dict must be JSON-safe (texts, numbers, lists, dicts) and has a
    # "kind": the name the browser's part of the minigame is registered under.
    make_content: Callable
