"""Production WhatsApp Cloud API adapter using env-configured credentials."""

from datetime import datetime, timezone
from typing import Any
import httpx

from app.adapters.interfaces import WhatsAppSendResult


class ProductionWhatsAppAdapter:
    mode = "production"

    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id

    def send_message(
        self, to_number: str, body: str, metadata: dict[str, Any] | None = None
    ) -> WhatsAppSendResult:
        if not self.access_token or not self.phone_number_id:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set")

        url = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number.lstrip("+"),
            "type": "text",
            "text": {"body": body},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        msg_id = data.get("messages", [{}])[0].get("id", "")
        return WhatsAppSendResult(
            provider_message_id=msg_id,
            status="sent",
            mode=self.mode,
            recipient=to_number,
            sent_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.access_token and self.phone_number_id)
        return {
            "adapter": "whatsapp_business",
            "mode": "production",
            "configured": configured,
            "note": "WhatsApp Cloud API v20 ready" if configured else "Missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID",
        }


class ProductionTwilioWhatsAppAdapter:
    mode = "production_twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

    def send_message(
        self, to_number: str, body: str, metadata: dict[str, Any] | None = None
    ) -> WhatsAppSendResult:
        if not self.account_sid or not self.auth_token or not self.from_number:
            raise RuntimeError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_FROM must be set")

        to_wa = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={"From": self.from_number, "To": to_wa, "Body": body},
            )
            resp.raise_for_status()
            data = resp.json()
        return WhatsAppSendResult(
            provider_message_id=data.get("sid", ""),
            status="sent",
            mode=self.mode,
            recipient=to_number,
            sent_at_iso=datetime.now(timezone.utc).isoformat(),
        )

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.account_sid and self.auth_token and self.from_number)
        return {
            "adapter": "whatsapp_business",
            "mode": self.mode,
            "configured": configured,
            "note": "Twilio WhatsApp Sandbox ready" if configured else "Missing Twilio WhatsApp credentials",
        }
