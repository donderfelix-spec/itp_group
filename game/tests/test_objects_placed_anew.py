"""The hiding and station objects placed anew (M3-1.7, S-196).

Felix drew on a picture of the whole map where the objects should stand
(2026-11-22). This file pins the new places and checks, with the real map
and the real rules, what must keep holding there:

- stations 4, 8, 9 and 12, the hedge with its hollow, the boxes and the
  potted plant stand at their new places; the other stations, the beanbag
  and the red button kept theirs; station 6 stays where it was;
- three new hiding spots (coffee sacks in Mon Café, folding chairs in the
  Lecture Hall, sun loungers on the Main Deck) lie in their rooms, on free
  floor, and E reaches them from up to `use_range` (25) away, not further;
- every station and every hiding spot can be reached from the spawn on the
  server's path grid;
- where a spot stands beside a station (the Canteen's plant beside station
  9), one place reaches both;
- a hiding spot may name its drawing with `object` (the deck has two spots
  now); the map check refuses a name that is not one;
- the walking distances of the Duel and Solo (S-79), measured again: the
  longest and the shortest tour and how evenly the tours are spread.

The drawn objects are checked in test_hiding_objects.py (the spots) and
test_map_polish.py (the stations, station 6's surfboard included); hiding
with E through the server at every spot in test_hide_with_e.py and
test_server_hiding.py, in real browsers in test_play_hiding.py.
"""

import copy
import itertools
import math

import pytest

from server.classic import hiding
from server.modes import duel
from server.world.campus import CampusError, check_campus, load_campus
from server.world.movement import is_free
from server.world.paths import GRID_STEP, SPAWN, Grid, station_distances
from server.world.stations import station_in_range

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
WIDTH, HEIGHT = CAMPUS["width"], CAMPUS["height"]
USE_RANGE = CAMPUS["use_range"]

# Station id -> (x, y): the places of M3-1.7, and where they were before.
MOVED_STATIONS = {4: (38, 521), 8: (278, 154), 9: (612, 156), 12: (644, 350)}
STATIONS_BEFORE = {4: (90, 520), 8: (292, 118), 9: (609, 130), 12: (600, 350)}
UNCHANGED_STATIONS = {
    1: (196, 46), 2: (431, 62), 3: (640, 48), 5: (532, 534), 6: (300, 534),
    7: (32, 46), 10: (131, 268), 11: (596, 468),
}

# The hiding spots in the order of the map: (x, y, r) and the room they lie
# in (None on the Main Deck). H1 to H4 were at (595, 249), (549, 468),
# (136, 524) and (636, 128); H5 to H7 are new.
SPOTS = [
    ((644, 297, 9), None),  # H1 the hollow in the hedge
    ((573, 499, 9), "pingo-doce"),  # H2 cardboard boxes
    ((136, 524, 9), "ctt"),  # H3 the beanbag, unchanged
    ((646, 156, 9), "canteen"),  # H4 the potted plant
    ((406, 133, 9), "mon-cafe"),  # H5 coffee sacks
    ((39, 154, 9), "lecture-hall"),  # H6 folding chairs
    ((183, 539, 9), None),  # H7 sun loungers
]
NEW_SPOTS = [4, 5, 6]


def station_called(station_id, campus=CAMPUS):
    return next(station for station in campus["stations"] if station["id"] == station_id)


def room_of(x, y):
    """The id of the room the point lies in (its edge included), or None on the deck."""
    for room in CAMPUS["rooms"]:
        if room["x"] <= x <= room["x"] + room["w"] and room["y"] <= y <= room["y"] + room["h"]:
            return room["id"]
    return None


# ---- The places -----------------------------------------------------------


def test_the_moved_stations_stand_at_their_new_places():
    assert {station_id: (station_called(station_id)["x"], station_called(station_id)["y"])
            for station_id in MOVED_STATIONS} == MOVED_STATIONS


def test_the_other_stations_kept_their_places():
    assert {station_id: (station_called(station_id)["x"], station_called(station_id)["y"])
            for station_id in UNCHANGED_STATIONS} == UNCHANGED_STATIONS


def test_every_moved_station_stays_in_its_room():
    for station_id, (x, y) in MOVED_STATIONS.items():
        station = station_called(station_id)
        expected = None if station["room"] == "deck" else station["room"]
        assert room_of(x, y) == expected, station_id


def test_the_red_button_kept_its_place():
    button = CAMPUS["button"]
    assert (button["x"], button["y"], button["r"]) == (365, 375, 11)


def test_the_seven_hiding_spots_stand_at_their_places_in_their_rooms():
    assert [((spot["x"], spot["y"], spot["r"]), room_of(spot["x"], spot["y"])) for spot in CAMPUS["hiding_spots"]] == SPOTS


@pytest.mark.parametrize("index", range(len(SPOTS)))
def test_every_spot_has_free_floor_in_its_middle(index):
    spot = CAMPUS["hiding_spots"][index]
    assert is_free(spot["x"], spot["y"], SOLIDS, WIDTH, HEIGHT)


@pytest.mark.parametrize("station_id", sorted(MOVED_STATIONS))
def test_every_moved_station_has_free_floor_in_its_middle(station_id):
    station = station_called(station_id)
    assert is_free(station["x"], station["y"], SOLIDS, WIDTH, HEIGHT)


def test_no_two_spots_and_no_spot_and_station_overlap():
    circles = [(spot["x"], spot["y"], spot["r"]) for spot in CAMPUS["hiding_spots"]]
    circles += [(station["x"], station["y"], station["r"]) for station in CAMPUS["stations"]]
    for first, second in itertools.combinations(circles, 2):
        assert math.dist(first[:2], second[:2]) > first[2] + second[2], (first, second)


# ---- Reached from the spawn ------------------------------------------------


@pytest.fixture(scope="module")
def reached_from_the_spawn():
    """The walking distance from the spawn to every grid point a player reaches (server/world/paths.py)."""
    grid = Grid(SOLIDS, WIDTH, HEIGHT)
    start = grid.nearest_free_point(CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"], GRID_STEP)
    return grid, grid.distances_from(start)


@pytest.mark.parametrize("index", range(len(SPOTS)))
def test_every_spot_can_be_walked_to_from_the_spawn(reached_from_the_spawn, index):
    grid, reached = reached_from_the_spawn
    spot = CAMPUS["hiding_spots"][index]
    near = grid.nearest_free_point(spot["x"], spot["y"], spot["r"])
    assert near is not None and near in reached


@pytest.mark.parametrize("station_id", sorted(MOVED_STATIONS) + [6])
def test_every_moved_station_and_station_6_can_be_walked_to_from_the_spawn(reached_from_the_spawn, station_id):
    grid, reached = reached_from_the_spawn
    station = station_called(station_id)
    near = grid.nearest_free_point(station["x"], station["y"], USE_RANGE)
    assert near is not None and near in reached


def test_a_spot_walled_in_would_not_be_reached(reached_from_the_spawn):
    # Rejected: the check above finds a spot nobody can walk to.
    _, reached = reached_from_the_spawn
    spot = CAMPUS["hiding_spots"][4]
    walls = [
        {"id": "a", "kind": "wall", "x": spot["x"] - 30, "y": spot["y"] - 30, "w": 60, "h": 4},
        {"id": "b", "kind": "wall", "x": spot["x"] - 30, "y": spot["y"] + 26, "w": 60, "h": 4},
        {"id": "c", "kind": "wall", "x": spot["x"] - 30, "y": spot["y"] - 30, "w": 4, "h": 60},
        {"id": "d", "kind": "wall", "x": spot["x"] + 26, "y": spot["y"] - 30, "w": 4, "h": 60},
    ]
    grid = Grid(SOLIDS + walls, WIDTH, HEIGHT)
    start = grid.nearest_free_point(CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"], GRID_STEP)
    walled_in = grid.distances_from(start)
    assert grid.nearest_free_point(spot["x"], spot["y"], spot["r"]) not in walled_in


# ---- E reaches the new spots ----------------------------------------------


def free_side(spot, distance):
    """A direction (dx, dy) in which the place `distance` from the spot's centre is free floor."""
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        if is_free(spot["x"] + dx * distance, spot["y"] + dy * distance, SOLIDS, WIDTH, HEIGHT):
            return dx, dy
    raise AssertionError(f"no free place {distance} units from {spot}")


@pytest.mark.parametrize("index", NEW_SPOTS)
def test_e_reaches_a_new_spot_from_25_units_on_free_floor_but_not_from_more(index):
    spot = CAMPUS["hiding_spots"][index]
    dx, dy = free_side(spot, USE_RANGE + 1)
    at_the_reach = (spot["x"] + dx * USE_RANGE, spot["y"] + dy * USE_RANGE)
    beyond = (spot["x"] + dx * (USE_RANGE + 0.01), spot["y"] + dy * (USE_RANGE + 0.01))
    assert hiding.spot_in_reach(CAMPUS, at_the_reach) is spot
    assert hiding.spot_in_reach(CAMPUS, beyond) is None


@pytest.mark.parametrize("index", NEW_SPOTS)
def test_a_living_free_rider_beside_a_new_spot_may_hide_and_a_high_performer_may_not(index):
    spot = CAMPUS["hiding_spots"][index]
    dx, dy = free_side(spot, 15)
    beside = (spot["x"] + dx * 15, spot["y"] + dy * 15)
    roles = {"fr": "FR", "hp": "HP"}
    assert hiding.hide_refusal(roles, set(), "round", "fr", beside, CAMPUS) is None
    assert hiding.hide_refusal(roles, set(), "round", "hp", beside, CAMPUS) == "hide_rejected"


def test_between_station_9_and_the_plant_both_are_in_reach():
    # Felix wants the plant beside station 9 (no distance added): from the
    # middle between them a High Performer can open the station and a Free
    # Rider can hide in the plant.
    station = station_called(9)
    plant = CAMPUS["hiding_spots"][3]
    middle = ((station["x"] + plant["x"]) / 2, (station["y"] + plant["y"]) / 2)
    assert is_free(*middle, SOLIDS, WIDTH, HEIGHT)
    assert station_in_range(*middle, [station], USE_RANGE) == 9
    assert hiding.spot_in_reach(CAMPUS, middle) is plant


def test_the_hedge_hollow_and_station_12_are_two_targets_apart():
    # Station 12 stands right below the hedge; no place reaches both (53 > 2 x 25),
    # so E never has to choose between them.
    station = station_called(12)
    hollow = CAMPUS["hiding_spots"][0]
    assert math.dist((station["x"], station["y"]), (hollow["x"], hollow["y"])) > 2 * USE_RANGE


# ---- The name of a spot's drawing -----------------------------------------


def test_only_the_sun_loungers_name_their_drawing():
    assert [spot.get("object") for spot in CAMPUS["hiding_spots"]] == [None] * 6 + ["sun-loungers"]


def test_a_spot_without_a_drawing_name_is_accepted():
    campus = copy.deepcopy(CAMPUS)
    del campus["hiding_spots"][6]["object"]
    assert check_campus(campus) is campus


@pytest.mark.parametrize("name", ["Sun loungers", "sun loungers", "", "-loungers", 5, None, ["sun-loungers"]])
def test_a_drawing_name_that_is_not_a_name_is_refused(name):
    campus = copy.deepcopy(CAMPUS)
    campus["hiding_spots"][6]["object"] = name
    with pytest.raises(CampusError, match="object"):
        check_campus(campus)


# ---- The walking distances of the Duel and Solo (S-79) ---------------------

# Station 6 was still decorative when M3-1.7 moved the other stations.
STATIONS_DURING_M3_1_7 = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]

# Measured with paths.station_distances on the map of M3-1.7, in map units:
# the spawn and every station with a minigame (1-5 and 7-12), 66 ways. The
# server measures them again when it starts; this table shows what changed.
WAYS_SINCE_M3_1_7 = {
    (SPAWN, 1): 598.676, (SPAWN, 2): 339.647, (SPAWN, 3): 326.274, (SPAWN, 4): 760.735, (SPAWN, 5): 262.510,
    (SPAWN, 7): 614.960, (SPAWN, 8): 286.392, (SPAWN, 9): 209.421, (SPAWN, 10): 471.078, (SPAWN, 11): 230.108,
    (SPAWN, 12): 181.539, (1, 2): 572.333, (1, 3): 815.362, (1, 4): 606.108, (1, 5): 856.500, (1, 7): 164.000,
    (1, 8): 495.882, (1, 9): 698.510, (1, 10): 321.137, (1, 11): 824.098, (1, 12): 780.215, (2, 3): 529.588,
    (2, 4): 757.588, (2, 5): 597.470, (2, 7): 588.617, (2, 8): 205.823, (2, 9): 412.735, (2, 10): 467.931,
    (2, 11): 565.068, (2, 12): 507.127, (3, 4): 1000.617, (3, 5): 542.392, (3, 7): 831.647, (3, 8): 481.019,
    (3, 9): 130.912, (3, 10): 710.960, (3, 11): 500.049, (3, 12): 365.019, (4, 5): 1018.558, (4, 7): 594.510,
    (4, 8): 681.137, (4, 9): 883.765, (4, 10): 324.569, (4, 11): 986.156, (4, 12): 942.274, (5, 7): 872.784,
    (5, 8): 544.215, (5, 9): 425.539, (5, 10): 728.902, (5, 11): 113.941, (5, 12): 258.510, (7, 8): 512.167,
    (7, 9): 714.794, (7, 10): 309.539, (7, 11): 840.382, (7, 12): 796.500, (8, 9): 364.167, (8, 10): 391.480,
    (8, 11): 511.813, (8, 12): 458.558, (9, 10): 594.108, (9, 11): 383.196, (9, 12): 248.167,
    (10, 11): 696.500, (10, 12): 652.617, (11, 12): 216.167,
}
# The pinned values are rounded to 0.001.
ROUNDING = 0.001


@pytest.fixture(scope="module")
def ways_now():
    return station_distances(CAMPUS, STATIONS_DURING_M3_1_7)


@pytest.fixture(scope="module")
def ways_before():
    """The ways with the four moved stations at their old places (the hedge is walkable and changes none)."""
    campus = copy.deepcopy(CAMPUS)
    for station in campus["stations"]:
        if station["id"] in STATIONS_BEFORE:
            station["x"], station["y"] = STATIONS_BEFORE[station["id"]]
    return station_distances(campus, STATIONS_DURING_M3_1_7)


def test_the_pinned_ways_cover_the_duel_stations_at_the_time_of_m3_1_7():
    places = [SPAWN] + STATIONS_DURING_M3_1_7
    assert {frozenset(pair) for pair in WAYS_SINCE_M3_1_7} == {
        frozenset(pair) for pair in itertools.combinations(places, 2)
    }


def test_every_way_is_as_long_as_pinned_both_ways_round(ways_now):
    for (start, goal), length in WAYS_SINCE_M3_1_7.items():
        assert ways_now[(start, goal)] == pytest.approx(length, abs=ROUNDING), (start, goal)
        assert ways_now[(goal, start)] == pytest.approx(length, abs=ROUNDING), (goal, start)


def test_only_ways_to_a_moved_station_changed(ways_now, ways_before):
    for pair, length in ways_now.items():
        if not set(pair) & set(STATIONS_BEFORE):
            assert length == pytest.approx(ways_before[pair], abs=ROUNDING), pair


def tours(ways):
    """Every Duel and Solo route (three stations from the spawn) with its length, shortest first."""
    routes = duel.all_routes(STATIONS_DURING_M3_1_7)
    return sorted((duel.route_length(route, ways), route) for route in routes)


def test_the_shortest_and_the_longest_tour(ways_now, ways_before):
    # Before: 423.6 (12, 11, 5) and 2566.8 (4, 5, 7). Station 12 moved 44
    # units further from the spawn, so the shortest tour is 88 longer; the
    # longest is 85.3 (3.3 %) longer, because station 4 stands by the wall.
    before, now = tours(ways_before), tours(ways_now)
    assert (round(before[0][0], 1), before[0][1]) == (423.6, (12, 11, 5))
    assert (round(before[-1][0], 1), before[-1][1]) == (2566.8, (4, 5, 7))
    assert (round(now[0][0], 1), now[0][1]) == (511.6, (12, 11, 5))
    assert (round(now[-1][0], 1), now[-1][1]) == (2652.1, (4, 5, 7))


def test_the_tours_are_spread_no_wider_than_before(ways_now, ways_before):
    # Fair for the Duel (S-94): the longest tour is now 5.2 times the shortest
    # (6.1 before), and the middle tour grew by less than 2 % (1493.4 -> 1518.7).
    before, now = tours(ways_before), tours(ways_now)
    assert now[-1][0] / now[0][0] < before[-1][0] / before[0][0]
    middle = len(now) // 2
    assert now[middle][0] / before[middle][0] < 1.02
