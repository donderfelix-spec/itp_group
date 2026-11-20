# Network trace tools (M2-1.12, M2-1.14)

Tools for measuring by hand how smooth walking looks over a bad connection. They are not tests: pytest does not collect them, and they need Playwright with Chromium, which is not a dependency of the game (S-72).

| File | What it is |
|---|---|
| `delay_proxy.py` | A TCP proxy in front of the game server. It delays what the server sends like the internet: a fixed delay, random jitter, occasional bursts, and optionally a recorded pattern from a JSON file, looped. Browser to server only gets the fixed delay. |
| `felix_2026-11-20.json` | Felix's connection to the deployed game, read off his DevTools screenshot of 2026-11-20: the extra delay per `positions` message in ms, 24 messages long. About every 410 ms one message is held about 105 ms and arrives together with the next one, with smaller holds of about 37 ms in between. |
| `felix_with_400ms_gap_every_3s.json` | The same, 44 messages long, with 400 ms more on the last one: a long gap about every 3 seconds, as Felix reported later that day (its real size is unknown). |
| `measure_walk.js` | One headless Chromium guest walks for a given time while bots walk too. It records every frame (camera, drawing time, walk phase) and every `positions` message. |
| `analyze_walk.py`, `analyze_feet.py` | Numbers per run: stalls, gaps, frame time, frozen feet, the fastest catch-up. |

## Example

From `game/`, with the game running on port 8000:

```bash
python3 tests/network_trace/delay_proxy.py 8030 8000 30 0 0 0 tests/network_trace/felix_2026-11-20.json &
NODE_PATH=$(npm root -g) node tests/network_trace/measure_walk.js 8030 2 12 /tmp/run.json
python3 tests/network_trace/analyze_feet.py /tmp/run.json
```

`BOTPORT` sets where the bots connect (default 8000). To compare with another version, start a second server on another port and a second proxy in front of it, and set `BOTPORT` to that server.
