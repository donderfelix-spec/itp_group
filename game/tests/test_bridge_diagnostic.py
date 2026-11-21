"""What the walking diagnostic shows about "bridge the gaps" (M2-1.16).

With `?debug` in the address, the panel and the report of
js/world/diagnostic.js have one more group, "Bridging (the own character
walks on while messages are late)", below "Own character while walking".
world.js counts (`Game.world.bridgeNumbers()`), the diagnostic only shows,
and its Reset button sets the counts back to zero.

Two harnesses: the diagnostic alone with stand-ins (tests/diagnostic_in_node.js,
for the text of the lines), and the real bridge.js, world.js and
diagnostic.js together (tests/world_bridge_in_node.js, for a real walk
through hold-ups). Without Node the tests are skipped; CI has Node.
"""

import json
import subprocess

import pytest

from bridge_helpers import FELIX_DEBUG_RUN, KEY_AT, NODE, TESTS, looped, walk_right

DIAGNOSTIC_IN_NODE = TESTS / "diagnostic_in_node.js"
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

TITLE = "Bridging (the own character walks on while messages are late)"
# As in test_bridge_gaps.py: message 25 is held 620 ms, four more 240 ms each.
HOLD_UPS = looped(FELIX_DEBUG_RUN, first=-5)


def run_diagnostic(search="", calls=(), steps=()):
    finished = subprocess.run(
        [NODE, str(DIAGNOSTIC_IN_NODE)],
        input=json.dumps({"search": search, "calls": list(calls), "steps": list(steps)}),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(finished.stdout)


# ---- The lines, from numbers given to the diagnostic's plain functions ------------------------

EMPTY = {"startedAt": 0, "tabWasHidden": False, "frames": [], "messages": [], "roundTrips": [], "lostProbes": 0}
FACTS = {"date": "today", "userAgent": "Test", "devicePixelRatio": 1, "canvas": None}
COUNTED = {
    "on": True, "loaded": True, "inputLagMs": 121.6, "serverStepMs": 67.78,
    "steps": 37, "milliseconds": 2466.7, "replaced": 35, "corrections": 12, "largeCorrections": 2,
    "largestCorrection": 8.563, "takenBack": 1,
}


def report_lines(bridge):
    """The lines of a report whose numbers have `bridge` as the world's numbers about bridging."""
    numbers = run_diagnostic(calls=[["summarize", EMPTY, 1000]])["results"][0]
    if bridge != "missing":
        numbers["bridge"] = bridge
    return run_diagnostic(calls=[["reportText", FACTS, numbers]])["results"][0].splitlines()


def group(lines):
    """The lines of the group about bridging: its title and the indented lines below it."""
    start = lines.index(TITLE)
    end = next(index for index in range(start + 1, len(lines) + 1) if index == len(lines) or not lines[index].startswith("  "))
    return lines[start:end]


def test_the_group_shows_every_number_of_the_bridge():
    assert group(report_lines(COUNTED)) == [
        TITLE,
        "  bridging: on, input lag ms: 122, server step ms: 67.8",
        "  bridged steps: 37, bridged ms: 2467, server positions in their place: 35",
        "  corrections: 12, largest units: 8.56, above 1.5 units: 2, taken back: 1",
    ]


def test_the_group_stands_below_the_own_character_and_above_start_and_stop():
    lines = report_lines(COUNTED)
    before = lines[:lines.index(TITLE)]
    assert "Own character while walking" in before
    assert before[-1].startswith("  drawn speed (units/s): ")  # the last line of that group
    after = lines[lines.index(TITLE) + len(group(lines)):]
    assert after[0] == "Start and stop"
    assert lines.count(TITLE) == 1


def test_switched_off_the_group_says_bridging_off():
    off = dict(COUNTED, on=False, steps=0, milliseconds=0, replaced=0)
    assert group(report_lines(off)) == [TITLE, "  bridging: off"]


def test_without_bridge_js_the_group_says_that_it_did_not_load():
    assert group(report_lines({"on": False, "loaded": False})) == [TITLE, "  bridging: off (bridge.js did not load)"]


@pytest.mark.parametrize("bridge", [None, "missing"])
def test_when_the_world_cannot_tell_the_group_says_not_available(bridge):
    assert group(report_lines(bridge)) == [TITLE, "  bridging: not available"]


def test_with_a_world_that_does_not_count_the_panel_and_the_report_still_work():
    # The stand-in world of this harness has no bridgeNumbers(), like a
    # world.js from before this to-do. Reset must not fail either.
    result = run_diagnostic(search="?debug", steps=[["frame", 0], ["tick", 500], ["click", "Reset"], ["tick", 500]])
    assert result["numbers"]["bridge"] is None
    assert TITLE in result["report"].splitlines()
    assert "  bridging: not available" in result["panelTexts"][0].splitlines()


# ---- The real diagnostic on the real world, through hold-ups ------------------------------------

REFRESHED_AT = KEY_AT + 5000


def walked(search, steps=()):
    walk = walk_right(HOLD_UPS, until=KEY_AT + 7000, steps=list(steps))
    return walk.run(search=search)


@pytest.fixture(scope="module")
def with_debug():
    return walked("?debug", steps=[["numbers", REFRESHED_AT], ["refresh", REFRESHED_AT]])


def expected_group(numbers):
    return [
        TITLE,
        f"  bridging: on, input lag ms: {numbers['inputLagMs']:.0f}, server step ms: {numbers['serverStepMs']:.1f}",
        f"  bridged steps: {numbers['steps']}, bridged ms: {numbers['milliseconds']:.0f}, "
        f"server positions in their place: {numbers['replaced']}",
        f"  corrections: {numbers['corrections']}, largest units: {numbers['largestCorrection']:.2f}, "
        f"above 1.5 units: {numbers['largeCorrections']}, taken back: {numbers['takenBack']}",
    ]


def test_the_numbers_of_the_diagnostic_contain_the_numbers_of_the_bridge(with_debug):
    assert with_debug["diagnostic"]["bridge"] == with_debug["bridge"]
    assert with_debug["bridge"]["steps"] >= 9 + 3 * 3
    assert with_debug["bridge"]["on"] is True


def test_the_report_shows_the_group_with_the_counts_of_the_walk(with_debug):
    assert group(with_debug["report"].splitlines()) == expected_group(with_debug["bridge"])


def test_the_panel_shows_the_group_with_the_counts_at_that_moment(with_debug):
    at_the_refresh = with_debug["numbers"][0]
    assert at_the_refresh["steps"] == 9  # the long hold-up is over, the short ones are still to come
    assert group(with_debug["panels"][0].splitlines()) == expected_group(at_the_refresh)


def test_with_the_bridge_the_diagnostic_finds_no_stall_in_the_walk_through_the_hold_ups(with_debug):
    walking = with_debug["diagnostic"]["walking"]
    assert walking["frames"] > 350
    assert walking["frozenFrames"] == 0 and walking["stalls"] == 0
    assert walking["unevenPercent"] == 0
    # The messages were held up all the same: the diagnostic saw the gaps.
    assert with_debug["diagnostic"]["walkingGaps"]["max"] > 600


def test_switched_off_the_panel_says_so_and_the_diagnostic_finds_the_stalls():
    off = walked("?debug&bridge=off", steps=[["refresh", REFRESHED_AT]])
    assert group(off["panels"][0].splitlines()) == [TITLE, "  bridging: off"]
    assert group(off["report"].splitlines()) == [TITLE, "  bridging: off"]
    assert off["diagnostic"]["bridge"]["on"] is False
    assert off["diagnostic"]["walking"]["stalls"] >= 1
    assert off["diagnostic"]["walking"]["longestStallMs"] > 300


def test_reset_sets_the_counts_of_the_bridge_back_to_zero():
    after_the_long_hold_up = KEY_AT + 3000
    steps = [
        ["numbers", after_the_long_hold_up],
        ["click", after_the_long_hold_up, "Reset"],
        ["numbers", after_the_long_hold_up],
        ["refresh", after_the_long_hold_up],
    ]
    result = walked("?debug", steps=steps)
    before, after = result["numbers"]
    assert before["steps"] == 9 and before["replaced"] == 9
    counts = ["steps", "milliseconds", "replaced", "corrections", "largeCorrections", "largestCorrection", "takenBack"]
    assert [after[count] for count in counts] == [0] * len(counts)
    # What was measured about the connection stays: it is no count.
    assert after["inputLagMs"] == before["inputLagMs"] and after["serverStepMs"] == before["serverStepMs"]
    assert after["on"] is True
    assert "  bridged steps: 0, bridged ms: 0, server positions in their place: 0" in result["panels"][0].splitlines()
    # From the reset on it counts again: only the four short hold-ups.
    assert 4 * 3 <= result["bridge"]["steps"] <= 4 * 4


def test_reset_leaves_every_frame_as_it_was():
    steps = [["click", KEY_AT + 2500, "Reset"]]  # in the middle of the long hold-up
    assert walked("?debug", steps=steps)["frames"] == walked("?debug")["frames"]


def test_the_diagnostic_and_its_questions_leave_every_frame_of_a_bridged_walk_as_it_was(with_debug):
    without_debug = walked("")
    assert without_debug["diagnostic"] is None
    assert with_debug["frames"] == without_debug["frames"]
    assert {key: value for key, value in with_debug["bridge"].items()} == without_debug["bridge"]


def test_without_debug_the_diagnostic_is_still_inert_but_the_world_counts():
    result = walked("", steps=[["refresh", REFRESHED_AT]])
    assert result["diagnostic"] is None and result["report"] is None
    for active_only in ["report", "numbers", "reset"]:
        assert active_only not in result["exported"]
    assert result["panels"] == [""]  # no panel was made
    assert result["bridge"]["steps"] >= 9 + 3 * 3
