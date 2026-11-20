"""Play test of coming back into the lobby after a lost connection (M3-2.2, S-109).

S-109: the page remembers the code of the lobby it was in when the
connection was lost. After the player signs in again on the new connection,
the page sends one `join_lobby` with that code by itself and puts the code
into the join field. The server answers as it answers a click on Join.

There are two parts, because the page decides when to join and the server
decides what happens then:

- The server's part, with the FastAPI test client (S-72): what a player who
  signs in again on a new connection and sends the remembered code gets, and
  what the others in the lobby see.
- The page's part: the page's real net.js, forms.js and main.js run in Node
  (tests/page_in_node.js) with a stand-in for the WebSocket and the
  document. The test plays the server's side with the server's own messages
  from `protocol.py`. Playwright is not used (S-72). Without Node these
  tests are skipped; CI has Node.

How it looks in a real browser is tried by the tester.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server import protocol
from server.main import app
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import PASSWORD, ask, player
from test_server_duel import lobby_of, news, wait_for_news

CODE = "ABCD"
NO_LOBBY = protocol.rejection("no_lobby")
ROUND_RUNNING = protocol.rejection("round_running")
LEFT = {"type": "left_lobby"}


def names_in(lobby_state):
    return [listed["name"] for listed in lobby_state["players"]]


def log_in_again(connect, name):
    """What the page does after a lost connection: a new connection, and the player logs in."""
    connection = connect()
    assert ask(connection, {"type": "log_in", "name": name, "password": PASSWORD}) == protocol.signed_in(name, False)
    return connection


def wait_until_gone(connection, name):
    """Read the lobby's states until this name is no longer in the list. Returns the last state."""
    told = wait_for_news(connection, "lobby_state")
    while name in names_in(told[-1]):
        told = wait_for_news(connection, "lobby_state")
    return told[-1]


# The server's part: what the one automatic `join_lobby` gets


def test_a_player_who_lost_the_connection_in_the_lobby_gets_back_in_and_the_others_see_it(connect):
    players, code = lobby_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    tiago.close()
    for connection in (mara, ines):
        assert names_in(wait_until_gone(connection, "Tiago")) == ["Mara", "Ines"]
    back = log_in_again(connect, "Tiago")
    answer = ask(back, {"type": "join_lobby", "code": code})
    assert answer["type"] == "lobby_state" and answer["code"] == code and answer["phase"] == "lobby"
    assert names_in(answer) == ["Mara", "Ines", "Tiago"]
    assert news(mara) == [answer] and news(ines) == [answer]


def test_the_account_gets_back_in_even_before_the_server_noticed_that_the_old_connection_is_gone(connect):
    # The old connection is not closed: the server still thinks it is there.
    # Logging in again signs it out (S-76) and takes it out of the lobby.
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    mara, old_tiago = players["Mara"], players["Tiago"]
    back = log_in_again(connect, "Tiago")
    assert names_in(wait_until_gone(mara, "Tiago")) == ["Mara"]
    answer = ask(back, {"type": "join_lobby", "code": code})
    assert names_in(answer) == ["Mara", "Tiago"]
    assert news(mara) == [answer]
    assert news(old_tiago) == [protocol.signed_out()]


def test_a_guest_comes_back_under_a_new_name_and_the_others_see_it(connect):
    mara = player(connect, "Mara")
    code = ask(mara, {"type": "create_lobby"})["code"]
    guest = connect()
    old_name = ask(guest, {"type": "guest"})["name"]
    assert names_in(ask(guest, {"type": "join_lobby", "code": code})) == ["Mara", old_name]
    news(mara)
    guest.close()
    wait_until_gone(mara, old_name)
    back = connect()
    signed_in = ask(back, {"type": "guest"})
    assert signed_in["type"] == "signed_in" and signed_in["guest"] is True
    answer = ask(back, {"type": "join_lobby", "code": code})
    assert names_in(answer) == ["Mara", signed_in["name"]]
    assert news(mara) == [answer]


def test_during_the_countdown_the_player_is_refused_with_this_round_has_already_started(connect, clock):
    players, code = lobby_of(connect, ["Mara", "Tiago", "Ines"])
    players["Ines"].close()
    wait_until_gone(players["Mara"], "Ines")
    # The countdown is started with the rules' own function; the tick that
    # would end it is switched off in the tests, so it is still running.
    lobby, rejection_code = app.state.lobbies.start("Mara", clock.now)
    assert rejection_code is None and lobby.phase == "countdown"
    back = log_in_again(connect, "Ines")
    assert ask(back, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert ROUND_RUNNING["message"] == "This round has already started."


def test_during_the_round_the_player_is_refused_with_this_round_has_already_started(connect):
    players, code = lobby_of(connect, ["Mara", "Tiago", "Ines"])
    players["Ines"].close()
    wait_until_gone(players["Mara"], "Ines")
    assert ask(players["Mara"], {"type": "start_game"})["phase"] == "round"
    back = log_in_again(connect, "Ines")
    assert ask(back, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    # Joining after the end of the round: test_play_leave_round.py, the last player's comeback.


def test_a_lobby_whose_last_member_was_lost_is_gone(connect):
    mara = player(connect, "Mara")
    code = ask(mara, {"type": "create_lobby"})["code"]
    mara.close()
    back = log_in_again(connect, "Mara")
    assert ask(back, {"type": "join_lobby", "code": code}) == NO_LOBBY
    assert NO_LOBBY["message"] == "No lobby with that code."


# The page's part: when the page sends the automatic `join_lobby`

NODE = shutil.which("node")
PAGE_IN_NODE = Path(__file__).resolve().parent / "page_in_node.js"
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")


def run_page(*steps):
    """Run the page in Node through these steps. Returns what it sent and shows (see page_in_node.js)."""
    finished = subprocess.run(
        [NODE, str(PAGE_IN_NODE)], input=json.dumps(steps), capture_output=True, text=True, timeout=30
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def joins(page):
    return [message for message in page["sent"] if message["type"] == "join_lobby"]


# Each way of signing in starts with the new connection opening.


def guest_signs_in(name="Guest 1234"):
    return [["open"], ["click", "start-guest"], ["receive", protocol.signed_in(name, True)]]


def logs_in(name="Tiago"):
    return [
        ["open"],
        ["type", "login-name", name],
        ["type", "login-password", PASSWORD],
        ["submit", "login-form"],
        ["receive", protocol.signed_in(name, False)],
    ]


def in_the_lobby(phase="lobby", name="Guest 1234"):
    """Signed in as a guest, the player creates a lobby and is in it, in this phase."""
    state = protocol.lobby_state(CODE, name, [(name, "finance_bro")], "duel", phase)
    return guest_signs_in(name) + [["click", "home-create"], ["receive", state]]


REJOIN = {"type": "join_lobby", "code": CODE}


@needs_node
@pytest.mark.parametrize("signs_in_again", [guest_signs_in("Guest 5678"), logs_in("Tiago")], ids=["guest", "account"])
def test_after_a_lost_connection_the_page_joins_the_lobby_by_itself_once_signed_in_again(signs_in_again):
    page = run_page(*in_the_lobby(), ["lose"], *signs_in_again)
    assert page["sent"][-1] == REJOIN
    assert joins(page) == [REJOIN]
    assert page["joinCode"] == CODE


@needs_node
def test_nothing_is_joined_before_the_player_signs_in_again():
    page = run_page(*in_the_lobby(), ["lose"], ["open"])
    assert joins(page) == [] and page["screen"] == "start"


@needs_node
def test_the_servers_lobby_state_takes_the_player_into_the_lobby():
    back = protocol.lobby_state(CODE, "Mara", [("Mara", "finance_bro"), ("Guest 5678", "surfer")])
    page = run_page(*in_the_lobby(), ["lose"], *guest_signs_in("Guest 5678"), ["receive", back])
    assert joins(page) == [REJOIN] and page["screen"] == "lobby"


@needs_node
@pytest.mark.parametrize("phase", ["countdown", "round"])
def test_a_running_round_is_told_at_the_code_field_and_join_later_uses_the_code_in_the_field(phase):
    refused = run_page(*in_the_lobby(phase), ["lose"], *logs_in(), ["receive", ROUND_RUNNING])
    assert refused["screen"] == "home"
    assert refused["codeError"] == "This round has already started."
    assert refused["joinCode"] == CODE
    assert joins(refused) == [REJOIN]
    # After the round the player presses Join: the code is still in the field.
    later = run_page(*in_the_lobby(phase), ["lose"], *logs_in(), ["receive", ROUND_RUNNING], ["submit", "join-form"])
    assert joins(later) == [REJOIN, REJOIN]


@needs_node
def test_a_lobby_that_is_gone_is_told_at_the_code_field():
    page = run_page(*in_the_lobby(), ["lose"], *guest_signs_in("Guest 5678"), ["receive", NO_LOBBY])
    assert page["screen"] == "home"
    assert page["codeError"] == "No lobby with that code."
    assert page["joinCode"] == CODE


@needs_node
def test_a_double_click_on_join_while_the_automatic_join_waits_sends_nothing_more():
    page = run_page(*in_the_lobby(), ["lose"], *guest_signs_in("Guest 5678"), ["submit", "join-form"])
    assert joins(page) == [REJOIN]


# The page forgets the code


@needs_node
def test_leaving_with_the_button_forgets_the_lobby():
    page = run_page(*in_the_lobby(), ["receive", LEFT], ["lose"], *guest_signs_in("Guest 5678"))
    assert joins(page) == [] and page["joinCode"] == ""


@needs_node
def test_logging_out_forgets_the_lobby():
    steps = [*in_the_lobby(), ["receive", LEFT], ["click", "home-logout"], ["receive", protocol.signed_out()]]
    page = run_page(*steps, ["lose"], *logs_in())
    assert {"type": "log_out"} in page["sent"]
    assert joins(page) == [] and page["joinCode"] == ""


@needs_node
def test_being_signed_in_somewhere_else_forgets_the_lobby():
    steps = [*in_the_lobby(), ["receive", protocol.signed_out()]]
    told = run_page(*steps)
    assert told["message"] == "You were signed in somewhere else."
    page = run_page(*steps, ["lose"], *logs_in())
    assert joins(page) == [] and page["joinCode"] == ""


@needs_node
def test_a_reloaded_page_joins_nothing():
    # A reload starts the page's code anew: nothing of the old page is left.
    run_page(*in_the_lobby(), ["lose"])
    page = run_page(*guest_signs_in("Guest 5678"))
    assert joins(page) == [] and page["joinCode"] == ""


@needs_node
def test_a_connection_lost_outside_a_lobby_remembers_nothing():
    page = run_page(*guest_signs_in(), ["lose"], *guest_signs_in("Guest 5678"))
    assert joins(page) == []


# One automatic join per lost connection


@needs_node
def test_failed_attempts_to_reconnect_keep_the_code_for_the_one_join():
    page = run_page(*in_the_lobby(), ["lose"], ["fail"], ["fail"], ["fail"], *guest_signs_in("Guest 5678"))
    assert joins(page) == [REJOIN]


@needs_node
def test_a_new_connection_lost_again_before_signing_in_keeps_the_code_for_the_one_join():
    page = run_page(*in_the_lobby(), ["lose"], ["open"], ["lose"], ["fail"], *guest_signs_in("Guest 5678"))
    assert joins(page) == [REJOIN]


@needs_node
def test_signing_in_a_second_time_after_logging_out_joins_nothing_more():
    after_refusal = [["receive", ROUND_RUNNING], ["click", "home-logout"], ["receive", protocol.signed_out()]]
    same_connection = logs_in()[1:]  # without ["open"]: the connection is still there
    page = run_page(*in_the_lobby("round"), ["lose"], *logs_in(), *after_refusal, *same_connection)
    assert joins(page) == [REJOIN]


@needs_node
def test_losing_the_connection_again_on_home_after_the_one_join_joins_nothing_more():
    after_refusal = [["receive", ROUND_RUNNING], ["lose"]]
    page = run_page(*in_the_lobby("round"), ["lose"], *logs_in(), *after_refusal, *guest_signs_in("Guest 9999"))
    assert joins(page) == [REJOIN]


@needs_node
def test_after_getting_back_in_a_second_lost_connection_joins_the_lobby_again():
    back = protocol.lobby_state(CODE, "Mara", [("Mara", "finance_bro"), ("Guest 5678", "surfer")])
    steps = [*in_the_lobby(), ["lose"], *guest_signs_in("Guest 5678"), ["receive", back]]
    page = run_page(*steps, ["lose"], *guest_signs_in("Guest 9999"))
    assert joins(page) == [REJOIN, REJOIN]
