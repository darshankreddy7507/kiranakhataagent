"""Production Supplier Bill-Image OCR adapter scaffold."""

from typing import Any
import httpx

from app.adapters.interfaces import BillExtractionResult


class ProductionBillOcrAdapter:
    mode = "production"

    def __init__(self, api_key: str, endpoint: str) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    def extract_bill(
        self, image_bytes: bytes | None, filename: str, scenario: str | None = None
    ) -> BillExtractionResult:
        if not self.api_key or not self.endpoint:
            raise RuntimeError("BILL_OCR_API_KEY and BILL_OCR_ENDPOINT must be set")
        if not image_bytes:
            raise ValueError("image_bytes required in production OCR mode")

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"image": (filename, image_bytes)},
            )
            resp.raise_for_status()
            data = resp.json()
        return BillExtractionResult(
            supplier_name=data["supplier_name"],
            invoice_number=data["invoice_number"],
            bill_date=data["bill_date"],
            items=data["items"],
            total_amount=float(data["total_amount"]),
            confidence=float(data.get("confidence", 0.9)),
            mode=self.mode,
        )

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.api_key and self.endpoint)
        return {
            "adapter": "bill_ocr",
            "mode": "production",
            "configured": configured,
            "note": "Bill OCR endpoint configured" if configured else "Missing BILL_OCR_API_KEY or BILL_OCR_ENDPOINT",
        }
