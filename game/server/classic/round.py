"""Round state and action adapters for Classic mode."""

from rules import (
    apply_fail,
    assign_roles,
    assign_tasks,
    call_emergency,
    check_winner,
    end_reason,
    progress,
    report_sheet,
    role_reveal_for,
    sheet_id_for,
    tasks_after_leaving,
)
from server.classic import meeting as meeting_rules

EMERGENCY_DELAY_SECONDS = 45.0


class ClassicRound:
    def __init__(self, player_ids, station_ids, rng, started_at=0.0):
        self.roles = assign_roles(player_ids, rng)
        self.tasks = assign_tasks(self.roles, [str(station) for station in station_ids], rng)
        self.completed_tasks = {player_id: set() for player_id in player_ids}
        self.eliminated = set()
        self.positions = {}
        self.last_fail_at = {}
        self.f_sheets = {}
        self.sheets_issued = 0
        self.emergency_used = set()
        self.meeting_triggers = set()
        self.meeting = None
        self.phase = "round"
        self.timers_paused = False
        self.failure_count = 0
        self.meeting_count = 0
        self._has_news = True
        self.started_at = float(started_at)

    def state(self):
        return {
            "roles": self.roles,
            "tasks": self.tasks,
            "completed_tasks": self.completed_tasks,
            "eliminated": self.eliminated,
        }

    def rule_state(self):
        """Return the complete value passed between the pure Classic rules."""
        return {
            **self.state(),
            "positions": self.positions,
            "last_fail_at": self.last_fail_at,
            "f_sheets": self.f_sheets,
            "sheets_issued": self.sheets_issued,
            "emergency_used": self.emergency_used,
            "meeting_triggers": self.meeting_triggers,
            "phase": self.phase,
            "timers_paused": self.timers_paused,
        }

    def stations_needed(self, player_id, finished, in_use):
        return [int(station) for station in self.tasks.get(player_id, ())]

    def station_done(self, player_id, station):
        station_id = str(station)
        if (
            self.roles.get(player_id) != "HP"
            or station_id not in self.tasks.get(player_id, ())
            or station_id in self.completed_tasks[player_id]
        ):
            return
        self.completed_tasks[player_id].add(station_id)
        self._has_news = True

    def fail(self, fr_id, target_id, now, position):
        """Apply a validated fail action, count its F sheet and return the sheet id."""
        updated = apply_fail(self.rule_state(), fr_id, target_id, now, position)
        self._sync_rule_state(updated)
        self.failure_count += 1
        self._has_news = True
        return sheet_id_for(self.sheets_issued)

    def report(self, player_id, sheet_id, position, now):
        """Report a sheet and open a timed discussion for the living players."""
        updated = report_sheet(self.rule_state(), player_id, sheet_id, position)
        self._sync_rule_state(updated)
        living = [player for player in self.roles if player not in self.eliminated]
        ghosts = [player for player in self.roles if player in self.eliminated]
        self.meeting = meeting_rules.start_discussion(living, ghosts, now, updated)
        self.meeting["reason"] = "report"
        self.meeting_count += 1
        self._has_news = True
        return self.meeting

    def emergency(self, player_id, now):
        """Use a living player's once-per-round emergency call."""
        if now - self.started_at < EMERGENCY_DELAY_SECONDS:
            raise ValueError("The emergency button is not unlocked yet.")
        updated = call_emergency(self.rule_state(), player_id)
        self._sync_rule_state(updated)
        living = [player for player in self.roles if player not in self.eliminated]
        ghosts = [player for player in self.roles if player in self.eliminated]
        self.meeting = meeting_rules.start_discussion(living, ghosts, now, updated)
        self.meeting["reason"] = "emergency"
        self.meeting_count += 1
        self._has_news = True
        return self.meeting

    def emergency_seconds_left(self, now):
        return max(0.0, self.started_at + EMERGENCY_DELAY_SECONDS - now)

    def send_chat(self, player_id, text, now):
        if self.meeting is None:
            raise ValueError("There is no active meeting.")
        self.meeting = meeting_rules.send_chat(self.meeting, player_id, text, now)
        return self.meeting

    def cast_vote(self, voter_id, target_id):
        if self.meeting is None:
            raise ValueError("There is no active meeting.")
        self.meeting = meeting_rules.cast_vote(self.meeting, voter_id, target_id)
        return self.meeting

    def advance_meeting(self, now):
        """Advance this round's own copy of the meeting; only tests use it.

        The server applies a meeting's result through `apply_meeting_result`
        (M3-3.9) and must not use this method: it replaces `eliminated` with
        the meeting's list, which would undo failures made after the meeting
        started.
        """
        if self.meeting is None:
            raise ValueError("There is no active meeting.")
        self.meeting = meeting_rules.advance_meeting(self.meeting, now)
        if self.meeting["phase"] == "result":
            self.eliminated = set(self.meeting.get("eliminated", self.eliminated))
            self.phase = "result"
            self._has_news = True
        return self.meeting

    def apply_meeting_result(self, meeting):
        """A meeting reached its result: apply it to the round, and play goes on.

        The server calls this exactly once per meeting (M3-3.9). Only the
        player voted out, if any, becomes a ghost; the list of ghosts is
        never replaced by the meeting's older copy of it.
        """
        vote_result = meeting.get("vote_result")
        if vote_result is not None and vote_result.ejected_id is not None:
            self.eliminated.add(vote_result.ejected_id)
        self.phase = "round"
        self.timers_paused = False
        self.meeting = meeting
        self._has_news = True

    def remove_player(self, player_id):
        """The player left the round (M3-3.11, DESIGN.md section 5).

        They count as failed, so the win rules see one living player fewer,
        and their open tasks disappear from the progress bar; the tasks they
        finished keep counting. Their role stays known for the end screen.
        """
        if player_id not in self.roles:
            return
        self.eliminated.add(player_id)
        self.tasks = tasks_after_leaving(self.tasks, self.completed_tasks, player_id)
        self._has_news = True

    def progress(self):
        return progress(self.state())

    def winner(self):
        return check_winner(self.state())

    def result_reason(self):
        return end_reason(self.state())

    def role_reveal(self, player_id):
        return role_reveal_for(self.state(), player_id)

    def take_news(self):
        had_news = self._has_news
        self._has_news = False
        return had_news

    def result(self, winner=None, reason=None):
        winner = self.winner() if winner is None else winner
        reason = self.result_reason() if reason is None else reason
        return {
            "type": "classic_result",
            "winner": winner,
            "reason": reason,
            "roles": dict(self.roles),
            "stats": {
                "failures": self.failure_count,
                "completed_tasks": sum(len(tasks) for tasks in self.completed_tasks.values()),
                "meetings": self.meeting_count,
            },
        }

    def _sync_rule_state(self, state):
        self.eliminated = set(state["eliminated"])
        self.last_fail_at = dict(state.get("last_fail_at", self.last_fail_at))
        self.f_sheets = dict(state.get("f_sheets", self.f_sheets))
        self.sheets_issued = int(state.get("sheets_issued", self.sheets_issued))
        self.emergency_used = set(state.get("emergency_used", self.emergency_used))
        self.meeting_triggers = set(state.get("meeting_triggers", self.meeting_triggers))
        self.phase = state.get("phase", self.phase)
        self.timers_paused = state.get("timers_paused", self.timers_paused)
