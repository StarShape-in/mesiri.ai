"""Shared FastAPI auth dependencies for domain routers."""

from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException

from ..identity.auth_service import ALGORITHM, SECRET_KEY


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization[7:]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


async def require_admin(payload: dict = Depends(get_current_user)) -> dict:
    role = (payload.get("role") or "").upper()
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
