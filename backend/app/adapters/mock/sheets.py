"""Mock Google Sheets inventory/khata adapter for demo mode."""

from datetime import datetime, timezone
from typing import Any


class MockSheetsSyncAdapter:
    mode = "mock"

    def sync_inventory_row(self, sku: str, product_name: str, stock_qty: float, price: float) -> dict[str, Any]:
        return {
            "synced": True,
            "mode": self.mode,
            "sheet": "Kirana_Inventory_Mirror",
            "sku": sku,
            "stock_qty": stock_qty,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def sync_khata_row(self, customer_code: str, customer_name: str, balance: float) -> dict[str, Any]:
        return {
            "synced": True,
            "mode": self.mode,
            "sheet": "Kirana_Khata_Ledger",
            "customer_code": customer_code,
            "balance": balance,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": "google_sheets",
            "mode": "mock",
            "configured": True,
            "note": "Local SQLite mirror active (Google Sheets adapter mocked)",
        }
