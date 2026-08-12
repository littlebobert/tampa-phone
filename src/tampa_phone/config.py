from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _phone_set(value: str) -> frozenset[str]:
    return frozenset(number.strip() for number in value.split(",") if number.strip())


@dataclass(frozen=True)
class Settings:
    menu_data_path: Path
    allowed_caller_numbers: frozenset[str]
    caller_name: str
    delivery_zip: str
    fulfillment_preference: str
    twilio_account_sid: str | None
    twilio_auth_token: str | None
    twilio_from_number: str | None
    order_review_number: str | None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            menu_data_path=Path(os.getenv("MENU_DATA_PATH", "data/menus.json")),
            allowed_caller_numbers=_phone_set(os.getenv("ALLOWED_CALLER_NUMBERS", "")),
            caller_name=os.getenv("CALLER_NAME", "there"),
            delivery_zip=os.getenv("DELIVERY_ZIP", "33609"),
            fulfillment_preference=os.getenv("FULFILLMENT_PREFERENCE", "delivery_then_pickup"),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER"),
            order_review_number=os.getenv("ORDER_REVIEW_NUMBER"),
        )

    @property
    def fulfillment_summary(self) -> str:
        if self.fulfillment_preference == "delivery_then_pickup":
            return (
                f"Delivery to ZIP {self.delivery_zip} is preferred; use pickup if delivery "
                "is unavailable."
            )
        if self.fulfillment_preference == "pickup":
            return "Pickup is preferred."
        return f"Fulfillment preference: {self.fulfillment_preference}."

    @property
    def sms_is_configured(self) -> bool:
        return all(
            (
                self.twilio_account_sid,
                self.twilio_auth_token,
                self.twilio_from_number,
                self.order_review_number,
            )
        )
