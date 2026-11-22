"""Play test in Chromium: a refused meeting chat is answered only to its sender (M3-2.1).

Five guests play Classic in real Chromium pages, driven through
`play_classic_leaving_in_browser.js` (the driver of
test_play_classic_leaving.py, reused as it is), against the real server with
its real tick, run in this process. The test holds the server's clock still
while it listens: then the tick has nothing to send in a meeting (no second
of the clock passes, nobody moves), so every WebSocket message a page gets
in that time was caused by what the test did. It skips the clock forward
instead of waiting 45 seconds for the emergency button and 75 for a meeting.

One round:

1. The Free Rider fails a High Performer: a ghost. A living player calls an
   emergency meeting and writes in the chat with the page's own input:
   every page gets it and draws it.
2. The ghost's chat input and Send button are disabled. A chat sent past
   the page (straight on the WebSocket) gives the ghost "You cannot send
   that chat message right now."; the four other pages get no message at all.
3. A living player sends two chats quickly with the page's input: the first
   reaches everybody once, the second (in the 2-second chat cooldown) is
   refused for that player only; the others get nothing for it.
4. In the vote one player votes and another presses Skip: every page shows
   the voter's character next to the target (S-160) and "1 / 3 Skip votes"
   (S-162). A chat sent then is refused for the sender only.
5. The vote's time runs out and a chat is sent right away: the sender gets
   the refusal, every page gets the result exactly once. The window closes
   on every page.
6. After the meeting a chat sent past the page is refused for the sender
   only, by a living player and by the ghost.

No page may log an error or a warning. Skipped when Node, Playwright or
Chromium is missing. Screenshots and a JSON of everything seen go to the
folder in CLASSIC_REFUSED_CHAT_SCREENSHOTS, if that is set.
"""

import json
import os
import socket
import threading
import time
import traceback
from pathlib import Path

import pytest
import uvicorn

from server import main, protocol
from server.main import app
from test_play_classic_leaving import FAIL_PLACE, FAR_PLACES, Browser, Play
from test_play_hiding import (  # noqa: F401 (quiet_tick replaces the fixture of conftest.py)
    fresh_server_state,
    playwright_works,
    press_at_button,
    press_fail,
    put,
    quiet_tick,
    standing_still,
    wait_until,
)

SCREENSHOTS = os.environ.get("CLASSIC_REFUSED_CHAT_SCREENSHOTS")
LABELS = ["P0", "P1", "P2", "P3", "P4"]
CHAT_REJECTED = protocol.REJECTIONS["chat_rejected"]
# How long a page is listened to after a refused chat: several ticks.
LISTEN_SECONDS = 1.0

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")


class HeldClock:
    """The server's clock: the real one, or held still; plus the seconds the test skipped."""

    def __init__(self):
        self.skipped = 0.0
        self.held_at = None

    def __call__(self):
        base = self.held_at if self.held_at is not None else time.monotonic()
        return base + self.skipped

    def hold(self):
        self.held_at = time.monotonic()

    def release(self):
        # The clock goes on from where it was held, not with a jump.
        self.skipped -= time.monotonic() - self.held_at
        self.held_at = None

    def skip(self, seconds):
        self.skipped += seconds


@pytest.fixture(scope="module")
def server():
    """The real server with its real tick and its clock in the test's hand."""
    fresh_server_state()
    clock = HeldClock()
    real_clock = main.seconds_now
    main.seconds_now = clock
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    running = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not running.started:
        assert time.monotonic() < deadline, "the server did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}", clock
    finally:
        running.should_exit = True
        thread.join(timeout=10)
        main.seconds_now = real_clock


# ---- What the pages got -------------------------------------------------


def everything_since(b, label, since):
    """Every message the page received since `since` (its clock): [message]."""
    return b.js(label, f"window.__received.filter((r) => r.t >= {since}).map((r) => r.m)")


def send_past_the_page(b, label, text):
    """Send a chat straight on the page's WebSocket, as a changed page could."""
    b.js(label, f"window.__socket.send(JSON.stringify({{type: 'chat', text: {json.dumps(text)}}}))")


def refused_chat(play, sender, text, labels):
    """Send a chat past the page, listen to every page; what each one got."""
    b = play.browser
    mark = play.marks(labels)
    send_past_the_page(b, sender, text)
    b.wait(sender, f"window.__received.some((r) => r.t >= {mark[sender]} && r.m.type === 'error')")
    time.sleep(LISTEN_SECONDS)
    return {
        "sender_got": everything_since(b, sender, mark[sender]),
        "sender_shown": b.shown(sender, mark[sender]),
        "others_got": {label: everything_since(b, label, mark[label]) for label in labels if label != sender},
        "in_transcript": text in [m["text"] for m in play.lobby().meeting["messages"]],
    }


def shot(b, label, name):
    """A screenshot of the page into CLASSIC_REFUSED_CHAT_SCREENSHOTS, if that is set."""
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        b.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))


def chat_texts(message):
    return [entry["text"] for entry in message.get("messages", [])]


# ---- The play -------------------------------------------------------------


def play_the_meeting(play, labels, seen):
    b, clock = play.browser, play.clock
    names = b.names
    roles = play.start(labels)
    play.role_cards_closed(labels)
    fr = next(label for label in labels if roles[label] == "FR")
    ghost, caller, talker, skipper = [label for label in labels if label != fr]
    seen["roles"] = {names[label]: role for label, role in roles.items()}
    play.spread(labels)

    # The emergency button and the fail are possible 45 seconds after the start.
    clock.skip(50)
    put(names[fr], FAIL_PLACE)
    put(names[ghost], (FAIL_PLACE[0] + 3, FAIL_PLACE[1]))
    standing_still(names[fr])
    press_fail(b, fr)
    wait_until(lambda: names[ghost] in play.classic().eliminated, "the fail")
    put(names[ghost], FAR_PLACES[0])
    put(names[fr], FAR_PLACES[1])
    time.sleep(0.4)

    mark = play.marks(labels)
    press_at_button(b, caller, names[caller])
    play.wait_for_phase(labels, "discussion", mark)
    standing_still(names[caller])
    clock.hold()
    time.sleep(0.5)

    # 1. An accepted chat, written in the page's own input, reaches everybody.
    hello = "Who was near the library?"
    accepted = play.marks(labels)
    b.call("fill", label=caller, selector="#classic-chat-input", text=hello)
    b.call("press", label=caller, key="Enter")
    for label in labels:
        b.wait(label, f"""window.__received.some((r) => r.t >= {accepted[label]} && r.m.type === 'meeting_state'
            && r.m.messages.some((x) => x.text === {json.dumps(hello)}))""")
        b.wait(label, f"window.__meetingTexts.some((d) => d.t >= {accepted[label]} && d.text.includes({json.dumps(hello)}))")
    time.sleep(0.3)
    seen["accepted_chat"] = {
        label: [m["type"] for m in everything_since(b, label, accepted[label])] for label in labels
    }
    shot(b, caller, "1_chat_reaches_everybody_caller")
    shot(b, ghost, "1_chat_reaches_everybody_ghost")

    # 2. The ghost cannot chat.
    seen["ghost_input"] = {
        "input_disabled": b.js(ghost, "document.getElementById('classic-chat-input').disabled"),
        "send_disabled": b.js(ghost, "document.getElementById('classic-chat-send').disabled"),
        "hint": b.text(ghost, "classic-chat-hint"),
    }
    seen["ghost_chat"] = refused_chat(play, ghost, "I am a ghost", labels)
    shot(b, ghost, "2_ghost_chat_refused")

    # 3. A living player chats twice quickly with the page's input.
    first, again = "I was at the cafeteria.", "Really, the cafeteria!"
    quick = play.marks(labels)
    b.call("fill", label=talker, selector="#classic-chat-input", text=first)
    b.call("press", label=talker, key="Enter")
    b.call("fill", label=talker, selector="#classic-chat-input", text=again)
    b.call("press", label=talker, key="Enter")
    b.wait(talker, f"window.__received.some((r) => r.t >= {quick[talker]} && r.m.type === 'error')")
    time.sleep(LISTEN_SECONDS)
    seen["chat_twice"] = {
        "sent": b.js(talker, f"window.__sent.filter((s) => s.t >= {quick[talker]} && s.m.type === 'chat').map((s) => s.m.text)"),
        "talker_got": everything_since(b, talker, quick[talker]),
        "talker_shown": b.shown(talker, quick[talker]),
        "others_got": {label: everything_since(b, label, quick[label]) for label in labels if label != talker},
        "transcript": [m["text"] for m in play.lobby().meeting["messages"]],
        "first": first,
        "again": again,
    }
    shot(b, talker, "3_second_chat_refused")

    # 4. The vote: one vote, one Skip; then a chat in the vote.
    voting = play.marks(labels)
    clock.skip(46)
    play.wait_for_phase(labels, "voting", voting)
    target = fr
    selector = f'.classic-vote-player[data-target-id="{names[target]}"]'
    b.wait(caller, f"document.querySelector('{selector}') !== null && !document.querySelector('{selector}').disabled")
    b.call("click", label=caller, selector=selector)
    b.wait(skipper, "!document.getElementById('classic-skip-discussion').disabled")
    b.call("click", label=skipper, selector="#classic-skip-discussion")
    wait_until(lambda: names[skipper] in play.lobby().meeting.get("skip_votes", ()), "the Skip")
    # The target's vote button names its voters in its title (S-173).
    marker = f"{names[target]} — votes: {names[caller]}"
    for label in labels:
        b.wait(label, f"Array.from(document.querySelectorAll('.classic-vote-player')).some((x) => x.title === {json.dumps(marker)})")
        b.wait(label, "document.getElementById('classic-skip-status').textContent.startsWith('1 / ')")
    time.sleep(0.3)
    seen["vote_shown"] = {
        label: {
            "markers": b.js(label, "Array.from(document.querySelectorAll('.classic-vote-player'))"
                         ".filter((x) => x.querySelector('.classic-vote-count').textContent !== '0').map((x) => x.title)"),
            "selected": b.js(label, "Array.from(document.querySelectorAll('.classic-vote-player-selected')).map((x) => x.dataset.targetId)"),
            "skip_status": b.text(label, "classic-skip-status"),
            "skip_button": b.text(label, "classic-skip-discussion"),
            "chat_input_disabled": b.js(label, "document.getElementById('classic-chat-input').disabled"),
        }
        for label in labels
    }
    seen["vote_expected"] = {"marker": marker, "caller": caller, "skipper": skipper, "target": names[target]}
    shot(b, caller, "4_vote_and_skip_caller")
    shot(b, ghost, "4_vote_and_skip_ghost")
    seen["chat_in_vote"] = refused_chat(play, talker, "Can I still talk?", labels)

    # 5. The vote's time runs out; a chat right away.
    ending = play.marks(labels)
    clock.skip(31)
    send_past_the_page(b, talker, "Wait, one more thing")
    play.wait_for_phase(labels, "result", ending)
    b.wait(talker, f"window.__received.some((r) => r.t >= {ending[talker]} && r.m.type === 'error')")
    shot(b, caller, "5_result_caller")
    result_shown = {label: b.text(label, "classic-vote-result") for label in labels}
    for label in labels:
        b.wait(label, "document.getElementById('classic-meeting').hidden", timeout=6000)
    time.sleep(0.5)
    seen["vote_end"] = {
        "results_per_page": {
            label: len([m for m in b.messages(label, "meeting_state", ending[label]) if m["phase"] == "result"])
            for label in labels
        },
        "talker_errors": b.errors(talker, ending[talker]),
        "others_errors": {label: b.errors(label, ending[label]) for label in labels if label != talker},
        "result_text": result_shown,
        "window_hidden": {label: b.js(label, "document.getElementById('classic-meeting').hidden") for label in labels},
        "round_phase": play.classic().phase,
    }
    shot(b, caller, "5_window_closed_caller")

    # 6. After the meeting: a living player and the ghost chat past the page.
    seen["chat_after_living"] = refused_chat(play, talker, "Hello after the meeting", labels)
    seen["chat_after_ghost"] = refused_chat(play, ghost, "Boo after the meeting", labels)
    clock.release()


@pytest.fixture(scope="module")
def played(server):
    base, clock = server
    browser = Browser(base)
    seen = {"errors": {}}
    play = Play(browser, clock)
    stage = "setup"
    try:
        for label in LABELS:
            browser.open(label)
        browser.call("click", label="P0", selector="#home-create")
        browser.wait("P0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        play.code = browser.js("P0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        play.host = "P0"
        for label in LABELS[1:]:
            play.join(label)
        browser.call("click", label="P0", selector='#lobby-modes button:has-text("Classic")')
        wait_until(lambda: play.lobby().mode == "classic", "Classic chosen")
        stage = "meeting"
        play_the_meeting(play, LABELS, seen)
        stage = "done"
    except Exception:
        seen["errors"][stage] = traceback.format_exc()
        if clock.held_at is not None:
            clock.release()
    finally:
        seen["stage"] = stage
        try:
            seen["problems"] = browser.close()
        except Exception:
            seen["problems"] = ["the browser driver could not be closed"]
        if SCREENSHOTS:
            Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
            (Path(SCREENSHOTS) / "refused_chat_seen.json").write_text(json.dumps(seen, indent=1, default=str))
    return seen


def reached(played, key):
    """The part of the play under `key`; fails with the reason if the play stopped before it."""
    assert key in played, f"the play stopped in {played['stage']}: {played['errors']}"
    return played[key]


def assert_refused_for_the_sender_only(seen):
    assert [m["type"] for m in seen["sender_got"]] == ["error"], seen
    assert seen["sender_got"][0]["message"] == CHAT_REJECTED
    assert [CHAT_REJECTED, True] in seen["sender_shown"], seen
    assert seen["others_got"] == {label: [] for label in seen["others_got"]}, seen
    assert seen["in_transcript"] is False


# ---- The checks -----------------------------------------------------------


def test_an_accepted_chat_reaches_every_page_once(played):
    seen = reached(played, "accepted_chat")
    assert seen == {label: ["meeting_state"] for label in LABELS}


def test_the_ghost_page_cannot_write_in_the_chat(played):
    seen = reached(played, "ghost_input")
    assert seen["input_disabled"] is True
    assert seen["send_disabled"] is True
    assert seen["hint"] == "Ghosts can read the chat but cannot write."


def test_a_ghost_chat_past_the_page_is_refused_for_the_ghost_only(played):
    assert_refused_for_the_sender_only(reached(played, "ghost_chat"))


def test_a_second_chat_in_the_cooldown_is_refused_for_the_sender_only(played):
    seen = reached(played, "chat_twice")
    assert seen["sent"] == [seen["first"], seen["again"]]
    # The sender: the first chat in the meeting, then the refusal of the second.
    assert [m["type"] for m in seen["talker_got"]] == ["meeting_state", "error"], seen
    assert seen["talker_got"][1]["message"] == CHAT_REJECTED
    assert [CHAT_REJECTED, True] in seen["talker_shown"]
    # Everybody else: the first chat once, nothing for the second.
    for label, got in seen["others_got"].items():
        assert [m["type"] for m in got] == ["meeting_state"], (label, got)
        assert chat_texts(got[0]).count(seen["first"]) == 1
        assert seen["again"] not in chat_texts(got[0])
    assert seen["first"] in seen["transcript"]
    assert seen["again"] not in seen["transcript"]


def test_votes_and_skips_show_on_every_page(played):
    seen = reached(played, "vote_shown")
    expected = played["vote_expected"]
    for label, page in seen.items():
        assert page["markers"] == [expected["marker"]], (label, page)
        assert page["skip_status"] == "1 / 3 Skip votes to end voting early.", (label, page)
        assert page["chat_input_disabled"] is True
    assert seen[expected["caller"]]["selected"] == [expected["target"]]
    assert seen[expected["skipper"]]["skip_button"] == "Undo Skip"


def test_a_chat_in_the_vote_is_refused_for_the_sender_only(played):
    assert_refused_for_the_sender_only(reached(played, "chat_in_vote"))


def test_a_chat_right_after_the_vote_time_is_refused_and_the_result_comes_once(played):
    seen = reached(played, "vote_end")
    assert seen["talker_errors"] == [CHAT_REJECTED]
    assert seen["others_errors"] == {label: [] for label in seen["others_errors"]}
    assert seen["results_per_page"] == {label: 1 for label in LABELS}
    # One vote against one Skip is a tie: nobody is ejected, the round goes on.
    assert seen["result_text"] == {label: "No one was ejected." for label in LABELS}
    assert seen["window_hidden"] == {label: True for label in LABELS}
    assert seen["round_phase"] == "round"


def test_a_living_players_chat_after_the_meeting_is_refused_for_the_sender_only(played):
    assert_refused_for_the_sender_only(reached(played, "chat_after_living"))


def test_a_ghosts_chat_after_the_meeting_is_refused_for_the_ghost_only(played):
    assert_refused_for_the_sender_only(reached(played, "chat_after_ghost"))


def test_the_whole_play_ran_without_console_errors(played):
    reached(played, "chat_after_ghost")
    assert played["problems"] == []
