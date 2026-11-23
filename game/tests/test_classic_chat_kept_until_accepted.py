"""S-226: a meeting chat message never vanishes silently.

The server keeps its limit of one message per player every 2 seconds
(spam protection, `CHAT_COOLDOWN_SECONDS`). The page keeps the typed text in
the field until the server took it; a refused message goes back into an
empty field and the refusal text of DESIGN.md section 9 shows under the
field for a few seconds. Runs the page in Node (tests/classic_cleanup_in_node.js).
"""

from server import protocol
from test_classic_round_end_cleanup import OWN, classic_round_as_free_rider, meeting_state, needs_node, run_page

REFUSED = protocol.REJECTIONS["chat_rejected"]


def discussion_with(messages):
    step = meeting_state("discussion")
    step[1]["messages"] = [{"player_id": who, "text": text} for who, text in messages]
    return step


def refusal():
    return ["receive", {"type": "error", "code": "chat_rejected", "message": REFUSED}]


@needs_node
def test_the_text_stays_until_the_server_took_it_then_the_field_is_empty():
    result = run_page(classic_round_as_free_rider() + [
        discussion_with([]),
        ["typeChat", "I was at the cafe."], ["lookAtChat"],
        discussion_with([(OWN, "I was at the cafe.")]), ["lookAtChat"],
    ])
    waiting, accepted = result["drawings"]
    assert waiting["chatValue"] == "I was at the cafe."  # not cleared on sending
    assert accepted["chatValue"] == ""
    assert {"type": "chat", "text": "I was at the cafe."} in result["sent"]


@needs_node
def test_a_quick_second_message_that_is_refused_stays_in_the_field_with_the_refusal_shown():
    result = run_page(classic_round_as_free_rider() + [
        discussion_with([]),
        ["typeChat", "First."],
        ["typeChat", "Second, quickly."],  # the player typed over the first one and sent again
        discussion_with([(OWN, "First.")]),  # the first is accepted
        refusal(),  # the second comes within 2 s
        ["lookAtChat"],
        ["wait", 3500], discussion_with([(OWN, "First.")]), ["lookAtChat"],
    ])
    refused, later = result["drawings"]
    assert refused["chatValue"] == "Second, quickly."  # the first's acceptance did not clear the second
    assert refused["chatHint"] == REFUSED and refused["chatRefused"] is True
    assert later["chatValue"] == "Second, quickly."  # still there to send again
    assert later["chatHint"] == "Living players can chat during the discussion." and later["chatRefused"] is False


@needs_node
def test_a_refused_message_comes_back_into_an_empty_field_but_never_over_new_text():
    result = run_page(classic_round_as_free_rider() + [
        discussion_with([]),
        ["typeChat", "Lost?"],
        ["receive", {"type": "error", "code": "not_in_lobby", "message": "x"}],  # another error changes nothing
        ["lookAtChat"],
        refusal(), ["lookAtChat"],
    ])
    other_error, refused = result["drawings"]
    assert other_error["chatValue"] == "Lost?" and other_error["chatRefused"] is False
    assert refused["chatValue"] == "Lost?" and refused["chatHint"] == REFUSED


@needs_node
def test_another_players_message_with_the_same_text_does_not_empty_the_own_field():
    result = run_page(classic_round_as_free_rider() + [
        discussion_with([]),
        ["typeChat", "Skip?"],
        discussion_with([("Bo", "Skip?")]), ["lookAtChat"],
    ])
    assert result["drawings"][0]["chatValue"] == "Skip?"
