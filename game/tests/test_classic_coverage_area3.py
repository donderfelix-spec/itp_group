"""Additional Classic rule coverage for nearest-target selection and end-to-end tasks."""

import pytest

from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic


PLAYER_SETS = [
    ("Mara", "Tiago", "Ines", "Rui"),
    ("Mara", "Tiago", "Ines", "Rui", "Luca"),
]


def drain_fail_result(connections, fr_id, expected_target, final=False):
    for player_id, connection in connections.items():
        if player_id == fr_id:
            continue  # The caller already read its own classic_fail response.
        message = connection.receive_json()
        assert message["type"] == "classic_fail"
        assert message["target_id"] == expected_target
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"
    for connection in connections.values():
        while True:
            message = connection.receive_json()
            if message["type"] == "classic_roster":
                break
            assert message["type"] == "classic_fail_status"
    for connection in connections.values():
        assert connection.receive_json()["type"] == "positions"
    if final:
        for connection in connections.values():
            result = connection.receive_json()
            assert result["type"] == "classic_result"
            assert result["winner"] == "FR"
            assert result["reason"] == "free_riders_reached_parity"
            connection.receive_json()  # lobby_state after the result


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_classic_q_selects_the_nearest_living_hp(names, connect):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    lobby.walkers._walkers[fr_id].position = (0.0, 0.0)
    for index, player in enumerate(hp_ids):
        lobby.walkers._walkers[player].position = (float(index + 1), 0.0)

    connections[fr_id].send_json({"type": "fail"})
    event = connections[fr_id].receive_json()

    assert event["type"] == "classic_fail"
    assert event["target_id"] == hp_ids[0]
    assert hp_ids[0] in round_state.eliminated
    for player, connection in connections.items():
        if player != fr_id:
            assert connection.receive_json()["type"] == "classic_fail"
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_classic_q_distance_tie_uses_lobby_join_order(names, connect):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    lobby.walkers._walkers[fr_id].position = (0.0, 0.0)
    for player in hp_ids:
        lobby.walkers._walkers[player].position = (1.0, 0.0)

    connections[fr_id].send_json({"type": "fail"})
    event = connections[fr_id].receive_json()

    # Targets keep the lobby's joining order; min() keeps the first equal-distance item.
    assert event["type"] == "classic_fail"
    assert event["target_id"] == hp_ids[0]
    for player, connection in connections.items():
        if player != fr_id:
            assert connection.receive_json()["type"] == "classic_fail"
        assert connection.receive_json()["type"] == "classic_progress"
    assert connections[fr_id].receive_json()["type"] == "classic_fail_status"


@pytest.mark.parametrize("names,fail_count", [(PLAYER_SETS[0], 2), (PLAYER_SETS[1], 3)])
def test_classic_q_cooldown_then_reaches_fr_parity(names, fail_count, connect, clock):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    for player in names:
        lobby.walkers._walkers[player].position = (1.0, 1.0)

    for index in range(fail_count):
        if index:
            clock.wait(14.0)
            connections[fr_id].send_json({"type": "fail"})
            rejected = connections[fr_id].receive_json()
            assert rejected["code"] == "fail_rejected"
            clock.wait(1.0)
        connections[fr_id].send_json({"type": "fail"})
        event = connections[fr_id].receive_json()
        assert event["type"] == "classic_fail"
        expected = hp_ids[index]
        drain_fail_result(connections, fr_id, expected, final=index == fail_count - 1)

    assert round_state.winner() == "FR"
    assert round_state.result_reason() == "free_riders_reached_parity"


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_all_hp_tasks_over_websocket_fill_the_bar_and_end_with_all_roles(names, connect, clock):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    assert round_state.progress() == 0.0

    for hp_id in hp_ids:
        for station_text in round_state.tasks[hp_id]:
            station = int(station_text)
            put_at_station(hp_id, station)
            assert ask(connections[hp_id], {"type": "open_station", "station": station})["type"] == "station_opened"
            clock.wait(1.1)
            assert ask(connections[hp_id], {"type": "finish_station"})["type"] == "station_done"
            for connection in connections.values():
                update = connection.receive_json()
                assert update["type"] == "classic_progress"

    assert round_state.progress() == 1.0
    for connection in connections.values():
        result = connection.receive_json()
        assert result["type"] == "classic_result"
        assert result["winner"] == "HP"
        assert result["reason"] == "bar_full"
        assert set(result["roles"]) == set(names)
        assert result["roles"][fr_id] == "FR"
        connection.receive_json()  # lobby_state after the result


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_free_rider_can_move_but_cannot_close_or_complete_a_station(names, connect):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    lobby = app.state.lobbies.lobby_of(fr_id)
    put_at_station(fr_id, int(round_state.tasks[fr_id][0]))
    before = round_state.progress()

    connections[fr_id].send_json({"type": "move", "dx": 1, "dy": 0})
    assert ask(connections[fr_id], {"type": "hello", "name": fr_id})["type"] == "welcome"
    assert lobby.walkers._walkers[fr_id].dx == 1
    for kind, fields in (
        ("open_station", {"station": int(round_state.tasks[fr_id][0])}),
        ("close_station", {}),
        ("finish_station", {}),
    ):
        assert ask(connections[fr_id], {"type": kind, **fields})["code"] == "fr_cannot_task"
    assert round_state.progress() == before == 0.0


def test_role_cards_and_free_rider_marker_are_private_per_websocket(connect):
    connections, _code, public_messages, start_messages = start_classic(
        connect, PLAYER_SETS[1]
    )
    round_state = classic_for(PLAYER_SETS[1][0])
    assert all(
        "role" not in player and "roles" not in message
        for message in public_messages
        if message.get("type") == "lobby_state"
        for player in message.get("players", [])
    )
    for player_id, messages in start_messages.items():
        role_cards = [message for message in messages if message["type"] == "classic_role"]
        assert len(role_cards) == 1
        assert role_cards[0]["role"] == round_state.roles[player_id]
        markers = [message for message in messages if message["type"] == "you_are_fr"]
        assert markers == ([{"type": "you_are_fr"}] if round_state.roles[player_id] == "FR" else [])


def test_private_free_rider_name_marker_is_wired_to_all_four_views():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    world = (root / "client/js/world/world.js").read_text()
    lobby = (root / "client/js/lobby/lobby.js").read_text()
    round_view = (root / "client/js/classic/round.js").read_text()
    meeting = (root / "client/js/classic/meeting.js").read_text()
    styles = (root / "client/css/style.css").read_text()

    assert "ownIsFreeRider && isOwn(entry.player)" in world
    assert "label.isFreeRider ? \"#C43E3E\"" in world
    assert "player.name === ownName && ownIsFreeRider" in lobby
    assert "free-rider-name" in styles
    assert "ownNameLabel.classList.toggle(\"free-rider-name\", ownIsFreeRider)" in round_view
    assert "ownIsFreeRider && playerId === ownName" in meeting
    for view in (round_view,):
        assert "setOwnFreeRider" in view


def test_role_card_is_timed_for_three_seconds_and_only_for_current_role():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    round_view = (root / "client/js/classic/round.js").read_text()
    assert "[\"HP\", \"FR\"].includes(message.role)" in round_view
    assert "window.setTimeout(function () { roleScreen.hidden = true; roleTimer = null; }, 3000)" in round_view


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_classic_report_vote_chain_produces_hp_win_for_four_and_five_players(names):
    import random

    from server.classic.round import ClassicRound

    game = ClassicRound(names, [1, 2, 3, 4, 5], random.Random(20261119))
    fr_id = next(player for player, role in game.roles.items() if role == "FR")
    hp_ids = [player for player, role in game.roles.items() if role == "HP"]
    game.positions = {fr_id: (0.0, 0.0), **{player: (1.0, 0.0) for player in hp_ids}}
    game.fail(fr_id, hp_ids[0], 0.0, game.positions[hp_ids[0]])
    sheet_id, sheet_position = next(iter(game.f_sheets.items()))
    meeting = game.report(hp_ids[1], sheet_id, sheet_position, 1.0)
    game.send_chat(hp_ids[1], "I found the sheet.", 2.0)
    game.send_chat(fr_id, "I was at a station.", 4.0)
    assert meeting["phase"] == "discussion"
    assert [item["text"] for item in game.meeting["messages"]] == [
        "I found the sheet.", "I was at a station."
    ]

    game.advance_meeting(46.0)
    for living_hp in hp_ids[1:]:
        game.cast_vote(living_hp, fr_id)
    game.cast_vote(fr_id, hp_ids[1])
    result = game.advance_meeting(76.0)

    assert result["vote_result"].ejected_id == fr_id
    assert result["winner"] == "HP"
    assert game.result_reason() == "all_free_riders_eliminated"
    assert game.result()["roles"] == game.roles


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_classic_vote_tie_over_websocket_leaves_round_running(names, connect, clock):
    from server.classic.meeting import start_discussion

    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    lobby = app.state.lobbies.lobby_of(names[0])
    lobby.meeting = start_discussion(list(names), [], clock.now, round_state.state())
    clock.wait(45.0)
    targets = [names[1], names[0], names[0], names[1]]
    if len(names) == 5:
        targets.append(names[2])

    for index, (voter, target) in enumerate(zip(names, targets)):
        connections[voter].send_json({"type": "vote", "target_id": target})
        snapshots = [connection.receive_json() for connection in connections.values()]
        assert all(snapshot == snapshots[0] for snapshot in snapshots)
        # Once everybody has voted, the vote ends at once (Felix, 2026-11-21).
        assert snapshots[0]["phase"] == ("result" if index == len(names) - 1 else "voting")
    for connection in connections.values():
        assert connection.receive_json()["type"] == "classic_roster"
        assert connection.receive_json()["type"] == "positions"

    clock.wait(30.0)
    connections[names[0]].send_json({"type": "vote", "target_id": names[0]})
    assert connections[names[0]].receive_json()["code"] == "vote_rejected"
    snapshots = [connection.receive_json() for connection in connections.values()]

    assert all(snapshot == snapshots[0] for snapshot in snapshots)
    assert snapshots[0]["phase"] == "result"
    assert snapshots[0]["tie"] is True
    assert snapshots[0]["ejected_id"] is None
    assert snapshots[0]["winner"] is None
    assert lobby.round_is_running()
