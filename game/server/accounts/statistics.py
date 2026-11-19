"""The rules for statistics, as plain functions (S-40).

No network, no database and no clock in here: the ranking of a round and the
old numbers are passed in, the new numbers come back. So tests can call
everything directly.

Three shapes are used in this file and by the stores:

    change   what one round adds for one account:
             {"name": "Mara", "rounds": 1, "wins": 1, "best_seconds": 72.4}
    record   what is kept per account and mode:
             {"rounds": 3, "wins": 1, "best_seconds": 72.4}
    total    one account on the leaderboard, as a tuple:
             ("Mara", wins in all modes, best Duel time)

`best_seconds` is None as long as the account has never finished a Duel.
"""

from server.accounts.store import name_key

DUEL = "duel"
# How many accounts the leaderboard shows at most.
LEADERBOARD_SIZE = 20


def changes_from_duel(ranking, account_names) -> list:
    """What a finished Duel adds to the statistics, one change per account.

    `ranking` is the list of rows from `Duel.ranking`. `account_names` are
    the players of the round who are signed in with an account: everybody
    else (a guest, S-38) gets no change. A player who left during the round
    is not in the ranking any more and so gets none either.
    """
    return [_change_from_row(row) for row in ranking if row["name"] in account_names]


def _change_from_row(row) -> dict:
    finished = row["seconds"] is not None
    # Place 1 alone is not a win: when the time ran out before anybody
    # finished, the player with the most stations is on place 1 too. Two
    # players with the same time share place 1 (S-97), and both win.
    won = finished and row["place"] == 1
    return {
        "name": row["name"],
        "rounds": 1,
        "wins": 1 if won else 0,
        "best_seconds": row["seconds"] if finished else None,
    }


def add_change(record, change) -> dict:
    """The record after a round. `record` is None for the first round of an account in a mode."""
    if record is None:
        record = {"rounds": 0, "wins": 0, "best_seconds": None}
    return {
        "rounds": record["rounds"] + change["rounds"],
        "wins": record["wins"] + change["wins"],
        "best_seconds": smaller_time(record["best_seconds"], change["best_seconds"]),
    }


def smaller_time(old, new):
    """The better of two times. None means "no time" and never beats a time."""
    if old is None:
        return new
    if new is None:
        return old
    return min(old, new)


def profile_rows(records, modes) -> list:
    """Rounds and wins for every mode in `modes`, as `(mode, rounds, wins)`.

    `records` is `{mode: record}` of one account. A mode the account has
    never played is listed with zeros, so the profile always has the same rows.
    """
    rows = []
    for mode in modes:
        record = records.get(mode)
        rows.append((mode, record["rounds"], record["wins"]) if record else (mode, 0, 0))
    return rows


def best_duel_seconds(records):
    """The account's best Duel time, or None. `records` is `{mode: record}`."""
    record = records.get(DUEL)
    return record["best_seconds"] if record else None


def total_of(name: str, records) -> tuple:
    """One account's line for the leaderboard. `records` is `{mode: record}`."""
    wins = sum(record["wins"] for record in records.values())
    return (name, wins, best_duel_seconds(records))


def best_first(totals) -> list:
    """The totals in the order of the leaderboard.

    Most wins first. With equal wins the better Duel time, and an account
    without a time after those with one. Then by name, so the order is
    always the same.
    """
    return sorted(totals, key=_leaderboard_key)


def _leaderboard_key(total) -> tuple:
    name, wins, best_seconds = total
    has_no_time = best_seconds is None
    return (-wins, has_no_time, 0 if has_no_time else best_seconds, name_key(name))


def leaderboard_rows(totals) -> list:
    """Number the totals, which are already in order: place 1 is the first one."""
    return [
        {"place": index + 1, "name": name, "wins": wins, "best_seconds": best_seconds}
        for index, (name, wins, best_seconds) in enumerate(totals)
    ]
