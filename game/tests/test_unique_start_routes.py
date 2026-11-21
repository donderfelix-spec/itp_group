"""The server gives every participant a different first task, including full lobbies."""
import random

import pytest

from server.modes import duel, minigames
from server.world.campus import load_campus
from server.world.paths import station_distances

ACTIVE = sorted(minigames.MINIGAMES)
DISTANCES = station_distances(load_campus(), ACTIVE)
NAMES = ['Mara', 'Tiago', 'Ines', 'Rui', 'Sofia', 'Duarte', 'Leonor', 'Vasco']


@pytest.mark.parametrize('player_count', range(2, 9))
def test_two_to_eight_players_never_share_their_first_task_over_many_seeds(player_count):
    assert ACTIVE == [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    names = NAMES[:player_count]
    for seed in range(300):
        routes = duel.draw_routes(names, ACTIVE, DISTANCES, random.Random(seed))
        assert list(routes) == names
        assert len({route[0] for route in routes.values()}) == player_count
        assert len(set(routes.values())) == player_count
        for route in routes.values():
            assert len(route) == len(set(route)) == 3
            assert set(route) <= set(ACTIVE)


def test_solo_test_mode_still_gets_one_random_route_and_can_draw_every_first_task():
    first_tasks = set()
    for seed in range(300):
        routes = duel.draw_routes(['Mara'], ACTIVE, DISTANCES, random.Random(seed))
        assert list(routes) == ['Mara']
        assert len(set(routes['Mara'])) == 3
        first_tasks.add(routes['Mara'][0])
        assert routes == duel.draw_routes(['Mara'], ACTIVE, DISTANCES, random.Random(seed))
    assert first_tasks == set(ACTIVE)


@pytest.mark.parametrize('player_count', [6, 7, 8])
def test_more_players_than_available_first_tasks_are_explicitly_refused(player_count):
    with pytest.raises(ValueError, match='different starting station'):
        duel.draw_routes(NAMES[:player_count], ACTIVE[:5], DISTANCES, random.Random(0))


def test_close_route_selection_compares_distinct_starting_stations_not_full_routes():
    # The nearest alternatives are2then3then4; route5 is much longer.
    candidates = [(1,), (2,), (3,), (4,), (5,)]
    lengths = {1: 100, 2: 105, 3: 130, 4: 150, 5: 250}
    distances = {('spawn', station): length for station, length in lengths.items()}
    for seed in range(20):
        selected = duel.routes_with_different_starts((1,), candidates, distances, 3, random.Random(seed))
        assert selected == [(2,), (3,), (4,)]


def test_whenever_enough_distinct_starts_are_close_all_selected_routes_stay_close():
    candidates = duel.all_routes(ACTIVE)
    for seed in range(100):
        anchor = random.Random(seed).choice(candidates)
        wanted = duel.route_length(anchor, DISTANCES)
        close_starts = {route[0] for route in candidates
                        if abs(duel.route_length(route, DISTANCES) - wanted) <= duel.LENGTH_TOLERANCE * wanted}
        count = min(8, len(close_starts))
        routes = duel.draw_routes(NAMES[:count], ACTIVE, DISTANCES, random.Random(seed))
        assert len({route[0] for route in routes.values()}) == count
        assert all(abs(duel.route_length(route, DISTANCES) - wanted) <= duel.LENGTH_TOLERANCE * wanted
                   for route in routes.values())
