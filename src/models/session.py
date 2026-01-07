from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("resource_id", "code", name="uq_sessions_resource_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)

    # код/алиас сессии (telegram_account_1 и т.п.)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class SessionSettings(Base, TimestampMixin):
    __tablename__ = "session_settings"
    __table_args__ = (UniqueConstraint("session_id", name="uq_session_settings_session"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
