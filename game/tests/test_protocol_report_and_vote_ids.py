"""The ids in `report.sheet_id` and `vote.target_id` (to-do M3-3.18).

The protocol checks only the shape of an id: a sheet id is "f-sheet-" and a
number of 1 to 9 digits without a leading zero, a vote target is a username of
3 to 16 letters or numbers. Whether that sheet or player exists in the running
round is a question for the rules, so an unknown but well-formed id passes the
protocol and is refused by the rules (tested at the end of this file).
"""

import json

import pytest

from rules import can_report, report_sheet
from server.classic.meeting import cast_vote
from server.protocol import ProtocolError, parse_client_message

BAD_SHEET_ID = ("bad_sheet_id", "That F-sheet could not be identified.")
BAD_NAME = ("bad_name", "Usernames are 3–16 letters or numbers.")
GOOD_POSITION = {"x": 12.5, "y": 30.0}


def report(sheet_id):
    return {"type": "report", "sheet_id": sheet_id, "position": GOOD_POSITION}


def vote(target_id):
    return {"type": "vote", "target_id": target_id}


def rejected(message):
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(json.dumps(message))
    return caught.value.code, caught.value.message


# report.sheet_id: accepted and edges

@pytest.mark.parametrize("sheet_id", ["f-sheet-1", "f-sheet-9", "f-sheet-10", "f-sheet-123456789"])
def test_well_formed_sheet_ids_are_accepted(sheet_id):
    assert parse_client_message(json.dumps(report(sheet_id)))["sheet_id"] == sheet_id


# report.sheet_id: rejected

@pytest.mark.parametrize(
    "sheet_id",
    [
        "",                     # empty
        "f-sheet-",             # no number
        "f-sheet-0",            # numbers start at 1
        "f-sheet-01",           # leading zero
        "f-sheet-1234567890",   # ten digits: too long
        "f-sheet-" + "1" * 200, # far too long
        "F-SHEET-1",            # case matters
        "f-sheet-1 ",           # trailing space
        " f-sheet-1",           # leading space
        "f-sheet-1\n",          # trailing newline
        "f-sheet--1",
        "f-sheet-1.5",
        "f-sheet-١",            # an Arabic-Indic digit is not a 0-9 digit
        "sheet-1",
        "1",
        "<b>f-sheet-1</b>",
    ],
)
def test_badly_written_sheet_ids_are_rejected(sheet_id):
    assert rejected(report(sheet_id)) == BAD_SHEET_ID


@pytest.mark.parametrize(
    "sheet_id",
    [None, 1, 1.0, True, False, ["f-sheet-1"], [], {"id": "f-sheet-1"}, {}],
    ids=["null", "int", "float", "true", "false", "list", "empty-list", "object", "empty-object"],
)
def test_a_sheet_id_that_is_not_text_is_rejected(sheet_id):
    assert rejected(report(sheet_id)) == BAD_SHEET_ID


def test_a_report_without_sheet_id_is_incomplete():
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(json.dumps({"type": "report", "position": GOOD_POSITION}))
    assert caught.value.code == "missing_field"


def test_a_bad_sheet_id_is_rejected_even_with_a_good_position():
    # The sheet id is checked first, so the player learns which field was wrong.
    assert rejected({"type": "report", "sheet_id": "x", "position": {"x": "bad"}}) == BAD_SHEET_ID


# vote.target_id: accepted and edges

@pytest.mark.parametrize("target_id", ["abc", "A" * 16, "Mara", "Guest1234", "007"])
def test_well_formed_vote_targets_are_accepted(target_id):
    assert parse_client_message(json.dumps(vote(target_id))) == vote(target_id)


# vote.target_id: rejected

@pytest.mark.parametrize(
    "target_id",
    [
        "",           # empty; Skip has its own message (skip_discussion)
        "ab",         # too short
        "A" * 17,     # too long
        "A" * 500,    # far too long
        "has space",
        "Mara ",
        "Mara\n",
        "Zoë",
        "a_b",
        "<b>x</b>",
        "\x00abc",
    ],
)
def test_badly_written_vote_targets_are_rejected(target_id):
    assert rejected(vote(target_id)) == BAD_NAME


@pytest.mark.parametrize(
    "target_id",
    [None, 123, 1.5, True, ["Mara"], [], {"name": "Mara"}, {}],
    ids=["null", "int", "float", "true", "list", "empty-list", "object", "empty-object"],
)
def test_a_vote_target_that_is_not_text_is_rejected(target_id):
    assert rejected(vote(target_id)) == BAD_NAME


def test_a_vote_without_target_is_incomplete():
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(json.dumps({"type": "vote"}))
    assert caught.value.code == "missing_field"


# Unknown but well-formed ids pass the protocol and are refused by the rules

def round_with_one_sheet():
    return {
        "roles": {"fr": "FR", "hp": "HP"},
        "eliminated": set(),
        "f_sheets": {"f-sheet-1": (3.0, 4.0)},
        "meeting_triggers": set(),
        "phase": "playing",
    }


def test_an_unknown_sheet_id_passes_the_protocol_but_cannot_be_reported():
    assert parse_client_message(json.dumps(report("f-sheet-7")))["sheet_id"] == "f-sheet-7"
    state = round_with_one_sheet()
    assert not can_report(state, "hp", "f-sheet-7", (3.0, 4.0))
    with pytest.raises(ValueError, match="cannot report"):
        report_sheet(state, "hp", "f-sheet-7", (3.0, 4.0))
    # The known sheet at the same place can be reported.
    assert can_report(state, "hp", "f-sheet-1", (3.0, 4.0))


def test_an_unknown_vote_target_passes_the_protocol_but_is_no_vote():
    assert parse_client_message(json.dumps(vote("Nobody")))["target_id"] == "Nobody"
    meeting = {"phase": "voting", "living": ("Mara", "Lena"), "votes": {}, "skip_votes": set()}
    with pytest.raises(ValueError, match="living player"):
        cast_vote(meeting, "Mara", "Nobody")
