"""Play test of the statistics (M2-2.4, S-40).

What the tester played in real browsers with two accounts and a guest, and
what `test_server_statistics.py` does not already check, as far as the
server takes part in it:

- a whole evening: three Duels (a first lobby, a new lobby with a new code,
  a second round in the same lobby after one player left to look at the
  profile and came back), with profile and leaderboard read after each as
  the page asks for them. The best time in the profile is the time of the
  ranking, it only gets better, and the leaderboard goes by wins before time;
- after rounds that counted: a round one player left in the middle and a
  round in which the time ran out change only what they should, and the
  leaderboard puts accounts without a time behind those with one, by name;
- messages sent past the page (a profile with somebody's name in it, the
  same question several times at once, a question right after logging
  out, questions in a running round) are answered with the texts of
  DESIGN.md, section 9, show nobody anything of another account and leave
  the round as it was.

The rounds are played like in test_server_statistics.py: the tick is off,
the server's clock is set by the test, every station holds the placeholder
and every test gets a fresh store in memory.
"""

from server import protocol
from server.main import app
from task_helpers import client, clock, connect  # noqa: F401
from task_helpers import placeholder_at_every_station  # noqa: F401
from task_helpers import ask, lobby_named, player
from test_server_duel import fixed_routes  # noqa: F401
from test_server_duel import (
    FIXED_ROUTES,
    call_tick,
    duel_of,
    news,
    play,
    play_route,
    start,
    the_duel_of,
    wait_for_the_open_lobby,
)
from test_server_statistics import store  # noqa: F401
from test_server_statistics import (
    GUEST_MESSAGE,
    NOT_SIGNED_IN,
    guest,
    leaderboard_for,
    profile,
    profile_of,
    wait_for_rounds,
)

LONG_NAME = "Maximiliano12345"  # 16 characters, the longest name there is
UNKNOWN_FIELD = {
    "type": "error",
    "code": "unknown_field",
    "message": "That message has a field the server does not expect.",
}


def board(*rows):
    """The leaderboard after the Duel-only games played here, best first."""
    listed = [
        {
            "place": index + 1,
            "name": name,
            "wins": wins,
            "classic_wins": 0,
            "duel_wins": wins,
            "best_duel_seconds": best,
        }
        for index, (name, wins, best) in enumerate(rows)
    ]
    return {"type": "leaderboard", "players": listed}


def play_round(players, clock, store, waits):  # noqa: F811
    """The first player starts, then all play their routes in the order of `waits`.

    `waits` is `{name: seconds}`: how long each one dawdles before playing
    the three stations (one second each). Returns the ranking everybody was
    sent, after the result was written.
    """
    written_before = len(store.rounds)
    for connection in players.values():
        news(connection)
    start(players)
    told = []
    for name, seconds in waits.items():
        clock.wait(seconds)
        told = play_route(players[name], name, clock)
    wait_for_rounds(store, written_before + 1)
    results = [message for message in told if message["type"] == "duel_result"]
    assert len(results) == 1 and results[0]["time_up"] is False
    for connection in players.values():
        news(connection)
    return results[0]["ranking"]


def seconds_of(ranking, name):
    return next(row["seconds"] for row in ranking if row["name"] == name)


def leave(connection):
    """Leave the lobby. What was still waiting (a notice about a new host) is read first."""
    news(connection)
    assert ask(connection, {"type": "leave_lobby"}) == {"type": "left_lobby"}


def join(connection, code):
    assert ask(connection, {"type": "join_lobby", "code": code})["phase"] == "lobby"


def test_three_rounds_of_two_accounts_and_a_guest_add_up(connect, clock, fixed_routes, store):  # noqa: F811
    mara = player(connect, "Mara")
    long_name = player(connect, LONG_NAME)
    visitor, guest_name = guest(connect)

    # Before anything was played.
    assert leaderboard_for(visitor) == board()
    assert leaderboard_for(mara) == board()
    assert profile_of(mara) == profile("Mara", 0, 0, None)
    assert profile_of(visitor) == GUEST_MESSAGE

    # Round 1 in Mara's lobby: the long name wins, the guest is last.
    first_code = ask(mara, {"type": "create_lobby"})["code"]
    join(long_name, first_code)
    join(visitor, first_code)
    players = {"Mara": mara, LONG_NAME: long_name, guest_name: visitor}
    ranking = play_round(players, clock, store, {LONG_NAME: 19.4, "Mara": 0, guest_name: 0})
    assert [(row["place"], row["name"]) for row in ranking] == [(1, LONG_NAME), (2, "Mara"), (3, guest_name)]
    for connection in players.values():
        leave(connection)
    assert app.state.lobbies.all() == []

    # Rounds 1, a win for the winner only, and the best time is the time of the ranking.
    assert profile_of(long_name) == profile(LONG_NAME, 1, 1, 22.4)
    assert profile_of(mara) == profile("Mara", 1, 0, 25.4)
    assert profile_of(long_name)["best_duel_seconds"] == seconds_of(ranking, LONG_NAME)
    assert profile_of(mara)["best_duel_seconds"] == seconds_of(ranking, "Mara")
    assert profile_of(visitor) == GUEST_MESSAGE
    # Everybody reads the same leaderboard, the guest too, and the guest is not on it.
    after_one = board((LONG_NAME, 1, 22.4), ("Mara", 0, 25.4))
    assert leaderboard_for(mara) == leaderboard_for(long_name) == leaderboard_for(visitor) == after_one

    # Round 2 in a new lobby with a new code: Mara wins with a better time
    # than before, the long name is slower than before.
    second_code = ask(long_name, {"type": "create_lobby"})["code"]
    assert second_code != first_code
    join(mara, second_code)
    join(visitor, second_code)
    players = {LONG_NAME: long_name, "Mara": mara, guest_name: visitor}
    ranking = play_round(players, clock, store, {"Mara": 10, guest_name: 0, LONG_NAME: 11})
    assert seconds_of(ranking, "Mara") == 13.0 and seconds_of(ranking, LONG_NAME) == 30.0

    # Mara leaves to look at her numbers and comes back into the same lobby.
    leave(mara)
    assert profile_of(mara) == profile("Mara", 2, 1, 13.0)
    # One win each now: the better time is first.
    assert leaderboard_for(mara) == board(("Mara", 1, 13.0), (LONG_NAME, 1, 22.4))
    join(mara, second_code)

    # Round 3 in the same lobby: the long name wins again, both slower than their best.
    players = {LONG_NAME: long_name, guest_name: visitor, "Mara": mara}
    ranking = play_round(players, clock, store, {LONG_NAME: 37, guest_name: 0, "Mara": 0})
    assert lobby_named("Mara").code == second_code
    assert seconds_of(ranking, LONG_NAME) == 40.0 and seconds_of(ranking, "Mara") == 46.0
    assert profile_of(mara) == profile("Mara", 3, 1, 13.0)
    assert profile_of(long_name) == profile(LONG_NAME, 3, 2, 22.4)
    # Wins count before the time: Mara has the better time and is second.
    after_three = board((LONG_NAME, 2, 22.4), ("Mara", 1, 13.0))
    assert leaderboard_for(mara) == leaderboard_for(visitor) == after_three
    assert profile_of(visitor) == GUEST_MESSAGE
    assert store.records_of(guest_name) == {}

    # The page was loaded again: a new connection that logs in reads the same numbers.
    leave(mara)
    assert ask(mara, {"type": "log_out"}) == {"type": "signed_out"}
    again = connect()
    assert ask(again, {"type": "log_in", "name": "Mara", "password": "password123"})["type"] == "signed_in"
    assert profile_of(again) == profile("Mara", 3, 1, 13.0)
    assert leaderboard_for(again) == after_three


def test_a_round_somebody_left_and_a_round_nobody_finished_change_only_what_they_should(
    connect, clock, fixed_routes, store  # noqa: F811
):
    mara = player(connect, "Mara")
    tiago = player(connect, "Tiago")
    code = ask(mara, {"type": "create_lobby"})["code"]
    join(tiago, code)
    players = {"Mara": mara, "Tiago": tiago}
    play_round(players, clock, store, {"Mara": 0, "Tiago": 0})
    assert profile_of(mara) == profile("Mara", 1, 1, 3.0)
    assert profile_of(tiago) == profile("Tiago", 1, 0, 6.0)

    # Ines joins, plays one station and leaves in the middle of the round.
    ines = player(connect, "Ines")
    join(ines, code)
    players["Ines"] = ines
    for connection in players.values():
        news(connection)
    start(players)
    play(ines, "Ines", FIXED_ROUTES[2][0], clock)
    leave(ines)
    # Asked during the round she left: nothing.
    assert profile_of(ines) == profile("Ines", 0, 0, None)
    clock.wait(20)  # both slower than their best
    play_route(tiago, "Tiago", clock)
    play_route(mara, "Mara", clock)
    wait_for_rounds(store, 2)
    # Nothing was written for Ines, and she is not on the leaderboard.
    assert profile_of(ines) == profile("Ines", 0, 0, None)
    assert store.records_of("Ines") == {}
    assert leaderboard_for(ines) == board(("Mara", 1, 3.0), ("Tiago", 1, 6.0))
    assert profile_of(mara) == profile("Mara", 2, 1, 3.0)
    assert profile_of(tiago) == profile("Tiago", 2, 1, 6.0)

    # Two new accounts join, Zed before Abe. Mara does one station, then the time runs out.
    zed = player(connect, "Zed")
    abe = player(connect, "Abe")
    join(zed, code)
    join(abe, code)
    players = {"Mara": mara, "Tiago": tiago, "Zed": zed, "Abe": abe}
    for connection in players.values():
        news(connection)
    start(players)
    play(mara, "Mara", FIXED_ROUTES[0][0], clock)
    clock.wait(181)
    call_tick(mara)
    told = wait_for_the_open_lobby(mara)
    result = next(message for message in told if message["type"] == "duel_result")
    assert result["time_up"] is True
    assert [(row["place"], row["name"], row["seconds"]) for row in result["ranking"]][0] == (1, "Mara", None)
    wait_for_rounds(store, 3)

    # One more round for everybody ranked, nobody a win, no best time touched.
    assert profile_of(mara) == profile("Mara", 3, 1, 3.0)
    assert profile_of(tiago) == profile("Tiago", 3, 1, 6.0)
    assert profile_of(zed) == profile("Zed", 1, 0, None)
    assert profile_of(abe) == profile("Abe", 1, 0, None)
    # Without a time after those with one, then by name: Abe before Zed, though Zed joined first.
    expected = board(("Mara", 1, 3.0), ("Tiago", 1, 6.0), ("Abe", 0, None), ("Zed", 0, None))
    assert leaderboard_for(zed) == leaderboard_for(ines) == expected


def test_a_profile_with_a_name_in_it_is_refused_and_shows_nobody_elses_numbers(
    connect, clock, fixed_routes, store  # noqa: F811
):
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    for name in ("Tiago", "Mara"):
        play_route(players[name], name, clock)
    wait_for_rounds(store, 1)
    news(mara)
    news(tiago)
    for extra in ({"name": "Tiago"}, {"mode": "duel"}):
        assert ask(mara, {"type": "get_profile", **extra}) == UNKNOWN_FIELD
    assert ask(mara, {"type": "get_leaderboard", "limit": 1000}) == UNKNOWN_FIELD
    # The plain question still gives her own numbers, and Tiago heard nothing of all this.
    assert profile_of(mara) == profile("Mara", 1, 0, 6.0)
    assert news(tiago) == []


def test_the_same_question_several_times_at_once_gets_one_answer_each(connect, clock, fixed_routes, store):  # noqa: F811
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara, tiago = players["Mara"], players["Tiago"]
    # In the running round, past the page: three questions before any answer is read.
    for message_type in ("get_profile", "get_leaderboard", "get_profile"):
        mara.send_json({"type": message_type})
    answers = news(mara)
    assert answers == [profile("Mara", 0, 0, None), board(), profile("Mara", 0, 0, None)]
    # Nobody else was told, and the round is as it was.
    assert news(tiago) == []
    assert the_duel_of("Mara").progress() == [("Mara", 0), ("Tiago", 0)]
    assert store.rounds == []


def test_a_question_right_after_logging_out_is_not_answered_with_numbers(connect, clock, fixed_routes, store):  # noqa: F811
    players, code = duel_of(connect, ["Mara", "Tiago"])
    mara = players["Mara"]
    for name in ("Mara", "Tiago"):
        play_route(players[name], name, clock)
    wait_for_rounds(store, 1)
    leave(mara)
    for message_type in ("log_out", "get_profile", "get_leaderboard"):
        mara.send_json({"type": message_type})
    assert news(mara) == [protocol.signed_out(), NOT_SIGNED_IN, NOT_SIGNED_IN]
