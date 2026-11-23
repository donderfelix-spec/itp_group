# Group Project: the code

A multiplayer game in the browser that is set on the Nova SBE campus. The “High Performers” complete tasks for a group project, while a “Free Rider” among them secretly sabotages. The game belongs to the social deduction genre, but it is a game of its own with its own name, its own characters, its own map and its own graphics (see S-01 and S-02 in the [DECISIONS.md](DECISIONS.md)).

What the game is, who built it, the public URL and the known limitations are in the [README.md](../README.md) of the main folder. This page is the map of the code.

## Starting and testing

Run all commands in the `game` folder.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

```bash
.venv/bin/uvicorn server.main:app --reload
```

```bash
.venv/bin/python -m pytest
```

```bash
.venv/bin/pip-audit -r requirements.txt
```

The first command sets up the environment once. The second starts the game on http://localhost:8000 (without `DATABASE_URL`, accounts and statistics are kept in memory). The third runs the tests, the fourth checks the dependencies for known security vulnerabilities.

Some tests run the real client files in Node.js, and the play tests (`tests/test_play_*.py` and a few others) drive real Chromium pages through the npm package Playwright. Without Node, or without Playwright and Chromium, pytest skips them and says so. The CI on GitHub (`.github/workflows/ci.yml`) has Node but no Playwright.

## Documents

- [DESIGN.md](DESIGN.md): look, map, characters, screens, rules of the modes, minigames, every message shown to the player
- [TODO.md](TODO.md): all to-dos, sorted by milestone and area
- [FEATURES.md](FEATURES.md): overview of all features with their status
- [DECISIONS.md](DECISIONS.md): all decisions with reasons
- [WORKFLOW.md](WORKFLOW.md): the agent roles and the process from the to-do to the merge

## The modes

| Mode | In short | Players |
|---|---|---|
| Classic | Everyone completes tasks on the campus, one active task at a time. One or two Free Riders fail others and can hide. In meetings the players discuss by chat and vote in public. | 4 to 8 |
| Duel | Everyone gets their own random route of three stations, of about the same walking length. Whoever completes them first wins; the round ends after 3 minutes at the latest. | 2 to 8 |
| Solo | The Duel for one player alone, without statistics. | 1 |

## The four areas

The areas have owners (S-96): area 1 Hanna, area 2 Felix, area 3 Laurin, area 4 Lennart.

| Area | Responsible for | Boundary to the others |
|---|---|---|
| 1 Campus and characters | Map with its rooms, movement, collision, camera, limited view, characters, graphics | Delivers positions and “player is at station X”. What happens at the station belongs to area 3 or 4. |
| 2 Network, lobby and foundation | Server, lobby with code, synchronisation of the players, reconnecting, message format, accounts and statistics, tests, CI, hosting | Transports messages and checks them, but does not know the rules of a mode. |
| 3 Classic rules | Roles, failing someone, reporting, meeting, chat, vote, hiding, win conditions | Only asks area 4 “task done?”. |
| 4 Minigames and extra modes | Frame for minigames, all minigames, Duel and Solo | Reports “done” to the server. Does not know any roles. |

## Structure

Every file belongs to exactly one area.

| Folder or file | Content | Area |
|---|---|---|
| `server/main.py` | Web server, WebSocket connection, security headers, the handlers that connect messages to the rules | 2 |
| `server/protocol.py` | Validation of every message from the browser, and the fixed texts of every rejection | 2 |
| `server/net/` | Lobbies, sessions, walking of the players, limits on attempts | 2 |
| `server/accounts/` | Accounts (Argon2 hashes), statistics and the leaderboard, in memory or in Postgres | 2 |
| `server/world/` | The checked map, movement and collision, stations, walking distances, what a player can see | 1 |
| `rules.py` | The rules of a Classic round as plain functions: roles, tasks, failing, reporting, winner | 3 |
| `server/classic/` | The Classic round, meetings and votes, the emergency button, hiding | 3 |
| `server/modes/` | The task frame (open, close, finish a station), the minigames' content, the Duel | 4 |
| `client/index.html`, `client/css/` | Page skeleton, screens and colours | 2 |
| `client/js/main.js`, `client/js/net.js` | Routing of the server's messages to the parts of the page; the WebSocket connection | 2 |
| `client/js/lobby/` | Start screen, sign-up and log-in, lobby, countdown, profile and leaderboard | 2 |
| `client/js/world/` | Map (`campus.json`), drawing of rooms and characters (`art/`), walking, camera, limited view, overview map | 1 |
| `client/js/classic/` | Role card, action buttons, meeting window, end screen | 3 |
| `client/js/minigames/` | Frame and one file per kind of minigame, Duel panel, task card and arrow | 4 |
| `design/` | Sketches of the map and the characters (SVG) | 1 |
| `tests/` | Tests with pytest, and the Node and browser scripts they drive | 2 (frame), every area for its own tests |
| `requirements.txt`, `requirements-dev.txt`, `pyproject.toml` | Dependencies with pinned versions, test settings | 2 |

The rules for all agents are in the [AGENTS.md](../AGENTS.md) in the main folder, the agent roles under `.claude/agents/`.
