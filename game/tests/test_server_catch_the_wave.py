"""Station six uses the real task frame and its own minimum time."""

import random
import re
from pathlib import Path

import pytest

from extra_task_helpers import news
from task_helpers import ask, client, clock, connect, open_station, player, put_at_station  # noqa: F401

from server import protocol
from server.modes import catch_the_wave, duel, minigames
from server.world.campus import load_campus
from server.world.paths import SPAWN, station_distances


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


# ---- Added when station 6 was taken over (M4-4.0, S-221) ----

CLIENT = Path(__file__).resolve().parents[1] / "client" / "js" / "minigames" / "catch_the_wave.js"


def client_constant(name):
    """A number the browser's part of the minigame uses, read from its source."""
    match = re.search(r"const " + name + r" = (-?\d+);", CLIENT.read_text())
    assert match, f"expected the constant {name} in catch_the_wave.js"
    return int(match.group(1))


def fastest_honest_solve_ms(wave_duration_ms):
    """How soon after opening a player can have caught all waves at the earliest.

    A wave crosses from WAVE_START to WAVE_END (in % of the scene) in
    `wave_duration_ms`, then PAUSE_MS pass before the next. Only one try
    per wave counts, so the GOAL-th catch comes in wave GOAL - 1, at the
    earliest when its crest reaches the near edge of the catch zone.
    """
    start, end = client_constant("WAVE_START"), client_constant("WAVE_END")
    near_edge = client_constant("BOARD_POSITION") - client_constant("CATCH_MARGIN")
    cycle = wave_duration_ms + client_constant("PAUSE_MS")
    into_the_wave = (near_edge - start) / (end - start) * wave_duration_ms
    return (client_constant("GOAL") - 1) * cycle + into_the_wave


def test_the_minimum_time_never_refuses_a_player_who_really_caught_three_waves():
    # S-19: the server only checks that the time is plausible. The fastest
    # wave is the shortest honest game, about 5.2 s; the server measures from
    # its own "opened" to its receipt of "done", which is never shorter.
    fastest = min(fastest_honest_solve_ms(duration) for duration in (1800, 2400))
    assert catch_the_wave.MINIGAME.min_seconds * 1000 <= fastest
    assert fastest == pytest.approx(5183.5, abs=0.1)


def test_the_minimum_time_still_stops_a_script_that_reports_done_at_once():
    assert catch_the_wave.MINIGAME.min_seconds >= 1


def test_the_content_names_only_the_kind_and_the_speed_of_the_waves():
    # Nothing in it decides the result: the player still has to time three clicks.
    for seed in range(5):
        assert set(catch_the_wave.make_content(random.Random(seed))) == {"kind", "wave_duration_ms"}


def test_station_6_is_neither_the_nearest_nor_the_farthest_station_from_the_spawn():
    # Fair for Duel and Solo (S-94): its ways are measured like every other
    # station's, and it adds no route outside the spread the others have.
    stations = sorted(minigames.MINIGAMES)
    ways = station_distances(load_campus(), stations)
    from_spawn = {station: ways[(SPAWN, station)] for station in stations}
    others = [length for station, length in from_spawn.items() if station != 6]
    assert min(others) < from_spawn[6] < max(others)
