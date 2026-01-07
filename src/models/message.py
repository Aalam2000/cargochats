from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id", ondelete="CASCADE"), nullable=False, index=True)

    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in/out
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


Index("ix_messages_dialog_created", Message.dialog_id, Message.created_at)
