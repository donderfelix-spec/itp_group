"""Play test of leaving a running Duel and of the host change (M2-2.3, S-78, S-91, S-94).

What the tester played with three browsers, as far as the server takes part
in it and `test_server_duel.py`, `test_play_duel.py` and `test_play_round.py`
do not already check:

- a player who leaves is gone from the map, the player list and the
  progress of the others, hears nothing more of the round, cannot come back
  while it runs and can after it;
- a player who had finished and then leaves is not in the ranking
  (DESIGN.md, section 6);
- closing the tab with a minigame open, and logging in from a second
  browser, take the player out in the same way; the second browser cannot
  get into the running round;
- when the host leaves, the others read "The host left. <name> is the new
  host.", the round goes on, and after it the new host starts the next
  round, in which the old host is an ordinary player;
- when two of three leave, the one left plays on alone, to the ranking or
  to the end of the three minutes, and cannot start the next round alone;
- a player whose connection was lost signs in again on a new connection and
  is refused with "This round has already started." until the round is over.

What only the page does ("Connection lost. Reconnecting…", the Start screen
after a lost connection) cannot be checked here.
"""

import time

from server import protocol
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import (
    NOT_IN_LOBBY,
    NOT_SIGNED_IN,
    PASSWORD,
    ask,
    lobby_named,
    open_station,
    opened,
    put_at_station,
)
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import (
    FIXED_ROUTES,
    REAL_TICK,
    call_tick,
    duel_of,
    news,
    play,
    play_route,
    progress,
    result,
    start,
    state,
    the_duel_of,
    types_of,
    wait_for_news,
    wait_for_the_open_lobby,
    wait_until,
)

NAMES = ["Mara", "Tiago", "Ines"]
LEFT = {"type": "left_lobby"}
NOT_HOST = protocol.rejection("not_host")
ROUND_RUNNING = protocol.rejection("round_running")
TOO_FEW_FOR_DUEL = {"type": "error", "code": "too_few_players", "message": "Duel needs at least 2 players."}
DEADLINE_SECONDS = 5


# Helpers


def notice_of_new_host(name):
    return {"type": "notice", "message": f"The host left. {name} is the new host."}


def names_in(lobby_state):
    return [listed["name"] for listed in lobby_state["players"]]


def names_on_the_map(connection):
    """Run the real tick once and return whose positions it sent this player."""
    connection.portal.call(REAL_TICK, 0.0)
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        connection.send_json({"type": "hello", "name": "Reader"})
        found = None
        while True:
            message = connection.receive_json()
            if message["type"] == "welcome":
                break
            if message["type"] == "positions":
                found = [listed["name"] for listed in message["players"]]
        if found is not None:
            return found
        assert time.monotonic() < deadline, "the tick sent no positions in time"
        time.sleep(0.02)


def wait_for_the_progress_of(connection, names):
    """Read this player's news until the newest progress lists exactly these players. Returns the news.

    A leave is told with the lobby's state and then the progress without
    the leaver, so that progress is the last message a leave brings.
    """
    def lists_these_players(messages):
        told = [message for message in messages if message["type"] == "duel_progress"]
        return bool(told) and [listed["name"] for listed in told[-1]["players"]] == names

    return wait_until(connection, lists_these_players)


def log_in_again(connect, name):
    """A new connection, signed in with the account that already exists."""
    connection = connect()
    assert ask(connection, {"type": "log_in", "name": name, "password": PASSWORD}) == protocol.signed_in(name, False)
    return connection


def rankings_in(messages):
    return [message for message in messages if message["type"] == "duel_result"]


# A player leaves with "Leave lobby"


def test_a_leaver_is_gone_from_the_map_the_list_and_the_progress_of_the_others(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(tiago, "Tiago", FIXED_ROUTES[1][0], clock)
    news(mara), news(ines)
    assert names_on_the_map(mara) == NAMES
    news(tiago), news(ines)
    assert ask(tiago, {"type": "leave_lobby"}) == LEFT
    for connection in (mara, ines):
        told = wait_for_news(connection, "duel_progress")
        assert types_of(told) == ["lobby_state", "duel_progress"]
        assert names_in(told[0]) == ["Mara", "Ines"] and told[0]["phase"] == "round"
        assert told[1] == progress(179, ("Mara", 0), ("Ines", 0))
    assert names_on_the_map(mara) == ["Mara", "Ines"]
    assert names_on_the_map(ines) == ["Mara", "Ines"]
    assert news(tiago) == []  # the tick tells the leaver nothing


def test_a_second_leave_and_task_messages_of_the_leaver_are_refused_and_disturb_nobody(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    # Two clicks on "Leave lobby" sent past the page, one right after the other.
    tiago.send_json({"type": "leave_lobby"})
    tiago.send_json({"type": "leave_lobby"})
    assert news(tiago) == [LEFT, NOT_IN_LOBBY]
    for connection in (mara, ines):
        assert types_of(wait_for_the_progress_of(connection, ["Mara", "Ines"])) == ["lobby_state", "duel_progress"]
    for message in ({"type": "finish_station"}, {"type": "close_station"}, {"type": "open_station", "station": 2},
                    {"type": "start_game"}, {"type": "move", "dx": 1, "dy": 0}):
        assert ask(tiago, message) == NOT_IN_LOBBY
    assert ask(tiago, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert news(mara) == [] and news(ines) == []
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Ines", 0)]


def test_the_round_ends_when_the_rest_have_finished_and_the_ranking_leaves_the_leaver_out(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(tiago, "Tiago", FIXED_ROUTES[1][0], clock)
    assert ask(tiago, {"type": "leave_lobby"}) == LEFT
    for connection in (mara, ines):
        wait_for_the_progress_of(connection, ["Mara", "Ines"])
    play_route(mara, "Mara", clock)
    assert lobby_named("Mara").phase == "round"  # Ines is still running
    expected = result(False, (1, "Mara", 4.0, 3), (2, "Ines", 7.0, 3))
    for told in (play_route(ines, "Ines", clock), wait_for_the_open_lobby(mara)):
        assert rankings_in(told) == [expected]
        assert told[-1]["phase"] == "lobby" and names_in(told[-1]) == ["Mara", "Ines"]
    assert news(tiago) == []
    # After the ranking the leaver comes back with the same code, as the last in the list.
    answer = ask(tiago, {"type": "join_lobby", "code": code})
    assert answer["phase"] == "lobby" and names_in(answer) == ["Mara", "Ines", "Tiago"] and answer["host"] == "Mara"
    assert news(mara) == [answer] and news(ines) == [answer]


def test_a_player_who_finished_first_and_then_leaves_is_not_in_the_ranking(connect, clock, fixed_routes):
    # DESIGN.md, section 6: a player who leaves during the round is taken out of the ranking.
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    told = play_route(tiago, "Tiago", clock)
    assert told[1] == state(None, 3, 3.0)
    assert wait_for_news(mara, "duel_progress")[-1] == progress(177, ("Mara", 0), ("Tiago", 3), ("Ines", 0))
    assert ask(tiago, {"type": "leave_lobby"}) == LEFT
    assert wait_for_the_progress_of(mara, ["Mara", "Ines"])[-1] == progress(177, ("Mara", 0), ("Ines", 0))
    wait_for_the_progress_of(ines, ["Mara", "Ines"])
    play_route(ines, "Ines", clock)
    told = play_route(mara, "Mara", clock)
    assert rankings_in(told) == [result(False, (1, "Ines", 6.0, 3), (2, "Mara", 9.0, 3))]


# The tab is closed, the account logs in elsewhere


def test_a_player_who_closes_the_tab_with_a_minigame_open_is_gone_for_the_others(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(ines, "Ines", FIXED_ROUTES[2][0], clock)
    put_at_station("Ines", FIXED_ROUTES[2][1])
    assert open_station(ines, FIXED_ROUTES[2][1]) == opened(FIXED_ROUTES[2][1])
    news(mara), news(tiago)
    ines.close()
    for connection in (mara, tiago):
        told = wait_for_news(connection, "duel_progress")
        assert types_of(told) == ["lobby_state", "duel_progress"]
        assert names_in(told[0]) == ["Mara", "Tiago"] and told[0]["phase"] == "round"
        assert told[1] == progress(179, ("Mara", 0), ("Tiago", 0))
    assert names_on_the_map(mara) == ["Mara", "Tiago"]
    news(tiago)
    # The two who stayed play to their ranking.
    play_route(mara, "Mara", clock)
    told = play_route(tiago, "Tiago", clock)
    assert rankings_in(told) == [result(False, (1, "Mara", 4.0, 3), (2, "Tiago", 7.0, 3))]


def test_the_same_account_in_a_second_browser_signs_the_first_out_and_stays_outside_the_round(
    connect, clock, fixed_routes
):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(tiago, "Tiago", FIXED_ROUTES[1][0], clock)
    news(mara), news(ines)
    second_browser = log_in_again(connect, "Tiago")
    for connection in (mara, ines):
        told = wait_for_the_progress_of(connection, ["Mara", "Ines"])
        assert names_in(told[0]) == ["Mara", "Ines"]
        assert told[-1] == progress(179, ("Mara", 0), ("Ines", 0))
    assert names_on_the_map(mara) == ["Mara", "Ines"]
    # The first browser is signed out and is told so; nothing of the round follows.
    assert news(tiago) == [{"type": "signed_out"}]
    assert ask(tiago, {"type": "join_lobby", "code": code}) == NOT_SIGNED_IN
    # The second browser is signed in, in no lobby, and cannot get into the round.
    assert ask(second_browser, {"type": "finish_station"}) == NOT_IN_LOBBY
    assert ask(second_browser, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert news(mara) == [] and news(ines) == []
    # The station Tiago had done went with him: the ranking knows two players.
    play_route(mara, "Mara", clock)
    told = play_route(ines, "Ines", clock)
    assert rankings_in(told) == [result(False, (1, "Mara", 4.0, 3), (2, "Ines", 7.0, 3))]
    assert news(second_browser) == []


# The host leaves


def test_when_the_host_leaves_the_others_read_who_the_new_host_is_and_play_on(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    # Ines is inside a minigame when it happens: her task stays open.
    put_at_station("Ines", FIXED_ROUTES[2][0])
    assert open_station(ines, FIXED_ROUTES[2][0]) == opened(FIXED_ROUTES[2][0])
    assert ask(mara, {"type": "leave_lobby"}) == LEFT
    for connection in (tiago, ines):
        told = wait_for_news(connection, "duel_progress")
        assert types_of(told) == ["notice", "lobby_state", "duel_progress"]
        assert told[0] == notice_of_new_host("Tiago")
        assert told[1]["host"] == "Tiago" and told[1]["code"] == code and told[1]["phase"] == "round"
    clock.wait(1)
    ines.send_json({"type": "finish_station"})
    assert news(ines)[:2] == [protocol.station_done(FIXED_ROUTES[2][0]), state(FIXED_ROUTES[2][1], 1)]
    assert news(tiago) == [progress(179, ("Tiago", 0), ("Ines", 1))]
    # During the round the new host can start nothing, like the old one.
    assert ask(tiago, {"type": "start_game"}) == ROUND_RUNNING
    assert ask(tiago, {"type": "choose_mode", "mode": "duel"}) == ROUND_RUNNING
    assert ask(ines, {"type": "start_game"}) == NOT_HOST


def test_after_the_round_the_new_host_starts_the_next_one_and_the_old_host_is_an_ordinary_player(
    connect, clock, fixed_routes
):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    assert ask(mara, {"type": "leave_lobby"}) == LEFT
    for connection in (tiago, ines):
        wait_for_the_progress_of(connection, ["Tiago", "Ines"])
    play_route(tiago, "Tiago", clock)
    told = play_route(ines, "Ines", clock)
    assert rankings_in(told) == [result(False, (1, "Tiago", 3.0, 3), (2, "Ines", 6.0, 3))]
    assert told[-1]["host"] == "Tiago" and told[-1]["phase"] == "lobby"
    news(tiago)
    # The old host comes back with the code and is the last in the list now.
    answer = ask(mara, {"type": "join_lobby", "code": code})
    assert answer["host"] == "Tiago" and names_in(answer) == ["Tiago", "Ines", "Mara"]
    assert ask(mara, {"type": "start_game"}) == NOT_HOST
    assert ask(mara, {"type": "choose_mode", "mode": "duel"}) == NOT_HOST
    news(tiago), news(ines)
    told = start({"Tiago": tiago, "Ines": ines, "Mara": mara})
    for name in ("Tiago", "Ines", "Mara"):
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][0]["host"] == "Tiago" and told[name][0]["phase"] == "round"
        assert told[name][2] == progress(180, ("Tiago", 0), ("Ines", 0), ("Mara", 0))


def test_when_the_host_and_the_next_host_leave_one_after_the_other_the_third_is_host_and_plays_on(
    connect, clock, fixed_routes
):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    assert ask(mara, {"type": "leave_lobby"}) == LEFT
    tiago.close()

    told = wait_for_the_progress_of(ines, ["Ines"])
    notices = [message for message in told if message["type"] == "notice"]
    assert notices[-1] == notice_of_new_host("Ines")
    assert set(message["message"] for message in notices) <= {
        notice_of_new_host("Tiago")["message"], notice_of_new_host("Ines")["message"]
    }
    last_state = [message for message in told if message["type"] == "lobby_state"][-1]
    assert last_state["host"] == "Ines" and last_state["phase"] == "round" and last_state["code"] == code
    assert names_on_the_map(ines) == ["Ines"]
    told = play_route(ines, "Ines", clock)
    assert rankings_in(told) == [result(False, (1, "Ines", 3.0, 3))]


# Two of three leave


def test_two_of_three_leave_and_the_one_left_finishes_alone(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(mara, "Mara", FIXED_ROUTES[0][0], clock)
    assert ask(mara, {"type": "leave_lobby"}) == LEFT
    ines.close()
    wait_for_the_progress_of(tiago, ["Tiago"])
    told = play_route(tiago, "Tiago", clock)
    assert rankings_in(told) == [result(False, (1, "Tiago", 4.0, 3))]
    assert told[-1] == protocol.lobby_state(code, "Tiago", [("Tiago", "finance_bro")], "duel", "lobby")
    # Alone in the open lobby the new host cannot start the next round.
    assert ask(tiago, {"type": "start_game"}) == TOO_FEW_FOR_DUEL
    assert lobby_named("Tiago").phase == "lobby"


def test_two_of_three_leave_and_the_time_runs_out_for_the_one_left(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(ines, "Ines", FIXED_ROUTES[2][0], clock)
    ines.close()
    wait_for_the_progress_of(mara, ["Mara", "Tiago"])
    assert ask(mara, {"type": "leave_lobby"}) == LEFT
    wait_for_the_progress_of(tiago, ["Tiago"])
    play(tiago, "Tiago", FIXED_ROUTES[1][0], clock)
    news(tiago)
    clock.now = 1000.0 + 179.9
    call_tick(tiago)
    assert news(tiago) == [] and lobby_named("Tiago").phase == "round"
    clock.now = 1000.0 + 180
    call_tick(tiago)
    told = wait_for_news(tiago)
    assert types_of(told) == ["duel_result", "lobby_state"]
    assert told[0] == result(True, (1, "Tiago", None, 1))
    assert told[1]["host"] == "Tiago" and told[1]["phase"] == "lobby" and names_in(told[1]) == ["Tiago"]
    assert news(mara) == []  # the leaver hears nothing of the end


# Coming back after a lost connection


def test_a_player_whose_connection_was_lost_signs_in_again_and_is_refused_until_the_round_is_over(
    connect, clock, fixed_routes
):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(ines, "Ines", FIXED_ROUTES[2][0], clock)
    ines.close()
    for connection in (mara, tiago):
        wait_for_the_progress_of(connection, ["Mara", "Tiago"])
    # The page connects again: being signed in went with the old connection (S-78).
    back = connect()
    assert ask(back, {"type": "join_lobby", "code": code}) == NOT_SIGNED_IN
    assert ask(back, {"type": "log_in", "name": "Ines", "password": PASSWORD}) == protocol.signed_in("Ines", False)
    assert ask(back, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert ask(back, {"type": "join_lobby", "code": code}) == ROUND_RUNNING  # trying again changes nothing
    assert news(mara) == [] and news(tiago) == []
    assert the_duel_of("Mara").names() == ["Mara", "Tiago"]
    # Nobody tells her when the round is over: she finds out by trying again.
    play_route(mara, "Mara", clock)
    play_route(tiago, "Tiago", clock)
    news(mara)
    assert news(back) == []
    answer = ask(back, {"type": "join_lobby", "code": code})
    assert answer["phase"] == "lobby" and names_in(answer) == ["Mara", "Tiago", "Ines"]
    news(mara), news(tiago)
    # The next round is hers too, from the first station: nothing is left of the station she had done.
    told = start({"Mara": mara, "Tiago": tiago, "Ines": back})
    assert told["Ines"][1] == state(FIXED_ROUTES[2][0], 0)
    assert told["Ines"][2] == progress(180, ("Mara", 0), ("Tiago", 0), ("Ines", 0))


def test_a_guest_who_comes_back_is_a_new_guest_and_is_refused_like_everybody_else(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    back = connect()
    answer = ask(back, {"type": "guest"})
    assert answer["type"] == "signed_in" and answer["guest"] is True
    assert ask(back, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    # When everybody has left the round, its code is free: the lobby is gone.
    assert ask(players["Mara"], {"type": "leave_lobby"}) == LEFT
    wait_for_the_progress_of(players["Tiago"], ["Tiago"])
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == LEFT
    assert ask(back, {"type": "join_lobby", "code": code}) == protocol.rejection("no_lobby")


def test_nothing_of_all_this_is_logged_as_an_error(connect, clock, fixed_routes, caplog):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    put_at_station("Ines", FIXED_ROUTES[2][0])
    open_station(ines, FIXED_ROUTES[2][0])
    ines.close()
    second_browser = log_in_again(connect, "Mara")
    wait_for_the_progress_of(tiago, ["Tiago"])
    assert ask(second_browser, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    told = play_route(tiago, "Tiago", clock)
    assert rankings_in(told) == [result(False, (1, "Tiago", 3.0, 3))]
    assert ask(second_browser, {"type": "join_lobby", "code": code})["phase"] == "lobby"
    assert [record for record in caplog.records if record.levelname in ("ERROR", "CRITICAL")] == []
