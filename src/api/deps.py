from __future__ import annotations

import time
import jwt
from fastapi import Request, HTTPException, Query

from src.config import get_settings


def require_company_from_token(
    request: Request,
    token: str | None = Query(default=None),
):
    jwt_token = token or request.cookies.get("cargochats_token")
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Missing token")

    settings = get_settings()

    try:
        payload = jwt.decode(
            jwt_token,
            settings.CARGOCHATS_JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    expires_at = payload.get("expires_at")
    if not expires_at or expires_at < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    request.state.company_id = payload["company_id"]
    request.state.user_id = payload["user_id"]
