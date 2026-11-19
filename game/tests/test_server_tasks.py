"""The tasks at the stations over the WebSocket, with several players (M2-4.1, S-93).

The tick is switched off here (see conftest.py), so no `positions` messages
mix with the answers. The tests put the players where they need them, and the
server's clock for the tasks is replaced by one the tests set. How a player
with an open task stands still while the real tick runs is tested in
test_server_tasks_walking.py.
"""

import random

import pytest

from server import main, protocol
from server.main import app
from server.modes import minigames
from server.modes.minigame import Minigame

# The helpers live in task_helpers.py, where the tests of the minigames find
# them too. They are imported by name, so that every one of them can still be
# taken from this file as well. The fixtures work through this import alone.
from task_helpers import (  # noqa: F401
    BAD_STATION,
    CAMPUS,
    NEW_HOST,
    NO_STATION,
    NO_TASK_OPEN,
    NOT_IN_LOBBY,
    NOT_IN_ROUND,
    NOT_NEEDED,
    NOT_SIGNED_IN,
    PASSWORD,
    PLACEHOLDER,
    SPAWN,
    STATION,
    TASK_FAILED,
    TASK_OPEN,
    TITLES,
    TOO_FAR,
    TOO_FAST,
    Clock,
    ask,
    client,
    clock,
    close_station,
    connect,
    finish_station,
    lobby_named,
    lobby_of_two,
    open_station,
    opened,
    placeholder_at_every_station,
    round_without_duel,
    player,
    put,
    put_at_station,
    round_with_station_open,
    running_round,
    still_works,
)


# Opening: accepted


@pytest.mark.parametrize("station", [1, 2, 3, 4, 5])
def test_a_player_in_range_opens_a_station_and_gets_title_and_content(connect, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    assert open_station(mara, station) == opened(station)


def test_only_the_player_who_opened_is_told(connect):
    mara, tiago, _ = round_with_station_open(connect)
    assert still_works(tiago)
    assert still_works(mara)


def test_at_the_edge_of_the_range_the_station_opens(connect):
    mara, tiago, _ = running_round(connect)
    put("Mara", (STATION[1]["x"], STATION[1]["y"] + CAMPUS["use_range"]))
    assert open_station(mara, 1) == opened(1)


def test_two_players_can_open_the_same_station(connect):
    mara, tiago, _ = round_with_station_open(connect, 2)
    put_at_station("Tiago", 2)
    assert open_station(tiago, 2) == opened(2)


def test_the_lobby_state_does_not_change_when_a_station_opens(connect):
    mara, tiago, code = round_with_station_open(connect)
    lobby = lobby_named("Mara")
    assert main.state_of(lobby) == protocol.lobby_state(code, "Mara", lobby.players(), "duel", "round")
    assert set(main.state_of(lobby)) == {"type", "code", "host", "players", "mode", "phase"}


# Opening: standing still


def test_opening_stops_the_player(connect):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    mara.send_json({"type": "move", "dx": 1, "dy": 0})
    assert still_works(mara)
    open_station(mara, 1)
    walker = lobby_named("Mara").walkers._walkers["Mara"]
    assert (walker.dx, walker.dy) == (0, 0)


def test_moves_are_ignored_without_an_error_while_a_task_is_open(connect):
    mara, tiago, _ = round_with_station_open(connect)
    mara.send_json({"type": "move", "dx": 1, "dy": 1})
    assert still_works(mara)  # No error was sent for the move.
    walkers = lobby_named("Mara").walkers
    before = walkers.position_of("Mara")
    walkers.advance(1.0, CAMPUS)
    assert walkers.position_of("Mara") == before


def test_the_other_player_keeps_walking_while_a_task_is_open(connect):
    mara, tiago, _ = round_with_station_open(connect)
    tiago.send_json({"type": "move", "dx": 0, "dy": 1})
    assert still_works(tiago)
    walkers = lobby_named("Mara").walkers
    before = walkers.position_of("Tiago")
    walkers.advance(0.2, CAMPUS)
    assert walkers.position_of("Tiago") != before


@pytest.mark.parametrize("ending", ["close_station", "finish_station"])
def test_after_the_task_ended_the_player_walks_again(connect, clock, ending):
    mara, tiago, _ = round_with_station_open(connect, 2)
    clock.wait(5)
    ask(mara, {"type": ending})
    mara.send_json({"type": "move", "dx": 0, "dy": 1})
    assert still_works(mara)
    walkers = lobby_named("Mara").walkers
    before = walkers.position_of("Mara")
    walkers.advance(0.2, CAMPUS)
    assert walkers.position_of("Mara") != before


def test_a_rejected_open_does_not_stop_the_player(connect):
    mara, tiago, _ = running_round(connect)
    mara.send_json({"type": "move", "dx": 1, "dy": 0})
    assert open_station(mara, 1) == TOO_FAR
    walker = lobby_named("Mara").walkers._walkers["Mara"]
    assert (walker.dx, walker.dy) == (1, 0)


# Opening: rejected


def test_a_stranger_is_told_to_sign_in_first(connect):
    stranger = connect()
    for message in [{"type": "open_station", "station": 1}, {"type": "close_station"}, {"type": "finish_station"}]:
        assert ask(stranger, message) == NOT_SIGNED_IN


def test_a_player_outside_a_lobby_is_told_so(connect):
    mara = player(connect, "Mara")
    for message in [{"type": "open_station", "station": 1}, {"type": "close_station"}, {"type": "finish_station"}]:
        assert ask(mara, message) == NOT_IN_LOBBY


def test_before_the_round_starts_no_task_can_be_opened_closed_or_finished(connect):
    mara, tiago, _ = lobby_of_two(connect)
    lobby_named("Mara").walkers.advance(0.0, CAMPUS)  # Both stand on the spawn.
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == NOT_IN_ROUND
    assert close_station(mara) == NOT_IN_ROUND
    assert finish_station(mara) == NOT_IN_ROUND
    assert lobby_named("Mara").tasks is None


def test_station_6_is_not_in_use(connect):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 6)
    assert open_station(mara, 6) == NO_STATION
    assert not lobby_named("Mara").tasks.has_open_task("Mara")


@pytest.mark.parametrize("station", [0, 7, -1, 1.0, "1", True, None], ids=repr)
def test_a_station_that_cannot_be_read_is_rejected_by_the_message_check(connect, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    assert open_station(mara, station) == BAD_STATION
    assert not lobby_named("Mara").tasks.has_open_task("Mara")
    assert still_works(mara)


def test_from_the_spawn_every_station_is_too_far(connect):
    mara, tiago, _ = running_round(connect)
    for station in [1, 2, 3, 4, 5]:
        assert open_station(mara, station) == TOO_FAR
    assert not lobby_named("Mara").tasks.has_open_task("Mara")


def test_one_unit_beyond_the_range_is_too_far(connect):
    mara, tiago, _ = running_round(connect)
    put("Mara", (STATION[1]["x"], STATION[1]["y"] + CAMPUS["use_range"] + 1))
    assert open_station(mara, 1) == TOO_FAR


def test_before_the_first_tick_placed_the_player_everything_is_too_far(connect):
    mara, tiago, _ = lobby_of_two(connect)
    ask(mara, {"type": "start_game"})
    assert lobby_named("Mara").walkers.position_of("Mara") is None
    assert open_station(mara, 1) == TOO_FAR
    assert not lobby_named("Mara").tasks.has_open_task("Mara")


def test_a_second_station_cannot_be_opened_while_a_task_is_open(connect):
    mara, tiago, _ = round_with_station_open(connect, 1)
    assert open_station(mara, 1) == TASK_OPEN
    put_at_station("Mara", 2)
    assert open_station(mara, 2) == TASK_OPEN
    assert lobby_named("Mara").tasks.open_station_of("Mara") == 1


def test_a_finished_station_cannot_be_opened_again(connect, clock):
    mara, tiago, _ = round_with_station_open(connect, 3)
    clock.wait(1)
    assert finish_station(mara) == {"type": "station_done", "station": 3}
    assert open_station(mara, 3) == NOT_NEEDED
    assert not lobby_named("Mara").tasks.has_open_task("Mara")
    # The other player has not finished it and may still open it.
    put_at_station("Tiago", 3)
    assert open_station(tiago, 3) == opened(3)


# Closing


def test_closing_answers_station_closed_and_the_station_opens_again(connect):
    mara, tiago, _ = round_with_station_open(connect, 4)
    assert close_station(mara) == {"type": "station_closed", "station": 4}
    assert open_station(mara, 4) == opened(4)
    assert still_works(tiago)


def test_closing_without_an_open_task_is_rejected(connect):
    mara, tiago, _ = running_round(connect)
    assert close_station(mara) == NO_TASK_OPEN
    put_at_station("Mara", 1)
    open_station(mara, 1)
    close_station(mara)
    assert close_station(mara) == NO_TASK_OPEN


def test_a_reopened_station_draws_fresh_content(connect, monkeypatch):
    def draw_number(rng):
        return {"kind": "number", "number": rng.randrange(10**9)}

    monkeypatch.setitem(minigames.MINIGAMES, 1, Minigame(title="Sort the slides", min_seconds=1, make_content=draw_number))
    mara, tiago, _ = running_round(connect)
    # Seeded only now: the lobby code was drawn from the same generator.
    monkeypatch.setattr(main, "random", random.Random(4))
    put_at_station("Mara", 1)
    first = open_station(mara, 1)
    close_station(mara)
    second = open_station(mara, 1)
    expected = random.Random(4)
    assert first == opened(1, {"kind": "number", "number": expected.randrange(10**9)})
    assert second == opened(1, {"kind": "number", "number": expected.randrange(10**9)})
    assert first["content"] != second["content"]


# Finishing


def test_finishing_after_the_minimum_time_answers_station_done(connect, clock):
    mara, tiago, _ = round_with_station_open(connect, 5)
    clock.wait(12.5)
    assert finish_station(mara) == {"type": "station_done", "station": 5}
    assert lobby_named("Mara").tasks.finished_by("Mara") == {5}
    assert still_works(tiago)


def test_exactly_the_minimum_time_is_enough(connect, clock):
    mara, tiago, _ = round_with_station_open(connect)
    clock.wait(1)
    assert finish_station(mara) == {"type": "station_done", "station": 1}


def test_finishing_too_soon_sends_the_error_and_then_closes(connect, clock):
    mara, tiago, _ = round_with_station_open(connect, 2)
    clock.wait(0.9)
    assert finish_station(mara) == TOO_FAST
    assert mara.receive_json() == {"type": "station_closed", "station": 2}
    assert still_works(mara)
    assert lobby_named("Mara").tasks.finished_by("Mara") == set()
    assert not lobby_named("Mara").tasks.has_open_task("Mara")


def test_after_too_fast_the_station_can_be_opened_and_finished(connect, clock):
    mara, tiago, _ = round_with_station_open(connect, 2)
    finish_station(mara)
    mara.receive_json()
    assert open_station(mara, 2) == opened(2)
    clock.wait(3)
    assert finish_station(mara) == {"type": "station_done", "station": 2}


def test_finishing_without_an_open_task_is_rejected(connect, clock):
    mara, tiago, _ = running_round(connect)
    assert finish_station(mara) == NO_TASK_OPEN
    put_at_station("Mara", 1)
    open_station(mara, 1)
    clock.wait(2)
    finish_station(mara)
    assert finish_station(mara) == NO_TASK_OPEN


def test_a_player_can_finish_all_five_stations(connect, clock):
    mara, tiago, _ = running_round(connect)
    for station in [1, 2, 3, 4, 5]:
        put_at_station("Mara", station)
        assert open_station(mara, station) == opened(station)
        clock.wait(2)
        assert finish_station(mara) == {"type": "station_done", "station": station}
    assert lobby_named("Mara").tasks.finished_by("Mara") == {1, 2, 3, 4, 5}
    assert lobby_named("Mara").tasks.finished_by("Tiago") == set()


# New rounds, leaving, faults


def test_a_new_lobby_starts_with_nothing_finished(connect, clock):
    mara, tiago, _ = round_with_station_open(connect, 1)
    clock.wait(2)
    finish_station(mara)
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert tiago.receive_json() == NEW_HOST
    assert tiago.receive_json()["type"] == "lobby_state"
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert app.state.lobbies.count() == 0

    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    assert lobby_named("Mara").tasks is None
    ask(mara, {"type": "start_game"})
    tiago.receive_json()
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == opened(1)


def both_finish_one_station(mara, tiago, clock):
    """Mara finishes station 2 and Tiago station 3, so both have something to lose."""
    for connection, name, station in [(mara, "Mara", 2), (tiago, "Tiago", 3)]:
        put_at_station(name, station)
        assert open_station(connection, station) == opened(station)
        clock.wait(2)
        assert finish_station(connection) == {"type": "station_done", "station": station}


def test_leaving_with_a_task_open_forgets_it_and_disturbs_nobody(connect, clock):
    mara, tiago, code = running_round(connect)
    both_finish_one_station(mara, tiago, clock)
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == opened(1)
    lobby = lobby_named("Mara")
    assert lobby.tasks.finished_by("Mara") == {2}
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert tiago.receive_json() == NEW_HOST
    assert tiago.receive_json() == protocol.lobby_state(code, "Tiago", [("Tiago", protocol.CHARACTERS[1])], "duel", "round")
    assert not lobby.tasks.has_open_task("Mara")
    assert lobby.tasks.open_station_of("Mara") is None
    # Mara had finished station 2: an empty set shows her state was removed.
    assert lobby.tasks.finished_by("Mara") == set()
    assert lobby.tasks.open_station_of("Tiago") is None
    assert lobby.tasks.finished_by("Tiago") == {3}
    assert close_station(mara) == NOT_IN_LOBBY
    # Tiago plays on as if nothing had happened.
    put_at_station("Tiago", 1)
    assert open_station(tiago, 1) == opened(1)


def test_disconnecting_with_a_task_open_forgets_it_and_disturbs_nobody(connect, clock):
    mara, tiago, code = running_round(connect)
    both_finish_one_station(mara, tiago, clock)
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == opened(1)
    lobby = lobby_named("Mara")
    assert lobby.tasks.finished_by("Mara") == {2}
    mara.close()
    assert tiago.receive_json() == NEW_HOST
    assert tiago.receive_json()["host"] == "Tiago"
    assert lobby.tasks.open_station_of("Mara") is None
    # Mara had finished station 2: an empty set shows her state was removed.
    assert lobby.tasks.finished_by("Mara") == set()
    assert lobby.tasks.open_station_of("Tiago") is None
    assert lobby.tasks.finished_by("Tiago") == {3}
    put_at_station("Tiago", 2)
    assert open_station(tiago, 2) == opened(2)
    clock.wait(2)
    assert finish_station(tiago) == {"type": "station_done", "station": 2}


def test_a_fault_in_a_minigame_does_not_close_the_connection(connect, monkeypatch):
    def broken(rng):
        raise ValueError("this minigame is broken")

    monkeypatch.setitem(minigames.MINIGAMES, 1, Minigame(title="Sort the slides", min_seconds=1, make_content=broken))
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    # The server answers the fault with an error (review of M2-4.1): with no
    # answer the browser would wait for one forever.
    assert open_station(mara, 1) == TASK_FAILED
    assert still_works(mara)
    # The other stations still work.
    put_at_station("Mara", 2)
    assert open_station(mara, 2) == opened(2)


def test_a_fault_in_a_minigame_is_answered_with_an_error_and_the_player_can_go_on(connect, monkeypatch):
    def broken(rng):
        raise ValueError("this minigame is broken")

    monkeypatch.setitem(minigames.MINIGAMES, 1, Minigame(title="Sort the slides", min_seconds=1, make_content=broken))
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    # The browser waits for an answer to every task message, so one must come.
    assert open_station(mara, 1) == TASK_FAILED
    # No task was left open: nothing more is sent, and another station opens.
    assert not lobby_named("Mara").tasks.has_open_task("Mara")
    assert still_works(mara)
    assert still_works(tiago)
    put_at_station("Mara", 2)
    assert open_station(mara, 2) == opened(2)


def test_a_fault_after_the_task_was_opened_forgets_the_task_and_tells_the_player(connect, monkeypatch):
    def broken(station, title, content):
        raise ValueError("the answer could not be built")

    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    with monkeypatch.context() as patched:
        patched.setattr(protocol, "station_opened", broken)
        # The error comes first, then the news that the task is closed.
        assert open_station(mara, 1) == TASK_FAILED
        assert mara.receive_json() == {"type": "station_closed", "station": 1}
    assert not lobby_named("Mara").tasks.has_open_task("Mara")
    assert still_works(mara)
    # The same station opens again, and nothing counted as finished.
    assert lobby_named("Mara").tasks.finished_by("Mara") == set()
    assert open_station(mara, 1) == opened(1)


def test_a_fault_while_closing_or_finishing_is_answered_too(connect, monkeypatch):
    def broken(station):
        raise ValueError("the answer could not be built")

    mara, tiago, _ = round_with_station_open(connect, 1)
    with monkeypatch.context() as patched:
        patched.setattr(protocol, "station_closed", broken)
        # The rules had closed the task before the fault: only the error comes.
        assert close_station(mara) == TASK_FAILED
    assert still_works(mara)
    assert open_station(mara, 1) == opened(1)


def test_a_fault_while_finishing_leaves_nothing_open(connect, monkeypatch, clock):
    def broken(station):
        raise ValueError("the answer could not be built")

    mara, tiago, _ = round_with_station_open(connect, 1)
    clock.wait(2)
    with monkeypatch.context() as patched:
        patched.setattr(protocol, "station_done", broken)
        # Only the error comes: no `station_closed` follows it.
        assert finish_station(mara) == TASK_FAILED
    assert still_works(mara)
    assert not lobby_named("Mara").tasks.has_open_task("Mara")
    assert lobby_named("Mara").tasks.open_station_of("Mara") is None
    # The player is not stuck: closing finds no task, and another station opens.
    assert close_station(mara) == NO_TASK_OPEN
    put_at_station("Mara", 2)
    assert open_station(mara, 2) == opened(2)
    assert still_works(tiago)


def test_a_fault_is_logged_by_its_kind_only(connect, monkeypatch, caplog):
    def broken(rng):
        raise ValueError("secret detail")

    monkeypatch.setitem(minigames.MINIGAMES, 1, Minigame(title="Sort the slides", min_seconds=1, make_content=broken))
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == TASK_FAILED
    assert "ValueError" in caplog.text
    assert "secret detail" not in caplog.text
