"""Minigame of station 2, Mon Café: "Brew the order" (DESIGN.md, section 8).

An order slip names a drink with its recipe. The player presses the buttons
of the coffee machine in the order of the recipe. The recipe is sent to the
browser on purpose: it is what the player reads from the slip.
"""

from server.modes.minigame import Minigame

# The six buttons of the coffee machine.
BUTTONS = ["Cup", "Glass", "Espresso", "Hot water", "Milk", "Foam"]

# Drink -> the buttons to press, in this order. No recipe has the same
# button twice in a row, so a double click can never count as two steps.
RECIPES = {
    "Bica": ["Cup", "Espresso"],
    "Abatanado": ["Cup", "Espresso", "Hot water"],
    "Meia de leite": ["Cup", "Espresso", "Milk"],
    "Galão": ["Glass", "Espresso", "Milk"],
    "Cappuccino": ["Cup", "Espresso", "Milk", "Foam"],
}

# Bica has only two steps: a quick player needs about this long for it.
MIN_SECONDS = 2


def make_content(rng) -> dict:
    """Draw one drink and where each button sits on the machine.

    The buttons are shuffled every time, so the minigame cannot be played
    from muscle memory.
    """
    drink = rng.choice(list(RECIPES))
    buttons = list(BUTTONS)
    rng.shuffle(buttons)
    return {
        "kind": "brew_order",
        "drink": drink,
        "recipe": list(RECIPES[drink]),
        "buttons": buttons,
    }


MINIGAME = Minigame(title="Brew the order", min_seconds=MIN_SECONDS, make_content=make_content)
