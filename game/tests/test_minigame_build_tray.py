"""The content of "Build the tray", the minigame of the Canteen (M2-4.2, S-60).

The browser plays the minigame, so the server's part is small: it draws the
counter and the order slip. The last tests open station 3 over the WebSocket,
with the helpers of test_server_tasks.py.
"""

import json
import random

import pytest

from server.modes import build_tray, minigames
from server.modes.minigame import Minigame
import test_server_tasks as round_helpers
from test_server_tasks import client, clock, connect  # noqa: F401  (fixtures)

DISHES = ["Soup", "Bacalhau", "Rice", "Salad", "Pastel de nata", "Fruit"]
MANY_SEEDS = range(200)


def content_for(seed):
    return build_tray.make_content(random.Random(seed))


# What the content looks like


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 42])
def test_the_content_has_exactly_the_agreed_keys_and_kind(seed):
    content = content_for(seed)
    assert set(content) == {"kind", "dishes", "order"}
    assert content["kind"] == "build_tray"


@pytest.mark.parametrize("seed", MANY_SEEDS)
def test_the_counter_holds_the_six_agreed_dishes_once_each(seed):
    dishes = content_for(seed)["dishes"]
    assert isinstance(dishes, list)
    assert len(dishes) == 6
    assert sorted(dishes) == sorted(DISHES)


@pytest.mark.parametrize("seed", MANY_SEEDS)
def test_the_slip_names_four_different_dishes_of_the_counter(seed):
    content = content_for(seed)
    order = content["order"]
    assert isinstance(order, list)
    assert len(order) == 4
    assert len(set(order)) == 4
    assert set(order) <= set(content["dishes"])


@pytest.mark.parametrize("seed", MANY_SEEDS)
def test_two_dishes_of_the_counter_are_never_on_the_slip(seed):
    content = content_for(seed)
    assert len(set(content["dishes"]) - set(content["order"])) == 2


def test_the_content_is_json_safe():
    content = content_for(7)
    assert json.loads(json.dumps(content)) == content


def test_the_names_are_the_ones_of_the_design():
    assert list(build_tray.DISHES) == DISHES


# Randomness comes only from the generator passed in


def test_the_same_seed_gives_the_same_content():
    assert content_for(5) == content_for(5)


def test_one_generator_gives_new_content_at_every_opening():
    rng = random.Random(5)
    contents = [build_tray.make_content(rng) for _ in range(20)]
    assert len({json.dumps(content) for content in contents}) > 1


def test_different_seeds_give_different_slips():
    slips = {tuple(content_for(seed)["order"]) for seed in MANY_SEEDS}
    assert len(slips) > 20


def test_the_counter_order_varies():
    counters = {tuple(content_for(seed)["dishes"]) for seed in MANY_SEEDS}
    assert len(counters) > 20


def test_every_dish_is_ordered_and_left_out_at_some_point():
    ordered = set()
    left_out = set()
    for seed in MANY_SEEDS:
        content = content_for(seed)
        ordered |= set(content["order"])
        left_out |= set(content["dishes"]) - set(content["order"])
    assert ordered == set(DISHES)
    assert left_out == set(DISHES)


def test_every_dish_stands_at_every_place_of_the_counter_at_some_point():
    seen = {(place, dish) for seed in MANY_SEEDS for place, dish in enumerate(content_for(seed)["dishes"])}
    assert len(seen) == 6 * 6


def test_the_list_of_dishes_is_not_changed_by_drawing():
    before = tuple(build_tray.DISHES)
    content = content_for(1)
    content["dishes"].clear()
    content["order"].clear()
    assert tuple(build_tray.DISHES) == before
    assert len(content_for(1)["dishes"]) == 6


class OnlyTheAgreedCalls:
    """A generator that has nothing but the four agreed functions."""

    def __init__(self, seed):
        real = random.Random(seed)
        self.shuffle = real.shuffle
        self.sample = real.sample
        self.choice = real.choice
        self.randrange = real.randrange


def test_only_the_agreed_functions_of_the_generator_are_used():
    content = build_tray.make_content(OnlyTheAgreedCalls(3))
    assert sorted(content["dishes"]) == sorted(DISHES)


# Station 3 in the table of minigames


def test_station_3_is_build_the_tray():
    minigame = minigames.MINIGAMES[3]
    assert minigame is build_tray.MINIGAME
    assert isinstance(minigame, Minigame)
    assert minigame.title == "Build the tray"
    assert minigame.min_seconds == 1
    assert minigame.make_content is build_tray.make_content


# Over the WebSocket


def open_station_3(connect):
    """A running round in which Mara has just asked for station 3."""
    mara, tiago, _ = round_helpers.running_round(connect)
    round_helpers.put_at_station("Mara", 3)
    return mara, round_helpers.open_station(mara, 3)


def test_station_3_opens_with_a_tray_to_build(connect):
    mara, answer = open_station_3(connect)
    assert set(answer) == {"type", "station", "title", "content"}
    assert answer["type"] == "station_opened"
    assert answer["station"] == 3
    assert answer["title"] == "Build the tray"
    content = answer["content"]
    assert content["kind"] == "build_tray"
    assert sorted(content["dishes"]) == sorted(DISHES)
    assert len(set(content["order"])) == 4
    assert set(content["order"]) <= set(DISHES)


def test_station_3_counts_after_the_minimum_time(connect, clock):
    mara, _ = open_station_3(connect)
    clock.wait(1)
    assert round_helpers.finish_station(mara) == {"type": "station_done", "station": 3}


def test_station_3_does_not_count_sooner_than_the_minimum_time(connect, clock):
    mara, _ = open_station_3(connect)
    clock.wait(0.9)
    assert round_helpers.finish_station(mara) == round_helpers.TOO_FAST


def test_reopening_station_3_gives_new_content(connect):
    mara, first = open_station_3(connect)
    contents = {json.dumps(first["content"])}
    for _ in range(15):
        round_helpers.close_station(mara)
        contents.add(json.dumps(round_helpers.open_station(mara, 3)["content"]))
    # 16 equal draws out of 720 x 360 possible ones would mean nothing is shuffled.
    assert len(contents) > 1
