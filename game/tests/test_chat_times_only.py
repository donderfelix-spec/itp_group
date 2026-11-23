"""S-223: "Decode the group chat" (station 10) asks only for the times.

The server sends four people, four slots, four clues (one per person) and
the answer as person and slot. The work category is gone from the content.
The client's own checks run in tests/challenges_in_node.js.
"""

import random
import re
from pathlib import Path

import pytest

from server.modes import room_tasks

CLIENT = Path(__file__).resolve().parents[1] / "client" / "js" / "minigames" / "campus_challenges.js"


@pytest.mark.parametrize("seed", range(50))
def test_the_content_has_one_time_per_person_and_nothing_about_work(seed):
    content = room_tasks.chat(random.Random(seed))
    assert set(content) == {"kind", "puzzle", "people", "slots", "clues", "schedule"}
    assert sorted(row["person"] for row in content["schedule"]) == sorted(content["people"])
    assert sorted(row["slot"] for row in content["schedule"]) == content["slots"] == [9, 10, 11, 12]
    assert all(set(row) == {"person", "slot"} for row in content["schedule"])
    assert len(content["clues"]) == 4


def test_the_fastest_honest_solve_is_never_refused():
    # Even a player who picks all four times at once reaches the server only
    # after the "Crisis averted" pause, which waits until 1100 ms after the
    # window opened (`1100 - (performance.now() - started)` in complete()).
    pause_ms = int(re.search(r"Math\.max\(0, (\d+) - \(performance\.now\(\) - started\)\)", CLIENT.read_text()).group(1))
    assert room_tasks.MINIGAMES[10].min_seconds * 1000 < pause_ms
