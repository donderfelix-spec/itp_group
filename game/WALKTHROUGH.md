# Walkthrough: how the project is built

A tour of the whole project for somebody who has the repository open: every one of us should be able to answer for every part of it, not only for the area we own. Reading it takes about fifteen minutes. What the game is, who built it and how to run it are in the [README](../README.md); the map of every folder is in [game/README.md](README.md). Function names below are the real ones; search for them in the file named next to them.

## 1. The whole in one picture

One server (Python, FastAPI) holds everything that matters in its memory: who is signed in, the lobbies, the running rounds. Every browser keeps one WebSocket connection to it (`client/js/net.js`, `/ws` in `server/main.py`). The browser only sends what its player wants to do (walk, open a station, report, vote) and draws what the server tells it. Every message from a browser takes the same path: `parse_client_message` in `server/protocol.py` checks its shape, a handler in `server/main.py` checks whether this player may do it now, and a plain rule function (in `rules.py`, `server/classic/`, `server/modes/`, `server/world/`, `server/net/`, `server/accounts/`) decides what happens. The handler then sends each player only what that player may know. Walking is the one exception to “one message, one answer”: `move` only sets a direction (`answer_move_message`), and the tick (`run_ticks`, 15 times a second) moves everybody with `step` from `server/world/movement.py` and sends the positions (`tell_positions`). Accounts and statistics are the only data that outlive the server; they live in Postgres (section 6).

The two traces below follow this path for two real actions.

## 2. One message, end to end: pressing R at an F-sheet

The Free Rider has failed Tiago. An F-sheet lies where he stood. Mara walks up to it and presses R.

**1. The key (browser, area 1).** In `client/js/world/world.js`, `onKeyDown` sees the key `KeyR` (`isReportKey`) and calls `reportSheetInRange`. That asks `nearestSheetInRange` for the nearest F-sheet that is not reported yet and lies within `REPORT_RANGE` (8 map units, the same number as `rules.REPORT_RANGE`) of the player's position as the server last sent it. Clicking the button “R Report” does the same (`onReportButtonClick`); `updateReportButton` shows that button only to a living player next to a sheet (`reportVisible` in `client/js/classic/hud-actions.js`). Without a sheet in range nothing happens and no message is sent. Mara's browser knows where the sheet lies only because the server told it when the place came into her sight: `classic_fail` carries the place only to the Free Rider, the ghosts and those who see it, and the tick sends `classic_sheet` to the others later (`tell_classic_sheets`, `sheets_to_tell` in `server/classic/sheets.py`, S-202).

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

## 3. A second trace: a task station and its minigame (area 4)

1. **E at a station.** `useActionInRange` in `world.js` decides what E means here (leave hiding, hide, emergency or a station); for a station, `useStationInRange` calls `openStation` in `main.js`, which sends `{type: "open_station", station}` with `Game.net.ask` (one action at a time).
2. **Checks.** `parse_client_message` checks the station number (`_check_station`). `answer_task_message` in `server/main.py` checks sign-in and lobby, then `handle_open_station` refuses a Free Rider (“Free Riders cannot complete tasks.”) and any opening during a meeting. The rest is the plain rule `RoundTasks.open` in `server/modes/tasks.py`, with its checks in a fixed order (`_why_not_open`): the station exists, the player needs it (in Classic only the one active task, `active_task` in `server/classic/round.py`; in Duel only the next station of the route), no other task is open, and the player stands in range (`station_in_range` in `server/world/stations.py`).
3. **Content from the server.** `RoundTasks.open` draws the content with the station's `make_content` (the table `MINIGAMES` in `server/modes/minigames.py`, one file per minigame), so the browser cannot pick an easy task. `station_opened` goes to this player only, and the player stands still while the task is open.
4. **Playing.** `whenStationOpened` in `main.js` calls `Game.minigames.open` in `client/js/minigames/frame.js`, which builds the window and starts the minigame registered for that `kind` (for example `client/js/minigames/brew_order.js`). When the player solves it, the minigame calls `done()`, and the frame sends `finish_station` (`reportDone`, `sendDone`).
5. **Who decides that it counts: the server.** `handle_finish_station` calls `RoundTasks.finish`: a task must be open, and it must have been open for at least the minigame's `min_seconds`; otherwise “That was too fast. Try again.” and the window closes. The server does not replay the minigame; that is the trade-off of S-19 and S-93. Only then `count_for_the_mode` counts it: in Classic `ClassicRound.station_done`, in Duel `Duel.station_done`. The player gets `station_done` (in Classic with their next active station, to them alone); everybody gets the new group progress (`tell_round_news`, `tell_classic_progress`) or the Duel progress.

Tests: `tests/test_tasks.py` (`test_just_under_the_minimum_time_is_too_fast`, `test_one_step_beyond_the_range_is_too_far`), `tests/test_server_tasks.py` (`test_finishing_too_soon_sends_the_error_and_then_closes`), `tests/test_classic_one_active_task.py`, and in real browsers `tests/test_play_classic_task_card_end_to_end.py`.

## 4. The four areas

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

## 5. The five rules that shape the code

The rules are in [AGENTS.md](../AGENTS.md). One place where each can be seen:

1. **The server decides.** `tell_positions` in `server/main.py`: each player is sent only the positions they may know (no ghosts for the living, only those in sight, no hidden Free Rider for a living High Performer), and `you_are_fr` goes only to a Free Rider (`tell_classic_start`).
2. **Every message is checked.** `parse_client_message` and the table `CLIENT_MESSAGES` in `server/protocol.py`; `test_the_message_table_holds_exactly_the_agreed_types` in `tests/test_protocol.py` pins the list.
3. **Every permission is checked.** `answer_report_message` in `server/main.py` (section 2, step 4), or `_why_not_open` in `server/modes/tasks.py`.
4. **Rules are plain functions.** `can_report` and `report_sheet` in `rules.py`; `RoundTasks.finish(name, now)` gets the time as an argument.
5. **No secrets in the repository.** `server/main.py` reads `DATABASE_URL` from the environment (`make_account_store(os.environ.get("DATABASE_URL"))`); `.gitignore` keeps `.env` files out, and `tests/conftest.py` removes `DATABASE_URL` so tests never touch a real database.

## 6. Questions we expect, and the answers

**Where is the data stored?**
Accounts and statistics are in Postgres at Supabase, in two tables: `accounts` (`server/accounts/store.py`, `PostgresAccountStore`) and `account_statistics` (`server/accounts/statistics_store.py`). The server finds the database through the environment variable `DATABASE_URL`, which is set only in Render's settings (S-39). A password is stored only as an Argon2 hash (`Argon2Hasher` in `server/accounts/service.py`, S-38). Both tables have row level security switched on with no policy, so Supabase's public Data API sees no rows. Without `DATABASE_URL` (locally, in the tests) the same methods run on `MemoryAccountStore` and `MemoryStatisticsStore` (`make_account_store`, `make_statistics_store`). Lobbies, rounds, positions and who is signed in live only in the server's memory (`Lobbies`, `Sessions`; S-32, S-39): a round lasts minutes and need not survive a restart. The browser stores nothing about the player: no cookie, no `localStorage`, no token. The one thing it keeps is a flag in `sessionStorage` that the keyboard notice was closed with “Play anyway” (`client/js/keyboard_notice.js`, S-219); it is gone when the tab is closed. Being signed in belongs to the connection (S-78): after a reload a player signs in again. After a lost connection the page keeps the lobby code only in a variable, not in storage (S-109).
*Limit:* a restart or a new deploy ends every lobby and round. *Could change:* keep lobbies in a shared store such as Redis, or let a running round wait for a player who reconnects.

**What do the tests cover, and what not?**
On 2026-11-23 there are about 6,900 test cases in `tests/`. About 940 of them are in the 35 files that drive Chromium; without Playwright most of those are skipped and the rest pass. They work on four levels:
- the plain rule functions, with the time and the random choices passed in (`tests/test_rules.py`, `tests/test_tasks.py`, `tests/test_movement.py`);
- the real server over real WebSocket connections with FastAPI's test client, several players at once (`tests/test_server_tasks.py`, `tests/test_classic_rule1_messages.py`);
- the real client files run in Node.js (`*_in_node.js`);
- play tests that drive real Chromium pages with Playwright (about 35 files, most of them `tests/test_play_*.py`).
The message types are tested for accepted, rejected and edge cases (rule 2). The CI (`.github/workflows/ci.yml`) runs pytest, `node --check` and `pip-audit` on every pull request and on `main`; it has no Playwright, so it skips the browser plays. They run after each merge to `main` and when started by hand in `.github/workflows/browser-plays.yml`, with Playwright and Chromium (S-220): every `tests/test_play_*.py` and the six other files that drive Chromium, and a failed test is run once more on its own.
*Not covered:*
- the deployed site on Render;
- the real Supabase database: `tests/conftest.py` removes `DATABASE_URL`, and the Postgres stores are tested with fake connections;
- the browser play tests on pull requests: they run only after the merge to `main`, so a pull request can break one without a red check;
- browsers other than Chromium, phones and touch;
- real network delay (only simulated, `tests/test_play_smooth_delivery.py`);
- many lobbies or players at once: there is no load test.

**What happens if the service the game depends on is unavailable?**
Our only outside service is the database. We tried it with the server pointed at a closed port and at a port that never answers, and against a real local Postgres that we froze in the middle of a call or cut off from the network (S-211):
- The server starts anyway: the stores connect only when they are first needed.
- Sign-up and log-in answer “Accounts are unavailable right now. You can still play as a guest.” (`accounts_unavailable`). It comes at once when the database refuses, and after 5 seconds when it does not answer (`CONNECT_TIMEOUT_SECONDS`; a query may run at most 5 seconds, `SET_STATEMENT_TIMEOUT`). If the network dies in the middle of a call, our end notices within about 5 seconds (`SOCKET_OPTIONS`, libpq's keepalive and `tcp_user_timeout`); if the database is reachable but stuck, the call is cut off 10 seconds after it connected (`CallDeadline` in `server/accounts/store.py`). A down database is not counted as a wrong password (`handle_log_in`).
- Profile and leaderboard answer “Statistics are unavailable right now.”
- Guests sign in, create lobbies and play every mode at the same moment. The database runs on four worker threads (`account_workers`), never on the loop that runs the game; at most two of them hash a password at once (`HASHES_AT_ONCE`), because one Argon2 hash needs 64 MiB.
- The result of a finished round is written only after the players were told (`write_result_later`). If that write fails, the round has ended normally and only its statistics are lost (`tests/test_server_statistics.py`, `test_a_store_that_fails_does_not_keep_the_round_from_ending`).
- The log gets one fixed line per failure, never the address or the password (`problem_log_line`).
*Limits:* with a database that hangs, every account action holds one of the four workers for up to about 15 seconds (5 to connect, then 10 for the call), so more than four log-ins at once still wait in turn. A known risk we accept on purpose: if the database fails exactly while a finished round is being saved, that round's statistics are lost and are not written again. A retry is not safe, because the first write may have arrived after all and the round would then count twice. *Could change:* give every round an id with a unique constraint, so that the database refuses a second copy and a write can be repeated safely (open to-do M3-2.9).

**Why was it built this way?**
- Python with FastAPI on the server, because the course works with Python (S-29, replacing Node.js in S-15).
- WebSockets, because several players need a permanent connection both ways (S-15, S-29).
- Plain JavaScript on a canvas, without a framework or a build step: few dependencies and code everybody can read (S-17); the course asks for approval of JavaScript frameworks (S-42).
- The server decides everything that counts and tells each browser only what its player may know, so a changed browser cannot cheat (S-16).
- Rules as plain functions, so pytest can test them in seconds (S-30).
- Minigames are played in the browser, with content drawn by the server and a minimum time (S-19, S-93): replaying every minigame on the server would cost too much for a game among friends.
- Rounds in memory, data in Postgres (S-32, S-39).
- Coding agents with fixed roles (S-22): the reviewer sees only the brief and the change (S-24), every loop stops after three rounds (S-25), and a person approves every pull request (S-26). The rules every agent follows are in [AGENTS.md](../AGENTS.md) (S-35), and every decision is written down with who made it.

**What are the limits, and how could it change?**
The README lists the known limitations: no return into a running round, rounds lost on a restart, attempt limits per connection and none on sign-up, everybody learns at once who was failed, no drifting out to sea, no browser plays on pull requests. Next steps we would take:
1. Let a player who lost the connection return to the running round (S-109 today only rejoins the lobby).
2. Show the character voted out drifting out to sea instead of a line of text (M3-3.5).
3. Count failed log-ins per account or address, not per connection.
4. Run the Playwright play tests on every pull request too, and add a test against a real Postgres.

**How is it secured?**
- Input: every message is checked for size, shape and allowed values in `server/protocol.py` before any game code sees it.
- Permissions: every handler asks whether this player may act now (host, alive, in range, off cooldown).
- What each player is told: no browser is sent what its player must not know (rule 1, `tests/test_classic_rule1_messages.py`).
- Passwords: stored as Argon2 hashes. Log-in tries are limited to 5 wrong ones a minute and lobby codes to 10 (`server/net/attempts.py`). An unknown name takes as long to answer as a wrong password (`log_in`).
- Database: queries are parameterised (`INSERT_ACCOUNT`).
- Pages: the server sets security headers, including a content security policy (`SECURITY_HEADERS` in `server/main.py`).
- Dependencies: five runtime packages, all pinned in `requirements.txt`; `pip-audit` reports no known vulnerabilities.
- Secrets: none in the repository; `.env` is ignored.
- WebSocket origin: `/ws` accepts a page only from the host the request was sent to, the deployed address or a site listed in `ALLOWED_ORIGINS`; any other page is refused before the connection opens (HTTP 403, `OriginCheck` in `server/main.py`, `is_origin_allowed` in `server/net/origin.py`, S-207). A connection without an `Origin` header (a script, not a browser) is let through on purpose and meets the same message checks and limits. `ORIGIN_CHECK=off` in Render's settings switches the check off if a page of the real game is ever refused.
*Known gaps:* the attempt limits count per connection, so a new connection starts at zero (S-107); sign-up has no limit of its own, so a script can create many accounts; a player who loses the connection cannot return to a running round (S-109).

### Questions about the last day's changes

**Why does the server check the origin of the WebSocket, and what does that not protect?** (S-207)
Without it, a page of any other site could open our `/ws` in a visitor's browser and play or guess passwords in that visitor's name. The handshake is refused (HTTP 403) unless the page comes from the host the request was sent to, the deployed address or a site in `ALLOWED_ORIGINS`. It does not stop a script that sends no `Origin` header at all; that is allowed on purpose for tools and tests, and such a connection meets the same message checks and limits as any browser. *Show:* `is_origin_allowed` in `server/net/origin.py`, `OriginCheck` in `server/main.py`, the switch `ORIGIN_CHECK=off` in the README.

**What happens when Supabase hangs or is down?** (S-211, S-38)
Every database call runs on one of four worker threads, with short TCP keepalives and a statement timeout, so a hanging connection frees its worker within seconds. The player reads “Accounts are unavailable right now. You can still play as a guest.”, and guests and rounds go on, because lobbies live in memory. At most two Argon2 hashes run at once, to keep memory low. *Show:* `SOCKET_OPTIONS` in `server/accounts/store.py`, `HASHES_AT_ONCE` in `server/accounts/service.py`, `account_workers` in `server/main.py`.

**How does a meeting end?** (S-162, S-212, S-215)
In one of three ways: the clock runs out (45 seconds of discussion and 30 of voting); 75 % of the living choose Skip, which ends it at once with nobody voted out; or 10 seconds after every living player has voted, worked out once per meeting by a plain function that gets the time passed in. After a report or an emergency call, voting is open from the start. *Show:* `shorten_when_everybody_voted`, `end_if_enough_skips` and `voting_is_open` in `server/classic/meeting.py`; the vote tests `tests/test_classic_*vote*.py`.

**Where do players stand after a meeting, and why?** (S-199, replaced by S-213)
Where they stood before it. S-199 first sent everybody back to the Main Deck; Lennart asked that the round go on where everyone had been standing, and S-213 replaced that point. What stays from S-199: nobody walks or opens a task during a meeting, open tasks are closed when it starts, and the Free Rider's 15-second cooldown starts again from the meeting's end. *Show:* `advance_classic_walkers`, `settle_meeting` and `close_every_open_task` in `server/main.py`; `apply_meeting_result` and `take_cooldown_news` in `server/classic/round.py`.

**How do statistics and the leaderboard work with two modes?** (S-40, S-198, S-217)
Only the server writes a finished round: a Duel from its ranking, a Classic round once for every account still in the lobby, with a win for the winning side. Solo and guests write nothing. The leaderboard adds up the wins per mode in SQL (`SUM … FILTER`) and orders by all wins, then the best Duel time, then the name. *Show:* `changes_from_classic` and `total_of` in `server/accounts/statistics.py`, `SELECT_TOP` in `server/accounts/statistics_store.py`, `end_round_if_over` in `server/main.py`.

**Why is the emergency button grey at the start and after a meeting?** (S-216, S-218)
It is drawn from the start of the round, locked and grey, so that players learn where it is; it turns red when it unlocks 45 seconds after the round started or after the last meeting ended. Whether it can be pressed is decided only by the server: the time, a distance of at most 25 units and one call per living player. *Show:* `drawButton` in `client/js/world/draw.js`, `emergency_unlocks_at` in `server/classic/round.py`, `emergency_button_in_reach` in `server/classic/emergency_button.py`.

**How does the browser know not to show “Free Rider” to a High Performer?** (rule 1)
It is never told. The server sends each player only their own role, positions only within 120 units and in line of sight, a hidden Free Rider to no living High Performer, and F-sheets only to those who see them (S-202). `tests/test_classic_rule1_messages.py` lists for every message type who may receive it. *Show:* `server/world/visibility.py`, `tell_positions` in `server/main.py`.

**What runs on GitHub, and when?** (S-220)
`ci.yml` runs on every pull request and every push: pytest, `pip-audit` and the syntax check. `browser-plays.yml` runs after each merge to `main` and when started by hand, with Playwright 1.63.0 and Chromium, so the slow browser plays never block a merge but still run on `main`. *Show:* `.github/workflows/`, “About the tests” in the README.

**What would you build next, and how?**
Two examples. A return into a running round: today a player who loses the connection goes back to the lobby when the round is over (S-109); the server would have to keep that player's place for a few seconds and give it back to the same player on a new connection. And a statistics write that can be repeated safely: give every finished round an id with a unique constraint, so that the database refuses a second copy and a failed write can be tried again (M3-2.9, S-211). *Show:* `game/TODO.md` (the open items), `game/DECISIONS.md`.

**How do you know invalid input does not break the server?**
Every browser message goes through `server/protocol.py` first: at most 2048 bytes, a JSON object, a known type, exactly the right fields, types and ranges (huge numbers are refused since M3-2.3). Then each handler checks the permission (host, alive, in range, off cooldown) and answers with a fixed text from DESIGN.md, section 9. A frame over 4096 bytes is not even read when the server is started with `--ws-max-size 4096` (S-224). *Show:* `parse_client_message` and `REJECTIONS` in `server/protocol.py`; `tests/test_protocol*.py` and the rejected cases in each `tests/test_server_*` and `tests/test_classic_*` file.

## 7. Where decisions and work are written down

- [DECISIONS.md](DECISIONS.md): every decision, numbered S-01, S-02, …, with its date, its reason and who decided.
- [TODO.md](TODO.md): the to-dos by milestone and area, ticked when done.
- [FEATURES.md](FEATURES.md): every feature and its status.
- [WORKFLOW.md](WORKFLOW.md): how a to-do goes from the list to `main` with the coder, reviewer and tester agents (`.claude/agents/`).
- Pull requests on GitHub: every change reached `main` through one (two exceptions on 2026-11-22, named in the README).

**One real example: hiding with E.** Felix wanted the Free Rider to hide on purpose instead of just by standing in a hiding spot (recorded on 2026-11-22). That became the to-do **M3-1.6** in TODO.md and the decisions **S-191** (who may hide, how it ends, what is refused while hidden) and **S-192** (a hidden Free Rider is sent to no living High Performer; the others see a crossed-out eye). It was built on the branch `game/m3-hide-with-e` (commits “The Free Rider hides on purpose with E (M3-1.6, S-191)” and “A hidden Free Rider is sent to no High Performer; others see a crossed-out eye (S-192)”), with the plain rules in `server/classic/hiding.py`, the server tests in `tests/test_hide_with_e.py` and a play test with four browsers (`tests/test_play_hide_with_e.py`). It reached `main` as **pull request #100** on 2026-11-22, together with M3-1.5 (hiding spots as map objects, S-190).

## 8. Try it in two minutes

1. Start the server as the [README](../README.md#run-it-locally) says and open http://localhost:8000.
2. Click “Play as guest”, then “Create lobby”. A new lobby starts in Solo (S-203): “Start game” plays a Duel route alone.
3. Open a second browser window, “Play as guest”, type the four-letter code and “Join”. The lobby switches to Duel; the host clicks “Start game”. Walk with WASD, press E at the pulsing station.
4. For Classic open four windows (four players at least), and the host chooses “Classic”. M opens the campus map.

## 9. Before the live demo

- Open https://itp-group.onrender.com a few minutes before: the free Render instance sleeps and takes about a minute to wake.
- Check in Supabase that the project is not paused, and log in once with a test account. If accounts fail, the game still works for guests, and the page says so.
- Have four browser windows ready (Classic needs four players), two of them signed in with accounts so the profile has numbers to show.
- A five-minute path:
  1. Sign up and log in, and show one refused input (a lobby code with three letters: “Lobby codes are 4 letters.”).
  2. Create a lobby and let the others join with the code.
  3. Play Classic: the Free Rider fails somebody, somebody reports, then chat and vote.
  4. Play one short Duel.
  5. Open the profile on Home and show the new rounds.
- If the hall's network blocks WebSockets, use a phone hotspot.
