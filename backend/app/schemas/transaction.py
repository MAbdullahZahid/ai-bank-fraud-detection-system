from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class TransactionCreate(BaseModel):
    sender_id: int
    receiver_id: int
    amount: float
    type: str  # one of: CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER


class TransactionOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    amount: float
    type: str
    fraud_probability: Optional[float]
    prediction: Optional[str]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
