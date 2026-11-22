"""The drawing of the emergency button stays inside the button (M3-4.24).

The button is the circle campus.button, (365, 375) with radius 11. Hanna drew
it as an alarm switch: a dark round base, a yellow safety plate, a dark red
ring, a raised coral cap with a cream highlight. The page's own drawMap draws
the whole map at 4 pixels per unit with and without the button
(emergency_button_art_in_browser.js); the pixels that differ are the ones the
button adds.

- Accepted: every added pixel lies within the button's radius of its centre,
  and the button adds a clear amount of red or coral and of yellow.
- Rejected: the same check catches a button drawn 6 units off its place or
  with a radius of 14 instead of 11.
- Edge case: while the button is hidden (the first 45 seconds of a round,
  emergencyVisible false or left out), not a single pixel is drawn.

A pixel counts as inside when its centre is at most the radius plus half a
pixel's diagonal from the centre: that is the farthest pixel whose square
still touches the circle, and the edge of a round shape is smoothed into it.

Skipped when Node, Playwright or Chromium is missing.
"""

import json
import math
import subprocess
from pathlib import Path

import pytest

from test_play_campus_detail import (  # noqa: F401 (the fixture)
    NODE,
    needs_chromium,
    node_environment,
    running_server,
)

BROWSER_SCRIPT = Path(__file__).with_name("emergency_button_art_in_browser.js")
# Each colour must cover at least this share of the button's circle.
LEAST_COLOUR_SHARE = 0.08


@pytest.fixture(scope="module")
def measured(running_server):  # noqa: F811 (the imported fixture)
    finished = subprocess.run(
        [NODE, str(BROWSER_SCRIPT), running_server],
        env=node_environment(), capture_output=True, text=True, timeout=120, check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


def farthest_pixel(pixels, centre, scale):
    """How far the farthest pixel centre lies from `centre`, in map units."""
    return max(
        math.hypot((x + 0.5) / scale - centre["x"], (y + 0.5) / scale - centre["y"])
        for x, y, *_colour in pixels
    )


def lies_inside(pixels, button, scale):
    half_pixel_diagonal = math.sqrt(2) / 2 / scale
    return farthest_pixel(pixels, button, scale) <= button["r"] + half_pixel_diagonal


def is_red(red, green, blue):
    # Coral (#F2695C) and the dark red ring (#9E352E), not the paving.
    return red > 140 and red - green > 70 and red - blue > 70


def is_yellow(red, green, blue):
    # The safety plate (#FFD23F).
    return red > 220 and green > 170 and blue < 120


def share_of_circle(count, button, scale):
    circle_pixels = math.pi * (button["r"] * scale) ** 2
    return count / circle_pixels


# ---- The real button ----------------------------------------------------

@needs_chromium
def test_the_map_with_the_button_draws_without_a_console_error_or_warning(measured):
    assert measured["console"] == []


@needs_chromium
def test_the_button_is_the_one_of_the_map(measured):
    assert measured["button"] == {"x": 365, "y": 375, "r": 11}


@needs_chromium
def test_every_pixel_the_button_adds_lies_within_its_radius(measured):
    pixels = measured["drawn"]["real"]
    assert pixels, "the button added no pixel"
    assert lies_inside(pixels, measured["button"], measured["scale"]), \
        farthest_pixel(pixels, measured["button"], measured["scale"])


@needs_chromium
def test_the_button_adds_a_clear_amount_of_red_and_of_yellow(measured):
    pixels = measured["drawn"]["real"]
    red = sum(1 for *_place, r, g, b in pixels if is_red(r, g, b))
    yellow = sum(1 for *_place, r, g, b in pixels if is_yellow(r, g, b))
    assert share_of_circle(red, measured["button"], measured["scale"]) >= LEAST_COLOUR_SHARE, red
    assert share_of_circle(yellow, measured["button"], measured["scale"]) >= LEAST_COLOUR_SHARE, yellow


# ---- Rejected: a drawing off its place or too large -----------------------

@needs_chromium
def test_a_button_drawn_6_units_off_its_place_is_caught(measured):
    assert not lies_inside(measured["drawn"]["moved"], measured["button"], measured["scale"])


@needs_chromium
def test_a_button_drawn_with_radius_14_is_caught(measured):
    assert not lies_inside(measured["drawn"]["enlarged"], measured["button"], measured["scale"])


# ---- Edge case: the hidden button -----------------------------------------

@needs_chromium
def test_nothing_is_drawn_while_the_button_is_hidden(measured):
    assert measured["hidden"] == {"visibleFalse": 0, "leftOut": 0}


# ---- The check itself, without a browser ----------------------------------

BUTTON = {"x": 10, "y": 10, "r": 2}


def test_a_pixel_whose_square_touches_the_circle_counts_as_inside():
    # At 4 pixels per unit, pixel (47, 39) has its centre at (11.875, 9.875):
    # 1.879 from the centre, inside radius 2.
    assert lies_inside([[47, 39, 0, 0, 0]], BUTTON, 4)


def test_a_pixel_more_than_half_a_diagonal_past_the_radius_counts_as_outside():
    # Pixel (49, 39) has its centre at (12.375, 9.875): 2.378 from the
    # centre, more than 2 + 0.177 (half a pixel's diagonal).
    assert not lies_inside([[49, 39, 0, 0, 0]], BUTTON, 4)


def test_the_colours_are_told_apart():
    assert is_red(242, 105, 92) and is_red(158, 53, 46)
    assert is_yellow(255, 210, 63)
    assert not is_red(255, 210, 63) and not is_yellow(242, 105, 92)
    # The paving (light beige) is neither.
    assert not is_red(225, 219, 205) and not is_yellow(225, 219, 205)
