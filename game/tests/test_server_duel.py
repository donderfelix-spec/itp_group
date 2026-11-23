"""A Duel over the WebSocket, with 2, 3 and 8 players (M2-4.7, S-94).

The tick loop is switched off here (see conftest.py), so no `positions`
messages mix with the answers; the tests that need the tick call the real
one themselves. The players are put where the tests need them, and the
server's clock is the one of task_helpers.py, set by the tests.

Most tests fix the routes (`fixed_routes`), so they know who has to go
where. The tests of the start draw them for real.
"""

import random
import time

import pytest

from server import main, protocol
from server.main import app
from server.modes import duel, tasks
from server.modes.duel import all_routes, route_length

# `clock`, `client` and `connect` are fixtures; the placeholder at every
# station gives every task a known content and a minimum time of 1 second.
from task_helpers import (  # noqa: F401
    NOT_IN_ROUND,
    NOT_NEEDED,
    PASSWORD,
    TASK_FAILED,
    TITLES,
    TOO_FAR,
    ask,
    client,
    clock,
    close_station,
    connect,
    lobby_named,
    open_station,
    opened,
    placeholder_at_every_station,
    player,
    put,
    put_at_station,
    SPAWN,
)

# The real tick, taken before conftest.py replaces it for the tests.
REAL_TICK = main.tick

IN_USE = [1, 2, 3, 4, 5]
EIGHT_NAMES = ["Mara", "Tiago", "Ines", "Rui", "Sofia", "Duarte", "Leonor", "Vasco"]
# What `fixed_routes` gives the players, in joining order.
FIXED_ROUTES = [(3, 1, 5), (2, 4, 1), (4, 5, 2), (1, 2, 3), (5, 3, 4), (1, 4, 2), (2, 5, 3), (3, 4, 1)]
NOT_HOST = protocol.rejection("not_host")
ROUND_RUNNING = protocol.rejection("round_running")
DEADLINE_SECONDS = 5


@pytest.fixture
def fixed_routes(monkeypatch):
    """Every player gets the route of FIXED_ROUTES at their place in the joining order."""
    def draw(names, stations_in_use, distances, rng):
        return dict(zip(names, FIXED_ROUTES))

    monkeypatch.setattr(duel, "draw_routes", draw)


# Helpers


def news(connection):
    """Everything the server has sent this connection and the test has not read yet.

    A hello is sent and everything up to its answer is collected, so this
    never waits forever. `positions` messages (from tests that call the
    tick) are left out.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    messages = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return [message for message in messages if message["type"] != "positions"]
        messages.append(message)


def wait_for_news(connection, last_type="lobby_state"):
    """Like `news`, but waits until a message of `last_type` has arrived.

    For what the tick sends on its own: its sends run after the tick, so
    they may not all be there at the first look. The end of a round is told
    with the lobby's state as the last message.

    Also for what another player's leaving brings: the leaver gets
    `left_lobby` first and the others are told after it, so a test that has
    read the leaver's answer cannot count on the others' messages yet.
    """
    return wait_until(connection, lambda messages: last_type in types_of(messages))


def wait_for_the_open_lobby(connection):
    """Like `news`, but waits until the last message is the lobby's state with phase "lobby".

    For a round that ends because a player left: the others get the state
    of the leave first (phase "round"), so the first `lobby_state` is not
    the end yet.
    """
    def lobby_is_open(messages):
        return bool(messages) and messages[-1]["type"] == "lobby_state" and messages[-1]["phase"] == "lobby"

    return wait_until(connection, lobby_is_open)


def wait_until(connection, is_complete):
    """Collect the connection's news, in the order sent, until `is_complete(messages)` is true."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    messages = []
    while True:
        messages += news(connection)
        if is_complete(messages):
            return messages
        assert time.monotonic() < deadline, "the expected messages did not arrive in time"
        time.sleep(0.02)


def types_of(messages):
    return [message["type"] for message in messages]


def lobby_of(connect, names):
    """The first name creates a lobby, the others join in this order. Everybody has read everything.

    Returns `({name: connection}, code)`.
    """
    players = {name: player(connect, name) for name in names}
    code = ask(players[names[0]], {"type": "create_lobby"})["code"]
    for name in names[1:]:
        assert ask(players[name], {"type": "join_lobby", "code": code})["type"] == "lobby_state"
    for connection in players.values():
        news(connection)
    return players, code


def start(players):
    """The first player starts the round. Returns what each player was told, as `{name: [messages]}`."""
    names = list(players)
    players[names[0]].send_json({"type": "start_game"})
    told = {name: news(players[name]) for name in names}
    for name in names:
        put(name, SPAWN)  # as after the first tick
    return told


def duel_of(connect, names):
    """A running Duel of these players. Returns `({name: connection}, code)`; everything is read."""
    players, code = lobby_of(connect, names)
    start(players)
    return players, code


def the_duel_of(name):
    return lobby_named(name).duel


def route_of(name):
    return the_duel_of(name)._players[name].route


def play(connection, name, station, clock, seconds=1):
    """Walk to the station, open it, wait and report it as done. Returns the player's news.

    What was waiting for the player before (the progress of the others) is
    read first and thrown away.
    """
    news(connection)
    put_at_station(name, station)
    assert open_station(connection, station) == opened(station)
    clock.wait(seconds)
    connection.send_json({"type": "finish_station"})
    return news(connection)


def play_route(connection, name, clock):
    """Play every station the player has left. Returns the news after the last one."""
    told = []
    while the_duel_of(name) is not None and the_duel_of(name).next_station(name) is not None:
        told = play(connection, name, the_duel_of(name).next_station(name), clock)
    return told


def state(next_station, done, seconds=None):
    return protocol.duel_state(next_station, done, 3, seconds)


def progress(seconds_left, *players):
    return protocol.duel_progress(players, 3, seconds_left)


def result(time_up, *rows):
    ranking = [{"place": place, "name": name, "seconds": seconds, "done": done} for place, name, seconds, done in rows]
    return protocol.duel_result(ranking, time_up)


def call_tick(connection):
    """Run the real tick once, inside the server, as its loop would."""
    connection.portal.call(REAL_TICK, 0.0)


# The start


@pytest.mark.parametrize("player_count", [2, 3, 8])
def test_at_the_start_everybody_gets_the_state_their_first_station_and_the_progress(connect, player_count):
    names = EIGHT_NAMES[:player_count]
    players, code = lobby_of(connect, names)
    told = start(players)
    everybody_at_zero = progress(180, *[(name, 0) for name in names])
    for name in names:
        lobby_state, own_state, shared_progress = told[name]
        assert lobby_state["type"] == "lobby_state" and lobby_state["phase"] == "round"
        assert own_state == state(route_of(name)[0], 0)
        assert shared_progress == everybody_at_zero


@pytest.mark.parametrize("player_count", [2, 3, 8])
def test_every_player_has_a_route_of_three_different_stations_and_no_two_the_same(connect, player_count):
    names = EIGHT_NAMES[:player_count]
    players, code = duel_of(connect, names)
    routes = [route_of(name) for name in names]
    assert len(set(routes)) == player_count
    for route in routes:
        assert len(route) == 3 and len(set(route)) == 3 and set(route) <= set(IN_USE)


@pytest.mark.parametrize("seed", range(12))
def test_the_routes_of_a_real_start_are_about_equally_long(connect, monkeypatch, seed):
    # `random.Random` has everything the server uses of `random`, with a seed.
    monkeypatch.setattr(main, "random", random.Random(seed))
    names = EIGHT_NAMES[:4]
    players, code = duel_of(connect, names)
    lengths = [route_length(route_of(name), app.state.distances) for name in names]
    # One of them is the route drawn first: all others are within 10 % of it.
    assert any(all(abs(length - first) <= 0.1 * first for length in lengths) for first in lengths)


def test_two_starts_with_different_luck_give_different_routes(connect, monkeypatch):
    seen = set()
    for seed in range(8):
        app.state.lobbies = type(app.state.lobbies)()
        app.state.sessions = type(app.state.sessions)()
        app.state.account_store = type(app.state.account_store)()
        monkeypatch.setattr(main, "random", random.Random(seed))
        duel_of(connect, ["Mara", "Tiago"])
        seen.add((route_of("Mara"), route_of("Tiago")))
    assert len(seen) > 1


def test_nobody_is_sent_another_players_route_or_station(connect, clock, fixed_routes):
    names = EIGHT_NAMES[:3]
    players, code = lobby_of(connect, names)
    everything = {name: list(messages) for name, messages in start(players).items()}
    for name in names:
        for station in route_of_fixed(names, name):
            everything[name] += play(players[name], name, station, clock)
            for reader in names:
                everything[reader] += news(players[reader])
    for name in names:
        own_states = [message for message in everything[name] if message["type"] == "duel_state"]
        # Start, and one after each of the three stations: only the player's own.
        assert [message["next_station"] for message in own_states] == list(route_of_fixed(names, name)) + [None]
        for message in everything[name]:
            if message["type"] != "duel_state":
                assert "next_station" not in message and "route" not in str(message)
            if message["type"] == "duel_progress":
                assert all(set(listed) == {"name", "done"} for listed in message["players"])


def route_of_fixed(names, name):
    return FIXED_ROUTES[names.index(name)]


def test_the_lobby_state_of_a_duel_carries_nothing_new(connect):
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    told = start(players)
    assert set(told["Mara"][0]) == {"type", "code", "host", "players", "mode", "phase"}


def test_too_few_players_start_no_duel(connect):
    mara = player(connect, "Mara")
    ask(mara, {"type": "create_lobby"})
    ask(mara, {"type": "choose_mode", "mode": "duel"})  # a new lobby is in Solo (S-203); Duel needs two
    assert ask(mara, {"type": "start_game"})["code"] == "too_few_players"
    assert the_duel_of("Mara") is None
    assert lobby_named("Mara").tasks is None


def test_only_the_host_starts_the_duel(connect):
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    assert ask(players["Tiago"], {"type": "start_game"}) == NOT_HOST
    assert the_duel_of("Mara") is None


def test_every_mode_that_can_be_chosen_has_its_round(connect):
    assert set(main.ROUND_SETUPS) == set(protocol.MODES)


# The order of the stations


def test_only_the_next_station_opens_and_every_other_is_not_needed(connect, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]  # route 3, 1, 5
    for station in (1, 2, 4, 5):
        put_at_station("Mara", station)
        assert open_station(mara, station) == NOT_NEEDED
    put_at_station("Mara", 3)
    assert open_station(mara, 3) == opened(3)


def test_the_next_station_from_too_far_away_is_too_far(connect, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    assert open_station(players["Mara"], 3) == TOO_FAR


def test_two_players_at_the_same_station_only_the_one_who_needs_it_opens_it(connect, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    put_at_station("Mara", 3)
    put_at_station("Tiago", 3)
    assert open_station(players["Tiago"], 3) == NOT_NEEDED  # Tiago's route begins at 2
    assert open_station(players["Mara"], 3) == opened(3)


def test_a_finished_station_brings_the_next_one_and_tells_everybody_the_count(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    clock.wait(27.2)
    told = play(mara, "Mara", 3, clock)
    new_progress = progress(152, ("Mara", 1), ("Tiago", 0))
    assert told == [protocol.station_done(3), state(1, 1), new_progress]
    # Tiago hears the count, not the station.
    assert news(tiago) == [new_progress]


def test_after_a_station_the_old_one_is_not_needed_and_the_new_one_opens(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    play(mara, "Mara", 3, clock)
    assert open_station(mara, 3) == NOT_NEEDED
    put_at_station("Mara", 5)
    assert open_station(mara, 5) == NOT_NEEDED  # the third of the route, not yet
    put_at_station("Mara", 1)
    assert open_station(mara, 1) == opened(1)


def test_closing_a_task_counts_nothing_and_tells_nobody(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    put_at_station("Mara", 3)
    open_station(mara, 3)
    assert close_station(mara) == protocol.station_closed(3)
    assert news(mara) == [] and news(tiago) == []
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Tiago", 0)]


def test_a_task_reported_too_fast_counts_nothing_and_tells_nobody(connect, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    put_at_station("Mara", 3)
    open_station(mara, 3)
    mara.send_json({"type": "finish_station"})
    assert types_of(news(mara)) == ["error", "station_closed"]
    assert news(tiago) == []
    assert the_duel_of("Mara").state_of("Mara") == (3, 0, None)


def test_the_third_station_ends_the_route_with_the_servers_time(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play(mara, "Mara", 3, clock, seconds=20)
    play(mara, "Mara", 1, clock, seconds=30)
    told = play(mara, "Mara", 5, clock, seconds=22.44)
    new_progress = progress(108, ("Mara", 3), ("Tiago", 0))
    assert told == [protocol.station_done(5), state(None, 3, 72.4), new_progress]
    assert news(tiago)[-1] == new_progress
    # Tiago is still running, so the round goes on.
    assert lobby_named("Mara").phase == "round"


def test_a_finished_player_needs_no_station_any_more(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    play_route(mara, "Mara", clock)
    for station in IN_USE:
        put_at_station("Mara", station)
        assert open_station(mara, station) == NOT_NEEDED


# The end: everybody finished


@pytest.mark.parametrize("player_count", [2, 3, 8])
def test_when_everybody_has_finished_everybody_gets_the_ranking_and_the_lobby_is_open(
    connect, clock, fixed_routes, player_count
):
    names = EIGHT_NAMES[:player_count]
    players, code = duel_of(connect, names)
    # They finish one after the other, the last in the lobby first.
    order = list(reversed(names))
    for name in order[:-1]:
        clock.wait(5)
        play_route(players[name], name, clock)
        for reader in names:
            assert "duel_result" not in types_of(news(players[reader]))
    clock.wait(5)
    last = order[-1]
    told = play_route(players[last], last, clock)
    rows = [(place + 1, name, 8.0 * (place + 1), 3) for place, name in enumerate(order)]
    expected_result = result(False, *rows)
    assert types_of(told) == ["station_done", "duel_state", "duel_progress", "duel_result", "lobby_state"]
    assert told[3] == expected_result
    assert told[4]["phase"] == "lobby" and told[4]["host"] == names[0]
    for name in names:
        if name != last:
            assert news(players[name])[-3:] == told[-3:]
    lobby = lobby_named(names[0])
    assert lobby.phase == "lobby" and lobby.duel is None and lobby.tasks is None


def test_the_ranking_is_sent_exactly_once(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play_route(mara, "Mara", clock)
    told = play_route(tiago, "Tiago", clock)
    assert types_of(told).count("duel_result") == 1
    assert types_of(news(mara)).count("duel_result") == 1
    # Later ticks and later messages find no round to end.
    clock.wait(500)
    call_tick(mara)
    call_tick(mara)
    mara.send_json({"type": "open_station", "station": 3})
    assert news(mara) == [NOT_IN_ROUND]
    assert news(tiago) == []


def test_ties_share_a_place_in_the_ranking_that_is_sent(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    # Mara and Ines do one station each, Tiago none, then the time runs out.
    play(ines, "Ines", 4, clock)
    play(mara, "Mara", 3, clock)
    clock.wait(180)
    call_tick(mara)
    expected = result(True, (1, "Mara", None, 1), (1, "Ines", None, 1), (3, "Tiago", None, 0))
    assert expected in wait_for_news(tiago)


# The end: time up


def test_after_180_seconds_the_tick_ends_the_round_without_any_message_from_a_browser(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play_route(mara, "Mara", clock)
    news(tiago)
    clock.now = 1000.0 + 179.9
    call_tick(mara)
    assert news(mara) == [] and news(tiago) == []
    assert lobby_named("Mara").phase == "round"
    clock.now = 1000.0 + 180
    call_tick(mara)
    expected = result(True, (1, "Mara", 3.0, 3), (2, "Tiago", None, 0))
    for connection in (mara, tiago):
        told = wait_for_news(connection)
        assert told[0] == expected
        assert types_of(told) == ["duel_result", "lobby_state"]
        assert told[1]["phase"] == "lobby"
    assert lobby_named("Mara").duel is None


def test_the_real_tick_loop_ends_a_round_whose_time_is_up(connect, clock, fixed_routes, monkeypatch):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    monkeypatch.setattr(main, "tick", REAL_TICK)  # from here on the server's own loop ticks
    clock.wait(180)
    for connection in players.values():
        told = wait_for_news(connection)
        assert types_of(told) == ["duel_result", "lobby_state"]
        assert told[0] == result(True, (1, "Mara", None, 0), (1, "Tiago", None, 0))
    # The loop keeps ticking: nothing more comes.
    time.sleep(0.3)
    assert news(players["Mara"]) == []


def test_a_task_message_after_the_time_is_up_ends_the_round_first(connect, clock, fixed_routes):
    # No tick has noticed yet. The finish comes too late: it does not count.
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play(mara, "Mara", 3, clock)
    play(mara, "Mara", 1, clock)
    put_at_station("Mara", 5)
    assert open_station(mara, 5) == opened(5)
    news(tiago)
    clock.now = 1000.0 + 180
    mara.send_json({"type": "finish_station"})
    told = news(mara)
    expected = result(True, (1, "Mara", None, 2), (2, "Tiago", None, 0))
    assert told == [protocol.station_closed(5), expected, told[2], NOT_IN_ROUND]
    assert told[2]["type"] == "lobby_state" and told[2]["phase"] == "lobby"
    assert news(tiago) == [expected, told[2]]


def test_the_last_station_and_the_time_limit_in_the_same_tick_end_the_round_once(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play_route(mara, "Mara", clock)
    play(tiago, "Tiago", 2, clock)
    play(tiago, "Tiago", 4, clock)
    put_at_station("Tiago", 1)
    open_station(tiago, 1)
    news(mara)
    # Tiago's last "done" and the tick both come at exactly 180 seconds.
    clock.now = 1000.0 + 180
    tiago.send_json({"type": "finish_station"})
    call_tick(mara)
    call_tick(mara)
    told_tiago = news(tiago)
    told_mara = wait_for_news(mara)
    assert types_of(told_tiago).count("duel_result") == 1
    assert types_of(told_mara).count("duel_result") == 1
    assert types_of(told_mara).count("lobby_state") == 1
    assert lobby_named("Mara").phase == "lobby"


def test_a_player_with_a_minigame_open_gets_it_closed_before_the_ranking(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    put_at_station("Tiago", 2)
    assert open_station(tiago, 2) == opened(2)
    told = play_route(mara, "Mara", clock)  # Mara finishes; Tiago is still inside his task
    assert "duel_result" not in types_of(told)
    news(tiago)
    clock.wait(200)
    call_tick(mara)
    told = wait_for_news(tiago)
    assert types_of(told) == ["station_closed", "duel_result", "lobby_state"]
    assert told[0] == protocol.station_closed(2)
    # Mara had nothing open: no `station_closed` for her.
    assert types_of(wait_for_news(mara)) == ["duel_result", "lobby_state"]
    # Tiago's task is gone on the server too: he can walk again.
    assert not tasks.stands_still(lobby_named("Tiago").tasks, "Tiago")


# After the end


def test_after_the_end_no_task_can_be_opened_closed_or_finished(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    clock.wait(180)
    call_tick(players["Mara"])
    for connection in players.values():
        wait_for_news(connection)
    mara = players["Mara"]
    put_at_station("Mara", 3)
    assert open_station(mara, 3) == NOT_IN_ROUND
    assert close_station(mara) == NOT_IN_ROUND
    assert ask(mara, {"type": "finish_station"}) == NOT_IN_ROUND


def test_the_host_starts_a_second_round_in_the_same_lobby_with_new_routes(connect, clock, monkeypatch):
    monkeypatch.setattr(main, "random", random.Random(3))
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    first_duel = the_duel_of("Mara")
    first_routes = (route_of("Mara"), route_of("Tiago"))
    play_route(mara, "Mara", clock)
    play_route(tiago, "Tiago", clock)
    news(mara)
    assert lobby_named("Mara").phase == "lobby"

    assert ask(tiago, {"type": "start_game"}) == NOT_HOST
    clock.wait(60)
    told = start(players)
    assert lobby_named("Mara").code == code
    second_duel = the_duel_of("Mara")
    assert second_duel is not None and second_duel is not first_duel
    for name in ("Mara", "Tiago"):
        assert types_of(told[name]) == ["lobby_state", "duel_state", "duel_progress"]
        assert told[name][0]["phase"] == "round"
        # Nothing is finished and the clock is full again.
        assert told[name][1] == state(route_of(name)[0], 0)
        assert told[name][2] == progress(180, ("Mara", 0), ("Tiago", 0))
    assert (route_of("Mara"), route_of("Tiago")) != first_routes
    # A station finished in the first round opens again when the new route asks for it.
    told = play_route(mara, "Mara", clock)
    assert told[1]["seconds"] == 3.0


def test_a_second_round_can_be_played_to_its_own_ranking(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play_route(mara, "Mara", clock)
    play_route(tiago, "Tiago", clock)
    news(mara)
    start(players)
    clock.wait(10)
    play_route(tiago, "Tiago", clock)
    told = play_route(mara, "Mara", clock)
    assert told[3] == result(False, (1, "Tiago", 13.0, 3), (2, "Mara", 16.0, 3))


def test_after_the_end_a_new_player_can_join_and_plays_the_next_round(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    ines = player(connect, "Ines")
    assert ask(ines, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    clock.wait(180)
    call_tick(players["Mara"])
    for connection in players.values():
        wait_for_news(connection)
    assert ask(ines, {"type": "join_lobby", "code": code})["phase"] == "lobby"
    players["Ines"] = ines
    for connection in players.values():
        news(connection)
    told = start(players)
    assert told["Ines"][2] == progress(180, ("Mara", 0), ("Tiago", 0), ("Ines", 0))


# Leaving during the Duel


def test_a_player_who_leaves_disappears_from_the_progress_and_the_round_goes_on(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play(tiago, "Tiago", 2, clock)
    news(mara), news(ines)
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    for connection in (mara, ines):
        told = wait_for_news(connection, "duel_progress")
        assert types_of(told) == ["lobby_state", "duel_progress"]
        assert told[0]["phase"] == "round"
        assert told[1] == progress(179, ("Mara", 0), ("Ines", 0))
        assert news(connection) == []  # and nothing after it
    assert news(tiago) == []  # the leaver hears nothing more of the Duel
    assert lobby_named("Mara").phase == "round"


def test_a_player_who_disconnects_disappears_from_the_progress(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    players["Ines"].close()
    for name in ("Mara", "Tiago"):
        told = wait_for_news(players[name], "duel_progress")
        assert told[-1] == progress(180, ("Mara", 0), ("Tiago", 0))


def test_a_player_who_logs_out_disappears_from_the_progress(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    players["Ines"].send_json({"type": "log_out"})
    assert news(players["Ines"]) == [{"type": "signed_out"}]
    assert news(players["Mara"])[-1] == progress(180, ("Mara", 0), ("Tiago", 0))


def test_a_player_replaced_by_a_newer_log_in_is_taken_out_of_the_duel(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    newer = connect()
    assert ask(newer, {"type": "log_in", "name": "Ines", "password": PASSWORD})["type"] == "signed_in"
    # The server answers the log-in first and takes the old connection out after it.
    assert wait_for_news(players["Mara"], "duel_progress")[-1] == progress(180, ("Mara", 0), ("Tiago", 0))
    assert the_duel_of("Mara").names() == ["Mara", "Tiago"]
    # The new connection is outside the lobby and hears nothing of the Duel.
    assert news(newer) == []


def test_when_the_host_leaves_the_next_player_is_host_and_the_duel_goes_on(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    for connection in (tiago, ines):
        told = wait_for_news(connection, "duel_progress")
        assert types_of(told) == ["notice", "lobby_state", "duel_progress"]
        assert told[0]["message"] == "The host left. Tiago is the new host."
        assert told[1]["host"] == "Tiago" and told[1]["phase"] == "round"
        assert told[2] == progress(180, ("Tiago", 0), ("Ines", 0))
    # The new host cannot start a round over the running one, but can after it.
    assert ask(tiago, {"type": "start_game"}) == ROUND_RUNNING
    play_route(tiago, "Tiago", clock)
    play_route(ines, "Ines", clock)
    news(tiago)
    assert types_of(start({"Tiago": tiago, "Ines": ines})["Ines"]) == ["lobby_state", "duel_state", "duel_progress"]


def test_the_round_ends_when_the_only_player_still_running_leaves(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    play_route(mara, "Mara", clock)
    clock.wait(10)
    play_route(ines, "Ines", clock)
    news(mara), news(tiago)
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    expected = result(False, (1, "Mara", 3.0, 3), (2, "Ines", 16.0, 3))
    for connection in (mara, ines):
        told = wait_for_the_open_lobby(connection)
        # In this order: the leave, the progress without the leaver, the ranking, the open lobby.
        assert types_of(told) == ["lobby_state", "duel_progress", "duel_result", "lobby_state"]
        assert told[0]["phase"] == "round"
        assert told[1] == progress(164, ("Mara", 3), ("Ines", 3))
        assert told[2] == expected
        assert told[3]["phase"] == "lobby" and [listed["name"] for listed in told[3]["players"]] == ["Mara", "Ines"]
        assert news(connection) == []  # the end is told once


def test_a_duel_goes_on_for_a_single_player_and_ends_when_that_player_finishes(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert wait_for_news(mara, "duel_progress")[-1] == progress(180, ("Mara", 0))
    assert lobby_named("Mara").phase == "round"
    told = play_route(mara, "Mara", clock)
    assert told[-2] == result(False, (1, "Mara", 3.0, 3))
    assert told[-1]["phase"] == "lobby"


def test_a_duel_of_a_single_player_ends_when_the_time_is_up(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    players["Tiago"].close()
    wait_for_news(mara, "duel_progress")
    play(mara, "Mara", 3, clock)
    news(mara)
    clock.wait(180)
    call_tick(mara)
    assert wait_for_news(mara)[0] == result(True, (1, "Mara", None, 1))


def test_when_everybody_leaves_the_lobby_and_its_duel_are_gone(connect, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    for connection in players.values():
        connection.send_json({"type": "leave_lobby"})
        assert news(connection)[-1] == {"type": "left_lobby"}
    assert app.state.lobbies.count() == 0
    for connection in players.values():
        assert news(connection) == []


def test_a_leaver_with_a_task_open_disturbs_nobody(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    put_at_station("Tiago", 2)
    open_station(players["Tiago"], 2)
    assert ask(players["Tiago"], {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert types_of(wait_for_news(players["Mara"], "duel_progress")) == ["lobby_state", "duel_progress"]
    assert play(players["Mara"], "Mara", 3, clock)[0] == protocol.station_done(3)


# Faults after the count (M2-4.7a): counted and told belong together


def assert_the_station_is_still_open_for_the_player(connection, name, station, clock):
    """Neither the frame nor the Duel counts the station, and the player can play it again."""
    lobby = lobby_named(name)
    assert station not in lobby.tasks.finished_by(name)
    assert lobby.duel.next_station(name) == station
    assert not lobby.tasks.has_open_task(name)
    told = play(connection, name, station, clock)
    assert told[0] == protocol.station_done(station)
    assert told[1]["done"] == lobby.duel.state_of(name)[1]


def test_a_fault_in_the_duels_count_leaves_the_station_uncounted_and_playable(connect, clock, fixed_routes, monkeypatch):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]

    def broken(self, name, station, now):
        raise ValueError("the Duel could not count")

    with monkeypatch.context() as patched:
        patched.setattr(duel.Duel, "station_done", broken)
        assert play_until_the_answer(mara, "Mara", 3, clock) == [TASK_FAILED]
    assert the_duel_of("Mara").state_of("Mara") == (3, 0, None)
    assert news(tiago) == []  # nobody was told a count that did not happen
    assert_the_station_is_still_open_for_the_player(mara, "Mara", 3, clock)


def play_until_the_answer(connection, name, station, clock):
    news(connection)
    put_at_station(name, station)
    assert open_station(connection, station) == opened(station)
    clock.wait(1)
    connection.send_json({"type": "finish_station"})
    return [message for message in news(connection) if message["type"] != "duel_progress"]


def test_a_fault_after_the_duel_counted_takes_the_count_back(connect, clock, fixed_routes, monkeypatch):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]

    def broken(*values):
        raise ValueError("the answer could not be built")

    with monkeypatch.context() as patched:
        patched.setattr(protocol, "duel_state", broken)
        assert play_until_the_answer(mara, "Mara", 3, clock) == [TASK_FAILED]
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Tiago", 0)]
    # Whatever Tiago was told, it does not say that Mara has a station done.
    for message in news(tiago):
        assert message == progress(179, ("Mara", 0), ("Tiago", 0))
    assert_the_station_is_still_open_for_the_player(mara, "Mara", 3, clock)


def test_a_fault_while_building_station_done_takes_the_count_back(connect, clock, fixed_routes, monkeypatch):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]

    def broken(station):
        raise ValueError("the answer could not be built")

    with monkeypatch.context() as patched:
        patched.setattr(protocol, "station_done", broken)
        assert play_until_the_answer(mara, "Mara", 3, clock) == [TASK_FAILED]
    assert_the_station_is_still_open_for_the_player(mara, "Mara", 3, clock)


def test_a_fault_at_the_third_station_sets_no_time_and_does_not_end_the_round(connect, clock, fixed_routes, monkeypatch):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    play_route(tiago, "Tiago", clock)  # Mara's finish would end the round
    play(mara, "Mara", 3, clock)
    play(mara, "Mara", 1, clock)

    def broken(*values):
        raise ValueError("the answer could not be built")

    with monkeypatch.context() as patched:
        patched.setattr(protocol, "duel_state", broken)
        assert play_until_the_answer(mara, "Mara", 5, clock) == [TASK_FAILED]
    assert the_duel_of("Mara").state_of("Mara") == (5, 2, None)
    assert lobby_named("Mara").phase == "round"
    assert "duel_result" not in types_of(news(tiago))
    # Played again, it counts, with the time of the second try.
    told = play(mara, "Mara", 5, clock)
    assert told[1] == state(None, 3, 7.0)
    assert told[3] == result(False, (1, "Tiago", 3.0, 3), (2, "Mara", 7.0, 3))


def test_a_fault_while_telling_the_others_leaves_the_player_told_and_connected(connect, clock, fixed_routes, monkeypatch, caplog):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]

    def broken(*values):
        raise ValueError("secret detail")

    with monkeypatch.context() as patched:
        patched.setattr(protocol, "duel_progress", broken)
        # The player's own answers were complete before the fault: counted and told.
        assert play(mara, "Mara", 3, clock) == [protocol.station_done(3), state(1, 1)]
    assert "ValueError" in caplog.text and "secret detail" not in caplog.text
    assert the_duel_of("Mara").state_of("Mara") == (1, 1, None)
    # The next count tells everybody the whole truth again.
    assert play(mara, "Mara", 1, clock)[-1] == progress(178, ("Mara", 2), ("Tiago", 0))
    assert news(tiago) == [progress(178, ("Mara", 2), ("Tiago", 0))]


def test_a_fault_in_the_check_for_the_end_does_not_stop_the_tick(connect, clock, fixed_routes, monkeypatch, caplog):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    clock.wait(180)

    def broken(ranking, time_up):
        raise ValueError("secret detail")

    with monkeypatch.context() as patched:
        patched.setattr(protocol, "duel_result", broken)
        call_tick(mara)  # does not raise
        told = wait_for_news(mara)
    assert "ValueError" in caplog.text and "secret detail" not in caplog.text
    # The round is over all the same, and the browsers are told so: nobody
    # is kept in a round without an end.
    assert types_of(told) == ["lobby_state"] and told[0]["phase"] == "lobby"
    assert lobby_named("Mara").phase == "lobby"
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
