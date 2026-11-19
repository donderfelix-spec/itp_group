"""The sign-up and log-in forms of the page, as far as Python can check them.

There is no JavaScript test runner in this project, so these tests read the
files the server hands to the browser: the eye button at each password field
(M1-2.7) and the text for being signed out by a second log-in (M1-2.8).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app

CLIENT_FOLDER = Path(__file__).resolve().parent.parent / "client"
FORMS = ["signup", "login"]
SIGNED_OUT_TEXT = "You were signed in somewhere else."


@pytest.fixture(scope="module")
def page() -> str:
    with TestClient(app) as client:
        answer = client.get("/")
    assert answer.status_code == 200
    return answer.text


def section(page: str, form: str) -> str:
    """The HTML of one form's screen, from <section ...> to </section>."""
    found = re.search(rf'<section id="screen-{form}".*?</section>', page, re.DOTALL)
    assert found, f"The page has no section screen-{form}"
    return found.group(0)


def tags(html: str, name: str) -> list[str]:
    """Every opening tag `<name ...>` in the HTML, as text."""
    return re.findall(rf"<{name}\b[^>]*>", html)


def eye_buttons(html: str) -> list[str]:
    return [tag for tag in tags(html, "button") if "password-eye" in tag]


@pytest.mark.parametrize("form", FORMS)
def test_each_password_field_has_exactly_one_eye_button(page, form):
    buttons = eye_buttons(section(page, form))
    assert len(buttons) == 1
    assert f'id="{form}-password-eye"' in buttons[0]


def test_the_page_has_no_eye_button_outside_the_two_forms(page):
    assert len(eye_buttons(page)) == len(FORMS)


@pytest.mark.parametrize("form", FORMS)
def test_the_eye_button_cannot_submit_the_form(page, form):
    button = eye_buttons(section(page, form))[0]
    assert 'type="button"' in button


@pytest.mark.parametrize("form", FORMS)
def test_the_eye_button_starts_as_show_password_and_not_pressed(page, form):
    button = eye_buttons(section(page, form))[0]
    assert 'aria-label="Show password"' in button
    assert 'aria-pressed="false"' in button


@pytest.mark.parametrize("form", FORMS)
def test_the_eye_button_names_the_field_it_belongs_to(page, form):
    button = eye_buttons(section(page, form))[0]
    assert f'aria-controls="{form}-password"' in button


@pytest.mark.parametrize("form", FORMS)
def test_the_password_field_starts_hidden(page, form):
    fields = [tag for tag in tags(section(page, form), "input") if 'name="password"' in tag]
    assert len(fields) == 1
    assert f'id="{form}-password"' in fields[0]
    assert 'type="password"' in fields[0]
    assert 'type="text"' not in fields[0]


@pytest.mark.parametrize("form", FORMS)
def test_the_eye_is_drawn_in_the_page_and_hidden_from_screen_readers(page, form):
    icons = tags(section(page, form), "svg")
    assert len(icons) == 1
    assert 'aria-hidden="true"' in icons[0]


@pytest.mark.parametrize("form", FORMS)
def test_the_form_has_no_inline_style(page, form):
    # The Content-Security-Policy forbids inline styles: they would be ignored.
    assert "style=" not in section(page, form)


@pytest.mark.parametrize("script", ["js/lobby/forms.js", "js/main.js"])
def test_the_scripts_of_the_forms_set_no_inline_style(script):
    text = (CLIENT_FOLDER / script).read_text(encoding="utf-8")
    assert "style=" not in text
    assert ".style." not in text
    assert "cssText" not in text


def test_the_stylesheet_is_served_with_the_rules_for_the_eye():
    with TestClient(app) as client:
        answer = client.get("/css/style.css")
    assert answer.status_code == 200
    assert ".password-eye" in answer.text


def test_the_signed_out_text_stands_in_the_client_exactly_once():
    files = [path for path in CLIENT_FOLDER.rglob("*") if path.suffix in {".html", ".js", ".css"}]
    count = sum(path.read_text(encoding="utf-8").count(SIGNED_OUT_TEXT) for path in files)
    assert count == 1


def test_the_signed_out_text_is_not_sent_by_the_server():
    # The browser works out by itself why it was signed out (see main.js).
    server_folder = CLIENT_FOLDER.parent / "server"
    for path in server_folder.rglob("*.py"):
        assert SIGNED_OUT_TEXT not in path.read_text(encoding="utf-8"), path
