"""The server's time in `positions` and the numbered `move` it has heard (M2-1.16).

Three parts, each without a real network:

- `protocol.py`: `move` may carry "seq", `positions` may carry "t" and "you".
- `Walkers`: the plain rules remember the last numbered move of each player.
- `main.tick` with stand-ins for the WebSockets and a clock the test sets,
  like the slow-member tests in test_server_walking.py.

The same rules with the real tick and real connections are played in
test_play_positions_time_and_heard.py.
"""

import asyncio
import json

import pytest

from server import main, protocol
from server.main import app
from server.net.walking import Walkers
from server.protocol import ProtocolError, parse_client_message

BAD_MOVE = ("bad_move", "That move could not be read.")


def rejected(raw):
    """The (code, message) of the error for this raw text."""
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(raw)
    return (caught.value.code, caught.value.message)


def numbered_move(dx, dy, seq):
    return json.dumps({"type": "move", "dx": dx, "dy": dy, "seq": seq})


# protocol: `move` with "seq", accepted


@pytest.mark.parametrize("seq", [0, 1, 7, 123456, 2_000_000_000])
def test_a_move_with_a_whole_number_from_0_to_2_billion_is_accepted(seq):
    assert parse_client_message(numbered_move(1, -1, seq)) == {"type": "move", "dx": 1, "dy": -1, "seq": seq}


def test_a_move_without_seq_is_accepted_as_before_and_has_no_seq():
    checked = parse_client_message('{"type": "move", "dx": 0, "dy": 1}')
    assert checked == {"type": "move", "dx": 0, "dy": 1}
    assert "seq" not in checked


# protocol: `move` with "seq", rejected


@pytest.mark.parametrize(
    "seq",
    [True, False, 1.0, 0.5, "1", -1, 2_000_000_001, None, [1], {"seq": 1}],
    ids=repr,
)
def test_a_seq_that_is_not_a_whole_number_in_range_is_a_bad_move(seq):
    assert rejected(numbered_move(1, 0, seq)) == BAD_MOVE


@pytest.mark.parametrize("raw_seq", ["1.0", "1e3", "-0.0", "true", "null", "2000000001"])
def test_a_seq_written_by_hand_in_the_raw_text_is_a_bad_move(raw_seq):
    # json.dumps cannot write some of these the way a browser might.
    assert rejected('{"type": "move", "dx": 1, "dy": 0, "seq": ' + raw_seq + "}") == BAD_MOVE


def test_a_good_seq_does_not_save_a_bad_direction():
    assert rejected(numbered_move(2, 0, 5)) == BAD_MOVE


def test_a_move_with_seq_and_an_unknown_field_is_still_rejected():
    raw = json.dumps({"type": "move", "dx": 1, "dy": 0, "seq": 5, "speed": 99})
    assert rejected(raw)[0] == "unknown_field"


def test_a_move_with_seq_but_without_dy_is_still_incomplete():
    assert rejected('{"type": "move", "dx": 1, "seq": 5}')[0] == "missing_field"


@pytest.mark.parametrize("message_type", [name for name in protocol.CLIENT_MESSAGES if name != "move"])
def test_no_other_message_accepts_seq(message_type):
    assert rejected(json.dumps({"type": message_type, "seq": 1}))[0] == "unknown_field"


# protocol: `positions` with "t" and "you"


def test_positions_without_t_and_you_is_unchanged():
    assert protocol.positions([("Mara", 12.34, 7.86)]) == {
        "type": "positions",
        "players": [{"name": "Mara", "x": 12.3, "y": 7.9}],
    }


def test_positions_with_t_carries_the_time_and_no_you():
    message = protocol.positions([("Mara", 12.34, 7.86)], 1234567)
    assert message == {"type": "positions", "players": [{"name": "Mara", "x": 12.3, "y": 7.9}], "t": 1234567}


def test_positions_with_t_zero_still_carries_it():
    assert protocol.positions([], 0) == {"type": "positions", "players": [], "t": 0}


def test_positions_with_you_carries_seq_time_and_direction():
    message = protocol.positions([("Mara", 1.04, 2.06), ("Tiago", 3, 4)], 5000, (7, 4990, -1, 0))
    assert message == {
        "type": "positions",
        "players": [{"name": "Mara", "x": 1.0, "y": 2.1}, {"name": "Tiago", "x": 3, "y": 4}],
        "t": 5000,
        "you": {"seq": 7, "t": 4990, "dx": -1, "dy": 0},
    }
    json.dumps(message)  # It can be sent as it is.


# Walkers: what was heard


def walkers_with(*names):
    """Players who joined and have been placed and told, so there is no news left."""
    walkers = Walkers()
    for name in names:
        walkers.add(name)
    walkers.advance(0, open_field())
    for name in names:
        walkers.mark_told(name)
    return walkers


def open_field():
    return {"width": 1000, "height": 1000, "spawn": {"x": 100, "y": 200}, "solids": []}


def test_a_newcomer_has_been_heard_nothing():
    walkers = walkers_with("Mara")
    assert walkers.last_heard("Mara") is None


def test_hearing_remembers_the_seq_and_the_time():
    walkers = walkers_with("Mara")
    walkers.hear("Mara", 7, 12.5)
    assert walkers.last_heard("Mara") == (7, 12.5)
    walkers.hear("Mara", 8, 13.0)
    assert walkers.last_heard("Mara") == (8, 13.0)


def test_what_was_heard_is_per_player():
    walkers = walkers_with("Mara", "Tiago")
    walkers.hear("Mara", 7, 12.5)
    assert walkers.last_heard("Tiago") is None
    walkers.hear("Tiago", 3, 14.0)
    assert walkers.last_heard("Mara") == (7, 12.5)
    assert walkers.last_heard("Tiago") == (3, 14.0)


def test_hearing_does_not_change_the_direction():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, -1)
    walkers.hear("Mara", 7, 12.5)
    assert walkers.direction_of("Mara") == (1, -1)


def test_direction_of_is_what_was_set_and_still_at_first():
    walkers = walkers_with("Mara")
    assert walkers.direction_of("Mara") == (0, 0)
    walkers.set_direction("Mara", -1, 1)
    assert walkers.direction_of("Mara") == (-1, 1)


def test_what_was_heard_survives_the_way_back_to_the_spawn():
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walkers.hear("Mara", 7, 12.5)
    walkers.back_to_spawn()
    assert walkers.last_heard("Mara") == (7, 12.5)
    assert walkers.direction_of("Mara") == (1, 0)


def test_what_was_heard_is_gone_after_leaving_and_joining_again():
    walkers = walkers_with("Mara", "Tiago")
    walkers.hear("Mara", 7, 12.5)
    walkers.remove("Mara")
    walkers.add("Mara")
    assert walkers.last_heard("Mara") is None


def test_hearing_gives_news_to_that_player_only_even_if_nobody_moves():
    walkers = walkers_with("Mara", "Tiago")
    walkers.hear("Mara", 7, 12.5)
    assert walkers.names_to_tell() == ["Mara"]
    assert walkers.advance(0.1, open_field()) is True
    assert walkers.names_to_tell() == ["Mara"]
    walkers.mark_told("Mara")
    assert walkers.advance(0.1, open_field()) is False


def test_setting_a_direction_alone_gives_no_news():
    walkers = walkers_with("Mara", "Tiago")
    walkers.set_direction("Mara", 0, 0)
    assert walkers.advance(0.1, open_field()) is False


# main.tick with stand-ins for the WebSockets


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: these tests call the real tick."""


class Clock:
    """Stands in for `main.seconds_now`, so the test decides how late it is."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    test_clock = Clock()
    monkeypatch.setattr(main, "seconds_now", test_clock)
    return test_clock


class FakeWebSocket:
    """Stands in for a WebSocket and remembers what the server sent to it."""

    def __init__(self):
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self):
        pass


def fake_lobby(**websockets):
    """Sign the stand-ins in under their names and put them in one lobby, in order."""
    names = list(websockets)
    for name, websocket in websockets.items():
        app.state.sessions.sign_in_account(websocket, name)
    lobby, rejection_code = app.state.lobbies.create(names[0], lambda: "ABCD")
    for name in names[1:]:
        app.state.lobbies.join(name, "ABCD")
    return lobby


async def one_tick(clock, seconds_later=1 / main.TICKS_PER_SECOND):
    """Let the clock run on, run the tick once and let the started sends run."""
    clock.now += seconds_later
    main.tick(1 / main.TICKS_PER_SECOND)
    await asyncio.sleep(0.01)


async def placed_and_told(clock, *websockets):
    """The first tick places everybody on the spawn. Forget those first messages."""
    await one_tick(clock)
    for websocket in websockets:
        websocket.sent.clear()


def test_every_member_of_one_tick_gets_the_same_time_and_players(clock):
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago)
    lobby.walkers.set_direction("Tiago", 1, 0)

    async def two_ticks():
        await one_tick(clock, 0.5)
        await one_tick(clock, 0.25)

    asyncio.run(two_ticks())
    assert [message["t"] for message in mara.sent] == [1_000_500, 1_000_750]
    assert [message["t"] for message in tiago.sent] == [1_000_500, 1_000_750]
    assert [message["players"] for message in mara.sent] == [message["players"] for message in tiago.sent]
    # Nobody sent a numbered move, so nobody gets "you".
    assert all("you" not in message for message in mara.sent + tiago.sent)


def test_a_numbered_move_is_answered_to_that_player_alone_at_the_next_tick(clock):
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    lobby = fake_lobby(Mara=mara, Tiago=tiago)

    async def mara_stops_with_a_number():
        await placed_and_told(clock, mara, tiago)
        clock.now += 0.02
        await main.answer_move_message(mara, {"type": "move", "dx": 0, "dy": 0, "seq": 4})
        await one_tick(clock)
        await one_tick(clock)

    asyncio.run(mara_stops_with_a_number())
    # One message for Mara, at the first tick after the move, though nobody moved.
    heard_at = round((1000.0 + 1 / main.TICKS_PER_SECOND + 0.02) * 1000)
    assert len(mara.sent) == 1
    assert mara.sent[0]["you"] == {"seq": 4, "t": heard_at, "dx": 0, "dy": 0}
    assert mara.sent[0]["t"] >= heard_at
    assert tiago.sent == []
    assert lobby.walkers.last_heard("Mara") == (4, 1000.0 + 1 / main.TICKS_PER_SECOND + 0.02)


def test_a_move_without_a_number_brings_no_extra_message(clock):
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)

    async def mara_stops_without_a_number():
        await placed_and_told(clock, mara, tiago)
        await main.answer_move_message(mara, {"type": "move", "dx": 0, "dy": 0})
        await one_tick(clock)

    asyncio.run(mara_stops_without_a_number())
    assert mara.sent == []
    assert tiago.sent == []


def test_each_member_gets_only_their_own_you(clock):
    mara, tiago, ines = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago, Ines=ines)

    async def two_numbered_moves():
        await placed_and_told(clock, mara, tiago, ines)
        await main.answer_move_message(mara, {"type": "move", "dx": 1, "dy": 0, "seq": 3})
        await main.answer_move_message(tiago, {"type": "move", "dx": 0, "dy": -1, "seq": 50})
        await one_tick(clock)

    asyncio.run(two_numbered_moves())
    assert mara.sent[-1]["you"]["seq"] == 3 and (mara.sent[-1]["you"]["dx"], mara.sent[-1]["you"]["dy"]) == (1, 0)
    assert tiago.sent[-1]["you"]["seq"] == 50 and (tiago.sent[-1]["you"]["dx"], tiago.sent[-1]["you"]["dy"]) == (0, -1)
    assert "you" not in ines.sent[-1]
    assert mara.sent[-1]["t"] == tiago.sent[-1]["t"] == ines.sent[-1]["t"]
    assert mara.sent[-1]["players"] == tiago.sent[-1]["players"] == ines.sent[-1]["players"]


def test_a_member_who_was_busy_gets_the_answer_to_the_move_later(clock):
    mara, tiago = FakeWebSocket(), FakeWebSocket()
    fake_lobby(Mara=mara, Tiago=tiago)

    async def mara_is_busy_when_her_move_is_heard():
        await placed_and_told(clock, mara, tiago)
        main.taking_positions.add(mara)  # As if Mara were still taking an older message.
        await main.answer_move_message(mara, {"type": "move", "dx": 0, "dy": 0, "seq": 9})
        await one_tick(clock)
        assert mara.sent == []
        main.taking_positions.discard(mara)
        await one_tick(clock)

    asyncio.run(mara_is_busy_when_her_move_is_heard())
    assert len(mara.sent) == 1
    assert mara.sent[0]["you"]["seq"] == 9
    assert tiago.sent == []


def test_the_direction_in_you_is_the_one_the_server_walks():
    # The server stops a player itself when a station opens (`handle_open_station`).
    # Here the same is done by hand, after the browser's numbered move.
    walkers = walkers_with("Mara")
    walkers.set_direction("Mara", 1, 0)
    walkers.hear("Mara", 2, 10.0)
    walkers.set_direction("Mara", 0, 0)
    assert main.what_was_heard_from(walkers, "Mara") == (2, 10_000, 0, 0)


def test_nothing_heard_means_no_you():
    walkers = walkers_with("Mara")
    assert main.what_was_heard_from(walkers, "Mara") is None


@pytest.mark.parametrize("seconds, expected", [(0.0, 0), (1.0, 1000), (12.3456, 12346), (0.0004, 0)])
def test_milliseconds_are_whole_numbers(seconds, expected):
    assert main.milliseconds(seconds) == expected
    assert type(main.milliseconds(seconds)) is int
