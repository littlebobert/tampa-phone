from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MenuItem:
    id: str
    name: str
    description: str
    price_cents: int | None
    category: str

    @property
    def price(self) -> str:
        if self.price_cents is None:
            return "price unavailable"
        return f"${self.price_cents / 100:.2f}"


@dataclass(frozen=True)
class Restaurant:
    id: str
    name: str
    cuisine: str
    neighborhood: str
    address: str
    phone: str
    hours_note: str
    source_url: str
    refreshed_at: str
    items: tuple[MenuItem, ...]


def _normalize_search_text(value: str) -> str:
    normalized = value.casefold().replace("\u2019", "'").replace("'", "").replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    words = normalized.split()
    aliases = {"bbq": "barbecue"}
    return " ".join(aliases.get(word, word) for word in words)


class MenuStore:
    def __init__(self, restaurants: tuple[Restaurant, ...]) -> None:
        self.restaurants = restaurants
        self._restaurants_by_id = {restaurant.id: restaurant for restaurant in restaurants}

    @classmethod
    def from_json(cls, path: Path) -> MenuStore:
        raw = json.loads(path.read_text())
        restaurants = []
        for entry in raw["restaurants"]:
            items = tuple(MenuItem(**item) for item in entry.pop("items"))
            restaurants.append(Restaurant(items=items, **entry))
        return cls(tuple(restaurants))

    def restaurant(self, restaurant_id: str) -> Restaurant:
        try:
            return self._restaurants_by_id[restaurant_id]
        except KeyError as error:
            raise ValueError(f"Unknown restaurant: {restaurant_id}") from error

    def item(self, restaurant_id: str, item_id: str) -> MenuItem:
        restaurant = self.restaurant(restaurant_id)
        for item in restaurant.items:
            if item.id == item_id:
                return item
        raise ValueError(f"Unknown item {item_id} at {restaurant.name}")

    def search_restaurants(self, query: str = "") -> tuple[Restaurant, ...]:
        words = _normalize_search_text(query).split()
        if not words:
            return self.restaurants
        matches = []
        for restaurant in self.restaurants:
            haystack = _normalize_search_text(
                " ".join((restaurant.name, restaurant.cuisine, restaurant.neighborhood))
            )
            if all(word in haystack for word in words):
                matches.append(restaurant)
        return tuple(matches)

    def categories(self, restaurant_id: str) -> tuple[str, ...]:
        restaurant = self.restaurant(restaurant_id)
        return tuple(dict.fromkeys(item.category for item in restaurant.items))

    def menu_page(
        self,
        restaurant_id: str,
        category: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 4,
    ) -> tuple[tuple[MenuItem, ...], int | None]:
        restaurant = self.restaurant(restaurant_id)
        items = restaurant.items
        if category:
            items = tuple(item for item in items if item.category.casefold() == category.casefold())
        if query:
            words = query.casefold().split()
            items = tuple(
                item
                for item in items
                if all(
                    word in f"{item.name} {item.description} {item.category}".casefold()
                    for word in words
                )
            )
        safe_offset = max(offset, 0)
        page = items[safe_offset : safe_offset + limit]
        next_offset = safe_offset + limit if safe_offset + limit < len(items) else None
        return page, next_offset
