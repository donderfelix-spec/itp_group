"""The lobbies: who is in which one, who is host, who has which character.

These are the rules only. There is no network and no randomness in here: the
server passes in a function that picks a lobby code, tests pass their own.

A player is identified by name. Names are unique among connected players
(S-76, S-77), and a player is in at most one lobby.

Every action returns the rejection code as its last value: None when the
action was accepted, otherwise a key of `protocol.REJECTIONS` or
"too_few_players" (whose text depends on the mode, see
`protocol.too_few_players`). A rejected action changes nothing.
"""

from server.net.walking import Walkers
from server.protocol import CHARACTERS, DEFAULT_MODE, MIN_PLAYERS, PHASE_LOBBY, PHASE_ROUND

# Every player has a character of their own (S-75), so a lobby cannot hold
# more players than there are characters.
MAX_PLAYERS = len(CHARACTERS)


class Lobby:
    def __init__(self, code: str):
        self.code = code
        self.host = None
        # name -> character. A dict keeps the order in which the names were
        # added, so this is also the order in which the players joined.
        self._characters = {}
        # Where the players stand on the campus. Kept here so that a player
        # who leaves the lobby in any way loses their position with it.
        self.walkers = Walkers()
        # What the host has chosen to play, and whether the round is running (S-91).
        self.mode = DEFAULT_MODE
        self.phase = PHASE_LOBBY

    def names(self) -> list:
        """The names of the players, in the order they joined."""
        return list(self._characters)

    def players(self) -> list:
        """(name, character) pairs in joining order, as `protocol.lobby_state` wants them."""
        return list(self._characters.items())

    def character_of(self, name: str):
        return self._characters[name]

    def is_full(self) -> bool:
        return len(self._characters) >= MAX_PLAYERS

    def is_empty(self) -> bool:
        return len(self._characters) == 0

    def round_is_running(self) -> bool:
        return self.phase == PHASE_ROUND

    def has_too_few_players(self) -> bool:
        """Whether a round of the chosen mode cannot start yet (S-53)."""
        return len(self._characters) < MIN_PLAYERS[self.mode]

    def start_round(self):
        """The round begins: everybody starts from the spawn point."""
        self.phase = PHASE_ROUND
        self.walkers.back_to_spawn()

    def add(self, name: str):
        """Put the player in with the first character nobody here has (S-75)."""
        self._characters[name] = self._first_free_character()
        self.walkers.add(name)
        if self.host is None:
            self.host = name

    def remove(self, name: str):
        """Take the player out. Returns the new host's name if the host changed, else None."""
        del self._characters[name]
        self.walkers.remove(name)
        if name != self.host:
            return None
        # The first name left is the player who has been here longest.
        self.host = self.names()[0] if not self.is_empty() else None
        return self.host

    def character_is_taken_by_another(self, name: str, character: str) -> bool:
        for other_name, other_character in self._characters.items():
            if other_name != name and other_character == character:
                return True
        return False

    def set_character(self, name: str, character: str):
        self._characters[name] = character

    def _first_free_character(self) -> str:
        taken = set(self._characters.values())
        for character in CHARACTERS:
            if character not in taken:
                return character
        # Cannot happen: MAX_PLAYERS is the number of characters.
        raise RuntimeError("no free character")


class Lobbies:
    def __init__(self):
        self._lobbies = {}  # code -> Lobby
        self._code_of = {}  # name -> code of the lobby the player is in

    def lobby_of(self, name: str):
        """The lobby the player is in, or None."""
        code = self._code_of.get(name)
        if code is None:
            return None
        return self._lobbies[code]

    def count(self) -> int:
        """How many lobbies there are."""
        return len(self._lobbies)

    def all(self) -> list:
        """Every lobby there is."""
        return list(self._lobbies.values())

    def find(self, code: str):
        """The lobby with this code, or None."""
        return self._lobbies.get(code)

    def create(self, name: str, pick_code):
        """Open a new lobby with `name` as host. Returns `(lobby, rejection_code)`.

        `pick_code` is a function that returns four capital letters. If that
        code is in use, it is asked again until it returns a free one.
        """
        if name in self._code_of:
            return (None, "already_in_lobby")
        code = pick_code()
        while code in self._lobbies:
            code = pick_code()
        lobby = Lobby(code)
        self._lobbies[code] = lobby
        self._put_in(lobby, name)
        return (lobby, None)

    def join(self, name: str, code: str):
        """Join the lobby with this code (capital letters). Returns `(lobby, rejection_code)`."""
        if name in self._code_of:
            return (None, "already_in_lobby")
        lobby = self._lobbies.get(code)
        if lobby is None:
            return (None, "no_lobby")
        # Before the check for a full lobby: a full lobby whose round is
        # running stays closed even when somebody leaves it.
        if lobby.round_is_running():
            return (None, "round_running")
        if lobby.is_full():
            return (None, "lobby_full")
        self._put_in(lobby, name)
        return (lobby, None)

    def choose_character(self, name: str, character: str):
        """Change the player's character. Returns `(lobby, changed, rejection_code)`.

        Choosing the character the player already has is accepted and changes
        nothing: `changed` is then False.
        """
        lobby = self.lobby_of(name)
        if lobby is None:
            return (None, False, "not_in_lobby")
        # A character that changes during a round would confuse who is who (S-91).
        if lobby.round_is_running():
            return (None, False, "round_running")
        if lobby.character_is_taken_by_another(name, character):
            return (None, False, "character_taken")
        changed = lobby.character_of(name) != character
        lobby.set_character(name, character)
        return (lobby, changed, None)

    def choose_mode(self, name: str, mode: str):
        """The host sets what will be played. Returns `(lobby, rejection_code)`.

        `mode` is one of `protocol.MODES`; the message check made sure of that.
        """
        lobby, rejection_code = self._lobby_hosted_by(name)
        if rejection_code is not None:
            return (None, rejection_code)
        lobby.mode = mode
        return (lobby, None)

    def start(self, name: str):
        """The host starts the round. Returns `(lobby, rejection_code)`."""
        lobby, rejection_code = self._lobby_hosted_by(name)
        if rejection_code is not None:
            return (None, rejection_code)
        if lobby.has_too_few_players():
            return (None, "too_few_players")
        lobby.start_round()
        return (lobby, None)

    def _lobby_hosted_by(self, name: str):
        """The checks every action of the host begins with. Returns `(lobby, rejection_code)`.

        The lobby is returned only if the player is in one, is its host and
        its round is not running yet. The checks come in this order.
        """
        lobby = self.lobby_of(name)
        if lobby is None:
            return (None, "not_in_lobby")
        if lobby.host != name:
            return (None, "not_host")
        if lobby.round_is_running():
            return (None, "round_running")
        return (lobby, None)

    def leave(self, name: str):
        """Take the player out of their lobby. Returns `(lobby, new_host, rejection_code)`.

        `new_host` is the name of the new host if the player was the host and
        somebody is left, otherwise None. A lobby that is empty afterwards is
        deleted, so its code can be given out again.
        """
        lobby = self.lobby_of(name)
        if lobby is None:
            return (None, None, "not_in_lobby")
        new_host = lobby.remove(name)
        del self._code_of[name]
        if lobby.is_empty():
            del self._lobbies[lobby.code]
        return (lobby, new_host, None)

    def _put_in(self, lobby: Lobby, name: str):
        lobby.add(name)
        self._code_of[name] = lobby.code
