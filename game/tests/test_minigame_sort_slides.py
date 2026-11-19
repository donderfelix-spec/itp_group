"""The server's part of "Sort the slides", the minigame of station 1 (M2-4.4).

The first tests call the plain function that shuffles the pile. The last ones
open station 1 over the WebSocket in a round, in the style of
test_server_tasks.py: the tick is switched off (see conftest.py) and the test
puts the player at the station.
"""

import contextlib
import json
import random

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.modes import minigames, sort_slides

RIGHT_ORDER = ["Title", "Agenda", "Analysis", "Results", "Q&A"]
MANY_SEEDS = range(2000)
PASSWORD = "password123"
STATION_1 = next(station for station in app.state.campus["stations"] if station["id"] == 1)


class LazyRng:
    """A random generator whose shuffle changes nothing: the worst luck there is."""

    def __init__(self):
        self.shuffles = 0

    def shuffle(self, items):
        self.shuffles += 1


class ReversingRng:
    """A generator that is not random at all: its shuffle turns the list around."""

    def shuffle(self, items):
        items.reverse()


# The content


def test_the_content_has_exactly_the_agreed_keys_and_kind():
    content = sort_slides.make_content(random.Random(1))
    assert set(content) == {"kind", "order", "slides"}
    assert content["kind"] == "sort_slides"


@pytest.mark.parametrize("seed", [0, 1, 2, 99])
def test_the_order_is_always_the_five_slides_in_the_right_order(seed):
    assert sort_slides.make_content(random.Random(seed))["order"] == RIGHT_ORDER


def test_the_pile_is_a_permutation_of_the_five_slides_for_many_seeds():
    for seed in MANY_SEEDS:
        slides = sort_slides.make_content(random.Random(seed))["slides"]
        assert len(slides) == 5
        assert sorted(slides) == sorted(RIGHT_ORDER)


def test_the_pile_is_never_already_sorted_for_many_seeds():
    for seed in MANY_SEEDS:
        assert sort_slides.make_content(random.Random(seed))["slides"] != RIGHT_ORDER


def test_the_same_seed_gives_the_same_content():
    assert sort_slides.make_content(random.Random(7)) == sort_slides.make_content(random.Random(7))


def test_the_pile_varies_between_seeds():
    piles = {tuple(sort_slides.make_content(random.Random(seed))["slides"]) for seed in MANY_SEEDS}
    # 119 unsorted orders exist. 2000 draws find far more than half of them.
    assert len(piles) > 60


def test_one_generator_gives_different_piles_one_after_the_other():
    rng = random.Random(3)
    piles = {tuple(sort_slides.make_content(rng)["slides"]) for _ in range(50)}
    assert len(piles) > 10


def test_the_content_is_json_safe():
    content = sort_slides.make_content(random.Random(5))
    assert json.loads(json.dumps(content)) == content


def test_each_call_gets_lists_of_its_own():
    first = sort_slides.make_content(random.Random(1))
    first["order"].clear()
    first["slides"].clear()
    assert sort_slides.make_content(random.Random(1))["order"] == RIGHT_ORDER
    assert sort_slides.RIGHT_ORDER == tuple(RIGHT_ORDER)


# Edge cases: a generator with bad luck


def test_a_shuffle_that_does_nothing_still_gives_an_unsorted_pile():
    rng = LazyRng()
    content = sort_slides.make_content(rng)
    assert content["slides"] == ["Agenda", "Analysis", "Results", "Q&A", "Title"]
    assert content["order"] == RIGHT_ORDER


def test_the_number_of_tries_is_fixed_so_bad_luck_never_loops_forever():
    rng = LazyRng()
    sort_slides.make_content(rng)
    assert rng.shuffles == sort_slides.SHUFFLE_TRIES


def test_the_first_unsorted_shuffle_is_taken():
    assert sort_slides.make_content(ReversingRng())["slides"] == RIGHT_ORDER[::-1]


def test_only_shuffle_is_asked_of_the_generator():
    # LazyRng has nothing but `shuffle`: any other call would raise AttributeError.
    sort_slides.make_content(LazyRng())


def test_move_first_to_end_keeps_the_slides_and_changes_the_order():
    assert sort_slides.move_first_to_end([1, 2, 3]) == [2, 3, 1]


# The table of minigames


def test_station_1_is_sort_the_slides():
    minigame = minigames.MINIGAMES[1]
    assert minigame is sort_slides.MINIGAME
    assert minigame.title == "Sort the slides"
    assert minigame.min_seconds == 1
    assert minigame.make_content is sort_slides.make_content


def test_the_other_stations_did_not_change():
    titles = {station: minigame.title for station, minigame in minigames.MINIGAMES.items()}
    assert titles == {
        1: "Sort the slides",
        2: "Brew the order",
        3: "Build the tray",
        4: "Shelve the books",
        5: "Self-checkout",
    }


# Over the WebSocket, in a round


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


def mara_at_station_1(connect):
    """A running round of Mara and Tiago in which Mara stands at station 1."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    tiago.receive_json()
    # Walking there takes many seconds, so the test writes the position
    # where the tick writes it (as in test_server_tasks.py).
    walker = app.state.lobbies.lobby_of("Mara").walkers._walkers["Mara"]
    walker.position = (float(STATION_1["x"]), float(STATION_1["y"]))
    return mara


def open_station_1(connection):
    return ask(connection, {"type": "open_station", "station": 1})


def test_opening_station_1_in_a_round_sends_sort_the_slides(connect, clock, monkeypatch):
    mara = mara_at_station_1(connect)
    # Seeded only now: the lobby code was drawn from the same generator.
    monkeypatch.setattr(main, "random", random.Random(11))
    answer = open_station_1(mara)
    assert answer == {
        "type": "station_opened",
        "station": 1,
        "title": "Sort the slides",
        "content": sort_slides.make_content(random.Random(11)),
    }
    assert answer["content"]["kind"] == "sort_slides"
    assert answer["content"]["slides"] != RIGHT_ORDER


def test_a_reopened_station_1_has_a_new_pile(connect, clock, monkeypatch):
    mara = mara_at_station_1(connect)
    monkeypatch.setattr(main, "random", random.Random(11))
    expected = random.Random(11)
    first = open_station_1(mara)
    assert ask(mara, {"type": "close_station"}) == {"type": "station_closed", "station": 1}
    second = open_station_1(mara)
    assert first["content"] == sort_slides.make_content(expected)
    assert second["content"] == sort_slides.make_content(expected)
    assert first["content"]["slides"] != second["content"]["slides"]


def test_station_1_is_too_fast_before_one_second_and_counts_after(connect, clock):
    mara = mara_at_station_1(connect)
    open_station_1(mara)
    clock.wait(0.9)
    too_fast = ask(mara, {"type": "finish_station"})
    assert (too_fast["type"], too_fast["code"]) == ("error", "too_fast")
    # After "too fast" the server closes the task (see test_server_tasks.py).
    assert mara.receive_json() == {"type": "station_closed", "station": 1}
    open_station_1(mara)
    clock.wait(1)
    assert ask(mara, {"type": "finish_station"}) == {"type": "station_done", "station": 1}
