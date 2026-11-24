"""Production Razorpay UPI payment-link & webhook verification adapter."""

import hashlib
import hmac
from typing import Any
import httpx

from app.adapters.interfaces import PaymentLinkResult


class ProductionRazorpayUpiAdapter:
    mode = "production"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str) -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret

    def create_upi_link(
        self, customer_name: str, customer_phone: str, amount: float, reference_id: str
    ) -> PaymentLinkResult:
        if not self.key_id or not self.key_secret:
            raise RuntimeError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set")
        payload = {
            "amount": int(round(amount * 100)),
            "currency": "INR",
            "upi_link": True,
            "description": f"Kirana Khata payment ({reference_id})",
            "customer": {"name": customer_name, "contact": customer_phone},
            "reference_id": reference_id,
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.razorpay.com/v1/payment_links",
                json=payload,
                auth=(self.key_id, self.key_secret),
            )
            resp.raise_for_status()
            data = resp.json()
        return PaymentLinkResult(
            provider_link_id=data["id"],
            short_url=data["short_url"],
            upi_intent_uri=data.get("short_url", ""),
            amount=round(amount, 2),
            mode=self.mode,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return False
        expected = hmac.new(
            self.webhook_secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.key_id and self.key_secret)
        return {
            "adapter": "razorpay_upi",
            "mode": "production",
            "configured": configured,
            "note": "Razorpay UPI API configured" if configured else "Missing RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET",
        }
