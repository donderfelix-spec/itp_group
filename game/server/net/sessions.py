"""Who is signed in on which connection.

A connection is in one of three states: signed out, signed in as an account,
or a guest. Being signed in belongs to the connection (S-78): when the
connection closes, it is forgotten.

This is a plain class without any network. A "connection" can be any object
that works as a dict key: the server passes its WebSocket, tests pass strings.
"""

GUEST_NUMBERS = 10_000  # Guest0000 to Guest9999


class Sessions:
    def __init__(self):
        self._signed_in = {}  # connection -> (name, is_guest)

    def is_signed_in(self, connection) -> bool:
        return connection in self._signed_in

    def name_of(self, connection):
        """The player's name, or None when the connection is signed out."""
        if connection not in self._signed_in:
            return None
        return self._signed_in[connection][0]

    def is_guest(self, connection) -> bool:
        return connection in self._signed_in and self._signed_in[connection][1]

    def sign_in_account(self, connection, name: str):
        """Sign the connection in as the account `name`.

        If the account is signed in on another connection, the new one wins
        (S-76): the old connection is signed out and returned, so the server
        can tell it. Otherwise None is returned.
        """
        replaced = self._connection_of_account(name)
        if replaced is not None:
            del self._signed_in[replaced]
        self._signed_in[connection] = (name, False)
        return replaced

    def sign_in_guest(self, connection, pick_number):
        """Sign the connection in as a guest and return the name, "Guest" + four digits.

        `pick_number` is a function that returns a number from 0 to 9999. The
        server passes a random one, tests pass their own. If the picked name is
        in use, the next free number is taken. Returns None if all are in use.
        """
        taken = {name for name, is_guest in self._signed_in.values() if is_guest}
        first = pick_number() % GUEST_NUMBERS
        for step in range(GUEST_NUMBERS):
            name = f"Guest{(first + step) % GUEST_NUMBERS:04d}"
            if name not in taken:
                self._signed_in[connection] = (name, True)
                return name
        return None

    def sign_out(self, connection) -> bool:
        """Sign the connection out. Returns False if it was not signed in.

        Also called when a connection closes: its guest name is free again.
        """
        if connection not in self._signed_in:
            return False
        del self._signed_in[connection]
        return True

    def _connection_of_account(self, name: str):
        """The connection signed in with this account (ignoring case), or None."""
        for connection, (other_name, is_guest) in self._signed_in.items():
            if not is_guest and other_name.lower() == name.lower():
                return connection
        return None
