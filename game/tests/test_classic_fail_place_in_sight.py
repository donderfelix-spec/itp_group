"""S-202 (M3-3.25): where an F-sheet lies only reaches those who may see it.

Rule 1 with limited vision (S-185): who failed stays public at once (S-159,
S-163, S-164), but the place of the sheet (the victim's position) goes only
to the Free Rider who did it, to the ghosts and to living players who have
the place in sight (range `classic_vision_range`, walls block). The others
are sent a `classic_sheet` once the place comes into their sight.
"""

import random

import pytest

from rules import FAIL_COOLDOWN_SECONDS
from server import main, protocol
from server.classic import round as classic_round_module
from server.classic import sheets
from server.classic.round import ClassicRound
from server.main import app
from server.world import visibility
from task_helpers import client, clock, connect, placeholder_at_every_station, put  # noqa: F401
from test_classic_leaving import wait_for_background_sends
import test_classic_meeting_once as meeting_once
from test_classic_meeting_once import everything_sent, read_until
from test_classic_server_features import classic_for, start_classic
from test_server_duel import REAL_TICK

CAMPUS = app.state.campus
RANGE = CAMPUS["classic_vision_range"]

SIX = ("Mara", "Tiago", "Ines", "Rui", "Luca", "Sofia")
FREE_RIDERS = {"Mara", "Sofia"}
ACTOR, VICTIM, NEAR, FAR, BEHIND_WALL, SECOND_FR = SIX
FR_PLACE = (200.0, 200.0)  # on the Main Deck, just below the lecture hall's wall
SHEET = (201.0, 200.0)  # where the victim stands
PLACES = {
    ACTOR: FR_PLACE,
    VICTIM: SHEET,
    NEAR: (260.0, 200.0),  # 59 units away, nothing between
    FAR: (400.0, 330.0),  # about 238 units away
    BEHIND_WALL: (201.0, 140.0),  # 60 units away, the lecture hall's wall between
    SECOND_FR: (100.0, 330.0),  # about 165 units away
}
SHEET_POSITION = {"x": SHEET[0], "y": SHEET[1]}


# The plain rules


def test_the_sight_rule_for_a_place_is_the_range_with_its_edge_and_no_wall():
    origin = (300.0, 400.0)
    assert visibility.place_in_sight(origin, origin, CAMPUS)
    assert visibility.place_in_sight(origin, (origin[0] + RANGE, origin[1]), CAMPUS)
    assert not visibility.place_in_sight(origin, (origin[0] + RANGE + 0.01, origin[1]), CAMPUS)
    assert not visibility.place_in_sight(PLACES[BEHIND_WALL], SHEET, CAMPUS)
    assert visibility.place_in_sight(PLACES[NEAR], SHEET, CAMPUS)


def test_the_places_of_this_test_are_what_their_names_say():
    for name in (ACTOR, VICTIM, NEAR):
        assert visibility.place_in_sight(PLACES[name], SHEET, CAMPUS), name
    for name in (FAR, BEHIND_WALL, SECOND_FR):
        assert not visibility.place_in_sight(PLACES[name], SHEET, CAMPUS), name


def test_a_ghost_has_every_sheet_in_view_in_the_order_they_were_issued():
    f_sheets = {"f-sheet-10": (900.0, 900.0), "f-sheet-2": SHEET, "f-sheet-1": (10.0, 10.0)}
    assert sheets.sheets_in_view(f_sheets, None, True, CAMPUS) == ["f-sheet-1", "f-sheet-2", "f-sheet-10"]


def test_a_living_player_has_only_the_sheets_in_his_sight_in_view():
    f_sheets = {"f-sheet-1": SHEET, "f-sheet-2": (900.0, 900.0)}
    assert sheets.sheets_in_view(f_sheets, PLACES[NEAR], False, CAMPUS) == ["f-sheet-1"]
    assert sheets.sheets_in_view(f_sheets, PLACES[BEHIND_WALL], False, CAMPUS) == []
    assert sheets.sheets_in_view(f_sheets, None, False, CAMPUS) == []  # not placed yet
    assert sheets.sheets_in_view({}, PLACES[NEAR], True, CAMPUS) == []


def test_a_sheet_already_told_is_not_told_again():
    f_sheets = {"f-sheet-1": SHEET, "f-sheet-2": (205.0, 200.0)}
    assert sheets.sheets_to_tell(f_sheets, PLACES[NEAR], False, {"f-sheet-1"}, CAMPUS) == ["f-sheet-2"]
    assert sheets.sheets_to_tell(f_sheets, PLACES[NEAR], False, set(f_sheets), CAMPUS) == []


def a_round_with_one_sheet():
    game = ClassicRound(list(SIX), [1, 2, 3, 4, 5], rng=random.Random(1))
    game.roles = {name: "FR" if name in FREE_RIDERS else "HP" for name in SIX}
    game.positions = dict(PLACES)
    sheet_id = game.fail(ACTOR, VICTIM, 1000.0, SHEET, "student-1")
    return game, sheet_id


def test_the_round_tells_each_sheet_once_with_its_character_and_report_state():
    game, sheet_id = a_round_with_one_sheet()
    assert game.sheet_news(FAR, PLACES[FAR], CAMPUS) == []
    assert game.sheet_news(FAR, PLACES[NEAR], CAMPUS) == [(sheet_id, SHEET, "student-1", False)]
    assert game.sheet_news(FAR, PLACES[NEAR], CAMPUS) == []
    game.meeting_triggers.add(f"report:{sheet_id}")
    assert game.sheet_news(BEHIND_WALL, PLACES[NEAR], CAMPUS) == [(sheet_id, SHEET, "student-1", True)]


def test_the_victim_is_a_ghost_and_may_know_every_sheet_wherever_he_is():
    game, sheet_id = a_round_with_one_sheet()
    assert game.may_know_sheet(VICTIM, (900.0, 900.0), sheet_id, CAMPUS)
    assert not game.may_know_sheet(FAR, PLACES[FAR], sheet_id, CAMPUS)
    assert not game.may_know_sheet(SECOND_FR, PLACES[SECOND_FR], sheet_id, CAMPUS)


def test_a_new_round_knows_no_sheets_and_has_told_nobody():
    game = ClassicRound(list(SIX), [1, 2, 3, 4, 5], rng=random.Random(1))
    assert game.f_sheets == {} and game.sheets_told == {}
    assert game.sheet_news(NEAR, PLACES[NEAR], CAMPUS) == []


def test_the_classic_sheet_message_names_the_place_and_whether_it_was_reported():
    assert protocol.classic_sheet("f-sheet-1", SHEET, "student-1", True) == {
        "type": "classic_sheet", "sheet_id": "f-sheet-1", "character": "student-1",
        "position": SHEET_POSITION, "reported": True,
    }


# Over the real WebSocket endpoint


@pytest.fixture
def six(connect, clock, monkeypatch):
    """Six players with Mara and Sofia as the Free Riders, placed as in PLACES."""
    monkeypatch.setattr(
        classic_round_module, "assign_roles",
        lambda player_ids, rng: {name: "FR" if name in FREE_RIDERS else "HP" for name in player_ids},
    )
    connections, _code, _public, _start = start_classic(connect, SIX)
    for name, place in PLACES.items():
        put(name, place)
    for connection in connections.values():
        everything_sent(connection)
    return connections


def tick(connections, count=1):
    first = next(iter(connections.values()))
    for _ in range(count):
        first.portal.call(REAL_TICK, 0.0)
    wait_for_background_sends()


def of_type(messages, wanted):
    return [message for message in messages if message["type"] == wanted]


def fail(connections, actor):
    connections[actor].send_json({"type": "fail"})
    return {name: read_until(connection, "classic_fail")[-1] for name, connection in connections.items()}


def test_the_place_of_a_fail_goes_only_to_who_sees_it_the_ghost_and_the_free_rider(six):
    told = fail(six, ACTOR)

    # Who failed is public at once (S-159, S-163, S-164).
    for name, message in told.items():
        assert message["target_id"] == VICTIM, name
        assert message["sheet_id"] == "f-sheet-1"
        assert message["character"] == app.state.lobbies.lobby_of(ACTOR).character_of(VICTIM)
    # The place only to the Free Rider who did it, the victim (a ghost now) and the near one.
    for name in (ACTOR, VICTIM, NEAR):
        assert told[name]["position"] == SHEET_POSITION, name
    for name in (FAR, BEHIND_WALL, SECOND_FR):
        assert "position" not in told[name], name


def test_the_free_rider_who_did_it_is_told_the_place_even_behind_a_wall(six):
    # Within the fail range (25), but a wall between him and the victim.
    put(ACTOR, (201.0, 160.0))
    put(VICTIM, (201.0, 180.0))
    assert not visibility.place_in_sight((201.0, 160.0), (201.0, 180.0), CAMPUS)
    told = fail(six, ACTOR)
    assert told[ACTOR]["position"] == {"x": 201.0, "y": 180.0}
    assert told[VICTIM]["position"] == {"x": 201.0, "y": 180.0}


def test_nothing_else_after_the_fail_names_the_place_to_those_who_do_not_see_it(six):
    fail(six, ACTOR)
    tick(six, 3)
    for name in (FAR, BEHIND_WALL, SECOND_FR):
        rest = everything_sent(six[name])
        assert of_type(rest, "classic_sheet") == [], name
        # The victim (a ghost now) is in no living player's positions (S-155).
        for message in of_type(rest, "positions"):
            assert VICTIM not in {entry["name"] for entry in message["players"]}, name


def test_a_sheet_that_comes_into_sight_later_is_sent_once(six):
    fail(six, ACTOR)
    tick(six)
    for connection in six.values():
        everything_sent(connection)

    put(FAR, (240.0, 220.0))
    tick(six, 3)

    sheets_for_far = of_type(everything_sent(six[FAR]), "classic_sheet")
    assert sheets_for_far == [{
        "type": "classic_sheet", "sheet_id": "f-sheet-1",
        "character": app.state.lobbies.lobby_of(ACTOR).character_of(VICTIM),
        "position": SHEET_POSITION, "reported": False,
    }]
    # Those told with the fail are not told again; behind the wall nobody is.
    for name in (ACTOR, VICTIM, NEAR, BEHIND_WALL, SECOND_FR):
        assert of_type(everything_sent(six[name]), "classic_sheet") == [], name


def test_a_new_ghost_is_sent_every_earlier_sheet_wherever_he_stands(six, clock):
    # With two Free Riders the second fail would end the round (parity), so one leaves first.
    six[SECOND_FR].send_json({"type": "leave_lobby"})
    read_until(six[SECOND_FR], "left_lobby")
    del six[SECOND_FR]
    for connection in six.values():
        everything_sent(connection)
    fail(six, ACTOR)
    clock.wait(FAIL_COOLDOWN_SECONDS + 1)
    put(ACTOR, (400.0, 400.0))
    put(FAR, (401.0, 400.0))
    told = fail(six, ACTOR)
    assert told[FAR]["position"] == {"x": 401.0, "y": 400.0}  # his own sheet, as a ghost
    assert "position" not in told[BEHIND_WALL]

    tick(six)

    earlier = of_type(everything_sent(six[FAR]), "classic_sheet")
    assert [message["sheet_id"] for message in earlier] == ["f-sheet-1"]
    assert earlier[0]["position"] == SHEET_POSITION
    assert of_type(everything_sent(six[BEHIND_WALL]), "classic_sheet") == []


def test_a_sheet_seen_after_its_report_comes_as_reported(six):
    fail(six, ACTOR)
    put(NEAR, SHEET)
    six[NEAR].send_json({"type": "report", "sheet_id": "f-sheet-1", "position": SHEET_POSITION})
    for connection in six.values():
        read_until(connection, "meeting_state")
    tick(six)
    for connection in six.values():
        everything_sent(connection)

    put(BEHIND_WALL, (230.0, 200.0))
    tick(six)

    seen = of_type(everything_sent(six[BEHIND_WALL]), "classic_sheet")
    assert [(message["sheet_id"], message["reported"]) for message in seen] == [("f-sheet-1", True)]
    # The meeting snapshot names the reported sheet, never its place.
    assert "position" not in main.classic_meeting.meeting_snapshot(
        app.state.lobbies.lobby_of(ACTOR).meeting, main.seconds_now()
    )


def test_a_player_who_does_not_know_the_place_cannot_report_from_afar(six):
    fail(six, ACTOR)
    six[FAR].send_json({"type": "report", "sheet_id": "f-sheet-1", "position": SHEET_POSITION})
    answer = read_until(six[FAR], "error")[-1]
    assert answer["message"] == protocol.REJECTIONS["report_rejected"]
    six[FAR].send_json({"type": "report", "sheet_id": "f-sheet-1", "position": {"x": 400.0, "y": 330.0}})
    answer = read_until(six[FAR], "error")[-1]
    assert answer["message"] == protocol.REJECTIONS["report_rejected"]
    assert classic_for(FAR).phase == "round"


def test_a_player_who_left_is_sent_no_sheet(six):
    fail(six, ACTOR)
    six[SECOND_FR].send_json({"type": "leave_lobby"})
    read_until(six[SECOND_FR], "left_lobby")
    put(NEAR, PLACES[SECOND_FR])  # someone else stands where he stood
    tick(six, 2)
    # No return into a running round (S-109): he hears nothing more of it.
    assert of_type(everything_sent(six[SECOND_FR]), "classic_sheet") == []


# After a meeting and after a vote


def five_with_a_sheet_at(connect, sheet):
    """Five players far apart (random roles); the Free Rider fails a High Performer at `sheet`."""
    connections, lobby, fr, high_performers = meeting_once.classic_round(connect)
    victim = high_performers[0]
    put(fr, (sheet[0] - 10.0, sheet[1]))
    put(victim, sheet)
    for connection in connections.values():
        everything_sent(connection)
    fail(connections, fr)
    meeting_once.ticks(connections, count=2)
    return connections, lobby, fr, high_performers


def test_a_player_voted_out_is_sent_every_sheet_as_a_ghost(connect, clock):
    connections, lobby, fr, [victim, out, *living] = five_with_a_sheet_at(connect, meeting_once.FAIL_PLACE)
    spawn = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
    assert not visibility.place_in_sight(spawn, meeting_once.FAIL_PLACE, CAMPUS)  # not from the Main Deck
    assert not lobby.classic_round.sheets_told.get(out)  # far away: not told before
    for connection in connections.values():
        everything_sent(connection)
    meeting_once.start_emergency(connections, living[0], clock)

    told = meeting_once.everybody_votes(connections, lobby, clock, lambda voter: out)
    meeting_once.ticks(connections, count=2)

    assert out in lobby.classic_round.eliminated
    sent_to_out = told[out] + everything_sent(connections[out])
    assert [m["sheet_id"] for m in of_type(sent_to_out, "classic_sheet")] == ["f-sheet-1"]
    for name in living:  # where they stood, out of sight of the sheet (S-213)
        assert of_type(told[name] + everything_sent(connections[name]), "classic_sheet") == [], name


def test_a_meeting_does_not_move_players_into_sight_of_a_sheet(connect, clock):
    sheet = (520.0, 380.0)
    spawn = (CAMPUS["spawn"]["x"], CAMPUS["spawn"]["y"])
    assert visibility.place_in_sight(spawn, sheet, CAMPUS)
    for place in meeting_once.FAR_PLACES:
        assert not visibility.place_in_sight(place, sheet, CAMPUS)
    connections, lobby, fr, [victim, *living] = five_with_a_sheet_at(connect, sheet)
    for name in living:
        assert of_type(everything_sent(connections[name]), "classic_sheet") == [], name

    for connection in connections.values():
        everything_sent(connection)
    meeting_once.start_emergency(connections, living[0], clock)
    before = {name: lobby.walkers.position_of(name) for name in living}
    told = meeting_once.everybody_skips(connections, lobby, clock)
    meeting_once.ticks(connections, count=2)

    for name in living:
        assert lobby.walkers.position_of(name) == before[name], name
        seen = of_type(told[name] + everything_sent(connections[name]), "classic_sheet")
        assert not seen, name
    # The Free Rider was told with the fail, the victim as a ghost: never twice.
    for name in (fr, victim):
        assert of_type(told[name] + everything_sent(connections[name]), "classic_sheet") == [], name
