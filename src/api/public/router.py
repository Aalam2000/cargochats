"""
PATH: src/api/public/router.py
PURPOSE: Public router aggregator. Mounts endpoints under /public/* (no UI).
"""

from __future__ import annotations

from fastapi import APIRouter

from .tilda import router as tilda_router

router = APIRouter(prefix="/public", tags=["public"])
router.include_router(tilda_router)
