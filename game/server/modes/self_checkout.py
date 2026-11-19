"""Minigame 5, "Self-checkout" at Pingo Doce (DESIGN.md, section 8; S-60).

The checkout shows a target amount and six products lie on the belt. The
player scans products until the total is exactly the target. The server only
draws the prices, the order on the belt and the target; the browser plays it
(S-19).

Money is counted in whole cents (150 for €1.50) everywhere, never in euros
with a decimal point: a computer cannot store 0.10 exactly, so 0.10 + 0.20
is not exactly 0.30, and "is the total exactly the target?" could fail.
Whole numbers add up without any error.
"""

from server.modes.minigame import Minigame

PRODUCT_NAMES = ["Water", "Bread", "Cheese", "Apples", "Coffee", "Chocolate"]

# Prices are multiples of 50 cents, from €0.50 to €4.00.
PRICE_STEP_CENTS = 50
LOWEST_PRICE_CENTS = 50
HIGHEST_PRICE_CENTS = 400

# The target is the total of this many products, so there is always a solution.
PRODUCTS_IN_TARGET = 3

# Reading the target and three clicks take longer than this.
MIN_SECONDS = 3


def draw_price(rng) -> int:
    """One price in whole cents."""
    return rng.randrange(LOWEST_PRICE_CENTS, HIGHEST_PRICE_CENTS + 1, PRICE_STEP_CENTS)


def make_content(rng) -> dict:
    """The six products in their order on the belt, and the target amount.

    Which three products add up to the target is not sent: the player has to
    find a combination, and every combination that fits counts (S-60).
    """
    names = list(PRODUCT_NAMES)
    rng.shuffle(names)
    products = [{"name": name, "cents": draw_price(rng)} for name in names]
    chosen = rng.sample(products, PRODUCTS_IN_TARGET)
    target_cents = sum(product["cents"] for product in chosen)
    return {"kind": "self_checkout", "products": products, "target_cents": target_cents}


MINIGAME = Minigame(title="Self-checkout", min_seconds=MIN_SECONDS, make_content=make_content)
