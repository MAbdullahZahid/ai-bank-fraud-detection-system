"""
Admin-managed Merchants and Billers.

Merchants -> used in PAYMENT transactions.
Billers -> used in DEBIT transactions.

These are stored as normal User accounts so they have balances and can
receive money through the existing transaction flow.
"""

import re
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.database import get_db
from app.models.user import User
from app.services.auth_service import hash_password
from app.routers.deps import get_current_admin, get_current_user

router = APIRouter(prefix="/api", tags=["Merchants & Billers"])

PHONE_REGEX = re.compile(r"^\+?[0-9]{7,15}$")


# ---------------------------------------------------
# Validation
# ---------------------------------------------------

def validate_phone(value: str) -> str:
    value = value.strip().replace(" ", "")

    if not PHONE_REGEX.match(value):
        raise ValueError(
            "Phone number must contain 7-15 digits (optional leading +)."
        )

    return value


# ---------------------------------------------------
# Schemas
# ---------------------------------------------------

class PayeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone_number: str
    starting_balance: float = Field(default=0.0, ge=0)

    @field_validator("phone_number")
    @classmethod
    def phone_validator(cls, value):
        return validate_phone(value)


class PayeeUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    balance: Optional[float] = Field(default=None, ge=0)

    @field_validator("phone_number")
    @classmethod
    def phone_validator(cls, value):
        if value is None:
            return value
        return validate_phone(value)


class PayeeOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone_number: str
    balance: float

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------
# Internal helpers
# ---------------------------------------------------

def create_payee(
    db: Session,
    payee_in: PayeeCreate,
    *,
    is_merchant: bool,
    is_biller: bool,
):

    existing = db.query(User).filter(
        User.phone_number == payee_in.phone_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="A user with this phone number already exists."
        )

    existing_email = db.query(User).filter(
        User.email == payee_in.email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists."
        )

    payee = User(
        full_name=payee_in.full_name,
        email=payee_in.email,
        phone_number=payee_in.phone_number,
        password=hash_password(secrets.token_hex(16)),
        balance=payee_in.starting_balance,
        is_merchant=is_merchant,
        is_biller=is_biller,
    )

    db.add(payee)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Unable to create payee."
        )

    db.refresh(payee)

    return payee


def update_payee(
    db: Session,
    payee_id: int,
    payee_in: PayeeUpdate,
    *,
    is_merchant: bool,
    is_biller: bool,
):

    payee = db.query(User).filter(
        User.id == payee_id,
        User.is_merchant == is_merchant,
        User.is_biller == is_biller,
    ).first()

    if not payee:
        raise HTTPException(status_code=404, detail="Payee not found.")

    if (
        payee_in.phone_number
        and payee.phone_number != payee_in.phone_number
    ):

        exists = db.query(User).filter(
            User.phone_number == payee_in.phone_number
        ).first()

        if exists:
            raise HTTPException(
                status_code=400,
                detail="A user with this phone number already exists."
            )

        payee.phone_number = payee_in.phone_number

    if (
        payee_in.email
        and payee.email != payee_in.email
    ):

        exists_email = db.query(User).filter(
            User.email == payee_in.email
        ).first()

        if exists_email:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists."
            )

        payee.email = payee_in.email

    if payee_in.full_name is not None:
        payee.full_name = payee_in.full_name

    if payee_in.balance is not None:
        payee.balance = payee_in.balance

    db.commit()
    db.refresh(payee)

    return payee


def delete_payee(
    db: Session,
    payee_id: int,
    *,
    is_merchant: bool,
    is_biller: bool,
):

    payee = db.query(User).filter(
        User.id == payee_id,
        User.is_merchant == is_merchant,
        User.is_biller == is_biller,
    ).first()

    if not payee:
        raise HTTPException(status_code=404, detail="Payee not found.")

    try:
        db.delete(payee)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete. Existing transactions reference this account."
        )

    return {"message": "Deleted successfully."}


# ==========================================================
# Merchant APIs
# ==========================================================

@router.post("/admin/merchants", response_model=PayeeOut)
def create_merchant(
    payee: PayeeCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return create_payee(
        db,
        payee,
        is_merchant=True,
        is_biller=False,
    )


@router.get("/admin/merchants", response_model=List[PayeeOut])
def admin_merchants(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return (
        db.query(User)
        .filter(User.is_merchant.is_(True))
        .order_by(User.full_name)
        .all()
    )


@router.put("/admin/merchants/{merchant_id}", response_model=PayeeOut)
def edit_merchant(
    merchant_id: int,
    payee: PayeeUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return update_payee(
        db,
        merchant_id,
        payee,
        is_merchant=True,
        is_biller=False,
    )


@router.delete("/admin/merchants/{merchant_id}")
def remove_merchant(
    merchant_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return delete_payee(
        db,
        merchant_id,
        is_merchant=True,
        is_biller=False,
    )


@router.get("/merchants", response_model=List[PayeeOut])
def merchants(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(User)
        .filter(User.is_merchant.is_(True))
        .order_by(User.full_name)
        .all()
    )


# ==========================================================
# Biller APIs
# ==========================================================

@router.post("/admin/billers", response_model=PayeeOut)
def create_biller(
    payee: PayeeCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return create_payee(
        db,
        payee,
        is_merchant=False,
        is_biller=True,
    )


@router.get("/admin/billers", response_model=List[PayeeOut])
def admin_billers(
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return (
        db.query(User)
        .filter(User.is_biller.is_(True))
        .order_by(User.full_name)
        .all()
    )


@router.put("/admin/billers/{biller_id}", response_model=PayeeOut)
def edit_biller(
    biller_id: int,
    payee: PayeeUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return update_payee(
        db,
        biller_id,
        payee,
        is_merchant=False,
        is_biller=True,
    )


@router.delete("/admin/billers/{biller_id}")
def remove_biller(
    biller_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return delete_payee(
        db,
        biller_id,
        is_merchant=False,
        is_biller=True,
    )


@router.get("/billers", response_model=List[PayeeOut])
def billers(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(User)
        .filter(User.is_biller.is_(True))
        .order_by(User.full_name)
        .all()
    )