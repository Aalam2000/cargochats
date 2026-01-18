from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
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
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    # 🔴 ВОТ ЗДЕСЬ — ЕДИНСТВЕННО ВЕРНОЕ МЕСТО
    if "token" in request.query_params:
        response = RedirectResponse(url="/ui/resources", status_code=302)
        response.set_cookie(
            key="cargochats_token",
            value=request.query_params["token"],
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return response

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
            "items": items,
        },
    )
