"""Play test of the Duel (M2-4.7, S-94, S-97).

What the tester played in three browsers and what `test_server_duel.py` does
not already check, as far as the server takes part in it:

- messages sent past the page during a running Duel (finishing or closing
  with no task open, the host starting again, opening a station that is
  not the next one while standing at it) are refused with the text of
  DESIGN.md, section 9, tell nobody anything and leave the Duel as it was;
- a player who left the lobby in the middle of a round with a minigame open
  cannot come back while the round runs, can come back after the ranking,
  and then plays the next round from 0/3 with nothing left of the old one.
"""

from server import protocol
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import (
    NO_TASK_OPEN,
    NOT_NEEDED,
    ask,
    close_station,
    finish_station,
    open_station,
    opened,
    put_at_station,
)
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import (
    FIXED_ROUTES,
    duel_of,
    news,
    play,
    play_route,
    progress,
    result,
    start,
    state,
    the_duel_of,
    types_of,
    wait_for_news,
    wait_for_the_open_lobby,
)

ROUND_RUNNING = protocol.rejection("round_running")


def test_refused_messages_in_a_running_duel_tell_nobody_and_change_nothing(connect, clock, fixed_routes):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    first, second, third = FIXED_ROUTES[0]
    assert finish_station(mara) == NO_TASK_OPEN
    assert close_station(mara) == NO_TASK_OPEN
    assert ask(mara, {"type": "start_game"}) == ROUND_RUNNING
    put_at_station("Mara", second)  # standing at it, so it is not "too far"
    assert open_station(mara, second) == NOT_NEEDED
    assert news(mara) == []
    assert news(tiago) == []
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Tiago", 0)]
    assert the_duel_of("Mara").next_station("Mara") == first
    # The round is as playable as before.
    told = play(mara, "Mara", first, clock)
    assert told[1] == state(second, 1)
    assert wait_for_news(tiago, "duel_progress")[-1] == progress(179, ("Mara", 1), ("Tiago", 0))


def test_a_player_who_left_with_a_task_open_comes_back_after_the_ranking_and_starts_at_zero(
    connect, clock, fixed_routes
):
    players, code = duel_of(connect, ["Mara", "Tiago", "Ines"])
    mara, tiago, ines = players["Mara"], players["Tiago"], players["Ines"]
    tiagos_route = FIXED_ROUTES[1]
    play(tiago, "Tiago", tiagos_route[0], clock)
    play(tiago, "Tiago", tiagos_route[1], clock)
    news(tiago)
    put_at_station("Tiago", tiagos_route[2])
    assert open_station(tiago, tiagos_route[2]) == opened(tiagos_route[2])
    assert ask(tiago, {"type": "leave_lobby"}) == {"type": "left_lobby"}
    # While the round runs there is no way back in.
    assert ask(tiago, {"type": "join_lobby", "code": code}) == ROUND_RUNNING
    assert the_duel_of("Mara").names() == ["Mara", "Ines"]

    play_route(mara, "Mara", clock)
    # Ines ends the round with her last station and reads its end as her answer;
    # Mara is told after it, so the test waits for her messages.
    for told in (play_route(ines, "Ines", clock), wait_for_the_open_lobby(mara)):
        ranking = [message for message in told if message["type"] == "duel_result"]
        assert ranking == [result(False, (1, "Mara", 5.0, 3), (2, "Ines", 8.0, 3))]
        assert told[-1]["type"] == "lobby_state" and told[-1]["phase"] == "lobby"
    assert news(tiago) == []  # the leaver heard nothing of the end

    assert ask(tiago, {"type": "join_lobby", "code": code})["phase"] == "lobby"
    for connection in (mara, ines, tiago):
        news(connection)
    back = {"Mara": mara, "Ines": ines, "Tiago": tiago}
    told = start(back)
    # Tiago is the third player now and gets the third route, from its first station.
    assert types_of(told["Tiago"]) == ["lobby_state", "duel_state", "duel_progress"]
    assert told["Tiago"][1] == state(FIXED_ROUTES[2][0], 0)
    assert told["Tiago"][2] == progress(180, ("Mara", 0), ("Ines", 0), ("Tiago", 0))
    # Nothing is left of the task that was open when Tiago left.
    assert close_station(tiago) == NO_TASK_OPEN
    put_at_station("Tiago", FIXED_ROUTES[2][0])
    assert open_station(tiago, FIXED_ROUTES[2][0]) == opened(FIXED_ROUTES[2][0])
