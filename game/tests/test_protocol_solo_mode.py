"""Choosing Solo, the practice round for one player, in `server/protocol.py`.

"solo" is a built mode next to "duel". Only the exact text is a mode:
anything else is refused with the text of DESIGN.md, section 9.
"""

import json

import pytest

from server import protocol
from server.protocol import ProtocolError, parse_client_message

BAD_MODE = ("bad_mode", "That mode does not exist.")


def rejected(message):
    with pytest.raises(ProtocolError) as error:
        parse_client_message(json.dumps(message))
    return (error.value.code, error.value.message)


# Accepted


@pytest.mark.parametrize("mode", ["duel", "classic", "solo"])
def test_every_built_mode_is_accepted(mode):
    message = {"type": "choose_mode", "mode": mode}
    assert parse_client_message(json.dumps(message)) == message


def test_the_check_itself_gives_back_the_mode():
    assert protocol._check_mode("solo") == "solo"
    assert protocol._check_mode("duel") == "duel"


def test_solo_has_a_name_and_needs_one_player():
    assert protocol.MODES == ("duel", "classic", "solo")
    assert protocol.MODE_NAMES["solo"] == "Solo"
    assert protocol.MIN_PLAYERS["solo"] == 1


def test_duel_stays_the_mode_of_a_new_lobby():
    assert protocol.DEFAULT_MODE == "duel"


# Rejected


@pytest.mark.parametrize(
    "mode",
    ["test", "Test", "Solo", "SOLO", "solo ", " solo", "practice", "", None, 1, 0, True, False, ["solo"], {"mode": "solo"}],
    ids=repr,
)
def test_anything_that_is_not_exactly_solo_or_duel_is_rejected(mode):
    assert rejected({"type": "choose_mode", "mode": mode}) == BAD_MODE


@pytest.mark.parametrize("mode", ["test", "Solo", "solo ", "", None, 1, True, ["solo"]], ids=repr)
def test_the_check_itself_refuses_with_the_text_of_the_design(mode):
    with pytest.raises(ProtocolError) as error:
        protocol._check_mode(mode)
    assert (error.value.code, error.value.message) == BAD_MODE


# Edge cases


def test_choose_mode_solo_with_an_extra_field_is_rejected():
    with pytest.raises(ProtocolError) as error:
        parse_client_message(json.dumps({"type": "choose_mode", "mode": "solo", "players": 1}))
    assert error.value.code == "unknown_field"


def test_start_game_cannot_carry_solo():
    with pytest.raises(ProtocolError) as error:
        parse_client_message(json.dumps({"type": "start_game", "mode": "solo"}))
    assert error.value.code == "unknown_field"


def test_a_lobby_state_can_carry_solo():
    state = protocol.lobby_state("ABCD", "Mara", [("Mara", "surfer")], "solo", "round")
    assert state["mode"] == "solo"
