"""S-228: the victim of a fail reads "You failed." over the map.

The page takes it from `classic_fail`, which names the victim to every
member already (S-159): no new message. It shows for 4 seconds, or until a
meeting opens or the round ends; another player's fail shows nothing. The
page runs in Node (tests/classic_cleanup_in_node.js); the text itself is in
index.html.
"""

from pathlib import Path

from test_classic_round_end_cleanup import OWN, lobby_state, meeting_state, needs_node, run_page, signed_in_lobby

INDEX = Path(__file__).resolve().parents[1] / "client" / "index.html"


def as_high_performer():
    return signed_in_lobby() + [
        lobby_state("countdown"), lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP", "task_stations": [1]}],
    ]


def fail_of(victim):
    return ["receive", {"type": "classic_fail", "target_id": victim, "character": "c1", "sheet_id": "f-sheet-1"}]


def test_the_text_is_you_failed():
    assert '<p id="classic-you-failed" class="classic-you-failed" role="alert" hidden>You failed.</p>' in INDEX.read_text()


@needs_node
def test_the_victim_sees_it_for_four_seconds():
    looks = run_page(as_high_performer() + [
        ["look"], fail_of(OWN), ["look"], ["wait", 3800], ["look"], ["wait", 400], ["look"],
    ])["looks"]
    assert [look["youFailed"]["shown"] for look in looks] == [False, True, True, False]


@needs_node
def test_another_players_fail_shows_nothing():
    looks = run_page(as_high_performer() + [fail_of("Bo"), ["look"]])["looks"]
    assert looks[-1]["youFailed"]["shown"] is False


@needs_node
def test_a_meeting_or_the_end_of_the_round_takes_it_away():
    meeting = run_page(as_high_performer() + [fail_of(OWN), meeting_state("discussion"), ["look"]])["looks"]
    ended = run_page(as_high_performer() + [fail_of(OWN), lobby_state("lobby"), ["look"]])["looks"]
    assert meeting[-1]["youFailed"]["shown"] is False
    assert ended[-1]["youFailed"]["shown"] is False


@needs_node
def test_outside_a_classic_round_nothing_shows():
    looks = run_page(signed_in_lobby() + [fail_of(OWN), ["look"]])["looks"]
    assert looks[-1]["youFailed"]["shown"] is False
