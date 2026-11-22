"""Hiding through the real server: who is sent a Free Rider in a hiding spot (M3-1.4).

`tell_positions` sends every member the positions. In a Classic round a
living Free Rider who hides is left out for every living High Performer, at
any distance (S-192; before, he was sent within 35 map units, S-133). Since
M3-1.6 (S-191) he hides by pressing E at a hiding object (`hide_at` below),
not by standing in the spot, and a meeting ends hiding (replaces S-138).
Ghosts see him (S-136), other Free Riders see him (S-137). Classic's own
filter stays: the living are never sent the ghosts. Ordinary Classic sight
also applies to the living, including Free Riders. Outside Classic nothing
changes.

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
# Clear sight lines from outside the 35-unit hiding reveal range to each spot.
SPOT_WATCHERS = [(640.0, 249.0), (549.0, 513.0), (91.0, 524.0), (591.0, 128.0)]
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


def hide_at(connections, name, place):
    """Put the Free Rider at `place` and press E there (M3-1.6): he hides.

    The server puts him on the spot's centre and sends everybody the
    positions at once; those are read here, so the next `positions_now`
    gets fresh ones.
    """
    put(name, place)
    connections[name].send_json({"type": "hide"})
    while True:
        message = connections[name].receive_json()
        assert message["type"] != "error", message
        if message["type"] == "classic_hiding":
            assert message["hidden"] is True
            break
    for connection in connections.values():
        next_positions(connection)


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


def test_a_hidden_free_rider_is_left_out_for_high_performers_at_any_distance(connect):
    # Before S-192: left out beyond 35 and sent within 35. Now never sent.
    connections, [fr], [far, at_35, near] = classic_round(connect)
    hide_at(connections, fr, IN_THE_SPOT)
    put(far, beside_the_spot(35.5))
    put(at_35, beside_the_spot(35))
    put(near, (SPOT["x"], SPOT["y"] + 20))

    told = positions_now(connections)

    assert fr not in names_in(told[far])
    assert fr not in names_in(told[at_35])
    assert fr not in names_in(told[near])
    # The Free Rider himself gets everybody, his own position included,
    # and is told that he hides (S-192).
    assert sorted(names_in(told[fr])) == sorted(FOUR)
    assert [entry.get("hidden") for entry in told[fr]["players"] if entry["name"] == fr] == [True]


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_one_of_the_four_spots_hides_the_free_rider(connect, index):
    connections, [fr], high_performers = classic_round(connect)
    spot = CAMPUS["hiding_spots"][index]
    for name in high_performers:
        put(name, SPOT_WATCHERS[index])
    put(fr, SPOT_WATCHERS[index])
    seen_before = positions_now(connections)
    assert all(fr in names_in(seen_before[name]) for name in high_performers)

    hide_at(connections, fr, (spot["x"], spot["y"]))
    told = positions_now(connections)
    for name in high_performers:
        assert fr not in names_in(told[name])


def test_pressing_e_on_the_edge_of_the_spot_still_hides(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(far, SPOT_WATCHERS[0])
    hide_at(connections, fr, (SPOT["x"], SPOT["y"] - SPOT["r"]))
    assert fr not in names_in(positions_now(connections)[far])


def test_the_message_to_a_far_player_carries_no_trace_of_the_hidden_free_rider(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    for name in FOUR:
        put(name, SPOT_WATCHERS[0])
    hide_at(connections, fr, IN_THE_SPOT)
    lobby = app.state.lobbies.lobby_of(fr)
    others = [entry for entry in lobby.walkers.positions() if entry[0] != fr]

    message = positions_now(connections)[far]

    # Exactly the message of the others, in the usual format: nothing added.
    assert message == protocol.positions(others)
    assert set(message) == {"type", "players"}
    assert all(set(entry) == {"name", "x", "y"} for entry in message["players"])
    assert fr not in json.dumps(message)


def test_a_free_rider_walking_into_the_spot_disappears_only_when_he_presses_e(connect):
    # Since M3-1.6 (S-191) walking in does not hide: he is seen on every step.
    connections, [fr], [far, _, _] = classic_round(connect)
    # Below the hedge; three steps of 9 units up end in the spot, at y 253.
    put(far, SPOT_WATCHERS[0])
    put(fr, (595.0, 280.0))
    lobby = app.state.lobbies.lobby_of(fr)
    lobby.walkers.set_direction(fr, 0, -1)
    seen_by_far = []
    for _ in range(3):
        connections[fr].portal.call(REAL_TICK, 0.1)
        seen_by_far.append(names_in(next_positions(connections[far])))
    lobby.walkers.set_direction(fr, 0, 0)

    assert lobby.walkers.position_of(fr) == (595.0, 253.0)
    assert [fr in seen for seen in seen_by_far] == [True, True, True]
    connections[fr].send_json({"type": "hide"})
    connections[fr].portal.call(REAL_TICK, 0.0)
    assert fr not in names_in(next_positions(connections[far]))


# Accepted: nobody else hides


def test_a_high_performer_in_a_spot_is_sent_to_everybody_in_sight(connect):
    connections, [fr], [in_spot, far, _] = classic_round(connect)
    for name in FOUR:
        put(name, SPOT_WATCHERS[0])
    put(in_spot, IN_THE_SPOT)
    told = positions_now(connections)
    for name in FOUR:
        assert in_spot in names_in(told[name])
    assert fr in names_in(told[far])


def test_a_free_rider_outside_every_spot_is_sent_to_everybody_in_sight(connect):
    connections, [fr], _ = classic_round(connect)
    for name in FOUR:
        put(name, SPOT_WATCHERS[0])
    put(fr, beside_the_spot(SPOT["r"] + 0.5))
    told = positions_now(connections)
    for name in FOUR:
        assert fr in names_in(told[name])


def test_leaving_the_spot_makes_the_free_rider_visible_in_the_next_positions(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(far, SPOT_WATCHERS[0])
    hide_at(connections, fr, IN_THE_SPOT)
    assert fr not in names_in(positions_now(connections)[far])
    # Since S-191 he leaves by a step (a move message), not by being put.
    connections[fr].send_json({"type": "move", "dx": 1, "dy": 0})
    put(fr, beside_the_spot(SPOT["r"] + 1))
    assert fr in names_in(positions_now(connections)[far])


# Ghosts and a second Free Rider


def test_a_ghost_sees_the_hidden_free_rider_and_the_living_still_see_no_ghost(connect):
    connections, [fr], [ghost, far, _] = classic_round(connect)
    classic_for(fr).eliminated = {ghost}
    hide_at(connections, fr, IN_THE_SPOT)

    told = positions_now(connections)

    assert sorted(names_in(told[ghost])) == sorted(FOUR)
    # The ghost is told that he hides (S-192).
    assert [entry.get("hidden") for entry in told[ghost]["players"] if entry["name"] == fr] == [True]
    assert fr not in names_in(told[far])
    assert ghost not in names_in(told[far])
    assert ghost not in names_in(told[fr])


def test_a_second_free_rider_sees_the_hidden_one(connect):
    connections, [first, second], high_performers = classic_round(connect, SIX)
    for name in [second, *high_performers]:
        put(name, SPOT_WATCHERS[0])
    hide_at(connections, first, IN_THE_SPOT)
    told = positions_now(connections)
    assert first in names_in(told[second])
    # The other Free Rider is told that he hides (S-192).
    assert [entry.get("hidden") for entry in told[second]["players"] if entry["name"] == first] == [True]
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


def test_a_meeting_ends_hiding_and_reveals_the_free_rider(connect, clock):
    # Since M3-1.6 (S-191) a meeting ends hiding (replaces S-138).
    connections, [fr], [caller, far, _] = classic_round(connect)
    put(far, SPOT_WATCHERS[0])
    hide_at(connections, fr, IN_THE_SPOT)
    button = CAMPUS["button"]
    put(caller, (button["x"], button["y"]))
    clock.wait(46)  # the emergency button unlocks 45 seconds after the start
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        while True:
            message = connection.receive_json()
            assert message["type"] != "error", message
            if message["type"] == "meeting_state":
                break
    assert classic_for(fr).phase == "meeting"

    assert fr in names_in(positions_now(connections)[far])


def test_the_end_of_the_round_alone_sends_the_hidden_free_rider_to_everybody_again(connect):
    connections, [fr], [first, second, far] = classic_round(connect)
    put(far, SPOT_WATCHERS[0])
    hide_at(connections, fr, IN_THE_SPOT)
    lobby = app.state.lobbies.lobby_of(fr)
    # As at the start of the round, everybody is to be told where everybody
    # stands, so the first tick tells everybody: the far player without him.
    lobby.walkers.everybody_needs_news()
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
    hide_at(connections, fr, IN_THE_SPOT)
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
    put(far, SPOT_WATCHERS[0])
    hide_at(connections, fr, IN_THE_SPOT)
    classic_for(fr).phase = "result"
    assert fr in names_in(positions_now(connections)[far])


# Ordinary Classic sight, independent of the hiding spots.


@pytest.mark.parametrize(
    ("viewer_at", "other_at", "visible"),
    [
        ((500.0, 390.0), (500.0, 410.0), False),  # Pingo Doce wall
        ((540.0, 390.0), (540.0, 410.0), True),   # its door
        ((500.0, 330.0), (620.0, 330.0), True),   # 120 units exactly
        ((500.0, 330.0), (620.1, 330.0), False),
    ],
)
def test_classic_sight_obeys_walls_and_range(connect, viewer_at, other_at, visible):
    connections, [fr], [hp, _, _] = classic_round(connect)
    put(fr, viewer_at)
    put(hp, other_at)

    told = positions_now(connections)

    assert fr in names_in(told[fr]) and hp in names_in(told[hp])
    assert (hp in names_in(told[fr])) is visible
    assert (fr in names_in(told[hp])) is visible


@pytest.mark.parametrize("phase", ["round", "meeting", "result"])
def test_classic_sight_holds_in_every_phase(connect, phase):
    connections, [fr], [hp, _, _] = classic_round(connect)
    put(fr, (500.0, 390.0))
    put(hp, (500.0, 410.0))  # behind the wall of Pingo Doce
    classic_for(fr).phase = phase

    told = positions_now(connections)

    assert hp not in names_in(told[fr])
    assert fr not in names_in(told[hp])


@pytest.mark.parametrize("place", [(500.0, 390.0), (100.0, 330.0)], ids=["behind a wall", "beyond the range"])
def test_the_other_free_rider_sees_a_hidden_one_only_in_his_sight(connect, place):
    connections, [first, second], _ = classic_round(connect, SIX)
    put(first, IN_THE_SPOT)
    put(second, place)

    told = positions_now(connections)

    assert first not in names_in(told[second])


def test_a_player_who_just_became_a_ghost_gets_the_full_view_at_once(connect):
    connections, [fr], [victim, beyond_wall, far] = classic_round(connect)
    put(victim, (500.0, 390.0))
    put(beyond_wall, (500.0, 410.0))
    put(far, (100.0, 330.0))
    put(fr, (650.0, 128.0))
    assert names_in(positions_now(connections)[victim]) == [victim]

    classic_for(fr).eliminated = {victim}

    assert sorted(names_in(positions_now(connections)[victim])) == sorted(FOUR)


def test_ghost_sight_ignores_walls_and_range_in_classic(connect):
    connections, [fr], [ghost, beyond_wall, far] = classic_round(connect)
    classic_for(fr).eliminated = {ghost}
    put(ghost, (500.0, 390.0))
    put(beyond_wall, (500.0, 410.0))
    put(far, (100.0, 330.0))

    told = positions_now(connections)

    assert sorted(names_in(told[ghost])) == sorted(FOUR)
    assert all(ghost not in names_in(told[name]) for name in (fr, beyond_wall, far))


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
