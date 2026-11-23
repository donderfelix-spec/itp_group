# Walkthrough: how the code fits together

A tour of the code for somebody who has the repository open. It takes about ten minutes. What the game is, who built it and how to run it are in the [README](../README.md); the map of every folder is in [game/README.md](README.md). Function names below are the real ones; search for them in the file named next to them.

## 1. One message, end to end: pressing R at an F-sheet

The Free Rider has failed Tiago. An F-sheet lies where he stood. Mara walks up to it and presses R.

**1. The key (browser, area 1).** In `client/js/world/world.js`, `onKeyDown` sees the key `KeyR` (`isReportKey`) and calls `reportSheetInRange`. That asks `nearestSheetInRange` for the nearest F-sheet that is not reported yet and lies within `REPORT_RANGE` (8 map units, the same number as `rules.REPORT_RANGE`) of the player's position as the server last sent it. Clicking the button “R Report” does the same (`onReportButtonClick`); `updateReportButton` shows that button only to a living player next to a sheet (`reportVisible` in `client/js/classic/hud-actions.js`). Without a sheet in range nothing happens and no message is sent.

**2. The message (browser, area 2).** `reportSheetInRange` calls the handler that `client/js/main.js` registered with `setReportHandler`: `requestReport`. It sends `{type: "report", sheet_id, position}` with `Game.net.send` from `client/js/net.js`, only in a running Classic round and only once until an answer comes (`reportIsOnItsWay`; `reportAnswered` clears it on `meeting_state` or `error`). So a double click sends one report (M3-3.21).

**3. The message check (server, area 2).** `game_socket` in `server/main.py` hands every frame to `read_messages`, which first calls `parse_client_message` in `server/protocol.py`. Nothing else sees the message before that. It refuses a message over 2048 bytes, text that is not a JSON object, an unknown type, an extra or a missing field. For `report`, the table `CLIENT_MESSAGES` names two checks: `_check_sheet_id` (text of the form `f-sheet-` and a number, else “That F-sheet could not be identified.”) and `_check_position` (exactly `x` and `y`, finite numbers, else “That position could not be read.”). Every refusal is a `ProtocolError`; `read_messages` sends it back to this connection only, with the text from DESIGN.md, section 9, and the connection stays open.

**4. The permission check (server, area 2).** `read_messages` passes the checked message to `answer_report_message`. It asks, in this order: is the connection signed in, is the player in a lobby, is a Classic round running, is the player hidden (`blocked_while_hidden` in `server/classic/hiding.py`: “Leave your hiding spot first.”), and is the position the browser claims within 2 map units of where the server has the player (`lobby.walkers.position_of`)? The server then goes on with its own position, not the browser's.

**5. The plain rule (area 3).** `ClassicRound.report` in `server/classic/round.py` calls `report_sheet` in `rules.py`. `report_sheet` uses `can_report`: no meeting running, the player is a living High Performer or Free Rider (a ghost is refused), this sheet has not started a meeting before (`report:<sheet id>` is not in `meeting_triggers`), and the player stands within `REPORT_RANGE` of the sheet. Then `start_meeting` returns a new state; nothing is changed in place, and there is no clock or network inside. Back in `ClassicRound.report`, hiding ends (`end_all_hiding`) and `start_discussion` in `server/classic/meeting.py` opens the timed discussion. A refused rule raises `ValueError`, which `answer_report_message` turns into “You cannot report that F-sheet right now. Stand at the sheet and try again.”

**6. The answers, and who gets what (rule 1).** A refusal goes only to the reporter. On success `answer_report_message` tells each player who was hidden that hiding ended (`tell_hiding`), closes every open minigame (`close_every_open_task` sends `station_closed` only to players who had one open), and `tell_meeting_state` sends the same `meeting_snapshot` (from `server/classic/meeting.py`) to every member, living or ghost. The snapshot holds the phase, the time left, the living and the ghosts, who reported which sheet, the chat and the votes. It holds no roles; the only role it ever names is that of the player voted out, once the vote has a result.

**7. What the browser draws (area 3).** `client/js/classic/meeting.js` listens for `meeting_state` (`show`): it marks the sheet as reported (`markBloodSheetReported` in `world.js`, so R does nothing there any more), opens the meeting window, stops the own character from walking (`holdTheCharacter`) and draws the players, the chat and the vote buttons.

**Tests for each step**

| Step | Test |
|---|---|
| R and the button send `report` | `tests/test_classic_triggers_area3.py` (`test_client_wires_report_and_emergency_keys_to_server_actions`), `tests/test_classic_report_button_area3.py` |
| One report per press | `tests/test_classic_report_once.py` (`test_a_report_is_sent_once_until_its_answer_in_node`) |
| Message check | `tests/test_protocol.py` (`test_every_new_message_is_accepted_and_returned_exactly`), `tests/test_protocol_report_position.py` (`test_the_connection_stays_open_after_a_huge_number`) |
| Permission check | `tests/test_classic_report_and_fail_ranges.py` (`test_report_over_the_websocket_at_eight_accepted_and_just_beyond_refused`), `tests/test_hide_with_e.py` (`test_a_hidden_free_rider_must_step_out_to_fail_report_or_call`) |
| Plain rule | `tests/test_rules.py` (`test_ghost_cannot_report_or_call_emergency`, `test_report_starts_meeting_keeps_sheet_and_cannot_be_repeated`) |
| Answers and who gets them | `tests/test_classic_meeting_sheets_area3.py` (`test_meeting_snapshot_names_the_reported_sheet`), `tests/test_classic_rule1_messages.py` (`test_every_classic_message_reaches_only_who_may_know_it`) |
| In real browsers | `tests/test_play_classic_report_after_meeting_and_new_round.py` |

## 2. A second trace: a task station and its minigame (area 4)

1. **E at a station.** `useActionInRange` in `world.js` decides what E means here (leave hiding, hide, emergency or a station); for a station, `useStationInRange` calls `openStation` in `main.js`, which sends `{type: "open_station", station}` with `Game.net.ask` (one action at a time).
2. **Checks.** `parse_client_message` checks the station number (`_check_station`). `answer_task_message` in `server/main.py` checks sign-in and lobby, then `handle_open_station` refuses a Free Rider (“Free Riders cannot complete tasks.”) and any opening during a meeting. The rest is the plain rule `RoundTasks.open` in `server/modes/tasks.py`, with its checks in a fixed order (`_why_not_open`): the station exists, the player needs it (in Classic only the one active task, `active_task` in `server/classic/round.py`; in Duel only the next station of the route), no other task is open, and the player stands in range (`station_in_range` in `server/world/stations.py`).
3. **Content from the server.** `RoundTasks.open` draws the content with the station's `make_content` (the table `MINIGAMES` in `server/modes/minigames.py`, one file per minigame), so the browser cannot pick an easy task. `station_opened` goes to this player only, and the player stands still while the task is open.
4. **Playing.** `whenStationOpened` in `main.js` calls `Game.minigames.open` in `client/js/minigames/frame.js`, which builds the window and starts the minigame registered for that `kind` (for example `client/js/minigames/brew_order.js`). When the player solves it, the minigame calls `done()`, and the frame sends `finish_station` (`reportDone`, `sendDone`).
5. **Who decides that it counts: the server.** `handle_finish_station` calls `RoundTasks.finish`: a task must be open, and it must have been open for at least the minigame's `min_seconds`; otherwise “That was too fast. Try again.” and the window closes. The server does not replay the minigame; that is the trade-off of S-19 and S-93. Only then `count_for_the_mode` counts it: in Classic `ClassicRound.station_done`, in Duel `Duel.station_done`. The player gets `station_done` (in Classic with their next active station, to them alone); everybody gets the new group progress (`tell_round_news`, `tell_classic_progress`) or the Duel progress.

Tests: `tests/test_tasks.py` (`test_just_under_the_minimum_time_is_too_fast`, `test_one_step_beyond_the_range_is_too_far`), `tests/test_server_tasks.py` (`test_finishing_too_soon_sends_the_error_and_then_closes`), `tests/test_classic_one_active_task.py`, and in real browsers `tests/test_play_classic_task_card_end_to_end.py`.

## 3. The four areas

**Area 1, Campus and characters (Hanna).** The map, walking and collision, the camera, limited vision, the drawing of rooms and characters.

- `client/js/world/campus.json`: the one map file (rooms, walls, furniture, stations, hiding spots), read by the browser and by the server.
- `server/world/movement.py`: walking as plain functions; `step` moves a player for a given time and stops them at solids.
- `client/js/world/world.js`: the map in the browser: keys, camera, drawing the players, the key hints and buttons.
- Rule worth showing: `positions_in_sight` in `server/world/visibility.py`: who a living Classic player is sent (within the vision range, no wall in between).
- Rejected case: `test_sight_stops_at_its_range_and_opaque_walls` in `tests/test_classic_vision.py`.
- How to explain it: “The map exists once, in campus.json; the server moves everybody with the same walls the browser draws, and in Classic it only sends you the players you can see.”

**Area 2, Network, lobby, accounts, foundation (Felix).** The server, the connection, the message checks, lobbies, accounts and statistics, CI and hosting.

- `server/main.py`: the web server and the WebSocket; the handlers that check permissions and connect messages to the rules.
- `server/protocol.py`: the check of every message from the browser, and the fixed texts of every refusal (`REJECTIONS`).
- `server/net/lobbies.py`: lobbies, host, characters, the countdown, as plain rules.
- Rule worth showing: `mode_after_a_join` in `server/net/lobbies.py`: a Solo lobby that gets a second player plays Duel (S-203).
- Rejected case: `test_a_field_the_server_does_not_expect_is_rejected` in `tests/test_protocol.py`.
- How to explain it: “Every message goes through protocol.py first, then a handler in main.py asks whether this player may do it now, and only then a rule function decides.”

**Area 3, Classic rules (Laurin).** Roles, failing, reporting, meetings, chat and votes, hiding, the winner.

- `rules.py`: the Classic rules as plain functions: roles, tasks, failing, reporting, the winner.
- `server/classic/meeting.py`: the meeting: discussion clock, chat, votes, Skip, the result, and the snapshot everybody gets.
- `client/js/classic/meeting.js`: the meeting window: chat, vote buttons, result.
- Rule worth showing: `check_winner` in `rules.py`: the High Performers win at full progress or with no Free Rider left, the Free Riders once the living Free Riders are at least as many as the living High Performers. The High Performers' conditions are checked first.
- Rejected case: `test_ghost_cannot_report_or_call_emergency` in `tests/test_rules.py`.
- How to explain it: “rules.py takes the state, the time and the random choices as arguments and returns a new state, so every rule can be tested without a server.”

**Area 4, Minigames and other modes (Lennart).** The frame for minigames, the eleven minigames, Duel and Solo.

- `server/modes/tasks.py`: the frame: who has which task open, the range and the minimum time.
- `server/modes/minigames.py`: which minigame is at which station; each draws its content with a plain function.
- `client/js/minigames/frame.js`: the minigame window in the browser and the `finish_station` it sends.
- Rule worth showing: `draw_routes` in `server/modes/duel.py`: every Duel player gets their own route of three stations, of about the same walking length (S-94).
- Rejected case: `test_just_under_the_minimum_time_is_too_fast` in `tests/test_tasks.py`.
- How to explain it: “The browser plays the minigame, but the server draws its content and decides whether ‘done’ counts.”

## 4. The five rules that shape the code

The rules are in [AGENTS.md](../AGENTS.md). One place where each can be seen:

1. **The server decides.** `tell_positions` in `server/main.py`: each player is sent only the positions they may know (no ghosts for the living, only those in sight, no hidden Free Rider for a living High Performer), and `you_are_fr` goes only to a Free Rider (`tell_classic_start`).
2. **Every message is checked.** `parse_client_message` and the table `CLIENT_MESSAGES` in `server/protocol.py`; `test_the_message_table_holds_exactly_the_agreed_types` in `tests/test_protocol.py` pins the list.
3. **Every permission is checked.** `answer_report_message` in `server/main.py` (section 1, step 4), or `_why_not_open` in `server/modes/tasks.py`.
4. **Rules are plain functions.** `can_report` and `report_sheet` in `rules.py`; `RoundTasks.finish(name, now)` gets the time as an argument.
5. **No secrets in the repository.** `server/main.py` reads `DATABASE_URL` from the environment (`make_account_store(os.environ.get("DATABASE_URL"))`); `.gitignore` keeps `.env` files out, and `tests/conftest.py` removes `DATABASE_URL` so tests never touch a real database.

## 5. Where decisions and work are written down

- [DECISIONS.md](DECISIONS.md): every decision, numbered S-01, S-02, …, with its date, its reason and who decided.
- [TODO.md](TODO.md): the to-dos by milestone and area, ticked when done.
- [FEATURES.md](FEATURES.md): every feature and its status.
- [WORKFLOW.md](WORKFLOW.md): how a to-do goes from the list to `main` with the coder, reviewer and tester agents (`.claude/agents/`).
- Pull requests on GitHub: every change reached `main` through one (two exceptions on 2026-11-22, named in the README).

**One real example: hiding with E.** Felix wanted the Free Rider to hide on purpose instead of just by standing in a hiding spot (recorded on 2026-11-22). That became the to-do **M3-1.6** in TODO.md and the decisions **S-191** (who may hide, how it ends, what is refused while hidden) and **S-192** (a hidden Free Rider is sent to no living High Performer; the others see a crossed-out eye). It was built on the branch `game/m3-hide-with-e` (commits “The Free Rider hides on purpose with E (M3-1.6, S-191)” and “A hidden Free Rider is sent to no High Performer; others see a crossed-out eye (S-192)”), with the plain rules in `server/classic/hiding.py`, the server tests in `tests/test_hide_with_e.py` and a play test with four browsers (`tests/test_play_hide_with_e.py`). It reached `main` as **pull request #100** on 2026-11-22, together with M3-1.5 (hiding spots as map objects, S-190).

## 6. Try it in two minutes

1. Start the server as the [README](../README.md#run-it-locally) says and open http://localhost:8000.
2. Click “Play as guest”, then “Create lobby”. A new lobby starts in Solo (S-203): “Start game” plays a Duel route alone.
3. Open a second browser window, “Play as guest”, type the four-letter code and “Join”. The lobby switches to Duel; the host clicks “Start game”. Walk with WASD, press E at the pulsing station.
4. For Classic open four windows (four players at least), and the host chooses “Classic”. M opens the campus map.

## 7. What we would do next

- Let a player whose connection dropped return to the running round (today they wait until it is over, S-109).
- Send the victim's position after a fail only to the players who see it (M3-3.25), and show the voted-out character drifting out to sea (M3-3.5).
- Run the browser play tests in CI too, not only on our machines.
