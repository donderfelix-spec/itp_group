"""The position in a `report` message: huge whole numbers are refused, not crashed on.

Found in the final audit (2026-11-23): `{"x": <400 digits>}` made `float()`
raise OverflowError in `protocol._check_position`, the server logged a
traceback and closed the sender's connection.
"""

import json

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.protocol import ProtocolError, parse_client_message

BAD_POSITION = ("bad_position", "That position could not be read.")
HUGE = 10 ** 400


def report(x, y):
    return json.dumps({"type": "report", "sheet_id": "f-sheet-1", "position": {"x": x, "y": y}})


def rejected(text):
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(text)
    return caught.value.code, caught.value.message


# Accepted

@pytest.mark.parametrize("x, y", [(12, 30), (0, 0), (-5.5, 1e300), (10 ** 300, 2)])
def test_whole_and_large_but_finite_numbers_are_accepted_as_floats(x, y):
    checked = parse_client_message(report(x, y))
    assert checked["position"] == {"x": float(x), "y": float(y)}
    assert type(checked["position"]["x"]) is float


# Rejected

@pytest.mark.parametrize("x, y", [(HUGE, 0), (-HUGE, 0), (0, HUGE), (HUGE, -HUGE)])
def test_a_whole_number_too_large_for_a_float_is_a_bad_position(x, y):
    assert rejected(report(x, y)) == BAD_POSITION


# Edge cases

def test_the_largest_float_passes_and_one_digit_more_does_not():
    biggest = int(1.7976931348623157e308)
    assert parse_client_message(report(biggest, 0))["position"]["x"] == 1.7976931348623157e308
    assert rejected(report(biggest * 10, 0)) == BAD_POSITION


def test_the_connection_stays_open_after_a_huge_number():
    with TestClient(app).websocket_connect("/ws") as socket:
        socket.send_text(report(HUGE, 0))
        answer = socket.receive_json()
        assert answer["code"] == "bad_position"
        # The same connection still answers the next message.
        socket.send_text(json.dumps({"type": "guest"}))
        assert socket.receive_json()["type"] != "error"
