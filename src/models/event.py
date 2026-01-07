from __future__ import annotations

from sqlalchemy import Integer, String, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    level: Mapped[str] = mapped_column(String(16), nullable=False, server_default="info")  # info/warn/error
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)             # adapter/job/llm/etc
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    dialog_id: Mapped[int | None] = mapped_column(
        ForeignKey("dialogs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )

    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


Index("ix_events_company_created", Event.company_id, Event.created_at)
