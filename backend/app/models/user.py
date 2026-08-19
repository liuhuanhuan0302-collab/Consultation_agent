"""Back-office user models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class Role(str, Enum):
    admin = "admin"
    operator = "operator"
    sales = "sales"
    consultant = "consultant"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[Role] = mapped_column(String(32), default=Role.sales.value)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
