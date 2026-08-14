"""Runtime API gateway configuration model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class GatewayApiConfig(Base):
    __tablename__ = "gateway_api_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    search_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    search_provider: Mapped[str] = mapped_column(String(32), default="bocha")
    search_api_key: Mapped[str | None] = mapped_column(String(255))
    search_base_url: Mapped[str | None] = mapped_column(String(500))
    search_timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    search_max_results: Mapped[int] = mapped_column(Integer, default=20)
    search_model: Mapped[str | None] = mapped_column(String(120))
    llm_api_key: Mapped[str | None] = mapped_column(String(255))
    llm_base_url: Mapped[str | None] = mapped_column(String(500))
    llm_model: Mapped[str | None] = mapped_column(String(120))
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
