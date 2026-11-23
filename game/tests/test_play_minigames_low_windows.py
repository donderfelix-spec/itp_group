"""The minigames of stations 6 to 12 in a low window (M2-4.25, station 6 since M4-4.0).

On a small laptop screen the window of these minigames was up to 1150px
high: at 1280x600 the player had to scroll inside it to reach "Publish
honest chart", "Pin the schedule", the second row of products or the lane
buttons. Now their layout follows the height of the map.

This test opens every one of them with the real page and the real frame
(`Game.minigames.open`, as main.js does when the server opens a station)
over the map of a lobby, with content the server's own minigames drew from
three seeds each. In laptop windows (1280x800, 1024x700, 1280x600 and
1024x600) it checks that every control and the instruction lie inside the
window, that the window lies inside the viewport, and that no two of them
overlap. In a 320x640 window, where every minigame scrolls (stations 1 to
5 too), the window still lies inside the viewport and nothing reaches out
of it sideways. Skipped when Node, Playwright or Chromium is missing, like
the other play tests.
"""

import contextlib
import json
import random
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server.modes import minigames
from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_minigames_low_windows_in_browser.js")
STATIONS = [6, 7, 8, 9, 10, 11, 12]
SEEDS = [1, 2, 3]
LAPTOP_SIZES = ["1280x800", "1024x700", "1280x600", "1024x600"]
PHONE_SIZE = "320x640"
SIZES = LAPTOP_SIZES + [PHONE_SIZE]
# Rounding of the layout, in CSS pixels.
TOLERANCE = 0.5

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def running_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            time.sleep(0.1)
        yield base
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="module")
def played(running_server, tmp_path_factory):
    openings = []
    for station in STATIONS:
        minigame = minigames.MINIGAMES[station]
        for seed in SEEDS:
            content = minigame.make_content(random.Random(seed))
            openings.append({"station": station, "title": minigame.title, "content": content})
    path = tmp_path_factory.mktemp("low_windows") / "openings.json"
    path.write_text(json.dumps(openings))
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), running_server, str(path)],
        env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def openings_of(played, size, station):
    found = [seen for seen in played["seen"][size] if seen["station"] == station]
    assert len(found) == len(SEEDS)
    return found


def lies_inside(box, frame):
    return (box["x"] >= frame["x"] - TOLERANCE and box["y"] >= frame["y"] - TOLERANCE
            and box["x"] + box["w"] <= frame["x"] + frame["w"] + TOLERANCE
            and box["y"] + box["h"] <= frame["y"] + frame["h"] + TOLERANCE)


def overlap(a, b):
    """How far two boxes reach into each other, the smaller of both directions."""
    across = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    down = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return min(across, down)


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("station", STATIONS)
def test_the_window_lies_inside_the_viewport(played, size, station):
    for seen in openings_of(played, size, station):
        assert seen["shown"]
        viewport = {"x": 0, "y": 0, "w": seen["viewport"]["w"], "h": seen["viewport"]["h"]}
        assert lies_inside(seen["window"], viewport)


@needs_chromium
@pytest.mark.parametrize("size", LAPTOP_SIZES)
@pytest.mark.parametrize("station", STATIONS)
def test_the_instruction_and_every_control_are_in_view_without_scrolling(played, size, station):
    for seen in openings_of(played, size, station):
        assert len(seen["instructions"]) == 1
        assert seen["controls"], "expected the controls of the minigame"
        for box in seen["instructions"] + seen["controls"]:
            assert lies_inside(box, seen["inside"]), f"{box['name']} lies outside the window"


@needs_chromium
@pytest.mark.parametrize("size", LAPTOP_SIZES)
@pytest.mark.parametrize("station", STATIONS)
def test_no_two_controls_and_no_control_and_the_instruction_overlap(played, size, station):
    for seen in openings_of(played, size, station):
        boxes = seen["instructions"] + seen["controls"]
        for index, first in enumerate(boxes):
            for second in boxes[index + 1:]:
                assert overlap(first, second) <= TOLERANCE, f"{first['name']} lies on {second['name']}"


@needs_chromium
@pytest.mark.parametrize("station", STATIONS)
def test_in_a_phone_window_nothing_reaches_out_of_the_window_sideways(played, station):
    for seen in openings_of(played, PHONE_SIZE, station):
        assert seen["sideways"] <= TOLERANCE
        inside = seen["inside"]
        for box in seen["instructions"] + seen["controls"]:
            assert box["x"] >= inside["x"] - TOLERANCE, box["name"]
            assert box["x"] + box["w"] <= inside["x"] + inside["w"] + TOLERANCE, box["name"]
