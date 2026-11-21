"""Funny campus tasks, added alongside the five original games of Duel.

Content is drawn by the server; the browser plays it (S-19). Labels, recipes
and the chat sentence are visible clues, not hidden information.
"""

from server.modes.minigame import Minigame

ROOMS = {
    7: "Lecture Hall", 8: "Mon Café", 9: "Canteen",
    10: "CTT Student Hall", 11: "Pingo Doce", 12: "Main Deck",
}


def cleanup_content(rng, theme, good, bad):
    items = [
        {"id": f"good-{index}", "label": label, "remove": False}
        for index, label in enumerate(rng.sample(good, 3))
    ]
    items += [
        {"id": f"bad-{index}", "label": label, "remove": True}
        for index, label in enumerate(rng.sample(bad, 3))
    ]
    rng.shuffle(items)
    return {"kind": "campus_task", "puzzle": "cleanup", "theme": theme, "items": items}


def slides(rng):
    return cleanup_content(
        rng, "slides",
        ["Research question", "Survey results", "Sources", "Actual conclusion"],
        ["Synergy tornado", "Blockchain-powered vibes", "Disruptive lunch strategy", "Quantum stakeholder alignment"],
    )


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


def chat(rng):
    sentences = [
        "My laptop joined another group project",
        "The seagull ate my contribution again",
        "I thought this deadline was optional",
        "Our spreadsheet has developed trust issues",
    ]
    sentence = rng.choice(sentences)
    order = sentence.split()
    words = list(order)
    rng.shuffle(words)
    return {"kind": "campus_task", "puzzle": "order", "words": words,
            "order": order, "hint": sentence}


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
    return {"kind": "campus_task", "puzzle": "seagull", "pages": rng.randint(4, 6)}


MINIGAMES = {
    7: Minigame("De-buzzword the slides", 1, slides),
    8: Minigame("Emergency caffeine protocol", 1, coffee),
    9: Minigame("Save the lunch", 1, lunch),
    10: Minigame("Decode the group chat", 1, chat),
    11: Minigame("Expense the essentials", 1, budget),
    12: Minigame("Seagull quality control", 1, seagull),
}
