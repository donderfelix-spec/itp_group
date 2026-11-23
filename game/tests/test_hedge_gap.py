"""The hedge on the Main Deck touches the deck's right wall, so no player fits between them.

Until M3-1.7 the hedge lay left to right at the top right of the deck and
began where tree 3 ends, closing a gap exactly one player wide (M1-1.5,
S-111). Since M3-1.7 (S-196) it stands upright along the right wall, and the
same rule moves with it: the hedge ends where the wall begins (x 657), so
no player can squeeze in between and be drawn over both. Tree 3 now stands
on its own. These tests use the real map file and the real walking rules.

They are about a solid hedge (S-87). Since M3-1.4 the hedge is walkable for
hiding (S-98), so these tests run on a copy of the real map with the hedge
made solid again: the gap to the wall must stay closed should the hedge ever
be solid again. Walking into the walkable hedge is tested in
`test_hiding_visibility.py`.
"""

import copy
import math

import pytest

from server.modes import minigames
from server.world.campus import load_campus
from server.world.movement import is_free, overlaps, step
from server.world.paths import station_distances

# Keep the closed-hedge regression scenarios as a historical collision fixture.
# The current walkable hedge and visibility are covered by test_hiding_visibility.py.
CAMPUS = load_campus()
next(solid for solid in CAMPUS["solids"] if solid["id"] == "deck-hedge")["walkable"] = False
SOLIDS = CAMPUS["solids"]
WIDTH = CAMPUS["width"]
HEIGHT = CAMPUS["height"]

# The strip at the wall that a hedge 10 units narrower would leave open:
# from its right edge (x 647) to the wall (x 657), as high as the hedge
# (y 255 to 323). Exactly one player wide, like the old gap at tree 3.
WALL_GAP = {"x": 647, "y": 255, "w": 10, "h": 68}

# One step of a walk, the same length as a tick of the server.
TICK_SECONDS = 0.05


def solid(solid_id):
    return next(item for item in SOLIDS if item["id"] == solid_id)


def walk(x, y, dx, dy, seconds, solids=SOLIDS):
    """Walk for `seconds` in small steps and return every position on the way."""
    positions = [(x, y)]
    for _ in range(round(seconds / TICK_SECONDS)):
        x, y = step(x, y, dx, dy, TICK_SECONDS, solids, WIDTH, HEIGHT)
        positions.append((x, y))
    return positions


def narrower_map():
    """A copy of the real map with a hedge 10 units narrower: x 631, w 16, leaving a gap at the wall."""
    narrower = copy.deepcopy(CAMPUS)
    hedge = next(item for item in narrower["solids"] if item["id"] == "deck-hedge")
    hedge["w"] = 16
    return narrower


def narrower_map_solids():
    """The solids of the map with the narrower hedge, which leaves a gap at the wall."""
    return narrower_map()["solids"]


def numbers_from_to(low, high, size):
    """All numbers from `low` to `high`, `size` apart, both ends included."""
    count = round((high - low) / size)
    return [low + index * size for index in range(count + 1)]


# The map data


def test_the_hedge_stands_upright_and_ends_where_the_right_wall_begins():
    hedge = solid("deck-hedge")
    wall = solid("deck-wall-right")
    assert hedge["x"] + hedge["w"] == wall["x"] == 657
    assert (hedge["x"], hedge["y"], hedge["w"], hedge["h"]) == (631, 255, 26, 68)
    assert hedge["h"] > hedge["w"]


def test_the_hiding_spot_still_lies_inside_the_hedge():
    hedge = solid("deck-hedge")
    # Found by its position, and only x, y and r compared, so that a field
    # added later (an id, a room) does not break this test.
    spot = next(spot for spot in CAMPUS["hiding_spots"] if (spot["x"], spot["y"]) == (644, 297))
    assert spot["r"] == 9
    assert hedge["x"] <= spot["x"] - spot["r"]
    assert spot["x"] + spot["r"] <= hedge["x"] + hedge["w"]
    assert hedge["y"] <= spot["y"] - spot["r"]
    assert spot["y"] + spot["r"] <= hedge["y"] + hedge["h"]


def test_the_emergency_button_is_in_clear_space_at_the_center_of_the_deck():
    button = CAMPUS["button"]
    assert (button["x"], button["y"], button["r"]) == (365, 375, 11)
    x, y, radius = button["x"], button["y"], button["r"]

    for solid in SOLIDS:
        closest_x = min(max(x, solid["x"]), solid["x"] + solid["w"])
        closest_y = min(max(y, solid["y"]), solid["y"] + solid["h"])
        assert math.dist((x, y), (closest_x, closest_y)) > radius, solid["id"]

    for point in CAMPUS["hiding_spots"] + CAMPUS["stations"]:
        assert math.dist((x, y), (point["x"], point["y"])) > radius + point["r"]


# Rejected: nobody can stand between the hedge and the wall


def test_no_position_between_the_hedge_and_the_wall_is_free():
    # The strip lies wholly inside the hedge, so every player square that
    # overlaps it also overlaps the hedge. The loop only checks that on many
    # positions, the edges included.
    checked = 0
    for x in numbers_from_to(642, 662, 0.5):
        for y in numbers_from_to(250, 328, 0.5):
            if overlaps(x, y, WALL_GAP):
                checked += 1
                assert not is_free(x, y, SOLIDS, WIDTH, HEIGHT), (x, y)
    # Make sure the loop really looked at many positions.
    assert checked > 1000


def test_a_hedge_10_units_narrower_would_leave_room_for_a_player_at_the_wall():
    # Shows that the test above would catch such a gap.
    assert is_free(652, 289, narrower_map_solids(), WIDTH, HEIGHT)


def test_walking_up_along_the_wall_stops_below_the_hedge():
    positions = walk(652, 360, 0, -1, 3)
    # The hedge's bottom edge is y 323 and the player is 10 high.
    assert all(y >= 323 + 5 for _, y in positions)
    assert positions[-1] == (652, 328)


def test_walking_down_along_the_wall_stops_above_the_hedge():
    positions = walk(652, 205, 0, 1, 3)
    # The hedge's top edge is y 255.
    assert all(y <= 255 - 5 for _, y in positions)
    assert positions[-1] == (652, 250)


def test_with_a_narrower_hedge_a_player_walked_straight_along_the_wall():
    positions = walk(652, 360, 0, -1, 3, narrower_map_solids())
    assert positions[-1][1] < 250


# Accepted: the ways around tree 3 and the hedge are still open


def test_a_player_can_still_walk_up_left_of_tree_3():
    x, y = walk(520, 300, 0, -1, 3)[-1]
    assert x == 520
    assert y < 230


def test_a_player_can_now_walk_up_right_of_tree_3_where_the_hedge_was():
    # The old hedge lay at x 556 to 624, y 236 to 262; that is open deck now.
    x, y = walk(590, 300, 0, -1, 3)[-1]
    assert x == 590
    assert y < 230


def test_a_player_can_walk_up_left_of_the_hedge():
    # The lane touching the hedge's left side (x 631) is open from below to
    # the corridor.
    x, y = walk(626, 360, 0, -1, 3)[-1]
    assert x == 626
    assert y < 230


@pytest.mark.parametrize("x", [626, 600])
def test_the_way_left_of_the_hedge_is_open_beside_it(x):
    # The lane touching the hedge and one further out, along the hedge's whole height.
    for y in numbers_from_to(245, 335, 1):
        assert is_free(x, y, SOLIDS, WIDTH, HEIGHT), (x, y)


def test_the_duel_walking_distances_are_the_same_as_with_a_narrower_hedge():
    # A gap of 10 units at the wall would not shorten any way of the Duel:
    # going round the hedge's left side is as short, so closing it at the
    # wall changes no walking distance.
    stations = sorted(minigames.MINIGAMES)
    assert station_distances(CAMPUS, stations) == station_distances(narrower_map(), stations)
