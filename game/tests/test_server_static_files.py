"""The files of the client: the favicon, the cache header and the security headers."""

import pytest
from fastapi.testclient import TestClient

from server.main import SECURITY_HEADERS, app

CLIENT_FILES = ["/", "/js/main.js", "/css/style.css", "/js/world/campus.json", "/favicon.ico"]

# Every .ico file starts with these four bytes: reserved 0, then type 1 (icon).
ICO_SIGNATURE = b"\x00\x00\x01\x00"


@pytest.fixture
def client():
    return TestClient(app)


def assert_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_favicon_is_served_as_an_image(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert len(response.content) > len(ICO_SIGNATURE)
    assert response.content.startswith(ICO_SIGNATURE)


def test_start_page_links_to_the_favicon(client):
    response = client.get("/")
    assert '<link rel="icon" href="favicon.ico">' in response.text


@pytest.mark.parametrize("path", CLIENT_FILES)
def test_client_file_is_sent_with_no_cache(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("path", CLIENT_FILES)
def test_client_file_keeps_the_security_headers(client, path):
    assert_security_headers(client.get(path))


def test_unchanged_script_is_answered_with_not_modified(client):
    first = client.get("/js/main.js")
    second = client.get("/js/main.js", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["cache-control"] == "no-cache"
    assert_security_headers(second)


def test_wrong_etag_gets_the_whole_script_again(client):
    response = client.get("/js/main.js", headers={"If-None-Match": '"not-the-etag"'})
    assert response.status_code == 200
    assert response.content != b""
    assert response.headers["cache-control"] == "no-cache"


def test_missing_file_is_a_404_with_the_security_headers(client):
    response = client.get("/js/no-such-file.js")
    assert response.status_code == 404
    assert_security_headers(response)


def test_health_needs_no_cache_header(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "cache-control" not in response.headers
    assert_security_headers(response)
