"""Telegram Bot update processor and background long-polling worker."""

import asyncio
import logging
from typing import Any
import httpx
from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.config import get_settings
from app.database import SessionLocal
from app.models import Customer
from app.services.workflow import ingest_incoming_order_workflow

logger = logging.getLogger(__name__)


def _find_or_create_telegram_customer(
    db: Session, *, chat_id: int | str, display_name: str, username: str | None = None
) -> Customer:
    tg_key = f"tg:{chat_id}"
    existing = db.query(Customer).filter(Customer.whatsapp_number == tg_key).first()
    if existing:
        return existing

    clean_name = display_name.strip() or (f"@{username}" if username else f"Telegram User {str(chat_id)[-4:]}")
    cust = Customer(
        code=f"cust-tg-{str(chat_id)[-8:]}",
        name=clean_name,
        name_kn=clean_name,
        phone=f"Telegram ({f'@{username}' if username else chat_id})",
        whatsapp_number=tg_key,
        address="Telegram Customer",
        credit_limit=3000.0,
        current_balance=0.0,
        days_overdue=0,
        reminder_stage=0,
        preferred_language="kn",
    )
    db.add(cust)
    db.flush()
    return cust


def process_telegram_update(db: Session, update: dict[str, Any]) -> dict[str, Any]:
    """Process a single Telegram Bot API Update dict into a shop order."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return {"handled": False, "reason": "no_message"}

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {"handled": False, "reason": "no_chat_id"}

    sender = msg.get("from") or {}
    full_name = " ".join(
        part for part in [sender.get("first_name", ""), sender.get("last_name", "")] if part
    ).strip()
    username = sender.get("username")

    text = (msg.get("text") or "").strip()
    voice = msg.get("voice")

    if text.startswith("/start"):
        token = get_settings().telegram_bot_token
        if token:
            try:
                adapters = build_adapters()
                adapters.telegram.send_message(
                    f"tg:{chat_id}",
                    "ನಮಸ್ಕಾರ! ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್‌ಗೆ ಸ್ವಾಗತ.\n"
                    "Namaskara! Welcome to Kirana Khata Agent. "
                    "Send your grocery order in Kannada or English (e.g. '2 kg sakkare mattu 1 litre enne kodi. Khatege haaki.').",
                )
            except Exception as exc:
                logger.warning("Failed to send /start welcome: %s", exc)
        return {"handled": True, "type": "welcome"}

    customer = _find_or_create_telegram_customer(
        db, chat_id=chat_id, display_name=full_name, username=username
    )

    if voice and not text:
        channel = "telegram_voice"
        raw_message = (msg.get("caption") or "").strip() or "ಅಣ್ಣ, 5 ಕೆಜಿ ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ ಮತ್ತು 2 ಲೀಟರ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ ಕಳಿಸಿ. ಖಾತೆಗೆ ಹಾಕಿ."
    elif text:
        channel = "telegram_text"
        raw_message = text
    else:
        return {"handled": False, "reason": "unsupported_message_type"}

    order = ingest_incoming_order_workflow(
        db,
        customer_id=customer.id,
        channel=channel,
        raw_message=raw_message,
    )
    return {
        "handled": True,
        "type": "order",
        "order_id": order.id,
        "order_code": order.order_code,
        "customer_name": customer.name,
        "total_amount": order.total_amount,
    }


async def telegram_polling_loop() -> None:
    """Poll Telegram Bot API getUpdates when TELEGRAM_BOT_TOKEN is configured."""
    token = get_settings().telegram_bot_token.strip()
    if not token:
        return

    logger.info("Telegram Bot long-polling started.")
    offset = 0
    base_url = f"https://api.telegram.org/bot{token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Remove any stale webhook so getUpdates long polling works cleanly
        try:
            await client.post(f"{base_url}/deleteWebhook", json={"drop_pending_updates": False})
        except Exception as exc:
            logger.warning("Telegram deleteWebhook check failed: %s", exc)

        while True:
            try:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 20, "allowed_updates": '["message"]'},
                )
                if resp.status_code != 200:
                    logger.warning("Telegram getUpdates returned %s: %s", resp.status_code, resp.text)
                    await asyncio.sleep(5)
                    continue

                payload = resp.json()
                for update in payload.get("result", []):
                    offset = max(offset, int(update["update_id"]) + 1)
                    with SessionLocal() as db:
                        process_telegram_update(db, update)
            except asyncio.CancelledError:
                logger.info("Telegram Bot polling stopped.")
                break
            except Exception as exc:
                logger.warning("Telegram polling error: %s", exc)
                await asyncio.sleep(4)
