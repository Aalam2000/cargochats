from __future__ import annotations

import os
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def build_db_url() -> str:
    host = os.getenv("DB_HOST", "postgres")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "cargochats")
    user = os.getenv("DB_USER", "cargochats")
    password = os.getenv("DB_PASSWORD", "cargochats")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def get_engine() -> AsyncEngine:
    return create_async_engine(build_db_url(), pool_pre_ping=True)


async_session_factory = sessionmaker(
    bind=get_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
)
