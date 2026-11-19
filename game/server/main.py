"""The web server: serves the game page and holds the WebSocket connections.

Start it from the `game` folder:

    uvicorn server.main:app --reload

This file only moves messages. Game rules live in their own modules as plain
functions, so they can be tested without a network.
"""

import asyncio
import logging
import os
import random
import string
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from server import protocol
from server.accounts import service
from server.accounts.store import make_account_store
from server.net.lobbies import Lobbies
from server.net.sessions import GUEST_NUMBERS, Sessions
from server.protocol import PROTOCOL_VERSION, ProtocolError, error, parse_client_message, welcome

logger = logging.getLogger(__name__)

CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Only our own files may load. The game needs no outside scripts, fonts or images.
    "Content-Security-Policy": "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:",
}

# The automatic API pages are switched off: the game has no public API to document.
app = FastAPI(title="Group Project", docs_url=None, redoc_url=None, openapi_url=None)

# Kept on `app.state` so the tests can put their own in. Accounts live in
# Postgres when DATABASE_URL is set (never print it: it holds the password),
# otherwise in memory. Creating the store does not connect to anything yet.
app.state.account_store = make_account_store(os.environ.get("DATABASE_URL"))
app.state.hasher = service.Argon2Hasher()
app.state.sessions = Sessions()
app.state.lobbies = Lobbies()

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
        # The movement message is not answered yet.


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
        await websocket.send_json(protocol.rejection(rejection_code))


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
    return protocol.lobby_state(lobby.code, lobby.host, lobby.players())


async def send_to(name: str, message: dict) -> bool:
    """Send a message to the player with this name. Never raises.

    Returns whether the message was handed over. If not, that player's
    connection is going away: its own handler notices that and takes the
    player out of the lobby. The other members must still get their messages.
    """
    connection = app.state.sessions.connection_of(name)
    if connection is None:
        return False
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
}


# Mounted last, so /health and /ws win over files of the same name.
app.mount("/", StaticFiles(directory=CLIENT_DIR, html=True), name="client")
