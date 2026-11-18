"""Rules for messages from the browser: what is accepted, what is rejected, and the edges."""

import json

import pytest

from server.protocol import MAX_MESSAGE_BYTES, ProtocolError, error, parse_client_message, welcome


def hello(name):
    return json.dumps({"type": "hello", "name": name})


def rejected_code(raw):
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(raw)
    return caught.value.code


# Accepted

def test_hello_with_a_valid_name_is_accepted():
    assert parse_client_message(hello("Mara")) == {"type": "hello", "name": "Mara"}


@pytest.mark.parametrize("name", ["abc", "A" * 16, "Guest1234", "007"])
def test_names_at_the_allowed_limits_are_accepted(name):
    assert parse_client_message(hello(name))["name"] == name


def test_a_message_of_exactly_the_maximum_size_is_read():
    padding = MAX_MESSAGE_BYTES - len(hello("Mara"))
    raw = hello("Mara") + " " * padding
    assert len(raw.encode("utf-8")) == MAX_MESSAGE_BYTES
    assert parse_client_message(raw)["name"] == "Mara"


# Rejected

@pytest.mark.parametrize("name", ["ab", "A" * 17, "", "has space", "<b>x</b>", "Zoë", "a_b", None, 123, ["Mara"]])
def test_bad_names_are_rejected(name):
    assert rejected_code(hello(name)) == "bad_name"


def test_a_message_one_byte_too_large_is_rejected():
    raw = hello("Mara") + " " * (MAX_MESSAGE_BYTES - len(hello("Mara")) + 1)
    assert rejected_code(raw) == "too_large"


def test_size_is_counted_in_bytes_not_characters():
    # 700 three-byte characters fit the character count but not the byte limit.
    assert rejected_code("€" * 700) == "too_large"


@pytest.mark.parametrize("raw", ["", "not json", "{", "{'type': 'hello'}"])
def test_text_that_is_not_json_is_rejected(raw):
    assert rejected_code(raw) == "not_json"


@pytest.mark.parametrize("raw", ["[]", "\"hello\"", "42", "null", "true"])
def test_json_that_is_not_an_object_is_rejected(raw):
    assert rejected_code(raw) == "not_object"


@pytest.mark.parametrize("message", [{}, {"type": "fly"}, {"type": 7}, {"type": None}, {"type": ["hello"]}, {"name": "Mara"}])
def test_unknown_or_missing_types_are_rejected(message):
    assert rejected_code(json.dumps(message)) == "unknown_type"


def test_a_field_the_server_does_not_expect_is_rejected():
    assert rejected_code(json.dumps({"type": "hello", "name": "Mara", "role": "free_rider"})) == "unknown_field"


def test_a_missing_field_is_rejected():
    assert rejected_code(json.dumps({"type": "hello"})) == "missing_field"


@pytest.mark.parametrize("raw", [None, b"{}", 5])
def test_anything_that_is_not_text_is_rejected(raw):
    assert rejected_code(raw) == "not_text"


# Messages the server sends

def test_error_message_carries_code_and_text_for_the_player():
    assert error(ProtocolError("bad_name", "Nope")) == {"type": "error", "code": "bad_name", "message": "Nope"}


def test_welcome_repeats_the_name_and_the_protocol_version():
    assert welcome("Mara") == {"type": "welcome", "name": "Mara", "protocol": 1}
