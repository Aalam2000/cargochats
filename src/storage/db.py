from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None


def build_db_url() -> str:
    host = os.getenv("DB_HOST", "postgres")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "cargochats")
    user = os.getenv("DB_USER", "cargochats")
    password = os.getenv("DB_PASSWORD", "cargochats")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def get_engine() -> AsyncEngine:
    """Singleton engine на процесс."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            build_db_url(),
            pool_pre_ping=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Singleton фабрика AsyncSession."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: db: AsyncSession = Depends(get_db)."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


async def db_ping() -> int:
    """Быстрый smoke-test подключения к БД."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        return int(result.scalar_one())
