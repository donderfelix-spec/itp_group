"""WebSocket coverage for reporting sheets and calling emergency meetings."""

import json

import pytest

from server import protocol
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import ask, classic_for, start_classic


PLAYER_SETS = [
    ("Mara", "Tiago", "Ines", "Rui"),
    ("Mara", "Tiago", "Ines", "Rui", "Luca"),
]


def failed_sheet(names, connect, clock):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    for player in names:
        lobby.walkers._walkers[player].position = (100.0, 100.0)

    connections[fr_id].send_json({"type": "fail"})
    fail_message = connections[fr_id].receive_json()
    assert fail_message["type"] == "classic_fail"
    for player, connection in connections.items():
        if player != fr_id:
            event = connection.receive_json()
            assert event["type"] == "classic_fail"
            assert event["target_id"] == fail_message["target_id"]
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_roster"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "positions"

    ghost_id = fail_message["target_id"]
    reporter_id = next(player for player in hp_ids if player != ghost_id)
    sheet_position = fail_message["position"]
    lobby.walkers._walkers[reporter_id].position = (
        sheet_position["x"], sheet_position["y"]
    )
    return connections, round_state, lobby, fr_id, ghost_id, reporter_id, sheet_position


def receive_broadcast(connections, expected_type):
    messages = {player: connection.receive_json() for player, connection in connections.items()}
    assert all(message["type"] == expected_type for message in messages.values())
    assert len({json.dumps(message, sort_keys=True) for message in messages.values()}) == 1
    return next(iter(messages.values()))


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_report_message_starts_meeting_and_websocket_scenario_a_wins_for_hp(names, connect, clock):
    connections, round_state, lobby, fr_id, ghost_id, reporter_id, position = failed_sheet(
        names, connect, clock
    )
    sheet_id = next(iter(round_state.f_sheets))

    connections[ghost_id].send_json({
        "type": "report", "sheet_id": sheet_id, "position": position,
    })
    assert connections[ghost_id].receive_json()["code"] == "report_rejected"

    connections[reporter_id].send_json({
        "type": "report", "sheet_id": sheet_id, "position": position,
    })
    meeting = receive_broadcast(connections, "meeting_state")
    assert meeting["phase"] == "discussion"
    assert ghost_id in meeting["ghosts"]
    assert sheet_id in round_state.f_sheets
    assert round_state.meeting["reason"] == "report"

    connections[reporter_id].send_json({"type": "chat", "text": "I found the sheet."})
    chat_state = receive_broadcast(connections, "meeting_state")
    assert chat_state["messages"] == [
        {"player_id": reporter_id, "text": "I found the sheet."}
    ]

    clock.wait(45.0)
    living = [player for player in names if player != ghost_id]
    for player in living:
        target = fr_id if player != fr_id else reporter_id
        connections[player].send_json({"type": "vote", "target_id": target})
        vote_state = receive_broadcast(connections, "meeting_state")
        assert vote_state["phase"] == "voting"
        assert "votes" not in vote_state

    clock.wait(30.0)
    connections[reporter_id].send_json({"type": "vote", "target_id": fr_id})
    assert connections[reporter_id].receive_json()["code"] == "vote_rejected"
    final_meeting = receive_broadcast(connections, "meeting_state")
    assert final_meeting["phase"] == "result"
    assert final_meeting["ejected_id"] == fr_id
    assert final_meeting["revealed_role"] == "FR"
    assert final_meeting["winner"] == "HP"

    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_roster"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "positions"

    results = {player: connection.receive_json() for player, connection in connections.items()}
    assert all(result["type"] == "classic_result" for result in results.values())
    assert all(result["winner"] == "HP" for result in results.values())
    assert all(result["reason"] == "all_free_riders_eliminated" for result in results.values())
    assert all(result["roles"][fr_id] == "FR" for result in results.values())


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_emergency_is_living_only_once_per_player_and_chat_vote_reach_all(names, connect, clock):
    connections, round_state, lobby, _fr_id, ghost_id, reporter_id, _position = failed_sheet(
        names, connect, clock
    )
    clock.wait(45.0)
    connections[ghost_id].send_json({"type": "emergency"})
    assert connections[ghost_id].receive_json()["code"] == "emergency_rejected"

    connections[reporter_id].send_json({"type": "emergency"})
    first_meeting = receive_broadcast(connections, "meeting_state")
    assert first_meeting["phase"] == "discussion"
    assert round_state.meeting["reason"] == "emergency"

    connections[reporter_id].send_json({"type": "emergency"})
    assert connections[reporter_id].receive_json()["code"] == "emergency_rejected"

    connections[reporter_id].send_json({"type": "chat", "text": "Emergency meeting."})
    chat_state = receive_broadcast(connections, "meeting_state")
    assert chat_state["messages"][-1]["player_id"] == reporter_id

    clock.wait(45.0)
    living = [player for player in names if player != ghost_id]
    if len(living) == 3:
        targets = [living[1], living[2], living[0]]
    else:
        targets = [living[1], living[0], living[0], living[1]]
    for player, target in zip(living, targets):
        connections[player].send_json({"type": "vote", "target_id": target})
        receive_broadcast(connections, "meeting_state")
    clock.wait(30.0)
    connections[reporter_id].send_json({"type": "vote", "target_id": reporter_id})
    assert connections[reporter_id].receive_json()["code"] == "vote_rejected"
    final_meeting = receive_broadcast(connections, "meeting_state")
    assert final_meeting["phase"] == "result"
    assert round_state.meeting_count == 1

    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_roster"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "positions"

    # The completed meeting returns to play; one other living player can still call once.
    another_living = next(player for player in living if player != reporter_id)
    connections[reporter_id].send_json({"type": "emergency"})
    assert connections[reporter_id].receive_json()["code"] == "emergency_rejected"
    connections[another_living].send_json({"type": "emergency"})
    second_meeting = receive_broadcast(connections, "meeting_state")
    assert second_meeting["phase"] == "discussion"


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_emergency_button_unlocks_at_45_seconds_from_round_start(names, connect, clock):
    connections, round_state, _lobby, fr_id, ghost_id, reporter_id, _position = failed_sheet(
        names, connect, clock
    )
    clock.wait(44.99)
    connections[reporter_id].send_json({"type": "emergency"})
    rejected = connections[reporter_id].receive_json()
    assert rejected["type"] == "error"
    assert rejected["code"] == "emergency_rejected"
    assert "second" in rejected["message"]
    assert round_state.meeting is None

    clock.wait(0.01)
    connections[reporter_id].send_json({"type": "emergency"})
    meeting = receive_broadcast(connections, "meeting_state")
    assert meeting["reason"] == "emergency"
    assert meeting["trigger_player_id"] == reporter_id

    connections[reporter_id].send_json({"type": "emergency"})
    assert connections[reporter_id].receive_json()["code"] == "emergency_rejected"
    connections[ghost_id].send_json({"type": "emergency"})
    assert connections[ghost_id].receive_json()["code"] == "emergency_rejected"
    assert round_state.meeting["reason"] == "emergency"


def test_protocol_accepts_report_with_sheet_position_and_emergency_without_fields():
    report = {
        "type": "report",
        "sheet_id": "f-sheet-1",
        "position": {"x": 12.5, "y": 30.0},
    }
    assert protocol.parse_client_message(json.dumps(report)) == report
    assert protocol.parse_client_message('{"type":"emergency"}') == {"type": "emergency"}


def test_client_wires_report_and_emergency_keys_to_server_actions():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    world = (root / "client/js/world/world.js").read_text()
    main = (root / "client/js/main.js").read_text()
    assert "KeyR" in world
    assert "type: 'report'" in main or 'type: "report"' in main
    assert "type: 'emergency'" in main or 'type: "emergency"' in main
