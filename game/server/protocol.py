"""Messages between the browser and the server.

Every message is a JSON object with a "type". The server trusts nothing the
browser sends: `parse_client_message` checks size, shape, type and every field
before any game code sees the message. Anything else is rejected with a
`ProtocolError`, which the server turns into an "error" message for the player.

This file belongs to area 2 (network). Changing a message format affects every
area, so it is a team decision (see WORKFLOW.md, step 4).
"""

import json
import math
import re

from server.world.campus import STATION_COUNT

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 2048

NAME_PATTERN = re.compile(r"[A-Za-z0-9]{3,16}")
LOBBY_CODE_PATTERN = re.compile(r"[A-Za-z]{4}")
SHEET_ID_PATTERN = re.compile(r"f-sheet-[1-9][0-9]{0,8}")

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 64
# Log-in accepts any text up to this length, so the error never reveals the sign-up rules.
MAX_CREDENTIAL_LENGTH = 64

# The ids of the characters a player can choose.
CHARACTERS = (
    "consultant",
    "finance_bro",
    "exchange_student",
    "surfer",
    "founder",
    "overachiever",
    "latecomer",
    "library_local",
)

# The modes that are built and can be chosen (S-91). Classic follows later.
MODES = ("duel", "classic", "solo")
# The mode of a new lobby.
DEFAULT_MODE = "duel"
# The name of each mode as the players read it.
MODE_NAMES = {"duel": "Duel", "classic": "Classic", "solo": "Solo"}
# How many players a round of each mode needs at least (S-53). The only place
# on the server where these numbers stand.
MIN_PLAYERS = {"duel": 2, "classic": 4, "solo": 1}

# A lobby is waiting for its host to start, counting down to the start of
# the round (S-102), or its round is running.
PHASE_LOBBY = "lobby"
PHASE_COUNTDOWN = "countdown"
PHASE_ROUND = "round"

# Fixed texts for actions the server refuses because of the state of the game
# (not because the message was malformed). Build the message with `rejection`.
REJECTIONS = {
    "name_taken": "That username is taken.",
    "wrong_credentials": "Wrong username or password.",
    "accounts_unavailable": "Accounts are unavailable right now. You can still play as a guest.",
    "not_signed_in": "Log in or play as a guest first.",
    "already_signed_in": "Log out first.",
    "no_lobby": "No lobby with that code.",
    "lobby_full": "This lobby is full.",
    "not_in_lobby": "You are not in a lobby.",
    "already_in_lobby": "Leave your lobby first.",
    "character_taken": "That character is taken.",
    "not_host": "Only the host can do that.",
    "round_running": "This round has already started.",
    # Guessing passwords or lobby codes (M1-2.6).
    "too_many_attempts": "Too many attempts. Try again in a minute.",
    # The tasks at the stations (S-93).
    "not_in_round": "No round is running.",
    "no_station": "That station does not exist.",
    "too_far": "You are too far away.",
    "station_not_needed": "You do not need that station.",
    "task_open": "Close your current task first.",
    "no_task_open": "You have no task open.",
    "too_fast": "That was too fast. Try again.",
    "task_failed": "Something went wrong. Try again.",
    "fr_cannot_task": "Free Riders cannot complete tasks.",
    "fail_rejected": "You cannot fail a player right now.",
    "chat_rejected": "You cannot send that chat message right now.",
    "vote_rejected": "You cannot cast that vote right now.",
    "skip_discussion_rejected": "You cannot skip this discussion right now.",
    "report_rejected": "You cannot report that F-sheet right now. Stand at the sheet and try again.",
    "emergency_rejected": "You cannot call an emergency meeting right now.",
    "emergency_out_of_reach": "Walk to the red button to call a meeting.",
    # Hiding with E (M3-1.6, S-191).
    "hide_rejected": "You cannot hide right now.",
    "hide_out_of_reach": "Walk up to a hiding spot to hide.",
    "leave_hiding_first": "Leave your hiding spot first.",
    # Statistics (S-40).
    "guest_no_statistics": "Guests have no statistics. Sign up to keep yours.",
    "statistics_unavailable": "Statistics are unavailable right now.",
}


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


def _is_safe_text(value: str) -> bool:
    """Say whether later code can store and hash this text.

    JSON allows half of a character pair ("\\ud800"), which cannot be written
    as UTF-8, and the NUL character, which Postgres refuses to store.
    """
    if "\x00" in value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check_new_password(value):
    """The password rules for signing up."""
    if not isinstance(value, str) or len(value) < MIN_PASSWORD_LENGTH:
        raise ProtocolError("bad_password", "Passwords need at least 8 characters.")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ProtocolError("bad_password", "Passwords can have at most 64 characters.")
    if not _is_safe_text(value):
        raise ProtocolError("bad_password", "Passwords cannot contain that character.")
    return value


def _check_credential(value):
    """A name or password for logging in.

    Logging in never explains the sign-up rules: every bad value gets the same
    answer as a wrong password, so nobody can learn anything from the error.
    """
    readable = isinstance(value, str) and 1 <= len(value) <= MAX_CREDENTIAL_LENGTH
    if not readable or not _is_safe_text(value):
        raise ProtocolError("wrong_credentials", REJECTIONS["wrong_credentials"])
    return value


def _check_lobby_code(value):
    if not isinstance(value, str) or not LOBBY_CODE_PATTERN.fullmatch(value):
        raise ProtocolError("bad_code", "Lobby codes are 4 letters.")
    # Players may type the code in any case; the server always works with upper case.
    return value.upper()


def _check_character(value):
    # The isinstance check comes first because a list or dict cannot be looked up in a tuple safely.
    if not isinstance(value, str) or value not in CHARACTERS:
        raise ProtocolError("bad_character", "That character does not exist.")
    return value


def _check_mode(value):
    # Modes are enabled only when their round setup is registered.
    if not isinstance(value, str) or value not in MODES:
        raise ProtocolError("bad_mode", "That mode does not exist.")
    return value


def _check_step(value):
    """One direction of a move: -1, 0 or 1."""
    # `type(value) is int` and not isinstance: True and False count as ints in
    # Python, and 1.0 == 1, so a looser check would let them through.
    if type(value) is not int or value not in (-1, 0, 1):
        raise ProtocolError("bad_move", "That move could not be read.")
    return value


def _check_station(value):
    """The id of a station on the map: 1 to STATION_COUNT.

    Whether that station is in use and whether the player may open it is a
    question for the rules (`server/modes/tasks.py`), not for this check.
    """
    # `type(value) is int` for the same reason as in `_check_step`.
    if type(value) is not int or not 1 <= value <= STATION_COUNT:
        raise ProtocolError("bad_station", "That station does not exist.")
    return value


def _check_sheet_id(value):
    if not isinstance(value, str) or not SHEET_ID_PATTERN.fullmatch(value):
        raise ProtocolError("bad_sheet_id", "That F-sheet could not be identified.")
    return value


def _check_position(value):
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        raise ProtocolError("bad_position", "That position could not be read.")
    checked = {}
    for axis in ("x", "y"):
        coordinate = value[axis]
        if (
            isinstance(coordinate, bool)
            or not isinstance(coordinate, (int, float))
            or not math.isfinite(coordinate)
        ):
            raise ProtocolError("bad_position", "That position could not be read.")
        checked[axis] = float(coordinate)
    return checked


def _check_chat_text(value):
    """Chat text is short, readable UTF-8 and safe to echo to every player."""
    if not isinstance(value, str) or not 1 <= len(value) <= 200 or not _is_safe_text(value):
        raise ProtocolError("bad_chat", "Chat messages must contain 1–200 characters.")
    return value


# Each client message type with its required fields and the check for each field.
CLIENT_MESSAGES = {
    "hello": {"name": _check_name},
    "sign_up": {"name": _check_name, "password": _check_new_password},
    "log_in": {"name": _check_credential, "password": _check_credential},
    "guest": {},
    "log_out": {},
    "create_lobby": {},
    "join_lobby": {"code": _check_lobby_code},
    "leave_lobby": {},
    "choose_character": {"character": _check_character},
    "choose_mode": {"mode": _check_mode},
    "start_game": {},
    "move": {"dx": _check_step, "dy": _check_step},
    "open_station": {"station": _check_station},
    "close_station": {},
    "finish_station": {},
    "fail": {},
    "report": {"sheet_id": _check_sheet_id, "position": _check_position},
    "emergency": {},
    # Hiding with E (M3-1.6, S-191): no fields. The server knows where the
    # player stands and which spot is in reach.
    "hide": {},
    "leave_hiding": {},
    "chat": {"text": _check_chat_text},
    "vote": {"target_id": _check_name},
    "skip_discussion": {},
    # Statistics (S-40). Neither carries a name: the profile is always the
    # one of the account the connection is signed in with.
    "get_profile": {},
    "get_leaderboard": {},
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


def rejection(code: str) -> dict:
    """The error message for a refused action. An unknown code raises KeyError."""
    return {"type": "error", "code": code, "message": REJECTIONS[code]}


# Choosing or starting Solo with two or more players (Felix, 2026-11-21).
# Its own constant and not in REJECTIONS: tests/test_protocol.py from main
# pins REJECTIONS to exactly the codes agreed until then.
SOLO_NEEDS_ONE_PLAYER = "solo_needs_one_player"
SOLO_NEEDS_ONE_PLAYER_TEXT = "Solo is only for one player alone."


def solo_needs_one_player() -> dict:
    """The error message for Solo in a lobby with more than one player."""
    return {"type": "error", "code": SOLO_NEEDS_ONE_PLAYER, "message": SOLO_NEEDS_ONE_PLAYER_TEXT}


def too_few_players(mode: str) -> dict:
    """The error message for a start with too few players.

    Its text depends on the mode, so it cannot be a fixed text in REJECTIONS.
    """
    text = f"{MODE_NAMES[mode]} needs at least {MIN_PLAYERS[mode]} players."
    return {"type": "error", "code": "too_few_players", "message": text}


def signed_in(name: str, guest: bool) -> dict:
    return {"type": "signed_in", "name": name, "guest": guest}


def signed_out() -> dict:
    return {"type": "signed_out"}


def lobby_state(code: str, host: str, players, mode: str = DEFAULT_MODE, phase: str = PHASE_LOBBY) -> dict:
    """`players` is a list of (name, character) pairs, in the order they joined.

    Every player has a character from the moment they join (S-75). Without
    `mode` and `phase` this is the state of a new lobby (S-91).
    """
    listed = [{"name": name, "character": character} for name, character in players]
    return {
        "type": "lobby_state",
        "code": code,
        "host": host,
        "players": listed,
        "mode": mode,
        "phase": phase,
    }


def countdown(seconds: int) -> dict:
    """Sent to everybody in the lobby when the host has started the countdown (S-102).

    `seconds` is how long it is until the round starts. The browser counts
    its display down from it; the round itself starts only with the lobby's
    state in phase "round".
    """
    return {"type": "countdown", "seconds": seconds}


def left_lobby() -> dict:
    return {"type": "left_lobby"}


def positions(players) -> dict:
    """`players` is a list of (name, x, y) triples.

    One decimal is enough to draw a character and keeps the message small.
    """
    listed = [{"name": name, "x": round(x, 1), "y": round(y, 1)} for name, x, y in players]
    return {"type": "positions", "players": listed}


def station_opened(station: int, title: str, content: dict) -> dict:
    """Sent only to the player who opened the station (S-93).

    `content` is what the station's minigame drew for this opening. The title
    comes along so the browser can show it for any minigame.
    """
    return {"type": "station_opened", "station": station, "title": title, "content": content}


def station_closed(station: int) -> dict:
    """The player's task is closed and did not count."""
    return {"type": "station_closed", "station": station}


def station_done(station: int) -> dict:
    """The player's task counted: the station is finished for this round."""
    return {"type": "station_done", "station": station}


def duel_state(next_station, done: int, total: int, seconds=None) -> dict:
    """Sent only to the player it is about (S-94): nobody learns another player's route.

    `next_station` is None once the player has finished. Only then the
    message carries "seconds", the player's time.
    """
    message = {"type": "duel_state", "next_station": next_station, "done": done, "total": total}
    if seconds is not None:
        message["seconds"] = seconds
    return message


def duel_progress(players, total: int, seconds_left: int) -> dict:
    """`players` is a list of (name, done) pairs in joining order. Sent to everybody."""
    listed = [{"name": name, "done": done} for name, done in players]
    return {"type": "duel_progress", "players": listed, "total": total, "seconds_left": seconds_left}


def duel_result(ranking, time_up: bool) -> dict:
    """`ranking` is the list of rows from `Duel.ranking`, best first. Sent to everybody."""
    listed = [
        {"place": row["place"], "name": row["name"], "seconds": row["seconds"], "done": row["done"]}
        for row in ranking
    ]
    return {"type": "duel_result", "ranking": listed, "time_up": time_up}


def profile(name: str, modes, best_duel_seconds) -> dict:
    """Sent only to the account it is about (S-40).

    `modes` is a list of (mode, rounds, wins) triples. The title of each
    mode comes along, so the browser can show a mode it does not know yet.
    """
    listed = [
        {"mode": mode, "title": MODE_NAMES[mode], "rounds": rounds, "wins": wins}
        for mode, rounds, wins in modes
    ]
    return {"type": "profile", "name": name, "modes": listed, "best_duel_seconds": best_duel_seconds}


def leaderboard(rows) -> dict:
    """`rows` is the list from `statistics.leaderboard_rows`, best first.

    Each field is copied by name, so nothing else that is known about an
    account can end up in the message.
    """
    listed = [
        {
            "place": row["place"],
            "name": row["name"],
            "wins": row["wins"],
            "best_duel_seconds": row["best_seconds"],
        }
        for row in rows
    ]
    return {"type": "leaderboard", "players": listed}


def notice(message: str) -> dict:
    return {"type": "notice", "message": message}
