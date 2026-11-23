"""Station six uses the real task frame and its own minimum time."""

import random

from extra_task_helpers import news
from task_helpers import ask, client, clock, connect, open_station, player, put_at_station  # noqa: F401

from server import protocol
from server.modes import catch_the_wave, duel


def test_wave_duration_is_seeded_and_stays_within_its_range():
    durations = set()
    for seed in range(20):
        content = catch_the_wave.make_content(random.Random(seed))
        assert content == catch_the_wave.make_content(random.Random(seed))
        assert content["kind"] == "catch_the_wave"
        assert 1800 <= content["wave_duration_ms"] <= 2400
        durations.add(content["wave_duration_ms"])
    assert len(durations) > 1


def test_station_six_opens_and_counts_only_after_its_minimum_time(connect, clock, monkeypatch):
    def route_through_the_wave(names, stations, distances, rng):
        assert 6 in stations
        return {name: (6, 1, 5) for name in names}

    monkeypatch.setattr(duel, "draw_routes", route_through_the_wave)
    mara = player(connect, "Mara")
    assert ask(mara, {"type": "create_lobby"})["mode"] == "solo"
    assert ask(mara, {"type": "start_game"})["phase"] == "round"
    assert protocol.duel_state(6, 0, 3) in news(mara)

    assert open_station(mara, 6) == protocol.rejection("too_far")
    put_at_station("Mara", 6)
    opened = open_station(mara, 6)
    assert (opened["type"], opened["station"], opened["title"]) == ("station_opened", 6, "Catch the wave")
    assert opened["content"]["kind"] == "catch_the_wave"
    assert 1800 <= opened["content"]["wave_duration_ms"] <= 2400

    clock.wait(2.999)
    mara.send_json({"type": "finish_station"})
    assert news(mara) == [protocol.rejection("too_fast"), protocol.station_closed(6)]

    assert open_station(mara, 6)["type"] == "station_opened"
    clock.wait(3)
    mara.send_json({"type": "finish_station"})
    messages = news(mara)
    assert messages[0] == protocol.station_done(6)
    assert protocol.duel_state(1, 1, 3) in messages
