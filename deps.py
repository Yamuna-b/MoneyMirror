"""FastAPI dependencies: DB session and current user."""
from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal, User
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    cfg = get_settings()
    cred_ex = HTTPException(
        status_code=401,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, cfg.secret_key, algorithms=["HS256"])
        email: str = payload.get("sub")
        if not email:
            raise cred_ex
    except JWTError:
        raise cred_ex
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise cred_ex
    return user
