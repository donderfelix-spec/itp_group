"""The messages for statistics: asking for the profile and the leaderboard (M2-2.4)."""

import json

import pytest

from server import protocol
from server.protocol import ProtocolError, parse_client_message

MESSAGE_TYPES = ["get_profile", "get_leaderboard"]


def rejected_code(raw):
    with pytest.raises(ProtocolError) as raised:
        parse_client_message(raw)
    return raised.value.code


# Accepted


@pytest.mark.parametrize("message_type", MESSAGE_TYPES)
def test_the_message_is_accepted_and_returned_exactly(message_type):
    assert parse_client_message(json.dumps({"type": message_type})) == {"type": message_type}


# Rejected


@pytest.mark.parametrize("message_type", MESSAGE_TYPES)
@pytest.mark.parametrize("field, value", [("name", "Mara"), ("limit", 1000), ("mode", "duel"), ("guest", False)])
def test_no_field_is_accepted_so_nobody_can_ask_for_another_account(message_type, field, value):
    assert rejected_code(json.dumps({"type": message_type, field: value})) == "unknown_field"


@pytest.mark.parametrize("message_type", ["profile", "leaderboard", "GET_PROFILE", "get_profile ", "get_statistics"])
def test_similar_types_are_unknown(message_type):
    assert rejected_code(json.dumps({"type": message_type})) == "unknown_type"


# Edge cases


@pytest.mark.parametrize("message_type", MESSAGE_TYPES)
def test_the_message_as_a_list_or_text_is_rejected(message_type):
    assert rejected_code(json.dumps([{"type": message_type}])) == "not_object"
    assert rejected_code(json.dumps(message_type)) == "not_object"


@pytest.mark.parametrize("message_type", MESSAGE_TYPES)
def test_the_message_with_far_too_much_padding_is_rejected(message_type):
    raw = json.dumps({"type": message_type}) + " " * protocol.MAX_MESSAGE_BYTES
    assert rejected_code(raw) == "too_large"


# What the server sends


def test_the_profile_carries_rounds_and_wins_per_mode_and_the_best_duel_time():
    assert protocol.profile("Mara", [("duel", 3, 1)], 72.4) == {
        "type": "profile",
        "name": "Mara",
        "modes": [{"mode": "duel", "title": "Duel", "rounds": 3, "wins": 1}],
        "best_duel_seconds": 72.4,
    }


def test_the_profile_of_a_second_mode_is_one_more_row():
    modes = protocol.profile("Mara", [("duel", 3, 1), ("classic", 2, 2)], None)["modes"]
    assert modes[1] == {"mode": "classic", "title": "Classic", "rounds": 2, "wins": 2}


def test_the_profile_without_a_time_carries_null():
    assert protocol.profile("Mara", [("duel", 0, 0)], None)["best_duel_seconds"] is None


def test_the_leaderboard_carries_place_name_win_totals_and_time_and_nothing_else():
    rows = [
        {"place": 1, "name": "Mara", "wins": 3, "classic_wins": 2, "duel_wins": 1,
         "best_seconds": 72.4, "name_key": "mara", "password_hash": "x"},
        {"place": 2, "name": "Tiago", "wins": 1, "classic_wins": 1, "duel_wins": 0, "best_seconds": None},
    ]
    assert protocol.leaderboard(rows) == {
        "type": "leaderboard",
        "players": [
            {"place": 1, "name": "Mara", "wins": 3, "classic_wins": 2, "duel_wins": 1, "best_duel_seconds": 72.4},
            {"place": 2, "name": "Tiago", "wins": 1, "classic_wins": 1, "duel_wins": 0, "best_duel_seconds": None},
        ],
    }


def test_an_empty_leaderboard_has_an_empty_list():
    assert protocol.leaderboard([]) == {"type": "leaderboard", "players": []}


def test_the_two_new_texts():
    assert protocol.rejection("guest_no_statistics") == {
        "type": "error",
        "code": "guest_no_statistics",
        "message": "Guests have no statistics. Sign up to keep yours.",
    }
    assert protocol.rejection("statistics_unavailable") == {
        "type": "error",
        "code": "statistics_unavailable",
        "message": "Statistics are unavailable right now.",
    }
