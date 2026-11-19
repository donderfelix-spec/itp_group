"""The web server: serves the game page and holds the WebSocket connections.

Start it from the `game` folder:

    uvicorn server.main:app --reload

This file only moves messages. Game rules live in their own modules as plain
functions, so they can be tested without a network.
"""

import asyncio
import contextlib
import logging
import os
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from server import protocol
from server.accounts import service
from server.accounts.store import make_account_store
from server.modes import tasks
from server.net.lobbies import Lobbies
from server.net.sessions import GUEST_NUMBERS, Sessions
from server.protocol import PROTOCOL_VERSION, ProtocolError, error, parse_client_message, welcome
from server.world.campus import load_campus

logger = logging.getLogger(__name__)

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Only our own files may load. The game needs no outside scripts, fonts or images.
    "Content-Security-Policy": "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:",
}


@contextlib.asynccontextmanager
async def lifespan(app):
    """The tick loop starts with the server and stops with it."""
    ticking = asyncio.create_task(run_ticks())
    yield
    ticking.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await ticking


# The automatic API pages are switched off: the game has no public API to document.
app = FastAPI(title="Group Project", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

# Kept on `app.state` so the tests can put their own in. Accounts live in
# Postgres when DATABASE_URL is set (never print it: it holds the password),
# otherwise in memory. Creating the store does not connect to anything yet.
app.state.account_store = make_account_store(os.environ.get("DATABASE_URL"))
app.state.hasher = service.Argon2Hasher()
app.state.sessions = Sessions()
app.state.lobbies = Lobbies()
# The map is read once, when the server starts. A broken map file stops the
# start with a clear message, which is better than a game without walls.
app.state.campus = load_campus()

# Hashing a password and asking the database both take a while, so they run in
# worker threads and do not freeze the game for every other player. There are
# only two workers on purpose: one Argon2 hash needs 64 MiB of memory, and the
# host has 512 MB. Python's default of up to 32 threads at once could use it all.
# With two, further log-ins simply wait their turn.
account_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="accounts")

# Sends that run on their own (see `tell_signed_out_later`). Python may throw
# away a running task nobody refers to, so they are kept here until they finish.
background_sends = set()


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


@app.get("/health")
def health():
    """Used by the host and by the tests to see that the server is up."""
    return {"status": "ok", "protocol": PROTOCOL_VERSION}


@app.websocket("/ws")
async def game_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        await read_messages(websocket)
    except (WebSocketDisconnect, RuntimeError) as problem:
        # Sending to a player who has just gone raises one of these two. That
        # is normal life on a network, not a fault: the handler simply ends.
        logger.info("Connection ended while sending: %s", type(problem).__name__)
    finally:
        # A closed connection is forgotten: its guest name is free again and
        # its player leaves the lobby. A connection that was replaced by a
        # newer log-in (S-76) has no name any more, so nothing happens here.
        name = app.state.sessions.name_of(websocket)
        app.state.sessions.sign_out(websocket)
        if name is not None:
            await take_out_of_lobby(name)


async def read_messages(websocket: WebSocket):
    """Answer the messages of one connection until it closes."""
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return
        try:
            message = parse_client_message(frame.get("text"))
        except ProtocolError as problem:
            # A bad message is answered, not punished: the connection stays open.
            await websocket.send_json(error(problem))
            continue
        if message["type"] == "hello":
            await websocket.send_json(welcome(message["name"]))
        elif message["type"] in ACCOUNT_HANDLERS:
            await answer_account_message(websocket, message)
        elif message["type"] in LOBBY_HANDLERS:
            await answer_lobby_message(websocket, message)
        elif message["type"] == "move":
            await answer_move_message(websocket, message)
        elif message["type"] in TASK_HANDLERS:
            await answer_task_message(websocket, message)


async def answer_account_message(websocket: WebSocket, message: dict):
    """Run the handler for an account message and send its answer.

    A handler returns None when it has already sent everything itself.
    """
    handler = ACCOUNT_HANDLERS[message["type"]]
    answer = await handler(websocket, message)
    if answer is not None:
        await websocket.send_json(answer)


async def handle_sign_up(websocket: WebSocket, message: dict):
    return await sign_in_with(service.sign_up, websocket, message)


async def handle_log_in(websocket: WebSocket, message: dict):
    return await sign_in_with(service.log_in, websocket, message)


async def sign_in_with(rule, websocket: WebSocket, message: dict):
    """Shared by sign-up and log-in. `rule` is `service.sign_up` or `service.log_in`.

    Returns the rejection to send, or None after a successful sign-in (which
    sends its own answer, because the order of the steps matters there).
    """
    sessions = app.state.sessions
    if sessions.is_signed_in(websocket):
        return protocol.rejection("already_signed_in")
    name, rejection_code = await run_account_rule(rule, message["name"], message["password"])
    if rejection_code is not None:
        return protocol.rejection(rejection_code)

    # The player may have left while the password was being checked. A
    # connection that is gone must not be signed in: it would push a living
    # session of the same account out.
    if not is_connected(websocket):
        return None
    # Answer first, sign in second. If this send fails, the player is gone,
    # the handler ends here and nobody else has been signed out for nothing.
    await websocket.send_json(protocol.signed_in(name, guest=False))
    replaced = sessions.sign_in_account(websocket, name)
    if replaced is not None:
        tell_signed_out_later(replaced)
        # The old connection's place in a lobby is given up: the new
        # connection starts outside of any lobby.
        await take_out_of_lobby(name)
    return None


async def run_account_rule(rule, name: str, password: str):
    """Run a rule from `service` on the account workers. Returns `(name, rejection_code)`."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            account_workers, rule, app.state.account_store, app.state.hasher, name, password
        )
    except Exception as problem:
        # Nothing in the account code may close the connection or stop the
        # server. Only the kind of error is logged, never a password or URL.
        logger.error("Account rule %s failed: %s", rule.__name__, type(problem).__name__)
        return (None, "accounts_unavailable")


def is_connected(websocket: WebSocket) -> bool:
    """Whether the server still believes the player is there.

    The server only notices a closed connection when it next reads or sends,
    so True is not a promise. False is certain.
    """
    connected = WebSocketState.CONNECTED
    return websocket.client_state == connected and websocket.application_state == connected


def tell_signed_out_later(replaced: WebSocket):
    """Tell a connection that lost its account to a newer log-in (S-76).

    This runs as its own task, so a slow or broken old connection cannot hold
    up the player who has just logged in.
    """
    task = asyncio.create_task(tell_signed_out(replaced))
    background_sends.add(task)
    task.add_done_callback(background_sends.discard)


async def tell_signed_out(replaced: WebSocket):
    try:
        await replaced.send_json(protocol.signed_out())
    except Exception:
        # The old connection may already be gone. Nobody is waiting for this message.
        pass


async def handle_guest(websocket: WebSocket, message: dict):
    sessions = app.state.sessions
    if sessions.is_signed_in(websocket):
        return protocol.rejection("already_signed_in")
    name = sessions.sign_in_guest(websocket, pick_guest_number)
    if name is None:
        # Every guest name is in use. There is no text of its own for this.
        return protocol.rejection("accounts_unavailable")
    return protocol.signed_in(name, guest=True)


def pick_guest_number() -> int:
    return random.randrange(GUEST_NUMBERS)


async def handle_log_out(websocket: WebSocket, message: dict):
    name = app.state.sessions.name_of(websocket)
    if not app.state.sessions.sign_out(websocket):
        return protocol.rejection("not_signed_in")
    await take_out_of_lobby(name)
    return protocol.signed_out()


ACCOUNT_HANDLERS = {
    "sign_up": handle_sign_up,
    "log_in": handle_log_in,
    "guest": handle_guest,
    "log_out": handle_log_out,
}


# The lobby. The rules are in `server/net/lobbies.py`; the functions here only
# ask them and send the answers.

# How long one send to a lobby member may take. A browser that has stopped
# reading would otherwise keep everybody else in its lobby waiting.
SEND_TIMEOUT_SECONDS = 2


async def answer_lobby_message(websocket: WebSocket, message: dict):
    """Run the handler for a lobby message. A handler returns a rejection code or None."""
    name = app.state.sessions.name_of(websocket)
    if name is None:
        await websocket.send_json(protocol.rejection("not_signed_in"))
        return
    handler = LOBBY_HANDLERS[message["type"]]
    rejection_code = await handler(websocket, name, message)
    if rejection_code is not None:
        await websocket.send_json(rejection_for(name, rejection_code))


def rejection_for(name: str, rejection_code: str) -> dict:
    """The error message for a lobby action the rules refused."""
    if rejection_code == "too_few_players":
        # The only rejection without a fixed text: it names the lobby's mode.
        return protocol.too_few_players(app.state.lobbies.lobby_of(name).mode)
    return protocol.rejection(rejection_code)


async def handle_create_lobby(websocket: WebSocket, name: str, message: dict):
    lobby, rejection_code = app.state.lobbies.create(name, pick_lobby_code)
    if rejection_code is None:
        await tell_lobby(lobby)
    return rejection_code


def pick_lobby_code() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=4))


async def handle_join_lobby(websocket: WebSocket, name: str, message: dict):
    lobby, rejection_code = app.state.lobbies.join(name, message["code"])
    if rejection_code is None:
        await tell_lobby(lobby)
    return rejection_code


async def handle_choose_character(websocket: WebSocket, name: str, message: dict):
    lobby, changed, rejection_code = app.state.lobbies.choose_character(name, message["character"])
    if rejection_code is not None:
        return rejection_code
    if changed:
        await tell_lobby(lobby)
    else:
        # The player chose the character they already have. Nothing is new
        # for the others, so only the player gets an answer.
        await websocket.send_json(state_of(lobby))
    return None


async def handle_choose_mode(websocket: WebSocket, name: str, message: dict):
    lobby, rejection_code = app.state.lobbies.choose_mode(name, message["mode"])
    if rejection_code is None:
        await tell_lobby(lobby)
    return rejection_code


async def handle_start_game(websocket: WebSocket, name: str, message: dict):
    # The new state with phase "round" is the news that the round started;
    # there is no message of its own for it (S-91). The next tick sends
    # everybody's position on the spawn.
    lobby, rejection_code = app.state.lobbies.start(name)
    if rejection_code is None:
        # A new round begins with no task open and nothing finished.
        campus = app.state.campus
        lobby.tasks = tasks.RoundTasks(campus["stations"], campus["use_range"])
        await tell_lobby(lobby)
    return rejection_code


async def handle_leave_lobby(websocket: WebSocket, name: str, message: dict):
    lobby, new_host, rejection_code = app.state.lobbies.leave(name)
    if rejection_code is None:
        await websocket.send_json(protocol.left_lobby())
        await tell_lobby(lobby, new_host)
    return rejection_code


async def take_out_of_lobby(name: str):
    """For a player who logs out, disconnects or is replaced: leave the lobby, if in one.

    The player gets no message about it. The players who stay are told.
    """
    lobby, new_host, rejection_code = app.state.lobbies.leave(name)
    if rejection_code is None:
        await tell_lobby(lobby, new_host)


async def tell_lobby(lobby, new_host=None):
    """Send every member the lobby's state, after a notice if `new_host` took over.

    All members are told at the same time, so one slow connection does not
    make the others wait. A send never takes longer than SEND_TIMEOUT_SECONDS
    and never raises (see `send_to`).
    """
    await asyncio.gather(*(tell_member(name, lobby, new_host) for name in lobby.names()))


async def tell_member(name: str, lobby, new_host):
    """Send one member the notice about the new host (if any), then the lobby's state.

    While a send waits, other players can join or leave. So membership is
    checked before every send, and the state is read only at that moment:
    nobody outside the lobby is told and nobody gets outdated news.
    """
    # If the host has changed again in the meantime, the notice is skipped:
    # it would name a host who is not the host any more.
    if new_host is not None and is_member(name, lobby) and lobby.host == new_host:
        delivered = await send_to(name, protocol.notice(f"The host left. {new_host} is the new host."))
        if not delivered:
            return
    if is_member(name, lobby):
        await send_to(name, state_of(lobby))


def is_member(name: str, lobby) -> bool:
    return app.state.lobbies.lobby_of(name) is lobby


def state_of(lobby) -> dict:
    return protocol.lobby_state(lobby.code, lobby.host, lobby.players(), lobby.mode, lobby.phase)


async def send_to(name: str, message: dict) -> bool:
    """Send a message to the player with this name. Never raises.

    Returns whether the message was handed over. If not, that player's
    connection is going away: its own handler notices that and takes the
    player out of the lobby. The other members must still get their messages.
    """
    connection = app.state.sessions.connection_of(name)
    if connection is None:
        return False
    return await send_on(connection, message)


async def send_on(connection, message: dict) -> bool:
    """Send a message on this connection, with the time limit. Never raises."""
    try:
        await asyncio.wait_for(connection.send_json(message), SEND_TIMEOUT_SECONDS)
        return True
    except TimeoutError:
        # The browser has stopped reading. The connection is closed, so it
        # cannot hold up the lobby again at the next change.
        await close_stuck_connection(connection)
    except Exception as problem:
        logger.info("Could not send to a player: %s", type(problem).__name__)
    return False


async def close_stuck_connection(connection):
    logger.info("A player's connection took too long and is closed.")
    try:
        await asyncio.wait_for(connection.close(), SEND_TIMEOUT_SECONDS)
    except Exception:
        # Closing can fail or hang for the same reason the send did. Nothing more can be done here.
        pass


LOBBY_HANDLERS = {
    "create_lobby": handle_create_lobby,
    "join_lobby": handle_join_lobby,
    "leave_lobby": handle_leave_lobby,
    "choose_character": handle_choose_character,
    "choose_mode": handle_choose_mode,
    "start_game": handle_start_game,
}


# Walking on the campus. The rules are in `server/net/walking.py` and
# `server/world/movement.py`; the functions here measure the time, ask the
# rules and send the positions.

# How often per second the server moves the players and tells their browsers (S-72).
TICKS_PER_SECOND = 15

# Connections that are still busy taking a positions message. Positions are
# replaceable: a newer message is better than a queue of old ones, so a busy
# connection is skipped until it is free again.
taking_positions = set()


async def answer_move_message(websocket: WebSocket, message: dict):
    """Remember the direction the player wants to walk. Only a rejection is answered."""
    name = app.state.sessions.name_of(websocket)
    if name is None:
        await websocket.send_json(protocol.rejection("not_signed_in"))
        return
    lobby = app.state.lobbies.lobby_of(name)
    if lobby is None:
        await websocket.send_json(protocol.rejection("not_in_lobby"))
        return
    # With a task open the player stands still (S-93). The message is not an
    # error: a key may have been pressed just before the window opened.
    if tasks.stands_still(lobby.tasks, name):
        return
    # The next tick moves the player. The browser sees the result in `positions`.
    lobby.walkers.set_direction(name, message["dx"], message["dy"])


async def run_ticks():
    """Call `tick` about TICKS_PER_SECOND times per second, until the server stops."""
    previous = time.monotonic()
    while True:
        await asyncio.sleep(1 / TICKS_PER_SECOND)
        now = time.monotonic()
        try:
            tick(now - previous)
        except Exception as problem:
            # `tick` already catches what goes wrong in one lobby. This is the
            # last line of defence: whatever else fails, the loop goes on and
            # the next tick tries again. Only the kind of error is logged.
            logger.error("A tick failed: %s", type(problem).__name__)
        previous = now


def tick(seconds: float):
    """Move the players of every lobby for `seconds` and tell them the news.

    This function never waits for a browser: every send runs as its own task.
    So a slow player cannot delay the tick or the other players.
    """
    for lobby in app.state.lobbies.all():
        try:
            if lobby.walkers.advance(seconds, app.state.campus):
                tell_positions(lobby)
        except Exception as problem:
            # A fault in one lobby must not freeze the lobbies after it.
            # Only the kind of error is logged.
            logger.error("The tick failed for one lobby: %s", type(problem).__name__)


def tell_positions(lobby):
    """Start sending the lobby's positions to every member who needs them and is free."""
    message = protocol.positions(lobby.walkers.positions())
    for name in lobby.walkers.names_to_tell():
        connection = app.state.sessions.connection_of(name)
        if connection is None or connection in taking_positions:
            # Not marked as told: this player gets the newest positions at a
            # later tick, as soon as the connection is free.
            continue
        lobby.walkers.mark_told(name)
        taking_positions.add(connection)
        task = asyncio.create_task(send_positions(name, connection, lobby, message))
        background_sends.add(task)
        task.add_done_callback(background_sends.discard)


async def send_positions(name: str, connection, lobby, message: dict):
    """Send one member the positions. Runs as its own task, started by `tell_positions`."""
    try:
        # The player may have left, or logged in elsewhere, in the short
        # moment before this task started. Then the positions are not theirs
        # to see any more.
        still_there = is_member(name, lobby) and app.state.sessions.connection_of(name) is connection
        if still_there:
            await send_on(connection, message)
    finally:
        taking_positions.discard(connection)


# The tasks at the stations (S-93). The rules are in `server/modes/tasks.py`;
# the functions here measure the time, ask the rules and build the answers.
# Only the acting player is answered: nobody else hears about a task.


def seconds_now() -> float:
    """The server's clock for the tasks. A function of its own, so tests can replace it."""
    return time.monotonic()


async def answer_task_message(websocket: WebSocket, message: dict):
    """Run the handler for a task message and send the player its answers."""
    name = app.state.sessions.name_of(websocket)
    if name is None:
        await websocket.send_json(protocol.rejection("not_signed_in"))
        return
    lobby = app.state.lobbies.lobby_of(name)
    if lobby is None:
        await websocket.send_json(protocol.rejection("not_in_lobby"))
        return
    try:
        answers = TASK_HANDLERS[message["type"]](lobby, name, message)
    except Exception as problem:
        # A fault in a minigame must not close the player's connection.
        # Only the kind of error is logged.
        logger.error("The task message %s failed: %s", message["type"], type(problem).__name__)
        answers = answers_after_fault(lobby, name)
    for answer in answers:
        await websocket.send_json(answer)


def answers_after_fault(lobby, name: str) -> list:
    """What the player is told when a task handler failed.

    The browser waits for an answer to every task message, so it always gets
    one. The fault may have happened after the task was opened: then the task
    is forgotten and the browser is told, so page and server agree again.
    """
    answers = [protocol.rejection("task_failed")]
    station, _ = tasks.close_station(lobby.tasks, name)
    if station is not None:
        answers.append(protocol.station_closed(station))
    return answers


def handle_open_station(lobby, name: str, message: dict) -> list:
    position = lobby.walkers.position_of(name)
    opened, rejection_code = tasks.open_station(
        lobby.tasks, name, message["station"], position, seconds_now(), random
    )
    if rejection_code is not None:
        return [protocol.rejection(rejection_code)]
    # The player stands still while the task is open, so "in range" stays
    # true until it ends. `answer_move_message` ignores `move` until then.
    lobby.walkers.set_direction(name, 0, 0)
    return [protocol.station_opened(opened["station"], opened["title"], opened["content"])]


def handle_close_station(lobby, name: str, message: dict) -> list:
    station, rejection_code = tasks.close_station(lobby.tasks, name)
    if rejection_code is not None:
        return [protocol.rejection(rejection_code)]
    return [protocol.station_closed(station)]


def handle_finish_station(lobby, name: str, message: dict) -> list:
    station, rejection_code = tasks.finish_station(lobby.tasks, name, seconds_now())
    if rejection_code == "too_fast":
        # The task is closed without counting. The error comes first, then
        # the news that lets the browser close its window.
        return [protocol.rejection(rejection_code), protocol.station_closed(station)]
    if rejection_code is not None:
        return [protocol.rejection(rejection_code)]
    return [protocol.station_done(station)]


TASK_HANDLERS = {
    "open_station": handle_open_station,
    "close_station": handle_close_station,
    "finish_station": handle_finish_station,
}


# Mounted last, so /health and /ws win over files of the same name.
app.mount("/", StaticFiles(directory=CLIENT_DIR, html=True), name="client")
