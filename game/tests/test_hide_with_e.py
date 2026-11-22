"""Hiding with the key E (M3-1.6, S-191).

A living Free Rider in a Classic round who stands within reach (`use_range`,
25) of a hiding spot presses E: the browser sends `hide`. The server puts
him on the spot's centre, he stands still and is hidden: no living High
Performer is sent his position, however near (S-192). He himself, the other
Free Riders and the ghosts still get him, with `"hidden": true`. Standing in a
spot no longer hides by itself. A step, E again (`leave_hiding`), a meeting
and leaving the lobby end hiding. While hidden he cannot fail, report or
call the emergency meeting. Only he is told whether he hides
(`classic_hiding`), never anybody else.

The plain rules are in `server/classic/hiding.py`, the state in
`ClassicRound.hidden`, the handlers in `server/main.py`.
"""

import json

import pytest

from server import main, protocol
from server.classic import hiding
from server.classic.round import ClassicRound, HideRefused
from server.main import app
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_server_features import classic_for, player
from test_server_hiding import (
    CAMPUS, FOUR, SIX, SPOT, classic_round, names_in, next_positions, positions_arrived, positions_now,
)
from test_server_duel import REAL_TICK, duel_of, lobby_of

CENTRE = (float(SPOT["x"]), float(SPOT["y"]))
REACH = CAMPUS["use_range"]
ROLES = {"fr": "FR", "hp": "HP", "hp2": "HP", "hp3": "HP"}


def below_the_spot(distance):
    """A free place `distance` units below the hedge spot's centre (the deck below the hedge)."""
    return (CENTRE[0], CENTRE[1] + distance)


def answer(connection, kinds=("error", "classic_hiding")):
    """The next message of one of `kinds`; positions and the like are skipped."""
    while True:
        message = connection.receive_json()
        if message["type"] in kinds:
            return message


def press_hide(connections, name):
    """Send `hide` and return the answer. After a hide, every member is sent
    the positions at once; those messages are read here, so that the next
    `positions_now` gets fresh ones."""
    connections[name].send_json({"type": "hide"})
    reply = answer(connections[name])
    if reply == {"type": "classic_hiding", "hidden": True}:
        for connection in connections.values():
            next_positions(connection)
    return reply


def hidden_in_the_spot(connect, names=FOUR):
    """A Classic round whose Free Rider pressed E beside the hedge and hides."""
    connections, free_riders, high_performers = classic_round(connect, names)
    put(free_riders[0], below_the_spot(15))
    assert press_hide(connections, free_riders[0]) == {"type": "classic_hiding", "hidden": True}
    return connections, free_riders, high_performers


# ---- The plain rules ------------------------------------------------------


def test_the_reach_is_the_maps_use_range():
    assert hiding.HIDE_REACH_KEY == "use_range" and REACH == 25


@pytest.mark.parametrize("distance,found", [(0, True), (9, True), (24.99, True), (25, True), (25.01, False), (60, False)])
def test_a_spot_is_in_reach_up_to_the_use_range_included(distance, found):
    assert (hiding.spot_in_reach(CAMPUS, below_the_spot(distance)) is SPOT) is found


def test_no_position_has_no_spot_in_reach():
    assert hiding.spot_in_reach(CAMPUS, None) is None


def test_the_nearest_spot_in_reach_wins():
    campus = {"use_range": 25, "hiding_spots": [{"x": 0, "y": 0, "r": 9}, {"x": 30, "y": 0, "r": 9}]}
    assert hiding.spot_in_reach(campus, (20, 0)) is campus["hiding_spots"][1]
    assert hiding.spot_in_reach(campus, (15, 0)) is campus["hiding_spots"][0]  # a tie: the first one


def test_a_living_free_rider_in_reach_during_the_round_may_hide():
    assert hiding.hide_refusal(ROLES, set(), "round", "fr", below_the_spot(20), CAMPUS) is None


@pytest.mark.parametrize("player,ghosts,phase", [
    ("hp", set(), "round"),          # a High Performer
    ("fr", {"fr"}, "round"),         # a Free Rider who is a ghost
    ("fr", set(), "meeting"),        # in a meeting
    ("fr", set(), "result"),         # after the result
    ("stranger", set(), "round"),    # not in the round
])
def test_nobody_else_may_hide(player, ghosts, phase):
    assert hiding.hide_refusal(ROLES, ghosts, phase, player, CENTRE, CAMPUS) == "hide_rejected"


def test_a_free_rider_out_of_reach_is_told_to_walk_up():
    assert hiding.hide_refusal(ROLES, set(), "round", "fr", below_the_spot(26), CAMPUS) == "hide_out_of_reach"
    assert hiding.hide_refusal(ROLES, set(), "round", "fr", None, CAMPUS) == "hide_out_of_reach"


@pytest.mark.parametrize("action", ["fail", "report", "emergency"])
def test_a_hidden_player_must_step_out_for_fail_report_and_emergency(action):
    assert hiding.blocked_while_hidden(action, "fr", {"fr": SPOT}) is True
    assert hiding.blocked_while_hidden(action, "fr", {}) is False


def test_other_actions_are_not_blocked_while_hidden():
    assert hiding.blocked_while_hidden("chat", "fr", {"fr": SPOT}) is False


# ---- The round's state ----------------------------------------------------


class FixedRandom:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        pass

    def choice(self, items):
        return items[0]


def a_round():
    classic = ClassicRound(["fr", "hp", "hp2", "hp3"], range(1, 13), FixedRandom())
    classic.roles = dict(ROLES)
    return classic


def test_the_round_remembers_who_hides_and_forgets_when_he_steps_out():
    classic = a_round()
    assert classic.hide("fr", below_the_spot(10), CAMPUS) is SPOT
    assert classic.is_hidden("fr")
    assert classic.leave_hiding("fr") is True
    assert classic.leave_hiding("fr") is False
    assert classic.hidden == {}


def test_hiding_twice_keeps_the_first_spot():
    classic = a_round()
    classic.hide("fr", below_the_spot(10), CAMPUS)
    assert classic.hide("fr", (20.0, 20.0), CAMPUS) is SPOT


def test_a_refused_hide_changes_nothing():
    classic = a_round()
    with pytest.raises(HideRefused) as refused:
        classic.hide("hp", CENTRE, CAMPUS)
    assert refused.value.code == "hide_rejected"
    assert classic.hidden == {}


def test_leaving_the_round_ends_hiding():
    classic = a_round()
    classic.hide("fr", CENTRE, CAMPUS)
    classic.remove_player("fr")
    assert classic.hidden == {}


def test_ending_all_hiding_tells_who_hid():
    classic = a_round()
    classic.hide("fr", CENTRE, CAMPUS)
    assert classic.end_all_hiding() == ["fr"]
    assert classic.hidden == {}


# ---- Through the real server: accepted -----------------------------------


def test_pressing_e_beside_the_hedge_puts_him_in_the_spot_hidden_and_standing_still(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    lobby = app.state.lobbies.lobby_of(fr)
    assert lobby.walkers.position_of(fr) == CENTRE
    assert (lobby.walkers._walkers[fr].dx, lobby.walkers._walkers[fr].dy) == (0, 0)
    assert classic_for(fr).hidden == {fr: SPOT}
    assert fr not in names_in(positions_now(connections)[far])


def test_standing_in_a_spot_without_pressing_e_does_not_hide(connect):
    connections, [fr], [far, _, _] = classic_round(connect)
    put(fr, CENTRE)
    assert fr in names_in(positions_now(connections)[far])


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_spot_can_be_hidden_in(connect, index):
    connections, [fr], high_performers = classic_round(connect)
    spot = CAMPUS["hiding_spots"][index]
    put(fr, (spot["x"], spot["y"]))
    assert press_hide(connections, fr) == {"type": "classic_hiding", "hidden": True}
    told = positions_now(connections)
    for name in high_performers:
        assert fr not in names_in(told[name])


def test_no_high_performer_gets_him_however_near(connect):
    connections, [fr], [beside, at_35, beyond] = hidden_in_the_spot(connect)
    put(beside, (CENTRE[0] + 1, CENTRE[1]))
    put(at_35, (CENTRE[0] + 35, CENTRE[1]))
    put(beyond, (CENTRE[0] + 35.5, CENTRE[1]))
    told = positions_now(connections)
    for name in (beside, at_35, beyond):
        assert fr not in names_in(told[name])


def test_no_message_to_a_living_high_performer_carries_the_hidden_flag(connect):
    connections, [fr], high_performers = hidden_in_the_spot(connect)
    told = positions_now(connections)
    for name in high_performers:
        assert all(set(entry) == {"name", "x", "y"} for entry in told[name]["players"])
        assert "hidden" not in json.dumps(told[name])
    # He himself is told, and only about himself.
    assert [entry["name"] for entry in told[fr]["players"] if entry.get("hidden")] == [fr]


def test_only_the_free_rider_is_told_and_the_others_get_no_trace(connect):
    connections, [fr], high_performers = classic_round(connect)
    put(fr, below_the_spot(5))
    connections[fr].send_json({"type": "hide"})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": True}
    lobby = app.state.lobbies.lobby_of(fr)
    connections[fr].portal.call(REAL_TICK, 0.0)
    for name in high_performers:
        # What the hide sent them: positions without him, and nothing else.
        message = next_positions(connections[name])
        assert "classic_hiding" not in json.dumps(message)
        assert fr not in json.dumps(message)
    assert lobby.walkers.position_of(fr) == CENTRE


def test_the_second_free_rider_and_ghosts_still_see_him(connect):
    connections, [first, second], [ghost, *living] = classic_round(connect, SIX)
    classic_for(first).eliminated = {ghost}
    put(first, CENTRE)
    assert press_hide(connections, first)["hidden"] is True
    told = positions_now(connections)
    assert first in names_in(told[second])
    assert first in names_in(told[ghost])
    for name in living:
        assert first not in names_in(told[name])


# ---- Ending hiding --------------------------------------------------------


def test_a_step_ends_hiding_and_he_is_sent_again(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    connections[fr].send_json({"type": "move", "dx": 0, "dy": 1})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": False}
    assert classic_for(fr).hidden == {}
    assert fr in names_in(positions_now(connections)[far])


def test_letting_go_of_every_key_does_not_end_hiding(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    connections[fr].send_json({"type": "move", "dx": 0, "dy": 0})
    assert fr not in names_in(positions_now(connections)[far])
    assert classic_for(fr).is_hidden(fr)


def test_e_again_ends_hiding(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    connections[fr].send_json({"type": "leave_hiding"})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": False}
    assert fr in names_in(positions_now(connections)[far])


def test_leaving_hiding_when_not_hidden_is_quietly_ignored(connect):
    connections, [fr], _ = classic_round(connect)
    connections[fr].send_json({"type": "leave_hiding"})
    connections[fr].send_json({"type": "hello", "name": "Reader"})
    assert answer(connections[fr], ("error", "classic_hiding", "welcome"))["type"] == "welcome"


def test_a_meeting_ends_hiding_and_tells_him(connect, clock):
    connections, [fr], [caller, far, _] = hidden_in_the_spot(connect)
    button = CAMPUS["button"]
    put(caller, (button["x"], button["y"]))
    clock.wait(46)
    connections[caller].send_json({"type": "emergency"})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": False}
    assert classic_for(fr).hidden == {}
    assert classic_for(fr).phase == "meeting"


def test_a_report_ends_hiding_and_tells_him(connect, clock):
    connections, [fr], [victim, reporter, far] = classic_round(connect)
    # He fails a High Performer first (not hidden), then hides.
    put(fr, below_the_spot(15))
    put(victim, below_the_spot(18))
    connections[fr].send_json({"type": "fail"})
    sheet = answer(connections[reporter], ("classic_fail",))
    assert press_hide(connections, fr) == {"type": "classic_hiding", "hidden": True}
    put(reporter, (sheet["position"]["x"], sheet["position"]["y"]))
    connections[reporter].send_json({"type": "report", "sheet_id": sheet["sheet_id"], "position": sheet["position"]})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": False}
    assert classic_for(fr).phase == "meeting"
    assert classic_for(fr).hidden == {}
    positions_arrived(connections[far])  # the older positions, sent while he hid
    assert fr in names_in(positions_now(connections)[far])


def test_leaving_the_lobby_while_hidden_ends_hiding_for_good(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    classic = classic_for(fr)
    connections[fr].send_json({"type": "leave_lobby"})
    answer(connections[fr], ("left_lobby", "error"))
    assert classic.hidden == {}


def test_hiding_twice_answers_hidden_and_changes_nothing(connect):
    connections, [fr], _ = hidden_in_the_spot(connect)
    connections[fr].send_json({"type": "hide"})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": True}
    assert classic_for(fr).hidden == {fr: SPOT}


def test_a_blocked_step_still_ends_hiding_and_everybody_is_told_again(connect):
    connections, [fr], [far, _, _] = hidden_in_the_spot(connect)
    lobby = app.state.lobbies.lobby_of(fr)
    for name in FOUR:
        lobby.walkers.mark_told(name)
    connections[fr].send_json({"type": "move", "dx": 1, "dy": 0})
    assert answer(connections[fr]) == {"type": "classic_hiding", "hidden": False}
    assert sorted(lobby.walkers.names_to_tell()) == sorted(FOUR)


def test_the_end_of_the_round_sends_him_to_everybody(connect):
    connections, [fr], [first, second, far] = hidden_in_the_spot(connect)
    lobby = app.state.lobbies.lobby_of(fr)
    lobby.classic_round.eliminated = {first, second}
    connections[fr].portal.call(main.tell_round_news, lobby)
    assert lobby.classic_round is None
    told = positions_now(connections)
    for name in FOUR:
        assert fr in names_in(told[name])


# ---- Rejected -------------------------------------------------------------


def test_a_high_performer_cannot_hide(connect):
    connections, _, [hp, _, _] = classic_round(connect)
    put(hp, CENTRE)
    assert press_hide(connections, hp) == protocol.rejection("hide_rejected")
    assert classic_for(hp).hidden == {}


def test_a_free_rider_out_of_reach_cannot_hide(connect):
    connections, [fr], _ = classic_round(connect)
    put(fr, below_the_spot(REACH + 1))
    assert press_hide(connections, fr) == protocol.rejection("hide_out_of_reach")
    assert app.state.lobbies.lobby_of(fr).walkers.position_of(fr) == below_the_spot(REACH + 1)


def test_a_free_rider_who_is_a_ghost_cannot_hide(connect):
    connections, [fr], _ = classic_round(connect)
    classic_for(fr).eliminated = {fr}
    put(fr, CENTRE)
    assert press_hide(connections, fr) == protocol.rejection("hide_rejected")


@pytest.mark.parametrize("phase", ["meeting", "result"])
def test_nobody_hides_during_a_meeting_or_its_result(connect, phase):
    connections, [fr], _ = classic_round(connect)
    classic_for(fr).phase = phase
    put(fr, CENTRE)
    assert press_hide(connections, fr) == protocol.rejection("hide_rejected")


def test_nobody_hides_in_the_lobby_or_in_a_duel(connect):
    connections, _code = lobby_of(connect, ["Mara", "Tiago"])
    put("Mara", CENTRE)
    assert press_hide(connections, "Mara") == protocol.rejection("hide_rejected")
    connections, _code = duel_of(connect, ["Ana", "Bea", "Caro"])
    put("Ana", CENTRE)
    assert press_hide(connections, "Ana") == protocol.rejection("hide_rejected")


@pytest.mark.parametrize("kind", ["hide", "leave_hiding"])
def test_hiding_needs_a_signed_in_player_in_a_lobby(connect, kind):
    alone = connect()
    alone.send_json({"type": kind})
    assert answer(alone) == protocol.rejection("not_signed_in")
    guest = player(connect, "Nobody")
    guest.send_json({"type": kind})
    assert answer(guest) == protocol.rejection("not_in_lobby")


@pytest.mark.parametrize("message", [
    {"type": "hide", "spot": 1},
    {"type": "leave_hiding", "now": True},
])
def test_a_hide_message_with_a_field_is_refused_by_the_protocol(message):
    with pytest.raises(protocol.ProtocolError) as refused:
        protocol.parse_client_message(json.dumps(message))
    assert refused.value.code == "unknown_field"


@pytest.mark.parametrize("message", [{"type": "fail"}, {"type": "emergency"},
                                     {"type": "report", "sheet_id": "f-sheet-1", "position": {"x": 595.0, "y": 249.0}}])
def test_a_hidden_free_rider_must_step_out_to_fail_report_or_call(connect, clock, message):
    connections, [fr], [hp, _, _] = hidden_in_the_spot(connect)
    put(hp, (CENTRE[0], CENTRE[1] + 3))  # in fail range
    clock.wait(46)
    connections[fr].send_json(message)
    assert answer(connections[fr]) == protocol.rejection("leave_hiding_first")
    assert classic_for(fr).is_hidden(fr)
    assert classic_for(fr).eliminated == set()
    assert classic_for(fr).phase == "round"
