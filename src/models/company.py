from __future__ import annotations

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # связь с Cargo1 (tenant id в Cargo1)
    cargo1_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
