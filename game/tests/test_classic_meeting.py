"""Pure Classic meeting rules and the WebSocket chat broadcast (M3-3.4)."""

import asyncio

import pytest

from server import main
from server.classic.meeting import (
    advance_meeting, can_send_chat, meeting_snapshot, send_chat, start_discussion,
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
