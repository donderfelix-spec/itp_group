"""Minigame 5, "Self-checkout": the content the server draws (M2-4.6, S-60).

The browser plays the minigame (S-19), so the tests here are about the
content: six products with fair prices and a target that can always be hit.
"""

import contextlib
import itertools
import json
import random

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.modes import minigames, self_checkout
from server.modes.self_checkout import make_content

NAMES = ["Water", "Bread", "Cheese", "Apples", "Coffee", "Chocolate"]
SEEDS = range(300)
PASSWORD = "password123"
CAMPUS = app.state.campus
STATION_5 = next(station for station in CAMPUS["stations"] if station["id"] == 5)


def content_of(seed):
    return make_content(random.Random(seed))


def is_whole_number(value):
    """True for an int. `True` and `False` are ints in Python, but no prices."""
    return type(value) is int


def totals_of_three(products):
    """Every total three of the products can add up to."""
    prices = [product["cents"] for product in products]
    return {sum(three) for three in itertools.combinations(prices, 3)}


# The shape of the content


def test_the_content_has_exactly_the_agreed_keys_and_kind():
    content = content_of(1)
    assert set(content) == {"kind", "products", "target_cents"}
    assert content["kind"] == "self_checkout"


@pytest.mark.parametrize("seed", SEEDS)
def test_there_are_six_products_with_each_name_once(seed):
    products = content_of(seed)["products"]
    assert len(products) == 6
    assert sorted(product["name"] for product in products) == sorted(NAMES)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_product_has_only_a_name_and_a_price(seed):
    for product in content_of(seed)["products"]:
        assert set(product) == {"name", "cents"}


@pytest.mark.parametrize("seed", SEEDS)
def test_every_price_is_a_whole_number_of_cents_in_steps_of_50_from_50_to_400(seed):
    for product in content_of(seed)["products"]:
        cents = product["cents"]
        assert is_whole_number(cents)
        assert cents % 50 == 0
        assert 50 <= cents <= 400


# The target


@pytest.mark.parametrize("seed", SEEDS)
def test_the_target_is_a_whole_number_and_the_total_of_some_three_products(seed):
    content = content_of(seed)
    assert is_whole_number(content["target_cents"])
    assert content["target_cents"] in totals_of_three(content["products"])


@pytest.mark.parametrize("seed", SEEDS)
def test_the_target_is_never_below_the_cheapest_or_above_the_dearest_three(seed):
    content = content_of(seed)
    totals = totals_of_three(content["products"])
    assert min(totals) <= content["target_cents"] <= max(totals)
    assert 150 <= content["target_cents"] <= 1200


def test_the_content_does_not_name_the_solution():
    # Only the kind, the belt and the target: nothing says which three were drawn.
    for seed in SEEDS:
        content = content_of(seed)
        assert set(content) == {"kind", "products", "target_cents"}
        assert all(set(product) == {"name", "cents"} for product in content["products"])


def test_the_three_products_of_the_target_are_not_always_at_the_same_place_on_the_belt():
    # If the first three products always made the target, the order would give it away.
    places = set()
    for seed in SEEDS:
        content = content_of(seed)
        prices = [product["cents"] for product in content["products"]]
        for three in itertools.combinations(range(6), 3):
            if sum(prices[place] for place in three) == content["target_cents"]:
                places.add(three)
    assert len(places) == 20  # every way to pick three of six came up


# Randomness


def test_the_same_seed_gives_the_same_content():
    assert content_of(7) == content_of(7)


def test_the_content_does_not_change_the_names_it_draws_from():
    content_of(3)
    assert self_checkout.PRODUCT_NAMES == NAMES


def test_prices_order_and_target_vary_between_seeds():
    contents = [content_of(seed) for seed in SEEDS]
    orders = {tuple(product["name"] for product in content["products"]) for content in contents}
    prices = {product["cents"] for content in contents for product in content["products"]}
    targets = {content["target_cents"] for content in contents}
    assert len(orders) > 50
    assert prices == set(range(50, 401, 50))  # every price comes up
    assert len(targets) > 10


def test_every_product_gets_different_prices_over_time():
    for name in NAMES:
        prices = {
            product["cents"]
            for seed in SEEDS
            for product in content_of(seed)["products"]
            if product["name"] == name
        }
        assert len(prices) > 1


def test_the_content_uses_only_the_random_generator_that_is_passed_in():
    # Drawing with the shared `random` module in between must not change the result.
    first = content_of(11)
    random.random()
    assert content_of(11) == first


def test_the_content_is_json_safe():
    for seed in SEEDS:
        content = content_of(seed)
        assert json.loads(json.dumps(content)) == content


def test_the_text_of_the_content_has_no_decimal_point():
    # Money travels in whole cents, never as 1.5 or 7.50.
    assert "." not in json.dumps(content_of(5))


# The entry in the table of minigames


def test_station_5_is_the_self_checkout():
    minigame = minigames.MINIGAMES[5]
    assert minigame is self_checkout.MINIGAME
    assert minigame.title == "Self-checkout"
    assert minigame.min_seconds == 3
    assert minigame.make_content is make_content


def test_the_other_stations_are_untouched():
    assert sorted(minigames.MINIGAMES) == [1, 2, 3, 4, 5]
    assert minigames.MINIGAMES[1].title == "Sort the slides"
    assert minigames.MINIGAMES[4].title == "Shelve the books"


# Over the WebSocket, in a round (in the style of test_server_tasks.py)


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


def mara_at_station_5(connect):
    """A round of Mara and Tiago in which Mara stands at the self-checkout."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    tiago.receive_json()
    # Walking there takes seconds of real time, so the test writes the
    # position where the tick would write it (as in test_server_tasks.py).
    walker = app.state.lobbies.lobby_of("Mara").walkers._walkers["Mara"]
    walker.position = (float(STATION_5["x"]), float(STATION_5["y"]))
    return mara


def test_opening_station_5_in_a_round_sends_the_self_checkout(connect, clock):
    mara = mara_at_station_5(connect)
    answer = ask(mara, {"type": "open_station", "station": 5})
    assert set(answer) == {"type", "station", "title", "content"}
    assert answer["type"] == "station_opened"
    assert answer["station"] == 5
    assert answer["title"] == "Self-checkout"
    content = answer["content"]
    assert set(content) == {"kind", "products", "target_cents"}
    assert content["kind"] == "self_checkout"
    assert sorted(product["name"] for product in content["products"]) == sorted(NAMES)
    assert content["target_cents"] in totals_of_three(content["products"])


def test_the_self_checkout_counts_after_three_seconds_but_not_sooner(connect, clock):
    mara = mara_at_station_5(connect)
    ask(mara, {"type": "open_station", "station": 5})
    clock.wait(2.9)
    assert ask(mara, {"type": "finish_station"})["code"] == "too_fast"
    assert mara.receive_json() == {"type": "station_closed", "station": 5}
    ask(mara, {"type": "open_station", "station": 5})
    clock.wait(3)
    assert ask(mara, {"type": "finish_station"}) == {"type": "station_done", "station": 5}
