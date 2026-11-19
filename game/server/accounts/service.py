"""The rules for signing up and logging in, as plain functions.

No network and no clock in here. The store and the hasher are passed in, so
tests can use a store in memory and a fast fake hasher.

`sign_up` and `log_in` both return a pair `(name, rejection_code)`:

    ("Mara", None)            it worked; "Mara" is the stored spelling
    (None, "name_taken")      refused; the second value is a code from
                              `protocol.REJECTIONS`

Passwords are never stored or logged, only their hash.
"""

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from server.accounts.store import StoreUnavailable

# Guests are called "Guest" plus digits (S-77). No account may look like one.
GUEST_NAME_PATTERN = re.compile(r"guest[0-9]+", re.IGNORECASE)


class Argon2Hasher:
    """Turns passwords into Argon2 hashes and checks a password against a hash."""

    def __init__(self):
        self._hasher = PasswordHasher()
        # Checked against when the name does not exist, see `log_in`.
        self.dummy_hash = self._hasher.hash("no account has this password")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def matches(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            # Wrong password, or a stored hash that cannot be read.
            return False


def is_guest_name(name: str) -> bool:
    return GUEST_NAME_PATTERN.fullmatch(name) is not None


def sign_up(store, hasher, name: str, password: str):
    """Create the account. Returns `(name, None)` or `(None, rejection code)`."""
    if is_guest_name(name):
        return (None, "name_taken")
    try:
        added = store.add(name, hasher.hash(password))
    except StoreUnavailable:
        return (None, "accounts_unavailable")
    if not added:
        return (None, "name_taken")
    return (name, None)


def log_in(store, hasher, name: str, password: str):
    """Check name and password. Returns `(stored name, None)` or `(None, rejection code)`."""
    try:
        account = store.find(name)
    except StoreUnavailable:
        return (None, "accounts_unavailable")

    if account is None:
        # Hashing is slow on purpose. Without this check an unknown name would
        # be answered much faster than a wrong password, and the time alone
        # would tell an attacker which usernames exist.
        hasher.matches(hasher.dummy_hash, password)
        return (None, "wrong_credentials")

    stored_name, password_hash = account
    if not hasher.matches(password_hash, password):
        return (None, "wrong_credentials")
    return (stored_name, None)
