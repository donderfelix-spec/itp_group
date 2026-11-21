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


@pytest.mark.parametrize("samples, median", [
    ([80], 80),
    ([80, 120], 100),  # an even count: the mean of the two middle ones
    ([400, 70, 90], 90),  # one sample during a hold-up does not count
    ([90, 30, 400, 70, 110], 90),
    ([100, 9, 20, 11], 15.5),  # sorted as numbers, not as text
])
def test_the_input_lag_is_the_median_start_delay_plus_the_wait_in_the_queue(samples, median):
    assert call("inputLag", samples, GLIDE, TICK) == pytest.approx(median + GLIDE - TICK)


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
        "tickMilliseconds": TICK,
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


def test_the_step_starts_at_the_end_of_the_glide_before_and_lasts_one_tick():
    # Not at `now`: so the pace is the same however late the frame is.
    for now in [10_000, 10_005, 10_033, 10_250]:
        step = next_step(now=now)
        assert step["startAt"] == 10_000
        assert step["endAt"] == pytest.approx(10_000 + TICK)


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
    assert next_step(history=pressed_late, inputLag=100) is not None
    assert next_step(history=[]) is None


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


def test_released_keys_do_not_end_a_bridge_that_is_under_way():
    # During a hold-up (a bridged step is waiting already) the character
    # walks on for one input lag after the release, like on the server.
    released = [{"time": 0, **RIGHT}, {"time": 9_950, **STANDING}]
    step = next_step(history=released, waitingSteps=1)
    assert step["x"] == pytest.approx(SPAWN[0] + STEP)
    # One input lag after the release it stands.
    assert next_step(history=released, waitingSteps=1, now=10_075, glideEndsAt=10_070) is None


def test_without_a_place_to_start_from_no_step_is_made():
    assert next_step(**{"from": None}) is None


# ---- When the server's position arrives ---------------------------------------------

WAITING = [{"x": 106, "y": 50}, {"x": 112, "y": 50}, {"x": 118, "y": 50}]


def test_differs_by_more_than_a_hair_on_an_axis():
    here = {"x": 10, "y": 20}
    results = calls(
        ["differs", here, {"x": 10, "y": 20}], ["differs", here, {"x": 10.04, "y": 19.96}],
        ["differs", here, {"x": 10.06, "y": 20}], ["differs", here, {"x": 10, "y": 19.94}],
    )
    assert results == [False, False, True, True]


def test_a_server_position_on_the_oldest_bridged_step_takes_its_place():
    result = call("takeServerPosition", WAITING, 106.04, 50)
    assert result == {"waiting": WAITING[1:], "distance": 0, "size": "none"}


def test_a_server_position_a_little_off_moves_the_steps_still_waiting():
    # The server walks 6.1 units per tick, the bridge 6.0.
    result = call("takeServerPosition", WAITING, 106.1, 50)
    assert result["size"] == "small"
    assert result["distance"] == pytest.approx(0.1)
    assert [(step["x"], step["y"]) for step in result["waiting"]] == [pytest.approx((112.1, 50)), pytest.approx((118.1, 50))]


def test_a_server_position_far_off_is_a_wrong_guess():
    # The server stood: its position is a whole step behind the bridge.
    result = call("takeServerPosition", WAITING, 100, 50)
    assert result["size"] == "large"
    assert result["distance"] == pytest.approx(6)
    assert [(step["x"], step["y"]) for step in result["waiting"]] == [(106, 50), (112, 50)]
    # The server went down instead of right.
    result = call("takeServerPosition", WAITING, 100, 56)
    assert result["distance"] == pytest.approx(math.hypot(6, 6))
    assert [(step["x"], step["y"]) for step in result["waiting"]] == [(106, 56), (112, 56)]


def test_small_and_large_are_divided_at_one_and_a_half_units_on_an_axis():
    results = calls(["takeServerPosition", WAITING, 107.5, 51.5], ["takeServerPosition", WAITING, 106, 48.49])
    assert [result["size"] for result in results] == ["small", "large"]


def test_the_last_waiting_step_leaves_nothing_waiting():
    assert call("takeServerPosition", WAITING[:1], 109, 50)["waiting"] == []


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
