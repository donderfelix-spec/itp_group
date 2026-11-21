"""The plain rules of "bridge the gaps" (M2-1.16), js/world/bridge.js.

While the server's positions are held up, the browser walks the own
character on by itself with the server's own movement rule. bridge.js holds
everything of that which is a plain function:

- `step`: a copy of `step()` in server/world/movement.py. The parity test
  below runs thousands of random steps on the real map through the Python
  and the JavaScript function and requires the same result.
- which direction a bridged step uses (the one the player held a moment
  ago), and how that moment is measured;
- whether a bridged step is made, and to where;
- what happens when the server's position arrives.

The real bridge.js runs in Node (tests/bridge_in_node.js). How world.js uses
these functions is tested in test_bridge_gaps.py. Without Node these tests
are skipped; CI has Node.
"""

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from server.main import TICKS_PER_SECOND, app
from server.world import movement
from bridge_helpers import OPEN_START

TESTS = Path(__file__).resolve().parent
BRIDGE_IN_NODE = TESTS / "bridge_in_node.js"
BRIDGE_JS = TESTS.parent / "client" / "js" / "world" / "bridge.js"
INDEX_HTML = TESTS.parent / "client" / "index.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CAMPUS = app.state.campus
SOLIDS = CAMPUS["solids"]
WIDTH = CAMPUS["width"]
HEIGHT = CAMPUS["height"]
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])

TICK = 1000 / TICKS_PER_SECOND  # ms
GLIDE = 110  # GLIDE_MILLISECONDS in world.js
STEP = 6  # map units in one tick at 90 units per second
DIRECTIONS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def run_bridge(calls=(), steps=()):
    finished = subprocess.run(
        [NODE, str(BRIDGE_IN_NODE)],
        input=json.dumps({"calls": list(calls), "steps": list(steps)}),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    result = json.loads(finished.stdout)
    assert result["changedArguments"] == [], "a plain function must leave its arguments as they were"
    return result


def call(name, *arguments):
    """The result of one function of Game.world.bridge."""
    return run_bridge(calls=[[name, *arguments]])["results"][0]


def calls(*several):
    return run_bridge(calls=several)["results"]


# ---- The page loads it --------------------------------------------------------


def test_index_html_loads_the_bridge_right_before_world_js():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert '<script src="js/world/bridge.js"></script>\n  <script src="js/world/world.js"></script>\n' in html


def test_the_javascript_rule_says_that_it_must_change_together_with_the_python_rule():
    text = BRIDGE_JS.read_text(encoding="utf-8")
    assert "server/world/movement.py" in text
    assert "CHANGE BOTH TOGETHER" in text


def test_the_numbers_of_the_rule_are_those_of_the_server():
    exported = run_bridge()["exported"]
    assert "step" in exported and "overlaps" in exported
    text = BRIDGE_JS.read_text(encoding="utf-8")
    assert f"var PLAYER_HALF_SIZE = {movement.PLAYER_HALF_SIZE};" in text
    assert f"var PLAYER_SPEED = {movement.PLAYER_SPEED};" in text
    assert f"var MAX_STEP_SECONDS = {movement.MAX_STEP_SECONDS};" in text


# ---- Parity of step() with the server's rule ------------------------------------


def random_cases(count, seed):
    """`count` steps [x, y, dx, dy, seconds] all over the real map, the same in every run.

    A fifth of them each: anywhere, touching a solid, overlapping a solid,
    within a step of a solid's edge, and at or beyond the edge of the map.
    All 9 directions, times from 0 to 0.15 s (the cap is 0.1 s).
    """
    rng = random.Random(seed)
    half = movement.PLAYER_HALF_SIZE
    cases = []
    for number in range(count):
        kind = number % 5
        solid = rng.choice(SOLIDS)
        if kind == 0:  # anywhere
            x, y = rng.uniform(half, WIDTH - half), rng.uniform(half, HEIGHT - half)
        elif kind == 1:  # touching one side of a solid exactly
            x = rng.choice([solid["x"] - half, solid["x"] + solid["w"] + half])
            y = rng.uniform(solid["y"] - half, solid["y"] + solid["h"] + half)
            if rng.random() < 0.5:
                x = rng.uniform(solid["x"] - half, solid["x"] + solid["w"] + half)
                y = rng.choice([solid["y"] - half, solid["y"] + solid["h"] + half])
        elif kind == 2:  # inside a solid
            x = rng.uniform(solid["x"] - half + 0.01, solid["x"] + solid["w"] + half - 0.01)
            y = rng.uniform(solid["y"] - half + 0.01, solid["y"] + solid["h"] + half - 0.01)
        elif kind == 3:  # within a step of a solid
            x = rng.uniform(solid["x"] - half - 10, solid["x"] + solid["w"] + half + 10)
            y = rng.uniform(solid["y"] - half - 10, solid["y"] + solid["h"] + half + 10)
        else:  # at the edge of the map, on it or a little beyond
            x = rng.choice([half, WIDTH - half, rng.uniform(-3, half + 9), rng.uniform(WIDTH - half - 9, WIDTH + 3)])
            y = rng.choice([half, HEIGHT - half, rng.uniform(-3, half + 9), rng.uniform(HEIGHT - half - 9, HEIGHT + 3)])
        dx, dy = DIRECTIONS[number % 9] if number < 900 else rng.choice(DIRECTIONS)
        seconds = rng.choice([0, 1 / 15, 0.1, 0.15, rng.uniform(0, 0.15), rng.uniform(0, 0.15)])
        cases.append([x, y, dx, dy, seconds])
    return cases


def test_step_gives_the_same_result_as_the_server_for_thousands_of_random_steps():
    cases = random_cases(3000, seed=20261121)
    from_javascript = run_bridge(steps=cases)["steps"]

    assert len(from_javascript) == len(cases)
    blocked = 0
    for case, (js_x, js_y) in zip(cases, from_javascript):
        x, y, dx, dy, seconds = case
        py_x, py_y = movement.step(x, y, dx, dy, seconds, SOLIDS, WIDTH, HEIGHT)
        assert js_x == pytest.approx(py_x, abs=1e-9), case
        assert js_y == pytest.approx(py_y, abs=1e-9), case
        # Not only to 1e-9: the same arithmetic in the same order gives the same number.
        assert (js_x, js_y) == (py_x, py_y), case
        free = movement.step(x, y, dx, dy, seconds, [], 10_000, 10_000)
        blocked += (py_x, py_y) != free
    # The cases really meet walls and edges: many steps end elsewhere than in the open.
    assert blocked > 400


def test_the_random_cases_cover_every_direction_and_kind():
    cases = random_cases(3000, seed=20261121)
    assert {(dx, dy) for _, _, dx, dy, _ in cases} == set(DIRECTIONS)
    overlapping = sum(1 for x, y, *_ in cases if any(movement.overlaps(x, y, solid) for solid in SOLIDS))
    assert overlapping > 500
    assert any(seconds > movement.MAX_STEP_SECONDS for *_, seconds in cases)
    assert any(seconds == 0 for *_, seconds in cases)


def test_a_walk_of_many_steps_stays_the_same_as_on_the_server():
    # Each step starts where the one before ended, as in a real walk: from
    # the spawn in a zigzag through the map, into walls and along them.
    rng = random.Random(7)
    x, y = SPAWN
    cases = []
    for number in range(600):
        if number % 12 == 0:
            dx, dy = rng.choice(DIRECTIONS)
        seconds = rng.uniform(0.060, 0.075)
        cases.append([x, y, dx, dy, seconds])
        x, y = movement.step(x, y, dx, dy, seconds, SOLIDS, WIDTH, HEIGHT)
    from_javascript = run_bridge(steps=cases)["steps"]
    for case, (js_x, js_y) in zip(cases, from_javascript):
        assert (js_x, js_y) == movement.step(*case, SOLIDS, WIDTH, HEIGHT), case


def test_overlaps_is_the_servers_rule_and_touching_is_not_overlapping():
    solid = {"x": 100, "y": 200, "w": 30, "h": 10}
    places = [(95, 205), (94.999, 205), (95.001, 205), (135, 205), (134.9, 205), (110, 195), (110, 195.01), (110, 215), (300, 300)]
    results = calls(*[["overlaps", x, y, solid] for x, y in places])
    assert results == [movement.overlaps(x, y, solid) for x, y in places]
    assert results[0] is False and results[2] is True


def test_step_refuses_a_position_that_is_no_number_like_the_server():
    result = call("step", None, 5, 1, 0, 0.1, [], 100, 100)
    assert "finite" in result["threw"]
    with pytest.raises(ValueError):
        movement.step(None, 5, 1, 0, 0.1, [], 100, 100)


def test_a_direction_or_time_that_is_no_number_moves_nothing_like_the_server():
    wrong = [["step", 50, 50, "1", "1", 0.1, [], 100, 100], ["step", 50, 50, 1, 1, "0.1", [], 100, 100],
             ["step", 50, 50, 1, 0, -1, [], 100, 100], ["step", 50, 50, 7, -0.5, 0.05, [], 100, 100]]
    results = calls(*wrong)
    for (_, *arguments), result in zip(wrong, results):
        assert (result["x"], result["y"]) == movement.step(*arguments)
    assert results[0] == {"x": 50, "y": 50}
    assert results[3]["x"] > 50 and results[3]["y"] < 50  # any positive number is 1, any negative -1


# ---- The direction the player held a moment ago -----------------------------------

RIGHT = {"dx": 1, "dy": 0}
DOWN = {"dx": 0, "dy": 1}
STANDING = {"dx": 0, "dy": 0}
HISTORY = [{"time": 1000, **RIGHT}, {"time": 1500, **DOWN}, {"time": 2000, **STANDING}]


def test_the_direction_of_an_empty_history_is_standing():
    assert call("directionAt", [], 5000) == STANDING


def test_the_direction_before_at_and_after_the_entries_of_a_history():
    results = calls(
        ["directionAt", HISTORY, 999.9],  # before the first entry: the player stood
        ["directionAt", HISTORY, 1000],  # exactly at an entry: that entry counts already
        ["directionAt", HISTORY, 1499.9],
        ["directionAt", HISTORY, 1500],
        ["directionAt", HISTORY, 1999],
        ["directionAt", HISTORY, 2000],
        ["directionAt", HISTORY, 99999],  # after the last
    )
    assert results == [STANDING, RIGHT, RIGHT, DOWN, DOWN, STANDING, STANDING]


def test_the_direction_after_the_last_entry_is_the_last_one_also_when_it_walks():
    assert call("directionAt", HISTORY[:2], 99999) == DOWN


def test_remember_direction_adds_an_entry_and_leaves_the_list_as_it_was():
    longer = call("rememberDirection", HISTORY, 2400, -1, 1)
    assert longer == HISTORY + [{"time": 2400, "dx": -1, "dy": 1}]


def test_old_directions_are_forgotten_but_never_the_one_that_was_current_then():
    # Asked 2 s back at most: the entry of 1000 was current until 1500,
    # which is older than 2 s before 4000, so it goes. The entry of 1500 was
    # current until 2000, exactly 2 s ago: it stays.
    kept = call("rememberDirection", HISTORY, 4000, 1, 0)
    assert [entry["time"] for entry in kept] == [1500, 2000, 4000]
    # Long after: only the direction that was current since then, and the new one.
    kept = call("rememberDirection", HISTORY, 60_000, 1, 0)
    assert [entry["time"] for entry in kept] == [2000, 60_000]
    assert call("directionAt", kept, 59_999) == STANDING


def test_a_history_never_grows_beyond_64_entries():
    history = []
    for number in range(200):  # a key every 5 ms: faster than any hand
        history = call("rememberDirection", history, 1000 + 5 * number, number % 2, 0)
    assert len(history) == 64
    assert history[-1]["time"] == 1000 + 5 * 199


def test_stood_between_with_an_empty_history_or_before_the_first_key():
    assert call("stoodBetween", [], 100, 200) is True
    assert call("stoodBetween", HISTORY, 500, 900) is True  # before the first entry the player stood
    assert call("stoodBetween", HISTORY, 900, 1200) is True  # stood at the beginning of the time asked for


def test_stood_between_finds_a_moment_without_keys_inside_the_time():
    # HISTORY: right from 1000, down from 1500, no key from 2000.
    stop_and_go = HISTORY + [{"time": 2030, **RIGHT}]
    results = calls(
        ["stoodBetween", stop_and_go, 1000, 1999.9],  # walking the whole time, with a turn
        ["stoodBetween", stop_and_go, 1000, 2000],  # the release at the very end counts
        ["stoodBetween", stop_and_go, 1990, 2100],  # the whole moment lies inside
        ["stoodBetween", stop_and_go, 2010, 2100],  # it began before and lasts into the time
        ["stoodBetween", stop_and_go, 2029.9, 2100],
        ["stoodBetween", stop_and_go, 2030, 2100],  # pressed again at the very beginning: walking
        ["stoodBetween", stop_and_go, 2040, 5000],
    )
    assert results == [False, True, True, True, True, False, False]


def test_stood_between_sees_a_moment_without_keys_of_no_length():
    # The opposite key and the release at the same instant.
    reversal = [{"time": 1000, **RIGHT}, {"time": 1500, **STANDING}, {"time": 1500, "dx": -1, "dy": 0}]
    assert call("stoodBetween", reversal, 1400, 1600) is True
    assert call("stoodBetween", reversal, 1500, 1600) is False
    assert call("stoodBetween", reversal, 1000, 1499) is False


def test_is_walking_at_looks_at_the_keys_now_and_one_input_lag_ago():
    walk = [{"time": 1000, **RIGHT}, {"time": 2000, **STANDING}]
    results = calls(
        ["isWalkingAt", walk, 900, 120],  # before the key
        ["isWalkingAt", walk, 1000, 120],  # the key itself: walking by the keys of now
        ["isWalkingAt", walk, 1999, 120],
        ["isWalkingAt", walk, 2000, 120],  # released, but the server still walks: the keys of 120 ms ago
        ["isWalkingAt", walk, 2119, 120],
        ["isWalkingAt", walk, 2120, 120],  # one input lag after the release: standing
        ["isWalkingAt", [], 2120, 120],
    )
    assert results == [False, True, True, True, True, False, False]


# ---- Measuring the input lag ------------------------------------------------------


def test_a_walk_from_standing_waits_for_its_first_position_from_the_key_on():
    # The last own position that moved came 400 ms before the key or earlier.
    assert call("walkStart", None, STANDING, RIGHT, 5000, 4600) == 5000
    assert call("walkStart", None, STANDING, RIGHT, 5000, 1000) == 5000


def test_a_walk_that_starts_while_the_server_still_moved_the_player_is_no_sample():
    # A position that moved arrived 399 ms before the key: the first
    # position after the key may still belong to the walk before.
    assert call("walkStart", None, STANDING, RIGHT, 5000, 4601) is None


def test_a_turn_keeps_the_key_that_started_the_walk():
    assert call("walkStart", 5000, RIGHT, DOWN, 5200, 1000) == 5000
    assert call("walkStart", None, RIGHT, DOWN, 5200, 1000) is None


def test_a_release_before_the_first_position_drops_the_sample():
    assert call("walkStart", 5000, RIGHT, STANDING, 5040, 1000) is None


def test_start_delays_are_clamped_to_30_and_400_ms():
    results = calls(
        ["rememberStartDelay", [], 5], ["rememberStartDelay", [], 30], ["rememberStartDelay", [], 87.5],
        ["rememberStartDelay", [], 400], ["rememberStartDelay", [], 2500], ["rememberStartDelay", [], -40],
    )
    assert results == [[30], [30], [87.5], [400], [400], [30]]


def test_only_the_last_five_start_delays_are_kept():
    samples = []
    for delay in [50, 60, 70, 80, 90, 100, 110]:
        samples = call("rememberStartDelay", samples, delay)
    assert samples == [70, 80, 90, 100, 110]


def test_before_a_sample_the_input_lag_is_100_ms_plus_the_wait_in_the_queue():
    assert call("inputLag", [], GLIDE, TICK) == pytest.approx(100 + GLIDE - TICK)


@pytest.mark.parametrize("samples, smallest", [
    ([80], 80),
    ([80, 120], 80),
    ([400, 70, 90], 70),  # a sample during a hold-up does not count
    ([400, 400, 400, 400, 62], 62),  # nor do four walks that started against a wall
    ([90, 30, 400, 70, 110], 30),
    ([100, 9, 20, 11], 9),  # compared as numbers, not as text
])
def test_the_input_lag_is_the_smallest_start_delay_plus_the_wait_in_the_queue(samples, smallest):
    # A sample can only be too long (the wait for the server's tick, a
    # hold-up, the time at a wall), so the smallest one is the best.
    assert call("inputLag", samples, GLIDE, TICK) == pytest.approx(smallest + GLIDE - TICK)


def test_a_long_sample_leaves_the_last_five_after_five_more_walks():
    samples = [400]
    for delay in [70, 75, 80, 85]:
        samples = call("rememberStartDelay", samples, delay)
    assert call("inputLag", samples, GLIDE, TICK) == pytest.approx(70 + GLIDE - TICK)
    # The connection got slower: after five walks the old short sample is gone.
    for delay in [150, 160, 155, 170, 165]:
        samples = call("rememberStartDelay", samples, delay)
    assert call("inputLag", samples, GLIDE, TICK) == pytest.approx(150 + GLIDE - TICK)


# ---- How long a tick of the server is ----------------------------------------------------

SECONDS = 6.1 / 90  # a tick of the deployed server: 6.1 map units per step
DIAGONAL = 6.1 / math.sqrt(2)  # what a diagonal step of that tick covers on each axis


def remember(samples, dx, dy):
    return call("rememberServerStep", samples, dx, dy, TICK)


def test_before_a_step_of_the_server_was_seen_its_tick_counts_as_a_fifteenth_of_a_second():
    assert call("stepSeconds", [], TICK) == pytest.approx(1 / 15)


@pytest.mark.parametrize("dx, dy", [(6.1, 0), (-6.1, 0), (0, 6.1), (0, -6.1)])
def test_a_straight_step_of_the_server_tells_how_long_its_tick_was(dx, dy):
    assert remember([], dx, dy) == [pytest.approx(SECONDS)]


@pytest.mark.parametrize("dx, dy", [(DIAGONAL, DIAGONAL), (-DIAGONAL, DIAGONAL), (DIAGONAL, -DIAGONAL)])
def test_a_diagonal_step_tells_the_same_time(dx, dy):
    assert remember([], dx, dy) == [pytest.approx(SECONDS)]


@pytest.mark.parametrize("dx, dy", [(0, DIAGONAL), (-DIAGONAL, 0), (1.8, DIAGONAL)])
def test_a_diagonal_step_that_slides_along_a_wall_tells_the_same_time(dx, dy):
    # One axis is stopped by the wall, fully or in part; the other moves as far as in the open.
    assert remember([], dx, dy) == [pytest.approx(SECONDS)]


@pytest.mark.parametrize("dx, dy", [(0.4, 0), (0, -4.2), (3, 3), (0.06, 0.06)])
def test_a_step_stopped_by_a_wall_tells_nothing(dx, dy):
    assert remember([SECONDS], dx, dy) == [SECONDS]
    assert remember([], dx, dy) == []


@pytest.mark.parametrize("dx, dy", [(12.2, 0), (0, -9.1), (8.63, 8.63 + 1), (-40, 3), (59, 59)])
def test_a_change_further_than_the_server_walks_in_one_step_tells_nothing(dx, dy):
    # Two steps in one message (the server skipped this browser for a
    # tick), or the server put the player somewhere.
    assert remember([SECONDS], dx, dy) == [SECONDS]
    assert call("isOneServerStep", dx, dy) is False


@pytest.mark.parametrize("dx, dy, one_step", [
    (6.1, 0, True), (0, -6.1, True), (DIAGONAL, DIAGONAL, True), (0.3, 0, True),
    (9, 0, True), (-9, 9, True),  # the longest step: 90 units per second for the cap of 0.1 s
    (9.2, 0, False), (0, 0, False), (0.04, -0.04, False),
])
def test_what_counts_as_one_step_of_the_server(dx, dy, one_step):
    assert call("isOneServerStep", dx, dy) is one_step


def test_two_kinds_of_step_are_read_wrongly_and_the_median_drops_them():
    # A straight step that a wall shortened to 5 units is read as a diagonal
    # (too long a time); a diagonal step of a tick of 100 ms is read as
    # straight (too short a time). Among ordinary steps neither changes the result.
    shortened = remember([], 5, 0)
    assert shortened == [pytest.approx(5 * math.sqrt(2) / 90)]
    slow_diagonal = remember([], 9 / math.sqrt(2), 9 / math.sqrt(2))
    assert slow_diagonal == [pytest.approx(9 / math.sqrt(2) / 90)]
    samples = [SECONDS, SECONDS, SECONDS] + shortened + slow_diagonal + [SECONDS, SECONDS]
    assert call("stepSeconds", samples, TICK) == pytest.approx(SECONDS)


def test_a_tick_of_exactly_a_fifteenth_of_a_second_is_read_right_on_both_kinds_of_step():
    assert remember([], 6, 0) == [pytest.approx(1 / 15)]
    assert remember([], 6 / math.sqrt(2), -6 / math.sqrt(2)) == [pytest.approx(1 / 15)]


def test_only_the_last_eight_steps_of_the_server_are_kept():
    samples = []
    for number in range(10):
        samples = remember(samples, 6 + number / 10, 0)
    assert samples == [pytest.approx((6 + number / 10) / 90) for number in range(2, 10)]


def test_the_time_of_a_step_is_the_median_of_the_servers_last_ticks():
    assert call("stepSeconds", [SECONDS], TICK) == pytest.approx(SECONDS)
    assert call("stepSeconds", [0.0678, 0.0683, 0.0675, 0.0678, 0.0689], TICK) == pytest.approx(0.0678)
    # One long tick (the server hung for a moment) does not count.
    assert call("stepSeconds", [0.0678, 0.0678, 0.1, 0.0678, 0.068], TICK) == pytest.approx(0.0678)


def test_the_time_of_a_step_is_never_shorter_than_a_tick_and_never_longer_than_the_servers_cap():
    assert call("stepSeconds", [0.05, 0.05, 0.05], TICK) == pytest.approx(1 / 15)
    assert call("stepSeconds", [0.3, 0.3, 0.3], TICK) == movement.MAX_STEP_SECONDS


# ---- Would a bridged step be made? ---------------------------------------------------

HELD_RIGHT = [{"time": 0, **RIGHT}]  # the key "right", held since long ago


def situation(**changes):
    """The own character walks right in the open; the glide of its last step ended 5 ms ago."""
    base = {
        "now": 10_005,
        "campus": "real",
        "switchedOff": False,
        "inputPaused": False,
        "queueLength": 0,
        "glideEndsAt": 10_000,
        "glideWasAStep": True,
        "from": {"x": SPAWN[0], "y": SPAWN[1]},
        "waitingSteps": 0,
        "history": HELD_RIGHT,
        "inputLag": 120,
        "stepSeconds": TICK / 1000,
    }
    base.update(changes)
    return base


def next_step(**changes):
    return call("nextStep", situation(**changes))


def against(dx, dy):
    """A place where the player touches a solid in the direction (dx, dy), reached from the spawn."""
    x, y = SPAWN
    for _ in range(400):
        after = movement.step(x, y, dx, dy, 1 / 15, SOLIDS, WIDTH, HEIGHT)
        if after == (x, y):
            return {"x": x, "y": y}
        x, y = after
    raise AssertionError("no solid in this direction")


def test_in_the_open_with_the_key_held_a_step_is_made():
    step = next_step()
    expected = movement.step(*SPAWN, 1, 0, 1 / 15, SOLIDS, WIDTH, HEIGHT)
    assert (step["x"], step["y"]) == pytest.approx(expected)
    assert step["x"] == pytest.approx(SPAWN[0] + STEP)
    assert (step["dx"], step["dy"]) == (1, 0)  # the direction it walked is kept with it


SERVER_TICK_SECONDS = 6.1 / 90  # a tick of the deployed server: 67.8 ms, 6.1 units per step


def test_the_step_is_as_long_as_the_servers_steps():
    step = next_step(stepSeconds=SERVER_TICK_SECONDS)
    assert step["x"] == pytest.approx(SPAWN[0] + 6.1)
    assert (step["x"], step["y"]) == movement.step(*SPAWN, 1, 0, SERVER_TICK_SECONDS, SOLIDS, WIDTH, HEIGHT)


def test_the_glide_of_a_step_lasts_as_long_as_the_server_takes_for_it():
    # Not one tick of the browser (66.7 ms): drawn faster than the server
    # walks, the character gained a whole step on it every few seconds.
    step = next_step(stepSeconds=SERVER_TICK_SECONDS, waitingSteps=1)
    assert step["endAt"] - step["startAt"] == pytest.approx(SERVER_TICK_SECONDS * 1000)
    way = step["x"] - SPAWN[0]
    assert way / ((step["endAt"] - step["startAt"]) / 1000) == pytest.approx(movement.PLAYER_SPEED)


def test_the_first_step_of_a_bridge_is_drawn_a_tenth_slower():
    # So a position that is only a little late arrives before the glide is
    # over, and the queue takes over again.
    first = next_step(stepSeconds=SERVER_TICK_SECONDS, waitingSteps=0)
    assert first["endAt"] - first["startAt"] == pytest.approx(1.1 * SERVER_TICK_SECONDS * 1000)
    assert first["x"] == pytest.approx(SPAWN[0] + 6.1)  # as far as every step
    for waiting in [1, 2, 9]:
        later = next_step(stepSeconds=SERVER_TICK_SECONDS, waitingSteps=waiting)
        assert later["endAt"] - later["startAt"] == pytest.approx(SERVER_TICK_SECONDS * 1000)


def test_the_step_starts_at_the_end_of_the_glide_before():
    # Not at `now`: so the pace is the same however late the frame is.
    for now in [10_000, 10_005, 10_033, 10_250]:
        step = next_step(now=now, waitingSteps=1)
        assert step["startAt"] == 10_000
        assert step["endAt"] == pytest.approx(10_000 + TICK)  # the server's tick of this situation


def test_no_step_while_the_map_is_not_loaded():
    assert next_step(campus=None) is None
    assert next_step(campus={"width": 680, "height": 668}) is None  # a map without solids is no map


def test_no_step_when_bridging_is_switched_off():
    assert next_step(switchedOff=True) is None


def test_no_step_while_the_input_is_paused():
    assert next_step(inputPaused=True) is None


def test_no_step_while_a_server_position_waits_in_the_queue():
    assert next_step(queueLength=1) is None


def test_no_step_while_the_glide_is_not_over():
    assert next_step(glideEndsAt=10_005.1) is None
    assert next_step(glideEndsAt=10_005) is not None  # over at this very instant


def test_no_step_when_the_glide_ended_more_than_250_ms_ago():
    # A hidden tab or a long pause never bridges.
    assert next_step(now=10_250) is not None
    assert next_step(now=10_250.1) is None
    assert next_step(now=60_000) is None


def test_no_step_when_the_glide_before_was_no_walking_step():
    # A bridge only ever continues a walk and never starts one.
    assert next_step(glideWasAStep=False) is None


def test_no_step_when_the_player_stood_one_input_lag_before():
    # The key is held now, but it was pressed only 100 ms before the step
    # would start: with a lag of 120 ms the server did not know it yet.
    pressed_late = [{"time": 9_900, **RIGHT}]
    assert next_step(history=pressed_late) is None
    assert next_step(history=[]) is None


# The situation of these tests: the step would start at 10 000, the input
# lag is 120 ms, so the direction is read from 9 880. One tick of the server
# is 66.7 ms there, and the bridge keeps a tick and a half (100 ms) away
# from a moment without keys: from 9 780 to 9 980.
READ_AT = 10_000 - 120
NEAR = 1.5 * TICK


def test_the_bridge_keeps_a_tick_and_a_half_away_from_a_moment_without_keys():
    assert NEAR == pytest.approx(100)
    assert "var NEAR_A_STANDSTILL_TICKS = 1.5;" in BRIDGE_JS.read_text(encoding="utf-8")


def test_no_step_when_the_key_was_pressed_less_than_a_tick_and_a_half_before_the_moment_read():
    # The walk began a moment before: the server may still have stood at
    # the tick whose position is missing.
    assert next_step(history=[{"time": READ_AT - NEAR + 0.1, **RIGHT}]) is None
    assert next_step(history=[{"time": READ_AT - NEAR, **RIGHT}]) is not None
    assert next_step(history=[{"time": READ_AT - NEAR + 0.1, **RIGHT}], waitingSteps=3) is None


@pytest.mark.parametrize("released_at, pressed_at, steps", [
    (9_600, 9_630, True),  # the moment without keys was over long before
    (READ_AT - NEAR - 30, READ_AT - NEAR, True),  # it ended exactly a tick and a half before
    (READ_AT - NEAR - 30, READ_AT - NEAR + 0.1, False),  # it lasts into that time
    (9_850, 9_880, False),  # around the moment the direction is read from
    (READ_AT + 5, READ_AT + 10, False),  # 5 ms without a key, right after it
    (READ_AT + NEAR, READ_AT + NEAR + 5, False),  # it begins exactly a tick and a half after
    (READ_AT + NEAR + 0.1, READ_AT + NEAR + 5, True),  # it begins later than that
])
def test_no_step_when_no_key_was_held_at_some_time_near_the_moment_read(released_at, pressed_at, steps):
    # A stop and go: right, no key, right again. If the server's tick fell
    # into the moment without a key, it sent no position for that tick, and
    # the position that is missing now may be that one.
    stop_and_go = [{"time": 0, **RIGHT}, {"time": released_at, **STANDING}, {"time": pressed_at, **RIGHT}]
    assert (next_step(history=stop_and_go) is not None) is steps
    # The same in the middle of a bridge.
    assert (next_step(history=stop_and_go, waitingSteps=2) is not None) is steps


def test_a_reversal_through_a_moment_without_keys_makes_no_step_in_either_direction():
    # Right, then the opposite key while the first is still down (no
    # direction), then left: neither the old nor the new direction is bridged.
    reversal = [{"time": 0, **RIGHT}, {"time": 9_870, **STANDING}, {"time": 9_875, "dx": -1, "dy": 0}]
    assert next_step(history=reversal) is None
    assert next_step(history=reversal, waitingSteps=1) is None
    # A turn without such a moment (both keys change at once) is bridged as before.
    turn = [{"time": 0, **RIGHT}, {"time": 9_870, **DOWN}]
    step = next_step(history=turn)
    assert (step["x"], step["y"]) == pytest.approx((SPAWN[0], SPAWN[1] + STEP))


def test_no_step_when_ten_steps_wait_for_the_server():
    assert next_step(waitingSteps=9) is not None
    assert next_step(waitingSteps=10) is None
    assert next_step(waitingSteps=11) is None


def test_no_step_against_a_wall():
    assert next_step(**{"from": against(1, 0)}) is None
    assert next_step(**{"from": against(0, 1)}, history=[{"time": 0, **DOWN}]) is None


def test_a_last_short_step_ends_touching_the_wall():
    wall = against(1, 0)
    step = next_step(**{"from": {"x": wall["x"] - 2.5, "y": wall["y"]}})
    assert (step["x"], step["y"]) == (wall["x"], wall["y"])


def test_a_diagonal_along_a_wall_slides_like_on_the_server():
    wall = against(1, 0)
    step = next_step(**{"from": wall}, history=[{"time": 0, "dx": 1, "dy": 1}])
    assert step["x"] == wall["x"]
    assert step["y"] == pytest.approx(wall["y"] + STEP / math.sqrt(2))
    assert (step["x"], step["y"]) == movement.step(wall["x"], wall["y"], 1, 1, TICK / 1000, SOLIDS, WIDTH, HEIGHT)


def test_the_step_uses_the_direction_of_one_input_lag_ago_not_the_keys_of_now():
    # The player turned from right to down 50 ms before the step starts.
    # The server learned of it later: this step still goes right.
    turned = [{"time": 0, **RIGHT}, {"time": 9_950, **DOWN}]
    step = next_step(history=turned)
    assert (step["x"], step["y"]) == pytest.approx((SPAWN[0] + STEP, SPAWN[1]))
    # 120 ms after the turn, the step goes down.
    step = next_step(history=turned, now=10_075, glideEndsAt=10_070)
    assert (step["x"], step["y"]) == pytest.approx((SPAWN[0], SPAWN[1] + STEP))


def test_released_keys_start_no_bridge():
    # An ordinary stop: the key was released 50 ms before the glide ended.
    # One input lag ago it was still held, but the server sends nothing
    # more after a stop, so nothing may be made up.
    released = [{"time": 0, **RIGHT}, {"time": 9_950, **STANDING}]
    assert next_step(history=released) is None
    # Released at the very moment the step would start counts as released.
    assert next_step(history=[{"time": 0, **RIGHT}, {"time": 10_000, **STANDING}]) is None
    assert next_step(history=[{"time": 0, **RIGHT}, {"time": 10_000.1, **STANDING}]) is not None


def test_a_bridge_that_is_under_way_goes_on_after_a_release_until_the_release_is_near_the_moment_read():
    # During a hold-up (a bridged step is waiting already) the server still
    # walks for a moment after the release. The bridge walks on as long as
    # the release lies more than a tick and a half after the moment the
    # direction is read from.
    released = [{"time": 0, **RIGHT}, {"time": READ_AT + NEAR + 0.1, **STANDING}]
    step = next_step(history=released, waitingSteps=1)
    assert step["x"] == pytest.approx(SPAWN[0] + STEP)
    # The next step (one tick later) reads from a moment nearer to the release: it is not made.
    assert next_step(history=released, waitingSteps=1, now=10_075, glideEndsAt=10_070) is None
    assert next_step(history=[{"time": 0, **RIGHT}, {"time": READ_AT + NEAR, **STANDING}], waitingSteps=1) is None


def test_without_a_place_to_start_from_no_step_is_made():
    assert next_step(**{"from": None}) is None


# ---- When the server's position arrives ---------------------------------------------

# Three bridged steps to the right in the open, waiting for the server. The
# own player walked from the left end of the map's longest open way.
OPEN = OPEN_START
WAITING = [{"x": OPEN[0] + STEP * number, "y": OPEN[1], "dx": 1, "dy": 0} for number in (1, 2, 3)]


def take(waiting, x, y):
    return call("takeServerPosition", waiting, x, y, "real campus", TICK / 1000)


def places(steps):
    return [(step["x"], step["y"]) for step in steps]


def test_differs_by_more_than_a_hair_on_an_axis():
    here = {"x": 10, "y": 20}
    results = calls(
        ["differs", here, {"x": 10, "y": 20}], ["differs", here, {"x": 10.04, "y": 19.96}],
        ["differs", here, {"x": 10.06, "y": 20}], ["differs", here, {"x": 10, "y": 19.94}],
    )
    assert results == [False, False, True, True]


def test_a_server_position_on_the_oldest_bridged_step_takes_its_place():
    result = take(WAITING, WAITING[0]["x"] + 0.04, OPEN[1])
    assert result == {"waiting": WAITING[1:], "distance": 0, "size": "none"}


def test_a_server_position_a_little_off_moves_the_steps_still_waiting_by_the_difference():
    # This tick of the server was a little longer than the others.
    result = take(WAITING, WAITING[0]["x"] + 0.1, OPEN[1])
    assert result["size"] == "small"
    assert result["distance"] == pytest.approx(0.1)
    assert places(result["waiting"]) == [pytest.approx((step["x"] + 0.1, OPEN[1])) for step in WAITING[1:]]
    # They keep the direction they walked.
    assert [(step["dx"], step["dy"]) for step in result["waiting"]] == [(1, 0), (1, 0)]


def test_a_server_position_far_off_is_a_wrong_guess():
    # The server stood: its position is a whole step behind the bridge.
    result = take(WAITING, OPEN[0], OPEN[1])
    assert result["size"] == "large"
    assert result["distance"] == pytest.approx(STEP)
    assert places(result["waiting"]) == [pytest.approx((step["x"] - STEP, OPEN[1])) for step in WAITING[1:]]
    # The server went up instead of right.
    result = take(WAITING, OPEN[0], OPEN[1] - STEP)
    assert result["distance"] == pytest.approx(math.hypot(STEP, STEP))
    assert places(result["waiting"]) == [pytest.approx((step["x"] - STEP, OPEN[1] - STEP)) for step in WAITING[1:]]


def test_small_and_large_are_divided_at_one_and_a_half_units_on_an_axis():
    first = WAITING[0]
    results = [take(WAITING, first["x"] + 1.5, OPEN[1] - 1.5), take(WAITING, first["x"], OPEN[1] - 1.51)]
    assert [result["size"] for result in results] == ["small", "large"]


def test_the_last_waiting_step_leaves_nothing_waiting():
    assert take(WAITING[:1], WAITING[0]["x"] + 3, OPEN[1])["waiting"] == []


def test_next_to_a_wall_the_waiting_steps_are_walked_again_and_never_put_inside_it():
    # Three bridged steps to the right; the last one ends touching a wall.
    # The server is a little further on than the first of them. Moved by
    # that difference, the last step would lie inside the wall, and a player
    # inside a solid is not stopped by it. Walked again with the rule, it
    # ends touching the wall.
    wall = against(1, 0)
    waiting = [{"x": wall["x"] - STEP * number, "y": wall["y"], "dx": 1, "dy": 0} for number in (2, 1, 0)]
    result = take(waiting, waiting[0]["x"] + 0.5, wall["y"])
    assert result["size"] == "small"
    assert places(result["waiting"]) == [pytest.approx((wall["x"] - STEP + 0.5, wall["y"])), (wall["x"], wall["y"])]
    for x, y in places(result["waiting"]):
        assert not any(movement.overlaps(x, y, solid) for solid in SOLIDS)


def test_a_waiting_step_that_no_longer_moves_is_dropped():
    # The server already touches the wall: it sends no position for the
    # steps into the wall, so nothing waits for them.
    wall = against(1, 0)
    waiting = [{"x": wall["x"] - 4, "y": wall["y"], "dx": 1, "dy": 0}, {"x": wall["x"], "y": wall["y"], "dx": 1, "dy": 0}]
    assert take(waiting, wall["x"], wall["y"])["waiting"] == []
    # A diagonal still slides along the wall, like on the server.
    waiting[1]["dy"] = 1
    slid = take(waiting, wall["x"], wall["y"])["waiting"]
    assert places(slid) == [movement.step(wall["x"], wall["y"], 1, 1, TICK / 1000, SOLIDS, WIDTH, HEIGHT)]


def test_a_correction_lasts_the_time_the_glide_had_left_but_at_least_50_ms():
    results = calls(
        ["correctionMilliseconds", 60, TICK], ["correctionMilliseconds", 50, TICK], ["correctionMilliseconds", 3, TICK],
        ["correctionMilliseconds", 0, TICK], ["correctionMilliseconds", -900, TICK],  # the glide was over: one tick
    )
    assert results == [60, 50, 50, pytest.approx(TICK), pytest.approx(TICK)]


def test_waiting_steps_are_taken_back_a_second_after_the_last_sign_of_life():
    assert calls(["takeBackAt", 5000, 4000], ["takeBackAt", 5000, 5300]) == [6000, 6300]


def test_the_memory_and_the_counts_start_empty():
    walk = run_bridge(calls=[["newWalk"]])["results"][0]
    assert walk["history"] == [] and walk["waiting"] == []
    assert walk["startedAt"] is None and walk["mayBeOffServer"] is False
    tally = call("newTally")
    assert tally == {"steps": 0, "milliseconds": 0, "replaced": 0, "corrections": 0, "largeCorrections": 0,
                     "largestCorrection": 0, "takenBack": 0}
