"""To-do M2-1.16 "Bridge the gaps", with the real world.js: walking on connections that hold messages up.

On the deployed game the `positions` messages are sometimes held up: one in
six about 105 ms, and every 15 to 50 seconds everything for 260 to 690 ms,
which then arrives at once. The own character and the camera stood that
long. Now the own character walks on by itself with the server's own rule
while its queue is empty although the player walks ("bridged steps"), and
the server's positions take the place of those steps when they arrive.

Each test describes the keys of the player and how late every message is.
The helpers (tests/bridge_helpers.py) play the server with the server's own
rule and run the page's bridge.js, world.js and diagnostic.js in Node
(tests/world_bridge_in_node.js). The tests read where every frame draws the
own character.

Walls, a server that does not walk, the start of a round and the station in
range are in test_bridge_gaps_edges.py; the plain functions in
test_bridge_rule.py. Without Node the tests are skipped; CI has Node.
"""

import functools
import math

import pytest

from bridge_helpers import (
    EXACT,
    FELIX,
    FELIX_BAD_SECOND,
    FELIX_DEBUG_RUN,
    FIRST_FRAME,
    KEY_AT,
    NODE,
    OPEN_LENGTH,
    OPEN_START,
    OTHER_CHARACTER,
    OWN_CHARACTER,
    SERVER_STEP,
    SERVER_TICK,
    TICK,
    UNEVEN_STEPS,
    Scenario,
    between,
    circling,
    distance_to_path,
    drawn,
    frozen,
    held,
    held_from,
    looped,
    on_time,
    open_square,
    pairs,
    place,
    speeds,
    walk_right,
    way_back,
)

pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

RIGHT = (1, 0)
DOWN = (0, 1)
SETTLED = KEY_AT + 500  # the first 500 ms of a walk are its start: not judged
WALK_UNTIL = KEY_AT + 7000  # seven seconds of walking fit on the map's longest open way
WALK_CYCLE = 36  # WALK_CYCLE_LENGTH in world.js: map units per two steps of the feet

# Messages that are up to 40 ms late: no gap, but the playback delay of the
# other players grows a little.
A_LITTLE_LATE = [0, 12, 30, 5, 40, 0, 22, 8]

# The connection of the walking diagnostic's run of 2026-11-20, started so
# that all its hold-ups fall into seven seconds: message 25 is held 620 ms,
# the messages 83, 89, 95 and 101 are held 240 ms each.
HOLD_UPS = looped(FELIX_DEBUG_RUN, first=-5)
LONG_HOLD_UP_MESSAGE = 25

# A second player who walks in a circle the whole time, so the server sends
# a message on every tick, also when the own player stands.
SOMEBODY = circling((OPEN_START[0] + 200, OPEN_START[1] - 60))


def test_the_map_has_an_open_way_long_enough_for_these_walks():
    assert OPEN_LENGTH >= 90 * 7 + 10


# Every scenario is played once per way of playing it, however many tests look at it.
SCENARIOS = {
    "on time": lambda: walk_right(on_time(), until=6500, release_at=5000),
    "a little late": lambda: walk_right(looped(A_LITTLE_LATE), until=6500, release_at=5000),
    "felix": lambda: walk_right(looped(FELIX), until=WALK_UNTIL),
    "hold-ups": lambda: walk_right(HOLD_UPS, until=WALK_UNTIL),
    "bad second": lambda: walk_right(looped(FELIX_BAD_SECOND), until=WALK_UNTIL),
    "felix, two players": lambda: walk_right(looped(FELIX), until=WALK_UNTIL, other=SOMEBODY),
    "hold-ups, two players": lambda: walk_right(HOLD_UPS, until=WALK_UNTIL, other=SOMEBODY),
    "bad second, two players": lambda: walk_right(looped(FELIX_BAD_SECOND), until=WALK_UNTIL, other=SOMEBODY),
    "felix, uneven ticks": lambda: walk_right(looped(FELIX), until=WALK_UNTIL, step_lengths=UNEVEN_STEPS),
    "hold-ups, uneven ticks": lambda: walk_right(HOLD_UPS, until=WALK_UNTIL, step_lengths=UNEVEN_STEPS),
    "bad second, uneven ticks": lambda: walk_right(looped(FELIX_BAD_SECOND), until=WALK_UNTIL, step_lengths=UNEVEN_STEPS),
    "felix, then a stop": lambda: walk_right(looped(FELIX), until=6500, release_at=4000),
    "long hold-up": lambda: walk_right(held(m30=1500), until=8500, release_at=6500),
}


@functools.lru_cache(maxsize=None)
def scenario(name):
    return SCENARIOS[name]()


@functools.lru_cache(maxsize=None)
def played(name, fps=60, search="", bridge=True, ask=None):
    return scenario(name).run(fps=fps, search=search, bridge=bridge, ask=list(ask) if ask else None)


def xs(frames):
    return [place(frame)[0] for frame in frames]


# ---- a. Messages on time ---------------------------------------------------------------


def test_with_messages_on_time_no_step_is_ever_bridged_also_not_at_the_stop():
    result = played("on time")
    assert result["bridge"]["on"] is True
    assert result["bridge"]["steps"] == 0
    assert result["bridge"]["takenBack"] == 0
    # The walk was drawn and ended on the server's position.
    assert place(result["frames"][-1]) == pytest.approx(scenario("on time").server_place())
    assert place(result["frames"][-1])[0] > OPEN_START[0] + 300


def test_with_messages_on_time_every_frame_is_the_same_as_without_the_bridge():
    # On time the playback delay of everybody is the smallest one already,
    # which is the own character's delay with the bridge: nothing differs.
    assert played("on time")["frames"] == played("on time", search="?bridge=off")["frames"]


@pytest.mark.parametrize("release_at", range(3000, 3068, 4))
def test_an_ordinary_stop_at_any_moment_of_the_servers_tick_bridges_nothing(release_at):
    # At a stop the own queue runs empty too, and one input lag ago the key
    # was still held. A step made up then walks the character on and brings
    # it back a second later: it happened in a third of these stops before
    # released keys were kept from starting a bridge.
    stop = walk_right(on_time(), until=5000, release_at=release_at)
    result = stop.run()
    assert result["bridge"]["steps"] == 0
    assert way_back(result["frames"], RIGHT) == 0
    assert place(result["frames"][-1]) == pytest.approx(stop.server_place())


def test_with_messages_a_little_late_nothing_is_bridged_and_only_the_own_delay_differs():
    with_bridge = played("a little late")
    without = played("a little late", search="?bridge=off")
    assert with_bridge["bridge"]["steps"] == 0
    # What differs is the own delay: with the bridge the own character is
    # played at the smallest delay (110 ms), without it at the one that
    # grows with the gaps (here about 125 ms). So it is drawn a little
    # further along its walk in every frame, never behind, by at most the
    # way of that difference in time, and it ends on the same place.
    ahead = [a - b for a, b in zip(xs(with_bridge["frames"]), xs(without["frames"]))]
    assert min(ahead) >= -EXACT
    assert 0.5 < max(ahead) < 3
    assert place(with_bridge["frames"][-1]) == place(without["frames"][-1])


# ---- b. One message 105 ms late every 410 ms ---------------------------------------------


def test_with_felix_bunched_messages_no_frame_is_frozen_while_the_key_is_held():
    frames = played("felix")["frames"]
    assert len(between(frames, SETTLED)) > 380
    assert frozen(frames, SETTLED) == []
    # Without the bridge the own character runs at the smallest delay no
    # longer, and at the growing one the picture stopped now and then.


def test_with_felix_bunched_messages_the_speed_stays_between_80_and_100():
    drawn_speeds = speeds(played("felix")["frames"], SETTLED)
    assert min(drawn_speeds) >= 80, min(drawn_speeds)
    assert max(drawn_speeds) <= 100, max(drawn_speeds)


def test_with_felix_bunched_messages_steps_are_bridged_and_none_needs_a_correction():
    numbers = played("felix")["bridge"]
    assert numbers["steps"] >= 10  # about one per 410 ms
    assert numbers["replaced"] >= numbers["steps"] - 1
    # The bridge walks as far per step as the server did lately: its steps
    # end where the server's do.
    assert numbers["corrections"] == 0
    assert numbers["takenBack"] == 0


@pytest.mark.parametrize("name", ["felix, uneven ticks", "hold-ups, uneven ticks", "bad second, uneven ticks"])
def test_with_ticks_of_uneven_length_every_correction_is_small_and_the_walk_as_smooth(name):
    # The server measures the time since its last tick; its steps are 6.0
    # to 6.2 units long. The bridge walks the usual length, so a bridged
    # step ends up to a fifth of a unit from the server's.
    result = played(name)
    numbers = result["bridge"]
    assert numbers["steps"] >= 10
    assert 0 < numbers["corrections"] <= numbers["replaced"]
    assert 0.05 < numbers["largestCorrection"] < 1.5
    assert numbers["largeCorrections"] == 0
    frames = result["frames"]
    assert frozen(frames, SETTLED) == []
    assert way_back(frames, RIGHT) == 0
    drawn_speeds = speeds(frames, SETTLED)
    low, high = (80, 100) if name.startswith("felix") else (60, 120)
    assert low <= min(drawn_speeds) and max(drawn_speeds) <= high, (min(drawn_speeds), max(drawn_speeds))


def test_with_felix_bunched_messages_the_character_never_moves_backwards():
    assert way_back(played("felix")["frames"], RIGHT) == 0


# ---- c. Hold-ups of 620 and 240 ms, and the bad second -------------------------------------


@pytest.mark.parametrize("name", ["hold-ups", "bad second"])
def test_through_hold_ups_no_frame_is_frozen_while_the_key_is_held(name):
    frames = played(name)["frames"]
    assert len(between(frames, SETTLED)) > 380
    assert frozen(frames, SETTLED) == []


@pytest.mark.parametrize("name", ["hold-ups", "bad second"])
def test_through_hold_ups_the_character_never_moves_backwards(name):
    frames = played(name)["frames"]
    assert all(b >= a - EXACT for a, b in zip(xs(frames), xs(frames)[1:]))


@pytest.mark.parametrize("name", ["hold-ups", "bad second"])
def test_through_hold_ups_the_speed_stays_between_60_and_120(name):
    drawn_speeds = speeds(played(name)["frames"], SETTLED)
    assert min(drawn_speeds) >= 60, min(drawn_speeds)
    assert max(drawn_speeds) <= 120, max(drawn_speeds)


def test_the_scenario_really_holds_messages_up_and_without_the_bridge_the_character_stands():
    hold_ups = scenario("hold-ups")
    gaps = [b[0] - a[0] for a, b in zip(hold_ups.messages[1:], hold_ups.messages[2:])]
    assert max(gaps) == pytest.approx(620 + SERVER_TICK)
    assert sum(1 for gap in gaps if 300 < gap < 320) == 4  # 240 ms + one tick
    without = played("hold-ups", search="?bridge=off")
    assert without["bridge"]["steps"] == 0
    assert len(frozen(without["frames"], SETTLED)) > 30


def test_during_the_long_hold_up_the_character_walks_at_the_servers_speed():
    hold_ups = scenario("hold-ups")
    frames = played("hold-ups")["frames"]
    # From 200 ms after the last message before the hold-up to its end.
    start = hold_ups.arrival(LONG_HOLD_UP_MESSAGE - 1) + 200
    end = hold_ups.arrival(LONG_HOLD_UP_MESSAGE) - 1
    assert end - start > 400
    drawn_speeds = speeds(frames, start, end)
    # A bridged step is as long as the server's and is drawn over one tick of the browser.
    assert all(speed == pytest.approx(SERVER_STEP / (TICK / 1000), rel=0.01) for speed in drawn_speeds)


# ---- d. A hold-up longer than the bridge may cover ------------------------------------------


def test_in_a_hold_up_of_a_second_and_a_half_the_character_walks_on_ten_steps_then_stands():
    long_one = scenario("long hold-up")
    frames = played("long hold-up")["frames"]
    last_before = long_one.arrival(29)
    arrives = long_one.arrival(30)
    assert arrives - last_before == pytest.approx(1500 + SERVER_TICK)

    stood = frozen(frames, last_before, arrives)
    # It walked on for about 700 ms: ten steps of one tick after the queue
    # ran dry (about 100 ms after the last message).
    assert 700 < stood[0] - last_before < 830
    # From then on it stood until the messages arrived, ten bridged steps
    # beyond the newest position that had arrived.
    assert stood == [frame["t"] for frame in between(frames, stood[0], arrives)]
    known = long_one.known_place(arrives - 1)
    standing_at = place(between(frames, stood[0], arrives)[-1])
    assert standing_at == pytest.approx((known[0] + 10 * SERVER_STEP, known[1]))


def test_after_a_hold_up_longer_than_the_bridge_the_character_goes_on_without_going_back():
    long_one = scenario("long hold-up")
    result = played("long hold-up")
    frames = result["frames"]
    assert result["bridge"]["steps"] == 10
    assert result["bridge"]["replaced"] == 10
    assert result["bridge"]["takenBack"] == 0
    # The server walked further than the bridge: never backwards.
    assert all(b >= a - EXACT for a, b in zip(xs(frames), xs(frames)[1:]))
    # It moves again in the first frames after the arrival, and ends on the server's position.
    arrives = long_one.arrival(30)
    assert frozen(frames, arrives + 2 * 1000 / 60, arrives + 600) == []
    assert place(frames[-1]) == pytest.approx(long_one.server_place())


# ---- e. The key is released in the middle of a hold-up ----------------------------------------

RELEASES = range(3150, 3420, 30)  # message 30 is sent at 3073 and held until 3698


def released_in_a_hold_up(release_at, **more):
    # By the time of the server's tick, not by the number of the message:
    # with a second player the server sends from the start.
    return walk_right(held_from(3073, 600), until=6500, release_at=release_at, **more)


@pytest.mark.parametrize("release_at", RELEASES)
def test_released_in_a_hold_up_the_character_stops_within_one_tick_of_the_server(release_at):
    stop = released_in_a_hold_up(release_at)
    frames = stop.run()["frames"]
    arrives = stop.arrival(30)
    assert stop.arrival(29) < 3150 and arrives == pytest.approx(3698)
    # It stands before the held messages arrive ...
    assert frozen(frames, arrives - 100, arrives - 1) == [frame["t"] for frame in between(frames, arrives - 100, arrives - 1)]
    # ... at most one step of the server from where the server stopped.
    standing_at = place(between(frames, 0, arrives - 1)[-1])
    assert math.dist(standing_at, stop.server_place()) <= SERVER_STEP + 0.6


@pytest.mark.parametrize("release_at", RELEASES)
def test_released_in_a_hold_up_the_character_ends_exactly_on_the_servers_position(release_at):
    stop = released_in_a_hold_up(release_at)
    frames = stop.run()["frames"]
    arrives = stop.arrival(30)
    final = stop.server_place()
    late = between(frames, arrives + 1200)
    assert len(late) > 60
    for frame in late:
        assert math.dist(place(frame), final) <= 0.05, frame["t"]
    assert place(frames[-1]) == pytest.approx(final, abs=EXACT)
    # One made-up step at most is taken back.
    assert way_back(frames, RIGHT) <= 7


def test_some_releases_in_a_hold_up_walk_one_step_too_far_and_take_it_back():
    # The measured input lag is known to within one tick only (the start
    # delay it is made of contains the wait for the server's tick). So the
    # character may walk one step further than the server; the step is
    # taken back a second after the last sign of life.
    taken_back = []
    for release_at in RELEASES:
        stop = released_in_a_hold_up(release_at)
        result = stop.run()
        numbers = result["bridge"]
        assert numbers["steps"] - numbers["replaced"] in (0, 1)
        assert numbers["takenBack"] == numbers["steps"] - numbers["replaced"]
        taken_back.append(numbers["takenBack"])
    assert 0 < sum(taken_back) < len(taken_back)


# ---- f. The player turns in the middle of a hold-up ------------------------------------------

TURNS = range(1500, 1800, 40)  # message 6 is sent at 1421 and held until 2046


def turned_in_a_hold_up(turn_at, **more):
    """Right, then down from `turn_at` on (both keys change at the same instant), in an open square."""
    keys = [(KEY_AT, "down", "KeyD"), (turn_at, "up", "KeyD"), (turn_at, "down", "KeyS"), (2300, "up", "KeyS")]
    return Scenario(keys, held_from(1421, 600), until=4500, start=open_square(120), **more)


def test_the_turn_scenario_turns_in_the_open_in_the_middle_of_the_hold_up():
    turn = turned_in_a_hold_up(1620)
    assert turn.arrival(5) < 1500 and turn.arrival(6) > 1800 + 200
    path = turn.server_path()
    # Every step of the server is a full one: no wall is met.
    lengths = [math.dist(a, b) for a, b in zip(path, path[1:])]
    assert all(length == pytest.approx(SERVER_STEP) for length in lengths)
    assert path[-1][0] > path[0][0] + 30 and path[-1][1] > path[0][1] + 30


@pytest.mark.parametrize("turn_at", TURNS)
def test_a_turn_in_a_hold_up_is_corrected_by_one_step_at_most(turn_at):
    turn = turned_in_a_hold_up(turn_at)
    result = turn.run()
    frames = result["frames"]
    # The bridge may take one step in the old direction that the server
    # took in the new one: a diagonal of two steps, 6.1 x 1.41 = 8.6 units.
    assert result["bridge"]["largestCorrection"] <= 9
    assert result["bridge"]["largeCorrections"] <= 1
    # It never moves against the old or the new direction by more than that.
    assert way_back(frames, RIGHT) <= 9
    assert way_back(frames, DOWN) <= 9


@pytest.mark.parametrize("turn_at", TURNS)
def test_after_a_turn_in_a_hold_up_the_character_is_on_the_servers_path_and_ends_on_its_position(turn_at):
    turn = turned_in_a_hold_up(turn_at)
    frames = turn.run()["frames"]
    path = turn.server_path()
    for frame in between(frames, turn.arrival(6) + 300):
        assert distance_to_path(place(frame), path) <= 0.1, frame["t"]
    assert place(frames[-1]) == pytest.approx(turn.server_place(), abs=EXACT)


def test_some_turns_in_a_hold_up_need_a_correction_and_some_do_not():
    large = [turned_in_a_hold_up(turn_at).run()["bridge"]["largeCorrections"] for turn_at in TURNS]
    assert 0 < sum(large) < len(large)


# ---- l. The other players are drawn as before --------------------------------------------------


def others(frames):
    return [drawn(frame, OTHER_CHARACTER) for frame in frames]


@pytest.mark.parametrize("name", ["felix, two players", "hold-ups, two players", "bad second, two players"])
def test_another_player_in_the_same_messages_is_drawn_exactly_as_without_the_bridge(name):
    with_bridge = played(name)
    without = played(name, search="?bridge=off")
    assert with_bridge["bridge"]["steps"] > 0
    assert len(with_bridge["frames"]) == len(without["frames"]) > 400
    assert others(with_bridge["frames"]) == others(without["frames"])
    assert all(other is not None for other in others(with_bridge["frames"]))


def test_another_player_is_drawn_as_before_also_through_a_release_and_a_turn_in_a_hold_up():
    for build in [lambda **more: released_in_a_hold_up(3240, **more), lambda **more: turned_in_a_hold_up(1620, **more)]:
        walk = build(other=SOMEBODY)
        with_bridge = walk.run()
        without = walk.run(search="?bridge=off")
        assert with_bridge["bridge"]["steps"] > 0
        assert others(with_bridge["frames"]) == others(without["frames"])


@pytest.mark.parametrize("name", ["felix, two players", "hold-ups, two players"])
def test_with_another_player_walking_the_own_character_is_as_smooth(name):
    # With somebody else walking, the server sends on every tick, also the
    # ticks in which the own player does not move.
    frames = played(name)["frames"]
    assert frozen(frames, SETTLED) == []
    assert way_back(frames, RIGHT) == 0


# ---- m. Switched off, or bridge.js not loaded ---------------------------------------------------


@pytest.mark.parametrize("name", ["felix", "hold-ups", "bad second", "hold-ups, two players"])
def test_switched_off_every_frame_is_the_same_as_without_bridge_js(name):
    # Without bridge.js the world runs the code it had before this to-do.
    switched_off = played(name, search="?bridge=off")
    not_loaded = played(name, bridge=False)
    assert switched_off["frames"] == not_loaded["frames"]
    assert len(switched_off["frames"]) > 400
    assert switched_off["bridge"]["steps"] == 0
    assert switched_off["bridge"]["on"] is False
    assert not_loaded["bridge"] == {"on": False, "loaded": False}


@pytest.mark.parametrize("search", ["?bridge=off", "?debug&bridge=off", "?bridge=off&x=1"])
def test_bridge_off_in_the_address_switches_the_bridge_off(search):
    assert played("hold-ups", search=search)["bridge"]["on"] is False


@pytest.mark.parametrize("search", ["", "?debug", "?bridge", "?bridge=on", "?bridge=offf", "?nobridge=off"])
def test_any_other_address_leaves_the_bridge_on(search):
    assert played("felix", search=search)["bridge"]["on"] is True


def test_what_the_world_tells_the_server_is_the_same_with_and_without_the_bridge():
    # The bridge sends nothing: the server hears the keys, as before.
    assert played("felix, then a stop")["moves"] == played("felix, then a stop", search="?bridge=off")["moves"]
    assert played("felix, then a stop")["moves"] == [[KEY_AT, 1, 0], [4000, 0, 0]]


# ---- The own delay ---------------------------------------------------------------------------------


def first_move(frames, after):
    return next(frame["t"] for before, frame in pairs(frames, after) if math.dist(place(before), place(frame)) >= 0.01)


def last_move(frames):
    return [frame["t"] for before, frame in pairs(frames, 0) if math.dist(place(before), place(frame)) >= 0.01][-1]


def test_with_the_bridge_the_own_character_follows_the_keys_sooner():
    # Without the bridge the delay grows with the gaps between the messages
    # (about 190 ms on this connection); with it the own character is
    # played at the smallest delay.
    with_bridge = played("felix, then a stop")["frames"]
    without = played("felix, then a stop", search="?bridge=off")["frames"]
    assert first_move(with_bridge, KEY_AT) == first_move(without, KEY_AT)  # the first step starts when it arrives
    # Once the first gaps have been seen, it is further along, and after
    # the release it stands sooner.
    later = between(with_bridge, KEY_AT + 2500)[0], between(without, KEY_AT + 2500)[0]
    assert place(later[0])[0] > place(later[1])[0] + 3
    assert last_move(with_bridge) < last_move(without) - 50
    assert place(with_bridge[-1]) == place(without[-1])


# ---- n. ownDrawnPosition: what the frame draws, also in a frame that bridges -----------------------

ASKED_AT_THE_FRAME = (0,)
ASKED_AT_OTHER_TIMES = (0, 40, 500, 5000, -30)


def assert_asked_is_drawn(frames):
    for frame in frames:
        if frame["t"] > FIRST_FRAME:  # from the first position on
            asked = frame["asked"][0]
            assert math.dist((asked["x"], asked["y"]), place(frame)) < EXACT, frame["t"]


@pytest.mark.parametrize("name", ["felix", "hold-ups", "bad second", "long hold-up"])
def test_asked_before_a_frame_the_own_position_is_what_that_frame_draws(name):
    result = played(name, ask=ASKED_AT_THE_FRAME)
    assert result["bridge"]["steps"] > 0
    assert len(result["frames"]) > 400
    assert_asked_is_drawn(result["frames"])


def test_asked_before_a_frame_the_own_position_is_right_through_a_release_and_a_turn_in_a_hold_up():
    for walk in [released_in_a_hold_up(3180), released_in_a_hold_up(3240), turned_in_a_hold_up(1540), turned_in_a_hold_up(1620)]:
        result = walk.run(ask=list(ASKED_AT_THE_FRAME))
        # These walks have a step taken back or a wrong guess corrected.
        assert result["bridge"]["takenBack"] + result["bridge"]["largeCorrections"] == 1
        assert_asked_is_drawn(result["frames"])


@pytest.mark.parametrize("name", ["felix", "hold-ups", "bad second", "long hold-up"])
def test_asking_for_the_own_position_leaves_every_frame_and_every_count_as_it_was(name):
    never_asked = played(name)
    # Asked for the time of the frame, for later times (a frame at those
    # times would bridge more steps) and for an earlier one.
    asked = played(name, ask=ASKED_AT_OTHER_TIMES)
    for frame in asked["frames"]:
        del frame["asked"]
    for frame in never_asked["frames"]:
        frame.pop("asked", None)
    assert asked["frames"] == never_asked["frames"]
    assert asked["bridge"] == never_asked["bridge"]


def test_asking_leaves_a_release_and_a_turn_in_a_hold_up_as_they_were():
    for walk in [released_in_a_hold_up(3180), turned_in_a_hold_up(1540)]:
        never_asked = walk.run()
        asked = walk.run(ask=list(ASKED_AT_OTHER_TIMES))
        assert [place(frame) for frame in asked["frames"]] == [place(frame) for frame in never_asked["frames"]]
        assert asked["bridge"] == never_asked["bridge"]


# ---- o. The feet ------------------------------------------------------------------------------------


def own(frame):
    return drawn(frame, OWN_CHARACTER)


@pytest.mark.parametrize("name", ["felix", "hold-ups", "bad second"])
def test_through_hold_ups_the_run_of_the_feet_goes_on_without_a_break(name):
    frames = played(name)["frames"]
    walking = between(frames, SETTLED)
    # Full steps in every frame: the feet never begin to stop.
    assert all(own(frame)["stride"] == 1 for frame in walking)
    # The cycle of the feet moves on exactly with the way the drawn
    # character covers, in every frame, also in a bridged one.
    for before, frame in pairs(frames, SETTLED):
        covered = math.dist(place(before), place(frame)) / WALK_CYCLE
        advanced = (own(frame)["walkPhase"] - own(before)["walkPhase"]) % 1
        assert advanced == pytest.approx(covered, abs=1e-9), frame["t"]


def test_a_bridged_step_keeps_the_side_the_character_faces():
    # Walking to the left through the hold-ups: mirrored in every frame.
    keys = [(KEY_AT, "down", "KeyA")]
    start = (OPEN_START[0] + OPEN_LENGTH, OPEN_START[1])
    frames = Scenario(keys, HOLD_UPS, until=WALK_UNTIL, start=start).run()["frames"]
    assert frozen(frames, SETTLED) == []
    assert all(own(frame)["mirrored"] is True for frame in between(frames, SETTLED))


def test_a_correction_does_not_turn_the_character_and_does_not_restart_its_feet():
    # Right, then down: the bridge walks one step too far to the right and
    # is corrected to the left by almost a step. The character never faces left.
    turn = turned_in_a_hold_up(1620)
    result = turn.run()
    frames = result["frames"]
    assert result["bridge"]["largeCorrections"] == 1
    assert way_back(frames, RIGHT) > 5
    assert all(own(frame)["mirrored"] is False for frame in frames)
    # The feet run on through the correction: full steps, and the cycle
    # moves on with the way covered. (Where the way bends between two
    # frames, it is a little longer than the straight line between them.)
    walking = pairs(frames, SETTLED, 2300)
    assert all(own(frame)["stride"] == 1 for _, frame in walking)
    for before, frame in walking:
        straight = math.dist(place(before), place(frame)) / WALK_CYCLE
        advanced = (own(frame)["walkPhase"] - own(before)["walkPhase"]) % 1
        assert straight - 1e-9 <= advanced <= 1.5 * straight + 1e-9, frame["t"]


def test_a_step_that_is_taken_back_does_not_turn_the_character_or_move_its_feet():
    stop = released_in_a_hold_up(3180)
    result = stop.run()
    frames = result["frames"]
    assert result["bridge"]["takenBack"] == 1
    moved_back = [frame for before, frame in pairs(frames, 0) if place(frame)[0] < place(before)[0] - EXACT]
    assert len(moved_back) >= 3  # it glides back over one tick
    for frame in moved_back:
        assert own(frame)["mirrored"] is False
        assert own(frame)["stride"] == 0 and own(frame)["walkPhase"] is None


# ---- p. Frame rates -----------------------------------------------------------------------------------


def places_by_time(frames):
    return {round(frame["t"], 6): place(frame) for frame in frames}


@pytest.mark.parametrize("name", ["felix", "hold-ups", "bad second"])
@pytest.mark.parametrize("fps", [30, 120, 144])
def test_the_path_is_the_same_at_every_frame_rate(name, fps):
    at_60 = places_by_time(played(name)["frames"])
    at_fps = places_by_time(played(name, fps=fps)["frames"])
    together = sorted(set(at_60) & set(at_fps))
    # 30 and 120 frames per second share every frame of the slower one with
    # 60; 144 shares one frame in six (every 100 ms).
    assert len(together) > 60
    for time in together:
        assert math.dist(at_60[time], at_fps[time]) <= 0.05, time


@pytest.mark.parametrize("fps", [30, 120, 144])
def test_the_bridge_counts_the_same_at_every_frame_rate(fps):
    assert played("hold-ups", fps=fps)["bridge"] == played("hold-ups")["bridge"]


@pytest.mark.parametrize("fps", [30, 144])
def test_at_other_frame_rates_no_frame_is_frozen_and_none_goes_backwards(fps):
    for name in ["felix", "hold-ups", "bad second"]:
        frames = played(name, fps=fps)["frames"]
        assert frozen(frames, SETTLED) == []
        assert way_back(frames, RIGHT) == 0
