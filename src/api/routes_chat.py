from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select

from src.api.deps import require_api_key
from src.storage.db import get_db
from src.models.resource import Resource, ResourceSettings
from src.core.chat_engine import generate_reply

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    text: str
    client_external_id: str | None = None
    resource: str | None = None   # ожидаем: Resource.id (число) ИЛИ Resource.code
    session: str | None = None    # пока не используем


class ChatOut(BaseModel):
    reply: str


async def _resolve_resource(db, resource_ref: str) -> Resource | None:
    ref = (resource_ref or "").strip()
    if not ref:
        return None

    if ref.isdigit():
        stmt = select(Resource).where(Resource.id == int(ref))
    else:
        stmt = select(Resource).where(Resource.code == ref)

    res = await db.execute(stmt.limit(1))
    return res.scalar_one_or_none()


async def _get_resource_refs(db, resource_id: int) -> tuple[int | None, int | None]:
    res = await db.execute(
        select(ResourceSettings.data).where(ResourceSettings.resource_id == resource_id).limit(1)
    )
    data = res.scalar_one_or_none() or {}
    if not isinstance(data, dict):
        return None, None

    def _as_int(v) -> int | None:
        try:
            return int(v) if v else None
        except Exception:
            return None

    return _as_int(data.get("openai_resource_id")), _as_int(data.get("prompt_resource_id"))


@router.post("", response_model=ChatOut, dependencies=[Depends(require_api_key)])
async def chat(inp: ChatIn, db=Depends(get_db)):
    text = (inp.text or "").strip()
    if not text:
        return ChatOut(reply="Пустой текст.")

    resource_ref = (inp.resource or "").strip()
    if not resource_ref:
        return ChatOut(reply="Не задан resource (нужен Resource.id или Resource.code).")

    resource = await _resolve_resource(db, resource_ref)
    if not resource:
        return ChatOut(reply="Ресурс не найден.")

    openai_resource_id, prompt_resource_id = await _get_resource_refs(db, resource.id)

    reply = await generate_reply(
        db,
        company_id=int(resource.company_id),
        openai_resource_id=openai_resource_id,
        prompt_resource_id=prompt_resource_id,
        user_text=text,
    )
    return ChatOut(reply=reply)
