from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional

VALID_TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}


class TransactionCreate(BaseModel):
    counterparty_phone: str = Field(validation_alias=AliasChoices("counterparty_phone", "receiver_phone"))
    amount: float = Field(gt=0)
    type: str
    # Only ever meaningful for CASH_OUT (ATM flow) - count of wrong password
    # tries immediately before this attempt succeeded. Every other type
    # should send 0 (or omit it), which the rules engine treats as a no-op.
    # Bounded 0-3 since the frontend locks the card after 3 total attempts -
    # anything outside that range can't be a real value and is rejected here
    # rather than trusted from the client.
    failed_password_attempts: int = Field(default=0, ge=0, le=3)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        normalized = v.strip().upper()
        if normalized not in VALID_TYPES:
            raise ValueError(f"type must be one of {sorted(VALID_TYPES)}")
        return normalized

    @field_validator("counterparty_phone")
    @classmethod
    def validate_phone(cls, v):
        return v.strip().replace(" ", "")


class TransactionOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    amount: float
    type: str
    fraud_probability: Optional[float] = None
    prediction: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)