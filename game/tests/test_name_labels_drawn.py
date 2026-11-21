"""The name labels as the drawing loop of world.js writes them (M2-1.8), checked by the tester.

test_name_labels.py tests Game.world.chooseLabels() with labels made by hand.
These tests run the page's own characters.js, draw.js and world.js together
in Node (tests/world_labels_in_node.js) and play what a browser gets from the
server: the players, the own name, positions, frames. They check the names
that end up on the canvas, so they also cover what world.js adds around the
rule: the drawing order with the own character in front, the label above
each head, the hidden names kept from one frame to the next and forgotten
when the world stops.

The stand-in canvas counts 3 map units per letter, so the label of a name
with 3 letters is 3 * 3 + 6 + 2 * 0.7 = 16.4 units wide (world.js:
labelAboveHead) and two such labels touch at 16.4 units apart.

Without Node the tests are skipped; CI has Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
WORLD_LABELS_IN_NODE = TESTS / "world_labels_in_node.js"
CAMPUS_FILE = TESTS.parent / "client" / "js" / "world" / "campus.json"
CAMPUS = json.loads(CAMPUS_FILE.read_text(encoding="utf-8"))
SPAWN = CAMPUS["spawn"]

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

CHARACTERS = [
    "consultant",
    "finance_bro",
    "exchange_student",
    "surfer",
    "founder",
    "overachiever",
    "latecomer",
    "library_local",
]
# Width of the label of a name with three letters with the stand-in canvas.
THREE_LETTER_LABEL = 3 * 3 + 6 + 2 * 0.7
LABEL_HEIGHT = 8 + 2 * 0.7
MARGIN = 4  # LABEL_COME_BACK_MARGIN in draw.js
# Long enough for every glide to end (GLIDE_MILLISECONDS in world.js is 67).
SETTLED = 500


def players(*names):
    return ["players", [{"name": name, "character": CHARACTERS[index % 8]} for index, name in enumerate(names)]]


def positions(places):
    """`places`: name -> (x, y)."""
    return ["positions", [{"name": name, "x": x, "y": y} for name, (x, y) in places.items()]]


def frame(milliseconds=SETTLED):
    return ["frame", milliseconds]


def drawn(steps):
    """The names drawn on the canvas, per frame: a list of lists of {name, x, y}."""
    finished = subprocess.run(
        [NODE, str(WORLD_LABELS_IN_NODE)],
        input=json.dumps({"campus": CAMPUS, "steps": steps}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def names(drawn_frame):
    return sorted(label["name"] for label in drawn_frame)


def label_offset():
    """How far above a player's position its name is written, measured with one player alone."""
    [[alone]] = drawn([["start"], ["own", "Me"], players("Me"), positions({"Me": (300, 300)}), frame()])
    assert alone["x"] == 300
    return alone["y"] - 300


def names_do_not_overlap(drawn_frame):
    for first, a in enumerate(drawn_frame):
        for b in drawn_frame[first + 1:]:
            width_a = len(a["name"]) * 3 + 6 + 1.4
            width_b = len(b["name"]) * 3 + 6 + 1.4
            apart_sideways = abs(a["x"] - b["x"]) >= (width_a + width_b) / 2
            apart_up_and_down = abs(a["y"] - b["y"]) >= LABEL_HEIGHT
            if not apart_sideways and not apart_up_and_down:
                return False
    return True


def everybody_on_the_spawn(count):
    return {f"P{index}": (SPAWN["x"], SPAWN["y"]) for index in range(count)}


# Accepted: on the spawn each browser writes only its own name (A1)

@needs_node
@pytest.mark.parametrize("count", [2, 8])
def test_on_the_spawn_every_browser_writes_only_its_own_name(count):
    everybody = [f"P{index}" for index in range(count)]
    offset = label_offset()
    for own in everybody:
        frames = drawn([
            ["start"], ["own", own], players(*everybody), positions(everybody_on_the_spawn(count)),
            frame(), frame(16), frame(16),
        ])
        for drawn_frame in frames:
            assert drawn_frame == [{"name": own, "x": SPAWN["x"], "y": SPAWN["y"] + offset}]


@needs_node
def test_before_the_own_name_is_known_one_name_is_written_on_the_spawn():
    # Before the welcome the page knows no own name: of eight players on one
    # point exactly one name is written.
    everybody = [f"P{index}" for index in range(8)]
    [drawn_frame] = drawn([["start"], players(*everybody), positions(everybody_on_the_spawn(8)), frame()])
    assert len(drawn_frame) == 1


# Accepted: apart, every name is above its own character (A2)

@needs_node
def test_players_apart_every_name_is_written_above_its_own_head():
    offset = label_offset()
    places = {"Me": (300, 300), "Ann": (360, 300), "Bob": (300, 340), "Cid": (240, 260), "Dan": (420, 380)}
    [drawn_frame] = drawn([["start"], ["own", "Me"], players(*places), positions(places), frame()])
    assert names(drawn_frame) == sorted(places)
    for label in drawn_frame:
        x, y = places[label["name"]]
        assert (label["x"], label["y"]) == (x, y + offset)


@needs_node
def test_after_walking_apart_from_the_spawn_every_name_comes_back():
    everybody = ["Me", "Ann", "Bob", "Cid"]
    apart = {"Me": (SPAWN["x"], SPAWN["y"]), "Ann": (SPAWN["x"] - 50, SPAWN["y"]),
             "Bob": (SPAWN["x"] + 50, SPAWN["y"]), "Cid": (SPAWN["x"], SPAWN["y"] + 40)}
    on_spawn, walked = drawn([
        ["start"], ["own", "Me"], players(*everybody),
        positions({name: (SPAWN["x"], SPAWN["y"]) for name in everybody}), frame(),
        positions(apart), frame(),
    ])
    assert names(on_spawn) == ["Me"]
    assert names(walked) == sorted(everybody)


# The drawing order of world.js decides between two others

@needs_node
def test_the_own_name_wins_against_another_standing_lower():
    # The other one stands 3 units lower, less than OWN_IN_FRONT: the own
    # character is still drawn on top, and the own name is written.
    [drawn_frame] = drawn([
        ["start"], ["own", "Me"], players("Me", "Ann"), positions({"Me": (300, 300), "Ann": (302, 303)}), frame(),
    ])
    assert names(drawn_frame) == ["Me"]


@needs_node
def test_of_two_others_the_lower_one_drawn_on_top_wins():
    [drawn_frame] = drawn([
        ["start"], ["own", "Me"], players("Me", "Ann", "Bob"),
        positions({"Me": (100, 100), "Ann": (300, 302), "Bob": (305, 300)}), frame(),
    ])
    assert names(drawn_frame) == ["Ann", "Me"]


@needs_node
def test_walking_past_each_other_up_and_down_swaps_the_name_once():
    # Bob walks down past Ann in small steps; Ann stands. The name swaps once,
    # when Bob gets below Ann, and stays while he walks on.
    steps = [["start"], ["own", "Me"], players("Me", "Ann", "Bob"),
             positions({"Me": (100, 100), "Ann": (300, 300), "Bob": (305, 295)}), frame()]
    for bob_y in range(296, 306):
        steps += [positions({"Bob": (305, bob_y)}), frame(70)]
    frames = drawn(steps)
    shown_others = [[name for name in names(drawn_frame) if name != "Me"] for drawn_frame in frames]
    assert shown_others[0] == ["Ann"]
    assert shown_others[-1] == ["Bob"]
    changes = sum(1 for before, after in zip(shown_others, shown_others[1:]) if before != after)
    assert changes == 1
    assert all(names_do_not_overlap(drawn_frame) for drawn_frame in frames)


# A hidden name comes back only with the margin (A4)

@needs_node
def test_a_hidden_name_comes_back_only_outside_the_margin():
    # Bob stands half a unit lower than Ann, so he is drawn on top and Ann's
    # name is hidden. Then he steps sideways away from her.
    touching = THREE_LETTER_LABEL
    steps = [["start"], ["own", "Me"], players("Me", "Ann", "Bob"),
             positions({"Me": (100, 100), "Ann": (300, 300), "Bob": (310, 300.5)}), frame(),
             # clear of Ann, but inside the margin: Ann stays hidden
             positions({"Bob": (300 + touching + MARGIN - 1, 300.5)}), frame(), frame(16),
             # outside the margin: Ann is back
             positions({"Bob": (300 + touching + MARGIN + 1, 300.5)}), frame(),
             # back inside the margin but clear: Ann was shown, so she stays
             positions({"Bob": (300 + touching + 1, 300.5)}), frame()]
    covered, inside, inside_later, outside, back_inside = [names(drawn_frame) for drawn_frame in drawn(steps)]
    assert covered == ["Bob", "Me"]
    assert inside == inside_later == ["Bob", "Me"]
    assert outside == ["Ann", "Bob", "Me"]
    assert back_inside == ["Ann", "Bob", "Me"]


@needs_node
def test_a_name_hidden_by_the_own_name_needs_the_margin_too():
    # "Me" has two letters: its label is 13.4 units wide, Ann's 16.4.
    touching = (2 * 3 + 6 + 1.4 + THREE_LETTER_LABEL) / 2
    frames = drawn([
        ["start"], ["own", "Me"], players("Me", "Ann"), positions({"Me": (300, 300), "Ann": (305, 300)}), frame(),
        positions({"Ann": (300 + touching + MARGIN - 1, 300)}), frame(),
        positions({"Ann": (300 + touching + MARGIN + 1, 300)}), frame(),
    ])
    assert [names(drawn_frame) for drawn_frame in frames] == [["Me"], ["Me"], ["Ann", "Me"]]


# Leaving a lobby and joining another (play step 6)

@needs_node
def test_after_the_world_stops_nobody_counts_as_hidden_before():
    # In the first lobby Ann is hidden under Bob. The player leaves (the world
    # stops) and joins another lobby where Ann stands just clear of Bob,
    # inside the margin. Ann is a player not seen before there: her name is
    # written from the first frame.
    just_clear = {"Me": (100, 100), "Ann": (300, 300), "Bob": (300 + THREE_LETTER_LABEL + 1, 300.5)}
    first_lobby = [["start"], ["own", "Me"], players("Me", "Ann", "Bob"),
                   positions({"Me": (100, 100), "Ann": (300, 300), "Bob": (305, 300.5)}), frame()]
    in_the_same_lobby = drawn(first_lobby + [positions(just_clear), frame()])
    after_a_new_lobby = drawn(first_lobby + [
        ["stop"], ["start"], ["own", "Me"], players("Me", "Ann", "Bob"), positions(just_clear), frame(),
    ])
    assert names(in_the_same_lobby[0]) == ["Bob", "Me"]
    # Without leaving, Ann still needs the margin: this is what the test tells apart.
    assert names(in_the_same_lobby[1]) == ["Bob", "Me"]
    assert names(after_a_new_lobby[1]) == ["Ann", "Bob", "Me"]


@needs_node
def test_a_world_with_nobody_writes_no_name():
    assert drawn([["start"], ["own", "Me"], frame(), frame(16)]) == [[], []]


@needs_node
def test_a_player_omitted_from_a_full_visibility_snapshot_loses_their_name_immediately():
    initial = {"Me": (300, 300), "Ann": (350, 300)}
    frames = drawn([
        ["start"], ["own", "Me"], players("Me", "Ann"), positions(initial), frame(),
        ["snapshot", positions({"Me": (300, 300)})[1]], frame(),
        ["snapshot", positions(initial)[1]], frame(),
    ])
    assert sorted(names(frames[0])) == ["Ann", "Me"]
    assert names(frames[1]) == ["Me"]
    assert sorted(names(frames[2])) == ["Ann", "Me"]
