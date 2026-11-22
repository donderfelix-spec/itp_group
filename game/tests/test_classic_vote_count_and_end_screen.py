"""The page in Node: the vote count of each vote button and "New Round" for the host only.

Felix, 2026-11-22: the vote buttons jumped, because a small character of
every voter was put into the button. Now a button shows the letter, the
name and a count field of fixed size; who voted is in the button's label
and title, e.g. "Bo — votes: Ana, Cy". The data of `meeting_state` is
unchanged. On the end screen only the host sees "New Round"; everybody
else sees "The host can start the next round." and no button for it.

Runs the page's own JavaScript through tests/classic_cleanup_in_node.js.
The sizes on screen are checked in Chromium in test_play_meeting_window_and_end_screen.py.
"""

from test_classic_round_end_cleanup import (
    OWN,
    PLAYERS,
    RESULT,
    classic_round_as_free_rider,
    meeting_state,
    needs_node,
    run_page,
    signed_in_lobby,
)

LONG_NAME = "Maximilianaaaaaa"  # 16 letters, the longest name an account may have
EIGHT = ["Ana", "Bo", "Cy", "Di", "Ed", "Flo", "Gus", LONG_NAME]


def meeting_with(phase, **changes):
    step = meeting_state(phase)
    step[1].update(changes)
    return step


def shown_votes(look):
    """{target: (number in its count field, its label)}."""
    return {target: (vote["count"], vote["label"]) for target, vote in look["votes"].items()}


def lobby_with_host(phase, host):
    return ["receive", {
        "type": "lobby_state", "code": "ABCD", "host": host, "mode": "classic",
        "phase": phase, "players": PLAYERS,
    }]


def round_ended_with_host(host):
    """A Classic round that ends while `host` is the host; the end screen is open."""
    return [
        ["receive", {"type": "signed_in", "name": OWN, "guest": False}],
        lobby_with_host("lobby", host),
        lobby_with_host("countdown", host),
        lobby_with_host("round", host),
        ["receive", {"type": "classic_role", "role": "HP", "task_stations": [1]}],
        ["receive", RESULT],
        lobby_with_host("lobby", host),
        ["wait", 50],
        ["look"],
    ]


# ---- Accepted: the count and the label follow every vote -----------------------


@needs_node
def test_without_votes_every_button_shows_a_pale_zero_and_no_votes():
    steps = classic_round_as_free_rider() + [meeting_state("voting"), ["look"]]
    seen = run_page(steps)["looks"][-1]
    assert shown_votes(seen) == {
        "Ana": ("0", "Ana — no votes"), "Bo": ("0", "Bo — no votes"), "Cy": ("0", "Cy — no votes"),
    }
    assert all(vote["countIsZero"] for vote in seen["votes"].values())
    # The title says the same as the label, for a mouse pointer.
    assert all(vote["title"] == vote["label"] for vote in seen["votes"].values())
    assert seen["voterIcons"] == 0


@needs_node
def test_the_count_and_label_follow_arriving_changed_and_withdrawn_votes():
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"),
        meeting_with("voting", vote_targets={"Bo": "Cy"}), ["look"],
        meeting_with("voting", vote_targets={"Bo": "Cy", "Ana": "Cy", "Cy": "Bo"}), ["look"],
        meeting_with("voting", vote_targets={"Bo": "Ana", "Ana": "Cy", "Cy": "Bo"}), ["look"],
        meeting_with("voting", vote_targets={"Bo": "Ana"}), ["look"],
    ]
    one, three, changed, withdrawn = run_page(steps)["looks"][-4:]
    assert shown_votes(one)["Cy"] == ("1", "Cy — votes: Bo")
    assert shown_votes(three) == {
        "Ana": ("0", "Ana — no votes"), "Bo": ("1", "Bo — votes: Cy"), "Cy": ("2", "Cy — votes: Ana, Bo"),
    }
    assert three["selectedVoteTarget"] == "Cy"
    assert shown_votes(changed) == {
        "Ana": ("1", "Ana — votes: Bo"), "Bo": ("1", "Bo — votes: Cy"), "Cy": ("1", "Cy — votes: Ana"),
    }
    assert shown_votes(withdrawn) == {
        "Ana": ("1", "Ana — votes: Bo"), "Bo": ("0", "Bo — no votes"), "Cy": ("0", "Cy — no votes"),
    }
    assert withdrawn["selectedVoteTarget"] is None
    assert withdrawn["votes"]["Ana"]["countIsZero"] is False
    assert withdrawn["votes"]["Cy"]["countIsZero"] is True
    assert [look["voterIcons"] for look in (one, three, changed, withdrawn)] == [0, 0, 0, 0]


@needs_node
def test_the_voters_are_listed_alphabetically_whatever_order_the_server_sends():
    steps = classic_round_as_free_rider() + [
        meeting_with("voting", living=EIGHT, ghosts=[],
                     vote_targets={"Gus": "Bo", LONG_NAME: "Bo", "Ana": "Bo", "Di": "Bo"}),
        ["look"],
    ]
    seen = run_page(steps)["looks"][-1]
    assert shown_votes(seen)["Bo"] == ("4", f"Bo — votes: Ana, Di, Gus, {LONG_NAME}")
    assert [button["target"] for button in seen["voteButtons"]] == EIGHT
    assert shown_votes(seen)[LONG_NAME] == ("0", f"{LONG_NAME} — no votes")


@needs_node
def test_the_buttons_are_built_once_and_only_their_count_changes():
    # The same living players: the buttons stay the same elements, so the
    # grid is never rebuilt while votes come and go.
    steps = classic_round_as_free_rider() + [
        meeting_state("voting"), ["look"],
        meeting_with("voting", vote_targets={"Ana": "Bo"}), ["look"],
    ]
    before, after = run_page(steps)["looks"][-2:]
    assert [b["target"] for b in before["voteButtons"]] == [b["target"] for b in after["voteButtons"]]
    assert shown_votes(after)["Bo"] == ("1", "Bo — votes: Ana")


# ---- Rejected and edge cases ---------------------------------------------------------


@needs_node
def test_a_vote_for_somebody_not_living_or_from_a_bad_message_shows_no_count():
    steps = classic_round_as_free_rider() + [
        meeting_with("voting", vote_targets={"Ana": "Nobody"}), ["look"],
        meeting_with("voting", vote_targets="Ana"), ["look"],
        meeting_with("voting", vote_targets=None), ["look"],
    ]
    for seen in run_page(steps)["looks"][-3:]:
        assert {target: vote["count"] for target, vote in seen["votes"].items()} == {"Ana": "0", "Bo": "0", "Cy": "0"}


@needs_node
def test_a_vote_from_a_ghost_still_counts_as_the_server_sent_it():
    # The server decides who may vote; the page only shows vote_targets.
    steps = classic_round_as_free_rider() + [
        meeting_with("voting", vote_targets={"Di": "Bo"}), ["look"],
    ]
    assert shown_votes(run_page(steps)["looks"][-1])["Bo"] == ("1", "Bo — votes: Di")


# ---- The end screen: "New Round" only for the host -----------------------------------


@needs_node
def test_the_host_sees_new_round_on_the_end_screen():
    seen = run_page(round_ended_with_host(OWN))["looks"][-1]
    assert seen["endScreenHidden"] is False
    assert seen["newRound"] == {"hidden": False, "disabled": False}
    assert seen["hostHint"] == "Start another round with the same lobby."


@needs_node
def test_a_player_who_is_not_the_host_does_not_see_new_round():
    steps = round_ended_with_host("Bo") + [["click", "classic-new-round"]]
    result = run_page(steps)
    seen = result["looks"][-1]
    assert seen["endScreenHidden"] is False
    assert seen["newRound"] == {"hidden": True, "disabled": True}
    assert seen["hostHint"] == "The host can start the next round."
    # Even a click on the hidden button sends nothing.
    assert not any(message["type"] == "start_game" for message in result["sent"])


@needs_node
def test_new_round_follows_a_host_change_while_the_end_screen_is_open():
    steps = round_ended_with_host("Bo") + [
        lobby_with_host("lobby", OWN), ["look"],
        lobby_with_host("lobby", "Cy"), ["look"],
    ]
    not_host, became_host, lost_host = run_page(steps)["looks"][-3:]
    assert not_host["newRound"]["hidden"] is True
    assert became_host["endScreenHidden"] is False
    assert became_host["newRound"] == {"hidden": False, "disabled": False}
    assert became_host["hostHint"] == "Start another round with the same lobby."
    assert lost_host["newRound"] == {"hidden": True, "disabled": True}
    assert lost_host["hostHint"] == "The host can start the next round."


@needs_node
def test_new_round_is_hidden_before_any_round_ended():
    seen = run_page(signed_in_lobby() + [["look"]])["looks"][-1]
    assert seen["endScreenHidden"] is True
    assert seen["newRound"]["hidden"] is True
