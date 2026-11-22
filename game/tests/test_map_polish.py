"""The map polish of to-do M2-1.20: aisles without dead ends, no gaps a
player only just squeezes into, lamp posts against the walls, and station
objects that stand free.

With the real map and the real walking rule (`step`, `is_free`):

- the CTT's aisle along the window wall and the Canteen's aisle along its
  left wall can be walked from one end to the other;
- no two solids anywhere leave a gap of 10 to 13 units that a player can
  reach (S-111): 10 is exactly one player, so a player gets in and is drawn
  over the furniture on both sides;
- every lamp post touches a wall or stands less than 10 units from one, so
  nobody can walk between them;
- every station's object, with its outline at the high point of the pulse,
  lies on no solid and on no other station, and every station can be used
  from a place a player reaches from the spawn;
- no way of the Duel (spawn and stations 1-5 and 7-12) became longer.

The follow-up (Felix, 2026-11-22: the objects were "a bit too big" and did
not match the furniture): every object is at most its target size plus 2,
stands against a wall or a piece of furniture (all but stations 9 and 12,
which no allowed place brings near one), and no way of the Duel is longer
than on the branch before.

In Chromium (skipped when Node, Playwright or Chromium is missing): the
pixels of each station's object, outline, shadow and number tag lie on no
drawn furniture and in no wall, the boxes pinned here (also those of the
room names) are the real drawings, every outline fits into the square it is
grown in, and the map draws without a console error or warning. In Node:
draw.js puts each shadow and each number tag at its default place, or where
the station's drawing says (a shadow can also be left out), and no drawing
strokes a line wider than 1.
"""

import contextlib
import itertools
import json
import math
import socket
import subprocess
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

import pytest

from server.modes import minigames
from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE, PLAYER_SPEED, is_free, step
from server.world.paths import SPAWN, station_distances
from server.world.stations import station_in_range
from test_play_campus_detail import NODE, node_environment, playwright_works

CAMPUS = load_campus()
SOLIDS = CAMPUS["solids"]
WIDTH, HEIGHT = CAMPUS["width"], CAMPUS["height"]
USE_RANGE = CAMPUS["use_range"]

# A gap a player (10 units wide) could just squeeze into (S-111).
SQUEEZE_GAPS = range(10, 14)


def solid_called(solid_id, solids=SOLIDS):
    return next(solid for solid in solids if solid["id"] == solid_id)


def station_called(station_id):
    return next(station for station in CAMPUS["stations"] if station["id"] == station_id)


def changed(solid_id, **place):
    """The real solids with one solid moved or resized."""
    solids = [dict(solid) for solid in SOLIDS]
    solid_called(solid_id, solids).update(place)
    return solids


def walk(x, y, dx, dy, seconds, solids=SOLIDS):
    """Walk with the real rule in ticks of 0.05 s; returns where the player ends."""
    for _ in range(round(seconds / 0.05)):
        x, y = step(x, y, dx, dy, 0.05, solids, WIDTH, HEIGHT)
    return x, y


# The aisles along the walls

def window_aisle_of_the_ctt():
    """The free lane between the pillars at the window wall and the table rows."""
    pillar = solid_called("ctt-pillar-1")
    row = solid_called("ctt-table-row-1")
    return pillar["x"] + pillar["w"], row["x"]


def test_the_window_aisle_of_the_ctt_is_wider_than_a_player_beside_every_pillar():
    left, right = window_aisle_of_the_ctt()
    assert right - left == 14  # 22 from the wall, 14 beside each pillar


@pytest.mark.parametrize("x", [36, 38, 40], ids=lambda x: f"x {x}")
def test_a_player_walks_the_ctt_window_aisle_from_the_top_to_the_bookshelf(x):
    # x 36 touches the pillars, x 40 touches the table rows: both still pass.
    top = solid_called("ctt-wall-top-1")["y"] + solid_called("ctt-wall-top-1")["h"]
    start_y = top + PLAYER_HALF_SIZE + 2
    assert is_free(x, start_y, SOLIDS, WIDTH, HEIGHT)
    end = walk(x, start_y, 0, 1, 5)
    assert end == (x, solid_called("ctt-bookshelf")["y"] - PLAYER_HALF_SIZE)


def test_a_player_walks_the_ctt_window_aisle_back_up_from_the_bookshelf():
    bottom_y = solid_called("ctt-bookshelf")["y"] - PLAYER_HALF_SIZE
    top = solid_called("ctt-wall-top-1")["y"] + solid_called("ctt-wall-top-1")["h"]
    assert walk(38, bottom_y, 0, -1, 5) == (38, top + PLAYER_HALF_SIZE)


def test_beside_a_pillar_a_player_one_unit_too_far_left_is_stopped():
    # Edge case: the lane beside the pillars is exactly as wide as the walk needs.
    end = walk(35, 245, 0, 1, 5)
    assert end == (35, solid_called("ctt-pillar-1")["y"] - PLAYER_HALF_SIZE)


def test_with_the_old_long_rows_the_ctt_window_aisle_was_cut_into_dead_ends():
    # Rejected: the rows at x 37 left 6 units beside each pillar.
    solids = SOLIDS
    for number in range(1, 9):
        solids = [dict(solid, x=37, w=58) if solid["id"] == f"ctt-table-row-{number}" else solid for solid in solids]
    bookshelf_y = solid_called("ctt-bookshelf")["y"] - PLAYER_HALF_SIZE
    starts = [x for x in range(28, 46) if is_free(x, 240, solids, WIDTH, HEIGHT)]
    assert starts != []
    assert [x for x in starts if walk(x, 240, 0, 1, 5, solids)[1] == bookshelf_y] == []


def canteen_left_aisle_x():
    """The middle of the aisle between the Canteen's left wall and its left tables."""
    wall = solid_called("canteen-wall-left")
    table = solid_called("canteen-table-1")
    return (wall["x"] + wall["w"] + table["x"]) / 2


def test_a_player_walks_the_canteen_aisle_along_the_left_wall_down_to_the_recycling_bins():
    x = canteen_left_aisle_x()
    start_y = solid_called("canteen-drinks-fridge")["y"] + solid_called("canteen-drinks-fridge")["h"] + PLAYER_HALF_SIZE
    assert is_free(x, start_y, SOLIDS, WIDTH, HEIGHT)
    end = walk(x, start_y, 0, 1, 3)
    assert end == (x, solid_called("canteen-recycling")["y"] - PLAYER_HALF_SIZE)


def test_the_water_fountain_stands_below_the_tray_return_against_the_right_wall():
    fountain = solid_called("canteen-water-fountain")
    tray_return = solid_called("canteen-tray-return")
    wall = solid_called("canteen-wall-right")
    assert fountain["y"] == tray_return["y"] + tray_return["h"]
    assert fountain["x"] + fountain["w"] == wall["x"]


def test_with_the_fountain_in_its_old_place_the_canteen_aisle_was_blocked():
    # Rejected: at x 473, y 95 it left 7 units of the 15-wide aisle.
    solids = changed("canteen-water-fountain", x=473, y=95)
    x = canteen_left_aisle_x()
    end = walk(x, 52, 0, 1, 3, solids)
    assert end == (x, 95 - PLAYER_HALF_SIZE)


# No gap a player only just squeezes into, anywhere

def blocking(solids):
    """The solids that stop a player: not the walkable hedge (hiding, S-98)."""
    return [solid for solid in solids if not solid.get("walkable", False)]


def free_places(solids):
    """For every whole-numbered place: may a player's centre stand there?

    Counts the solid units under the player's square with a table of sums
    (each entry is the number of solid units above and left of it), so each
    place is asked in four look-ups instead of against every solid.
    """
    solid_unit = [[False] * WIDTH for _ in range(HEIGHT)]
    for solid in blocking(solids):
        for y in range(max(0, int(solid["y"])), min(HEIGHT, -int(-(solid["y"] + solid["h"]) // 1))):
            row = solid_unit[y]
            for x in range(max(0, int(solid["x"])), min(WIDTH, -int(-(solid["x"] + solid["w"]) // 1))):
                row[x] = True
    sums = [[0] * (WIDTH + 1) for _ in range(HEIGHT + 1)]
    for y in range(HEIGHT):
        running = 0
        for x in range(WIDTH):
            running += solid_unit[y][x]
            sums[y + 1][x + 1] = sums[y][x + 1] + running

    def is_free_here(x, y):
        if not (PLAYER_HALF_SIZE <= x <= WIDTH - PLAYER_HALF_SIZE and PLAYER_HALF_SIZE <= y <= HEIGHT - PLAYER_HALF_SIZE):
            return False
        top, bottom, left, right = y - PLAYER_HALF_SIZE, y + PLAYER_HALF_SIZE, x - PLAYER_HALF_SIZE, x + PLAYER_HALF_SIZE
        return sums[bottom][right] - sums[top][right] - sums[bottom][left] + sums[top][left] == 0

    return is_free_here


def reachable_places(solids, start=(CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])):
    """Every whole-numbered place a player's centre reaches from `start`, one unit at a time."""
    is_free_here = free_places(solids)
    seen = {start}
    waiting = deque([start])
    while waiting:
        x, y = waiting.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            place = (x + dx, y + dy)
            if place not in seen and is_free_here(*place):
                seen.add(place)
                waiting.append(place)
    return seen


def lane_between(first, second):
    """The rectangle between two solids that face each other, and its width; or None.

    They face each other when they overlap along one axis by more than a
    point: then the lane runs between them along the other axis.
    """
    left = max(first["x"], second["x"])
    right = min(first["x"] + first["w"], second["x"] + second["w"])
    top = max(first["y"], second["y"])
    bottom = min(first["y"] + first["h"], second["y"] + second["h"])
    if right > left and bottom < top:  # one above the other
        return {"x": left, "y": bottom, "w": right - left, "h": top - bottom}, top - bottom
    if bottom > top and right < left:  # side by side
        return {"x": right, "y": top, "w": left - right, "h": bottom - top}, left - right
    return None


def reachable_squeeze_gaps(solids):
    """Pairs of solids with a gap of 10 to 13 between them that a player's centre reaches."""
    reached = reachable_places(solids)
    found = []
    for first, second in itertools.combinations(blocking(solids), 2):
        lane = lane_between(first, second)
        if lane is None or lane[1] not in SQUEEZE_GAPS:
            continue
        rectangle = lane[0]
        inside = any(
            (x, y) in reached
            for x in range(int(rectangle["x"]), int(rectangle["x"] + rectangle["w"]) + 1)
            for y in range(int(rectangle["y"]), int(rectangle["y"] + rectangle["h"]) + 1)
        )
        if inside:
            found.append((first["id"], second["id"], lane[1]))
    return found


@pytest.fixture(scope="module")
def reached_from_spawn():
    return reachable_places(SOLIDS)


def test_no_two_solids_anywhere_leave_a_gap_of_10_to_13_that_a_player_reaches():
    assert reachable_squeeze_gaps(SOLIDS) == []


@pytest.mark.parametrize("solid_id, old_place, gap", [
    ("ctt-bookshelf", {"x": 34, "w": 112}, 11),  # 11 at each end, to the CTT's walls
    ("pingo-doce-checkout", {"x": 456}, 13),  # 13 to the fridge on the left wall
    ("pingo-doce-totem-2", {"x": 516}, 13),  # 13 to the checkout in its new place
], ids=["bookshelf", "checkout", "totem 2"])
def test_the_old_places_had_gaps_a_player_squeezed_into(solid_id, old_place, gap):
    # Rejected: the places before this to-do are found.
    found = reachable_squeeze_gaps(changed(solid_id, **old_place))
    assert [pair[2] for pair in found if solid_id in pair[:2]] != []
    assert all(pair[2] == gap for pair in found if solid_id in pair[:2]), found


def test_a_gap_of_14_or_of_9_is_no_squeeze_gap():
    # Edge cases: 14 leaves room (S-122), 9 is too narrow to get in at all.
    for width, expected in ((14, False), (13, True), (10, True), (9, False)):
        solids = [
            {"id": "a", "x": 100, "y": 100, "w": 40, "h": 40},
            {"id": "b", "x": 140 + width, "y": 100, "w": 40, "h": 40},
        ]
        assert (lane_between(solids[0], solids[1])[1] in SQUEEZE_GAPS) is expected, width


def test_a_gap_nobody_can_reach_is_no_squeeze_gap():
    # Edge case: two crates with a gap of 12 inside a closed box on the deck.
    box = [
        {"id": "box-top", "x": 300, "y": 400, "w": 60, "h": 4},
        {"id": "box-bottom", "x": 300, "y": 446, "w": 60, "h": 4},
        {"id": "box-left", "x": 300, "y": 400, "w": 4, "h": 50},
        {"id": "box-right", "x": 356, "y": 400, "w": 4, "h": 50},
        {"id": "crate-1", "x": 304, "y": 404, "w": 20, "h": 42},
        {"id": "crate-2", "x": 336, "y": 404, "w": 20, "h": 42},
    ]
    solids = [solid for solid in SOLIDS if solid["id"] not in ("deck-logo", "deck-tree-6")] + box
    assert [pair for pair in reachable_squeeze_gaps(solids) if "crate-1" in pair] == []


# Lamp posts

def distance_between(first, second):
    """The free space between two rectangles (0 when they touch or overlap)."""
    gap_x = max(second["x"] - (first["x"] + first["w"]), first["x"] - (second["x"] + second["w"]), 0)
    gap_y = max(second["y"] - (first["y"] + first["h"]), first["y"] - (second["y"] + second["h"]), 0)
    return max(gap_x, gap_y)


def nearest_wall_distance(lamp, solids=SOLIDS):
    return min(distance_between(lamp, solid) for solid in solids if solid["kind"] == "wall")


LAMPS = [solid for solid in SOLIDS if solid["kind"] == "lamp-post"]


def test_there_are_four_lamp_posts():
    assert len(LAMPS) == 4


@pytest.mark.parametrize("lamp", LAMPS, ids=lambda lamp: lamp["id"])
def test_every_lamp_post_touches_a_wall_or_stands_less_than_10_from_one(lamp):
    # Less than a player is wide: nobody gets caught between lamp and wall.
    assert nearest_wall_distance(lamp) < 10


@pytest.mark.parametrize("lamp_id, old_place", [
    ("deck-lamp-1", {"y": 247}), ("deck-lamp-2", {"y": 247}), ("deck-lamp-3", {"x": 180}), ("deck-lamp-4", {"x": 418}),
])
def test_the_old_places_of_the_lamp_posts_stood_14_to_17_in_front_of_a_wall(lamp_id, old_place):
    # Rejected: a player could walk between lamp and wall and get caught.
    solids = changed(lamp_id, **old_place)
    assert 14 <= nearest_wall_distance(solid_called(lamp_id, solids), solids) <= 17


def test_a_lamp_post_10_from_a_wall_is_too_far():
    # Edge case: 10 is exactly one player.
    wall = {"kind": "wall", "x": 0, "y": 0, "w": 100, "h": 6}
    lamp = {"kind": "lamp-post", "x": 50, "y": 16, "w": 4, "h": 4}
    assert nearest_wall_distance(lamp, [wall]) == 10
    assert not nearest_wall_distance(lamp, [wall]) < 10


# Station objects

# The box of each station's object with its outline at the high point of the
# pulse, as offsets from the station's centre (left, top, right, bottom), in
# whole map units. Measured in Chromium with the page's own drawing
# (play_map_polish_in_browser.js); the browser test below checks that the
# drawing still has exactly these boxes. The shadow and the number tag that
# draw.js adds below every object have boxes of their own below.
# Since the follow-up of M2-1.20 (Felix, 2026-11-22) the objects are drawn
# smaller and stand against a wall or a piece of furniture (art/stations.js).
STATION_BOXES = {
    1: (-12, -20, 18, 5),
    2: (-8, -13, 16, 13),
    3: (-19, -17, 8, 5),
    4: (-15, -5, 15, 18),
    5: (-20, -15, 5, 13),
    7: (-8, -20, 17, 7),
    8: (-15, -19, 7, 4),
    9: (-14, -12, 14, 11),
    10: (-12, -4, 12, 18),
    11: (-12, -10, 11, 11),
    12: (-11, -14, 12, 12),
}

# The box of each object alone, measured the same way: at most the size the
# brief asked for (Felix: "a bit too big") plus 2 in each direction.
OBJECT_BOXES = {
    1: (-7, -15, 13, 0),
    2: (-3, -8, 11, 8),
    3: (-14, -13, 3, 0),
    4: (-10, 0, 10, 13),
    5: (-15, -10, 0, 8),
    7: (-3, -15, 12, 2),
    8: (-10, -14, 0, -2),
    9: (-9, -7, 9, 6),
    10: (-7, 1, 7, 12),
    11: (-8, -5, 6, 6),
    12: (-6, -9, 6, 7),
}

# The size the brief asks for (width, height), in map units: 1 projector
# screen, 2 espresso machine, 3 tray with plates, 4 book cart, 5
# self-checkout, 7 flip chart, 8 to-go cup (on its little table), 9 lunch
# tray, 10 laptop (on its desk), 11 basket, 12 seagull on a bin. A chair is
# about 8-10, a café table 34, a character 39 high.
TARGET_SIZES = {
    1: (18, 14), 2: (13, 14), 3: (16, 11), 4: (18, 14), 5: (14, 16), 7: (13, 16),
    8: (8, 10), 9: (16, 11), 10: (14, 10), 11: (12, 10), 12: (12, 14),
}
# How much larger than its target a drawn object may be in each direction.
SIZE_ALLOWANCE = 2

# The soft shadow below each object (the furniture's shadow, measured with a
# smaller difference because it is faint; where the number tag covers it,
# the tag's box counts). Every drawing gives its own place, along its foot.
SHADOW_BOXES = {
    1: (-1, -1, 7, 2), 2: (-2, 7, 6, 10), 3: (-13, -1, -1, 2), 4: (-8, 10, 5, 13),
    5: (-14, 7, -4, 10), 7: (-1, 1, 7, 4), 8: (-8, -3, -4, 0), 9: (-7, 4, 4, 7),
    10: (-6, 9, 2, 12), 11: (-6, 5, 2, 8), 12: (-5, 6, 2, 9),
}
# The shadow at draw.js's default place (no own place), and the old round
# shadow there (until this follow-up).
DEFAULT_SHADOW_BOX = (-9, 10, 9, 13)
OLD_DEFAULT_SHADOW_BOX = (-10, 7, 8, 14)

# The number tag at the lower right of each object. (Station 2's tag keeps
# 1.8 units off the café's wall at x 447, station 8's off table 2.)
TAG_BOXES = {
    1: (7, -6, 17, 3), 2: (5, 1, 14, 11), 3: (-2, -7, 7, 3), 4: (4, 7, 14, 17),
    5: (-5, 1, 4, 11), 7: (6, -4, 16, 5), 8: (-4, -8, 5, 2), 9: (3, 0, 13, 10),
    10: (2, 6, 11, 16), 11: (1, 0, 10, 9), 12: (1, 0, 11, 10),
}

# The drawn box of each room's name, in map units (x0, y0, x1, y1), measured
# in Chromium; a station's outline keeps at least 1 unit away from it.
ROOM_NAME_BOXES = {
    "lecture-hall": (88, 146, 162, 156),
    "mon-cafe": (320, 146, 380, 156),
    "canteen": (539, 146, 591, 156),
    "ctt": (37, 242, 143, 252),
    "pingo-doce": (579, 415, 650, 428),
}
NAME_MARGIN = 1


def box_at(station_id, offsets):
    """A box of offsets from the station's centre, as a rectangle on the map."""
    station = station_called(station_id)
    left, top, right, bottom = offsets
    return {"x": station["x"] + left, "y": station["y"] + top, "w": right - left, "h": bottom - top}


def station_box(station_id):
    return box_at(station_id, STATION_BOXES[station_id])


def name_box(room_id, margin=0):
    x0, y0, x1, y1 = ROOM_NAME_BOXES[room_id]
    return {"x": x0 - margin, "y": y0 - margin, "w": x1 - x0 + 2 * margin, "h": y1 - y0 + 2 * margin}


def overlap(first, second):
    """Do the two rectangles overlap? Touching is not overlapping."""
    return (first["x"] < second["x"] + second["w"] and second["x"] < first["x"] + first["w"]
            and first["y"] < second["y"] + second["h"] and second["y"] < first["y"] + first["h"])


def test_every_station_with_an_object_has_a_box():
    with_objects = {station["id"] for station in CAMPUS["stations"]} - {6}  # 6 has no object yet (S-128)
    assert set(STATION_BOXES) == with_objects


@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_no_station_object_or_its_outline_lies_on_a_solid(station_id):
    box = station_box(station_id)
    assert [solid["id"] for solid in SOLIDS if overlap(box, solid)] == []


@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_no_station_shadow_or_number_tag_lies_on_a_solid(station_id):
    for offsets in (SHADOW_BOXES[station_id], TAG_BOXES[station_id]):
        box = box_at(station_id, offsets)
        assert [solid["id"] for solid in SOLIDS if overlap(box, solid)] == []


@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_every_station_outline_keeps_1_unit_clear_of_every_room_name(station_id):
    box = station_box(station_id)
    assert [room for room in ROOM_NAME_BOXES if overlap(box, name_box(room, NAME_MARGIN))] == []


def test_station_10_keeps_clear_of_the_ctt_name_and_of_study_table_2():
    # Edge case: the laptop's desk stands 2 units in front of study table 2
    # (its outline), and 12 below the name.
    box = station_box(10)
    assert box["y"] - ROOM_NAME_BOXES["ctt"][3] == 12
    assert solid_called("ctt-study-table-2")["y"] - (box["y"] + box["h"]) == 2


def test_station_10_drawn_in_its_old_place_touched_the_ctt_name():
    # Rejected: the outline then reached up to y 251, inside the name's margin.
    old = box_at(10, (-18, -17, 18, 14))
    assert overlap(old, name_box("ctt", NAME_MARGIN))


def test_stations_1_3_and_7_with_the_default_shadow_would_lie_on_a_solid():
    # Rejected: at the old default place the round shadow reached row 1's
    # desk (y 58), table 3 (y 58) and, measured where the tag does not cover
    # it, the wall left of station 7 (ending at x 23; the shadow reached x 22).
    assert overlap(box_at(1, OLD_DEFAULT_SHADOW_BOX), solid_called("lecture-hall-bench-1"))
    assert overlap(box_at(3, (-10, 7, 12, 14)), solid_called("canteen-table-3"))
    assert overlap(box_at(7, (-10, 7, 8, 14)), solid_called("lecture-hall-wall-left"))
    # The furniture's shadow at the new default place still would for 1 and 3.
    assert overlap(box_at(1, DEFAULT_SHADOW_BOX), solid_called("lecture-hall-bench-1"))
    assert overlap(box_at(3, DEFAULT_SHADOW_BOX), solid_called("canteen-table-3"))


@pytest.mark.parametrize("station_id", sorted(OBJECT_BOXES))
def test_every_object_is_at_most_its_target_size_plus_2(station_id):
    left, top, right, bottom = OBJECT_BOXES[station_id]
    width, height = TARGET_SIZES[station_id]
    assert right - left <= width + SIZE_ALLOWANCE
    assert bottom - top <= height + SIZE_ALLOWANCE


def test_the_old_objects_were_larger_than_their_targets_allow():
    # Rejected: the laptop of station 10 was 26 x 15 (keyboard 26 wide), the
    # coffee cup 16 x 21; the size check finds both.
    assert 26 > TARGET_SIZES[10][0] + SIZE_ALLOWANCE
    assert 16 > TARGET_SIZES[8][0] + SIZE_ALLOWANCE and 21 > TARGET_SIZES[8][1] + SIZE_ALLOWANCE


def test_an_object_exactly_2_larger_than_its_target_is_allowed():
    # Edge case: the cup of station 8 on its table is 10 x 12, its target 8 x 10.
    left, top, right, bottom = OBJECT_BOXES[8]
    assert (right - left, bottom - top) == (TARGET_SIZES[8][0] + 2, TARGET_SIZES[8][1] + 2)


def gap_between_boxes(first, second):
    """How far apart two rectangles are (0 when they touch or overlap)."""
    dx = max(second["x"] - (first["x"] + first["w"]), first["x"] - (second["x"] + second["w"]), 0)
    dy = max(second["y"] - (first["y"] + first["h"]), first["y"] - (second["y"] + second["h"]), 0)
    return max(dx, dy)


# Stations 9 and 12 stand in the open, drawn as things that stand free (a
# trolley, a bin). Station 9: table 3 lies 24 above its outline, the tray
# return 26 to the right behind the hiding spot, and any place nearer to them
# makes a way of the Duel longer. Station 12: the nearest solid, bush 4, lies
# 33 to the left; beside it the station would glow within a second's walk of
# the spawn, and a place further from the spawn makes ways longer (below).
STANDS_IN_THE_OPEN = {9, 12}
# How close an outline comes to the wall or furniture its object stands against.
LEANING_GAP = 3


@pytest.mark.parametrize("station_id", sorted(set(STATION_BOXES) - STANDS_IN_THE_OPEN))
def test_every_object_stands_against_a_wall_or_a_piece_of_furniture(station_id):
    box = station_box(station_id)
    assert min(gap_between_boxes(box, solid) for solid in SOLIDS) <= LEANING_GAP


def test_station_9_has_no_wall_or_furniture_within_reach():
    box = station_box(9)
    assert min(gap_between_boxes(box, solid) for solid in SOLIDS) == 24


def test_station_12_has_no_wall_or_furniture_within_reach():
    box = station_box(12)
    assert min(gap_between_boxes(box, solid) for solid in SOLIDS) == 33


def test_station_12_beside_the_bush_would_glow_within_a_second_of_the_spawn():
    # Rejected: at (568, 350), beside bush 4, the station lies 98 from the
    # spawn, less than one second's walk plus the use range
    # (test_play_stations.py); lower down, at (576, 368), the way from the
    # spawn becomes longer (137.5 -> 140.6).
    spawn = CAMPUS["spawn"]
    assert math.hypot(568 - spawn["x"], 350 - spawn["y"]) <= PLAYER_SPEED + USE_RANGE
    station = station_called(12)
    assert math.hypot(station["x"] - spawn["x"], station["y"] - spawn["y"]) > PLAYER_SPEED + USE_RANGE


def test_a_station_box_that_only_touches_a_solid_is_free():
    # Edge case: station 11's box begins exactly where shelf 3 ends.
    shelf = solid_called("pingo-doce-shelf-3")
    assert station_box(11)["x"] == shelf["x"] + shelf["w"]
    assert not overlap(station_box(11), shelf)
    assert gap_between_boxes(station_box(11), shelf) == 0
    touching = {"x": 0, "y": 0, "w": 10, "h": 10}
    assert not overlap(touching, {"x": 10, "y": 0, "w": 5, "h": 5})


@pytest.mark.parametrize("station_id", sorted(minigames.MINIGAMES))
def test_every_station_can_be_used_from_a_place_the_spawn_reaches(reached_from_spawn, station_id):
    station = station_called(station_id)
    near = [
        (x, y) for x in range(station["x"] - USE_RANGE, station["x"] + USE_RANGE + 1)
        for y in range(station["y"] - USE_RANGE, station["y"] + USE_RANGE + 1)
        if (x, y) in reached_from_spawn
    ]
    assert any(station_in_range(x, y, [station], USE_RANGE) == station_id for x, y in near)


def test_a_station_walled_in_cannot_be_used_from_anywhere_the_spawn_reaches():
    # Rejected: station 11 in a closed box of solids.
    station = station_called(11)
    box = [
        {"id": "wall-a", "x": station["x"] - 40, "y": station["y"] - 40, "w": 80, "h": 4},
        {"id": "wall-b", "x": station["x"] - 40, "y": station["y"] + 36, "w": 80, "h": 4},
        {"id": "wall-c", "x": station["x"] - 40, "y": station["y"] - 40, "w": 4, "h": 80},
        {"id": "wall-d", "x": station["x"] + 36, "y": station["y"] - 40, "w": 4, "h": 80},
    ]
    reached = reachable_places(SOLIDS + box)
    near = [(x, y) for (x, y) in reached if abs(x - station["x"]) <= USE_RANGE and abs(y - station["y"]) <= USE_RANGE]
    assert not any(station_in_range(x, y, [station], USE_RANGE) == 11 for x, y in near)


# The Duel's ways

# Measured with paths.station_distances on the map before this to-do (main
# at f8cd9a3: the Felix mix of M2-1.19 with the walkable hedge of M3-1.4),
# in map units: the spawn and every station with a minigame (1-5 and 7-12),
# 66 ways.
WAYS_BEFORE_THIS_TO_DO = {
    (SPAWN, 1): 598.676, (SPAWN, 2): 341.304, (SPAWN, 3): 326.274, (SPAWN, 4): 718.108, (SPAWN, 5): 262.510,
    (SPAWN, 7): 614.960, (SPAWN, 8): 296.617, (SPAWN, 9): 250.392, (SPAWN, 10): 502.794, (SPAWN, 11): 266.108,
    (SPAWN, 12): 137.539, (1, 2): 573.990, (1, 3): 815.362, (1, 4): 568.167, (1, 5): 856.500,
    (1, 7): 175.314, (1, 8): 506.108, (1, 9): 739.480, (1, 10): 352.853, (1, 11): 860.098,
    (1, 12): 736.215, (2, 3): 531.245, (2, 4): 716.617, (2, 5): 599.127, (2, 7): 590.274,
    (2, 8): 181.255, (2, 9): 455.362, (2, 10): 501.304, (2, 11): 602.725, (2, 12): 464.784,
    (3, 4): 957.990, (3, 5): 542.392, (3, 7): 831.647, (3, 8): 491.245, (3, 9): 109.657,
    (3, 10): 742.676, (3, 11): 536.049, (3, 12): 346.794, (4, 5): 975.931, (4, 7): 556.569,
    (4, 8): 648.735, (4, 9): 882.108, (4, 10): 277.941, (4, 11): 979.529, (4, 12): 855.647,
    (5, 7): 872.784, (5, 8): 554.441, (5, 9): 466.510, (5, 10): 760.617, (5, 11): 168.284,
    (5, 12): 214.510, (7, 8): 522.392, (7, 9): 755.765, (7, 10): 341.255, (7, 11): 876.382,
    (7, 12): 752.500, (8, 9): 415.362, (8, 10): 433.421, (8, 11): 558.039, (8, 12): 424.784,
    (9, 10): 666.794, (9, 11): 460.167, (9, 12): 270.912, (10, 11): 764.215, (10, 12): 640.333,
    (11, 12): 208.167,
}

# The pinned values are rounded to 0.001: a way as long as before may differ by that.
ROUNDING = 0.001


def ways_longer_than_before(measured, before=WAYS_BEFORE_THIS_TO_DO):
    """The ways of `before` that `measured` (both orders of each pair) makes longer."""
    return [
        pair for pair, length in before.items()
        if measured[pair] > length + ROUNDING or measured[pair[::-1]] > length + ROUNDING
    ]


@pytest.fixture(scope="module")
def ways_now():
    return station_distances(CAMPUS, sorted(minigames.MINIGAMES))


def test_the_pinned_ways_are_every_way_between_the_spawn_and_the_duel_stations():
    places = [SPAWN] + sorted(minigames.MINIGAMES)
    assert sorted(minigames.MINIGAMES) == [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    assert {frozenset(pair) for pair in WAYS_BEFORE_THIS_TO_DO} == {
        frozenset(pair) for pair in itertools.combinations(places, 2)
    }
    assert len(WAYS_BEFORE_THIS_TO_DO) == 66


def test_no_way_of_the_duel_became_longer(ways_now):
    assert ways_longer_than_before(ways_now) == []


def test_the_aisles_and_free_stations_made_some_ways_much_shorter(ways_now):
    # Measured for this to-do against main before it: 46 of the 66 ways
    # became shorter and none longer. The largest change is 5 to 11, 32 %
    # shorter (station 11 in the aisle between the shelves); others are
    # 9 to 11 14.6 %, spawn to 11 13.5 %, 11 to 12 17.3 %, 8 to 10 9.9 % and
    # 1 to 7 6.5 %.
    assert ways_now[(5, 11)] == pytest.approx(113.941, abs=ROUNDING)
    assert ways_now[(11, 12)] == pytest.approx(172.167, abs=ROUNDING)
    assert ways_now[(8, 10)] == pytest.approx(390.392, abs=ROUNDING)


# The follow-up of M2-1.20 (station objects drawn like the furniture) may
# move a station only if no way becomes longer; it moved none in the end.
# Measured on the branch before the follow-up (b592c7c), the same 66 ways.
WAYS_ON_THE_BRANCH_BEFORE_THE_FOLLOW_UP = {
    (SPAWN, 1): 598.676, (SPAWN, 2): 339.647, (SPAWN, 3): 326.274, (SPAWN, 4): 718.108,
    (SPAWN, 5): 262.510, (SPAWN, 7): 614.960, (SPAWN, 8): 285.304, (SPAWN, 9): 219.362,
    (SPAWN, 10): 471.078, (SPAWN, 11): 230.108, (SPAWN, 12): 137.539, (1, 2): 572.333,
    (1, 3): 815.362, (1, 4): 568.167, (1, 5): 856.500, (1, 7): 164.000, (1, 8): 494.794,
    (1, 9): 706.108, (1, 10): 321.137, (1, 11): 824.098, (1, 12): 736.215, (2, 3): 529.588,
    (2, 4): 714.960, (2, 5): 597.470, (2, 7): 588.617, (2, 8): 174.912, (2, 9): 420.333,
    (2, 10): 467.931, (2, 11): 565.068, (2, 12): 463.127, (3, 4): 957.990, (3, 5): 542.392,
    (3, 7): 831.647, (3, 8): 479.931, (3, 9): 109.255, (3, 10): 710.960, (3, 11): 500.049,
    (3, 12): 346.794, (4, 5): 975.931, (4, 7): 556.569, (4, 8): 637.421, (4, 9): 848.735,
    (4, 10): 274.912, (4, 11): 943.529, (4, 12): 855.647, (5, 7): 872.784, (5, 8): 543.127,
    (5, 9): 435.480, (5, 10): 728.902, (5, 11): 113.941, (5, 12): 214.510, (7, 8): 511.078,
    (7, 9): 722.392, (7, 10): 309.539, (7, 11): 840.382, (7, 12): 752.500, (8, 9): 370.676,
    (8, 10): 390.392, (8, 11): 510.725, (8, 12): 413.470, (9, 10): 601.706, (9, 11): 393.137,
    (9, 12): 239.882, (10, 11): 696.500, (10, 12): 608.617, (11, 12): 172.167,
}


def test_the_pinned_ways_of_the_branch_are_the_same_66_ways():
    assert set(WAYS_ON_THE_BRANCH_BEFORE_THE_FOLLOW_UP) == set(WAYS_BEFORE_THIS_TO_DO)


def test_no_way_of_the_duel_became_longer_than_on_the_branch(ways_now):
    assert ways_longer_than_before(ways_now, WAYS_ON_THE_BRANCH_BEFORE_THE_FOLLOW_UP) == []


def test_no_way_of_the_duel_changed_in_the_follow_up(ways_now):
    before = WAYS_ON_THE_BRANCH_BEFORE_THE_FOLLOW_UP
    assert all(ways_now[pair] == pytest.approx(length, abs=ROUNDING) for pair, length in before.items())


def test_a_way_one_unit_longer_is_found_and_one_as_long_is_not():
    # Rejected and edge case for the check itself.
    measured = {}
    for pair, length in WAYS_BEFORE_THIS_TO_DO.items():
        measured[pair] = measured[pair[::-1]] = length + ROUNDING / 2
    assert ways_longer_than_before(measured) == []
    measured[(4, 5)] += 1
    assert ways_longer_than_before(measured) == [(4, 5)]


# In Chromium: the drawn station objects lie on no drawn furniture

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_map_polish_in_browser.js")

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def drawn():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            time.sleep(0.1)
        finished = subprocess.run(
            [NODE, str(BROWSER_SCRIPT), base],
            env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
        )
        assert finished.returncode == 0, finished.stderr
        result = json.loads(finished.stdout)
        result["stations"] = {row["id"]: row for row in result["stations"]}
        return result
    finally:
        server.terminate()
        server.wait(timeout=10)


@needs_chromium
def test_the_map_with_its_stations_draws_without_a_console_error_or_warning(drawn):
    assert drawn["console"] == []


@needs_chromium
def test_every_station_object_is_drawn(drawn):
    assert sorted(drawn["stations"]) == sorted(STATION_BOXES)


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_the_object_and_its_outline_lie_on_no_drawn_furniture_and_in_no_wall(drawn, station_id):
    row = drawn["stations"][station_id]
    assert row["object"]["onFurnitureOrWall"] == []
    assert row["objectAndLowOutline"]["onFurnitureOrWall"] == []
    assert row["objectAndHighOutline"]["onFurnitureOrWall"] == []


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_the_pinned_box_is_the_drawn_object_with_its_outline(drawn, station_id):
    box = drawn["stations"][station_id]["objectAndHighOutline"]["box"]
    assert (box["left"], box["top"], box["right"], box["bottom"]) == STATION_BOXES[station_id]


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(OBJECT_BOXES))
def test_the_pinned_object_box_is_the_drawn_object(drawn, station_id):
    box = drawn["stations"][station_id]["object"]["box"]
    assert (box["left"], box["top"], box["right"], box["bottom"]) == OBJECT_BOXES[station_id]


# draw.js grows the outline inside a square of 2 x OBJECT_HALF_SIZE units
# around the station; the outline reaches OUTLINE_GROWTH_HIGH beyond the
# object (and its soft edge a little more), so the drawing must stay this
# far inside the square, or the outline is cut off straight.
OBJECT_HALF_SIZE = 20
OUTLINE_GROWTH_HIGH = 4.2
OUTLINE_EDGE = 0.5


def outline_fits(reach):
    """Does an outline grown around a drawing that reaches this far fit the square?"""
    return max(abs(side) for side in reach) + OUTLINE_GROWTH_HIGH + OUTLINE_EDGE <= OBJECT_HALF_SIZE


def test_an_object_reaching_16_units_from_its_centre_would_have_its_outline_cut_off():
    # Edge case and rejected: 15.3 units is the most that fits; the first
    # projector screen of this follow-up reached 15.4 up, and the one before
    # the follow-up 18.4.
    assert outline_fits([-6.4, -15.3, 12.4, -0.1])
    assert not outline_fits([-6.4, -15.4, 12.4, -0.1])
    assert not outline_fits([-6.4, -18.4, 12.4, -0.1])


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_every_outline_fits_into_the_square_it_is_grown_in(drawn, station_id):
    assert outline_fits(drawn["reach"][str(station_id)])


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_the_shadow_and_number_tag_lie_on_no_drawn_furniture_and_in_no_wall(drawn, station_id):
    assert drawn["stations"][station_id]["shadowAndTag"]["onFurnitureOrWall"] == []


@needs_chromium
@pytest.mark.parametrize("station_id", sorted(STATION_BOXES))
def test_the_pinned_shadow_and_tag_boxes_are_the_drawn_ones(drawn, station_id):
    row = drawn["stations"][station_id]
    for part, pinned in (("shadow", SHADOW_BOXES), ("tag", TAG_BOXES)):
        box = row[part]["box"]
        assert (box["left"], box["top"], box["right"], box["bottom"]) == pinned[station_id], part


# What is drawn is what blocks (M2-1.20): the bushes, the NOVA logo and the
# lecture rows fill their solids. Before, a bush was about 67 % drawn, the
# logo 50 % and a row 63 %. (test_play_campus_detail.py's LEAST_DRAWN_SHARE
# of 0.25 still holds for every solid.)
FILLED_KINDS = ("tree", "logo", "bench")
LEAST_FILLED_SHARE = 0.9


def too_little_drawn(coverage, kinds=FILLED_KINDS, least=LEAST_FILLED_SHARE):
    """The ids of the solids of `kinds` of which less than `least` is drawn."""
    return [row["id"] for row in coverage if row["kind"] in kinds and row["share"] < least]


def test_a_bush_drawn_as_round_as_before_is_too_little_drawn():
    # Rejected: the old round crown, and edge case: exactly 0.9 is enough.
    coverage = [
        {"id": "deck-tree-1", "kind": "tree", "share": 0.67},
        {"id": "deck-tree-2", "kind": "tree", "share": 0.9},
        {"id": "deck-pool", "kind": "pool", "share": 0.5},  # not one of the kinds
    ]
    assert too_little_drawn(coverage) == ["deck-tree-1"]


@needs_chromium
def test_every_bush_the_logo_and_every_lecture_row_are_drawn_to_their_edges(drawn):
    rows = [row for row in drawn["coverage"] if row["kind"] in FILLED_KINDS]
    assert sorted(row["kind"] for row in rows) == ["bench"] * 3 + ["logo"] + ["tree"] * 6
    assert too_little_drawn(drawn["coverage"]) == []


@needs_chromium
def test_the_pinned_room_name_boxes_are_the_drawn_names(drawn):
    measured = {row["id"]: row["box"] for row in drawn["roomNames"]}
    assert {room: (box["x0"], box["y0"], box["x1"], box["y1"]) for room, box in measured.items()} == ROOM_NAME_BOXES


# The shadow's and the tag's place in draw.js, and the drawings' lines (with
# Node, the real drawing files)

SHADOWS_IN_NODE = Path(__file__).with_name("station_shadows_in_node.js")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed")

# The places draw.js uses for a drawing that gives none of its own: the
# shadow's top left corner and width, and the tag's middle.
DEFAULT_SHADOW = (-9, 10, 18)
DEFAULT_TAG = (11, 9)


def drawn_in_node(station_ids, shadows=None, tags=None):
    """What draw.js draws for each station: {id: {"shadows", "tags", "strokes"}}."""
    stations = [station_called(station_id) for station_id in station_ids]
    finished = subprocess.run(
        [NODE, str(SHADOWS_IN_NODE)],
        input=json.dumps({"stations": stations, "shadows": shadows or {}, "tags": tags or {}}),
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return {int(key): value for key, value in json.loads(finished.stdout).items()}


def shadows_drawn(station_ids, shadows=None):
    """Where draw.js draws the shadow of each station: {id: [(x, y, w), ...]}."""
    drawn = drawn_in_node(station_ids, shadows=shadows)
    return {key: [tuple(place) for place in value["shadows"]] for key, value in drawn.items()}


def tags_drawn(station_ids, tags=None):
    """Where draw.js draws the number tag of each station: {id: [(x, y), ...]}."""
    drawn = drawn_in_node(station_ids, tags=tags)
    return {key: [tuple(place) for place in value["tags"]] for key, value in drawn.items()}


def on_map(station_id, offsets):
    """Offsets from a station's centre (x, y, and a width that stays) on the map."""
    station = station_called(station_id)
    return (station["x"] + offsets[0], station["y"] + offsets[1]) + tuple(offsets[2:])


@needs_node
def test_a_drawing_without_its_own_shadow_place_gets_the_default_shadow():
    drawn = shadows_drawn(sorted(STATION_BOXES), {station_id: "default" for station_id in STATION_BOXES})
    for station_id in STATION_BOXES:
        assert drawn[station_id] == [on_map(station_id, DEFAULT_SHADOW)], station_id


@needs_node
def test_every_station_draws_its_shadow_along_the_foot_of_its_object():
    # The places art/stations.js gives (left, top, width, from the centre):
    # the projector's tripod, the book cart between its wheels, the tray
    # stand along its whole foot (1 in from each side).
    drawn = shadows_drawn([1, 3, 4])
    assert drawn[1] == [on_map(1, (-1, -1, 8))]
    assert drawn[3] == [on_map(3, (-12.5, -1, 14))]
    assert drawn[4] == [on_map(4, (-8, 10.5, 16))]


@needs_node
def test_a_drawing_that_says_it_has_no_shadow_gets_none():
    assert shadows_drawn([4], {4: None}) == {4: []}


@needs_node
def test_without_its_own_place_station_1_gets_the_default_shadow_again():
    assert shadows_drawn([1], {1: "default"}) == {1: [on_map(1, DEFAULT_SHADOW)]}


@needs_node
@pytest.mark.parametrize("shadow", [
    {"x": "1", "y": 2, "w": 3}, {"x": 1, "y": 2}, {"x": 1, "y": 2, "w": 0}, {"x": 1, "y": 2, "w": -4},
    "below", 5, [1, 2], True,
], ids=["text", "no width", "width 0", "width below 0", "word", "number", "list", "true"])
def test_a_shadow_place_that_is_not_three_numbers_gives_the_default_shadow(shadow):
    # Edge cases: a broken place never moves or hides the shadow.
    assert shadows_drawn([4], {4: shadow}) == {4: [on_map(4, DEFAULT_SHADOW)]}


@needs_node
def test_a_drawing_without_its_own_tag_place_gets_the_tag_at_the_old_place():
    drawn = tags_drawn(sorted(STATION_BOXES), {station_id: "default" for station_id in STATION_BOXES})
    for station_id in STATION_BOXES:
        assert drawn[station_id] == [on_map(station_id, DEFAULT_TAG)], station_id


@needs_node
def test_every_tag_sits_at_the_lower_right_of_its_object():
    # The tag's middle lies on the object's lower right corner (1 above its
    # foot), or a little inside it where a wall or a table is close (2, 8, 11).
    drawn = tags_drawn([1, 2, 3, 8, 11])
    assert drawn[1] == [on_map(1, (12, -1.5))]
    assert drawn[2] == [on_map(2, (9.5, 6))]
    assert drawn[3] == [on_map(3, (2.5, -2))]
    assert drawn[8] == [on_map(8, (0.5, -3))]
    assert drawn[11] == [on_map(11, (5.5, 4.5))]


@needs_node
def test_a_tag_place_of_its_own_is_used():
    assert tags_drawn([4], {4: {"x": -3, "y": 2.5}}) == {4: [on_map(4, (-3, 2.5))]}


@needs_node
@pytest.mark.parametrize("tag", [
    None, {"x": 1}, {"x": "1", "y": 2}, {"x": 1, "y": None}, "corner", 5, [1, 2], True,
], ids=["none", "no y", "text", "y none", "word", "number", "list", "true"])
def test_a_tag_place_that_is_not_two_numbers_gives_the_default_tag(tag):
    # Edge cases: a broken place never moves or hides the number.
    assert tags_drawn([4], {4: tag}) == {4: [on_map(4, DEFAULT_TAG)]}


# The furniture's line widths: an outer outline of 0.6-0.8 (the furniture of
# the rooms uses up to 1), finer lines inside. No drawing may stroke wider
# than WIDEST_LINE; before this follow-up the outlines were 1.4 and the
# projector's roller 2.4.
WIDEST_LINE = 1
OUTLINE_COLOUR = "#2E2A3B"


def too_wide(strokes, widest=WIDEST_LINE):
    """The widths of the strokes wider than `widest`."""
    return [width for width, _colour in strokes if width > widest]


def test_a_line_of_1_4_is_too_wide_and_one_of_1_is_not():
    # Rejected and edge case for the check itself.
    assert too_wide([[1.4, OUTLINE_COLOUR], [1, OUTLINE_COLOUR], [0.4, "#FFFFFF"]]) == [1.4]
    assert too_wide([[1, OUTLINE_COLOUR]]) == []


@needs_node
def test_no_station_drawing_strokes_a_line_wider_than_1():
    drawn = drawn_in_node(sorted(STATION_BOXES))
    for station_id in STATION_BOXES:
        strokes = drawn[station_id]["strokes"]
        assert strokes != [], station_id
        assert too_wide(strokes) == [], station_id


@needs_node
def test_every_station_drawing_has_an_outline_as_fine_as_the_furniture():
    drawn = drawn_in_node(sorted(STATION_BOXES))
    for station_id in STATION_BOXES:
        outline = [width for width, colour in drawn[station_id]["strokes"] if colour == OUTLINE_COLOUR]
        assert 0.6 <= max(outline) <= 0.8, station_id
