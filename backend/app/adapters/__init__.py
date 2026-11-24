"""Adapter registry selecting seeded mock adapters or env-configured production adapters."""

from dataclasses import dataclass

from app.adapters.interfaces import (
    BillOcrAdapter,
    KannadaSttAdapter,
    RazorpayUpiAdapter,
    SheetsSyncAdapter,
    WhatsAppAdapter,
)
from app.adapters.mock.bill_ocr import MockBillOcrAdapter
from app.adapters.mock.kannada_stt import MockKannadaSttAdapter
from app.adapters.mock.razorpay import MockRazorpayUpiAdapter
from app.adapters.mock.sheets import MockSheetsSyncAdapter
from app.adapters.mock.telegram import MockTelegramAdapter
from app.adapters.mock.whatsapp import MockWhatsAppAdapter
from app.adapters.production.bill_ocr import ProductionBillOcrAdapter
from app.adapters.production.kannada_stt import ProductionKannadaSttAdapter
from app.adapters.production.razorpay import ProductionRazorpayUpiAdapter
from app.adapters.production.sheets import ProductionSheetsSyncAdapter
from app.adapters.production.telegram import ProductionTelegramAdapter
from app.adapters.production.whatsapp import (
    ProductionTwilioWhatsAppAdapter,
    ProductionWhatsAppAdapter,
)
from app.config import Settings, get_settings


@dataclass
class AdapterBundle:
    whatsapp: WhatsAppAdapter
    telegram: WhatsAppAdapter
    sheets: SheetsSyncAdapter
    razorpay: RazorpayUpiAdapter
    kannada_stt: KannadaSttAdapter
    bill_ocr: BillOcrAdapter


def build_adapters(settings: Settings | None = None) -> AdapterBundle:
    cfg = settings or get_settings()

    telegram: WhatsAppAdapter = (
        ProductionTelegramAdapter(cfg.telegram_bot_token)
        if cfg.telegram_bot_token
        else MockTelegramAdapter()
    )

    # Select live WhatsApp adapter automatically whenever credentials are configured in env
    if cfg.whatsapp_access_token and cfg.whatsapp_phone_number_id:
        whatsapp: WhatsAppAdapter = ProductionWhatsAppAdapter(
            cfg.whatsapp_access_token, cfg.whatsapp_phone_number_id
        )
    elif cfg.twilio_account_sid and cfg.twilio_auth_token and cfg.twilio_whatsapp_from:
        whatsapp = ProductionTwilioWhatsAppAdapter(
            cfg.twilio_account_sid, cfg.twilio_auth_token, cfg.twilio_whatsapp_from
        )
    elif cfg.app_mode.lower() == "production":
        whatsapp = ProductionWhatsAppAdapter(cfg.whatsapp_access_token, cfg.whatsapp_phone_number_id)
    else:
        whatsapp = MockWhatsAppAdapter()

    if cfg.app_mode.lower() == "production":
        return AdapterBundle(
            whatsapp=whatsapp,
            telegram=telegram,
            sheets=ProductionSheetsSyncAdapter(cfg.google_sheets_credentials_json, cfg.google_sheets_spreadsheet_id),
            razorpay=ProductionRazorpayUpiAdapter(cfg.razorpay_key_id, cfg.razorpay_key_secret, cfg.razorpay_webhook_secret),
            kannada_stt=ProductionKannadaSttAdapter(cfg.kannada_stt_api_key, cfg.kannada_stt_endpoint),
            bill_ocr=ProductionBillOcrAdapter(cfg.bill_ocr_api_key, cfg.bill_ocr_endpoint),
        )
    return AdapterBundle(
        whatsapp=whatsapp,
        telegram=telegram,
        sheets=MockSheetsSyncAdapter(),
        razorpay=MockRazorpayUpiAdapter(),
        kannada_stt=MockKannadaSttAdapter(),
        bill_ocr=MockBillOcrAdapter(),
    )
