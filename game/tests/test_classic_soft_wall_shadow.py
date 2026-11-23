"""Soft wall shadows in the Classic fog, and players drawn whole (S-214, M3-1.9).

Felix on 2026-11-23, with a picture of the Main Deck: "Fix the shadow." The
wall `corridor-wall-2` cast a hard, flat grey wedge, unlike the soft edge of
the view elsewhere (S-188), and a player at the edge of that wedge was cut
in two by the same hard line.

Only the drawing changes: `vision.darkenSoftly`, beside the unchanged
`vision.darken`, asks nine points of sight (the player's centre and eight
points 4 units around it) what they see, so a wall's shadow fades in over a
band before the server's sight line; everything the server hides keeps the
full fog. Players are drawn after the clip, whole. The server's rule
(`place_in_sight`, S-185) is untouched.
"""

import json
import math
import re
import subprocess
from pathlib import Path

import pytest

from server.main import app
from server.world import movement
from server.world.visibility import place_in_sight
from test_classic_vision_soft_edge import NODE, needs_node
from test_play_campus_detail import node_environment
from test_play_classic_task_card_end_to_end import needs_chromium

TESTS = Path(__file__).parent
WORLD_JS = TESTS.parent / "client" / "js" / "world" / "world.js"
FULL_FOG_ALPHA = round(0.6 * 255)  # S-193
FOG_RGB = [34, 36, 54]

# Felix's place (deck, just below the canteen wall, right of the low
# corridor wall) and the right end of that wall, where the wedge starts.
VIEWER = (505.0, 248.0)
WALL_CORNER = (476.0, 227.0)


def _run_node(places=()):
    finished = subprocess.run(
        [NODE, str(TESTS / "soft_wall_shadow_in_node.js")],
        input=json.dumps({"places": [list(place) for place in places]}),
        capture_output=True, text=True, timeout=60,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def _places_beside_walls():
    """Every place on a 1-unit grid within 7 units of a wall where a player may stand."""
    campus = app.state.campus
    walls = [solid for solid in campus["solids"] if solid["kind"] == "wall"]
    places = set()
    for wall in walls:
        for x in range(int(wall["x"]) - 7, int(wall["x"] + wall["w"]) + 8):
            for y in range(int(wall["y"]) - 7, int(wall["y"] + wall["h"]) + 8):
                if movement.is_free(x, y, campus["solids"], campus["width"], campus["height"]):
                    places.add((x, y))
    return sorted(places)


def _strictly_inside(point, wall):
    return wall["x"] < point["x"] < wall["x"] + wall["w"] and wall["y"] < point["y"] < wall["y"] + wall["h"]


# The points of sight


@needs_node
def test_the_points_of_sight_are_the_centre_and_a_ring_closer_than_any_wall():
    places = _places_beside_walls()
    assert len(places) > 1000
    drawn = _run_node(places)
    # A player keeps half his square from every wall, so the ring stays on his side.
    assert 0 < drawn["radius"] < movement.PLAYER_HALF_SIZE
    walls = [solid for solid in app.state.campus["solids"] if solid["kind"] == "wall"]
    for (x, y), points in zip(places, drawn["points"]):
        assert points[0] == {"x": x, "y": y}
        assert len(points) == 9
        for point in points[1:]:
            assert math.dist((x, y), (point["x"], point["y"])) == pytest.approx(drawn["radius"])
        stray = [point for point in points for wall in walls if _strictly_inside(point, wall)]
        assert stray == [], (x, y)


@needs_node
def test_without_a_document_nothing_is_drawn_and_the_hard_fog_is_the_fallback():
    drawn = _run_node()
    assert drawn["noDocument"] == {"answer": False, "calls": []}
    frame = WORLD_JS.read_text(encoding="utf-8")
    assert re.search(
        r"if \(!vision\.darkenSoftly\(ctx, view, campus, centre\)\) \{\s*"
        r"vision\.darken\(ctx, view, sight, centre, vision\.rangeOf\(campus\)\);",
        frame,
    )


@needs_node
def test_the_soft_fog_counts_the_points_of_sight_that_see_and_keeps_the_range_fade():
    soft = _run_node()["soft"]
    log = soft["log"]
    assert soft["answer"] is True
    # Each point's view is added with an alpha of 1/9 (and one 8-bit step,
    # against rounding): the share that sees.
    shares = [args for canvas, call, args, state in log
              if canvas == "layer" and call == "fill" and state == ["lighter", pytest.approx(1 / 9 + 1 / 255)]]
    assert len(shares) == 9
    # Outside the centre's own view the full shade (like darken), then the
    # range fade of S-188, centred on the player, with the same range.
    outside = [args for canvas, call, args, state in log
               if canvas == "fog" and call == "fill" and args[0] == "evenodd"]
    assert outside == [["evenodd", "rgba(34, 36, 54, 1)"]]
    gradients = [args for canvas, call, args, _ in log if call == "createRadialGradient"]
    assert gradients == [[*VIEWER, 120 * 0.6, *VIEWER, 120]]
    # In the fog's colour, drawn at the fog's alpha (S-193).
    recolour = [state for canvas, call, args, state in log
                if canvas == "fog" and call == "fill" and args[1] == "rgb(34, 36, 54)"]
    assert recolour == [["source-in", 1]]


@needs_node
def test_the_soft_fog_covers_the_whole_view_and_leaves_the_canvas_as_it_was():
    soft = _run_node()["soft"]
    view = soft["view"]
    onto_main = [args for canvas, call, args, _ in soft["log"] if canvas == "main" and call == "drawImage"]
    assert len(onto_main) == 1
    image, x, y, w, h, smoothing = onto_main[0]
    assert image == "smooth" and smoothing is False
    assert x <= view["x"] and y <= view["y"]
    assert x + w >= view["x"] + view["w"] and y + h >= view["y"] + view["h"]
    main_calls = [(call, state) for canvas, call, _, state in soft["log"] if canvas == "main"]
    assert [call for call, _ in main_calls] == ["save", "drawImage", "restore"]
    assert main_calls[1][1] == ["source-over", 0.6]
    assert soft["mainDepth"] == 0 and soft["mainSmoothing"] is True


# Players are drawn whole


def test_players_and_names_are_drawn_after_the_clip_is_lifted():
    frame = WORLD_JS.read_text(encoding="utf-8")
    start = frame.index("function drawFrame(now)")
    body = frame[start:frame.index("\n  }\n", start)]
    fog = body.index("vision.darkenSoftly(")
    clip = body.index("vision.clip(ctx, sight);")
    lifted = body.index("if (sight) ctx.restore();")
    players = body.index("drawPlayers(now);")
    assert fog < clip < lifted < players
    # Sheets, the station glow and the arrow stay inside the view.
    for clipped in ("drawBloodSheets();", "drawStationGlow(", "Game.taskNavigation.draw("):
        assert clip < body.index(clipped) < lifted, clipped


# The drawn fog in Chromium, at Felix's place


def _across_the_shadow_line():
    """Points on a line across the shadow's edge, 20 units behind the wall's end."""
    span = math.dist(VIEWER, WALL_CORNER)
    away = ((WALL_CORNER[0] - VIEWER[0]) / span, (WALL_CORNER[1] - VIEWER[1]) / span)
    lit_side = (-away[1], away[0])
    edge = (WALL_CORNER[0] + 20 * away[0], WALL_CORNER[1] + 20 * away[1])
    return {f"t{t}": [edge[0] + t * lit_side[0], edge[1] + t * lit_side[1]] for t in range(6, -7, -1)}


POINTS = {
    "centre": list(VIEWER),
    "wedge": [420, 218],  # deep in the wall's shadow
    "open": [540, 250],  # clear floor in sight
    "beyond": [630, 248],  # past the range, no wall between
    **_across_the_shadow_line(),
}


def _draw_in_chromium(origin, points):
    request = json.dumps({"origin": list(origin), "points": points})
    finished = subprocess.run(
        [NODE, str(TESTS / "soft_wall_shadow_in_browser.js"), request],
        env=node_environment(), capture_output=True, text=True, timeout=120,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


@pytest.fixture(scope="module")
def fog():
    return _draw_in_chromium(VIEWER, POINTS)


# Right beside the end of the same wall, the ring of sight points looks far
# round the corner (the reviewer's case): those places must stay dark.
BESIDE_THE_CORNER = (481.0, 238.0)
ROUND_THE_CORNER = {f"p{i}": place for i, place in enumerate(
    [[458, 188], [452, 176], [452, 182], [458, 194], [464, 206], [470, 218], [446, 200]]
)}


@pytest.fixture(scope="module")
def corner():
    return _draw_in_chromium(BESIDE_THE_CORNER, ROUND_THE_CORNER)


def test_the_chosen_points_lie_where_the_server_says():
    campus = app.state.campus
    assert place_in_sight(VIEWER, POINTS["open"], campus)
    for hidden in ("wedge", "beyond"):
        assert not place_in_sight(VIEWER, POINTS[hidden], campus), hidden
    line = _across_the_shadow_line()
    assert all(place_in_sight(VIEWER, line[f"t{t}"], campus) for t in range(1, 7))
    assert not any(place_in_sight(VIEWER, line[f"t{t}"], campus) for t in range(-1, -7, -1))


@needs_chromium
def test_away_from_the_edge_the_soft_fog_is_the_old_fog(fog):
    assert fog["soft"]["answer"] is True
    for name in ("centre", "open", "beyond", "wedge"):
        soft, hard = fog["soft"]["pixels"][name], fog["hard"]["pixels"][name]
        assert abs(soft[3] - hard[3]) <= 4, (name, soft, hard)
    assert fog["soft"]["pixels"]["centre"][3] == 0
    assert fog["soft"]["pixels"]["open"][3] == 0
    for name in ("wedge", "beyond"):
        pixel = fog["soft"]["pixels"][name]
        assert abs(pixel[3] - FULL_FOG_ALPHA) <= 3, name
        assert all(abs(a - b) <= 2 for a, b in zip(pixel[:3], FOG_RGB)), name


@needs_chromium
def test_the_wall_shadow_fades_in_softly_before_the_servers_line(fog):
    names = [f"t{t}" for t in range(6, -7, -1)]  # from the lit side into the shadow
    hard = [fog["hard"]["pixels"][name][3] for name in names]
    soft = [fog["soft"]["pixels"][name][3] for name in names]
    # Before: a hard step from clear to the full fog (t0 lies on the line
    # itself, where the canvas smooths the polygon's edge by one pixel).
    assert all(alpha in (0, FULL_FOG_ALPHA) for name, alpha in zip(names, hard) if name != "t0")
    # After: it darkens steadily, with several steps in between, all on the
    # side the server lets the player see ...
    assert all(later >= earlier - 3 for earlier, later in zip(soft, soft[1:])), soft
    assert soft[0] <= 10, soft
    lit_side = [fog["soft"]["pixels"][f"t{t}"] for t in range(1, 7)]
    assert len([pixel for pixel in lit_side if 20 < pixel[3] < FULL_FOG_ALPHA - 20]) >= 2, soft
    for pixel in lit_side:
        if pixel[3] > 20:
            assert all(abs(a - b) <= 3 for a, b in zip(pixel[:3], FOG_RGB)), pixel
    # ... and everything the server hides keeps the full fog.
    for t in range(-1, -7, -1):
        assert fog["soft"]["pixels"][f"t{t}"][3] >= FULL_FOG_ALPHA - 3, soft


def test_the_places_round_the_corner_are_hidden_by_the_server():
    for name, place in ROUND_THE_CORNER.items():
        assert not place_in_sight(BESIDE_THE_CORNER, place, app.state.campus), name


@needs_chromium
def test_beside_a_wall_end_nothing_round_the_corner_looks_visible(corner):
    # Before this check the soft band was centred on the line and these
    # places got about half the fog (p0: 78 of 153). p0 lies 0.3 units from
    # the line, where the smooth scaling softens the edge by one unit.
    for name, pixel in corner["soft"]["pixels"].items():
        assert pixel[3] >= FULL_FOG_ALPHA - 6, (name, pixel)


@needs_chromium
def test_the_soft_fog_is_never_darker_than_the_full_fog(fog, corner):
    assert fog["soft"]["darkest"] <= FULL_FOG_ALPHA + 2
    assert corner["soft"]["darkest"] <= FULL_FOG_ALPHA + 2
