"""The play test of to-do M2-1.4 "detailed campus map", as repeatable tests.

A tester played the map in two browsers with real key presses: both guests
walked from the spawn through each of the five doors into the room and back
out, walked along the walls and the furniture, opened every station in use
with E in three Duels, and resized the window while walking. What can be
repeated is repeated here:

- with the real map and the real walking rule `step`: every room can be
  walked into and out of through its door, both openings between the
  corridor and the Main Deck walked through, and every hiding spot reached,
  also the one in the hedge, which is walkable since M3-1.4 (S-98);
- with the real server and its real tick, over WebSocket: walking into one
  solid of every kind that M2-1.4 added stops at its edge, and no position
  any player is told lies inside a solid;
- in Chromium (skipped when Node, Playwright or Chromium is missing): two
  guests walk with keys while the window is resized without a console error
  or warning, every solid is visibly drawn, and no drawing reaches more than
  3 units from its solid into floor a player can stand on.
"""

import contextlib
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE, PLAYER_SPEED, is_free, overlaps, step
from task_helpers import put

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
WIDTH, HEIGHT = CAMPUS["width"], CAMPUS["height"]
SPAWN = (float(CAMPUS["spawn"]["x"]), float(CAMPUS["spawn"]["y"]))
ROOMS = {room["id"]: room for room in CAMPUS["rooms"]}
PASSWORD = "password123"

# The kinds of solids that M2-1.4 added (all others were on the map before).
NEW_KINDS = sorted({
    "bike-rack", "black-column", "cube-divider", "deck-bench", "fridge", "fruit-stand", "grid-shelf",
    "high-table", "hot-counter", "lamp-post", "lectern", "microwave-counter", "pillar", "recycling-bins",
    "sofa", "staircase", "study-table", "surfboard-rack", "totem", "tray-rack", "turnstile",
    "water-fountain",
} & {solid["kind"] for solid in SOLIDS})

# The walk of test_play_stations.py: 3-unit steps, one place kept per 2 x 2 square.
STEP_SECONDS = 3 / PLAYER_SPEED
SQUARE_SIZE = 2
FOUR_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
# How far behind a door a player must get: well past the door posts and gates.
DEPTH_BEHIND_DOOR = 30


def places_reachable_from(start):
    """Places a player reaches from `start` with the real walking rule."""
    seen = {_square(start)}
    reached = [start]
    waiting = deque([start])
    while waiting:
        x, y = waiting.popleft()
        for dx, dy in FOUR_DIRECTIONS:
            place = step(x, y, dx, dy, STEP_SECONDS, SOLIDS, WIDTH, HEIGHT)
            if _square(place) not in seen:
                seen.add(_square(place))
                reached.append(place)
                waiting.append(place)
    return reached


def _square(place):
    return (place[0] // SQUARE_SIZE, place[1] // SQUARE_SIZE)


@pytest.fixture(scope="module")
def from_spawn():
    return places_reachable_from(SPAWN)


def inside_behind(door, places):
    """The reachable places in the door's room, in line with the door and at least 30 units behind it."""
    room = ROOMS[door["room"]]
    room_is_below = room["y"] >= door["y"]
    found = []
    for x, y in places:
        in_line = door["x"] + PLAYER_HALF_SIZE <= x <= door["x"] + door["w"] - PLAYER_HALF_SIZE
        in_room = room["x"] <= x <= room["x"] + room["w"] and room["y"] <= y <= room["y"] + room["h"]
        depth = y - (door["y"] + door["h"]) if room_is_below else door["y"] - y
        if in_line and in_room and depth >= DEPTH_BEHIND_DOOR:
            found.append((x, y))
    return found


# Every door: in and back out

@pytest.mark.parametrize("door", CAMPUS["doors"], ids=lambda door: door["room"])
def test_a_player_walks_from_the_spawn_through_the_door_into_the_room(from_spawn, door):
    assert inside_behind(door, from_spawn) != []


@pytest.mark.parametrize("door", CAMPUS["doors"], ids=lambda door: door["room"])
def test_a_player_walks_from_behind_the_door_back_to_the_spawn(from_spawn, door):
    inside = inside_behind(door, from_spawn)[0]
    back = places_reachable_from(inside)
    assert any(math.dist(place, SPAWN) <= SQUARE_SIZE * 2 for place in back)


# The two openings in the wall between the corridor and the Main Deck
# (y 227-233, S-122): a player walks through each of them both ways.
CORRIDOR_WALLS = sorted((solid for solid in SOLIDS if solid["id"].startswith("corridor-wall-")), key=lambda s: s["x"])
OPENINGS = [(340, 390), (476, 657)]


def walks_straight_through(x, from_y, to_y):
    """Walk from (x, from_y) straight up or down for 2 s; True if the player gets past to_y."""
    y = from_y
    direction = 1 if to_y > from_y else -1
    for _ in range(40):
        x, y = step(x, y, 0, direction, 0.05, SOLIDS, WIDTH, HEIGHT)
    return (y - to_y) * direction >= 0


def test_the_corridor_wall_leaves_the_two_openings():
    assert [(wall["x"], wall["x"] + wall["w"], wall["y"]) for wall in CORRIDOR_WALLS] == [(163, 340, 227), (390, 476, 227)]


@pytest.mark.parametrize("opening", OPENINGS, ids=lambda opening: f"opening x {opening[0]}-{opening[1]}")
def test_a_player_walks_through_each_corridor_opening_both_ways(from_spawn, opening):
    wall_y = CORRIDOR_WALLS[0]["y"]
    # Some place of the opening where nothing stands right in front or behind
    # (in the wide eastern opening, the hedge and tree 3 stand below part of it).
    through = [
        x for x in range(opening[0] + PLAYER_HALF_SIZE, opening[1] - PLAYER_HALF_SIZE + 1)
        if walks_straight_through(x, wall_y + 30, wall_y - 20) and walks_straight_through(x, wall_y - 20, wall_y + 30)
    ]
    assert through != []
    assert any(through[0] <= x <= through[-1] and wall_y - 30 < y < wall_y for x, y in from_spawn)


# Since hiding was built (M3-1.4) the hedge is walkable, so the hiding spot
# in it can be reached like the other three (S-98).
HIDING_SPOTS = CAMPUS["hiding_spots"]
HEDGE = next(solid for solid in SOLIDS if solid["kind"] == "hedge")


def centre_lies_in(spot, solid):
    return (
        solid["x"] <= spot["x"] <= solid["x"] + solid["w"]
        and solid["y"] <= spot["y"] <= solid["y"] + solid["h"]
    )


def test_one_of_the_four_hiding_spots_lies_in_the_walkable_hedge():
    assert len(HIDING_SPOTS) == 4
    assert HEDGE["walkable"] is True
    assert len([spot for spot in HIDING_SPOTS if centre_lies_in(spot, HEDGE)]) == 1


@pytest.mark.parametrize("spot", HIDING_SPOTS, ids=lambda spot: f"hiding spot at {spot['x']},{spot['y']}")
def test_every_hiding_spot_can_be_reached(from_spawn, spot):
    assert any(math.dist(place, (spot["x"], spot["y"])) <= spot["r"] for place in from_spawn)


# Walking into the new solids with the real server

def approach(solid):
    """A free start a few units off one side of the solid, and the direction towards it.

    The side (and the place along it) is one where the real `step` walks the
    player right up to the solid's edge, so nothing else is in the way.
    """
    for gap in (8, 3):
        for share in (0.5, 0.25, 0.75):
            along_x = solid["x"] + solid["w"] * share
            along_y = solid["y"] + solid["h"] * share
            off = PLAYER_HALF_SIZE + gap
            sides = [
                ((solid["x"] - off, along_y), (1, 0), ("x", solid["x"] - PLAYER_HALF_SIZE)),
                ((solid["x"] + solid["w"] + off, along_y), (-1, 0), ("x", solid["x"] + solid["w"] + PLAYER_HALF_SIZE)),
                ((along_x, solid["y"] - off), (0, 1), ("y", solid["y"] - PLAYER_HALF_SIZE)),
                ((along_x, solid["y"] + solid["h"] + off), (0, -1), ("y", solid["y"] + solid["h"] + PLAYER_HALF_SIZE)),
            ]
            for start, direction, (axis, edge) in sides:
                if walks_up_to(start, direction, axis, edge):
                    return start, direction, axis, edge
    return None


def walks_up_to(start, direction, axis, edge):
    if not is_free(start[0], start[1], SOLIDS, WIDTH, HEIGHT):
        return False
    x, y = start
    for _ in range(20):
        x, y = step(x, y, direction[0], direction[1], 0.05, SOLIDS, WIDTH, HEIGHT)
    return (x if axis == "x" else y) == pytest.approx(edge)


def one_solid_of_each_new_kind():
    return [next(solid for solid in SOLIDS if solid["kind"] == kind) for kind in NEW_KINDS]


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture
def connect():
    with TestClient(app) as client, contextlib.ExitStack() as connections:
        yield lambda: connections.enter_context(client.websocket_connect("/ws"))


def ask(connection, message):
    connection.send_json(message)
    return connection.receive_json()


def positions_until_quiet(connection):
    """Mara's positions as this connection is told them, until none arrive for 0.4 s."""
    deadline = time.monotonic() + 15
    trail = []
    while True:
        connection.send_json({"type": "hello", "name": "Reader"})
        arrived = []
        while (message := connection.receive_json())["type"] != "welcome":
            if message["type"] == "positions":
                arrived += [(p["x"], p["y"]) for p in message["players"] if p["name"] == "Mara"]
        if not arrived and trail:
            return trail
        trail += arrived
        assert time.monotonic() < deadline, "the positions did not stop arriving"
        time.sleep(0.4)


def test_every_new_kind_of_solid_has_a_side_a_player_can_walk_up_to():
    assert [solid["id"] for solid in one_solid_of_each_new_kind() if approach(solid) is None] == []


@pytest.mark.parametrize("solid", one_solid_of_each_new_kind(), ids=lambda solid: solid["id"])
def test_walking_into_a_new_solid_with_the_real_server_stops_at_its_edge(connect, solid):
    start, direction, axis, edge = approach(solid)
    mara = connect()
    assert ask(mara, {"type": "sign_up", "name": "Mara", "password": PASSWORD})["type"] == "signed_in"
    watcher = connect()
    assert ask(watcher, {"type": "guest"})["type"] == "signed_in"
    code = ask(mara, {"type": "create_lobby"})["code"]
    watcher.send_json({"type": "join_lobby", "code": code})
    positions_until_quiet(mara)
    positions_until_quiet(watcher)

    put("Mara", start)
    mara.send_json({"type": "move", "dx": direction[0], "dy": direction[1]})
    for connection in (mara, watcher):
        trail = positions_until_quiet(connection)
        assert [place for place in trail if any(overlaps(*place, other) for other in SOLIDS)] == []
        last = trail[-1]
        assert (last[0] if axis == "x" else last[1]) == pytest.approx(edge)


# In Chromium: no console errors, everything drawn where it blocks

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_campus_detail_in_browser.js")
NODE = shutil.which("node")
NPM = shutil.which("npm")
# A drawing may reach this far past its solid (outlines, shadows, a chair's back).
LONGEST_OVERHANG = 3
# Below this share of its rectangle drawn, a solid would block where nothing is seen.
LEAST_DRAWN_SHARE = 0.25


def node_environment():
    environment = dict(os.environ)
    if NPM:
        root = subprocess.run([NPM, "root", "-g"], capture_output=True, text=True, check=False).stdout.strip()
        environment["NODE_PATH"] = os.pathsep.join(filter(None, [environment.get("NODE_PATH"), root]))
    return environment


def playwright_works():
    if NODE is None:
        return False
    probe = "require('playwright').chromium.launch().then(b => b.close())"
    finished = subprocess.run([NODE, "-e", probe], env=node_environment(), capture_output=True, timeout=60, check=False)
    return finished.returncode == 0


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
def played(running_server):
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), running_server],
        env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


@needs_chromium
def test_two_guests_walk_and_resize_without_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
def test_every_solid_is_visibly_drawn(played):
    assert [row["id"] for row in played["coverage"] if row["share"] < LEAST_DRAWN_SHARE] == []


@needs_chromium
def test_no_drawing_reaches_far_into_floor_a_player_can_stand_on(played):
    assert played["overhang"]["distance"] <= LONGEST_OVERHANG, played["overhang"]
