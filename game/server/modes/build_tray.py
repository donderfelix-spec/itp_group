"""The minigame of the Canteen, station 3: "Build the tray".

Six dishes stand at the counter and the order slip names four of them
(DESIGN.md, section 8, and S-60). The server only draws where the dishes
stand and which four are ordered; the browser plays it (S-19). The order slip
is sent along, because it is exactly what the player has to read.
"""

from server.modes.minigame import Minigame

# The six dishes of the counter, with the names shown to the player.
DISHES = ("Soup", "Bacalhau", "Rice", "Salad", "Pastel de nata", "Fruit")

# How many of the dishes the order slip names.
DISHES_ON_SLIP = 4

# Reading the slip and four clicks take longer than this; a "done" that
# comes sooner was not played (S-93).
MIN_SECONDS = 3


def make_content(rng) -> dict:
    """Shuffle the counter and draw the order slip.

    `rng` is the only source of randomness, so a test that passes
    `random.Random(seed)` always gets the same tray.
    """
    counter = list(DISHES)
    rng.shuffle(counter)
    # Drawn from the fixed list, not from the shuffled counter, so the place
    # of a dish at the counter says nothing about whether it is ordered.
    order = rng.sample(DISHES, DISHES_ON_SLIP)
    return {"kind": "build_tray", "dishes": counter, "order": order}


MINIGAME = Minigame(title="Build the tray", min_seconds=MIN_SECONDS, make_content=make_content)
