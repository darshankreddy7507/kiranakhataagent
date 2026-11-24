"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings for Kirana Khata Agent."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_mode: str = "demo"
    shop_name: str = "Kirana Khata Agent"
    shop_name_kn: str = "ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್"
    owner_name: str = "Manjunath Gowda"

    # Supports SQLite locally and PostgreSQL/Supabase in production
    database_url: str = "sqlite:///./kirana_khata.db"
    frontend_origin: str = "http://localhost:3000"

    # WhatsApp Business Cloud API
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""

    # Optional Twilio WhatsApp Sandbox
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""

    # Telegram Bot API (long polling + live replies)
    telegram_bot_token: str = ""

    # Google Sheets Sync
    google_sheets_credentials_json: str = ""
    google_sheets_spreadsheet_id: str = ""

    # Razorpay UPI
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Kannada Speech-to-Text
    kannada_stt_api_key: str = ""
    kannada_stt_endpoint: str = ""

    # Supplier Bill OCR
    bill_ocr_api_key: str = ""
    bill_ocr_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
