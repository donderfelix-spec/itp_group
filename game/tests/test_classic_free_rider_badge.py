"""S-227: Free Riders see each other in the Players list, nobody else does.

A Free Rider's page marks the Free Riders' rows in the side panel's Players
list with a "Free Rider" badge, its own row included. It knows the others
only from its own private `classic_role` (`other_free_riders`, sent only to
a Free Rider by `rules.role_reveal_for`); nothing new is sent. A High
Performer's page shows no badge. The badges are gone when the round ends.
"""

import random

from rules import role_reveal_for
from server.classic.round import ClassicRound
from test_classic_round_end_cleanup import (
    lobby_state,
    needs_node,
    run_page,
    signed_in_lobby,
)

BADGE = "Free Rider"


def round_as(role, partners=None):
    role_message = {"type": "classic_role", "role": role}
    if partners is not None:
        role_message["other_free_riders"] = partners
    steps = signed_in_lobby() + [lobby_state("countdown"), lobby_state("round"), ["receive", role_message]]
    if role == "FR":
        steps.append(["receive", {"type": "you_are_fr"}])  # the server's order: role card, then this
    return steps


def badges(look):
    return sorted(row["name"] for row in look["markersInList"] if BADGE in row["markers"])


@needs_node
def test_a_free_rider_sees_the_badge_on_himself_and_the_other_free_rider_only():
    result = run_page(round_as("FR", ["Bo"]) + [["look"]])
    assert badges(result["looks"][-1]) == ["Ana", "Bo"]


@needs_node
def test_with_one_free_rider_only_the_own_row_has_the_badge():
    result = run_page(round_as("FR", []) + [["look"]])
    assert badges(result["looks"][-1]) == ["Ana"]


@needs_node
def test_a_high_performer_sees_no_badge():
    result = run_page(round_as("HP") + [["look"]])
    assert badges(result["looks"][-1]) == []


@needs_node
def test_the_badges_are_gone_when_the_round_ends_and_in_the_next_round_as_high_performer():
    result = run_page(round_as("FR", ["Bo"]) + [
        ["look"], lobby_state("lobby"), ["look"],
        lobby_state("countdown"), lobby_state("round"),
        ["receive", {"type": "classic_role", "role": "HP"}], ["look"],
    ])
    during, after, next_round = result["looks"]
    assert badges(during) == ["Ana", "Bo"]
    assert badges(after) == [] and badges(next_round) == []


def test_only_a_free_rider_is_told_the_other_free_riders():
    # Rule 1: the names come from the private role card, which a High
    # Performer gets without them, and a ghost does not get at all.
    game = ClassicRound(["Ana", "Bo", "Cy", "Di", "Ed", "Fy"], list(range(1, 12)), random.Random(3))
    game.roles = {"Ana": "FR", "Bo": "FR", "Cy": "HP", "Di": "HP", "Ed": "HP", "Fy": "HP"}
    game.eliminated = {"Fy"}
    state = game.state()
    assert role_reveal_for(state, "Ana") == {"role": "FR", "other_free_riders": ["Bo"]}
    assert role_reveal_for(state, "Cy") == {"role": "HP"}
    assert role_reveal_for(state, "Fy") is None
