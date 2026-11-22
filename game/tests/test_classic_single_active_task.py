"""Lennart's sequential Classic assignments and action ranges."""

import random

from rules import can_report, FAIL_RANGE_TILES, REPORT_RANGE
from server.classic.round import ClassicRound
from server.main import classic_task_stations


def test_only_the_first_unfinished_assignment_is_available():
    game = ClassicRound(["Ana", "Bo", "Cy", "Di"], [1, 2, 3, 4, 5], random.Random(5))
    player = next(name for name, role in game.roles.items() if role == "HP")
    first, second = map(int, game.tasks[player][:2])
    assert game.stations_needed(player, set(), []) == [first]
    assert classic_task_stations(game, player) == [first]
    game.station_done(player, second)
    assert game.completed_tasks[player] == set()
    game.station_done(player, first)
    assert game.stations_needed(player, set(), []) == [second]
    assert classic_task_stations(game, player) == [second]


def test_free_rider_can_report_own_sheet_at_doubled_range():
    state = {
        "roles": {"Free": "FR", "Victim": "HP"},
        "eliminated": {"Victim"}, "phase": "round",
        "f_sheets": {"f-sheet-1": (0, 0)}, "meeting_triggers": set(),
    }
    assert REPORT_RANGE == 8
    assert FAIL_RANGE_TILES == 20
    assert can_report(state, "Free", "f-sheet-1", (8, 0))
    assert not can_report(state, "Free", "f-sheet-1", (8.01, 0))
    state["meeting_triggers"].add("report:f-sheet-1")
    assert not can_report(state, "Free", "f-sheet-1", (0, 0))
