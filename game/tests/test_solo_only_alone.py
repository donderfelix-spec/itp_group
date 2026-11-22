"""Solo only when alone (Felix, 2026-11-21, brief D).

The server decides: Solo can be chosen and started only by a host who is
alone in the lobby. With two or more players it is refused with
"solo_needs_one_player" and "Solo is only for one player alone.". When a
second player joins a Solo lobby, the mode becomes Duel before anybody is
told.

Duel and Classic can still be chosen by a host who is alone; only their
start is refused, as on main. Main's tests need that
(test_lobbies.py::test_choose_mode_sets_the_mode_it_is_given and
test_server_countdown.py::test_after_a_cancelled_countdown_join_character_mode_and_start_work_again).
"""

import json

import pytest

from server import protocol
from server.net.lobbies import Lobbies, mode_after_a_join, solo_refusal
from server.protocol import ProtocolError, parse_client_message
from task_helpers import ask, client, clock, connect, player  # noqa: F401

START = 1000.0
SOLO_ERROR = {"type": "error", "code": "solo_needs_one_player", "message": "Solo is only for one player alone."}


def lobby_with(*names):
    """Lobbies with one lobby "ABCD": the first name created it, the others joined in order."""
    lobbies = Lobbies()
    lobbies.create(names[0], lambda: "ABCD")
    for name in names[1:]:
        assert lobbies.join(name, "ABCD")[1] is None
    return lobbies


# The plain rules


@pytest.mark.parametrize("mode", ["duel", "classic", "solo"])
def test_alone_every_mode_may_be_chosen(mode):
    assert solo_refusal(mode, 1) is None


@pytest.mark.parametrize("count", [2, 3, 8])
def test_with_others_solo_is_refused_and_the_other_modes_are_not(count):
    assert solo_refusal("solo", count) == "solo_needs_one_player"
    assert solo_refusal("duel", count) is None
    assert solo_refusal("classic", count) is None


@pytest.mark.parametrize("mode, count, after", [
    ("solo", 1, "solo"),
    ("solo", 2, "duel"),
    ("solo", 8, "duel"),
    ("duel", 2, "duel"),
    ("classic", 2, "classic"),
    ("duel", 1, "duel"),
])
def test_after_a_join_only_solo_with_others_becomes_duel(mode, count, after):
    assert mode_after_a_join(mode, count) == after


def test_the_text_is_the_one_of_the_design():
    assert protocol.solo_needs_one_player() == SOLO_ERROR


# The lobby rules: accepted


def test_a_host_alone_chooses_and_starts_solo():
    lobbies = lobby_with("Mara")
    lobby, refused = lobbies.choose_mode("Mara", "solo")
    assert refused is None and lobby.mode == "solo"
    assert lobbies.start("Mara", START) == (lobby, None)
    assert lobby.countdown_is_running()


@pytest.mark.parametrize("mode", ["duel", "classic"])
def test_with_two_players_duel_and_classic_are_chosen(mode):
    lobbies = lobby_with("Mara", "Tiago")
    lobby, refused = lobbies.choose_mode("Mara", mode)
    assert refused is None and lobby.mode == mode


@pytest.mark.parametrize("mode", ["duel", "classic"])
def test_a_host_alone_may_still_choose_duel_or_classic_but_not_start_it(mode):
    # The variant that keeps main's tests: only the start is refused.
    lobbies = lobby_with("Mara")
    lobby, refused = lobbies.choose_mode("Mara", mode)
    assert refused is None and lobby.mode == mode
    assert lobbies.start("Mara", START) == (None, "too_few_players")


# The lobby rules: rejected


@pytest.mark.parametrize("names", [("Mara", "Tiago"), ("Mara", "Tiago", "Ines", "Rui", "Sofia")])
def test_with_others_solo_cannot_be_chosen_and_nothing_changes(names):
    lobbies = lobby_with(*names)
    lobbies.choose_mode("Mara", "classic")
    assert lobbies.choose_mode("Mara", "solo") == (None, "solo_needs_one_player")
    assert lobbies.find("ABCD").mode == "classic"


def test_solo_with_others_cannot_be_started():
    lobbies = lobby_with("Mara", "Tiago")
    lobby = lobbies.find("ABCD")
    lobby.mode = "solo"  # cannot happen through the rules; the start checks anyway
    assert lobbies.start("Mara", START) == (None, "solo_needs_one_player")
    assert lobby.is_open() and lobby.mode == "solo"


def test_the_older_checks_come_first():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.choose_mode("Tiago", "solo") == (None, "not_host")
    assert lobbies.choose_mode("Ines", "solo") == (None, "not_in_lobby")


# Edge cases: the number of players changes


def test_a_second_player_joining_a_solo_lobby_turns_it_into_a_duel():
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "solo")
    lobby, refused = lobbies.join("Tiago", "ABCD")
    assert refused is None and lobby.mode == "duel"


def test_when_the_second_player_leaves_the_mode_stays():
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "solo")
    lobbies.join("Tiago", "ABCD")
    lobby = lobbies.leave("Tiago")[0]
    assert lobby.mode == "duel"
    assert lobbies.start("Mara", START) == (None, "too_few_players")
    assert lobbies.choose_mode("Mara", "solo") == (lobby, None)


def test_when_others_leave_classic_stays_chosen():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    lobbies.choose_mode("Mara", "classic")
    lobbies.leave("Tiago")
    lobby = lobbies.leave("Ines")[0]
    assert lobby.mode == "classic"


def test_a_host_who_leaves_a_solo_lobby_leaves_no_lobby_behind():
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "solo")
    lobbies.leave("Mara")
    assert lobbies.find("ABCD") is None


def test_a_solo_countdown_cannot_be_joined():
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "solo")
    lobbies.start("Mara", START)
    assert lobbies.join("Tiago", "ABCD") == (None, "round_running")
    assert lobbies.find("ABCD").mode == "solo"


@pytest.mark.parametrize("mode", ["Solo", "solo ", "SOLO", "", None, 1, True, ["solo"]], ids=repr)
def test_malformed_modes_are_still_refused_by_the_message_check(mode):
    with pytest.raises(ProtocolError) as error:
        parse_client_message(json.dumps({"type": "choose_mode", "mode": mode}))
    assert error.value.code == "bad_mode"


# Over the WebSocket


def test_over_the_websocket_two_players_cannot_choose_solo(connect):
    mara = player(connect, "Mara")
    code = ask(mara, {"type": "create_lobby"})["code"]
    tiago = player(connect, "Tiago")
    assert ask(tiago, {"type": "join_lobby", "code": code})["mode"] == "duel"
    mara.receive_json()  # the lobby_state with Tiago
    assert ask(mara, {"type": "choose_mode", "mode": "solo"}) == SOLO_ERROR


def test_over_the_websocket_everybody_is_told_that_a_solo_lobby_became_a_duel(connect):
    mara = player(connect, "Mara")
    code = ask(mara, {"type": "create_lobby"})["code"]
    assert ask(mara, {"type": "choose_mode", "mode": "solo"})["mode"] == "solo"
    tiago = player(connect, "Tiago")
    joined = ask(tiago, {"type": "join_lobby", "code": code})
    told = mara.receive_json()
    assert joined["mode"] == told["mode"] == "duel"
    assert [entry["name"] for entry in told["players"]] == ["Mara", "Tiago"]


def test_over_the_websocket_a_host_alone_cannot_start_a_duel(connect):
    mara = player(connect, "Mara")
    ask(mara, {"type": "create_lobby"})
    assert ask(mara, {"type": "choose_mode", "mode": "duel"})["mode"] == "duel"
    assert ask(mara, {"type": "start_game"}) == protocol.too_few_players("duel")
