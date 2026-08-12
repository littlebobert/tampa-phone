from pathlib import Path

import pytest

from tampa_phone.cart import Cart
from tampa_phone.menu import MenuStore

DATA = Path(__file__).parents[1] / "data" / "menus.json"


def test_cart_totals_and_summarizes() -> None:
    cart = Cart(MenuStore.from_json(DATA))

    cart.add("demo-bay-pizza", "garlic-knots", quantity=2)
    cart.add("demo-bay-pizza", "cheese-pizza", special_instructions="well done")

    assert cart.subtotal_cents == 2997
    assert "Menu subtotal $29.97" in cart.summary()
    assert "well done" in cart.summary()
    assert "final total still need review" in cart.summary()


def test_cart_rejects_multiple_restaurants() -> None:
    cart = Cart(MenuStore.from_json(DATA))
    cart.add("demo-bay-pizza", "garlic-knots")

    with pytest.raises(ValueError, match="one restaurant"):
        cart.add("demo-palm-thai", "pad-thai")


def test_cart_rejects_invalid_quantity() -> None:
    cart = Cart(MenuStore.from_json(DATA))

    with pytest.raises(ValueError, match="between 1 and 10"):
        cart.add("demo-bay-pizza", "garlic-knots", quantity=0)
