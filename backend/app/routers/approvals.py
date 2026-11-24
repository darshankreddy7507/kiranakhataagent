"""Approval queue and immutable audit log routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApprovalRequest, AuditLog
from app.routers.serializers import serialize_approval, serialize_audit_log
from app.schemas import ApprovalDecisionRequest
from app.services.approvals import decide_approval_request

router = APIRouter(prefix="/api", tags=["approvals"])


@router.get("/approvals")
def list_approvals(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status and status != "all":
        q = q.filter(ApprovalRequest.status == status)
    reqs = q.all()
    return [serialize_approval(db, a) for a in reqs]


@router.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: int, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)
):
    try:
        res = decide_approval_request(
            db,
            approval_id=approval_id,
            decision=payload.decision,
            edited_payload=payload.edited_payload,
            decision_note=payload.decision_note,
        )
        return {
            "approval": serialize_approval(db, res["approval"]),
            "follow_up_approval": serialize_approval(db, res["follow_up_approval"]) if res["follow_up_approval"] else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audit-logs")
def list_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_audit_log(l) for l in logs]
