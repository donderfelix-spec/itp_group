# To-dos for “Group Project”

As of 2026-11-19

The to-dos are sorted by milestone and, within each milestone, by area. The areas are described in the [README.md](README.md), the status of all features in the [FEATURES.md](FEATURES.md), decisions in the [DECISIONS.md](DECISIONS.md), and the process with the agents in the [WORKFLOW.md](WORKFLOW.md).

Whoever takes on a to-do writes their name after it. The number is made up of the milestone, the area and a running number: `M2-4.3` is the third to-do of area 4 in milestone 2.

## For the team to settle

These points hold up the start. The reasoning behind them is under “Open decisions” in the DECISIONS.md.

- [x] **K1** Date: submission on Monday, 2026-11-23, 23:59. The scope for it is in S-33.
- [x] **K2** The wiki requires a public URL, so hosting is needed (S-31)
- [x] **K3** Laptop with keyboard first (S-14)
- [x] **K11** Supabase project created, the team has the connection URL (2026-11-18)
- [x] **K4** Technology confirmed: Python with FastAPI and WebSockets, client with Canvas (S-29)
- [x] **K12** Ask the teaching staff whether a Python server with a JavaScript client is acceptable (S-42). Settled (2026-11-19)
- [x] **K5** The third mode is “Deadline”, only if time allows (S-12, S-33)
- [x] **K6** Name of the game: “Group Project” (S-37)
- [x] **K7** The four areas: area 1 Hanna, area 2 Felix, area 3 Laurin, area 4 Lennart (2026-11-19). The name after an open to-do below says who takes it
- [x] **K8** “We Be(a)t” is put aside for now (S-27)
- [x] **K9** Render account created and service set up (2026-11-18)
- [ ] **K10** Names and student numbers of all members for the README (S-36)
- [x] **K16** Settled 2026-11-19 (S-102): players may walk while the ranking card is up; a start by the host begins with a countdown of 5 seconds (M2-2.5); a finished player waits for the others as before

## M0: Preparation

- [ ] **M0-4.1** The five minigames are described in the DESIGN.md, the team should proofread them once more
- [ ] **M0-2.7** Write the README in the main folder in English for the submission (S-36), and decide whether the planning documents will be translated

## M1: Walking

Built, play-tested and on `main`, see “Done”. These points came up while building and testing milestone 1 and are still open.

**Security and accounts (area 2)**

- [ ] **M1-2.6** Limit log-in attempts and lobby-code guessing per connection (found in the code reviews, S-83)
- [ ] **M1-2.7** Show or hide the password with an eye icon in the sign-up and log-in forms
- [ ] **M1-2.8** Tell a player why they were signed out when the same account logs in somewhere else (needs a text in DESIGN.md, section 9)
- [ ] **M1-2.9** Add `sslmode=require` to `DATABASE_URL` on Render, as Supabase recommends, and check that sign up still works
- [ ] **M1-2.10** Check in the Supabase dashboard that the Data API returns no rows of `accounts` with the public key (row level security is on, S-90)
- [ ] **M1-2.11** Before the demo: open the Supabase project and make sure it is not paused (free projects pause after a week without activity, S-39)

**Server and hosting (area 2)**

- [ ] **M1-2.12** Send cache headers for the scripts and the stylesheet, so that players do not keep old files after a deploy (seen in the play test: a normal reload served an old script)
- [ ] **M1-2.13** Add a favicon (the server log shows a 404 for it on every visit)
- [ ] **M1-2.14** Add `server/world/` and `server/net/` to the area table in `AGENTS.md` (S-79), by pull request
- [ ] **M1-2.15** A lobby that fails on every tick writes 15 log lines per second: log it once and then only now and then
- [ ] **M1-2.16** Use Python 3.13 in the local `.venv` like CI and Render (it runs 3.14 on the development machine)

**Map and look (area 1)**

- [ ] **M1-1.5** Close or widen the gap between the third tree and the hedge on the Main Deck: it is exactly one player wide, and a player squeezing through is drawn over both
- [ ] **M1-1.6** Give each room a label position in `campus.json`: “Pingo Doce” is drawn in the middle of the room instead of at the right as in the sketch, and “Main Deck” sits on the spawn point
- [ ] **M1-1.7** Narrow windows (under about 800 px): the walking hint overlaps a room name and the top message overlaps the lobby code. Between about 800 and 920 px the button “E Use” also covers the end of the walking hint (seen in the play test of M2-1.1)
- [ ] **M1-1.8** Keep the list of characters in one place: the lobby panel has its own fallback copy next to `world/characters.js` and `protocol.CHARACTERS`
- [ ] **M1-1.9** Add the new texts to DESIGN.md: “Loading the campus…”, “Signed in as”, “Players”, “Character”, “Lobby code”, “Coming with the next milestone”

- [ ] **M1-2.20** The test `test_a_second_log_in_signs_the_first_connection_out` sometimes hangs when the machine is busy (seen twice while four test runs ran at once; alone it passes). A hanging test would block CI: find the cause

**To check by a person (the tools could not)**

- [ ] **M1-2.17** Hold a walking key and switch to another tab or window: the character must stop (only tested with simulated events)
- [ ] **M1-2.18** Watch two players walk on two real screens and judge whether the movement looks smooth (only measured: one position every 68 ms, no jumps)
- [ ] **M1-2.19** Hold a key, press Cmd and release the key on a Mac: the character must stop (only tested with simulated events)

**For the team to decide**

- [x] **K13** Confirmed 2026-11-19: all proposals of milestones 1 and 2 stand (S-100); S-87 is replaced by S-98
- [x] **K15** Settled 2026-11-19: they stay as they are for now (S-99). Two findings of the play test of the minigames: “Brew the order” and “Build the tray” take about 5 seconds instead of the 10 to 25 of DESIGN.md, section 8; and both can be solved without reading the slip by clicking everything, because a mistake costs nothing (S-58). Leave it, or make them longer or let a mistake cost a moment?
- [x] **K14** Settled 2026-11-19: players hide inside the hedge, so the hedge becomes walkable (S-98, replaces the solid hedge of S-87). Built with M3-1.4

## M2: Duel

Milestone 2 was built up to the Duel by Claude as lead (pull requests #19 to #26 and the Duel pull request). What is left is listed here per area, with what the next person needs to know. The process is in the [WORKFLOW.md](WORKFLOW.md); new work starts from `main`.

**Area 1 (Hanna)**

- [x] **M2-1.2** Character selection in the lobby, first version of the eight stereotypes (came with M1-2.1)
- [ ] **M2-1.3** Display of the current room (Hanna). Not started. The browser can find the room from the own position and the rooms in `campus.json`; `draw.js` already has `roomAt`. DESIGN.md, section 4: the name stands at the top left
- [ ] **M2-1.4** Make the map nicer and more detailed: floors, furniture and plants with more detail, still drawn from `campus.json` (Hanna). **Started, not merged.** Branch `game/m2-1.4-map-detail`: built, full suite green, one code review without blocking findings. No geometry changed; `campus.json` gained `pattern` on rooms, `faces` and `holds` on some solids and a list `decor` that only the browser draws. Branch `game/m2-1.4-map-detail-wip` holds the unfinished and untested fixes of that review: door mats and door leaves vanish at the edge of the view, six leaves lie on the walkable deck (decor must not lie where players walk; a test for that rule was started), the round café tables look smaller than the area they block, the canteen tables read as cassettes. Missing: finish and test those fixes, second review, play test, lists, pull request. Drawing the map costs about twice as much as before, still far inside one frame
- [ ] **M2-1.5** Draw the characters larger (Hanna). Not started. A character standing on a station already hides its number (seen in the play test of M2-1.1), so check that too. The server decides collisions, so check the collision size and the narrow passages of the map with it. If the collision size changes, the walking distances of the Duel change with it: `server/world/paths.py` measures them with the player's size, and its tests name the narrow places
- [x] **M2-1.6** More realistic walking: front, side and back view of all eight characters, alternating feet, a soft stop. Two code reviews, play test with two players, the icons in the lobby are unchanged (2026-11-19). Known and accepted: a player put back onto the spawn from fewer than 15 map units away is drawn taking one step, because the browser cannot tell that from a real step; hair and headwear do not turn yet (M2-1.7)
- [ ] **M2-1.7** The hair, buns and headwear of the characters follow the head when it turns in the walking direction, instead of staying in place (Hanna). Not started. Build it on top of M2-1.6: in the side view only the face is shifted so far, hair and headwear are still drawn from the front

**Area 2 (Felix)**

- [x] **M2-2.2** Back to the lobby after the round (Felix). Played through with three players in real browsers, also with the time running out and three rounds in a row; the run is `tests/test_play_back_to_lobby.py`. What the panel shows and where the players stand is decided in S-101 (2026-11-19)
- [x] **M2-2.3** A player leaves the round, the host changes (Felix). Played through with three players in real browsers: leaving with the button, closing the tab, the same account logging in elsewhere, the host leaving, two of three leaving, coming back after a lost connection or a restart of the server; the run is `tests/test_play_leave_round.py`. A player who comes back cannot rejoin the running round and reads “This round has already started.” until it is over; rejoining is M3-2.2, the missing text for being signed out elsewhere is M1-2.8 (2026-11-19)
- [x] **M2-2.4** Statistics: the server writes the result of every Duel round, profile with rounds, wins and best Duel time, leaderboard of the accounts that have played (Felix). Two code reviews, the SQL run against a real Postgres 16 by the reviewer, play test with two accounts and a guest; decisions in S-103 (2026-11-19). **Still to check by a person:** play one Duel on the deployed server with two accounts and open both screens, because the real Supabase database could not be reached while building
- [ ] **M2-2.6** Small follow-ups from the second review of M2-2.4, none of them a defect: make `result` a required argument of `tell_round_ended`; replace the test that waits 0.2 seconds for two requests with one that runs three calls of `leaderboard_totals` directly; give “Profile” and “Leaderboard” on Home the same width or correct the comment in the stylesheet; reset the leaderboard cache in `tests/conftest.py` (Felix)
- [ ] **M2-2.5** Countdown before a round: when the host presses “Start game”, everybody sees a countdown of 5 seconds, and only then the round starts. A ranking card that is still open stays readable during the countdown and closes when the round starts. The server counts (rule 1); decide while building what the players may do during the countdown, and add the text to DESIGN.md (Felix)

A complete Duel round needs nothing more from area 2: start, play, ranking and the next round work. M2-2.2 and M2-2.3 are about what is shown and about playing it with several people; M2-2.4 is the only part of the required scope (S-40) that is not built at all.

**Area 4 (Lennart)**

- [x] **M2-4.7a** A fault after a task was counted takes the count back, in the frame and in the Duel, so the server never counts a station the browser was not told about (solved with M2-4.7)
- [x] **M2-4.7** Duel: a separate route for each player with an equally long walking distance, progress of the opponents, leaderboard (S-94). In the pull request after #26
- [ ] **M2-4.8** Play test: two players play a Duel through to the leaderboard (Lennart). A scripted run with two browsers and the real minigames exists from the building of M2-4.7 (both finish, ranking, second round, time running out). Left to do: two people on two computers on the deployed server, and write down what gets in the way
- [ ] **M2-4.9** After a solved minigame the “Done” window stays for one second and the walking keys are ignored during it; a key that is already held only counts again when the window has closed. In a Duel that is three seconds of standing per route and feels like lag (found in the play test of M2-2.2, after Felix reported lag). Let a held or newly pressed walking key take effect at once, or shorten the window (Lennart)

**Known and open after the Duel**

- With 7 or 8 players a few draws do not find enough routes within 10 % of the first one; then the nearest routes in length are taken (S-94). The 60 routes are between about 15 and 29 seconds of walking
- A finish that reaches the server after the 180 seconds does not count
- **M2-4.9** (Lennart) If setting up a round ever failed at the start (`handle_start_game` in `server/main.py`), the lobby would stay in phase `round` with nothing to play and nobody could start, join or end it. Nothing in the code can fail there today; catch it, end the round and answer “Something went wrong. Try again.”, with a test. Found in the review of M2-4.7
- **M2-4.10** (Lennart) A fault while building the ranking would keep a round from ending and write a log line on every tick; only the building of the message is guarded so far. Found in the review of M2-4.7
- **M2-4.11** (Felix) A host who starts the next round in the same instant the old one ends can leave the old ranking card over the new round for a player. And `client/js/net.js` treats the Duel's progress messages as “the answer” to a click, so a double click can slip through while another player finishes a station (the server refuses it with “Close your current task first.”). Both found in the review of M2-4.7
- Two tests in `tests/test_play_round.py` sometimes read a position message from the tick first and fail about once in 25 runs (`test_a_player_who_became_host_during_the_round_can_neither_start_nor_choose`, `test_the_start_is_refused_when_the_only_other_player_has_just_closed_the_connection`). Same family as M1-2.20; they were not changed

## M3: Classic

**Area 1 (Hanna)**

- [ ] **M3-1.1** Limited vision (Hanna)
- [ ] **M3-1.2** Show ghosts, a failed character stays on the ground until it is reported (Hanna)
- [ ] **M3-1.3** Overview map with open tasks (Hanna)
- [ ] **M3-1.4** Four hiding spots (S-62), after the core of Classic (Hanna)

**Area 2 (Felix)**

- [ ] **M3-2.1** Every client receives only what its player is allowed to know (roles, ghost chat) (Felix)
- [ ] **M3-2.2** Reconnect after a short disconnection (Felix)

**Area 3 (Laurin)**

- [ ] **M3-3.1** Rules as pure functions: assign roles, assign tasks, win conditions, with tests (Laurin)
- [ ] **M3-3.2** Failing someone, with range and cooldown (Laurin)
- [ ] **M3-3.3** Reporting and emergency meeting (Laurin)
- [ ] **M3-3.4** Meeting screen with chat and time limit (Laurin)
- [ ] **M3-3.5** Vote and result (Laurin)
- [ ] **M3-3.6** Progress bar, role display, end screen (Laurin)
- [ ] **M3-3.8** When so many players leave a running Classic round that the ratio of High Performers to Free Riders no longer fits (S-48: one Free Rider with 4 or 5 players, two with 6 to 8), the round is stopped: everybody returns to the lobby with a clear message (Laurin, with Felix for the leaving). Requested by Felix on 2026-11-19. To decide while building: the exact limit, and the text for DESIGN.md, section 9
- [ ] **M3-3.7** Play test: one complete round with five players, once the students win, once the Free Rider wins (Laurin)

Classic starts like Duel: `server/main.py` has a small table `ROUND_SETUPS` with one entry per mode, and `protocol.MODES` lists the modes the host can choose. A new mode adds one entry to each.

**Area 4 (Lennart)**

- [ ] **M3-4.1** Connect the minigames to the task list of the Classic mode (Lennart). The frame asks a function which stations a player needs (`needed_stations` in `server/modes/tasks.py`); Duel passes “only the next one”, Classic passes the player's task list

## M4: Extension

- [ ] **M4-3.1** Sabotage “Wi-Fi outage”
- [ ] **M4-3.2** Sabotage “Fire alarm”
- [ ] **M4-4.0** Minigame “Catch the wave” at the beach exit, then switch Classic to four out of six and Duel to three out of six (S-67)
- [ ] **M4-4.1** Three more minigames (microwave, QR code, spreadsheet formula)
- [ ] **M4-4.2** Deadline mode
- [ ] **M4-1.1** Finished graphics for rooms and characters
- [ ] **M4-2.1** Friends: request, accept, decline, status, invitation to the lobby, leaderboard among friends (S-41)
- [ ] **M4-1.2** Touch controls for mobile phones
- [ ] Play a real round once with the whole team and write down what gets in the way

## Done

- [x] **M2-4.7** and **M2-4.7a** Duel: every player gets an own route of three stations with about the same walking distance, measured on the real map; only the next station opens; the panel shows the next station, the clock and everybody’s progress; the round ends when all have finished or after three minutes, with a ranking, and the lobby is open again (S-94) (2026-11-19)
- [x] **M2-4.6** Minigame Pingo Doce “Self-checkout”: scan products until the total is exactly the target, a product that goes over is refused. All five minigames were played in one round with two browsers; the runs are kept as `tests/test_play_minigames_1_3.py` and `tests/test_play_minigames_4_5.py` (2026-11-19)
- [x] **M2-4.5** Minigame CTT Student Hall “Shelve the books”: six books with numbers from 100 to 999 are clicked onto the shelf from the lowest to the highest, a wrong book falls back. Played in the browser in a real round (2026-11-19)
- [x] **M2-4.4** Minigame Lecture Hall “Sort the slides”: five slides are dragged onto five numbered places, a slide on a wrong place shakes and jumps back. Played in the browser in a real round (2026-11-19)
- [x] **M2-4.3** Minigame Mon Café “Brew the order”: five drinks, six buttons in shuffled places, the cup fills step by step, a wrong button flashes. Played in the browser in a real round (2026-11-19)
- [x] **M2-4.2** Minigame Canteen “Build the tray”: the order slip names four of six dishes, a wrong dish goes back to the counter. Played in the browser in a real round (2026-11-19)
- [x] **M2-4.1** Frame for minigames: E at a station opens a window over the map, the server checks round, station, range and a minimum time before “done” counts (S-93). Every station shows a placeholder until its minigame is merged. Play test with two browsers, kept as `tests/test_play_tasks.py` (2026-11-19)
- [x] **M2-1.1** Stations on the map: within 25 units the nearest station pulses yellow and the button “E Use” turns yellow, E or a click opens it (S-92). The rule also exists on the server (`server/world/stations.py`) for the check in M2-4.1. Play test in the browser at all six stations and with two players, kept as `tests/test_play_stations.py` (2026-11-19)
- [x] **M2-2.1** The host chooses the mode and starts the round: mode choice and “Start game” in the lobby panel, the server checks host, player count and running round (S-91), play test with two and three browsers and eight connections (`tests/test_play_round.py`). A round cannot end yet: that comes with M2-4.7 and M2-2.2 (2026-11-19)
- [x] **M1-2.5** Accounts run against the real Supabase database: sign up on the deployed URL stores the account with an Argon2 hash, the table has row level security (S-90). The cause of the first failure was a database password with special characters in `DATABASE_URL` (2026-11-19)
- [x] **M1-2.4** Play test: automated test with three players (`tests/test_play_walking.py`) and a run in the browser with two tabs and a full lobby (2026-11-19)
- [x] **M1-2.3** Positions: the server moves every player about 15 times per second and tells the lobby, the browser smooths in between (2026-11-19)
- [x] **M1-2.2** Lobby on the server: four-letter code, player list, host, host change (2026-11-18)
- [x] **M1-2.1** Start page, sign up and log in with the rules shown at the fields, home, lobby panel with character selection (2026-11-19)
- [x] **M1-2.0** Accounts: sign up, log in, log out, guest, Argon2 hashes, storage behind one interface. Run against Supabase in M1-2.5 (2026-11-18)
- [x] **M1-1.1** to **M1-1.4** Map drawn from `client/js/world/campus.json`, walking with WASD or arrow keys, camera, collision decided by the server, other players with names (2026-11-19)
- [x] **M0-2.5** Messages for lobby, accounts and movement defined and checked in `server/protocol.py`, list confirmed by the team (S-74) (2026-11-18)
- [x] **M0-2.6** First deploy on Render: https://itp-group.onrender.com, deploys automatically from `main`. Start page, `/health` and the WebSocket connection checked on the deployed URL (2026-11-18)
- [x] **M0-2.1** Agents created: `researcher`, `coder`, `reviewer`, `tester` under `.claude/agents/`, rules in `AGENTS.md`, `CLAUDE.md` refers to it (2026-11-18)
- [x] **M0-2.2** and **M0-2.3** Research on movement and tests: decided in S-72 (2026-11-18)
- [x] **M0-2.4** Project skeleton: server, start page, message validation, 51 tests, CI with tests, dependency check and syntax check (2026-11-18)
- [x] **M0-1.1** Floor plan of the map as a sketch (`design/map.svg`)
- [x] Planning: feature overview, decision log, to-do list, workflow of the agents (2026-11-18)
