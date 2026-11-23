"""The timing minigame at the beach exit (DESIGN.md, section 8)."""

from server.modes.minigame import Minigame


def make_content(rng) -> dict:
    """Choose how long each wave takes to cross the minigame."""
    return {
        "kind": "catch_the_wave",
        "wave_duration_ms": rng.randint(1800, 2400),
    }


MINIGAME = Minigame(title="Catch the wave", min_seconds=3, make_content=make_content)
