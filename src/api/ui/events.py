"""
PATH: src/api/ui/events.py
PURPOSE: UI page for Events.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.deps import require_company_from_token

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/events", response_class=HTMLResponse)
async def events_list(
    request: Request,
    _ctx=Depends(require_company_from_token),
):
    company_id = request.state.company_id

    return templates.TemplateResponse(
        "ui/events.html",
        {
            "request": request,
            "company_id": company_id,
            "items": [],
        },
    )
