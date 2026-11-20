"""The countdown before a round, as plain rules without any network (M2-2.5, S-102).

The host's start begins a countdown of 5 seconds; the round starts when the
server asks after those 5 seconds. The time is always passed in, so these
tests decide what time it is.
"""

import pytest

from server import protocol
from server.net.lobbies import COUNTDOWN_SECONDS, MAX_PLAYERS, Lobbies

FIRST, SECOND, THIRD = protocol.CHARACTERS[:3]
# The time on the server's clock at which the host presses "Start game".
START = 100.0


def codes(*values):
    """A `pick_code` that returns the given codes one after the other."""
    remaining = list(values)
    return lambda: remaining.pop(0)


def lobby_with(*names, code="ABCD"):
    """Lobbies with one lobby: the first name created it, the others joined in order."""
    lobbies = Lobbies()
    lobbies.create(names[0], codes(code))
    for name in names[1:]:
        lobbies.join(name, code)
    return lobbies


def counting_lobby(*names):
    """Lobbies with one lobby whose countdown began at START. The first name is the host."""
    lobbies = lobby_with(*names)
    assert lobbies.start(names[0], START)[1] is None
    return lobbies


# The message and the numbers


def test_the_countdown_lasts_five_seconds():
    assert COUNTDOWN_SECONDS == 5


def test_the_countdown_message_carries_the_seconds():
    assert protocol.countdown(5) == {"type": "countdown", "seconds": 5}


def test_the_phase_countdown_has_its_own_name():
    assert protocol.PHASE_COUNTDOWN == "countdown"
    assert len({protocol.PHASE_LOBBY, protocol.PHASE_COUNTDOWN, protocol.PHASE_ROUND}) == 3


def test_lobby_state_carries_the_phase_countdown():
    state = protocol.lobby_state("ABCD", "Mara", [("Mara", FIRST)], "duel", "countdown")
    assert state["phase"] == "countdown"


# The host starts the countdown


@pytest.mark.parametrize("number_of_players", range(2, MAX_PLAYERS + 1))
def test_the_host_starts_the_countdown_with_two_to_eight_players(number_of_players):
    names = [f"Player{number}" for number in range(number_of_players)]
    lobbies = lobby_with(*names)
    lobby, rejection_code = lobbies.start("Player0", START)
    assert rejection_code is None
    assert lobby is lobbies.find("ABCD")
    assert lobby.phase == "countdown"
    assert lobby.countdown_is_running()
    assert not lobby.round_is_running() and not lobby.is_open()
    assert lobby.round_starts_at == START + 5


def test_a_new_lobby_is_open_and_counts_nothing():
    lobby = lobby_with("Mara", "Tiago").find("ABCD")
    assert lobby.is_open() and not lobby.countdown_is_running()
    assert lobby.round_starts_at is None
    assert lobby.countdown_seconds_left(START) == 0


def test_the_countdown_moves_nobody_and_sets_up_nothing():
    lobbies = lobby_with("Mara", "Tiago")
    lobby = lobbies.find("ABCD")
    lobby.walkers._walkers["Tiago"].position = (300.0, 200.0)
    lobbies.start("Mara", START)
    assert lobby.walkers.position_of("Tiago") == (300.0, 200.0)
    assert lobby.tasks is None and lobby.duel is None


@pytest.mark.parametrize(
    "seconds_later, seconds_left",
    [(0, 5), (0.01, 5), (0.99, 5), (1, 4), (2.5, 3), (4, 1), (4.99, 1), (5, 0), (9, 0)],
)
def test_the_seconds_left_are_rounded_up_and_never_negative(seconds_later, seconds_left):
    lobby = counting_lobby("Mara", "Tiago").find("ABCD")
    assert lobby.countdown_seconds_left(START + seconds_later) == seconds_left


# Rejected starts


def test_a_start_outside_a_lobby_is_rejected():
    assert lobby_with("Mara").start("Tiago", START) == (None, "not_in_lobby")


def test_a_start_by_a_member_who_is_not_host_is_rejected():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.start("Tiago", START) == (None, "not_host")
    assert lobbies.find("ABCD").is_open()


def test_a_start_with_too_few_players_begins_no_countdown():
    lobbies = lobby_with("Mara")
    assert lobbies.start("Mara", START) == (None, "too_few_players")
    lobby = lobbies.find("ABCD")
    assert lobby.is_open() and lobby.round_starts_at is None


@pytest.mark.parametrize("seconds_later", [0, 1, 4.9])
def test_a_second_start_during_the_countdown_is_rejected_and_does_not_restart_it(seconds_later):
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.start("Mara", START + seconds_later) == (None, "round_running")
    lobby = lobbies.find("ABCD")
    assert lobby.countdown_is_running()
    assert lobby.round_starts_at == START + 5  # neither later nor earlier


def test_a_start_during_the_round_is_rejected():
    lobbies = counting_lobby("Mara", "Tiago")
    lobbies.find("ABCD").start_round_if_due(START + 5)
    assert lobbies.start("Mara", START + 6) == (None, "round_running")
    assert lobbies.find("ABCD").round_is_running()


# During the countdown the lobby is closed


def test_joining_during_the_countdown_is_rejected():
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.join("Ines", "ABCD") == (None, "round_running")
    assert lobbies.find("ABCD").names() == ["Mara", "Tiago"]
    assert lobbies.lobby_of("Ines") is None


def test_a_full_lobby_that_counts_down_says_round_running_and_not_full():
    names = [f"Player{number}" for number in range(MAX_PLAYERS)]
    lobbies = counting_lobby(*names)
    assert lobbies.join("Ines", "ABCD") == (None, "round_running")


@pytest.mark.parametrize("name", ["Mara", "Tiago"])
def test_choosing_a_character_during_the_countdown_is_rejected(name):
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.choose_character(name, THIRD) == (None, False, "round_running")
    assert lobbies.find("ABCD").players() == [("Mara", FIRST), ("Tiago", SECOND)]


def test_choosing_the_own_character_again_during_the_countdown_is_rejected_too():
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.choose_character("Mara", FIRST) == (None, False, "round_running")


def test_choosing_the_mode_during_the_countdown_is_rejected():
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.choose_mode("Mara", "classic") == (None, "round_running")
    assert lobbies.find("ABCD").mode == "duel"


def test_a_member_who_is_not_host_still_hears_not_host_during_the_countdown():
    lobbies = counting_lobby("Mara", "Tiago")
    assert lobbies.choose_mode("Tiago", "duel") == (None, "not_host")
    assert lobbies.start("Tiago", START + 1) == (None, "not_host")


# The end of the countdown


@pytest.mark.parametrize("seconds_later", [0, 2.5, 4.999])
def test_before_the_five_seconds_are_over_no_round_starts(seconds_later):
    lobby = counting_lobby("Mara", "Tiago").find("ABCD")
    assert lobby.start_round_if_due(START + seconds_later) is False
    assert lobby.countdown_is_running()


@pytest.mark.parametrize("seconds_later", [5, 5.07, 60])
def test_after_five_seconds_the_round_starts_also_when_the_server_asks_late(seconds_later):
    lobby = counting_lobby("Mara", "Tiago").find("ABCD")
    assert lobby.start_round_if_due(START + seconds_later) is True
    assert lobby.phase == "round" and lobby.round_is_running()
    assert not lobby.countdown_is_running() and not lobby.is_open()
    assert lobby.round_starts_at is None
    assert lobby.countdown_seconds_left(START + seconds_later) == 0


def test_the_round_starts_exactly_once_however_often_the_server_asks():
    lobby = counting_lobby("Mara", "Tiago").find("ABCD")
    answers = [lobby.start_round_if_due(START + 5) for _ in range(3)]
    assert answers == [True, False, False]
    assert lobby.round_is_running()


def test_the_start_of_the_round_puts_everybody_on_the_spawn_and_not_before():
    lobbies = lobby_with("Mara", "Tiago")
    lobby = lobbies.find("ABCD")
    lobbies.start("Mara", START)
    # Tiago walks away during the countdown.
    lobby.walkers._walkers["Tiago"].position = (300.0, 200.0)
    assert lobby.start_round_if_due(START + 4) is False
    assert lobby.walkers.position_of("Tiago") == (300.0, 200.0)
    assert lobby.start_round_if_due(START + 5) is True
    spawn = lobby.walkers.position_of("Mara")
    assert lobby.walkers.position_of("Tiago") == spawn


def test_an_open_lobby_and_a_running_round_start_nothing():
    lobby = lobby_with("Mara", "Tiago").find("ABCD")
    assert lobby.start_round_if_due(START + 100) is False
    assert lobby.is_open()
    lobby.start_countdown(START)
    assert lobby.start_round_if_due(START + 5) is True
    assert lobby.start_round_if_due(START + 100) is False


def test_after_the_round_the_next_start_counts_five_seconds_again():
    lobbies = counting_lobby("Mara", "Tiago")
    lobby = lobbies.find("ABCD")
    lobby.start_round_if_due(START + 5)
    lobby.end_round()
    assert lobby.is_open()
    assert lobbies.start("Mara", START + 60) == (lobby, None)
    assert lobby.round_starts_at == START + 65
    assert lobby.start_round_if_due(START + 64.9) is False
    assert lobby.start_round_if_due(START + 65) is True


# Leaving during the countdown


def test_a_member_leaving_with_enough_players_left_changes_nothing_else():
    lobbies = counting_lobby("Mara", "Tiago", "Ines")
    lobby, new_host, rejection_code = lobbies.leave("Tiago")
    assert (new_host, rejection_code) == (None, None)
    assert lobby.countdown_is_running() and lobby.round_starts_at == START + 5
    assert lobby.host == "Mara" and lobby.names() == ["Mara", "Ines"]
    assert lobby.start_round_if_due(START + 5) is True


def test_the_host_leaving_changes_the_host_and_the_countdown_goes_on():
    lobbies = counting_lobby("Mara", "Tiago", "Ines")
    lobby, new_host, rejection_code = lobbies.leave("Mara")
    assert (new_host, rejection_code) == ("Tiago", None)
    assert lobby.countdown_is_running() and lobby.round_starts_at == START + 5
    # The new host cannot press start again either.
    assert lobbies.start("Tiago", START + 1) == (None, "round_running")
    assert lobby.start_round_if_due(START + 5) is True
    assert lobby.names() == ["Tiago", "Ines"]


@pytest.mark.parametrize("leaver, stays", [("Tiago", "Mara"), ("Mara", "Tiago")])
def test_too_few_players_left_cancels_the_countdown_at_once(leaver, stays):
    lobbies = counting_lobby("Mara", "Tiago")
    lobby, new_host, rejection_code = lobbies.leave(leaver)
    assert rejection_code is None
    assert lobby.phase == "lobby" and lobby.is_open()
    assert lobby.round_starts_at is None
    assert lobby.host == stays
    # Nothing is left that could start a round later.
    assert lobby.start_round_if_due(START + 5) is False
    assert lobby.is_open() and lobby.tasks is None and lobby.duel is None


def test_after_a_cancelled_countdown_the_lobby_works_as_before():
    lobbies = counting_lobby("Mara", "Tiago")
    lobbies.leave("Tiago")
    assert lobbies.start("Mara", START + 2) == (None, "too_few_players")
    lobby, rejection_code = lobbies.join("Ines", "ABCD")
    assert rejection_code is None
    assert lobbies.choose_character("Ines", THIRD) == (lobby, True, None)
    assert lobbies.choose_mode("Mara", "duel") == (lobby, None)
    # A new start counts the full five seconds from its own time.
    assert lobbies.start("Mara", START + 3) == (lobby, None)
    assert lobby.round_starts_at == START + 8
    assert lobby.start_round_if_due(START + 5) is False
    assert lobby.start_round_if_due(START + 8) is True


def test_three_players_of_whom_two_leave_cancel_only_at_the_second():
    lobbies = counting_lobby("Mara", "Tiago", "Ines")
    assert lobbies.leave("Ines")[0].countdown_is_running()
    assert lobbies.leave("Tiago")[0].is_open()


# The cancel rule follows the mode. Classic is not built yet, so the message
# check refuses it (S-91); the rule itself stores the mode it is given, and
# `protocol.MIN_PLAYERS` already says that Classic needs four players.


def classic_lobby(*names):
    lobbies = lobby_with(*names)
    assert lobbies.choose_mode(names[0], "classic")[1] is None
    return lobbies


def test_classic_needs_four_players_for_its_countdown():
    assert protocol.MIN_PLAYERS["classic"] == 4
    lobbies = classic_lobby("Mara", "Tiago", "Ines")
    assert lobbies.find("ABCD").has_too_few_players()
    assert lobbies.start("Mara", START) == (None, "too_few_players")
    lobbies.join("Rui", "ABCD")
    assert not lobbies.find("ABCD").has_too_few_players()
    assert lobbies.start("Mara", START)[1] is None
    assert lobbies.find("ABCD").countdown_is_running()


def test_a_classic_countdown_of_five_goes_on_with_four_and_is_cancelled_with_three():
    lobbies = classic_lobby("Mara", "Tiago", "Ines", "Rui", "Sofia")
    lobbies.start("Mara", START)
    lobby = lobbies.leave("Sofia")[0]
    assert lobby.countdown_is_running() and lobby.round_starts_at == START + 5
    # Three players would be enough for a Duel, but this lobby plays Classic.
    lobbies.leave("Rui")
    assert lobby.is_open() and lobby.round_starts_at is None
    assert lobby.mode == "classic" and lobby.names() == ["Mara", "Tiago", "Ines"]
    assert lobby.start_round_if_due(START + 5) is False


def test_a_duel_countdown_of_three_is_not_cancelled_where_classic_would_be():
    lobbies = counting_lobby("Mara", "Tiago", "Ines")
    assert lobbies.leave("Ines")[0].countdown_is_running()


def test_a_lobby_that_empties_during_the_countdown_is_deleted():
    lobbies = counting_lobby("Mara", "Tiago")
    lobbies.leave("Mara")
    lobby, new_host, rejection_code = lobbies.leave("Tiago")
    assert rejection_code is None and new_host is None
    assert lobbies.count() == 0 and lobbies.all() == []
    assert lobbies.find("ABCD") is None
    assert lobby.is_open()  # also the forgotten lobby counts nothing any more


def test_the_code_of_a_lobby_that_emptied_during_the_countdown_gives_a_fresh_lobby():
    lobbies = counting_lobby("Mara", "Tiago")
    lobbies.leave("Mara")
    lobbies.leave("Tiago")
    lobby, rejection_code = lobbies.create("Ines", codes("ABCD"))
    assert rejection_code is None
    assert lobby.is_open() and lobby.round_starts_at is None


def test_leaving_during_a_round_cancels_nothing():
    lobbies = counting_lobby("Mara", "Tiago")
    lobby = lobbies.find("ABCD")
    lobby.start_round_if_due(START + 5)
    lobbies.leave("Tiago")
    assert lobby.round_is_running()
