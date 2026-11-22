"""The soft edge of the Classic fog (S-188): only the drawing changes.

The fog fades over the outer part of the view instead of ending in a hard
edge. The server's rule is untouched: the fade uses the same range as
`positions_in_sight`, is drawn only on the map before the players, and never
gets darker than the fog outside the view.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.main import app
from server.world import visibility

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("vision_soft_edge_in_node.js")
WORLD_JS = Path(__file__).parents[1] / "client" / "js" / "world" / "world.js"
FOG = "rgba(34, 36, 54, 0.74)"

needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")


@pytest.fixture(scope="module")
def drawn():
    finished = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=30)
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def fills(result):
    return [call for call in result["calls"] if call[0] == "fill"]


# Accepted: the soft edge


@needs_node
def test_the_fade_runs_from_clear_inside_to_the_full_fog_at_the_range(drawn):
    gradients = [call for call in drawn["soft"]["calls"] if call[0] == "createRadialGradient"]
    inner = 150 * drawn["fadeFrom"]
    assert gradients == [["createRadialGradient", 486, 296, inner, 486, 296, 150]]
    assert 0 < drawn["fadeFrom"] < 1
    fade = fills(drawn["soft"])[1][2]
    # Clear where it starts, exactly the outside fog at the range: no seam,
    # and never darker than the fog itself.
    assert fade["stops"] == [[0, "rgba(34, 36, 54, 0)"], [1, FOG]]


@needs_node
def test_the_fade_fills_only_the_view_and_leaves_the_canvas_as_it_was(drawn):
    soft = drawn["soft"]
    assert [fill[1] for fill in fills(soft)] == ["evenodd", None]
    # Both fills trace the whole view polygon: the outside fog and the fade inside it.
    assert soft["lineTos"] == 2 * (soft["points"] - 1)
    assert [call for call in soft["calls"] if call[0] == "moveTo"] == [["moveTo", soft["first"]["x"], soft["first"]["y"]]] * 2
    assert not [call for call in soft["calls"] if call[0] in ("clip", "fillRect")]
    assert soft["calls"][0] == ["save"] and soft["calls"][-1] == ["restore"]
    assert soft["depthAfter"] == 0
    assert soft["fillStyleAfter"] == "#000000" and soft["globalAlphaAfter"] == 1


def test_players_sheets_and_glow_are_drawn_after_the_fog_so_the_fade_never_hides_them():
    frame = WORLD_JS.read_text(encoding="utf-8")
    darken = frame.index("vision.darken(ctx, view, sight, centre, vision.rangeOf(campus));")
    for later in ("drawBloodSheets();", "Game.world.drawStationGlow(", "drawPlayers(now);"):
        assert frame.index(later, darken) > darken, later


@needs_node
def test_fog_and_server_use_the_same_range(drawn):
    assert drawn["rangeOfCampus"] == app.state.campus["classic_vision_range"]
    assert drawn["rangeOfEmpty"] == visibility.DEFAULT_VISION_RANGE


# Edge cases: without an origin or a range the edge stays hard, as before


@needs_node
@pytest.mark.parametrize("case", ["hard", "zeroRange"])
def test_without_origin_or_range_only_the_hard_fog_is_drawn(drawn, case):
    result = drawn[case]
    assert fills(result) == [["fill", "evenodd", FOG]]
    assert not [call for call in result["calls"] if call[0] == "createRadialGradient"]
    assert result["depthAfter"] == 0
