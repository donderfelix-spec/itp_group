"""Server-level Classic behavior for tasks, fails, roles and four-player starts."""

from collections import Counter

import pytest

from server import main, protocol
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station  # noqa: F401


PASSWORD = "password123"
STATIONS = {station["id"]: station for station in app.state.campus["stations"]}


def ask(connection, message):
    connection.send_json(message)
    return connection.receive_json()


def player(connect, name):
    connection = connect()
    assert ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def start_classic(connect, names=("Mara", "Tiago", "Ines", "Rui")):
    connections = {name: player(connect, name) for name in names}
    public_messages = [ask(connections[names[0]], {"type": "create_lobby"})]
    code = public_messages[0]["code"]
    for index, name in enumerate(names[1:], start=1):
        public_messages.append(ask(connections[name], {"type": "join_lobby", "code": code}))
        public_messages.extend(connections[previous].receive_json() for previous in names[:index])

    public_messages.append(ask(connections[names[0]], {"type": "choose_mode", "mode": "classic"}))
    public_messages.extend(connections[name].receive_json() for name in names[1:])
    public_messages.append(ask(connections[names[0]], {"type": "start_game"}))
    public_messages.extend(connections[name].receive_json() for name in names[1:])

    start_messages = {}
    for name, connection in connections.items():
        received = []
        while True:
            message = connection.receive_json()
            received.append(message)
            if message["type"] == "classic_progress":
                break
        start_messages[name] = received
    return connections, code, public_messages, start_messages


def put_at_station(name, station_id):
    station = STATIONS[station_id]
    lobby = app.state.lobbies.lobby_of(name)
    lobby.walkers._walkers[name].position = (float(station["x"]), float(station["y"]))


def classic_for(name):
    return app.state.lobbies.lobby_of(name).classic_round


def test_classic_starts_with_four_players_one_fr_three_hp_and_twelve_real_tasks(connect):
    connections, _code, _public, _start_messages = start_classic(connect)
    round_state = classic_for("Mara")

    assert len(connections) == 4
    assert Counter(round_state.roles.values()) == {"FR": 1, "HP": 3}
    assert sum(len(round_state.tasks[player]) for player, role in round_state.roles.items() if role == "HP") == 12


def test_classic_does_not_start_with_three_players(connect):
    connections = {name: player(connect, name) for name in ("Mara", "Tiago", "Ines")}
    code = ask(connections["Mara"], {"type": "create_lobby"})["code"]
    ask(connections["Tiago"], {"type": "join_lobby", "code": code})
    connections["Mara"].receive_json()
    ask(connections["Ines"], {"type": "join_lobby", "code": code})
    for name in ("Mara", "Tiago"):
        connections[name].receive_json()
    ask(connections["Mara"], {"type": "choose_mode", "mode": "classic"})
    for name in ("Tiago", "Ines"):
        connections[name].receive_json()

    assert ask(connections["Mara"], {"type": "start_game"}) == {
        "type": "error",
        "code": "too_few_players",
        "message": "Classic needs at least 4 players.",
    }


def test_free_rider_cannot_open_or_finish_a_minigame_and_hp_task_advances_progress(connect, clock):
    connections, _code, _public, _start_messages = start_classic(connect)
    round_state = classic_for("Mara")
    fr_id = next(name for name, role in round_state.roles.items() if role == "FR")
    hp_id = next(name for name, role in round_state.roles.items() if role == "HP")

    fr_station = int(round_state.tasks[fr_id][0])
    put_at_station(fr_id, fr_station)
    expected_rejection = protocol.rejection("fr_cannot_task")
    assert ask(connections[fr_id], {"type": "open_station", "station": fr_station}) == expected_rejection
    assert ask(connections[fr_id], {"type": "finish_station"}) == expected_rejection
    assert round_state.progress() == 0.0

    hp_station = int(round_state.tasks[hp_id][0])
    put_at_station(hp_id, hp_station)
    opened = ask(connections[hp_id], {"type": "open_station", "station": hp_station})
    assert opened["type"] == "station_opened"
    clock.wait(1.1)
    assert ask(connections[hp_id], {"type": "finish_station"}) == {
        "type": "station_done", "station": hp_station,
    }
    assert round_state.progress() == pytest.approx(1 / 12)


def test_only_free_rider_can_fail_and_fail_cooldown_is_checked_by_server(connect, clock):
    connections, _code, _public, _start_messages = start_classic(connect)
    round_state = classic_for("Mara")
    fr_id = next(name for name, role in round_state.roles.items() if role == "FR")
    hp_ids = [name for name, role in round_state.roles.items() if role == "HP"]
    for name in (fr_id, *hp_ids):
        put_at_station(name, 1)

    assert ask(connections[hp_ids[0]], {"type": "fail"}) == protocol.rejection("fail_rejected")
    result = ask(connections[fr_id], {"type": "fail"})
    assert result["type"] == "classic_fail"
    assert len(round_state.eliminated) == 1
    assert round_state.eliminated <= set(hp_ids)

    assert connections[fr_id].receive_json()["type"] == "classic_progress"
    for player_id, connection in connections.items():
        if player_id == fr_id:
            continue
        assert connection.receive_json()["type"] == "classic_fail"
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"

    clock.wait(24.99)
    cooldown_rejection = ask(connections[fr_id], {"type": "fail"})
    assert cooldown_rejection["type"] == "error"
    assert cooldown_rejection["code"] == "fail_rejected"
    assert isinstance(cooldown_rejection["cooldown_until"], (int, float))
    assert "second" in cooldown_rejection["message"]
    assert len(round_state.eliminated) == 1


def test_role_debug_output_requires_debug_roles_environment_variable(connect, monkeypatch, capsys):
    monkeypatch.setenv("DEBUG_ROLES", "1")
    _connections, _code, _public, _start_messages = start_classic(connect)
    output = capsys.readouterr().out
    assert "Classic roles:" in output
    assert "FR" in output and "HP" in output


def test_role_debug_output_is_silent_without_debug_roles(connect, monkeypatch, capsys):
    monkeypatch.delenv("DEBUG_ROLES", raising=False)
    start_classic(connect)
    assert "Classic roles:" not in capsys.readouterr().out


def test_only_free_rider_receives_marker_and_public_lobby_states_hide_roles(connect):
    connections, _code, public_messages, start_messages = start_classic(connect)
    roles = {name: classic_for(name).roles[name] for name in connections}
    free_riders = {name for name, role in roles.items() if role == "FR"}

    lobby_states = [message for message in public_messages if message.get("type") == "lobby_state"]
    assert lobby_states
    assert all("role" not in player for state in lobby_states for player in state["players"])
    assert all("roles" not in state for state in lobby_states)
    for name, messages in start_messages.items():
        markers = [message for message in messages if message["type"] == "you_are_fr"]
        if name in free_riders:
            assert markers == [{"type": "you_are_fr"}]
        else:
            assert markers == []
