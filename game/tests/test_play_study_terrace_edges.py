"""Play test of M2-1.21: a player walks against the study terrace and a deck bush.

The study tables (S-148) are drawn on a wooden terrace in place of the
reflecting pool; the solid `deck-pool` (130 x 56 at 300, 262) did not move.
A square deck bush keeps its 28 x 28 solid. Here a real Chromium page in a
Duel holds a walk key against each of the four sides of both, at both ends
and in the middle of each side, and the server must stop the player exactly
where his 10 x 10 square touches the solid: no invisible wall in front of
it, and never on it.

The pages and the server are those of test_play_hiding.py (uvicorn in this
process, so a player can be put where a walk starts). Screenshots go to the
folder in TERRACE_SCREENSHOTS, if that is set.

Skipped when Node, Playwright or Chromium is missing.
"""

import os
import time
from pathlib import Path

import pytest

from server.world.movement import PLAYER_HALF_SIZE
from test_play_hiding import (  # noqa: F401  (server and quiet_tick are fixtures)
    SOLIDS,
    Browser,
    fresh_server_state,
    lobby_of,
    playwright_works,
    position,
    put,
    quiet_tick,
    server,
    standing_still,
    wait_until,
)

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

SCREENSHOTS = os.environ.get("TERRACE_SCREENSHOTS")
TERRACE = next(solid for solid in SOLIDS if solid["id"] == "deck-pool")
BUSH = next(solid for solid in SOLIDS if solid["id"] == "deck-tree-4")
# Where a walk starts: this far from the side, so a step of the tick cannot
# jump over the place where the player should stop.
START_GAP = 15
# Positions on the server are floats; touching is exact up to rounding.
EXACT = 0.01


def pushes(solid):
    """For each side, at both ends and in the middle: (name, start, key, axis, expected stop)."""
    left, top = solid["x"], solid["y"]
    right, bottom = left + solid["w"], top + solid["h"]
    # The lanes whose square overlaps the side by just one unit at each end
    # (a corner), and the middle of the side.
    rows = [top - PLAYER_HALF_SIZE + 1, (top + bottom) / 2, bottom + PLAYER_HALF_SIZE - 1]
    columns = [left - PLAYER_HALF_SIZE + 1, (left + right) / 2, right + PLAYER_HALF_SIZE - 1]
    found = []
    for where, y in zip(("top end", "middle", "bottom end"), rows):
        found.append((f"west side, {where}", (left - PLAYER_HALF_SIZE - START_GAP, y), "KeyD", 0, left - PLAYER_HALF_SIZE))
        found.append((f"east side, {where}", (right + PLAYER_HALF_SIZE + START_GAP, y), "KeyA", 0, right + PLAYER_HALF_SIZE))
    for where, x in zip(("left end", "middle", "right end"), columns):
        found.append((f"north side, {where}", (x, top - PLAYER_HALF_SIZE - START_GAP), "KeyS", 1, top - PLAYER_HALF_SIZE))
        found.append((f"south side, {where}", (x, bottom + PLAYER_HALF_SIZE + START_GAP), "KeyW", 1, bottom + PLAYER_HALF_SIZE))
    return found


def push(browser, label, name, start, key):
    """Put the player at `start`, hold `key` until he stands still, and return where he stopped."""
    put(name, start)
    standing_still(name)
    browser.call("down", label=label, key=key)
    try:
        # 15 units at 90 per second take about 0.17 s; then he must be stopped.
        time.sleep(0.35)
        stopped = standing_still(name, 0.3)
    finally:
        browser.call("up", label=label, key=key)
    return stopped


def shot(browser, label, file_name):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        browser.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{file_name}.png"))


@pytest.fixture(scope="module")
def walked(server):
    fresh_server_state()
    browser = Browser(server[0])
    seen = {"stops": {}, "errors": []}
    try:
        for label in ("W0", "W1"):
            browser.open(label)
        names = browser.names
        browser.call("click", label="W0", selector="#home-create")
        browser.wait("W0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        code = browser.js("W0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        browser.call("fill", label="W1", selector="#join-code", text=code)
        browser.call("click", label="W1", selector="#join-submit")
        browser.wait("W1", "!document.getElementById('screen-lobby').hidden")
        browser.call("click", label="W0", selector='#lobby-modes button:has-text("Duel")')
        wait_until(lambda: lobby_of(names["W0"]).mode == "duel", "Duel chosen")
        browser.call("click", label="W0", selector="#lobby-start")
        for label in ("W0", "W1"):
            browser.wait(label, "window.__received.some((r) => r.m.type === 'duel_state')")
            browser.js(label, "document.activeElement && document.activeElement.blur()")
        wait_until(lambda: lobby_of(names["W0"]).duel is not None, "the Duel")
        # The other player waits far away, so he never stands in the way.
        put(names["W1"], (486, 600))
        for solid in (TERRACE, BUSH):
            for side, start, key, axis, expected in pushes(solid):
                stopped = push(browser, "W0", names["W0"], start, key)
                seen["stops"][(solid["id"], side)] = {"start": start, "stopped": stopped, "axis": axis, "expected": expected}
                if "middle" in side:
                    shot(browser, "W0", f"{solid['id']}_{side.split(',')[0].replace(' ', '_')}")
        seen["errors"] = browser.messages("W0", "error")
    finally:
        seen["console"] = browser.close()
    return seen


def test_the_terrace_and_the_bush_are_mains_solids():
    assert (TERRACE["kind"], TERRACE["x"], TERRACE["y"], TERRACE["w"], TERRACE["h"]) == ("pool", 300, 262, 130, 56)
    assert (BUSH["kind"], BUSH["x"], BUSH["y"], BUSH["w"], BUSH["h"]) == ("tree", 528, 330, 28, 28)


def test_every_push_has_a_start_off_the_solid_and_a_lane_across_it():
    for solid in (TERRACE, BUSH):
        for _, (x, y), _, axis, _ in pushes(solid):
            assert not (solid["x"] - PLAYER_HALF_SIZE < x < solid["x"] + solid["w"] + PLAYER_HALF_SIZE
                        and solid["y"] - PLAYER_HALF_SIZE < y < solid["y"] + solid["h"] + PLAYER_HALF_SIZE)
            lane = y if axis == 0 else x
            low, high = (solid["y"], solid["y"] + solid["h"]) if axis == 0 else (solid["x"], solid["x"] + solid["w"])
            assert low - PLAYER_HALF_SIZE < lane < high + PLAYER_HALF_SIZE


@pytest.mark.parametrize("solid_id", ["deck-pool", "deck-tree-4"])
def test_the_player_stops_exactly_where_his_square_touches_each_side(walked, solid_id):
    wrong = {
        side: record for (found_id, side), record in walked["stops"].items()
        if found_id == solid_id and abs(record["stopped"][record["axis"]] - record["expected"]) > EXACT
    }
    assert wrong == {}
    assert len([key for key in walked["stops"] if key[0] == solid_id]) == 12


@pytest.mark.parametrize("solid_id", ["deck-pool", "deck-tree-4"])
def test_the_player_never_moves_sideways_while_pushing(walked, solid_id):
    for (found_id, _), record in walked["stops"].items():
        if found_id == solid_id:
            other = 1 - record["axis"]
            assert abs(record["stopped"][other] - record["start"][other]) <= EXACT


def test_no_error_message_and_no_console_problem(walked):
    assert walked["errors"] == []
    assert walked["console"] == []
