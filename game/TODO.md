# To-dos for “Group Project”

As of 2026-11-18

The to-dos are sorted by milestone and, within each milestone, by area. The areas are described in the [README.md](README.md), the status of all features in the [FEATURES.md](FEATURES.md), decisions in the [DECISIONS.md](DECISIONS.md), and the process with the agents in the [WORKFLOW.md](WORKFLOW.md).

Whoever takes on a to-do writes their name after it. The number is made up of the milestone, the area and a running number: `M2-4.3` is the third to-do of area 4 in milestone 2.

## For the team to settle

These points hold up the start. The reasoning behind them is under “Open decisions” in the DECISIONS.md.

- [x] **K1** Date: submission on Monday, 2026-11-23, 23:59. The scope for it is in S-33.
- [x] **K2** The wiki requires a public URL, so hosting is needed (S-31)
- [x] **K3** Laptop with keyboard first (S-14)
- [x] **K11** Supabase project created, the team has the connection URL (2026-11-18)
- [x] **K4** Technology confirmed: Python with FastAPI and WebSockets, client with Canvas (S-29)
- [ ] **K12** Ask the teaching staff whether a Python server with a JavaScript client is acceptable (S-42)
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

**Area 1**

- [ ] **M1-1.1** Draw the map from the floor plan, with simple shapes
- [ ] **M1-1.2** Move the character with the keyboard, the camera follows
- [ ] **M1-1.3** Collision with walls and furniture
- [ ] **M1-1.4** Draw other players with their names

**Area 2**

- [ ] **M1-2.0** Accounts: tables in Supabase, sign up, log in, log out, guest access, with tests for rejected cases (name taken, wrong password, password too short)
- [ ] **M1-2.1** Start page: log in or play as a guest, create a lobby or join with a code
- [ ] **M1-2.2** Lobby on the server: code, player list, host
- [ ] **M1-2.3** Synchronise positions and smooth the movement of the other players
- [ ] **M1-2.4** Play test with several browsers: three players join and see each other walk

## M2: Duel

**Area 1**

- [ ] **M2-1.1** Stations on the map, highlight when nearby, key to open
- [ ] **M2-1.2** Character selection in the lobby, first version of the eight stereotypes
- [ ] **M2-1.3** Display of the current room

**Area 2**

- [ ] **M2-2.1** The host chooses the mode and starts the round
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

- [x] **M0-2.5** Messages for lobby, accounts and movement defined and checked in `server/protocol.py`, list confirmed by the team (S-74) (2026-11-18)
- [x] **M0-2.6** First deploy on Render: https://itp-group.onrender.com, deploys automatically from `main`. Start page, `/health` and the WebSocket connection checked on the deployed URL (2026-11-18)
- [x] **M0-2.1** Agents created: `researcher`, `coder`, `reviewer`, `tester` under `.claude/agents/`, rules in `AGENTS.md`, `CLAUDE.md` refers to it (2026-11-18)
- [x] **M0-2.2** and **M0-2.3** Research on movement and tests: decided in S-72 (2026-11-18)
- [x] **M0-2.4** Project skeleton: server, start page, message validation, 51 tests, CI with tests, dependency check and syntax check (2026-11-18)
- [x] **M0-1.1** Floor plan of the map as a sketch (`design/map.svg`)
- [x] Planning: feature overview, decision log, to-do list, workflow of the agents (2026-11-18)
