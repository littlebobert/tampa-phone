from __future__ import annotations

import asyncio

from twilio.rest import Client

from tampa_phone.config import Settings


class OrderHandoff:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, body: str) -> str:
        if not self.settings.sms_is_configured:
            raise RuntimeError("SMS handoff is not configured")
        return await asyncio.to_thread(self._send_sync, body)

    def _send_sync(self, body: str) -> str:
        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=self.settings.twilio_from_number,
            to=self.settings.order_review_number,
        )
        return message.sid
