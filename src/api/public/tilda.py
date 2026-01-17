"""
PATH: src/api/public/tilda.py
PURPOSE:
- POST /public/tilda/chat: validates widget_token, resolves resource/client/dialog, writes messages, returns LLM reply
- GET  /public/tilda/history: returns dialog messages for widget_token + external_client_id
- POST /public/tilda/clear: soft-deletes dialog messages for widget_token + external_client_id
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.db import get_db
from src.models import (
    Resource,
    ResourceSettings,
    Client,
    ClientIdentity,
    Dialog,
    Message,
)

router = APIRouter(prefix="/tilda")

_openai = AsyncOpenAI()


# ---------- Pydantic схемы ----------

class TildaChatIn(BaseModel):
    widget_token: str = Field(min_length=1)
    external_client_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class TildaChatOut(BaseModel):
    reply: str
    dialog_id: int


class HistoryItem(BaseModel):
    id: int
    direction: str
    text: str | None
    created_at: datetime


class TildaHistoryOut(BaseModel):
    dialog_id: int
    items: list[HistoryItem]


class TildaClearIn(BaseModel):
    widget_token: str = Field(min_length=1)
    external_client_id: str = Field(min_length=1)


class TildaClearOut(BaseModel):
    ok: bool
    dialog_id: int
    deleted: int


# ---------- helpers ----------

async def _resolve_resource(db: AsyncSession, widget_token: str) -> tuple[Resource, ResourceSettings]:
    stmt = (
        select(Resource, ResourceSettings)
        .join(ResourceSettings, ResourceSettings.resource_id == Resource.id)
        .where(
            Resource.kind == "tilda",
            Resource.is_enabled.is_(True),
            ResourceSettings.is_enabled.is_(True),
            ResourceSettings.data["widget_token"].astext == widget_token,
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Unknown widget_token (resource not found)")
    resource, settings = row
    return resource, settings


async def _resolve_or_create_client(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    external_client_id: str,
) -> Client:
    # 1) try identity
    stmt = (
        select(Client)
        .join(ClientIdentity, ClientIdentity.client_id == Client.id)
        .where(
            Client.company_id == company_id,
            Client.is_enabled.is_(True),
            ClientIdentity.resource_id == resource_id,
            ClientIdentity.kind == "tilda",
            ClientIdentity.external_id == external_client_id,
            ClientIdentity.is_enabled.is_(True),
        )
        .limit(1)
    )
    client = (await db.execute(stmt)).scalar_one_or_none()
    if client:
        return client

    # 2) create client + identity
    client_code = external_client_id[:64]  # Client.code ограничен 64
    client = Client(company_id=company_id, code=client_code, meta={"source": "tilda"})
    db.add(client)
    await db.flush()  # получить client.id

    identity = ClientIdentity(
        client_id=client.id,
        resource_id=resource_id,
        external_id=external_client_id,
        kind="tilda",
        meta={},
    )
    db.add(identity)
    await db.flush()

    return client


async def _resolve_or_create_dialog(db: AsyncSession, *, company_id: int, client_id: int, resource_id: int) -> Dialog:
    stmt = (
        select(Dialog)
        .where(
            Dialog.company_id == company_id,
            Dialog.client_id == client_id,
            Dialog.status == "open",
            Dialog.is_enabled.is_(True),
        )
        .order_by(Dialog.created_at.desc())
        .limit(1)
    )
    dialog = (await db.execute(stmt)).scalar_one_or_none()
    if dialog:
        return dialog

    dialog = Dialog(company_id=company_id, client_id=client_id, meta={"resource_id": resource_id})
    db.add(dialog)
    await db.flush()
    return dialog


def _settings_get(settings: ResourceSettings, key: str, default: Any = None) -> Any:
    if not settings or not isinstance(settings.data, dict):
        return default
    return settings.data.get(key, default)


async def _call_openai(*, settings: ResourceSettings, text: str) -> str:
    model = _settings_get(settings, "model") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    system_prompt = _settings_get(settings, "system_prompt") or os.getenv("OPENAI_SYSTEM_PROMPT")

    # MVP: без “структурированной истории”, просто prompt + текущий текст.
    if system_prompt:
        prompt = f"{system_prompt}\n\nUSER:\n{text}"
    else:
        prompt = text

    resp = await _openai.responses.create(
        model=model,
        input=prompt,
    )
    reply = (resp.output_text or "").strip()
    if not reply:
        reply = "Не получил текст ответа от модели."
    return reply


# ---------- endpoints ----------

@router.post("/chat", response_model=TildaChatOut)
async def tilda_chat(inp: TildaChatIn, db: AsyncSession = Depends(get_db)) -> TildaChatOut:
    resource, rset = await _resolve_resource(db, inp.widget_token)

    client = await _resolve_or_create_client(
        db,
        company_id=resource.company_id,
        resource_id=resource.id,
        external_client_id=inp.external_client_id,
    )

    dialog = await _resolve_or_create_dialog(
        db,
        company_id=resource.company_id,
        client_id=client.id,
        resource_id=resource.id,
    )

    # inbound message (фиксируем сразу)
    msg_in = Message(
        dialog_id=dialog.id,
        direction="in",
        text=inp.text,
        resource_id=resource.id,
        session_id=None,
        meta={"external_client_id": inp.external_client_id},
    )
    db.add(msg_in)
    await db.commit()

    # LLM
    try:
        reply = await _call_openai(settings=rset, text=inp.text)
    except Exception as e:
        # если LLM упал — оставляем входящее сообщение сохранённым
        raise HTTPException(status_code=502, detail=f"LLM error: {type(e).__name__}: {e}") from e

    # outbound message
    msg_out = Message(
        dialog_id=dialog.id,
        direction="out",
        text=reply,
        resource_id=resource.id,
        session_id=None,
        meta={},
    )
    db.add(msg_out)
    await db.commit()

    return TildaChatOut(reply=reply, dialog_id=dialog.id)


@router.get("/history", response_model=TildaHistoryOut)
async def tilda_history(widget_token: str, external_client_id: str, db: AsyncSession = Depends(get_db)) -> TildaHistoryOut:
    resource, _ = await _resolve_resource(db, widget_token)

    client = await _resolve_or_create_client(
        db,
        company_id=resource.company_id,
        resource_id=resource.id,
        external_client_id=external_client_id,
    )

    dialog = await _resolve_or_create_dialog(
        db,
        company_id=resource.company_id,
        client_id=client.id,
        resource_id=resource.id,
    )

    stmt = (
        select(Message)
        .where(Message.dialog_id == dialog.id, Message.is_deleted.is_(False))
        .order_by(Message.created_at.asc())
        .limit(200)
    )
    msgs = (await db.execute(stmt)).scalars().all()

    items = [
        HistoryItem(id=m.id, direction=m.direction, text=m.text, created_at=m.created_at)
        for m in msgs
    ]
    return TildaHistoryOut(dialog_id=dialog.id, items=items)


@router.post("/clear", response_model=TildaClearOut)
async def tilda_clear(inp: TildaClearIn, db: AsyncSession = Depends(get_db)) -> TildaClearOut:
    resource, _ = await _resolve_resource(db, inp.widget_token)

    client = await _resolve_or_create_client(
        db,
        company_id=resource.company_id,
        resource_id=resource.id,
        external_client_id=inp.external_client_id,
    )

    dialog = await _resolve_or_create_dialog(
        db,
        company_id=resource.company_id,
        client_id=client.id,
        resource_id=resource.id,
    )

    stmt = (
        update(Message)
        .where(Message.dialog_id == dialog.id, Message.is_deleted.is_(False))
        .values(is_deleted=True)
    )
    res = await db.execute(stmt)
    await db.commit()

    # res.rowcount может быть None в некоторых режимах — приводим к int безопасно
    deleted = int(res.rowcount or 0)
    return TildaClearOut(ok=True, dialog_id=dialog.id, deleted=deleted)
