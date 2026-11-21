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
from server.accounts import service, statistics
from server.accounts.leaderboard_cache import LeaderboardCache
from server.accounts.statistics_store import make_statistics_store
from server.accounts.store import StoreUnavailable, make_account_store
from server.modes import duel, minigames, tasks
from server.net.attempts import AttemptLimits
from server.net.lobbies import Lobbies
from server.net.repeated_faults import RepeatedFaults
from server.net.sessions import GUEST_NUMBERS, Sessions
from server.protocol import PROTOCOL_VERSION, ProtocolError, error, parse_client_message, welcome
from server.world.visibility import visible_positions
from server.world import paths
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
# Statistics live next to the accounts: in Postgres or in memory (S-39).
app.state.statistics_store = make_statistics_store(os.environ.get("DATABASE_URL"))
# The last answer for the leaderboard, kept for a few seconds, and the
# question to the store that is running right now, as `(store, task)` or None
# (see `leaderboard_totals`).
app.state.leaderboard_cache = LeaderboardCache()
app.state.leaderboard_call = None
app.state.hasher = service.Argon2Hasher()
app.state.sessions = Sessions()
app.state.attempt_limits = AttemptLimits()
app.state.lobbies = Lobbies()
# Which faults of the tick were logged lately, so that a repeating fault does not flood the log.
app.state.repeated_faults = RepeatedFaults()
# The map is read once, when the server starts. A broken map file stops the
# start with a clear message, which is better than a game without walls.
app.state.campus = load_campus()
# How far a player walks from the spawn to every station in use and between
# them (S-94). Measured once, here: it takes about a third of a second, too
# long to repeat at every start of a round. A station nobody can walk to
# stops the start of the server, like a broken map.
app.state.distances = paths.station_distances(app.state.campus, sorted(minigames.MINIGAMES))

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
        app.state.attempt_limits.forget(websocket)
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
        elif message["type"] in STATISTICS_HANDLERS:
            await answer_statistics_message(websocket, message)
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
    if app.state.sessions.is_signed_in(websocket):
        return protocol.rejection("already_signed_in")
    # Asked before the password is hashed: one hash costs 64 MiB of memory
    # and a worker thread, so a guessing script must not get that far (M1-2.6).
    limits = app.state.attempt_limits
    if limits.is_blocked(websocket, "log_in", seconds_now()):
        return protocol.rejection("too_many_attempts")
    answer = await sign_in_with(service.log_in, websocket, message)
    # Only a wrong name or password is a guess. A database that is down is not.
    if answer is not None and answer["code"] == "wrong_credentials":
        limits.failed(websocket, "log_in", seconds_now())
    return answer


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


# Statistics (S-40). The rules are in `server/accounts/statistics.py`; the
# functions here ask the store on the account workers and send the answers.

async def answer_statistics_message(websocket: WebSocket, message: dict):
    """Run the handler for a statistics message and send its answer."""
    handler = STATISTICS_HANDLERS[message["type"]]
    await websocket.send_json(await handler(websocket))


async def handle_get_profile(websocket: WebSocket) -> dict:
    """The profile of the account this connection is signed in with, never of anybody else."""
    sessions = app.state.sessions
    name = sessions.name_of(websocket)
    if name is None:
        return protocol.rejection("not_signed_in")
    if sessions.is_guest(websocket):
        return protocol.rejection("guest_no_statistics")
    records = await ask_statistics_store(app.state.statistics_store.records_of, name)
    if records is None:
        return protocol.rejection("statistics_unavailable")
    rows = statistics.profile_rows(records, protocol.MODES)
    return protocol.profile(name, rows, statistics.best_duel_seconds(records))


async def handle_get_leaderboard(websocket: WebSocket) -> dict:
    """The leaderboard, for accounts and guests alike."""
    if not app.state.sessions.is_signed_in(websocket):
        return protocol.rejection("not_signed_in")
    totals = await leaderboard_totals()
    if totals is None:
        return protocol.rejection("statistics_unavailable")
    # Cut again here: whatever a store returns, nobody gets more than 20 rows.
    return protocol.leaderboard(statistics.leaderboard_rows(totals[: statistics.LEADERBOARD_SIZE]))


async def leaderboard_totals():
    """The accounts of the leaderboard, best first, or None when the statistics cannot be used.

    The store is asked at most once in 10 seconds (see `LeaderboardCache`).
    Players who ask while a question to the store is running wait for its
    answer instead of starting a question of their own.
    """
    store = app.state.statistics_store
    cached = app.state.leaderboard_cache.get(store, seconds_now())
    if cached is not None:
        return cached
    running = app.state.leaderboard_call
    if running is None or running[0] is not store or running[1].done():
        running = (store, asyncio.create_task(load_leaderboard(store)))
        app.state.leaderboard_call = running
    # `shield`: if this player leaves while waiting, the question goes on
    # for the others who wait for the same answer.
    return await asyncio.shield(running[1])


async def load_leaderboard(store):
    """Ask the store for the leaderboard and keep its answer. Never raises. A failure is not kept."""
    cache = app.state.leaderboard_cache
    ticket = cache.ticket()
    totals = await ask_statistics_store(store.top, statistics.LEADERBOARD_SIZE)
    if totals is not None:
        # Refused by the cache if a result was written in the meantime:
        # this answer may be older than that result.
        cache.put(store, totals, seconds_now(), ticket)
    return totals


def forget_leaderboard():
    """The numbers have changed: the next look at the leaderboard asks the store again."""
    app.state.leaderboard_cache.drop()
    # A question that is still running may be answered with the old
    # numbers, so nobody new waits for it.
    app.state.leaderboard_call = None


async def ask_statistics_store(method, *values):
    """Call a method of the statistics store on the account workers. Never raises.

    Returns the method's answer, or None when the statistics cannot be used
    right now. The database takes a while, so it must not run on the event
    loop, where it would freeze the game for every other player.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(account_workers, method, *values)
    except StoreUnavailable:
        # The store has logged the reason already (S-90).
        return None
    except Exception as problem:
        # Only the kind of error is logged, never its text: that could
        # contain details of the connection to the database.
        logger.error("The statistics store failed in %s: %s", method.__name__, type(problem).__name__)
        return None


def duel_result_to_write(lobby, ranking):
    """What a finished Duel adds to the statistics, as `(mode, changes)`. Never raises.

    Returns None when there is nothing to write (only guests played). Called
    at the one place a round ends, so each round gives exactly one result.
    Nothing is written here: that happens later and off the event loop (see
    `write_result_later`), so the end of the round is not delayed.
    """
    try:
        changes = statistics.changes_from_duel(ranking, account_names(lobby.names()))
        return (statistics.DUEL, changes) if changes else None
    except Exception as problem:
        # Statistics must never keep a round from ending.
        logger.error("The result of a round could not be noted: %s", type(problem).__name__)
        return None


def account_names(names) -> set:
    """Those of `names` who are signed in with an account. Guests have no statistics (S-38).

    The server's own list of sessions decides who is a guest, never
    anything the browser says.
    """
    sessions = app.state.sessions
    accounts = set()
    for name in names:
        connection = sessions.connection_of(name)
        if connection is not None and not sessions.is_guest(connection):
            accounts.add(name)
    return accounts


def write_result_later(result):
    """Start writing one round's result, `(mode, changes)` or None, as a task of its own."""
    if result is not None:
        mode, changes = result
        run_in_background(write_result(mode, changes))


async def write_result(mode: str, changes: list):
    # If the database cannot be reached, the result of this round is lost.
    # The store has logged why; the round itself ended long before.
    await ask_statistics_store(app.state.statistics_store.record_round, mode, changes)
    # Also after a failed write: it costs one question to the store, and
    # nobody has to work out here what a failure left behind.
    forget_leaderboard()


STATISTICS_HANDLERS = {
    "get_profile": handle_get_profile,
    "get_leaderboard": handle_get_leaderboard,
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
    # Lobby codes have four letters, so they could be guessed by trying (M1-2.6).
    limits = app.state.attempt_limits
    if limits.is_blocked(websocket, "join_lobby", seconds_now()):
        return "too_many_attempts"
    lobby, rejection_code = app.state.lobbies.join(name, message["code"])
    if rejection_code is None:
        await tell_lobby(lobby)
    # Only a code that does not exist is a guess. A full or running lobby is not.
    if rejection_code == "no_lobby":
        limits.failed(websocket, "join_lobby", seconds_now())
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
    # The round does not start here: the lobby counts down first (S-102),
    # and the tick starts the round when the countdown is over (see
    # `start_round_if_due`). Until then nothing of the round exists.
    lobby, rejection_code = app.state.lobbies.start(name, seconds_now())
    if rejection_code is None:
        await tell_lobby(lobby)
        await tell_countdown(lobby)
    return rejection_code


async def tell_countdown(lobby):
    """After the lobby's state with phase "countdown": tell every member how long it is."""
    await asyncio.gather(*(tell_member_the_countdown(name, lobby) for name in lobby.names()))


async def tell_member_the_countdown(name: str, lobby):
    # Asked right before the send, like in `tell_member`: the countdown may
    # have been cancelled in the meantime, or the player may have left.
    if is_member(name, lobby) and lobby.countdown_is_running():
        await send_to(name, protocol.countdown(lobby.countdown_seconds_left(seconds_now())))


async def handle_leave_lobby(websocket: WebSocket, name: str, message: dict):
    lobby, new_host, rejection_code = app.state.lobbies.leave(name)
    if rejection_code is None:
        await websocket.send_json(protocol.left_lobby())
        await tell_lobby(lobby, new_host)
        # The round goes on without this player, or ends if nobody is left to wait for.
        await tell_round_news(lobby)
    return rejection_code


async def take_out_of_lobby(name: str):
    """For a player who logs out, disconnects or is replaced: leave the lobby, if in one.

    The player gets no message about it. The players who stay are told.
    """
    lobby, new_host, rejection_code = app.state.lobbies.leave(name)
    if rejection_code is None:
        await tell_lobby(lobby, new_host)
        await tell_round_news(lobby)


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
            log_tick_fault("A tick failed", None, problem)
        previous = now


def log_tick_fault(what_failed: str, lobby_code, problem: Exception):
    """Log a fault of the tick, but not every time the same fault repeats.

    The tick runs many times per second, so a lobby that fails on every tick
    would flood the log. The same fault (the same place in the same lobby) is
    logged at once the first time and then at most once a minute, with the
    number of times it happened in between. Only the kind of error is logged.
    """
    log_it, swallowed = app.state.repeated_faults.happened((what_failed, lobby_code), seconds_now())
    if not log_it:
        return
    kind = type(problem).__name__
    if swallowed:
        logger.error("%s: %s (and %d more times since the last such line)", what_failed, kind, swallowed)
    else:
        logger.error("%s: %s", what_failed, kind)


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
            log_tick_fault("The tick failed for one lobby", lobby.code, problem)
        try:
            # A countdown that is over starts its round here (S-102). A try
            # of its own, like the end of a round below.
            if start_round_if_due(lobby):
                run_in_background(tell_round_begins(lobby))
        except Exception as problem:
            logger.error("The start of a round failed: %s", type(problem).__name__)
        try:
            # A round whose time is up ends here, with no message from a
            # browser needed. A try of its own: a fault in the walking above
            # must not keep a round from ending.
            farewells, result = end_round_if_over(lobby)
            if farewells:
                run_in_background(tell_round_ended(lobby, farewells, result))
        except Exception as problem:
            log_tick_fault("The check for the end of a round failed", lobby.code, problem)


def tell_positions(lobby):
    """Start sending the lobby's positions to every member who needs them and is free."""
    positions = lobby.walkers.positions()
    for name in lobby.walkers.names_to_tell():
        connection = app.state.sessions.connection_of(name)
        if connection is None or connection in taking_positions:
            # Not marked as told: this player gets the newest positions at a
            # later tick, as soon as the connection is free.
            continue
        lobby.walkers.mark_told(name)
        taking_positions.add(connection)
        message = protocol.positions(visible_positions(positions, name, app.state.campus))
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
    """The server's clock for the tasks, the countdown, the rounds and the leaderboard's cache.

    A function of its own, so tests can replace it.
    """
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
    # The time of the round may have run out since the last tick. Then the
    # round ends first, and this message is answered with "No round is running."
    await tell_round_news(lobby)
    try:
        answers = TASK_HANDLERS[message["type"]](lobby, name, message)
    except Exception as problem:
        # A fault in a minigame must not close the player's connection.
        # Only the kind of error is logged.
        logger.error("The task message %s failed: %s", message["type"], type(problem).__name__)
        answers = answers_after_fault(lobby, name)
    for answer in answers:
        await websocket.send_json(answer)
    # After the player's own answers: the others hear about a counted task,
    # and the round ends if that was the last one.
    await tell_round_news(lobby)


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
    now = seconds_now()
    station, rejection_code = tasks.finish_station(lobby.tasks, name, now)
    if rejection_code == "too_fast":
        # The task is closed without counting. The error comes first, then
        # the news that lets the browser close its window.
        return [protocol.rejection(rejection_code), protocol.station_closed(station)]
    if rejection_code is not None:
        return [protocol.rejection(rejection_code)]
    # From here on the station is counted. Counted and told belong together
    # (M2-4.7a): if anything fails before the answers for the player are
    # complete, the count is taken back and the fault is passed on. The
    # player then gets "Something went wrong. Try again." and can play the
    # station again, instead of being left with a station that the server
    # counts but the browser still shows as open.
    try:
        return [protocol.station_done(station)] + count_for_the_mode(lobby, name, station, now)
    except Exception:
        take_back_the_count(lobby, name, station)
        raise


def count_for_the_mode(lobby, name: str, station: int, now: float) -> list:
    """Tell the round's mode about a counted task. Returns what the mode adds to the player's answers."""
    if lobby.duel is None:
        return []
    if not lobby.duel.station_done(name, station, now):
        # Cannot happen: the frame only opens the player's next station.
        raise RuntimeError("a station counted that is not the next one of the route")
    return [duel_state_of(lobby.duel, name)]


def take_back_the_count(lobby, name: str, station: int):
    """Undo the count of a task everywhere it was counted."""
    lobby.tasks.take_back(name, station)
    if lobby.duel is not None:
        lobby.duel.take_back(name, station)


TASK_HANDLERS = {
    "open_station": handle_open_station,
    "close_station": handle_close_station,
    "finish_station": handle_finish_station,
}


# The round of each mode. The rules of Duel are in `server/modes/duel.py`
# (S-94); the functions here ask them and send the news. A further mode gets
# its own line in ROUND_SETUPS, its own place in the lobby (like `lobby.duel`)
# and its own branch in the functions that ask `lobby.duel`.


def start_round_if_due(lobby) -> bool:
    """Start the lobby's round if its countdown is over (S-102). Returns whether the countdown ended.

    Called by the tick. This function does not wait for anything, and the
    rules change the phase before anything else happens: so one countdown
    starts exactly one round, also when a tick comes late or twice. The
    round is set up now, for the players who are in the lobby now.
    """
    try:
        if not lobby.start_round_if_due(seconds_now()):
            return False
        set_up_round(lobby)
    except Exception as problem:
        # Whatever failed, in the rules' own start or while the round was
        # set up: a round without its tasks could never end. The lobby is
        # open again instead, and the host can press "Start game" once
        # more. Only the kind of error is logged.
        logger.error("A round could not be started: %s", type(problem).__name__)
        lobby.end_round()
    return True


async def tell_round_begins(lobby):
    """The news that the round started: the lobby's state with phase "round", then what the mode tells.

    There is no message of its own for the start (S-91). The next tick
    sends everybody's position on the spawn. If the round could not be
    started, the state says that the lobby is open again, and nothing follows it.
    """
    await tell_lobby(lobby)
    await tell_round_started(lobby)


def set_up_round(lobby):
    """Give the lobby what a round of its mode needs. A new round begins with no task open and nothing finished."""
    ROUND_SETUPS[lobby.mode](lobby)


def set_up_duel(lobby):
    campus = app.state.campus
    routes = duel.draw_routes(lobby.names(), sorted(minigames.MINIGAMES), app.state.distances, random)
    lobby.duel = duel.Duel(routes, seconds_now())
    # The frame of the minigames asks the Duel which stations a player may
    # open: only the next one of their route.
    lobby.tasks = tasks.RoundTasks(
        campus["stations"], campus["use_range"], needed_stations=lobby.duel.stations_needed
    )


ROUND_SETUPS = {
    "duel": set_up_duel,
}


def duel_state_of(the_duel, name: str) -> dict:
    """The message about one player's own Duel. Only that player may get it."""
    next_station, done, seconds = the_duel.state_of(name)
    return protocol.duel_state(next_station, done, duel.STATIONS_PER_ROUTE, seconds)


def duel_progress_of(the_duel) -> dict:
    """The message about everybody's progress. It names no station, so everybody may get it."""
    seconds_left = the_duel.seconds_left(seconds_now())
    return protocol.duel_progress(the_duel.progress(), duel.STATIONS_PER_ROUTE, seconds_left)


def is_in_duel(name: str, lobby, the_duel) -> bool:
    """Whether this Duel is still running in the lobby and the player is still in it.

    Asked before every send, like `is_member`: while a send waits, the
    player can leave and the round can end.
    """
    return is_member(name, lobby) and lobby.duel is the_duel and name in the_duel.names()


async def tell_round_started(lobby):
    """After the lobby's state with phase "round": what the mode tells at the start."""
    the_duel = lobby.duel
    if the_duel is None:
        return
    the_duel.take_news()  # everybody is told right now
    await asyncio.gather(*(tell_duel_start(name, lobby, the_duel) for name in the_duel.names()))


async def tell_duel_start(name: str, lobby, the_duel):
    """Send one player their own first station, then everybody's progress."""
    if is_in_duel(name, lobby, the_duel):
        await send_to(name, duel_state_of(the_duel, name))
    await tell_duel_progress(name, lobby, the_duel)


async def tell_duel_progress(name: str, lobby, the_duel):
    if is_in_duel(name, lobby, the_duel):
        await send_to(name, duel_progress_of(the_duel))


async def tell_round_news(lobby):
    """Tell the lobby what changed in its round, and end the round if it is over. Never raises.

    Called after everything that can change a round: a counted task, a
    player who left. If nothing changed, nothing is sent.
    """
    try:
        the_duel = lobby.duel
        if the_duel is not None and the_duel.take_news():
            await asyncio.gather(*(tell_duel_progress(name, lobby, the_duel) for name in the_duel.names()))
        farewells, result = end_round_if_over(lobby)
        await tell_round_ended(lobby, farewells, result)
    except Exception as problem:
        # The caller is a player's own handler: a fault here must not close
        # that player's connection. Only the kind of error is logged.
        logger.error("Telling the news of a round failed: %s", type(problem).__name__)


def end_round_if_over(lobby) -> tuple:
    """End the lobby's round if its mode says it is over.

    Returns `(farewells, result)`. `farewells` is what each player still
    has to be told, as `{name: [messages]}`, or an empty dict if the round
    goes on (or none is running). `result` is what the round adds to the
    statistics (see `duel_result_to_write`), or None. Both go to
    `tell_round_ended`, so a round's result travels with its own farewells.

    This function does not wait for anything: between the question "is it
    over?" and the end of the round nothing else can happen. So a round ends
    exactly once, even if the last task and the time limit fall together
    and the tick and a player's handler both ask.
    """
    the_duel = lobby.duel
    if the_duel is None or not the_duel.is_over(seconds_now()):
        return {}, None
    ranking = the_duel.ranking()
    # Everybody finished, or the time ran out: nothing else ends a Duel.
    time_up = not the_duel.everybody_finished()
    open_stations = {name: lobby.tasks.open_station_of(name) for name in lobby.names()}
    lobby.end_round()
    # Only the server writes the result of a round (S-40). It is worked out
    # here and written after the players were told (see `tell_round_ended`).
    result_to_write = duel_result_to_write(lobby, ranking)

    # From here on the round is over, whatever happens. If the messages
    # cannot be built, the players still get the lobby's new state from
    # `tell_round_ended`, so no browser stays in a round that has ended.
    try:
        result = [protocol.duel_result(ranking, time_up)]
    except Exception as problem:
        logger.error("The result of a Duel could not be built: %s", type(problem).__name__)
        result = []
    farewells = {}
    for name, station in open_stations.items():
        # A task that was open is gone with the round. The browser hears
        # that first, so its window closes before the ranking appears.
        closed = [] if station is None else [protocol.station_closed(station)]
        farewells[name] = closed + result
    return farewells, result_to_write


async def tell_round_ended(lobby, farewells: dict, result):
    """Send what `end_round_if_over` returned, then the lobby's state: it is open again.

    `result` is this round's result for the statistics, or None when there
    is nothing to write. It is written once this round's players have been
    told, and only by this call. It has no default, so that no caller can
    forget it and lose a round's statistics without anybody noticing.
    """
    if not farewells:
        return
    try:
        await asyncio.gather(*(tell_farewell(name, lobby, messages) for name, messages in farewells.items()))
    finally:
        # After the players have the result, and whatever happened while
        # telling them: the statistics are written now, in the background.
        write_result_later(result)
    await tell_lobby(lobby)


async def tell_farewell(name: str, lobby, messages: list):
    for message in messages:
        if not is_member(name, lobby):
            return
        await send_to(name, message)


def run_in_background(coroutine):
    """Start a coroutine as its own task, for the tick, which never waits for a browser."""
    task = asyncio.create_task(coroutine)
    background_sends.add(task)
    task.add_done_callback(background_sends.discard)


class ClientFiles(StaticFiles):
    """The files of the client, each sent with `Cache-Control: no-cache`.

    `no-cache` means: the browser may keep its copy, but it asks the server
    before every use whether the copy is still current. An unchanged file is
    answered with a short `304 Not Modified`, so nothing is downloaded twice.
    Without the header a browser guesses how long a file stays fresh, and a
    normal reload after a deploy showed an old script.

    Not `no-store`: then every file would be downloaded again on every visit.
    Not a long `max-age`: that is only safe when a changed file gets a new
    name (a version in the file name), and without a build step ours never do.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Mounted last, so /health and /ws win over files of the same name.
app.mount("/", ClientFiles(directory=CLIENT_DIR, html=True), name="client")
