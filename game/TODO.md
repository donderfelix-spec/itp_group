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
- [ ] **K7** Who takes on which of the four areas?
- [x] **K8** “We Be(a)t” is put aside for now (S-27)
- [x] **K9** Render account created and service set up (2026-11-18)
- [ ] **K10** Names and student numbers of all members for the README (S-36)

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

**To check by a person (the tools could not)**

- [ ] **M1-2.17** Hold a walking key and switch to another tab or window: the character must stop (only tested with simulated events)
- [ ] **M1-2.18** Watch two players walk on two real screens and judge whether the movement looks smooth (only measured: one position every 68 ms, no jumps)
- [ ] **M1-2.19** Hold a key, press Cmd and release the key on a Mac: the character must stop (only tested with simulated events)

**For the team to decide**

- [ ] **K13** Confirm or change the decisions marked “Proposal” from milestone 1: S-83 to S-89 in DECISIONS.md
- [ ] **K14** The hedge is solid, but a hiding spot is drawn inside it: hide beside the hedge, or make the hedge walkable? (S-87, needed for M3-1.4)

## M2: Duel

**Area 1**

- [x] **M2-1.2** Character selection in the lobby, first version of the eight stereotypes (came with M1-2.1)
- [ ] **M2-1.3** Display of the current room
- [ ] **M2-1.4** Make the map nicer and more detailed: floors, furniture and plants with more detail, still drawn from `campus.json`
- [ ] **M2-1.5** Draw the characters larger. A character standing on a station already hides its number (seen in the play test of M2-1.1), so check that too. The server decides collisions, so check the collision size and the narrow passages of the map with it
- [ ] **M2-1.6** More realistic walking: feet that move while walking, and the head turned in the walking direction

**Area 2**

- [ ] **M2-2.2** Back to the lobby after the round
- [ ] **M2-2.3** A player leaves the round, the host changes
- [ ] **M2-2.4** Statistics: the server writes the result of every round, profile with wins and best Duel time, leaderboard

**Area 4**

- [ ] **M2-4.1** Frame for minigames: open, close, report “done”, plausibility check on the server
- [ ] **M2-4.2** Minigame Canteen: put a tray together
- [ ] **M2-4.3** Minigame Mon Café: Brew the order
- [ ] **M2-4.4** Minigame Lecture Hall: sort slides
- [ ] **M2-4.5** Minigame CTT Student Hall: sort books
- [ ] **M2-4.6** Minigame Pingo Doce: Self-checkout with a target amount
- [ ] **M2-4.7** Duel: a separate route for each player with an equally long walking distance, progress of the opponents, leaderboard
- [ ] **M2-4.8** Play test: two players play a Duel through to the leaderboard

## M3: Classic

**Area 1**

- [ ] **M3-1.1** Limited vision
- [ ] **M3-1.2** Show ghosts, a failed character stays on the ground until it is reported
- [ ] **M3-1.3** Overview map with open tasks
- [ ] **M3-1.4** Four hiding spots (S-62), after the core of Classic

**Area 2**

- [ ] **M3-2.1** Every client receives only what its player is allowed to know (roles, ghost chat)
- [ ] **M3-2.2** Reconnect after a short disconnection

**Area 3**

- [ ] **M3-3.1** Rules as pure functions: assign roles, assign tasks, win conditions, with tests
- [ ] **M3-3.2** Failing someone, with range and cooldown
- [ ] **M3-3.3** Reporting and emergency meeting
- [ ] **M3-3.4** Meeting screen with chat and time limit
- [ ] **M3-3.5** Vote and result
- [ ] **M3-3.6** Progress bar, role display, end screen
- [ ] **M3-3.7** Play test: one complete round with five players, once the students win, once the Free Rider wins

**Area 4**

- [ ] **M3-4.1** Connect the minigames to the task list of the Classic mode

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
