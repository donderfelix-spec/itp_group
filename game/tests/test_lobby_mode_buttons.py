"""M2-2.13: the mode buttons of the lobby, checked in Chromium with the real server.

Felix saw a chosen mode that does not fit the number of players in pale
yellow and a locked mode that is not chosen in grey. Now:

- every locked mode has the same grey (same colours, same opacity, same
  pixel on screen); the chosen one is marked only by its dark frame and
  shadow; a chosen mode that fits is still yellow;
- the round "?" leaves the same gap above, below and to its right inside
  its mode button, can still be tapped on a 24 x 24 px square, opens its
  text on a click and shows an outline on keyboard focus;
- no page logs a console error or warning.

Checked alone with Duel chosen, alone with Solo chosen and with two
players, at 1280x800 and 320x640. At 1280x800 also with 1, 2, 3 and 4
players (Felix, 2026-11-22: a mode fits only between its minimum and maximum, so
Classic is locked below 4), with Classic chosen by 4 players and after
one of them left. Skipped when Node, Playwright or Chromium is missing.
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
BROWSER_SCRIPT = Path(__file__).with_name("lobby_mode_buttons_in_browser.js")
SUN = "rgb(255, 210, 63)"
WHY_TEXTS = {
    "duel": "Duel needs at least 2 players.",
    "solo": "Solo is only for one player alone.",
    "classic": "Classic needs at least 4 players.",
}
INK = "rgb(46, 42, 59)"

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


def every_situation(played):
    """(viewport, situation name, situation) for every lobby state that was looked at."""
    for viewport, situations in played["situations"].items():
        for name, situation in situations.items():
            yield viewport, name, situation


def button(situation, mode):
    return next(b for b in situation["buttons"] if b["mode"] == mode)


def locked(situation):
    return [b for b in situation["buttons"] if b["disabled"]]


@needs_chromium
def test_no_page_logs_a_console_error_or_warning(played):
    assert played["console"] == []


@needs_chromium
def test_both_viewports_and_all_three_states_were_looked_at(played):
    assert set(played["situations"]) == {"wide", "narrow", "counts"}
    for viewport in ("wide", "narrow"):
        assert set(played["situations"][viewport]) == {"alone_duel", "alone_solo", "two"}
    assert set(played["situations"]["counts"]) == {"one", "two", "three", "four", "four_classic", "three_classic"}


@needs_chromium
def test_the_expected_modes_are_locked_and_chosen(played):
    for viewport, name, situation in every_situation(played):
        chosen = [b["mode"] for b in situation["buttons"] if b["chosen"]]
        unfit = sorted(b["mode"] for b in situation["buttons"] if b["unfit"])
        expected = {
            "alone_duel": (["duel"], ["classic", "duel"]),
            "alone_solo": (["solo"], ["classic", "duel"]),
            "two": (["duel"], ["classic", "solo"]),
            "one": (["duel"], ["classic", "duel"]),
            "three": (["duel"], ["classic", "solo"]),
            "four": (["duel"], ["solo"]),
            "four_classic": (["classic"], ["solo"]),
            "three_classic": (["classic"], ["classic", "solo"]),
        }[name]
        assert (chosen, unfit) == expected, (viewport, name)


@needs_chromium
def test_every_locked_mode_has_the_same_grey_chosen_or_not(played):
    looks = set()
    for viewport, name, situation in every_situation(played):
        for b in locked(situation):
            looks.add((b["background"], b["opacity"], tuple(b["pixel"])))
    assert len(looks) == 1, looks
    background, opacity, pixel = looks.pop()
    assert opacity == "1"  # the grey is see-through in its colour, not the whole button
    # The grey #D9D3C5 at 60% over the cream panel #F4EFE3, as before M2-2.13.
    expected = [0.6 * grey + 0.4 * cream for grey, cream in zip((217, 211, 197), (244, 239, 227))]
    assert all(abs(seen - wanted) <= 2 for seen, wanted in zip(pixel, expected)), pixel


@needs_chromium
def test_the_chosen_mode_that_does_not_fit_keeps_its_dark_frame_and_shadow(played):
    for viewport, name, situation in every_situation(played):
        for b in situation["buttons"]:
            if b["chosen"]:
                assert b["boxShadow"] == f"{INK} 3px 3px 0px 0px", (viewport, name, b["mode"])
                assert b["borderColor"] == INK, (viewport, name, b["mode"])
            else:
                assert b["boxShadow"] == "none", (viewport, name, b["mode"])
    # Duel chosen while alone: locked, grey, but marked.
    duel = button(played["situations"]["wide"]["alone_duel"], "duel")
    assert duel["disabled"] and duel["unfit"] and duel["background"] != SUN


@needs_chromium
def test_a_chosen_mode_that_fits_is_still_yellow(played):
    for viewport, name, mode in [
        ("wide", "alone_solo", "solo"), ("narrow", "alone_solo", "solo"),
        ("wide", "two", "duel"), ("narrow", "two", "duel"), ("counts", "four_classic", "classic"),
    ]:
        chosen = button(played["situations"][viewport][name], mode)
        assert chosen["background"] == SUN and chosen["pixel"] == [255, 210, 63], (viewport, name)


@needs_chromium
def test_every_question_mark_has_even_gaps_inside_its_mode_button(played):
    seen = set()
    for viewport, name, situation in every_situation(played):
        assert situation["whys"], (viewport, name)
        for why in situation["whys"]:
            seen.add(why["mode"])
            gaps = why["gaps"]
            assert max(gaps.values()) - min(gaps.values()) <= 1, (viewport, name, why)
            assert min(gaps.values()) > 0, (viewport, name, why)
    assert seen == {"duel", "solo", "classic"}


@needs_chromium
def test_the_text_of_a_mode_never_runs_under_its_question_mark(played):
    for viewport, name, situation in every_situation(played):
        for why in situation["whys"]:
            assert why["textRoomEnd"] <= 0, (viewport, name, why)


@needs_chromium
def test_every_question_mark_can_be_tapped_on_24_by_24_px_and_opens_its_text(played):
    for viewport, name, situation in every_situation(played):
        for why in situation["whys"]:
            assert why["hit24"], (viewport, name, why["mode"])
            assert why["clickOpens"], (viewport, name, why["mode"])


@needs_chromium
def test_every_question_mark_shows_an_outline_on_keyboard_focus(played):
    for viewport, name, situation in every_situation(played):
        for why in situation["whys"]:
            outline = why["outline"]
            assert outline["focused"] and outline["focusVisible"], (viewport, name, why["mode"])
            assert outline["style"] != "none" and outline["width"] >= 2, (viewport, name, why["mode"])


@needs_chromium
def test_exactly_the_modes_that_do_not_fit_are_locked_and_show_their_question_mark(played):
    for viewport, name, situation in every_situation(played):
        unfit = {b["mode"] for b in situation["buttons"] if b["unfit"]}
        locked_modes = {b["mode"] for b in locked(situation)}
        assert locked_modes == unfit, (viewport, name)  # the others can be chosen
        assert {why["mode"]: why["text"] for why in situation["whys"]} == {mode: WHY_TEXTS[mode] for mode in unfit}, (viewport, name)


@needs_chromium
def test_classic_chosen_by_four_stays_chosen_after_another_lobby_state(played):
    classic = button(played["situations"]["counts"]["four_classic"], "classic")
    assert classic["chosen"] and not classic["disabled"] and classic["background"] == SUN


@needs_chromium
def test_classic_stays_chosen_but_locked_when_a_player_leaves(played):
    situation = played["situations"]["counts"]["three_classic"]
    classic = button(situation, "classic")
    assert classic["chosen"] and classic["unfit"] and classic["disabled"]
    assert classic["boxShadow"] == f"{INK} 3px 3px 0px 0px" and classic["borderColor"] == INK
    assert classic["pixel"] == button(situation, "solo")["pixel"]  # the same grey as Solo
    assert "classic" in {why["mode"] for why in situation["whys"]}
    assert situation["start"] == {"disabled": True, "hint": "Classic needs 1 more player"}
