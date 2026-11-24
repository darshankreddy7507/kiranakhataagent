"""SQLAlchemy ORM models for Kirana Khata Agent."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140))
    name_kn: Mapped[str] = mapped_column(String(160))
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(24))
    whatsapp_number: Mapped[str] = mapped_column(String(24))
    category_focus: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")
    supplier_orders: Mapped[list["SupplierOrder"]] = relationship(back_populates="supplier")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    name_kn: Mapped[str] = mapped_column(String(160))
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(64), index=True)
    unit: Mapped[str] = mapped_column(String(32))
    price: Mapped[float] = mapped_column(Float)
    cost_price: Mapped[float] = mapped_column(Float)
    stock_qty: Mapped[float] = mapped_column(Float)
    reorder_level: Mapped[float] = mapped_column(Float)
    default_reorder_qty: Mapped[float] = mapped_column(Float)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    last_restocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    substitute_group: Mapped[str | None] = mapped_column(String(64), nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="products")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    name_kn: Mapped[str] = mapped_column(String(140))
    phone: Mapped[str] = mapped_column(String(24))
    whatsapp_number: Mapped[str] = mapped_column(String(24))
    address: Mapped[str] = mapped_column(String(200))
    credit_limit: Mapped[float] = mapped_column(Float, default=3000.0)
    current_balance: Mapped[float] = mapped_column(Float, default=0.0)
    days_overdue: Mapped[int] = mapped_column(Integer, default=0)
    last_payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_stage: Mapped[int] = mapped_column(Integer, default=0)
    preferred_language: Mapped[str] = mapped_column(String(8), default="kn")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    orders: Mapped[list["WhatsAppOrder"]] = relationship(back_populates="customer")
    khata_entries: Mapped[list["KhataEntry"]] = relationship(back_populates="customer")
    payment_links: Mapped[list["PaymentLink"]] = relationship(back_populates="customer")


class WhatsAppOrder(Base):
    __tablename__ = "whatsapp_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="whatsapp_text")
    raw_message: Mapped[str] = mapped_column(Text)
    english_translation: Mapped[str] = mapped_column(Text)
    audio_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_transcript_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent: Mapped[str] = mapped_column(String(32), default="order")
    payment_intent: Mapped[str] = mapped_column(String(24), default="credit")
    status: Mapped[str] = mapped_column(String(32), default="pending_approval", index=True)
    workflow_stage: Mapped[str] = mapped_column(String(48), default="awaiting_owner_approval")
    parsed_items_json: Mapped[list] = mapped_column(JSON, default=list)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    credit_check_status: Mapped[str] = mapped_column(String(32), default="ok")
    suggested_action: Mapped[str] = mapped_column(String(160), default="")
    reason_text: Mapped[str] = mapped_column(Text, default="")
    source_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_reply_kn: Mapped[str] = mapped_column(Text, default="")
    draft_reply_en: Mapped[str] = mapped_column(Text, default="")
    is_repeat_order: Mapped[bool] = mapped_column(Boolean, default=False)
    reference_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    link_code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    short_url: Mapped[str] = mapped_column(String(200))
    upi_intent_uri: Mapped[str] = mapped_column(String(300))
    amount_requested: Mapped[float] = mapped_column(Float)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(24), default="sent", index=True)
    reminder_stage: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="payment_links")


class KhataEntry(Base):
    __tablename__ = "khata_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    entry_type: Mapped[str] = mapped_column(String(32))  # credit_sale | payment_upi | payment_cash
    amount: Mapped[float] = mapped_column(Float)  # positive adds debt, negative reduces debt
    balance_after: Mapped[float] = mapped_column(Float)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("whatsapp_orders.id"), nullable=True)
    payment_link_id: Mapped[int | None] = mapped_column(ForeignKey("payment_links.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    description_kn: Mapped[str] = mapped_column(String(255), default="")
    approved_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="khata_entries")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), default="outbound")
    message_type: Mapped[str] = mapped_column(String(40))
    body_kn: Mapped[str] = mapped_column(Text)
    body_en: Mapped[str] = mapped_column(Text)
    payment_link_id: Mapped[int | None] = mapped_column(ForeignKey("payment_links.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupplierOrder(Base):
    __tablename__ = "supplier_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    po_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    items_json: Mapped[list] = mapped_column(JSON, default=list)
    total_estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    whatsapp_draft_kn: Mapped[str] = mapped_column(Text, default="")
    whatsapp_draft_en: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_orders")


class SupplierBill(Base):
    __tablename__ = "supplier_bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bill_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    supplier_name_extracted: Mapped[str] = mapped_column(String(140))
    invoice_number: Mapped[str] = mapped_column(String(64))
    bill_date: Mapped[str] = mapped_column(String(32))
    image_filename: Mapped[str] = mapped_column(String(200))
    extracted_items_json: Mapped[list] = mapped_column(JSON, default=list)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0.94)
    status: Mapped[str] = mapped_column(String(24), default="pending_approval", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    approval_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(180))
    title_kn: Mapped[str] = mapped_column(String(200), default="")
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    mcp_tool_name: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    source_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    amount_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(48))
    mcp_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    summary_kn: Mapped[str] = mapped_column(Text, default="")
    before_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    summary_date: Mapped[str] = mapped_column(String(24), index=True)
    total_sales: Mapped[float] = mapped_column(Float, default=0.0)
    credit_sales: Mapped[float] = mapped_column(Float, default=0.0)
    cash_upi_sales: Mapped[float] = mapped_column(Float, default=0.0)
    payments_collected: Mapped[float] = mapped_column(Float, default=0.0)
    low_stock_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_approvals_count: Mapped[int] = mapped_column(Integer, default=0)
    top_overdue_json: Mapped[list] = mapped_column(JSON, default=list)
    low_stock_items_json: Mapped[list] = mapped_column(JSON, default=list)
    text_en: Mapped[str] = mapped_column(Text)
    text_kn: Mapped[str] = mapped_column(Text)
    voice_script_kn: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shop_name: Mapped[str] = mapped_column(String(160), default="Sri Lakshmi Kirana Stores")
    shop_name_kn: Mapped[str] = mapped_column(String(180), default="ಶ್ರೀ ಲಕ್ಷ್ಮೀ ಕಿರಾಣಾ ಸ್ಟೋರ್ಸ್")
    owner_name: Mapped[str] = mapped_column(String(120), default="Manjunath Gowda")
    owner_phone: Mapped[str] = mapped_column(String(24), default="+91 98450 11223")
    upi_id: Mapped[str] = mapped_column(String(100), default="srilakshmikirana@okicici")
    default_credit_limit: Mapped[float] = mapped_column(Float, default=3000.0)
    owner_pin: Mapped[str] = mapped_column(String(16), default="1234")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
