"""A character on a station no longer gets a number badge at its feet (M2-1.10).

There is no JavaScript test runner in this project, so these tests read the
drawing code from its files in client/js/world/ on disk. How the station looks
with a character on it is tried in a browser.
"""

from pathlib import Path

import pytest

WORLD_FOLDER = Path(__file__).resolve().parent.parent / "client" / "js" / "world"

# Names that only the removed badge used. The check looks for each name as
# part of the text, so "drawBadge" also catches "drawBadgesOfHiddenStations".
BADGE_NAMES = [
    "BADGE_RADIUS",
    "BADGE_TEXT_SIZE",
    "STANDING_MARGIN",
    "standsOn",
    "drawBadge",
]


def world_script() -> str:
    return (WORLD_FOLDER / "world.js").read_text(encoding="utf-8")


def draw_script() -> str:
    return (WORLD_FOLDER / "draw.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", BADGE_NAMES)
def test_the_badge_code_is_gone(name):
    assert name not in world_script()


def test_the_station_still_draws_its_own_number():
    # The large number in the station circle comes from draw.js and stays.
    assert "String(station.id)" in draw_script()


def test_the_station_in_range_still_glows():
    assert "Game.world.drawStationGlow(" in world_script()
