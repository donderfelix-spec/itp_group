"""Exercise the overview controls and markers with a recording canvas in Node."""

import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("overview_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")
def test_the_overview_shows_own_open_tasks_and_closes_for_the_game():
    result = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
