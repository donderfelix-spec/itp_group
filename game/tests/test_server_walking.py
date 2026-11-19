"""Walking on the campus over the WebSocket: the tick, the `move` message, who gets positions.

The tick runs about 15 times per second in the background. These tests never
count ticks: they wait, with a generous deadline, until the server has sent
what they expect.
"""

import asyncio
import contextlib
import math
import time

import pytest
from fastapi.testclient import TestClient

from server import main
from server.main import app
from server.world.movement import PLAYER_HALF_SIZE

PASSWORD = "password123"
SPAWN_X = app.state.campus["spawn"]["x"]
SPAWN_Y = app.state.campus["spawn"]["y"]
AT_THE_SPAWN = {"x": SPAWN_X, "y": SPAWN_Y}

# Long enough for several ticks. Used only to see that nothing more arrives.
QUIET_SECONDS = 0.4


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture
def client():
    # Used as a context manager, the test client starts the server properly
    # (so the tick loop runs) and keeps all connections in one event loop.
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def waiting_messages(connection):
    """Everything the server has sent this player and the test has not read yet.

    A hello is sent and everything up to its answer is collected. So this
    never waits forever, even when nothing was sent.
    """
    connection.send_json({"type": "hello", "name": "Mara"})
    messages = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return messages
        messages.append(message)


def waiting_positions(connection):
    """The unread `positions` messages of this player, as {name: {"x", "y"}} dicts."""
    return [
        {listed["name"]: {"x": listed["x"], "y": listed["y"]} for listed in message["players"]}
        for message in waiting_messages(connection)
        if message["type"] == "positions"
    ]


def wait_for_positions(connection, wanted, seconds=5.0):
    """Read this player's messages until a `positions` message fits. Returns it as a dict.

    `wanted` is a function that takes {name: {"x", "y"}} and says yes or no.
    """
    deadline = time.monotonic() + seconds
    while True:
        for positions in waiting_positions(connection):
            if wanted(positions):
                return positions
        assert time.monotonic() < deadline, "the expected positions did not arrive in time"
        time.sleep(0.02)


def wait_until_quiet(connection, seconds=5.0):
    """Wait until no positions arrive any more. Returns the last ones that did (or None)."""
    deadline = time.monotonic() + seconds
    last = None
    waiting_before = waiting_positions(connection)
    while True:
        if waiting_before:
            last = waiting_before[-1]
        time.sleep(QUIET_SECONDS)
        arrived_meanwhile = waiting_positions(connection)
        if not arrived_meanwhile:
            return last
        assert time.monotonic() < deadline, "the positions did not stop arriving"
        waiting_before = arrived_meanwhile


def gets_no_positions(connection) -> bool:
    """True if several ticks pass without a `positions` message for this player."""
    time.sleep(QUIET_SECONDS)
    return waiting_positions(connection) == []


def answer_of_type(connection, message, wanted_type):
    """Send a message and return the server's answer of this type.

    A walking player gets `positions` all the time, so one of them may arrive
    before the answer. Returns `(answer, messages_that_came_before_it)`.
    """
    connection.send_json(message)
    earlier = []
    while True:
        answer = connection.receive_json()
        if answer["type"] == wanted_type:
            return answer, earlier
        earlier.append(answer)


def player(connect, name):
    """A new connection, signed in with a new account of this name."""
    connection = connect()
    answer = ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})
    assert answer["type"] == "signed_in"
    return connection


def create(connection) -> str:
    """Create a lobby and return its code."""
    return ask(connection, {"type": "create_lobby"})["code"]


def join(connection, code):
    connection.send_json({"type": "join_lobby", "code": code})


def move(connection, dx, dy):
    connection.send_json({"type": "move", "dx": dx, "dy": dy})


def mara_and_tiago_at_the_spawn(connect):
    """Mara creates a lobby, Tiago joins, and both have been told that both stand at the spawn."""
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = create(mara)
    join(tiago, code)
    both_at_the_spawn = lambda positions: positions == {"Mara": AT_THE_SPAWN, "Tiago": AT_THE_SPAWN}
    wait_for_positions(mara, both_at_the_spawn)
    wait_for_positions(tiago, both_at_the_spawn)
    return mara, tiago, code


# Appearing


def test_the_creator_of_a_lobby_is_told_where_they_stand(connect):
    mara = player(connect, "Mara")
    create(mara)
    assert wait_for_positions(mara, lambda positions: True) == {"Mara": AT_THE_SPAWN}


def test_after_a_join_both_get_both_names_at_the_spawn(connect):
    mara_and_tiago_at_the_spawn(connect)  # The waiting in there is the check.


def test_the_positions_message_has_only_names_and_finite_numbers(connect):
    mara = player(connect, "Mara")
    create(mara)
    move(mara, 1, 1)
    deadline = time.monotonic() + 5
    found = []
    while not found:
        found = [message for message in waiting_messages(mara) if message["type"] == "positions"]
        assert time.monotonic() < deadline
    for message in found:
        assert set(message) == {"type", "players"}
        for listed in message["players"]:
            assert set(listed) == {"name", "x", "y"}
            assert math.isfinite(listed["x"]) and math.isfinite(listed["y"])


# Walking


def test_a_walking_player_is_seen_moving_by_both(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    move(mara, 1, 0)
    mara_went_right = lambda positions: positions["Mara"]["x"] > SPAWN_X
    for connection in (mara, tiago):
        # On a fast machine this takes about a tick. The deadline is generous
        # so that a slow machine does not fail the test.
        seen = wait_for_positions(connection, mara_went_right)
        assert seen["Mara"]["y"] == SPAWN_Y
        assert seen["Tiago"] == AT_THE_SPAWN


def test_the_direction_stays_without_further_messages(connect):
    mara = player(connect, "Mara")
    create(mara)
    move(mara, -1, 0)
    first = wait_for_positions(mara, lambda positions: positions["Mara"]["x"] < SPAWN_X)
    wait_for_positions(mara, lambda positions: positions["Mara"]["x"] < first["Mara"]["x"])


def test_a_player_who_stops_stays_and_the_positions_stop_coming(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    move(mara, 1, 0)
    seen_by_mara = wait_for_positions(mara, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    move(mara, 0, 0)
    # If Mara stopped at once, the positions she has just read were the last.
    last_for_mara = wait_until_quiet(mara) or seen_by_mara
    last_for_tiago = wait_until_quiet(tiago)
    # Both know the same final spot, to the right of the spawn.
    assert last_for_mara == last_for_tiago
    assert last_for_mara["Mara"]["x"] > SPAWN_X
    assert last_for_mara["Tiago"] == AT_THE_SPAWN
    assert gets_no_positions(mara)
    assert gets_no_positions(tiago)


def test_an_idle_lobby_gets_no_positions(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    assert gets_no_positions(mara)
    assert gets_no_positions(tiago)


def test_a_player_stops_at_the_wall_of_the_deck(connect):
    mara = player(connect, "Mara")
    create(mara)
    move(mara, 1, 0)
    # Mara keeps walking right, so the positions only stop when a wall stops her.
    last = wait_until_quiet(mara, seconds=10.0)
    # Her right edge touches the wall, so her centre is half a player before it.
    wall = next(solid for solid in app.state.campus["solids"] if solid["id"] == "deck-wall-right")
    assert last["Mara"] == {"x": wall["x"] - PLAYER_HALF_SIZE, "y": SPAWN_Y}


# Rejections


def test_move_when_signed_out_is_rejected(connect):
    stranger = connect()
    assert ask(stranger, {"type": "move", "dx": 1, "dy": 0}) == {
        "type": "error",
        "code": "not_signed_in",
        "message": "Log in or play as a guest first.",
    }
    assert ask(stranger, {"type": "guest"})["type"] == "signed_in"


def test_move_outside_a_lobby_is_rejected(connect):
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "move", "dx": 0, "dy": -1}) == {
        "type": "error",
        "code": "not_in_lobby",
        "message": "You are not in a lobby.",
    }
    assert ask(mara, {"type": "create_lobby"})["type"] == "lobby_state"


def test_a_valid_move_gets_no_direct_answer(connect):
    mara = player(connect, "Mara")
    create(mara)
    wait_until_quiet(mara)
    move(mara, 0, 0)  # Standing still: no answer and no new positions either.
    assert waiting_messages(mara) == []


def test_a_move_that_is_not_a_direction_is_refused_by_the_message_check(connect):
    mara = player(connect, "Mara")
    create(mara)
    wait_until_quiet(mara)
    assert ask(mara, {"type": "move", "dx": 5, "dy": 0})["type"] == "error"
    assert gets_no_positions(mara)


def test_after_leaving_a_move_is_rejected(connect):
    mara = player(connect, "Mara")
    create(mara)
    wait_until_quiet(mara)
    assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert ask(mara, {"type": "move", "dx": 1, "dy": 0})["code"] == "not_in_lobby"


# Who gets which positions


def test_another_lobby_never_gets_these_positions(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    ines = player(connect, "Ines")
    create(ines)
    assert wait_for_positions(ines, lambda positions: True) == {"Ines": AT_THE_SPAWN}

    move(mara, 1, 0)
    wait_for_positions(tiago, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    move(mara, 0, 0)
    wait_until_quiet(mara)
    # While Mara walked, nothing changed in the lobby of Ines.
    assert waiting_messages(ines) == []
    # And Mara and Tiago never hear of Ines.
    move(ines, 0, 1)
    wait_for_positions(ines, lambda positions: positions["Ines"]["y"] > SPAWN_Y)
    assert waiting_messages(mara) == []
    assert waiting_messages(tiago) == []


def test_a_signed_in_player_without_a_lobby_gets_no_positions(connect):
    mara = player(connect, "Mara")
    ines = player(connect, "Ines")
    create(mara)
    move(mara, 1, 0)
    wait_for_positions(mara, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    assert waiting_messages(ines) == []


def test_after_a_member_left_the_other_gets_positions_without_them(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    assert wait_for_positions(mara, lambda positions: "Tiago" not in positions) == {"Mara": AT_THE_SPAWN}

    move(mara, 1, 0)
    wait_for_positions(mara, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    assert waiting_messages(tiago) == []


def test_after_a_member_closed_the_page_the_other_gets_positions_without_them(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    tiago.close()
    assert wait_for_positions(mara, lambda positions: "Tiago" not in positions) == {"Mara": AT_THE_SPAWN}


def test_someone_who_comes_back_starts_at_the_spawn_again(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    move(tiago, 0, 1)
    wait_for_positions(tiago, lambda positions: positions["Tiago"]["y"] > SPAWN_Y)
    # Tiago leaves while still walking, so positions may arrive before the answer.
    answer_of_type(tiago, {"type": "leave_lobby"}, "left_lobby")
    wait_for_positions(mara, lambda positions: "Tiago" not in positions)

    join(tiago, code)
    wait_for_positions(mara, lambda positions: positions.get("Tiago") == AT_THE_SPAWN)
    assert gets_no_positions(mara)  # Tiago stands still: the old direction is gone too.


def test_after_a_log_out_the_player_is_gone_and_gets_no_positions(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    assert ask(mara, {"type": "log_out"}) == {"type": "signed_out"}
    assert wait_for_positions(tiago, lambda positions: "Mara" not in positions) == {"Tiago": AT_THE_SPAWN}

    move(tiago, 1, 0)
    wait_for_positions(tiago, lambda positions: positions["Tiago"]["x"] > SPAWN_X)
    assert waiting_messages(mara) == []
    assert ask(mara, {"type": "move", "dx": 1, "dy": 0})["code"] == "not_signed_in"


def test_after_a_log_in_elsewhere_the_old_connection_is_gone_and_gets_no_positions(connect):
    old_mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    new_mara = connect()
    answer = ask(new_mara, {"type": "log_in", "name": "Mara", "password": PASSWORD})
    assert answer["type"] == "signed_in"
    assert old_mara.receive_json() == {"type": "signed_out"}
    assert wait_for_positions(tiago, lambda positions: "Mara" not in positions) == {"Tiago": AT_THE_SPAWN}

    move(tiago, 1, 0)
    wait_for_positions(tiago, lambda positions: positions["Tiago"]["x"] > SPAWN_X)
    # Neither connection of Mara is in the lobby, so neither hears of Tiago's walk.
    assert waiting_messages(old_mara) == []
    assert waiting_messages(new_mara) == []
    assert ask(old_mara, {"type": "move", "dx": 1, "dy": 0})["code"] == "not_signed_in"
    assert ask(new_mara, {"type": "move", "dx": 1, "dy": 0})["code"] == "not_in_lobby"


def test_the_host_leaves_while_somebody_walks(connect):
    mara, tiago, code = mara_and_tiago_at_the_spawn(connect)
    move(tiago, 1, 0)
    wait_for_positions(tiago, lambda positions: positions["Tiago"]["x"] > SPAWN_X)
    answer_of_type(mara, {"type": "leave_lobby"}, "left_lobby")

    # Tiago gets the notice, the new state and positions without Mara. Lobby
    # messages and positions are sent independently, so the test collects
    # until all three are there and does not expect an order between them.
    notices, states, positions_without_mara = [], [], []
    deadline = time.monotonic() + 5
    while not (notices and states and positions_without_mara):
        assert time.monotonic() < deadline, "Tiago was not told everything in time"
        for message in waiting_messages(tiago):
            if message["type"] == "notice":
                notices.append(message)
            elif message["type"] == "lobby_state":
                states.append(message)
            elif [listed["name"] for listed in message["players"]] == ["Tiago"]:
                positions_without_mara.append(message)
    assert notices == [{"type": "notice", "message": "The host left. Tiago is the new host."}]
    assert len(states) == 1
    assert states[0]["host"] == "Tiago"
    assert [listed["name"] for listed in states[0]["players"]] == ["Tiago"]
    # Tiago is still walking, and Mara hears nothing of it.
    last_x = positions_without_mara[-1]["players"][0]["x"]
    wait_for_positions(tiago, lambda positions: positions["Tiago"]["x"] > last_x)
    assert waiting_messages(mara) == []


# Without the tick loop


def test_without_the_tick_loop_the_server_still_answers():
    # `TestClient(app)` without `with` does not start the tick loop.
    with TestClient(app).websocket_connect("/ws") as mara:
        assert ask(mara, {"type": "guest"})["type"] == "signed_in"
        assert ask(mara, {"type": "create_lobby"})["type"] == "lobby_state"
        move(mara, 1, 0)
        assert waiting_messages(mara) == []
        assert ask(mara, {"type": "leave_lobby"}) == {"type": "left_lobby"}


# Slow members and failing ticks. These call the server's functions directly
# with stand-ins for the WebSockets, because a real test connection cannot get
# stuck at an exact moment.


class FakeWebSocket:
    """Stands in for a WebSocket and remembers what the server sent to it."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self):
        self.closed = True


class StuckWebSocket(FakeWebSocket):
    """A browser that has stopped reading: a send to it never returns."""

    def __init__(self):
        super().__init__()
        self.sends_started = 0

    async def send_json(self, message):
        self.sends_started += 1
        await asyncio.Event().wait()  # Nobody ever sets this event.


def fake_lobby(**websockets):
    """Sign the stand-ins in under their names and put them in one lobby, in order."""
    names = list(websockets)
    for name, websocket in websockets.items():
        app.state.sessions.sign_in_account(websocket, name)
    lobby, rejection_code = app.state.lobbies.create(names[0], lambda: "ABCD")
    for name in names[1:]:
        app.state.lobbies.join(name, "ABCD")
    return lobby


async def a_few_ticks(count=5):
    """Run the tick a few times, each time letting the started sends run."""
    for number in range(count):
        main.tick(0.05)
        await asyncio.sleep(0.01)


def x_of(message, name):
    for listed in message["players"]:
        if listed["name"] == name:
            return listed["x"]


def test_the_tick_runs_15_times_per_second():
    assert main.TICKS_PER_SECOND == 15


def test_a_member_whose_send_never_returns_does_not_stop_the_tick():
    mara, tiago = StuckWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago)
    lobby.walkers.set_direction("Tiago", 1, 0)

    started = time.monotonic()
    asyncio.run(a_few_ticks(5))
    seconds = time.monotonic() - started

    # Tiago got the positions of every tick, each further right than the one before.
    assert len(tiago.sent) == 5
    xs = [x_of(message, "Tiago") for message in tiago.sent]
    assert xs == sorted(xs) and xs[0] < xs[-1]
    # Mara is still busy with her first message and was skipped after that.
    assert mara.sends_started == 1
    # Nobody waited for the time limit of a send.
    assert seconds < main.SEND_TIMEOUT_SECONDS


def test_a_stuck_member_is_closed_after_the_time_limit(monkeypatch):
    monkeypatch.setattr(main, "SEND_TIMEOUT_SECONDS", 0.05)
    mara, tiago = StuckWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)

    async def one_tick_and_a_wait():
        main.tick(0.05)
        deadline = time.monotonic() + 5
        while (not mara.closed or main.taking_positions) and time.monotonic() < deadline:
            await asyncio.sleep(0.01)

    asyncio.run(one_tick_and_a_wait())
    assert mara.closed
    assert not tiago.closed
    assert main.taking_positions == set()


def test_a_member_who_was_busy_gets_the_newest_positions_later():
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago)

    async def tiago_walks_while_mara_is_busy():
        main.taking_positions.add(mara)  # As if Mara were still taking an older message.
        lobby.walkers.set_direction("Tiago", 1, 0)
        await a_few_ticks(3)
        lobby.walkers.set_direction("Tiago", 0, 0)
        assert mara.sent == []
        main.taking_positions.discard(mara)
        await a_few_ticks(3)  # Nobody moves now, but Mara is still owed the news.

    asyncio.run(tiago_walks_while_mara_is_busy())
    assert len(mara.sent) == 1
    assert mara.sent[0] == tiago.sent[-1]
    assert x_of(mara.sent[0], "Tiago") > SPAWN_X


def test_a_member_whose_send_fails_does_not_stop_the_others():
    class BrokenWebSocket(FakeWebSocket):
        async def send_json(self, message):
            raise RuntimeError("the connection is gone")

    tiago = FakeWebSocket()
    fake_lobby(Mara=BrokenWebSocket(), Tiago=tiago)
    asyncio.run(a_few_ticks(1))
    assert len(tiago.sent) == 1


def test_someone_who_left_right_after_the_tick_gets_no_positions():
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)

    async def tiago_leaves_before_the_send_starts():
        main.tick(0.05)
        app.state.lobbies.leave("Tiago")
        await asyncio.sleep(0.01)

    asyncio.run(tiago_leaves_before_the_send_starts())
    assert len(mara.sent) == 1
    assert tiago.sent == []


def test_fake_lobbies_only_get_their_own_positions():
    mara, ines = FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara)
    app.state.sessions.sign_in_account(ines, "Ines")
    app.state.lobbies.create("Ines", lambda: "WXYZ")
    asyncio.run(a_few_ticks(2))
    assert [listed["name"] for listed in mara.sent[0]["players"]] == ["Mara"]
    assert [listed["name"] for listed in ines.sent[0]["players"]] == ["Ines"]
    assert len(mara.sent) == 1 and len(ines.sent) == 1


def test_a_failing_lobby_does_not_stop_the_next_lobby(monkeypatch, caplog):
    mara, ines = FakeWebSocket(), FakeWebSocket()
    broken_lobby = fake_lobby(Mara=mara)
    app.state.sessions.sign_in_account(ines, "Ines")
    healthy_lobby, rejection_code = app.state.lobbies.create("Ines", lambda: "WXYZ")
    # The broken lobby comes first, so the tick meets the fault before the healthy lobby.
    assert app.state.lobbies.all() == [broken_lobby, healthy_lobby]

    def broken_advance(seconds, campus):
        raise ValueError("secret detail that must not be logged")

    monkeypatch.setattr(broken_lobby.walkers, "advance", broken_advance)
    healthy_lobby.walkers.set_direction("Ines", 1, 0)

    with caplog.at_level("ERROR"):
        asyncio.run(a_few_ticks(3))

    # Ines was moved and told at every tick, although the lobby before hers failed.
    xs = [x_of(message, "Ines") for message in ines.sent]
    assert len(xs) == 3
    assert SPAWN_X < xs[0] < xs[1] < xs[2]
    assert mara.sent == []
    assert "ValueError" in caplog.text
    assert "secret detail" not in caplog.text


def test_a_failing_tick_does_not_end_the_loop(monkeypatch, caplog):
    calls = []

    def tick_that_fails_once(seconds):
        calls.append(seconds)
        if len(calls) == 1:
            raise ValueError("secret detail that must not be logged")

    monkeypatch.setattr(main, "tick", tick_that_fails_once)

    async def run_the_loop_until_three_ticks():
        loop = asyncio.create_task(main.run_ticks())
        deadline = time.monotonic() + 5
        while len(calls) < 3 and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        still_running = not loop.done()
        loop.cancel()
        return still_running

    with caplog.at_level("ERROR"):
        assert asyncio.run(run_the_loop_until_three_ticks())
    assert len(calls) >= 3
    # The time since the previous tick is passed in, and it is a real, small time.
    assert all(0 < seconds < 5 for seconds in calls)
    # Only the class of the error is logged.
    assert "ValueError" in caplog.text
    assert "secret detail" not in caplog.text


def test_the_tick_loop_stops_with_the_server():
    with TestClient(app):
        pass
    # Leaving the block stopped the server. Reaching this line means the loop
    # was cancelled cleanly: otherwise the block above would hang or raise.
