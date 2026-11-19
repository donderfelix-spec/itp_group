"""A task open while the real tick runs: who stands still and who hears what (M2-4.1).

The tick runs in the background here, as in test_server_walking.py. These
tests never count ticks: they wait, with a generous deadline, for what they expect.
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server.main import app

CAMPUS = app.state.campus
STATION_2 = next(station for station in CAMPUS["stations"] if station["id"] == 2)
SPAWN = {"x": CAMPUS["spawn"]["x"], "y": CAMPUS["spawn"]["y"]}
STATION_MESSAGES = ("station_opened", "station_closed", "station_done")


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture
def client():
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def read_until(connection, wanted, seen, seconds=5.0):
    """Read this player's messages until `wanted(message)` is true. Returns that message.

    Every message read on the way is added to the list `seen`.
    """
    deadline = time.monotonic() + seconds
    while True:
        assert time.monotonic() < deadline, "the expected message did not arrive in time"
        message = connection.receive_json()
        seen.append(message)
        if wanted(message):
            return message


def of_type(message_type):
    return lambda message: message["type"] == message_type


def place_of(name, positions_message):
    for listed in positions_message["players"]:
        if listed["name"] == name:
            return {"x": listed["x"], "y": listed["y"]}
    return None


def stands_at(name, place):
    return lambda message: message["type"] == "positions" and place_of(name, message) == place


def has_left(name, place):
    def wanted(message):
        return message["type"] == "positions" and place_of(name, message) not in (None, place)
    return wanted


def guest(connect, seen):
    connection = connect()
    connection.send_json({"type": "guest"})
    name = read_until(connection, of_type("signed_in"), seen)["name"]
    return connection, name


def test_a_player_with_a_task_open_stands_still_and_the_other_walks_on(connect):
    seen_by_first, seen_by_second = [], []
    first, first_name = guest(connect, seen_by_first)
    second, second_name = guest(connect, seen_by_second)
    first.send_json({"type": "create_lobby"})
    code = read_until(first, of_type("lobby_state"), seen_by_first)["code"]
    second.send_json({"type": "join_lobby", "code": code})
    read_until(second, of_type("lobby_state"), seen_by_second)
    first.send_json({"type": "start_game"})
    read_until(first, stands_at(first_name, SPAWN), seen_by_first)

    # The walk to a station takes many seconds, so the first player is put
    # next to station 2, where the tick keeps the positions.
    lobby = app.state.lobbies.lobby_of(first_name)
    at_station = {"x": float(STATION_2["x"]), "y": float(STATION_2["y"] + 20)}
    lobby.walkers._walkers[first_name].position = (at_station["x"], at_station["y"])

    first.send_json({"type": "move", "dx": 1, "dy": 0})  # Walking when the window opens.
    first.send_json({"type": "open_station", "station": 2})
    opened = read_until(first, of_type("station_opened"), seen_by_first)
    assert opened["title"] == "Brew the order"
    where_it_opened = lobby.walkers.position_of(first_name)

    # Keys pressed while the window is open do nothing.
    first.send_json({"type": "move", "dx": 0, "dy": 1})
    # The second player walks, and both browsers see it.
    second.send_json({"type": "move", "dx": -1, "dy": 0})
    read_until(first, has_left(second_name, SPAWN), seen_by_first)
    read_until(second, has_left(second_name, SPAWN), seen_by_second)
    assert lobby.walkers.position_of(first_name) == where_it_opened

    # After closing, the first player walks again.
    first.send_json({"type": "close_station"})
    assert read_until(first, of_type("station_closed"), seen_by_first)["station"] == 2
    first.send_json({"type": "move", "dx": 0, "dy": 1})
    read_until(second, lambda message: message["type"] == "positions"
               and place_of(first_name, message) is not None
               and place_of(first_name, message)["y"] > where_it_opened[1], seen_by_second)

    # Nobody got an error, and the second player heard nothing about the task.
    assert [message for message in seen_by_first + seen_by_second if message["type"] == "error"] == []
    assert [message for message in seen_by_second if message["type"] in STATION_MESSAGES] == []
