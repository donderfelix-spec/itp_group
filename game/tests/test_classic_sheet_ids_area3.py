"""F-sheet ids: the id the client holds must be the id the server stores.

Area 3 bug: the report button sends the sheet id from the ``classic_fail``
event. The server built that id from ``len(classic.f_sheets)`` after the fail,
so once one sheet had been reported and removed, a new sheet could get the id
of a sheet that was still on the map. The report then names the wrong sheet.
"""

import pytest

from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_fail_hud_area3 import drain_fail, place_players
from test_classic_server_features import classic_for, start_classic


PLAYER_SETS = [
    ("Mara", "Tiago", "Ines", "Rui"),
    ("Mara", "Tiago", "Ines", "Rui", "Luca"),
]
EIGHT_PLAYERS = ("Mara", "Tiago", "Ines", "Rui", "Luca", "Sol", "Ana", "Joao")


def receive_broadcast(connections, expected_type):
    messages = {player: connection.receive_json() for player, connection in connections.items()}
    assert all(message["type"] == expected_type for message in messages.values())
    return next(iter(messages.values()))


def read_until(connection, message_type):
    while True:
        message = connection.receive_json()
        if message["type"] == message_type:
            return message


def roles_of(round_state):
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    hp_ids = [player for player, role in round_state.roles.items() if role == "HP"]
    return fr_id, hp_ids


@pytest.mark.parametrize("names", PLAYER_SETS)
def test_fail_event_names_the_stored_sheet_and_report_on_it_is_accepted(names, connect, clock):
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id, hp_ids = roles_of(round_state)
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, names, {player: (100.0, 100.0) for player in names})

    connections[fr_id].send_json({"type": "fail"})
    fail = connections[fr_id].receive_json()
    assert fail["type"] == "classic_fail"
    drain_fail(connections, round_state, fr_id, fail["target_id"])

    assert fail["sheet_id"] in round_state.f_sheets

    reporter_id = next(player for player in hp_ids if player != fail["target_id"])
    connections[reporter_id].send_json({
        "type": "report", "sheet_id": fail["sheet_id"], "position": fail["position"],
    })
    meeting = receive_broadcast(connections, "meeting_state")
    assert meeting["phase"] == "discussion"
    assert round_state.meeting["reason"] == "report"


def test_report_on_a_sheet_made_after_another_report_names_that_sheet(connect, clock):  # 8 players: 2 FR, 6 HP
    """Sheet A is reported, sheet B stays on the map, then sheet C is made.

    C must get an id of its own, and reporting C by its event id must work.
    """
    connections, _code, _public, _start = start_classic(connect, EIGHT_PLAYERS)
    round_state = classic_for(EIGHT_PLAYERS[0])
    fr_id, hp_ids = roles_of(round_state)
    lobby = app.state.lobbies.lobby_of(fr_id)
    place_players(lobby, EIGHT_PLAYERS, {player: (100.0, 100.0) for player in EIGHT_PLAYERS})

    # Sheet A: the FR fails the first HP.
    connections[fr_id].send_json({"type": "fail"})
    fail_a = connections[fr_id].receive_json()
    assert fail_a["type"] == "classic_fail"
    drain_fail(connections, round_state, fr_id, fail_a["target_id"])

    # Sheet B: a second fail after the 15 s cooldown.
    clock.wait(15.0)
    connections[fr_id].send_json({"type": "fail"})
    fail_b = connections[fr_id].receive_json()
    assert fail_b["type"] == "classic_fail"
    drain_fail(connections, round_state, fr_id, fail_b["target_id"])
    ghosts = {fail_a["target_id"], fail_b["target_id"]}

    # Report sheet A. The meeting ends in a tie, so nobody is ejected.
    reporter = next(player for player in hp_ids if player not in ghosts)
    connections[reporter].send_json({
        "type": "report", "sheet_id": fail_a["sheet_id"], "position": fail_a["position"],
    })
    meeting = receive_broadcast(connections, "meeting_state")
    assert meeting["phase"] == "discussion"
    assert fail_a["sheet_id"] in round_state.f_sheets
    assert fail_b["sheet_id"] in round_state.f_sheets

    living = [player for player in EIGHT_PLAYERS if player not in ghosts]
    next_vote = {voter: living[(index + 1) % len(living)] for index, voter in enumerate(living)}
    clock.wait(45.0)
    for voter in living:
        connections[voter].send_json({"type": "vote", "target_id": next_vote[voter]})
        assert receive_broadcast(connections, "meeting_state")["phase"] == "voting"
    clock.wait(30.0)
    connections[reporter].send_json({"type": "vote", "target_id": next_vote[reporter]})
    assert connections[reporter].receive_json()["code"] == "vote_rejected"
    result = receive_broadcast(connections, "meeting_state")
    assert result["phase"] == "result"
    assert result["ejected_id"] is None
    for connection in connections.values():
        read_until(connection, "positions")

    # Sheet C: a new fail while sheet B is still on the map.
    connections[fr_id].send_json({"type": "fail"})
    fail_c = connections[fr_id].receive_json()
    assert fail_c["type"] == "classic_fail"
    drain_fail(connections, round_state, fr_id, fail_c["target_id"])

    assert fail_c["sheet_id"] != fail_b["sheet_id"]
    assert fail_c["sheet_id"] in round_state.f_sheets

    ghosts.add(fail_c["target_id"])
    reporter_c = next(player for player in hp_ids if player not in ghosts)
    connections[reporter_c].send_json({
        "type": "report", "sheet_id": fail_c["sheet_id"], "position": fail_c["position"],
    })
    meeting = receive_broadcast(connections, "meeting_state")
    assert meeting["phase"] == "discussion"
    assert round_state.meeting["reason"] == "report"
