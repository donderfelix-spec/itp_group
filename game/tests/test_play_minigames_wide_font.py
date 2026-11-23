"""The low-window checks of the minigames again, with a wider system font (S-225).

The game ships no font: the page and the canvas use "system-ui, sans-serif",
so every machine draws its own. Our machines draw Inter. Ubuntu without our
font setting draws DejaVu Sans, which is wider: there the chart of station 7
reached 3 px out of a 320 px window (the "−10"/"+10" buttons could not get
narrower than their text). The checks of test_play_minigames_low_windows.py
alone would not see that on our machines.

So this file runs those same checks, imported unchanged, while Chromium
resolves system-ui and sans-serif to DejaVu Sans. The font is chosen with
fontconfig (`FONTCONFIG_FILE`), which Chromium uses on Linux. Skipped
when fontconfig or DejaVu Sans is missing (for example on macOS or
Windows), and, like every play test, without Node, Playwright or Chromium.
"""

import json
import random
import shutil
import subprocess

import pytest

from server.modes import minigames
from test_play_campus_detail import NODE, node_environment
from test_play_minigames_low_windows import (  # noqa: F401 (the checks are collected here again; running_server is a fixture)
    BROWSER_SCRIPT,
    SEEDS,
    STATIONS,
    running_server,
    test_in_a_phone_window_nothing_reaches_out_of_the_window_sideways,
    test_no_page_logs_a_console_error_or_warning,
    test_no_two_controls_and_no_control_and_the_instruction_overlap,
    test_the_instruction_and_every_control_are_in_view_without_scrolling,
    test_the_window_lies_inside_the_viewport,
)

WIDE_FONT = "DejaVu Sans"
# The system's own settings, then DejaVu Sans before every other font for
# the two names the game asks for. A later alias wins over an earlier one.
FONT_SETTINGS = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <include>/etc/fonts/fonts.conf</include>
  <alias binding="strong"><family>system-ui</family><prefer><family>{WIDE_FONT}</family></prefer></alias>
  <alias binding="strong"><family>sans-serif</family><prefer><family>{WIDE_FONT}</family></prefer></alias>
</fontconfig>
"""


def font_of(settings_file, family):
    """The font fontconfig picks for `family` with these settings, or None without fontconfig."""
    if shutil.which("fc-match") is None:
        return None
    environment = {**node_environment(), "FONTCONFIG_FILE": str(settings_file)}
    found = subprocess.run(["fc-match", "-f", "%{family}", family], env=environment,
                           capture_output=True, text=True, timeout=30, check=False)
    return found.stdout.split(",")[0].strip() if found.returncode == 0 else None


@pytest.fixture(scope="module")
def font_settings(tmp_path_factory):
    path = tmp_path_factory.mktemp("wide_font") / "fonts.conf"
    path.write_text(FONT_SETTINGS)
    for family in ("system-ui", "sans-serif"):
        if font_of(path, family) != WIDE_FONT:
            pytest.skip(f"fontconfig with {WIDE_FONT} is needed")
    return path


@pytest.fixture(scope="module")
def played(running_server, font_settings, tmp_path_factory):  # noqa: F811 (the imported fixture)
    """The same openings as test_play_minigames_low_windows.py, drawn with DejaVu Sans."""
    openings = []
    for station in STATIONS:
        minigame = minigames.MINIGAMES[station]
        for seed in SEEDS:
            openings.append({"station": station, "title": minigame.title,
                             "content": minigame.make_content(random.Random(seed))})
    path = tmp_path_factory.mktemp("wide_font_openings") / "openings.json"
    path.write_text(json.dumps(openings))
    environment = {**node_environment(), "FONTCONFIG_FILE": str(font_settings)}
    finished = subprocess.run([NODE, str(BROWSER_SCRIPT), running_server, str(path)],
                              env=environment, capture_output=True, text=True, timeout=240, check=False)
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def test_the_settings_choose_the_wide_font_and_leave_bold_to_it(font_settings):
    # Edge case: the canvas draws the room names in bold; that must be DejaVu too.
    assert font_of(font_settings, "system-ui:bold") == WIDE_FONT
