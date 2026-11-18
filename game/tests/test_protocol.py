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


# ---------------------------------------------------------------------------
# Lobby, account and movement messages (to-do M0-2.5)
# ---------------------------------------------------------------------------

from server import protocol  # noqa: E402  (kept next to the tests that use it)


def rejected(message):
    """Send a message as JSON and return the (code, text) it is rejected with."""
    with pytest.raises(ProtocolError) as caught:
        parse_client_message(json.dumps(message))
    return caught.value.code, caught.value.message


TOO_SHORT = ("bad_password", "Passwords need at least 8 characters.")
TOO_LONG = ("bad_password", "Passwords can have at most 64 characters.")
WRONG_CREDENTIALS = ("wrong_credentials", "Wrong username or password.")
BAD_CODE = ("bad_code", "Lobby codes are 4 letters.")
BAD_CHARACTER = ("bad_character", "That character does not exist.")
BAD_MOVE = ("bad_move", "That move could not be read.")

VALID_MESSAGES = [
    {"type": "sign_up", "name": "Mara", "password": "longenough"},
    {"type": "log_in", "name": "Mara", "password": "longenough"},
    {"type": "guest"},
    {"type": "log_out"},
    {"type": "create_lobby"},
    {"type": "join_lobby", "code": "ABCD"},
    {"type": "leave_lobby"},
    {"type": "choose_character", "character": "surfer"},
    {"type": "move", "dx": 1, "dy": -1},
]
MESSAGES_WITHOUT_FIELDS = ["guest", "log_out", "create_lobby", "leave_lobby"]


# Accepted

@pytest.mark.parametrize("message", VALID_MESSAGES, ids=lambda message: message["type"])
def test_every_new_message_is_accepted_and_returned_exactly(message):
    assert parse_client_message(json.dumps(message)) == message


@pytest.mark.parametrize("length", [8, 64])
def test_sign_up_passwords_at_the_limits_are_accepted(length):
    message = {"type": "sign_up", "name": "Mara", "password": "p" * length}
    assert parse_client_message(json.dumps(message)) == message


def test_sign_up_password_may_contain_any_characters():
    message = {"type": "sign_up", "name": "Mara", "password": "pässwörd with spaces!"}
    assert parse_client_message(json.dumps(message)) == message


@pytest.mark.parametrize("value", ["x", "x" * 64, "has space", "Zoë"])
def test_log_in_accepts_any_text_of_1_to_64_characters(value):
    message = {"type": "log_in", "name": value, "password": value}
    assert parse_client_message(json.dumps(message)) == message


@pytest.mark.parametrize("code", ["abcd", "ABCD", "aBcD"])
def test_join_lobby_code_is_returned_in_upper_case(code):
    assert parse_client_message(json.dumps({"type": "join_lobby", "code": code})) == {"type": "join_lobby", "code": "ABCD"}


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_every_character_can_be_chosen(character):
    message = {"type": "choose_character", "character": character}
    assert parse_client_message(json.dumps(message)) == message


def test_the_characters_are_the_eight_agreed_ids():
    assert protocol.CHARACTERS == (
        "consultant", "finance_bro", "exchange_student", "surfer",
        "founder", "overachiever", "latecomer", "library_local",
    )


@pytest.mark.parametrize("dx", [-1, 0, 1])
@pytest.mark.parametrize("dy", [-1, 0, 1])
def test_every_step_of_minus_one_zero_or_one_is_accepted(dx, dy):
    assert parse_client_message(json.dumps({"type": "move", "dx": dx, "dy": dy})) == {"type": "move", "dx": dx, "dy": dy}


def test_an_accepted_step_is_a_real_int():
    checked = parse_client_message('{"type": "move", "dx": 1, "dy": 0}')
    assert type(checked["dx"]) is int and type(checked["dy"]) is int


# Rejected

@pytest.mark.parametrize("password", ["", "p" * 7, None, 12345678, ["password"], True])
def test_sign_up_password_that_is_too_short_or_not_text_is_rejected(password):
    assert rejected({"type": "sign_up", "name": "Mara", "password": password}) == TOO_SHORT


@pytest.mark.parametrize("length", [65, 200])
def test_sign_up_password_that_is_too_long_is_rejected(length):
    assert rejected({"type": "sign_up", "name": "Mara", "password": "p" * length}) == TOO_LONG


@pytest.mark.parametrize("name", ["ab", "A" * 17, "has space", "Zoë", None, 123])
def test_sign_up_with_a_bad_name_is_rejected(name):
    code, _ = rejected({"type": "sign_up", "name": name, "password": "longenough"})
    assert code == "bad_name"


@pytest.mark.parametrize("value", ["", "x" * 65, None, 123, ["Mara"], True])
def test_log_in_with_an_unreadable_name_is_rejected_as_wrong_credentials(value):
    assert rejected({"type": "log_in", "name": value, "password": "longenough"}) == WRONG_CREDENTIALS


@pytest.mark.parametrize("value", ["", "x" * 65, None, 123, ["secret"], True])
def test_log_in_with_an_unreadable_password_is_rejected_as_wrong_credentials(value):
    assert rejected({"type": "log_in", "name": "Mara", "password": value}) == WRONG_CREDENTIALS


@pytest.mark.parametrize("code", ["ABC", "ABCDE", "", "1234", "AB1D", "ÄBCD", "AB D", "ABCD\n", None, 1234, ["ABCD"]])
def test_bad_lobby_codes_are_rejected(code):
    assert rejected({"type": "join_lobby", "code": code}) == BAD_CODE


@pytest.mark.parametrize("character", ["wizard", "", "Surfer", "surfer ", None, 3, ["surfer"], {"id": "surfer"}])
def test_unknown_characters_are_rejected(character):
    assert rejected({"type": "choose_character", "character": character}) == BAD_CHARACTER


BAD_STEPS = [2, -2, True, False, 1.0, 0.5, "1", None, [1]]


@pytest.mark.parametrize("step", BAD_STEPS)
def test_a_bad_dx_is_rejected(step):
    assert rejected({"type": "move", "dx": step, "dy": 0}) == BAD_MOVE


@pytest.mark.parametrize("step", BAD_STEPS)
def test_a_bad_dy_is_rejected(step):
    assert rejected({"type": "move", "dx": 0, "dy": step}) == BAD_MOVE


def test_a_step_written_as_one_point_zero_is_rejected():
    # json.dumps(1.0) writes "1.0"; this pins the raw text a browser could send.
    assert rejected_code('{"type": "move", "dx": 1.0, "dy": 0}') == "bad_move"


# The general rules apply to the new messages too

@pytest.mark.parametrize("message_type", MESSAGES_WITHOUT_FIELDS)
def test_a_message_without_fields_rejects_an_extra_field(message_type):
    assert rejected_code(json.dumps({"type": message_type, "name": "Mara"})) == "unknown_field"


@pytest.mark.parametrize("message", [m for m in VALID_MESSAGES if len(m) > 1], ids=lambda message: message["type"])
def test_a_message_with_fields_rejects_an_extra_field(message):
    assert rejected_code(json.dumps({**message, "role": "free_rider"})) == "unknown_field"


MISSING_FIELD_CASES = [
    (message["type"], field)
    for message in VALID_MESSAGES
    for field in message
    if field != "type"
]


@pytest.mark.parametrize("message_type, field", MISSING_FIELD_CASES)
def test_a_message_with_fields_rejects_a_missing_one(message_type, field):
    message = next(m for m in VALID_MESSAGES if m["type"] == message_type)
    without = {key: value for key, value in message.items() if key != field}
    assert rejected_code(json.dumps(without)) == "missing_field"


def test_a_new_message_that_is_too_large_is_rejected():
    raw = json.dumps({"type": "log_in", "name": "Mara", "password": "p" * MAX_MESSAGE_BYTES})
    assert rejected_code(raw) == "too_large"


def test_the_message_table_holds_exactly_the_agreed_types():
    assert set(protocol.CLIENT_MESSAGES) == {"hello"} | {message["type"] for message in VALID_MESSAGES}


# Messages the server sends

def test_signed_in_carries_the_name_and_whether_the_player_is_a_guest():
    assert protocol.signed_in("Mara", False) == {"type": "signed_in", "name": "Mara", "guest": False}
    assert protocol.signed_in("Guest1234", True) == {"type": "signed_in", "name": "Guest1234", "guest": True}


def test_signed_out_has_only_its_type():
    assert protocol.signed_out() == {"type": "signed_out"}


def test_lobby_state_lists_code_host_and_players_in_order():
    state = protocol.lobby_state("ABCD", "Mara", [("Mara", "surfer"), ("Tom", None)])
    assert state == {
        "type": "lobby_state",
        "code": "ABCD",
        "host": "Mara",
        "players": [{"name": "Mara", "character": "surfer"}, {"name": "Tom", "character": None}],
    }


def test_lobby_state_with_no_players_has_an_empty_list():
    assert protocol.lobby_state("ABCD", "Mara", []) == {"type": "lobby_state", "code": "ABCD", "host": "Mara", "players": []}


def test_left_lobby_has_only_its_type():
    assert protocol.left_lobby() == {"type": "left_lobby"}


def test_positions_lists_every_player_with_rounded_coordinates():
    message = protocol.positions([("Mara", 12.34, 7.86), ("Tom", 3, -0.04)])
    assert message == {
        "type": "positions",
        "players": [{"name": "Mara", "x": 12.3, "y": 7.9}, {"name": "Tom", "x": 3, "y": -0.0}],
    }


def test_positions_with_no_players_has_an_empty_list():
    assert protocol.positions([]) == {"type": "positions", "players": []}


def test_notice_carries_its_text():
    assert protocol.notice("Tom left the lobby.") == {"type": "notice", "message": "Tom left the lobby."}


def test_every_server_message_can_be_sent_as_json():
    messages = [
        protocol.signed_in("Mara", True),
        protocol.signed_out(),
        protocol.lobby_state("ABCD", "Mara", [("Mara", None)]),
        protocol.left_lobby(),
        protocol.positions([("Mara", 1.25, 2.75)]),
        protocol.notice("Hi"),
        protocol.rejection("lobby_full"),
    ]
    for message in messages:
        assert json.loads(json.dumps(message)) == message


# Fixed texts for refused actions

REJECTION_TEXTS = {
    "name_taken": "That username is taken.",
    "wrong_credentials": "Wrong username or password.",
    "accounts_unavailable": "Accounts are unavailable right now. You can still play as a guest.",
    "not_signed_in": "Log in or play as a guest first.",
    "no_lobby": "No lobby with that code.",
    "lobby_full": "This lobby is full.",
    "not_in_lobby": "You are not in a lobby.",
    "already_in_lobby": "Leave your lobby first.",
    "character_taken": "That character is taken.",
}


@pytest.mark.parametrize("code, text", REJECTION_TEXTS.items())
def test_rejection_returns_the_exact_text_for_each_code(code, text):
    assert protocol.rejection(code) == {"type": "error", "code": code, "message": text}


def test_the_rejection_table_holds_exactly_the_agreed_codes():
    assert protocol.REJECTIONS == REJECTION_TEXTS


@pytest.mark.parametrize("code", ["bad_name", "", "LOBBY_FULL"])
def test_rejection_with_an_unknown_code_raises_key_error(code):
    with pytest.raises(KeyError):
        protocol.rejection(code)


# Text that later code cannot store or hash (review finding on M0-2.5)

# A lone surrogate is half of a character pair: JSON may carry it as "\ud800",
# but it cannot be written as UTF-8. Postgres refuses the NUL character.
LONE_SURROGATE = "\ud800"
NUL = "\x00"
UNSAFE_PASSWORD = ("bad_password", "Passwords cannot contain that character.")


@pytest.mark.parametrize("bad_character", [LONE_SURROGATE, NUL], ids=["lone_surrogate", "nul"])
def test_sign_up_password_with_an_unsafe_character_is_rejected(bad_character):
    password = "longenough" + bad_character
    assert rejected({"type": "sign_up", "name": "Mara", "password": password}) == UNSAFE_PASSWORD


@pytest.mark.parametrize("bad_character", [LONE_SURROGATE, NUL], ids=["lone_surrogate", "nul"])
def test_log_in_name_with_an_unsafe_character_is_rejected_as_wrong_credentials(bad_character):
    assert rejected({"type": "log_in", "name": "Mara" + bad_character, "password": "longenough"}) == WRONG_CREDENTIALS


@pytest.mark.parametrize("bad_character", [LONE_SURROGATE, NUL], ids=["lone_surrogate", "nul"])
def test_log_in_password_with_an_unsafe_character_is_rejected_as_wrong_credentials(bad_character):
    assert rejected({"type": "log_in", "name": "Mara", "password": "longenough" + bad_character}) == WRONG_CREDENTIALS


@pytest.mark.parametrize("raw_escape", ["\\ud800", "\\u0000"], ids=["lone_surrogate", "nul"])
def test_unsafe_characters_written_as_json_escapes_are_rejected(raw_escape):
    # This is the exact text a browser could send, without json.dumps in between.
    sign_up = '{"type": "sign_up", "name": "Mara", "password": "longenough' + raw_escape + '"}'
    log_in = '{"type": "log_in", "name": "Mara", "password": "longenough' + raw_escape + '"}'
    assert rejected_code(sign_up) == "bad_password"
    assert rejected_code(log_in) == "wrong_credentials"


@pytest.mark.parametrize("password", ["pässwörd-äöü", "🔥🔥🔥🔥🔥🔥🔥🔥", "surf🏄wave🌊"])
def test_normal_non_ascii_and_emoji_passwords_are_accepted(password):
    for message_type in ("sign_up", "log_in"):
        message = {"type": message_type, "name": "Mara", "password": password}
        assert parse_client_message(json.dumps(message)) == message
        # ensure_ascii=False sends the characters themselves instead of \u escapes.
        assert parse_client_message(json.dumps(message, ensure_ascii=False)) == message
