"""Full-size players can traverse every lecture row gap and the cafe aisles."""
import pytest
from server.world.campus import load_campus
from server.world.movement import is_free, step


def walk(start, direction, ticks):
    campus = load_campus()
    x, y = start
    assert is_free(x, y, campus['solids'], campus['width'], campus['height'])
    for _ in range(ticks):
        old_x, old_y = x, y
        x, y = step(x, y, *direction, 1 / 30, campus['solids'], campus['width'], campus['height'])
        assert (x, y) == pytest.approx((old_x + direction[0] * 3, old_y + direction[1] * 3))
        assert is_free(x, y, campus['solids'], campus['width'], campus['height'])


@pytest.mark.parametrize('y', [70, 73, 76, 100, 103, 106, 130, 133, 136])
@pytest.mark.parametrize('reverse', [False, True])
def test_every_lecture_row_gap_can_be_walked_across(y, reverse):
    walk((215 if reverse else 35, y), (-1 if reverse else 1, 0), 60)


@pytest.mark.parametrize('x', [35, 215])
@pytest.mark.parametrize('reverse', [False, True])
def test_lecture_side_aisles_connect_all_rows(x, reverse):
    walk((x, 158 if reverse else 50), (0, -1 if reverse else 1), 36)


@pytest.mark.parametrize('y', [106, 109, 112])
@pytest.mark.parametrize('reverse', [False, True])
def test_cafe_cross_aisle_has_steering_room(y, reverse):
    walk((413 if reverse else 287, y), (-1 if reverse else 1, 0), 42)


@pytest.mark.parametrize('x', [290, 410])
@pytest.mark.parametrize('reverse', [False, True])
def test_cafe_side_aisles_connect_front_and_back(x, reverse):
    walk((x, 155 if reverse else 59), (0, -1 if reverse else 1), 32)


@pytest.mark.parametrize('x,direction', [(290, 1), (410, -1)])
def test_cafe_door_connects_to_both_side_aisles(x, direction):
    walk((350, 179), (0, -1), 8)
    walk((350, 155), (-direction, 0), 20)
    walk((x, 155), (0, -1), 32)
