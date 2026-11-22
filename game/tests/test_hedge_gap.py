"""The hedge on the Main Deck touches tree 3, so no player fits between them (M1-1.5).

Before, tree 3 ended at x 556 and the hedge began at x 566: a gap of exactly
10 units, as wide as a player. A player could stand in it and was drawn over
both. Now the hedge begins at x 556. These tests use the real map file and
the real walking rules.

They are about a solid hedge (S-87). Since M3-1.4 the hedge is walkable for
hiding (S-98), so these tests run on a copy of the real map with the hedge
made solid again: the gap to tree 3 must stay closed should the hedge ever be
solid again. Walking into the walkable hedge is tested in
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

# The strip between the right edge of tree 3 and the old left edge of the
# hedge, where both had a side: from the top of the tree (y 238) to the
# bottom of the hedge (y 262). Below y 262 there is only open deck.
OLD_GAP = {"x": 556, "y": 238, "w": 10, "h": 24}

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


def old_map():
    """A copy of the real map with the hedge where it was before: x 566, w 58."""
    old = copy.deepcopy(CAMPUS)
    old_hedge = next(item for item in old["solids"] if item["id"] == "deck-hedge")
    old_hedge["x"], old_hedge["w"] = 566, 58
    return old


def old_map_solids():
    """The solids of the map with the old hedge, which left a gap to tree 3."""
    return old_map()["solids"]


def numbers_from_to(low, high, size):
    """All numbers from `low` to `high`, `size` apart, both ends included."""
    count = round((high - low) / size)
    return [low + index * size for index in range(count + 1)]


# The map data


def test_the_hedge_starts_where_tree_3_ends_and_keeps_its_right_edge():
    hedge = solid("deck-hedge")
    tree = solid("deck-tree-3")
    assert hedge["x"] == tree["x"] + tree["w"] == 556
    assert hedge["x"] + hedge["w"] == 624
    assert (hedge["y"], hedge["h"]) == (236, 26)


def test_the_hiding_spot_still_lies_inside_the_hedge():
    hedge = solid("deck-hedge")
    # Found by its position, and only x, y and r compared, so that a field
    # added later (an id, a room) does not break this test.
    spot = next(spot for spot in CAMPUS["hiding_spots"] if (spot["x"], spot["y"]) == (595, 249))
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


# Rejected: nobody can stand in the old gap


def test_no_position_in_the_old_gap_is_free():
    # Looking every 0.5 units is enough: the old gap lies wholly inside the new
    # hedge, so every player square that overlaps the gap also overlaps the
    # hedge. The loop only checks that on many positions, the edges included.
    checked = 0
    for x in numbers_from_to(551, 571, 0.5):
        for y in numbers_from_to(231, 267, 0.5):
            if overlaps(x, y, OLD_GAP):
                checked += 1
                assert not is_free(x, y, SOLIDS, WIDTH, HEIGHT), (x, y)
    # Make sure the loop really looked at many positions.
    assert checked > 1000


def test_the_old_map_had_room_for_a_player_in_the_gap():
    # Shows that the test above would have caught the old gap.
    assert is_free(561, 249, old_map_solids(), WIDTH, HEIGHT)


def test_walking_up_into_the_old_gap_stops_below_the_hedge():
    positions = walk(561, 300, 0, -1, 3)
    # The hedge's bottom edge is y 262 and the player is 10 high.
    assert all(y >= 262 + 5 for _, y in positions)
    assert positions[-1] == (561, 267)


def test_walking_down_into_the_old_gap_stops_above_the_hedge():
    positions = walk(561, 210, 0, 1, 3)
    # The hedge's top edge is y 236, above the top of tree 3 (y 238).
    assert all(y <= 236 - 5 for _, y in positions)
    assert positions[-1] == (561, 231)


def test_on_the_old_map_a_player_walked_straight_through_the_gap():
    positions = walk(561, 300, 0, -1, 3, old_map_solids())
    assert positions[-1][1] < 230


# Accepted: the ways around tree 3 and the hedge are still open


def test_a_player_can_still_walk_up_left_of_tree_3():
    x, y = walk(520, 300, 0, -1, 3)[-1]
    assert x == 520
    assert y < 230


def test_a_player_can_still_walk_up_right_of_the_hedge_past_the_button():
    # Between the hedge (right edge 624) and the deck wall (x 657) there are
    # 33 units of room. The button is not solid, so walking over it is fine.
    x, y = walk(640, 300, 0, -1, 3)[-1]
    assert x == 640
    assert y < 230


@pytest.mark.parametrize("x", [629, 652])
def test_the_way_right_of_the_hedge_is_open_from_wall_to_hedge(x):
    # The leftmost and rightmost lanes in that way: touching the hedge, touching the wall.
    for y in numbers_from_to(225, 275, 1):
        assert is_free(x, y, SOLIDS, WIDTH, HEIGHT), (x, y)


def test_the_duel_walking_distances_are_the_same_as_with_the_old_hedge():
    # The gap was only 10 units wide, and with a grid step of 4 no grid point
    # of `paths` fitted into it, so closing it changes no walking distance.
    stations = sorted(minigames.MINIGAMES)
    assert station_distances(CAMPUS, stations) == station_distances(old_map(), stations)
