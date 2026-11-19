"""The minigame of every station that is in use.

How to add a real minigame (for example "Sort the slides" at station 1):

1. Write one new file in this folder, `sort_slides.py`. It needs a function
   that draws the content and one `Minigame`:

       from server.modes.minigame import Minigame

       def make_content(rng) -> dict:
           slides = ["Title", "Agenda", "Analysis", "Results", "Q&A"]
           rng.shuffle(slides)
           return {"kind": "sort_slides", "slides": slides}

       MINIGAME = Minigame(title="Sort the slides", min_seconds=3, make_content=make_content)

2. Change the one line of that station in `MINIGAMES` below:

       1: sort_slides.MINIGAME,

3. In the browser: one new file `client/js/minigames/sort_slides.js` that
   calls `Game.minigames.register("sort_slides", ...)` (see
   `client/js/minigames/frame.js`) and one `<script>` tag for it in
   `client/index.html`, after `frame.js`.

Nothing else changes: the frame (`tasks.py`, `server/main.py`, `frame.js`)
works with whatever stands in this table. Never put the solution of a task
into the content if the player must not see it.

A station that is not in this table is not in use: station 6, "Catch the
wave", comes only if time allows.
"""

from server.modes import build_tray
from server.modes.placeholder import placeholder

# Station id -> its minigame. The titles are the ones of DESIGN.md, section 8.
MINIGAMES = {
    1: placeholder("Sort the slides"),
    2: placeholder("Brew the order"),
    3: build_tray.MINIGAME,
    4: placeholder("Shelve the books"),
    5: placeholder("Self-checkout"),
}
