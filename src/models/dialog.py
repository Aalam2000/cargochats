from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Dialog(Base, TimestampMixin):
    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="open")  # open/closed/archived
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


Index("ix_dialogs_company_client", Dialog.company_id, Dialog.client_id)
