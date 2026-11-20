"""How long a character glides to a new position in the browser (M2-1.12).

The server sends positions once per tick. Over the internet many messages
arrive late. world.js glides each character to its new position over
GLIDE_MILLISECONDS; if that is over before the next message arrives, the
character and the camera stand still for a moment and the picture stutters.
"""

import re
from pathlib import Path

from server.main import TICKS_PER_SECOND

WORLD_JS = Path(__file__).resolve().parent.parent / "client" / "js" / "world" / "world.js"
TICK_MILLISECONDS = 1000 / TICKS_PER_SECOND


def world_js_number(name):
    """A number written as `var NAME = number;` in world.js."""
    match = re.search(rf"var {name} = ([\d.]+);", WORLD_JS.read_text(encoding="utf-8"))
    assert match, name
    return float(match.group(1))


def test_the_glide_time_is_a_plain_number():
    assert world_js_number("GLIDE_MILLISECONDS") > 0


def test_a_message_up_to_40_ms_late_does_not_stop_the_character():
    """The glide lasts at least 40 ms longer than one tick.

    So the next position may arrive up to 40 ms late and the character is
    still gliding: it never stands still between two messages.
    """
    assert world_js_number("GLIDE_MILLISECONDS") >= TICK_MILLISECONDS + 40


def test_the_character_is_never_drawn_more_than_two_messages_behind():
    """The glide lasts at most two ticks (about 133 ms).

    A longer glide would draw the character further behind where the server
    says it is.
    """
    assert world_js_number("GLIDE_MILLISECONDS") <= 2 * TICK_MILLISECONDS
