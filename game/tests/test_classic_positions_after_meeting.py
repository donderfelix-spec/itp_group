"""S-213: after a meeting everybody goes on from where they stood (replaces S-199 point 4).

The checks of what staying in place could open up:
- a player voted out stays where they stood, as a ghost, and the living
  next to them are still not sent the ghost (rule 1, M3-3.20);
- a Free Rider who stood beside a High Performer when the meeting began
  cannot fail him at once afterwards: the cooldown starts from the
  meeting's end (S-199 point 5), and he can once it has run out;
- a Free Rider who hid when the meeting began stands, visible, on the
  hiding spot's centre, a free place, and walks on from there;
- the next round still starts everybody on the spawn of the Main Deck.
The positions kept across a meeting and the sheets that come into sight
are in test_classic_after_meeting.py and test_classic_fail_place_in_sight.py.
"""

from rules import FAIL_COOLDOWN_SECONDS
from server.main import app
from server.world.movement import is_free
from task_helpers import client, clock, connect, put  # noqa: F401
from test_classic_meeting_once import (
    FAIL_PLACE,
    FIVE,
    classic_round,
    everybody_skips,
    everybody_votes,
    everything_sent,
    read_until,
    start_emergency,
    ticks,
)
from test_server_duel import REAL_TICK

CAMPUS = app.state.campus
SPAWN = (float(CAMPUS["spawn"]["x"]), float(CAMPUS["spawn"]["y"]))
BESIDE = (FAIL_PLACE[0] + 1, FAIL_PLACE[1])


def position_of(name):
    return app.state.lobbies.lobby_of(name).walkers.position_of(name)


def names_in_last_positions(messages):
    last = [m for m in messages if m["type"] == "positions"][-1]
    return {player["name"] for player in last["players"]}


def test_a_player_voted_out_stays_in_place_and_the_living_beside_them_are_not_sent_the_ghost(connect, clock):
    connections, lobby, fr, [caller, out, watcher, _other] = classic_round(connect)
    put(out, FAIL_PLACE)
    put(watcher, BESIDE)
    lobby.walkers.everybody_needs_news()
    ticks(connections, count=1)
    assert out in names_in_last_positions(everything_sent(connections[watcher]))  # seen while living
    for connection in connections.values():
        everything_sent(connection)
    start_emergency(connections, caller, clock)

    told = everybody_votes(connections, lobby, clock, lambda voter: out if voter != out else watcher)

    assert lobby.classic_round.eliminated == {out}
    assert position_of(out) == FAIL_PLACE and position_of(watcher) == BESIDE
    ticks(connections, count=2)
    for name in (watcher, caller, fr):
        assert out not in names_in_last_positions(told[name] + everything_sent(connections[name])), name
    assert watcher in names_in_last_positions(told[out] + everything_sent(connections[out]))


def test_a_free_rider_beside_a_high_performer_cannot_fail_him_right_after_the_meeting(connect, clock):
    connections, lobby, fr, [caller, victim, *_] = classic_round(connect)
    put(fr, FAIL_PLACE)
    put(victim, BESIDE)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    assert position_of(fr) == FAIL_PLACE and position_of(victim) == BESIDE

    connections[fr].send_json({"type": "fail"})
    refused = read_until(connections[fr], "error")[-1]
    assert refused["code"] == "fail_rejected" and "fail again" in refused["message"]
    assert victim not in lobby.classic_round.eliminated

    clock.wait(FAIL_COOLDOWN_SECONDS)
    ticks(connections, count=1)
    connections[fr].send_json({"type": "fail"})
    assert read_until(connections[fr], "classic_fail")[-1]["target_id"] == victim
    assert victim in lobby.classic_round.eliminated


def test_a_free_rider_who_hid_stands_visible_on_the_spot_and_walks_on_from_there(connect, clock):
    connections, lobby, fr, [caller, watcher, *_] = classic_round(connect)
    spot = CAMPUS["hiding_spots"][0]
    put(fr, (spot["x"], spot["y"]))
    connections[fr].send_json({"type": "hide"})
    assert read_until(connections[fr], "classic_hiding")[-1]["hidden"] is True
    for connection in connections.values():
        everything_sent(connection)  # the positions sent after he hid
    # As start_emergency, but the meeting first tells him that hiding ended (S-191).
    clock.wait(46)
    put(caller, (CAMPUS["button"]["x"], CAMPUS["button"]["y"]))
    connections[caller].send_json({"type": "emergency"})
    for connection in connections.values():
        read_until(connection, "meeting_state")
    everybody_skips(connections, lobby, clock)

    place = position_of(fr)
    assert place == (spot["x"], spot["y"])
    assert is_free(place[0], place[1], CAMPUS["solids"], CAMPUS["width"], CAMPUS["height"])
    assert not lobby.classic_round.is_hidden(fr)

    # A living High Performer in sight, beyond the reveal range of 35 units, is sent him.
    put(watcher, (spot["x"] - 50, spot["y"]))
    lobby.walkers.everybody_needs_news()
    ticks(connections, count=1)
    assert fr in names_in_last_positions(everything_sent(connections[watcher]))

    connections[fr].send_json({"type": "move", "dx": 0, "dy": 1})
    first = next(iter(connections.values()))
    for _ in range(4):
        first.portal.call(REAL_TICK, 0.1)
    assert position_of(fr) != place


def test_the_next_round_starts_everybody_on_the_spawn(connect, clock):
    connections, lobby, fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_votes(connections, lobby, clock, lambda voter: fr if voter != fr else caller, last="lobby_state")
    assert lobby.classic_round is None
    assert any(position_of(name) != SPAWN for name in FIVE)  # the round ended where they stood

    connections[FIVE[0]].send_json({"type": "start_game"})
    for connection in connections.values():
        read_until(connection, "lobby_state")
    ticks(connections, count=1)

    assert {name: position_of(name) for name in FIVE} == {name: SPAWN for name in FIVE}
