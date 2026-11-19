"""Play test of "Shelve the books" (station 4), "Self-checkout" (station 5)
and of one whole round with all five real minigames (M2-4.5, M2-4.6, S-93).

What the tester played in the browser, as far as the server takes part in it:
a player opens and finishes every real minigame in one round and then needs
no station, the other player gets none of it, a second "done" counts nothing,
and stations 4 and 5 draw new, fair content at every opening.

The placeholder fixture of `task_helpers` is left out on purpose: these tests
want the real minigame at every station.
"""

import itertools

import pytest

from server.modes import minigames
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import (
    NO_TASK_OPEN,
    NOT_NEEDED,
    TITLES,
    TOO_FAST,
    close_station,
    finish_station,
    lobby_named,
    open_station,
    put_at_station,
    running_round,
    still_works,
)

ALL_STATIONS = [1, 2, 3, 4, 5]
KINDS = {1: "sort_slides", 2: "brew_order", 3: "build_tray", 4: "shelve_books", 5: "self_checkout"}
SLIDES = ["Title", "Agenda", "Analysis", "Results", "Q&A"]
BUTTONS = ["Cup", "Glass", "Espresso", "Hot water", "Milk", "Foam"]
DISHES = ["Soup", "Bacalhau", "Rice", "Salad", "Pastel de nata", "Fruit"]
PRODUCTS = ["Water", "Bread", "Cheese", "Apples", "Coffee", "Chocolate"]
OPENINGS = 25


def is_whole_number(value):
    """True for an int. `True` and `False` are ints in Python, but no numbers of the game."""
    return type(value) is int


def assert_slides_can_be_played(content):
    assert set(content) == {"kind", "order", "slides"}
    assert content["order"] == SLIDES
    assert sorted(content["slides"]) == sorted(SLIDES)
    assert content["slides"] != SLIDES  # never sorted already


def assert_brew_can_be_played(content):
    assert set(content) == {"kind", "drink", "recipe", "buttons"}
    assert sorted(content["buttons"]) == sorted(BUTTONS)
    assert 2 <= len(content["recipe"]) <= 4
    assert all(step in BUTTONS for step in content["recipe"])


def assert_tray_can_be_played(content):
    assert set(content) == {"kind", "dishes", "order"}
    assert sorted(content["dishes"]) == sorted(DISHES)
    assert len(set(content["order"])) == 4
    assert all(dish in DISHES for dish in content["order"])


def assert_books_can_be_played(content):
    assert set(content) == {"kind", "books"}
    books = content["books"]
    assert len(books) == 6 and len(set(books)) == 6
    assert all(is_whole_number(number) and 100 <= number <= 999 for number in books)
    assert books != sorted(books)  # never in ascending order already


def assert_checkout_can_be_played(content):
    assert set(content) == {"kind", "products", "target_cents"}
    products = content["products"]
    assert sorted(product["name"] for product in products) == sorted(PRODUCTS)
    prices = [product["cents"] for product in products]
    assert all(is_whole_number(cents) and cents > 0 and cents % 50 == 0 for cents in prices)
    target = content["target_cents"]
    assert is_whole_number(target)
    assert target in {sum(three) for three in itertools.combinations(prices, 3)}
    assert target not in prices  # one click alone never solves it


CAN_BE_PLAYED = {
    1: assert_slides_can_be_played,
    2: assert_brew_can_be_played,
    3: assert_tray_can_be_played,
    4: assert_books_can_be_played,
    5: assert_checkout_can_be_played,
}


def open_real(connection, name, station):
    """Walk `name` to the station and open its real minigame. Returns the content."""
    put_at_station(name, station)
    answer = open_station(connection, station)
    assert set(answer) == {"type", "station", "title", "content"}
    assert answer["type"] == "station_opened"
    assert answer["station"] == station
    assert answer["title"] == TITLES[station]
    assert answer["content"]["kind"] == KINDS[station]
    CAN_BE_PLAYED[station](answer["content"])
    return answer["content"]


def play_real(connection, name, station, clock):
    """Open the real minigame, take exactly its minimum time and report it as done."""
    content = open_real(connection, name, station)
    clock.wait(minigames.MINIGAMES[station].min_seconds)
    assert finish_station(connection) == {"type": "station_done", "station": station}
    return content


def finished_by(name):
    return lobby_named(name).tasks.finished_by(name)


# One whole round


def test_the_real_minigames_stand_at_all_five_stations():
    assert sorted(minigames.MINIGAMES) == ALL_STATIONS
    for station in ALL_STATIONS:
        assert minigames.MINIGAMES[station].title == TITLES[station]
        assert minigames.MINIGAMES[station].min_seconds == 1


def test_a_player_finishes_all_five_real_minigames_in_one_round_and_then_needs_no_station(connect, clock):
    mara, tiago, _ = running_round(connect)
    for done_so_far, station in enumerate(ALL_STATIONS):
        assert finished_by("Mara") == set(ALL_STATIONS[:done_so_far])
        play_real(mara, "Mara", station, clock)
    assert finished_by("Mara") == set(ALL_STATIONS)
    # Nothing is left: every station answers "not needed", also from right next to it.
    for station in ALL_STATIONS:
        put_at_station("Mara", station)
        assert open_station(mara, station) == NOT_NEEDED
    assert finish_station(mara) == NO_TASK_OPEN
    assert close_station(mara) == NO_TASK_OPEN
    # The other player heard nothing of all this and still has everything to do.
    assert finished_by("Tiago") == set()
    assert still_works(tiago)
    assert still_works(mara)


@pytest.mark.parametrize("order", [[5, 4, 3, 2, 1], [4, 5, 1, 3, 2], [3, 1, 5, 2, 4]])
def test_the_five_minigames_can_be_finished_in_any_order(connect, clock, order):
    mara, _, _ = running_round(connect)
    for station in order:
        play_real(mara, "Mara", station, clock)
    assert finished_by("Mara") == set(ALL_STATIONS)


def test_two_players_play_the_same_round_side_by_side_and_each_counts_alone(connect, clock):
    mara, tiago, _ = running_round(connect)
    # Both stand at the bookshelf and have it open at the same time.
    open_real(mara, "Mara", 4)
    open_real(tiago, "Tiago", 4)
    clock.wait(1)
    assert finish_station(mara) == {"type": "station_done", "station": 4}
    # Mara's "done" did not finish or close Tiago's task.
    assert lobby_named("Tiago").tasks.open_station_of("Tiago") == 4
    assert finished_by("Tiago") == set()
    assert close_station(tiago) == {"type": "station_closed", "station": 4}
    # Mara goes on through the rest, Tiago solves two of them.
    for station in [1, 2, 3, 5]:
        play_real(mara, "Mara", station, clock)
    play_real(tiago, "Tiago", 5, clock)
    play_real(tiago, "Tiago", 3, clock)
    assert finished_by("Mara") == set(ALL_STATIONS)
    assert finished_by("Tiago") == {3, 5}
    # Tiago still needs the others, and nothing of Mara's is waiting for him.
    assert open_real(tiago, "Tiago", 4)["kind"] == "shelve_books"
    assert close_station(tiago) == {"type": "station_closed", "station": 4}
    assert still_works(tiago)
    assert still_works(mara)


# Stations 4 and 5: what a player can do wrong towards the server


@pytest.mark.parametrize("station", [4, 5])
def test_a_second_done_right_after_the_first_counts_nothing_and_breaks_nothing(connect, clock, station):
    mara, tiago, _ = running_round(connect)
    play_real(mara, "Mara", station, clock)
    assert finish_station(mara) == NO_TASK_OPEN
    assert finish_station(mara) == NO_TASK_OPEN
    assert finished_by("Mara") == {station}
    assert open_station(mara, station) == NOT_NEEDED
    assert still_works(mara)
    assert still_works(tiago)


@pytest.mark.parametrize("station", [4, 5])
def test_done_after_closing_with_esc_does_not_count(connect, clock, station):
    mara, _, _ = running_round(connect)
    open_real(mara, "Mara", station)
    clock.wait(5)
    assert close_station(mara) == {"type": "station_closed", "station": station}
    assert finish_station(mara) == NO_TASK_OPEN
    assert finished_by("Mara") == set()
    # The station is still needed and opens again.
    play_real(mara, "Mara", station, clock)


@pytest.mark.parametrize("station", [4, 5])
def test_a_solve_in_one_and_a_half_seconds_is_not_too_fast(connect, clock, station):
    mara, _, _ = running_round(connect)
    open_real(mara, "Mara", station)
    clock.wait(1.5)
    assert finish_station(mara) == {"type": "station_done", "station": station}


def test_too_fast_at_one_station_keeps_what_was_finished_before(connect, clock):
    mara, _, _ = running_round(connect)
    play_real(mara, "Mara", 4, clock)
    open_real(mara, "Mara", 5)
    clock.wait(0.5)
    assert finish_station(mara) == TOO_FAST
    assert mara.receive_json() == {"type": "station_closed", "station": 5}
    assert finished_by("Mara") == {4}
    put_at_station("Mara", 4)
    assert open_station(mara, 4) == NOT_NEEDED
    # Station 5 is still open to be played properly.
    play_real(mara, "Mara", 5, clock)
    assert finished_by("Mara") == {4, 5}


def test_the_time_spent_on_an_earlier_opening_does_not_count_for_the_next(connect, clock):
    mara, _, _ = running_round(connect)
    open_real(mara, "Mara", 5)
    clock.wait(30)
    assert close_station(mara) == {"type": "station_closed", "station": 5}
    open_real(mara, "Mara", 5)
    clock.wait(0.2)
    assert finish_station(mara) == TOO_FAST
    assert mara.receive_json() == {"type": "station_closed", "station": 5}
    assert finished_by("Mara") == set()


# Stations 4 and 5: new and fair content at every opening


def contents_of_many_openings(connection, name, station):
    contents = []
    for _ in range(OPENINGS):
        contents.append(open_real(connection, name, station))
        assert close_station(connection) == {"type": "station_closed", "station": station}
    return contents


def test_the_bookshelf_has_other_books_at_every_opening(connect, clock):
    mara, _, _ = running_round(connect)
    contents = contents_of_many_openings(mara, "Mara", 4)
    different = {tuple(content["books"]) for content in contents}
    # 900 numbers, six of them: the same six in the same order twice would be a broken draw.
    assert len(different) == OPENINGS


def test_the_checkout_has_other_prices_or_another_target_at_every_few_openings(connect, clock):
    mara, _, _ = running_round(connect)
    contents = contents_of_many_openings(mara, "Mara", 5)
    different = {
        (tuple((product["name"], product["cents"]) for product in content["products"]), content["target_cents"])
        for content in contents
    }
    assert len(different) >= OPENINGS - 1
    assert len({content["target_cents"] for content in contents}) > 1


def test_both_players_get_content_of_their_own_at_the_same_station(connect, clock):
    mara, tiago, _ = running_round(connect)
    for station in [4, 5]:
        of_mara = open_real(mara, "Mara", station)
        of_tiago = open_real(tiago, "Tiago", station)
        assert of_mara is not of_tiago
        assert close_station(mara) == {"type": "station_closed", "station": station}
        assert close_station(tiago) == {"type": "station_closed", "station": station}
    assert still_works(mara)
    assert still_works(tiago)
