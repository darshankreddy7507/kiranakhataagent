"""Mock Supplier Bill-Image OCR adapter for demo stock-intake verification."""

from datetime import date
import hashlib
from typing import Any

from app.adapters.interfaces import BillExtractionResult


class MockBillOcrAdapter:
    mode = "mock"

    def extract_bill(
        self, image_bytes: bytes | None, filename: str, scenario: str | None = None
    ) -> BillExtractionResult:
        lower = f"{filename or ''} {scenario or ''}".lower()
        today_str = date.today().isoformat()

        if "oil" in lower or "ganesh" in lower or "ghee" in lower:
            items = [
                {"item_name": "Sunflower Oil 1 L Pouch", "sku_hint": "SKU-OIL-1L", "quantity": 24, "unit": "litre", "unit_price": 134.0, "line_total": 3216.0},
                {"item_name": "Nandini Pure Ghee 500 ml", "sku_hint": "SKU-GHEE-500ML", "quantity": 10, "unit": "jar", "unit_price": 295.0, "line_total": 2950.0},
                {"item_name": "Mustard Seeds (Sasuve) 200 g", "sku_hint": "SKU-MUSTARD-200G", "quantity": 15, "unit": "pack", "unit_price": 32.0, "line_total": 480.0},
            ]
            return BillExtractionResult(
                supplier_name="Nandini & Sri Ganesh Oil Depot",
                invoice_number="SGO-2026-4418",
                bill_date=today_str,
                items=items,
                total_amount=6646.0,
                confidence=0.95,
                mode=self.mode,
            )

        if "fmcg" in lower or "bengaluru" in lower or "soap" in lower or "tea" in lower:
            items = [
                {"item_name": "Mysore Sandal Soap 150 g", "sku_hint": "SKU-SOAP-MYSORE", "quantity": 30, "unit": "bar", "unit_price": 52.0, "line_total": 1560.0},
                {"item_name": "Red Label Tea 500 g", "sku_hint": "SKU-TEA-500G", "quantity": 12, "unit": "pack", "unit_price": 225.0, "line_total": 2700.0},
                {"item_name": "Surf Excel Easy Wash 1 kg", "sku_hint": "SKU-DETERGENT-1KG", "quantity": 15, "unit": "pack", "unit_price": 122.0, "line_total": 1830.0},
            ]
            return BillExtractionResult(
                supplier_name="Bengaluru FMCG Distributors",
                invoice_number="BFD-2026-8821",
                bill_date=today_str,
                items=items,
                total_amount=6090.0,
                confidence=0.93,
                mode=self.mode,
            )

        # Default staples bill from Kaveri Agro (restocks Aashirvaad Atta, Rice, Sugar, Toor Dal)
        seed_digest = hashlib.md5((filename or "sample_bill.jpg").encode()).hexdigest()[:4].upper()
        items = [
            {"item_name": "Aashirvaad Atta 5 kg", "sku_hint": "SKU-ATTA-AASHIRVAAD-5KG", "quantity": 12, "unit": "bag", "unit_price": 258.0, "line_total": 3096.0},
            {"item_name": "Sona Masoori Rice 1 kg", "sku_hint": "SKU-RICE-SONA-1KG", "quantity": 40, "unit": "kg", "unit_price": 52.0, "line_total": 2080.0},
            {"item_name": "Toor Dal 1 kg", "sku_hint": "SKU-TOOR-DAL-1KG", "quantity": 25, "unit": "kg", "unit_price": 138.0, "line_total": 3450.0},
            {"item_name": "White Sugar (Sakkare) 1 kg", "sku_hint": "SKU-SUGAR-1KG", "quantity": 30, "unit": "kg", "unit_price": 41.0, "line_total": 1230.0},
        ]
        return BillExtractionResult(
            supplier_name="Kaveri Agro & Staples Wholesale",
            invoice_number=f"KAW-2026-{seed_digest}",
            bill_date=today_str,
            items=items,
            total_amount=9856.0,
            confidence=0.96,
            mode=self.mode,
        )

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "bill_ocr",
            "mode": "mock",
            "configured": True,
            "note": "Mock Supplier Bill-Image OCR extractor active",
        }
