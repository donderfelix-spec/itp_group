"""Different first stations in a Duel (Lennart's request, S-94 and S-97 stay).

`draw_routes` gives every player a different first station as long as there
are enough stations. With more players than stations the first stations are
spread as evenly as possible, and with more players than routes even the
routes are given again, evenly. It never raises for 0 to 8 players and a
pool of at least three stations.

The pools: the twelve active stations, the five original stations, and
three stations as the smallest edge case.
"""

import itertools
import random
from collections import Counter

import pytest

from server.modes import duel
from server.modes.duel import LENGTH_TOLERANCE, all_routes, draw_routes, route_length
from server.world.campus import load_campus
from server.world.paths import SPAWN, station_distances

CAMPUS = load_campus()
TWELVE = list(range(1, 13))
FIVE = [1, 2, 3, 4, 5]
THREE = [1, 2, 3]
REAL_TWELVE = station_distances(CAMPUS, TWELVE)
REAL_FIVE = station_distances(CAMPUS, FIVE)
REAL_THREE = station_distances(CAMPUS, THREE)
EIGHT_NAMES = ["Mara", "Tiago", "Ines", "Rui", "Sofia", "Duarte", "Leonor", "Vasco"]
SEEDS = range(100)

POOLS = {
    "twelve": (TWELVE, REAL_TWELVE),
    "five": (FIVE, REAL_FIVE),
    "three": (THREE, REAL_THREE),
}


def made_up_distances(stations, length_of):
    """A table in which the way to station `s` is `length_of(s)` long, from anywhere."""
    places = [SPAWN] + list(stations)
    return {
        (start, goal): length_of(goal) if goal != SPAWN else 1
        for start, goal in itertools.permutations(places, 2)
    }


def is_close(route, first, distances):
    wanted = route_length(first, distances)
    return abs(route_length(route, distances) - wanted) <= LENGTH_TOLERANCE * wanted


def spread(counts, total, places):
    """Whether `total` uses are spread over `places` as evenly as possible."""
    values = [counts.get(place, 0) for place in places]
    return sum(values) == total and max(values) - min(values) <= 1


# Accepted: as many stations as players or more


@pytest.mark.parametrize("player_count", range(1, 9))
def test_with_twelve_stations_nobody_shares_a_first_station(player_count):
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = draw_routes(names, TWELVE, REAL_TWELVE, random.Random(seed))
        assert list(routes) == names
        assert len({route[0] for route in routes.values()}) == player_count
        assert len(set(routes.values())) == player_count
        for route in routes.values():
            assert len(set(route)) == 3 and set(route) <= set(TWELVE)


@pytest.mark.parametrize("player_count", range(1, 6))
def test_with_five_stations_up_to_five_players_never_share_a_first_station(player_count):
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = draw_routes(names, FIVE, REAL_FIVE, random.Random(seed))
        assert len({route[0] for route in routes.values()}) == player_count
        assert len(set(routes.values())) == player_count


@pytest.mark.parametrize("player_count", range(2, 9))
def test_on_the_real_twelve_stations_all_routes_stay_within_ten_percent_of_one_of_them(player_count):
    # On the real map every number of players finds routes within 10 % that
    # also start at different stations, so the tolerance of S-94 holds.
    names = EIGHT_NAMES[:player_count]
    for seed in range(40):
        routes = list(draw_routes(names, TWELVE, REAL_TWELVE, random.Random(seed)).values())
        assert any(all(is_close(route, first, REAL_TWELVE) for route in routes) for first in routes)


def test_one_player_can_get_any_first_station_and_the_same_seed_gives_the_same_route():
    first_stations = set()
    for seed in range(300):
        routes = draw_routes(["Mara"], TWELVE, REAL_TWELVE, random.Random(seed))
        assert list(routes) == ["Mara"]
        assert routes == draw_routes(["Mara"], TWELVE, REAL_TWELVE, random.Random(seed))
        first_stations.add(routes["Mara"][0])
    assert first_stations == set(TWELVE)


def test_where_enough_first_stations_have_close_routes_every_route_is_close_to_the_first():
    candidates = all_routes(TWELVE)
    for seed in range(60):
        first = random.Random(seed).choice(candidates)
        close_starts = {route[0] for route in candidates if route[0] != first[0] and is_close(route, first, REAL_TWELVE)}
        count = min(8, len(close_starts) + 1)
        routes = draw_routes(EIGHT_NAMES[:count], TWELVE, REAL_TWELVE, random.Random(seed))
        # The route drawn first was kept, and all others are close to it.
        assert first in routes.values()
        assert all(is_close(route, first, REAL_TWELVE) for route in routes.values())
        assert len({route[0] for route in routes.values()}) == count


def test_a_different_first_station_comes_before_a_route_of_the_same_length():
    # Every way to station 1 is 100 long, every way to the others 1000: the
    # second player still gets a route that starts elsewhere, the nearest
    # in length of those.
    distances = made_up_distances(FIVE, lambda station: 100 if station == 1 else 1000)
    for seed in range(30):
        routes = draw_routes(EIGHT_NAMES[:2], FIVE, distances, random.Random(seed))
        assert len({route[0] for route in routes.values()}) == 2


# Edge cases: more players than stations, or than routes


@pytest.mark.parametrize("player_count", [6, 7, 8])
def test_with_five_stations_six_to_eight_players_share_first_stations_evenly(player_count):
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = draw_routes(names, FIVE, REAL_FIVE, random.Random(seed))
        assert list(routes) == names
        assert len(set(routes.values())) == player_count
        assert spread(Counter(route[0] for route in routes.values()), player_count, FIVE)


@pytest.mark.parametrize("player_count", range(0, 9))
def test_with_three_stations_nothing_raises_and_everybody_gets_a_route(player_count):
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = draw_routes(names, THREE, REAL_THREE, random.Random(seed))
        assert list(routes) == names
        given = list(routes.values())
        assert spread(Counter(route[0] for route in given), player_count, THREE)
        # Three stations make only six routes: up to six players they are all
        # different, beyond that a route is given twice before any thrice.
        if player_count <= 6:
            assert len(set(given)) == player_count
        else:
            assert max(Counter(given).values()) == 2


def test_with_three_stations_and_eight_players_every_route_is_given():
    routes = draw_routes(EIGHT_NAMES, THREE, REAL_THREE, random.Random(0))
    assert set(routes.values()) == set(all_routes(THREE))


@pytest.mark.parametrize("pool", POOLS)
@pytest.mark.parametrize("player_count", range(0, 9))
def test_no_pool_and_no_number_of_players_raises(pool, player_count):
    stations, distances = POOLS[pool]
    spread_out = made_up_distances(stations, lambda station: 10 ** (stations.index(station) % 6))
    for table in (distances, spread_out):
        for seed in range(20):
            routes = draw_routes(EIGHT_NAMES[:player_count], stations, table, random.Random(seed))
            assert len(routes) == player_count
            first_stations = Counter(route[0] for route in routes.values())
            assert spread(first_stations, player_count, stations)
            if player_count <= len(stations):
                assert len(first_stations) == player_count


def test_the_same_seed_gives_the_same_routes_with_more_players_than_stations():
    for seed in range(20):
        one = draw_routes(EIGHT_NAMES, FIVE, REAL_FIVE, random.Random(seed))
        other = draw_routes(EIGHT_NAMES, FIVE, REAL_FIVE, random.Random(seed))
        assert one == other


# The helpers


def test_least_used_prefers_unused_routes_and_then_unused_first_stations():
    candidates = all_routes(THREE)
    assert duel.least_used([], candidates) == candidates
    allowed = duel.least_used([(1, 2, 3)], candidates)
    assert allowed == [(2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]
    # Every route given once: all six are allowed again.
    assert duel.least_used(candidates, candidates) == candidates


def test_a_first_route_without_close_routes_elsewhere_is_drawn_again():
    # On the real map with five stations, 13 of the 60 routes have fewer than
    # three other first stations with a route within 10 %. They are never
    # kept as the first route of four players.
    candidates = all_routes(FIVE)
    lacking = [route for route in candidates if not duel.has_close_routes_from_other_starts(route, candidates, REAL_FIVE, 3)]
    assert lacking
    for seed in range(100):
        first = duel.draw_first_route(candidates, REAL_FIVE, 4, random.Random(seed))
        assert first not in lacking


def test_if_no_first_route_has_enough_close_routes_the_first_drawn_is_kept():
    # The way from the spawn decides the length: routes that start at
    # different stations are at least ten times apart.
    distances = {pair: 1 for pair in itertools.permutations([SPAWN] + FIVE, 2)}
    distances.update({(SPAWN, station): 10 ** station for station in FIVE})
    candidates = all_routes(FIVE)
    assert not any(duel.has_close_routes_from_other_starts(route, candidates, distances, 1) for route in candidates)
    for seed in range(10):
        drawn = random.Random(seed).choice(candidates)
        assert duel.draw_first_route(candidates, distances, 8, random.Random(seed)) == drawn
