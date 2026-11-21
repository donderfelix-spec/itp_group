"""Additional tasks remain physically usable after upstream map decoration.

Historical furniture/distance comparisons in test_campus_detail.py measure
only the original five stations. These checks cover every active task on the
current map, including the six additional room tasks.
"""

import itertools

import pytest

from server.modes import minigames
from server.world.campus import load_campus
from server.world.movement import is_free
from server.world.paths import SPAWN, station_distances

CAMPUS = load_campus()
STATIONS = {station["id"]: station for station in CAMPUS["stations"]}


@pytest.mark.parametrize("station_id", range(7, 13))
def test_additional_task_centres_are_clear_of_the_current_furniture(station_id):
    station = STATIONS[station_id]
    assert is_free(station["x"], station["y"], CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])


def test_every_active_task_remains_reachable_on_the_current_map():
    active = sorted(minigames.MINIGAMES)
    distances = station_distances(CAMPUS, active)
    places = [SPAWN] + active
    assert set(distances) == set(itertools.permutations(places, 2))
    assert all(distance is not None and distance > 0 for distance in distances.values())
