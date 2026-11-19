"""The rules of the tasks at the stations (M2-4.1, S-93): open, close, finish.

No network here. The clock is a number the test chooses, and the random
generator is seeded or a fake, so every result is known beforehand.
"""

import json
import random

import pytest

from server import protocol
from server.modes import minigames, tasks
from server.modes.minigame import Minigame
from server.modes.placeholder import placeholder
from server.modes.tasks import RoundTasks
from server.world.campus import load_campus

USE_RANGE = 25
# Three stations in a row, far apart, and two that share some ground.
STATIONS = [
    {"id": 1, "x": 100, "y": 100},
    {"id": 2, "x": 300, "y": 100},
    {"id": 3, "x": 500, "y": 100},
    {"id": 4, "x": 700, "y": 100},
    {"id": 5, "x": 730, "y": 100},
    {"id": 6, "x": 900, "y": 100},
]
AT = {station["id"]: (station["x"], station["y"]) for station in STATIONS}
FAR_AWAY = (100, 400)

MIN_SECONDS = 3


def draw_number(rng) -> dict:
    return {"kind": "number", "number": rng.randrange(1000)}


# Stations 1 to 5 are in use, like in the real game; 6 is on the map only.
MINIGAMES = {
    station: Minigame(title=f"Game {station}", min_seconds=MIN_SECONDS, make_content=draw_number)
    for station in range(1, 6)
}


class FakeRandom:
    """Returns the numbers it was given, one after the other."""

    def __init__(self, *numbers):
        self.numbers = list(numbers)

    def randrange(self, below):
        return self.numbers.pop(0)


def new_round(**options):
    return RoundTasks(STATIONS, USE_RANGE, MINIGAMES, **options)


def opened_round(station=1, now=10.0):
    """A round in which Mara has the minigame of `station` open since `now`."""
    round_tasks = new_round()
    assert round_tasks.open("Mara", station, AT[station], now, FakeRandom(7))[1] is None
    return round_tasks


# Opening: accepted


def test_opening_a_station_in_range_returns_station_title_and_content():
    opened, rejection_code = new_round().open("Mara", 3, AT[3], 10.0, FakeRandom(42))
    assert rejection_code is None
    assert opened == {"station": 3, "title": "Game 3", "content": {"kind": "number", "number": 42}}


def test_opening_remembers_the_open_station():
    round_tasks = opened_round(station=2)
    assert round_tasks.has_open_task("Mara")
    assert round_tasks.open_station_of("Mara") == 2


@pytest.mark.parametrize("station", [1, 2, 3, 4, 5])
def test_every_station_in_use_can_be_opened(station):
    opened, rejection_code = new_round().open("Mara", station, AT[station], 0.0, FakeRandom(1))
    assert rejection_code is None
    assert opened["station"] == station


def test_exactly_at_the_range_still_counts():
    position = (AT[1][0] + USE_RANGE, AT[1][1])
    assert new_round().open("Mara", 1, position, 0.0, FakeRandom(1))[1] is None


def test_a_player_in_range_of_two_stations_may_open_the_farther_one():
    # (712, 100) is 12 away from station 4 and 18 away from station 5.
    position = (712, 100)
    assert new_round().open("Mara", 5, position, 0.0, FakeRandom(1))[1] is None
    assert new_round().open("Mara", 4, position, 0.0, FakeRandom(1))[1] is None


def test_the_content_comes_from_the_random_generator_that_is_passed_in():
    first, _ = new_round().open("Mara", 1, AT[1], 0.0, random.Random(5))
    again, _ = new_round().open("Mara", 1, AT[1], 0.0, random.Random(5))
    other, _ = new_round().open("Mara", 1, AT[1], 0.0, random.Random(6))
    assert first["content"] == again["content"]
    assert first["content"] != other["content"]


def test_two_players_can_have_the_same_station_open():
    round_tasks = opened_round(station=1)
    assert round_tasks.open("Tiago", 1, AT[1], 11.0, FakeRandom(2))[1] is None
    assert round_tasks.open_station_of("Mara") == 1
    assert round_tasks.open_station_of("Tiago") == 1


# Opening: rejected


def rejected_open(round_tasks, station, position, name="Mara"):
    opened, rejection_code = round_tasks.open(name, station, position, 20.0, FakeRandom(1))
    assert opened is None
    return rejection_code


def test_a_station_that_is_not_in_use_does_not_exist():
    assert rejected_open(new_round(), 6, AT[6]) == "no_station"


@pytest.mark.parametrize("station", [0, 7, -1, 99])
def test_a_station_that_is_not_on_the_map_does_not_exist(station):
    assert rejected_open(new_round(), station, AT[1]) == "no_station"


def test_one_step_beyond_the_range_is_too_far():
    position = (AT[1][0] + USE_RANGE + 0.1, AT[1][1])
    assert rejected_open(new_round(), 1, position) == "too_far"


def test_standing_at_another_station_is_too_far():
    assert rejected_open(new_round(), 1, AT[2]) == "too_far"


def test_a_player_without_a_position_is_too_far():
    assert rejected_open(new_round(), 1, None) == "too_far"


def test_a_position_that_is_not_a_number_is_too_far():
    assert rejected_open(new_round(), 1, (float("nan"), 100)) == "too_far"


def test_a_second_task_cannot_be_opened():
    round_tasks = opened_round(station=4)
    # Station 5 is in range from station 4 (30 apart is not, so stand between).
    assert rejected_open(round_tasks, 5, (712, 100)) == "task_open"
    assert round_tasks.open_station_of("Mara") == 4


def test_the_open_station_itself_cannot_be_opened_again():
    round_tasks = opened_round(station=1)
    assert rejected_open(round_tasks, 1, AT[1]) == "task_open"


def test_a_finished_station_is_not_needed_any_more():
    round_tasks = opened_round(station=1, now=10.0)
    round_tasks.finish("Mara", 10.0 + MIN_SECONDS)
    assert rejected_open(round_tasks, 1, AT[1]) == "station_not_needed"


def test_a_rejected_open_changes_nothing():
    round_tasks = new_round()
    for station, position in [(6, AT[6]), (1, FAR_AWAY), (1, None)]:
        rejected_open(round_tasks, station, position)
    assert not round_tasks.has_open_task("Mara")
    assert round_tasks.finished_by("Mara") == set()
    # And nothing was drawn: the generator is untouched.
    untouched = FakeRandom(1)
    round_tasks.open("Mara", 1, FAR_AWAY, 0.0, untouched)
    assert untouched.numbers == [1]


def test_a_minigame_that_fails_to_draw_leaves_no_task_open():
    def broken(rng):
        raise ValueError("this minigame is broken")

    broken_first = dict(MINIGAMES)
    broken_first[1] = Minigame(title="Broken", min_seconds=1, make_content=broken)
    round_tasks = RoundTasks(STATIONS, USE_RANGE, broken_first)
    with pytest.raises(ValueError):
        round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    assert not round_tasks.has_open_task("Mara")
    assert round_tasks.open("Mara", 2, AT[2], 0.0, FakeRandom(1))[1] is None


# Opening: the order of the checks


def test_a_station_not_in_use_is_reported_before_everything_else():
    # Task open, far away and station 6: "no_station" wins.
    round_tasks = opened_round(station=1)
    assert rejected_open(round_tasks, 6, FAR_AWAY) == "no_station"


def test_not_needed_is_reported_before_an_open_task_and_before_the_range():
    round_tasks = opened_round(station=1, now=0.0)
    round_tasks.finish("Mara", 100.0)
    round_tasks.open("Mara", 2, AT[2], 100.0, FakeRandom(1))
    assert rejected_open(round_tasks, 1, FAR_AWAY) == "station_not_needed"


def test_an_open_task_is_reported_before_the_range():
    round_tasks = opened_round(station=1)
    assert rejected_open(round_tasks, 2, FAR_AWAY) == "task_open"


# Opening: a mode can restrict a player's stations


def only_the_next_station(name, finished, in_use):
    """Like Duel will do it: the stations in order, one after the other."""
    for station in in_use:
        if station not in finished:
            return [station]
    return []


def test_by_default_a_player_needs_every_station_in_use():
    assert tasks.every_station_in_use("Mara", {1}, [1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_a_mode_can_allow_only_some_stations():
    round_tasks = new_round(needed_stations=only_the_next_station)
    assert rejected_open(round_tasks, 2, AT[2]) == "station_not_needed"
    assert round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))[1] is None


def test_the_next_station_becomes_available_when_the_one_before_is_finished():
    round_tasks = new_round(needed_stations=only_the_next_station)
    round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    round_tasks.finish("Mara", 50.0)
    assert round_tasks.open("Mara", 2, AT[2], 60.0, FakeRandom(1))[1] is None
    # Tiago has finished nothing: for him it is still station 1.
    assert rejected_open(round_tasks, 2, AT[2], name="Tiago") == "station_not_needed"


def test_the_hook_is_asked_with_name_finished_stations_and_stations_in_use():
    asked = []

    def remember(name, finished, in_use):
        asked.append((name, finished, in_use))
        return in_use

    round_tasks = new_round(needed_stations=remember)
    round_tasks.open("Mara", 2, AT[2], 0.0, FakeRandom(1))
    round_tasks.finish("Mara", 50.0)
    round_tasks.open("Mara", 3, AT[3], 60.0, FakeRandom(1))
    assert asked == [("Mara", set(), [1, 2, 3, 4, 5]), ("Mara", {2}, [1, 2, 3, 4, 5])]


def test_a_finished_station_stays_closed_even_if_the_hook_allows_it():
    round_tasks = new_round(needed_stations=lambda name, finished, in_use: [1])
    round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    round_tasks.finish("Mara", 50.0)
    assert rejected_open(round_tasks, 1, AT[1]) == "station_not_needed"


def test_the_hook_cannot_change_what_a_player_has_finished():
    def meddle(name, finished, in_use):
        finished.clear()
        return in_use

    round_tasks = new_round(needed_stations=meddle)
    round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    round_tasks.finish("Mara", 50.0)
    round_tasks.open("Mara", 2, AT[2], 60.0, FakeRandom(1))
    assert round_tasks.finished_by("Mara") == {1}


# Closing


def test_closing_returns_the_station_and_forgets_the_task():
    round_tasks = opened_round(station=3)
    assert round_tasks.close("Mara") == (3, None)
    assert not round_tasks.has_open_task("Mara")
    assert round_tasks.finished_by("Mara") == set()


def test_closing_without_an_open_task_is_rejected():
    assert new_round().close("Mara") == (None, "no_task_open")


def test_closing_twice_is_rejected_the_second_time():
    round_tasks = opened_round()
    round_tasks.close("Mara")
    assert round_tasks.close("Mara") == (None, "no_task_open")


def test_a_closed_station_can_be_opened_again_with_new_content():
    round_tasks = new_round()
    rng = random.Random(1)
    first, _ = round_tasks.open("Mara", 1, AT[1], 0.0, rng)
    round_tasks.close("Mara")
    second, rejection_code = round_tasks.open("Mara", 1, AT[1], 5.0, rng)
    assert rejection_code is None
    assert second["content"] != first["content"]


def test_closing_does_not_touch_another_player():
    round_tasks = opened_round(station=1)
    round_tasks.open("Tiago", 2, AT[2], 0.0, FakeRandom(1))
    round_tasks.close("Mara")
    assert round_tasks.open_station_of("Tiago") == 2


# Finishing


def test_finishing_after_the_minimum_time_counts():
    round_tasks = opened_round(station=2, now=10.0)
    assert round_tasks.finish("Mara", 10.0 + MIN_SECONDS + 5) == (2, None)
    assert round_tasks.finished_by("Mara") == {2}
    assert not round_tasks.has_open_task("Mara")


def test_exactly_the_minimum_time_is_long_enough():
    round_tasks = opened_round(station=2, now=10.0)
    assert round_tasks.finish("Mara", 10.0 + MIN_SECONDS) == (2, None)


def test_just_under_the_minimum_time_is_too_fast():
    round_tasks = opened_round(station=2, now=10.0)
    assert round_tasks.finish("Mara", 10.0 + MIN_SECONDS - 0.001) == (2, "too_fast")


def test_too_fast_closes_the_task_without_counting():
    round_tasks = opened_round(station=2, now=10.0)
    round_tasks.finish("Mara", 10.5)
    assert not round_tasks.has_open_task("Mara")
    assert round_tasks.finished_by("Mara") == set()


def test_after_too_fast_the_station_can_be_opened_and_finished():
    round_tasks = opened_round(station=2, now=10.0)
    round_tasks.finish("Mara", 10.5)
    assert round_tasks.open("Mara", 2, AT[2], 11.0, FakeRandom(1))[1] is None
    assert round_tasks.finish("Mara", 11.0 + MIN_SECONDS) == (2, None)


def test_the_minimum_time_counts_from_the_latest_opening():
    round_tasks = opened_round(station=2, now=0.0)
    round_tasks.close("Mara")
    round_tasks.open("Mara", 2, AT[2], 100.0, FakeRandom(1))
    # 101 is long after the first opening, but only one second after the second.
    assert round_tasks.finish("Mara", 101.0) == (2, "too_fast")


def test_a_clock_that_runs_backwards_is_too_fast_and_breaks_nothing():
    round_tasks = opened_round(station=2, now=10.0)
    assert round_tasks.finish("Mara", 5.0) == (2, "too_fast")


def test_every_minigame_has_its_own_minimum_time():
    quick_and_slow = {
        1: Minigame(title="Quick", min_seconds=1, make_content=draw_number),
        2: Minigame(title="Slow", min_seconds=10, make_content=draw_number),
    }
    round_tasks = RoundTasks(STATIONS, USE_RANGE, quick_and_slow)
    round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    assert round_tasks.finish("Mara", 2.0) == (1, None)
    round_tasks.open("Mara", 2, AT[2], 10.0, FakeRandom(1))
    assert round_tasks.finish("Mara", 12.0) == (2, "too_fast")


def test_finishing_without_an_open_task_is_rejected():
    assert new_round().finish("Mara", 100.0) == (None, "no_task_open")


def test_finishing_twice_is_rejected_the_second_time():
    round_tasks = opened_round(now=0.0)
    round_tasks.finish("Mara", 50.0)
    assert round_tasks.finish("Mara", 60.0) == (None, "no_task_open")
    assert round_tasks.finished_by("Mara") == {1}


def test_finishing_counts_only_for_the_player_who_did_it():
    round_tasks = opened_round(station=1, now=0.0)
    round_tasks.finish("Mara", 50.0)
    assert round_tasks.finished_by("Tiago") == set()
    assert round_tasks.open("Tiago", 1, AT[1], 60.0, FakeRandom(1))[1] is None


def test_all_five_stations_can_be_finished_one_after_the_other():
    round_tasks = new_round()
    for station in [3, 1, 5, 2, 4]:
        now = station * 100.0
        assert round_tasks.open("Mara", station, AT[station], now, FakeRandom(1))[1] is None
        assert round_tasks.finish("Mara", now + MIN_SECONDS) == (station, None)
    assert round_tasks.finished_by("Mara") == {1, 2, 3, 4, 5}


def test_finished_by_hands_out_a_copy():
    round_tasks = opened_round(station=1, now=0.0)
    round_tasks.finish("Mara", 50.0)
    round_tasks.finished_by("Mara").clear()
    assert round_tasks.finished_by("Mara") == {1}


# Players who leave, new rounds


def test_a_player_who_leaves_loses_the_open_task_and_everything_finished():
    round_tasks = opened_round(station=1, now=0.0)
    round_tasks.finish("Mara", 50.0)
    round_tasks.open("Mara", 2, AT[2], 60.0, FakeRandom(1))
    round_tasks.remove("Mara")
    assert not round_tasks.has_open_task("Mara")
    assert round_tasks.finished_by("Mara") == set()


def test_removing_a_player_the_round_never_heard_of_is_fine():
    new_round().remove("Nobody")


def test_removing_one_player_leaves_the_others_alone():
    round_tasks = opened_round(station=1)
    round_tasks.open("Tiago", 2, AT[2], 0.0, FakeRandom(1))
    round_tasks.remove("Mara")
    assert round_tasks.open_station_of("Tiago") == 2


def test_asking_about_a_player_changes_nothing_for_them():
    round_tasks = new_round()
    round_tasks.has_open_task("Mara")
    round_tasks.finished_by("Mara")
    round_tasks.open_station_of("Mara")
    # Asked about, Mara still has nothing: no task open, nothing finished,
    # and she can open and finish a station like a player nobody asked about.
    assert round_tasks.open_station_of("Mara") is None
    assert round_tasks.finished_by("Mara") == set()
    assert round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))[1] is None
    assert round_tasks.finish("Mara", 50.0) == (1, None)
    assert round_tasks.finished_by("Mara") == {1}


def test_a_new_round_starts_with_nothing_finished():
    old_round = opened_round(station=1, now=0.0)
    old_round.finish("Mara", 50.0)
    assert new_round().open("Mara", 1, AT[1], 0.0, FakeRandom(1))[1] is None


# The functions the server calls: they also know "no round is running"


def test_without_a_round_nothing_can_be_opened_closed_or_finished():
    assert tasks.open_station(None, "Mara", 1, AT[1], 0.0, FakeRandom(1)) == (None, "not_in_round")
    assert tasks.close_station(None, "Mara") == (None, "not_in_round")
    assert tasks.finish_station(None, "Mara", 0.0) == (None, "not_in_round")


def test_no_round_is_reported_before_a_station_that_does_not_exist():
    assert tasks.open_station(None, "Mara", 6, None, 0.0, FakeRandom(1)) == (None, "not_in_round")


def test_with_a_round_the_functions_do_what_the_round_does():
    round_tasks = new_round()
    opened, rejection_code = tasks.open_station(round_tasks, "Mara", 1, AT[1], 0.0, FakeRandom(9))
    assert rejection_code is None
    assert opened["content"] == {"kind": "number", "number": 9}
    assert tasks.close_station(round_tasks, "Mara") == (1, None)
    tasks.open_station(round_tasks, "Mara", 1, AT[1], 0.0, FakeRandom(9))
    assert tasks.finish_station(round_tasks, "Mara", MIN_SECONDS) == (1, None)


def test_a_player_stands_still_only_while_a_task_is_open():
    assert not tasks.stands_still(None, "Mara")
    round_tasks = new_round()
    assert not tasks.stands_still(round_tasks, "Mara")
    round_tasks.open("Mara", 1, AT[1], 0.0, FakeRandom(1))
    assert tasks.stands_still(round_tasks, "Mara")
    assert not tasks.stands_still(round_tasks, "Tiago")
    round_tasks.close("Mara")
    assert not tasks.stands_still(round_tasks, "Mara")


def test_every_rejection_code_of_the_rules_has_a_text():
    codes = ["not_in_round", "no_station", "station_not_needed", "task_open", "too_far", "no_task_open", "too_fast"]
    for code in codes:
        assert code in protocol.REJECTIONS


# The table of minigames


def test_stations_1_to_5_are_in_use_and_station_6_is_not():
    assert sorted(minigames.MINIGAMES) == [1, 2, 3, 4, 5]


def test_the_titles_are_the_ones_of_the_stations_on_the_map():
    names_on_the_map = {station["id"]: station["name"] for station in load_campus()["stations"]}
    for station, minigame in minigames.MINIGAMES.items():
        assert minigame.title == names_on_the_map[station]


@pytest.mark.parametrize("station", [1, 2, 3, 4, 5])
def test_every_minigame_draws_json_safe_content_with_a_kind(station):
    minigame = minigames.MINIGAMES[station]
    content = minigame.make_content(random.Random(station))
    assert isinstance(content["kind"], str)
    assert json.loads(json.dumps(content)) == content
    assert minigame.min_seconds > 0


def test_the_placeholder_has_fixed_content_and_one_second_minimum():
    minigame = placeholder("Sort the slides")
    assert minigame.title == "Sort the slides"
    assert minigame.min_seconds == 1
    assert minigame.make_content(random.Random(1)) == {"kind": "placeholder"}
    assert minigame.make_content(random.Random(2)) == {"kind": "placeholder"}


def test_without_a_table_of_its_own_a_round_uses_the_real_minigames(monkeypatch):
    # A minigame nobody else has, so the test does not depend on which
    # minigames the real table holds.
    marked = Minigame(title="Only in this test", min_seconds=7, make_content=lambda rng: {"kind": "marked"})
    monkeypatch.setitem(minigames.MINIGAMES, 1, marked)
    campus = load_campus()
    round_tasks = RoundTasks(campus["stations"], campus["use_range"])
    station = campus["stations"][0]
    opened, rejection_code = round_tasks.open("Mara", 1, (station["x"], station["y"]), 0.0, random.Random(1))
    assert rejection_code is None
    assert opened == {"station": 1, "title": "Only in this test", "content": {"kind": "marked"}}
    # Its minimum time is used too: 6.9 seconds are too fast, 7 are enough.
    assert round_tasks.finish("Mara", 6.9) == (1, "too_fast")
    round_tasks.open("Mara", 1, (station["x"], station["y"]), 10.0, random.Random(1))
    assert round_tasks.finish("Mara", 17.0) == (1, None)


def test_the_real_table_has_the_five_stations_with_the_titles_of_the_design():
    """True whatever minigames are in the table: stations, titles, a minimum time, content."""
    titles = {1: "Sort the slides", 2: "Brew the order", 3: "Build the tray", 4: "Shelve the books", 5: "Self-checkout"}
    assert {station: minigame.title for station, minigame in minigames.MINIGAMES.items()} == titles
    for minigame in minigames.MINIGAMES.values():
        assert minigame.min_seconds > 0
        content = minigame.make_content(random.Random(0))
        assert isinstance(content, dict)
        assert isinstance(content["kind"], str)
        assert json.loads(json.dumps(content)) == content
