"""Tests of the walking diagnostic, js/world/diagnostic.js (M2-1.15).

The diagnostic only runs with `?debug` in the address of the page. It
measures how `positions` messages arrive, the round trip of a `hello` probe,
the frames and how smoothly the own character is drawn, and shows the
numbers in a panel with Copy, Reset and Hide.

The real diagnostic.js runs in Node (tests/diagnostic_in_node.js) with
stand-ins for the window, the document, Game.net and Game.world:

- without `?debug` it must register, send, start and create nothing;
- its pure helper functions are called directly with lists and times;
- with `?debug` a test plays frames, messages, timers and clicks.

How net.js treats the answer `welcome` is tested with the page's own
net.js, forms.js and main.js in tests/page_in_node.js. The diagnostic on top
of the real world.js is tested in test_walking_diagnostic_world.py.

Without Node these tests are skipped; CI has Node.
"""

import json
import random
import shutil
import statistics
import subprocess
from pathlib import Path

import pytest

from server import protocol

TESTS = Path(__file__).resolve().parent
DIAGNOSTIC_IN_NODE = TESTS / "diagnostic_in_node.js"
PAGE_IN_NODE = TESTS / "page_in_node.js"
INDEX_HTML = TESTS.parent / "client" / "index.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

FRAME_MS = 16
WALKING_SPEED = 90  # map units per second on the server
OWN_NAME = "Ana"
STOPPED_FOR_MS = 200  # as in diagnostic.js
WALL_NOTE = "Walk in the open: pressing against a wall counts as a gap and a stall."
# How many entries the diagnostic keeps of each kind: about three minutes.
MOST_FRAMES = 10800
MOST_MESSAGES = 2700
MOST_ROUND_TRIPS = 180


def hello(number):
    """The probe with this number: every probe has its own name."""
    return {"type": "hello", "name": f"debug{number}"}


def welcome(number):
    """The server's answer to the probe with this number."""
    return {"type": "welcome", "name": f"debug{number}", "protocol": protocol.PROTOCOL_VERSION}


def run_diagnostic(search="", calls=(), steps=(), clipboard="works"):
    finished = subprocess.run(
        [NODE, str(DIAGNOSTIC_IN_NODE)],
        input=json.dumps({"search": search, "calls": list(calls), "steps": list(steps), "clipboard": clipboard}),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(finished.stdout)


def call(name, *arguments):
    """The result of one pure function of Game.diagnostic."""
    return run_diagnostic(calls=[[name, *arguments]])["results"][0]


def frame(time, x, walking_since=0, y=0):
    return {"time": time, "x": x, "y": y, "walkingSince": walking_since}


def walking_frames(start=0, end=1000, walking_since=0, x_at_start=0.0):
    """A frame every 16 ms while the character is drawn at 90 units per second."""
    return [
        frame(time, x_at_start + WALKING_SPEED * (time - start) / 1000, walking_since)
        for time in range(start, end + 1, FRAME_MS)
    ]


def freeze(frames, first, count):
    """The frames first .. first+count-1 are drawn where the frame before them was."""
    for index in range(first, first + count):
        frames[index]["x"] = frames[first - 1]["x"]
    return frames


# ---- Without ?debug: nothing at all ------------------------------------------------


@pytest.mark.parametrize("search", ["", "?debugger", "?x=1", "?code=ABCD"])
def test_without_debug_nothing_is_registered_sent_started_or_created(search):
    result = run_diagnostic(search=search)
    record = result["record"]
    assert result["active"] is False
    assert record["handlers"] == []
    assert record["sent"] == []
    assert record["created"] == []
    assert record["frameRequests"] == 0
    assert record["intervals"] == []
    assert record["timeouts"] == 0
    assert record["listeners"] == []
    assert result["bodyChildren"] == 0


def test_with_debug_the_only_listeners_are_the_ones_intended():
    # No key listener, nothing on the window: the walking keys belong to
    # world.js. Only the tab's visibility, and a click on each button.
    steps = [["frame", 0], ["direction", 1, 0], ["frame", 16], ["tick", 500], ["tick", 1000], ["click", "Copy"]]
    for clipboard in ["works", "missing"]:  # "missing": the copy goes through a hidden textarea
        record = run_diagnostic(search="?debug", steps=steps, clipboard=clipboard)["record"]
        assert record["listeners"] == ["document:visibilitychange"]
        assert record["elementListeners"] == ["BUTTON:click"] * 3


def test_without_debug_only_the_pure_helpers_are_there():
    exported = run_diagnostic()["exported"]
    for helper in ["median", "percentile", "histogram", "walkingGaps", "stallsOf", "startDelays", "stops"]:
        assert helper in exported
    for active_only in ["report", "numbers", "reset"]:
        assert active_only not in exported


@pytest.mark.parametrize("search", ["?debug", "?debug=1", "?x=1&debug", "?debug="])
def test_the_parameter_debug_switches_it_on(search):
    result = run_diagnostic(search=search)
    assert result["active"] is True
    assert result["bodyChildren"] == 1


def test_is_debug_address():
    results = run_diagnostic(
        calls=[["isDebugAddress", ""], ["isDebugAddress", "?debug"], ["isDebugAddress", "?nodebug=1"]]
    )["results"]
    assert results == [False, True, False]


def test_index_html_loads_the_diagnostic_right_after_world_js():
    html = INDEX_HTML.read_text(encoding="utf-8")
    world = '<script src="js/world/world.js"></script>\n'
    assert world + '  <script src="js/world/diagnostic.js"></script>\n' in html


# ---- Pure helpers: median, percentile, maximum ------------------------------------


def test_median():
    results = run_diagnostic(
        calls=[["median", []], ["median", [5]], ["median", [3, 1, 2]], ["median", [4, 1, 3, 2]]]
    )["results"]
    assert results == [None, 5, 2, 2.5]


def test_percentile_of_small_lists():
    results = run_diagnostic(
        calls=[
            ["percentile", [], 95],
            ["percentile", [7], 95],
            ["percentile", [7], 5],
            ["percentile", [3, 1, 2], 95],
            ["percentile", [3, 1, 2], 5],
            ["percentile", [1, 2], 50],
            ["percentile", [5, 9], 0],
        ]
    )["results"]
    assert results == [None, 7, 7, 3, 1, 1, 5]


def test_percentile_of_twenty_values():
    values = list(range(20, 0, -1))  # 20 .. 1, not sorted
    results = run_diagnostic(
        calls=[["percentile", values, 95], ["percentile", values, 50], ["percentile", values, 100]]
    )["results"]
    assert results == [19, 10, 20]


def test_maximum():
    results = run_diagnostic(calls=[["maximum", []], ["maximum", [-3]], ["maximum", [2, 9, 4]]])["results"]
    assert results == [None, -3, 9]


def test_the_input_lists_are_not_reordered():
    # The median and the percentiles are picked out of a copy. The node
    # script compares the arguments before and after each call, because
    # this test only ever sees copies of them.
    unsorted = [5, 3, 9, 1, 4, 8, 2, 7, 6, 0]
    recording = {
        "startedAt": 0,
        "tabWasHidden": False,
        "frames": [frame(time, x, walking_since=-1000) for time, x in zip([0, 30, 40, 90, 100, 190], [0, 9, 3, 7, 1, 5])],
        "messages": [],
        "roundTrips": unsorted,
        "lostProbes": 0,
    }
    result = run_diagnostic(
        calls=[
            ["median", unsorted],
            ["percentile", unsorted, 95],
            ["percentile", unsorted, 5],
            ["maximum", unsorted],
            ["histogram", unsorted],
            ["summarize", recording, 200],
        ]
    )
    assert result["results"][:4] == [4.5, 9, 0, 9]
    assert result["results"][5]["roundTrip"]["median"] == 4.5
    assert result["changedArguments"] == []


def nearest_rank(values, percent):
    ordered = sorted(values)
    return ordered[max(0, -(-percent * len(ordered) // 100) - 1)]


def test_median_and_percentiles_are_those_of_the_sorted_list():
    # They are picked out without sorting (valueAtRank in diagnostic.js):
    # lists of every length, with many equal values, sorted and reversed.
    randomness = random.Random(2026)
    lists = [[randomness.randint(0, 20) for _ in range(length)] for length in range(1, 60)]
    lists += [[randomness.random() * 100 for _ in range(length)] for length in (100, 999, 1000)]
    lists += [list(range(50)), list(range(50, 0, -1)), [7] * 40]
    calls = []
    for values in lists:
        calls += [["median", values], ["percentile", values, 5], ["percentile", values, 95], ["percentile", values, 100]]
    results = run_diagnostic(calls=calls)["results"]
    for number, values in enumerate(lists):
        median, p5, p95, p100 = results[4 * number : 4 * number + 4]
        assert median == pytest.approx(statistics.median(values))
        assert p5 == nearest_rank(values, 5)
        assert p95 == nearest_rank(values, 95)
        assert p100 == max(values)


# ---- Pure helpers: histogram ---------------------------------------------------------

LABELS = ["<20", "20–50", "50–90", "90–130", "130–200", "200–300", "300–500", "≥500"]


def test_histogram_bucket_borders():
    # Each border belongs to the bucket above it: 20 is in 20–50, 500 in ≥500.
    values = [0, 19.99, 20, 49.9, 50, 89.9, 90, 129.9, 130, 199.9, 200, 299.9, 300, 499.9, 500, 10000]
    buckets = call("histogram", values)
    assert [bucket["label"] for bucket in buckets] == LABELS
    assert [bucket["count"] for bucket in buckets] == [2] * 8


def test_histogram_of_nothing():
    assert [bucket["count"] for bucket in call("histogram", [])] == [0] * 8


def test_histogram_of_one_gap_on_time():
    assert [bucket["count"] for bucket in call("histogram", [67])] == [0, 0, 1, 0, 0, 0, 0, 0]


# ---- Pure helpers: gaps between messages ---------------------------------------------


def message(time, walking_since):
    return {"time": time, "walkingSince": walking_since}


def test_walking_gaps_of_nothing_and_of_one_message():
    results = run_diagnostic(calls=[["walkingGaps", []], ["walkingGaps", [message(5, 0)]]])["results"]
    assert results == [[], []]


def test_gaps_while_standing_do_not_count():
    assert call("walkingGaps", [message(0, None), message(500, None), message(3000, None)]) == []


def test_a_gap_counts_only_inside_one_walk():
    messages = [
        message(0, 0),
        message(67, 0),  # walking: counts
        message(400, None),  # stood: the gap to it does not count
        message(500, 450),  # a new walk: the gap from standing does not count
        message(567, 450),  # counts
        message(800, 700),  # walked again after a stop in between: does not count
    ]
    assert call("walkingGaps", messages) == [{"at": 67, "gap": 67}, {"at": 567, "gap": 67}]


def test_a_gap_from_standing_into_a_walk_does_not_count():
    assert call("walkingGaps", [message(0, None), message(67, 30)]) == []


def test_messages_per_second():
    results = run_diagnostic(
        calls=[["messagesPerSecond", []], ["messagesPerSecond", [100, 100]], ["messagesPerSecond", [0]]]
    )["results"]
    assert results == [None, 10, None]


def test_own_steps():
    messages = [
        {"own": {"x": 0, "y": 0}},
        {"own": None},  # the own player was not in this message
        {"own": {"x": 6, "y": 0}},  # a step of 6
        {"own": {"x": 6, "y": 0}},  # stood: not a step
        {"own": {"x": 6, "y": 0.5}},  # exactly 0.5: too small to count
        {"own": {"x": 6, "y": 100}},  # the server put the player somewhere: not a step
        {"own": {"x": 9, "y": 104}},  # a step of 5
    ]
    assert call("ownSteps", messages) == [6, 5]
    assert call("ownSteps", []) == []


def test_own_position_in_a_message():
    players = {"players": [{"name": "Bo", "x": 1, "y": 2}, {"name": OWN_NAME, "x": 3, "y": 4}]}
    results = run_diagnostic(
        calls=[
            ["ownPositionIn", players, OWN_NAME],
            ["ownPositionIn", players, "Cy"],
            ["ownPositionIn", players, None],
            ["ownPositionIn", {"players": [{"name": OWN_NAME, "x": "3", "y": 4}]}, OWN_NAME],
            ["ownPositionIn", {}, OWN_NAME],
        ]
    )["results"]
    assert results == [{"x": 3, "y": 4}, None, None, None, None]


def test_walking_since_of_a_direction():
    results = run_diagnostic(
        calls=[
            ["walkingSinceOf", {"dx": 0, "dy": 0, "since": None}],
            ["walkingSinceOf", {"dx": 1, "dy": 0, "since": 5}],
            ["walkingSinceOf", {"dx": 0, "dy": -1, "since": 5.5}],
            ["walkingSinceOf", {"dx": 1, "dy": 1, "since": 0}],  # a walk that began at time 0
            ["walkingSinceOf", {"dx": 0, "dy": 0, "since": 5}],  # standing never has a since
            ["walkingSinceOf", {"dx": 1, "dy": 0}],  # a world that does not tell
            ["walkingSinceOf", None],  # no world at all
        ]
    )["results"]
    assert results == [None, 5, 5.5, 0, None, None, None]


def test_a_zero_shorter_than_the_time_between_two_messages_ends_the_walk():
    # Released and pressed again between the messages at 67 and 134: both
    # times the player walks, but not in the same walk.
    messages = [message(0, 0), message(67, 0), message(134, 100.5), message(201, 100.5)]
    assert call("walkingGaps", messages) == [{"at": 67, "gap": 67}, {"at": 201, "gap": 67}]


# ---- Pure helpers: frozen frames and stalls ----------------------------------------------


def test_stalls_of_nothing_and_of_one_frame():
    empty = {"walkingFrames": 0, "frozenFrames": 0, "walkingMs": 0, "stalls": []}
    results = run_diagnostic(calls=[["stallsOf", []], ["stallsOf", [frame(500, 1)]]])["results"]
    assert results == [empty, empty]


def test_smooth_walking_has_no_frozen_frames():
    found = call("stallsOf", walking_frames(end=1000))
    # Judged are the frames from 400 ms on: 400, 416, ... 992.
    assert found["walkingFrames"] == len(range(400, 1001, FRAME_MS))
    assert found["frozenFrames"] == 0
    assert found["stalls"] == []
    assert found["walkingMs"] == FRAME_MS * found["walkingFrames"]


def test_a_stall_of_exactly_two_frames():
    frames = freeze(walking_frames(end=1000), first=32, count=2)  # frames at 512 and 528
    found = call("stallsOf", frames)
    assert found["frozenFrames"] == 2
    # From the last frame that moved (496) to the first that moves again (544).
    assert found["stalls"] == [{"at": 496, "length": 48}]


def test_one_frozen_frame_is_no_stall():
    found = call("stallsOf", freeze(walking_frames(end=1000), first=32, count=1))
    assert found["frozenFrames"] == 1
    assert found["stalls"] == []


def test_a_long_stall():
    found = call("stallsOf", freeze(walking_frames(end=1500), first=40, count=20))  # 640 .. 944
    assert found["frozenFrames"] == 20
    assert found["stalls"] == [{"at": 624, "length": 960 - 624}]


def test_a_frozen_run_in_the_first_400_ms_of_a_walk_is_not_counted():
    frames = freeze(walking_frames(end=1000), first=10, count=8)  # 160 .. 272: the normal start delay
    found = call("stallsOf", frames)
    assert found["frozenFrames"] == 0
    assert found["stalls"] == []


def test_a_frozen_run_that_lasts_past_400_ms_counts_from_400_ms_on():
    frames = freeze(walking_frames(end=1000), first=20, count=10)  # 320 .. 464
    found = call("stallsOf", frames)
    assert found["frozenFrames"] == len(range(400, 465, FRAME_MS))
    assert found["stalls"] == [{"at": 304, "length": 480 - 304}]


def test_a_frozen_run_that_ends_with_the_key_released_is_no_stall():
    # Walking against a wall, then letting go: frozen frames, but no stall.
    frames = freeze(walking_frames(end=1000), first=40, count=23)  # 640 .. 992
    frames.append(frame(1008, frames[-1]["x"], walking_since=None))
    found = call("stallsOf", frames)
    assert found["frozenFrames"] == 23
    assert found["stalls"] == []


def test_frames_without_a_position_are_not_judged():
    frames = [frame(time, None) for time in range(0, 1001, FRAME_MS)]
    found = call("stallsOf", frames)
    assert found["walkingFrames"] == 0
    assert found["frozenFrames"] == 0


def test_frames_while_standing_are_not_judged():
    frames = [frame(time, 5, walking_since=None) for time in range(0, 1001, FRAME_MS)]
    assert call("stallsOf", frames)["walkingFrames"] == 0


# ---- Pure helpers: speed, start and stop ------------------------------------------------


def test_drawn_speed_of_smooth_walking_is_the_server_speed():
    speeds = call("drawnSpeeds", walking_frames(end=1000))
    assert len(speeds) == len(range(400, 1001, FRAME_MS))
    assert all(speed == pytest.approx(WALKING_SPEED) for speed in speeds)


def test_drawn_speed_skips_the_start_and_frames_of_no_time():
    frames = [frame(0, 0), frame(100, 9), frame(500, 45), frame(500, 46), frame(516, 47.44)]
    assert call("drawnSpeeds", frames) == [pytest.approx(90), pytest.approx(90)]
    assert call("drawnSpeeds", []) == []


def test_uneven_percent():
    results = run_diagnostic(
        calls=[["unevenPercent", []], ["unevenPercent", [90, 30, 200, 90]], ["unevenPercent", [45, 135]]]
    )["results"]
    # 45 and 135 themselves are not uneven.
    assert results == [None, 50, 0]


def standing_frames(start, end, x=0.0):
    """A frame every 16 ms from `start` to before `end`: no key held, the character stands at x."""
    return [frame(time, x, walking_since=None) for time in range(start, end, FRAME_MS)]


def test_start_delay():
    standing = standing_frames(0, 300)  # 0 .. 288
    # The key comes at 300, between two frames; the character still stands.
    walking = [frame(time, 0, walking_since=300) for time in range(304, 452, FRAME_MS)]
    # The first frame that moves is the one at 464.
    moving = walking_frames(start=464, end=800, walking_since=300, x_at_start=1.44)
    assert call("startDelays", standing + walking + moving) == [464 - 300]


def test_no_start_delay_for_a_walk_that_never_moved():
    standing = standing_frames(0, 300)
    walking = [frame(time, 0, walking_since=300) for time in range(304, 500, FRAME_MS)]
    stopped = standing_frames(512, 800)
    assert call("startDelays", standing + walking + stopped) == []
    assert call("startDelays", []) == []


def frames_of_a_release_and_a_new_key(key_after_ms, glides_on_ms):
    """The player walks, lets go at 1000 and presses again `key_after_ms` later.

    After the release the character glides on for `glides_on_ms` (the queue
    still plays), then stands. After the new key it stands for 160 ms more
    (the server's answer is on its way) and then walks.
    Returns the frames, the time of the new key and of the first frame that moves after it.
    """
    frames = walking_frames(end=992)
    x = frames[-1]["x"]
    key_at = 1000 + key_after_ms
    moves_again_at = key_at + 160
    for time in range(1008, moves_again_at + 400, FRAME_MS):
        gliding_out = time <= 1000 + glides_on_ms
        walking_again = time >= moves_again_at
        if gliding_out or walking_again:
            x += 1.44
        frames.append(frame(time, x, walking_since=key_at if time >= key_at else None))
    first_moved = next(time for time in range(1008, moves_again_at + 400, FRAME_MS) if time >= moves_again_at)
    return frames, key_at, first_moved


def test_a_key_120_ms_after_a_release_is_no_start():
    # A quick turn: the character had not stood for 200 ms before the key.
    frames, _, _ = frames_of_a_release_and_a_new_key(key_after_ms=120, glides_on_ms=0)
    assert call("startDelays", frames) == []


def test_a_key_while_the_character_still_glides_out_of_the_walk_before_is_no_start():
    # It moves in the frame right after the key, long before the server
    # can have answered: counted, that would read as a start delay of one frame.
    frames, _, _ = frames_of_a_release_and_a_new_key(key_after_ms=120, glides_on_ms=150)
    assert call("startDelays", frames) == []


def test_a_key_600_ms_after_a_release_is_a_start():
    frames, key_at, first_moved = frames_of_a_release_and_a_new_key(key_after_ms=600, glides_on_ms=150)
    assert call("startDelays", frames) == [first_moved - key_at]
    assert first_moved - key_at >= 160


@pytest.mark.parametrize("stood_ms, counted", [(STOPPED_FOR_MS - 1, False), (STOPPED_FOR_MS, True)])
def test_a_start_counts_when_the_character_stood_for_200_ms_before_the_key(stood_ms, counted):
    walking = walking_frames(end=992)
    x = walking[-1]["x"]
    key_at = 992 + stood_ms  # the frame at 992 is the last one that moved
    standing = [frame(time, x, walking_since=None) for time in range(1008, key_at, FRAME_MS)]
    waiting = [frame(time, x, walking_since=key_at) for time in range(1008 + FRAME_MS * len(standing), 1400, FRAME_MS)]
    moving = walking_frames(start=1400, end=1600, walking_since=key_at, x_at_start=x + 1.44)
    assert call("startDelays", walking + standing + waiting + moving) == ([1400 - key_at] if counted else [])


def test_a_walk_at_the_very_beginning_of_the_recording_is_no_start():
    # Nobody knows whether the character stood before the first frame.
    standing = standing_frames(0, 100)
    walking = [frame(time, 0, walking_since=100) for time in range(112, 260, FRAME_MS)]
    moving = walking_frames(start=272, end=600, walking_since=100, x_at_start=1.44)
    assert call("startDelays", standing + walking + moving) == []


def test_a_zero_shorter_than_a_frame_while_walking_starts_a_new_walk_but_is_no_start():
    # Released and the opposite key pressed between the frames at 992 and
    # 1008: no frame saw the direction (0, 0), but `since` changed.
    first = walking_frames(end=992, walking_since=0)
    second = walking_frames(start=1008, end=2000, walking_since=1000.5, x_at_start=first[-1]["x"] + 1.44)
    frames = first + second
    found = call("stallsOf", frames)
    # Judged: 400 .. 992 of the first walk, and the second from 400 ms after its key.
    assert found["walkingFrames"] == len(range(400, 993, FRAME_MS)) + len(range(1408, 2001, FRAME_MS))
    assert len(call("drawnSpeeds", frames)) == found["walkingFrames"]
    assert call("startDelays", frames) == []
    assert call("stops", frames) == []


def test_a_frozen_run_across_a_zero_shorter_than_a_frame_is_no_stall():
    # The character stands (a wall) while one walk ends and the next begins.
    first = walking_frames(end=992, walking_since=0)
    x = first[-1]["x"]
    frozen = [frame(time, x, walking_since=0) for time in range(1008, 1200, FRAME_MS)]
    frozen += [frame(time, x, walking_since=1200.5) for time in range(1216, 1500, FRAME_MS)]
    again = walking_frames(start=1504, end=2400, walking_since=1200.5, x_at_start=x + 1.44)
    found = call("stallsOf", first + frozen + again)
    assert found["frozenFrames"] == len(range(1008, 1200, FRAME_MS))
    assert found["stalls"] == []


def test_a_start_waits_for_the_newest_key_when_two_come_before_the_character_moves():
    standing = standing_frames(0, 400)
    first_key = [frame(time, 0, walking_since=400) for time in range(400, 450, FRAME_MS)]
    second_key = [frame(time, 0, walking_since=450.5) for time in range(464, 600, FRAME_MS)]
    moving = walking_frames(start=608, end=900, walking_since=450.5, x_at_start=1.44)
    assert call("startDelays", standing + first_key + second_key + moving) == [608 - 450.5]


def test_stop_distance_and_time():
    walking = walking_frames(end=992)
    last_x = walking[-1]["x"]
    # The key is released before the frame at 1008. The character glides on
    # by 0.5 units in each of the next 6 frames (1024 .. 1104) and then stands.
    gliding = [frame(1008, last_x, walking_since=None)]
    gliding += [frame(1008 + FRAME_MS * k, last_x + 0.5 * k, walking_since=None) for k in range(1, 7)]
    standing = [frame(time, last_x + 3, walking_since=None) for time in range(1120, 1400, FRAME_MS)]
    found = call("stops", walking + gliding + standing)
    assert found == [{"distance": pytest.approx(3), "duration": 1104 - 1008}]


def test_a_stop_without_gliding_on():
    walking = walking_frames(end=992)
    standing = [frame(time, walking[-1]["x"], walking_since=None) for time in range(1008, 1300, FRAME_MS)]
    assert call("stops", walking + standing) == [{"distance": 0, "duration": 0}]


def test_a_stop_is_dropped_when_the_player_walks_again_before_it_settled():
    walking = walking_frames(end=992)
    short_break = [frame(time, walking[-1]["x"], walking_since=None) for time in range(1008, 1100, FRAME_MS)]
    again = walking_frames(start=1104, end=1500, walking_since=1104, x_at_start=walking[-1]["x"])
    assert call("stops", walking + short_break + again) == []
    assert call("stops", []) == []


def test_frame_times():
    results = run_diagnostic(
        calls=[["frameTimes", []], ["frameTimes", [frame(3, 0)]], ["frameTimes", [frame(0, 0), frame(16, 0), frame(50, 0)]]]
    )["results"]
    assert results == [[], [], [16, 34]]


def test_summary_and_report_of_an_empty_recording():
    recording = {"startedAt": 1000, "tabWasHidden": False, "frames": [], "messages": [], "roundTrips": [], "lostProbes": 0}
    facts = {"date": "today", "userAgent": "Test", "devicePixelRatio": 1, "canvas": None}
    numbers = call("summarize", recording, 3000)
    text = call("reportText", facts, numbers)
    assert numbers["recordedSeconds"] == 2
    assert numbers["fullBuffers"] == []
    assert "Buffers full: none" in text
    assert numbers["walkingGaps"]["count"] == 0
    assert numbers["walkingGaps"]["median"] is None
    assert numbers["roundTrip"] == {"count": 0, "median": None, "p95": None, "max": None, "lost": 0}
    assert numbers["walking"]["stallsPerSecond"] is None
    assert text.splitlines()[0] == "Group Project walking diagnostic"
    assert "Canvas: none" in text
    assert "median -" in text


# ---- With ?debug: a walk played through the stand-ins ---------------------------------------


def positions(x):
    return {"type": "positions", "players": [{"name": "Bo", "x": 50, "y": 50}, {"name": OWN_NAME, "x": x, "y": 10}]}


# The player stands until the key at 320 ms. All other times of the walk
# count from the key.
KEY_AT = 320
# When the server's messages arrive: every 67 ms, but the one at 1400 is 300 ms late.
MESSAGE_TIMES = list(range(100, 1100, 67)) + list(range(1400, 3000, 67))
MOVES_FROM = 176  # the character is drawn moving from then on
FIRST_FRAME_THAT_MOVED = 192


def walk_steps():
    """Steps of a recording: the player stands, walks right for 3 s, then stops.

    The server sends the own position every 67 ms, 6 units further each
    time, except for one message that comes 300 ms late. The character is
    drawn moving at 90 units per second from 176 ms after the key on.
    """
    steps = [["receive", {"type": "signed_in", "name": OWN_NAME, "guest": True}], ["position", 0, 10], ["frame", 0]]
    steps += [["tick", 1000], ["clock", 40], ["receive", welcome(0)]]
    for time in range(FRAME_MS, KEY_AT + 1, FRAME_MS):
        steps += [["frame", time]]
    steps += [["direction", 1, 0]]  # the key, right after the frame at 320
    events = []
    for time in range(FRAME_MS, 3001, FRAME_MS):
        x = max(0, WALKING_SPEED * (time - MOVES_FROM) / 1000)
        events.append((time, ["position", x, 10]))
        events.append((time, ["frame", KEY_AT + time]))
    for number, time in enumerate(MESSAGE_TIMES):
        events.append((time - 1, ["clock", KEY_AT + time]))
        events.append((time - 1, ["receive", positions(6 * number)]))
    events.sort(key=lambda event: event[0])
    for _, step in events:
        steps.append(step)
    steps += [["direction", 0, 0]]
    stop_x = WALKING_SPEED * (3000 - MOVES_FROM) / 1000
    for time in range(3008, 3400, FRAME_MS):
        steps += [["position", stop_x, 10], ["frame", KEY_AT + time]]
    return steps


@pytest.fixture(scope="module")
def walked():
    return run_diagnostic(search="?debug", steps=walk_steps())


def test_the_panel_appears_in_the_top_left_corner_above_everything(walked):
    style = walked["panelStyle"]
    assert walked["bodyChildren"] == 1
    assert style["position"] == "fixed"
    assert style["top"] == "4px" and style["left"] == "4px"
    assert int(style["zIndex"]) > 10  # the top message has 10
    assert "monospace" in style["font"]
    assert style["pointerEvents"] == "none"  # clicks reach the game, except on the buttons
    assert walked["panelTexts"][0].startswith("Walking diagnostic, ")
    # The buttons are never reached with Tab.
    assert walked["buttons"] == [
        {"text": "Copy", "tabIndex": -1},
        {"text": "Reset", "tabIndex": -1},
        {"text": "Hide", "tabIndex": -1},
    ]


def test_the_panel_says_that_a_wall_counts_as_a_gap_and_a_stall(walked):
    lines = walked["panelTexts"][0].splitlines()
    assert lines[1] == WALL_NOTE
    assert WALL_NOTE in walked["report"].splitlines()


def test_the_diagnostic_listens_sends_and_draws_only_with_debug(walked):
    record = walked["record"]
    assert sorted(record["handlers"]) == ["close", "positions", "signed_in", "signed_out", "welcome"]
    assert sorted(record["intervals"]) == [500, 1000]
    assert record["frameRequests"] > 100
    assert record["sent"] == [hello(0)]


def test_the_numbers_of_a_walk(walked):
    numbers = walked["numbers"]
    gaps = numbers["walkingGaps"]
    # The first message after the key counts as the start of the gaps.
    assert gaps["count"] == len(MESSAGE_TIMES) - 1
    assert gaps["median"] == 67
    assert gaps["max"] == 1400 - 1038
    assert [bucket["count"] for bucket in gaps["histogram"]][2] == gaps["count"] - 1
    assert [bucket["count"] for bucket in gaps["histogram"]][6] == 1  # 300–500
    assert gaps["largeGaps"] == [{"atSeconds": pytest.approx((KEY_AT + 1400) / 1000), "ms": 362}]
    assert gaps["perSecond"] == pytest.approx(gaps["count"] / ((MESSAGE_TIMES[-1] - MESSAGE_TIMES[0]) / 1000))
    assert numbers["ownStep"]["median"] == 6
    assert numbers["roundTrip"]["count"] == 1
    assert numbers["roundTrip"]["median"] == 40
    assert numbers["frames"]["median"] == FRAME_MS
    assert numbers["frames"]["over25"] == 0
    walking = numbers["walking"]
    assert walking["frames"] > 100
    assert walking["frozenFrames"] == 0
    assert walking["stalls"] == 0
    assert walking["speed"]["median"] == pytest.approx(WALKING_SPEED)
    assert walking["unevenPercent"] == 0
    # From the key itself to the first frame that moved.
    assert numbers["startDelay"] == {"count": 1, "median": FIRST_FRAME_THAT_MOVED, "max": FIRST_FRAME_THAT_MOVED}
    assert numbers["stop"]["distance"]["count"] == 1
    assert numbers["fullBuffers"] == []
    assert numbers["tabWasHidden"] is False
    assert numbers["devicePixelRatio"] == 2
    assert numbers["canvas"] == {"width": 800, "height": 600, "pageWidth": 400, "pageHeight": 300}


EVERY_LINE = [
    "Group Project walking diagnostic",
    "Date: ",
    "Recorded: ",
    "Buffers full: none",
    "Browser: Node stand-in browser",
    "Device pixel ratio: 2",
    "Canvas: 800 x 600 pixels (400 x 300 on the page)",
    "Tab hidden during recording: no",
    WALL_NOTE,
    "walking gaps: ",
    "messages per second: ",
    "gap ms: median 67.0, p95 ",
    "histogram ms: <20: 0 | 20–50: 0 | 50–90: ",
    "| ≥500: 0",
    "last large gaps (>= 150 ms): at 1.7 s: 362 ms",
    "own step per message (units): count ",
    "Round trip (hello to welcome)",
    "answered: 1, lost: 0, ms: median 40.0, p95 40.0, max 40.0",
    "frames: ",
    "longer than 25 ms: 0, longer than 50 ms: 0",
    "walking frames: ",
    "frozen frames: 0",
    "stalls: 0, per second of walking: 0.00, longest ms: -",
    "last stalls: none",
    "drawn speed (units/s): median 90.0, p5 90.0, p95 90.0, uneven frames: 0.0 %",
    "start delay ms: count 1, median 192, max 192",
    "stop distance units: count 1",
    "stop time ms: count 1",
]


@pytest.mark.parametrize("line", EVERY_LINE)
def test_the_report_contains_every_number(walked, line):
    assert line in walked["report"]


def test_the_report_starts_with_its_title_and_holds_no_player_name(walked):
    report = walked["report"]
    assert report.splitlines()[0] == "Group Project walking diagnostic"
    assert OWN_NAME not in report
    assert "Bo" not in report


def test_a_hidden_tab_is_reported():
    report = run_diagnostic(search="?debug", steps=[["hide"]])["report"]
    assert "Tab hidden during recording: yes" in report


def test_stalls_are_found_in_a_played_walk():
    steps = [["direction", 1, 0]]
    x = 0.0
    for time in range(0, 2001, FRAME_MS):
        if not 1000 <= time < 1200:  # 200 ms in which the character is drawn in one place
            x += 1.44
        steps += [["position", x, 0], ["frame", time]]
    walking = run_diagnostic(search="?debug", steps=steps)["numbers"]["walking"]
    assert walking["stalls"] == 1
    assert walking["longestStallMs"] == 1200 - 992
    assert walking["lastStalls"] == [{"atSeconds": 0.992, "ms": 208}]


# ---- With ?debug: the probe ----------------------------------------------------------------


def probe_steps(*times):
    """The one-second timer runs at each of these times."""
    steps = []
    for time in times:
        steps += [["clock", time], ["tick", 1000]]
    return steps


def test_at_most_one_probe_is_in_flight():
    result = run_diagnostic(search="?debug", steps=probe_steps(1000, 2000, 3000, 4000, 5999))
    assert result["record"]["sent"] == [hello(0)]
    assert result["numbers"]["roundTrip"]["lost"] == 0


def test_a_probe_unanswered_after_5_seconds_is_lost_and_the_next_one_goes_out():
    steps = probe_steps(1000, 2000, 3000, 4000, 5000, 6000)
    steps += [["clock", 6100], ["receive", welcome(1)]]
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["record"]["sent"] == [hello(0), hello(1)]
    assert result["numbers"]["roundTrip"]["lost"] == 1
    assert result["numbers"]["roundTrip"]["count"] == 1
    assert result["numbers"]["roundTrip"]["median"] == 6100 - 6000


def test_a_late_welcome_to_a_lost_probe_is_not_the_answer_to_the_next_one():
    # The answer to the first probe arrives after 5.02 s, just after the
    # second probe went out. It must not read as a round trip of 20 ms.
    steps = probe_steps(1000, 6000) + [["clock", 6020], ["receive", welcome(0)]]
    late_only = run_diagnostic(search="?debug", steps=steps)
    assert late_only["record"]["sent"] == [hello(0), hello(1)]
    assert late_only["numbers"]["roundTrip"]["count"] == 0
    assert late_only["numbers"]["roundTrip"]["lost"] == 1

    # The second probe is still in flight, and its own answer counts.
    steps += probe_steps(7000) + [["clock", 7300], ["receive", welcome(1)]]
    then_answered = run_diagnostic(search="?debug", steps=steps)
    assert then_answered["record"]["sent"] == [hello(0), hello(1)]
    assert then_answered["numbers"]["roundTrip"]["count"] == 1
    assert then_answered["numbers"]["roundTrip"]["median"] == 7300 - 6000


@pytest.mark.parametrize(
    "answer",
    [
        {"type": "welcome"},  # no name
        {"type": "welcome", "name": "debug"},  # the name of the first version of the probe
        {"type": "welcome", "name": "debug1"},  # a probe that was not sent yet
        {"type": "welcome", "name": 0},
    ],
)
def test_a_welcome_with_another_name_is_not_the_answer(answer):
    steps = probe_steps(1000) + [["clock", 1080], ["receive", answer]] + probe_steps(2000)
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["numbers"]["roundTrip"]["count"] == 0
    assert result["record"]["sent"] == [hello(0)]  # the probe is still in flight


def test_an_answered_probe_frees_the_way_for_the_next():
    steps = probe_steps(1000) + [["clock", 1080], ["receive", welcome(0)]] + probe_steps(2000)
    steps += [["clock", 2050], ["receive", welcome(1)]]
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["record"]["sent"] == [hello(0), hello(1)]
    assert result["numbers"]["roundTrip"]["count"] == 2
    assert result["numbers"]["roundTrip"]["max"] == 80


def test_a_welcome_without_a_probe_is_ignored():
    steps = [["clock", 500], ["receive", welcome(0)]]
    assert run_diagnostic(search="?debug", steps=steps)["numbers"]["roundTrip"]["count"] == 0


def test_without_a_connection_no_probe_is_in_flight():
    steps = [["connected", False]] + probe_steps(1000, 2000) + [["connected", True]] + probe_steps(3000)
    result = run_diagnostic(search="?debug", steps=steps)
    # A probe that could not be sent does not use up a name.
    assert result["record"]["sent"] == [hello(0)]
    assert result["numbers"]["roundTrip"]["lost"] == 0


def test_a_probe_in_flight_when_the_connection_closes_is_forgotten_not_lost():
    # The connection closes 300 ms after a probe went out and is back after
    # 8 s. net.js tells 'close' once and 'open' when it is back.
    steps = probe_steps(1000) + [["clock", 1300], ["connected", False], ["receive", {"type": "close"}]]
    steps += probe_steps(2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000)
    steps += [["clock", 9300], ["connected", True], ["receive", {"type": "open"}]]
    steps += probe_steps(10000) + [["clock", 10060], ["receive", welcome(1)]]
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["record"]["sent"] == [hello(0), hello(1)]
    assert result["numbers"]["roundTrip"]["lost"] == 0
    assert result["numbers"]["roundTrip"]["count"] == 1
    assert result["numbers"]["roundTrip"]["median"] == 60
    assert "answered: 1, lost: 0" in result["report"]


def test_a_connection_that_is_back_at_once_sends_the_next_probe_without_waiting_5_seconds():
    steps = probe_steps(1000) + [["clock", 1300], ["connected", False], ["receive", {"type": "close"}]]
    steps += [["clock", 1900], ["connected", True], ["receive", {"type": "open"}]] + probe_steps(2000)
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["record"]["sent"] == [hello(0), hello(1)]
    assert result["numbers"]["roundTrip"]["lost"] == 0


def test_the_welcome_to_a_probe_from_before_the_connection_closed_is_ignored():
    steps = probe_steps(1000) + [["clock", 1300], ["receive", {"type": "close"}]]
    steps += [["clock", 1400], ["receive", welcome(0)]]
    assert run_diagnostic(search="?debug", steps=steps)["numbers"]["roundTrip"]["count"] == 0


def test_every_probe_name_is_a_valid_name_and_the_numbers_start_again_after_9999():
    steps = []
    for number in range(10001):
        steps += [["clock", 1000 * number], ["tick", 1000], ["receive", welcome(number % 10000)]]
    result = run_diagnostic(search="?debug", steps=steps)
    names = [sent["name"] for sent in result["record"]["sent"]]
    assert names[:2] == ["debug0", "debug1"]
    assert names[9999:] == ["debug9999", "debug0"]
    assert len(set(names[:10000])) == 10000
    for name in ["debug0", "debug9999"]:  # the shortest and the longest
        assert protocol.parse_client_message(json.dumps({"type": "hello", "name": name}))["name"] == name
    assert all(protocol.NAME_PATTERN.fullmatch(name) for name in names)
    assert result["numbers"]["roundTrip"]["lost"] == 0


# ---- With ?debug: Copy and Reset ---------------------------------------------------------------


def test_copy_puts_the_report_on_the_clipboard_and_gives_up_the_focus():
    result = run_diagnostic(search="?debug", steps=[["frame", 0], ["frame", 16], ["click", "Copy"]])
    copied = result["record"]["copied"]
    assert len(copied) == 1
    assert copied[0].startswith("Group Project walking diagnostic\n")
    assert result["record"]["focusAfterClicks"] == [False]
    assert [button["text"] for button in result["buttons"]] == ["Copied", "Reset", "Hide"]


def test_copied_turns_back_into_copy():
    result = run_diagnostic(search="?debug", steps=[["click", "Copy"], ["timeouts"]])
    assert [button["text"] for button in result["buttons"]] == ["Copy", "Reset", "Hide"]


@pytest.mark.parametrize("clipboard", ["refuses", "missing"])
def test_copy_falls_back_to_a_hidden_textarea(clipboard):
    result = run_diagnostic(search="?debug", clipboard=clipboard, steps=[["click", "Copy"]])
    assert result["record"]["execCommands"] == ["copy"]
    assert "textarea" in result["record"]["created"]
    assert result["bodyChildren"] == 1  # the textarea is gone again
    assert result["record"]["focusAfterClicks"] == [False]
    assert result["buttons"][0]["text"] == "Copied"


def test_reset_forgets_everything_and_gives_up_the_focus():
    steps = [["direction", 1, 0]]
    for time in range(0, 1001, FRAME_MS):
        steps += [["position", time / 10, 0], ["frame", time]]
    steps += probe_steps(1000) + [["clock", 1050], ["receive", welcome(0)]]
    steps += [["clock", 2000], ["click", "Reset"], ["frame", 2016]]
    result = run_diagnostic(search="?debug", steps=steps)
    numbers = result["numbers"]
    assert numbers["frames"]["count"] == 0
    assert numbers["walking"]["frames"] == 0
    assert numbers["roundTrip"]["count"] == 0
    assert numbers["recordedSeconds"] == pytest.approx(0.016)
    assert result["record"]["focusAfterClicks"] == [False]


def test_reset_drops_the_probe_in_flight():
    steps = probe_steps(1000) + [["reset"], ["clock", 1100], ["receive", welcome(0)]]
    result = run_diagnostic(search="?debug", steps=steps + probe_steps(2000))
    assert result["numbers"]["roundTrip"]["count"] == 0
    # The next probe has a new name, so the old answer can never be taken for its own.
    assert result["record"]["sent"] == [hello(0), hello(1)]


# ---- With ?debug: Hide and Show ----------------------------------------------------------------


def short_walk_steps(start=0, end=1000):
    steps = [["direction", 1, 0]]
    for time in range(start, end + 1, FRAME_MS):
        steps += [["position", WALKING_SPEED * time / 1000, 0], ["frame", time]]
    return steps


def test_hide_folds_the_panel_down_to_its_title_line_and_the_buttons():
    result = run_diagnostic(search="?debug", steps=short_walk_steps() + [["clock", 1200], ["click", "Hide"]])
    assert result["panelTexts"] == ["Walking diagnostic, 1.2 s recorded"]
    assert [button["text"] for button in result["buttons"]] == ["Copy", "Reset", "Show"]
    assert result["record"]["focusAfterClicks"] == [False]  # the walking keys keep working
    assert result["bodyChildren"] == 1


def test_while_hidden_the_recording_goes_on_and_the_title_keeps_counting():
    steps = short_walk_steps(end=496) + [["click", "Hide"]] + short_walk_steps(start=512, end=1000)
    steps += probe_steps(1000) + [["clock", 1040], ["receive", welcome(0)], ["clock", 1500], ["tick", 500]]
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["panelTexts"] == ["Walking diagnostic, 1.5 s recorded"]
    numbers = result["numbers"]
    assert numbers["frames"]["count"] == len(range(0, 1001, FRAME_MS)) - 1
    assert numbers["walking"]["frames"] == len(range(400, 1001, FRAME_MS))
    assert numbers["roundTrip"]["count"] == 1


def test_copy_while_hidden_still_copies_the_whole_report():
    steps = short_walk_steps() + [["click", "Hide"], ["click", "Copy"]]
    result = run_diagnostic(search="?debug", steps=steps)
    copied = result["record"]["copied"]
    assert len(copied) == 1
    assert "drawn speed (units/s): median 90.0" in copied[0]
    assert [button["text"] for button in result["buttons"]] == ["Copied", "Reset", "Show"]
    assert result["panelTexts"][0].count("\n") == 0


def test_show_brings_the_numbers_back_at_once():
    steps = short_walk_steps() + [["click", "Hide"], ["clock", 1300], ["click", "Show"]]
    result = run_diagnostic(search="?debug", steps=steps)
    lines = result["panelTexts"][0].splitlines()
    assert lines[0] == "Walking diagnostic, 1.3 s recorded"
    assert lines[1] == WALL_NOTE
    assert any(line.startswith("  walking frames: ") for line in lines)
    assert [button["text"] for button in result["buttons"]] == ["Copy", "Reset", "Hide"]
    assert result["record"]["focusAfterClicks"] == [False, False]


def test_reset_while_hidden_keeps_the_panel_hidden():
    steps = short_walk_steps() + [["click", "Hide"], ["clock", 2000], ["click", "Reset"], ["clock", 2500], ["tick", 500]]
    result = run_diagnostic(search="?debug", steps=steps)
    assert result["panelTexts"] == ["Walking diagnostic, 0.5 s recorded"]
    assert [button["text"] for button in result["buttons"]] == ["Copy", "Reset", "Show"]
    assert result["numbers"]["frames"]["count"] == 0


# ---- With ?debug: full buffers ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def long_recording():
    # 400 s of walking: about 24 000 frames, 5 700 messages and 380 probes,
    # more than the diagnostic keeps of each. Then the panel is refreshed 61 times.
    steps = [["receive", {"type": "signed_in", "name": OWN_NAME, "guest": True}], ["long_walk", 400], ["time_refresh", 61]]
    return run_diagnostic(search="?debug", steps=steps)


def test_only_the_newest_entries_are_kept(long_recording):
    numbers = long_recording["numbers"]
    assert numbers["recordedSeconds"] > 400
    assert numbers["frames"]["count"] == MOST_FRAMES - 1  # the times between 10 800 frames
    assert numbers["walkingGaps"]["count"] == MOST_MESSAGES - 1
    assert numbers["roundTrip"]["count"] == MOST_ROUND_TRIPS


def test_the_numbers_say_which_buffers_are_full_and_what_they_cover(long_recording):
    full = long_recording["numbers"]["fullBuffers"]
    assert [(buffer["what"], buffer["kept"]) for buffer in full] == [
        ("frames", MOST_FRAMES),
        ("positions messages", MOST_MESSAGES),
        ("round trips", MOST_ROUND_TRIPS),
    ]
    # 10 800 frames of about 17 ms and 2 700 messages of about 75 ms: about three minutes each.
    assert full[0]["seconds"] == pytest.approx(MOST_FRAMES * 0.017, rel=0.1)
    assert full[1]["seconds"] == pytest.approx(MOST_MESSAGES * 0.075, rel=0.1)
    assert full[0]["seconds"] < long_recording["numbers"]["recordedSeconds"] / 2
    assert full[2]["seconds"] is None


def test_the_report_and_the_panel_say_that_recorded_covers_more_than_the_numbers(long_recording):
    lines = long_recording["report"].splitlines()
    assert lines[2].startswith("Recorded: 40")
    assert lines[3].startswith("Buffers full: frames: the last 10800 only (1")
    assert "; positions messages: the last 2700 only (" in lines[3]
    assert lines[3].endswith(" s); round trips: the last 180 only")
    panel = long_recording["panelTexts"][0].splitlines()
    assert panel[1] == lines[3]
    assert panel[2] == WALL_NOTE


def test_while_no_buffer_is_full_the_panel_has_no_line_about_it(walked):
    assert "Buffers full" not in walked["panelTexts"][0]


def test_a_refresh_of_the_panel_with_full_buffers_is_quick(long_recording):
    # Twice a second, on the same thread that draws the game and handles the
    # `positions` messages: the tool must not disturb what it measures. It
    # takes about 2 ms here; 8 ms leaves room for a busy machine. (Before,
    # with five sorts of up to 20 000 values, it took 35 to 65 ms.)
    times = long_recording["record"]["refreshMs"]
    assert len(times) == 61
    assert statistics.median(times) < 8, sorted(times)


def test_a_long_even_walk_is_reported_as_even(long_recording):
    # Checks the numbers of the full buffers against what the node script played.
    walking = long_recording["numbers"]["walking"]
    assert walking["frames"] == MOST_FRAMES - 1
    assert walking["speed"]["median"] == pytest.approx(WALKING_SPEED)
    assert walking["unevenPercent"] == 0
    assert long_recording["numbers"]["roundTrip"]["max"] <= 60


# ---- net.js: `welcome` is not the answer to an action ----------------------------------------


def run_page(steps):
    finished = subprocess.run(
        [NODE, str(PAGE_IN_NODE)], input=json.dumps(steps), capture_output=True, text=True, timeout=60, check=True
    )
    return json.loads(finished.stdout)


def guests_sent(page):
    return [sent for sent in page["sent"] if sent["type"] == "guest"]


def test_a_welcome_does_not_let_a_second_action_through():
    page = run_page([["open"], ["click", "start-guest"], ["receive", protocol.welcome("debug")], ["click", "start-guest"]])
    assert len(guests_sent(page)) == 1


def test_a_real_answer_still_lets_the_next_action_through():
    # The same steps with an answer of the server instead of `welcome`.
    page = run_page(
        [["open"], ["click", "start-guest"], ["receive", protocol.rejection("no_lobby")], ["click", "start-guest"]]
    )
    assert len(guests_sent(page)) == 2


def test_a_welcome_while_nothing_is_asked_changes_nothing():
    page = run_page([["open"], ["receive", protocol.welcome("debug")], ["click", "start-guest"]])
    assert len(guests_sent(page)) == 1
