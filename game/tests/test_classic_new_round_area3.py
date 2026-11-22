"""Area 3: a new round closes the meeting view and forgets the old vote.

Bug: the meeting view (client/js/classic/meeting.js) stayed open after a
round ended in a vote and the host started a new round. It only closed
after its own result timer, so the old result or vote could still cover
the new round.

Two tests:
- In the browser: the page's own files, main.js included, run in Node
  (tests/classic_cleanup_in_node.js). A vote ends the round (the Free
  Riders win by parity), the server sends the vote's result, then
  `classic_result` (S-166), then the lobby, then the host's next round.
  main.js closes the meeting once the lobby no longer has a running round
  (PR 72). The test waits far less than the meeting's own 1.8-second result
  timer (S-153), so only that path can have closed it.
- On the server: after a round ended by a vote no meeting is left, and the
  next round starts without one.
"""

from server.classic.meeting import start_discussion
from server.main import app
from task_helpers import clock, client, connect, placeholder_at_every_station  # noqa: F401
from test_classic_round_end_cleanup import lobby_state, meeting_state, needs_node, run_page, signed_in_lobby
from test_classic_server_features import classic_for, start_classic


# A wait much shorter than the meeting's own result timer (1.8 s, S-153).
SHORT_WAIT = 50  # milliseconds
# Ana (the own player) and Cy are living High Performers, Bo is the Free
# Rider, Di is a ghost. Ejecting Cy leaves one of each: the Free Riders win.
VOTE_TARGETS = {"Ana": "Bo", "Bo": "Cy", "Cy": "Cy"}
ROUND_RESULT = {
    "type": "classic_result", "winner": "FR", "reason": "free_riders_reached_parity",
    "roles": {"Ana": "HP", "Bo": "FR", "Cy": "HP", "Di": "HP"},
    "stats": {"failures": 1, "completed_tasks": 0, "meetings": 1},
}


def round_ending_meeting(phase):
    """A meeting_state step of the vote that ends the round."""
    step = meeting_state(phase)
    step[1].update(voted=list(VOTE_TARGETS), vote_targets=VOTE_TARGETS)
    if phase == "result":
        step[1].update(ejected_id="Cy", revealed_role="HP", winner="FR")
    return step


def a_round_ended_by_a_vote_then_a_new_round():
    """The messages in the order the server sends them, with a look after
    the vote, after its result, and once the new round runs."""
    return signed_in_lobby() + [
        lobby_state("countdown"),
        lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP", "task_stations": [1]}],
        ["wait", 100],
        round_ending_meeting("voting"),
        ["look"],
        round_ending_meeting("result"),
        ["look"],
        ["receive", ROUND_RESULT],
        lobby_state("lobby"),
        ["wait", SHORT_WAIT],
        # The host starts the next Classic round.
        lobby_state("countdown"),
        lobby_state("round"),
        ["wait", SHORT_WAIT],
        ["look"],
    ]


@needs_node
def test_a_new_round_closes_the_meeting_view_that_was_open_at_the_end():
    voting, at_result, new_round = run_page(a_round_ended_by_a_vote_then_a_new_round())["looks"]
    # The harness really had a vote list and a held character to clear.
    assert [button["target"] for button in voting["voteButtons"]] == ["Ana", "Bo", "Cy"]
    assert voting["inputPaused"] is True
    assert at_result["meetingHidden"] is False, "the result must be shown first"
    # The vote result and the old vote list are inside the meeting window
    # (index.html), so neither is shown once the window is hidden.
    assert new_round["meetingHidden"] is True
    assert new_round["inputPaused"] is False


def receive_until(connection, message_type):
    """Receive messages up to and including the first one of `message_type`."""
    received = []
    while True:
        message = connection.receive_json()
        received.append(message)
        if message["type"] == message_type:
            return received


def test_a_round_ended_by_a_vote_leaves_no_meeting_for_the_next_round(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    old_round = classic_for(names[0])
    fr_id = next(player for player, role in old_round.roles.items() if role == "FR")
    hp_ids = [player for player, role in old_round.roles.items() if role == "HP"]
    lobby = app.state.lobbies.lobby_of(fr_id)
    # One High Performer is already out. Ejecting another one leaves one
    # Free Rider and one High Performer: parity, so the Free Riders win.
    ghost = hp_ids[0]
    old_round.eliminated = {ghost}
    living = [fr_id] + hp_ids[1:]
    lobby.meeting = start_discussion(living, [ghost], clock.now, old_round.state())
    clock.wait(45.0)
    for voter in living:
        connections[voter].send_json({"type": "vote", "target_id": hp_ids[1]})
        for connection in connections.values():
            connection.receive_json()
    clock.wait(30.0)
    # Only a message from a player makes the server count the votes.
    connections[living[0]].send_json({"type": "vote", "target_id": fr_id})
    assert connections[living[0]].receive_json()["code"] == "vote_rejected"
    for connection in connections.values():
        messages = receive_until(connection, "classic_result")
        assert messages[-1]["winner"] == "FR"
    assert lobby.round_is_running() is False
    assert lobby.meeting is None
    assert lobby.meeting_clock is None

    connections[names[0]].send_json({"type": "start_game"})
    for connection in connections.values():
        receive_until(connection, "classic_progress")
    assert lobby.round_is_running()
    assert lobby.classic_round is not old_round
    assert lobby.meeting is None
    assert lobby.meeting_clock is None
