"""
PATH: src/api/ui/resources.py
PURPOSE: UI pages for Resources: list/create/detail (Tilda/Telegram/etc). Keep it lean: one file per section.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_list(request: Request, company_id: int):
    # TODO: load resources from DB by company_id
    return templates.TemplateResponse(
        "ui/resources.html",
        {"request": request, "company_id": company_id, "items": []},
    )


@router.get("/resources/{resource_id}", response_class=HTMLResponse)
async def resource_detail(request: Request, company_id: int, resource_id: int):
    # TODO: load resource + settings; show token/snippet; enable/disable
    return templates.TemplateResponse(
        "ui/resource_detail.html",
        {"request": request, "company_id": company_id, "resource_id": resource_id},
    )
