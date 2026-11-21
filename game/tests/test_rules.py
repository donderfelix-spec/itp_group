import random

import pytest

from rules import (
    apply_fail,
    assign_roles,
    assign_tasks,
    call_emergency,
    can_emergency,
    can_fail,
    can_report,
    check_winner,
    progress,
    role_reveal_for,
    report_sheet,
)


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


def test_fail_is_allowed_at_exactly_five_fields_and_rejected_beyond_range():
    state = failure_state()
    state["positions"]["hp"] = (5.0, 0.0)
    assert can_fail(state, "fr", "hp", 100.0)

    state["positions"]["hp"] = (6.0, 0.0)
    assert not can_fail(state, "fr", "hp", 100.0)


def test_fail_cooldown_blocks_before_15_seconds_and_allows_at_15_seconds():
    state = failure_state()
    state["last_fail_at"]["fr"] = 100.0

    assert not can_fail(state, "fr", "hp", 114.99)
    assert can_fail(state, "fr", "hp", 115.0)


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


def meeting_state():
    return {
        **failure_state(),
        "f_sheets": {"sheet-1": (3.0, 4.0)},
        "task_timers": {"task-1": 12.5},
        "emergency_used": set(),
        "meeting_triggers": set(),
        "phase": "playing",
    }


def test_ghost_cannot_report_or_call_emergency():
    state = meeting_state()
    state["eliminated"].add("hp")

    assert not can_report(state, "hp", "sheet-1", (3.0, 4.0))
    assert not can_emergency(state, "hp")
    with pytest.raises(ValueError, match="cannot report"):
        report_sheet(state, "hp", "sheet-1", (3.0, 4.0))
    with pytest.raises(ValueError, match="cannot call"):
        call_emergency(state, "hp")


def test_report_starts_meeting_removes_sheet_and_cannot_be_repeated():
    state = meeting_state()

    assert can_report(state, "hp", "sheet-1", (3.0, 4.0))
    updated = report_sheet(state, "hp", "sheet-1", (3.0, 4.0))

    assert updated["phase"] == "meeting"
    assert updated["meeting"]["active"] is True
    assert updated["meeting"]["reason"] == "report"
    assert updated["f_sheets"]["sheet-1"] == state["f_sheets"]["sheet-1"]
    assert not can_report(updated, "fr", "sheet-1", (3.0, 4.0))
    with pytest.raises(ValueError, match="cannot report"):
        report_sheet(updated, "fr", "sheet-1", (3.0, 4.0))


def test_emergency_button_can_be_used_once_per_player():
    state = meeting_state()

    assert can_emergency(state, "fr")
    updated = call_emergency(state, "fr")

    assert updated["phase"] == "meeting"
    assert updated["meeting"]["reason"] == "emergency"
    assert "fr" in updated["emergency_used"]
    with pytest.raises(ValueError, match="cannot call"):
        call_emergency(updated, "fr")


@pytest.mark.parametrize("reason", ["report", "emergency"])
def test_meeting_pauses_timers_without_changing_their_values(reason):
    state = meeting_state()
    state["last_fail_at"] = {"fr": 90.0}
    if reason == "report":
        updated = report_sheet(state, "hp", "sheet-1", (3.0, 4.0))
    else:
        updated = call_emergency(state, "hp")

    assert updated["timers_paused"] is True
    assert updated["task_timers"] == {"task-1": 12.5}
    assert updated["last_fail_at"] == {"fr": 90.0}
    assert not can_fail(updated, "fr", "hp2", 100.0)
    assert "timers_paused" not in state
    assert state["task_timers"] == {"task-1": 12.5}


@pytest.mark.parametrize(("done", "expected"), [(0, 0.0), (4, 0.5), (8, 1.0)])
def test_progress_is_zero_half_or_full(done, expected):
    state = {
        "roles": {"hp1": "HP", "hp2": "HP", "fr": "FR"},
        "tasks": {"hp1": ["a", "b", "c", "d"], "hp2": ["e", "f", "g", "h"], "fr": ["i", "j", "k", "l"]},
        "completed_tasks": {"hp1": ["a", "b", "c", "d"][:min(done, 4)], "hp2": ["e", "f", "g", "h"][:max(0, done - 4)], "fr": ["i", "j", "k", "l"]},
        "eliminated": set(),
    }
    assert progress(state) == pytest.approx(expected)


def test_end_reason_reports_each_winner_condition_in_order():
    from rules import end_reason

    base = {
        "roles": {"hp1": "HP", "hp2": "HP", "hp3": "HP", "fr": "FR"},
        "tasks": {"hp1": ["a"], "hp2": ["b"], "hp3": ["c"], "fr": ["fake"]},
        "completed_tasks": {},
        "eliminated": set(),
    }
    assert end_reason(base) is None
    assert end_reason({**base, "completed_tasks": {"hp1": ["a"], "hp2": ["b"], "hp3": ["c"]}}) == "bar_full"
    assert end_reason({**base, "eliminated": {"fr"}}) == "all_free_riders_eliminated"
    assert end_reason({**base, "eliminated": {"hp1", "hp2"}}) == "free_riders_reached_parity"


def test_role_reveal_is_private_for_living_players_and_absent_for_ghosts():
    from rules import role_reveal_for

    state = {
        "roles": {"hp": "HP", "fr1": "FR", "fr2": "FR"},
        "tasks": {},
        "completed_tasks": {},
        "eliminated": set(),
    }
    start_cards = {player_id: role_reveal_for(state, player_id) for player_id in state["roles"]}
    assert all(card is not None for card in start_cards.values())
    assert start_cards["hp"] == {"role": "HP"}
    assert role_reveal_for({**state, "eliminated": {"hp"}}, "hp") is None
    assert role_reveal_for(state, "fr1") == {"role": "FR", "other_free_riders": ["fr2"]}
    assert role_reveal_for(state, "fr2") == {"role": "FR", "other_free_riders": ["fr1"]}
