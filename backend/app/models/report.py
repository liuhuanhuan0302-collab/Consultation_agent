"""Generated report, AI conversation and delivery models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.common import now, token


class ReportStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    generated = "generated"
    fallback = "fallback"
    failed = "failed"


class ReportDeliveryStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    sent = "sent"
    failed = "failed"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), unique=True, index=True)
    public_token: Mapped[str] = mapped_column(String(64), default=token, unique=True, index=True)
    status: Mapped[ReportStatus] = mapped_column(String(32), default=ReportStatus.pending.value)
    title: Mapped[str] = mapped_column(String(255))
    html_content: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[str | None] = mapped_column(Text)
    company_research_json: Mapped[str | None] = mapped_column(Text)
    model_vendor: Mapped[str] = mapped_column(String(80), default="deepseek")
    model_name: Mapped[str | None] = mapped_column(String(120))
    generation_error: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submission: Mapped["DiagnosisSubmission"] = relationship(back_populates="report")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class AiConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("company_leads.id"), index=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(80), default="report_advisor", index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    model_vendor: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ReportDeliveryJob(Base):
    __tablename__ = "report_delivery_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("company_leads.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("diagnosis_submissions.id"), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[ReportDeliveryStatus] = mapped_column(
        String(32),
        default=ReportDeliveryStatus.queued.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    lead: Mapped["CompanyLead"] = relationship()
    submission: Mapped["DiagnosisSubmission"] = relationship()
    report: Mapped[Report] = relationship()


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("case_studies.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    priority_score: Mapped[int] = mapped_column(Integer, default=50)

    report: Mapped[Report] = relationship(back_populates="recommendations")
    case: Mapped["CaseStudy | None"] = relationship()


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    content: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
