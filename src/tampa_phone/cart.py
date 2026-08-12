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
    def subtotal_cents(self) -> int | None:
        if self.item.price_cents is None:
            return None
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
        return sum(line.subtotal_cents or 0 for line in self.lines)

    def clear(self) -> None:
        self.lines.clear()

    def summary(self) -> str:
        if not self.lines:
            return "The cart is empty."
        restaurant = self.menus.restaurant(self.lines[0].restaurant_id)
        details = []
        has_unknown_prices = False
        for index, line in enumerate(self.lines, start=1):
            note = f" Notes: {line.special_instructions}." if line.special_instructions else ""
            if line.subtotal_cents is None:
                has_unknown_prices = True
                line_price = "price unavailable"
            else:
                line_price = f"${line.subtotal_cents / 100:.2f}"
            details.append(f"{index}. {line.quantity} {line.item.name}, {line_price}.{note}")
        known_price_lines = sum(line.subtotal_cents is not None for line in self.lines)
        if known_price_lines == 0:
            subtotal = " No menu subtotal is available."
        elif has_unknown_prices:
            subtotal = f" Known-price subtotal ${self.subtotal_cents / 100:.2f}."
        else:
            subtotal = f" Menu subtotal ${self.subtotal_cents / 100:.2f}."
        price_warning = (
            " One or more item prices were unavailable and are not included in that subtotal."
            if has_unknown_prices and known_price_lines > 0
            else ""
        )
        return (
            f"Cart for {restaurant.name}. "
            + " ".join(details)
            + subtotal
            + price_warning
            + " Taxes, fees, availability, and the final total still need review."
        )
