"""The walkways of the campus map of M2-1.19 (S-125), as plain checks on the map.

Felix chose this map from a preview: fewer pieces of furniture, so that the
rooms have walkways for characters 39 units high. Three lecture rows with
walkable gaps, a café door that leads straight in, a centre aisle in the
canteen, one wide lane between two turnstile posts in Pingo Doce, and a
hedge that stays solid while it is drawn as round bushes.
The real walking rule `step` and `is_free` are used, so the tests ask what a
player can really do.
"""

import copy

import pytest

from server.modes import minigames
from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE, is_free, overlaps, step
from server.world.paths import station_distances

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
WIDTH, HEIGHT = CAMPUS["width"], CAMPUS["height"]

# A gap a player (10 units wide) could just squeeze into (S-111, S-122).
SQUEEZE_GAPS = range(10, 14)

# The pieces of the map before M2-1.19 (S-122) that this to-do took out or
# moved, with their places then. Used to measure what the Duel lost or won.
BEFORE_THIS_TO_DO = {
    "lecture-hall-bench-1": {"kind": "bench", "x": 40, "y": 58, "w": 170, "h": 18},
    "lecture-hall-bench-2": {"kind": "bench", "x": 40, "y": 76, "w": 170, "h": 18},
    "lecture-hall-bench-3": {"kind": "bench", "x": 40, "y": 108, "w": 170, "h": 18},
    "lecture-hall-bench-4": {"kind": "bench", "x": 40, "y": 126, "w": 170, "h": 18},
    "mon-cafe-column-2": {"kind": "column", "x": 419, "y": 82, "w": 14, "h": 14},
    "mon-cafe-table-1": {"kind": "round-table", "x": 333, "y": 108, "w": 34, "h": 34},
    "canteen-table-2": {"kind": "table", "x": 545, "y": 58, "w": 40, "h": 36},
    "canteen-table-5": {"kind": "table", "x": 545, "y": 108, "w": 40, "h": 36},
    "pingo-doce-gate-2": {"kind": "turnstile", "x": 529, "y": 417, "w": 4, "h": 9},
    "pingo-doce-gate-3": {"kind": "turnstile", "x": 547, "y": 417, "w": 4, "h": 9},
}


def solid_called(solid_id):
    return next(solid for solid in SOLIDS if solid["id"] == solid_id)


def solids_of_kind(kind):
    return sorted((solid for solid in SOLIDS if solid["kind"] == kind), key=lambda solid: (solid["y"], solid["x"]))


def room_called(room_id):
    return next(room for room in CAMPUS["rooms"] if room["id"] == room_id)


def door_of(room_id):
    return next(door for door in CAMPUS["doors"] if door["room"] == room_id)


def lies_in(solid, room):
    return (room["x"] <= solid["x"] and solid["x"] + solid["w"] <= room["x"] + room["w"]
            and room["y"] <= solid["y"] and solid["y"] + solid["h"] <= room["y"] + room["h"])


def solids_overlapping(area):
    """The ids of the solids that overlap the rectangle `area` (touching is not overlapping)."""
    return [solid["id"] for solid in SOLIDS
            if solid["x"] < area["x"] + area["w"] and area["x"] < solid["x"] + solid["w"]
            and solid["y"] < area["y"] + area["h"] and area["y"] < solid["y"] + solid["h"]]


def walk(x, y, dx, dy, seconds):
    """Walk with the real rule in steps of 0.05 seconds and return where the player ends."""
    for _ in range(round(seconds / 0.05)):
        x, y = step(x, y, dx, dy, 0.05, SOLIDS, WIDTH, HEIGHT)
    return x, y


def lies_inside(inner, outer):
    """The rectangle `inner` lies wholly inside `outer`; the edges may meet."""
    return (outer["x"] <= inner["x"] and inner["x"] + inner["w"] <= outer["x"] + outer["w"]
            and outer["y"] <= inner["y"] and inner["y"] + inner["h"] <= outer["y"] + outer["h"])


def gap_between(first, second):
    """The free space between two solids that face each other along one axis, or None.

    The same rule as in tests/test_campus_detail.py: solids that only lie
    diagonally to each other leave no lane, and neither does a gap that a
    third solid fills completely.
    """
    left = max(first["x"], second["x"])
    right = min(first["x"] + first["w"], second["x"] + second["w"])
    top = max(first["y"], second["y"])
    bottom = min(first["y"] + first["h"], second["y"] + second["h"])
    if right > left and bottom > top:
        return 0
    if right > left:
        between = {"x": left, "y": bottom, "w": right - left, "h": top - bottom}
    elif bottom > top:
        between = {"x": right, "y": top, "w": left - right, "h": bottom - top}
    else:
        return None
    if any(lies_inside(between, third) for third in SOLIDS if third is not first and third is not second):
        return None
    return between["w"] if right <= left else between["h"]


# The Lecture Hall: three rows with walkways

def test_the_lecture_hall_has_three_rows_of_the_same_size():
    rows = solids_of_kind("bench")
    assert [(row["x"], row["y"], row["w"], row["h"]) for row in rows] == [
        (48, 56, 154, 18), (48, 91, 154, 18), (48, 126, 154, 18)]


def test_the_circle_of_station_1_lies_clear_of_the_first_lecture_row():
    # A drawing around every station must not sit on the desks (review of M2-1.19).
    station = next(station for station in CAMPUS["stations"] if station["id"] == 1)
    first_row = solids_of_kind("bench")[0]
    assert station["y"] + station["r"] <= first_row["y"]


def test_a_player_walks_from_wall_to_wall_between_every_two_lecture_rows():
    room = room_called("lecture-hall")
    rows = solids_of_kind("bench")
    for front, back in zip(rows, rows[1:]):
        y = (front["y"] + front["h"] + back["y"]) / 2
        start_x = room["x"] + 3 + PLAYER_HALF_SIZE  # touching the left wall
        assert is_free(start_x, y, SOLIDS, WIDTH, HEIGHT), (front["id"], back["id"])
        end_x, end_y = walk(start_x, y, 1, 0, 3)
        assert (end_x, end_y) == (room["x"] + room["w"] - 3 - PLAYER_HALF_SIZE, y)


@pytest.mark.parametrize("side", ["left", "right"])
def test_beside_the_lecture_rows_a_player_walks_from_the_back_to_the_front(side):
    room = room_called("lecture-hall")
    rows = solids_of_kind("bench")
    if side == "left":
        x = (room["x"] + 3 + rows[0]["x"]) / 2
    else:
        x = (rows[0]["x"] + rows[0]["w"] + room["x"] + room["w"] - 3) / 2
    start_y = rows[-1]["y"] + rows[-1]["h"] + 10
    end_x, end_y = walk(x, start_y, 0, -1, 3)
    # Up alongside every row to the front of the first one.
    assert end_x == x
    assert end_y <= rows[0]["y"] - PLAYER_HALF_SIZE


def test_the_door_room_name_and_station_1_of_the_lecture_hall_stay_free():
    room = room_called("lecture-hall")
    door = door_of("lecture-hall")
    station = next(station for station in CAMPUS["stations"] if station["id"] == 1)
    last_row = solids_of_kind("bench")[-1]
    assert room["label"]["y"] > last_row["y"] + last_row["h"]
    assert is_free(station["x"], station["y"], SOLIDS, WIDTH, HEIGHT)
    # Straight in through the door up to the last row.
    end = walk(door["x"] + door["w"] / 2, door["y"] + door["h"] + 10, 0, -1, 2)
    assert end[1] == last_row["y"] + last_row["h"] + PLAYER_HALF_SIZE


# Mon Café: straight in through the door

def test_the_cafe_door_leads_straight_in_to_the_counter_without_a_table():
    door = door_of("mon-cafe")
    counter = solid_called("mon-cafe-counter")
    left_table, right_table = solids_of_kind("round-table")
    # The lane between the two tables, from the door up to the counter: no
    # solid in it, wide enough for three players, and the door's middle in its middle.
    lane = {"x": left_table["x"] + left_table["w"], "y": counter["y"] + counter["h"],
            "w": right_table["x"] - (left_table["x"] + left_table["w"]),
            "h": door["y"] - (counter["y"] + counter["h"])}
    assert solids_overlapping(lane) == []
    assert lane["w"] >= 6 * PLAYER_HALF_SIZE
    assert lane["x"] + lane["w"] / 2 == door["x"] + door["w"] / 2
    end = walk(door["x"] + door["w"] / 2, door["y"] + door["h"] + 10, 0, -1, 3)
    assert end[1] == counter["y"] + counter["h"] + PLAYER_HALF_SIZE


def test_no_column_stands_under_the_badge_of_station_2():
    station = next(station for station in CAMPUS["stations"] if station["id"] == 2)
    reach = CAMPUS["use_range"]
    around = {"x": station["x"] - reach, "y": station["y"] - reach, "w": 2 * reach, "h": 2 * reach}
    assert sorted(solids_overlapping(around)) == ["mon-cafe-coffee-machine", "mon-cafe-wall-right"]


def test_mon_cafe_has_two_tables_with_guests_and_three_columns():
    room = room_called("mon-cafe")
    assert [solid["id"] for solid in solids_of_kind("round-table")] == ["mon-cafe-table-2", "mon-cafe-table-3"]
    assert len([solid for solid in solids_of_kind("column") if lies_in(solid, room)]) == 3


# The canteen: a centre aisle

def test_the_canteen_has_a_centre_aisle_from_the_door_to_the_counter():
    tables = solids_of_kind("table")
    assert [table["id"] for table in tables] == ["canteen-table-1", "canteen-table-3", "canteen-table-4"]
    left_edge = max(table["x"] + table["w"] for table in tables if table["x"] < 540)
    right_edge = min(table["x"] for table in tables if table["x"] > 540)
    counter = solid_called("canteen-counter")
    door = door_of("canteen")
    aisle = {"x": left_edge, "y": counter["y"] + counter["h"], "w": right_edge - left_edge,
             "h": door["y"] - (counter["y"] + counter["h"])}
    # Wider than the door, which lies inside it.
    assert aisle["x"] <= door["x"] and door["x"] + door["w"] <= aisle["x"] + aisle["w"]
    assert solids_overlapping({**aisle, "x": door["x"], "w": door["w"]}) == []
    end = walk(door["x"] + door["w"] / 2, door["y"] + door["h"] + 10, 0, -1, 3)
    assert end[1] == counter["y"] + counter["h"] + PLAYER_HALF_SIZE


# Pingo Doce: one lane between two turnstile posts

def turnstiles():
    return solids_of_kind("turnstile")


def test_pingo_doce_has_two_turnstile_posts_and_a_lane_centred_on_the_door():
    left, right = turnstiles()
    door = door_of("pingo-doce")
    lane_left = left["x"] + left["w"]
    lane_right = right["x"]
    assert lane_right - lane_left == 50
    assert (lane_left + lane_right) / 2 == door["x"] + door["w"] / 2 == 540
    # The lane is wider than the door, so nothing narrows the way in.
    assert lane_left <= door["x"] and door["x"] + door["w"] <= lane_right


@pytest.mark.parametrize("post_index, direction", [(0, -1), (1, 1)], ids=["left post", "right post"])
def test_walking_sideways_out_of_the_lane_stops_at_each_post(post_index, direction):
    post = turnstiles()[post_index]
    y = post["y"] + post["h"] / 2
    end = walk(540, y, direction, 0, 2)
    edge = post["x"] + post["w"] + PLAYER_HALF_SIZE if direction < 0 else post["x"] - PLAYER_HALF_SIZE
    assert end == (edge, y)
    assert not overlaps(end[0], end[1], post)


@pytest.mark.parametrize("post_index", [0, 1], ids=["left post", "right post"])
def test_walking_down_onto_each_post_stops_on_it(post_index):
    post = turnstiles()[post_index]
    x = post["x"] + post["w"] / 2
    start = (x, post["y"] - 8)
    assert is_free(*start, SOLIDS, WIDTH, HEIGHT)
    end = walk(*start, 0, 1, 2)
    assert end == (x, post["y"] - PLAYER_HALF_SIZE)


def test_the_start_of_the_shelf_test_in_tests_test_movement_stays_free():
    # tests/test_movement.py walks down from (524, 415) onto pingo-doce-shelf-2.
    assert is_free(524, 415, SOLIDS, WIDTH, HEIGHT)
    end = walk(524, 415, 0, 1, 3)
    assert end == (524, solid_called("pingo-doce-shelf-2")["y"] - PLAYER_HALF_SIZE)


# The rooms with fewer pieces leave no gap a player could squeeze into

# Pingo Doce only lost two turnstile posts; the two left are of a kind that
# test_campus_detail.py already checks against every other solid.
@pytest.mark.parametrize("room_id", ["lecture-hall", "mon-cafe", "canteen"])
def test_no_piece_in_a_changed_room_leaves_a_gap_a_player_could_just_squeeze_into(room_id):
    room = room_called(room_id)
    pieces = [solid for solid in SOLIDS if solid["kind"] != "wall" and lies_in(solid, room)]
    for piece in pieces:
        for other in SOLIDS:
            if other is not piece:
                assert gap_between(piece, other) not in SQUEEZE_GAPS, (piece["id"], other["id"])


# The hedge on the deck

def test_the_hedge_stays_solid_until_the_hiding_spots_are_built():
    hedge = solid_called("deck-hedge")
    assert (hedge["x"], hedge["y"], hedge["w"], hedge["h"]) == (556, 236, 68, 26)
    assert "walkable" not in hedge
    assert not is_free(595, 249, SOLIDS, WIDTH, HEIGHT)


# The Duel

def as_before_this_to_do(campus):
    """The map as it was on main before M2-1.19 (S-122)."""
    old = copy.deepcopy(campus)
    old["solids"] = [solid for solid in old["solids"] if solid["id"] not in BEFORE_THIS_TO_DO]
    for solid_id, place in BEFORE_THIS_TO_DO.items():
        old["solids"].append({"id": solid_id, **place})
    return old


def test_fewer_pieces_make_no_way_of_the_duel_longer_and_none_much_shorter():
    # Measured for this to-do against main before it: 1 to 2 became 3.5 %
    # shorter (597.0 -> 576.3), spawn to 1 2.2 %; the ways to station 4 from
    # the spawn, 3 and 5 did not change.
    stations = sorted(minigames.MINIGAMES)
    before = station_distances(as_before_this_to_do(CAMPUS), stations)
    after = station_distances(CAMPUS, stations)
    assert after.keys() == before.keys()
    for pair, distance in before.items():
        assert distance * 0.96 <= after[pair] <= distance + 0.001, pair
