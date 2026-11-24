"""Core workflow operations for Kirana Khata Agent (shared by FastAPI and MCP tools)."""

from datetime import date, datetime, timezone
import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.models import (
    ApprovalRequest,
    AuditLog,
    Customer,
    DailySummary,
    KhataEntry,
    PaymentLink,
    Product,
    ShopSettings,
    Supplier,
    SupplierBill,
    SupplierOrder,
    WhatsAppMessage,
    WhatsAppOrder,
)
from app.services.approvals import (
    create_approval_request,
    decide_approval_request,
    execute_update_inventory,
    record_audit,
)
from app.services.realtime import realtime_bus
from app.services.parser import (
    match_customer_by_text,
    match_product_by_text,
    parse_owner_voice_command,
    parse_whatsapp_order_message,
)


REMINDER_STAGE_LABELS = {
    0: "Current",
    1: "Stage 1 · Soft Reminder",
    2: "Stage 2 · Polite Follow-up",
    3: "Stage 3 · Firmer Request",
    4: "Stage 4 · Call Customer",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def product_stock_status(prod: Product) -> str:
    if prod.stock_qty <= 0:
        return "out_of_stock"
    if prod.stock_qty <= prod.reorder_level:
        return "low_stock"
    return "in_stock"


def create_payment_link_record(
    db: Session, *, customer: Customer, amount: float, reminder_stage: int = 1
) -> PaymentLink:
    adapters = build_adapters()
    res = adapters.razorpay.create_upi_link(
        customer_name=customer.name,
        customer_phone=customer.phone,
        amount=amount,
        reference_id=customer.code,
    )
    link = PaymentLink(
        link_code=res.provider_link_id,
        customer_id=customer.id,
        short_url=res.short_url,
        upi_intent_uri=res.upi_intent_uri,
        amount_requested=round(amount, 2),
        amount_paid=0.0,
        status="sent",
        reminder_stage=reminder_stage,
    )
    db.add(link)
    db.flush()
    return link


def build_reminder_copy(customer: Customer, stage: int, short_url: str) -> tuple[str, str, str]:
    """Return (kannada_body, english_body, risk_level) tuned to the gentle reminder stage."""
    amt = int(round(customer.current_balance))
    if stage <= 1:
        kn = (
            f"Namaskara {customer.name} avare. Nimma angadi khateyalli ₹{amt:,} baki ide. "
            f"Dayavittu saadhyavadashTu bega UPI link ({short_url}) mulaka payment maadi. "
            f"- Kirana Khata Agent"
        )
        en = (
            f"Gentle Stage 1 reminder: Namaskara {customer.name}, ₹{amt:,} is pending in your kirana khata. "
            f"Please pay via UPI link {short_url} at your convenience."
        )
        return kn, en, "normal"
    if stage == 2:
        kn = (
            f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಅಂಗಡಿ ಖಾತೆಯಲ್ಲಿ ₹{amt:,} ಬಾಕಿ {customer.days_overdue} "
            f"ದಿನಗಳಿಂದ ಬಾಕಿ ಇದೆ. ದಯವಿಟ್ಟು ಈ UPI ಲಿಂಕ್ ಮೂಲಕ ಪಾವತಿ ಮಾಡಿ: {short_url}. ಧನ್ಯವಾದಗಳು."
        )
        en = (
            f"Polite Stage 2 follow-up: {customer.name}, ₹{amt:,} has been overdue for {customer.days_overdue} days. "
            f"Please settle via {short_url}."
        )
        return kn, en, "attention"
    if stage == 3:
        kn = (
            f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಖಾತೆ ಬಾಕಿ ₹{amt:,} ({customer.days_overdue} ದಿನಗಳು) "
            f"ಇನ್ನೂ ಪಾವತಿಯಾಗಿಲ್ಲ. ಹೊಸ ಆರ್ಡರ್‌ಗಳಿಗೆ ಮುನ್ನ ದಯವಿಟ್ಟು ಇಂದು UPI ಮೂಲಕ ಪಾವತಿ ಮಾಡಿ: {short_url}"
        )
        en = (
            f"Firmer Stage 3 request: {customer.name}, ₹{amt:,} is {customer.days_overdue} days overdue. "
            f"Please complete payment today at {short_url} before placing new credit orders."
        )
        return kn, en, "attention"

    kn = (
        f"[ಮಾಲೀಕರ ಕರೆ ಸೂಚನೆ] {customer.name_kn} ({customer.phone}) ಅವರ ಖಾತೆ ₹{amt:,} "
        f"({customer.days_overdue} ದಿನ ಬಾಕಿ). ದಯವಿಟ್ಟು ನೇರವಾಗಿ ಕರೆ ಮಾಡಿ ಮಾತನಾಡಿ."
    )
    en = (
        f"[Owner Call Task] {customer.name} ({customer.phone}) is {customer.days_overdue} days overdue "
        f"with ₹{amt:,} balance. Please call the customer directly rather than sending an automated message."
    )
    return kn, en, "high"


def create_reminder_draft_workflow(
    db: Session,
    *,
    customer_id: int,
    custom_message_kn: str | None = None,
    custom_message_en: str | None = None,
) -> ApprovalRequest:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer #{customer_id} not found")
    if customer.current_balance <= 0:
        raise ValueError(f"{customer.name} has ₹0 balance; no reminder needed.")

    stage = customer.reminder_stage if customer.reminder_stage > 0 else 1
    if customer.days_overdue >= 35:
        stage = 4
    elif customer.days_overdue >= 22:
        stage = max(stage, 3)
    elif customer.days_overdue >= 15:
        stage = max(stage, 2)

    active_link = (
        db.query(PaymentLink)
        .filter(
            PaymentLink.customer_id == customer.id,
            PaymentLink.status.in_(["created", "sent", "partial"]),
        )
        .order_by(PaymentLink.created_at.desc())
        .first()
    )
    if not active_link:
        active_link = create_payment_link_record(
            db, customer=customer, amount=customer.current_balance, reminder_stage=stage
        )

    kn_body, en_body, risk_level = build_reminder_copy(customer, stage, active_link.short_url)
    final_kn = custom_message_kn.strip() if custom_message_kn else kn_body
    final_en = custom_message_en.strip() if custom_message_en else en_body

    msg = WhatsAppMessage(
        message_code=_code("MSG"),
        customer_id=customer.id,
        direction="outbound",
        message_type="payment_reminder",
        body_kn=final_kn,
        body_en=final_en,
        payment_link_id=active_link.id,
        status="pending_approval",
    )
    db.add(msg)
    db.flush()

    stage_label = REMINDER_STAGE_LABELS.get(stage, "Reminder")
    req = create_approval_request(
        db,
        action_type="payment_reminder",
        title=f"{stage_label} for {customer.name} (₹{int(customer.current_balance):,})",
        title_kn=f"{customer.name_kn} ಅವರಿಗೆ ಬಾಕಿ ನೆನಪು (₹{int(customer.current_balance):,})",
        entity_type="whatsapp_message",
        entity_id=msg.id,
        customer_id=customer.id,
        mcp_tool_name="create_reminder_draft",
        payload={
            "message_id": msg.id,
            "customer_id": customer.id,
            "payment_link_id": active_link.id,
            "short_url": active_link.short_url,
            "stage": stage,
            "stage_label": stage_label,
            "body_kn": final_kn,
            "body_en": final_en,
        },
        reason=(
            f"{customer.name} owes ₹{int(customer.current_balance):,} ({customer.days_overdue} days overdue). "
            f"Prepared {stage_label} with Razorpay UPI link {active_link.short_url}."
        ),
        source_data={
            "customer_balance": customer.current_balance,
            "days_overdue": customer.days_overdue,
            "reminder_stage": stage,
            "payment_link": active_link.short_url,
        },
        amount_impact=customer.current_balance,
        risk_level=risk_level,
    )
    db.commit()
    return req


def simulate_payment_received_workflow(
    db: Session,
    *,
    amount_paid: float,
    payment_link_id: int | None = None,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """Match Razorpay UPI payment link, update khata entry & balance, and queue thank-you approval."""
    link: PaymentLink | None = None
    if payment_link_id:
        link = db.query(PaymentLink).filter(PaymentLink.id == payment_link_id).first()
    elif customer_id:
        link = (
            db.query(PaymentLink)
            .filter(
                PaymentLink.customer_id == customer_id,
                PaymentLink.status.in_(["created", "sent", "partial"]),
            )
            .order_by(PaymentLink.created_at.desc())
            .first()
        )
    if not link and customer_id:
        cust_fallback = db.query(Customer).filter(Customer.id == customer_id).first()
        if not cust_fallback:
            raise ValueError(f"Customer #{customer_id} not found")
        link = create_payment_link_record(
            db, customer=cust_fallback, amount=max(amount_paid, cust_fallback.current_balance), reminder_stage=1
        )
    if not link:
        raise ValueError("Matching active UPI payment link not found")

    customer = db.query(Customer).filter(Customer.id == link.customer_id).first()
    if not customer:
        raise ValueError("Customer for payment link not found")

    applied = round(min(amount_paid, max(customer.current_balance, amount_paid)), 2)
    old_balance = customer.current_balance
    new_balance = round(max(0.0, old_balance - applied), 2)

    link.amount_paid = round(link.amount_paid + applied, 2)
    is_partial = new_balance > 0 and link.amount_paid < link.amount_requested
    link.status = "partial" if is_partial else "paid"
    link.paid_at = utcnow()

    customer.current_balance = new_balance
    customer.last_payment_date = utcnow()
    if new_balance == 0:
        customer.days_overdue = 0
        customer.reminder_stage = 0

    entry = KhataEntry(
        customer_id=customer.id,
        entry_type="payment_upi",
        amount=-applied,
        balance_after=new_balance,
        payment_link_id=link.id,
        description=f"UPI Payment matched ({link.link_code}) · {'Partial' if is_partial else 'Full'} ₹{applied:,.0f}",
        description_kn=f"UPI ಪಾವತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ ({link.link_code}) ₹{applied:,.0f}",
    )
    db.add(entry)
    db.flush()

    adapters = build_adapters()
    adapters.sheets.sync_khata_row(customer.code, customer.name, customer.current_balance)

    record_audit(
        db,
        event_type="payment_matched",
        actor="razorpay_webhook",
        mcp_tool="record_payment",
        entity_type="payment_link",
        entity_id=link.id,
        summary=(
            f"Matched ₹{applied:,.0f} UPI payment on {link.link_code} for {customer.name}. "
            f"Balance ₹{old_balance:,.0f} -> ₹{new_balance:,.0f} ({'partial' if is_partial else 'settled'})."
        ),
        summary_kn=f"{customer.name_kn} ಅವರಿಂದ ₹{applied:,.0f} UPI ಪಾವತಿ ಬಂದಿದೆ. ಉಳಿದ ಬಾಕಿ ₹{new_balance:,.0f}.",
        before_state={"balance": old_balance, "link_status": "sent"},
        after_state={"balance": new_balance, "link_status": link.status, "amount_paid": applied},
    )

    # Draft Kannada thank-you message gated by owner approval
    if new_balance > 0:
        kn_thanks = (
            f"ಧನ್ಯವಾದಗಳು {customer.name_kn} ಅವರೆ! ₹{int(applied):,} UPI ಪಾವತಿ ತಲುಪಿದೆ. "
            f"ನಿಮ್ಮ ಖಾತೆಯ ಉಳಿದ ಬಾಕಿ ₹{int(new_balance):,} ಆಗಿದೆ. - ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್."
        )
        en_thanks = (
            f"Thank you {customer.name}! Received partial UPI payment of ₹{int(applied):,}. "
            f"Remaining khata balance is ₹{int(new_balance):,}."
        )
    else:
        kn_thanks = (
            f"ಧನ್ಯವಾದಗಳು {customer.name_kn} ಅವರೆ! ₹{int(applied):,} ಪೂರ್ಣ UPI ಪಾವತಿ ತಲುಪಿದೆ. "
            f"ನಿಮ್ಮ ಖಾತೆ ಬಾಕಿ ₹0 ಆಗಿದೆ. - ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್."
        )
        en_thanks = (
            f"Thank you {customer.name}! Received full UPI payment of ₹{int(applied):,}. "
            f"Your khata balance is now ₹0."
        )

    msg = WhatsAppMessage(
        message_code=_code("MSG"),
        customer_id=customer.id,
        direction="outbound",
        message_type="payment_thank_you",
        body_kn=kn_thanks,
        body_en=en_thanks,
        payment_link_id=link.id,
        status="pending_approval",
    )
    db.add(msg)
    db.flush()

    thank_you_approval = create_approval_request(
        db,
        action_type="payment_thank_you",
        title=f"Send Kannada thank-you to {customer.name} (₹{int(applied):,} received)",
        title_kn=f"{customer.name_kn} ಅವರಿಗೆ ಪಾವತಿ ಧನ್ಯವಾದ ಸಂದೇಶ ಕಳಿಸಿ",
        entity_type="whatsapp_message",
        entity_id=msg.id,
        customer_id=customer.id,
        mcp_tool_name="send_approved_whatsapp_message",
        payload={
            "message_id": msg.id,
            "customer_id": customer.id,
            "amount_paid": applied,
            "new_balance": new_balance,
            "body_kn": kn_thanks,
            "body_en": en_thanks,
        },
        reason=f"Razorpay webhook matched ₹{int(applied):,} on {link.link_code}; Kannada receipt message ready for owner approval.",
        source_data={
            "payment_link_code": link.link_code,
            "old_balance": old_balance,
            "amount_paid": applied,
            "new_balance": new_balance,
            "is_partial": is_partial,
        },
        amount_impact=applied,
        risk_level="normal",
    )
    db.commit()

    realtime_bus.publish("payment_matched", {"customer_id": customer.id, "amount_paid": applied})
    return {
        "payment_link": link,
        "customer": customer,
        "khata_entry": entry,
        "old_balance": old_balance,
        "new_balance": new_balance,
        "amount_paid": applied,
        "is_partial": is_partial,
        "thank_you_approval": thank_you_approval,
    }


def ingest_incoming_order_workflow(
    db: Session,
    *,
    customer_id: int,
    channel: str,
    raw_message: str,
    payment_intent: str | None = None,
) -> WhatsAppOrder:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer #{customer_id} not found")

    transcript_kn = None
    transcript_conf = None
    audio_dur = None
    effective_text = raw_message

    if channel in ("whatsapp_voice", "telegram_voice"):
        adapters = build_adapters()
        stt = adapters.kannada_stt.transcribe(None, "incoming_voice.ogg", hint_text=raw_message)
        transcript_kn = stt.transcript_kn
        transcript_conf = stt.confidence
        audio_dur = stt.duration_sec
        effective_text = stt.transcript_kn

    parsed = parse_whatsapp_order_message(db, customer, effective_text, payment_intent)
    order = WhatsAppOrder(
        order_code=_code("ORD"),
        customer_id=customer.id,
        channel=channel,
        raw_message=raw_message,
        english_translation=parsed["english_translation"],
        audio_duration_sec=audio_dur,
        audio_transcript_kn=transcript_kn,
        transcript_confidence=transcript_conf,
        intent=parsed["intent"],
        payment_intent=parsed["payment_intent"],
        status=parsed["status"],
        workflow_stage=parsed["workflow_stage"],
        parsed_items_json=parsed["parsed_items"],
        total_amount=parsed["total_amount"],
        credit_check_status=parsed["credit_check_status"],
        suggested_action=parsed["suggested_action"],
        reason_text=parsed["reason_text"],
        source_data_json=parsed["source_data"],
        draft_reply_kn=parsed["draft_reply_kn"],
        draft_reply_en=parsed["draft_reply_en"],
        is_repeat_order=parsed["is_repeat_order"],
        reference_order_id=parsed["reference_order_id"],
    )
    db.add(order)
    db.flush()

    if order.status in ("pending_approval", "credit_warning"):
        action_type = "credit_override" if order.credit_check_status == "exceeds_limit" else "order_fulfill"
        risk = "high" if action_type == "credit_override" else "normal"
        create_approval_request(
            db,
            action_type=action_type,
            title=(
                f"Credit limit check: {customer.name} order {order.order_code} (₹{int(order.total_amount):,})"
                if action_type == "credit_override"
                else f"Approve order {order.order_code} from {customer.name} (₹{int(order.total_amount):,})"
            ),
            title_kn=f"{customer.name_kn} ಆರ್ಡರ್ {order.order_code} ಅನುಮೋದಿಸಿ (₹{int(order.total_amount):,})",
            entity_type="whatsapp_order",
            entity_id=order.id,
            customer_id=customer.id,
            mcp_tool_name="check_credit_limit" if action_type == "credit_override" else "fulfill_order",
            payload={
                "order_id": order.id,
                "order_code": order.order_code,
                "items": order.parsed_items_json,
                "total_amount": order.total_amount,
                "draft_reply_kn": order.draft_reply_kn,
                "draft_reply_en": order.draft_reply_en,
            },
            reason=order.reason_text,
            source_data=order.source_data_json,
            amount_impact=order.total_amount,
            risk_level=risk,
        )

    db.commit()
    db.refresh(order)
    realtime_bus.publish("order_received", {"order_id": order.id, "order_code": order.order_code})
    return order


def select_order_substitute_workflow(
    db: Session,
    *,
    order_id: int,
    original_product_id: int,
    substitute_product_id: int,
    draft_reply_kn: str | None = None,
) -> dict[str, Any]:
    order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == order_id).first()
    if not order:
        raise ValueError(f"Order #{order_id} not found")
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    sub_prod = db.query(Product).filter(Product.id == substitute_product_id).first()
    if not sub_prod or not customer:
        raise ValueError("Substitute product or customer not found")

    items = [dict(i) for i in (order.parsed_items_json or [])]
    orig_name = ""
    for item in items:
        if item.get("product_id") == original_product_id:
            orig_name = item.get("matched_product_name", "")
            qty = float(item.get("qty", 1))
            item["product_id"] = sub_prod.id
            item["matched_product_name"] = sub_prod.name
            item["matched_product_name_kn"] = sub_prod.name_kn
            item["unit"] = sub_prod.unit
            item["unit_price"] = sub_prod.price
            item["line_total"] = round(qty * sub_prod.price, 2)
            item["stock_qty"] = sub_prod.stock_qty
            item["available"] = sub_prod.stock_qty >= qty
            item["selected_substitute_id"] = sub_prod.id
            item["substitute_options"] = []

    order.parsed_items_json = items
    order.total_amount = round(sum(float(i["line_total"]) for i in items), 2)

    # Check credit limit with new total
    projected = customer.current_balance + (order.total_amount if order.payment_intent == "credit" else 0)
    credit_exceeded = order.payment_intent == "credit" and projected > customer.credit_limit
    order.credit_check_status = "exceeds_limit" if credit_exceeded else "ok"
    order.status = "credit_warning" if credit_exceeded else "pending_approval"
    order.workflow_stage = "awaiting_owner_approval"
    order.suggested_action = (
        f"Substitute applied ({orig_name} -> {sub_prod.name}). Approve order & send Kannada confirmation."
    )

    if draft_reply_kn and draft_reply_kn.strip():
        order.draft_reply_kn = draft_reply_kn.strip()
    else:
        item_summary_kn = ", ".join(f"{int(i['qty'])} {i['unit']} {i['matched_product_name_kn']}" for i in items)
        order.draft_reply_kn = (
            f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. {orig_name} ಬದಲಾಗಿ {sub_prod.name_kn} ಸೇರಿಸಲಾಗಿದೆ. "
            f"ನಿಮ್ಮ ಆರ್ಡರ್ ({item_summary_kn}) ಒಟ್ಟು ₹{int(order.total_amount):,}. ದಯವಿಟ್ಟು ತಿಳಿಸಿ."
        )
    order.draft_reply_en = (
        f"Substituted {orig_name} with {sub_prod.name}. Updated total is ₹{int(order.total_amount):,}."
    )

    # Cancel any stale pending order approval and create fresh approval
    stale = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == "whatsapp_order",
            ApprovalRequest.entity_id == order.id,
            ApprovalRequest.status == "pending",
        )
        .all()
    )
    for s in stale:
        s.status = "rejected"
        s.decision_note = "Replaced after substitute selection"

    action_type = "credit_override" if credit_exceeded else "order_fulfill"
    req = create_approval_request(
        db,
        action_type=action_type,
        title=f"Approve order {order.order_code} with substitute {sub_prod.name} (₹{int(order.total_amount):,})",
        title_kn=f"{customer.name_kn} ಆರ್ಡರ್ {order.order_code} ({sub_prod.name_kn}) ಅನುಮೋದಿಸಿ",
        entity_type="whatsapp_order",
        entity_id=order.id,
        customer_id=customer.id,
        mcp_tool_name="fulfill_order",
        payload={
            "order_id": order.id,
            "order_code": order.order_code,
            "items": items,
            "total_amount": order.total_amount,
            "draft_reply_kn": order.draft_reply_kn,
            "draft_reply_en": order.draft_reply_en,
        },
        reason=f"Owner selected {sub_prod.name} as substitute for out-of-stock {orig_name}.",
        source_data={"original_product": orig_name, "substitute": sub_prod.name, "total_amount": order.total_amount},
        amount_impact=order.total_amount,
        risk_level="attention",
    )
    db.commit()
    return {"order": order, "approval": req}


def process_order_decision_workflow(
    db: Session,
    *,
    order_id: int,
    decision: str,
    edited_items: list[dict[str, Any]] | None = None,
    draft_reply_kn: str | None = None,
    draft_reply_en: str | None = None,
    note: str | None = None,
    auto_send_reply: bool = False,
) -> dict[str, Any]:
    order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == order_id).first()
    if not order:
        raise ValueError(f"Order #{order_id} not found")
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    assert customer is not None

    if edited_items is not None:
        order.parsed_items_json = edited_items
        order.total_amount = round(sum(float(i.get("line_total", 0)) for i in edited_items), 2)
    if draft_reply_kn:
        order.draft_reply_kn = draft_reply_kn
    if draft_reply_en:
        order.draft_reply_en = draft_reply_en
    db.flush()

    pending_order_req = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.entity_type == "whatsapp_order",
            ApprovalRequest.entity_id == order.id,
            ApprovalRequest.status == "pending",
        )
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )

    if decision == "cancel":
        if pending_order_req:
            decide_approval_request(
                db,
                approval_id=pending_order_req.id,
                decision="reject",
                decision_note=note or "Cancelled by owner",
            )
        else:
            order.status = "cancelled"
            order.workflow_stage = "cancelled"
            record_audit(
                db,
                event_type="rejected",
                actor="owner",
                entity_type="whatsapp_order",
                entity_id=order.id,
                summary=f"Cancelled order {order.order_code} for {customer.name}",
                summary_kn=f"{customer.name_kn} ಆರ್ಡರ್ {order.order_code} ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ.",
            )
            db.commit()
        return {"order": order, "result": "cancelled", "follow_up_approval": None}

    if decision == "ask_payment":
        # Reject the pending credit override and stage a payment-first WhatsApp request + UPI link
        if pending_order_req:
            pending_order_req.status = "rejected"
            pending_order_req.decision_note = note or "Owner chose: Ask for payment first"
            pending_order_req.decided_by = "Manjunath Gowda (Owner)"
            pending_order_req.decided_at = utcnow()
        order.status = "awaiting_payment"
        order.workflow_stage = "ask_for_payment_first"
        req = create_reminder_draft_workflow(
            db,
            customer_id=customer.id,
            custom_message_kn=(
                f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಹಳೆಯ ಬಾಕಿ ₹{int(customer.current_balance):,} "
                f"ಮತ್ತು ಹೊಸ ಆರ್ಡರ್ ₹{int(order.total_amount):,} ಇದೆ. ದಯವಿಟ್ಟು ಮೊದಲು ಹಳೆಯ ಬಾಕಿಯನ್ನು ಪಾವತಿಸಿ."
            ),
            custom_message_en=(
                f"Namaskara {customer.name}. Your current balance is ₹{int(customer.current_balance):,} "
                f"(limit ₹{int(customer.credit_limit):,}). Please pay part of your balance before we dispatch "
                f"order {order.order_code} (₹{int(order.total_amount):,})."
            ),
        )
        return {"order": order, "result": "payment_requested", "follow_up_approval": req}

    # decision == "approve"
    if not pending_order_req:
        pending_order_req = create_approval_request(
            db,
            action_type="order_fulfill",
            title=f"Approve order {order.order_code} from {customer.name}",
            title_kn=f"{customer.name_kn} ಆರ್ಡರ್ {order.order_code} ಅನುಮೋದಿಸಿ",
            entity_type="whatsapp_order",
            entity_id=order.id,
            customer_id=customer.id,
            mcp_tool_name="fulfill_order",
            payload={
                "order_id": order.id,
                "order_code": order.order_code,
                "items": order.parsed_items_json,
                "draft_reply_kn": order.draft_reply_kn,
                "draft_reply_en": order.draft_reply_en,
            },
            reason=order.reason_text or "Owner initiated order approval",
            source_data=order.source_data_json or {},
            amount_impact=order.total_amount,
        )
        db.flush()

    res = decide_approval_request(
        db,
        approval_id=pending_order_req.id,
        decision="approve",
        edited_payload={
            "items": order.parsed_items_json,
            "draft_reply_kn": order.draft_reply_kn,
            "draft_reply_en": order.draft_reply_en,
        },
        decision_note=note or "Approved from Orders Inbox",
    )
    follow_up = res["follow_up_approval"]
    if auto_send_reply and follow_up is not None:
        decide_approval_request(
            db,
            approval_id=follow_up.id,
            decision="approve",
            edited_payload={
                "body_kn": order.draft_reply_kn,
                "body_en": order.draft_reply_en,
            },
            decision_note="1-click confirm & send reply",
        )
        db.refresh(order)
        return {"order": order, "result": "completed", "follow_up_approval": follow_up}

    db.refresh(order)
    return {"order": order, "result": "approved_awaiting_message_send", "follow_up_approval": follow_up}


def create_supplier_reorder_draft_workflow(
    db: Session,
    *,
    supplier_id: int | None = None,
    product_ids: list[int] | None = None,
    custom_items: list[dict[str, Any]] | None = None,
    whatsapp_draft_kn: str | None = None,
) -> dict[str, Any]:
    """Draft a supplier purchase order for low-stock products and gate sending behind approval."""
    products: list[Product] = []
    if product_ids:
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    elif supplier_id:
        products = (
            db.query(Product)
            .filter(Product.supplier_id == supplier_id, Product.stock_qty <= Product.reorder_level)
            .all()
        )
    if not products and custom_items:
        ids = [int(i["product_id"]) for i in custom_items if i.get("product_id")]
        products = db.query(Product).filter(Product.id.in_(ids)).all()
    if not products:
        raise ValueError("No low-stock products selected for supplier reorder.")

    target_supplier_id = supplier_id or products[0].supplier_id
    supplier = db.query(Supplier).filter(Supplier.id == target_supplier_id).first()
    if not supplier:
        raise ValueError("Supplier not found")

    custom_qty_map = {int(i["product_id"]): float(i["ordered_qty"]) for i in (custom_items or []) if i.get("product_id")}
    po_items: list[dict[str, Any]] = []
    for prod in products:
        suggested_qty = prod.default_reorder_qty
        ordered_qty = custom_qty_map.get(prod.id, suggested_qty)
        po_items.append(
            {
                "product_id": prod.id,
                "sku": prod.sku,
                "product_name": prod.name,
                "product_name_kn": prod.name_kn,
                "current_stock": prod.stock_qty,
                "reorder_level": prod.reorder_level,
                "suggested_qty": suggested_qty,
                "ordered_qty": ordered_qty,
                "unit": prod.unit,
                "unit_cost": prod.cost_price,
                "line_cost": round(ordered_qty * prod.cost_price, 2),
            }
        )

    total_cost = round(sum(i["line_cost"] for i in po_items), 2)
    lines_kn = "\n".join(
        f"• {i['product_name_kn']} ({i['product_name']}): {int(i['ordered_qty'])} {i['unit']}"
        for i in po_items
    )
    lines_en = ", ".join(f"{int(i['ordered_qty'])} {i['unit']} {i['product_name']}" for i in po_items)

    draft_kn = whatsapp_draft_kn or (
        f"ನಮಸ್ಕಾರ {supplier.contact_person} ಅವರೆ ({supplier.name_kn}).\n"
        f"ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್‌ಗೆ ಈ ಕೆಳಗಿನ ಸ್ಟಾಕ್ ಕಳಿಸಿ:\n{lines_kn}\n"
        f"ದಯವಿಟ್ಟು ಬಿಲ್ ಜೊತೆ ಇಂದು ಸಂಜೆ ಒಳಗೆ ತಲುಪಿಸಿ."
    )
    draft_en = (
        f"Namaskara {supplier.contact_person} ({supplier.name}). Please supply for Kirana Khata Agent: "
        f"{lines_en}. Estimated total ₹{int(total_cost):,}."
    )

    po = SupplierOrder(
        po_code=_code("PO"),
        supplier_id=supplier.id,
        items_json=po_items,
        total_estimated_cost=total_cost,
        whatsapp_draft_kn=draft_kn,
        whatsapp_draft_en=draft_en,
        status="pending_approval",
    )
    db.add(po)
    db.flush()

    req = create_approval_request(
        db,
        action_type="supplier_reorder",
        title=f"Supplier reorder {po.po_code} -> {supplier.name} (₹{int(total_cost):,})",
        title_kn=f"{supplier.name_kn} ಸ್ಟಾಕ್ ಆರ್ಡರ್ {po.po_code} ಅನುಮೋದಿಸಿ",
        entity_type="supplier_order",
        entity_id=po.id,
        supplier_id=supplier.id,
        mcp_tool_name="create_supplier_order",
        payload={
            "po_id": po.id,
            "po_code": po.po_code,
            "supplier_id": supplier.id,
            "items": po_items,
            "whatsapp_draft_kn": draft_kn,
            "whatsapp_draft_en": draft_en,
        },
        reason=(
            f"{len(po_items)} item(s) at or below reorder threshold: "
            + ", ".join(f"{i['product_name']} ({i['current_stock']}/{i['reorder_level']})" for i in po_items)
        ),
        source_data={"supplier": supplier.name, "low_stock_items": po_items},
        amount_impact=total_cost,
        risk_level="attention",
    )
    db.commit()
    return {"supplier_order": po, "approval": req}


def ingest_supplier_bill_workflow(
    db: Session,
    *,
    image_bytes: bytes | None,
    filename: str,
    scenario: str | None = None,
) -> dict[str, Any]:
    adapters = build_adapters()
    extracted = adapters.bill_ocr.extract_bill(image_bytes, filename, scenario=scenario)

    supplier = None
    for sup in db.query(Supplier).all():
        if sup.name.lower() in extracted.supplier_name.lower() or extracted.supplier_name.lower() in sup.name.lower():
            supplier = sup
            break

    products = db.query(Product).all()
    sku_map = {p.sku: p for p in products}
    mapped_items: list[dict[str, Any]] = []
    for raw in extracted.items:
        matched = sku_map.get(raw.get("sku_hint", "")) or match_product_by_text(db, raw["item_name"])
        mapped_items.append(
            {
                "item_name": raw["item_name"],
                "matched_product_id": matched.id if matched else None,
                "matched_product_name": matched.name if matched else raw["item_name"],
                "quantity": float(raw["quantity"]),
                "unit": raw["unit"],
                "unit_price": float(raw["unit_price"]),
                "line_total": float(raw["line_total"]),
            }
        )

    bill = SupplierBill(
        bill_code=_code("BILL"),
        supplier_id=supplier.id if supplier else None,
        supplier_name_extracted=extracted.supplier_name,
        invoice_number=extracted.invoice_number,
        bill_date=extracted.bill_date,
        image_filename=filename,
        extracted_items_json=mapped_items,
        total_amount=extracted.total_amount,
        ocr_confidence=extracted.confidence,
        status="pending_approval",
    )
    db.add(bill)
    db.flush()

    req = create_approval_request(
        db,
        action_type="bill_stock_intake",
        title=f"Add stock from supplier bill {bill.invoice_number} ({extracted.supplier_name})",
        title_kn=f"ಬಿಲ್ {bill.invoice_number} ({extracted.supplier_name}) ಸ್ಟಾಕ್ ದೃಢೀಕರಿಸಿ",
        entity_type="supplier_bill",
        entity_id=bill.id,
        supplier_id=supplier.id if supplier else None,
        mcp_tool_name="extract_supplier_bill",
        payload={
            "bill_id": bill.id,
            "invoice_number": bill.invoice_number,
            "supplier_name": extracted.supplier_name,
            "items": mapped_items,
            "total_amount": extracted.total_amount,
        },
        reason=(
            f"OCR extracted {len(mapped_items)} line items totaling ₹{int(extracted.total_amount):,} "
            f"({int(extracted.confidence * 100)}% confidence). Inventory will update only after approval."
        ),
        source_data={
            "image_filename": filename,
            "invoice_number": bill.invoice_number,
            "ocr_confidence": extracted.confidence,
        },
        amount_impact=extracted.total_amount,
        risk_level="attention",
    )
    db.commit()
    return {"bill": bill, "approval": req}


def generate_daily_summary_workflow(db: Session, *, persist: bool = True) -> DailySummary:
    today_iso = date.today().isoformat()
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)

    # Compute real operational metrics from orders & khata entries
    todays_orders = (
        db.query(WhatsAppOrder)
        .filter(
            WhatsAppOrder.status.in_(["completed", "confirmation_pending", "approved"]),
            WhatsAppOrder.updated_at >= today_start,
        )
        .all()
    )
    # Include historical same-day seeded entries in KhataEntry as well
    todays_khata = db.query(KhataEntry).filter(KhataEntry.created_at >= today_start).all()

    credit_sales = round(sum(e.amount for e in todays_khata if e.entry_type == "credit_sale" and e.amount > 0), 2)
    payments_collected = round(
        sum(abs(e.amount) for e in todays_khata if e.entry_type in ("payment_upi", "payment_cash")), 2
    )
    cash_upi_sales = round(
        sum(o.total_amount for o in todays_orders if o.payment_intent in ("cash", "upi")), 2
    )
    total_sales = round(credit_sales + cash_upi_sales, 2)

    low_stock_prods = (
        db.query(Product)
        .filter(Product.stock_qty <= Product.reorder_level)
        .order_by(Product.stock_qty.asc())
        .all()
    )
    low_stock_items = [
        {
            "id": p.id,
            "name": p.name,
            "name_kn": p.name_kn,
            "stock_qty": p.stock_qty,
            "reorder_level": p.reorder_level,
            "unit": p.unit,
        }
        for p in low_stock_prods
    ]

    overdue_custs = (
        db.query(Customer)
        .filter(Customer.current_balance > 0, Customer.days_overdue > 0)
        .order_by(Customer.current_balance.desc())
        .all()
    )
    top_overdue = [
        {
            "id": c.id,
            "name": c.name,
            "name_kn": c.name_kn,
            "balance": c.current_balance,
            "days_overdue": c.days_overdue,
            "reminder_stage": c.reminder_stage,
        }
        for c in overdue_custs[:3]
    ]

    pending_approvals = db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending").count()

    top_overdue_en = ", ".join(f"{c['name']} (₹{int(c['balance']):,}, {c['days_overdue']}d)" for c in top_overdue) or "None"
    top_overdue_kn = ", ".join(f"{c['name_kn']} (₹{int(c['balance']):,}, {c['days_overdue']} ದಿನ)" for c in top_overdue) or "ಯಾರೂ ಇಲ್ಲ"
    low_stock_names_en = ", ".join(p["name"] for p in low_stock_items[:4]) or "All stocked"
    low_stock_names_kn = ", ".join(p["name_kn"] for p in low_stock_items[:4]) or "ಎಲ್ಲಾ ಸ್ಟಾಕ್ ಇದೆ"

    shop_row = db.query(ShopSettings).first()
    shop_en = shop_row.shop_name if shop_row else "Kirana Khata Agent"
    shop_kn = shop_row.shop_name_kn if shop_row else "ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್"
    owner_first = (shop_row.owner_name if shop_row else "Manjunath").split()[0]

    text_en = (
        f"9 PM Daily Summary · {shop_en} ({today_iso}): "
        f"Total sales ₹{int(total_sales):,} (Credit ₹{int(credit_sales):,}, Cash/UPI ₹{int(cash_upi_sales):,}). "
        f"Payments collected today ₹{int(payments_collected):,}. "
        f"{len(low_stock_items)} low-stock items ({low_stock_names_en}). "
        f"Top overdue: {top_overdue_en}. Pending approvals: {pending_approvals}."
    )
    text_kn = (
        f"ರಾತ್ರಿ 9 ಗಂಟೆಯ ದಿನದ ಸಾರಾಂಶ · {shop_kn} ({today_iso}): "
        f"ಇಂದಿನ ಒಟ್ಟು ಮಾರಾಟ ₹{int(total_sales):,} (ಖಾತೆ ₹{int(credit_sales):,}, ನಗದು/UPI ₹{int(cash_upi_sales):,}). "
        f"ಇಂದು ವಸೂಲಾದ ಹಣ ₹{int(payments_collected):,}. "
        f"ಕಡಿಮೆ ಸ್ಟಾಕ್ ವಸ್ತುಗಳು: {len(low_stock_items)} ({low_stock_names_kn}). "
        f"ಹೆಚ್ಚು ಬಾಕಿ ಇರುವವರು: {top_overdue_kn}. ಬಾಕಿ ಅನುಮೋದನೆಗಳು: {pending_approvals}."
    )
    voice_script_kn = (
        f"ನಮಸ್ಕಾರ {owner_first} ಅವರೇ, ಇಂದಿನ {shop_kn} ವರದಿ ಹೀಗಿದೆ. "
        f"ಇಂದು ಒಟ್ಟು ₹{int(total_sales):,} ಮಾರಾಟವಾಗಿದೆ. ಇದರಲ್ಲಿ ₹{int(credit_sales):,} ಖಾತೆ ಮಾರಾಟ ಮತ್ತು "
        f"₹{int(payments_collected):,} ಹಣ ವಸೂಲಾಗಿದೆ. "
        f"ಪ್ರಸ್ತುತ {len(low_stock_items)} ವಸ್ತುಗಳ ಸ್ಟಾಕ್ ಕಡಿಮೆ ಇದೆ ಮತ್ತು {pending_approvals} ಅನುಮೋದನೆಗಳು ಬಾಕಿ ಇವೆ."
    )

    summary = DailySummary(
        summary_date=today_iso,
        total_sales=total_sales,
        credit_sales=credit_sales,
        cash_upi_sales=cash_upi_sales,
        payments_collected=payments_collected,
        low_stock_count=len(low_stock_items),
        pending_approvals_count=pending_approvals,
        top_overdue_json=top_overdue,
        low_stock_items_json=low_stock_items,
        text_en=text_en,
        text_kn=text_kn,
        voice_script_kn=voice_script_kn,
    )
    if persist:
        db.add(summary)
        db.flush()
        record_audit(
            db,
            event_type="daily_summary_generated",
            actor="owner",
            mcp_tool="generate_daily_summary",
            entity_type="daily_summary",
            entity_id=summary.id,
            summary=f"Generated 9 PM Daily Summary (Sales ₹{int(total_sales):,}, Collected ₹{int(payments_collected):,})",
            summary_kn="ರಾತ್ರಿ 9 ಗಂಟೆಯ ದಿನದ ವರದಿ ಸಿದ್ಧಪಡಿಸಲಾಗಿದೆ.",
        )
        db.commit()
    return summary


def process_owner_voice_command_workflow(db: Session, *, command_text: str) -> dict[str, Any]:
    """Execute read queries or stage approval-gated write requests from owner Kannada voice commands."""
    parsed = parse_owner_voice_command(command_text)
    intent = parsed["intent"]

    if intent == "check_stock":
        prod = match_product_by_text(db, command_text)
        if not prod:
            return {
                "transcript": command_text,
                "english_meaning": "Check product inventory stock",
                "intent": intent,
                "summary_en": "Could not identify a matching product. Try mentioning Sugar (Sakkare), Rice, Oil, or Toor Dal.",
                "summary_kn": "ಸಂಬಂಧಿತ ವಸ್ತು ಕಂಡುಬಂದಿಲ್ಲ. ಸಕ್ಕರೆ, ಅಕ್ಕಿ, ಎಣ್ಣೆ ಅಥವಾ ಬೇಳೆ ಹೆಸರಿಸಿ.",
                "result_data": {},
                "created_approval": None,
                "mcp_tool_used": "get_inventory",
                "source_data": {"command": command_text},
            }
        status = product_stock_status(prod)
        return {
            "transcript": command_text,
            "english_meaning": f"How much {prod.name} stock is available?",
            "intent": intent,
            "summary_en": (
                f"{prod.name}: {prod.stock_qty:g} {prod.unit} in stock "
                f"(reorder threshold: {prod.reorder_level:g} {prod.unit}, status: {status.replace('_', ' ')})."
            ),
            "summary_kn": (
                f"{prod.name_kn} ಪ್ರಸ್ತುತ ಸ್ಟಾಕ್: {prod.stock_qty:g} {prod.unit} "
                f"(ಕನಿಷ್ಠ ಮಟ್ಟ: {prod.reorder_level:g} {prod.unit})."
            ),
            "result_data": {
                "product_id": prod.id,
                "name": prod.name,
                "name_kn": prod.name_kn,
                "stock_qty": prod.stock_qty,
                "reorder_level": prod.reorder_level,
                "unit": prod.unit,
                "status": status,
            },
            "created_approval": None,
            "mcp_tool_used": "get_inventory",
            "source_data": {"product_sku": prod.sku, "stock_qty": prod.stock_qty},
        }

    customer = match_customer_by_text(db, command_text)
    if not customer:
        return {
            "transcript": command_text,
            "english_meaning": "Customer lookup command",
            "intent": intent,
            "summary_en": "Customer not recognized. Try Ramesh, Suresh, Lakshmi, Kumar, Geetha, or Basavaraj.",
            "summary_kn": "ಗ್ರಾಹಕರ ಹೆಸರು ಗುರುತಿಸಲಾಗಲಿಲ್ಲ. ರಮೇಶ್, ಸುರೇಶ್, ಲಕ್ಷ್ಮೀ ಅಥವಾ ಕುಮಾರ್ ಪ್ರಯತ್ನಿಸಿ.",
            "result_data": {},
            "created_approval": None,
            "mcp_tool_used": "get_customer_balance",
            "source_data": {"command": command_text},
        }

    if intent == "check_balance":
        return {
            "transcript": command_text,
            "english_meaning": f"How much khata balance does {customer.name} owe?",
            "intent": intent,
            "summary_en": (
                f"{customer.name} owes ₹{int(customer.current_balance):,} "
                f"(Credit limit ₹{int(customer.credit_limit):,}, {customer.days_overdue} days overdue)."
            ),
            "summary_kn": (
                f"{customer.name_kn} ಅವರ ಬಾಕಿ ₹{int(customer.current_balance):,} "
                f"(ಕ್ರೆಡಿಟ್ ಮಿತಿ ₹{int(customer.credit_limit):,}, {customer.days_overdue} ದಿನ ಬಾಕಿ)."
            ),
            "result_data": {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "current_balance": customer.current_balance,
                "credit_limit": customer.credit_limit,
                "days_overdue": customer.days_overdue,
            },
            "created_approval": None,
            "mcp_tool_used": "get_customer_balance",
            "source_data": {"customer_code": customer.code, "current_balance": customer.current_balance},
        }

    if intent == "send_reminder":
        req = create_reminder_draft_workflow(db, customer_id=customer.id)
        return {
            "transcript": command_text,
            "english_meaning": f"Draft and queue a WhatsApp payment reminder for {customer.name}.",
            "intent": intent,
            "summary_en": f"Drafted payment reminder for {customer.name} (₹{int(customer.current_balance):,}). Queued for your approval ({req.approval_code}).",
            "summary_kn": f"{customer.name_kn} ಅವರಿಗೆ ₹{int(customer.current_balance):,} ಪಾವತಿ ನೆನಪು ಸಿದ್ಧವಾಗಿದೆ. ಅನುಮೋದನೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ.",
            "result_data": {"approval_id": req.id, "approval_code": req.approval_code, "payload": req.payload_json},
            "created_approval": req,
            "mcp_tool_used": "create_reminder_draft",
            "source_data": req.source_data_json,
        }

    # add_khata: strictly approval-gated!
    amount = float(parsed.get("amount") or 500.0)
    projected = customer.current_balance + amount
    over = projected > customer.credit_limit
    req = create_approval_request(
        db,
        action_type="voice_khata_entry",
        title=f"Voice Khata Entry: Add ₹{int(amount):,} to {customer.name}",
        title_kn=f"ಧ್ವನಿ ಆಜ್ಞೆ: {customer.name_kn} ಖಾತೆಗೆ ₹{int(amount):,} ಸೇರಿಸಿ",
        entity_type="customer",
        entity_id=customer.id,
        customer_id=customer.id,
        mcp_tool_name="create_khata_entry",
        payload={
            "customer_id": customer.id,
            "amount": amount,
            "description": f"Owner voice command: '{command_text}'",
            "description_kn": f"ಮಾಲೀಕರ ಧ್ವನಿ ಆಜ್ಞೆ: {command_text}",
        },
        reason=(
            f"Voice command parsed as +₹{int(amount):,} credit for {customer.name}. "
            + (
                f"WARNING: New balance ₹{int(projected):,} exceeds limit ₹{int(customer.credit_limit):,}!"
                if over
                else "Within credit limit. Requires owner approval before modifying ledger."
            )
        ),
        source_data={
            "voice_command": command_text,
            "current_balance": customer.current_balance,
            "credit_limit": customer.credit_limit,
            "projected_balance": projected,
        },
        amount_impact=amount,
        risk_level="high" if over else "normal",
    )
    db.commit()
    return {
        "transcript": command_text,
        "english_meaning": f"Add ₹{int(amount):,} to {customer.name}'s khata ledger.",
        "intent": "add_khata",
        "summary_en": (
            f"Prepared ₹{int(amount):,} khata entry for {customer.name} "
            f"(Current: ₹{int(customer.current_balance):,} -> Projected: ₹{int(projected):,}). "
            f"Approve {req.approval_code} to post."
        ),
        "summary_kn": (
            f"{customer.name_kn} ಖಾತೆಗೆ ₹{int(amount):,} ಸೇರಿಸಲು ಅನುಮೋದನೆ ವಿನಂತಿ ({req.approval_code}) ಸಿದ್ಧವಾಗಿದೆ."
        ),
        "result_data": {
            "approval_id": req.id,
            "approval_code": req.approval_code,
            "projected_balance": projected,
            "over_limit": over,
        },
        "created_approval": req,
        "mcp_tool_used": "create_khata_entry",
        "source_data": req.source_data_json,
    }


def owner_add_stock_workflow(
    db: Session,
    *,
    product_id: int,
    quantity_added: float,
    note: str | None = None,
    new_price: float | None = None,
) -> Product:
    """Owner-initiated stock addition: records owner approval + immutable audit log and increments stock."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise ValueError(f"Product #{product_id} not found")

    if new_price is not None:
        prod.price = round(new_price, 2)

    req = create_approval_request(
        db,
        action_type="bill_stock_intake",
        title=f"Owner added +{quantity_added:g} {prod.unit} of {prod.name}",
        title_kn=f"ಮಾಲೀಕರು {prod.name_kn} ಸ್ಟಾಕ್ +{quantity_added:g} {prod.unit} ಸೇರಿಸಿದ್ದಾರೆ",
        entity_type="product",
        entity_id=prod.id,
        supplier_id=prod.supplier_id,
        mcp_tool_name="update_inventory",
        payload={"product_id": prod.id, "quantity_change": quantity_added, "note": note or "New stock received"},
        reason=note or "Owner directly added newly received stock in Inventory.",
        source_data={"sku": prod.sku, "previous_stock": prod.stock_qty, "added": quantity_added},
        risk_level="normal",
    )
    req.status = "approved"
    req.decided_by = "Manjunath Gowda (Owner)"
    req.decided_at = utcnow()
    req.decision_note = "Direct owner stock entry"
    db.flush()

    updated = execute_update_inventory(
        db,
        product_id=prod.id,
        quantity_change=quantity_added,
        approval_id=req.id,
        reason_note=note or "New stock received by owner",
    )
    db.commit()
    db.refresh(updated)
    realtime_bus.publish("stock_updated", {"product_id": updated.id, "stock_qty": updated.stock_qty})
    return updated


def owner_create_product_workflow(
    db: Session,
    *,
    name: str,
    name_kn: str | None,
    category: str,
    unit: str,
    price: float,
    cost_price: float | None,
    stock_qty: float,
    reorder_level: float,
    supplier_id: int,
) -> Product:
    """Create a brand-new inventory item and log it to the audit trail."""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise ValueError(f"Supplier #{supplier_id} not found")

    sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
    clean_name = name.strip()
    clean_kn = (name_kn or clean_name).strip()
    aliases = [clean_name.lower(), clean_name.split()[0].lower()]
    if clean_kn and clean_kn != clean_name:
        aliases.append(clean_kn)

    prod = Product(
        sku=sku,
        name=clean_name,
        name_kn=clean_kn,
        aliases_json=list(dict.fromkeys(aliases)),
        category=category.strip() or "Staples",
        unit=unit.strip() or "kg",
        price=round(price, 2),
        cost_price=round(cost_price if cost_price is not None else price * 0.85, 2),
        stock_qty=round(stock_qty, 2),
        reorder_level=round(reorder_level, 2),
        default_reorder_qty=max(10.0, round(reorder_level * 2, 2)),
        supplier_id=supplier.id,
        last_restocked_at=utcnow(),
    )
    db.add(prod)
    db.flush()

    adapters = build_adapters()
    adapters.sheets.sync_inventory_row(prod.sku, prod.name, prod.stock_qty, prod.price)

    record_audit(
        db,
        event_type="inventory_updated",
        actor="owner",
        mcp_tool="update_inventory",
        entity_type="product",
        entity_id=prod.id,
        summary=f"Added new product '{prod.name}' with {prod.stock_qty:g} {prod.unit} @ ₹{prod.price:.0f}",
        summary_kn=f"ಹೊಸ ವಸ್ತು '{prod.name_kn}' ({prod.stock_qty:g} {prod.unit}) ಸೇರಿಸಲಾಗಿದೆ.",
        after_state={"sku": prod.sku, "stock_qty": prod.stock_qty, "price": prod.price},
    )
    db.commit()
    db.refresh(prod)
    realtime_bus.publish("stock_updated", {"product_id": prod.id, "stock_qty": prod.stock_qty})
    return prod
