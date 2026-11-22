import pytest

from server.world.visibility import positions_in_sight


VIEWER = ("viewer", 0, 0)
WALL = {"kind": "wall", "x": 20, "y": -10, "w": 5, "h": 20}


@pytest.mark.parametrize(
    ("position", "visible"),
    [
        ((-150, 0), True),
        ((-150.01, 0), False),
        ((19, 0), True),
        ((50, 0), False),
        ((50, 40), True),  # the opening beyond the end of the wall
        ((50, 25), False),  # the line touches the wall's corner
        ((0, 120), True),  # a ray parallel to the wall's face
    ],
)
def test_sight_stops_at_its_range_and_opaque_walls(position, visible):
    target = ("target", *position)
    entries = [VIEWER, target]
    campus = {"classic_vision_range": 150, "solids": [WALL]}
    assert positions_in_sight(entries, "viewer", campus) == ([VIEWER, target] if visible else [VIEWER])
    assert entries == [VIEWER, target]


def test_furniture_does_not_block_sight():
    target = ("target", 50, 0)
    campus = {"solids": [{**WALL, "kind": "table"}]}
    assert positions_in_sight([VIEWER, target], "viewer", campus) == [VIEWER, target]


def test_no_positions_are_disclosed_before_the_viewer_is_placed():
    assert positions_in_sight([VIEWER], "not placed", {"solids": []}) == []
