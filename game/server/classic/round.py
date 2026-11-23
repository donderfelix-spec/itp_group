"""Round state and action adapters for Classic mode."""

import math

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
from server.classic import hiding as hiding_rules
from server.classic import meeting as meeting_rules
from server.classic import sheets as sheet_rules

EMERGENCY_DELAY_SECONDS = 45.0


def active_task(roles, tasks, completed_tasks, player_id):
    """A High Performer's active task: the first unfinished one of his list (S-197).

    Returns a list with that station, or [] for a Free Rider, a stranger or
    a High Performer who has finished all four. Ghosts keep their task (S-04).
    """
    if roles.get(player_id) != "HP":
        return []
    completed = completed_tasks.get(player_id, set())
    return [int(station) for station in tasks.get(player_id, ()) if station not in completed][:1]


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
        # The character drawn on each sheet, and which players were told
        # its place (S-202): player -> set of sheet ids. Only the server knows it.
        self.sheet_characters = {}
        self.sheets_told = {}
        self.emergency_used = set()
        self.meeting_triggers = set()
        self.meeting = None
        self.phase = "round"
        self.timers_paused = False
        self.failure_count = 0
        self.meeting_count = 0
        self._has_news = True
        self.started_at = float(started_at)
        # The Free Riders who pressed E at a hiding object (M3-1.6, S-191):
        # name -> the spot they hide in. Only the server knows it.
        self.hidden = {}
        # Set when a meeting's result is applied: the server puts everybody
        # back on the Main Deck before anybody walks again (DESIGN.md 5.8).
        self._back_to_the_deck = False
        # Set at the same moment: the Free Riders are to be told their new cooldown.
        self._cooldown_news = False

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
        """The one station this player may open now (S-197), as a list.

        The four tasks were drawn in a random order at the start, so this
        read is stable and a rolled-back completion gives the same task back.
        """
        return active_task(self.roles, self.tasks, self.completed_tasks, player_id)

    def station_done(self, player_id, station):
        station_id = str(station)
        # Compared as text, so 3 and "3" are the same station, as before S-197.
        if station_id not in [str(active) for active in self.stations_needed(player_id, set(), ())]:
            return
        self.completed_tasks[player_id].add(station_id)
        self._has_news = True

    def fail(self, fr_id, target_id, now, position, character=None):
        """Apply a validated fail action, count its F sheet and return the sheet id."""
        updated = apply_fail(self.rule_state(), fr_id, target_id, now, position)
        self._sync_rule_state(updated)
        self.failure_count += 1
        self._has_news = True
        sheet_id = sheet_id_for(self.sheets_issued)
        self.sheet_characters[sheet_id] = character
        return sheet_id

    def sheet_is_reported(self, sheet_id):
        return f"report:{sheet_id}" in self.meeting_triggers

    def may_know_sheet(self, viewer, viewer_position, sheet_id, campus):
        """Whether this player may be told where the sheet lies (S-202)."""
        return sheet_id in sheet_rules.sheets_in_view(
            {sheet_id: self.f_sheets[sheet_id]}, viewer_position, viewer in self.eliminated, campus
        )

    def mark_sheet_told(self, viewer, sheet_id):
        self.sheets_told.setdefault(viewer, set()).add(sheet_id)

    def sheet_news(self, viewer, viewer_position, campus):
        """The sheets that came into this player's view since he was last told, now marked told.

        Returns (sheet_id, (x, y), character, reported) for each.
        """
        told = self.sheets_told.setdefault(viewer, set())
        new = sheet_rules.sheets_to_tell(
            self.f_sheets, viewer_position, viewer in self.eliminated, told, campus
        )
        told.update(new)
        return [
            (sheet_id, self.f_sheets[sheet_id], self.sheet_characters.get(sheet_id),
             self.sheet_is_reported(sheet_id))
            for sheet_id in new
        ]

    def hide(self, player_id, position, campus):
        """A Free Rider presses E at a hiding object. Returns the spot he hides in.

        Raises `HideRefused` with a rejection code when he may not. Pressing E
        again while hidden is answered by `leave_hiding`, not here; hiding
        twice keeps him in his first spot.
        """
        if player_id in self.hidden:
            return self.hidden[player_id]
        refusal = hiding_rules.hide_refusal(
            self.roles, self.eliminated, self.phase, player_id, position, campus
        )
        if refusal is not None:
            raise HideRefused(refusal)
        spot = hiding_rules.spot_in_reach(campus, position)
        self.hidden[player_id] = spot
        return spot

    def leave_hiding(self, player_id):
        """He steps out (E again, or a step). Returns whether he was hidden."""
        return self.hidden.pop(player_id, None) is not None

    def end_all_hiding(self):
        """A meeting starts: everybody steps out. Returns who was hidden."""
        ended = sorted(self.hidden)
        self.hidden = {}
        return ended

    def is_hidden(self, player_id):
        return player_id in self.hidden

    def report(self, player_id, sheet_id, position, now):
        """Report a sheet and open a timed discussion for the living players."""
        updated = report_sheet(self.rule_state(), player_id, sheet_id, position)
        self._sync_rule_state(updated)
        self.end_all_hiding()
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
        self.end_all_hiding()
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
        # DESIGN.md 5.8: after a meeting the Free Riders' cooldown starts
        # again. It counts from the end of the meeting, which a finished
        # meeting keeps as its "deadline", so no clock is needed here.
        ended_at = meeting.get("deadline")
        if isinstance(ended_at, (int, float)) and not isinstance(ended_at, bool) and math.isfinite(ended_at):
            for player_id, role in self.roles.items():
                if role == "FR" and player_id not in self.eliminated:
                    self.last_fail_at[player_id] = float(ended_at)
        self._back_to_the_deck = True
        self._cooldown_news = True
        self.phase = "round"
        self.timers_paused = False
        self.meeting = meeting
        self._has_news = True

    def take_back_to_the_deck(self):
        """True once after each applied meeting: now everybody goes back to the Main Deck (DESIGN.md 5.8)."""
        due = self._back_to_the_deck
        self._back_to_the_deck = False
        return due

    def take_cooldown_news(self):
        """True once after each applied meeting: the Free Riders' cooldown started again."""
        due = self._cooldown_news
        self._cooldown_news = False
        return due

    def remove_player(self, player_id):
        """The player left the round (M3-3.11, DESIGN.md section 5).

        They count as failed, so the win rules see one living player fewer,
        and their open tasks disappear from the progress bar; the tasks they
        finished keep counting. Their role stays known for the end screen.
        """
        if player_id not in self.roles:
            return
        self.eliminated.add(player_id)
        self.hidden.pop(player_id, None)
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


class HideRefused(Exception):
    """A Free Rider may not hide now. `code` is a key of `protocol.REJECTIONS`."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code
