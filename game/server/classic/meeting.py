"""Pure discussion and voting clock and chat rules for a Classic meeting."""

from copy import deepcopy
import math
from typing import Literal, NamedTuple

from rules import check_winner, tasks_after_leaving


DISCUSSION_SECONDS = 45
VOTING_SECONDS = 30
MAX_CHAT_LENGTH = 200
CHAT_COOLDOWN_SECONDS = 2.0
# Once every living player has voted or chosen Skip, the meeting ends this
# many seconds later at the latest (S-215).
SECONDS_AFTER_EVERYBODY_VOTED = 10
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
        "skip_votes": set(),
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


def agree_to_skip_discussion(meeting: dict, player_id: str, now: float) -> dict:
    """Toggle a Skip ballot and end the meeting at 75% agreement."""
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    living = meeting.get("living", ())
    if not voting_is_open(meeting):
        raise ValueError("Voting is not open.")
    if player_id not in living:
        raise ValueError("Only living players may skip a discussion.")
    if now >= meeting.get("deadline", -math.inf):
        raise ValueError("This discussion has already ended.")
    updated = deepcopy(meeting)
    skips = updated.setdefault("skip_votes", set())
    if player_id in skips:
        skips.remove(player_id)
        return updated
    updated["votes"].pop(player_id, None)
    skips.add(player_id)
    return end_if_enough_skips(updated, now)


def end_if_enough_skips(meeting: dict, now: float) -> dict:
    """End an open vote at once when Skip has 75 % of the living players.

    Called after a Skip, and after a player left: fewer living players can
    bring the Skips that are already there up to 75 %. Otherwise the state
    is returned unchanged.
    """
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    living = set(meeting.get("living", ()))
    skips = living.intersection(meeting.get("skip_votes", ()))
    if not voting_is_open(meeting) or not living or 4 * len(skips) < 3 * len(living):
        return meeting
    updated = deepcopy(meeting)
    updated["phase"] = "result"
    updated["deadline"] = float(now)
    return resolve_vote_result(updated)


def everybody_has_voted(meeting: dict) -> bool:
    """Whether every living player has voted for a player or chosen Skip. Ghosts do not count."""
    living = set(meeting.get("living", ()))
    decided = set(meeting.get("votes", {})) | set(meeting.get("skip_votes", ()))
    return bool(living) and living <= decided


def shorten_when_everybody_voted(meeting: dict, now: float) -> dict:
    """Let the meeting end 10 seconds from `now` once every living player has voted (S-215).

    It happens once per meeting, the first time everybody has voted while
    voting is open: the meeting's end becomes the earlier of its old end and
    now + 10 s, and `ends_by` records it. Taking a vote back or changing it
    afterwards neither gives the time back nor starts it again. In the
    discussion the chat stays open until then and the meeting goes straight
    to its result; if the discussion ends earlier, the vote that follows
    ends there. Otherwise the state is returned unchanged.
    """
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    if (
        meeting.get("ends_by") is not None
        or not voting_is_open(meeting)
        or now >= meeting.get("deadline", -math.inf)
        or not everybody_has_voted(meeting)
    ):
        return meeting
    meeting_end = meeting["deadline"]
    if meeting["phase"] == "discussion":
        meeting_end += VOTING_SECONDS
    ends_by = min(meeting_end, float(now) + SECONDS_AFTER_EVERYBODY_VOTED)
    updated = deepcopy(meeting)
    updated["ends_by"] = ends_by
    updated["deadline"] = min(meeting["deadline"], ends_by)
    return updated


def voting_is_open(state: dict) -> bool:
    return state.get("phase") == "voting" or (
        state.get("phase") == "discussion" and state.get("reason") in ("report", "emergency")
    )


def cast_vote(state: dict, voter_id: str, target_id: str) -> dict:
    """Toggle a target or replace the voter's previous ballot."""
    living = state.get("living", ())
    if not voting_is_open(state):
        raise ValueError("Voting is not open.")
    if voter_id not in living:
        raise ValueError("Only living players may vote.")
    if target_id not in living:
        raise ValueError("Votes must target a living player.")
    updated = deepcopy(state)
    updated.setdefault("skip_votes", set()).discard(voter_id)
    if updated["votes"].get(voter_id) == target_id:
        del updated["votes"][voter_id]
    else:
        updated["votes"][voter_id] = target_id
    return updated


def remove_player(meeting: dict, player_id: str) -> dict:
    """Return a new meeting state without a player who left the round (M3-3.11).

    The player is out of `living` and `ghosts`. Their own vote and Skip are
    gone, and so are the votes for them; the tally then counts as it always
    does. Whether the Skips left now reach 75 % is checked by the caller,
    which knows the time (`end_if_enough_skips`). The
    meeting's copy of the round, from which the winner of the vote is
    worked out, counts them as failed and without their open tasks.
    """
    updated = deepcopy(meeting)
    updated["living"] = tuple(name for name in meeting.get("living", ()) if name != player_id)
    updated["ghosts"] = tuple(name for name in meeting.get("ghosts", ()) if name != player_id)
    updated["votes"] = {
        voter: target
        for voter, target in meeting.get("votes", {}).items()
        if voter != player_id and target != player_id
    }
    updated["skip_votes"] = set(meeting.get("skip_votes", ())) - {player_id}
    if "eliminated" in updated:
        updated["eliminated"] = set(updated["eliminated"]) | {player_id}
    if "tasks" in updated and "completed_tasks" in updated:
        updated["tasks"] = tasks_after_leaving(updated["tasks"], updated["completed_tasks"], player_id)
    return updated


def tally_votes(state: dict) -> EjectResult:
    """Count votes only after voting ends.

    Only living players who pressed Skip count as Skip; a player who did
    not vote counts for nobody. Nobody goes when two players tie for the
    most votes, or when Skip has at least as many votes as the leading player.
    """
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
    skips = len(living.intersection(state.get("skip_votes", ())))
    if skips >= most_votes:
        return EjectResult(None, skips == most_votes, None)
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


def advance_meeting(meeting: dict, now: float) -> dict:
    """Advance elapsed server-side phases, without changing the input state."""
    if not _valid_time(now):
        raise ValueError("Meeting time must be a finite number.")
    updated = deepcopy(meeting)
    while updated["phase"] != "result" and now >= updated["deadline"]:
        ends_by = updated.get("ends_by")
        if updated["phase"] == "discussion" and ends_by is not None and updated["deadline"] >= ends_by:
            # Everybody voted during the discussion (S-215): the meeting ends here.
            updated["phase"] = "result"
            updated = resolve_vote_result(updated)
        elif updated["phase"] == "discussion":
            updated["phase"] = "voting"
            updated["deadline"] += VOTING_SECONDS
            if ends_by is not None:
                updated["deadline"] = min(updated["deadline"], ends_by)
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
        # Votes are public in the meeting UI: every player can see which
        # character voted for which target, as requested for the game flow.
        "voted": list(current.get("votes", {})),
        "vote_targets": dict(current.get("votes", {})),
        # Skip agreements are public, like the fact that someone has voted;
        # they never reveal a vote target. A set has no fixed order, so the
        # names are sorted: every snapshot lists them the same way.
        # (vote_targets and voted follow the dict's order of the votes, which
        # is the same every time.)
        "skip_voted": sorted(current.get("skip_votes", ())),
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
