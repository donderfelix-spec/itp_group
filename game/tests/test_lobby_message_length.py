"""The longest message of the lobby screen and the room the page keeps for it (M1-1.7).

In the play test of M1-1.7 the longest real message of the lobby screen was
"The host left. <name> is the new host." with a 16-letter name: the host left
a lobby of three, and the second player had a 16-letter account name. In
Chromium at 320px it is three lines high, also with the widest letters
("WWWWWWWWWWWWWWWM"). With the panel below the map the message stands at the
bottom of the window, and the panel keeps room below its buttons for a
message of three lines (style.css, "The message on the lobby screen").

These tests keep the two things the room was measured with:

- the server sends exactly this notice, to everybody left in the lobby;
- no other message the page can get in the lobby is longer. A longer one
  could be four lines at 320px and lie on "Leave lobby" at the end of the
  page. Then measure it in a browser and give the panel more room.

The number of letters stands in for the width, which only a browser can
measure: every one of these messages is ordinary text, and the 16 widest
letters were measured.
"""

import pytest

from server import protocol
from task_helpers import client, connect  # noqa: F401
from task_helpers import ask, player

LONGEST_NAME = "Abcdefghijklmnop"  # 16 letters, the longest name an account can have
LONGEST_NOTICE = f"The host left. {LONGEST_NAME} is the new host."

# Every refusal a player can get on the lobby screen by using the page: the
# panel's buttons, the character list, the stations and minigames, and an
# action that crosses the end of a round on the way.
LOBBY_REFUSALS = [
    "not_host",
    "round_running",
    "character_taken",
    "not_in_round",
    "not_in_lobby",
    "no_station",
    "too_far",
    "station_not_needed",
    "task_open",
    "no_task_open",
    "too_fast",
    "task_failed",
]


def lobby_of_three(connect):
    """Mara creates a lobby, then the player with the longest name joins, then Tiago.

    Returns the three connections after each has read every lobby state so far.
    """
    mara = player(connect, "Mara")
    longest = player(connect, LONGEST_NAME)
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    ask(longest, {"type": "join_lobby", "code": code})
    mara.receive_json()
    ask(tiago, {"type": "join_lobby", "code": code})
    mara.receive_json()
    longest.receive_json()
    return mara, longest, tiago


def test_the_longest_name_is_a_name_an_account_can_have():
    assert len(LONGEST_NAME) == 16
    assert protocol.parse_client_message('{"type": "sign_up", "name": "%s", "password": "password123"}' % LONGEST_NAME)


def test_a_name_one_letter_longer_is_refused():
    # Edge case: the notice can never name a longer player.
    longer = LONGEST_NAME + "q"
    with pytest.raises(protocol.ProtocolError) as refusal:
        protocol.parse_client_message('{"type": "sign_up", "name": "%s", "password": "password123"}' % longer)
    assert refusal.value.message == "Usernames are 3–16 letters or numbers."


def test_when_the_host_leaves_both_others_read_the_notice_with_the_longest_name(connect):
    mara, longest, tiago = lobby_of_three(connect)
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    for connection in (longest, tiago):
        assert connection.receive_json() == protocol.notice(LONGEST_NOTICE)
        state = connection.receive_json()
        assert state["type"] == "lobby_state"
        assert state["host"] == LONGEST_NAME


def test_the_notice_with_the_longest_name_has_48_characters():
    # The page's room for a message was measured with this text.
    assert len(LONGEST_NOTICE) == 48


def test_no_refusal_on_the_lobby_screen_is_longer_than_the_notice():
    for code in LOBBY_REFUSALS:
        text = protocol.REJECTIONS[code]
        assert len(text) <= len(LONGEST_NOTICE), f"{code}: {text!r} may need a fourth line at 320px"


def test_no_too_few_players_message_is_longer_than_the_notice():
    # "Duel needs at least 2 players." and "Classic needs at least 4 players."
    for mode in protocol.MIN_PLAYERS:
        text = protocol.too_few_players(mode)["message"]
        assert len(text) <= len(LONGEST_NOTICE), f"{text!r} may need a fourth line at 320px"
