import asyncio
from pathlib import Path

from tampa_phone.agent import BoatingPhoneAgent, FoodPhoneAgent, ModeRouterAgent
from tampa_phone.config import Settings
from tampa_phone.menu import MenuStore
from tampa_phone.noaa import NOAAClient

DATA = Path(__file__).parents[1] / "data" / "menus.json"


def _router() -> ModeRouterAgent:
    return ModeRouterAgent(
        menus=MenuStore.from_json(DATA),
        settings=Settings.from_env(),
        noaa=NOAAClient(),
    )


def test_routes_dennis_to_food_and_larry_to_boating() -> None:
    router = _router()

    dennis = asyncio.run(ModeRouterAgent.select_caller._func(router, "This is Dennis"))
    larry = asyncio.run(ModeRouterAgent.select_caller._func(router, "Larry speaking"))

    assert isinstance(dennis[0], FoodPhoneAgent)
    assert isinstance(larry[0], BoatingPhoneAgent)


def test_rejects_unknown_demo_name() -> None:
    router = _router()

    result = asyncio.run(ModeRouterAgent.select_caller._func(router, "Steve"))

    assert result == "This demo only recognizes Dennis or Larry. Ask the caller to choose one."
