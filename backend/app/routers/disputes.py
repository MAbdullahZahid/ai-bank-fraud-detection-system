from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.dispute import Dispute
from app.models.model_feedback import ModelFeedback
from app.schemas.dispute import DisputeCreate, DisputeOut, DisputeResolve
from app.routers.deps import get_current_user, get_current_admin
from app.services.email_service import send_dispute_email

router = APIRouter(prefix="/api", tags=["Disputes"])


@router.post("/transactions/{transaction_id}/dispute", response_model=DisputeOut)
def create_dispute(
    transaction_id: int,
    dispute_in: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only dispute your own transactions")
    if transaction.prediction != "fraud":
        raise HTTPException(status_code=400, detail="Only transactions flagged as fraud can be disputed")

    existing = db.query(Dispute).filter(Dispute.transaction_id == transaction_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"This transaction already has a dispute (status: {existing.status})",
        )

    dispute = Dispute(
        transaction_id=transaction_id,
        customer_id=current_user.id,
        customer_reason=dispute_in.reason,
        status="pending",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.get("/disputes/me", response_model=List[DisputeOut])
def my_disputes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Dispute)
        .filter(Dispute.customer_id == current_user.id)
        .order_by(Dispute.created_at.desc())
        .all()
    )


@router.get("/admin/disputes")
def list_disputes(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    disputes = db.query(Dispute).order_by(Dispute.created_at.desc()).all()
    result = []
    for d in disputes:
        tx = db.query(Transaction).filter(Transaction.id == d.transaction_id).first()
        customer = db.query(User).filter(User.id == d.customer_id).first()
        result.append({
            "id": d.id,
            "transaction_id": d.transaction_id,
            "customer_name": customer.full_name if customer else "Unknown",
            "customer_phone": customer.phone_number if customer else "-",
            "amount": tx.amount if tx else None,
            "type": tx.type if tx else None,
            "fraud_probability": tx.fraud_probability if tx else None,
            "customer_reason": d.customer_reason,
            "status": d.status,
            "admin_notes": d.admin_notes,
            "created_at": d.created_at,
            "resolved_at": d.resolved_at,
        })
    return result


@router.post("/admin/disputes/{dispute_id}/resolve", response_model=DisputeOut)
def resolve_dispute(
    dispute_id: int,
    resolution: DisputeResolve,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if dispute.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"This dispute was already resolved (status: {dispute.status})"
        )

    transaction = db.query(Transaction).filter(Transaction.id == dispute.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Underlying transaction not found")

    sender = db.query(User).filter(User.id == transaction.sender_id).first()
    receiver = db.query(User).filter(User.id == transaction.receiver_id).first()

    if resolution.approve:
        if sender.balance < transaction.amount:
            raise HTTPException(
                status_code=400,
                detail="Sender no longer has sufficient balance to complete this transaction",
            )
        sender.balance -= transaction.amount
        receiver.balance += transaction.amount
        transaction.prediction = "legit"
        dispute.status = "approved"

        feedback = ModelFeedback(
            transaction_id=transaction.id,
            original_probability=transaction.fraud_probability,
            original_prediction="fraud",
            corrected_label="legit",
            source="dispute_approved",
        )
    else:
        dispute.status = "rejected"

        feedback = ModelFeedback(
            transaction_id=transaction.id,
            original_probability=transaction.fraud_probability,
            original_prediction="fraud",
            corrected_label="fraud",
            source="dispute_rejected",
        )

    dispute.admin_notes = resolution.admin_notes
    dispute.resolved_at = datetime.utcnow()

    db.add(feedback)
    db.commit()
    db.refresh(dispute)

    customer = db.query(User).filter(User.id == dispute.customer_id).first()
    send_dispute_email(
        to_email=customer.email,
        full_name=customer.full_name,
        approved=resolution.approve,
        amount=transaction.amount,
        transaction_type=transaction.type,
    )

    return dispute