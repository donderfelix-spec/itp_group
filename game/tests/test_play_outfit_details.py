"""The play test of to-do M2-1.18 "outfit details and softer face", as repeatable tests.

A tester played it in Chromium with two guests, one at pixel density 2 (A)
and one at density 1 (B): each guest took every one of the eight characters
in turn (the other guest gave way when it held the one wanted, a taken
character being greyed out), stood, walked left and walked right with real
key presses. tests/play_outfit_details_in_browser.js repeats that and reads
the pixels the page drew:

- in the lobby, the icon of every character: the torso band where its motif
  lies, at both densities;
- on the map, the own figure (the camera keeps it in the middle of the
  canvas): every drawn frame while it stands and while it walks, the pixels
  of the motif's colour in a band of the torso, and where their middle is,
  in map units from the figure's middle.

The tests of tests/test_outfit_details.py check the drawing exactly in Node;
these check that the page, with the real map and the real walking, shows it.

The icon's canvas is checked at density 2 (96 x 96 pixels). At density 1
(48 x 48), and still more as the page shows it on a character button (the
stylesheet shrinks it to 36 x 36 CSS pixels), the Consultant's tie clip, the
Finance Bro's pin, the Exchange Student's patches, the Founder's diamond and
the Library Local's book are blended into their surroundings: no pixel shows
their colour even half strong. Whether they must be recognisable that small
is a question of design, not of the acceptance criteria, so the browser
script reports it (icons -> dsf1, and `shown`) and the tester's report says
it; it is not checked here.

Skipped when Node, Playwright or Chromium is missing.
"""

import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from server import protocol

GAME = Path(__file__).resolve().parents[1]
BROWSER_SCRIPT = Path(__file__).with_name("play_outfit_details_in_browser.js")
NODE = shutil.which("node")
NPM = shutil.which("npm")

GUESTS = ["A", "B"]  # A at pixel density 2, B at density 1
WALKS = ["left", "right"]

# The middle of the turned body, in map units from the figure's middle: the
# body reaches from x = -18 to 17 of the design (112 units high), the figure
# on the map is 39 units high.
TURNED_BODY_MIDDLE = -0.5 * 39 / 112
# How far the middle of the motif may lie from it while the figure stands
# (pixels at density 1 are about 0.2 map units).
STANDING_SPREAD = 0.4
# While walking, the body leans into the direction (at most 0.11 rad) and
# bobs; the motif must still lie in the middle half of the torso (the turned
# body is about 12 map units wide).
WALKING_SPREAD = 3.0
# From one drawn frame to the next the motif may move this far (map units).
# A jump of the drawing (a frame with the motif elsewhere) would be more.
LARGEST_STEP_BETWEEN_FRAMES = 1.0
# Walking left is the mirror of walking right.
MIRROR_SPREAD = 0.4
# A swinging hand may cover part of a motif (the Exchange Student's patch);
# in every frame at least this share of the standing figure's pixels shows.
LEAST_SHARE_WHILE_WALKING = 0.4
# A motif in a 96 x 96 icon shows at least this strong in some pixel
# (0 is the colour below it, 1 its own colour; thin lines are blended).
LEAST_ICON_STRENGTH = 0.7


def node_environment():
    environment = dict(os.environ)
    if NPM:
        root = subprocess.run([NPM, "root", "-g"], capture_output=True, text=True, check=False).stdout.strip()
        environment["NODE_PATH"] = os.pathsep.join(filter(None, [environment.get("NODE_PATH"), root]))
    return environment


def playwright_works():
    if NODE is None:
        return False
    probe = "require('playwright').chromium.launch().then(b => b.close())"
    try:
        finished = subprocess.run(
            [NODE, "-e", probe], env=node_environment(), capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return finished.returncode == 0


pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


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
        env=node_environment(), capture_output=True, text=True, timeout=300, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def every_figure():
    return [(guest, character) for guest in GUESTS for character in protocol.CHARACTERS]


def middle(frames):
    return sum(frame["x"] for frame in frames) / len(frames)


def test_both_guests_play_every_character_without_a_console_error_or_warning(played):
    assert played["console"] == []


def test_no_choice_of_a_free_character_is_rejected(played):
    assert played["rejections"] == {"A": [], "B": []}


def test_the_browser_script_plays_all_eight_characters_for_both_guests(played):
    for guest in GUESTS:
        assert sorted(played["map"][guest]) == sorted(protocol.CHARACTERS)
    assert sorted(played["icons"]["dsf2"]) == sorted(protocol.CHARACTERS)


@pytest.mark.parametrize("character", protocol.CHARACTERS)
def test_every_motif_shows_in_its_lobby_icon_at_density_2(played, character):
    icon = played["icons"]["dsf2"][character]["drawn"]
    assert icon["size"] == [96, 96]
    assert icon["strongest"] >= LEAST_ICON_STRENGTH, icon
    assert icon["strong"] >= 2, icon


@pytest.mark.parametrize(("guest", "character"), every_figure())
def test_the_standing_figure_shows_its_motif_in_the_middle_of_the_torso(played, guest, character):
    frames = played["map"][guest][character]["standing"]
    assert all(frame["count"] >= 4 for frame in frames), frames
    for frame in frames:
        assert abs(frame["x"] - TURNED_BODY_MIDDLE) <= STANDING_SPREAD, frame


@pytest.mark.parametrize(("guest", "character"), every_figure())
@pytest.mark.parametrize("walk", WALKS)
def test_the_motif_shows_in_every_walking_frame(played, guest, character, walk):
    standing = played["map"][guest][character]["standing"][0]["count"]
    frames = played["map"][guest][character][walk]
    assert len(frames) >= 20
    shown = [frame["count"] for frame in frames]
    assert min(shown) >= LEAST_SHARE_WHILE_WALKING * standing, shown


@pytest.mark.parametrize(("guest", "character"), every_figure())
@pytest.mark.parametrize("walk", WALKS)
def test_the_motif_stays_on_the_middle_of_the_torso_while_walking(played, guest, character, walk):
    for frame in played["map"][guest][character][walk]:
        assert abs(frame["x"] - TURNED_BODY_MIDDLE) <= WALKING_SPREAD, frame


@pytest.mark.parametrize(("guest", "character"), every_figure())
@pytest.mark.parametrize("walk", WALKS)
def test_the_motif_does_not_jump_between_walking_frames(played, guest, character, walk):
    frames = played["map"][guest][character][walk]
    for before, after in zip(frames, frames[1:]):
        assert abs(after["x"] - before["x"]) <= LARGEST_STEP_BETWEEN_FRAMES, (before, after)
        assert abs(after["y"] - before["y"]) <= LARGEST_STEP_BETWEEN_FRAMES, (before, after)


@pytest.mark.parametrize(("guest", "character"), every_figure())
def test_walking_left_shows_the_motif_mirrored_from_walking_right(played, guest, character):
    figure = played["map"][guest][character]
    assert abs(middle(figure["left"]) + middle(figure["right"])) <= MIRROR_SPREAD
