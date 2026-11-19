"""The minigame of station 2, "Brew the order" (M2-4.3, DESIGN.md section 8).

The server only draws the content: which drink and where the six buttons sit.
The browser plays it (S-19). The last tests open the station over the
WebSocket, in the style of test_server_tasks.py.
"""

import contextlib
import json
import random

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.modes import brew_order, minigames
from server.modes.minigame import Minigame

# Written out again here on purpose: the tests pin the table of DESIGN.md.
BUTTONS = ["Cup", "Glass", "Espresso", "Hot water", "Milk", "Foam"]
RECIPES = {
    "Bica": ["Cup", "Espresso"],
    "Abatanado": ["Cup", "Espresso", "Hot water"],
    "Meia de leite": ["Cup", "Espresso", "Milk"],
    "Galão": ["Glass", "Espresso", "Milk"],
    "Cappuccino": ["Cup", "Espresso", "Milk", "Foam"],
}
MANY_SEEDS = range(200)

PASSWORD = "password123"
CAMPUS = app.state.campus
STATION = {station["id"]: station for station in CAMPUS["stations"]}


def content_for(seed):
    return brew_order.make_content(random.Random(seed))


# The tables


def test_the_buttons_are_the_six_of_the_design():
    assert brew_order.BUTTONS == BUTTONS


def test_the_recipes_are_the_five_of_the_design():
    assert brew_order.RECIPES == RECIPES


def test_every_recipe_step_is_one_of_the_six_buttons():
    for recipe in brew_order.RECIPES.values():
        assert set(recipe) <= set(BUTTONS)


def test_no_recipe_has_the_same_button_twice_in_a_row():
    # So a fast double click on a right button can never count as two steps.
    for recipe in brew_order.RECIPES.values():
        for step, next_step in zip(recipe, recipe[1:]):
            assert step != next_step


def test_every_recipe_starts_with_a_cup_or_a_glass():
    for recipe in brew_order.RECIPES.values():
        assert recipe[0] in ("Cup", "Glass")
        assert len(recipe) >= 2


# The content


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 42])
def test_the_content_has_exactly_the_agreed_keys_and_kind(seed):
    content = content_for(seed)
    assert set(content) == {"kind", "drink", "recipe", "buttons"}
    assert content["kind"] == "brew_order"


def test_the_drink_is_one_of_the_five_with_exactly_its_recipe():
    for seed in MANY_SEEDS:
        content = content_for(seed)
        assert content["drink"] in RECIPES
        assert content["recipe"] == RECIPES[content["drink"]]


def test_the_buttons_are_always_all_six_each_once():
    for seed in MANY_SEEDS:
        buttons = content_for(seed)["buttons"]
        assert len(buttons) == 6
        assert sorted(buttons) == sorted(BUTTONS)


def test_the_same_seed_draws_the_same_content():
    for seed in [0, 7, 99]:
        assert content_for(seed) == content_for(seed)


def test_over_many_seeds_every_drink_appears():
    drinks = {content_for(seed)["drink"] for seed in MANY_SEEDS}
    assert drinks == set(RECIPES)


def test_over_many_seeds_the_button_order_varies():
    orders = {tuple(content_for(seed)["buttons"]) for seed in MANY_SEEDS}
    assert len(orders) > 50
    # Every button gets to sit in the first place at some time.
    assert {order[0] for order in orders} == set(BUTTONS)


def test_two_openings_from_one_generator_differ():
    rng = random.Random(5)
    drawn = [brew_order.make_content(rng) for _ in range(20)]
    assert len({json.dumps(content) for content in drawn}) > 1


def test_the_content_is_json_safe():
    for seed in MANY_SEEDS:
        content = content_for(seed)
        assert json.loads(json.dumps(content)) == content


def test_drawing_does_not_change_the_tables():
    # The browser gets copies: shuffling must not reorder the module's lists.
    first = content_for(1)
    first["recipe"].append("Foam")
    first["buttons"].clear()
    assert brew_order.BUTTONS == BUTTONS
    assert brew_order.RECIPES == RECIPES


def test_the_module_random_generator_works_too():
    # The server passes the `random` module itself.
    content = brew_order.make_content(random)
    assert content["recipe"] == RECIPES[content["drink"]]


# The entry in the table of minigames


def test_station_2_is_brew_the_order():
    minigame = minigames.MINIGAMES[2]
    assert minigame is brew_order.MINIGAME
    assert isinstance(minigame, Minigame)
    assert minigame.title == "Brew the order"
    assert minigame.min_seconds == 2
    assert minigame.make_content is brew_order.make_content


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


def mara_at_station_2(connect):
    """A running round of Mara and Tiago in which Mara stands at the coffee machine."""
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
    walker.position = (float(STATION[2]["x"]), float(STATION[2]["y"]))
    return mara


def test_opening_station_2_in_a_round_sends_a_drink_and_the_buttons(connect, clock):
    mara = mara_at_station_2(connect)
    answer = ask(mara, {"type": "open_station", "station": 2})
    assert set(answer) == {"type", "station", "title", "content"}
    assert answer["type"] == "station_opened"
    assert answer["station"] == 2
    assert answer["title"] == "Brew the order"
    content = answer["content"]
    assert set(content) == {"kind", "drink", "recipe", "buttons"}
    assert content["kind"] == "brew_order"
    assert content["recipe"] == RECIPES[content["drink"]]
    assert sorted(content["buttons"]) == sorted(BUTTONS)


def test_station_2_counts_after_two_seconds_and_not_sooner(connect, clock):
    mara = mara_at_station_2(connect)
    ask(mara, {"type": "open_station", "station": 2})
    clock.wait(1.9)
    assert ask(mara, {"type": "finish_station"})["code"] == "too_fast"
    assert mara.receive_json() == {"type": "station_closed", "station": 2}
    ask(mara, {"type": "open_station", "station": 2})
    clock.wait(2)
    assert ask(mara, {"type": "finish_station"}) == {"type": "station_done", "station": 2}


def test_reopening_station_2_draws_new_content(connect, clock, monkeypatch):
    mara = mara_at_station_2(connect)
    # Seeded only now: the lobby code was drawn from the same generator.
    monkeypatch.setattr(main, "random", random.Random(3))
    expected = random.Random(3)
    drawn = []
    for _ in range(6):
        drawn.append(ask(mara, {"type": "open_station", "station": 2})["content"])
        assert drawn[-1] == brew_order.make_content(expected)
        ask(mara, {"type": "close_station"})
    assert len({json.dumps(content) for content in drawn}) > 1
