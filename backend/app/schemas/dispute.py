from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class DisputeCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class DisputeOut(BaseModel):
    id: int
    transaction_id: int
    customer_reason: str
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DisputeResolve(BaseModel):
    approve: bool
    admin_notes: Optional[str] = Field(default=None, max_length=1000)