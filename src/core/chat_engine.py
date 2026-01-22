from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.openai_client import call_openai_text
from src.resources.openai import get_openai_api_key


def get_default_model() -> str:
    # Совместимо с тем, что у тебя уже есть в админке (по умолчанию gpt-4o-mini)
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"


async def generate_reply(
    db: AsyncSession,
    *,
    company_id: int,
    openai_resource_id: int | None,
    user_text: str,
) -> str:
    if not openai_resource_id:
        return "OpenAI не настроен: выбери OpenAI-ресурс в настройках Telegram."

    api_key = await get_openai_api_key(
        db,
        company_id=company_id,
        openai_resource_id=int(openai_resource_id),
    )
    if not api_key:
        return "OpenAI не настроен: ключ не найден или ресурс отключён."

    model = get_default_model()

    # Шаг 1: без истории и промптов (история будет в шаге 2, промпты в шаге 3)
    input_items = [
        {"role": "user", "content": user_text},
    ]

    text = await call_openai_text(api_key=api_key, model=model, input_items=input_items)
    return text or "Пустой ответ от модели."
