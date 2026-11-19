"""Where the players of one lobby stand and which way they are walking.

These are plain rules: no network and no clock in here. The server measures
the time since the previous tick and passes it in, tests pass their own.

Every lobby has one `Walkers` object. The server calls `advance` about 15
times per second (S-72) and afterwards sends the positions to every member
named by `names_to_tell`.
"""

from server.world import movement


class Walker:
    """One player on the campus."""

    def __init__(self):
        # None until the next tick puts the player on the spawn. The lobby
        # rules that add a player do not know the map, the tick does.
        self.position = None
        # The direction the player wants to walk: -1, 0 or 1 on each axis.
        self.dx = 0
        self.dy = 0
        # Whether this player still has to be sent the newest positions.
        self.needs_news = False


class Walkers:
    def __init__(self):
        # name -> Walker, in the order the players joined.
        self._walkers = {}

    def add(self, name: str):
        """A newcomer stands still on the spawn. Everybody must be told."""
        self._walkers[name] = Walker()
        self._everybody_needs_news()

    def remove(self, name: str):
        """The player's position is gone. Those who stay must be told."""
        del self._walkers[name]
        self._everybody_needs_news()

    def back_to_spawn(self):
        """Put every player back on the spawn, for the start of a round.

        The next `advance` places them, exactly like newcomers. The direction
        a player is holding stays: the browser sends a direction only when it
        changes (S-74), so a player holding a key would otherwise stand still
        until they let go and press again.
        """
        for walker in self._walkers.values():
            walker.position = None
        self._everybody_needs_news()

    def set_direction(self, name: str, dx: int, dy: int):
        """Remember where the player wants to go. It stays until it is set again."""
        walker = self._walkers[name]
        walker.dx = dx
        walker.dy = dy

    def position_of(self, name: str):
        """Where the player stands, as `(x, y)`, or None before the first tick placed them."""
        return self._walkers[name].position

    def advance(self, seconds, campus) -> bool:
        """Move every player for `seconds`. Returns whether there is news to send.

        There is news if somebody moved in this step, or if somebody joined or
        left since the members were last told. `campus` is the checked map
        from `load_campus`.
        """
        somebody_moved = False
        for walker in self._walkers.values():
            if self._advance_one(walker, seconds, campus):
                somebody_moved = True
        if somebody_moved:
            self._everybody_needs_news()
        return len(self.names_to_tell()) > 0

    def positions(self) -> list:
        """(name, x, y) triples in joining order, as `protocol.positions` wants them.

        A newcomer is listed from the first `advance` after joining, and so
        is a player who was put back on the spawn.
        """
        return [
            (name, walker.position[0], walker.position[1])
            for name, walker in self._walkers.items()
            if walker.position is not None
        ]

    def names_to_tell(self) -> list:
        """The players who have not been sent the newest positions yet."""
        return [name for name, walker in self._walkers.items() if walker.needs_news]

    def mark_told(self, name: str):
        """The newest positions are on their way to this player."""
        self._walkers[name].needs_news = False

    def _advance_one(self, walker: Walker, seconds, campus) -> bool:
        """Move one player. Returns whether the position is different afterwards."""
        if walker.position is None:
            walker.position = (campus["spawn"]["x"], campus["spawn"]["y"])
        before = walker.position
        walker.position = movement.step(
            before[0], before[1], walker.dx, walker.dy,
            seconds, campus["solids"], campus["width"], campus["height"],
        )
        return walker.position != before

    def _everybody_needs_news(self):
        for walker in self._walkers.values():
            walker.needs_news = True
