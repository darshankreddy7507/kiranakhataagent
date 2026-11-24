"""Khata ledger, overdue payment reminders, UPI payment links, and payment matching."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, KhataEntry, PaymentLink, WhatsAppOrder
from app.routers.serializers import (
    serialize_approval,
    serialize_customer,
    serialize_payment_link,
)
from app.schemas import CustomerDetailOut, KhataEntryOut, ReminderDraftRequest, SimulatePaymentRequest
from app.services.workflow import (
    REMINDER_STAGE_LABELS,
    build_reminder_copy,
    create_reminder_draft_workflow,
    simulate_payment_received_workflow,
)

router = APIRouter(prefix="/api/khata", tags=["khata"])


@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    customers = (
        db.query(Customer)
        .order_by(Customer.days_overdue.desc(), Customer.current_balance.desc())
        .all()
    )
    return [serialize_customer(c) for c in customers]


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
def get_customer_detail(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    entries = (
        db.query(KhataEntry)
        .filter(KhataEntry.customer_id == customer_id)
        .order_by(KhataEntry.created_at.desc())
        .all()
    )
    links = (
        db.query(PaymentLink)
        .filter(PaymentLink.customer_id == customer_id)
        .order_by(PaymentLink.created_at.desc())
        .all()
    )
    orders = (
        db.query(WhatsAppOrder)
        .filter(WhatsAppOrder.customer_id == customer_id)
        .order_by(WhatsAppOrder.created_at.desc())
        .limit(8)
        .all()
    )
    return CustomerDetailOut(
        customer=serialize_customer(customer),
        entries=[
            KhataEntryOut(
                id=e.id,
                customer_id=e.customer_id,
                entry_type=e.entry_type,
                amount=e.amount,
                balance_after=e.balance_after,
                order_id=e.order_id,
                payment_link_id=e.payment_link_id,
                description=e.description,
                description_kn=e.description_kn,
                approved_by_id=e.approved_by_id,
                created_at=e.created_at,
            )
            for e in entries
        ],
        payment_links=[serialize_payment_link(l) for l in links],
        recent_orders=[
            {
                "id": o.id,
                "order_code": o.order_code,
                "total_amount": o.total_amount,
                "status": o.status,
                "payment_intent": o.payment_intent,
                "created_at": o.created_at,
            }
            for o in orders
        ],
    )


@router.get("/overdue")
def get_overdue_queue(db: Session = Depends(get_db)):
    customers = (
        db.query(Customer)
        .filter(Customer.current_balance > 0, Customer.days_overdue > 0)
        .order_by(Customer.days_overdue.desc(), Customer.current_balance.desc())
        .all()
    )
    queue = []
    for c in customers:
        stage = c.reminder_stage or 1
        if c.days_overdue >= 35:
            stage = 4
        elif c.days_overdue >= 22:
            stage = max(stage, 3)
        elif c.days_overdue >= 15:
            stage = max(stage, 2)
        active_link = (
            db.query(PaymentLink)
            .filter(PaymentLink.customer_id == c.id, PaymentLink.status.in_(["created", "sent", "partial"]))
            .order_by(PaymentLink.created_at.desc())
            .first()
        )
        short_url = active_link.short_url if active_link else f"https://rzp.io/i/slks-{c.code}"
        kn_preview, en_preview, risk = build_reminder_copy(c, stage, short_url)
        queue.append(
            {
                "customer": serialize_customer(c),
                "recommended_stage": stage,
                "recommended_stage_label": REMINDER_STAGE_LABELS.get(stage, "Stage 1"),
                "payment_link": serialize_payment_link(active_link) if active_link else None,
                "preview_kn": kn_preview,
                "preview_en": en_preview,
                "risk_level": risk,
            }
        )
    return queue


@router.get("/payment-links")
def list_payment_links(db: Session = Depends(get_db)):
    links = db.query(PaymentLink).order_by(PaymentLink.created_at.desc()).all()
    return [serialize_payment_link(l) for l in links]


@router.post("/reminders/draft")
def create_reminder_draft(payload: ReminderDraftRequest, db: Session = Depends(get_db)):
    try:
        req = create_reminder_draft_workflow(
            db,
            customer_id=payload.customer_id,
            custom_message_kn=payload.custom_message_kn,
            custom_message_en=payload.custom_message_en,
        )
        return serialize_approval(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payments/simulate")
def simulate_payment(payload: SimulatePaymentRequest, db: Session = Depends(get_db)):
    try:
        res = simulate_payment_received_workflow(
            db,
            payment_link_id=payload.payment_link_id,
            customer_id=payload.customer_id,
            amount_paid=payload.amount_paid,
        )
        return {
            "payment_link": serialize_payment_link(res["payment_link"]),
            "customer": serialize_customer(res["customer"]),
            "old_balance": res["old_balance"],
            "new_balance": res["new_balance"],
            "amount_paid": res["amount_paid"],
            "is_partial": res["is_partial"],
            "thank_you_approval": serialize_approval(db, res["thank_you_approval"]),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
