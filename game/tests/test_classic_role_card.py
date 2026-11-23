"""The role card leaves out "Other Free Riders:" when there is only one Free Rider (DESIGN.md, screen 5).

Runs tests/classic_role_card_in_node.js, which drives the real
client/js/classic/round.js in Node.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("classic_role_card_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node.js is needed")
def test_the_role_card_names_the_other_free_rider_only_when_there_is_one_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "all 6 checks passed" in finished.stdout
