"""WebSocket coverage for ghost visibility in Classic rounds."""

import pytest

from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic


PLAYER_SETS = [
    ("Mara", "Tiago", "Ines", "Rui"),
    ("Mara", "Tiago", "Ines", "Rui", "Luca"),
]


def receive_type(connection, expected):
    while True:
        message = connection.receive_json()
        if message["type"] == expected:
            return message
        assert message["type"] in {"classic_progress", "classic_fail_status"}


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_living_clients_do_not_receive_ghost_roster_or_position(names, connect, clock):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    ghost_id = next(player for player, role in round_state.roles.items() if role == "HP")
    lobby = app.state.lobbies.lobby_of(fr_id)
    for index, player in enumerate(names):
        lobby.walkers._walkers[player].position = (100.0 + index * 20, 100.0)
    lobby.walkers._walkers[fr_id].position = (100.0, 100.0)
    lobby.walkers._walkers[ghost_id].position = (101.0, 100.0)

    connections[fr_id].send_json({"type": "fail"})
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_fail"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"

    roster_by_player = {
        player: connection.receive_json()
        for player, connection in connections.items()
    }
    for player, roster in roster_by_player.items():
        assert roster["type"] == "classic_roster"
        roster_names = {entry["name"] for entry in roster["players"]}
        if player == ghost_id:
            assert roster_names == set(names)
            ghost_entry = next(entry for entry in roster["players"] if entry["name"] == ghost_id)
            assert ghost_entry["ghost"] is True
        else:
            assert ghost_id not in roster_names
            assert all("role" not in entry for entry in roster["players"])

    positions_by_player = {
        player: connection.receive_json()
        for player, connection in connections.items()
    }
    for player, positions in positions_by_player.items():
        assert positions["type"] == "positions"
        position_names = {entry["name"] for entry in positions["players"]}
        if player == ghost_id:
            assert position_names == set(names)
        else:
            assert ghost_id not in position_names

    station = int(round_state.tasks[ghost_id][0])
    put_at_station(ghost_id, station)
    before = round_state.progress()
    connections[ghost_id].send_json({"type": "open_station", "station": station})
    opened = receive_type(connections[ghost_id], "station_opened")
    assert opened["type"] == "station_opened"
    clock.wait(1.1)
    connections[ghost_id].send_json({"type": "finish_station"})
    assert receive_type(connections[ghost_id], "station_done") == {
        "type": "station_done", "station": station,
        "task_stations": [int(round_state.tasks[ghost_id][1])],  # S-197: the next task only
    }
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_progress"
    assert round_state.progress() > before
    assert ask(connections[ghost_id], {"type": "fail"})["code"] == "fail_rejected"
