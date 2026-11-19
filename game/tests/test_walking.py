"""Where the players of a lobby stand and walk: the plain rules, without a network."""

import math

import pytest

from server.net.lobbies import Lobbies
from server.net.walking import Walkers
from server.world.campus import load_campus
from server.world.movement import PLAYER_HALF_SIZE, PLAYER_SPEED

TICKS_PER_SECOND = 15
ONE_TICK = 1 / TICKS_PER_SECOND


def open_field():
    """A small map with nothing in the way."""
    return {"width": 1000, "height": 1000, "spawn": {"x": 100, "y": 200}, "solids": []}


def field_with_a_wall():
    """The same map with a wall 40 units to the right of the spawn."""
    field = open_field()
    field["solids"] = [{"x": 140, "y": 0, "w": 6, "h": 1000}]
    return field


def walk_for_one_second(walkers, campus):
    for tick in range(TICKS_PER_SECOND):
        walkers.advance(ONE_TICK, campus)


def position_of(walkers, name):
    for listed_name, x, y in walkers.positions():
        if listed_name == name:
            return (x, y)
    return None


def walkers_with(*names):
    """Players who joined and have been placed and told, so there is no news left."""
    walkers = Walkers()
    for name in names:
        walkers.add(name)
    walkers.advance(0, open_field())
    for name in names:
        walkers.mark_told(name)
    return walkers


# Appearing and leaving


def test_a_newcomer_appears_at_the_spawn():
    walkers = Walkers()
    walkers.add("Mara")
    walkers.advance(ONE_TICK, open_field())
    assert walkers.positions() == [("Mara", 100, 200)]


def test_a_newcomer_is_not_listed_before_the_first_tick():
    walkers = Walkers()
    walkers.add("Mara")
    assert walkers.positions() == []


def test_several_players_may_stand_on_the_same_spot():
    walkers = walkers_with("Mara", "Tiago")
    assert walkers.positions() == [("Mara", 100, 200), ("Tiago", 100, 200)]


def test_leaving_removes_the_player():
    walkers = walkers_with("Mara", "Tiago")
    walkers.remove("Mara")
    assert walkers.positions() == [("Tiago", 100, 200)]


def test_someone_who_comes_back_starts_at_the_spawn_and_stands_still():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, open_field())
    walkers.remove("Mara")
    walkers.add("Mara")
    walk_for_one_second(walkers, open_field())
    assert walkers.positions() == [("Mara", 100, 200)]


# Walking


def test_one_second_to_the_right_is_90_units():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, open_field())
    x, y = position_of(walkers, "Mara")
    assert x == pytest.approx(100 + PLAYER_SPEED)
    assert PLAYER_SPEED == 90
    assert y == 200


def test_without_a_direction_nobody_moves():
    walkers = walkers_with("Mara")
    walk_for_one_second(walkers, open_field())
    assert position_of(walkers, "Mara") == (100, 200)


def test_the_direction_stays_until_it_is_changed():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 0, 1)
    walk_for_one_second(walkers, open_field())
    walkers.set_direction("Mara", 0, 0)
    walk_for_one_second(walkers, open_field())
    x, y = position_of(walkers, "Mara")
    assert (x, y) == (100, pytest.approx(200 + PLAYER_SPEED))


def test_only_the_player_who_asked_moves():
    walkers = walkers_with("Mara", "Tiago")
    walkers.set_direction("Mara", -1, 0)
    walkers.advance(ONE_TICK, open_field())
    assert position_of(walkers, "Mara")[0] < 100
    assert position_of(walkers, "Tiago") == (100, 200)


def test_a_player_walking_at_a_wall_stops_in_front_of_it():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, field_with_a_wall())
    # The player's right edge touches the wall's left side at x = 140.
    assert position_of(walkers, "Mara") == (140 - PLAYER_HALF_SIZE, 200)


def test_ghost_can_walk_through_walls_while_living_player_still_stops():
    walkers = walkers_with("Ghost", "Mara")
    walkers.set_direction("Ghost", 1, 0)
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second_with_ghosts(walkers, field_with_a_wall(), {"Ghost"})
    assert position_of(walkers, "Ghost")[0] > 140 + PLAYER_HALF_SIZE
    assert position_of(walkers, "Mara") == (140 - PLAYER_HALF_SIZE, 200)


def walk_for_one_second_with_ghosts(walkers, campus, ghosts):
    for _ in range(TICKS_PER_SECOND):
        walkers.advance(ONE_TICK, campus, ghosts=ghosts)


def test_a_long_pause_does_not_become_a_long_jump():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walkers.advance(30, open_field())
    # `movement.step` covers at most 0.1 seconds, which is 9 units.
    assert position_of(walkers, "Mara") == (pytest.approx(109), 200)


def test_on_the_real_campus_a_second_of_walking_is_at_most_90_units():
    campus = load_campus()
    spawn_x, spawn_y = campus["spawn"]["x"], campus["spawn"]["y"]
    walkers = Walkers()
    walkers.add("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, campus)
    x, y = position_of(walkers, "Mara")
    assert math.isfinite(x) and math.isfinite(y)
    assert spawn_x < x <= spawn_x + PLAYER_SPEED + 0.001
    assert y == spawn_y


# Is there news to send?


def test_a_newcomer_is_news_for_everybody():
    walkers = walkers_with("Mara")
    walkers.add("Tiago")
    assert walkers.advance(ONE_TICK, open_field()) is True
    assert walkers.names_to_tell() == ["Mara", "Tiago"]


def test_someone_leaving_is_news_for_those_who_stay():
    walkers = walkers_with("Mara", "Tiago")
    walkers.remove("Tiago")
    assert walkers.advance(ONE_TICK, open_field()) is True
    assert walkers.names_to_tell() == ["Mara"]


def test_a_move_is_news_for_everybody():
    walkers = walkers_with("Mara", "Tiago")
    walkers.set_direction("Mara", 1, 0)
    assert walkers.advance(ONE_TICK, open_field()) is True
    assert walkers.names_to_tell() == ["Mara", "Tiago"]


def test_when_nobody_moves_and_nobody_came_or_went_there_is_no_news():
    walkers = walkers_with("Mara", "Tiago")
    assert walkers.advance(ONE_TICK, open_field()) is False
    assert walkers.names_to_tell() == []


def test_walking_into_a_wall_without_getting_anywhere_is_no_news():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, field_with_a_wall())  # Now Mara touches the wall.
    walkers.mark_told("Mara")
    assert walkers.advance(ONE_TICK, field_with_a_wall()) is False


def test_news_stays_until_the_player_was_told():
    walkers = walkers_with("Mara", "Tiago")
    walkers.set_direction("Mara", 1, 0)
    walkers.advance(ONE_TICK, open_field())
    walkers.set_direction("Mara", 0, 0)
    walkers.mark_told("Mara")
    # Nobody moves in this step, but Tiago has not been told about the last one.
    assert walkers.advance(ONE_TICK, open_field()) is True
    assert walkers.names_to_tell() == ["Tiago"]
    walkers.mark_told("Tiago")
    assert walkers.advance(ONE_TICK, open_field()) is False


def test_an_empty_lobby_has_no_news():
    assert Walkers().advance(ONE_TICK, open_field()) is False


# Together with the lobby rules


def test_creating_and_joining_a_lobby_adds_the_players():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobby.walkers.advance(ONE_TICK, open_field())
    assert lobby.walkers.positions() == [("Mara", 100, 200), ("Tiago", 100, 200)]


def test_leaving_the_lobby_removes_the_position():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobby.walkers.advance(ONE_TICK, open_field())
    lobbies.leave("Mara")
    assert lobby.walkers.positions() == [("Tiago", 100, 200)]


def test_a_rejected_join_adds_nobody():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    assert lobbies.join("Mara", "ABCD") == (None, "already_in_lobby")
    lobby.walkers.advance(ONE_TICK, open_field())
    assert lobby.walkers.positions() == [("Mara", 100, 200)]


def test_all_lists_every_lobby():
    lobbies = Lobbies()
    assert lobbies.all() == []
    first, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    second, rejection_code = lobbies.create("Tiago", lambda: "WXYZ")
    assert lobbies.all() == [first, second]
    lobbies.leave("Mara")
    assert lobbies.all() == [second]


# Back to the spawn at the start of a round (M2-2.1)


def test_back_to_spawn_puts_everybody_on_the_spawn():
    walkers = walkers_with("Mara", "Tiago")
    walkers.set_direction("Mara", 1, 0)
    walkers.set_direction("Tiago", 0, 1)
    walk_for_one_second(walkers, open_field())
    walkers.set_direction("Mara", 0, 0)
    walkers.set_direction("Tiago", 0, 0)
    assert position_of(walkers, "Mara") != (100, 200)
    assert position_of(walkers, "Tiago") != (100, 200)

    walkers.back_to_spawn()
    assert walkers.advance(ONE_TICK, open_field()) is True
    assert walkers.positions() == [("Mara", 100, 200), ("Tiago", 100, 200)]


def test_back_to_spawn_is_news_for_everybody_even_if_nobody_moved():
    walkers = walkers_with("Mara", "Tiago")  # Both stand on the spawn already.
    assert walkers.names_to_tell() == []
    walkers.back_to_spawn()
    assert walkers.names_to_tell() == ["Mara", "Tiago"]
    assert walkers.advance(ONE_TICK, open_field()) is True


def test_a_player_holding_a_direction_walks_on_from_the_spawn():
    # The browser sends a direction only when it changes. If the start of a
    # round forgot it, a player holding a key would be stuck.
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walk_for_one_second(walkers, open_field())
    far_x = position_of(walkers, "Mara")[0]

    walkers.back_to_spawn()
    walkers.advance(ONE_TICK, open_field())
    x, y = position_of(walkers, "Mara")
    assert 100 < x < far_x
    assert y == 200


def test_back_to_spawn_with_nobody_there_changes_nothing():
    walkers = Walkers()
    walkers.back_to_spawn()
    assert walkers.positions() == []
    assert walkers.advance(ONE_TICK, open_field()) is False


def test_starting_a_round_puts_the_lobby_back_on_the_spawn():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobby.walkers.set_direction("Tiago", -1, 0)
    walk_for_one_second(lobby.walkers, open_field())
    lobby.walkers.set_direction("Tiago", 0, 0)

    assert lobbies.start("Mara")[1] is None
    lobby.walkers.advance(ONE_TICK, open_field())
    assert lobby.walkers.positions() == [("Mara", 100, 200), ("Tiago", 100, 200)]


def test_a_rejected_start_moves_nobody():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", lambda: "ABCD")
    lobbies.join("Tiago", "ABCD")
    lobby.walkers.set_direction("Tiago", -1, 0)
    walk_for_one_second(lobby.walkers, open_field())
    lobby.walkers.set_direction("Tiago", 0, 0)
    before = lobby.walkers.positions()

    assert lobbies.start("Tiago") == (None, "not_host")
    lobby.walkers.advance(ONE_TICK, open_field())
    assert lobby.walkers.positions() == before


# Asking for one player's position (M2-4.1: the range check of the stations)


def test_position_of_is_none_until_the_first_tick_placed_the_player():
    walkers = Walkers()
    walkers.add("Mara")
    assert walkers.position_of("Mara") is None
    walkers.advance(0.0, open_field())
    assert walkers.position_of("Mara") == (open_field()["spawn"]["x"], open_field()["spawn"]["y"])


def test_position_of_is_none_again_after_the_round_put_everybody_back():
    walkers = Walkers()
    walkers.add("Mara")
    walkers.advance(0.0, open_field())
    walkers.back_to_spawn()
    assert walkers.position_of("Mara") is None
