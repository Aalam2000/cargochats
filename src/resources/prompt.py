from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resource import Resource, ResourceSettings


async def get_prompt_settings(
    db: AsyncSession,
    *,
    company_id: int,
    prompt_resource_id: int,
) -> dict | None:
    """
    Возвращает настройки Prompt из ResourceSettings.data выбранного Prompt-ресурса.
    Защита: company_id + kind=prompt + is_enabled.
    """
    stmt = (
        select(ResourceSettings.data)
        .select_from(Resource)
        .join(ResourceSettings, ResourceSettings.resource_id == Resource.id, isouter=True)
        .where(
            Resource.company_id == company_id,
            Resource.id == prompt_resource_id,
            Resource.kind == "prompt",
            Resource.is_enabled.is_(True),
        )
        .limit(1)
    )

    result = await db.execute(stmt)
    data = result.scalar_one_or_none()
    if data is None:
        return None
    if not isinstance(data, dict):
        return {}
    return data
