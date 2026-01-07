"""
PATH: src/api/ui/dialogs.py
PURPOSE: UI pages for Dialogs: list and viewer (messages feed).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/dialogs", response_class=HTMLResponse)
async def dialogs_list(request: Request, company_id: int):
    # TODO: load dialogs list by company_id
    return templates.TemplateResponse(
        "ui/dialogs.html",
        {"request": request, "company_id": company_id, "items": []},
    )


@router.get("/dialogs/{dialog_id}", response_class=HTMLResponse)
async def dialog_detail(request: Request, company_id: int, dialog_id: int):
    # TODO: load dialog + messages
    return templates.TemplateResponse(
        "ui/dialog_detail.html",
        {"request": request, "company_id": company_id, "dialog_id": dialog_id, "messages": []},
    )
