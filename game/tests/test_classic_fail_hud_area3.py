"""WebSocket regression tests for the Free Rider's fail action and HUD state."""

import pytest

from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import ask, classic_for, start_classic


PLAYER_SETS = [
    (("Mara", "Tiago", "Ines", "Rui"), 2),
    (("Mara", "Tiago", "Ines", "Rui", "Luca"), 3),
]


def place_players(lobby, names, positions):
    for name in names:
        lobby.walkers._walkers[name].position = positions[name]


def drain_fail(connections, round_state, fr_id, target_id, final=False):
    for player_id, connection in connections.items():
        if player_id == fr_id:
            continue
        event = connection.receive_json()
        assert event["type"] == "classic_fail"
        assert event["target_id"] == target_id
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_progress"
    if not final:
        status = connections[fr_id].receive_json()
        assert status["type"] == "classic_fail_status"
        assert status["available"] is False
        assert status["in_range"] is True
        assert isinstance(status["cooldown_until"], (int, float))
    if final:
        for connection in connections.values():
            result = connection.receive_json()
            assert result["type"] == "classic_result"
            assert result["winner"] == "FR"
            assert result["reason"] == "free_riders_reached_parity"
            connection.receive_json()  # lobby_state follows the result


@pytest.mark.parametrize("names,fail_count", PLAYER_SETS)
def test_fr_fail_cooldown_and_parity_win_over_websocket(names, fail_count, connect, clock):
    connections, _code, _public, start_messages = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, names, {player: (100.0, 100.0) for player in names})

    # The round starts with the FR's ability loaded.
    assert round_state.last_fail_at == {}
    fr_statuses = [message for message in start_messages[fr_id] if message["type"] == "classic_fail_status"]
    assert fr_statuses == [{
        "type": "classic_fail_status", "available": False, "in_range": False,
        "cooldown_until": None,
    }]
    assert all(
        not any(message["type"] == "classic_fail_status" for message in messages)
        for player, messages in start_messages.items() if player != fr_id
    )

    for index in range(fail_count):
        if index:
            clock.wait(24.99)
            connections[fr_id].send_json({"type": "fail"})
            rejected = connections[fr_id].receive_json()
            assert rejected["type"] == "error"
            assert rejected["code"] == "fail_rejected"
            assert isinstance(rejected["cooldown_until"], (int, float))
            assert "second" in rejected["message"]
            assert round_state.failure_count == index
            clock.wait(0.01)

        connections[fr_id].send_json({"type": "fail"})
        success = connections[fr_id].receive_json()
        target_id = hp_ids[index]
        assert success["type"] == "classic_fail"
        assert success["target_id"] == target_id
        assert target_id in round_state.eliminated
        assert round_state.failure_count == index + 1
        assert round_state.last_fail_at[fr_id] == clock.now
        assert round_state.f_sheets
        drain_fail(connections, round_state, fr_id, target_id, final=index == fail_count - 1)


def test_no_hp_in_range_and_hp_fail_are_rejected_without_using_cooldown(connect):
    names = PLAYER_SETS[0][0]
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, names, {fr_id: (10.0, 10.0), **{hp: (100.0 + i * 10, 100.0) for i, hp in enumerate(hp_ids)}})

    hp_rejection = ask(connections[hp_ids[0]], {"type": "fail"})
    assert hp_rejection["type"] == "error"
    assert hp_rejection["code"] == "fail_rejected"

    no_target = ask(connections[fr_id], {"type": "fail"})
    assert no_target["type"] == "error"
    assert no_target["code"] == "fail_rejected"
    assert no_target["cooldown_until"] is None
    assert round_state.last_fail_at == {}
    assert round_state.failure_count == 0

    lobby.walkers._walkers[hp_ids[0]].position = (11.0, 10.0)
    retry = connections[fr_id]
    retry.send_json({"type": "fail"})
    result = retry.receive_json()
    assert result["type"] == "classic_fail"
    assert result["target_id"] == hp_ids[0]
    assert round_state.failure_count == 1


def test_fail_button_is_private_to_fr_and_q_uses_the_same_handler():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    world = (root / "client/js/world/world.js").read_text()
    main = (root / "client/js/main.js").read_text()
    assert "Durchfallen lassen" in world
    assert "ownIsFreeRider" in world
    assert 'event.code === FAIL_KEY_CODE' in world
    assert "type: 'fail'" in main or 'type: "fail"' in main
