"""M3-4.22: the Classic arrow follows the real server, end to end.

Five guests play Classic in Chromium against the real server, run in this
process (the fixtures and `put` of test_play_classic_task_card_end_to_end.py).
The browser script watches the arrow by wrapping Game.taskNavigation.draw.

- A High Performer a few tiles from its station: the arrow points at its one
  active task (S-197); the card at the top left names the room and the task.
- After it really finished that station (E, "Finish task", the server's
  `station_done`), the arrow points at the next task the server names.
- After it finished all four, one after the other: no arrow.
- The Free Rider's page never draws an arrow.
- A High Performer failed by the Free Rider (a ghost) still gets the arrow.

Skipped when Node, Playwright or Chromium is missing.
"""

import json
import math
import os
import subprocess
import threading
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment
from test_play_classic_task_card_end_to_end import (  # noqa: F401 (fixtures)
    needs_chromium,
    no_countdown,
    placeholder_at_every_station,
    put,
    quiet_tick,
    server_in_this_process,
)

BROWSER_SCRIPT = Path(__file__).with_name("play_classic_arrow_end_to_end_in_browser.js")
# Set CLASSIC_ARROW_SCREENSHOT to a file path to keep a picture of step 1.
SCREENSHOT = os.environ.get("CLASSIC_ARROW_SCREENSHOT", "")


def play(base):
    """Run the browser script, placing players whenever it asks. Returns its last line."""
    browser = subprocess.Popen(
        [NODE, str(BROWSER_SCRIPT), base, SCREENSHOT], env=node_environment(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    timer = threading.Timer(240, browser.kill)
    timer.start()
    try:
        result = None
        for line in browser.stdout:
            message = json.loads(line)
            if "put" in message:
                for name, where in message["put"]:
                    put(name, where)
                browser.stdin.write("ok\n")
                browser.stdin.flush()
            else:
                result = message
        browser.wait()
        assert browser.returncode == 0, browser.stderr.read()
        return result
    finally:
        timer.cancel()


def assert_points_at(stations, frame, station_id):
    station = next(entry for entry in stations if entry["id"] == station_id)
    drawn = frame["drawn"]
    expected = math.atan2(station["y"] - drawn["y"], station["x"] - drawn["x"])
    assert frame["angle"] is not None, frame
    assert abs(frame["angle"] - expected) < 1e-6, (frame, station_id)


@pytest.fixture
def played(server_in_this_process):  # noqa: F811 (the imported fixture)
    return play(server_in_this_process)


@needs_chromium
def test_the_classic_arrow_points_at_the_one_active_task(played):
    worker = played["worker"]
    stations = worker["campus"]["stations"]
    tasks = worker["tasks"]
    # S-197: one active task; the arrow and the card follow it.
    assert len(tasks) == 1, worker
    start = worker["start"]
    assert worker["first"] == tasks[0]
    assert_points_at(stations, start, worker["first"])
    assert not worker["card"]["taskHidden"] and worker["card"]["here"], worker["card"]
    assert worker["second"] != worker["first"]
    assert_points_at(stations, worker["afterOne"], worker["second"])
    assert len(worker["order"]) == len(set(worker["order"])) == 4 and worker["left"] == [], worker
    assert worker["afterAll"]["angle"] is None, worker["afterAll"]

    assert played["freeRider"]["ever"] is False
    assert played["ghost"]["failed"]
    assert played["ghost"]["arrow"]["angle"] is not None, played["ghost"]

    assert played["problems"] == []
