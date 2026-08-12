from __future__ import annotations

from dataclasses import dataclass

from tampa_phone.menu import MenuItem, MenuStore


@dataclass
class CartLine:
    restaurant_id: str
    item: MenuItem
    quantity: int
    special_instructions: str = ""

    @property
    def subtotal_cents(self) -> int:
        return self.item.price_cents * self.quantity


class Cart:
    def __init__(self, menus: MenuStore) -> None:
        self.menus = menus
        self.lines: list[CartLine] = []

    def add(
        self,
        restaurant_id: str,
        item_id: str,
        quantity: int = 1,
        special_instructions: str = "",
    ) -> CartLine:
        if quantity < 1 or quantity > 10:
            raise ValueError("Quantity must be between 1 and 10")
        if self.lines and self.lines[0].restaurant_id != restaurant_id:
            raise ValueError("A cart can only contain items from one restaurant")
        line = CartLine(
            restaurant_id=restaurant_id,
            item=self.menus.item(restaurant_id, item_id),
            quantity=quantity,
            special_instructions=special_instructions.strip(),
        )
        self.lines.append(line)
        return line

    def remove(self, line_number: int) -> CartLine:
        if line_number < 1 or line_number > len(self.lines):
            raise ValueError("That line number is not in the cart")
        return self.lines.pop(line_number - 1)

    @property
    def subtotal_cents(self) -> int:
        return sum(line.subtotal_cents for line in self.lines)

    def clear(self) -> None:
        self.lines.clear()

    def summary(self) -> str:
        if not self.lines:
            return "The cart is empty."
        restaurant = self.menus.restaurant(self.lines[0].restaurant_id)
        details = []
        for index, line in enumerate(self.lines, start=1):
            note = f" Notes: {line.special_instructions}." if line.special_instructions else ""
            details.append(
                f"{index}. {line.quantity} {line.item.name}, "
                f"${line.subtotal_cents / 100:.2f}.{note}"
            )
        return (
            f"Cart for {restaurant.name}. "
            + " ".join(details)
            + f" Menu subtotal ${self.subtotal_cents / 100:.2f}. "
            "Taxes, fees, availability, and the final total still need review."
        )
