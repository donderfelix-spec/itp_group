"""The character buttons in the lobby keep their size when the choice changes.

There is no JavaScript test runner in this project, so these tests read the
stylesheet the server hands to the browser (M2-2.8). The heights themselves
were measured in a real browser; these tests only guard the two rules that
make them equal.
"""

import re

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture(scope="module")
def stylesheet() -> str:
    with TestClient(app) as client:
        answer = client.get("/css/style.css")
    assert answer.status_code == 200
    return answer.text


def rule(stylesheet: str, selector: str) -> str:
    """The inside of the rule `selector { ... }` that starts a line."""
    found = re.search(rf"^{re.escape(selector)} \{{(.*?)\}}", stylesheet, re.MULTILINE | re.DOTALL)
    assert found, f"The stylesheet has no rule for {selector}"
    return found.group(1)


def test_all_rows_of_the_character_grid_are_equally_high(stylesheet):
    assert "grid-auto-rows: 1fr;" in rule(stylesheet, ".characters")


def test_the_line_is_hidden_but_keeps_its_room_on_the_other_cards(stylesheet):
    line = rule(stylesheet, ".character-line")
    assert "visibility: hidden;" in line
    assert "display" not in line


def test_the_line_is_shown_on_the_own_card(stylesheet):
    own_line = rule(stylesheet, ".character-own .character-line")
    assert "visibility: visible;" in own_line
    assert "display" not in own_line


def test_the_text_of_a_card_starts_at_the_top(stylesheet):
    # In the middle of the card, the names of one row would not stand at the
    # same height: the hidden line below a name is one or two lines high.
    assert "align-self: flex-start;" in rule(stylesheet, ".character-text")


def test_no_rule_removes_the_line_from_the_layout(stylesheet):
    # A "display: none" anywhere (also in a media query) would make the cards
    # change their height with the choice again.
    for found in re.finditer(r"([^{}]*)\{([^{}]*)\}", stylesheet):
        selectors, body = found.groups()
        if "character-line" in selectors:
            assert "display: none" not in body
