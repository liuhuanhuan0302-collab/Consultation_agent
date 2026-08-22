"""Tracking, export and operation audit models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str | None] = mapped_column(String(64), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("company_leads.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(120), index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ExportLog(Base):
    __tablename__ = "export_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    export_type: Mapped[str] = mapped_column(String(80))
    filters_json: Mapped[str | None] = mapped_column(Text)
    rows_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str | None] = mapped_column(String(120))
    target_id: Mapped[str | None] = mapped_column(String(120))
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
