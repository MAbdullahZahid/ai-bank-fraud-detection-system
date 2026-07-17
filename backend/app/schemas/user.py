import re
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from typing import Optional
PHONE_REGEX = re.compile(r"^(?:\+44|0)7\d{9}$")


def _validate_phone(v: str) -> str:
    cleaned = v.strip().replace(" ", "")
    if not PHONE_REGEX.match(cleaned):
        raise ValueError("Phone number must be 7-15 digits, optionally starting with +")
    return cleaned


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone_number: str
    password: str = Field(min_length=6, max_length=72)
    balance: float = Field(default=0.0, ge=0)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        return _validate_phone(v)


class UserUpdate(BaseModel):
    """All fields optional - admin only sends what they want to change."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    balance: Optional[float] = Field(default=None, ge=0)
    password: Optional[str] = Field(default=None, min_length=6, max_length=72)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        return _validate_phone(v)


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone_number: str
    balance: float

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    phone_number: str
    password: str


class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone_number: str
    balance: float

    model_config = ConfigDict(from_attributes=True)


class UserCreateResult(BaseModel):
    user: UserOut
    email_sent: bool

class VerifyPasswordRequest(BaseModel):
    password: str


class VerifyPasswordResponse(BaseModel):
    valid: bool