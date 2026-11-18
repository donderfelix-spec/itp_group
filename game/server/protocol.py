"""Messages between the browser and the server.

Every message is a JSON object with a "type". The server trusts nothing the
browser sends: `parse_client_message` checks size, shape, type and every field
before any game code sees the message. Anything else is rejected with a
`ProtocolError`, which the server turns into an "error" message for the player.

This file belongs to area 2 (network). Changing a message format affects every
area, so it is a team decision (see WORKFLOW.md, step 4).
"""

import json
import re

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 2048

NAME_PATTERN = re.compile(r"[A-Za-z0-9]{3,16}")


class ProtocolError(Exception):
    """A message the server refuses. `code` is stable, `message` is shown to the player."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _check_name(value):
    if not isinstance(value, str) or not NAME_PATTERN.fullmatch(value):
        raise ProtocolError("bad_name", "Usernames are 3–16 letters or numbers.")
    return value


# Each client message type with its required fields and the check for each field.
CLIENT_MESSAGES = {
    "hello": {"name": _check_name},
}


def parse_client_message(raw) -> dict:
    """Return the checked message, or raise ProtocolError."""
    if not isinstance(raw, str):
        raise ProtocolError("not_text", "Messages must be text.")
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ProtocolError("too_large", "That message is too long.")
    try:
        data = json.loads(raw)
    except ValueError:
        raise ProtocolError("not_json", "That message could not be read.") from None
    if not isinstance(data, dict):
        raise ProtocolError("not_object", "That message could not be read.")

    message_type = data.get("type")
    if not isinstance(message_type, str) or message_type not in CLIENT_MESSAGES:
        raise ProtocolError("unknown_type", "The server does not know that action.")

    fields = CLIENT_MESSAGES[message_type]
    for key in data:
        if key != "type" and key not in fields:
            raise ProtocolError("unknown_field", "That message has a field the server does not expect.")

    checked = {"type": message_type}
    for key, check in fields.items():
        if key not in data:
            raise ProtocolError("missing_field", "That message is incomplete.")
        checked[key] = check(data[key])
    return checked


def welcome(name: str) -> dict:
    return {"type": "welcome", "name": name, "protocol": PROTOCOL_VERSION}


def error(problem: ProtocolError) -> dict:
    return {"type": "error", "code": problem.code, "message": problem.message}
