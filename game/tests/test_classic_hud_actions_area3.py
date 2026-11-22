"""Client-facing range and action wiring for the Classic HUD."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_report_button_is_available_only_to_a_living_player_within_two_fields():
    helper = ROOT / "client/js/classic/hud-actions.js"
    script = f"""
      const actions = require({json.dumps(str(helper))});
      process.stdout.write(JSON.stringify([
        actions.reportVisible(true, 2),
        actions.reportVisible(true, 2.01),
        actions.reportVisible(false, 0)
      ]));
    """
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [True, False, False]


def test_emergency_unlock_uses_server_timestamp_and_monotonic_elapsed_time():
    helper = ROOT / "client/js/classic/hud-actions.js"
    script = f"""
      const actions = require({json.dumps(str(helper))});
      const status = {{ emergency_ready_at: 1045, server_time: 1000 }};
      process.stdout.write(JSON.stringify([
        actions.emergencyUnlocked(status, 5000, 49999),
        actions.emergencyUnlocked(status, 5000, 50000)
      ]));
    """
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [False, True]


def test_end_popup_and_lobby_button_share_the_same_leave_handler():
    lobby = (ROOT / "client/js/lobby/lobby.js").read_text()
    classic_round = (ROOT / "client/js/classic/round.js").read_text()
    assert "function leaveLobby()" in lobby
    assert "addEventListener('click', leaveLobby)" in lobby
    assert 'addEventListener("click", hideResult)' in classic_round and "leaveLobby" not in classic_round


def test_client_displays_report_and_meeting_trigger_and_dead_players():
    world = (ROOT / "client/js/world/world.js").read_text()
    meeting = (ROOT / "client/js/classic/meeting.js").read_text()
    assert 'var REPORT_BUTTON_TEXT = "R Report"' in world  # S-195: was "Report"
    assert 'reportButton.textContent = REPORT_BUTTON_TEXT' in world
    assert "ownIsGhost" in world
    assert 'state.trigger_player_id' in meeting
    assert 'state.reason' in meeting
    assert '"Dead players"' in meeting
