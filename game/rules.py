"""Pure rules for setting up and evaluating a Classic round."""

from collections.abc import Collection, Mapping, Sequence
import math
from typing import Literal, NotRequired, Protocol, TypedDict


Role = Literal["HP", "FR"]
TASKS_PER_PLAYER = 4
FAIL_RANGE = 2.0
FAIL_COOLDOWN = 25.0
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
