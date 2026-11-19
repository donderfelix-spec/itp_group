import random

import pytest

from rules import apply_fail, assign_roles, assign_tasks, can_fail, check_winner, progress


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


def failure_state():
    return {
        "roles": {"fr": "FR", "hp": "HP", "hp2": "HP", "other_fr": "FR"},
        "tasks": {},
        "completed_tasks": {},
        "eliminated": set(),
        "positions": {
            "fr": (0.0, 0.0),
            "hp": (2.0, 0.0),
            "hp2": (1.0, 0.0),
            "other_fr": (1.0, 1.0),
        },
        "last_fail_at": {},
        "f_sheets": {},
    }


def test_fail_is_allowed_at_exactly_two_fields_and_rejected_beyond_range():
    state = failure_state()
    assert can_fail(state, "fr", "hp", 100.0)

    state["positions"]["hp"] = (2.01, 0.0)
    assert not can_fail(state, "fr", "hp", 100.0)


def test_fail_cooldown_blocks_before_25_seconds_and_allows_at_25_seconds():
    state = failure_state()
    state["last_fail_at"]["fr"] = 100.0

    assert not can_fail(state, "fr", "hp", 124.99)
    assert can_fail(state, "fr", "hp", 125.0)


def test_fail_rejects_a_free_rider_or_ghost_as_target():
    state = failure_state()

    assert not can_fail(state, "fr", "other_fr", 100.0)
    state["eliminated"].add("hp")
    assert not can_fail(state, "fr", "hp", 100.0)


def test_a_high_performer_or_ghost_cannot_act_as_the_free_rider():
    state = failure_state()

    assert not can_fail(state, "hp", "hp2", 100.0)
    state["eliminated"].add("fr")
    assert not can_fail(state, "fr", "hp", 100.0)


def test_apply_fail_returns_new_state_with_ghost_and_f_sheet_without_mutating_input():
    state = failure_state()
    original_eliminated = set(state["eliminated"])
    sheet_position = (1.25, 0.75)

    updated = apply_fail(state, "fr", "hp", 100.0, sheet_position)

    assert updated is not state
    assert "hp" in updated["eliminated"]
    assert updated["last_fail_at"]["fr"] == 100.0
    assert updated["f_sheets"] == {"f-sheet-1": sheet_position}
    assert state["eliminated"] == original_eliminated
    assert state["last_fail_at"] == {}
    assert state["f_sheets"] == {}


def test_a_free_rider_cannot_fail_themselves():
    state = failure_state()

    assert not can_fail(state, "fr", "fr", 100.0)
    with pytest.raises(ValueError, match="cannot fail"):
        apply_fail(state, "fr", "fr", 100.0, (0.0, 0.0))


