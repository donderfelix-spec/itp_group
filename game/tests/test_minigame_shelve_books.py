"""The minigame of station 4, "Shelve the books": what the server draws (M2-4.5).

The browser plays the minigame; the server only draws six shelf numbers and
the mixed order the books lie in (S-19, S-93). The last test opens the
station over the WebSocket, in the way of test_server_tasks.py.
"""

import contextlib
import json
import random

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.modes import minigames, shelve_books
from server.modes.minigame import Minigame

SEEDS = range(500)
PASSWORD = "password123"
STATION_4 = next(station for station in app.state.campus["stations"] if station["id"] == 4)


def books_for(seed):
    return shelve_books.make_content(random.Random(seed))["books"]


class UnluckyRng:
    """A generator with the worst luck: sorted numbers, and a shuffle that changes nothing."""

    def __init__(self):
        self.shuffles = 0

    def sample(self, population, count):
        return list(population)[:count]

    def shuffle(self, items):
        self.shuffles += 1


class ReversingRng(UnluckyRng):
    """Its shuffle turns the list around, so the first try is already mixed."""

    def shuffle(self, items):
        self.shuffles += 1
        items.reverse()


# The content


def test_the_content_has_the_kind_and_the_books_and_nothing_else():
    content = shelve_books.make_content(random.Random(1))
    assert set(content) == {"kind", "books"}
    assert content["kind"] == "shelve_books"
    assert isinstance(content["books"], list)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 99])
def test_there_are_six_books(seed):
    assert len(books_for(seed)) == 6


def test_every_number_is_a_whole_number_and_no_bool():
    for seed in SEEDS:
        assert all(type(number) is int for number in books_for(seed))


def test_all_six_numbers_are_different():
    for seed in SEEDS:
        assert len(set(books_for(seed))) == 6


def test_every_number_is_a_shelf_number_from_100_to_999():
    for seed in SEEDS:
        assert all(100 <= number <= 999 for number in books_for(seed))


def test_the_content_is_json_safe():
    content = shelve_books.make_content(random.Random(7))
    assert json.loads(json.dumps(content)) == content


def test_the_module_random_works_as_generator_too():
    # The server passes the `random` module itself (server/main.py).
    books = shelve_books.make_content(random)["books"]
    assert len(set(books)) == 6


# The mixed order


def test_the_books_never_lie_in_ascending_order_already():
    for seed in SEEDS:
        books = books_for(seed)
        assert books != sorted(books)


def test_with_the_worst_luck_the_books_lie_backwards():
    rng = UnluckyRng()
    content = shelve_books.make_content(rng)
    assert content == {"kind": "shelve_books", "books": [105, 104, 103, 102, 101, 100]}
    # The shuffle was tried a fixed number of times, not for ever.
    assert rng.shuffles == shelve_books.SHUFFLE_TRIES


def test_a_shuffle_that_mixes_is_taken_at_the_first_try():
    rng = ReversingRng()
    assert shelve_books.make_content(rng)["books"] == [105, 104, 103, 102, 101, 100]
    assert rng.shuffles == 1


def test_mix_keeps_exactly_the_same_books_and_leaves_its_argument_alone():
    books = [100, 200, 300, 400, 500, 600]
    mixed = shelve_books.mix(books, random.Random(3))
    assert sorted(mixed) == books
    assert mixed != books
    assert books == [100, 200, 300, 400, 500, 600]


@pytest.mark.parametrize(
    "numbers, expected",
    [([1, 2, 3], True), ([3, 2, 1], False), ([1, 3, 2], False), ([5], True), ([], True)],
)
def test_is_ascending(numbers, expected):
    assert shelve_books.is_ascending(numbers) is expected


# Random, but controlled by the generator


def test_the_same_seed_draws_the_same_content():
    for seed in range(20):
        assert shelve_books.make_content(random.Random(seed)) == shelve_books.make_content(random.Random(seed))


def test_the_numbers_vary_between_openings():
    drawn = {tuple(books_for(seed)) for seed in range(50)}
    assert len(drawn) == 50
    every_number = {number for books in drawn for number in books}
    assert len(every_number) > 200


def test_the_numbers_are_not_evenly_spaced_every_time():
    def steps(books):
        ordered = sorted(books)
        return {second - first for first, second in zip(ordered, ordered[1:])}

    assert any(len(steps(books_for(seed))) > 1 for seed in range(20))


def test_one_generator_draws_new_content_each_time():
    rng = random.Random(11)
    assert shelve_books.make_content(rng) != shelve_books.make_content(rng)


# The entry in the table of minigames


def test_station_4_is_shelve_the_books():
    minigame = minigames.MINIGAMES[4]
    assert minigame is shelve_books.MINIGAME
    assert isinstance(minigame, Minigame)
    assert minigame.title == "Shelve the books"
    assert minigame.min_seconds == 1
    assert minigame.make_content is shelve_books.make_content


# Over the WebSocket


class Clock:
    """The server's clock for the tasks, set by the test."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.now += seconds


@pytest.fixture
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


def player(connect, name):
    connection = connect()
    assert ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})["type"] == "signed_in"
    return connection


def mara_at_station_4(connect):
    """A running round of Mara and Tiago in which Mara stands at station 4."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    tiago.receive_json()
    # Walking there takes many seconds, so the position is written where the tick writes it.
    walker = app.state.lobbies.lobby_of("Mara").walkers._walkers["Mara"]
    walker.position = (float(STATION_4["x"]), float(STATION_4["y"]))
    return mara


def test_station_4_opens_with_six_books_and_counts_after_the_minimum_time(connect, clock, monkeypatch):
    mara = mara_at_station_4(connect)
    # Only now: the lobby code is drawn from the same generator.
    monkeypatch.setattr(main, "random", random.Random(4))

    answer = ask(mara, {"type": "open_station", "station": 4})
    expected = shelve_books.make_content(random.Random(4))
    assert answer == {"type": "station_opened", "station": 4, "title": "Shelve the books", "content": expected}

    clock.wait(1)
    assert ask(mara, {"type": "finish_station"}) == {"type": "station_done", "station": 4}


def test_station_4_reported_done_too_fast_does_not_count_and_reopens_with_new_books(connect, clock, monkeypatch):
    mara = mara_at_station_4(connect)
    # Only now: the lobby code is drawn from the same generator.
    monkeypatch.setattr(main, "random", random.Random(4))
    first = ask(mara, {"type": "open_station", "station": 4})["content"]

    clock.wait(0.9)
    assert ask(mara, {"type": "finish_station"})["code"] == "too_fast"
    assert mara.receive_json() == {"type": "station_closed", "station": 4}

    second = ask(mara, {"type": "open_station", "station": 4})["content"]
    assert second["kind"] == "shelve_books"
    assert second["books"] != first["books"]
