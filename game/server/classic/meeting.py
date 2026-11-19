"""Pure discussion and voting clock and chat rules for a Classic meeting."""

from copy import deepcopy
import math
from typing import Literal

from rules import check_winner


DISCUSSION_SECONDS = 45
VOTING_SECONDS = 30
MAX_CHAT_LENGTH = 200
CHAT_COOLDOWN_SECONDS = 2.0
MeetingPhase = Literal["discussion", "voting", "result"]



def start_discussion(
    living: list[str], ghosts: list[str], now: float, round_state: dict | None = None
) -> dict:
    """Create a meeting state. The server supplies the current monotonic time."""
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    if len(set(living)) != len(living) or len(set(ghosts)) != len(ghosts):
        raise ValueError("Meeting player lists must not contain duplicates.")
    if set(living) & set(ghosts):
        raise ValueError("A player cannot be living and a ghost at once.")
    state = {
        "phase": "discussion",
        "deadline": float(now) + DISCUSSION_SECONDS,
        "living": tuple(living),
        "ghosts": tuple(ghosts),
        "messages": [],
        "last_message_at": {},
        "votes": {},
    }
    if round_state is not None:
        for key in ("roles", "tasks", "completed_tasks", "eliminated"):
            if key in round_state:
                state[key] = deepcopy(round_state[key])
    return state


def can_send_chat(meeting: dict, player_id: str, text: str, now: float) -> bool:
    """Return whether this living player may add a chat message now."""
    if meeting.get("phase") != "discussion" or player_id not in meeting.get("living", ()):
        return False
    if not isinstance(text, str) or not 1 <= len(text) <= MAX_CHAT_LENGTH:
        return False
    if not _valid_time(now) or now >= meeting.get("deadline", -math.inf):
        return False
    last_message_at = meeting.get("last_message_at", {}).get(player_id)
    return last_message_at is None or now - last_message_at >= CHAT_COOLDOWN_SECONDS


def send_chat(meeting: dict, player_id: str, text: str, now: float) -> dict:
    """Return a new meeting state with the accepted message appended."""
    if not can_send_chat(meeting, player_id, text, now):
        raise ValueError("Chat message is not allowed right now.")
    updated = deepcopy(meeting)
    updated["messages"].append({"player_id": player_id, "text": text, "sent_at": float(now)})
    updated["last_message_at"][player_id] = float(now)
    return updated


def advance_meeting(meeting: dict, now: float) -> dict:
    """Advance elapsed server-side phases, without changing the input state."""
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    updated = deepcopy(meeting)
    while updated["phase"] != "result" and now >= updated["deadline"]:
        if updated["phase"] == "discussion":
            updated["phase"] = "voting"
            updated["deadline"] += VOTING_SECONDS
        elif updated["phase"] == "voting":
            updated["phase"] = "result"
        else:
            raise ValueError("Meeting phase is invalid.")
    return updated


def meeting_snapshot(meeting: dict, now: float) -> dict:
    """Build the same phase, player lists and chat transcript for all participants."""
    current = advance_meeting(meeting, now)
    return {
        "type": "meeting_state",
        "phase": current["phase"],
        "seconds_left": max(0, math.ceil(current["deadline"] - now)),
        "living": list(current["living"]),
        "ghosts": list(current["ghosts"]),
        "messages": [
            {"player_id": item["player_id"], "text": item["text"]}
            for item in current["messages"]
        ],
    }


def _valid_time(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )
