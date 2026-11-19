"""Helpers for tests that play tasks through the real server (M2-4.1, S-93).

Tests of the minigames should take their helpers from here: start a round
(`running_round`), place a player at a station (`put_at_station`), open,
close and finish (`open_station`, `close_station`, `finish_station`) and set
the server's clock for the tasks (`clock`).

The fixtures (`clock`, `client`, `connect`, `placeholder_at_every_station`)
work in a test file once they are imported there by name:

    from task_helpers import client, clock, connect  # noqa: F401

`clock` is used by every test of a file that imports it, asked for or not.
So is `placeholder_at_every_station`: the tests of the frame import it, a
test of a real minigame leaves it out, so its own minigame stays at its station.
"""

import contextlib

import pytest
from fastapi.testclient import TestClient

from server import main, protocol
from server.main import app
from server.modes import minigames
from server.modes.placeholder import placeholder

PASSWORD = "password123"
CAMPUS = app.state.campus
STATION = {station["id"]: station for station in CAMPUS["stations"]}
SPAWN = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])

NOT_SIGNED_IN = protocol.rejection("not_signed_in")
NOT_IN_LOBBY = protocol.rejection("not_in_lobby")
NOT_IN_ROUND = {"type": "error", "code": "not_in_round", "message": "No round is running."}
NO_STATION = {"type": "error", "code": "no_station", "message": "That station does not exist."}
BAD_STATION = {"type": "error", "code": "bad_station", "message": "That station does not exist."}
TOO_FAR = {"type": "error", "code": "too_far", "message": "You are too far away."}
NOT_NEEDED = {"type": "error", "code": "station_not_needed", "message": "You do not need that station."}
TASK_OPEN = {"type": "error", "code": "task_open", "message": "Close your current task first."}
NO_TASK_OPEN = {"type": "error", "code": "no_task_open", "message": "You have no task open."}
TOO_FAST = {"type": "error", "code": "too_fast", "message": "That was too fast. Try again."}

NEW_HOST = {"type": "notice", "message": "The host left. Tiago is the new host."}

PLACEHOLDER = {"kind": "placeholder"}
TASK_FAILED = {"type": "error", "code": "task_failed", "message": "Something went wrong. Try again."}

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


@pytest.fixture(autouse=True)
def placeholder_at_every_station(monkeypatch):
    """Put the placeholder at all five stations while a test of the frame runs.

    The frame's tests check opening, closing and finishing, not which
    minigame is at which station. With the placeholder everywhere they know
    the content and the minimum time (1 second), whatever real minigames
    `server/modes/minigames.py` holds by now.

    The whole table is replaced, before the round starts: a `RoundTasks`
    takes the table that is in `minigames.MINIGAMES` when it is made. A test
    can still put its own minigame at one station with `monkeypatch.setitem`.
    """
    table = {station: placeholder(title) for station, title in TITLES.items()}
    monkeypatch.setattr(minigames, "MINIGAMES", table)


@pytest.fixture
def client():
    # One event loop for all connections, like the real server (see test_server_lobby.py).
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def player(connect, name):
    """A new connection, signed in with a new account of this name."""
    connection = connect()
    assert ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def still_works(connection):
    """True if the next message is the answer to a hello: nothing else was waiting."""
    return ask(connection, {"type": "hello", "name": "Mara"})["type"] == "welcome"


def lobby_of_two(connect):
    """Mara creates a lobby and Tiago joins. Both have read every state so far."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    return mara, tiago, code


def running_round(connect):
    """A round of Mara and Tiago. Both stand on the spawn, as after the first tick."""
    mara, tiago, code = lobby_of_two(connect)
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    tiago.receive_json()
    put("Mara", SPAWN)
    put("Tiago", SPAWN)
    return mara, tiago, code


def lobby_named(name):
    return app.state.lobbies.lobby_of(name)


def put(name, position):
    """Place a player on the map, as the tick would after a long walk.

    Walking to a station takes many seconds of real time, so the tests write
    the position where the tick writes it.
    """
    lobby_named(name).walkers._walkers[name].position = (float(position[0]), float(position[1]))


def put_at_station(name, station):
    put(name, (STATION[station]["x"], STATION[station]["y"]))


def open_station(connection, station):
    return ask(connection, {"type": "open_station", "station": station})


def close_station(connection):
    return ask(connection, {"type": "close_station"})


def finish_station(connection):
    return ask(connection, {"type": "finish_station"})


def opened(station, content=PLACEHOLDER):
    return {"type": "station_opened", "station": station, "title": TITLES[station], "content": content}


def round_with_station_open(connect, station=1):
    """A running round in which Mara has the minigame of `station` open."""
    mara, tiago, code = running_round(connect)
    put_at_station("Mara", station)
    assert open_station(mara, station) == opened(station)
    return mara, tiago, code
