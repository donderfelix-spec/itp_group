"""S-224: two notices at once are shown one after the other (the host left, and the round was stopped).

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
def test_notices_at_once_are_shown_one_after_the_other_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "all 9 checks passed" in finished.stdout
