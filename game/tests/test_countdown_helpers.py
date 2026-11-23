"""The helpers that start a round without its countdown (countdown_helpers.py, M2-2.5).

They exist so that tests of the round itself need not wait five seconds. A
round started with them must look exactly like one that the tick started
after a real countdown: these tests compare the two.
"""

from countdown_helpers import no_countdown, start_round_at_once  # noqa: F401
from server import main, protocol
from server.net.lobbies import Lobbies
from task_helpers import ask, client, clock, connect, lobby_named, player  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import (
    FIXED_ROUTES,
    REAL_TICK,
    lobby_of,
    news,
    progress,
    state,
    types_of,
    wait_for_news,
)

NOT_HOST = protocol.rejection("not_host")
ROUND_RUNNING = protocol.rejection("round_running")
FIRST, SECOND = protocol.CHARACTERS[:2]


def lobby_with(*names):
    lobbies = Lobbies()
    lobbies.create(names[0], lambda: "ABCD")
    for name in names[1:]:
        lobbies.join(name, "ABCD")
    return lobbies


# The plain rules


def test_start_round_at_once_leaves_a_running_round_with_everybody_on_the_way_to_the_spawn():
    lobbies = lobby_with("Mara", "Tiago")
    lobby, rejection_code = start_round_at_once(lobbies, "Mara")
    assert rejection_code is None and lobby is lobbies.find("ABCD")
    assert lobby.round_is_running() and lobby.round_starts_at is None


def test_start_round_at_once_passes_on_every_rejection():
    lobbies = lobby_with("Mara")
    lobbies.choose_mode("Mara", "duel")  # a new lobby is in Solo (S-203); Duel needs two
    assert start_round_at_once(lobbies, "Tiago") == (None, "not_in_lobby")
    assert start_round_at_once(lobbies, "Mara") == (None, "too_few_players")
    lobbies.join("Tiago", "ABCD")
    assert start_round_at_once(lobbies, "Tiago") == (None, "not_host")
    assert start_round_at_once(lobbies, "Mara")[1] is None
    assert start_round_at_once(lobbies, "Mara") == (None, "round_running")


# Over the WebSocket


def test_with_no_countdown_the_start_tells_everybody_the_round_and_nothing_of_a_countdown(connect, fixed_routes):
    players, code = lobby_of(connect, ["Mara", "Tiago"])
    players["Mara"].send_json({"type": "start_game"})
    listed = [("Mara", FIRST), ("Tiago", SECOND)]
    for place, name in enumerate(players):
        assert news(players[name]) == [
            protocol.lobby_state(code, "Mara", listed, "duel", "round"),
            state(FIXED_ROUTES[place][0], 0),
            progress(180, ("Mara", 0), ("Tiago", 0)),
        ]
    lobby = lobby_named("Mara")
    assert lobby.phase == "round" and lobby.round_starts_at is None
    assert lobby.tasks is not None and lobby.duel is not None


def test_the_stand_in_and_the_real_countdown_send_the_same_messages_about_the_round(
    connect, clock, fixed_routes, monkeypatch
):
    # First lobby: the stand-in of `no_countdown`.
    codes = iter(["AAAA", "BBBB"])
    monkeypatch.setattr(main, "pick_lobby_code", lambda: next(codes))
    quick, _ = lobby_of(connect, ["Mara", "Tiago"])
    quick["Mara"].send_json({"type": "start_game"})
    told_by_stand_in = [news(connection) for connection in quick.values()]

    # Second lobby: the server's real handler, five seconds and the real tick.
    monkeypatch.setitem(main.LOBBY_HANDLERS, "start_game", main.handle_start_game)
    real, _ = lobby_of(connect, ["Ines", "Rui"])
    real["Ines"].send_json({"type": "start_game"})
    announced = [news(connection) for connection in real.values()]
    assert [types_of(messages) for messages in announced] == [["lobby_state", "countdown"]] * 2
    clock.wait(5)
    real["Ines"].portal.call(REAL_TICK, 0.0)
    told_by_server = [wait_for_news(connection, "duel_progress") for connection in real.values()]

    # The same messages in the same order, apart from the names and the lobby's code.
    assert [types_of(messages) for messages in told_by_stand_in] == [
        ["lobby_state", "duel_state", "duel_progress"]
    ] * 2
    assert renamed(told_by_stand_in) == renamed(told_by_server)


def renamed(told):
    """The messages with the players called by their place in the lobby and without the lobby's code."""
    places = {"Mara": "first", "Tiago": "second", "Ines": "first", "Rui": "second"}
    text = repr(told).replace("AAAA", "code").replace("BBBB", "code")
    for name, place in places.items():
        text = text.replace(repr(name), repr(place))
    return text


def test_with_no_countdown_the_checks_of_the_start_are_the_server_s_own(connect):
    mara = player(connect, "Mara")
    ask(mara, {"type": "create_lobby"})
    ask(mara, {"type": "choose_mode", "mode": "duel"})  # a new lobby is in Solo (S-203); Duel needs two
    assert ask(mara, {"type": "start_game"})["code"] == "too_few_players"
    tiago = player(connect, "Tiago")
    ask(tiago, {"type": "join_lobby", "code": lobby_named("Mara").code})
    news(mara)
    assert ask(tiago, {"type": "start_game"}) == NOT_HOST
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    news(mara)
    assert ask(mara, {"type": "start_game"}) == ROUND_RUNNING
