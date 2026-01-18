from __future__ import annotations

from fastapi import APIRouter

from .resources import router as resources_router
from .sessions import router as sessions_router
from .dialogs import router as dialogs_router
from .events import router as events_router
from .widget_test import router as widget_test_router

router = APIRouter(prefix="/ui", tags=["ui"])

# HTML / UI
router.include_router(resources_router)
router.include_router(sessions_router)
router.include_router(dialogs_router)
router.include_router(events_router)
router.include_router(widget_test_router)
