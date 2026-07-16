from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional

VALID_TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


class TransactionCreate(BaseModel):
    receiver_phone: str
    amount: float = Field(gt=0)
    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in VALID_TYPES:
            raise ValueError(f"type must be one of {sorted(VALID_TYPES)}")
        return v

    @field_validator("receiver_phone")
    @classmethod
    def validate_phone(cls, v):
        return v.strip().replace(" ", "")


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
