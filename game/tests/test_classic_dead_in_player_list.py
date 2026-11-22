"""Dead players in the side panel's Players list during a Classic round.

Lennart showed ghosts as "Dead" in a Players card that main no longer has
(S-130). On main the side panel's Players list shows it instead: a player
whose `classic_roster` entry has `ghost: true` is crossed out (CSS class
`player-dead`) and carries the marker "Dead", so it is not told by colour
alone. Who receives whom stays the server's rule: the living get no ghosts,
ghosts get everybody (test_classic_ghost_visibility_area3.py).

The page runs in Node (tests/classic_cleanup_in_node.js).
"""

from test_classic_round_end_cleanup import (
    classic_round_as_free_rider,
    lobby_state,
    needs_node,
    run_page,
)


def roster(*players):
    return ["receive", {"type": "classic_roster", "players": list(players)}]


def entry(name, character, ghost=False):
    return {"name": name, "character": character, "ghost": ghost}


GHOSTS_VIEW = roster(
    entry("Ana", "c1", ghost=True), entry("Bo", "c2"), entry("Cy", "c3"), entry("Di", "c4", ghost=True),
)


@needs_node
def test_a_ghost_sees_every_ghost_marked_dead():
    seen = run_page(classic_round_as_free_rider() + [GHOSTS_VIEW, ["look"]])["looks"][-1]
    assert seen["deadInList"] == [
        {"name": "Ana", "markers": ["Host", "You", "Dead"]},
        {"name": "Di", "markers": ["Dead"]},
    ]


@needs_node
def test_a_living_player_gets_no_ghost_and_sees_nobody_dead():
    living_view = roster(entry("Ana", "c1"), entry("Bo", "c2"), entry("Cy", "c3"))
    seen = run_page(classic_round_as_free_rider() + [living_view, ["look"]])["looks"][-1]
    assert seen["deadInList"] == []


@needs_node
def test_only_ghost_true_counts_as_dead():
    odd = roster(
        entry("Ana", "c1"), entry("Bo", "c2", ghost="true"), entry("Cy", "c3", ghost=1),
        {"name": "Di", "character": "c4"},
    )
    seen = run_page(classic_round_as_free_rider() + [odd, ["look"]])["looks"][-1]
    assert seen["deadInList"] == []


@needs_node
def test_the_dead_stay_marked_when_the_lobby_changes_during_the_round():
    steps = classic_round_as_free_rider() + [GHOSTS_VIEW, lobby_state("round"), ["look"]]
    seen = run_page(steps)["looks"][-1]
    assert [row["name"] for row in seen["deadInList"]] == ["Ana", "Di"]


@needs_node
def test_after_the_round_nobody_is_marked_dead():
    steps = classic_round_as_free_rider() + [GHOSTS_VIEW, lobby_state("lobby"), ["look"]]
    assert run_page(steps)["looks"][-1]["deadInList"] == []


@needs_node
def test_a_late_roster_after_the_round_changes_nothing_in_the_lobby():
    # The living's roster without the ghost Di arrives after the round ended.
    living_view = roster(entry("Ana", "c1"), entry("Bo", "c2"), entry("Cy", "c3"))
    steps = classic_round_as_free_rider() + [
        lobby_state("lobby"), GHOSTS_VIEW, living_view, ["look"],
    ]
    seen = run_page(steps)["looks"][-1]
    assert seen["deadInList"] == []
    assert seen["listNames"] == ["Ana", "Bo", "Cy", "Di"]
