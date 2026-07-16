"""
Core transaction flow:
1. User submits a transaction from the home page (sender, receiver, amount, type)
2. Backend looks up real balances from the users table
3. Computes engineered features and sends them to the trained XGBoost model
4. If flagged as fraud -> transaction is logged, balances are NOT updated,
   and a fraud_log entry is created for the admin portal
5. If legit -> balances update normally, transaction is logged as "legit"
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.ml_service import predict_fraud, THRESHOLD
from app.routers.deps import get_current_admin

router = APIRouter(prefix="/api", tags=["Transactions"])

VALID_TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


@router.post("/transactions", response_model=TransactionOut)
def create_transaction(tx_in: TransactionCreate, db: Session = Depends(get_db)):
    if tx_in.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(VALID_TYPES)}")
    if tx_in.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    sender = db.query(User).filter(User.id == tx_in.sender_id).first()
    receiver = db.query(User).filter(User.id == tx_in.receiver_id).first()
    if not sender or not receiver:
        raise HTTPException(status_code=404, detail="Sender or receiver not found")
    if sender.id == receiver.id:
        raise HTTPException(status_code=400, detail="Sender and receiver must be different users")
    if sender.balance < tx_in.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

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
        # Block the transfer - balances are NOT updated for flagged transactions
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
    else:
        sender.balance = new_balance_orig
        receiver.balance = new_balance_dest
        db.commit()

    return transaction


@router.get("/admin/transactions", response_model=List[TransactionOut])
def list_transactions(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(Transaction).order_by(Transaction.timestamp.desc()).all()


@router.get("/admin/fraud-logs")
def list_fraud_logs(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    logs = db.query(FraudLog).order_by(FraudLog.created_at.desc()).all()
    return [
        {
            "id": log.id,
            "transaction_id": log.transaction_id,
            "model_score": log.model_score,
            "threshold": log.threshold,
            "reason": log.reason,
            "created_at": log.created_at,
        }
        for log in logs
    ]
