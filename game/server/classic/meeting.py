"""Pure discussion and voting clock and chat rules for a Classic meeting."""

from copy import deepcopy
import math
from typing import Literal, NamedTuple

from rules import check_winner
from server import protocol


DISCUSSION_SECONDS = 45
VOTING_SECONDS = 30
MAX_CHAT_LENGTH = 200
CHAT_COOLDOWN_SECONDS = 2.0
MeetingPhase = Literal["discussion", "voting", "result"]


class EjectResult(NamedTuple):
    ejected_id: str | None
    tie: bool
    revealed_role: str | None


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
        "reason": (round_state or {}).get("meeting_reason"),
        "trigger_player_id": (round_state or {}).get("meeting_trigger_player_id"),
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


def cast_vote(state: dict, voter_id: str, target_id: str) -> dict:
    """Return a new state with one final vote from a living voter."""
    living = state.get("living", ())
    if state.get("phase") != "voting":
        raise ValueError("Voting is not open.")
    if voter_id not in living:
        raise ValueError("Only living players may vote.")
    if target_id not in living:
        raise ValueError("Votes must target a living player.")
    if voter_id in state.get("votes", {}):
        raise ValueError("A player's vote is final.")
    updated = deepcopy(state)
    updated["votes"][voter_id] = target_id
    return updated


def tally_votes(state: dict) -> EjectResult:
    """Count votes only after voting ends; tied leaders cause no ejection."""
    if state.get("phase") != "result":
        raise ValueError("Votes stay hidden until voting ends.")
    living = set(state.get("living", ()))
    valid_votes = [
        target_id
        for voter_id, target_id in state.get("votes", {}).items()
        if voter_id in living and target_id in living
    ]
    if not valid_votes:
        return EjectResult(None, False, None)

    counts = {player_id: valid_votes.count(player_id) for player_id in set(valid_votes)}
    most_votes = max(counts.values())
    leaders = [player_id for player_id, count in counts.items() if count == most_votes]
    if len(leaders) != 1:
        return EjectResult(None, True, None)

    ejected_id = leaders[0]
    role = state.get("roles", {}).get(ejected_id)
    return EjectResult(ejected_id, False, role)


def resolve_vote_result(state: dict) -> dict:
    """Eject the voted player, reveal their role and evaluate the win rules."""
    result = tally_votes(state)
    updated = deepcopy(state)
    if result.ejected_id is not None:
        updated["living"] = tuple(
            player_id for player_id in state.get("living", ())
            if player_id != result.ejected_id
        )
        updated["ghosts"] = tuple(state.get("ghosts", ())) + (result.ejected_id,)
        updated["eliminated"] = set(state.get("eliminated", ())) | {result.ejected_id}

    updated["vote_result"] = result
    required = {"roles", "tasks", "completed_tasks", "eliminated"}
    updated["winner"] = check_winner(updated) if required <= updated.keys() else None
    return updated


def count_votes(state: dict) -> dict:
    """How many votes each player has: the living, and the player voted out at the result.

    Every stored vote had a living target when it was cast (`cast_vote`), so
    a player voted out by the result keeps the count of the vote (S-100).
    Who voted for whom stays hidden.
    """
    counts = {player_id: 0 for player_id in state.get("living", ())}
    for target_id in state.get("votes", {}).values():
        counts[target_id] = counts.get(target_id, 0) + 1
    return counts


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
            updated = resolve_vote_result(updated)
        else:
            raise ValueError("Meeting phase is invalid.")
    return updated


def meeting_snapshot(meeting: dict, now: float) -> dict:
    """Build the same public state for every meeting participant."""
    current = advance_meeting(meeting, now)
    return {
        "type": "meeting_state",
        "phase": current["phase"],
        "seconds_left": max(0, math.ceil(current["deadline"] - now)),
        "living": list(current["living"]),
        "ghosts": list(current["ghosts"]),
        "reason": current.get("reason"),
        "trigger_player_id": current.get("trigger_player_id"),
        "reported_sheet_id": current.get("reported_sheet_id"),
        "messages": [
            {"player_id": item["player_id"], "text": item["text"]}
            for item in current["messages"]
        ],
        # Only the number of votes per living player, from the vote on. During
        # discussion there are no votes yet, so nothing is sent.
        "vote_counts": (
            protocol.vote_counts(count_votes(current))
            if current["phase"] != "discussion"
            else []
        ),
        # Who has voted is public, but the selected target stays hidden until
        # the result is calculated and is never sent to the clients.
        "voted": list(current.get("votes", {})),
        "ejected_id": (
            current["vote_result"].ejected_id
            if current.get("vote_result") is not None
            else None
        ),
        "revealed_role": (
            current["vote_result"].revealed_role
            if current.get("vote_result") is not None
            else None
        ),
        "tie": current["vote_result"].tie if current.get("vote_result") is not None else False,
        "winner": current.get("winner"),
    }


def _valid_time(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )
