"""The stand-in for a minigame that is not built yet.

It has nothing to draw: the browser shows "This task is still being built."
and a button "Finish task" (DESIGN.md, section 8).
"""

from server.modes.minigame import Minigame

# Long enough that a click the moment the window opens does not count.
MIN_SECONDS = 1


def make_content(rng) -> dict:
    """The placeholder looks the same every time, so `rng` is not used."""
    return {"kind": "placeholder"}


def placeholder(title: str) -> Minigame:
    """The entry for a station whose real minigame does not exist yet."""
    return Minigame(title=title, min_seconds=MIN_SECONDS, make_content=make_content)
