"""The Node harnesses of area 4, run by pytest (brief A, fix 5).

Each file runs the page's real JavaScript in Node with a small stand-in for
the browser and throws on the first check that fails:

- test_client_room_tasks.js: the six room tasks of stations 7 to 12, and
  Duel and Solo in main.js
- test_client_roster.js: the "Players" card over the map
- test_task_navigation.js: the task arrow and card, and which stations
  world.js and draw.js show
- test_minigame_done_close.js: the × of the minigame window in its "Done" state
- test_station_objects.js: the objects at the stations and their pulsing outline

Without Node the tests are skipped; CI has Node. When Node ends with an
error, the test fails and shows what Node printed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
NODE = shutil.which("node")
HARNESSES = [
    "test_client_room_tasks.js",
    "test_client_roster.js",
    "test_task_navigation.js",
    "test_minigame_done_close.js",
    "test_station_objects.js",
]

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")


@pytest.mark.parametrize("harness", HARNESSES)
def test_the_harness_passes_in_node(harness):
    finished = subprocess.run(
        [NODE, str(TESTS / harness)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = finished.stdout + finished.stderr
    assert finished.returncode == 0, f"{harness} failed:\n{output}"
    assert "passed" in finished.stdout, f"{harness} printed no summary:\n{output}"
