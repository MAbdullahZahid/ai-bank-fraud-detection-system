from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    balance: float = 0.0


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    balance: float

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    """Minimal info shown on the public home page dropdown (no email/balance leak)."""
    id: int
    full_name: str

    model_config = ConfigDict(from_attributes=True)
