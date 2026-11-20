"""The five minigames in narrow and low windows (M2-4.12).

Two problems in a window of a 320px wide page:

- The window of a minigame is often lower than the minigame. The body of the
  window shrank to what was left and centred the minigame in it, so the top
  of it lay over the title, the close button and the sentence, where no
  scrolling reached it.
- In a window of about 208px inside, slides, dishes, books and products were
  squeezed until their names lay on each other or out of their buttons, the
  books on the shelf and the display of the checkout reached past the window,
  and the window scrolled sideways.

Now the body keeps its full height, and below 420px of room the minigames
are rearranged by container queries on the body. These tests read the
stylesheet as the server sends it, like test_narrow_windows.py, and do the
arithmetic of the layouts. The widths of names were measured in Chromium;
where the boxes end up was measured at every width from 320 to 1280px.
"""

import re

from task_helpers import client  # noqa: F401

NARROW = "@container (width < 420px)"
FEWER_PRODUCTS = "@container (width < 450px)"
FEWEST_PRODUCTS = "@container (width < 230px)"
NARROWEST_PAGE = 320
LOWEST_PAGE = 568  # 320 x 568 is the smallest phone the game is tried on


def stylesheet_of(client):
    return client.get("/css/style.css").text


def declarations(body):
    """The declarations between the braces of one rule, as a set of lines."""
    without_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    return {line.strip() for line in without_comments.replace(";", ";\n").splitlines() if line.strip()}


def rule_of(text, selector):
    """The declarations of the one rule for `selector` that starts a line of `text`."""
    parts = text.split("\n" + selector + " {")
    assert len(parts) == 2, f"expected exactly one rule for {selector}"
    return declarations(parts[1].split("}")[0])


def block_of(stylesheet, query):
    """The inside of the one block that starts with `query {`; it ends at a line that is only `}`."""
    parts = stylesheet.split("\n" + query + " {")
    assert len(parts) == 2, f"expected exactly one block {query}"
    return "\n" + parts[1].split("\n}")[0]


def rule_in_block(block, selector):
    """The declarations of `selector` in a block, however it is indented."""
    parts = re.split(r"\n[ \t]*" + re.escape(selector) + r" \{", block)
    assert len(parts) == 2, f"expected exactly one rule for {selector}"
    return declarations(parts[1].split("}")[0])


def value_of(rule, name):
    values = [line.split(":", 1)[1].strip().removesuffix(";") for line in rule if line.split(":", 1)[0] == name]
    assert len(values) == 1, f"expected one {name} in {rule}"
    return values[0]


def pixels(value):
    return float(value.removesuffix("px"))


def outline(stylesheet):
    match = re.search(r"--outline: ([\d.]+)px solid", stylesheet)
    assert match, "expected the width of --outline"
    return float(match.group(1))


def columns(rule):
    """`repeat(3, minmax(0, 1fr))` -> 3, `minmax(0, 1fr)` -> 1."""
    value = value_of(rule, "grid-template-columns")
    if value == "minmax(0, 1fr)":
        return 1
    match = re.fullmatch(r"repeat\((\d+), minmax\(0, 1fr\)\)", value)
    assert match, f"unexpected columns {value}"
    return int(match.group(1))


def room_of_narrowest_window(stylesheet):
    """The width of the body of a minigame window in a 320px page (about 208px)."""
    backdrop = pixels(value_of(rule_of(stylesheet, ".minigame"), "padding"))
    card = rule_of(stylesheet, ".minigame-window")
    return NARROWEST_PAGE - 2 * backdrop - 2 * pixels(value_of(card, "padding")) - 2 * outline(stylesheet)


def room_of_widest_window(stylesheet):
    """The width of the body of a minigame window at its widest (about 471px)."""
    card = rule_of(stylesheet, ".minigame-window")
    match = re.fullmatch(r"min\(100%, (\d+)px\)", value_of(card, "width"))
    assert match
    return int(match.group(1)) - 2 * pixels(value_of(card, "padding")) - 2 * outline(stylesheet)


def query_width(query):
    return int(re.search(r"width < (\d+)px", query).group(1))


# ---- The body of the window ----


def test_the_body_keeps_its_full_height_so_nothing_lies_on_the_header(client):
    assert "flex-shrink: 0;" in rule_of(stylesheet_of(client), ".minigame-body")


def test_the_brew_order_has_no_rule_of_its_own_for_that_any_more(client):
    # Edge case: the first fix of M2-4.12 was only for "Brew the order".
    assert ".minigame-body:has(" not in stylesheet_of(client)


def test_the_body_is_the_container_the_narrow_rules_ask_about(client):
    # Its width is the room of the minigame, whether the panel is next to the
    # map or below it, so one query fits both layouts of the lobby.
    assert "container-type: inline-size;" in rule_of(stylesheet_of(client), ".minigame-body")


def test_only_the_body_is_a_container(client):
    # An unnamed @container query asks the nearest container: there must be
    # no other one between a minigame and its body.
    assert stylesheet_of(client).count("container-type:") == 1


# ---- When the narrow rules apply ----


def test_the_narrow_rules_apply_in_a_320px_page(client):
    stylesheet = stylesheet_of(client)
    assert room_of_narrowest_window(stylesheet) < query_width(NARROW)


def test_the_narrow_rules_never_apply_in_the_widest_window(client):
    # The window is at its widest at 1280px, so nothing changes there.
    stylesheet = stylesheet_of(client)
    for query in (NARROW, FEWER_PRODUCTS, FEWEST_PRODUCTS):
        assert room_of_widest_window(stylesheet) >= query_width(query)


def test_the_narrow_rules_come_after_the_rules_they_change(client):
    # The selectors are the same, so the later rule wins.
    stylesheet = stylesheet_of(client)
    narrow_starts = stylesheet.index("\n" + NARROW + " {")
    for selector in (".slides-board", ".slides-row", ".tray-game", ".tray-counter", ".books-shelf", ".checkout-display", ".checkout-row", ".checkout-message"):
        assert stylesheet.index("\n" + selector + " {") < narrow_starts, selector
    assert stylesheet.index("\n" + FEWER_PRODUCTS + " {") < stylesheet.index("\n" + FEWEST_PRODUCTS + " {")


# ---- Sort the slides ----


def test_the_places_and_the_pile_stand_in_two_columns(client):
    block = block_of(stylesheet_of(client), NARROW)
    assert "flex-direction: row;" in rule_in_block(block, ".slides-board")
    assert columns(rule_in_block(block, ".slides-row")) == 1


def test_the_whole_board_fits_into_the_window_of_the_lowest_page(client):
    # Nothing scrolls during a drag, so a slide at the bottom of the pile
    # must be dragged to place 1 with both in view. The map is 55% of the
    # page high when the panel is below it, the backdrop keeps 32px free,
    # and the window shows its padding at the end of the scroll.
    stylesheet = stylesheet_of(client)
    block = block_of(stylesheet, NARROW)
    slide = pixels(value_of(rule_in_block(block, ".slides-place,\n  .slides-spot"), "height"))
    gap = pixels(value_of(rule_in_block(block, ".slides-row"), "gap"))
    board_padding = pixels(value_of(rule_of(stylesheet, ".slides-board"), "padding"))
    board = 5 * slide + 4 * gap + 2 * board_padding
    assert "grid-template-rows: 55vh auto;" in stylesheet
    backdrop = pixels(value_of(rule_of(stylesheet, ".minigame"), "padding"))
    card_padding = pixels(value_of(rule_of(stylesheet, ".minigame-window"), "padding"))
    visible = 0.55 * LOWEST_PAGE - 2 * backdrop - 2 * outline(stylesheet) - card_padding
    assert board <= visible


def test_a_low_slide_shows_its_name_and_not_its_sketch(client):
    block = block_of(stylesheet_of(client), NARROW)
    assert "display: none;" in rule_in_block(block, ".slides-sketch")
    assert "aspect-ratio: auto;" in rule_in_block(block, ".slides-place,\n  .slides-spot")


def test_the_longest_slide_name_fits_into_a_column(client):
    # "Analysis" is about 57px wide; a slide has 6px padding on each side.
    stylesheet = stylesheet_of(client)
    gap = pixels(value_of(rule_in_block(block_of(stylesheet, NARROW), ".slides-board"), "gap"))
    column = (room_of_narrowest_window(stylesheet) - 2 * 4 - gap) / 2
    assert column - 2 * 6 - 2 * outline(stylesheet) >= 57


# ---- Build the tray ----


def test_the_slip_stands_above_the_counter_and_two_dishes_fit_in_a_row(client):
    stylesheet = stylesheet_of(client)
    block = block_of(stylesheet, NARROW)
    assert columns(rule_in_block(block, ".tray-game")) == 1
    assert columns(rule_in_block(block, ".tray-counter,\n  .tray-tray")) == 2
    # "Bacalhau" is about 55px wide, a dish has 2px padding and the outline.
    counter = rule_of(stylesheet, ".tray-counter")
    inside = room_of_narrowest_window(stylesheet) - 2 * pixels(value_of(counter, "padding")) - 2 * outline(stylesheet)
    dish = (inside - pixels(value_of(counter, "gap"))) / 2
    assert dish - 2 * 2 - 2 * outline(stylesheet) >= 55


# ---- Shelve the books ----


def test_the_shelf_has_two_boards_of_three_places(client):
    rule = rule_in_block(block_of(stylesheet_of(client), NARROW), ".books-shelf")
    assert "display: grid;" in rule
    assert columns(rule) == 3


def test_a_standing_book_fits_into_its_place(client):
    # A three-digit number in 22px is about 43px wide; the place has a 2px
    # dashed border and the book the outline.
    stylesheet = stylesheet_of(client)
    shelf = rule_of(stylesheet, ".books-shelf")
    left_and_right = pixels(value_of(shelf, "padding").split()[1])
    inside = room_of_narrowest_window(stylesheet) - 2 * left_and_right - 2 * outline(stylesheet)
    place = (inside - 2 * pixels(value_of(shelf, "gap"))) / 3
    assert place - 2 * 2 - 2 * outline(stylesheet) >= 43


# ---- Self-checkout ----


def test_the_total_stands_below_the_target_with_the_line_above_it(client):
    block = block_of(stylesheet_of(client), NARROW)
    assert columns(rule_in_block(block, ".checkout-display")) == 1
    total = rule_in_block(block, ".checkout-line + .checkout-line")
    assert {"padding-left: 0;", "border-left: none;", "border-top: 2px solid var(--cream);"} <= total


def test_target_and_total_side_by_side_need_less_than_the_narrow_width(client):
    # Each line needs about 135px ("Total", 8px, "€12.00" and the thin line),
    # so side by side about 310px with the display's padding: above 420px
    # they still fit.
    stylesheet = stylesheet_of(client)
    display = rule_of(stylesheet, ".checkout-display")
    needed = 2 * 135 + pixels(value_of(display, "gap")) + 2 * 14 + 2 * outline(stylesheet)
    assert needed < query_width(NARROW)


def test_the_message_may_wrap_below_the_name_of_the_row(client):
    block = block_of(stylesheet_of(client), NARROW)
    assert "flex-wrap: wrap;" in rule_in_block(block, ".checkout-area-heading")
    assert "white-space: normal;" in rule_in_block(block, ".checkout-message")


def product_width(stylesheet, room, count):
    """How wide one product's place is with `count` in a row of a body `room` wide."""
    row = rule_of(stylesheet, ".checkout-row")
    inside = room - 2 * pixels(value_of(row, "padding")) - 2 * outline(stylesheet)
    return (inside - (count - 1) * pixels(value_of(row, "gap"))) / count


# "Chocolate" is about 60px wide; a product has 1px padding and the outline.
CHOCOLATE_NEEDS = 60 + 2 * 1 + 2 * 2.5


def test_six_products_in_a_row_fit_wherever_they_stay_six(client):
    stylesheet = stylesheet_of(client)
    assert product_width(stylesheet, query_width(FEWER_PRODUCTS), 6) >= CHOCOLATE_NEEDS


def test_three_products_in_a_row_fit_wherever_they_are_three(client):
    stylesheet = stylesheet_of(client)
    assert columns(rule_in_block(block_of(stylesheet, FEWER_PRODUCTS), ".checkout-row")) == 3
    assert product_width(stylesheet, query_width(FEWEST_PRODUCTS), 3) >= CHOCOLATE_NEEDS


def test_two_products_in_a_row_in_a_320px_page(client):
    stylesheet = stylesheet_of(client)
    assert columns(rule_in_block(block_of(stylesheet, FEWEST_PRODUCTS), ".checkout-row")) == 2
    room = room_of_narrowest_window(stylesheet)
    assert room < query_width(FEWEST_PRODUCTS)
    assert product_width(stylesheet, room, 2) >= CHOCOLATE_NEEDS
