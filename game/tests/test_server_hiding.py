"""Hiding through the real server: who is sent a Free Rider in a hiding spot (M3-1.4).

`tell_positions` sends every member the positions. In a Classic round a
living Free Rider whose centre stands in one of the four hiding spots is
left out for every living High Performer farther than 35 map units away
(S-124 to S-126). Ghosts see him (S-129), other Free Riders see him
(S-130), a meeting does not reveal him (S-131). Classic's own filter stays:
the living are never sent the ghosts. Outside Classic nothing changes.

The players are placed where a long walk would have brought them, then the
positions are sent as the tick sends them; one test walks with the real tick.
"""

import json
import time

import pytest

from server import main, protocol
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_server_features import classic_for, start_classic
from test_server_duel import REAL_TICK, duel_of, lobby_of

CAMPUS = app.state.campus
# The hiding spot in the hedge on the Main Deck (595, 249, r 9).
SPOT = CAMPUS["hiding_spots"][0]
IN_THE_SPOT = (SPOT["x"], SPOT["y"])
# Far from every hiding spot and from each other.
FAR_PLACES = [(100.0, 330.0), (300.0, 330.0), (300.0, 400.0), (200.0, 300.0), (400.0, 300.0), (250.0, 450.0)]
FOUR = ("Mara", "Tiago", "Ines", "Rui")
SIX = ("Mara", "Tiago", "Ines", "Rui", "Luca", "Sofia")


def beside_the_spot(distance):
    """A place `distance` units to the right of the spot's centre."""
    return (SPOT["x"] + distance, SPOT["y"])


def next_positions(connection):
    """The next `positions` message of this connection; other messages are skipped."""
    while True:
        message = connection.receive_json()
        if message["type"] == "positions":
            return message


def positions_now(connections):
    """Send the lobby's positions now, as the tick does. Returns `{receiver: message}`."""
    first = next(iter(connections))
    lobby = app.state.lobbies.lobby_of(first)
    lobby.walkers._everybody_needs_news()
    connections[first].portal.call(main.tell_positions, lobby)
    return {name: next_positions(connection) for name, connection in connections.items()}


def names_in(message):
    return [entry["name"] for entry in message["players"]]


def positions_arrived(connection):
    """The `positions` messages this connection got so far. Never waits forever.

    A hello is sent and everything up to its answer is collected.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    arrived = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return arrived
        if message["type"] == "positions":
            arrived.append(message)


def wait_for_positions_with(connection, name, seconds=3):
    """Collect positions until one lists `name`. Returns all collected, or fails after `seconds`."""
    deadline = time.monotonic() + seconds
    collected = []
    while not any(name in names_in(message) for message in collected):
        assert time.monotonic() < deadline, f"no positions with {name} arrived"
        collected += positions_arrived(connection)
        time.sleep(0.02)
    return collected


def classic_round(connect, names=FOUR):
    """A running Classic round. Returns (connections, Free Riders, High Performers).

    Everybody stands far apart and far from every hiding spot.
    """
    connections, _code, _public, _start = start_classic(connect, names)
    roles = classic_for(names[0]).roles
    free_riders = [name for name in names if roles[name] == "FR"]
    high_performers = [name for name in names if roles[name] == "HP"]
    for name, place in zip(names, FAR_PLACES):
        put(name, place)
    return connections, free_riders, high_performers


# Accepted: the Free Rider hides from living High Performers farther than 35


def test_a_free_rider_in_a_spot_is_left_out_beyond_35_and_sent_within_35(connect):
    connections, [fr], [far, at_35, near] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    put(far, beside_the_spot(35.5))
    put(at_35, beside_the_spot(35))
    put(near, (SPOT["x"], SPOT["y"] + 20))

    told = positions_now(connections)

    assert fr not in names_in(told[far])
    assert fr in names_in(told[at_35])
    assert fr in names_in(told[near])
    # The Free Rider himself gets everybody, his own position included.
    assert sorted(names_in(told[fr])) == sorted(FOUR)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_one_of_the_four_spots_hides_the_free_rider(connect, index):
    connections, [fr], high_performers = classic_round(connect)
    spot = CAMPUS["hiding_spots"][index]
    put(fr, (spot["x"], spot["y"]))
    told = positions_now(connections)
    for name in high_performers:
        assert fr not in names_in(told[name])


def test_the_edge_of_the_spot_still_hides(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(fr, (SPOT["x"], SPOT["y"] - SPOT["r"]))
    assert fr not in names_in(positions_now(connections)[far])


def test_the_message_to_a_far_player_carries_no_trace_of_the_hidden_free_rider(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    lobby = app.state.lobbies.lobby_of(fr)
    others = [entry for entry in lobby.walkers.positions() if entry[0] != fr]

    message = positions_now(connections)[far]

    # Exactly the message of the others, in the usual format: nothing added.
    assert message == protocol.positions(others)
    assert set(message) == {"type", "players"}
    assert all(set(entry) == {"name", "x", "y"} for entry in message["players"])
    assert fr not in json.dumps(message)


def test_a_free_rider_walking_into_the_spot_disappears_for_the_far_players(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    # Below the hedge; three steps of 9 units up end in the spot, at y 253.
    put(fr, (595.0, 280.0))
    lobby = app.state.lobbies.lobby_of(fr)
    lobby.walkers.set_direction(fr, 0, -1)
    seen_by_far = []
    for _ in range(3):
        connections[fr].portal.call(REAL_TICK, 0.1)
        seen_by_far.append(names_in(next_positions(connections[far])))
    lobby.walkers.set_direction(fr, 0, 0)

    assert lobby.walkers.position_of(fr) == (595.0, 253.0)
    assert [fr in seen for seen in seen_by_far] == [True, True, False]


# Accepted: nobody else hides


def test_a_high_performer_in_a_spot_is_sent_to_everybody(connect):
    connections, [fr], [in_spot, far, _] = classic_round(connect)
    put(in_spot, IN_THE_SPOT)
    told = positions_now(connections)
    for name in FOUR:
        assert in_spot in names_in(told[name])
    assert fr in names_in(told[far])


def test_a_free_rider_outside_every_spot_is_sent_to_everybody(connect):
    connections, [fr], _ = classic_round(connect)
    put(fr, beside_the_spot(SPOT["r"] + 0.5))
    told = positions_now(connections)
    for name in FOUR:
        assert fr in names_in(told[name])


def test_leaving_the_spot_makes_the_free_rider_visible_in_the_next_positions(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    assert fr not in names_in(positions_now(connections)[far])
    put(fr, beside_the_spot(SPOT["r"] + 1))
    assert fr in names_in(positions_now(connections)[far])


# Ghosts and a second Free Rider


def test_a_ghost_sees_the_hidden_free_rider_and_the_living_still_see_no_ghost(connect):
    connections, [fr], [ghost, far, _] = classic_round(connect)
    classic_for(fr).eliminated = {ghost}
    put(fr, IN_THE_SPOT)

    told = positions_now(connections)

    assert sorted(names_in(told[ghost])) == sorted(FOUR)
    assert fr not in names_in(told[far])
    assert ghost not in names_in(told[far])
    assert ghost not in names_in(told[fr])


def test_a_second_free_rider_sees_the_hidden_one(connect):
    connections, [first, second], high_performers = classic_round(connect, SIX)
    put(first, IN_THE_SPOT)
    told = positions_now(connections)
    assert first in names_in(told[second])
    for name in high_performers:
        assert first not in names_in(told[name])


def test_a_free_rider_who_is_a_ghost_does_not_hide_but_the_living_still_do_not_get_him(connect):
    connections, [ghost_fr, living_fr], [ghost_hp, *living_hps] = classic_round(connect, SIX)
    classic_for(ghost_fr).eliminated = {ghost_fr, ghost_hp}
    put(ghost_fr, IN_THE_SPOT)

    told = positions_now(connections)

    # A ghost far away sees him: a ghost does not hide.
    assert ghost_fr in names_in(told[ghost_hp])
    # The living do not get him, as Classic never sends the living a ghost.
    assert ghost_fr not in names_in(told[living_fr])
    for name in living_hps:
        assert ghost_fr not in names_in(told[name])


# A meeting and the end of the round


def test_a_meeting_does_not_reveal_the_hidden_free_rider(connect, clock):
    connections, [fr], [caller, far, _] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    clock.wait(46)  # the emergency button unlocks 45 seconds after the start
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        while connection.receive_json()["type"] != "meeting_state":
            pass
    assert classic_for(fr).phase == "meeting"

    assert fr not in names_in(positions_now(connections)[far])


def test_the_end_of_the_round_alone_sends_the_hidden_free_rider_to_everybody_again(connect):
    connections, [fr], [first, second, far] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    lobby = app.state.lobbies.lobby_of(fr)
    # The start of the round put everybody on the spawn, so the first tick
    # tells everybody where everybody stands: the far player without him.
    assert sorted(lobby.walkers.names_to_tell()) == sorted(FOUR)
    connections[fr].portal.call(REAL_TICK, 0.0)
    told = {name: next_positions(connection) for name, connection in connections.items()}
    assert fr not in names_in(told[far])
    assert lobby.walkers.names_to_tell() == []

    # Nobody moves. Two High Performers count as failed: one Free Rider
    # against one High Performer is parity, so the next tick ends the round.
    lobby.classic_round.eliminated = {first, second}
    connections[fr].portal.call(REAL_TICK, 0.0)
    assert lobby.classic_round is None
    # The tick after it sends everybody the positions, though nobody moved.
    connections[fr].portal.call(REAL_TICK, 0.0)

    for name in FOUR:
        assert fr in names_in(wait_for_positions_with(connections[name], fr)[-1])


def test_after_the_round_ended_nobody_is_hidden(connect):
    # Whatever is sent after the end: here the positions are sent at once.
    connections, [fr], [first, second, far] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    # Two High Performers failed: one Free Rider against one High Performer
    # is parity, so the Free Riders win and the round ends.
    lobby = app.state.lobbies.lobby_of(fr)
    lobby.classic_round.eliminated = {first, second}
    connections[fr].portal.call(main.tell_round_news, lobby)
    assert lobby.classic_round is None

    told = positions_now(connections)
    for name in FOUR:
        assert fr in names_in(told[name])


def test_in_the_result_phase_of_the_round_nobody_is_hidden(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(fr, IN_THE_SPOT)
    classic_for(fr).phase = "result"
    assert fr in names_in(positions_now(connections)[far])


# Outside Classic nothing changes


def test_in_the_lobby_a_player_in_a_spot_is_sent_to_everybody(connect):
    connections, _code = lobby_of(connect, ["Mara", "Tiago"])
    put("Mara", IN_THE_SPOT)
    put("Tiago", (100.0, 330.0))
    told = positions_now(connections)
    lobby = app.state.lobbies.lobby_of("Mara")
    for name in connections:
        assert told[name] == protocol.positions(lobby.walkers.positions())


def test_in_a_duel_a_player_in_a_spot_is_sent_to_everybody(connect):
    connections, _code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    put("Mara", IN_THE_SPOT)
    put("Tiago", (100.0, 330.0))
    put("Ines", (300.0, 400.0))
    told = positions_now(connections)
    lobby = app.state.lobbies.lobby_of("Mara")
    assert lobby.duel is not None and lobby.classic_round is None
    for name in connections:
        assert told[name] == protocol.positions(lobby.walkers.positions())
