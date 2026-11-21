"""The vote handler in server/main.py: two last votes at once, and a result sent once."""

import asyncio

from server import main
from server.classic.meeting import SKIP, start_discussion
from server.net.lobbies import Lobbies
from server.net.sessions import Sessions


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def lobby_in_a_vote(monkeypatch, now=150.0):
    """Mara and Tiago are alive and voting; Ines is a ghost."""
    names = ["Mara", "Tiago", "Ines"]
    sockets = {name: FakeSocket() for name in names}
    sessions = Sessions()
    for name, socket in sockets.items():
        sessions.sign_in_account(socket, name)
    monkeypatch.setattr(main.app.state, "sessions", sessions)
    monkeypatch.setattr(main, "seconds_now", lambda: now)
    lobbies = Lobbies()
    lobby, _ = lobbies.create("Mara", lambda: "ABCD")
    for name in names[1:]:
        lobbies.join(name, "ABCD")
    lobby.meeting = start_discussion(["Mara", "Tiago"], ["Ines"], 100.0)
    lobby.meeting["phase"] = "voting"
    lobby.meeting["deadline"] = 175.0
    monkeypatch.setattr(main.app.state, "lobbies", lobbies)
    return lobby, sockets


def results_sent_to(socket):
    return [m for m in socket.messages if m["type"] == "meeting_state" and m["phase"] == "result"]


def test_a_vote_handler_survives_a_meeting_cleared_while_it_waited(monkeypatch):
    # Two players cast the last two votes at once and the first one ends the
    # round, which clears the meeting while the second handler still waits
    # in `tell_meeting_state`. The second handler must not raise.
    lobby, sockets = lobby_in_a_vote(monkeypatch)
    send_the_snapshot = main.tell_meeting_state

    async def snapshot_then_round_over(the_lobby, now=None):
        await send_the_snapshot(the_lobby, now)
        the_lobby.meeting = None  # what the other handler did meanwhile

    monkeypatch.setattr(main, "tell_meeting_state", snapshot_then_round_over)
    asyncio.run(main.answer_vote_message(sockets["Mara"], {"type": "vote", "target_id": SKIP}))
    assert lobby.meeting is None


def test_two_last_votes_at_once_both_finish(monkeypatch):
    lobby, sockets = lobby_in_a_vote(monkeypatch)

    async def both():
        await asyncio.gather(
            main.answer_vote_message(sockets["Mara"], {"type": "vote", "target_id": "Tiago"}),
            main.answer_vote_message(sockets["Tiago"], {"type": "vote", "target_id": SKIP}),
        )

    asyncio.run(both())
    assert lobby.meeting["phase"] == "result"


def test_an_early_result_is_sent_once_and_not_again_by_the_tick(monkeypatch):
    lobby, sockets = lobby_in_a_vote(monkeypatch)
    asyncio.run(main.answer_vote_message(sockets["Mara"], {"type": "vote", "target_id": SKIP}))
    asyncio.run(main.answer_vote_message(sockets["Tiago"], {"type": "vote", "target_id": SKIP}))
    assert lobby.meeting["phase"] == "result"
    assert all(len(results_sent_to(socket)) == 1 for socket in sockets.values())

    scheduled = []
    monkeypatch.setattr(main, "run_in_background", lambda work: scheduled.append(work) or work.close())
    main.update_meeting_clock(lobby)  # the next tick
    assert scheduled == []


def test_the_tick_still_publishes_a_new_clock_second(monkeypatch):
    # Edge: recording the clock after a vote must not stop the countdown.
    lobby, sockets = lobby_in_a_vote(monkeypatch)
    asyncio.run(main.answer_vote_message(sockets["Mara"], {"type": "vote", "target_id": SKIP}))
    assert lobby.meeting["phase"] == "voting"

    scheduled = []
    monkeypatch.setattr(main, "run_in_background", lambda work: scheduled.append(work) or work.close())
    main.update_meeting_clock(lobby)  # the same second: nothing new
    assert scheduled == []
    monkeypatch.setattr(main, "seconds_now", lambda: 151.0)
    main.update_meeting_clock(lobby)  # one second later
    assert len(scheduled) == 1
