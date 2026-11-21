"""Pure Classic meeting rules and the WebSocket chat broadcast (M3-3.4)."""

import asyncio

import pytest

from server import main
from server.classic.meeting import (
    EjectResult,
    advance_meeting,
    cast_vote,
    can_send_chat,
    meeting_snapshot,
    send_chat,
    start_discussion,
    tally_votes,
)
from server.net.lobbies import Lobbies
from server.net.sessions import Sessions


def new_meeting():
    return start_discussion(["Mara", "Tiago"], ["Ines"], 100.0)


def test_a_ghost_may_read_but_cannot_send_chat():
    meeting = new_meeting()

    assert not can_send_chat(meeting, "Ines", "I saw something", 101.0)
    with pytest.raises(ValueError, match="not allowed"):
        send_chat(meeting, "Ines", "I saw something", 101.0)


def test_chat_rejects_more_than_200_characters():
    meeting = new_meeting()

    assert not can_send_chat(meeting, "Mara", "x" * 201, 101.0)
    with pytest.raises(ValueError, match="not allowed"):
        send_chat(meeting, "Mara", "x" * 201, 101.0)


def test_a_player_must_wait_two_seconds_between_chat_messages():
    meeting = send_chat(new_meeting(), "Mara", "First", 101.0)

    assert not can_send_chat(meeting, "Mara", "Too soon", 102.99)
    assert can_send_chat(meeting, "Mara", "Ready", 103.0)


def test_discussion_changes_to_voting_after_45_seconds_with_fake_time():
    meeting = new_meeting()

    assert advance_meeting(meeting, 144.99)["phase"] == "discussion"
    updated = advance_meeting(meeting, 145.0)
    assert updated["phase"] == "voting"
    assert updated["deadline"] == 175.0


def test_chat_history_snapshot_is_identical_for_every_participant():
    meeting = send_chat(new_meeting(), "Mara", "We should compare notes.", 101.0)
    participants = ["Mara", "Tiago", "Ines"]

    views = [meeting_snapshot(meeting, 102.0) for _participant in participants]

    assert all(view == views[0] for view in views)
    assert views[0]["messages"] == [
        {"player_id": "Mara", "text": "We should compare notes."}
    ]


def test_meeting_snapshot_includes_trigger_reason_and_dead_players():
    meeting = new_meeting()
    meeting["reason"] = "report"
    meeting["trigger_player_id"] = "Mara"
    snapshot = meeting_snapshot(meeting, 101.0)
    assert snapshot["reason"] == "report"
    assert snapshot["trigger_player_id"] == "Mara"
    assert snapshot["ghosts"] == ["Ines"]


def voting_state(roles, votes):
    living = list(roles)
    state = start_discussion(
        living,
        [],
        0.0,
        {
            "roles": roles,
            "tasks": {player_id: ["1", "2", "3", "4"] for player_id in roles},
            "completed_tasks": {},
            "eliminated": set(),
        },
    )
    state["phase"] = "voting"
    state["deadline"] = 30.0
    state["votes"] = dict(votes)
    return state


def test_the_majority_is_ejected_only_after_voting_ends():
    state = voting_state(
        {"A": "HP", "B": "HP", "C": "HP", "D": "HP", "F": "FR"},
        {"A": "F", "B": "F", "C": "F", "D": "A", "F": "A"},
    )

    with pytest.raises(ValueError, match="hidden"):
        tally_votes(state)
    finished = advance_meeting(state, 29.99)
    assert finished["phase"] == "voting"
    result_state = advance_meeting(state, 30.0)

    assert result_state["vote_result"] == EjectResult("F", False, "FR")
    assert result_state["living"] == ("A", "B", "C", "D")
    assert result_state["ghosts"] == ("F",)
    assert result_state["winner"] == "HP"


def test_a_tie_ejects_nobody():
    state = voting_state(
        {"A": "HP", "B": "HP", "C": "HP", "F": "FR"},
        {"A": "B", "B": "A", "C": "A", "F": "B"},
    )

    result_state = advance_meeting(state, 30.0)

    assert result_state["vote_result"] == EjectResult(None, True, None)
    assert result_state["living"] == ("A", "B", "C", "F")
    assert result_state["ghosts"] == ()


def test_a_ghost_cannot_vote_and_a_vote_cannot_target_a_ghost():
    state = voting_state({"A": "HP", "F": "FR"}, {})
    state["living"] = ("A",)
    state["ghosts"] = ("F",)

    with pytest.raises(ValueError, match="living players"):
        cast_vote(state, "F", "A")
    with pytest.raises(ValueError, match="living player"):
        cast_vote(state, "A", "F")


def test_a_player_cannot_change_their_final_vote():
    state = voting_state({"A": "HP", "B": "HP", "F": "FR"}, {})
    cast = cast_vote(state, "A", "B")

    assert cast["votes"] == {"A": "B"}
    assert state["votes"] == {}
    with pytest.raises(ValueError, match="final"):
        cast_vote(cast, "A", "F")


def test_ejecting_an_hp_leaves_the_round_running_when_hp_still_outnumber_fr():
    state = voting_state(
        {"A": "HP", "B": "HP", "C": "HP", "D": "HP", "F": "FR"},
        {"A": "C", "B": "C", "D": "C", "C": "A", "F": "A"},
    )

    result_state = advance_meeting(state, 30.0)

    assert result_state["vote_result"] == EjectResult("C", False, "HP")
    assert result_state["winner"] is None


def test_votes_are_not_shown_to_players_before_the_result():
    state = voting_state(
        {"A": "HP", "B": "HP", "F": "FR"}, {"A": "F"}
    )

    snapshot = meeting_snapshot(state, 10.0)

    assert snapshot["voted"] == ["A"]
    assert "votes" not in snapshot
    assert snapshot["ejected_id"] is None
    assert snapshot["revealed_role"] is None
    assert "vote_targets" not in snapshot


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def test_websocket_chat_broadcasts_the_same_transcript_to_living_and_ghosts(monkeypatch):
    names = ["Mara", "Tiago", "Ines"]
    sockets = {name: FakeSocket() for name in names}
    sessions = Sessions()
    for name, socket in sockets.items():
        sessions.sign_in_account(socket, name)
    monkeypatch.setattr(main.app.state, "sessions", sessions)
    monkeypatch.setattr(main, "seconds_now", lambda: 101.0)

    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    for name in names[1:]:
        lobbies.join(name, "ABCD")
    lobby.meeting = start_discussion(["Mara", "Tiago"], ["Ines"], 100.0)
    monkeypatch.setattr(main.app.state, "lobbies", lobbies)

    asyncio.run(main.answer_chat_message(sockets["Mara"], {"text": "Hello everyone."}))

    received = [socket.messages[-1] for socket in sockets.values()]
    assert received[0] == received[1] == received[2]
    assert received[0]["messages"] == [
        {"player_id": "Mara", "text": "Hello everyone."}
    ]


def test_websocket_rejects_a_ghost_chat_message(monkeypatch):
    ghost_socket = FakeSocket()
    living_socket = FakeSocket()
    sessions = Sessions()
    sessions.sign_in_account(ghost_socket, "Ines")
    sessions.sign_in_account(living_socket, "Mara")
    monkeypatch.setattr(main.app.state, "sessions", sessions)
    monkeypatch.setattr(main, "seconds_now", lambda: 101.0)
    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Ines", "ABCD")
    lobby.meeting = start_discussion(["Mara"], ["Ines"], 100.0)
    monkeypatch.setattr(main.app.state, "lobbies", lobbies)

    asyncio.run(main.answer_chat_message(ghost_socket, {"text": "Ghost message"}))

    assert ghost_socket.messages[0]["code"] == "chat_rejected"
    assert not lobby.meeting["messages"]
