from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import require_api_key

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ping", dependencies=[Depends(require_api_key)])
async def ping():
    return {"status": "ok"}
