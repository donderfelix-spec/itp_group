"""Walking on the campus: speed, stopping at solids, sliding, doors and what can be reached."""

import math
import random
from collections import deque

import pytest

from server.world.campus import load_campus
from server.world.movement import (
    MAX_STEP_SECONDS,
    PLAYER_HALF_SIZE,
    PLAYER_SPEED,
    is_free,
    overlaps,
    step,
)

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
WIDTH = CAMPUS["width"]
HEIGHT = CAMPUS["height"]

# An open field without anything in the way, for the tests about speed.
OPEN = 10_000

TICK = 1 / 15          # the step length used in the acceptance criteria
GRID = 4               # the flood fill walks in steps of 4 units


def walk(x, y, dx, dy, seconds, solids=SOLIDS, width=WIDTH, height=HEIGHT, tick=TICK):
    """Hold one direction for `seconds`, in steps of `tick`, and return where the player ends."""
    for _ in range(round(seconds / tick)):
        x, y = step(x, y, dx, dy, tick, solids, width, height)
    return x, y


def solid_called(solid_id):
    return next(solid for solid in SOLIDS if solid["id"] == solid_id)


def gap_to(x, y, solid):
    """The free space between the player square and a solid (0 when they touch)."""
    gap_x = max(solid["x"] - (x + PLAYER_HALF_SIZE), (x - PLAYER_HALF_SIZE) - (solid["x"] + solid["w"]), 0)
    gap_y = max(solid["y"] - (y + PLAYER_HALF_SIZE), (y - PLAYER_HALF_SIZE) - (solid["y"] + solid["h"]), 0)
    return max(gap_x, gap_y)


def inside_rectangle(x, y, rectangle, margin=0):
    return (
        rectangle["x"] + margin <= x <= rectangle["x"] + rectangle["w"] - margin
        and rectangle["y"] + margin <= y <= rectangle["y"] + rectangle["h"] - margin
    )


def inside_deck(x, y):
    """Is the point inside the outline of the Main Deck, or on its line?

    The outline only has horizontal and vertical edges. The test counts the
    vertical edges to the left of the point: an odd number means inside.
    """
    corners = CAMPUS["deck"]
    edges = list(zip(corners, corners[1:] + corners[:1]))
    crossings = 0
    for start, end in edges:
        if start["x"] != end["x"]:
            # A point on a horizontal edge is on the line, so it counts as inside.
            on_edge = y == start["y"] and min(start["x"], end["x"]) <= x <= max(start["x"], end["x"])
            if on_edge:
                return True
            continue
        top, bottom = min(start["y"], end["y"]), max(start["y"], end["y"])
        if top <= y <= bottom and x == start["x"]:
            return True
        if top <= y < bottom and start["x"] < x:
            crossings += 1
    return crossings % 2 == 1


def on_the_campus(x, y):
    """Inside a room or on the Main Deck. Everything else is lawn, beach or sea."""
    return inside_deck(x, y) or any(inside_rectangle(x, y, room) for room in CAMPUS["rooms"])


def distance_to_walk(position, direction, grid_origin):
    """How far the flood fill walks on one axis: always up to the next grid line.

    From a grid line that is a full 4 units. From a place between the lines
    (where a solid stopped the player) it is the rest of the way to the next
    line, so the search comes back onto the grid instead of drifting beside it.
    """
    past_the_line = (position - grid_origin) % GRID
    if past_the_line == 0:
        return GRID
    return past_the_line if direction < 0 else GRID - past_the_line


def flood(solids, stop_at=None):
    """Every point a player can walk to from the spawn, found by flood fill.

    The search walks with the real `step` on a grid of 4 units around the
    spawn. It also goes on from the points where a step was cut short by a
    solid (the player then touches that solid), because a passage that is only
    a little wider than the player can only be entered from there.

    `stop_at` is a function `(x, y) -> bool`. The search ends at the first
    point for which it says yes: enough to prove a hole, without flooding the
    whole lawn.
    """
    start = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
    straight = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    diagonal = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    found = {start}
    waiting = deque([start])
    while waiting:
        x, y = waiting.popleft()
        moves = []
        for dx, dy in straight:
            if dx != 0:
                moves.append((dx, dy, distance_to_walk(x, dx, start[0])))
            else:
                moves.append((dx, dy, distance_to_walk(y, dy, start[1])))
        on_the_grid = (x - start[0]) % GRID == 0 and (y - start[1]) % GRID == 0
        if on_the_grid:
            # A diagonal step of 4 units on each axis is sqrt(2) times as long.
            moves += [(dx, dy, GRID * math.sqrt(2)) for dx, dy in diagonal]

        for dx, dy, distance in moves:
            new_x, new_y = step(x, y, dx, dy, distance / PLAYER_SPEED, solids, WIDTH, HEIGHT)
            # Rounded so that 251.99999999999997 and 252 count as the same point.
            point = (round(new_x, 6), round(new_y, 6))
            if point in found:
                continue
            found.add(point)
            waiting.append(point)
            if stop_at is not None and stop_at(*point):
                return found
    return found


def without(*solid_ids):
    """The solids of the map with some of them taken away, to cut a hole on purpose."""
    assert all(solid_called(solid_id) for solid_id in solid_ids)
    return [solid for solid in SOLIDS if solid["id"] not in solid_ids]


def off_the_campus(x, y):
    return not on_the_campus(x, y)


def in_a_room(x, y):
    """Clearly inside one of the five rooms, not just in its doorway."""
    return any(inside_rectangle(x, y, room, margin=PLAYER_HALF_SIZE) for room in CAMPUS["rooms"])


def bricked_up_doors():
    """One extra wall in every doorway."""
    return [dict(door, id="bricks", kind="wall") for door in CAMPUS["doors"]]


def reaches(solids, place):
    """Does the flood fill get to a point for which `place(x, y)` says yes?"""
    return any(place(x, y) for x, y in flood(solids, stop_at=place))


@pytest.fixture(scope="module")
def reached():
    return flood(SOLIDS)


# Speed (criterion 7)

@pytest.mark.parametrize("dx, dy", [(1, 0), (-1, 0), (0, 1), (0, -1)])
def test_one_second_straight_covers_90_units(dx, dy):
    x, y = walk(5000, 5000, dx, dy, 1, solids=[], width=OPEN, height=OPEN)
    assert x == pytest.approx(5000 + 90 * dx)
    assert y == pytest.approx(5000 + 90 * dy)


@pytest.mark.parametrize("dx, dy", [(1, 1), (1, -1), (-1, 1), (-1, -1)])
def test_one_second_diagonally_covers_90_units_and_not_127(dx, dy):
    x, y = walk(5000, 5000, dx, dy, 1, solids=[], width=OPEN, height=OPEN)
    assert math.dist((5000, 5000), (x, y)) == pytest.approx(90)


def test_the_speed_does_not_depend_on_the_length_of_the_steps():
    slow = walk(5000, 5000, 1, 0, 1, solids=[], width=OPEN, height=OPEN, tick=1 / 60)
    fast = walk(5000, 5000, 1, 0, 1, solids=[], width=OPEN, height=OPEN, tick=1 / 10)
    assert slow[0] == pytest.approx(fast[0]) == pytest.approx(5090)


def test_no_direction_does_not_move():
    assert step(486, 296, 0, 0, TICK, SOLIDS, WIDTH, HEIGHT) == (486, 296)


def test_a_long_pause_moves_no_further_than_a_tenth_of_a_second():
    capped = step(5000, 5000, 1, 0, MAX_STEP_SECONDS, [], OPEN, OPEN)
    assert step(5000, 5000, 1, 0, 5, [], OPEN, OPEN) == capped
    assert capped[0] == pytest.approx(5009)
    assert MAX_STEP_SECONDS == 0.1


@pytest.mark.parametrize("seconds", [0, -0.0, -1, -5, float("-inf"), float("nan")])
def test_no_time_or_negative_time_does_not_move(seconds):
    assert step(486, 296, 1, 1, seconds, SOLIDS, WIDTH, HEIGHT) == (486, 296)


def test_endless_time_counts_as_the_longest_step():
    assert step(5000, 5000, 1, 0, float("inf"), [], OPEN, OPEN) == step(5000, 5000, 1, 0, 0.1, [], OPEN, OPEN)


@pytest.mark.parametrize("dx", [5, 1000, 0.3, float("inf")])
def test_a_direction_larger_or_smaller_than_one_is_not_faster_or_slower(dx):
    assert step(5000, 5000, dx, 0, 0.1, [], OPEN, OPEN) == step(5000, 5000, 1, 0, 0.1, [], OPEN, OPEN)


@pytest.mark.parametrize("dx", [float("nan"), None, "1", [1]])
def test_a_direction_that_is_not_a_number_does_not_move(dx):
    assert step(5000, 5000, dx, 0, 0.1, [], OPEN, OPEN) == (5000, 5000)


@pytest.mark.parametrize("dx, dy, seconds", [
    (1, 1, 0.1), (float("inf"), float("-inf"), float("inf")), (float("nan"), 1, 5), (1e308, -1e308, 1e308),
])
def test_the_result_is_always_finite(dx, dy, seconds):
    x, y = step(486, 296, dx, dy, seconds, SOLIDS, WIDTH, HEIGHT)
    assert math.isfinite(x) and math.isfinite(y)


HUGE = 10 ** 400        # a whole number too large for a float


def test_a_huge_whole_number_as_time_counts_as_the_longest_step():
    assert step(5000, 5000, 1, 0, HUGE, [], OPEN, OPEN) == step(5000, 5000, 1, 0, 0.1, [], OPEN, OPEN)
    assert step(5000, 5000, 1, 0, -HUGE, [], OPEN, OPEN) == (5000, 5000)


def test_a_huge_whole_number_as_direction_counts_as_one():
    assert step(5000, 5000, HUGE, -HUGE, 0.1, [], OPEN, OPEN) == step(5000, 5000, 1, -1, 0.1, [], OPEN, OPEN)


def test_huge_numbers_everywhere_still_give_a_finite_result_on_the_map():
    x, y = step(486, 296, HUGE, HUGE, HUGE, SOLIDS, WIDTH, HEIGHT)
    assert math.isfinite(x) and math.isfinite(y)
    assert is_free(x, y, SOLIDS, WIDTH, HEIGHT)


@pytest.mark.parametrize("seconds", [None, "0.1", [0.1]])
def test_time_that_is_not_a_number_does_not_move(seconds):
    assert step(486, 296, 1, 1, seconds, SOLIDS, WIDTH, HEIGHT) == (486, 296)


@pytest.mark.parametrize("x, y", [
    (float("nan"), 296), (486, float("inf")), (float("-inf"), 296),
    (HUGE, 296), (486, -HUGE), (None, 296), (486, "296"), ([486], 296), (True, 296),
])
def test_a_position_that_is_not_finite_is_an_error_and_not_a_silent_result(x, y):
    with pytest.raises(ValueError):
        step(x, y, 1, 0, 0.1, SOLIDS, WIDTH, HEIGHT)


# Stopping at solids (criterion 4)

# solid, start x, start y, direction x, direction y. Each start has a free straight line to the solid.
STRAIGHT_AT = [
    ("deck-wall-right",      600, 300,  1,  0),   # wall
    ("deck-wall-top-2",      240, 200,  0, -1),   # wall, from below
    ("ctt-wall-right",       180, 300, -1,  0),   # wall between the deck and the CTT hall
    ("pingo-doce-wall-left", 400, 500,  1,  0),   # wall between the deck and Pingo Doce
    ("glass-front",          300, 530,  0,  1),   # glass
    ("deck-pool",            365, 200,  0,  1),   # pool
    ("deck-tree-1",          175, 252,  1,  0),   # tree
    ("deck-hedge",           595, 300,  0, -1),   # hedge
    ("deck-logo",            300, 420,  0,  1),   # logo
    ("lecture-hall-bench-3", 125, 150,  0, -1),   # furniture, one per room (the last row, S-125)
    ("mon-cafe-table-3",     385, 150,  0, -1),
    ("canteen-table-4",      508, 150,  0, -1),
    ("ctt-table-row-1",       90, 245,  0,  1),
    ("pingo-doce-shelf-2",   524, 415,  0,  1),
]


@pytest.mark.parametrize("solid_id, x, y, dx, dy", STRAIGHT_AT)
def test_walking_straight_at_a_solid_for_3_seconds_ends_outside_it(solid_id, x, y, dx, dy):
    solid = solid_called(solid_id)
    assert is_free(x, y, SOLIDS, WIDTH, HEIGHT), "the start of this test must be free"
    end_x, end_y = walk(x, y, dx, dy, 3)
    assert not overlaps(end_x, end_y, solid)
    assert is_free(end_x, end_y, SOLIDS, WIDTH, HEIGHT)
    assert (end_x, end_y) != (x, y), "the player should have walked up to the solid"
    # No visible gap is left: the player ends touching the solid.
    assert gap_to(end_x, end_y, solid) <= 1


@pytest.mark.parametrize("solid_id, x, y, dx, dy", STRAIGHT_AT)
def test_running_at_a_solid_with_the_longest_step_does_not_pass_it(solid_id, x, y, dx, dy):
    end_x, end_y = x, y
    for _ in range(40):
        # 5 seconds are capped at 0.1 seconds: 9 units, the longest step there is.
        end_x, end_y = step(end_x, end_y, dx, dy, 5, SOLIDS, WIDTH, HEIGHT)
    assert is_free(end_x, end_y, SOLIDS, WIDTH, HEIGHT)
    assert gap_to(end_x, end_y, solid_called(solid_id)) <= 1


def test_a_player_touching_a_wall_stays_exactly_there():
    wall = [{"x": 100, "y": 0, "w": 6, "h": 200}]
    assert step(95, 50, 1, 0, 0.1, wall, 300, 200) == (95, 50)


def test_a_player_can_walk_away_from_a_wall_they_touch():
    wall = [{"x": 100, "y": 0, "w": 6, "h": 200}]
    x, y = step(95, 50, -1, 0, 0.1, wall, 300, 200)
    assert (x, y) == (pytest.approx(86), 50)


def test_a_solid_beside_the_lane_does_not_stop_the_player():
    # The block ends at y = 40; the player's square starts at y = 40: they touch but do not overlap.
    block = [{"x": 100, "y": 0, "w": 20, "h": 40}]
    x, y = walk(50, 45, 1, 0, 1, solids=block, width=300, height=200)
    assert x == pytest.approx(140)


def test_a_solid_one_hair_inside_the_lane_stops_the_player():
    block = [{"x": 100, "y": 0, "w": 20, "h": 40.001}]
    x, y = walk(50, 45, 1, 0, 1, solids=block, width=300, height=200)
    assert x == 95


@pytest.mark.parametrize("dx, dy, expected", [
    (-1, 0, (5, 50)), (1, 0, (295, 50)), (0, -1, (50, 5)), (0, 1, (50, 195)),
])
def test_the_player_cannot_leave_the_map(dx, dy, expected):
    assert walk(50, 50, dx, dy, 5, solids=[], width=300, height=200) == expected


# solid, a point inside it, and where a player walking back at it from each side must stop
@pytest.mark.parametrize("dx, dy, stops_at", [
    (-1, 0, (295, 290)), (1, 0, (435, 290)), (0, -1, (365, 257)), (0, 1, (365, 323)),
])
def test_a_player_inside_the_pool_can_walk_out_and_is_then_blocked_by_it_again(dx, dy, stops_at):
    x, y = 365, 290                                   # the middle of the pool
    assert overlaps(x, y, solid_called("deck-pool"))
    x, y = walk(x, y, dx, dy, 1)                      # out in 1 second: the edge is at most 70 units away
    assert is_free(x, y, SOLIDS, WIDTH, HEIGHT)
    assert walk(x, y, -dx, -dy, 3) == stops_at        # and walking back ends at the edge


def test_a_player_one_unit_inside_a_wall_can_walk_back_out():
    # The inner face of the deck's right wall is at x = 657; touching it means x = 652.
    assert overlaps(653, 300, solid_called("deck-wall-right"))
    x, y = step(653, 300, -1, 0, TICK, SOLIDS, WIDTH, HEIGHT)
    assert (x, y) == (pytest.approx(647), 300)
    assert walk(x, y, 1, 0, 1) == (652, 300), "from outside the wall blocks again"


def test_a_player_inside_one_solid_is_still_stopped_by_the_others():
    inside = {"x": 100, "y": 0, "w": 50, "h": 200}
    other = {"x": 150, "y": 0, "w": 6, "h": 200}       # touches the first one
    x, _ = walk(120, 50, 1, 0, 3, solids=[inside, other], width=300, height=200)
    assert x == 145


def test_a_player_inside_a_solid_at_the_edge_of_the_map_still_cannot_leave_the_map():
    block = [{"x": 250, "y": 0, "w": 50, "h": 200}]
    assert walk(270, 50, 1, 0, 3, solids=block, width=300, height=200) == (295, 50)


def test_the_list_of_solids_passed_in_is_not_changed():
    solids = [{"x": 100, "y": 0, "w": 50, "h": 200}]
    step(120, 50, 1, 0, 0.1, solids, 300, 200)
    assert solids == [{"x": 100, "y": 0, "w": 50, "h": 200}]


def test_a_player_who_is_somehow_inside_a_solid_is_not_thrown_backwards():
    block = [{"x": 100, "y": 0, "w": 50, "h": 200}]
    x, y = step(120, 50, 1, 0, 0.1, block, 300, 200)
    assert math.isfinite(x) and x >= 120 and y == 50


# Doors (criterion 5)

def door_and_room():
    rooms = {room["id"]: room for room in CAMPUS["rooms"]}
    return [(door, rooms[door["room"]]) for door in CAMPUS["doors"]]


@pytest.mark.parametrize("door, room", door_and_room(), ids=lambda value: value.get("id", ""))
def test_each_door_can_be_walked_through_in_a_straight_line(door, room):
    x = door["x"] + door["w"] / 2
    door_y = door["y"] + door["h"] / 2
    # The room is above its door (direction -1) or below it (direction 1).
    towards_room = -1 if room["y"] < door_y else 1
    start_y = door_y - towards_room * 30          # on the deck, 30 units before the door
    assert not inside_rectangle(x, start_y, room)

    end_x, end_y = walk(x, start_y, 0, towards_room, 1)
    assert end_x == x
    assert inside_rectangle(end_x, end_y, room, margin=15), "the player should stand well inside the room"

    back_x, back_y = walk(end_x, end_y, 0, -towards_room, 1)
    assert not inside_rectangle(back_x, back_y, room), "and the way back out works too"


@pytest.mark.parametrize("door, room", door_and_room(), ids=lambda value: value.get("id", ""))
def test_a_door_is_exactly_as_wide_as_drawn(door, room):
    door_y = door["y"] + door["h"] / 2
    towards_room = -1 if room["y"] < door_y else 1
    start_y = door_y - towards_room * 15

    # Hugging the left post of the door still fits ...
    hugging = door["x"] + PLAYER_HALF_SIZE
    _, end_y = walk(hugging, start_y, 0, towards_room, 0.4)
    assert abs(end_y - start_y) > 20

    # ... but 2 units further left the player hits the wall beside the door.
    _, end_y = walk(hugging - 2, start_y, 0, towards_room, 0.4)
    assert abs(end_y - start_y) < 15

    # The same at the right post.
    hugging = door["x"] + door["w"] - PLAYER_HALF_SIZE
    _, end_y = walk(hugging, start_y, 0, towards_room, 0.4)
    assert abs(end_y - start_y) > 20
    _, end_y = walk(hugging + 2, start_y, 0, towards_room, 0.4)
    assert abs(end_y - start_y) < 15


# Sliding (criterion 6)

def test_a_diagonal_against_a_wall_slides_along_it():
    # The right wall of the deck: its inner face is at x = 657, so the player stops at x = 652.
    x, y = walk(640, 300, 1, 1, 1)
    assert x == 652
    assert y == pytest.approx(300 + PLAYER_SPEED / math.sqrt(2))


def test_a_diagonal_against_the_glass_front_slides_sideways():
    x, y = walk(300, 550, -1, 1, 1)
    assert y == 556                                   # the glass starts at y = 561
    assert x == pytest.approx(300 - PLAYER_SPEED / math.sqrt(2))


def test_sliding_into_a_corner_ends_in_the_corner():
    # Bottom right corner of the Canteen: walls at x = 657 and y = 167.
    assert walk(600, 150, 1, 1, 3) == (652, 162)


# Corners and gaps (criterion 8)

def test_a_wall_corner_cannot_be_cut_diagonally():
    # Two blocks that touch only at the point (150, 100). The player comes from the
    # lower left and pushes up and to the right, straight at that point.
    blocks = [{"x": 100, "y": 50, "w": 50, "h": 50}, {"x": 150, "y": 100, "w": 50, "h": 50}]
    x, y = walk(130, 120, 1, -1, 3, solids=blocks, width=300, height=300)
    assert (x, y) == (145, 105)
    assert not any(overlaps(x, y, block) for block in blocks)


def test_two_solids_that_touch_leave_no_way_through():
    pair = [{"x": 100, "y": 0, "w": 6, "h": 100}, {"x": 100, "y": 100, "w": 6, "h": 100}]
    for start_y in (95, 99, 100, 101, 105):
        x, _ = walk(50, start_y, 1, 0, 3, solids=pair, width=300, height=200)
        assert x == 95


def test_a_gap_narrower_than_the_player_cannot_be_entered():
    pair = [{"x": 100, "y": 0, "w": 6, "h": 96}, {"x": 100, "y": 105, "w": 6, "h": 95}]   # gap of 9
    x, _ = walk(50, 100.5, 1, 0, 3, solids=pair, width=300, height=200)
    assert x == 95


def test_a_gap_exactly_as_wide_as_the_player_can_be_entered():
    pair = [{"x": 100, "y": 0, "w": 6, "h": 95}, {"x": 100, "y": 105, "w": 6, "h": 95}]    # gap of 10
    x, _ = walk(50, 100, 1, 0, 3, solids=pair, width=300, height=200)
    assert x == 295


# What can be reached (criteria 3, 8 and 9)

def test_the_flood_fill_covers_a_real_part_of_the_map(reached):
    assert len(reached) > 10_000


@pytest.mark.parametrize("room", CAMPUS["rooms"], ids=lambda room: room["id"])
def test_every_room_can_be_reached_from_the_spawn(reached, room):
    assert any(inside_rectangle(x, y, room, margin=20) for x, y in reached)


@pytest.mark.parametrize("room", CAMPUS["rooms"], ids=lambda room: room["id"])
def test_every_corner_region_of_a_room_can_be_reached(reached, room):
    # The furniture must not cut a room in two: each quarter of the room has reachable points.
    middle_x = room["x"] + room["w"] / 2
    middle_y = room["y"] + room["h"] / 2
    inside = [(x, y) for x, y in reached if inside_rectangle(x, y, room, margin=6)]
    for left in (True, False):
        for top in (True, False):
            assert any((x < middle_x) == left and (y < middle_y) == top for x, y in inside)


@pytest.mark.parametrize("station", CAMPUS["stations"], ids=lambda station: station["name"])
def test_every_station_can_be_reached_from_the_spawn(reached, station):
    nearest = min(math.dist((x, y), (station["x"], station["y"])) for x, y in reached)
    assert nearest <= 20


def test_the_emergency_button_can_be_reached(reached):
    button = CAMPUS["button"]
    assert min(math.dist((x, y), (button["x"], button["y"])) for x, y in reached) <= 20


def test_nobody_reaches_the_beach(reached):
    assert max(y for _, y in reached) <= 572
    # In fact nobody gets past the glass front, which starts at y = 561.
    assert max(y for _, y in reached) <= 561 - PLAYER_HALF_SIZE


def test_nobody_reaches_the_lawn(reached):
    outside = [(x, y) for x, y in reached if not on_the_campus(x, y)]
    assert outside == []


@pytest.mark.parametrize("x, y", [
    (10, 200), (340, 10), (670, 300), (240, 100), (460, 100), (100, 600), (560, 580), (10, 10),
])
def test_points_on_the_lawn_and_the_beach_are_far_from_everything_reachable(reached, x, y):
    assert not on_the_campus(x, y)
    assert min(math.dist((x, y), point) for point in reached) > PLAYER_HALF_SIZE


def test_nobody_ever_stands_inside_a_solid(reached):
    inside = [(x, y) for x, y in reached if not is_free(x, y, SOLIDS, WIDTH, HEIGHT)]
    assert inside == []


def test_a_long_random_walk_never_enters_a_solid_or_leaves_the_campus():
    choices = random.Random(2026)        # a fixed seed, so the test walks the same way every time
    x, y = CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"]
    dx = dy = 0
    for number in range(30_000):
        if number % 20 == 0:             # keep a direction for a while to get around
            dx, dy = choices.choice((-1, 0, 1)), choices.choice((-1, 0, 1))
        x, y = step(x, y, dx, dy, choices.uniform(0, 0.15), SOLIDS, WIDTH, HEIGHT)
        assert is_free(x, y, SOLIDS, WIDTH, HEIGHT), (x, y)
        assert on_the_campus(x, y), (x, y)


# The reachability tests must notice a hole (otherwise they prove nothing)

@pytest.mark.parametrize("solid_id", [
    "ctt-wall-bottom",          # only reachable through the 11 units beside the bookshelf
    "canteen-wall-right",
    "deck-wall-left",
    "glass-front",
])
def test_without_an_outer_wall_or_the_glass_the_flood_fill_reaches_the_outside(solid_id):
    assert reaches(without(solid_id), off_the_campus)


def test_with_every_door_bricked_up_no_room_can_be_entered():
    # If any wall between a room and the deck were missing or too short,
    # the player would get into that room without its door.
    found = flood(SOLIDS + bricked_up_doors())
    assert not any(in_a_room(x, y) for x, y in found)
    assert len(found) > 5_000, "the deck itself is still walkable"


@pytest.mark.parametrize("solid_id", ["deck-wall-top-3", "ctt-wall-right", "pingo-doce-wall-left"])
def test_without_a_wall_between_a_room_and_the_deck_a_bricked_up_room_is_entered(solid_id):
    # The proof that the test above notices such a wall.
    assert reaches(without(solid_id) + bricked_up_doors(), in_a_room)


def test_the_helper_inside_deck_knows_the_shape_of_the_deck():
    assert inside_deck(486, 296) and inside_deck(300, 500) and inside_deck(90, 200)
    assert inside_deck(125, 170)                       # on the line, in a doorway
    assert not inside_deck(90, 300)                    # the CTT hall
    assert not inside_deck(550, 480)                   # Pingo Doce
    assert not inside_deck(300, 600) and not inside_deck(10, 200) and not inside_deck(670, 300)
