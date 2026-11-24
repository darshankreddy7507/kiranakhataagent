"""Shared ORM -> Pydantic response serializers."""

from sqlalchemy.orm import Session

from app.models import (
    ApprovalRequest,
    AuditLog,
    Customer,
    DailySummary,
    PaymentLink,
    Product,
    Supplier,
    SupplierBill,
    SupplierOrder,
    WhatsAppOrder,
)
from app.schemas import (
    ApprovalOut,
    AuditLogOut,
    CustomerOut,
    DailySummaryOut,
    PaymentLinkOut,
    ProductOut,
    SupplierBillOut,
    SupplierOrderOut,
    SupplierOut,
    WhatsAppOrderOut,
)
from app.services.workflow import REMINDER_STAGE_LABELS, product_stock_status


def serialize_customer(c: Customer) -> CustomerOut:
    over_limit = c.current_balance > c.credit_limit
    util = round((c.current_balance / c.credit_limit) * 100.0, 1) if c.credit_limit > 0 else 0.0
    return CustomerOut(
        id=c.id,
        code=c.code,
        name=c.name,
        name_kn=c.name_kn,
        phone=c.phone,
        whatsapp_number=c.whatsapp_number,
        address=c.address,
        credit_limit=c.credit_limit,
        current_balance=c.current_balance,
        days_overdue=c.days_overdue,
        last_payment_date=c.last_payment_date,
        reminder_stage=c.reminder_stage,
        reminder_stage_label=REMINDER_STAGE_LABELS.get(c.reminder_stage, "Current"),
        preferred_language=c.preferred_language,
        over_limit=over_limit,
        utilization_pct=util,
    )


def serialize_product(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        sku=p.sku,
        name=p.name,
        name_kn=p.name_kn,
        category=p.category,
        unit=p.unit,
        price=p.price,
        cost_price=p.cost_price,
        stock_qty=p.stock_qty,
        reorder_level=p.reorder_level,
        default_reorder_qty=p.default_reorder_qty,
        supplier_id=p.supplier_id,
        supplier_name=p.supplier.name if p.supplier else "",
        last_restocked_at=p.last_restocked_at,
        substitute_group=p.substitute_group,
        stock_status=product_stock_status(p),
    )


def serialize_supplier(db: Session, s: Supplier) -> SupplierOut:
    low_count = (
        db.query(Product)
        .filter(Product.supplier_id == s.id, Product.stock_qty <= Product.reorder_level)
        .count()
    )
    pending_po = (
        db.query(SupplierOrder)
        .filter(SupplierOrder.supplier_id == s.id, SupplierOrder.status == "pending_approval")
        .count()
    )
    return SupplierOut(
        id=s.id,
        code=s.code,
        name=s.name,
        name_kn=s.name_kn,
        contact_person=s.contact_person,
        phone=s.phone,
        whatsapp_number=s.whatsapp_number,
        category_focus=s.category_focus,
        low_stock_product_count=low_count,
        pending_po_count=pending_po,
    )


def serialize_order(db: Session, o: WhatsAppOrder) -> WhatsAppOrderOut:
    c = o.customer
    projected = round(c.current_balance + (o.total_amount if o.payment_intent == "credit" else 0.0), 2)
    credit_exceeded = o.payment_intent == "credit" and projected > c.credit_limit
    exceeds_by = round(max(0.0, projected - c.credit_limit), 2) if o.payment_intent == "credit" else 0.0

    approvals = (
        db.query(ApprovalRequest)
        .filter(
            (ApprovalRequest.entity_type == "whatsapp_order") & (ApprovalRequest.entity_id == o.id)
            | (ApprovalRequest.customer_id == o.customer_id) & (ApprovalRequest.status == "pending")
        )
        .order_by(ApprovalRequest.created_at.desc())
        .all()
    )
    related = [
        {
            "id": a.id,
            "approval_code": a.approval_code,
            "action_type": a.action_type,
            "title": a.title,
            "status": a.status,
            "payload": a.payload_json,
        }
        for a in approvals
        if a.entity_id == o.id or (a.payload_json or {}).get("order_id") == o.id
    ]

    return WhatsAppOrderOut(
        id=o.id,
        order_code=o.order_code,
        customer_id=o.customer_id,
        customer_name=c.name,
        customer_name_kn=c.name_kn,
        customer_phone=c.phone,
        customer_balance=c.current_balance,
        customer_credit_limit=c.credit_limit,
        projected_balance=projected,
        credit_exceeded=credit_exceeded,
        exceeds_by=exceeds_by,
        channel=o.channel,
        raw_message=o.raw_message,
        english_translation=o.english_translation,
        audio_duration_sec=o.audio_duration_sec,
        audio_transcript_kn=o.audio_transcript_kn,
        transcript_confidence=o.transcript_confidence,
        intent=o.intent,
        payment_intent=o.payment_intent,
        status=o.status,
        workflow_stage=o.workflow_stage,
        parsed_items=o.parsed_items_json or [],
        total_amount=o.total_amount,
        credit_check_status=o.credit_check_status,
        suggested_action=o.suggested_action,
        reason_text=o.reason_text,
        source_data=o.source_data_json or {},
        draft_reply_kn=o.draft_reply_kn,
        draft_reply_en=o.draft_reply_en,
        is_repeat_order=o.is_repeat_order,
        reference_order_id=o.reference_order_id,
        related_approvals=related,
        created_at=o.created_at,
    )


def serialize_approval(db: Session, a: ApprovalRequest) -> ApprovalOut:
    cust_name = None
    sup_name = None
    if a.customer_id:
        c = db.query(Customer).filter(Customer.id == a.customer_id).first()
        cust_name = c.name if c else None
    if a.supplier_id:
        s = db.query(Supplier).filter(Supplier.id == a.supplier_id).first()
        sup_name = s.name if s else None
    return ApprovalOut(
        id=a.id,
        approval_code=a.approval_code,
        action_type=a.action_type,
        title=a.title,
        title_kn=a.title_kn,
        entity_type=a.entity_type,
        entity_id=a.entity_id,
        customer_id=a.customer_id,
        customer_name=cust_name,
        supplier_id=a.supplier_id,
        supplier_name=sup_name,
        mcp_tool_name=a.mcp_tool_name,
        payload=a.payload_json or {},
        reason=a.reason,
        source_data=a.source_data_json or {},
        amount_impact=a.amount_impact,
        risk_level=a.risk_level,
        status=a.status,
        decision_note=a.decision_note,
        decided_by=a.decided_by,
        decided_at=a.decided_at,
        created_at=a.created_at,
    )


def serialize_payment_link(p: PaymentLink) -> PaymentLinkOut:
    return PaymentLinkOut(
        id=p.id,
        link_code=p.link_code,
        customer_id=p.customer_id,
        customer_name=p.customer.name if p.customer else "",
        short_url=p.short_url,
        upi_intent_uri=p.upi_intent_uri,
        amount_requested=p.amount_requested,
        amount_paid=p.amount_paid,
        remaining_amount=round(max(0.0, p.amount_requested - p.amount_paid), 2),
        status=p.status,
        reminder_stage=p.reminder_stage,
        created_at=p.created_at,
        paid_at=p.paid_at,
    )


def serialize_supplier_order(po: SupplierOrder) -> SupplierOrderOut:
    return SupplierOrderOut(
        id=po.id,
        po_code=po.po_code,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier.name if po.supplier else "",
        supplier_name_kn=po.supplier.name_kn if po.supplier else "",
        supplier_phone=po.supplier.phone if po.supplier else "",
        items=po.items_json or [],
        total_estimated_cost=po.total_estimated_cost,
        whatsapp_draft_kn=po.whatsapp_draft_kn,
        whatsapp_draft_en=po.whatsapp_draft_en,
        status=po.status,
        created_at=po.created_at,
        sent_at=po.sent_at,
    )


def serialize_bill(db: Session, b: SupplierBill) -> SupplierBillOut:
    req = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.entity_type == "supplier_bill", ApprovalRequest.entity_id == b.id)
        .order_by(ApprovalRequest.created_at.desc())
        .first()
    )
    return SupplierBillOut(
        id=b.id,
        bill_code=b.bill_code,
        supplier_id=b.supplier_id,
        supplier_name_extracted=b.supplier_name_extracted,
        invoice_number=b.invoice_number,
        bill_date=b.bill_date,
        image_filename=b.image_filename,
        extracted_items=b.extracted_items_json or [],
        total_amount=b.total_amount,
        ocr_confidence=b.ocr_confidence,
        status=b.status,
        approval_id=req.id if req else None,
        created_at=b.created_at,
    )


def serialize_audit_log(log: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=log.id,
        event_type=log.event_type,
        actor=log.actor,
        mcp_tool=log.mcp_tool,
        approval_id=log.approval_id,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        summary=log.summary,
        summary_kn=log.summary_kn,
        before_state=log.before_state_json,
        after_state=log.after_state_json,
        created_at=log.created_at,
    )


def serialize_daily_summary(s: DailySummary) -> DailySummaryOut:
    return DailySummaryOut(
        id=s.id,
        summary_date=s.summary_date,
        total_sales=s.total_sales,
        credit_sales=s.credit_sales,
        cash_upi_sales=s.cash_upi_sales,
        payments_collected=s.payments_collected,
        low_stock_count=s.low_stock_count,
        pending_approvals_count=s.pending_approvals_count,
        top_overdue=s.top_overdue_json or [],
        low_stock_items=s.low_stock_items_json or [],
        text_en=s.text_en,
        text_kn=s.text_kn,
        voice_script_kn=s.voice_script_kn,
        created_at=s.created_at,
    )
