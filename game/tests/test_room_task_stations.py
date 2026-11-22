"""The six room-task stations 7 to 12 block no way (brief A, fix 4).

Stations are not solid, so adding them must not change any way on the map.
The walking distances between the spawn and stations 1 to 5 are pinned here
as they were measured on main (d2be14d) before the stations were added.
Free centres, reachability and "no place in range of two stations" are
checked for every station in test_campus.py, test_task_map_integration.py
and test_play_stations.py.
"""

import itertools

import pytest

from server.world.campus import load_campus
from server.world.movement import is_free
from server.world.paths import SPAWN, station_distances

CAMPUS = load_campus()
NEW_STATIONS = [7, 8, 9, 10, 11, 12]

# Measured on main (d2be14d) with paths.station_distances, in map units.
# Measured again for the map of M2-1.19 (S-141), which took a lecture row,
# a café table and column and two canteen tables out: the ways through the
# Lecture Hall and Mon Café became shorter (1 to 2: 597.019 -> 573.990).
# The stations still change no way (the map is the same with and without them).
# 3-5 is shorter than measured there: the hedge became walkable for hiding
# (S-98, M3-1.4), which shortens that one way from 558.960 (S-140).
DISTANCES_ON_MAIN = {
    (SPAWN, 1): 598.676, (SPAWN, 2): 341.304, (SPAWN, 3): 326.274, (SPAWN, 4): 718.108, (SPAWN, 5): 262.510,
    (1, 2): 573.990, (1, 3): 815.362, (1, 4): 568.167, (1, 5): 856.500,
    (2, 3): 531.245, (2, 4): 716.617, (2, 5): 599.127,
    (3, 4): 957.990, (3, 5): 542.392,
    (4, 5): 975.931,
}


@pytest.fixture(scope="module")
def distances_now():
    return station_distances(CAMPUS, [1, 2, 3, 4, 5])


def test_every_way_between_the_spawn_and_stations_1_to_5_is_as_long_as_on_main(distances_now):
    for (start, goal), length in DISTANCES_ON_MAIN.items():
        assert distances_now[(start, goal)] == pytest.approx(length, abs=0.001), (start, goal)
        assert distances_now[(goal, start)] == pytest.approx(length, abs=0.001), (goal, start)


def test_the_pinned_table_covers_every_pair(distances_now):
    pairs = {frozenset(pair) for pair in itertools.combinations([SPAWN, 1, 2, 3, 4, 5], 2)}
    assert {frozenset(pair) for pair in DISTANCES_ON_MAIN} == pairs
    assert len(distances_now) == 2 * len(pairs)


def test_the_map_without_the_new_stations_gives_the_same_ways(distances_now):
    # Edge case: taking stations 7 to 12 away again changes nothing.
    without = dict(CAMPUS, stations=[station for station in CAMPUS["stations"] if station["id"] not in NEW_STATIONS])
    assert station_distances(without, [1, 2, 3, 4, 5]) == distances_now


@pytest.mark.parametrize("station_id", NEW_STATIONS)
def test_a_player_can_stand_on_every_new_station(station_id):
    station = next(station for station in CAMPUS["stations"] if station["id"] == station_id)
    assert is_free(station["x"], station["y"], CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
