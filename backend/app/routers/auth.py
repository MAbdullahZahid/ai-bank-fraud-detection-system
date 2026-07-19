from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.user import User
from app.services.auth_service import verify_password, create_access_token
from app.schemas.admin import Token
from app.schemas.user import UserLogin

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
def admin_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == form_data.username).first()
    if not admin or not verify_password(form_data.password, admin.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(admin.id), "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/user-login", response_model=Token)
def user_login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == credentials.phone_number.strip()).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")

    # ATM lockout: 3 wrong password attempts at the ATM locks the card for
    # 15 minutes AND blocks login for that same window - checked here so a
    # locked customer can't just log back in and try the ATM again immediately.
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining_seconds = (user.locked_until - datetime.utcnow()).total_seconds()
        remaining_minutes = int(remaining_seconds // 60) + 1
        raise HTTPException(
            status_code=403,
            detail=f"Account locked due to too many failed ATM attempts. "
                   f"Try again in {remaining_minutes} minute(s).",
        )

    token = create_access_token({"sub": str(user.id), "role": "user"})
    return {"access_token": token, "token_type": "bearer"}