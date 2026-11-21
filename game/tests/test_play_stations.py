"""The play test of to-do M2-1.1 "Stations on the map", as repeatable tests.

A tester walked a character to each of the six stations in a browser. What can
be repeated without a browser is repeated here, with the real map and the real
walking rules: every station can be walked into range from the spawn point,
nothing is in range on the way out of the spawn, and no place on the campus is
in range of two stations at once.

The glowing border, the button "E Use" and the key E live in the browser
(client/js/world/world.js) and were checked by hand; pytest cannot run them.
"""

import math
from collections import deque

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.world.campus import load_campus
from server.world.movement import PLAYER_SPEED, step
from server.world.stations import station_in_range

CAMPUS = load_campus()
STATIONS = CAMPUS["stations"]
USE_RANGE = CAMPUS["use_range"]
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])

# One step of the walk below is 3 units long: fine enough for every corridor
# of the map (the narrowest is wider than a player), coarse enough to be quick.
STEP_SECONDS = 3 / PLAYER_SPEED
SQUARE_SIZE = 2
FOUR_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def places_a_player_can_walk_to():
    """Places a player reaches from the spawn point with the real walking rule.

    The player tries the four directions from every place it has reached, again
    and again, until no new place turns up. To stay quick, the campus is split
    into squares of 2 x 2 units and only the first place found in each square
    is kept and walked on from. Every corridor of the map leaves a player more
    than 2 units of room, so no corridor is missed.
    """
    start = (float(SPAWN[0]), float(SPAWN[1]))
    seen_squares = {_square(start)}
    reached = [start]
    waiting = deque([start])
    while waiting:
        x, y = waiting.popleft()
        for dx, dy in FOUR_DIRECTIONS:
            place = step(x, y, dx, dy, STEP_SECONDS, CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
            if _square(place) not in seen_squares:
                seen_squares.add(_square(place))
                reached.append(place)
                waiting.append(place)
    return reached


def _square(place):
    return (place[0] // SQUARE_SIZE, place[1] // SQUARE_SIZE)


@pytest.fixture(scope="module")
def reachable():
    return places_a_player_can_walk_to()


def places_in_range_of(station, reachable):
    return [
        (x, y) for x, y in reachable
        if station_in_range(x, y, STATIONS, USE_RANGE) == station["id"]
    ]


# Accepted: every station can be used

@pytest.mark.parametrize("station", STATIONS, ids=lambda station: f"station {station['id']}")
def test_a_player_can_walk_from_the_spawn_into_range_of_every_station(reachable, station):
    assert places_in_range_of(station, reachable) != []


@pytest.mark.parametrize("station", STATIONS, ids=lambda station: f"station {station['id']}")
def test_no_furniture_forces_one_exact_spot_to_use_a_station(reachable, station):
    # "Comfortable" in numbers: the places in range that a player can stand on
    # are at least 20 units apart in one direction, more than three steps of
    # the server (6 units each). A player does not have to hit one exact spot.
    places = places_in_range_of(station, reachable)
    widest = max(
        max(x for x, _ in places) - min(x for x, _ in places),
        max(y for _, y in places) - min(y for _, y in places),
    )
    assert widest >= 20


@pytest.mark.parametrize("station", STATIONS, ids=lambda station: f"station {station['id']}")
def test_a_player_can_stand_right_next_to_every_station(reachable, station):
    # Well inside the range, not only at its very edge: within 15 units.
    nearest = min(math.hypot(x - station["x"], y - station["y"]) for x, y in reachable)
    assert nearest <= 15


# Rejected: nothing to use

def test_nothing_is_in_range_within_a_second_of_walking_from_the_spawn(reachable):
    # Criterion "on the spawn point nothing glows", with room around it.
    near_the_spawn = [
        (x, y) for x, y in reachable
        if math.hypot(x - SPAWN[0], y - SPAWN[1]) <= PLAYER_SPEED
    ]
    assert near_the_spawn != []
    assert all(station_in_range(x, y, STATIONS, USE_RANGE) is None for x, y in near_the_spawn)


def test_the_walk_really_covers_the_campus(reachable):
    # A check of the helper itself: it found the far corners of the deck, and
    # never a place on the beach.
    assert any(x < 40 and y > 500 for x, y in reachable)  # bottom of the CTT hall
    assert any(x > 640 and y < 60 for x, y in reachable)  # top right of the canteen
    assert all(y < 566 for _, y in reachable)


# Edge cases

def test_no_place_is_in_range_of_two_stations():
    # Then "the closer one counts" never has to decide between two stations.
    for first in STATIONS:
        for second in STATIONS:
            if first["id"] < second["id"]:
                apart = math.hypot(first["x"] - second["x"], first["y"] - second["y"])
                assert apart > 2 * USE_RANGE, (first["id"], second["id"])


def test_the_browser_gets_the_stations_and_the_range_with_the_map():
    # The browser decides what glows from this file; it must carry the same
    # twelve stations and the same range the server uses.
    with TestClient(app) as client:
        answer = client.get("/js/world/campus.json")
    assert answer.status_code == 200
    sent = answer.json()
    assert sent["use_range"] == USE_RANGE
    assert [(s["id"], s["x"], s["y"]) for s in sent["stations"]] == [(s["id"], s["x"], s["y"]) for s in STATIONS]
    assert sorted(s["id"] for s in sent["stations"]) == list(range(1, 13))
