"""Play test of "bridge the gaps" (M2-1.16, S-121).

What the tester played in real browsers (alone, in a Duel of two and in a
lobby of eight, on a good connection and behind the delay proxy) and what
`test_bridge_gaps.py` and `test_bridge_gaps_edges.py` do not already check:

- a hold-up of two and a half seconds with the key held: the character
  walks on ten steps, stands, is put back on the last position the server
  sent a second later, and goes on from the server's place when the
  messages arrive;
- a walk that starts again a moment after a stop, with every message on
  time: one step is bridged and nothing needs a correction;
- a change of direction with a short moment in which no key is held, with
  every message on time. A player who lets go of one key before pressing
  the next does this all the time. If the server's tick falls into that
  moment, the server sends no position for it (nobody moved), and the
  bridge takes that for a held-up message: it walks one step on in the old
  direction and is corrected by one step each way (8.6 units after a
  quarter turn, 12.2 after a reversal). In the browser this showed on a
  connection without any delay: "corrections: largest units: 12.25, above
  1.5 units: 2" after 26 seconds of walking. The first test below says how
  far that goes at most; the second one says what the to-do expects (no
  wrong guess while the messages are on time) and is marked as failing.
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


@pytest.mark.xfail(strict=True, reason=(
    "Found in the play test of M2-1.16: with every message on time the bridge still guesses a step wrong when the "
    "server's tick falls into the moment without keys of a change of direction (correction of 8.6 or 12.2 units). "
    "Remove this mark when that is fixed, or the test when the team accepts it as a known limit of S-121."
))
@pytest.mark.parametrize("kind", NEXT_KEYS)
def test_with_messages_on_time_a_change_of_direction_is_never_guessed_wrong(kind):
    wrong = [change_at for change_at in CHANGES_AT if change_of_direction(kind, change_at)[1]["bridge"]["largeCorrections"] > 0]
    assert wrong == []


# ---- A walk that starts again a moment after a stop, messages on time ------------------------------


@pytest.mark.parametrize("pause", [150, 300, 390])
def test_a_walk_that_starts_again_within_400_ms_bridges_one_step_and_needs_no_correction(pause):
    # After a pause shorter than PAUSE_MILLISECONDS in world.js the queue
    # starts without its delay, so the second position of the new walk
    # arrives a moment after the first glide ended: one bridged step.
    keys = [(KEY_AT, "down", "KeyD"), (1900, "up", "KeyD"), (1900 + pause, "down", "KeyD"), (2900, "up", "KeyD")]
    walk = Scenario(keys, on_time(), until=5000, start=open_square(120))
    result = walk.run()
    numbers = result["bridge"]
    assert numbers["steps"] == 1 and numbers["replaced"] == 1
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
