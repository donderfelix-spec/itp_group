"""S-222: "Seagull quality control" (station 12) ends at six saved pages.

The server refuses a task finished faster than its `min_seconds`. Since the
rescue now ends at the sixth saved page instead of after all twelve
flights, this pins that even the fastest honest solve of any packet the
server makes takes far longer than that floor.
"""

import random

import pytest

from server.modes import room_tasks

GAP_MS = 250       # pause between two flights (`ui.later(nextWave, 250)` in campus_challenges.js)
CATCH_SHARE = 0.5  # a page can be caught from the second half of its flight on


def fastest_solve_ms(content):
    """Catch every page at the earliest moment and touch no coffee."""
    elapsed = 0
    saved = 0
    for wave in content["waves"]:
        if wave["cargo"] == "page":
            saved += 1
            if saved == content["goal"]:
                return elapsed + wave["duration"] * CATCH_SHARE
        elapsed += wave["duration"] + GAP_MS
    raise AssertionError("the packet cannot be won")


@pytest.mark.parametrize("seed", range(300))
def test_every_packet_can_be_won_and_the_fastest_win_is_slower_than_the_floor(seed):
    content = room_tasks.seagull(random.Random(seed))
    floor_ms = room_tasks.MINIGAMES[12].min_seconds * 1000
    # Six pages need at least five whole flights before the sixth is caught.
    assert fastest_solve_ms(content) >= 5 * floor_ms


def test_eight_pages_four_coffees_and_a_goal_of_six():
    content = room_tasks.seagull(random.Random(1))
    cargo = [wave["cargo"] for wave in content["waves"]]
    assert (cargo.count("page"), cargo.count("coffee"), content["goal"]) == (8, 4, 6)
    # Two pages may be missed; the third missed page is the third mistake.
    assert cargo.count("page") - content["goal"] == 2
