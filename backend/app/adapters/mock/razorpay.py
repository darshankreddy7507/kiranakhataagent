"""Mock Razorpay UPI payment-link and webhook verification adapter."""

import uuid
from typing import Any

from app.adapters.interfaces import PaymentLinkResult


class MockRazorpayUpiAdapter:
    mode = "mock"

    def create_upi_link(
        self, customer_name: str, customer_phone: str, amount: float, reference_id: str
    ) -> PaymentLinkResult:
        token = uuid.uuid4().hex[:8]
        safe_name = customer_name.replace(" ", "%20")
        return PaymentLinkResult(
            provider_link_id=f"plink_mock_{token}",
            short_url=f"https://rzp.io/i/slks-{token}",
            upi_intent_uri=(
                f"upi://pay?pa=srilakshmikirana@okicici&pn=Sri%20Lakshmi%20Kirana%20Stores"
                f"&am={amount:.2f}&cu=INR&tn=Khata%20{reference_id}%20{safe_name}"
            ),
            amount=round(amount, 2),
            mode=self.mode,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        return True

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "razorpay_upi",
            "mode": "mock",
            "configured": True,
            "note": "Seeded mock Razorpay UPI link & webhook simulator active",
        }
