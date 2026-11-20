"""The Profile and Leaderboard icons at the top right of the Home screen (M2-2.7).

These tests read the page and the stylesheet as the server sends them. What
the icons look like and where they sit in a window is tried in a browser.
"""

from html.parser import HTMLParser

from task_helpers import client  # noqa: F401

ICONS = {"home-profile": "Profile", "home-leaderboard": "Leaderboard"}


class Page(HTMLParser):
    """Remembers every button: its attributes, its screen, what is inside it."""

    def __init__(self):
        super().__init__()
        self.screen = None  # id of the <section> being read
        self.button = None  # the <button> being read
        self.buttons = {}  # id -> what is known about the button

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "section":
            self.screen = attributes.get("id")
        elif tag == "button":
            self.button = {"attributes": attributes, "screen": self.screen, "text": "", "inside": []}
            self.button["inside_attributes"] = []
            self.buttons[attributes.get("id")] = self.button
        elif self.button is not None:
            self.button["inside"].append(tag)
            self.button["inside_attributes"].extend(attributes)

    def handle_endtag(self, tag):
        if tag == "button":
            self.button = None
        elif tag == "section":
            self.screen = None

    def handle_data(self, text):
        if self.button is not None:
            self.button["text"] += text.strip()


def buttons_of(client):
    page = Page()
    page.feed(client.get("/").text)
    return page.buttons


def test_both_icons_are_buttons_with_a_name_for_screen_reader_and_mouse(client):
    buttons = buttons_of(client)
    for element_id, name in ICONS.items():
        attributes = buttons[element_id]["attributes"]
        assert attributes["type"] == "button"
        assert attributes["aria-label"] == name
        assert attributes["title"] == name


def test_both_icons_are_drawn_in_the_page_and_carry_no_text(client):
    buttons = buttons_of(client)
    for element_id in ICONS:
        assert buttons[element_id]["inside"][0] == "svg"
        assert "img" not in buttons[element_id]["inside"]
        assert buttons[element_id]["text"] == ""


def test_the_icons_stay_reachable_with_the_keyboard(client):
    buttons = buttons_of(client)
    for element_id in ICONS:
        attributes = buttons[element_id]["attributes"]
        assert "tabindex" not in attributes
        assert "disabled" not in attributes


def test_the_icons_are_on_the_home_screen_only(client):
    buttons = buttons_of(client)
    for element_id in ICONS:
        assert buttons[element_id]["screen"] == "screen-home"
    labels = [button["attributes"].get("aria-label") for button in buttons.values()]
    assert labels.count("Profile") == 1
    assert labels.count("Leaderboard") == 1


def test_the_keyboard_still_starts_on_create_lobby(client):
    # screens.js focuses the first button of a screen, so the icons come after the card.
    home = [element_id for element_id, button in buttons_of(client).items() if button["screen"] == "screen-home"]
    assert home[0] == "home-create"
    assert home[-2:] == ["home-profile", "home-leaderboard"]


def test_the_old_button_row_is_gone_from_page_and_stylesheet(client):
    assert "stats-buttons" not in client.get("/").text
    assert "stats-buttons" not in client.get("/css/style.css").text


def test_the_icons_are_at_least_44_pixels_wide_and_high(client):
    stylesheet = client.get("/css/style.css").text
    rule = stylesheet.split(".icon-button {")[1].split("}")[0]
    assert "width: 48px;" in rule
    assert "height: 48px;" in rule


def test_the_drawings_load_nothing_and_run_nothing(client):
    # A drawing is shapes only: nothing fetched from elsewhere, no code inside.
    buttons = buttons_of(client)
    for element_id in ICONS:
        inside = buttons[element_id]["inside"]
        for tag in ("script", "use", "image"):
            assert tag not in inside
        for attribute in buttons[element_id]["inside_attributes"]:
            assert "href" not in attribute
            assert not attribute.startswith("on")
