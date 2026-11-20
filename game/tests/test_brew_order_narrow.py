"""The minigame "Brew the order" in narrow windows (M2-4.12).

In a 320px wide window the order slip and the coffee machine stood next to
each other in a window of about 206px inside: the content reached from -13
to 354px, part of it was cut off and the window scrolled sideways. Now the
machine moves below the slip when the two do not fit, and its buttons stand
in two columns when three do not fit.

These tests read the stylesheet and the script as the server sends them,
like test_narrow_windows.py, and do the arithmetic of the layout. Where the
boxes end up was measured in Chromium at every width from 320 to 1280px.
"""

import re

from task_helpers import client  # noqa: F401

# The narrowest page the game is made for.
NARROWEST_PAGE = 320


def stylesheet_of(client):
    return client.get("/css/style.css").text


def rule_of(stylesheet, selector):
    """The declarations of the one rule for `selector` that starts a line, as a set of lines."""
    parts = stylesheet.split("\n" + selector + " {")
    assert len(parts) == 2, f"expected exactly one rule for {selector}"
    body = re.sub(r"/\*.*?\*/", "", parts[1].split("}")[0], flags=re.DOTALL)
    return {line.strip() for line in body.replace(";", ";\n").splitlines() if line.strip()}


def value_of(rule, name):
    """The value of one declaration, for example "gap" -> "14px"."""
    values = [line.split(":", 1)[1].strip().removesuffix(";") for line in rule if line.split(":", 1)[0] == name]
    assert len(values) == 1, f"expected one {name} in {rule}"
    return values[0]


def pixels(value):
    """`"14px"` -> 14.0."""
    return float(value.removesuffix("px"))


def flex_parts(rule):
    """`flex: 1 1 282px` -> (1, 1, 282.0): grow, shrink, basis."""
    grow, shrink, basis = value_of(rule, "flex").split()
    return int(grow), int(shrink), pixels(basis)


def outline_width(stylesheet):
    """The width of the border every card and button has, from `--outline: 2.5px solid ...`."""
    match = re.search(r"--outline: ([\d.]+)px solid", stylesheet)
    assert match, "expected the width of --outline"
    return float(match.group(1))


def widest_card_inside(stylesheet):
    """The room inside the window of a minigame at its widest (520px in a wide page)."""
    card = rule_of(stylesheet, ".minigame-window")
    match = re.fullmatch(r"min\(100%, (\d+)px\)", value_of(card, "width"))
    assert match, "expected the window of a minigame to be at most a fixed width"
    return int(match.group(1)) - 2 * pixels(value_of(card, "padding")) - 2 * outline_width(stylesheet)


def narrowest_card_inside(stylesheet):
    """The room inside the window of a minigame in a 320px wide page.

    Up to 800px the map has the whole width of the page, and the backdrop
    keeps its padding free on both sides of the window.
    """
    backdrop = pixels(value_of(rule_of(stylesheet, ".minigame"), "padding"))
    card = rule_of(stylesheet, ".minigame-window")
    card_width = NARROWEST_PAGE - 2 * backdrop
    return card_width - 2 * pixels(value_of(card, "padding")) - 2 * outline_width(stylesheet)


def panel_inside(stylesheet, machine_width):
    """The room for the buttons in a machine of this width: minus its border and the panel's padding."""
    padding = value_of(rule_of(stylesheet, ".brew-panel"), "padding").split()
    left_and_right = pixels(padding[1]) * 2
    return machine_width - 2 * outline_width(stylesheet) - left_and_right


def button_columns(stylesheet):
    """The smallest width of a button column, from `repeat(auto-fit, minmax(80px, 1fr))`."""
    columns = value_of(rule_of(stylesheet, ".brew-panel"), "grid-template-columns")
    match = re.fullmatch(r"repeat\(auto-fit, minmax\((\d+)px, 1fr\)\)", columns)
    assert match, f"expected as many button columns as fit, not {columns}"
    return int(match.group(1))


def columns_that_fit(stylesheet, machine_width):
    """How many button columns the grid makes in a machine of this width."""
    room = panel_inside(stylesheet, machine_width)
    gap = pixels(value_of(rule_of(stylesheet, ".brew-panel"), "gap"))
    smallest = button_columns(stylesheet)
    # n columns need n * smallest + (n - 1) * gap.
    return int((room + gap) // (smallest + gap))


# ---- Slip and machine: next to each other, or one below the other ----


def test_the_machine_moves_below_the_slip_when_the_two_do_not_fit(client):
    assert "flex-wrap: wrap;" in rule_of(stylesheet_of(client), ".brew-layout")


def test_in_the_widest_window_slip_and_machine_still_stand_next_to_each_other(client):
    stylesheet = stylesheet_of(client)
    _, _, slip = flex_parts(rule_of(stylesheet, ".brew-slip"))
    _, _, machine = flex_parts(rule_of(stylesheet, ".brew-machine"))
    gap = pixels(value_of(rule_of(stylesheet, ".brew-layout"), "gap"))
    # A row breaks when the starting widths do not fit into it.
    assert slip + gap + machine <= widest_card_inside(stylesheet)


def test_in_the_widest_window_the_machine_is_as_wide_as_before(client):
    # Before M2-4.12 the machine was always 306px. Slip and machine share the
    # free room equally, so the machine reaches its full width when half the
    # free room covers the rest up to it. Then a wide window looks as before.
    stylesheet = stylesheet_of(client)
    slip_grow, _, slip = flex_parts(rule_of(stylesheet, ".brew-slip"))
    machine_rule = rule_of(stylesheet, ".brew-machine")
    machine_grow, _, machine = flex_parts(machine_rule)
    full_width = pixels(value_of(machine_rule, "max-width"))
    gap = pixels(value_of(rule_of(stylesheet, ".brew-layout"), "gap"))
    free = widest_card_inside(stylesheet) - slip - gap - machine
    assert full_width == 306
    assert slip_grow == machine_grow == 1
    assert free / 2 >= full_width - machine


def test_the_slip_starts_at_its_smallest_width(client):
    # Edge case: a starting width above `min-width` would make the row break
    # earlier than needed, for room the slip does not need.
    rule = rule_of(stylesheet_of(client), ".brew-slip")
    _, _, basis = flex_parts(rule)
    assert basis == pixels(value_of(rule, "min-width"))


def test_alone_in_its_row_the_machine_fits_into_the_narrowest_window(client):
    # The machine may shrink and has no fixed width any more, so a 320px page
    # does not push it out of the window.
    stylesheet = stylesheet_of(client)
    rule = rule_of(stylesheet, ".brew-machine")
    _, shrink, basis = flex_parts(rule)
    assert shrink == 1
    assert not any(line.startswith("width:") for line in rule)
    assert basis > narrowest_card_inside(stylesheet), "the case this test is about"


# ---- The six buttons ----


def test_next_to_the_slip_three_buttons_stand_in_a_row(client):
    # The smallest machine next to the slip still has the three columns of before.
    stylesheet = stylesheet_of(client)
    _, _, machine = flex_parts(rule_of(stylesheet, ".brew-machine"))
    assert columns_that_fit(stylesheet, machine) == 3


def test_in_the_widest_window_there_are_three_columns_as_before(client):
    stylesheet = stylesheet_of(client)
    full_width = pixels(value_of(rule_of(stylesheet, ".brew-machine"), "max-width"))
    assert columns_that_fit(stylesheet, full_width) == 3


def test_in_the_narrowest_window_two_buttons_stand_in_a_row(client):
    stylesheet = stylesheet_of(client)
    assert columns_that_fit(stylesheet, narrowest_card_inside(stylesheet)) == 2


def test_a_button_column_is_wide_enough_to_be_clicked_easily(client):
    # Players click these buttons in a hurry: at least about 40px each.
    assert button_columns(stylesheet_of(client)) >= 40


def test_hot_water_is_still_the_longest_button_name(client):
    # 80px per column holds "Hot water" on one line (79.3px in Chromium with
    # its 15px font, padding and border). A longer name needs a new check.
    script = client.get("/js/minigames/brew_order.js").text
    match = re.search(r"const BUTTON_NAMES = \[(.*?)\];", script)
    assert match, "expected the six button names in brew_order.js"
    names = re.findall(r"'([^']+)'", match.group(1))
    assert len(names) == 6
    assert max(names, key=len) == "Hot water"
    assert all(len(name) <= len("Hot water") for name in names)
    assert "white-space: nowrap;" in rule_of(stylesheet_of(client), ".brew-button")


# ---- A window lower than the minigame ----


def test_the_body_of_the_window_keeps_the_full_height_of_the_brew_order(client):
    # Shrunk to what is left of a low window, the body centred the slip over
    # the header and the sentence, where no scrolling reached it.
    rule = rule_of(stylesheet_of(client), ".minigame-body:has(> .brew-layout)")
    assert rule == {"flex-shrink: 0;"}


def test_the_brew_layout_is_a_direct_child_of_the_body(client):
    # The rule above finds the body by `> .brew-layout`: the script puts the
    # layout straight into the body it gets from the frame.
    script = client.get("/js/minigames/brew_order.js").text
    assert "const layout = element('div', 'brew-layout');" in script
    assert "body.append(layout);" in script

