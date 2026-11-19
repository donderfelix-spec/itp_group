"""Pure rules for setting up and evaluating a Classic round."""

from collections.abc import Collection, Mapping, Sequence
import math
from typing import Literal, NotRequired, Protocol, TypedDict


Role = Literal["HP", "FR"]
TASKS_PER_PLAYER = 4
FAIL_RANGE_TILES = 5.0
FAIL_RANGE = FAIL_RANGE_TILES
FAIL_COOLDOWN_SECONDS = 15.0
FAIL_COOLDOWN = FAIL_COOLDOWN_SECONDS
REPORT_RANGE = 2.0
Position = tuple[float, float]


class RandomSource(Protocol):
    """The part of a random generator used by these rules."""

    def sample(self, population: Sequence[str], k: int) -> list[str]: ...


class ClassicState(TypedDict):
    """State needed to calculate task progress and the round winner.

    ``tasks`` contains genuine assignments for High Performers and fake
    assignments for Free Riders. A player's eliminated status does not remove
    their completed High Performer tasks from the shared progress.
    """

    roles: Mapping[str, Role]
    tasks: Mapping[str, Sequence[str]]
    completed_tasks: Mapping[str, Collection[str]]
    eliminated: Collection[str]
    positions: NotRequired[Mapping[str, Position]]
    last_fail_at: NotRequired[Mapping[str, float]]
    f_sheets: NotRequired[Mapping[str, Position]]
    task_timers: NotRequired[Mapping[str, float]]
    emergency_used: NotRequired[Collection[str]]
    meeting_triggers: NotRequired[Collection[str]]
    pending_meeting_trigger: NotRequired[Mapping[str, object]]
    phase: NotRequired[str]
    meeting: NotRequired[Mapping[str, object]]
    timers_paused: NotRequired[bool]


def assign_roles(player_ids: Sequence[str], rng: RandomSource) -> dict[str, Role]:
    """Assign the required number of Free Riders using the supplied RNG."""
    players = list(player_ids)
    if not 4 <= len(players) <= 8:
        raise ValueError("Classic needs between 4 and 8 players.")
    if any(not isinstance(player_id, str) or not player_id for player_id in players):
        raise ValueError("Player IDs must be non-empty strings.")
    if len(set(players)) != len(players):
        raise ValueError("Player IDs must be unique.")

    free_rider_count = 1 if len(players) <= 5 else 2
    free_riders = set(rng.sample(players, free_rider_count))
    return {
        player_id: "FR" if player_id in free_riders else "HP"
        for player_id in players
    }


def assign_tasks(
    roles: Mapping[str, Role], stations: Sequence[str], rng: RandomSource
) -> dict[str, list[str]]:
    """Give every player four distinct stations; Free Rider assignments are fake."""
    if not roles:
        raise ValueError("At least one player role is required.")
    if any(role not in ("HP", "FR") for role in roles.values()):
        raise ValueError("Roles must be 'HP' or 'FR'.")

    station_list = list(stations)
    if len(station_list) < TASKS_PER_PLAYER:
        raise ValueError("At least 4 stations are required to assign tasks.")
    if any(not isinstance(station, str) or not station for station in station_list):
        raise ValueError("Station IDs must be non-empty strings.")
    if len(set(station_list)) != len(station_list):
        raise ValueError("Station IDs must be unique.")

    return {
        player_id: list(rng.sample(station_list, TASKS_PER_PLAYER))
        for player_id in roles
    }


def progress(state: ClassicState) -> float:
    """Return completed genuine HP tasks divided by all genuine HP tasks.

    Free Rider tasks are fake and ignored. Eliminated High Performers remain in
    the calculation, so their completed work still contributes as a ghost.
    """
    total_tasks = 0
    completed_count = 0
    for player_id, role in state["roles"].items():
        if role != "HP":
            continue
        assigned = set(state["tasks"].get(player_id, ()))
        completed = set(state["completed_tasks"].get(player_id, ()))
        total_tasks += len(assigned)
        completed_count += len(assigned & completed)

    if total_tasks == 0:
        return 0.0
    return min(1.0, completed_count / total_tasks)


def check_winner(state: ClassicState) -> Literal["HP", "FR"] | None:
    """Return the winner, checking High Performer conditions before parity."""
    if progress(state) >= 1.0:
        return "HP"

    roles = state["roles"]
    eliminated = set(state["eliminated"])
    free_riders = {player_id for player_id, role in roles.items() if role == "FR"}
    if free_riders and free_riders <= eliminated:
        return "HP"

    living_free_riders = sum(
        role == "FR" and player_id not in eliminated
        for player_id, role in roles.items()
    )
    living_high_performers = sum(
        role == "HP" and player_id not in eliminated
        for player_id, role in roles.items()
    )
    if living_free_riders >= living_high_performers:
        return "FR"
    return None


def can_fail(state: ClassicState, fr_id: str, target_id: str, now: float) -> bool:
    """Return whether a living Free Rider may fail this nearby HP now."""
    roles = state["roles"]
    eliminated = state["eliminated"]
    if (
        state.get("phase") == "meeting"
        or state.get("timers_paused", False)
        or fr_id == target_id
        or roles.get(fr_id) != "FR"
        or fr_id in eliminated
        or roles.get(target_id) != "HP"
        or target_id in eliminated
    ):
        return False
    if (
        isinstance(now, bool)
        or not isinstance(now, (int, float))
        or not math.isfinite(now)
    ):
        return False

    last_fail_at = state.get("last_fail_at", {}).get(fr_id)
    if last_fail_at is not None:
        if (
            isinstance(last_fail_at, bool)
            or not isinstance(last_fail_at, (int, float))
            or not math.isfinite(last_fail_at)
            or now - last_fail_at < FAIL_COOLDOWN
        ):
            return False

    positions = state.get("positions", {})
    fr_position = positions.get(fr_id)
    target_position = positions.get(target_id)
    if not _valid_position(fr_position) or not _valid_position(target_position):
        return False
    return math.dist(fr_position, target_position) <= FAIL_RANGE


def apply_fail(
    state: ClassicState,
    fr_id: str,
    target_id: str,
    now: float,
    position: Position,
) -> ClassicState:
    """Return a new state with the target ghosted and an F sheet placed."""
    if not can_fail(state, fr_id, target_id, now):
        raise ValueError("The player cannot fail this target right now.")
    if not _valid_position(position):
        raise ValueError("The F-sheet position must contain two finite numbers.")

    updated_state = dict(state)
    updated_state["eliminated"] = set(state["eliminated"]) | {target_id}
    updated_state["last_fail_at"] = {
        **state.get("last_fail_at", {}),
        fr_id: now,
    }
    f_sheets = dict(state.get("f_sheets", {}))
    next_sheet_number = len(f_sheets) + 1
    sheet_id = f"f-sheet-{next_sheet_number}"
    while sheet_id in f_sheets:
        next_sheet_number += 1
        sheet_id = f"f-sheet-{next_sheet_number}"
    f_sheets[sheet_id] = (float(position[0]), float(position[1]))
    updated_state["f_sheets"] = f_sheets
    return updated_state


def _valid_position(position: object) -> bool:
    """Check a two-dimensional position without accepting booleans or NaNs."""
    return (
        isinstance(position, (tuple, list))
        and len(position) == 2
        and all(
            not isinstance(coordinate, bool)
            and isinstance(coordinate, (int, float))
            and math.isfinite(coordinate)
            for coordinate in position
        )
    )


def can_report(
    state: ClassicState, player_id: str, blood_sheet_id: str, position: Position
) -> bool:
    """Return whether a living player is within the 2-field F-sheet interaction range."""
    if state.get("phase") == "meeting" or state.get("timers_paused", False):
        return False
    if player_id in state["eliminated"] or state["roles"].get(player_id) not in ("HP", "FR"):
        return False
    sheet_position = state.get("f_sheets", {}).get(blood_sheet_id)
    if not _valid_position(position) or not _valid_position(sheet_position):
        return False
    return math.dist(position, sheet_position) <= REPORT_RANGE


def can_emergency(state: ClassicState, player_id: str) -> bool:
    """Return whether a living player can still use their emergency button."""
    return (
        state.get("phase") != "meeting"
        and not state.get("timers_paused", False)
        and player_id in state["roles"]
        and state["roles"][player_id] in ("HP", "FR")
        and player_id not in state["eliminated"]
        and player_id not in state.get("emergency_used", ())
    )


def report_sheet(
    state: ClassicState, player_id: str, blood_sheet_id: str, position: Position
) -> ClassicState:
    """Report an F sheet and start its one meeting, returning a new state."""
    if not can_report(state, player_id, blood_sheet_id, position):
        raise ValueError("The player cannot report this F sheet.")
    triggered_state = dict(state)
    triggered_state["pending_meeting_trigger"] = {
        "player_id": player_id,
        "blood_sheet_id": blood_sheet_id,
        "position": tuple(position),
    }
    return start_meeting(triggered_state, "report")


def call_emergency(state: ClassicState, player_id: str) -> ClassicState:
    """Use this player's one emergency call and start the meeting."""
    if not can_emergency(state, player_id):
        raise ValueError("The player cannot call an emergency meeting.")
    triggered_state = dict(state)
    triggered_state["pending_meeting_trigger"] = {"player_id": player_id}
    return start_meeting(triggered_state, "emergency")


def start_meeting(
    state: ClassicState, reason: Literal["report", "emergency"]
) -> ClassicState:
    """Start a meeting for a validated trigger and pause round timers."""
    if reason not in ("report", "emergency"):
        raise ValueError("Meeting reason must be 'report' or 'emergency'.")
    if state.get("phase") == "meeting":
        raise ValueError("A meeting is already active.")

    trigger = state.get("pending_meeting_trigger")
    if not isinstance(trigger, Mapping) or not isinstance(trigger.get("player_id"), str):
        raise ValueError("A meeting needs a validated player trigger.")
    player_id = trigger["player_id"]
    if reason == "report":
        blood_sheet_id = trigger.get("blood_sheet_id")
        position = trigger.get("position")
        if not isinstance(blood_sheet_id, str) or not can_report(
            state, player_id, blood_sheet_id, position
        ):
            raise ValueError("A meeting report needs an unreported F sheet.")
        trigger_id = f"report:{blood_sheet_id}"
    else:
        if not can_emergency(state, player_id):
            raise ValueError("A meeting emergency needs an unused player button.")
        trigger_id = f"emergency:{player_id}"

    meeting_triggers = set(state.get("meeting_triggers", ()))
    if trigger_id in meeting_triggers:
        raise ValueError("This meeting trigger has already been used.")
    meeting_triggers.add(trigger_id)

    updated_state = dict(state)
    living_players = tuple(
        current_id
        for current_id in state["roles"]
        if current_id not in state["eliminated"]
    )
    updated_state["phase"] = "meeting"
    updated_state["meeting"] = {
        "active": True,
        "reason": reason,
        "players": living_players,
    }
    updated_state["timers_paused"] = True
    updated_state["meeting_triggers"] = meeting_triggers
    updated_state.pop("pending_meeting_trigger", None)

    if reason == "report":
        remaining_sheets = dict(state.get("f_sheets", {}))
        del remaining_sheets[blood_sheet_id]
        updated_state["f_sheets"] = remaining_sheets
    else:
        updated_state["emergency_used"] = set(state.get("emergency_used", ())) | {
            player_id
        }

    return updated_state


def end_reason(state: ClassicState) -> Literal[
    "bar_full", "all_free_riders_eliminated", "free_riders_reached_parity"
] | None:
    """Return the user-facing result key in the documented win-check order."""
    if progress(state) >= 1.0:
        return "bar_full"

    roles = state["roles"]
    eliminated = set(state["eliminated"])
    free_riders = {player_id for player_id, role in roles.items() if role == "FR"}
    if free_riders and free_riders <= eliminated:
        return "all_free_riders_eliminated"

    living_free_riders = sum(
        role == "FR" and player_id not in eliminated
        for player_id, role in roles.items()
    )
    living_high_performers = sum(
        role == "HP" and player_id not in eliminated
        for player_id, role in roles.items()
    )
    if living_free_riders >= living_high_performers:
        return "free_riders_reached_parity"
    return None


def role_reveal_for(state: ClassicState, player_id: str) -> dict | None:
    """Build the private start-of-round role card, or None for a ghost/unknown player."""
    role = state["roles"].get(player_id)
    if role not in ("HP", "FR") or player_id in state["eliminated"]:
        return None
    reveal = {"role": role}
    if role == "FR":
        reveal["other_free_riders"] = [
            other_id
            for other_id, other_role in state["roles"].items()
            if other_role == "FR" and other_id != player_id
        ]
    return reveal
