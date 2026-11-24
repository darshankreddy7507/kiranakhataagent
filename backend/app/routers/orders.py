"""WhatsApp-style Orders inbox and 9-step order processing routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WhatsAppOrder
from app.routers.serializers import serialize_approval, serialize_order
from app.schemas import (
    IncomingOrderCreate,
    OrderDecisionRequest,
    SubstituteSelectRequest,
)
from app.services.workflow import (
    ingest_incoming_order_workflow,
    process_order_decision_workflow,
    select_order_substitute_workflow,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(WhatsAppOrder).order_by(WhatsAppOrder.created_at.desc())
    if status and status != "all":
        q = q.filter(WhatsAppOrder.status == status)
    orders = q.all()
    return [serialize_order(db, o) for o in orders]


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(WhatsAppOrder).filter(WhatsAppOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize_order(db, order)


@router.post("/simulate-incoming")
def simulate_incoming_order(payload: IncomingOrderCreate, db: Session = Depends(get_db)):
    try:
        order = ingest_incoming_order_workflow(
            db,
            customer_id=payload.customer_id,
            channel=payload.channel,
            raw_message=payload.raw_message,
            payment_intent=payload.payment_intent,
        )
        return serialize_order(db, order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{order_id}/select-substitute")
def select_substitute(
    order_id: int, payload: SubstituteSelectRequest, db: Session = Depends(get_db)
):
    try:
        res = select_order_substitute_workflow(
            db,
            order_id=order_id,
            original_product_id=payload.original_product_id,
            substitute_product_id=payload.substitute_product_id,
            draft_reply_kn=payload.draft_reply_kn,
        )
        return {
            "order": serialize_order(db, res["order"]),
            "approval": serialize_approval(db, res["approval"]),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{order_id}/decision")
def decide_order(order_id: int, payload: OrderDecisionRequest, db: Session = Depends(get_db)):
    try:
        res = process_order_decision_workflow(
            db,
            order_id=order_id,
            decision=payload.decision,
            edited_items=payload.edited_items,
            draft_reply_kn=payload.draft_reply_kn,
            draft_reply_en=payload.draft_reply_en,
            note=payload.note,
            auto_send_reply=payload.auto_send_reply,
        )
        return {
            "order": serialize_order(db, res["order"]),
            "result": res["result"],
            "follow_up_approval": serialize_approval(db, res["follow_up_approval"]) if res["follow_up_approval"] else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
