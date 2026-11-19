"""Repeatable, fake-clock playtests for two complete five-player Classic rounds."""

import random

import pytest

from server.classic.round import ClassicRound


PLAYER_IDS = ["Ari", "Bea", "Cal", "Dev", "Eli"]
STATIONS = [1, 2, 3, 4, 5]
SEED = 20261119


def seeded_round():
    round_state = ClassicRound(PLAYER_IDS, STATIONS, random.Random(SEED))
    free_riders = [player for player, role in round_state.roles.items() if role == "FR"]
    high_performers = [player for player, role in round_state.roles.items() if role == "HP"]
    assert free_riders == ["Dev"]
    assert len(high_performers) == 4
    return round_state, free_riders[0], high_performers


def test_playtest_a_hp_win_after_report_meeting_and_fr_ejection():
    """The FR fails one HP; the report meeting votes the FR out."""
    game, fr, hps = seeded_round()
    game.positions = {fr: (0.0, 0.0), **{player: (1.0, 0.0) for player in hps}}

    # 00:08 — Q: nearby HP fails; their sheet appears at their position.
    game.fail(fr, hps[0], 8.0, game.positions[hps[0]])
    sheet_id, sheet_position = next(iter(game.f_sheets.items()))
    assert hps[0] in game.eliminated
    assert game.failure_count == 1

    # 00:09 — R: another living HP finds and reports that exact sheet.
    game.positions[hps[1]] = sheet_position
    meeting = game.report(hps[1], sheet_id, game.positions[hps[1]], 9.0)
    assert meeting["phase"] == "discussion"
    assert meeting["ghosts"] == (hps[0],)
    assert not game.f_sheets

    # 00:10 and 00:12 — two messages are accepted into the shared transcript.
    game.send_chat(hps[1], "I found the sheet by the library.", 10.0)
    game.send_chat(fr, "I was working near the cafe.", 12.0)
    assert [item["text"] for item in game.meeting["messages"]] == [
        "I found the sheet by the library.",
        "I was working near the cafe.",
    ]

    # 00:54 — discussion ends after 45 seconds; voting runs for 30 seconds.
    game.advance_meeting(54.0)
    assert game.meeting["phase"] == "voting"
    for hp in hps[1:]:
        game.cast_vote(hp, fr)
    game.cast_vote(fr, hps[1])
    result = game.advance_meeting(84.0)

    # 01:24 — the FR is ejected and the HP win because no FR remains.
    assert result["phase"] == "result"
    assert result["vote_result"].ejected_id == fr
    assert result["winner"] == "HP"
    assert game.winner() == "HP"
    assert game.result_reason() == "all_free_riders_eliminated"
    assert game.result()["stats"] == {"failures": 1, "completed_tasks": 0, "meetings": 1}


def test_playtest_b_fr_win_after_three_fails_with_cooldown():
    """Two cooldown checks and three timed fails leave one HP against one FR."""
    game, fr, hps = seeded_round()
    game.positions = {fr: (0.0, 0.0), **{player: (1.0, 0.0) for player in hps}}

    # 00:10 — first Q succeeds.
    game.fail(fr, hps[0], 10.0, game.positions[hps[0]])
    assert hps[0] in game.eliminated

    # 00:24.999 — second Q is rejected; no state or statistic changes.
    before = (set(game.eliminated), dict(game.f_sheets), game.failure_count)
    with pytest.raises(ValueError, match="cannot fail"):
        game.fail(fr, hps[1], 24.999, game.positions[hps[1]])
    assert (game.eliminated, game.f_sheets, game.failure_count) == before

    # 00:25 — 15 seconds after the first fail, second Q succeeds.
    game.fail(fr, hps[1], 25.0, game.positions[hps[1]])
    assert hps[1] in game.eliminated

    # 00:40 — 15 seconds later, third Q succeeds. One HP and one FR remain.
    game.fail(fr, hps[2], 40.0, game.positions[hps[2]])
    assert game.eliminated == set(hps[:3])
    living = set(PLAYER_IDS) - game.eliminated
    assert sum(game.roles[player] == "FR" for player in living) == 1
    assert sum(game.roles[player] == "HP" for player in living) == 1
    assert game.failure_count == 3
    assert game.winner() == "FR"
    assert game.result_reason() == "free_riders_reached_parity"
    assert game.result()["reason"] == "free_riders_reached_parity"
    assert game.result()["stats"]["failures"] == 3
