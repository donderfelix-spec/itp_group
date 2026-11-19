"""The running server: pages, security headers and the WebSocket connection."""

import pytest
from fastapi.testclient import TestClient

from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "protocol": 1}


def test_start_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Group Project" in response.text


def test_script_and_stylesheet_are_served(client):
    assert client.get("/js/main.js").status_code == 200
    assert client.get("/css/style.css").status_code == 200


def test_connection_script_is_served(client):
    assert client.get("/js/net.js").status_code == 200


@pytest.mark.parametrize("name", ["screens.js", "forms.js", "lobby.js"])
def test_lobby_scripts_are_served(client, name):
    assert client.get(f"/js/lobby/{name}").status_code == 200


def test_start_page_loads_every_script_it_needs_in_order(client):
    page = client.get("/").text
    scripts = ["js/net.js", "js/lobby/screens.js", "js/lobby/forms.js", "js/lobby/lobby.js", "js/main.js"]
    places = [page.index(f'<script src="{script}">') for script in scripts]
    assert places == sorted(places)


def test_start_page_has_no_inline_script_or_style(client):
    # The Content-Security-Policy would block them, and the page would break silently.
    page = client.get("/").text
    assert "<style" not in page
    assert " style=" not in page
    assert " onclick=" not in page
    assert page.count("<script") == page.count("<script src=")


def test_start_page_loads_the_world_scripts_between_connection_and_lobby(client):
    # The lobby scripts and main.js call Game.world, so the world scripts come first.
    page = client.get("/").text
    scripts = [
        "js/net.js",
        "js/world/characters.js",
        "js/world/draw.js",
        "js/world/world.js",
        "js/lobby/screens.js",
        "js/lobby/forms.js",
        "js/lobby/lobby.js",
        "js/main.js",
    ]
    places = [page.index(f'<script src="{script}">') for script in scripts]
    assert places == sorted(places)


@pytest.mark.parametrize("name", ["characters.js", "draw.js", "world.js"])
def test_world_scripts_are_served(client, name):
    assert client.get(f"/js/world/{name}").status_code == 200


def test_map_file_is_served_as_json(client):
    # The browser draws the map from the same file the server reads for collision (S-79).
    response = client.get("/js/world/campus.json")
    assert response.status_code == 200
    campus = response.json()
    assert campus["width"] == 680 and campus["height"] == 668
    assert len(campus["rooms"]) == 5


def test_unknown_page_is_not_found(client):
    assert client.get("/does-not-exist").status_code == 404


def test_files_outside_the_client_folder_are_not_served(client):
    assert client.get("/../server/main.py").status_code == 404
    assert client.get("/%2e%2e/requirements.txt").status_code == 404


def test_api_documentation_pages_are_switched_off(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_every_page_carries_the_security_headers(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in headers["Content-Security-Policy"]


def test_hello_is_answered_with_welcome(client):
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "hello", "name": "Mara"})
        assert socket.receive_json() == {"type": "welcome", "name": "Mara", "protocol": 1}


def test_a_bad_message_gets_an_error_and_the_connection_stays_open(client):
    with client.websocket_connect("/ws") as socket:
        socket.send_text("not json")
        assert socket.receive_json()["code"] == "not_json"
        socket.send_json({"type": "hello", "name": "x"})
        assert socket.receive_json()["code"] == "bad_name"
        socket.send_json({"type": "hello", "name": "Mara"})
        assert socket.receive_json()["type"] == "welcome"


def test_a_binary_frame_gets_an_error(client):
    with client.websocket_connect("/ws") as socket:
        socket.send_bytes(b"\x00\x01")
        assert socket.receive_json()["code"] == "not_text"


def test_two_players_are_answered_separately(client):
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        first.send_json({"type": "hello", "name": "Mara"})
        second.send_json({"type": "hello", "name": "Tiago"})
        assert first.receive_json()["name"] == "Mara"
        assert second.receive_json()["name"] == "Tiago"
