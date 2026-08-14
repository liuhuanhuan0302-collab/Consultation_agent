"""Consulting case library models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.common import now


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(120), index=True)
    function_area: Mapped[str] = mapped_column(String(120), index=True)
    module_code: Mapped[str] = mapped_column(String(40), index=True)
    maturity: Mapped[str] = mapped_column(String(80), default="MVP")
    roi_level: Mapped[str] = mapped_column(String(40), default="medium")
    difficulty: Mapped[str] = mapped_column(String(40), default="medium")
    description: Mapped[str] = mapped_column(Text)
    expected_benefit: Mapped[str] = mapped_column(Text)
    priority_tag: Mapped[str] = mapped_column(String(40), default="攻坚战")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
