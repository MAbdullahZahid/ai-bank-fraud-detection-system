"""
Shared auth dependencies. Admin and User are separate identities with
separate JWTs (each token carries a "role" claim) - a user token can never
be used to access admin routes and vice versa.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.user import User
from app.services.auth_service import decode_access_token

oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl="/api/auth/user-login")


def get_current_admin(token: str = Depends(oauth2_scheme_admin), db: Session = Depends(get_db)) -> Admin:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired admin session. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("role") != "admin":
            raise exc
        admin_id = payload.get("sub")
        if admin_id is None:
            raise exc
    except JWTError:
        raise exc

    admin = db.query(Admin).filter(Admin.id == int(admin_id)).first()
    if admin is None:
        raise exc
    return admin


def get_current_user(token: str = Depends(oauth2_scheme_user), db: Session = Depends(get_db)) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("role") != "user":
            raise exc
        user_id = payload.get("sub")
        if user_id is None:
            raise exc
    except JWTError:
        raise exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise exc
    return user
