# Group Project

A multiplayer browser game set on the Nova SBE campus in Carcavelos. Everyone is working on the group project. One of you is only pretending.

Two to eight players join a lobby with a four-letter code. The **High Performers** walk across the campus and complete tasks, each one a short minigame. The **Free Rider** pretends to work and quietly fails the others. Find the Free Rider and vote them out before the group project falls apart.

Team project for Introduction to Programming (course 2477), Nova SBE, 2026.

## Play it

**Deployed URL:** https://itp-group.onrender.com

The game runs on a free Render instance that goes to sleep when nobody visits. The first visit after a pause can take about a minute to load.

## Team

| Name | Student number | Area |
|---|---|---|
| Hanna Schlesiger | 78153 | 1 Campus and characters |
| Felix Donder | 75246 | 2 Network, lobby, accounts, foundation |
| Laurin Dusel | 81263 | 3 Classic rules |
| Lennart Schmülling | 79898 | 4 Minigames and other modes |

## Run it locally

You need Python 3.13 or newer. Run all commands from the `game` folder.

Set up once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

Start the game, then open http://localhost:8000:

```bash
.venv/bin/uvicorn server.main:app --reload
```

Run the tests:

```bash
.venv/bin/python -m pytest
```

Check the dependencies for known vulnerabilities:

```bash
.venv/bin/pip-audit -r requirements.txt
```

To see several players at once, open the page in two or more browser windows.

## The modes

| Mode | Players | What happens |
|---|---|---|
| Classic | 4 to 8 | Complete tasks, find the Free Rider, discuss and vote in meetings. With 6 to 8 players there are two Free Riders. |
| Duel | 2 to 8 | Everyone gets their own random route across three task stations. The first to finish all three wins. |
| Deadline | 2 to 8 | Everyone plays together against the clock while disruptions get in the way. Built only if time allows. |

## What works today

As of 2026-11-19: accounts and guests, lobbies with a four-letter code, walking across the campus together, five minigames, a complete Duel round with ranking, and a profile and leaderboard for accounts. The Classic mode with the Free Rider, meetings and votes is being built. The status of every feature is in [game/FEATURES.md](game/FEATURES.md).

## The four areas

The work is split into four areas. Every file belongs to exactly one of them, and each area has one owner.

| Area | Owner | Responsible for | Code |
|---|---|---|---|
| 1 Campus and characters | Hanna | The map with its rooms, walking, collision, camera, characters, graphics | `game/client/js/world/`, `game/server/world/` |
| 2 Network, lobby, accounts, foundation | Felix | Server, WebSocket connection, message checks, lobby, accounts and statistics, tests, CI, hosting | `game/server/main.py`, `game/server/protocol.py`, `game/server/net/`, `game/server/accounts/`, `game/client/js/net.js`, `game/client/js/lobby/` |
| 3 Classic rules | Laurin | Roles, failing someone, reporting, meetings, chat, votes, win conditions | `game/server/classic/`, `game/client/js/classic/` |
| 4 Minigames and other modes | Lennart | The frame for minigames, all minigames, the Duel and Deadline modes | `game/server/modes/`, `game/client/js/minigames/` |

## How it is built

| Part | Where | What it does |
|---|---|---|
| Server | `game/server/` | Python with FastAPI. Serves the page, holds one WebSocket connection per player, and decides everything that matters: roles, positions, votes, results. |
| Message checks | `game/server/protocol.py` | Every message from a browser is checked for size, shape and allowed values before any game code sees it. |
| Client | `game/client/` | Plain HTML, CSS and JavaScript drawing on a canvas. No framework and no build step. It sends what the player wants to do and draws what the server reports. |
| Tests | `game/tests/` | pytest. Accepted actions, rejected actions and edge cases. They run on every pull request. |
| Data | Supabase (Postgres) | Accounts and statistics. Lobbies and running rounds live only in the server's memory and are gone after a restart. |

No credentials are stored in this repository. The server reads the database connection from the environment variable `DATABASE_URL`.

## Documents

- [game/DESIGN.md](game/DESIGN.md): look, map, characters, screens, rules of every mode, minigames
- [game/DECISIONS.md](game/DECISIONS.md): every decision with its reason, including the ones we later replaced
- [game/FEATURES.md](game/FEATURES.md): every feature and its status
- [game/TODO.md](game/TODO.md): open and finished to-dos
- [game/WORKFLOW.md](game/WORKFLOW.md): how we work with coding agents
- [AGENTS.md](AGENTS.md): the rules every coding agent follows in this repository

## About this repository

The folder `prototype/`, the folder `tests/` and the files `TODO.md`, `DECISIONS.md` and `FEATURES.md` in the root belong to an earlier idea, the betting app "We Be(a)t". We dropped it in favour of the game. They are not part of the deployed application and will move to an `archive/` folder before submission.
