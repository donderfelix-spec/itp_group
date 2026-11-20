"""The message at the top centre uses the width of the page (M1-1.10).

With `left: 50%` the message could only use the right half of the window, so
on a narrow window it wrapped early (four lines at 320px). These tests read
the stylesheet as the server sends it. How wide the message is in a window
is measured in a browser.
"""

from task_helpers import client  # noqa: F401


def rule_of(client, selector):
    """The declarations of one rule, for example `.message`, as a set of lines."""
    stylesheet = client.get("/css/style.css").text
    # A rule starts at the beginning of a line, so ".checkout-message {" is not found for ".message".
    parts = stylesheet.split("\n" + selector + " {")
    assert len(parts) == 2, f"expected exactly one rule for {selector}"
    body = parts[1].split("}")[0]
    lines = set()
    for line in body.replace(";", ";\n").splitlines():
        line = line.strip()
        if line and not line.startswith("/*") and not line.endswith("*/"):
            lines.add(line)
    return lines


def test_the_message_gets_the_whole_width_minus_16_pixels_on_each_side(client):
    rule = rule_of(client, ".message")
    assert "left: 16px;" in rule
    assert "right: 16px;" in rule


def test_the_message_is_only_as_wide_as_its_text_and_centred(client):
    rule = rule_of(client, ".message")
    assert "width: fit-content;" in rule
    assert "margin: 0 auto;" in rule


def test_the_message_no_longer_starts_in_the_middle_of_the_window(client):
    # `left: 50%` is what limited the message to the right half of the window.
    rule = rule_of(client, ".message")
    assert "left: 50%;" not in rule
    assert not any(line.startswith("transform") for line in rule)


def test_a_long_word_is_broken_instead_of_sticking_out(client):
    assert "overflow-wrap: anywhere;" in rule_of(client, ".message")


def test_the_message_still_looks_like_the_same_pill_at_the_top(client):
    rule = rule_of(client, ".message")
    for declaration in (
        "position: fixed;",
        "top: 16px;",
        "z-index: 10;",
        "padding: 6px 18px;",
        "border: var(--outline);",
        "border-radius: 999px;",
        "background: var(--cream);",
        "box-shadow: var(--shadow);",
        "font-weight: 600;",
        "text-align: center;",
    ):
        assert declaration in rule


def test_the_error_message_only_changes_the_colour(client):
    # So the coral message is placed and sized exactly like the cream one.
    assert rule_of(client, ".message-error") == {"background: var(--coral);"}
