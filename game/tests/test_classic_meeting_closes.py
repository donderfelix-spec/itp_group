"""The meeting window closes shortly after every result (M3-3.10), in the page in Node."""

from test_classic_round_end_cleanup import (
    classic_round_as_free_rider,
    meeting_state,
    needs_node,
    run_page,
)


def a_result(ejected_id, revealed_role, winner=None, tie=False):
    result = meeting_state("result")
    result[1].update({"ejected_id": ejected_id, "revealed_role": revealed_role, "winner": winner, "tie": tie})
    return result


def shown_then_closed(result):
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), result, ["look"], ["wait", 1799], ["look"], ["wait", 1], ["look"],
    ]
    return run_page(steps)["looks"][-3:]


@needs_node
def test_the_window_closes_after_an_ejection():
    shown, still_shown, closed = shown_then_closed(a_result("Bo", "HP"))
    assert shown["meetingHidden"] is False
    assert still_shown["meetingHidden"] is False
    assert closed["meetingHidden"] is True
    assert closed["inputPaused"] is False


@needs_node
def test_the_window_closes_after_a_tie():
    shown, _still_shown, closed = shown_then_closed(a_result(None, None, tie=True))
    assert shown["meetingHidden"] is False
    assert closed["meetingHidden"] is True


@needs_node
def test_a_repeated_result_does_not_open_the_closed_window_again():
    result = a_result("Bo", "HP")
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), result, ["wait", 1800], result, ["look"],
    ]
    assert run_page(steps)["looks"][-1]["meetingHidden"] is True


@needs_node
def test_the_next_meeting_opens_the_window_again():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), a_result("Bo", "HP"), ["wait", 1800],
        meeting_state("discussion"), ["look"],
    ]
    assert run_page(steps)["looks"][-1]["meetingHidden"] is False
