"""
PATH: src/api/ui/events.py
PURPOSE: UI page for Events: technical events/errors/statuses viewer with lightweight filters.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/events", response_class=HTMLResponse)
async def events_list(request: Request, company_id: int):
    # TODO: load events by company_id (+ optional filters later)
    return templates.TemplateResponse(
        "ui/events.html",
        {"request": request, "company_id": company_id, "items": []},
    )
