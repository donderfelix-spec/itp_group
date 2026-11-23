"""DESIGN.md 5.8 and M3-3.13, M3-3.23: what a meeting does to walking, tasks and the cooldown.

- While a meeting runs nobody walks and no task can be opened; a task that
  was open when the meeting started is closed (`station_closed`).
- After the meeting everybody stands on the Main Deck (the spawn) again, and
  the Free Riders' 15-second cooldown starts again from the meeting's end.
- A player who is failed has their open task closed.
"""

import random

from rules import FAIL_COOLDOWN_SECONDS, can_fail
from server import main
from server.classic.round import ClassicRound
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_meeting_once import (
    FAIL_PLACE,
    FAR_PLACES,
    FIVE,
    a_round_in_a_meeting,
    classic_round,
    everybody_skips,
    everything_sent,
    finished,
    read_until,
    start_emergency,
    ticks,
)

STATIONS = {station["id"]: station for station in app.state.campus["stations"]}
SPAWN = (float(app.state.campus["spawn"]["x"]), float(app.state.campus["spawn"]["y"]))


def position_of(name):
    return app.state.lobbies.lobby_of(name).walkers.position_of(name)


def open_active_task(connections, lobby, name):
    """`name` stands at their one active station and opens it. Returns the station."""
    station = main.classic_task_stations(lobby.classic_round, name)[0]
    put(name, (STATIONS[station]["x"], STATIONS[station]["y"]))
    connections[name].send_json({"type": "open_station", "station": station})
    assert connections[name].receive_json()["type"] == "station_opened"
    return station


# The plain rules (ClassicRound, no network)


def test_after_a_meeting_the_living_free_rider_must_wait_the_cooldown_from_its_end():
    game, fr, high_performers = a_round_in_a_meeting()
    meeting = finished(game, {})  # nobody voted out
    ended_at = meeting["deadline"]

    game.apply_meeting_result(meeting)

    assert game.last_fail_at[fr] == ended_at
    game.positions = {name: (100.0, 100.0) for name in FIVE}
    state = game.rule_state()
    assert not can_fail(state, fr, high_performers[0], ended_at + FAIL_COOLDOWN_SECONDS - 0.01)
    assert can_fail(state, fr, high_performers[0], ended_at + FAIL_COOLDOWN_SECONDS)


def test_a_free_rider_voted_out_gets_no_cooldown_and_high_performers_never_do():
    game, fr, high_performers = a_round_in_a_meeting()
    game.apply_meeting_result(finished(game, {name: fr for name in FIVE}))
    assert fr in game.eliminated
    assert game.last_fail_at == {}


def test_the_way_back_to_the_deck_is_due_once_per_applied_meeting():
    game, _fr, _hps = a_round_in_a_meeting()
    assert game.take_back_to_the_deck() is False
    game.apply_meeting_result(finished(game, {}))
    assert game.take_back_to_the_deck() is True
    assert game.take_back_to_the_deck() is False


def test_a_meeting_without_a_readable_end_changes_no_cooldown():
    game = ClassicRound(list(FIVE), list(range(1, 12)), random.Random(7))
    game.apply_meeting_result({"phase": "result", "deadline": float("nan")})
    assert game.last_fail_at == {}
    game.apply_meeting_result({"phase": "result"})
    assert game.last_fail_at == {}


# The server


def test_after_the_meeting_everybody_stands_on_the_main_deck(connect, clock):
    connections, lobby, _fr, [caller, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    assert lobby.meeting["applied"] is True

    ticks(connections, count=1)

    for name in FIVE:
        assert position_of(name) == SPAWN


def test_right_after_the_meeting_the_free_rider_cannot_fail_and_hears_his_cooldown(connect, clock):
    connections, lobby, fr, [caller, victim, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    ticks(connections, count=1)  # everybody on the deck, the status is sent
    statuses = [m for m in everything_sent(connections[fr]) if m["type"] == "classic_fail_status"]
    assert statuses and statuses[-1]["cooldown_until"] is not None

    put(fr, FAIL_PLACE)
    put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))
    connections[fr].send_json({"type": "fail"})
    answer = connections[fr].receive_json()
    assert answer["code"] == "fail_rejected"
    assert victim not in lobby.classic_round.eliminated

    clock.wait(FAIL_COOLDOWN_SECONDS)
    connections[fr].send_json({"type": "fail"})
    assert connections[fr].receive_json()["type"] == "classic_fail"
    assert victim in lobby.classic_round.eliminated


def test_nobody_walks_during_a_meeting(connect, clock):
    connections, lobby, _fr, [caller, walker, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    before = position_of(walker)
    connections[walker].send_json({"type": "move", "dx": 1, "dy": 0})
    everything_sent(connections[walker])
    connections[walker].portal.call(main.tick, 0.5)

    assert position_of(walker) == before


def test_a_task_cannot_be_opened_during_a_meeting(connect, clock):
    connections, lobby, _fr, [caller, worker, *_] = classic_round(connect)
    start_emergency(connections, caller, clock)
    station = main.classic_task_stations(lobby.classic_round, worker)[0]
    put(worker, (STATIONS[station]["x"], STATIONS[station]["y"]))

    connections[worker].send_json({"type": "open_station", "station": station})

    assert read_until(connections[worker], "error")[-1] == {
        "type": "error",
        "code": "meeting_running",
        "message": "Tasks wait until the meeting is over.",
    }


def test_an_open_task_closes_when_a_meeting_starts_before_the_meeting_is_shown(connect, clock):
    connections, lobby, _fr, [caller, worker, *_] = classic_round(connect)
    clock.wait(46)
    station = open_active_task(connections, lobby, worker)
    put(caller, (app.state.campus["button"]["x"], app.state.campus["button"]["y"]))

    connections[caller].send_json({"type": "emergency"})

    assert connections[worker].receive_json() == {"type": "station_closed", "station": station}
    assert connections[worker].receive_json()["type"] == "meeting_state"
    assert lobby.tasks.open_station_of(worker) is None
    # Nothing was counted: the task is still the active one.
    assert main.classic_task_stations(lobby.classic_round, worker) == [station]


def test_a_failed_player_has_their_open_task_closed(connect, clock):
    connections, lobby, fr, [_hp, victim, *_] = classic_round(connect)
    station = open_active_task(connections, lobby, victim)
    for name, place in zip(FIVE, FAR_PLACES):
        if name != victim:
            put(name, place)
    put(fr, FAIL_PLACE)
    put(victim, (FAIL_PLACE[0] + 1, FAIL_PLACE[1]))

    connections[fr].send_json({"type": "fail"})

    told = read_until(connections[victim], "station_closed")
    types = [m["type"] for m in told]
    assert types.index("classic_fail") < types.index("station_closed")
    assert {"type": "station_closed", "station": station} in told
    assert lobby.tasks.open_station_of(victim) is None
