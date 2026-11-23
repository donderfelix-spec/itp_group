"""M2-2.11 and S-143: the panel of the round's mode stands first, seen without scrolling.

The clock (`#duel-clock`) and the own next task (`#duel-next`) stood below
the player list in the scrolling middle of the side panel. With eight
players and their progress rows (S-130) they were only seen after
scrolling in a 1280x800 window. Now the Duel panel stands first in the
middle of the panel. S-143 does the same for Classic's "Group progress",
in the same place and with the same spacing (class round-panel).

Checked in Chromium (skipped when Node, Playwright or Chromium is missing),
with the real server: eight guests in one lobby, the host starts a Duel;
the host and one other guest are measured at 1280x800, 1024x700 and
320x640. Then one guest plays Solo alone, and five guests play Classic,
measured the same way. In Classic the panel reads "Classic", the own name,
"Group progress" with label and bar, then "Players"; it has no task card
(S-197). Each Classic page's card at the top left is compared with the one
task it was sent; one High Performer's page is then handed the
`station_done` messages the server sends for its four stations: the card
names each next task, and at the end "All your tasks are done." in green.
The Free Rider's card says "Fake tasks: stand at a station to look busy."
"""

import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from test_play_campus_detail import NODE, node_environment, playwright_works

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_duel_clock_in_browser.js")
WIDE_SIZES = ["1280x800", "1024x700"]
NARROW_SIZE = "320x640"
ALL_SIZES = WIDE_SIZES + [NARROW_SIZE]
WHO = ["host", "guest"]

needs_chromium = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


@pytest.fixture(scope="module")
def running_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)],
        cwd=GAME, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            with contextlib.suppress(OSError):
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            time.sleep(0.1)
        yield base
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="module")
def played(running_server):
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), running_server],
        env=node_environment(), capture_output=True, text=True, timeout=240, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def is_fully_seen(box, panel):
    """Whether `box` lies inside the visible part of the panel's middle and inside the window."""
    visible = panel["visible"]
    window = panel["window"]
    inside_panel = (
        box["top"] >= visible["top"] and box["bottom"] <= visible["bottom"]
        and box["left"] >= visible["left"] and box["right"] <= visible["right"]
    )
    inside_window = box["top"] >= 0 and box["bottom"] <= window["height"] and box["right"] <= window["width"]
    return inside_panel and inside_window


def assert_seen_without_scrolling(panel):
    assert panel["middleScrollTop"] == 0 and panel["pageScrollY"] == 0
    assert panel["clock"] is not None and panel["next"] is not None
    assert is_fully_seen(panel["clock"], panel), (panel["clock"], panel["visible"])
    assert is_fully_seen(panel["next"], panel), (panel["next"], panel["visible"])


# ---- Accepted: the clock and the next task are seen ----


@needs_chromium
@pytest.mark.parametrize("size", WIDE_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_in_a_duel_with_eight_players_clock_and_next_task_are_seen_without_scrolling(played, size, who):
    panel = played["duel"][size][who]
    assert panel["playerRows"] == 8
    assert panel["clockText"] and panel["nextText"].startswith("Next:")
    assert_seen_without_scrolling(panel)


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_the_clock_stands_before_the_player_list(played, size, who):
    panel = played["duel"][size][who]
    assert panel["firstShownId"] == "duel-panel"
    assert panel["clock"]["bottom"] <= panel["players"]["top"]


@needs_chromium
@pytest.mark.parametrize("who", WHO)
def test_at_320_pixels_the_clock_is_not_pushed_below_the_eight_players(played, who):
    panel = played["duel"][NARROW_SIZE][who]
    assert panel["playerRows"] == 8
    assert panel["next"]["bottom"] <= panel["players"]["top"]
    assert not panel["pageScrollsSideways"]


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_solo_shows_the_same_layout_with_its_own_heading(played, size):
    panel = played["solo"][size]
    assert panel["heading"] == "Solo"
    assert panel["firstShownId"] == "duel-panel"
    assert panel["clock"]["bottom"] <= panel["players"]["top"]
    if size in WIDE_SIZES:
        assert_seen_without_scrolling(panel)


# ---- What must stay as it was (S-110, S-113, S-130, lobby, Classic) ----


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_the_duel_player_list_keeps_its_progress_and_the_old_list_stays_gone(played, size):
    for panel in played["duel"][size].values():
        assert panel["progressRows"] == ["0/3"] * 8
        assert panel["bars"] == 8
        assert not panel["oldDuelList"]


@needs_chromium
def test_in_the_lobby_the_panel_starts_with_the_players_as_before(played):
    panel = played["lobby"]
    assert panel["duelPanel"] is None
    assert panel["firstShownId"] == "Players"
    assert panel["playerRows"] == 8
    assert panel["progressRows"] == [] and panel["bars"] == 0
    # The order below the list is unchanged: modes, then the characters.
    assert panel["players"]["bottom"] <= panel["modes"]["top"] <= panel["characterArea"]["top"]


@needs_chromium
def test_in_the_lobby_all_character_buttons_are_equally_high(played):
    heights = played["lobby"]["characterHeights"]
    assert len(heights) == 8
    assert max(heights) - min(heights) < 0.5


# ---- Classic (S-143): the same place and spacing as the Duel panel ----


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_in_classic_the_group_progress_stands_first_above_the_players(played, size, who):
    panel = played["classic"][size][who]
    assert panel["duelPanel"] is None
    assert panel["firstShownId"] == "classic-progress"
    assert panel["playerRows"] == 5
    assert panel["progressRows"] == [] and panel["bars"] == 0
    assert panel["classicProgress"]["bottom"] <= panel["playersHeading"]["top"]


@needs_chromium
@pytest.mark.parametrize("size", WIDE_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_in_classic_heading_name_label_and_track_are_seen_without_scrolling(played, size, who):
    panel = played["classic"][size][who]
    assert panel["classicOwnNameText"]
    assert panel["middleScrollTop"] == 0 and panel["pageScrollY"] == 0
    for part in panel["classicParts"]:
        assert part is not None and is_fully_seen(part, panel), (part, panel["visible"])


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_duel_solo_and_classic_panels_start_at_the_same_height_with_the_same_space_below(played, size):
    panels = [played["duel"][size]["guest"], played["solo"][size], played["classic"][size]["guest"]]
    tops = [(panel["duelPanel"] or panel["classicProgress"])["top"] for panel in panels]
    spaces = [panel["playersHeading"]["top"] - (panel["duelPanel"] or panel["classicProgress"])["bottom"] for panel in panels]
    assert max(tops) - min(tops) < 0.5
    assert max(spaces) - min(spaces) < 0.5


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
def test_duel_solo_and_classic_headings_look_like_the_players_heading(played, size):
    panels = [played["duel"][size]["guest"], played["solo"][size], played["classic"][size]["guest"]]
    for panel in panels:
        assert panel["roundHeadingStyle"] == panel["playersHeadingStyle"]


@needs_chromium
@pytest.mark.parametrize("size", ALL_SIZES)
@pytest.mark.parametrize("who", WHO)
def test_the_classic_panel_reads_classic_name_progress_then_players(played, size, who):
    panel = played["classic"][size][who]
    assert panel["classicHeadingText"] == "Classic"
    assert not panel["classicTaskShown"]  # S-197: no task card in the panel
    order = panel["classicOrder"]  # heading, own name, "Group progress", label, bar
    assert None not in order and order == sorted(order) and len(set(order)) == len(order)
    assert panel["classicTrack"]["bottom"] <= panel["playersHeading"]["top"]


# ---- Classic: the own task in the card at the top left (S-197, before S-154) ----

FAKE_TASKS = "Fake tasks: stand at a station to look busy."
ALL_DONE = "All your tasks are done."


def cards_of(played, role):
    return [card for card in played["classicCards"] if card["role"] == role]


def is_title_of(title, name):
    """`name` is Duel's "Title (Room)" of a station, `title` what the card shows."""
    return bool(title) and name.startswith(title + " (")


@needs_chromium
def test_five_classic_players_have_one_free_rider_and_four_high_performers(played):
    assert len(played["classicCards"]) == 5
    assert len(cards_of(played, "FR")) == 1 and len(cards_of(played, "HP")) == 4


@needs_chromium
def test_a_high_performer_is_sent_one_station_and_the_top_left_card_names_it(played):
    for card in cards_of(played, "HP"):
        assert len(card["taskStations"]) == 1
        assert all(name.endswith(")") and " (" in name for name in card["names"])
        assert not card["cardShown"] and card["cardText"] == ""
        assert is_title_of(card["topTitle"], card["names"][0]), card
        assert card["topNote"] is None


@needs_chromium
def test_the_top_left_card_follows_each_next_task_and_the_panel_stays_without_a_card(played):
    done = played["classicDone"]
    hp = next(card for card in cards_of(played, "HP") if not card["isHost"])
    assert [step["station"] for step in done][0] == hp["taskStations"][0]
    assert len(done) == 4
    for step in done[:-1]:
        assert len(step["left"]) == 1
        assert is_title_of(step["topTitle"], step["nextNames"][0]), step
        assert step["topNote"] is None
        assert not step["cardShown"]


@needs_chromium
def test_with_every_task_done_the_top_left_card_says_so_in_green(played):
    last = played["classicDone"][-1]
    assert last["left"] == []
    assert last["topTitle"] is None
    assert last["topNote"] == ALL_DONE and last["topNoteGreen"]
    assert not last["cardShown"]


@needs_chromium
def test_the_free_rider_card_fakes_and_shows_nothing_of_the_others(played):
    (free_rider,) = cards_of(played, "FR")
    assert free_rider["taskStations"] == [] and free_rider["names"] == []
    assert not free_rider["cardShown"] and free_rider["cardText"] == ""
    assert free_rider["topTitle"] is None
    assert free_rider["topNote"] == FAKE_TASKS and not free_rider["topNoteGreen"]
    for card in cards_of(played, "HP"):
        assert not any(name in free_rider["pageText"] for name in card["names"])


@needs_chromium
def test_no_high_performer_page_shows_the_free_rider_text(played):
    for card in cards_of(played, "HP"):
        assert FAKE_TASKS not in card["pageText"]


@needs_chromium
def test_a_paragraph_at_the_end_of_the_classic_panel_stands_under_the_bar_above_the_players(played):
    panel = played["classicWithHint"]
    extra, track, box = panel["extraParagraph"], panel["classicTrack"], panel["classicProgress"]
    assert extra is not None
    assert extra["top"] >= track["bottom"]
    assert extra["bottom"] <= box["bottom"]
    assert box["bottom"] <= panel["playersHeading"]["top"]


# ---- Edge: nothing is logged ----


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []
