"""Self-checkout: the message "Unexpected item in the bagging area" is seen (M2-4.12).

In a 320px wide page the belt stands in three rows and is taller than the
visible part of the minigame window. The message stands below the belt, so a
click on a product that is too expensive showed it out of view and the player
saw nothing happen. Now the minigame asks the browser to bring the message
into view with `scrollIntoView({block: 'nearest', inline: 'nearest'})`:
the window scrolls just far enough, and not at all when the message is
already in view, so wide windows behave as before.

The page's own self_checkout.js runs in Node (tests/self_checkout_in_node.js)
with a stand-in document that writes down every scrollIntoView call. That the
smallest scroll really shows the message at 320 x 568 and 320 x 700 and moves
nothing at 1280 x 800 was checked in Chromium.

Without Node these tests are skipped; CI has Node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SELF_CHECKOUT_IN_NODE = Path(__file__).parent / "self_checkout_in_node.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")

TOO_MUCH_TEXT = "Unexpected item in the bagging area"
MESSAGE_VISIBLE_MS = 1800
NEAREST = {"block": "nearest", "inline": "nearest"}
BRING_MESSAGE_INTO_VIEW = [{"element": "checkout-message", "options": NEAREST}]

# The places on the belt, in the order of PRODUCTS below.
WATER, BREAD, CHEESE, APPLES, COFFEE, CHOCOLATE = range(6)
PRODUCTS = [
    {"name": "Water", "cents": 150},
    {"name": "Bread", "cents": 200},
    {"name": "Cheese", "cents": 350},
    {"name": "Apples", "cents": 100},
    {"name": "Coffee", "cents": 400},
    {"name": "Chocolate", "cents": 250},
]
# Bread and Apples make 3.00. Cheese and Coffee alone are already too much.
CONTENT = {"kind": "self_checkout", "products": PRODUCTS, "target_cents": 300}


def play(steps):
    """Run the minigame with these steps; one result per step (see self_checkout_in_node.js)."""
    finished = subprocess.run(
        [NODE, str(SELF_CHECKOUT_IN_NODE)],
        input=json.dumps({"content": CONTENT, "steps": steps}),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


# Accepted: a product that is too expensive brings the message into view


@needs_node
def test_a_too_expensive_product_brings_the_message_into_view_with_the_smallest_scroll():
    [after] = play([["click", COFFEE]])
    assert after["message"] == TOO_MUCH_TEXT
    assert after["scrolls"] == BRING_MESSAGE_INTO_VIEW


@needs_node
def test_the_too_expensive_product_stays_on_the_belt_and_the_total_is_unchanged():
    [after] = play([["click", COFFEE]])
    assert "Coffee" in after["onBelt"]
    assert after["inBag"] == []
    assert after["total"] == "€0.00"
    assert after["solved"] is False


@needs_node
def test_after_some_products_a_too_expensive_one_also_brings_the_message_into_view():
    _, after = play([["click", WATER], ["click", CHOCOLATE]])
    assert after["message"] == TOO_MUCH_TEXT
    assert after["scrolls"] == BRING_MESSAGE_INTO_VIEW
    assert after["inBag"] == ["Water"]
    assert after["total"] == "€1.50"


# No message, no scroll


@needs_node
def test_an_accepted_product_scrolls_nothing():
    [after] = play([["click", WATER]])
    assert after["message"] == ""
    assert after["scrolls"] == []
    assert after["inBag"] == ["Water"]
    assert after["total"] == "€1.50"


@needs_node
def test_putting_a_product_back_scrolls_nothing():
    _, after = play([["click", WATER], ["click", WATER]])
    assert after["message"] == ""
    assert after["scrolls"] == []
    assert after["inBag"] == []
    assert after["total"] == "€0.00"


@needs_node
def test_solving_the_task_scrolls_nothing():
    _, after = play([["click", BREAD], ["click", APPLES]])
    assert after["solved"] is True
    assert after["total"] == "€3.00"
    assert after["scrolls"] == []


# The message still goes away as before, without scrolling


@needs_node
def test_the_message_disappears_after_its_time_without_a_scroll():
    _, still_there, gone = play([["click", COFFEE], ["wait", MESSAGE_VISIBLE_MS - 1], ["wait", 1]])
    assert still_there["message"] == TOO_MUCH_TEXT
    assert gone["message"] == ""
    assert still_there["scrolls"] == gone["scrolls"] == []


@needs_node
def test_the_message_disappears_on_the_next_accepted_click_without_a_scroll():
    _, after = play([["click", COFFEE], ["click", WATER]])
    assert after["message"] == ""
    assert after["scrolls"] == []
    assert after["inBag"] == ["Water"]


# Edge case: a second too-expensive click while the message is shown


@needs_node
def test_a_second_too_expensive_click_while_the_message_is_shown_brings_it_into_view_again():
    # Between the clicks the player may have scrolled the belt back into view.
    _, _, after = play([["click", COFFEE], ["wait", 1000], ["click", CHEESE]])
    assert after["message"] == TOO_MUCH_TEXT
    assert after["scrolls"] == BRING_MESSAGE_INTO_VIEW
    assert "Cheese" in after["onBelt"]
    assert after["total"] == "€0.00"


@needs_node
def test_after_a_second_too_expensive_click_the_message_stays_its_full_time_again():
    steps = [["click", COFFEE], ["wait", 1000], ["click", CHEESE],
             ["wait", MESSAGE_VISIBLE_MS - 1], ["wait", 1]]
    *_, still_there, gone = play(steps)
    assert still_there["message"] == TOO_MUCH_TEXT
    assert gone["message"] == ""
