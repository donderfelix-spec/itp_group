"""Classic draws its task lists from all twelve stations (Felix, brief C).

The server gives ClassicRound the stations with a minigame, stations 1 to 12. Every player still gets four different stations, the Free Rider's
list is still fake, and a High Performer can finish a new station.
"""

import random

from server import main
from server.classic.round import ClassicRound
from server.modes import minigames

TWELVE = list(range(1, 13))
NAMES = ["Mara", "Tiago", "Ines", "Rui", "Sofia", "Duarte"]


def test_the_server_gives_classic_the_twelve_stations_with_a_minigame(monkeypatch):
    given = {}

    class Recorder:
        def __init__(self, names, stations, rng, started_at):
            given["stations"] = list(stations)
            self.stations_needed = lambda *values: []

    class Lobby:
        def names(self):
            return NAMES[:4]

    monkeypatch.setattr(main, "ClassicRound", Recorder)
    main.set_up_classic(Lobby())
    assert given["stations"] == sorted(minigames.MINIGAMES) == TWELVE


def test_every_player_gets_four_different_stations_out_of_the_twelve():
    seen = set()
    for seed in range(200):
        round_ = ClassicRound(NAMES, TWELVE, random.Random(seed))
        for name in NAMES:
            # S-197: the four are the drawn list; only its first one is needed at a time.
            needed = [int(station) for station in round_.tasks[name]]
            assert len(needed) == len(set(needed)) == 4
            assert set(needed) <= set(TWELVE)
            seen.update(needed)
    assert seen == set(TWELVE)


def test_a_high_performer_can_finish_a_new_station_and_a_free_rider_never_counts():
    for seed in range(50):
        round_ = ClassicRound(NAMES, TWELVE, random.Random(seed))
        for name, role in round_.roles.items():
            station = int(round_.tasks[name][0])  # S-197: the Free Rider has no active task
            round_.station_done(name, station)
            if role == "HP":
                assert round_.completed_tasks[name] == {str(station)}
            else:
                assert round_.completed_tasks[name] == set()
