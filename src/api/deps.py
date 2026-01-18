from __future__ import annotations

import time
from typing import TypedDict

import jwt
from fastapi import Header, HTTPException, Query, Request, Response

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
    response: Response,
    token: str | None = Query(default=None),
) -> CompanyContext:
    """
    Логика:
    1. Если token пришёл в URL — используем его и кладём в cookie
    2. Если token нет в URL — пробуем взять из cookie
    3. Если нигде нет — 401
    """

    settings = get_settings()

    jwt_token = token or request.cookies.get("cargochats_token")
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt.decode(
            jwt_token,
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

    # кладём в state
    request.state.company_id = company_id
    request.state.user_id = user_id

    # если токен пришёл из URL — сохраняем в cookie
    if token:
        response.set_cookie(
            key="cargochats_token",
            value=jwt_token,
            httponly=True,
            samesite="lax",
            secure=True,
        )

    return {
        "company_id": company_id,
        "user_id": user_id,
    }
