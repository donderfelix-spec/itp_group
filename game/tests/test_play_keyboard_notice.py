"""M4-2.2: phones and tablets see "Group Project needs a keyboard." first.

Played in Chromium (skipped when Node, Playwright or Chromium is missing)
with the real server: a phone emulated with touch (coarse pointer, no
hover) sees the notice, "Play anyway" closes it for the visit, a real
walking key closes it too; a desktop browser never sees it.
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
BROWSER_SCRIPT = Path(__file__).with_name("play_keyboard_notice_in_browser.js")
HEADING = "Group Project needs a keyboard."
TEXT = (
    "Walking uses W, A, S, D or the arrow keys, so the game cannot be played on a phone or tablet. "
    "Please open it on a computer."
)

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
        env=node_environment(), capture_output=True, text=True, timeout=180, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def inside(inner, outer):
    return (inner["left"] >= outer["left"] and inner["right"] <= outer["right"]
            and inner["top"] >= outer["top"] and inner["bottom"] <= outer["bottom"])


def apart(upper, lower):
    return upper["bottom"] <= lower["top"]


# ---- Accepted: a phone sees the notice and can still play ----


@needs_chromium
def test_a_phone_sees_the_notice_first(played):
    first = played["phone"]["first"]
    assert first["shown"]
    assert first["heading"] == HEADING
    assert first["text"] == TEXT
    assert first["buttonText"] == "Play anyway"


@needs_chromium
def test_the_notice_is_an_accessible_dialog_with_focus_on_the_button(played):
    first = played["phone"]["first"]
    assert first["role"] == "dialog" and first["modal"] == "true"
    assert first["focused"] == "keyboard-notice-play"
    assert first["behindInert"]


@needs_chromium
def test_play_anyway_closes_it_and_the_lobby_works(played):
    phone = played["phone"]
    assert not phone["closed"]["shown"]
    assert not phone["closed"]["behindInert"]
    assert len(phone["lobbyCode"]) == 4


@needs_chromium
def test_it_stays_closed_after_a_reload_in_the_same_visit(played):
    assert not played["phone"]["afterReload"]["shown"]


@needs_chromium
def test_a_real_walking_key_closes_it(played):
    assert not played["keys"]["afterWalkingKey"]["shown"]


# ---- Rejected: computers, taps behind it, keys that are not walking keys ----


@needs_chromium
def test_a_desktop_browser_never_sees_it(played):
    assert not played["desktop"]["seen"]["shown"]
    assert not played["desktop"]["seen"]["behindInert"]
    assert len(played["desktop"]["lobbyCode"]) == 4


@needs_chromium
def test_a_narrow_desktop_window_never_sees_it(played):
    assert not played["narrowDesktop"]["shown"]


@needs_chromium
def test_a_tap_behind_the_notice_reaches_nothing(played):
    assert played["phone"]["tapBehind"] == "blocked"
    assert not played["phone"]["homeAfterTap"]


@needs_chromium
def test_a_key_from_a_script_or_another_key_does_not_close_it(played):
    assert played["keys"]["afterScriptKey"]["shown"]
    assert played["keys"]["afterOtherKey"]["shown"]


# ---- Edge cases ----


@needs_chromium
def test_a_new_visit_shows_it_again(played):
    assert played["newVisit"]["shown"]


@needs_chromium
def test_without_storage_play_anyway_still_closes_it(played):
    seen = played["noStorage"]
    assert seen["first"]["shown"]
    assert not seen["closed"]["shown"]
    # Nothing could be remembered, so the next load asks again.
    assert seen["afterReload"]["shown"]


@needs_chromium
@pytest.mark.parametrize("index", range(4))
def test_it_fits_in_portrait_and_landscape_without_overlap(played, index):
    size = played["sizes"][index]
    seen = size["seen"]
    assert seen["shown"]
    assert seen["scrollWidth"] <= seen["viewport"]["width"]
    assert seen["noticeScrollWidth"] <= seen["noticeClientWidth"]
    card = seen["card"]
    assert card["left"] >= 0 and card["right"] <= seen["viewport"]["width"]
    for part in ("title", "paragraph", "button"):
        assert inside(seen[part], card), part
    assert apart(seen["title"], seen["paragraph"])
    assert apart(seen["paragraph"], seen["button"])


@needs_chromium
@pytest.mark.parametrize("index", [0, 2])
def test_portrait_sizes_need_no_scrolling_at_all(played, index):
    seen = played["sizes"][index]["seen"]
    assert seen["card"]["top"] >= 0 and seen["card"]["bottom"] <= seen["viewport"]["height"]


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []
