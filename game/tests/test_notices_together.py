"""S-224: two notices that come together are shown in one line (the host left, and the round was stopped).

Runs tests/notices_together_in_node.js, which drives the real client file
main.js in Node.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("notices_together_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node.js is needed")
def test_notices_that_come_together_are_shown_in_one_line_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "all 6 checks passed" in finished.stdout
