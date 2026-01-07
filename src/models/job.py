from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # inbound/outbound/retention/service
    queue: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="new")  # new/running/done/failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


Index("ix_jobs_company_queue_status", Job.company_id, Job.queue, Job.status)
