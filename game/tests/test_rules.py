import random

import pytest

from rules import assign_roles, assign_tasks, check_winner, progress


@pytest.mark.parametrize(
    ("player_count", "expected_free_riders"),
    [(4, 1), (5, 1), (6, 2), (8, 2)],
)
def test_role_count_follows_the_classic_player_count_rule(
    player_count, expected_free_riders
):
    roles = assign_roles([f"player-{i}" for i in range(player_count)], random.Random(12))

    assert sum(role == "FR" for role in roles.values()) == expected_free_riders
    assert sum(role == "HP" for role in roles.values()) == player_count - expected_free_riders


@pytest.mark.parametrize("player_count", [3, 9])
def test_role_assignment_rejects_an_invalid_player_count(player_count):
    with pytest.raises(ValueError, match="4 and 8"):
        assign_roles([f"player-{i}" for i in range(player_count)], random.Random(1))


def test_role_assignment_is_repeatable_for_the_same_seed():
    players = [f"player-{i}" for i in range(8)]

    assert assign_roles(players, random.Random(41)) == assign_roles(
        players, random.Random(41)
    )


def test_role_assignment_changes_with_a_different_seed():
    players = [f"player-{i}" for i in range(8)]

    assert assign_roles(players, random.Random(41)) != assign_roles(
        players, random.Random(42)
    )


def test_role_assignment_rejects_duplicate_player_ids():
    with pytest.raises(ValueError, match="unique"):
        assign_roles(["A", "B", "C", "A"], random.Random(1))


def test_each_player_gets_four_distinct_tasks_and_fr_tasks_are_fake():
    roles = {"A": "HP", "B": "FR", "C": "HP", "D": "HP"}
    stations = ["canteen", "cafe", "lecture-hall", "ctt", "pingo-doce"]

    tasks = assign_tasks(roles, stations, random.Random(8))

    assert set(tasks) == set(roles)
    assert all(len(player_tasks) == 4 for player_tasks in tasks.values())
    assert all(len(set(player_tasks)) == 4 for player_tasks in tasks.values())
    assert set(tasks["B"]) <= set(stations)  # FR receives fake station tasks too.


def test_assign_tasks_rejects_fewer_than_four_stations():
    with pytest.raises(ValueError, match="At least 4 stations"):
        assign_tasks({"A": "HP"}, ["canteen", "cafe", "ctt"], random.Random(1))


def test_progress_ignores_fr_fake_tasks_and_counts_eliminated_hp_work():
    state = {
        "roles": {"A": "HP", "B": "HP", "C": "FR"},
        "tasks": {
            "A": ["a1", "a2", "a3", "a4"],
            "B": ["b1", "b2", "b3", "b4"],
            "C": ["f1", "f2", "f3", "f4"],
        },
        "completed_tasks": {
            "A": ["a1", "a2", "not-assigned"],
            "B": ["b1", "b2"],
            "C": ["f1", "f2", "f3", "f4"],
        },
        "eliminated": {"A"},
    }

    assert progress(state) == pytest.approx(0.5)


def test_full_progress_wins_for_hp_even_when_a_free_rider_is_alive():
    state = {
        "roles": {"A": "HP", "B": "HP", "C": "HP", "D": "FR"},
        "tasks": {player: [f"{player}{i}" for i in range(4)] for player in "ABCD"},
        "completed_tasks": {player: [f"{player}{i}" for i in range(4)] for player in "ABC"},
        "eliminated": set(),
    }

    assert progress(state) == 1.0
    assert check_winner(state) == "HP"


def test_all_free_riders_eliminated_wins_for_hp_before_parity():
    state = {
        "roles": {"A": "HP", "B": "HP", "C": "HP", "D": "FR"},
        "tasks": {player: [f"{player}{i}" for i in range(4)] for player in "ABCD"},
        "completed_tasks": {},
        "eliminated": {"D"},
    }

    assert check_winner(state) == "HP"


def test_equal_living_free_riders_and_high_performers_wins_for_fr():
    state = {
        "roles": {"A": "HP", "B": "HP", "C": "HP", "D": "FR", "E": "FR"},
        "tasks": {player: [f"{player}{i}" for i in range(4)] for player in "ABCDE"},
        "completed_tasks": {},
        "eliminated": {"A", "B", "D"},
    }

    assert check_winner(state) == "FR"


def test_no_winner_while_hp_have_more_living_players_and_tasks_remain():
    state = {
        "roles": {"A": "HP", "B": "HP", "C": "HP", "D": "FR"},
        "tasks": {player: [f"{player}{i}" for i in range(4)] for player in "ABCD"},
        "completed_tasks": {"A": ["A0"]},
        "eliminated": set(),
    }

    assert check_winner(state) is None


