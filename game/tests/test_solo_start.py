"""A new lobby starts in Solo and switches to Duel with the second player (S-203).

Felix, 2026-11-23: a host alone can start at once; the second player turns
the lobby into a Duel (`mode_after_a_join`, S-125); nothing switches back
when players leave; the host can still choose any mode by hand.
"""

from server import protocol
from server.net.lobbies import Lobbies

from task_helpers import ask, client, connect, lobby_named, player  # noqa: F401
from test_server_duel import news


def lobby_states(messages):
    return [message for message in messages if message["type"] == "lobby_state"]


def create(connection):
    return ask(connection, {"type": "create_lobby"})


def join(connection, code):
    return ask(connection, {"type": "join_lobby", "code": code})


# Accepted


def test_a_new_lobby_is_in_solo_and_its_host_can_start_at_once(connect):
    mara = player(connect, "Mara")
    assert create(mara)["mode"] == "solo"
    started = ask(mara, {"type": "start_game"})
    assert started["type"] == "lobby_state" and started["phase"] == "round" and started["mode"] == "solo"


def test_the_second_player_switches_the_lobby_to_duel_and_both_are_told(connect):
    mara = player(connect, "Mara")
    code = create(mara)["code"]
    tiago = player(connect, "Tiago")

    assert join(tiago, code)["mode"] == "duel"  # what the guest sees
    assert lobby_states(news(mara))[-1]["mode"] == "duel"
    assert lobby_named("Mara").mode == "duel"


def test_a_mode_the_host_chose_by_hand_stays_when_somebody_joins(connect):
    for chosen in ("classic", "duel"):
        mara = player(connect, f"Mara{chosen}")
        code = create(mara)["code"]
        assert ask(mara, {"type": "choose_mode", "mode": chosen})["mode"] == chosen
        tiago = player(connect, f"Tiago{chosen}")
        assert join(tiago, code)["mode"] == chosen
        assert lobby_states(news(mara))[-1]["mode"] == chosen


# Rejected


def test_when_the_second_player_leaves_the_lobby_stays_in_duel(connect):
    mara = player(connect, "Mara")
    code = create(mara)["code"]
    tiago = player(connect, "Tiago")
    join(tiago, code)
    news(mara)
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}

    assert lobby_states(news(mara))[-1]["mode"] == "duel"  # no automatic switch back
    assert ask(mara, {"type": "start_game"}) == protocol.too_few_players("duel")


def test_solo_with_two_players_is_still_refused(connect):
    mara = player(connect, "Mara")
    code = create(mara)["code"]
    join(player(connect, "Tiago"), code)
    news(mara)
    assert ask(mara, {"type": "choose_mode", "mode": "solo"})["code"] == "solo_needs_one_player"


# Edge cases (the plain lobby rules)


def test_every_new_lobby_is_in_solo_also_after_the_last_one_emptied():
    lobbies = Lobbies()
    lobbies.create("Mara", lambda: "ABCD")
    assert lobbies.find("ABCD").mode == "solo"
    lobbies.join("Tiago", "ABCD")
    assert lobbies.find("ABCD").mode == "duel"
    lobbies.leave("Tiago")
    lobbies.leave("Mara")
    lobbies.create("Ines", lambda: "EFGH")
    assert lobbies.find("EFGH").mode == "solo"
