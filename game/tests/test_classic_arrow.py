"""M3-4.22: in Classic the arrow points at the nearest own open task.

Runs tests/classic_arrow_in_node.js, which loads the real
client/js/minigames/task_navigation.js in Node with a fake canvas: the plain
helper nearestStation (nearest, tie, empty list, unknown id, no position)
and draw with a list (arrow or none, its angle and fade, the card without a
task, Duel's one target unchanged). Skipped without Node.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("classic_arrow_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node is needed to run the page's JavaScript")
def test_the_classic_arrow_checks_pass_in_node():
    finished = subprocess.run([NODE, str(HARNESS)], capture_output=True, text=True, timeout=60)
    output = finished.stdout + finished.stderr
    assert finished.returncode == 0, output
    assert "passed" in finished.stdout, output
