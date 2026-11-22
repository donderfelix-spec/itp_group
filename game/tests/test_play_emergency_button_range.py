"""M3-3.21: the red emergency button works only within reach (S-170 to S-172), in Chromium.

Five guests play Classic in real Chromium pages against the real server,
run in this process. The pages, the server, `put` and the walking with real
keys are the ones of test_play_hiding.py (its driver play_hiding_in_browser.js
is reused). The server's clock is set forward instead of waiting 45 seconds
for the button and 45 seconds of discussion; the 15-second fail cooldown
runs on in real time.

What is played, in this order, in one round:

1. After 45 s the button is drawn at campus.button on every page (each page's
   Game.world.drawMap is wrapped to note whether it was asked to draw the
   button and whether a circle of the button's radius was drawn there).
2. The Free Rider fails a High Performer (this also tells every page that the
   button is unlocked). During the 15-second cooldown he sees "Let fail (N s)"
   away from the button and an enabled "E Emergency" within 25 units of it;
   E sends {"type": "emergency"} and opens the meeting for all five pages.
   The meeting is played to its end (nobody votes, nobody goes).
3. A High Performer far from the button sends {"type": "emergency"} past the
   page: exactly "Walk to the red button to call a meeting.", shown on his
   page, and no meeting. The same 25.5 units away (between the two numbers).
4. The ghost standing on the button sees no "E Emergency"; E sends nothing.
5. A High Performer walks with the key W towards the button: "E Emergency"
   shows once he is within 25 units. Put 26 units away: no hint, E sends
   nothing; 25 units away: the hint, and E (pressed twice quickly) opens one
   meeting for all five pages in phase "discussion"; two players chat and all
   five pages get both lines; 45 seconds later the vote opens on every page.
6. No High Performer's page (the ghost's included) was told who the Free
   Rider is, and no page but his shows "Free Rider" as anybody's role.

Set EMERGENCY_RANGE_SCREENSHOTS to a folder to keep the screenshots (and
seen.json, everything the play recorded). Skipped when Node, Playwright or
Chromium is missing.
"""

import json
import math
import os
import time
import urllib.request
from pathlib import Path

import pytest

from test_play_hiding import (  # noqa: F401 (quiet_tick and server are fixtures)
    BUTTON,
    LABELS,
    SPAWN,
    Browser,
    failed,
    free_place_at,
    lobby_of,
    playwright_works,
    position,
    press_fail,
    put,
    quiet_tick,
    server,
    standing_still,
    start_round,
    wait_for_meeting_phase,
    wait_until,
)
from server import main as server_main
from server.main import app

pytestmark = pytest.mark.skipif(not playwright_works(), reason="Node with Playwright and Chromium is needed")

USE_RANGE = app.state.campus["use_range"]
CENTRE = (BUTTON["x"], BUTTON["y"])
SCREENSHOTS = os.environ.get("EMERGENCY_RANGE_SCREENSHOTS")
OUT_OF_REACH = "Walk to the red button to call a meeting."
EMERGENCY_DELAY_SECONDS = 45
FAIL_COOLDOWN_SECONDS = 15
DISCUSSION_SECONDS = 45

# Installed in every page once it is loaded: what the page sends, and per
# frame whether the map was asked to draw the button and drew it.
PROBE = """(() => {
  window.__sent = [];
  const socket = window.__socket;
  const send = socket.send.bind(socket);
  socket.send = (data) => {
    try { window.__sent.push({ t: performance.now(), m: JSON.parse(data) }); } catch (e) { /* not JSON */ }
    return send(data);
  };
  window.__button = { frame: null };
  const world = window.Game.world;
  const drawMap = world.drawMap;
  const arc = CanvasRenderingContext2D.prototype.arc;
  let arcs = null;
  CanvasRenderingContext2D.prototype.arc = function (x, y, r) {
    if (arcs) arcs.push([x, y, r]);
    return arc.apply(this, arguments);
  };
  world.drawMap = function (ctx, campus, view, emergencyVisible) {
    arcs = [];
    try { return drawMap.apply(this, arguments); } finally {
      const b = campus && campus.button;
      const drawn = Boolean(b) && arcs.some(([x, y, r]) => x === b.x && y === b.y && r === b.r);
      window.__button.frame = { visible: emergencyVisible === true, drawn, t: performance.now() };
      arcs = null;
    }
  };
  return true;
})()"""

# Notes, in the page, the moment "E Emergency" first shows and the own
# position the page was last told at that moment (NAME: the own name).
WATCH_HINT = """(() => {
  window.__hintFlip = null;
  const armed = performance.now();
  const button = document.querySelector('.use-button');
  const observer = new MutationObserver(() => {
    if (window.__hintFlip !== null || button.textContent !== 'E Emergency') return;
    const last = window.__received.filter((r) => r.m.type === 'positions'
      && r.m.players.some((p) => p.name === NAME)).pop();
    const me = last.m.players.find((p) => p.name === NAME);
    window.__hintFlip = { t: performance.now(), armed, told: [me.x, me.y] };
    observer.disconnect();
  });
  observer.observe(button, { childList: true, characterData: true, subtree: true });
  return true;
})()"""

USE_BUTTON = """(() => {
  const b = document.querySelector('.use-button');
  return b ? { text: b.textContent, disabled: b.disabled, failLook: b.classList.contains('fail-button') } : null;
})()"""


def shot(browser, label, name):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        browser.call("screenshot", label=label, path=str(Path(SCREENSHOTS) / f"{name}.png"))


def write_down(seen):
    if SCREENSHOTS:
        Path(SCREENSHOTS).mkdir(parents=True, exist_ok=True)
        (Path(SCREENSHOTS) / "seen.json").write_text(json.dumps(seen, indent=1, default=str))


def stand(browser, label, place):
    """Put the player at `place` and wait until his page was told so (and its HUD followed)."""
    name = browser.names[label]
    put(name, place)
    standing_still(name)
    browser.wait(label, f"""(() => {{
        const last = window.__received.filter((r) => r.m.type === 'positions'
            && r.m.players.some((p) => p.name === {json.dumps(name)})).pop();
        if (!last) return false;
        const me = last.m.players.find((p) => p.name === {json.dumps(name)});
        return Math.abs(me.x - {place[0]}) < 0.11 && Math.abs(me.y - {place[1]}) < 0.11;
    }})()""")
    time.sleep(0.3)  # the use button follows on the next frames


def use_button(browser, label):
    return browser.js(label, USE_BUTTON)


def sent_emergencies(browser, label):
    return browser.js(label, "window.__sent.filter((r) => r.m.type === 'emergency').length")


def meeting_states(browser, label):
    return browser.js(label, "window.__received.filter((r) => r.m.type === 'meeting_state').length")


def errors_since(browser, label, count):
    return browser.js(label, f"window.__received.filter((r) => r.m.type === 'error').slice({count}).map((r) => r.m)")


def error_count(browser, label):
    return browser.js(label, "window.__received.filter((r) => r.m.type === 'error').length")


def press_and_watch(browser, label, key="KeyE", wait=0.8):
    """Press a key; return how many emergency messages the page sent and meeting states each page got."""
    sent = sent_emergencies(browser, label)
    states = {other: meeting_states(browser, other) for other in LABELS}
    browser.call("press", label=label, key=key)
    time.sleep(wait)
    return {
        "sent": sent_emergencies(browser, label) - sent,
        "meetings": {other: meeting_states(browser, other) - states[other] for other in LABELS},
    }


def bypass(browser, label):
    """Send {"type": "emergency"} past the page, as a player with the console would."""
    errors = error_count(browser, label)
    states = {other: meeting_states(browser, other) for other in LABELS}
    browser.js(label, "Game.net.send({ type: 'emergency' })")
    browser.wait(label, f"window.__received.filter((r) => r.m.type === 'error').length > {errors}")
    time.sleep(0.5)
    message = browser.js(label, """(() => {
        const box = document.getElementById('message');
        return { hidden: box.hidden, text: box.textContent };
    })()""")
    return {
        "errors": errors_since(browser, label, errors),
        "shown": message,
        "meetings": {other: meeting_states(browser, other) - states[other] for other in LABELS},
        "server_meeting": lobby_of(browser.names[label]).meeting is not None
        and lobby_of(browser.names[label]).meeting.get("phase") != "result",
    }


def first_meeting_state_since(browser, label, count):
    return browser.js(label, f"window.__received.filter((r) => r.m.type === 'meeting_state').slice({count}).map((r) => r.m)")


def end_meeting(browser, clock, number):
    """Play an open meeting to its end without votes: discussion, vote, result."""
    clock.skip(DISCUSSION_SECONDS + 1)
    wait_for_meeting_phase(browser, LABELS, "voting", number)
    clock.skip(31)
    wait_for_meeting_phase(browser, LABELS, "result", number)
    for label in LABELS:
        browser.wait(label, "document.getElementById('classic-meeting').hidden", timeout=20000)
    time.sleep(0.5)


def leaks_of_the_free_rider(browser, label, fr_name):
    """What a page was told or shows that names the Free Rider's role."""
    return browser.js(label, f"""(() => {{
        const found = [];
        for (const r of window.__received) {{
            const text = JSON.stringify(r.m);
            if (r.m.type === 'classic_role' && r.m.role !== 'HP') found.push(text);
            else if (r.m.type !== 'classic_role' && (text.includes('"FR"') || text.includes('Free Rider'))) found.push(text);
        }}
        const shown = document.body.innerText;
        if (shown.includes('Free Rider') && shown.includes({json.dumps(fr_name)})) {{
            for (const element of document.querySelectorAll('body *')) {{
                if (element.children.length === 0 && element.offsetParent !== null
                    && element.textContent.includes('Free Rider') && element.textContent.includes({json.dumps(fr_name)})) {{
                    found.push('shown: ' + element.textContent);
                }}
            }}
        }}
        return found;
    }})()""")


def straight_line_to_button(distance):
    """A free place `distance` units below the button: the way up to it is free (S-170)."""
    return (CENTRE[0], CENTRE[1] + distance)


@pytest.fixture(scope="module")
def played(server):  # noqa: F811 (the imported fixture)
    base, clock = server
    seen = {}
    with urllib.request.urlopen(base + "/health", timeout=5) as answer:
        seen["health"] = answer.status
    browser = Browser(base)
    try:
        for label in LABELS:
            browser.open(label)
            browser.js(label, PROBE)
        names = browser.names
        browser.call("click", label="P0", selector="#home-create")
        browser.wait("P0", "/[A-Z0-9]{4}/.test(document.getElementById('lobby-code').textContent)")
        code = browser.js("P0", "document.getElementById('lobby-code').textContent.match(/[A-Z0-9]{4}/)[0]")
        for label in LABELS[1:]:
            browser.call("fill", label=label, selector="#join-code", text=code)
            browser.call("click", label=label, selector="#join-submit")
            browser.wait(label, "!document.getElementById('screen-lobby').hidden")
        browser.call("click", label="P0", selector='#lobby-modes button:has-text("Classic")')
        wait_until(lambda: lobby_of(names["P0"]).mode == "classic", "Classic chosen")

        roles = start_round(browser, "P0", LABELS, 0)
        seen["roles"] = roles
        fr = next(label for label, role in roles.items() if role == "Free Rider")
        hps = [label for label in LABELS if label != fr]
        classic = lobby_of(names[fr]).classic_round
        seen["server_roles"] = {label: classic.roles[names[label]] for label in LABELS}
        victim, caller, chatter, other = hps
        seen["labels"] = {"fr": fr, "victim": victim, "caller": caller, "chatter": chatter, "other": other}
        seen["before_unlock"] = {label: browser.js(label, "window.__button.frame") for label in LABELS}

        # Everybody around the Main Deck, so that every screenshot shows the button.
        around = {label: free_place_at(CENTRE, 60, near=(CENTRE[0] + dx, CENTRE[1] + dy))
                  for label, (dx, dy) in zip(hps, [(-60, 0), (60, 0), (-40, 45), (40, 45)])}
        for label, place in around.items():
            put(names[label], place)

        # The button unlocks on the server after 45 s; the pages hear it with
        # the next progress message, which the Free Rider's fail sends.
        clock.skip(EMERGENCY_DELAY_SECONDS + 1)
        fr_place = free_place_at(CENTRE, 60, near=(CENTRE[0], CENTRE[1] - 60))
        put(names[victim], (fr_place[0] + 3, fr_place[1]))
        put(names[fr], fr_place)
        standing_still(names[fr])
        press_fail(browser, fr)
        failed(browser, fr, names[victim])
        fail_at = classic.last_fail_at[names[fr]]
        put(names[victim], around[victim])

        # 1. The button on every page.
        for label in LABELS:
            browser.wait(label, "window.__button.frame && window.__button.frame.visible && window.__button.frame.drawn")
        seen["unlocked"] = {label: browser.js(label, "window.__button.frame") for label in LABELS}
        for label in LABELS:
            shot(browser, label, f"1_button_on_page_{label}")

        # 2. The Free Rider during his fail cooldown: away, then at the button.
        stand(browser, fr, fr_place)
        browser.wait(fr, "/^Let fail \\(\\d+ s\\)$/.test(document.querySelector('.use-button').textContent)", timeout=5000)
        away = use_button(browser, fr)
        away["distance"] = math.dist(fr_place, CENTRE)
        away["cooldown_left"] = fail_at + FAIL_COOLDOWN_SECONDS - server_main.seconds_now()
        seen["fr_away"] = away
        shot(browser, fr, "2a_free_rider_away_let_fail_countdown")
        fr_at_button = (CENTRE[0] - 20, CENTRE[1] + 10)
        stand(browser, fr, fr_at_button)
        browser.wait(fr, "document.querySelector('.use-button').textContent === 'E Emergency'", timeout=5000)
        near = use_button(browser, fr)
        near["distance"] = math.dist(fr_at_button, CENTRE)
        near["cooldown_left"] = fail_at + FAIL_COOLDOWN_SECONDS - server_main.seconds_now()
        seen["fr_near"] = near
        shot(browser, fr, "2b_free_rider_at_button_during_cooldown")
        states = {label: meeting_states(browser, label) for label in LABELS}
        sent = sent_emergencies(browser, fr)
        browser.call("press", label=fr, key="KeyE")
        wait_for_meeting_phase(browser, LABELS, "discussion", 1)
        for label in LABELS:
            browser.wait(label, "!document.getElementById('classic-meeting').hidden")
        seen["fr_meeting"] = {
            "sent": browser.js(fr, f"window.__sent.filter((r) => r.m.type === 'emergency').slice({sent}).map((r) => r.m)"),
            "cooldown_left_at_press": fail_at + FAIL_COOLDOWN_SECONDS - server_main.seconds_now(),
            "first_state": {label: first_meeting_state_since(browser, label, states[label])[0] for label in LABELS},
        }
        shot(browser, caller, "2c_meeting_called_by_free_rider_seen_by_high_performer")
        end_meeting(browser, clock, 1)
        seen["after_first_meeting"] = {"eliminated": sorted(classic.eliminated), "phase": classic.phase}

        # 3. Past the page from far away, and from 25.5 units.
        stand(browser, caller, SPAWN)
        seen["far_bypass"] = bypass(browser, caller)
        seen["far_bypass"]["distance"] = math.dist(SPAWN, CENTRE)
        shot(browser, caller, "3a_far_message_walk_to_the_red_button")
        just_out = straight_line_to_button(USE_RANGE + 0.5)
        stand(browser, caller, just_out)
        seen["just_out_hint"] = use_button(browser, caller)
        seen["just_out_bypass"] = bypass(browser, caller)

        # 4. The ghost on the button.
        stand(browser, victim, CENTRE)
        seen["ghost_hint"] = use_button(browser, victim)
        seen["ghost_press"] = press_and_watch(browser, victim)
        shot(browser, victim, "4_ghost_on_the_button_no_hint")
        seen["ghost_bypass"] = bypass(browser, victim)
        put(names[victim], around[victim])

        # 5. A living High Performer: walking up with W, then 26 and 25 units.
        start = straight_line_to_button(USE_RANGE + 20)
        stand(browser, caller, start)
        seen["walk_start_hint"] = use_button(browser, caller)
        browser.js(caller, WATCH_HINT.replace("NAME", json.dumps(names[caller])))
        browser.call("down", label=caller, key="KeyW")
        try:
            browser.wait(caller, "window.__hintFlip !== null", timeout=5000)
        finally:
            browser.call("up", label=caller, key="KeyW")
        standing_still(names[caller])
        flip = browser.js(caller, "window.__hintFlip")
        told = browser.js(caller, f"""window.__received
            .filter((r) => r.m.type === 'positions' && r.m.players.some((p) => p.name === {json.dumps(names[caller])}))
            .map((r) => [r.t, r.m.players.find((p) => p.name === {json.dumps(names[caller])})])
            .map(([t, p]) => [t, p.x, p.y])""")
        first_in = next(t for t, x, y in told if t >= flip["armed"] and math.dist((x, y), CENTRE) <= USE_RANGE)
        last_out = max(t for t, x, y in told if t <= flip["t"] and math.dist((x, y), CENTRE) > USE_RANGE)
        seen["walk"] = {"told_at_flip": flip["told"], "distance": math.dist(flip["told"], CENTRE),
                        "ms_after_first_told_in_range": flip["t"] - first_in,
                        "flip_after_last_told_out": flip["t"] > last_out,
                        "stopped_at": position(names[caller])}
        shot(browser, caller, "5a_walked_up_hint_shows")

        outside = straight_line_to_button(USE_RANGE + 1)
        stand(browser, caller, outside)
        seen["at_26"] = use_button(browser, caller)
        seen["at_26_press"] = press_and_watch(browser, caller)
        shot(browser, caller, "5b_26_units_no_hint")
        edge = straight_line_to_button(USE_RANGE)
        stand(browser, caller, edge)
        seen["at_25"] = use_button(browser, caller)
        shot(browser, caller, "5c_25_units_hint")
        states = {label: meeting_states(browser, label) for label in LABELS}
        errors = error_count(browser, caller)
        sent = sent_emergencies(browser, caller)
        meetings_before = classic.meeting_count
        browser.call("press", label=caller, key="KeyE")
        browser.call("press", label=caller, key="KeyE")
        wait_for_meeting_phase(browser, LABELS, "discussion", 2)
        for label in LABELS:
            browser.wait(label, "!document.getElementById('classic-meeting').hidden")
        time.sleep(0.8)
        seen["hp_meeting"] = {
            "sent": sent_emergencies(browser, caller) - sent,
            "errors": errors_since(browser, caller, errors),
            "first_state": {label: first_meeting_state_since(browser, label, states[label])[0] for label in LABELS},
            "meetings_started": classic.meeting_count - meetings_before,
            "triggers_since": {
                label: sorted({m["trigger_player_id"] for m in first_meeting_state_since(browser, label, states[label])})
                for label in LABELS
            },
        }

        # Chat in the discussion: the caller and one more living player write.
        lines = {caller: "I pressed the red button.", chatter: "Who was at the deck?"}
        for label, text in lines.items():
            browser.call("fill", label=label, selector="#classic-chat-input", text=text)
            browser.call("click", label=label, selector="#classic-chat-send")
            time.sleep(0.3)
        for label in LABELS:
            browser.wait(label, f"""(() => {{
                const last = window.__received.filter((r) => r.m.type === 'meeting_state').pop();
                return last && last.m.messages.length >= 2;
            }})()""")
        seen["chat"] = {
            label: browser.js(label, "window.__received.filter((r) => r.m.type === 'meeting_state').pop().m.messages")
            for label in LABELS
        }
        seen["chat_written_by"] = {label: names[label] for label in lines}
        seen["ghost_chat_input"] = browser.js(victim, "document.getElementById('classic-chat-input').disabled")
        seen["phase_before_45_s"] = lobby_of(names[caller]).meeting["phase"]
        shot(browser, caller, "5d_meeting_discussion_chat_caller")
        shot(browser, victim, "5e_meeting_discussion_chat_ghost")
        clock.skip(DISCUSSION_SECONDS + 1)
        wait_for_meeting_phase(browser, LABELS, "voting", 2)
        time.sleep(0.5)
        seen["voting"] = {
            label: browser.js(label, """(() => {
                const last = window.__received.filter((r) => r.m.type === 'meeting_state').pop().m;
                const options = document.getElementById('classic-vote-options');
                return { phase: last.phase, reason: last.reason, seconds_left: last.seconds_left,
                         options_shown: Boolean(options) && !options.hidden,
                         chat_disabled: document.getElementById('classic-chat-input').disabled };
            })()""")
            for label in LABELS
        }
        shot(browser, caller, "5f_vote_open_after_45_s")

        # 6. Nobody but the Free Rider was told or shown his role.
        seen["leaks"] = {label: leaks_of_the_free_rider(browser, label, names[fr]) for label in hps}
        seen["fr_own_role"] = browser.js(fr, "window.__received.filter((r) => r.m.type === 'classic_role').map((r) => r.m.role)")
        seen["problems"] = browser.close()
    except BaseException:
        write_down(seen)
        try:
            browser.close()
        except Exception:
            pass
        raise
    seen["names"] = dict(browser.names)
    write_down(seen)
    return seen


def test_the_server_answers_health(played):
    assert played["health"] == 200


def test_five_players_have_one_free_rider(played):
    assert sorted(played["roles"].values()).count("Free Rider") == 1
    assert sorted(played["server_roles"].values()).count("FR") == 1


def test_after_45_s_every_page_draws_the_button(played):
    assert all(frame is None or frame["visible"] is False for frame in played["before_unlock"].values())
    for label, frame in played["unlocked"].items():
        assert frame["visible"] and frame["drawn"], (label, frame)


def test_the_free_rider_sees_let_fail_with_seconds_away_from_the_button(played):
    away = played["fr_away"]
    assert away["distance"] > USE_RANGE
    assert away["cooldown_left"] > 0
    assert away["failLook"] is True
    assert away["text"].startswith("Let fail (") and away["text"].endswith(" s)"), away


def test_the_free_rider_at_the_button_during_his_cooldown_sees_an_enabled_e_emergency(played):
    near = played["fr_near"]
    assert near["distance"] <= USE_RANGE
    assert near["cooldown_left"] > 0
    assert near == {**near, "text": "E Emergency", "disabled": False, "failLook": False}


def test_e_of_the_free_rider_at_the_button_opens_the_meeting_for_all(played):
    meeting = played["fr_meeting"]
    assert meeting["sent"] == [{"type": "emergency"}]
    assert meeting["cooldown_left_at_press"] > 0
    fr_name = played["names"][played["labels"]["fr"]]
    for label, state in meeting["first_state"].items():
        assert state["phase"] == "discussion" and state["reason"] == "emergency", (label, state)
        assert state["trigger_player_id"] == fr_name
    assert played["after_first_meeting"]["phase"] != "meeting"


def test_a_call_from_far_away_gets_walk_to_the_red_button_and_no_meeting(played):
    far = played["far_bypass"]
    assert far["distance"] > USE_RANGE
    assert [(e["code"], e["message"]) for e in far["errors"]] == [("emergency_out_of_reach", OUT_OF_REACH)]
    assert far["shown"] == {"hidden": False, "text": OUT_OF_REACH}
    assert set(far["meetings"].values()) == {0}
    assert far["server_meeting"] is False


def test_a_call_from_25_5_units_is_out_of_reach_too(played):
    assert played["just_out_hint"]["text"] != "E Emergency"
    out = played["just_out_bypass"]
    assert [(e["code"], e["message"]) for e in out["errors"]] == [("emergency_out_of_reach", OUT_OF_REACH)]
    assert set(out["meetings"].values()) == {0}


def test_a_ghost_on_the_button_sees_no_e_emergency(played):
    assert played["ghost_hint"]["text"] != "E Emergency"
    assert played["ghost_press"]["sent"] == 0
    assert set(played["ghost_press"]["meetings"].values()) == {0}
    codes = [e["code"] for e in played["ghost_bypass"]["errors"]]
    assert codes == ["emergency_rejected"]
    assert set(played["ghost_bypass"]["meetings"].values()) == {0}


def test_walking_up_with_w_shows_the_hint_within_25_units(played):
    assert played["walk_start_hint"]["text"] != "E Emergency"
    walk = played["walk"]
    # The page decides from the last position it was told: within 25 units,
    # and within a few frames of the first position within 25 units.
    assert walk["distance"] <= USE_RANGE, walk
    assert walk["flip_after_last_told_out"], walk
    assert walk["ms_after_first_told_in_range"] < 250, walk


def test_26_units_away_no_hint_and_e_does_nothing(played):
    assert played["at_26"]["text"] != "E Emergency"
    assert played["at_26_press"]["sent"] == 0
    assert set(played["at_26_press"]["meetings"].values()) == {0}


def test_25_units_away_the_hint_shows_and_e_opens_one_discussion_for_all(played):
    assert played["at_25"] == {"text": "E Emergency", "disabled": False, "failLook": False}
    meeting = played["hp_meeting"]
    caller_name = played["names"][played["labels"]["caller"]]
    assert len(meeting["first_state"]) == 5
    for label, state in meeting["first_state"].items():
        assert state["phase"] == "discussion" and state["reason"] == "emergency", (label, state)
        assert state["trigger_player_id"] == caller_name
        assert DISCUSSION_SECONDS - 1 <= state["seconds_left"] <= DISCUSSION_SECONDS
    # E twice quickly: one meeting; the page sent at most a second call, which was refused.
    assert meeting["meetings_started"] == 1
    assert all(triggers == [caller_name] for triggers in meeting["triggers_since"].values()), meeting["triggers_since"]
    assert 1 <= meeting["sent"] <= 2
    assert all(e["code"] == "emergency_rejected" for e in meeting["errors"]), meeting["errors"]


def test_the_chat_works_in_the_discussion_on_every_page(played):
    written = {played["chat_written_by"][label] for label in played["chat_written_by"]}
    for label, messages in played["chat"].items():
        assert {m["player_id"] for m in messages} == written, (label, messages)
        assert {m["text"] for m in messages} == {"I pressed the red button.", "Who was at the deck?"}
    assert played["ghost_chat_input"] is True
    assert played["phase_before_45_s"] == "discussion"


def test_after_45_s_of_discussion_the_vote_opens_on_every_page(played):
    for label, state in played["voting"].items():
        assert state["phase"] == "voting" and state["reason"] == "emergency", (label, state)
        assert state["chat_disabled"] is True


def test_no_other_page_learns_who_the_free_rider_is(played):
    assert played["fr_own_role"] == ["FR"]
    for label, leaks in played["leaks"].items():
        assert leaks == [], (label, leaks)


def test_no_console_error_or_warning_on_any_page(played):
    assert played["problems"] == []
