"""The lobby rules, without any network. Players are plain names here."""

import pytest

from server import protocol
from server.net.lobbies import MAX_PLAYERS, Lobbies
from server.net.sessions import Sessions

FIRST, SECOND, THIRD = protocol.CHARACTERS[:3]


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


def full_lobby():
    return lobby_with(*[f"Player{number}" for number in range(MAX_PLAYERS)])


# Accepted


def test_create_makes_a_lobby_with_the_creator_as_host():
    lobbies = Lobbies()
    lobby, rejection_code = lobbies.create("Mara", codes("ABCD"))
    assert rejection_code is None
    assert lobby.code == "ABCD"
    assert lobby.host == "Mara"
    assert lobby.players() == [("Mara", FIRST)]
    assert lobbies.find("ABCD") is lobby
    assert lobbies.lobby_of("Mara") is lobby


def test_join_adds_the_player_after_the_others():
    lobbies = lobby_with("Mara")
    lobby, rejection_code = lobbies.join("Tiago", "ABCD")
    assert rejection_code is None
    assert lobby.host == "Mara"
    assert lobby.players() == [("Mara", FIRST), ("Tiago", SECOND)]
    assert lobbies.lobby_of("Tiago") is lobby


def test_eight_players_fit_and_all_have_different_characters():
    lobby = full_lobby().find("ABCD")
    assert len(lobby.names()) == 8
    assert [character for name, character in lobby.players()] == list(protocol.CHARACTERS)


def test_choose_character_changes_the_character_and_keeps_the_order():
    lobbies = lobby_with("Mara", "Tiago")
    lobby, changed, rejection_code = lobbies.choose_character("Mara", "surfer")
    assert rejection_code is None
    assert changed is True
    assert lobby.players() == [("Mara", "surfer"), ("Tiago", SECOND)]


def test_choosing_the_character_you_have_is_accepted_and_changes_nothing():
    lobbies = lobby_with("Mara", "Tiago")
    lobby, changed, rejection_code = lobbies.choose_character("Mara", FIRST)
    assert rejection_code is None
    assert changed is False
    assert lobby.players() == [("Mara", FIRST), ("Tiago", SECOND)]


def test_a_character_someone_gave_up_can_be_chosen():
    lobbies = lobby_with("Mara", "Tiago")
    lobbies.choose_character("Mara", "surfer")
    lobby, changed, rejection_code = lobbies.choose_character("Tiago", FIRST)
    assert rejection_code is None
    assert lobby.character_of("Tiago") == FIRST


def test_leave_takes_the_player_out():
    lobbies = lobby_with("Mara", "Tiago")
    lobby, new_host, rejection_code = lobbies.leave("Tiago")
    assert rejection_code is None
    assert new_host is None  # Tiago was not the host.
    assert lobby.host == "Mara"
    assert lobby.players() == [("Mara", FIRST)]
    assert lobbies.lobby_of("Tiago") is None


def test_after_leaving_a_player_can_create_or_join_again():
    lobbies = lobby_with("Mara", "Tiago")
    lobbies.leave("Tiago")
    assert lobbies.join("Tiago", "ABCD")[1] is None
    lobbies.leave("Tiago")
    lobby, rejection_code = lobbies.create("Tiago", codes("WXYZ"))
    assert rejection_code is None
    assert lobby.host == "Tiago"


# The host leaves


def test_when_the_host_leaves_the_player_who_is_here_longest_becomes_host():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    lobby, new_host, rejection_code = lobbies.leave("Mara")
    assert rejection_code is None
    assert new_host == "Tiago"
    assert lobby.host == "Tiago"
    assert lobby.names() == ["Tiago", "Ines"]


def test_the_host_is_handed_on_in_joining_order_each_time():
    lobbies = lobby_with("Mara", "Tiago", "Ines", "Joao")
    lobbies.leave("Tiago")  # Not the host: Ines is now the longest after Mara.
    assert lobbies.leave("Mara")[1] == "Ines"
    assert lobbies.leave("Ines")[1] == "Joao"


def test_a_player_who_comes_back_is_at_the_end_of_the_line():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    lobbies.leave("Tiago")
    lobbies.join("Tiago", "ABCD")
    assert lobbies.leave("Mara")[1] == "Ines"


# Codes


def test_a_code_that_is_in_use_is_picked_again():
    lobbies = lobby_with("Mara", code="ABCD")
    lobby, rejection_code = lobbies.create("Tiago", codes("ABCD", "ABCD", "WXYZ"))
    assert rejection_code is None
    assert lobby.code == "WXYZ"
    assert lobbies.find("ABCD").names() == ["Mara"]


def test_an_empty_lobby_is_deleted_and_its_code_is_free_again():
    lobbies = lobby_with("Mara", "Tiago")
    lobbies.leave("Mara")
    lobby, new_host, rejection_code = lobbies.leave("Tiago")
    assert rejection_code is None
    assert new_host is None  # Nobody is left to be host.
    assert lobbies.find("ABCD") is None
    assert lobbies.join("Ines", "ABCD") == (None, "no_lobby")
    # The same code can be given to a new lobby.
    assert lobbies.create("Ines", codes("ABCD"))[0].players() == [("Ines", FIRST)]


def test_a_lobby_holds_exactly_one_player_per_character():
    assert MAX_PLAYERS == len(protocol.CHARACTERS) == 8


def test_count_says_how_many_lobbies_there_are():
    lobbies = Lobbies()
    assert lobbies.count() == 0
    lobbies.create("Mara", codes("AAAA"))
    lobbies.create("Tiago", codes("BBBB"))
    lobbies.join("Ines", "BBBB")
    assert lobbies.count() == 2
    lobbies.leave("Mara")
    assert lobbies.count() == 1


def test_two_lobbies_are_separate():
    lobbies = Lobbies()
    lobbies.create("Mara", codes("AAAA"))
    lobbies.create("Tiago", codes("BBBB"))
    lobbies.join("Ines", "BBBB")
    assert lobbies.find("AAAA").players() == [("Mara", FIRST)]
    assert lobbies.find("BBBB").players() == [("Tiago", FIRST), ("Ines", SECOND)]


# The first free character


def test_a_joiner_gets_the_first_character_nobody_has():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    assert lobbies.find("ABCD").players() == [("Mara", FIRST), ("Tiago", SECOND), ("Ines", THIRD)]


def test_a_joiner_gets_an_earlier_character_after_its_player_left():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    lobbies.leave("Mara")  # The first character is free again.
    lobby, rejection_code = lobbies.join("Joao", "ABCD")
    assert lobby.players() == [("Tiago", SECOND), ("Ines", THIRD), ("Joao", FIRST)]


def test_a_joiner_skips_a_character_someone_chose():
    lobbies = lobby_with("Mara")
    lobbies.choose_character("Mara", SECOND)
    lobbies.join("Tiago", "ABCD")
    lobbies.join("Ines", "ABCD")
    assert lobbies.find("ABCD").players() == [("Mara", SECOND), ("Tiago", FIRST), ("Ines", THIRD)]


# Rejected


def test_create_while_in_a_lobby_is_rejected():
    lobbies = lobby_with("Mara")
    assert lobbies.create("Mara", codes("WXYZ")) == (None, "already_in_lobby")
    assert lobbies.find("WXYZ") is None
    assert lobbies.lobby_of("Mara").code == "ABCD"


def test_join_while_in_a_lobby_is_rejected():
    lobbies = lobby_with("Mara")
    lobbies.create("Tiago", codes("WXYZ"))
    assert lobbies.join("Tiago", "ABCD") == (None, "already_in_lobby")
    # Also for the lobby the player is already in.
    assert lobbies.join("Mara", "ABCD") == (None, "already_in_lobby")
    assert lobbies.find("ABCD").names() == ["Mara"]


def test_join_with_an_unknown_code_is_rejected():
    lobbies = lobby_with("Mara")
    assert lobbies.join("Tiago", "WXYZ") == (None, "no_lobby")
    assert lobbies.lobby_of("Tiago") is None


def test_a_ninth_player_is_rejected():
    lobbies = full_lobby()
    assert lobbies.join("Mara", "ABCD") == (None, "lobby_full")
    assert len(lobbies.find("ABCD").names()) == 8
    assert lobbies.lobby_of("Mara") is None


def test_a_full_lobby_has_room_again_after_someone_left():
    lobbies = full_lobby()
    lobbies.leave("Player3")
    lobby, rejection_code = lobbies.join("Mara", "ABCD")
    assert rejection_code is None
    assert lobby.character_of("Mara") == protocol.CHARACTERS[3]


def test_choosing_a_character_of_another_player_is_rejected():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.choose_character("Tiago", FIRST) == (None, False, "character_taken")
    assert lobbies.find("ABCD").players() == [("Mara", FIRST), ("Tiago", SECOND)]


def test_the_same_character_can_be_used_in_two_lobbies():
    lobbies = Lobbies()
    lobbies.create("Mara", codes("AAAA"))
    lobbies.create("Tiago", codes("BBBB"))
    assert lobbies.choose_character("Tiago", FIRST)[2] is None


def test_choose_character_outside_a_lobby_is_rejected():
    assert Lobbies().choose_character("Mara", FIRST) == (None, False, "not_in_lobby")


def test_leave_outside_a_lobby_is_rejected():
    lobbies = lobby_with("Mara")
    assert lobbies.leave("Tiago") == (None, None, "not_in_lobby")
    assert lobbies.find("ABCD").names() == ["Mara"]


def test_leaving_twice_is_rejected_the_second_time():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.leave("Tiago")[2] is None
    assert lobbies.leave("Tiago") == (None, None, "not_in_lobby")


@pytest.mark.parametrize("code", ["already_in_lobby", "no_lobby", "lobby_full", "character_taken", "not_in_lobby"])
def test_every_rejection_code_has_a_text(code):
    assert protocol.rejection(code)["message"]


# The small addition to Sessions that the lobby needs: finding a player's connection.


def test_sessions_finds_the_connection_of_a_name():
    sessions = Sessions()
    sessions.sign_in_account("a", "Mara")
    sessions.sign_in_guest("b", lambda: 7)
    assert sessions.connection_of("Mara") == "a"
    assert sessions.connection_of("Guest0007") == "b"
    assert sessions.connection_of("Tiago") is None
    sessions.sign_out("a")
    assert sessions.connection_of("Mara") is None


# Choosing the mode and starting the round (M2-2.1, S-91)


def started_lobby(*names):
    """Lobbies with one lobby whose round is running. The first name is the host."""
    lobbies = lobby_with(*names)
    assert lobbies.start(names[0])[1] is None
    return lobbies


def test_a_new_lobby_has_mode_duel_and_phase_lobby():
    lobby = lobby_with("Mara").find("ABCD")
    assert lobby.mode == "duel"
    assert lobby.phase == "lobby"
    assert not lobby.round_is_running()


def test_the_host_chooses_the_mode():
    lobbies = lobby_with("Mara", "Tiago")
    lobby, rejection_code = lobbies.choose_mode("Mara", "duel")
    assert rejection_code is None
    assert lobby is lobbies.find("ABCD")
    assert lobby.mode == "duel"


def test_choose_mode_sets_the_mode_it_is_given():
    # Only "duel" passes the message check today. The rule itself stores
    # what it is given, so Classic needs no new code here later.
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "classic")
    assert lobbies.find("ABCD").mode == "classic"


def test_choose_mode_outside_a_lobby_is_rejected():
    lobbies = lobby_with("Mara")
    assert lobbies.choose_mode("Tiago", "duel") == (None, "not_in_lobby")


def test_choose_mode_by_a_member_who_is_not_host_is_rejected():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.choose_mode("Tiago", "classic") == (None, "not_host")
    assert lobbies.find("ABCD").mode == "duel"


def test_choose_mode_during_a_round_is_rejected():
    lobbies = started_lobby("Mara", "Tiago")
    assert lobbies.choose_mode("Mara", "classic") == (None, "round_running")
    assert lobbies.find("ABCD").mode == "duel"


@pytest.mark.parametrize("number_of_players", range(2, MAX_PLAYERS + 1))
def test_the_host_starts_duel_with_two_to_eight_players(number_of_players):
    names = [f"Player{number}" for number in range(number_of_players)]
    lobbies = lobby_with(*names)
    lobby, rejection_code = lobbies.start("Player0")
    assert rejection_code is None
    assert lobby.phase == "round"
    assert lobby.round_is_running()
    assert lobby.names() == names


def test_start_outside_a_lobby_is_rejected():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.start("Ines") == (None, "not_in_lobby")
    assert lobbies.find("ABCD").phase == "lobby"


def test_start_by_a_member_who_is_not_host_is_rejected():
    lobbies = lobby_with("Mara", "Tiago")
    assert lobbies.start("Tiago") == (None, "not_host")
    assert lobbies.find("ABCD").phase == "lobby"


def test_start_with_one_player_is_rejected():
    lobbies = lobby_with("Mara")
    assert lobbies.start("Mara") == (None, "too_few_players")
    assert lobbies.find("ABCD").phase == "lobby"


def test_the_minimum_depends_on_the_mode():
    lobbies = lobby_with("Mara", "Tiago", "Ines")
    lobbies.choose_mode("Mara", "classic")  # Needs 4 (S-53).
    assert lobbies.start("Mara") == (None, "too_few_players")
    lobbies.join("Rui", "ABCD")
    assert lobbies.start("Mara")[1] is None


def test_a_second_start_is_rejected():
    lobbies = started_lobby("Mara", "Tiago")
    assert lobbies.start("Mara") == (None, "round_running")
    assert lobbies.find("ABCD").phase == "round"


def test_not_host_is_checked_before_round_running_and_too_few_players():
    assert started_lobby("Mara", "Tiago").start("Tiago") == (None, "not_host")
    assert started_lobby("Mara", "Tiago").choose_mode("Tiago", "duel") == (None, "not_host")


def test_round_running_is_checked_before_too_few_players():
    lobbies = started_lobby("Mara", "Tiago")
    lobbies.leave("Tiago")  # One player is left in the running round.
    assert lobbies.start("Mara") == (None, "round_running")


def test_joining_a_running_round_is_rejected():
    lobbies = started_lobby("Mara", "Tiago")
    assert lobbies.join("Ines", "ABCD") == (None, "round_running")
    assert lobbies.find("ABCD").names() == ["Mara", "Tiago"]
    assert lobbies.lobby_of("Ines") is None


def test_a_full_running_round_says_round_running_not_lobby_full():
    lobbies = full_lobby()
    lobbies.start("Player0")
    assert lobbies.join("Mara", "ABCD") == (None, "round_running")


def test_a_player_in_another_lobby_is_told_to_leave_first_even_if_the_round_runs():
    lobbies = started_lobby("Mara", "Tiago")
    lobbies.create("Ines", codes("WXYZ"))
    assert lobbies.join("Ines", "ABCD") == (None, "already_in_lobby")


def test_choosing_a_character_during_a_round_is_rejected():
    lobbies = started_lobby("Mara", "Tiago")
    assert lobbies.choose_character("Tiago", "surfer") == (None, False, "round_running")
    assert lobbies.find("ABCD").character_of("Tiago") == SECOND


def test_a_taken_character_during_a_round_says_round_running():
    lobbies = started_lobby("Mara", "Tiago")
    assert lobbies.choose_character("Tiago", FIRST) == (None, False, "round_running")


def test_a_member_leaves_a_running_round_and_the_others_stay_in_it():
    lobbies = started_lobby("Mara", "Tiago", "Ines")
    lobby, new_host, rejection_code = lobbies.leave("Tiago")
    assert (new_host, rejection_code) == (None, None)
    assert lobby.names() == ["Mara", "Ines"]
    assert lobby.phase == "round"


def test_the_host_leaves_a_running_round_and_the_next_player_is_host():
    lobbies = started_lobby("Mara", "Tiago", "Ines")
    lobby, new_host, rejection_code = lobbies.leave("Mara")
    assert new_host == "Tiago"
    assert lobby.host == "Tiago"
    assert lobby.phase == "round"
    # The new host cannot start the running round again either.
    assert lobbies.start("Tiago") == (None, "round_running")


def test_a_running_round_that_everybody_left_is_deleted():
    lobbies = started_lobby("Mara", "Tiago")
    lobbies.leave("Mara")
    lobbies.leave("Tiago")
    assert lobbies.find("ABCD") is None
    # The code can be given out again, and the new lobby starts fresh.
    lobby, rejection_code = lobbies.create("Mara", codes("ABCD"))
    assert lobby.phase == "lobby"


@pytest.mark.parametrize("code", ["not_host", "round_running"])
def test_the_new_rejection_codes_have_a_text(code):
    assert protocol.rejection(code)["message"]
