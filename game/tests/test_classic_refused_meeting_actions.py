"""A refused chat, vote or Skip is heard only by its sender (M3-2.1, findings 1 to 3).

The handlers in server/main.py are called directly with stand-in
connections, in a Classic round of four: Mara (the Free Rider), Tiago and
Rui are alive, Ines is a ghost. The scripted rounds
over the real WebSocket endpoint are in test_classic_rule1_messages.py.
"""

import asyncio
import random

from server import main
from server.classic.meeting import CHAT_COOLDOWN_SECONDS, start_discussion
from server.classic.round import ClassicRound
from server.net.lobbies import Lobbies
from server.net.sessions import Sessions

LIVING = ["Mara", "Tiago", "Rui"]
GHOST = "Ines"


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def lobby_in_a_meeting(monkeypatch, now=101.0, reason="report"):
    """A meeting that began at 100.0: the discussion ends at 145.0 and the vote at 175.0."""
    names = LIVING + [GHOST]
    sockets = {name: FakeSocket() for name in names}
    sessions = Sessions()
    for name, socket in sockets.items():
        sessions.sign_in_account(socket, name)
    monkeypatch.setattr(main.app.state, "sessions", sessions)
    set_clock(monkeypatch, now)
    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    for name in names[1:]:
        lobbies.join(name, "ABCD")
    lobby.classic_round = a_classic_round(names)
    lobby.meeting = start_discussion(LIVING, [GHOST], 100.0)
    lobby.meeting["reason"] = reason  # both Classic meeting triggers allow immediate voting
    monkeypatch.setattr(main.app.state, "lobbies", lobbies)
    return lobby, sockets


def a_classic_round(names):
    """Mara is the Free Rider and Ines has failed, so nobody has won."""
    classic = ClassicRound(names, [1, 2, 3, 4, 5], random.Random(1))
    classic.roles = {name: "FR" if name == "Mara" else "HP" for name in names}
    classic.eliminated = {GHOST}
    classic.phase = "meeting"
    return classic


def set_clock(monkeypatch, now):
    monkeypatch.setattr(main, "seconds_now", lambda: now)


def forget_what_was_sent(sockets):
    for socket in sockets.values():
        socket.messages.clear()


def codes(socket):
    return [message.get("code", message["type"]) for message in socket.messages]


def heard_by_others(sockets, sender):
    return {name: codes(socket) for name, socket in sockets.items() if name != sender and socket.messages}


def send(sockets, name, message):
    handlers = {
        "chat": main.answer_chat_message,
        "vote": main.answer_vote_message,
    }
    if message["type"] == "skip_discussion":
        asyncio.run(main.answer_skip_discussion_message(sockets[name]))
    else:
        asyncio.run(handlers[message["type"]](sockets[name], message))


def run_the_tick_sends(monkeypatch, lobby):
    """What one tick of the meeting clock sends, run to its end here."""
    started = []
    monkeypatch.setattr(main, "run_in_background", started.append)
    main.update_meeting_clock(lobby)
    for work in started:
        asyncio.run(work)
    return len(started)


CHAT = {"type": "chat", "text": "Where were you?"}
SKIP = {"type": "skip_discussion"}


def vote(target):
    return {"type": "vote", "target_id": target}


# Finding 1: a refused chat


def test_an_accepted_chat_goes_to_everybody(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Mara", CHAT)
    snapshots = [socket.messages for socket in sockets.values()]
    assert all(messages == snapshots[0] and len(messages) == 1 for messages in snapshots)
    assert snapshots[0][0]["messages"] == [{"player_id": "Mara", "text": "Where were you?"}]


def test_a_ghosts_chat_is_heard_only_by_the_ghost(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, GHOST, CHAT)
    assert codes(sockets[GHOST]) == ["chat_rejected"]
    assert heard_by_others(sockets, GHOST) == {}
    assert lobby.meeting["messages"] == []


def test_a_chat_during_the_cooldown_is_heard_only_by_its_sender(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Mara", CHAT)
    forget_what_was_sent(sockets)
    set_clock(monkeypatch, 101.0 + CHAT_COOLDOWN_SECONDS / 2)
    send(sockets, "Mara", CHAT)
    assert codes(sockets["Mara"]) == ["chat_rejected"]
    assert heard_by_others(sockets, "Mara") == {}


def test_a_chat_just_after_the_cooldown_goes_to_everybody(monkeypatch):
    # Edge: exactly at the end of the cooldown the chat is accepted again.
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Mara", CHAT)
    forget_what_was_sent(sockets)
    set_clock(monkeypatch, 101.0 + CHAT_COOLDOWN_SECONDS)
    send(sockets, "Mara", CHAT)
    assert all(codes(socket) == ["meeting_state"] for socket in sockets.values())


def test_a_chat_refused_because_the_discussion_ended_leaves_the_news_to_the_tick(monkeypatch):
    # Edge: the time ran out just before the chat. The sender alone hears
    # the refusal; the tick then tells everybody once that the vote is open.
    lobby, sockets = lobby_in_a_meeting(monkeypatch, now=146.0, reason="emergency")
    send(sockets, "Mara", CHAT)
    assert codes(sockets["Mara"]) == ["chat_rejected"]
    assert heard_by_others(sockets, "Mara") == {}
    forget_what_was_sent(sockets)

    assert run_the_tick_sends(monkeypatch, lobby) == 1
    for socket in sockets.values():
        assert [(m["type"], m["phase"]) for m in socket.messages] == [("meeting_state", "voting")]
    assert run_the_tick_sends(monkeypatch, lobby) == 0  # the same second: nothing again


# Finding 2: a refused vote or Skip


def test_an_accepted_vote_goes_to_everybody(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Mara", vote("Tiago"))
    assert all(codes(socket) == ["meeting_state"] for socket in sockets.values())
    assert sockets[GHOST].messages[0]["vote_targets"] == {"Mara": "Tiago"}


def test_a_ghosts_skip_is_heard_only_by_the_ghost(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, GHOST, SKIP)
    assert codes(sockets[GHOST]) == ["skip_discussion_rejected"]
    assert heard_by_others(sockets, GHOST) == {}


def test_a_vote_for_a_ghost_is_heard_only_by_the_voter(monkeypatch):
    lobby, sockets = lobby_in_a_meeting(monkeypatch)
    send(sockets, "Tiago", vote(GHOST))
    assert codes(sockets["Tiago"]) == ["vote_rejected"]
    assert heard_by_others(sockets, "Tiago") == {}
    assert lobby.meeting["votes"] == {}


def test_a_vote_and_a_skip_in_an_emergency_discussion_are_broadcast(monkeypatch):
    _lobby, sockets = lobby_in_a_meeting(monkeypatch, reason="emergency")
    send(sockets, "Mara", vote("Tiago"))
    send(sockets, "Mara", SKIP)
    for socket in sockets.values():
        assert codes(socket) == ["meeting_state", "meeting_state"]
        first, second = socket.messages
        assert first["phase"] == second["phase"] == "discussion"
        assert first["vote_targets"] == {"Mara": "Tiago"}
        assert second["vote_targets"] == {}
        assert second["skip_voted"] == ["Mara"]


def test_a_vote_refused_because_the_time_ran_out_sends_the_result_once(monkeypatch):
    # Edge: the vote's time ran out just before the vote. Everybody gets the
    # result exactly once, from the handler or from the tick, never twice.
    lobby, sockets = lobby_in_a_meeting(monkeypatch, now=176.0)
    send(sockets, "Mara", vote("Tiago"))
    run_the_tick_sends(monkeypatch, lobby)
    assert "vote_rejected" in codes(sockets["Mara"])
    for socket in sockets.values():
        results = [m for m in socket.messages if m["type"] == "meeting_state" and m["phase"] == "result"]
        assert len(results) == 1


def test_a_chat_refused_because_the_vote_ended_sends_the_result_once(monkeypatch):
    # Edge (review M1): the vote's time ran out before the next tick and a
    # living player chats. The sender gets the refusal, and everybody gets
    # the result exactly once, from the tick.
    lobby, sockets = lobby_in_a_meeting(monkeypatch, now=176.0)
    lobby.meeting["phase"] = "voting"
    lobby.meeting["deadline"] = 175.0
    send(sockets, "Tiago", CHAT)
    assert codes(sockets["Tiago"]) == ["chat_rejected"]
    run_the_tick_sends(monkeypatch, lobby)
    for socket in sockets.values():
        results = [m for m in socket.messages if m["type"] == "meeting_state" and m["phase"] == "result"]
        assert len(results) == 1
    assert codes(sockets["Tiago"]).count("chat_rejected") == 1


# Finding 3: after the meeting


def lobby_after_the_result(monkeypatch):
    """The vote ended at 175.0 and everybody was sent its result; now it is 180.0."""
    lobby, sockets = lobby_in_a_meeting(monkeypatch, now=176.0)
    run_the_tick_sends(monkeypatch, lobby)
    assert lobby.meeting["applied"] is True
    set_clock(monkeypatch, 180.0)
    forget_what_was_sent(sockets)
    return lobby, sockets


def test_a_vote_and_a_skip_after_the_meeting_are_heard_only_by_the_sender(monkeypatch):
    lobby, sockets = lobby_after_the_result(monkeypatch)
    send(sockets, "Mara", vote("Tiago"))
    send(sockets, "Tiago", SKIP)
    assert codes(sockets["Mara"]) == ["vote_rejected"]
    assert codes(sockets["Tiago"]) == ["skip_discussion_rejected"]
    assert codes(sockets[GHOST]) == []


def test_the_tick_does_not_send_a_finished_meeting_again(monkeypatch):
    lobby, sockets = lobby_after_the_result(monkeypatch)
    assert run_the_tick_sends(monkeypatch, lobby) == 0
    assert all(socket.messages == [] for socket in sockets.values())


def test_a_chat_after_the_meeting_is_heard_only_by_its_sender(monkeypatch):
    lobby, sockets = lobby_after_the_result(monkeypatch)
    send(sockets, "Mara", CHAT)
    assert codes(sockets["Mara"]) == ["chat_rejected"]
    assert heard_by_others(sockets, "Mara") == {}
