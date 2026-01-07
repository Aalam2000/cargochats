from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Resource(Base, TimestampMixin):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_resources_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # tilda / telegram / etc
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # уникальный код/алиас ресурса внутри компании
    code: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class ResourceSettings(Base, TimestampMixin):
    __tablename__ = "resource_settings"
    __table_args__ = (UniqueConstraint("resource_id", name="uq_resource_settings_resource"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)

    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
