"""Play test of the character list in the lobby (M2-2.8, S-110).

What the tester played with two to eight guests in Chromium, at 1280x800,
900x700 and 390x844: the host chooses every free character in turn, the
other player changes theirs, both click the same character in the same
moment, eight players fill the lobby and one of them leaves. In every state
all eight buttons were equally high and kept their place (measured with
getBoundingClientRect, see the tester's report).

The sizes themselves cannot be measured without a browser, and this project
has no browser in its tests. What is checked here is the part the server
takes in it: every one of these clicks gets the answer the page draws from,
and a click on a taken character gets the text of DESIGN.md, section 9.
The stylesheet rules that keep the sizes are guarded in
test_client_character_buttons.py; the row gap of S-110 is guarded here.
"""

import re

from fastapi.testclient import TestClient

from server import protocol
from server.main import app
from test_server_lobby import ask, client, connect, still_works  # noqa: F401

CHARACTER_TAKEN = protocol.rejection("character_taken")


# Helpers


def guest(connect):
    """A new connection that pressed "Play as guest". Returns it and the guest's name."""
    connection = connect()
    answer = ask(connection, {"type": "guest"})
    assert answer["type"] == "signed_in"
    return connection, answer["name"]


def characters_in(state):
    return {listed["name"]: listed["character"] for listed in state["players"]}


def lobby_of_guests(connect, count):
    """The first guest creates a lobby, the others join by its code.

    Returns the connections and names in the order they came, and the code.
    Every message of the joins is read away.
    """
    host, host_name = guest(connect)
    code = ask(host, {"type": "create_lobby"})["code"]
    connections, names = [host], [host_name]
    for _ in range(count - 1):
        joiner, name = guest(connect)
        assert ask(joiner, {"type": "join_lobby", "code": code})["type"] == "lobby_state"
        for earlier in connections:
            assert earlier.receive_json()["type"] == "lobby_state"
        connections.append(joiner)
        names.append(name)
    return connections, names, code


def choose(connection, character):
    return ask(connection, {"type": "choose_character", "character": character})


# Two guests


def test_the_host_chooses_every_free_character_in_turn_and_both_see_each_choice(connect):
    (host, other), (host_name, other_name), _ = lobby_of_guests(connect, 2)
    # The host starts with the first character, the other guest has the second.
    others_character = protocol.CHARACTERS[1]
    free = [character for character in protocol.CHARACTERS if character != others_character]
    for character in free[1:] + free[:1]:
        answer = choose(host, character)
        assert characters_in(answer) == {host_name: character, other_name: others_character}
        assert other.receive_json() == answer
    assert still_works(other)


def test_the_other_player_changes_and_the_host_sees_the_button_taken(connect):
    (host, other), (host_name, other_name), _ = lobby_of_guests(connect, 2)
    for character in ["surfer", "founder", "library_local"]:
        answer = choose(other, character)
        assert characters_in(answer)[other_name] == character
        assert host.receive_json() == answer


def test_a_character_the_other_player_just_took_is_refused_with_the_text_of_section_9(connect):
    # In the page the button is switched off as soon as the state arrives; a
    # click sent before that, in the same moment as the other player's, gets
    # this answer from the server.
    (host, other), (host_name, other_name), _ = lobby_of_guests(connect, 2)
    taken = choose(other, "surfer")
    assert host.receive_json() == taken
    assert choose(host, "surfer") == CHARACTER_TAKEN
    assert characters_in(taken)[host_name] == protocol.CHARACTERS[0]
    # Nobody else hears of the refused click.
    assert still_works(other)
    assert still_works(host)


def test_a_character_just_left_by_the_other_player_can_be_taken_at_once(connect):
    (host, other), (host_name, other_name), _ = lobby_of_guests(connect, 2)
    left_behind = protocol.CHARACTERS[1]
    assert characters_in(choose(other, "founder"))[other_name] == "founder"
    host.receive_json()
    answer = choose(host, left_behind)
    assert characters_in(answer) == {host_name: left_behind, other_name: "founder"}
    assert other.receive_json() == answer


def test_many_clicks_in_a_row_end_with_the_last_choice_and_nothing_breaks(connect):
    # The page sends one click at a time (Game.net.ask); a script that does
    # not wait sends them all, and every one is still answered in order.
    (host, other), (host_name, other_name), _ = lobby_of_guests(connect, 2)
    clicks = ["surfer", "founder", "surfer", "surfer", protocol.CHARACTERS[1], "latecomer"]
    for character in clicks:
        host.send_json({"type": "choose_character", "character": character})
    answers = [host.receive_json() for _ in clicks]
    assert answers[4] == CHARACTER_TAKEN  # the other player's character
    assert characters_in(answers[-1])[host_name] == "latecomer"
    assert still_works(host)


# Eight guests


def test_eight_guests_get_eight_different_characters_and_a_leaver_frees_one(connect):
    connections, names, _ = lobby_of_guests(connect, 8)
    host = connections[0]
    # Every character is taken: whatever the host clicks is refused, except their own,
    # which is answered to the host alone.
    state = choose(host, protocol.CHARACTERS[0])
    assert sorted(characters_in(state).values()) == sorted(protocol.CHARACTERS)
    assert choose(host, protocol.CHARACTERS[7]) == CHARACTER_TAKEN
    # The eighth leaves: their character is free again for the host.
    freed = characters_in(state)[names[-1]]
    ask(connections[-1], {"type": "leave_lobby"})
    assert freed not in characters_in(host.receive_json()).values()
    assert characters_in(choose(host, freed))[names[0]] == freed


# The row gap of S-110


def test_the_rows_of_the_character_list_are_4px_apart():
    with TestClient(app) as browser:
        stylesheet = browser.get("/css/style.css").text
    found = re.search(r"^\.characters \{(.*?)\}", stylesheet, re.MULTILINE | re.DOTALL)
    assert found, "The stylesheet has no rule for .characters"
    # `gap: <rows> <columns>`: 4px between the rows, 6px between the columns.
    assert re.search(r"^\s*gap: 4px 6px;", found.group(1), re.MULTILINE)
