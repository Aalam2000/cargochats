from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # применимость: на resource или session (оба nullable, но хотя бы один будет задан)
    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


Index("ix_policies_company_priority", Policy.company_id, Policy.priority)
