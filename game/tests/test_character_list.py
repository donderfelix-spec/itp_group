"""One list of characters per side, held together by these tests (M1-1.8).

The server checks `choose_character` against `protocol.CHARACTERS`. The
browser's only list is `characters` in client/js/world/characters.js
(`Game.world.characters`), which also has the names, lines and colours. The
lobby panel builds its buttons from that list and has none of its own.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from server import protocol

CLIENT = Path(__file__).resolve().parent.parent / "client" / "js"
CHARACTERS_JS = CLIENT / "world" / "characters.js"
LOBBY_JS = CLIENT / "lobby" / "lobby.js"
LOBBY_IN_NODE = Path(__file__).resolve().parent / "lobby_characters_in_node.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")


# ---- Reading characters.js ----


def list_block(source):
    """The text between `var characters = [` and the `];` that closes it."""
    found = re.search(r"var characters = \[(.*?)\];", source, re.DOTALL)
    assert found, "characters.js has no `var characters = [ ... ];` list"
    return found.group(1)


def quoted_field(entry, field):
    """The value of `field: "..."` in one entry, or None if it is missing."""
    found = re.search(field + r"""\s*:\s*(["'])(.*?)\1""", entry)
    return found.group(2) if found else None


def browser_characters(source):
    """(id, name) of every `{ ... }` entry in the list, in the file's order."""
    entries = re.findall(r"\{[^{}]*\}", list_block(source))
    return [(quoted_field(entry, "id"), quoted_field(entry, "name")) for entry in entries]


def test_the_browser_list_has_the_server_ids_in_the_same_order():
    ids = [character_id for character_id, _ in browser_characters(CHARACTERS_JS.read_text())]
    assert ids == list(protocol.CHARACTERS)


def test_every_character_in_the_browser_list_has_a_name():
    for character_id, name in browser_characters(CHARACTERS_JS.read_text()):
        assert name, f"{character_id} has no name in characters.js"


# The reader itself, so a broken reader cannot hide a broken list.


def test_reader_sees_a_swapped_order():
    source = """
      var characters = [
        { id: "finance_bro", name: "The Finance Bro" },
        { id: "consultant", name: "The Consultant" }
      ];
    """
    assert browser_characters(source) == [
        ("finance_bro", "The Finance Bro"),
        ("consultant", "The Consultant"),
    ]


def test_reader_sees_a_missing_or_empty_name():
    source = """
      var characters = [
        { id: "consultant", colour: "#26406E" },
        { id: "surfer", name: "" }
      ];
    """
    assert browser_characters(source) == [("consultant", None), ("surfer", "")]


def test_reader_fails_when_the_list_is_gone():
    with pytest.raises(AssertionError):
        browser_characters("var people = [];")


# ---- The lobby has no list of its own ----


def test_lobby_names_no_character_id():
    lobby = LOBBY_JS.read_text()
    for character_id in protocol.CHARACTERS:
        for quote in ("'", '"', "`"):
            assert quote + character_id + quote not in lobby, f"lobby.js names {character_id}"


def test_lobby_names_no_character_name():
    lobby = LOBBY_JS.read_text()
    for _, name in browser_characters(CHARACTERS_JS.read_text()):
        assert name not in lobby, f"lobby.js names {name}"


def lobby_buttons(mode):
    """Run lobby.js in Node (see lobby_characters_in_node.js) and return its buttons."""
    finished = subprocess.run(
        [NODE, str(LOBBY_IN_NODE), mode], capture_output=True, text=True, timeout=30, check=False
    )
    assert finished.returncode == 0, finished.stderr
    return json.loads(finished.stdout)


@needs_node
def test_lobby_builds_one_button_per_character_from_the_world_list():
    buttons = lobby_buttons("with-characters")
    expected = browser_characters(CHARACTERS_JS.read_text())
    assert [button["name"] for button in buttons] == [name for _, name in expected]
    assert [button["asked"] for button in buttons] == [
        {"type": "choose_character", "character": character_id} for character_id in protocol.CHARACTERS
    ]


@needs_node
def test_lobby_without_the_world_list_shows_no_characters_and_does_not_crash():
    assert lobby_buttons("without-characters") == []
