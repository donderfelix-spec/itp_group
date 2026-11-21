"""The limit on failed log-ins and wrong lobby codes per connection (M1-2.6).

These are the plain rules: no server, no clock. The time is a number the
test chooses.
"""

import pytest

from server.net import attempts
from server.net.attempts import AttemptLimits

KINDS = [
    ("log_in", attempts.LOG_IN_FAILURES_ALLOWED, attempts.LOG_IN_WINDOW_SECONDS),
    ("join_lobby", attempts.JOIN_LOBBY_FAILURES_ALLOWED, attempts.JOIN_LOBBY_WINDOW_SECONDS),
]


def fail(limits, connection, kind, times):
    for now in times:
        limits.failed(connection, kind, now)


def test_the_numbers_of_the_rule():
    assert attempts.LOG_IN_FAILURES_ALLOWED == 5
    assert attempts.LOG_IN_WINDOW_SECONDS == 60
    assert attempts.JOIN_LOBBY_FAILURES_ALLOWED == 10
    assert attempts.JOIN_LOBBY_WINDOW_SECONDS == 60


# Allowed


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_a_new_connection_is_not_blocked(kind, allowed, window):
    assert not AttemptLimits().is_blocked("a", kind, 0.0)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_one_failure_under_the_limit_is_still_allowed(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [0.0] * (allowed - 1))
    assert not limits.is_blocked("a", kind, 0.0)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_failures_spread_over_more_than_the_window_never_block(kind, allowed, window):
    limits = AttemptLimits()
    step = window / (allowed - 1) + 0.5  # so any window holds fewer than `allowed`
    for number in range(50):
        now = number * step
        assert not limits.is_blocked("a", kind, now)
        limits.failed("a", kind, now)


# Blocked


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_exactly_at_the_limit_the_next_attempt_is_blocked(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [float(number) for number in range(allowed)])
    assert limits.is_blocked("a", kind, float(allowed))


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_the_block_holds_for_the_whole_window(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [100.0] * allowed)
    for later in (0, 1, window / 2, window - 0.001):
        assert limits.is_blocked("a", kind, 100.0 + later)


# The edges of the window


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_exactly_one_window_later_is_still_blocked_and_just_after_is_not(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [100.0] * allowed)
    assert limits.is_blocked("a", kind, 100.0 + window)
    assert not limits.is_blocked("a", kind, 100.0 + window + 0.001)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_the_block_ends_when_the_oldest_failure_is_too_old(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [float(number) for number in range(allowed)])  # 0, 1, 2, ...
    assert limits.is_blocked("a", kind, window)  # the failure at 0 is exactly one window old
    assert not limits.is_blocked("a", kind, window + 0.5)  # now it has dropped out


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_the_window_slides_one_failure_at_a_time(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [float(number) for number in range(allowed)])  # 0, 1, 2, ...
    # Each second one old failure drops out and makes room for exactly one new one.
    for number in range(allowed):
        now = window + number + 0.5
        assert not limits.is_blocked("a", kind, now)
        limits.failed("a", kind, now)
        assert limits.is_blocked("a", kind, now)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_asking_while_blocked_does_not_extend_the_block(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [0.0] * allowed)
    # A script keeps trying, once a second. The server only asks `is_blocked`
    # for a refused attempt, and asking changes nothing.
    for second in range(1, window + 1):
        assert limits.is_blocked("a", kind, float(second))
    assert not limits.is_blocked("a", kind, window + 0.001)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_more_failures_than_allowed_are_not_kept(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [0.0] * (allowed * 3))
    assert len(limits._failures["a"][kind]) == allowed


# What is independent of what


def test_the_kinds_are_counted_separately():
    limits = AttemptLimits()
    fail(limits, "a", "log_in", [0.0] * attempts.LOG_IN_FAILURES_ALLOWED)
    assert limits.is_blocked("a", "log_in", 1.0)
    assert not limits.is_blocked("a", "join_lobby", 1.0)

    fail(limits, "b", "join_lobby", [0.0] * attempts.JOIN_LOBBY_FAILURES_ALLOWED)
    assert limits.is_blocked("b", "join_lobby", 1.0)
    assert not limits.is_blocked("b", "log_in", 1.0)


def test_five_wrong_lobby_codes_do_not_block_joining():
    limits = AttemptLimits()
    fail(limits, "a", "join_lobby", [0.0] * attempts.LOG_IN_FAILURES_ALLOWED)
    assert not limits.is_blocked("a", "join_lobby", 1.0)


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_the_connections_are_counted_separately(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [0.0] * allowed)
    fail(limits, "b", kind, [0.0] * (allowed - 1))
    assert limits.is_blocked("a", kind, 1.0)
    assert not limits.is_blocked("b", kind, 1.0)
    assert not limits.is_blocked("c", kind, 1.0)


def test_an_unknown_kind_is_a_mistake_in_the_code():
    with pytest.raises(KeyError):
        AttemptLimits().is_blocked("a", "sign_up", 0.0)


# Forgetting


@pytest.mark.parametrize("kind, allowed, window", KINDS)
def test_forget_drops_everything_about_one_connection(kind, allowed, window):
    limits = AttemptLimits()
    fail(limits, "a", kind, [0.0] * allowed)
    fail(limits, "b", kind, [0.0] * allowed)
    limits.forget("a")
    assert not limits.knows("a")
    assert not limits.is_blocked("a", kind, 1.0)
    assert limits.is_blocked("b", kind, 1.0)
    assert limits.count() == 1


def test_forgetting_an_unknown_connection_does_nothing():
    limits = AttemptLimits()
    limits.forget("nobody")
    assert limits.count() == 0


def test_asking_stores_nothing():
    limits = AttemptLimits()
    assert not limits.is_blocked("a", "log_in", 0.0)
    assert not limits.knows("a")
    assert limits.count() == 0
