from pathlib import Path

from tampa_phone.menu import MenuStore

DATA = Path(__file__).parents[1] / "data" / "menus.json"


def test_searches_restaurants_by_cuisine() -> None:
    store = MenuStore.from_json(DATA)

    matches = store.search_restaurants("thai")

    assert [restaurant.id for restaurant in matches] == ["demo-palm-thai"]


def test_menu_pages_are_limited_to_four_items() -> None:
    store = MenuStore.from_json(DATA)

    first_page, next_offset = store.menu_page("demo-bay-pizza")
    second_page, final_offset = store.menu_page("demo-bay-pizza", offset=next_offset or 0)

    assert len(first_page) == 4
    assert next_offset == 4
    assert len(second_page) == 2
    assert final_offset is None


def test_filters_menu_by_category() -> None:
    store = MenuStore.from_json(DATA)

    items, _ = store.menu_page("demo-bay-pizza", category="Pizza")

    assert {item.id for item in items} == {
        "cheese-pizza",
        "pepperoni-pizza",
        "veggie-pizza",
    }
