"""Walking distances on the map, as plain functions (M2-4.7, S-94).

First on small maps made by hand, where the right answer is easy to see,
then on the real campus.
"""

import itertools
import math
import time

import pytest

from server.world import paths
from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE, is_free
from server.world.paths import SPAWN, PathError, station_distances, walking_distances

CAMPUS = load_campus()
STATIONS = {station["id"]: station for station in CAMPUS["stations"]}
IN_USE = [1, 2, 3, 4, 5]
USE_RANGE = CAMPUS["use_range"]

# A small empty map: 200 x 100 units, no solids.
WIDTH = 200
HEIGHT = 100


def wall(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def distance_between(start, goal, solids=(), width=WIDTH, height=HEIGHT):
    """The walking distance between two points that have to be reached exactly."""
    places = {"start": (start[0], start[1], 0), "goal": (goal[0], goal[1], 0)}
    return walking_distances(places, list(solids), width, height)[("start", "goal")]


@pytest.fixture(scope="module")
def real_distances():
    return station_distances(CAMPUS, IN_USE)


# Small maps: accepted


def test_a_straight_line_is_as_long_as_it_looks():
    assert distance_between((20, 40), (120, 40)) == pytest.approx(100)
    assert distance_between((20, 20), (20, 80)) == pytest.approx(60)


def test_a_diagonal_is_longer_than_its_sides_by_the_square_root_of_two():
    assert distance_between((20, 20), (60, 60)) == pytest.approx(40 * math.sqrt(2))


def test_a_knight_like_way_is_a_diagonal_and_a_straight_part():
    # 80 to the right and 40 down: 40 diagonally, then 40 straight.
    assert distance_between((20, 20), (100, 60)) == pytest.approx(40 * math.sqrt(2) + 40)


def test_a_place_is_no_distance_from_itself_and_not_listed():
    places = {"a": (20, 20, 0), "b": (20, 20, 0)}
    distances = walking_distances(places, [], WIDTH, HEIGHT)
    assert distances == {("a", "b"): 0, ("b", "a"): 0}


def test_a_wall_with_a_door_has_to_be_walked_around():
    # A wall across the whole map at x = 100, with a door from y = 60 to y = 100.
    solids = [wall(96, 0, 8, 60)]
    straight = distance_between((40, 20), (160, 20))
    around = distance_between((40, 20), (160, 20), solids)
    assert straight == pytest.approx(120)
    # Down to the door and up again: clearly longer than the straight line,
    # and never shorter than the way over the door's nearest free corner.
    corner = (100, 60 + PLAYER_HALF_SIZE)
    shortest_possible = math.dist((40, 20), corner) + math.dist(corner, (160, 20))
    assert around >= shortest_possible - 1
    assert around <= shortest_possible * 1.09  # a grid path is at most 8 % longer


def test_a_way_does_not_cut_through_the_corner_of_a_solid():
    block = wall(40, 40, 20, 20)
    # Both ends are free, but a player walking the diagonal between them
    # would clip the block's lower left corner: the point beside it, (36, 64),
    # is not free. So the way is two straight steps, not one diagonal one.
    start, goal = (36, 68), (32, 64)
    assert is_free(*start, [block], WIDTH, HEIGHT) and is_free(*goal, [block], WIDTH, HEIGHT)
    assert not is_free(36, 64, [block], WIDTH, HEIGHT)
    assert distance_between(start, goal, [block]) == pytest.approx(8)
    # Without the block the same step is a plain diagonal.
    assert distance_between(start, goal) == pytest.approx(4 * math.sqrt(2))


def test_a_station_counts_as_reached_at_the_nearest_free_point_in_its_range():
    # The "station" sits inside a tall block. The nearest place to stand on
    # the grid is 16 units to its left, at (84, 40): the block begins at
    # x = 92, and half a player has to fit in front of it.
    block = wall(92, 20, 16, 40)
    places = {"start": (20, 40, 0), "station": (100, 40, 25)}
    distances = walking_distances(places, [block], WIDTH, HEIGHT)
    assert distances[("start", "station")] == pytest.approx(84 - 20)


def test_two_equally_near_points_of_a_station_give_the_same_answer_every_time():
    # Above, below, left and right of this block are equally near. The rule
    # takes the one further up, so the result never depends on chance.
    block = wall(92, 32, 16, 16)
    places = {"start": (100, 8, 0), "station": (100, 40, 25)}
    distances = walking_distances(places, [block], WIDTH, HEIGHT)
    assert distances[("start", "station")] == pytest.approx(24 - 8)


def test_distances_are_the_same_in_both_directions_on_a_small_map():
    solids = [wall(96, 0, 8, 60), wall(40, 70, 30, 10)]
    places = {"a": (20, 20, 0), "b": (160, 20, 0), "c": (60, 92, 0)}
    distances = walking_distances(places, solids, WIDTH, HEIGHT)
    for first, second in itertools.permutations(places, 2):
        assert distances[(first, second)] == pytest.approx(distances[(second, first)])


# Small maps: rejected and edge cases


def test_a_place_behind_a_closed_wall_has_no_distance():
    closed = [wall(96, 0, 8, HEIGHT)]
    assert distance_between((40, 20), (160, 20), closed) is None
    assert distance_between((160, 20), (40, 20), closed) is None


def test_a_place_inside_a_solid_has_no_distance():
    block = wall(80, 20, 40, 40)
    assert distance_between((20, 40), (100, 40), [block]) is None


def test_a_place_outside_the_map_has_no_distance():
    assert distance_between((20, 40), (400, 40)) is None


def test_a_station_without_a_free_point_in_range_has_no_distance():
    block = wall(60, 0, 80, HEIGHT)
    places = {"start": (20, 40, 0), "station": (100, 40, 25)}
    assert walking_distances(places, [block], WIDTH, HEIGHT)[("start", "station")] is None


def test_one_unreachable_place_does_not_spoil_the_others():
    closed = [wall(96, 0, 8, HEIGHT)]
    places = {"a": (20, 20, 0), "b": (60, 20, 0), "far": (160, 20, 0)}
    distances = walking_distances(places, closed, WIDTH, HEIGHT)
    assert distances[("a", "b")] == pytest.approx(40)
    assert distances[("a", "far")] is None
    assert distances[("far", "b")] is None


def test_a_gap_that_is_too_narrow_for_a_player_is_no_way():
    # The door is 8 units high, a player is 10.
    solids = [wall(96, 0, 8, 46), wall(96, 54, 8, 46)]
    assert distance_between((40, 48), (160, 48), solids) is None


def test_a_gap_just_wide_enough_for_a_player_is_a_way():
    # The door is 12 units high and a grid line runs through its middle.
    solids = [wall(96, 0, 8, 42), wall(96, 54, 8, 46)]
    assert distance_between((40, 48), (160, 48), solids) == pytest.approx(120)


def test_a_map_whose_station_cannot_be_reached_is_refused_with_a_clear_error():
    campus = dict(CAMPUS)
    # A box around station 5: nobody can come into its range.
    station = STATIONS[5]
    box = wall(station["x"] - 40, station["y"] - 40, 80, 80)
    campus["solids"] = CAMPUS["solids"] + [box]
    with pytest.raises(PathError, match="no way from"):
        station_distances(campus, IN_USE)


def test_a_station_that_is_not_on_the_map_is_refused_with_a_clear_error():
    with pytest.raises(PathError, match="Station 9 is not on the map"):
        station_distances(CAMPUS, [1, 9])


# The real campus


def test_every_distance_between_the_spawn_and_the_stations_in_use_exists(real_distances):
    places = [SPAWN] + IN_USE
    assert set(real_distances) == set(itertools.permutations(places, 2))
    for distance in real_distances.values():
        assert distance is not None and distance > 0


def test_no_walking_distance_is_shorter_than_the_straight_line(real_distances):
    def centre(place):
        if place == SPAWN:
            return (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
        return (STATIONS[place]["x"], STATIONS[place]["y"])

    for (start, goal), distance in real_distances.items():
        straight = math.dist(centre(start), centre(goal))
        # A station is reached anywhere in its range, the spawn within one grid step.
        allowance = sum(USE_RANGE if place != SPAWN else paths.GRID_STEP for place in (start, goal))
        assert distance >= straight - allowance


def test_the_real_distances_are_the_same_in_both_directions(real_distances):
    for (start, goal), distance in real_distances.items():
        assert distance == pytest.approx(real_distances[(goal, start)], abs=0.5)


def test_a_detour_over_a_third_place_is_never_shorter(real_distances):
    places = [SPAWN] + IN_USE
    for start, middle, goal in itertools.permutations(places, 3):
        detour = real_distances[(start, middle)] + real_distances[(middle, goal)]
        assert real_distances[(start, goal)] <= detour + 0.5


def test_the_stations_are_far_apart_so_that_duel_means_walking(real_distances):
    # DESIGN.md, section 2: "so that you really have to walk in Duel".
    for start, goal in itertools.permutations(IN_USE, 2):
        assert real_distances[(start, goal)] >= 400


def test_walls_make_some_ways_much_longer_than_the_straight_line(real_distances):
    # Station 4 (CTT) and station 5 (Pingo Doce) lie on one height, but the
    # way leads out of one door, across the deck and in at the other.
    straight = math.dist((STATIONS[4]["x"], STATIONS[4]["y"]), (STATIONS[5]["x"], STATIONS[5]["y"]))
    assert real_distances[(4, 5)] > 2 * straight


def test_the_point_a_station_is_measured_at_is_one_it_can_be_opened_from():
    grid = paths.Grid(CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
    for station_id in IN_USE:
        station = STATIONS[station_id]
        column, row = grid.nearest_free_point(station["x"], station["y"], USE_RANGE)
        x, y = column * paths.GRID_STEP, row * paths.GRID_STEP
        assert is_free(x, y, CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
        assert math.dist((x, y), (station["x"], station["y"])) <= USE_RANGE


def test_the_grid_asks_the_real_collision_rule_at_every_point():
    grid = paths.Grid(CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
    step = paths.GRID_STEP
    for column in range(-1, CAMPUS["width"] // step + 2):
        for row in range(-1, CAMPUS["height"] // step + 2):
            expected = is_free(column * step, row * step, CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
            assert grid.is_free((column, row)) == expected


def test_a_finer_grid_measures_nearly_the_same(real_distances, monkeypatch):
    # The grid step is a choice between speed and exactness (see paths.py).
    # With half the step no way may turn out much shorter: that would mean
    # the coarser grid misses a passage.
    monkeypatch.setattr(paths, "GRID_STEP", paths.GRID_STEP // 2)
    finer = station_distances(CAMPUS, IN_USE)
    for pair, distance in real_distances.items():
        assert distance == pytest.approx(finer[pair], rel=0.04)


def test_the_same_map_gives_the_same_distances_every_time(real_distances):
    assert station_distances(CAMPUS, IN_USE) == real_distances


def test_measuring_the_real_map_is_quick_enough_for_the_start_of_the_server():
    started = time.perf_counter()
    station_distances(CAMPUS, IN_USE)
    # About a third of a second on a laptop. The limit is generous, because
    # the tests share their machine.
    assert time.perf_counter() - started < 5


def test_the_server_keeps_the_distances_it_measured_at_the_start(real_distances):
    from server.main import app

    assert app.state.distances == real_distances
