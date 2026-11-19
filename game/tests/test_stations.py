"""Which station is in range: the rule the server and the browser share."""

import pytest

from server.world.campus import load_campus
from server.world.stations import station_in_range

CAMPUS = load_campus()
STATIONS = CAMPUS["stations"]
USE_RANGE = CAMPUS["use_range"]

# A small map for the rule alone: two stations 40 units apart on one line.
LEFT = {"id": 1, "x": 100, "y": 100}
RIGHT = {"id": 2, "x": 140, "y": 100}
TWO = [LEFT, RIGHT]


# Accepted: a station is in range

def test_standing_on_a_station_it_is_in_range():
    assert station_in_range(100, 100, TWO, 25) == 1


def test_a_station_a_few_units_away_is_in_range():
    assert station_in_range(90, 110, TWO, 25) == 1


def test_the_distance_counts_in_every_direction():
    # 15 right and 20 down is exactly 25 away, 16 and 20 is a little more.
    assert station_in_range(115, 120, [LEFT], 25) == 1
    assert station_in_range(116, 120, [LEFT], 25) is None


# Rejected: nothing in range

def test_far_from_every_station_nothing_is_in_range():
    assert station_in_range(300, 300, TWO, 25) is None


def test_just_outside_the_range_nothing_is_in_range():
    assert station_in_range(74.99, 100, TWO, 25) is None


def test_without_stations_nothing_is_in_range():
    assert station_in_range(100, 100, [], 25) is None


@pytest.mark.parametrize("x, y", [
    (float("nan"), 100), (100, float("nan")), (float("inf"), 100), (100, float("-inf")),
])
def test_a_position_that_is_not_a_real_number_is_in_range_of_nothing(x, y):
    assert station_in_range(x, y, TWO, 25) is None


# Edge cases

def test_exactly_on_the_limit_counts_as_in_range():
    assert station_in_range(75, 100, TWO, 25) == 1
    assert station_in_range(100, 125, TWO, 25) == 1


def test_with_two_in_range_the_closer_one_wins():
    assert station_in_range(119, 100, TWO, 25) == 1
    assert station_in_range(121, 100, TWO, 25) == 2


def test_the_closer_one_wins_whatever_the_order_of_the_list():
    assert station_in_range(121, 100, [RIGHT, LEFT], 25) == 2
    assert station_in_range(119, 100, [RIGHT, LEFT], 25) == 1


def test_an_exact_tie_goes_to_the_smaller_id():
    # (120, 100) is 20 away from both.
    assert station_in_range(120, 100, [LEFT, RIGHT], 25) == 1
    assert station_in_range(120, 100, [RIGHT, LEFT], 25) == 1


def test_only_usable_stations_count():
    # Station 1 is closer, but only station 2 may be used.
    assert station_in_range(119, 100, TWO, 25, usable_ids=[2]) == 2
    assert station_in_range(100, 100, TWO, 25, usable_ids=[2]) is None


def test_usable_ids_may_be_a_set():
    assert station_in_range(119, 100, TWO, 25, usable_ids={1, 2}) == 1


def test_with_no_usable_station_nothing_is_in_range():
    assert station_in_range(100, 100, TWO, 25, usable_ids=[]) is None


def test_usable_ids_none_means_all_stations():
    assert station_in_range(140, 100, TWO, 25, usable_ids=None) == 2


def test_an_id_that_is_no_station_makes_nothing_usable():
    assert station_in_range(100, 100, TWO, 25, usable_ids=[7]) is None


def test_the_rule_changes_neither_the_stations_nor_the_usable_ids():
    stations = [dict(LEFT), dict(RIGHT)]
    usable = [2, 1]
    station_in_range(119, 100, stations, 25, usable)
    assert stations == TWO and usable == [2, 1]


# The real map

def test_the_range_of_the_real_map_is_25():
    assert USE_RANGE == 25


@pytest.mark.parametrize("station", STATIONS, ids=lambda station: station["name"])
def test_on_every_station_of_the_campus_that_station_is_in_range(station):
    assert station_in_range(station["x"], station["y"], STATIONS, USE_RANGE) == station["id"]


@pytest.mark.parametrize("station", STATIONS, ids=lambda station: station["name"])
def test_at_the_limit_of_every_station_of_the_campus_it_is_still_in_range(station):
    # The stations stand far apart, so no other one can be closer.
    assert station_in_range(station["x"] - USE_RANGE, station["y"], STATIONS, USE_RANGE) == station["id"]
    assert station_in_range(station["x"] - USE_RANGE - 1, station["y"], STATIONS, USE_RANGE) is None


def test_on_the_spawn_point_no_station_is_in_range():
    spawn = CAMPUS["spawn"]
    assert station_in_range(spawn["x"], spawn["y"], STATIONS, USE_RANGE) is None


def test_on_the_campus_only_the_usable_station_is_in_range():
    second = STATIONS[1]
    assert station_in_range(second["x"], second["y"], STATIONS, USE_RANGE, usable_ids=[2]) == 2
    assert station_in_range(second["x"], second["y"], STATIONS, USE_RANGE, usable_ids=[1, 3]) is None
