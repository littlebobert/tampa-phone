from pathlib import Path

import pytest

from tampa_phone.cart import Cart
from tampa_phone.menu import MenuStore

DATA = Path(__file__).parents[1] / "data" / "menus.json"


def test_cart_totals_and_summarizes() -> None:
    cart = Cart(MenuStore.from_json(DATA))

    cart.add("wingstop-south-dale-mabry", "6-pc-wing-combo-boneless", quantity=2)
    cart.add(
        "wingstop-south-dale-mabry",
        "8-pc-wing-combo-boneless",
        special_instructions="well done",
    )

    assert cart.subtotal_cents == 3747
    assert "Menu subtotal $37.47" in cart.summary()
    assert "well done" in cart.summary()
    assert "final total still need review" in cart.summary()


def test_cart_rejects_multiple_restaurants() -> None:
    cart = Cart(MenuStore.from_json(DATA))
    cart.add("wingstop-south-dale-mabry", "6-pc-wing-combo-boneless")

    with pytest.raises(ValueError, match="one restaurant"):
        cart.add("metro-diner-south-tampa", "cinnamon-roll-pancakes")


def test_cart_rejects_invalid_quantity() -> None:
    cart = Cart(MenuStore.from_json(DATA))

    with pytest.raises(ValueError, match="between 1 and 10"):
        cart.add(
            "wingstop-south-dale-mabry",
            "6-pc-wing-combo-boneless",
            quantity=0,
        )


def test_cart_handles_unavailable_prices() -> None:
    cart = Cart(MenuStore.from_json(DATA))

    cart.add(
        "anthonys-coal-fired-pizza-south-tampa",
        "lunch-10-inch-cheese-pizza-beverage",
    )

    assert "price unavailable" in cart.summary()
    assert "No menu subtotal is available" in cart.summary()
