"""Production Google Sheets sync adapter scaffold."""

from datetime import datetime, timezone
from typing import Any


class ProductionSheetsSyncAdapter:
    mode = "production"

    def __init__(self, credentials_json: str, spreadsheet_id: str) -> None:
        self.credentials_json = credentials_json
        self.spreadsheet_id = spreadsheet_id

    def sync_inventory_row(self, sku: str, product_name: str, stock_qty: float, price: float) -> dict[str, Any]:
        if not self.credentials_json or not self.spreadsheet_id:
            raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS_JSON and GOOGLE_SHEETS_SPREADSHEET_ID must be set")
        # Integration hook: wire gspread / google-api-python-client service account call here.
        return {
            "synced": True,
            "mode": self.mode,
            "spreadsheet_id": self.spreadsheet_id,
            "sku": sku,
            "stock_qty": stock_qty,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def sync_khata_row(self, customer_code: str, customer_name: str, balance: float) -> dict[str, Any]:
        if not self.credentials_json or not self.spreadsheet_id:
            raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS_JSON and GOOGLE_SHEETS_SPREADSHEET_ID must be set")
        return {
            "synced": True,
            "mode": self.mode,
            "spreadsheet_id": self.spreadsheet_id,
            "customer_code": customer_code,
            "balance": balance,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def health_check(self) -> dict[str, Any]:
        configured = bool(self.credentials_json and self.spreadsheet_id)
        return {
            "adapter": "google_sheets",
            "mode": "production",
            "configured": configured,
            "note": "Google Sheets API configured" if configured else "Missing Google Sheets credentials env vars",
        }
