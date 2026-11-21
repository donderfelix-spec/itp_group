"""More edge cases of drawing the map without a working character drawing (M1-1.11).

What the tester played in the browser and test_draw_without_characters.py
does not check yet:

- characters.js loaded, but Game.world.drawCharacter is not a function: the
  players are circles, as when the file is missing;
- the drawing throws a plain value instead of an Error: still a circle, one
  warning, no error;
- a drawing that failed once is not tried again on later frames;
- a player whose character failed and who then takes another character is
  drawn as that character again, without a new warning.

Uses the same Node harness (tests/world_in_node.js). Without Node these
tests are skipped; CI has Node.
"""

import json
import subprocess

from test_draw_without_characters import (
    ANA,
    BO,
    BROKEN,
    NODE,
    WORLD_IN_NODE,
    circles_in_outline_colour,
    draw_frames,
    needs_node,
    places,
)


@needs_node
def test_a_drawing_that_is_not_a_function_counts_as_missing():
    expected = draw_frames("with-characters", [ANA, BO])
    result = draw_frames("not-a-function", [ANA, BO])
    assert places(circles_in_outline_colour(result)) == places(expected["characters"])
    assert result["names"] == expected["names"]
    assert len(result["warnings"]) == 1
    assert result["errors"] == []


@needs_node
def test_a_drawing_that_throws_a_plain_value_becomes_a_circle_with_one_warning():
    expected = draw_frames("with-characters", [ANA, BROKEN, BO])
    result = draw_frames("failing-plain-value", [ANA, BROKEN, BO])
    broken = [item for item in expected["characters"] if item["character"] == "broken"]
    assert places(circles_in_outline_colour(result)) == places(broken)
    assert sorted(item["character"] for item in result["characters"]) == ["c1", "c2"]
    assert result["names"] == expected["names"]
    assert len(result["warnings"]) == 1
    assert '"broken"' in result["warnings"][0]
    assert result["errors"] == []


@needs_node
def test_a_drawing_that_failed_is_not_tried_again_on_later_frames():
    for mode in ("failing-character", "failing-nested", "failing-plain-value"):
        result = draw_frames(mode, [ANA, BROKEN, BO])
        assert result["brokenAttempts"] == 1, mode


@needs_node
def test_a_player_who_leaves_a_failing_character_is_drawn_as_the_new_one():
    changed = [
        {"name": ANA["name"], "character": ANA["character"]},
        {"name": BROKEN["name"], "character": "c3"},
        {"name": BO["name"], "character": BO["character"]},
    ]
    finished = draw_frames_with_change("failing-character", [ANA, BROKEN, BO], changed)
    assert sorted(item["character"] for item in finished["characters"]) == ["c1", "c2", "c3"]
    assert circles_in_outline_colour(finished) == []
    assert len(finished["warnings"]) == 1  # only the first failure
    assert finished["errors"] == []


def draw_frames_with_change(mode, players, changed_players, frames=60):
    """Like draw_frames, but the characters change after the first frame."""
    finished = subprocess.run(
        [NODE, str(WORLD_IN_NODE), mode],
        input=json.dumps({"players": players, "frames": frames, "changedPlayers": changed_players}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)
