"""What the play test of the minigame frame did in the browser (M2-4.1, S-93).

Two players in a round, as in the browser: opening, closing and finishing
tasks in quick succession, leaving in every way while a window is open, and
messages the page itself would never send. test_server_tasks.py tests each
rule of the tasks on its own; these tests replay the sequences that were
played, so they run again on every later change.

The tick is switched off (see conftest.py) and the players are put where
they need to be, as in test_server_tasks.py.
"""

import contextlib

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app

# Used by every test here without being asked for: the placeholder stands at
# all five stations, whatever real minigames the game has by now.
from task_helpers import placeholder_at_every_station  # noqa: F401

PASSWORD = "password123"
CAMPUS = app.state.campus
STATION = {station["id"]: station for station in CAMPUS["stations"]}
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])

NOT_SIGNED_IN = {"type": "error", "code": "not_signed_in", "message": "Log in or play as a guest first."}
NOT_IN_LOBBY = {"type": "error", "code": "not_in_lobby", "message": "You are not in a lobby."}
NOT_NEEDED = {"type": "error", "code": "station_not_needed", "message": "You do not need that station."}
TASK_OPEN = {"type": "error", "code": "task_open", "message": "Close your current task first."}
NO_TASK_OPEN = {"type": "error", "code": "no_task_open", "message": "You have no task open."}
TOO_FAST = {"type": "error", "code": "too_fast", "message": "That was too fast. Try again."}
UNKNOWN_TYPE = {"type": "error", "code": "unknown_type", "message": "The server does not know that action."}

TITLES = {1: "Sort the slides", 2: "Brew the order", 3: "Build the tray", 4: "Shelve the books", 5: "Self-checkout"}


class Clock:
    """The server's clock for the tasks, set by the test."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    test_clock = Clock()
    monkeypatch.setattr(main, "seconds_now", test_clock)
    return test_clock


@pytest.fixture
def connect():
    """A function that opens one more connection. All of them are closed after the test."""
    with TestClient(app) as client, contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def news(connection):
    """Everything the server sent this connection since the last question.

    A `hello` is answered with `welcome`, so all messages before that answer
    were waiting already.
    """
    connection.send_json({"type": "hello", "name": "Mara"})
    waiting = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return waiting
        waiting.append(message)


def player(connect, name):
    connection = connect()
    assert ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def start_round(host, member):
    """The host creates a lobby, the member joins, the host starts the round."""
    code = ask(host, {"type": "create_lobby"})["code"]
    assert ask(member, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    news(host)  # the host is told that the member joined
    assert ask(host, {"type": "start_game"})["phase"] == "round"
    news(host)
    news(member)
    return code


def running_round(connect):
    """A round of Mara (host) and Tiago. Both stand on the spawn and have read everything."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = start_round(mara, tiago)
    put("Mara", SPAWN)
    put("Tiago", SPAWN)
    return mara, tiago, code


def lobby_named(name):
    return app.state.lobbies.lobby_of(name)


def put(name, position):
    """Place a player on the map, as the tick would after a long walk."""
    lobby_named(name).walkers._walkers[name].position = (float(position[0]), float(position[1]))


def put_at_station(name, station):
    put(name, (STATION[station]["x"], STATION[station]["y"]))


def opened(station):
    return {"type": "station_opened", "station": station, "title": TITLES[station], "content": {"kind": "placeholder"}}


def closed(station):
    return {"type": "station_closed", "station": station}


def done(station):
    return {"type": "station_done", "station": station}


OPEN_5 = {"type": "open_station", "station": 5}
CLOSE = {"type": "close_station"}
FINISH = {"type": "finish_station"}


# The same action several times, quickly


def test_ten_quick_openings_and_closings_leave_nothing_stuck(connect, clock):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    for _ in range(10):
        mara.send_json(OPEN_5)
        mara.send_json(CLOSE)
    assert news(mara) == [opened(5), closed(5)] * 10
    tasks = lobby_named("Mara").tasks
    assert not tasks.has_open_task("Mara")
    assert tasks.finished_by("Mara") == set()
    # Afterwards the station opens, can be finished, and the player walks.
    assert ask(mara, OPEN_5) == opened(5)
    clock.wait(2)
    assert ask(mara, FINISH) == done(5)
    mara.send_json({"type": "move", "dx": 1, "dy": 0})
    assert news(mara) == []
    walkers = lobby_named("Mara").walkers
    before = walkers.position_of("Mara")
    walkers.advance(0.2, CAMPUS)
    assert walkers.position_of("Mara") != before


def test_two_openings_sent_together_open_one_task(connect):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    mara.send_json(OPEN_5)
    mara.send_json(OPEN_5)
    assert news(mara) == [opened(5), TASK_OPEN]
    assert lobby_named("Mara").tasks.open_station_of("Mara") == 5
    assert ask(mara, CLOSE) == closed(5)


def test_two_finishes_sent_together_count_the_station_once(connect, clock):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    assert ask(mara, OPEN_5) == opened(5)
    clock.wait(2)
    mara.send_json(FINISH)
    mara.send_json(FINISH)
    assert news(mara) == [done(5), NO_TASK_OPEN]
    assert lobby_named("Mara").tasks.finished_by("Mara") == {5}
    assert ask(mara, OPEN_5) == NOT_NEEDED


def test_opening_and_finishing_at_once_is_too_fast_every_time_and_never_counts(connect, clock):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    for _ in range(3):
        mara.send_json(OPEN_5)
        mara.send_json(FINISH)
        assert news(mara) == [opened(5), TOO_FAST, closed(5)]
    assert lobby_named("Mara").tasks.finished_by("Mara") == set()
    assert ask(mara, OPEN_5) == opened(5)
    clock.wait(1)
    assert ask(mara, FINISH) == done(5)


# Only the player who acts hears about tasks


def test_the_other_player_hears_nothing_of_a_whole_task(connect, clock):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    assert ask(mara, OPEN_5) == opened(5)
    assert ask(mara, OPEN_5) == TASK_OPEN
    assert ask(mara, CLOSE) == closed(5)
    assert ask(mara, CLOSE) == NO_TASK_OPEN
    ask(mara, OPEN_5)
    mara.send_json(FINISH)
    assert news(mara) == [TOO_FAST, closed(5)]
    ask(mara, OPEN_5)
    clock.wait(2)
    assert ask(mara, FINISH) == done(5)
    assert ask(mara, OPEN_5) == NOT_NEEDED
    assert news(tiago) == []


@pytest.mark.parametrize("message_type", ["station_opened", "station_closed", "station_done"])
def test_a_browser_cannot_send_the_messages_of_the_server(connect, message_type):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", 5)
    forged = {"type": message_type, "station": 5, "title": TITLES[5], "content": {"kind": "placeholder"}}
    assert ask(mara, forged) == UNKNOWN_TYPE
    tasks = lobby_named("Mara").tasks
    assert not tasks.has_open_task("Mara")
    assert tasks.finished_by("Mara") == set()
    assert news(tiago) == []


# Leaving while windows are open


def test_the_host_leaves_while_the_other_player_has_a_task_open(connect, clock):
    mara, tiago, code = running_round(connect)
    put_at_station("Mara", 5)
    put_at_station("Tiago", 5)
    assert ask(mara, OPEN_5) == opened(5)
    assert ask(tiago, OPEN_5) == opened(5)
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    told = news(tiago)
    assert told[0] == {"type": "notice", "message": "The host left. Tiago is the new host."}
    assert [message["type"] for message in told] == ["notice", "lobby_state"]
    assert (told[1]["host"], told[1]["phase"]) == ("Tiago", "round")
    # Tiago's task is still open and counts when he finishes it.
    assert lobby_named("Tiago").tasks.open_station_of("Tiago") == 5
    clock.wait(2)
    assert ask(tiago, FINISH) == done(5)
    # Mara is at Home: no task, no lobby.
    assert ask(mara, OPEN_5) == NOT_IN_LOBBY
    assert ask(mara, FINISH) == NOT_IN_LOBBY


def test_logging_out_with_a_task_open_forgets_it_and_the_other_plays_on(connect, clock):
    mara, tiago, _ = running_round(connect)
    put_at_station("Tiago", 5)
    assert ask(tiago, OPEN_5) == opened(5)
    lobby = lobby_named("Tiago")
    assert ask(tiago, {"type": "log_out"}) == {"type": "signed_out"}
    assert lobby.tasks.open_station_of("Tiago") is None
    assert ask(tiago, CLOSE) == NOT_SIGNED_IN
    assert ask(tiago, FINISH) == NOT_SIGNED_IN
    told = news(mara)
    assert [message["type"] for message in told] == ["lobby_state"]
    put_at_station("Mara", 5)
    assert ask(mara, OPEN_5) == opened(5)
    clock.wait(2)
    assert ask(mara, FINISH) == done(5)


def test_guests_who_all_left_start_a_new_round_with_nothing_finished(connect, clock):
    """The browser players are guests: the names come from the server."""
    first, second = connect(), connect()
    first_name = ask(first, {"type": "guest"})["name"]
    second_name = ask(second, {"type": "guest"})["name"]
    start_round(first, second)
    put_at_station(first_name, 5)
    put_at_station(second_name, 5)
    for connection in (first, second):
        assert ask(connection, OPEN_5) == opened(5)
        clock.wait(2)
        assert ask(connection, FINISH) == done(5)
    # The first leaves with a window open at another station, then the second.
    put_at_station(first_name, 3)
    assert ask(first, {"type": "open_station", "station": 3}) == opened(3)
    assert ask(first, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    news(second)
    assert ask(second, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert app.state.lobbies.count() == 0

    start_round(second, first)
    for name, connection in ((first_name, first), (second_name, second)):
        assert lobby_named(name).tasks.finished_by(name) == set()
        assert not lobby_named(name).tasks.has_open_task(name)
        put_at_station(name, 5)
        assert ask(connection, OPEN_5) == opened(5)
