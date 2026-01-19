from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, delete

from src.api.deps import require_company_from_token
from src.models.resource import Resource, ResourceSettings
from src.storage.db import get_db

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_list(
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    # 🔴 если первый заход с token — чистим URL
    token = request.query_params.get("token")
    if token:
        response = RedirectResponse(url="/ui/resources", status_code=302)
        response.set_cookie(
            key="cargochats_token",
            value=str(token),
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


@router.post("/resources")
async def resource_create(
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    data = await request.json()
    kind = data.get("kind")

    if kind not in ("openai", "telegram", "web"):
        raise HTTPException(status_code=400, detail="Invalid resource kind")

    company_id = request.state.company_id

    resource = Resource(
        company_id=company_id,
        kind=kind,
        code=str(uuid4()),  # техническое поле, не используем
    )
    db.add(resource)
    await db.flush()

    db.add(ResourceSettings(resource_id=resource.id))
    await db.commit()

    return JSONResponse({"id": resource.id})


@router.delete("/resources/{resource_id}")
async def resource_delete(
    resource_id: int,
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    await db.execute(
        delete(Resource)
        .where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    await db.commit()

    return JSONResponse({"status": "ok"})
