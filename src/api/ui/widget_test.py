"""
PATH: src/api/ui/widget_test.py
PURPOSE: UI test page that mimics Tilda widget behavior; useful for immediate manual checks.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/widget/test", response_class=HTMLResponse)
async def widget_test(request: Request, token: str, client: str = "test-client"):
    # token: widget_token from resource_settings (later)
    return templates.TemplateResponse(
        "ui/widget_test.html",
        {"request": request, "token": token, "client": client},
    )
