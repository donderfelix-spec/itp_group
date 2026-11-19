"""The cache of the leaderboard as a plain class, with the time passed in (M2-2.4)."""

import pytest

from server.accounts.leaderboard_cache import KEEP_SECONDS, LeaderboardCache

STORE = object()
ANSWER = [("Mara", 2, 72.4)]


@pytest.fixture
def cache():
    return LeaderboardCache()


def filled(cache, now=100.0):
    assert cache.put(STORE, ANSWER, now, cache.ticket()) is True
    return cache


def test_answers_are_kept_for_10_seconds():
    assert KEEP_SECONDS == 10


def test_an_empty_cache_has_no_answer(cache):
    assert cache.get(STORE, 100.0) is None


@pytest.mark.parametrize("now", [100.0, 105.0, 109.99])
def test_a_kept_answer_is_served_for_less_than_10_seconds(cache, now):
    assert filled(cache).get(STORE, now) is ANSWER


@pytest.mark.parametrize("now", [110.0, 110.01, 5000.0])
def test_from_10_seconds_on_the_answer_is_too_old(cache, now):
    assert filled(cache).get(STORE, now) is None


def test_an_empty_leaderboard_is_an_answer_too(cache):
    cache.put(STORE, [], 100.0, cache.ticket())
    assert cache.get(STORE, 101.0) == []


def test_a_dropped_answer_is_gone(cache):
    filled(cache).drop()
    assert cache.get(STORE, 100.0) is None


def test_dropping_an_empty_cache_is_harmless(cache):
    cache.drop()
    assert cache.get(STORE, 100.0) is None


def test_an_answer_asked_for_before_a_drop_is_not_kept(cache):
    ticket = cache.ticket()
    cache.drop()  # a result was written while the store was being asked
    assert cache.put(STORE, ANSWER, 100.0, ticket) is False
    assert cache.get(STORE, 100.0) is None


def test_an_answer_asked_for_after_a_drop_is_kept(cache):
    cache.drop()
    assert cache.put(STORE, ANSWER, 100.0, cache.ticket()) is True
    assert cache.get(STORE, 100.0) is ANSWER


def test_the_answer_of_another_store_is_not_served(cache):
    assert filled(cache).get(object(), 100.0) is None


def test_a_newer_answer_replaces_the_older_one_and_starts_its_own_10_seconds(cache):
    filled(cache, now=100.0)
    newer = [("Tiago", 3, None)]
    cache.put(STORE, newer, 108.0, cache.ticket())
    assert cache.get(STORE, 117.9) is newer
    assert cache.get(STORE, 118.0) is None
