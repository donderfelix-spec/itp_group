"""Tests for the rule that keeps a repeating fault from flooding the log (M1-2.15).

First the rule itself (`server/net/repeated_faults.py`), with the time passed
in. Then the server's tick, with a lobby that fails on every tick.
"""

import pytest

from server import main
from server.main import app
from server.net.repeated_faults import QUIET_SECONDS, RepeatedFaults

TICKS_PER_SECOND = 15
ONE_TICK = 1 / TICKS_PER_SECOND


# The rule


def test_the_first_fault_is_logged_at_once():
    faults = RepeatedFaults()
    assert faults.happened("walking", 100.0) == (True, 0)


def test_repeats_within_the_quiet_time_are_not_logged():
    faults = RepeatedFaults()
    faults.happened("walking", 100.0)
    assert faults.happened("walking", 100.1) == (False, 0)
    assert faults.happened("walking", 130.0) == (False, 0)
    assert faults.happened("walking", 159.9) == (False, 0)


def test_the_first_fault_after_the_quiet_time_is_logged_with_the_count():
    faults = RepeatedFaults()
    faults.happened("walking", 0.0)
    for second in range(1, 60):
        faults.happened("walking", float(second))
    # 59 faults were swallowed, at the seconds 1 to 59.
    assert faults.happened("walking", 60.5) == (True, 59)


def test_exactly_the_quiet_time_later_the_fault_is_logged_again():
    faults = RepeatedFaults()
    faults.happened("walking", 10.0)
    faults.happened("walking", 40.0)
    assert faults.happened("walking", 10.0 + QUIET_SECONDS) == (True, 1)


def test_just_before_the_quiet_time_is_over_the_fault_is_not_logged():
    faults = RepeatedFaults()
    faults.happened("walking", 10.0)
    assert faults.happened("walking", 10.0 + QUIET_SECONDS - 0.001) == (False, 0)


def test_the_count_starts_again_after_every_logged_line():
    faults = RepeatedFaults()
    faults.happened("walking", 0.0)
    faults.happened("walking", 30.0)
    faults.happened("walking", 45.0)
    assert faults.happened("walking", 60.0) == (True, 2)
    faults.happened("walking", 90.0)
    assert faults.happened("walking", 120.0) == (True, 1)


def test_a_fault_every_tick_for_a_minute_is_logged_twice():
    faults = RepeatedFaults()
    # Tick 0 is at second 0 and tick 900 at second 60. Whole numbers divided
    # by the rate, so the last time is exactly 60 and not a rounding away.
    answers = [faults.happened("walking", tick / TICKS_PER_SECOND) for tick in range(901)]
    logged = [answer for answer in answers if answer[0]]
    assert logged == [(True, 0), (True, 899)]


def test_two_keys_are_independent():
    faults = RepeatedFaults()
    assert faults.happened(("walking", "ABCD"), 0.0) == (True, 0)
    assert faults.happened(("walking", "ABCD"), 1.0) == (False, 0)
    # Another lobby and another place are both new faults.
    assert faults.happened(("walking", "WXYZ"), 2.0) == (True, 0)
    assert faults.happened(("round end", "ABCD"), 3.0) == (True, 0)
    # The first one goes on counting on its own.
    assert faults.happened(("walking", "ABCD"), 60.0) == (True, 1)
    assert faults.happened(("walking", "WXYZ"), 60.0) == (False, 0)


def test_a_key_may_hold_none_for_a_fault_without_a_lobby():
    faults = RepeatedFaults()
    assert faults.happened(("tick", None), 0.0) == (True, 0)
    assert faults.happened(("tick", None), 1.0) == (False, 0)


def test_a_fault_that_stays_away_is_forgotten():
    faults = RepeatedFaults()
    faults.happened(("walking", "ABCD"), 0.0)
    faults.happened(("walking", "ABCD"), 5.0)
    assert faults.remembered() == 1
    # Another fault, more than the quiet time after ABCD's last one.
    faults.happened(("walking", "WXYZ"), 5.0 + QUIET_SECONDS + 0.1)
    assert faults.remembered() == 1


def test_a_forgotten_fault_that_comes_back_is_logged_at_once_as_new():
    faults = RepeatedFaults()
    faults.happened("walking", 0.0)
    faults.happened("walking", 5.0)  # swallowed
    # More than the quiet time after the last one: logged as a first fault,
    # the old count is gone with the old entry.
    assert faults.happened("walking", 5.0 + QUIET_SECONDS + 0.1) == (True, 0)


def test_a_fault_seen_exactly_the_quiet_time_ago_is_still_remembered():
    faults = RepeatedFaults()
    faults.happened("walking", 0.0)
    faults.happened("round end", float(QUIET_SECONDS))
    assert faults.remembered() == 2


def test_a_fault_that_goes_on_is_not_forgotten():
    faults = RepeatedFaults()
    for second in range(0, 300, 10):
        faults.happened("walking", float(second))
    assert faults.remembered() == 1


def test_many_lobbies_that_closed_leave_nothing_behind():
    faults = RepeatedFaults()
    for number in range(500):
        faults.happened(("walking", f"L{number}"), 0.0)
    assert faults.remembered() == 500
    faults.happened(("walking", "LATE"), 2 * QUIET_SECONDS)
    assert faults.remembered() == 1


# The server's tick


@pytest.fixture(autouse=True)
def quiet_tick():
    """Replaces the fixture of the same name in conftest.py: here the real tick runs."""


class FakeClock:
    """Stands in for the server's clock: the test decides what time it is."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake_clock = FakeClock()
    monkeypatch.setattr(main, "seconds_now", fake_clock)
    return fake_clock


@pytest.fixture(autouse=True)
def fresh_repeated_faults():
    """Every test starts with nothing remembered, and leaves nothing for the tests after it."""
    app.state.repeated_faults = RepeatedFaults()
    yield
    app.state.repeated_faults = RepeatedFaults()


def always_fails(*arguments):
    raise ValueError("secret detail that must not be logged")


def broken_lobby(monkeypatch, code):
    """A lobby whose walking fails on every tick."""
    host = f"Host{code}"
    lobby, rejection_code = app.state.lobbies.create(host, lambda: code)
    assert rejection_code is None
    monkeypatch.setattr(lobby.walkers, "advance", always_fails)
    return lobby


def run_ticks_from_to(clock, start, first_tick, last_tick):
    """Call the tick once for every tick number, at 15 ticks per second of the fake clock."""
    for number in range(first_tick, last_tick + 1):
        clock.now = start + number / TICKS_PER_SECOND
        main.tick(ONE_TICK)


def lines_about(caplog, text):
    return [record.getMessage() for record in caplog.records if text in record.getMessage()]


def test_a_lobby_that_fails_every_tick_writes_one_line(monkeypatch, caplog, clock):
    broken_lobby(monkeypatch, "ABCD")
    with caplog.at_level("ERROR"):
        # Ticks 0 to 899: just under 60 seconds.
        run_ticks_from_to(clock, clock.now, 0, 899)
    assert lines_about(caplog, "The tick failed") == ["The tick failed for one lobby: ValueError"]
    assert "secret detail" not in caplog.text


def test_after_a_minute_a_second_line_names_the_count(monkeypatch, caplog, clock):
    broken_lobby(monkeypatch, "ABCD")
    with caplog.at_level("ERROR"):
        # Ticks 0 to 900: exactly 60 seconds from the first to the last.
        run_ticks_from_to(clock, clock.now, 0, 900)
    assert lines_about(caplog, "The tick failed") == [
        "The tick failed for one lobby: ValueError",
        "The tick failed for one lobby: ValueError (and 899 more times since the last such line)",
    ]
    assert "secret detail" not in caplog.text


def test_a_fault_in_a_second_lobby_is_logged_at_once(monkeypatch, caplog, clock):
    start = clock.now
    broken_lobby(monkeypatch, "ABCD")
    with caplog.at_level("ERROR"):
        run_ticks_from_to(clock, start, 0, 299)
        assert len(lines_about(caplog, "The tick failed")) == 1
        # After 20 seconds a second lobby starts to fail as well.
        broken_lobby(monkeypatch, "WXYZ")
        run_ticks_from_to(clock, start, 300, 300)
        assert len(lines_about(caplog, "The tick failed")) == 2
        run_ticks_from_to(clock, start, 301, 600)
    # Still one line per lobby: neither has failed for a minute yet.
    assert len(lines_about(caplog, "The tick failed")) == 2


def test_the_two_places_of_one_lobby_are_logged_independently(monkeypatch, caplog, clock):
    broken_lobby(monkeypatch, "ABCD")
    monkeypatch.setattr(main, "end_round_if_over", always_fails)
    with caplog.at_level("ERROR"):
        run_ticks_from_to(clock, clock.now, 0, 99)
    assert lines_about(caplog, "The tick failed") == ["The tick failed for one lobby: ValueError"]
    assert lines_about(caplog, "end of a round") == ["The check for the end of a round failed: ValueError"]
    assert "secret detail" not in caplog.text


def test_a_fault_that_comes_back_after_a_quiet_time_is_logged_at_once(monkeypatch, caplog, clock):
    start = clock.now
    lobby = broken_lobby(monkeypatch, "ABCD")
    with caplog.at_level("ERROR"):
        run_ticks_from_to(clock, start, 0, 10)
        # The lobby works again for two minutes, then it breaks again.
        monkeypatch.setattr(lobby.walkers, "advance", lambda seconds, campus: False)
        run_ticks_from_to(clock, start, 11, 1800)
        monkeypatch.setattr(lobby.walkers, "advance", always_fails)
        run_ticks_from_to(clock, start, 1801, 1810)
    assert lines_about(caplog, "The tick failed") == ["The tick failed for one lobby: ValueError"] * 2


def test_a_failing_lobby_still_lets_the_tick_serve_the_next_lobby(monkeypatch, clock):
    broken_lobby(monkeypatch, "ABCD")
    healthy, rejection_code = app.state.lobbies.create("Ines", lambda: "WXYZ")
    advanced = []
    monkeypatch.setattr(healthy.walkers, "advance", lambda seconds, campus: advanced.append(seconds))
    # Also on the ticks whose fault is not logged, the tick must not raise.
    run_ticks_from_to(clock, clock.now, 0, 49)
    assert len(advanced) == 50


def test_the_outer_fault_of_the_loop_is_logged_once(caplog, clock):
    problem = ValueError("secret detail that must not be logged")
    with caplog.at_level("ERROR"):
        for number in range(100):
            clock.now += ONE_TICK
            main.log_tick_fault("A tick failed", None, problem)
    assert lines_about(caplog, "A tick failed") == ["A tick failed: ValueError"]
    assert "secret detail" not in caplog.text
