"""Tests for order parsing, credit-limit checks, stock updates, approval gating, and payment matching."""

import pytest

from app.models import AuditLog, Customer, Product, WhatsAppMessage, WhatsAppOrder
from app.services.approvals import (
    ApprovalRequiredError,
    decide_approval_request,
    execute_create_khata_entry,
    execute_send_approved_whatsapp_message,
    execute_update_inventory,
)
from app.services.parser import parse_whatsapp_order_message


def test_order_parsing_kannada_sugar_and_oil(db_session):
    ramesh = db_session.query(Customer).filter(Customer.code == "cust-ramesh").first()
    parsed = parse_whatsapp_order_message(
        db_session,
        ramesh,
        "Anna, 2 kg sakkare mattu 1 litre enne kodi. Khatege haaki.",
    )
    assert parsed["payment_intent"] == "credit"
    names = [i["matched_product_name"] for i in parsed["parsed_items"]]
    assert "White Sugar (Sakkare) 1 kg" in names
    assert "Sunflower Oil 1 L Pouch" in names
    assert parsed["total_amount"] == 250.0  # (2 * 48) + (1 * 154)
    assert parsed["credit_check_status"] == "exceeds_limit"


def test_repeat_order_resolves_previous_items(db_session):
    lakshmi = db_session.query(Customer).filter(Customer.code == "cust-lakshmi").first()
    parsed = parse_whatsapp_order_message(db_session, lakshmi, "Same as last week")
    assert parsed["is_repeat_order"] is True
    assert len(parsed["parsed_items"]) == 4
    assert parsed["total_amount"] == 640.0
    assert parsed["status"] == "pending_approval"


def test_unavailable_product_suggests_smart_substitutes(db_session):
    kumar = db_session.query(Customer).filter(Customer.code == "cust-kumar").first()
    parsed = parse_whatsapp_order_message(
        db_session,
        kumar,
        "Aashirvaad Atta 5 kg 1 bag mattu 1 kg Toor Dal kodi",
    )
    assert parsed["status"] == "needs_substitute"
    atta_item = next(i for i in parsed["parsed_items"] if "Aashirvaad" in i["matched_product_name"])
    toor_item = next(i for i in parsed["parsed_items"] if "Toor Dal" in i["matched_product_name"])
    assert atta_item["qty"] == 1.0
    assert toor_item["qty"] == 1.0
    assert atta_item["available"] is False
    subs = atta_item["substitute_options"]
    assert len(subs) == 2
    assert subs[0]["name"] == "Pillsbury Atta 5 kg"
    assert subs[0]["comparison_label"] == "₹20 cheaper"
    assert subs[1]["name"] == "Fortune Atta 5 kg"
    assert subs[1]["comparison_label"] == "same price"


def test_approval_gating_blocks_direct_writes_and_sends(db_session):
    sugar = db_session.query(Product).filter(Product.sku == "SKU-SUGAR-1KG").first()
    ramesh = db_session.query(Customer).filter(Customer.code == "cust-ramesh").first()
    msg = db_session.query(WhatsAppMessage).first()

    with pytest.raises(ApprovalRequiredError):
        execute_update_inventory(
            db_session, product_id=sugar.id, quantity_change=-2, approval_id=0, reason_note="bypass"
        )
    with pytest.raises(ApprovalRequiredError):
        execute_create_khata_entry(
            db_session, customer_id=ramesh.id, amount=100.0, order_id=None, approval_id=0, description="bypass"
        )
    with pytest.raises(ApprovalRequiredError):
        execute_send_approved_whatsapp_message(db_session, message_id=msg.id, approval_id=0)


def test_order_two_step_approval_updates_stock_khata_and_audit_log(client, db_session):
    # Suresh voice order: 5 kg Sona Masoori Rice + 2 L Sunflower Oil
    suresh_order = (
        db_session.query(WhatsAppOrder)
        .join(Customer)
        .filter(Customer.code == "cust-suresh")
        .first()
    )
    rice_before = db_session.query(Product).filter(Product.sku == "SKU-RICE-SONA-1KG").first().stock_qty
    suresh_before = db_session.query(Customer).filter(Customer.code == "cust-suresh").first().current_balance

    # Step 1: Owner approves order -> updates inventory & khata, stages Kannada confirmation approval
    resp = client.post(
        f"/api/orders/{suresh_order.id}/decision",
        json={"decision": "approve", "note": "Verified stock"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["order"]["status"] == "confirmation_pending"
    follow_up = data["follow_up_approval"]
    assert follow_up is not None
    assert follow_up["action_type"] == "send_whatsapp"

    db_session.expire_all()
    rice_after = db_session.query(Product).filter(Product.sku == "SKU-RICE-SONA-1KG").first().stock_qty
    suresh_after = db_session.query(Customer).filter(Customer.code == "cust-suresh").first().current_balance
    assert rice_after == rice_before - 5.0
    assert suresh_after == suresh_before + suresh_order.total_amount

    # Step 2: Owner approves sending Kannada confirmation message
    send_resp = client.post(
        f"/api/approvals/{follow_up['id']}/decision",
        json={"decision": "approve"},
    )
    assert send_resp.status_code == 200

    db_session.expire_all()
    refreshed_order = db_session.query(WhatsAppOrder).filter(WhatsAppOrder.id == suresh_order.id).first()
    assert refreshed_order.status == "completed"
    audit_events = [a.event_type for a in db_session.query(AuditLog).all()]
    assert "inventory_updated" in audit_events
    assert "khata_created" in audit_events
    assert "whatsapp_sent" in audit_events


def test_credit_limit_ask_payment_first_creates_reminder(client, db_session):
    ramesh_order = (
        db_session.query(WhatsAppOrder)
        .join(Customer)
        .filter(Customer.code == "cust-ramesh")
        .first()
    )
    assert ramesh_order.credit_check_status == "exceeds_limit"

    resp = client.post(
        f"/api/orders/{ramesh_order.id}/decision",
        json={"decision": "ask_payment"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "payment_requested"
    assert data["follow_up_approval"]["action_type"] == "payment_reminder"


def test_partial_and_full_payment_matching(client, db_session):
    basava = db_session.query(Customer).filter(Customer.code == "cust-basavaraj").first()
    start_bal = basava.current_balance  # 920.0

    # Partial payment of ₹420
    res1 = client.post(
        "/api/khata/payments/simulate",
        json={"customer_id": basava.id, "amount_paid": 420.0},
    )
    assert res1.status_code == 200
    p1 = res1.json()
    assert p1["is_partial"] is True
    assert p1["old_balance"] == start_bal
    assert p1["new_balance"] == start_bal - 420.0
    assert p1["thank_you_approval"]["action_type"] == "payment_thank_you"

    # Remaining ₹500 full settlement
    res2 = client.post(
        "/api/khata/payments/simulate",
        json={"customer_id": basava.id, "amount_paid": 500.0},
    )
    assert res2.status_code == 200
    p2 = res2.json()
    assert p2["is_partial"] is False
    assert p2["new_balance"] == 0.0


def test_bill_ocr_and_voice_commands_and_mcp_catalog(client, db_session):
    # Bill OCR stages approval without mutating stock yet
    atta_before = db_session.query(Product).filter(Product.sku == "SKU-ATTA-AASHIRVAAD-5KG").first().stock_qty
    bill_resp = client.post("/api/inventory/bills/upload", data={"scenario": "kaveri_staples"})
    assert bill_resp.status_code == 200
    bill_data = bill_resp.json()
    assert bill_data["approval"]["status"] == "pending"

    db_session.expire_all()
    assert db_session.query(Product).filter(Product.sku == "SKU-ATTA-AASHIRVAAD-5KG").first().stock_qty == atta_before

    # Approving bill updates inventory
    approve_bill = client.post(
        f"/api/approvals/{bill_data['approval']['id']}/decision",
        json={"decision": "approve"},
    )
    assert approve_bill.status_code == 200
    db_session.expire_all()
    assert db_session.query(Product).filter(Product.sku == "SKU-ATTA-AASHIRVAAD-5KG").first().stock_qty == atta_before + 12.0

    # Voice command checks & MCP catalog
    v1 = client.post("/api/voice/command", json={"command_text": "Sakkare stock eshtu ide?"})
    assert v1.status_code == 200
    assert v1.json()["mcp_tool_used"] == "get_inventory"

    v2 = client.post("/api/voice/command", json={"command_text": "Ramesh ge 500 khatege haki."})
    assert v2.status_code == 200
    assert v2.json()["created_approval"]["action_type"] == "voice_khata_entry"

    tools_resp = client.get("/api/mcp/tools")
    assert tools_resp.status_code == 200
    assert len(tools_resp.json()["tools"]) == 14


def test_owner_add_inventory_and_new_product(client, db_session):
    atta = db_session.query(Product).filter(Product.sku == "SKU-ATTA-AASHIRVAAD-5KG").first()
    assert atta.stock_qty == 0.0

    add_resp = client.post(
        "/api/inventory/add-stock",
        json={"product_id": atta.id, "quantity_added": 10.0, "note": "Morning market delivery"},
    )
    assert add_resp.status_code == 200
    assert add_resp.json()["stock_qty"] == 10.0
    assert add_resp.json()["stock_status"] == "in_stock"

    new_prod_resp = client.post(
        "/api/inventory/products",
        json={
            "name": "Ragi Flour 1 kg",
            "name_kn": "ರಾಗಿ ಹಿಟ್ಟು 1 ಕೆಜಿ",
            "category": "Atta & Flours",
            "unit": "kg",
            "price": 56.0,
            "stock_qty": 25.0,
            "reorder_level": 8.0,
            "supplier_id": atta.supplier_id,
        },
    )
    assert new_prod_resp.status_code == 200
    assert new_prod_resp.json()["name"] == "Ragi Flour 1 kg"
    assert new_prod_resp.json()["stock_qty"] == 25.0


def test_realtime_whatsapp_and_razorpay_webhooks(client, db_session):
    # Incoming WhatsApp webhook matched by customer phone number
    wa_resp = client.post(
        "/api/webhooks/whatsapp",
        json={
            "phone": "+919886411209",  # Lakshmi Devi
            "message": "Anna, 2 kg sakkare mattu 1 kg toor dal kodi. Khatege haaki.",
        },
    )
    assert wa_resp.status_code == 200
    wa_data = wa_resp.json()
    assert wa_data["received"] is True
    order = wa_data["order"]
    assert order["customer_name"] == "Lakshmi Devi"
    assert order["total_amount"] == 254.0  # (2 * 48) + (1 * 158)
    assert order["status"] == "pending_approval"

    # Incoming Razorpay webhook matching an active payment link
    rzp_resp = client.post(
        "/api/webhooks/razorpay",
        json={"payment_link_code": "plink_mock_basava01", "amount_inr": 400.0},
    )
    assert rzp_resp.status_code == 200
    rzp_data = rzp_resp.json()
    assert rzp_data["matched"] is True
    assert rzp_data["customer"] == "Basavaraj Patil"
    assert rzp_data["new_balance"] == 520.0

    # Meta WhatsApp Cloud API payload from a brand-new phone number auto-registers customer
    meta_resp = client.post(
        "/api/webhooks/whatsapp",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Darshan"}}],
                                "messages": [
                                    {
                                        "from": "919988776655",
                                        "type": "text",
                                        "text": {"body": "2 kg sakkare kodi"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )
    assert meta_resp.status_code == 200
    assert meta_resp.json()["order"]["customer_name"] == "Darshan"
    assert meta_resp.json()["order"]["total_amount"] == 96.0

    # Twilio WhatsApp Sandbox form-encoded webhook
    twilio_resp = client.post(
        "/api/webhooks/whatsapp",
        data={
            "From": "whatsapp:+919112233445",
            "ProfileName": "Kiran",
            "Body": "1 litre enne kodi. UPI",
        },
    )
    assert twilio_resp.status_code == 200
    assert twilio_resp.json()["order"]["customer_name"] == "Kiran"
    assert twilio_resp.json()["order"]["total_amount"] == 154.0


def test_telegram_webhook_and_reply_routing(client, db_session):
    tg_resp = client.post(
        "/api/webhooks/telegram",
        json={
            "update_id": 1001,
            "message": {
                "message_id": 12,
                "chat": {"id": 987654321, "type": "private"},
                "from": {"id": 987654321, "first_name": "Arun", "last_name": "Gowda", "username": "arung"},
                "text": "Anna, 2 kg sakkare mattu 1 litre enne kodi. Khatege haaki.",
            },
        },
    )
    assert tg_resp.status_code == 200
    tg_data = tg_resp.json()
    assert tg_data["handled"] is True
    assert tg_data["customer_name"] == "Arun Gowda"
    assert tg_data["total_amount"] == 250.0

    # Approve order & send confirmation -> verifies routing works cleanly for tg: customer
    order_id = tg_data["order_id"]
    dec1 = client.post(f"/api/orders/{order_id}/decision", json={"decision": "approve"})
    assert dec1.status_code == 200
    follow_id = dec1.json()["follow_up_approval"]["id"]
    dec2 = client.post(f"/api/approvals/{follow_id}/decision", json={"decision": "approve"})
    assert dec2.status_code == 200


def test_store_settings_auth_and_one_click_order_reply(client, db_session):
    # Read & update store name and owner name
    s_get = client.get("/api/settings")
    assert s_get.status_code == 200
    assert s_get.json()["shop_name"] == "Kirana Khata Agent"

    s_put = client.put(
        "/api/settings",
        json={
            "shop_name": "Namma Bengaluru Kirana",
            "shop_name_kn": "ನಮ್ಮ ಬೆಂಗಳೂರು ಕಿರಾಣಾ",
            "owner_name": "Raghavendra Rao",
            "upi_id": "nammakirana@okicici",
        },
    )
    assert s_put.status_code == 200
    assert s_put.json()["shop_name"] == "Namma Bengaluru Kirana"
    assert s_put.json()["owner_name"] == "Raghavendra Rao"

    # Auth login/logout checks
    bad_login = client.post("/api/auth/login", json={"pin": "9999"})
    assert bad_login.status_code == 401
    good_login = client.post("/api/auth/login", json={"pin": "1234"})
    assert good_login.status_code == 200
    assert good_login.json()["authenticated"] is True
    assert client.post("/api/auth/logout").status_code == 200

    # 1-click Confirm & Send Reply on Lakshmi's repeat order
    lakshmi_order = (
        db_session.query(WhatsAppOrder)
        .join(Customer)
        .filter(Customer.code == "cust-lakshmi", WhatsAppOrder.status == "pending_approval")
        .first()
    )
    one_click = client.post(
        f"/api/orders/{lakshmi_order.id}/decision",
        json={"decision": "approve", "auto_send_reply": True},
    )
    assert one_click.status_code == 200
    assert one_click.json()["result"] == "completed"
    assert one_click.json()["order"]["status"] == "completed"
