"""The line in the card at the top left in Classic (S-197), checked in Node.

Runs tests/classic_card_note_in_node.js: "All your tasks are done." for a
High Performer who finished all four, "Fake tasks: stand at a station to
look busy." for the Free Rider, each only on the page of the player
concerned, a task going first, and nothing outside a Classic round.
Skipped when Node is missing.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("classic_card_note_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node is needed")
def test_the_classic_card_line_passes_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stderr + finished.stdout
    assert "Classic card line checks passed" in finished.stdout
