"""Real-time SSE stream and WhatsApp (Meta Cloud API & Twilio) / Razorpay webhook endpoints."""

import re
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.config import get_settings
from app.database import get_db
from app.models import Customer, PaymentLink
from app.routers.serializers import serialize_order
from app.services.realtime import realtime_bus
from app.services.telegram_poller import process_telegram_update
from app.services.workflow import (
    ingest_incoming_order_workflow,
    simulate_payment_received_workflow,
)

router = APIRouter(prefix="/api", tags=["realtime"])


class SimpleWhatsAppWebhookPayload(BaseModel):
    phone: str | None = None
    customer_id: int | None = None
    sender_name: str | None = None
    message: str
    channel: str = "whatsapp_text"
    payment_intent: str | None = None


def _normalize_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)[-10:]


def _find_or_create_customer_by_phone(
    db: Session, phone: str, sender_name: str | None = None
) -> Customer | None:
    target = _normalize_digits(phone)
    if not target:
        return None
    for cust in db.query(Customer).all():
        if _normalize_digits(cust.whatsapp_number) == target or _normalize_digits(cust.phone) == target:
            return cust

    # Automatically register a new walk-in/WhatsApp customer when a real phone messages the shop
    display_name = (sender_name or "").strip() or f"WhatsApp Customer ({target[-4:]})"
    formatted_phone = f"+91{target}" if len(target) == 10 else f"+{re.sub(r'\\D', '', phone)}"
    cust = Customer(
        code=f"cust-{uuid.uuid4().hex[:6]}",
        name=display_name,
        name_kn=display_name,
        phone=formatted_phone,
        whatsapp_number=formatted_phone,
        address="WhatsApp Customer",
        credit_limit=3000.0,
        current_balance=0.0,
        days_overdue=0,
        reminder_stage=0,
        preferred_language="kn",
    )
    db.add(cust)
    db.flush()
    return cust


@router.get("/events/stream")
async def stream_events():
    """Server-Sent Events stream pushing real-time order, khata, stock, and approval updates."""
    return StreamingResponse(
        realtime_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    """Meta WhatsApp Business Cloud API webhook verification challenge."""
    expected = get_settings().whatsapp_verify_token or "kirana_demo_verify"
    if hub_mode == "subscribe" and hub_verify_token == expected and hub_challenge:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """Accept Meta WhatsApp Cloud API JSON, Twilio WhatsApp form-urlencoded, or simple {phone, message} JSON."""
    content_type = (request.headers.get("content-type") or "").lower()

    customer: Customer | None = None
    raw_message = ""
    channel = "whatsapp_text"
    payment_intent: str | None = None

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        sender_phone = str(form.get("From") or form.get("WaId") or "")
        sender_name = str(form.get("ProfileName") or "")
        raw_message = str(form.get("Body") or "").strip()
        num_media = int(str(form.get("NumMedia") or "0") or "0")
        if num_media > 0 and not raw_message:
            channel = "whatsapp_voice"
            raw_message = "Voice note order"
        customer = _find_or_create_customer_by_phone(db, sender_phone, sender_name=sender_name)
    else:
        body: dict[str, Any] = await request.json()

        # Meta WhatsApp Cloud API webhook payload
        if "entry" in body:
            try:
                change = body["entry"][0]["changes"][0]["value"]
                messages = change.get("messages") or []
                if not messages:
                    # Meta status callback (sent/delivered/read) — acknowledge with 200 OK
                    return {"received": True, "ignored": "status_update"}
                msg_obj = messages[0]
                sender_phone = msg_obj.get("from", "")
                contacts = change.get("contacts") or []
                sender_name = (
                    contacts[0].get("profile", {}).get("name") if contacts else None
                )
                msg_type = msg_obj.get("type", "text")
                if msg_type == "audio":
                    channel = "whatsapp_voice"
                    raw_message = msg_obj.get("audio", {}).get("caption") or "Voice note order"
                else:
                    raw_message = msg_obj.get("text", {}).get("body", "")
                customer = _find_or_create_customer_by_phone(
                    db, sender_phone, sender_name=sender_name
                )
            except (IndexError, KeyError, TypeError) as exc:
                raise HTTPException(status_code=400, detail="Invalid WhatsApp Cloud payload") from exc
        else:
            payload = SimpleWhatsAppWebhookPayload(**body)
            raw_message = payload.message
            channel = payload.channel
            payment_intent = payload.payment_intent
            if payload.customer_id:
                customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
            elif payload.phone:
                customer = _find_or_create_customer_by_phone(
                    db, payload.phone, sender_name=payload.sender_name
                )

    if not customer:
        raise HTTPException(status_code=400, detail="Could not identify customer phone or id")
    if not raw_message:
        raise HTTPException(status_code=400, detail="Empty WhatsApp message body")

    order = ingest_incoming_order_workflow(
        db,
        customer_id=customer.id,
        channel=channel,
        raw_message=raw_message,
        payment_intent=payment_intent,
    )
    return {
        "received": True,
        "order": serialize_order(db, order),
    }


@router.post("/webhooks/razorpay")
async def receive_razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Razorpay UPI payment link webhook (verifies signature in production mode)."""
    raw_body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    adapters = build_adapters()
    if not adapters.razorpay.verify_webhook_signature(raw_body, sig):
        raise HTTPException(status_code=401, detail="Invalid Razorpay signature")

    data = await request.json()
    link_code = data.get("payment_link_code") or data.get("link_code")
    amount_inr = float(data.get("amount_inr") or 0)
    if not link_code and "payload" in data:
        pl = data["payload"].get("payment_link", {}).get("entity", {})
        link_code = pl.get("id")
        amount_inr = float(pl.get("amount_paid", 0)) / 100.0

    link = db.query(PaymentLink).filter(PaymentLink.link_code == link_code).first()
    if not link:
        raise HTTPException(status_code=404, detail=f"PaymentLink '{link_code}' not found")
    if amount_inr <= 0:
        amount_inr = max(1.0, link.amount_requested - link.amount_paid)

    res = simulate_payment_received_workflow(
        db, payment_link_id=link.id, amount_paid=amount_inr
    )
    return {
        "matched": True,
        "customer": res["customer"].name,
        "amount_paid": res["amount_paid"],
        "new_balance": res["new_balance"],
        "thank_you_approval_code": res["thank_you_approval"].approval_code,
    }


@router.post("/webhooks/telegram")
async def receive_telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Telegram Bot API webhook update JSON (or use built-in polling via TELEGRAM_BOT_TOKEN)."""
    update: dict[str, Any] = await request.json()
    return process_telegram_update(db, update)
