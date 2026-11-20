"""Play test of the character selection with three guests (M1-1.8).

What the tester played with three browsers, as far as the server and the
page's files take part in it and `test_server_lobby.py`, `test_lobbies.py`,
`test_protocol.py` and `test_character_list.py` do not already check:

- the page loads its one character list (world/characters.js) before the
  lobby panel that builds its buttons from it; in the other order the lobby
  would show no characters at all, without an error;
- two guests choose, a third joins later: all three get the same state, in
  which the third has the first free character and sees the others' choices;
- one player chooses twice quickly: both choices are answered in order, the
  others hear both, the last one counts;
- two players ask for the same free character at the same moment: exactly
  one gets it, the other is told "That character is taken." and nothing else;
- a player leaves: the character becomes free, another player can take it,
  and on rejoining the player gets the first free character.

What only the page does (greyed-out cards, the message at the top) was
checked in the browser and cannot be checked here.
"""

import re
from pathlib import Path

from server import protocol
from test_server_lobby import ask, client, connect, create, join, leave, still_works  # noqa: F401

INDEX_HTML = Path(__file__).resolve().parent.parent / "client" / "index.html"
CONSULTANT, FINANCE_BRO, EXCHANGE_STUDENT, SURFER, FOUNDER, OVERACHIEVER, LATECOMER, LIBRARY_LOCAL = (
    protocol.CHARACTERS
)
CHARACTER_TAKEN = {"type": "error", "code": "character_taken", "message": "That character is taken."}


def a_guest(connect):
    """A new connection that entered as a guest. Returns it and the guest's name."""
    connection = connect()
    answer = ask(connection, {"type": "guest"})
    assert answer["type"] == "signed_in"
    return connection, answer["name"]


def choose_message(character):
    return {"type": "choose_character", "character": character}


def three_guests_in_a_lobby(connect):
    """The first guest creates a lobby, the other two join. Every copy of the state is read."""
    first, first_name = a_guest(connect)
    second, second_name = a_guest(connect)
    third, third_name = a_guest(connect)
    code = create(first)["code"]
    join(second, code)
    first.receive_json()
    join(third, code)
    first.receive_json()
    second.receive_json()
    return [first, second, third], [first_name, second_name, third_name], code


def state(code, host, *players):
    return protocol.lobby_state(code, host, players)


# The page


def test_the_page_loads_the_character_list_before_the_lobby_panel():
    scripts = re.findall(r'<script src="([^"]+)"', INDEX_HTML.read_text())
    assert "js/world/characters.js" in scripts
    assert "js/lobby/lobby.js" in scripts
    assert scripts.index("js/world/characters.js") < scripts.index("js/lobby/lobby.js")


# Three guests


def test_a_third_guest_who_joins_later_sees_the_choices_of_the_others(connect):
    first, first_name = a_guest(connect)
    second, second_name = a_guest(connect)
    third, third_name = a_guest(connect)
    code = create(first)["code"]
    assert ask(first, choose_message(SURFER)) == state(code, first_name, (first_name, SURFER))
    join(second, code)
    first.receive_json()
    ask(second, choose_message(FOUNDER))
    first.receive_json()

    # The Consultant is free again, so the third guest gets it, not the
    # character after the others' ones.
    expected = state(code, first_name, (first_name, SURFER), (second_name, FOUNDER), (third_name, CONSULTANT))
    assert join(third, code) == expected
    assert first.receive_json() == expected
    assert second.receive_json() == expected


def test_the_third_guest_cannot_take_a_character_chosen_before_they_came(connect):
    (first, second, third), names, code = three_guests_in_a_lobby(connect)
    ask(first, choose_message(SURFER))
    second.receive_json()
    third.receive_json()

    assert ask(third, choose_message(SURFER)) == CHARACTER_TAKEN
    assert ask(third, choose_message(FINANCE_BRO)) == CHARACTER_TAKEN  # the second guest's
    # Nobody else was told anything, and nothing changed.
    assert still_works(first)
    assert still_works(second)
    expected = state(code, names[0], (names[0], SURFER), (names[1], FINANCE_BRO), (names[2], LATECOMER))
    assert ask(third, choose_message(LATECOMER)) == expected


# Quickly, twice


def test_two_quick_choices_are_both_answered_and_the_last_one_counts(connect):
    (first, second, third), names, code = three_guests_in_a_lobby(connect)
    third.send_json(choose_message(OVERACHIEVER))
    third.send_json(choose_message(LIBRARY_LOCAL))

    after_first_choice = state(code, names[0], (names[0], CONSULTANT), (names[1], FINANCE_BRO), (names[2], OVERACHIEVER))
    after_second_choice = state(code, names[0], (names[0], CONSULTANT), (names[1], FINANCE_BRO), (names[2], LIBRARY_LOCAL))
    for connection in (first, second, third):
        assert connection.receive_json() == after_first_choice
        assert connection.receive_json() == after_second_choice
    # The Overachiever was given up again, so another guest may take it.
    expected = state(code, names[0], (names[0], OVERACHIEVER), (names[1], FINANCE_BRO), (names[2], LIBRARY_LOCAL))
    assert ask(first, choose_message(OVERACHIEVER)) == expected


def test_two_guests_who_ask_for_the_same_character_at_once_cannot_both_get_it(connect):
    (first, second, third), names, code = three_guests_in_a_lobby(connect)
    second.send_json(choose_message(LATECOMER))
    third.send_json(choose_message(LATECOMER))

    # One of them asked first. Whoever it was, the first guest hears exactly
    # one change, and the other one is refused.
    final = first.receive_json()
    holders = [player["name"] for player in final["players"] if player["character"] == LATECOMER]
    assert len(holders) == 1
    winner, loser = (second, third) if holders == [names[1]] else (third, second)
    assert winner.receive_json() == final
    answers_of_the_loser = [loser.receive_json(), loser.receive_json()]
    assert CHARACTER_TAKEN in answers_of_the_loser
    assert final in answers_of_the_loser  # The loser was told about the winner's choice too.
    for connection in (first, second, third):
        assert still_works(connection)


# Leaving and coming back


def test_a_character_given_up_by_leaving_can_be_taken_and_the_rejoiner_gets_a_free_one(connect):
    (first, second, third), names, code = three_guests_in_a_lobby(connect)
    ask(third, choose_message(SURFER))
    first.receive_json()
    second.receive_json()

    assert leave(third) == {"type": "left_lobby"}
    first.receive_json()
    second.receive_json()

    after_taking = state(code, names[0], (names[0], CONSULTANT), (names[1], SURFER))
    assert ask(second, choose_message(SURFER)) == after_taking
    assert first.receive_json() == after_taking

    # The Finance Bro is free now and comes before every other free character.
    back = state(code, names[0], (names[0], CONSULTANT), (names[1], SURFER), (names[2], FINANCE_BRO))
    assert join(third, code) == back
    assert first.receive_json() == back
    assert second.receive_json() == back
    assert ask(third, choose_message(SURFER)) == CHARACTER_TAKEN
