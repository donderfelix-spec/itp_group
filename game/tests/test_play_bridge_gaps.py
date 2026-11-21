"""Play test of "bridge the gaps" (M2-1.16, S-121).

What the tester played in real browsers (alone, in a Duel of two and in a
lobby of eight, on a good connection and behind the delay proxy) and what
`test_bridge_gaps.py` and `test_bridge_gaps_edges.py` do not already check:

- a hold-up of two and a half seconds with the key held: the character
  walks on ten steps, stands, is put back on the last position the server
  sent a second later, and goes on from the server's place when the
  messages arrive;
- a walk that starts again a moment after a stop, with every message on
  time: nothing is bridged and nothing needs a correction;
- a change of direction with a short moment in which no key is held, with
  every message on time. A player who lets go of one key before pressing
  the next does this all the time. If the server's tick falls into that
  moment, the server sends no position for it (nobody moved), and the
  bridge took that for a held-up message: it walked one step on in the old
  direction and was corrected by one step each way (8.6 units after a
  quarter turn, 12.2 after a reversal). In the browser this showed on a
  connection without any delay: "corrections: largest units: 12.25, above
  1.5 units: 2" after 26 seconds of walking. Since then the bridge makes
  no step when no key was held at some time near the moment it reads the
  direction from (within a tick and a half of the server), and the
  character waits for the server's position as it did before the bridge.
  The tests below sweep such changes of direction over the server's tick.
"""

import functools
import math

import pytest

from bridge_helpers import (
    EXACT,
    KEY_AT,
    NODE,
    SERVER_STEP,
    Scenario,
    between,
    frozen,
    held_from,
    on_time,
    open_square,
    overlapping,
    place,
    place_at,
    walk_right,
    way_back,
)

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

RIGHT = (1, 0)
DOWN = (0, 1)

# ---- A change of direction with a moment in which no key is held, messages on time ----------------

NO_KEY_MILLISECONDS = 30  # between letting go of one key and pressing the next
# The change at twelve moments spread over one tick of the server (68 ms).
CHANGES_AT = [1900 + 6 * number for number in range(12)]
NEXT_KEYS = {"a reversal": "KeyA", "a quarter turn": "KeyS"}


@functools.lru_cache(maxsize=None)
def change_of_direction(kind, change_at):
    """Walk right, let go, press the next key 30 ms later, walk on for half a second."""
    next_key = NEXT_KEYS[kind]
    pressed_at = change_at + NO_KEY_MILLISECONDS
    keys = [(KEY_AT, "down", "KeyD"), (change_at, "up", "KeyD"), (pressed_at, "down", next_key), (pressed_at + 500, "up", next_key)]
    walk = Scenario(keys, on_time(), until=pressed_at + 2600, start=open_square(120))
    return walk, walk.run()


@pytest.mark.parametrize("kind", NEXT_KEYS)
def test_a_change_of_direction_through_a_moment_without_keys_is_guessed_one_step_wrong_at_most(kind):
    for change_at in CHANGES_AT:
        walk, result = change_of_direction(kind, change_at)
        frames = result["frames"]
        numbers = result["bridge"]
        # One wrong guess at most: one step too far in the old direction
        # while the server walked one step in the new one.
        assert numbers["largeCorrections"] <= 1, change_at
        assert numbers["largestCorrection"] <= 2 * SERVER_STEP + 0.1, change_at
        assert numbers["steps"] <= 4 and numbers["takenBack"] == 0, change_at
        # The character is never drawn more than half a step beyond the
        # place where the server turned ...
        turned_at = max(x for x, _ in walk.server_path())
        assert max(place(frame)[0] for frame in frames) <= turned_at + SERVER_STEP / 2, change_at
        # ... it never stands inside a solid, and it ends on the server's position.
        assert overlapping(frames) == []
        assert math.dist(place(frames[-1]), walk.server_place()) < 1e-9


@pytest.mark.parametrize("kind", NEXT_KEYS)
def test_with_messages_on_time_a_change_of_direction_is_never_guessed_wrong(kind):
    wrong = [change_at for change_at in CHANGES_AT if change_of_direction(kind, change_at)[1]["bridge"]["largeCorrections"] > 0]
    assert wrong == []


# The same, wider: every way a player changes direction through a moment
# without a direction, for moments of 5 to 120 ms, at twelve times spread
# over one tick of the server.

MOMENTS_WITHOUT_A_DIRECTION = [5, 10, 30, 60, 120]  # ms
TWELVE_TIMES = [1900 + 68 * number / 12 for number in range(12)]
WAYS_TO_CHANGE = ["a reversal", "a quarter turn", "a stop and go", "a reversal with both keys down"]


def keys_of_a_change(way, change_at, milliseconds, first_key_at=KEY_AT):
    """Walk right, change direction through `milliseconds` without a direction, walk on for half a second."""
    again_at = change_at + milliseconds
    if way == "a reversal with both keys down":
        # The opposite key is pressed while the first is still down: right
        # and left cancel each other until the first key is released.
        return [(first_key_at, "down", "KeyD"), (change_at, "down", "KeyA"), (again_at, "up", "KeyD"), (again_at + 500, "up", "KeyA")]
    next_key = {"a reversal": "KeyA", "a quarter turn": "KeyS", "a stop and go": "KeyD"}[way]
    return [(first_key_at, "down", "KeyD"), (change_at, "up", "KeyD"), (again_at, "down", next_key), (again_at + 500, "up", next_key)]


def changed(way, change_at, milliseconds, first_key_at=KEY_AT):
    keys = keys_of_a_change(way, change_at, milliseconds, first_key_at)
    return Scenario(keys, on_time(), until=change_at + milliseconds + 2600, start=open_square(120))


def assert_nothing_was_guessed(walk, result, where):
    frames = result["frames"]
    numbers = result["bridge"]
    # No correction at all, large or small, and nothing taken back.
    assert numbers["corrections"] == 0 and numbers["largeCorrections"] == 0 and numbers["takenBack"] == 0, where
    # No bridged step in the old direction: the character is never drawn
    # beyond the place where the server stopped or turned.
    furthest = max(x for x, _ in walk.server_path())
    assert max(place(frame)[0] for frame in frames) <= furthest + EXACT, where
    assert overlapping(frames) == [], where
    assert math.dist(place(frames[-1]), walk.server_place()) < 1e-9, where


@pytest.mark.parametrize("milliseconds", MOMENTS_WITHOUT_A_DIRECTION)
@pytest.mark.parametrize("way", WAYS_TO_CHANGE)
def test_with_messages_on_time_no_way_of_changing_direction_is_guessed_wrong(way, milliseconds):
    servers_ticks_in_the_moment = 0
    for change_at in TWELVE_TIMES:
        walk = changed(way, change_at, milliseconds)
        assert_nothing_was_guessed(walk, walk.run(), (way, milliseconds, change_at))
        # Did the server stand for a tick? Then one position less was sent.
        moved = [was_moved for time, _, was_moved in walk.ticks if 1500 < time < change_at + milliseconds + 400]
        servers_ticks_in_the_moment += moved.count(False) > 0
    # The sweep hits what it is for: in some of the twelve the server's tick
    # fell into the moment without a direction (in all of them when the
    # moment is longer than a tick).
    assert servers_ticks_in_the_moment >= 1
    if milliseconds > 68:
        assert servers_ticks_in_the_moment == 12


@pytest.mark.parametrize("first_key_at", [KEY_AT + 17, KEY_AT + 34, KEY_AT + 51])
@pytest.mark.parametrize("way", ["a reversal", "a quarter turn"])
def test_the_same_holds_whenever_the_first_key_fell_within_the_servers_tick(way, first_key_at):
    # The input lag is measured at the start of the walk and contains the
    # wait for the server's next tick, a different one for each of these
    # keys. With one tick on each side, 4 of 240 such changes were still
    # guessed wrong; with a tick and a half none.
    for change_at in TWELVE_TIMES:
        walk = changed(way, change_at, 30, first_key_at)
        assert_nothing_was_guessed(walk, walk.run(), (way, first_key_at, change_at))


@pytest.mark.parametrize("way", WAYS_TO_CHANGE)
def test_a_change_of_direction_is_drawn_as_without_the_bridge_except_for_the_own_delay(way):
    identical = 0
    for milliseconds in [10, 60]:
        for change_at in TWELVE_TIMES[::3]:
            walk = changed(way, change_at, milliseconds)
            with_bridge = walk.run()["frames"]
            without = walk.run(search="?bridge=off")["frames"]
            assert len(with_bridge) == len(without)
            # Up to the change, and for 100 ms after it, every frame is the same.
            early = [frame["t"] <= change_at + 100 for frame in with_bridge]
            assert [f for f, is_early in zip(with_bridge, early) if is_early] == [f for f, is_early in zip(without, early) if is_early]
            # Afterwards the only difference is the own delay. When the
            # server stood for a tick, one message is missing; without the
            # bridge the playback delay grows with that gap (to about 150
            # ms), with it the own character stays at 110 ms. So the two
            # drawings are less than half a step apart for the rest of the
            # walk, and they end on the same place.
            apart = max(math.dist(place(a), place(b)) for a, b in zip(with_bridge, without))
            assert apart < 3.1, (milliseconds, change_at)
            assert place(with_bridge[-1]) == place(without[-1])
            # And like without the bridge the character never stands while
            # the new key is held (after the start of the new walk).
            new_walk = change_at + milliseconds
            assert frozen(with_bridge, new_walk + 200, new_walk + 500) == frozen(without, new_walk + 200, new_walk + 500) == []
            identical += with_bridge == without
    # Where the server did not stand for a tick, there is no gap and no difference at all.
    assert identical >= 2


# ---- A walk that starts again a moment after a stop, messages on time ------------------------------


@pytest.mark.parametrize("pause", [150, 300, 390])
def test_a_walk_that_starts_again_within_400_ms_is_not_bridged_and_needs_no_correction(pause):
    # After a pause shorter than PAUSE_MILLISECONDS in world.js the queue
    # starts without its delay, so the second position of the new walk
    # arrives a moment after the first glide ended. Before the bridge kept
    # away from a moment without keys, it stepped in there once; now the
    # walk has only just begun, and the character waits for the position
    # as it did before the bridge.
    keys = [(KEY_AT, "down", "KeyD"), (1900, "up", "KeyD"), (1900 + pause, "down", "KeyD"), (2900, "up", "KeyD")]
    walk = Scenario(keys, on_time(), until=5000, start=open_square(120))
    result = walk.run()
    numbers = result["bridge"]
    assert numbers["steps"] == 0 and numbers["replaced"] == 0
    assert numbers["corrections"] == 0 and numbers["takenBack"] == 0
    assert way_back(result["frames"], RIGHT) == 0
    assert math.dist(place(result["frames"][-1]), walk.server_place()) < 1e-9


# ---- A hold-up of two and a half seconds with the key held ------------------------------------------

HELD_MESSAGE = 30  # sent at 3073 and held 2.5 s: it arrives at 5598 with everything after it
RELEASED_AT = 7400


@functools.lru_cache(maxsize=None)
def long_outage():
    walk = walk_right(held_from(3073, 2500), until=RELEASED_AT + 1800, release_at=RELEASED_AT)
    return walk, walk.run()


def test_the_outage_scenario_holds_the_messages_for_two_and_a_half_seconds():
    walk, _ = long_outage()
    assert walk.arrival(HELD_MESSAGE) - walk.arrival(HELD_MESSAGE - 1) == pytest.approx(2568)


def test_in_a_long_outage_the_character_walks_on_ten_steps_and_then_stands():
    walk, result = long_outage()
    frames = result["frames"]
    last_heard = walk.arrival(HELD_MESSAGE - 1)
    known = walk.known_place(last_heard)
    standing = between(frames, last_heard + 900, last_heard + 1700)
    assert len(standing) > 40
    assert frozen(frames, last_heard + 900, last_heard + 1700) == [frame["t"] for frame in standing]
    assert place(standing[0]) == pytest.approx((known[0] + 10 * SERVER_STEP, known[1]), abs=0.05)
    assert result["bridge"]["steps"] == 10


def test_a_second_later_the_character_is_back_on_the_last_position_the_server_sent():
    walk, result = long_outage()
    frames = result["frames"]
    last_heard = walk.arrival(HELD_MESSAGE - 1)
    arrives = walk.arrival(HELD_MESSAGE)
    known = walk.known_place(last_heard)
    waiting = between(frames, last_heard + 1950, arrives - 1)
    assert len(waiting) > 30
    for frame in waiting:
        assert place(frame) == pytest.approx(known, abs=EXACT), frame["t"]
    assert result["bridge"]["takenBack"] == 1
    # The ten steps are taken back in full, and nothing else ever goes backwards.
    assert way_back(frames, RIGHT) == pytest.approx(10 * SERVER_STEP, abs=0.05)
    assert way_back(frames, RIGHT, 0, last_heard + 1700) == 0
    assert way_back(frames, RIGHT, arrives) == 0


def test_when_the_messages_arrive_the_character_goes_on_from_the_servers_place_and_ends_on_it():
    walk, result = long_outage()
    frames = result["frames"]
    arrives = walk.arrival(HELD_MESSAGE)
    for time in range(int(arrives) + 700, RELEASED_AT, 100):
        behind = walk.server_place(time)[0] - place_at(frames, time)[0]
        assert 0 <= behind <= 2.5 * SERVER_STEP, time
    assert frozen(frames, arrives + 700, RELEASED_AT) == []
    assert overlapping(frames) == []
    assert math.dist(place(frames[-1]), walk.server_place()) < 1e-9
