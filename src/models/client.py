from __future__ import annotations

from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class Client(Base, TimestampMixin):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_clients_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # внутренний код клиента (можно UUID позже; сейчас строка)
    code: Mapped[str] = mapped_column(String(64), nullable=False)

    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class ClientIdentity(Base, TimestampMixin):
    __tablename__ = "client_identities"
    __table_args__ = (
        UniqueConstraint("resource_id", "external_id", name="uq_client_identities_resource_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)

    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)

    # tg_user_id / tilda_chat_id / phone / email / etc (строкой)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # tg / tilda / phone / email

    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
