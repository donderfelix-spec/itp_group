"""The play test of milestone M1 "Walking" (to-do M1-2.4), as repeatable tests.

What a tester played by hand in several browser tabs is played here by several
WebSocket connections against the real server with the real tick: three
players in one lobby who walk in different directions, walls that stop them,
people outside the lobby who must hear nothing, and the messages of DESIGN.md,
section 9, that the milestone asks for.

No test counts ticks. Each one waits, with a generous deadline, until the
server has sent what it expects.
"""

import contextlib
import time

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.world.movement import PLAYER_HALF_SIZE, is_free

PASSWORD = "password123"
SPAWN_X = app.state.campus["spawn"]["x"]
SPAWN_Y = app.state.campus["spawn"]["y"]
AT_THE_SPAWN = {"x": SPAWN_X, "y": SPAWN_Y}

# Generous: a walk across the whole deck takes about two seconds.
DEADLINE_SECONDS = 15.0
# Long enough for several ticks. Used only to see that nothing more arrives.
QUIET_SECONDS = 0.4


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


@pytest.fixture
def client():
    # As a context manager the test client starts the server properly, so the tick loop runs.
    with TestClient(app) as shared_client:
        yield shared_client


@pytest.fixture
def connect(client):
    """A function that opens one more connection. All of them are closed after the test."""
    with contextlib.ExitStack() as open_connections:
        yield lambda: open_connections.enter_context(client.websocket_connect("/ws"))


# Helpers


def ask(connection, message):
    """Send one message and return the next message the server sends."""
    connection.send_json(message)
    return connection.receive_json()


def waiting_messages(connection):
    """Everything the server has sent this connection and the test has not read yet.

    A hello is sent and everything up to its answer is collected, so this
    never waits forever, even when nothing was sent. `hello` is answered for
    every connection, signed in or not.
    """
    connection.send_json({"type": "hello", "name": "Reader"})
    messages = []
    while True:
        message = connection.receive_json()
        if message["type"] == "welcome":
            return messages
        messages.append(message)


def as_positions(messages):
    """The `positions` messages among these, as {name: {"x", "y"}} dicts."""
    return [
        {listed["name"]: {"x": listed["x"], "y": listed["y"]} for listed in message["players"]}
        for message in messages
        if message["type"] == "positions"
    ]


def wait_for_positions(connection, wanted, seen=None):
    """Read this player's messages until a `positions` message fits. Returns it as a dict.

    `wanted` takes {name: {"x", "y"}} and says yes or no. Every positions
    message read on the way is added to the list `seen`, if one is given.
    """
    deadline = time.monotonic() + DEADLINE_SECONDS
    while True:
        for positions in as_positions(waiting_messages(connection)):
            if seen is not None:
                seen.append(positions)
            if wanted(positions):
                return positions
        assert time.monotonic() < deadline, "the expected positions did not arrive in time"
        time.sleep(0.02)


def read_until_quiet(connection):
    """Read this player's positions until none arrive any more. Returns all of them, in order."""
    deadline = time.monotonic() + DEADLINE_SECONDS
    everything = as_positions(waiting_messages(connection))
    while True:
        time.sleep(QUIET_SECONDS)
        arrived_meanwhile = as_positions(waiting_messages(connection))
        if not arrived_meanwhile:
            return everything
        everything.extend(arrived_meanwhile)
        assert time.monotonic() < deadline, "the positions did not stop arriving"


def account(connect, name):
    """A new connection, signed in with a new account of this name."""
    connection = connect()
    answer = ask(connection, {"type": "sign_up", "name": name, "password": PASSWORD})
    assert answer == {"type": "signed_in", "name": name, "guest": False}
    return connection


def guest(connect):
    """A new connection that entered as a guest. Returns (connection, name)."""
    connection = connect()
    answer = ask(connection, {"type": "guest"})
    assert answer["type"] == "signed_in" and answer["guest"] is True
    return connection, answer["name"]


def create(connection) -> str:
    """Create a lobby and return its code."""
    answer = ask(connection, {"type": "create_lobby"})
    assert answer["type"] == "lobby_state"
    return answer["code"]


def join(connection, code):
    connection.send_json({"type": "join_lobby", "code": code})


def move(connection, dx, dy):
    connection.send_json({"type": "move", "dx": dx, "dy": dy})


def solid(solid_id):
    return next(listed for listed in app.state.campus["solids"] if listed["id"] == solid_id)


def one_account_and_two_guests_in_a_lobby(connect):
    """Mara (account) creates a lobby, two guests join, and all three know all three stand at the spawn.

    Returns ({name: connection}, code). The names are in joining order.
    """
    mara = account(connect, "Mara")
    first_guest, first_name = guest(connect)
    second_guest, second_name = guest(connect)
    code = create(mara)
    join(first_guest, code)
    join(second_guest, code)
    players = {"Mara": mara, first_name: first_guest, second_name: second_guest}
    all_at_the_spawn = lambda positions: positions == {name: AT_THE_SPAWN for name in players}
    for connection in players.values():
        wait_for_positions(connection, all_at_the_spawn)
    return players, code


# Criterion 7, first part: three players walk three ways and each sees the other two


def test_each_of_three_players_sees_the_other_two_walk_the_right_way(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, up_name, right_name = list(players)

    move(players[mara_name], -1, 0)  # Mara walks left, towards the pool.
    move(players[up_name], 0, -1)  # The first guest walks up, towards the Canteen.
    move(players[right_name], 1, 0)  # The second guest walks right, towards the wall of the deck.

    def all_three_moved_the_right_way(positions):
        return (
            set(positions) == set(players)
            and positions[mara_name]["x"] < SPAWN_X and positions[mara_name]["y"] == SPAWN_Y
            and positions[up_name]["y"] < SPAWN_Y and positions[up_name]["x"] == SPAWN_X
            and positions[right_name]["x"] > SPAWN_X and positions[right_name]["y"] == SPAWN_Y
        )

    # EACH of the three is told, not only the one who walks.
    last_seen = [
        wait_for_positions(connection, all_three_moved_the_right_way) for connection in players.values()
    ]

    # They stop, and afterwards all three know the very same final picture.
    for connection in players.values():
        move(connection, 0, 0)
    for number, connection in enumerate(players.values()):
        # If nothing arrived after the stop, what this player read last was the final picture.
        last_seen[number] = (read_until_quiet(connection) or [last_seen[number]])[-1]
    assert last_seen[0] == last_seen[1] == last_seen[2]
    assert all_three_moved_the_right_way(last_seen[0])


def test_nobody_teleports_while_three_players_walk(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, up_name, right_name = list(players)
    move(players[mara_name], -1, 0)
    move(players[up_name], 0, -1)
    move(players[right_name], 1, 0)

    # All three walk until something stops them. Mara reads every message on the way.
    seen = read_until_quiet(players[mara_name])
    assert len(seen) > 5, "a walk across the deck is told in many small steps"

    # Each player only ever moves in the direction they chose, never back and never sideways.
    xs_of_mara = [positions[mara_name]["x"] for positions in seen]
    ys_of_up = [positions[up_name]["y"] for positions in seen]
    xs_of_right = [positions[right_name]["x"] for positions in seen]
    assert xs_of_mara == sorted(xs_of_mara, reverse=True)
    assert ys_of_up == sorted(ys_of_up, reverse=True)
    assert xs_of_right == sorted(xs_of_right)
    assert all(positions[mara_name]["y"] == SPAWN_Y for positions in seen)
    assert all(positions[up_name]["x"] == SPAWN_X for positions in seen)
    assert all(positions[right_name]["y"] == SPAWN_Y for positions in seen)

    # No step is longer than a tenth of the way they walked in the two seconds
    # or so: the browser can glide from one message to the next. (A slow
    # machine may skip a few ticks, so this is far above one normal step of 6.)
    for values in (xs_of_mara, ys_of_up, xs_of_right):
        steps = [abs(after - before) for before, after in zip(values, values[1:])]
        assert max(steps) <= 30


# Criterion 7, second part: walls


def test_walkers_stop_outside_the_pool_the_top_wall_and_the_right_wall(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, up_name, right_name = list(players)
    move(players[mara_name], -1, 0)
    move(players[up_name], 0, -1)
    move(players[right_name], 1, 0)

    # Nobody lets go of the key: only the obstacles end the walks.
    seen_by = {name: read_until_quiet(connection) for name, connection in players.items()}

    pool = solid("deck-pool")
    top_wall = solid("deck-wall-top-3")
    right_wall = solid("deck-wall-right")
    pool_edge = pool["x"] + pool["w"]
    top_wall_edge = top_wall["y"] + top_wall["h"]

    for name, seen in seen_by.items():
        # In no message that anybody got is a player inside an obstacle ...
        for positions in seen:
            assert positions[mara_name]["x"] - PLAYER_HALF_SIZE >= pool_edge
            assert positions[up_name]["y"] - PLAYER_HALF_SIZE >= top_wall_edge
            assert positions[right_name]["x"] + PLAYER_HALF_SIZE <= right_wall["x"]
        # ... and at the end each one touches theirs: not inside, not short of it.
        assert seen[-1] == {
            mara_name: {"x": pool_edge + PLAYER_HALF_SIZE, "y": SPAWN_Y},
            up_name: {"x": SPAWN_X, "y": top_wall_edge + PLAYER_HALF_SIZE},
            right_name: {"x": right_wall["x"] - PLAYER_HALF_SIZE, "y": SPAWN_Y},
        }

    # They keep pushing against the obstacles: nothing moves, so nothing is sent.
    time.sleep(QUIET_SECONDS)
    for connection in players.values():
        assert waiting_messages(connection) == []

    # Asking for the same direction again changes nothing either.
    move(players[right_name], 1, 0)
    time.sleep(QUIET_SECONDS)
    for connection in players.values():
        assert waiting_messages(connection) == []


def test_a_diagonal_walk_slides_along_a_tree_through_a_door_into_the_corner_of_the_canteen(connect):
    mara = account(connect, "Mara")
    watcher, watcher_name = guest(connect)
    code = create(mara)
    join(watcher, code)
    wait_for_positions(watcher, lambda positions: positions.get("Mara") == AT_THE_SPAWN)

    # Up and right from the spawn: the tree stops her going right, so she
    # slides up along it, walks on through the door of the Canteen, between
    # its tables, and ends in the top right corner of the room.
    move(mara, 1, -1)
    seen_by_mara = read_until_quiet(mara)
    seen_by_watcher = read_until_quiet(watcher)

    campus = app.state.campus
    for seen in (seen_by_mara, seen_by_watcher):
        # At no moment is she inside a wall, a tree, a table or anything else solid.
        for positions in seen:
            x, y = positions["Mara"]["x"], positions["Mara"]["y"]
            assert is_free(x, y, campus["solids"], campus["width"], campus["height"]), (x, y)
        # Both know the same end: touching the right wall and the top wall of the Canteen.
        right_wall = solid("canteen-wall-right")
        top_wall = solid("canteen-wall-top")
        assert seen[-1]["Mara"] == {
            "x": right_wall["x"] - PLAYER_HALF_SIZE,
            "y": top_wall["y"] + top_wall["h"] + PLAYER_HALF_SIZE,
        }

    # She really went through the door and not through the wall next to it.
    door = next(listed for listed in campus["doors"] if listed["room"] == "canteen")
    in_the_wall_line = [
        positions["Mara"]["x"] for positions in seen_by_watcher
        if door["y"] < positions["Mara"]["y"] < door["y"] + door["h"]
    ]
    assert in_the_wall_line, "she was never seen in the doorway"
    for x in in_the_wall_line:
        assert door["x"] + PLAYER_HALF_SIZE <= x <= door["x"] + door["w"] - PLAYER_HALF_SIZE


def test_nobody_reaches_the_beach(connect):
    mara = account(connect, "Mara")
    create(mara)
    move(mara, 0, 1)  # Straight down from the spawn, towards the sea.
    seen = read_until_quiet(mara)

    sand = next(band for band in app.state.campus["bands"] if band["id"] == "sand")
    assert seen[-1]["Mara"]["y"] > SPAWN_Y
    for positions in seen:
        assert positions["Mara"]["y"] + PLAYER_HALF_SIZE < sand["y"]


# Criterion 7, third part: who hears nothing


def test_nobody_outside_the_lobby_receives_anything(connect):
    # Outside: someone who is not signed in, a guest without a lobby, an
    # account without a lobby, and a guest alone in another lobby.
    stranger = connect()
    guest_at_home, guest_at_home_name = guest(connect)
    ines = account(connect, "Ines")
    in_another_lobby, another_name = guest(connect)
    other_code = create(in_another_lobby)
    assert wait_for_positions(in_another_lobby, lambda positions: True) == {another_name: AT_THE_SPAWN}
    outsiders = [stranger, guest_at_home, ines, in_another_lobby]
    for outsider in outsiders:
        assert waiting_messages(outsider) == []

    # Inside: three players join, choose, walk, stop and one of them leaves.
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    assert code != other_code
    mara_name, up_name, right_name = list(players)
    players[mara_name].send_json({"type": "choose_character", "character": "surfer"})
    move(players[mara_name], -1, 0)
    move(players[up_name], 0, -1)
    move(players[right_name], 1, 0)
    wait_for_positions(players[mara_name], lambda positions: positions[right_name]["x"] > SPAWN_X + 20)
    for outsider in outsiders:
        assert waiting_messages(outsider) == []

    players[mara_name].send_json({"type": "leave_lobby"})
    wait_for_positions(players[up_name], lambda positions: mara_name not in positions)
    for connection in (players[up_name], players[right_name]):
        move(connection, 0, 0)
    stopped_at_y = SPAWN_Y
    for connection in (players[up_name], players[right_name]):
        for positions in read_until_quiet(connection):
            stopped_at_y = positions[up_name]["y"]

    # Through all of it not one message reached anybody outside.
    time.sleep(QUIET_SECONDS)
    for outsider in outsiders:
        assert waiting_messages(outsider) == []

    # And the one who left hears nothing of the lobby any more.
    waiting_messages(players[mara_name])  # Empties what was on its way while Mara left.
    move(players[up_name], 0, 1)
    wait_for_positions(players[right_name], lambda positions: positions[up_name]["y"] > stopped_at_y)
    move(players[up_name], 0, 0)
    read_until_quiet(players[up_name])
    assert waiting_messages(players[mara_name]) == []


# Criterion 5: the messages of DESIGN.md, section 9, with their exact text


def test_the_ninth_player_is_told_that_the_lobby_is_full(connect):
    host, host_name = guest(connect)
    code = create(host)
    for number in range(7):
        member, member_name = guest(connect)
        assert ask(member, {"type": "join_lobby", "code": code})["type"] == "lobby_state"

    ninth, ninth_name = guest(connect)
    assert ask(ninth, {"type": "join_lobby", "code": code}) == {
        "type": "error",
        "code": "lobby_full",
        "message": "This lobby is full.",
    }
    # The ninth is not in the lobby: no positions arrive, although eight players stand there.
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(ninth) == []
    # The eight are all told where all eight stand.
    assert len(wait_for_positions(host, lambda positions: len(positions) == 8)) == 8


def test_an_unknown_code_and_a_code_of_three_letters_get_their_messages(connect):
    someone, name = guest(connect)
    assert ask(someone, {"type": "join_lobby", "code": "ZZZZ"}) == {
        "type": "error",
        "code": "no_lobby",
        "message": "No lobby with that code.",
    }
    assert ask(someone, {"type": "join_lobby", "code": "ABC"})["message"] == "Lobby codes are 4 letters."
    # Neither mistake cost anything: the guest can still create a lobby.
    assert ask(someone, {"type": "create_lobby"})["type"] == "lobby_state"


def test_the_account_messages_have_the_exact_texts(connect):
    account(connect, "Mara")
    second = connect()
    assert ask(second, {"type": "sign_up", "name": "Mara", "password": PASSWORD}) == {
        "type": "error",
        "code": "name_taken",
        "message": "That username is taken.",
    }
    assert ask(second, {"type": "log_in", "name": "Mara", "password": "not-the-password"}) == {
        "type": "error",
        "code": "wrong_credentials",
        "message": "Wrong username or password.",
    }
    assert ask(second, {"type": "sign_up", "name": "Tiago", "password": "short"}) == {
        "type": "error",
        "code": "bad_password",
        "message": "Passwords need at least 8 characters.",
    }
    assert ask(second, {"type": "sign_up", "name": "T!", "password": PASSWORD})["message"] == (
        "Usernames are 3–16 letters or numbers."
    )
    # After four rejections the connection still works.
    assert ask(second, {"type": "guest"})["type"] == "signed_in"


# Criterion 6: the host leaves


def test_when_the_host_leaves_the_next_player_is_host_and_the_leaver_is_gone_from_the_map(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, second_name, third_name = list(players)
    for connection in players.values():
        waiting_messages(connection)  # Forget the lobby states of joining.

    assert ask(players[mara_name], {"type": "leave_lobby"}) == {"type": "left_lobby"}

    for name in (second_name, third_name):
        deadline = time.monotonic() + DEADLINE_SECONDS
        messages = []
        while not any(message["type"] == "positions" for message in messages):
            messages.extend(waiting_messages(players[name]))
            assert time.monotonic() < deadline
        notices = [message for message in messages if message["type"] == "notice"]
        states = [message for message in messages if message["type"] == "lobby_state"]
        assert notices == [{"type": "notice", "message": f"The host left. {second_name} is the new host."}]
        assert states[-1]["host"] == second_name
        assert [listed["name"] for listed in states[-1]["players"]] == [second_name, third_name]
        # On the map Mara is gone too.
        assert as_positions(messages)[-1] == {second_name: AT_THE_SPAWN, third_name: AT_THE_SPAWN}


def test_a_player_who_closes_the_page_while_walking_disappears_for_the_others(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, second_name, third_name = list(players)
    move(players[third_name], 1, 0)
    wait_for_positions(players[mara_name], lambda positions: positions[third_name]["x"] > SPAWN_X)

    players[third_name].close()  # Like a reload of the tab, with the key still held down.

    for name in (mara_name, second_name):
        last = wait_for_positions(players[name], lambda positions: third_name not in positions)
        assert last == {mara_name: AT_THE_SPAWN, second_name: AT_THE_SPAWN}
    # Nothing keeps walking in the lobby after that.
    for name in (mara_name, second_name):
        read_until_quiet(players[name])
        assert waiting_messages(players[name]) == []


def test_logging_in_again_elsewhere_takes_the_first_connection_out_of_the_lobby(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, second_name, third_name = list(players)
    move(players[mara_name], -1, 0)
    wait_for_positions(players[second_name], lambda positions: positions[mara_name]["x"] < SPAWN_X)

    second_tab = connect()
    assert ask(second_tab, {"type": "log_in", "name": "Mara", "password": PASSWORD}) == {
        "type": "signed_in",
        "name": "Mara",
        "guest": False,
    }

    # The first tab is signed out, the guests see Mara vanish and get a new host.
    deadline = time.monotonic() + DEADLINE_SECONDS
    told = []
    while {"type": "signed_out"} not in told:
        told.extend(waiting_messages(players[mara_name]))
        assert time.monotonic() < deadline
    wait_for_positions(players[second_name], lambda positions: mara_name not in positions)
    # The new connection of Mara is outside of every lobby: it gets no positions and cannot walk.
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(second_tab) == []
    assert ask(second_tab, {"type": "move", "dx": 1, "dy": 0}) == {
        "type": "error",
        "code": "not_in_lobby",
        "message": "You are not in a lobby.",
    }
    # The old connection cannot walk either: it is nobody now.
    assert ask(players[mara_name], {"type": "move", "dx": 1, "dy": 0})["message"] == (
        "Log in or play as a guest first."
    )


# Breaking it: hand-written bad messages while walking


BAD_MESSAGES = [
    ('{"type":"move","dx":5,"dy":0}', "That move could not be read."),
    ('{"type":"move","dx":1.5,"dy":0}', "That move could not be read."),
    ('{"type":"move","dx":true,"dy":0}', "That move could not be read."),
    ('{"type":"move","dx":"1","dy":0}', "That move could not be read."),
    ('{"type":"move","dx":1}', "That message is incomplete."),
    ('{"type":"move","dx":1,"dy":0,"speed":99}', "That message has a field the server does not expect."),
    ('{"type":"fly"}', "The server does not know that action."),
    ('{"type":"join_lobby","code":"ABC"}', "Lobby codes are 4 letters."),
    ('{"type":"hello","name":"' + "x" * 5000 + '"}', "That message is too long."),
    ("x" * 200_000, "That message is too long."),
    ("walk left please", "That message could not be read."),
    ("[1, 2, 3]", "That message could not be read."),
    ('{"type":"create_lobby"}', "Leave your lobby first."),
    ('{"type":"guest"}', "Log out first."),
    ('{"type":"choose_character","character":"wizard"}', "That character does not exist."),
]


def test_bad_messages_get_an_error_each_and_change_nothing_on_the_map(connect):
    mara = account(connect, "Mara")
    watcher, watcher_name = guest(connect)
    code = create(mara)
    join(watcher, code)
    both_at_the_spawn = lambda positions: positions == {"Mara": AT_THE_SPAWN, watcher_name: AT_THE_SPAWN}
    wait_for_positions(mara, both_at_the_spawn)
    wait_for_positions(watcher, both_at_the_spawn)
    waiting_messages(mara)
    waiting_messages(watcher)

    for raw, expected_text in BAD_MESSAGES:
        mara.send_text(raw)
        answer = mara.receive_json()
        assert answer["type"] == "error", raw[:60]
        assert answer["message"] == expected_text, raw[:60]

    # Nobody moved because of them, and the watcher was told nothing at all.
    time.sleep(QUIET_SECONDS)
    assert waiting_messages(mara) == []
    assert waiting_messages(watcher) == []

    # The connection and the server are fine: Mara can still walk and is seen walking.
    move(mara, 1, 0)
    wait_for_positions(watcher, lambda positions: positions["Mara"]["x"] > SPAWN_X)
    move(mara, 0, 0)


def test_a_taken_character_is_refused_with_its_message_and_nobody_changes(connect):
    players, code = one_account_and_two_guests_in_a_lobby(connect)
    mara_name, second_name, third_name = list(players)
    for connection in players.values():
        waiting_messages(connection)

    # Mara is the Consultant (the first free character went to her).
    assert ask(players[second_name], {"type": "choose_character", "character": "consultant"}) == {
        "type": "error",
        "code": "character_taken",
        "message": "That character is taken.",
    }
    assert waiting_messages(players[mara_name]) == []

    # A free character works and all three are told.
    players[second_name].send_json({"type": "choose_character", "character": "surfer"})
    for connection in players.values():
        deadline = time.monotonic() + DEADLINE_SECONDS
        states = []
        while not states:
            states = [m for m in waiting_messages(connection) if m["type"] == "lobby_state"]
            assert time.monotonic() < deadline
        characters = {listed["name"]: listed["character"] for listed in states[-1]["players"]}
        assert characters[second_name] == "surfer"
        assert characters[mara_name] == "consultant"


def test_the_same_direction_sent_twice_quickly_is_one_walk(connect):
    mara = account(connect, "Mara")
    create(mara)
    wait_for_positions(mara, lambda positions: positions == {"Mara": AT_THE_SPAWN})

    # Like a key that repeats: the same message many times in a row.
    for number in range(20):
        move(mara, 1, 0)
    seen = []
    wait_for_positions(mara, lambda positions: positions["Mara"]["x"] > SPAWN_X + 30, seen)
    for number in range(20):
        move(mara, 0, 0)
    seen.extend(read_until_quiet(mara))

    # She walked at the normal speed: every step is small, none is 20 steps at once.
    xs = [SPAWN_X] + [positions["Mara"]["x"] for positions in seen]
    assert xs == sorted(xs)
    assert max(after - before for before, after in zip(xs, xs[1:])) <= 30
