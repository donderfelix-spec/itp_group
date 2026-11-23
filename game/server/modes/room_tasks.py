"""Funny campus tasks, added alongside the five original games of Duel.

Content is drawn by the server; the browser plays it (S-19). Labels, recipes
and the chat sentence are visible clues, not hidden information.
"""

from server.modes.minigame import Minigame

ROOMS = {
    7: "Lecture Hall", 8: "Mon Café", 9: "Canteen",
    10: "CTT Student Hall", 11: "Pingo Doce", 12: "Main Deck",
}


def slides(rng):
    labels = rng.sample(["Did the reading", "Brought snacks", "Opened the document", "Said 'quick call'"], 3)
    counts = rng.sample(range(2, 9), 3)
    rows = [{"label": label, "count": count, "sample": 10} for label, count in zip(labels, counts)]
    return {"kind": "campus_challenge", "puzzle": "chart", "rows": rows,
            "initial_labels": labels[1:] + labels[:1],
            "initial_values": [(count * 10 + 30) % 100 for count in counts]}


def coffee(rng):
    drinks = [
        ("The 11:59 PM special", ["Cup", "Espresso", "Espresso", "Milk", "Hope"]),
        ("The consultant's deliverable", ["Cup", "Espresso", "Milk", "Foam", "Hope"]),
        ("The founder's runway", ["Cup", "Espresso", "Water", "Espresso", "Hope"]),
    ]
    drink, recipe = rng.choice(drinks)
    controls = ["Cup", "Espresso", "Milk", "Water", "Foam", "Hope"]
    rng.shuffle(controls)
    return {"kind": "campus_task", "puzzle": "recipe", "drink": drink,
            "controls": controls, "recipe": list(recipe)}


def lunch(rng):
    """One tray of rice, vegetables and chicken, with individual mouldy pieces.

    IDs identify pieces independently of the shuffled drawing order. Only
    discolouration marks bad pieces in the client; labels name the food.
    """
    foods = (("rice", "Rice grain", 10, 3), ("vegetable", "Vegetable piece", 3, 1),
             ("chicken", "Chicken piece", 3, 1))
    items = []
    for food, label, count, bad_count in foods:
        mouldy = set(rng.sample(range(count), bad_count))
        for index in range(count):
            items.append({"id": f"{food}-{index}", "label": label, "remove": index in mouldy})
    rng.shuffle(items)
    return {"kind": "campus_task", "puzzle": "cleanup", "theme": "food", "items": items}


# Four ways to tell the order of the four slots, so the speaker at 9:00 is not
# always the one with the same kind of message (M2-4.22). Each function gets
# the four names in slot order and returns one sentence per slot; together the
# four sentences admit exactly one order (tests/test_chat_clue_variety.py).
SLOT_CLUES = (
    lambda n: [f"I present before {n[2]}.", f"My slot is immediately after {n[0]}'s.",
               f"I go immediately after {n[1]}.", "I'm last. Please leave some coffee."],
    lambda n: ["I'm first. Somebody has to wake everyone up.", f"I present before {n[3]}.",
               f"I go immediately before {n[3]}.", f"I present after {n[0]}."],
    lambda n: [f"I present before {n[1]}.", f"I go immediately before {n[2]}.",
               "I'm the third to present.", f"I present after {n[2]}."],
    lambda n: [f"I go immediately before {n[1]}.", "I'm second. Not first, not last.",
               f"I go immediately after {n[1]}.", f"I present after {n[2]}."],
)


def chat(rng):
    """Four teammates, one message each; the player picks only the times (S-223)."""
    people = rng.sample(["Mara", "Tiago", "Ines", "Rui"], 4)
    sentences = rng.choice(SLOT_CLUES)(people)
    clues = [{"from": person, "text": text} for person, text in zip(people, sentences)]
    rng.shuffle(clues)
    displayed = list(people)
    rng.shuffle(displayed)
    return {"kind": "campus_challenge", "puzzle": "chat_logic", "people": displayed,
            "slots": [9, 10, 11, 12], "clues": clues,
            "schedule": [{"person": person, "slot": slot} for person, slot in zip(people, [9, 10, 11, 12])]}


def budget(rng):
    names = ["Emergency noodles", "Deadline chocolate", "Team morale bananas",
             "Printer tribute paper", "Panic coffee", "Meeting biscuits"]
    # Three products always reach the target, and even the most expensive
    # single product is cheaper than that target. All amounts are cents.
    prices = rng.sample([150, 200, 250, 300, 350, 400], len(names))
    products = [{"name": name, "price": price} for name, price in zip(names, prices)]
    target = sum(product["price"] for product in rng.sample(products, 3))
    rng.shuffle(products)
    return {"kind": "campus_task", "puzzle": "budget", "products": products, "target": target}


def seagull(rng):
    cargo = ["page"] * 8 + ["coffee"] * 4
    rng.shuffle(cargo)
    return {"kind": "campus_challenge", "puzzle": "seagull_defence", "goal": 6,
            "waves": [{"lane": rng.randrange(3), "cargo": item,
                       "duration": rng.choice([1600, 1800, 2000]) - index * 25}
                      for index, item in enumerate(cargo)]}


MINIGAMES = {
    7: Minigame("Fix the consultant’s chart", 1, slides),
    8: Minigame("Emergency caffeine protocol", 1, coffee),
    9: Minigame("Save the lunch", 1, lunch),
    10: Minigame("Decode the group chat", 1, chat),
    11: Minigame("Expense the essentials", 1, budget),
    12: Minigame("Seagull quality control", 1, seagull),
}
