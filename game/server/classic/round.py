"""Round state and task adapters for Classic mode."""

from rules import assign_roles, assign_tasks, progress, role_reveal_for


class ClassicRound:
    def __init__(self, player_ids, station_ids, rng):
        self.roles = assign_roles(player_ids, rng)
        self.tasks = assign_tasks(self.roles, [str(station) for station in station_ids], rng)
        self.completed_tasks = {player_id: set() for player_id in player_ids}
        self.eliminated = set()
        self.failure_count = 0
        self.meeting_count = 0
        self._has_news = True

    def state(self):
        return {
            "roles": self.roles,
            "tasks": self.tasks,
            "completed_tasks": self.completed_tasks,
            "eliminated": self.eliminated,
        }

    def stations_needed(self, player_id, finished, in_use):
        return [int(station) for station in self.tasks.get(player_id, ())]

    def station_done(self, player_id, station):
        if self.roles.get(player_id) != "HP":
            return
        self.completed_tasks[player_id].add(str(station))
        self._has_news = True

    def progress(self):
        return progress(self.state())

    def role_reveal(self, player_id):
        return role_reveal_for(self.state(), player_id)

    def take_news(self):
        had_news = self._has_news
        self._has_news = False
        return had_news

    def result(self, winner, reason):
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
