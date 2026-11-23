"""The hiding spots are objects of the map (M3-1.5, S-190).

Each hiding spot shows an object that fits its place instead of the dashed
circle: boxes in the aisle of Pingo Doce, a beanbag by the bookshelf of the
CTT Student Hall, a potted plant in the corner of the Canteen and a hollow
in the hedge on the Main Deck. Each stands in a soft shade as large as the
spot. Since M3-1.7 (S-196) three more spots have their objects (coffee
sacks in Mon Café, folding chairs in the Lecture Hall, sun loungers on the
Main Deck), and the hedge, the boxes and the plant stand in new places. The
objects are only drawn:

- the spots lie at their places with their radii and nothing new is solid
  (the walking rules and the server's hiding rule stay as they are);
- every spot has its own object, drawn inside its circle (plus the
  drawing overhang) and on no other solid or station;
- without its drawing a spot still shows the dashed circle.

The browser part is hiding_objects_in_browser.js.
"""

import contextlib
import json
import math
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server.world.campus import load_campus
from server.world.movement import is_free
from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("hiding_objects_in_browser.js")
CAMPUS = load_campus()

# The spots, (x, y, r) -> the room they lie in. Of the four of S-62, M3-1.7
# (S-196) moved all but the beanbag; the last three are new.
SPOTS = {
    (644, 297, 9): None,  # the hedge on the Main Deck (was 595, 249)
    (573, 499, 9): "pingo-doce",  # was 549, 468
    (136, 524, 9): "ctt",
    (646, 156, 9): "canteen",  # was 636, 128
    (406, 133, 9): "mon-cafe",  # new: coffee sacks
    (39, 154, 9): "lecture-hall",  # new: folding chairs
    (183, 539, 9): None,  # new: sun loungers on the Main Deck
}
# How far a drawing may reach past its spot's circle (DRAWING_OVERHANG in draw.js).
REACH = 4
# The fewest changed pixels (of 16 per map unit) inside a spot's circle for
# its object to count as drawn: a fifth of the circle at 4 pixels per unit.
LEAST_DRAWN_PIXELS = int(math.pi * 9 * 9 * 16 / 5)

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


# ---- The map file: places kept, nothing new solid -------------------------


def test_the_seven_spots_lie_at_their_places_with_their_radii():
    assert {(spot["x"], spot["y"], spot["r"]) for spot in CAMPUS["hiding_spots"]} == set(SPOTS)


def solid_under(spot, solids=CAMPUS["solids"]):
    """The ids of the solids whose rectangle reaches into the spot's square."""
    return [solid["id"] for solid in solids
            if solid["x"] < spot["x"] + spot["r"] and spot["x"] - spot["r"] < solid["x"] + solid["w"]
            and solid["y"] < spot["y"] + spot["r"] and spot["y"] - spot["r"] < solid["y"] + solid["h"]]


def test_no_solid_but_the_walkable_hedge_lies_on_a_spot():
    found = {(spot["x"], spot["y"]): solid_under(spot) for spot in CAMPUS["hiding_spots"]}
    assert found == {(644, 297): ["deck-hedge"], (573, 499): [], (136, 524): [], (646, 156): [],
                     (406, 133): [], (39, 154): [], (183, 539): []}
    hedge = next(solid for solid in CAMPUS["solids"] if solid["id"] == "deck-hedge")
    assert hedge["walkable"] is True


def test_a_solid_put_on_a_spot_would_be_found():
    boxes = {"id": "boxes", "kind": "box", "x": 545, "y": 470, "w": 8, "h": 6}
    assert solid_under({"x": 549, "y": 468, "r": 9}, CAMPUS["solids"] + [boxes]) == ["boxes"]


def test_a_solid_that_only_touches_a_spots_square_is_not_on_it():
    touching = {"id": "beside", "kind": "box", "x": 558, "y": 470, "w": 3, "h": 3}
    assert solid_under({"x": 549, "y": 468, "r": 9}, CAMPUS["solids"] + [touching]) == []


def test_a_player_can_stand_in_the_middle_of_every_spot():
    for spot in CAMPUS["hiding_spots"]:
        assert is_free(spot["x"], spot["y"], CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])


# ---- What the page draws --------------------------------------------------


@pytest.fixture(scope="module")
def drawn():
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
            env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
        )
        assert finished.returncode == 0, finished.stderr
        result = json.loads(finished.stdout)
        result["spots"] = {(spot["x"], spot["y"], spot["r"]): spot for spot in result["spots"]}
        return result
    finally:
        server.terminate()
        server.wait(timeout=10)


@needs_chromium
def test_the_page_draws_the_spots_without_a_console_problem(drawn):
    assert drawn["console"] == []


@needs_chromium
def test_every_spot_has_its_own_object_from_its_rooms_art(drawn):
    assert {place: (spot["room"], spot["hasObject"]) for place, spot in drawn["spots"].items()} == {
        place: (room, True) for place, room in SPOTS.items()
    }


# The drawing each spot takes from the art files: "room-id:spot" in a room,
# "spot" for the hedge, and the deck's second spot names its own (M3-1.7).
DRAWINGS = {
    (644, 297, 9): "spot",
    (573, 499, 9): "pingo-doce:spot",
    (136, 524, 9): "ctt:spot",
    (646, 156, 9): "canteen:spot",
    (406, 133, 9): "mon-cafe:spot",
    (39, 154, 9): "lecture-hall:spot",
    (183, 539, 9): "sun-loungers",
}


@needs_chromium
def test_every_spot_takes_its_own_drawing_and_the_deck_has_two_different_ones(drawn):
    assert {place: spot["drawing"] for place, spot in drawn["spots"].items()} == DRAWINGS
    assert len(set(DRAWINGS.values())) == len(DRAWINGS)


def test_only_the_second_spot_on_the_deck_names_its_drawing():
    named = {(spot["x"], spot["y"]): spot["object"] for spot in CAMPUS["hiding_spots"] if "object" in spot}
    assert named == {(183, 539): "sun-loungers"}


@needs_chromium
def test_every_object_is_drawn_inside_its_spot(drawn):
    for place, spot in drawn["spots"].items():
        assert spot["inside"] >= LEAST_DRAWN_PIXELS, place
        assert spot["outside"] == 0, place


@needs_chromium
def test_no_object_is_drawn_on_other_furniture_or_a_station(drawn):
    assert {place: spot["onOthers"] for place, spot in drawn["spots"].items()} == {place: [] for place in SPOTS}


@needs_chromium
def test_a_spot_without_its_drawing_shows_the_dashed_circle(drawn):
    for place, spot in drawn["spots"].items():
        assert spot["fallback"] >= LEAST_DRAWN_PIXELS, place
