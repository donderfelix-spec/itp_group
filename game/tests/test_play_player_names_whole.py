"""S-224: names in the lobby's Players list are not cut beside the map, in Chromium.

The panel beside the map (wider than 800px) lists one player per row, so a
name of 16 letters shows whole at 1280x800 and 1024x700 with 2 and 8 players,
and no name runs under "Host" or "You". Below the map (360x700) the list
keeps its two columns. Skipped without Node, Playwright and Chromium.
"""

import json
import subprocess
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works, running_server  # noqa: F401

SCRIPT = Path(__file__).with_name("player_names_in_browser.js")

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def seen(running_server):  # noqa: F811 (the imported fixture)
    finished = subprocess.run(
        [NODE, str(SCRIPT), running_server], env=node_environment(),
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


@pytest.mark.parametrize("size", ["1280x800", "1024x700"])
@pytest.mark.parametrize("count", [2, 8])
def test_beside_the_map_every_name_of_16_letters_shows_whole(seen, size, count):
    listed = seen["result"][f"{size} {count}"]
    assert listed["rows"] == count
    assert listed["cut"] == []
    assert listed["columns"] == 1


@pytest.mark.parametrize("size", ["1280x800", "1024x700", "360x700"])
def test_no_name_runs_under_a_marker(seen, size):
    assert not seen["result"][f"{size} 8"]["underMarker"]


def test_below_the_map_the_list_keeps_two_columns(seen):
    assert seen["result"]["360x700 8"]["columns"] == 2


def test_no_console_error_or_warning(seen):
    assert seen["problems"] == []
