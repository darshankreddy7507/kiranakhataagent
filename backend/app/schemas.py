"""Pydantic schemas for typed API contracts."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class SupplierOut(BaseModel):
    id: int
    code: str
    name: str
    name_kn: str
    contact_person: str
    phone: str
    whatsapp_number: str
    category_focus: str
    low_stock_product_count: int = 0
    pending_po_count: int = 0


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    name_kn: str
    category: str
    unit: str
    price: float
    cost_price: float
    stock_qty: float
    reorder_level: float
    default_reorder_qty: float
    supplier_id: int
    supplier_name: str
    last_restocked_at: datetime
    substitute_group: str | None = None
    stock_status: str  # in_stock | low_stock | out_of_stock


class CustomerOut(BaseModel):
    id: int
    code: str
    name: str
    name_kn: str
    phone: str
    whatsapp_number: str
    address: str
    credit_limit: float
    current_balance: float
    days_overdue: int
    last_payment_date: datetime | None
    reminder_stage: int
    reminder_stage_label: str
    preferred_language: str
    over_limit: bool
    utilization_pct: float


class KhataEntryOut(BaseModel):
    id: int
    customer_id: int
    entry_type: str
    amount: float
    balance_after: float
    order_id: int | None
    payment_link_id: int | None
    description: str
    description_kn: str
    approved_by_id: int | None
    created_at: datetime


class PaymentLinkOut(BaseModel):
    id: int
    link_code: str
    customer_id: int
    customer_name: str
    short_url: str
    upi_intent_uri: str
    amount_requested: float
    amount_paid: float
    remaining_amount: float
    status: str
    reminder_stage: int
    created_at: datetime
    paid_at: datetime | None


class CustomerDetailOut(BaseModel):
    customer: CustomerOut
    entries: list[KhataEntryOut]
    payment_links: list[PaymentLinkOut]
    recent_orders: list[dict[str, Any]]


class SubstituteOptionOut(BaseModel):
    product_id: int
    sku: str
    name: str
    name_kn: str
    price: float
    stock_qty: float
    price_diff: float
    comparison_label: str


class ParsedOrderItemOut(BaseModel):
    product_id: int | None
    requested_name: str
    matched_product_name: str | None
    matched_product_name_kn: str | None
    qty: float
    unit: str
    unit_price: float
    line_total: float
    stock_qty: float
    available: bool
    substitute_options: list[SubstituteOptionOut] = []
    selected_substitute_id: int | None = None


class WhatsAppOrderOut(BaseModel):
    id: int
    order_code: str
    customer_id: int
    customer_name: str
    customer_name_kn: str
    customer_phone: str
    customer_balance: float
    customer_credit_limit: float
    projected_balance: float
    credit_exceeded: bool
    exceeds_by: float
    channel: str
    raw_message: str
    english_translation: str
    audio_duration_sec: int | None
    audio_transcript_kn: str | None
    transcript_confidence: float | None
    intent: str
    payment_intent: str
    status: str
    workflow_stage: str
    parsed_items: list[ParsedOrderItemOut]
    total_amount: float
    credit_check_status: str
    suggested_action: str
    reason_text: str
    source_data: dict[str, Any]
    draft_reply_kn: str
    draft_reply_en: str
    is_repeat_order: bool
    reference_order_id: int | None
    related_approvals: list[dict[str, Any]] = []
    created_at: datetime


class IncomingOrderCreate(BaseModel):
    customer_id: int
    channel: str = Field(default="whatsapp_text", pattern="^(whatsapp_text|whatsapp_voice)$")
    raw_message: str = Field(..., min_length=2, max_length=1000)
    payment_intent: str | None = Field(default=None, pattern="^(credit|cash|upi)$")


class SubstituteSelectRequest(BaseModel):
    original_product_id: int
    substitute_product_id: int
    draft_reply_kn: str | None = None


class OrderDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|ask_payment|cancel)$")
    edited_items: list[dict[str, Any]] | None = None
    draft_reply_kn: str | None = None
    draft_reply_en: str | None = None
    note: str | None = None
    auto_send_reply: bool = False


class ReminderDraftRequest(BaseModel):
    customer_id: int
    custom_message_kn: str | None = None
    custom_message_en: str | None = None


class SimulatePaymentRequest(BaseModel):
    payment_link_id: int | None = None
    customer_id: int | None = None
    amount_paid: float = Field(..., gt=0)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    edited_payload: dict[str, Any] | None = None
    decision_note: str | None = None


class ApprovalOut(BaseModel):
    id: int
    approval_code: str
    action_type: str
    title: str
    title_kn: str
    entity_type: str
    entity_id: int
    customer_id: int | None
    customer_name: str | None = None
    supplier_id: int | None
    supplier_name: str | None = None
    mcp_tool_name: str
    payload: dict[str, Any]
    reason: str
    source_data: dict[str, Any]
    amount_impact: float | None
    risk_level: str
    status: str
    decision_note: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime


class AuditLogOut(BaseModel):
    id: int
    event_type: str
    actor: str
    mcp_tool: str | None
    approval_id: int | None
    entity_type: str
    entity_id: int | None
    summary: str
    summary_kn: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    created_at: datetime


class SupplierOrderDraftCreate(BaseModel):
    supplier_id: int | None = None
    product_ids: list[int] | None = None
    items: list[dict[str, Any]] | None = None
    whatsapp_draft_kn: str | None = None


class SupplierOrderOut(BaseModel):
    id: int
    po_code: str
    supplier_id: int
    supplier_name: str
    supplier_name_kn: str
    supplier_phone: str
    items: list[dict[str, Any]]
    total_estimated_cost: float
    whatsapp_draft_kn: str
    whatsapp_draft_en: str
    status: str
    created_at: datetime
    sent_at: datetime | None


class SupplierBillOut(BaseModel):
    id: int
    bill_code: str
    supplier_id: int | None
    supplier_name_extracted: str
    invoice_number: str
    bill_date: str
    image_filename: str
    extracted_items: list[dict[str, Any]]
    total_amount: float
    ocr_confidence: float
    status: str
    approval_id: int | None = None
    created_at: datetime


class VoiceCommandRequest(BaseModel):
    command_text: str = Field(..., min_length=2, max_length=500)
    is_simulated_voice: bool = True


class AddStockRequest(BaseModel):
    product_id: int
    quantity_added: float = Field(..., gt=0)
    note: str | None = Field(default=None, max_length=240)
    new_price: float | None = Field(default=None, gt=0)


class CreateProductRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=140)
    name_kn: str | None = Field(default=None, max_length=160)
    category: str = Field(default="Staples", max_length=64)
    unit: str = Field(default="kg", max_length=32)
    price: float = Field(..., gt=0)
    cost_price: float | None = Field(default=None, gt=0)
    stock_qty: float = Field(default=0.0, ge=0)
    reorder_level: float = Field(default=5.0, ge=0)
    supplier_id: int


class ShopSettingsOut(BaseModel):
    shop_name: str
    shop_name_kn: str
    owner_name: str
    owner_phone: str
    upi_id: str
    default_credit_limit: float
    telegram_connected: bool = False


class ShopSettingsUpdate(BaseModel):
    shop_name: str = Field(..., min_length=2, max_length=160)
    shop_name_kn: str | None = Field(default=None, max_length=180)
    owner_name: str = Field(..., min_length=2, max_length=120)
    owner_phone: str | None = Field(default=None, max_length=24)
    upi_id: str | None = Field(default=None, max_length=100)
    default_credit_limit: float | None = Field(default=None, gt=0)
    owner_pin: str | None = Field(default=None, min_length=4, max_length=16)


class LoginRequest(BaseModel):
    pin: str = Field(default="1234", min_length=1, max_length=16)
    owner_name: str | None = None


class VoiceCommandResponse(BaseModel):
    transcript: str
    english_meaning: str
    intent: str
    summary_en: str
    summary_kn: str
    result_data: dict[str, Any]
    created_approval: ApprovalOut | None = None
    mcp_tool_used: str
    source_data: dict[str, Any]


class DailySummaryOut(BaseModel):
    id: int
    summary_date: str
    total_sales: float
    credit_sales: float
    cash_upi_sales: float
    payments_collected: float
    low_stock_count: int
    pending_approvals_count: int
    top_overdue: list[dict[str, Any]]
    low_stock_items: list[dict[str, Any]]
    text_en: str
    text_kn: str
    voice_script_kn: str
    created_at: datetime
