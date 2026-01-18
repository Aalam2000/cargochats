"""
PATH: src/api/ui/dialogs.py
PURPOSE: UI pages for Dialogs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.deps import require_company_from_token

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/dialogs", response_class=HTMLResponse)
async def dialogs_list(
    request: Request,
    _ctx=Depends(require_company_from_token),
):
    company_id = request.state.company_id

    return templates.TemplateResponse(
        "ui/dialogs.html",
        {
            "request": request,
            "company_id": company_id,
            "items": [],
        },
    )


@router.get("/dialogs/{dialog_id}", response_class=HTMLResponse)
async def dialog_detail(
    request: Request,
    dialog_id: int,
    _ctx=Depends(require_company_from_token),
):
    company_id = request.state.company_id

    return templates.TemplateResponse(
        "ui/dialog_detail.html",
        {
            "request": request,
            "company_id": company_id,
            "dialog_id": dialog_id,
            "messages": [],
        },
    )
