# Rules for coding agents

These rules apply to every agent working in this repository (Codex, Claude Code, others) and to every team member's sessions. Change this file only through a pull request.

## The project

**Group Project** is a multiplayer browser game set on the Nova SBE campus. "High Performers" complete tasks for a group project while a hidden "Free Rider" sabotages them. It is our team project for Introduction to Programming, due **2026-11-23, 23:59**.

The game lives in `game/`. The folder `archive/` holds an older, unrelated project (the prototype "We Be(a)t" with its tests and lists, S-45): do not touch it.

Read before you change anything:

- `game/DESIGN.md`: look, map, characters, screens, rules of every mode, minigames, messages shown to the player
- `game/DECISIONS.md`: every decision with its reason. Newer entries replace older ones where they say so.
- `game/TODO.md` and `game/FEATURES.md`: what is open and what exists
- `game/WORKFLOW.md`: how a to-do travels from the list to `main`

Everything in `game/` is English: documents, code, comments, tests, commit messages and all text shown in the game.

## Stack

- Server: Python 3.13, FastAPI, WebSockets. No other framework.
- Client: plain HTML, CSS and JavaScript on a canvas. No build step, no framework, no npm packages.
- Data: accounts and statistics in Postgres (Supabase). Lobbies and running rounds live in the server's memory.
- Tests: pytest.

## Commands

Run all of these from the `game` folder.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # once
.venv/bin/uvicorn server.main:app --reload --ws-max-size 4096          # run the game on http://localhost:8000
.venv/bin/python -m pytest                                               # run the tests
.venv/bin/pip-audit -r requirements.txt                                  # check dependencies for known vulnerabilities
```

## Where things are

Every file belongs to exactly one area. Stay inside the area of your to-do.

| Area | Folders |
|---|---|
| 1 Campus and characters | `game/client/js/world/`, `game/server/world/` (movement, collision, stations and walking distances on the server, S-79), drawing code for map and characters, `game/design/` |
| 2 Network, lobby, accounts, foundation | `game/server/main.py`, `game/server/protocol.py`, `game/server/net/`, `game/server/accounts/`, `game/client/index.html`, `game/client/css/`, `game/client/js/main.js`, `game/client/js/net.js`, `game/client/js/keyboard_notice.js`, `game/client/js/lobby/`, CI, hosting |
| 3 Classic rules | `game/rules.py` (the plain Classic rules), `game/server/classic/`, `game/client/js/classic/` |
| 4 Minigames and other modes | `game/server/modes/`, `game/client/js/minigames/` |

Tests go in `game/tests/`, named after what they test.

## Rules that are never broken

1. **The server decides.** Roles, positions, who failed, votes, results and statistics are decided and stored by the server. The browser only sends what the player wants to do and draws what the server tells it. Never send a browser information its player must not know (for example who the Free Rider is).
2. **Check every message.** Everything from the browser goes through `server/protocol.py` first. A new message type needs its checks and tests for accepted, rejected and edge cases.
3. **Check every permission.** For each action the server asks: may this player do this now? (Is the player the host, alive, in range, off cooldown?) A rejected action gets a clear message from the table in `DESIGN.md`, section 9, and never crashes anything.
4. **Game rules are plain functions.** No network, no database, no clock inside them. Pass the time and random choices in as arguments so tests can control them.
5. **No secrets in the repository.** Connection strings and keys are read from environment variables. Never print them, never commit a `.env` file.
6. **Few dependencies, all pinned.** Adding a package is a team decision. Pin the exact version in `requirements.txt`.
7. **Never change a test to make it pass.** If a test is wrong, say so and explain why. Do not delete or weaken tests.
8. **One branch per to-do, merged by pull request.** Never push to `main`. A person approves every pull request.
9. **Do only what the to-do asks.** No extra features, no refactoring of files outside the to-do.
10. **Keep the lists true.** When a to-do is done, tick it in `TODO.md`, update the row in `FEATURES.md`, and add any new decision to `DECISIONS.md` with its reason.

## Done means

- The acceptance criteria of the to-do are met.
- `pytest` passes, with new tests for accepted actions, rejected actions and edge cases.
- `pip-audit` reports nothing.
- The feature was tried in a browser, with several players where it involves several players.
- Every team member could explain the change after reading it: clear names, short functions, a comment where the reason is not obvious.
