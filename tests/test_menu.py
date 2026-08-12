from pathlib import Path

from tampa_phone.menu import MenuStore

DATA = Path(__file__).parents[1] / "data" / "menus.json"


def test_searches_restaurants_by_cuisine() -> None:
    store = MenuStore.from_json(DATA)

    matches = store.search_restaurants("wings chicken")

    assert [restaurant.id for restaurant in matches] == ["wingstop-south-dale-mabry"]


def test_normalizes_spoken_restaurant_queries() -> None:
    store = MenuStore.from_json(DATA)

    assert {restaurant.id for restaurant in store.search_restaurants("BBQ")} == {
        "jimbos-pit-bar-b-q",
        "4-rivers-smokehouse-south-tampa",
    }
    assert [restaurant.id for restaurant in store.search_restaurants("Anthonys Pizza")] == [
        "anthonys-coal-fired-pizza-south-tampa"
    ]


def test_menu_pages_are_limited_to_four_items() -> None:
    store = MenuStore.from_json(DATA)

    first_page, next_offset = store.menu_page("wingstop-south-dale-mabry")
    second_page, final_offset = store.menu_page(
        "wingstop-south-dale-mabry", offset=next_offset or 0
    )

    assert len(first_page) == 4
    assert next_offset == 4
    assert len(second_page) == 4
    assert final_offset == 8


def test_filters_menu_by_category() -> None:
    store = MenuStore.from_json(DATA)

    items, next_offset = store.menu_page("wingstop-south-dale-mabry", category="Wing Combos")

    assert len(items) == 4
    assert next_offset == 4
    assert items[0].id == "6-pc-wing-combo-boneless"
