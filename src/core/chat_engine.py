from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.openai_client import call_openai_text
from src.resources.openai import get_openai_api_key
from src.resources.prompt import get_prompt_settings


def get_default_model() -> str:
    # Совместимо с тем, что у тебя уже есть в админке (по умолчанию gpt-4o-mini)
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"


async def generate_reply(
    db: AsyncSession,
    *,
    company_id: int,
    openai_resource_id: int | None,
    prompt_resource_id: int | None,
    user_text: str,
    history_messages: list[dict] | None = None,  # сюда позже подмешаем N*2 (user/assistant)
) -> str:
    if not openai_resource_id:
        return "OpenAI не настроен: выбери OpenAI-ресурс в настройках ресурса."

    if not prompt_resource_id:
        return "Prompt не настроен: выбери Prompt-ресурс в настройках ресурса."

    api_key = await get_openai_api_key(
        db,
        company_id=company_id,
        openai_resource_id=int(openai_resource_id),
    )
    if not api_key:
        return "OpenAI не настроен: ключ не найден или ресурс отключён."

    pset = await get_prompt_settings(
        db,
        company_id=company_id,
        prompt_resource_id=int(prompt_resource_id),
    )
    if pset is None:
        return "Prompt не настроен: Prompt-ресурс не найден или отключён."

    model = (str(pset.get("model") or "").strip()) or get_default_model()
    system_prompt = (str(pset.get("system_prompt") or "").strip())

    input_items: list[dict] = []
    if system_prompt:
        input_items.append({"role": "system", "content": system_prompt})

    if history_messages:
        input_items.extend(history_messages)

    input_items.append({"role": "user", "content": user_text})

    text = await call_openai_text(api_key=api_key, model=model, input_items=input_items)
    return text or "Пустой ответ от модели."
