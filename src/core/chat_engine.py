from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.openai_client import call_openai_text
from src.models.resource import Resource, ResourceSettings
from src.resources.openai import get_openai_api_key
from src.storage.messages import load_history


def get_default_model() -> str:
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"


async def _get_history_pairs(
    db: AsyncSession,
    *,
    company_id: int,
    prompt_resource_id: int | None,
) -> int:
    if not prompt_resource_id:
        return 0

    stmt = (
        select(ResourceSettings.data)
        .select_from(Resource)
        .join(ResourceSettings, ResourceSettings.resource_id == Resource.id, isouter=True)
        .where(
            Resource.company_id == int(company_id),
            Resource.id == int(prompt_resource_id),
            Resource.kind == "prompt",
            Resource.is_enabled.is_(True),
        )
        .limit(1)
    )
    data = (await db.execute(stmt)).scalar_one_or_none() or {}
    if not isinstance(data, dict):
        return 0

    hp = data.get("history_pairs")
    try:
        n = int(hp)
    except Exception:
        return 0
    if n < 0:
        return 0
    if n > 50:
        n = 50
    return n


async def generate_reply(
    db: AsyncSession,
    *,
    company_id: int,
    openai_resource_id: int | None,
    user_text: str,
    # шаг №2 (история)
    prompt_resource_id: int | None = None,
    resource_id: int | None = None,
    session_id: int | None = None,
    chat_id: int | None = None,
    current_in_message_id: int | None = None,
) -> str:
    text = (user_text or "").strip()
    if not text:
        return "Пустой текст."

    if not openai_resource_id:
        return "OpenAI не настроен: выбери OpenAI-ресурс в настройках Telegram."

    api_key = await get_openai_api_key(
        db,
        company_id=int(company_id),
        openai_resource_id=int(openai_resource_id),
    )
    if not api_key:
        return "OpenAI не настроен: ключ не найден или ресурс отключён."

    model = get_default_model()

    n_pairs = await _get_history_pairs(db, company_id=int(company_id), prompt_resource_id=prompt_resource_id)
    limit_messages = int(n_pairs) * 2

    input_items: list[dict] = []

    # История только если есть весь ключ (resource_id + chat_id); session_id может быть None
    if limit_messages > 0 and resource_id and chat_id:
        msgs = await load_history(
            db,
            company_id=int(company_id),
            resource_id=int(resource_id),
            session_id=session_id,
            chat_id=int(chat_id),
            limit_messages=limit_messages,
            exclude_message_id=current_in_message_id,
        )

        for m in msgs:
            if not m.text:
                continue
            role = "user" if m.direction == "in" else "assistant"
            input_items.append({"role": role, "content": m.text})

        # лёгкая нормализация до пар
        if len(input_items) % 2 == 1:
            input_items = input_items[1:]
        if input_items and input_items[0].get("role") == "assistant":
            input_items = input_items[1:]
        if len(input_items) > limit_messages:
            input_items = input_items[-limit_messages:]

    # текущий ввод всегда в конец
    input_items.append({"role": "user", "content": text})

    reply = await call_openai_text(api_key=api_key, model=model, input_items=input_items)
    reply = (reply or "").strip()
    return reply or "Пустой ответ от модели."
