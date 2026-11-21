"""What the own browser shows while its Free Rider hides (M3-1.4).

Only the own living Free Rider in a Classic round, standing in a hiding
spot, sees the own character half transparent and the text "Hidden" in the
Classic panel (S-128). A High Performer, a ghost, a Duel and the lobby show
nothing of it. The browser only draws: what the others are sent is decided
by the server (test_server_hiding.py).

Also here: a player the server leaves out of `positions` is no longer drawn,
so a hidden Free Rider does not stay standing where he was last seen, and
comes back at his new place at once.

The rule itself (`ClassicHudActions.ownIsHidden` in
client/js/classic/hud-actions.js) runs in Node on its own; the page with its
own world.js, round.js and main.js runs in tests/classic_cleanup_in_node.js.
Without Node these tests are skipped; CI has Node.
"""

import json
import subprocess
from pathlib import Path

import pytest

from test_classic_round_end_cleanup import (
    NODE,
    OWN,
    PLAYERS,
    RESULT,
    lobby_state,
    needs_node,
    run_page,
    signed_in_lobby,
)

ROOT = Path(__file__).resolve().parents[1]
HUD_ACTIONS = ROOT / "client/js/classic/hud-actions.js"
CAMPUS = json.loads((ROOT / "client/js/world/campus.json").read_text(encoding="utf-8"))
SPOTS = CAMPUS["hiding_spots"]
SPOT = SPOTS[0]  # in the hedge on the Main Deck
IN_THE_SPOT = {"x": SPOT["x"], "y": SPOT["y"]}
OUTSIDE = {"x": SPOT["x"] + SPOT["r"] + 1, "y": SPOT["y"]}
OWN_CHARACTER = "c1"  # Ana's character in PLAYERS
OTHER = "Bo"
OTHER_CHARACTER = "c2"
HIDDEN_ALPHA = 0.5
GHOST_ALPHA = 0.38


def own_is_hidden(**state):
    """`ClassicHudActions.ownIsHidden(state)` of the page's own file, run in Node."""
    script = f"""
      const actions = require({json.dumps(str(HUD_ACTIONS))});
      process.stdout.write(JSON.stringify(actions.ownIsHidden({json.dumps(state)})));
    """
    result = subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def hiding_state(**changes):
    state = {"classicRound": True, "freeRider": True, "ghost": False, "x": SPOT["x"], "y": SPOT["y"], "spots": SPOTS}
    state.update(changes)
    return state


def stand(place, *others):
    """The server tells the own player's place (and others'); the queue plays it."""
    players = [dict(name=OWN, **place)] + [dict(name=name, **where) for name, where in others]
    return [["receive", {"type": "positions", "players": players}], ["wait", 400]]


def classic_round(role="FR"):
    steps = signed_in_lobby() + [lobby_state("countdown"), lobby_state("round")]
    if role == "FR":
        steps.append(["receive", {"type": "you_are_fr"}])
    steps.append(["receive", {"type": "classic_role", "role": role, "other_free_riders": []}])
    return steps


def own_drawn(drawing):
    found = [drawn for drawn in drawing["charactersDrawn"] if drawn["character"] == OWN_CHARACTER]
    assert len(found) == 1, drawing["charactersDrawn"]
    return found[0]


def shows_hiding(look):
    return own_drawn(look)["alpha"] == HIDDEN_ALPHA and look["hiddenHintShown"] is True


def shows_nothing_of_hiding(look):
    return own_drawn(look)["alpha"] == 1 and look["hiddenHintShown"] is False


# The rule on its own


@needs_node
def test_a_living_free_rider_in_a_spot_in_a_classic_round_hides():
    assert own_is_hidden(**hiding_state()) is True


@needs_node
@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_spot_hides_also_on_its_edge(index):
    spot = SPOTS[index]
    assert own_is_hidden(**hiding_state(x=spot["x"], y=spot["y"] + spot["r"])) is True
    assert own_is_hidden(**hiding_state(x=spot["x"], y=spot["y"] + spot["r"] + 0.01)) is False


@needs_node
@pytest.mark.parametrize("changes", [
    {"freeRider": False},
    {"ghost": True},
    {"classicRound": False},
    {"x": 300, "y": 300},
    {"x": None},
    {"x": "595"},
    {"spots": None},
    {"spots": []},
], ids=["high performer", "ghost", "not in a classic round", "outside every spot",
        "no position", "position as text", "no spots", "empty spots"])
def test_nobody_else_hides(changes):
    assert own_is_hidden(**hiding_state(**changes)) is False


@needs_node
def test_no_state_at_all_hides_nobody():
    script = f"""
      const actions = require({json.dumps(str(HUD_ACTIONS))});
      process.stdout.write(JSON.stringify([actions.ownIsHidden(), actions.ownIsHidden(null), actions.inHidingSpot(1, 2)]));
    """
    result = subprocess.run([NODE, "-e", script], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [False, False, False]


# Accepted: the own Free Rider in a spot


@needs_node
def test_the_own_free_rider_in_a_spot_is_half_transparent_and_reads_hidden():
    look = run_page(classic_round() + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert shows_hiding(look), look


@needs_node
def test_leaving_the_spot_takes_the_transparency_and_the_text_away():
    drawings = run_page(classic_round() + stand(IN_THE_SPOT) + [["lookAtDrawing"]] + stand(OUTSIDE) + [["lookAtDrawing"]])["drawings"]
    assert shows_hiding(drawings[0])
    assert shows_nothing_of_hiding(drawings[1]), drawings[1]


@needs_node
def test_only_the_own_character_is_drawn_transparent():
    other_at = {"x": SPOT["x"] + 20, "y": SPOT["y"]}
    look = run_page(classic_round() + stand(IN_THE_SPOT, (OTHER, other_at)) + [["lookAtDrawing"]])["drawings"][0]
    others = [drawn for drawn in look["charactersDrawn"] if drawn["character"] == OTHER_CHARACTER]
    assert [drawn["alpha"] for drawn in others] == [1]
    assert shows_hiding(look)


# Rejected: nobody else sees anything of hiding


@needs_node
def test_a_high_performer_in_a_spot_sees_nothing_of_hiding():
    look = run_page(classic_round("HP") + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert shows_nothing_of_hiding(look), look


@needs_node
def test_a_free_rider_who_is_a_ghost_sees_nothing_of_hiding():
    roster = {"type": "classic_roster", "players": [dict(entry, ghost=entry["name"] == OWN) for entry in PLAYERS]}
    look = run_page(classic_round() + [["receive", roster]] + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert own_drawn(look)["alpha"] == GHOST_ALPHA
    assert look["hiddenHintShown"] is False


@needs_node
def test_in_the_lobby_a_spot_shows_nothing_of_hiding():
    look = run_page(signed_in_lobby() + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert shows_nothing_of_hiding(look), look


@needs_node
def test_in_a_duel_a_spot_shows_nothing_of_hiding():
    steps = signed_in_lobby("duel") + [lobby_state("countdown", "duel"), lobby_state("round", "duel")]
    look = run_page(steps + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert shows_nothing_of_hiding(look), look


@needs_node
def test_a_duel_after_a_classic_round_shows_nothing_of_hiding():
    end = [["receive", RESULT], lobby_state("lobby"), ["wait", 50]]
    duel = [lobby_state("countdown", "duel"), lobby_state("round", "duel")]
    look = run_page(classic_round() + stand(IN_THE_SPOT) + end + duel + stand(IN_THE_SPOT) + [["lookAtDrawing"]])["drawings"][0]
    assert shows_nothing_of_hiding(look), look


# Edge cases: the end of the round, leaving


@needs_node
def test_the_end_of_the_round_ends_hiding_at_once():
    end = [["receive", RESULT], lobby_state("lobby"), ["wait", 50], ["lookAtDrawing"]]
    look = run_page(classic_round() + stand(IN_THE_SPOT) + end)["drawings"][0]
    assert shows_nothing_of_hiding(look), look


@needs_node
def test_leaving_the_lobby_while_hidden_takes_the_text_away():
    leave = [["receive", {"type": "left_lobby"}], ["wait", 50], ["lookAtDrawing"]]
    look = run_page(classic_round() + stand(IN_THE_SPOT) + leave)["drawings"][0]
    assert look["hiddenHintShown"] is False


# A player left out of `positions` is not drawn


def drawn_other(look):
    return [drawn for drawn in look["charactersDrawn"] if drawn["character"] == OTHER_CHARACTER]


@needs_node
def test_a_player_left_out_of_the_positions_is_no_longer_drawn_and_comes_back_at_his_new_place():
    first = {"x": 300, "y": 330}
    later = {"x": 400, "y": 300}
    steps = (
        classic_round("HP")
        + stand(OUTSIDE, (OTHER, first)) + [["lookAtDrawing"]]
        + stand(OUTSIDE) + [["lookAtDrawing"]]
        + [["receive", {"type": "positions", "players": [dict(name=OWN, **OUTSIDE), dict(name=OTHER, **later)]}],
           ["wait", 16], ["lookAtDrawing"]]
    )
    seen, gone, back = run_page(steps)["drawings"]
    assert [drawn["x"] for drawn in drawn_other(seen)] == [first["x"]]
    assert drawn_other(gone) == []
    # Drawn at once at the new place, not gliding from the old one.
    assert [drawn["x"] for drawn in drawn_other(back)] == [later["x"]]


@needs_node
def test_the_own_player_stays_drawn_when_a_message_does_not_list_him():
    steps = classic_round("HP") + stand(OUTSIDE) + [
        ["receive", {"type": "positions", "players": []}], ["wait", 50], ["lookAtDrawing"],
    ]
    look = run_page(steps)["drawings"][0]
    assert own_drawn(look)["x"] == OUTSIDE["x"]


@needs_node
@pytest.mark.parametrize("mode", ["lobby", "duel"])
def test_outside_a_classic_round_a_player_left_out_stays_drawn_as_before(mode):
    if mode == "lobby":
        steps = signed_in_lobby()
    else:
        steps = signed_in_lobby("duel") + [lobby_state("countdown", "duel"), lobby_state("round", "duel")]
    steps += stand(OUTSIDE, (OTHER, {"x": 300, "y": 330})) + stand(OUTSIDE) + [["lookAtDrawing"]]
    drawing = run_page(steps)["drawings"][0]
    assert [drawn["x"] for drawn in drawn_other(drawing)] == [300]


@needs_node
def test_after_a_classic_round_a_player_left_out_stays_drawn_as_before():
    end = [["receive", RESULT], lobby_state("lobby"), ["wait", 50]]
    steps = classic_round() + end + stand(OUTSIDE, (OTHER, {"x": 300, "y": 330})) + stand(OUTSIDE) + [["lookAtDrawing"]]
    drawing = run_page(steps)["drawings"][0]
    assert [drawn["x"] for drawn in drawn_other(drawing)] == [300]
