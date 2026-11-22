"""The own Classic task card in the side panel (S-154), checked in Node.

Runs tests/classic_task_card_in_node.js: lobby.js's lines of the card for a
High Performer (remaining stations, all done), the Free Rider and a station
without a name, and main.js's handling of `classic_role`, `station_done`,
the lobby and leaving. Skipped when Node is missing.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("classic_task_card_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node is needed")
def test_the_classic_task_card_passes_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stderr + finished.stdout
    assert "Classic task card checks passed" in finished.stdout
