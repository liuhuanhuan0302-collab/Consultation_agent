"""Independent organization-diagnosis analysis and PDF models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.common import now


class OrganizationAnalysisStatus(str, Enum):
    """The analysis state shown to administrators for one organization submission."""

    not_eligible = "not_eligible"
    waiting_manual = "waiting_manual"
    queued = "queued"
    processing = "processing"
    generated = "generated"
    failed = "failed"


class OrganizationReportStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    generated = "generated"
    failed = "failed"


class OrganizationReportTaskKind(str, Enum):
    automatic = "automatic"
    manual = "manual"


class OrganizationReportTaskStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    succeeded = "succeeded"
    failed = "failed"


class OrganizationReport(Base):
    """One immutable successful/failed generation attempt for a submission."""

    __tablename__ = "organization_reports"
    __table_args__ = (
        UniqueConstraint(
            "organization_submission_id",
            "version",
            name="uq_organization_report_submission_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_submission_id: Mapped[int] = mapped_column(
        ForeignKey("organization_submissions.id", ondelete="CASCADE"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[OrganizationReportStatus] = mapped_column(
        String(32),
        default=OrganizationReportStatus.pending.value,
        server_default=OrganizationReportStatus.pending.value,
        index=True,
    )
    report_format_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    title: Mapped[str] = mapped_column(String(255))
    summary_json: Mapped[str | None] = mapped_column(Text)
    analysis_json: Mapped[str | None] = mapped_column(Text)
    # The rendered organization report contains the complete multi-page HTML
    # document.  MySQL TEXT is limited to 64 KiB, which is too small for a
    # report with all module tables and insight pages.  Keep Text for SQLite
    # and other dialects, but use MEDIUMTEXT on MySQL (up to 16 MiB).
    html_content: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    pdf_content: Mapped[bytes | None] = mapped_column(LargeBinary(length=16_777_215))
    source_enterprise_report_id: Mapped[int | None] = mapped_column(Integer, index=True)
    model_vendor: Mapped[str] = mapped_column(String(80), default="deepseek", server_default="deepseek")
    model_name: Mapped[str | None] = mapped_column(String(120))
    generation_error: Mapped[str | None] = mapped_column(Text)
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    generation_completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submission: Mapped["OrganizationSubmission"] = relationship(back_populates="reports")
    tasks: Mapped[list["OrganizationReportTask"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )


class OrganizationReportTask(Base):
    """Independent async task; it never enters the enterprise report queue."""

    __tablename__ = "organization_report_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_submission_id: Mapped[int] = mapped_column(
        ForeignKey("organization_submissions.id", ondelete="CASCADE"),
        index=True,
    )
    organization_report_id: Mapped[int] = mapped_column(
        ForeignKey("organization_reports.id", ondelete="CASCADE"),
        index=True,
    )
    task_kind: Mapped[OrganizationReportTaskKind] = mapped_column(String(32), index=True)
    status: Mapped[OrganizationReportTaskStatus] = mapped_column(
        String(32),
        default=OrganizationReportTaskStatus.queued.value,
        server_default=OrganizationReportTaskStatus.queued.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lock_token: Mapped[str | None] = mapped_column(String(64))
    run_after: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    submission: Mapped["OrganizationSubmission"] = relationship()
    report: Mapped[OrganizationReport] = relationship(back_populates="tasks")
