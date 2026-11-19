# Group Project

A multiplayer game in the browser that is set on the Nova SBE campus. The “High Performers” complete tasks for a group project, while a “Free Rider” among them secretly sabotages. The game belongs to the social deduction genre, but it is a game of its own with its own name, its own characters, its own map and its own graphics (see S-01 in the [DECISIONS.md](DECISIONS.md)).

As of 2026-11-18. The project skeleton is in place: the server delivers a start page and answers a first WebSocket message. The game itself comes from milestone 1 onwards. The old prototype “We Be(a)t” lies unchanged under `prototype/`.

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

The first command sets up the environment once. The second starts the game on http://localhost:8000. The third runs the tests, the fourth checks the dependencies for known security vulnerabilities.

## Documents

- [DESIGN.md](DESIGN.md): look, map, characters, screens, rules of the modes, minigames
- [TODO.md](TODO.md): all to-dos, sorted by milestone and area
- [FEATURES.md](FEATURES.md): overview of all features with their status
- [DECISIONS.md](DECISIONS.md): all decisions with reasons, plus the open questions
- [WORKFLOW.md](WORKFLOW.md): the five agents and the process from the to-do to the merge

## The three modes

| Mode | In short | Players |
|---|---|---|
| Classic | Everyone completes tasks on the campus. One or two Free Riders sabotage and make others “fail”. In meetings the players discuss and vote. | 4 to 8 |
| Duel | Everyone gets the same three minigames in the same order. Whoever completes them in one go first wins. | 2 to 8 |
| Deadline (proposal) | Everyone plays together against the clock: the group project must be finished before midnight, while random disruptions get in the way. No Free Rider. | 2 to 8 |

## The four areas

The areas have owners (S-96): area 1 Hanna, area 2 Felix, area 3 Laurin, area 4 Lennart.

| Area | Responsible for | Boundary to the others |
|---|---|---|
| 1 Campus and characters | Map with the five rooms, movement, collision, camera, characters, graphics and sound | Delivers positions and “player is at station X”. What happens at the station belongs to area 3 or 4. |
| 2 Network, lobby and foundation | Server, lobby with code, synchronisation of the game states, reconnecting, message format, tests, CI, hosting, pull requests | Transports messages, but does not know any game rules. |
| 3 Classic rules | Roles, failing someone, reporting, meeting, chat, vote, sabotage, win conditions | Only asks area 4 “task done?”. |
| 4 Minigames and extra modes | Frame for minigames, all minigames, Duel mode, Deadline mode | Reports “done” to the server. Does not know any roles. |

## Structure

Every file belongs to exactly one area. Folders without “exists” are created with their first to-do.

| Folder or file | Content | Area |
|---|---|---|
| `server/main.py` (exists) | Web server, WebSocket connection, security headers | 2 |
| `server/protocol.py` (exists) | Validation of every message from the browser | 2 |
| `server/net/` | Lobby, synchronisation of the players | 2 |
| `server/accounts/` | Accounts, statistics, friends | 2 |
| `server/classic/` | Rules of the Classic mode as pure functions | 3 |
| `server/modes/` | Duel and Deadline | 4 |
| `client/index.html`, `client/css/` (exists) | Page skeleton and colours | 2 |
| `client/js/main.js` (exists) | Connection to the server | 2 |
| `client/js/world/` | Map, movement, camera, characters | 1 |
| `client/js/lobby/` | Login and lobby | 2 |
| `client/js/classic/` | Meeting, chat, vote, role display | 3 |
| `client/js/minigames/` | Frame and one file per minigame | 4 |
| `tests/` (exists) | Tests with pytest | 2 (frame), every area for its own tests |
| `requirements.txt` (exists) | Dependencies with pinned versions | 2 |

The rules for all agents are in the [AGENTS.md](../AGENTS.md) in the main folder, the four agents under `.claude/agents/`.
