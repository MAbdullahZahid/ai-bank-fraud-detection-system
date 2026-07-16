"""
Core transaction flow (updated for phone-number-based transfers):
1. A logged-in user submits a transaction (destination phone number, amount, type)
2. Backend resolves sender from the JWT (never trusts a client-supplied sender id)
3. Backend looks up the receiver by phone number - like a mobile wallet account number
4. Computes engineered features and sends them to the trained XGBoost model
5. If flagged as fraud -> transaction is logged, balances are NOT updated,
   and a fraud_log entry is created for the admin portal
6. If legit -> balances update normally, transaction is logged as "legit"

Admin-only endpoints below also expose enriched transaction/fraud data
(with names + phone numbers joined in) and summary stats for the dashboard.
"""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.ml_service import predict_fraud, THRESHOLD
from app.routers.deps import get_current_admin, get_current_user
from app.services.email_service import send_transaction_email, send_admin_fraud_alert

router = APIRouter(prefix="/api", tags=["Transactions"])

OUTGOING_TYPES = {"TRANSFER", "CASH_OUT", "PAYMENT", "DEBIT"}
INCOMING_TYPES = {"CASH_IN"}


@router.post(
    "/transactions",
    response_model=TransactionOut,
    responses={
        400: {"description": "Validation or balance error"},
        404: {"description": "Counterparty account not found"},
    },
)
def create_transaction(
    tx_in: TransactionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    counterparty = db.query(User).filter(User.phone_number == tx_in.counterparty_phone).first()
    if not counterparty:
        raise HTTPException(status_code=404, detail="No account found with this phone number")

    if counterparty.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot use your own account as the counterparty")

    if tx_in.type in OUTGOING_TYPES:
        sender = current_user
        receiver = counterparty
        if sender.balance < tx_in.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
    elif tx_in.type in INCOMING_TYPES:
        sender = counterparty
        receiver = current_user
        if sender.balance < tx_in.amount:
            raise HTTPException(status_code=400, detail="Counterparty account has insufficient balance")
    else:
        raise HTTPException(status_code=400, detail="Unsupported transaction type")

    old_balance_orig = sender.balance
    new_balance_orig = sender.balance - tx_in.amount
    old_balance_dest = receiver.balance
    new_balance_dest = receiver.balance + tx_in.amount

    probability, is_fraud = predict_fraud(
        tx_in.type, tx_in.amount,
        old_balance_orig, new_balance_orig,
        old_balance_dest, new_balance_dest,
    )

    transaction = Transaction(
        sender_id=sender.id,
        receiver_id=receiver.id,
        amount=tx_in.amount,
        type=tx_in.type,
        fraud_probability=probability,
        prediction="fraud" if is_fraud else "legit",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    if is_fraud:
        fraud_log = FraudLog(
            transaction_id=transaction.id,
            model_score=probability,
            threshold=THRESHOLD,
            reason=(
                f"{tx_in.type} of amount {tx_in.amount:.2f} flagged as fraud "
                f"(model score {probability:.4f} >= threshold {THRESHOLD})."
            ),
        )
        db.add(fraud_log)
        db.commit()

        # NEW - notify the customer and the admin
        send_transaction_email(
            to_email=current_user.email, full_name=current_user.full_name,
            transaction_type=tx_in.type, amount=tx_in.amount,
            is_fraud=True, probability=probability,
        )
        send_admin_fraud_alert(
            user_full_name=current_user.full_name, user_phone=current_user.phone_number,
            transaction_type=tx_in.type, amount=tx_in.amount,
            probability=probability, transaction_id=transaction.id,
        )
    else:
        current_user.balance = new_balance_orig
        receiver.balance = new_balance_dest
        db.commit()

        # NEW - notify the customer
        send_transaction_email(
            to_email=current_user.email, full_name=current_user.full_name,
            transaction_type=tx_in.type, amount=tx_in.amount,
            is_fraud=False, probability=probability,
        )

    return transaction


@router.get("/transactions/me")
def my_transactions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """The logged-in user's own transaction history - sent and received, never anyone else's."""
    txs = (
        db.query(Transaction)
        .filter((Transaction.sender_id == current_user.id) | (Transaction.receiver_id == current_user.id))
        .order_by(Transaction.timestamp.desc())
        .all()
    )

    result = []
    for t in txs:
        direction = "sent" if t.sender_id == current_user.id else "received"
        counterpart_id = t.receiver_id if direction == "sent" else t.sender_id
        counterpart = db.query(User).filter(User.id == counterpart_id).first()
        result.append({
            "id": t.id,
            "direction": direction,
            "counterpart_name": counterpart.full_name if counterpart else "Unknown",
            "counterpart_phone": counterpart.phone_number if counterpart else "-",
            "amount": t.amount,
            "type": t.type,
            "prediction": t.prediction,
            "fraud_probability": t.fraud_probability,
            "timestamp": t.timestamp,
        })
    return result


@router.get("/admin/transactions")
def list_transactions(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[object, Depends(get_current_admin)],
):
    """Admin view - enriched with names/phone numbers so it's actually readable."""
    txs = db.query(Transaction).order_by(Transaction.timestamp.desc()).all()
    result = []
    for t in txs:
        sender = db.query(User).filter(User.id == t.sender_id).first()
        receiver = db.query(User).filter(User.id == t.receiver_id).first()
        result.append({
            "id": t.id,
            "sender_name": sender.full_name if sender else "Unknown",
            "sender_phone": sender.phone_number if sender else "-",
            "receiver_name": receiver.full_name if receiver else "Unknown",
            "receiver_phone": receiver.phone_number if receiver else "-",
            "amount": t.amount,
            "type": t.type,
            "fraud_probability": t.fraud_probability,
            "prediction": t.prediction,
            "timestamp": t.timestamp,
        })
    return result


@router.get("/admin/fraud-logs")
def list_fraud_logs(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[object, Depends(get_current_admin)],
):
    logs = db.query(FraudLog).order_by(FraudLog.created_at.desc()).all()
    result = []
    for log in logs:
        tx = db.query(Transaction).filter(Transaction.id == log.transaction_id).first()
        result.append({
            "id": log.id,
            "transaction_id": log.transaction_id,
            "model_score": log.model_score,
            "threshold": log.threshold,
            "reason": log.reason,
            "created_at": log.created_at,
            "amount": tx.amount if tx else None,
            "type": tx.type if tx else None,
        })
    return result


@router.get("/admin/stats")
def get_stats(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[object, Depends(get_current_admin)],
):
    """Summary numbers for the admin dashboard's stat cards + chart."""
    total_users = db.query(User).count()
    total_tx = db.query(Transaction).count()
    fraud_count = db.query(Transaction).filter(Transaction.prediction == "fraud").count()
    legit_count = total_tx - fraud_count
    total_volume = (
        db.query(func.sum(Transaction.amount)).filter(Transaction.prediction == "legit").scalar() or 0
    )
    fraud_rate = round((fraud_count / total_tx * 100), 2) if total_tx else 0.0

    return {
        "total_users": total_users,
        "total_transactions": total_tx,
        "fraud_count": fraud_count,
        "legit_count": legit_count,
        "fraud_rate": fraud_rate,
        "total_volume": total_volume,
    }
