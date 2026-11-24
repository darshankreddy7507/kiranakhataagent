"""Store settings and owner sign-in/logout routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ShopSettings
from app.schemas import LoginRequest, ShopSettingsOut, ShopSettingsUpdate
from app.services.approvals import record_audit
from app.services.realtime import realtime_bus

router = APIRouter(prefix="/api", tags=["settings"])


def get_or_create_shop_settings(db: Session) -> ShopSettings:
    row = db.query(ShopSettings).first()
    if row:
        return row
    cfg = get_settings()
    row = ShopSettings(
        shop_name=cfg.shop_name,
        shop_name_kn=cfg.shop_name_kn,
        owner_name=cfg.owner_name,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _serialize_settings(row: ShopSettings) -> ShopSettingsOut:
    return ShopSettingsOut(
        shop_name=row.shop_name,
        shop_name_kn=row.shop_name_kn,
        owner_name=row.owner_name,
        owner_phone=row.owner_phone,
        upi_id=row.upi_id,
        default_credit_limit=row.default_credit_limit,
        telegram_connected=bool(get_settings().telegram_bot_token.strip()),
    )


@router.get("/settings", response_model=ShopSettingsOut)
def read_shop_settings(db: Session = Depends(get_db)):
    return _serialize_settings(get_or_create_shop_settings(db))


@router.put("/settings", response_model=ShopSettingsOut)
def update_shop_settings(payload: ShopSettingsUpdate, db: Session = Depends(get_db)):
    row = get_or_create_shop_settings(db)
    old_name = row.shop_name
    row.shop_name = payload.shop_name.strip()
    if payload.shop_name_kn is not None and payload.shop_name_kn.strip():
        row.shop_name_kn = payload.shop_name_kn.strip()
    else:
        row.shop_name_kn = row.shop_name
    row.owner_name = payload.owner_name.strip()
    if payload.owner_phone is not None:
        row.owner_phone = payload.owner_phone.strip()
    if payload.upi_id is not None:
        row.upi_id = payload.upi_id.strip()
    if payload.default_credit_limit is not None:
        row.default_credit_limit = float(payload.default_credit_limit)
    if payload.owner_pin is not None:
        row.owner_pin = payload.owner_pin.strip()

    record_audit(
        db,
        event_type="approved",
        actor="owner",
        entity_type="shop_settings",
        entity_id=row.id,
        summary=f"Updated store settings ({old_name} -> {row.shop_name}, Owner: {row.owner_name})",
        summary_kn=f"ಅಂಗಡಿ ವಿವರ ನವೀಕರಿಸಲಾಗಿದೆ: {row.shop_name_kn}",
        before_state={"shop_name": old_name},
        after_state={"shop_name": row.shop_name, "owner_name": row.owner_name},
    )
    db.commit()
    db.refresh(row)
    realtime_bus.publish("settings_updated", {"shop_name": row.shop_name})
    return _serialize_settings(row)


@router.post("/auth/login")
def owner_login(payload: LoginRequest, db: Session = Depends(get_db)):
    row = get_or_create_shop_settings(db)
    if payload.pin.strip() != row.owner_pin:
        raise HTTPException(status_code=401, detail="Incorrect shop PIN (default demo PIN is 1234)")
    if payload.owner_name and payload.owner_name.strip():
        row.owner_name = payload.owner_name.strip()
        db.commit()
    return {
        "authenticated": True,
        "owner_name": row.owner_name,
        "shop_name": row.shop_name,
        "settings": _serialize_settings(row),
    }


@router.post("/auth/logout")
def owner_logout():
    return {"authenticated": False}
