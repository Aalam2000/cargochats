from __future__ import annotations

import time
import jwt

from fastapi import Request, HTTPException, Header, Query, Depends
from sqlalchemy import select

from src.config import get_settings
from src.storage.db import get_db
from src.models.company import Company


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def require_company_from_token(
    request: Request,
    token: str | None = Query(default=None),
    db=Depends(get_db),
):
    settings = get_settings()

    # =========================
    # DEV MODE
    # =========================
    if settings.ENV == "dev":
        company_id = 1
        user_id = 1

        result = await db.execute(
            select(Company).where(Company.id == company_id)
        )
        company = result.scalar_one_or_none()

        if not company:
            company = Company(
                id=company_id,
                name="DEV COMPANY",
                cargo1_company_id=None,
                is_enabled=True,
            )
            db.add(company)
            await db.commit()

        request.state.company_id = company_id
        request.state.user_id = user_id
        return

    # =========================
    # PROD MODE
    # =========================
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

    expires_at = payload.get("expires_at")
    if not expires_at or expires_at < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")

    company_id = payload.get("company_id")
    user_id = payload.get("user_id")

    if not company_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()

    if not company:
        company = Company(
            id=company_id,
            name=f"Company {company_id}",
            cargo1_company_id=company_id,
            is_enabled=True,
        )
        db.add(company)
        await db.commit()

    request.state.company_id = company_id
    request.state.user_id = user_id
