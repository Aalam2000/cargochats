"""
PATH: src/api/ui/sessions.py
PURPOSE: UI pages for Sessions: list/create/detail for a resource (e.g., Telegram accounts).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/resources/{resource_id}/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request, company_id: int, resource_id: int):
    # TODO: load sessions by resource_id
    return templates.TemplateResponse(
        "ui/sessions.html",
        {"request": request, "company_id": company_id, "resource_id": resource_id, "items": []},
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, company_id: int, session_id: int):
    # TODO: load session + settings; enable/disable
    return templates.TemplateResponse(
        "ui/session_detail.html",
        {"request": request, "company_id": company_id, "session_id": session_id},
    )
