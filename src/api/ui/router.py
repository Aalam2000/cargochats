from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .dialogs import router as dialogs_router
from .events import router as events_router
from .resources import router as resources_router
from .sessions import router as sessions_router
from .widget_test import router as widget_test_router

router = APIRouter(prefix="/ui", tags=["ui"])

templates = Jinja2Templates(directory="src/web/templates")


# ---------- HTML страницы ----------

@router.get("/resources", response_class=HTMLResponse)
def resources_page(request: Request):
    return templates.TemplateResponse(
        "ui/resources.html",
        {"request": request},
    )


# ---------- API / вложенные роуты ----------

router.include_router(resources_router, prefix="/resources")
router.include_router(sessions_router)
router.include_router(dialogs_router)
router.include_router(events_router)
router.include_router(widget_test_router)
