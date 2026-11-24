"""Clean protocol/ABC interfaces for future production integrations."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class WhatsAppSendResult:
    provider_message_id: str
    status: str
    mode: str
    recipient: str
    sent_at_iso: str


@dataclass
class PaymentLinkResult:
    provider_link_id: str
    short_url: str
    upi_intent_uri: str
    amount: float
    mode: str


@dataclass
class SpeechTranscriptionResult:
    transcript_kn: str
    english_meaning: str
    confidence: float
    duration_sec: int
    mode: str


@dataclass
class BillExtractionResult:
    supplier_name: str
    invoice_number: str
    bill_date: str
    items: list[dict[str, Any]]
    total_amount: float
    confidence: float
    mode: str


class WhatsAppAdapter(Protocol):
    """WhatsApp Business Cloud API adapter interface."""

    mode: str

    def send_message(self, to_number: str, body: str, metadata: dict[str, Any] | None = None) -> WhatsAppSendResult:
        ...

    def health_check(self) -> dict[str, Any]:
        ...


class SheetsSyncAdapter(Protocol):
    """Google Sheets inventory & khata sync adapter interface."""

    mode: str

    def sync_inventory_row(self, sku: str, product_name: str, stock_qty: float, price: float) -> dict[str, Any]:
        ...

    def sync_khata_row(self, customer_code: str, customer_name: str, balance: float) -> dict[str, Any]:
        ...

    def health_check(self) -> dict[str, Any]:
        ...


class RazorpayUpiAdapter(Protocol):
    """Razorpay UPI payment-link and webhook verification adapter interface."""

    mode: str

    def create_upi_link(self, customer_name: str, customer_phone: str, amount: float, reference_id: str) -> PaymentLinkResult:
        ...

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        ...

    def health_check(self) -> dict[str, Any]:
        ...


class KannadaSttAdapter(Protocol):
    """Kannada speech-to-text adapter interface."""

    mode: str

    def transcribe(self, audio_bytes: bytes | None, filename: str, hint_text: str | None = None) -> SpeechTranscriptionResult:
        ...

    def health_check(self) -> dict[str, Any]:
        ...


class BillOcrAdapter(Protocol):
    """Supplier bill-image OCR adapter interface."""

    mode: str

    def extract_bill(self, image_bytes: bytes | None, filename: str, scenario: str | None = None) -> BillExtractionResult:
        ...

    def health_check(self) -> dict[str, Any]:
        ...
