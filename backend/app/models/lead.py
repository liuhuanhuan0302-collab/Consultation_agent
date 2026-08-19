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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submissions: Mapped[list["DiagnosisSubmission"]] = relationship(back_populates="lead")
