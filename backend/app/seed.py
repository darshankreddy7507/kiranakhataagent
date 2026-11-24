"""Deterministic realistic seed data for Kirana Khata Agent."""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import (
    ApprovalRequest,
    AuditLog,
    Customer,
    KhataEntry,
    PaymentLink,
    Product,
    Supplier,
    SupplierOrder,
    WhatsAppMessage,
    WhatsAppOrder,
)
from app.services.approvals import create_approval_request, record_audit
from app.services.workflow import generate_daily_summary_workflow, ingest_incoming_order_workflow


def seed_database_if_empty(db: Session) -> None:
    """Populate database once with realistic kirana shop demo data."""
    if db.query(Product).count() > 0:
        return

    now = datetime.now(timezone.utc)

    # 1. Seed 3 Wholesale Suppliers
    sup_kaveri = Supplier(
        code="sup-kaveri",
        name="Kaveri Agro & Staples Wholesale",
        name_kn="ಕಾವೇರಿ ಅಗ್ರೋ ಮತ್ತು ಸ್ಟೇಪಲ್ಸ್ ಹೋಲ್‌ಸೇಲ್",
        contact_person="Shivakumar Hegde",
        phone="+91 98450 22114",
        whatsapp_number="+919845022114",
        category_focus="Rice, Atta, Sugar & Pulses",
    )
    sup_ganesh = Supplier(
        code="sup-ganesh",
        name="Nandini & Sri Ganesh Oil Depot",
        name_kn="ನಂದಿನಿ ಮತ್ತು ಶ್ರೀ ಗಣೇಶ್ ಆಯಿಲ್ ಡಿಪೋ",
        contact_person="Nagaraj Rao",
        phone="+91 98452 77810",
        whatsapp_number="+919845277810",
        category_focus="Cooking Oils, Ghee & Spices",
    )
    sup_fmcg = Supplier(
        code="sup-fmcg",
        name="Bengaluru FMCG Distributors",
        name_kn="ಬೆಂಗಳೂರು ಎಫ್‌ಎಂಸಿಜಿ ಡಿಸ್ಟ್ರಿಬ್ಯೂಟರ್ಸ್",
        contact_person="Prashanth Shetty",
        phone="+91 99001 44519",
        whatsapp_number="+919900144519",
        category_focus="Soaps, Tea, Coffee, Detergents",
    )
    db.add_all([sup_kaveri, sup_ganesh, sup_fmcg])
    db.flush()

    # 2. Seed 20 Grocery Products
    products_data = [
        ("SKU-RICE-SONA-1KG", "Sona Masoori Rice 1 kg", "ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ 1 ಕೆಜಿ", ["rice", "akki", "sona masoori", "ಅಕ್ಕಿ", "ಸೋನಾ ಮಸೂರಿ"], "Grains & Rice", "kg", 62.0, 52.0, 14.0, 20.0, 50.0, sup_kaveri.id, 6, None),
        ("SKU-SUGAR-1KG", "White Sugar (Sakkare) 1 kg", "ಬಿಳಿ ಸಕ್ಕರೆ 1 ಕೆಜಿ", ["sakkare", "sugar", "ಸಕ್ಕರೆ"], "Staples", "kg", 48.0, 41.0, 28.0, 15.0, 30.0, sup_kaveri.id, 4, None),
        ("SKU-OIL-1L", "Sunflower Oil 1 L Pouch", "ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ 1 ಲೀಟರ್", ["enne", "sunflower oil", "oil", "ಎಣ್ಣೆ", "ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ"], "Oils & Ghee", "litre", 154.0, 134.0, 9.0, 12.0, 24.0, sup_ganesh.id, 8, None),
        ("SKU-TOOR-DAL-1KG", "Toor Dal (Thogari Bele) 1 kg", "ತೊಗರಿ ಬೇಳೆ 1 ಕೆಜಿ", ["toor dal", "thogari bele", "dal", "bele", "ತೊಗರಿ ಬೇಳೆ", "ಬೇಳೆ"], "Pulses & Dals", "kg", 158.0, 138.0, 7.0, 10.0, 25.0, sup_kaveri.id, 9, None),
        ("SKU-ATTA-AASHIRVAAD-5KG", "Aashirvaad Atta 5 kg", "ಆಶೀರ್ವಾದ್ ಗೋಧಿ ಹಿಟ್ಟು 5 ಕೆಜಿ", ["aashirvaad", "aashirvaad atta", "atta", "godhi hittu", "ಆಶೀರ್ವಾದ್", "ಗೋಧಿ ಹಿಟ್ಟು"], "Atta & Flours", "bag", 295.0, 258.0, 0.0, 6.0, 12.0, sup_kaveri.id, 15, "atta_5kg"),
        ("SKU-ATTA-PILLSBURY-5KG", "Pillsbury Atta 5 kg", "ಪಿಲ್ಸ್‌ಬರಿ ಗೋಧಿ ಹಿಟ್ಟು 5 ಕೆಜಿ", ["pillsbury", "pillsbury atta", "atta"], "Atta & Flours", "bag", 275.0, 240.0, 11.0, 5.0, 10.0, sup_kaveri.id, 3, "atta_5kg"),
        ("SKU-ATTA-FORTUNE-5KG", "Fortune Atta 5 kg", "ಫಾರ್ಚೂನ್ ಗೋಧಿ ಹಿಟ್ಟು 5 ಕೆಜಿ", ["fortune", "fortune atta", "atta"], "Atta & Flours", "bag", 295.0, 255.0, 8.0, 5.0, 10.0, sup_kaveri.id, 5, "atta_5kg"),
        ("SKU-SALT-1KG", "Tata Salt 1 kg", "ಟಾಟಾ ಉಪ್ಪು 1 ಕೆಜಿ", ["salt", "uppu", "tata salt", "ಉಪ್ಪು"], "Staples", "kg", 28.0, 23.0, 32.0, 15.0, 30.0, sup_kaveri.id, 2, None),
        ("SKU-GHEE-500ML", "Nandini Pure Ghee 500 ml", "ನಂದಿನಿ ತುಪ್ಪ 500 ಮಿಲಿ", ["ghee", "tuppa", "nandini ghee", "ತುಪ್ಪ"], "Oils & Ghee", "jar", 330.0, 295.0, 4.0, 6.0, 10.0, sup_ganesh.id, 11, None),
        ("SKU-URAD-DAL-1KG", "Urad Dal (Uddina Bele) 1 kg", "ಉದ್ದಿನ ಬೇಳೆ 1 ಕೆಜಿ", ["urad dal", "uddina bele", "ಉದ್ದಿನ ಬೇಳೆ"], "Pulses & Dals", "kg", 165.0, 142.0, 18.0, 8.0, 20.0, sup_kaveri.id, 5, None),
        ("SKU-MOONG-DAL-1KG", "Moong Dal (Hesaru Bele) 1 kg", "ಹೆಸರು ಬೇಳೆ 1 ಕೆಜಿ", ["moong dal", "hesaru bele", "ಹೆಸರು ಬೇಳೆ"], "Pulses & Dals", "kg", 136.0, 118.0, 16.0, 8.0, 20.0, sup_kaveri.id, 6, None),
        ("SKU-BESAN-1KG", "Gram Flour (Kadale Hittu) 1 kg", "ಕಡಲೆ ಹಿಟ್ಟು 1 ಕೆಜಿ", ["besan", "kadale hittu", "ಕಡಲೆ ಹಿಟ್ಟು"], "Atta & Flours", "kg", 105.0, 88.0, 14.0, 8.0, 15.0, sup_kaveri.id, 4, None),
        ("SKU-MUSTARD-200G", "Mustard Seeds (Sasuve) 200 g", "ಸಾಸಿವೆ 200 ಗ್ರಾಂ", ["mustard", "sasuve", "ಸಾಸಿವೆ"], "Spices", "pack", 38.0, 32.0, 24.0, 10.0, 20.0, sup_ganesh.id, 7, None),
        ("SKU-JEERA-200G", "Cumin Seeds (Jeerige) 200 g", "ಜೀರಿಗೆ 200 ಗ್ರಾಂ", ["jeera", "jeerige", "ಜೀರಿಗೆ"], "Spices", "pack", 92.0, 76.0, 19.0, 8.0, 15.0, sup_ganesh.id, 7, None),
        ("SKU-RASAM-200G", "MTR Rasam Powder 200 g", "ಎಂಟಿಆರ್ ಸಾರು ಪುಡಿ 200 ಗ್ರಾಂ", ["rasam powder", "saaru pudi", "mtr"], "Spices", "pack", 118.0, 96.0, 15.0, 6.0, 12.0, sup_ganesh.id, 5, None),
        ("SKU-TEA-500G", "Red Label Tea 500 g", "ರೆಡ್ ಲೇಬಲ್ ಚಹಾ ಪುಡಿ 500 ಗ್ರಾಂ", ["tea", "chaha", "tea powder", "red label", "ಚಹಾ"], "Beverages", "pack", 255.0, 225.0, 12.0, 8.0, 15.0, sup_fmcg.id, 4, None),
        ("SKU-COFFEE-100G", "Bru Instant Coffee 100 g", "ಬ್ರೂ ಕಾಫಿ 100 ಗ್ರಾಂ", ["coffee", "bru", "ಕಾಫಿ"], "Beverages", "pack", 195.0, 168.0, 10.0, 6.0, 12.0, sup_fmcg.id, 4, None),
        ("SKU-SOAP-MYSORE", "Mysore Sandal Soap 150 g", "ಮೈಸೂರು ಸ್ಯಾಂಡಲ್ ಸೋಪು", ["soap", "mysore sandal", "sopu", "ಸೋಪು"], "Personal Care", "bar", 62.0, 52.0, 28.0, 12.0, 30.0, sup_fmcg.id, 3, None),
        ("SKU-DETERGENT-1KG", "Surf Excel Easy Wash 1 kg", "ಸರ್ಫ್ ಎಕ್ಸೆಲ್ 1 ಕೆಜಿ", ["surf", "detergent", "surf excel"], "Household", "pack", 142.0, 122.0, 13.0, 8.0, 15.0, sup_fmcg.id, 6, None),
        ("SKU-BISCUIT-PARLEG", "Parle-G Family Pack 800 g", "ಪಾರ್ಲೆ-ಜಿ ಬಿಸ್ಕತ್ 800 ಗ್ರಾಂ", ["parle", "biscuit", "parle-g"], "Snacks", "pack", 85.0, 72.0, 22.0, 10.0, 24.0, sup_fmcg.id, 2, None),
    ]

    prod_map: dict[str, Product] = {}
    for (
        sku, name, name_kn, aliases, cat, unit, price, cost, stock, reorder, def_reorder, sup_id, days_ago, sub_group
    ) in products_data:
        p = Product(
            sku=sku,
            name=name,
            name_kn=name_kn,
            aliases_json=aliases,
            category=cat,
            unit=unit,
            price=price,
            cost_price=cost,
            stock_qty=stock,
            reorder_level=reorder,
            default_reorder_qty=def_reorder,
            supplier_id=sup_id,
            last_restocked_at=now - timedelta(days=days_ago),
            substitute_group=sub_group,
        )
        db.add(p)
        prod_map[sku] = p
    db.flush()

    # 3. Seed 6 Customers (including over-limit, partial payment, long overdue, and current)
    ramesh = Customer(
        code="cust-ramesh",
        name="Ramesh Gowda",
        name_kn="ರಮೇಶ್ ಗೌಡ",
        phone="+91 98451 30112",
        whatsapp_number="+919845130112",
        address="3rd Cross, Jayanagar",
        credit_limit=3000.0,
        current_balance=3200.0,
        days_overdue=14,
        last_payment_date=now - timedelta(days=19),
        reminder_stage=1,
        preferred_language="kn",
    )
    suresh = Customer(
        code="cust-suresh",
        name="Suresh Shetty",
        name_kn="ಸುರೇಶ್ ಶೆಟ್ಟಿ",
        phone="+91 99002 61844",
        whatsapp_number="+919900261844",
        address="Near Bus Stand, JP Nagar",
        credit_limit=4000.0,
        current_balance=1850.0,
        days_overdue=19,
        last_payment_date=now - timedelta(days=4),
        reminder_stage=2,
        preferred_language="kn",
    )
    lakshmi = Customer(
        code="cust-lakshmi",
        name="Lakshmi Devi",
        name_kn="ಲಕ್ಷ್ಮೀ ದೇವಿ",
        phone="+91 98864 11209",
        whatsapp_number="+919886411209",
        address="Temple Road, Basavanagudi",
        credit_limit=2500.0,
        current_balance=640.0,
        days_overdue=0,
        last_payment_date=now - timedelta(days=6),
        reminder_stage=0,
        preferred_language="kn",
    )
    kumar = Customer(
        code="cust-kumar",
        name="Kumar Swamy",
        name_kn="ಕುಮಾರ್ ಸ್ವಾಮಿ",
        phone="+91 97411 89230",
        whatsapp_number="+919741189230",
        address="4th Block, Banashankari",
        credit_limit=3000.0,
        current_balance=1200.0,
        days_overdue=27,
        last_payment_date=now - timedelta(days=27),
        reminder_stage=3,
        preferred_language="kn",
    )
    geetha = Customer(
        code="cust-geetha",
        name="Geetha Hegde",
        name_kn="ಗೀತಾ ಹೆಗ್ಡೆ",
        phone="+91 98440 55901",
        whatsapp_number="+919844055901",
        address="1st Main, Vijayanagar",
        credit_limit=3500.0,
        current_balance=4150.0,
        days_overdue=42,
        last_payment_date=now - timedelta(days=42),
        reminder_stage=4,
        preferred_language="kn",
    )
    basavaraj = Customer(
        code="cust-basavaraj",
        name="Basavaraj Patil",
        name_kn="ಬಸವರಾಜ್ ಪಾಟೀಲ್",
        phone="+91 99805 71234",
        whatsapp_number="+919980571234",
        address="2nd Stage, Rajajinagar",
        credit_limit=3000.0,
        current_balance=920.0,
        days_overdue=7,
        last_payment_date=now - timedelta(hours=3),
        reminder_stage=1,
        preferred_language="kn",
    )
    db.add_all([ramesh, suresh, lakshmi, kumar, geetha, basavaraj])
    db.flush()

    # 4. Seed UPI Payment Links (active + partial payment example)
    plink_ramesh = PaymentLink(
        link_code="plink_mock_ramesh01",
        customer_id=ramesh.id,
        short_url="https://rzp.io/i/kka-ramesh",
        upi_intent_uri="upi://pay?pa=kiranakhata@okicici&pn=Kirana%20Khata%20Agent&am=3200.00&cu=INR",
        amount_requested=3200.0,
        amount_paid=0.0,
        status="sent",
        reminder_stage=1,
        created_at=now - timedelta(days=2),
    )
    plink_suresh_partial = PaymentLink(
        link_code="plink_mock_suresh01",
        customer_id=suresh.id,
        short_url="https://rzp.io/i/kka-suresh",
        upi_intent_uri="upi://pay?pa=kiranakhata@okicici&pn=Kirana%20Khata%20Agent&am=2850.00&cu=INR",
        amount_requested=2850.0,
        amount_paid=1000.0,
        status="partial",
        reminder_stage=2,
        created_at=now - timedelta(days=5),
        paid_at=now - timedelta(days=4),
    )
    plink_kumar = PaymentLink(
        link_code="plink_mock_kumar01",
        customer_id=kumar.id,
        short_url="https://rzp.io/i/kka-kumar",
        upi_intent_uri="upi://pay?pa=kiranakhata@okicici&pn=Kirana%20Khata%20Agent&am=1200.00&cu=INR",
        amount_requested=1200.0,
        amount_paid=0.0,
        status="sent",
        reminder_stage=3,
        created_at=now - timedelta(days=3),
    )
    plink_geetha = PaymentLink(
        link_code="plink_mock_geetha01",
        customer_id=geetha.id,
        short_url="https://rzp.io/i/kka-geetha",
        upi_intent_uri="upi://pay?pa=kiranakhata@okicici&pn=Kirana%20Khata%20Agent&am=4150.00&cu=INR",
        amount_requested=4150.0,
        amount_paid=0.0,
        status="sent",
        reminder_stage=4,
        created_at=now - timedelta(days=10),
    )
    plink_basavaraj = PaymentLink(
        link_code="plink_mock_basava01",
        customer_id=basavaraj.id,
        short_url="https://rzp.io/i/kka-basava",
        upi_intent_uri="upi://pay?pa=kiranakhata@okicici&pn=Kirana%20Khata%20Agent&am=920.00&cu=INR",
        amount_requested=920.0,
        amount_paid=0.0,
        status="sent",
        reminder_stage=1,
        created_at=now - timedelta(days=1),
    )
    db.add_all([plink_ramesh, plink_suresh_partial, plink_kumar, plink_geetha, plink_basavaraj])
    db.flush()

    # 5. Seed Historical Completed Orders (so Repeat Order & Today's KPIs are real!)
    lakshmi_last_week_items = [
        {
            "product_id": prod_map["SKU-TOOR-DAL-1KG"].id,
            "requested_name": "1 kg Toor Dal",
            "matched_product_name": prod_map["SKU-TOOR-DAL-1KG"].name,
            "matched_product_name_kn": prod_map["SKU-TOOR-DAL-1KG"].name_kn,
            "qty": 1.0,
            "unit": "kg",
            "unit_price": 158.0,
            "line_total": 158.0,
            "stock_qty": prod_map["SKU-TOOR-DAL-1KG"].stock_qty,
            "available": True,
            "substitute_options": [],
        },
        {
            "product_id": prod_map["SKU-SALT-1KG"].id,
            "requested_name": "1 kg Tata Salt",
            "matched_product_name": prod_map["SKU-SALT-1KG"].name,
            "matched_product_name_kn": prod_map["SKU-SALT-1KG"].name_kn,
            "qty": 1.0,
            "unit": "kg",
            "unit_price": 28.0,
            "line_total": 28.0,
            "stock_qty": prod_map["SKU-SALT-1KG"].stock_qty,
            "available": True,
            "substitute_options": [],
        },
        {
            "product_id": prod_map["SKU-SOAP-MYSORE"].id,
            "requested_name": "2 Mysore Sandal Soap",
            "matched_product_name": prod_map["SKU-SOAP-MYSORE"].name,
            "matched_product_name_kn": prod_map["SKU-SOAP-MYSORE"].name_kn,
            "qty": 2.0,
            "unit": "bar",
            "unit_price": 62.0,
            "line_total": 124.0,
            "stock_qty": prod_map["SKU-SOAP-MYSORE"].stock_qty,
            "available": True,
            "substitute_options": [],
        },
        {
            "product_id": prod_map["SKU-GHEE-500ML"].id,
            "requested_name": "500 ml Nandini Ghee",
            "matched_product_name": prod_map["SKU-GHEE-500ML"].name,
            "matched_product_name_kn": prod_map["SKU-GHEE-500ML"].name_kn,
            "qty": 1.0,
            "unit": "jar",
            "unit_price": 330.0,
            "line_total": 330.0,
            "stock_qty": prod_map["SKU-GHEE-500ML"].stock_qty,
            "available": True,
            "substitute_options": [],
        },
    ]
    lakshmi_prev_order = WhatsAppOrder(
        order_code="ORD-1028",
        customer_id=lakshmi.id,
        channel="whatsapp_text",
        raw_message="1 kg toor dal, 1 kg salt, 2 mysore sandal soap mattu 500 ml nandini ghee kodi. Khatege haaki.",
        english_translation="1 kg Toor Dal, 1 kg Tata Salt, 2 Mysore Sandal Soap, 500 ml Nandini Ghee (on credit/khata)",
        intent="order",
        payment_intent="credit",
        status="completed",
        workflow_stage="completed",
        parsed_items_json=lakshmi_last_week_items,
        total_amount=640.0,
        credit_check_status="ok",
        suggested_action="Completed last week",
        reason_text="Delivered & confirmed in Kannada",
        draft_reply_kn="ನಿಮ್ಮ ಆರ್ಡರ್ ₹640 ಖಾತೆಗೆ ಸೇರಿಸಲಾಗಿದೆ.",
        draft_reply_en="Your order for ₹640 was added to khata.",
        is_repeat_order=False,
        created_at=now - timedelta(days=7),
        updated_at=now - timedelta(days=7),
    )
    basava_today_order = WhatsAppOrder(
        order_code="ORD-1039",
        customer_id=basavaraj.id,
        channel="whatsapp_text",
        raw_message="2 pack Red Label tea mattu 1 pack Bru coffee kodi. UPI madtini.",
        english_translation="2 pack Red Label Tea 500 g and 1 pack Bru Instant Coffee 100 g (UPI)",
        intent="order",
        payment_intent="upi",
        status="completed",
        workflow_stage="completed",
        parsed_items_json=[
            {
                "product_id": prod_map["SKU-TEA-500G"].id,
                "requested_name": "2 Red Label Tea",
                "matched_product_name": prod_map["SKU-TEA-500G"].name,
                "matched_product_name_kn": prod_map["SKU-TEA-500G"].name_kn,
                "qty": 2.0,
                "unit": "pack",
                "unit_price": 255.0,
                "line_total": 510.0,
                "stock_qty": prod_map["SKU-TEA-500G"].stock_qty,
                "available": True,
                "substitute_options": [],
            },
            {
                "product_id": prod_map["SKU-COFFEE-100G"].id,
                "requested_name": "1 Bru Coffee",
                "matched_product_name": prod_map["SKU-COFFEE-100G"].name,
                "matched_product_name_kn": prod_map["SKU-COFFEE-100G"].name_kn,
                "qty": 1.0,
                "unit": "pack",
                "unit_price": 195.0,
                "line_total": 195.0,
                "stock_qty": prod_map["SKU-COFFEE-100G"].stock_qty,
                "available": True,
                "substitute_options": [],
            },
        ],
        total_amount=705.0,
        credit_check_status="ok",
        suggested_action="Completed via UPI today",
        reason_text="Stock verified and UPI received",
        draft_reply_kn="ನಿಮ್ಮ ಚಹಾ ಮತ್ತು ಕಾಫಿ ಆರ್ಡರ್ ₹705 ತಲುಪಿಸಲಾಗಿದೆ. ಧನ್ಯವಾದಗಳು.",
        draft_reply_en="Your tea & coffee order for ₹705 has been delivered. Thank you.",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2, minutes=45),
    )
    basava_today_credit = WhatsAppOrder(
        order_code="ORD-1040",
        customer_id=basavaraj.id,
        channel="whatsapp_text",
        raw_message="3 kg Sona Masoori rice mattu 2 kg sugar kodi. Khatege haaki.",
        english_translation="3 kg Sona Masoori Rice and 2 kg Sugar (on credit/khata)",
        intent="order",
        payment_intent="credit",
        status="completed",
        workflow_stage="completed",
        parsed_items_json=[],
        total_amount=282.0,
        credit_check_status="ok",
        suggested_action="Completed today",
        reason_text="Approved by owner earlier today",
        draft_reply_kn="ನಿಮ್ಮ ಆರ್ಡರ್ ₹282 ಖಾತೆಗೆ ಸೇರಿಸಲಾಗಿದೆ.",
        draft_reply_en="Your order for ₹282 was added to khata.",
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1, minutes=50),
    )
    db.add_all([lakshmi_prev_order, basava_today_order, basava_today_credit])
    db.flush()

    # 6. Seed Khata Ledger History (including today's credit/collection & Suresh partial payment)
    khata_entries = [
        KhataEntry(customer_id=ramesh.id, entry_type="credit_sale", amount=1800.0, balance_after=1800.0, description="Monthly staples & oil groceries", description_kn="ತಿಂಗಳ ದಿನಸಿ ಮತ್ತು ಎಣ್ಣೆ", created_at=now - timedelta(days=22)),
        KhataEntry(customer_id=ramesh.id, entry_type="credit_sale", amount=1400.0, balance_after=3200.0, description="Festival rice & pulses order", description_kn="ಹಬ್ಬದ ಅಕ್ಕಿ ಮತ್ತು ಬೇಳೆ ಆರ್ಡರ್", created_at=now - timedelta(days=14)),
        KhataEntry(customer_id=suresh.id, entry_type="credit_sale", amount=2850.0, balance_after=2850.0, description="Rice 25 kg & Sunflower Oil groceries", description_kn="ಅಕ್ಕಿ ಮತ್ತು ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ", created_at=now - timedelta(days=19)),
        KhataEntry(customer_id=suresh.id, entry_type="payment_upi", amount=-1000.0, balance_after=1850.0, payment_link_id=plink_suresh_partial.id, description="UPI Partial Payment matched (plink_mock_suresh01)", description_kn="UPI ಭಾಗಶಃ ಪಾವತಿ ₹1,000", created_at=now - timedelta(days=4)),
        KhataEntry(customer_id=lakshmi.id, entry_type="credit_sale", amount=640.0, balance_after=640.0, order_id=lakshmi_prev_order.id, description="Weekly staples order ORD-1028", description_kn="ವಾರದ ದಿನಸಿ ಆರ್ಡರ್ ORD-1028", created_at=now - timedelta(days=7)),
        KhataEntry(customer_id=kumar.id, entry_type="credit_sale", amount=1200.0, balance_after=1200.0, description="Atta, pulses & cooking staples", description_kn="ಗೋಧಿ ಹಿಟ್ಟು ಮತ್ತು ಬೇಳೆ", created_at=now - timedelta(days=27)),
        KhataEntry(customer_id=geetha.id, entry_type="credit_sale", amount=4150.0, balance_after=4150.0, description="Bulk monthly kitchen provisions", description_kn="ತಿಂಗಳ ಅಡುಗೆ ದಿನಸಿ", created_at=now - timedelta(days=42)),
        KhataEntry(customer_id=basavaraj.id, entry_type="credit_sale", amount=1138.0, balance_after=1138.0, description="Previous groceries balance", description_kn="ಹಿಂದಿನ ದಿನಸಿ ಬಾಕಿ", created_at=now - timedelta(days=7)),
        KhataEntry(customer_id=basavaraj.id, entry_type="payment_upi", amount=-500.0, balance_after=638.0, description="UPI Partial Payment received today", description_kn="ಇಂದು ಬಂದ UPI ಪಾವತಿ ₹500", created_at=now - timedelta(hours=3)),
        KhataEntry(customer_id=basavaraj.id, entry_type="credit_sale", amount=282.0, balance_after=920.0, order_id=basava_today_credit.id, description="WhatsApp Order ORD-1040 (Rice & Sugar)", description_kn="ವಾಟ್ಸಾಪ್ ಆರ್ಡರ್ ORD-1040", created_at=now - timedelta(hours=1, minutes=50)),
    ]
    db.add_all(khata_entries)
    db.flush()

    # 7. Seed the 4 Active Inbox Orders via our live parser/workflow
    ingest_incoming_order_workflow(
        db,
        customer_id=ramesh.id,
        channel="whatsapp_text",
        raw_message="Anna, 2 kg sakkare mattu 1 litre enne kodi. Khatege haaki.",
        payment_intent="credit",
    )
    ingest_incoming_order_workflow(
        db,
        customer_id=suresh.id,
        channel="whatsapp_voice",
        raw_message="ಅಣ್ಣ, 5 ಕೆಜಿ ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ ಮತ್ತು 2 ಲೀಟರ್ ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ ಕಳಿಸಿ. ಖಾತೆಗೆ ಹಾಕಿ.",
        payment_intent="credit",
    )
    ingest_incoming_order_workflow(
        db,
        customer_id=lakshmi.id,
        channel="whatsapp_text",
        raw_message="Same as last week",
        payment_intent="credit",
    )
    ingest_incoming_order_workflow(
        db,
        customer_id=kumar.id,
        channel="whatsapp_text",
        raw_message="Aashirvaad Atta 5 kg 1 bag mattu 1 kg Toor Dal kodi. Khatege haaki.",
        payment_intent="credit",
    )

    # 8. Seed 1 pending payment reminder approval for Kumar (Stage 3) & 1 supplier reorder draft for low stock
    msg_kumar_rem = WhatsAppMessage(
        message_code="MSG-REM-KUMAR",
        customer_id=kumar.id,
        direction="outbound",
        message_type="payment_reminder",
        body_kn=f"ನಮಸ್ಕಾರ ಕುಮಾರ್ ಸ್ವಾಮಿ ಅವರೆ. ನಿಮ್ಮ ಖಾತೆ ಬಾಕಿ ₹1,200 (27 ದಿನಗಳು) ಇನ್ನೂ ಪಾವತಿಯಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು ಈ UPI ಲಿಂಕ್ ಮೂಲಕ ಪಾವತಿ ಮಾಡಿ: {plink_kumar.short_url}",
        body_en=f"Stage 3 reminder: Kumar Swamy, ₹1,200 is 27 days overdue. Pay via {plink_kumar.short_url}.",
        payment_link_id=plink_kumar.id,
        status="pending_approval",
    )
    db.add(msg_kumar_rem)
    db.flush()

    create_approval_request(
        db,
        action_type="payment_reminder",
        title="Stage 3 · Firmer Request for Kumar Swamy (₹1,200)",
        title_kn="ಕುಮಾರ್ ಸ್ವಾಮಿ ಅವರಿಗೆ ಬಾಕಿ ನೆನಪು (₹1,200)",
        entity_type="whatsapp_message",
        entity_id=msg_kumar_rem.id,
        customer_id=kumar.id,
        mcp_tool_name="create_reminder_draft",
        payload={
            "message_id": msg_kumar_rem.id,
            "customer_id": kumar.id,
            "payment_link_id": plink_kumar.id,
            "short_url": plink_kumar.short_url,
            "stage": 3,
            "stage_label": "Stage 3 · Firmer Request",
            "body_kn": msg_kumar_rem.body_kn,
            "body_en": msg_kumar_rem.body_en,
        },
        reason="Kumar Swamy's ₹1,200 khata balance is 27 days overdue. Stage 3 reminder with UPI link ready.",
        source_data={"current_balance": 1200.0, "days_overdue": 27, "reminder_stage": 3, "upi_link": plink_kumar.short_url},
        amount_impact=1200.0,
        risk_level="attention",
    )

    # Seed 1 pending Supplier Reorder PO draft for Kaveri Agro low-stock staples
    po_items = [
        {
            "product_id": prod_map["SKU-ATTA-AASHIRVAAD-5KG"].id,
            "sku": "SKU-ATTA-AASHIRVAAD-5KG",
            "product_name": "Aashirvaad Atta 5 kg",
            "product_name_kn": "ಆಶೀರ್ವಾದ್ ಗೋಧಿ ಹಿಟ್ಟು 5 ಕೆಜಿ",
            "current_stock": 0.0,
            "reorder_level": 6.0,
            "suggested_qty": 12.0,
            "ordered_qty": 12.0,
            "unit": "bag",
            "unit_cost": 258.0,
            "line_cost": 3096.0,
        },
        {
            "product_id": prod_map["SKU-RICE-SONA-1KG"].id,
            "sku": "SKU-RICE-SONA-1KG",
            "product_name": "Sona Masoori Rice 1 kg",
            "product_name_kn": "ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ 1 ಕೆಜಿ",
            "current_stock": 14.0,
            "reorder_level": 20.0,
            "suggested_qty": 50.0,
            "ordered_qty": 50.0,
            "unit": "kg",
            "unit_cost": 52.0,
            "line_cost": 2600.0,
        },
    ]
    po_draft = SupplierOrder(
        po_code="PO-204",
        supplier_id=sup_kaveri.id,
        items_json=po_items,
        total_estimated_cost=5696.0,
        whatsapp_draft_kn=(
            "ನಮಸ್ಕಾರ ಶಿವಕುಮಾರ್ ಅವರೆ (ಕಾವೇರಿ ಅಗ್ರೋ).\n"
            "ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್‌ಗೆ ಇಂದು ಈ ಸ್ಟಾಕ್ ಕಳಿಸಿ:\n"
            "• ಆಶೀರ್ವಾದ್ ಗೋಧಿ ಹಿಟ್ಟು 5 ಕೆಜಿ: 12 bag\n"
            "• ಸೋನಾ ಮಸೂರಿ ಅಕ್ಕಿ 1 ಕೆಜಿ: 50 kg\n"
            "ದಯವಿಟ್ಟು ಬಿಲ್ ಜೊತೆ ಕಳಿಸಿ."
        ),
        whatsapp_draft_en="Namaskara Shivakumar (Kaveri Agro). Please supply 12 bags Aashirvaad Atta 5 kg and 50 kg Sona Masoori Rice.",
        status="pending_approval",
    )
    db.add(po_draft)
    db.flush()

    create_approval_request(
        db,
        action_type="supplier_reorder",
        title="Supplier reorder PO-204 -> Kaveri Agro & Staples Wholesale (₹5,696)",
        title_kn="ಕಾವೇರಿ ಅಗ್ರೋ ಸ್ಟಾಕ್ ಆರ್ಡರ್ PO-204 ಅನುಮೋದಿಸಿ",
        entity_type="supplier_order",
        entity_id=po_draft.id,
        supplier_id=sup_kaveri.id,
        mcp_tool_name="create_supplier_order",
        payload={
            "po_id": po_draft.id,
            "po_code": po_draft.po_code,
            "supplier_id": sup_kaveri.id,
            "items": po_items,
            "whatsapp_draft_kn": po_draft.whatsapp_draft_kn,
            "whatsapp_draft_en": po_draft.whatsapp_draft_en,
        },
        reason="Aashirvaad Atta 5 kg is out of stock (0/6) and Sona Masoori Rice is below reorder level (14/20 kg).",
        source_data={"supplier": sup_kaveri.name, "low_stock_skus": ["SKU-ATTA-AASHIRVAAD-5KG", "SKU-RICE-SONA-1KG"]},
        amount_impact=5696.0,
        risk_level="attention",
    )

    # Seed 1 historical approved action in audit log for immediate context
    record_audit(
        db,
        event_type="approved",
        actor="owner",
        mcp_tool="fulfill_order",
        entity_type="whatsapp_order",
        entity_id=basava_today_order.id,
        summary="Approved & sent Kannada confirmation for Basavaraj Patil order ORD-1039 (₹705 UPI)",
        summary_kn="ಬಸವರಾಜ್ ಪಾಟೀಲ್ ಆರ್ಡರ್ ORD-1039 (₹705 UPI) ಅನುಮೋದಿಸಿ ಕಳಿಸಲಾಗಿದೆ.",
        after_state={"status": "completed", "total_amount": 705.0},
    )

    db.commit()
    generate_daily_summary_workflow(db, persist=True)
