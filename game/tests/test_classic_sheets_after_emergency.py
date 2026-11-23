"""S-230: an emergency meeting closes every F-sheet that lies on the map when it starts.

Those sheets can no longer be reported for the rest of the round
(`rules.call_emergency` marks them as reported); a sheet that comes into a
player's sight later is sent as reported (S-202, `sheet_news`), and a page
that knows a sheet shows no "R Report" for it once the emergency meeting
opens. A player failed after the meeting is reported as usual. A report
meeting closes only its own sheet, as before (S-150).
"""

from rules import call_emergency, can_report, report_sheet
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_round_end_cleanup import (
    SHEET as SHEET_AFTER,
    UNLOCK_WAIT,
    classic_round_as_free_rider,
    meeting_state,
    needs_node,
    run_page,
)


def a_state(sheets):
    return {
        "roles": {"Ana": "FR", "Bo": "HP", "Cy": "HP", "Di": "HP", "Ed": "HP"},
        "eliminated": {"Bo"}, "phase": "round",
        "f_sheets": dict(sheets), "meeting_triggers": set(), "emergency_used": set(),
        "positions": {}, "tasks": {}, "completed_tasks": {},
    }


def resumed(state, **changes):
    """The round going on after the meeting: not paused, as `apply_meeting_result` leaves it."""
    return dict(state, phase="round", timers_paused=False, **changes)


def test_an_emergency_call_closes_every_sheet_on_the_map():
    state = a_state({"f-sheet-1": (0, 0), "f-sheet-2": (100, 0)})
    assert can_report(state, "Cy", "f-sheet-1", (0, 0))

    after = call_emergency(state, "Cy")

    assert not can_report(resumed(after), "Di", "f-sheet-1", (0, 0))
    assert not can_report(resumed(after), "Di", "f-sheet-2", (100, 0))
    assert "emergency:Cy" in after["meeting_triggers"]
    assert state["meeting_triggers"] == set()  # the input is not changed


def test_a_sheet_of_a_fail_after_the_meeting_can_be_reported():
    after = call_emergency(a_state({"f-sheet-1": (0, 0)}), "Cy")
    later = resumed(after, eliminated={"Bo", "Ed"})
    later["f_sheets"] = dict(after["f_sheets"], **{"f-sheet-2": (50, 0)})
    assert can_report(later, "Di", "f-sheet-2", (50, 0))
    assert not can_report(later, "Di", "f-sheet-1", (0, 0))


def test_an_emergency_with_no_sheet_on_the_map_closes_nothing():
    after = call_emergency(a_state({}), "Cy")
    assert after["meeting_triggers"] == {"emergency:Cy"}


def test_a_report_meeting_closes_only_its_own_sheet():
    state = a_state({"f-sheet-1": (0, 0), "f-sheet-2": (100, 0)})
    after = report_sheet(state, "Cy", "f-sheet-1", (0, 0))
    assert not can_report(resumed(after), "Di", "f-sheet-1", (0, 0))
    assert can_report(resumed(after), "Di", "f-sheet-2", (100, 0))


# ---- The server: a sheet seen after the emergency meeting comes as reported -------


def test_a_round_tells_a_sheet_seen_after_the_emergency_as_reported():
    import random

    from server.classic.round import ClassicRound
    from server.main import app

    game = ClassicRound(["Ana", "Bo", "Cy", "Di", "Ed"], list(range(1, 12)), random.Random(1))
    game.roles = {"Ana": "FR", "Bo": "HP", "Cy": "HP", "Di": "HP", "Ed": "HP"}
    game.eliminated = {"Bo"}
    game.f_sheets = {"f-sheet-1": (300.0, 300.0)}
    game.sheet_characters = {"f-sheet-1": "consultant"}
    game.emergency("Cy", 100.0)

    news = game.sheet_news("Di", (300.0, 310.0), app.state.campus)
    assert news == [("f-sheet-1", (300.0, 300.0), "consultant", True)]


# ---- The page ----------------------------------------------------------------------


@needs_node
def test_once_an_emergency_meeting_opens_the_page_offers_no_report_for_a_known_sheet():
    # The own player stands at the sheet (SHEET, next to the red button).
    steps = classic_round_as_free_rider() + [["wait", UNLOCK_WAIT], ["look"]]
    before = run_page(steps)["looks"][-1]
    assert before["reportButtonShown"] is True

    after = run_page(steps + [
        meeting_state("discussion"), ["call", "classicMeeting", "hide"], ["wait", 200], ["look"],
    ])["looks"][-1]
    assert after["reportButtonShown"] is False
    assert "f-sheet-1" in after["sheetIds"]  # still on the map, only no longer reportable


@needs_node
def test_a_report_meeting_does_not_close_the_other_sheets_on_the_page():
    report = meeting_state("discussion")
    report[1].update(reason="report", reported_sheet_id="f-sheet-9")
    looks = run_page(classic_round_as_free_rider() + [
        ["wait", UNLOCK_WAIT], report, ["call", "classicMeeting", "hide"], ["wait", 200], ["look"],
    ])["looks"]
    assert looks[-1]["reportButtonShown"] is True


# ---- Over the WebSocket ------------------------------------------------------------


def test_after_an_emergency_meeting_an_old_sheet_is_refused_and_a_new_one_reported(connect, clock):
    from task_helpers import put
    from test_classic_meeting_once import (  # noqa: I001
        classic_round,
        everybody_skips,
        everything_sent,
        fail,
        read_until,
        start_emergency,
        ticks,
    )

    connections, lobby, fr, [caller, reporter, first_victim, second_victim] = classic_round(connect)
    def sheet_of(victim):
        """Fail `victim` beside the Free Rider; every page has read the news up to the positions."""
        before = set(lobby.classic_round.f_sheets)
        fail(connections, fr, victim)
        assert victim in lobby.classic_round.eliminated
        [sheet_id] = set(lobby.classic_round.f_sheets) - before
        x, y = lobby.classic_round.f_sheets[sheet_id]
        return {"sheet_id": sheet_id, "position": {"x": x, "y": y}}

    old = sheet_of(first_victim)
    start_emergency(connections, caller, clock)
    everybody_skips(connections, lobby, clock)
    ticks(connections, count=1)

    put(reporter, (old["position"]["x"], old["position"]["y"]))
    for connection in connections.values():
        everything_sent(connection)
    connections[reporter].send_json({"type": "report", "sheet_id": old["sheet_id"], "position": old["position"]})
    assert read_until(connections[reporter], "error")[-1]["code"] == "report_rejected"
    for name, connection in connections.items():
        if name != reporter:
            assert everything_sent(connection) == [], name  # heard only by the reporter
    assert lobby.classic_round.phase == "round"

    clock.wait(16)  # the Free Rider's cooldown after the meeting
    ticks(connections, count=1)
    for connection in connections.values():
        everything_sent(connection)
    new = sheet_of(second_victim)  # `fail` puts everybody else far away first
    assert new["sheet_id"] != old["sheet_id"]
    put(reporter, (new["position"]["x"], new["position"]["y"]))
    connections[reporter].send_json({"type": "report", "sheet_id": new["sheet_id"], "position": new["position"]})
    state = read_until(connections[reporter], "meeting_state")[-1]
    assert state["reason"] == "report" and state["reported_sheet_id"] == new["sheet_id"]


@needs_node
def test_a_sheet_failed_after_the_emergency_meeting_shows_report_also_after_a_late_result_copy():
    late_result = meeting_state("result")
    late_result[1].update(ejected_id=None, revealed_role=None, winner=None)
    new_sheet = dict(SHEET_AFTER, sheet_id="f-sheet-2")
    looks = run_page(classic_round_as_free_rider() + [
        ["wait", UNLOCK_WAIT], meeting_state("discussion"), ["call", "classicMeeting", "hide"],
        ["receive", new_sheet], ["wait", 200], ["look"],
        late_result, ["call", "classicMeeting", "hide"], ["wait", 200], ["look"],
    ])["looks"]
    assert looks[0]["reportButtonShown"] is True  # the new sheet, failed after the meeting
    assert looks[1]["reportButtonShown"] is True  # a late copy of the result closes nothing
