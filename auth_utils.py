"""Password hashing and JWT helpers."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import bcrypt as _bcrypt
from jose import jwt

from config import get_settings


def hash_password(pw: str) -> str:
    pw_bytes = pw.encode("utf-8")[:72]
    salt = _bcrypt.gensalt(rounds=12)
    return _bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        pw_bytes = pw.encode("utf-8")[:72]
        return _bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password(pw: str) -> str | None:
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    if len(pw.encode("utf-8")) > 72:
        return "Password is too long (max 72 characters)."
    if not re.search(r"[A-Za-z]", pw):
        return "Password must contain at least one letter."
    if not re.search(r"[0-9]", pw):
        return "Password must contain at least one number."
    return None


def create_token(data: dict) -> str:
    cfg = get_settings()
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=cfg.access_token_expire_minutes)
    return jwt.encode(to_encode, cfg.secret_key, algorithm="HS256")
