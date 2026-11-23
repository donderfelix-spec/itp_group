"""M3-3.21: a double click or a double R on "R Report" sends one report and shows no error.

Runs tests/classic_report_once_in_node.js, which drives the real client
file main.js in Node: the second report before the answer is swallowed;
the meeting, a refusal or the end of the round end the wait.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).with_name("classic_report_once_in_node.js")


@pytest.mark.skipif(NODE is None, reason="Node.js is needed")
def test_a_report_is_sent_once_until_its_answer_in_node():
    finished = subprocess.run([NODE, str(SCRIPT)], capture_output=True, text=True, timeout=60, check=False)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "all 8 checks passed" in finished.stdout
