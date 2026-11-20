"""A TCP proxy that delays the bytes like an internet connection would.

Server -> browser: every chunk is held base + uniform(0, jitter) ms, never
overtaking an earlier chunk (TCP keeps the order), so a late chunk makes the
next ones arrive together. With probability BURST a chunk is held BURST_MS
longer, which makes two messages arrive at once.
Browser -> server: held base ms.
After the WebSocket upgrade, an optional JSON file adds a recorded pattern:
a list of extra delays in ms, taken one per chunk from the server, in a loop.

Usage: python3 delay_proxy.py LISTEN TARGET BASE_MS JITTER_MS BURST_PROB BURST_MS [PATTERN.json]
Example (Felix's connection of 2026-11-20 in front of a local server on 8000):
  python3 delay_proxy.py 8030 8000 30 0 0 0 felix_2026-11-20.json
"""
import asyncio, json, random, sys, time

LISTEN, TARGET = int(sys.argv[1]), int(sys.argv[2])
BASE, JITTER = float(sys.argv[3]) / 1000, float(sys.argv[4]) / 1000
BURST, BURST_MS = float(sys.argv[5]), float(sys.argv[6]) / 1000
# Optional 7th argument: a JSON file with a list of extra delays in ms, applied
# to the WebSocket chunks from the server one after the other, in a loop.
CYCLE = json.load(open(sys.argv[7])) if len(sys.argv) > 7 else None


async def pipe(reader, writer, downstream):
    queue = asyncio.Queue()
    last = [0.0]

    async def deliver():
        while True:
            at, data = await queue.get()
            if data is None:
                break
            wait = at - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            writer.write(data)
            await writer.drain()
        writer.close()

    task = asyncio.create_task(deliver())
    upgraded = False
    count = 0
    while True:
        data = await reader.read(65536)
        if not data:
            break
        delay = BASE
        if downstream and CYCLE is not None and upgraded:
            delay += CYCLE[count % len(CYCLE)] / 1000
            count += 1
        if downstream and b'101 Switching' in data:
            upgraded = True
        if downstream:
            delay += random.uniform(0, JITTER)
            if random.random() < BURST:
                delay += BURST_MS
        at = max(time.monotonic() + delay, last[0])
        last[0] = at
        queue.put_nowait((at, data))
    queue.put_nowait((0, None))
    await task


async def handle(client_reader, client_writer):
    server_reader, server_writer = await asyncio.open_connection("127.0.0.1", TARGET)
    client_writer.transport.set_write_buffer_limits(0)
    await asyncio.gather(
        pipe(client_reader, server_writer, False),
        pipe(server_reader, client_writer, True),
        return_exceptions=True,
    )


async def main():
    server = await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    async with server:
        await server.serve_forever()

asyncio.run(main())
