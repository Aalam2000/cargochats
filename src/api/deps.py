from __future__ import annotations

import time
from typing import TypedDict

import jwt
from fastapi import Header, HTTPException, Query, Request

from src.config import get_settings


class CompanyContext(TypedDict):
    company_id: int
    user_id: int


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_company_from_token(
    request: Request,
    token: str | None = Query(default=None),
) -> CompanyContext:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.CARGOCHATS_JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    company_id = payload.get("company_id")
    user_id = payload.get("user_id")
    expires_at = payload.get("expires_at")

    if not company_id or not user_id or not expires_at:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    if expires_at < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    request.state.company_id = company_id
    request.state.user_id = user_id

    return {
        "company_id": company_id,
        "user_id": user_id,
    }
