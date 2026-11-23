"""May a WebSocket from this origin connect? (M3-2.5, S-207)

A browser sends the header `Origin` with every WebSocket handshake: the site
of the page that opens the connection. Without a check, a page on any other
site could open a connection to our server in a visitor's browser and play in
their name (cross-site WebSocket hijacking). So the server accepts a
connection only when the page comes from our own site.

"Our own site" is the host the browser sent the request to. Our page builds
the address from `location.host` (`client/js/net.js`), so for our own page the
Origin's host and port always equal the `Host` header. Behind a proxy such as
Render's, the proxy may pass the public host on in `X-Forwarded-Host` instead,
so a match with any of these headers counts. That is safe: a page on another
site cannot set `Host` or `X-Forwarded-Host` in a visitor's browser.

Hosts are compared, not schemes: the browser's Origin says `https`, while the
proxy speaks `http` to our server. The port counts, because another port on
the same host is another site (a page on localhost:3000 must not reach the
game on localhost:8000).

Four choices keep the real game playable if a proxy behaves unexpectedly:

- The public address of the deployed game is always allowed (`PUBLIC_ORIGINS`).
- More origins can be allowed in the environment variable `ALLOWED_ORIGINS`.
- The check can be switched off with `ORIGIN_CHECK=off`.
- A missing Origin is accepted: browsers always send one, so a connection
  without it comes from a program (the tests, curl), and a page cannot remove
  the header to get around the check.

These are plain functions without network or environment: `server/main.py`
reads the headers and the environment variables and passes them in.
"""

import re
from urllib.parse import urlsplit

# The address of the deployed game (S-31). Always allowed, so the game stays
# playable even if Render's proxy passed on a host we did not expect.
PUBLIC_ORIGINS = ("https://itp-group.onrender.com",)

DEFAULT_PORTS = {"http": 80, "https": 443}

# The values of ORIGIN_CHECK that switch the check off. Anything else keeps it on.
OFF_VALUES = {"off", "false", "0", "no"}

# A host name: labels of letters, digits, "-" and "_", with at most one dot at the end.
NAME = re.compile(r"[a-z0-9_-]+(\.[a-z0-9_-]+)*\.?")
# An IPv6 address, written in square brackets in a URL.
IPV6 = re.compile(r"[0-9a-f:.]+")

# Characters that never belong to an Origin after "scheme://": a path, a
# query, a fragment, a user name or a backslash.
NOT_IN_ORIGIN = set("/?#@\\")


def check_is_on(setting: str | None) -> bool:
    """The value of ORIGIN_CHECK: on unless it is set to "off" (or false, 0, no)."""
    if setting is None:
        return True
    return setting.strip().lower() not in OFF_VALUES


def parse_allowed_origins(setting: str | None) -> tuple:
    """The value of ALLOWED_ORIGINS as a list: comma separated, spaces and a final "/" ignored."""
    if not setting:
        return ()
    entries = (entry.strip().rstrip("/") for entry in setting.split(","))
    return tuple(entry for entry in entries if entry)


def is_origin_allowed(origin, host, forwarded_hosts, allowed_origins) -> bool:
    """True if a WebSocket from `origin` may connect.

    `origin` and `host` are the values of the headers `Origin` and `Host`, or
    None when missing. `forwarded_hosts` are the values of `X-Forwarded-Host`
    (each may list several hosts, comma separated). `allowed_origins` are
    further origins that are always allowed, such as "https://example.org", or
    a bare host such as "example.org" for both http and https.
    """
    if origin is None:
        return True
    page = parse_origin(origin)
    if page is None:
        return False
    for candidate in request_hosts(host, forwarded_hosts):
        if matches_host(page, candidate):
            return True
    return any(matches_allowed(page, entry) for entry in allowed_origins)


def request_hosts(host, forwarded_hosts) -> list:
    """Every host the request may have been sent to, parsed; unreadable ones left out."""
    values = [] if host is None else [host]
    for header in forwarded_hosts:
        values.extend(header.split(","))
    parsed = (parse_host(value.strip()) for value in values)
    return [found for found in parsed if found is not None]


def matches_allowed(page, entry: str) -> bool:
    """True if the parsed origin `page` is the allowed origin (or bare host) `entry`."""
    if "://" in entry:
        return parse_origin(entry) == page
    allowed_host = parse_host(entry)
    return allowed_host is not None and matches_host(page, allowed_host)


def matches_host(page, request_host) -> bool:
    """True if the parsed origin `page` is on the parsed host `request_host`.

    A host without a port matches only an origin on the default port of its
    own scheme (80 for http, 443 for https): the browser leaves the default
    port out of `Host`, and a proxy may change the scheme on the way.
    """
    scheme, name, port = page
    host_name, host_port = request_host
    if name != host_name:
        return False
    if host_port is None:
        return port == DEFAULT_PORTS[scheme]
    return port == host_port


def parse_origin(text: str):
    """`(scheme, host, port)` of an Origin such as "https://example.org:8443", or None if it is not one.

    The port is always filled in (443 for https without a port). "null", other
    schemes and anything with a path, query, user name or space give None.
    """
    if not is_plain_text(text) or "://" not in text:
        return None
    scheme, rest = text.split("://", 1)
    scheme = scheme.lower()
    if scheme not in DEFAULT_PORTS or NOT_IN_ORIGIN & set(rest):
        return None
    host = parse_host(rest)
    if host is None:
        return None
    name, port = host
    return (scheme, name, DEFAULT_PORTS[scheme] if port is None else port)


def parse_host(text: str):
    """`(host, port)` of a Host header such as "example.org:8000", or None if it is not one.

    The host is in lower case without a final dot, the port is None when not
    given. An IPv6 address is returned without its square brackets.
    """
    if not is_plain_text(text) or NOT_IN_ORIGIN & set(text) or text.endswith(":"):
        return None
    try:
        parts = urlsplit("//" + text)
        name, port = parts.hostname, parts.port
    except ValueError:
        return None
    if not name:
        return None
    pattern = IPV6 if text.startswith("[") else NAME
    if not pattern.fullmatch(name):
        return None
    return (name.rstrip("."), port)


def is_plain_text(text) -> bool:
    """True for a non-empty string of visible ASCII characters without spaces."""
    return isinstance(text, str) and text != "" and all("!" <= character <= "~" for character in text)


def origin_host_for_log(origin: str) -> str:
    """What the log says about a refused origin: only its host, never the whole header."""
    page = parse_origin(origin)
    if page is not None:
        return page[1][:100]
    return "null" if origin == "null" else "an unreadable origin"
