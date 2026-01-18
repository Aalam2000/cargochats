"""
PATH: src/api/ui/resources.py
PURPOSE: UI pages for Resources: list/create/detail (Tilda/Telegram/etc).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from src.api.deps import require_company_from_token
from src.models.resource import Resource
from src.storage.db import get_db

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_list(
    request: Request,
    _ctx=Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    result = await db.execute(
        select(Resource)
        .where(Resource.company_id == company_id)
        .order_by(Resource.id)
    )
    items = result.scalars().all()

    return templates.TemplateResponse(
        "ui/resources.html",
        {
            "request": request,
            "company_id": company_id,
            "items": items,
        },
    )
