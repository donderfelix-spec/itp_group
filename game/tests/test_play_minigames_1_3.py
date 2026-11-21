"""What the play test of the minigames at stations 1 to 3 did, as repeatable tests.

"Sort the slides" (Lecture Hall), "Brew the order" (Mon Café) and "Build the
tray" (Canteen) were played in two browsers at once. Dragging, pressing and
clicking happen in the browser and cannot be repeated here (S-72); these tests
repeat what the server saw of it, with the real minigames at their stations:
two players at the same station at the same time, the content of many
openings in a row, the way from "too fast" to "done", a second finish, and a
player who leaves in the middle.

The content of one opening and the minimum time of each minigame are checked
in test_minigame_sort_slides.py, test_minigame_brew_order.py and
test_minigame_build_tray.py; the frame, with the placeholder at every
station, in test_server_tasks.py and test_play_tasks.py.

`placeholder_at_every_station` is not imported on purpose: the real minigames
stay at their stations.
"""

import pytest

from server.modes import brew_order, build_tray, sort_slides
from task_helpers import client, clock, connect  # noqa: F401  (fixtures)
from task_helpers import round_without_duel  # noqa: F401  (fixture)
from task_helpers import (
    NO_TASK_OPEN,
    NOT_NEEDED,
    TASK_OPEN,
    TITLES,
    TOO_FAST,
    close_station,
    finish_station,
    open_station,
    put_at_station,
    running_round,
    still_works,
)

STATIONS = [1, 2, 3]
KINDS = {1: "sort_slides", 2: "brew_order", 3: "build_tray"}
OPENINGS_IN_A_ROW = 40


def is_playable_pile(content):
    """Station 1: the right order, and a pile with the same five slides that is not sorted."""
    right_order = list(sort_slides.RIGHT_ORDER)
    is_shuffled = sorted(content["slides"]) == sorted(right_order) and content["slides"] != right_order
    return content["order"] == right_order and is_shuffled


def is_playable_order(content):
    """Station 2: a drink of the design with exactly its recipe, and all six buttons once."""
    has_its_recipe = brew_order.RECIPES.get(content["drink"]) == content["recipe"]
    return has_its_recipe and sorted(content["buttons"]) == sorted(brew_order.BUTTONS)


def is_playable_tray(content):
    """Station 3: the six dishes at the counter, four different ones of them on the slip."""
    has_all_dishes = sorted(content["dishes"]) == sorted(build_tray.DISHES)
    slip = content["order"]
    return has_all_dishes and len(set(slip)) == 4 and set(slip) <= set(build_tray.DISHES)


IS_PLAYABLE = {1: is_playable_pile, 2: is_playable_order, 3: is_playable_tray}


def opened_content(answer, station):
    """The content of a `station_opened` for this station, after checking the frame around it."""
    assert answer["type"] == "station_opened", answer
    assert answer["station"] == station
    assert answer["title"] == TITLES[station]
    assert answer["content"]["kind"] == KINDS[station]
    return answer["content"]


def done(station):
    return {"type": "station_done", "station": station}


def closed(station):
    return {"type": "station_closed", "station": station}


# Two players at the same station at the same time


@pytest.mark.parametrize("station", STATIONS)
def test_two_players_open_the_same_station_and_each_gets_a_playable_task(connect, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    put_at_station("Tiago", station)
    for connection in (mara, tiago):
        content = opened_content(open_station(connection, station), station)
        assert IS_PLAYABLE[station](content)


@pytest.mark.parametrize("station", STATIONS)
def test_two_players_at_one_station_draw_their_own_content(connect, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    put_at_station("Tiago", station)
    pairs_that_differ = 0
    for _ in range(10):
        of_mara = opened_content(open_station(mara, station), station)
        of_tiago = opened_content(open_station(tiago, station), station)
        pairs_that_differ += of_mara != of_tiago
        assert close_station(mara) == closed(station)
        assert close_station(tiago) == closed(station)
    # Ten equal pairs would mean both players are handed the same draw.
    assert pairs_that_differ > 0


@pytest.mark.parametrize("station", STATIONS)
def test_one_player_finishing_leaves_the_task_of_the_other_open(connect, clock, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    put_at_station("Tiago", station)
    opened_content(open_station(mara, station), station)
    opened_content(open_station(tiago, station), station)
    clock.wait(5)
    assert finish_station(mara) == done(station)
    # Tiago heard nothing of it, his task is still open and still counts.
    assert still_works(tiago)
    assert open_station(tiago, station) == TASK_OPEN
    assert finish_station(tiago) == done(station)


@pytest.mark.parametrize("station", STATIONS)
def test_one_player_closing_leaves_the_task_of_the_other_open(connect, clock, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    put_at_station("Tiago", station)
    open_station(mara, station)
    open_station(tiago, station)
    assert close_station(mara) == closed(station)
    clock.wait(2)
    assert still_works(tiago)
    assert finish_station(tiago) == done(station)
    # And Mara, who only closed, can still open and finish hers.
    opened_content(open_station(mara, station), station)
    clock.wait(2)
    assert finish_station(mara) == done(station)


# Opening and closing many times


@pytest.mark.parametrize("station", STATIONS)
def test_every_one_of_many_openings_in_a_row_is_playable(connect, station):
    mara, _, _ = running_round(connect)
    put_at_station("Mara", station)
    for _ in range(OPENINGS_IN_A_ROW):
        content = opened_content(open_station(mara, station), station)
        assert IS_PLAYABLE[station](content), content
        assert close_station(mara) == closed(station)


def test_many_openings_of_station_2_bring_more_than_one_drink(connect):
    mara, _, _ = running_round(connect)
    put_at_station("Mara", 2)
    drinks = set()
    for _ in range(OPENINGS_IN_A_ROW):
        drinks.add(open_station(mara, 2)["content"]["drink"])
        close_station(mara)
    # One drink in 40 draws out of five has a chance of about 1 in 10^27.
    assert len(drinks) > 1


# From "too fast" to "done"


@pytest.mark.parametrize("station", STATIONS)
def test_after_too_fast_the_station_opens_again_with_a_playable_task_and_then_counts(connect, clock, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    open_station(mara, station)
    clock.wait(0.4)  # all pieces placed by a script, as in the play test
    assert finish_station(mara) == TOO_FAST
    assert mara.receive_json() == closed(station)
    content = opened_content(open_station(mara, station), station)
    assert IS_PLAYABLE[station](content)
    clock.wait(1.4)  # the quickest solve a practised player managed
    assert finish_station(mara) == done(station)
    assert still_works(tiago)


@pytest.mark.parametrize("station", STATIONS)
def test_a_solved_station_takes_no_second_finish_and_does_not_open_again(connect, clock, station):
    mara, _, _ = running_round(connect)
    put_at_station("Mara", station)
    open_station(mara, station)
    clock.wait(10)
    assert finish_station(mara) == done(station)
    assert finish_station(mara) == NO_TASK_OPEN
    assert open_station(mara, station) == NOT_NEEDED
    assert close_station(mara) == NO_TASK_OPEN
    assert still_works(mara)


# A whole walk through the three rooms at the top


def test_one_player_solves_stations_1_2_and_3_one_after_the_other(connect, clock):
    mara, tiago, _ = running_round(connect)
    for station in STATIONS:
        put_at_station("Mara", station)
        content = opened_content(open_station(mara, station), station)
        assert IS_PLAYABLE[station](content)
        clock.wait(12)
        assert finish_station(mara) == done(station)
    for station in STATIONS:
        put_at_station("Mara", station)
        assert open_station(mara, station) == NOT_NEEDED
    # Tiago heard nothing of all this, and all three are still open to him.
    assert still_works(tiago)
    for station in STATIONS:
        put_at_station("Tiago", station)
        opened_content(open_station(tiago, station), station)
        assert close_station(tiago) == closed(station)


def test_with_one_minigame_open_the_one_of_another_station_does_not_open(connect, clock):
    mara, _, _ = running_round(connect)
    put_at_station("Mara", 1)
    opened_content(open_station(mara, 1), 1)
    assert open_station(mara, 2) == TASK_OPEN
    assert open_station(mara, 3) == TASK_OPEN
    clock.wait(3)
    assert finish_station(mara) == done(1)


# Leaving in the middle


@pytest.mark.parametrize("station", STATIONS)
def test_a_player_who_leaves_in_the_middle_does_not_disturb_the_task_of_the_other(connect, clock, station):
    mara, tiago, _ = running_round(connect)
    put_at_station("Mara", station)
    put_at_station("Tiago", station)
    open_station(mara, station)
    open_station(tiago, station)
    tiago.send_json({"type": "leave_lobby"})
    assert tiago.receive_json() == {"type": "left_lobby"}
    assert mara.receive_json()["type"] == "lobby_state"
    clock.wait(3)
    assert finish_station(mara) == done(station)
    assert still_works(mara)
