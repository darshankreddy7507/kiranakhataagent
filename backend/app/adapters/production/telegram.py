"""Production Telegram Bot API adapter driven by TELEGRAM_BOT_TOKEN env var."""

from datetime import datetime, timezone
from typing import Any
import httpx

from app.adapters.interfaces import WhatsAppSendResult


class ProductionTelegramAdapter:
    mode = "production_telegram"

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    def send_message(
        self, to_number: str, body: str, metadata: dict[str, Any] | None = None
    ) -> WhatsAppSendResult:
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN must be set")

        chat_id = to_number.removeprefix("tg:").strip()
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": body})
            resp.raise_for_status()
            data = resp.json()
        msg_id = str(data.get("result", {}).get("message_id", ""))
        return WhatsAppSendResult(
            provider_message_id=f"tg.{msg_id}",
            status="sent",
            mode=self.mode,
            recipient=to_number,
            sent_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.bot_token)
        return {
            "adapter": "telegram_bot",
            "mode": self.mode,
            "configured": configured,
            "note": "Telegram Bot API active (long polling & live replies)" if configured else "Missing TELEGRAM_BOT_TOKEN",
        }
