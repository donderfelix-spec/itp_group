"""A living player is never sent a ghost, in any phase of a Classic round (M3-3.20).

Before this fix, `tell_positions` and `state_of` in `server/main.py` left the
ghosts out for the living only while the round's phase was "round". During a
meeting and its result every ghost's position went to everybody. Now the
filter holds whenever a Classic round exists. Ghosts still see everybody
(S-136).
"""

import pytest

from server import main
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_server_features import classic_for, start_classic

FOUR = ("Mara", "Tiago", "Ines", "Rui")
# An open stretch of the deck, outside hiding spots and within mutual sight.
DECK_PLACES = [(475.0, 287.0), (489.0, 305.0), (505.0, 285.0), (521.0, 305.0)]


def next_of_type(connection, wanted):
    """The next message of this type on this connection; other messages are skipped."""
    while True:
        message = connection.receive_json()
        if message["type"] == wanted:
            return message


def positions_now(connections):
    """Send the lobby's positions now, as the tick does. Returns `{receiver: names}`."""
    first = next(iter(connections))
    lobby = app.state.lobbies.lobby_of(first)
    lobby.walkers._everybody_needs_news()
    connections[first].portal.call(main.tell_positions, lobby)
    return {
        name: {entry["name"] for entry in next_of_type(connection, "positions")["players"]}
        for name, connection in connections.items()
    }


def lobby_players_now(lobby):
    """The player names of the `lobby_state` each member would be sent now."""
    return {
        name: {entry["name"] for entry in main.state_of(lobby, name)["players"]}
        for name in lobby.names()
    }


def round_with_a_ghost(connect):
    """A Classic round of four in which one High Performer is a known ghost.

    Returns (connections, lobby, ghost, living players).
    """
    connections, _code, _public, _start = start_classic(connect, FOUR)
    classic = classic_for(FOUR[0])
    for name, place in zip(FOUR, DECK_PLACES):
        put(name, place)
    ghost = next(name for name in FOUR if classic.roles[name] == "HP")
    classic.eliminated = {ghost}
    living = [name for name in FOUR if name != ghost]
    return connections, app.state.lobbies.lobby_of(ghost), ghost, living


# Accepted: in a real meeting the living get no ghost, the ghost gets everybody


def test_during_a_meeting_the_living_are_not_sent_the_ghost(connect, clock):
    connections, lobby, ghost, living = round_with_a_ghost(connect)
    clock.wait(46)  # the emergency button unlocks 45 seconds after the start
    put(living[0], (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))
    connections[living[0]].send_json({"type": "emergency"})
    for connection in connections.values():
        next_of_type(connection, "meeting_state")
    assert lobby.classic_round.phase == "meeting"
    # Back from the button to the deck: everybody, the ghost included, in mutual sight (S-185).
    put(living[0], DECK_PLACES[FOUR.index(living[0])])

    told = positions_now(connections)

    for name in living:
        assert ghost not in told[name]
        assert told[name] == set(FOUR) - {ghost}
    assert told[ghost] == set(FOUR)


def test_during_a_meeting_the_lobby_state_of_the_living_has_no_ghost(connect, clock):
    connections, lobby, ghost, living = round_with_a_ghost(connect)
    clock.wait(46)
    put(living[0], (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))
    connections[living[0]].send_json({"type": "emergency"})
    for connection in connections.values():
        next_of_type(connection, "meeting_state")

    players = lobby_players_now(lobby)

    for name in living:
        assert players[name] == set(FOUR) - {ghost}
    assert players[ghost] == set(FOUR)


# Edge cases: every other value of the phase, also one nobody uses yet


@pytest.mark.parametrize("phase", ["meeting", "result", "something_new"])
def test_in_every_phase_the_living_get_no_ghost_position(phase, connect):
    connections, lobby, ghost, living = round_with_a_ghost(connect)
    lobby.classic_round.phase = phase

    told = positions_now(connections)

    for name in living:
        assert told[name] == set(FOUR) - {ghost}
    assert told[ghost] == set(FOUR)


@pytest.mark.parametrize("phase", ["round", "meeting", "result", "something_new"])
def test_in_every_phase_the_lobby_state_of_the_living_has_no_ghost(phase, connect):
    _connections, lobby, ghost, living = round_with_a_ghost(connect)
    lobby.classic_round.phase = phase

    players = lobby_players_now(lobby)

    for name in living:
        assert players[name] == set(FOUR) - {ghost}
    assert players[ghost] == set(FOUR)


def test_with_two_ghosts_each_ghost_sees_the_other_and_the_living_see_neither(connect):
    connections, lobby, ghost, living = round_with_a_ghost(connect)
    classic = lobby.classic_round
    second_ghost = next(name for name in living if classic.roles[name] == "HP")
    classic.eliminated = {ghost, second_ghost}
    classic.phase = "meeting"

    told = positions_now(connections)

    for name in FOUR:
        if name in (ghost, second_ghost):
            assert told[name] == set(FOUR)
        else:
            assert told[name] == set(FOUR) - {ghost, second_ghost}


# Rejected nothing, changed nothing: without a ghost, or after the round, everybody gets everybody


def test_in_a_meeting_without_ghosts_everybody_gets_everybody(connect):
    connections, lobby, _ghost, _living = round_with_a_ghost(connect)
    lobby.classic_round.eliminated = set()
    lobby.classic_round.phase = "meeting"

    told = positions_now(connections)

    for name in FOUR:
        assert told[name] == set(FOUR)


def test_after_the_round_ended_the_lobby_state_lists_everybody(connect):
    _connections, lobby, _ghost, _living = round_with_a_ghost(connect)
    lobby.end_round()

    players = lobby_players_now(lobby)

    for name in FOUR:
        assert players[name] == set(FOUR)
