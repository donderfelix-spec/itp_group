"""The map still draws when the character drawing is missing or fails (M1-1.11).

If characters.js does not load, or its drawing fails for a character, the
map must keep working: every player is drawn as a plain circle instead, the
names are shown as usual, and the console gets one warning in total instead
of an error on every frame.

The page's own draw.js and world.js run in Node (tests/world_in_node.js)
with a canvas that writes down what is drawn and where on the screen.
Without Node these tests are skipped; CI has Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

WORLD_IN_NODE = Path(__file__).resolve().parent / "world_in_node.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

OUTLINE = "#2E2A3B"  # the outline colour of DESIGN.md; the circles are drawn in it
FRAMES = 300  # about 5 seconds at 60 frames per second

ANA = {"name": "Ana", "character": "c1", "x": 486, "y": 296}
BO = {"name": "Bo", "character": "c2", "x": 520, "y": 300}
BROKEN = {"name": "Cy", "character": "broken", "x": 450, "y": 310}


def draw_frames(mode, players, frames=FRAMES):
    """Runs the world for `frames` frames and returns what the last one drew."""
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE), mode],
        input=json.dumps({"players": players, "frames": frames}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def places(drawn):
    """The screen places (x, y) of drawn characters or circles, rounded."""
    return sorted((round(item["x"], 3), round(item["y"], 3)) for item in drawn)


def circles_in_outline_colour(result):
    return [circle for circle in result["standIns"] if circle["colour"] == OUTLINE]


# Accepted: with characters.js nothing changes


@needs_node
def test_with_characters_every_player_is_drawn_as_a_character_and_nothing_is_logged():
    result = draw_frames("with-characters", [ANA, BO])
    assert sorted(item["character"] for item in result["characters"]) == ["c1", "c2"]
    assert circles_in_outline_colour(result) == []
    assert result["warnings"] == []
    assert result["errors"] == []


# Rejected drawing: characters.js is missing


@needs_node
def test_without_characters_the_frames_run_without_errors_and_warn_only_once():
    result = draw_frames("without-characters", [ANA, BO])
    assert result["errors"] == []
    assert len(result["warnings"]) == 1


@needs_node
def test_without_characters_every_player_is_a_circle_where_the_character_would_be():
    expected = draw_frames("with-characters", [ANA, BO])
    result = draw_frames("without-characters", [ANA, BO])
    assert places(circles_in_outline_colour(result)) == places(expected["characters"])


@needs_node
def test_without_characters_the_names_are_drawn_in_the_same_places():
    expected = draw_frames("with-characters", [ANA, BO])
    result = draw_frames("without-characters", [ANA, BO])
    assert result["names"] == expected["names"]


# Edge cases: the drawing fails for one character only


@needs_node
def test_a_failing_character_becomes_a_circle_and_the_others_stay_characters():
    expected = draw_frames("with-characters", [ANA, BROKEN, BO])
    result = draw_frames("failing-character", [ANA, BROKEN, BO])
    broken_place = [(item["x"], item["y"]) for item in expected["characters"] if item["character"] == "broken"]
    assert places(circles_in_outline_colour(result)) == places(
        [{"x": x, "y": y} for x, y in broken_place]
    )
    assert sorted(item["character"] for item in result["characters"]) == ["c1", "c2"]


@needs_node
def test_a_drawing_that_fails_halfway_does_not_move_the_others_or_the_names():
    # The failing drawing has already moved and scaled the canvas when it
    # fails. The players after it and all names must still be in place.
    expected = draw_frames("with-characters", [ANA, BROKEN, BO])
    result = draw_frames("failing-character", [ANA, BROKEN, BO])
    others = [item for item in expected["characters"] if item["character"] != "broken"]
    assert places(result["characters"]) == places(others)
    assert result["names"] == expected["names"]


@needs_node
def test_a_failing_character_gives_one_warning_and_no_errors_over_many_frames():
    result = draw_frames("failing-character", [ANA, BROKEN, BO])
    assert result["errors"] == []
    assert len(result["warnings"]) == 1


@needs_node
def test_a_single_frame_without_characters_already_draws_the_circles():
    result = draw_frames("without-characters", [ANA], frames=1)
    assert len(circles_in_outline_colour(result)) == 1
    assert [name["text"] for name in result["names"]] == ["Ana"]
