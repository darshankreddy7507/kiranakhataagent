"""Inventory ledger and supplier-bill photo OCR upload routes."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product, SupplierBill
from app.routers.serializers import (
    serialize_approval,
    serialize_bill,
    serialize_product,
)
from app.schemas import AddStockRequest, CreateProductRequest
from app.services.workflow import (
    ingest_supplier_bill_workflow,
    owner_add_stock_workflow,
    owner_create_product_workflow,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("")
def list_inventory(
    status: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    products = db.query(Product).order_by(Product.stock_qty.asc(), Product.name.asc()).all()
    items = [serialize_product(p) for p in products]
    if status and status != "all":
        if status == "low":
            items = [i for i in items if i.stock_status in ("low_stock", "out_of_stock")]
        else:
            items = [i for i in items if i.stock_status == status]
    if category and category != "all":
        items = [i for i in items if i.category == category]
    return items


@router.get("/bills")
def list_supplier_bills(db: Session = Depends(get_db)):
    bills = db.query(SupplierBill).order_by(SupplierBill.created_at.desc()).all()
    return [serialize_bill(db, b) for b in bills]


@router.post("/bills/upload")
async def upload_supplier_bill(
    file: UploadFile | None = File(default=None),
    scenario: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    image_bytes = await file.read() if file else None
    filename = (file.filename if file and file.filename else None) or f"{scenario or 'kaveri_staples'}_bill.jpg"
    try:
        res = ingest_supplier_bill_workflow(
            db,
            image_bytes=image_bytes,
            filename=filename,
            scenario=scenario,
        )
        return {
            "bill": serialize_bill(db, res["bill"]),
            "approval": serialize_approval(db, res["approval"]),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/add-stock")
def add_inventory_stock(payload: AddStockRequest, db: Session = Depends(get_db)):
    try:
        updated = owner_add_stock_workflow(
            db,
            product_id=payload.product_id,
            quantity_added=payload.quantity_added,
            note=payload.note,
            new_price=payload.new_price,
        )
        return serialize_product(updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/products")
def create_inventory_product(payload: CreateProductRequest, db: Session = Depends(get_db)):
    try:
        created = owner_create_product_workflow(
            db,
            name=payload.name,
            name_kn=payload.name_kn,
            category=payload.category,
            unit=payload.unit,
            price=payload.price,
            cost_price=payload.cost_price,
            stock_qty=payload.stock_qty,
            reorder_level=payload.reorder_level,
            supplier_id=payload.supplier_id,
        )
        return serialize_product(created)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
