"""Edge cases of coming back into the lobby after a lost connection (M3-2.2, S-109).

Found by the tester while playing the change in a real browser, with each
player's connection cut at the network level. test_play_reconnect.py holds
the main cases; this file adds what that one does not cover:

- A guest whose old connection the server has not noticed yet (about 40 s
  in the browser) still holds a place. In a full lobby the new connection is
  refused with "This lobby is full.", at the code field and with the code in
  it, and can join by hand once the server has noticed.
- Clicking "Play as guest" twice quickly after the connection is back sends
  one `guest` and one automatic join.
- After the automatic join was refused, a double click on Join sends one
  `join_lobby` only.
"""

from server import protocol
from task_helpers import client, connect  # noqa: F401
from task_helpers import ask
from test_play_reconnect import CODE, REJOIN, guest_signs_in, in_the_lobby, joins, names_in, needs_node, run_page
from test_play_reconnect import wait_until_gone
from test_server_duel import lobby_of, news

LOBBY_FULL = protocol.rejection("lobby_full")
ROUND_RUNNING = protocol.rejection("round_running")
EIGHT_NAMES = ["Mara", "Tiago", "Ines", "Rui", "Joana", "Pedro", "Sofia"]  # seven accounts and one guest


# The server's part


def test_a_guest_back_before_the_server_noticed_the_old_connection_is_refused_by_a_full_lobby(connect):
    players, code = lobby_of(connect, EIGHT_NAMES)
    old_guest = connect()
    old_name = ask(old_guest, {"type": "guest"})["name"]
    assert len(names_in(ask(old_guest, {"type": "join_lobby", "code": code}))) == 8
    news(players["Mara"])
    # The old connection is not closed: the server still counts the old guest.
    back = connect()
    assert ask(back, {"type": "guest"})["type"] == "signed_in"
    assert ask(back, {"type": "join_lobby", "code": code}) == LOBBY_FULL
    assert LOBBY_FULL["message"] == "This lobby is full."
    # Once the server notices that the old connection is gone, Join works.
    old_guest.close()
    wait_until_gone(players["Mara"], old_name)
    answer = ask(back, {"type": "join_lobby", "code": code})
    assert answer["type"] == "lobby_state" and len(names_in(answer)) == 8


# The page's part


@needs_node
def test_a_full_lobby_is_told_at_the_code_field_with_the_code_in_it():
    page = run_page(*in_the_lobby(), ["lose"], *guest_signs_in("Guest 5678"), ["receive", LOBBY_FULL])
    assert page["screen"] == "home"
    assert page["codeError"] == "This lobby is full."
    assert page["joinCode"] == CODE
    assert joins(page) == [REJOIN]


@needs_node
def test_a_double_click_on_play_as_guest_after_a_lost_connection_sends_one_guest_and_one_join():
    steps = [*in_the_lobby(), ["lose"], ["open"], ["click", "start-guest"], ["click", "start-guest"]]
    page = run_page(*steps, ["receive", protocol.signed_in("Guest 5678", True)])
    sent_after_loss = page["sent"][page["sent"].index({"type": "create_lobby"}) + 1 :]
    assert sent_after_loss == [{"type": "guest"}, REJOIN]


@needs_node
def test_a_double_click_on_join_after_the_refusal_sends_one_join():
    refused = [["receive", ROUND_RUNNING]]
    page = run_page(*in_the_lobby("round"), ["lose"], *guest_signs_in("Guest 5678"), *refused,
                    ["submit", "join-form"], ["submit", "join-form"])
    assert joins(page) == [REJOIN, REJOIN]
