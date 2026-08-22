"""Customer lead models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.common import now, token


class CompanyLead(Base):
    __tablename__ = "company_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), default=token, unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    industry: Mapped[str | None] = mapped_column(String(120), index=True)
    company_size: Mapped[str | None] = mapped_column(String(80))
    annual_revenue: Mapped[str | None] = mapped_column(String(80))
    contact_name: Mapped[str | None] = mapped_column(String(80))
    position: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    wechat: Mapped[str | None] = mapped_column(String(80))
    ai_focus: Mapped[str | None] = mapped_column(Text)
    privacy_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    source_code: Mapped[str | None] = mapped_column(String(80), index=True)
    lead_level: Mapped[str] = mapped_column(String(40), default="low", index=True)
    priority_strategy: Mapped[str | None] = mapped_column(String(40), index=True)
    demand_summary: Mapped[str | None] = mapped_column(Text)
    # 三维跟踪状态：查看 / 处理 / 导出 互不影响。
    # 处理状态由 lead_status.sync_lead_processing_status 在流水线各转换点统一维护。
    view_status: Mapped[str] = mapped_column(String(20), default="unviewed", server_default="unviewed", index=True)
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    first_viewed_by: Mapped[str | None] = mapped_column(String(120))
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    processing_note: Mapped[str | None] = mapped_column(Text)
    export_status: Mapped[str] = mapped_column(String(20), default="unexported", server_default="unexported", index=True)
    first_exported_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_exported_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submissions: Mapped[list["DiagnosisSubmission"]] = relationship(back_populates="lead")
