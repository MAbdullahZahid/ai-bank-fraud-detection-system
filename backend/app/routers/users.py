"""
User management (admin-only CRUD) + the logged-in user's own profile.
Regular users never see the full user directory or other users' phone
numbers - they only ever type in a destination phone number when sending
money (handled in transactions.py), like a mobile wallet account number.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut, UserProfile, UserCreateResult  ,  VerifyPasswordRequest, VerifyPasswordResponse
from app.services.auth_service import hash_password, verify_password
from app.services.email_service import send_welcome_email
from app.routers.deps import get_current_admin, get_current_user


router = APIRouter(prefix="/api", tags=["Users"])


@router.post("/admin/users", response_model=UserCreateResult)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    if db.query(User).filter(User.phone_number == user_in.phone_number).first():
        raise HTTPException(status_code=400, detail="A user with this phone number already exists")

    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        phone_number=user_in.phone_number,
        password=hash_password(user_in.password),
        balance=user_in.balance,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Best-effort - a failed email should never block user creation
    email_sent = send_welcome_email(
        to_email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        password=user_in.password,  # plain text, only used here before it's discarded
        balance=user.balance,
    )

    return {"user": user, "email_sent": email_sent}


@router.get("/admin/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(User).order_by(User.id).all()


@router.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, user_in: UserUpdate, db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.email and user_in.email != user.email:
        if db.query(User).filter(User.email == user_in.email).first():
            raise HTTPException(status_code=400, detail="Email already in use by another user")
        user.email = user_in.email

    if user_in.phone_number and user_in.phone_number != user.phone_number:
        if db.query(User).filter(User.phone_number == user_in.phone_number).first():
            raise HTTPException(status_code=400, detail="Phone number already in use by another user")
        user.phone_number = user_in.phone_number

    if user_in.full_name:
        user.full_name = user_in.full_name

    if user_in.balance is not None:
        user.balance = user_in.balance

    if user_in.password:
        user.password = hash_password(user_in.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this user - they have existing transactions on record.",
        )

    return {"message": f"User #{user_id} deleted successfully"}


@router.get("/me", response_model=UserProfile)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """The logged-in user's own profile - includes their balance, nothing about other users."""
    return current_user

@router.post("/verify-password", response_model=VerifyPasswordResponse)
def verify_password_endpoint(
    data: VerifyPasswordRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect password")

    return {"valid": True}