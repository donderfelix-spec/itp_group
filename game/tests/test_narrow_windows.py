"""The lobby screen in narrow windows (M1-1.7).

Three things lay on top of each other in a narrow window:

- the walking hint ran into the button "E Use" when the map was narrow, and
  at 320px it lay on the room name "Pingo Doce";
- the message at the top lay on the lobby code at the top of the panel;
- with the panel below the map, the page scrolls, and the message lay on the
  lobby code as soon as the code was scrolled up.

These tests read the stylesheet and the page as the server sends them, like
test_message_width.py. Where the boxes end up in a window is measured in a
browser at 320, 600, 800, 920 and 1280px.
"""

import re

from server.world.campus import load_campus
from task_helpers import client  # noqa: F401

PANEL_BELOW_MAP = "@media (max-width: 800px)"
LOBBY_MESSAGE = "body:has(#screen-lobby:not([hidden])) .message"
# The narrow-map query: "a window up to A px, or one above B px up to C px".
NARROW_MAP = re.compile(r"\n@media \(width <= (\d+)px\), \((\d+)px < width <= (\d+)px\) \{")


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


def rule_in_block(block, selector):
    """The declarations of `selector` in one media block, however it is indented, or None."""
    parts = re.split(r"\n[ \t]*" + re.escape(selector) + r" \{", block)
    assert len(parts) <= 2, f"expected at most one rule for {selector}"
    if len(parts) == 1:
        return None
    return declarations(parts[1].split("}")[0])


def rule_in_media(stylesheet, query, selector):
    """The declarations of `selector` inside the one block of `query` that has it."""
    rules = [rule_in_block(block, selector) for block in media_blocks(stylesheet, query)]
    rules = [rule for rule in rules if rule is not None]
    assert len(rules) == 1, f"expected exactly one rule for {selector} in {query}"
    return rules[0]


def narrow_map_block(stylesheet):
    """The three widths of the narrow-map query and the inside of its block."""
    matches = list(NARROW_MAP.finditer(stylesheet))
    assert len(matches) == 1, "expected exactly one media query for a narrow map"
    widths = [int(number) for number in matches[0].groups()]
    block = "\n" + stylesheet[matches[0].end():].split("\n}")[0]
    return widths, block


def pixels(value):
    """`94px;` -> 94."""
    return int(value.removesuffix(";").removesuffix("px"))


def value_of(rule, name):
    """The value of one declaration, for example "bottom" -> "94px;"."""
    matches = [line.split(":", 1)[1].strip() for line in rule if line.split(":", 1)[0] == name]
    assert len(matches) == 1, f"expected one {name} in {rule}"
    return matches[0]


def panel_width(stylesheet):
    """The width of the panel next to the map, from `.screen-lobby`."""
    columns = value_of(rule_in(stylesheet, ".screen-lobby"), "grid-template-columns")
    match = re.fullmatch(r"minmax\(0, 1fr\) (\d+)px;", columns)
    assert match, f"unexpected columns of the lobby: {columns}"
    return int(match.group(1))


def stacked_layout_width(stylesheet):
    """The window width up to which the panel is below the map."""
    for block_start in re.finditer(r"\n@media \(max-width: (\d+)px\) \{", stylesheet):
        block = "\n" + stylesheet[block_start.end():].split("\n}")[0]
        layout = rule_in_block(block, ".screen-lobby")
        if layout and "grid-template-columns: 1fr;" in layout:
            return int(block_start.group(1))
    raise AssertionError("expected the media query that puts the panel below the map")


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
    stylesheet = stylesheet_of(client)
    _, block = narrow_map_block(stylesheet)
    hint = rule_in_block(block, ".hint")
    use_button = rule_in(stylesheet, ".use-button")
    # Right edge in line with the button's, and no longer pulled to the middle.
    assert value_of(hint, "right") == value_of(use_button, "right")
    assert "left: auto;" in hint
    assert "transform: none;" in hint
    # Above the button: its distance from the bottom, the button (about 52px
    # high, 51px in Chromium) and at least 4px between the two.
    assert pixels(value_of(hint, "bottom")) >= pixels(value_of(use_button, "bottom")) + 52 + 4


def test_on_a_narrow_map_the_hint_is_two_lines_whatever_the_font(client):
    # One line per part, and the box only as wide as the longer part: a wider
    # font makes the hint wider, not a third line higher.
    _, block = narrow_map_block(stylesheet_of(client))
    hint = rule_in_block(block, ".hint")
    assert "width: max-content;" in hint
    assert "white-space: normal;" in hint
    assert "display: block;" in rule_in_block(block, ".hint-part")


def test_on_a_narrow_map_the_hint_is_never_wider_than_the_map(client):
    _, block = narrow_map_block(stylesheet_of(client))
    assert value_of(rule_in_block(block, ".hint"), "max-width").startswith("calc(100% - ")


def test_the_hint_has_two_parts_and_still_reads_as_one_sentence(client):
    page = client.get("/").text
    hints = re.findall(r'<p class="hint">(.*?)</p>', page)
    assert len(hints) == 1
    parts = re.findall(r'<span class="hint-part">(.*?)</span>', hints[0])
    assert parts == ["Walk with WASD", "or the arrow keys"]
    # A space between the parts, so on a wide map it is the old single line.
    assert re.sub(r"<[^>]+>", "", hints[0]) == "Walk with WASD or the arrow keys"


def test_a_narrow_map_means_the_same_width_with_and_without_the_panel_next_to_it(client):
    # Up to the stacked-layout width the panel is below the map; above it the
    # panel is next to the map and takes its width. So "the map is at most
    # A px" is "a window up to A px, or one above the stacked width up to A
    # plus the panel".
    stylesheet = stylesheet_of(client)
    (alone, above, up_to), _ = narrow_map_block(stylesheet)
    assert above == stacked_layout_width(stylesheet)
    assert up_to == alone + panel_width(stylesheet)


def test_no_window_width_between_the_two_layouts_is_left_out(client):
    # Edge case: with "min-width: 801px" a zoomed window of 800.5px had the
    # panel next to the map but the centred hint, which ran into "E Use".
    # "800px < width" starts exactly where "max-width: 800px" ends.
    stylesheet = stylesheet_of(client)
    (_, above, _), _ = narrow_map_block(stylesheet)
    assert f"({above}px < width <= " in stylesheet
    assert f"(min-width: {above + 1}px)" not in stylesheet


def test_no_room_name_lies_where_the_narrow_hint_is_at_the_spawn_point():
    # Measured in Chromium at 320x700, 320x568, 600x700 and 920x700, also with
    # letters spaced 1.5px wider (a stand-in for a wider system font), the
    # narrow hint covers at most this part of the map around the spawn point
    # (map units, x to the right, y downwards), with a margin of a few units.
    # If a room name or the spawn point moves into it, check the hint again.
    left, right, top, bottom = -50, 130, 0, 110
    campus = load_campus()
    spawn = campus["spawn"]
    # A room without a label shows no name.
    names = [(room["name"], room["label"]) for room in campus["rooms"] if room.get("label")]
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
    stylesheet = stylesheet_of(client)
    rule = rule_in(stylesheet, LOBBY_MESSAGE)
    assert value_of(rule, "right") == f"calc({panel_width(stylesheet)}px + 16px);"


def test_only_the_lobby_screen_changes_where_the_message_is(client):
    # On Start and Home the message keeps the window minus 16px on each side
    # (M1-1.10): every other rule for the message is only for the lobby screen.
    stylesheet = stylesheet_of(client)
    selectors = [line.strip().removesuffix(" {") for line in stylesheet.splitlines() if line.strip().endswith(".message {")]
    others = [selector for selector in selectors if selector != ".message"]
    assert selectors.count(".message") == 1
    assert others, "expected the rules for the message on the lobby screen"
    assert all(selector == LOBBY_MESSAGE for selector in others)
    assert "right: 16px;" in rule_in(stylesheet, ".message")


def test_with_the_panel_below_the_map_the_message_stands_at_the_bottom(client):
    rule = rule_in_media(stylesheet_of(client), PANEL_BELOW_MAP, LOBBY_MESSAGE)
    assert {"top: auto;", "right: 16px;", "bottom: 16px;"} <= rule


def test_the_message_moves_down_exactly_when_the_panel_moves_below_the_map(client):
    # The same window width in both media queries, or there would be widths
    # where the message is at the bottom while the panel is still at the side.
    stylesheet = stylesheet_of(client)
    width = stacked_layout_width(stylesheet)
    assert rule_in_media(stylesheet, f"@media (max-width: {width}px)", LOBBY_MESSAGE)


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
