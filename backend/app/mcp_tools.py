"""Official Python MCP SDK tool layer for Kirana Khata Agent."""

from typing import Any
from mcp.server.mcpserver import MCPServer

from app.adapters import build_adapters
from app.database import SessionLocal
from app.models import (
    ApprovalRequest,
    Customer,
    PaymentLink,
    Product,
    WhatsAppMessage,
)
from app.services.approvals import (
    ApprovalRequiredError,
    create_approval_request,
    execute_create_khata_entry,
    execute_send_approved_whatsapp_message,
    execute_update_inventory,
)
from app.services.workflow import (
    create_payment_link_record,
    create_reminder_draft_workflow,
    create_supplier_reorder_draft_workflow,
    generate_daily_summary_workflow,
    ingest_supplier_bill_workflow,
    product_stock_status,
    simulate_payment_received_workflow,
)

mcp = MCPServer(
    "kirana-khata-agent",
    instructions=(
        "Kirana Khata Agent MCP Server. "
        "All write, khata, inventory, and WhatsApp send tools strictly enforce owner approval gating."
    ),
)


@mcp.tool()
def get_customer_balance(customer_id: int) -> dict[str, Any]:
    """Return a customer's current khata balance, credit limit, overdue days, and reminder stage."""
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"Customer #{customer_id} not found"}
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "name_kn": customer.name_kn,
            "current_balance": customer.current_balance,
            "credit_limit": customer.credit_limit,
            "days_overdue": customer.days_overdue,
            "reminder_stage": customer.reminder_stage,
            "over_limit": customer.current_balance > customer.credit_limit,
            "source_data": {"customer_code": customer.code, "table": "customers"},
        }


@mcp.tool()
def check_credit_limit(customer_id: int, proposed_amount: float) -> dict[str, Any]:
    """Check whether adding proposed_amount exceeds the customer's khata credit limit."""
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"Customer #{customer_id} not found"}
        projected = round(customer.current_balance + proposed_amount, 2)
        exceeds = projected > customer.credit_limit
        return {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "current_balance": customer.current_balance,
            "credit_limit": customer.credit_limit,
            "proposed_amount": proposed_amount,
            "projected_balance": projected,
            "exceeds_limit": exceeds,
            "exceeds_by": round(max(0.0, projected - customer.credit_limit), 2),
            "suggested_action": "Approve additional credit, ask for payment first, or cancel" if exceeds else "Proceed with order approval",
            "reason": (
                f"Projected balance ₹{projected:,.0f} exceeds ₹{customer.credit_limit:,.0f} limit."
                if exceeds
                else f"Projected balance ₹{projected:,.0f} is within ₹{customer.credit_limit:,.0f} limit."
            ),
            "source_data": {"customer_code": customer.code, "current_balance": customer.current_balance},
        }


@mcp.tool()
def get_inventory(product_id: int) -> dict[str, Any]:
    """Read current stock level, reorder threshold, price, and supplier for a product."""
    with SessionLocal() as db:
        prod = db.query(Product).filter(Product.id == product_id).first()
        if not prod:
            return {"error": f"Product #{product_id} not found"}
        return {
            "product_id": prod.id,
            "sku": prod.sku,
            "name": prod.name,
            "name_kn": prod.name_kn,
            "stock_qty": prod.stock_qty,
            "reorder_level": prod.reorder_level,
            "unit": prod.unit,
            "price": prod.price,
            "status": product_stock_status(prod),
            "supplier_id": prod.supplier_id,
            "source_data": {"sku": prod.sku, "table": "products"},
        }


@mcp.tool()
def update_inventory(
    product_id: int, quantity_change: float, approval_id: int | None = None
) -> dict[str, Any]:
    """Update product stock only when backed by an approved ApprovalRequest; otherwise stage an approval request."""
    with SessionLocal() as db:
        prod = db.query(Product).filter(Product.id == product_id).first()
        if not prod:
            return {"error": f"Product #{product_id} not found"}
        if not approval_id:
            req = create_approval_request(
                db,
                action_type="bill_stock_intake" if quantity_change > 0 else "order_fulfill",
                title=f"Update stock for {prod.name} ({quantity_change:+g} {prod.unit})",
                title_kn=f"{prod.name_kn} ಸ್ಟಾಕ್ ಬದಲಾವಣೆ ({quantity_change:+g})",
                entity_type="product",
                entity_id=prod.id,
                mcp_tool_name="update_inventory",
                payload={"product_id": prod.id, "quantity_change": quantity_change},
                reason="Direct inventory mutation requested via MCP tool; owner approval required.",
                source_data={"sku": prod.sku, "current_stock": prod.stock_qty},
                risk_level="attention",
            )
            db.commit()
            return {
                "status": "pending_approval",
                "approval_id": req.id,
                "approval_code": req.approval_code,
                "message": "Write action gated behind owner approval request.",
            }
        try:
            updated = execute_update_inventory(
                db,
                product_id=product_id,
                quantity_change=quantity_change,
                approval_id=approval_id,
                reason_note="Approved MCP update_inventory",
            )
            db.commit()
            return {"status": "updated", "product_id": updated.id, "stock_qty": updated.stock_qty}
        except ApprovalRequiredError as exc:
            return {"status": "blocked", "error": str(exc)}


@mcp.tool()
def create_khata_entry(
    customer_id: int, amount: float, order_id: int | None = None, approval_id: int | None = None
) -> dict[str, Any]:
    """Create a credit khata entry only after explicit owner approval; otherwise queue an ApprovalRequest."""
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"Customer #{customer_id} not found"}
        if not approval_id:
            req = create_approval_request(
                db,
                action_type="voice_khata_entry",
                title=f"Add ₹{amount:,.0f} khata entry for {customer.name}",
                title_kn=f"{customer.name_kn} ಖಾತೆಗೆ ₹{amount:,.0f} ಸೇರಿಸಿ",
                entity_type="customer",
                entity_id=customer.id,
                customer_id=customer.id,
                mcp_tool_name="create_khata_entry",
                payload={"customer_id": customer.id, "amount": amount, "order_id": order_id},
                reason="Khata credit entry requires owner approval before modifying ledger.",
                source_data={"customer_code": customer.code, "current_balance": customer.current_balance},
                amount_impact=amount,
                risk_level="high" if customer.current_balance + amount > customer.credit_limit else "normal",
            )
            db.commit()
            return {
                "status": "pending_approval",
                "approval_id": req.id,
                "approval_code": req.approval_code,
            }
        try:
            entry = execute_create_khata_entry(
                db,
                customer_id=customer_id,
                amount=amount,
                order_id=order_id,
                approval_id=approval_id,
                description=f"Approved khata entry ₹{amount:,.0f}",
            )
            db.commit()
            return {"status": "created", "entry_id": entry.id, "balance_after": entry.balance_after}
        except ApprovalRequiredError as exc:
            return {"status": "blocked", "error": str(exc)}


@mcp.tool()
def create_payment_link(customer_id: int, amount: float) -> dict[str, Any]:
    """Generate a mock/production Razorpay UPI payment link for a customer balance."""
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"Customer #{customer_id} not found"}
        link = create_payment_link_record(db, customer=customer, amount=amount, reminder_stage=max(1, customer.reminder_stage))
        db.commit()
        return {
            "payment_link_id": link.id,
            "link_code": link.link_code,
            "short_url": link.short_url,
            "upi_intent_uri": link.upi_intent_uri,
            "amount_requested": link.amount_requested,
            "status": link.status,
        }


@mcp.tool()
def record_payment(payment_link_id: int, amount: float) -> dict[str, Any]:
    """Match an incoming UPI payment to a payment link, update khata, and stage thank-you approval."""
    with SessionLocal() as db:
        res = simulate_payment_received_workflow(db, payment_link_id=payment_link_id, amount_paid=amount)
        return {
            "status": res["payment_link"].status,
            "customer": res["customer"].name,
            "amount_paid": res["amount_paid"],
            "old_balance": res["old_balance"],
            "new_balance": res["new_balance"],
            "thank_you_approval_code": res["thank_you_approval"].approval_code,
        }


@mcp.tool()
def get_overdue_customers() -> dict[str, Any]:
    """Return customers with outstanding overdue balances sorted by risk and amount."""
    with SessionLocal() as db:
        customers = (
            db.query(Customer)
            .filter(Customer.current_balance > 0, Customer.days_overdue > 0)
            .order_by(Customer.days_overdue.desc(), Customer.current_balance.desc())
            .all()
        )
        return {
            "count": len(customers),
            "customers": [
                {
                    "customer_id": c.id,
                    "name": c.name,
                    "name_kn": c.name_kn,
                    "current_balance": c.current_balance,
                    "credit_limit": c.credit_limit,
                    "days_overdue": c.days_overdue,
                    "reminder_stage": c.reminder_stage,
                }
                for c in customers
            ],
        }


@mcp.tool()
def create_reminder_draft(customer_id: int) -> dict[str, Any]:
    """Draft a stage-appropriate Kannada & English payment reminder gated behind owner approval."""
    with SessionLocal() as db:
        req = create_reminder_draft_workflow(db, customer_id=customer_id)
        return {
            "status": "pending_approval",
            "approval_id": req.id,
            "approval_code": req.approval_code,
            "payload": req.payload_json,
            "reason": req.reason,
        }


@mcp.tool()
def send_approved_whatsapp_message(message_id: int, approval_id: int | None = None) -> dict[str, Any]:
    """Send a drafted WhatsApp message ONLY if an approved ApprovalRequest authorizes it."""
    with SessionLocal() as db:
        if not approval_id:
            msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
            if not msg:
                return {"error": f"WhatsAppMessage #{message_id} not found"}
            if msg.approval_id:
                approval_id = msg.approval_id
        try:
            sent = execute_send_approved_whatsapp_message(db, message_id=message_id, approval_id=approval_id or 0)
            db.commit()
            return {
                "status": "sent",
                "message_id": sent.id,
                "provider_message_id": sent.provider_message_id,
            }
        except ApprovalRequiredError as exc:
            return {"status": "blocked", "error": str(exc)}


@mcp.tool()
def create_supplier_order(supplier_id: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a supplier reorder draft and gate sending behind owner approval."""
    with SessionLocal() as db:
        res = create_supplier_reorder_draft_workflow(
            db, supplier_id=supplier_id, custom_items=items
        )
        return {
            "status": "pending_approval",
            "po_code": res["supplier_order"].po_code,
            "approval_code": res["approval"].approval_code,
            "total_estimated_cost": res["supplier_order"].total_estimated_cost,
        }


@mcp.tool()
def generate_daily_summary() -> dict[str, Any]:
    """Generate the 9 PM daily operational summary in English, Kannada text, and Kannada voice script."""
    with SessionLocal() as db:
        summary = generate_daily_summary_workflow(db, persist=True)
        return {
            "summary_date": summary.summary_date,
            "total_sales": summary.total_sales,
            "credit_sales": summary.credit_sales,
            "payments_collected": summary.payments_collected,
            "low_stock_count": summary.low_stock_count,
            "pending_approvals_count": summary.pending_approvals_count,
            "text_en": summary.text_en,
            "text_kn": summary.text_kn,
            "voice_script_kn": summary.voice_script_kn,
        }


@mcp.tool()
def transcribe_kannada_voice(audio_file: str, hint_text: str | None = None) -> dict[str, Any]:
    """Transcribe a Kannada customer voice note or owner voice command via Kannada STT adapter."""
    adapters = build_adapters()
    res = adapters.kannada_stt.transcribe(None, audio_file, hint_text=hint_text)
    return {
        "transcript_kn": res.transcript_kn,
        "english_meaning": res.english_meaning,
        "confidence": res.confidence,
        "duration_sec": res.duration_sec,
        "mode": res.mode,
    }


@mcp.tool()
def extract_supplier_bill(image_file: str, scenario: str | None = None) -> dict[str, Any]:
    """Extract items from a supplier bill image and create an approval request before updating stock."""
    with SessionLocal() as db:
        res = ingest_supplier_bill_workflow(db, image_bytes=None, filename=image_file, scenario=scenario)
        return {
            "status": "pending_approval",
            "bill_code": res["bill"].bill_code,
            "invoice_number": res["bill"].invoice_number,
            "supplier_name": res["bill"].supplier_name_extracted,
            "total_amount": res["bill"].total_amount,
            "approval_code": res["approval"].approval_code,
        }


MCP_TOOL_CATALOG = [
    {"name": "get_customer_balance", "access": "read", "description": "Read customer khata balance, credit limit, and overdue age."},
    {"name": "check_credit_limit", "access": "read", "description": "Check whether a new order exceeds customer credit limit."},
    {"name": "get_inventory", "access": "read", "description": "Fetch SKU stock quantity, reorder level, and supplier."},
    {"name": "update_inventory", "access": "approval_gated", "description": "Adjust stock quantity only after an approved ApprovalRequest."},
    {"name": "create_khata_entry", "access": "approval_gated", "description": "Post customer credit ledger entry only after owner approval."},
    {"name": "create_payment_link", "access": "write_link", "description": "Generate Razorpay UPI payment link for customer collection."},
    {"name": "record_payment", "access": "webhook_match", "description": "Match UPI payment, reduce khata balance, queue Kannada thank-you approval."},
    {"name": "get_overdue_customers", "access": "read", "description": "List overdue customers ordered by risk and aging."},
    {"name": "create_reminder_draft", "access": "approval_gated", "description": "Draft gentle staged Kannada/English payment reminder for approval."},
    {"name": "send_approved_whatsapp_message", "access": "approval_gated", "description": "Send WhatsApp message only when authorized by an approved request."},
    {"name": "create_supplier_order", "access": "approval_gated", "description": "Draft low-stock supplier PO & WhatsApp message for owner approval."},
    {"name": "generate_daily_summary", "access": "read_write", "description": "Compute 9 PM daily sales, credit, collections, and Kannada voice summary."},
    {"name": "transcribe_kannada_voice", "access": "read", "description": "Transcribe Kannada customer voice note or owner voice command."},
    {"name": "extract_supplier_bill", "access": "approval_gated", "description": "OCR supplier bill image and stage stock intake approval."},
]


if __name__ == "__main__":
    mcp.run()
