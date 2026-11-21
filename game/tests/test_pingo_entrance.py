"""The wider Pingo entrance admits an ordinary player without pixel-perfect steering."""

import pytest

from server.world.campus import load_campus
from server.world.movement import is_free, step


@pytest.mark.parametrize("x", [540, 544, 548])
@pytest.mark.parametrize("start_y,direction", [(388, 1), (475, -1)])
def test_player_walks_between_gates_into_shelf_aisle_and_back(x, start_y, direction):
    campus = load_campus()
    y = start_y
    for _ in range(30):
        old_y = y
        next_x, y = step(x, y, 0, direction, 1 / 30,
                         campus["solids"], campus["width"], campus["height"])
        assert next_x == x
        assert y == pytest.approx(old_y + direction * 3)
        assert is_free(x, y, campus["solids"], campus["width"], campus["height"])


def test_pingo_gates_leave_generous_passages_for_full_size_characters():
    campus = load_campus()
    gates = sorted((s for s in campus["solids"] if s["kind"] == "turnstile"), key=lambda s: s["x"])
    assert len(gates) == 2
    for left, right in zip(gates, gates[1:]):
        assert right["x"] - left["x"] - left["w"] >= 28


@pytest.mark.parametrize("direction,start_y", [(1, 407), (-1, 436)])
def test_gate_posts_still_stop_players(direction, start_y):
    campus = load_campus()
    gate = next(s for s in campus["solids"] if s["id"] == "pingo-doce-gate-3")
    x, y = gate["x"] + gate["w"] / 2, start_y
    for _ in range(10):
        x, y = step(x, y, 0, direction, 0.1,
                    campus["solids"], campus["width"], campus["height"])
    assert y == (gate["y"] - 5 if direction == 1 else gate["y"] + gate["h"] + 5)


@pytest.mark.parametrize("x", [531, 535, 540, 544, 548, 549])
@pytest.mark.parametrize("start_y,direction", [(408, 1), (432, -1)])
def test_centered_exit_lane_allows_steering_margin(x, start_y, direction):
    campus = load_campus()
    y = start_y
    for _ in range(8):
        old_y = y
        x, y = step(x, y, 0, direction, 1 / 30,
                    campus["solids"], campus["width"], campus["height"])
        assert y == pytest.approx(old_y + direction * 3)
        assert is_free(x, y, campus["solids"], campus["width"], campus["height"])


def test_exit_lane_is_centered_on_the_door_and_its_sign():
    campus = load_campus()
    gates = sorted((s for s in campus["solids"] if s["kind"] == "turnstile"), key=lambda s: s["x"])
    door = next(d for d in campus["doors"] if d["room"] == "pingo-doce")
    sign = next(d for d in campus["decor"] if d.get("text") == "EXIT")
    lane_center = (gates[0]["x"] + gates[0]["w"] + gates[1]["x"]) / 2
    assert lane_center == door["x"] + door["w"] / 2
    assert lane_center == sign["x"] + sign["w"] / 2
