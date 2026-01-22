from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resource import Resource, ResourceSettings

OPENAI_KEY_FIELD = "openai_api_key"


async def get_openai_api_key(
    db: AsyncSession,
    *,
    company_id: int,
    openai_resource_id: int,
) -> str | None:
    """
    Возвращает OpenAI api_key из ResourceSettings.data выбранного OpenAI-ресурса.
    Защищаемся по company_id + kind=openai + is_enabled.
    """
    stmt = (
        select(ResourceSettings.data)
        .select_from(Resource)
        .join(ResourceSettings, ResourceSettings.resource_id == Resource.id, isouter=True)
        .where(
            Resource.company_id == company_id,
            Resource.id == openai_resource_id,
            Resource.kind == "openai",
            Resource.is_enabled.is_(True),
        )
        .limit(1)
    )

    result = await db.execute(stmt)
    data = result.scalar_one_or_none() or {}
    if not isinstance(data, dict):
        return None

    api_key = (data.get(OPENAI_KEY_FIELD) or "").strip()
    return api_key or None
