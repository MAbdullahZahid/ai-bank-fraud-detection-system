"""
User management.
- Admin-only: create user, list all users (with balance/email visible)
- Public: minimal user list for the home page transaction dropdown
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserPublic
from app.services.auth_service import hash_password
from app.routers.deps import get_current_admin

router = APIRouter(prefix="/api", tags=["Users"])


@router.post("/admin/users", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password=hash_password(user_in.password),
        balance=user_in.balance,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    return db.query(User).all()


@router.get("/users", response_model=List[UserPublic])
def public_users(db: Session = Depends(get_db)):
    """Used by the home page's sender/receiver dropdowns - no auth, minimal fields only."""
    return db.query(User).all()
