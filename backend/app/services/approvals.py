"""Approval gating engine and immutable audit log helpers."""

from datetime import datetime, timezone
import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.adapters import build_adapters
from app.services.realtime import realtime_bus
from app.models import (
    ApprovalRequest,
    AuditLog,
    Customer,
    KhataEntry,
    PaymentLink,
    Product,
    Supplier,
    SupplierBill,
    SupplierOrder,
    WhatsAppMessage,
    WhatsAppOrder,
)


class ApprovalRequiredError(Exception):
    """Raised when a mutation or external send is attempted without an approved request."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _next_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def record_audit(
    db: Session,
    *,
    event_type: str,
    actor: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    summary_kn: str = "",
    mcp_tool: str | None = None,
    approval_id: int | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        actor=actor,
        mcp_tool=mcp_tool,
        approval_id=approval_id,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        summary_kn=summary_kn,
        before_state_json=before_state,
        after_state_json=after_state,
    )
    db.add(entry)
    db.flush()
    return entry


def create_approval_request(
    db: Session,
    *,
    action_type: str,
    title: str,
    title_kn: str,
    entity_type: str,
    entity_id: int,
    mcp_tool_name: str,
    payload: dict[str, Any],
    reason: str,
    source_data: dict[str, Any],
    customer_id: int | None = None,
    supplier_id: int | None = None,
    amount_impact: float | None = None,
    risk_level: str = "normal",
) -> ApprovalRequest:
    req = ApprovalRequest(
        approval_code=_next_code("APR"),
        action_type=action_type,
        title=title,
        title_kn=title_kn,
        entity_type=entity_type,
        entity_id=entity_id,
        customer_id=customer_id,
        supplier_id=supplier_id,
        mcp_tool_name=mcp_tool_name,
        payload_json=payload,
        reason=reason,
        source_data_json=source_data,
        amount_impact=amount_impact,
        risk_level=risk_level,
        status="pending",
    )
    db.add(req)
    db.flush()
    record_audit(
        db,
        event_type="approval_created",
        actor="mcp_agent",
        mcp_tool=mcp_tool_name,
        approval_id=req.id,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=f"Created approval {req.approval_code}: {title}",
        summary_kn=title_kn,
        after_state={"status": "pending", "amount_impact": amount_impact},
    )
    return req


def assert_approved_gate(db: Session, approval_id: int | None, expected_tools: tuple[str, ...]) -> ApprovalRequest:
    """Enforce that mutating MCP tools execute ONLY from an explicitly APPROVED request."""
    if not approval_id:
        raise ApprovalRequiredError(
            "Direct mutation blocked: create an ApprovalRequest and obtain owner approval first."
        )
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req:
        raise ApprovalRequiredError(f"ApprovalRequest #{approval_id} not found.")
    if req.status != "approved":
        raise ApprovalRequiredError(
            f"ApprovalRequest {req.approval_code} has status '{req.status}'; must be 'approved' before execution."
        )
    if expected_tools and req.mcp_tool_name not in expected_tools:
        raise ApprovalRequiredError(
            f"ApprovalRequest {req.approval_code} is bound to '{req.mcp_tool_name}', not {expected_tools}."
        )
    return req


def execute_update_inventory(
    db: Session, *, product_id: int, quantity_change: float, approval_id: int, reason_note: str
) -> Product:
    assert_approved_gate(
        db,
        approval_id,
        ("update_inventory", "fulfill_order", "extract_supplier_bill"),
    )
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise ValueError(f"Product #{product_id} not found")
    before_qty = prod.stock_qty
    new_qty = round(max(0.0, before_qty + quantity_change), 2)
    prod.stock_qty = new_qty
    if quantity_change > 0:
        prod.last_restocked_at = utcnow()
    db.flush()

    adapters = build_adapters()
    adapters.sheets.sync_inventory_row(prod.sku, prod.name, prod.stock_qty, prod.price)

    record_audit(
        db,
        event_type="inventory_updated",
        actor="owner",
        mcp_tool="update_inventory",
        approval_id=approval_id,
        entity_type="product",
        entity_id=prod.id,
        summary=f"{prod.name}: stock {before_qty} -> {new_qty} ({quantity_change:+g} {prod.unit}). {reason_note}",
        summary_kn=f"{prod.name_kn}: ಸ್ಟಾಕ್ {before_qty} ರಿಂದ {new_qty} ಕ್ಕೆ ಬದಲಾಯಿಸಲಾಗಿದೆ.",
        before_state={"stock_qty": before_qty},
        after_state={"stock_qty": new_qty},
    )
    return prod


def execute_create_khata_entry(
    db: Session,
    *,
    customer_id: int,
    amount: float,
    order_id: int | None,
    approval_id: int,
    description: str,
    description_kn: str = "",
) -> KhataEntry:
    assert_approved_gate(
        db,
        approval_id,
        ("create_khata_entry", "fulfill_order", "check_credit_limit"),
    )
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer #{customer_id} not found")

    before_balance = customer.current_balance
    customer.current_balance = round(before_balance + amount, 2)
    entry = KhataEntry(
        customer_id=customer.id,
        entry_type="credit_sale",
        amount=round(amount, 2),
        balance_after=customer.current_balance,
        order_id=order_id,
        description=description,
        description_kn=description_kn or description,
        approved_by_id=approval_id,
    )
    db.add(entry)
    db.flush()

    adapters = build_adapters()
    adapters.sheets.sync_khata_row(customer.code, customer.name, customer.current_balance)

    record_audit(
        db,
        event_type="khata_created",
        actor="owner",
        mcp_tool="create_khata_entry",
        approval_id=approval_id,
        entity_type="customer",
        entity_id=customer.id,
        summary=f"Khata +{amount:.0f} for {customer.name}: ₹{before_balance:.0f} -> ₹{customer.current_balance:.0f}",
        summary_kn=f"{customer.name_kn} ಖಾತೆಗೆ ₹{amount:.0f} ಸೇರಿಸಲಾಗಿದೆ. ಹೊಸ ಬಾಕಿ ₹{customer.current_balance:.0f}",
        before_state={"current_balance": before_balance},
        after_state={"current_balance": customer.current_balance},
    )
    return entry


def execute_send_approved_whatsapp_message(
    db: Session, *, message_id: int, approval_id: int
) -> WhatsAppMessage:
    assert_approved_gate(
        db,
        approval_id,
        ("send_approved_whatsapp_message", "create_reminder_draft"),
    )
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise ValueError(f"WhatsAppMessage #{message_id} not found")

    recipient = ""
    recipient_name = ""
    if msg.customer_id:
        cust = db.query(Customer).filter(Customer.id == msg.customer_id).first()
        if cust:
            recipient = cust.whatsapp_number
            recipient_name = cust.name
    elif msg.supplier_id:
        sup = db.query(Supplier).filter(Supplier.id == msg.supplier_id).first()
        if sup:
            recipient = sup.whatsapp_number
            recipient_name = sup.name

    adapters = build_adapters()
    if recipient.startswith("tg:"):
        send_res = adapters.telegram.send_message(recipient, msg.body_kn)
    else:
        send_res = adapters.whatsapp.send_message(recipient or "+919900000000", msg.body_kn)
    msg.status = "sent"
    msg.provider_message_id = send_res.provider_message_id
    msg.approval_id = approval_id
    msg.sent_at = utcnow()
    db.flush()

    record_audit(
        db,
        event_type="whatsapp_sent",
        actor="owner",
        mcp_tool="send_approved_whatsapp_message",
        approval_id=approval_id,
        entity_type="whatsapp_message",
        entity_id=msg.id,
        summary=f"Sent approved WhatsApp ({msg.message_type}) to {recipient_name} [{send_res.provider_message_id}]",
        summary_kn=f"{recipient_name} ಅವರಿಗೆ ಅನುಮೋದಿತ ವಾಟ್ಸಾಪ್ ಸಂದೇಶ ಕಳಿಸಲಾಗಿದೆ.",
        after_state={"status": "sent", "provider_message_id": send_res.provider_message_id},
    )
    return msg


def _stage_order_confirmation_message(db: Session, order: WhatsAppOrder, customer: Customer) -> ApprovalRequest:
    msg = WhatsAppMessage(
        message_code=_next_code("MSG"),
        customer_id=customer.id,
        direction="outbound",
        message_type="order_confirmation",
        body_kn=order.draft_reply_kn,
        body_en=order.draft_reply_en,
        status="pending_approval",
    )
    db.add(msg)
    db.flush()

    return create_approval_request(
        db,
        action_type="send_whatsapp",
        title=f"Send Kannada confirmation to {customer.name} ({order.order_code})",
        title_kn=f"{customer.name_kn} ಅವರಿಗೆ ಆರ್ಡರ್ ದೃಢೀಕರಣ ಸಂದೇಶ ಕಳಿಸಿ",
        entity_type="whatsapp_message",
        entity_id=msg.id,
        customer_id=customer.id,
        mcp_tool_name="send_approved_whatsapp_message",
        payload={
            "message_id": msg.id,
            "order_id": order.id,
            "order_code": order.order_code,
            "body_kn": msg.body_kn,
            "body_en": msg.body_en,
        },
        reason="Order stock & khata updated; final Kannada customer confirmation requires owner approval before sending.",
        source_data={"order_code": order.order_code, "customer": customer.name, "total_amount": order.total_amount},
        amount_impact=order.total_amount,
        risk_level="normal",
    )


def decide_approval_request(
    db: Session,
    *,
    approval_id: int,
    decision: str,
    edited_payload: dict[str, Any] | None = None,
    decision_note: str | None = None,
    actor: str = "Manjunath Gowda (Owner)",
) -> dict[str, Any]:
    """Approve or reject an ApprovalRequest, executing gated mutations only upon approval."""
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
    if not req:
        raise ValueError(f"ApprovalRequest #{approval_id} not found")
    if req.status != "pending":
        raise ValueError(f"ApprovalRequest {req.approval_code} is already '{req.status}'")

    payload = dict(req.payload_json or {})
    if edited_payload:
        payload.update(edited_payload)
        req.payload_json = payload

    if decision == "reject":
        req.status = "rejected"
        req.decision_note = decision_note or "Rejected by shop owner"
        req.decided_by = actor
        req.decided_at = utcnow()
        _mark_entity_rejected(db, req, req.decision_note)
        record_audit(
            db,
            event_type="rejected",
            actor="owner",
            mcp_tool=req.mcp_tool_name,
            approval_id=req.id,
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            summary=f"Rejected {req.approval_code} ({req.title}). Note: {req.decision_note}",
            summary_kn=f"ಅನುಮೋದನೆ {req.approval_code} ತಿರಸ್ಕರಿಸಲಾಗಿದೆ.",
            after_state={"status": "rejected", "note": req.decision_note},
        )
        db.commit()
        return {"approval": req, "follow_up_approval": None}

    # Approve and immediately mark status so gated tools verify status == 'approved'
    req.status = "approved"
    req.decision_note = decision_note or "Approved by shop owner"
    req.decided_by = actor
    req.decided_at = utcnow()
    db.flush()

    record_audit(
        db,
        event_type="approved",
        actor="owner",
        mcp_tool=req.mcp_tool_name,
        approval_id=req.id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        summary=f"Approved {req.approval_code}: {req.title}",
        summary_kn=f"{req.approval_code} ಅನುಮೋದಿಸಲಾಗಿದೆ: {req.title_kn}",
        after_state={"status": "approved"},
    )

    follow_up: ApprovalRequest | None = None

    if req.action_type in ("order_fulfill", "credit_override"):
        order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == req.entity_id).first()
        if not order:
            raise ValueError(f"Order #{req.entity_id} not found")
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        assert customer is not None

        items = payload.get("items") or order.parsed_items_json
        if payload.get("draft_reply_kn"):
            order.draft_reply_kn = payload["draft_reply_kn"]
        if payload.get("draft_reply_en"):
            order.draft_reply_en = payload["draft_reply_en"]

        total_amount = 0.0
        for item in items:
            pid = item.get("product_id")
            qty = float(item.get("qty", 0))
            if not pid or qty <= 0:
                continue
            prod = db.query(Product).filter(Product.id == pid).first()
            if not prod:
                continue
            execute_update_inventory(
                db,
                product_id=pid,
                quantity_change=-qty,
                approval_id=req.id,
                reason_note=f"Order {order.order_code} for {customer.name}",
            )
            line_total = round(qty * prod.price, 2)
            item["unit_price"] = prod.price
            item["line_total"] = line_total
            item["stock_qty"] = prod.stock_qty
            item["available"] = True
            total_amount += line_total

        order.parsed_items_json = items
        order.total_amount = round(total_amount, 2)

        if order.payment_intent == "credit":
            item_desc = ", ".join(f"{i.get('qty')} {i.get('unit')} {i.get('matched_product_name')}" for i in items)
            execute_create_khata_entry(
                db,
                customer_id=customer.id,
                amount=order.total_amount,
                order_id=order.id,
                approval_id=req.id,
                description=f"WhatsApp Order {order.order_code}: {item_desc}",
                description_kn=f"ವಾಟ್ಸಾಪ್ ಆರ್ಡರ್ {order.order_code}",
            )

        order.status = "confirmation_pending"
        order.workflow_stage = "owner_approve_message"
        follow_up = _stage_order_confirmation_message(db, order, customer)

    elif req.action_type in ("send_whatsapp", "payment_thank_you"):
        msg_id = int(payload["message_id"])
        msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == msg_id).first()
        if msg:
            if payload.get("body_kn"):
                msg.body_kn = payload["body_kn"]
            if payload.get("body_en"):
                msg.body_en = payload["body_en"]
        execute_send_approved_whatsapp_message(db, message_id=msg_id, approval_id=req.id)
        order_id = payload.get("order_id")
        if order_id:
            order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == order_id).first()
            if order:
                if msg and msg.message_type == "order_confirmation":
                    order.status = "completed"
                    order.workflow_stage = "completed"
                elif msg and msg.message_type in ("substitute_proposal", "credit_hold_request"):
                    order.status = "awaiting_customer"
                    order.workflow_stage = "awaiting_customer_reply"

    elif req.action_type == "payment_reminder":
        msg_id = int(payload["message_id"])
        customer_id = int(payload["customer_id"])
        msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == msg_id).first()
        cust = db.query(Customer).filter(Customer.id == customer_id).first()
        if msg:
            if payload.get("body_kn"):
                msg.body_kn = payload["body_kn"]
            if payload.get("body_en"):
                msg.body_en = payload["body_en"]
        if payload.get("stage") == 4 and cust:
            # Stage 4 long overdue: mark call logged / notified rather than automated WhatsApp push
            if msg:
                msg.status = "sent"
                msg.sent_at = utcnow()
            record_audit(
                db,
                event_type="whatsapp_sent",
                actor="owner",
                mcp_tool="create_reminder_draft",
                approval_id=req.id,
                entity_type="customer",
                entity_id=cust.id,
                summary=f"Stage 4 owner follow-up call scheduled/logged for {cust.name} (₹{cust.current_balance:.0f})",
                summary_kn=f"{cust.name_kn} ಅವರಿಗೆ ದೂರವಾಣಿ ಕರೆ ಮಾಡಲು ನಿಗದಿಪಡಿಸಲಾಗಿದೆ.",
            )
        else:
            execute_send_approved_whatsapp_message(db, message_id=msg_id, approval_id=req.id)
            if cust and cust.reminder_stage < 3:
                cust.reminder_stage = min(3, cust.reminder_stage + 1)

    elif req.action_type == "supplier_reorder":
        po = db.query(SupplierOrder).filter(SupplierOrder.id == req.entity_id).first()
        if not po:
            raise ValueError(f"SupplierOrder #{req.entity_id} not found")
        if payload.get("items"):
            po.items_json = payload["items"]
            po.total_estimated_cost = round(
                sum(float(i["ordered_qty"]) * float(i["unit_cost"]) for i in po.items_json), 2
            )
        if payload.get("whatsapp_draft_kn"):
            po.whatsapp_draft_kn = payload["whatsapp_draft_kn"]
        po.status = "approved_sent"
        po.sent_at = utcnow()

        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        adapters = build_adapters()
        send_res = adapters.whatsapp.send_message(
            supplier.whatsapp_number if supplier else "+919800000000",
            po.whatsapp_draft_kn,
        )
        msg = WhatsAppMessage(
            message_code=_next_code("MSG"),
            supplier_id=po.supplier_id,
            direction="outbound",
            message_type="supplier_reorder",
            body_kn=po.whatsapp_draft_kn,
            body_en=po.whatsapp_draft_en,
            status="sent",
            provider_message_id=send_res.provider_message_id,
            approval_id=req.id,
            sent_at=utcnow(),
        )
        db.add(msg)
        record_audit(
            db,
            event_type="supplier_order_sent",
            actor="owner",
            mcp_tool="create_supplier_order",
            approval_id=req.id,
            entity_type="supplier_order",
            entity_id=po.id,
            summary=f"Sent PO {po.po_code} to {supplier.name if supplier else 'Supplier'} (₹{po.total_estimated_cost:.0f})",
            summary_kn=f"{supplier.name_kn if supplier else 'ಸರಬರಾಜುದಾರರಿಗೆ'} PO {po.po_code} ಕಳಿಸಲಾಗಿದೆ.",
            after_state={"status": "approved_sent", "total_estimated_cost": po.total_estimated_cost},
        )

    elif req.action_type == "bill_stock_intake":
        bill = db.query(SupplierBill).filter(SupplierBill.id == req.entity_id).first()
        if not bill:
            raise ValueError(f"SupplierBill #{req.entity_id} not found")
        items = payload.get("items") or bill.extracted_items_json
        for item in items:
            pid = item.get("matched_product_id")
            qty = float(item.get("quantity", 0))
            if pid and qty > 0:
                execute_update_inventory(
                    db,
                    product_id=pid,
                    quantity_change=qty,
                    approval_id=req.id,
                    reason_note=f"Supplier bill {bill.invoice_number} ({bill.supplier_name_extracted})",
                )
        bill.status = "approved"
        record_audit(
            db,
            event_type="bill_posted",
            actor="owner",
            mcp_tool="extract_supplier_bill",
            approval_id=req.id,
            entity_type="supplier_bill",
            entity_id=bill.id,
            summary=f"Posted supplier bill {bill.invoice_number} ({len(items)} items, ₹{bill.total_amount:.0f}) to inventory",
            summary_kn=f"ಬಿಲ್ {bill.invoice_number} ವಸ್ತುಗಳನ್ನು ಸ್ಟಾಕ್‌ಗೆ ಸೇರಿಸಲಾಗಿದೆ.",
            after_state={"status": "approved"},
        )

    elif req.action_type == "voice_khata_entry":
        customer_id = int(payload["customer_id"])
        amount = float(payload["amount"])
        note = payload.get("description", "Voice command khata entry")
        execute_create_khata_entry(
            db,
            customer_id=customer_id,
            amount=amount,
            order_id=None,
            approval_id=req.id,
            description=note,
            description_kn=payload.get("description_kn", "ಧ್ವನಿ ಆಜ್ಞೆಯ ಖಾತೆ ದಾಖಲೆ"),
        )

    db.commit()
    realtime_bus.publish("approval_decided", {"approval_id": req.id, "decision": decision})
    return {"approval": req, "follow_up_approval": follow_up}


def _mark_entity_rejected(db: Session, req: ApprovalRequest, note: str) -> None:
    if req.action_type in ("order_fulfill", "credit_override"):
        order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == req.entity_id).first()
        if order:
            order.status = "rejected"
            order.workflow_stage = "rejected"
    elif req.action_type in ("send_whatsapp", "payment_reminder", "payment_thank_you"):
        msg_id = (req.payload_json or {}).get("message_id")
        if msg_id:
            msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == msg_id).first()
            if msg:
                msg.status = "rejected"
    elif req.action_type == "supplier_reorder":
        po = db.query(SupplierOrder).filter(SupplierOrder.id == req.entity_id).first()
        if po:
            po.status = "rejected"
    elif req.action_type == "bill_stock_intake":
        bill = db.query(SupplierBill).filter(SupplierBill.id == req.entity_id).first()
        if bill:
            bill.status = "rejected"
