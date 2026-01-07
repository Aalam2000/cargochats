from __future__ import annotations

from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.db import Base
from ._mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # внешний пользователь Cargo1
    cargo1_user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    email: Mapped[str | None] = mapped_column(String(254), nullable=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
