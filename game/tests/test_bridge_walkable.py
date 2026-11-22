"""The browser's copy of the walking rule knows walkable solids like the server (M3-1.4).

`step` in client/js/world/bridge.js is a copy of `step()` in
server/world/movement.py (S-121). Since the hedge became walkable (S-98)
both let a player walk into and through a solid marked `"walkable": true`.
These walks in and around the hedge of the real map must end on the very
same place in both. Without Node these tests are skipped; CI has Node.
"""

import pytest

from server.main import app
from server.world import movement
from test_bridge_rule import NODE, call, calls, run_bridge

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CAMPUS = app.state.campus
SOLIDS = CAMPUS["solids"]
WIDTH, HEIGHT = CAMPUS["width"], CAMPUS["height"]
HEDGE = next(solid for solid in SOLIDS if solid["id"] == "deck-hedge")
DIRECTIONS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def test_overlapping_a_walkable_solid_is_no_overlap_in_the_browser_either():
    walkable = {"x": 100, "y": 200, "w": 30, "h": 10, "walkable": True}
    solid = {"x": 100, "y": 200, "w": 30, "h": 10, "walkable": False}
    assert calls(["overlaps", 110, 205, walkable], ["overlaps", 110, 205, solid]) == [False, True]
    assert [movement.overlaps(110, 205, walkable), movement.overlaps(110, 205, solid)] == [False, True]


def test_a_walkable_solid_does_not_block_a_step_in_the_browser_either():
    walkable = [{"x": 100, "y": 0, "w": 6, "h": 200, "walkable": True}]
    assert call("step", 90, 50, 1, 0, 0.1, walkable, 300, 200) == {"x": 99, "y": 50}
    assert movement.step(90, 50, 1, 0, 0.1, walkable, 300, 200) == (99, 50)


def test_every_direction_from_inside_and_around_the_hedge_ends_where_the_server_ends():
    places = [
        (HEDGE["x"] + HEDGE["w"] / 2, HEDGE["y"] + HEDGE["h"] / 2),  # in the middle
        (595, 249),  # the hiding spot
        (595, HEDGE["y"] + HEDGE["h"] + 5),  # touching its bottom
        (595, HEDGE["y"] - 5),  # touching its top
        (HEDGE["x"] + 5, 249),  # inside, touching tree 3
        (HEDGE["x"] + HEDGE["w"] + 5, 249),  # touching its right side
    ]
    cases = [[x, y, dx, dy, seconds] for x, y in places for dx, dy in DIRECTIONS for seconds in (0.05, 0.1)]
    from_javascript = run_bridge(steps=cases)["steps"]
    for case, place in zip(cases, from_javascript):
        assert tuple(place) == movement.step(*case, SOLIDS, WIDTH, HEIGHT), case


def test_a_walk_up_through_the_hedge_is_the_same_step_by_step():
    x, y = 595.0, 290.0
    cases = []
    for _ in range(12):
        cases.append([x, y, 0, -1, 1 / 15])
        x, y = movement.step(x, y, 0, -1, 1 / 15, SOLIDS, WIDTH, HEIGHT)
    from_javascript = run_bridge(steps=cases)["steps"]
    assert [tuple(place) for place in from_javascript] == [
        movement.step(*case, SOLIDS, WIDTH, HEIGHT) for case in cases
    ]
    # The walk really went through the hedge.
    assert y < HEDGE["y"] - movement.PLAYER_HALF_SIZE
