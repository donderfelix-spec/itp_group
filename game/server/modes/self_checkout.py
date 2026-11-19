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

# A target that one product alone reaches would be solved with a single click,
# so such a draw is thrown away and the three products are drawn again. This
# is how often at most, so the drawing always ends.
TARGET_TRIES = 10

# The minimum only has to stop a script that finishes at once. A player who
# reads fast and clicks three products must not be told "too fast".
MIN_SECONDS = 1


def draw_price(rng) -> int:
    """One price in whole cents."""
    return rng.randrange(LOWEST_PRICE_CENTS, HIGHEST_PRICE_CENTS + 1, PRICE_STEP_CENTS)


def total_cents(products) -> int:
    return sum(product["cents"] for product in products)


def dearest_three_total(products) -> int:
    """The total of the three most expensive products.

    It is always more than any single price: the dearest product is part of
    it, and the other two cost at least 50 cents each.
    """
    by_price = sorted(products, key=lambda product: product["cents"], reverse=True)
    return total_cents(by_price[:PRODUCTS_IN_TARGET])


def draw_target(rng, products) -> int:
    """The total of three of the products, never the price of a single one."""
    single_prices = {product["cents"] for product in products}
    for _ in range(TARGET_TRIES):
        target_cents = total_cents(rng.sample(products, PRODUCTS_IN_TARGET))
        if target_cents not in single_prices:
            return target_cents
    # Every try hit a single price (very rare). No more drawing: this total
    # cannot be a single price, so the function always ends with a fair target.
    return dearest_three_total(products)


def make_content(rng) -> dict:
    """The six products in their order on the belt, and the target amount.

    Which three products add up to the target is not sent: the player has to
    find a combination, and every combination that fits counts (S-60).
    """
    names = list(PRODUCT_NAMES)
    rng.shuffle(names)
    products = [{"name": name, "cents": draw_price(rng)} for name in names]
    return {"kind": "self_checkout", "products": products, "target_cents": draw_target(rng, products)}


MINIGAME = Minigame(title="Self-checkout", min_seconds=MIN_SECONDS, make_content=make_content)
