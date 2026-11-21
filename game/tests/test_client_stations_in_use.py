"""The stations main.js lets a Classic player use are the stations with a minigame (brief C).

`STATIONS_IN_USE` in client/js/main.js must list the same stations as
MINIGAMES in server/modes/minigames.py. M3-3.17 will replace the constant
with the player's own task list from the server.
"""

import re
from pathlib import Path

from server.modes import minigames

MAIN_JS = Path(__file__).resolve().parents[1] / "client" / "js" / "main.js"


def stations_in_use_of_main_js():
    found = re.search(r"const STATIONS_IN_USE = \[([0-9, ]*)\];", MAIN_JS.read_text(encoding="utf-8"))
    assert found, "main.js has no STATIONS_IN_USE"
    return [int(number) for number in found.group(1).split(",")]


def test_main_js_lists_exactly_the_stations_with_a_minigame():
    assert stations_in_use_of_main_js() == sorted(minigames.MINIGAMES)


def test_the_list_holds_the_eleven_stations_and_not_station_6():
    stations = stations_in_use_of_main_js()
    assert stations == [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
    assert 6 not in stations
