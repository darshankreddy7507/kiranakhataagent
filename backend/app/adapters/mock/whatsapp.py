"""Mock WhatsApp Business adapter for demo workflows."""

from datetime import datetime, timezone
import uuid
from typing import Any

from app.adapters.interfaces import WhatsAppSendResult


class MockWhatsAppAdapter:
    mode = "mock"

    def send_message(
        self, to_number: str, body: str, metadata: dict[str, Any] | None = None
    ) -> WhatsAppSendResult:
        return WhatsAppSendResult(
            provider_message_id=f"wamid.mock.{uuid.uuid4().hex[:12]}",
            status="sent",
            mode=self.mode,
            recipient=to_number,
            sent_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "whatsapp_business",
            "mode": "mock",
            "configured": True,
            "note": "Seeded mock WhatsApp gateway active (no external API call)",
        }
