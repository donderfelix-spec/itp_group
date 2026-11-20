"""The lobby screen in narrow windows (M1-1.7).

Three things lay on top of each other in a narrow window:

- the walking hint ran into the button "E Use" when the map was narrow, and
  at 320px it lay on the room name "Pingo Doce";
- the message at the top lay on the lobby code at the top of the panel;
- with the panel below the map, the page scrolls, and the message lay on the
  lobby code as soon as the code was scrolled up.

These tests read the stylesheet as the server sends it, like
test_message_width.py. Where the boxes end up in a window is measured in a
browser at 320, 600, 800, 920 and 1280px.
"""

import re

from server.world.campus import load_campus
from task_helpers import client  # noqa: F401

NARROW_MAP = "@media (max-width: 580px), (min-width: 801px) and (max-width: 960px)"
PANEL_BELOW_MAP = "@media (max-width: 800px)"
LOBBY_MESSAGE = "body:has(#screen-lobby:not([hidden])) .message"
PANEL_WIDTH = 380


def stylesheet_of(client):
    return client.get("/css/style.css").text


def declarations(body):
    """The declarations between the braces of one rule, as a set of lines."""
    without_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    lines = set()
    for line in without_comments.replace(";", ";\n").splitlines():
        if line.strip():
            lines.add(line.strip())
    return lines


def rule_in(text, selector):
    """The declarations of the one rule for `selector` that starts a line in `text`."""
    parts = text.split("\n" + selector + " {")
    assert len(parts) == 2, f"expected exactly one rule for {selector}"
    return declarations(parts[1].split("}")[0])


def media_blocks(stylesheet, query):
    """The inside of every block that starts with `query {`, in order."""
    blocks = []
    for part in stylesheet.split("\n" + query + " {")[1:]:
        # The block ends at the first line that is only a closing brace.
        blocks.append("\n" + part.split("\n}")[0])
    return blocks


def rule_in_media(stylesheet, query, selector):
    """The declarations of `selector` inside the one block of `query` that has it."""
    rules = []
    for block in media_blocks(stylesheet, query):
        parts = block.split("\n  " + selector + " {")
        rules += [declarations(part.split("}")[0]) for part in parts[1:]]
    assert len(rules) == 1, f"expected exactly one rule for {selector} in {query}"
    return rules[0]


def pixels(value):
    """`94px;` -> 94."""
    return int(value.removesuffix(";").removesuffix("px"))


def value_of(rule, name):
    """The value of one declaration, for example "bottom" -> "94px;"."""
    matches = [line.split(":", 1)[1].strip() for line in rule if line.split(":", 1)[0] == name]
    assert len(matches) == 1, f"expected one {name} in {rule}"
    return matches[0]


# ---- The walking hint and "E Use" ----


def test_on_a_wide_map_the_hint_stays_centred_at_the_bottom(client):
    # At 1280px nothing moves: the old rule is untouched.
    rule = rule_in(stylesheet_of(client), ".hint")
    for declaration in ("position: absolute;", "left: 50%;", "bottom: 30px;", "white-space: nowrap;", "transform: translateX(-50%);"):
        assert declaration in rule


def test_e_use_stays_at_the_bottom_right_of_the_map(client):
    rule = rule_in(stylesheet_of(client), ".use-button")
    assert {"right: 34px;", "bottom: 34px;"} <= rule


def test_on_a_narrow_map_the_hint_stands_above_e_use(client):
    hint = rule_in_media(stylesheet_of(client), NARROW_MAP, ".hint")
    use_button = rule_in(stylesheet_of(client), ".use-button")
    # Right edge in line with the button's, and no longer pulled to the middle.
    assert value_of(hint, "right") == value_of(use_button, "right")
    assert "left: auto;" in hint
    assert "transform: none;" in hint
    # Above the button: its distance from the bottom, the button (about 52px
    # high, 51px in Chromium) and at least 4px between the two.
    assert pixels(value_of(hint, "bottom")) >= pixels(value_of(use_button, "bottom")) + 52 + 4


def test_on_a_narrow_map_the_hint_takes_two_lines_that_fit_into_320_pixels(client):
    hint = rule_in_media(stylesheet_of(client), NARROW_MAP, ".hint")
    assert "white-space: normal;" in hint
    assert "text-align: center;" in hint
    # In a 320px window the map has 320 - 2 * 16 px; the hint starts 34px
    # from its right edge, so it must not be wider than what is left.
    width = pixels(value_of(hint, "width"))
    assert width <= 320 - 34 - 2 * 16


def test_a_narrow_map_means_the_same_width_with_and_without_the_panel_next_to_it(client):
    # Up to 800px the panel is below the map, from 801px it is next to it and
    # takes 380px: so a map below 580px is a window below 580px or one from
    # 801px up to 580 + 380 = 960px.
    stylesheet = stylesheet_of(client)
    assert f"grid-template-columns: minmax(0, 1fr) {PANEL_WIDTH}px;" in rule_in(stylesheet, ".screen-lobby")
    assert "(max-width: 580px)" in NARROW_MAP
    assert f"(min-width: 801px) and (max-width: {580 + PANEL_WIDTH}px)" in NARROW_MAP
    assert len(media_blocks(stylesheet, NARROW_MAP)) == 1


def test_no_room_name_lies_where_the_narrow_hint_is_at_the_spawn_point():
    # Measured in Chromium at 320x700, 320x568 and 920x700, the narrow hint
    # covers at most this part of the map around the spawn point (map units,
    # x to the right, y downwards), with a margin of a few units. If a room
    # name or the spawn point moves into it, the hint has to be checked again.
    left, right, top, bottom = -40, 120, 0, 110
    campus = load_campus()
    spawn = campus["spawn"]
    names = [(room["name"], room["label"]) for room in campus["rooms"]]
    names.append((campus["deck_label"]["name"], campus["deck_label"]))
    for name, place in names:
        # The same guess of the width as draw.js: about 8 units per letter,
        # and letters about 13 units high.
        half_width = len(name) * 8 / 2
        x = place["x"] - spawn["x"]
        y = place["y"] - spawn["y"]
        beside = x + half_width < left or x - half_width > right
        above_or_below = y + 7 < top or y - 7 > bottom
        assert beside or above_or_below, f"{name} lies where the hint is on a narrow map"


# ---- The message on the lobby screen ----


def test_next_to_the_panel_the_message_stays_over_the_map(client):
    rule = rule_in(stylesheet_of(client), LOBBY_MESSAGE)
    assert rule == {f"right: calc({PANEL_WIDTH}px + 16px);"}


def test_the_lobby_rule_only_counts_while_the_lobby_screen_is_shown(client):
    # On Start and Home the message keeps the window minus 16px on each side (M1-1.10).
    assert LOBBY_MESSAGE.startswith("body:has(#screen-lobby:not([hidden])) ")
    assert "right: 16px;" in rule_in(stylesheet_of(client), ".message")


def test_with_the_panel_below_the_map_the_message_stands_at_the_bottom(client):
    rule = rule_in_media(stylesheet_of(client), PANEL_BELOW_MAP, LOBBY_MESSAGE)
    assert rule == {"top: auto;", "right: 16px;", "bottom: 16px;"}


def test_the_message_moves_down_exactly_when_the_panel_moves_below_the_map(client):
    # The same window width in both media queries, or there would be widths
    # where the message is at the bottom while the panel is still at the side.
    layout = rule_in_media(stylesheet_of(client), PANEL_BELOW_MAP, ".screen-lobby")
    assert "grid-template-columns: 1fr;" in layout


def test_below_the_panel_there_is_room_for_a_message_of_three_lines(client):
    # A three-line message at 320px is about 95px high and 16px from the bottom.
    panel = rule_in_media(stylesheet_of(client), PANEL_BELOW_MAP, ".panel")
    assert pixels(value_of(panel, "padding-bottom")) >= 95 + 16


def test_the_message_rule_itself_is_not_changed_for_the_lobby(client):
    # Edge case: the lobby rules must not start a line with ".message {",
    # which would make a second rule for every screen.
    stylesheet = stylesheet_of(client)
    assert stylesheet.count("\n.message {") == 1
    assert stylesheet.count("\n.message-error {") == 1
