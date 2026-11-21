"""Canteen chair groups leave usable lanes for full-size players."""
import pytest
from server.world.campus import load_campus
from server.world.movement import is_free, step


def walk(x, y, dx, dy, ticks):
    c = load_campus()
    assert is_free(x, y, c['solids'], c['width'], c['height'])
    for _ in range(ticks):
        wanted = (x + dx * 3, y + dy * 3)
        x, y = step(x, y, dx, dy, 1 / 30, c['solids'], c['width'], c['height'])
        assert (x, y) == pytest.approx(wanted)
        assert is_free(x, y, c['solids'], c['width'], c['height'])


@pytest.mark.parametrize('y', [98, 101, 104])
@pytest.mark.parametrize('reverse', [False, True])
def test_between_both_rows_with_steering_margin(y, reverse):
    walk(644 if reverse else 488, y, -1 if reverse else 1, 0, 52)


@pytest.mark.parametrize('x', [532, 536, 540, 589, 593, 597])
@pytest.mark.parametrize('reverse', [False, True])
def test_between_columns_with_steering_margin(x, reverse):
    walk(x, 149 if reverse else 53, 0, -1 if reverse else 1, 32)


def test_door_connects_to_cross_aisle_around_middle_table():
    walk(565, 179, 0, -1, 10)
    walk(565, 149, 1, 0, 9)
    walk(592, 149, 0, -1, 16)
