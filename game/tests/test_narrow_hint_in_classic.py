"""M3-1.8: on a narrow map the walking hint makes room for "R Report" and the Free Rider's E button.

On a narrow map the hint stands right above "E Use" (tests/test_narrow_windows.py).
In a Classic round "R Report" and the Free Rider's own E button stand there
too (S-195), so the hint goes for the Classic round on a narrow map (S-201):
the players walked in the lobby before. In the lobby, in a Duel and on a wide
map it stays where it is.
"""

import re

from test_narrow_windows import client, narrow_map_block, stylesheet_of  # noqa: F401 (client is a fixture)

HIDDEN_IN_CLASSIC = re.compile(
    r"\n[ \t]*body:has\(#classic-progress:not\(\[hidden\]\)\) \.hint \{\s*display: none;\s*\}"
)


def test_on_a_narrow_map_the_hint_goes_while_the_classic_panel_is_shown(client):
    _, block = narrow_map_block(stylesheet_of(client))
    assert HIDDEN_IN_CLASSIC.search(block)


def test_on_a_wide_map_the_hint_stays_in_classic_too(client):
    stylesheet = stylesheet_of(client)
    _, block = narrow_map_block(stylesheet)
    outside = stylesheet.replace(block[1:], "")  # the block starts with an added newline
    assert not HIDDEN_IN_CLASSIC.search(outside)


def test_the_classic_panel_starts_hidden_so_the_lobby_keeps_the_hint(client):
    page = client.get("/").text
    assert re.search(r'<div id="classic-progress"[^>]*\shidden[\s>]', page)
