"""Play test of the way back to the lobby after a Duel (M2-2.2, S-91, S-94).

What the tester played with three browsers, as far as the server takes part
in it and `test_server_duel.py` and `test_play_duel.py` do not already check:

- three players finish and all get the same ranking, then the open lobby
  with the same code, host and players; everybody stays where they stood;
- between two rounds the lobby is a lobby again: walking, another
  character and the host's mode choice are accepted, a task is not;
- during the round the same actions are refused with the texts of
  DESIGN.md, section 9, and nobody else hears of them;
- the second round puts everybody on the spawn with a fresh route, nothing
  done and the full three minutes, whatever the first round left behind;
- the same after a round that ended because the time ran out, with one
  player finished, one inside a minigame and one who did nothing.

What only the page does (the card "Duel ranking" and its button "Back to
lobby", the panel that shows the lobby again) cannot be checked here: the
button sends nothing to the server.
"""

import time

from server import protocol
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import (
    NOT_IN_ROUND,
    SPAWN,
    STATION,
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
    state,
    the_duel_of,
    types_of,
    wait_for_news,
)

NAMES = ["Mara", "Tiago", "Ines"]
NOT_HOST = protocol.rejection("not_host")
ROUND_RUNNING = protocol.rejection("round_running")
CHARACTER_TAKEN = protocol.rejection("character_taken")
BAD_MODE = {"type": "error", "code": "bad_mode", "message": "That mode does not exist."}
DEADLINE_SECONDS = 5


# Helpers


def at_station(station):
    return (float(STATION[station]["x"]), float(STATION[station]["y"]))


def where(name):
    """Where the server has the player standing, or None before a tick placed them."""
    return lobby_named(name).walkers.position_of(name)


def play_everybody_to_the_end(players, clock):
    """Mara, Tiago and Ines finish in this order, five seconds apart. Returns the last player's news."""
    told = []
    for name in players:
        clock.wait(5)
        told = play_route(players[name], name, clock)
    return told


def read_everything(players):
    for connection in players.values():
        news(connection)


def positions_after_a_tick(connection, seconds, readers=()):
    """Run the real tick once and return the positions it sent this player, as `{name: (x, y)}`.

    The tick tells everybody in the lobby. `readers` are other connections
    whose positions message is read away too, so their next answer is not it.
    """
    connection.portal.call(REAL_TICK, seconds)
    for reader in readers:
        wait_for_positions(reader)
    return wait_for_positions(connection)


def wait_for_positions(connection):
    """Read this player's messages until a `positions` message was among them. Returns the last one."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        connection.send_json({"type": "hello", "name": "Reader"})
        found = None
        while True:
            message = connection.receive_json()
            if message["type"] == "welcome":
                break
            if message["type"] == "positions":
                found = {listed["name"]: (listed["x"], listed["y"]) for listed in message["players"]}
        if found is not None:
            return found
        assert time.monotonic() < deadline, "the tick sent no positions in time"
        time.sleep(0.02)


def start_without_placing(players):
    """The host starts. Unlike `start` of test_server_duel.py nobody is put on the spawn by the test."""
    host = next(iter(players.values()))
    host.send_json({"type": "start_game"})
    return {name: news(connection) for name, connection in players.items()}


# Everybody finishes


def test_three_players_finish_and_all_get_the_same_ranking_and_the_same_open_lobby(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    told = {"Ines": play_everybody_to_the_end(players, clock)}
    told["Mara"] = news(players["Mara"])
    told["Tiago"] = news(players["Tiago"])
    # Place, name and the server's time for each of the three.
    expected = result(False, (1, "Mara", 8.0, 3), (2, "Tiago", 16.0, 3), (3, "Ines", 24.0, 3))
    open_lobby = protocol.lobby_state(
        code, "Mara", [("Mara", "consultant"), ("Tiago", "finance_bro"), ("Ines", "exchange_student")], "duel", "lobby"
    )
    for name in NAMES:
        assert told[name][-2:] == [expected, open_lobby]
        assert types_of(told[name]).count("duel_result") == 1


def test_at_the_end_of_a_round_everybody_stays_where_they_stand(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    last_stations = {name: route[-1] for name, route in zip(NAMES, FIXED_ROUTES)}
    for name in NAMES:
        assert where(name) == at_station(last_stations[name])
    # Ticks in the open lobby move nobody who is not walking.
    call_tick(players["Mara"])
    call_tick(players["Mara"])
    for name in NAMES:
        assert where(name) == at_station(last_stations[name])


# Between two rounds


def test_between_two_rounds_a_player_walks_and_everybody_sees_it(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    # Tiago stands at his last station (1, in the Lecture Hall) and walks to the left.
    start_x, start_y = at_station(FIXED_ROUTES[1][-1])
    players["Tiago"].send_json({"type": "move", "dx": -1, "dy": 0})
    news(players["Tiago"])  # the server has read the move
    seen = positions_after_a_tick(players["Mara"], 0.1)
    assert seen["Tiago"] == (start_x - 9.0, start_y)
    assert seen["Mara"] == at_station(FIXED_ROUTES[0][-1])


def test_between_two_rounds_a_player_chooses_another_character_and_everybody_is_told(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    answer = ask(players["Tiago"], {"type": "choose_character", "character": "surfer"})
    assert answer["type"] == "lobby_state" and answer["phase"] == "lobby"
    assert {"name": "Tiago", "character": "surfer"} in answer["players"]
    assert news(players["Mara"]) == [answer]
    assert news(players["Ines"]) == [answer]
    # A character somebody else has stays refused, as before the first round.
    assert ask(players["Ines"], {"type": "choose_character", "character": "surfer"}) == CHARACTER_TAKEN
    assert news(players["Mara"]) == []


def test_between_two_rounds_the_host_can_choose_the_mode_and_nobody_else(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    answer = ask(players["Mara"], {"type": "choose_mode", "mode": "duel"})
    assert answer["type"] == "lobby_state" and answer["mode"] == "duel" and answer["phase"] == "lobby"
    assert news(players["Tiago"]) == [answer]
    assert ask(players["Tiago"], {"type": "choose_mode", "mode": "duel"}) == NOT_HOST
    assert ask(players["Tiago"], {"type": "start_game"}) == NOT_HOST
    # Classic is not built yet: the host cannot choose it past the page either.
    assert ask(players["Mara"], {"type": "choose_mode", "mode": "classic"}) == BAD_MODE
    assert lobby_named("Mara").phase == "lobby"


def test_between_two_rounds_no_station_opens_even_for_a_player_standing_at_one(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    for name, route in zip(NAMES, FIXED_ROUTES):
        assert where(name) == at_station(route[-1])
        assert open_station(players[name], route[-1]) == NOT_IN_ROUND
        assert open_station(players[name], route[0]) == NOT_IN_ROUND
    for name in NAMES:
        assert news(players[name]) == []


# During the round


def test_during_a_duel_character_mode_and_start_are_refused_and_nobody_else_hears_of_it(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    assert ask(mara, {"type": "choose_mode", "mode": "duel"}) == ROUND_RUNNING
    assert ask(mara, {"type": "start_game"}) == ROUND_RUNNING
    assert ask(mara, {"type": "choose_character", "character": "surfer"}) == ROUND_RUNNING
    assert ask(tiago, {"type": "choose_character", "character": "surfer"}) == ROUND_RUNNING
    # For a member "not the host" comes first, as in the lobby.
    assert ask(tiago, {"type": "choose_mode", "mode": "duel"}) == NOT_HOST
    assert ask(tiago, {"type": "start_game"}) == NOT_HOST
    assert news(ines) == [] and news(mara) == [] and news(tiago) == []
    assert lobby_named("Mara").players() == [
        ("Mara", "consultant"), ("Tiago", "finance_bro"), ("Ines", "exchange_student")
    ]
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Tiago", 0), ("Ines", 0)]


def test_the_same_actions_are_refused_again_in_the_second_round(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    assert ask(players["Tiago"], {"type": "choose_character", "character": "surfer"})["type"] == "lobby_state"
    read_everything(players)
    start_without_placing(players)
    assert ask(players["Tiago"], {"type": "choose_character", "character": "founder"}) == ROUND_RUNNING
    assert ask(players["Mara"], {"type": "choose_mode", "mode": "duel"}) == ROUND_RUNNING
    assert ask(players["Mara"], {"type": "start_game"}) == ROUND_RUNNING
    # The character chosen between the rounds is the one of the second round.
    assert ("Tiago", "surfer") in lobby_named("Mara").players()


# The second round


def test_the_second_round_has_the_same_code_and_puts_everybody_on_the_spawn(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    for name, route in zip(NAMES, FIXED_ROUTES):
        assert where(name) == at_station(route[-1])
    told = start_without_placing(players)
    for name in NAMES:
        assert told[name][0]["type"] == "lobby_state"
        assert told[name][0]["code"] == code and told[name][0]["phase"] == "round"
        assert where(name) is None  # the next tick places them
    seen = positions_after_a_tick(players["Ines"], 0.0)
    assert seen == {name: (float(SPAWN[0]), float(SPAWN[1])) for name in NAMES}


def test_the_second_round_starts_with_nothing_done_the_full_time_and_no_old_ranking(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    clock.wait(600)  # ten minutes in the lobby do not count for the next round
    told = start_without_placing(players)
    for name, route in zip(NAMES, FIXED_ROUTES):
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][1] == state(route[0], 0)
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0), ("Ines", 0))
    # A station finished in the first round is open again where the new route asks for it.
    first = FIXED_ROUTES[0][0]
    put_at_station("Mara", first)
    assert open_station(players["Mara"], first) == opened(first)


def test_the_second_round_is_ranked_by_its_own_times_only(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    start_without_placing(players)
    # This time Ines is first and Mara does not finish at all.
    clock.wait(2)
    play_route(players["Ines"], "Ines", clock)
    play_route(players["Tiago"], "Tiago", clock)
    play(players["Mara"], "Mara", FIXED_ROUTES[0][0], clock)
    clock.wait(180)
    call_tick(players["Mara"])
    expected = result(True, (1, "Ines", 5.0, 3), (2, "Tiago", 8.0, 3), (3, "Mara", None, 1))
    for name in NAMES:
        told = wait_for_news(players[name])
        assert [message for message in told if message["type"] == "duel_result"] == [expected]
        assert told[-1]["phase"] == "lobby"


def test_three_rounds_in_a_row_in_the_same_lobby(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    for round_number in range(3):
        told = play_everybody_to_the_end(players, clock)
        assert told[-2]["type"] == "duel_result" and len(told[-2]["ranking"]) == 3
        assert told[-1]["phase"] == "lobby" and told[-1]["code"] == code
        read_everything(players)
        if round_number < 2:
            start_without_placing(players)
    lobby = lobby_named("Mara")
    assert lobby.phase == "lobby" and lobby.duel is None and lobby.tasks is None


# The time runs out


def time_runs_out_with_one_finished_one_in_a_minigame_and_one_idle(players, clock):
    """Mara finishes, Tiago has done one station and has his second one open, Ines did nothing.

    Returns what each player was told at the end, as `{name: [messages]}`.
    """
    play_route(players["Mara"], "Mara", clock)
    play(players["Tiago"], "Tiago", FIXED_ROUTES[1][0], clock)
    put_at_station("Tiago", FIXED_ROUTES[1][1])
    assert open_station(players["Tiago"], FIXED_ROUTES[1][1]) == opened(FIXED_ROUTES[1][1])
    read_everything(players)
    clock.now = 1000.0 + 180
    call_tick(players["Mara"])
    return {name: wait_for_news(players[name]) for name in NAMES}


def test_when_the_time_runs_out_the_ranking_says_so_and_shows_how_far_everybody_came(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    told = time_runs_out_with_one_finished_one_in_a_minigame_and_one_idle(players, clock)
    expected = result(True, (1, "Mara", 3.0, 3), (2, "Tiago", None, 1), (3, "Ines", None, 0))
    assert expected["time_up"] is True
    assert types_of(told["Mara"]) == ["duel_result", "lobby_state"]
    assert types_of(told["Ines"]) == ["duel_result", "lobby_state"]
    # Tiago's window is closed first, so the ranking is not hidden behind it.
    assert types_of(told["Tiago"]) == ["station_closed", "duel_result", "lobby_state"]
    for name in NAMES:
        assert told[name][-2] == expected
        assert told[name][-1]["phase"] == "lobby" and told[name][-1]["code"] == code


def test_after_the_time_ran_out_the_player_from_the_minigame_walks_again(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    time_runs_out_with_one_finished_one_in_a_minigame_and_one_idle(players, clock)
    start_x, start_y = at_station(FIXED_ROUTES[1][1])
    assert where("Tiago") == (start_x, start_y)
    players["Tiago"].send_json({"type": "move", "dx": 1, "dy": 0})
    news(players["Tiago"])
    seen = positions_after_a_tick(players["Ines"], 0.1)
    assert seen["Tiago"] == (start_x + 9.0, start_y)


def test_the_round_after_a_time_up_starts_fresh_for_all_three(connect, clock, fixed_routes):
    players, code = duel_of(connect, NAMES)
    time_runs_out_with_one_finished_one_in_a_minigame_and_one_idle(players, clock)
    told = start_without_placing(players)
    for name, route in zip(NAMES, FIXED_ROUTES):
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][0]["code"] == code
        assert told[name][1] == state(route[0], 0)
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0), ("Ines", 0))
        assert where(name) is None
    on_the_spawn = {name: (float(SPAWN[0]), float(SPAWN[1])) for name in NAMES}
    assert positions_after_a_tick(players["Mara"], 0.0, readers=[players["Tiago"], players["Ines"]]) == on_the_spawn
    # Tiago's task from the first round is gone: he opens his first station anew.
    first = FIXED_ROUTES[1][0]
    put_at_station("Tiago", first)
    assert open_station(players["Tiago"], first) == opened(first)
    # The new round has its own three minutes: it is not over yet, long after the first one's end.
    clock.wait(179)
    call_tick(players["Mara"])
    assert lobby_named("Mara").phase == "round"
    assert "duel_result" not in types_of(news(players["Mara"]))


def test_nothing_of_all_this_is_logged_as_an_error(connect, clock, fixed_routes, caplog):
    players, code = duel_of(connect, NAMES)
    time_runs_out_with_one_finished_one_in_a_minigame_and_one_idle(players, clock)
    start_without_placing(players)
    play_everybody_to_the_end(players, clock)
    read_everything(players)
    start_without_placing(players)
    assert [record for record in caplog.records if record.levelname in ("ERROR", "CRITICAL")] == []
