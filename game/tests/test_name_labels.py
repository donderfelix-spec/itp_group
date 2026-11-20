"""Only one name where name labels would cover each other (M2-1.8, S-117).

Game.world.chooseLabels() in client/js/world/draw.js decides which labels are
drawn. It is a plain function, so these tests run the page's own draw.js in
Node (tests/labels_in_node.js) and pass it labels as world.js would. The
labels' sizes below are those of world.js: 8 map units high plus an outline
of 0.7 on each side. How the names look in the running game is tried in a
browser.

Without Node the tests that run draw.js are skipped; CI has Node.
"""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
LABELS_IN_NODE = TESTS / "labels_in_node.js"
WORLD_FOLDER = TESTS.parent / "client" / "js" / "world"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

HEIGHT = 9.4  # LABEL_HEIGHT 8 plus the outline on both sides
WIDTH = 40  # a short name with its outline
MARGIN = 4  # LABEL_COME_BACK_MARGIN in draw.js


def label(name, x, y=100, own=False, width=WIDTH):
    return {"name": name, "x": x, "y": y, "width": width, "height": HEIGHT, "own": own}


def choose(frames, hidden_before=()):
    """Runs chooseLabels on each frame in turn, passing the hidden names on."""
    finished = subprocess.run(
        [NODE, str(LABELS_IN_NODE)],
        input=json.dumps({"hiddenBefore": list(hidden_before), "frames": frames}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def shown_names(result):
    return sorted(shown["name"] for shown in result["shown"])


def overlap(a, b):
    apart_sideways = abs(a["x"] - b["x"]) >= (a["width"] + b["width"]) / 2
    apart_up_and_down = abs(a["y"] - b["y"]) >= (a["height"] + b["height"]) / 2
    return not apart_sideways and not apart_up_and_down


def players_on_one_point(count, own_index):
    """`count` labels on the same point in drawing order; the own one at `own_index`."""
    return [label(f"P{index}", 300, own=index == own_index) for index in range(count)]


# Accepted: everybody on the spawn sees only the own name

@needs_node
@pytest.mark.parametrize("count", [2, 8])
def test_on_one_point_only_the_own_label_is_drawn(count):
    # world.js draws the own character last (OWN_IN_FRONT).
    [result] = choose([players_on_one_point(count, own_index=count - 1)])
    assert shown_names(result) == [f"P{count - 1}"]
    assert result["hidden"] == sorted(f"P{index}" for index in range(count - 1))


@needs_node
@pytest.mark.parametrize("count", [2, 8])
def test_the_own_label_wins_against_a_character_drawn_on_top(count):
    [result] = choose([players_on_one_point(count, own_index=0)])
    assert shown_names(result) == ["P0"]


@needs_node
@pytest.mark.parametrize("count", [2, 8])
def test_on_one_point_every_browser_draws_its_own_name(count):
    # Each of the players looks at the same pile from their own browser.
    for own_index in range(count):
        [result] = choose([players_on_one_point(count, own_index)])
        assert shown_names(result) == [f"P{own_index}"]


@needs_node
def test_the_own_label_stays_above_its_head():
    own = label("Me", 300, y=120, own=True)
    [result] = choose([[label("Other", 305, y=118), own]], hidden_before=["Me"])
    assert result["shown"] == [own]


@needs_node
def test_labels_apart_are_all_drawn_where_they_belong():
    labels = [label("A", 100), label("B", 100 + WIDTH), label("C", 300, own=True), label("D", 100, y=100 + HEIGHT)]
    [result] = choose([labels])
    assert shown_names(result) == ["A", "B", "C", "D"]
    assert result["hidden"] == []
    # Nobody's label was moved.
    assert sorted(result["shown"], key=lambda shown: shown["name"]) == labels


# Two other players

@needs_node
def test_of_two_new_others_on_one_point_the_one_drawn_on_top_wins():
    [result] = choose([[label("Below", 300), label("OnTop", 310)]])
    assert shown_names(result) == ["OnTop"]
    assert result["hidden"] == ["Below"]


@needs_node
def test_when_the_draw_order_flips_the_name_on_top_is_shown_once_and_stays():
    frames = [
        [label("A", 300), label("B", 310)],  # B is drawn on top and wins
        [label("A", 305), label("B", 305)],
        [label("B", 310), label("A", 300)],  # now A is drawn on top: one swap
        [label("B", 312), label("A", 298)],
        [label("B", 314), label("A", 296)],  # no swapping back while A stays on top
    ]
    results = choose(frames)
    assert [shown_names(result) for result in results] == [["B"], ["B"], ["A"], ["A"], ["A"]]
    assert [result["hidden"] for result in results] == [["A"], ["A"], ["B"], ["B"], ["B"]]


@needs_node
def test_a_hidden_name_comes_back_only_outside_the_margin():
    gap_steps = [0, 1, 2, 3, 3.9, MARGIN, MARGIN + 1]
    frames = [[label("A", 300 + WIDTH + gap), label("B", 300)] for gap in gap_steps]
    results = choose(frames, hidden_before=["A"])
    assert [shown_names(result) for result in results] == [
        ["B"], ["B"], ["B"], ["B"], ["B"], ["A", "B"], ["A", "B"],
    ]


@needs_node
def test_the_margin_also_counts_up_and_down():
    frames = [[label("A", 300, y=100 + HEIGHT + gap), label("B", 300)] for gap in [2, MARGIN]]
    results = choose(frames, hidden_before=["A"])
    assert [shown_names(result) for result in results] == [["B"], ["A", "B"]]


@needs_node
def test_a_name_that_was_shown_needs_no_margin():
    # Touching at the edge is not covering.
    [result] = choose([[label("A", 300 + WIDTH), label("B", 300)]])
    assert shown_names(result) == ["A", "B"]


@needs_node
def test_a_hidden_name_needs_the_margin_also_from_the_own_label():
    frames = [[label("A", 300 + WIDTH + gap), label("Me", 300, own=True)] for gap in [2, MARGIN]]
    results = choose(frames, hidden_before=["A"])
    assert [shown_names(result) for result in results] == [["Me"], ["A", "Me"]]


@needs_node
def test_a_hidden_name_drawn_on_top_is_decided_first_and_wins():
    # The margin only delays a name coming back next to a label drawn on top;
    # it never lets a lower character's label beat one drawn on top.
    [result] = choose([[label("WasShown", 300), label("WasHidden", 300)]], hidden_before=["WasHidden"])
    assert shown_names(result) == ["WasHidden"]
    assert result["hidden"] == ["WasShown"]


@needs_node
def test_a_hidden_name_does_not_block_a_name_decided_after_it():
    # B covers A, A was shown. C covers B but not A. B is hidden, so C is drawn.
    labels = [label("C", 300 + 1.5 * WIDTH), label("B", 300 + WIDTH / 2), label("A", 300)]
    [result] = choose([labels])
    assert shown_names(result) == ["A", "C"]
    assert result["hidden"] == ["B"]


# Edge cases

@needs_node
def test_without_own_player_the_others_are_still_decided():
    frames = [
        [label("A", 300), label("B", 300), label("C", 500)],
        [label("B", 300), label("A", 300), label("C", 500)],
    ]
    results = choose(frames)
    assert [shown_names(result) for result in results] == [["B", "C"], ["A", "C"]]


@needs_node
def test_no_labels_draws_nothing():
    [result] = choose([[]], hidden_before=["Gone"])
    assert result == {"shown": [], "hidden": []}


@needs_node
def test_a_player_seen_for_the_first_time_needs_no_margin():
    # New is drawn below Old and only 2 units beside it: not hidden before,
    # so being clear of it is enough.
    frames = [[label("Old", 300)], [label("New", 300 + WIDTH + 2), label("Old", 300)]]
    results = choose(frames)
    assert shown_names(results[1]) == ["New", "Old"]


@needs_node
def test_a_player_seen_for_the_first_time_on_top_wins():
    frames = [[label("Old", 300)], [label("Old", 300), label("New", 300)]]
    results = choose(frames)
    assert shown_names(results[1]) == ["New"]


@needs_node
def test_a_player_who_left_is_forgotten():
    frames = [[label("A", 300), label("B", 300)], [label("B", 300)], [label("B", 300), label("A", 300)]]
    results = choose(frames)
    assert results[1]["hidden"] == []
    # A comes back as a new player and is drawn on top.
    assert shown_names(results[2]) == ["A"]


@needs_node
def test_drawn_labels_never_overlap_and_never_move():
    # Eight players walk about at random near the spawn for 200 frames.
    chance = random.Random(88)
    places = {f"P{index}": [300.0, 300.0] for index in range(8)}
    frames = []
    for _ in range(200):
        for place in places.values():
            place[0] += chance.uniform(-6, 6)
            place[1] += chance.uniform(-6, 6)
        frame = [label(name, x, y, own=name == "P0") for name, (x, y) in places.items()]
        frames.append(sorted(frame, key=lambda entry: entry["y"]))
    for frame, result in zip(frames, choose(frames)):
        shown = result["shown"]
        assert "P0" in shown_names(result)
        for first in range(len(shown)):
            assert shown[first] in frame
            for second in range(first + 1, len(shown)):
                assert not overlap(shown[first], shown[second])


# The stacking is gone (A5)

def world_script():
    return (WORLD_FOLDER / "world.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["placeLabels", "LABEL_GAP", "label.y -="])
def test_the_stacking_code_is_gone(name):
    assert name not in world_script()


def test_stopping_the_world_forgets_the_hidden_names():
    # A player hidden on the last frame before leaving a lobby must not need
    # the margin in the next lobby: there they are a player not seen before.
    script = world_script()
    stop = script[script.index("function stop() {"):]
    stop = stop[:stop.index("\n  }\n")]
    assert "players.clear();" in stop
    assert "hiddenNames = new Set();" in stop


def test_world_js_asks_draw_js_which_labels_to_draw():
    assert "Game.world.chooseLabels(" in world_script()
    assert "var LABEL_COME_BACK_MARGIN = 4;" in (WORLD_FOLDER / "draw.js").read_text(encoding="utf-8")
