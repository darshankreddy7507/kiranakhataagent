"""Suppliers and low-stock reorder draft routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product, Supplier, SupplierOrder
from app.routers.serializers import (
    serialize_approval,
    serialize_product,
    serialize_supplier,
    serialize_supplier_order,
)
from app.schemas import SupplierOrderDraftCreate
from app.services.workflow import create_supplier_reorder_draft_workflow

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).order_by(Supplier.name.asc()).all()
    low_stock = (
        db.query(Product)
        .filter(Product.stock_qty <= Product.reorder_level)
        .order_by(Product.stock_qty.asc())
        .all()
    )
    return {
        "suppliers": [serialize_supplier(db, s) for s in suppliers],
        "low_stock_products": [serialize_product(p) for p in low_stock],
    }


@router.get("/orders")
def list_supplier_orders(db: Session = Depends(get_db)):
    orders = db.query(SupplierOrder).order_by(SupplierOrder.created_at.desc()).all()
    return [serialize_supplier_order(po) for po in orders]


@router.post("/orders/draft")
def create_supplier_order_draft(payload: SupplierOrderDraftCreate, db: Session = Depends(get_db)):
    try:
        res = create_supplier_reorder_draft_workflow(
            db,
            supplier_id=payload.supplier_id,
            product_ids=payload.product_ids,
            custom_items=payload.items,
            whatsapp_draft_kn=payload.whatsapp_draft_kn,
        )
        return {
            "supplier_order": serialize_supplier_order(res["supplier_order"]),
            "approval": serialize_approval(db, res["approval"]),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
