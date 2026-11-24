"""Kannada, Tanglish, and English parser for WhatsApp orders and owner voice commands."""

import re
from typing import Any
from sqlalchemy.orm import Session

from app.models import Customer, Product, WhatsAppOrder


REPEAT_PHRASES = (
    "same as last week",
    "last week",
    "kaleda vaaradanthe",
    "ಕಳೆದ ವಾರದಂತೆಯೇ",
    "ಕಳೆದ ವಾರ",
    "munche order",
)

CREDIT_PHRASES = (
    "khatege",
    "khate",
    "khata",
    "baki",
    "credit",
    "ಖಾತೆಗೆ",
    "ಖಾತೆ",
    "ಬಾಕಿ",
)

CASH_PHRASES = (
    "cash",
    "upi",
    "gpay",
    "phonepe",
    "ನಗದು",
)


def detect_payment_intent(text: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    lower = text.lower()
    if any(p in lower or p in text for p in CREDIT_PHRASES):
        return "credit"
    if any(p in lower or p in text for p in CASH_PHRASES):
        return "upi" if "upi" in lower or "gpay" in lower or "phonepe" in lower else "cash"
    return "credit"


def is_repeat_order_text(text: str) -> bool:
    lower = text.lower()
    return any(p in lower or p in text for p in REPEAT_PHRASES)


def _substitute_options_for(db: Session, product: Product) -> list[dict[str, Any]]:
    if not product.substitute_group:
        return []
    candidates = (
        db.query(Product)
        .filter(
            Product.substitute_group == product.substitute_group,
            Product.id != product.id,
            Product.stock_qty > 0,
        )
        .order_by(Product.price.asc())
        .all()
    )
    options: list[dict[str, Any]] = []
    for cand in candidates:
        diff = round(cand.price - product.price, 2)
        if diff < 0:
            label = f"₹{int(abs(diff))} cheaper"
        elif diff > 0:
            label = f"₹{int(diff)} higher"
        else:
            label = "same price"
        options.append(
            {
                "product_id": cand.id,
                "sku": cand.sku,
                "name": cand.name,
                "name_kn": cand.name_kn,
                "price": cand.price,
                "stock_qty": cand.stock_qty,
                "price_diff": diff,
                "comparison_label": label,
            }
        )
    return options


def _score_product_match(segment: str, product: Product) -> int:
    seg = segment.lower().strip()
    score = 0
    if product.name.lower() in seg:
        score += 10
    if product.name_kn and product.name_kn in segment:
        score += 10
    for alias in product.aliases_json or []:
        alias_l = str(alias).lower().strip()
        if not alias_l:
            continue
        if alias_l in seg or alias_l in segment:
            score += 4 + len(alias_l.split())
    return score


def _extract_qty_near_segment(segment: str, product_name: str = "") -> tuple[float, str]:
    cleaned = segment
    # Avoid confusing product pack size (e.g. "5 kg" in "Aashirvaad Atta 5 kg") with order quantity
    pack_match = re.search(r"(\d+(?:\.\d+)?\s*(?:kg|g|ml|l|litre|liter))\b", product_name, flags=re.IGNORECASE)
    if pack_match:
        pack_token = re.escape(pack_match.group(1))
        cleaned = re.sub(pack_token, " ", cleaned, count=1, flags=re.IGNORECASE)

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(kg|ಕೆಜಿ|litre|liter|ltr|ಲೀಟರ್|l|pack|bag|bar|jar|ಪ್ಯಾಕ್)?",
        cleaned,
        flags=re.IGNORECASE,
    )
    if match:
        qty = float(match.group(1))
        unit_raw = (match.group(2) or "").lower()
        unit_map = {
            "ಕೆಜಿ": "kg",
            "liter": "litre",
            "ltr": "litre",
            "ಲೀಟರ್": "litre",
            "l": "litre",
            "ಪ್ಯಾಕ್": "pack",
        }
        return qty, unit_map.get(unit_raw, unit_raw or "unit")
    return 1.0, "unit"


def parse_whatsapp_order_message(
    db: Session,
    customer: Customer,
    raw_message: str,
    explicit_payment_intent: str | None = None,
) -> dict[str, Any]:
    """Parse Kannada/Tanglish/English message into structured line items, stock checks, and draft replies."""
    products = db.query(Product).all()
    payment_intent = detect_payment_intent(raw_message, explicit_payment_intent)
    repeat = is_repeat_order_text(raw_message)

    parsed_items: list[dict[str, Any]] = []
    reference_order_id: int | None = None

    if repeat:
        last_order = (
            db.query(WhatsAppOrder)
            .filter(
                WhatsAppOrder.customer_id == customer.id,
                WhatsAppOrder.status.in_(["completed", "approved"]),
            )
            .order_by(WhatsAppOrder.created_at.desc())
            .first()
        )
        if last_order and last_order.parsed_items_json:
            reference_order_id = last_order.id
            prod_by_id = {p.id: p for p in products}
            for prev in last_order.parsed_items_json:
                prod = prod_by_id.get(prev.get("product_id"))
                if not prod:
                    continue
                qty = float(prev.get("qty", 1))
                avail = prod.stock_qty >= qty
                parsed_items.append(
                    {
                        "product_id": prod.id,
                        "requested_name": prev.get("requested_name", prod.name),
                        "matched_product_name": prod.name,
                        "matched_product_name_kn": prod.name_kn,
                        "qty": qty,
                        "unit": prod.unit,
                        "unit_price": prod.price,
                        "line_total": round(qty * prod.price, 2),
                        "stock_qty": prod.stock_qty,
                        "available": avail,
                        "substitute_options": [] if avail else _substitute_options_for(db, prod),
                        "selected_substitute_id": None,
                    }
                )
    else:
        # Split sentence on common Kannada & English conjunctions
        chunks = re.split(r"(?:,|\band\b|\bmattu\b|ಮತ್ತು|\+|&)", raw_message, flags=re.IGNORECASE)
        matched_ids: set[int] = set()
        for chunk in chunks:
            cleaned = chunk.strip()
            if not cleaned:
                continue
            best_prod: Product | None = None
            best_score = 0
            for prod in products:
                s = _score_product_match(cleaned, prod)
                if s > best_score:
                    best_score = s
                    best_prod = prod
            if best_prod and best_score > 0 and best_prod.id not in matched_ids:
                matched_ids.add(best_prod.id)
                qty, detected_unit = _extract_qty_near_segment(cleaned, best_prod.name)
                unit_label = best_prod.unit or detected_unit
                avail = best_prod.stock_qty >= qty
                parsed_items.append(
                    {
                        "product_id": best_prod.id,
                        "requested_name": cleaned,
                        "matched_product_name": best_prod.name,
                        "matched_product_name_kn": best_prod.name_kn,
                        "qty": qty,
                        "unit": unit_label,
                        "unit_price": best_prod.price,
                        "line_total": round(qty * best_prod.price, 2),
                        "stock_qty": best_prod.stock_qty,
                        "available": avail,
                        "substitute_options": [] if avail else _substitute_options_for(db, best_prod),
                        "selected_substitute_id": None,
                    }
                )

    total_amount = round(sum(item["line_total"] for item in parsed_items), 2)
    unavailable_items = [item for item in parsed_items if not item["available"]]
    projected_balance = round(customer.current_balance + (total_amount if payment_intent == "credit" else 0.0), 2)
    credit_exceeded = payment_intent == "credit" and projected_balance > customer.credit_limit

    if unavailable_items:
        first_missing = unavailable_items[0]
        subs = first_missing.get("substitute_options", [])
        if subs:
            top_sub = subs[0]
            draft_kn = (
                f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಆರ್ಡರ್‌ನ {first_missing['matched_product_name_kn']} "
                f"ಸದ್ಯಕ್ಕೆ ಸ್ಟಾಕ್‌ನಲ್ಲಿ ಇಲ್ಲ. ಅದರ ಬದಲಾಗಿ {top_sub['name_kn']} ({top_sub['comparison_label']}, "
                f"₹{int(top_sub['price'])}) ಕಳಿಸಲಾ? ದಯವಿಟ್ಟು ತಿಳಿಸಿ."
            )
            draft_en = (
                f"Namaskara {customer.name}. {first_missing['matched_product_name']} is currently out of stock. "
                f"May we send {top_sub['name']} (₹{int(top_sub['price'])}, {top_sub['comparison_label']}) instead? "
                f"Please confirm."
            )
        else:
            draft_kn = (
                f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. {first_missing['matched_product_name_kn']} ಸದ್ಯಕ್ಕೆ ಸ್ಟಾಕ್ ಮುಗಿದಿದೆ. "
                f"ನಾಳೆ ಹೊಸ ಸ್ಟಾಕ್ ಬರುತ್ತದೆ."
            )
            draft_en = f"Namaskara {customer.name}. {first_missing['matched_product_name']} is out of stock until tomorrow."
        suggested_action = f"Select substitute for {first_missing['matched_product_name']} and approve Kannada reply"
        status = "needs_substitute"
        workflow_stage = "suggest_substitute"
    elif credit_exceeded:
        draft_kn = (
            f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಹಳೆಯ ಬಾಕಿ ₹{int(customer.current_balance):,} ಆಗಿದ್ದು, "
            f"ಕ್ರೆಡಿಟ್ ಮಿತಿ ₹{int(customer.credit_limit):,} ಮೀರಿದೆ. ದಯವಿಟ್ಟು ಮುಂಗಡ ಪಾವತಿ ಮಾಡಿ ಅಥವಾ ಅಂಗಡಿಗೆ ತಿಳಿಸಿ."
        )
        draft_en = (
            f"Namaskara {customer.name}. Your balance ₹{int(customer.current_balance):,} exceeds your credit limit "
            f"₹{int(customer.credit_limit):,}. Owner approval required before adding ₹{int(total_amount):,} order."
        )
        suggested_action = "Credit limit exceeded — approve additional credit, ask for payment first, or cancel"
        status = "credit_warning"
        workflow_stage = "credit_limit_check"
    else:
        item_summary_kn = ", ".join(
            f"{int(i['qty']) if i['qty'].is_integer() else i['qty']} {i['unit']} {i['matched_product_name_kn']}"
            for i in parsed_items
        )
        item_summary_en = ", ".join(
            f"{int(i['qty']) if i['qty'].is_integer() else i['qty']} {i['unit']} {i['matched_product_name']}"
            for i in parsed_items
        )
        pay_kn = "ನಿಮ್ಮ ಖಾತೆಗೆ ಸೇರಿಸಲಾಗಿದೆ" if payment_intent == "credit" else "UPI / ನಗದು ಬಿಲ್ ಸಿದ್ಧವಾಗಿದೆ"
        pay_en = "added to your khata" if payment_intent == "credit" else "billed via cash/UPI"
        draft_kn = (
            f"ನಮಸ್ಕಾರ {customer.name_kn} ಅವರೆ. ನಿಮ್ಮ ಆರ್ಡರ್ ({item_summary_kn}) ದೃಢೀಕರಿಸಲಾಗಿದೆ. "
            f"ಒಟ್ಟು ಮೊತ್ತ ₹{int(total_amount):,} {pay_kn}. ಧನ್ಯವಾದಗಳು - ಕಿರಾಣಾ ಖಾತಾ ಏಜೆಂಟ್."
        )
        draft_en = (
            f"Namaskara {customer.name}. Your order ({item_summary_en}) for ₹{int(total_amount):,} "
            f"has been confirmed and {pay_en}. Thank you - Kirana Khata Agent."
        )
        suggested_action = "Approve order fulfillment, update stock & khata, and send Kannada WhatsApp confirmation"
        status = "pending_approval"
        workflow_stage = "awaiting_owner_approval"

    english_translation = (
        "Repeat last week's order"
        if repeat
        else "; ".join(
            f"{int(i['qty']) if i['qty'].is_integer() else i['qty']} {i['unit']} {i['matched_product_name']}"
            for i in parsed_items
        )
        + (f" ({'on credit/khata' if payment_intent == 'credit' else payment_intent})" if parsed_items else "")
    )
    if not parsed_items:
        english_translation = raw_message

    reason_parts = [
        f"Parsed {len(parsed_items)} SKU(s) from customer message ({'repeat order lookup' if repeat else 'Kannada/English NLP match'})."
    ]
    if unavailable_items:
        reason_parts.append(f"{unavailable_items[0]['matched_product_name']} has 0 stock; matched same-category alternatives.")
    elif credit_exceeded:
        reason_parts.append(
            f"Current balance ₹{int(customer.current_balance):,} + order ₹{int(total_amount):,} = ₹{int(projected_balance):,} > limit ₹{int(customer.credit_limit):,}."
        )
    else:
        reason_parts.append("All items verified in stock and customer is within credit limit.")

    return {
        "intent": "repeat_order" if repeat else "order",
        "payment_intent": payment_intent,
        "english_translation": english_translation,
        "parsed_items": parsed_items,
        "total_amount": total_amount,
        "credit_check_status": "exceeds_limit" if credit_exceeded else "ok",
        "status": status,
        "workflow_stage": workflow_stage,
        "suggested_action": suggested_action,
        "reason_text": " ".join(reason_parts),
        "source_data": {
            "raw_message": raw_message,
            "is_repeat_order": repeat,
            "reference_order_id": reference_order_id,
            "customer_balance": customer.current_balance,
            "customer_credit_limit": customer.credit_limit,
            "items_matched": [i["matched_product_name"] for i in parsed_items],
        },
        "draft_reply_kn": draft_kn,
        "draft_reply_en": draft_en,
        "is_repeat_order": repeat,
        "reference_order_id": reference_order_id,
    }


def match_customer_by_text(db: Session, text: str) -> Customer | None:
    lower = text.lower()
    for cust in db.query(Customer).all():
        first = cust.name.split()[0].lower()
        if first in lower or cust.name.lower() in lower or (cust.name_kn and cust.name_kn in text):
            return cust
    return None


def match_product_by_text(db: Session, text: str) -> Product | None:
    best_prod: Product | None = None
    best_score = 0
    for prod in db.query(Product).all():
        s = _score_product_match(text, prod)
        if s > best_score:
            best_score = s
            best_prod = prod
    return best_prod


def parse_owner_voice_command(text: str) -> dict[str, Any]:
    """Parse owner Kannada/Tanglish/English voice commands into structured intent."""
    lower = text.lower().strip()
    amount_match = re.search(r"(\d+(?:\.\d+)?)", lower)
    amount = float(amount_match.group(1)) if amount_match else None

    if any(k in lower or k in text for k in ("reminder", "kalisu", "ರಿಮೈಂಡರ್", "ಕಳಿಸು")):
        return {"intent": "send_reminder", "amount": amount, "raw": text}
    if any(k in lower or k in text for k in ("stock", "eshtu ide", "ಸ್ಟಾಕ್", "ಎಷ್ಟು ಇದೆ")):
        return {"intent": "check_stock", "amount": amount, "raw": text}
    if any(k in lower or k in text for k in ("baki iddane", "baki", "balance", "ಬಾಕಿ")):
        if amount and any(k in lower or k in text for k in ("haki", "haaki", "add", "ಹಾಕಿ")):
            return {"intent": "add_khata", "amount": amount, "raw": text}
        return {"intent": "check_balance", "amount": amount, "raw": text}
    if any(k in lower or k in text for k in ("khatege", "haki", "haaki", "add", "ಖಾತೆಗೆ", "ಹಾಕಿ")) and amount:
        return {"intent": "add_khata", "amount": amount, "raw": text}

    return {"intent": "check_balance", "amount": amount, "raw": text}
