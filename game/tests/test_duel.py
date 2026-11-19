"""The rules of Duel as plain functions (M2-4.7, S-94): routes, progress, end and ranking.

No server and no clock here: every test passes its own time and its own
random generator.
"""

import itertools
import random

import pytest

from server import protocol
from server.modes import duel
from server.modes.duel import Duel, all_routes, draw_routes, route_length, routes_about_as_long
from server.modes.tasks import RoundTasks
from server.world.campus import load_campus
from server.world.paths import SPAWN, station_distances

CAMPUS = load_campus()
IN_USE = [1, 2, 3, 4, 5]
REAL_DISTANCES = station_distances(CAMPUS, IN_USE)
EIGHT_NAMES = ["Mara", "Tiago", "Ines", "Rui", "Sofia", "Duarte", "Leonor", "Vasco"]
SEEDS = range(300)

START = 1000.0


def made_up_distances(length_of):
    """A table of distances in which the way to station `s` is `length_of(s)` long, from anywhere."""
    places = [SPAWN] + IN_USE
    return {
        (start, goal): length_of(goal) if goal != SPAWN else 1
        for start, goal in itertools.permutations(places, 2)
    }


# With these the way to a higher station is ten times as long, so the
# lengths of the routes lie far apart: for some routes fewer than seven
# others are within 10 %.
SPREAD_OUT = made_up_distances(lambda station: 10 ** station)
# With these every route is exactly as long as every other.
ALL_EQUAL = made_up_distances(lambda station: 100)


def is_within_tolerance(route, first, distances):
    wanted = route_length(first, distances)
    return abs(route_length(route, distances) - wanted) <= duel.LENGTH_TOLERANCE * wanted


def close_routes(first, distances):
    return [route for route in all_routes(IN_USE) if route != first and is_within_tolerance(route, first, distances)]


def duel_of(*routes_by_name, started=START):
    """A Duel with the given `(name, route)` pairs, in joining order."""
    return Duel(dict(routes_by_name), started)


def finish(the_duel, name, at):
    """Let a player finish all the stations they have left, the last one at time `at`."""
    while the_duel.next_station(name) is not None:
        assert the_duel.station_done(name, the_duel.next_station(name), at)


# Routes: the candidates


def test_there_are_sixty_routes_of_three_different_stations_out_of_five():
    routes = all_routes(IN_USE)
    assert len(routes) == 60
    assert len(set(routes)) == 60
    for route in routes:
        assert len(route) == 3
        assert len(set(route)) == 3
        assert set(route) <= set(IN_USE)


def test_the_order_of_a_route_matters():
    routes = all_routes(IN_USE)
    assert (1, 2, 3) in routes and (3, 2, 1) in routes


def test_with_six_stations_in_use_there_are_120_routes():
    assert len(all_routes([1, 2, 3, 4, 5, 6])) == 120


def test_the_length_of_a_route_starts_at_the_spawn_and_follows_the_order():
    distances = REAL_DISTANCES
    expected = distances[(SPAWN, 4)] + distances[(4, 1)] + distances[(1, 5)]
    assert route_length((4, 1, 5), distances) == pytest.approx(expected)
    assert route_length((4, 1, 5), distances) != pytest.approx(route_length((5, 1, 4), distances))


# Routes: drawing, accepted


@pytest.mark.parametrize("player_count", [1, 2, 3, 4, 5, 6, 7, 8])
def test_every_player_gets_a_route_of_their_own(player_count):
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = draw_routes(names, IN_USE, REAL_DISTANCES, random.Random(seed))
        assert list(routes) == names
        assert len(set(routes.values())) == player_count
        for route in routes.values():
            assert route in all_routes(IN_USE)


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_on_the_real_map_all_routes_are_within_ten_percent_of_one_of_them(player_count):
    # Every route of the real map has at least three others within 10 %, so
    # with up to four players the tolerance always holds. Which route was
    # drawn first is not told, so the test looks for one that fits.
    names = EIGHT_NAMES[:player_count]
    for seed in SEEDS:
        routes = list(draw_routes(names, IN_USE, REAL_DISTANCES, random.Random(seed)).values())
        assert any(
            all(is_within_tolerance(route, first, REAL_DISTANCES) for route in routes)
            for first in routes
        )


def test_every_route_of_the_real_map_has_at_least_three_others_within_ten_percent():
    assert min(len(close_routes(first, REAL_DISTANCES)) for first in all_routes(IN_USE)) >= 3


def test_for_eight_players_nearly_every_first_route_has_seven_others_within_ten_percent():
    enough = [first for first in all_routes(IN_USE) if len(close_routes(first, REAL_DISTANCES)) >= 7]
    assert len(enough) >= 55  # 58 of 60 when this was written


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 6, 7])
def test_the_other_routes_are_within_ten_percent_of_the_first_where_enough_exist(count):
    for first in all_routes(IN_USE):
        if len(close_routes(first, REAL_DISTANCES)) < count:
            continue
        for seed in range(5):
            others = routes_about_as_long(first, all_routes(IN_USE), REAL_DISTANCES, count, random.Random(seed))
            assert len(others) == count
            assert len(set(others)) == count
            assert first not in others
            assert all(is_within_tolerance(route, first, REAL_DISTANCES) for route in others)


def test_the_longest_route_of_all_is_never_given_next_to_the_shortest():
    by_length = sorted(all_routes(IN_USE), key=lambda route: route_length(route, REAL_DISTANCES))
    shortest, longest = by_length[0], by_length[-1]
    for seed in SEEDS:
        routes = draw_routes(EIGHT_NAMES, IN_USE, REAL_DISTANCES, random.Random(seed)).values()
        assert not (shortest in routes and longest in routes)


def test_the_same_seed_gives_the_same_routes():
    for seed in range(20):
        first = draw_routes(EIGHT_NAMES, IN_USE, REAL_DISTANCES, random.Random(seed))
        second = draw_routes(EIGHT_NAMES, IN_USE, REAL_DISTANCES, random.Random(seed))
        assert first == second


def test_different_seeds_give_different_routes():
    drawn = {
        tuple(draw_routes(EIGHT_NAMES[:2], IN_USE, REAL_DISTANCES, random.Random(seed)).values())
        for seed in SEEDS
    }
    assert len(drawn) > 100


def test_over_many_seeds_every_station_and_every_route_is_drawn():
    seen_routes = set()
    for seed in range(2000):
        seen_routes.update(draw_routes(EIGHT_NAMES[:2], IN_USE, REAL_DISTANCES, random.Random(seed)).values())
    assert seen_routes == set(all_routes(IN_USE))
    assert {station for route in seen_routes for station in route} == set(IN_USE)


def test_who_gets_which_route_is_random_too():
    # With equal distances any route can be the first; over many seeds the
    # first player must not always hold the route that was drawn first.
    holders = set()
    for seed in SEEDS:
        rng = random.Random(seed)
        first_drawn = random.Random(seed).choice(all_routes(IN_USE))
        routes = draw_routes(EIGHT_NAMES[:4], IN_USE, ALL_EQUAL, rng)
        holders.add(next(name for name, route in routes.items() if route == first_drawn))
    assert holders == set(EIGHT_NAMES[:4])


def test_nobody_is_told_anything_through_the_order_of_the_names():
    routes = draw_routes(["Tiago", "Mara"], IN_USE, REAL_DISTANCES, random.Random(1))
    assert list(routes) == ["Tiago", "Mara"]


# Routes: drawing, the fallback and edge cases


def test_where_too_few_routes_are_close_the_nearest_in_length_are_taken():
    candidates = all_routes(IN_USE)
    with_too_few = [first for first in candidates if len(close_routes(first, SPREAD_OUT)) < 7]
    assert len(with_too_few) >= 6
    for first in with_too_few:
        others = routes_about_as_long(first, candidates, SPREAD_OUT, 7, random.Random(0))
        assert len(set(others)) == 7 and first not in others

        def difference(route):
            return abs(route_length(route, SPREAD_OUT) - route_length(first, SPREAD_OUT))

        # Nobody who was left out is nearer than somebody who was taken, and
        # the routes that are within 10 % are all among the taken ones.
        left_out = [route for route in candidates if route != first and route not in others]
        assert max(difference(route) for route in others) <= min(difference(route) for route in left_out)
        assert set(close_routes(first, SPREAD_OUT)) <= set(others)


def test_the_fallback_does_not_depend_on_chance():
    first = (1, 2, 3)
    assert len(close_routes(first, SPREAD_OUT)) < 7
    one = routes_about_as_long(first, all_routes(IN_USE), SPREAD_OUT, 7, random.Random(1))
    other = routes_about_as_long(first, all_routes(IN_USE), SPREAD_OUT, 7, random.Random(2))
    assert one == other


def test_eight_players_get_eight_routes_even_when_none_are_close():
    for seed in range(50):
        routes = draw_routes(EIGHT_NAMES, IN_USE, SPREAD_OUT, random.Random(seed))
        assert len(set(routes.values())) == 8


def test_with_equal_distances_every_route_is_close_and_any_can_be_drawn():
    seen = set()
    for seed in SEEDS:
        seen.update(draw_routes(EIGHT_NAMES, IN_USE, ALL_EQUAL, random.Random(seed)).values())
    assert seen == set(all_routes(IN_USE))


def test_a_route_exactly_ten_percent_longer_is_still_close_and_one_just_beyond_is_not():
    # Routes of one station keep the numbers simple: the first is 100 long,
    # the others 110 (exactly 10 % more) and 111.
    distances = made_up_distances(lambda station: {1: 100, 2: 110, 3: 111}.get(station, 0))
    assert is_within_tolerance((2,), (1,), distances)
    assert not is_within_tolerance((3,), (1,), distances)
    for seed in range(20):
        assert routes_about_as_long((1,), [(1,), (2,), (3,)], distances, 1, random.Random(seed)) == [(2,)]


def test_one_player_gets_one_route_and_nobody_gets_none():
    assert len(draw_routes(["Mara"], IN_USE, REAL_DISTANCES, random.Random(0))) == 1
    assert draw_routes([], IN_USE, REAL_DISTANCES, random.Random(0)) == {}


# The round: the order of the stations


def test_at_the_start_everybody_needs_the_first_station_of_their_route():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.next_station("Mara") == 3
    assert the_duel.next_station("Tiago") == 2
    assert the_duel.stations_needed("Mara") == [3]
    assert the_duel.state_of("Mara") == (3, 0, None)
    assert the_duel.progress() == [("Mara", 0), ("Tiago", 0)]


def test_a_finished_station_brings_the_next_one():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.station_done("Mara", 3, START + 10) is True
    assert the_duel.next_station("Mara") == 1
    assert the_duel.state_of("Mara") == (1, 1, None)
    assert the_duel.station_done("Mara", 1, START + 20) is True
    assert the_duel.state_of("Mara") == (5, 2, None)
    # Tiago's route did not move.
    assert the_duel.state_of("Tiago") == (2, 0, None)
    assert the_duel.progress() == [("Mara", 2), ("Tiago", 0)]


@pytest.mark.parametrize("wrong_station", [1, 5, 2, 4, 6, 0, None])
def test_a_station_that_is_not_the_next_one_changes_nothing_and_says_so(wrong_station):
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.station_done("Mara", wrong_station, START + 10) is False
    assert the_duel.state_of("Mara") == (3, 0, None)
    assert the_duel.take_news() is False


def test_a_station_done_before_cannot_be_counted_again():
    the_duel = duel_of(("Mara", (3, 1, 5)))
    assert the_duel.station_done("Mara", 3, START + 10) is True
    assert the_duel.station_done("Mara", 3, START + 11) is False
    assert the_duel.state_of("Mara") == (1, 1, None)


def test_a_player_who_is_not_in_the_duel_counts_nothing():
    the_duel = duel_of(("Mara", (3, 1, 5)))
    assert the_duel.station_done("Rui", 3, START + 10) is False
    assert the_duel.next_station("Rui") is None
    assert the_duel.stations_needed("Rui") == []
    assert the_duel.progress() == [("Mara", 0)]


def test_the_frame_of_the_minigames_lets_a_player_open_only_the_next_station():
    # The Duel's function is what `RoundTasks` asks before it opens a station.
    the_duel = duel_of(("Mara", (3, 1, 5)))
    stations = {station["id"]: station for station in CAMPUS["stations"]}
    round_tasks = RoundTasks(CAMPUS["stations"], CAMPUS["use_range"], needed_stations=the_duel.stations_needed)
    rng = random.Random(0)
    for station in (1, 2, 4, 5):
        at_station = (stations[station]["x"], stations[station]["y"])
        assert round_tasks.open("Mara", station, at_station, START, rng) == (None, "station_not_needed")
    opened, rejection_code = round_tasks.open("Mara", 3, (stations[3]["x"], stations[3]["y"]), START, rng)
    assert rejection_code is None and opened["station"] == 3


# The round: finishing


def test_the_third_station_sets_the_time_from_the_start_of_the_round():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    the_duel.station_done("Mara", 3, START + 20)
    the_duel.station_done("Mara", 1, START + 50)
    assert the_duel.station_done("Mara", 5, START + 72.44) is True
    assert the_duel.next_station("Mara") is None
    assert the_duel.stations_needed("Mara") == []
    assert the_duel.state_of("Mara") == (None, 3, 72.4)


def test_a_finished_player_cannot_count_anything_more_and_keeps_the_time():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    finish(the_duel, "Mara", START + 60)
    for station in (3, 1, 5, 2, 4):
        assert the_duel.station_done("Mara", station, START + 99) is False
    assert the_duel.state_of("Mara") == (None, 3, 60.0)


def test_taking_back_the_last_station_lets_the_player_do_it_again():
    the_duel = duel_of(("Mara", (3, 1, 5)))
    the_duel.station_done("Mara", 3, START + 10)
    the_duel.take_back("Mara", 3)
    assert the_duel.state_of("Mara") == (3, 0, None)
    assert the_duel.station_done("Mara", 3, START + 30) is True


def test_taking_back_the_third_station_takes_the_time_back_too():
    the_duel = duel_of(("Mara", (3, 1, 5)))
    finish(the_duel, "Mara", START + 60)
    the_duel.take_back("Mara", 5)
    assert the_duel.state_of("Mara") == (5, 2, None)
    assert the_duel.is_over(START + 61) is False


@pytest.mark.parametrize("station", [3, 5, 2, 9, None])
def test_only_the_station_counted_last_can_be_taken_back(station):
    the_duel = duel_of(("Mara", (3, 1, 5)))
    the_duel.station_done("Mara", 3, START + 10)
    the_duel.station_done("Mara", 1, START + 20)
    the_duel.take_back("Mara", station)
    assert the_duel.state_of("Mara") == (5, 2, None)


def test_taking_back_with_nothing_counted_or_for_a_stranger_changes_nothing():
    the_duel = duel_of(("Mara", (3, 1, 5)))
    the_duel.take_back("Mara", 3)
    the_duel.take_back("Rui", 3)
    assert the_duel.state_of("Mara") == (3, 0, None)


# The round: when it is over


def test_a_new_duel_is_not_over():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.is_over(START) is False
    assert the_duel.everybody_finished() is False


def test_it_is_over_when_everybody_has_finished():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    finish(the_duel, "Mara", START + 60)
    assert the_duel.is_over(START + 60) is False
    finish(the_duel, "Tiago", START + 90)
    assert the_duel.is_over(START + 90) is True
    assert the_duel.everybody_finished() is True
    assert the_duel.time_is_up(START + 90) is False


def test_it_is_over_at_exactly_180_seconds_and_not_one_second_before():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.is_over(START + 179) is False
    assert the_duel.is_over(START + 179.99) is False
    assert the_duel.is_over(START + 180) is True
    assert the_duel.time_is_up(START + 180) is True
    assert the_duel.is_over(START + 500) is True
    assert the_duel.everybody_finished() is False


def test_the_round_lasts_three_minutes():
    assert duel.ROUND_SECONDS == 180
    assert duel.STATIONS_PER_ROUTE == 3


def test_after_a_player_left_the_others_decide_whether_it_is_over():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)))
    finish(the_duel, "Mara", START + 60)
    finish(the_duel, "Ines", START + 70)
    assert the_duel.is_over(START + 70) is False
    the_duel.remove("Tiago")
    assert the_duel.is_over(START + 70) is True


def test_a_duel_goes_on_for_a_single_player():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    the_duel.remove("Tiago")
    assert the_duel.is_over(START + 10) is False
    assert the_duel.names() == ["Mara"]
    finish(the_duel, "Mara", START + 60)
    assert the_duel.is_over(START + 60) is True


def test_a_duel_everybody_left_is_over():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    the_duel.remove("Mara")
    the_duel.remove("Tiago")
    assert the_duel.is_over(START) is True
    assert the_duel.progress() == []
    assert the_duel.ranking() == []


def test_removing_a_player_twice_or_a_stranger_is_harmless():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    the_duel.remove("Tiago")
    the_duel.remove("Tiago")
    the_duel.remove("Rui")
    assert the_duel.progress() == [("Mara", 0)]


# The round: the clock


@pytest.mark.parametrize(
    "seconds_after_the_start, expected",
    [(0, 180), (0.01, 180), (0.99, 180), (1, 179), (28.2, 152), (179, 1), (179.01, 1), (180, 0), (180.5, 0), (999, 0)],
)
def test_the_seconds_left_are_whole_rounded_up_and_never_below_zero(seconds_after_the_start, expected):
    the_duel = duel_of(("Mara", (3, 1, 5)))
    left = the_duel.seconds_left(START + seconds_after_the_start)
    assert left == expected
    assert type(left) is int


# The round: news for the others


def test_there_is_news_after_a_count_and_after_a_player_left_and_only_once():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    assert the_duel.take_news() is False
    the_duel.station_done("Mara", 3, START + 10)
    assert the_duel.take_news() is True
    assert the_duel.take_news() is False
    the_duel.remove("Tiago")
    assert the_duel.take_news() is True
    assert the_duel.take_news() is False


# The ranking


def row(place, name, seconds, done):
    return {"place": place, "name": name, "seconds": seconds, "done": done}


def test_players_who_finished_are_ranked_by_their_time():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)))
    finish(the_duel, "Tiago", START + 95.04)
    finish(the_duel, "Ines", START + 61.25)
    finish(the_duel, "Mara", START + 72.449)
    assert the_duel.ranking() == [
        row(1, "Ines", 61.2, 3),
        row(2, "Mara", 72.4, 3),
        row(3, "Tiago", 95.0, 3),
    ]


def test_players_who_did_not_finish_come_after_by_stations_done():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)), ("Rui", (1, 2, 3)))
    the_duel.station_done("Mara", 3, START + 5)
    the_duel.station_done("Ines", 4, START + 30)
    the_duel.station_done("Ines", 5, START + 60)
    finish(the_duel, "Rui", START + 170)
    assert the_duel.ranking() == [
        row(1, "Rui", 170.0, 3),
        row(2, "Ines", None, 2),
        row(3, "Mara", None, 1),
        row(4, "Tiago", None, 0),
    ]


def test_a_late_finisher_still_beats_a_player_with_two_stations_done_early():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    the_duel.station_done("Mara", 3, START + 5)
    the_duel.station_done("Mara", 1, START + 10)
    finish(the_duel, "Tiago", START + 179)
    assert [entry["name"] for entry in the_duel.ranking()] == ["Tiago", "Mara"]


def test_equal_results_share_a_place_and_the_next_place_is_skipped():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)), ("Rui", (1, 2, 3)))
    finish(the_duel, "Rui", START + 50)
    the_duel.station_done("Tiago", 2, START + 20)
    the_duel.station_done("Mara", 3, START + 90)
    assert the_duel.ranking() == [
        row(1, "Rui", 50.0, 3),
        row(2, "Mara", None, 1),
        row(2, "Tiago", None, 1),
        row(4, "Ines", None, 0),
    ]


def test_equal_times_share_a_place_in_joining_order():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)))
    finish(the_duel, "Ines", START + 80)
    finish(the_duel, "Tiago", START + 64.44)
    finish(the_duel, "Mara", START + 64.41)  # the same tenth of a second as Tiago
    assert the_duel.ranking() == [
        row(1, "Mara", 64.4, 3),
        row(1, "Tiago", 64.4, 3),
        row(3, "Ines", 80.0, 3),
    ]


def test_with_nobody_finished_everybody_with_the_same_count_shares_a_place():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)))
    assert the_duel.ranking() == [
        row(1, "Mara", None, 0),
        row(1, "Tiago", None, 0),
        row(1, "Ines", None, 0),
    ]


def test_a_player_who_left_is_in_neither_progress_nor_ranking():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)), ("Ines", (4, 5, 2)))
    finish(the_duel, "Tiago", START + 40)
    the_duel.station_done("Ines", 4, START + 50)
    the_duel.remove("Tiago")
    assert the_duel.progress() == [("Mara", 0), ("Ines", 1)]
    assert the_duel.ranking() == [row(1, "Ines", None, 1), row(2, "Mara", None, 0)]


def test_asking_for_the_ranking_twice_gives_the_same_rows():
    the_duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    finish(the_duel, "Tiago", START + 40)
    assert the_duel.ranking() == the_duel.ranking()


# The messages (S-94)


def test_duel_state_names_the_next_station_and_no_time_while_the_player_is_running():
    assert protocol.duel_state(3, 1, 3) == {"type": "duel_state", "next_station": 3, "done": 1, "total": 3}


def test_duel_state_of_a_finished_player_has_no_station_and_the_time():
    assert protocol.duel_state(None, 3, 3, 72.4) == {
        "type": "duel_state", "next_station": None, "done": 3, "total": 3, "seconds": 72.4,
    }


def test_duel_progress_lists_names_and_counts_and_no_station():
    message = protocol.duel_progress([("Mara", 1), ("Tiago", 0)], 3, 151)
    assert message == {
        "type": "duel_progress",
        "players": [{"name": "Mara", "done": 1}, {"name": "Tiago", "done": 0}],
        "total": 3,
        "seconds_left": 151,
    }


def test_duel_result_carries_the_ranking_and_whether_the_time_ran_out():
    ranking = [row(1, "Mara", 72.4, 3), row(2, "Tiago", None, 2)]
    assert protocol.duel_result(ranking, False) == {
        "type": "duel_result",
        "ranking": [
            {"place": 1, "name": "Mara", "seconds": 72.4, "done": 3},
            {"place": 2, "name": "Tiago", "seconds": None, "done": 2},
        ],
        "time_up": False,
    }
    assert protocol.duel_result([], True) == {"type": "duel_result", "ranking": [], "time_up": True}


# The small rules the Duel needs from the lobby and from the frame of the minigames


def test_ending_the_round_opens_the_lobby_again_and_forgets_the_round():
    from server.net.lobbies import Lobbies

    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobbies.start("Mara")
    lobby.tasks = RoundTasks(CAMPUS["stations"], CAMPUS["use_range"])
    lobby.duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    lobby.end_round()
    assert lobby.phase == "lobby" and lobby.tasks is None and lobby.duel is None
    assert lobby.names() == ["Mara", "Tiago"] and lobby.host == "Mara"
    # The host can start again, and a third player can join now.
    assert lobbies.join("Ines", "ABCD")[1] is None
    assert lobbies.start("Mara")[1] is None


def test_a_player_removed_from_the_lobby_is_removed_from_its_duel():
    from server.net.lobbies import Lobbies

    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobbies.start("Mara")
    lobby.duel = duel_of(("Mara", (3, 1, 5)), ("Tiago", (2, 4, 1)))
    lobbies.leave("Tiago")
    assert lobby.duel.names() == ["Mara"]


def test_a_count_of_the_frame_can_be_taken_back_and_the_station_opens_again():
    stations = {station["id"]: station for station in CAMPUS["stations"]}
    at_station_3 = (stations[3]["x"], stations[3]["y"])
    round_tasks = RoundTasks(CAMPUS["stations"], CAMPUS["use_range"])
    rng = random.Random(0)
    round_tasks.open("Mara", 3, at_station_3, START, rng)
    assert round_tasks.finish("Mara", START + 5) == (3, None)
    assert round_tasks.open("Mara", 3, at_station_3, START + 6, rng) == (None, "station_not_needed")
    round_tasks.take_back("Mara", 3)
    assert round_tasks.finished_by("Mara") == set()
    opened, rejection_code = round_tasks.open("Mara", 3, at_station_3, START + 7, rng)
    assert rejection_code is None


def test_taking_back_what_was_never_counted_changes_nothing():
    round_tasks = RoundTasks(CAMPUS["stations"], CAMPUS["use_range"])
    round_tasks.take_back("Mara", 3)
    round_tasks.take_back("Rui", 9)
    assert round_tasks.finished_by("Mara") == set()
