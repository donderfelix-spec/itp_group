"""The play test of to-do M2-1.19 "campus map Felix mix", as repeatable tests.

A tester played the new map in Chromium with two guests and real key presses
(play_campus_felix_mix_in_browser.js): a guest holds a walk key and lets go
when the server says the character is where it should be. What was played is
checked here:

- every room is walked into through its door (30 units behind it) and back
  out, and both openings of the corridor wall are walked through both ways;
- stations 1-5 are walked into range in the lobby;
- the new walkways: down both side aisles of the Lecture Hall and straight
  through both gaps between its three rows, straight from the Mon Café door
  to the counter, up the Canteen's centre aisle to the counter, straight down
  the Pingo Doce lane between the two posts, and each post stops a player
  walking sideways in the lane;
- a Duel: each guest walks to its first station, sees it glow ("E Use") and
  opens its minigame with E pressed twice quickly (one window); then one guest
  leaves in the middle of the round while walking, and the other walks on;
- a 320 x 568 window: no horizontal scrolling, the map is drawn;
- no console error or warning and no page error in any of the pages.

Skipped when Node, Playwright or Chromium is missing.
"""

import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE
from test_play_campus_detail import NODE, node_environment, playwright_works

CAMPUS = load_campus()
SOLIDS = {solid["id"]: solid for solid in CAMPUS["solids"]}
STATIONS = {station["id"]: station for station in CAMPUS["stations"]}
GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_campus_felix_mix_in_browser.js")

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def played():
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
        finished = subprocess.run(
            [NODE, str(BROWSER_SCRIPT), base],
            env=node_environment(), capture_output=True, text=True, timeout=480, check=False,
        )
    finally:
        server.terminate()
        server.wait(timeout=10)
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def straight(played, name):
    return next(walk for walk in played["straight"] if walk["name"] == name)


@needs_chromium
def test_no_console_error_warning_or_page_error_in_any_page(played):
    assert played["console"] == []


@needs_chromium
def test_every_planned_walk_ended_where_it_should(played):
    assert played["misses"] == []


@needs_chromium
@pytest.mark.parametrize("room", [door["room"] for door in CAMPUS["doors"]])
def test_a_guest_walks_through_each_door_in_and_out(played, room):
    door = played["doors"][room]
    assert door["behind_door"], door
    assert door["back_out"], door


@needs_chromium
@pytest.mark.parametrize("index", [0, 1], ids=["opening x 340-390", "opening x 476-657"])
def test_a_guest_walks_through_each_corridor_opening_both_ways(played, index):
    opening = played["openings"][index]
    assert opening["up"] and opening["down"], opening


@needs_chromium
@pytest.mark.parametrize("station", [1, 2, 3, 4, 5])
def test_a_guest_walks_into_range_of_stations_1_to_5(played, station):
    assert played["stations"][str(station)]["in_range"], played["stations"][str(station)]


@needs_chromium
@pytest.mark.parametrize("name", ["lecture left aisle down", "lecture right aisle down"])
def test_both_side_aisles_of_the_lecture_hall_are_walked_from_the_front_to_the_back(played, name):
    walk = straight(played, name)
    first_row = SOLIDS["lecture-hall-bench-1"]
    last_row = SOLIDS["lecture-hall-bench-3"]
    assert walk["from"]["x"] == walk["to"]["x"]
    assert walk["from"]["y"] < first_row["y"]
    assert walk["to"]["y"] > last_row["y"] + last_row["h"]


@needs_chromium
@pytest.mark.parametrize(
    ("name", "above", "below"),
    [
        ("lecture gap rows 1-2 left to right", "lecture-hall-bench-1", "lecture-hall-bench-2"),
        ("lecture gap rows 2-3 right to left", "lecture-hall-bench-2", "lecture-hall-bench-3"),
    ],
)
def test_a_guest_walks_straight_through_each_gap_between_the_lecture_rows(played, name, above, below):
    walk = straight(played, name)
    row_above, row_below = SOLIDS[above], SOLIDS[below]
    assert walk["from"]["y"] == walk["to"]["y"]
    assert row_above["y"] + row_above["h"] < walk["to"]["y"] < row_below["y"]
    xs = sorted([walk["from"]["x"], walk["to"]["x"]])
    assert xs[0] < row_above["x"] and xs[1] > row_above["x"] + row_above["w"]


@needs_chromium
@pytest.mark.parametrize(
    ("name", "counter"),
    [("cafe door to counter", "mon-cafe-counter"), ("canteen centre aisle to counter", "canteen-counter")],
)
def test_a_guest_walks_straight_from_the_door_up_to_the_counter(played, name, counter):
    walk = straight(played, name)
    assert walk["from"]["x"] == walk["to"]["x"]
    assert walk["from"]["y"] > 173  # started outside, in the corridor
    solid = SOLIDS[counter]
    assert walk["to"]["y"] == pytest.approx(solid["y"] + solid["h"] + PLAYER_HALF_SIZE)


@needs_chromium
def test_a_guest_walks_straight_down_the_pingo_lane_past_the_posts(played):
    walk = straight(played, "pingo lane down")
    post = SOLIDS["pingo-doce-gate-1"]
    assert walk["from"]["x"] == walk["to"]["x"]
    assert walk["from"]["y"] < next(door for door in CAMPUS["doors"] if door["room"] == "pingo-doce")["y"]
    assert walk["to"]["y"] > post["y"] + post["h"] + PLAYER_HALF_SIZE


@needs_chromium
@pytest.mark.parametrize(
    ("name", "post", "side"),
    [("pingo lane left into post", "pingo-doce-gate-1", "right"), ("pingo lane right into post", "pingo-doce-gate-4", "left")],
)
def test_each_pingo_post_stops_a_guest_walking_sideways_in_the_lane(played, name, post, side):
    walk = straight(played, name)
    solid = SOLIDS[post]
    edge = solid["x"] + solid["w"] + PLAYER_HALF_SIZE if side == "right" else solid["x"] - PLAYER_HALF_SIZE
    assert walk["from"]["y"] == walk["to"]["y"]
    assert walk["to"]["x"] == pytest.approx(edge)


@needs_chromium
@pytest.mark.parametrize("guest", ["A", "B"])
def test_in_a_duel_each_guest_sees_its_station_glow_and_opens_it_with_e(played, guest):
    duel = played["duel"][guest]
    assert duel["glowing"] == duel["station"]
    assert duel["opened"]


@needs_chromium
@pytest.mark.parametrize("guest", ["A", "B"])
def test_pressing_e_twice_quickly_opens_one_window(played, guest):
    assert played["duel"][guest]["windows"] == 1


@needs_chromium
def test_a_guest_walks_on_after_the_other_left_in_the_middle_of_the_duel(played):
    after = played["duel"]["after_leave"]
    assert after["b_at_home"]
    assert after["a_to"]["y"] > after["a_from"]["y"]


@needs_chromium
def test_a_narrow_window_draws_the_map_without_horizontal_scrolling(played):
    narrow = played["narrow"]
    assert narrow["scroll_width"] <= narrow["client_width"] == 320
    assert narrow["canvas"]["left"] >= 0 and narrow["canvas"]["right"] <= 320
    assert narrow["canvas"]["shown_width"] > 0 and narrow["canvas"]["shown_height"] > 0
    assert narrow["colours"] > 20  # a drawn map, not an empty canvas


@needs_chromium
def test_no_action_of_the_play_was_rejected(played):
    assert played["rejections"] == {"A": [], "B": []}
