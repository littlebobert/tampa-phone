from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from twilio.rest import Client

from tampa_phone.config import Settings


@dataclass(frozen=True)
class HandoffResult:
    sid: str
    status: str
    error_code: int | None = None


class OrderHandoff:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, body: str) -> HandoffResult:
        if not self.settings.sms_is_configured:
            raise RuntimeError("SMS handoff is not configured")
        return await asyncio.to_thread(self._send_sync, body)

    def _send_sync(self, body: str) -> HandoffResult:
        account_sid = self.settings.twilio_account_sid
        auth_token = self.settings.twilio_auth_token
        from_number = self.settings.twilio_from_number
        review_number = self.settings.order_review_number
        if not all((account_sid, auth_token, from_number, review_number)):
            raise RuntimeError("SMS handoff is not configured")
        assert account_sid is not None
        assert auth_token is not None
        assert from_number is not None
        assert review_number is not None

        client = Client(account_sid, auth_token)
        message = client.messages.create(body=body, from_=from_number, to=review_number)
        if not message.sid:
            raise RuntimeError("Twilio accepted the request without returning a message SID")
        message_sid = message.sid
        for _ in range(16):
            message = client.messages(message_sid).fetch()
            if message.status in {"delivered", "undelivered", "failed"}:
                break
            time.sleep(0.5)
        return HandoffResult(
            sid=message_sid,
            status=str(message.status or "unknown"),
            error_code=message.error_code,
        )
