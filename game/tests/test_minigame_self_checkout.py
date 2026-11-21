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
from task_helpers import round_without_duel  # noqa: F401  (fixture)

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


def test_there_are_six_products_with_each_name_once():
    for seed in SEEDS:
        products = content_of(seed)["products"]
        assert len(products) == 6
        assert sorted(product["name"] for product in products) == sorted(NAMES)


def test_a_product_has_only_a_name_and_a_price():
    for seed in SEEDS:
        for product in content_of(seed)["products"]:
            assert set(product) == {"name", "cents"}


def test_every_price_is_a_whole_number_of_cents_in_steps_of_50_from_50_to_400():
    for seed in SEEDS:
        for product in content_of(seed)["products"]:
            cents = product["cents"]
            assert is_whole_number(cents)
            assert cents % 50 == 0
            assert 50 <= cents <= 400


# The target


def test_the_target_is_a_whole_number_and_the_total_of_some_three_products():
    for seed in SEEDS:
        content = content_of(seed)
        assert is_whole_number(content["target_cents"])
        assert content["target_cents"] in totals_of_three(content["products"])


def test_the_target_is_never_below_the_cheapest_or_above_the_dearest_three():
    for seed in SEEDS:
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


class SpyRandom(random.Random):
    """A random generator that remembers every `sample` it was asked for."""

    def __init__(self, seed):
        super().__init__(seed)
        self.samples = []  # (the list drawn from, how many, what was drawn)

    def sample(self, population, k):
        drawn = super().sample(population, k)
        self.samples.append((population, k, drawn))
        return drawn


def test_the_three_products_of_the_target_are_drawn_from_the_products_that_are_sent():
    for seed in SEEDS:
        rng = SpyRandom(seed)
        content = make_content(rng)
        assert rng.samples  # the three are drawn, not taken from fixed places
        for population, how_many, _ in rng.samples:
            assert population == content["products"]
            assert how_many == 3
        # The last draw is the one that was kept.
        drawn = rng.samples[-1][2]
        assert content["target_cents"] == sum(product["cents"] for product in drawn)


def test_the_first_three_products_on_the_belt_are_not_always_the_target():
    # If the first three products always made the target, the order would give it away.
    misses = 0
    for seed in SEEDS:
        content = content_of(seed)
        first_three = sum(product["cents"] for product in content["products"][:3])
        if first_three != content["target_cents"]:
            misses += 1
    assert misses > len(SEEDS) / 2


def test_the_target_is_never_the_price_of_a_single_product():
    # One click would solve it, faster than the server lets a task count.
    for seed in range(3000):
        content = content_of(seed)
        assert content["target_cents"] not in {product["cents"] for product in content["products"]}


class ScriptedRandom(random.Random):
    """Leaves the names in order, hands out the given prices, and always
    draws the first three products for the target."""

    def __init__(self, prices):
        super().__init__(0)
        self.prices = list(prices)
        self.sample_calls = 0

    def shuffle(self, items):
        pass

    def randrange(self, start, stop=None, step=1):
        return self.prices.pop(0)

    def sample(self, population, k):
        self.sample_calls += 1
        return population[:k]


def test_a_draw_that_equals_a_single_price_is_drawn_again_only_a_fixed_number_of_times():
    # 50 + 50 + 50 = 150, and Apples cost 150: every draw is thrown away.
    rng = ScriptedRandom([50, 50, 50, 150, 100, 100])
    content = make_content(rng)
    assert rng.sample_calls == self_checkout.TARGET_TRIES
    assert [product["cents"] for product in content["products"]] == [50, 50, 50, 150, 100, 100]
    # After the tries the three dearest make the target: 150 + 100 + 100.
    assert content["target_cents"] == 350
    assert content["target_cents"] in totals_of_three(content["products"])
    assert content["target_cents"] not in {50, 100, 150}


def test_a_draw_that_fits_is_kept_at_once():
    rng = ScriptedRandom([100, 150, 200, 250, 300, 350])
    content = make_content(rng)
    assert rng.sample_calls == 1
    assert content["target_cents"] == 450


def test_the_three_dearest_products_never_total_a_single_price():
    # The way out after the tries must hold for every belt, so try every
    # set of six prices there is (the order does not matter for a total).
    prices = range(50, 401, 50)
    for six in itertools.combinations_with_replacement(prices, 6):
        products = [{"name": name, "cents": cents} for name, cents in zip(NAMES, six)]
        total = self_checkout.dearest_three_total(products)
        assert total not in six
        assert total in totals_of_three(products)


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
    assert minigame.min_seconds == 1
    assert minigame.make_content is make_content


def test_the_other_stations_are_not_the_self_checkout():
    for station, minigame in minigames.MINIGAMES.items():
        if station != 5:
            assert minigame is not self_checkout.MINIGAME
            assert minigame.title != "Self-checkout"
            assert minigame.make_content is not make_content


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


def test_the_self_checkout_counts_after_one_second_but_not_sooner(connect, clock):
    mara = mara_at_station_5(connect)
    ask(mara, {"type": "open_station", "station": 5})
    clock.wait(0.9)
    assert ask(mara, {"type": "finish_station"})["code"] == "too_fast"
    assert mara.receive_json() == {"type": "station_closed", "station": 5}
    ask(mara, {"type": "open_station", "station": 5})
    clock.wait(1)
    assert ask(mara, {"type": "finish_station"}) == {"type": "station_done", "station": 5}
