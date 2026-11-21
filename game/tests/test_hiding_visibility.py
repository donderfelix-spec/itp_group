"""Hiding is enforced before positions leave the server."""
import pytest

from server.world.campus import load_campus
from server.world.movement import is_free, step
from server.world.visibility import hiding_spot, visible_positions


@pytest.fixture
def campus():
    return load_campus()


def test_all_four_hiding_spots_are_reachable_positions(campus):
    assert len(campus["hiding_spots"]) == 4
    for spot in campus["hiding_spots"]:
        assert is_free(spot["x"], spot["y"], campus["solids"], campus["width"], campus["height"])


def test_hidden_player_does_not_reach_a_distant_viewer(campus):
    spot = campus["hiding_spots"][0]
    positions = [("viewer", 300, 300), ("hidden", spot["x"], spot["y"])]
    assert visible_positions(positions, "viewer", campus) == positions[:1]


def test_hidden_player_always_sees_their_own_position(campus):
    spot = campus["hiding_spots"][0]
    positions = [("hidden", spot["x"], spot["y"])]
    assert visible_positions(positions, "hidden", campus) == positions


@pytest.mark.parametrize("distance,visible", [(34, True), (35, True), (36, False)])
def test_reveal_range_includes_its_boundary(campus, distance, visible):
    spot = campus["hiding_spots"][0]
    positions = [("viewer", spot["x"] + distance, spot["y"]), ("hidden", spot["x"], spot["y"])]
    assert (len(visible_positions(positions, "viewer", campus)) == 2) is visible


def test_hiding_circle_includes_its_edge(campus):
    spot = campus["hiding_spots"][0]
    assert hiding_spot(campus, spot["x"] + spot["r"], spot["y"]) is spot
    assert hiding_spot(campus, spot["x"] + spot["r"] + 0.01, spot["y"]) is None


def test_leaving_hiding_reveals_player_to_distant_viewer(campus):
    spot = campus["hiding_spots"][0]
    positions = [("viewer", 300, 300), ("other", spot["x"] + spot["r"] + 1, spot["y"])]
    assert visible_positions(positions, "viewer", campus) == positions


def test_viewer_without_a_position_receives_nothing(campus):
    assert visible_positions([("other", 300, 300)], "missing", campus) == []


def test_visibility_is_recipient_specific_and_does_not_mutate_positions(campus):
    spot = campus["hiding_spots"][0]
    positions = [("far", 300, 300), ("near", spot["x"] + 20, spot["y"]), ("hidden", spot["x"], spot["y"])]
    before = list(positions)
    assert len(visible_positions(positions, "far", campus)) == 2
    assert len(visible_positions(positions, "near", campus)) == 3
    assert positions == before


def test_walking_enters_and_exits_the_hedge(campus):
    x, y = 595, 280
    for _ in range(12):
        x, y = step(x, y, 0, -1, 0.1, campus["solids"], campus["width"], campus["height"])
    assert y < 236
    assert x == 595


@pytest.mark.parametrize("key,value", [("hide_reveal_range", 0), ("hide_reveal_range", float("inf"))])
def test_invalid_reveal_range_is_rejected(campus, key, value):
    from server.world.campus import CampusError, check_campus
    campus[key] = value
    with pytest.raises(CampusError):
        check_campus(campus)


def test_hiding_inside_a_solid_is_rejected(campus):
    from server.world.campus import CampusError, check_campus
    campus["hiding_spots"][0].update(x=534, y=249)
    with pytest.raises(CampusError):
        check_campus(campus)


@pytest.mark.parametrize("radius", [0, -1, float("nan"), True])
def test_invalid_hiding_radius_is_rejected(campus, radius):
    from server.world.campus import CampusError, check_campus
    campus["hiding_spots"][0]["r"] = radius
    with pytest.raises(CampusError):
        check_campus(campus)


def test_outbound_position_messages_are_filtered_per_recipient(campus, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from server import main

    spot = campus["hiding_spots"][0]
    positions = [("far", 300, 300), ("hidden", spot["x"], spot["y"])]
    connections = {name: object() for name, _, _ in positions}
    captured = {}

    async def exercise():
        walkers = SimpleNamespace(
            positions=lambda: positions,
            names_to_tell=lambda: list(connections),
            mark_told=lambda name: None,
        )
        lobby = SimpleNamespace(walkers=walkers)
        main.app.state.campus = campus
        monkeypatch.setattr(main.app.state.sessions, "connection_of", connections.get)

        async def capture(name, connection, lobby, message):
            captured[name] = message
            main.taking_positions.discard(connection)

        monkeypatch.setattr(main, "send_positions", capture)
        main.tell_positions(lobby)
        await asyncio.gather(*list(main.background_sends))

    original_campus = main.app.state.campus
    try:
        asyncio.run(exercise())
    finally:
        main.app.state.campus = original_campus
    assert [p["name"] for p in captured["far"]["players"]] == ["far"]
    assert [p["name"] for p in captured["hidden"]["players"]] == ["far", "hidden"]
