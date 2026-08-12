from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, TurnHandlingOptions, function_tool
from livekit.plugins import openai
from openai.types.beta.realtime.session import TurnDetection

from livekit import agents, rtc
from tampa_phone.cart import Cart
from tampa_phone.config import Settings
from tampa_phone.handoff import OrderHandoff
from tampa_phone.menu import MenuStore

load_dotenv(".env.local")
load_dotenv()

logger = logging.getLogger("tampa-phone")
AGENT_NAME = os.getenv("AGENT_NAME", "tampa-food-phone")


class FoodPhoneAgent(Agent):
    def __init__(self, menus: MenuStore, settings: Settings) -> None:
        self.menus = menus
        self.settings = settings
        self.cart = Cart(menus)
        self.handoff = OrderHandoff(settings)
        super().__init__(
            instructions=f"""
You are a warm, patient phone concierge helping {settings.caller_name} browse restaurant
menus and prepare a food order for family review. This is a phone call, not a screen.

Conversation rules:
- Speak naturally, using short sentences and no markdown.
- Never read more than four menu items at once. After a short group, pause and ask
  whether to hear more, repeat one, switch categories, or choose one.
- Let the caller interrupt. Track references such as "the second one" from the most
  recent group. Repeat names, descriptions, and prices whenever asked.
- Use menu tools for every restaurant, item, price, and availability claim. Never invent
  menu facts or imply that demo/stale data is current.
- Start broad: ask what kind of food sounds good, unless the caller names a restaurant.
- Mention data freshness or unverified hours when it matters, especially before review.
- Fulfillment preference: {settings.fulfillment_summary} Treat delivery availability as
  provisional until checkout. If delivery is unavailable, prepare the same cart for pickup.

Cart and safety rules:
- A cart can contain items from only one restaurant.
- Adding an item is not placing an order.
- Before requesting review, call get_cart and read every item, quantity, instructions,
  menu subtotal, and the warning that taxes, fees, availability, and final total remain.
- Ask for an explicit yes after that complete readback.
- Only after that yes may you call send_cart_for_review.
- The handoff sends a text to a trusted family member. It never purchases food.
- Never ask for or accept a card number, password, PIN, or Uber/DoorDash credentials.
"""
        )

    @function_tool
    async def find_restaurants(self, query: str = "") -> str:
        """Find cached restaurants by name, cuisine, or neighborhood."""
        matches = self.menus.search_restaurants(query)
        if not matches:
            return "No cached restaurants matched that request. Offer another cuisine or name."
        lines = [
            f"ID {restaurant.id}: {restaurant.name}; {restaurant.cuisine}; "
            f"{restaurant.neighborhood}; hours note: {restaurant.hours_note}."
            for restaurant in matches[:8]
        ]
        return "\n".join(lines)

    @function_tool
    async def get_restaurant_details(self, restaurant_id: str) -> str:
        """Get details and menu categories for one cached restaurant."""
        try:
            restaurant = self.menus.restaurant(restaurant_id)
        except ValueError as error:
            return str(error)
        categories = ", ".join(self.menus.categories(restaurant_id))
        return (
            f"{restaurant.name}. Cuisine: {restaurant.cuisine}. "
            f"Neighborhood: {restaurant.neighborhood}. Address: {restaurant.address}. "
            f"Hours note: {restaurant.hours_note}. Categories: {categories}. "
            f"Menu refreshed: {restaurant.refreshed_at}. "
            f"{self.settings.fulfillment_summary} Delivery eligibility is not guaranteed until "
            "checkout."
        )

    @function_tool
    async def browse_menu(
        self,
        restaurant_id: str,
        category: str = "",
        query: str = "",
        offset: int = 0,
    ) -> str:
        """Browse at most four menu items. Use next_offset to continue the same result set."""
        try:
            restaurant = self.menus.restaurant(restaurant_id)
            items, next_offset = self.menus.menu_page(
                restaurant_id=restaurant_id,
                category=category,
                query=query,
                offset=offset,
            )
        except ValueError as error:
            return str(error)
        if not items:
            return f"No matching cached menu items at {restaurant.name}."
        lines = [
            f"Item ID {item.id}: {item.name}, {item.price}. {item.description}" for item in items
        ]
        continuation = (
            f"More results are available; call browse_menu with offset {next_offset}."
            if next_offset is not None
            else "That is the end of this result set."
        )
        return "\n".join([*lines, continuation])

    @function_tool
    async def add_to_cart(
        self,
        restaurant_id: str,
        item_id: str,
        quantity: int = 1,
        special_instructions: str = "",
    ) -> str:
        """Add a cached menu item to the review cart. This does not place an order."""
        try:
            line = self.cart.add(
                restaurant_id=restaurant_id,
                item_id=item_id,
                quantity=quantity,
                special_instructions=special_instructions,
            )
        except ValueError as error:
            return str(error)
        return (
            f"Added {line.quantity} {line.item.name} to the review cart. No order has been placed."
        )

    @function_tool
    async def remove_from_cart(self, line_number: int) -> str:
        """Remove one numbered line from the cart."""
        try:
            line = self.cart.remove(line_number)
        except ValueError as error:
            return str(error)
        return f"Removed {line.quantity} {line.item.name}."

    @function_tool
    async def clear_cart(self) -> str:
        """Remove every item from the cart."""
        self.cart.clear()
        return "The cart is empty."

    @function_tool
    async def get_cart(self) -> str:
        """Get the complete cart for verbal readback before family review."""
        return f"{self.cart.summary()} {self.settings.fulfillment_summary}"

    @function_tool
    async def send_cart_for_review(self, caller_explicitly_confirmed: bool) -> str:
        """Text the cart to family only after a complete readback and the caller's explicit yes."""
        if not caller_explicitly_confirmed:
            return "Do not send. Read back the complete cart and ask for an explicit yes."
        if not self.cart.lines:
            return "The cart is empty, so there is nothing to send."
        if not self.settings.sms_is_configured:
            return "SMS review is not configured. No order was placed and no message was sent."
        body = (
            f"Food order review requested by {self.settings.caller_name}:\n\n"
            f"{self.cart.summary()}\n\n"
            f"Fulfillment: {self.settings.fulfillment_summary}\n\n"
            "Please verify current availability, prices, fees, delivery address, and final total "
            "before placing anything. This text did not place an order."
        )
        try:
            result = await self.handoff.send(body)
        except Exception:
            logger.exception("Could not send order review SMS")
            return "The review text failed to send. No order was placed. Please try again later."
        if result.status in {"undelivered", "failed"}:
            logger.error(
                "Order review SMS delivery failed",
                extra={
                    "message_sid": result.sid,
                    "message_status": result.status,
                    "message_error_code": result.error_code,
                },
            )
            return (
                f"The review text was not delivered. Twilio error {result.error_code}. "
                "No order was placed. Please contact the family reviewer another way."
            )
        if result.status == "delivered":
            return (
                f"The review text was delivered successfully with reference {result.sid}. "
                "No order has been placed."
            )
        return (
            f"Twilio accepted the review text with reference {result.sid}, but delivery is not "
            "confirmed yet. No order has been placed."
        )


class RestrictedCallerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Politely say this private number only accepts calls from an approved phone "
                "number, then say goodbye. Do not provide any other assistance."
            )
        )


def _is_allowed_sip_caller(participant: rtc.RemoteParticipant, settings: Settings) -> bool:
    if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        return True
    caller = participant.attributes.get("sip.phoneNumber", "")
    return caller in settings.allowed_caller_numbers


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def food_phone(ctx: agents.JobContext) -> None:
    settings = Settings.from_env()
    menu_path = settings.menu_data_path
    if not menu_path.is_absolute():
        menu_path = Path.cwd() / menu_path
    menus = MenuStore.from_json(menu_path)

    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    caller = participant.attributes.get("sip.phoneNumber", "non-SIP")
    ctx.log_context_fields = {"caller": caller, "room": ctx.room.name}

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model="gpt-realtime",
            voice="marin",
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="low",
                create_response=True,
                interrupt_response=False,
            ),
        ),
        turn_handling=TurnHandlingOptions(
            interruption={
                "mode": "adaptive",
                "min_duration": 0.8,
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.2,
                "backchannel_boundary": (1.5, 1.0),
            }
        ),
    )

    if not _is_allowed_sip_caller(participant, settings):
        logger.warning("Rejected unapproved caller")
        await session.start(room=ctx.room, agent=RestrictedCallerAgent())
        await session.generate_reply(
            instructions="Explain the restriction briefly and say goodbye."
        )
        return

    await session.start(room=ctx.room, agent=FoodPhoneAgent(menus, settings))
    await session.generate_reply(
        instructions=(
            f"Greet {settings.caller_name} warmly. Explain in one sentence that you can help "
            "browse menus and prepare a cart for family review, then ask what sounds good."
        )
    )


def main() -> None:
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()
