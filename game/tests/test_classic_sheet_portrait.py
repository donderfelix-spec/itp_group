"""The victim's portrait on the F-sheet (Lennart, Spielfluss-und-Bug-Fixing).

`classic_fail` carries the victim's `character`, and it goes to everybody.
world.js draws that character on the sheet, for every browser, also after
the sheet was reported (it stays on the map, S-150). A sheet without a
character keeps the plain big "F".

The page runs in Node (tests/classic_cleanup_in_node.js). Its stand-in for
drawCharacter writes down every character drawn with its x and transparency;
the portrait is the one at x 0 (the sheet's own centre) drawn at 0.78.
"""

from test_classic_round_end_cleanup import (
    classic_round_as_free_rider,
    meeting_state,
    needs_node,
    run_page,
)
from server.main import app
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_server_features import classic_for, start_classic

SHEET_WITH_PORTRAIT = {
    "type": "classic_fail", "sheet_id": "f-sheet-2", "target_id": "Cy", "character": "c3",
    "position": {"x": 300, "y": 300},
}


def portraits(drawing):
    return [
        drawn["character"] for drawn in drawing["charactersDrawn"]
        if drawn["x"] == 0 and drawn["alpha"] == 0.78
    ]


@needs_node
def test_a_sheet_with_a_character_shows_the_portrait_and_one_without_does_not():
    steps = classic_round_as_free_rider() + [
        ["wait", 50], ["lookAtDrawing"],  # only f-sheet-1, which has no character
        ["receive", SHEET_WITH_PORTRAIT], ["wait", 50], ["lookAtDrawing"],
    ]
    without, with_portrait = run_page(steps)["drawings"]
    assert portraits(without) == []
    assert portraits(with_portrait) == ["c3"]


@needs_node
def test_the_portrait_stays_on_a_reported_sheet():
    report = meeting_state("discussion")
    report[1]["reason"] = "report"
    report[1]["reported_sheet_id"] = "f-sheet-2"
    steps = classic_round_as_free_rider() + [
        ["receive", SHEET_WITH_PORTRAIT], report, ["wait", 50], ["lookAtDrawing"], ["look"],
    ]
    result = run_page(steps)
    assert portraits(result["drawings"][-1]) == ["c3"]
    assert "f-sheet-2" in result["looks"][-1]["sheetIds"]


@needs_node
def test_a_character_that_is_not_text_draws_no_portrait():
    for bad in (None, 7, ["c3"], {"id": "c3"}):
        sheet = dict(SHEET_WITH_PORTRAIT, character=bad)
        steps = classic_round_as_free_rider() + [["receive", sheet], ["wait", 50], ["lookAtDrawing"]]
        assert portraits(run_page(steps)["drawings"][-1]) == []


def test_classic_fail_carries_the_victims_character_to_everybody(connect, clock):
    names = ("Mara", "Tiago", "Ines", "Rui")
    connections, _code, _public, _start = start_classic(connect, names)
    round_state = classic_for(names[0])
    fr_id = next(player for player, role in round_state.roles.items() if role == "FR")
    lobby = app.state.lobbies.lobby_of(fr_id)
    for player in names:
        lobby.walkers._walkers[player].position = (100.0, 100.0)

    connections[fr_id].send_json({"type": "fail"})
    events = [connection.receive_json() for connection in connections.values()]
    assert all(event["type"] == "classic_fail" for event in events)
    victim = events[0]["target_id"]
    assert all(event["character"] == lobby.character_of(victim) for event in events)
    assert isinstance(events[0]["character"], str)
