"""Mock Telegram Bot adapter for demo/offline mode."""

from datetime import datetime, timezone
import uuid
from typing import Any

from app.adapters.interfaces import WhatsAppSendResult


class MockTelegramAdapter:
    mode = "mock"

    def send_message(
        self, to_number: str, body: str, metadata: dict[str, Any] | None = None
    ) -> WhatsAppSendResult:
        return WhatsAppSendResult(
            provider_message_id=f"tg.mock.{uuid.uuid4().hex[:10]}",
            status="sent",
            mode=self.mode,
            recipient=to_number,
            sent_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "telegram_bot",
            "mode": "mock",
            "configured": False,
            "note": "Set TELEGRAM_BOT_TOKEN in backend/.env to connect a live Telegram bot",
        }
