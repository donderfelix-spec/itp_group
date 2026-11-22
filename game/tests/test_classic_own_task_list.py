"""Every Classic player is told only their own task list (M3-3.17).

Felix, 2026-11-21: a High Performer's browser lets all stations of the own
list pulse, and only those. The Free Rider has no task list and cannot open
a station; they fake tasks by standing at one. Rule 1: nothing gives the
Free Rider away to the others: no other browser learns their empty list,
and the refusal "Free Riders cannot complete tasks." goes only to them.
"""

from server import main, protocol
from task_helpers import client, clock, connect  # noqa: F401
from test_classic_server_features import ask, classic_for, put_at_station, start_classic
from extra_task_helpers import news


def roles(classic):
    fr = next(name for name, role in classic.roles.items() if role == "FR")
    hps = [name for name, role in classic.roles.items() if role == "HP"]
    return fr, hps


def test_a_high_performer_is_told_the_whole_own_list_in_its_order(connect):
    _connections, _code, _public, messages = start_classic(connect)
    classic = classic_for("Mara")
    _fr, hps = roles(classic)
    for name in hps:
        card = next(message for message in messages[name] if message["type"] == "classic_role")
        assert card["task_stations"] == [int(station) for station in classic.tasks[name]]


def test_the_free_rider_is_told_an_empty_list_and_nobody_else_hears_of_it(connect):
    _connections, _code, public, messages = start_classic(connect)
    classic = classic_for("Mara")
    fr, hps = roles(classic)
    card = next(message for message in messages[fr] if message["type"] == "classic_role")
    assert card["task_stations"] == []
    # The others get exactly one list each, their own, and nothing about the Free Rider's.
    for name in hps:
        lists = [message for message in messages[name] if "task_stations" in message]
        assert len(lists) == 1
        assert lists[0]["task_stations"] == [int(station) for station in classic.tasks[name]]
    assert all("task_stations" not in message for message in public)


def test_the_refusal_goes_only_to_the_free_rider(connect):
    connections, _code, _public, _messages = start_classic(connect)
    classic = classic_for("Mara")
    fr, hps = roles(classic)
    station = int(classic.tasks[fr][0])
    put_at_station(fr, station)

    for kind, fields in (("open_station", {"station": station}), ("finish_station", {})):
        assert ask(connections[fr], {"type": kind, **fields}) == protocol.rejection("fr_cannot_task")
    for name in hps:
        heard = news(connections[name])
        assert all(message.get("code") != "fr_cannot_task" for message in heard)
        assert all("Free Riders" not in str(message.get("message", "")) for message in heard)
    assert classic.progress() == 0.0


def test_a_ghost_high_performer_keeps_its_own_list():
    """Ghosts keep doing their tasks (DESIGN.md 5.9), so their list stays."""

    class Classic:
        roles = {"Ana": "HP", "Fr": "FR"}
        tasks = {"Ana": ["3", "8"], "Fr": ["1", "2"]}
        completed_tasks = {"Ana": {"3"}, "Fr": set()}
        eliminated = {"Ana"}

    assert main.classic_task_stations(Classic, "Ana") == [8]
    assert main.classic_task_stations(Classic, "Fr") == []
    assert main.classic_task_stations(Classic, "Stranger") == []
