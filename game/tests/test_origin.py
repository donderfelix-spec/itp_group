"""The rule "may a WebSocket from this origin connect?" (M3-2.7, S-207, `server/net/origin.py`)."""

import pytest

from server.net.origin import (
    PUBLIC_ORIGINS,
    check_is_on,
    is_origin_allowed,
    origin_host_for_log,
    parse_allowed_origins,
    parse_origin,
)

SITE = "itp-group.onrender.com"


def allowed(origin, host=SITE, forwarded=(), listed=()):
    return is_origin_allowed(origin, host, list(forwarded), tuple(listed))


# --- accepted --------------------------------------------------------------


@pytest.mark.parametrize(
    "origin, host",
    [
        ("https://itp-group.onrender.com", "itp-group.onrender.com"),
        ("http://localhost:8000", "localhost:8000"),
        ("http://127.0.0.1:8000", "127.0.0.1:8000"),
        ("http://[::1]:8000", "[::1]:8000"),
        ("http://example.org", "example.org"),
    ],
)
def test_the_same_host_is_accepted(origin, host):
    assert allowed(origin, host)


@pytest.mark.parametrize(
    "origin, host",
    [
        # A default port written out on either side is the same site.
        ("https://itp-group.onrender.com:443", "itp-group.onrender.com"),
        ("https://itp-group.onrender.com", "itp-group.onrender.com:443"),
        ("http://example.org:80", "example.org"),
        ("http://example.org", "example.org:80"),
        ("https://example.org:8443", "example.org:8443"),
    ],
)
def test_default_and_explicit_ports_of_the_same_site_are_accepted(origin, host):
    assert allowed(origin, host)


def test_the_scheme_is_not_compared_behind_a_proxy():
    # Render ends TLS: the page is https, the proxy speaks http to the server,
    # the Host header stays the public host without a port.
    assert allowed("https://itp-group.onrender.com", "itp-group.onrender.com")


def test_a_forwarded_host_is_accepted_when_the_proxy_changed_host():
    assert allowed("https://itp-group.onrender.com", "10.0.0.5:10000", forwarded=["itp-group.onrender.com"])


def test_every_value_of_a_forwarded_host_list_counts():
    assert allowed("https://itp-group.onrender.com", "internal:10000", forwarded=["edge.example, itp-group.onrender.com"])
    assert allowed("https://itp-group.onrender.com", "internal:10000", forwarded=["edge.example", SITE])


def test_a_listed_origin_is_accepted_whatever_the_host():
    assert allowed("https://game.example.org", "internal:10000", listed=["https://game.example.org"])


def test_a_listed_bare_host_is_accepted_for_both_schemes():
    assert allowed("https://game.example.org", "internal", listed=["game.example.org"])
    assert allowed("http://game.example.org", "internal", listed=["game.example.org"])
    assert allowed("http://game.example.org:8080", "internal", listed=["game.example.org:8080"])


def test_the_public_address_is_always_in_the_built_in_list():
    assert "https://itp-group.onrender.com" in PUBLIC_ORIGINS
    assert allowed("https://itp-group.onrender.com", "10.0.0.5:10000", listed=PUBLIC_ORIGINS)


def test_a_missing_origin_is_accepted():
    # Browsers always send Origin; a program (the tests, curl) does not, and a
    # page cannot remove the header to get past the check.
    assert allowed(None)
    assert allowed(None, host=None)


@pytest.mark.parametrize(
    "origin, host",
    [
        ("HTTPS://ITP-GROUP.ONRENDER.COM", "itp-group.onrender.com"),
        ("https://itp-group.onrender.com", "ITP-Group.OnRender.com"),
        ("https://itp-group.onrender.com.", "itp-group.onrender.com."),
        ("https://itp-group.onrender.com.", "itp-group.onrender.com"),
        ("https://itp-group.onrender.com", "itp-group.onrender.com."),
    ],
)
def test_case_and_a_final_dot_do_not_matter(origin, host):
    assert allowed(origin, host)


# --- refused ---------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "https://itp-group.onrender.com.evil.example",
        "https://evil-itp-group.onrender.com",
        "https://evilitp-group.onrender.com",
        "https://x.itp-group.onrender.com",
        "https://onrender.com",
        "https://itp-group.onrender.co",
    ],
)
def test_another_site_is_refused(origin):
    assert not allowed(origin)


def test_a_prefix_or_suffix_trick_is_refused_by_the_allowed_list_too():
    listed = ["https://itp-group.onrender.com", "game.example.org"]
    assert not allowed("https://itp-group.onrender.com.evil.example", "evil", listed=listed)
    assert not allowed("https://evil-itp-group.onrender.com", "evil", listed=listed)
    assert not allowed("https://game.example.org.evil.example", "evil", listed=listed)
    assert not allowed("https://evilgame.example.org", "evil", listed=listed)


@pytest.mark.parametrize(
    "origin, host",
    [
        ("http://localhost:3000", "localhost:8000"),
        ("http://localhost", "localhost:8000"),
        ("http://localhost:8000", "localhost"),
        ("https://example.org:8443", "example.org"),
        ("http://example.org:443", "example.org"),
        ("http://localhost:8000", "127.0.0.1:8000"),
    ],
)
def test_another_port_or_another_name_for_the_machine_is_refused(origin, host):
    assert not allowed(origin, host)


def test_a_listed_origin_counts_only_with_its_scheme_and_port():
    listed = ["https://game.example.org"]
    assert not allowed("http://game.example.org", "internal", listed=listed)
    assert not allowed("https://game.example.org:8443", "internal", listed=listed)


def test_null_is_refused():
    # Sandboxed frames and pages opened from a file send "null".
    assert not allowed("null")
    assert not allowed("null", host="null")


@pytest.mark.parametrize(
    "origin",
    [
        "",
        " ",
        "itp-group.onrender.com",
        "https://",
        "https://:443",
        "https://itp-group.onrender.com:",
        "https://itp-group.onrender.com:abc",
        "https://itp-group.onrender.com:99999",
        "https://itp-group.onrender.com/",
        "https://itp-group.onrender.com/path",
        "https://itp-group.onrender.com?x",
        "https://itp-group.onrender.com#x",
        "https://evil.example@itp-group.onrender.com",
        "https://itp-group.onrender.com\\@evil.example",
        "https://itp-group .onrender.com",
        "https://itp-group.onrender.com\t",
        "https://itp-grüp.onrender.com",
        "https://itp-group..onrender.com",
        "https://[itp-group.onrender.com]",
        "ftp://itp-group.onrender.com",
        "ws://itp-group.onrender.com",
        "wss://itp-group.onrender.com",
        "chrome-extension://abcdef",
        "file://",
        "javascript:alert(1)",
        "https://itp-group.onrender.com,https://evil.example",
    ],
)
def test_a_malformed_origin_is_refused(origin):
    assert not allowed(origin)


@pytest.mark.parametrize("host", [None, "", "null", "a b", "evil.example/itp-group.onrender.com", "x:abc"])
def test_an_unreadable_host_matches_nothing(host):
    assert not allowed("https://itp-group.onrender.com", host)


def test_a_wrong_forwarded_host_does_not_help():
    assert not allowed("https://evil.example", forwarded=["itp-group.onrender.com"])
    assert not allowed("https://itp-group.onrender.com", "internal", forwarded=["", " , ", "evil.example"])


def test_an_unreadable_allowed_entry_is_ignored():
    assert not allowed("https://evil.example", "internal", listed=["https://", "evil.example/", "*"])


# --- settings --------------------------------------------------------------


@pytest.mark.parametrize("setting", [None, "", "on", "ON", "yes", "true", "1", "anything"])
def test_the_check_is_on_unless_switched_off(setting):
    assert check_is_on(setting)


@pytest.mark.parametrize("setting", ["off", "OFF", " Off ", "false", "0", "no"])
def test_the_kill_switch_turns_the_check_off(setting):
    assert not check_is_on(setting)


def test_allowed_origins_are_read_from_a_comma_separated_setting():
    assert parse_allowed_origins(None) == ()
    assert parse_allowed_origins("") == ()
    assert parse_allowed_origins(" https://a.example/ , ,b.example:8000,") == ("https://a.example", "b.example:8000")


def test_a_listed_origin_with_a_final_slash_still_works():
    listed = parse_allowed_origins("https://game.example.org/")
    assert allowed("https://game.example.org", "internal", listed=listed)


# --- details ---------------------------------------------------------------


def test_an_origin_is_parsed_with_its_port_filled_in():
    assert parse_origin("https://itp-group.onrender.com") == ("https", SITE, 443)
    assert parse_origin("http://localhost:8000") == ("http", "localhost", 8000)
    assert parse_origin("http://[::1]:8000") == ("http", "::1", 8000)


def test_the_log_names_only_the_host():
    assert origin_host_for_log("https://evil.example:8443") == "evil.example"
    assert origin_host_for_log("null") == "null"
    assert origin_host_for_log("https://evil.example/path\nFAKE LOG LINE") == "an unreadable origin"
    assert len(origin_host_for_log("https://" + "a" * 500 + ".example")) == 100
